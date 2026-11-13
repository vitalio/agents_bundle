# agents_bundle

**Unix-style project context bundler and token-budgeted repository file tree for AI coding agents.**

`agents_bundle` reads `.agents_bundle` in the current directory, executes `$ <cmd>` lines,
includes specified files and `-p/--prompt` text, and writes the assembled bundle strictly to `stdout`
(sending any warnings or errors to `stderr`) so it composes cleanly via Unix pipes.

## Usage

```bash
agents_bundle --init
agents_bundle > bundle.txt
agents_bundle -p "Fix issue #12" src/main.py | run_block --start
agents_bundle --tree --max-lines 100
```

## License

[MIT](LICENSE) © 2026 [vitalio](https://github.com/vitalio)
