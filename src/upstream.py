from __future__ import annotations

import json
import re

from src.core import prog_name
from src.header import PROMPT_HEADER, RULES_HEADER, VAR_NAME_PATTERN


_FRAGMENT_GROUPS = {
    "rule": "rules",
    "cmd": "cmds",
    "file": "files",
    "prompt": "prompts",
}
_HEADER_RE = re.compile(r"([A-Za-z][A-Za-z0-9_.-]*):(?:[ \t]+(.*)|[ \t]*)")
_PRODUCER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*(?:/[A-Za-z_][A-Za-z0-9_-]*)?")
_VAR_RE = re.compile(VAR_NAME_PATTERN)


def _normalize_producer(tok: str) -> tuple[str, str]:
    p_norm = tok.lower().replace("-", "_").replace("/", ".")
    p_short = p_norm.rsplit(".", 1)[-1]
    return p_norm, p_short


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
        return bool(self.prompt) or any(meta.get("kind") == "prompt" for meta, _ in self.fragments)


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
    """Group fragments into rules, cmds, files, and prompts; also return unknown kinds."""
    groups: dict[str, list[tuple[dict[str, object], str]]] = {
        "rules": [],
        "cmds": [],
        "files": [],
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

    ambiguous_shorts: set[str] = set()
    if preamble_items and (idx == len(lines) or not lines[idx].strip()):
        seen_producers: set[str] = set()
        short_to_producers: dict[str, set[str]] = {}
        current_producer: str | None = None
        raw_vars: list[tuple[str | None, str, str]] = []

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
                    p_norm, p_short = _normalize_producer(tok)
                    if p_norm in seen_producers:
                        raise SystemExit(f"{prog}: duplicate Bundle-Name producer {p_norm!r} in pipeline")
                    seen_producers.add(p_norm)
                    short_to_producers.setdefault(p_short, set()).add(p_norm)
                    result.producers.append(p_norm)
                    result.bundle_name = p_norm
                    current_producer = p_norm
            elif kl.startswith("bundle-"):
                continue
            elif v:
                raw_vars.append((current_producer, kl, v))

        if result.command:
            cmd_producers: list[str] = []
            for seg in result.command.split("|"):
                seg_tokens = seg.strip().split()
                if seg_tokens:
                    exe = seg_tokens[0].rsplit("/", 1)[-1].lower().replace("-", "_")
                    cmd_producers.append(exe)
            if len(cmd_producers) > 1 and len(cmd_producers) != len(set(cmd_producers)):
                for p in cmd_producers:
                    if cmd_producers.count(p) > 1:
                        if p in seen_producers:
                            raise SystemExit(f"{prog}: duplicate Bundle-Name producer {p!r} in pipeline")
                        owners = short_to_producers.get(p, set())
                        if len(owners) == 1:
                            only_prod = next(iter(owners))
                            raise SystemExit(f"{prog}: duplicate Bundle-Name producer {only_prod!r} in pipeline")

        # Also inspect pre-namespaced headers (<owner>.<repo>.<key> or <repo>.<key>)
        for assoc_prod, kl, _v in raw_vars:
            if "." in kl:
                parts = [p.replace("-", "_") for p in kl.split(".")]
                if len(parts) >= 3:
                    ns_full = f"{parts[0]}.{parts[1]}"
                    ns_short = parts[1]
                    if ns_full in seen_producers:
                        raise SystemExit(f"{prog}: duplicate Bundle-Name producer {ns_full!r} in pipeline")
                    short_to_producers.setdefault(ns_short, set()).add(ns_full)
                else:
                    ns_short = parts[0]
                    if ns_short in seen_producers:
                        raise SystemExit(f"{prog}: duplicate Bundle-Name producer {ns_short!r} in pipeline")
                    if assoc_prod and assoc_prod.rsplit(".", 1)[-1] == ns_short and ns_short in short_to_producers:
                        if len(short_to_producers[ns_short]) == 1 and assoc_prod in short_to_producers[ns_short]:
                            raise SystemExit(f"{prog}: duplicate Bundle-Name producer {assoc_prod!r} in pipeline")

        ambiguous_shorts = {s for s, owners in short_to_producers.items() if len(owners) > 1}

        for assoc_prod, kl, v in raw_vars:
            prod = assoc_prod or result.bundle_name
            if "." in kl:
                parts = [p.replace("-", "_") for p in kl.split(".")]
                if len(parts) >= 3:
                    ns_full = f"{parts[0]}.{parts[1]}"
                    ns_short = parts[1]
                    rest = ".".join(parts[2:])
                    full_var = f"{ns_full}.{rest}"
                    if _VAR_RE.fullmatch(full_var):
                        result.vars[full_var] = v
                    if ns_short not in ambiguous_shorts:
                        short_var = f"{ns_short}.{rest}"
                        if _VAR_RE.fullmatch(short_var):
                            result.vars[short_var] = v
                else:
                    ns = parts[0]
                    rest = ".".join(parts[1:])
                    if ns not in ambiguous_shorts:
                        var_name = f"{ns}.{rest}"
                        if _VAR_RE.fullmatch(var_name):
                            result.vars[var_name] = v
            else:
                key_norm = kl.replace("-", "_")
                if prod:
                    full_var = f"{prod}.{key_norm}"
                    if _VAR_RE.fullmatch(full_var):
                        result.vars[full_var] = v
                    p_short = prod.rsplit(".", 1)[-1]
                    if p_short != prod and p_short not in ambiguous_shorts:
                        short_var = f"{p_short}.{key_norm}"
                        if _VAR_RE.fullmatch(short_var):
                            result.vars[short_var] = v
                else:
                    if _VAR_RE.fullmatch(key_norm):
                        result.vars[key_norm] = v

        raw = "\n".join(lines[idx:]).strip()
        lines = raw.splitlines()

    if result.boundary:
        result.fragments, result.prompt = extract_fragments(raw, result.boundary)
        return result
    if len(lines) == 1 and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", lines[0].strip()):
        token = lines[0].strip()
        if result.bundle_name:
            result.vars.setdefault(f"{result.bundle_name}.task", token)
            p_short = result.bundle_name.rsplit(".", 1)[-1]
            if p_short != result.bundle_name and p_short not in ambiguous_shorts:
                result.vars.setdefault(f"{p_short}.task", token)
        else:
            result.vars.setdefault("task", token)
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
