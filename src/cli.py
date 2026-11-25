from __future__ import annotations

import ast
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

from src.header import DEFAULT_RULES_PKG, DEFAULT_UPDATE_URL, LEGACY_REPO_MARKER, REPO_MARKER, VERSION
from src.core import cache_dir_path, prog_name, usage_text
from src.tree import cmd_tree
from src.rules_engine import (
    _parse_rule_directive_tokens,
    cmd_list_rules,
    cmd_update_cache,
    collect_directive_items,
    env_vars,
    format_collected_rules,
)
from src.bundle import cmd_bundle, cmd_init, cmd_trust


def parse_version_from_source(source: str) -> str | None:
    m = re.search(r'^VERSION\s*=\s*["\x27]([^"\x27]+)["\x27]', source, flags=re.MULTILINE)
    return m.group(1) if m else None


def version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.split(r"[^0-9]+", v) if p)


def _is_our_binary(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:2048]
    except OSError:
        return False
    return REPO_MARKER in head or LEGACY_REPO_MARKER in head


def _remove_legacy_binary(install_dir: Path, keep_path: Path | None = None) -> None:
    legacy = install_dir / "agents_bundle"
    if keep_path is not None and legacy.resolve() == keep_path.resolve():
        return
    if _is_our_binary(legacy):
        try:
            legacy.unlink()
        except OSError:
            pass


def fetch_remote_script(url: str | None = None) -> str:
    import urllib.request

    target_url = url or os.environ.get("CONTEXT_BUNDLE_UPDATE_URL") or DEFAULT_UPDATE_URL
    if target_url.startswith(("http://", "https://")) and "?" not in target_url:
        target_url = f"{target_url}?t={int(time.time())}"
    req = urllib.request.Request(
        target_url,
        headers={"User-Agent": f"context-bundle/{VERSION}", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read().decode("utf-8")
    if REPO_MARKER not in data and LEGACY_REPO_MARKER not in data:
        raise ValueError("downloaded file does not contain expected repository marker")
    ast.parse(data)
    return data


def cmd_check_update(url: str | None = None) -> int:
    prog = prog_name()
    try:
        remote_src = fetch_remote_script(url)
    except Exception as exc:
        sys.stderr.write(f"{prog}: failed to check for updates: {exc}\n")
        return 1
    remote_ver = parse_version_from_source(remote_src) or "unknown"
    if version_tuple(remote_ver) > version_tuple(VERSION):
        sys.stdout.write(f"{prog}: update available: {VERSION} -> {remote_ver} (run '{prog} --update')\n")
    else:
        sys.stdout.write(f"{prog} {VERSION} is up to date (remote: {remote_ver}).\n")
    return 0


def cmd_update(force: bool = False, url: str | None = None) -> int:
    prog = prog_name()
    self_file = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else Path(__file__).resolve()
    if not self_file.is_file():
        self_file = Path(__file__).resolve()
    dest = (self_file.parent / "context") if self_file.name == "agents_bundle" else self_file
    try:
        remote_src = fetch_remote_script(url)
    except Exception as exc:
        sys.stderr.write(f"{prog}: update failed: {exc}\n")
        return 1
    remote_ver = parse_version_from_source(remote_src) or "unknown"
    if not force and dest == self_file and version_tuple(remote_ver) <= version_tuple(VERSION):
        _remove_legacy_binary(dest.parent, keep_path=dest)
        sys.stdout.write(f"{prog} {VERSION} is already up to date.\n")
        return 0
    try:
        tmp_fd, tmp_name = tempfile.mkstemp(prefix=f".{dest.name}.", dir=str(dest.parent))
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(remote_src)
            os.chmod(tmp_name, 0o755)
            os.replace(tmp_name, dest)
        except Exception:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise
    except Exception as exc:
        sys.stderr.write(f"{prog}: could not write updated binary to {dest}: {exc}\n")
        return 1
    _remove_legacy_binary(dest.parent, keep_path=dest)
    sys.stdout.write(f"{prog}: updated {VERSION} -> {remote_ver} ({dest})\n")
    return 0


def cmd_uninstall() -> int:
    prog = prog_name()
    removed_bins: list[str] = []
    candidate_dirs: list[Path] = []
    env_dir = os.environ.get("CONTEXT_BUNDLE_INSTALL_DIR")
    if env_dir:
        candidate_dirs.append(Path(env_dir).expanduser())
    self_path = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else Path(__file__).resolve()
    is_repo_checkout = (self_path.parent / "build.py").is_file() and (self_path.parent / "src").is_dir()
    if not is_repo_checkout and self_path.parent.is_dir():
        candidate_dirs.append(self_path.parent)
    elif not env_dir:
        candidate_dirs.append(Path.home() / ".local" / "bin")

    cmd_name = os.environ.get("CONTEXT_BUNDLE_NAME") or "context"
    names = []
    for n in (cmd_name, self_path.name if not is_repo_checkout else "", "context", "agents_bundle"):
        if n and n not in names:
            names.append(n)

    seen_targets: set[Path] = set()
    for d in candidate_dirs:
        for n in names:
            target = d / n
            try:
                resolved = target.resolve()
            except OSError:
                continue
            if resolved in seen_targets:
                continue
            seen_targets.add(resolved)
            if (resolved.parent / "build.py").is_file() and (resolved.parent / "src").is_dir():
                continue
            if target.is_file():
                if not _is_our_binary(target):
                    if n == cmd_name and env_dir:
                        sys.stderr.write(f"{prog}: {target} is not a vitalio/context-bundle script\n")
                        return 1
                    continue
                try:
                    target.unlink()
                    removed_bins.append(str(target))
                except OSError as exc:
                    sys.stderr.write(f"{prog}: could not remove {target}: {exc}\n")
                    return 1

    cdir = cache_dir_path()
    removed_caches: list[str] = []
    for cache_target in (cdir, cdir.parent / "agents_bundle"):
        if cache_target.exists():
            shutil.rmtree(cache_target, ignore_errors=True)
            removed_caches.append(str(cache_target))

    details = ", ".join([*removed_bins, *removed_caches]) or "nothing to remove"
    sys.stdout.write(f"{prog}: uninstalled ({details})\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    prog = prog_name()
    if "-h" in args or "--help" in args:
        sys.stdout.write(usage_text())
        return 0
    if "-V" in args or "--version" in args:
        sys.stdout.write(f"{prog} {VERSION}\n")
        return 0
    if args and args[0] == "bundle":
        if len(args) < 2 or args[1].startswith("-"):
            raise SystemExit(
                f"{prog}: usage: {prog} bundle <pkg>[:<name>] [k=v] [-C DIR] [-p TEXT] [--plain] [-v] [--refresh]"
            )
        return cmd_bundle(args[2:], bundle_target=args[1], raw_argv=args)
    if args and args[0] == "rule":
        refresh = "--refresh" in args[1:]
        verbose = "-v" in args[1:] or "--verbose" in args[1:]
        rest_tokens = [a for a in args[1:] if a not in ("--refresh", "-v", "--verbose")]
        targets, vmap = _parse_rule_directive_tokens(rest_tokens, prog)
        merged_vmap = {**env_vars(prog), **vmap}
        items = []
        for target in targets:
            items.extend(
                collect_directive_items(
                    "rule",
                    target,
                    cli_vars=merged_vmap,
                    refresh=refresh,
                )
            )
        out = format_collected_rules(items, verbose=verbose)
        if out:
            sys.stdout.write(out + "\n")
        return 0
    if args and args[0] in ("--list", "-l"):
        if len(args) > 2:
            raise SystemExit(f"{prog}: usage: {prog} --list [package]")
        return cmd_list_rules(args[1] if len(args) == 2 else DEFAULT_RULES_PKG)
    if args and args[0] == "--update-cache":
        return cmd_update_cache()
    if args and args[0] == "--init":
        force = "--force" in args[1:]
        rest = [a for a in args[1:] if a != "--force"]
        if rest:
            raise SystemExit(f"{prog}: usage: {prog} --init [--force]")
        return cmd_init(force=force)
    if args and args[0] == "--trust":
        return cmd_trust(args[1:])
    if args and args[0] == "--tree":
        return cmd_tree(args[1:])
    if args and args[0] == "--check-update":
        return cmd_check_update()
    if args and args[0] in ("--update", "--self-update"):
        return cmd_update(force="--force" in args[1:])
    if args and args[0] == "--uninstall":
        if len(args) > 1:
            raise SystemExit(f"{prog}: usage: {prog} --uninstall")
        return cmd_uninstall()
    return cmd_bundle(args)


if __name__ == "__main__":
    raise SystemExit(main())
