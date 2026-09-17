# Cline integration (template)

Bundled reference for the project-level adapter directory created by `co adapt cline`:

- `.clinerules/` — Cline workspace rules (toggle in Rules panel)
- `AGENTS.md` — cross-tool instructions (also read by Cline)
- `.agent/adapters/cline/mcp-snippet.json` — MCP stdio config snippet
- `.agent/adapters/cline/README.md` — install steps

## MCP install

```bash
co adapt cline
co mcp install cline --dry-run
co mcp install cline -y
```

Cline VS Code extension: merge into `cline_mcp_settings.json` (extension globalStorage).

Cline CLI: merge into `~/.cline/mcp.json` — inspect with `cline config mcp --json`.

Docs: https://docs.cline.bot/mcp/mcp-marketplace

## Skills roots

| Path | Role |
|------|------|
| `.agent/skills/<name>/` | Protocol / portable cokodo skills |
| `.agent/skills/_project/<name>/` | Project-specific skills (preferred for team skills) |
| `.agents/skills/<name>/` | Optional Agents Skills / upstream Cline layout |

Cline hosts that use `instructionSystem=cokodo` (or equivalent) should discover both `.agent/skills` and `.agent/skills/_project`. See `.agent/skills/skill-interface.md` §2.1.
