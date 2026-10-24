# langfuse-arcade overlay

Canonical routing/provenance for the private App-backed `langfuse-arcade` ChatGPT plugin.

The plugin should expose Langfuse through Arcade Tool Recommendation rather than inject the full Langfuse MCP schema into every ChatGPT request.

Desired path:

```text
ChatGPT
  -> Arcade_SelectTools
  -> Arcade_UseTool
  -> Langfuse Clean gateway
  -> Langfuse remote MCP
```

The App-backed MCP binding itself is managed by the ChatGPT App configuration and is opaque to Plugin Creator updates. This repository therefore records the canonical endpoint and acceptance invariant separately from the private App binding.

## ChatGPT host compatibility

Production web/mobile routing must remain App-backed. The existing `langfuse-arcade` plugin keeps its `.app.json` binding and receives only skills/support-file overlays from this repository.

Do not replace it with a standalone plugin that embeds the Arcade URL in `mcp.json` / `.mcp.json`: current ChatGPT host behavior marks that packaging Desktop only. The portable package in `plugin-overlays/langfuse-arcade-portable/` is retained only as a desktop diagnostic fixture.
