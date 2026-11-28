#!/usr/bin/env python3
"""Bundle assembly, directives, headers, and fragment marker tests for context-bundle."""
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests.helpers import AgentsBundleTestCase, SCRIPT


class TestBundle(AgentsBundleTestCase):
    def test_bundle_rule_if_conditions_and_cmd_directives(self):
        cur_os = "macos" if sys.platform == "darwin" else "linux"
        other_os = "macos" if cur_os == "linux" else "linux"
        (self.tmp / "AGENTS.md").write_text("# Project Rules\n", encoding="utf-8")
        (self.tmp / "extra.txt").write_text("extra content\n", encoding="utf-8")
        (self.tmp / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:core lang=Spanish\n"
            f"if os={cur_os}\n"
            "    rule vitalio/agents-rules:os/linux\n"
            f"if os={other_os}\n"
            "    rule vitalio/agents-rules:os/macos\n"
            f"if os={cur_os}\n"
            "    rule vitalio/agents-rules:stack/python-cli py_min=3.12\n"
            "cmd cat AGENTS.md\n"
            "cmd context --tree --max-lines 10\n"
            "cmd echo cmd_ok\n",
            encoding="utf-8",
        )
        self._trust()
        rb = self._run(
            [str(SCRIPT), "extra.txt", "-p", "Solve task 1"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(rb)
        self.assertIn("Bundle-Command: context extra.txt -p 'Solve task 1'", rb.stdout)
        self.assertIn("Bundle-Name: vitalio/context-bundle\n", rb.stdout)
        self.assertIn("===== Rules =====", rb.stdout)
        self.assertNotIn("# [bundle", rb.stdout)
        self.assertIn("in Spanish", rb.stdout)
        self.assertNotIn("Clean external text & two-step external changes:", rb.stdout)
        self.assertIn("Linux & POSIX shell rules:", rb.stdout)
        self.assertNotIn("macOS & BSD userland rules:", rb.stdout)
        self.assertIn("Python 3.12+ compatibility", rb.stdout)

        # Verify -v / --verbose includes provenance trace comments with 'if <cond>'
        rb_v = self._run(
            [str(SCRIPT), "-v"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(rb_v)
        self.assertIn("# [bundle vitalio/agents-rules:core -> agents/core/start.md]", rb_v.stdout)
        self.assertIn(f"# [if os={cur_os} rule vitalio/agents-rules:os/linux -> agents/os/linux.md]", rb_v.stdout)
        self.assertIn(f"# [if os={cur_os} rule vitalio/agents-rules:stack/python-cli -> agents/stack/python-cli.md] (py_min=3.12)", rb_v.stdout)

        # Verify direct URL rule and bundle loading
        url_rule = self.tmp / "custom_url_rule.md"
        url_rule.write_text("# Description: Direct URL rule\n- **Direct URL invariant:** Loaded from URL {val:42}.\n", encoding="utf-8")
        url_bundle = self.tmp / "custom_url.bundle"
        url_bundle.write_text(f"# Description: Direct URL bundle\nrule {url_rule.as_uri()} val=99\n", encoding="utf-8")
        r_url = self._run(
            [str(SCRIPT), "bundle", url_bundle.as_uri(), "--plain"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_url)
        self.assertIn("Loaded from URL 99.", r_url.stdout)

        # Verify bundle directive, CLI key=val variables, and prompt directives in .context.bundle
        inc_file = self.tmp / "task_flow.bundle"
        inc_file.write_text(
            "# Description: Custom task flow bundle\n"
            "if role=plan\n"
            "    if task=\n"
            "        cmd echo all_tasks\n"
            "    if task!=\n"
            "        cmd echo focused_task_{task:}\n"
            "    prompt Mode: PLANNING\n"
            "if role=execute\n"
            "    if task=\n"
            "        cmd echo all_tasks\n"
            "        prompt Mode: EXECUTION\n"
            "    if task!=\n"
            "        cmd echo focused_task_{task:}\n"
            "        prompt Mode: EXECUTION ({task:})\n",
            encoding="utf-8",
        )
        (self.tmp / ".context.bundle").write_text(
            "bundle vitalio/context-bundle:context\n"
            "bundle vitalio/agents-rules:core\n"
            "bundle vitalio/todo-md\n"
            f"bundle {inc_file.as_posix()}\n"
            "export role task\n",
            encoding="utf-8",
        )
        self._trust()
        r_none = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self._assert_ok(r_none)
        self.assertIn("Context bundler & rules engine", r_none.stdout)
        self.assertIn("Bundle assembly:", r_none.stdout)
        self.assertIn(
            '[<upstream_cmd> | ]context [key=val ...] [-p "<prompt>"] [file ...]',
            r_none.stdout,
        )
        self.assertNotIn("Session assembly", r_none.stdout)
        self.assertIn("Task management (`todo`)", r_none.stdout)
        self.assertNotIn("all_tasks", r_none.stdout)
        self.assertNotIn("focused_task_", r_none.stdout)
        self.assertNotIn("===== Prompt =====", r_none.stdout)

        r_plan = self._run([str(SCRIPT), "role=plan"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self._assert_ok(r_plan)
        self.assertIn("Bundle-Command: context role=plan\n", r_plan.stdout)
        self.assertIn("Bundle-Name: vitalio/context-bundle\n", r_plan.stdout)
        self.assertNotIn("Bundle-Expose:", r_plan.stdout)
        self.assertIn("Role: plan\n", r_plan.stdout)
        self.assertIn("all_tasks", r_plan.stdout)
        self.assertNotIn("focused_task_", r_plan.stdout)
        self.assertIn("===== Prompt =====\nMode: PLANNING", r_plan.stdout)

        r_exec = self._run([str(SCRIPT), "role=execute"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self._assert_ok(r_exec)
        self.assertIn("Bundle-Command: context role=execute\n", r_exec.stdout)
        self.assertIn("Bundle-Name: vitalio/context-bundle\n", r_exec.stdout)
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
        self.assertIn("Bundle-Command: context role=execute task=A2 lang=German -p 'Focus on edge cases'", r_foc.stdout)
        self.assertIn("Role: execute\nTask: A2\n", r_foc.stdout)
        self.assertNotIn("Lang: German\n", r_foc.stdout)
        self.assertIn("focused_task_A2", r_foc.stdout)
        self.assertNotIn("all_tasks", r_foc.stdout)
        self.assertIn("in German", r_foc.stdout)
        self.assertIn("===== Prompt =====\nMode: EXECUTION (A2)\n\nFocus on edge cases", r_foc.stdout)

        # Verify local relative paths (./..., ../...) across nested bundles and local package dirs
        rel_ws = self.tmp / "rel_workspace" / "proj"
        shared_dir = self.tmp / "rel_workspace" / "shared"
        nested_dir = rel_ws / "bundles" / "nested"
        local_pkg = self.tmp / "rel_workspace" / "local_pkg" / "agents"
        nested_dir.mkdir(parents=True)
        shared_dir.mkdir(parents=True)
        local_pkg.mkdir(parents=True)

        (shared_dir / "shared_rule.md").write_text(
            "# Description: Shared rule\n- Shared parent relative rule body.\n",
            encoding="utf-8",
        )
        (shared_dir / "shared.bundle").write_text(
            "rule ./shared_rule.md\n",
            encoding="utf-8",
        )
        (nested_dir / "local_rule.md").write_text(
            "# Description: Nested local rule\n- Nested sibling relative rule body.\n",
            encoding="utf-8",
        )
        (nested_dir / "child.bundle").write_text(
            "rule ./local_rule.md\n"
            "bundle ../../../shared/shared.bundle\n",
            encoding="utf-8",
        )
        (local_pkg / "default.bundle").write_text(
            "rule pkg_rule\n",
            encoding="utf-8",
        )
        (local_pkg / "pkg_rule.md").write_text(
            "# Description: Local pkg rule\n- Local package directory bundle rule body.\n",
            encoding="utf-8",
        )
        (rel_ws / ".context.bundle").write_text(
            "bundle ./bundles/nested/child.bundle\n"
            "bundle ../local_pkg\n",
            encoding="utf-8",
        )
        r_rel = self._run([str(SCRIPT)], cwd=str(rel_ws), capture_output=True, text=True, check=False)
        self._assert_ok(r_rel)
        self.assertIn("Nested sibling relative rule body.", r_rel.stdout)
        self.assertIn("Shared parent relative rule body.", r_rel.stdout)
        self.assertIn("Local package directory bundle rule body.", r_rel.stdout)

    def test_context_bundle_vars_env_and_cli_override(self):
        (self.tmp / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:core lang=English\n"
            "export lang mode\n"
            "if mode=custom\n"
            "    prompt Custom mode active ({chat_lang:default})\n",
            encoding="utf-8",
        )
        env = {**os.environ, "CONTEXT_BUNDLE_VARS": "lang=Spanish mode=custom chat_lang=French"}
        r_env = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, env=env, check=False)
        self._assert_ok(r_env)
        self.assertIn("Bundle-Command: context\n", r_env.stdout)
        self.assertIn("Bundle-Name: vitalio/context-bundle\n", r_env.stdout)
        self.assertIn("Lang: Spanish\nMode: custom\n", r_env.stdout)
        self.assertNotIn("Chat-Lang:", r_env.stdout)
        self.assertIn("in Spanish", r_env.stdout)
        self.assertIn("Custom mode active (French)", r_env.stdout)

        # CLI key=val overrides CONTEXT_BUNDLE_VARS
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

        # Subcommand rule also respects CONTEXT_BUNDLE_VARS and CLI override
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

        # Invalid CONTEXT_BUNDLE_VARS token fails explicitly
        bad_env = {**os.environ, "CONTEXT_BUNDLE_VARS": "not_a_pair"}
        r_bad = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, env=bad_env, check=False)
        self.assertNotEqual(r_bad.returncode, 0, msg=f"stdout:\n{r_bad.stdout}\nstderr:\n{r_bad.stderr}")
        self.assertIn("CONTEXT_BUNDLE_VARS", r_bad.stderr)

    def test_dynamic_let_file_and_stdin_pipe(self):
        (self.tmp / "src").mkdir()
        (self.tmp / "src/target.py").write_text("VALUE = 42\n", encoding="utf-8")
        (self.tmp / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:core\n"
            "if role=execute\n"
            "    let task=$(printf 'F7')\n"
            "    export role task\n"
            "    file $(printf 'src/target.py\\nmissing/file.py\\n')\n"
            "    prompt Executing {task:}\n",
            encoding="utf-8",
        )
        self._trust()
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

    def test_custom_posix_shell_and_posix_file_paths(self):
        fake_bin = self.tmp / "fake_bin"
        fake_bin.mkdir()
        sh_shim = fake_bin / "custom_sh"
        sh_shim.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('SH_ARGS:' + '|'.join(sys.argv[1:]))\n",
            encoding="utf-8",
        )
        sh_shim.chmod(0o755)
        sub = self.tmp / "pkg"
        sub.mkdir()
        (sub / "mod.py").write_text("X = 1\n", encoding="utf-8")
        (self.tmp / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:core\n"
            "file pkg/mod.py\n"
            "cmd git status -sb\n",
            encoding="utf-8",
        )
        self._trust()
        env = {**os.environ, "CONTEXT_BUNDLE_SHELL": str(sh_shim)}
        r = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self._assert_ok(r)
        self.assertIn("SH_ARGS:-c|git status -sb", r.stdout)
        self.assertIn("===== $ cat pkg/mod.py =====\nX = 1\n", r.stdout)

    def test_single_rules_section_when_bundles_contain_commands(self):
        b1 = self.tmp / "first.bundle"
        b1.write_text(
            "rule vitalio/agents-rules:core/start\n"
            "cmd echo cmd_from_b1\n",
            encoding="utf-8",
        )
        b2 = self.tmp / "second.bundle"
        b2.write_text(
            "rule vitalio/agents-rules:core/ssot\n"
            "cmd echo cmd_from_b2\n",
            encoding="utf-8",
        )
        (self.tmp / ".context.bundle").write_text(
            f"bundle {b1.as_posix()}\n"
            "cmd echo middle_cmd\n"
            f"bundle {b2.as_posix()}\n"
            "rule vitalio/agents-rules:core/lang\n",
            encoding="utf-8",
        )
        self._trust()
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
            for ln in (init_dir / ".context.bundle").read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        self.assertIn("file AGENTS.md", init_lines)
        self.assertNotIn("bundle vitalio/agents-rules:default", init_lines)
        mod = self._load_bundle_module()
        self.assertTrue(mod.is_spec_trusted(init_dir / ".context.bundle"))

    def test_piped_workdir_preamble_and_dir_priority(self):
        proj = self.tmp / "target_proj"
        proj.mkdir()
        (proj / "AGENTS.md").write_text("# Target Project Rules\n", encoding="utf-8")
        (proj / "note.txt").write_text("hello from target\n", encoding="utf-8")
        (proj / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:core\n"
            "export project task title role chat_lang\n"
            "cmd cat AGENTS.md\n"
            "cmd context --tree\n"
            "cmd pwd\n",
            encoding="utf-8",
        )
        self._trust(proj)

        # Piped Key: Value preamble maps Workdir and non-transport headers to lowercase vars
        piped = (
            f"Bundle-Command: todo F18\n"
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
        self.assertIn("Bundle-Name: vitalio/context-bundle\n", r.stdout)
        self.assertIn("Task: F18\n", r.stdout)
        self.assertIn("Title: Demo task title\n", r.stdout)
        self.assertIn("Role: execute\n", r.stdout)
        self.assertIn("Chat-Lang: Spanish\n", r.stdout)
        self.assertNotIn("Bundle-Boundary: nonce123", r.stdout)
        self.assertIn("Bundle-Command: todo F18 | context\n", r.stdout)
        self.assertIn("===== $ cat AGENTS.md =====\n# Target Project Rules\n", r.stdout)
        self.assertIn("note.txt", r.stdout)
        self.assertIn(f"===== $ pwd =====\n{proj.resolve()}\n", r.stdout)
        self.assertIn("===== Prompt =====\n# TODO.md:1\n- Details here", r.stdout)

        # CLI k=v and CONTEXT_BUNDLE_VARS override piped preamble headers
        env_ovr = {**os.environ, "CONTEXT_BUNDLE_VARS": "role=plan task=F10"}
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
        (override_proj / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:core\n"
            "export task\n"
            "cmd cat AGENTS.md\n",
            encoding="utf-8",
        )
        self._trust(override_proj)
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
        (piped_guard_proj / ".context.bundle").write_text(
            "if piped!=1\n"
            "    cmd echo fetch_from_tracker\n"
            "if piped=1\n"
            "    cmd echo already_piped\n",
            encoding="utf-8",
        )
        self._trust(piped_guard_proj)
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
        (proj / ".context.bundle").write_text("cmd echo marker_should_not_run\n", encoding="utf-8")
        self._trust(proj)
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

    def test_bundle_boundary_nonce_and_export_lexical_scoping(self):
        sub_bundle = self.tmp / "extra.bundle"
        sub_bundle.write_text(
            "let local_only=secret_val\n"
            "let project_id=from_child\n"
            "export project_id\n"
            "if role=execute\n"
            "    export work_item, role\n",
            encoding="utf-8",
        )
        sibling_bundle = self.tmp / "sibling.bundle"
        sibling_bundle.write_text(
            "prompt Sibling sees project={project_id:none} local={local_only:none}\n",
            encoding="utf-8",
        )
        (self.tmp / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:core\n"
            "export chat_lang title\n"
            "export {opt_hdr:}\n"
            f"bundle {sub_bundle.as_posix()}\n"
            f"bundle {sibling_bundle.as_posix()}\n",
            encoding="utf-8",
        )

        # Exported vars appear in preamble and sibling bundle; unexported CLI/let vars do not leak
        r1 = self._run(
            [str(SCRIPT), "role=execute", "task=F19", "title=Export check", "lang=German", "chat_lang=French"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r1)
        self.assertIn("Bundle-Name: vitalio/context-bundle\n", r1.stdout)
        self.assertNotIn("Bundle-Expose:", r1.stdout)
        self.assertNotIn("Bundle-Hide:", r1.stdout)
        self.assertIn("Chat-Lang: French\n", r1.stdout)
        self.assertIn("Title: Export check\n", r1.stdout)
        self.assertIn("Project-Id: from_child\n", r1.stdout)
        self.assertIn("Role: execute\n", r1.stdout)
        self.assertNotIn("Task:", r1.stdout)
        self.assertNotIn("\nLang:", r1.stdout)
        self.assertNotIn("Local-Only:", r1.stdout)
        self.assertIn("Sibling sees project=from_child local=none", r1.stdout)
        m1 = re.search(r"^Bundle-Boundary: ([0-9a-f]+)$", r1.stdout, flags=re.MULTILINE)
        self.assertIsNotNone(m1, msg=r1.stdout)

        # Second run generates a distinct nonce and excludes conditional export when condition is false
        r2 = self._run(
            [str(SCRIPT), "role=plan", "opt_hdr=extra_scope", "extra_scope=yes"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r2)
        self.assertIn("Extra-Scope: yes\n", r2.stdout)
        self.assertNotIn("Role: plan\n", r2.stdout)
        m2 = re.search(r"^Bundle-Boundary: ([0-9a-f]+)$", r2.stdout, flags=re.MULTILINE)
        self.assertIsNotNone(m2, msg=r2.stdout)
        self.assertNotEqual(m1.group(1), m2.group(1))

        # Invalid export variable name fails explicitly
        (self.tmp / ".context.bundle").write_text("export bad=key\n", encoding="utf-8")
        r_bad_spec = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_bad_spec.returncode, 0, msg=f"stdout:\n{r_bad_spec.stdout}\nstderr:\n{r_bad_spec.stderr}")
        self.assertIn(".context.bundle", r_bad_spec.stderr)

    def test_source_provenance_and_command_telemetry(self):
        mod = self._load_bundle_module()

        leaf_bundle = self.tmp / "leaf.bundle"
        leaf_bundle.write_text(
            "bundle vitalio/agents-rules:default\n"
            "file leaf_note.txt\n"
            "cmd printf leaf_ok\n"
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
            "file root_note.txt\n"
            "cmd printf root_ok\n"
            "cmd exit 7\n"
            "prompt Root prompt\n"
        )
        (self.tmp / ".context.bundle").write_text(spec_text, encoding="utf-8")
        self._trust()

        # 1. Verify parse_spec preserves full multi-hop chain (root=[] vs nested bundles)
        parsed = mod.parse_spec(spec_text, work_dir=self.tmp)
        by_val = {(kind, val): chain for kind, val, _cond, chain in parsed}
        self.assertEqual(
            by_val[("directive", "rule vitalio/agents-rules:release/single-file-build")],
            [],
        )
        self.assertEqual(by_val[("file", "root_note.txt")], [])
        self.assertEqual(by_val[("cmd", "printf root_ok")], [])
        self.assertEqual(by_val[("prompt", "Root prompt")], [])

        top_ref = top_bundle.as_posix()
        leaf_ref = leaf_bundle.as_posix()
        self.assertEqual(by_val[("directive", "rule vitalio/agents-rules:stack/python-cli")], [top_ref])
        self.assertEqual(
            by_val[("directive", "rule vitalio/agents-rules:core/start")],
            [top_ref, leaf_ref, "vitalio/agents-rules:default", "vitalio/agents-rules:core"],
        )
        self.assertEqual(by_val[("file", "leaf_note.txt")], [top_ref, leaf_ref])
        self.assertEqual(by_val[("cmd", "printf leaf_ok")], [top_ref, leaf_ref])
        self.assertEqual(by_val[("prompt", "Leaf prompt")], [top_ref, leaf_ref])

        # 2. Verify collect_directive_items preserves full multi-hop chain across nested bundles
        items = mod.collect_directive_items(
            "bundle",
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
                "chain": [".context.bundle"],
            },
        )
        self.assertEqual(
            rule_recs["vitalio/agents-rules:stack/python-cli"],
            {
                "kind": "rule",
                "id": "vitalio/agents-rules:stack/python-cli",
                "chain": [".context.bundle", top_ref],
            },
        )
        self.assertEqual(
            rule_recs["vitalio/agents-rules:core/start"],
            {
                "kind": "rule",
                "id": "vitalio/agents-rules:core/start",
                "chain": [
                    ".context.bundle",
                    top_ref,
                    leaf_ref,
                    "vitalio/agents-rules:default",
                    "vitalio/agents-rules:core",
                ],
            },
        )

        cmd_recs = {r["name"]: r for r in records if r["kind"] == "cmd"}
        self.assertEqual(cmd_recs["printf leaf_ok"]["chain"], [".context.bundle", top_ref, leaf_ref])
        self.assertEqual(cmd_recs["printf leaf_ok"]["rc"], 0)
        self.assertIsInstance(cmd_recs["printf leaf_ok"]["ms"], int)
        self.assertGreaterEqual(cmd_recs["printf leaf_ok"]["ms"], 0)

        self.assertEqual(cmd_recs["printf root_ok"]["chain"], [".context.bundle"])
        self.assertEqual(cmd_recs["printf root_ok"]["rc"], 0)
        self.assertEqual(cmd_recs["exit 7"]["chain"], [".context.bundle"])
        self.assertEqual(cmd_recs["exit 7"]["rc"], 7)
        self.assertIsInstance(cmd_recs["exit 7"]["ms"], int)

        inc_recs = {r["name"]: r for r in records if r["kind"] == "file"}
        self.assertEqual(inc_recs["leaf_note.txt"]["chain"], [".context.bundle", top_ref, leaf_ref])
        self.assertEqual(inc_recs["root_note.txt"]["chain"], [".context.bundle"])
        self.assertEqual(inc_recs["cli_note.txt"]["chain"], [])

        prompt_recs = [r for r in records if r["kind"] == "prompt"]
        self.assertEqual([r["chain"] for r in prompt_recs], [[".context.bundle", top_ref, leaf_ref], [".context.bundle"], []])

        # Merged prompt with mixed chains emits chain=[], while shared non-empty chain emits shared chain
        _, mixed_frags = self._extract_fragments(body)
        mixed_prompt_meta = [m for m, _b in mixed_frags if m["kind"] == "prompt"][0]
        self.assertEqual(mixed_prompt_meta, {"kind": "prompt", "chain": []})

        shared_bundle = self.tmp / "shared_prompt.bundle"
        shared_bundle.write_text("prompt First\nprompt Second\n", encoding="utf-8")
        shared_ref = shared_bundle.as_posix()
        (self.tmp / ".context.bundle").write_text(f"bundle {shared_ref}\n", encoding="utf-8")
        shared_body, _ = mod.build_bundle(work_dir=self.tmp)
        _, shared_frags = self._extract_fragments(shared_body)
        shared_prompt_meta = [m for m, _b in shared_frags if m["kind"] == "prompt"][0]
        self.assertEqual(shared_prompt_meta, {"kind": "prompt", "chain": [".context.bundle", shared_ref]})

    def test_json_fragment_markers_for_all_kinds(self):
        pkg_dir = Path(os.environ["CONTEXT_BUNDLE_LOCAL_PKG_DIR"])
        (pkg_dir / "agents" / "core" / "multiline.md").write_text(
            "# Description: Multiline rule\n"
            "- Multiline rule header:\n"
            "  - Bullet one\n"
            "  - Bullet two\n",
            encoding="utf-8",
        )
        (self.tmp / "sub.bundle").write_text(
            "rule vitalio/agents-rules:core/multiline\n"
            "rule vitalio/agents-rules:core/start\n"
            "file sub_doc.txt\n"
            "cmd printf 'sub_line_1\\nsub_line_2\\n'\n",
            encoding="utf-8",
        )
        (self.tmp / "sub_doc.txt").write_text("sub doc line 1\nsub doc line 2\n", encoding="utf-8")
        (self.tmp / "root_doc.txt").write_text("root doc body\n", encoding="utf-8")
        (self.tmp / "cli_doc.txt").write_text("cli doc body\n", encoding="utf-8")
        (self.tmp / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:core\n"
            f"bundle {(self.tmp / 'sub.bundle').as_posix()}\n"
            "file root_doc.txt\n"
            "cmd printf 'line1\\nline2\\n'\n"
            "cmd echo 'arrow --> test'\n"
            "cmd true\n"
            "cmd exit 3\n"
            "prompt Line one\n"
            "prompt Line two\n",
            encoding="utf-8",
        )
        self._trust()

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

        # Verify no fragment leaks .context.bundle, group, or via
        for meta, _ in fragments:
            self.assertNotIn("group", meta)
            self.assertNotIn("via", meta)

        # Verify rule deduplication: core/start appears in core bundle and sub.bundle, emitted once
        rule_frags = [(meta, body) for meta, body in fragments if meta["kind"] == "rule"]
        rule_ids = [meta["id"] for meta, _ in rule_frags]
        self.assertEqual(
            rule_ids,
            [
                "vitalio/agents-rules:core/start",
                "vitalio/agents-rules:core/ssot",
                "vitalio/agents-rules:core/lang",
                "vitalio/agents-rules:core/multiline",
                "vitalio/context-bundle:context",
            ],
        )
        by_rule_id = {meta["id"]: (meta, body) for meta, body in rule_frags}
        self.assertEqual(
            by_rule_id["vitalio/agents-rules:core/start"][0],
            {
                "kind": "rule",
                "id": "vitalio/agents-rules:core/start",
                "chain": [".context.bundle", "vitalio/agents-rules:core"],
            },
        )
        sub_ref = (self.tmp / "sub.bundle").as_posix()
        multi_meta, multi_body = by_rule_id["vitalio/agents-rules:core/multiline"]
        self.assertEqual(
            multi_meta,
            {
                "kind": "rule",
                "id": "vitalio/agents-rules:core/multiline",
                "chain": [".context.bundle", sub_ref],
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
        self.assertEqual(sub_cmd_meta["chain"], [".context.bundle", sub_ref])
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
        self.assertEqual(exit_meta["chain"], [".context.bundle"])

        # Verify file fragments across bundle, .context.bundle, and CLI
        inc_frags = {meta["name"]: (meta, body) for meta, body in fragments if meta["kind"] == "file"}
        self.assertEqual(
            inc_frags["sub_doc.txt"][0],
            {"kind": "file", "name": "sub_doc.txt", "chain": [".context.bundle", sub_ref]},
        )
        self.assertIn("sub doc line 1\nsub doc line 2", inc_frags["sub_doc.txt"][1])
        self.assertEqual(
            inc_frags["root_doc.txt"][0],
            {"kind": "file", "name": "root_doc.txt", "chain": [".context.bundle"]},
        )
        self.assertEqual(
            inc_frags["cli_doc.txt"][0],
            {"kind": "file", "name": "cli_doc.txt", "chain": []},
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
        self.assertTrue(any("# [bundle vitalio/agents-rules:core -> agents/core/start.md]" in b for b in v_rules))

        # Verify standalone rule subcommand does not emit bundle fragment markers
        rs = self._run(
            [str(SCRIPT), "rule", "vitalio/agents-rules:core/start"],
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
            "export role task project_id\n"
            "cmd printf 'sub_cmd_out\\n'\n",
            encoding="utf-8",
        )
        (self.tmp / "doc.txt").write_text("included doc line\n", encoding="utf-8")
        (self.tmp / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:core\n"
            f"bundle {(self.tmp / 'sub.bundle').as_posix()}\n"
            "file doc.txt\n"
            "cmd printf 'root_cmd_out\\n'\n"
            "prompt Plain mode prompt\n",
            encoding="utf-8",
        )
        self._trust()

        for label, extra_args, extra_env in [
            ("cli_flag", ["--plain"], {}),
            ("env_var_1", [], {"CONTEXT_BUNDLE_PLAIN": "1"}),
            ("env_var_true", [], {"CONTEXT_BUNDLE_PLAIN": "true"}),
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

        # Verify CONTEXT_BUNDLE_PLAIN=0 preserves transport headers and fragment markers
        env_off = {**os.environ, "CONTEXT_BUNDLE_PLAIN": "0"}
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
        self.assertIn("Bundle-Name: vitalio/context-bundle\n", r_default.stdout)
        self.assertIn("Bundle-Boundary:", r_default.stdout)
        self.assertNotIn("Bundle-Expose:", r_default.stdout)
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
        extras = ["big.txt:9-20", "nomatch/*.py", "big.txt:0-2", "big.txt:4-2", "odd:1-2.txt"]
        (self.tmp / "odd:1-2.txt").write_text("whole\n", encoding="utf-8")
        (self.tmp / ".context.bundle").write_text(
            "file src/*.py\n"
            "file big.txt:2-3\n"
            "file big.txt:5\n"
            "file big.txt:2-3\n"
            "file src/**/*.py\n",
            encoding="utf-8",
        )
        records: list[dict[str, object]] = []
        body, warnings = mod.build_bundle(work_dir=self.tmp, extra_files=extras, records=records)

        names = [r["name"] for r in records if r["kind"] == "file"]
        expected = [
            "src/a.py",
            "src/b.py",
            "big.txt:2-3",
            "big.txt:5-5",
            "src/sub/c.py",
            "big.txt:9-20",
            "odd:1-2.txt",
        ]
        self.assertEqual(names, expected)
        self.assertEqual(
            next(r for r in records if r.get("name") == "big.txt:2-3"),
            {"kind": "file", "name": "big.txt:2-3", "chain": [".context.bundle"]},
        )
        for missing in ("nomatch/*.py", "big.txt:0-2", "big.txt:4-2"):
            self.assertIn(f"missing file: {missing}", warnings)

        _, frags = self._extract_fragments(body)
        by_name = {m["name"]: b for m, b in frags if m["kind"] == "file"}
        self.assertEqual(by_name["src/a.py"], "===== $ cat src/a.py =====\na1\na2")
        self.assertEqual(by_name["big.txt:2-3"], "===== $ sed -n '2,3p' big.txt =====\nline2\nline3")
        self.assertEqual(by_name["big.txt:5-5"], "===== $ sed -n '5,5p' big.txt =====\nline5")
        self.assertEqual(by_name["big.txt:9-20"], "===== $ sed -n '9,20p' big.txt =====\nline9\nline10")
        self.assertEqual(by_name["odd:1-2.txt"], "===== $ cat odd:1-2.txt =====\nwhole")

    def test_external_bundle_command_tree_trust_hashing_and_allow_rejection(self):
        pkg_dir = Path(os.environ["CONTEXT_BUNDLE_LOCAL_PKG_DIR"])
        ext_bundles = pkg_dir / "agents"
        marker_file = self.tmp / "should_not_exist.txt"

        (ext_bundles / "ext_cmd.bundle").write_text(
            "rule vitalio/agents-rules:core/start\n"
            "cmd printf ext_cmd_ok\n",
            encoding="utf-8",
        )
        (ext_bundles / "ext_pipe.bundle").write_text(
            "cmd printf 'a\\nb\\n' | head -n 1\n",
            encoding="utf-8",
        )
        (ext_bundles / "ext_subshell.bundle").write_text(
            f"let dyn=$(\x22{sys.executable}\x22 -c \x22import pathlib; pathlib.Path({str(marker_file)!r}).write_text('ran'); print('val')\x22)\n"
            "cmd printf after_var\n",
            encoding="utf-8",
        )
        (ext_bundles / "ext_var_only.bundle").write_text(
            "let dyn=$(printf dyn_val)\n"
            "prompt Dynamic: {dyn:none}\n",
            encoding="utf-8",
        )
        (ext_bundles / "ext_self_allow.bundle").write_text(
            "allow printf\n"
            "cmd printf hacked\n",
            encoding="utf-8",
        )

        # 1. Untrusted root spec referencing external bundle with shell commands fails closed before running anything
        (self.tmp / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:ext_subshell\n",
            encoding="utf-8",
        )
        r_untrusted = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertNotEqual(r_untrusted.returncode, 0)
        self.assertIn("untrusted .context.bundle", r_untrusted.stderr)
        self.assertIn("pending shell commands:", r_untrusted.stderr)
        self.assertIn("cmd printf after_var (external bundle vitalio/agents-rules:ext_subshell)", r_untrusted.stderr)
        self.assertFalse(marker_file.exists())

        # 2. Trusting root spec trusts external bundle commands and subshells without allow directive
        (self.tmp / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:ext_cmd\n"
            "bundle vitalio/agents-rules:ext_var_only\n"
            "bundle vitalio/agents-rules:ext_pipe\n",
            encoding="utf-8",
        )
        self._trust()
        r_trusted = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self._assert_ok(r_trusted)
        self.assertIn("ext_cmd_ok", r_trusted.stdout)
        self.assertIn("Dynamic: dyn_val", r_trusted.stdout)
        self.assertIn("===== $ printf 'a\\nb\\n' | head -n 1 =====\na\n", r_trusted.stdout)

        # 3. Changing non-command rules/prompts in external bundle keeps trust digest valid,
        #    while modifying or adding a shell command template in external bundle invalidates trust
        (ext_bundles / "ext_cmd.bundle").write_text(
            "rule vitalio/agents-rules:core/start\n"
            "prompt Added non-command prompt\n"
            "cmd printf ext_cmd_ok\n",
            encoding="utf-8",
        )
        r_still_trusted = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self._assert_ok(r_still_trusted)
        self.assertIn("Added non-command prompt", r_still_trusted.stdout)

        (ext_bundles / "ext_cmd.bundle").write_text(
            "rule vitalio/agents-rules:core/start\n"
            "cmd printf ext_cmd_tampered\n",
            encoding="utf-8",
        )
        r_tampered = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertNotEqual(r_tampered.returncode, 0)
        self.assertIn("untrusted .context.bundle", r_tampered.stderr)
        self.assertIn("cmd printf ext_cmd_tampered (external bundle vitalio/agents-rules:ext_cmd)", r_tampered.stderr)
        self.assertNotIn("ext_cmd_tampered", r_tampered.stdout)

        # Qualifying external command templates with bundle identity:
        # adding an identical command template to another referenced external bundle invalidates trust
        (ext_bundles / "ext_cmd.bundle").write_text(
            "rule vitalio/agents-rules:core/start\n"
            "cmd printf ext_cmd_ok\n",
            encoding="utf-8",
        )
        self._trust()
        (ext_bundles / "ext_var_only.bundle").write_text(
            "let dyn=$(printf dyn_val)\n"
            "cmd printf ext_cmd_ok\n"
            "prompt Dynamic: {dyn:none}\n",
            encoding="utf-8",
        )
        r_dup_ext = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertNotEqual(r_dup_ext.returncode, 0)
        self.assertIn("untrusted .context.bundle", r_dup_ext.stderr)
        self.assertIn("cmd printf ext_cmd_ok (external bundle vitalio/agents-rules:ext_var_only)", r_dup_ext.stderr)

        # 4. 'allow' directive is rejected as an invalid directive in both root and child bundles
        for bad_spec in ("allow printf\n", "bundle vitalio/agents-rules:ext_self_allow\n"):
            with self.subTest(rejected_allow=bad_spec.strip()):
                (self.tmp / ".context.bundle").write_text(bad_spec, encoding="utf-8")
                self._trust()
                r_allow = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
                self.assertNotEqual(r_allow.returncode, 0)
                self.assertIn("invalid line", r_allow.stderr)
                self.assertNotIn("or 'allow ...'", r_allow.stderr)

        # 5. File bundle outside spec_dir is treated as external and included in command-tree trust digest
        outside_dir = self.tmp.parent / f"{self.tmp.name}_ext_outside"
        outside_dir.mkdir(exist_ok=True)
        try:
            outside_bundle = outside_dir / "out.bundle"
            outside_bundle.write_text("cmd printf outside_ran\n", encoding="utf-8")
            (self.tmp / ".context.bundle").write_text(
                f"bundle {outside_bundle.as_posix()}\n",
                encoding="utf-8",
            )
            r_out_blocked = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
            self.assertNotEqual(r_out_blocked.returncode, 0)
            self.assertIn("untrusted .context.bundle", r_out_blocked.stderr)
            self.assertIn("cmd printf outside_ran", r_out_blocked.stderr)

            self._trust()
            r_out_ok = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
            self._assert_ok(r_out_ok)
            self.assertIn("outside_ran", r_out_ok.stdout)

            outside_bundle.write_text("cmd printf outside_modified\n", encoding="utf-8")
            r_out_tampered = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
            self.assertNotEqual(r_out_tampered.returncode, 0)
            self.assertIn("untrusted .context.bundle", r_out_tampered.stderr)
        finally:
            import shutil
            shutil.rmtree(outside_dir, ignore_errors=True)

    def test_external_bundle_file_restricted_to_spec_dir(self):
        pkg_dir = Path(os.environ["CONTEXT_BUNDLE_LOCAL_PKG_DIR"])
        ext_bundles = pkg_dir / "agents"
        (self.tmp / "inside.txt").write_text("inside workspace\n", encoding="utf-8")

        outside_dir = self.tmp.parent / f"{self.tmp.name}_outside_files"
        outside_dir.mkdir(exist_ok=True)
        try:
            outside_file = outside_dir / "secret.txt"
            outside_file.write_text("top secret\n", encoding="utf-8")
            rel_outside = f"../{outside_dir.name}/secret.txt"

            (ext_bundles / "inc_inside.bundle").write_text(
                "file inside.txt\n",
                encoding="utf-8",
            )
            (ext_bundles / "inc_abs_out.bundle").write_text(
                f"file {outside_file.as_posix()}\n",
                encoding="utf-8",
            )
            (ext_bundles / "inc_rel_out.bundle").write_text(
                f"file {rel_outside}:1-1\n",
                encoding="utf-8",
            )
            (ext_bundles / "inc_glob_out.bundle").write_text(
                f"file ../{outside_dir.name}/*.txt\n",
                encoding="utf-8",
            )

            # 1. Include inside repository root succeeds
            (self.tmp / ".context.bundle").write_text(
                "bundle vitalio/agents-rules:inc_inside\n",
                encoding="utf-8",
            )
            r_in = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
            self._assert_ok(r_in)
            self.assertIn("===== $ cat inside.txt =====\ninside workspace", r_in.stdout)

            # 2. Absolute, parent-relative slice, and glob outside spec_dir fail fast
            for bname in ("inc_abs_out", "inc_rel_out", "inc_glob_out"):
                with self.subTest(bundle=bname):
                    (self.tmp / ".context.bundle").write_text(
                        f"bundle vitalio/agents-rules:{bname}\n",
                        encoding="utf-8",
                    )
                    r_out = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
                    self.assertNotEqual(r_out.returncode, 0)
                    self.assertIn("resolves outside repository root", r_out.stderr)
                    self.assertIn(f"vitalio/agents-rules:{bname}", r_out.stderr)
                    self.assertNotIn("top secret", r_out.stdout)

            # 3. Symlink inside spec_dir pointing outside spec_dir is blocked for external bundle
            sym = self.tmp / "leak_link.txt"
            sym.symlink_to(outside_file)
            (ext_bundles / "inc_symlink.bundle").write_text(
                "file leak_link.txt\n",
                encoding="utf-8",
            )
            (self.tmp / ".context.bundle").write_text(
                "bundle vitalio/agents-rules:inc_symlink\n",
                encoding="utf-8",
            )
            r_sym = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
            self.assertNotEqual(r_sym.returncode, 0)
            self.assertIn("resolves outside repository root", r_sym.stderr)
            self.assertNotIn("top secret", r_sym.stdout)
        finally:
            import shutil
            shutil.rmtree(outside_dir, ignore_errors=True)

    def test_python_indented_if_elif_else_and_declaration_order_assembly(self):
        (self.tmp / "first.txt").write_text("FIRST_FILE\n", encoding="utf-8")
        (self.tmp / "second.txt").write_text("SECOND_FILE\n", encoding="utf-8")
        adapter = self.tmp / "adapter.bundle"
        adapter.write_text(
            "if todo_md.role!=\n"
            "    let role={todo_md.role:}\n"
            "else if todo_md.prefix=D\n"
            "    let role=design\n"
            "elif todo_md.status=WIP,NEXT\n"
            "    let role=work\n"
            "else\n"
            "    let role=plan\n"
            "export role\n",
            encoding="utf-8",
        )
        (self.tmp / ".context.bundle").write_text(
            f"bundle {adapter.as_posix()}\n"
            "rule vitalio/agents-rules:core/start vitalio/agents-rules:core/ssot\n"
            "file first.txt {empty_files:}\n"
            "cmd printf 'BETWEEN_FILES'\n"
            "file second.txt first.txt\n",
            encoding="utf-8",
        )
        self._trust()

        for label, cli_args, expected_role in [
            ("explicit_role", ["todo_md.role=audit", "todo_md.prefix=D"], "audit"),
            ("else_if_branch", ["todo_md.prefix=D", "todo_md.status=WIP"], "design"),
            ("elif_branch", ["todo_md.prefix=F", "todo_md.status=NEXT"], "work"),
            ("else_branch", ["todo_md.prefix=F", "todo_md.status=NEW"], "plan"),
        ]:
            with self.subTest(branch=label):
                r = self._run([str(SCRIPT), *cli_args], cwd=str(self.tmp))
                self._assert_ok(r)
                self.assertIn(f"Role: {expected_role}\n", r.stdout)
                _n, frags = self._extract_fragments(r.stdout)
                middle = [(m["kind"], m["name"]) for m, _ in frags if m["kind"] in ("file", "cmd")]
                self.assertEqual(
                    middle,
                    [
                        ("file", "first.txt"),
                        ("cmd", "printf 'BETWEEN_FILES'"),
                        ("file", "second.txt"),
                    ],
                )

        # Syntax errors in Python-indented blocks fail fast
        for label, bad_spec, err_sub in [
            ("trailing_colon", "if role=work:\n    prompt x\n", "trailing ':'"),
            ("endif_forbidden", "if role=work\n    prompt x\nendif\n", "'endif' is not supported"),
            ("empty_block", "if role=work\nprompt x\n", "expected 4-space indented block"),
            ("bad_indent_width", "if role=work\n  prompt x\n", "multiple of 4 spaces"),
            ("tab_indent", "if role=work\n\tprompt x\n", "tabs are not allowed"),
            ("orphan_else", "else\n    prompt x\n", "without matching 'if'"),
            ("elif_after_else", "if a=1\n    prompt x\nelse\n    prompt y\nelif a=2\n    prompt z\n", "after 'else'"),
            ("legacy_bracket_if_block", "[if role=work]\n    prompt x\n[/if]\n", "unexpected indentation"),
            ("legacy_bracket_if_inline", "[if role=work] prompt x\n", "invalid line"),
            ("legacy_ruleset_kw", "ruleset vitalio/agents-rules:core\n", "invalid line"),
            ("legacy_include_kw", "include first.txt\n", "invalid line"),
            ("legacy_dollar_kw", "$ echo hi\n", "invalid line"),
            ("legacy_var_kw", "var a=1\n", "invalid line"),
            ("legacy_expose_kw", "expose a\n", "invalid line"),
        ]:
            with self.subTest(syntax_error=label):
                (self.tmp / ".context.bundle").write_text(bad_spec, encoding="utf-8")
                r_bad = self._run([str(SCRIPT)], cwd=str(self.tmp))
                self.assertNotEqual(r_bad.returncode, 0, msg=r_bad.stdout)
                self.assertIn(err_sub, r_bad.stderr)

    def test_root_bundle_file_workdir_boundary_and_unrestricted_cli_files(self):
        repo = self.tmp / "boundary_repo"
        repo.mkdir()
        (repo / "local.txt").write_text("inside repo\n", encoding="utf-8")
        outside = self.tmp / "secrets.env"
        outside.write_text("API_KEY=secret123\n", encoding="utf-8")
        sym = repo / "escape_link.env"
        sym.symlink_to(outside)

        for label, spec_line in [
            ("tilde_home", "file ~/.ssh/id_rsa\n"),
            ("parent_relative", "file ../secrets.env\n"),
            ("parent_slice", "file ../secrets.env:1-1\n"),
            ("parent_glob", "file ../*.env\n"),
            ("absolute_outside", f"file {outside.as_posix()}\n"),
            ("symlink_outside", "file escape_link.env\n"),
        ]:
            with self.subTest(blocked_root_file=label):
                (repo / ".context.bundle").write_text(spec_line, encoding="utf-8")
                r_bad = self._run([str(SCRIPT)], cwd=str(repo))
                self.assertNotEqual(r_bad.returncode, 0, msg=r_bad.stdout)
                self.assertIn("resolves outside repository root", r_bad.stderr)
                self.assertNotIn("secret123", r_bad.stdout)

        with self.subTest(case="CLI extra file argument outside repo remains unrestricted"):
            (repo / ".context.bundle").write_text("file local.txt\n", encoding="utf-8")
            r_ok = self._run([str(SCRIPT), outside.as_posix()], cwd=str(repo))
            self._assert_ok(r_ok)
            self.assertIn("inside repo", r_ok.stdout)
            self.assertIn("API_KEY=secret123", r_ok.stdout)

    def test_root_bundle_builtin_readonly_commands_and_trust_enforcement(self):
        from unittest import mock

        mod = self._load_bundle_module()
        for removed_attr in (
            "_is_safe_builtin_command",
            "_is_safe_tree_args",
            "_GIT_READONLY_SUBCMDS",
            "_GIT_BRANCH_VALUE_FLAGS",
            "_GIT_BRANCH_SAFE_BOOL_FLAGS",
            "_is_safe_git_branch_args",
            "_TODO_MUTATING_SUBCMDS",
            "_TODO_READONLY_SUBCMDS",
            "_TODO_FORBIDDEN_FLAGS",
            "_is_safe_todo_args",
            "_SHELL_WRAPPER_BINS",
            "_parse_allow_bins",
            "_extract_subshells_and_segments",
            "_extract_command_executables",
            "_check_command_allowed",
        ):
            self.assertFalse(hasattr(mod, removed_attr), msg=removed_attr)

        repo = self.tmp / "untrusted_repo"
        repo.mkdir()
        (repo / "AGENTS.md").write_text("# Repo Rules\n", encoding="utf-8")

        with self.subTest(case="strictly declarative untrusted spec runs without trusted.json"):
            (repo / ".context.bundle").write_text(
                "bundle vitalio/agents-rules:core\n"
                "let role=work\n"
                "export role\n"
                "if role=work\n"
                "    file AGENTS.md\n"
                "    prompt Declarative prompt\n",
                encoding="utf-8",
            )
            with mock.patch.object(mod, "_collect_spec_trust_tree", wraps=mod._collect_spec_trust_tree) as spy_walk:
                r_decl = self._run([str(SCRIPT)], cwd=str(repo))
            self._assert_ok(r_decl)
            self.assertEqual(spy_walk.call_count, 0)
            self.assertIn("===== $ cat AGENTS.md =====", r_decl.stdout)
            self.assertIn("Declarative prompt", r_decl.stdout)

        marker = self.tmp / "untrusted_ran.txt"
        for label, untrusted_spec, expected_cmd in [
            ("context_tree_cmd", "cmd context --tree\n", "cmd context --tree"),
            (
                "context_tree_opts_cmd",
                "cmd context --tree -x build --max-lines 50 --max-tokens 800\n",
                "cmd context --tree -x build --max-lines 50 --max-tokens 800",
            ),
            ("context_tree_let_subshell", "let tree=$(context --tree)\n", "let tree=$(context --tree)"),
            ("context_tree_file_subshell", "file $(context --tree)\n", "file $(context --tree)"),
            (
                "arbitrary_cmd",
                f"cmd \"{sys.executable}\" -c \"import pathlib; pathlib.Path({str(marker)!r}).write_text('pwn')\"\n",
                "pathlib.Path",
            ),
            ("git_status_cmd", "cmd git status -sb\n", "cmd git status -sb"),
            ("todo_cmd", "cmd todo overview\n", "cmd todo overview"),
            ("arbitrary_let_subshell", "let x=$(printf pwn_val)\n", "let x=$(printf pwn_val)"),
            ("arbitrary_file_subshell", "file $(printf AGENTS.md)\n", "file $(printf AGENTS.md)"),
        ]:
            with self.subTest(blocked_without_trust=label):
                (repo / ".context.bundle").write_text(untrusted_spec, encoding="utf-8")
                with mock.patch.object(
                    mod, "_collect_spec_trust_tree", wraps=mod._collect_spec_trust_tree
                ) as spy_walk:
                    r_blk = self._run([str(SCRIPT)], cwd=str(repo))
                self.assertNotEqual(r_blk.returncode, 0, msg=r_blk.stdout)
                self.assertEqual(r_blk.stdout, "")
                self.assertEqual(spy_walk.call_count, 1)
                self.assertIn("untrusted .context.bundle", r_blk.stderr)
                self.assertIn("pending shell commands:", r_blk.stderr)
                self.assertIn(expected_cmd, r_blk.stderr)
                self.assertIn(
                    "inspect .context.bundle and run 'context --trust' to trust this file",
                    r_blk.stderr,
                )
                self.assertFalse(marker.exists())

        with self.subTest(case="untrusted error hint includes target directory when Workdir differs from cwd"):
            (repo / ".context.bundle").write_text("cmd context --tree\n", encoding="utf-8")
            expected_hint = (
                f"inspect {repo.resolve() / '.context.bundle'} and run "
                f"'context --trust -C {repo.resolve()}' to trust this file"
            )
            r_dash_c = self._run([str(SCRIPT), "-C", str(repo)], cwd=str(self.tmp))
            self.assertNotEqual(r_dash_c.returncode, 0)
            self.assertIn(expected_hint, r_dash_c.stderr)

            r_piped_wdir = self._run(
                [str(SCRIPT)],
                cwd=str(self.tmp),
                input=f"Workdir: {repo}\nTask: F41\n\n# Prompt\n",
            )
            self.assertNotEqual(r_piped_wdir.returncode, 0)
            self.assertIn(expected_hint, r_piped_wdir.stderr)

        with self.subTest(case="trusted context --tree executes via in-process fast path with a single trust-tree walk"):
            (repo / ".context.bundle").write_text(
                "file AGENTS.md\n"
                "cmd context --tree\n",
                encoding="utf-8",
            )
            r_pos_trust = self._run([str(SCRIPT), "--trust", str(repo)], cwd=str(self.tmp))
            self._assert_ok(r_pos_trust)
            with mock.patch.object(mod, "_collect_spec_trust_tree", wraps=mod._collect_spec_trust_tree) as spy_walk:
                r_tree = self._run([str(SCRIPT), "-C", str(repo)], cwd=str(self.tmp))
            self._assert_ok(r_tree)
            self.assertEqual(spy_walk.call_count, 1)
            self.assertIn("===== $ context --tree =====", r_tree.stdout)
            r_pos_revoke = self._run([str(SCRIPT), "--trust", "--revoke", str(repo)], cwd=str(self.tmp))
            self._assert_ok(r_pos_revoke)

        with self.subTest(case="trust allows execution and file edit invalidates sha256 trust"):
            (repo / ".context.bundle").write_text("cmd printf trusted_ok\n", encoding="utf-8")
            self._trust(repo)
            r_tr = self._run([str(SCRIPT)], cwd=str(repo))
            self._assert_ok(r_tr)
            self.assertIn("===== $ printf trusted_ok =====\ntrusted_ok", r_tr.stdout)

            # Modifying .context.bundle changes sha256 and requires re-trusting
            (repo / ".context.bundle").write_text("cmd printf modified_untrusted\n", encoding="utf-8")
            r_mod = self._run([str(SCRIPT)], cwd=str(repo))
            self.assertNotEqual(r_mod.returncode, 0)
            self.assertIn("untrusted .context.bundle", r_mod.stderr)
            self.assertIn("cmd printf modified_untrusted", r_mod.stderr)
            self.assertNotIn("modified_untrusted", r_mod.stdout)

        with self.subTest(case="interactive /dev/tty confirmation prompt displays pending commands and accepts"):
            tty_file = self.tmp / "fake_tty.txt"
            tty_file.write_text("n\n", encoding="utf-8")
            env_tty = {**os.environ, "CONTEXT_BUNDLE_TTY": str(tty_file)}
            with mock.patch.object(mod, "_collect_spec_trust_tree", wraps=mod._collect_spec_trust_tree) as spy_no:
                r_no = self._run([str(SCRIPT)], cwd=str(repo), env=env_tty)
            self.assertNotEqual(r_no.returncode, 0)
            self.assertEqual(spy_no.call_count, 1)
            self.assertIn("untrusted .context.bundle", r_no.stderr)

            tty_file.write_text("y\n", encoding="utf-8")
            with mock.patch.object(mod, "_collect_spec_trust_tree", wraps=mod._collect_spec_trust_tree) as spy_yes:
                r_yes = self._run([str(SCRIPT)], cwd=str(repo), env=env_tty)
            self._assert_ok(r_yes)
            self.assertEqual(spy_yes.call_count, 1)
            self.assertIn("===== $ printf modified_untrusted =====\nmodified_untrusted", r_yes.stdout)
            self.assertTrue(mod.is_spec_trusted(repo / ".context.bundle"))

        with self.subTest(case="modifying local child bundle inside repo invalidates composite sha256 trust"):
            child_b = repo / "local_child.bundle"
            child_b.write_text("cmd printf child_v1\n", encoding="utf-8")
            (repo / ".context.bundle").write_text("bundle ./local_child.bundle\n", encoding="utf-8")
            self._trust(repo)
            r_c1 = self._run([str(SCRIPT)], cwd=str(repo))
            self._assert_ok(r_c1)
            self.assertIn("child_v1", r_c1.stdout)

            # Tampering with local_child.bundle without touching .context.bundle invalidates trust
            child_b.write_text("cmd printf child_tampered\n", encoding="utf-8")
            r_c2 = self._run([str(SCRIPT)], cwd=str(repo))
            self.assertNotEqual(r_c2.returncode, 0)
            self.assertIn("untrusted .context.bundle", r_c2.stderr)
            self.assertIn("./local_child.bundle", r_c2.stderr)
            self.assertNotIn("child_tampered", r_c2.stdout)

        with self.subTest(case="local directory package ./path/to/pkg:<item> anchors work_dir and tracks local files in trusted.json"):
            pkg_sub = repo / "packages" / "my_pkg" / "agents"
            pkg_sub.mkdir(parents=True, exist_ok=True)
            (pkg_sub / "main.bundle").write_text(
                "bundle sibling\n"
                "rule sub_rule\n",
                encoding="utf-8",
            )
            sibling_b = pkg_sub / "sibling.bundle"
            sibling_b.write_text(
                "rule sib_rule\n"
                "cmd printf local_pkg_sib_v1\n",
                encoding="utf-8",
            )
            (pkg_sub / "sub_rule.md").write_text(
                "# Description: Sub rule\n- LOCAL_PKG_SUB_RULE_BODY\n",
                encoding="utf-8",
            )
            (pkg_sub / "sib_rule.md").write_text(
                "# Description: Sibling rule\n- LOCAL_PKG_SIB_RULE_BODY\n",
                encoding="utf-8",
            )
            (repo / ".context.bundle").write_text(
                "bundle ./packages/my_pkg:main\n",
                encoding="utf-8",
            )
            self._trust(repo)
            r_lp1 = self._run([str(SCRIPT), "--plain"], cwd=str(repo))
            self._assert_ok(r_lp1)
            self.assertIn("LOCAL_PKG_SUB_RULE_BODY", r_lp1.stdout)
            self.assertIn("LOCAL_PKG_SIB_RULE_BODY", r_lp1.stdout)
            self.assertIn("local_pkg_sib_v1", r_lp1.stdout)

            # Also verify collect_directive_items directly on ./packages/my_pkg:main
            direct_items = mod.collect_directive_items("bundle", "./packages/my_pkg:main", work_dir=repo)
            direct_bodies = "\n".join(item[2] for item in direct_items)
            self.assertIn("LOCAL_PKG_SUB_RULE_BODY", direct_bodies)
            self.assertIn("LOCAL_PKG_SIB_RULE_BODY", direct_bodies)

            # Modifying sibling.bundle inside ./packages/my_pkg/agents/ invalidates composite sha256 trust
            sibling_b.write_text(
                "rule sib_rule\n"
                "cmd printf local_pkg_sib_tampered\n",
                encoding="utf-8",
            )
            r_lp2 = self._run([str(SCRIPT)], cwd=str(repo))
            self.assertNotEqual(r_lp2.returncode, 0)
            self.assertIn("untrusted .context.bundle", r_lp2.stderr)
            self.assertNotIn("local_pkg_sib_tampered", r_lp2.stdout)

        with self.subTest(case="context --init automatically records trust in trusted.json"):
            init_repo = self.tmp / "init_trusted_repo"
            init_repo.mkdir()
            self._git(init_repo, "init", "-q")
            self._git(init_repo, "symbolic-ref", "HEAD", "refs/heads/main")
            (init_repo / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
            self._git(init_repo, "add", "AGENTS.md")
            self._git(init_repo, "commit", "-q", "-m", "init")
            r_init = self._run([str(SCRIPT), "--init"], cwd=str(init_repo))
            self._assert_ok(r_init)
            self.assertTrue(mod.is_spec_trusted(init_repo / ".context.bundle"))
            r_run = self._run([str(SCRIPT)], cwd=str(init_repo))
            self._assert_ok(r_run)
            self.assertIn("===== $ git status -sb =====", r_run.stdout)

    def test_prepass_session_variables_precedence_and_subshell_caching(self):
        pkg_dir = Path(os.environ["CONTEXT_BUNDLE_LOCAL_PKG_DIR"])
        todo_pkg = pkg_dir / "vitalio" / "todo-md" / "agents"
        todo_pkg.mkdir(parents=True, exist_ok=True)
        (todo_pkg / "todo.md").write_text(
            "# Description: Todo rule\n- Task management (`todo`): Manage `TODO.md`.\n",
            encoding="utf-8",
        )
        adapters_dir = pkg_dir / "agents" / "adapters"
        adapters_dir.mkdir(parents=True, exist_ok=True)
        (adapters_dir / "todo-md.bundle").write_text(
            "# Description: Todo-md adapter\n"
            "rule vitalio/todo-md\n"
            "if todo_md.role!=\n"
            "    let role={todo_md.role:}\n"
            "elif todo_md.status=WIP,NEXT\n"
            "    let role=work\n"
            "if todo_md.task!=\n"
            "    let task={todo_md.task:}\n"
            "if todo_md.title!=\n"
            "    let title={todo_md.title:}\n"
            "export role task title\n",
            encoding="utf-8",
        )
        (pkg_dir / "agents" / "role" / "work.md").write_text(
            "# Description: Universal Worker role\n- Role (Worker): Focus strictly on delivering the target task.\n",
            encoding="utf-8",
        )
        (pkg_dir / "agents" / "core" / "core.bundle").write_text(
            "# Description: Core axioms\n"
            "rule core/start\n"
            "rule core/ssot\n"
            "rule core/lang lang=English\n"
            "if role!=\n"
            "    rule role/{role:}\n",
            encoding="utf-8",
        )

        # 1. Trailing adapters/todo-md placed AFTER core still populates role/task/title for core in Pass 2
        counter_file = self.tmp / "subshell_count.txt"
        child_writer_1 = self.tmp / "writer1.bundle"
        child_writer_1.write_text(
            "let empty_export=\n"
            "export empty_export\n"
            "let shared_var=from_writer1\n"
            "let local_var=writer1_local\n"
            "export shared_var\n",
            encoding="utf-8",
        )
        child_writer_2 = self.tmp / "writer2.bundle"
        child_writer_2.write_text(
            "let empty_export=claimed_by_writer2\n"
            "let shared_var=from_writer2_ignored\n"
            "let root_let_var=from_writer2_ignored\n"
            "let cli_var=from_writer2_ignored\n"
            "let local_var=writer2_local\n"
            f"let dyn_var=$(\"{sys.executable}\" -c \"from pathlib import Path; p = Path({str(counter_file)!r}); n = int(p.read_text()) + 1 if p.exists() else 1; p.write_text(str(n)); print('dyn_val_' + str(n))\")\n"
            "export empty_export shared_var root_let_var cli_var dyn_var\n"
            "prompt Writer2 sees local={local_var:} shared={shared_var:} dyn={dyn_var:}\n",
            encoding="utf-8",
        )

        (self.tmp / ".context.bundle").write_text(
            "let root_let_var=from_root_let\n"
            "bundle vitalio/agents-rules:core\n"
            f"bundle {child_writer_1.as_posix()}\n"
            f"bundle {child_writer_2.as_posix()}\n"
            "bundle vitalio/agents-rules:adapters/todo-md\n"
            "prompt Root sees role={role:} task={task:} title={title:} shared={shared_var:} empty={empty_export:} root_let={root_let_var:} cli={cli_var:}\n",
            encoding="utf-8",
        )
        self._trust()

        upstream_todo = (
            "Bundle-Command: todo F39\n"
            "Bundle-Name: vitalio/todo-md\n"
            "Bundle-Boundary: todo123\n"
            "Task: F39\n"
            "Status: WIP\n"
            "Title: Pre-pass and stratification\n\n"
            "<!-- bundle:todo123:part {\"kind\": \"prompt\", \"id\": \"F39\", \"chain\": [\"vitalio/todo-md\"]} -->\n"
            "===== Prompt =====\n# WIP F39\n"
            "<!-- bundle:todo123:end -->\n"
        )
        r = self._run(
            [str(SCRIPT), "cli_var=from_cli"],
            cwd=str(self.tmp),
            input=upstream_todo,
        )
        self._assert_ok(r)
        # Dynamic let x=$(...) executed only once across Pass 1 and Pass 2
        self.assertEqual(counter_file.read_text(encoding="utf-8").strip(), "1")
        self.assertIn("Role: work\n", r.stdout)
        self.assertIn("Task: F39\n", r.stdout)
        self.assertIn("Title: Pre-pass and stratification\n", r.stdout)
        self.assertIn("Shared-Var: from_writer1\n", r.stdout)
        self.assertIn("Empty-Export: claimed_by_writer2\n", r.stdout)
        self.assertIn("Root-Let-Var: from_root_let\n", r.stdout)
        self.assertIn("Cli-Var: from_cli\n", r.stdout)
        self.assertIn("Dyn-Var: dyn_val_1\n", r.stdout)
        self.assertIn("Role (Worker): Focus strictly on delivering the target task.", r.stdout)
        self.assertIn("Writer2 sees local=writer2_local shared=from_writer1 dyn=dyn_val_1", r.stdout)
        self.assertIn(
            "Root sees role=work task=F39 title=Pre-pass and stratification "
            "shared=from_writer1 empty=claimed_by_writer2 root_let=from_root_let cli=from_cli",
            r.stdout,
        )

    def test_two_layer_rule_cache_stratification_and_upstream_rule_reuse(self):
        pkg_dir = Path(os.environ["CONTEXT_BUNDLE_LOCAL_PKG_DIR"])
        todo_pkg = pkg_dir / "vitalio" / "todo-md" / "agents"
        todo_pkg.mkdir(parents=True, exist_ok=True)
        (todo_pkg / "todo.md").write_text(
            "# Description: Todo rule\n- Task management (`todo`): Package fallback body.\n",
            encoding="utf-8",
        )
        adapters_dir = pkg_dir / "agents" / "adapters"
        adapters_dir.mkdir(parents=True, exist_ok=True)
        (adapters_dir / "todo-md.bundle").write_text(
            "# Description: Todo-md adapter\n"
            "rule vitalio/todo-md\n"
            "if todo_md.role!=\n"
            "    let role={todo_md.role:}\n"
            "elif todo_md.status=WIP,NEXT\n"
            "    let role=work\n"
            "if todo_md.task!=\n"
            "    let task={todo_md.task:}\n"
            "export role task\n",
            encoding="utf-8",
        )
        (pkg_dir / "agents" / "role" / "work.md").write_text(
            "# Description: Universal Worker role\n- Role (Worker): Deliver target task.\n",
            encoding="utf-8",
        )
        (pkg_dir / "agents" / "collab").mkdir(parents=True, exist_ok=True)
        (pkg_dir / "agents" / "collab" / "commits.md").write_text(
            "# Description: Commits\n- Commit subject line: Imperative summary.\n",
            encoding="utf-8",
        )
        (pkg_dir / "agents" / "core" / "core.bundle").write_text(
            "# Description: Core axioms\n"
            "rule core/start\n"
            "rule core/ssot\n"
            "rule core/lang lang=English\n"
            "if os=linux\n"
            "    rule os/linux\n"
            "if os=macos\n"
            "    rule os/macos\n"
            "if vcs=git\n"
            "    rule vcs/git\n"
            "if role!=\n"
            "    rule role/{role:}\n",
            encoding="utf-8",
        )

        (self.tmp / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:adapters/todo-md\n"
            "bundle vitalio/agents-rules:core\n"
            "rule vitalio/agents-rules:release/single-file-build\n"
            "rule vitalio/agents-rules:collab/commits\n",
            encoding="utf-8",
        )
        cur_os = "macos" if sys.platform == "darwin" else "linux"
        expected_layer1 = [
            "vitalio/todo-md:todo",
            "vitalio/agents-rules:core/start",
            "vitalio/agents-rules:core/ssot",
            "vitalio/agents-rules:core/lang",
            f"vitalio/agents-rules:os/{cur_os}",
            "vitalio/agents-rules:release/single-file-build",
            "vitalio/agents-rules:collab/commits",
            "vitalio/context-bundle:context",
        ]

        # 1. Non-piped run with role=work vs role=plan vs no role: Layer 1 prefix is identical
        r_no_role = self._run([str(SCRIPT)], cwd=str(self.tmp))
        self._assert_ok(r_no_role)
        _, frags_no_role = self._extract_fragments(r_no_role.stdout)
        rules_no_role = [m["id"] for m, _ in frags_no_role if m["kind"] == "rule"]
        self.assertEqual(rules_no_role, expected_layer1)

        r_work = self._run([str(SCRIPT), "role=work"], cwd=str(self.tmp))
        self._assert_ok(r_work)
        _, frags_work = self._extract_fragments(r_work.stdout)
        rules_work = [m["id"] for m, _ in frags_work if m["kind"] == "rule"]
        self.assertEqual(rules_work, [*expected_layer1, "vitalio/agents-rules:role/work"])

        r_plan = self._run([str(SCRIPT), "role=plan"], cwd=str(self.tmp))
        self._assert_ok(r_plan)
        _, frags_plan = self._extract_fragments(r_plan.stdout)
        rules_plan = [m["id"] for m, _ in frags_plan if m["kind"] == "rule"]
        self.assertEqual(rules_plan, [*expected_layer1, "vitalio/agents-rules:role/plan"])

        # 2. Piped run with upstream vitalio/todo-md:todo and an unreferenced upstream rule:
        #    vitalio/todo-md:todo stays in its Layer 1 position reusing the piped upstream body,
        #    while the unreferenced upstream rule is placed at the end of Layer 2.
        piped_bundle = (
            "Bundle-Command: todo F39\n"
            "Bundle-Name: vitalio/todo-md\n"
            "Bundle-Boundary: pipe999\n"
            "Task: F39\n"
            "Status: WIP\n\n"
            "<!-- bundle:pipe999:part {\"kind\": \"rule\", \"id\": \"vitalio/todo-md:todo\", \"chain\": [\"vitalio/todo-md\"]} -->\n"
            "# Description: Upstream todo rule\n- Task management (`todo`): UPSTREAM_PIPED_TODO_BODY.\n"
            "<!-- bundle:pipe999:end -->\n"
            "<!-- bundle:pipe999:part {\"kind\": \"rule\", \"id\": \"acme/custom:extra\", \"chain\": [\"acme/custom\"]} -->\n"
            "- Unreferenced upstream rule body.\n"
            "<!-- bundle:pipe999:end -->\n"
        )
        r_piped = self._run([str(SCRIPT)], cwd=str(self.tmp), input=piped_bundle)
        self._assert_ok(r_piped)
        _, frags_piped = self._extract_fragments(r_piped.stdout)
        rule_frags_piped = [(m, b) for m, b in frags_piped if m["kind"] == "rule"]
        rules_piped_ids = [m["id"] for m, _ in rule_frags_piped]
        self.assertEqual(
            rules_piped_ids,
            [
                *expected_layer1,
                "vitalio/agents-rules:role/work",
                "acme/custom:extra",
            ],
        )
        by_id_piped = {m["id"]: (m, b) for m, b in rule_frags_piped}
        self.assertIn("UPSTREAM_PIPED_TODO_BODY", by_id_piped["vitalio/todo-md:todo"][1])
        self.assertNotIn("Package fallback body", by_id_piped["vitalio/todo-md:todo"][1])
        self.assertEqual(
            by_id_piped["vitalio/todo-md:todo"][0]["chain"],
            [".context.bundle", "vitalio/agents-rules:adapters/todo-md"],
        )

        # 3. Typo in intra-package rule inside vitalio/agents-rules (role=reivew) fails immediately in vitalio/agents-rules
        r_typo = self._run([str(SCRIPT), "role=reivew"], cwd=str(self.tmp))
        self.assertNotEqual(r_typo.returncode, 0)
        self.assertIn("unknown rule 'role/reivew' in package 'vitalio/agents-rules'", r_typo.stderr)


if __name__ == "__main__":
    unittest.main()
