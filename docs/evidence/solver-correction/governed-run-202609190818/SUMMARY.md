# Governed native-worker run (issue #47 + GEN 06/07/08/11 residuals)

Commit under test: **`be955a5`** ("fix(ross): version-aware unbalance-response
keyword for governed forced analysis"). Every native execution below was
launched through the repo's own `NativeJobManager` participant lifecycle
(PREPARE -> ADMIT -> EXECUTE -> PARSE -> VALIDATE -> HASH -> ResultEnvelope);
nothing was run as an ad-hoc direct library call. Mesh *preparation* (turning a
generated Gmsh mesh into a solver-native mesh directory) is the only
non-governed step and is recorded explicitly.

Reproduce: `scripts/gcp/governed-worker-startup.sh` (bootstrap) +
`scripts/gcp/run-governed.sh` (env + driver) + `scripts/gcp/governed-run.py`.

## VM / cost

| Item | Value |
|---|---|
| VM | `aero-governed-202609190805` |
| Zone | `us-central1-a` |
| Machine | Spot `e2-standard-2` (2 vCPU / 8 GB), Ubuntu 22.04, 60 GB pd-standard |
| Created | 2026-09-19T08:08Z |
| Install finished | 2026-09-19T08:13Z (~5 min) |
| Governed runs | 2026-09-19T08:18Z – 08:24Z |
| Deleted | 2026-09-19T08:29Z (**verified deleted**; no `aero-governed*` remains) |
| Wall | **21 min** (created 08:08Z → deleted 08:29Z); install 5 min |
| Estimated cost | < **US$0.02** (Spot e2-standard-2 ≈ $0.021/h × 0.35 h + 60 GB pd-standard prorated) — under the $0.15 run target and the $0.20/issue cap |

Per-issue allocation (actual wall-clock, Spot): #47 ≈ 40 s; GEN 08 ≈ 2 s (fails
closed); GEN 06 ≈ 0.5 s; GEN 07 ≈ 0.3 s; GEN 11 ≈ <1 s. No GPU, no on-demand.

## Solver identities / versions (recorded on the worker)

From `artifacts/versions_py312.json` and `artifacts/versions.json`:

| Solver | Version | Notes |
|---|---|---|
| ROSS (`ross-rotordynamics`) | **3.0.0** | python 3.12.13 venv `/opt/py312` |
| ElmerSolver | **26.2** | `elmerfem-csc` PPA, `/usr/bin/ElmerSolver` |
| gmsh (bin + python) | 4.8.4 / 4.15.2 | |
| OpenFOAM | **v2412** | conda-forge prefix `/opt/solvers` |
| preCICE (+ pyprecice) | conda-forge, prefix `/opt/precice` | `precice-tools` present |
| Code_Aster | **18.1.6** | conda-forge prefix `/opt/aster`; only `run_aster` on PATH (`as_run` absent) |
| pybamm | 26.8.0.0 | |
| OpenMDAO | 3.45.1 | |
| cantera | 3.2.0 | |
| cadquery | 2.8.0 | |
| numpy / scipy / casadi | 2.5.3 / 1.18.1 / 3.7.2 | |

## Governed run table

| Issue | Participant | Solver + version | Job state | Envelope source / validity | Key real numbers |
|---|---|---|---|---|---|
| **#47** | `rotor-campbell` (`analysis=forced`) | ROSS 3.0.0 | **COMPLETED** | **`native_solver`** / validity `passed=true` | `peak_response_m = 1.3863709872090623e-4`, `peak_speed_rpm = 2550.0`, `ndof = 30`, `input_hash = 14d2628d…`, `run_id = f7538d30…`, `provenance_id = 2a932224…` |
| GEN 06 | `rotating-flow-mrf` (AMI transient) | OpenFOAM v2412 | **FAILED** | none (fail-closed) | `CAPABILITY_UNAVAILABLE: no executable or library for openfoam is installed`. AMI case files were correctly prepared (`0/U` carries `cyclicAMI` + `neighbourPatch seal_slave/slave_master`; see `artifacts/of_ami_0_U.txt`). |
| GEN 07 | `structural-static` | Code_Aster 18.1.6 | **FAILED** | none (fail-closed) | `CAPABILITY_UNAVAILABLE: no executable or library for code-aster is installed`. Legacy deck prepared (`artifacts/aster_case.comm`, `artifacts/aster_case.export`). |
| GEN 08 | `thermal-conduction` (two-material) | Elmer 26.2 | **FAILED** | none (fail-closed) | `PROCESS_EXIT_NONZERO`. Elmer rejects the generated SIF: `Unlisted keyword: [target bodies] in section: [solver 3]` and `Solvers 2 and 3 have the same Equation name!` (see `artifacts/08_solver.log`). |
| GEN 11 | `coupled-interface-validation` (native window) | preCICE | not reachable | none | conservative-mapping integral conservation measured through the repo mapping path (see below); native coupled window BLOCKED. |

### #47 detail (this receipt closes issue #47)

`rotor-campbell` with `analysis="forced"` now completes on ROSS 3.x because
`solvers/participants/run_scripts/run_ross.py` selects `speed_range` vs
`frequency` by signature (`_unbalance_response`). The governed job emitted the
full legal state chain `QUEUED -> PREPARING -> RUNNING -> PARSING -> VALIDATING
-> COMPLETED` and published a `ResultEnvelope` with `source=native_solver`,
`solver_identity=ross`, `solver_version=3.0.0`, validity
`{response_finite: true}`.

Registered + re-hashed artifacts (`receipts/47_ross_forced_envelope.json`):

| Artifact | bytes | sha256 |
|---|---|---|
| `case.json` | 1631 | `e0d514825e9b25a5a0533fce46b7778d312dcff912bb421b74935b7a7bca06c5` |
| `result.json` | 177 | `ab6d9a4f1692d5ac57489883d53c293055a42d74fd0c5268cd5c84b8a2749aa0` |
| `run_ross.py` | 13480 | `d68de00eae80ba89a545aefdd44b0753423623905157d75b3f582c7e6711cf8f` |
| `solver.log` | 996 | `db7d15b2133364296124277ab0035c506807feb990f91cd322d75607744e44e5` |
| `stdout.log` | 996 | `db7d15b2133364296124277ab0035c506807feb990f91cd322d75607744e44e5` |
| `stderr.log` | 233 | `e0d631ace40e66543e6c17b4645a658baf5a8077cc57965b43f6b63e15b5460f` |

The worker could not reach the upstream repository to write a git receipt; the
result is the raw `ResultEnvelope` JSON in `receipts/`.

## GEN 11 — conservative-mapping integral conservation (repo path)

`precice.coupling.map_field(..., method="conservative")` (repo code, not native
solver output — labelled `analytic-transfer`) transferred a uniform load
`q = 7.0` over `[0,1]` (source integral `7.0`) onto non-matching target meshes
at three resolutions. Every transfer was accepted with
`relative_conservation_error = 0.0` and target integral exactly `7.0`:

| target resolution (points) | rel. conservation error | target integral |
|---|---|---|
| 3 | 0.0 | 7.0 |
| 6 | 0.0 | 7.0 |
| 9 | 0.0 | 7.0 |

The **native coupled window** (FSI/CHT with checkpoint/rollback) is **BLOCKED**:
the only preCICE participant is `coupled-interface-validation`, whose command is
`precice-config-visualizer` (a config-only tool) with no native coupling loop;
that executable is also absent from the conda preCICE prefix (`/opt/precice/bin`
ships `precice-config-validate`, not `precice-config-visualizer`), so the
capability probe reports `unavailable`. Adding a governed native-coupling
participant would require a new manifest + run script, outside this run's
sanctioned scope.

## BLOCKED items and exact reasons

1. **GEN 06 — OpenFOAM transient AMI (BLOCKED).**
   - `participants.capabilities._probe_executable` runs `<exe> --version` and
     requires exit code 0. OpenFOAM v2412 `simpleFoam`/`pimpleFoam` exit **1**
     for both `--version` and `-help` (verified on the worker), so the
     capability probe reports OpenFOAM `unavailable` and the governed job fails
     closed at PREPARING. (Probe returned `CAPABILITY_UNAVAILABLE`.)
   - Independent of the probe: `participants.commands.build_command` always
     selects `manifest.executable.executables[0]` (`simpleFoam`) for every
     OpenFOAM participant, so a transient `pimpleFoam` AMI case cannot be
     launched through the governed path even if the probe passed.
   - Independent of both: the OpenFOAM participant writes case dictionaries
     only; it never converts the governed Gmsh artifact to `constant/polyMesh`,
     and the allowlisted command is the solver alone (no `gmshToFoam`).
   Real prepared-case evidence retained (`artifacts/of_ami_0_U.txt`,
   `artifacts/of_ami_case_manifest.json`).

2. **GEN 07 — Code_Aster structural (BLOCKED).**
   - `as_run` is absent; only `run_aster` 18.1.6 is installed. The manifest
     allowlists `as_run` and `build_command` emits `("as_run", "case.export")`,
     so the capability probe fails closed.
   - Even with `run_aster case.export` (it accepts an export file), the governed
     parser `parse_comm_result` requires a `result_table.txt`, while the export
     writes `IMPR_RESU(FORMAT='TABLEAU', UNITE=80)` and renames unit 80 to
     `result.rmed` (`artifacts/aster_case.export`). No governed path produces
     `result_table.txt`, so parsing would fail even after launch.

3. **GEN 08 — Elmer two-material (BLOCKED).**
   - First blocker (later fixed, see "Product changes"): the generated SIF put
     `Steady State Convergence Tolerance` inside `[Simulation]`, which Elmer
     26.2 rejects (`Unlisted keyword`, run2).
   - After that fix, Elmer 26.2 still rejects the native SIF: the per-region
     `SaveScalars` solver uses `Target Bodies`, which 26.2 reports as
     `Unlisted keyword: [target bodies] in section: [solver 3]`, and multiple
     `SaveScalars` solvers share `Equation = SaveScalars` (26.2:
     `Solvers 2 and 3 have the same Equation name!`). The run fails before
     producing any field (run3, `artifacts/08_solver.log`).
   - Additionally, the product SIF emits no `Energy Balance` operator, while
     `elmer.parser.validate_elmer_result` requires an
     `energy_balance_relative_error` row (missing -> `NaN` -> fail closed), so
     even a converged run could not publish an envelope today.
   - A manual diagnostic (removing only the two offending keywords) made
     ElmerSolver reach `ALL DONE`, but the SaveScalars `result.dat` was written
     as **unlabeled bare numbers** (`0.0 0.0 0.0`) rather than the
     `Variable : operator = value` rows `elmer.parser` expects, and ElmerGrid
     numbered the physical boundaries `left=3, right=4` while the SIF hard-codes
     `Target Boundaries = 1,2` from mapping order. Closing GEN 08 therefore
     requires a coordinated SIF/parser/numbering change with tests, not a
     one-line fix.
   - The governed two-material mesh itself was built and verified by the driver
     (ElmerGrid: 199 nodes / 1003 elements; body ids 1,2; `left`=3, `right`=4),
     and the analytic expectation is `q = 133.33 W/m²`, `T_interface = 380 K`.
     These are **analytic targets, not native results**, and are not claimed.

4. **GEN 11 — native coupled window (BLOCKED)** as described above.

Nothing fabricated: every number above is read from a real governed receipt or
a real solver log. Blocked capabilities are recorded as blocked, not estimated.

## Product changes applied (for integrator review — not committed)

- `solvers/elmer/case.py`: removed `Steady State Convergence Tolerance` from
  the `[Simulation]` block of the native thermal SIF (invalid in Elmer 26.2;
  the same keyword correctly remains in the `HeatSolver` block). This is a
  prerequisite that exposes the remaining Elmer 26.2 SIF incompatibilities; it
  does not by itself close GEN 08.
- Added `scripts/gcp/governed-worker-startup.sh`, `scripts/gcp/run-governed.sh`,
  `scripts/gcp/governed-run.py` (reproduction).

No capability/security/cost gate was weakened; `AERO_ALLOW_REMOTE_COMPUTE` was
never enabled (all runs were local to the worker VM).

## Files

- `receipts/47_ross_forced.json`, `receipts/47_ross_forced_envelope.json`
- `receipts/06_openfoam_ami.json`, `receipts/07_code_aster_static.json`,
  `receipts/08_elmer_multimaterial.json`, `receipts/08_elmergrid.json`,
  `receipts/11_precice_conservative.json`
- `artifacts/`: 47 result/case/log/run-script, 08 SIF/log, OpenFOAM AMI case
  files, Code_Aster deck, solver version reports
- `capabilities.json` (worker capability probes), `driver.log`

## FINAL_REPORT

- **VM**: `aero-governed-202609190805` (created 2026-09-19T08:08Z), zone
  `us-central1-a`, Spot `e2-standard-2`, Ubuntu 22.04, 60 GB. Deleted
  2026-09-19T08:29Z and **verified absent** via
  `gcloud compute instances list` (only pre-existing TERMINATED instances and
  the untouched RUNNING `instance-20260823-180846` remain).
- **Wall**: 21 min total (install 5 min), well under the 180-min budget.
- **Cost**: < US$0.02 (Spot). Per-issue Spot allocation: #47 ≈ $0.0002,
  GEN 08 ≈ $0.00001, GEN 06 ≈ $0.000003, GEN 07 ≈ $0.000002, GEN 11 ≈ $0.000005.
- **Outcome**: #47 **CLOSED** (governed `native_solver` envelope). GEN 06 / 07 /
  08 native governed execution and the GEN 11 native coupled window are
  **BLOCKED** by concrete product-path gaps documented above; GEN 11
  conservative-mapping conservation was measured for real (rel. error 0.0 at 3
  resolutions, labelled analytic-transfer).
- **Teardown confirmed**: `aero-governed*` deleted; the pre-existing
  `instance-20260823-180846` (asia-south1-c) was never touched.
