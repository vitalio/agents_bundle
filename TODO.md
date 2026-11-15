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

# ⚪ [NEW] F10: Enforce command allowlist policy in .agents_bundle for external bundles

- Support an explicit allowlist directive in root .agents_bundle (e.g. 'allow <cmd1> <cmd2> ...' or per-bundle 'bundle <pkg> allow=...') defining which executables external bundles are permitted to run via '$' commands and 'var x=$(...)' subshells.
- Statically inspect all parsed commands from included bundles before executing any shell command; fail fast with a clear error naming the blocked command and originating bundle if any command executable is not in the user's allowlist.
- Restrict 'include' paths from external bundles to files inside the repository root (spec_dir) so external bundles cannot read arbitrary host paths outside the workspace.
- Update src/bundle.py, src/header.py (--help), src/rules/agents_bundle.md, README.md, and unit tests in tests/test_agents_bundle.py.
