# ⚪ [NEW] F5: Emit a single Rules section before commands and group bundles at top

- Collect all rule lines from bundle, ruleset, and rule directives into a single ===== Rules ===== section before executing and rendering any $ <cmd> sections so bundles containing commands never split ===== Rules ===== into multiple sections.
- Update the agents_bundle --init template and repository .agents_bundle to group all bundle directives together at the top before ruleset, rule, and $ <cmd> directives.

# ⚪ [NEW] F6: Add bundle CLI subcommand to render and inspect .bundle files

- Add 'agents_bundle bundle <pkg>[:<name>] [k=v]' CLI subcommand (symmetric with 'ruleset' and 'rule') to render a bundle from the command line.
- Keep src/header.py (--help), src/rules/agents_bundle.md, README.md, and tests in sync.
