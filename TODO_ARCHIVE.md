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
