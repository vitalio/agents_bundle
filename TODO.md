# ⚪ [NEW] F5: Emit a single Rules section before commands and group bundles at top

- Collect all rule lines from bundle, ruleset, and rule directives into a single ===== Rules ===== section before executing and rendering any $ <cmd> sections so bundles containing commands never split ===== Rules ===== into multiple sections.
- Update the agents_bundle --init template and repository .agents_bundle to group all bundle directives together at the top before ruleset, rule, and $ <cmd> directives.
