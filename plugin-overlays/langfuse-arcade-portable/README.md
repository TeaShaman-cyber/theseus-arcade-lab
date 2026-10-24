# langfuse-arcade portable package

Status: **DESKTOP_DIAGNOSTIC_ONLY**.

This package embeds the remote Arcade MCP endpoint through `mcp.json`.
In ChatGPT's current plugin host behavior, that portable remote-MCP packaging is
marked **Desktop only** even when the MCP endpoint is public HTTPS.

It is therefore NOT the production path for web/mobile ChatGPT.

The web-compatible production plugin is the existing App-backed
`langfuse-arcade` object whose package keeps `.app.json` / App binding and adds
skills on top without adding `mcp.json` or `.mcp.json`.

Use this portable package only for diagnostics, artifact inspection, or desktop
experiments. Do not use it as the migration target for the web/mobile plugin.
