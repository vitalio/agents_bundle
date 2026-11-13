#!/usr/bin/env python3
"""Tests for agents_bundle."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "agents_bundle"
BUILD_PY = ROOT / "build.py"
INSTALL_SH = ROOT / "install.sh"


class TestAgentsBundle(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ab_test_"))

    def tearDown(self):
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

    def test_init_and_bundle_to_stdout_with_warnings_on_stderr(self):
        ri = subprocess.run([str(SCRIPT), "--init"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(ri.returncode, 0)
        self.assertTrue((self.tmp / ".agents_bundle").is_file())

        (self.tmp / "AGENTS.md").write_text("# Project Rules\n", encoding="utf-8")
        (self.tmp / "extra.txt").write_text("extra content\n", encoding="utf-8")
        (self.tmp / ".agents_bundle").write_text(
            "AGENTS.md\nMISSING.md\n$ agents_bundle --tree --max-lines 10\n$ echo cmd_ok\n",
            encoding="utf-8",
        )
        rb = subprocess.run(
            [str(SCRIPT), "extra.txt", "-p", "Solve task 1"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(rb.returncode, 0)
        self.assertIn("missing file: MISSING.md", rb.stderr)
        self.assertNotIn("MISSING.md", rb.stdout)
        self.assertIn("===== File: AGENTS.md =====", rb.stdout)
        self.assertIn("# Project Rules", rb.stdout)
        self.assertIn("===== $ agents_bundle --tree --max-lines 10 =====", rb.stdout)
        self.assertIn("cmd_ok", rb.stdout)
        self.assertIn("===== File: extra.txt =====", rb.stdout)
        self.assertIn("===== Prompt =====", rb.stdout)
        self.assertIn("Solve task 1", rb.stdout)

    def test_install_sh(self):
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        ri = subprocess.run(["sh", str(INSTALL_SH), "--dir", str(bin_dir), "--yes"], capture_output=True, text=True, check=False)
        self.assertEqual(ri.returncode, 0, ri.stderr)
        self.assertTrue((bin_dir / "agents_bundle").is_file())


if __name__ == "__main__":
    unittest.main()
