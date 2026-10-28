import base64
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from oauth_support import (
    OAuthBearerGate,
    OAuthConfig,
    exchange_authorization_code,
    exchange_refresh_token,
    issue_authorization_code,
    oauth_authorization_server_metadata,
    oauth_protected_resource_metadata,
    validate_authorization_request,
    verify_access_token,
    www_authenticate_challenge,
)


ISSUER = "https://theseus-zenodo-oauth-canary-semyon-s-nakama.vercel.app"
AUTH_ORIGIN = "https://theseus-zenodo-oauth-login-semyon-s-nakama.vercel.app"
REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"


def challenge_for(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def config() -> OAuthConfig:
    return OAuthConfig(
        issuer=ISSUER,
        resource=ISSUER,
        authorization_origin=AUTH_ORIGIN,
        client_id="chatgpt-theseus",
        signing_secret="signing-secret-with-enough-entropy-for-tests",
        redirect_uris=(REDIRECT,),
        scopes=("zenodo:read", "offline_access"),
    )


class MetadataTests(unittest.TestCase):
    def test_protected_resource_points_to_public_oauth_issuer(self):
        metadata = oauth_protected_resource_metadata(config())
        self.assertEqual(metadata["resource"], ISSUER)
        self.assertEqual(metadata["authorization_servers"], [ISSUER])
        self.assertEqual(metadata["scopes_supported"], ["zenodo:read", "offline_access"])

    def test_authorization_endpoint_is_protected_alias_but_token_endpoint_is_public(self):
        metadata = oauth_authorization_server_metadata(config())
        self.assertEqual(metadata["issuer"], ISSUER)
        self.assertEqual(metadata["authorization_endpoint"], AUTH_ORIGIN + "/oauth/authorize")
        self.assertEqual(metadata["token_endpoint"], ISSUER + "/oauth/token")
        self.assertEqual(metadata["token_endpoint_auth_methods_supported"], ["none"])
        self.assertIn("S256", metadata["code_challenge_methods_supported"])
        self.assertIn("authorization_code", metadata["grant_types_supported"])
        self.assertIn("refresh_token", metadata["grant_types_supported"])
        self.assertTrue(metadata["authorization_response_iss_parameter_supported"])
        self.assertNotIn("registration_endpoint", metadata)
        self.assertNotIn("client_id_metadata_document_supported", metadata)

    def test_401_challenge_exposes_only_public_resource_metadata(self):
        challenge = www_authenticate_challenge(config())
        self.assertIn('resource_metadata="' + ISSUER + '/.well-known/oauth-protected-resource"', challenge)
        self.assertIn('scope="zenodo:read"', challenge)
        self.assertNotIn("signing-secret", challenge)


class AuthorizationRequestTests(unittest.TestCase):
    def base_params(self):
        verifier = "v" * 64
        return {
            "response_type": "code",
            "client_id": "chatgpt-theseus",
            "redirect_uri": REDIRECT,
            "resource": ISSUER,
            "scope": "zenodo:read offline_access",
            "state": "opaque-state",
            "code_challenge_method": "S256",
            "code_challenge": challenge_for(verifier),
        }, verifier

    def test_accepts_exact_chatgpt_authorization_request(self):
        params, _ = self.base_params()
        request = validate_authorization_request(params, config())
        self.assertEqual(request["client_id"], "chatgpt-theseus")
        self.assertEqual(request["resource"], ISSUER)
        self.assertEqual(request["redirect_uri"], REDIRECT)
        self.assertEqual(request["scopes"], ("zenodo:read", "offline_access"))

    def test_rejects_redirect_uri_not_on_exact_allowlist(self):
        params, _ = self.base_params()
        params["redirect_uri"] = "https://evil.example/callback"
        with self.assertRaisesRegex(ValueError, "redirect_uri"):
            validate_authorization_request(params, config())

    def test_rejects_wrong_resource(self):
        params, _ = self.base_params()
        params["resource"] = "https://other.example"
        with self.assertRaisesRegex(ValueError, "resource"):
            validate_authorization_request(params, config())

    def test_rejects_non_s256_pkce(self):
        params, _ = self.base_params()
        params["code_challenge_method"] = "plain"
        with self.assertRaisesRegex(ValueError, "S256"):
            validate_authorization_request(params, config())


class TokenTests(unittest.TestCase):
    def authorize(self, now=1_800_000_000):
        params, verifier = AuthorizationRequestTests().base_params()
        request = validate_authorization_request(params, config())
        code = issue_authorization_code(request, config(), subject="vercel-authenticated-user", now=now)
        return code, verifier

    def exchange(self, code, verifier, now=1_800_000_001):
        return exchange_authorization_code(
            {
                "grant_type": "authorization_code",
                "client_id": "chatgpt-theseus",
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": REDIRECT,
                "resource": ISSUER,
            },
            config(),
            now=now,
        )

    def test_public_client_code_exchange_uses_pkce_and_binds_audience(self):
        code, verifier = self.authorize()
        result = self.exchange(code, verifier)
        self.assertEqual(result["token_type"], "Bearer")
        self.assertEqual(result["expires_in"], 3600)
        self.assertIn("refresh_token", result)
        claims = verify_access_token(result["access_token"], config(), now=1_800_000_002)
        self.assertEqual(claims["aud"], ISSUER)
        self.assertEqual(claims["iss"], ISSUER)
        self.assertEqual(claims["sub"], "vercel-authenticated-user")
        self.assertEqual(claims["client_id"], "chatgpt-theseus")
        self.assertIn("zenodo:read", claims["scope"].split())

    def test_code_exchange_rejects_wrong_pkce_verifier(self):
        code, _ = self.authorize()
        with self.assertRaisesRegex(ValueError, "PKCE"):
            self.exchange(code, "x" * 64)

    def test_code_exchange_rejects_wrong_client_id(self):
        code, verifier = self.authorize()
        form = {
            "grant_type": "authorization_code",
            "client_id": "wrong-client",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": REDIRECT,
            "resource": ISSUER,
        }
        with self.assertRaisesRegex(ValueError, "client_id"):
            exchange_authorization_code(form, config(), now=1_800_000_001)

    def test_refresh_grant_requires_no_client_secret(self):
        code, verifier = self.authorize()
        first = self.exchange(code, verifier)
        refreshed = exchange_refresh_token(
            {
                "grant_type": "refresh_token",
                "client_id": "chatgpt-theseus",
                "refresh_token": first["refresh_token"],
                "resource": ISSUER,
            },
            config(),
            now=1_800_001_000,
        )
        self.assertNotEqual(first["access_token"], refreshed["access_token"])
        claims = verify_access_token(refreshed["access_token"], config(), now=1_800_001_001)
        self.assertEqual(claims["aud"], ISSUER)
        self.assertEqual(claims["sub"], "vercel-authenticated-user")

    def test_access_token_rejects_wrong_audience_even_with_valid_signature(self):
        code, verifier = self.authorize()
        result = self.exchange(code, verifier)
        other = OAuthConfig(
            issuer=ISSUER,
            resource="https://wrong-resource.example",
            authorization_origin=AUTH_ORIGIN,
            client_id="chatgpt-theseus",
            signing_secret="signing-secret-with-enough-entropy-for-tests",
            redirect_uris=(REDIRECT,),
            scopes=("zenodo:read", "offline_access"),
        )
        with self.assertRaisesRegex(ValueError, "audience"):
            verify_access_token(result["access_token"], other, now=1_800_000_002)


class OAuthBearerGateTests(unittest.TestCase):
    def _access_token(self):
        params, verifier = AuthorizationRequestTests().base_params()
        request = validate_authorization_request(params, config())
        code = issue_authorization_code(request, config(), subject="vercel-authenticated-user", now=1_800_000_000)
        return exchange_authorization_code(
            {
                "grant_type": "authorization_code",
                "client_id": "chatgpt-theseus",
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": REDIRECT,
                "resource": ISSUER,
            },
            config(),
            now=1_800_000_001,
        )["access_token"]

    def _call(self, header, *, now=1_800_000_002):
        seen = {"called": False, "claims": None}

        async def inner(scope, receive, send):
            seen["called"] = True
            seen["claims"] = scope.get("oauth_claims")
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        gate = OAuthBearerGate(inner, config(), now=lambda: now)
        messages = []
        headers = [] if header is None else [(b"authorization", header.encode())]
        scope = {"type": "http", "path": "/mcp", "headers": headers}

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        import asyncio
        asyncio.run(gate(scope, receive, send))
        return seen, messages

    def test_unconfigured_gate_fails_closed_with_503(self):
        seen = {"called": False}

        async def inner(scope, receive, send):
            seen["called"] = True

        gate = OAuthBearerGate(inner, None, now=lambda: 1_800_000_002)
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        import asyncio
        asyncio.run(gate({"type": "http", "path": "/mcp", "headers": []}, receive, send))
        self.assertFalse(seen["called"])
        self.assertEqual(messages[0]["status"], 503)
        self.assertIn(b"not_configured", messages[1]["body"])

    def test_missing_bearer_returns_discovery_challenge_without_calling_mcp(self):
        seen, messages = self._call(None)
        self.assertFalse(seen["called"])
        self.assertEqual(messages[0]["status"], 401)
        headers = dict(messages[0]["headers"])
        challenge = headers[b"www-authenticate"].decode()
        self.assertIn('/.well-known/oauth-protected-resource', challenge)
        self.assertIn('scope="zenodo:read"', challenge)

    def test_valid_access_token_reaches_mcp_with_verified_claims(self):
        token = self._access_token()
        seen, messages = self._call("Bearer " + token)
        self.assertTrue(seen["called"])
        self.assertEqual(messages[0]["status"], 204)
        self.assertEqual(seen["claims"]["sub"], "vercel-authenticated-user")
        self.assertEqual(seen["claims"]["aud"], ISSUER)


class ServerStaticContractTests(unittest.TestCase):
    def test_server_has_no_human_password_or_oauth_client_secret(self):
        text = (ROOT / "server.py").read_text(encoding="utf-8")
        self.assertNotIn("OAUTH_APPROVAL_SECRET", text)
        self.assertNotIn("OAUTH_CLIENT_SECRET", text)
        self.assertNotIn("approval_secret", text)
        self.assertNotIn("client_secret", text)

    def test_server_requires_separate_authorization_origin(self):
        text = (ROOT / "server.py").read_text(encoding="utf-8")
        self.assertIn("OAUTH_AUTHORIZATION_ORIGIN", text)
        self.assertIn("authorization_origin", text)
        self.assertIn("request.base_url", text)

    def test_server_exposes_draft_lifecycle_tools_with_risk_annotations(self):
        text = (ROOT / "server.py").read_text(encoding="utf-8")
        for name in [
            'list_deposits', 'get_deposit', 'create_deposit', 'update_deposit',
            'reserve_doi', 'get_file', 'upload_file', 'delete_file', 'delete_draft',
            'edit_published_deposit', 'create_new_version', 'import_previous_version_files',
        ]:
            self.assertIn(f'def {name}(', text)
        self.assertIn('ToolAnnotations', text)
        self.assertIn('read_only_hint=True', text)
        self.assertIn('destructive_hint=True', text)
        self.assertIn('destructive_hint=False', text)
        self.assertNotIn('def publish_deposit(', text)

    def test_publication_remains_separate_from_raw_agent_tool_surface(self):
        text = (ROOT / "server.py").read_text(encoding="utf-8")
        self.assertNotIn('@mcp.tool()\n    async def publish_deposit', text)
        client = (ROOT.parent.parent / 'arcade' / 'zenodo-account' / 'src' / 'theseus_zenodo_arcade' / 'zenodo.py').read_text(encoding='utf-8')
        self.assertIn('def publish_deposit(', client)


if __name__ == "__main__":
    unittest.main()
