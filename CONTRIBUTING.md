# Contributing

## Install

`pnpm setup` — installs pinned workspace dependencies, then verifies runtimes and prints a solver capability report. Check readiness anytime with `pnpm run doctor` (diagnostics-only; never installs or changes anything).

## Test, typecheck, lint

- `pnpm test` — web/unit tests, contract tests, workspace smoke, and the Python suite.
- `node --test tests/unit/*.test.ts` — fast JS/TS unit check used by CI.
- `pnpm typecheck` and `pnpm lint` — TypeScript plus Python (`ruff`, `mypy`) checks.
- `pnpm audit:report` — requirements gap report (informational); `pnpm audit:requirements` stays red until the tracked physics work is genuinely complete.

## Architecture rules

- The UI (`apps/web`) and the MCP server (`mcp/engineering`) are clients of the public product API. They never import scheduler internals and never invoke solver adapters directly.
- Solver execution goes only through the manifest registry (`packages/solver-contracts/src/manifests.ts`) and the solver gateway/participant lifecycle (`solvers/participants`). No caller-supplied commands, no manifest bypass.
- Native results are publishable only after a verified completion receipt (run receipt, artifact root, parser receipt, SHA-256, solver version, input/checkpoint lineage). Anything less fails closed — never fabricate solver output.

## Artifacts and secrets

- Generated artifacts belong under the job root (`~/.aeroworkbench/native-jobs` by default, `AEROWORKBENCH_JOB_ROOT` to override) or other runtime-ignored locations. Never commit runtime outputs, SQLite state, solver logs, provenance ledgers, or build output.
- Never commit secrets. Approvals and credentials are runtime environment values only (`AERO_ALLOW_MUTATIONS`, `AERO_ALLOW_DESTRUCTIVE`, `AERO_OWNER_ID`, `AERO_ALLOW_REMOTE_COMPUTE`, `AERO_REMOTE_COST_CEILING_USD`).
