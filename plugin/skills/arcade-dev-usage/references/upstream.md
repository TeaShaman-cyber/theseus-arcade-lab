# Upstream provenance

Official source: https://github.com/ArcadeAI/arcade-plugin
Pinned commit: `842c97051897cdb5ad72316ee242b74e99170483`
License: MIT

Bundled unchanged:
- `plugin/skills/scale-arcade/SKILL.md`
  - upstream git blob: `084363854731f851c0fc10373254fe2d28b47fe3`
- `plugin/skills/scale-arcade/references/arcade-docs.md`
  - upstream git blob: `a1e59b8fe55cf2587c64d7be03bf0cdbf5c01829`

License copy:
- upstream `LICENSE`
  - upstream git blob: `ddab4af7001c3e2fdf5bfc6a538b7835b27103da`

Intentionally not bundled as an active skill:
- `try-arcade`
  - upstream git blob: `92115cb7973cb1f28e2b1d942073c71d12798524`
  - reason: it assumes the consumer Arcade gateway with `Arcade_SelectTools` / `Arcade_UseTool`; the custom `arcade-dev` plugin exposes the admin/control-plane surface instead.

Local ChatGPT routing semantics live only in `skills/arcade-dev-usage/SKILL.md`.

