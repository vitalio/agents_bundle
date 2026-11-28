from __future__ import annotations

import os
import shutil
import sys
import textwrap
from pathlib import Path

from src.header import (
    DEFAULT_RULES_PKG,
    EMBEDDED_RULE_CONTEXT,
    HELP_GAP,
    HELP_INDENT,
    HELP_MAX_LEFT,
    HELP_MAX_WIDTH,
    HELP_PROSE_WIDTH,
    HELP_SECTIONS,
    HELP_USAGE,
)

_OBSOLETE_VITALIO_PKGS = ("agents_bundle", "run_block", "todo_md")


def prog_name() -> str:
    raw = Path(sys.argv[0]).name if sys.argv and sys.argv[0] else "context"
    for suf in (".py",):
        if raw.lower().endswith(suf) and len(raw) > len(suf):
            raw = raw[:-len(suf)]
            break
    return raw or "context"


def _migrate_and_prune_cache(base: Path) -> Path:
    target = base / "context-bundle"
    legacy = base / "agents_bundle"
    if not target.exists() and legacy.is_dir():
        try:
            os.replace(legacy, target)
        except OSError:
            pass
    if target.is_dir():
        vitalio_dir = target / "packages" / "vitalio"
        if vitalio_dir.is_dir():
            for name in _OBSOLETE_VITALIO_PKGS:
                obs = vitalio_dir / name
                if obs.exists():
                    shutil.rmtree(obs, ignore_errors=True)
    return target


def cache_dir_path() -> Path:
    env_c = os.environ.get("CONTEXT_BUNDLE_CACHE_DIR")
    if env_c:
        target = Path(env_c).expanduser()
        if target.is_dir():
            vitalio_dir = target / "packages" / "vitalio"
            if vitalio_dir.is_dir():
                for name in _OBSOLETE_VITALIO_PKGS:
                    obs = vitalio_dir / name
                    if obs.exists():
                        shutil.rmtree(obs, ignore_errors=True)
        return target
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else (Path.home() / ".cache")
    return _migrate_and_prune_cache(base)


def state_dir_path() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME", "").strip()
    base = Path(xdg).expanduser() if xdg else (Path.home() / ".local" / "state")
    return base / "context-bundle"


def trust_file_path() -> Path:
    return state_dir_path() / "trusted.json"


def render_help_section(title: str, rows, col: int | None = None) -> str:
    max_col = HELP_INDENT + HELP_MAX_LEFT + HELP_GAP
    if col is None:
        max_left = max((min(len(left), HELP_MAX_LEFT) for left, _ in rows), default=0)
        col = HELP_INDENT + max_left + HELP_GAP
    else:
        col = min(col, max_col)
    width = max(min(HELP_PROSE_WIDTH, HELP_MAX_WIDTH - col), 20)
    max_inline_left = col - HELP_INDENT - HELP_GAP
    left_wrap_width = max(HELP_MAX_WIDTH - HELP_INDENT, 20)
    lines = [title]
    for left, right in rows:
        wrapped = textwrap.wrap(right, width=width, break_long_words=True, break_on_hyphens=False) or [""]
        if len(left) <= max_inline_left:
            lines.append(" " * HELP_INDENT + left.ljust(col - HELP_INDENT) + wrapped[0])
            lines.extend(" " * col + part for part in wrapped[1:])
        else:
            left_lines = textwrap.wrap(
                left,
                width=left_wrap_width,
                break_long_words=True,
                break_on_hyphens=False,
            ) or [left]
            lines.extend(" " * HELP_INDENT + lpart for lpart in left_lines)
            lines.extend(" " * col + part for part in wrapped)
    return "\n".join(lines)


def usage_text() -> str:
    fields = {
        "prog": prog_name(),
        "default_pkg": DEFAULT_RULES_PKG,
        "cache_dir": cache_dir_path(),
        "trust_file": trust_file_path(),
    }
    usage_wrap_width = max(HELP_MAX_WIDTH - HELP_INDENT, 20)
    usage_lines = ["Usage:"]
    for tmpl in HELP_USAGE:
        rendered = tmpl.format(**fields)
        if len(rendered) <= usage_wrap_width:
            usage_lines.append(" " * HELP_INDENT + rendered)
        else:
            wrapped_u = textwrap.wrap(
                rendered,
                width=usage_wrap_width,
                subsequent_indent=" " * HELP_INDENT,
                break_long_words=True,
                break_on_hyphens=False,
            )
            usage_lines.extend(" " * HELP_INDENT + part for part in wrapped_u)
    sections = [
        (title, [(left.format(**fields), right.format(**fields)) for left, right in rows])
        for title, rows in HELP_SECTIONS
    ]
    shared_col = (
        HELP_INDENT
        + max(min(len(left), HELP_MAX_LEFT) for _, rows in sections for left, _ in rows)
        + HELP_GAP
    )
    blocks = ["\n".join(usage_lines)]
    blocks.extend(render_help_section(title, rows, col=shared_col) for title, rows in sections)
    return "\n\n".join(blocks) + "\n"


def embedded_rule_text() -> str:
    if EMBEDDED_RULE_CONTEXT:
        return EMBEDDED_RULE_CONTEXT
    src_rule = Path(__file__).resolve().parent.parent / "agents" / "context.md"
    if not src_rule.is_file():
        raise SystemExit(f"{prog_name()}: embedded rule not found: {src_rule}")
    return src_rule.read_text(encoding="utf-8")
