import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
CANARY = ROOT / "experiments" / "zenodo-timeweb-canary"
ZENODO_SRC = ROOT / "arcade" / "zenodo-account" / "src"
BASE_URL = "http://127.0.0.1:8765"
INGRESS_TOKEN = "synthetic-ingress-token"


def wait_for_health() -> None:
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"{BASE_URL}/healthz", timeout=1) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and payload == {"status": "ok"}:
                    return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("Timeweb canary health endpoint never became ready")


def post_mcp_status() -> tuple[int, str]:
    request = urllib.request.Request(
        f"{BASE_URL}/mcp",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def start_server(env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "server:app",
            "--app-dir",
            str(CANARY),
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def stop_server(proc: subprocess.Popen[str]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    if proc.returncode not in (0, -15) and proc.stdout:
        print(proc.stdout.read(), file=sys.stderr)


def verify_unconfigured_startup(base_env: dict[str, str]) -> None:
    env = base_env.copy()
    env.pop("ZENODO_ACCESS_TOKEN", None)
    env.pop("MCP_INGRESS_TOKEN", None)
    proc = start_server(env)
    try:
        wait_for_health()
        status, body = post_mcp_status()
        if status != 503 or "not_configured" not in body:
            raise RuntimeError(f"Unconfigured MCP boundary mismatch: {status} {body}")
        print("TIMEWEB_CANARY_UNCONFIGURED_PASS")
    finally:
        stop_server(proc)


def verify_unauthorized_boundary() -> None:
    status, body = post_mcp_status()
    if status != 401:
        raise RuntimeError(f"Unauthenticated MCP request status was {status}")
    if INGRESS_TOKEN in body:
        raise RuntimeError("Ingress token leaked in unauthorized response")
    print("TIMEWEB_CANARY_UNAUTH_PASS")


async def verify_mcp_tools() -> None:
    async with httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {INGRESS_TOKEN}"}
    ) as http_client:
        async with streamable_http_client(
            f"{BASE_URL}/mcp",
            http_client=http_client,
            terminate_on_close=False,
        ) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()

    names = [tool.name for tool in result.tools]
    if names != ["list_deposits", "get_deposit"]:
        raise RuntimeError(f"Unexpected Timeweb canary tool surface: {names}")
    print("TIMEWEB_CANARY_TOOLS=" + ",".join(names))


def main() -> None:
    base_env = os.environ.copy()
    base_env["PYTHONPATH"] = os.pathsep.join(
        [str(ZENODO_SRC), str(CANARY), base_env.get("PYTHONPATH", "")]
    )

    verify_unconfigured_startup(base_env)

    env = base_env.copy()
    env["ZENODO_ACCESS_TOKEN"] = "synthetic-zenodo-token"
    env["MCP_INGRESS_TOKEN"] = INGRESS_TOKEN
    proc = start_server(env)
    try:
        wait_for_health()
        print("TIMEWEB_CANARY_HEALTH_PASS")
        verify_unauthorized_boundary()
        asyncio.run(verify_mcp_tools())
        print("TIMEWEB_ZENODO_HTTP_SMOKE_PASS")
    finally:
        stop_server(proc)


if __name__ == "__main__":
    main()
