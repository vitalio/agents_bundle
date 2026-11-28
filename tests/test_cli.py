#!/usr/bin/env python3
"""CLI, build check, installer, and uninstaller tests for context-bundle."""
import importlib.util
import os
import re
import sys
import unittest

from tests.helpers import AgentsBundleTestCase, BUILD_PY, INSTALL_SH, ROOT, SCRIPT


class TestCLI(AgentsBundleTestCase):
    def test_build_check_help_and_version(self):
        rb = self._run_subprocess([sys.executable, str(BUILD_PY), "--check"], capture_output=True, text=True, check=False)
        self._assert_ok(rb)
        rh = self._run_subprocess([str(SCRIPT), "-h"], capture_output=True, text=True, check=False)
        self._assert_ok(rh)
        self.assertIn("Usage:", rh.stdout)
        self.assertIn("Commands:", rh.stdout)
        self.assertIn("--plain", rh.stdout)
        self.assertIn("--update [--check | --force]", rh.stdout)
        self.assertIn("--uninstall", rh.stdout)
        self.assertIn("CONTEXT_BUNDLE_PLAIN", rh.stdout)
        self.assertIn("Bundle Output Protocol:", rh.stdout)
        self.assertIn("-x, --exclude DIR", rh.stdout)
        self.assertIn("context [k=v ...] [FILE ...]", rh.stdout)
        self.assertIn("--bundle <pkg>[:<name>] [k=v]", rh.stdout)
        self.assertIn("--rule <pkg>[:<name...>] [k=v]", rh.stdout)
        self.assertIn("local agents/ and .context.bundle", " ".join(rh.stdout.split()))
        self.assertNotIn("vitalio/agents-rules", rh.stdout)
        self.assertNotIn("--check-update", rh.stdout)
        self.assertNotIn("--self-update", rh.stdout)
        self.assertNotIn("--agents", rh.stdout)
        rv = self._run_subprocess([str(SCRIPT), "--version"], capture_output=True, text=True, check=False)
        self._assert_ok(rv)
        ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(rv.stdout.strip(), f"context {ver}")

    def test_help_width_and_column_alignment(self):
        for flag in ("-h", "--help"):
            with self.subTest(flag=flag):
                r = self._run_subprocess([str(SCRIPT), flag], capture_output=True, text=True, check=False)
                self._assert_ok(r)
                self.assertNotIn("{", r.stdout)
                lines = r.stdout.splitlines()
                for line in lines:
                    self.assertLessEqual(len(line), 100, msg=line)
                sections = {}
                current_title = None
                current = None
                for line in lines:
                    if not line.strip():
                        current_title = None
                        current = None
                    elif not line.startswith(" "):
                        current_title = line
                        current = sections.setdefault(line, {"lines": [], "entries": set(), "conts": set()})
                    elif current is not None:
                        current["lines"].append(line)
                        if current_title == "Usage:":
                            continue
                        indent = len(line) - len(line.lstrip())
                        if indent == 2:
                            m = re.match(r"^ {2}\S.*?\S( {2,})\S", line)
                            self.assertIsNotNone(m, msg=line)
                            current["entries"].add(m.end() - 1)
                        else:
                            current["conts"].add(indent)
                self.assertIn("Usage:", sections)
                self.assertEqual(
                    sections["Usage:"]["lines"],
                    [
                        "  context [k=v ...] [-p TEXT] [FILE ...]",
                        "  context <command|flag> [args] [opts]",
                    ],
                )
                shared_cols = set()
                for title in ("Commands:", "Options:", "Bundle Output Protocol:", "Environment:"):
                    with self.subTest(section=title):
                        self.assertIn(title, sections)
                        self.assertEqual(len(sections[title]["entries"]), 1)
                        self.assertLessEqual(sections[title]["conts"], sections[title]["entries"])
                        shared_cols.update(sections[title]["entries"])
                self.assertEqual(len(shared_cols), 1)
                self.assertLessEqual(next(iter(shared_cols)), 36)
                opts_lines = [ln for ln in sections["Options:"]["lines"] if ln.startswith("  -")]
                self.assertTrue(opts_lines[-2].startswith("  -V, --version "))
                self.assertTrue(opts_lines[-1].startswith("  -h, --help "))

    def test_build_strips_internal_imports(self):
        spec = importlib.util.spec_from_file_location("build_mod", BUILD_PY)
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        hdr = build.header_import_set("import os\nfrom pathlib import Path\n")
        src = (
            "from __future__ import annotations\n\nimport os\nfrom pathlib import Path\n\n"
            "from src.header import (\n    A,\n    B,\n)\n\n\ndef f():\n    return os, Path, A, B\n"
        )
        order = ["header.py", "core.py", "tree.py"]
        self.assertEqual(
            build.strip_module_imports("core.py", src, hdr, order),
            "def f():\n    return os, Path, A, B",
        )
        with self.subTest(case="stdlib import missing in header"):
            with self.assertRaises(SystemExit):
                build.strip_module_imports("core.py", "import json\n", hdr, order)
        with self.subTest(case="sibling import from a later module"):
            with self.assertRaises(SystemExit):
                build.strip_module_imports("core.py", "from src.tree import x\n", hdr, order)
        self.assertNotIn("from src.", SCRIPT.read_text(encoding="utf-8"))

    def test_missing_spec_fails_with_hint(self):
        r = self._run([str(SCRIPT)], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertEqual(r.returncode, 2, msg=f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}")
        self.assertEqual(r.stdout, "")
        self.assertIn(".context.bundle not found", r.stderr)
        self.assertIn("context --init", r.stderr)

    def test_bundle_subcommand_renders_bundle(self):
        target = "vitalio/context-bundle:context"
        with self.subTest(case="plain output without .context.bundle"):
            r = self._run(
                [str(SCRIPT), "--bundle", target, "role=design", "--plain"],
                cwd=str(self.tmp),
                capture_output=True,
                text=True,
                check=False,
            )
            self._assert_ok(r)
            self.assertNotIn("Bundle-Boundary", r.stdout)
            self.assertIn("Role: design", r.stdout)
            self.assertIn("Context bundler & rules engine", r.stdout)
            self.assertIn("===== $ context --list =====", r.stdout)
        with self.subTest(case="transport headers and fragment markers"):
            r = self._run(
                [str(SCRIPT), "--bundle", "vitalio/todo-md"],
                cwd=str(self.tmp),
                capture_output=True,
                text=True,
                check=False,
            )
            self._assert_ok(r)
            self.assertIn("Bundle-Command: context --bundle vitalio/todo-md", r.stdout)
            _nonce, fragments = self._extract_fragments(r.stdout)
            self.assertEqual(fragments[0][0]["kind"], "rule")
            self.assertEqual(fragments[0][0]["chain"], ["vitalio/todo-md"])
        with self.subTest(case="missing target"):
            r = self._run([str(SCRIPT), "--bundle"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("usage: context --bundle", r.stderr)
        with self.subTest(case="flag as target rejected with usage"):
            r = self._run([str(SCRIPT), "--bundle", "--plain"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("usage: context --bundle", r.stderr)
        with self.subTest(case="unknown bundle"):
            r = self._run(
                [str(SCRIPT), "--bundle", "vitalio/context-bundle:nope"],
                cwd=str(self.tmp),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("unknown bundle 'nope'", r.stderr)
        with self.subTest(case="bare bundle and rule commands fail with exit code 2 and did-you-mean hint"):
            for bare in ("bundle", "rule"):
                r_bare = self._run(
                    [str(SCRIPT), bare, target],
                    cwd=str(self.tmp),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(r_bare.returncode, 2, msg=r_bare.stderr)
                self.assertEqual(r_bare.stdout, "")
                self.assertIn(
                    f"context: unknown bare command '{bare}'; did you mean '--{bare}'?",
                    r_bare.stderr,
                )

    def test_install_sh_installs_and_uninstalls(self):
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        xdg_cache = self.tmp / "xdg_cache"
        new_cache = xdg_cache / "context-bundle"
        (new_cache / "packages" / "vitalio" / "agents-rules").mkdir(parents=True)

        env = {k: v for k, v in os.environ.items() if k != "CONTEXT_BUNDLE_CACHE_DIR"}
        env["XDG_CACHE_HOME"] = str(xdg_cache)
        ri = self._run_subprocess(
            ["sh", str(INSTALL_SH), "--dir", str(bin_dir), "--yes"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(ri)
        installed_context = bin_dir / "context"
        self.assertTrue(installed_context.is_file())
        self.assertTrue(new_cache.is_dir())
        self.assertTrue((new_cache / "packages" / "vitalio" / "agents-rules").is_dir())

        with self.subTest(case="cli --uninstall removes binary and cache"):
            ru = self._run_subprocess(
                [str(installed_context), "--uninstall"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self._assert_ok(ru)
            self.assertFalse(installed_context.exists())
            self.assertFalse(new_cache.exists())

        with self.subTest(case="install.sh --uninstall removes binary and cache"):
            ri2 = self._run_subprocess(
                ["sh", str(INSTALL_SH), "--dir", str(bin_dir), "--yes"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self._assert_ok(ri2)
            new_cache.mkdir(parents=True, exist_ok=True)
            ru2 = self._run_subprocess(
                ["sh", str(INSTALL_SH), "--dir", str(bin_dir), "--uninstall"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self._assert_ok(ru2)
            self.assertFalse(installed_context.exists())
            self.assertFalse(new_cache.exists())

    def test_trust_cli_lifecycle_and_permissions(self):
        import hashlib
        import json
        import stat

        repo = self.tmp / "trust_repo"
        repo.mkdir()
        spec = repo / ".context.bundle"

        with self.subTest(case="missing spec fails with exit code 2"):
            r_miss = self._run([str(SCRIPT), "--trust", "-C", str(repo)])
            self.assertEqual(r_miss.returncode, 2, msg=r_miss.stderr)
            self.assertIn(".context.bundle not found", r_miss.stderr)

        with self.subTest(case="empty trust list before trusting"):
            r_empty = self._run([str(SCRIPT), "--trust", "--list"])
            self._assert_ok(r_empty)
            self.assertIn("No trusted .context.bundle files", r_empty.stdout)

        spec.write_text("cmd echo trusted_hello\n", encoding="utf-8")
        expected_sha = hashlib.sha256(spec.read_bytes()).hexdigest()

        with self.subTest(case="--trust records (realpath, sha256) with 0600 permissions"):
            r_trust = self._run([str(SCRIPT), "--trust", "-C", str(repo)])
            self._assert_ok(r_trust)
            self.assertIn(str(spec.resolve()), r_trust.stdout)
            self.assertIn(expected_sha, r_trust.stdout)
            trust_json = self.tmp / "state" / "context-bundle" / "trusted.json"
            self.assertTrue(trust_json.is_file())
            self.assertEqual(stat.S_IMODE(trust_json.stat().st_mode), 0o600)
            data = json.loads(trust_json.read_text(encoding="utf-8"))
            self.assertEqual(data.get(str(spec.resolve())), expected_sha)

        with self.subTest(case="--trust --list prints digest and realpath"):
            r_list = self._run([str(SCRIPT), "--trust", "--list"])
            self._assert_ok(r_list)
            self.assertIn(expected_sha, r_list.stdout)
            self.assertIn(str(spec.resolve()), r_list.stdout)

        with self.subTest(case="--trust --revoke removes entry"):
            r_rev = self._run([str(SCRIPT), "--trust", "--revoke", "-C", str(repo)])
            self._assert_ok(r_rev)
            self.assertIn("revoked trust", r_rev.stdout)
            r_list2 = self._run([str(SCRIPT), "--trust", "--list"])
            self._assert_ok(r_list2)
            self.assertNotIn(expected_sha, r_list2.stdout)

        with self.subTest(case="--trust accepts optional positional [DIR] for trust and revoke"):
            r_pos = self._run([str(SCRIPT), "--trust", str(repo)])
            self._assert_ok(r_pos)
            self.assertIn(expected_sha, r_pos.stdout)
            r_pos_rev = self._run([str(SCRIPT), "--trust", "--revoke", str(repo)])
            self._assert_ok(r_pos_rev)
            self.assertIn("revoked trust", r_pos_rev.stdout)

        with self.subTest(case="conflicting flags fail with usage"):
            r_bad = self._run([str(SCRIPT), "--trust", "--revoke", "--list"])
            self.assertNotEqual(r_bad.returncode, 0)
            self.assertIn("usage: context --trust", r_bad.stderr)

        with self.subTest(case="--trust inside prompt argument is not hijacked as subcommand"):
            spec.write_text("file AGENTS.md\n", encoding="utf-8")
            (repo / "AGENTS.md").write_text("# Doc\n", encoding="utf-8")
            r_prompt = self._run([str(SCRIPT), "-p", "--trust", "--plain"], cwd=str(repo))
            self._assert_ok(r_prompt)
            self.assertIn("===== Prompt =====\n--trust", r_prompt.stdout)

    def test_update_check_force_and_flag_validation(self):
        remote_script = self.tmp / "remote_context"
        installed_bin = self.tmp / "bin_update" / "context"
        installed_bin.parent.mkdir(parents=True, exist_ok=True)
        installed_bin.write_text(
            "#!/usr/bin/env python3\n# context-bundle-repo: vitalio/context-bundle\nVERSION = '0.1.0'\n",
            encoding="utf-8",
        )
        installed_bin.chmod(0o755)
        remote_url = remote_script.resolve().as_uri()
        env = {**os.environ, "CONTEXT_BUNDLE_UPDATE_URL": remote_url}

        with self.subTest(case="rejects mutually exclusive --check and --force with exit code 2"):
            r_both = self._run_in_process([str(installed_bin), "--update", "--check", "--force"], env=env)
            self.assertEqual(r_both.returncode, 2)
            self.assertIn("usage: context --update [--check | --force]", r_both.stderr)

        with self.subTest(case="rejects unknown flag under --update with exit code 2"):
            r_unk = self._run_in_process([str(installed_bin), "--update", "--bogus"], env=env)
            self.assertEqual(r_unk.returncode, 2)
            self.assertIn("usage: context --update [--check | --force]", r_unk.stderr)

        with self.subTest(case="removed --check-update and --self-update flags are rejected"):
            for old_flag in ("--check-update", "--self-update"):
                r_old = self._run_in_process([str(installed_bin), old_flag], env=env)
                self.assertNotEqual(r_old.returncode, 0)
                self.assertIn(f"unknown option: {old_flag}", r_old.stderr)

        remote_script.write_text(
            "#!/usr/bin/env python3\n# context-bundle-repo: vitalio/context-bundle\nVERSION = '0.0.1'\n",
            encoding="utf-8",
        )
        with self.subTest(case="--update --check reports up to date without modifying binary"):
            r_chk_old = self._run_in_process([str(installed_bin), "--update", "--check"], env=env)
            self._assert_ok(r_chk_old)
            self.assertIn("is up to date (remote: 0.0.1)", r_chk_old.stdout)
            self.assertIn("VERSION = '0.1.0'", installed_bin.read_text(encoding="utf-8"))

        with self.subTest(case="--update skips reinstall when already up to date"):
            r_up_noop = self._run_in_process([str(installed_bin), "--update"], env=env)
            self._assert_ok(r_up_noop)
            self.assertIn("is already up to date", r_up_noop.stdout)
            self.assertIn("VERSION = '0.1.0'", installed_bin.read_text(encoding="utf-8"))

        with self.subTest(case="--update --force reinstalls even when remote is older"):
            r_up_force = self._run_in_process([str(installed_bin), "--update", "--force"], env=env)
            self._assert_ok(r_up_force)
            self.assertIn("updated", r_up_force.stdout)
            self.assertIn("VERSION = '0.0.1'", installed_bin.read_text(encoding="utf-8"))

        remote_script.write_text(
            "#!/usr/bin/env python3\n# context-bundle-repo: vitalio/context-bundle\nVERSION = '99.0.0'\n",
            encoding="utf-8",
        )
        with self.subTest(case="--update --check detects newer remote version without modifying binary"):
            r_chk_new = self._run_in_process([str(installed_bin), "--update", "--check"], env=env)
            self._assert_ok(r_chk_new)
            self.assertIn("update available:", r_chk_new.stdout)
            self.assertIn("-> 99.0.0", r_chk_new.stdout)
            self.assertIn("VERSION = '0.0.1'", installed_bin.read_text(encoding="utf-8"))

        with self.subTest(case="--update installs newer remote version atomically"):
            r_up_new = self._run_in_process([str(installed_bin), "--update"], env=env)
            self._assert_ok(r_up_new)
            self.assertIn("-> 99.0.0", r_up_new.stdout)
            self.assertIn("VERSION = '99.0.0'", installed_bin.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
