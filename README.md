# Aero Multiphysics Workbench

A local-first engineering environment for exploring a single physical design state through coupled aerodynamic, structural, thermal, electrical, rotor-dynamic, and propulsion models.

Every numerical result records its source (`analytical`, `surrogate`, `benchmark`, or `native_solver`). Requested native solvers that are not installed fail closed — they report as unavailable instead of returning invented data.

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
5. One-command local startup — serves the API (with the in-process single-worker native job path) plus the UI behind readiness gates, then prints `stack ready`. `Ctrl-C` shuts owned services down in reverse order:
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

### Solvers (evidence: `docs/solver-verification.md`, `docs/evidence/milestone-2/benchmarks.json`, `docs/evidence/milestone-2/summary.json`)

| Solver | Adapter | Executable verified | Canonical benchmark passes | Workflow validated |
|---|---|---|---|---|
| OpenFOAM | yes | yes — v2412 `blockMesh`/`icoFoam` lid-driven cavity at two mesh resolutions on GCP 2026-09-14 | no — `edf-duct-flow`/`edf-cht` gated; prepare+parse golden files only | no |
| Code_Aster | yes | no — never executed (the GCP CalculiX cantilever exit-0 note concerns a different tool with no adapter) | no — `cantilever-modal` gated | no |
| preCICE | yes | version string only — 3.2.0 feature string, no coupled run | no — `edf-cht` gated; analytic-transfer path proven, native path fails closed | no |
| ROSS | yes | yes — governed `ross-rotordynamics` 2.3.0 Campbell/modal execution | yes — `rotor-campbell` COMPLETED, 1.1% beam agreement | yes — governed API job; `pnpm smoke:product` |
| PyBaMM | yes | yes — governed 26.8.0.0 execution; GCP SPM discharge numbers | yes — `cell-spm-discharge` COMPLETED, validity checks passed | yes — governed API jobs |
| Elmer | yes | version string only — solver banner, no FEM run | no — `.sif` prepare+parse golden files only | no |
| Cantera | manifest + probe only (no dedicated case builder) | partially — GCP 0D CH4/air equilibrium executed (2621.9 K); no governed participant run | no | no |
| pyCycle | manifest + probe only | no | no | no |
| CadQuery | manifest + probe (+ OCC fallback path) | yes as a library — 2.8.0 via the `cad-interchange` fallback | partial — `cad-interchange` COMPLETED via fallback, honestly labelled | partial |
| Gmsh | yes | yes — 4.8.4 on GCP; 4.15.2 governed execution | yes — `domain-mesh` COMPLETED (119852 elements) | yes — governed API jobs |
| OpenVSP | manifest + probe only | no | no | no |
| FreeCAD | yes | no full run — exit 0 under `xvfb-run` only; no STEP roundtrip yet | partial via the CadQuery fallback above | no (native path) |

OpenMDAO 3.45.1 is the scalar coordinator rather than a catalogued solver: paraboloid SLSQP convergence verified on GCP, and convergence/optimization drivers verified in `docs/evidence/milestone-3/summary.json`.

## Known limitations

- Native solvers are optional: without `pnpm setup:solvers` (or on Windows/macOS) every native capability reports unavailable and governed jobs fail closed with `CAPABILITY_UNAVAILABLE`. Version probes never imply a usable case or valid results.
- Local native execution is single-worker with an 896 MiB aggregate project reservation budget (see `docs/architecture.md`); large jobs need the explicit remote-compute switch, which is disabled by default and has no cloud resources provisioned (see `docs/cloud-and-containers.md`).
- Result sources are distinct: analytical screening, surrogate, benchmark, and native_solver envelopes are labelled and never substituted for one another.
- Still unimplemented after issues #1–#8: native OpenFOAM/Code_Aster/Elmer runs, native preCICE field exchange, full-aircraft/combustor/turbine native workflows, cross-restart worker resume (local SQLite ledger), MCP-backed cancellation beyond queued reservations, deployment (no images built or pushed). The complete gap list is `pnpm audit:report`.

## Development

See `CONTRIBUTING.md` for install, test, typecheck, lint, the UI/MCP-use-API and manifest/gateway architecture rules, the fail-closed native result rule, and artifact/secret handling. Security policy lives in `SECURITY.md`.

Further reading: `docs/architecture.md` (product contract), `docs/solver-verification.md` (GCP evidence), `docs/solver-integrations.md` (integration table), `docs/platform-operations.md` (commands, resources, remote policy), `docs/mcp-engineering.md` (MCP server and policy gates), `docs/cloud-and-containers.md` (container/cloud boundary).

## License

Apache-2.0. See [LICENSE](LICENSE).
