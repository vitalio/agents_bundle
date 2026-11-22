# ✅ [DONE] F10: Enforce command allowlist policy in .agents_bundle for external bundles — *2026-11-23, Enforce command allowlist and workspace-root include boundary for external bundles*

- Depends on: F13, F7
- Support an explicit allowlist directive in root `.agents_bundle` (e.g. `allow <cmd1> <cmd2> ...` or per-bundle `bundle <pkg> allow=...`) defining which executables external bundles are permitted to run via `$` commands and `var x=$(...)` subshells in `parse_spec()` and `build_bundle()` (`src/bundle.py:167-566`).
- Statically inspect all parsed commands from included bundles before executing any shell command; fail fast with a clear error naming the blocked command and originating bundle if any command executable is not in the user's allowlist.
- Restrict `include` paths from external bundles in `_expand_include()` (`src/bundle.py:313-360`) to files inside the repository root (`spec_dir`) so external bundles cannot read arbitrary host paths outside the workspace.
- Target files: `src/header.py`, `src/bundle.py:167-566`, `src/rules_engine.py:412-566`, `AGENTS.md`, `README.md`, `tests/test_bundle.py:720-1070`.

# ✅ [DONE] F7: Support agents/ package directory, custom relative paths, and @ref local-resolve fix — *2026-11-22*

- Depends on: F13, F30
- Standardize `agents/` as the canonical package directory for rules (`.md`) and bundles (`.bundle`) across repositories (supporting logical domain subdirectories, `owner/repo` -> `agents/<repo>.bundle` or `agents/default.bundle`, and `owner/repo:domain` -> `agents/domain/domain.bundle`) while keeping fallback compatibility with legacy root `rules/`, `rulesets/`, `bundles/` and `src/` paths in `_load_package_from_dir()` and `resolve_bundle_source()` in `src/rules_engine.py:175-415`.
- Support explicit relative file paths inside a package (`owner/repo[@ref]:path/to/file`) and local relative paths (`./...`, `../...`).
- Fix `_ensure_remote_package()` in `src/rules_engine.py:242-295` so explicit `@<ref>` on `vitalio/*` packages fetches the requested ref instead of returning the unpinned local working tree.
- Keep `agents/agents_bundle.md`, `AGENTS.md`, `README.md`, `src/header.py`, and unit tests in `tests/test_rules_engine.py:1-323` and `tests/test_bundle.py:1-260` in sync.
- Target files: `src/header.py`, `src/rules_engine.py:175-415`, `src/bundle.py:167-268`, `AGENTS.md`, `README.md`, `tests/test_rules_engine.py:1-323`, `tests/test_bundle.py:1-260`.

# ✅ [DONE] F32: Render table-driven -h/--help output wrapped to <= 100 columns per stack/cli — *2026-11-22*

- Replace static `USAGE_TEMPLATE.format(...)` in `src/header.py` and `usage_text()` (`src/core.py`) with structured table-driven help rendering (`HELP_MAX_WIDTH = 100`, `HELP_PROSE_WIDTH = 80`, `HELP_INDENT = 2`, `HELP_GAP = 2`, matching `todo_md` and `vitalio/agents-rules:stack/cli`).
- Measure the left column width after expanding `{prog}`, `{default_pkg}`, and `{cache_dir}` within each section (`Usage:`, `Options:`, `Bundle Output Protocol:`, `Environment:`) so all descriptions and wrapped continuation lines align to the same column and no line exceeds 100 columns.
- Rebuild `./agents_bundle` via `python3 build.py` and add unit test assertions in `tests/test_cli.py` verifying that every line of `agents_bundle -h` / `--help` is `<= 100` columns and section description columns are aligned.
- Target files: `src/header.py`, `src/core.py`, `tests/test_cli.py`.

# ✅ [DONE] B2: Normalize upstream rule fragments through _parse_md_text() and _render_rule_vars() — *2026-11-22*

- In `build_bundle_from_spec()` (`src/bundle.py:345-415`), when ingesting upstream `kind: "rule"` fragments from `up_groups["rules"]`, pass each upstream rule body through `_parse_md_text(up_body, up_uid)[1]` and `_render_rule_vars(..., {**builtin_vars(spec_dir, piped=piped), **effective_cli_vars}).strip()` before appending to `pending_rules` (matching the processing applied to `EMBEDDED_RULE_NAME` and `.agents_bundle` rules):
  - Strips any leading `# Description:` metadata line from upstream tool rules (such as `todo_md:todo_md`).
  - Evaluates `[if ...]` conditional blocks/lines and `{cmd:...}` / template variable substitutions against the active session variables (`role`, `task`, etc.).
  - Skips appending the upstream rule if the rendered body is empty after conditional filtering.
- Add unit tests in `tests/test_upstream.py` verifying that upstream `rule` fragments have `# Description:` stripped, `[if role=...]` blocks filtered against `Role:` preamble headers or CLI `role=...` overrides, and `{cmd:...}` placeholders expanded.
- Target files: `src/bundle.py:340-415`, `tests/test_upstream.py`.

# ✅ [DONE] F31: Active backlog task references removed src/rules/agents_bundle.md and src/bundles/ — *2026-11-22, Replaced stale src/rules/agents_bundle.md and src/bundles/ references with agents/agents_bundle.md in F27*

Observed: the Target files bullet of the open task that depends on F6, F7, and F10 still lists `src/rules/agents_bundle.md` and `src/bundles/`, which no longer exist after the embedded rule moved to `agents/agents_bundle.md`. Impact: `todo_md files` preloads missing paths for that task and the reference misleads the next worker.

# ✅ [DONE] F30: Implement context-bundle-protocol v1 pass-through, range-aware include deduplication, root .agents_bundle chain provenance, and embedded rule — *2026-11-22*

- Implement the Assembler side of `context-bundle-protocol` v1 per `todo_flow` `docs/adr/0002-context-bundle-protocol-and-self-contained-producers.md`:
  - In `src/bundle.py` and `src/rules_engine.py`, emit `Bundle-Protocol: 1` in non-plain bundle headers; when piped `stdin` declares `Bundle-Boundary: <up_nonce>`, parse upstream preamble headers into `inferred_vars` (`CLI key=val > AGENTS_BUNDLE_VARS > piped preamble`), chain upstream `Bundle-Command` as `<upstream_cmd> | <agents_bundle_cmd>`, merge upstream `Bundle-Expose` / `Bundle-Hide`, and unpack upstream `<!-- bundle:<up_nonce>:part {...} -->` fragments by `kind`:
    - `kind == "rule"`: merge into `===== Rules =====` and deduplicate by rule `id` (`uid`).
    - `kind in ("include", "file")`: merge into file includes before `===== Prompt =====` and deduplicate across upstream includes, `.agents_bundle` `include` directives, and CLI file arguments with line-range coverage (a whole-file include absorbs any `start-end` slice of the same `resolved_path`, and overlapping or contained slices of the same file are merged into a single slice).
    - `kind in ("task", "context", "prompt")`: emit inside `===== Prompt =====` re-wrapped with the output `boundary` and preserving each fragment's individual metadata (`kind`, `id`, `name`, `chain`).
  - When assembling from `.agents_bundle` (`spec_file is not None`), pass `chain=[SPEC_FILE_NAME]` (`[".agents_bundle"]`) into `parse_spec()` so all fragments originating from `.agents_bundle` (and nested `.bundle` files) carry `chain: [".agents_bundle", ...]`, while keeping upstream piped fragments (`chain: ["todo_md"]`), embedded `agents_bundle` rule (`chain: ["agents_bundle"]`), and CLI file/`-p` arguments (`chain: []`) outside `.agents_bundle`'s `chain`.
  - Move and trim `src/rules/agents_bundle.md` to `agents/agents_bundle.md` (~10 lines covering `agents_bundle --tree` and session assembly/handoff, pointing to `agents_bundle -h` / `--list` when editing `.agents_bundle`), embed it into `src/header.py` (`EMBEDDED_RULE_AGENTS_BUNDLE`) via `build.py` (with source-tree fallback to `agents/agents_bundle.md`), auto-inject it into `===== Rules =====` with `chain: ["agents_bundle"]` (deduplicating legacy `vitalio/agents_bundle:agents_bundle`), and delete `src/bundles/agents_bundle.bundle`.
  - Move `Bundle Output Protocol` and `.bundle` directive reference documentation to `README.md` and `AGENTS.md`, and update `default_spec_template()` (`--init`) to remove `bundle vitalio/agents_bundle` and `bundle vitalio/todo_md` and use `include AGENTS.md`.
- Target files: `src/header.py`, `src/bundle.py:31-268`, `src/bundle.py:313-660`, `src/rules_engine.py:412-636`, `src/rules/agents_bundle.md`, `build.py`, `README.md`, `tests/test_bundle.py:1-260`, `tests/test_rules_engine.py:1-323`.

# ✅ [DONE] F29: Support glob path patterns and path:start-end line-range slices in include directive and CLI file arguments — *2026-11-21*

- In `assemble_bundle()` (`src/bundle.py:395-445`), expand relative glob patterns (`*`, `?`, `[`, including recursive `**` via `sorted(wdir.glob(clean))`, skipping `.git` and `__pycache__`) and parse optional `:start-end` (or `:line`) 1-based inclusive line-range suffixes on `included_files` items (from `include` directives and CLI `extra_files`) when the full string is not an existing file path on disk.
- Resolve each underlying file path against `wdir`, slice lines `start..end` (`lines[max(0, start - 1) : end]`) when a range is present, deduplicate by `(p, start, end)` so multiple slices of the same large file can be included, and emit line-range fragments with header `===== $ sed -n '<start>,<end>p' <disp> =====` and fragment metadata `{"kind": "include", "name": "<disp>:<start>-<end>", "chain": ...}`.
- Update `src/header.py`, `src/rules/agents_bundle.md`, `README.md`, and unit tests in `tests/test_bundle.py`, rebuild `./agents_bundle` via `build.py`, and bump `VERSION` for a MINOR release.

# ✅ [DONE] F6: Add bundle CLI subcommand to render and inspect .bundle files — *2026-11-21*

- Depends on: F13
- Add 'agents_bundle bundle <pkg>[:<name>] [k=v]' CLI subcommand (symmetric with 'ruleset' and 'rule') to render a bundle from the command line.
- Keep src/header.py (--help), src/rules/agents_bundle.md, README.md, and tests in sync.

# ✅ [DONE] F13: Make src/ modules standalone importable and extract core helpers from src/tree.py — *2026-11-21*

- Depends on: B1
- Move `prog_name()`, `cache_dir_path()`, and `usage_text()` out of `src/tree.py` into `src/header.py` (or a dedicated `src/core.py` in `MODULE_ORDER`) so `src/tree.py` handles only repository tree generation.
- Make each module under `src/` valid, standalone-importable Python for IDE/linter analysis while updating `build.py` to strip internal cross-module imports when assembling the single-file `agents_bundle` executable.
- Keep `AGENTS.md`, `build.py`, and unit tests in `tests/test_*.py` in sync.

# ✅ [DONE] B1: Fail fast when piped stdin is an empty FIFO instead of falling back to unpiped bundle assembly — *2026-11-21*

- In `cmd_bundle()` (`src/bundle.py`), detect when `sys.stdin` is an actual pipe/FIFO (`stat.S_ISFIFO(os.fstat(sys.stdin.fileno()).st_mode)`) and `piped_raw.strip()` is empty (for example when an upstream command in `todo_md <ID> | agents_bundle role=work | run_block` fails and exits without writing to `stdout`).
- When an actual pipe/FIFO delivers empty input, write a clear error message to `sys.stderr` (e.g. `agents_bundle: empty piped input on stdin (upstream command failed?)`) and return non-zero (`2`) immediately before evaluating `.agents_bundle` or `.bundle` `$ <cmd>` directives (while still allowing non-FIFO non-TTY stdin such as `/dev/null` in background/test runners).
- Cover empty-pipe failure vs `/dev/null` non-TTY behavior with unit tests in `tests/test_bundle.py`, rebuild `./agents_bundle` via `build.py`, and bump `VERSION` for a PATCH release.

# ✅ [DONE] F28: Speed up test suite (in-process runner, lazy urllib) and split monolithic test_agents_bundle.py into modular tests/test_*.py — *2026-11-20, In-process test runner, lazy urllib.request import, and modular tests/test_*.py split*

- Role: work
- Move `import urllib.request` out of top-level `src/header.py` into `fetch_remote_script()` in `src/cli.py` (and `src/rules_engine.py` URL fetching where needed) so local CLI startups do not pay the `urllib.request` import cost (~40 ms).
- Create `tests/helpers.py` containing `_seed_offline_rules_pkg()` and a shared base class `AgentsBundleTestCase(unittest.TestCase)` that loads `./agents_bundle` once in `setUpClass()` and provides `_assert_ok()`, `_run_in_process()`, `_run_subprocess()`, `_run()`, `_git()`, `_load_bundle_module()`, and `_extract_fragments()` helpers (isolating `cwd`, `env`, `sys.argv`, and `sys.stdin` with `contextlib.redirect_stdout` / `redirect_stderr` and full `stdout`/`stderr` diagnostic `msg=` on `returncode` assertions).
- Convert routine `subprocess.run([str(SCRIPT), ...])` calls to `self._run([str(SCRIPT), ...])` (keeping real subprocess smoke checks for `-h`/`--version`, `install.sh`, and `build.py --check`, and using `sys.executable` instead of `"python3"` literals).
- Split the 22 test methods in `tests/test_agents_bundle.py` programmatically via `ast.parse()` (`node.lineno`..`node.end_lineno`) without re-emitting test bodies in chat into modular test files mirroring `src/`:
  - `tests/test_cli.py` (`build.py --check`, `--help`, `--version`, missing spec hint, `install.sh`)
  - `tests/test_tree.py` (`--tree` exclusions, truncation, and `AGENTS.md` pinning)
  - `tests/test_rules_engine.py` (`ruleset`, `rule`, `--list`, circular reference detection, `--update-cache`, `--refresh`, and no implicit home package fallback)
  - `tests/test_bundle.py` (`.agents_bundle` directives, `var`, `include`, `[if]`, `$ <cmd>`, piped `stdin` / `Workdir:`, `Bundle-Boundary` nonce, `Bundle-Expose`, JSON fragment markers, provenance/telemetry, and `--plain`)
- Remove monolithic `tests/test_agents_bundle.py`, document the modular `tests/` layout in `AGENTS.md`, rebuild `./agents_bundle` via `build.py`, verify `python3 build.py --check`, ensure `python3 -m unittest discover -s tests` runs all 22 tests in `<1.5s`, and bump `VERSION` for a PATCH release.

# ✅ [DONE] F26: Remove bundle vitalio/run_block from --init template, .agents_bundle, and docs — *2026-11-19*

- Remove `bundle vitalio/run_block` from `default_spec_template()` in `src/bundle.py` (`agents_bundle --init`), from `.agents_bundle`, and from usage examples in `README.md`.
- Update `tests/test_agents_bundle.py`, rebuild `./agents_bundle` via `build.py`, and bump `VERSION` for a PATCH release.

# ✅ [DONE] F16: Update role=execute and role=audit examples to role=work and role=review — *Ready after agents-rules:F9 and agents-rules:F16*

- Replace `role=execute` and `role=audit` usage examples in `README.md` (and any bundled rule/help text if present) with `role=work` and `role=review` once the roles are renamed in `agents-rules` (coordinated in `todo_flow`).

# ✅ [DONE] F12: Detect and fail fast on circular ruleset and bundle references — *2026-11-18, Track active ruleset and bundle resolution chains and fail fast with cycle path diagnostics*

- Track active resolution chains across recursive `ruleset` expansion in `src/rules_engine.py` and recursive `bundle` expansion in `src/bundle.py`.
- Fail fast with a clear `SystemExit` diagnostic showing the cycle path instead of hitting `RecursionError`.
- Add unit tests covering self-referential and multi-step cycles in `tests/test_agents_bundle.py`.

# ✅ [DONE] F25: Emit neutral inclusion chain and root-level provenance in bundle fragment markers — *2026-11-18, Replaced group/via with neutral chain list across rules_engine, bundle, docs, help, and tests*

- Conform to the producer-agnostic Bundle Input Protocol (`<!-- bundle:<nonce>:part <json> -->`): replace `group` and `via` completely with a neutral `chain` list (`[]` for direct root directives and CLI inputs, or ordered inclusion path of bundle/ruleset specifiers from root, e.g. `["vitalio/outer", "vitalio/inner"]`) alongside `kind`, `id`/`name`, `rc`, and `ms` in `src/bundle.py` and `src/rules_engine.py` (including `records`).
- Stop setting `group=".agents_bundle"` or `via=".agents_bundle"` anywhere, so root directives (`rule`, `$`, `include`, `prompt`), CLI `extra_files`, and CLI `-p` prompts emit `chain: []` without leaking `.agents_bundle`; for a merged `===== Prompt =====` section, emit the shared `chain` when all prompt items share one, else `[]`.
- Preserve full multi-hop `chain` when expanding nested `bundle` and `ruleset` directives in `parse_spec()` (`src/bundle.py`) and `collect_directive_items()` (`src/rules_engine.py`) (root `rule` -> `[]`; root `ruleset R` -> `["R"]`; nested `bundle A` -> `ruleset R` -> `["A", "R"]`).
- Update `AGENTS.md`, `src/header.py` (`--help`), `README.md` (if needed), and unit tests in `tests/test_agents_bundle.py`, and rebuild `agents_bundle` via `build.py`.

# ✅ [DONE] F24: Include Title in default Bundle-Expose headers — *2026-11-18, Include Title in default Bundle-Expose headers*

- Depends on: F23
- Add `Title` to the default `Bundle-Expose` header list (`Role, Task, Title`) in `build_bundle` (`src/bundle.py`) so `Title:` preamble headers piped from `todo_md` (or supplied via `title=...`) are exposed to downstream consumers such as `run_block`.
- Sync `src/header.py` (`--help`), `src/rules/agents_bundle.md`, `README.md`, and `tests/test_agents_bundle.py`, and rebuild `agents_bundle` via `python3 build.py`.

# ✅ [DONE] F23: Add --plain flag (AGENTS_BUNDLE_PLAIN) and document Bundle Output Protocol — *2026-11-18, Add --plain flag (AGENTS_BUNDLE_PLAIN) and document Bundle Output Protocol*

- Depends on: F22
- Support `--plain` in `src/cli.py` / `src/bundle.py` and `AGENTS_BUNDLE_PLAIN=1` in the environment to omit transport `Bundle-*` headers (`Bundle-Boundary`, `Bundle-Expose`) and JSON fragment markers when plain Markdown/text output is requested.
- Update `--help` in `src/header.py`, `src/rules/agents_bundle.md`, `README.md`, and `AGENTS.md` to document the Bundle Output Protocol (`Bundle-Boundary`, `Bundle-Expose`, `expose`, fragment markers, and `--plain`).
- Add unit tests in `tests/test_agents_bundle.py` covering `--plain` and `AGENTS_BUNDLE_PLAIN=1`.

# ✅ [DONE] F22: Wrap emitted rules, commands, includes, and prompts in JSON fragment markers — *2026-11-18, Wrap emitted rules, commands, includes, and prompts in single-line JSON fragment markers*

- Depends on: F21
- Wrap each emitted rule, command section, included file section, and prompt block in `<!-- bundle:<nonce>:part {...} -->` and `<!-- bundle:<nonce>:end -->` single-line JSON markers in `src/bundle.py` and `src/rules_engine.py` using neutral fields (`kind`, `id`/`name`, `group`, `via`, `rc`, `ms`).
- Ensure markers serialize cleanly without breaking rule deduplication or multi-line outputs.
- Add unit tests in `tests/test_agents_bundle.py` covering all four fragment kinds (`rule`, `cmd`, `include`, `prompt`) and marker field schemas.

# ✅ [DONE] F21: Track bundle source (via/group) and command telemetry (rc, ms) — *2026-11-18, Propagated bundle source metadata (group/via) and command telemetry (rc/ms) across parse_spec, collect_directive_items, _run_spec_command, and build_bundle*

- Depends on: F19
- Propagate top-level source metadata (`group` / `via`, identifying the originating `bundle` or root `.agents_bundle`) through `parse_spec` in `src/bundle.py` and `collect_directive_items` in `src/rules_engine.py`.
- Record command exit code (`rc`) and elapsed execution duration in integer milliseconds (`ms`) when running `$ <cmd>` entries in `_run_spec_command` and `build_bundle` (`src/bundle.py`).
- Add unit tests in `tests/test_agents_bundle.py` verifying source provenance across nested bundles/rulesets and accurate `rc`/`ms` capture.

# ✅ [DONE] F19: Emit Bundle-Boundary nonce and Bundle-Expose header control — *2026-11-17*

- Add `json` and `secrets` standard library imports to `src/header.py`.
- Generate a per-run hex nonce in `build_bundle` (`src/bundle.py`) and emit `Bundle-Boundary: <nonce>` and `Bundle-Expose: Role, Task` by default.
- Support an `expose <key...>` directive in `.agents_bundle` / `.bundle` and `AGENTS_BUNDLE_EXPOSE` in the environment (normalizing keys to Title-Case header names) so projects can expose additional session headers while keeping unexposed template variables out of exposed session headers.
- Add unit tests in `tests/test_agents_bundle.py` covering default header exposure, `expose` directives, `AGENTS_BUNDLE_EXPOSE`, and per-run nonce uniqueness.

# ❌ [CANCELED] F14: Document bundle header and body output contract in README.md and AGENTS.md — *Superseded by F23 (Bundle Output Protocol documentation)*

- Document the standard output contract of `agents_bundle` (`Key: Value` metadata headers followed by a blank line and `===== ... =====` body sections) in `README.md` so downstream consumers like `run_block` can separate session metadata from the LLM prompt body.
- Record the header-block output invariant in `AGENTS.md` under `src/bundle.py` module boundaries.

# ✅ [DONE] F20: Map preamble headers (Task, Role, Workdir) from stdin without todo_md Markdown regex — *2026-11-17, Map stdin preamble headers to lowercase vars, remove Markdown regex, expose piped=1 builtin*

- Update `_parse_stdin_pipe` in `src/bundle.py` to parse `Key: Value` preamble headers: use `Workdir:` as the working directory (unless overridden by `-C`) and map other non-transport preamble headers (`Task:`, `Role:`, etc.) to lowercase template variables (`task`, `role`, ...) when not overridden by CLI `k=v` or env vars, keeping single-token `<ID>` fallback and removing the hardcoded `todo_md` Markdown status/emoji regex.
- Expose a builtin variable (such as `piped=1`) when stdin prompt text is present so bundles like `todo_md.bundle` can avoid duplicating task bodies already piped via stdin.
- Sync `README.md`, `src/header.py`, `src/rules/agents_bundle.md`, and `tests/test_agents_bundle.py`, and rebuild `agents_bundle` via `build.py`.

# ✅ [DONE] F18: Use piped Workdir header as the bundle working directory — *2026-11-17*

- In `src/bundle.py` (`_parse_stdin_pipe`, `cmd_bundle`), when piped stdin
  starts with a `Key: Value` preamble containing `Workdir:`, use that directory
  as `work_dir` for `.agents_bundle` lookup, `AGENTS.md`, `--tree`, and `$`
  commands, and strip the preamble from the prompt body.
- An explicit `-C`/`--dir` option takes priority; a missing or non-existent
  directory fails with a clear error and a non-zero status.
- Emit `Workdir: <path>` in the bundle header so downstream consumers such as
  `run_block` can read it.
- Keep `src/header.py` (`--help`), `README.md`, `AGENTS.md`, and
  `tests/test_*.py` in sync.

# ✅ [DONE] F17: Connect python-stdlib and python-annotations rules in .agents_bundle — *2026-11-16*

- In `.agents_bundle`, remove `py_min=3.9` from `stack/python-cli` and add
  `rule vitalio/agents-rules:stack/python-stdlib` and
  `rule vitalio/agents-rules:stack/python-annotations py_min=3.9`, after the
  python-cli split is released in agents-rules and the package cache is
  refreshed.
- Keep `from __future__ import annotations` only in `build.py` and
  `src/header.py`; do not add it to modules under `src/`.
- Run `python3 -m unittest discover -s tests`; if the progress line shows
  stderr noise, capture it with `contextlib.redirect_stderr` in `tests/`.

# ✅ [DONE] F11: Unify --update-cache, deduplicate --refresh per run, and remove implicit ~/vitalio_* fallback — *2026-11-16*

- Update `cmd_update_cache()` in `src/rules_engine.py` to refresh both Git repositories in `<cache_dir>/packages` (via `git fetch --depth 1` and `git reset --hard FETCH_HEAD` so branches, retagged refs, and force-pushes update cleanly) and cached files in `<cache_dir>/urls`, reporting clear per-item status.
- Memoize package and URL refreshes within a single invocation in `src/rules_engine.py` and `src/bundle.py` so `--refresh` fetches each remote dependency at most once per run.
- Remove the implicit `~/vitalio_*` home-directory lookup in `_ensure_remote_package` (`src/rules_engine.py`), relying strictly on explicit `AGENTS_BUNDLE_LOCAL_PKG_DIR` or the cache directory.
- Keep `src/header.py` (`--help`), `src/rules/agents_bundle.md`, `README.md`, and unit tests in `tests/test_agents_bundle.py` in sync.

# ✅ [DONE] F5: Emit a single Rules section before commands and group bundles at top — *2026-11-15, Emit a single Rules section before commands and group bundles at top*

- Collect all rule lines from `bundle`, `ruleset`, and `rule` directives into a single `===== Rules =====` section in `src/bundle.py` before executing and rendering any `$ <cmd>` sections so bundles containing commands never split `===== Rules =====` into multiple sections.
- Update `default_spec_template()` in `src/bundle.py` (`agents_bundle --init`) and repository `.agents_bundle` to group all `bundle` directives together at the top before `ruleset`, `rule`, and `$ <cmd>` directives.
- Add unit tests in `tests/test_agents_bundle.py` verifying a single `Rules` section when bundles contain commands.

# ✅ [DONE] F8: Support dynamic task resolution, task file auto-inclusion, and todo_md stdin pipeline in bundles — *2026-11-15, Support dynamic var/include directives and piped task stdin inference in bundles*

- Depends on: todo_md:F8
- Support dynamic variable resolution in `.bundle` / `.agents_bundle` (e.g. resolving `task` from the top `WIP`/`NEXT` task in `TODO.md` when `role=execute` or `role=work` is invoked without `task=<ID>`, or when task output is piped via `todo_md [<ID>] | agents_bundle | run_block`) so `Task: <ID>` is always emitted in the bundle header (`0.txt`).
- Support automatic inclusion of existing repository files referenced by the active `task=<ID>` (via `todo_md --files <ID>` or a bundle directive) alongside explicit `[file ...]` CLI arguments so execution sessions start with target files preloaded in `0.txt`.
- Update `src/rules/agents_bundle.md` (and `agents/rules/agents_bundle.md` per F7), `src/header.py`, `README.md`, and unit tests to document and test `todo_md | agents_bundle | run_block` and target-file preloading.

# ✅ [DONE] F9: Add Quick Installation instructions and update commands to README.md — *2026-11-15, Added Quick Installation instructions and update commands to README.md, cleaned up install.ps1 header, and bumped version*

- Add a Quick Installation section to README.md with one-liner install commands for Linux/macOS (install.sh) and Windows PowerShell 7+ (install.ps1), plus custom --name/--dir options and --update/--check-update CLI usage.
- Remove the obsolete --agents-md reference from the comment header in install.ps1.
- Verify python3 build.py --check and unit tests, and bump PATCH version in VERSION.

# ✅ [DONE] F1: Rename preset to ruleset and include to bundle (rule -> ruleset -> bundle hierarchy) — *2026-11-14, Renamed preset to ruleset and include to bundle across agents-rules and agents_bundle*

Establish a clean three-level entity hierarchy (`rule` -> `ruleset` -> `bundle`) with no backward-compatibility aliases:

- `rule` — atomic rule (`rules/<name>.md` in a rules package, local file, or URL).
- `ruleset` (replaces `preset`) — flat collection of rules and `[if ...]` conditions (`rulesets/<name>.ruleset`).
- `bundle` (replaces `include`) — reusable `.agents_bundle` fragment (`bundles/<name>.bundle`).

Target outcome across repositories:
1. **`~/agents-rules` (`vitalio/agents-rules`):**
   - Rename `presets/*.preset` to `rulesets/*.ruleset` and `includes/*.bundle` to `bundles/*.bundle`, updating internal directives and `README.md`. Commit and push.
2. **`~/agents_bundle`:**
   - Replace `preset` with `ruleset` and `include` with `bundle` across `.agents_bundle` directives, CLI subcommands, `--list`, `--init`, `--help`, documentation, `.agents_bundle`, and tests.
   - Rebuild, test, reinstall locally, refresh cached packages, and release a new version (commit, tag, and push).
3. **Dependent `.agents_bundle` files:**
   - Update `preset` -> `ruleset` and `include` -> `bundle` in `~/chrome/canary/.agents_bundle` (gitignored, do not commit) and in `~/todo_md/.agents_bundle`, `~/run_block/.agents_bundle`, and `~/co_turn/.agents_bundle` (commit and push each repository).

# ✅ [DONE] F2: Support AGENTS_BUNDLE_VARS environment variable for personal default key=val overrides — *2026-11-14*

- Parse key=val pairs from AGENTS_BUNDLE_VARS in the environment as user-level defaults (overridable by CLI key=val arguments) so personal settings such as chat_lang=<lang> do not need to be committed into repository .agents_bundle files.

# ✅ [DONE] F3: Add --agents, active bundle header variables, and 4-role workflow (design, plan, execute, audit) — *2026-11-14, c05091c*

- Add --agents flag and bundle vitalio/agents-rules:agents_bundle (--agents + conditional --list in role=design).
- Emit actual invocation in Bundle-Command: and Title-Case variable headers (Role:, Task:, etc.) in bundle header.
- Define 4 orthogonal roles in vitalio/agents-rules (design, plan, execute, audit) and bind their artifacts in todo_md.bundle.

# ✅ [DONE] F4: Support bundle <owner>/<repo> shorthand, add src/rules & src/bundles, and remove --agents CLI flag — *2026-11-14*
