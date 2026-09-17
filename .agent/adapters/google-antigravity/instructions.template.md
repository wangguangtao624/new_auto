# Gemini Agent Adapter

> Place as `GEMINI.md` at project root. Supports `@file` import syntax.

---

**Authority**: For this project, rules under `$AGENT_DIR/` and this file are the single source of truth; user/global IDE rules are for editor behavior only. If they conflict, follow this repository's `.agent` protocol.

This project uses AI Agent Collaboration Protocol.
The files below are auto-imported for full context.

@$AGENT_DIR/project/status.md

@$AGENT_DIR/start-here.md

@$AGENT_DIR/project/context.md

@$AGENT_DIR/project/tech-stack.md

@$AGENT_DIR/project/deploy.md

@$AGENT_DIR/project/commands.md

@$AGENT_DIR/core/core-rules.md

## Key Rules

- Encoding: UTF-8 (explicit declaration required)
- Paths: always use forward slash `/`
- Test data: must use `autotest_` prefix
- No external CDN links
- Check `$AGENT_DIR/project/known-issues.md` before starting work
- Check `$AGENT_DIR/project/deploy.md` for deployment info before infra-related tasks
- Update `$AGENT_DIR/project/status.md` at checkpoints (after tasks, before commits, on blockers)

---

## Compatibility

| Feature | This Protocol | Gemini |
|---------|---------------|--------|
| Skills location | `$AGENT_DIR/skills/<name>/SKILL.md` | `skills/<name>/SKILL.md` |
| Frontmatter | YAML with name + description | YAML |
| File import | `@relative/path.md` | `@relative/path.md` |

---

*Adapt $AGENT_DIR to your actual directory name*
