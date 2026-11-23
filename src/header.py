#!/usr/bin/env python3
# agents_bundle-repo: vitalio/agents_bundle
"""Context bundler and rules engine."""
from __future__ import annotations

import ast
import json
import math
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

VERSION = "__VERSION__"
REPO_MARKER = "agents_bundle-repo: vitalio/agents_bundle"
DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/vitalio/agents_bundle/main/agents_bundle"
SPEC_FILE_NAME = ".context.bundle"
LEGACY_SPEC_FILE_NAME = ".agents_bundle"
PRODUCER_NAME = "agents_bundle"
DEFAULT_RULES_PKG = "vitalio/agents-rules"
EMBEDDED_RULE_AGENTS_BUNDLE = ""
EMBEDDED_RULE_NAME = "agents_bundle"
LEGACY_RULE_ID = "vitalio/agents_bundle:agents_bundle"
PROTOCOL_VERSION = "1"
RULES_HEADER = "===== Rules ====="
PROMPT_HEADER = "===== Prompt ====="
VAR_NAME_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
HELP_MAX_WIDTH = 100
HELP_PROSE_WIDTH = 80
HELP_INDENT = 2
HELP_GAP = 2
HELP_SECTIONS = (
    (
        "Usage:",
        (
            (
                "{prog} [k=v ...] [-p TEXT] [FILE ...]",
                "Build context bundle from .context.bundle (or .agents_bundle) to stdout (stdin: "
                "Key: Value preamble, task ID, or prompt; sets piped=1 on prompt; empty piped "
                "stdin exits 2)",
            ),
            (
                "{prog} bundle <pkg>[:<name>] [k=v]",
                "Render a bundle from agents/ without .context.bundle (reads no stdin; "
                "honors -C, -p, --plain, -v, --refresh, allow=<cmd,...>)",
            ),
            (
                "{prog} rule <pkg>:<name...> [k=v]",
                "Render one or more rules from agents/ (<owner>/<repo>[@ref]:<name|path>, "
                "./path, or URL) to stdout",
            ),
            (
                "{prog} --list | -l [pkg]",
                "List bundles, rules, and built-in variables (default: {default_pkg})",
            ),
            ("{prog} --update-cache", "Refresh cached git packages and URL files in {cache_dir}"),
            ("{prog} --init [--force]", "Create a starter .context.bundle in the current directory"),
            ("{prog} --tree [DIR] [opts]", "Print token-budgeted repository file tree to stdout"),
            ("{prog} --update [--force]", "Self-update {prog} from GitHub (vitalio/agents_bundle)"),
            ("{prog} --check-update", "Check if a newer version is available"),
            ("{prog} -V | --version", "Print version and exit 0"),
            ("{prog} -h | --help", "Print this usage and exit 0"),
        ),
    ),
    (
        "Options:",
        (
            ("-p, --prompt TEXT", "Append prompt text to the Prompt section"),
            (
                "FILE ...",
                "Extra files to include; accepts globs (*, ?, [, **) and path:START-END or "
                "path:LINE slices (1-based, inclusive)",
            ),
            ("-C, --dir DIR", "Set working directory (default: piped Workdir: or cwd)"),
            ("-v, --verbose", "Include rule provenance trace comments"),
            ("--plain", "Omit transport Bundle-* headers and JSON fragment markers"),
            ("--refresh", "Re-fetch each remote package or URL at most once per run"),
            ("-x, --exclude DIR", "Exclude directory name in --tree (repeatable)"),
            ("--max-lines N", "Maximum output lines for --tree (default: 160)"),
            ("--max-tokens N", "Approximate token budget for --tree (default: 1600)"),
            (
                "--force",
                "Overwrite existing .context.bundle (--init) or force reinstall (--update)",
            ),
        ),
    ),
    (
        "Bundle Output Protocol:",
        (
            (
                "Headers",
                "Emits Bundle-Command, Bundle-Name: agents_bundle, Bundle-Boundary: <nonce>, "
                "Bundle-Protocol: 1, exported Key: Value variable headers (via 'export'), and "
                "Workdir: <path>",
            ),
            (
                "Fragment markers",
                "Wraps rules, files, commands, and prompts in "
                "<!-- bundle:<nonce>:part <json> --> and <!-- bundle:<nonce>:end --> "
                "(kinds: rule, file, cmd, prompt; fields: kind, id/name, chain, rc, ms)",
            ),
            (
                "Plain mode",
                "--plain or AGENTS_BUNDLE_PLAIN=1 omits transport Bundle-* headers and "
                "fragment markers",
            ),
            (
                "Piped bundles",
                "Piped stdin with Bundle-Boundary is unpacked: Bundle-Name: <producer> "
                "namespaces upstream headers as <producer>.<key_lower> (rejecting duplicate "
                "producers); upstream rule, file, cmd, and prompt fragments are merged and "
                "re-wrapped; Bundle-Command is chained with ' | '",
            ),
        ),
    ),
    (
        "Environment:",
        (
            ("AGENTS_BUNDLE_VARS", "Default key=val pairs (overridden by CLI key=val)"),
            (
                "AGENTS_BUNDLE_PLAIN",
                "Set to 1 to omit transport Bundle-* headers and fragment markers",
            ),
            (
                "AGENTS_BUNDLE_LOCAL_PKG_DIR",
                "Use a local package checkout instead of the cache",
            ),
            ("AGENTS_BUNDLE_CACHE_DIR", "Override the cache directory"),
        ),
    ),
)
