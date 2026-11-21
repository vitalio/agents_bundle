# `agents_bundle` — Project-Specific Agent Rules

Universal workflow, language, Git, SemVer, Python CLI, and single-file build
rules are loaded via `.agents_bundle`.

## Architecture & Module Boundaries

- `src/header.py` — CLI usage docstring (exposed as `USAGE_TEMPLATE`), the
  standard library imports shared by the assembled executable, and version
  constants.
- `src/core.py` — `prog_name()`, `cache_dir_path()`, and `usage_text()`
  helpers shared by all modules.
- `src/tree.py` — `agents_bundle --tree` token-budgeted repository file tree
  with `-x/--exclude`, `AGENTS.md` pinning, deep directory collapsing, and file
  list truncation.
- `src/rules_engine.py` — resolves flat rulesets, rules, and reusable bundles
  from `<owner>/<repo>[@<ref>][:<name>]`, local paths, or direct URLs
  (`http://`, `https://`, `file://`), and evaluates `[if ...]` conditions
  against `os`, `vcs`, and CLI `key=val` overrides.
- `src/bundle.py` — parses `.agents_bundle` (`ruleset`, `rule`, `bundle`,
  `expose`, `prompt`, `[if ...]`, and `$` directives), resolves `work_dir` from
  `-C/--dir` or a piped `Workdir:` preamble, handles `--plain` and
  `AGENTS_BUNDLE_PLAIN`, emits `Workdir: <path>` in the bundle header, and
  assembles the context bundle to `stdout`.
- `src/rules/agents_bundle.md` & `src/bundles/agents_bundle.bundle` — agent
  instructions and conditional rule catalog for `bundle vitalio/agents_bundle`.
- `src/cli.py` — CLI entrypoint, subcommand routing, and self-update
  (`--update`, `--check-update`).
- `tests/` — offline test suite split to mirror `src/`: `tests/helpers.py`
  (`AgentsBundleTestCase` in-process CLI runner and offline package fixtures),
  `tests/test_cli.py`, `tests/test_core.py`, `tests/test_tree.py`,
  `tests/test_rules_engine.py`, and `tests/test_bundle.py`.
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
  `Bundle-Boundary: <nonce>`, and `Bundle-Expose: Role, Task, Title` (extensible via
  `expose` or `AGENTS_BUNDLE_EXPOSE`) by default so downstream runners
  (`run_block`) keep transport headers in session metadata while forwarding
  exposed headers into the final prompt header.
- Fragment markers: Wrap emitted rules, commands (`rc`, `ms`), included files,
  and prompts in `<!-- bundle:<nonce>:part <json> -->` and
  `<!-- bundle:<nonce>:end -->` JSON markers using neutral `kind`, `id`/`name`,
  `chain` (`[]` at root/CLI or ordered inclusion path of bundle/ruleset
  specifiers), `rc`, and `ms` fields without hardcoding `run_block` internals.
- Plain output (`--plain`): Pass `--plain` or set `AGENTS_BUNDLE_PLAIN=1` to
  omit transport `Bundle-*` headers (`Bundle-Command`, `Bundle-Boundary`,
  `Bundle-Expose`) and JSON fragment markers when pure Markdown/text output is
  requested.
