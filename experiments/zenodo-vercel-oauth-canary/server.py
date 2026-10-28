import asyncio
import os
from typing import Any
from urllib.parse import parse_qs, urlencode

from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

from oauth_support import (
    OAuthBearerGate,
    OAuthConfig,
    exchange_authorization_code,
    exchange_refresh_token,
    issue_authorization_code,
    oauth_authorization_server_metadata,
    oauth_protected_resource_metadata,
    validate_authorization_request,
)
from theseus_zenodo_arcade.zenodo import ZenodoClient


def _optional(name: str) -> str:
    return os.environ.get(name, "").strip()


def _required(name: str) -> str:
    value = _optional(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def load_oauth_config() -> OAuthConfig | None:
    required = {name: _optional(name) for name in ("OAUTH_ISSUER", "OAUTH_AUTHORIZATION_ORIGIN", "OAUTH_CLIENT_ID", "OAUTH_SIGNING_SECRET")}
    if not all(required.values()):
        return None
    issuer = required["OAUTH_ISSUER"].rstrip("/")
    resource = _optional("OAUTH_RESOURCE").rstrip("/") or issuer
    redirects = tuple(item.strip() for item in _optional("OAUTH_REDIRECT_URIS").split(",") if item.strip()) or ("https://chatgpt.com/connector_platform_oauth_redirect",)
    return OAuthConfig(
        issuer=issuer,
        resource=resource,
        authorization_origin=required["OAUTH_AUTHORIZATION_ORIGIN"].rstrip("/"),
        client_id=required["OAUTH_CLIENT_ID"],
        signing_secret=required["OAUTH_SIGNING_SECRET"],
        redirect_uris=redirects,
        scopes=("zenodo:read", "offline_access"),
    )


def _config_or_response():
    config = load_oauth_config()
    if config is None:
        return None, JSONResponse({"error": "not_configured"}, status_code=503)
    return config, None


async def healthz(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "oauth_configured": load_oauth_config() is not None})


async def protected_resource_metadata(_: Request):
    config, response = _config_or_response()
    return response if response is not None else JSONResponse(oauth_protected_resource_metadata(config))


async def authorization_server_metadata(_: Request):
    config, response = _config_or_response()
    return response if response is not None else JSONResponse(oauth_authorization_server_metadata(config))


async def authorize(request: Request):
    config, response = _config_or_response()
    if response is not None:
        return response

    # Vercel Authentication is the human identity gate. The same deployment is
    # also reachable through a public alias for machine endpoints, so never
    # issue authorization codes unless the request arrived through the exact
    # Vercel-protected authorization alias advertised in OAuth metadata.
    request_origin = str(request.base_url).rstrip("/")
    if request_origin != config.authorization_origin:
        return JSONResponse({"error": "authorization_origin_required"}, status_code=404)

    params = {key: value for key, value in request.query_params.items()}
    try:
        normalized = validate_authorization_request(params, config)
    except ValueError as exc:
        return JSONResponse({"error": "invalid_request", "error_description": str(exc)}, status_code=400)

    code = issue_authorization_code(normalized, config, subject="vercel-authenticated-user")
    query = urlencode({"code": code, "state": normalized["state"], "iss": config.issuer})
    separator = "&" if "?" in normalized["redirect_uri"] else "?"
    return RedirectResponse(normalized["redirect_uri"] + separator + query, status_code=302)


async def token(request: Request):
    config, response = _config_or_response()
    if response is not None:
        return response
    raw = (await request.body()).decode("utf-8")
    parsed = parse_qs(raw, keep_blank_values=True)
    form = {key: values[-1] for key, values in parsed.items()}
    grant_type = form.get("grant_type", "")
    try:
        if grant_type == "authorization_code":
            payload = exchange_authorization_code(form, config)
        elif grant_type == "refresh_token":
            payload = exchange_refresh_token(form, config)
        else:
            return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
    except ValueError as exc:
        status = 401 if "client_id" in str(exc).lower() else 400
        error = "invalid_client" if status == 401 else "invalid_grant"
        return JSONResponse({"error": error, "error_description": str(exc)}, status_code=status)
    return JSONResponse(payload, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})


def build_app():
    oauth_config = load_oauth_config()
    zenodo_token = _optional("ZENODO_ACCESS_TOKEN")
    mcp = MCPServer("theseus-zenodo-vercel-oauth")

    @mcp.tool()
    async def list_deposits() -> list[dict[str, Any]]:
        """List bounded metadata for unpublished Zenodo draft records."""
        zenodo = ZenodoClient(_required("ZENODO_ACCESS_TOKEN") if not zenodo_token else zenodo_token)
        return await asyncio.to_thread(zenodo.list_deposits)

    @mcp.tool()
    async def get_deposit(deposition_id: str) -> dict[str, Any]:
        """Read bounded metadata for one exact Zenodo draft record."""
        zenodo = ZenodoClient(_required("ZENODO_ACCESS_TOKEN") if not zenodo_token else zenodo_token)
        return await asyncio.to_thread(zenodo.get_deposit, deposition_id)

    mcp_app = mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True, host="0.0.0.0")
    mcp_app.routes.insert(0, Route("/healthz", healthz, methods=["GET"]))
    mcp_app.routes.insert(1, Route("/.well-known/oauth-protected-resource", protected_resource_metadata, methods=["GET"]))
    mcp_app.routes.insert(2, Route("/.well-known/oauth-authorization-server", authorization_server_metadata, methods=["GET"]))
    mcp_app.routes.insert(3, Route("/oauth/authorize", authorize, methods=["GET"]))
    mcp_app.routes.insert(4, Route("/oauth/token", token, methods=["POST"]))
    return OAuthBearerGate(mcp_app, oauth_config)


app = build_app()
