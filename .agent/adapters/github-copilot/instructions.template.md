# GitHub Copilot Instructions Template

> Place as `AGENTS.md` at project root. Prefer `co adapt copilot`, which writes this
> file from the shared generator and also emits `.agents/skills/`.

---

**Authority**: rules under `$AGENT_DIR/` and this file are the single source of truth
for this project; user/global IDE rules govern editor behavior only. On conflict,
follow `$AGENT_DIR/`.

## Session entry

1. Read `$AGENT_DIR/project/status.md` **first, every session**.
2. If it shows **Active change (SDD)**, read `$AGENT_DIR/project/changes/<name>/tasks.md`.
3. `$AGENT_DIR/start-here.md` is the protocol entry point.

Check `$AGENT_DIR/project/known-issues.md` before touching an area it names.

## Protocol map (load on demand)

`$AGENT_DIR/core/protocol-map.md` documents directory roles, artifact indexes,
plan governance, and the cross-project MCP workflow. Read it when writing a plan,
research report, review, spec, event, or journal fragment, or when a task involves
another project on this machine.

## Hard rules

- Encoding: UTF-8, declared explicitly.
- Paths: forward slash `/`.
- Test data: `autotest_` prefix.
- No external CDN links.
- Product PRs write `$AGENT_DIR/project/journal.d/` fragments and must not edit
  `status.md`. Sync with `co journal-flush`.

## Skills

Procedures live under `.agents/skills/*/SKILL.md`. Run `co skills export` or
`co adapt copilot` to regenerate them from the protocol. See
`$AGENT_DIR/skills/skill-interface.md`.

---

*Adapt $AGENT_DIR to your actual directory name*
