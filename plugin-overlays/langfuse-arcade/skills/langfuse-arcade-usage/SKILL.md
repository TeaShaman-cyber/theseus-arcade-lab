---
name: langfuse-arcade-usage
description: Use whenever Langfuse project data is accessed through the custom Arcade-backed ChatGPT plugin, especially for traces, observations, metrics, prompts, scores, datasets, evaluators, dashboards, or debugging the ChatGPT-to-Arcade-to-Langfuse path.
---

# Langfuse through Arcade in ChatGPT

This plugin routes `ChatGPT -> Arcade gateway -> Langfuse remote MCP -> Langfuse project data`.

Use the bundled official Langfuse skills for domain workflows and best practices. This adapter owns only the ChatGPT/Arcade execution route.

## Web/mobile compatibility invariant

The production `langfuse-arcade` plugin is App-backed. Preserve `.app.json` / the App binding and layer skills on top of it.

Do **not** add `mcp.json` or `.mcp.json` to the App-backed plugin package. A standalone package that embeds a remote MCP endpoint through those manifests is treated by the current ChatGPT host as **Desktop only**, even when the endpoint is public HTTPS.

If a newly-created Langfuse plugin is marked Desktop only, check packaging first: App-backed `.app.json` is the web/mobile path; portable remote-MCP packaging is diagnostic/desktop-only.

## Canonical gateway

Read `references/gateway.md` before diagnosing routing or changing the connection.

The canonical target is the `Langfuse Clean` gateway. Compact mode must use the base gateway URL without the `tool_recommendation=false` query parameter.

## Routing

Prefer Arcade Tool Recommendation when the connection exposes it:

1. call `Arcade_SelectTools` with one concise description of the Langfuse task;
2. use the returned exact tool name/schema through `Arcade_UseTool`;
3. repeat selection only for a genuinely different task.

This keeps the full Langfuse MCP surface out of the model's default tool context.

If the current ChatGPT runtime still exposes dozens of direct `Langfuse.*` tools and does not expose `Arcade_SelectTools` / `Arcade_UseTool`, classify that runtime as a legacy/direct connection or stale App binding. Direct tools may still be used for already-authorized work, but do not claim that the compact cutover is complete.

Use current Langfuse documentation for conceptual, SDK, API, instrumentation, and product guidance. Do not implement from memory when current docs matter.

Never ask the user to paste Langfuse API keys, Basic credentials, Arcade header secrets, OAuth tokens, or Authorization headers into chat.

## Default read path

Default to read-only inspection unless the user explicitly requests a change.

For trace-oriented work, prefer the modern observation tools:
1. locate relevant observations with the narrowest useful time window;
2. use compact fields first;
3. keep each observation window at or below 336 elapsed hours (14 days);
4. fetch full details only for selected observations;
5. for a known trace, filter observations by trace ID rather than relying on legacy trace APIs.

Common read intents:
- analytics / cost / latency / errors;
- prompts;
- scores;
- datasets and runs;
- evaluators / rules;
- project skills;
- health / schema.

Describe these intents to `Arcade_SelectTools`; do not hard-code a permanent Langfuse tool catalog in this adapter.

## Mutation boundary

Creating, updating, deleting, promoting labels, running paid evaluators, submitting feedback, or otherwise changing Langfuse state requires explicit user intent for that action.

Before a consequential write, read the current object/state when that affects correctness and preserve stable IDs and existing labels/tags unless the user asked to replace them.

After an important write, read the affected object or list back and report only the observed postcondition. If eventual consistency applies, say so rather than claiming immediate success.

For feedback submission, show the exact payload and obtain explicit permission immediately before sending it.

## Failure isolation

Keep these layers separate:
1. ChatGPT plugin exposure / cached tool surface;
2. Arcade OAuth/session;
3. Arcade gateway policy and Tool Recommendation mode;
4. Arcade project registry / remote-MCP discovery;
5. Arcade -> Langfuse upstream authentication;
6. Langfuse execution / project data.

Missing evidence at one layer is not affirmative evidence that another layer failed. Preserve `UNKNOWN`, `DEGRADED`, or `REPROBE_REQUIRED` when attribution is not proved.

## Response ergonomics

- Do not enumerate the full Langfuse tool catalog unless explicitly asked.
- Keep the next action small and obvious.
- Link to Langfuse UI resources when a tool returns a direct URL.
- Never place credentials or secret material in chat, Git issues, logs, or durable notes.
