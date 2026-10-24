# Upstream provenance

Source repository: https://github.com/langfuse/skills
Pinned commit: `4429a94b309980e1cee2f5960c271e123347cb42`

Bundled upstream skills:
- `skills/langfuse`
- `skills/migrate-to-langfuse`

ChatGPT/Arcade-specific routing lives only in `skills/langfuse-arcade-usage/`.

Arcade consumer-gateway provenance:
- source: https://github.com/ArcadeAI/arcade-plugin
- pinned commit: `842c97051897cdb5ad72316ee242b74e99170483`
- official `try-arcade` is retained under `upstream/try-arcade/` as reference;
- active `try-langfuse-arcade` narrows its routing to the Langfuse-only gateway to avoid hijacking unrelated connected-app tasks.
