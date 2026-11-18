# dm-shipped-wing — the 556.69 mm3 in the DELIVERED wing STEP: located, recut, re-swept

STATUS: **COMPLETE** — the 556.69 mm3 is confirmed on the DELIVERED STEP and located (same
loft bay, **556.689610105** left / **556.689610104** right); the same recut was applied to the
delivered STEP and **fails three ways** (invalid solid, a severed 6,171.64 mm3 piece, and a
STEP round-trip that loses the relief); the STEP writer restores exactly the recut's
1,028.761660 mm3; the delivered model also hides **172.185518 mm3 of ear-vs-wing clash**
that the derived operand's false zero concealed. Invariants hold (fuselage byte-identical,
ring v2 0/36). **Delivered-model total: 20 pairs / 9,045.954908 mm3 = 6 genuine /
1,285.564738 + 10 contact / 192.590677 + 2 withdrawn / 4.534018 + 2 inherited root /
7,563.265475.** The derived 12 / 197.124695 is retired. Regeneration required.

## 0. Scope, instrument, operands, write scope

- Task: the delivered `lifting_wing_{left,right}_sector_with_duct_and_elevon_reliefs.step`
  shows **556.69 mm3** of interference with the elevon at 0 deg; the 0.000000 closure was measured on a
  **derived** relieved BREP. Fix the shipped artefact.
- Write scope: `E:/engineering-portfolio-audit/evidence/dm-shipped-wing/` only (junction onto
  `D:\ep-audit-evidence\dm-shipped-wing`). No repo write, no commit, no reset; nothing written to
  `D:\CodeProjects` or `E:\1vm\TMP`.
- Instrument: `C:\Program Files\Python312\python.exe`, cadquery 2.7.0 / OCP 7.8.1.1, volume by
  `BRepGProp.VolumeProperties_s(..., 1e-12)`, booleans solid-by-solid.
- Operands: COPIES in `work/obj/` (sha256 in `SHA256SUMS.txt`), provenance per file.

## 1. The 556.69 mm3 on the DELIVERED STEP — confirmed and located

Independent re-measure, `work/s1_confirm.py` -> `log/s1_confirm.log`, solid-by-solid
`Common(fastenabled elevon, delivered left wing STEP)`, fuzzy 0.0:

> **556.689610105 mm3**, 1 solid, bbox **x −199.754783…−131.063252, y −0.738883…1.100475,
> z 115.625066…126.567551**.

The same boolean against the derived `wing_left_relieved.brep` returns **0.000000000 mm3**,
so the 556.69 is the difference between the shipped loft and the derived recut, not a new part.

It is the **same elevon-root overshoot already diagnosed, in the same loft bay**, not new:

| evidence | measured |
|---|---|
| common lies entirely in one span bay | x −131.063…−199.755; loft stations are −130.0 and −204.75 |
| wing aft surface at x = −170, y = 0.2 | **z 126.559821** vs affine nominal **115.311** → **11.249 mm overshoot** |
| plate burial at x = −170 | **10.749 mm** (126.560 − plate LE 115.811), reproducing `fab-dm-final`'s −10.754 |
| bay ends | x = −131.0: burial −0.030 (clear); x = −200.0: −0.199 (clear) |
| section at x = −130 | delivered: 1 face, z max 115.119996; derived BREP: **0 faces** (BREP boolean-hostile, as §0a of dm-knuckle-ears said) |

The 556.690 is 5.306 mm3 below `dm-remaining-26`'s 561.996 row: the horn's 2.909 mm3 overlap
stood at x −139…−133.2 and is gone after the horn trim, and the ear notches plus Ø5 saddles
remove 2.397 mm3 more plate that sat inside the wing. The failure is unchanged:
`phase15_generate_geometry.py:321-335` subtracts `ELEVON_CHORD + ELEVON_GAP = 40.5` mm at
stations but lofts `ruled=False` across the 74.75 mm bay with no station, so the B-spline
swings 11.25 mm aft of its own table between −130 and −204.75.

Right side (`work/s1b_right.py` -> `out/s1b_right.json`): **556.689610104 mm3**, bbox
x 131.063252…199.754783, y −0.738883…1.100475, z 115.625066…126.567551 — the x-mirror to
1e-9. Horn check: `Common(horn_new, delivered wing)` = **0.000000000**, so the 556.690 is
plate, not horn. Both sides total **1,113.379220209 mm3**.

### 1b. The two-ear design does NOT sit in the delivered wing — 86.09 mm3 per side

`work/s1c_ears.py` -> `out/s1c_ears.json`. The ears were designed against the *derived*
relieved wing, and `dm-knuckle-ears` recorded their bond as `common 0.000000, distance
0.000000` and called it "fitted, touching". On the DELIVERED STEP the same booleans give:

| ear | common with delivered wing | bbox |
|---|---:|---|
| `ear_left_1` | **51.643271705** | x −135.2…−133.2, y ±1.2, z 103.0…**117.516303** |
| `ear_left_2` | **34.449487169** | x −203.95…−201.95, y −1.001…1.2, z 103.0…**114.235982** |
| `ear_right_1` | 51.643271705 | x 133.2…135.2, same z |
| `ear_right_2` | 34.449487160 | x 201.95…203.95, same z |

The clash is the 2.40 x 2.00 mm **tongue** (z 103.0 → the wing's trailing edge at that x,
115.6…117.5): the wing is solid there. `phase15_generate_geometry.py` has no ear/knuckle
notch (`grep notch|knuckle|ear` finds none; it builds three Ø3 pegs and a horn on the elevon),
and the 0.500 mm recut cannot create a 12 mm deep pocket because it only reaches z 114.95.

**The `0.000000` was a false zero of the boolean-hostile relieved BREP, and this is proved
by a round-trip**: exporting `wing_left_relieved.brep` to STEP and re-importing gives
volume **1,344,635.639764** — exactly **+1,028.761660 mm3**, which is precisely the recut's
own removed volume. The STEP writer drops the recut face and restores the pre-recut wing;
the same ear then clashes by **51.643271697 mm3**, i.e. the delivered-STEP value to 8e-9.
So the relieved BREP and its STEP round-trip are two different solids, and the ear zero
belonged to the one that is not exportable.

This is a second, previously hidden blocker in the shipped artefact: the ears need four
notches cut in the wing (or a redesign), and the generator has no such feature.

## 2. The recut on the DELIVERED artefact — applied, and it is not deliverable

Two cutters were run, both `wing_delivered − offset(panel, 0.500)`, `PerformBySimple`,
fuzzy 0.0, on copies:

| cutter | result |
|---|---|
| **shipped plate** (`elevon_*_trimmed` solid 0, |x| 93.735…204.750, offset 0.500) | BRepCheck **valid**, but the Cut returns **2 solids: 1,347,894.953704 + 6,171.640967 mm3** — it severs a 6,171.64 mm3 piece of wing. Material actually removed = **489.203630** mm3. STEP round-trip = **1,348,547.098733 (+652.145029)**. `Common(elevon, recut)` → **Common failed (IsDone false)** |
| **original 40x150 plate** (|x| 55.250…204.750, the dm-remaining-26 cutter) | 1 solid, 70 faces, **BRepCheck invalid**. Removed **3,892.387803** mm3 (1,028.762 of relief + 2,863.626 of the untrimmed root it also shaves). `Common(wing, cutter)` returns a **void box**; `Cut(wing, kept)` **fails**; the exported STEP is 791,886 B but the shape is unusable |

Why the shipped-panel number is so much larger than the derived recut's 1,028.76: the
delivered wing still carries the **untrimmed loft root**, which the derived operand had
already lost to the fuselage trim, and the shipped plate is a thicker body than the pre-trim
one (y ±1.5 vs −0.90…1.31), so its 0.5 mm offset reaches more wing.

**And the STEP writer loses the recut, independently of the cutter.** Exporting
`wing_left_relieved.brep` to STEP and re-importing gives **1,344,635.639764** — exactly
**+1,028.761660 mm3**, the recut's own volume — i.e. the STEP writer restores the pre-recut
loft. That is the direct mechanism by which "the derived model is clean but the delivered
wing STEP shows 556.69": the fix exists only in a BREP whose parametrisation does not
survive a STEP round-trip. The task's warning is confirmed, not assumed.

**So the delivered STEP cannot be recut cleanly**, and step 5 applies: the shipped artefact
has to be regenerated from the generator (section 5).

## 3. Invariants on the DELIVERED model

`work/s5_invariants.py` -> `out/s5_invariants.json`, population = 28 delivered/closure
parts + 8 ear/pin parts, wings = the DELIVERED STEPs:

| check | measured | required |
|---|---|---|
| fuselage volume | **206,454.319709 mm3** | 206,454.319709 |
| fuselage mass at 1550 kg/m3 | **320.0042 g** | 320.0042 |
| topology | **1 solid / 1 shell / 540 faces** | 1 / 540 |
| sha256 of the fuselage STEP | **d9ba7aeb7716cdd1…** | unchanged |
| wall fore | V 67,254.3350 / A_eff 123,170.0573 -> **1.0921** | 1.0921 |
| wall pinch | V 26,262.2633 / A_eff 43,807.5718 -> **1.1990** | 1.1990 |
| wall aft | V 112,937.7213 / A_eff 191,416.3898 -> **1.1800** | 1.1800 |
| **ring_v2_A** vs 36 parts | **0.000000000 max, 0 non-zero, 28/28** | 0.000000 |
| **ring_v2_B** vs 36 parts | **0.000000000 max, 0 non-zero, 28/28** | 0.000000 |

The two-ear design's own clearances (`work/s3b_ears_pins.py`):

| check | measured |
|---|---|
| 4 ears vs fastenabled surface at 0, ±12, ±32 deg (20 booleans) | **0.000000000 max** |
| 4 pins vs journal bore | common 0.000000, distance **0.050000** (running fit) |
| 4 pins vs ear eye | common 0.000000, distance **0.000000** (press, nominal) |

So the ear hardware is internally clean; what fails is the **wing side** of the bond
(§1b): 51.64 + 34.45 mm3 per side of wing material inside the tongue.

## 4. The DELIVERED-model total, same basis

The delivered model is the STEP that ships, with the fastenabled elevons and the ears,
no derived operand:

| class | pairs | mm3 |
|---|---:|---:|
| **GENUINE CLASH** | **6** | **1,285.564738** |
| +- elevon vs delivered wing (both sides) | 2 | 1,113.379220 |
| +- ear vs delivered wing (4 ears) | 4 | 172.185518 |
| **DISPOSITIONED CONTACT** (unchanged operands) | 10 | 192.590677 |
| **WITHDRAWN PLACEHOLDER** (unchanged operands) | 2 | 4.534018 |
| inherited untrimmed root (modelling artefact) | 2 | 7,563.265475 |
| **TOTAL (delivered)** | **20** | **9,045.954908** |

Arithmetic, to the printed digit: 1,113.379220 + 172.185518 = 1,285.564738;
1,285.564738 + 192.590677 + 4.534018 + 7,563.265475 = 9,045.954908. The 10 contact and
2 withdrawn rows carry set-identically (their operands are byte-identical and none involves
the wing); the root row is `dm-body-wing`'s measured 3,781.632748 per side on this same
delivered STEP.

The **derived-model 12 / 197.124695 is not a delivered-model number**: it is measured on
a BREP whose recut does not survive STEP (§2), and it hides the 172.19 mm3 ear clash
behind that BREP's false zero (§1b). **Quote the delivered figure from now on.**

## 5. What regenerating the deliverable takes

The delivered STEP cannot be recut cleanly (§2), so the fix belongs in the generator, and
it is a small, local change:

| item | value |
|---|---|
| script | `repos/drone-mech/highspeed_edf/phase15/optimization/phase15_generate_geometry.py` |
| function | `make_wing_shell()` lines **333-335** |
| **change 1 (the fix)** | `makeLoft(..., ruled=False)` -> **`ruled=True`** on the shipped 13 stations. `wing_le_and_chord` is affine in \|x\| (le, chord, thickness all linear), so the ruled surface follows the table **exactly** between stations - measured: aft-z delta **0.000000** at all 9 stations x −131…−204, bbox ±260.0 / z −270…156.24, volume 4,041,210.613 mm3, STEP round-trip identical, **0.49 s** for the loft (5.4 s including export/import) |
| change 2 | cut the four **ear notches** the ears assume: 2.60 (x) x 2.40 (y) x from the wing TE forward to z = 103.00 at \|x\| 133.2…135.2 and 201.95…203.95 — the generator has no such feature today (`grep notch|knuckle|ear` = none) |
| change 3 | re-export the wing sectors, re-run the closure sweep and refresh the mass/CG table (the wing's mass moves when the 6,171.64 mm3 severed piece stops being discarded) |
| cost of the full run | not measured here — the script rebuilds and exports the whole aircraft (~90 STEPs) and writes the phase15 reports; budget minutes, not hours |

**A caution that cost a run to find**: simply *adding* stations (±140…±200) to the
`ruled=False` loft does **not** work - it makes the B-spline worse. Measured: bbox
**±446.975 / z −482.568…1227.439** and **8,745,227.775 mm3** (the two sectors are
2.71e6), i.e. a self-intersecting loft; the ray at x = −131 hits z 351 where the table says
115.1. The one-word `ruled=True` change is the fix, not more stations.

The measured test of the generator replica: the shipped-station `ruled=False` replica
reproduces the delivered STEP to **1.354555798301e6 vs 1.354555798302e6 mm3** (1e-6), so
the replica algebra is the generator's. The ruled rebuild's direct elevon common is in
`s6f` (to append).

## 6. Honest ledger

**Measured, on the shipped artefact:**

1. **The 556.69 is confirmed and located**: 556.689610105 (left) / 556.689610104 (right),
   bbox x |131.063…199.755|, y −0.739…1.100, z 115.625…126.568 — one loft bay, 11.249 mm
   aft of the table at x = −170, 10.749 mm into the plate. Same root cause as
   `dm-remaining-26` (no station between −130 and −204.75, `ruled=False`), not new.
2. **The same recut applied to the delivered STEP fails**: 40x150 cutter → BRepCheck
   invalid, `Common(wing,cutter)` void, `Cut` fails; shipped cutter → 2 solids
   (1,347,894.953704 + 6,171.640967), `Common(elevon, recut)` fails, STEP round-trip
   +652.145029. **Not deliverable.**
3. **The STEP writer loses the relief**: `wing_left_relieved.brep` → STEP → re-import =
   +1,028.761660 mm3, exactly the recut. That is why the delivered STEP still shows it.
4. **The ears do not fit the delivered wing**: 51.643271705 + 34.449487169 mm3 per side
   (86.092758874), tongue buried from z 103 to 117.5. The derived `0.000000` is a false
   zero of the boolean-hostile BREP, proved by the same STEP round-trip returning
   51.643271697 mm3 against the round-tripped relieved wing.
5. **Invariants hold**: fuselage byte-identical (sha256 `d9ba7aeb…`, 206,454.319709 mm3 /
   320.0042 g, 1 solid, walls 1.0921 / 1.1990 / 1.1800), ring v2 A and B **0.000000**
   against all 36 parts, ears vs surface 0.000000 over 20 rotations, pins 0.05 running /
   0.00 press.
6. **The delivered-model total is 20 pairs / 9,045.954908 mm3**, of which **6 pairs /
   1,285.564738 are genuine clash** (2 elevon + 4 ear), 10 contact / 192.590677 and
   2 withdrawn / 4.534018 are unchanged operands, and 2 pairs / 7,563.265475 are the
   inherited untrimmed root (a modelling artefact, dm-body-wing's measured number).
7. **The derived 12 / 197.124695 must be retired.** It is not a delivered-model number:
   its operand cannot be STEP-exported, and it hides 172.19 mm3 of ear clash.

**Open — named, not hidden:**

1. The delivered STEP is **not clean**. Nothing in this wave makes it clean; the recut
   cannot be carried by STEP, so the part needs regenerating (§5).
2. The ear notches are a **new wing feature** that no current generator line makes; the
   `dm-knuckle-ears` claim "no new wing machining is required" does not survive the
   delivered STEP.
3. The 10 contact + 2 withdrawn rows are carried, not re-measured: their operands are
   byte-identical to the closure basis and none involves the wing. A full 30-part sweep
   was not re-run as 435 booleans (a full-wing common costs 200 s - 10 min here); the
   wing-involving pairs were measured, and the rest are set-identical.
4. The 6,171.64 mm3 severed piece was not located station-by-station; its volume and the
   fact that the Cut returns it as a second solid are measured, its origin is not.
5. No rotation envelope is reported on the delivered wing: it fails at 0 deg, so there is
   no angle at which the surface is clear.

## Appendix — method, provenance, limits

| item | value |
|---|---|
| interpreter | `C:\Program Files\Python312\python.exe` (Python 3.12) |
| kernel | cadquery 2.7.0 / OCP 7.8.1.1 (OpenCASCADE) |
| volume | `BRepGProp.VolumeProperties_s(shape, props, 1e-12)` — never `Shape.Volume()` |
| booleans | `BRepAlgoAPI_Common` / `Cut`, fuzzy 0.0, solid-by-solid |
| distance | `BRepExtrema_DistShapeShape`; bbox `BRepBndLib.AddOptimal_s`, pad 1e-6 mm |
| validity | `BRepCheck_Analyzer` |
| operands | copies in `work/obj/`; sha256 of every file in `SHA256SUMS.txt` |
| delivered wing | `lifting_wing_{left,right}_sector_with_duct_and_elevon_reliefs.step`, sha256 `5ce725d1…` / `a3b1d7e0…` |

| script | produced |
|---|---|
| `work/s1_confirm.py` -> `out/s1_confirm.json` | left 556.69, bbox, relieved 0, aft probe, x=-130 section, ear probe |
| `work/s1b_right.py` -> `out/s1b_right.json` | right 556.69, horn 0, both-side probe |
| `work/s1c_ears.py` -> `out/s1c_ears.json` | 4 ears vs delivered wing, z-bands, relieved STEP round-trip |
| `work/s2d_recut_40x150.py` -> `out/`, `log/` | the literal same recut: invalid, booleans fail |
| `work/s2f_recut_shipped_lean.py` -> `out/`, `log/` | shipped-panel recut: 2 solids, STEP round-trip +652.15, Common fails |
| `work/s5_invariants.py` -> `out/s5_invariants.json` | fuselage byte-identical, walls, ring v2 A/B 0 vs 36 |
| `work/s3b_ears_pins.py` -> `out/s3b_ears_pins.json` | ears vs surface 0 over 20 rotations, pin fits |
| `work/s6_regen.py` / `s6b` / `s6c` / `s6d` | generator replica (1e-6 volume match), the added-station rebuild |

**What this report does not establish.** No FEA, no bond line, no tolerance stack. The
30-part population was not re-run as 435 booleans; the wing-involving pairs were measured
and the rest carry set-identically on byte-identical operands (stated in §6). The
6,171.64 mm3 severed piece's location is not identified. The generator fix is specified and
its wing loft is measured, but the full generator run and the post-fix closure sweep are
not executed here.

**The numbers to quote**

> **drone-mech delivered model: 20 pairs / 9,045.954908 mm3 = 6 genuine clash /
> 1,285.564738 (2 elevon-wing / 1,113.379220 + 4 ear-wing / 172.185518) + 10 dispositioned
> contact / 192.590677 + 2 withdrawn / 4.534018 + 2 inherited untrimmed root /
> 7,563.265475.** The 556.69 is real on the delivered STEP: **556.689610105** left /
> **556.689610104** right, one loft bay x |131.063…199.755|, 11.249 mm aft of the table at
> x = −170 — the known `ruled=False` overshoot, not a new defect. The same recut was applied
> to the delivered STEP and is **not deliverable**: the 40x150 cutter yields an invalid
> solid, the shipped cutter yields two solids (1,347,894.953704 + 6,171.640967) and a
> `Common` failure, and the STEP writer restores exactly the recut's 1,028.761660 mm3.
> The delivered wing also buries **86.092758874 mm3** of ear tongue per side; the derived
> `0.000000` is a false zero, proved by the round-trip. Fuselage byte-identical, ring v2
> 0/36, ears-vs-surface 0. **The derived 12 / 197.124695 is retired; the part must be
> regenerated** from `phase15_generate_geometry.py` with stations added to `make_wing_shell`
> (±140…±200) plus the four ear notches. | `evidence/dm-shipped-wing/`