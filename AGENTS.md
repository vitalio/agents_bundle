# `context-bundle` (`context`) — Project-Specific Agent Rules

Universal workflow, language, Git, SemVer, Python CLI, and single-file build
rules are loaded via `.context.bundle`.

## Architecture & Module Boundaries

- `src/header.py` — table-driven help data (`HELP_SECTIONS` and the `HELP_*`
  width constants), the standard library imports shared by the assembled
  executable, and version/protocol constants (`SPEC_FILE_NAME = ".context.bundle"`,
  `PRODUCER_NAME = "vitalio/context-bundle"`,
  `EMBEDDED_RULE_ID = "vitalio/context-bundle:context"`, `VAR_NAME_PATTERN`).
- `src/core.py` — `prog_name()`, `cache_dir_path()`, `state_dir_path()`,
  `trust_file_path()`, and `usage_text()` helpers shared by all modules;
  `cache_dir_path()` atomically migrates `~/.cache/agents_bundle` ->
  `~/.cache/context-bundle` and prunes obsolete
  `packages/vitalio/{agents_bundle,run_block,todo_md}` clones; `usage_text()`
  expands `{prog}`, `{default_pkg}`, `{cache_dir}`, and `{trust_file}` in
  `HELP_SECTIONS`, aligns the description column at a shared column across all
  sections, and wraps lines to at most `HELP_MAX_WIDTH` columns.
- `src/tree.py` — `context --tree` token-budgeted repository file tree
  with `-x/--exclude`, `AGENTS.md` pinning, large/dense file byte sizes, deep
  directory collapsing, file list truncation, and total byte size summary.
- `src/rules_engine.py` — resolves atomic rules (`.md`) and composite bundles
  (`.bundle`) from canonical `agents/` (including `<repo>.bundle` /
  `default.bundle` for `bundle <owner>/<repo>`, `<repo>.md` / `default.md` /
  sole `agents/*.md` rule for `rule <owner>/<repo>`, and
  `agents/<domain>/<domain>.bundle` or `agents/<domain>/default.bundle` for
  `<owner>/<repo>:<domain>`), explicit package-relative paths
  (`<owner>/<repo>[@<ref>]:path/to/file`), local relative paths (`./...`,
  `../...`), or direct URLs (`http://`, `https://`, `file://`); reuses piped
  upstream rule bodies when a referenced package rule's canonical ID is already
  present in `up_groups["rules"]`; fetches explicit `@<ref>` refs into the
  package cache even when `CONTEXT_BUNDLE_LOCAL_PKG_DIR` is set; parses
  Python-indented `if <cond>`, `else if <cond>` (`elif <cond>`), and `else`
  blocks; and evaluates conditions against `os` (`linux`, `macos`), `vcs`, and
  dot-separated variables.
- `src/includes.py` — `file` item expansion (globs, `path:start-end`, `~`),
  repository-root boundary enforcement (`root_dir=spec_dir`) for all bundle
  `file` directives (root `.context.bundle` and external child bundles, while
  keeping CLI `FILE ...` arguments unrestricted), and range-aware span
  deduplication shared by upstream, `.context.bundle`, and CLI files; emits
  canonical `"kind": "file"` metadata.
- `src/upstream.py` — parses piped stdin (preamble headers, `Bundle-Name:
  <owner>/<repo>` or `<producer>` producer namespacing `<owner>.<repo>.<key>`
  and unambiguous short alias `<repo>.<key>` with duplicate producer rejection,
  and upstream fragments by `Bundle-Boundary` for the 4 canonical `"rule"`,
  `"file"`, `"cmd"`, `"prompt"` kinds) into `PipedInput`.
- `src/bundle.py` — locates `.context.bundle`,
  parses the 8-keyword `.bundle` language (`bundle`, `rule`, `file`, `cmd`,
  `prompt`, `let`, `export`, `if`/`else if`/`elif`/`else`) in two passes (Pass 1
  resolves session variables and `export` directives across nested bundles with
  cached `let x=$(...)` subshells and precedence CLI > root `let` / inline
  `bundle ... k=v` > child `export` first-non-empty-writer > child-local `let`;
  Pass 2 collects rules, files, commands, and prompts in declaration order),
  stratifies `===== Rules =====` into Layer 1 (invariant rules + embedded
  `vitalio/context-bundle:context`) and Layer 2 (session/role conditional rules
  + remaining unreferenced upstream rules), keeps only the in-process
  `context --tree` fast path exempt from external shell execution trust while
  requiring unified `(realpath, sha256)` trust in
  `${XDG_STATE_HOME:-~/.local/state}/context-bundle/trusted.json` (`0600`,
  computed over root `.context.bundle`, local child bundles, and the ordered
  set of shell command templates `cmd ...`, `let x=$(...)`, `file $(...)`
  collected across referenced external bundles; recorded via
  `context --trust [--revoke | --list]`, `context --init`, or `/dev/tty`
  prompt displaying pending shell commands), assembles `file` and `cmd` in
  declaration order, and writes the bundle to `stdout`.
- `agents/context.md` — embedded agent rule (`id: "vitalio/context-bundle:context"`,
  `chain: ["vitalio/context-bundle"]`). `build.py` embeds it into `src/header.py`
  as `EMBEDDED_RULE_CONTEXT`; source-tree runs fall back to the file via
  `embedded_rule_text()` in `src/core.py`. Keep it about 10 lines.
- `src/cli.py` — CLI entrypoint, subcommand routing, self-update
  (`--update`, `--check-update`), and `--uninstall`.
- `tests/` — offline test suite split to mirror `src/`: `tests/helpers.py`
  (`AgentsBundleTestCase` in-process CLI runner and offline package fixtures),
  `tests/test_cli.py`, `tests/test_core.py`, `tests/test_tree.py`,
  `tests/test_rules_engine.py`, `tests/test_includes.py`,
  `tests/test_upstream.py`, and `tests/test_bundle.py`.
- Standalone modules: every module under `src/` carries its own
  `from __future__ import annotations` (when needed), standard library
  imports, and absolute sibling imports (`from src.<module> import ...`) so
  it imports cleanly for IDEs, linters, and tests. `build.py` strips all
  top-level imports from non-header modules when assembling `./context`
  and fails the build unless each stripped import is provided by
  `src/header.py` or an earlier module in `MODULE_ORDER`; add every new
  standard library import to `src/header.py` as well.

## Bundle Output Protocol

- Header visibility (`Bundle-*`): Emit `Bundle-Command`,
  `Bundle-Name: vitalio/context-bundle`, `Bundle-Boundary: <nonce>`,
  `Bundle-Protocol: 1`, exported `Key: Value` variable headers (promoted via
  `export`), and `Workdir: <path>` by default. Unexported variables do not
  appear in the output preamble.
- Fragment markers: Wrap emitted rules, files, commands (`rc`, `ms`), and
  prompts in `<!-- bundle:<nonce>:part <json> -->` and
  `<!-- bundle:<nonce>:end -->` JSON markers using the 4 canonical `kind`
  values (`rule`, `file`, `cmd`, `prompt`), `id`/`name`, `chain` (`[]` at
  root/CLI or ordered inclusion path of bundle specifiers), `rc`, and `ms`
  fields without hardcoding `run-block` internals.
- Plain output (`--plain`): Pass `--plain` or set `CONTEXT_BUNDLE_PLAIN=1` to
  omit transport `Bundle-*` headers (`Bundle-Command`, `Bundle-Name`,
  `Bundle-Boundary`, `Bundle-Protocol`) and JSON fragment markers when pure
  Markdown/text output is requested.
- Piped upstream bundles (`context-bundle-protocol` v1): stdin with
  `Bundle-Boundary` is unpacked by `src/upstream.py`; when `Bundle-Name:
  <producer>` is present, `/` normalizes to `.` and `-` to `_` so non-transport
  preamble headers (except `Workdir`) populate `<owner>.<repo>.<key_lower>` and
  unambiguous `<repo>.<key_lower>` while duplicate producer names in the same
  pipeline are rejected. `rule` fragments merge by `id`, `file` fragments
  merge with bundle and CLI files through `merge_spans()` at first occurrence,
  and `prompt` fragments are re-wrapped inside the Prompt section keeping their
  metadata. `Bundle-Command` is chained with ` | `.
- Rule body normalization: embedded and upstream `rule` fragments go through
  `normalize_rule_body()` (`_parse_md_text()` then `_render_rule_vars()`).
  Rule `.md` bodies are static Markdown: only `# Description:` stripping and
  `{name:default}` substitution apply; `if` conditions belong to `.bundle`
  specs, never to rule bodies.
- Chain provenance: `build_bundle()` passes `chain=[spec_file.name]` to
  `parse_spec()` only when `.context.bundle` is read; `bundle`
  subcommand, piped, CLI, and embedded fragments stay outside it. Keep the
  `.bundle` directive reference in `README.md`.
