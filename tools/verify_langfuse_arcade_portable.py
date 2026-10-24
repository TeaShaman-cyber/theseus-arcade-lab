from pathlib import Path
import json
import subprocess

root = Path(__file__).resolve().parents[1]
pkg = root / "plugin-overlays/langfuse-arcade-portable"

manifest = json.loads((pkg / "plugin.json").read_text(encoding="utf-8"))
assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
assert manifest["name"] == "langfuse-arcade-compact"
assert manifest["version"] == "0.1.0"
interface = manifest["extensions"]["com.openai"]["interface"]
assert interface["category"] == "Developer Tools"
assert len(interface["displayName"]) <= 30
assert len(interface["shortDescription"]) <= 30
assert interface["capabilities"] == []

mcp = json.loads((pkg / "mcp.json").read_text(encoding="utf-8"))
assert mcp["$schema"] == "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
server = mcp["mcpServers"]["langfuse-arcade"]
assert server["type"] == "streamable-http"
assert server["url"] == "https://api.arcade.dev/mcp/gw_3L7MRKPtAX27M5pBEobEz54PZMs"
assert "tool_recommendation=false" not in json.dumps(mcp)
assert not (pkg / ".app.json").exists()

for rel in [
    "skills/langfuse/SKILL.md",
    "skills/migrate-to-langfuse/SKILL.md",
    "skills/langfuse-arcade-usage/SKILL.md",
    "skills/langfuse-arcade-usage/references/gateway.md",
    "skills/langfuse-arcade-usage/references/upstream.md",
]:
    if not (pkg / rel).is_file():
        raise SystemExit(f"missing portable plugin file: {rel}")

lines = (pkg / "UPSTREAM.tsv").read_text(encoding="utf-8").splitlines()
if not lines or lines[0] != "commit\t4429a94b309980e1cee2f5960c271e123347cb42":
    raise SystemExit("unexpected Langfuse upstream commit provenance")
for line in lines[1:]:
    expected, upstream_path = line.split("\t", 1)
    rel = upstream_path.removeprefix("skills/")
    local = pkg / "skills" / rel
    if not local.is_file():
        raise SystemExit(f"missing pinned upstream file: {local}")
    actual = subprocess.check_output(["git", "hash-object", str(local)], text=True).strip()
    if actual != expected:
        raise SystemExit(f"upstream drift: {local}: {actual} != {expected}")

adapter = (pkg / "skills/langfuse-arcade-usage/SKILL.md").read_text(encoding="utf-8")
for needle in ["Arcade_SelectTools", "Arcade_UseTool", "legacy/direct connection"]:
    if needle not in adapter:
        raise SystemExit(f"compact adapter invariant missing: {needle}")


# Arcade consumer-gateway provenance and scoped adaptation.
arcade_commit = "842c97051897cdb5ad72316ee242b74e99170483"
arcade_files = {
    "upstream/try-arcade/SKILL.md": "92115cb7973cb1f28e2b1d942073c71d12798524",
    "upstream/try-arcade/references/arcade-docs.md": "a1e59b8fe55cf2587c64d7be03bf0cdbf5c01829",
    "third_party/ArcadeAI-arcade-plugin-LICENSE.txt": "ddab4af7001c3e2fdf5bfc6a538b7835b27103da",
}
for rel, expected in arcade_files.items():
    path = pkg / rel
    if not path.is_file():
        raise SystemExit(f"missing Arcade upstream file: {rel}")
    actual = subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()
    if actual != expected:
        raise SystemExit(f"Arcade upstream drift: {rel}: {actual} != {expected}")

scoped = (pkg / "skills/try-langfuse-arcade/SKILL.md").read_text(encoding="utf-8")
for needle in [
    "Arcade_SelectTools",
    "Arcade_UseTool",
    "Do not use this skill for email, calendar, Slack",
    "legacy/direct mode",
]:
    if needle not in scoped:
        raise SystemExit(f"scoped Arcade skill invariant missing: {needle}")
if (pkg / "skills/try-arcade").exists():
    raise SystemExit("broad upstream try-arcade must not be active in the Langfuse-only plugin")

print("LANGFUSE_ARCADE_PORTABLE_VERIFY_PASS")
