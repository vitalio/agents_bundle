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
  `prompt`, `[if ...]`, and `$` directives), resolves `work_dir` from `-C/--dir`
  or a piped `Workdir:` preamble, emits `Workdir: <path>` in the bundle header,
  and assembles the context bundle to `stdout`.
- `src/rules/agents_bundle.md` & `src/bundles/agents_bundle.bundle` — agent
  instructions and conditional rule catalog for `bundle vitalio/agents_bundle`.
- `src/cli.py` — CLI entrypoint, subcommand routing, and self-update
  (`--update`, `--check-update`).

## Bundle Output Protocol

- Header visibility (`Bundle-*`): Emit `Bundle-Boundary: <nonce>` and
  `Bundle-Expose: Role, Task` (extensible via `expose`) by default so
  downstream runners (`run_block`) keep transport headers in session metadata
  while forwarding exposed headers into the final prompt header.
- Fragment markers: Wrap emitted rules, commands (`via`, `rc`, `ms`), included
  files, and prompts in `<!-- bundle:<nonce>:part {...} -->` and
  `<!-- bundle:<nonce>:end -->` JSON markers using neutral `kind`, `id`/`name`,
  `group`, `via`, `rc`, and `ms` fields without hardcoding `run_block`
  internals.
- Plain output (`--plain`): Omit transport `Bundle-*` headers and fragment
  markers when pure Markdown/text output is requested.
