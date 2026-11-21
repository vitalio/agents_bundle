# 🎯 [NEXT] F7: Support agents/ package directory, custom relative paths, and @ref local-resolve fix

- Depends on: F13, F30
- Standardize `agents/` as the canonical package directory for rules (`.md`) and bundles (`.bundle`) across repositories (supporting logical domain subdirectories, `owner/repo` -> `agents/<repo>.bundle` or `agents/default.bundle`, and `owner/repo:domain` -> `agents/domain/domain.bundle`) while keeping fallback compatibility with legacy root `rules/`, `rulesets/`, `bundles/` and `src/` paths in `_load_package_from_dir()` and `resolve_bundle_source()` in `src/rules_engine.py:175-415`.
- Support explicit relative file paths inside a package (`owner/repo[@ref]:path/to/file`) and local relative paths (`./...`, `../...`).
- Fix `_ensure_remote_package()` in `src/rules_engine.py:242-295` so explicit `@<ref>` on `vitalio/*` packages fetches the requested ref instead of returning the unpinned local working tree.
- Keep `agents/agents_bundle.md`, `AGENTS.md`, `README.md`, `src/header.py`, and unit tests in `tests/test_rules_engine.py:1-323` and `tests/test_bundle.py:1-260` in sync.
- Target files: `src/header.py`, `src/rules_engine.py:175-415`, `src/bundle.py:167-268`, `AGENTS.md`, `README.md`, `tests/test_rules_engine.py:1-323`, `tests/test_bundle.py:1-260`.

# 🎯 [NEXT] F10: Enforce command allowlist policy in .agents_bundle for external bundles

- Depends on: F13, F7
- Support an explicit allowlist directive in root `.agents_bundle` (e.g. `allow <cmd1> <cmd2> ...` or per-bundle `bundle <pkg> allow=...`) defining which executables external bundles are permitted to run via `$` commands and `var x=$(...)` subshells in `parse_spec()` and `build_bundle()` (`src/bundle.py:167-566`).
- Statically inspect all parsed commands from included bundles before executing any shell command; fail fast with a clear error naming the blocked command and originating bundle if any command executable is not in the user's allowlist.
- Restrict `include` paths from external bundles in `_expand_include()` (`src/bundle.py:313-360`) to files inside the repository root (`spec_dir`) so external bundles cannot read arbitrary host paths outside the workspace.
- Target files: `src/header.py`, `src/bundle.py:167-566`, `src/rules_engine.py:412-566`, `AGENTS.md`, `README.md`, `tests/test_bundle.py:720-1070`.

# ⚪ [NEW] F27: Rename project to ctx-bundle and CLI utility to cxb

- Rename project/repository references from `agents_bundle` to `ctx-bundle` and CLI entrypoint from `agents_bundle` to `cxb` (applying agreed deprecation aliases/symlinks and config/env-var updates from the ecosystem rename design).
- Target files: `build.py`, `install.sh`, `install.ps1`, `src/cli.py`, `src/header.py`, `src/bundle.py`, `src/rules_engine.py`, `src/tree.py`, `src/rules/agents_bundle.md`, `src/bundles/`, `.agents_bundle`, `AGENTS.md`, `README.md`, `VERSION`, `tests/helpers.py`, `tests/test_*.py`, and `.github/`.
- Acceptance criteria: `build.py` outputs `cxb`, `install.sh`/`install.ps1` install `cxb` (plus any agreed compatibility alias), `--help`/rules/docs/tests reflect `ctx-bundle` and `cxb`, and `python3 -m unittest discover -s tests` passes.

# ⚪ [NEW] F15: Unify ruleset into bundle and support logical package directory layout

- Depends on: F6, F7, F10
- Merge `ruleset` into `bundle` across `src/rules_engine.py`, `src/bundle.py`, `src/cli.py`, and `src/header.py` so `bundle` serves as the single composition primitive alongside atomic `rule` files (`.md`), coordinating with `F6`, `F7`, and `F10`.
- Support logical domain-based layouts inside `agents/` (resolving `.md` rules and `.bundle` presets by relative path without requiring top-level `rules/` vs `rulesets/` splits), defining deprecation or migration behavior for existing `ruleset` references and legacy directories.
- Keep `README.md`, `agents/agents_bundle.md`, and `tests/test_rules_engine.py` and `tests/test_bundle.py` in sync.

# ⚪ [NEW] F31: Active backlog task references removed src/rules/agents_bundle.md and src/bundles/

Observed: the Target files bullet of the open task that depends on F6, F7, and F10 still lists `src/rules/agents_bundle.md` and `src/bundles/`, which no longer exist after the embedded rule moved to `agents/agents_bundle.md`. Impact: `todo_md files` preloads missing paths for that task and the reference misleads the next worker.
