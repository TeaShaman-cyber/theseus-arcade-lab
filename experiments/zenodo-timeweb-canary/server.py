import asyncio
import os
from typing import Any

from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from theseus_zenodo_arcade.zenodo import ZenodoClient
from support import BearerGate, resolve_secret


async def healthz(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def build_app(*, zenodo_access_token: str | None = None, ingress_token: str | None = None):
    zenodo_token = resolve_secret("ZENODO_ACCESS_TOKEN", zenodo_access_token)
    mcp_ingress_token = resolve_secret("MCP_INGRESS_TOKEN", ingress_token)
    zenodo = ZenodoClient(zenodo_token)

    mcp = MCPServer("theseus-zenodo-timeweb")

    @mcp.tool()
    async def list_deposits() -> list[dict[str, Any]]:
        """List bounded metadata for unpublished Zenodo draft records."""
        return await asyncio.to_thread(zenodo.list_deposits)

    @mcp.tool()
    async def get_deposit(deposition_id: str) -> dict[str, Any]:
        """Read bounded metadata for one exact Zenodo draft record."""
        return await asyncio.to_thread(zenodo.get_deposit, deposition_id)

    mcp_app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        host="0.0.0.0",
    )
    mcp_app.routes.insert(0, Route("/healthz", healthz, methods=["GET"]))
    return BearerGate(mcp_app, mcp_ingress_token)


app = build_app()
