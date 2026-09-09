# Engineering MCP server

The server is a user-started official Model Context Protocol SDK stdio server, not a background daemon:

```powershell
node mcp/engineering/server.ts
```

The SDK owns JSON-RPC framing and the server communicates only over stdin/stdout protocol frames. Diagnostics are sent to stderr. Use an official MCP client transport to connect; do not send ad-hoc JSON lines.

Supported tools are `design.inspect`, `design.variant.create`, `result.inspect`, `provenance.list`, `simulation.launch`, `job.cancel`, and `design.delete`. Inspection returns metadata-only status; it does not read arbitrary paths. Variant mutation requires `AERO_ALLOW_MUTATIONS=1`; simulation launch submits a memory/cost reservation, not a solver process. Jobs can only be cancelled by their owner. `design.delete` is denied by default and remains a no-op until a design store is configured. Set `AERO_ALLOW_DESTRUCTIVE=1` only for an interactive, reviewed session. Remote reservations remain denied unless `AERO_ALLOW_REMOTE_COMPUTE=1` and `AERO_REMOTE_COST_CEILING_USD` are explicitly supplied.

The server contains no credentials, path-execution operation, Terraform operation, Docker operation, arbitrary command operation, or result fabrication path.
