#!/usr/bin/env python3
"""Piped upstream bundle pass-through, producer namespacing, and canonical fragment normalization tests."""
import json
import unittest

from tests.helpers import AgentsBundleTestCase, SCRIPT


class TestUpstream(AgentsBundleTestCase):
    def _run_upstream(self) -> str:
        (self.tmp / "big.txt").write_text("".join(f"line{i}\n" for i in range(1, 11)), encoding="utf-8")
        (self.tmp / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:core\n"
            "export task\n"
            "cmd echo up_cmd\n",
            encoding="utf-8",
        )
        up = self._run(
            [str(SCRIPT), "role=work", "task=F1", "-p", "up prompt", "big.txt:2-4"], cwd=str(self.tmp)
        )
        self._assert_ok(up)
        self.assertIn("Bundle-Name: agents_bundle\n", up.stdout)
        self.assertIn("Bundle-Protocol: 1\n", up.stdout)
        self.assertIn("Task: F1\n", up.stdout)
        self.assertNotIn("Role:", up.stdout)
        self.assertNotIn("Bundle-Expose:", up.stdout)
        (self.tmp / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:core\n"
            "if agents_bundle.task!=\n"
            "    let task={agents_bundle.task:}\n"
            "    export task\n"
            "cmd echo down_cmd\n",
            encoding="utf-8",
        )
        return up.stdout

    def test_pipe_merges_dedups_and_chains_fragments(self):
        up_out = self._run_upstream()
        down = self._run([str(SCRIPT), "big.txt:3-6"], cwd=str(self.tmp), input=up_out)
        self._assert_ok(down)
        self.assertIn(
            "Bundle-Command: agents_bundle role=work task=F1 -p 'up prompt' big.txt:2-4 | agents_bundle big.txt:3-6\n",
            down.stdout,
        )
        self.assertIn("Bundle-Name: agents_bundle\n", down.stdout)
        self.assertIn("Task: F1\n", down.stdout)
        _nonce, frags = self._extract_fragments(down.stdout)
        rules = {m["id"]: m for m, _ in frags if m["kind"] == "rule"}
        self.assertEqual(
            list(rules),
            [
                "vitalio/agents-rules:core/start",
                "vitalio/agents-rules:core/ssot",
                "vitalio/agents-rules:core/lang",
                "agents_bundle",
            ],
        )
        self.assertEqual(
            rules["vitalio/agents-rules:core/start"]["chain"],
            [".context.bundle", "vitalio/agents-rules:core"],
        )
        self.assertEqual(rules["agents_bundle"]["chain"], ["agents_bundle"])
        files = [(m, b) for m, b in frags if m["kind"] == "file"]
        self.assertEqual([m["name"] for m, _ in files], ["big.txt:2-6"])
        self.assertEqual(files[0][1], "===== $ sed -n '2,6p' big.txt =====\nline2\nline3\nline4\nline5\nline6")
        cmds = [m for m, _ in frags if m["kind"] == "cmd"]
        self.assertEqual([m["name"] for m in cmds], ["echo up_cmd", "echo down_cmd"])
        self.assertEqual(cmds[0]["chain"], [".context.bundle"])
        prompts = [(m, b) for m, b in frags if m["kind"] == "prompt"]
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0][0]["chain"], [])
        self.assertTrue(prompts[0][1].startswith("===== Prompt =====\nup prompt"))

        whole = self._run([str(SCRIPT), "big.txt"], cwd=str(self.tmp), input=up_out)
        self._assert_ok(whole)
        _n, whole_frags = self._extract_fragments(whole.stdout)
        whole_files = [(m, b) for m, b in whole_frags if m["kind"] == "file"]
        self.assertEqual([m["name"] for m, _ in whole_files], ["big.txt"])
        self.assertTrue(whole_files[0][1].endswith("line10"))

    def test_producer_namespacing_and_canonical_4_kind_fragments(self):
        (self.tmp / "a.py").write_text("A = 1\n", encoding="utf-8")
        (self.tmp / "b.py").write_text("B = 2\n", encoding="utf-8")
        p1_meta = {"kind": "prompt", "id": "F9", "name": "TODO.md:F9", "chain": ["todo_md"]}
        p2_meta = {"kind": "prompt", "name": "notes", "chain": ["todo_md"]}
        file_meta = {"kind": "file", "name": "a.py", "chain": ["todo_md"]}
        weird = {"kind": "weird", "id": "w"}
        legacy_inc = {"kind": "include", "name": "a.py"}
        upstream = (
            "Bundle-Command: todo_md F9\n"
            "Bundle-Name: todo_md\n"
            "Bundle-Boundary: abc123\n"
            "Task: F9\n"
            "Prefix: F\n"
            "Status: WIP\n"
            "Title: Namespaced task\n"
            "Files: b.py\n\n"
            f"<!-- bundle:abc123:part {json.dumps(file_meta)} -->\n"
            "===== $ cat a.py =====\nA = 1\n"
            "<!-- bundle:abc123:end -->\n"
            f"<!-- bundle:abc123:part {json.dumps(p1_meta)} -->\n"
            "===== Prompt =====\n# F9 title\n"
            "<!-- bundle:abc123:end -->\n"
            f"<!-- bundle:abc123:part {json.dumps(p2_meta)} -->\n"
            "Extra context\n"
            "<!-- bundle:abc123:end -->\n"
            f"<!-- bundle:abc123:part {json.dumps(weird)} -->\nignored\n<!-- bundle:abc123:end -->\n"
            f"<!-- bundle:abc123:part {json.dumps(legacy_inc)} -->\nignored\n<!-- bundle:abc123:end -->\n"
        )
        (self.tmp / ".context.bundle").write_text(
            "if todo_md.status=WIP,NEXT\n"
            "    let role=work\n"
            "export role\n"
            "if todo_md.task!=\n"
            "    let task={todo_md.task:}\n"
            "    export task\n"
            "if todo_md.title!=\n"
            "    let title={todo_md.title:}\n"
            "    export title\n"
            "if role=work\n"
            "    file {todo_md.files:}\n"
            "prompt Local note for {todo_md.prefix:}:{task:}\n",
            encoding="utf-8",
        )
        r = self._run([str(SCRIPT)], cwd=str(self.tmp), input=upstream)
        self._assert_ok(r)
        self.assertIn("Bundle-Command: todo_md F9 | agents_bundle\n", r.stdout)
        self.assertIn("Bundle-Name: agents_bundle\n", r.stdout)
        self.assertNotIn("Bundle-Expose:", r.stdout)
        self.assertNotIn("Bundle-Hide:", r.stdout)
        self.assertIn("Role: work\n", r.stdout)
        self.assertIn("Task: F9\n", r.stdout)
        self.assertIn("Title: Namespaced task\n", r.stdout)
        self.assertNotIn("Files:", r.stdout)
        self.assertNotIn("Prefix:", r.stdout)
        self.assertNotIn("Status:", r.stdout)
        self.assertIn("unknown kind: weird", r.stderr)
        self.assertIn("unknown kind: include", r.stderr)
        _n, frags = self._extract_fragments(r.stdout)
        for m, _ in frags:
            self.assertIn(m["kind"], ("rule", "file", "cmd", "prompt"))
        file_frags = [(m, b) for m, b in frags if m["kind"] == "file"]
        self.assertEqual([m["name"] for m, _ in file_frags], ["a.py", "b.py"])
        prompts = [(m, b) for m, b in frags if m["kind"] == "prompt"]
        self.assertEqual(
            [m for m, _ in prompts],
            [
                {"kind": "prompt", "id": "F9", "name": "TODO.md:F9", "chain": ["todo_md"]},
                {"kind": "prompt", "name": "notes", "chain": ["todo_md"]},
                {"kind": "prompt", "chain": [".context.bundle"]},
            ],
        )
        self.assertEqual(prompts[0][1], "===== Prompt =====\n# F9 title")
        self.assertEqual(prompts[1][1], "Extra context")
        self.assertEqual(prompts[2][1], "Local note for F:F9")

    def test_duplicate_bundle_name_producer_rejected(self):
        (self.tmp / ".context.bundle").write_text("prompt hi\n", encoding="utf-8")
        for label, bad_stdin in [
            (
                "duplicate_bundle_name_header",
                "Bundle-Name: todo_md\nBundle-Name: todo_md\nBundle-Boundary: abc\n\n",
            ),
            (
                "already_namespaced_collision",
                "Bundle-Name: todo_md\ntodo_md.task: F1\nTask: F2\nBundle-Boundary: abc\n\n",
            ),
            (
                "pipeline_command_collision",
                "Bundle-Command: todo_md F1 | todo_md F2\nBundle-Name: todo_md\nBundle-Boundary: abc\n\n",
            ),
        ]:
            with self.subTest(case=label):
                r = self._run([str(SCRIPT)], cwd=str(self.tmp), input=bad_stdin)
                self.assertNotEqual(r.returncode, 0, msg=r.stdout)
                self.assertIn("duplicate Bundle-Name producer 'todo_md'", r.stderr)

    def _upstream_rules(self, role_header: str | None, body: str, argv: list[str]) -> dict[str, str]:
        meta = {"kind": "rule", "id": "todo_md:todo_md", "chain": ["todo_md"]}
        head = "Bundle-Boundary: abc123\n"
        if role_header:
            head += f"Role: {role_header}\n"
        upstream = (
            head + "\n"
            f"<!-- bundle:abc123:part {json.dumps(meta)} -->\n{body}\n<!-- bundle:abc123:end -->\n"
        )
        (self.tmp / ".context.bundle").write_text("prompt Local note\n", encoding="utf-8")
        r = self._run([str(SCRIPT), *argv], cwd=str(self.tmp), input=upstream)
        self._assert_ok(r)
        _n, frags = self._extract_fragments(r.stdout)
        return {m["id"]: b for m, b in frags if m["kind"] == "rule"}

    def test_upstream_rule_fragment_strips_description_and_renders_vars(self):
        body = "# Description: Tool rule\n- Tool: run {cmd:todo_md} as {role:none} role"
        rules = self._upstream_rules("work", body, [])
        text = rules["todo_md:todo_md"]
        self.assertIn("- Tool: run todo_md as work role", text)
        self.assertNotIn("Description", text)
        cli = self._upstream_rules("work", body, ["role=plan", "cmd=tm"])
        self.assertIn("- Tool: run tm as plan role", cli["todo_md:todo_md"])

    def test_upstream_rule_fragment_with_empty_body_is_skipped(self):
        rules = self._upstream_rules(None, "# Description: Only metadata", [])
        self.assertNotIn("todo_md:todo_md", rules)


if __name__ == "__main__":
    unittest.main()
