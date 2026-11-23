# 🎯 [NEXT] F27: Rename project to context-bundle and CLI utility to ctx

- Depends on: F15, F33
- Rename project/repository references from `agents_bundle` to `context-bundle` (`vitalio/context-bundle`) and CLI entrypoint to `ctx` per `todo_flow:D8` (`docs/adr/0004-ecosystem-rename-and-cutover.md`):
  - Emit `Bundle-Name: vitalio/context-bundle`, embedded rule `agents/ctx.md` (`{cmd:ctx}`, `id: "vitalio/context-bundle:ctx"`, `chain: ["vitalio/context-bundle"]`), and repo marker `# context-bundle-repo: vitalio/context-bundle`.
  - Support qualified `Bundle-Name: <owner>/<repo>` on `stdin` in `src/upstream.py`: normalize `/` -> `.` and `-` -> `_` so producer headers populate both `<owner>.<repo>.<key>` (`vitalio.todo_md.task`) and the unambiguous short alias `<repo>.<key>` (`todo_md.task`), omitting the short alias only if two producers in the same pipeline share `<repo>` under different owners.
  - Switch environment variables to `CTX_*` (`CTX_VARS`, `CTX_PLAIN`, `CTX_CACHE_DIR`, `CTX_LOCAL_PKG_DIR`, `CTX_SHELL`, `CTX_UPDATE_URL`, and installer `CTX_NAME`, `CTX_INSTALL_DIR`).
  - Migrate package cache in `cache_dir_path()` and `install.sh`: atomically rename `~/.cache/agents_bundle` -> `~/.cache/context-bundle` and prune obsolete `packages/vitalio/{agents_bundle,run_block,todo_md}` clones.
  - Replace any existing `agents_bundle` binary in `$INSTALL_DIR` during `install.sh` / `--update`, add `--uninstall` to `ctx` and `install.sh`, and run `python3 build.py && ./install.sh --yes` to migrate the local machine.
- Acceptance criteria: `build.py` outputs `ctx`, `install.sh` installs `ctx` and removes legacy `agents_bundle`, `--uninstall` removes `ctx` and `~/.cache/context-bundle`, and `python3 -m unittest discover -s tests` passes.
