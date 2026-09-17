# Claude Instructions Template

> For Claude Code integration. Prefer `co adapt claude`, which writes `CLAUDE.md`,
> root `AGENTS.md`, and `.claude/skills/` (Claude Code does not read `.agents/skills/`).

---

@AGENTS.md

The shared protocol contract is in `AGENTS.md`, imported above. Everything below is
Claude-Code-specific and does not belong in the cross-tool file.

## Claude Code specifics

- `.claude/rules/*.md` carries path-scoped rules via `paths:` frontmatter. Rules without
  `paths` load at launch at the same priority as this file.
- After `/compact`, this file is re-read from disk, but nested `CLAUDE.md` files and
  `paths:`-scoped rules are **not** — they reload when a matching file is next read.
- Prefer `.claude/skills/` (or the neutral `.agents/skills/`) for procedures. Run
  `co skills export --mirror claude` or `co adapt claude` to regenerate them.

---

*Claude Code does not read `AGENTS.md` natively; the `@AGENTS.md` import is required.*
