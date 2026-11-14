def default_spec_template(prog: str | None = None) -> str:
    cmd = prog or prog_name()
    lines = [
        f"# {SPEC_FILE_NAME} — root context preset and command bundle for '{cmd}'",
        "# Directives:",
        f"#   preset <owner>/<repo>:<name> [-exclude ...] [key=val ...]",
        f"#   rule <owner>/<repo>:<name> [key=val ...]",
        f"#   include <owner>/<repo>:<name> [key=val ...]",
        "#   prompt <text>",
        "#   [if os=linux] rule <owner>/<repo>:os/linux  (or multi-line [if ...] ... [/if])",
        "#   $ <shell command>  (use '$ cat <file>' to include a file)",
        "",
        f"preset {DEFAULT_RULES_PKG}:default",
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


def find_spec_file(start_dir: Path | None = None) -> Path | None:
    cur = (start_dir if start_dir is not None else Path.cwd()).resolve()
    candidate = cur / SPEC_FILE_NAME
    if candidate.is_file():
        return candidate
    return None


def parse_spec(
    text: str,
    work_dir: Path | None = None,
    cli_vars: dict[str, str] | None = None,
    refresh: bool = False,
) -> list[tuple[str, str, str | None]]:
    prog = prog_name()
    bvars = {**builtin_vars(work_dir), **(cli_vars or {})}
    entries: list[tuple[str, str, str | None]] = []
    for cond_expr, raw_line in strip_if_blocks_and_lines(text, prog):
        if cond_expr and not eval_if_condition(cond_expr, bvars, prog):
            continue
        line = _render_rule_vars(raw_line, bvars).strip()
        if line.startswith("$ ") or line.startswith("! "):
            cmd_str = line[2:].strip()
            if cmd_str:
                entries.append(("cmd", cmd_str, cond_expr))
        elif line in ("$", "!"):
            continue
        elif line.startswith("preset ") or line.startswith("rule "):
            entries.append(("directive", line, cond_expr))
        elif line.startswith("include "):
            parts = shlex.split(line)
            target, excls, vmap = _parse_directive_tokens(parts[1:], prog)
            if excls:
                raise SystemExit(f"{prog}: include directive does not support excludes: {line!r}")
            inc_text = resolve_include_text(target, work_dir=work_dir, refresh=refresh)
            merged_cli = {**(cli_vars or {}), **vmap}
            for sub_kind, sub_val, sub_cond in parse_spec(
                inc_text, work_dir=work_dir, cli_vars=merged_cli, refresh=refresh
            ):
                comb_cond = " ".join(c for c in (cond_expr, sub_cond) if c) or None
                entries.append((sub_kind, sub_val, comb_cond))
        elif line.startswith("prompt "):
            p_str = line[len("prompt ") :].strip()
            if p_str:
                entries.append(("prompt", p_str, cond_expr))
        elif line == "prompt":
            continue
        else:
            raise SystemExit(
                f"{prog}: invalid line in {SPEC_FILE_NAME}: {line!r} (expected 'preset ...', 'rule ...', 'include ...', 'prompt ...', '[if ...]', or '$ <command>')"
            )
    return entries


def _run_spec_command(cmd_str: str, cwd: Path) -> tuple[int, str]:
    prog = prog_name()
    self_dir = str(Path(__file__).resolve().parent)
    if re.match(rf"^(?:{re.escape(prog)}|agents_bundle)\s+--tree(?:\s+.*)?$", cmd_str):
        try:
            parts = shlex.split(cmd_str)[2:]
            return 0, _tree_from_args(parts, default_dir=cwd).rstrip()
        except SystemExit as exc:
            return 1, str(exc)

    shell_bin = os.environ.get("AGENTS_BUNDLE_SHELL", "bash").strip() or "bash"
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
        return r.returncode, r.stdout.decode("utf-8", errors="replace").rstrip()
    except OSError as exc:
        return 1, f"[error running {cmd_str!r}: {exc}]"


def build_bundle(
    work_dir: Path | None = None,
    extra_files: list[str] | None = None,
    prompt_text: str | None = None,
    refresh: bool = False,
    verbose: bool = False,
    cli_vars: dict[str, str] | None = None,
) -> tuple[str, list[str]]:
    prog = prog_name()
    wdir = (work_dir if work_dir is not None else Path.cwd()).resolve()
    spec_file = find_spec_file(wdir)
    if spec_file is None:
        sys.stderr.write(f"{prog}: {SPEC_FILE_NAME} not found in {wdir} (run '{prog} --init' to create a starter template)\n")
        raise SystemExit(2)

    spec_dir = spec_file.parent
    entries = parse_spec(
        spec_file.read_text(encoding="utf-8"),
        work_dir=spec_dir,
        cli_vars=cli_vars,
        refresh=refresh,
    )
    sections: list[tuple[str, str]] = []
    warnings: list[str] = []
    pending_rules: list[tuple[str, str, str]] = []
    spec_prompts: list[str] = []

    def flush_pending_rules() -> None:
        if not pending_rules:
            return
        formatted = format_collected_rules(pending_rules, verbose=verbose).strip()
        pending_rules.clear()
        if formatted:
            sections.append(("Rules", formatted))

    for kind, val, cond_expr in entries:
        if kind == "directive":
            parts = shlex.split(val)
            d_kind = parts[0]
            target, excls, vmap = _parse_directive_tokens(parts[1:], prog)
            trace_start = f"[if {cond_expr}] {d_kind} {target}" if cond_expr else f"{d_kind} {target}"
            merged_vmap = {**vmap, **(cli_vars or {})}
            pending_rules.extend(
                collect_directive_items(
                    d_kind,
                    target,
                    excludes=excls,
                    cli_vars=merged_vmap,
                    work_dir=spec_dir,
                    refresh=refresh,
                    trace_prefix=[trace_start],
                )
            )
        elif kind == "cmd":
            flush_pending_rules()
            rc, out = _run_spec_command(val, spec_dir)
            if rc != 0:
                warnings.append(f"command exited {rc}: {val}")
            sections.append((f"$ {val}", out))
        elif kind == "prompt":
            spec_prompts.append(val)
    flush_pending_rules()

    for extra in extra_files or []:
        clean = extra.strip()
        if not clean:
            continue
        p = (wdir / clean).resolve() if not Path(clean).is_absolute() else Path(clean).resolve()
        if not p.is_file():
            warnings.append(f"missing file: {clean}")
            continue
        try:
            disp = str(p.relative_to(spec_dir))
        except ValueError:
            disp = str(p)
        content = p.read_text(encoding="utf-8", errors="replace").rstrip()
        sections.append((f"$ cat {disp}", content))

    all_prompts = [*spec_prompts]
    if prompt_text and prompt_text.strip():
        all_prompts.append(prompt_text.strip())
    if all_prompts:
        sections.append(("Prompt", "\n\n".join(all_prompts)))

    header = f'Bundle-Command: {prog} [key=val ...] [-p "<prompt>"] [file ...]\n'
    blocks = [header, *(f"===== {title} =====\n{content}\n" for title, content in sections)]
    return "\n".join(blocks), warnings


def cmd_bundle(argv: list[str]) -> int:
    prog = prog_name()
    work_dir: Path | None = None
    prompt_parts: list[str] = []
    extra_files: list[str] = []
    cli_vars: dict[str, str] = {}
    refresh = False
    verbose = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--refresh":
            refresh = True
            i += 1
        elif a in ("-v", "--verbose"):
            verbose = True
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

    prompt_text = "\n\n".join(prompt_parts) if prompt_parts else None
    body, warnings = build_bundle(
        work_dir=work_dir,
        extra_files=extra_files,
        prompt_text=prompt_text,
        refresh=refresh,
        verbose=verbose,
        cli_vars=cli_vars,
    )
    for w in warnings:
        sys.stderr.write(f"{prog}: warning: {w}\n")
    sys.stdout.write(body)
    return 0
