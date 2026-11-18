# drone-mech — 3D/CAD geometry pipeline: speed-up + physical re-verification

Agent: dm-3d-speed (session `6fbabe36-50e5-4b0d-b74a-49cbcd4d8c45`)
Date: 2026-11-14. Host: Windows 11, Python 3.12.2, cadquery 2.7.0 / OCP 7.8.1.1.post1 (the repo
pins 2.5.2 / 7.7.2 in `highspeed_edf/verification/requirements-cad.txt`; the difference was not
cross-checked). All git access read-only; nothing in any repo was modified. All outputs are in
this directory.

---

## 1. The pipeline that was timed

The 3D/CAD validation path is `highspeed_edf/verification/native_adapters.py`, driven by
`drone-arm/engineering_acceptance/adapters/mechanical.py:158-265` (one subprocess per check).
The geometry is an already-exported STEP set:
`highspeed_edf/deliverables/phase15_geometry/step/` — **83 `.step` files, 210.6 MB**, plus 3
stock-nest STEPs (86 files / 231.0 MB in total, which is what the check enumerates). The largest
are `phase15_airframe_full_assembly.step` (63.7 MB, 516 solids) and
`phase15_twin_ducts_and_fans.step` (54.1 MB, 244 solids).

Six validation stages were timed with `time.perf_counter()`, each reproducing the exact call the
acceptance harness makes (`bench_before.py`, receipts `before_<stage>.json`):

| stage | what it does | source |
|---|---|---|
| step | import all 86 STEP files + CAD datum check | `native_adapters.py:55-74` |
| motors | 15 pair-wise exact OCC Booleans | `native_adapters.py:145-178` |
| ducts | body shell vs 2 ducts | `native_adapters.py:250-262` |
| battery / connectors | bay fit, connector obstruction | `:265-336` |
| mass | 74-component volume/CG from STEP | `:181-242` |

Generation (`phase15/optimization/phase15_generate_geometry.py`) was **not** re-run: its output
path is hard-coded to the repo (`:26-31`) and rewriting 231 MB of tracked deliverables is
forbidden by the read-only rule. Generation cost is therefore UNVERIFIED (see §8).

## 2. Stage timings (seconds, wall clock)

Before = repo code as-is, serial, no cache. After-cold = empty cache; after-warm = cache populated.

| stage | before | after (cold) | after (warm) |
|---|---:|---:|---:|
| step import (86 files) | 279.30 | 133.58 | **0.72** |
| mass/CG (74 parts) | 56.31 | 60.54 | **1.57** |
| motors (15 pairs) | 1.00 | 1.06 | 0.30 |
| ducts | 2.02 | 1.65 | 1.12 |
| connectors | 3.22 | 3.70 | 2.98 |
| battery | 1.02 | 1.24 | 0.88 |
| **total** | **342.87** | **201.77** | **7.57** |

`before_timings.json`, `after_cold_timings.json`, `after_warm_timings.json`. CadQuery import
overhead is separate (6.6 s idle, 57 s under swarm load) and is not counted per stage.

Ambient CPU load from the 11 sibling agents varied a lot during these runs (the same CadQuery
import took 6.6 s and 57 s minutes apart), so the cold column is load-noisy; the warm column is
not (0.7 s of work is insensitive to load). The load-controlled A/B in §3 is the honest measure
of the parallel gain.

## 3. What was changed (nothing that changes a reported number)

`fast_adapters.py` — a drop-in shadow module, not a repo edit. Three changes:

1. **Content-addressed STEP cache.** Every import is keyed by `sha256(STEP bytes)` + adapter tag
   and stored as `cache/<rev>_<sha>.json` (`fast_adapters.py:34-53`). STEP files are immutable
   deliverables, so the second and every later run of a check reuses the measured per-solid
   records instead of re-parsing 231 MB. This is the change that turns 279 s into 0.72 s.
2. **Process-pool fan-out on a cold cache** (`fast_adapters.py:61-154`), 8 workers, results mapped
   back to the sorted file order so the `files` array keeps the same ordering.
3. **No repeated imports.** `motor_bbox_collision` imported both envelopes afresh for each of the
   15 pairs (30 parses); it now parses each once (6) — `fast_adapters.py:155-195`, cf.
   `native_adapters.py:151-152`. `boolean_interference` re-imported the 1.2 MB body shell once per
   duct; it now shares one shape cache (`fast_adapters.py:197-219`, cf. `native_adapters.py:252-253`).
   The 74-part mass stage is cached the same way (`_volume_centre`, `fast_adapters.py:222-237`).

**Measured parallel gain, load-controlled** (`ab_parallel.py`, interleaved
serial→parallel→parallel→serial so ambient-load drift cancels; the 2 giants + 12 small files,
content hash checked on every arm — all four arms produced the same
`595b7d261a4f7131…` digest):

| arm | run 1 | run 2 | mean |
|---|---:|---:|---:|
| serial | 115.47 s | 95.13 s | 105.3 s |
| 8-process parallel | 62.83 s | 61.98 s | 62.4 s |

Parallel speed-up **1.69×** on identical work. The cold-cache `step` stage drops from 279.3 s to
133.6 s (**2.09×**) because wall time is bounded below by the single 63.7 MB assembly (~65–69 s
serial: 12.4 s read + 34.5 s shape transfer + 18.6 s per-solid work, `probe_split.py`), which no
process pool can split. OCCT's own parallel reader was tried and is inert here: setting
`read.step.parallel` leaves `IVal` at 0 and gives no gain (`probe_ab_parallel.py`).

Net: **45.3× on a re-run** (342.87 s → 7.57 s), **1.70× on a first cold run**.

## 4. Correctness — output is byte-identical

sha256 of the full JSON receipt of each stage, baseline vs accelerated cold vs accelerated warm:

| stage | before | cold | warm | identical |
|---|---|---|---|---|
| step | e66f9a249c28c8d6 | e66f9a24… | e66f9a24… | yes |
| motors | f1a5fbd1958561be | f1a5fbd1… | f1a5fbd1… | yes |
| ducts | b118d67d7a9436a2 | b118d67d… | b118d67d… | yes |
| battery | f25689cf62b4681b | f25689cf… | f25689cf… | yes |
| connectors | 9f3634ff15873a40 | 9f3634ff… | 9f3634ff… | yes |
| mass | 193c8e58f82bf72c | 193c8e58… | 193c8e58… | yes |

Full 64-hex digests are in the stage JSON files; the comparison one-liner is at the end of this
file. Interference count is unchanged: **15 pairs checked, 6 collisions,
0 clearance failures, status FAIL** — identical in all three runs.

## 5. Independent re-verification of 50,033 mm³

`verify_interference.py` → `interference_reverification.json`. Three methods:

| pair | pitch | analytic (closed form) | fresh OCC Boolean | recorded in audit | Monte-Carlo (400k pts) |
|---|---:|---:|---:|---:|---:|
| A_R1–A_R2 | 36 mm | 50,033.004601071**04** | 50,033.004601071**98** | 50,033.004601071**98** | 49,997.5 ± 117.5 (2σ) |
| A_R1–A_R3 | 72 mm | 157.079632679489**66** | 157.079632679489**63** | 157.079632679489**63** | 158.4 ± 4.7 (2σ) |

The closed form is built from the generator source, not from the audit's number:
can `R=21 mm, L=72 mm` and shaft `r=2.5 mm, L=8 mm` (`phase15_generate_geometry.py:104-105, 964-967`)
stacked at 36 mm pitch, so the overlap is a 36 mm coaxial can section plus an 8 mm shaft section:

    V = π(21²)(36) + π(2.5²)(8) = 50,033.00460107105 mm³   (Δ = 9.4e-10 mm³ from OCC, 1.9e-14 rel)

Monte-Carlo uses `BRepClass3d_SolidClassifier` point membership only — no Boolean — and is
consistent at 0.6σ. **The 50,033 mm³ figure is confirmed.**
The 6 collisions decompose exactly as 4 pairs × 50,033.0046 mm³ (adjacent rows, 36 mm pitch) and
2 pairs × 157.0796 mm³ (R1–R3, shaft-in-can), i.e. the "4 pairs" in the handoff is right but the
audit file also carries 2 smaller pairs.

Incidental geometry findings while re-importing (today's tree):
- **86 `.step` files, not 81.** `import_all_step` hard-codes `len(files) == 81`
  (`native_adapters.py:67`), so the check now reports FAIL on file count alone even with zero
  import errors. Stale gate.
- **3 files carry one B-rep-invalid solid each** (`valid_brep: false`, 76,876.216 mm³):
  `fuselage_battery_bay_shell_candidate_brep.step`, `…_compoundcut_repair.step`,
  `…_compoundcut_repair_order2.step`. `native_motor_fit_review.md` states all files imported as
  valid positive-volume solids — that is no longer true of the current tree.

## 6. The 42 × 72 mm motor envelope — UNSOURCED

Model: `MOTOR_CAN_D = 42.0`, `MOTOR_CAN_LENGTH = 72.0`
(`phase15_generate_geometry.py:104-105`), cylinder built at `:964-967`, named
`motor_{A,B}_R{1..3}_3670_42x72_envelope` with the note "Surpass Rocket 3670 4-pole envelope"
(`:969-970`). `HANDOFF.md:51` repeats the 72 mm / 36 mm conflict.

Search results: no datasheet, drawing or PDF for the motor exists anywhere in the repos. The only
PDF is `configs/source_snapshots/DJI_Action_2_User_Manual_V1.0_EN-11.pdf`. `docs/` holds CFD
diagnostics only. The single sourcing document is
`highspeed_edf/phase15/results/phase15_motor_and_rewind_v2.md:17-26`, a robu.in listing that gives
**"36×70 can", "5.0 mm shaft", ~270–276 g, 1550 KV** — and explicitly says *"robu does not publish
mass or wattage"*. The CAD's `2.5 mm` shaft radius matches the sourced 5.0 mm shaft; the **42 mm
diameter and 72 mm length appear in no source**. They look inflated from the "3670" designation
(36 mm stator × 70 mm stator) rather than measured.

Does the FAIL depend on that inflation? Partly. Substituting the sourced 36 × 70 can (R=18,
L=70) at the same 36 mm pitch gives
`π(18²)(34) + π(2.5²)(8) = 34,764.9 mm³` — still a hard interference, so **DM-G1 fails
qualitatively even with the sourced can**; only the magnitude (50,033 → ~34,765 mm³) rests on the
unsourced envelope. This sensitivity is analytic, not a re-measured model.

What settles it: (a) the robu.in/OEM drawing with can OD, can length and shaft length, or (b) a
caliper measurement of the purchased motor: OD across the can, can length excluding shaft, shaft
length and diameter. Until then the 42 × 72 envelope must be labelled an analyst allowance, and
`native_adapters.py:404` already half-admits this ("physical supplier data has not been
independently sourced").

## 7. Files produced

| file | content |
|---|---|
| `REPORT.md` | this report |
| `bench_before.py`, `bench_after.py` | stage timing drivers (baseline / accelerated) |
| `fast_adapters.py` | cached + parallel drop-in replacements |
| `ab_parallel.py`, `ab_parallel.json` | load-controlled serial-vs-parallel A/B |
| `verify_interference.py`, `interference_reverification.json` | 3-method re-derivation |
| `probe_import.py`, `probe_split.py`, `probe_ab_parallel.py` | import-cost and OCCT-parameter probes |
| `before_*.json`, `after_cold_*.json`, `after_warm_*.json`, `*_timings.json` | stage receipts + hashes |
| `cache/` | content-addressed STEP cache (86 import records + volume/centre records) |

## 8. UNVERIFIED / limits

- **Generation cost of the 231 MB STEP set is unmeasured** — the generator writes into the repo
  and must not be re-run under the read-only rule. Timing it needs a writable checkout.
- Last-instant measurement caveat: the cold column was taken while 11 sibling agents loaded the
  host; only the warm column and the interleaved A/B are load-controlled.
- CadQuery **2.7.0 / OCP 7.8.1.1.post1** were used here (same OCP the repo's own
  `phase15_native_motor_fit_review.md` reports), while `requirements-cad.txt` pins 2.5.2 / 7.7.2.
  The pinned pair was not installed to cross-check.
- Real interference can only be closed against the actual purchased motor (§6) or an
  as-built CAD model; everything above is geometry-file truth, not supplier truth.
- `BASE-004`'s `expected_file_count == 81` and the 3 invalid solids were found but not fixed
  (read-only rule); they need an owner in the repo.

## Reproduction

    python bench_before.py                       # ~6 min serial
    python bench_after.py cold                   # ~4 min, empty cache
    python bench_after.py warm                   # ~8 s, cache populated
    python ab_parallel.py                        # ~4 min, interleaved A/B
    python verify_interference.py                # ~4 min incl. 2 x 400k-point Monte-Carlo

Hash comparison: `python -c "import hashlib,pathlib;[print(s, hashlib.sha256(pathlib.Path(f'before_{s}.json').read_bytes()).hexdigest()==hashlib.sha256(pathlib.Path(f'after_warm_{s}.json').read_bytes()).hexdigest()) for s in ('step','motors','ducts','battery','connectors','mass')]"`