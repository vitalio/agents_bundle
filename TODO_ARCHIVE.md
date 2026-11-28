# ✅ [DONE] F43: Remove legacy agents_bundle, .agents_bundle, todo_md, and run_block migration shims — *2026-11-28, Removed legacy agents_bundle, .agents_bundle, todo_md, and run_block migration shims across src/, install.sh, README.md, AGENTS.md, and tests/.*

- Depends on: F42
- Bump: `PATCH`
- Remove post-ADR-0004 legacy migration shims and fallbacks across `src/`, `install.sh`, `README.md`, `AGENTS.md`, and `tests/` (keeping canonical `context-bundle-protocol` v1 variable normalization `<owner>.<repo>.*` / `todo_md.*` in `src/upstream.py` intact):
  - `src/header.py` & `src/bundle.py`: remove `LEGACY_REPO_MARKER`, `LEGACY_SPEC_FILE_NAME` (`.agents_bundle`), and `LEGACY_RULE_ID`; resolve only `SPEC_FILE_NAME` (`.context.bundle`) in `find_spec_file()`, `cmd_trust()`, `parse_spec()`, and `build_bundle()`; remove `LEGACY_RULE_ID` and `"agents_bundle"` from `spec_rules` / `upstream_rule_entries` filters; drop `(or .agents_bundle)` from `HELP_SECTIONS` and error messages.
  - `src/core.py`: remove `_OBSOLETE_VITALIO_PKGS = ("agents_bundle", "run_block", "todo_md")` and `_migrate_and_prune_cache()` (`~/.cache/agents_bundle` migration and obsolete package pruning).
  - `src/cli.py` & `install.sh`: remove `_remove_legacy_binary()`, `LEGACY_REPO_MARKER` checks, `self_file.name == "agents_bundle"` rename logic in `cmd_update()`, and `agents_bundle` binary/cache cleanup in `cmd_uninstall()` and `install.sh`.
  - `README.md`, `AGENTS.md`, & `tests/`: remove `.agents_bundle` and `~/.cache/agents_bundle` migration references from documentation; update `tests/helpers.py`, `tests/test_bundle.py`, `tests/test_rules_engine.py`, `tests/test_cli.py`, `tests/test_core.py`, and `tests/test_includes.py` to use `.context.bundle`, `vitalio/todo-md`, and `context_bundle_mod`, and remove obsolete legacy migration tests.
- Rebuild `./context` via `python3 build.py` and verify the full unit test suite passes.

# ✅ [DONE] F42: Fold --check-update into --update [--check | --force], separate Usage: from Commands: in context -h, and compact left-column signatures — *2026-11-28, Folded --check-update and --self-update into --update [--check | --force], separated Usage: from Commands: in context -h, compacted left-column signatures, and added HELP_MAX_LEFT guard.*

- Bump: `MINOR`
- Fold `--check-update` and `--self-update` into `context --update [--check | --force]` in `src/cli.py` and `src/header.py` per `agents/cli/lifecycle.md`:
  - Replace the top-level `--check-update` flag and `--self-update` alias with `context --update [--check | --force]` (`cmd_update(check=..., force=...)` or routing `--update --check` to `cmd_check_update()`), rejecting unknown flags or mutually exclusive `--check` + `--force` with exit status `2`.
- Update `src/header.py` and `src/core.py` (`HELP_USAGE`, `HELP_SECTIONS`, `usage_text()`) to match the refined `agents/cli/help.md` layout contract:
  - Render top-level `Usage:` syntax lines (`{prog} [k=v ...] [-p TEXT] [FILE ...]`, `{prog} <command|flag> [args] [opts]`) as a compact usage block rather than a two-column table.
  - Add a dedicated `Commands:` section for subcommands and mode flags (`bundle <pkg>[:<name>] [k=v]`, `rule <pkg>[:<name...>] [k=v]`, `--list | -l [pkg]`, `--update-cache`, `--init [--force]`, `--trust [opts]`, `--tree [DIR] [opts]`, `--update [--check | --force]`, `--uninstall`) without repeating `{prog} ` on every row, listing `--trust` sub-options (`--revoke`, `--list`, `-C DIR`) in the description column so the shared description column shifts left to ~34 columns.
  - Move `-V, --version` and `-h, --help` to the end of `Options:`, and guard `render_help_section()` / `usage_text()` with a maximum left-column cap (`HELP_MAX_LEFT`) so long custom binary names wrap/break cleanly without squeezing the right-hand column.
- Update `tests/test_cli.py`, `README.md`, and `AGENTS.md` to reflect `context --update [--check | --force]` and the grouped `-h`/`--help` sections, rebuild `./context` via `python3 build.py`, and run the test suite.

# ✅ [DONE] D1: Design local .context/ overlays, package lock/vendoring, and ephemeral task-scout bundles — *2026-11-28, Rejected dedicated .context/, lock.json, vendor/, and tasks/ engine abstractions in favor of removing hardcoded DEFAULT_RULES_PKG (F44), compiling self-contained AGENTS.md with in-place <!-- context:compiled --> blocks and -f/--file selection (F35), and using standard conditional bundle directives for preload slices.*

- Depends on: F39 -> F40 -> F41, B3
- Evaluate separating repository-exported rules/bundles under root `agents/` from project-local context assembly assets under `.context/`:
  - `agents/` remains the public package export directory consumed by downstream projects (`<owner>/<repo>`).
  - `.context/rules/` (optional) stores project-local roles and rules that are not exported outside the repository.
  - `.context/tasks/<ID>.bundle` (gitignored ephemeral file) stores pre-flight task reconnaissance slices (`file <path>:<start>-<end>`) and entry-point notes generated by a fast read-only scout step (`role=scout` / `lets scout <ID>`).
- Preserve 100% prompt-cache prefix stability when loading `.context/tasks/<ID>.bundle`: inject task-scout `file` and `prompt` fragments strictly into the dynamic session tail (`user[0]`) without mutating Layer 1 or Layer 2 `[system]` rules (`F39`).
- Evaluate offline-first package pinning (`.context/lock.json` recording commit SHA and tree hash, plus optional `.context/vendor/<owner>/<repo>/` for standalone external repositories without forcing duplicate vendor commits across local multi-repo workspaces) and unified project trust (`context --trust` hashing `.context.bundle` and `.context/` instead of per-binary `allow` Maintenance).

# ✅ [DONE] F41: Require trusted.json for all commands including context --tree and deduplicate trust-tree walks — *2026-11-27, Required trusted.json for all commands including context --tree, deduplicated trust-tree walks via cached snapshot, qualified external templates with bundle identity, and added target dir hint and positional [DIR] to --trust.*

- Depends on: F40
- Bump: `PATCH`
- Require `trusted.json` verification for every `cmd ...`, `let <k>=$(<cmd>)`, and `file $(<cmd>)` directive without exception (including `context --tree`), so untrusted `.context.bundle` specs remain strictly declarative (`rule`, `prompt`, static `let`/`export`/`if`, and `file` bounded to `spec_dir`).
- Remove `_is_safe_builtin_command()` and `_is_safe_tree_args()` from `src/bundle.py`, keeping in-process `_tree_from_args()` in `_run_spec_command()` purely as a runtime performance fast path after trust verification.
- Reuse the computed `(local_files, external_templates, pending_commands, digest)` trust snapshot across `is_spec_trusted()`, `_prompt_tty_trust()`, and `_ensure_root_spec_trusted()` within a single run instead of re-walking the bundle tree on disk multiple times, and qualify external command templates in the trust digest with their originating bundle identity.
- Include the target directory in the untrusted error hint in `_ensure_root_spec_trusted()` when `spec_file.resolve().parent != Path.cwd().resolve()` (for example, when `Workdir` is piped from an orchestrator via `todo <project>:<ID> -B | context` or passed via `-C DIR`), suggesting `inspect <spec_path> and run 'context --trust -C <dir>' to trust this file` (and accept an optional positional `[DIR]` in `cmd_trust()` alongside `-C DIR`).
- Update `README.md`, `AGENTS.md`, and `tests/test_bundle.py`, and rebuild `./context` via `python3 build.py`.

# ✅ [DONE] B3: Fix context --tree hang on large/CVS repositories (.cvsignore pruning and O(D log D) tree collapse) — *2026-11-27*

- Bump: `PATCH`
- In `src/tree.py` (`_TREE_SKIP_DIRS`, `_collect_repo_files()`):
  - Add `"CVS"`, `".svn"`, and `".hg"` to `_TREE_SKIP_DIRS` so VCS metadata directories are never walked during non-Git `os.walk()` fallback.
  - When falling back to `os.walk(root)` (e.g., in CVS repositories or plain directories where `git ls-files` exits non-zero), load ignore patterns from root `.cvsignore` and `.gitignore` (supporting basename/path globs via `fnmatch`, while preserving `AGENTS.md` files even if listed in `.cvsignore` / `.gitignore`) and prune matching directories in `dirnames[:]` and files in `filenames` before inspecting file metadata.
- In `src/tree.py` (`build_repo_tree()`):
  - Eliminate the `O(D^2)` bottleneck where Stage 1 (`deep_candidates`), Stage 2 (`trunc_candidates`), and Stage 3 (`top_candidates`) re-render the entire tree (`render_dir("")`) and rescan `all_dirs` on every single-directory collapse iteration (which hangs on repositories with thousands of nested directories such as `~/zon1`).
  - Maintain visible line counts incrementally as directories are collapsed / file lists truncated (or batch/binary-search ordered collapse candidates) so `render_dir()` only runs when checking the final token budget (`approx_tokens <= max_tokens`), keeping tree rendering sub-second on repositories with 10,000+ directories and 50,000+ files.
- Add unit tests in `tests/test_tree.py` covering `CVS/` and `.cvsignore` (`build.*`, glob patterns, and `AGENTS.md` preservation) during `os.walk` fallback as well as fast tree generation on deep multi-thousand-directory trees; update `AGENTS.md` and rebuild `./context` via `python3 build.py`.

# ✅ [DONE] L2: Remove session handoff and legacy run_block pipe from agents/context.md — *2026-11-26, Renamed Session assembly and handoff to Bundle assembly and removed legacy | run_block pipe in agents/context.md*

- Bump: `PATCH`
- Clean up `agents/context.md` and sync `EMBEDDED_RULE_CONTEXT` in `context`:
  - Rename `Session assembly and handoff:` to `Bundle assembly:` and remove `| run_block` from `[<upstream_cmd> | ]{cmd:context} [key=val ...] [-p "<prompt>"] [file ...]` so the embedded `context` rule describes only bundle assembly without instructing worker sessions to pipe into a runner for session handoff.
- Update any affected tests in `tests/` and verify the test suite passes.

# ✅ [DONE] F40: Replace allow directive and hardcoded git/todo command whitelists with unified trusted.json command-tree hashing — *2026-11-26*

- Depends on: F39
- Bump: `MINOR`
- Remove the `allow` directive (and inline `bundle ... allow=...`) from the `.bundle` language in `src/bundle.py` and `src/header.py`, leaving the 8 core directives (`bundle`, `rule`, `file`, `cmd`, `prompt`, `let`, `export`, `if` / `else if` / `else`).
- Remove all hardcoded external CLI command whitelists and shell-command executable parsers from `src/bundle.py`: `_GIT_READONLY_SUBCMDS`, `_GIT_BRANCH_VALUE_FLAGS`, `_GIT_BRANCH_SAFE_BOOL_FLAGS`, `_is_safe_git_branch_args()`, `_TODO_MUTATING_SUBCMDS`, `_TODO_READONLY_SUBCMDS`, `_TODO_FORBIDDEN_FLAGS`, `_is_safe_todo_args()`, `_SHELL_WRAPPER_BINS`, `_parse_allow_bins()`, `_extract_subshells_and_segments()`, `_extract_command_executables()`, `_check_command_allowed()`, and the legacy `agents_bundle` executable alias. Keep only the in-process `context --tree` fast path exempt from external shell execution trust.
- Unify trust verification around `context --trust` (`trusted.json`): compute the trust digest over the root `.context.bundle` (and local child bundles) together with the ordered set of shell command templates (`cmd ...`, `let x=$(...)`, `file $(...)`) collected across referenced external bundles; when untrusted, display the pending shell commands in the `/dev/tty` `[y/N]` trust prompt (or non-interactive error message), and automatically record trust in `trusted.json` when creating a starter file via `context --init`.
- Update `README.md`, `AGENTS.md`, and `tests/test_bundle.py`, and rebuild `./context` via `python3 build.py`.

# ✅ [DONE] F39: Resolve exported session variables in a pre-pass and stratify rules into invariant and conditional cache layers — *2026-11-26, Resolved exported session variables in a pre-pass, added rule <owner>/<repo> package shorthand with upstream rule reuse, and stratified rules into invariant Layer 1 and conditional Layer 2 cache layers.*

- Depends on: F38
- Bump: `MINOR`
- In `parse_spec()` and `build_bundle()` (`src/bundle.py`, `src/rules_engine.py`), combine a two-pass session variable pre-pass, package-shorthand `rule <owner>/<repo>` resolution, and two-layer rule cache stratification while preserving `.context.bundle` declaration order within each layer:
  - Pass 1 (session variable & `export` pre-pass): traverse `.context.bundle` and child `.bundle` ASTs evaluating only `allow`, `let`, `export`, `if` / `else if` / `else`, and nested `bundle` directives without running `cmd` or expanding `file` items (caching dynamic `let x=$(...)` results by scope and command so subshells never execute twice). Enforce strict precedence: CLI `key=val` (`CONTEXT_BUNDLE_VARS`) > root `.context.bundle` `let key=val` (and inline `bundle ... key=val`) > child bundle `export <var>` in top-down order (first non-empty writer wins; empty values do not claim the variable and later child bundles cannot overwrite an already-resolved non-empty variable) > child bundle-local `let key=default`.
  - Pass 2 (declaration-order content collection): evaluate `.context.bundle` top-down with `session_vars` populated from Pass 1 so `core` placed first in `.context.bundle` sees `role`, `task`, and `title` exported by a trailing `adapters/todo-md` bundle.
  - Default package rule shorthand (`rule <owner>/<repo>[@<ref>]`): mirror `bundle <owner>/<repo>` by enabling `allow_repo_shorthand=True` for `rule` targets without `:`, resolving in order: (1) `agents/<repo>.md` (or `agents/<repo>/<repo>.md`), (2) `agents/default.md` (or `agents/default/default.md`), (3) the sole rule in `agents/*.md` when the package contains exactly one rule (`len(rules_dict) == 1`), returning its canonical rule ID `<owner>/<repo>:<rule_key>` (e.g. `rule vitalio/todo-md` -> `vitalio/todo-md:todo`) and reusing the already-piped upstream rule body from `up_groups["rules"]` when that canonical ID is present in piped stdin.
  - Two-layer `===== Rules =====` cache stratification in `build_bundle()`: partition collected rules into Layer 1 (role- and session-invariant rules from `.context.bundle` whose condition chain and template placeholders do not reference dynamic session/pipeline variables such as `role`, `piped`, `upstream.vars` / `todo_md.*`, `export` variables, or CLI overrides — e.g. unconditional `core/*`, `os/*`, `vcs/*`, `vitalio/todo-md:todo` via `adapters/todo-md`, `collab/commits`, and `release/*` rules — followed by the embedded `vitalio/context-bundle:context` rule) and Layer 2 (session- and role-conditional rules from `.context.bundle` in declaration order, followed by any remaining unreferenced upstream piped `up_groups["rules"]`).
- Update `README.md` and `AGENTS.md`, and add unit tests in `tests/test_bundle.py` and `tests/test_rules_engine.py` covering `rule <owner>/<repo>` shorthand resolution, `adapters/todo-md` placed after `core`, variable precedence across CLI / root `let` / multiple child `export` bundles, and Layer 1 before Layer 2 rule stratification across role switches and piped vs. non-piped runs.

# ✅ [DONE] F38: Enforce workdir boundary on root .context.bundle file directives and require trust for non-builtin shell commands — *2026-11-25, Enforced Workdir boundary on root .context.bundle file directives and added (realpath, sha256) trust enforcement for non-builtin shell commands (v0.21.0).*

- Bump: `MINOR`
- Close two untrusted-repository security gaps when running `context` in a directory with a repository-local `.context.bundle` (`src/bundle.py`, `src/includes.py`, `src/cli.py`, `src/header.py`):
  - Workdir boundary on root `file` directives: always pass `root_dir=spec_dir` to `_expand_include()` for all `file` directives inside `.context.bundle` (not only external child bundles), preventing a malicious root `.context.bundle` from reading sensitive files outside the repository (such as `file ~/.ssh/id_rsa` or `file ../../secrets.env`) while keeping explicit user CLI file arguments (`context /path/to/file`) unrestricted.
  - Safe default command policy and explicit trust for root `.context.bundle` shell execution: allow built-in read-only inspection commands (`context --tree`, read-only `git status`/`branch`/`log`/`diff`/`rev-parse`, and read-only `todo` queries) in root `.context.bundle` out of the box with zero friction, but require explicit repository trust before executing arbitrary shell commands (`cmd ...`, `let x=$(...)`, `file $(...)`) or custom `allow <bin...>` grants from a root `.context.bundle`.
  - Persist trusted `(realpath, sha256)` entries in `${XDG_STATE_HOME:-~/.local/state}/context-bundle/trusted.json` (`0600` permissions) managed via `context --trust [--revoke | --list]` (or an interactive `/dev/tty` confirmation prompt when a TTY is attached, failing closed in non-interactive pipes with an actionable error message instructing the user to inspect `.context.bundle` and run `context --trust`).
  - Document the root `.context.bundle` trust and `Workdir` boundary model in `README.md`, `AGENTS.md`, and `src/header.py` (`--help`), and add unit tests in `tests/test_bundle.py`, `tests/test_includes.py`, and `tests/test_cli.py`.

# ✅ [DONE] F37: Sync README.md starter .context.bundle example with current agents-rules taxonomy and tighten Quick Start — *2026-11-24, Synced starter .context.bundle example with current agents-rules taxonomy and moved slice/bundle behavior details out of Quick Start into reference sections*

- Update the starter `.context.bundle` example in `README.md` to use current `vitalio/agents-rules` bundle/rule identifiers (`bundle vitalio/agents-rules:adapters/todo-md`, `bundle vitalio/agents-rules:stack/python py_min=3.9`, `bundle vitalio/agents-rules:stack/cli`, `rule vitalio/agents-rules:release/semver`) instead of removed `adapters/todo_md` and `stack/python-cli`.
- Move detailed slice merge and `context bundle` behavioral edge cases out of `Quick Start` into the reference sections below so `Quick Start` stays concise and scenario-focused per `agents/stack/cli/docs.md`.

# ✅ [DONE] F34: Restructure README.md with progressive disclosure, scenario-based Quick Start, and CLI Reference tables — *2026-11-23, Restructured README.md with progressive disclosure, scenario-based Quick Start, and CLI Reference tables; aligned context -h description column across all sections.*

- Depends on: F36
- Rewrite README.md following progressive-disclosure and CLI documentation conventions:
  - Header & intro: '# context-bundle (`context`)' with a bold one-line tagline, a concise 3-4 line overview, and a short '## Key Features' bullet list (moving low-level stdin preamble, FIFO exit-2, and namespace normalization details out of the top intro into the protocol section).
  - '## Quick Installation': curl | sh install, custom --name / --dir options, and --check-update / --update / --uninstall.
  - '## Quick Start': replace the monolithic 22-command 'CLI Usage' dump with short, scenario-grouped examples (initializing and building a bundle / piping with todo and run, passing prompts and file globs or line-range slices, rendering standalone bundles/rules and listing catalogs, and printing token-budgeted repository file trees).
  - '## CLI Reference': structured tables/lists for Commands, Options, and Environment variables in full sync with 'context -h'.
  - '## .context.bundle Format & 9-Keyword Directive Reference': starter example and the 9-keyword directive specification (bundle, rule, file, cmd, prompt, let, export, if/else if/else, allow).
  - '## Bundle Output Protocol & Piped Input': Key: Value preamble and Bundle-* headers, canonical 4-kind JSON fragment markers (rule, file, cmd, prompt), --plain mode, piped stdin / Bundle-Name producer namespace normalization (<owner>.<repo>.<key> and <repo>.<key>), chain provenance, and embedded rule.
  - '## Package Cache' and '## License'.

- Align the description column in `context -h` (`src/core.py:usage_text()`) at a single shared column across all tabular sections (`Usage:`, `Options:`, `Bundle Output Protocol:`, `Environment:`) per `vitalio/agents-rules:stack/cli/help`.

# ✅ [DONE] F36: Show total byte size and large/dense file sizes in context --tree — *2026-11-23, Added total size summary and large/dense file byte sizes to context --tree*

- Always include total size in the `# Total: <N> files, <M> lines (<size>)` summary line of `context --tree` (formatted compactly in `B` / `KB` / `MB`).
- For individual files in the tree, keep the compact `(<N>L)` label by default and append byte size `(<N>L, <X>K)` only when a file is at least `16 KB` (`16384` bytes) or has an average line length above `120` bytes/line (catching minified/dense single-line files without cluttering small source files).
- Add unit tests in `tests/test_tree.py` and update `README.md` / `AGENTS.md` if needed.

# ✅ [DONE] F27: Rename project to context-bundle and CLI utility to context — *2026-11-23, Renamed repository to vitalio/context-bundle and CLI utility to context with qualified Bundle-Name producer namespaces, CONTEXT_BUNDLE_* environment variables, automatic cache/binary migration, and --uninstall*

- Depends on: F15, F33
- Rename project/repository references from `agents_bundle` to `context-bundle` (`vitalio/context-bundle`) and CLI entrypoint to `context` per `todo_flow:D8` (`docs/adr/0004-ecosystem-rename-and-cutover.md`):
  - Emit `Bundle-Name: vitalio/context-bundle`, embedded rule `agents/context.md` (`{cmd:context}`, `id: "vitalio/context-bundle:context"`, `chain: ["vitalio/context-bundle"]`), and repo marker `# context-bundle-repo: vitalio/context-bundle`.
  - Support qualified `Bundle-Name: <owner>/<repo>` on `stdin` in `src/upstream.py`: normalize `/` -> `.` and `-` -> `_` so producer headers populate both `<owner>.<repo>.<key>` (`vitalio.todo_md.task`) and the unambiguous short alias `<repo>.<key>` (`todo_md.task`), omitting the short alias only if two producers in the same pipeline share `<repo>` under different owners.
  - Switch environment variables to `CONTEXT_BUNDLE_*` (`CONTEXT_BUNDLE_VARS`, `CONTEXT_BUNDLE_PLAIN`, `CONTEXT_BUNDLE_CACHE_DIR`, `CONTEXT_BUNDLE_LOCAL_PKG_DIR`, `CONTEXT_BUNDLE_SHELL`, `CONTEXT_BUNDLE_UPDATE_URL`, and installer `CONTEXT_BUNDLE_NAME`, `CONTEXT_BUNDLE_INSTALL_DIR`).
  - Migrate package cache in `cache_dir_path()` and `install.sh`: atomically rename `~/.cache/agents_bundle` -> `~/.cache/context-bundle` and prune obsolete `packages/vitalio/{agents_bundle,run_block,todo_md}` clones.
  - Replace any existing `agents_bundle` binary in `$INSTALL_DIR` during `install.sh` / `--update`, add `--uninstall` to `context` and `install.sh`, rename the GitHub repository `vitalio/agents_bundle` -> `vitalio/context-bundle` and update local `git remote` URL, update `cmd agents_bundle --tree` -> `cmd context --tree` across workspace `.context.bundle` files so subsequent sessions do not invoke removed `agents_bundle`, and run `python3 build.py && ./install.sh --yes`.
- Acceptance criteria: GitHub repo is `vitalio/context-bundle`, `build.py` outputs `context`, `install.sh` installs `context` and removes legacy `agents_bundle`, `--uninstall` removes `context` and `~/.cache/context-bundle`, and `python3 -m unittest discover -s tests` passes.

# ✅ [DONE] F33: Remove transitional .bundle directives, legacy package layouts, and legacy fragment kind aliases — *2026-11-23, Removed transitional .bundle directive aliases, legacy package directories, and legacy upstream fragment kind aliases*

- Depends on: F15
- Remove transitional `.bundle` directive aliases (`ruleset`, `include`, `$`, `!`, `var`, `expose`) and legacy `[if ...]` / `[/if]` / `[endif]` conditional syntax (`_preprocess_legacy_if_lines`, `IF_PREFIX_RE`, `[if ...]` in trace labels) from `src/bundle.py`, `src/rules_engine.py`, and `src/cli.py`.
- Remove legacy package directory resolution (`rules/`, `src/rules/`, `rulesets/`, `src/rulesets/`, `bundles/`, `src/bundles/`) and `*.ruleset` file discovery from `src/rules_engine.py`, keeping only the canonical `agents/` directory with `.bundle` and `.md` files.
- Remove legacy upstream fragment kind aliases (`include`, `task`, `context`) from `src/upstream.py` (`PROMPT_KINDS`, `_KIND_NORMALIZATION`, `_FRAGMENT_GROUPS`), keeping only the 4 canonical ADR-0003 fragment kinds (`rule`, `file`, `cmd`, `prompt`).
- Strip historical `- Role:` and `- Target files:` lines from `TODO_ARCHIVE.md`.
- Acceptance criteria: only the 9 canonical `.bundle` keywords (`bundle`, `rule`, `file`, `cmd`, `prompt`, `let`, `export`, `if`/`else if`/`elif`/`else`, `allow`), canonical `agents/` layout, and 4 fragment kinds (`rule`, `file`, `cmd`, `prompt`) remain; `AGENTS.md`, `README.md`, `--help`, and `tests/test_*.py` are updated; `./build.py` and `python3 -m unittest discover -s tests` pass.

# ❌ [CANCELED] L1: Clarify ~1000-line module size guideline as pragmatic recommendation rather than hard split trigger — *moved to todo_flow*

- Observed problem: the modular cohesion rule wording ('split any module that exceeds about 1000 lines') gets interpreted by planning and worker sessions as a hard line-count cap, prompting artificial relocation of cohesive helpers across modules just to keep `wc -l` below 1000.
- Context & impact: splitting or moving functions across modules solely to satisfy a line threshold when a module remains cohesive and focused on a single architectural layer hurts locality and maintainability.

# ✅ [DONE] F15: Unify ruleset into .bundle, implement Bundle-Name producer namespaces, Python-indented if/let/export/file/cmd language, and drop Windows support — *2026-11-23, Unified ruleset into .bundle, implemented Bundle-Name producer namespaces, 9-keyword Python-indented .bundle language, canonical 4-kind fragments, .ctx.bundle support, and dropped Windows support*

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

# ✅ [DONE] F10: Enforce command allowlist policy in .agents_bundle for external bundles — *2026-11-23, Enforce command allowlist and workspace-root include boundary for external bundles*

- Depends on: F13, F7
- Support an explicit allowlist directive in root `.agents_bundle` (e.g. `allow <cmd1> <cmd2> ...` or per-bundle `bundle <pkg> allow=...`) defining which executables external bundles are permitted to run via `$` commands and `var x=$(...)` subshells in `parse_spec()` and `build_bundle()` (`src/bundle.py:167-566`).
- Statically inspect all parsed commands from included bundles before executing any shell command; fail fast with a clear error naming the blocked command and originating bundle if any command executable is not in the user's allowlist.
- Restrict `include` paths from external bundles in `_expand_include()` (`src/bundle.py:313-360`) to files inside the repository root (`spec_dir`) so external bundles cannot read arbitrary host paths outside the workspace.

# ✅ [DONE] F7: Support agents/ package directory, custom relative paths, and @ref local-resolve fix — *2026-11-22*

- Depends on: F13, F30
- Standardize `agents/` as the canonical package directory for rules (`.md`) and bundles (`.bundle`) across repositories (supporting logical domain subdirectories, `owner/repo` -> `agents/<repo>.bundle` or `agents/default.bundle`, and `owner/repo:domain` -> `agents/domain/domain.bundle`) while keeping fallback compatibility with legacy root `rules/`, `rulesets/`, `bundles/` and `src/` paths in `_load_package_from_dir()` and `resolve_bundle_source()` in `src/rules_engine.py:175-415`.
- Support explicit relative file paths inside a package (`owner/repo[@ref]:path/to/file`) and local relative paths (`./...`, `../...`).
- Fix `_ensure_remote_package()` in `src/rules_engine.py:242-295` so explicit `@<ref>` on `vitalio/*` packages fetches the requested ref instead of returning the unpinned local working tree.
- Keep `agents/agents_bundle.md`, `AGENTS.md`, `README.md`, `src/header.py`, and unit tests in `tests/test_rules_engine.py:1-323` and `tests/test_bundle.py:1-260` in sync.

# ✅ [DONE] F32: Render table-driven -h/--help output wrapped to <= 100 columns per stack/cli — *2026-11-22*

- Replace static `USAGE_TEMPLATE.format(...)` in `src/header.py` and `usage_text()` (`src/core.py`) with structured table-driven help rendering (`HELP_MAX_WIDTH = 100`, `HELP_PROSE_WIDTH = 80`, `HELP_INDENT = 2`, `HELP_GAP = 2`, matching `todo_md` and `vitalio/agents-rules:stack/cli`).
- Measure the left column width after expanding `{prog}`, `{default_pkg}`, and `{cache_dir}` within each section (`Usage:`, `Options:`, `Bundle Output Protocol:`, `Environment:`) so all descriptions and wrapped continuation lines align to the same column and no line exceeds 100 columns.
- Rebuild `./agents_bundle` via `python3 build.py` and add unit test assertions in `tests/test_cli.py` verifying that every line of `agents_bundle -h` / `--help` is `<= 100` columns and section description columns are aligned.

# ✅ [DONE] B2: Normalize upstream rule fragments through _parse_md_text() and _render_rule_vars() — *2026-11-22*

- In `build_bundle_from_spec()` (`src/bundle.py:345-415`), when ingesting upstream `kind: "rule"` fragments from `up_groups["rules"]`, pass each upstream rule body through `_parse_md_text(up_body, up_uid)[1]` and `_render_rule_vars(..., {**builtin_vars(spec_dir, piped=piped), **effective_cli_vars}).strip()` before appending to `pending_rules` (matching the processing applied to `EMBEDDED_RULE_NAME` and `.agents_bundle` rules):
  - Strips any leading `# Description:` metadata line from upstream tool rules (such as `todo_md:todo_md`).
  - Evaluates `[if ...]` conditional blocks/lines and `{cmd:...}` / template variable substitutions against the active session variables (`role`, `task`, etc.).
  - Skips appending the upstream rule if the rendered body is empty after conditional filtering.
- Add unit tests in `tests/test_upstream.py` verifying that upstream `rule` fragments have `# Description:` stripped, `[if role=...]` blocks filtered against `Role:` preamble headers or CLI `role=...` overrides, and `{cmd:...}` placeholders expanded.

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
