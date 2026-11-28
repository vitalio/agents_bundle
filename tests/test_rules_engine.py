#!/usr/bin/env python3
"""Rules engine, package cache, and circular dependency tests for context-bundle."""
import http.server
import os
import threading
import unittest
from pathlib import Path

from tests.helpers import AgentsBundleTestCase, SCRIPT


class TestRulesEngine(AgentsBundleTestCase):
    def test_builtin_vars_override_in_bundle(self):
        rp = self._run(
            [str(SCRIPT), "--bundle", "vitalio/agents-rules:default", "os=macos", "vcs=cvs", "-v", "--plain"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(rp)
        self.assertIn("if os=macos rule vitalio/agents-rules:os/macos -> agents/os/macos.md", rp.stdout)
        self.assertIn("if vcs=cvs rule vitalio/agents-rules:vcs/cvs -> agents/vcs/cvs.md", rp.stdout)
        self.assertNotIn("agents/os/linux.md", rp.stdout)
        self.assertNotIn("agents/vcs/git.md", rp.stdout)

        # Multi-target rule CLI and exclude rejection
        rm = self._run(
            [str(SCRIPT), "--rule", "vitalio/agents-rules:core/start", "vitalio/agents-rules:core/ssot"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(rm)
        self.assertIn("Start priority", rm.stdout)
        self.assertIn("Single source of truth", rm.stdout)

        rex = self._run(
            [str(SCRIPT), "--rule", "vitalio/agents-rules:core/start", "-core/ssot"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(rex.returncode, 0)
        self.assertIn("excludes are not supported", rex.stderr)

    def test_cli_bundle_rule_and_list(self):
        rl_pkg = self._run(
            [str(SCRIPT), "--list", "vitalio/agents-rules"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(rl_pkg)
        self.assertIn("Built-in variables", rl_pkg.stdout)
        self.assertIn("piped", rl_pkg.stdout)
        self.assertIn("if os=linux rule os/linux", rl_pkg.stdout)
        self.assertIn("Bundles in 'vitalio/agents-rules'", rl_pkg.stdout)
        self.assertNotIn("os/auto", rl_pkg.stdout)
        self.assertNotIn("vcs/auto", rl_pkg.stdout)

        with self.subTest(case="--list without pkg and without local agents/ or .context.bundle prints hint"):
            empty_dir = self.tmp / "empty_list_dir"
            empty_dir.mkdir()
            rl_empty = self._run([str(SCRIPT), "--list"], cwd=str(empty_dir))
            self._assert_ok(rl_empty)
            self.assertIn("Built-in variables", rl_empty.stdout)
            self.assertIn("No local agents/ catalog or .context.bundle packages found", rl_empty.stdout)
            self.assertIn("context --list <owner>/<repo>", rl_empty.stdout)
            self.assertNotIn("vitalio/agents-rules", rl_empty.stdout)

        with self.subTest(case="--list without pkg lists local agents/ and .context.bundle packages"):
            proj_dir = self.tmp / "proj_list_dir"
            (proj_dir / "agents").mkdir(parents=True)
            (proj_dir / "agents" / "local_rule.md").write_text(
                "# Description: Local repo rule\n- Local rule body.\n",
                encoding="utf-8",
            )
            (proj_dir / "agents" / "local_bundle.bundle").write_text(
                "# Description: Local repo bundle\nrule local_rule\n",
                encoding="utf-8",
            )
            (proj_dir / ".context.bundle").write_text(
                "bundle vitalio/agents-rules:core\n",
                encoding="utf-8",
            )
            rl_proj = self._run([str(SCRIPT), "--list"], cwd=str(proj_dir))
            self._assert_ok(rl_proj)
            self.assertIn("Bundles in 'agents/' (use as 'bundle <bundle>'):", rl_proj.stdout)
            self.assertIn("local_bundle", rl_proj.stdout)
            self.assertIn("Atomic rules in 'agents/' (use as 'rule <rule>'):", rl_proj.stdout)
            self.assertIn("local_rule", rl_proj.stdout)
            self.assertIn("Bundles in 'vitalio/agents-rules'", rl_proj.stdout)

        rr = self._run(
            [str(SCRIPT), "--rule", "vitalio/agents-rules:release/single-file-build"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
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
        cmd = [str(SCRIPT), "--rule", url_rule.as_uri()]
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
            (self.tmp / ".context.bundle").write_text(f"rule {url}\nrule {url}\n", encoding="utf-8")
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
        env = {k: v for k, v in os.environ.items() if k != "CONTEXT_BUNDLE_LOCAL_PKG_DIR"}
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
            [str(SCRIPT), "--rule", "vitalio/agents-rules:core/ssot"],
            cwd=str(self.tmp),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r.returncode, 0, msg=f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}")
        self.assertNotIn("Home fallback body", r.stdout)
        self.assertIn("failed to fetch package", r.stderr)

    def test_circular_bundle_references_fail_fast(self):
        pkg_dir = Path(os.environ["CONTEXT_BUNDLE_LOCAL_PKG_DIR"])
        (pkg_dir / "agents" / "self_loop.bundle").write_text(
            "# Description: Self-referential bundle\n"
            "bundle self_loop\n",
            encoding="utf-8",
        )
        (pkg_dir / "agents" / "cycle_a.bundle").write_text(
            "# Description: Cycle A\n"
            "rule core/start\n"
            "bundle cycle_b\n",
            encoding="utf-8",
        )
        (pkg_dir / "agents" / "cycle_b.bundle").write_text(
            "# Description: Cycle B\n"
            "bundle cycle_c\n",
            encoding="utf-8",
        )
        (pkg_dir / "agents" / "cycle_c.bundle").write_text(
            "# Description: Cycle C\n"
            "bundle vitalio/agents-rules:cycle_a\n",
            encoding="utf-8",
        )

        # 1. Self-referential bundle fails fast with cycle path
        r_rs_self = self._run(
            [str(SCRIPT), "--bundle", "vitalio/agents-rules:self_loop"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_rs_self.returncode, 0, msg=f"stdout:\n{r_rs_self.stdout}\nstderr:\n{r_rs_self.stderr}")
        self.assertNotIn("RecursionError", r_rs_self.stderr)
        self.assertIn(
            "circular bundle reference detected: vitalio/agents-rules:self_loop -> self_loop",
            r_rs_self.stderr,
        )

        # 2. Multi-step package bundle cycle fails fast with full cycle path
        (self.tmp / ".context.bundle").write_text(
            "bundle vitalio/agents-rules:cycle_a\n",
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
            "circular bundle reference detected: "
            ".context.bundle -> vitalio/agents-rules:cycle_a -> cycle_b -> "
            "cycle_c -> vitalio/agents-rules:cycle_a",
            r_rs_multi.stderr,
        )

        # 3. Local file bundle cycle across relative and absolute paths fails fast
        rs_file_a = self.tmp / "rs_a.bundle"
        rs_file_b = self.tmp / "rs_b.bundle"
        rs_file_a.write_text("bundle ./rs_b.bundle\n", encoding="utf-8")
        rs_file_b.write_text(f"bundle {rs_file_a.resolve().as_posix()}\n", encoding="utf-8")
        (self.tmp / ".context.bundle").write_text("bundle ./rs_a.bundle\n", encoding="utf-8")
        r_rs_file = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_rs_file.returncode, 0, msg=f"stdout:\n{r_rs_file.stdout}\nstderr:\n{r_rs_file.stderr}")
        self.assertNotIn("RecursionError", r_rs_file.stderr)
        self.assertIn("circular bundle reference detected:", r_rs_file.stderr)
        self.assertIn("./rs_a.bundle -> ./rs_b.bundle ->", r_rs_file.stderr)

        # 4. Self-referential bundle (both local file and package repo shorthand alias) fails fast
        self_bundle = self.tmp / "self.bundle"
        self_bundle.write_text(f"bundle {self_bundle.resolve().as_posix()}\n", encoding="utf-8")
        (self.tmp / ".context.bundle").write_text("bundle ./self.bundle\n", encoding="utf-8")
        r_b_self = self._run(
            [str(SCRIPT)],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_b_self.returncode, 0, msg=f"stdout:\n{r_b_self.stdout}\nstderr:\n{r_b_self.stderr}")
        self.assertNotIn("RecursionError", r_b_self.stderr)
        self.assertIn("circular bundle reference detected: .context.bundle -> ./self.bundle ->", r_b_self.stderr)

        loop_pkg = pkg_dir / "vitalio" / "loop_pkg" / "agents"
        loop_pkg.mkdir(parents=True)
        (loop_pkg / "loop_pkg.bundle").write_text(
            "bundle vitalio/loop_pkg:loop_pkg\n",
            encoding="utf-8",
        )
        (self.tmp / ".context.bundle").write_text("bundle vitalio/loop_pkg\n", encoding="utf-8")
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
            "circular bundle reference detected: .context.bundle -> vitalio/loop_pkg -> vitalio/loop_pkg:loop_pkg",
            r_b_alias.stderr,
        )

        # 5. Multi-step bundle cycle and cycle back to .context.bundle fail fast
        b1 = self.tmp / "b1.bundle"
        b2 = self.tmp / "b2.bundle"
        b3 = self.tmp / "b3.bundle"
        b1.write_text("bundle ./b2.bundle\n", encoding="utf-8")
        b2.write_text("bundle ./b3.bundle\n", encoding="utf-8")
        b3.write_text(f"bundle {b1.resolve().as_posix()}\n", encoding="utf-8")
        (self.tmp / ".context.bundle").write_text("bundle ./b1.bundle\n", encoding="utf-8")
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
            "circular bundle reference detected: .context.bundle -> ./b1.bundle -> ./b2.bundle -> ./b3.bundle ->",
            r_b_multi.stderr,
        )

        b_root = self.tmp / "back_to_root.bundle"
        b_root.write_text("bundle ./.context.bundle\n", encoding="utf-8")
        (self.tmp / ".context.bundle").write_text("bundle ./back_to_root.bundle\n", encoding="utf-8")
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
            "circular bundle reference detected: .context.bundle -> ./back_to_root.bundle -> ./.context.bundle",
            r_b_root.stderr,
        )

        # 6. Non-circular diamond bundle references succeed
        shared_b = self.tmp / "diamond_shared.bundle"
        shared_b.write_text("bundle vitalio/agents-rules:core\n", encoding="utf-8")
        branch_b = self.tmp / "diamond_branch.bundle"
        branch_b.write_text(
            f"bundle {shared_b.as_posix()}\n"
            "rule vitalio/agents-rules:stack/python-cli\n",
            encoding="utf-8",
        )
        (self.tmp / ".context.bundle").write_text(
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

    def test_agents_package_dir_domain_bundles_and_relative_paths(self):
        pkg_root = Path(os.environ["CONTEXT_BUNDLE_LOCAL_PKG_DIR"])
        mod_pkg = pkg_root / "vitalio" / "modern_pkg"
        (mod_pkg / "agents" / "core").mkdir(parents=True)
        (mod_pkg / "agents" / "coding").mkdir(parents=True)
        (mod_pkg / "agents" / "stack" / "python").mkdir(parents=True)
        (mod_pkg / "custom" / "sub").mkdir(parents=True)

        (mod_pkg / "agents" / "AGENTS.md").write_text("# Ignored repo AGENTS.md\n", encoding="utf-8")
        (mod_pkg / "agents" / "README.md").write_text("# Ignored repo README.md\n", encoding="utf-8")
        (mod_pkg / "agents" / "core" / "axiom.md").write_text(
            "# Description: Core axiom\n- Canonical agents/ core axiom body.\n",
            encoding="utf-8",
        )
        (mod_pkg / "agents" / "coding" / "arch.md").write_text(
            "# Description: Coding arch\n- Coding architecture rule body.\n",
            encoding="utf-8",
        )
        (mod_pkg / "agents" / "coding" / "coding.bundle").write_text(
            "# Description: Coding domain bundle\n"
            "rule coding/arch\n"
            "rule ./local_coding.md\n",
            encoding="utf-8",
        )
        (mod_pkg / "agents" / "coding" / "local_coding.md").write_text(
            "# Description: Local coding rule\n- Relative rule inside coding domain.\n",
            encoding="utf-8",
        )
        (mod_pkg / "agents" / "stack" / "python" / "python.bundle").write_text(
            "# Description: Python stack bundle\n"
            "rule stack/python/typing\n",
            encoding="utf-8",
        )
        (mod_pkg / "agents" / "stack" / "python" / "typing.md").write_text(
            "# Description: Python typing\n- Postponed annotations rule.\n",
            encoding="utf-8",
        )
        (mod_pkg / "agents" / "default.bundle").write_text(
            "# Description: Default modern bundle\n"
            "rule core/axiom\n",
            encoding="utf-8",
        )
        (mod_pkg / "custom" / "sub" / "extra.md").write_text(
            "# Description: Custom relative rule\n- Explicit package-relative rule body.\n",
            encoding="utf-8",
        )
        (mod_pkg / "custom" / "sub" / "extra.bundle").write_text(
            "# Description: Custom relative bundle\n"
            "rule ./extra.md\n",
            encoding="utf-8",
        )

        # 1. --list discovers rules and bundles under agents/ and ignores AGENTS.md / README.md
        r_list = self._run(
            [str(SCRIPT), "--list", "vitalio/modern_pkg"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_list)
        self.assertIn("vitalio/modern_pkg:core/axiom", r_list.stdout)
        self.assertIn("vitalio/modern_pkg:coding/coding", r_list.stdout)
        self.assertIn("vitalio/modern_pkg:default", r_list.stdout)
        self.assertNotIn(":agents", r_list.stdout)
        self.assertNotIn(":readme", r_list.stdout)

        # 2. owner/repo resolves agents/default.bundle when agents/<repo>.bundle is absent
        r_def = self._run(
            [str(SCRIPT), "--bundle", "vitalio/modern_pkg", "--plain"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_def)
        self.assertIn("Canonical agents/ core axiom body.", r_def.stdout)

        # 3. owner/repo prefers agents/<repo>.bundle over agents/default.bundle when present
        (mod_pkg / "agents" / "modern_pkg.bundle").write_text(
            "# Description: Repo-named bundle\n"
            "rule core/axiom\n"
            "rule stack/python/typing\n",
            encoding="utf-8",
        )
        r_repo = self._run(
            [str(SCRIPT), "--bundle", "vitalio/modern_pkg", "--plain"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_repo)
        self.assertIn("Canonical agents/ core axiom body.", r_repo.stdout)
        self.assertIn("Postponed annotations rule.", r_repo.stdout)

        # 4. owner/repo:domain -> agents/domain/domain.bundle and nested stack/python -> agents/stack/python/python.bundle
        r_dom = self._run(
            [str(SCRIPT), "--bundle", "vitalio/modern_pkg:coding", "--plain"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_dom)
        self.assertIn("Coding architecture rule body.", r_dom.stdout)
        self.assertIn("Relative rule inside coding domain.", r_dom.stdout)

        r_nested = self._run(
            [str(SCRIPT), "--bundle", "vitalio/modern_pkg:stack/python", "--plain"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_nested)
        self.assertIn("Postponed annotations rule.", r_nested.stdout)

        # 5. Explicit relative file paths inside a package (owner/repo:path/to/file)
        r_rel_rule = self._run(
            [str(SCRIPT), "--rule", "vitalio/modern_pkg:custom/sub/extra.md"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_rel_rule)
        self.assertIn("Explicit package-relative rule body.", r_rel_rule.stdout)

        r_rel_bundle = self._run(
            [str(SCRIPT), "--bundle", "vitalio/modern_pkg:custom/sub/extra.bundle", "--plain"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_rel_bundle)
        self.assertIn("Explicit package-relative rule body.", r_rel_bundle.stdout)

        # Path traversal escaping package root fails fast
        r_escape = self._run(
            [str(SCRIPT), "--rule", "vitalio/modern_pkg:../../outside.md"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_escape.returncode, 0)
        self.assertIn("escapes package root", r_escape.stderr)

    def test_explicit_ref_fetches_remote_ref_instead_of_unpinned_local_override(self):
        pkg_root = Path(os.environ["CONTEXT_BUNDLE_LOCAL_PKG_DIR"])
        local_unpinned = pkg_root / "vitalio" / "ref_pkg" / "agents"
        local_unpinned.mkdir(parents=True)
        (local_unpinned / "info.md").write_text(
            "# Description: Local unpinned\n- UNPINNED_LOCAL_WORKING_TREE\n",
            encoding="utf-8",
        )
        (local_unpinned / "ref_pkg.bundle").write_text(
            "rule info\n",
            encoding="utf-8",
        )

        # Create an offline git origin for vitalio/ref_pkg.git with tag v1.0 and a later main commit
        remotes_dir = self.tmp / "remotes" / "vitalio"
        remote_repo = remotes_dir / "ref_pkg.git"
        (remote_repo / "agents").mkdir(parents=True)
        self._git(remote_repo, "init", "-q")
        self._git(remote_repo, "symbolic-ref", "HEAD", "refs/heads/main")
        (remote_repo / "agents" / "info.md").write_text(
            "# Description: Pinned v1.0\n- PINNED_TAG_V1_0_BODY\n",
            encoding="utf-8",
        )
        (remote_repo / "agents" / "ref_pkg.bundle").write_text(
            "rule info\n",
            encoding="utf-8",
        )
        (remote_repo / "custom" ).mkdir()
        (remote_repo / "custom" / "pinned.md").write_text(
            "# Description: Custom pinned\n- CUSTOM_PINNED_REL_PATH\n",
            encoding="utf-8",
        )
        self._git(remote_repo, "add", ".")
        self._git(remote_repo, "commit", "-q", "-m", "release v1.0")
        self._git(remote_repo, "tag", "v1.0")

        (remote_repo / "agents" / "info.md").write_text(
            "# Description: Main head\n- REMOTE_MAIN_HEAD_BODY\n",
            encoding="utf-8",
        )
        self._git(remote_repo, "add", ".")
        self._git(remote_repo, "commit", "-q", "-m", "advance main")

        env = {
            **os.environ,
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"url.{remotes_dir.parent.as_uri()}/.insteadOf",
            "GIT_CONFIG_VALUE_0": "https://github.com/",
        }

        # Unpinned vitalio/ref_pkg uses CONTEXT_BUNDLE_LOCAL_PKG_DIR
        r_unpinned = self._run(
            [str(SCRIPT), "--rule", "vitalio/ref_pkg:info"],
            cwd=str(self.tmp),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_unpinned)
        self.assertIn("UNPINNED_LOCAL_WORKING_TREE", r_unpinned.stdout)

        # Explicit @v1.0 fetches the requested ref into cache instead of returning unpinned local tree
        r_pinned = self._run(
            [str(SCRIPT), "--rule", "vitalio/ref_pkg@v1.0:info"],
            cwd=str(self.tmp),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_pinned)
        self.assertIn("PINNED_TAG_V1_0_BODY", r_pinned.stdout)
        self.assertNotIn("UNPINNED_LOCAL_WORKING_TREE", r_pinned.stdout)
        self.assertTrue((self.tmp / "cache" / "packages" / "vitalio" / "ref_pkg@v1.0").is_dir())

        # Explicit @v1.0 with explicit relative file path inside package
        r_pinned_rel = self._run(
            [str(SCRIPT), "--rule", "vitalio/ref_pkg@v1.0:custom/pinned.md"],
            cwd=str(self.tmp),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_pinned_rel)
        self.assertIn("CUSTOM_PINNED_REL_PATH", r_pinned_rel.stdout)

        # Explicit @v1.0 on bundle shorthand vitalio/ref_pkg@v1.0
        r_pinned_bundle = self._run(
            [str(SCRIPT), "--bundle", "vitalio/ref_pkg@v1.0", "--plain"],
            cwd=str(self.tmp),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_pinned_bundle)
        self.assertIn("PINNED_TAG_V1_0_BODY", r_pinned_bundle.stdout)

        # Explicit @v1.0 on rule shorthand vitalio/ref_pkg@v1.0 (sole rule fallback)
        r_pinned_rule_shorthand = self._run(
            [str(SCRIPT), "--rule", "vitalio/ref_pkg@v1.0"],
            cwd=str(self.tmp),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r_pinned_rule_shorthand)
        self.assertIn("PINNED_TAG_V1_0_BODY", r_pinned_rule_shorthand.stdout)

    def test_package_rule_shorthand_resolution_order_and_ambiguity_rejection(self):
        pkg_root = Path(os.environ["CONTEXT_BUNDLE_LOCAL_PKG_DIR"])

        # 1. Sole rule in agents/*.md (e.g. vitalio/todo-md -> agents/todo.md -> vitalio/todo-md:todo)
        todo_pkg = pkg_root / "vitalio" / "todo-md" / "agents"
        todo_pkg.mkdir(parents=True)
        (todo_pkg / "todo.md").write_text(
            "# Description: Todo rule\n- SOLE_RULE_TODO_MD_BODY\n",
            encoding="utf-8",
        )
        mod = self._load_bundle_module()
        items_sole = mod.collect_directive_items("rule", "vitalio/todo-md", work_dir=self.tmp)
        self.assertEqual(len(items_sole), 1)
        self.assertEqual(items_sole[0][0], "vitalio/todo-md:todo")
        self.assertIn("SOLE_RULE_TODO_MD_BODY", items_sole[0][2])

        # 2. agents/default.md preferred when multiple rules exist and <repo>.md is absent
        (todo_pkg / "extra.md").write_text(
            "# Description: Extra rule\n- EXTRA_RULE_BODY\n",
            encoding="utf-8",
        )
        r_ambig = self._run(
            [str(SCRIPT), "--rule", "vitalio/todo-md"],
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(r_ambig.returncode, 0)
        self.assertIn("unknown rule", r_ambig.stderr)

        (todo_pkg / "default.md").write_text(
            "# Description: Default rule\n- DEFAULT_RULE_TODO_MD_BODY\n",
            encoding="utf-8",
        )
        items_def = mod.collect_directive_items("rule", "vitalio/todo-md", work_dir=self.tmp)
        self.assertEqual(items_def[0][0], "vitalio/todo-md:default")
        self.assertIn("DEFAULT_RULE_TODO_MD_BODY", items_def[0][2])

        # 3. agents/<repo>.md (with '-' / '_' normalization) preferred over agents/default.md
        (todo_pkg / "todo-md.md").write_text(
            "# Description: Repo-named rule\n- REPO_NAMED_TODO_MD_BODY\n",
            encoding="utf-8",
        )
        items_repo = mod.collect_directive_items("rule", "vitalio/todo-md", work_dir=self.tmp)
        self.assertEqual(items_repo[0][0], "vitalio/todo-md:todo-md")
        self.assertIn("REPO_NAMED_TODO_MD_BODY", items_repo[0][2])

    def test_root_targets_require_explicit_package_or_local_agents_and_no_intra_pkg_shorthand_fallback(self):
        from unittest import mock

        repo = self.tmp / "no_default_pkg_repo"
        repo.mkdir()

        with self.subTest(case="unprefixed root rule or bundle without local agents/ fails fast"):
            for cmd_args, target in (
                (["--rule", "core"], "core"),
                (["--bundle", "core"], "core"),
            ):
                r_unpref = self._run([str(SCRIPT), *cmd_args], cwd=str(repo))
                self.assertNotEqual(r_unpref.returncode, 0)
                self.assertIn(f"missing package prefix in {target!r}", r_unpref.stderr)

        with self.subTest(case="unprefixed root rule or bundle resolves from current repository local agents/"):
            (repo / "agents").mkdir()
            (repo / "agents" / "my_rule.md").write_text(
                "# Description: Local rule\n- LOCAL_AGENTS_RULE_BODY\n",
                encoding="utf-8",
            )
            (repo / "agents" / "my_bundle.bundle").write_text(
                "# Description: Local bundle\nrule my_rule\n",
                encoding="utf-8",
            )
            r_local_rule = self._run([str(SCRIPT), "--rule", "my_rule"], cwd=str(repo))
            self._assert_ok(r_local_rule)
            self.assertIn("LOCAL_AGENTS_RULE_BODY", r_local_rule.stdout)

            r_local_bundle = self._run([str(SCRIPT), "--bundle", "my_bundle", "--plain"], cwd=str(repo))
            self._assert_ok(r_local_bundle)
            self.assertIn("LOCAL_AGENTS_RULE_BODY", r_local_bundle.stdout)

        with self.subTest(case="nested bundle resolves sibling-owner repo shorthand but fails fast on intra-package typos"):
            mod = self._load_bundle_module()
            pkg_root = Path(os.environ["CONTEXT_BUNDLE_LOCAL_PKG_DIR"])
            todo_pkg = pkg_root / "vitalio" / "todo-md" / "agents"
            todo_pkg.mkdir(parents=True, exist_ok=True)
            (todo_pkg / "todo.md").write_text(
                "# Description: Todo rule\n- NESTED_REPO_SHORTHAND_TODO_BODY\n",
                encoding="utf-8",
            )
            adapters_dir = pkg_root / "agents" / "adapters"
            adapters_dir.mkdir(parents=True, exist_ok=True)
            (adapters_dir / "todo-md.bundle").write_text(
                "# Description: Todo-md adapter\n"
                "rule vitalio/todo-md\n"
                "if role!=\n"
                "    rule role/{role:}\n",
                encoding="utf-8",
            )

            # 1. rule vitalio/todo-md inside vitalio/agents-rules:adapters/todo-md resolves to vitalio/todo-md:todo
            items_ok = mod.collect_directive_items(
                "bundle",
                "vitalio/agents-rules:adapters/todo-md",
                work_dir=repo,
            )
            self.assertEqual([it[0] for it in items_ok], ["vitalio/todo-md:todo"])
            self.assertIn("NESTED_REPO_SHORTHAND_TODO_BODY", items_ok[0][2])

            r_adapter_ok = self._run(
                [str(SCRIPT), "--bundle", "vitalio/agents-rules:adapters/todo-md", "--plain"],
                cwd=str(repo),
            )
            self._assert_ok(r_adapter_ok)
            self.assertIn("NESTED_REPO_SHORTHAND_TODO_BODY", r_adapter_ok.stdout)

            # 2. Intra-package typos (role/reivew, core/isolatoin) fail in default_pkg without git clone fallback
            (adapters_dir / "typo_core.bundle").write_text(
                "rule core/isolatoin\n",
                encoding="utf-8",
            )
            with mock.patch.object(mod, "_ensure_remote_package", wraps=mod._ensure_remote_package) as spy_remote:
                for b_target, cli_extra, bad_rule in (
                    ("vitalio/agents-rules:adapters/todo-md", ["role=reivew"], "role/reivew"),
                    ("vitalio/agents-rules:default", ["role=reivew"], "role/reivew"),
                    ("vitalio/agents-rules:adapters/typo_core", [], "core/isolatoin"),
                ):
                    r_typo_cli = self._run(
                        [str(SCRIPT), "--bundle", b_target, *cli_extra],
                        cwd=str(repo),
                    )
                    self.assertNotEqual(r_typo_cli.returncode, 0)
                    self.assertIn(f"unknown rule {bad_rule!r} in package 'vitalio/agents-rules'", r_typo_cli.stderr)
                    for call in spy_remote.call_args_list:
                        self.assertNotEqual(call.args[0], bad_rule)

                    with self.assertRaises(SystemExit) as ctx:
                        mod.collect_directive_items(
                            "bundle",
                            b_target,
                            cli_vars={"role": "reivew"} if cli_extra else None,
                            work_dir=repo,
                        )
                    self.assertIn(f"unknown rule {bad_rule!r} in package 'vitalio/agents-rules'", str(ctx.exception))
                    for call in spy_remote.call_args_list:
                        self.assertNotEqual(call.args[0], bad_rule)

        with self.subTest(case="_ensure_remote_package disables interactive git terminal prompts"):
            import subprocess as sp

            mod = self._load_bundle_module()
            fake_cp = sp.CompletedProcess(args=["git"], returncode=128, stdout="", stderr="fatal: repository not found")
            env_no_local = {k: v for k, v in os.environ.items() if k != "CONTEXT_BUNDLE_LOCAL_PKG_DIR"}
            with mock.patch.dict(os.environ, env_no_local, clear=True), mock.patch.object(
                mod.subprocess, "run", return_value=fake_cp
            ) as mock_run:
                with self.assertRaises(SystemExit) as ctx:
                    mod._ensure_remote_package("nonexistent_owner/nonexistent_repo", refresh=True)
                self.assertIn("failed to fetch package", str(ctx.exception))
                self.assertEqual(mock_run.call_count, 1)
                _, kwargs = mock_run.call_args
                self.assertIs(kwargs.get("stdin"), sp.DEVNULL)
                self.assertEqual(kwargs.get("env", {}).get("GIT_TERMINAL_PROMPT"), "0")


if __name__ == "__main__":
    unittest.main()
