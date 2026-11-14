# 🔵 [WIP] F3: Add --agents, active bundle header variables, and 4-role workflow (design, plan, execute, audit)

- Add --agents flag and bundle vitalio/agents-rules:agents_bundle (--agents + conditional --list in role=design).
- Emit actual invocation in Bundle-Command: and Title-Case variable headers (Role:, Task:, etc.) in bundle header.
- Define 4 orthogonal roles in vitalio/agents-rules (design, plan, execute, audit) and bind their artifacts in todo_md.bundle.
