# Cline MCP setup (cokodo-agent)

Cline stores MCP configuration in the extension settings file (not in this repo).
Use the snippet below to connect the cokodo-agent MCP server.

## Quick install (CLI)

```bash
co mcp install cline --dry-run   # preview merge
co mcp install cline -y          # write to detected Cline MCP settings
co mcp snippet cline --show      # print snippet path and JSON
```

Use `--target PATH` to write a specific JSON file instead of auto-detect.

## Cline CLI (optional)

If you use [Cline CLI](https://docs.cline.bot/) outside VS Code, MCP settings live at `~/.cline/mcp.json`.
Run `cline config mcp --json` to inspect, or merge the same `mcp-snippet.json` entry manually.

VS Code extension settings typically use:
`%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json` (Windows)
or the equivalent path under `~/Library/Application Support/Code/` (macOS).

## Manual steps

1. Open the Cline panel in VS Code.
2. Click **MCP Servers** (stacked server icon) → **Configure** → **Configure MCP Servers**.
3. Merge the contents of `mcp-snippet.json` into your `mcpServers` object.
4. Confirm **cokodo-agent** shows a green status indicator.
5. In a new chat, ask Cline to call `session_gate` or `get_project_context`.

## Windows note

If Cline cannot find `co`, replace `"command": "co"` with the absolute path from `where co`.
The install command tries to resolve `co` automatically.

## Regenerate

Run `co adapt cline` after protocol upgrades to refresh `.clinerules/` and this snippet.
