# agents_bundle

**Unix-style context bundler, rule/preset engine, and token-budgeted repository file tree for AI coding agents.**

`agents_bundle` executes `.agents_bundle` in the current directory (`preset ...`, `rule ...`, `[if ...]`, and `$ <cmd>` directives),
includes any extra files and `-p/--prompt` text, and writes the assembled bundle strictly to `stdout`
(sending warnings or errors to `stderr`) so it composes cleanly via Unix pipes.

## `.agents_bundle` Format

```text
$ run_block --agents
$ todo_md --agents
$ agents_bundle --agents

preset vitalio/agents_rules:workflow
[if os=linux] rule vitalio/agents_rules:os/linux
[if os=macos] rule vitalio/agents_rules:os/macos
[if os=windows] rule vitalio/agents_rules:os/windows
rule vitalio/agents_rules:vcs/git
rule vitalio/agents_rules:release/semver
rule vitalio/agents_rules:stack/cli
rule vitalio/agents_rules:stack/python-cli py_min=3.9

$ cat AGENTS.md
$ todo_md
$ agents_bundle --tree -x archive_dir
$ git status -sb
```

## CLI Usage

```bash
agents_bundle --init
agents_bundle | run_block --start
agents_bundle -p "Fix issue #12" src/main.py | run_block --start
agents_bundle preset vitalio/agents_rules:default os=windows
agents_bundle rule vitalio/agents_rules:release/single-file-build
agents_bundle --list
agents_bundle --tree -x bumps -x resolutions --max-lines 160
```

## License

[MIT](LICENSE) © 2026 [vitalio](https://github.com/vitalio)
