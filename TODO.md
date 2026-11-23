# ⚪ [NEW] F35: Add --compile flag to compile baseline AGENTS.md from .context.bundle

- Depends on: F36 -> F34
- Implement `context --compile` so `context --compile > AGENTS.md` renders a static baseline `AGENTS.md` from the project's `.context.bundle` (and local `agents/*.md` rules) without role-specific or session-specific runtime headers.
