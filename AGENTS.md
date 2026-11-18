# `agents_bundle` — Project-Specific Agent Rules

Universal workflow, language, Git, SemVer, Python CLI, and single-file build
rules are loaded via `.agents_bundle`.

## Architecture & Module Boundaries

- `src/header.py` — CLI usage docstring, standard library imports, and version
  constants.
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
