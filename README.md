# Aero Multiphysics Workbench

A local-first engineering environment for exploring a single physical design state through coupled aerodynamic, structural, thermal, electrical, rotor-dynamic, and propulsion models.

The project is under active construction. Numerical results are required to identify their source and fidelity; unavailable native solvers must fail closed instead of returning invented data.

## Run locally

Install the pinned workspace dependencies with `pnpm install`, then start the API from `services/api` with `uv run uvicorn aeroworkbench_api.main:app --reload --port 8000` and the UI with `pnpm --filter @aero/web dev`. The UI performs one bounded capability check on first paint; set `NEXT_PUBLIC_API_BASE_URL` when the API is hosted elsewhere. If the API is unavailable, the workbench remains usable as a clearly labelled analytical sample and does not start solver processes.

## Resource contract

Local development and validation enforce an **896 MiB project reservation budget with worker-tree RSS telemetry**, leaving headroom below the one-gigabyte host contract. This is not an OS-wide ceiling over unrelated host processes; native solver execution remains capability-gated and unclaimed until a controlled worker is connected.

## License

Apache-2.0. See [LICENSE](LICENSE).

