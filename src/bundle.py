def default_spec_template(prog: str | None = None) -> str:
    cmd = prog or prog_name()
    lines = [
        f"# {SPEC_FILE_NAME} — root context ruleset and command bundle for '{cmd}'",
        "# Directives:",
        f"#   ruleset <owner>/<repo>:<name> [-exclude ...] [key=val ...]",
        f"#   rule <owner>/<repo>:<name> [key=val ...]",
        f"#   bundle <owner>/<repo>[:<name>] [key=val ...]",
        "#   var <name>=$(<shell command>)  (or var <name>=<value>; sets variable if not already passed)",
        "#   expose <key...>  (add header names to Bundle-Expose alongside Role, Task)",
        "#   include $(<shell command>)  (includes existing repository files listed by command or path)",
        "#   prompt <text>",
        "#   [if os=linux] rule <owner>/<repo>:os/linux  (or multi-line [if ...] ... [/if])",
        "#   $ <shell command>  (use '$ cat <file>' to include a file)",
        "",
        "bundle vitalio/run_block",
        "bundle vitalio/agents_bundle",
        "bundle vitalio/todo_md",
        "",
        f"ruleset {DEFAULT_RULES_PKG}:default",
        "",
        "$ cat AGENTS.md",
        f"$ {cmd} --tree",
        "$ git status -sb",
        "$ git branch -vv",
        "$ git log --oneline -10",
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
    parts = [part.capitalize() for part in re.split(r"[-_]+", raw_key.strip()) if part]
    return "-".join(parts)


def _parse_expose_keys(raw_args: str, source_label: str, prog: str) -> list[str]:
    tokens = [tok for tok in re.split(r"[\s,]+", raw_args.strip()) if tok]
    keys: list[str] = []
    for tok in tokens:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", tok):
            raise SystemExit(f"{prog}: invalid header name {tok!r} in {source_label}")
        hdr = _normalize_header_name(tok)
        if hdr and hdr not in keys:
            keys.append(hdr)
    return keys


def env_expose(prog: str | None = None) -> list[str]:
    raw = os.environ.get("AGENTS_BUNDLE_EXPOSE", "").strip()
    if not raw:
        return []
    p = prog or prog_name()
    return _parse_expose_keys(raw, "AGENTS_BUNDLE_EXPOSE", p)


def env_plain() -> bool:
    raw = os.environ.get("AGENTS_BUNDLE_PLAIN", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def find_spec_file(start_dir: Path | None = None) -> Path | None:
    cur = (start_dir if start_dir is not None else Path.cwd()).resolve()
    candidate = cur / SPEC_FILE_NAME
    if candidate.is_file():
        return candidate
    return None


def _eval_dynamic_expr(expr: str, work_dir: Path | None = None) -> str:
    s = expr.strip()
    if s.startswith("$(") and s.endswith(")") and len(s) >= 3:
        cmd = s[2:-1].strip()
        if not cmd:
            return ""
        cwd = (work_dir if work_dir is not None else Path.cwd()).resolve()
        rc, out, _ = _run_spec_command(cmd, cwd)
        if rc != 0:
            return ""
        return out.strip()
    return s


def _parse_stdin_pipe(stdin_text: str) -> tuple[dict[str, str], str, str | None]:
    raw = stdin_text.strip()
    if not raw:
        return {}, "", None
    inferred_vars: dict[str, str] = {}
    piped_workdir: str | None = None
    lines = raw.splitlines()

    preamble: dict[str, str] = {}
    idx = 0
    while idx < len(lines):
        ln = lines[idx]
        if not ln.strip():
            break
        hm = re.fullmatch(r"([A-Za-z][A-Za-z0-9_-]*):(?:[ \t]+(.*)|[ \t]*)", ln)
        if not hm:
            break
        preamble[hm.group(1)] = hm.group(2).strip() if hm.group(2) is not None else ""
        idx += 1

    if preamble and (idx == len(lines) or not lines[idx].strip()):
        for k, v in preamble.items():
            kl = k.lower()
            if kl == "workdir":
                piped_workdir = v
            elif kl.startswith("bundle-"):
                continue
            elif v:
                var_name = kl.replace("-", "_")
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", var_name):
                    inferred_vars[var_name] = v
        raw = "\n".join(lines[idx:]).strip()
        if not raw:
            return inferred_vars, "", piped_workdir
        lines = raw.splitlines()

    if len(lines) == 1 and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", lines[0].strip()):
        inferred_vars.setdefault("task", lines[0].strip())
        return inferred_vars, "", piped_workdir
    return inferred_vars, raw, piped_workdir


def parse_spec(
    text: str,
    work_dir: Path | None = None,
    cli_vars: dict[str, str] | None = None,
    refresh: bool = False,
    resolved_vars: dict[str, str] | None = None,
    piped: bool = False,
    via: str = SPEC_FILE_NAME,
) -> list[tuple[str, str, str | None, str]]:
    prog = prog_name()
    active_vars: dict[str, str] = dict(cli_vars) if cli_vars is not None else {}
    bvars = {**builtin_vars(work_dir, piped=piped), **active_vars}
    entries: list[tuple[str, str, str | None, str]] = []
    for cond_expr, raw_line in strip_if_blocks_and_lines(text, prog):
        if cond_expr and not eval_if_condition(cond_expr, bvars, prog):
            continue
        line = _render_rule_vars(raw_line, bvars).strip()
        if line.startswith("var "):
            assign = line[len("var ") :].strip()
            if "=" not in assign:
                raise SystemExit(f"{prog}: invalid var directive in {SPEC_FILE_NAME}: {line!r} (expected 'var key=val')")
            k, v_expr = assign.split("=", 1)
            k_clean = k.strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k_clean):
                raise SystemExit(f"{prog}: invalid variable name {k_clean!r} in {line!r}")
            if not active_vars.get(k_clean):
                val = _eval_dynamic_expr(v_expr, work_dir=work_dir)
                if val:
                    active_vars[k_clean] = val
                    bvars[k_clean] = val
                    if resolved_vars is not None:
                        resolved_vars[k_clean] = val
        elif line.startswith("include "):
            inc_expr = line[len("include ") :].strip()
            if inc_expr:
                resolved_inc = _eval_dynamic_expr(inc_expr, work_dir=work_dir)
                for item in resolved_inc.splitlines():
                    clean_item = item.strip()
                    if clean_item:
                        entries.append(("include", clean_item, cond_expr, via))
        elif line == "include":
            continue
        elif line.startswith("$ ") or line.startswith("! "):
            cmd_str = line[2:].strip()
            if cmd_str:
                entries.append(("cmd", cmd_str, cond_expr, via))
        elif line in ("$", "!"):
            continue
        elif line.startswith("ruleset ") or line.startswith("rule "):
            entries.append(("directive", line, cond_expr, via))
        elif line.startswith("bundle "):
            parts = shlex.split(line)
            target, excls, vmap = _parse_directive_tokens(parts[1:], prog)
            if excls:
                raise SystemExit(f"{prog}: bundle directive does not support excludes: {line!r}")
            inc_text = resolve_bundle_text(target, work_dir=work_dir, refresh=refresh)
            merged_cli = {**active_vars, **vmap}
            sub_resolved: dict[str, str] = {}
            child_via = target if via == SPEC_FILE_NAME else via
            for sub_kind, sub_val, sub_cond, sub_via in parse_spec(
                inc_text,
                work_dir=work_dir,
                cli_vars=merged_cli,
                refresh=refresh,
                resolved_vars=sub_resolved,
                piped=piped,
                via=child_via,
            ):
                comb_cond = " ".join(c for c in (cond_expr, sub_cond) if c) or None
                entries.append((sub_kind, sub_val, comb_cond, sub_via))
            for rk, rv in sub_resolved.items():
                if not active_vars.get(rk):
                    active_vars[rk] = rv
                    bvars[rk] = rv
                    if resolved_vars is not None:
                        resolved_vars[rk] = rv
        elif line.startswith("expose "):
            exp_raw = line[len("expose ") :].strip()
            for hdr in _parse_expose_keys(exp_raw, SPEC_FILE_NAME, prog):
                entries.append(("expose", hdr, cond_expr, via))
        elif line == "expose":
            continue
        elif line.startswith("prompt "):
            p_str = line[len("prompt ") :].strip()
            if p_str:
                entries.append(("prompt", p_str, cond_expr, via))
        elif line == "prompt":
            continue
        else:
            raise SystemExit(
                f"{prog}: invalid line in {SPEC_FILE_NAME}: {line!r} (expected 'ruleset ...', 'rule ...', 'bundle ...', 'var ...', 'expose ...', 'include ...', 'prompt ...', '[if ...]', or '$ <command>')"
            )
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

    env_shell = os.environ.get("AGENTS_BUNDLE_SHELL", "").strip()
    if env_shell:
        shell_bin = env_shell
    elif os.name == "nt":
        shell_bin = "pwsh" if shutil.which("pwsh") else "powershell"
    else:
        shell_bin = "bash"
    shell_flag = "-Command" if Path(shell_bin).stem.lower() in ("pwsh", "powershell") else "-c"
    env = {**os.environ, "PYTHONUTF8": "1"}
    env["PATH"] = f"{self_dir}{os.pathsep}{Path.home() / '.local/bin'}{os.pathsep}{env.get('PATH', '')}"
    try:
        r = subprocess.run(
            [shell_bin, shell_flag, cmd_str],
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
    spec_file = find_spec_file(wdir)
    if spec_file is None:
        sys.stderr.write(f"{prog}: {SPEC_FILE_NAME} not found in {wdir} (run '{prog} --init' to create a starter template)\n")
        raise SystemExit(2)

    spec_dir = spec_file.parent
    effective_cli_vars: dict[str, str] = dict(cli_vars or {})
    resolved_vars: dict[str, str] = {}
    entries = parse_spec(
        spec_file.read_text(encoding="utf-8"),
        work_dir=spec_dir,
        cli_vars=effective_cli_vars,
        refresh=refresh,
        resolved_vars=resolved_vars,
        piped=piped,
        via=SPEC_FILE_NAME,
    )
    effective_cli_vars.update(resolved_vars)
    boundary = secrets.token_hex(16)
    fragment_boundary = None if plain else boundary
    section_blocks: list[str] = []
    warnings: list[str] = []
    pending_rules: list[tuple[str, str, str, str, str]] = []
    pending_cmds: list[tuple[str, str]] = []
    spec_prompts: list[tuple[str, str]] = []
    spec_expose: list[str] = []
    included_files: list[tuple[str, bool, str]] = []

    for kind, val, cond_expr, entry_via in entries:
        if kind == "directive":
            parts = shlex.split(val)
            d_kind = parts[0]
            target, excls, vmap = _parse_directive_tokens(parts[1:], prog)
            base_trace = f"[if {cond_expr}] {d_kind} {target}" if cond_expr else f"{d_kind} {target}"
            trace_start = f"bundle {entry_via} -> {base_trace}" if entry_via != SPEC_FILE_NAME else base_trace
            merged_vmap = {**vmap, **effective_cli_vars}
            pending_rules.extend(
                collect_directive_items(
                    d_kind,
                    target,
                    excludes=excls,
                    cli_vars=merged_vmap,
                    work_dir=spec_dir,
                    refresh=refresh,
                    trace_prefix=[trace_start],
                    piped=piped,
                    group=(None if d_kind == "ruleset" else entry_via),
                    via=entry_via,
                )
            )
        elif kind == "cmd":
            pending_cmds.append((val, entry_via))
        elif kind == "expose":
            if val not in spec_expose:
                spec_expose.append(val)
        elif kind == "include":
            included_files.append((val, False, entry_via))
        elif kind == "prompt":
            spec_prompts.append((val, entry_via))

    if pending_rules:
        formatted = format_collected_rules(pending_rules, verbose=verbose, boundary=fragment_boundary).strip()
        if formatted:
            section_blocks.append(f"===== Rules =====\n{formatted}\n")
            if records is not None:
                seen_rule_uids: set[str] = set()
                for r_uid, _r_prov, _r_body, r_group, r_via in pending_rules:
                    if r_uid in seen_rule_uids:
                        continue
                    seen_rule_uids.add(r_uid)
                    records.append(
                        {
                            "kind": "rule",
                            "id": r_uid,
                            "group": r_group,
                            "via": r_via,
                        }
                    )

    for cmd_val, cmd_via in pending_cmds:
        rc, out, elapsed_ms = _run_spec_command(cmd_val, spec_dir)
        if rc != 0:
            warnings.append(f"command exited {rc}: {cmd_val}")
        cmd_meta: dict[str, object] = {
            "kind": "cmd",
            "name": cmd_val,
            "group": cmd_via,
            "via": cmd_via,
            "rc": rc,
            "ms": elapsed_ms,
        }
        wrapped_cmd = wrap_bundle_fragment(fragment_boundary, cmd_meta, f"===== $ {cmd_val} =====\n{out}")
        section_blocks.append(f"{wrapped_cmd}\n")
        if records is not None:
            records.append(cmd_meta)

    for extra in extra_files or []:
        included_files.append((extra, True, "cli"))

    seen_files: set[Path] = set()
    for raw_file, warn_missing, inc_via in included_files:
        clean = raw_file.strip()
        if not clean:
            continue
        p = (wdir / clean).resolve() if not Path(clean).is_absolute() else Path(clean).resolve()
        if not p.is_file():
            if warn_missing:
                warnings.append(f"missing file: {clean}")
            continue
        if p in seen_files:
            continue
        seen_files.add(p)
        try:
            disp = p.relative_to(spec_dir).as_posix()
        except ValueError:
            disp = p.as_posix()
        content = p.read_text(encoding="utf-8", errors="replace").rstrip()
        inc_meta: dict[str, object] = {
            "kind": "include",
            "name": disp,
            "group": inc_via,
            "via": inc_via,
        }
        wrapped_inc = wrap_bundle_fragment(fragment_boundary, inc_meta, f"===== $ cat {disp} =====\n{content}")
        section_blocks.append(f"{wrapped_inc}\n")
        if records is not None:
            records.append(inc_meta)

    all_prompt_items = [*spec_prompts]
    if prompt_text and prompt_text.strip():
        all_prompt_items.append((prompt_text.strip(), "cli"))
    if all_prompt_items:
        prompt_vias: list[str] = []
        for _p_text, p_via in all_prompt_items:
            if p_via not in prompt_vias:
                prompt_vias.append(p_via)
        prompt_via = prompt_vias[0] if len(prompt_vias) == 1 else ", ".join(prompt_vias)
        prompt_meta: dict[str, object] = {
            "kind": "prompt",
            "group": prompt_via,
            "via": prompt_via,
        }
        joined_prompt = "\n\n".join(text for text, _ in all_prompt_items)
        wrapped_prompt = wrap_bundle_fragment(fragment_boundary, prompt_meta, f"===== Prompt =====\n{joined_prompt}")
        section_blocks.append(f"{wrapped_prompt}\n")
        if records is not None:
            for _p_text, p_via in all_prompt_items:
                records.append(
                    {
                        "kind": "prompt",
                        "group": p_via,
                        "via": p_via,
                    }
                )

    header_lines: list[str] = []
    if not plain:
        exposed_headers = ["Role", "Task"]
        for hdr in [*spec_expose, *env_expose(prog)]:
            if hdr not in exposed_headers:
                exposed_headers.append(hdr)
        cmd_line = shlex.join([prog, *raw_argv]) if raw_argv else prog
        header_lines.extend(
            [
                f"Bundle-Command: {cmd_line}",
                f"Bundle-Boundary: {boundary}",
                f"Bundle-Expose: {', '.join(exposed_headers)}",
            ]
        )
    for k, v in effective_cli_vars.items():
        if v != "" and k != "workdir":
            hdr_key = _normalize_header_name(k)
            header_lines.append(f"{hdr_key}: {v}")
    header_lines.append(f"Workdir: {wdir}")
    header = "\n".join(header_lines) + "\n"
    blocks = [header, *section_blocks]
    return "\n".join(blocks), warnings


def cmd_bundle(argv: list[str]) -> int:
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
        elif "=" in a and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", a, flags=re.DOTALL) and not Path(a).exists():
            k, v = a.split("=", 1)
            cli_vars[k.strip()] = v.strip()
            i += 1
        else:
            extra_files.append(a)
            i += 1

    piped_workdir: str | None = None
    has_piped_prompt = False
    if not sys.stdin.isatty():
        try:
            piped_raw = sys.stdin.read()
        except Exception:
            piped_raw = ""
        if piped_raw.strip():
            inferred_vars, piped_prompt, piped_workdir = _parse_stdin_pipe(piped_raw)
            for ik, iv in inferred_vars.items():
                if not cli_vars.get(ik):
                    cli_vars[ik] = iv
            if piped_prompt:
                has_piped_prompt = True
                prompt_parts.insert(0, piped_prompt)

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
        raw_argv=argv,
        piped=has_piped_prompt,
        plain=plain,
    )
    for w in warnings:
        sys.stderr.write(f"{prog}: warning: {w}\n")
    sys.stdout.write(body)
    return 0
