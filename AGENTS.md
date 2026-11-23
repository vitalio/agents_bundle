# `agents_bundle` — Project-Specific Agent Rules

Universal workflow, language, Git, SemVer, Python CLI, and single-file build
rules are loaded via `.ctx.bundle` (or `.agents_bundle`).

## Architecture & Module Boundaries

- `src/header.py` — table-driven help data (`HELP_SECTIONS` and the `HELP_*`
  width constants), the standard library imports shared by the assembled
  executable, and version/protocol constants (`SPEC_FILE_NAME = ".ctx.bundle"`,
  `LEGACY_SPEC_FILE_NAME = ".agents_bundle"`, `PRODUCER_NAME = "agents_bundle"`,
  `VAR_NAME_PATTERN`).
- `src/core.py` — `prog_name()`, `cache_dir_path()`, and `usage_text()`
  helpers shared by all modules; `usage_text()` expands `{prog}`,
  `{default_pkg}`, and `{cache_dir}` in `HELP_SECTIONS`, aligns each section's
  description column, and wraps lines to at most `HELP_MAX_WIDTH` columns.
- `src/tree.py` — `agents_bundle --tree` token-budgeted repository file tree
  with `-x/--exclude`, `AGENTS.md` pinning, deep directory collapsing, and file
  list truncation.
- `src/rules_engine.py` — resolves atomic rules (`.md`) and composite bundles
  (`.bundle`) from canonical `agents/` (including `<repo>.bundle` /
  `default.bundle` for `<owner>/<repo>` and `agents/<domain>/<domain>.bundle` or
  `agents/<domain>/default.bundle` for `<owner>/<repo>:<domain>`), explicit
  package-relative paths (`<owner>/<repo>[@<ref>]:path/to/file`), local
  relative paths (`./...`, `../...`), or direct URLs (`http://`, `https://`,
  `file://`); fetches explicit `@<ref>` refs into the package cache even when
  `AGENTS_BUNDLE_LOCAL_PKG_DIR` is set; parses Python-indented `if <cond>`,
  `else if <cond>` (`elif <cond>`), and `else` blocks; and evaluates conditions
  against `os` (`linux`, `macos`), `vcs`, and dot-separated variables.
- `src/includes.py` — `file` item expansion (globs, `path:start-end`),
  repository-root boundary enforcement (`root_dir`) for external bundle files,
  and range-aware span deduplication shared by upstream, `.ctx.bundle` /
  `.agents_bundle`, and CLI files; emits canonical `"kind": "file"` metadata.
- `src/upstream.py` — parses piped stdin (preamble headers, `Bundle-Name:
  <producer>` producer namespacing `<producer>.<key_lower>` with duplicate
  producer rejection, and upstream fragments by `Bundle-Boundary` for the 4
  canonical `"rule"`, `"file"`, `"cmd"`, `"prompt"` kinds) into `PipedInput`.
- `src/bundle.py` — locates `.ctx.bundle` (with fallback to `.agents_bundle`),
  parses the 9-keyword `.bundle` language (`bundle`, `rule`, `file`, `cmd`,
  `prompt`, `let`, `export`, `if`/`else if`/`elif`/`else`, `allow`), enforces
  lexical scoping on `let` and session/header promotion on `export`, enforces
  the external bundle command allowlist before running shell commands,
  assembles `file` and `cmd` in declaration order, and writes the bundle to
  `stdout`.
- `agents/agents_bundle.md` — embedded agent rule (chain `agents_bundle`).
  `build.py` embeds it into `src/header.py` as `EMBEDDED_RULE_AGENTS_BUNDLE`;
  source-tree runs fall back to the file via `embedded_rule_text()` in
  `src/core.py`. Keep it about 10 lines.
- `src/cli.py` — CLI entrypoint, subcommand routing, and self-update
  (`--update`, `--check-update`).
- `tests/` — offline test suite split to mirror `src/`: `tests/helpers.py`
  (`AgentsBundleTestCase` in-process CLI runner and offline package fixtures),
  `tests/test_cli.py`, `tests/test_core.py`, `tests/test_tree.py`,
  `tests/test_rules_engine.py`, `tests/test_includes.py`,
  `tests/test_upstream.py`, and `tests/test_bundle.py`.
- Standalone modules: every module under `src/` carries its own
  `from __future__ import annotations` (when needed), standard library
  imports, and absolute sibling imports (`from src.<module> import ...`) so
  it imports cleanly for IDEs, linters, and tests. `build.py` strips all
  top-level imports from non-header modules when assembling `./agents_bundle`
  and fails the build unless each stripped import is provided by
  `src/header.py` or an earlier module in `MODULE_ORDER`; add every new
  standard library import to `src/header.py` as well.

## Bundle Output Protocol

- Header visibility (`Bundle-*`): Emit `Bundle-Command`,
  `Bundle-Name: agents_bundle`, `Bundle-Boundary: <nonce>`,
  `Bundle-Protocol: 1`, exported `Key: Value` variable headers (promoted via
  `export`), and `Workdir: <path>` by default. Unexported variables do not
  appear in the output preamble.
- Fragment markers: Wrap emitted rules, files, commands (`rc`, `ms`), and
  prompts in `<!-- bundle:<nonce>:part <json> -->` and
  `<!-- bundle:<nonce>:end -->` JSON markers using the 4 canonical `kind`
  values (`rule`, `file`, `cmd`, `prompt`), `id`/`name`, `chain` (`[]` at
  root/CLI or ordered inclusion path of bundle specifiers), `rc`, and `ms`
  fields without hardcoding `run_block` internals.
- Plain output (`--plain`): Pass `--plain` or set `AGENTS_BUNDLE_PLAIN=1` to
  omit transport `Bundle-*` headers (`Bundle-Command`, `Bundle-Name`,
  `Bundle-Boundary`, `Bundle-Protocol`) and JSON fragment markers when pure
  Markdown/text output is requested.
- Piped upstream bundles (`context-bundle-protocol` v1): stdin with
  `Bundle-Boundary` is unpacked by `src/upstream.py`; when `Bundle-Name:
  <producer>` is present, non-transport preamble headers (except `Workdir`) are
  namespaced as `<producer>.<key_lower>` and duplicate producer names in the
  same pipeline are rejected. `rule` fragments merge by `id`, `file` fragments
  merge with bundle and CLI files through `merge_spans()` at first occurrence,
  and `prompt` fragments are re-wrapped inside the Prompt section keeping their
  metadata. `Bundle-Command` is chained with ` | `.
- Rule body normalization: embedded and upstream `rule` fragments go through
  `normalize_rule_body()` (`_parse_md_text()` then `_render_rule_vars()`).
  Rule `.md` bodies are static Markdown: only `# Description:` stripping and
  `{name:default}` substitution apply; `if` conditions belong to `.bundle`
  specs, never to rule bodies.
- Chain provenance: `build_bundle()` passes `chain=[spec_file.name]` to
  `parse_spec()` only when `.ctx.bundle` or `.agents_bundle` is read; `bundle`
  subcommand, piped, CLI, and embedded fragments stay outside it. Keep the
  `.bundle` directive reference in `README.md`.
