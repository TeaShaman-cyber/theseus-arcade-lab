# Zenodo Vercel OAuth canary

Issue #18 experiment: verify that the scoped Zenodo MCP and the OAuth layer required by a ChatGPT custom plugin can run on the same Vercel Hobby application without Arcade or another auth SaaS.

## Surface

- `GET /healthz`
- `GET /.well-known/oauth-protected-resource`
- `GET /.well-known/oauth-authorization-server`
- `GET|POST /oauth/authorize`
- `POST /oauth/token`
- `POST /mcp`

The OAuth path uses one predefined confidential client, authorization code + PKCE `S256`, the RFC 8707 `resource` value as the token audience, a human approval secret, access tokens, and refresh tokens. The MCP surface remains exactly two read-only tools: `list_deposits` and `get_deposit`.

## Environment contract

Required for OAuth:

- `OAUTH_ISSUER`
- `OAUTH_RESOURCE` (defaults to the issuer)
- `OAUTH_CLIENT_ID`
- `OAUTH_CLIENT_SECRET`
- `OAUTH_SIGNING_SECRET`
- `OAUTH_APPROVAL_SECRET`
- `OAUTH_REDIRECT_URIS` (comma-separated; defaults to ChatGPT's stable connector redirect)

Provider access remains separate:

- `ZENODO_ACCESS_TOKEN`

Do not commit any of these values. Automated and hosted canaries use synthetic values only.

## Current verification status

Verified on 2026-10-28 against a protected Vercel Hobby preview:

- OAuth protected-resource discovery;
- OAuth authorization-server discovery;
- human authorization page;
- authorization-code exchange with PKCE `S256`;
- refresh-token exchange;
- MCP `401` discovery challenge without an access token;
- MCP `initialize` and `tools/list` with the issued access token;
- exact tools `list_deposits,get_deposit`.

Marker: `LIVE_OAUTH_MCP_PASS`.

## Known gap before production-grade OAuth

The canary keeps authorization codes stateless. They expire after five minutes and are bound to client ID, exact redirect URI, resource, and PKCE challenge, but a successfully redeemed code is not durably marked as consumed. OAuth requires authorization codes to be single-use.

Do not describe this canary as fully OAuth-conformant until a durable one-time redemption mechanism is added and verified. Vercel Runtime Cache is not an acceptable substitute because it is ephemeral and regional.

The final ChatGPT custom-plugin connection remains a separate human/UI integration witness.
