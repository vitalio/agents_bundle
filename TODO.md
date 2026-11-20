# 🎯 [NEXT] F28: Speed up test suite (in-process runner, lazy urllib) and split monolithic test_agents_bundle.py into modular tests/test_*.py

- Role: work
- Move `import urllib.request` out of top-level `src/header.py` into `fetch_remote_script()` in `src/cli.py` (and `src/rules_engine.py` URL fetching where needed) so local CLI startups do not pay the `urllib.request` import cost (~40 ms).
- Create `tests/helpers.py` containing `_seed_offline_rules_pkg()` and a shared base class `AgentsBundleTestCase(unittest.TestCase)` that loads `./agents_bundle` once in `setUpClass()` and provides `_assert_ok()`, `_run_in_process()`, `_run_subprocess()`, `_run()`, `_git()`, `_load_bundle_module()`, and `_extract_fragments()` helpers (isolating `cwd`, `env`, `sys.argv`, and `sys.stdin` with `contextlib.redirect_stdout` / `redirect_stderr` and full `stdout`/`stderr` diagnostic `msg=` on `returncode` assertions).
- Convert routine `subprocess.run([str(SCRIPT), ...])` calls to `self._run([str(SCRIPT), ...])` (keeping real subprocess smoke checks for `-h`/`--version`, `install.sh`, and `build.py --check`, and using `sys.executable` instead of `"python3"` literals).
- Split the 22 test methods in `tests/test_agents_bundle.py` programmatically via `ast.parse()` (`node.lineno`..`node.end_lineno`) without re-emitting test bodies in chat into modular test files mirroring `src/`:
  - `tests/test_cli.py` (`build.py --check`, `--help`, `--version`, missing spec hint, `install.sh`)
  - `tests/test_tree.py` (`--tree` exclusions, truncation, and `AGENTS.md` pinning)
  - `tests/test_rules_engine.py` (`ruleset`, `rule`, `--list`, circular reference detection, `--update-cache`, `--refresh`, and no implicit home package fallback)
  - `tests/test_bundle.py` (`.agents_bundle` directives, `var`, `include`, `[if]`, `$ <cmd>`, piped `stdin` / `Workdir:`, `Bundle-Boundary` nonce, `Bundle-Expose`, JSON fragment markers, provenance/telemetry, and `--plain`)
- Remove monolithic `tests/test_agents_bundle.py`, document the modular `tests/` layout in `AGENTS.md`, rebuild `./agents_bundle` via `build.py`, verify `python3 build.py --check`, ensure `python3 -m unittest discover -s tests` runs all 22 tests in `<1.5s`, and bump `VERSION` for a PATCH release.

# 🎯 [NEXT] B1: Fail fast when piped stdin is an empty FIFO instead of falling back to unpiped bundle assembly

- Role: work
- In `cmd_bundle()` (`src/bundle.py`), detect when `sys.stdin` is an actual pipe/FIFO (`stat.S_ISFIFO(os.fstat(sys.stdin.fileno()).st_mode)`) and `piped_raw.strip()` is empty (for example when an upstream command in `todo_md <ID> | agents_bundle role=work | run_block` fails and exits without writing to `stdout`).
- When an actual pipe/FIFO delivers empty input, write a clear error message to `sys.stderr` (e.g. `agents_bundle: empty piped input on stdin (upstream command failed?)`) and return non-zero (`2`) immediately before evaluating `.agents_bundle` or `.bundle` `$ <cmd>` directives (while still allowing non-FIFO non-TTY stdin such as `/dev/null` in background/test runners).
- Cover empty-pipe failure vs `/dev/null` non-TTY behavior with unit tests in `tests/test_agents_bundle.py`, rebuild `./agents_bundle` via `build.py`, and bump `VERSION` for a PATCH release.

# 🎯 [NEXT] F6: Add bundle CLI subcommand to render and inspect .bundle files

- Role: plan
- Add 'agents_bundle bundle <pkg>[:<name>] [k=v]' CLI subcommand (symmetric with 'ruleset' and 'rule') to render a bundle from the command line.
- Keep src/header.py (--help), src/rules/agents_bundle.md, README.md, and tests in sync.

# ⚪ [NEW] F7: Support agents/ package directory, custom relative paths, and @ref local-resolve fix

- Standardize `agents/` as the canonical package directory for rules (`.md`) and bundles (`.bundle`) across repositories (supporting logical domain subdirectories, `owner/repo` -> `agents/<repo>.bundle` or `agents/default.bundle`, and `owner/repo:domain` -> `agents/domain/domain.bundle`) while keeping fallback compatibility with legacy root `rules/`, `rulesets/`, `bundles/` and `src/` paths.
- Support explicit relative file paths inside a package (`owner/repo[@ref]:path/to/file`) and local relative paths (`./...`, `../...`).
- Fix `_ensure_remote_package` so explicit `@<ref>` on `vitalio/*` packages fetches the requested ref instead of returning the unpinned local working tree.
- Move `src/rules/agents_bundle.md` and `src/bundles/agents_bundle.bundle` into `agents/` and keep `AGENTS.md`, `README.md`, `src/header.py`, and unit tests in sync.

# ⚪ [NEW] F10: Enforce command allowlist policy in .agents_bundle for external bundles

- Role: plan
- Support an explicit allowlist directive in root .agents_bundle (e.g. 'allow <cmd1> <cmd2> ...' or per-bundle 'bundle <pkg> allow=...') defining which executables external bundles are permitted to run via '$' commands and 'var x=$(...)' subshells.
- Statically inspect all parsed commands from included bundles before executing any shell command; fail fast with a clear error naming the blocked command and originating bundle if any command executable is not in the user's allowlist.
- Restrict 'include' paths from external bundles to files inside the repository root (spec_dir) so external bundles cannot read arbitrary host paths outside the workspace.
- Update src/bundle.py, src/header.py (--help), src/rules/agents_bundle.md, README.md, and unit tests in tests/test_agents_bundle.py.

# ⚪ [NEW] F13: Make src/ modules standalone importable and extract core helpers from src/tree.py

- Move `prog_name()`, `cache_dir_path()`, and `usage_text()` out of `src/tree.py` into `src/header.py` (or a dedicated `src/core.py` in `MODULE_ORDER`) so `src/tree.py` handles only repository tree generation.
- Make each module under `src/` valid, standalone-importable Python for IDE/linter analysis while updating `build.py` to strip internal cross-module imports when assembling the single-file `agents_bundle` executable.
- Keep `AGENTS.md`, `build.py`, and unit tests in `tests/test_agents_bundle.py` in sync.

# ⚪ [NEW] F15: Unify ruleset into bundle and support logical package directory layout

- Depends on: F6, F7, F10
- Merge `ruleset` into `bundle` across `src/rules_engine.py`, `src/bundle.py`, `src/cli.py`, and `src/header.py` so `bundle` serves as the single composition primitive alongside atomic `rule` files (`.md`), coordinating with `F6`, `F7`, and `F10`.
- Support logical domain-based layouts inside `agents/` (resolving `.md` rules and `.bundle` presets by relative path without requiring top-level `rules/` vs `rulesets/` splits), defining deprecation or migration behavior for existing `ruleset` references and legacy directories.
- Keep `README.md`, `agents/agents_bundle.md`, and `tests/test_agents_bundle.py` in sync.

# ⚪ [NEW] F27: Rename project to ctx-bundle and CLI utility to cxb

- Role: plan
- Rename project/repository references from `agents_bundle` to `ctx-bundle` and CLI entrypoint from `agents_bundle` to `cxb` (applying agreed deprecation aliases/symlinks and config/env-var updates from the ecosystem rename design).
- Target files: `build.py`, `install.sh`, `install.ps1`, `src/cli.py`, `src/header.py`, `src/bundle.py`, `src/rules_engine.py`, `src/tree.py`, `src/rules/agents_bundle.md`, `src/bundles/`, `.agents_bundle`, `AGENTS.md`, `README.md`, `VERSION`, `tests/test_agents_bundle.py`, and `.github/`.
- Acceptance criteria: `build.py` outputs `cxb`, `install.sh`/`install.ps1` install `cxb` (plus any agreed compatibility alias), `--help`/rules/docs/tests reflect `ctx-bundle` and `cxb`, and `tests/test_agents_bundle.py` passes.
