# `agents_bundle` — Project-Specific Agent Rules

Universal workflow, language, Git, SemVer, Python CLI, and single-file build rules are loaded via `.agents_bundle`.

## Architecture & Module Boundaries

- `src/header.py` — CLI usage docstring, standard library imports, and version constants.
- `src/tree.py` — `agents_bundle --tree` token-budgeted repository file tree with `-x/--exclude`, deep directory collapsing, and file list truncation.
- `src/rules_engine.py` — resolves flat presets and rules from `<owner>/<repo>[@<ref>]:<name>`, local paths, or direct URLs (`http://`, `https://`, `file://`), and evaluates `[if ...]` conditions against `os`, `vcs`, and CLI `key=val` overrides.
- `src/bundle.py` — parses `.agents_bundle` and assembles the context bundle to `stdout`.
- `src/cli.py` — CLI entrypoint, subcommand routing, and self-update (`--update`, `--check-update`).
