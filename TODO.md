# ⚪ [NEW] F27: Rename project to ctx-bundle and CLI utility to ctx

- Depends on: F15
- Rename project/repository references from `agents_bundle` to `ctx-bundle` and CLI entrypoint from `agents_bundle` to `ctx` (with `.ctx.bundle` as root bundle config and agreed deprecation aliases/symlinks and env-var updates from `todo_flow:D8` and ADR 0003).
- Remove transitional `.bundle` migration aliases (`ruleset` / `*.ruleset`, `include`, `$`, `var`, `expose`, and `[if ...]` / `[/if]`) once all workspace and `agents-rules` bundles have migrated in `todo_flow:F4`.
- Acceptance criteria: `build.py` outputs `ctx`, `install.sh` installs `ctx` (plus any agreed compatibility alias), legacy `ruleset` / directive aliases are removed, `--help`/rules/docs/tests reflect `ctx-bundle` and `ctx`, and `python3 -m unittest discover -s tests` passes.
- Target files: `build.py`, `install.sh`, `src/cli.py`, `src/header.py`, `src/bundle.py`, `src/rules_engine.py`, `src/upstream.py`, `src/tree.py`, `agents/agents_bundle.md`, `.agents_bundle`, `AGENTS.md`, `README.md`, `VERSION`, `tests/helpers.py`, `tests/test_*.py`, and `.github/`.

# ⚪ [NEW] L1: Clarify ~1000-line module size guideline as pragmatic recommendation rather than hard split trigger

- Observed problem: the modular cohesion rule wording ('split any module that exceeds about 1000 lines') gets interpreted by planning and worker sessions as a hard line-count cap, prompting artificial relocation of cohesive helpers across modules just to keep `wc -l` below 1000.
- Context & impact: splitting or moving functions across modules solely to satisfy a line threshold when a module remains cohesive and focused on a single architectural layer hurts locality and maintainability.
