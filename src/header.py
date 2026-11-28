#!/usr/bin/env python3
# context-bundle-repo: vitalio/context-bundle
"""Context bundler and rules engine."""
from __future__ import annotations

import ast
import fnmatch
import hashlib
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
REPO_MARKER = "context-bundle-repo: vitalio/context-bundle"
DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/vitalio/context-bundle/main/context"
SPEC_FILE_NAME = ".context.bundle"
PRODUCER_NAME = "vitalio/context-bundle"
EMBEDDED_RULE_CONTEXT = ""
EMBEDDED_RULE_NAME = "context"
EMBEDDED_RULE_ID = "vitalio/context-bundle:context"
PROTOCOL_VERSION = "1"
RULES_HEADER = "===== Rules ====="
PROMPT_HEADER = "===== Prompt ====="
VAR_NAME_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
HELP_MAX_WIDTH = 100
HELP_PROSE_WIDTH = 80
HELP_MAX_LEFT = 32
HELP_INDENT = 2
HELP_GAP = 2
HELP_USAGE = (
    "{prog} [k=v ...] [-p TEXT] [FILE ...]",
    "{prog} <command|flag> [args] [opts]",
)
HELP_SECTIONS = (
    (
        "Commands:",
        (
            (
                "[k=v ...] [FILE ...]",
                "Build context bundle from .context.bundle to stdout (stdin: "
                "Key: Value preamble, task ID, or prompt; sets piped=1 on prompt; empty piped "
                "stdin exits 2)",
            ),
            (
                "bundle <pkg>[:<name>] [k=v]",
                "Render a bundle from agents/ without .context.bundle (reads no stdin; "
                "honors -C, -p, --plain, -v, --refresh)",
            ),
            (
                "rule <pkg>[:<name...>] [k=v]",
                "Render one or more rules from agents/ (<owner>/<repo>[@ref][:<name|path>], "
                "./path, or URL) to stdout",
            ),
            (
                "--list | -l [pkg]",
                "List bundles, rules, and built-in variables (default: local agents/ and .context.bundle)",
            ),
            ("--update-cache", "Refresh cached git packages and URL files in {cache_dir}"),
            ("--init [--force]", "Create a starter .context.bundle in the current directory"),
            (
                "--trust [opts]",
                "Trust current .context.bundle or revoke/list entries in {trust_file} "
                "(options: [DIR], --revoke, --list, -C DIR)",
            ),
            ("--tree [DIR] [opts]", "Print token-budgeted repository file tree to stdout"),
            (
                "--update [--check | --force]",
                "Self-update {prog} from GitHub (vitalio/context-bundle) or check for updates",
            ),
            ("--uninstall", "Remove installed {prog} binary and package cache ({cache_dir})"),
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
            ("--check", "Check if a newer version is available without installing (with --update)"),
            (
                "--force",
                "Overwrite existing .context.bundle (--init) or force reinstall (--update)",
            ),
            ("--revoke", "Revoke trust for current .context.bundle (with --trust)"),
            ("-l, --list", "List bundles/rules, or list trusted specs (with --trust)"),
            ("-V, --version", "Print version and exit 0"),
            ("-h, --help", "Print this usage and exit 0"),
        ),
    ),
    (
        "Bundle Output Protocol:",
        (
            (
                "Headers",
                "Emits Bundle-Command, Bundle-Name: vitalio/context-bundle, "
                "Bundle-Boundary: <nonce>, Bundle-Protocol: 1, exported Key: Value variable "
                "headers (via 'export'), and Workdir: <path>",
            ),
            (
                "Fragment markers",
                "Wraps rules, files, commands, and prompts in "
                "<!-- bundle:<nonce>:part <json> --> and <!-- bundle:<nonce>:end --> "
                "(kinds: rule, file, cmd, prompt; fields: kind, id/name, chain, rc, ms)",
            ),
            (
                "Plain mode",
                "--plain or CONTEXT_BUNDLE_PLAIN=1 omits transport Bundle-* headers and "
                "fragment markers",
            ),
            (
                "Piped bundles",
                "Piped stdin with Bundle-Boundary is unpacked: Bundle-Name: <producer> "
                "namespaces upstream headers as <owner>.<repo>.<key> and unambiguous "
                "<repo>.<key> (rejecting duplicate producers); upstream rule, file, cmd, and "
                "prompt fragments are merged and re-wrapped; Bundle-Command is chained with ' | '",
            ),
        ),
    ),
    (
        "Environment:",
        (
            ("CONTEXT_BUNDLE_VARS", "Default key=val pairs (overridden by CLI key=val)"),
            (
                "CONTEXT_BUNDLE_PLAIN",
                "Set to 1 to omit transport Bundle-* headers and fragment markers",
            ),
            (
                "CONTEXT_BUNDLE_LOCAL_PKG_DIR",
                "Use a local package checkout instead of the cache",
            ),
            ("CONTEXT_BUNDLE_CACHE_DIR", "Override the cache directory"),
            ("XDG_STATE_HOME", "Base directory for context-bundle/trusted.json (default: ~/.local/state)"),
            ("CONTEXT_BUNDLE_SHELL", "Override the shell executable used for cmd directives"),
            ("CONTEXT_BUNDLE_UPDATE_URL", "Override the remote script URL for --update"),
        ),
    ),
)
