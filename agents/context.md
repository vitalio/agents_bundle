# Description: Context bundler file tree, session assembly, and catalog inspection
- Context bundler & rules engine (`{cmd:context}`):
  - Repository file tree: `{cmd:context} --tree [DIR] [-x DIR] [--max-lines N] [--max-tokens N]`
    (use instead of `find`/`ls` for directory structure; pins `AGENTS.md`).
  - Session assembly and handoff:
    `[<upstream_cmd> | ]{cmd:context} [key=val ...] [-p "<prompt>"] [file ...] | run_block`
    (extra `file` arguments accept globs and `path:start-end` slices).
  - Bundle authoring & catalog inspection: run `{cmd:context} --list [pkg]` to
    inspect available bundles, rules, and `let` parameters under `agents/`, and
    `{cmd:context} -h` for the `.bundle` directive reference.
