# 🎯 [NEXT] F27: Rename project to context-bundle and CLI utility to ctx

- Depends on: F15, F33
- Rename project/repository references from `agents_bundle` to `context-bundle` and CLI entrypoint from `agents_bundle` to `ctx` (with `.context.bundle` as root bundle config and agreed deprecation aliases/symlinks and env-var updates from `todo_flow:D8` and ADR 0003).
- Acceptance criteria: `build.py` outputs `ctx`, `install.sh` installs `ctx` (plus any agreed compatibility alias), `--help`/rules/docs/tests reflect `context-bundle` and `ctx`, and `python3 -m unittest discover -s tests` passes.
