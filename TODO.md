# 🎯 [NEXT] F15: Unify ruleset into .bundle, implement Bundle-Name producer namespaces, Python-indented if/let/export/file/cmd language, and drop Windows support

- Depends on: F6, F7, F10
- Implement the unified `.bundle` language, producer namespacing, canonical 4-kind fragment model, and POSIX-only cleanup per `todo_flow` `docs/adr/0003-task-targeted-bundle-architecture-and-atomic-rule-taxonomy.md`:
  - Unify `ruleset` into `bundle` across `src/rules_engine.py`, `src/bundle.py`, `src/cli.py`, and `src/header.py` as the single additive composition primitive (removing `-exclude` support while keeping `ruleset` and `*.ruleset` as legacy aliases during migration).
  - Support `.ctx.bundle` as the canonical root spec filename in `find_spec_file()` and `--init` with seamless fallback to `.agents_bundle`.
  - Emit `Bundle-Name: agents_bundle` in non-plain output headers. When unpacking an upstream `context-bundle-protocol` stream in `src/upstream.py`, read `Bundle-Name: <producer>` (rejecting duplicate producer names in the same pipeline) and automatically namespace all non-transport preamble headers (except `Workdir`) as `<producer>.<key_lower>` (e.g. `todo_md.task`, `todo_md.prefix`, `todo_md.status`, `todo_md.title`, `todo_md.files`, `todo_md.role`). Support dot-separated variable names (`[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*`) in `if`, `let`, `export`, and `{name:default}`.
  - Standardize `context-bundle-protocol` fragment kinds to the 4 canonical `.bundle` content directives (`rule`, `file`, `cmd`, `prompt`): emit `"kind": "file"` (instead of `"kind": "include"`) in `src/includes.py` `render_span()`, and normalize legacy upstream `"include"` -> `"file"` and `"task"` / `"context"` -> `"prompt"` in `src/upstream.py`.
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
- Target files: `src/header.py`, `src/includes.py`, `src/rules_engine.py`, `src/upstream.py`, `src/bundle.py`, `src/cli.py`, `agents/agents_bundle.md`, `README.md`, `tests/test_rules_engine.py`, `tests/test_upstream.py`, `tests/test_bundle.py`.
__RB_STEP__:2

# ⚪ [NEW] F27: Rename project to ctx-bundle and CLI utility to ctx

- Depends on: F15
- Rename project/repository references from `agents_bundle` to `ctx-bundle` and CLI entrypoint from `agents_bundle` to `ctx` (with `.ctx.bundle` as root bundle config and agreed deprecation aliases/symlinks and env-var updates from `todo_flow:D8` and ADR 0003).
- Remove transitional `.bundle` migration aliases (`ruleset` / `*.ruleset`, `include`, `$`, `var`, `expose`, and `[if ...]` / `[/if]`) once all workspace and `agents-rules` bundles have migrated in `todo_flow:F4`.
- Acceptance criteria: `build.py` outputs `ctx`, `install.sh` installs `ctx` (plus any agreed compatibility alias), legacy `ruleset` / directive aliases are removed, `--help`/rules/docs/tests reflect `ctx-bundle` and `ctx`, and `python3 -m unittest discover -s tests` passes.
- Target files: `build.py`, `install.sh`, `src/cli.py`, `src/header.py`, `src/bundle.py`, `src/rules_engine.py`, `src/upstream.py`, `src/tree.py`, `agents/agents_bundle.md`, `.agents_bundle`, `AGENTS.md`, `README.md`, `VERSION`, `tests/helpers.py`, `tests/test_*.py`, and `.github/`.
