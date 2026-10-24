# Architecture

## Arcade role

Treat Arcade as an agent application execution/governance plane rather than as authority over every downstream service.

```text
client
  -> Arcade exposure / gateway / auth / policy
  -> hosted or remote MCP server
  -> downstream provider
```

Each edge is independently observable and independently fallible.

## Composition rule

Multi-service applications may compose several provider capabilities through Arcade, for example:

```text
ChatGPT
  -> Arcade
     -> Timeweb
     -> Neon
     -> Langfuse
```

This composition does not merge credential or authority planes. Every provider keeps its own semantics, permission boundary, failure evidence, and canonical source.
