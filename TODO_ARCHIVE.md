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
