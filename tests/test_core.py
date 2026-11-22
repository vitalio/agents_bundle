#!/usr/bin/env python3
"""Core helper (src/core.py) and standalone module import tests."""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class TestCoreHelpers(unittest.TestCase):
    def setUp(self):
        self.core = importlib.import_module("src.core")

    def test_prog_name_strips_script_suffixes(self):
        for argv0, expected in (
            ("/x/agents_bundle", "agents_bundle"),
            ("agents_bundle.py", "agents_bundle"),
            ("/x/ab.cmd", "ab"),
            (".py", ".py"),
            ("", "agents_bundle"),
        ):
            with self.subTest(argv0=argv0):
                with mock.patch.object(sys, "argv", [argv0]):
                    self.assertEqual(self.core.prog_name(), expected)

    def test_cache_dir_path_precedence(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"AGENTS_BUNDLE_CACHE_DIR": d}):
                self.assertEqual(self.core.cache_dir_path(), Path(d))
            env = {k: v for k, v in os.environ.items() if k != "AGENTS_BUNDLE_CACHE_DIR"}
            env["XDG_CACHE_HOME"] = d
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(self.core.cache_dir_path(), Path(d) / "agents_bundle")

    def test_usage_text_renders_help_sections(self):
        header = importlib.import_module("src.header")
        text = self.core.usage_text()
        for title, _rows in header.HELP_SECTIONS:
            self.assertIn(title, text)
        self.assertIn(header.DEFAULT_RULES_PKG, text)
        self.assertNotIn("{prog}", text)
        self.assertNotIn("{cache_dir}", text)


class TestStandaloneModules(unittest.TestCase):
    def test_every_src_module_imports_standalone(self):
        for name, attr in (
            ("header", "HELP_SECTIONS"),
            ("core", "prog_name"),
            ("tree", "cmd_tree"),
            ("rules_engine", "render_directive"),
            ("bundle", "cmd_bundle"),
            ("cli", "main"),
        ):
            with self.subTest(module=name):
                mod = importlib.import_module(f"src.{name}")
                self.assertTrue(hasattr(mod, attr))


if __name__ == "__main__":
    unittest.main()
