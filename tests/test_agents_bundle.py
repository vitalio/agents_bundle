#!/usr/bin/env python3
"""Tests for agents_bundle."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "agents_bundle"
BUILD_PY = ROOT / "build.py"
INSTALL_SH = ROOT / "install.sh"
AR_REPO = Path("/home/vitaly/agents_rules")


class TestAgentsBundle(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ab_test_"))
        os.environ["AGENTS_BUNDLE_CACHE_DIR"] = str(self.tmp / "cache")
        os.environ["AGENTS_BUNDLE_LOCAL_PKG_DIR"] = str(AR_REPO)

    def tearDown(self):
        os.environ.pop("AGENTS_BUNDLE_CACHE_DIR", None)
        os.environ.pop("AGENTS_BUNDLE_LOCAL_PKG_DIR", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_check_help_and_version(self):
        rb = subprocess.run(["python3", str(BUILD_PY), "--check"], capture_output=True, text=True, check=False)
        self.assertEqual(rb.returncode, 0, rb.stderr)
        rh = subprocess.run([str(SCRIPT), "-h"], capture_output=True, text=True, check=False)
        self.assertEqual(rh.returncode, 0)
        self.assertIn("Usage:", rh.stdout)
        rv = subprocess.run([str(SCRIPT), "--version"], capture_output=True, text=True, check=False)
        self.assertEqual(rv.returncode, 0)
        ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(rv.stdout.strip(), f"agents_bundle {ver}")

    def test_missing_spec_fails_with_hint(self):
        r = subprocess.run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertIn(".agents_bundle not found", r.stderr)
        self.assertIn("agents_bundle --init", r.stderr)

    def test_preset_rule_and_dollar_commands_in_agents_bundle(self):
        (self.tmp / "AGENTS.md").write_text("# Project Rules\n", encoding="utf-8")
        (self.tmp / "extra.txt").write_text("extra content\n", encoding="utf-8")
        (self.tmp / ".agents_bundle").write_text(
            "preset vitalio/agents_rules:workflow -collab/external lang=Russian\n"
            "rule vitalio/agents_rules:stack/python-cli py_min=3.12\n"
            "$ cat AGENTS.md\n"
            "$ agents_bundle --tree --max-lines 10\n"
            "$ echo cmd_ok\n",
            encoding="utf-8",
        )
        rb = subprocess.run(
            [str(SCRIPT), "extra.txt", "-p", "Solve task 1"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(rb.returncode, 0, rb.stderr)
        self.assertIn("===== Rules =====", rb.stdout)
        self.assertNotIn("# [preset", rb.stdout)
        self.assertIn("in **Russian**", rb.stdout)
        self.assertNotIn("Clean external text & two-step external changes:", rb.stdout)
        self.assertIn("Python 3.12+ compatibility", rb.stdout)

        # Verify -v / --verbose includes provenance trace comments
        rb_v = subprocess.run(
            [str(SCRIPT), "-v"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(rb_v.returncode, 0, rb_v.stderr)
        self.assertIn("# [preset vitalio/agents_rules:workflow -> preset core -> rules/core/start.md]", rb_v.stdout)
        self.assertIn("# [rule vitalio/agents_rules:stack/python-cli -> rules/stack/python-cli.md] (py_min=3.12)", rb_v.stdout)
        self.assertIn("===== $ cat AGENTS.md =====", rb.stdout)
        self.assertIn("# Project Rules", rb.stdout)
        self.assertIn("===== $ agents_bundle --tree --max-lines 10 =====", rb.stdout)
        self.assertIn("cmd_ok", rb.stdout)
        self.assertIn("===== $ cat extra.txt =====", rb.stdout)
        self.assertIn("===== Prompt =====", rb.stdout)
        self.assertIn("Solve task 1", rb.stdout)

    def test_cli_preset_rule_and_list(self):
        rl = subprocess.run([str(SCRIPT), "--list"], capture_output=True, text=True, check=False)
        self.assertEqual(rl.returncode, 0, rl.stderr)
        self.assertIn("vitalio/agents_rules:workflow", rl.stdout)
        self.assertIn("vitalio/agents_rules:core/composability", rl.stdout)

        rr = subprocess.run([str(SCRIPT), "rule", "vitalio/agents_rules:release/single-file-build"], capture_output=True, text=True, check=False)
        self.assertEqual(rr.returncode, 0, rr.stderr)
        self.assertIn("Single-file build from modular `src/`:", rr.stdout)

    def test_install_sh(self):
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        ri = subprocess.run(["sh", str(INSTALL_SH), "--dir", str(bin_dir), "--yes"], capture_output=True, text=True, check=False)
        self.assertEqual(ri.returncode, 0, ri.stderr)
        self.assertTrue((bin_dir / "agents_bundle").is_file())


if __name__ == "__main__":
    unittest.main()
