import asyncio
from typing import Annotated, Any

from arcade_mcp_server import Context, MCPApp
from arcade_mcp_server.auth import OAuth2

from theseus_zenodo_arcade.zenodo import ZenodoClient

ZENODO_OAUTH_PROVIDER_ID = "theseus-zenodo"
DEPOSIT_WRITE_SCOPE = "deposit:write"

app = MCPApp(name="theseus_zenodo", version="0.1.0", log_level="INFO")


@app.tool(requires_auth=OAuth2(id=ZENODO_OAUTH_PROVIDER_ID, scopes=[DEPOSIT_WRITE_SCOPE]))
async def list_deposits(
    context: Context,
) -> Annotated[list[dict[str, Any]], "Bounded metadata for the authenticated user's Zenodo deposits."]:
    """List the authenticated user's Zenodo deposits without publication authority."""
    token = context.get_auth_token_or_empty()
    if not token:
        raise ValueError("Zenodo authorization is required")
    return await asyncio.to_thread(ZenodoClient(token).list_deposits)


@app.tool(requires_auth=OAuth2(id=ZENODO_OAUTH_PROVIDER_ID, scopes=[DEPOSIT_WRITE_SCOPE]))
async def get_deposit(
    context: Context,
    deposition_id: Annotated[str, "Exact Zenodo draft record ID returned by list_deposits."],
) -> Annotated[dict[str, Any], "Bounded metadata for one exact Zenodo deposit."]:
    """Read one exact Zenodo deposit without publication authority."""
    token = context.get_auth_token_or_empty()
    if not token:
        raise ValueError("Zenodo authorization is required")
    return await asyncio.to_thread(ZenodoClient(token).get_deposit, deposition_id)


if __name__ == "__main__":
    app.run()
