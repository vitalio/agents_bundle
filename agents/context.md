# Description: Context bundler file tree and session assembly
- Context bundler & rules engine (`{cmd:context}`):
  - Repository file tree: `{cmd:context} --tree [DIR] [-x DIR] [--max-lines N] [--max-tokens N]`
    (use instead of `find`/`ls` for directory structure; pins `AGENTS.md`).
  - Session assembly and handoff:
    `{cmd:context} [key=val ...] [-p "<prompt>"] [file ...] | run_block`
    (`role=design|plan|work|review|law`, `task=<ID>`; extra `file` arguments
    accept globs and `path:start-end` slices). Pipe an upstream bundle into it
    (`<cmd> | {cmd:context} | run_block`) to namespace its headers under
    `<producer>.*` (`Bundle-Name`) and merge its rules, files, and prompt.
  - When editing `.context.bundle` (or `.agents_bundle`) and `.bundle` files, run
    `{cmd:context} -h` for the 9-keyword directive and protocol reference
    and `{cmd:context} --list [pkg]` for the available bundles and rules
    under `agents/`.
