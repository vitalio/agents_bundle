#!/usr/bin/env python3
"""Repository file tree (--tree) tests for agents_bundle."""
import os
import unittest

from tests.helpers import AgentsBundleTestCase, SCRIPT


class TestTree(AgentsBundleTestCase):
    def test_tree_exclude_and_truncation(self):
        (self.tmp / "bumps" / "nested").mkdir(parents=True)
        (self.tmp / "bumps" / "nested" / "dump.txt").write_text("a\nb\nc\n", encoding="utf-8")
        (self.tmp / "tools").mkdir()
        for idx in range(12):
            (self.tmp / "tools" / f"tool_{idx:02d}.py").write_text("print(1)\n", encoding="utf-8")

        rt = self._run(
            [str(SCRIPT), "--tree", str(self.tmp), "-x", "bumps", "--max-lines", "12"],
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(rt)
        self.assertIn("bumps/ (excluded)", rt.stdout)
        self.assertNotIn("dump.txt", rt.stdout)
        self.assertIn("tools/", rt.stdout)
        self.assertIn("more files", rt.stdout)

    def test_tree_pins_agents_md_and_rules_ignore_agents_md(self):
        sub = self.tmp / "pkg_repo" / "agents" / "core"
        sub.mkdir(parents=True)
        (sub / "AGENTS.md").write_text("# Core philosophy\n", encoding="utf-8")
        (sub / "ssot.md").write_text("# Description: SSOT\n- SSOT rule\n", encoding="utf-8")
        for idx in range(12):
            (sub / f"z_file_{idx:02d}.txt").write_text("line\n", encoding="utf-8")
        r_tree = self._run(
            [str(SCRIPT), "--tree", str(self.tmp / "pkg_repo"), "--max-lines", "12"],
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_tree)
        self.assertIn("AGENTS.md", r_tree.stdout)

        # Verify comment stripping in rules and dynamic {role:} target resolution in bundles
        role_dir = self.tmp / "pkg_repo" / "agents" / "role"
        role_dir.mkdir(parents=True)
        (role_dir / "audit.md").write_text(
            "# Description: Auditor\n# Maintainer comment that must be stripped\n<!-- html comment -->\n- Role (Auditor): Check consistency.\n",
            encoding="utf-8",
        )
        p_dir = self.tmp / "pkg_repo" / "agents"
        p_dir.mkdir(parents=True, exist_ok=True)
        (p_dir / "default.bundle").write_text(
            "# Description: Default\nrule core/ssot\nif role!=\n    rule role/{role:}\n",
            encoding="utf-8",
        )
        env = {**os.environ, "AGENTS_BUNDLE_LOCAL_PKG_DIR": str(self.tmp / "pkg_repo")}
        r_role = self._run(
            [str(SCRIPT), "bundle", "vitalio/agents-rules:default", "role=audit", "--plain"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self._assert_ok(r_role)
        self.assertIn("- Role (Auditor): Check consistency.", r_role.stdout)
        self.assertNotIn("Maintainer comment", r_role.stdout)
        self.assertNotIn("html comment", r_role.stdout)


if __name__ == "__main__":
    unittest.main()
