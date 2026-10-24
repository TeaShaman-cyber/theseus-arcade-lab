---
name: try-langfuse-arcade
description: Use when accessing Langfuse through the compact Arcade gateway, especially when the request describes a Langfuse outcome rather than a specific tool: traces, observations, metrics, prompts, scores, datasets, evaluators, dashboards, health, or project diagnostics.
---

# Use Langfuse through the compact Arcade gateway

This is a Langfuse-scoped adaptation of Arcade's official `try-arcade` consumer-gateway workflow.

Do not use this skill for email, calendar, Slack, generic connected-app work, or Arcade administration. Those belong to their own plugins/routes.

## Gateway loop

When `Arcade_SelectTools` and `Arcade_UseTool` are exposed:

1. Call `Arcade_SelectTools` with one concise plain-language description of the whole Langfuse job.
2. Use the returned exact tool name, schema, and query ID with `Arcade_UseTool`.
3. Re-select only when the task materially changes.
4. Retrieve deferred/large results through the Arcade result route if the gateway exposes one.

Do not enumerate the full Langfuse catalog or ask the user to pick a tool/schema.

## Connection state

If the gateway or Langfuse app reports that authentication/connection is required:

- tell the user which connection needs repair;
- present the host-provided sign-in action/link when available;
- stop until the user confirms connection;
- retry the same bounded operation once.

Never ask for OAuth tokens, Langfuse API keys, Basic credentials, Arcade secrets, or Authorization headers in chat.

## Read/write boundary

Read-only Langfuse inspection is the default.

Before any external mutation (create/update/delete, evaluator execution with cost, feedback submission, prompt label promotion, dataset mutation, etc.), follow the bundled Langfuse skill's approval requirements and obtain explicit current user intent for that action.

After an important write, read the affected object/state back before claiming success.

## Failure semantics

Keep these layers separate:

```text
ChatGPT plugin exposure
  -> Arcade gateway/session
  -> Tool Recommendation/index
  -> Langfuse remote MCP/auth
  -> Langfuse execution/data
```

A missing or failed signal at one layer is not proof that another failed. Preserve `UNKNOWN`, `DEGRADED`, or `REPROBE_REQUIRED` when evidence is insufficient.

If the current runtime exposes dozens of direct `Langfuse.*` tools but no `Arcade_SelectTools` / `Arcade_UseTool`, treat it as legacy/direct mode rather than pretending compact mode is active.

## Arcade product questions

For current Arcade gateway behavior or Tool Recommendation semantics, read `references/arcade-docs.md` and then the relevant current Arcade docs page. Do not implement changing Arcade semantics from memory.
