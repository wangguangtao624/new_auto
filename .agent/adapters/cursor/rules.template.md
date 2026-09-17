# Cursor Rules Template

> Copy this content to `.cursor/rules/agent-protocol.mdc` in your project root.
> Prefer `co adapt cursor`, which also writes root `AGENTS.md` and `.agents/skills/`.

---
description: AI Agent Collaboration Protocol — read .agent/project/status.md first
alwaysApply: true
---

# Agent Protocol

The shared contract is `AGENTS.md` at the repository root, which Cursor loads as a rule.
Do not duplicate it here. Start every session by reading `$AGENT_DIR/project/status.md`,
then `$AGENT_DIR/start-here.md`.

**Authority**: `$AGENT_DIR/` and `AGENTS.md` are the single source of truth. User and
global Cursor rules govern editor behavior only; on conflict, follow `$AGENT_DIR/`.

## Cursor specifics

- `.cursor/plans/` is an IDE-local draft. A plan that should outlive the session must be
  mirrored to `$AGENT_DIR/project/plan/<kebab-name>.md` and registered in `plan-index.md`.
- Prefer skills in `.agents/skills/` over new always-on rules. Run `co skills export`
  (or `co adapt cursor`) to regenerate them.
- Team Rules (dashboard) take precedence over project rules. Keep project-specific
  conventions in `$AGENT_DIR/`, not in user or team rules.

### MCP (Cursor)

`.cursor/mcp.json` must pass the workspace root explicitly so parameterless
`session_gate` / `get_project_context` work when the MCP process cwd ≠ project:

```json
{
  "mcpServers": {
    "cokodo": {
      "command": "co",
      "args": ["serve", "--shared-launcher", "${workspaceFolder}"],
      "env": { "COKODO_PROJECT_ROOT": "${workspaceFolder}" }
    }
  }
}
```

Regenerate with `co adapt cursor`. Relies on Cursor config interpolation
(https://cursor.com/docs/mcp).

---

*Adapt $AGENT_DIR to your actual directory name*
