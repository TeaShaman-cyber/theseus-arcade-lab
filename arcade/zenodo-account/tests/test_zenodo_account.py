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


class LifecycleClientTests(unittest.TestCase):
    def test_create_deposit_posts_current_api_draft_payload(self):
        from theseus_zenodo_arcade.zenodo import ZenodoClient

        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["method"] = request.get_method()
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"id": "draft-new", "metadata": seen["body"]["metadata"], "files": {"enabled": True, "entries": []}})

        result = ZenodoClient("token", opener=opener).create_deposit(
            {"title": "Canary draft", "resource_type": {"id": "other"}},
            files_enabled=True,
        )
        self.assertEqual(seen["url"], "https://zenodo.org/api/records")
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(seen["body"]["metadata"]["title"], "Canary draft")
        self.assertEqual(seen["body"]["files"], {"enabled": True})
        self.assertEqual(result["id"], "draft-new")

    def test_update_deposit_preserves_existing_pids_and_writable_state(self):
        from theseus_zenodo_arcade.zenodo import ZenodoClient

        calls = []
        existing = {
            "id": "draft-1",
            "metadata": {"title": "Old", "description": "Keep"},
            "files": {"enabled": True},
            "access": {"record": "public", "files": "public"},
            "pids": {"doi": {"identifier": "10.5281/zenodo.1", "provider": "datacite"}},
            "custom_fields": {"journal:journal": {"title": "Example"}},
        }

        def opener(request, timeout):
            calls.append((request.full_url, request.get_method(), request.data))
            if len(calls) == 1:
                return FakeResponse(existing)
            body = json.loads(request.data.decode("utf-8"))
            self.assertEqual(body["pids"], existing["pids"])
            self.assertEqual(body["access"], existing["access"])
            self.assertEqual(body["files"], existing["files"])
            self.assertEqual(body["custom_fields"], existing["custom_fields"])
            self.assertEqual(body["metadata"]["title"], "Updated")
            self.assertEqual(body["metadata"]["description"], "Keep")
            return FakeResponse({**existing, **body})

        result = ZenodoClient("token", opener=opener).update_deposit("draft-1", {"title": "Updated"})
        self.assertEqual(calls[0][:2], ("https://zenodo.org/api/records/draft-1/draft", "GET"))
        self.assertEqual(calls[1][:2], ("https://zenodo.org/api/records/draft-1/draft", "PUT"))
        self.assertEqual(result["title"], "Updated")
        self.assertEqual(result["doi"], "10.5281/zenodo.1")

    def test_reserve_doi_posts_pid_endpoint_and_reads_back_draft(self):
        from theseus_zenodo_arcade.zenodo import ZenodoClient

        calls = []

        def opener(request, timeout):
            calls.append((request.full_url, request.get_method()))
            if len(calls) == 1:
                return FakeResponse({"id": "doi"})
            return FakeResponse({"id": "draft-2", "metadata": {"title": "DOI draft"}, "pids": {"doi": {"identifier": "10.5281/zenodo.2"}}})

        result = ZenodoClient("token", opener=opener).reserve_doi("draft-2")
        self.assertEqual(calls[0], ("https://zenodo.org/api/records/draft-2/draft/pids/doi", "POST"))
        self.assertEqual(calls[1], ("https://zenodo.org/api/records/draft-2/draft", "GET"))
        self.assertEqual(result["doi"], "10.5281/zenodo.2")

    def test_upload_file_initializes_puts_content_commits_and_returns_file_metadata(self):
        from theseus_zenodo_arcade.zenodo import ZenodoClient

        calls = []

        def opener(request, timeout):
            calls.append((request.full_url, request.get_method(), request.data, request.get_header("Content-type")))
            if len(calls) == 1:
                self.assertEqual(json.loads(request.data.decode("utf-8")), [{"key": "artifact.txt"}])
                return FakeResponse({"entries": [{"key": "artifact.txt", "status": "pending"}]})
            if len(calls) == 2:
                self.assertEqual(request.data, b"hello")
                return FakeResponse({"key": "artifact.txt", "status": "pending"})
            if len(calls) == 3:
                return FakeResponse({"key": "artifact.txt", "size": 5, "checksum": "md5:5d41402abc4b2a76b9719d911017c592"})
            return FakeResponse({"key": "artifact.txt", "size": 5, "checksum": "md5:5d41402abc4b2a76b9719d911017c592"})

        result = ZenodoClient("token", opener=opener).upload_file("draft-3", "artifact.txt", b"hello")
        self.assertEqual(calls[0][:2], ("https://zenodo.org/api/records/draft-3/draft/files", "POST"))
        self.assertEqual(calls[1][:2], ("https://zenodo.org/api/records/draft-3/draft/files/artifact.txt/content", "PUT"))
        self.assertEqual(calls[2][:2], ("https://zenodo.org/api/records/draft-3/draft/files/artifact.txt/commit", "POST"))
        self.assertEqual(calls[3][:2], ("https://zenodo.org/api/records/draft-3/draft/files/artifact.txt", "GET"))
        self.assertEqual(result["name"], "artifact.txt")
        self.assertEqual(result["size"], 5)

    def test_delete_file_and_delete_draft_use_exact_destructive_routes(self):
        from theseus_zenodo_arcade.zenodo import ZenodoClient

        calls = []

        def opener(request, timeout):
            calls.append((request.full_url, request.get_method()))
            return FakeResponse({})

        client = ZenodoClient("token", opener=opener)
        self.assertEqual(client.delete_file("draft-4", "a b.txt"), {"deleted": True, "deposition_id": "draft-4", "file": "a b.txt"})
        self.assertEqual(client.delete_draft("draft-4"), {"deleted": True, "deposition_id": "draft-4"})
        self.assertEqual(calls[0], ("https://zenodo.org/api/records/draft-4/draft/files/a%20b.txt", "DELETE"))
        self.assertEqual(calls[1], ("https://zenodo.org/api/records/draft-4/draft", "DELETE"))

    def test_edit_new_version_import_and_publish_primitives_use_current_routes(self):
        from theseus_zenodo_arcade.zenodo import ZenodoClient

        calls = []

        def opener(request, timeout):
            calls.append((request.full_url, request.get_method()))
            return FakeResponse({"id": "next-draft", "metadata": {"title": "Version"}})

        client = ZenodoClient("token", opener=opener)
        client.edit_published_deposit("published-1")
        client.create_new_version("published-1")
        client.import_previous_version_files("next-draft")
        client.publish_deposit("next-draft")
        self.assertEqual(
            calls,
            [
                ("https://zenodo.org/api/records/published-1/draft", "POST"),
                ("https://zenodo.org/api/records/published-1/versions", "POST"),
                ("https://zenodo.org/api/records/next-draft/draft/actions/files-import", "POST"),
                ("https://zenodo.org/api/records/next-draft/draft/actions/publish", "POST"),
            ],
        )
