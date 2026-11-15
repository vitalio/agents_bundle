# 🎯 [NEXT] F8: Support dynamic task resolution, task file auto-inclusion, and todo_md stdin pipeline in bundles

- Depends on: todo_md:F8
- Support dynamic variable resolution in `.bundle` / `.agents_bundle` (e.g. resolving `task` from the top `WIP`/`NEXT` task in `TODO.md` when `role=execute` or `role=work` is invoked without `task=<ID>`, or when task output is piped via `todo_md [<ID>] | agents_bundle | run_block`) so `Task: <ID>` is always emitted in the bundle header (`0.txt`).
- Support automatic inclusion of existing repository files referenced by the active `task=<ID>` (via `todo_md --files <ID>` or a bundle directive) alongside explicit `[file ...]` CLI arguments so execution sessions start with target files preloaded in `0.txt`.
- Update `src/rules/agents_bundle.md` (and `agents/rules/agents_bundle.md` per F7), `src/header.py`, `README.md`, and unit tests to document and test `todo_md | agents_bundle | run_block` and target-file preloading.

# ⚪ [NEW] F5: Emit a single Rules section before commands and group bundles at top

- Collect all rule lines from bundle, ruleset, and rule directives into a single ===== Rules ===== section before executing and rendering any $ <cmd> sections so bundles containing commands never split ===== Rules ===== into multiple sections.
- Update the agents_bundle --init template and repository .agents_bundle to group all bundle directives together at the top before ruleset, rule, and $ <cmd> directives.

# ⚪ [NEW] F6: Add bundle CLI subcommand to render and inspect .bundle files

- Add 'agents_bundle bundle <pkg>[:<name>] [k=v]' CLI subcommand (symmetric with 'ruleset' and 'rule') to render a bundle from the command line.
- Keep src/header.py (--help), src/rules/agents_bundle.md, README.md, and tests in sync.

# ⚪ [NEW] F7: Support agents/ package directory, custom relative paths, and @ref local-resolve fix

- Resolve package rules, rulesets, and bundles from agents/ (agents/rules/, agents/rulesets/, agents/bundles/ as well as flat agents/*.md, agents/*.ruleset, agents/*.bundle) while keeping fallback compatibility with root rules/, rulesets/, bundles/ and src/rules/, src/rulesets/, src/bundles/.
- Support explicit relative file paths inside a package (owner/repo[@ref]:path/to/file) and local relative paths (./..., ../...).
- Fix _ensure_remote_package so explicit @<ref> on vitalio/* packages fetches the requested ref instead of returning the unpinned local ~/repo working tree.
- Move src/rules/agents_bundle.md and src/bundles/agents_bundle.bundle into agents/ and keep AGENTS.md, README.md, src/header.py, and unit tests in sync.
