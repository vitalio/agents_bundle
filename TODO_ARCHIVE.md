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
