from __future__ import annotations

import re
from pathlib import Path

from src.core import prog_name


_LINE_RANGE_RE = re.compile(r"^(.*?):(\d+)(?:-(\d+))?$")
_GLOB_SKIP_DIRS = {".git", "__pycache__"}
_HEAD_SLICE_RE = re.compile(r"^===== [$] sed -n '(\d+),(\d+)p' (.+) =====\Z")
_HEAD_CAT_RE = re.compile(r"^===== [$] cat (.+) =====\Z")


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _expand_include(
    wdir: Path,
    spec: str,
    root_dir: Path | None = None,
    bundle_label: str | None = None,
) -> list[tuple[Path, int | None, int | None]]:
    """Resolve an include item to (file, start, end) slices; empty when nothing matches.

    An existing file named exactly by spec is always included whole. Otherwise an
    optional :START-END (or :LINE) 1-based inclusive suffix is split off and the
    remaining path is used as a file or, when relative, as a glob pattern.
    """
    resolved_root = root_dir.resolve() if root_dir is not None else None

    def to_abs(raw: str) -> Path:
        p = Path(raw).expanduser()
        return p.resolve() if p.is_absolute() else (wdir / p).resolve()

    def ensure_within_root(candidate: Path) -> None:
        if resolved_root is not None and not _is_within_root(candidate, resolved_root):
            prog = prog_name()
            origin = f" in external bundle {bundle_label!r}" if bundle_label else ""
            raise SystemExit(
                f"{prog}: include path {spec!r}{origin} resolves outside repository root {resolved_root}"
            )

    whole = to_abs(spec)
    if whole.is_file():
        ensure_within_root(whole)
        return [(whole, None, None)]
    base, start, end = spec, None, None
    m = _LINE_RANGE_RE.match(spec)
    if m:
        base = m.group(1)
        start = int(m.group(2))
        end = int(m.group(3) or start)
        if start < 1 or end < start:
            return []
    if not base:
        return []
    expanded_base = Path(base).expanduser()
    if expanded_base.is_absolute() or not any(c in base for c in "*?["):
        target = to_abs(base)
        ensure_within_root(target)
        return [(target, start, end)] if target.is_file() else []
    if resolved_root is not None:
        prefix_parts: list[str] = []
        for part in Path(base).parts:
            if any(c in part for c in "*?["):
                break
            prefix_parts.append(part)
        if prefix_parts:
            ensure_within_root(to_abs(Path(*prefix_parts).as_posix()))
        if ".." in Path(base).parts:
            ensure_within_root(to_abs(base))
    try:
        matches = sorted(wdir.glob(base))
    except (ValueError, NotImplementedError):
        return []
    results: list[tuple[Path, int | None, int | None]] = []
    for p in matches:
        if p.is_file() and not _GLOB_SKIP_DIRS.intersection(p.parts[len(wdir.parts) :]):
            resolved_p = p.resolve()
            ensure_within_root(resolved_p)
            results.append((resolved_p, start, end))
    return results


def display_path(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


class IncludeSpan:
    """One included file region.

    A whole-file span carries whole_text (start and end are None); a slice span
    carries lines, mapping 1-based line numbers to text, for the inclusive
    requested range start..end.
    """

    def __init__(
        self,
        key: str,
        disp: str,
        start: int | None,
        end: int | None,
        lines: dict[int, str],
        chain: list[str],
        whole_text: str | None = None,
    ) -> None:
        self.key = key
        self.disp = disp
        self.start = start
        self.end = end
        self.lines = lines
        self.chain = chain
        self.whole_text = whole_text


def read_span(path: Path, disp: str, start: int | None, end: int | None, chain: list[str]) -> IncludeSpan:
    text = path.read_text(encoding="utf-8", errors="replace")
    if start is None or end is None:
        return IncludeSpan(str(path), disp, None, None, {}, list(chain), whole_text=text)
    text_lines = text.splitlines()
    picked = {n: text_lines[n - 1] for n in range(start, min(end, len(text_lines)) + 1)}
    return IncludeSpan(str(path), disp, start, end, picked, list(chain))


def _span_key(resolved: object, disp: str, wdir: Path) -> str:
    p = Path(str(resolved) if resolved else disp)
    return str((p if p.is_absolute() else wdir / p).resolve())


def span_from_fragment(meta: dict[str, object], content: str, wdir: Path) -> IncludeSpan:
    """Rebuild an include span from an upstream file fragment."""
    raw_chain = meta.get("chain")
    chain = [str(c) for c in raw_chain] if isinstance(raw_chain, list) else []
    name = str(meta.get("name") or "")
    head, _, body = content.partition("\n")
    resolved = meta.get("resolved_path")
    m_slice = _HEAD_SLICE_RE.match(head)
    if m_slice:
        start, end, disp = int(m_slice.group(1)), int(m_slice.group(2)), m_slice.group(3)
        lines = {start + i: ln for i, ln in enumerate(body.split("\n"))} if body else {}
        return IncludeSpan(_span_key(resolved, disp, wdir), disp, start, end, lines, chain)
    m_cat = _HEAD_CAT_RE.match(head)
    if m_cat:
        disp = m_cat.group(1)
        return IncludeSpan(_span_key(resolved, disp, wdir), disp, None, None, {}, chain, whole_text=body)
    return IncludeSpan(f"upstream:{name or content}", name or head, None, None, {}, chain, whole_text=content)


def _absorb(base: IncludeSpan, other: IncludeSpan) -> None:
    assert base.start is not None and base.end is not None
    assert other.start is not None and other.end is not None
    base.start = min(base.start, other.start)
    base.end = max(base.end, other.end)
    base.lines.update(other.lines)


def merge_spans(spans: list[IncludeSpan]) -> list[IncludeSpan]:
    """Deduplicate spans by line coverage, keeping first-occurrence order.

    A whole-file span absorbs every slice of the same file; overlapping or
    contained slices of one file are merged into a single slice.
    """
    out: list[IncludeSpan] = []
    for s in spans:
        same = [o for o in out if o.key == s.key]
        if any(o.whole_text is not None for o in same):
            continue
        if s.whole_text is not None:
            if same:
                s.chain = list(same[0].chain)
                out[out.index(same[0])] = s
                out = [o for o in out if o not in same[1:]]
            else:
                out.append(s)
            continue
        assert s.start is not None and s.end is not None
        hit = [o for o in same if o.start <= s.end and s.start <= o.end]
        if not hit:
            out.append(s)
            continue
        for o in (*hit[1:], s):
            _absorb(hit[0], o)
        out = [o for o in out if o not in hit[1:]]
    return out


def render_span(span: IncludeSpan) -> tuple[dict[str, object], str]:
    """Return (fragment meta, section text) for a span."""
    if span.whole_text is not None:
        name = span.disp
        heading = f"cat {span.disp}"
        content = span.whole_text.rstrip()
    else:
        name = f"{span.disp}:{span.start}-{span.end}"
        heading = f"sed -n '{span.start},{span.end}p' {span.disp}"
        content = "\n".join(span.lines[n] for n in sorted(span.lines)).rstrip()
    meta: dict[str, object] = {"kind": "file", "name": name, "chain": list(span.chain)}
    return meta, f"===== $ {heading} =====\n{content}"
