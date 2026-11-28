# 🎯 [NEXT] F35: Compile self-contained AGENTS.md (--compile) and load compiled context with -f/--file override

- Depends on: F36 -> F34
- Depends on: F39, D1 -> F44 -> F45
- Bump: `MINOR`
- Add `context --compile [-f SPEC] [-C DIR]` and `-f, --file FILE` source selection across `src/cli.py`, `src/bundle.py`, `src/includes.py`, and `src/header.py`:
  - `context --compile [-f SPEC] [-C DIR]`: compile `.context.bundle` (or `SPEC`) into an in-place delimited `<!-- context:compiled ... -->...<!-- /context:compiled -->` block in `AGENTS.md`, preserving all user-authored project instructions outside the block across repeated compilations and recording trust for the compiled spec in `trusted.json`.
  - Self-contained compiled block: embed both Layer 1 invariant rules and conditional Layer 2 rules (`if role=...`) together with variable/command/file directives inside the compiled block so `AGENTS.md` works both as clean readable Markdown for standalone tools and as a zero-dependency offline bundle source for `context`.
  - Source resolution & `-f, --file FILE` override: in `build_bundle()` / `cmd_bundle()`, auto-select the compiled block in `AGENTS.md` when present in `Workdir` (without reading `.context.bundle` or querying external packages), falling back to `.context.bundle` otherwise; allow `-f, --file FILE` to explicitly force `.context.bundle`, `AGENTS.md`, or any custom bundle file path.
  - Deduplicated `file AGENTS.md` expansion: in `read_span()` (`src/includes.py`), strip any `<!-- context:compiled ... -->...<!-- /context:compiled -->` block when reading `AGENTS.md` so `===== $ cat AGENTS.md =====` emits only the user-authored project section (and omits the span if the remaining user section is empty) in both compiled and `.context.bundle` modes.
  - Document `--compile` and `-f, --file FILE` in `src/header.py` (`--help`), `README.md`, and `AGENTS.md`, add unit tests in `tests/test_bundle.py`, `tests/test_includes.py`, and `tests/test_cli.py`, and rebuild `./context` via `python3 build.py`.

# 🔎 [REVIEW] F45: Replace bare bundle/rule subcommands with --bundle/--rule and show '{prog} [k=v ...] [FILE ...]' in Commands: — *Replaced bare bundle/rule subcommands with --bundle/--rule and prefixed default Commands row with {prog} in v0.26.0*

- Depends on: F42, F44
- Bump: `MINOR`
- Replace bare positional `bundle` and `rule` subcommands with `--bundle` and `--rule` in `src/cli.py` and `src/header.py`:
  - Route `args[0] == "--bundle"` (usage: `{prog} --bundle <pkg>[:<name>] [k=v] [-C DIR] [-p TEXT] [--plain] [-v] [--refresh]`) and `args[0] == "--rule"` in `main()` (`src/cli.py`).
  - When `args[0]` is bare `"bundle"` or `"rule"`, fail with exit code `2` and `f"{prog}: unknown bare command '{args[0]}'; did you mean '--{args[0]}'?"` so every non-default command uses the `--<command>` flag contract.
- Update `HELP_USAGE` and `HELP_SECTIONS` in `src/header.py`:
  - In `Commands:`, prefix the bare default invocation row with `{prog}` (`"{prog} [k=v ...] [FILE ...]"`) per `agents/cli/help.md`, and update the subcommand rows to `"--bundle <pkg>[:<name>] [k=v]"` and `"--rule <pkg>[:<name...>] [k=v]"`.
- Update `README.md`, `AGENTS.md`, and unit tests in `tests/test_cli.py`, `tests/test_core.py`, `tests/test_rules_engine.py`, and `tests/test_bundle.py`, rebuild `./context` via `python3 build.py`, and verify `python3 build.py --check`.
