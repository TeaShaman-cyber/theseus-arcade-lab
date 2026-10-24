# Canonical Langfuse Arcade gateway

Status: canonical routing target for the `langfuse-arcade` ChatGPT plugin.

- Gateway name: `Langfuse Clean`
- Gateway ID / slug: `gw_3L7MRKPtAX27M5pBEobEz54PZMs`
- Canonical MCP URL: `https://api.arcade.dev/mcp/gw_3L7MRKPtAX27M5pBEobEz54PZMs`
- Expected mode: Arcade Tool Recommendation enabled
- Expected compact client surface: `Arcade_SelectTools` + `Arcade_UseTool` plus any enabled Arcade registry/meta tools

Do not append `?tool_recommendation=false` to the canonical plugin connection. That query parameter deliberately expands the full allowed tool list and defeats the compact-control-plane goal.

Historical stale gateway:
- `Langfuse`
- `gw_3L71MusJCi6qhXfztWzMyeYIJrp`

The historical gateway is a rollback/evidence resource only and must be retired only after the App-backed plugin binding to the canonical gateway is independently verified.
