#!/usr/bin/env python3
# agents_bundle-repo: vitalio/agents_bundle
"""Usage:
  {prog} [k=v ...] [-p TEXT] [FILE ...]       Build context bundle from .agents_bundle to stdout (stdin: Key: Value preamble, task ID, or prompt; sets piped=1 on prompt; empty piped stdin exits 2)
  {prog} ruleset <pkg>:<name> [-excl] [k=v]   Render a ruleset to stdout
  {prog} rule <pkg>:<name> [k=v]              Render a single rule to stdout
  {prog} bundle <pkg>[:<name>] [k=v]          Render a bundle to stdout without .agents_bundle (reads no stdin; honors -C, -p, --plain, -v, --refresh)
  {prog} --list | -l [pkg]                    List rulesets, rules, bundles, and built-in variables (default: {default_pkg})
  {prog} --update-cache                       Refresh cached git packages and URL files in {cache_dir}
  {prog} --init [--force]                     Create a starter .agents_bundle in the current directory
  {prog} --tree [DIR] [opts]                  Print token-budgeted repository file tree to stdout
  {prog} --update [--force]                   Self-update {prog} from GitHub (vitalio/agents_bundle)
  {prog} --check-update                       Check if a newer version is available
  {prog} -V | --version                       Print version and exit 0
  {prog} -h | --help                          Print this usage and exit 0

Options:
  -p, --prompt TEXT                           Append prompt text to the Prompt section
  -C, --dir DIR                               Set working directory (default: piped Workdir: or cwd)
  -v, --verbose                               Include rule provenance trace comments
  --plain                                     Omit transport Bundle-* headers and JSON fragment markers
  --refresh                                   Re-fetch each remote package or URL at most once per run
  -x, --exclude DIR                           Exclude directory name in --tree (-x/--exclude DIR, repeatable)
  --max-lines N                               Maximum output lines for --tree (default: 160)
  --max-tokens N                              Approximate token budget for --tree (default: 1600)
  --force                                     Overwrite existing .agents_bundle (--init) or force reinstall (--update)

Bundle Output Protocol:
  Headers                                     Emits Bundle-Command, Bundle-Boundary: <nonce>, Bundle-Expose: Role, Task, Title (extensible via 'expose' or AGENTS_BUNDLE_EXPOSE), variable headers, and Workdir: <path>
  Fragment markers                            Wraps rules, commands, included files, and prompts in <!-- bundle:<nonce>:part <json> --> and <!-- bundle:<nonce>:end --> (fields: kind, id/name, chain, rc, ms)
  Plain mode                                  --plain or AGENTS_BUNDLE_PLAIN=1 omits transport Bundle-* headers and fragment markers

Environment:
  AGENTS_BUNDLE_VARS                          Default key=val pairs (overridden by CLI key=val)
  AGENTS_BUNDLE_EXPOSE                        Extra header keys to add to Bundle-Expose
  AGENTS_BUNDLE_PLAIN                         Set to 1 to omit transport Bundle-* headers and fragment markers
  AGENTS_BUNDLE_LOCAL_PKG_DIR                 Use a local package checkout instead of the cache
  AGENTS_BUNDLE_CACHE_DIR                     Override the cache directory
"""
from __future__ import annotations

if __doc__ is None:
    raise SystemExit("missing usage documentation")

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
import time
from pathlib import Path

VERSION = "__VERSION__"
REPO_MARKER = "agents_bundle-repo: vitalio/agents_bundle"
DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/vitalio/agents_bundle/main/agents_bundle"
SPEC_FILE_NAME = ".agents_bundle"
DEFAULT_RULES_PKG = "vitalio/agents-rules"
USAGE_TEMPLATE = __doc__
