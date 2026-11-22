from __future__ import annotations

import json
import re

from src.core import prog_name
from src.header import PROMPT_HEADER, RULES_HEADER, VAR_NAME_PATTERN


PROMPT_KINDS = ("task", "context", "prompt")
_KIND_NORMALIZATION = {
    "rule": "rule",
    "cmd": "cmd",
    "file": "file",
    "include": "file",
    "prompt": "prompt",
    "task": "prompt",
    "context": "prompt",
}
_FRAGMENT_GROUPS = {
    "rule": "rules",
    "cmd": "cmds",
    "file": "files",
    "include": "files",
    "prompt": "prompts",
    "task": "prompts",
    "context": "prompts",
}
_HEADER_RE = re.compile(r"([A-Za-z][A-Za-z0-9_.-]*):(?:[ \t]+(.*)|[ \t]*)")
_PRODUCER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
_VAR_RE = re.compile(VAR_NAME_PATTERN)


class PipedInput:
    """Parsed stdin of an upstream command piped into the assembler."""

    def __init__(self) -> None:
        self.vars: dict[str, str] = {}
        self.prompt = ""
        self.workdir: str | None = None
        self.boundary: str | None = None
        self.command: str | None = None
        self.bundle_name: str | None = None
        self.producers: list[str] = []
        self.fragments: list[tuple[dict[str, object], str]] = []

    @property
    def has_prompt(self) -> bool:
        return bool(self.prompt) or any(meta.get("kind") in PROMPT_KINDS for meta, _ in self.fragments)


def _normalize_fragment_meta(meta: dict[str, object]) -> dict[str, object]:
    raw_kind = str(meta.get("kind") or "")
    norm_kind = _KIND_NORMALIZATION.get(raw_kind)
    if norm_kind is not None and norm_kind != raw_kind:
        return {**meta, "kind": norm_kind}
    return meta


def _parse_part_line(line: str, prefix: str) -> dict[str, object] | None:
    if not (line.startswith(prefix) and line.endswith(" -->")):
        return None
    try:
        meta = json.loads(line[len(prefix) : -len(" -->")])
    except ValueError:
        return None
    return _normalize_fragment_meta(meta) if isinstance(meta, dict) else None


def extract_fragments(text: str, nonce: str) -> tuple[list[tuple[dict[str, object], str]], str]:
    """Split upstream bundle text into (meta, content) fragments and leftover prose."""
    part_prefix = f"<!-- bundle:{nonce}:part "
    end_line = f"<!-- bundle:{nonce}:end -->"
    fragments: list[tuple[dict[str, object], str]] = []
    leftover: list[str] = []
    active: dict[str, object] | None = None
    buf: list[str] = []
    for line in text.splitlines():
        if active is not None:
            if line == end_line:
                fragments.append((active, "\n".join(buf)))
                active = None
            else:
                buf.append(line)
            continue
        meta = _parse_part_line(line, part_prefix)
        if meta is not None:
            active = meta
            buf = []
        elif line.strip() not in (RULES_HEADER, PROMPT_HEADER):
            leftover.append(line)
    if active is not None:
        raise SystemExit(f"{prog_name()}: unclosed upstream fragment marker on stdin")
    return fragments, "\n".join(leftover).strip()


def group_fragments(
    fragments: list[tuple[dict[str, object], str]],
) -> tuple[dict[str, list[tuple[dict[str, object], str]]], list[str]]:
    """Group fragments into rules, cmds, files, and prompts; also return unknown kinds."""
    groups: dict[str, list[tuple[dict[str, object], str]]] = {
        "rules": [],
        "cmds": [],
        "files": [],
        "prompts": [],
    }
    unknown: list[str] = []
    for meta, content in fragments:
        norm_meta = _normalize_fragment_meta(meta)
        group = _FRAGMENT_GROUPS.get(str(norm_meta.get("kind")))
        if group is None:
            unknown.append(str(meta.get("kind")))
        else:
            groups[group].append((norm_meta, content))
    return groups, unknown


def parse_stdin_pipe(stdin_text: str) -> PipedInput:
    prog = prog_name()
    result = PipedInput()
    raw = stdin_text.strip()
    if not raw:
        return result
    lines = raw.splitlines()
    preamble_items: list[tuple[str, str]] = []
    idx = 0
    while idx < len(lines):
        ln = lines[idx]
        if not ln.strip():
            break
        hm = _HEADER_RE.fullmatch(ln)
        if not hm:
            break
        preamble_items.append((hm.group(1), hm.group(2).strip() if hm.group(2) is not None else ""))
        idx += 1

    if preamble_items and (idx == len(lines) or not lines[idx].strip()):
        seen_producers: set[str] = set()
        raw_vars: list[tuple[str, str]] = []
        for k, v in preamble_items:
            kl = k.lower()
            if kl == "workdir":
                result.workdir = v
            elif kl == "bundle-boundary":
                result.boundary = v or None
            elif kl == "bundle-command":
                result.command = v or None
            elif kl == "bundle-name":
                tokens = [tok for tok in re.split(r"[\s,|]+", v.strip()) if tok]
                if not tokens:
                    raise SystemExit(f"{prog}: empty Bundle-Name header on stdin")
                for tok in tokens:
                    if not _PRODUCER_RE.fullmatch(tok):
                        raise SystemExit(f"{prog}: invalid Bundle-Name producer {tok!r} on stdin")
                    p_norm = tok.lower().replace("-", "_")
                    if p_norm in seen_producers:
                        raise SystemExit(f"{prog}: duplicate Bundle-Name producer {p_norm!r} in pipeline")
                    seen_producers.add(p_norm)
                    result.producers.append(p_norm)
                    result.bundle_name = p_norm
            elif kl.startswith("bundle-"):
                continue
            elif v:
                raw_vars.append((kl, v))

        if result.command:
            cmd_producers: list[str] = []
            for seg in result.command.split("|"):
                seg_tokens = seg.strip().split()
                if seg_tokens:
                    exe = seg_tokens[0].rsplit("/", 1)[-1].lower().replace("-", "_")
                    cmd_producers.append(exe)
            if len(cmd_producers) > 1 and len(cmd_producers) != len(set(cmd_producers)):
                for p in cmd_producers:
                    if cmd_producers.count(p) > 1 and p in seen_producers:
                        raise SystemExit(f"{prog}: duplicate Bundle-Name producer {p!r} in pipeline")

        for kl, v in raw_vars:
            if "." in kl:
                parts = kl.split(".")
                ns = parts[0].replace("-", "_")
                rest = ".".join(p.replace("-", "_") for p in parts[1:])
                if result.bundle_name and ns == result.bundle_name:
                    raise SystemExit(f"{prog}: duplicate Bundle-Name producer {ns!r} in pipeline")
                var_name = f"{ns}.{rest}"
            else:
                key_norm = kl.replace("-", "_")
                var_name = f"{result.bundle_name}.{key_norm}" if result.bundle_name else key_norm
            if _VAR_RE.fullmatch(var_name):
                result.vars[var_name] = v

        raw = "\n".join(lines[idx:]).strip()
        lines = raw.splitlines()

    if result.boundary:
        result.fragments, result.prompt = extract_fragments(raw, result.boundary)
        return result
    if len(lines) == 1 and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", lines[0].strip()):
        task_key = f"{result.bundle_name}.task" if result.bundle_name else "task"
        result.vars.setdefault(task_key, lines[0].strip())
        return result
    result.prompt = raw
    return result


def meta_chain(meta: dict[str, object]) -> list[str]:
    raw = meta.get("chain")
    return [str(c) for c in raw] if isinstance(raw, list) else []


def strip_section_header(content: str, header: str) -> str:
    """Drop a leading section header line from fragment content."""
    if content == header:
        return ""
    prefix = header + "\n"
    return content[len(prefix) :] if content.startswith(prefix) else content
