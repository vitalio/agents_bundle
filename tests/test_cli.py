#!/usr/bin/env python3
"""CLI, build check, and installer tests for agents_bundle."""
import sys
import unittest

from tests.helpers import AgentsBundleTestCase, BUILD_PY, INSTALL_SH, ROOT, SCRIPT


class TestCLI(AgentsBundleTestCase):
    def test_build_check_help_and_version(self):
        rb = self._run_subprocess([sys.executable, str(BUILD_PY), "--check"], capture_output=True, text=True, check=False)
        self._assert_ok(rb)
        rh = self._run_subprocess([str(SCRIPT), "-h"], capture_output=True, text=True, check=False)
        self._assert_ok(rh)
        self.assertIn("Usage:", rh.stdout)
        self.assertIn("--plain", rh.stdout)
        self.assertIn("AGENTS_BUNDLE_PLAIN", rh.stdout)
        self.assertIn("Bundle Output Protocol:", rh.stdout)
        self.assertIn("-x/--exclude DIR", rh.stdout)
        self.assertNotIn("--agents", rh.stdout)
        rv = self._run_subprocess([str(SCRIPT), "--version"], capture_output=True, text=True, check=False)
        self._assert_ok(rv)
        ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(rv.stdout.strip(), f"agents_bundle {ver}")

    def test_missing_spec_fails_with_hint(self):
        r = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 2, msg=f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}")
        self.assertEqual(r.stdout, "")
        self.assertIn(".agents_bundle not found", r.stderr)
        self.assertIn("agents_bundle --init", r.stderr)

    def test_install_sh(self):
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        ri = self._run_subprocess(["sh", str(INSTALL_SH), "--dir", str(bin_dir), "--yes"], capture_output=True, text=True, check=False)
        self._assert_ok(ri)
        self.assertTrue((bin_dir / "agents_bundle").is_file())


if __name__ == "__main__":
    unittest.main()
