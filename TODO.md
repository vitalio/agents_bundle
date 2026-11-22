# ⚪ [NEW] F27: Rename project to ctx-bundle and CLI utility to ctx

- Depends on: F15
- Rename project/repository references from `agents_bundle` to `ctx-bundle` and CLI entrypoint from `agents_bundle` to `ctx` (with `.ctx.bundle` as root bundle config and agreed deprecation aliases/symlinks and env-var updates from `todo_flow:D8` and ADR 0003).
- Remove transitional `.bundle` migration aliases (`ruleset` / `*.ruleset`, `include`, `$`, `var`, `expose`, and `[if ...]` / `[/if]`) once all workspace and `agents-rules` bundles have migrated in `todo_flow:F4`.
- Acceptance criteria: `build.py` outputs `ctx`, `install.sh` installs `ctx` (plus any agreed compatibility alias), legacy `ruleset` / directive aliases are removed, `--help`/rules/docs/tests reflect `ctx-bundle` and `ctx`, and `python3 -m unittest discover -s tests` passes.
- Target files: `build.py`, `install.sh`, `src/cli.py`, `src/header.py`, `src/bundle.py`, `src/rules_engine.py`, `src/upstream.py`, `src/tree.py`, `agents/agents_bundle.md`, `.agents_bundle`, `AGENTS.md`, `README.md`, `VERSION`, `tests/helpers.py`, `tests/test_*.py`, and `.github/`.
