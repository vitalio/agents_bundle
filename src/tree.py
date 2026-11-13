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


def _collect_repo_files(root: Path) -> list[str]:
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
                p = root / rel
                if p.is_file() and not p.is_symlink():
                    files.append(Path(rel).as_posix())
            return sorted(set(files))
    except Exception:
        pass

    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in _TREE_SKIP_DIRS and not d.startswith(".git")
        )
        rel_dir = Path(dirpath).relative_to(root)
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            if p.is_file() and not p.is_symlink():
                rel_p = (rel_dir / fn).as_posix() if str(rel_dir) != "." else fn
                files.append(rel_p)
    return sorted(set(files))


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
    max_lines: int = 120,
    max_tokens: int = 1200,
) -> str:
    root = (root_dir if root_dir is not None else Path.cwd()).resolve()
    rel_files = _collect_repo_files(root)
    file_info: dict[str, tuple[int, bool, int]] = {}
    dir_files: dict[str, list[str]] = {"": []}
    dir_subdirs: dict[str, list[str]] = {"": []}
    all_dirs: set[str] = {""}

    for rel in rel_files:
        info = _inspect_file_meta(root / rel)
        file_info[rel] = info
        parts = rel.split("/")
        cur = ""
        for part in parts[:-1]:
            nxt = f"{cur}/{part}" if cur else part
            if nxt not in all_dirs:
                all_dirs.add(nxt)
                dir_files[nxt] = []
                dir_subdirs[nxt] = []
                dir_subdirs[cur].append(nxt)
            cur = nxt
        dir_files[cur].append(rel)

    for d in all_dirs:
        dir_subdirs[d].sort()
        dir_files[d].sort()

    dir_totals: dict[str, tuple[int, int]] = {}
    for d in sorted(all_dirs, key=lambda x: (0 if not x else x.count("/") + 1), reverse=True):
        f_cnt = len(dir_files[d])
        l_cnt = sum(file_info[f][0] for f in dir_files[d])
        for sub in dir_subdirs[d]:
            sf, sl = dir_totals[sub]
            f_cnt += sf
            l_cnt += sl
        dir_totals[d] = (f_cnt, l_cnt)

    def render_dir(d: str, prefix: str, collapsed: set[str], root_file_limit: int | None) -> list[str]:
        out: list[str] = []
        subs = dir_subdirs[d]
        files = dir_files[d]
        extra_files = 0
        if d == "" and root_file_limit is not None and len(files) > root_file_limit:
            extra_files = len(files) - root_file_limit
            files = files[:root_file_limit]

        entries: list[tuple[str, str]] = [("dir", s) for s in subs] + [("file", f) for f in files]
        if extra_files > 0:
            entries.append(("more", f"... (+{extra_files} more files)"))

        for idx, (kind, item) in enumerate(entries):
            is_last = idx == len(entries) - 1
            conn = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")
            if kind == "dir":
                name = item.rsplit("/", 1)[-1]
                if item in collapsed:
                    fc, lc = dir_totals[item]
                    out.append(f"{prefix}{conn}{name}/ ({fc} file{'s' if fc != 1 else ''}, {lc:,}L)")
                else:
                    out.append(f"{prefix}{conn}{name}/")
                    out.extend(render_dir(item, child_prefix, collapsed, None))
            elif kind == "file":
                name = item.rsplit("/", 1)[-1]
                lines_n, is_bin, sz = file_info[item]
                tag = f"({sz:,}B)" if is_bin else f"({lines_n}L)"
                out.append(f"{prefix}{conn}{name} {tag}")
            else:
                out.append(f"{prefix}{conn}{item}")
        return out

    collapsed: set[str] = set()
    root_limit: int | None = None
    total_f, total_l = dir_totals[""]

    while True:
        body = [f"{root.name}/"] + render_dir("", "", collapsed, root_limit)
        footer = f"# Total: {total_f} file{'s' if total_f != 1 else ''}, {total_l:,} lines"
        full_lines = body + [footer]
        tok = approx_tokens("\n".join(full_lines))
        if len(full_lines) <= max_lines and tok <= max_tokens:
            return "\n".join(full_lines) + "\n"

        candidates = [
            d for d in all_dirs
            if d != "" and d not in collapsed and not any(
                d.startswith(c + "/") for c in collapsed
            ) and dir_totals[d][0] > 1
        ]
        if candidates:
            best = max(candidates, key=lambda d: (d.count("/"), dir_totals[d][0]))
            collapsed.add(best)
            continue

        cur_root_files = len(dir_files[""]) if root_limit is None else root_limit
        if cur_root_files > 5:
            root_limit = max(5, cur_root_files // 2)
            continue
        return "\n".join(full_lines[: max(2, max_lines - 1)] + [footer]) + "\n"


def _tree_from_args(argv: list[str], default_dir: Path | None = None) -> str:
    prog = prog_name()
    max_lines = 120
    max_tokens = 1200
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
        elif a.startswith("-"):
            raise SystemExit(f"{prog}: usage: {prog} --tree [DIR] [--max-lines N] [--max-tokens N]")
        else:
            p = Path(a).expanduser()
            if default_dir is not None and not p.is_absolute():
                p = default_dir / p
            if not p.is_dir():
                raise SystemExit(f"{prog}: directory not found: {a}")
            target_dir = p
            i += 1
    return build_repo_tree(root_dir=target_dir, max_lines=max_lines, max_tokens=max_tokens)


def cmd_tree(argv: list[str]) -> int:
    sys.stdout.write(_tree_from_args(argv))
    return 0
