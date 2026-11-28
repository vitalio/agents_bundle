#!/usr/bin/env python3
"""Repository file tree (--tree) tests for context-bundle."""
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
        env = {**os.environ, "CONTEXT_BUNDLE_LOCAL_PKG_DIR": str(self.tmp / "pkg_repo")}
        r_role = self._run(
            [str(SCRIPT), "--bundle", "vitalio/agents-rules:default", "role=audit", "--plain"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self._assert_ok(r_role)
        self.assertIn("- Role (Auditor): Check consistency.", r_role.stdout)
        self.assertNotIn("Maintainer comment", r_role.stdout)
        self.assertNotIn("html comment", r_role.stdout)

    def test_tree_total_size_and_large_or_dense_file_sizes(self):
        repo = self.tmp / "size_repo"
        repo.mkdir()
        # Small regular file (< 16 KB and <= 120 B/line): compact (<N>L) only
        (repo / "small.py").write_text("print('ok')\n" * 10, encoding="utf-8")
        # Large file (>= 16 KB, normal line length): shows (<N>L, <X>K)
        (repo / "large.py").write_text(("x = " + "1" * 75 + "\n") * 220, encoding="utf-8")
        # Dense single-line file (< 16 KB, > 120 B/line): shows (<N>L, <X>K)
        (repo / "dense.min.js").write_text("var a=" + "0" * 2042 + ";\n", encoding="utf-8")

        rt = self._run(
            [str(SCRIPT), "--tree", str(repo)],
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(rt)
        self.assertIn("small.py (10L)\n", rt.stdout)
        self.assertIn("large.py (220L, 17K)\n", rt.stdout)
        self.assertIn("dense.min.js (1L, 2K)\n", rt.stdout)
        self.assertIn("# Total: 3 files, 231 lines (19.3 KB)\n", rt.stdout)

    def test_tree_walk_fallback_prunes_cvs_and_cvsignore_preserving_agents_md(self):
        from src.tree import build_repo_tree

        repo = self.tmp / "cvs_repo"
        (repo / "CVS").mkdir(parents=True)
        (repo / "CVS" / "Root").write_text(":pserver:anon@cvs.example.org:/cvsroot\n", encoding="utf-8")
        (repo / "CVS" / "Entries").write_text("/Makefile/1.1/dummy//\n", encoding="utf-8")
        (repo / "src" / "CVS").mkdir(parents=True)
        (repo / "src" / "CVS" / "Entries").write_text("/main.c/1.1/dummy//\n", encoding="utf-8")
        (repo / ".svn").mkdir(parents=True)
        (repo / ".svn" / "entries").write_text("12\n", encoding="utf-8")
        (repo / ".hg").mkdir(parents=True)
        (repo / ".hg" / "dirstate").write_text("hg\n", encoding="utf-8")
        (repo / "build.linux" / "obj").mkdir(parents=True)
        (repo / "build.linux" / "obj" / "app.o").write_text("bin\n", encoding="utf-8")
        (repo / "build.x86").mkdir(parents=True)
        (repo / "build.x86" / "out.bin").write_text("bin\n", encoding="utf-8")
        (repo / "out").mkdir(parents=True)
        (repo / "out" / "bundle.js").write_text("var x = 1;\n", encoding="utf-8")
        (repo / "src" / "gen").mkdir(parents=True)
        (repo / "src" / "gen" / "auto.c").write_text("int g;\n", encoding="utf-8")
        (repo / "src" / "main.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        (repo / "src" / "main.o").write_text("obj\n", encoding="utf-8")
        (repo / "src" / "AGENTS.md").write_text("# Subdir agent guide\n", encoding="utf-8")
        (repo / "AGENTS.md").write_text("# Root agent guide\n", encoding="utf-8")
        (repo / "NOTES.md").write_text("# Ignored doc\n", encoding="utf-8")
        (repo / ".cvsignore").write_text(
            "# CVS ignore patterns\nbuild.* *.o\nAGENTS.md NOTES.md\nsrc/gen\n",
            encoding="utf-8",
        )
        (repo / ".gitignore").write_text("out/\nAGENTS.md\n", encoding="utf-8")

        tree_text = build_repo_tree(root_dir=repo)
        self.assertNotIn("CVS", tree_text)
        self.assertNotIn(".svn", tree_text)
        self.assertNotIn(".hg", tree_text)
        self.assertNotIn("build.linux", tree_text)
        self.assertNotIn("build.x86", tree_text)
        self.assertNotIn("main.o", tree_text)
        self.assertNotIn("NOTES.md", tree_text)
        self.assertNotIn("auto.c", tree_text)
        self.assertNotIn("out/", tree_text)
        self.assertIn("main.c (1L)", tree_text)
        self.assertEqual(tree_text.count("AGENTS.md (1L)"), 2)

    def test_tree_large_deep_repository_collapses_subsecond(self):
        import time
        from unittest import mock
        from src import tree as tree_mod

        # Synthesize 10,500 nested directories and 50,000 files
        rel_files: list[str] = ["AGENTS.md"]
        for top_i in range(15):
            for mid_i in range(35):
                for leaf_i in range(20):
                    d_path = f"pkg_{top_i:02d}/mod_{mid_i:02d}/sub_{leaf_i:02d}"
                    for f_i in range(4):
                        rel_files.append(f"{d_path}/file_{f_i}.py")
        for extra_i in range(8000):
            rel_files.append(f"pkg_{extra_i % 15:02d}/extra_{extra_i:04d}.py")

        self.assertGreaterEqual(len(rel_files), 50000)

        with (
            mock.patch.object(tree_mod, "_collect_repo_files", new=lambda _r, _e: (rel_files, set())),
            mock.patch.object(tree_mod, "_inspect_file_meta", new=lambda _p: (25, False, 600)),
        ):
            t0 = time.monotonic()
            out_default = tree_mod.build_repo_tree(root_dir=self.tmp, max_lines=160, max_tokens=1600)
            elapsed_default = time.monotonic() - t0

            t1 = time.monotonic()
            out_token_bound = tree_mod.build_repo_tree(root_dir=self.tmp, max_lines=5000, max_tokens=400)
            elapsed_token_bound = time.monotonic() - t1

        self.assertLess(elapsed_default, 1.0)
        self.assertLess(elapsed_token_bound, 1.0)
        default_lines = out_default.strip().splitlines()
        self.assertLessEqual(len(default_lines), 160)
        self.assertLessEqual(tree_mod.approx_tokens(out_default), 1600)
        self.assertIn("AGENTS.md (25L)", out_default)
        self.assertIn("# Total: 50001 files, 1,250,025 lines", out_default)
        self.assertLessEqual(tree_mod.approx_tokens(out_token_bound), 400)


if __name__ == "__main__":
    unittest.main()
