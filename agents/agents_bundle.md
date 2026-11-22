# Description: Context bundler file tree and session assembly
- Context bundler & rules engine (`{cmd:agents_bundle}`):
  - Repository file tree: `{cmd:agents_bundle} --tree [DIR] [-x DIR] [--max-lines N] [--max-tokens N]`
    (use instead of `find`/`ls` for directory structure; pins `AGENTS.md`).
  - Session assembly and handoff:
    `{cmd:agents_bundle} [key=val ...] [-p "<prompt>"] [file ...] | run_block`
    (`role=design|plan|work|review`, `task=<ID>`; extra `file` arguments accept
    globs and `path:start-end` slices). Pipe an upstream bundle into it
    (`<cmd> | {cmd:agents_bundle} | run_block`) to merge its rules, files, and prompt.
  - When editing `.agents_bundle` or `.bundle` files, run `{cmd:agents_bundle} -h`
    for the directive and protocol reference and `{cmd:agents_bundle} --list [pkg]`
    for the available rules, rulesets, and bundles under `agents/`.
