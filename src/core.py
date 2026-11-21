import os
import sys
from pathlib import Path

from src.header import DEFAULT_RULES_PKG, EMBEDDED_RULE_AGENTS_BUNDLE, USAGE_TEMPLATE


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
    return USAGE_TEMPLATE.format(
        prog=prog_name(),
        default_pkg=DEFAULT_RULES_PKG,
        cache_dir=cache_dir_path(),
    )


def embedded_rule_text() -> str:
    if EMBEDDED_RULE_AGENTS_BUNDLE:
        return EMBEDDED_RULE_AGENTS_BUNDLE
    src_rule = Path(__file__).resolve().parent.parent / "agents" / "agents_bundle.md"
    if not src_rule.is_file():
        raise SystemExit(f"{prog_name()}: embedded rule not found: {src_rule}")
    return src_rule.read_text(encoding="utf-8")
