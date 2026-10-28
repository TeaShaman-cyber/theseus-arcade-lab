# Zenodo Vercel OAuth canary

Issue #18 experiment: verify that the scoped Zenodo MCP and ChatGPT OAuth layer can run on Vercel Hobby without Arcade, an external auth SaaS, a new user password, or a separate Google/GitHub OAuth application.

## Human model

The same preview deployment is reached through two stable Vercel aliases:

```text
ChatGPT machine traffic -> public alias -> metadata / token / MCP
Browser authorization   -> protected alias -> Vercel Authentication -> /oauth/authorize
```

The protected authorization alias relies on the user's existing Vercel session. In the current Hobby team there is exactly one confirmed member, the owner, so successful Vercel Authentication is sufficient for this single-user canary. If team membership expands, replace this singleton invariant with explicit Vercel Passport identity verification.

No `OAUTH_APPROVAL_SECRET` exists. The user does not create or remember another password.

## OAuth client model

ChatGPT is a predefined **public OAuth client**:

- `client_id = chatgpt-theseus`
- authorization code + PKCE `S256`
- token endpoint auth method `none`
- no OAuth client secret
- `resource` is echoed into the token audience
- access and refresh tokens are signed by the canary's internal signing key

## Environment contract

Required:

- `OAUTH_ISSUER` — public OAuth/MCP alias
- `OAUTH_RESOURCE` — normally the same public alias
- `OAUTH_AUTHORIZATION_ORIGIN` — separate Vercel-protected alias
- `OAUTH_CLIENT_ID`
- `OAUTH_SIGNING_SECRET`
- `OAUTH_REDIRECT_URIS`
- `ZENODO_ACCESS_TOKEN`

The signing key is infrastructure state, not a user login credential.

## Routes

Public alias:
- `GET /.well-known/oauth-protected-resource`
- `GET /.well-known/oauth-authorization-server`
- `POST /oauth/token`
- `POST /mcp`

The code also exposes `/oauth/authorize`, but it refuses to issue a code unless the request origin exactly matches `OAUTH_AUTHORIZATION_ORIGIN`. This prevents the public alias from bypassing the Vercel human-authentication gate.

Protected authorization alias:
- `GET /oauth/authorize`

Vercel Authentication runs before the application sees the request.

## Known gaps before production-grade OAuth

1. Authorization codes are stateless and expire after five minutes but are not durably marked as consumed after redemption. OAuth requires single-use authorization codes.
2. The signing key must eventually become stable durable infrastructure state so refresh tokens survive redeploys.
3. Final ChatGPT UI connection remains the integration witness.

Do not describe the canary as fully OAuth-conformant until the single-use-code gap is resolved.
