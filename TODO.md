# 🎯 [NEXT] F23: Add --plain flag (AGENTS_BUNDLE_PLAIN) and document Bundle Output Protocol

- Depends on: F22
- Support `--plain` in `src/cli.py` / `src/bundle.py` and `AGENTS_BUNDLE_PLAIN=1` in the environment to omit transport `Bundle-*` headers (`Bundle-Boundary`, `Bundle-Expose`) and JSON fragment markers when plain Markdown/text output is requested.
- Update `--help` in `src/header.py`, `src/rules/agents_bundle.md`, `README.md`, and `AGENTS.md` to document the Bundle Output Protocol (`Bundle-Boundary`, `Bundle-Expose`, `expose`, fragment markers, and `--plain`).
- Add unit tests in `tests/test_agents_bundle.py` covering `--plain` and `AGENTS_BUNDLE_PLAIN=1`.

# 🎯 [NEXT] F22: Wrap emitted rules, commands, includes, and prompts in JSON fragment markers

- Depends on: F21
- Wrap each emitted rule, command section, included file section, and prompt block in `<!-- bundle:<nonce>:part {...} -->` and `<!-- bundle:<nonce>:end -->` single-line JSON markers in `src/bundle.py` and `src/rules_engine.py` using neutral fields (`kind`, `id`/`name`, `group`, `via`, `rc`, `ms`).
- Ensure markers serialize cleanly without breaking rule deduplication or multi-line outputs.
- Add unit tests in `tests/test_agents_bundle.py` covering all four fragment kinds (`rule`, `cmd`, `include`, `prompt`) and marker field schemas.

# 🎯 [NEXT] F21: Track bundle source (via/group) and command telemetry (rc, ms)

- Depends on: F19
- Propagate top-level source metadata (`group` / `via`, identifying the originating `bundle` or root `.agents_bundle`) through `parse_spec` in `src/bundle.py` and `collect_directive_items` in `src/rules_engine.py`.
- Record command exit code (`rc`) and elapsed execution duration in integer milliseconds (`ms`) when running `$ <cmd>` entries in `_run_spec_command` and `build_bundle` (`src/bundle.py`).
- Add unit tests in `tests/test_agents_bundle.py` verifying source provenance across nested bundles/rulesets and accurate `rc`/`ms` capture.

# 🎯 [NEXT] F19: Emit Bundle-Boundary nonce and Bundle-Expose header control

- Add `json` and `secrets` standard library imports to `src/header.py`.
- Generate a per-run hex nonce in `build_bundle` (`src/bundle.py`) and emit `Bundle-Boundary: <nonce>` and `Bundle-Expose: Role, Task` by default.
- Support an `expose <key...>` directive in `.agents_bundle` / `.bundle` and `AGENTS_BUNDLE_EXPOSE` in the environment (normalizing keys to Title-Case header names) so projects can expose additional session headers while keeping unexposed template variables out of exposed session headers.
- Add unit tests in `tests/test_agents_bundle.py` covering default header exposure, `expose` directives, `AGENTS_BUNDLE_EXPOSE`, and per-run nonce uniqueness.

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

- Merge `ruleset` into `bundle` across `src/rules_engine.py`, `src/bundle.py`, `src/cli.py`, and `src/header.py` so `bundle` serves as the single composition primitive alongside atomic `rule` files (`.md`), coordinating with `F6`, `F7`, and `F10`.
- Support logical domain-based layouts inside `agents/` (resolving `.md` rules and `.bundle` presets by relative path without requiring top-level `rules/` vs `rulesets/` splits), defining deprecation or migration behavior for existing `ruleset` references and legacy directories.
- Keep `README.md`, `agents/agents_bundle.md`, and `tests/test_agents_bundle.py` in sync.

# ⚪ [NEW] F16: Update role=execute and role=audit examples to role=work and role=review

- Depends on: agents-rules:F9, agents-rules:F16
- Replace `role=execute` and `role=audit` usage examples in `README.md` (and any bundled rule/help text if present) with `role=work` and `role=review` once the roles are renamed in `agents-rules`.
