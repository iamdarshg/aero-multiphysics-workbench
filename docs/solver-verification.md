# Solver verification (GCP, 2026-09-14)

Two short-lived Spot VMs (`aero-solver-01`, `aero-solver-02`; e2-small,
asia-south1-c, Ubuntu 22.04) instead of a crash-prone laptop. Both
**deleted** after verification. Total spend ≈ $0.02 (clearance was $0.50).
Every future VM must be Spot + auto-delete.

Reproducible worker: `infra/gcp/solver-worker-startup.sh` (bootstraps and
proves everything below in one shot).

## What actually ran (serial-port log evidence)

| Solver | Version | Evidence |
|---|---|---|
| OpenFOAM | v2412 (conda-forge) | `blockMesh` 0 + `icoFoam` 0 on a self-written 20x20 lid-driven cavity, continuity ~1e-9; repeated at 10x10 for mesh-independence. Tutorials ship as empty dirs in the conda package — write cases inline. Source `/opt/solvers/etc/bashrc`; icoFoam needs a `PISO` dict. |
| preCICE | 3.2.0 (conda-forge, MPI+PETSc+Python) | `precice-tools version` feature string. No coupled run yet. |
| Elmer | 26.2 (`ppa:elmer-csc-ubuntu/elmer-csc-ppa`) | `ElmerSolver` banner; needs `libopenblas0` from apt. No FEM run yet. |
| Gmsh | 4.8.4 (apt) | `gmsh --version`. |
| OpenMDAO | 3.45.1 (pip, python3.12) | Paraboloid SLSQP converges to f = -27.333333. |
| PyBaMM | 26.8.0.0 (pip) | SPM 600 s discharge: terminal voltage 3.78 → 3.71 V. |
| Cantera | 3.2.0 (pip) | CH4/air HP equilibrium: Tad = 2621.9 K. |
| ROSS | `ross-rotordynamics` 2.3.0 (pip; the bare PyPI `ross` name is a different package) | Import verified. No modal run yet. |
| CalculiX | apt `calculix-ccx` | Cantilever `ccx` exit 0. Result parsing inconclusive — rerun before claiming numbers. |
| FreeCAD | 1.x (conda-forge) | `freecadcmd` segfaults bare-headless; **exit 0 under `xvfb-run`**. Flaky on 2 GB boxes — use e2-medium for CAD work. No STEP roundtrip completed yet. |
| Docker | 29.1.3 | Daemon healthy; conda path won, no solver images pulled. |

Ubuntu 22.04 ships python3.10, which cannot take this stack — use
deadsnakes python3.12 and install pip packages one per command.

## Easy setup for average users

`pnpm setup:solvers` → `scripts/platform/setup-solvers.mjs` installs
micromamba + `infra/local/solver-environment.yml` (conda-forge). No sudo,
no compilation. On headless Linux, `apt-get install xvfb` for FreeCAD.

## Do not use

- `dl.openfoam.org` Ubuntu repo (broken GPG on jammy; left an unsigned entry).
- Docker Hub `openfoam/*` images (stale v4–v7 era only).
- Guessed `opencfd/*` tags (do not exist as probed).

## Pinned worker images (issue #43)

The per-boot `infra/gcp/solver-worker-startup.sh` path above installs the whole
stack at worker startup. That is now superseded for trusted execution by two
digest-pinned worker images under `infra/docker/worker/` (see
[cloud-and-containers.md](cloud-and-containers.md)):

- `participants-python.Dockerfile` — Python 3.12 participant stack only.
- `native-solvers.Dockerfile` — OpenFOAM 2412, Code_Aster 18.1.6, Elmer
  (`elmerfem-csc` 9.0 PPA), preCICE 3.2.0, plus the Python participant stack.

All pins (base-image digests, micromamba SHA-256, conda-forge and apt versions,
the reused `services/api/uv.lock`) are recorded in `infra/docker/worker/pins.json`.
A capability manifest is emitted at build/first start and must agree with runtime
participant probing before native results publish (`scripts/gcp/worker-smoke.py`).

**Build/smoke status (never fabricate):** the `#43` workstation had no Docker
daemon, so these images were statically validated only (`node --test
tests/unit/worker-image.test.ts`, `node scripts/gcp/worker-image-validate.mjs`).
The immutable image digests and the digest-verified smoke receipts are **PENDING**
until `scripts/gcp/build-worker-images.sh --push` runs on a Docker/BuildKit host.
No digest or receipt in this repository is fabricated.

Native correctness is unchanged and still owned by SOLVER-CORR. Image build
success is not a correctness signal.

