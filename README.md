# agents_bundle

**Unix-style context bundler, rule/ruleset engine, and token-budgeted repository file tree for AI coding agents.**

`agents_bundle` executes `.agents_bundle` in the target working directory
(`-C`/`--dir`, a piped `Workdir:` preamble on `stdin`, or the current directory),
runs `ruleset ...`, `rule ...`, `bundle ...`, `allow ...`, `var ...`,
`expose ...`, `include ...`, `prompt ...`, `[if ...]`, and `$ <cmd>` directives, includes any extra files and
`-p/--prompt` text, emits `Bundle-Command`, `Bundle-Boundary`, `Bundle-Expose`
(default: `Role, Task, Title`, extensible via `expose` or
`AGENTS_BUNDLE_EXPOSE`), and `Workdir: <path>` in the bundle header (or plain
Markdown/text via `--plain` / `AGENTS_BUNDLE_PLAIN=1`), and writes the assembled
bundle strictly to `stdout` (sending warnings or errors to `stderr`) so it
composes cleanly via Unix pipes.

When `stdin` is piped, leading `Key: Value` preamble headers (terminated by a
blank line or EOF) are parsed automatically: `Workdir:` selects the working
directory unless overridden by `-C`/`--dir`, `Bundle-*` transport headers are
ignored, and other headers (`Task:`, `Role:`, etc.) map to lowercase template
variables (`task`, `role`, ...) when not overridden by CLI `k=v` or
`AGENTS_BUNDLE_VARS`. A single-token body still sets `task=<ID>`, any remaining
body text is prepended to the prompt, and built-in `piped=1` is exposed when
stdin prompt text is present so bundles can guard duplicate output with
`[if piped!=1]`. When `stdin` is an actual pipe (FIFO) that delivers empty
input, for example because an upstream command failed without writing to
`stdout`, `agents_bundle` writes an error to `stderr` and exits `2` before
running any `.agents_bundle` directives; non-FIFO non-TTY `stdin` such as
`/dev/null` is still accepted.

## Quick Installation

**Linux / macOS:**

```bash
curl -fsSL https://raw.githubusercontent.com/vitalio/agents_bundle/main/install.sh | sh
```

**Windows (PowerShell 7+):**

```powershell
irm https://raw.githubusercontent.com/vitalio/agents_bundle/main/install.ps1 | iex
```

Custom command name or install directory:

```bash
curl -fsSL https://raw.githubusercontent.com/vitalio/agents_bundle/main/install.sh | sh -s -- --name ab --dir ~/.local/bin
```

Check for updates or self-update in place:

```bash
agents_bundle --check-update
agents_bundle --update
```

## `.agents_bundle` Format

```text
ruleset vitalio/agents-rules:default
rule vitalio/agents-rules:release/semver
rule vitalio/agents-rules:stack/cli
rule vitalio/agents-rules:stack/python-cli py_min=3.9

$ cat AGENTS.md
$ agents_bundle --tree -x archive_dir
$ git status -sb
[if role=work]
    var task=$(todo_md next-id)
    include $(todo_md files {task:})
[/if]
[if mode=summary]
    $ git shortlog -sn
    prompt Summarize recent repository activity.
[/if]
```

## CLI Usage

```bash
agents_bundle --init
agents_bundle > bundle.txt
agents_bundle role=design > bundle.txt
agents_bundle role=plan > bundle.txt
agents_bundle role=work > bundle.txt
agents_bundle role=work task=F1 > bundle.txt
todo_md F1 | agents_bundle role=work > bundle.txt
agents_bundle -C /path/to/project role=work > bundle.txt
agents_bundle role=review > bundle.txt
AGENTS_BUNDLE_VARS="chat_lang=Spanish" agents_bundle > bundle.txt
agents_bundle -p "Fix issue #12" src/main.py > bundle.txt
agents_bundle -p "Review" 'src/*.py' src/bundle.py:395-445 > bundle.txt
agents_bundle --plain role=work > plain_bundle.txt
AGENTS_BUNDLE_PLAIN=1 agents_bundle > plain_bundle.txt
agents_bundle ruleset vitalio/agents-rules:default os=windows
agents_bundle rule vitalio/agents-rules:release/single-file-build
agents_bundle bundle vitalio/todo_md role=design --plain
agents_bundle --refresh > bundle.txt
agents_bundle --update-cache
agents_bundle --list
agents_bundle --tree -x bumps -x resolutions --max-lines 160
```

`agents_bundle bundle <pkg>[:<name>] [k=v]` renders a single bundle,
symmetric with `ruleset` and `rule`, without requiring a `.agents_bundle`
file: the bundle's rules, command sections, included files, and prompts are
emitted in the regular bundle format. It accepts `k=v` variables and the
bundle options (`-C`/`--dir`, `-p`/`--prompt`, `--plain`, `-v`/`--verbose`,
`--refresh`) but does not read `stdin`.

Extra file arguments and `include` directive items accept relative glob
patterns (`*`, `?`, `[`, and recursive `**`; matches are sorted and `.git`
and `__pycache__` are skipped) and 1-based inclusive line-range slices
`path:START-END` or `path:LINE`. A string that names an existing file is
always included whole. A slice is emitted as a
`===== $ sed -n 'START,ENDp' <path> =====` section with the fragment name
`<path>:START-END`, so several slices of one large file can be included.

## Directive Reference

`.agents_bundle` and `.bundle` files take one directive per line; blank
lines and `#` comments are ignored:

- `ruleset <pkg>[@<ref>]:<name|path> [-exclude ...] [k=v ...]` and
  `rule <pkg>[@<ref>]:<name|path> [k=v ...]` add rule files from a package's
  `agents/` directory (with fallback to legacy `rules/`, `rulesets/`, and
  `src/`), an explicit package-relative path, a local relative path (`./...`,
  `../...`), or a URL.
- `bundle <owner>/<repo>[@<ref>][:<name|path>] [allow=<cmd,...>] [k=v ...]` (or a
  local path `./...`, `../...`) includes another bundle from `agents/`
  (`<repo>.bundle` or `default.bundle` for `<owner>/<repo>`, `<domain>.bundle`,
  `<domain>/<domain>.bundle`, or `<domain>/default.bundle` for `:<domain>`,
  with fallback to legacy `bundles/` and `src/bundles/`, or an explicit
  package-relative path); circular references fail fast. Pass `allow=<cmd,...>`
  to permit an external bundle to run specific executables.
- `allow <cmd1> <cmd2> ...` (root `.agents_bundle` only) permits external
  bundles to run the listed executables in `$ <cmd>`, `var <name>=$(<cmd>)`, and
  `include $(<cmd>)`. All commands from external bundles are inspected statically
  before any shell command runs; unlisted executables fail fast naming the
  blocked command and originating bundle.
- `var <name>=$(<cmd>)` or `var <name>=<value>` sets a variable that CLI
  `k=v` and `AGENTS_BUNDLE_VARS` override.
- `expose <key...>` adds header names to `Bundle-Expose`.
- `include <path>` or `include $(<cmd>)` adds repository files, globs,
  and `path:START-END` slices (external bundles are restricted to files within
  the repository root).
- `prompt <text>` appends text to the Prompt section.
- `$ <cmd>` runs a command and includes its output.
- `[if key=val] <line>` guards a line; multi-line `[if ...]` ...
  `[/if]` blocks indent nested lines by 4 spaces.

Keep shared files cross-platform: avoid POSIX-only shell syntax in
`$ <cmd>` lines or guard it with `[if os=windows]` / `[if os!=windows]`.

## Bundle Output Protocol

`agents_bundle` outputs a `Key: Value` header block separated by a blank line
from the assembled body sections (`===== Rules =====`, `===== $ <cmd> =====`,
`===== $ cat <file> =====`, and `===== Prompt =====`):

- **Header visibility (`Bundle-*`):** By default, the header block starts with
  `Bundle-Command`, `Bundle-Boundary: <nonce>` (a per-run hex token),
  `Bundle-Protocol: 1`, and `Bundle-Expose: Role, Task, Title`.
  Use the `expose <key...>` directive in `.agents_bundle` / `.bundle` or `AGENTS_BUNDLE_EXPOSE` in the environment to
  add normalized Title-Case header names to `Bundle-Expose` while keeping
  unexposed template variables in session metadata only.
- **JSON fragment markers:** Each emitted rule, command section, included file
  section, and prompt block is wrapped in single-line HTML comment markers
  keyed by the run nonce:

  ```text
  <!-- bundle:<nonce>:part {"kind": "cmd", "name": "git status -sb", "chain": [], "rc": 0, "ms": 8} -->
  ===== $ git status -sb =====
  ## main...origin/main
  <!-- bundle:<nonce>:end -->
  ```

  Marker payloads use neutral fields: `kind` (`rule`, `cmd`, `include`,
  `prompt`), `id` (for `rule`) or `name` (for `cmd` and `include`), `chain`
  (`[]` for root directives and CLI inputs, or ordered inclusion path of
  bundle/ruleset specifiers), and `rc` / `ms` (for `cmd`).
- **Plain output (`--plain`):** Pass `--plain` or set `AGENTS_BUNDLE_PLAIN=1`
  to omit transport `Bundle-*` headers (`Bundle-Command`, `Bundle-Boundary`,
  `Bundle-Expose`) and JSON fragment markers when plain Markdown/text output is
  requested.
- **Protocol version:** non-plain headers carry `Bundle-Protocol: 1`
  (`context-bundle-protocol` v1).
- **Piped bundles:** when `stdin` declares `Bundle-Boundary: <nonce>`,
  the upstream bundle is unpacked instead of being treated as prompt
  text. Upstream preamble headers become variables (CLI `k=v` over
  `AGENTS_BUNDLE_VARS` over piped), `Bundle-Command` is chained as
  `<upstream> | <this command>`, and `Bundle-Expose` / `Bundle-Hide` are
  merged. `rule` fragments are merged and deduplicated by `id`;
  `include` and `file` fragments are merged with the includes of
  `.agents_bundle` and the CLI, where a whole-file include absorbs any
  slice of the same file and overlapping slices become one slice;
  `task`, `context`, and `prompt` fragments are re-wrapped with the new
  boundary inside the Prompt section with their metadata preserved.
- **Chain provenance:** fragments from `.agents_bundle` (and nested
  bundles) carry `chain` starting with `.agents_bundle`; piped upstream
  fragments keep their own chain, and CLI file and `-p` arguments use
  `[]`.
- **Embedded rule:** a short built-in rule (`id` `agents_bundle`, chain
  `["agents_bundle"]`) describing `--tree` and session assembly is
  always added to the Rules section. `--init` creates a starter
  `.agents_bundle` that uses `include AGENTS.md`.

## Package Cache

Remote packages are cloned into `<cache_dir>/packages` and URL files are
saved in `<cache_dir>/urls` (`AGENTS_BUNDLE_CACHE_DIR` overrides the
location). `--refresh` re-fetches each remote package or URL at most once
per run. `--update-cache` fetches and hard-resets every cached git package
to its remote ref and re-downloads every cached URL file, printing one
status line per item (exit code 1 when any item fails). Set
`AGENTS_BUNDLE_LOCAL_PKG_DIR` to use a local package checkout for unpinned
package references instead of the cache (explicit `@<ref>` package specs always
fetch the requested ref into `<cache_dir>/packages/<owner>/<repo>@<ref>`);
there is no implicit lookup in the home directory.

## License

[MIT](LICENSE) © 2026 [vitalio](https://github.com/vitalio)
