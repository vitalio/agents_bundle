# 🎯 [NEXT] F36: Show total byte size and large/dense file sizes in context --tree

- Always include total size in the `# Total: <N> files, <M> lines (<size>)` summary line of `context --tree` (formatted compactly in `B` / `KB` / `MB`).
- For individual files in the tree, keep the compact `(<N>L)` label by default and append byte size `(<N>L, <X>K)` only when a file is at least `16 KB` (`16384` bytes) or has an average line length above `120` bytes/line (catching minified/dense single-line files without cluttering small source files).
- Add unit tests in `tests/test_tree.py` and update `README.md` / `AGENTS.md` if needed.

# 🎯 [NEXT] F34: Restructure README.md with progressive disclosure, scenario-based Quick Start, and CLI Reference tables

- Depends on: F36
- Rewrite README.md following progressive-disclosure and CLI documentation conventions:
  - Header & intro: '# context-bundle (`context`)' with a bold one-line tagline, a concise 3-4 line overview, and a short '## Key Features' bullet list (moving low-level stdin preamble, FIFO exit-2, and namespace normalization details out of the top intro into the protocol section).
  - '## Quick Installation': curl | sh install, custom --name / --dir options, and --check-update / --update / --uninstall.
  - '## Quick Start': replace the monolithic 22-command 'CLI Usage' dump with short, scenario-grouped examples (initializing and building a bundle / piping with todo and run, passing prompts and file globs or line-range slices, rendering standalone bundles/rules and listing catalogs, and printing token-budgeted repository file trees).
  - '## CLI Reference': structured tables/lists for Commands, Options, and Environment variables in full sync with 'context -h'.
  - '## .context.bundle Format & 9-Keyword Directive Reference': starter example and the 9-keyword directive specification (bundle, rule, file, cmd, prompt, let, export, if/else if/else, allow).
  - '## Bundle Output Protocol & Piped Input': Key: Value preamble and Bundle-* headers, canonical 4-kind JSON fragment markers (rule, file, cmd, prompt), --plain mode, piped stdin / Bundle-Name producer namespace normalization (<owner>.<repo>.<key> and <repo>.<key>), chain provenance, and embedded rule.
  - '## Package Cache' and '## License'.

- Align the description column in `context -h` (`src/core.py:usage_text()`) at a single shared column across all tabular sections (`Usage:`, `Options:`, `Bundle Output Protocol:`, `Environment:`) per `vitalio/agents-rules:stack/cli/help`.

# ⚪ [NEW] F35: Add --compile flag to compile baseline AGENTS.md from .context.bundle

- Depends on: F36 -> F34
- Implement `context --compile` so `context --compile > AGENTS.md` renders a static baseline `AGENTS.md` from the project's `.context.bundle` (and local `agents/*.md` rules) without role-specific or session-specific runtime headers.
