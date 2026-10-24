# theseus-arcade-lab

Public engineering lab for Arcade as an agent application execution and governance plane.

## Thesis

Arcade is useful here as more than an integration shim. It can provide a common control plane for agent-facing applications that combine hosted tools, remote MCP servers, identity, authorization, routing, and audit evidence.

```text
ChatGPT / agent client
        -> Arcade gateway / auth / policy
        -> hosted or remote MCP services
        -> provider systems
```

A future composition may combine services such as Timeweb, Neon, and Langfuse behind one governed agent workflow. This repository owns the Arcade composition/runtime pattern, not provider-specific semantics.

## Ownership boundary

This repository owns Arcade gateway/runtime patterns, hosted/remote MCP composition, ChatGPT-facing Arcade integration, identity/auth boundaries, observability/audit conventions, reusable multi-service agent applications, and source/provenance for custom Arcade plugin skills/adapters.

Provider-specific repositories remain authoritative for Timeweb, Neon, Langfuse, and other downstream systems.

## Core invariants

- Capability does not imply permission.
- Gateway, MCP server, remote server, hosted server, end-user auth, and provider authority remain distinct.
- Secrets and OAuth material never belong in Git, issue text, prompts, or durable public logs.
- Missing downstream evidence is not proof of a particular failure domain.
- External/upstream guidance is pinned by exact provenance when copied or adapted.
- Durable changes follow Issue -> branch -> deterministic QA -> PR -> hosted QA -> exact-head merge -> remote readback.

## Initial roadmap

1. Bootstrap repository guidance and QA (#1).
2. Mature the custom `arcade-dev` ChatGPT plugin with upstream Arcade guidance plus a thin route adapter (#2).
3. Define a reusable Arcade agent-application composition pattern.
4. Prototype one bounded multi-service composition, candidate: Timeweb + Neon + Langfuse.
5. Add cross-service observability and audit conventions.
