import asyncio
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server.py"
SUPPORT = ROOT / "support.py"


def load_support():
    spec = importlib.util.spec_from_file_location("zenodo_timeweb_support", SUPPORT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ConfigTests(unittest.TestCase):
    def test_requires_zenodo_access_token(self):
        mod = load_support()
        with self.assertRaisesRegex(RuntimeError, "ZENODO_ACCESS_TOKEN"):
            mod.resolve_secret("ZENODO_ACCESS_TOKEN", "")

    def test_requires_ingress_token(self):
        mod = load_support()
        with self.assertRaisesRegex(RuntimeError, "MCP_INGRESS_TOKEN"):
            mod.resolve_secret("MCP_INGRESS_TOKEN", "")


class BearerGateTests(unittest.TestCase):
    def _call(self, header):
        mod = load_support()
        seen = {"called": False}

        async def inner(scope, receive, send):
            seen["called"] = True
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        gate = mod.BearerGate(inner, "expected-secret")
        messages = []
        headers = [] if header is None else [(b"authorization", header.encode())]
        scope = {"type": "http", "path": "/mcp", "headers": headers}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        asyncio.run(gate(scope, receive, send))
        return seen, messages

    def test_unconfigured_ingress_returns_503_without_calling_mcp(self):
        mod = load_support()
        seen = {"called": False}

        async def inner(scope, receive, send):
            seen["called"] = True

        gate = mod.BearerGate(inner, "")
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        asyncio.run(gate({"type": "http", "path": "/mcp", "headers": []}, receive, send))
        self.assertFalse(seen["called"])
        self.assertEqual(messages[0]["status"], 503)
        self.assertIn(b"not_configured", messages[1]["body"])

    def test_rejects_missing_bearer_without_calling_mcp(self):
        seen, messages = self._call(None)
        self.assertFalse(seen["called"])
        self.assertEqual(messages[0]["status"], 401)

    def test_rejects_wrong_bearer_without_echoing_secret(self):
        seen, messages = self._call("Bearer wrong-secret")
        self.assertFalse(seen["called"])
        self.assertEqual(messages[0]["status"], 401)
        encoded = repr(messages).encode()
        self.assertNotIn(b"wrong-secret", encoded)
        self.assertNotIn(b"expected-secret", encoded)

    def test_allows_exact_bearer(self):
        seen, messages = self._call("Bearer expected-secret")
        self.assertTrue(seen["called"])
        self.assertEqual(messages[0]["status"], 204)

    def test_health_endpoint_is_not_bearer_gated(self):
        mod = load_support()
        seen = {"called": False}

        async def inner(scope, receive, send):
            seen["called"] = True
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        gate = mod.BearerGate(inner, "expected-secret")
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        asyncio.run(gate({"type": "http", "path": "/healthz", "headers": []}, receive, send))
        self.assertTrue(seen["called"])
        self.assertEqual(messages[0]["status"], 200)


class StaticContractTests(unittest.TestCase):
    def test_timeweb_transport_is_stateless_json_streamable_http(self):
        text = SERVER.read_text(encoding="utf-8")
        self.assertIn('host="0.0.0.0"', text)
        self.assertIn("stateless_http=True", text)
        self.assertIn("json_response=True", text)
        self.assertIn('Route("/healthz"', text)

    def test_only_initial_read_tools_exist(self):
        text = SERVER.read_text(encoding="utf-8")
        self.assertIn("def list_deposits(", text)
        self.assertIn("def get_deposit(", text)
        self.assertEqual(text.count("@mcp.tool()"), 2)
        self.assertNotIn("deposit:actions", text)
        self.assertNotIn("publish_deposit", text)

    def test_secrets_are_environment_contracts_only(self):
        text = SERVER.read_text(encoding="utf-8")
        self.assertIn('read_optional_secret("ZENODO_ACCESS_TOKEN"', text)
        self.assertIn('resolve_secret("ZENODO_ACCESS_TOKEN"', text)
        self.assertIn('read_optional_secret("MCP_INGRESS_TOKEN"', text)
        self.assertNotIn("personal_access_token=", text)


if __name__ == "__main__":
    unittest.main()
