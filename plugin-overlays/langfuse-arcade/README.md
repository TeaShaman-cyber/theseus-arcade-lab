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
