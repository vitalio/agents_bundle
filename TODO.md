# 🎯 [NEXT] F33: Remove transitional .bundle directives, legacy package layouts, and legacy fragment kind aliases

- Depends on: F15
- Remove transitional `.bundle` directive aliases (`ruleset`, `include`, `$`, `!`, `var`, `expose`) and legacy `[if ...]` / `[/if]` / `[endif]` conditional syntax (`_preprocess_legacy_if_lines`, `IF_PREFIX_RE`, `[if ...]` in trace labels) from `src/bundle.py`, `src/rules_engine.py`, and `src/cli.py`.
- Remove legacy package directory resolution (`rules/`, `src/rules/`, `rulesets/`, `src/rulesets/`, `bundles/`, `src/bundles/`) and `*.ruleset` file discovery from `src/rules_engine.py`, keeping only the canonical `agents/` directory with `.bundle` and `.md` files.
- Remove legacy upstream fragment kind aliases (`include`, `task`, `context`) from `src/upstream.py` (`PROMPT_KINDS`, `_KIND_NORMALIZATION`, `_FRAGMENT_GROUPS`), keeping only the 4 canonical ADR-0003 fragment kinds (`rule`, `file`, `cmd`, `prompt`).
- Strip historical `- Role:` and `- Target files:` lines from `TODO_ARCHIVE.md`.
- Acceptance criteria: only the 9 canonical `.bundle` keywords (`bundle`, `rule`, `file`, `cmd`, `prompt`, `let`, `export`, `if`/`else if`/`elif`/`else`, `allow`), canonical `agents/` layout, and 4 fragment kinds (`rule`, `file`, `cmd`, `prompt`) remain; `AGENTS.md`, `README.md`, `--help`, and `tests/test_*.py` are updated; `./build.py` and `python3 -m unittest discover -s tests` pass.

# ⚪ [NEW] F27: Rename project to ctx-bundle and CLI utility to ctx

- Depends on: F15, F33
- Rename project/repository references from `agents_bundle` to `ctx-bundle` and CLI entrypoint from `agents_bundle` to `ctx` (with `.ctx.bundle` as root bundle config and agreed deprecation aliases/symlinks and env-var updates from `todo_flow:D8` and ADR 0003).
- Acceptance criteria: `build.py` outputs `ctx`, `install.sh` installs `ctx` (plus any agreed compatibility alias), `--help`/rules/docs/tests reflect `ctx-bundle` and `ctx`, and `python3 -m unittest discover -s tests` passes.
