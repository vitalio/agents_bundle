import os
import sys
import textwrap
from pathlib import Path

from src.header import (
    DEFAULT_RULES_PKG,
    EMBEDDED_RULE_AGENTS_BUNDLE,
    HELP_GAP,
    HELP_INDENT,
    HELP_MAX_WIDTH,
    HELP_PROSE_WIDTH,
    HELP_SECTIONS,
)


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


def render_help_section(title: str, rows) -> str:
    col = HELP_INDENT + max(len(left) for left, _ in rows) + HELP_GAP
    width = max(min(HELP_PROSE_WIDTH, HELP_MAX_WIDTH - col), 20)
    lines = [title]
    for left, right in rows:
        wrapped = textwrap.wrap(right, width=width, break_long_words=True, break_on_hyphens=False)
        lines.append(" " * HELP_INDENT + left.ljust(col - HELP_INDENT) + wrapped[0])
        lines.extend(" " * col + part for part in wrapped[1:])
    return "\n".join(lines)


def usage_text() -> str:
    fields = {"prog": prog_name(), "default_pkg": DEFAULT_RULES_PKG, "cache_dir": cache_dir_path()}
    blocks = []
    for title, rows in HELP_SECTIONS:
        expanded = [(left.format(**fields), right.format(**fields)) for left, right in rows]
        blocks.append(render_help_section(title, expanded))
    return "\n\n".join(blocks) + "\n"


def embedded_rule_text() -> str:
    if EMBEDDED_RULE_AGENTS_BUNDLE:
        return EMBEDDED_RULE_AGENTS_BUNDLE
    src_rule = Path(__file__).resolve().parent.parent / "agents" / "agents_bundle.md"
    if not src_rule.is_file():
        raise SystemExit(f"{prog_name()}: embedded rule not found: {src_rule}")
    return src_rule.read_text(encoding="utf-8")
