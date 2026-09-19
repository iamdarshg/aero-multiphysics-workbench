# Governed native blocker fixes — real worker run (2026-09-19)

Repo under test: `D:\CodeProjects\aero-multiphysics-workbench` at commit `679dccc`
plus the uncommitted integrator patch (see `git status`). Every native execution
below was launched through the repo's own `NativeJobManager.submit` / `run`
lifecycle on a GCP worker; nothing was fabricated. Blocked capabilities are
recorded as blocked with their exact native reason.

Reproduce on a worker:

```
REPO_ROOT=/opt/repo bash scripts/gcp/governed-worker-startup.sh
REPO_ROOT=/opt/repo PY312=/opt/py312 bash scripts/gcp/run-blockers.sh /opt/governed-run \
  --issues 06,06ami,07static,07modal,08,11
```

## Per-path results (governed envelopes)

| Issue | Participant | Solver + version | State | Envelope source / validity | Key real numbers |
|---|---|---|---|---|---|
| 06 transient | `incompressible-steady-flow` | OpenFOAM 2412 (`pimpleFoam`) | **COMPLETED** | **`native_solver`** / `passed=true` | `mass_flow_inlet=-0.005`, `mass_flow_outlet=0.005` kg/s, `continuity_error=-5.08e-16`, `residual_p=6.23e-07`, `residual_Ux=5.28e-06`, `simulation_time_s=0.01`, `area_average_p_inlet=0.003224533` |
| 06 AMI | `rotating-flow-mrf` | OpenFOAM 2412 (`pimpleFoam`) | FAILED | — | `PROCESS_EXIT_NONZERO`: `sigFpe` in `GaussSeidelSmoother::smooth` on the first `U` solve of the cyclicAMI rotor/stator case |
| 07 static | `structural-static` | Code_Aster 18.1.6 (`run_aster`) | FAILED | — | solver ran to `DIAGNOSTIC JOB : OK`; parser `PARSER_FAILED: result table is missing` (run_aster reported copying `fort.80` to the case dir, but the file was not present at parse time) |
| 07 modal | `structural-modal` | Code_Aster 18.1.6 (`run_aster`) | FAILED | — | `CALC_MODES: Keyword MATR_RIGI is mandatory` (macro expansion rejects the supplied `MATR_RIGI`/`MATR_MASS`; `ASSEMBLAGE` of `RIGI`/`MASS` succeeded) |
| 08 Elmer | `thermal-conduction` | Elmer 26.2 (`ElmerSolver`) | **COMPLETED** | **`native_solver`** / `passed=true` | `boundary_left_heat_flow_w=0.6666667`, `boundary_right_heat_flow_w=-0.6666667` W, `energy_balance_relative_error=1.5e-13`, `max_temperature_k=400.0`, `min_temperature_k=300.0`, `mean_temperature_k=364.02` |
| 11 preCICE | `native-coupled-window` | preCICE (conda `pyprecice`) | **COMPLETED** | **`native_solver`** / `passed=true` | `coupling_iterations=5`, `interface_residual=0.0`, `conservation_error=0.0`, `checkpoints=6`, `rollbacks=4` |

Envelopes: `06_openfoam_transient_envelope.json`, `08_elmer_multimaterial_envelope.json`,
`11_precice_native_window_envelope.json`. Real lineage recorded, e.g. Elmer
`run_id=b92af5ef…`, `provenance_id=122d25dc…`, `input_hash=4eb94ea3…`;
preCICE `run_id=cd5176ff…`, `provenance_id=3eb3c06b…`.

Artifact hashes (observed) are in each `*_envelope.json` `output_files` block.

## What was fixed

Install / harness:
- `scripts/gcp/governed-worker-startup.sh`: replaced the ad-hoc pip loop with the
  pinned repo environment `uv sync --frozen --directory services/api`
  (`UV_PROJECT_ENVIRONMENT=/opt/py312`), installed `pyprecice` into that
  interpreter and the conda preCICE prefix, recorded the real installed set with
  the same interpreter used to run, and gated the readiness marker on the
  requested participants' capability probes.
- `scripts/gcp/governed-blocker-startup.sh` (new): no-SSH orchestrator that
  clones the repo at an immutable commit, applies the fix patch, installs, runs
  the driver, and uploads evidence with heartbeats.
- Capability probing now agrees with execution: `native-coupled-window` is only
  `ready` when a Python interpreter can actually `import precice`
  (`solvers/precice/interpreter.py`), and `run_precice.py` selects that
  interpreter and fails closed with the exact attempts.

OpenFOAM:
- `solvers/openfoam/case.py`: normalize the governed mesh to MSH 2.2 with 3D
  cells before `gmshToFoam` (bounded `gmsh -3 -format msh2`), mark declared AMI
  pairs `cyclicAMI` in `polyMesh/boundary`, emit OF2412 `transportModel`,
  `surfaceFieldValue.writeFields`, `pFinal`/`UFinal`/`pcorr`/`pcorrFinal`
  solver entries, a `PIMPLE` dict with a pressure reference for closed domains,
  and the OF2412 `dynamicMultiMotionSolverFvMeshCoeffs` shape.
- `scripts/gcp/governed-blocker-run.py`: 3D duct mesh with correct
  inlet/outlet/walls physical groups (OCC bbox tolerance), 3D rotor/stator AMI
  mesh with non-conformal seal faces, MSH2 output.

Elmer:
- `solvers/elmer/case.py`: accept `material_<name>`/`<name>` physical-group
  aliases for zones/material regions (generic, no demo names).
- `solvers/elmer/parser.py`: read bare `SaveScalars` numeric rows with their
  `.names` sidecar (operator-first Elmer 26.2 format) plus the labeled form.
- `solvers/elmer/sif.py`: write the manifested `result.json` canonical artifact.

Code_Aster:
- `solvers/code_aster/comm.py`: governed result written as a real
  `IMPR_RESU(FORMAT='RESULTAT', NOM_CHAM='DEPL', FORM_TABL='OUI')` listing;
  parser reads the native listing (blank lines / separated signs tolerated) and
  modal frequencies from the solver log; governed modal deck assembles
  `RIGI`/`MASS` with `ASSEMBLAGE`; nodal loads on surface groups synthesize a
  node group with `DEFI_GROUP` and use `FORCE_NODALE(GROUP_NO=…)`.
- `solvers/code_aster/structure.py`: a `nodal_force` may target a declared
  surface group (rendered as a node group), not only a node group.
- `scripts/gcp/governed-blocker-run.py`: Code_Aster mesh written as MED with
  correct `clamp-face`/`tip-face` groups; the tip load is a nodal force scaled
  by the tip-node count.

preCICE:
- `solvers/precice/validate.py`: read mappings declared on the receiving
  participant; the convergence measure references the exchange mesh.
- `solvers/participants/run_scripts/run_precice.py`: version-tolerant
  `set_vertices`/`read_data`/`write_data` shims; both participants use matching
  interface coordinates.

Manifest / probing:
- `solvers/participants/manifest.py`: OpenFOAM artifacts are flat, present files
  (`case_manifest.json`, `result.json`, `solver.log`).

## Local bounded tests

`services/api/.venv/Scripts/python.exe -m pytest` on
`tests/physics/test_native_blocker_fixes.py tests/physics/test_gen06_openfoam.py
tests/physics/test_gen07_code_aster.py tests/physics/test_gen08_elmer.py
tests/physics/test_gen11_precice_native.py tests/physics/test_participant_lifecycle.py
tests/physics/test_native_execution.py` → **157 passed**. Added bounded tests for
MSH2/3D detection and conversion, AMI boundary patching, OF2412 dynamic-mesh
shape, Elmer alias + bare SaveScalars, Code_Aster RESULTAT listing / modal log
frequencies / nodal-surface DEFI_GROUP, and preCICE interpreter discovery.
`ruff check --config services/api/pyproject.toml` passes on all changed files.

## VM / cost

- VM `aero-governed-blockers-20260919`, `us-central1-a`, on-demand
  `e2-standard-2` (2 vCPU / 8 GB), 60 GB pd-standard, Ubuntu 22.04.
- Created 2026-09-19T17:20:52Z; reused via reset for iterations; deleted
  2026-09-19T19:23:02Z and verified absent via `gcloud compute instances list`
  (only pre-existing TERMINATED instances remain; `instance-20260823-180846`
  untouched).
- Wall ≈ 2 h 02 m; estimated cost ≈ **US$0.14** (under the $0.60 run cap and
  the $0.20/issue cap).
