from pathlib import Path
import json
import subprocess

root = Path(__file__).resolve().parents[1]
plugin = root / "plugin"

manifest = json.loads((plugin / ".codex-plugin/plugin.json").read_text())
assert manifest["name"] == "dev-6adbc7118d948191af9a907f79bca7a3"
assert manifest["version"] == "1.0.1"
assert manifest["skills"] == "./skills"
assert manifest["apps"] == "./.app.json"

expected_blobs = {
    "skills/scale-arcade/SKILL.md": "084363854731f851c0fc10373254fe2d28b47fe3",
    "skills/scale-arcade/references/arcade-docs.md": "a1e59b8fe55cf2587c64d7be03bf0cdbf5c01829",
    "third_party/ArcadeAI-arcade-plugin-LICENSE.txt": "ddab4af7001c3e2fdf5bfc6a538b7835b27103da",
}

for rel, expected in expected_blobs.items():
    path = plugin / rel
    if not path.is_file():
        raise SystemExit(f"missing upstream file: {rel}")
    actual = subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()
    if actual != expected:
        raise SystemExit(f"upstream drift: {rel}: {actual} != {expected}")

adapter = (plugin / "skills/arcade-dev-usage/SKILL.md").read_text()
for needle in [
    "control/admin plane",
    "Gateway versus server",
    "Hosted versus remote MCP",
    "Arcade_SearchDocs",
    "UNKNOWN",
    "read the affected resource back",
]:
    if needle not in adapter:
        raise SystemExit(f"adapter missing invariant: {needle}")

if (plugin / ".app.json").exists():
    raise SystemExit("public overlay must not contain private App binding")

print("PLUGIN_OVERLAY_VERIFY_PASS")

