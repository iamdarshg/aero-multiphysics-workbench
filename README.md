# Aero Multiphysics Workbench

A local-first engineering environment for exploring a single physical design state through coupled aerodynamic, structural, thermal, electrical, rotor-dynamic, and propulsion models.

The project is under active construction. Numerical results are required to identify their source and fidelity; unavailable native solvers must fail closed instead of returning invented data.

## Quickstart (5 minutes, no solvers needed)

Prerequisites: Node.js 24 and Python 3.12. Docker is optional — without it
you still get the full UI plus analytical models; native solvers stay
clearly labelled as unavailable instead of failing obscurely.

1. `corepack pnpm install` — install pinned workspace dependencies.
2. `pnpm setup` — verify runtimes and print a solver capability report.
3. `pnpm run doctor` (`--json` for machine output) — diagnostics-only
   readiness and capability report; never installs or changes anything.
4. `pnpm dev:all` — one command starts the API (with the in-process
   single-worker native job path), the UI, and verifies readiness gates
   before printing `stack ready`. `pnpm start:local` is the production-ish
   equivalent (needs `pnpm --filter @aero/web build` first). Append `--`
   `--with-mcp` for the optional stdio MCP server. Ctrl-C shuts the stack
   down in reverse order with no owned survivors. `pnpm dev` (UI) plus,
   from `services/api`,
   `uv run uvicorn aeroworkbench_api.main:app --reload --port 8000` (API)
   remain available as individual service commands.

Open http://localhost:3000. The workbench opens on a labelled analytical
sample; the provenance dialog on any result tells you exactly what ran and
what did not.

## Solvers (one command)

Most functionality needs solvers. Average users should not compile anything:

`pnpm setup:solvers`

This installs a private micromamba + conda-forge environment
(`infra/local/solver-environment.yml`): OpenMDAO, ROSS, PyBaMM, Cantera,
Gmsh everywhere, plus OpenFOAM, preCICE and FreeCAD on Linux. No sudo, no
system changes, no servers started. Anything still unavailable is reported
as such by `node scripts/platform/capabilities.mjs` and the UI labels it
instead of failing obscurely.

## Run locally

Install the pinned workspace dependencies with `pnpm install`, then start the API from `services/api` with `uv run uvicorn aeroworkbench_api.main:app --reload --port 8000` and the UI with `pnpm --filter @aero/web dev`. The UI performs one bounded capability check on first paint; set `NEXT_PUBLIC_API_BASE_URL` when the API is hosted elsewhere. If the API is unavailable, the workbench remains usable as a clearly labelled analytical sample and does not start solver processes.

## Resource contract

Local development and validation enforce an **896 MiB project reservation budget with worker-tree RSS telemetry**, leaving headroom below the one-gigabyte host contract. This is not an OS-wide ceiling over unrelated host processes; native solver execution remains capability-gated and unclaimed until a controlled worker is connected.

## License

Apache-2.0. See [LICENSE](LICENSE).

