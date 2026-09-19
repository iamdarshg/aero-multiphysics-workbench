# Platform operations

## Local-first safety model

The platform owns a typed manifest registry and uses a fixed executable version probe for each native integration. A `READY` capability means only that the named executable answered its version command; it does not validate a physics benchmark, license, mesh, input deck, model fidelity, or solver result.

All missing commands fail closed. No platform command installs packages, fetches solver images, starts a daemon, or replaces missing solver output with an analytical surrogate.

## Commands

```powershell
node scripts/platform/bootstrap.mjs
node scripts/platform/capabilities.mjs
node scripts/platform/dev.mjs
node scripts/platform/stack.mjs dev [--with-mcp]
node scripts/platform/stack.mjs start [--with-mcp]
node scripts/platform/benchmark.mjs
node scripts/platform/demo.mjs edf
node mcp/engineering/server.ts
```

`pnpm dev:all` and `pnpm start:local` are the package.json entries for the
stack commands. The orchestrator starts only product services (API, web UI,
optionally MCP); it never launches solver executables and never requires
Docker. The governed, resource-aware native job lifecycle runs in-process
inside the API (the authoritative execution owner), so there is no separate
worker service: the worker gate is a live GET of `/v1/native/capabilities`
after `/health` responds, and the web gate is a loopback TCP accept on the UI
port. `stack ready` is printed only after every gate responds, within bounded timeouts
(`AERO_STACK_READY_TIMEOUT_MS`). Ports default to 8000/3000 with explicit
`AERO_API_PORT`/`AERO_WEB_PORT` overrides; occupied ports fail fast with an
actionable message and ports are never chosen at random. On Ctrl-C, child
exit, or startup failure the stack stops owned children in reverse dependency
order (mcp, web, api) with a bounded grace period (`AERO_STACK_STOP_GRACE_MS`)
and then force-kills only the observed process tree.

The demo command deliberately exits without a numerical result until an explicit native case runner supplies case data and READY capabilities. It is a safe operational gate, not a completed EDF/aircraft/turbine demonstration.

## Resource and remote policy

`ResourceScheduler` (replacing the earlier single global worker lock) enforces an 896 MiB aggregate project reservation budget and samples each admitted worker's root-plus-descendant RSS. Admission is per-solver-family: heavyweight native executables stay at concurrency 1, governed Python solvers may overlap two-up, and cheap analytical participants may run four-up, with deterministic priority/fairness aging so a stream of cheap jobs cannot starve a promoted high-fidelity job. Every admitted local process is launched without a shell in its own process group; the supervisor terminates the whole observed tree when the reservation or project reservation ceiling is exceeded. If process-tree measurement is unavailable, the run is terminated and fails closed. This telemetry plus admission control is not an OS-wide ceiling over unrelated host processes; a kernel/job-object host-wide ceiling remains a Task 4 gate. The supplied local compose profile caps the optional MCP container at 250 MiB.

Remote work is rejected unless both the user-owned MCP session sets `AERO_ALLOW_REMOTE_COMPUTE=1` and its cost ceiling fits the session’s `AERO_REMOTE_COST_CEILING_USD`. Destructive `job.cancel`/`design.delete` separately requires `AERO_ALLOW_DESTRUCTIVE=1`. These environment values must be set by the interactive operator; no file stores a credential or approval. The engineering MCP server exposes seven API-backed product tools over stdio — `capabilities.inspect`, `design.inspect`, `job.inspect`, `result.inspect`, `design.variant.create`, `analysis.submit` (always deferred), and `job.cancel` — imports no scheduler internals, and cannot enable remote compute or cost-bearing work by itself.

<!-- capability: schedulingMode=resource-aware-concurrent -->
<!-- capability: mcpServer=stdio-public-product-api -->
<!-- capability: remoteCompute=disabled-by-default-user-only -->
<!-- capability: nativeSolvers=capability-gated-fail-closed -->
<!-- capability: containers=manifests-ci-build-smoke -->

## Provenance and results

`SolverGateway.launch` creates a queued provenance event only after a capability is READY. Its `RunRecord` labels the intended source as `native-solver`; it does not execute a solver or create a result. Result publication is active through the evidence-gated envelope path: the governed lifecycle publishes only after retaining a completed process receipt, exact per-artifact 64-hex SHA-256 digests, an approved artifact root, a parser receipt, solver identity/version, the input digest, checkpoint lineage, start/end times, scheduler admission, and an explicit result source/fidelity. Any missing or mismatched piece of that chain fails closed with `RESULT_NOT_PUBLISHED` rather than emitting partial data.

<!-- capability: resultPublication=evidence-gated-publish-active -->

## Containers and cloud

`infra/docker/Dockerfile.platform` and `compose.local.yml` build and run in CI via `pnpm smoke:container` (`scripts/platform/container-smoke.mjs`): the job fails closed without a Docker daemon, builds the image, brings up api+web, runs one `native_solver` product job, and composes down. No image digest is published or pushed by this repository, and the local baseline path never requires Docker.

`infra/gcp/main.tf` declares a disabled-by-default storage plan. `enable_remote_compute` defaults to `false`; this repository has not run Terraform init/plan/apply and has not created a GCP project, bucket, Batch job, budget, or billing configuration. Before a future apply, set a project identifier, enable a user-reviewed remote policy, establish billing budgets/alerts outside this skeleton, and preserve the Terraform plan and apply receipt.

## CI tiers

`platform.yml` runs the no-install contract tier on Node 24. The native solver benchmark job is deliberately disabled. Enable it only on a controlled runner after separately capturing native versions, resource limits, test cases, expected tolerances, and artifact provenance.
