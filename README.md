# context-bundle (`context`)

**Unix-style context bundler, rule/bundle engine, and token-budgeted repository file tree for AI coding agents on POSIX (`linux` and `macos`).**

`context` executes `.context.bundle` in the
target working directory, evaluates the 8-keyword `.bundle` directive language,
merges rules, files, command outputs, and prompts, and writes the assembled
context bundle strictly to `stdout` (with diagnostics on `stderr`) so it
composes cleanly in Unix pipelines.

## Key Features

- **Declarative 8-keyword `.bundle` language:** compose remote or local
  `bundle` and `rule` specs, include `file` globs and `path:START-END` slices,
  capture `cmd` outputs, append `prompt` text, manage `let` and `export`
  variables, branch with `if`/`else if`/`else`, and verify shell execution via
  unified `trusted.json` command-tree hashing.
- **Composable Unix pipeline protocol:** emit structured `Bundle-*` and
  exported `Key: Value` headers with 4-kind JSON fragment markers (`rule`,
  `file`, `cmd`, `prompt`), chain upstream tools such as `todo` and downstream
  runners such as `run`, or switch to pure Markdown/text via `--plain`.
- **Standalone bundle & rule inspection:** render remote or local bundles and
  rules directly from `agents/` without a local `.context.bundle`, and browse
  package catalogs and parameters via `context --list`.
- **Token-budgeted repository file tree (`--tree`):** print a compact tree with
  `AGENTS.md` pinning, `-x/--exclude` filtering, large/dense file byte sizes,
  automatic deep-directory collapsing, and total line/byte summaries.

## Quick Installation

Install on Linux or macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/vitalio/context-bundle/main/install.sh | sh
```

Install with a custom command name or target directory:

```bash
curl -fsSL https://raw.githubusercontent.com/vitalio/context-bundle/main/install.sh | sh -s -- --name ctx --dir ~/.local/bin
```

Check for updates, self-update in place, or uninstall:

```bash
context --update --check
context --update
context --uninstall
```

## Quick Start

Initialize a starter `.context.bundle`, build a bundle, or trust a repository spec with custom commands:

```bash
context --init
context > bundle.txt
context --trust
context role=work task=F1 > bundle.txt
```

Pipe task context from `todo` and hand off to `run` (or emit plain text):

```bash
todo F1 | context role=work > bundle.txt
todo F1 | context role=work | run
context --plain role=work > plain_bundle.txt
```

Include ad-hoc prompts, file globs, and 1-based inclusive line-range slices:

```bash
context -p "Fix issue #12" src/main.py > bundle.txt
context -p "Review parser" 'src/*.py' src/bundle.py:395-445 > bundle.txt
context -C /path/to/project role=review > bundle.txt
```

Render standalone bundles or rules and inspect available package catalogs:

```bash
context --list
context --bundle vitalio/agents-rules:default os=macos --plain
context --rule vitalio/agents-rules:release/single-file-build
context --update-cache
```

Print a token-budgeted repository file tree:

```bash
context --tree
context --tree -x bumps -x resolutions --max-lines 160 --max-tokens 1600
```

## CLI Reference

### Commands

| Command | Description |
| :--- | :--- |
| `context [k=v ...] [-p TEXT] [FILE ...]` | Build context bundle from `.context.bundle` to `stdout` (`stdin`: `Key: Value` preamble, task ID, or prompt; sets `piped=1` on prompt; empty piped `stdin` exits `2`) |
| `context --bundle <pkg>[:<name>] [k=v]` | Render a bundle's rules, files, commands, and prompts from `agents/` in the regular bundle format without `.context.bundle` (reads no `stdin`; honors `-C`, `-p`, `--plain`, `-v`, `--refresh`) |
| `context --rule <pkg>[:<name...>] [k=v]` | Render one or more rules from `agents/` (`<owner>/<repo>[@ref][:<name\|path>]`, `./path`, or URL) to `stdout` |
| `context --list \| -l [pkg]` | List bundles, rules, and built-in variables (default: local `agents/` and `.context.bundle`) |
| `context --update-cache` | Refresh cached git packages and URL files in `~/.cache/context-bundle` |
| `context --init [--force]` | Create a starter `.context.bundle` in the current directory |
| `context --trust [opts]` | Trust current `.context.bundle` or revoke/list entries in `${XDG_STATE_HOME:-~/.local/state}/context-bundle/trusted.json` (options: `[DIR]`, `--revoke`, `--list`, `-C DIR`) |
| `context --tree [DIR] [opts]` | Print token-budgeted repository file tree to `stdout` |
| `context --update [--check \| --force]` | Self-update `context` from GitHub (`vitalio/context-bundle`) or check for updates |
| `context --uninstall` | Remove installed `context` binary and package cache (`~/.cache/context-bundle`) |

### Options

| Option | Description |
| :--- | :--- |
| `-p, --prompt TEXT` | Append prompt text to the Prompt section |
| `FILE ...` | Extra files to include; accepts globs (`*`, `?`, `[`, `**`) and `path:START-END` or `path:LINE` slices (1-based, inclusive) |
| `-C, --dir DIR` | Set working directory (default: piped `Workdir:` or cwd) |
| `-v, --verbose` | Include rule provenance trace comments |
| `--plain` | Omit transport `Bundle-*` headers and JSON fragment markers |
| `--refresh` | Re-fetch each remote package or URL at most once per run |
| `-x, --exclude DIR` | Exclude directory name in `--tree` (repeatable) |
| `--max-lines N` | Maximum output lines for `--tree` (default: `160`) |
| `--max-tokens N` | Approximate token budget for `--tree` (default: `1600`) |
| `--check` | Check if a newer version is available without installing (with `--update`) |
| `--force` | Overwrite existing `.context.bundle` (`--init`) or force reinstall (`--update`) |
| `--revoke` | Revoke trust for current `.context.bundle` (with `--trust`) |
| `-l, --list` | List bundles/rules, or list trusted specs (with `--trust`) |
| `-V, --version` | Print version and exit `0` |
| `-h, --help` | Print usage and exit `0` |

### Environment

| Variable | Description |
| :--- | :--- |
| `CONTEXT_BUNDLE_VARS` | Default `key=val` pairs (overridden by CLI `key=val`) |
| `CONTEXT_BUNDLE_PLAIN` | Set to `1` to omit transport `Bundle-*` headers and fragment markers |
| `CONTEXT_BUNDLE_LOCAL_PKG_DIR` | Use a local package checkout instead of the cache |
| `CONTEXT_BUNDLE_CACHE_DIR` | Override the cache directory (default: `$XDG_CACHE_HOME/context-bundle` or `~/.cache/context-bundle`) |
| `XDG_STATE_HOME` | Base directory for `context-bundle/trusted.json` (default: `~/.local/state`) |
| `CONTEXT_BUNDLE_SHELL` | Override the shell executable used for `cmd` directives |
| `CONTEXT_BUNDLE_UPDATE_URL` | Override the remote script URL for `--update` |

## `.context.bundle` Format & 8-Keyword Directive Reference

Starter `.context.bundle` example:

```text
bundle vitalio/agents-rules:core
bundle vitalio/agents-rules:coding/python py_min=3.9
bundle vitalio/agents-rules:coding/cli
rule vitalio/agents-rules:release/semver
bundle vitalio/agents-rules:adapters/todo-md

file AGENTS.md
if role=work
    file {todo_md.files:}

cmd context --tree -x archive_dir
cmd git status -sb
if mode=summary
    cmd git shortlog -sn
    prompt Summarize recent repository activity.
```

`.context.bundle` and package `.bundle` files share
the same 8-keyword directive language; blank lines and `#` comments are
ignored, exported session variables resolve in a pre-pass (so `core` placed
before a trailing `adapters/todo-md` bundle still sees `role`, `task`, and
`title`), and `file` and `cmd` fragments assemble in exact top-down declaration
order:

- `bundle <owner>/<repo>[@<ref>][:<name|path>] [k=v ...]`
  (or a local path `./...`, `../...`, or URL) includes a composite bundle from
  `agents/` (`<repo>.bundle` or `default.bundle` for `<owner>/<repo>`,
  `<domain>.bundle`, `<domain>/<domain>.bundle`, or `<domain>/default.bundle`
  for `:<domain>`, or an explicit package-relative path); circular references
  fail fast.
- `rule <owner>/<repo>[@<ref>][:<name|path>...] [k=v ...]` (or a local path
  `./...`, `../...`, or URL) includes one or more atomic `.md` rule files from
  `agents/` (`<repo>.md`, `default.md`, or the sole rule in `agents/*.md` for
  package shorthand `<owner>/<repo>[@<ref>]`, or `<name>.md` / an explicit
  package-relative path).
- `file <path|glob|slice...>` includes space-separated repository files, globs
  (`*`, `?`, `[`, and recursive `**`; matches are sorted and `.git` and
  `__pycache__` are skipped), 1-based inclusive line-range slices
  `path:START-END` or `path:LINE`, or `$(<cmd>)` output. All `file` directives
  in root `.context.bundle` and nested bundles are restricted to the repository
  `Workdir` boundary (`spec_dir`), rejecting paths, globs, or symlinks that
  resolve outside the repository while keeping explicit CLI file arguments
  (`context /path/to/file`) unrestricted. An argument naming an existing file
  is always included whole; a slice is emitted as a
  `===== $ sed -n 'START,ENDp' <path> =====` section with fragment name
  `<path>:START-END`, and overlapping or whole-file spans are merged at first
  occurrence. Empty `file` after variable expansion (such as
  `file {todo_md.files:}` when unset) is a no-op.
- `cmd <shell command>` runs a command in `Workdir` and includes its output.
  Every command in `cmd`, `let <k>=$(<cmd>)`, or `file $(<cmd>)` (including
  `context --tree`, across the root spec, local child bundles, and referenced
  external bundles) requires the root `.context.bundle` `(realpath, sha256)`
  command-tree digest to be trusted in
  `${XDG_STATE_HOME:-~/.local/state}/context-bundle/trusted.json` (`0600`) via
  `context --trust`, `context --init`, or interactive `/dev/tty` `[y/N]`
  confirmation displaying the pending shell commands (failing closed in
  non-interactive runs while keeping untrusted specs strictly declarative).
- `prompt <text>` appends text to the Prompt section.
- `let <name>=<value>` or `let <name>=$(<cmd>)` sets a lexically scoped
  bundle-local variable (set-if-unset; passed down to child `rule` and `bundle`
  invocations, never leaking upward to parent/sibling bundles or output
  preamble headers).
- `export <name...>` promotes variables to session scope in a pre-pass before
  content collection (precedence: CLI `key=val` / `CONTEXT_BUNDLE_VARS` > root
  `.context.bundle` `let` and inline `bundle ... key=val` > child bundle
  `export` in top-down first-non-empty-writer order > child bundle-local `let`
  defaults) and emits them as capitalized `Key: Value` output preamble headers
  when non-empty.
- `if <cond>`, `else if <cond>` (synonym `elif <cond>`), `else` guard 4-space
  Python-style indented blocks without trailing colons or `endif`. Variable
  names in `if`, `let`, `export`, and `{name:default}` support dot-separated
  producer namespaces (`<owner>.<repo>.<key>` and `<repo>.<key>`).

## Bundle Output Protocol & Piped Input

`context` outputs a `Key: Value` header block separated by a blank line from
the assembled body sections (`===== Rules =====`,
`===== $ cat <file> =====` / `===== $ <cmd> =====` in declaration order, and
`===== Prompt =====`):

- **Transport and exported headers:** By default, the header block starts with
  `Bundle-Command`, `Bundle-Name: vitalio/context-bundle`,
  `Bundle-Boundary: <nonce>` (a per-run hex token), and `Bundle-Protocol: 1`,
  followed by any non-empty variables explicitly promoted via `export <key...>`
  and `Workdir: <path>`. Unexported variables stay internal to bundle execution
  and never appear in the output preamble.
- **Canonical 4-kind JSON fragment markers:** Each emitted rule, file section,
  command section, and prompt block is wrapped in single-line HTML comment
  markers keyed by the run nonce:

  ```text
  <!-- bundle:<nonce>:part {"kind": "cmd", "name": "git status -sb", "chain": [], "rc": 0, "ms": 8} -->
  ===== $ git status -sb =====
  ## main...origin/main
  <!-- bundle:<nonce>:end -->
  ```

  Marker payloads use the 4 canonical `kind` values (`rule`, `file`, `cmd`,
  `prompt`), `id` (for `rule`) or `name` (for `file` and `cmd`), `chain` (`[]`
  for root directives and CLI inputs, or ordered inclusion path of bundle
  specifiers), and `rc` / `ms` (for `cmd`).
- **Plain output (`--plain`):** Pass `--plain` or set `CONTEXT_BUNDLE_PLAIN=1`
  to omit transport `Bundle-*` headers and JSON fragment markers when plain
  Markdown/text output is requested.
- **Piped `stdin` preambles, producer namespaces, and empty FIFO guard:** When
  `stdin` is piped, leading `Key: Value` preamble headers (terminated by a
  blank line or EOF) are parsed automatically: `Workdir:` selects the working
  directory unless overridden by `-C`/`--dir`, and when
  `Bundle-Name: <owner>/<repo>` (or `<producer>`) is present, `/` is normalized
  to `.` and `-` to `_` so non-transport headers populate both
  `<owner>.<repo>.<key_lower>` (for example `vitalio.todo_md.task`) and the
  unambiguous short alias `<repo>.<key_lower>` (`todo_md.task`,
  `todo_md.prefix`, `todo_md.status`, `todo_md.title`, `todo_md.files`,
  `todo_md.role`) while rejecting duplicate producer names in the same
  pipeline. A single-token body sets `task=<ID>` (or `<producer>.task=<ID>`),
  any remaining body text is prepended to the prompt, and built-in `piped=1` is
  exposed when `stdin` prompt text is present so bundles can guard duplicate
  output with `if piped!=1`. When `stdin` is an actual pipe (FIFO) that
  delivers empty input, `context` writes an error to `stderr` and exits `2`
  before running any directives; non-FIFO non-TTY `stdin` such as `/dev/null`
  is still accepted.
- **Piped bundles (`context-bundle-protocol` v1):** When `stdin` declares
  `Bundle-Boundary: <nonce>`, the upstream bundle is unpacked instead of being
  treated as plain prompt text, and `Bundle-Command` is chained as
  `<upstream> | <this command>`. `rule` fragments are merged and deduplicated
  by `id`; `file` fragments are merged with bundle and CLI files at first
  occurrence (where a whole-file span absorbs any slice of the same file and
  overlapping slices become one slice); `prompt` fragments are re-wrapped with
  the new boundary inside the Prompt section with their metadata preserved.
- **Chain provenance:** Fragments from `.context.bundle`
  (and nested bundles) carry `chain` starting with the root spec filename;
  piped upstream fragments keep their own chain, and CLI file and `-p`
  arguments use `[]`.
- **Two-layer rule cache stratification & embedded rule:** `===== Rules =====`
  partitions collected rules into Layer 1 (role- and session-invariant rules
  from `.context.bundle` in declaration order — including any package rule whose
  canonical ID matches a piped upstream rule body — followed by the embedded
  `vitalio/context-bundle:context` rule with chain
  `["vitalio/context-bundle"]`) and Layer 2 (session- and role-conditional rules
  from `.context.bundle` in declaration order, followed by any remaining
  unreferenced upstream piped rules). `--init` creates a starter
  `.context.bundle` that uses `file AGENTS.md`.

## Package Cache

Remote packages are cloned into `<cache_dir>/packages` and URL files are saved
in `<cache_dir>/urls` (`CONTEXT_BUNDLE_CACHE_DIR` overrides the default
`~/.cache/context-bundle` location). `--refresh` re-fetches each remote package or URL
at most once per run. `--update-cache` fetches and hard-resets every cached git
package to its remote ref and re-downloads every cached URL file, printing one
status line per item (exit code `1` when any item fails). Set
`CONTEXT_BUNDLE_LOCAL_PKG_DIR` to use a local package checkout for unpinned
package references instead of the cache (explicit `@<ref>` package specs always
fetch the requested ref into `<cache_dir>/packages/<owner>/<repo>@<ref>`);
there is no implicit lookup in the home directory.

## License

[MIT](LICENSE) © 2026 [vitalio](https://github.com/vitalio)
