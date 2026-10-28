import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


class ZenodoAccountTests(unittest.TestCase):
    def setUp(self):
        from theseus_zenodo_arcade.zenodo import normalize_deposit

        self.normalize_deposit = normalize_deposit
        self.raw = {
            "id": "abc12-def34",
            "is_published": False,
            "created": "2026-10-28T12:00:00+00:00",
            "updated": "2026-10-28T12:05:00+00:00",
            "owner": 12345,
            "links": {
                "self_html": "https://zenodo.org/uploads/abc12-def34",
                "self": "https://zenodo.org/api/records/abc12-def34/draft",
                "publish": "https://zenodo.org/api/records/abc12-def34/draft/actions/publish",
            },
            "metadata": {
                "title": "Theseus v1.0.0",
                "description": "Accepted baseline",
                "upload_type": "other",
                "access_token": "metadata-secret-must-not-leak",
            },
            "pids": {"doi": {"identifier": "10.5281/zenodo.542201", "provider": "datacite"}},
            "files": {
                "enabled": True,
                "entries": [
                    {
                        "key": "theseus-research-v1.0.0.tar.gz",
                        "size": 48835,
                        "checksum": "abc123",
                        "access_token": "file-secret-must-not-leak",
                    }
                ],
            },
            "authorization": "Bearer secret-must-not-leak",
            "cookie": "session=secret-must-not-leak",
        }

    def test_normalize_deposit_returns_only_bounded_metadata(self):
        out = self.normalize_deposit(self.raw)
        self.assertEqual(out["id"], "abc12-def34")
        self.assertEqual(out["title"], "Theseus v1.0.0")
        self.assertFalse(out["is_published"])
        self.assertEqual(out["doi"], "10.5281/zenodo.542201")
        self.assertEqual(out["html_url"], "https://zenodo.org/uploads/abc12-def34")
        self.assertEqual(
            out["files"],
            [{"name": "theseus-research-v1.0.0.tar.gz", "size": 48835, "checksum": "abc123"}],
        )
        self.assertNotIn("owner", out)
        serialized = json.dumps(out, sort_keys=True)
        self.assertNotIn("/actions/publish", serialized)
        self.assertNotIn("\"publish\"", serialized)

    def test_normalize_deposit_never_returns_secret_values(self):
        serialized = json.dumps(self.normalize_deposit(self.raw), sort_keys=True)
        for secret in (
            "secret-must-not-leak",
            "metadata-secret-must-not-leak",
            "file-secret-must-not-leak",
            "Bearer",
            "session=",
            "access_token",
            "authorization",
            "cookie",
        ):
            self.assertNotIn(secret, serialized)

    def test_normalize_deposit_tolerates_sparse_provider_response(self):
        self.assertEqual(
            self.normalize_deposit({"id": "draft-7"}),
            {
                "id": "draft-7",
                "title": "",
                "is_published": False,
                "created": None,
                "updated": None,
                "doi": None,
                "html_url": None,
                "files": [],
            },
        )


class FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._payload


class ClientBoundaryTests(unittest.TestCase):
    def test_list_deposits_uses_bearer_auth_and_returns_normalized_records(self):
        from theseus_zenodo_arcade.zenodo import ZenodoClient

        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["authorization"] = request.get_header("Authorization")
            seen["timeout"] = timeout
            return FakeResponse({"hits": {"hits": [{"id": "one", "metadata": {"title": "One"}}, {"id": "two", "metadata": {"title": "Two"}}]}})

        result = ZenodoClient("super-secret-token", opener=opener).list_deposits()
        self.assertEqual(seen["url"], "https://zenodo.org/api/user/records?q=is_published%3Afalse&size=100")
        self.assertEqual(seen["authorization"], "Bearer super-secret-token")
        self.assertEqual(seen["timeout"], 30)
        self.assertEqual([item["id"] for item in result], ["one", "two"])
        self.assertNotIn("super-secret-token", json.dumps(result))

    def test_get_deposit_targets_exact_id_and_returns_bounded_metadata(self):
        from theseus_zenodo_arcade.zenodo import ZenodoClient

        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            return FakeResponse({"id": "abc12-def34", "metadata": {"title": "Exact"}, "owner": 999})

        result = ZenodoClient("token", opener=opener).get_deposit("abc12-def34")
        self.assertEqual(seen["url"], "https://zenodo.org/api/records/abc12-def34/draft")
        self.assertEqual(result["id"], "abc12-def34")
        self.assertEqual(result["title"], "Exact")
        self.assertNotIn("owner", result)


class ServerContractTests(unittest.TestCase):
    def test_server_declares_scoped_custom_oauth_without_publish_authority(self):
        server = ROOT / "src" / "theseus_zenodo_arcade" / "server.py"
        text = server.read_text(encoding="utf-8")
        self.assertIn('ZENODO_OAUTH_PROVIDER_ID = "theseus-zenodo"', text)
        self.assertIn('DEPOSIT_WRITE_SCOPE = "deposit:write"', text)
        self.assertIn("OAuth2(", text)
        self.assertIn("id=ZENODO_OAUTH_PROVIDER_ID", text)
        self.assertIn("scopes=[DEPOSIT_WRITE_SCOPE]", text)
        self.assertNotIn("deposit:actions", text)
        self.assertNotIn("publish_deposit", text)

    def test_server_exposes_only_list_and_get_tools_in_initial_slice(self):
        server = ROOT / "src" / "theseus_zenodo_arcade" / "server.py"
        text = server.read_text(encoding="utf-8")
        self.assertIn("async def list_deposits(", text)
        self.assertIn("async def get_deposit(", text)
        self.assertEqual(text.count("@app.tool("), 2)


if __name__ == "__main__":
    unittest.main()
