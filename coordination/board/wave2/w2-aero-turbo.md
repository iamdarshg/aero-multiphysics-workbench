# W2 aero — extending the 3D speedup to the turbo and airframe paths

Repo: `E:/engineering-portfolio-audit/repos/aero-multiphysics-workbench`
Branch checked out: `audit/baseline-verification-20261111`, HEAD `6263f5c`. Since wave 1's
`7fbfc19` the only commits are `coordination/*` board markdown — `git diff --name-only
7fbfc19..HEAD -- packages examples solvers` is empty, so wave-1 numbers are still valid for
this tree. **Not modified**: every optimisation below is implemented in this evidence directory
and applied by wrapping or re-implementing the call sequence in the harness; no repo file,
branch, or git object was touched (`git status --porcelain` empty at start and end of this work).

Environment: Windows 11, 16 logical CPUs / 8 vCPU usable, **1.5–3.2 GB RAM available
during these runs** (the host is shared with the other audit agents), `uv` 0.9.6, repo venv:
Python 3.12.2, gmsh 4.15.2, cadquery 2.8.0 (OCP).

Correct test invocation for this repo is `uv run --directory services/api pytest -q` from the
repo root. A bare root `pytest` / `mypy` produces false failures and was not used.

Inherited from wave 1 (`evidence/aero-3d-speed/REPORT.md`), not re-derived here: the 1.73×
two-process gas-turbine speed-up with sha-identical meshes, the 4 M-element base-14 mm
baseline, and the fact that the aircraft demo is analytical only. Wave 1 measured **one**
path (the gas-turbine flowpath) at **one** size.

---

## 1. The three paths, and what each actually produces

| path | entry point | 3D output | status |
|---|---|---|---|
| **turbo** | `examples/gas_turbine` → `packages/geometry/duct_system.py::build_duct_system` → `packages/mesh/native_mesh.py::build_native_mesh` | 11 STEP files + `.msh` | **works** (accepted, min SICN ≈ 0.11) |
| **airframe** | `packages/airframe/aeroworkbench_airframe/aero_geometry/assembly.py::parametric_model` → 7 lofted solids → STEP/BREP → gmsh | 16 STEP+BREP files; **no mesh** | CAD works, **mesh fails closed at every size** |
| **aircraft** | `examples/aircraft/geometry.py` + `system.py` | none | **analytical only**, 0.60 s |

`examples/aircraft` never builds 3D geometry: `make_aircraft_geometry()` returns a canonical
`GeometryModel` of 7 named surfaces (`examples/aircraft/geometry.py:7-25`) and
`run_aircraft_demo()` evaluates an envelope (`examples/aircraft/system.py:13-40`). There is
no mesh stage to speed up on that path — this is a property of the code, not a limitation of
the measurement.

---

## 2. STAGE_TIMINGS (solo runs, one process per case = the way the pipeline is invoked)

### 2a. turbo — 3-stage flowpath, base 30 mm
`work/turbo-probe30/record.json` — 438,852 elements, min SICN 0.111092, 26 physical groups.

| stage | s | share |
|---|---:|---:|
| geometry definition (`build_duct_system`) | 0.0002 | 0 % |
| CAD build (10 solids, incl. ~5.8 s one-time kernel warm-up) | 6.33 | 25 % |
| STEP export (11 files) | 0.88 | 3 % |
| **mesh stage** | **18.16** | **72 %** |
| ├ gmsh init / finalize | 0.14 / 0.15 | 1 % |
| ├ STEP import (`merge`×10 + `synchronize`×10) | 0.57 | 2 % |
| ├ `occ.fragment` | 0.22 | 1 % |
| ├ groups + fields (physical groups, BL size field) | 0.01 | 0 % |
| ├ **`mesh.generate` 3D (Delaunay, Algorithm3D=1)** | **11.77** | **46 %** |
| ├ **`optimize("Relocate3D")`** | **3.08** | **12 %** |
| ├ quality (`getElements` + 5×`getElementQualities`) | 0.91 | 4 % |
| └ write `.msh` 4.1 ASCII | 0.91 | 4 % |
| **TOTAL** | **25.37** | |

Other turbo sizes: base 28 mm → 24.16 s, 526,056 elements, SICN 0.1165; base 32 mm → 14.27 s,
356,304 elements, SICN 0.1130. Warm CAD build (second build in the same process) is 0.52 s —
the ~5.8 s above is a one-time cadquery/OCP warm-up, not per-case work.

### 2b. airframe — full `fixed_wing.json` assembly, base 24 mm
`work/airframe-probe24/record.json` — **no mesh produced**.

| stage | s | share |
|---|---:|---:|
| fixture parse + assembly | 2.48 | 3.5 % |
| CAD build (7 lofted solids, incl. 7–14 s one-time kernel warm-up) | 14.89 | 21 % |
| STEP+BREP export (16 files) | 1.95 | 2.8 % |
| mesh spec | 0.007 | 0 % |
| **mesh attempt** | **51.41** | **72.7 %** |
| ├ STEP import (`merge`×7) | 2.74 | 3.9 % |
| ├ **`occ.fragment` (7 coincident/overlapping solids)** | **46.52** | **65.8 %** |
| ├ groups | 0.15 | 0.2 % |
| └ `mesh.generate` | 1.76 → **raises** `Invalid boundary mesh (overlapping facets) on surface 1 surface 915` | |
| **TOTAL (aborted)** | **70.75** | |

The same path at 18/24/30 mm: 58.17 / 47.71 / 49.17 s, all three raise the same exception
(`work/sweep-airframe-a1/records.json`). `occ.fragment` is size-independent and is 66–75 % of
the path. It also varies 42.5 → 82.5 → 126.3 s across repeated calls **within one process**
(same file) — a 3× spread attributed to host contention/process state, cause UNVERIFIED;
that spread is larger than every optimisation measured on this path, which is why no
wall-clock speed-up is claimed for it.

Warm airframe CAD build is 1.05 s, export 1.7–2.1 s.

### 2c. aircraft — analytical envelope
`work/aircraft-probe/record.json`: 0.603 s total (geometry definition 0.013 s + envelope
0.590 s), 7 canonically named surfaces, `meshed: false`.

---

## 3. Where the seconds go, per path

| path | slowest stage | share of path | second |
|---|---|---:|---|
| turbo | `mesh.generate` 3D | 46 % | `optimize("Relocate3D")` 12 % |
| airframe | `occ.fragment` | 66 % | STEP import 3.9 % |
| aircraft | envelope evaluation | 98 % of 0.6 s | — |

gmsh is serialised **in process** by `_MESH_LOCK`,
`packages/mesh/aeroworkbench_mesh/native_mesh.py:28`; `initialize()`/`finalize()` bracket every
single request (`:304`, `:583`), and every request re-merges every STEP (`:317-321`) and
re-fragments (`:334`). Nothing is cached — the key material is computed at `:592-607` and only
recorded in the receipt.

---

## 4. The three optimisations, measured

### 4a. gmsh session reuse — "cache the gmsh session, avoid re-import"
Harness: `bench_session.py` (`GmshSession`). Import + `occ.fragment` + physical groups are
done **once**; each variant then sets new characteristic lengths, `mesh.clear()`, rebuilds the
size fields, generates, optimises, measures and writes its own `.msh`. Two modes, same
process, same workload: `--fresh` (stock path per variant) vs `--session`.

**turbo, 3-size sweep 28/30/32 mm** (`work/sweep-turbo-s3`, `work/sweep-turbo-t2`):

| | s |
|---|---:|
| before — 3 stock runs, process per case | **70.75** |
| after — CAD+STEP once (7.10) + session prep (0.35) + 3 re-meshes (16.57+15.53+11.55) | **51.10** |
| **speed-up** | **1.38×** |

Session prep is only 0.35 s (import 0.19, fragment 0.14, groups 0.01) — on the turbo path the
reusable part is small, so session reuse buys 1.38× at best.

**airframe wing+body, 2-size sweep 60/90 mm** (`work/sweep-airframe-wb`) — the one airframe
configuration that does write a `.msh`:

| | 60 mm | 90 mm | total |
|---|---:|---:|---:|
| before (stock, process per case) | 14.31 | 4.61 | **18.92** |
| after (one session) | 0.61 | 0.49 | **5.19** |
| speed-up | | | **3.65×** |

**airframe full assembly: the session must NOT be reused.** After a failed `mesh.generate`,
the next variant on the same session does not reproduce the documented failure — it silently
returns an empty mesh (`MESH_QUALITY_UNMEASURED`, `element_count 0`) instead of raising
`Invalid boundary mesh` (`work/sweep-airframe-a1/records.json`, session variants 24/30).
A safe implementation has to discard the session on any failure, which on this path means
re-fragmenting every time → no saving. Measured, not assumed.

### 4b. Content-addressed mesh cache — "avoid re-import" for an unchanged request
Harness: `bench_cache.py`. On a miss it calls the stock `build_native_mesh` and stores the
`.msh` plus the receipt; on a hit it copies the mesh and rehydrates the receipt (**no gmsh
call at all**).

turbo, 30 + 32 mm, cold then warm (`work/cache-turbo-geo2/records.json`):

| | cold | warm (hit) | speed-up |
|---|---:|---:|---:|
| base 30 | 19.64 | 1.19 | **16.5×** |
| base 32 | 12.94 | 1.11 | **11.6×** |
| **both** | **32.57** | **2.30** | **14.15×** |

Cold-vs-warm receipt comparison with the cache layer: `receipt_diffs: {}` — identical state,
element count, min SICN, topology fingerprint, physical groups, interfaces, periodic pairs,
orphans, warnings and input hashes (excluding the two fields that legitimately differ:
`mesh_path`, and `input_hashes["artifact:*"]`, see below).

**Why the key cannot be the STEP bytes.** The OCC STEP writer stamps the wall clock into
`FILE_NAME`:

```
FILE_NAME('Open CASCADE Shape Model','2026-11-14T19:16:32', ...)   # cold
FILE_NAME('Open CASCADE Shape Model','2026-11-14T19:17:00', ...)   # warm
```

Two exports of the *same solid* differ (`evidence/w2-aero-turbo/step_nondeterminism.txt`).
Consequences, both measured: (i) a bytes-keyed cache has a **0 % hit rate** — the first
version of this harness missed on every warm call (`work/cache-turbo-c1/records.json`, keys
`15518f9b…` vs `62b968a2…` for identical geometry); (ii) the receipt's own
`input_hashes["artifact:<component>"]` (`native_mesh.py:596-601`) is non-deterministic for
identical inputs, so receipts for the same geometry cannot be compared across runs. Keying on
`geometryHash + meshSpecDigest` (both stable, `:592-594`) fixes the hit rate.

### 4c. One process per independent case — the lever that actually scales
`bench_parallel.py` (per path) and `bench_batch.py` (all three paths at once), one OS process
per case, all launched together.

turbo, 3 cases, 3 workers (`work/parallel-turbo-p3.json`): sequential **70.75 s** → concurrent
**28.44 s** = **2.49×**; `identical: true`.

Whole three-path batch, 7 cases — turbo 28/30/32, airframe 18/24/30, aircraft
(`work/batch-all1seq.json` vs `work/batch-all1.json`):

| path | case | sequential s | concurrent s | state |
|---|---|---:|---:|---|
| turbo | 28 mm | 25.83 | 29.32 | completed |
| turbo | 30 mm | 20.75 | 26.97 | completed |
| turbo | 32 mm | 20.57 | 26.15 | completed |
| airframe | 18 mm | 54.25 | 61.67 | exception (same failure) |
| airframe | 24 mm | 55.22 | 61.70 | exception (same failure) |
| airframe | 30 mm | 53.21 | 61.67 | exception (same failure) |
| aircraft | — | 2.73 | 3.87 | analytical |
| **total wall** | | **232.68** | **61.73** | **3.77×** |

Concurrency costs 12–30 % per case (host is shared, 16 logical CPUs, 2.6–3.3 GB available at
launch), but the wall clock collapses to the longest single case. CPU-seconds are unchanged:
this is a wall-clock win, not a work reduction.

---

## 5. CORRECTNESS

Every completion below is compared on the written `.msh` **sha256** and element count.

| comparison | run A | run B | sha256 | elements | verdict |
|---|---|---|---|---|---|
| turbo 28 mm stock vs session | `sweep-turbo-t2/fresh/28` | `sweep-turbo-s3/session/28` | `ab7db8a3…ab7511` = `ab7db8a3…ab7511` | 526,056 = 526,056 | **identical** |
| turbo 30 mm stock vs session | `turbo-probe30` | `sweep-turbo-s3/session/30` | `3a6a77e5…ff6a56` = `3a6a77e5…ff6a56` | 438,852 = 438,852 | **identical** |
| turbo 32 mm stock vs session | `sweep-turbo-t2/fresh/32` | `sweep-turbo-s3/session/32` | `4066eeff…7b4c54` = `4066eeff…7b4c54` | 356,304 = 356,304 | **identical** |
| turbo 28/30/32 sequential vs concurrent (3 workers) | `parallel-turbo-p3` seq leg | conc leg | all three equal | equal | **identical** |
| airframe wing+body 60 mm stock vs session | `sweep-airframe-wb/fresh/60` | `session/60` | `97579c05…59f8a4` = `97579c05…59f8a4` | 7,912 = 7,912 | **identical** |
| airframe wing+body 90 mm stock vs session | `sweep-airframe-wb/fresh/90` | `session/90` | `98f82e86…04b1` = `98f82e86…04b1` | 6,176 = 6,176 | **identical** |
| turbo mesh cache cold vs warm | `cache-turbo-geo2/cold` | `warm` | equal | 438,852 / 356,304 | **identical**, `receipt_diffs {}` |

So the session path is **byte-exact** whenever `mesh.generate` succeeds: same node positions,
same element ordering, same file bytes. It is only the *failure* case that is not reproducible
(§4a).

**What cannot be proven, and is not claimed:**

* The full airframe assembly produces **no accepted mesh at any tested size** — 18/24/30 mm all
  raise `Invalid boundary mesh (overlapping facets)`; wing+body meshes at 60/90/120 mm but is
  rejected by the quality gate with min SICN 2.77e-5 / 2.72e-5 / 1.3e-5 against a 0.05 floor.
  A mesh-sha correctness proof for a *delivered* airframe mesh is therefore impossible today;
  the airframe correctness proof above is on the `.msh` file that is written before the gate.
* The airframe STEP/BREP artefacts cannot be compared by sha across runs at all (§4b).

---

## 6. SPEEDUP per path, and COMBINED

| path | workload | before | after | speed-up | how |
|---|---|---:|---:|---:|---|
| **turbo** | 3 sizes, 28/30/32 mm | 70.75 s | 28.44 s | **2.49×** | one process per case, 3 workers |
| **turbo** | same, single process | 70.75 s | 51.10 s | **1.38×** | gmsh session reuse |
| **turbo** | repeat of one unchanged case | 19.64 s | 1.19 s | **16.5×** | content-addressed mesh cache |
| **airframe** | wing+body, 60/90 mm | 18.92 s | 5.19 s | **3.65×** | gmsh session reuse |
| **airframe** | full assembly, 18/24/30 mm | 162.68 s | 61.67 s | **2.64×** | one process per case (outputs unchanged: all three still fail closed) |
| **aircraft** | 1 run | 2.73 s | 3.87 s | **0.71×** (slower under contention) | nothing to gain: 0.60 s analytical, no 3D stage |
| **COMBINED** | all 7 cases, three paths | **232.68 s** | **61.73 s** | **3.77×** | one process per case, all launched together |

Notes on the combined number:
* It is **measured end-to-end**, both legs with the same harness, same case set, same host.
* It is a wall-clock win only. Total CPU-work is unchanged (~230 CPU-s); the batch now finishes
  in the time of its longest single case (one airframe attempt, 61.7 s), because the airframe
  path's fragment cannot be shortened or reused.
* The ceiling is therefore set by the airframe path, not the turbo path. If the airframe's
  deterministic meshing failure were detected **before** `occ.fragment` (a cheap 2D surface-mesh
  trial, ≈1.5 s, instead of fragmenting for 42–46 s and then failing), the batch would drop to
  roughly the turbo wall (~29 s) — that is a defect fix, **UNVERIFIED here** (not implemented,
  not measured).
* Session reuse and per-case parallelism do not stack on this batch: gmsh is serialised in
  process (`native_mesh.py:28`), so K variants in one cached session are *serial*; the parallel
  win comes from K processes each paying their own 0.35 s prep. They stack only for batches
  larger than the core count — projected, not measured.

---

## 7. NEXT_BOTTLENECK

`mesh.generate` (turbo: 10.0–14.5 s of every 11.5–16.6 s re-mesh, 87–88 % of the session
variant) and `occ.fragment` (airframe: 42.5–126 s, 66–75 %, paid before a guaranteed failure)
— both single-threaded gmsh/OCC C++ with no output-identical lever left. The remaining
output-preserving levers are exhausted; the only larger ones change the output and must be a
solver-side decision: `optimize("Relocate3D")` (−3.1 s, −12 %, changes node positions) and
`Mesh.Binary=1` (`native_mesh.py:308`, −0.9 s, changes `mesh_hash`).

---

## 8. FILES

```
E:/engineering-portfolio-audit/evidence/w2-aero-turbo/
  REPORT.md                  this report
  bench_stages.py            three-path stage timing + gmsh phase attribution
  bench_session.py           gmsh session reuse (GmshSession) A/B, fresh vs session
  bench_parallel.py          sequential vs N-worker wall clock, per-path
  bench_batch.py             all three paths launched at once; --sequential baseline
  bench_cache.py             content-addressed mesh cache (miss/hit, receipt rehydration)
  run_bench.ps1              uv run wrapper for bench_stages.py (PYTHONPATH = pytest tree)
  run_session.ps1            wrapper for bench_session.py
  run_parallel.ps1           wrapper for bench_parallel.py
  run_cache.ps1              wrapper for bench_cache.py
  step_nondeterminism.txt    proof that STEP bytes carry a timestamp
  work/turbo-probe30/record.json        turbo 30 mm stage timings
  work/airframe-probe24/record.json     airframe 24 mm stage timings + failure
  work/aircraft-probe/record.json       aircraft analytical timing
  work/sweep-turbo-t2|s3/records.json   turbo sweep, fresh vs session
  work/sweep-airframe-a1/records.json   airframe full sweep, fresh vs session (session hazard)
  work/sweep-airframe-wb/records.json   airframe wing+body sweep, byte-exact proof
  work/parallel-turbo-p3.json           turbo 2.49x A/B
  work/batch-all1.json|all1seq.json     combined 3.77x A/B
  work/cache-turbo-geo2/records.json    cache 14.15x A/B + receipt diff
  work/cache-turbo-c1/records.json      bytes-keyed cache: 0% hit rate evidence
  work/<case>/cad-*/, mesh/*.msh        artefacts and meshes per run
```

## 9. Reproduce

```powershell
cd E:/engineering-portfolio-audit/repos/aero-multiphysics-workbench
$ev='E:/engineering-portfolio-audit/evidence/w2-aero-turbo'

pwsh -NoProfile -File $ev/run_bench.ps1    -Path turbo    -BaseSize 30 -Tag probe
pwsh -NoProfile -File $ev/run_bench.ps1    -Path airframe -BaseSize 24 -Tag probe
pwsh -NoProfile -File $ev/run_bench.ps1    -Path aircraft -Tag probe

pwsh -NoProfile -File $ev/run_session.ps1  -Path turbo -Sizes 28,30,32 -Tag s3 -Fresh
pwsh -NoProfile -File $ev/run_session.ps1  -Path airframe -Sizes 60,90 -Components wing,fuselage -Tag wb -Fresh

pwsh -NoProfile -File $ev/run_parallel.ps1 -Path turbo -Sizes 28,30,32 -Workers 3 -Tag p3

$env:PYTHONPATH = ((Get-ChildItem "$PWD/packages" -Directory | % FullName) + "$PWD/solvers" + "$PWD/examples" + $PWD + $ev) -join ';'
uv run --directory services/api python $ev/bench_batch.py --cases turbo:28,turbo:30,turbo:32,airframe:18,airframe:24,airframe:30,aircraft:0 --tag all1 --sequential
uv run --directory services/api python $ev/bench_batch.py --cases turbo:28,turbo:30,turbo:32,airframe:18,airframe:24,airframe:30,aircraft:0 --tag all1

pwsh -NoProfile -File $ev/run_cache.ps1    -Path turbo -Sizes 30,32 -Tag geo2
```

## 10. UNVERIFIED / out of reach

* The 3× spread in `occ.fragment` (42.5 / 82.5 / 126.3 s, same process, same geometry) —
  attributed to host contention or OCC memory growth; not isolated.
* Any speed-up on the **delivered** airframe mesh: none exists to deliver (fails closed at
  every tested size, gate rejects the two that mesh).
* The "fail fast before `occ.fragment`" saving (§6): proposal, not implemented or measured.
* Multi-worker scaling beyond 3 workers in one path, or beyond 7 processes host-wide: not
  tested (RAM 1.5–3.3 GB free; 7 processes already saturate the shared host).
* Solver-side value of `Relocate3D` / binary msh: unchanged from wave 1, still needs a solver.
* Full pytest suite not re-run: no repo file was modified, and wave 1 already recorded
  `4 failed, 1790 passed` for this HEAD (`evidence/aero-3d-speed/pytest_full.log`).