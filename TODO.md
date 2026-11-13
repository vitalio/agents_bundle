# Project — active tasks and operational state

`README.md` documents usage; `AGENTS.md` sets the rules for an AI agent.
Deferred tasks live in `TODO_PLAN.md`; completed and canceled records live in `TODO_ARCHIVE.md`.

Task heading format: `### <emoji> [<STATUS>] <ID>: <title>`
(`⚪ [NEW]`, `🔵 [WIP]`, `⏸️ [HOLD]`, `❓ [QUESTION]`, `✅ [DONE]`, `❌ [CANCELED]`).

## Resume

Written 2026-11-14. Released `agents_bundle` `v0.5.0` (`5623f54`):
- Removed `--agents` flag from `agents_bundle` (since context bundling runs prior to starting a chat session via `agents_bundle | run_block`) and documented module boundaries in `AGENTS.md`.
- Updated tests and documentation for flat `core` and `default` presets in `vitalio/agents_rules`.

## Tasks

### ⚪ [NEW] F1: Initial task

Describe the goal and acceptance criteria.
