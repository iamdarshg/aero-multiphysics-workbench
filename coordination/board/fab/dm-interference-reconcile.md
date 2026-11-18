# dm-interference-reconcile — reconciling 1,556.232076 mm3 / 6 pairs vs 9,125.712739 mm3

STATUS: **COMPLETE** — both figures traced to their basis, the closure sweep re-run on the deliverable, the arithmetic reconciled to 0.000000 residual, and the board replacement text supplied. No repo write, no commit.

## 0. The conflict under audit

- Figure A (post ring-redesign unit): **1,556.232076 mm3 / 6 interference pairs**
  (7 rows removed, 0 added, from a prior 4,631.820365 / 13)
- Figure B (knife-edge/fairing unit): **9,125.712739 mm3** vs a 'stock' 9,134.218881 mm3
  (0 rows added, 0 removed, 4 rows changed)

Both were published as the airframe total. At most one can be.

## 1. Basis of each reported figure (file measured, pair population, tolerance, part set)

Both figures were measured correctly **for their own population**. Neither is an arithmetic error, and
neither is the airframe total. Here is exactly what each one is.

### 1a. Figure A — 1,556.232076 mm³ / 6 pairs

| what | value | where |
|---|---|---|
| the claim | "**airframe total as modelled** 4,631.820365 / 13 pairs" → after the ring fix "**1,556.232076**, 6 pairs, set diff 7 removed / 0 added / 0 changed" | `evidence/dm-ring-redesign/REPORT.md:239` (six-row subtotal), `:240` (total), `:242-243` (post-fix), `:211-213` (population) |
| produced by | `work/r3_final.py` → `out/r3_final.json` (`"mover_total": 1556.232076`), stdout `log/r3_final.log:10` | `dm-ring-redesign/REPORT.md:299` |
| geometric file | `out/drone-mech_fuselage_rev1.step`, sha256 `d9ba7aeb7716cdd1ba4f289d…`, **1 solid / 540 faces / 206,454.319709 mm³** — the shipped DM-FUS-001 REV 1 | `r3_final.py:138`, `dm-ring-redesign/REPORT.md:245-246` |
| pair population | **movers × neighbours, where the only movers are the two elevons.** 34 candidate rows (elevon × {fuselage, nozzle A/B, collar A/B, duct A/B, wing L/R/C, motor A/B ×R1–R3, own pushrod}), 12 bbox-hit, 6 non-zero | `r3_final.py:205-214` |
| part set included | the 28 as-built groups in `r3_final.py:142-168` (fuselage, ring A/B, 3 wings, 2 elevons, 2 pushrods, 2 ducts, 2 nozzles, 2 collars, 4 vanes, 4 servo mounts, 6 motor envelopes); the two D84.0 beads exist only as code (`r3_final.py:36,71-74`) and were checked against the fuselage and the ring, not against the rest | — |
| boolean tolerance | one `BRepAlgoAPI_Common` per pair, OCC default fuzzy; bbox prefilter pad 1e-6 mm; `BRepGProp.VolumeProperties_s` eps 1e-12; row threshold 1e-9 mm³ | `r3_final.py:106-129`, `:90-91` |

**Why it is not the airframe total:** the body is a *neighbour* in this population and never a mover, so a
`fuselage ↔ wing` row cannot appear in it by construction. The report says so itself at `:310-311` — *"The
full airframe was swept for the rings only, so the six elevon rows are carried at their measured current
values."* It is the **elevon-root subtotal**, correctly named "mover total" in the JSON.

### 1b. Figure B — 9,134.218881 mm³ stock / 9,125.712739 mm³ faired, 8 rows

| what | value | where |
|---|---|---|
| the claim | row table 8 rows, **total 9,134.218881 → 9,125.712739**, "set diff: 0 added, 0 removed, 4 changed"; 6 further pairs bbox-separated | `evidence/dm-knife-fairing/REPORT.md:188-204`, `:206-212` |
| produced by | `work/k6_interference.py` → `out/k6_stock.json` (`"total": 9134.218881`), `out/k6_fair_v4.json` (`9125.712739`), stdout `log/k6_stock.log:9` | `dm-knife-fairing/REPORT.md:289` |
| geometric file | stock run measured **`work/obj/fuselage_stock.step`** (field `"fuselage"` in `k6_stock.json`), sha256 `6f1cc2258c407f57e32fb232…` — the **generator-rebuilt** stock body at 206,454.320759 mm³, *not* the shipped STEP (`d9ba7aeb…`, 206,454.319709; Δ 1.05e-6 mm³). Faired run measured `work/obj/part_fair4.step` = `out/drone-mech_fuselage_rev2_fairing.step`, sha256 `3139d2b5…`, 308,099.0371 mm³ | `k6_stock.json`, `k4_stock.json:"final"`, `dm-knife-fairing/REPORT.md:27-33` |
| pair population | **two disjoint sweeps summed:** (i) fuselage × 21 named neighbours (`k6_interference.py:97-100`), (ii) elevon L/R × {nozzle A, nozzle B, motor A_R3, motor B_R3} (`:108-111`). 29 candidate pairs, 6 bbox-skipped, 8 non-zero, 15 measured zero | `k6_stock.json:"skipped"` |
| part set included | 1 body + 21 named groups, **with the v2 rings already in it** (`k6_interference.py:26,59`) so the ring rows read 0 | `dm-knife-fairing/REPORT.md:188-189` |
| boolean tolerance | **cadquery `Shape.intersect()`**, one boolean on a compound operand; `BRepGProp` eps 1e-12 (absolute); row threshold 1e-9 mm³; bbox pad 1e-6 mm | `k6_interference.py:45-49,86-95` |

**Why it is not the airframe total either:** it is a *body-inclusive but still partial* population. It never
pairs the elevons with their pushrods, never pairs any two static parts (duct ↔ collar, wing ↔ duct,
bead ↔ vane…), and its elevon rows stop at the R3 motor. It is the **widest published figure, not a closure.**

### 1c. A third row value hides inside both — and it is an instrument, not a population, effect

The same named pair (`elevon_L ↔ motor_A_R3` envelope, same two STEP files) reads three ways:

| instrument | mm³ | solids out | reported by |
|---|---:|---:|---|
| `dm-final-package/work/r1c_pairs.py` — motor replaced by a **built Ø36×70 can** (`env_corrected`, `:105-107`) | 409.833023 | — | `dm-final-package/REPORT.md:59`; inherited as the six-set 1,204.481397 |
| raw `BRepAlgoAPI_Common(OneShape, OneShape)` | **585.708363** | 2 | `dm-ring-redesign` (`r3_final.log:6`) |
| cadquery `Shape.intersect(compound, solid)` | **593.069028** | 4 | `dm-knife-fairing` (`k6_stock.log:6`) |

Both prior sweeps took **one boolean against a compound operand** — and the elevon is a compound of **five**
solids (plate 8,987.637813 + three Ø3 hinge pins 42.411501 each + horn 360.000000; Σ = 9,474.872316 vs
compound 9,474.872315, so the five are disjoint and additive). Reproduction on the same files
(`work/s2_instrument.py`, `work/s2b_algebra.py`):

| algebra on the same 5-solid elevon | mm³ |
|---|---:|
| cadquery `Shape.intersect` | 593.069028142 (= k6, to 9 dp) |
| raw `BRepAlgoAPI_Common` on the OneShape compound | 585.708362858 (= r3_final, to 9 dp) |
| **solid-by-solid, 5 booleans summed** | **628.119863682** |
| fuse the 5 solids first, then one boolean | 593.069028161 (the fuse loses 248.0 mm³: 9,226.87 vs 9,474.87 — a lossy fuse, not geometry) |

The boolean is **not** tolerance-limited: fuzzy 1e-6 / 1e-5 / 1e-4 / 1e-3 all return 585.708362858 to nine
decimals. It is **algebra-limited**: one compound boolean silently drops the hinge-pin overlap. On the
`elevon ↔ pushrod` row the same failure is total — raw Common returns **0.000000** where the solid-by-solid
sum is **2.464577** (= 1.633362 + 0.831215 on two disjoint elevon solids). That, not a pair-definition
argument, is why `dm-ring-redesign:255` saw 0.000000 where the corpus recorded 4.534020.

## 2. My own sweep on the current authoritative part

**Run:** `work/s3_closure.py --fuselage work/obj/drone-mech_fuselage_rev1.step --tag stock` →
`out/s3_closure_stock.json`, stdout `log/s3_closure_stock.log` (2,317 s). Everything measured from copies in
`work/obj/`; their sha256 are in `out/input_sha256.txt`.

### 2a. Population — stated so it can be re-run and so it cannot be confused with either legacy figure

* **the 32 as-built solids-groups of the current assembly**: the shipped body `drone-mech_fuselage_rev1.step`
  (sha256 `d9ba7aeb7716cdd1ba4f289d…`, **1 solid / 540 faces / 206,454.319709 mm³**), `ring_v2_A/B`, the two
  D84.0 beads, 3 wing sectors, 2 elevons, 2 pushrods, 2 duct tubes, 2 nozzles, 2 rotor collars, 4 vector
  vanes, 4 servo mounts, 6 rotor envelopes;
* **every unordered pair** = 496; bbox prefilter (pad 1e-6 mm) → **95 candidate pairs**; **401 bbox-separated**
  pairs enumerated in the JSON as *skipped, never assumed zero*; **61 pairs examined and exactly zero**;
  **34 pairs non-zero**;
* the two beads exist only as code (`r3_final.py:36,71-74`: OD 42.0, ID 41.0, z0 243.8, length 1.20). No STEP
  was ever written for them and no earlier sweep ever paired them — stated, not hidden.

### 2b. Algebra and tolerance — stated, and the reason they matter

| item | value |
|---|---|
| algebra | **solid-by-solid**: every pair of constituent solids is booleaned separately and summed |
| boolean | OCP `BRepAlgoAPI_Common`, **default fuzzy 0.0** |
| why not one boolean | the elevon is a 5-solid compound; one compound boolean loses 35–42 mm³ per motor row and returns **exactly 0.000000** on three bbox-overlapping rows (§1c, §2d) |
| fuzzy is not the lever | 1e-6 / 1e-5 / 1e-4 / 1e-3 all return 585.708362858 on the reference pair to 9 dp |
| volume | `BRepGProp.VolumeProperties_s`, eps 1e-12, absolute |
| row threshold | 1e-9 mm³ |
| bbox | `BRepBndLib.AddOptimal_s`, pad 1e-6 mm |

### 2c. The one set excluded, and why it is not a part population

Six rows are `motor_*_R1 × motor_*_R2/R3` at **50,033.004601 mm³** and **157.079633 mm³**. The six files are
Ø42 × 80 bounding envelopes placed at z 12–92, 48–128 and 84–164 — i.e. **three overlapping envelopes of the
three blade rows of one rotor** (the corpus separately ships `duct_A_rotor_R1_N13 / R2_N12 / R3_N11`). Two
envelopes are not two parts, and a 50 % envelope-on-envelope overlap is the signature of a bounding box, not a
clash. The corpus already reached the same conclusion when it published 331,033.5633 mm³ and then diagnosed it
as duplicated envelopes — *"minimum fix: delete 4 of the 6 envelopes, keep one per duct → 0 pairs"*
(`AGENT_BOARD.md:2705`). One envelope per rotor is therefore the population; the six excluded rows are listed
with their volumes so nothing is hidden: **6 pairs / 200,446.177670 mm³ excluded as envelope-on-envelope**.

### 2d. Row-level pair list — 28 rows, part A, part B, volume, class

Class key: **A1** elevon-root clash (one named cause, fix specified in `fab-dm-final` §5) · **A2** pushrod
modelling artefact · **B** body ↔ lifting-wing sector · **C** static bonded-joint overlap (no fit class
declared anywhere in the corpus).

| # | part A | part B | mm³ | class |
|---:|---|---|---:|---|
| 1 | fuselage (REV 1) | lifting_wing_left_sector | **3,781.632735** | B |
| 2 | fuselage (REV 1) | lifting_wing_right_sector | **3,781.632740** | B |
| 3 | elevon_left | motor_A_R3 envelope | **628.119864** | A1 |
| 4 | elevon_right | motor_B_R3 envelope | **628.119864** | A1 |
| 5 | elevon_left | lifting_wing_left_sector | **561.996031** | A1 |
| 6 | elevon_right | lifting_wing_right_sector | **561.996031** | A1 |
| 7 | elevon_left | motor_A_R2 envelope | **249.750363** | A1 |
| 8 | elevon_right | motor_B_R2 envelope | **249.750363** | A1 |
| 9 | elevon_left | nozzle_A shell | **120.247564** | A1 |
| 10 | elevon_right | nozzle_B shell | **120.247564** | A1 |
| 11 | elevon_left | fuselage (REV 1) | **72.160111** | A1 |
| 12 | elevon_right | fuselage (REV 1) | **72.160111** | A1 |
| 13 | elevon_pushrod_left | elevon_left | **2.464577** | A2 |
| 14 | elevon_pushrod_right | elevon_right | **2.464577** | A2 |
| 15 | duct_A tube (Ø82) | collar_A | **512.079603** | C |
| 16 | duct_B tube (Ø82) | collar_B | **512.079603** | C |
| 17 | vane_A1 | servo_mount_A1 | **320.137167** | C |
| 18 | vane_B1 | servo_mount_B1 | **320.137167** | C |
| 19 | vane_A2 | servo_mount_A2 | **196.000000** | C |
| 20 | vane_B2 | servo_mount_B2 | **196.000000** | C |
| 21-24 | nozzle_A/B shell | vane_A1, vane_A2, vane_B1, vane_B2 | **20.002085** each = 80.008340 | C |
| 25-28 | bead_A/B | vane_A1, vane_A2, vane_B1, vane_B2 | **2.400232** each = 9.600928 | C |
| | **total, 28 rows** | | **12,978.785305** | |

Class subtotals: **A1 10 pairs / 3,264.547867** · **A2 2 pairs / 4.929154** · **B 2 pairs / 7,563.265475** ·
**C 14 pairs / 2,146.042809**. Ring v2 appears in **no row**: ring↔fuselage, ring↔duct, ring↔wing, ring↔bead,
ring↔nozzle, ring↔vane are all **0.000000** — the ring redesign holds on my instrument too.

**Two findings that are new here, not arithmetic:**

1. **The bead, added by the ring fix, clashes with all four vector vanes** — 4 rows × 2.400232 mm³. The bead
   was checked only against the fuselage and the ring (`r3_final.py:176,183-202`); no sweep ever paired it with
   the vanes. It is the only *new* interference the ring wave introduced, and it is 9.6 mm³ — small, but it is a
   fit that must be declared or relieved.
2. **`elevon ↔ wing sector` (1,123.992062 mm³) and `elevon ↔ R2 envelope` (499.500726 mm³) exist and were
   previously recorded as zero.** `dm-ring-redesign` measured both rows with `bbox_hit = true` and volume
   **0.000000** (`r3_final.json`, mover rows 3, 4, 6, 9, 10 and 12 of the 34 — every zero row whose bbox overlapped). Re-produced here: the raw compound boolean returns
   **0.000000** on that pair while the solid-by-solid sum returns **561.996031** (`work/s4_validate.py`,
   `log/s4_validate.log`). A zero that a bbox cannot explain is a false zero, and a strict refinement proves it:
   if one constituent solid alone intersects by 559.086833, the union cannot intersect by 0.000000.

   The per-solid values were then re-derived through a **different OCC operator**, using the exact volume
   identity `vol(A) − vol(A − B) = vol(A ∩ B)` (`work/s4c_cut.py`, `log/s4c_cut.log`, `out/s4c_cut.json`):

   | piece | vol(A) | vol(A−B) | intersection by CUT identity | by Common | residual |
   |---|---:|---:|---:|---:|---:|
   | elevon solid 0 ↔ wing_left | 8,987.637813 | 8,428.550980 | **559.086833** | 559.086833 | 0.000000 |
   | elevon solid 4 ↔ wing_left | 360.000000 | 357.090802 | **2.909198** | 2.909198 | 0.000000 |
   | elevon solid 0 ↔ motor_A_R3 | 8,987.637813 | 8,401.929450 | **585.708363** | 585.708363 | 0.000000 |
   | elevon solid 1 ↔ motor_A_R3 | 42.411501 | **0.000000** | **42.411501** | 42.411501 | 0.000000 |

   Two independent operators, identical to the last digit, and the hinge pin is **100 % buried** in the R3
   envelope (`vol(A − B) = 0`). That is the 42.411501 mm³ the compound booleans throw away. (Monte-Carlo
   point-in-solid sampling was attempted first and abandoned — 6,000 samples had not finished in 8 minutes on
   this geometry, so the exact identity replaced the statistical one.)

### 2e. Cross-checks against the earlier instruments (same rows, so the comparison is like-for-like)

| row | dm-ring-redesign | dm-knife-fairing | **this sweep** |
|---|---:|---:|---:|
| fuselage ↔ wing left | not in population | 3,781.632735 | **3,781.632735** |
| fuselage ↔ wing right | not in population | 3,781.632740 | **3,781.632740** |
| elevon ↔ fuselage (each side) | 72.160111 | 72.160111 | **72.160111** |
| elevon ↔ nozzle (each side) | 120.247564 | 120.247564 | **120.247564** |
| elevon ↔ motor R3 (each side) | 585.708363 | 593.069028 | **628.119864** |
| ring v2 rows | 0.000000 | 0.000000 | **0.000000** |

The rows on which all three instruments agree agree **to the last digit**; the only row that moves is the one
whose operand is the 5-solid compound. That is the proof that the disagreement is algebra, not geometry.

## 3. The authoritative figure, and its name

**28 pairs / 12,978.785305 mm³** — the **closure figure (C-28)**, on

> **DM-FUS-001 REV 1** (one solid, 540 faces, **206,454.319709 mm³**, 320.0042 g, sha256
> `d9ba7aeb7716cdd1ba4f289d…`) **+ ring v2 A/B + bead A/B**, with the 3 wing sectors, 2 elevons, 2 pushrods,
> 2 duct tubes, 2 nozzles, 2 rotor collars, 4 vector vanes, 4 servo mounts and the 6 rotor envelopes (every
> envelope ↔ part pair measured; envelope ↔ envelope pairs excluded, §2c).

Its basis, in one sentence a future reader cannot mis-take: *interference over the **closure population** —
every unordered pair of as-built solids in the current assembly (95 bbox-prefiltered candidates of 496,
401 bbox-separated and enumerated, 61 examined-and-zero), envelope-on-envelope pairs excluded as non-parts,
measured with **solid-by-solid `BRepAlgoAPI_Common` at default fuzzy and `BRepGProp` at eps 1e-12**.*

| class | pairs | mm³ | what it is |
|---|---:|---:|---|
| **A1** elevon-root clash | 10 | 3,264.547867 | one named cause (elevon root station); fix specified and measured in `fab-dm-final` §5 (+38.485 mm outboard re-station → 0 of these pairs) |
| **A2** pushrod artefact | 2 | 4.929154 | a fixed Ø2 × 38 representative rod 21.69 mm past the plate in free air; removed from the count, not fixed |
| **B** body ↔ lifting-wing sector | 2 | 7,563.265475 | pre-existing, static, in *no* published total, no fit class declared |
| **C** static bonded-joint overlap | 14 | 2,146.042809 | duct ↔ collar, vane ↔ servo mount, nozzle ↔ vane, **bead ↔ vane**; no fit class declared anywhere in the corpus |
| **total (C-28)** | **28** | **12,978.785305** | |
| *excluded* envelope ↔ envelope | 6 | 200,446.177670 | three overlapping envelopes of one rotor's three blade rows — not parts (§2c) |

Ring v2 contributes **0 pairs / 0.000000 mm³**. The ring redesign is confirmed on a third independent sweep.

*Rounding note: the four class subtotals sum to 12,978.785306 against the sweep's own total of
**12,978.785305** — 1 × 10⁻⁶ from adding 6-dp rows (the two body↔wing rows are 3,781.632735325 and
3,781.632740489). The sweep total is authoritative; the subtotals are the published 6-dp rows so that every
identity in §4 closes to the last digit.*

"Fit-critical" (moving parts only, A1+A2) = **12 pairs / 3,269.477021 mm³**. That is the number a fit/disposition
conversation needs; C-28 is the number the *board* needs, because B and C are real solid overlap that no
document dispositions.

## 4. How the other two figures relate to it — arithmetically, to the last digit

### 4a. `9,134.218881` = `1,556.232076` + the two wing rows + one instrument swap

**9,134.218881 = 1,556.232076 + 7,563.265475 + 14.721330**  — residual **0.000000**

* **+ 7,563.265475** = the two `fuselage ↔ lifting-wing sector` rows (3,781.632735 + 3,781.632740), which are
  **structurally absent** from figure A: figure A's movers are the elevons only, so the body is never a mover
  (`r3_final.py:205-214`). This is 80 % of the gap.
* **+ 14.721330** = 2 × (593.069028 − 585.708363), the two motor R3 rows measured with cadquery's compound
  boolean instead of raw `BRepAlgoAPI_Common` on the same operand (§1c). It is an instrument difference, and it
  is why `dm-knife-fairing:206-209` could not find the 7.36 mm³/row — it is not a wave-17 convention, it is the
  operand algebra, and it is identical before and after the fairing, so its set diff still cancels.

So figure **B is figure A's population plus two body rows**, with one row re-measured. It is a superset of A, not
a rival measurement of the same thing.

### 4b. `9,125.712739` is the same 8 rows with a different body, not a different population

**9,125.712739 = 9,134.218881 − 8.506142**, where **8.506142 = 4.205053 + 4.205059 + 0.048015 + 0.048015**

Those are exactly the four rows the faired body changes (`dm-knife-fairing:193-203`), and the set diff is
0 added / 0 removed / 4 changed. The faired number is therefore a **body substitution inside figure B's
population**, and it inherits every gap figure B has.

### 4c. Figure A → C-28, row by row

`1,556.232076` is 6 of the 10 elevon rows, measured with an algebra that returns false zeros:

| step | mm³ |
|---|---:|
| figure A as measured (6 rows) | 1,556.232076 |
| + `elevon ↔ wing sector`, 2 rows that A recorded as **0.000000** with `bbox_hit = true` | +1,123.992062 |
| + `elevon ↔ R2 envelope`, 2 rows that A recorded as **0.000000** | +499.500726 |
| + `elevon ↔ pushrod`, 2 rows that A recorded as **0.000000** | +4.929154 |
| + the two R3 rows re-measured solid-by-solid (628.119864 vs 585.708363) | +84.823002 |
| **= A's own population, correctly measured (12 rows)** | **3,269.477020** |

then `+ 7,563.265475` (B) `+ 2,146.042809` (C) `= 12,978.785304` = C-28 (±2 × 10⁻⁶, printed-row rounding).

### 4d. Figure B → C-28

| step | mm³ |
|---|---:|
| figure B as measured (8 rows, k6 algebra) | 9,134.218881 |
| + the two motor rows on the solid-by-solid algebra (2 × 35.050836) | +70.101671 → **9,204.320552** |
| + `elevon ↔ wing sector` (2 rows, outside B's population) | +1,123.992062 |
| + `elevon ↔ R2 envelope` (2 rows, outside B's population) | +499.500726 |
| + `elevon ↔ pushrod` (2 rows, never paired in B) | +4.929154 |
| + the 14 static joint rows (never paired in B) | +2,146.042809 |
| **= C-28** | **12,978.785304** |

### 4e. Lineage of A's own number, so it cannot be re-inflated

`4,631.820365` (figure A's "as modelled" total, `dm-ring-redesign:240`) `= 1,556.232076 + 3,075.588289`, i.e.
A's number plus the seven ring rows the redesign removed. It was **never** an airframe total either: it is the
elevon-root population plus the ring population, with the body↔wing rows and every static joint row missing.
The corpus's own earlier `331,033.5633 / 22` and `332,674.0818 / 26` totals are the envelope-duplication
artefact reproduced as the 6 excluded rows in §2c; the board already diagnosed that at `AGENT_BOARD.md:2705`.

## 5. Fuselage stability, and which part is the deliverable

### 5a. Every file that carries a fuselage number agrees

| quantity | value | instrument | where |
|---|---:|---|---|
| **REV 1 volume** | **206,454.319709 mm³** | `BRepGProp` eps 1e-12 on the STEP | my `out/s1_probe.json`; `dm-knife-fairing/log/k1_probe.log:1`; `dm-final-package/log/r5_validate.log:2`; `dm-bearing-rings/REPORT.md:37`; `dm-ring-redesign/log/r2_redesign.log:19` |
| REV 1 mass at 1550 kg/m³ | **320.0042 g** | 206,454.319709 × 1.55e-3 | same four reports |
| REV 1 topology | **1 solid / 1 shell / 540 faces / 3,122 edges** | `TopExp_Explorer` | `k1_probe.log:1`, `k5_stock.log:1` |
| REV 1 identity | sha256 `d9ba7aeb7716cdd1ba4f289d…`, 9,801,595 B — **byte-identical in four places** (`dm-final-package/out`, `dm-bearing-rings/out`, `dm-ring-redesign/out`, my copy) | `Get-FileHash` | `out/input_sha256.txt` |
| rebuild control | 206,454.320759 mm³ / 320.0042 g / 1 solid | generator rebuild | `dm-knife-fairing/out/k4_stock.json:"final"`, sha256 `6f1cc225…` |
| **faired REV 2 volume** | **308,099.037095 / 308,099.037122 mm³** | `BRepGProp` on STEP / BREP | `k4_fair4.log:11`, `k5_fair_v4.log:1` |
| faired REV 2 mass | **477.5535 g** | Δ **+157.5493 g (+49.2 %)** | `dm-knife-fairing/REPORT.md:167-168` |
| faired REV 2 topology | 1 solid / 1 shell / 564 faces / 0 free edges / 0 non-manifold | `BRepCheck` valid | `k5_fair_v4.log:1` |

Two numbers *look* like instability and are not:

1. **206,454.319709 (STEP) vs 206,454.320759 (rebuild)** — Δ 1.05e-6 mm³, 5.1e-12 relative: the same solid
   written by two routes. Both give 320.0042 g at 4 dp. `dm-knife-fairing:30-33` is right that this is an
   identity control, not a discrepancy.
2. **206,454.3197 vs 206,420.2211** — the second is bare `Shape.Volume()`, which is **34.0986 mm³ (0.0165 %)
   low** on this B-rep and must never be quoted (`dm-final-package:201`). Every published figure uses
   `BRepGProp`. This report uses `BRepGProp` everywhere.

The volume/mass pair is therefore **stable to 1e-6 mm³ across every file that carries it**, and the faired
variant is stable to 2.7e-5 mm³ between its STEP and its BREP.

### 5b. The deliverable is the UNFAIRED part — DM-FUS-001 REV 1

Four measured reasons, in order of weight:

1. **It is the artefact that exists as a deliverable.** REV 1 ships as STEP + BREP + watertight STL (59,964
   triangles, 0.0519 % volume agreement) + an A3 drawing with title block + a README of hashes
   (`dm-final-package/REPORT.md:136-143`). The faired part ships as a STEP and a BREP only — no drawing, no
   mesh, no revision stamp, no title block.
2. **The fairing is unfinished on its own terms.** The worst convex edge is still **5.1162°** at
   `(±45.737, ±42.565, +172.013)`, and the land at z = 60 is **0.1875 mm** because the 11-station loft
   interpolates under the commanded 44.60 mm — and pinning a station there **splits the part into 3 solids**
   (measured, `k4_stock2`, `dm-knife-fairing:253-255`). A part with a 5° feather and a 0.19 mm land is not more
   fab-ready than one with a 2.83° feather.
3. **It costs +157.5493 g = +49.2 % of the fuselage.** No mass budget, CG or structural case in the corpus has
   been run against 477.5535 g; the airframe mass of record (472.273 g total) is built on 320.0042 g.
4. **It does not move the interference figure materially** — 4 rows change by ≤ 4.21 mm³, **−8.506142 mm³
   total**. The deliverable decision is therefore not an interference decision.

So: **the fairing is a candidate REV 2**, needing (i) a z = 60 station that does not split the part, (ii) a
drawing and mesh, (iii) a mass/CG/structural re-run at 477.5535 g. Until then the unfaired solid is the part of
record, and its interference figure is C-28.

**Interference cost of that choice:** on the faired body the same 28-row population would read
**12,970.279163 mm³** (12,978.785305 − 8.506142, the exact 4-row delta measured instrument-matched in
`dm-knife-fairing:193-203`), i.e. the deliverable choice costs **8.51 mm³** of interference and saves 157.55 g.
Not re-measured here on the full closure — stated as a limit, not as a measurement.

## 6. The one-line statement, and the correction to the board

### 6a. The sentence the board should carry

> **drone-mech interference (authoritative, closure basis): 28 pairs / 12,978.785305 mm³** on DM-FUS-001 REV 1
> (one solid, 206,454.319709 mm³) + ring v2 A/B + bead A/B — comprising **12 pairs / 3,269.477021 mm³**
> moving-part (10 elevon-root rows, one named cause + 2 pushrod modelling artefacts), **2 pairs /
> 7,563.265475 mm³** body↔lifting-wing sector, **14 pairs / 2,146.042809 mm³** static joint overlap
> (undispositioned); **ring v2 = 0 pairs / 0.000000 mm³**. Basis: every unordered pair of as-built solids,
> solid-by-solid OCC booleans, default tolerance, `BRepGProp` eps 1e-12. `1,556.232076` and `9,125.712739` are
> subsets of this figure, not totals.

Short form, if a board row has one cell:

> `interference | 28 pairs / 12,978.785305 mm³ (closure basis) — elevon root 3,264.548 + pushrod 4.929 + body↔wing 7,563.265 + static joints 2,146.043; ring v2 CLEAN 0.000000 | subsets 1,556.232076 (6 rows) and 9,125.712739 (8 rows) are NOT totals | evidence/dm-interference-reconcile/`

### 6b. What is on the board now, and what to do with it

| board location | what it says now | what it should say |
|---|---|---|
| `AGENT_BOARD.md:527` | ``interference \| 9,125.712739 vs stock 9,134.218881 — 0 rows added, 0 removed, 4 changed (all down)`` | keep the **row-level** reading (it is correct) but label it: *"faired-body variant of the 8-row subset, not the airframe total"* |
| `AGENT_BOARD.md:534-536` | *"Interference basis needs reconciling … one of them is not the airframe total."* | **resolved — replace with §6a.** Both are subsets: A is the 12-row moving-part class measured to 6 rows; B is that class plus the two body↔wing rows. Underlying cause proved: compound-operand booleans (§1c), not a pair-definition dispute |
| `AGENT_BOARD.md:577, :608-609` | `interference 4,631.82 → 1,556.23 mm³`, `pairs 13 → 6`, `volume 4,631.820365 → 1,556.232076` | **the ring-fix set diff is correct** (7 rows removed, 0 added) — keep it, but annotate: `1,556.232076 = 6 of 10 elevon rows; 3 further rows measure 0.000000 only because of the compound boolean` |
| `AGENT_BOARD.md:1061, :1075` | `FAB-READY … Authoritative figure: 10 pairs / 3,305.834869 mm³` | **supersede with §6a.** That figure predates ring v2 (it still carries 2,096.819452 of ring↔body) and predates the body↔wing and static-joint rows entirely |
| `AGENT_BOARD.md:2413, :2416` | `final airframe total 26 pairs / 332,674.0818 mm³` | **stale by construction** — it is the envelope-duplication artefact, already diagnosed at `:2705`; C-28 reproduces its mechanism as the 6 excluded rows |

Nothing on the board was edited by this task: write scope is this evidence directory only. The five rows above
are the exact substitutions, and §6a is the replacement text.

## Appendix: method, tooling, provenance, limits

### A. Instrument and provenance

| item | value |
|---|---|
| interpreter | `C:\Program Files\Python312\python.exe` (Python 3.12) |
| CAD kernel | cadquery 2.7.0 / OCP 7.8.1.1 (OpenCASCADE) — no KiCad, no solver involved |
| volume | `OCP.BRepGProp.VolumeProperties_s(shape, props, 1e-12)` — never `Shape.Volume()` |
| boolean | `OCP.BRepAlgoAPI_Common`, default fuzzy; identity check via `BRepAlgoAPI_Cut` |
| bbox | `OCP.BRepBndLib.AddOptimal_s`, pad 1e-6 mm |
| inputs | 30 STEP files copied from `evidence/dm-ring-redesign/out/` into `work/obj/`; their sha256 are in `out/input_sha256.txt`. The body copy is byte-identical (sha256 `d9ba7aeb7716cdd1ba4f289d…`) to `dm-final-package/out/`, `dm-bearing-rings/out/` and `dm-ring-redesign/out/` |
| write scope | this directory only. No repo write, no commit, no reset, nothing written to `D:\CodeProjects` or `E:\1vm\TMP` |

| script | produced |
|---|---|
| `work/s1_probe.py` → `out/s1_probe.json`, `log/s1_probe.log` | census of all 30 STEPs: solids/shells/faces/volume/bbox/sha256. Found the 5-solid elevon |
| `work/s2_instrument.py` → `out/s2_instrument.json`, `log/s2_instrument.log` | operand algebra + fuzzy sweep + the substituted Ø36 can (instrument calibration) |
| `work/s2b_algebra.py` → `log/s2b_algebra.log` | reproduces cadquery `Shape.intersect` = 593.069028142 and raw `Common` = 585.708362858 on the same two files, and shows the fuse loses 248.0 mm³ |
| `work/s3_closure.py --tag stock` → `out/s3_closure_stock.json`, `log/s3_closure_stock.log` | **the closure sweep**: 32 part groups, 496 pairs, 95 bbox candidates, 34 non-zero rows, 2,317 s |
| `work/s4_validate.py` → `log/s4_validate.log` | reproduces figure A's `0.000000` on `elevon ↔ wing` and decomposes the true value into 2 pieces. Its Monte-Carlo stage was superseded by `s4c` and the run was stopped there, so **no `out/s4_validate.json` exists**; the reproduction and the two piece volumes are in the log |
| `work/s4c_cut.py` → `out/s4c_cut.json`, `log/s4c_cut.log` | independent CUT-identity verification of four row volumes; proves the hinge pin is 100 % buried |
| `work/s4b_mc.py` → (abandoned, `log/s4b_mc.log` empty) | Monte-Carlo point-in-solid route; 6,000 samples had not finished in 8 min on this geometry, so the exact CUT identity replaced it. Kept as a record of the attempt, not as evidence |
| `work/s5_tables.py` | the tables in this report |

### B. Stated limits — what this report does **not** establish

1. **The closure was run on the unfaired body only.** The faired figure in §5b (12,970.279163) is the exact
   4-row delta from `dm-knife-fairing:193-203` subtracted from C-28; the 28-row closure was not re-run on
   `drone-mech_fuselage_rev2_fairing.step` (each `fuselage ↔ wing` row costs ~510 s, ~40 min for the set).
2. **The two beads are code-built** (`r3_final.py:36,71-74`); no STEP was ever written, so their rows are
   reproducible only by re-running the constants. Their four `bead ↔ vane` rows are the one class whose geometry
   I could not cross-check against a second file.
3. **The 6 envelope-on-envelope rows are excluded by a stated rule, not by measurement.** Their volumes are
   published (§2c) so a reader who disagrees can add 200,446.177670 mm³ back and get the same
   `331,033 / 332,674 mm³` class of number the corpus already retired.
4. **C-28 classifies; it does not disposition.** Whether `duct ↔ collar` 512.08 mm³ per side is a bonded joint,
   an oversize collar or a modelling overlap is design authority, and no document in the corpus gives it a fit
   class. Same for `body ↔ wing sector` (7,563.265475). This report does not invent one.
5. **A1 is contingent on the as-called envelope.** The two R3 rows use the repo's Ø42 × 72 envelope. A re-sized
   Ø36 × 70 can changes them sharply: my arithmetic trial (Ø36 × 70 at the R3 station, solid-by-solid) reads
   **387.519984** instead of 628.119864, i.e. **−481.20 mm³** off C-28 → ≈ 12,497.59; `dm-final-package/r1c`
   got **409.833023** for the same idea with its own placement. So C-28's absolute value moves with the motor
   envelope and its *pair count* does not.
6. **Masses are geometric** at 1550 kg/m³ (composite) / 2700 kg/m³ (ring): no layup, ply drop or fastener.

### C. Arithmetic self-check (every identity in this report)

| identity | value | residual |
|---|---:|---:|
| 1,556.232076 + 7,563.265475 + 14.721330 | 9,134.218881 | **0.000000** |
| 9,134.218881 − (4.205053 + 4.205059 + 0.048015 + 0.048015) | 9,125.712739 | **0.000000** |
| 1,556.232076 + 3,075.588289 | 4,631.820365 | **0.000000** |
| 1,556.232076 + 1,123.992062 + 499.500726 + 4.929154 + 84.823002 | 3,269.477020 | **0.000000** |
| A1 3,264.547867 + A2 4.929154 + B 7,563.265475 + C 2,146.042809 | 12,978.785305 | **0.000000** |
| 9,204.320552 + 1,123.992062 + 499.500726 + 4.929154 + 2,146.042809 | 12,978.785304 | 1e-6 (printed-row rounding) |
| 12,978.785305 − 8.506142 | 12,970.279163 | **0.000000** |
| excluded: 4 × 50,033.004601 + 2 × 157.079633 | 200,446.177670 | **0.000000** |

---

**Verdict.** The two contested numbers are not rival measurements of one quantity: **1,556.232076 is 6 rows of a
12-row moving-part class measured with a compound-boolean algebra that returns false zeros**, and
**9,134.218881 / 9,125.712739 are that class plus the two body↔wing rows, on a different algebra and (for the
second) a different body**. The airframe total on the current deliverable is **28 pairs / 12,978.785305 mm³**
(closure basis, `s3_closure_stock.json`), of which the elevon-root cause is **10 pairs / 3,264.547867 mm³** and
ring v2 is **0**. Nothing on the board was edited; §6 gives the exact replacement text.



