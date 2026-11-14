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
AR_REPO = Path("/home/vitaly/agents-rules")


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
        self.assertIn("-x/--exclude DIR", rh.stdout)
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

    def test_preset_rule_if_conditions_and_dollar_commands(self):
        import sys
        cur_os = "windows" if os.name == "nt" else ("macos" if sys.platform == "darwin" else "linux")
        other_os = "windows" if cur_os != "windows" else "linux"
        (self.tmp / "AGENTS.md").write_text("# Project Rules\n", encoding="utf-8")
        (self.tmp / "extra.txt").write_text("extra content\n", encoding="utf-8")
        (self.tmp / ".agents_bundle").write_text(
            "preset vitalio/agents-rules:core lang=Russian\n"
            f"[if os={cur_os}] rule vitalio/agents-rules:os/linux\n"
            f"[if os={other_os}] rule vitalio/agents-rules:os/windows\n"
            f"[if os={cur_os}]\n"
            "rule vitalio/agents-rules:stack/python-cli py_min=3.12\n"
            "[/if]\n"
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
        self.assertIn("Linux & POSIX shell rules:", rb.stdout)
        self.assertNotIn("Windows & PowerShell 7+ (`pwsh`) rules:", rb.stdout)
        self.assertIn("Python 3.12+ compatibility", rb.stdout)

        # Verify -v / --verbose includes provenance trace comments with [if ...]
        rb_v = subprocess.run(
            [str(SCRIPT), "-v"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(rb_v.returncode, 0, rb_v.stderr)
        self.assertIn("# [preset vitalio/agents-rules:core -> rules/core/start.md]", rb_v.stdout)
        self.assertIn(f"# [[if os={cur_os}] rule vitalio/agents-rules:os/linux -> rules/os/linux.md]", rb_v.stdout)
        self.assertIn(f"# [[if os={cur_os}] rule vitalio/agents-rules:stack/python-cli -> rules/stack/python-cli.md] (py_min=3.12)", rb_v.stdout)

        # Verify direct URL rule and preset loading
        url_rule = self.tmp / "custom_url_rule.md"
        url_rule.write_text("# Description: Direct URL rule\n- **Direct URL invariant:** Loaded from URL {val:42}.\n", encoding="utf-8")
        url_preset = self.tmp / "custom_url.preset"
        url_preset.write_text(f"# Description: Direct URL preset\nrule {url_rule.as_uri()} val=99\n", encoding="utf-8")
        r_url = subprocess.run(
            [str(SCRIPT), "preset", url_preset.as_uri()],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_url.returncode, 0, r_url.stderr)
        self.assertIn("Loaded from URL 99.", r_url.stdout)

        # Verify include directive, CLI key=val variables, and prompt directives in .agents_bundle
        inc_file = self.tmp / "task_flow.bundle"
        inc_file.write_text(
            "# Description: Custom task flow include\n"
            "[if task!=]\n"
            "[if task=plan] $ echo all_tasks\n"
            "[if task!=,plan] $ echo focused_task_{task:}\n"
            "[if task=plan] prompt Mode: PLANNING\n"
            "[if task!=,plan] prompt Mode: IMPLEMENTATION ({task:})\n"
            "[/if]\n",
            encoding="utf-8",
        )
        (self.tmp / ".agents_bundle").write_text(
            "preset vitalio/agents-rules:core\n"
            f"include {inc_file.as_posix()}\n",
            encoding="utf-8",
        )
        r_none = subprocess.run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(r_none.returncode, 0, r_none.stderr)
        self.assertNotIn("all_tasks", r_none.stdout)
        self.assertNotIn("focused_task_", r_none.stdout)
        self.assertNotIn("===== Prompt =====", r_none.stdout)

        r_plan = subprocess.run([str(SCRIPT), "task=plan"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(r_plan.returncode, 0, r_plan.stderr)
        self.assertIn("all_tasks", r_plan.stdout)
        self.assertNotIn("focused_task_", r_plan.stdout)
        self.assertIn("===== Prompt =====\nMode: PLANNING", r_plan.stdout)

        r_foc = subprocess.run(
            [str(SCRIPT), "task=A2", "lang=German", "-p", "Focus on edge cases"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_foc.returncode, 0, r_foc.stderr)
        self.assertIn("focused_task_A2", r_foc.stdout)
        self.assertNotIn("all_tasks", r_foc.stdout)
        self.assertIn("in **German**", r_foc.stdout)
        self.assertIn("===== Prompt =====\nMode: IMPLEMENTATION (A2)\n\nFocus on edge cases", r_foc.stdout)

    def test_builtin_vars_override_in_preset(self):
        rp = subprocess.run(
            [str(SCRIPT), "preset", "vitalio/agents-rules:default", "os=windows", "vcs=cvs", "-v"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(rp.returncode, 0, rp.stderr)
        self.assertIn("[if os=windows] rule os/windows -> rules/os/windows.md", rp.stdout)
        self.assertIn("[if vcs=cvs] rule vcs/cvs -> rules/vcs/cvs.md", rp.stdout)
        self.assertNotIn("rules/os/linux.md", rp.stdout)
        self.assertNotIn("rules/vcs/git.md", rp.stdout)

    def test_tree_exclude_and_truncation(self):
        (self.tmp / "bumps" / "nested").mkdir(parents=True)
        (self.tmp / "bumps" / "nested" / "dump.txt").write_text("a\nb\nc\n", encoding="utf-8")
        (self.tmp / "tools").mkdir()
        for idx in range(12):
            (self.tmp / "tools" / f"tool_{idx:02d}.py").write_text("print(1)\n", encoding="utf-8")

        rt = subprocess.run(
            [str(SCRIPT), "--tree", str(self.tmp), "-x", "bumps", "--max-lines", "12"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(rt.returncode, 0, rt.stderr)
        self.assertIn("bumps/ (excluded)", rt.stdout)
        self.assertNotIn("dump.txt", rt.stdout)
        self.assertIn("tools/", rt.stdout)
        self.assertIn("more files", rt.stdout)

    def test_cli_preset_rule_and_list(self):
        rl = subprocess.run([str(SCRIPT), "--list"], capture_output=True, text=True, check=False)
        self.assertEqual(rl.returncode, 0, rl.stderr)
        self.assertIn("Built-in variables", rl.stdout)
        self.assertIn("[if os=linux] rule os/linux", rl.stdout)
        self.assertIn("Bundle includes in 'vitalio/agents-rules'", rl.stdout)
        self.assertNotIn("os/auto", rl.stdout)
        self.assertNotIn("vcs/auto", rl.stdout)

        rr = subprocess.run([str(SCRIPT), "rule", "vitalio/agents-rules:release/single-file-build"], capture_output=True, text=True, check=False)
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
