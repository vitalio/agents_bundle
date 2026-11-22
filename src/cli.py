from __future__ import annotations

import ast
import os
import re
import sys
import tempfile
import time
from pathlib import Path

from src.header import DEFAULT_RULES_PKG, DEFAULT_UPDATE_URL, REPO_MARKER, VERSION
from src.core import prog_name, usage_text
from src.tree import cmd_tree
from src.rules_engine import (
    _parse_directive_tokens,
    _parse_rule_directive_tokens,
    cmd_list_rules,
    cmd_update_cache,
    collect_directive_items,
    env_vars,
    format_collected_rules,
    render_directive,
)
from src.bundle import cmd_bundle, cmd_init


def parse_version_from_source(source: str) -> str | None:
    m = re.search(r'^VERSION\s*=\s*["\x27]([^"\x27]+)["\x27]', source, flags=re.MULTILINE)
    return m.group(1) if m else None


def version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.split(r"[^0-9]+", v) if p)


def fetch_remote_script(url: str | None = None) -> str:
    import urllib.request

    target_url = url or os.environ.get("AGENTS_BUNDLE_UPDATE_URL") or DEFAULT_UPDATE_URL
    if target_url.startswith(("http://", "https://")) and "?" not in target_url:
        target_url = f"{target_url}?t={int(time.time())}"
    req = urllib.request.Request(
        target_url,
        headers={"User-Agent": f"agents_bundle/{VERSION}", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read().decode("utf-8")
    if REPO_MARKER not in data:
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
    dest = Path(__file__).resolve()
    try:
        remote_src = fetch_remote_script(url)
    except Exception as exc:
        sys.stderr.write(f"{prog}: update failed: {exc}\n")
        return 1
    remote_ver = parse_version_from_source(remote_src) or "unknown"
    if not force and version_tuple(remote_ver) <= version_tuple(VERSION):
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
    sys.stdout.write(f"{prog}: updated {VERSION} -> {remote_ver} ({dest})\n")
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
    if args and args[0] in ("ruleset", "rule"):
        kind = args[0]
        refresh = "--refresh" in args[1:]
        verbose = "-v" in args[1:] or "--verbose" in args[1:]
        rest_tokens = [a for a in args[1:] if a not in ("--refresh", "-v", "--verbose")]
        if kind == "rule":
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
        else:
            target, excls, vmap = _parse_directive_tokens(rest_tokens, prog)
            merged_vmap = {**env_vars(prog), **vmap}
            out = render_directive(kind, target, excludes=excls, cli_vars=merged_vmap, refresh=refresh, verbose=verbose)
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
    if args and args[0] == "--tree":
        return cmd_tree(args[1:])
    if args and args[0] == "--check-update":
        return cmd_check_update()
    if args and args[0] in ("--update", "--self-update"):
        return cmd_update(force="--force" in args[1:])
    return cmd_bundle(args)


if __name__ == "__main__":
    raise SystemExit(main())
