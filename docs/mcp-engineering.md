# Engineering MCP server

The server is a user-started official Model Context Protocol SDK stdio server, not a background daemon:

```powershell
node mcp/engineering/server.ts
```

The SDK owns JSON-RPC framing and the server communicates only over stdin/stdout protocol frames. Diagnostics are sent to stderr, and an initialization failure exits nonzero with a single-line `MCP_STARTUP_FAILED:<detail>` on stderr. Use an official MCP client transport to connect; do not send ad-hoc JSON lines.

## Thin API client, not a scheduler

The server is a policy-gated client of the public product API (default `http://localhost:8000`, override with loopback-only `AERO_API_BASE_URL`). Every operational tool calls the same API path a human or the workbench UI uses (`GET /v1/native/capabilities`, `POST /v1/native/analyses`, `GET /v1/native/analyses/{id}`, `POST .../cancel`, `GET /v1/native/results/{id}`, `/manifest`, `/v1/native/provenance/{id}`). It never imports scheduler internals and never invokes solver adapters directly. Stopping or disabling the MCP server changes nothing about the product: no API, UI, or scheduler module imports it.

## Tools (exactly seven)

- `capabilities.inspect` (read-only): solver capabilities, participant manifests, and the MCP policy gates in force.
- `design.inspect` (read-only): design/revision metadata anchored to a governed job record (`{ jobId }`). No separate design store exists; this reads the same job path the UI uses.
- `job.inspect` (read-only): governed job state, error codes, and run/result/provenance ids.
- `result.inspect` (read-only): trusted result envelope plus result manifest and provenance. Unpublished results fail honestly with the API's `RESULT_NOT_PUBLISHED` code.
- `design.variant.create` (mutation-gated): queues a validated variant as a deferred governed job using API-supported fields only.
- `analysis.submit` (mutation-gated): submits an allowed analysis as a deferred governed job using API-supported fields only. Participant and fidelity are validated live against the API; unknown ids are rejected before anything is submitted.
- `job.cancel` (destructive- and ownership-gated): cancels a job owned by the configured operator.

There is no shell, path, fetch, or raw-solver tool.

## Policy gates

- Read-only tools need no flag. `AERO_ALLOW_MUTATIONS=1` unlocks the two submit tools; `AERO_ALLOW_DESTRUCTIVE=1` plus an owner match (`AERO_OWNER_ID`, checked against the API-reported `owner_id`, fail-closed on missing/mismatch) unlocks cancel.
- Submits are always deferred: MCP queues a governed job but never starts execution, so it cannot trigger cost-bearing compute by itself.
- Remote compute and cost ceilings have no tool fields at all: any `remote*` or `*costCeiling*`/`*budget*` field is rejected structurally, so MCP can never enable remote compute or raise cost limits by itself.

## Schemas

All inputs are strict Zod objects (unknown fields rejected). Identifiers admit only bounded opaque product ids (`[A-Za-z0-9._:-]`, 1–128 chars, no `..`), which excludes absolute paths, traversal, and command text by construction; input maps are capped at 32 scalar entries with path/command-like values rejected.

## Tests

`tests/platform/mcp-stdio.test.ts` runs the server over real stdio against a stub product API: tool list, read-only calls, submit/variant/cancel through the stub, unowned-cancel rejection, path/command/unknown-field rejection, stdout-frames-only proof, and nonzero-exit startup failure. Policy unit tests live in `tests/unit/mcp-policy.test.ts`.

The server contains no credentials, path-execution operation, Terraform operation, Docker operation, arbitrary command operation, or result fabrication path.
