#!/usr/bin/env python3
"""Rules engine, package cache, and circular dependency tests for agents_bundle."""
import http.server
import os
import threading
import unittest
from pathlib import Path

from tests.helpers import AgentsBundleTestCase, SCRIPT


class TestRulesEngine(AgentsBundleTestCase):
    def test_builtin_vars_override_in_ruleset(self):
        rp = self._run(
            [str(SCRIPT), "ruleset", "vitalio/agents-rules:default", "os=windows", "vcs=cvs", "-v"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(rp)
        self.assertIn("[if os=windows] rule os/windows -> rules/os/windows.md", rp.stdout)
        self.assertIn("[if vcs=cvs] rule vcs/cvs -> rules/vcs/cvs.md", rp.stdout)
        self.assertNotIn("rules/os/linux.md", rp.stdout)
        self.assertNotIn("rules/vcs/git.md", rp.stdout)

    def test_cli_ruleset_rule_and_list(self):
        rl = self._run([str(SCRIPT), "--list"], capture_output=True, text=True, check=False)
        self._assert_ok(rl)
        self.assertIn("Built-in variables", rl.stdout)
        self.assertIn("piped", rl.stdout)
        self.assertIn("[if os=linux] rule os/linux", rl.stdout)
        self.assertIn("Bundles in 'vitalio/agents-rules'", rl.stdout)
        self.assertNotIn("os/auto", rl.stdout)
        self.assertNotIn("vcs/auto", rl.stdout)

        rr = self._run([str(SCRIPT), "rule", "vitalio/agents-rules:release/single-file-build"], capture_output=True, text=True, check=False)
        self._assert_ok(rr)
        self.assertIn("Single-file build from modular `src/`:", rr.stdout)

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

        r1 = self._run([str(SCRIPT), "--update-cache"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self._assert_ok(r1)
        self.assertIn("package owner/repo: updated", r1.stdout)
        self.assertIn(new_head, r1.stdout)
        self.assertEqual((clone / "f.txt").read_text(encoding="utf-8"), "v2\n")

        r2 = self._run([str(SCRIPT), "--update-cache"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self._assert_ok(r2)
        self.assertIn("package owner/repo: up to date", r2.stdout)

    def test_update_cache_refreshes_url_files(self):
        url_rule = self.tmp / "remote_rule.md"
        url_rule.write_text("# Description: R\n- Remote rule body one.\n", encoding="utf-8")
        cmd = [str(SCRIPT), "rule", url_rule.as_uri()]
        r1 = self._run(cmd, cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self._assert_ok(r1)
        self.assertIn("Remote rule body one.", r1.stdout)

        url_rule.write_text("# Description: R\n- Remote rule body two.\n", encoding="utf-8")
        ru = self._run([str(SCRIPT), "--update-cache"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self._assert_ok(ru)
        self.assertIn(f"url {url_rule.as_uri()}: updated", ru.stdout)

        r2 = self._run(cmd, cwd=str(self.tmp), capture_output=True, text=True, check=False)
        self.assertIn("Remote rule body two.", r2.stdout)

        ru2 = self._run([str(SCRIPT), "--update-cache"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
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
            r = self._run([str(SCRIPT), "--refresh"], cwd=str(self.tmp), capture_output=True, text=True, check=False)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        self._assert_ok(r)
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
        r = self._run(
            [str(SCRIPT), "rule", "vitalio/agents-rules:core/ssot"],
            cwd=str(self.tmp),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r.returncode, 0, msg=f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}")
        self.assertNotIn("Home fallback body", r.stdout)
        self.assertIn("failed to fetch package", r.stderr)

    def test_circular_ruleset_and_bundle_references_fail_fast(self):
        pkg_dir = Path(os.environ["AGENTS_BUNDLE_LOCAL_PKG_DIR"])
        (pkg_dir / "rulesets" / "self_loop.ruleset").write_text(
            "# Description: Self-referential ruleset\n"
            "ruleset self_loop\n",
            encoding="utf-8",
        )
        (pkg_dir / "rulesets" / "cycle_a.ruleset").write_text(
            "# Description: Cycle A\n"
            "rule core/start\n"
            "ruleset cycle_b\n",
            encoding="utf-8",
        )
        (pkg_dir / "rulesets" / "cycle_b.ruleset").write_text(
            "# Description: Cycle B\n"
            "ruleset cycle_c\n",
            encoding="utf-8",
        )
        (pkg_dir / "rulesets" / "cycle_c.ruleset").write_text(
            "# Description: Cycle C\n"
            "ruleset vitalio/agents-rules:cycle_a\n",
            encoding="utf-8",
        )

        # 1. Self-referential ruleset fails fast with cycle path
        r_rs_self = self._run(
            [str(SCRIPT), "ruleset", "vitalio/agents-rules:self_loop"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_rs_self.returncode, 0, msg=f"stdout:\n{r_rs_self.stdout}\nstderr:\n{r_rs_self.stderr}")
        self.assertNotIn("RecursionError", r_rs_self.stderr)
        self.assertIn(
            "circular ruleset reference detected: vitalio/agents-rules:self_loop -> vitalio/agents-rules:self_loop",
            r_rs_self.stderr,
        )

        # 2. Multi-step package ruleset cycle fails fast with full cycle path
        (self.tmp / ".agents_bundle").write_text(
            "ruleset vitalio/agents-rules:cycle_a\n",
            encoding="utf-8",
        )
        r_rs_multi = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_rs_multi.returncode, 0, msg=f"stdout:\n{r_rs_multi.stdout}\nstderr:\n{r_rs_multi.stderr}")
        self.assertNotIn("RecursionError", r_rs_multi.stderr)
        self.assertIn(
            "circular ruleset reference detected: "
            "vitalio/agents-rules:cycle_a -> vitalio/agents-rules:cycle_b -> "
            "vitalio/agents-rules:cycle_c -> vitalio/agents-rules:cycle_a",
            r_rs_multi.stderr,
        )

        # 3. Local file ruleset cycle across relative and absolute paths fails fast
        rs_file_a = self.tmp / "rs_a.ruleset"
        rs_file_b = self.tmp / "rs_b.ruleset"
        rs_file_a.write_text("ruleset ./rs_b.ruleset\n", encoding="utf-8")
        rs_file_b.write_text(f"ruleset {rs_file_a.resolve().as_posix()}\n", encoding="utf-8")
        (self.tmp / ".agents_bundle").write_text("ruleset ./rs_a.ruleset\n", encoding="utf-8")
        r_rs_file = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_rs_file.returncode, 0, msg=f"stdout:\n{r_rs_file.stdout}\nstderr:\n{r_rs_file.stderr}")
        self.assertNotIn("RecursionError", r_rs_file.stderr)
        self.assertIn("circular ruleset reference detected:", r_rs_file.stderr)
        self.assertIn("./rs_a.ruleset -> ./rs_b.ruleset ->", r_rs_file.stderr)

        # 4. Self-referential bundle (both local file and package repo shorthand alias) fails fast
        self_bundle = self.tmp / "self.bundle"
        self_bundle.write_text(f"bundle {self_bundle.resolve().as_posix()}\n", encoding="utf-8")
        (self.tmp / ".agents_bundle").write_text("bundle ./self.bundle\n", encoding="utf-8")
        r_b_self = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_b_self.returncode, 0, msg=f"stdout:\n{r_b_self.stdout}\nstderr:\n{r_b_self.stderr}")
        self.assertNotIn("RecursionError", r_b_self.stderr)
        self.assertIn("circular bundle reference detected: .agents_bundle -> ./self.bundle ->", r_b_self.stderr)

        loop_pkg = pkg_dir / "vitalio" / "loop_pkg" / "bundles"
        loop_pkg.mkdir(parents=True)
        (loop_pkg / "loop_pkg.bundle").write_text(
            "bundle vitalio/loop_pkg:loop_pkg\n",
            encoding="utf-8",
        )
        (self.tmp / ".agents_bundle").write_text("bundle vitalio/loop_pkg\n", encoding="utf-8")
        r_b_alias = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_b_alias.returncode, 0, msg=f"stdout:\n{r_b_alias.stdout}\nstderr:\n{r_b_alias.stderr}")
        self.assertNotIn("RecursionError", r_b_alias.stderr)
        self.assertIn(
            "circular bundle reference detected: .agents_bundle -> vitalio/loop_pkg -> vitalio/loop_pkg:loop_pkg",
            r_b_alias.stderr,
        )

        # 5. Multi-step bundle cycle and cycle back to .agents_bundle fail fast
        b1 = self.tmp / "b1.bundle"
        b2 = self.tmp / "b2.bundle"
        b3 = self.tmp / "b3.bundle"
        b1.write_text("bundle ./b2.bundle\n", encoding="utf-8")
        b2.write_text("bundle ./b3.bundle\n", encoding="utf-8")
        b3.write_text(f"bundle {b1.resolve().as_posix()}\n", encoding="utf-8")
        (self.tmp / ".agents_bundle").write_text("bundle ./b1.bundle\n", encoding="utf-8")
        r_b_multi = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_b_multi.returncode, 0, msg=f"stdout:\n{r_b_multi.stdout}\nstderr:\n{r_b_multi.stderr}")
        self.assertNotIn("RecursionError", r_b_multi.stderr)
        self.assertIn(
            "circular bundle reference detected: .agents_bundle -> ./b1.bundle -> ./b2.bundle -> ./b3.bundle ->",
            r_b_multi.stderr,
        )

        b_root = self.tmp / "back_to_root.bundle"
        b_root.write_text("bundle ./.agents_bundle\n", encoding="utf-8")
        (self.tmp / ".agents_bundle").write_text("bundle ./back_to_root.bundle\n", encoding="utf-8")
        r_b_root = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_b_root.returncode, 0, msg=f"stdout:\n{r_b_root.stdout}\nstderr:\n{r_b_root.stderr}")
        self.assertNotIn("RecursionError", r_b_root.stderr)
        self.assertIn(
            "circular bundle reference detected: .agents_bundle -> ./back_to_root.bundle -> ./.agents_bundle",
            r_b_root.stderr,
        )

        # 6. Non-circular diamond ruleset and bundle references succeed
        shared_b = self.tmp / "diamond_shared.bundle"
        shared_b.write_text("ruleset vitalio/agents-rules:core\n", encoding="utf-8")
        branch_b = self.tmp / "diamond_branch.bundle"
        branch_b.write_text(
            f"bundle {shared_b.as_posix()}\n"
            "rule vitalio/agents-rules:stack/python-cli\n",
            encoding="utf-8",
        )
        (self.tmp / ".agents_bundle").write_text(
            f"bundle {shared_b.as_posix()}\n"
            f"bundle {branch_b.as_posix()}\n",
            encoding="utf-8",
        )
        r_diamond = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_diamond)
        self.assertIn("Python 3.9+ compatibility", r_diamond.stdout)


if __name__ == "__main__":
    unittest.main()
