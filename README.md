# Aero Multiphysics Workbench

A local-first engineering environment for exploring a single physical design state through coupled aerodynamic, structural, thermal, electrical, rotor-dynamic, and propulsion models.

Every numerical result records its source (`analytical`, `surrogate`, `benchmark`, or `native_solver`). Requested native solvers that are not installed fail closed — they report as unavailable instead of returning invented data.

<!-- capability: authoritativeExecutionOwner=services-api-governed-inprocess-native-jobs -->
<!-- capability: schedulingMode=resource-aware-concurrent -->
<!-- capability: resultPublication=evidence-gated-publish-active -->
<!-- capability: cachePersistence=persistent-content-addressed -->
<!-- capability: mcpServer=stdio-public-product-api -->
<!-- capability: remoteCompute=disabled-by-default-user-only -->
<!-- capability: containers=manifests-ci-build-smoke -->
<!-- capability: nativeSolvers=capability-gated-fail-closed -->
<!-- capability: storage=sqlite-wal-plus-content-addressed-artifacts -->

These capability facts are machine-readable in `docs/requirements-audit.json` under `capabilityFacts`; the check in `scripts/check-docs.mjs` fails when this page or the other owned docs drift from them.

## Quickstart (baseline, no solvers needed)

Prerequisites: Node.js 24, `pnpm` via `corepack`, Python 3.12 with `uv`. Docker is **not** required for the baseline product. Linux extras (`xvfb`) only matter for the optional native solver environment below.

1. Clone the repository and enter it:
   `git clone https://github.com/iamdarshg/aero-multiphysics-workbench.git`
   `cd aero-multiphysics-workbench`
2. Baseline setup (installs pinned workspace dependencies, then verifies runtimes and prints a solver capability report without changing anything else):
   `pnpm setup`
3. Product doctor — diagnostics-only readiness and capability report; never installs or changes anything (`--json` for machine output). Note: use `pnpm run doctor` (bare `pnpm doctor` is pnpm's own builtin):
   `pnpm run doctor`
4. Optional native solvers — installs a private micromamba + conda-forge environment (`infra/local/solver-environment.yml`) with no sudo and no system changes. Anything still unavailable stays clearly labelled as unavailable:
   `pnpm setup:solvers`
5. One-command local startup — serves the API (the authoritative owner of the in-process, resource-aware governed native job lifecycle) plus the UI behind readiness gates, then prints `stack ready`. `Ctrl-C` shuts owned services down in reverse order:
   `pnpm dev:all`
   Production-ish equivalent (build the UI first with `pnpm --filter @aero/web build`):
   `pnpm start:local`
   Append `-- --with-mcp` to either command for the optional stdio MCP engineering server.
6. Open http://localhost:3000. The workbench opens on a labelled analytical sample; the provenance dialog on any result tells you exactly what ran and what did not.
7. Run one bounded product job — a tiny deterministic `rotor-campbell` analysis through the real governed API lifecycle on an isolated job root, verifying the terminal `native_solver` envelope plus provenance. It spawns its own API instance, so the stack does not need to be running:
   `pnpm smoke:product`

Individual service commands remain available: `pnpm dev` (UI) plus, from `services/api`, `uv run uvicorn aeroworkbench_api.main:app --reload --port 8000` (API). The full check suite is `pnpm test`, `pnpm typecheck`, `pnpm lint`; the requirements gap report is `pnpm audit:report`.

## Support matrix

Capability tiers used below — a `READY` capability means only that the named executable answered its version command:

- **adapter**: manifest entry in `packages/solver-contracts/src/manifests.ts` plus a capability probe in `solvers/participants/capabilities.py` (full case builders only where noted).
- **executable verified**: the real tool answered on record — a version probe at minimum, a genuine run where stated.
- **canonical benchmark passes**: one of the four cases in `benchmarks/manifest.json` completed to a verified `native_solver` envelope.
- **workflow validated**: end-to-end governed job (`POST /v1/native/analyses` lifecycle) demonstrated with evidence.

### Platforms

| Platform | Baseline product (UI, API, doctor, stack, smoke) | Native solvers |
|---|---|---|
| Windows (current dev host) | Supported — baseline reports READY | Not installed; `pnpm run doctor` reports all 12 unavailable, fail-closed |
| Linux x86-64 (Ubuntu 22.04; also CI) | Supported | Supported via `pnpm setup:solvers`; OpenFOAM/preCICE/FreeCAD conda packages are Linux-only; headless hosts also need `xvfb` for FreeCAD |
| macOS | Expected to work, not tested | Unsupported — Linux-only conda packages stay unavailable; the Python stack still installs |

### Solvers (evidence: `docs/solver-verification.md`, `docs/evidence/solver-correction/SUMMARY.md`, `docs/evidence/solver-correction/summary.json`, `docs/evidence/solver-correction/governed-blockers-fix-20260919/SUMMARY.md`, `docs/evidence/milestone-2/benchmarks.json`)

| Solver | Adapter | Executable verified | Canonical benchmark passes | Workflow validated |
|---|---|---|---|---|
| OpenFOAM | yes | yes — v2412 channel/cavity/rotating-frame MRF EXECUTED on GCP 2026-09-19 (mass imbalance 1.0e-9; 0.18% vs analytic); governed `pimpleFoam` transient COMPLETED (continuity -5.1e-16, residual_p 6.2e-07) | partial — channel + MRF + governed transient pass; transient AMI blocked by a native `sigFpe` in the first U solve | yes — governed API job (`incompressible-steady-flow`, `rotating-flow-mrf`) |
| Code_Aster | yes | yes — 18.1.6 `run_aster` EXECUTED on GCP (governed static deck assembled; solver reached `DIAGNOSTIC JOB: OK`) | partial — governed static blocked (result table not copied at parse time) and modal blocked (`CALC_MODES` macro rejects the supplied `MATR_RIGI`) | partial — native process runs, result publication blocked |
| preCICE | yes | yes — native implicit coupling EXECUTED on GCP 2026-09-19 (`pyprecice`): 5 iterations, interface residual 0.0, conservation 0.0, 6 checkpoints / 4 rollbacks | yes — governed `native-coupled-window` COMPLETED to a `native_solver` envelope | yes — governed API job |
| ROSS | yes | yes — 3.0.0 `Jeffcott`/soft-bearing/unbalance EXECUTED on GCP (first critical 8698 rpm; modal 0.46% vs Campbell) | yes — governed `rotor-campbell` COMPLETED; governed forced analysis fixed for the ROSS 3.x API and COMPLETED (peak 1.386e-4 m @ 2550 rpm) | yes — governed API job; `pnpm smoke:product` |
| PyBaMM | yes | yes — governed 26.8.0.0 execution; GCP SPM discharge numbers | yes — `cell-spm-discharge` COMPLETED, validity checks passed | yes — governed API jobs |
| Elmer | yes | yes — 26.2 steady Dirichlet/heat-flux + transient uniform heating EXECUTED (0.0% vs analytic) | yes — governed two-material conduction COMPLETED (boundary heat flow ±0.667 W, energy balance relative error 1.5e-13) | yes — governed API job |
| Cantera | manifest + probe only (no dedicated case builder) | partially — GCP 0D CH4/air equilibrium executed (2621.9 K); no governed participant run | no | no |
| pyCycle | manifest + probe only | no | no | no |
| CadQuery | manifest + probe (+ OCC fallback path) | yes as a library — 2.8.0 via the `cad-interchange` fallback | partial — `cad-interchange` COMPLETED via fallback, honestly labelled | partial |
| Gmsh | yes | yes — 4.8.4 on GCP; 4.15.2 governed execution | yes — `domain-mesh` COMPLETED (119852 elements) | yes — governed API jobs |
| OpenVSP/VSPAERO 3.52.1 | governed official AngelScript + `Results.csv` adapter | yes (native fixture) | yes | yes |
| FreeCAD | yes | no full run — exit 0 under `xvfb-run` only; no STEP roundtrip yet | partial via the CadQuery fallback above | no (native path) |

OpenMDAO 3.45.1 is the scalar coordinator rather than a catalogued solver: paraboloid SLSQP convergence verified on GCP, and convergence/optimization drivers verified in `docs/evidence/milestone-3/summary.json`.

## Testing and performance

- Tiered suites with hard runtime budgets: `pnpm test:fast` (bounded default loop, ~20 s), `pnpm test:focused`, `pnpm test:integration`, `pnpm test:native-smoke`, `pnpm test:science`, `pnpm test:all`. See `docs/testing-tiers.md`.
- Performance baselines and a regression budget for the control-plane hot paths: `pnpm perf:smoke` (see `docs/performance-baselines.md`).
- Numerical-independence and promotion gates (mesh/time-step ladders, physical closure): `packages/convergence`, plus the generic generative-engineering benchmark under `benchmarks/independence/` (see `docs/numerical-independence.md`).


## Known limitations

- Native solvers are optional: without `pnpm setup:solvers` (or on Windows/macOS) every native capability reports unavailable and governed jobs fail closed with `CAPABILITY_UNAVAILABLE`. Version probes never imply a usable case or valid results.
- Local native execution is admitted by the resource-aware `ResourceScheduler` under a hard 896 MiB aggregate project reservation budget: heavyweight native solvers stay at concurrency 1 by policy, governed Python solvers may overlap two-up, and cheap analytical participants may run four-up (see `docs/architecture.md`). Large jobs need the explicit remote-compute switch, which is disabled by default and has no cloud resources provisioned (see `docs/cloud-and-containers.md`).
- Result sources are distinct: analytical screening, surrogate, benchmark, and native_solver envelopes are labelled and never substituted for one another. Native results publish only through the evidence-gated envelope path, and engineering results/artifacts are cached persistently and content-addressed.
- Still unimplemented or blocked: OpenFOAM transient sliding-interface/AMI (native `sigFpe` on the first U solve of the cyclicAMI rotor/stator case), Code_Aster result publication (static result table not copied at parse time; modal `CALC_MODES` macro limitation), full-aircraft/combustor/turbine native workflows, hosted ChatGPT supervision, published container image digests (definitions are pinned but no image has been built; digests are explicitly pending), and provisioned cloud compute/checkpointing. The complete gap list is `pnpm audit:report`.

## Development

See `CONTRIBUTING.md` for install, test, typecheck, lint, the UI/MCP-use-API and manifest/gateway architecture rules, the fail-closed native result rule, and artifact/secret handling. Security policy lives in `SECURITY.md`.

Further reading: `docs/architecture.md` (product contract), `docs/solver-verification.md` (GCP evidence), `docs/solver-integrations.md` (integration table), `docs/platform-operations.md` (commands, resources, remote policy), `docs/mcp-engineering.md` (MCP server and policy gates), `docs/cloud-and-containers.md` (container/cloud boundary), `docs/testing-tiers.md` (bounded test tiers), `docs/performance-baselines.md` (perf budgets), `docs/numerical-independence.md` (independence/closure gates), `docs/hot-paths.md` (measured Node/Python boundaries).

## License

Apache-2.0. See [LICENSE](LICENSE).
