# 🎯 [NEXT] F12: Detect and fail fast on circular ruleset and bundle references

- Track active resolution chains across recursive `ruleset` expansion in `src/rules_engine.py` and recursive `bundle` expansion in `src/bundle.py`.
- Fail fast with a clear `SystemExit` diagnostic showing the cycle path instead of hitting `RecursionError`.
- Add unit tests covering self-referential and multi-step cycles in `tests/test_agents_bundle.py`.

# 🎯 [NEXT] F6: Add bundle CLI subcommand to render and inspect .bundle files

- Add 'agents_bundle bundle <pkg>[:<name>] [k=v]' CLI subcommand (symmetric with 'ruleset' and 'rule') to render a bundle from the command line.
- Keep src/header.py (--help), src/rules/agents_bundle.md, README.md, and tests in sync.

# ⚪ [NEW] F7: Support agents/ package directory, custom relative paths, and @ref local-resolve fix

- Standardize `agents/` as the canonical package directory for rules (`.md`) and bundles (`.bundle`) across repositories (supporting logical domain subdirectories, `owner/repo` -> `agents/<repo>.bundle` or `agents/default.bundle`, and `owner/repo:domain` -> `agents/domain/domain.bundle`) while keeping fallback compatibility with legacy root `rules/`, `rulesets/`, `bundles/` and `src/` paths.
- Support explicit relative file paths inside a package (`owner/repo[@ref]:path/to/file`) and local relative paths (`./...`, `../...`).
- Fix `_ensure_remote_package` so explicit `@<ref>` on `vitalio/*` packages fetches the requested ref instead of returning the unpinned local working tree.
- Move `src/rules/agents_bundle.md` and `src/bundles/agents_bundle.bundle` into `agents/` and keep `AGENTS.md`, `README.md`, `src/header.py`, and unit tests in sync.

# ⚪ [NEW] F10: Enforce command allowlist policy in .agents_bundle for external bundles

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

# ⚪ [NEW] F16: Update role=execute and role=audit examples to role=work and role=review

- Replace `role=execute` and `role=audit` usage examples in `README.md` (and any bundled rule/help text if present) with `role=work` and `role=review` once the roles are renamed in `agents-rules` (coordinated in `todo_flow`).
