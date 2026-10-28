import ast
from pathlib import Path

root = Path(__file__).resolve().parents[1]
package = root / "arcade" / "zenodo-account"
required = [
    package / "pyproject.toml",
    package / "README.md",
    package / "src" / "theseus_zenodo_arcade" / "server.py",
    package / "src" / "theseus_zenodo_arcade" / "zenodo.py",
    package / "tests" / "test_zenodo_account.py",
    root / "docs" / "zenodo-arcade.md",
    root / ".github" / "workflows" / "deploy-zenodo-arcade.yml",
]
for path in required:
    if not path.is_file():
        raise SystemExit(f"missing Zenodo adapter file: {path.relative_to(root)}")

for path in package.rglob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

server = (package / "src" / "theseus_zenodo_arcade" / "server.py").read_text(encoding="utf-8")
for needle in [
    'ZENODO_OAUTH_PROVIDER_ID = "theseus-zenodo"',
    'DEPOSIT_WRITE_SCOPE = "deposit:write"',
    "OAuth2(id=ZENODO_OAUTH_PROVIDER_ID, scopes=[DEPOSIT_WRITE_SCOPE])",
    "async def list_deposits(",
    "async def get_deposit(",
]:
    if needle not in server:
        raise SystemExit(f"Zenodo server contract missing: {needle}")
for forbidden in ["deposit:actions", "publish_deposit"]:
    if forbidden in server:
        raise SystemExit(f"Zenodo server exceeds initial authority: {forbidden}")

client = (package / "src" / "theseus_zenodo_arcade" / "zenodo.py").read_text(encoding="utf-8")
for needle in [
    "/user/records?q=is_published%3Afalse&size=100",
    '/records/{encoded_id}/draft',
]:
    if needle not in client:
        raise SystemExit(f"Zenodo current-API route missing: {needle}")
if "/deposit/depositions" in client:
    raise SystemExit("legacy Zenodo deposition API must not be used by the initial adapter")

workflow = (root / ".github" / "workflows" / "deploy-zenodo-arcade.yml").read_text(encoding="utf-8")
if "arcade deploy -e src/theseus_zenodo_arcade/server.py --secrets skip" not in workflow:
    raise SystemExit("Zenodo hosted deploy entrypoint missing")

print("ZENODO_ARCADE_VERIFY_PASS")
