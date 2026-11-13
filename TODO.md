# Project — active tasks and operational state

`README.md` documents usage; `AGENTS.md` sets the rules for an AI agent.
Deferred tasks live in `TODO_PLAN.md`; completed and canceled records live in `TODO_ARCHIVE.md`.

Task heading format: `### <emoji> [<STATUS>] <ID>: <title>`
(`⚪ [NEW]`, `🔵 [WIP]`, `⏸️ [HOLD]`, `❓ [QUESTION]`, `✅ [DONE]`, `❌ [CANCELED]`).

## Resume

Written 2026-11-14. Released `agents_bundle` `v0.4.0` (`7e09267`):
- Added support for loading standalone `.md` rules and `.preset` files directly via URL (`http://`, `https://`, `file://`) with local caching in `~/.cache/agents_bundle/urls/`.
- Fixed `test_preset_rule_if_conditions_and_dollar_commands` to use the active host OS variable so CI passes on `macos-latest` and `windows-latest`.
- Simplified `.agents_bundle` to use `preset vitalio/agents_rules:default`.

## Tasks

### ⚪ [NEW] F1: Initial task

Describe the goal and acceptance criteria.
