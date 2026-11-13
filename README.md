# agents_bundle

**Unix-style context bundler, rule/preset engine, and token-budgeted repository file tree for AI coding agents.**

`agents_bundle` executes `.agents_bundle` in the current directory (`preset ...`, `rule ...`, and `$ <cmd>` directives),
includes any extra files and `-p/--prompt` text, and writes the assembled bundle strictly to `stdout`
(sending warnings or errors to `stderr`) so it composes cleanly via Unix pipes.

## `.agents_bundle` Format

```text
$ run_block --agents
$ todo_md --agents
$ agents_bundle --agents

preset vitalio/agents_rules:workflow
rule vitalio/agents_rules:vcs/git
rule vitalio/agents_rules:release/semver
rule vitalio/agents_rules:stack/python-cli py_min=3.9

$ cat AGENTS.md
$ todo_md
$ agents_bundle --tree
$ git status -sb
```

## CLI Usage

```bash
agents_bundle --init
agents_bundle | run_block --start
agents_bundle -p "Fix issue #12" src/main.py | run_block --start
agents_bundle preset vitalio/agents_rules:workflow -core/external lang=Russian
agents_bundle rule vitalio/agents_rules:release/single-file-build
agents_bundle --list
agents_bundle --tree --max-lines 100
```

## License

[MIT](LICENSE) © 2026 [vitalio](https://github.com/vitalio)
