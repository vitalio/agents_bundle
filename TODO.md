# 🎯 [NEXT] F30: Implement context-bundle-protocol v1 pass-through, root .agents_bundle chain provenance, and self-contained embedded rule

- Depends on: F29
- Implement the Assembler side of `context-bundle-protocol` v1 per `todo_flow` `docs/adr/0002-context-bundle-protocol-and-self-contained-producers.md`:
  - In `src/bundle.py` and `src/rules_engine.py`, emit `Bundle-Protocol: 1` in non-plain bundle headers; when piped `stdin` declares `Bundle-Boundary: <up_nonce>`, parse upstream preamble headers into `inferred_vars` (`CLI key=val > AGENTS_BUNDLE_VARS > piped preamble`), chain upstream `Bundle-Command` as `<upstream_cmd> | <agents_bundle_cmd>`, merge upstream `Bundle-Expose` / `Bundle-Hide`, and unpack upstream `<!-- bundle:<up_nonce>:part {...} -->` fragments by `kind`:
    - `kind == "rule"`: merge into `===== Rules =====` and deduplicate by rule `id` (`uid`).
    - `kind in ("include", "file")`: merge into file includes before `===== Prompt =====` and deduplicate by `(resolved_path, start, end)` against `.agents_bundle` `include` directives and CLI file arguments.
    - `kind in ("task", "context", "prompt")`: emit inside `===== Prompt =====` re-wrapped with the output `boundary` and preserving each fragment's individual metadata (`kind`, `id`, `name`, `chain`).
  - When assembling from `.agents_bundle` (`spec_file is not None`), pass `chain=[SPEC_FILE_NAME]` (`[".agents_bundle"]`) into `parse_spec()` so all fragments originating from `.agents_bundle` (and nested `.bundle` files) carry `chain: [".agents_bundle", ...]`, while keeping upstream piped fragments (`chain: ["todo_md"]`), embedded `agents_bundle` rule (`chain: ["agents_bundle"]`), and CLI file/`-p` arguments (`chain: []`) outside `.agents_bundle`'s `chain`.
  - Move and trim `src/rules/agents_bundle.md` to `agents/agents_bundle.md` (~10 lines covering `agents_bundle --tree` and session assembly/handoff, pointing to `agents_bundle -h` / `--list` when editing `.agents_bundle`), embed it into `src/header.py` (`EMBEDDED_RULE_AGENTS_BUNDLE`) via `build.py` (with source-tree fallback to `agents/agents_bundle.md`), auto-inject it into `===== Rules =====` with `chain: ["agents_bundle"]` (deduplicating legacy `vitalio/agents_bundle:agents_bundle`), and delete `src/bundles/agents_bundle.bundle`.
  - Move `Bundle Output Protocol` and `.bundle` directive reference documentation to `README.md` and `AGENTS.md`, and update `default_spec_template()` (`--init`) to remove `bundle vitalio/agents_bundle` and `bundle vitalio/todo_md` and use `include AGENTS.md`.
  - Target files: `src/header.py`, `src/bundle.py:31-268`, `src/bundle.py:313-660`, `src/rules_engine.py:412-636`, `src/rules/agents_bundle.md`, `build.py`, `AGENTS.md`, `README.md`, `tests/test_bundle.py:1-260`, `tests/test_rules_engine.py:1-323`.

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
