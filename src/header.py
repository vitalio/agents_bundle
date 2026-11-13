#!/usr/bin/env python3
# agents_bundle-repo: vitalio/agents_bundle
"""Usage:
  {prog} [-p TEXT] [FILE ...]       Build context bundle from .agents_bundle to stdout
                                      Opts: -p/--prompt TEXT, -C/--dir DIR
  {prog} --init [--force]           Create a starter .agents_bundle in the current directory
  {prog} --tree [DIR] [opts]        Print token-budgeted repository file tree to stdout
                                      Opts: --max-lines N (120), --max-tokens N (1200)
  {prog} --agents                   Print Markdown instructions for AI agents
  {prog} --update [--force]         Self-update {prog} from GitHub (vitalio/agents_bundle)
  {prog} --check-update             Check if a newer version is available
  {prog} -V | --version             Print version and exit 0
  {prog} -h | --help                Print this usage and exit 0
"""
from __future__ import annotations

if __doc__ is None:
    raise SystemExit("missing usage documentation")

import ast
import math
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

VERSION = "0.1.0"
REPO_MARKER = "agents_bundle-repo: vitalio/agents_bundle"
DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/vitalio/agents_bundle/main/agents_bundle"
SPEC_FILE_NAME = ".agents_bundle"
