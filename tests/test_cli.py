#!/usr/bin/env python3
"""CLI, build check, and installer tests for agents_bundle."""
import importlib.util
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
        self.assertIn("bundle <pkg>[:<name>] [k=v]", rh.stdout)
        self.assertNotIn("--agents", rh.stdout)
        rv = self._run_subprocess([str(SCRIPT), "--version"], capture_output=True, text=True, check=False)
        self._assert_ok(rv)
        ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(rv.stdout.strip(), f"agents_bundle {ver}")

    def test_build_strips_internal_imports(self):
        spec = importlib.util.spec_from_file_location("build_mod", BUILD_PY)
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        hdr = build.header_import_set("import os\nfrom pathlib import Path\n")
        src = (
            "from __future__ import annotations\n\nimport os\nfrom pathlib import Path\n\n"
            "from src.header import (\n    A,\n    B,\n)\n\n\ndef f():\n    return os, Path, A, B\n"
        )
        order = ["header.py", "core.py", "tree.py"]
        self.assertEqual(
            build.strip_module_imports("core.py", src, hdr, order),
            "def f():\n    return os, Path, A, B",
        )
        with self.subTest(case="stdlib import missing in header"):
            with self.assertRaises(SystemExit):
                build.strip_module_imports("core.py", "import json\n", hdr, order)
        with self.subTest(case="sibling import from a later module"):
            with self.assertRaises(SystemExit):
                build.strip_module_imports("core.py", "from src.tree import x\n", hdr, order)
        self.assertNotIn("from src.", SCRIPT.read_text(encoding="utf-8"))

    def test_missing_spec_fails_with_hint(self):
        r = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 2, msg=f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}")
        self.assertEqual(r.stdout, "")
        self.assertIn(".agents_bundle not found", r.stderr)
        self.assertIn("agents_bundle --init", r.stderr)

    def test_bundle_subcommand_renders_bundle(self):
        target = "vitalio/agents_bundle:agents_bundle"
        with self.subTest(case="plain output without .agents_bundle"):
            r = self._run(
                [str(SCRIPT), "bundle", target, "role=design", "--plain"],
                cwd=str(self.tmp),
                capture_output=True,
                text=True,
                check=False,
            )
            self._assert_ok(r)
            self.assertNotIn("Bundle-Boundary", r.stdout)
            self.assertIn("Role: design", r.stdout)
            self.assertIn("Context bundler & rules engine", r.stdout)
            self.assertIn("===== $ agents_bundle --list =====", r.stdout)
        with self.subTest(case="transport headers and fragment markers"):
            r = self._run(
                [str(SCRIPT), "bundle", "vitalio/todo_md"],
                cwd=str(self.tmp),
                capture_output=True,
                text=True,
                check=False,
            )
            self._assert_ok(r)
            self.assertIn("Bundle-Command: agents_bundle bundle vitalio/todo_md", r.stdout)
            _nonce, fragments = self._extract_fragments(r.stdout)
            self.assertEqual(fragments[0][0]["kind"], "rule")
            self.assertEqual(fragments[0][0]["chain"], ["vitalio/todo_md"])
        with self.subTest(case="missing target"):
            r = self._run([str(SCRIPT), "bundle"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("usage: agents_bundle bundle", r.stderr)
        with self.subTest(case="unknown bundle"):
            r = self._run(
                [str(SCRIPT), "bundle", "vitalio/agents_bundle:nope"],
                cwd=str(self.tmp),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("unknown bundle 'nope'", r.stderr)

    def test_install_sh(self):
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        ri = self._run_subprocess(["sh", str(INSTALL_SH), "--dir", str(bin_dir), "--yes"], capture_output=True, text=True, check=False)
        self._assert_ok(ri)
        self.assertTrue((bin_dir / "agents_bundle").is_file())


if __name__ == "__main__":
    unittest.main()
