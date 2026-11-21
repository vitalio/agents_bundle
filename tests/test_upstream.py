#!/usr/bin/env python3
"""Piped upstream bundle pass-through, protocol header, and chain provenance tests for agents_bundle."""
import json
import unittest

from tests.helpers import AgentsBundleTestCase, SCRIPT


class TestUpstream(AgentsBundleTestCase):
    def _run_upstream(self) -> str:
        (self.tmp / "big.txt").write_text("".join(f"line{i}\n" for i in range(1, 11)), encoding="utf-8")
        (self.tmp / ".agents_bundle").write_text(
            "ruleset vitalio/agents-rules:core\n$ echo up_cmd\n", encoding="utf-8"
        )
        up = self._run(
            [str(SCRIPT), "role=work", "task=F1", "-p", "up prompt", "big.txt:2-4"], cwd=str(self.tmp)
        )
        self._assert_ok(up)
        self.assertIn("Bundle-Protocol: 1\n", up.stdout)
        (self.tmp / ".agents_bundle").write_text(
            "ruleset vitalio/agents-rules:core\n$ echo down_cmd\n", encoding="utf-8"
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
            [".agents_bundle", "vitalio/agents-rules:core"],
        )
        self.assertEqual(rules["agents_bundle"]["chain"], ["agents_bundle"])
        incs = [(m, b) for m, b in frags if m["kind"] == "include"]
        self.assertEqual([m["name"] for m, _ in incs], ["big.txt:2-6"])
        self.assertEqual(incs[0][1], "===== $ sed -n '2,6p' big.txt =====\nline2\nline3\nline4\nline5\nline6")
        cmds = [m for m, _ in frags if m["kind"] == "cmd"]
        self.assertEqual([m["name"] for m in cmds], ["echo up_cmd", "echo down_cmd"])
        self.assertEqual(cmds[0]["chain"], [".agents_bundle"])
        prompts = [(m, b) for m, b in frags if m["kind"] == "prompt"]
        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0][0]["chain"], [])
        self.assertTrue(prompts[0][1].startswith("===== Prompt =====\nup prompt"))

        whole = self._run([str(SCRIPT), "big.txt"], cwd=str(self.tmp), input=up_out)
        self._assert_ok(whole)
        _n, whole_frags = self._extract_fragments(whole.stdout)
        whole_incs = [(m, b) for m, b in whole_frags if m["kind"] == "include"]
        self.assertEqual([m["name"] for m, _ in whole_incs], ["big.txt"])
        self.assertTrue(whole_incs[0][1].endswith("line10"))

    def test_pipe_preserves_task_fragment_and_merges_expose_hide(self):
        meta = {"kind": "task", "id": "F9", "name": "TODO.md:F9", "chain": ["todo_md"]}
        weird = {"kind": "weird", "id": "w"}
        upstream = (
            "Bundle-Command: up_cmd\n"
            "Bundle-Boundary: abc123\n"
            "Bundle-Expose: Role, Task, Title, Foo-Bar\n"
            "Bundle-Hide: Secret\n"
            "Task: F9\n\n"
            f"<!-- bundle:abc123:part {json.dumps(meta)} -->\n"
            "===== Prompt =====\n# F9 title\n"
            "<!-- bundle:abc123:end -->\n"
            f"<!-- bundle:abc123:part {json.dumps(weird)} -->\nignored\n<!-- bundle:abc123:end -->\n"
        )
        (self.tmp / ".agents_bundle").write_text("prompt Local note\n", encoding="utf-8")
        r = self._run([str(SCRIPT)], cwd=str(self.tmp), input=upstream)
        self._assert_ok(r)
        self.assertIn("Bundle-Command: up_cmd | agents_bundle\n", r.stdout)
        self.assertIn("Bundle-Expose: Role, Task, Title, Foo-Bar\n", r.stdout)
        self.assertIn("Bundle-Hide: Secret\n", r.stdout)
        self.assertIn("Task: F9\n", r.stdout)
        self.assertIn("unknown kind: weird", r.stderr)
        _n, frags = self._extract_fragments(r.stdout)
        prompts = [(m, b) for m, b in frags if m["kind"] in ("task", "prompt")]
        self.assertEqual([m for m, _ in prompts], [meta, {"kind": "prompt", "chain": [".agents_bundle"]}])
        self.assertEqual(prompts[0][1], "===== Prompt =====\n# F9 title")
        self.assertEqual(prompts[1][1], "Local note")


if __name__ == "__main__":
    unittest.main()
