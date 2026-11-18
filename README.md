# agents_bundle

**Unix-style context bundler, rule/ruleset engine, and token-budgeted repository file tree for AI coding agents.**

`agents_bundle` executes `.agents_bundle` in the target working directory
(`-C`/`--dir`, a piped `Workdir:` preamble on `stdin`, or the current directory),
runs `ruleset ...`, `rule ...`, `bundle ...`, `expose ...`, `prompt ...`,
`[if ...]`, and `$ <cmd>` directives, includes any extra files and
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
`[if piped!=1]`.

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
bundle vitalio/run_block
bundle vitalio/agents_bundle

ruleset vitalio/agents-rules:default
rule vitalio/agents-rules:release/semver
rule vitalio/agents-rules:stack/cli
rule vitalio/agents-rules:stack/python-cli py_min=3.9

$ cat AGENTS.md
$ agents_bundle --tree -x archive_dir
$ git status -sb
[if role=execute]
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
agents_bundle role=execute > bundle.txt
agents_bundle role=execute task=F1 > bundle.txt
todo_md F1 | agents_bundle role=execute > bundle.txt
agents_bundle -C /path/to/project role=execute > bundle.txt
agents_bundle role=audit > bundle.txt
AGENTS_BUNDLE_VARS="chat_lang=Spanish" agents_bundle > bundle.txt
agents_bundle -p "Fix issue #12" src/main.py > bundle.txt
agents_bundle --plain role=execute > plain_bundle.txt
AGENTS_BUNDLE_PLAIN=1 agents_bundle > plain_bundle.txt
agents_bundle ruleset vitalio/agents-rules:default os=windows
agents_bundle rule vitalio/agents-rules:release/single-file-build
agents_bundle --refresh > bundle.txt
agents_bundle --update-cache
agents_bundle --list
agents_bundle --tree -x bumps -x resolutions --max-lines 160
```

## Bundle Output Protocol

`agents_bundle` outputs a `Key: Value` header block separated by a blank line
from the assembled body sections (`===== Rules =====`, `===== $ <cmd> =====`,
`===== $ cat <file> =====`, and `===== Prompt =====`):

- **Header visibility (`Bundle-*`):** By default, the header block starts with
  `Bundle-Command`, `Bundle-Boundary: <nonce>` (a per-run hex token), and
  `Bundle-Expose: Role, Task, Title`. Use the `expose <key...>` directive in
  `.agents_bundle` / `.bundle` or `AGENTS_BUNDLE_EXPOSE` in the environment to
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

## Package Cache

Remote packages are cloned into `<cache_dir>/packages` and URL files are
saved in `<cache_dir>/urls` (`AGENTS_BUNDLE_CACHE_DIR` overrides the
location). `--refresh` re-fetches each remote package or URL at most once
per run. `--update-cache` fetches and hard-resets every cached git package
to its remote ref and re-downloads every cached URL file, printing one
status line per item (exit code 1 when any item fails). Set
`AGENTS_BUNDLE_LOCAL_PKG_DIR` to use a local package checkout instead of the
cache; there is no implicit lookup in the home directory.

## License

[MIT](LICENSE) © 2026 [vitalio](https://github.com/vitalio)
