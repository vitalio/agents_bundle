#!/usr/bin/env python3
"""Tests for agents_bundle."""
from __future__ import annotations

import http.server
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "agents_bundle"
BUILD_PY = ROOT / "build.py"
INSTALL_SH = ROOT / "install.sh"


def _seed_offline_rules_pkg(pkg_dir: Path) -> None:
    files = {
        "rulesets/core.ruleset": (
            "# Description: Core axioms\n"
            "rule core/start\n"
            "rule core/ssot\n"
            "rule core/lang lang=English\n"
        ),
        "rulesets/default.ruleset": (
            "# Description: Default project rules\n"
            "ruleset core\n"
            "[if os=linux] rule os/linux\n"
            "[if os=macos] rule os/macos\n"
            "[if os=windows] rule os/windows\n"
            "[if vcs=git] rule vcs/git\n"
            "[if vcs=cvs] rule vcs/cvs\n"
            "[if role!=] rule role/{role:}\n"
        ),
        "rules/core/start.md": "# Description: Start priority\n- Start priority, instruction self-audit & dates: Format dates as `{chat_date_fmt:DD/MM/YYYY}`; in files, commits, headers, and logs always use UTC with ISO `YYYY-MM-DD`.\n",
        "rules/core/ssot.md": "# Description: SSOT\n- Single source of truth & DRY: Define every version in one place.\n",
        "rules/core/lang.md": "# Description: Language policy\n- Language policy: Write chat prose in {chat_lang:the language the user writes in}; keep code and docs in {lang:English}.\n",
        "rules/os/linux.md": "# Description: Linux shell rules\n- Linux & POSIX shell rules: Enable `set -euo pipefail` in mutating scripts.\n",
        "rules/os/macos.md": "# Description: macOS rules\n- macOS & BSD userland rules: Account for BSD userland differences.\n",
        "rules/os/windows.md": "# Description: Windows rules\n- Windows & PowerShell rules: Enable `$ErrorActionPreference = 'Stop'`.\n",
        "rules/vcs/git.md": "# Description: Git workflow\n- Git workflow & safety: Push to `origin {main_branch:main}`.\n",
        "rules/vcs/cvs.md": "# Description: CVS workflow\n- CVS workflow & safety: Inspect status via `cvs -nq update` and `cvs diff -u`.\n",
        "rules/role/design.md": "# Description: Universal Designer role\n- Role (Designer): Explore problem space and architecture.\n",
        "rules/role/plan.md": "# Description: Universal Planner role\n- Role (Planner): Decompose and prioritize tasks.\n",
        "rules/role/execute.md": "# Description: Universal Executor role\n- Role (Executor): Focus strictly on delivering the target task.\n",
        "rules/role/audit.md": "# Description: Universal Auditor role\n- Role (Auditor): Audit the requested scope.\n",
        "rules/stack/python-cli.md": "# Description: Python CLI rules\n- Python CLI engineering invariants: Python {py_min:3.9}+ compatibility.\n",
        "rules/release/single-file-build.md": "# Description: Single-file build\n- Single-file build from modular `src/`: Edit source modules under `src/`.\n",
        "rules/agents_bundle.md": "# Description: Bundler rule\n- Context bundler & rules engine (`agents_bundle`): Use `--tree` and `--list`.\n",
        "bundles/agents_bundle.bundle": "# Description: On-demand agents_bundle instructions\nrule vitalio/agents_bundle:agents_bundle\n[if role=design] $ agents_bundle --list\n",
        "rules/todo_md.md": "# Description: Task tracker rule\n- Task management (`todo_md`): Manage `TODO.md`.\n",
        "bundles/todo_md.bundle": "# Description: On-demand todo_md bundle\nrule vitalio/todo_md:todo_md\n",
    }
    for rel, content in files.items():
        p = pkg_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


class TestAgentsBundle(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ab_test_"))
        self._saved_env_vars = os.environ.pop("AGENTS_BUNDLE_VARS", None)
        pkg_dir = self.tmp / "offline_rules_pkg"
        _seed_offline_rules_pkg(pkg_dir)
        os.environ["AGENTS_BUNDLE_CACHE_DIR"] = str(self.tmp / "cache")
        os.environ["AGENTS_BUNDLE_LOCAL_PKG_DIR"] = str(pkg_dir)

    def tearDown(self):
        os.environ.pop("AGENTS_BUNDLE_CACHE_DIR", None)
        os.environ.pop("AGENTS_BUNDLE_LOCAL_PKG_DIR", None)
        if self._saved_env_vars is not None:
            os.environ["AGENTS_BUNDLE_VARS"] = self._saved_env_vars
        else:
            os.environ.pop("AGENTS_BUNDLE_VARS", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_check_help_and_version(self):
        rb = subprocess.run(["python3", str(BUILD_PY), "--check"], capture_output=True, text=True, check=False)
        self.assertEqual(rb.returncode, 0, rb.stderr)
        rh = subprocess.run([str(SCRIPT), "-h"], capture_output=True, text=True, check=False)
        self.assertEqual(rh.returncode, 0)
        self.assertIn("Usage:", rh.stdout)
        self.assertIn("-x/--exclude DIR", rh.stdout)
        self.assertNotIn("--agents", rh.stdout)
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

    def test_ruleset_rule_if_conditions_and_dollar_commands(self):
        import sys
        cur_os = "windows" if os.name == "nt" else ("macos" if sys.platform == "darwin" else "linux")
        other_os = "windows" if cur_os != "windows" else "linux"
        (self.tmp / "AGENTS.md").write_text("# Project Rules\n", encoding="utf-8")
        (self.tmp / "extra.txt").write_text("extra content\n", encoding="utf-8")
        (self.tmp / ".agents_bundle").write_text(
            "ruleset vitalio/agents-rules:core lang=Spanish\n"
            f"[if os={cur_os}] rule vitalio/agents-rules:os/linux\n"
            f"[if os={other_os}] rule vitalio/agents-rules:os/windows\n"
            f"[if os={cur_os}]\n"
            "    rule vitalio/agents-rules:stack/python-cli py_min=3.12\n"
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
        self.assertIn("Bundle-Command: agents_bundle extra.txt -p 'Solve task 1'", rb.stdout)
        self.assertIn("===== Rules =====", rb.stdout)
        self.assertNotIn("# [ruleset", rb.stdout)
        self.assertIn("in Spanish", rb.stdout)
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
        self.assertIn("# [ruleset vitalio/agents-rules:core -> rules/core/start.md]", rb_v.stdout)
        self.assertIn(f"# [[if os={cur_os}] rule vitalio/agents-rules:os/linux -> rules/os/linux.md]", rb_v.stdout)
        self.assertIn(f"# [[if os={cur_os}] rule vitalio/agents-rules:stack/python-cli -> rules/stack/python-cli.md] (py_min=3.12)", rb_v.stdout)

        # Verify direct URL rule and ruleset loading
        url_rule = self.tmp / "custom_url_rule.md"
        url_rule.write_text("# Description: Direct URL rule\n- **Direct URL invariant:** Loaded from URL {val:42}.\n", encoding="utf-8")
        url_ruleset = self.tmp / "custom_url.ruleset"
        url_ruleset.write_text(f"# Description: Direct URL ruleset\nrule {url_rule.as_uri()} val=99\n", encoding="utf-8")
        r_url = subprocess.run(
            [str(SCRIPT), "ruleset", url_ruleset.as_uri()],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_url.returncode, 0, r_url.stderr)
        self.assertIn("Loaded from URL 99.", r_url.stdout)

        # Verify bundle directive, CLI key=val variables, and prompt directives in .agents_bundle
        inc_file = self.tmp / "task_flow.bundle"
        inc_file.write_text(
            "# Description: Custom task flow bundle\n"
            "[if role=plan]\n"
            "    [if task=] $ echo all_tasks\n"
            "    [if task!=] $ echo focused_task_{task:}\n"
            "    prompt Mode: PLANNING\n"
            "[/if]\n"
            "[if role=execute]\n"
            "    [if task=]\n"
            "        $ echo all_tasks\n"
            "        prompt Mode: EXECUTION\n"
            "    [/if]\n"
            "    [if task!=]\n"
            "        $ echo focused_task_{task:}\n"
            "        prompt Mode: EXECUTION ({task:})\n"
            "    [/if]\n"
            "[/if]\n",
            encoding="utf-8",
        )
        (self.tmp / ".agents_bundle").write_text(
            "bundle vitalio/agents_bundle\n"
            "ruleset vitalio/agents-rules:core\n"
            "bundle vitalio/todo_md\n"
            f"bundle {inc_file.as_posix()}\n",
            encoding="utf-8",
        )
        r_none = subprocess.run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(r_none.returncode, 0, r_none.stderr)
        self.assertIn("Context bundler & rules engine", r_none.stdout)
        self.assertIn("Task management (`todo_md`)", r_none.stdout)
        self.assertNotIn("all_tasks", r_none.stdout)
        self.assertNotIn("focused_task_", r_none.stdout)
        self.assertNotIn("===== Prompt =====", r_none.stdout)

        r_plan = subprocess.run([str(SCRIPT), "role=plan"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(r_plan.returncode, 0, r_plan.stderr)
        self.assertIn("Bundle-Command: agents_bundle role=plan\n", r_plan.stdout)
        self.assertIn("Bundle-Expose: Role, Task\n", r_plan.stdout)
        self.assertIn("Role: plan\n", r_plan.stdout)
        self.assertIn("all_tasks", r_plan.stdout)
        self.assertNotIn("focused_task_", r_plan.stdout)
        self.assertIn("===== Prompt =====\nMode: PLANNING", r_plan.stdout)

        r_exec = subprocess.run([str(SCRIPT), "role=execute"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(r_exec.returncode, 0, r_exec.stderr)
        self.assertIn("Bundle-Command: agents_bundle role=execute\n", r_exec.stdout)
        self.assertIn("Bundle-Expose: Role, Task\n", r_exec.stdout)
        self.assertIn("Role: execute\n", r_exec.stdout)
        self.assertIn("all_tasks", r_exec.stdout)
        self.assertNotIn("focused_task_", r_exec.stdout)
        self.assertIn("===== Prompt =====\nMode: EXECUTION", r_exec.stdout)

        r_foc = subprocess.run(
            [str(SCRIPT), "role=execute", "task=A2", "lang=German", "-p", "Focus on edge cases"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_foc.returncode, 0, r_foc.stderr)
        self.assertIn("Bundle-Command: agents_bundle role=execute task=A2 lang=German -p 'Focus on edge cases'", r_foc.stdout)
        self.assertIn("Role: execute\nTask: A2\nLang: German\n", r_foc.stdout)
        self.assertIn("focused_task_A2", r_foc.stdout)
        self.assertNotIn("all_tasks", r_foc.stdout)
        self.assertIn("in German", r_foc.stdout)
        self.assertIn("===== Prompt =====\nMode: EXECUTION (A2)\n\nFocus on edge cases", r_foc.stdout)

    def test_builtin_vars_override_in_ruleset(self):
        rp = subprocess.run(
            [str(SCRIPT), "ruleset", "vitalio/agents-rules:default", "os=windows", "vcs=cvs", "-v"],
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

    def test_cli_ruleset_rule_and_list(self):
        rl = subprocess.run([str(SCRIPT), "--list"], capture_output=True, text=True, check=False)
        self.assertEqual(rl.returncode, 0, rl.stderr)
        self.assertIn("Built-in variables", rl.stdout)
        self.assertIn("piped", rl.stdout)
        self.assertIn("[if os=linux] rule os/linux", rl.stdout)
        self.assertIn("Bundles in 'vitalio/agents-rules'", rl.stdout)
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


    def test_tree_pins_agents_md_and_rules_ignore_agents_md(self):
        sub = self.tmp / "pkg_repo" / "rules" / "core"
        sub.mkdir(parents=True)
        (sub / "AGENTS.md").write_text("# Core philosophy\n", encoding="utf-8")
        (sub / "ssot.md").write_text("# Description: SSOT\n- SSOT rule\n", encoding="utf-8")
        for idx in range(12):
            (sub / f"z_file_{idx:02d}.txt").write_text("line\n", encoding="utf-8")
        r_tree = subprocess.run(
            [str(SCRIPT), "--tree", str(self.tmp / "pkg_repo"), "--max-lines", "12"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_tree.returncode, 0)
        self.assertIn("AGENTS.md", r_tree.stdout)

        # Verify comment stripping in rules and dynamic {role:} target resolution in rulesets
        role_dir = self.tmp / "pkg_repo" / "rules" / "role"
        role_dir.mkdir(parents=True)
        (role_dir / "audit.md").write_text(
            "# Description: Auditor\n# Maintainer comment that must be stripped\n<!-- html comment -->\n- Role (Auditor): Check consistency.\n",
            encoding="utf-8",
        )
        p_dir = self.tmp / "pkg_repo" / "rulesets"
        p_dir.mkdir(parents=True)
        (p_dir / "default.ruleset").write_text(
            "# Description: Default\nrule core/ssot\n[if role!=] rule role/{role:}\n",
            encoding="utf-8",
        )
        env = {**os.environ, "AGENTS_BUNDLE_LOCAL_PKG_DIR": str(self.tmp / "pkg_repo")}
        r_role = subprocess.run(
            [str(SCRIPT), "ruleset", "vitalio/agents-rules:default", "role=audit"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(r_role.returncode, 0)
        self.assertIn("- Role (Auditor): Check consistency.", r_role.stdout)
        self.assertNotIn("Maintainer comment", r_role.stdout)
        self.assertNotIn("html comment", r_role.stdout)

    def test_agents_bundle_vars_env_and_cli_override(self):
        (self.tmp / ".agents_bundle").write_text(
            "ruleset vitalio/agents-rules:core lang=English\n"
            "[if mode=custom] prompt Custom mode active ({chat_lang:default})\n",
            encoding="utf-8",
        )
        env = {**os.environ, "AGENTS_BUNDLE_VARS": "lang=Spanish mode=custom chat_lang=French"}
        r_env = subprocess.run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, env=env, check=False)
        self.assertEqual(r_env.returncode, 0, r_env.stderr)
        self.assertIn("Bundle-Command: agents_bundle\n", r_env.stdout)
        self.assertIn("Bundle-Expose: Role, Task\n", r_env.stdout)
        self.assertIn("Lang: Spanish\nMode: custom\nChat-Lang: French\n", r_env.stdout)
        self.assertIn("in Spanish", r_env.stdout)
        self.assertIn("Custom mode active (French)", r_env.stdout)

        # CLI key=val overrides AGENTS_BUNDLE_VARS
        r_cli = subprocess.run(
            [str(SCRIPT), "lang=German", "chat_lang=Italian"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(r_cli.returncode, 0, r_cli.stderr)
        self.assertIn("in German", r_cli.stdout)
        self.assertIn("Custom mode active (Italian)", r_cli.stdout)

        # Subcommand ruleset/rule also respects AGENTS_BUNDLE_VARS and CLI override
        r_sub = subprocess.run(
            [str(SCRIPT), "rule", "vitalio/agents-rules:core/lang"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(r_sub.returncode, 0, r_sub.stderr)
        self.assertIn("in Spanish", r_sub.stdout)

        r_sub_cli = subprocess.run(
            [str(SCRIPT), "rule", "vitalio/agents-rules:core/lang", "lang=Japanese"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(r_sub_cli.returncode, 0, r_sub_cli.stderr)
        self.assertIn("in Japanese", r_sub_cli.stdout)

        # Invalid AGENTS_BUNDLE_VARS token fails explicitly
        bad_env = {**os.environ, "AGENTS_BUNDLE_VARS": "not_a_pair"}
        r_bad = subprocess.run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, env=bad_env, check=False)
        self.assertNotEqual(r_bad.returncode, 0)
        self.assertIn("AGENTS_BUNDLE_VARS", r_bad.stderr)

    def test_dynamic_var_include_and_stdin_pipe(self):
        (self.tmp / "src").mkdir()
        (self.tmp / "src/target.py").write_text("VALUE = 42\n", encoding="utf-8")
        (self.tmp / ".agents_bundle").write_text(
            "ruleset vitalio/agents-rules:core\n"
            "[if role=execute]\n"
            "    var task=$(printf 'F7')\n"
            "    include $(printf 'src/target.py\\nmissing/file.py\\n')\n"
            "    prompt Executing {task:}\n"
            "[/if]\n",
            encoding="utf-8",
        )
        # Dynamic var resolution and include directive without explicit task=<ID>
        r_dyn = subprocess.run(
            [str(SCRIPT), "role=execute"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_dyn.returncode, 0, r_dyn.stderr)
        self.assertIn("Role: execute\nTask: F7\n", r_dyn.stdout)
        self.assertIn("===== $ cat src/target.py =====\nVALUE = 42\n", r_dyn.stdout)
        self.assertIn("===== Prompt =====\nExecuting F7\n", r_dyn.stdout)
        self.assertEqual(r_dyn.stderr, "")

        # Explicit task=<ID> overrides var directive fallback
        r_explicit = subprocess.run(
            [str(SCRIPT), "role=execute", "task=F9"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_explicit.returncode, 0, r_explicit.stderr)
        self.assertIn("Role: execute\nTask: F9\n", r_explicit.stdout)
        self.assertIn("===== Prompt =====\nExecuting F9\n", r_explicit.stdout)

        # Piped Task preamble on stdin maps task variable and includes body in Prompt
        piped_task = "Task: F12\n\n# 🎯 [NEXT] F12: Piped task title\n\n- Target file: `src/target.py`\n"
        r_pipe = subprocess.run(
            [str(SCRIPT), "role=execute"],
            cwd=str(self.tmp),
            input=piped_task,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_pipe.returncode, 0, r_pipe.stderr)
        self.assertIn("Role: execute\nTask: F12\n", r_pipe.stdout)
        self.assertIn("===== Prompt =====\nExecuting F12\n\n# 🎯 [NEXT] F12: Piped task title", r_pipe.stdout)

        # Markdown heading without Task preamble does not infer task via hardcoded regex
        r_no_regex = subprocess.run(
            [str(SCRIPT), "role=execute"],
            cwd=str(self.tmp),
            input="# 🎯 [NEXT] F99: Plain markdown body\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_no_regex.returncode, 0, r_no_regex.stderr)
        self.assertIn("Role: execute\nTask: F7\n", r_no_regex.stdout)
        self.assertIn("# 🎯 [NEXT] F99: Plain markdown body", r_no_regex.stdout)

        # Piped bare task ID on stdin infers task ID without polluting Prompt
        r_pipe_id = subprocess.run(
            [str(SCRIPT), "role=execute"],
            cwd=str(self.tmp),
            input="F15\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_pipe_id.returncode, 0, r_pipe_id.stderr)
        self.assertIn("Role: execute\nTask: F15\n", r_pipe_id.stdout)
        self.assertIn("===== Prompt =====\nExecuting F15\n", r_pipe_id.stdout)

    def test_windows_default_pwsh_shell_and_posix_include_paths(self):
        fake_bin = self.tmp / "fake_bin"
        fake_bin.mkdir()
        pwsh_shim = fake_bin / "pwsh"
        pwsh_shim.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('PWSH_ARGS:' + '|'.join(sys.argv[1:]))\n",
            encoding="utf-8",
        )
        pwsh_shim.chmod(0o755)
        sub = self.tmp / "pkg"
        sub.mkdir()
        (sub / "mod.py").write_text("X = 1\n", encoding="utf-8")
        (self.tmp / ".agents_bundle").write_text(
            "ruleset vitalio/agents-rules:core\n"
            "include pkg/mod.py\n"
            "$ git status -sb\n",
            encoding="utf-8",
        )
        # Verify pwsh uses -Command flag when configured via AGENTS_BUNDLE_SHELL
        env = {**os.environ, "AGENTS_BUNDLE_SHELL": str(pwsh_shim)}
        r = subprocess.run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PWSH_ARGS:-Command|git status -sb", r.stdout)
        self.assertIn("===== $ cat pkg/mod.py =====\nX = 1\n", r.stdout)

    def test_single_rules_section_when_bundles_contain_commands(self):
        b1 = self.tmp / "first.bundle"
        b1.write_text(
            "rule vitalio/agents-rules:core/start\n"
            "$ echo cmd_from_b1\n",
            encoding="utf-8",
        )
        b2 = self.tmp / "second.bundle"
        b2.write_text(
            "rule vitalio/agents-rules:core/ssot\n"
            "$ echo cmd_from_b2\n",
            encoding="utf-8",
        )
        (self.tmp / ".agents_bundle").write_text(
            f"bundle {b1.as_posix()}\n"
            "$ echo middle_cmd\n"
            f"bundle {b2.as_posix()}\n"
            "rule vitalio/agents-rules:core/lang\n",
            encoding="utf-8",
        )
        r = subprocess.run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.count("===== Rules ====="), 1)
        rules_pos = r.stdout.index("===== Rules =====")
        cmd1_pos = r.stdout.index("===== $ echo cmd_from_b1 =====")
        mid_pos = r.stdout.index("===== $ echo middle_cmd =====")
        cmd2_pos = r.stdout.index("===== $ echo cmd_from_b2 =====")
        self.assertLess(rules_pos, cmd1_pos)
        self.assertLess(cmd1_pos, mid_pos)
        self.assertLess(mid_pos, cmd2_pos)
        self.assertIn("Start priority", r.stdout)
        self.assertIn("Single source of truth", r.stdout)
        self.assertIn("Language policy", r.stdout)

        init_dir = self.tmp / "init_proj"
        init_dir.mkdir()
        ri = subprocess.run([str(SCRIPT), "--init"], cwd=str(init_dir), capture_output=True, text=True, check=False)
        self.assertEqual(ri.returncode, 0, ri.stderr)
        init_lines = [
            ln.strip()
            for ln in (init_dir / ".agents_bundle").read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        bundle_idxs = [idx for idx, ln in enumerate(init_lines) if ln.startswith("bundle ")]
        non_bundle_idxs = [idx for idx, ln in enumerate(init_lines) if not ln.startswith("bundle ")]
        self.assertGreaterEqual(len(bundle_idxs), 3)
        self.assertLess(max(bundle_idxs), min(non_bundle_idxs))

    def _git(self, repo, *args):
        r = subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, msg=r.stderr)
        return r.stdout.strip()

    def test_update_cache_resets_git_packages_to_rewritten_remote(self):
        upstream = self.tmp / "upstream"
        upstream.mkdir()
        self._git(upstream, "init", "-q")
        self._git(upstream, "symbolic-ref", "HEAD", "refs/heads/main")
        (upstream / "f.txt").write_text("v1\n", encoding="utf-8")
        self._git(upstream, "add", "f.txt")
        self._git(upstream, "commit", "-q", "-m", "v1")
        clone = self.tmp / "cache" / "packages" / "owner" / "repo"
        clone.parent.mkdir(parents=True)
        self._git(self.tmp, "clone", "-q", "--depth", "1", upstream.as_uri(), str(clone))

        (upstream / "f.txt").write_text("v2\n", encoding="utf-8")
        self._git(upstream, "add", "f.txt")
        self._git(upstream, "commit", "-q", "--amend", "-m", "v2")
        new_head = self._git(upstream, "rev-parse", "--short", "HEAD")

        r1 = subprocess.run([str(SCRIPT), "--update-cache"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(r1.returncode, 0, msg=r1.stderr)
        self.assertIn("package owner/repo: updated", r1.stdout)
        self.assertIn(new_head, r1.stdout)
        self.assertEqual((clone / "f.txt").read_text(encoding="utf-8"), "v2\n")

        r2 = subprocess.run([str(SCRIPT), "--update-cache"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(r2.returncode, 0, msg=r2.stderr)
        self.assertIn("package owner/repo: up to date", r2.stdout)

    def test_update_cache_refreshes_url_files(self):
        url_rule = self.tmp / "remote_rule.md"
        url_rule.write_text("# Description: R\n- Remote rule body one.\n", encoding="utf-8")
        cmd = [str(SCRIPT), "rule", url_rule.as_uri()]
        r1 = subprocess.run(cmd, cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(r1.returncode, 0, msg=r1.stderr)
        self.assertIn("Remote rule body one.", r1.stdout)

        url_rule.write_text("# Description: R\n- Remote rule body two.\n", encoding="utf-8")
        ru = subprocess.run([str(SCRIPT), "--update-cache"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(ru.returncode, 0, msg=ru.stderr)
        self.assertIn(f"url {url_rule.as_uri()}: updated", ru.stdout)

        r2 = subprocess.run(cmd, cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertIn("Remote rule body two.", r2.stdout)

        ru2 = subprocess.run([str(SCRIPT), "--update-cache"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertIn(f"url {url_rule.as_uri()}: unchanged", ru2.stdout)

    def test_refresh_fetches_each_remote_once_per_run(self):
        hits = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                body = b"# Description: Served\n- Served rule body.\n"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/served.md"
            (self.tmp / ".agents_bundle").write_text(f"rule {url}\nrule {url}\n", encoding="utf-8")
            r = subprocess.run([str(SCRIPT), "--refresh"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        self.assertEqual(r.returncode, 0, msg=r.stderr)
        self.assertIn("Served rule body.", r.stdout)
        self.assertEqual(hits, ["/served.md"])

    def test_no_implicit_home_package_fallback(self):
        home = self.tmp / "home"
        rule_dir = home / "agents-rules" / "rules" / "core"
        rule_dir.mkdir(parents=True)
        (rule_dir / "ssot.md").write_text("# Description: S\n- Home fallback body.\n", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != "AGENTS_BUNDLE_LOCAL_PKG_DIR"}
        env.update(
            {
                "HOME": str(home),
                "USERPROFILE": str(home),
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "url.file:///nonexistent/.insteadOf",
                "GIT_CONFIG_VALUE_0": "https://github.com/",
            }
        )
        r = subprocess.run(
            [str(SCRIPT), "rule", "vitalio/agents-rules:core/ssot"],
            cwd=str(self.tmp),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Home fallback body", r.stdout)
        self.assertIn("failed to fetch package", r.stderr)

    def test_piped_workdir_preamble_and_dir_priority(self):
        proj = self.tmp / "target_proj"
        proj.mkdir()
        (proj / "AGENTS.md").write_text("# Target Project Rules\n", encoding="utf-8")
        (proj / "note.txt").write_text("hello from target\n", encoding="utf-8")
        (proj / ".agents_bundle").write_text(
            "ruleset vitalio/agents-rules:core\n"
            "$ cat AGENTS.md\n"
            "$ agents_bundle --tree\n"
            "$ pwd\n",
            encoding="utf-8",
        )

        # Piped Key: Value preamble maps Workdir and non-transport headers to lowercase vars
        piped = (
            f"Bundle-Command: todo_md F18\n"
            f"Bundle-Boundary: nonce123\n"
            f"Project: demo\n"
            f"Task: F18\n"
            f"Role: execute\n"
            f"Chat-Lang: Spanish\n"
            f"Workdir: {proj}\n"
            f"\n"
            f"# TODO.md:1\n"
            f"- Details here\n"
        )
        r = subprocess.run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            input=piped,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, msg=r.stderr)
        self.assertIn(f"Workdir: {proj.resolve()}\n", r.stdout)
        self.assertIn("Project: demo\n", r.stdout)
        self.assertIn("Task: F18\n", r.stdout)
        self.assertIn("Role: execute\n", r.stdout)
        self.assertIn("Chat-Lang: Spanish\n", r.stdout)
        self.assertNotIn("Bundle-Boundary: nonce123", r.stdout)
        self.assertNotIn("Bundle-Command: todo_md", r.stdout)
        self.assertIn("===== $ cat AGENTS.md =====\n# Target Project Rules\n", r.stdout)
        self.assertIn("note.txt", r.stdout)
        self.assertIn(f"===== $ pwd =====\n{proj.resolve()}\n", r.stdout)
        self.assertIn("===== Prompt =====\n# TODO.md:1\n- Details here", r.stdout)

        # CLI k=v and AGENTS_BUNDLE_VARS override piped preamble headers
        env_ovr = {**os.environ, "AGENTS_BUNDLE_VARS": "role=plan task=F10"}
        r_vars = subprocess.run(
            [str(SCRIPT), "task=F99"],
            cwd=str(self.tmp),
            env=env_ovr,
            input=piped,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_vars.returncode, 0, msg=r_vars.stderr)
        self.assertIn("Task: F99\n", r_vars.stdout)
        self.assertIn("Role: plan\n", r_vars.stdout)

        # Piped Workdir with empty body or bare task ID
        r_empty = subprocess.run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            input=f"Workdir: {proj}\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_empty.returncode, 0, msg=r_empty.stderr)
        self.assertIn(f"Workdir: {proj.resolve()}\n", r_empty.stdout)
        self.assertNotIn("===== Prompt =====", r_empty.stdout)

        r_bare_id = subprocess.run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            input=f"Workdir: {proj}\n\nF21\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_bare_id.returncode, 0, msg=r_bare_id.stderr)
        self.assertIn("Task: F21\n", r_bare_id.stdout)
        self.assertIn(f"Workdir: {proj.resolve()}\n", r_bare_id.stdout)
        self.assertNotIn("===== Prompt =====", r_bare_id.stdout)

        # Explicit -C/--dir takes priority over piped Workdir while preserving other headers
        override_proj = self.tmp / "override_proj"
        override_proj.mkdir()
        (override_proj / "AGENTS.md").write_text("# Override Rules\n", encoding="utf-8")
        (override_proj / ".agents_bundle").write_text(
            "ruleset vitalio/agents-rules:core\n"
            "$ cat AGENTS.md\n",
            encoding="utf-8",
        )
        r_override = subprocess.run(
            [str(SCRIPT), "-C", str(override_proj)],
            cwd=str(self.tmp),
            input="Workdir: /nonexistent/ignored/path\nTask: F19\n\n# Body\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_override.returncode, 0, msg=r_override.stderr)
        self.assertIn(f"Workdir: {override_proj.resolve()}\n", r_override.stdout)
        self.assertIn("# Override Rules", r_override.stdout)
        self.assertIn("Task: F19\n", r_override.stdout)

        # Key: Value line without blank separator before non-header body stays in Prompt
        r_note = subprocess.run(
            [str(SCRIPT), "-C", str(proj)],
            cwd=str(self.tmp),
            input="Note: keep this line\nMore prompt details\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r_note.returncode, 0, msg=r_note.stderr)
        self.assertIn("===== Prompt =====\nNote: keep this line\nMore prompt details\n", r_note.stdout)

        # Builtin piped=1 is set only when stdin prompt text is present (and not emitted as header)
        piped_guard_proj = self.tmp / "piped_guard_proj"
        piped_guard_proj.mkdir()
        (piped_guard_proj / ".agents_bundle").write_text(
            "[if piped!=1] $ echo fetch_from_tracker\n"
            "[if piped=1] $ echo already_piped\n",
            encoding="utf-8",
        )
        for label, stdin_val, expect_piped in [
            ("no_stdin", None, False),
            ("bare_id", "F20\n", False),
            ("headers_only", "Task: F20\nRole: execute\n", False),
            ("headers_and_body", "Task: F20\n\n# TODO.md:1\nTask details\n", True),
        ]:
            with self.subTest(piped_case=label):
                rp = subprocess.run(
                    [str(SCRIPT), "-C", str(piped_guard_proj)],
                    cwd=str(self.tmp),
                    input=stdin_val,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(rp.returncode, 0, msg=rp.stderr)
                self.assertNotIn("Piped:", rp.stdout)
                if expect_piped:
                    self.assertIn("already_piped", rp.stdout)
                    self.assertNotIn("fetch_from_tracker", rp.stdout)
                else:
                    self.assertIn("fetch_from_tracker", rp.stdout)
                    self.assertNotIn("already_piped", rp.stdout)

        # Missing, empty, or non-directory Workdir fails cleanly
        missing = self.tmp / "does_not_exist"
        for label, args, stdin_val in [
            ("missing_cli", ["-C", str(missing)], None),
            ("missing_piped", [], f"Workdir: {missing}\n"),
            ("empty_piped", [], "Workdir:   \n"),
            ("file_not_dir", ["-C", str(proj / "note.txt")], None),
        ]:
            with self.subTest(case=label):
                r_err = subprocess.run(
                    [str(SCRIPT), *args],
                    cwd=str(self.tmp),
                    input=stdin_val,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(r_err.returncode, 0, msg=r_err.stdout)
                self.assertTrue(r_err.stderr.strip(), msg="expected error message on stderr")


    def test_bundle_boundary_nonce_and_expose_control(self):
        sub_bundle = self.tmp / "extra.bundle"
        sub_bundle.write_text(
            "expose project_id\n"
            "[if role=execute] expose work_item, role\n",
            encoding="utf-8",
        )
        (self.tmp / ".agents_bundle").write_text(
            "ruleset vitalio/agents-rules:core\n"
            "expose chat_lang custom-key\n"
            "expose {opt_hdr:}\n"
            f"bundle {sub_bundle.as_posix()}\n",
            encoding="utf-8",
        )

        # Default + expose directives without AGENTS_BUNDLE_EXPOSE; unexposed vars stay out of Bundle-Expose
        r1 = subprocess.run(
            [str(SCRIPT), "role=execute", "task=F19", "lang=German", "chat_lang=French", "project_id=demo"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r1.returncode, 0, msg=r1.stderr)
        self.assertIn(
            "Bundle-Expose: Role, Task, Chat-Lang, Custom-Key, Project-Id, Work-Item\n",
            r1.stdout,
        )
        self.assertIn("Lang: German\n", r1.stdout)
        m1 = re.search(r"^Bundle-Boundary: ([0-9a-f]+)$", r1.stdout, flags=re.MULTILINE)
        self.assertIsNotNone(m1, msg=r1.stdout)

        # Second run generates a distinct nonce and excludes conditional expose when condition is false
        env_exp = {**os.environ, "AGENTS_BUNDLE_EXPOSE": "build_id, chat-lang, trace_tag"}
        r2 = subprocess.run(
            [str(SCRIPT), "role=plan", "opt_hdr=extra_scope"],
            cwd=str(self.tmp),
            env=env_exp,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r2.returncode, 0, msg=r2.stderr)
        self.assertIn(
            "Bundle-Expose: Role, Task, Chat-Lang, Custom-Key, Extra-Scope, Project-Id, Build-Id, Trace-Tag\n",
            r2.stdout,
        )
        m2 = re.search(r"^Bundle-Boundary: ([0-9a-f]+)$", r2.stdout, flags=re.MULTILINE)
        self.assertIsNotNone(m2, msg=r2.stdout)
        self.assertNotEqual(m1.group(1), m2.group(1))

        # Invalid AGENTS_BUNDLE_EXPOSE or expose key fails explicitly
        bad_env = {**os.environ, "AGENTS_BUNDLE_EXPOSE": "bad=key"}
        r_bad = subprocess.run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            env=bad_env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_bad.returncode, 0)
        self.assertIn("AGENTS_BUNDLE_EXPOSE", r_bad.stderr)

        (self.tmp / ".agents_bundle").write_text("expose bad=key\n", encoding="utf-8")
        r_bad_spec = subprocess.run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_bad_spec.returncode, 0)
        self.assertIn(".agents_bundle", r_bad_spec.stderr)


if __name__ == "__main__":
    unittest.main()
