# aero-multiphysics-workbench — geometry/mesh pipeline: where the seconds go

Evidence for the 3D-deliverable geometry + meshing path.
Repo under test: `E:/engineering-portfolio-audit/repos/aero-multiphysics-workbench`
(branch checked out: `audit/baseline-verification-20261111`, HEAD `7fbfc19`; nothing was
checked out, edited, committed or pushed by this investigation).

Environment: Windows 11, 16 logical CPUs, 15.2 GB RAM (4.4 GB free during these runs —
other agents were using the host), `uv` 0.9.6, project venv from `services/api/pyproject.toml`:
Python 3.12.2, **gmsh 4.15.2**, **cadquery 2.8.0 (OCP)**, numpy 2.5.3.

---

## 1. Entry points that actually produce 3D geometry and a mesh

| Stage | Code | Notes |
|---|---|---|
| Canonical geometry identity | `packages/geometry/aeroworkbench_geometry/canonical.py` (`GeometryModel`, `shape_hash`) | pure hashing, microseconds |
| Parametric CAD definition + execution | `.../geometry/parametric.py` (`ParametricModel`, `export_artifacts`), `.../geometry/builder.py` (`execute`, OpenCascade via cadquery) | real solids, capability-gated (`probe_kernel`) |
| Aircraft airframe → CAD | `packages/airframe/aeroworkbench_airframe/aero_geometry/assembly.py` (`parametric_model`, `regenerate_assembly`) | lofts wing/tail/fin/fuselage/controls from `tests/airframe/aero_geometry/fixed_wing.json` |
| Duct/flowpath → CAD | `packages/geometry/aeroworkbench_geometry/duct_system.py` (`build_duct_system`) | generic N-rotor duct; the only flowpath CAD builder |
| STEP/BREP export | `geometry/parametric.py::export_artifacts` | one STEP per component |
| Native meshing | `packages/mesh/aeroworkbench_mesh/native_mesh.py::build_native_mesh` (702 lines) | gmsh Python API: merge STEPs → `occ.fragment` → physical groups → fields → `mesh.generate` → quality → write |
| Physics-facing wrapper | `packages/meshing/aeroworkbench_meshing/native.py` (`mesh_box_native`, `build_native_mesh_physics`) | serialises gmsh behind `_MESH_LOCK` |
| gmsh CLI plan (unused for real meshes) | `packages/mesh/aeroworkbench_mesh/gmsh_adapter.py:32-48` | only builds an argv tuple; nothing spawns it |

**There are no `.geo` files in this pipeline at all** (grep over `packages/*`, `solvers/*`,
`examples/*` finds only the argv planner above). gmsh is driven in-process through its Python
API and the `.msh` is written exactly once per run (`native_mesh.py:580`). So the suggested
"reduce redundant `.geo` writes" lever does not exist here; the equivalent redundant work is
the repeated *model queries* analysed in §4.

Harness (this investigation): `bench_pipeline.py` — runs the **unmodified** repo code path and
wraps every gmsh entry point with a timer, so each stage is attributed to real gmsh calls
rather than guessed. Modes: `stock`, `fast` (same path + memoization patches).

---

## 2. STAGE_TIMINGS

### 2a. Gas turbine — 3-stage flowpath (`build_duct_system`, Ø180/Ø160 mm bore × 460 mm,
3 rotor zones, 2 stator zones, 2 shafts), base size 14 mm

Record: `work/gasturbine-stock-stock2/record.json`
Result: `completed`, **3,975,212 elements, 248,980 nodes, min SICN 0.174938**, 10 STEP files.

| Stage | seconds | share |
|---|---:|---:|
| geometry definition + digest | 0.0002 | 0.0 % |
| CAD build (cadquery/OCP, 10 solids) | 6.18 | 5.0 % |
| STEP export (10 components) | 0.65 | 0.5 % |
| mesh spec + selectors | 0.0002 | 0.0 % |
| **mesh stage, total** | **117.09** | **94.5 %** |
| ├ gmsh init | 0.016 | 0.0 % |
| ├ STEP import (`merge`×10 + `synchronize`×10) | 0.20 | 0.2 % |
| ├ `occ.fragment` (conformal) | 0.11 | 0.1 % |
| ├ size fields (BL + refinement) | 0.0003 | 0.0 % |
| ├ physical groups + box selectors (238 gmsh calls) | 0.007 | 0.0 % |
| ├ **`mesh.generate` 3D (Delaunay, Algorithm3D=1)** | **65.73** | **53.0 %** |
| ├ **`mesh.optimize("Relocate3D")`** | **35.03** | **28.3 %** |
| ├ quality measurement (`getElements` + 5×`getElementQualities`) | 6.25 | 5.0 % |
| ├ **write `.msh` 4.1 ASCII** | **6.19** | **5.0 %** |
| └ finalize | 0.30 | 0.2 % |
| **TOTAL** | **123.92** | |

Repeat of the identical request (same host, minutes later): **156.75 s**
(`work/gasturbine-stock-stock-clean/`, `generate` 77.52 / `optimize` 36.86 / `write` 11.86).
Same output hash. Host load from co-running agents moves wall time by ±25 %; the shares are stable.

### 2b. Aircraft — real `fixed_wing.json` assembly (wing, tail, fin, fuselage, elevator,
rudder, aileron), base size 24 mm

Record: `work/aircraft-stock-full7/record.json` — **no mesh is produced** (see §5).

| Stage | seconds | share |
|---|---:|---:|
| geometry definition (fixture parse + payload) | 1.11 | 2.4 % |
| CAD build (7 lofted solids) | 6.09 | 13.1 % |
| STEP export (7 components) | 1.41 | 3.0 % |
| mesh spec | 0.004 | 0.0 % |
| STEP import (`merge`×7, `synchronize`×9) | 1.78 | 3.8 % |
| **`occ.fragment` (7 coincident/overlapping solids)** | **34.60** | **74.6 %** |
| `mesh.generate` 3D | 1.19 then **raised** | — |
| selector/boundary queries (3,266 gmsh calls) | 0.10 | 0.2 % |
| **TOTAL (aborted)** | **46.36** | |

Sub-case wing + fuselage only, base 60 mm (`work/aircraft-stock-wingbody2/`): total 14.36 s
(CAD 8.75, export 1.72, mesh 2.33 = fragment 1.24 + import 0.50 + generate 0.48) → meshes, but
the quality gate rejects it: `min SICN 0.000028 < 0.05`.

---

## 3. What is actually slow

1. **The gmsh kernel, not the workbench Python.** `generate` + `optimize` + `write` +
   `getElementQualities` = 113.2 s = **96.7 % of the mesh stage and 91.4 % of total runtime**.
   The workbench's own Python glue in `build_native_mesh` is **3.0-3.2 s of 124 s (2.6 %)**.
2. **`mesh.optimize("Relocate3D")` costs 35 s (28 %) and its benefit is unmeasured** — it is
   wrapped in `suppress(Exception)` (`native_mesh.py:559-562`), so even a silent no-op looks
   like success. This is the largest single "is it worth it?" in the pipeline.
3. **`Mesh.Binary = 0` (`native_mesh.py:308`) costs 6.2 s (5 %)** writing a 300+ MB ASCII file
   that the next stage reads back. Binary msh keeps identical elements/topology.
4. **Aircraft specifically: `occ.fragment` is the bottleneck (34.6 s) and the result cannot be
   meshed.** Seven lofted solids that touch at coincident faces blow up the boolean stage and
   then fail in `generate`. The aircraft path has no working meshed 3D deliverable on this
   host (§5).
5. **Nothing is cached.** Four independent runs of the *same* gas-turbine request each spent
   115-157 s and produced the identical `.msh` hash. All the cache-key material already exists
   (`native_mesh.py:592-607` builds `geometryHash`, `meshSpecDigest`, per-component STEP
   hashes) but is only *recorded*, never used as a lookup.

---

## 4. SPEEDUP

### 4a. Memoized model queries — implemented, measured, **rejected** (0.002 %)

Three memoizations applied to `build_native_mesh` via its module-level helpers
(`_surface_center` `native_mesh.py:194`, `_face_node_count` `:199`, `_apply_patch` `:212`):
per-surface bounding boxes cached across patches; per-volume boundary lists cached; per-surface
node sets cached and the pre-generation `_face_node_count` calls (which always return 0, since
no mesh exists yet — `:407`, `:448`) short-circuited.

| | stock | fast |
|---|---:|---:|
| gmsh query calls in groups/selectors | 238 | 130 |
| time in that stage | 0.0066 s | 0.0035 s |
| mesh output | sha `94163f87…` | sha `94163f87…` (identical) |

Saving: **3 ms out of 124 s = 0.002 %**. Wall-clock difference between the two runs
(123.9 s vs 115.3 s) is host noise in `generate` (65.7 vs 59.9 s), *not* the patch.
Honest conclusion: this optimisation is worthless on this pipeline; the 3,266 selector calls in
the aircraft run cost 0.10 s total. Do not ship it as a speed-up.

### 4b. Process-level parallelism of independent cases — **1.73× measured**

gmsh is serialised in-process by `_MESH_LOCK` (`native_mesh.py:28`), so the only sound
parallelism is one case per process. Two independent base-14 mm gas-turbine cases:

| | wall clock |
|---|---:|
| sequential (2 cases) | 226.14 s |
| concurrent (2 processes) | 130.53 s |
| **speed-up** | **1.73×** |

Correctness: both cases produce **byte-identical** meshes in the sequential and concurrent runs
(`seq-a` vs `par-a` and `seq-b` vs `par-b`: elements 3 975 212 / 3 975 212, `sha_equal=True`).
Limiter: 16 logical CPUs but only 4.4 GB free RAM; each 4 M-element case needs ~1.5 GB, so
2-3 workers is the practical ceiling on this host, not 8-16.

### 4c. Content-addressed mesh cache — identified, **not implemented**

Would turn a repeat of an unchanged case from 115-157 s into a hash lookup. Key material
already computed at `native_mesh.py:592-607`; the receipt (`NativeMeshReceipt`) is already
immutable and content-hashed, so a cache hit is a pure lookup with no recomputation and no
change to the receipt. Not implemented here because the repo is read-only for this audit.

### 4d. Measured but *output-changing* — do not call these "free"

* `Mesh.Binary = 1`: identical elements, identical quality, different file bytes; removes
  ~6 s/run (5 %) and shrinks the `.msh` substantially. Changes `mesh_hash`.
* Dropping `optimize("Relocate3D")`: removes 35 s (28 %). Changes node positions, so node
  count may stay equal but `min SICN`, `.msh` hash and topology fingerprint change. Whether it
  matters to a solver is a solver question (see §9) — it must be measured, not assumed.

---

## 5. CORRECTNESS

Gas-turbine case, four runs (two stock with full attribution, one stock before instrumentation,
one with the memoization patch):

| run | elements | nodes | min SICN | `.msh` sha256 | topology fingerprint |
|---|---:|---:|---|---|---|
| `gasturbine-stock-stock-clean` | 3 975 212 | 248 980 | 0.174937648240979 | `94163f87…aa7` | `0a476de7…134` |
| `gasturbine-stock-stock2` | 3 975 212 | 248 980 | 0.174937648240979 | `94163f87…aa7` | `0a476de7…134` |
| `gasturbine-fast-fast2` | 3 975 212 | 248 980 | 0.174937648240979 | `94163f87…aa7` | `0a476de7…134` |
| `gasturbine-stock-seq-a` / `par-a` / `seq-b` / `par-b` | 3 975 212 | — | — | equal within each pair | — |

**Unchanged: yes** — byte-identical `.msh`, identical element/node counts, identical SICN,
identical 26 physical groups (9 zone + 3 patch + 14 interface) and identical interface
surface/node counts, for both the memoization patch and the parallel schedule.

---

## 6. Aircraft 3D deliverable: three distinct failures (all fail-closed, none fabricate)

| configuration | outcome |
|---|---|
| all 7 components, base 24/60 mm | gmsh raises `Invalid boundary mesh (overlapping facets) on surface 1 surface 915` during `mesh.generate`; no mesh, no receipt (exception escapes `build_native_mesh`) |
| wing + fuselage, base 60 mm | meshes, then gate rejects: `MESH_QUALITY_BELOW_THRESHOLD: min SICN 0.000028 < 0.05` |
| single component | **crash**: `ValueError: zip() argument 2 is shorter than argument 1` at `native_mesh.py:340` — `occ.fragment((vol,), (vol,))` returns a parent map shorter than the input list when there is one volume |

Nobody exercised these paths: the meshing tests (`tests/physics/test_gen05_solver_mesh.py`) only
mesh the duct fixture. The aircraft demo (`examples/aircraft/system.py`) is analytical only and
never produces 3D geometry. So the "physical 3D deliverable" for the aircraft is currently CAD +
STEP only, and its meshing path is broken at the visible edge.

---

## 7. PYTEST_TRUTH

Command (the correct one): `uv run --directory services/api pytest -q` from the repo root.
Log: `pytest_full.log`.

```
4 failed, 1790 passed, 2 warnings in 1037.87s (0:17:17)   [1794 collected, 0 skipped]
```

| # | test id | cause |
|---|---|---|
| 1-3 | `tests/physics/test_edf_80mm_three_stage.py::test_edf_cad_interchange_runs_natively`<br>`tests/physics/test_generic_multiphysics_substrate.py::test_interchange_roundtrip_is_real`<br>`tests/physics/test_native_execution.py::test_cad_interchange_benchmark_runs_natively` | one root cause: **host PATH state**. `FreeCADCmd` 1.1.4 is on PATH (`D:\mcp\eng\freecad\FreeCAD_1.1.4-Windows-x86_64-py311\bin\freecadcmd.exe`); `solvers/freecad/adapter.py:147` invokes it with `--run-script`, which 1.1.4 rejects (`unrecognised option '--run-script'`), so the job ends `PROCESS_EXIT_NONZERO:forward conversion failed:CONVERSION_FAILED` instead of using the OCP fallback |
| 4 | `tests/physics/test_turbo11_calibration.py::test_turbo11_end_to_end_design_proof` | pinned golden hash: expects `deae9499e74c…fbe507`, computes `8d159c9518094c37a8d0f2da250173f83e8ca30621e6eebfc7b3f9e927e2a583` (line 348) |

The **single failure carried around is #4** — the turbo11 golden-hash pin. The other three are
not product faults; they are an ambient-toolchain collision. Evidence:

* `convert_with_freecad()` on a real STEP → `state=failed`, stderr `unrecognised option '--run-script'`;
  `convert_with_ocp()` on the same file → `state=completed`. (`probe_converter.py` output)
* With the FreeCAD directory removed from PATH, `test_interchange_roundtrip_is_real`
  **passes** (1 passed in 8.26 s). That reproduces the previously quoted
  `1 failed / 1793 passed / 1794 collected`: the only real failure is the turbo11 pin.
* turbo11 is deterministic (`proof.result_hash == run_design_proof().result_hash` passes) and
  no source under `packages/turbomachinery` changed after the pin was written
  (`git log cc84409..HEAD -- packages/turbomachinery` → 0 commits; the pin line itself was
  introduced by `cc84409`, 2026-09-22). So the pin is either stale in the dependency graph
  around it or host-dependent — **UNVERIFIED which**; the pin needs an owner decision, not a
  number in a summary.

---

## 8. Reproduce

```powershell
# full test truth (correct invocation)
cd E:/engineering-portfolio-audit/repos/aero-multiphysics-workbench
uv run --directory services/api pytest -q

# staged timings, gas turbine / aircraft
pwsh -NoProfile -File E:/engineering-portfolio-audit/evidence/aero-3d-speed/run_bench.ps1 `
  -Case gasturbine -Mode stock -BaseSize 14 -Tag myrun
pwsh -NoProfile -File .../run_bench.ps1 -Case aircraft -Mode stock -BaseSize 24 -Tag myrun
pwsh -NoProfile -File .../run_bench.ps1 -Case aircraft -Mode stock -BaseSize 60 -Tag wb -Components wing,fuselage

# memoization A/B
... -Mode fast -BaseSize 14 -Tag fast

# parallel vs sequential (2 independent cases)
pwsh -NoProfile -File .../parallel_demo.ps1 -SizeA 14 -SizeB 14

# converter root cause
uv run --directory services/api python .../probe_converter.py
```

---

## 9. UNVERIFIED / out of reach on this host

* Solver-side mesh quality: `checkMesh` (OpenFOAM) on the exported mesh, and whether
  `Relocate3D`'s 35 s actually improves solver-relevant metrics. Needs a solver run; no
  full-wave/CFD solver was used here.
* True boundary-layer extrusion: `native_mesh.py:527-534` only installs a *size field* and
  records `boundary_layer_achieved=True` with the honest detail "achieved size field only".
  Whether that is enough for a y+-sensitive case needs a solver (UNVERIFIED).
* Whether the turbo11 hash pin is stale-by-code or host-dependent — requires bisecting the
  dependency graph around `run_design_proof`, which is outside this item.
* Multi-worker scaling beyond 2 processes: not tested (4.4 GB free RAM on a shared host).
* Everything else here is a measured number from a command or file named above.

## 10. FILES

```
E:/engineering-portfolio-audit/evidence/aero-3d-speed/
  REPORT.md                 this report
  bench_pipeline.py         stage-timing + A/B harness (wraps gmsh, no repo edits)
  run_bench.ps1             runner (uv env + PYTHONPATH)
  parallel_demo.ps1         sequential-vs-concurrent wall clock + hash equality
  probe_converter.py        FreeCAD vs OCP conversion root cause
  probe_turbo11.py          turbo11 design-proof hash reproduction
  pytest_full.log           full suite output (4 failed / 1790 passed)
  parallel_demo.txt         parallel timing + hash equality output
  work/<case>-<mode>-<tag>/record.json   per-run JSON (stages, gmsh phases, hashes)
  work/<case>-<mode>-<tag>/cad-*/        exported STEP files
  work/<case>-<mode>-<tag>/mesh/*.msh    written meshes
```