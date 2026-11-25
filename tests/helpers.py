#!/usr/bin/env python3
"""Shared test helpers and base test case for context-bundle."""
from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "context"
BUILD_PY = ROOT / "build.py"
INSTALL_SH = ROOT / "install.sh"


class _TtyStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


def _seed_offline_rules_pkg(pkg_dir: Path) -> None:
    files = {
        "agents/core/core.bundle": (
            "# Description: Core axioms\n"
            "rule core/start\n"
            "rule core/ssot\n"
            "rule core/lang lang=English\n"
        ),
        "agents/default.bundle": (
            "# Description: Default project rules\n"
            "bundle core\n"
            "if os=linux\n"
            "    rule os/linux\n"
            "if os=macos\n"
            "    rule os/macos\n"
            "if vcs=git\n"
            "    rule vcs/git\n"
            "if vcs=cvs\n"
            "    rule vcs/cvs\n"
            "if role!=\n"
            "    rule role/{role:}\n"
        ),
        "agents/core/start.md": "# Description: Start priority\n- Start priority, instruction self-audit & dates: Format dates as `{chat_date_fmt:DD/MM/YYYY}`; in files, commits, headers, and logs always use UTC with ISO `YYYY-MM-DD`.\n",
        "agents/core/ssot.md": "# Description: SSOT\n- Single source of truth & DRY: Define every version in one place.\n",
        "agents/core/lang.md": "# Description: Language policy\n- Language policy: Write chat prose in {chat_lang:the language the user writes in}; keep code and docs in {lang:English}.\n",
        "agents/os/linux.md": "# Description: Linux shell rules\n- Linux & POSIX shell rules: Enable `set -euo pipefail` in mutating scripts.\n",
        "agents/os/macos.md": "# Description: macOS rules\n- macOS & BSD userland rules: Account for BSD userland differences.\n",
        "agents/vcs/git.md": "# Description: Git workflow\n- Git workflow & safety: Push to `origin {main_branch:main}`.\n",
        "agents/vcs/cvs.md": "# Description: CVS workflow\n- CVS workflow & safety: Inspect status via `cvs -nq update` and `cvs diff -u`.\n",
        "agents/role/design.md": "# Description: Universal Designer role\n- Role (Designer): Explore problem space and architecture.\n",
        "agents/role/plan.md": "# Description: Universal Planner role\n- Role (Planner): Decompose and prioritize tasks.\n",
        "agents/role/execute.md": "# Description: Universal Executor role\n- Role (Executor): Focus strictly on delivering the target task.\n",
        "agents/role/audit.md": "# Description: Universal Auditor role\n- Role (Auditor): Audit the requested scope.\n",
        "agents/stack/python-cli.md": "# Description: Python CLI rules\n- Python CLI engineering invariants: Python {py_min:3.9}+ compatibility.\n",
        "agents/release/single-file-build.md": "# Description: Single-file build\n- Single-file build from modular `src/`: Edit source modules under `src/`.\n",
        "agents/context.md": "# Description: Bundler rule\n- Context bundler & rules engine (`context`): Use `--tree` and `--list`.\n",
        "agents/context.bundle": "# Description: On-demand context instructions\nrule vitalio/context-bundle:context\nif role!=\n    export role\nif role=design\n    cmd context --list\n",
        "agents/todo_md.md": "# Description: Task tracker rule\n- Task management (`todo_md`): Manage `TODO.md`.\n",
        "agents/todo_md.bundle": "# Description: On-demand todo_md bundle\nrule vitalio/todo_md:todo_md\n",
    }
    for rel, content in files.items():
        p = pkg_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


class AgentsBundleTestCase(unittest.TestCase):
    _bundle_mod: types.ModuleType | None = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        loader = importlib.machinery.SourceFileLoader("agents_bundle_mod", str(SCRIPT))
        spec = importlib.util.spec_from_loader("agents_bundle_mod", loader)
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        cls._bundle_mod = mod

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ab_test_"))
        self._saved_env = {
            k: os.environ.pop(k, None)
            for k in ("CONTEXT_BUNDLE_VARS", "CONTEXT_BUNDLE_PLAIN", "XDG_STATE_HOME", "CONTEXT_BUNDLE_TTY")
        }
        pkg_dir = self.tmp / "offline_rules_pkg"
        _seed_offline_rules_pkg(pkg_dir)
        os.environ["CONTEXT_BUNDLE_CACHE_DIR"] = str(self.tmp / "cache")
        os.environ["CONTEXT_BUNDLE_LOCAL_PKG_DIR"] = str(pkg_dir)
        os.environ["XDG_STATE_HOME"] = str(self.tmp / "state")

    def tearDown(self):
        os.environ.pop("CONTEXT_BUNDLE_CACHE_DIR", None)
        os.environ.pop("CONTEXT_BUNDLE_LOCAL_PKG_DIR", None)
        os.environ.pop("XDG_STATE_HOME", None)
        os.environ.pop("CONTEXT_BUNDLE_TTY", None)
        for k, v in self._saved_env.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _load_bundle_module(self) -> types.ModuleType:
        mod = type(self)._bundle_mod
        assert mod is not None
        if hasattr(mod, "_REFRESHED"):
            mod._REFRESHED.clear()
        return mod

    def _assert_ok(self, proc: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(
            proc.returncode,
            0,
            msg=f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )

    def _run_in_process(
        self,
        cmd: list[str],
        *,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        mod = self._load_bundle_module()
        argv_str = [str(a) for a in cmd]
        old_cwd = os.getcwd()
        old_env = os.environ.copy()
        old_argv = sys.argv[:]
        old_stdin = sys.stdin
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        rc = 0
        try:
            if cwd is not None:
                os.chdir(cwd)
            if env is not None:
                os.environ.clear()
                os.environ.update(env)
            sys.argv = argv_str
            sys.stdin = _TtyStringIO("") if input is None else io.StringIO(input)
            with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
                try:
                    res = mod.main(argv_str[1:])
                    rc = int(res) if isinstance(res, int) else 0
                except SystemExit as exc:
                    if exc.code is None:
                        rc = 0
                    elif isinstance(exc.code, int):
                        rc = exc.code
                    else:
                        err_buf.write(f"{exc.code}\n")
                        rc = 1
        finally:
            sys.stdin = old_stdin
            sys.argv = old_argv
            os.environ.clear()
            os.environ.update(old_env)
            os.chdir(old_cwd)
        return subprocess.CompletedProcess(
            args=argv_str,
            returncode=rc,
            stdout=out_buf.getvalue(),
            stderr=err_buf.getvalue(),
        )

    def _run_subprocess(
        self,
        cmd: list[str],
        *,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        input: str | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(a) for a in cmd],
            cwd=str(cwd) if cwd is not None else None,
            env=env,
            input=input,
            capture_output=capture_output,
            text=text,
            check=check,
        )

    def _run(
        self,
        cmd: list[str],
        *,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        input: str | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        if cmd and Path(cmd[0]).resolve() == SCRIPT.resolve():
            return self._run_in_process(cmd, cwd=cwd, env=env, input=input)
        return self._run_subprocess(
            cmd,
            cwd=cwd,
            env=env,
            input=input,
            capture_output=capture_output,
            text=text,
            check=check,
        )

    def _trust(self, repo_dir: str | Path | None = None) -> None:
        target = Path(repo_dir) if repo_dir is not None else self.tmp
        r = self._run([str(SCRIPT), "--trust", "-C", str(target)])
        self._assert_ok(r)

    def _git(self, repo, *args):
        r = subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
            capture_output=True,
            text=True,
            check=False,
        )
        self._assert_ok(r)
        return r.stdout.strip()

    def _extract_fragments(self, output: str) -> tuple[str, list[tuple[dict[str, object], str]]]:
        m_bound = re.search(r"^Bundle-Boundary: ([0-9a-f]+)$", output, flags=re.MULTILINE)
        self.assertIsNotNone(m_bound, msg=output)
        assert m_bound is not None
        nonce = m_bound.group(1)
        part_prefix = f"<!-- bundle:{nonce}:part "
        end_line = f"<!-- bundle:{nonce}:end -->"

        fragments: list[tuple[dict[str, object], str]] = []
        active_meta: dict[str, object] | None = None
        buf: list[str] = []
        for line in output.splitlines():
            if line.startswith(part_prefix) and line.endswith(" -->"):
                self.assertIsNone(active_meta, msg=f"nested part marker before end: {line}")
                raw_json = line[len(part_prefix) : -len(" -->")]
                parsed = json.loads(raw_json)
                self.assertIsInstance(parsed, dict)
                active_meta = parsed
                buf = []
            elif line == end_line:
                self.assertIsNotNone(active_meta, msg="orphan end marker")
                assert active_meta is not None
                fragments.append((active_meta, "\n".join(buf)))
                active_meta = None
                buf = []
            elif active_meta is not None:
                buf.append(line)
        self.assertIsNone(active_meta, msg="unclosed part marker at EOF")
        return nonce, fragments
