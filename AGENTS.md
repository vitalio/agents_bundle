# `agents_bundle` — Project-Specific Agent Rules

Universal workflow, language, Git, SemVer, Python CLI, and single-file build rules are loaded via `$ agents_rules std:python-tool` and `$ agents_rules std:release/single-file-build`.

## Release trigger & local reinstall

- Edit source files under `src/` (`src/*.py`) and run `python3 build.py` to regenerate `./agents_bundle`.
- Whenever `src/`, `install.sh`, or `install.ps1` is modified, bump `VERSION` and `VERSION = "..."` in `src/header.py`, run `python3 build.py`, reinstall locally via `sh install.sh --yes >/dev/null`, commit, push to `origin main`, and push annotated tag `vX.Y.Z`.
