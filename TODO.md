# 🎯 [NEXT] F39: Resolve exported session variables in a pre-pass and stratify rules into invariant and conditional cache layers

- Depends on: F38
- Bump: `MINOR`
- In `parse_spec()` and `build_bundle()` (`src/bundle.py`, `src/rules_engine.py`), combine a two-pass session variable pre-pass, package-shorthand `rule <owner>/<repo>` resolution, and two-layer rule cache stratification while preserving `.context.bundle` declaration order within each layer:
  - Pass 1 (session variable & `export` pre-pass): traverse `.context.bundle` and child `.bundle` ASTs evaluating only `allow`, `let`, `export`, `if` / `else if` / `else`, and nested `bundle` directives without running `cmd` or expanding `file` items (caching dynamic `let x=$(...)` results by scope and command so subshells never execute twice). Enforce strict precedence: CLI `key=val` (`CONTEXT_BUNDLE_VARS`) > root `.context.bundle` `let key=val` (and inline `bundle ... key=val`) > child bundle `export <var>` in top-down order (first non-empty writer wins; empty values do not claim the variable and later child bundles cannot overwrite an already-resolved non-empty variable) > child bundle-local `let key=default`.
  - Pass 2 (declaration-order content collection): evaluate `.context.bundle` top-down with `session_vars` populated from Pass 1 so `core` placed first in `.context.bundle` sees `role`, `task`, and `title` exported by a trailing `adapters/todo-md` bundle.
  - Default package rule shorthand (`rule <owner>/<repo>[@<ref>]`): mirror `bundle <owner>/<repo>` by enabling `allow_repo_shorthand=True` for `rule` targets without `:`, resolving in order: (1) `agents/<repo>.md` (or `agents/<repo>/<repo>.md`), (2) `agents/default.md` (or `agents/default/default.md`), (3) the sole rule in `agents/*.md` when the package contains exactly one rule (`len(rules_dict) == 1`), returning its canonical rule ID `<owner>/<repo>:<rule_key>` (e.g. `rule vitalio/todo-md` -> `vitalio/todo-md:todo`) and reusing the already-piped upstream rule body from `up_groups["rules"]` when that canonical ID is present in piped stdin.
  - Two-layer `===== Rules =====` cache stratification in `build_bundle()`: partition collected rules into Layer 1 (role- and session-invariant rules from `.context.bundle` whose condition chain and template placeholders do not reference dynamic session/pipeline variables such as `role`, `piped`, `upstream.vars` / `todo_md.*`, `export` variables, or CLI overrides — e.g. unconditional `core/*`, `os/*`, `vcs/*`, `vitalio/todo-md:todo` via `adapters/todo-md`, `collab/commits`, and `release/*` rules — followed by the embedded `vitalio/context-bundle:context` rule) and Layer 2 (session- and role-conditional rules from `.context.bundle` in declaration order, followed by any remaining unreferenced upstream piped `up_groups["rules"]`).
- Update `README.md` and `AGENTS.md`, and add unit tests in `tests/test_bundle.py` and `tests/test_rules_engine.py` covering `rule <owner>/<repo>` shorthand resolution, `adapters/todo-md` placed after `core`, variable precedence across CLI / root `let` / multiple child `export` bundles, and Layer 1 before Layer 2 rule stratification across role switches and piped vs. non-piped runs.

# 🎯 [NEXT] F40: Replace allow directive and hardcoded git/todo command whitelists with unified trusted.json command-tree hashing

- Depends on: F39
- Bump: `MINOR`
- Remove the `allow` directive (and inline `bundle ... allow=...`) from the `.bundle` language in `src/bundle.py` and `src/header.py`, leaving the 8 core directives (`bundle`, `rule`, `file`, `cmd`, `prompt`, `let`, `export`, `if` / `else if` / `else`).
- Remove all hardcoded external CLI command whitelists and shell-command executable parsers from `src/bundle.py`: `_GIT_READONLY_SUBCMDS`, `_GIT_BRANCH_VALUE_FLAGS`, `_GIT_BRANCH_SAFE_BOOL_FLAGS`, `_is_safe_git_branch_args()`, `_TODO_MUTATING_SUBCMDS`, `_TODO_READONLY_SUBCMDS`, `_TODO_FORBIDDEN_FLAGS`, `_is_safe_todo_args()`, `_SHELL_WRAPPER_BINS`, `_parse_allow_bins()`, `_extract_subshells_and_segments()`, `_extract_command_executables()`, `_check_command_allowed()`, and the legacy `agents_bundle` executable alias. Keep only the in-process `context --tree` fast path exempt from external shell execution trust.
- Unify trust verification around `context --trust` (`trusted.json`): compute the trust digest over the root `.context.bundle` (and local child bundles) together with the ordered set of shell command templates (`cmd ...`, `let x=$(...)`, `file $(...)`) collected across referenced external bundles; when untrusted, display the pending shell commands in the `/dev/tty` `[y/N]` trust prompt (or non-interactive error message), and automatically record trust in `trusted.json` when creating a starter file via `context --init`.
- Update `README.md`, `AGENTS.md`, and `tests/test_bundle.py`, and rebuild `./context` via `python3 build.py`.

# 🎯 [NEXT] D1: Design local .context/ overlays, package lock/vendoring, and ephemeral task-scout bundles

- Depends on: F39 -> F40
- Evaluate separating repository-exported rules/bundles under root `agents/` from project-local context assembly assets under `.context/`:
  - `agents/` remains the public package export directory consumed by downstream projects (`<owner>/<repo>`).
  - `.context/rules/` (optional) stores project-local roles and rules that are not exported outside the repository.
  - `.context/tasks/<ID>.bundle` (gitignored ephemeral file) stores pre-flight task reconnaissance slices (`file <path>:<start>-<end>`) and entry-point notes generated by a fast read-only scout step (`role=scout` / `lets scout <ID>`).
- Preserve 100% prompt-cache prefix stability when loading `.context/tasks/<ID>.bundle`: inject task-scout `file` and `prompt` fragments strictly into the dynamic session tail (`user[0]`) without mutating Layer 1 or Layer 2 `[system]` rules (`F39`).
- Evaluate offline-first package pinning (`.context/lock.json` recording commit SHA and tree hash, plus optional `.context/vendor/<owner>/<repo>/` for standalone external repositories without forcing duplicate vendor commits across local multi-repo workspaces) and unified project trust (`context --trust` hashing `.context.bundle` and `.context/` instead of per-binary `allow` Maintenance).

# ⚪ [NEW] F35: Add --compile flag to compile baseline AGENTS.md from .context.bundle

- Depends on: F36 -> F34
- Depends on: F39
- Implement `context --compile` so `context --compile > AGENTS.md` renders a static baseline `AGENTS.md` from the project's `.context.bundle` (and local `agents/*.md` rules) without role-specific or session-specific runtime headers.
