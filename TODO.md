# 🎯 [NEXT] F38: Enforce workdir boundary on root .context.bundle file directives and require trust for non-builtin shell commands

- Bump: `MINOR`
- Close two untrusted-repository security gaps when running `context` in a directory with a repository-local `.context.bundle` (`src/bundle.py`, `src/includes.py`, `src/cli.py`, `src/header.py`):
  - Workdir boundary on root `file` directives: always pass `root_dir=spec_dir` to `_expand_include()` for all `file` directives inside `.context.bundle` (not only external child bundles), preventing a malicious root `.context.bundle` from reading sensitive files outside the repository (such as `file ~/.ssh/id_rsa` or `file ../../secrets.env`) while keeping explicit user CLI file arguments (`context /path/to/file`) unrestricted.
  - Safe default command policy and explicit trust for root `.context.bundle` shell execution: allow built-in read-only inspection commands (`context --tree`, read-only `git status`/`branch`/`log`/`diff`/`rev-parse`, and read-only `todo` queries) in root `.context.bundle` out of the box with zero friction, but require explicit repository trust before executing arbitrary shell commands (`cmd ...`, `let x=$(...)`, `file $(...)`) or custom `allow <bin...>` grants from a root `.context.bundle`.
  - Persist trusted `(realpath, sha256)` entries in `${XDG_STATE_HOME:-~/.local/state}/context-bundle/trusted.json` (`0600` permissions) managed via `context --trust [--revoke | --list]` (or an interactive `/dev/tty` confirmation prompt when a TTY is attached, failing closed in non-interactive pipes with an actionable error message instructing the user to inspect `.context.bundle` and run `context --trust`).
  - Document the root `.context.bundle` trust and `Workdir` boundary model in `README.md`, `AGENTS.md`, and `src/header.py` (`--help`), and add unit tests in `tests/test_bundle.py`, `tests/test_includes.py`, and `tests/test_cli.py`.

# ⚪ [NEW] F35: Add --compile flag to compile baseline AGENTS.md from .context.bundle

- Depends on: F36 -> F34
- Implement `context --compile` so `context --compile > AGENTS.md` renders a static baseline `AGENTS.md` from the project's `.context.bundle` (and local `agents/*.md` rules) without role-specific or session-specific runtime headers.
