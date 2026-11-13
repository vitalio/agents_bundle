#!/usr/bin/env python3
# agents_bundle-repo: vitalio/agents_bundle
"""Usage:
  {prog} [-p TEXT] [FILE ...]                 Build context bundle from .agents_bundle to stdout
                                                Opts: -p/--prompt TEXT, -C/--dir DIR, -v/--verbose, --refresh
  {prog} preset <pkg>:<name> [-excl] [k=v]    Render a preset to stdout
  {prog} rule <pkg>:<name> [k=v]              Render a single rule to stdout
  {prog} --list | -l [pkg]                    List presets, rules, and built-in variables (default: {default_pkg})
  {prog} --update-cache                       Refresh cached rule packages in {cache_dir}
  {prog} --init [--force]                     Create a starter .agents_bundle in the current directory
  {prog} --tree [DIR] [opts]                  Print token-budgeted repository file tree to stdout
                                                Opts: -x/--exclude DIR, --max-lines N (160), --max-tokens N (1600)
  {prog} --update [--force]                   Self-update {prog} from GitHub (vitalio/agents_bundle)
  {prog} --check-update                       Check if a newer version is available
  {prog} -V | --version                       Print version and exit 0
  {prog} -h | --help                          Print this usage and exit 0
"""
from __future__ import annotations

if __doc__ is None:
    raise SystemExit("missing usage documentation")

import ast
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

VERSION = "0.5.0"
REPO_MARKER = "agents_bundle-repo: vitalio/agents_bundle"
DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/vitalio/agents_bundle/main/agents_bundle"
SPEC_FILE_NAME = ".agents_bundle"
DEFAULT_RULES_PKG = "vitalio/agents_rules"
