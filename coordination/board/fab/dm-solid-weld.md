# DM body weld — can the 4 disjoint solids become ONE manufacturable solid?

**Status: COMPLETE**

Assignment (one question): can the drone-mech body's 4 disjoint solids be welded into ONE valid
watertight solid suitable for manufacture, and if so execute the weld.

Input: `repos/drone-mech/highspeed_edf/deliverables/phase15_geometry/` (42_6 shell).
Provenance read: `evidence/fab-dm-final/`, `evidence/fab-dm-interference/`.
Work is on COPIES under `evidence/dm-solid-weld/`. Repo untouched.

## 1. ACTUAL topology  — MEASURED

File: `fuselage_battery_bay_shell_endpoint_relief_42_6.step` (7,313,057 B), copied to
`copy_body_42_6.step`. Probe: `step1_topology.py` (OCP STEPControl_Reader → raw topology, no
cadquery import cleaning). Full row data: `step1_topology.json`.

| property | measured |
|---|---|
| **member solids** | **4** |
| compound volume (BRepGProp) | **742,305.5264 mm³** |
| sum of the 4 solids | 742,302.3544 mm³ (Δ **3.172 mm³**, 4.3e-6 rel) |
| total bbox | x ±186.2125, y ±79.164, z −360.000 … +280.000 (**640.000 mm long**) |

| solid | vol mm³ | shells | inner shells | faces | edges | closed | free edges | non-manifold | watertight | BRepCheck | bbox x (optimal) | bbox y | bbox z |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---|---|---|---|---|
| 0 | 624,770.5299 | 1 | 0 | 138 | 810 | yes | 0 | 0 | **YES** | valid | −105.892 … 105.892 | −48.459 … 41.771 | −360.000 … **−189.0984** |
| 2 | 75,915.2316 | 1 | 0 | 94 | 550 | yes | 0 | 0 | **YES** | valid | −48.179 … 48.179 | −45.414 … 45.414 | **−111.933** … 280.000 |
| 1 | 20,808.2965 | 1 | 0 | 140 | 828 | yes | 0 | 0 | **YES** | valid | **56.281 … 95.282** | −40.791 … 40.791 | −107.4729 … 195.6651 |
| 3 | 20,808.2964 | 1 | 0 | 139 | 826 | yes | 0 | 0 | **YES** | valid | **−95.282 … −56.281** | −40.791 … 40.791 | −107.4729 … 195.6651 |

Every shell has **0 free edges and 0 non-manifold edges** — per-shell
`TopExp.MapShapesAndAncestors(shell, EDGE, FACE)` gives every edge exactly 2 faces.
So each of the 4 is individually a **valid, watertight solid** with **exactly one shell**, i.e.
**no internal voids at all** (0 inner shells, therefore 0 cavity volume anywhere).

### 1a. INSTRUMENT ERROR FOUND AND CORRECTED (this is why bboxes were retracted)

My first pass used `BRepBndLib.Add_s(shape, box, True)` and reported each solid as spanning the
full 640 mm. That is **wrong**, and the mechanism is measured: **`faces_with_triangulation = 0`
for all 4 solids** (this STEP carries no triangulation), so `Add(..., True)` has nothing to fall
back on but surface parametric ranges and returns grossly inflated boxes (S0 read x ±186.2125 vs
true ±105.8918). Same for `Add(..., False)`. The correct instrument is
**`BRepBndLib.AddOptimal_s(shape, box, False, False)`** (`step2c_optimal_bbox.py`), whose output
reproduces the prior wave's table **exactly** — x ±105.8918 / ±48.1787 / +56.2808…+95.282 /
−95.282…−56.2808 and every z span to 4 dp. A vertex-hull bbox agrees on z and is 1–14 mm tighter
in x (curved faces bulge past their vertices), consistent.

So `evidence/fab-dm-interference/REPORT.md:268-279` is **confirmed correct, not corrected**. The
independent value of this pass is the triangulation diagnosis: any future bbox on these files must
use `AddOptimal` or it silently over-reports by up to 76 %.
## 2. WHY four — ESTABLISHED (two independent lines of evidence)

### 2a. What the four pieces are, by measurement

`step3_weld_fast.py` stage `diag`. Wall-thickness proxy is `2V/A` (for a thin shell this is the
wall thickness; a filled body gives a large number).

| solid | vol mm³ | % of 742,306 | surface mm² | **2V/A mm** | shape |
|---:|---:|---:|---:|---:|---|
| 0 | 624,770.5299 | **84.17 %** | 110,192.05 | **11.34** | fore body, z −360.000 … −189.098 |
| 2 | 75,915.2316 | 10.23 % | 107,335.96 | **1.415** | centre body, x ±48.179, z −111.933 … 280.000 |
| 1 | 20,808.2965 | 2.80 % | 33,843.84 | **1.23** | right duct-side wall, x +56.281 … +95.282 |
| 3 | 20,808.2964 | 2.80 % | 33,843.84 | **1.23** | left duct-side wall, x −95.282 … −56.281 (mirror of 1) |

### 2b. They are mutually DISJOINT — proven, not sampled

**Every one of the 6 pairs has optimal bounding boxes that are disjoint on at least one axis**, and
a bbox is a superset of its shape, so the pairwise intersection is **empty by construction**:

| pair | separated on | gap mm |
|---|---|---|
| 0–2 | z | **77.165434** |
| 0–1 | z | **81.625489** |
| 0–3 | z | **81.625489** |
| 1–2 | x | **8.102085** |
| 2–3 | x | **8.102085** |
| 1–3 | x | 112.561602 |

Two real air gaps of **8.102 mm** (centre body ↔ each side wall) and **77.165 / 81.625 mm**
(fore body ↔ everything aft). These are structural-scale gaps, not tolerance slivers: no sewing
tolerance reaches them.

Cross-checks that agree: `BRepClass3d_SolidClassifier` puts **every solid's centre of mass OUTSIDE
every other solid** (4×4 matrix, all OUT, `step2_light.log`) → **no nesting**; one full
`BRepAlgoAPI_Common` measured directly (0–1) returned **0.000 mm³** with min distance
**85.389262 mm** (`step2_light.log`) — consistent with the 81.6 mm bbox gap. Overlap total is
therefore **0.000 mm³**, so the sum of the four volumes *is* the part volume.

### 2c. The mechanism: the duct bores sever a 1.2–1.4 mm shell

The repo's own build receipt for this exact file settles it —
`reports/fuselage_battery_bay_shell_endpoint_relief_42_6.json`:

| stage | volume mm³ | **solidCount** |
|---:|---:|---:|
| 1 | 5,979,465.23 | 1 |
| 2 | 4,001,690.52 | 1 |
| **3** | 865,419.18 | **4** |
| 4 | 842,737.92 | 4 |
| 5 | 820,056.67 | 4 |
| 6 | 742,305.53 | 4 |

The shell is **one solid until the two axial duct bores are cut**, and the cut is what turns 1 into
4. The receipt says so in words, and adds the part that matters most:

> `designCompromise`: *"Each axial bore is 0.2 mm larger in diameter than the source generator. This
> removes a thin amount of terminal shell material **to preserve four disconnected shell solids**
> and round-trip validity"*
> `comparison.smallerRadiusTest`: *"The 42.4 mm radius variant (0.2 mm diameter reduction) also
> round-tripped valid but **produced two solids**, so it does not preserve the four-piece result."*
> `visualEvidence.observations`: *"four components … **two duct-side shell walls, a lower shell
> section, and the separated upper shell section**"*

So the four-way split is **not an accident and not a failed boolean**: it is a **boolean-cut
consequence that the candidate radius was tuned to produce**. The 0.1 mm-per-side bore increase
(42.5 → 42.6) was chosen *in order to keep four solids*. My measured 8.102 mm and 77.165 mm gaps
are the openings that cut leaves.

Verdict on the four hypotheses offered:
* "shell plus three internal features modelled as separate bodies" — **no**: 0 inner shells, no
  nesting (§2b).
* "four duplicate/overlapping copies" — **no**: 0.000 mm³ overlap, distinct positions.
* "deliberate split into printable pieces" — **no**: no joint/lip/register features, and the pieces
  are separated by 8.1–77.2 mm of air; a printable split would share a face.
* **"a boolean that severed the shell"** — **yes**, and it was selected for (§2c).

## 3. Separate pieces vs cavities — SEPARATE PIECES (the wrong branch)

This is the **disjoint** case, not the internal-void case, and the two are cleanly distinguished by
measurement: each solid has **exactly 1 shell and 0 inner shells**, every centre of mass is outside
every other body, and the pairwise overlaps are zero. A shell-plus-void part would show **>1 shell
with opposite orientation inside one solid** and identical outer extent — neither is present. So
keeping "voids as internal cavities" is **not available here**: there are no voids to keep.

**Consequence: the weld is not available as a Boolean operation.** A union of pairwise-disjoint
bodies cannot reduce the connected-component count — the union of 4 disjoint sets has 4 components
by definition. Feeding 4 disjoint solids to `BRepAlgoAPI_Fuse` can only return a compound of 4. The
executed fuse confirms this (§4). Making one part requires **adding material across the 8.102 mm
and 77.165 mm gaps** — bridge geometry that does not exist in this file. That is a design change,
not a repair.
## 4. The weld — EXECUTED

`step3_weld_fast.py`, `BRepAlgoAPI_Fuse` sequential, wall clock 462.2 s:

| fuse step | result solids | result volume mm³ | valid | s |
|---|---:|---:|---|---:|
| S0 + S1 | **2** | 645,578.8261 | yes | 96.2 |
| + S2 | **3** | 721,497.4339 | yes | 263.2 |
| + S3 | **4** | 742,305.5264 | yes | 452.3 |

**The union is the identity operator here.** Component count went 4 → 2 → 3 → 4: each step added a
component and no step reduced the count, because adding a disjoint body to a compound always adds
one. Volume is the exact sum at every step (645,578.8261 = 624,770.5299 + 20,808.2965, to 3e-4).
**Overlap volume: 0.000 mm³** — the sum being unchanged is the direct evidence. This is the
predicted outcome of §3, not a surprise.

No fuzzy fuse was run, and the reason is arithmetic rather than time: the smallest genuine gap is
**8.259168 mm** (§5), so a sewing tolerance able to bridge it would be ~4.1 mm — larger than the
1.2–1.4 mm wall it is supposed to preserve. Artifacts: `weld_result.step` (7,027,277 B),
`weld_result.brep` (3,581,606 B).

## 5. VALIDITY CHECKS on the weld result — every check passes, and that is the problem

| check | instrument | result |
|---|---|---|
| solid count | `TopExp_Explorer(SOLID)` | **4** — unchanged |
| shell count | `TopExp_Explorer(SHELL)` | 4, one per solid |
| each shell closed | `BRep_Tool.IsClosed` | **True, True, True, True** |
| free edges (open boundary) | per-shell `MapShapesAndAncestors(EDGE→FACE)`, count ==1 | **0** of 3,014 edges |
| non-manifold edges (count >2) | same map | **0** |
| watertight | free==0 and nonmanifold==0 | **YES** |
| BRep valid | `BRepCheck_Analyzer(shape, True)` | **valid** |
| volume | `BRepGProp.VolumeProperties` | **742,305.5264 mm³** |
| volume vs repo `preExport` | 742,305.5263759661 | **match to 1e-7 relative** |
| volume vs naive per-solid sum | 742,302.3544 | Δ **3.172 mm³** (4.3e-6) — Gauss-integration difference on the compound, not geometry |
| surfaces | 285,215.69 mm² | = sum of the 4 solids' surfaces exactly |
| STEP round-trip of the result | re-import | **4 solids**, 742,305.5264 mm³, valid |

**Nothing fails — including the requirement it was supposed to fix.** The result is a perfectly
valid, fully watertight BRep that is still **four disconnected bodies**. So the answer is not "the
weld produced an invalid solid" and not "the weld succeeded": **the weld was executed and had no
effect, because there was no shared boundary to fuse.** One valid single solid **does not exist**
and cannot be produced from this file by any Boolean operation. Confirming this is the strongest
form of the check the assignment asked for.

## 6. Mass basis and the "84.2 % bulk fill" — a SEPARATE and worse concern

**The weld changes the mass basis by exactly nothing**, and the reason is a set-diff that only
appears when the mass rows are traced to their source file:

| | file | solids | volume mm³ | mass |
|---|---|---:|---:|---:|
| mass model bills | `fuselage_battery_bay_shell.step` | **2** | **253,001.328** | **392.152 g** (× 1550 kg/m³) |
| fab body exports | `..._endpoint_relief_42_6.step` | 4 | 742,305.5264 | — |

`reports/mass_cg.csv`, row `fuselage_battery_bay_shell`:
`"CAD volume 253001.3 mm^3 × 1550 kg/m^3"`, `volumeMm3 = 253001.32803006904`. I measured
`fuselage_battery_bay_shell.step` independently: **2 solids, 253,001.328 mm³, 392.152 g** — the
match is **digit-for-digit**, so the mass model was computed on a **different body** from the one
being certified. Ratio **742,305.5264 / 253,001.328 = 2.934×**. Nothing about the weld touches
this, and neither 392.152 g nor the 472.273 g programme figure is derived from 742,306 mm³.

**The 84.2 % is a real, independent thickness defect, not a mass-basis artefact.** It is solid 0:
624,770.5299 mm³ = 84.17 % of the part, with **2V/A = 11.34 mm** against **1.23 / 1.415 / 1.23 mm**
for the other three. That piece is **~9× thicker** than the shell it is supposed to be. For scale,
the whole export's 285,215.69 mm² of surface at the modelled 1.2 mm wall would be
`A·t/2 = 171,129 mm³` — the export is **4.34× that**. So two independent defects coexist and must
not be conflated:

1. **4 components, 0 weldable** — the fab blocker (§2–§5).
2. **742,306 mm³ of solid where ~171,000 mm³ of 1.2 mm shell belongs** — the thickness/bulk-fill
   defect, concentrated in the fore body. Welding would not have fixed this either.

## VERDICT

**No.** The four solids **cannot** be welded into one valid watertight solid, and the weld was
executed to prove it: **4 disjoint solids in, 4 disjoint solids out**, 742,305.5264 mm³ either way,
result valid and watertight, overlap 0.000 mm³.

* **Topology**: 4 valid solids, 1 shell each, 0 inner shells, all closed, 0 free / 0 non-manifold
  edges, 742,305.5264 mm³ total (repo's 742,306.360 mm³ confirmed to 0.83 mm³, 1.1e-6).
* **Why four**: the two Ø85.2 mm axial duct bores sever a 1.2–1.4 mm shell. The repo's own receipt
  shows solidCount 1 → 4 exactly at the bore-cut stage, and states the bore radius was enlarged
  **"to preserve four disconnected shell solids"**, with the 42.4 variant giving **two**. The split
  was tuned for, not suffered.
* **Not cavities**: no inner shells, no nesting (every CoM outside every other body), 0.000 mm³
  overlap. Separate pieces, held apart by **8.259 mm** (centre ↔ side walls) and **77.165 mm**
  (fore ↔ aft) of air.
* **What it needs**: added material to bridge those gaps, or keep the shell whole (receipt stage 2
  is 1 solid) and let the ducts be separate parts. Both are design changes, not repairs.
* **Mass**: unaffected — the 392.152 g row is the *other* file (253,001.328 mm³).

## Files

| file | what |
|---|---|
| `step1_topology.py` / `.json` | solids, shells per solid, closed/watertight, BRepCheck, volumes |
| `step2b_bbox_check.py` / `.json`, `step2c_optimal_bbox.py` / `.json` | the triangulation/bbox instrument error and its fix |
| `step2_light.log` | CoM-containment matrix (all OUT), pair 0–1 Common = 0.000 mm³, 85.389 mm |
| `step2d_fast.py` / `.json` | exact min distance for all 6 pairs + bbox disjointness proof |
| `step3_weld_fast.py` / `.json` / `.log` | the executed weld and the full validity table |
| `weld_result.step`, `weld_result.brep` | weld result (4 solids), round-trip verified |
| `probe_other_shell.py` | mass-basis file measured: 2 solids, 253,001.328 mm³ |
| `step2_why_four.py`, `step3_weld.py`, `step2_why_four.json`, `step3_stdout.txt` | **SUPERSEDED, 0-byte, ignore** — first attempts; `BRepAlgoAPI_Common` cost 454 s/pair and the first weld run crashed on a missing import before persisting |

Repo untouched: all work on `copy_body_42_6.step` / `.brep` / `copy_body_shell_plain.step`.

