#!/usr/bin/env python3
"""Usage:
  python3 build.py            Build standalone ./agents_bundle from src/
  python3 build.py --check    Verify that ./agents_bundle is up to date with src/
  python3 build.py -h|--help  Print this usage and exit 0
"""
from __future__ import annotations

if __doc__ is None:
    raise SystemExit("missing usage documentation")

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
OUT_FILE = ROOT / "agents_bundle"

MODULE_ORDER = [
    "header.py",
    "core.py",
    "tree.py",
    "rules_engine.py",
    "includes.py",
    "upstream.py",
    "bundle.py",
    "cli.py",
]


def _import_aliases(node: ast.stmt) -> set[tuple[str, str, str | None]]:
    if isinstance(node, ast.Import):
        return {("", a.name, a.asname) for a in node.names}
    assert isinstance(node, ast.ImportFrom)
    return {(node.module or "", a.name, a.asname) for a in node.names}

def header_import_set(header_text: str) -> set[tuple[str, str, str | None]]:
    found: set[tuple[str, str, str | None]] = set()
    for node in ast.parse(header_text).body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found |= _import_aliases(node)
    return found

def strip_module_imports(
    name: str,
    text: str,
    header_imports: set[tuple[str, str, str | None]],
    order: list[str],
) -> str:
    """Drop top-level imports of a src module for the single-file build.

    Sibling imports (from src.<module> import ...) must point to an earlier
    module in order; other imports must be provided by src/header.py.
    """
    drop: list[tuple[int, int]] = []
    for node in ast.parse(text).body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        mod = node.module or "" if isinstance(node, ast.ImportFrom) else ""
        if mod.startswith("src."):
            dep = mod.split(".", 1)[1] + ".py"
            if dep not in order[: order.index(name)]:
                raise SystemExit(f"build.py: {name} imports {mod}, which must come earlier in MODULE_ORDER")
        elif mod != "__future__":
            missing = _import_aliases(node) - header_imports
            if missing:
                raise SystemExit(f"build.py: {name} imports {sorted(missing)} not provided by header.py")
        drop.append((node.lineno, node.end_lineno or node.lineno))
    kept = [ln for i, ln in enumerate(text.splitlines(), 1) if not any(a <= i <= b for a, b in drop)]
    return "\n".join(kept).lstrip("\n")

def assemble_source() -> str:
    ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    rule_text = (ROOT / "agents" / "agents_bundle.md").read_text(encoding="utf-8")
    texts = {m: (SRC_DIR / m).read_text(encoding="utf-8").rstrip() for m in MODULE_ORDER}
    header_imports = header_import_set(texts["header.py"])
    chunks: list[str] = []
    for m in MODULE_ORDER:
        txt = texts[m]
        if m == "header.py":
            txt = txt.replace('VERSION = "__VERSION__"', f'VERSION = "{ver}"')
            marker = 'EMBEDDED_RULE_AGENTS_BUNDLE = ""'
            if txt.count(marker) != 1:
                raise SystemExit("build.py: embedded rule placeholder not found in header.py")
            txt = txt.replace(marker, f"EMBEDDED_RULE_AGENTS_BUNDLE = {rule_text!r}")
        else:
            txt = strip_module_imports(m, txt, header_imports, MODULE_ORDER)
        chunks.append(txt.rstrip())
    source = "\n\n\n".join(chunks) + "\n"
    ast.parse(source)
    return source


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        sys.stdout.write(__doc__)
        return 0
    expected = assemble_source()
    if "--check" in args:
        if not OUT_FILE.is_file() or OUT_FILE.read_text(encoding="utf-8") != expected:
            sys.stderr.write("build.py: agents_bundle is out of sync with src/ (run 'python3 build.py')\n")
            return 1
        return 0
    if args:
        sys.stderr.write(__doc__)
        return 2
    OUT_FILE.write_text(expected, encoding="utf-8")
    OUT_FILE.chmod(0o755)
    sys.stdout.write(f"build.py: built {OUT_FILE} ({len(expected.splitlines())} lines)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
