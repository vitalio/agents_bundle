RULE_VAR_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*):([^{}]*)\}")
IF_PREFIX_RE = re.compile(r"^\[if\s+([^\]]+)\]\s*(.*)$")


def _render_rule_vars(text: str, vars_map: dict[str, str]) -> str:
    return RULE_VAR_RE.sub(lambda m: vars_map.get(m.group(1), m.group(2)), text)


def _detect_os_name() -> str:
    if os.name == "nt":
        return "windows"
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


def builtin_vars(work_dir: Path | None = None) -> dict[str, str]:
    return {
        "os": _detect_os_name(),
        "vcs": _detect_vcs_name(work_dir),
    }


def eval_if_condition(cond_expr: str, vars_map: dict[str, str], prog: str | None = None) -> bool:
    p = prog or prog_name()
    tokens = shlex.split(cond_expr.strip())
    if not tokens:
        raise SystemExit(f"{p}: empty [if ...] condition")
    for tok in tokens:
        if "!=" in tok:
            k, expected = tok.split("!=", 1)
            k = k.strip()
            allowed = {v.strip() for v in expected.split(",")}
            actual = vars_map.get(k, "")
            if actual in allowed:
                return False
        elif "=" in tok:
            k, expected = tok.split("=", 1)
            k = k.strip()
            allowed = {v.strip() for v in expected.split(",")}
            actual = vars_map.get(k, "")
            if actual not in allowed:
                return False
        else:
            raise SystemExit(f"{p}: invalid condition token {tok!r} in '[if {cond_expr}]' (expected key=val or key!=val)")
    return True


def strip_if_blocks_and_lines(raw_text: str, prog: str | None = None) -> list[tuple[str | None, str]]:
    """Parses raw lines supporting '[if cond] <line>' and '[if cond] ... [/if]' blocks.
    Returns list of (cond_expr_or_None, inner_line).
    """
    p = prog or prog_name()
    out: list[tuple[str | None, str]] = []
    block_stack: list[str] = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower() in ("[/if]", "[endif]"):
            if not block_stack:
                raise SystemExit(f"{p}: unexpected {line!r} without matching '[if ...]'")
            block_stack.pop()
            continue
        m = IF_PREFIX_RE.match(line)
        if m:
            cond_s = m.group(1).strip()
            rest = m.group(2).strip()
            if not rest:
                block_stack.append(cond_s)
                continue
            combined = " ".join([*block_stack, cond_s])
            out.append((combined, rest))
            continue
        combined = " ".join(block_stack) if block_stack else None
        out.append((combined, line))
    if block_stack:
        raise SystemExit(f"{p}: unclosed '[if {block_stack[-1]}]' block (missing '[/if]')")
    return out


def _parse_md_text(raw_text: str, fallback_desc: str) -> tuple[str, str]:
    lines = raw_text.splitlines()
    desc = fallback_desc
    body_lines = lines
    if lines and lines[0].startswith("# Description:"):
        desc = lines[0].split(":", 1)[1].strip()
        body_lines = lines[1:]
    return desc, "\n".join(body_lines).strip()


def _parse_directive_tokens(tokens: list[str], prog: str) -> tuple[str, list[str], dict[str, str]]:
    if not tokens:
        raise SystemExit(f"{prog}: missing target in preset/rule directive")
    target = tokens[0].strip()
    excludes: list[str] = []
    vars_map: dict[str, str] = {}
    for tok in tokens[1:]:
        s = tok.strip()
        if not s:
            continue
        if "=" in s and not s.startswith("-"):
            k, v = s.split("=", 1)
            k_clean = k.strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k_clean):
                raise SystemExit(f"{prog}: invalid variable name {k_clean!r} in {s!r}")
            vars_map[k_clean] = v.strip()
        elif s.startswith("-") and len(s) > 1:
            excludes.append(s[1:].strip())
        else:
            raise SystemExit(f"{prog}: unexpected argument {s!r} after target {target!r}")
    return target, excludes, vars_map


def _parse_preset_file(
    raw_text: str,
    fallback_desc: str,
) -> tuple[str, list[tuple[str | None, str, str, list[str], dict[str, str]]]]:
    prog = prog_name()
    desc = fallback_desc
    for raw_line in raw_text.splitlines():
        s = raw_line.strip()
        if s.startswith("# Description:"):
            desc = s.split(":", 1)[1].strip()
            break
    directives: list[tuple[str | None, str, str, list[str], dict[str, str]]] = []
    for cond_expr, line in strip_if_blocks_and_lines(raw_text, prog):
        parts = shlex.split(line)
        if not parts or parts[0] not in ("preset", "rule"):
            raise SystemExit(
                f"{prog}: invalid line in preset {fallback_desc!r}: {line!r} (expected 'preset ...' or 'rule ...')"
            )
        kind = parts[0]
        target, excls, vmap = _parse_directive_tokens(parts[1:], prog)
        directives.append((cond_expr, kind, target, excls, vmap))
    return desc, directives


def _load_package_from_dir(
    pkg_dir: Path,
) -> tuple[
    dict[str, tuple[str, str]],
    dict[str, tuple[str, list[tuple[str | None, str, str, list[str], dict[str, str]]]]],
]:
    rules: dict[str, tuple[str, str]] = {}
    presets: dict[str, tuple[str, list[tuple[str | None, str, str, list[str], dict[str, str]]]]] = {}
    r_root = pkg_dir / "rules" if (pkg_dir / "rules").is_dir() else (pkg_dir / "src/rules")
    p_root = pkg_dir / "presets" if (pkg_dir / "presets").is_dir() else (pkg_dir / "src/presets")
    if r_root.is_dir():
        for p in sorted(r_root.rglob("*.md")):
            if p.is_file():
                rel = p.relative_to(r_root).with_suffix("").as_posix().lower()
                rules[rel] = _parse_md_text(p.read_text(encoding="utf-8", errors="replace"), rel)
    if p_root.is_dir():
        for p in sorted(p_root.rglob("*.preset")):
            if p.is_file():
                rel = p.relative_to(p_root).with_suffix("").as_posix().lower()
                presets[rel] = _parse_preset_file(p.read_text(encoding="utf-8", errors="replace"), rel)
    return rules, presets


def _ensure_remote_package(pkg_spec: str, refresh: bool = False) -> Path:
    prog = prog_name()
    local_override = os.environ.get("AGENTS_BUNDLE_LOCAL_PKG_DIR")
    if local_override and pkg_spec == DEFAULT_RULES_PKG and Path(local_override).is_dir():
        return Path(local_override)
    home_candidate = Path.home() / "agents_rules"
    if pkg_spec == DEFAULT_RULES_PKG and not refresh and (home_candidate / "rules").is_dir() and (home_candidate / "presets").is_dir():
        cdir_chk = cache_dir_path() / "packages" / pkg_spec
        if not cdir_chk.is_dir():
            return home_candidate

    ref = ""
    repo_part = pkg_spec
    if "@" in pkg_spec:
        repo_part, ref = pkg_spec.rsplit("@", 1)
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


def _get_package_catalog(
    pkg_id: str,
    refresh: bool = False,
) -> tuple[
    dict[str, tuple[str, str]],
    dict[str, tuple[str, list[tuple[str | None, str, str, list[str], dict[str, str]]]]],
]:
    local_dir = Path(pkg_id).expanduser()
    if local_dir.is_dir():
        return _load_package_from_dir(local_dir)
    pkg_dir = _ensure_remote_package(pkg_id, refresh=refresh)
    return _load_package_from_dir(pkg_dir)


def _fetch_url_file(url: str, refresh: bool = False) -> Path:
    prog = prog_name()
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", url)
    cpath = cache_dir_path() / "urls" / slug
    if cpath.is_file() and not refresh:
        return cpath
    cpath.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"agents_bundle/{VERSION}"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
        cpath.write_text(data, encoding="utf-8")
        return cpath
    except Exception as exc:
        raise SystemExit(f"{prog}: failed to fetch {url!r}: {exc}")


def _parse_target_spec(spec: str, default_pkg: str | None = None) -> tuple[str, str]:
    prog = prog_name()
    if ":" not in spec and spec.startswith(("./", "../", "~/", "/")):
        return "__file__", spec
    if spec.startswith(("http://", "https://", "file://")):
        idx = spec.rfind(":")
        scheme_end = spec.find("://") + 2
        if idx <= scheme_end or spec.endswith((".md", ".preset")):
            return "__url__", spec
        return spec[:idx], spec[idx + 1:].strip().lower()
    if ":" not in spec:
        if default_pkg:
            return default_pkg, spec.strip().lower()
        raise SystemExit(
            f"{prog}: missing package prefix in {spec!r} (expected '<owner>/<repo>:{spec}' or './path')"
        )
    pkg, item = spec.split(":", 1)
    if not pkg.strip() or not item.strip():
        raise SystemExit(f"{prog}: invalid target {spec!r}; expected <package>:<item>")
    return pkg.strip(), item.strip().lower()


def _match_rule_in_dict(name: str, rules_dict: dict[str, tuple[str, str]]) -> str | None:
    if name in rules_dict:
        return name
    matches = [k for k in rules_dict if k.rsplit("/", 1)[-1] == name]
    if len(matches) == 1:
        return matches[0]
    return None


def collect_directive_items(
    kind: str,
    target_spec: str,
    excludes: list[str] | None = None,
    cli_vars: dict[str, str] | None = None,
    work_dir: Path | None = None,
    refresh: bool = False,
    default_pkg: str | None = None,
    trace_prefix: list[str] | None = None,
) -> list[tuple[str, str, str]]:
    """Returns list of (rule_uid, provenance_comment, rendered_body)."""
    prog = prog_name()
    if kind not in ("preset", "rule"):
        raise SystemExit(f"{prog}: directive kind must be 'preset' or 'rule' (got {kind!r})")

    pkg_id, item_name = _parse_target_spec(target_spec, default_pkg=default_pkg)
    excl_set: set[str] = set()
    for ex in excludes or []:
        clean_ex = ex.lstrip("-").strip().lower()
        if ":" in clean_ex:
            _, clean_ex = clean_ex.split(":", 1)
        if clean_ex:
            excl_set.add(clean_ex)

    effective_vars = {**builtin_vars(work_dir), **(cli_vars or {})}
    cur_trace = list(trace_prefix or [f"{kind} {target_spec}"])

    if pkg_id in ("__file__", "__url__"):
        if pkg_id == "__url__":
            fpath = _fetch_url_file(item_name, refresh=refresh)
            base_url = item_name.rsplit("/", 1)[0] if "/" in item_name else DEFAULT_RULES_PKG
        else:
            fpath = Path(item_name).expanduser()
            if work_dir is not None and not fpath.is_absolute():
                fpath = (work_dir / fpath).resolve()
            if not fpath.is_file():
                raise SystemExit(f"{prog}: {kind} file not found: {item_name}")
            base_url = DEFAULT_RULES_PKG
        raw = fpath.read_text(encoding="utf-8", errors="replace")
        if kind == "preset":
            _, directives = _parse_preset_file(raw, fpath.stem)
            items_out: list[tuple[str, str, str]] = []
            for cond_expr, sub_kind, sub_target, sub_excls, sub_vars in directives:
                merged_vars = {**effective_vars, **sub_vars, **(cli_vars or {})}
                if cond_expr and not eval_if_condition(cond_expr, merged_vars, prog):
                    continue
                merged_excls = list(excludes or []) + sub_excls
                step_label = f"[if {cond_expr}] {sub_kind} {sub_target}" if cond_expr else f"{sub_kind} {sub_target}"
                items_out.extend(
                    collect_directive_items(
                        sub_kind,
                        (f"{base_url}/{sub_target}" if (pkg_id == "__url__" and ":" not in sub_target and sub_target.endswith((".md", ".preset"))) else sub_target),
                        excludes=merged_excls,
                        cli_vars=merged_vars,
                        work_dir=work_dir,
                        refresh=refresh,
                        default_pkg=DEFAULT_RULES_PKG,
                        trace_prefix=[*cur_trace, step_label],
                    )
                )
            return items_out
        _, body = _parse_md_text(raw, fpath.stem)
        rendered = _render_rule_vars(body, effective_vars).strip()
        if not rendered:
            return []
        used_keys = {m.group(1) for m in RULE_VAR_RE.finditer(body)}
        active_vars = {k: v for k, v in effective_vars.items() if k in used_keys}
        vars_s = f" ({', '.join(f'{k}={v}' for k, v in active_vars.items())})" if active_vars else ""
        prov = f"# [{' -> '.join(cur_trace)}]{vars_s}"
        return [(str(fpath), prov, rendered)]

    def is_excluded(rk: str) -> bool:
        leaf = rk.rsplit("/", 1)[-1]
        return rk in excl_set or leaf in excl_set

    if kind == "rule":
        rules_dict, _ = _get_package_catalog(pkg_id, refresh=refresh)
        rk = _match_rule_in_dict(item_name, rules_dict)
        if rk is None:
            avail_r = sorted(rules_dict.keys())
            raise SystemExit(
                f"{prog}: unknown rule {item_name!r} in package {pkg_id!r} (available rules: {', '.join(avail_r)})"
            )
        if is_excluded(rk):
            return []
        raw_body = rules_dict[rk][1].strip()
        rendered = _render_rule_vars(raw_body, effective_vars)
        if not rendered:
            return []
        used_keys = {m.group(1) for m in RULE_VAR_RE.finditer(raw_body)}
        active_vars = {k: v for k, v in effective_vars.items() if k in used_keys}
        chain = [*cur_trace, f"rules/{rk}.md"] if (len(cur_trace) > 1 and cur_trace[-1].startswith("[if ")) else [*(cur_trace[:-1] if len(cur_trace) > 1 else cur_trace), f"rules/{rk}.md"]
        vars_s = f" ({', '.join(f'{k}={v}' for k, v in active_vars.items())})" if active_vars else ""
        prov = f"# [{' -> '.join(chain)}]{vars_s}"
        return [(f"{pkg_id}:{rk}", prov, rendered)]

    # kind == "preset"
    _, presets_dict = _get_package_catalog(pkg_id, refresh=refresh)
    if item_name not in presets_dict:
        avail_p = sorted(presets_dict.keys())
        raise SystemExit(
            f"{prog}: unknown preset {item_name!r} in package {pkg_id!r} (available presets: {', '.join(avail_p)})"
        )
    _, directives = presets_dict[item_name]
    out_items: list[tuple[str, str, str]] = []
    for cond_expr, sub_kind, sub_target, sub_excls, sub_vars in directives:
        merged_vars = {**effective_vars, **sub_vars, **(cli_vars or {})}
        if cond_expr and not eval_if_condition(cond_expr, merged_vars, prog):
            continue
        merged_excls = list(excludes or []) + sub_excls
        step_label = f"[if {cond_expr}] {sub_kind} {sub_target}" if cond_expr else f"{sub_kind} {sub_target}"
        out_items.extend(
            collect_directive_items(
                sub_kind,
                sub_target,
                excludes=merged_excls,
                cli_vars=merged_vars,
                work_dir=work_dir,
                refresh=refresh,
                default_pkg=pkg_id,
                trace_prefix=[*cur_trace, step_label],
            )
        )
    return out_items


def format_collected_rules(items: list[tuple[str, str, str]], verbose: bool = False) -> str:
    seen: set[str] = set()
    chunks: list[str] = []
    for uid, prov, body in items:
        if uid in seen:
            continue
        seen.add(uid)
        if verbose:
            chunks.append(f"{prov}\n{body}")
        else:
            chunks.append(body)
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
    rules_dict, presets_dict = _get_package_catalog(pkg_id)
    bvars = builtin_vars()
    sys.stdout.write("Built-in variables (usable in '[if key=val]' conditions and rule templates):\n")
    sys.stdout.write(f"  {'os':<38}  Active operating system (linux, macos, windows; current: {bvars['os']!r})\n")
    sys.stdout.write(f"  {'vcs':<38}  Detected repository VCS (git, cvs, or ''; current: {bvars['vcs']!r})\n\n")
    sys.stdout.write(f"Presets in '{pkg_id}' (use as 'preset {pkg_id}:<preset>'):\n")
    for k, (desc, directives) in presets_dict.items():
        target_tag = f"{pkg_id}:{k}"
        sys.stdout.write(f"  {target_tag:<38}  {desc}\n")
        for cond_expr, d_kind, d_tgt, d_ex, d_vars in directives:
            cond_s = f"[if {cond_expr}] " if cond_expr else ""
            ex_s = (" " + " ".join(f"-{e}" for e in d_ex)) if d_ex else ""
            var_s = (" " + " ".join(f"{vk}={vv}" for vk, vv in d_vars.items())) if d_vars else ""
            sys.stdout.write(f"  {'':<38}    {cond_s}{d_kind} {d_tgt}{ex_s}{var_s}\n")
    sys.stdout.write(f"\nAtomic rules in '{pkg_id}' (use as 'rule {pkg_id}:<rule>'):\n")
    for k, (desc, _) in rules_dict.items():
        target_tag = f"{pkg_id}:{k}"
        sys.stdout.write(f"  {target_tag:<38}  {desc}\n")
    return 0


def cmd_update_cache() -> int:
    pdir = cache_dir_path() / "packages"
    if not pdir.is_dir():
        sys.stdout.write(f"No cached packages in {pdir}\n")
        return 0
    updated = 0
    for git_dir in sorted(pdir.rglob(".git")):
        repo_root = git_dir.parent
        r = subprocess.run(["git", "-C", str(repo_root), "pull", "--ff-only"], capture_output=True, text=True, check=False)
        if r.returncode == 0:
            updated += 1
            sys.stdout.write(f"Updated {repo_root.relative_to(pdir)}\n")
        else:
            sys.stderr.write(f"Failed to update {repo_root}: {r.stderr.strip()}\n")
    sys.stdout.write(f"Refreshed {updated} cached package(s).\n")
    return 0
