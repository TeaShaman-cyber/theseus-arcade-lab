import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Mapping


ACCESS_TOKEN_TTL_SECONDS = 3600
REFRESH_TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60
AUTHORIZATION_CODE_TTL_SECONDS = 300
REQUIRED_RESOURCE_SCOPE = "zenodo:read"


@dataclass(frozen=True)
class OAuthConfig:
    issuer: str
    resource: str
    client_id: str
    client_secret: str
    signing_secret: str
    approval_secret: str
    redirect_uris: tuple[str, ...]
    scopes: tuple[str, ...] = (REQUIRED_RESOURCE_SCOPE, "offline_access")

    def __post_init__(self) -> None:
        for name in ("issuer", "resource", "client_id", "client_secret", "signing_secret", "approval_secret"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required")
        if not self.issuer.startswith("https://") or not self.resource.startswith("https://"):
            raise ValueError("issuer and resource must use https")
        if not self.redirect_uris:
            raise ValueError("at least one redirect_uri is required")
        if REQUIRED_RESOURCE_SCOPE not in self.scopes:
            raise ValueError(f"{REQUIRED_RESOURCE_SCOPE} scope is required")


def oauth_protected_resource_metadata(config: OAuthConfig) -> dict:
    return {
        "resource": config.resource,
        "authorization_servers": [config.issuer],
        "scopes_supported": list(config.scopes),
    }


def oauth_authorization_server_metadata(config: OAuthConfig) -> dict:
    return {
        "issuer": config.issuer,
        "authorization_endpoint": config.issuer + "/oauth/authorize",
        "token_endpoint": config.issuer + "/oauth/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
        "scopes_supported": list(config.scopes),
        "authorization_response_iss_parameter_supported": True,
    }


def www_authenticate_challenge(config: OAuthConfig, scope: str = REQUIRED_RESOURCE_SCOPE) -> str:
    metadata = config.resource.rstrip("/") + "/.well-known/oauth-protected-resource"
    return f'Bearer resource_metadata="{metadata}", scope="{scope}"'


def validate_authorization_request(params: Mapping[str, str], config: OAuthConfig) -> dict:
    if params.get("response_type") != "code":
        raise ValueError("response_type must be code")
    if params.get("client_id") != config.client_id:
        raise ValueError("client_id is not allowed")
    redirect_uri = str(params.get("redirect_uri", ""))
    if redirect_uri not in config.redirect_uris:
        raise ValueError("redirect_uri is not allowed")
    if params.get("resource") != config.resource:
        raise ValueError("resource does not match protected resource")
    if params.get("code_challenge_method") != "S256":
        raise ValueError("PKCE code_challenge_method must be S256")
    challenge = str(params.get("code_challenge", ""))
    if not challenge:
        raise ValueError("PKCE code_challenge is required")
    state = str(params.get("state", ""))
    if not state:
        raise ValueError("state is required")

    requested_scopes = tuple(part for part in str(params.get("scope", "")).split() if part)
    if REQUIRED_RESOURCE_SCOPE not in requested_scopes:
        raise ValueError(f"scope must include {REQUIRED_RESOURCE_SCOPE}")
    unsupported = [scope for scope in requested_scopes if scope not in config.scopes]
    if unsupported:
        raise ValueError("unsupported scope: " + " ".join(unsupported))

    return {
        "client_id": config.client_id,
        "redirect_uri": redirect_uri,
        "resource": config.resource,
        "scopes": requested_scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }


def issue_authorization_code(request: Mapping[str, object], config: OAuthConfig, *, subject: str, now: int | None = None) -> str:
    issued = _now(now)
    claims = {
        "typ": "authorization_code",
        "iss": config.issuer,
        "aud": config.resource,
        "sub": subject,
        "client_id": config.client_id,
        "redirect_uri": request["redirect_uri"],
        "scope": " ".join(request["scopes"]),
        "code_challenge": request["code_challenge"],
        "code_challenge_method": "S256",
        "iat": issued,
        "nbf": issued,
        "exp": issued + AUTHORIZATION_CODE_TTL_SECONDS,
        "jti": secrets.token_urlsafe(18),
    }
    return _encode_signed(claims, config.signing_secret)


def exchange_authorization_code(form: Mapping[str, str], config: OAuthConfig, *, now: int | None = None) -> dict:
    if form.get("grant_type") != "authorization_code":
        raise ValueError("grant_type must be authorization_code")
    _verify_client(form, config)
    claims = _decode_signed(str(form.get("code", "")), config.signing_secret, now=now)
    if claims.get("typ") != "authorization_code":
        raise ValueError("invalid authorization code type")
    _verify_common_binding(claims, config)
    if form.get("redirect_uri") != claims.get("redirect_uri"):
        raise ValueError("redirect_uri does not match authorization code")
    if form.get("resource") != claims.get("aud"):
        raise ValueError("resource does not match authorization code")
    verifier = str(form.get("code_verifier", ""))
    if not verifier:
        raise ValueError("PKCE code_verifier is required")
    if not hmac.compare_digest(_pkce_challenge(verifier), str(claims.get("code_challenge", ""))):
        raise ValueError("PKCE verification failed")
    return _issue_token_response(claims, config, now=now)


def exchange_refresh_token(form: Mapping[str, str], config: OAuthConfig, *, now: int | None = None) -> dict:
    if form.get("grant_type") != "refresh_token":
        raise ValueError("grant_type must be refresh_token")
    _verify_client(form, config)
    claims = _decode_signed(str(form.get("refresh_token", "")), config.signing_secret, now=now)
    if claims.get("typ") != "refresh_token":
        raise ValueError("invalid refresh token type")
    _verify_common_binding(claims, config)
    if form.get("resource") != claims.get("aud"):
        raise ValueError("resource does not match refresh token")
    return _issue_token_response(claims, config, now=now)


def verify_access_token(token: str, config: OAuthConfig, *, now: int | None = None) -> dict:
    claims = _decode_signed(token, config.signing_secret, now=now)
    if claims.get("typ") != "access_token":
        raise ValueError("invalid access token type")
    if claims.get("iss") != config.issuer:
        raise ValueError("issuer mismatch")
    if claims.get("aud") != config.resource:
        raise ValueError("audience mismatch")
    if claims.get("client_id") != config.client_id:
        raise ValueError("client mismatch")
    scopes = str(claims.get("scope", "")).split()
    if REQUIRED_RESOURCE_SCOPE not in scopes:
        raise ValueError("required scope missing")
    return claims


def _issue_token_response(source_claims: Mapping[str, object], config: OAuthConfig, *, now: int | None) -> dict:
    issued = _now(now)
    scope = str(source_claims.get("scope", REQUIRED_RESOURCE_SCOPE))
    common = {
        "iss": config.issuer,
        "aud": config.resource,
        "sub": source_claims["sub"],
        "client_id": config.client_id,
        "scope": scope,
        "iat": issued,
        "nbf": issued,
    }
    access_claims = {
        **common,
        "typ": "access_token",
        "exp": issued + ACCESS_TOKEN_TTL_SECONDS,
        "jti": secrets.token_urlsafe(18),
    }
    response = {
        "access_token": _encode_signed(access_claims, config.signing_secret),
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_TTL_SECONDS,
        "scope": scope,
    }
    if "offline_access" in scope.split():
        refresh_claims = {
            **common,
            "typ": "refresh_token",
            "exp": issued + REFRESH_TOKEN_TTL_SECONDS,
            "jti": secrets.token_urlsafe(18),
        }
        response["refresh_token"] = _encode_signed(refresh_claims, config.signing_secret)
    return response


def _verify_client(form: Mapping[str, str], config: OAuthConfig) -> None:
    if form.get("client_id") != config.client_id:
        raise ValueError("client_id is invalid")
    supplied = str(form.get("client_secret", ""))
    if not supplied or not hmac.compare_digest(supplied, config.client_secret):
        raise ValueError("client authentication failed")


def _verify_common_binding(claims: Mapping[str, object], config: OAuthConfig) -> None:
    if claims.get("iss") != config.issuer:
        raise ValueError("issuer mismatch")
    if claims.get("aud") != config.resource:
        raise ValueError("audience mismatch")
    if claims.get("client_id") != config.client_id:
        raise ValueError("client mismatch")


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _encode_signed(claims: Mapping[str, object], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_part = _b64_json(header)
    claims_part = _b64_json(dict(claims))
    signing_input = (header_part + "." + claims_part).encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return header_part + "." + claims_part + "." + _b64(signature)


def _decode_signed(token: str, secret: str, *, now: int | None) -> dict:
    try:
        header_part, claims_part, signature_part = token.split(".")
        signing_input = (header_part + "." + claims_part).encode("ascii")
        supplied_signature = _unb64(signature_part)
        expected_signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("token signature is invalid")
        header = json.loads(_unb64(header_part))
        claims = json.loads(_unb64(claims_part))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("token is malformed") from exc
    if header != {"alg": "HS256", "typ": "JWT"}:
        raise ValueError("token header is invalid")
    current = _now(now)
    if int(claims.get("nbf", 0)) > current:
        raise ValueError("token is not active")
    if int(claims.get("exp", 0)) <= current:
        raise ValueError("token is expired")
    return claims


def _b64_json(value: Mapping[str, object]) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _b64(raw)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _now(explicit: int | None) -> int:
    return int(time.time()) if explicit is None else int(explicit)


class OAuthBearerGate:
    def __init__(self, app, config: OAuthConfig | None, *, now=None) -> None:
        self._app = app
        self._config = config
        self._now = now or (lambda: int(time.time()))

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http" or scope.get("path", "").rstrip("/") != "/mcp":
            await self._app(scope, receive, send)
            return

        if self._config is None:
            body = b'{"error":"not_configured"}'
            await send({
                "type": "http.response.start",
                "status": 503,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        authorization = ""
        for key, value in scope.get("headers", []):
            if key.lower() == b"authorization":
                authorization = value.decode("latin-1")
                break

        prefix = "Bearer "
        token = authorization[len(prefix):] if authorization.startswith(prefix) else ""
        try:
            if not token:
                raise ValueError("missing bearer token")
            claims = verify_access_token(token, self._config, now=self._now())
        except ValueError:
            body = b'{"error":"unauthorized"}'
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"www-authenticate", www_authenticate_challenge(self._config).encode("utf-8")),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        forwarded = dict(scope)
        forwarded["oauth_claims"] = claims
        await self._app(forwarded, receive, send)
