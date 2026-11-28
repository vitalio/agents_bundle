# 🎯 [NEXT] F44: Remove hardcoded DEFAULT_RULES_PKG (vitalio/agents-rules) and resolve root targets without hidden package fallback

- Depends on: D1
- Depends on: F43
- Bump: `MINOR`
- Remove `DEFAULT_RULES_PKG = "vitalio/agents-rules"` from `src/header.py`, `src/core.py`, `src/rules_engine.py`, `src/bundle.py`, and `src/cli.py` so `context` has no hardcoded knowledge of `vitalio/agents-rules`:
  - Root-level `bundle` and `rule` directives in `.context.bundle` and CLI (`context bundle ...`, `context rule ...`) must specify an explicit `<owner>/<repo>[@<ref>][:<item>]` package, URL, or local path (`./...`, `../...`), or match a rule/bundle in the current repository's local `agents/` directory; nested directives inside an external package bundle continue to inherit `default_pkg = child_pkg`.
  - Do not fall back to `<owner>/<repo>` repo-shorthand in `_parse_target_spec()` when `default_pkg` is set (nested directives inside a package bundle) and the unprefixed two-segment target (e.g. `rule role/reivew`) does not exist in `default_pkg`, so typos in intra-package rule or bundle paths fail immediately with `unknown rule/bundle ... in package ...` instead of attempting to clone `https://github.com/<seg1>/<seg2>.git`.
  - Pass `GIT_TERMINAL_PROMPT=0` in `env` and `stdin=subprocess.DEVNULL` to `git clone` in `_ensure_remote_package()` so nonexistent or unauthenticated remote packages fail fast without blocking on an interactive `Username for 'https://github.com':` prompt.
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
