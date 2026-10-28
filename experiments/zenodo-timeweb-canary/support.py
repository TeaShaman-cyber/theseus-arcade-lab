import hmac
import json
import os
from collections.abc import Awaitable, Callable
from typing import Any

ASGIApp = Callable[[dict[str, Any], Callable[..., Awaitable[dict[str, Any]]], Callable[..., Awaitable[None]]], Awaitable[None]]


def resolve_secret(name: str, explicit: str | None = None) -> str:
    value = explicit if explicit is not None else os.environ.get(name, "")
    value = value.strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


class BearerGate:
    """Protect only the MCP endpoint with one static bearer secret."""

    def __init__(self, app: ASGIApp, expected_token: str) -> None:
        self._app = app
        self._expected_token = resolve_secret("MCP_INGRESS_TOKEN", expected_token)

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http" or scope.get("path", "").rstrip("/") != "/mcp":
            await self._app(scope, receive, send)
            return

        authorization = ""
        for key, value in scope.get("headers", []):
            if key.lower() == b"authorization":
                authorization = value.decode("latin-1")
                break

        prefix = "Bearer "
        supplied = authorization[len(prefix) :] if authorization.startswith(prefix) else ""
        if not supplied or not hmac.compare_digest(supplied, self._expected_token):
            body = json.dumps({"error": "unauthorized"}).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        await self._app(scope, receive, send)
