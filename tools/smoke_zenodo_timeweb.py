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
                    print("TIMEWEB_CANARY_HEALTH_PASS")
                    return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("Timeweb canary health endpoint never became ready")


def verify_unauthorized_boundary() -> None:
    request = urllib.request.Request(
        f"{BASE_URL}/mcp",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            body = exc.read().decode("utf-8")
            if "synthetic-ingress-token" in body:
                raise RuntimeError("Ingress token leaked in unauthorized response")
            print("TIMEWEB_CANARY_UNAUTH_PASS")
            return
        raise
    raise RuntimeError("Unauthenticated MCP request was accepted")


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
    print("TIMEWEB_ZENODO_HTTP_SMOKE_PASS")


def main() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ZENODO_SRC), str(CANARY), env.get("PYTHONPATH", "")]
    )
    env["ZENODO_ACCESS_TOKEN"] = "synthetic-zenodo-token"
    env["MCP_INGRESS_TOKEN"] = INGRESS_TOKEN

    proc = subprocess.Popen(
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

    try:
        wait_for_health()
        verify_unauthorized_boundary()
        asyncio.run(verify_mcp_tools())
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

        if proc.returncode not in (0, -15) and proc.stdout:
            print(proc.stdout.read(), file=sys.stderr)


if __name__ == "__main__":
    main()
