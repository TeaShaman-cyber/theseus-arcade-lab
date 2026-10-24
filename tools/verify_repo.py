from pathlib import Path

required = {
    "README.md": ["Capability does not imply permission", "Initial roadmap"],
    "AGENTS.md": ["tools/dev/check", "UNKNOWN"],
    "docs/architecture.md": ["execution/governance plane", "Timeweb", "Neon", "Langfuse"],
}

for name, needles in required.items():
    path = Path(name)
    if not path.is_file():
        raise SystemExit(f"missing required file: {name}")
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"{name}: missing invariant: {needle}")

print("REPO_VERIFY_PASS")


gateway = Path("plugin-overlays/langfuse-arcade/references/gateway.md").read_text(encoding="utf-8")
for needle in [
    "gw_3L7MRKPtAX27M5pBEobEz54PZMs",
    "https://api.arcade.dev/mcp/gw_3L7MRKPtAX27M5pBEobEz54PZMs",
    "Do not append `?tool_recommendation=false`",
    "gw_3L71MusJCi6qhXfztWzMyeYIJrp",
]:
    if needle not in gateway:
        raise SystemExit(f"Langfuse gateway invariant missing: {needle}")


adapter = Path("plugin-overlays/langfuse-arcade/skills/langfuse-arcade-usage/SKILL.md").read_text(encoding="utf-8")
for needle in [
    "Arcade_SelectTools",
    "Arcade_UseTool",
    "legacy/direct connection",
    "do not claim that the compact cutover is complete",
    "Web/mobile compatibility invariant",
    "Do **not** add `mcp.json` or `.mcp.json`",
    "Desktop only",
]:
    if needle not in adapter:
        raise SystemExit(f"Langfuse adapter invariant missing: {needle}")
