from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from src.header import DEFAULT_RULES_PKG, VAR_NAME_PATTERN, VERSION
from src.core import cache_dir_path, prog_name


VAR_NAME_RE = re.compile(VAR_NAME_PATTERN)
RULE_VAR_RE = re.compile(rf"\{{({VAR_NAME_PATTERN}):([^{{}}]*)\}}")


def _render_rule_vars(text: str, vars_map: dict[str, str]) -> str:
    return RULE_VAR_RE.sub(lambda m: vars_map.get(m.group(1), m.group(2)), text)


def _detect_os_name() -> str:
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _detect_vcs_name(work_dir: Path | None = None) -> str:
    wdir = (work_dir if work_dir is not None else Path.cwd()).resolve()
    cur = wdir
    while True:
        if (cur / ".git").exists():
            return "git"
        if (cur / "CVS").is_dir():
            return "cvs"
        if cur.parent == cur:
            break
        cur = cur.parent
    return ""


def builtin_vars(work_dir: Path | None = None, piped: bool = False) -> dict[str, str]:
    return {
        "os": _detect_os_name(),
        "vcs": _detect_vcs_name(work_dir),
        "piped": "1" if piped else "",
    }


def env_vars(prog: str | None = None) -> dict[str, str]:
    raw = os.environ.get("CONTEXT_BUNDLE_VARS", "").strip()
    if not raw:
        return {}
    p = prog or prog_name()
    try:
        tokens = shlex.split(raw)
    except ValueError as exc:
        raise SystemExit(f"{p}: invalid CONTEXT_BUNDLE_VARS={raw!r}: {exc}")
    out: dict[str, str] = {}
    for tok in tokens:
        if "=" not in tok:
            raise SystemExit(f"{p}: invalid entry {tok!r} in CONTEXT_BUNDLE_VARS (expected key=val)")
        k, v = tok.split("=", 1)
        k_clean = k.strip()
        if not VAR_NAME_RE.fullmatch(k_clean):
            raise SystemExit(f"{p}: invalid variable name {k_clean!r} in CONTEXT_BUNDLE_VARS")
        out[k_clean] = v.strip()
    return out


def _validate_if_condition_tokens(cond_expr: str, prog: str) -> list[tuple[str, str, set[str]]]:
    s = cond_expr.strip()
    if s.endswith(":"):
        raise SystemExit(f"{prog}: trailing ':' is not allowed in condition {cond_expr!r}")
    try:
        tokens = shlex.split(s)
    except ValueError as exc:
        raise SystemExit(f"{prog}: invalid condition {cond_expr!r}: {exc}")
    if not tokens:
        raise SystemExit(f"{prog}: empty if condition")
    parsed: list[tuple[str, str, set[str]]] = []
    for tok in tokens:
        if "!=" in tok:
            k, expected = tok.split("!=", 1)
            op = "!="
        elif "=" in tok:
            k, expected = tok.split("=", 1)
            op = "="
        else:
            raise SystemExit(
                f"{prog}: invalid condition token {tok!r} in 'if {cond_expr}' (expected key=val or key!=val)"
            )
        k_clean = k.strip()
        if not VAR_NAME_RE.fullmatch(k_clean):
            raise SystemExit(f"{prog}: invalid variable name {k_clean!r} in condition {cond_expr!r}")
        allowed = {v.strip() for v in expected.split(",")}
        parsed.append((op, k_clean, allowed))
    return parsed


def eval_if_condition(cond_expr: str, vars_map: dict[str, str], prog: str | None = None) -> bool:
    p = prog or prog_name()
    for op, k, allowed in _validate_if_condition_tokens(cond_expr, p):
        actual = vars_map.get(k, "")
        if op == "!=":
            if actual in allowed:
                return False
        else:
            if actual not in allowed:
                return False
    return True


def _preprocess_bundle_lines(raw_text: str, prog: str) -> list[tuple[int, str]]:
    """Extract non-empty, non-comment lines with validated 4-space indentation."""
    lines_out: list[tuple[int, str]] = []
    for raw_line in raw_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        leading = raw_line[: len(raw_line) - len(raw_line.lstrip())]
        if "\t" in leading:
            raise SystemExit(f"{prog}: tabs are not allowed in indentation: {raw_line!r}")
        raw_indent = len(leading)
        if raw_indent % 4 != 0:
            raise SystemExit(f"{prog}: indentation must be a multiple of 4 spaces: {raw_line!r}")
        if stripped.lower() == "endif":
            raise SystemExit(f"{prog}: 'endif' is not supported; use 4-space indented blocks: {raw_line!r}")
        lines_out.append((raw_indent, stripped))
    return lines_out


def _match_cond_header(text: str, prog: str) -> tuple[str, str | None] | None:
    if text == "if" or text.startswith("if ") or text.startswith("if:"):
        cond = text[2:].strip()
        if not cond or cond == ":":
            raise SystemExit(f"{prog}: empty if condition")
        _validate_if_condition_tokens(cond, prog)
        return "if", cond
    if text in ("else if", "elif") or text.startswith("else if ") or text.startswith("elif "):
        kw = "else if" if text.startswith("else if") else "elif"
        cond = text[len(kw) :].strip()
        if not cond or cond == ":":
            raise SystemExit(f"{prog}: empty {kw} condition")
        _validate_if_condition_tokens(cond, prog)
        return "elif", cond
    if text == "else" or text.startswith("else ") or text == "else:":
        if text == "else:":
            raise SystemExit(f"{prog}: trailing ':' is not allowed in 'else'")
        rest = text[4:].strip()
        if rest:
            raise SystemExit(f"{prog}: unexpected text after 'else': {text!r}")
        return "else", None
    return None


def parse_bundle_ast(raw_text: str, prog: str | None = None) -> list[tuple[str, object]]:
    """Parse bundle text into an AST of ('line', text) and ('if_chain', branches).

    Each branch in 'if_chain' is (cond_expr_or_None, trace_cond_str, body_ast).
    """
    p = prog or prog_name()
    lines = _preprocess_bundle_lines(raw_text, p)
    n = len(lines)

    def parse_block(start_idx: int, expected_indent: int) -> tuple[list[tuple[str, object]], int]:
        stmts: list[tuple[str, object]] = []
        idx = start_idx
        while idx < n:
            indent, text = lines[idx]
            if indent < expected_indent:
                break
            if indent > expected_indent:
                raise SystemExit(f"{p}: unexpected indentation at {text!r}")
            hdr = _match_cond_header(text, p)
            if hdr is None:
                stmts.append(("line", text))
                idx += 1
                continue
            kw, cond = hdr
            if kw in ("elif", "else"):
                raise SystemExit(f"{p}: unexpected {kw!r} without matching 'if': {text!r}")
            assert cond is not None
            branches: list[tuple[str | None, str, list[tuple[str, object]]]] = []
            idx += 1
            if idx >= n or lines[idx][0] <= expected_indent:
                raise SystemExit(f"{p}: expected 4-space indented block after 'if {cond}'")
            if lines[idx][0] != expected_indent + 4:
                raise SystemExit(f"{p}: expected 4-space indented block after 'if {cond}' (got {lines[idx][0] - expected_indent} spaces)")
            body, idx = parse_block(idx, expected_indent + 4)
            if not body:
                raise SystemExit(f"{p}: empty 'if {cond}' block")
            branches.append((cond, cond, body))
            seen_else = False
            while idx < n and lines[idx][0] == expected_indent:
                next_hdr = _match_cond_header(lines[idx][1], p)
                if next_hdr is None or next_hdr[0] == "if":
                    break
                n_kw, n_cond = next_hdr
                if seen_else:
                    raise SystemExit(f"{p}: unexpected {n_kw!r} after 'else': {lines[idx][1]!r}")
                hdr_label = lines[idx][1]
                idx += 1
                if idx >= n or lines[idx][0] <= expected_indent:
                    raise SystemExit(f"{p}: expected 4-space indented block after {hdr_label!r}")
                if lines[idx][0] != expected_indent + 4:
                    raise SystemExit(f"{p}: expected 4-space indented block after {hdr_label!r}")
                b_body, idx = parse_block(idx, expected_indent + 4)
                if not b_body:
                    raise SystemExit(f"{p}: empty {hdr_label!r} block")
                if n_kw == "else":
                    seen_else = True
                    branches.append((None, "else", b_body))
                else:
                    assert n_cond is not None
                    branches.append((n_cond, n_cond, b_body))
            stmts.append(("if_chain", branches))
        return stmts, idx

    ast_root, end_idx = parse_block(0, 0)
    if end_idx < n:
        raise SystemExit(f"{p}: unexpected indentation at {lines[end_idx][1]!r}")
    return ast_root


def strip_if_blocks_and_lines(raw_text: str, prog: str | None = None) -> list[tuple[str | None, str]]:
    """Flatten bundle AST into (cond_expr_or_None, inner_line) pairs."""
    p = prog or prog_name()
    out: list[tuple[str | None, str]] = []

    def walk(nodes: list[tuple[str, object]], stack: list[str]) -> None:
        for kind, payload in nodes:
            if kind == "line":
                comb = " ".join(c for c in stack if c and c != "else") or None
                out.append((comb, str(payload)))
            elif kind == "if_chain":
                for _cond, trace_c, body in payload:  # type: ignore[misc]
                    walk(body, [*stack, trace_c])

    walk(parse_bundle_ast(raw_text, p), [])
    return out


def _parse_md_text(raw_text: str, fallback_desc: str) -> tuple[str, str]:
    cleaned = re.sub(r"<!--.*?-->", "", raw_text, flags=re.DOTALL)
    lines = cleaned.splitlines()
    desc = fallback_desc
    body_lines: list[str] = []
    in_fence = False
    for idx, line in enumerate(lines):
        s = line.strip()
        if idx == 0 and s.startswith("# Description:"):
            desc = s.split(":", 1)[1].strip()
            continue
        if s.startswith("```"):
            in_fence = not in_fence
        if not in_fence and re.match(r"^#(?!#)", s):
            continue
        body_lines.append(line)
    return desc, "\n".join(body_lines).strip("\r\n")


def _parse_rule_directive_tokens(tokens: list[str], prog: str) -> tuple[list[str], dict[str, str]]:
    if not tokens:
        raise SystemExit(f"{prog}: missing target in rule directive")
    targets: list[str] = []
    vars_map: dict[str, str] = {}
    seen_var = False
    for tok in tokens:
        s = tok.strip()
        if not s:
            continue
        if s.startswith("-"):
            raise SystemExit(f"{prog}: excludes are not supported: {s!r}")
        if "=" in s:
            seen_var = True
            k, v = s.split("=", 1)
            k_clean = k.strip()
            if not VAR_NAME_RE.fullmatch(k_clean):
                raise SystemExit(f"{prog}: invalid variable name {k_clean!r} in {s!r}")
            vars_map[k_clean] = v.strip()
        elif not seen_var:
            targets.append(s)
        else:
            raise SystemExit(f"{prog}: unexpected argument {s!r} after key=val in rule directive")
    if not targets:
        raise SystemExit(f"{prog}: missing target in rule directive")
    return targets, vars_map


def _parse_directive_tokens(tokens: list[str], prog: str) -> tuple[str, list[str], dict[str, str]]:
    if not tokens:
        raise SystemExit(f"{prog}: missing target in bundle/rule directive")
    targets, vars_map = _parse_rule_directive_tokens(tokens, prog)
    if len(targets) > 1:
        raise SystemExit(f"{prog}: unexpected argument {targets[1]!r} after target {targets[0]!r}")
    return targets[0], [], vars_map


def _load_package_from_dir(
    pkg_dir: Path,
) -> tuple[
    dict[str, tuple[str, str]],
    dict[str, tuple[str, str]],
]:
    rules: dict[str, tuple[str, str]] = {}
    bundles: dict[str, tuple[str, str]] = {}
    a_root = pkg_dir / "agents"
    if a_root.is_dir():
        for p in sorted(a_root.rglob("*.md")):
            if p.is_file() and p.name.upper() not in ("AGENTS.MD", "README.MD"):
                rel = p.relative_to(a_root).with_suffix("").as_posix().lower()
                rules[rel] = _parse_md_text(p.read_text(encoding="utf-8", errors="replace"), rel)
        for p in sorted(a_root.rglob("*.bundle")):
            if p.is_file():
                rel = p.relative_to(a_root).with_suffix("").as_posix().lower()
                bundles[rel] = _parse_md_text(p.read_text(encoding="utf-8", errors="replace"), rel)
    return dict(sorted(rules.items())), dict(sorted(bundles.items()))


URL_ORIGIN_SUFFIX = ".origin"
_REFRESHED: set[str] = set()


def _first_refresh(key: str, refresh: bool) -> bool:
    """Honor a refresh request only once per process for each remote key."""
    if not refresh or key in _REFRESHED:
        return False
    _REFRESHED.add(key)
    return True


def _split_pkg_ref(pkg_spec: str, prog: str) -> tuple[str, str]:
    if "@" in pkg_spec and not pkg_spec.startswith("git@"):
        repo_part, ref = pkg_spec.rsplit("@", 1)
        if not repo_part.strip() or not ref.strip():
            raise SystemExit(f"{prog}: invalid package reference {pkg_spec!r}")
        return repo_part, ref
    if pkg_spec.startswith("git@") and "@" in pkg_spec[4:]:
        repo_part, ref = pkg_spec.rsplit("@", 1)
        if not repo_part.strip() or not ref.strip():
            raise SystemExit(f"{prog}: invalid package reference {pkg_spec!r}")
        return repo_part, ref
    return pkg_spec, ""


def _ensure_remote_package(pkg_spec: str, refresh: bool = False) -> Path:
    prog = prog_name()
    repo_part, ref = _split_pkg_ref(pkg_spec, prog)
    local_override = os.environ.get("CONTEXT_BUNDLE_LOCAL_PKG_DIR")
    if not ref and local_override and Path(local_override).is_dir():
        lo_path = Path(local_override)
        sub_pkg = lo_path / repo_part
        if sub_pkg.is_dir():
            return sub_pkg
        if pkg_spec == DEFAULT_RULES_PKG or (lo_path / "agents").is_dir():
            return lo_path
    refresh = _first_refresh(f"pkg:{pkg_spec}", refresh)

    if repo_part.startswith(("http://", "https://", "git@")):
        url = repo_part
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", repo_part.strip("/"))
    elif re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo_part):
        url = f"https://github.com/{repo_part}.git"
        slug = repo_part
    else:
        raise SystemExit(f"{prog}: invalid package reference {pkg_spec!r}")

    cdir = cache_dir_path() / "packages" / (f"{slug}@{ref}" if ref else slug)
    if cdir.is_dir() and not refresh:
        return cdir
    cdir.parent.mkdir(parents=True, exist_ok=True)
    if cdir.is_dir() and refresh:
        shutil.rmtree(cdir, ignore_errors=True)
    cmd = ["git", "clone", "--depth", "1"]
    if ref:
        cmd.extend(["--branch", ref])
    cmd.extend([url, str(cdir)])
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if r.returncode != 0:
        raise SystemExit(f"{prog}: failed to fetch package {pkg_spec!r}: {r.stderr.strip()}")
    return cdir


def _resolve_package_dir(
    pkg_id: str,
    work_dir: Path | None = None,
    refresh: bool = False,
) -> Path:
    prog = prog_name()
    is_explicit_path = pkg_id in (".", "..") or pkg_id.startswith(("./", "../", "~/", "/"))
    if "@" not in pkg_id or is_explicit_path:
        local_dir = Path(pkg_id).expanduser()
        if work_dir is not None and not local_dir.is_absolute():
            cand = (work_dir / local_dir).resolve()
            if cand.is_dir():
                return cand
        if local_dir.is_dir():
            return local_dir.resolve()
        if is_explicit_path:
            raise SystemExit(f"{prog}: package directory not found: {pkg_id}")
    return _ensure_remote_package(pkg_id, refresh=refresh)


def _get_package_catalog(
    pkg_id: str,
    refresh: bool = False,
    work_dir: Path | None = None,
) -> tuple[
    dict[str, tuple[str, str]],
    dict[str, tuple[str, str]],
]:
    pkg_dir = _resolve_package_dir(pkg_id, work_dir=work_dir, refresh=refresh)
    return _load_package_from_dir(pkg_dir)


def _download_url_text(url: str) -> str:
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": f"context-bundle/{VERSION}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8")


def _fetch_url_file(url: str, refresh: bool = False) -> Path:
    prog = prog_name()
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", url)
    cpath = cache_dir_path() / "urls" / slug
    refresh = _first_refresh(f"url:{url}", refresh)
    if cpath.is_file() and not refresh:
        return cpath
    cpath.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = _download_url_text(url)
        cpath.write_text(data, encoding="utf-8")
        cpath.with_name(cpath.name + URL_ORIGIN_SUFFIX).write_text(url + "\n", encoding="utf-8")
    except Exception as exc:
        raise SystemExit(f"{prog}: failed to fetch {url!r}: {exc}")
    return cpath


def _is_local_path_spec(spec: str) -> bool:
    s = spec.strip()
    return s in (".", "..") or s.startswith(("./", "../", "~/", "/"))


def _is_repo_shorthand_spec(spec: str) -> bool:
    s = spec.strip()
    if ":" in s or _is_local_path_spec(s) or s.startswith(("http://", "https://", "file://")):
        return False
    return re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:@[A-Za-z0-9_./-]+)?", s) is not None


def _target_exists_in_pkg(
    pkg_dir: Path,
    target: str,
    kind: str = "rule",
) -> bool:
    rules_dict, bundles_dict = _load_package_from_dir(pkg_dir)
    if kind == "bundle":
        if _match_bundle_in_dict(target, bundles_dict, repo_shorthand=False) is not None:
            return True
        return _resolve_package_rel_file(pkg_dir, target, (".bundle",)) is not None
    if _match_rule_in_dict(target, rules_dict, repo_shorthand=False) is not None:
        return True
    return _resolve_package_rel_file(pkg_dir, target, (".md",)) is not None


def _parse_target_spec(
    spec: str,
    default_pkg: str | None = None,
    allow_repo_shorthand: bool = False,
    work_dir: Path | None = None,
    refresh: bool = False,
    kind: str = "bundle",
) -> tuple[str, str]:
    prog = prog_name()
    if ":" not in spec and _is_local_path_spec(spec):
        return "__file__", spec.strip()
    if spec.startswith(("http://", "https://", "file://")):
        idx = spec.rfind(":")
        scheme_end = spec.find("://") + 2
        if idx <= scheme_end or spec.endswith((".md", ".bundle")):
            return "__url__", spec
        return spec[:idx], spec[idx + 1:].strip().lower()
    if ":" not in spec:
        s_clean = spec.strip()
        if default_pkg and "@" not in s_clean:
            if not (allow_repo_shorthand and _is_repo_shorthand_spec(s_clean)):
                return default_pkg, s_clean.lower()
            try:
                def_dir = _resolve_package_dir(default_pkg, work_dir=work_dir, refresh=refresh)
            except SystemExit:
                def_dir = None
            if def_dir is not None and _target_exists_in_pkg(def_dir, s_clean, kind=kind):
                return default_pkg, s_clean.lower()
        if allow_repo_shorthand and _is_repo_shorthand_spec(s_clean):
            repo_leaf = s_clean.split("@", 1)[0].rsplit("/", 1)[-1].lower()
            return s_clean, repo_leaf
        if default_pkg:
            return default_pkg, s_clean.lower()
        raise SystemExit(
            f"{prog}: missing package prefix in {spec!r} (expected '<owner>/<repo>:{spec}' or './path')"
        )
    pkg, item = spec.split(":", 1)
    if not pkg.strip() or not item.strip():
        raise SystemExit(f"{prog}: invalid target {spec!r}; expected <package>:<item>")
    return pkg.strip(), item.strip().lower()


def _strip_item_affixes(
    name: str,
    prefixes: tuple[str, ...],
    suffixes: tuple[str, ...],
) -> list[str]:
    s = name.strip().lower()
    while s.startswith("./"):
        s = s[2:]
    for suf in suffixes:
        if s.endswith(suf) and len(s) > len(suf):
            s = s[: -len(suf)]
            break
    candidates = [s]
    for pref in prefixes:
        if s.startswith(pref) and len(s) > len(pref):
            stripped = s[len(pref) :]
            if stripped not in candidates:
                candidates.append(stripped)
    return candidates


def _match_exact_or_norm(key: str, mapping: dict[str, object]) -> str | None:
    if key in mapping:
        return key
    norm = key.replace("-", "_")
    for k in mapping:
        if k.replace("-", "_") == norm:
            return k
    return None


def _match_rule_in_dict(
    name: str,
    rules_dict: dict[str, tuple[str, str]],
    repo_shorthand: bool = False,
) -> str | None:
    for cand in _strip_item_affixes(name, ("agents/",), (".md",)):
        leaf = cand.rsplit("/", 1)[-1]
        for probe in (cand, f"{cand}/{leaf}"):
            hit = _match_exact_or_norm(probe, rules_dict)
            if hit is not None:
                return hit
        norm = cand.replace("-", "_")
        matches = [k for k in rules_dict if k.rsplit("/", 1)[-1].replace("-", "_") == norm]
        if len(matches) == 1:
            return matches[0]
    if repo_shorthand:
        for probe in ("default", "default/default"):
            hit = _match_exact_or_norm(probe, rules_dict)
            if hit is not None:
                return hit
        if len(rules_dict) == 1:
            return next(iter(rules_dict))
    return None


def _is_invariant_condition_var(var_name: str, dynamic_vars: set[str] | None = None) -> bool:
    return var_name in ("os", "vcs") and (dynamic_vars is None or var_name not in dynamic_vars)


def _cond_is_invariant(
    cond_expr: str | None,
    dynamic_vars: set[str] | None = None,
    prog: str | None = None,
) -> bool:
    if not cond_expr:
        return True
    p = prog or prog_name()
    for _op, k, _allowed in _validate_if_condition_tokens(cond_expr, p):
        if not _is_invariant_condition_var(k, dynamic_vars):
            return False
    return True


def _rule_template_is_invariant(
    raw_body: str,
    dynamic_vars: set[str] | None = None,
) -> bool:
    dyn = dynamic_vars or set()
    for m in RULE_VAR_RE.finditer(raw_body):
        k = m.group(1)
        if "." in k or k in ("role", "task", "title", "piped") or k in dyn:
            return False
    return True


def _match_bundle_in_dict(
    name: str,
    bundles_dict: dict[str, tuple[str, str]],
    repo_shorthand: bool = False,
) -> str | None:
    for cand in _strip_item_affixes(
        name,
        ("agents/",),
        (".bundle",),
    ):
        leaf = cand.rsplit("/", 1)[-1]
        for probe in (cand, f"{cand}/{leaf}", f"{cand}/default"):
            hit = _match_exact_or_norm(probe, bundles_dict)
            if hit is not None:
                return hit
        norm = cand.replace("-", "_")
        if norm != "default":
            matches = [k for k in bundles_dict if k.rsplit("/", 1)[-1].replace("-", "_") == norm]
            if len(matches) == 1:
                return matches[0]
    if repo_shorthand:
        for probe in ("default", "default/default"):
            hit = _match_exact_or_norm(probe, bundles_dict)
            if hit is not None:
                return hit
    return None


def _resolve_package_rel_file(
    pkg_dir: Path,
    raw_item: str,
    suffixes: tuple[str, ...],
) -> tuple[str, Path] | None:
    prog = prog_name()
    clean = raw_item.strip()
    if not clean or Path(clean).is_absolute():
        return None
    pkg_root = pkg_dir.resolve()
    candidates = [pkg_dir / clean]
    for suf in suffixes:
        if not clean.lower().endswith(suf):
            candidates.append(pkg_dir / f"{clean}{suf}")
    for cand in candidates:
        resolved = cand.resolve()
        try:
            rel = resolved.relative_to(pkg_root)
        except ValueError:
            raise SystemExit(f"{prog}: package path escapes package root: {raw_item}")
        if resolved.is_file():
            rel_key = (
                rel.with_suffix("").as_posix().lower()
                if rel.suffix.lower() in suffixes
                else rel.as_posix().lower()
            )
            return rel_key, resolved
    return None


def _find_bundle_file_in_pkg(pkg_dir: Path, ik: str) -> Path | None:
    cand = pkg_dir / "agents" / f"{ik}.bundle"
    if cand.is_file():
        return cand.resolve()
    return None


def _is_external_bundle_source(
    canonical_id: str,
    child_pkg: str | None,
    child_bdir: Path | None,
    root_dir: Path | None,
    parent_is_external: bool = False,
) -> bool:
    if parent_is_external or child_pkg is not None or child_bdir is None or root_dir is None:
        return True
    try:
        fpath = Path(canonical_id).resolve()
        fpath.relative_to(root_dir.resolve())
    except ValueError:
        return True
    try:
        fpath.relative_to(cache_dir_path().resolve())
        return True
    except ValueError:
        pass
    local_override = os.environ.get("CONTEXT_BUNDLE_LOCAL_PKG_DIR")
    if local_override:
        try:
            fpath.relative_to(Path(local_override).resolve())
            return True
        except ValueError:
            pass
    return False


def _resolve_bundle_context(
    target_spec: str,
    work_dir: Path | None = None,
    refresh: bool = False,
    default_pkg: str | None = DEFAULT_RULES_PKG,
    kind_label: str = "bundle",
) -> tuple[str, str, str | None, Path | None, Path | None]:
    prog = prog_name()
    pkg_id, item_name = _parse_target_spec(
        target_spec,
        default_pkg=default_pkg,
        allow_repo_shorthand=True,
        work_dir=work_dir,
        refresh=refresh,
        kind="bundle",
    )
    if pkg_id in ("__file__", "__url__"):
        if pkg_id == "__url__":
            fpath = _fetch_url_file(item_name, refresh=refresh)
            raw = fpath.read_text(encoding="utf-8", errors="replace")
            return item_name, _parse_md_text(raw, fpath.stem)[1], None, None, None
        fpath = Path(item_name).expanduser()
        if work_dir is not None and not fpath.is_absolute():
            fpath = (work_dir / fpath).resolve()
        else:
            fpath = fpath.resolve()
        if fpath.is_dir():
            _, bundles_dict = _load_package_from_dir(fpath)
            ik = _match_bundle_in_dict(fpath.name.lower(), bundles_dict, repo_shorthand=True)
            if ik is None:
                avail_i = sorted(bundles_dict.keys())
                raise SystemExit(
                    f"{prog}: unknown {kind_label} {fpath.name!r} in package {str(fpath)!r} "
                    f"(available {kind_label}s: {', '.join(avail_i)})"
                )
            bfile = _find_bundle_file_in_pkg(fpath, ik)
            bdir = bfile.parent if bfile is not None else fpath
            return f"{fpath}:{ik}", bundles_dict[ik][1], str(fpath), fpath, bdir
        if not fpath.is_file() and not fpath.suffix and fpath.with_suffix(".bundle").is_file():
            fpath = fpath.with_suffix(".bundle").resolve()
        if not fpath.is_file():
            raise SystemExit(f"{prog}: {kind_label} file not found: {item_name}")
        raw = fpath.read_text(encoding="utf-8", errors="replace")
        return str(fpath), _parse_md_text(raw, fpath.stem)[1], None, None, fpath.parent

    s_clean = target_spec.strip()
    is_shorthand = _is_repo_shorthand_spec(s_clean) and pkg_id == s_clean
    raw_item = s_clean.split(":", 1)[1].strip() if ":" in s_clean else item_name
    pkg_dir = _resolve_package_dir(pkg_id, work_dir=work_dir, refresh=refresh)
    _, bundles_dict = _load_package_from_dir(pkg_dir)
    ik = _match_bundle_in_dict(item_name, bundles_dict, repo_shorthand=is_shorthand)
    if ik is not None:
        bfile = _find_bundle_file_in_pkg(pkg_dir, ik)
        bdir = bfile.parent if bfile is not None else pkg_dir
        return f"{pkg_id}:{ik}", bundles_dict[ik][1], pkg_id, pkg_dir, bdir
    rel_match = _resolve_package_rel_file(pkg_dir, raw_item, (".bundle",))
    if rel_match is None:
        avail_i = sorted(bundles_dict.keys())
        raise SystemExit(
            f"{prog}: unknown {kind_label} {item_name!r} in package {pkg_id!r} "
            f"(available {kind_label}s: {', '.join(avail_i)})"
        )
    ik, bfile = rel_match
    raw = bfile.read_text(encoding="utf-8", errors="replace")
    return f"{pkg_id}:{ik}", _parse_md_text(raw, bfile.stem)[1], pkg_id, pkg_dir, bfile.parent


def resolve_bundle_source(
    target_spec: str,
    work_dir: Path | None = None,
    refresh: bool = False,
    default_pkg: str | None = DEFAULT_RULES_PKG,
) -> tuple[str, str]:
    canonical_id, body, _, _, _ = _resolve_bundle_context(
        target_spec,
        work_dir=work_dir,
        refresh=refresh,
        default_pkg=default_pkg,
    )
    return canonical_id, body


def resolve_bundle_text(
    target_spec: str,
    work_dir: Path | None = None,
    refresh: bool = False,
    default_pkg: str | None = DEFAULT_RULES_PKG,
) -> str:
    return resolve_bundle_source(
        target_spec,
        work_dir=work_dir,
        refresh=refresh,
        default_pkg=default_pkg,
    )[1]


def collect_directive_items(
    kind: str,
    target_spec: str,
    excludes: list[str] | None = None,
    cli_vars: dict[str, str] | None = None,
    work_dir: Path | None = None,
    refresh: bool = False,
    default_pkg: str | None = None,
    trace_prefix: list[str] | None = None,
    piped: bool = False,
    chain: list[str] | None = None,
    active_bundles: list[tuple[str, str]] | None = None,
    cond_expr: str | None = None,
    dynamic_vars: set[str] | None = None,
    rule_invariance: dict[str, bool] | None = None,
    upstream_rules: dict[str, str] | None = None,
    claimed_upstream_rules: set[str] | None = None,
) -> list[tuple[str, str, str, list[str]]]:
    """Returns list of (rule_uid, provenance_comment, rendered_body, chain)."""
    prog = prog_name()
    if kind not in ("bundle", "rule"):
        raise SystemExit(f"{prog}: directive kind must be 'bundle' or 'rule' (got {kind!r})")
    if excludes:
        raise SystemExit(f"{prog}: excludes are not supported: {excludes[0]!r}")

    effective_vars = {**builtin_vars(work_dir, piped=piped), **(cli_vars or {})}
    raw_target_spec = target_spec
    target_spec = _render_rule_vars(target_spec, effective_vars)
    base_chain = list(chain) if chain else []
    cur_trace = list(trace_prefix or [f"{kind} {target_spec}"])

    if kind == "bundle":
        canonical_id, body_text, child_pkg, _child_pkg_dir, child_bdir = _resolve_bundle_context(
            target_spec,
            work_dir=work_dir,
            refresh=refresh,
            default_pkg=default_pkg or DEFAULT_RULES_PKG,
            kind_label=kind,
        )
        pkg_id, item_name = _parse_target_spec(
            target_spec,
            default_pkg=default_pkg or DEFAULT_RULES_PKG,
            allow_repo_shorthand=True,
            work_dir=work_dir,
            refresh=refresh,
            kind="bundle",
        )
        bundle_spec = (
            target_spec
            if (pkg_id in ("__file__", "__url__") or (_is_repo_shorthand_spec(target_spec.strip()) and pkg_id == target_spec.strip()))
            else f"{pkg_id}:{item_name}"
        )
        next_bundles: list[tuple[str, str]] = list(active_bundles) if active_bundles else []
        if any(cid == canonical_id for cid, _ in next_bundles):
            cycle_path = " -> ".join([*(lbl for _, lbl in next_bundles), bundle_spec])
            raise SystemExit(f"{prog}: circular bundle reference detected: {cycle_path}")
        next_bundles = [*next_bundles, (canonical_id, bundle_spec)]
        bundle_chain = [*base_chain, bundle_spec]
        base_url = item_name.rsplit("/", 1)[0] if (pkg_id == "__url__" and "/" in item_name) else None
        sub_wdir = child_bdir if child_bdir is not None else work_dir
        local_vars = dict(effective_vars)
        items_out: list[tuple[str, str, str, list[str]]] = []

        def exec_nodes(nodes: list[tuple[str, object]], cond_stack: list[str]) -> None:
            for n_kind, payload in nodes:
                if n_kind == "if_chain":
                    prior_conds: list[str] = []
                    for b_cond, b_trace, b_body in payload:  # type: ignore[misc]
                        if b_cond is None or eval_if_condition(b_cond, local_vars, prog):
                            branch_conds = [*prior_conds, *([b_cond] if b_cond is not None else [])]
                            branch_comb = " ".join(branch_conds) or "else"
                            exec_nodes(b_body, [*cond_stack, branch_comb if b_cond is None else b_trace])
                            break
                        if b_cond is not None:
                            prior_conds.append(b_cond)
                    continue
                raw_line = str(payload)
                rendered_line = _render_rule_vars(raw_line, local_vars).strip()
                if not rendered_line:
                    continue
                if rendered_line == "let" or rendered_line.startswith("let "):
                    assign = rendered_line[len("let") :].strip()
                    if "=" not in assign:
                        raise SystemExit(f"{prog}: invalid let directive: {rendered_line!r}")
                    k, v_expr = assign.split("=", 1)
                    k_clean = k.strip()
                    if not VAR_NAME_RE.fullmatch(k_clean):
                        raise SystemExit(f"{prog}: invalid variable name {k_clean!r} in {rendered_line!r}")
                    if not local_vars.get(k_clean) and v_expr.strip():
                        local_vars[k_clean] = v_expr.strip()
                    continue
                if rendered_line == "export" or rendered_line.startswith(("export ", "file ", "cmd ", "prompt ")):
                    continue
                parts = shlex.split(rendered_line)
                if not parts or parts[0] not in ("bundle", "rule"):
                    raise SystemExit(
                        f"{prog}: invalid line in {kind} {target_spec!r}: {rendered_line!r}"
                    )
                sub_kind = parts[0]
                if sub_kind == "rule":
                    sub_targets, sub_vars = _parse_rule_directive_tokens(parts[1:], prog)
                else:
                    s_tgt, _ex, sub_vars = _parse_directive_tokens(parts[1:], prog)
                    sub_targets = [s_tgt]
                merged_vars = {**local_vars, **sub_vars, **(cli_vars or {})}
                cond_s = " ".join(c for c in cond_stack if c and c != "else")
                full_cond = " ".join(c for c in (cond_expr, cond_s) if c) or None
                for sub_target in sub_targets:
                    step_label = f"if {cond_s} {sub_kind} {sub_target}" if cond_s else f"{sub_kind} {sub_target}"
                    qual_target = (
                        f"{base_url}/{sub_target}"
                        if (base_url and ":" not in sub_target and sub_target.endswith((".md", ".bundle")))
                        else sub_target
                    )
                    items_out.extend(
                        collect_directive_items(
                            sub_kind,
                            qual_target,
                            cli_vars=merged_vars,
                            work_dir=sub_wdir,
                            refresh=refresh,
                            default_pkg=child_pkg or DEFAULT_RULES_PKG,
                            trace_prefix=[*cur_trace, step_label],
                            piped=piped,
                            chain=bundle_chain,
                            active_bundles=next_bundles,
                            cond_expr=full_cond,
                            dynamic_vars=dynamic_vars,
                            rule_invariance=rule_invariance,
                            upstream_rules=upstream_rules,
                            claimed_upstream_rules=claimed_upstream_rules,
                        )
                    )

        exec_nodes(parse_bundle_ast(body_text, prog), [])
        return items_out

    pkg_id, item_name = _parse_target_spec(
        target_spec,
        default_pkg=default_pkg,
        allow_repo_shorthand=True,
        work_dir=work_dir,
        refresh=refresh,
        kind="rule",
    )
    if pkg_id in ("__file__", "__url__"):
        if pkg_id == "__url__":
            fpath = _fetch_url_file(item_name, refresh=refresh)
        else:
            fpath = Path(item_name).expanduser()
            if work_dir is not None and not fpath.is_absolute():
                fpath = (work_dir / fpath).resolve()
            else:
                fpath = fpath.resolve()
            if not fpath.is_file() and not fpath.suffix and fpath.with_suffix(".md").is_file():
                fpath = fpath.with_suffix(".md").resolve()
            if not fpath.is_file():
                raise SystemExit(f"{prog}: rule file not found: {item_name}")
        raw = fpath.read_text(encoding="utf-8", errors="replace")
        _, body = _parse_md_text(raw, fpath.stem)
        rendered = _render_rule_vars(body, effective_vars).strip()
        if not rendered:
            return []
        rule_uid = str(fpath)
        if rule_invariance is not None and rule_uid not in rule_invariance:
            rule_invariance[rule_uid] = (
                _cond_is_invariant(cond_expr, dynamic_vars, prog)
                and _rule_template_is_invariant(raw_target_spec, dynamic_vars)
                and _rule_template_is_invariant(body, dynamic_vars)
            )
        used_keys = {m.group(1) for m in RULE_VAR_RE.finditer(body)}
        active_vars = {k: v for k, v in effective_vars.items() if k in used_keys}
        vars_s = f" ({', '.join(f'{k}={v}' for k, v in active_vars.items())})" if active_vars else ""
        prov = f"# [{' -> '.join(cur_trace)}]{vars_s}"
        return [(rule_uid, prov, rendered, list(base_chain))]

    s_clean = target_spec.strip()
    is_shorthand = _is_repo_shorthand_spec(s_clean) and pkg_id == s_clean
    raw_item = s_clean.split(":", 1)[1].strip() if ":" in s_clean else item_name
    pkg_dir = _resolve_package_dir(pkg_id, work_dir=work_dir, refresh=refresh)
    rules_dict, _ = _load_package_from_dir(pkg_dir)

    rk = _match_rule_in_dict(item_name, rules_dict, repo_shorthand=is_shorthand)
    if rk is not None:
        raw_body = rules_dict[rk][1].strip()
    else:
        rel_match = None if is_shorthand else _resolve_package_rel_file(pkg_dir, raw_item, (".md",))
        if rel_match is None:
            avail_r = sorted(rules_dict.keys())
            raise SystemExit(
                f"{prog}: unknown rule {item_name!r} in package {pkg_id!r} (available rules: {', '.join(avail_r)})"
            )
        rk, fpath = rel_match
        raw_body = _parse_md_text(fpath.read_text(encoding="utf-8", errors="replace"), rk)[1].strip()

    repo_base = _split_pkg_ref(pkg_id, prog)[0]
    canonical_uid = f"{pkg_id}:{rk}"
    unpinned_uid = f"{repo_base}:{rk}"
    up_raw: str | None = None
    if upstream_rules is not None:
        if canonical_uid in upstream_rules:
            up_raw = upstream_rules[canonical_uid]
            if claimed_upstream_rules is not None:
                claimed_upstream_rules.add(canonical_uid)
        elif unpinned_uid in upstream_rules:
            up_raw = upstream_rules[unpinned_uid]
            if claimed_upstream_rules is not None:
                claimed_upstream_rules.add(unpinned_uid)
    body_for_render = _parse_md_text(up_raw, canonical_uid)[1].strip() if up_raw is not None else raw_body
    rendered = _render_rule_vars(body_for_render, effective_vars).strip()
    if not rendered:
        return []
    if rule_invariance is not None and canonical_uid not in rule_invariance:
        rule_invariance[canonical_uid] = (
            _cond_is_invariant(cond_expr, dynamic_vars, prog)
            and _rule_template_is_invariant(raw_target_spec, dynamic_vars)
            and _rule_template_is_invariant(body_for_render, dynamic_vars)
        )
    used_keys = {m.group(1) for m in RULE_VAR_RE.finditer(body_for_render)}
    active_vars = {k: v for k, v in effective_vars.items() if k in used_keys}
    trace_chain = (
        [*cur_trace, f"agents/{rk}.md"]
        if (len(cur_trace) > 1 and cur_trace[-1].startswith("if "))
        else [*(cur_trace[:-1] if len(cur_trace) > 1 else cur_trace), f"agents/{rk}.md"]
    )
    vars_s = f" ({', '.join(f'{k}={v}' for k, v in active_vars.items())})" if active_vars else ""
    prov = f"# [{' -> '.join(trace_chain)}]{vars_s}"
    return [(canonical_uid, prov, rendered, list(base_chain))]


def format_bundle_part_marker(nonce: str, meta: dict[str, object]) -> str:
    payload = json.dumps(meta, ensure_ascii=False).replace("-->", "--\\u003e")
    return f"<!-- bundle:{nonce}:part {payload} -->"


def format_bundle_end_marker(nonce: str) -> str:
    return f"<!-- bundle:{nonce}:end -->"


def wrap_bundle_fragment(nonce: str | None, meta: dict[str, object], content: str) -> str:
    if not nonce:
        return content
    part_line = format_bundle_part_marker(nonce, meta)
    end_line = format_bundle_end_marker(nonce)
    if content:
        return f"{part_line}\n{content}\n{end_line}"
    return f"{part_line}\n{end_line}"


def format_collected_rules(
    items: list[tuple[str, str, str, list[str]]],
    verbose: bool = False,
    boundary: str | None = None,
) -> str:
    seen: set[str] = set()
    chunks: list[str] = []
    for item in items:
        uid, prov, body = item[0], item[1], item[2]
        if uid in seen:
            continue
        seen.add(uid)
        chain = list(item[3]) if len(item) > 3 else []
        chunk = f"{prov}\n{body}" if verbose else body
        if boundary:
            chunk = wrap_bundle_fragment(
                boundary,
                {
                    "kind": "rule",
                    "id": uid,
                    "chain": chain,
                },
                chunk,
            )
        chunks.append(chunk)
    sep = "\n\n" if verbose else "\n"
    return sep.join(chunks)


def render_directive(
    kind: str,
    target_spec: str,
    excludes: list[str] | None = None,
    cli_vars: dict[str, str] | None = None,
    work_dir: Path | None = None,
    refresh: bool = False,
    default_pkg: str | None = None,
    verbose: bool = False,
) -> str:
    items = collect_directive_items(
        kind,
        target_spec,
        excludes=excludes,
        cli_vars=cli_vars,
        work_dir=work_dir,
        refresh=refresh,
        default_pkg=default_pkg,
    )
    return format_collected_rules(items, verbose=verbose)


def cmd_list_rules(pkg_id: str = DEFAULT_RULES_PKG) -> int:
    rules_dict, bundles_dict = _get_package_catalog(pkg_id)
    bvars = builtin_vars()
    sys.stdout.write("Built-in variables (usable in 'if key=val' conditions and rule templates):\n")
    sys.stdout.write(f"  {'os':<38}  Active operating system (linux, macos; current: {bvars['os']!r})\n")
    sys.stdout.write(f"  {'vcs':<38}  Detected repository VCS (git, cvs, or ''; current: {bvars['vcs']!r})\n")
    sys.stdout.write(f"  {'piped':<38}  Set to '1' when stdin prompt text is present, else '' (current: {bvars['piped']!r})\n\n")
    if bundles_dict:
        sys.stdout.write(f"Bundles in '{pkg_id}' (use as 'bundle {pkg_id}:<bundle>'):\n")
        for k, (desc, body) in bundles_dict.items():
            target_tag = f"{pkg_id}:{k}"
            sys.stdout.write(f"  {target_tag:<38}  {desc}\n")
            for cond_expr, line in strip_if_blocks_and_lines(body):
                cond_s = f"if {cond_expr} " if cond_expr else ""
                sys.stdout.write(f"  {'':<38}    {cond_s}{line}\n")
    sys.stdout.write(f"\nAtomic rules in '{pkg_id}' (use as 'rule {pkg_id}:<rule>'):\n")
    for k, (desc, _) in rules_dict.items():
        target_tag = f"{pkg_id}:{k}"
        sys.stdout.write(f"  {target_tag:<38}  {desc}\n")
    return 0


def _git_run(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def _git_head(repo_root: Path) -> str:
    return _git_run(repo_root, "rev-parse", "--short", "HEAD").stdout.strip()


def _refresh_cached_repo(repo_root: Path) -> tuple[str, str]:
    before = _git_head(repo_root)
    for args in (("fetch", "--depth", "1", "--force", "origin"), ("reset", "--hard", "FETCH_HEAD")):
        r = _git_run(repo_root, *args)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or f"git {args[0]} failed")
    return before, _git_head(repo_root)


def cmd_update_cache() -> int:
    prog = prog_name()
    root = cache_dir_path()
    pdir = root / "packages"
    udir = root / "urls"
    counts = {"updated": 0, "unchanged": 0, "skipped": 0, "failed": 0}
    if pdir.is_dir():
        for git_dir in sorted(pdir.rglob(".git")):
            repo_root = git_dir.parent
            label = f"package {repo_root.relative_to(pdir).as_posix()}"
            try:
                before, after = _refresh_cached_repo(repo_root)
            except RuntimeError as exc:
                counts["failed"] += 1
                sys.stderr.write(f"{prog}: {label}: failed: {exc}\n")
                continue
            if before == after:
                counts["unchanged"] += 1
                sys.stdout.write(f"{label}: up to date ({after})\n")
            else:
                counts["updated"] += 1
                sys.stdout.write(f"{label}: updated {before} -> {after}\n")
    if udir.is_dir():
        cached = sorted(p for p in udir.iterdir() if p.is_file() and not p.name.endswith(URL_ORIGIN_SUFFIX))
        for cpath in cached:
            origin = cpath.with_name(cpath.name + URL_ORIGIN_SUFFIX)
            if not origin.is_file():
                counts["skipped"] += 1
                sys.stdout.write(f"url {cpath.name}: skipped (source URL not recorded; re-fetch with --refresh)\n")
                continue
            url = origin.read_text(encoding="utf-8").strip()
            label = f"url {url}"
            try:
                data = _download_url_text(url)
            except Exception as exc:
                counts["failed"] += 1
                sys.stderr.write(f"{prog}: {label}: failed: {exc}\n")
                continue
            if cpath.read_text(encoding="utf-8", errors="replace") == data:
                counts["unchanged"] += 1
                sys.stdout.write(f"{label}: unchanged\n")
            else:
                cpath.write_text(data, encoding="utf-8")
                counts["updated"] += 1
                sys.stdout.write(f"{label}: updated\n")
    if sum(counts.values()) == 0:
        sys.stdout.write(f"No cached packages or URL files in {root}\n")
        return 0
    sys.stdout.write(
        "Refreshed cache: "
        f"{counts['updated']} updated, {counts['unchanged']} unchanged, "
        f"{counts['skipped']} skipped, {counts['failed']} failed.\n"
    )
    return 1 if counts["failed"] else 0
