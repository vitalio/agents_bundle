from __future__ import annotations

import os
import re
import secrets
import shlex
import stat
import subprocess
import sys
import time
from pathlib import Path

from src.header import (
    DEFAULT_RULES_PKG,
    EMBEDDED_RULE_NAME,
    LEGACY_RULE_ID,
    LEGACY_SPEC_FILE_NAME,
    PRODUCER_NAME,
    PROMPT_HEADER,
    PROTOCOL_VERSION,
    RULES_HEADER,
    SPEC_FILE_NAME,
    VAR_NAME_PATTERN,
)
from src.core import embedded_rule_text, prog_name
from src.tree import _tree_from_args
from src.rules_engine import (
    VAR_NAME_RE,
    _is_external_bundle_source,
    _is_local_path_spec,
    _parse_directive_tokens,
    _parse_md_text,
    _parse_rule_directive_tokens,
    _render_rule_vars,
    _resolve_bundle_context,
    builtin_vars,
    collect_directive_items,
    env_vars,
    eval_if_condition,
    format_collected_rules,
    parse_bundle_ast,
    resolve_bundle_source,
    strip_if_blocks_and_lines,
    wrap_bundle_fragment,
)
from src.includes import IncludeSpan, _expand_include, display_path, merge_spans, read_span, render_span, span_from_fragment
from src.upstream import (
    PipedInput,
    group_fragments,
    meta_chain,
    parse_stdin_pipe,
    strip_section_header,
)


def default_spec_template(prog: str | None = None) -> str:
    cmd = prog or prog_name()
    lines = [
        f"# {SPEC_FILE_NAME} — root context bundle for '{cmd}'",
        "# Directives:",
        "#   bundle <owner>/<repo>[:<name>] [allow=<cmd,...>] [key=val ...]",
        "#   rule <owner>/<repo>:<name...> [key=val ...]",
        "#   file <path|glob|slice...>  (or file $(<shell command>))",
        "#   cmd <shell command>",
        "#   prompt <text>",
        "#   let <name>=<value>  (or let <name>=$(<shell command>); bundle-scoped)",
        "#   export <name...>  (promote to session scope and output preamble)",
        "#   if <cond> / else if <cond> / else  (4-space indented blocks)",
        "#   allow <bin...>  (permit external bundles to run listed executables)",
        "",
        f"bundle {DEFAULT_RULES_PKG}:default",
        "",
        "file AGENTS.md",
        f"cmd {cmd} --tree",
        "cmd git status -sb",
        "cmd git branch -vv",
        "cmd git log --oneline -10",
        "",
    ]
    return "\n".join(lines)


def cmd_init(force: bool = False, target_dir: Path | None = None) -> int:
    prog = prog_name()
    base_dir = (target_dir if target_dir is not None else Path.cwd()).resolve()
    path = base_dir / SPEC_FILE_NAME
    if path.exists() and not force:
        sys.stderr.write(f"{prog}: {path} already exists (use --force to overwrite)\n")
        return 2
    path.write_text(default_spec_template(prog), encoding="utf-8")
    sys.stdout.write(f"{prog}: wrote starter {SPEC_FILE_NAME} to {path}\n")
    return 0


def _normalize_header_name(raw_key: str) -> str:
    segments = []
    for dot_part in raw_key.strip().split("."):
        parts = [part.capitalize() for part in re.split(r"[-_]+", dot_part) if part]
        if parts:
            segments.append("-".join(parts))
    return ".".join(segments)


def _parse_export_keys(raw_args: str, source_label: str, prog: str) -> list[str]:
    tokens = [tok for tok in re.split(r"[\s,]+", raw_args.strip()) if tok]
    keys: list[str] = []
    for tok in tokens:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", tok):
            raise SystemExit(f"{prog}: invalid variable name {tok!r} in {source_label}")
        norm = tok.lower().replace("-", "_")
        if norm and norm not in keys:
            keys.append(norm)
    return keys


def env_plain() -> bool:
    raw = os.environ.get("AGENTS_BUNDLE_PLAIN", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def find_spec_file(start_dir: Path | None = None) -> Path | None:
    cur = (start_dir if start_dir is not None else Path.cwd()).resolve()
    for name in (SPEC_FILE_NAME, LEGACY_SPEC_FILE_NAME):
        candidate = cur / name
        if candidate.is_file():
            return candidate
    return None


_SHELL_WRAPPER_BINS = {"command", "builtin", "exec", "nohup", "time", "env", "nice"}


def _parse_allow_bins(raw_args: str, source_label: str, prog: str) -> list[str]:
    tokens = [tok for tok in re.split(r"[\s,]+", raw_args.strip()) if tok]
    if not tokens:
        raise SystemExit(f"{prog}: empty allow list in {source_label}")
    bins: list[str] = []
    for tok in tokens:
        if not re.fullmatch(r"[A-Za-z0-9_./+-]+", tok):
            raise SystemExit(f"{prog}: invalid command name {tok!r} in {source_label}")
        if tok not in bins:
            bins.append(tok)
    return bins


def _extract_subshells_and_segments(cmd_str: str) -> list[str]:
    segments: list[str] = []
    subshells: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    i = 0
    n = len(cmd_str)
    while i < n:
        ch = cmd_str[i]
        if escaped:
            buf.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            escaped = True
            buf.append(ch)
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            buf.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            buf.append(ch)
            i += 1
            continue
        if not in_single and ch == "$" and i + 1 < n and cmd_str[i + 1] == "(":
            depth = 1
            j = i + 2
            sub_s = False
            sub_d = False
            sub_esc = False
            while j < n and depth > 0:
                c2 = cmd_str[j]
                if sub_esc:
                    sub_esc = False
                elif c2 == "\\" and not sub_s:
                    sub_esc = True
                elif c2 == "'" and not sub_d:
                    sub_s = not sub_s
                elif c2 == '"' and not sub_s:
                    sub_d = not sub_d
                elif not sub_s and not sub_d:
                    if c2 == "(":
                        depth += 1
                    elif c2 == ")":
                        depth -= 1
                j += 1
            inner = cmd_str[i + 2 : j - 1 if depth == 0 else j].strip()
            if inner:
                subshells.append(inner)
            buf.append("__SUBSHELL__")
            i = j
            continue
        if not in_single and ch == "`":
            j = i + 1
            sub_esc = False
            while j < n:
                c2 = cmd_str[j]
                if sub_esc:
                    sub_esc = False
                elif c2 == "\\":
                    sub_esc = True
                elif c2 == "`":
                    break
                j += 1
            inner = cmd_str[i + 1 : j].strip()
            if inner:
                subshells.append(inner)
            buf.append("__SUBSHELL__")
            i = min(n, j + 1)
            continue
        if not in_single and not in_double:
            if cmd_str[i : i + 2] in ("&&", "||"):
                seg = "".join(buf).strip()
                if seg:
                    segments.append(seg)
                buf = []
                i += 2
                continue
            if ch in ("|", ";", "&", "\n"):
                seg = "".join(buf).strip()
                if seg:
                    segments.append(seg)
                buf = []
                i += 1
                continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        segments.append(tail)
    for sub in subshells:
        segments.extend(_extract_subshells_and_segments(sub))
    return segments


def _extract_command_executables(cmd_str: str) -> list[str]:
    exes: list[str] = []
    for raw_seg in _extract_subshells_and_segments(cmd_str):
        seg = raw_seg.strip()
        while seg and seg[0] in ("(", "{", "!"):
            seg = seg[1:].strip()
        while seg and seg[-1] in (")", "}"):
            seg = seg[:-1].strip()
        if not seg or seg.startswith("#"):
            continue
        try:
            tokens = shlex.split(seg, posix=True)
        except ValueError:
            tokens = seg.split()
        idx = 0
        while idx < len(tokens):
            tok = tokens[idx].lstrip("({!").rstrip(")}")
            if not tok or tok in ("!", "(", ")", "{", "}"):
                idx += 1
                continue
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tok, flags=re.DOTALL):
                idx += 1
                continue
            if tok != "__SUBSHELL__":
                exes.append(tok)
            if tok in _SHELL_WRAPPER_BINS:
                idx += 1
                if tok == "command" and idx < len(tokens) and tokens[idx] in ("-v", "-V"):
                    break
                while idx < len(tokens) and (
                    tokens[idx].startswith("-")
                    or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[idx], flags=re.DOTALL)
                ):
                    idx += 1
                continue
            break
    return exes


def _check_command_allowed(
    cmd_str: str,
    allowed_cmds: set[str],
    bundle_label: str,
    prog: str,
) -> None:
    exes = _extract_command_executables(cmd_str)
    for exe in exes:
        if exe not in allowed_cmds:
            raise SystemExit(
                f"{prog}: command {cmd_str!r} (executable {exe!r}) in external bundle "
                f"{bundle_label!r} is not in allowlist (add 'allow {exe}' in {SPEC_FILE_NAME} "
                f"or 'bundle {bundle_label} allow={exe}')"
            )


def _eval_dynamic_expr(
    expr: str,
    work_dir: Path | None = None,
    allowed_cmds: set[str] | None = None,
    bundle_label: str | None = None,
    prog: str | None = None,
) -> str:
    s = expr.strip()
    if s.startswith("$(") and s.endswith(")") and len(s) >= 3:
        cmd = s[2:-1].strip()
        if not cmd:
            return ""
        if allowed_cmds is not None:
            _check_command_allowed(cmd, allowed_cmds, bundle_label or SPEC_FILE_NAME, prog or prog_name())
        cwd = (work_dir if work_dir is not None else Path.cwd()).resolve()
        rc, out, _ = _run_spec_command(cmd, cwd)
        if rc != 0:
            return ""
        return out.strip()
    return s


def _split_file_items(raw_expr: str, is_dynamic: bool) -> list[str]:
    if not raw_expr.strip():
        return []
    if is_dynamic and "\n" in raw_expr:
        return [ln.strip() for ln in raw_expr.splitlines() if ln.strip()]
    try:
        return [tok.strip() for tok in shlex.split(raw_expr) if tok.strip()]
    except ValueError:
        return [tok.strip() for tok in raw_expr.split() if tok.strip()]


def _qualify_nested_target(
    target: str,
    work_dir: Path | None,
    bundle_dir: Path | None,
    default_pkg: str | None,
    pkg_dir: Path | None,
    prog: str,
) -> str:
    if _is_local_path_spec(target) and not Path(target).expanduser().is_absolute():
        if default_pkg is not None and pkg_dir is not None and bundle_dir is not None:
            resolved = (bundle_dir / target).resolve()
            try:
                rel = resolved.relative_to(pkg_dir.resolve())
            except ValueError:
                raise SystemExit(f"{prog}: package path escapes package root: {target}")
            return f"{default_pkg}:{rel.as_posix()}"
        if bundle_dir is not None and work_dir is not None and bundle_dir.resolve() != work_dir.resolve():
            return (bundle_dir / target).resolve().as_posix()
    elif (
        ":" not in target
        and not target.startswith(("http://", "https://", "file://"))
        and default_pkg is not None
    ):
        return f"{default_pkg}:{target}"
    return target


def _static_inspect_bundle_ast(
    nodes: list[tuple[str, object]],
    bvars: dict[str, str],
    allowed_cmds: set[str],
    bundle_label: str,
    root_label: str,
    prog: str,
) -> None:
    sim_vars = dict(bvars)

    def walk(stmts: list[tuple[str, object]]) -> None:
        for n_kind, payload in stmts:
            if n_kind == "if_chain":
                for b_cond, _b_trace, b_body in payload:  # type: ignore[misc]
                    if b_cond is None or eval_if_condition(b_cond, sim_vars, prog):
                        walk(b_body)
                        break
                continue
            raw_line = str(payload)
            line = _render_rule_vars(raw_line, sim_vars).strip()
            if line == "allow" or line.startswith("allow "):
                raise SystemExit(
                    f"{prog}: 'allow' directive is only permitted in root {root_label} "
                    f"(found in bundle {bundle_label!r}: {line!r})"
                )
            if line.startswith("cmd "):
                cmd_str = line[4:].strip()
                if cmd_str:
                    _check_command_allowed(cmd_str, allowed_cmds, bundle_label, prog)
            elif line.startswith("let "):
                assign = line[4:].strip()
                if "=" in assign:
                    k, v_expr = assign.split("=", 1)
                    k_clean = k.strip()
                    s = v_expr.strip()
                    if s.startswith("$(") and s.endswith(")") and len(s) >= 3:
                        cmd_str = s[2:-1].strip()
                        if cmd_str:
                            _check_command_allowed(cmd_str, allowed_cmds, bundle_label, prog)
                    elif not sim_vars.get(k_clean) and s:
                        sim_vars[k_clean] = s
            elif line.startswith("file "):
                inc_expr = line[5:].strip()
                if inc_expr.startswith("$(") and inc_expr.endswith(")") and len(inc_expr) >= 3:
                    cmd_str = inc_expr[2:-1].strip()
                    if cmd_str:
                        _check_command_allowed(cmd_str, allowed_cmds, bundle_label, prog)

    walk(nodes)


def parse_spec(
    text: str,
    work_dir: Path | None = None,
    cli_vars: dict[str, str] | None = None,
    refresh: bool = False,
    resolved_vars: dict[str, str] | None = None,
    piped: bool = False,
    chain: list[str] | None = None,
    active_bundles: list[tuple[str, str]] | None = None,
    default_pkg: str | None = None,
    pkg_dir: Path | None = None,
    bundle_dir: Path | None = None,
    is_external: bool = False,
    allowed_cmds: set[str] | None = None,
    enforce_allowlist: bool = True,
    external_chains: dict[tuple[str, ...], tuple[str, set[str] | None]] | None = None,
    session_vars: dict[str, str] | None = None,
) -> list[tuple[str, str, str | None, list[str]]]:
    prog = prog_name()
    caller_vars: dict[str, str] = dict(cli_vars) if cli_vars is not None else {}
    active_vars: dict[str, str] = dict(caller_vars)
    bvars = {**builtin_vars(work_dir, piped=piped), **active_vars}
    cur_chain = list(chain) if chain else []
    cur_bdir = bundle_dir if bundle_dir is not None else work_dir
    root_label = (
        cur_chain[0]
        if (cur_chain and cur_chain[0] in (SPEC_FILE_NAME, LEGACY_SPEC_FILE_NAME))
        else SPEC_FILE_NAME
    )
    in_child_bundle = bool(cur_chain and cur_chain != [root_label])
    bundle_label = cur_chain[-1] if in_child_bundle else root_label
    cur_allowed: set[str] = set(allowed_cmds) if allowed_cmds is not None else set()
    ast_nodes = parse_bundle_ast(text, prog)

    if is_external and enforce_allowlist and in_child_bundle:
        _static_inspect_bundle_ast(ast_nodes, bvars, cur_allowed, bundle_label, root_label, prog)

    effective_allow_set: set[str] | None = cur_allowed if (is_external and enforce_allowlist) else None
    if is_external and external_chains is not None:
        external_chains[tuple(cur_chain)] = (
            bundle_label,
            set(cur_allowed) if effective_allow_set is not None else None,
        )

    entries: list[tuple[str, str, str | None, list[str]]] = []
    local_exports: list[str] = []

    def promote_export(var_key: str) -> None:
        if var_key not in local_exports:
            local_exports.append(var_key)
        val = active_vars.get(var_key, "")
        if val:
            if session_vars is not None:
                session_vars[var_key] = val
            if resolved_vars is not None:
                resolved_vars[var_key] = val

    def exec_nodes(nodes: list[tuple[str, object]], cond_stack: list[str]) -> None:
        for n_kind, payload in nodes:
            if n_kind == "if_chain":
                for b_cond, b_trace, b_body in payload:  # type: ignore[misc]
                    if b_cond is None or eval_if_condition(b_cond, bvars, prog):
                        exec_nodes(b_body, [*cond_stack, b_trace])
                        break
                continue
            raw_line = str(payload)
            cond_expr = " ".join(c for c in cond_stack if c and c != "else") or None
            line = _render_rule_vars(raw_line, bvars).strip()
            if not line:
                continue
            if line == "allow" or line.startswith("allow "):
                if in_child_bundle:
                    raise SystemExit(
                        f"{prog}: 'allow' directive is only permitted in root {root_label} "
                        f"(found in bundle {bundle_label!r}: {line!r})"
                    )
                if line == "allow":
                    raise SystemExit(f"{prog}: empty allow list in {root_label}")
                cur_allowed.update(_parse_allow_bins(line[len("allow ") :], root_label, prog))
            elif line == "let" or line.startswith("let "):
                assign = line[len("let") :].strip()
                if "=" not in assign:
                    raise SystemExit(
                        f"{prog}: invalid let directive in {bundle_label}: {line!r} (expected 'let key=val')"
                    )
                k, v_expr = assign.split("=", 1)
                k_clean = k.strip()
                if not VAR_NAME_RE.fullmatch(k_clean):
                    raise SystemExit(f"{prog}: invalid variable name {k_clean!r} in {line!r}")
                if not active_vars.get(k_clean):
                    val = _eval_dynamic_expr(
                        v_expr,
                        work_dir=work_dir,
                        allowed_cmds=effective_allow_set,
                        bundle_label=bundle_label,
                        prog=prog,
                    )
                    if val:
                        active_vars[k_clean] = val
                        bvars[k_clean] = val
                        if k_clean in local_exports:
                            if session_vars is not None:
                                session_vars[k_clean] = val
                            if resolved_vars is not None:
                                resolved_vars[k_clean] = val
            elif line == "file" or line.startswith("file "):
                inc_expr = line[len("file") :].strip()
                if not inc_expr:
                    continue
                is_dyn = inc_expr.startswith("$(") and inc_expr.endswith(")") and len(inc_expr) >= 3
                resolved_inc = _eval_dynamic_expr(
                    inc_expr,
                    work_dir=work_dir,
                    allowed_cmds=effective_allow_set,
                    bundle_label=bundle_label,
                    prog=prog,
                )
                for clean_item in _split_file_items(resolved_inc, is_dyn):
                    if is_external and work_dir is not None:
                        _expand_include(work_dir, clean_item, root_dir=work_dir, bundle_label=bundle_label)
                    entries.append(("file", clean_item, cond_expr, list(cur_chain)))
            elif line == "cmd" or line.startswith("cmd "):
                cmd_str = line[len("cmd") :].strip()
                if cmd_str:
                    if effective_allow_set is not None:
                        _check_command_allowed(cmd_str, effective_allow_set, bundle_label, prog)
                    entries.append(("cmd", cmd_str, cond_expr, list(cur_chain)))
            elif line == "rule" or line.startswith("rule "):
                parts = shlex.split(line)
                targets, vmap = _parse_rule_directive_tokens(parts[1:], prog)
                eff_vmap = {**active_vars, **vmap, **caller_vars}
                var_tokens = [f"{k}={v}" for k, v in eff_vmap.items()]
                for tgt in targets:
                    new_tgt = _qualify_nested_target(tgt, work_dir, cur_bdir, default_pkg, pkg_dir, prog)
                    single_line = shlex.join(["rule", new_tgt, *var_tokens])
                    entries.append(("directive", single_line, cond_expr, list(cur_chain)))
            elif line == "bundle" or line.startswith("bundle "):
                parts = shlex.split(line)
                target, _excls, vmap = _parse_directive_tokens(parts[1:], prog)
                bundle_allow_raw = vmap.pop("allow", None)
                child_allowed = set(cur_allowed)
                child_enforce = enforce_allowlist
                if bundle_allow_raw is not None:
                    parsed_bins = set(_parse_allow_bins(bundle_allow_raw, f"bundle {target}", prog))
                    if is_external and enforce_allowlist:
                        disallowed = sorted(parsed_bins - cur_allowed)
                        if disallowed:
                            raise SystemExit(
                                f"{prog}: external bundle {bundle_label!r} cannot grant allow={','.join(disallowed)!r} "
                                f"to child bundle {target!r}"
                            )
                        child_allowed = cur_allowed & parsed_bins
                    else:
                        child_allowed.update(parsed_bins)
                        child_enforce = True
                lookup_target = _qualify_nested_target(target, work_dir, cur_bdir, default_pkg, pkg_dir, prog)
                canonical_bundle, inc_text, child_pkg, child_pkg_dir, child_bdir = _resolve_bundle_context(
                    lookup_target,
                    work_dir=cur_bdir,
                    refresh=refresh,
                    default_pkg=default_pkg or DEFAULT_RULES_PKG,
                )
                cur_active = list(active_bundles) if active_bundles else []
                if any(cid == canonical_bundle for cid, _ in cur_active):
                    cycle_path = " -> ".join([*(lbl for _, lbl in cur_active), target])
                    raise SystemExit(f"{prog}: circular bundle reference detected: {cycle_path}")
                child_is_external = _is_external_bundle_source(
                    canonical_bundle,
                    child_pkg,
                    child_bdir,
                    work_dir,
                    parent_is_external=is_external,
                )
                merged_cli = {**active_vars, **vmap, **caller_vars}
                sub_resolved: dict[str, str] = {}
                child_chain_label = (
                    lookup_target
                    if (default_pkg is not None and ":" not in target and not _is_local_path_spec(target))
                    else target
                )
                child_chain = [*cur_chain, child_chain_label]
                for sub_kind, sub_val, sub_cond, sub_chain in parse_spec(
                    inc_text,
                    work_dir=work_dir,
                    cli_vars=merged_cli,
                    refresh=refresh,
                    resolved_vars=sub_resolved,
                    piped=piped,
                    chain=child_chain,
                    active_bundles=[*cur_active, (canonical_bundle, target)],
                    default_pkg=child_pkg,
                    pkg_dir=child_pkg_dir,
                    bundle_dir=child_bdir,
                    is_external=child_is_external,
                    allowed_cmds=child_allowed,
                    enforce_allowlist=child_enforce,
                    external_chains=external_chains,
                    session_vars=session_vars,
                ):
                    comb_cond = " ".join(c for c in (cond_expr, sub_cond) if c) or None
                    entries.append((sub_kind, sub_val, comb_cond, sub_chain))
                for rk, rv in sub_resolved.items():
                    if not active_vars.get(rk):
                        active_vars[rk] = rv
                        bvars[rk] = rv
                        if resolved_vars is not None:
                            resolved_vars[rk] = rv
                        if session_vars is not None:
                            session_vars[rk] = rv
            elif line == "export" or line.startswith("export "):
                exp_raw = line[len("export") :].strip()
                if not exp_raw:
                    continue
                for var_key in _parse_export_keys(exp_raw, bundle_label, prog):
                    promote_export(var_key)
                    entries.append(("export", var_key, cond_expr, list(cur_chain)))
            elif line == "prompt" or line.startswith("prompt "):
                p_str = line[len("prompt") :].strip()
                if p_str:
                    entries.append(("prompt", p_str, cond_expr, list(cur_chain)))
            else:
                raise SystemExit(
                    f"{prog}: invalid line in {bundle_label}: {line!r} (expected 'bundle ...', 'rule ...', "
                    f"'file ...', 'cmd ...', 'prompt ...', 'let ...', 'export ...', 'if ...', or 'allow ...')"
                )

    exec_nodes(ast_nodes, [])
    return entries


def _run_spec_command(cmd_str: str, cwd: Path) -> tuple[int, str, int]:
    t0 = time.monotonic()
    prog = prog_name()
    self_dir = str(Path(__file__).resolve().parent)
    if re.match(rf"^(?:{re.escape(prog)}|agents_bundle)\s+--tree(?:\s+.*)?$", cmd_str):
        try:
            parts = shlex.split(cmd_str)[2:]
            out = _tree_from_args(parts, default_dir=cwd).rstrip()
            elapsed_ms = max(0, int(round((time.monotonic() - t0) * 1000)))
            return 0, out, elapsed_ms
        except SystemExit as exc:
            elapsed_ms = max(0, int(round((time.monotonic() - t0) * 1000)))
            return 1, str(exc), elapsed_ms

    shell_bin = os.environ.get("AGENTS_BUNDLE_SHELL", "").strip() or "bash"
    env = {**os.environ, "PYTHONUTF8": "1"}
    env["PATH"] = f"{self_dir}{os.pathsep}{Path.home() / '.local/bin'}{os.pathsep}{env.get('PATH', '')}"
    try:
        r = subprocess.run(
            [shell_bin, "-c", cmd_str],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            check=False,
        )
        elapsed_ms = max(0, int(round((time.monotonic() - t0) * 1000)))
        return r.returncode, r.stdout.decode("utf-8", errors="replace").rstrip(), elapsed_ms
    except OSError as exc:
        elapsed_ms = max(0, int(round((time.monotonic() - t0) * 1000)))
        return 1, f"[error running {cmd_str!r}: {exc}]", elapsed_ms


def build_bundle(
    work_dir: Path | None = None,
    extra_files: list[str] | None = None,
    prompt_text: str | None = None,
    refresh: bool = False,
    verbose: bool = False,
    cli_vars: dict[str, str] | None = None,
    raw_argv: list[str] | None = None,
    piped: bool = False,
    records: list[dict[str, object]] | None = None,
    plain: bool = False,
    spec_text: str | None = None,
    upstream: PipedInput | None = None,
) -> tuple[str, list[str]]:
    prog = prog_name()
    if work_dir is not None:
        resolved_wdir = work_dir.resolve()
        if not resolved_wdir.exists():
            sys.stderr.write(f"{prog}: directory not found: {work_dir}\n")
            raise SystemExit(2)
        if not resolved_wdir.is_dir():
            sys.stderr.write(f"{prog}: not a directory: {work_dir}\n")
            raise SystemExit(2)
        wdir = resolved_wdir
    else:
        wdir = Path.cwd().resolve()
    spec_file = find_spec_file(wdir) if spec_text is None else None
    if spec_text is None and spec_file is None:
        sys.stderr.write(
            f"{prog}: {SPEC_FILE_NAME} or {LEGACY_SPEC_FILE_NAME} not found in {wdir} "
            f"(run '{prog} --init' to create a starter template)\n"
        )
        raise SystemExit(2)

    if spec_file is not None:
        spec_dir = spec_file.parent
        spec_source = spec_file.read_text(encoding="utf-8")
        spec_label = spec_file.name
        root_bundles = [(str(spec_file.resolve()), spec_label)]
    else:
        spec_dir = wdir
        spec_source = spec_text or ""
        spec_label = SPEC_FILE_NAME
        root_bundles = []
    effective_cli_vars: dict[str, str] = dict(cli_vars or {})
    cli_allow_raw = effective_cli_vars.pop("allow", None) if spec_file is None else None
    init_allowed: set[str] | None = (
        set(_parse_allow_bins(cli_allow_raw, "allow", prog)) if cli_allow_raw is not None else None
    )
    enforce_allowlist = spec_file is not None or cli_allow_raw is not None
    external_chains: dict[tuple[str, ...], tuple[str, set[str] | None]] = {}
    session_vars: dict[str, str] = dict(effective_cli_vars)
    resolved_vars: dict[str, str] = {}
    entries = parse_spec(
        spec_source,
        work_dir=spec_dir,
        cli_vars=effective_cli_vars,
        refresh=refresh,
        resolved_vars=resolved_vars,
        piped=piped,
        chain=[spec_label] if spec_file is not None else None,
        active_bundles=root_bundles,
        allowed_cmds=init_allowed,
        enforce_allowlist=enforce_allowlist,
        external_chains=external_chains,
        session_vars=session_vars,
    )
    session_vars.update(resolved_vars)
    boundary = secrets.token_hex(16)
    fragment_boundary = None if plain else boundary
    section_blocks: list[str] = []
    warnings: list[str] = []
    pending_rules: list[tuple[str, str, str, list[str]]] = []
    middle_items: list[tuple[str, object]] = []
    spec_prompts: list[tuple[str, list[str]]] = []
    spec_exports: list[str] = []
    up_groups: dict[str, list[tuple[dict[str, object], str]]] = {
        "rules": [],
        "cmds": [],
        "files": [],
        "prompts": [],
    }
    rule_vars = {**builtin_vars(spec_dir, piped=piped), **session_vars}

    def normalize_rule_body(raw_body: str, name: str) -> str:
        return _render_rule_vars(_parse_md_text(raw_body, name)[1], rule_vars).strip()

    if upstream is not None:
        up_groups, unknown_kinds = group_fragments(upstream.fragments)
        for unknown in unknown_kinds:
            warnings.append(f"ignored upstream fragment of unknown kind: {unknown}")
        for up_meta, up_body in up_groups["rules"]:
            up_uid = str(up_meta.get("id") or "")
            if not up_uid:
                warnings.append("ignored upstream rule fragment without id")
                continue
            up_rendered = normalize_rule_body(up_body, up_uid)
            if up_rendered:
                pending_rules.append((up_uid, f"# [upstream rule {up_uid}]", up_rendered, meta_chain(up_meta)))
        for up_meta, up_content in up_groups["cmds"]:
            middle_items.append(("up_cmd", (dict(up_meta), up_content)))
        for up_meta, up_content in up_groups["files"]:
            middle_items.append(("span", span_from_fragment(up_meta, up_content, wdir)))

    for kind, val, cond_expr, entry_chain in entries:
        if kind == "directive":
            parts = shlex.split(val)
            d_kind = parts[0]
            target, excls, vmap = _parse_directive_tokens(parts[1:], prog)
            base_trace = f"if {cond_expr} {d_kind} {target}" if cond_expr else f"{d_kind} {target}"
            trace_chain = [b for b in entry_chain if b not in (SPEC_FILE_NAME, LEGACY_SPEC_FILE_NAME)]
            trace_prefix = [*(f"bundle {b}" for b in trace_chain), base_trace]
            merged_vmap = {**vmap, **session_vars}
            pending_rules.extend(
                collect_directive_items(
                    d_kind,
                    target,
                    excludes=excls,
                    cli_vars=merged_vmap,
                    work_dir=spec_dir,
                    refresh=refresh,
                    trace_prefix=trace_prefix,
                    piped=piped,
                    chain=entry_chain,
                )
            )
        elif kind == "cmd":
            ext_policy = external_chains.get(tuple(entry_chain))
            if ext_policy is not None and ext_policy[1] is not None:
                _check_command_allowed(val, ext_policy[1], ext_policy[0], prog)
            middle_items.append(("cmd", (val, list(entry_chain))))
        elif kind == "export":
            if val not in spec_exports:
                spec_exports.append(val)
        elif kind == "file":
            clean = val.strip()
            if not clean:
                continue
            ext_policy = external_chains.get(tuple(entry_chain))
            slices = _expand_include(
                wdir,
                clean,
                root_dir=spec_dir if ext_policy is not None else None,
                bundle_label=ext_policy[0] if ext_policy is not None else None,
            )
            for p, start, end in slices:
                middle_items.append(("span", read_span(p, display_path(p, spec_dir), start, end, entry_chain)))
        elif kind == "prompt":
            spec_prompts.append((val, entry_chain))

    for extra in extra_files or []:
        clean = extra.strip()
        if not clean:
            continue
        slices = _expand_include(wdir, clean)
        if not slices:
            warnings.append(f"missing file: {clean}")
            continue
        for p, start, end in slices:
            middle_items.append(("span", read_span(p, display_path(p, spec_dir), start, end, [])))

    pending_rules = [r for r in pending_rules if r[0] != LEGACY_RULE_ID]
    embedded = normalize_rule_body(embedded_rule_text(), EMBEDDED_RULE_NAME)
    if embedded:
        pending_rules.append(
            (EMBEDDED_RULE_NAME, f"# [embedded rule {EMBEDDED_RULE_NAME}]", embedded, [EMBEDDED_RULE_NAME])
        )

    if pending_rules:
        formatted = format_collected_rules(pending_rules, verbose=verbose, boundary=fragment_boundary).strip()
        if formatted:
            section_blocks.append(f"{RULES_HEADER}\n{formatted}\n")
            if records is not None:
                seen_rule_uids: set[str] = set()
                for r_uid, _r_prov, _r_body, r_chain in pending_rules:
                    if r_uid in seen_rule_uids:
                        continue
                    seen_rule_uids.add(r_uid)
                    records.append(
                        {
                            "kind": "rule",
                            "id": r_uid,
                            "chain": list(r_chain),
                        }
                    )

    raw_spans: list[IncludeSpan] = [item[1] for item in middle_items if item[0] == "span"]  # type: ignore[misc]
    merged_span_list = merge_spans(raw_spans)
    merged_by_id = {id(s): s for s in merged_span_list}
    # Map each first-occurrence key/range position to the surviving merged span
    surviving_spans = list(merged_span_list)
    used_merged: set[int] = set()

    for m_kind, m_payload in middle_items:
        if m_kind == "up_cmd":
            up_meta, up_content = m_payload  # type: ignore[misc]
            wrapped_up = wrap_bundle_fragment(fragment_boundary, dict(up_meta), up_content)
            section_blocks.append(f"{wrapped_up}\n")
            if records is not None:
                records.append(dict(up_meta))
        elif m_kind == "cmd":
            cmd_val, cmd_chain = m_payload  # type: ignore[misc]
            rc, out, elapsed_ms = _run_spec_command(cmd_val, spec_dir)
            if rc != 0:
                warnings.append(f"command exited {rc}: {cmd_val}")
            cmd_meta: dict[str, object] = {
                "kind": "cmd",
                "name": cmd_val,
                "chain": list(cmd_chain),
                "rc": rc,
                "ms": elapsed_ms,
            }
            wrapped_cmd = wrap_bundle_fragment(fragment_boundary, cmd_meta, f"===== $ {cmd_val} =====\n{out}")
            section_blocks.append(f"{wrapped_cmd}\n")
            if records is not None:
                records.append(cmd_meta)
        elif m_kind == "span":
            orig_span: IncludeSpan = m_payload  # type: ignore[assignment]
            chosen: IncludeSpan | None = None
            if id(orig_span) in merged_by_id and id(orig_span) not in used_merged:
                chosen = orig_span
            else:
                for cand in surviving_spans:
                    if id(cand) not in used_merged and cand.key == orig_span.key:
                        if cand.whole_text is not None or (
                            orig_span.start is not None
                            and orig_span.end is not None
                            and cand.start is not None
                            and cand.end is not None
                            and cand.start <= orig_span.end
                            and orig_span.start <= cand.end
                        ):
                            chosen = cand
                            break
            if chosen is None:
                continue
            used_merged.add(id(chosen))
            inc_meta, inc_text = render_span(chosen)
            wrapped_inc = wrap_bundle_fragment(fragment_boundary, inc_meta, inc_text)
            section_blocks.append(f"{wrapped_inc}\n")
            if records is not None:
                records.append(inc_meta)

    all_prompt_items = [*spec_prompts]
    if prompt_text and prompt_text.strip():
        all_prompt_items.append((prompt_text.strip(), []))
    prompt_frags: list[tuple[dict[str, object], str]] = [
        (dict(m), strip_section_header(c, PROMPT_HEADER)) for m, c in up_groups["prompts"]
    ]
    n_upstream_prompts = len(prompt_frags)
    if all_prompt_items:
        first_chain = all_prompt_items[0][1]
        shared_chain = list(first_chain) if all(p_chain == first_chain for _p_text, p_chain in all_prompt_items) else []
        prompt_meta: dict[str, object] = {
            "kind": "prompt",
            "chain": shared_chain,
        }
        prompt_frags.append((prompt_meta, "\n\n".join(text for text, _ in all_prompt_items)))
    if prompt_frags:
        wrapped_parts = [
            wrap_bundle_fragment(fragment_boundary, meta, f"{PROMPT_HEADER}\n{body}" if idx == 0 else body)
            for idx, (meta, body) in enumerate(prompt_frags)
        ]
        section_blocks.append(("\n" if fragment_boundary else "\n\n").join(wrapped_parts) + "\n")
        if records is not None:
            for meta, _body in prompt_frags[:n_upstream_prompts]:
                records.append(dict(meta))
            for _p_text, p_chain in all_prompt_items:
                records.append(
                    {
                        "kind": "prompt",
                        "chain": list(p_chain),
                    }
                )

    header_lines: list[str] = []
    if not plain:
        cmd_line = shlex.join([prog, *raw_argv]) if raw_argv else prog
        if upstream is not None and upstream.command:
            cmd_line = f"{upstream.command} | {cmd_line}"
        header_lines.extend(
            [
                f"Bundle-Command: {cmd_line}",
                f"Bundle-Name: {PRODUCER_NAME}",
                f"Bundle-Boundary: {boundary}",
                f"Bundle-Protocol: {PROTOCOL_VERSION}",
            ]
        )
    for exp_key in spec_exports:
        if exp_key == "workdir":
            continue
        val = session_vars.get(exp_key, "")
        if val != "":
            hdr_key = _normalize_header_name(exp_key)
            header_lines.append(f"{hdr_key}: {val}")
    header_lines.append(f"Workdir: {wdir}")
    header = "\n".join(header_lines) + "\n"
    blocks = [header, *section_blocks]
    return "\n".join(blocks), warnings


def _stdin_is_fifo() -> bool:
    try:
        return stat.S_ISFIFO(os.fstat(sys.stdin.fileno()).st_mode)
    except (AttributeError, OSError, ValueError):
        return False


def cmd_bundle(
    argv: list[str],
    bundle_target: str | None = None,
    raw_argv: list[str] | None = None,
) -> int:
    prog = prog_name()
    work_dir: Path | None = None
    prompt_parts: list[str] = []
    extra_files: list[str] = []
    cli_vars: dict[str, str] = env_vars(prog)
    refresh = False
    verbose = False
    plain = env_plain()
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--refresh":
            refresh = True
            i += 1
        elif a in ("-v", "--verbose"):
            verbose = True
            i += 1
        elif a == "--plain":
            plain = True
            i += 1
        elif a in ("-p", "--prompt"):
            if i + 1 >= len(argv):
                raise SystemExit(f"{prog}: {a} requires an argument")
            prompt_parts.append(argv[i + 1])
            i += 2
        elif a in ("-C", "--dir"):
            if i + 1 >= len(argv):
                raise SystemExit(f"{prog}: {a} requires a directory path")
            work_dir = Path(argv[i + 1]).expanduser()
            i += 2
        elif a.startswith("-"):
            raise SystemExit(f"{prog}: unknown option: {a}")
        elif "=" in a and re.fullmatch(rf"{VAR_NAME_PATTERN}=.*", a, flags=re.DOTALL) and not Path(a).exists():
            k, v = a.split("=", 1)
            cli_vars[k.strip()] = v.strip()
            i += 1
        else:
            extra_files.append(a)
            i += 1

    piped_workdir: str | None = None
    has_piped_prompt = False
    upstream: PipedInput | None = None
    if bundle_target is None and not sys.stdin.isatty():
        try:
            piped_raw = sys.stdin.read()
        except Exception:
            piped_raw = ""
        if not piped_raw.strip() and _stdin_is_fifo():
            sys.stderr.write(f"{prog}: empty piped input on stdin (upstream command failed?)\n")
            return 2
        if piped_raw.strip():
            upstream = parse_stdin_pipe(piped_raw)
            piped_workdir = upstream.workdir
            for ik, iv in upstream.vars.items():
                if not cli_vars.get(ik):
                    cli_vars[ik] = iv
            has_piped_prompt = upstream.has_prompt
            if upstream.prompt:
                prompt_parts.insert(0, upstream.prompt)

    if work_dir is None and piped_workdir is not None:
        if not piped_workdir:
            sys.stderr.write(f"{prog}: empty Workdir in piped input\n")
            return 2
        work_dir = Path(piped_workdir).expanduser()

    prompt_text = "\n\n".join(prompt_parts) if prompt_parts else None
    body, warnings = build_bundle(
        work_dir=work_dir,
        extra_files=extra_files,
        prompt_text=prompt_text,
        refresh=refresh,
        verbose=verbose,
        cli_vars=cli_vars,
        raw_argv=raw_argv if raw_argv is not None else argv,
        piped=has_piped_prompt,
        plain=plain,
        spec_text=None if bundle_target is None else f"bundle {shlex.quote(bundle_target)}",
        upstream=upstream,
    )
    for w in warnings:
        sys.stderr.write(f"{prog}: warning: {w}\n")
    sys.stdout.write(body)
    return 0
