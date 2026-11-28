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
            ("/x/context", "context"),
            ("context.py", "context"),
            (".py", ".py"),
            ("", "context"),
        ):
            with self.subTest(argv0=argv0):
                with mock.patch.object(sys, "argv", [argv0]):
                    self.assertEqual(self.core.prog_name(), expected)

    def test_cache_dir_path_precedence_and_legacy_migration(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"CONTEXT_BUNDLE_CACHE_DIR": d}):
                self.assertEqual(self.core.cache_dir_path(), Path(d))
            env = {k: v for k, v in os.environ.items() if k != "CONTEXT_BUNDLE_CACHE_DIR"}
            env["XDG_CACHE_HOME"] = d
            legacy = Path(d) / "agents_bundle"
            keep_pkg = legacy / "packages" / "vitalio" / "agents-rules"
            keep_pkg.mkdir(parents=True)
            (keep_pkg / "marker.txt").write_text("ok", encoding="utf-8")
            for obs in ("agents_bundle", "run_block", "todo_md"):
                obs_dir = legacy / "packages" / "vitalio" / obs
                obs_dir.mkdir(parents=True)
                (obs_dir / "old.txt").write_text("stale", encoding="utf-8")
            with mock.patch.dict(os.environ, env, clear=True):
                cdir = self.core.cache_dir_path()
                self.assertEqual(cdir, Path(d) / "context-bundle")
                self.assertFalse(legacy.exists())
                self.assertTrue((cdir / "packages" / "vitalio" / "agents-rules" / "marker.txt").is_file())
                for obs in ("agents_bundle", "run_block", "todo_md"):
                    self.assertFalse((cdir / "packages" / "vitalio" / obs).exists())

    def test_usage_text_renders_help_sections(self):
        header = importlib.import_module("src.header")
        with mock.patch.object(sys, "argv", ["context"]), mock.patch.dict(
            os.environ, {"CONTEXT_BUNDLE_CACHE_DIR": "/tmp/ctx-cache"}
        ):
            text = self.core.usage_text()
        self.assertIn("Usage:", text)
        for title, _rows in header.HELP_SECTIONS:
            self.assertIn(title, text)
        self.assertIn(header.DEFAULT_RULES_PKG, text)
        self.assertNotIn("{prog}", text)
        self.assertNotIn("{cache_dir}", text)
        self.assertNotIn("{trust_file}", text)
        fields = {
            "prog": "context",
            "default_pkg": header.DEFAULT_RULES_PKG,
            "cache_dir": "/tmp/ctx-cache",
            "trust_file": "/tmp/trusted.json",
        }
        expected_col = (
            header.HELP_INDENT
            + max(
                min(len(left.format(**fields)), header.HELP_MAX_LEFT)
                for _, rows in header.HELP_SECTIONS
                for left, _ in rows
            )
            + header.HELP_GAP
        )
        self.assertLessEqual(expected_col, 36)
        in_usage = False
        for line in text.splitlines():
            self.assertLessEqual(len(line), header.HELP_MAX_WIDTH, msg=line)
            if not line:
                in_usage = False
                continue
            if not line.startswith(" "):
                in_usage = line == "Usage:"
                continue
            if in_usage or not line.startswith(" " * header.HELP_INDENT):
                continue
            if line.startswith(" " * expected_col):
                self.assertNotEqual(line[expected_col], " ", msg=line)
            else:
                self.assertGreater(len(line), expected_col, msg=line)
                self.assertEqual(line[expected_col - 1], " ", msg=line)
                self.assertNotEqual(line[expected_col], " ", msg=line)

        with self.subTest(case="overlong left label caps left column via HELP_MAX_LEFT"):
            overlong_left = "custom-overlong-command-signature [k=v ...] [FILE ...]"
            custom_sections = (
                ("Commands:", ((overlong_left, "Build context bundle"),)),
                *header.HELP_SECTIONS,
            )
            with mock.patch.object(self.core, "HELP_SECTIONS", custom_sections), mock.patch.dict(
                os.environ, {"CONTEXT_BUNDLE_CACHE_DIR": "/tmp/ctx-cache"}
            ):
                long_text = self.core.usage_text()
            max_col = header.HELP_INDENT + header.HELP_MAX_LEFT + header.HELP_GAP
            for line in long_text.splitlines():
                self.assertLessEqual(len(line), header.HELP_MAX_WIDTH, msg=line)
            expected_wrapped = f"  {overlong_left}\n" + (" " * max_col) + "Build context bundle"
            self.assertEqual(long_text.count(expected_wrapped), 1)


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
