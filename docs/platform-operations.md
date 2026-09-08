# Platform operations

## Local-first safety model

The platform owns a typed manifest registry and uses a fixed executable version probe for each native integration. A `READY` capability means only that the named executable answered its version command; it does not validate a physics benchmark, license, mesh, input deck, model fidelity, or solver result.

All missing commands fail closed. No platform command installs packages, fetches solver images, starts a daemon, or replaces missing solver output with an analytical surrogate.

## Commands

```powershell
node scripts/platform/bootstrap.mjs
node scripts/platform/capabilities.mjs
node scripts/platform/dev.mjs
node scripts/platform/benchmark.mjs
node scripts/platform/demo.mjs edf
node mcp/engineering/server.ts
```

The demo command deliberately exits without a numerical result until an explicit native case runner supplies case data and READY capabilities. It is a safe operational gate, not a completed EDF/aircraft/turbine demonstration.

## Resource and remote policy

`LocalScheduler` reserves aggregate local RSS and rejects a total above 1024 MiB. The supplied local compose profile caps the optional MCP container at 250 MiB. Reservations are conservative admission controls; host process RSS remains an operational measurement that must be captured around a real native run.

Remote work is rejected unless both the user-owned MCP session sets `AERO_ALLOW_REMOTE_COMPUTE=1` and its cost ceiling fits the session’s `AERO_REMOTE_COST_CEILING_USD`. Destructive `design.delete` separately requires `AERO_ALLOW_DESTRUCTIVE=1`. These environment values must be set by the interactive operator; no file stores a credential or approval.

## Provenance and results

`SolverGateway.launch` creates a provenance event only after a capability is READY. Its `RunRecord` labels source as `native-solver`; it does not create a result. Native worker implementations must retain solver version, input digest, case directory/output digest, checkpoint lineage, start/end times, scheduler admission, and an explicit result source/fidelity before publishing data.

## Containers and cloud

`infra/docker/Dockerfile.platform` and `compose.local.yml` are manifests only. No image was built or pushed. The compose service has an explicit profile and deny-by-default permissions.

`infra/gcp/main.tf` declares a disabled-by-default storage plan. `enable_remote_compute` defaults to `false`; this repository has not run Terraform init/plan/apply and has not created a GCP project, bucket, Batch job, budget, or billing configuration. Before a future apply, set a project identifier, enable a user-reviewed remote policy, establish billing budgets/alerts outside this skeleton, and preserve the Terraform plan and apply receipt.

## CI tiers

`platform.yml` runs the no-install contract tier on Node 24. The native solver benchmark job is deliberately disabled. Enable it only on a controlled runner after separately capturing native versions, resource limits, test cases, expected tolerances, and artifact provenance.
