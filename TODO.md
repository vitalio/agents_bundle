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

# 🎯 [NEXT] F15: Unify ruleset into .bundle, implement Bundle-Name producer namespaces, Python-indented if/let/export/file/cmd language, and drop Windows support

- Depends on: F6, F7, F10
- Implement the unified `.bundle` language, producer namespacing, and POSIX-only cleanup per `todo_flow` `docs/adr/0003-task-targeted-bundle-architecture-and-atomic-rule-taxonomy.md`:
  - Unify `ruleset` into `bundle` across `src/rules_engine.py`, `src/bundle.py`, `src/cli.py`, and `src/header.py` as the single additive composition primitive (removing `-exclude` support while keeping `ruleset` and `*.ruleset` as legacy aliases during migration).
  - Support `.ctx.bundle` as the canonical root spec filename in `find_spec_file()` and `--init` with seamless fallback to `.agents_bundle`.
  - Emit `Bundle-Name: agents_bundle` in non-plain output headers. When unpacking an upstream `context-bundle-protocol` stream in `src/upstream.py`, read `Bundle-Name: <producer>` (rejecting duplicate producer names in the same pipeline) and automatically namespace all non-transport preamble headers (except `Workdir`) as `<producer>.<key_lower>` (e.g. `todo_md.task`, `todo_md.prefix`, `todo_md.status`, `todo_md.title`, `todo_md.files`, `todo_md.role`). Support dot-separated variable names (`[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*`) in `if`, `let`, `export`, and `{name:default}`.
  - Implement the 9-keyword `.bundle` vocabulary with top-down declaration-order assembly (`file` and `cmd` emitted in exact declaration order rather than grouping all `cmd` before all `file`):
    - `bundle <target> [k=v ...]`
    - `rule <target...> [k=v ...]`
    - `file <path|glob|slice...>` (legacy alias `include`; space-separated items; empty `file` after variable expansion is a no-op)
    - `cmd <shell_cmd>` (legacy alias `$`)
    - `prompt <text>`
    - `let <k>=<v>` / `let <k>=$(<cmd>)` (legacy alias `var`; lexically scoped to the current bundle and its children, never leaking upward to parent/sibling bundles or output preamble headers)
    - `export <k...>` (legacy alias `expose`; promotes variables to session scope and emits them as `Key: Value` output preamble headers when non-empty, removing unexported variables and `Bundle-Expose`/`Bundle-Hide` from the output preamble)
    - `if <cond>`, `else if <cond>` (synonym `elif <cond>`), `else` with mandatory 4-space Python-style indentation blocks without colons or `endif` (retaining legacy `[if ...]` / `[/if]` compatibility)
    - `allow <bin...>` (`F10`)
  - Drop Windows support: remove `install.ps1`, `os.name == 'nt'` / PowerShell branches in `src/rules_engine.py` and `src/bundle.py`, and `windows-latest` from `.github/workflows/ci.yml`.
- Target files: `src/header.py`, `src/rules_engine.py`, `src/upstream.py`, `src/bundle.py`, `src/cli.py`, `agents/agents_bundle.md`, `AGENTS.md`, `README.md`, `tests/test_rules_engine.py`, `tests/test_upstream.py`, `tests/test_bundle.py`.

# ⚪ [NEW] F27: Rename project to ctx-bundle and CLI utility to ctx

- Depends on: F15
- Rename project/repository references from `agents_bundle` to `ctx-bundle` and CLI entrypoint from `agents_bundle` to `ctx` (with `.ctx.bundle` as root bundle config and agreed deprecation aliases/symlinks and env-var updates from `todo_flow:D8` and ADR 0003).
- Acceptance criteria: `build.py` outputs `ctx`, `install.sh` installs `ctx` (plus any agreed compatibility alias), `--help`/rules/docs/tests reflect `ctx-bundle` and `ctx`, and `python3 -m unittest discover -s tests` passes.
- Target files: `build.py`, `install.sh`, `install.ps1`, `src/cli.py`, `src/header.py`, `src/bundle.py`, `src/rules_engine.py`, `src/tree.py`, `agents/agents_bundle.md`, `.agents_bundle`, `AGENTS.md`, `README.md`, `VERSION`, `tests/helpers.py`, `tests/test_*.py`, and `.github/`.
