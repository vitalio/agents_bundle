from __future__ import annotations

import fnmatch
import math
import os
import stat
import subprocess
import sys
from pathlib import Path

from src.core import prog_name


def approx_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


_TREE_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "CVS",
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


def _normalize_ignore_pattern(raw_pat: str) -> tuple[str, bool] | None:
    pat = raw_pat.strip()
    if not pat or pat.startswith("#") or pat.startswith("!"):
        return None
    while pat.startswith("./"):
        pat = pat[2:]
    dir_only = pat.endswith("/")
    pat = pat.strip("/")
    if pat.startswith("**/"):
        pat = pat[3:].strip("/")
    if not pat:
        return None
    return pat, dir_only


def _load_ignore_patterns(root: Path) -> list[tuple[str, bool]]:
    patterns: list[tuple[str, bool]] = []
    cvsignore = root / ".cvsignore"
    if cvsignore.is_file():
        try:
            for raw_line in cvsignore.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                for tok in line.split():
                    norm = _normalize_ignore_pattern(tok)
                    if norm is not None:
                        patterns.append(norm)
        except OSError:
            pass
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        try:
            for raw_line in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
                norm = _normalize_ignore_pattern(raw_line)
                if norm is not None:
                    patterns.append(norm)
        except OSError:
            pass
    return patterns


def _matches_ignore(
    name: str,
    rel_posix: str,
    patterns: list[tuple[str, bool]],
    *,
    is_dir: bool,
) -> bool:
    if not is_dir and name == "AGENTS.md":
        return False
    for pat, dir_only in patterns:
        if dir_only and not is_dir:
            continue
        if "/" in pat:
            if fnmatch.fnmatchcase(rel_posix, pat):
                return True
        elif fnmatch.fnmatchcase(name, pat) or fnmatch.fnmatchcase(rel_posix, pat):
            return True
    return False


def _collect_repo_files(root: Path, excluded_set: set[str]) -> tuple[list[str], set[str]]:
    root_str = str(root)
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
                try:
                    st = os.lstat(os.path.join(root_str, rel_posix))
                except OSError:
                    continue
                if stat.S_ISREG(st.st_mode):
                    files.append(rel_posix)
            return sorted(set(files)), found_excluded
    except Exception:
        pass

    ignore_patterns = _load_ignore_patterns(root)
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
            if _matches_ignore(d, cand_rel, ignore_patterns, is_dir=True):
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs
        for fn in sorted(filenames):
            rel_p = f"{rel_dir_str}/{fn}" if rel_dir_str else fn
            if _matches_ignore(fn, rel_p, ignore_patterns, is_dir=False):
                continue
            try:
                st = os.lstat(os.path.join(dirpath, fn))
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                files.append(rel_p)
    return sorted(set(files)), found_excluded


_LARGE_FILE_BYTES = 16 * 1024
_DENSE_LINE_BYTES = 120


def _format_total_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        val = f"{num_bytes / 1024:.1f}"
        if val.endswith(".0"):
            val = val[:-2]
        return f"{val} KB"
    val = f"{num_bytes / (1024 * 1024):.1f}"
    if val.endswith(".0"):
        val = val[:-2]
    return f"{val} MB"


def _format_file_size_k(num_bytes: int) -> str:
    kb = num_bytes / 1024
    if kb >= 10:
        return f"{round(kb)}K"
    val = f"{max(0.1, kb):.1f}"
    if val.endswith(".0"):
        val = val[:-2]
    return f"{val}K"


def _format_file_tag(lines_n: int, is_bin: bool, size: int) -> str:
    if is_bin:
        return f"({size:,}B)"
    if size >= _LARGE_FILE_BYTES or (lines_n > 0 and size > lines_n * _DENSE_LINE_BYTES):
        return f"({lines_n}L, {_format_file_size_k(size)})"
    return f"({lines_n}L)"


def _inspect_file_meta(path: Path | str) -> tuple[int, bool, int]:
    try:
        size = os.stat(path).st_size
        with open(path, "rb") as f:
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
        if not dir_path or dir_path in all_dirs:
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

    root_prefix = str(root) + os.sep
    for rel in rel_files:
        info = _inspect_file_meta(root_prefix + rel)
        file_info[rel] = info
        parent_dir = rel.rsplit("/", 1)[0] if "/" in rel else ""
        if parent_dir and parent_dir not in all_dirs:
            ensure_dir_chain(parent_dir)
        dir_files[parent_dir].append(rel)

    dirs_with_agents: set[str] = set()
    for d in all_dirs:
        dir_subdirs[d].sort()
        files_d = dir_files[d]
        if files_d:
            files_d.sort(key=lambda f: (0 if (f == "AGENTS.md" or f.endswith("/AGENTS.md")) else 1, f))
            if files_d[0] == "AGENTS.md" or files_d[0].endswith("/AGENTS.md"):
                cur_a = d
                while cur_a not in dirs_with_agents:
                    dirs_with_agents.add(cur_a)
                    if not cur_a:
                        break
                    cur_a = cur_a.rsplit("/", 1)[0] if "/" in cur_a else ""

    dirs_bottom_up = sorted(all_dirs, key=lambda x: (0 if not x else x.count("/") + 1), reverse=True)
    dir_totals: dict[str, tuple[int, int, int]] = {}
    for d in dirs_bottom_up:
        if d in active_excluded:
            dir_totals[d] = (0, 0, 0)
            continue
        f_cnt = len(dir_files[d])
        l_cnt = sum(file_info[f][0] for f in dir_files[d])
        b_cnt = sum(file_info[f][2] for f in dir_files[d])
        for sub in dir_subdirs[d]:
            sf, sl, sb = dir_totals[sub]
            f_cnt += sf
            l_cnt += sl
            b_cnt += sb
        dir_totals[d] = (f_cnt, l_cnt, b_cnt)

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
                    fc, lc, _ = dir_totals[item]
                    ag_note = ", AGENTS.md" if item in dirs_with_agents else ""
                    out.append(f"{prefix}{conn}{name}/ ({fc} file{'s' if fc != 1 else ''}, {lc:,}L{ag_note})")
                else:
                    out.append(f"{prefix}{conn}{name}/")
                    out.extend(render_dir(item, child_prefix, collapsed, file_limits))
            elif kind == "file":
                name = item.rsplit("/", 1)[-1]
                lines_n, is_bin, sz = file_info[item]
                tag = _format_file_tag(lines_n, is_bin, sz)
                out.append(f"{prefix}{conn}{name} {tag}")
            else:
                out.append(f"{prefix}{conn}{item}")
        return out

    collapsed: set[str] = set()
    file_limits: dict[str, int] = {}
    total_f, total_l, total_b = dir_totals[""]
    footer = (
        f"# Total: {total_f} file{'s' if total_f != 1 else ''}, "
        f"{total_l:,} lines ({_format_total_size(total_b)})"
    )

    def is_initially_open(d: str) -> bool:
        if d == "":
            return True
        if d in active_excluded:
            return False
        if not active_excluded:
            return True
        cur = d
        while "/" in cur:
            cur = cur.rsplit("/", 1)[0]
            if cur in active_excluded:
                return False
        return True

    open_dirs = [d for d in all_dirs if is_initially_open(d)]
    cur_lines = 2 + sum(len(dir_subdirs[d]) + len(dir_files[d]) for d in open_dirs)

    # Precompute deterministic O(D log D) reduction operations across Stages 1, 2, and 3:
    # (kind, dir_path, new_limit, prev_limit, line_delta)
    ops: list[tuple[str, str, int, int, int]] = []

    # Stage 1: collapse nested subdirectories (depth >= 1) first, deepest first.
    deep_candidates = [
        d for d in open_dirs
        if "/" in d and (len(dir_subdirs[d]) + len(dir_files[d]) > 0)
    ]
    deep_candidates.sort(
        key=lambda d: (0 if d in dirs_with_agents else 1, d.count("/"), dir_totals[d][0]),
        reverse=True,
    )
    for d in deep_candidates:
        ops.append(("collapse", d, 0, 0, len(dir_subdirs[d]) + len(dir_files[d])))

    # Stage 2: truncate file lists in visible directories (down to 8, then 5) before collapsing top-level dirs.
    stage2_dirs = [""] + [d for d in dir_subdirs[""] if d not in active_excluded]
    stage2_steps: list[tuple[int, int, str, int, int, int]] = []
    for d in stage2_dirs:
        n_files = len(dir_files[d])
        if n_files > 10:
            stage2_steps.append((n_files, n_files, d, 8, 0, n_files - 9))
            stage2_steps.append((8, n_files, d, 5, 8, 3))
        elif n_files > 6:
            stage2_steps.append((n_files, n_files, d, 5, 0, n_files - 6))
    stage2_steps.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    for _, _, d, new_lim, prev_lim, delta in stage2_steps:
        ops.append(("trunc", d, new_lim, prev_lim, delta))

    # Stage 3: collapse top-level directories if still over budget.
    top_candidates = [
        d for d in dir_subdirs[""]
        if d not in active_excluded and (len(dir_subdirs[d]) + len(dir_files[d]) > 0)
    ]
    top_candidates.sort(
        key=lambda d: (0 if d in dirs_with_agents else 1, dir_totals[d][0]),
        reverse=True,
    )
    for d in top_candidates:
        n_files = len(dir_files[d])
        vis_files = 6 if n_files > 6 else n_files
        ops.append(("collapse", d, 0, 0, len(dir_subdirs[d]) + vis_files))

    cur_idx = 0

    def move_to(target_idx: int) -> None:
        nonlocal cur_idx, cur_lines
        while cur_idx < target_idx:
            kind, d, new_lim, _prev_lim, delta = ops[cur_idx]
            if kind == "collapse":
                collapsed.add(d)
            else:
                file_limits[d] = new_lim
            cur_lines -= delta
            cur_idx += 1
        while cur_idx > target_idx:
            cur_idx -= 1
            kind, d, _new_lim, prev_lim, delta = ops[cur_idx]
            if kind == "collapse":
                collapsed.discard(d)
            else:
                if prev_lim == 0:
                    file_limits.pop(d, None)
                else:
                    file_limits[d] = prev_lim
            cur_lines += delta

    def render_full() -> tuple[list[str], int]:
        full = [f"{root.name}/"] + render_dir("", "", collapsed, file_limits) + [footer]
        return full, approx_tokens("\n".join(full))

    while cur_idx < len(ops) and cur_lines > max_lines:
        move_to(cur_idx + 1)

    full_lines, tok = render_full()
    if len(full_lines) <= max_lines and tok <= max_tokens:
        return "\n".join(full_lines) + "\n"

    if cur_idx < len(ops):
        lo = cur_idx + 1
        step = 1
        hi = lo
        best_lines: list[str] | None = None
        while True:
            move_to(hi)
            cand_lines, cand_tok = render_full()
            if len(cand_lines) <= max_lines and cand_tok <= max_tokens:
                best_lines = cand_lines
                break
            if hi >= len(ops):
                full_lines = cand_lines
                break
            lo = hi + 1
            step *= 2
            hi = min(len(ops), lo + step - 1)

        if best_lines is not None:
            while lo < hi:
                mid = (lo + hi) // 2
                move_to(mid)
                cand_lines, cand_tok = render_full()
                if len(cand_lines) <= max_lines and cand_tok <= max_tokens:
                    best_lines = cand_lines
                    hi = mid
                else:
                    lo = mid + 1
            return "\n".join(best_lines) + "\n"

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
