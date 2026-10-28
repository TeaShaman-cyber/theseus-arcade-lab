# Zenodo through Arcade

Issue: #11

## Purpose

Provide a thin authenticated bridge from agent clients through Arcade to a user's Zenodo deposit workspace without giving the model an access token and without granting publication authority in the initial slice.

```text
ChatGPT / agent client
  -> Arcade gateway
  -> theseus_zenodo hosted tool server
  -> Arcade OAuth provider: theseus-zenodo
  -> Zenodo
```

Git/GitHub remains authority for Theseus source state. Zenodo remains the publication/archive service. Arcade is the execution and authorization plane between the agent and Zenodo.

## Current upstream contracts checked 2026-10-28

Zenodo developer documentation:

- REST API base: `https://zenodo.org/api`
- authenticated current-user draft list: `GET /api/user/records?q=is_published:false`
- exact draft read: `GET /api/records/{id}/draft`
- bearer token authentication is recommended
- `deposit:write` grants deposition write access but does not grant publication
- `deposit:actions` covers publish/edit/discard actions

Sources:

- https://support.zenodo.org/help/en-gb/31-api/209-what-is-the-difference-between-the-legacy-api-and-the-rest-api
- https://inveniordm.docs.cern.ch/reference/rest_api_drafts_records/
- https://developers.zenodo.org/ (legacy API/auth scope reference still supported by Zenodo)
- https://github.com/zenodo/zenodo-rdm/issues/878 (OAuth authorize/token endpoint evidence)

Arcade documentation:

- custom OAuth2 providers support authorization-code flow;
- custom MCP tools declare `OAuth2(id=..., scopes=[...])`;
- Arcade injects the user's access token into runtime context rather than returning it to the MCP client/model.

Sources:

- https://docs.arcade.dev/en/references/auth-providers/oauth2
- https://docs.arcade.dev/en/build/create-tools/tool-basics/create-tool-auth

## API selection

Zenodo states that the documented `/api/deposit/depositions` interface is the legacy API retained for compatibility, while the current UI uses the InvenioRDM REST API. This adapter therefore targets the current user-record/draft routes and does not depend on the legacy deposition routes.

The initial list call is intentionally bounded to unpublished drafts and at most 100 results:

```text
GET /api/user/records?q=is_published:false&size=100
```

## Provider contract

Provider ID:

```text
theseus-zenodo
```

Initial scope:

```text
deposit:write
```

Current Zenodo OAuth endpoint evidence:

```text
Authorization endpoint: https://zenodo.org/oauth/authorize
Token endpoint:         https://zenodo.org/oauth/token
```

Arcade's custom-provider form also requires a refresh-token endpoint. Zenodo refresh-token behavior has not yet been independently verified for this integration, so refresh semantics remain `UNKNOWN` until the first authorization is exercised. Do not claim refresh support from the presence of the form field alone.

## Registration sequence

1. Open Arcade Dashboard -> Connections -> OAuth providers -> Add OAuth Provider -> Custom Provider.
2. Choose provider ID `theseus-zenodo`.
3. Obtain the Arcade-generated redirect URI from the provider setup flow.
4. In Zenodo -> Account -> Applications -> New application, create the OAuth application using that exact redirect URI.
5. Copy the resulting Zenodo client ID and client secret into Arcade's provider configuration. Never place either value in Git, issues, chat, CI logs, or workflow inputs.
6. Configure the authorization/token endpoints above and request only `deposit:write` for this slice.
7. Complete one user authorization challenge.
8. Read back the configured provider through Arcade and verify that the connected user's granted scope is exactly the expected bounded scope.
9. Only after server deployment and tool discovery, add the two read tools to a dedicated Zenodo gateway or another explicitly chosen gateway.

## Runtime result boundary

Tool results are allow-listed to:

- deposit ID;
- title;
- publication state (`is_published`);
- created/updated timestamps;
- pre-reserved DOI when present;
- deposit HTML URL;
- bounded file name/size/checksum summaries.

The adapter intentionally drops provider ownership metadata, action URLs such as publish, authorization material, cookies, and unknown response fields.

## Publication boundary

This initial package has no `deposit:actions` scope and no publish function.

A future publish capability requires a separate explicit change because publication creates a public durable research artifact/DOI boundary. Preparing a draft must not silently become authority to publish it.

## Deployment/currentness

Hosted deployment is not proof of provider authorization. Provider authorization is not proof of gateway exposure. Gateway exposure is not proof of a successful Zenodo read.

Verify each layer separately:

```text
server deployed
  -> provider configured
  -> user authorized
  -> tools discovered
  -> gateway exposes tools
  -> authenticated read succeeds
```
