---
name: arcade-dev-usage
description: Use whenever operating or diagnosing Arcade through the custom arcade.dev ChatGPT plugin: projects, organizations, gateways, MCP servers, OAuth providers, members, audit logs, hosted logs, docs, billing, or control-plane mutations.
---

# Arcade.dev through ChatGPT

This plugin is an Arcade **control/admin plane** for the authenticated user. It is not the consumer Arcade MCP gateway used by `try-arcade`.

Use the bundled upstream `scale-arcade` skill for product-level rollout and gateway design guidance. This local adapter defines how to execute that guidance through the actual `arcade-dev` ChatGPT tool surface.

## Route model

Keep these layers distinct:

```text
ChatGPT host/plugin exposure
        ->
arcade.dev control-plane connection
        ->
Arcade organization/project
        ->
Gateway / hosted or remote MCP server
        ->
downstream provider
```

A success or failure at one layer is evidence about that layer only.

In particular:

- `Arcade_GetWhoami` success proves the current ChatGPT session can reach the Arcade control plane; it does not prove another chat/session exposes the plugin.
- a gateway existing does not prove its tools are healthy or authorized for an end user;
- a registered remote MCP server does not prove the upstream provider succeeded;
- missing downstream evidence does not prove client, Arcade, server, or provider fault. Preserve `UNKNOWN` when attribution is not established.

## Establish context first

Before project-scoped work, use `Arcade_GetWhoami` when the active organization/project is not already proven in the current task.

Treat organization and project switches as scope changes. Use `Arcade_SwitchOrganization` or `Arcade_SwitchProject` only when the intended target is explicit from the user/task. After a switch, read the returned active scope and use it as the new session context.

Do not surface account IDs, emails, or private inventory unless they are necessary to answer the user's request.

## Prefer the narrowest read

Default to read-only inspection.

Common routes:

- gateways: `Arcade_ListMyGateways`;
- hosted/remote MCP servers: `Arcade_ListServers`;
- current OAuth provider configuration: `Arcade_ListOauthProviders`;
- project access: `Arcade_ListProjectMembers`;
- connected end-user OAuth sessions: `Arcade_ListConnectedUsers`;
- audit evidence: `Arcade_ListAuditLogs`;
- hosted server application logs: `Arcade_ListServerLogs`;
- product semantics/how-to: `Arcade_SearchDocs`;
- billing/usage only when requested: `Arcade_GetBillingOverview`.

Do not enumerate the entire tool catalog when a narrower read answers the question.

## Gateway versus server

Never conflate them.

A **server** is a tool-producing MCP server in a project. It may be Arcade Hosted or a registered Remote MCP server.

A **gateway** is a higher-level use-case endpoint exposing a curated set of tools from one or more servers.

Therefore:

```text
server existence != gateway exposure
gateway exposure != end-user authorization
authorization != successful upstream execution
```

## Hosted versus remote MCP

`Arcade_ListServerLogs` works only for Arcade Hosted / managed servers.

For a Remote MCP server, absence of application logs through that tool is an expected capability boundary, not proof that the remote server emitted no logs or failed to execute.

Use Arcade audit/gateway evidence plus the remote application's own observability surface when available.

## Documentation first for changing semantics

Arcade evolves quickly. When a question depends on current product behavior, supported clients, OAuth semantics, gateway configuration, server deployment, audit behavior, or limits, call `Arcade_SearchDocs` before implementing or asserting the behavior.

Do not implement from remembered Arcade behavior when fresh documentation can change the answer.

## Mutation boundary

Read current state first whenever it affects correctness.

State-changing tools include, among others:

- `Arcade_CreateGateway`;
- `Arcade_ModifyGateway`;
- `Arcade_AddServer`;
- `Arcade_InviteMembers`;
- organization/project switching when it changes the target scope.

Use them only when the user's current intent authorizes that specific change.

Destructive or revoking actions require explicit confirmation immediately before execution:

- `Arcade_DeleteGateway`;
- `Arcade_RemoveServer`;
- `Arcade_RemoveProjectMember`;
- `Arcade_RevokeConnectedUser`;
- `Arcade_RevokeInvitation`.

After an important write, read the affected resource back through an independent read route and report only the observed postcondition.

Tool capability never grants permission by itself.

## Authentication boundaries

Keep setup/admin authentication separate from end-user runtime authorization.

For Remote MCP servers, setup discovery may use administrator credentials while runtime tool calls can require per-end-user authentication. Do not treat successful setup discovery as proof that every end user is authorized.

Never ask the user to paste API keys, OAuth tokens, Authorization headers, session cookies, or secret values into chat.

## Failure isolation

Use the narrowest deterministic probe at the suspected boundary.

Suggested diagnostic order:

1. **ChatGPT/plugin exposure** — is the `arcade-dev` capability present in this session?
2. **Arcade control plane** — does `Arcade_GetWhoami` succeed?
3. **Scope** — is the expected organization/project active?
4. **Registry/configuration** — does the gateway/server/provider appear in the relevant list?
5. **Arcade execution/audit** — is there bounded audit evidence for the action?
6. **Application/provider** — inspect hosted logs or the remote/provider observability surface.

Do not use absence of step N+1 as affirmative evidence that step N is at fault.

If evidence is missing, conflicting, stale, or crosses an unobservable runtime boundary, report `UNKNOWN`, `DEGRADED`, or `REPROBE_REQUIRED` rather than guessing.

## Audit and observability

Arcade audit logs are control-plane evidence. They may establish who changed or executed a resource, when, and through which Arcade surface.

They are not automatically equivalent to:

- remote MCP application logs;
- downstream provider request logs;
- model/inference traces;
- ChatGPT host/plugin selection telemetry.

Correlate independent evidence when diagnosing an end-to-end agent application.

For cross-service agent applications, prefer an explicit correlation/trace identifier when the participating systems support one, but do not claim propagation until it is observed.

## Response ergonomics

- Keep the next action small and obvious.
- Do not dump raw account inventory unless requested.
- Name the layer that is actually proved by the evidence.
- Preserve exact resource IDs internally for follow-up actions, but avoid exposing unnecessary identifiers.
- When a write succeeds, include the meaningful postcondition rather than only the executor's success message.

