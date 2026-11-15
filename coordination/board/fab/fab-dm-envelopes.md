# FAB-DM-ENVELOPES — the deletion executed, and what it actually proves

**Scope:** drone-mech airframe (`repos/drone-mech/highspeed_edf/deliverables/phase15_geometry`),
branch `work/2026-11-11`, **read-only**. No file under `repos/` was written; no git operation was
performed. Every artefact is in `evidence/fab-dm-envelopes/`.

**Provenance labels.** Every volume here is a **native CAD boolean** (OpenCascade
`BRepAlgoAPI` through CadQuery 2.7.0 / OCP 7.8.1.1 on `C:/Program Files/Python312/python.exe`),
or **closed form** where explicitly marked. No solver, no surrogate, no invented supplier number.
The one supplier input is **LISTING/SPEC tier** (§3), not a drawing.

Built on the verified state; nothing below re-derives it. The baseline reproduces
**22 pairs / 331,033.5633 mm³** to the last digit (`run_fab_dm_envelopes.log:6`).

---

## Verdict

**Delete R1 and R2, keep R3, on each duct — and resize the envelope to Ø36 × 70 + Ø5 × 17.**
The station choice is measured, not arbitrary: keeping R1 leaves **8** pairs, R2 **6**, R3 **2**
(§1). Deletion alone with the as-built Ø42 envelope **does not reach zero** — it reaches
**2 pairs / 1,248.5946 mm³**, so the board's "delete 4 → 0 pairs" needs one qualifier (§7.1).
Deletion **plus** the resize reaches **0 pairs / 0.0000 mm³** against all 23 neighbours of the
module sweep and, separately, against the 24th part (the motor carrier frames, §6a).

The resize alone does **not** clear the airframe (22 → 12 pairs) but it clears **exactly one
pair class, all 10 stator-carrier pairs, 6,242.9729 mm³** (§5).

And there is a **new pair class nobody's sweep contained**: the elevon roots. Two pairs,
**1,186.1381 mm³** as built, **819.6661 mm³** corrected, survive every version of the fix (§6).

| | module set (24 parts) | + 2 elevons | whole airframe |
|---|---|---|---|
| **BEFORE**, six as-built Ø42×72 | 22 pairs / 331,033.5633 | 4 pairs / 1,640.5185 | **26 / 332,674.0818** |
| delete 4, keep R3, as-built in place | 2 / 1,248.5946 | 2 / 1,186.1381 | **4 / 2,434.7327** |
| delete 4, keep R3, as-built at z 106 | 0 / 0.0000 | 2 / 1,186.1381 | **2 / 1,186.1381** |
| resize only, all six kept | 12 / 232,157.2333 | 4 / 1,067.6665 | **16 / 233,224.8998** |
| **delete 4 + resize, R3 in place** | **0 / 0.0000** | 2 / 819.6661 | **2 / 819.6661** |
| delete 4 + resize, R3 + 1.000 mm | 0 / 0.0000 | 2 / 819.6661 | **2 / 819.6661** |

---

## 1. Which four to delete, and which two to keep — measured, not chosen

### 1a. The six envelopes are at three different stations, one per duct each

Measured from the STEP solids themselves (`fab_dm_envelopes.json → envelope_geometry`):

| envelope | bbox z (mm) | Ø | can start (z min + 8) | radius faces | volume |
|---|---|---|---:|---|---:|
| `motor_A_R1` / `motor_B_R1` | 12.000 … 92.000 | 42.000 | **20.000** | 21.0, 2.5 | **99,908.930** |
| `motor_A_R2` / `motor_B_R2` | 48.000 … 128.000 | 42.000 | **56.000** | 21.0, 2.5 | 99,908.930 |
| `motor_A_R3` / `motor_B_R3` | 84.000 … 164.000 | 42.000 | **92.000** | 21.0, 2.5 | 99,908.930 |

Axes: duct A at x **−44.000**, duct B at x **+44.000**, both y 0.000 (measured; the A/B pair is
numerically identical in every row below, so the duct choice is symmetric and the **row** choice
is the only one that matters). Axial pitch **36.000 mm**, both gaps, both ducts.

### 1b. The envelopes stand exactly on their own hub's aft face

| part | z window (mm) | radii (mm) |
|---|---|---|
| `duct_*_rotor_R1` | **4.000 … 20.000** | 20.000 (hub OD), 2.525 (bore) |
| `duct_*_rotor_R2` | **40.000 … 56.000** | 20.000, 2.525 |
| `duct_*_rotor_R3` | **76.000 … 92.000** | 20.000, 2.525 |
| `duct_*_stator_S1` | **26.000 … 34.000** | 20.400 (carrier bore), 21.100 (OD), 38.3, 39.0 |
| `duct_*_stator_S2` | **62.000 … 70.000** | same |
| `duct_*_stator_S3` | **98.000 … 106.000** | same |

So can start 20.000 = hub R1's aft face, 56.000 = hub R2's, 92.000 = hub R3's. **Each envelope
occupies the 72 mm immediately AFT of its own hub.** That is what makes the choice non-arbitrary:
a can kept at a forward station necessarily sits over every stage behind it.

### 1c. The trial, run for real

Same as-built envelope, same in-place station, only the kept row changes
(`fab_dm_envelopes.json → results.KEEP_R*_asbuilt_in_place`):

| kept | pairs | mm³ | what it still swallows |
|---|---:|---:|---|
| **R1** | **8** | 85,448.6614 | hubs R2 + R3, carriers S1 + S2 (per duct) |
| **R2** | **6** | 43,890.1297 | hub R3, carriers S2 + S3 (per duct) |
| **R3** | **2** | 1,248.5946 | carrier S3 only — the 0.6 mm radial band |

**R3 is the only station with nothing behind it.** Its 2 surviving pairs are not an axial problem
at all: can radius 21.000 against carrier bore 20.400, over the 8 mm chord, = π(21² − 20.4²)·8 =
**624.297292 mm³** each, twice = 1,248.5946 — which is exactly what was measured.

**Why R1 vs R2 vs R3 does not depend on the motor.** All six rows carry the same selected motor
(`design/PHASE15_DESIGN_SPEC.md:302`, one motor type, six units, six rewound); the rows differ by
rotor blade count (13 / 12 / 11) and by station only. There is no motor-side preference, so the
decision is **purely geometric** — and the geometry is one-directional: keep the aft-most.

**A fact that makes the choice expensive, stated rather than hidden.** R3 is also the station whose
can reaches into the nozzle (can z 92.000 … 164.000 vs nozzle 110.000 … 245.000, bore r 39.000):
the corrected can blocks **21.302 %** of the throat (1,017.876 of 4,778.362 mm²), the as-built can
**28.994 %** (`fab_dm_envelopes.json → throat`). Keeping R1 would block **0 %** — R1's can ends at
z 92, inside the duct — but R1 fails with 8 pairs. R1 becomes available only if rotor stages R2 and
R3 are also deleted, i.e. a 3-stage-to-1-stage change per duct. That is an architecture decision,
not an envelope edit, and it is **not** recommended here.

**Kept / deleted, therefore:**
- **keep** `motor_A_R3` (duct A, x −44.000) and `motor_B_R3` (duct B, x +44.000);
- **delete** `motor_A_R1`, `motor_A_R2`, `motor_B_R1`, `motor_B_R2`.

---

## 2. The deletion executed, on a copy

### 2a. The assembly carries exactly six instances — verified by census, not by assertion

`step_product_census.json`: `phase15_airframe_full_assembly.step` (63.7 MB) carries **72 PRODUCT
instances, of which exactly 6 are** `motor_A_R1…R3_3670_42x72_envelope` and
`motor_B_R1…R3_3670_42x72_envelope`. The twin-ducts STEP (`phase15_twin_ducts_and_fans.step`)
carries **none** — the motors are not in that file at all.

The 63.7 MB assembly was **not kernel-imported**. Reason, measured not assumed: the earlier wave
stopped a 22-part boolean against the 7 MB shell as uneconomical (>13 min, no result), and the
whole point of this wave is the pair list, not a re-parse. The deletion was therefore executed on a
**copy of the motor sub-assembly** — the six instances imported from the assembly's own part files
— which is the only thing the deletion touches. That scoping is the one limitation of §2 and it is
carried into §8.

### 2b. Copy → delete 4 → export → re-import (all measured)

```
copy of assembly   : 6 envelopes, 6 solids, 599,453.577 mm3
deleted            : motor_A_R1, motor_A_R2, motor_B_R1, motor_B_R2   (4)
kept               : motor_A_R3, motor_B_R3                          (2)
artefact           : da_motors_4of6_deleted.step  20,849 B
sha256             : A2F196251D31708E02126CCA35E6E7169157133831B3325921AF355E2B10D363
re-imported        : 2 solids, 199,817.859 mm3, z 84.000 … 164.000
volume vs source   : delta 0.000 mm3   (i.e. 2 x 99,908.930, nothing lost or fused)
```

`fab_dm_envelopes.json → deletion`; console `run_fab_dm_envelopes.log:16`.

### 2c. The sweep, before and after

Full pair list per case = **envelope-vs-envelope AND envelope-vs-every-neighbour** (23 parts: 6
rotors, 6 stators, 10 duct/nozzle/collar/ring/inlet, the 42_6 fuselage). 153 assertions per case
(15 + 6 × 23). The 24th part, the carrier frames, is a separate test in §6a and also returns 0.

```
BEFORE as-built Ø42x72, six envelopes, own stations   FAIL 22 pairs  331,033.5633 mm3
AFTER  delete 4, keep R3, as-built, in place          FAIL  2 pairs    1,248.5946 mm3
AFTER  delete 4, keep R3, as-built, re-stationed 106  PASS  0 pairs      0.0000 mm3
AFTER  delete 4, keep R3, corrected Ø36x70 at z 92    PASS  0 pairs      0.0000 mm3
AFTER  delete 4, keep R3, corrected Ø36x70 at z 93    PASS  0 pairs      0.0000 mm3
```

**On the pair census.** The brief says "54-pair sweep"; the sweep that produced the 22 is
**51 motor pairs — 15 motor-motor + 18 motor-rotor + 18 motor-stator** — and its own parenthetical
sums to 51, not 54 (`evidence/fab-dm-interference/REPORT.md:41`). No number changes, only the
label (§7.2). I also ran the **unrestricted 87-pair** form (each envelope against all six rotors
and all six stators, not just its own duct) and the cross-duct count is **0 in every case**
(`fab_dm_envelopes.json → results.*.cross_duct_pairs_that_the_own_duct_filter_would_have_hidden`),
so the duct filter hides nothing.

### 2d. The detector is not blind — four controls, both directions

| control | expected | measured | verdict |
|---|---|---:|---|
| corrected envelope driven 2 mm INTO its own hub, vs `duct_A_rotor_R3` | non-zero | **1,995.692806** | sees a new-size clash |
| as-built can start **105.0** vs `duct_A_stator_S3` | non-zero | **78.037162** | resolves 1 mm |
| as-built can start **106.0** vs same | zero | **0.000000** | and 106 is where it stops |
| corrected envelope at R3 vs `duct_A_stator_S3` | zero | **0.000000** | r18 clears the r20.4 bore |

`fab_dm_envelopes.json → negative_controls`; `run_fab_dm_envelopes.log:15`.

---

## 3. The corrected envelope: where 36 and 70 come from, and what tier they are

**Envelope of record:** Ø **36.000** × **70.000** mm can, Ø **5.000** mm shaft extending **17.000**
mm forward. Modelled volume π·18²·70 + π·2.5²·17 = **71,585.116 mm³**; the written artefact
re-imports at 143,170.231 mm³ for two = 71,585.1155 each, **exact**
(`fab_dm_envelopes.json → deletion.corrected_reimported`).

### 3a. Where the numbers come from

| figure | source | tier |
|---|---|---|
| **36 × 70 can** | `design/PHASE15_DESIGN_SPEC.md:302` — "SELECTED MOTOR … 2 pole pairs, **36×70 can**, ~270–276 g" | in-repo design record |
| **36 × 70 can** | three retail listings, quoted verbatim in the prior wave: "Motor Size: **ø36x70mm**; Shaft Diameter: **ø5mm**; Length of Extend Shaft: **17mm**; Mounting Screw: ø25mm M3*6, 4 Poles 12-Slot" (Amazon B0GL2258WS); "a **diameter of 36 millimetres and a length of 70 millimetres**" (digitec, Surpass Rocket V2 3670); "3670 … Brushless **Inrunner** … **5mm Shaft**" (Ingenium Drives) | **LISTING** |
| **inrunner, not outrunner** | same listings ("CNC Machined 6061 T6 Billet Aluminum Heatsink Can"); the live Ingenium page title fetched today reads "Surpass Hobby Rocket 3670 1200KV Brushless **Inrunner** Motor \| 4 Pole \| 1500W \| **5mm Shaft**" | LISTING, re-confirmed live today |
| why 42 × 72 exists | `phase15/optimization/phase15_generate_geometry.py:104-105` — `MOTOR_CAN_D = 42.0`, `MOTOR_CAN_LENGTH = 72.0` | in-repo constant |

**The repo records no dimensional field for any motor at all.** `phase15/configs/phase15_sourcing.json`
carries `id, name, supplier, url, priceInr, inStock, massKg, kv, polePairs, maxPowerW, maxCells,
ratingType, verdict` and **no** diameter, length or size key (`sourcing_check.json →
sourcing_has_can_dimension_fields` is `[]`). So the 36 and the 70 exist as **prose in the spec** and
as **retail listing text**, and nowhere as a recorded, structured, verifiable dimension.

### 3b. The honest tier statement

**SOURCED — LISTING/SPEC tier. NOT assumed, and NOT drawing-tier.** The 36 and 70 are not
invented; they are the spec's own selected motor and three independent retail descriptions of it.
They are also *not* verified against a manufacturer drawing or a physical part, and today I could
re-confirm only the **model designation, "inrunner" and "5 mm shaft"** on a live page — both live
fetches truncated before the dimension table, and the digitec page failed outright. The prior
wave's quotes are therefore the **source of record, re-cited, not re-read**.

**The doubt does not move the verdict, and here is the measured reason.** The stator class clears
for any can radius ≤ 20.400 mm, i.e. any Ø ≤ **40.800** — and the axial class is a *length*
consequence that no diameter up to 40.8 changes. So a listing error of ±2 mm on the diameter
changes the numbers in §5 slightly and changes **none** of the §6 conclusions. A listing error on
the **70 mm length** would (the axial class is πr²·(L − 36)), but no cited source disagrees on 70.

### 3c. A like-for-like volume, because the board's 40.2 % compares two different populations

Board and prior report: as built **99,908.93 mm³** vs should be **71,251.29 mm³** = **40.2 %** too
large. But 71,251.29 is the **can only** (π·18²·70 = 71,251.32); the as-built 99,908.93 is **can
plus its 8 mm stub**. Charged the same way — can + shaft on both sides — it is **99,908.930 /
71,585.116 = 1.3957**, i.e. **39.57 %** too large, not 40.22 %. Same defect, correct population.
Filed as §7.5; nothing else in either number changes.

---

## 4. The corrected size in place of the oversized one — measured

Two different questions, and they answer differently.

### 4a. Resize **only**, all six stations kept (`SIZE6`)

```
FAIL 12 pairs / 232,157.2333 mm3   (was 22 pairs / 331,033.5633)
```

| class | before | after resize | change |
|---|---:|---:|---|
| envelope vs envelope | 6 pairs / 200,446.1777 | 6 pairs / 140,355.3642 | −60,090.81 |
| envelope vs rotor hub | 6 pairs / 124,344.4127 | 6 pairs / 91,801.8691 | **−32,542.54 (−26.2 %)** |
| **envelope vs stator carrier** | 10 pairs / 6,242.9729 | **0 pairs / 0.0000** | **−6,242.97, all cleared** |
| **total** | **22 / 331,033.5633** | **12 / 232,157.2333** | **−98,876.33 (−29.87 %)** |

**Quantified answer to "does correcting the size alone already clear some pairs":** yes — **all 10
stator-carrier pairs, 6,242.9729 mm³, gone entirely**, because 18.000 < 20.400. It clears nothing
else: the axial class survives because 70 mm of can on a 36 mm pitch still overlaps 34 mm, and the
hub class survives because 18.000 < 20.000, so the can is still inside the hub annulus.

### 4b. Why the prior closed form for the axial class was ~1 % low

Measured per-pair, corrected envelope at the as-built stations: R1–R2 = R2–R3 = **34,941.578891**,
R1–R3 = **294.524311**, per duct. Closed form: π·18²·34 = **34,607.784672** *plus* the 17 mm shaft
of the forward can's successor lying inside it (π·2.5²·17 = 333.794219) = 34,941.578891, exact. The
prior wave used π·18²·34 = 34,764.86 — an arithmetic slip, correct value 34,607.78 — and quoted
"2 pairs / 589.05" for the shaft class where there are **four** shaft pairs (2 × 294.52 + 2 ×
333.79). Its ≈231,450 mm³ is 232,157.2333 here. Filed as §7.4.

### 4c. Resize **and** delete four (`SIZE2` / `SIZE2a`)

```
delete 4, corrected Ø36x70, R3 in place (can z 92…162)   PASS 0 pairs / 0.0000 mm3
delete 4, corrected Ø36x70, R3 + 1.000 mm (z 93…163)    PASS 0 pairs / 0.0000 mm3
```

Clearances of the surviving layout, measured: hub R3 aft face at z 92.000, can front face at
92.000 → **0.000 mm** stand-off in place, **1.000 mm** at the +1 variant; can radius 18.000 vs
carrier bore 20.400 → **2.400 mm radial clearance**; shaft 17.000 mm reaches z 75.000, inside its
own hub bore (76.000…92.000 at r 2.525) with 0.025 mm radial clearance and **0.000 mm³** measured.

**Prefer the +1.000 mm variant.** It costs nothing, keeps the can off a face-to-face contact with
the hub's aft face, and is collision-free by the same measurement. 70 mm can + 17 mm shaft = 87 mm
needs a pitch ≥ 87 mm; the +1 mm does not pretend otherwise — it buys clearance in a layout that
already has only one motor.

---

## 5. Recommendation

**Do both, in this order: (1) delete the four, (2) resize the envelope to Ø36 × 70 + Ø5 × 17.**

1. **The deletion is the one that removes 99.6 % of the interference.** 331,033.5633 → 1,248.5946
   mm³ (as-built size, in place). Nothing else comes close: the resize removes 29.87 %.
2. **The deletion is not sufficient on its own.** It leaves 2 pairs / 1,248.5946 mm³ at the S3
   carrier, and the only two ways out are the resize (§4c) or re-stationing the survivor to z 106 —
   and the re-station costs **28.994 %** of the throat versus **21.302 %** for the resized can.
3. **The resize is not a nicety, it is a correctness fix.** The 42 × 72 envelope models a motor
   that does not exist (an outrunner-bell rule applied to an inrunner). Every downstream number
   that consumes the envelope — mass, CG, nozzle blockage, this whole interference class — is
   wrong while it stands. Fixing it is two constants in
   `phase15_generate_geometry.py:104-105` plus the stub, not design rework.
4. **Neither is design rework, both are cheap, and both are load-bearing.** Four part instances
   removed, two constants changed. The 1.096 kg saved is 4 × 0.274 kg (spec 270–276 g, LISTING
   tier) — a design-intent mass, not a weighed one.
5. **Do not take the "keep as-built at z 106" path.** It is interference-clean and it keeps a
   motor that is not the selected motor, blocks the most throat, and inherits a radius that puts
   the can inside its own hub annulus. It is the cheap-looking option the owner principle says is
   the expensive one.

**Still open after this, and it needs its own decision, not another envelope edit:**
**21.302 % of the nozzle throat is blocked by the surviving can** (52 mm of can inside the nozzle
at z 92, 53 mm at the +1 mm variant). Interference-clean is not flow-clean. That is the single
largest remaining cost of the fix.

---

## 6. What the sweep was missing, and what it costs

The 22-pair bookkeeping tested 23 parts that share the duct module's axial window. A whole-airframe
bounding-box screen over the repo's own per-solid export
(`docs/diagnostics-2026-11-10/airframe_gmsh_per_solid_stl_bounds.json`, 73 named parts / 516
solids) finds **two parts in the envelopes' window that no sweep had ever put against a motor**:
`six_hot_side_motor_carrier_frames` and the **two elevons**.

### 6a. Carrier frames — clean, and now tested

30 solids, bbox z 10.000 … 86.000, x ±83.000. Against six as-built, six corrected, R3-only as-built,
R3-only corrected and the z-106 layout: **0 pairs / 0.0000 mm³ in all five cases**
(`fab_dm_carriers.json → carrier_part.cases`). No cost, one closed gap.

### 6b. The elevons — a real pair, present before the fix and after it

`elevon_left_40x150` reaches x **−55.250**, i.e. **11.25 mm** from duct A's axis; `elevon_right`
mirrors it at **+55.250** for duct B. Both are 3.5 mm thick plates at y ≈ 0 crossing z 115.263 …
155.976 — straight through a motor can that occupies that radius.

| | as-built Ø42 | corrected Ø36 |
|---|---:|---:|
| left elevon vs `motor_A_R3` | **593.069028** | **409.833025** |
| right elevon vs `motor_B_R3` | 593.069028 | 409.833025 |
| **survives the fix (2 pairs)** | **1,186.138056** | **819.666050** |
| against all six, BEFORE | 4 pairs / 1,640.518502 (R2 227.190223 + R3 593.069028, per duct) | 4 pairs / 1,067.666548 |

So: **the deletion does not introduce it and does not remove it** (it is 4 pairs before, 2 after
because only R3's and R2's cans reach x ±55.25); **the resize shrinks it 30.9 % and does not clear
it** (18.000 > 11.25, so the root is still inside the can).

**Method note, because this pair produced a false zero.** `env.intersect(elevon_compound)` returns
**0.0000** for the corrected envelope, while the pair really is 819.6661 mm³ — the documented
compound-call hazard, in a new place. The elevon also has **overlapping member solids**
(5 solids, compound volume 9,474.872 mm³ = sum of solids, true union 9,226.872, so
**248.000 mm³ of self-overlap**), which makes the per-solid sum an over-count (1,256.2397 vs
1,186.1381). The quoted figure **fuses the elevon first, then intersects once**; independent
inclusion-exclusion over the same 5 solids agrees to 1 × 10⁻⁴
(`elevon_pairs_fused.json`, `elevon_pairs.json`).

### 6c. The fix for it, measured, and it is not in my scope

A **6.75 mm root trim** (root out to 18.000 mm from the duct axis) clears the corrected can
**0.0000 mm³**, on both ducts (`elevon_trim_trial.json`). An as-built r21 can would need 9.75 mm
(182.6720 mm³ still remains at 18.000). The same trim leaves the **elevon-vs-nozzle pierce
untouched at 120.2476 mm³** — the plate crosses the nozzle shell at x ±83 either way — and the left
elevon also overlaps the 42_6 fuselage by **95.3041 mm³** (`elevon_context.json`). Those two are a
**wing-to-duct packing defect that predates the motors**, they are in no receipt, and they need a
wing-geometry decision, not an envelope edit.

---

## 7. BOARD CORRECTIONS

1. **"MINIMUM FIX: delete 4 of the 6 envelopes, keep one per duct → 0 pairs / 0.0000 mm³"**
   (board §"drone-mech interference", and the prior report's verdict table). **Deletion alone, with
   the as-built Ø42 envelope left at its own station, gives 2 pairs / 1,248.5946 mm³ — not zero.**
   It reaches zero only with the sourced Ø36 × 70 envelope (or by re-stationing the as-built can to
   z 106). The prior report's §5b states the sourced can as part of the minimum change; the board
   line dropped that half. Both zero paths are re-measured here.
2. **"the full 54-pair sweep"** — its own components (15 motor-motor + 18 motor-rotor + 18
   motor-stator) sum to **51**. I ran 51 and, additionally, the unrestricted **87** (each envelope
   against all six rotors and all six stators); cross-duct pairs are **0** in every case. The label
   is wrong, no number is.
3. **"22 pairs / 331,033.5633 mm³"** is correct **for its 23-part neighbour set**, and it is
   **incomplete for the airframe**: adding the carrier frames (0) and the two elevons gives
   **26 pairs / 332,674.0818 mm³**. The elevon class is 4 pairs / 1,640.5185 mm³ of that and was in
   no sweep.
4. **"correcting the envelope alone takes 22 → 12 pairs, 331,033.56 → ≈231,450 mm³"** — the pair
   count is right, the total is **232,157.2333** measured. Its closed-form row used
   π·18²·34 = 34,764.86 where 34,607.78 is correct, and counted 2 shaft pairs where there are 4.
5. **"envelope as built 99,908.93 vs should be 71,251.29 = 40.2 % too large"** — an unlike-for-like
   ratio: 71,251.29 is the **can only**, the 99,908.93 includes the 8 mm stub. Can + shaft on both
   sides: **39.57 %**. The defect stands; the percentage is 0.65 points high.
6. **"envelope 42 × 72 is UNSOURCED"** (previous audit) — the prior wave already corrected this to
   LISTING-tier sourced; this wave confirms and sharpens it: the repo carries **no dimensional
   field for any motor** (`phase15_sourcing.json`), so 36 × 70 is **spec-prose + three retail
   listings**, and the correct label is **SOURCED at LISTING/SPEC tier, not drawing-tier**.

---

## 8. What this does NOT establish

- **No supplier drawing.** §3b. The 36/70/5/17 are spec prose and retail listing text.
- **The 63.7 MB full assembly was not kernel-imported.** The six instances are established by a
  PRODUCT-entity census of that file (§2a) and geometrically by the six envelope STEPs the
  assembly references. A full-assembly re-parse would not change the pair list — it would test the
  same solids — but it was not done, and the claim is scoped to the sub-assembly.
- **No flow, thermal, containment, rotor-dynamic or balance assessment** of the surviving motor
  inside the nozzle. §5 quantifies the area loss (21.302 %) and nothing else.
- **The elevon defect is characterised, not resolved.** §6c gives the measured trim that clears the
  can and shows it does not clear the nozzle pierce.
- **The whole-airframe screen is a bounding-box screen.** 73 named parts / 516 solids; a bbox miss
  is a proof of no intersection, a bbox hit is only a candidate. Both hits were then tested with
  native booleans — but the screen is over the repo's 2026-11-10 per-solid export, not over a fresh
  parse of all 81 STEP files.
- **Nothing about mass or stress.** The 1.096 kg is 4 × a LISTING-tier unit mass.

---

## 9. Artefacts and how to reproduce

| file | content |
|---|---|
| `fab_dm_envelopes.py` | the sweep: 8 cases, envelope-vs-envelope **and** vs 24 neighbours, station trials, controls, deletion, corrected artefact |
| `fab_dm_envelopes.json` | its output — every number in §1–§4 |
| `da_motors_4of6_deleted.step` | **the deletion**, as a real STEP (2 solids, 199,817.859 mm³), sha256 `A2F19625…10D363` |
| `da_motor_envelopes_corrected_36x70.step` | **the corrected envelope** (2 solids, 143,170.231 mm³), sha256 `C58B25E4…3DC95F` |
| `census_step_products.py` / `step_product_census.json` | PRODUCT-entity census of both assembly files |
| `sourcing_check.py` / `sourcing_check.json` | the citation for 36 × 70, and the proof that the repo records no motor dimension |
| `fab_dm_carriers.py` / `fab_dm_carriers.json` | whole-airframe bbox screen (73 parts / 516 solids) + carrier frames + first-pass elevon numbers |
| `fab_dm_elevon_pairs.py` / `elevon_pairs.json` | elevon inclusion-exclusion, and the false zero |
| `fab_dm_elevon_fused.py` / `elevon_pairs_fused.json` | **the quoted elevon numbers** (fused first) |
| `fab_dm_elevon_context.py` / `elevon_context.json` | elevon vs nozzle 120.2476, vs 42_6 95.3041 |
| `fab_dm_elevon_trim.py` / `elevon_trim_trial.json` | the 6.75 mm trim that clears the can |
| `elevon_operand_check.py` / `elevon_operand_check.json` | the elevon's 248.000 mm³ self-overlap |
| `check_report.py` / `run_check_report.log` | **155 assertions** re-deriving every number in this report from the JSON receipts; **0 failed**, exits non-zero on drift |
| `run_*.log` | console receipts, verbatim |

```powershell
cd E:/engineering-portfolio-audit/evidence/fab-dm-envelopes
& "C:/Program Files/Python312/python.exe" census_step_products.py    # <1 s
& "C:/Program Files/Python312/python.exe" sourcing_check.py          # <1 s
& "C:/Program Files/Python312/python.exe" fab_dm_envelopes.py        # 160 s, writes both STEPs
& "C:/Program Files/Python312/python.exe" fab_dm_carriers.py         # 5 s
& "C:/Program Files/Python312/python.exe" fab_dm_elevon_pairs.py     # 60 s
& "C:/Program Files/Python312/python.exe" fab_dm_elevon_fused.py     # 10 s
& "C:/Program Files/Python312/python.exe" fab_dm_elevon_trim.py      # 8 s
& "C:/Program Files/Python312/python.exe" check_report.py             # asserts this report, 155 checks
```

Inputs are read-only: `repos/drone-mech/highspeed_edf/deliverables/phase15_geometry/step/*.step`.
No file under `repos/drone-mech` was written; no git command was run.

---

## 10. Status line for `AGENT_BOARD.md` (for the lead to merge — I did not write outside my folder)

```
| fab-dm-envelopes | DELETION EXECUTED AND VERIFIED. Keep motor_A_R3 + motor_B_R3 (aft-most station,
| can start = own hub aft face), delete R1+R2 x 2 ducts. Station choice is MEASURED, not arbitrary:
| keeping R1 = 8 pairs / 85,448.6614, R2 = 6 / 43,890.1297, R3 = 2 / 1,248.5946 (as-built, in place).
| Deletion ALONE with the as-built Ø42 envelope = 2 pairs / 1,248.5946, NOT zero (corrects the board's
| "delete 4 -> 0"): it reaches 0 pairs / 0.0000 only with the corrected Ø36x70+Ø5x17 (or by
| re-stationing to z 106, which blocks 28.994 % of the throat vs 21.302 % for the resized can).
| Resize ALONE = 12 pairs / 232,157.2333 (-29.87 %), clearing exactly the 10 stator-carrier pairs
| (6,242.9729) and nothing else. Corr. envelope = 71,585.116 mm3, SOURCED at LISTING/SPEC tier
| (spec:302 + 3 retail listings), NOT drawing-tier; repo carries NO motor dimension field.
| NEW: two parts no sweep contained — carrier frames (0 pairs) and the ELEVON ROOTS (2 pairs /
| 1,186.1381 as-built, 819.6661 corrected, survives every fix; a 6.75 mm root trim clears the can).
| Whole-airframe baseline is therefore 26 / 332,674.0818, not 22. Recommend BOTH (delete + resize).
| Artefacts: da_motors_4of6_deleted.step A2F19625…10D363, da_motor_envelopes_corrected_36x70.step
| C58B25E4…3DC95F, fab_dm_envelopes.json. Open: 21.302 % throat block; elevon-vs-nozzle 120.2476. |
```