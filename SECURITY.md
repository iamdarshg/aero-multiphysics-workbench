# Security policy

## Reporting a vulnerability

Open a GitHub issue on `iamdarshg/aero-multiphysics-workbench` describing the affected component and how to reproduce the concern. Do not include secrets, credentials, exploit payloads, or unrelated private data in the report. There is no separate private contact; keep reports factual and minimal so they can be triaged in the open.

## What this repository enforces

- **No arbitrary shell or paths.** Solver identity maps to a fixed executable and argument builder from the immutable manifest registry (`packages/solver-contracts/src/manifests.ts`, mirrored in `solvers/manifests/catalog.json`). No caller-supplied command reaches the runner. Case identifiers are opaque and relative (no separators, drive roots, absolute paths, or traversal) and are resolved beneath the approved per-job work directory; uncontained paths are rejected before anything spawns.
- **Fail-closed native execution.** Missing executables, incomplete runs, parser failures, and failed quality gates produce explicit unavailable/failed states. Analytical or surrogate output is never substituted for a missing native result.
- **Remote compute and cost gates.** Remote work is disabled by default and is rejected unless the interactive operator sets both `AERO_ALLOW_REMOTE_COMPUTE=1` and a fitting `AERO_REMOTE_COST_CEILING_USD`. No AI tool call can enable it, and the MCP server has no tool fields for remote or cost settings — any `remote*`/`*costCeiling*`/`*budget*` field is rejected structurally. Destructive `design.delete` separately requires `AERO_ALLOW_DESTRUCTIVE=1`; MCP submits additionally require `AERO_ALLOW_MUTATIONS=1` plus an owner match on `AERO_OWNER_ID`.
- **Secrets handling.** Secrets and approvals live only in runtime environment values set by the interactive operator. They are never stored in source, results, provenance events, or committed files, and no file in this repository holds a credential or approval.
- **Local artifacts and data.** The governed job lifecycle stores jobs, artifacts, and provenance under `~/.aeroworkbench/native-jobs` by default, overridable per run with `AEROWORKBENCH_JOB_ROOT` (CI and smoke tests use isolated temp roots). Generated results, SQLite state, solver output, provenance ledgers, `.next` output, and virtualenvs are never committed and never cross CI job boundaries.
- **Local resource ceiling.** Project-owned processes are admission-controlled against an 896 MiB aggregate reservation budget with process-tree RSS supervision; jobs that exceed it (or cannot be measured) are terminated fail-closed. This is telemetry plus admission control over project processes, not an OS-wide sandbox.

## What is (and is not) a security boundary

Boundaries: the manifest/allowlist command construction, per-job path containment, the capability/readiness gates, the remote/cost/destructive environment gates, and fail-closed result publication.

Not boundaries: UI labels and analytical screening output (informational only), the local SQLite job ledger (no multi-user access control), and the review-only Docker/Terraform manifests (no images built or pushed, no cloud resources provisioned — see `docs/cloud-and-containers.md`).
