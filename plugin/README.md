# arcade-dev plugin overlay

This directory is the public, reproducible skill overlay for the existing private App-backed `arcade.dev` ChatGPT plugin.

The private `.app.json` App binding is deliberately not stored here. Plugin Creator overlays these files onto the existing release while preserving that binding and MCP configuration.

Bundled skills:
- `scale-arcade` — copied unchanged from the pinned official Arcade Agent Plugin source.
- `arcade-dev-usage` — local adapter for the actual ChatGPT admin/control-plane tool surface.

`try-arcade` is intentionally not bundled because it assumes the consumer Arcade gateway (`Arcade_SelectTools` / `Arcade_UseTool`) rather than the `arcade-dev` admin/control plane.
