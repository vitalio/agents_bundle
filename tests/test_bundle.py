#!/usr/bin/env python3
"""Bundle assembly, directives, headers, and fragment marker tests for agents_bundle."""
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests.helpers import AgentsBundleTestCase, SCRIPT


class TestBundle(AgentsBundleTestCase):
    def test_ruleset_rule_if_conditions_and_dollar_commands(self):
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
        rb = self._run(
            [str(SCRIPT), "extra.txt", "-p", "Solve task 1"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(rb)
        self.assertIn("Bundle-Command: agents_bundle extra.txt -p 'Solve task 1'", rb.stdout)
        self.assertIn("===== Rules =====", rb.stdout)
        self.assertNotIn("# [ruleset", rb.stdout)
        self.assertIn("in Spanish", rb.stdout)
        self.assertNotIn("Clean external text & two-step external changes:", rb.stdout)
        self.assertIn("Linux & POSIX shell rules:", rb.stdout)
        self.assertNotIn("Windows & PowerShell 7+ (`pwsh`) rules:", rb.stdout)
        self.assertIn("Python 3.12+ compatibility", rb.stdout)

        # Verify -v / --verbose includes provenance trace comments with [if ...]
        rb_v = self._run(
            [str(SCRIPT), "-v"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(rb_v)
        self.assertIn("# [ruleset vitalio/agents-rules:core -> rules/core/start.md]", rb_v.stdout)
        self.assertIn(f"# [[if os={cur_os}] rule vitalio/agents-rules:os/linux -> rules/os/linux.md]", rb_v.stdout)
        self.assertIn(f"# [[if os={cur_os}] rule vitalio/agents-rules:stack/python-cli -> rules/stack/python-cli.md] (py_min=3.12)", rb_v.stdout)

        # Verify direct URL rule and ruleset loading
        url_rule = self.tmp / "custom_url_rule.md"
        url_rule.write_text("# Description: Direct URL rule\n- **Direct URL invariant:** Loaded from URL {val:42}.\n", encoding="utf-8")
        url_ruleset = self.tmp / "custom_url.ruleset"
        url_ruleset.write_text(f"# Description: Direct URL ruleset\nrule {url_rule.as_uri()} val=99\n", encoding="utf-8")
        r_url = self._run(
            [str(SCRIPT), "ruleset", url_ruleset.as_uri()],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_url)
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
        r_none = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self._assert_ok(r_none)
        self.assertIn("Context bundler & rules engine", r_none.stdout)
        self.assertIn("Task management (`todo_md`)", r_none.stdout)
        self.assertNotIn("all_tasks", r_none.stdout)
        self.assertNotIn("focused_task_", r_none.stdout)
        self.assertNotIn("===== Prompt =====", r_none.stdout)

        r_plan = self._run([str(SCRIPT), "role=plan"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self._assert_ok(r_plan)
        self.assertIn("Bundle-Command: agents_bundle role=plan\n", r_plan.stdout)
        self.assertIn("Bundle-Expose: Role, Task, Title\n", r_plan.stdout)
        self.assertIn("Role: plan\n", r_plan.stdout)
        self.assertIn("all_tasks", r_plan.stdout)
        self.assertNotIn("focused_task_", r_plan.stdout)
        self.assertIn("===== Prompt =====\nMode: PLANNING", r_plan.stdout)

        r_exec = self._run([str(SCRIPT), "role=execute"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self._assert_ok(r_exec)
        self.assertIn("Bundle-Command: agents_bundle role=execute\n", r_exec.stdout)
        self.assertIn("Bundle-Expose: Role, Task, Title\n", r_exec.stdout)
        self.assertIn("Role: execute\n", r_exec.stdout)
        self.assertIn("all_tasks", r_exec.stdout)
        self.assertNotIn("focused_task_", r_exec.stdout)
        self.assertIn("===== Prompt =====\nMode: EXECUTION", r_exec.stdout)

        r_foc = self._run(
            [str(SCRIPT), "role=execute", "task=A2", "lang=German", "-p", "Focus on edge cases"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_foc)
        self.assertIn("Bundle-Command: agents_bundle role=execute task=A2 lang=German -p 'Focus on edge cases'", r_foc.stdout)
        self.assertIn("Role: execute\nTask: A2\nLang: German\n", r_foc.stdout)
        self.assertIn("focused_task_A2", r_foc.stdout)
        self.assertNotIn("all_tasks", r_foc.stdout)
        self.assertIn("in German", r_foc.stdout)
        self.assertIn("===== Prompt =====\nMode: EXECUTION (A2)\n\nFocus on edge cases", r_foc.stdout)

    def test_agents_bundle_vars_env_and_cli_override(self):
        (self.tmp / ".agents_bundle").write_text(
            "ruleset vitalio/agents-rules:core lang=English\n"
            "[if mode=custom] prompt Custom mode active ({chat_lang:default})\n",
            encoding="utf-8",
        )
        env = {**os.environ, "AGENTS_BUNDLE_VARS": "lang=Spanish mode=custom chat_lang=French"}
        r_env = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, env=env, check=False)
        self._assert_ok(r_env)
        self.assertIn("Bundle-Command: agents_bundle\n", r_env.stdout)
        self.assertIn("Bundle-Expose: Role, Task, Title\n", r_env.stdout)
        self.assertIn("Lang: Spanish\nMode: custom\nChat-Lang: French\n", r_env.stdout)
        self.assertIn("in Spanish", r_env.stdout)
        self.assertIn("Custom mode active (French)", r_env.stdout)

        # CLI key=val overrides AGENTS_BUNDLE_VARS
        r_cli = self._run(
            [str(SCRIPT), "lang=German", "chat_lang=Italian"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self._assert_ok(r_cli)
        self.assertIn("in German", r_cli.stdout)
        self.assertIn("Custom mode active (Italian)", r_cli.stdout)

        # Subcommand ruleset/rule also respects AGENTS_BUNDLE_VARS and CLI override
        r_sub = self._run(
            [str(SCRIPT), "rule", "vitalio/agents-rules:core/lang"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self._assert_ok(r_sub)
        self.assertIn("in Spanish", r_sub.stdout)

        r_sub_cli = self._run(
            [str(SCRIPT), "rule", "vitalio/agents-rules:core/lang", "lang=Japanese"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self._assert_ok(r_sub_cli)
        self.assertIn("in Japanese", r_sub_cli.stdout)

        # Invalid AGENTS_BUNDLE_VARS token fails explicitly
        bad_env = {**os.environ, "AGENTS_BUNDLE_VARS": "not_a_pair"}
        r_bad = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, env=bad_env, check=False)
        self.assertNotEqual(r_bad.returncode, 0, msg=f"stdout:\n{r_bad.stdout}\nstderr:\n{r_bad.stderr}")
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
        r_dyn = self._run(
            [str(SCRIPT), "role=execute"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_dyn)
        self.assertIn("Role: execute\nTask: F7\n", r_dyn.stdout)
        self.assertIn("===== $ cat src/target.py =====\nVALUE = 42\n", r_dyn.stdout)
        self.assertIn("===== Prompt =====\nExecuting F7\n", r_dyn.stdout)
        self.assertEqual(r_dyn.stderr, "")

        # Explicit task=<ID> overrides var directive fallback
        r_explicit = self._run(
            [str(SCRIPT), "role=execute", "task=F9"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_explicit)
        self.assertIn("Role: execute\nTask: F9\n", r_explicit.stdout)
        self.assertIn("===== Prompt =====\nExecuting F9\n", r_explicit.stdout)

        # Piped Task preamble on stdin maps task variable and includes body in Prompt
        piped_task = "Task: F12\n\n# 🎯 [NEXT] F12: Piped task title\n\n- Target file: `src/target.py`\n"
        r_pipe = self._run(
            [str(SCRIPT), "role=execute"],
            cwd=str(self.tmp),
            input=piped_task,
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_pipe)
        self.assertIn("Role: execute\nTask: F12\n", r_pipe.stdout)
        self.assertIn("===== Prompt =====\nExecuting F12\n\n# 🎯 [NEXT] F12: Piped task title", r_pipe.stdout)

        # Markdown heading without Task preamble does not infer task via hardcoded regex
        r_no_regex = self._run(
            [str(SCRIPT), "role=execute"],
            cwd=str(self.tmp),
            input="# 🎯 [NEXT] F99: Plain markdown body\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_no_regex)
        self.assertIn("Role: execute\nTask: F7\n", r_no_regex.stdout)
        self.assertIn("# 🎯 [NEXT] F99: Plain markdown body", r_no_regex.stdout)

        # Piped bare task ID on stdin infers task ID without polluting Prompt
        r_pipe_id = self._run(
            [str(SCRIPT), "role=execute"],
            cwd=str(self.tmp),
            input="F15\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_pipe_id)
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
        r = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self._assert_ok(r)
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
        r = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self._assert_ok(r)
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
        ri = self._run([str(SCRIPT), "--init"], cwd=str(init_dir), capture_output=True, text=True, check=False)
        self._assert_ok(ri)
        init_lines = [
            ln.strip()
            for ln in (init_dir / ".agents_bundle").read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        bundle_idxs = [idx for idx, ln in enumerate(init_lines) if ln.startswith("bundle ")]
        non_bundle_idxs = [idx for idx, ln in enumerate(init_lines) if not ln.startswith("bundle ")]
        self.assertEqual(len(bundle_idxs), 2)
        self.assertIn("bundle vitalio/agents_bundle", init_lines)
        self.assertIn("bundle vitalio/todo_md", init_lines)
        self.assertNotIn("bundle vitalio/run_block", init_lines)
        self.assertLess(max(bundle_idxs), min(non_bundle_idxs))

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
            f"Title: Demo task title\n"
            f"Role: execute\n"
            f"Chat-Lang: Spanish\n"
            f"Workdir: {proj}\n"
            f"\n"
            f"# TODO.md:1\n"
            f"- Details here\n"
        )
        r = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            input=piped,
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r)
        self.assertIn(f"Workdir: {proj.resolve()}\n", r.stdout)
        self.assertIn("Project: demo\n", r.stdout)
        self.assertIn("Bundle-Expose: Role, Task, Title\n", r.stdout)
        self.assertIn("Task: F18\n", r.stdout)
        self.assertIn("Title: Demo task title\n", r.stdout)
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
        r_vars = self._run(
            [str(SCRIPT), "task=F99"],
            cwd=str(self.tmp),
            env=env_ovr,
            input=piped,
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_vars)
        self.assertIn("Task: F99\n", r_vars.stdout)
        self.assertIn("Role: plan\n", r_vars.stdout)

        # Piped Workdir with empty body or bare task ID
        r_empty = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            input=f"Workdir: {proj}\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_empty)
        self.assertIn(f"Workdir: {proj.resolve()}\n", r_empty.stdout)
        self.assertNotIn("===== Prompt =====", r_empty.stdout)

        r_bare_id = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            input=f"Workdir: {proj}\n\nF21\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_bare_id)
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
        r_override = self._run(
            [str(SCRIPT), "-C", str(override_proj)],
            cwd=str(self.tmp),
            input="Workdir: /nonexistent/ignored/path\nTask: F19\n\n# Body\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_override)
        self.assertIn(f"Workdir: {override_proj.resolve()}\n", r_override.stdout)
        self.assertIn("# Override Rules", r_override.stdout)
        self.assertIn("Task: F19\n", r_override.stdout)

        # Key: Value line without blank separator before non-header body stays in Prompt
        r_note = self._run(
            [str(SCRIPT), "-C", str(proj)],
            cwd=str(self.tmp),
            input="Note: keep this line\nMore prompt details\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_note)
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
                rp = self._run(
                    [str(SCRIPT), "-C", str(piped_guard_proj)],
                    cwd=str(self.tmp),
                    input=stdin_val,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self._assert_ok(rp)
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
                r_err = self._run(
                    [str(SCRIPT), *args],
                    cwd=str(self.tmp),
                    input=stdin_val,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(r_err.returncode, 0, msg=f"stdout:\n{r_err.stdout}\nstderr:\n{r_err.stderr}")
                self.assertTrue(r_err.stderr.strip(), msg="expected error message on stderr")

    def test_empty_piped_fifo_fails_fast_but_devnull_is_allowed(self):
        proj = self.tmp / "empty_pipe_proj"
        proj.mkdir()
        (proj / ".agents_bundle").write_text("$ echo marker_should_not_run\n", encoding="utf-8")
        for label, data in [("empty", ""), ("whitespace", "  \n")]:
            with self.subTest(fifo_case=label):
                r_fifo = self._run_subprocess([str(SCRIPT), "-C", str(proj)], cwd=self.tmp, input=data)
                self.assertEqual(r_fifo.returncode, 2, msg=f"stdout:\n{r_fifo.stdout}\nstderr:\n{r_fifo.stderr}")
                self.assertEqual(r_fifo.stdout, "")
                self.assertIn("empty piped input on stdin", r_fifo.stderr)
        r_null = subprocess.run(
            [str(SCRIPT), "-C", str(proj)],
            cwd=str(self.tmp),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_null)
        self.assertIn("marker_should_not_run", r_null.stdout)

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
        r1 = self._run(
            [str(SCRIPT), "role=execute", "task=F19", "title=Expose check", "lang=German", "chat_lang=French", "project_id=demo"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r1)
        self.assertIn(
            "Bundle-Expose: Role, Task, Title, Chat-Lang, Custom-Key, Project-Id, Work-Item\n",
            r1.stdout,
        )
        self.assertIn("Title: Expose check\n", r1.stdout)
        self.assertIn("Lang: German\n", r1.stdout)
        m1 = re.search(r"^Bundle-Boundary: ([0-9a-f]+)$", r1.stdout, flags=re.MULTILINE)
        self.assertIsNotNone(m1, msg=r1.stdout)

        # Second run generates a distinct nonce and excludes conditional expose when condition is false
        env_exp = {**os.environ, "AGENTS_BUNDLE_EXPOSE": "build_id, chat-lang, trace_tag"}
        r2 = self._run(
            [str(SCRIPT), "role=plan", "opt_hdr=extra_scope"],
            cwd=str(self.tmp),
            env=env_exp,
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r2)
        self.assertIn(
            "Bundle-Expose: Role, Task, Title, Chat-Lang, Custom-Key, Extra-Scope, Project-Id, Build-Id, Trace-Tag\n",
            r2.stdout,
        )
        m2 = re.search(r"^Bundle-Boundary: ([0-9a-f]+)$", r2.stdout, flags=re.MULTILINE)
        self.assertIsNotNone(m2, msg=r2.stdout)
        self.assertNotEqual(m1.group(1), m2.group(1))

        # Invalid AGENTS_BUNDLE_EXPOSE or expose key fails explicitly
        bad_env = {**os.environ, "AGENTS_BUNDLE_EXPOSE": "bad=key"}
        r_bad = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            env=bad_env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_bad.returncode, 0, msg=f"stdout:\n{r_bad.stdout}\nstderr:\n{r_bad.stderr}")
        self.assertIn("AGENTS_BUNDLE_EXPOSE", r_bad.stderr)

        (self.tmp / ".agents_bundle").write_text("expose bad=key\n", encoding="utf-8")
        r_bad_spec = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_bad_spec.returncode, 0, msg=f"stdout:\n{r_bad_spec.stdout}\nstderr:\n{r_bad_spec.stderr}")
        self.assertIn(".agents_bundle", r_bad_spec.stderr)

    def test_source_provenance_and_command_telemetry(self):
        mod = self._load_bundle_module()

        leaf_bundle = self.tmp / "leaf.bundle"
        leaf_bundle.write_text(
            "ruleset vitalio/agents-rules:default\n"
            "include leaf_note.txt\n"
            "$ printf leaf_ok\n"
            "prompt Leaf prompt\n",
            encoding="utf-8",
        )
        top_bundle = self.tmp / "top.bundle"
        top_bundle.write_text(
            "rule vitalio/agents-rules:stack/python-cli\n"
            f"bundle {leaf_bundle.as_posix()}\n",
            encoding="utf-8",
        )
        (self.tmp / "leaf_note.txt").write_text("leaf note\n", encoding="utf-8")
        (self.tmp / "root_note.txt").write_text("root note\n", encoding="utf-8")
        (self.tmp / "cli_note.txt").write_text("cli note\n", encoding="utf-8")

        spec_text = (
            "rule vitalio/agents-rules:release/single-file-build\n"
            f"bundle {top_bundle.as_posix()}\n"
            "include root_note.txt\n"
            "$ printf root_ok\n"
            "$ exit 7\n"
            "prompt Root prompt\n"
        )
        (self.tmp / ".agents_bundle").write_text(spec_text, encoding="utf-8")

        # 1. Verify parse_spec preserves full multi-hop chain (root=[] vs nested bundles)
        parsed = mod.parse_spec(spec_text, work_dir=self.tmp)
        by_val = {(kind, val): chain for kind, val, _cond, chain in parsed}
        self.assertEqual(
            by_val[("directive", "rule vitalio/agents-rules:release/single-file-build")],
            [],
        )
        self.assertEqual(by_val[("include", "root_note.txt")], [])
        self.assertEqual(by_val[("cmd", "printf root_ok")], [])
        self.assertEqual(by_val[("prompt", "Root prompt")], [])

        top_ref = top_bundle.as_posix()
        leaf_ref = leaf_bundle.as_posix()
        self.assertEqual(by_val[("directive", "rule vitalio/agents-rules:stack/python-cli")], [top_ref])
        self.assertEqual(by_val[("directive", "ruleset vitalio/agents-rules:default")], [top_ref, leaf_ref])
        self.assertEqual(by_val[("include", "leaf_note.txt")], [top_ref, leaf_ref])
        self.assertEqual(by_val[("cmd", "printf leaf_ok")], [top_ref, leaf_ref])
        self.assertEqual(by_val[("prompt", "Leaf prompt")], [top_ref, leaf_ref])

        # 2. Verify collect_directive_items preserves full multi-hop chain across nested rulesets
        items = mod.collect_directive_items(
            "ruleset",
            "vitalio/agents-rules:default",
            work_dir=self.tmp,
            chain=[top_ref, leaf_ref],
        )
        self.assertTrue(len(items) >= 2)
        by_uid = {uid: chain for uid, _prov, _body, chain in items}
        self.assertEqual(
            by_uid["vitalio/agents-rules:core/start"],
            [top_ref, leaf_ref, "vitalio/agents-rules:default", "vitalio/agents-rules:core"],
        )

        # 3. Verify _run_spec_command captures exit code (rc) and integer duration (ms)
        rc_ok, out_ok, ms_ok = mod._run_spec_command(f'"{sys.executable}" -c "import time; time.sleep(0.02); print(123)"', self.tmp)
        self.assertEqual(rc_ok, 0)
        self.assertEqual(out_ok, "123")
        self.assertIsInstance(ms_ok, int)
        self.assertGreaterEqual(ms_ok, 10)

        rc_fail, _out_fail, ms_fail = mod._run_spec_command("exit 5", self.tmp)
        self.assertEqual(rc_fail, 5)
        self.assertIsInstance(ms_fail, int)
        self.assertGreaterEqual(ms_fail, 0)

        # 4. Verify build_bundle records neutral provenance chain and command telemetry (rc/ms)
        records: list[dict[str, object]] = []
        body, warnings = mod.build_bundle(
            work_dir=self.tmp,
            extra_files=["cli_note.txt"],
            prompt_text="CLI prompt",
            records=records,
        )
        self.assertIn("command exited 7: exit 7", warnings)
        self.assertIn("leaf_ok", body)
        self.assertIn("root_ok", body)
        for rec in records:
            self.assertNotIn("group", rec)
            self.assertNotIn("via", rec)

        rule_recs = {r["id"]: r for r in records if r["kind"] == "rule"}
        self.assertEqual(
            rule_recs["vitalio/agents-rules:release/single-file-build"],
            {
                "kind": "rule",
                "id": "vitalio/agents-rules:release/single-file-build",
                "chain": [],
            },
        )
        self.assertEqual(
            rule_recs["vitalio/agents-rules:stack/python-cli"],
            {
                "kind": "rule",
                "id": "vitalio/agents-rules:stack/python-cli",
                "chain": [top_ref],
            },
        )
        self.assertEqual(
            rule_recs["vitalio/agents-rules:core/start"],
            {
                "kind": "rule",
                "id": "vitalio/agents-rules:core/start",
                "chain": [top_ref, leaf_ref, "vitalio/agents-rules:default", "vitalio/agents-rules:core"],
            },
        )

        cmd_recs = {r["name"]: r for r in records if r["kind"] == "cmd"}
        self.assertEqual(cmd_recs["printf leaf_ok"]["chain"], [top_ref, leaf_ref])
        self.assertEqual(cmd_recs["printf leaf_ok"]["rc"], 0)
        self.assertIsInstance(cmd_recs["printf leaf_ok"]["ms"], int)
        self.assertGreaterEqual(cmd_recs["printf leaf_ok"]["ms"], 0)

        self.assertEqual(cmd_recs["printf root_ok"]["chain"], [])
        self.assertEqual(cmd_recs["printf root_ok"]["rc"], 0)
        self.assertEqual(cmd_recs["exit 7"]["chain"], [])
        self.assertEqual(cmd_recs["exit 7"]["rc"], 7)
        self.assertIsInstance(cmd_recs["exit 7"]["ms"], int)

        inc_recs = {r["name"]: r for r in records if r["kind"] == "include"}
        self.assertEqual(inc_recs["leaf_note.txt"]["chain"], [top_ref, leaf_ref])
        self.assertEqual(inc_recs["root_note.txt"]["chain"], [])
        self.assertEqual(inc_recs["cli_note.txt"]["chain"], [])

        prompt_recs = [r for r in records if r["kind"] == "prompt"]
        self.assertEqual([r["chain"] for r in prompt_recs], [[top_ref, leaf_ref], [], []])

        # Merged prompt with mixed chains emits chain=[], while shared non-empty chain emits shared chain
        _, mixed_frags = self._extract_fragments(body)
        mixed_prompt_meta = [m for m, _b in mixed_frags if m["kind"] == "prompt"][0]
        self.assertEqual(mixed_prompt_meta, {"kind": "prompt", "chain": []})

        shared_bundle = self.tmp / "shared_prompt.bundle"
        shared_bundle.write_text("prompt First\nprompt Second\n", encoding="utf-8")
        shared_ref = shared_bundle.as_posix()
        (self.tmp / ".agents_bundle").write_text(f"bundle {shared_ref}\n", encoding="utf-8")
        shared_body, _ = mod.build_bundle(work_dir=self.tmp)
        _, shared_frags = self._extract_fragments(shared_body)
        shared_prompt_meta = [m for m, _b in shared_frags if m["kind"] == "prompt"][0]
        self.assertEqual(shared_prompt_meta, {"kind": "prompt", "chain": [shared_ref]})

    def test_json_fragment_markers_for_all_kinds(self):
        pkg_dir = Path(os.environ["AGENTS_BUNDLE_LOCAL_PKG_DIR"])
        (pkg_dir / "rules" / "core" / "multiline.md").write_text(
            "# Description: Multiline rule\n"
            "- Multiline rule header:\n"
            "  - Bullet one\n"
            "  - Bullet two\n",
            encoding="utf-8",
        )
        (self.tmp / "sub.bundle").write_text(
            "rule vitalio/agents-rules:core/multiline\n"
            "rule vitalio/agents-rules:core/start\n"
            "include sub_doc.txt\n"
            "$ printf 'sub_line_1\\nsub_line_2\\n'\n",
            encoding="utf-8",
        )
        (self.tmp / "sub_doc.txt").write_text("sub doc line 1\nsub doc line 2\n", encoding="utf-8")
        (self.tmp / "root_doc.txt").write_text("root doc body\n", encoding="utf-8")
        (self.tmp / "cli_doc.txt").write_text("cli doc body\n", encoding="utf-8")
        (self.tmp / ".agents_bundle").write_text(
            "ruleset vitalio/agents-rules:core\n"
            f"bundle {(self.tmp / 'sub.bundle').as_posix()}\n"
            "include root_doc.txt\n"
            "$ printf 'line1\\nline2\\n'\n"
            "$ echo 'arrow --> test'\n"
            "$ true\n"
            "$ exit 3\n"
            "prompt Line one\n"
            "prompt Line two\n",
            encoding="utf-8",
        )

        r = self._run(
            [str(SCRIPT), "cli_doc.txt", "-p", "CLI prompt line"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r)
        nonce, fragments = self._extract_fragments(r.stdout)
        self.assertTrue(len(nonce) >= 16)

        # Verify no fragment leaks .agents_bundle, group, or via
        for meta, _ in fragments:
            self.assertNotIn("group", meta)
            self.assertNotIn("via", meta)
            self.assertNotIn(".agents_bundle", meta["chain"])

        # Verify rule deduplication: core/start appears in core ruleset and sub.bundle, emitted once
        rule_frags = [(meta, body) for meta, body in fragments if meta["kind"] == "rule"]
        rule_ids = [meta["id"] for meta, _ in rule_frags]
        self.assertEqual(
            rule_ids,
            [
                "vitalio/agents-rules:core/start",
                "vitalio/agents-rules:core/ssot",
                "vitalio/agents-rules:core/lang",
                "vitalio/agents-rules:core/multiline",
            ],
        )
        by_rule_id = {meta["id"]: (meta, body) for meta, body in rule_frags}
        self.assertEqual(
            by_rule_id["vitalio/agents-rules:core/start"][0],
            {
                "kind": "rule",
                "id": "vitalio/agents-rules:core/start",
                "chain": ["vitalio/agents-rules:core"],
            },
        )
        sub_ref = (self.tmp / "sub.bundle").as_posix()
        multi_meta, multi_body = by_rule_id["vitalio/agents-rules:core/multiline"]
        self.assertEqual(
            multi_meta,
            {
                "kind": "rule",
                "id": "vitalio/agents-rules:core/multiline",
                "chain": [sub_ref],
            },
        )
        self.assertIn("- Multiline rule header:\n  - Bullet one\n  - Bullet two", multi_body)

        # Verify cmd fragments (multi-line output, comment-escaping, empty output, non-zero rc)
        cmd_frags = {meta["name"]: (meta, body) for meta, body in fragments if meta["kind"] == "cmd"}
        self.assertEqual(
            set(cmd_frags.keys()),
            {
                "printf 'sub_line_1\\nsub_line_2\\n'",
                "printf 'line1\\nline2\\n'",
                "echo 'arrow --> test'",
                "true",
                "exit 3",
            },
        )
        sub_cmd_meta, sub_cmd_body = cmd_frags["printf 'sub_line_1\\nsub_line_2\\n'"]
        self.assertEqual(sub_cmd_meta["chain"], [sub_ref])
        self.assertEqual(sub_cmd_meta["rc"], 0)
        self.assertIsInstance(sub_cmd_meta["ms"], int)
        self.assertGreaterEqual(sub_cmd_meta["ms"], 0)
        self.assertIn("sub_line_1\nsub_line_2", sub_cmd_body)

        arrow_meta, arrow_body = cmd_frags["echo 'arrow --> test'"]
        self.assertEqual(arrow_meta["rc"], 0)
        self.assertIn("===== $ echo 'arrow --> test' =====", arrow_body)

        true_meta, true_body = cmd_frags["true"]
        self.assertEqual(true_meta["rc"], 0)
        self.assertIn("===== $ true =====", true_body)

        exit_meta, _exit_body = cmd_frags["exit 3"]
        self.assertEqual(exit_meta["rc"], 3)
        self.assertEqual(exit_meta["chain"], [])

        # Verify include fragments across bundle, .agents_bundle, and CLI
        inc_frags = {meta["name"]: (meta, body) for meta, body in fragments if meta["kind"] == "include"}
        self.assertEqual(
            inc_frags["sub_doc.txt"][0],
            {"kind": "include", "name": "sub_doc.txt", "chain": [sub_ref]},
        )
        self.assertIn("sub doc line 1\nsub doc line 2", inc_frags["sub_doc.txt"][1])
        self.assertEqual(
            inc_frags["root_doc.txt"][0],
            {"kind": "include", "name": "root_doc.txt", "chain": []},
        )
        self.assertEqual(
            inc_frags["cli_doc.txt"][0],
            {"kind": "include", "name": "cli_doc.txt", "chain": []},
        )

        # Verify prompt fragment
        prompt_frags = [(meta, body) for meta, body in fragments if meta["kind"] == "prompt"]
        self.assertEqual(len(prompt_frags), 1)
        p_meta, p_body = prompt_frags[0]
        self.assertEqual(
            p_meta,
            {
                "kind": "prompt",
                "chain": [],
            },
        )
        self.assertIn("===== Prompt =====\nLine one\n\nLine two\n\nCLI prompt line", p_body)

        # Verify verbose mode keeps provenance comments inside rule fragment markers
        rv = self._run([str(SCRIPT), "-v"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self._assert_ok(rv)
        _, v_frags = self._extract_fragments(rv.stdout)
        v_rules = [body for meta, body in v_frags if meta["kind"] == "rule"]
        self.assertTrue(any("# [ruleset vitalio/agents-rules:core -> rules/core/start.md]" in b for b in v_rules))

        # Verify standalone ruleset/rule subcommands do not emit bundle fragment markers
        rs = self._run(
            [str(SCRIPT), "ruleset", "vitalio/agents-rules:core"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(rs)
        self.assertNotIn("<!-- bundle:", rs.stdout)

    def test_plain_flag_and_env_omit_transport_headers_and_markers(self):
        (self.tmp / "sub.bundle").write_text(
            "rule vitalio/agents-rules:core/start\n"
            "expose project_id\n"
            "$ printf 'sub_cmd_out\\n'\n",
            encoding="utf-8",
        )
        (self.tmp / "doc.txt").write_text("included doc line\n", encoding="utf-8")
        (self.tmp / ".agents_bundle").write_text(
            "ruleset vitalio/agents-rules:core\n"
            f"bundle {(self.tmp / 'sub.bundle').as_posix()}\n"
            "include doc.txt\n"
            "$ printf 'root_cmd_out\\n'\n"
            "prompt Plain mode prompt\n",
            encoding="utf-8",
        )

        for label, extra_args, extra_env in [
            ("cli_flag", ["--plain"], {}),
            ("env_var_1", [], {"AGENTS_BUNDLE_PLAIN": "1"}),
            ("env_var_true", [], {"AGENTS_BUNDLE_PLAIN": "true"}),
        ]:
            with self.subTest(plain_mode=label):
                env = {**os.environ, **extra_env}
                r = self._run(
                    [str(SCRIPT), *extra_args, "role=execute", "task=F23", "project_id=demo"],
                    cwd=str(self.tmp),
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self._assert_ok(r)
                self.assertNotIn("Bundle-Command:", r.stdout)
                self.assertNotIn("Bundle-Boundary:", r.stdout)
                self.assertNotIn("Bundle-Expose:", r.stdout)
                self.assertNotIn("<!-- bundle:", r.stdout)
                self.assertIn("Role: execute\n", r.stdout)
                self.assertIn("Task: F23\n", r.stdout)
                self.assertIn("Project-Id: demo\n", r.stdout)
                self.assertIn(f"Workdir: {self.tmp.resolve()}\n", r.stdout)
                self.assertIn("===== Rules =====\n", r.stdout)
                self.assertEqual(r.stdout.count("Start priority, instruction self-audit & dates:"), 1)
                self.assertIn("===== $ printf 'sub_cmd_out\\n' =====\nsub_cmd_out\n", r.stdout)
                self.assertIn("===== $ printf 'root_cmd_out\\n' =====\nroot_cmd_out\n", r.stdout)
                self.assertIn("===== $ cat doc.txt =====\nincluded doc line\n", r.stdout)
                self.assertIn("===== Prompt =====\nPlain mode prompt\n", r.stdout)

        # Verify AGENTS_BUNDLE_PLAIN=0 preserves transport headers and fragment markers
        env_off = {**os.environ, "AGENTS_BUNDLE_PLAIN": "0"}
        r_default = self._run(
            [str(SCRIPT), "role=execute", "task=F23"],
            cwd=str(self.tmp),
            env=env_off,
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_default)
        self.assertIn("Bundle-Command:", r_default.stdout)
        self.assertIn("Bundle-Boundary:", r_default.stdout)
        self.assertIn("Bundle-Expose: Role, Task, Title, Project-Id\n", r_default.stdout)
        _, frags = self._extract_fragments(r_default.stdout)
        self.assertTrue(len(frags) >= 5)

    def test_include_glob_and_line_range_slices(self):
        mod = self._load_bundle_module()
        src = self.tmp / "src"
        (src / "sub").mkdir(parents=True)
        (src / "__pycache__").mkdir()
        (src / "a.py").write_text("a1\na2\n", encoding="utf-8")
        (src / "b.py").write_text("b1\n", encoding="utf-8")
        (src / "sub" / "c.py").write_text("c1\n", encoding="utf-8")
        (src / "__pycache__" / "x.py").write_text("x1\n", encoding="utf-8")
        (self.tmp / "big.txt").write_text("".join(f"line{i}\n" for i in range(1, 11)), encoding="utf-8")
        extras = ["big.txt:9-20", "nomatch/*.py", "big.txt:0-2", "big.txt:4-2"]
        if os.name != "nt":
            (self.tmp / "odd:1-2.txt").write_text("whole\n", encoding="utf-8")
            extras.append("odd:1-2.txt")
        (self.tmp / ".agents_bundle").write_text(
            "include src/*.py\n"
            "include big.txt:2-3\n"
            "include big.txt:5\n"
            "include big.txt:2-3\n"
            "include src/**/*.py\n",
            encoding="utf-8",
        )
        records: list[dict[str, object]] = []
        body, warnings = mod.build_bundle(work_dir=self.tmp, extra_files=extras, records=records)

        names = [r["name"] for r in records if r["kind"] == "include"]
        expected = [
            "src/a.py",
            "src/b.py",
            "big.txt:2-3",
            "big.txt:5-5",
            "src/sub/c.py",
            "big.txt:9-20",
        ]
        if os.name != "nt":
            expected.append("odd:1-2.txt")
        self.assertEqual(names, expected)
        self.assertEqual(
            records[2],
            {"kind": "include", "name": "big.txt:2-3", "chain": []},
        )
        for missing in ("nomatch/*.py", "big.txt:0-2", "big.txt:4-2"):
            self.assertIn(f"missing file: {missing}", warnings)

        _, frags = self._extract_fragments(body)
        by_name = {m["name"]: b for m, b in frags if m["kind"] == "include"}
        self.assertEqual(by_name["src/a.py"], "===== $ cat src/a.py =====\na1\na2")
        self.assertEqual(by_name["big.txt:2-3"], "===== $ sed -n '2,3p' big.txt =====\nline2\nline3")
        self.assertEqual(by_name["big.txt:5-5"], "===== $ sed -n '5,5p' big.txt =====\nline5")
        self.assertEqual(by_name["big.txt:9-20"], "===== $ sed -n '9,20p' big.txt =====\nline9\nline10")
        if os.name != "nt":
            self.assertEqual(by_name["odd:1-2.txt"], "===== $ cat odd:1-2.txt =====\nwhole")


if __name__ == "__main__":
    unittest.main()
