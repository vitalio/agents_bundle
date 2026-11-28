# 🎯 [NEXT] F43: Remove legacy agents_bundle, .agents_bundle, todo_md, and run_block migration shims

- Depends on: F42
- Bump: `PATCH`
- Remove post-ADR-0004 legacy migration shims and fallbacks across `src/`, `install.sh`, `README.md`, `AGENTS.md`, and `tests/` (keeping canonical `context-bundle-protocol` v1 variable normalization `<owner>.<repo>.*` / `todo_md.*` in `src/upstream.py` intact):
  - `src/header.py` & `src/bundle.py`: remove `LEGACY_REPO_MARKER`, `LEGACY_SPEC_FILE_NAME` (`.agents_bundle`), and `LEGACY_RULE_ID`; resolve only `SPEC_FILE_NAME` (`.context.bundle`) in `find_spec_file()`, `cmd_trust()`, `parse_spec()`, and `build_bundle()`; remove `LEGACY_RULE_ID` and `"agents_bundle"` from `spec_rules` / `upstream_rule_entries` filters; drop `(or .agents_bundle)` from `HELP_SECTIONS` and error messages.
  - `src/core.py`: remove `_OBSOLETE_VITALIO_PKGS = ("agents_bundle", "run_block", "todo_md")` and `_migrate_and_prune_cache()` (`~/.cache/agents_bundle` migration and obsolete package pruning).
  - `src/cli.py` & `install.sh`: remove `_remove_legacy_binary()`, `LEGACY_REPO_MARKER` checks, `self_file.name == "agents_bundle"` rename logic in `cmd_update()`, and `agents_bundle` binary/cache cleanup in `cmd_uninstall()` and `install.sh`.
  - `README.md`, `AGENTS.md`, & `tests/`: remove `.agents_bundle` and `~/.cache/agents_bundle` migration references from documentation; update `tests/helpers.py`, `tests/test_bundle.py`, `tests/test_rules_engine.py`, `tests/test_cli.py`, `tests/test_core.py`, and `tests/test_includes.py` to use `.context.bundle`, `vitalio/todo-md`, and `context_bundle_mod`, and remove obsolete legacy migration tests.
- Rebuild `./context` via `python3 build.py` and verify the full unit test suite passes.

# 🎯 [NEXT] F44: Remove hardcoded DEFAULT_RULES_PKG (vitalio/agents-rules) and resolve root targets without hidden package fallback

- Depends on: D1
- Depends on: F43
- Bump: `MINOR`
- Remove `DEFAULT_RULES_PKG = "vitalio/agents-rules"` from `src/header.py`, `src/core.py`, `src/rules_engine.py`, `src/bundle.py`, and `src/cli.py` so `context` has no hardcoded knowledge of `vitalio/agents-rules`:
  - Root-level `bundle` and `rule` directives in `.context.bundle` and CLI (`context bundle ...`, `context rule ...`) must specify an explicit `<owner>/<repo>[@<ref>][:<item>]` package, URL, or local path (`./...`, `../...`), or match a rule/bundle in the current repository's local `agents/` directory; nested directives inside an external package bundle continue to inherit `default_pkg = child_pkg`.
  - Update `context --list [pkg]` (`cmd_list_rules()`) so running without a `pkg` argument lists built-in variables together with any local `agents/` bundles/rules and packages referenced in the current `.context.bundle` (or prints a usage hint when none are present), and update `default_spec_template()` (`context --init`) and `HELP_SECTIONS` (`{default_pkg}` removal in `src/header.py` and `src/core.py`).
  - Fix nested target resolution when a local directory package (`./path/to/pkg:<item>`) includes sibling bundles or rules so `work_dir` remains anchored at the repository root and local package files inside `root_dir` are tracked as local files in `trusted.json`.
  - Update `README.md`, `AGENTS.md`, and unit tests in `tests/test_core.py`, `tests/test_cli.py`, `tests/test_rules_engine.py`, and `tests/test_bundle.py`, rebuild `./context` via `python3 build.py`, and verify `python3 build.py --check`.

# 🎯 [NEXT] F35: Compile self-contained AGENTS.md (--compile) and load compiled context with -f/--file override

- Depends on: F36 -> F34
- Depends on: F39, D1 -> F44
- Bump: `MINOR`
- Add `context --compile [-f SPEC] [-C DIR]` and `-f, --file FILE` source selection across `src/cli.py`, `src/bundle.py`, `src/includes.py`, and `src/header.py`:
  - `context --compile [-f SPEC] [-C DIR]`: compile `.context.bundle` (or `SPEC`) into an in-place delimited `<!-- context:compiled ... -->...<!-- /context:compiled -->` block in `AGENTS.md`, preserving all user-authored project instructions outside the block across repeated compilations and recording trust for the compiled spec in `trusted.json`.
  - Self-contained compiled block: embed both Layer 1 invariant rules and conditional Layer 2 rules (`if role=...`) together with variable/command/file directives inside the compiled block so `AGENTS.md` works both as clean readable Markdown for standalone tools and as a zero-dependency offline bundle source for `context`.
  - Source resolution & `-f, --file FILE` override: in `build_bundle()` / `cmd_bundle()`, auto-select the compiled block in `AGENTS.md` when present in `Workdir` (without reading `.context.bundle` or querying external packages), falling back to `.context.bundle` otherwise; allow `-f, --file FILE` to explicitly force `.context.bundle`, `AGENTS.md`, or any custom bundle file path.
  - Deduplicated `file AGENTS.md` expansion: in `read_span()` (`src/includes.py`), strip any `<!-- context:compiled ... -->...<!-- /context:compiled -->` block when reading `AGENTS.md` so `===== $ cat AGENTS.md =====` emits only the user-authored project section (and omits the span if the remaining user section is empty) in both compiled and `.context.bundle` modes.
  - Document `--compile` and `-f, --file FILE` in `src/header.py` (`--help`), `README.md`, and `AGENTS.md`, add unit tests in `tests/test_bundle.py`, `tests/test_includes.py`, and `tests/test_cli.py`, and rebuild `./context` via `python3 build.py`.
