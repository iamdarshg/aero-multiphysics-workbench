# Solver verification (GCP, 2026-09-14)

All-native installs were done on a short-lived Spot VM (`aero-solver-01`,
e2-small, asia-south1-c, Ubuntu 22.04) instead of a crash-prone laptop.
The VM was **deleted** after verification. Spend ≈ $0.02 (under the $0.50
clearance by ~25x). Every future VM must be Spot + auto-delete.

## What actually ran (serial-port log evidence)

| Solver | Version | Evidence |
|---|---|---|
| OpenFOAM | v2412 (conda-forge) | `blockMesh` exit 0 + `icoFoam` exit 0 on a self-written 20x20 lid-driven cavity (ExecutionTime lines in log). Tutorials ship as empty dirs in the conda package — write cases inline. Source `/opt/solvers/etc/bashrc`; do not hand-set env. |
| preCICE | 3.2.0 (conda-forge, MPI+PETSc+Python) | `precice-tools version` prints full feature string. No coupled run yet. |
| Elmer | 26.2 (`ppa:elmer-csc-ubuntu/elmer-csc-ppa`) | `ElmerSolver` banner prints. No FEM run yet. |
| Gmsh | 4.8.4 (apt) | `gmsh --version`. |
| OpenMDAO | 3.45.1 (pip) | Paraboloid SLSQP converges to f = -27.333333. |
| PyBaMM | 26.8.0.0 (pip) | Installed; short SPM discharge smoke inconclusive in-log, rerun before claiming. |
| Cantera | 3.2.0 (pip) | Import + version only. No kinetics run yet. |
| FreeCAD | 1.x (conda-forge) | `freecadcmd` segfaults on bare headless; **works under `xvfb-run`** (exit 0). Headless servers need `xvfb`. |
| Docker | 29.1.3 | Daemon healthy; no solver images pulled (conda path won instead). |
| ROSS | — | Version never confirmed in-log. Unverified; do not claim. |

## Easy setup for average users

`pnpm setup:solvers` → `scripts/platform/setup-solvers.mjs` installs
micromamba + `infra/local/solver-environment.yml` (conda-forge). No sudo,
no compilation. On headless Linux, `apt-get install xvfb` for FreeCAD.

## Do not use

- `dl.openfoam.org` Ubuntu repo (broken GPG on jammy; left an unsigned entry).
- Docker Hub `openfoam/*` images (stale v4–v7 era only).
- Guessed `opencfd/*` tags (do not exist as probed).
