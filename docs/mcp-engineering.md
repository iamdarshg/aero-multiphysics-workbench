# Engineering MCP server

The server is a user-started JSON-lines bridge, not a background daemon:

```powershell
node mcp/engineering/server.ts
```

Send one object per input line: `{"id":"request-1","operation":"design.inspect","input":{"designId":"fan-a"}}`.

Supported operations are `design.inspect`, `result.inspect`, `simulation.launch`, and `design.delete`. Inspection returns metadata-only status; it does not read arbitrary paths. Simulation launch submits a memory/cost reservation, not a solver process. `design.delete` is denied by default. Set `AERO_ALLOW_DESTRUCTIVE=1` only for an interactive, reviewed session. Remote reservations remain denied unless `AERO_ALLOW_REMOTE_COMPUTE=1` and `AERO_REMOTE_COST_CEILING_USD` are explicitly supplied.

The server contains no credentials, path-execution operation, Terraform operation, Docker operation, arbitrary command operation, or result fabrication path.
