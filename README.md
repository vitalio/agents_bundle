# context-bundle (`context`)

Unix-style context bundler, rule/bundle engine, and token-budgeted repository
file tree for AI coding agents on POSIX (`linux` and `macos`).

`context` executes `.context.bundle` (with fallback to `.agents_bundle`) in
the target working directory (`-C`/`--dir`, a piped `Workdir:` preamble on
`stdin`, or the current directory), runs the 9-keyword `.bundle` language
(`bundle`, `rule`, `file`, `cmd`, `prompt`, `let`, `export`,
`if`/`else if`/`elif`/`else`, and `allow`), includes any extra CLI files and
`-p/--prompt` text, emits `Bundle-Command`, `Bundle-Name: vitalio/context-bundle`,
`Bundle-Boundary`, `Bundle-Protocol: 1`, exported `Key: Value` variable
headers, and `Workdir: <path>` in the bundle header (or plain Markdown/text via
`--plain` / `CONTEXT_BUNDLE_PLAIN=1`), and writes the assembled bundle strictly
to `stdout` (sending warnings or errors to `stderr`) so it composes cleanly via
Unix pipes.

When `stdin` is piped, leading `Key: Value` preamble headers (terminated by a
blank line or EOF) are parsed automatically: `Workdir:` selects the working
directory unless overridden by `-C`/`--dir`, and when `Bundle-Name: <owner>/<repo>`
(or `<producer>`) is present, `/` is normalized to `.` and `-` to `_` so
non-transport headers populate both `<owner>.<repo>.<key_lower>` (for example
`vitalio.todo_md.task`) and the unambiguous short alias `<repo>.<key_lower>`
(`todo_md.task`, `todo_md.prefix`, `todo_md.status`, `todo_md.title`,
`todo_md.files`, `todo_md.role`) while rejecting duplicate producer names in
the same pipeline. A single-token body sets `task=<ID>` (or `<producer>.task=<ID>`),
any remaining body text is prepended to the prompt, and built-in `piped=1` is
exposed when stdin prompt text is present so bundles can guard duplicate output
with `if piped!=1`. When `stdin` is an actual pipe (FIFO) that delivers empty
input, `context` writes an error to `stderr` and exits `2` before running any
directives; non-FIFO non-TTY `stdin` such as `/dev/null` is still accepted.

## Quick Installation

Linux / macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/vitalio/context-bundle/main/install.sh | sh
```

Custom command name or install directory:

```bash
curl -fsSL https://raw.githubusercontent.com/vitalio/context-bundle/main/install.sh | sh -s -- --name ctx --dir ~/.local/bin
```

Check for updates, self-update in place, or uninstall:

```bash
context --check-update
context --update
context --uninstall
```

## `.context.bundle` Format

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

## CLI Usage

```bash
context --init
context > bundle.txt
context role=design > bundle.txt
context role=plan > bundle.txt
context role=work > bundle.txt
context role=work task=F1 > bundle.txt
todo_md F1 | context role=work > bundle.txt
context -C /path/to/project role=work > bundle.txt
context role=review > bundle.txt
CONTEXT_BUNDLE_VARS="chat_lang=Spanish" context > bundle.txt
context -p "Fix issue #12" src/main.py > bundle.txt
context -p "Review" 'src/*.py' src/bundle.py:395-445 > bundle.txt
context --plain role=work > plain_bundle.txt
CONTEXT_BUNDLE_PLAIN=1 context > plain_bundle.txt
context bundle vitalio/agents-rules:default os=macos --plain
context rule vitalio/agents-rules:release/single-file-build
context bundle vitalio/todo_md role=design --plain
context --refresh > bundle.txt
context --update-cache
context --list
context --tree -x bumps -x resolutions --max-lines 160
```

`context bundle <pkg>[:<name>] [k=v]` renders a single bundle without
requiring a `.context.bundle` file: the bundle's rules, file sections, command
sections, and prompts are emitted in the regular bundle format. It accepts
`k=v` variables and the bundle options (`-C`/`--dir`, `-p`/`--prompt`,
`--plain`, `-v`/`--verbose`, `--refresh`) but does not read `stdin`.

Extra file arguments and `file` directive items accept relative glob patterns
(`*`, `?`, `[`, and recursive `**`; matches are sorted and `.git` and
`__pycache__` are skipped) and 1-based inclusive line-range slices
`path:START-END` or `path:LINE`. A string that names an existing file is always
included whole. A slice is emitted as a `===== $ sed -n 'START,ENDp' <path>
=====` section with the fragment name `<path>:START-END`, so several slices of
one large file can be included.

## 9-Keyword `.bundle` Directive Reference

`.context.bundle` (legacy `.agents_bundle`) and package `.bundle` files share the
same 9-keyword directive language; blank lines and `#` comments are ignored,
and `file` and `cmd` fragments assemble in exact top-down declaration order:

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

## Bundle Output Protocol

`context` outputs a `Key: Value` header block separated by a blank line
from the assembled body sections (`===== Rules =====`, `===== $ cat <file>
=====` / `===== $ <cmd> =====` in declaration order, and `===== Prompt =====`):

- **Transport and exported headers:** By default, the header block starts with
  `Bundle-Command`, `Bundle-Name: vitalio/context-bundle`, `Bundle-Boundary: <nonce>`
  (a per-run hex token), and `Bundle-Protocol: 1`, followed by any non-empty
  variables explicitly promoted via `export <key...>` and `Workdir: <path>`.
  Unexported variables stay internal to bundle execution and never appear in
  the output preamble.
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
- **Piped bundles (`context-bundle-protocol` v1):** when `stdin` declares
  `Bundle-Boundary: <nonce>`, the upstream bundle is unpacked instead of being
  treated as prompt text. When `Bundle-Name: <producer>` is present, `/` is
  normalized to `.` and `-` to `_` so upstream preamble headers (except
  `Workdir`) populate `<owner>.<repo>.<key_lower>` and unambiguous
  `<repo>.<key_lower>` (rejecting duplicate producer names in the same
  pipeline), and `Bundle-Command` is chained as `<upstream> | <this command>`.
  `rule` fragments are merged and deduplicated by `id`; `file` fragments are
  merged with bundle and CLI files at first occurrence (where a whole-file span
  absorbs any slice of the same file and overlapping slices become one slice);
  `prompt` fragments are re-wrapped with the new boundary inside the Prompt
  section with their metadata preserved.
- **Chain provenance:** fragments from `.context.bundle` or `.agents_bundle` (and
  nested bundles) carry `chain` starting with the root spec filename; piped
  upstream fragments keep their own chain, and CLI file and `-p` arguments use
  `[]`.
- **Embedded rule:** a short built-in rule (`id` `vitalio/context-bundle:context`,
  chain `["vitalio/context-bundle"]`) describing `--tree` and session assembly is
  always added to the Rules section. `--init` creates a starter `.context.bundle`
  that uses `file AGENTS.md`.

## Package Cache

Remote packages are cloned into `<cache_dir>/packages` and URL files are
saved in `<cache_dir>/urls` (`CONTEXT_BUNDLE_CACHE_DIR` overrides the
location; `~/.cache/agents_bundle` is automatically migrated to
`~/.cache/context-bundle`). `--refresh` re-fetches each remote package or URL
at most once per run. `--update-cache` fetches and hard-resets every cached git
package to its remote ref and re-downloads every cached URL file, printing one
status line per item (exit code 1 when any item fails). Set
`CONTEXT_BUNDLE_LOCAL_PKG_DIR` to use a local package checkout for unpinned
package references instead of the cache (explicit `@<ref>` package specs always
fetch the requested ref into `<cache_dir>/packages/<owner>/<repo>@<ref>`);
there is no implicit lookup in the home directory.

## License

[MIT](LICENSE) © 2026 [vitalio](https://github.com/vitalio)
