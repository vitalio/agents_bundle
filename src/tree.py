def prog_name() -> str:
    raw = Path(sys.argv[0]).name if sys.argv and sys.argv[0] else "agents_bundle"
    for suf in (".py", ".cmd", ".bat", ".exe"):
        if raw.lower().endswith(suf) and len(raw) > len(suf):
            raw = raw[:-len(suf)]
            break
    return raw or "agents_bundle"


def cache_dir_path() -> Path:
    env_c = os.environ.get("AGENTS_BUNDLE_CACHE_DIR")
    if env_c:
        return Path(env_c).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else (Path.home() / ".cache")
    return base / "agents_bundle"


def usage_text() -> str:
    return (__doc__ or "").format(
        prog=prog_name(),
        default_pkg=DEFAULT_RULES_PKG,
        cache_dir=cache_dir_path(),
    )


def approx_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


_TREE_SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "target",
}


def _normalize_exclude_path(raw: str) -> str:
    s = Path(raw.strip()).as_posix().strip("/")
    while s.startswith("./"):
        s = s[2:].strip("/")
    return s


def _is_under_excluded(rel_posix: str, excluded_set: set[str]) -> str | None:
    for ex in excluded_set:
        if rel_posix == ex or rel_posix.startswith(ex + "/"):
            return ex
    return None


def _collect_repo_files(root: Path, excluded_set: set[str]) -> tuple[list[str], set[str]]:
    found_excluded: set[str] = set()
    for ex in excluded_set:
        if (root / ex).is_dir():
            found_excluded.add(ex)

    try:
        r = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
            check=False,
        )
        if r.returncode == 0:
            files = []
            for raw in r.stdout.splitlines():
                rel = raw.strip()
                if not rel:
                    continue
                rel_posix = Path(rel).as_posix()
                matched_ex = _is_under_excluded(rel_posix, excluded_set)
                if matched_ex is not None:
                    found_excluded.add(matched_ex)
                    continue
                p = root / rel_posix
                if p.is_file() and not p.is_symlink():
                    files.append(rel_posix)
            return sorted(set(files)), found_excluded
    except Exception:
        pass

    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir_obj = Path(dirpath).relative_to(root)
        rel_dir_str = "" if str(rel_dir_obj) == "." else rel_dir_obj.as_posix()
        kept_dirs: list[str] = []
        for d in sorted(dirnames):
            if d in _TREE_SKIP_DIRS or d.startswith(".git"):
                continue
            cand_rel = f"{rel_dir_str}/{d}" if rel_dir_str else d
            if cand_rel in excluded_set:
                found_excluded.add(cand_rel)
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            if p.is_file() and not p.is_symlink():
                rel_p = f"{rel_dir_str}/{fn}" if rel_dir_str else fn
                files.append(rel_p)
    return sorted(set(files)), found_excluded


def _inspect_file_meta(path: Path) -> tuple[int, bool, int]:
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            head = f.read(4096)
            if b"\x00" in head:
                return 0, True, size
            rest = f.read(512 * 1024)
        data = head + rest
        n_lines = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
        return n_lines, False, size
    except OSError:
        return 0, False, 0


def build_repo_tree(
    root_dir: Path | None = None,
    max_lines: int = 160,
    max_tokens: int = 1600,
    exclude_dirs: list[str] | None = None,
) -> str:
    root = (root_dir if root_dir is not None else Path.cwd()).resolve()
    excluded_input = {
        _normalize_exclude_path(x)
        for x in (exclude_dirs or [])
        if _normalize_exclude_path(x)
    }
    rel_files, active_excluded = _collect_repo_files(root, excluded_input)
    file_info: dict[str, tuple[int, bool, int]] = {}
    dir_files: dict[str, list[str]] = {"": []}
    dir_subdirs: dict[str, list[str]] = {"": []}
    all_dirs: set[str] = {""}

    def ensure_dir_chain(dir_path: str) -> None:
        if not dir_path:
            return
        parts = dir_path.split("/")
        cur = ""
        for part in parts:
            nxt = f"{cur}/{part}" if cur else part
            if nxt not in all_dirs:
                all_dirs.add(nxt)
                dir_files[nxt] = []
                dir_subdirs[nxt] = []
                dir_subdirs[cur].append(nxt)
            cur = nxt

    for ex_dir in sorted(active_excluded):
        ensure_dir_chain(ex_dir)

    for rel in rel_files:
        info = _inspect_file_meta(root / rel)
        file_info[rel] = info
        parts = rel.split("/")
        parent_dir = "/".join(parts[:-1])
        ensure_dir_chain(parent_dir)
        dir_files[parent_dir].append(rel)

    dirs_with_agents: set[str] = set()
    for d in all_dirs:
        dir_subdirs[d].sort()
        dir_files[d].sort(key=lambda f: (0 if f.rsplit("/", 1)[-1] == "AGENTS.md" else 1, f))
        if any(f.rsplit("/", 1)[-1] == "AGENTS.md" for f in dir_files[d]):
            cur_a = d
            while True:
                dirs_with_agents.add(cur_a)
                if not cur_a or "/" not in cur_a:
                    if cur_a:
                        dirs_with_agents.add("")
                    break
                cur_a = cur_a.rsplit("/", 1)[0]

    dirs_bottom_up = sorted(all_dirs, key=lambda x: (0 if not x else x.count("/") + 1), reverse=True)
    dir_totals: dict[str, tuple[int, int]] = {}
    for d in dirs_bottom_up:
        if d in active_excluded:
            dir_totals[d] = (0, 0)
            continue
        f_cnt = len(dir_files[d])
        l_cnt = sum(file_info[f][0] for f in dir_files[d])
        for sub in dir_subdirs[d]:
            sf, sl = dir_totals[sub]
            f_cnt += sf
            l_cnt += sl
        dir_totals[d] = (f_cnt, l_cnt)

    def render_dir(
        d: str,
        prefix: str,
        collapsed: set[str],
        file_limits: dict[str, int],
    ) -> list[str]:
        out: list[str] = []
        subs = dir_subdirs[d]
        files = dir_files[d]
        limit = file_limits.get(d)
        extra_files = 0
        extra_lines = 0
        if limit is not None and len(files) > limit:
            hidden = files[limit:]
            extra_files = len(hidden)
            extra_lines = sum(file_info[f][0] for f in hidden)
            files = files[:limit]

        entries: list[tuple[str, str]] = [("dir", s) for s in subs] + [("file", f) for f in files]
        if extra_files > 0:
            entries.append(("more", f"... (+{extra_files} more file{'s' if extra_files != 1 else ''}, {extra_lines:,}L)"))

        for idx, (kind, item) in enumerate(entries):
            is_last = idx == len(entries) - 1
            conn = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")
            if kind == "dir":
                name = item.rsplit("/", 1)[-1]
                if item in active_excluded:
                    out.append(f"{prefix}{conn}{name}/ (excluded)")
                elif item in collapsed:
                    fc, lc = dir_totals[item]
                    ag_note = ", AGENTS.md" if item in dirs_with_agents else ""
                    out.append(f"{prefix}{conn}{name}/ ({fc} file{'s' if fc != 1 else ''}, {lc:,}L{ag_note})")
                else:
                    out.append(f"{prefix}{conn}{name}/")
                    out.extend(render_dir(item, child_prefix, collapsed, file_limits))
            elif kind == "file":
                name = item.rsplit("/", 1)[-1]
                lines_n, is_bin, sz = file_info[item]
                tag = f"({sz:,}B)" if is_bin else f"({lines_n}L)"
                out.append(f"{prefix}{conn}{name} {tag}")
            else:
                out.append(f"{prefix}{conn}{item}")
        return out

    collapsed: set[str] = set()
    file_limits: dict[str, int] = {}
    total_f, total_l = dir_totals[""]
    footer = f"# Total: {total_f} file{'s' if total_f != 1 else ''}, {total_l:,} lines"

    def is_visible_dir(d: str) -> bool:
        if d == "" or d in active_excluded or d in collapsed:
            return False
        cur = d
        while "/" in cur:
            cur = cur.rsplit("/", 1)[0]
            if cur in collapsed or cur in active_excluded:
                return False
        return True

    while True:
        body = [f"{root.name}/"] + render_dir("", "", collapsed, file_limits)
        full_lines = body + [footer]
        tok = approx_tokens("\n".join(full_lines))
        if len(full_lines) <= max_lines and tok <= max_tokens:
            return "\n".join(full_lines) + "\n"

        # Stage 1: collapse nested subdirectories (depth >= 1) first, deepest first.
        # Include single-file deep chains when they have subdirectories or files inside.
        deep_candidates = [
            d for d in all_dirs
            if "/" in d and is_visible_dir(d) and (len(dir_subdirs[d]) + len(dir_files[d]) > 0)
        ]
        if deep_candidates:
            best_deep = max(deep_candidates, key=lambda d: (0 if d in dirs_with_agents else 1, d.count("/"), dir_totals[d][0]))
            collapsed.add(best_deep)
            # Clean up any child collapses under best_deep so set stays small
            prefix_slash = best_deep + "/"
            collapsed = {c for c in collapsed if not c.startswith(prefix_slash)}
            continue

        # Stage 2: truncate file lists in visible directories (down to 8, then 5) before collapsing top-level dirs
        trunc_candidates = []
        for d in all_dirs:
            if d != "" and not is_visible_dir(d):
                continue
            cur_lim = file_limits.get(d, len(dir_files[d]))
            if len(dir_files[d]) > 6 and cur_lim > 5:
                trunc_candidates.append((cur_lim, len(dir_files[d]), d))
        if trunc_candidates:
            _, _, best_trunc = max(trunc_candidates)
            cur_lim = file_limits.get(best_trunc, len(dir_files[best_trunc]))
            file_limits[best_trunc] = 8 if cur_lim > 10 else 5
            continue

        # Stage 3: collapse top-level directories if still over budget
        top_candidates = [
            d for d in dir_subdirs[""]
            if is_visible_dir(d) and (len(dir_subdirs[d]) + len(dir_files[d]) > 0)
        ]
        if top_candidates:
            best_top = max(top_candidates, key=lambda d: (0 if d in dirs_with_agents else 1, dir_totals[d][0]))
            collapsed.add(best_top)
            continue

        return "\n".join(full_lines[: max(2, max_lines - 1)] + [footer]) + "\n"


def _tree_from_args(argv: list[str], default_dir: Path | None = None) -> str:
    prog = prog_name()
    max_lines = 160
    max_tokens = 1600
    exclude_dirs: list[str] = []
    target_dir: Path | None = default_dir
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--max-lines":
            if i + 1 >= len(argv):
                raise SystemExit(f"{prog}: --max-lines requires an integer")
            try:
                max_lines = max(5, int(argv[i + 1]))
            except ValueError:
                raise SystemExit(f"{prog}: invalid --max-lines value: {argv[i + 1]!r}")
            i += 2
        elif a.startswith("--max-lines="):
            try:
                max_lines = max(5, int(a.split("=", 1)[1]))
            except ValueError:
                raise SystemExit(f"{prog}: invalid --max-lines value: {a!r}")
            i += 1
        elif a == "--max-tokens":
            if i + 1 >= len(argv):
                raise SystemExit(f"{prog}: --max-tokens requires an integer")
            try:
                max_tokens = max(20, int(argv[i + 1]))
            except ValueError:
                raise SystemExit(f"{prog}: invalid --max-tokens value: {argv[i + 1]!r}")
            i += 2
        elif a.startswith("--max-tokens="):
            try:
                max_tokens = max(20, int(a.split("=", 1)[1]))
            except ValueError:
                raise SystemExit(f"{prog}: invalid --max-tokens value: {a!r}")
            i += 1
        elif a in ("-x", "--exclude"):
            if i + 1 >= len(argv):
                raise SystemExit(f"{prog}: {a} requires a directory name")
            for part in argv[i + 1].split(","):
                if part.strip():
                    exclude_dirs.append(part.strip())
            i += 2
        elif a.startswith("--exclude="):
            for part in a.split("=", 1)[1].split(","):
                if part.strip():
                    exclude_dirs.append(part.strip())
            i += 1
        elif a.startswith("-"):
            raise SystemExit(
                f"{prog}: usage: {prog} --tree [DIR] [-x/--exclude DIR] [--max-lines N] [--max-tokens N]"
            )
        else:
            p = Path(a).expanduser()
            if default_dir is not None and not p.is_absolute():
                p = default_dir / p
            if not p.is_dir():
                raise SystemExit(f"{prog}: directory not found: {a}")
            target_dir = p
            i += 1
    return build_repo_tree(
        root_dir=target_dir,
        max_lines=max_lines,
        max_tokens=max_tokens,
        exclude_dirs=exclude_dirs,
    )


def cmd_tree(argv: list[str]) -> int:
    sys.stdout.write(_tree_from_args(argv))
    return 0
