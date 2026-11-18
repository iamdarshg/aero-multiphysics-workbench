# W2 · drone-mech — accelerating the 191-file STEP corpus

Evidence dir: `E:/engineering-portfolio-audit/evidence/w2-dm-step/`
Repo: `E:/engineering-portfolio-audit/repos/drone-mech` @ `work/2026-11-11` (`0ba96ab`)
Host: Windows 11, 8 cores / 16 logical, 15.2 GB RAM, E: 932 GB (15.9 GB free at start).
Toolchain: `C:\Program Files\Python312\python.exe` — Python 3.12.2, cadquery 2.7.0,
cadquery-ocp (OCP) 7.8.1.1, gmsh 4.15.2, trimesh 4.10.0.
WSL `Ubuntu2404` (8 vCPU, **3 GB** RAM) has no OCP/cadquery/gmsh/numpy, so this work
runs on the Windows 3.12 interpreter, not in WSL.

Read-only on git: nothing committed, reset, or pushed. All writes are inside this
evidence dir.

**Caveat that applies to every timing below: this host was shared with the other
rectification agents.** Competing Python benchmarks were running (observed PIDs
`33072`, `19940` under `evidence/w2-aero-turbo/`, system CPU load 53%). Absolute
seconds are therefore inflated and vary run to run; the serial and parallel passes
ran back to back under the same conditions, so the *ratio* is the defensible number.

---

## 1. The decisive question: GENERATED or COMMITTED?

**COMMITTED.** The corpus is generated offline by checked-in generator scripts, and
the resulting bytes are committed as the canonical artefact. Nothing regenerates
them at run time, under test, or in any build step.

### 1.1 Proof it is committed (git)

| check | command | result |
|---|---|---|
| all 205 artefacts tracked in HEAD | `git ls-tree -r --name-only HEAD \| Select-String '\.(step\|stp\|brep)$'` | **205** = 191 `.step` + 14 `.brep` |
| tracked and unmodified | `git ls-files` → 205; `git diff --name-only HEAD -- '*.step' '*.brep'` | **0** modified |
| no Git-LFS indirection | `git check-attr -a <step>` → empty; no `.gitattributes`; `git cat-file -s` returns full blob size | real blobs, not pointers |
| history, not one import dump | `git log --diff-filter=A -- highspeed_edf/deliverables/phase1{0,1,2,3}/step` | all four added in `832fa22` (2026-09-30) |
| phase-15 geometry | `git log -- .../phase15_geometry/step` | `832fa22`, `66391c5`, `f7c23af` (2026-10-31) |
| print prototype | `git log -- .../print_prototype/main_wing` | `24a92a2` (2026-10-30) |
| packed, not loose | `.git/objects/pack/pack-ab9f07ba….pack` | **994.1 MB** in one pack |

Corpus: **205 files, 1,231,029,316 bytes (1.146 GiB)** = 43.2% of the repo's 2.66 GB
working tree.

### 1.2 Proof it is nevertheless *generated* (rebuildable, not hand-edited)

Generators that mint these exact paths:

- `highspeed_edf/phase15/optimization/phase15_generate_geometry.py` — 86 STEP in
  `deliverables/phase15_geometry/step` + 3 stock nests. Its `build()` at `:886`
  **deletes** `*.step` in its two owned dirs before rebuilding (`:890-892`), i.e. it
  treats them purely as derived output.
- `highspeed_edf/phase11/optimization/phase11_generate_cad_cam.py` —
  `phase11_flowpath_R{%03d}.step` (`:213`), `phase11_full_assembly_R{%03d}.step`
  (`:258`), `phase11_EDF_{A,B}_R{%03d}.step` (`:260-261`).
- `deliverables/phase12/phase12_generate.py`,
  `phase13/optimization/phase13_generate_cad_cam.py`,
  `optimization/phase10_generate_deliverables.py`.

**But there is no run-time producer.** No Makefile, Taskfile, justfile, CI workflow or
`.toml` task regenerates them (a search for `Makefile,*.mk,Taskfile*,justfile,*.yml,
*.yaml,*.toml,*.cfg,*.ini` returns only `requirements*.yaml` and FSI case
`config.yml`). No Python file invokes a generator as a subprocess
(`'subprocess.*generate_geometry'` → **0 hits**). The verification suite only reads
the generator *source*: `sha256(GENERATOR)`
(`verification/test_material_matrix.py:65`), `ast.parse(...)`
(`verification/motor_drive_screen.py:131`), `read_generator_constants(...)`
(`verification/tests/test_motor_drive_screen.py:113`). The generator's own sha256 is
source-pinned in `highspeed_edf/verification/material_sources.json`, which holds
exactly 2 entries (the mass CSV and the generator) — **no STEP file is hash-pinned**.

### 1.3 Why a cache keyed on geometry inputs cannot be the fix here

Every STEP file carries an OCC export timestamp in its header:

```
FILE_DESCRIPTION(('Open CASCADE Model'),'2;1');
FILE_NAME('Open CASCADE Shape Model','2026-09-26T00:06:18',('Author'),...
```

- **191/191** STEP files carry `FILE_NAME(...,'<ISO timestamp>',...)`
  (`data/step_headers.json`), **109 distinct** stamps, range
  `2026-09-25T21:14:03` → `2026-10-31T13:49:54`.
- A re-run of the generator therefore **cannot** be byte-identical: the header
  timestamp changes on every export. "Cache keyed on geometry inputs, prove
  byte-identical output" is unachievable for this corpus *by construction* — which is
  precisely why committing the bytes is the right call.
- **0 duplicate sha256 across the 205 files** — no redundant copy to dedup.
- Nothing reads the commit timestamps at run time; the timestamp is inert metadata.

Consequence: per-run generation cost is **zero**. The recurring cost this corpus
imposes on every validation pass is the **import-and-check sweep**. That is what is
optimised below.

---

## 2. The pipeline that is actually timed

The repo's own adapter, reproduced field for field:

- `highspeed_edf/verification/native_adapters.py:29` `import_step()` — cadquery
  `importStep`, then per solid `BRepCheck_Analyzer(...).IsValid()`, `Volume()`,
  `BoundingBox()`; aggregate `valid = bool(records) and all(valid_brep and volume>0)`.
- `highspeed_edf/verification/native_adapters.py:55` `import_all_step()` — a **serial**
  loop over one directory; `status` gated on `len(files) == 81` (`:67`). It globs only
  `.step`/`.stp`, so the 14 `.brep` files are never validated by it.

`scripts/sweep.py` reimplements `import_step()` exactly, adds `.brep` support
(`BRepTools.Read_s` + `cadquery.Shape.cast`), and sweeps the whole corpus. Timing
instrument: wall clock around import+validity only (`seconds`), sha256 timed
separately (`sha256_seconds`).

### 2.1 Scripts in this evidence dir

| script | role |
|---|---|
| `scripts/sweep.py` | the validator; `--mode serial\|parallel`, optional `--cache` (sha256-keyed) |
| `scripts/sweep2.py` | crash-tolerant driver: per-file `.start`/`.json` markers, `ProcessPoolExecutor`, pool restart on kernel death, resume by construction |
| `scripts/compare.py` | canonical-blob diff between two sweeps + speedup; exit 1 if they differ |
| `scripts/attribute.py` | referrer attribution, producer/reader/doc split, orphan proof |
| `scripts/headers.py` | STEP header timestamp + duplicate scan |
| `scripts/stats.py`, `scripts/progress.py`, `scripts/orphan_cost.py`, `scripts/corpus_shape.py` | analysis |

### 2.2 Why the driver is crash-tolerant

The first attempt — a plain in-process serial loop
(`scripts/sweep.py --mode serial`, job `pwsh-56bc065e98ef4c95`) — **died after
~15.5 minutes with exit 1 and wrote nothing**, losing every completed result. The
cause is **undetermined**: no traceback was written, and on Windows a force-killed
process also settles as exit 1 without a signal marker, so this could have been a hard
OCC kernel termination or an external kill. What is certain is the failure mode — an
in-process loop has no way to keep what it already finished.

`sweep2.py` therefore writes `<key>.start` before each artefact and `<key>.json`
after, so a hard death loses at most the in-flight file and the next run resumes. The
death never reproduced: all three timed runs completed with `pool_runs: 1`,
`pool_died: 0`, `crashes: []`, and the serial baseline produced all 205 records in one
pass.

---

## 3. TIMING

### 3.1 Serial baseline (the correctness reference)

`data/serial.json`, 205 artefacts, 1,231,029,316 bytes, 1 worker:

| metric | value |
|---|---|
| wall | **923.371 s** (15 min 23 s) |
| time inside import+validity | **906.637 s** |
| sha256 total | 8.371 s |
| **per artefact, mean** | **4.42 s** |
| per artefact, median | 0.41 s |
| per artefact, p90 | 12.13 s |
| per artefact, max | 47.35 s (`phase13_full_assembly_R030.step`) |
| **per MB** | **0.772 s/MB** |
| solids imported | 5,609 (median 4 per file, max 516) |
| valid / invalid / errors | **198 / 7 / 0** |

The distribution is extremely skewed: 31 files >10 MB hold 80.5% of the bytes, the
top 10 hold 45.7%. Ten assembly STEPs cost ~40-47 s each, while **107 of 205** files
finish under 0.5 s (and hold only 18.6 MB between them) — which is why thread-level
parallelism over files pays: most items are small, the tail is a handful of heavy
assemblies.

Slowest artefacts (serial seconds):

| s | solids | MB | artefact |
|---|---|---|---|
| 47.3 | 172 | 56.9 | `deliverables/phase13/step/phase13_full_assembly_R030.step` |
| 47.0 | 516 | 60.7 | `deliverables/phase15_geometry/step/phase15_airframe_full_assembly.step` |
| 46.8 | 227 | 51.3 | `deliverables/phase10/step/phase10_full_assembly.step` |
| 46.1 | 255 | 53.8 | `deliverables/phase12/step/phase12_full_assembly_R040.step` |
| 42.1 | 234 | 51.4 | `deliverables/phase11/step/phase11_full_assembly_R000.step` |
| 41.1 | 249 | 54.2 | `deliverables/phase12/step/phase12_full_assembly_R035.step` |

### 3.2 Parallel

`data/parallel6.json` (6 workers) and `data/parallel6_cold.json` (6 workers,
cache write-through), same corpus:

| run | wall | speedup vs serial |
|---|---|---|
| serial, 1 worker | 923.371 s | 1.00x |
| parallel, 6 workers | **218.003 s** | **4.24x** |
| parallel, 6 workers (repeat) | **221.513 s** | **4.17x** |
| parallel, 6 workers + warm cache | **14.834 s** | **62.2x** |

Parallel scaling: 4.17-4.24x on 6 workers = **70-71% efficiency**. Sum-of-import time
*rises* under parallelism (906.6 s → 1,081.8 s / 1,103.3 s) because six OCC processes
contend for core time and cache; the wall-clock win is still 4.2x. Worker working set
was observed at 0.4-0.6 GB per process during the serial pass, so 6 workers fit
comfortably in 15.2 GB; 6 (not 8) was chosen to bound memory and because the host was
already loaded by other agents.

**Cache design** (`sweep.py --cache`): key = sha256 of the artefact's own bytes, one
JSON record per key. A hit cannot be stale with respect to content, because the key is
the content. Warm pass re-hashes everything (unavoidable, that is how the key is
formed) and skips all OCC work: 205/205 hits, 0.0 s of geometry work.

### 3.3 Correctness proof (the important part)

`scripts/compare.py` builds a canonical blob per artefact — every field except timing
and run-provenance (`seconds`, `sha256_seconds`, `cache_hit`, …) — and hashes the
whole map. Three comparisons, all over the same 205 paths:

| comparison | file | digest (both sides) | differing records | verdict |
|---|---|---|---|---|
| serial vs parallel-6 | `data/compare_serial_vs_par6.json` | `99301ffc3fd3b693…` | 0 | **identical** (4.236x) |
| serial vs parallel-6 cold | `data/compare_serial_vs_par6cold.json` | `99301ffc3fd3b693…` | 0 | **identical** (4.168x) |
| cold vs warm-cache | `data/compare_cold_vs_warm.json` | `99301ffc3fd3b693…` | 0 | **identical** (14.933x) |

All three independent comparisons collapse to the **same** canonical digest
`99301ffc3fd3b693ff626a28c703a0d64f7ea3cc348a5e5d613adf2a17c56bbe` — serial, both
parallel passes, and the fully cached pass all return one and the same verdict set.

So the 4.2x parallel speedup and the 62x warm-cache speedup return *exactly* the
serial verdicts: same 205 paths, same sha256, same solid counts, same 5,609 solids,
same per-solid `valid_brep`/`volume_mm3`/`bbox_mm`, same 198 valid / 7 invalid, same 0
errors. Not approximate agreement — byte-identical canonical blobs.

---

## 4. Orphans: which of the 191 are referenced by anything?

`scripts/attribute.py` classifies every text referrer by what it does with the name —
`PRODUCER` (a `.py` with `exportStep`/`save_assembly`), `READER` (a `.py` with
`importStep`/`BRepTools`/`gmsh.open`, including directory `glob`s that pick the file
up), `DATA` (a checked-in `.json`/`.csv`/`.yaml` manifest listing it), `DOC` (prose
only). The test matches the full basename **and** the stem, because a report could
cite a geometry without its extension.

Result over 748 text files: **202 CONSUMED, 3 ORPHAN, 0 produced-only, 0 doc-only**
(`data/references.json`).

| orphan | bytes | serial s | sha s | solids | valid |
|---|---|---|---|---|---|
| `deliverables/phase11/step/phase11_EDF_A_R000.step` | 26,729,186 | 23.1 | 0.71 | 113 | **False** |
| `deliverables/phase11/step/phase11_EDF_B_R000.step` | 25,627,982 | 22.7 | 0.72 | 111 | True |
| `deliverables/phase11/step/phase11_full_assembly_R000.step` | 53,944,331 | 42.1 | 1.45 | 234 | **False** |
| **total** | **106,301,499 (8.64%)** | **87.9 (9.70% of import)** | **2.88** | | |

Criterion, and why these three and only these three:

1. **Zero mentions anywhere.** Exact-string searches for each basename report **0
   hits**, and searches for the stem alone also report **0 hits**, across 748 text
   files (`orphan_cost.py`). No code, no manifest, no report names them.
2. **Superseded by the current config.** `phase11/configs/phase11_iterative_optimization.json`
   declares `turnRadiiM: [0.065, 0.07, 0.075]`; the generator emits the EDF/full
   assembly at `min(turnRadiiM)` → `R065` only (`phase11_generate_cad_cam.py:202,258`).
   Export stamps confirm the history: the R000 trio was written
   `2026-09-25T23:16:46 - 23:17:47`, the R065/R070/R075 set 35-50 minutes later
   (`2026-09-26T00:03:08 - 00:06:42`). R000 is the earlier design point.
3. **Nothing would recreate them.** The current generator cannot emit `R000`, so their
   only source is the old config — deleting them is not self-healing, it is a
   deliberate corpus trim. (If that history is wanted, keep the commit; git has it.)

Impact of deletion, measured not guessed: serial wall 923.4 s → **832.6 s** (1.109x,
subtracting the orphans' 87.9 s of import *and* 2.88 s of hashing); corpus
1,174.0 MiB → **1,072.6 MiB**. Combined with the parallel pass (arithmetic on the two
measured factors, *not* a separately measured run): ~221.5 s → ~199.7 s ≈ **4.62x** vs
serial. Bonus: two of the three orphans are among the 7 invalid artefacts, so the
invalid count drops 7 → 5.

---

## 5. Validation findings (side effect of the sweep, worth reporting)

The sweep is the first pass over all 205 artefacts, and **7 of them fail the repo's own
`valid` criterion** (`data/serial.json`). Three distinct defect classes:

1. **BREP-invalid on import** — `phase11_EDF_A_R000.step` (solid 111 of 113),
   `phase11_full_assembly_R000.step` (solid 111 of 234), and the three fuselage-shell
   exports `fuselage_battery_bay_shell_candidate_brep.step`,
   `fuselage_battery_bay_shell_compoundcut_repair.step`,
   `..._compoundcut_repair_order2.step` (solid 2 of 4 in each, volume 76,876.2 mm³).
2. **Zero-volume slivers** — `phase12_full_assembly_R035.step` (solids 110, 114, 228,
   231) and `phase12_interchangeable_inlet_split_R035.step` (solids 0, 4, 8, 11), all
   with `valid_brep=True` but volume ≈ **-1.92e-21 mm³**. Note the *same* solid indices
   fail in both files — the defect is inherited, not independent.
3. **STEP/BREP disagreement** — `fuselage_battery_bay_shell_candidate.brep` imports
   clean (4 solids, valid) while its STEP export
   `fuselage_battery_bay_shell_candidate_brep.step` is BREP-invalid at solid 2. The
   round-trip introduced the defect; consistent with commit `f7c23af` ("Record
   fuselage shell repair candidates and round-trip failures").

All 14 `.brep` files are valid (20.75 MB, 1-20 solids each, 50 solids total, 11.57 s
serial). Note that `import_all_step()` skips `.brep` entirely: it globs only
`.step`/`.stp`, so those 14 files are outside the repo's existing validation - and its
`len(files) == 81` gate means any file added to or removed from a swept directory
turns `status` to `FAIL`, which is why the orphan trim is only safe for
`deliverables/phase11/step` (no `import_all_step` caller points there; callers are
`verification/negative_fixtures.py:51` with an empty dir, and the CLI path at
`native_adapters.py:394`).

---

## 6. Recommendations, in order of value

1. **Run the sweep parallel (4.2x, proven identical).** 6 workers, `pool_died: 0`.
   Any consumer of 191 STEP files should not be a `for path in files:` loop —
   `native_adapters.import_all_step()` is one, and at 906.6 s serial for this corpus it
   is the single largest avoidable cost.
2. **Add the sha256 cache for repeat passes (62x warm).** With a validator-version salt
   (see §7) this makes the sweep effectively free when nothing changed, which is the
   common case in CI/pre-commit use.
3. **Delete the 3 R000 orphans** — 8.64% of bytes, 1.109x, zero references, provably
   superseded. Do it as a deliberate commit with the export timestamps above as the
   justification.
4. **Extend `import_all_step()` to `.brep`** and replace the hard-coded
   `len(files) == 81` with a declared manifest — the count gate is currently a
   foot-gun that any corpus edit trips.
5. **Fix the 7 invalid artefacts**, starting with the two zero-volume sliver families,
   since they share failing solid indices.

---

## 7. Limits of this evidence

- Timings are from a host shared with other agents; absolute seconds are inflated and
  varied (parallel repeats: 218.0 s vs 221.5 s). Ratios are stable.
- The cache key is the file's sha256 only. It does **not** salt the validator version,
  so if `sweep.py`'s checking logic changes, stale verdicts would be reused. Adding
  that salt is a required follow-up before the cache is trusted in CI.
- 6 workers is the only parallelism measured; 8 was not attempted, so the 70%
  efficiency is a one-point observation, not a scaling curve.
- The ~4.62x combined figure (parallel + orphan trim) is arithmetic on two measured
  components, not a separately measured run.
- The repo's own `import_all_step()` was not executed against this corpus (its
  `len(files) == 81` gate does not match 205 files); the sweep reimplements its
  per-file semantics and is proven equivalent to itself across serial/parallel/cache,
  not to a run of the original function.
- Wave-1 numbers (1.35x cold / ~30x warm; 247 files / 1.31 GB) are cited, not
  re-derived. This corpus measures 205 artefacts / 1.146 GiB for `.step`+`.brep` alone;
  the 247/1.31 GB figure includes `.glb`/`.stl` etc. that this sweep does not import.
- `phase15_generate_geometry.py` was **not executed** — doing so would delete and
  rewrite committed STEP files in the repo, which is out of scope on a read-only
  checkout.

---

## 8. Reproduce

```powershell
$py='C:\Program Files\Python312\python.exe'; $ev='E:/engineering-portfolio-audit/evidence/w2-dm-step'
$root='E:/engineering-portfolio-audit/repos/drone-mech/highspeed_edf'

# inventory + attribution + headers
& $py "$ev/scripts/sweep.py" --mode list --root $root > "$ev/data/inventory.json"
& $py "$ev/scripts/attribute.py"
& $py "$ev/scripts/headers.py"

# serial baseline (~15 min), then parallel (~3.7 min), then warm (~15 s)
& $py "$ev/scripts/sweep2.py" --mode serial   --root $root --records "$ev/data/rec_serial" --out "$ev/data/serial.json"
& $py "$ev/scripts/sweep2.py" --mode parallel --workers 6 --root $root --records "$ev/data/rec_par6b" --cache "$ev/data/cache" --out "$ev/data/parallel6_cold.json"
& $py "$ev/scripts/sweep2.py" --mode parallel --workers 6 --root $root --records "$ev/data/rec_warm"  --cache "$ev/data/cache" --out "$ev/data/parallel6_warm.json"

# equivalence + speedup (exit 1 if the verdicts differ)
& $py "$ev/scripts/compare.py" --a "$ev/data/serial.json"          --b "$ev/data/parallel6_cold.json"
& $py "$ev/scripts/compare.py" --a "$ev/data/parallel6_cold.json"  --b "$ev/data/parallel6_warm.json"
```