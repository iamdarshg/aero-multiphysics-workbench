# Engineering MCP server

The server is a user-started official Model Context Protocol SDK stdio server, not a background daemon:

```powershell
node mcp/engineering/server.ts
```

The SDK owns JSON-RPC framing and the server communicates only over stdin/stdout protocol frames. Diagnostics are sent to stderr. Use an official MCP client transport to connect; do not send ad-hoc JSON lines.

Supported tools are `design.inspect`, `design.variant.create`, `result.inspect`, `provenance.list`, `simulation.launch`, `job.cancel`, and `design.delete`. These are explicitly skeleton operations: inspect/result/provenance return metadata-only empty status, variant/delete remain queued/no-op until their stores are connected, launch creates a bounded reservation only, and cancel removes a queued reservation only. No tool executes a native solver or claims Task 4/5 completion. Variant mutation requires `AERO_ALLOW_MUTATIONS=1`; `design.delete` is denied by default and remains fail-closed until a design store is configured. Set `AERO_ALLOW_DESTRUCTIVE=1` only for an interactive, reviewed session. Remote reservations remain denied unless `AERO_ALLOW_REMOTE_COMPUTE=1` and `AERO_REMOTE_COST_CEILING_USD` are explicitly supplied.

The server contains no credentials, path-execution operation, Terraform operation, Docker operation, arbitrary command operation, or result fabrication path.
