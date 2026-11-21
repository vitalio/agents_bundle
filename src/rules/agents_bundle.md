# Description: Context bundler CLI, file tree, rule discovery, and .agents_bundle maintenance
- Context bundler & rules engine (`{cmd:agents_bundle}`):
  - Assemble session bundle: `{cmd:agents_bundle} [key=val ...] [-p "<prompt>"] [file ...] | run_block`
    (roles: `role=design`, `role=plan`, `role=work`, `role=review`; task
    focus: `task=<ID>`, `--plain` or `AGENTS_BUNDLE_PLAIN=1` to omit transport
    `Bundle-*` headers and JSON fragment markers, or pipe `<cmd> | {cmd:agents_bundle} | run_block`
    to parse `Key: Value` preamble headers into `Workdir:` and lowercase
    template variables such as `task`/`role`, accept a bare `<ID>`, prepend any
    piped prompt body, and expose builtin `piped=1` when prompt text is piped).
  - Bundle Output Protocol: default output emits `Bundle-Command`,
    `Bundle-Boundary: <nonce>`, `Bundle-Expose: Role, Task, Title` (extensible via
    `expose <key...>` or `AGENTS_BUNDLE_EXPOSE`), variable headers, and
    `Workdir: <path>`, and wraps emitted rules, commands, included files, and
    prompts in `<!-- bundle:<nonce>:part <json> -->` and
    `<!-- bundle:<nonce>:end -->` markers (`kind`, `id`/`name`, `chain`,
    `rc`, `ms`). Pass `--plain` (or `AGENTS_BUNDLE_PLAIN=1`) when plain
    Markdown/text output without transport framing is needed.
  - Inspect repository file tree: `{cmd:agents_bundle} --tree [DIR] [-x DIR] [--max-lines N] [--max-tokens N]`
    (use instead of `find`/`ls` for directory structure; pins `AGENTS.md`).
  - Discover rulesets, rules, and bundles: `{cmd:agents_bundle} --list [pkg]`,
    `{cmd:agents_bundle} ruleset <pkg>:<name> [k=v]`, `{cmd:agents_bundle} rule <pkg>:<name> [k=v]`,
    `{cmd:agents_bundle} bundle <pkg>[:<name>] [k=v]`.
  - Maintain `.agents_bundle` and `.bundle` files: directives `ruleset`, `rule`,
    `bundle` (`bundle <owner>/<repo>` or `bundle <owner>/<repo>:<name>`),
    `var` (`var <name>=$(<cmd>)`), `expose` (`expose <key...>`),
    `include` (`include $(<cmd>)`), `prompt`, `[if key=val]`, and `$ <cmd>` (single-line `[if ...] <line>`
    needs no `[/if]`; indent nested lines inside multi-line `[if ...] ... [/if]`
    blocks by 4 spaces). During design or planning, keep `.agents_bundle`
    updated with the rulesets, stack rules, and bundles required by the project
    (`{cmd:agents_bundle} --init` bootstraps a new `.agents_bundle`).
  - Keep `.agents_bundle` and `.bundle` files cross-platform across Linux, macOS,
    and Windows (`pwsh`): avoid POSIX-only shell syntax (`&&`, shell variables,
    `for`/`while` loops) in shared `$ <cmd>` lines; use declarative `var`,
    `include`, and single cross-platform commands, or guard OS-specific
    commands with `[if os=windows]` and `[if os!=windows]`.
  - Remote package cache: `{cmd:agents_bundle} --update-cache` hard-resets cached
    git packages and re-downloads cached URL files; `--refresh` re-fetches each
    remote at most once per run; set `AGENTS_BUNDLE_LOCAL_PKG_DIR` to use a
    local package checkout (no implicit home-directory lookup).
