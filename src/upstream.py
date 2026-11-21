from __future__ import annotations

import json
import re

from src.core import prog_name
from src.header import PROMPT_HEADER, RULES_HEADER


PROMPT_KINDS = ("task", "context", "prompt")
_FRAGMENT_GROUPS = {
    "rule": "rules",
    "cmd": "cmds",
    "include": "includes",
    "file": "includes",
    "task": "prompts",
    "context": "prompts",
    "prompt": "prompts",
}
_HEADER_RE = re.compile(r"([A-Za-z][A-Za-z0-9_-]*):(?:[ \t]+(.*)|[ \t]*)")


class PipedInput:
    """Parsed stdin of an upstream command piped into the assembler."""

    def __init__(self) -> None:
        self.vars: dict[str, str] = {}
        self.prompt = ""
        self.workdir: str | None = None
        self.boundary: str | None = None
        self.command: str | None = None
        self.expose: list[str] = []
        self.hide: list[str] = []
        self.fragments: list[tuple[dict[str, object], str]] = []

    @property
    def has_prompt(self) -> bool:
        return bool(self.prompt) or any(meta.get("kind") in PROMPT_KINDS for meta, _ in self.fragments)


def _split_header_list(value: str) -> list[str]:
    return [tok for tok in re.split(r"[\s,]+", value.strip()) if tok]


def _parse_part_line(line: str, prefix: str) -> dict[str, object] | None:
    if not (line.startswith(prefix) and line.endswith(" -->")):
        return None
    try:
        meta = json.loads(line[len(prefix) : -len(" -->")])
    except ValueError:
        return None
    return meta if isinstance(meta, dict) else None


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
    """Group fragments into rules, cmds, includes, and prompts; also return unknown kinds."""
    groups: dict[str, list[tuple[dict[str, object], str]]] = {
        "rules": [],
        "cmds": [],
        "includes": [],
        "prompts": [],
    }
    unknown: list[str] = []
    for meta, content in fragments:
        group = _FRAGMENT_GROUPS.get(str(meta.get("kind")))
        if group is None:
            unknown.append(str(meta.get("kind")))
        else:
            groups[group].append((meta, content))
    return groups, unknown


def parse_stdin_pipe(stdin_text: str) -> PipedInput:
    result = PipedInput()
    raw = stdin_text.strip()
    if not raw:
        return result
    lines = raw.splitlines()
    preamble: dict[str, str] = {}
    idx = 0
    while idx < len(lines):
        ln = lines[idx]
        if not ln.strip():
            break
        hm = _HEADER_RE.fullmatch(ln)
        if not hm:
            break
        preamble[hm.group(1)] = hm.group(2).strip() if hm.group(2) is not None else ""
        idx += 1

    if preamble and (idx == len(lines) or not lines[idx].strip()):
        for k, v in preamble.items():
            kl = k.lower()
            if kl == "workdir":
                result.workdir = v
            elif kl == "bundle-boundary":
                result.boundary = v or None
            elif kl == "bundle-command":
                result.command = v or None
            elif kl == "bundle-expose":
                result.expose = _split_header_list(v)
            elif kl == "bundle-hide":
                result.hide = _split_header_list(v)
            elif kl.startswith("bundle-"):
                continue
            elif v:
                var_name = kl.replace("-", "_")
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", var_name):
                    result.vars[var_name] = v
        raw = "\n".join(lines[idx:]).strip()
        lines = raw.splitlines()

    if result.boundary:
        result.fragments, result.prompt = extract_fragments(raw, result.boundary)
        return result
    if len(lines) == 1 and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", lines[0].strip()):
        result.vars.setdefault("task", lines[0].strip())
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
