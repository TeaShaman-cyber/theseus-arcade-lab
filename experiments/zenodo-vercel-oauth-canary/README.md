# Zenodo Vercel OAuth canary

Issues #18 and #20: verify that the scoped Zenodo MCP and ChatGPT OAuth layer can run on Vercel Hobby without Arcade, an external auth SaaS, a new user password, or a separate Google/GitHub OAuth application, then expand the verified transport into a thin Zenodo draft-lifecycle shim.

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
- first-party MCP scope: `zenodo:read` (legacy connector transport scope; not the provider-capability boundary)
- `resource` is echoed into the token audience
- access and refresh tokens are signed by the canary's internal signing key

`zenodo:read` is retained for connector-session compatibility. It is a legacy transport scope name, not a statement that the MCP surface is read-only. Provider capability comes from the Zenodo PAT; consequential authority is controlled by explicit human approval.

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

## MCP surface

Read-only:
- `list_deposits`
- `get_deposit`
- `get_file`

Routine draft/version writes:
- `create_deposit`
- `update_deposit`
- `reserve_doi`
- `edit_published_deposit`
- `create_new_version`
- `import_previous_version_files`

Potentially destructive writes:
- `upload_file` — same-name replacement may destroy prior draft content
- `delete_file`
- `delete_draft`

All tools carry MCP `ToolAnnotations` describing read-only/write/destructive/idempotency properties. These annotations are advisory metadata, not a security mechanism; consequential/destructive calls still require explicit human approval in the controlling ChatGPT workflow.

### Publication boundary

The low-level Zenodo client contains the provider publish primitive, but **there is no raw agent-facing `publish_deposit(id)` MCP tool**.

Publication remains a separate GitHub-governed promotion workflow owned by `TeaShaman-cyber/theseus-research#96`:

```text
accepted GitHub artifact/release + exact provenance
  -> metadata/artifact verification
  -> explicit human approval
  -> provider publish primitive
  -> Zenodo DOI/record/file readback
  -> durable receipt back into GitHub
```

This keeps provider capability available without allowing a context-free deposition ID to bypass repository authority.

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

Do not describe the canary as fully OAuth-conformant until the single-use-code gap is resolved.
