# AGENTS.md

This is a public, project-owned infrastructure/research repository.

## Workflow

- Create or reuse one narrow Issue before durable architecture, implementation, automation, routing, permission, persistence, or cross-cutting changes.
- Start from current `origin/main` on a narrow branch.
- Prefer small reversible changes.
- Run `tools/dev/check` before promotion.
- Open a PR linked to the Issue.
- Require hosted QA on the exact PR head before merge.
- Re-check exact head/base before merge and read back `origin/main` after merge.

## Safety and authority

- Capability is not permission.
- Keep Arcade project/gateway authority separate from downstream provider authority.
- Never commit API keys, OAuth tokens, session cookies, authorization headers, secret values, private account inventory, or generated credentials.
- Public evidence should use bounded non-secret receipts.
- Do not infer a downstream failure from missing evidence; preserve `UNKNOWN` when attribution is not proved.

## Upstream material

- Pin copied/adapted upstream material to an exact commit or blob SHA.
- Preserve required license and attribution.
- Keep local adapters separate from copied upstream semantics.
- Re-check current Arcade docs when product semantics can drift.
