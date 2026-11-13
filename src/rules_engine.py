RULE_VAR_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*):([^{}]*)\}")


def _render_rule_vars(text: str, vars_map: dict[str, str]) -> str:
    return RULE_VAR_RE.sub(lambda m: vars_map.get(m.group(1), m.group(2)), text)


def _detect_vcs_rule(work_dir: Path | None = None) -> str | None:
    wdir = (work_dir if work_dir is not None else Path.cwd()).resolve()
    cur = wdir
    while True:
        if (cur / ".git").exists():
            return "vcs/git"
        if (cur / "CVS").is_dir():
            return "vcs/cvs"
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


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


def _parse_preset_file(raw_text: str, fallback_desc: str) -> tuple[str, list[tuple[str, str, list[str], dict[str, str]]]]:
    prog = prog_name()
    desc = fallback_desc
    directives: list[tuple[str, str, list[str], dict[str, str]]] = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# Description:"):
            desc = line.split(":", 1)[1].strip()
            continue
        if line.startswith("#"):
            continue
        parts = shlex.split(line)
        if not parts or parts[0] not in ("preset", "rule"):
            raise SystemExit(f"{prog}: invalid line in preset {fallback_desc!r}: {line!r} (expected 'preset ...' or 'rule ...')")
        kind = parts[0]
        target, excls, vmap = _parse_directive_tokens(parts[1:], prog)
        directives.append((kind, target, excls, vmap))
    return desc, directives


def _load_package_from_dir(pkg_dir: Path) -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, list[tuple[str, str, list[str], dict[str, str]]]]]]:
    rules: dict[str, tuple[str, str]] = {}
    presets: dict[str, tuple[str, list[tuple[str, str, list[str], dict[str, str]]]]] = {}
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
    # Check if local override directory exists (e.g. ~/agents_rules when developing locally)
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


def _get_package_catalog(pkg_id: str, refresh: bool = False) -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, list[tuple[str, str, list[str], dict[str, str]]]]]]:
    local_dir = Path(pkg_id).expanduser()
    if local_dir.is_dir():
        return _load_package_from_dir(local_dir)
    pkg_dir = _ensure_remote_package(pkg_id, refresh=refresh)
    return _load_package_from_dir(pkg_dir)


def _parse_target_spec(spec: str, default_pkg: str | None = None) -> tuple[str, str]:
    prog = prog_name()
    if ":" not in spec and spec.startswith(("./", "../", "~/", "/")):
        return "__file__", spec
    if ":" not in spec:
        if default_pkg:
            return default_pkg, spec.strip().lower()
        raise SystemExit(
            f"{prog}: missing package prefix in {spec!r} (expected '<owner>/<repo>:{spec}' or './path')"
        )
    if spec.startswith(("http://", "https://")):
        idx = spec.rfind(":")
        if idx <= 8:
            raise SystemExit(f"{prog}: missing ':<item>' in URL target {spec!r}")
        return spec[:idx], spec[idx + 1:].strip().lower()
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


def render_directive(
    kind: str,
    target_spec: str,
    excludes: list[str] | None = None,
    cli_vars: dict[str, str] | None = None,
    work_dir: Path | None = None,
    refresh: bool = False,
    default_pkg: str | None = None,
) -> str:
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

    caller_vars = dict(cli_vars or {})

    if pkg_id == "__file__":
        fpath = Path(item_name).expanduser()
        if work_dir is not None and not fpath.is_absolute():
            fpath = (work_dir / fpath).resolve()
        if not fpath.is_file():
            raise SystemExit(f"{prog}: {kind} file not found: {item_name}")
        raw = fpath.read_text(encoding="utf-8", errors="replace")
        if kind == "preset":
            _, directives = _parse_preset_file(raw, fpath.stem)
            parts: list[str] = []
            for sub_kind, sub_target, sub_excls, sub_vars in directives:
                # Caller vars override preset line vars
                merged_vars = {**sub_vars, **caller_vars}
                merged_excls = list(excludes or []) + sub_excls
                rendered = render_directive(
                    sub_kind,
                    sub_target,
                    excludes=merged_excls,
                    cli_vars=merged_vars,
                    work_dir=work_dir,
                    refresh=refresh,
                    default_pkg=DEFAULT_RULES_PKG,
                )
                if rendered.strip():
                    parts.append(rendered.strip())
            return "\n".join(parts)
        _, body = _parse_md_text(raw, fpath.stem)
        return _render_rule_vars(body, caller_vars)

    def is_excluded(rk: str) -> bool:
        leaf = rk.rsplit("/", 1)[-1]
        return rk in excl_set or leaf in excl_set

    if kind == "rule":
        if item_name in ("vcs/auto", "auto-vcs"):
            vcs = _detect_vcs_rule(work_dir)
            if not vcs:
                return ""
            item_name = vcs
        rules_dict, _ = _get_package_catalog(pkg_id, refresh=refresh)
        rk = _match_rule_in_dict(item_name, rules_dict)
        if rk is None:
            avail_r = sorted(rules_dict.keys())
            raise SystemExit(
                f"{prog}: unknown rule {item_name!r} in package {pkg_id!r} (available rules: {', '.join(avail_r)})"
            )
        if is_excluded(rk):
            return ""
        return _render_rule_vars(rules_dict[rk][1].strip(), caller_vars)

    # kind == "preset"
    _, presets_dict = _get_package_catalog(pkg_id, refresh=refresh)
    if item_name not in presets_dict:
        avail_p = sorted(presets_dict.keys())
        raise SystemExit(
            f"{prog}: unknown preset {item_name!r} in package {pkg_id!r} (available presets: {', '.join(avail_p)})"
        )
    _, directives = presets_dict[item_name]
    out_parts: list[str] = []
    for sub_kind, sub_target, sub_excls, sub_vars in directives:
        # Precedence: rule default < inner preset line vars < outer caller vars
        merged_vars = {**sub_vars, **caller_vars}
        merged_excls = list(excludes or []) + sub_excls
        rendered = render_directive(
            sub_kind,
            sub_target,
            excludes=merged_excls,
            cli_vars=merged_vars,
            work_dir=work_dir,
            refresh=refresh,
            default_pkg=pkg_id,
        )
        if rendered.strip():
            out_parts.append(rendered.strip())
    return "\n".join(out_parts)


def cmd_list_rules(pkg_id: str = DEFAULT_RULES_PKG) -> int:
    rules_dict, presets_dict = _get_package_catalog(pkg_id)
    sys.stdout.write(f"Presets in '{pkg_id}' (use as 'preset {pkg_id}:<preset>'):\n")
    for k, (desc, directives) in presets_dict.items():
        target_tag = f"{pkg_id}:{k}"
        sys.stdout.write(f"  {target_tag:<38}  {desc}\n")
        for d_kind, d_tgt, d_ex, d_vars in directives:
            ex_s = (" " + " ".join(f"-{e}" for e in d_ex)) if d_ex else ""
            var_s = (" " + " ".join(f"{vk}={vv}" for vk, vv in d_vars.items())) if d_vars else ""
            sys.stdout.write(f"  {'':<38}    {d_kind} {d_tgt}{ex_s}{var_s}\n")
    sys.stdout.write(f"\nAtomic rules in '{pkg_id}' (use as 'rule {pkg_id}:<rule>'):\n")
    sys.stdout.write(f"  {pkg_id + ':vcs/auto':<38}  Auto-select vcs/git or vcs/cvs by repository directory\n")
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
