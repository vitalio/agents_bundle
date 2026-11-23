# ⚪ [NEW] F35: Add --compile flag to compile baseline AGENTS.md from .context.bundle

- Depends on: F36 -> F34
- Implement `context --compile` so `context --compile > AGENTS.md` renders a static baseline `AGENTS.md` from the project's `.context.bundle` (and local `agents/*.md` rules) without role-specific or session-specific runtime headers.

# ⚪ [NEW] F37: Sync README.md starter .context.bundle example with current agents-rules taxonomy and tighten Quick Start

- Update the starter `.context.bundle` example in `README.md` to use current `vitalio/agents-rules` bundle/rule identifiers (`bundle vitalio/agents-rules:adapters/todo-md`, `bundle vitalio/agents-rules:stack/python py_min=3.9`, `bundle vitalio/agents-rules:stack/cli`, `rule vitalio/agents-rules:release/semver`) instead of removed `adapters/todo_md` and `stack/python-cli`.
- Move detailed slice merge and `context bundle` behavioral edge cases out of `Quick Start` into the reference sections below so `Quick Start` stays concise and scenario-focused per `agents/stack/cli/docs.md`.
