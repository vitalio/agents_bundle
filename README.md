# context-bundle (`context`)

**Unix-style context bundler, rule/bundle engine, and token-budgeted repository file tree for AI coding agents on POSIX (`linux` and `macos`).**

`context` executes `.context.bundle` (with fallback to `.agents_bundle`) in the
target working directory, evaluates the 9-keyword `.bundle` directive language,
merges rules, files, command outputs, and prompts, and writes the assembled
context bundle strictly to `stdout` (with diagnostics on `stderr`) so it
composes cleanly in Unix pipelines.

## Key Features

- **Declarative 9-keyword `.bundle` language:** compose remote or local
  `bundle` and `rule` specs, include `file` globs and `path:START-END` slices,
  capture `cmd` outputs, append `prompt` text, manage `let` and `export`
  variables, branch with `if`/`else if`/`else`, and enforce an external command
  `allow` list.
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
context --check-update
context --update
context --uninstall
```

## Quick Start

Initialize a starter `.context.bundle` and build a bundle:

```bash
context --init
context > bundle.txt
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

Extra file arguments and `file` directive items accept relative glob patterns
(`*`, `?`, `[`, and recursive `**`; matches are sorted and `.git` and
`__pycache__` are skipped) and 1-based inclusive line-range slices
`path:START-END` or `path:LINE`. A string that names an existing file is always
included whole. A slice is emitted as a
`===== $ sed -n 'START,ENDp' <path> =====` section with the fragment name
`<path>:START-END`, so multiple slices of one large file can be included.

Render standalone bundles or rules and inspect available package catalogs:

```bash
context --list
context bundle vitalio/agents-rules:default os=macos --plain
context rule vitalio/agents-rules:release/single-file-build
context --update-cache
```

`context bundle <pkg>[:<name>] [k=v]` renders a single bundle without requiring
a `.context.bundle` file: the bundle's rules, file sections, command sections,
and prompts are emitted in the regular bundle format. It accepts `k=v`
variables and the bundle options (`-C`/`--dir`, `-p`/`--prompt`, `--plain`,
`-v`/`--verbose`, `--refresh`, `allow=<cmd,...>`) but does not read `stdin`.

Print a token-budgeted repository file tree:

```bash
context --tree
context --tree -x bumps -x resolutions --max-lines 160 --max-tokens 1600
```

## CLI Reference

### Commands

| Command | Description |
| :--- | :--- |
| `context [k=v ...] [-p TEXT] [FILE ...]` | Build context bundle from `.context.bundle` (or `.agents_bundle`) to `stdout` (`stdin`: `Key: Value` preamble, task ID, or prompt; sets `piped=1` on prompt; empty piped `stdin` exits `2`) |
| `context bundle <pkg>[:<name>] [k=v]` | Render a bundle from `agents/` without `.context.bundle` (reads no `stdin`; honors `-C`, `-p`, `--plain`, `-v`, `--refresh`, `allow=<cmd,...>`) |
| `context rule <pkg>:<name...> [k=v]` | Render one or more rules from `agents/` (`<owner>/<repo>[@ref]:<name\|path>`, `./path`, or URL) to `stdout` |
| `context --list \| -l [pkg]` | List bundles, rules, and built-in variables (default: `vitalio/agents-rules`) |
| `context --update-cache` | Refresh cached git packages and URL files in `~/.cache/context-bundle` |
| `context --init [--force]` | Create a starter `.context.bundle` in the current directory |
| `context --tree [DIR] [opts]` | Print token-budgeted repository file tree to `stdout` |
| `context --update [--force]` | Self-update `context` from GitHub (`vitalio/context-bundle`) |
| `context --check-update` | Check if a newer version is available |
| `context --uninstall` | Remove installed `context` binary and package cache (`~/.cache/context-bundle`) |
| `context -V \| --version` | Print version and exit `0` |
| `context -h \| --help` | Print usage and exit `0` |

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
| `--force` | Overwrite existing `.context.bundle` (`--init`) or force reinstall (`--update`) |

### Environment

| Variable | Description |
| :--- | :--- |
| `CONTEXT_BUNDLE_VARS` | Default `key=val` pairs (overridden by CLI `key=val`) |
| `CONTEXT_BUNDLE_PLAIN` | Set to `1` to omit transport `Bundle-*` headers and fragment markers |
| `CONTEXT_BUNDLE_LOCAL_PKG_DIR` | Use a local package checkout instead of the cache |
| `CONTEXT_BUNDLE_CACHE_DIR` | Override the cache directory (default: `$XDG_CACHE_HOME/context-bundle` or `~/.cache/context-bundle`) |
| `CONTEXT_BUNDLE_SHELL` | Override the shell executable used for `cmd` directives |
| `CONTEXT_BUNDLE_UPDATE_URL` | Override the remote script URL for `--update` |

## `.context.bundle` Format & 9-Keyword Directive Reference

Starter `.context.bundle` example:

```text
bundle vitalio/agents-rules:adapters/todo_md
bundle vitalio/agents-rules:core
rule vitalio/agents-rules:release/semver vitalio/agents-rules:stack/cli
rule vitalio/agents-rules:stack/python-cli py_min=3.9

file AGENTS.md
if role=work
    file {todo_md.files:}

cmd context --tree -x archive_dir
cmd git status -sb
if mode=summary
    cmd git shortlog -sn
    prompt Summarize recent repository activity.
```

`.context.bundle` (legacy `.agents_bundle`) and package `.bundle` files share
the same 9-keyword directive language; blank lines and `#` comments are
ignored, and `file` and `cmd` fragments assemble in exact top-down declaration
order:

- `bundle <owner>/<repo>[@<ref>][:<name|path>] [allow=<cmd,...>] [k=v ...]`
  (or a local path `./...`, `../...`, or URL) includes a composite bundle from
  `agents/` (`<repo>.bundle` or `default.bundle` for `<owner>/<repo>`,
  `<domain>.bundle`, `<domain>/<domain>.bundle`, or `<domain>/default.bundle`
  for `:<domain>`, or an explicit package-relative path); circular references
  fail fast. Pass `allow=<cmd,...>` to permit an external bundle to run
  specific executables.
- `rule <target...> [k=v ...]` includes one or more atomic `.md` rule files
  from a package's `agents/` directory, an explicit package-relative path, a
  local relative path (`./...`, `../...`), or a URL.
- `file <path|glob|slice...>` includes space-separated repository files, globs,
  `path:START-END` slices, or `$(<cmd>)` output (external bundles are
  restricted to files within the repository root). Empty `file` after variable
  expansion (such as `file {todo_md.files:}` when unset) is a no-op.
- `cmd <shell command>` runs a command in `Workdir` and includes its output.
- `prompt <text>` appends text to the Prompt section.
- `let <name>=<value>` or `let <name>=$(<cmd>)` sets a lexically scoped
  bundle-local variable (set-if-unset; passed down to child `rule` and `bundle`
  invocations, never leaking upward to parent/sibling bundles or output
  preamble headers).
- `export <name...>` promotes variables to session scope (visible to subsequent
  bundles) and emits them as capitalized `Key: Value` output preamble headers
  when non-empty.
- `if <cond>`, `else if <cond>` (synonym `elif <cond>`), `else` guard 4-space
  Python-style indented blocks without trailing colons or `endif`. Variable
  names in `if`, `let`, `export`, and `{name:default}` support dot-separated
  producer namespaces (`<owner>.<repo>.<key>` and `<repo>.<key>`).
- `allow <bin...>` (root `.context.bundle` / `.agents_bundle` only) permits
  external bundles to run the listed executables in `cmd`, `let <k>=$(<cmd>)`,
  and `file $(<cmd>)`. All commands from external bundles are inspected
  statically before any shell command runs; unlisted executables fail fast
  naming the blocked command and originating bundle.

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
- **Chain provenance:** Fragments from `.context.bundle` or `.agents_bundle`
  (and nested bundles) carry `chain` starting with the root spec filename;
  piped upstream fragments keep their own chain, and CLI file and `-p`
  arguments use `[]`.
- **Embedded rule:** A short built-in rule (`id`
  `vitalio/context-bundle:context`, chain `["vitalio/context-bundle"]`)
  describing `--tree` and session assembly is always added to the Rules
  section. `--init` creates a starter `.context.bundle` that uses
  `file AGENTS.md`.

## Package Cache

Remote packages are cloned into `<cache_dir>/packages` and URL files are saved
in `<cache_dir>/urls` (`CONTEXT_BUNDLE_CACHE_DIR` overrides the location;
`~/.cache/agents_bundle` is automatically migrated to
`~/.cache/context-bundle`). `--refresh` re-fetches each remote package or URL
at most once per run. `--update-cache` fetches and hard-resets every cached git
package to its remote ref and re-downloads every cached URL file, printing one
status line per item (exit code `1` when any item fails). Set
`CONTEXT_BUNDLE_LOCAL_PKG_DIR` to use a local package checkout for unpinned
package references instead of the cache (explicit `@<ref>` package specs always
fetch the requested ref into `<cache_dir>/packages/<owner>/<repo>@<ref>`);
there is no implicit lookup in the home directory.

## License

[MIT](LICENSE) © 2026 [vitalio](https://github.com/vitalio)
