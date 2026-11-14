# agents_bundle

**Unix-style context bundler, rule/preset engine, and token-budgeted repository file tree for AI coding agents.**

`agents_bundle` executes `.agents_bundle` in the current directory (`preset ...`, `rule ...`, `include ...`, `prompt ...`, `[if ...]`, and `$ <cmd>` directives),
includes any extra files and `-p/--prompt` text, and writes the assembled bundle strictly to `stdout`
(sending warnings or errors to `stderr`) so it composes cleanly via Unix pipes.

## `.agents_bundle` Format

```text
$ run_block --agents

preset vitalio/agents-rules:default
rule vitalio/agents-rules:release/semver
rule vitalio/agents-rules:stack/cli
rule vitalio/agents-rules:stack/python-cli py_min=3.9

$ cat AGENTS.md
include vitalio/agents-rules:todo_md
$ agents_bundle --tree -x archive_dir
$ git status -sb
```

## CLI Usage

```bash
agents_bundle --init
agents_bundle | run_block
agents_bundle task=plan | run_block
agents_bundle task=F1 -p "Fix issue #12" src/main.py | run_block
agents_bundle preset vitalio/agents-rules:default os=windows
agents_bundle rule vitalio/agents-rules:release/single-file-build
agents_bundle --list
agents_bundle --tree -x bumps -x resolutions --max-lines 160
```

## License

[MIT](LICENSE) © 2026 [vitalio](https://github.com/vitalio)
