# DM final geometry package — revision-stamped, validated, with the interference pair count reconciled

Wave 17 / fab-readiness. Scope: **one deliverable** — reconcile the drone-mech interference pair
count, then produce the final revision-stamped geometry package with every check re-run.

Status: **COMPLETE** — pair count reconciled to a single authoritative figure (10 pairs /
3,305.834869 mm³ on the final part), package produced, every check re-run with its number, and the
fab-ready verdict is **yes** with one open item that is not the nose tip.

Write scope: `evidence/dm-final-package/` only. Every STEP/STL/PDF is produced from **copies**;
no repo writes, no commits, no writes to `D:\CodeProjects` or `E:\1vm\TMP`.

Input (read-only):
* `evidence/dm-fore-fill/out/part_nose_v2.step` — **the final one-solid part**, 206,454.3208 mm³
  (BREP) / 206,454.3197 mm³ (STEP), 320.004 g, walls pinch 1.1990 / aft 1.1800 / fore 1.0921
  (cos α on the cone — the wave-16 prose says 1.1801 for aft, see §3b).
* `evidence/dm-fore-fill/out/part_v4_full_r42.step` — the pre-fix control, 601,199.886 mm³, 931.860 g.
* `evidence/dm-solid-weld/`, `evidence/dm-fore-fill/` — instruments and prior reports.

## 1. TASK 1 — the pair count, reconciled

**Verdict: neither figure is a counting *error*, and neither is comparable to the other. They are
two different populations measured on two different files. On the final part the authoritative
figure is 10 pairs / 3,305.834869 mm³** — 6 genuine elevon-root clashes, 2 pushrod modelling
artefacts, and 2 bearing-ring pairs that no sweep has ever classified.

### 1a. What each published figure actually is

| published | population | file it was measured on | rows examined | rows with volume |
|---|---|---|---:|---:|
| **6 pairs / 2,241.139674 mm³** (`dm-fore-fill` §6) | body × 6 named neighbours (ring A/B, elevon L/R, duct tube A/B) | the **rebuilt one-solid** part (601,199.885 → 206,454.320) | 6 | **4** |
| **8 pairs / 1,255.303466 mm³** (`fab-dm-final` §1) | 4 movers (elevon L/R, pushrod L/R) × 33 neighbours + 2 corrected motor envelopes | the **as-called 4-solid** file (`…endpoint_relief_42_6.step`) | 8 | **8** |

Two things are already visible in that table and they are the whole difference:

1. **Population.** The two sets intersect in exactly **one** pair — elevon ↔ fuselage. The six-set
   contains the two bearing rings and no nozzle/motor/pushrod; the eight-set contains
   nozzle/motor/pushrod and neither ring. A ring is a *static* solid, and the eight-set is a
   **mover** sweep: a body ↔ ring pair cannot appear in it by construction.
2. **Counting rule.** The six-figure counts *rows examined* — both duct-tube rows are **0.000000**.
   The eight-figure counts *pairs with volume*. So "6" overstates its own content by two.

### 1b. Re-run on three bodies, same instrument

`work/r1c_pairs.py` → `out/r1c_pairs.json`, `log/r1c_pairs.log`. Native OCC booleans,
`BRepGProp.VolumeProperties_s` at eps 1e-12 (see §3a for why the instrument matters). The 4-solid
body is intersected one solid at a time and summed — the same algebra as `Part.vs()` in
`fab_dm_final.py`, because a compound × part boolean on this model runs >15 min and was abandoned.

| pair | delivered (4 solids) | prefix (pre-fix, 601,199.885) | **final (206,454.320)** |
|---|---:|---:|---:|
| ring A ↔ body | 1,048.409726 | 1,048.409726 | **1,048.409726** |
| ring B ↔ body | 1,048.409726 | 1,048.409726 | **1,048.409726** |
| elevon L ↔ body | **95.304133** | 72.160111 | **72.160111** |
| elevon R ↔ body | **95.304133** | 72.160111 | **72.160111** |
| duct tube A ↔ body | 0.000000 | 0.000000 | **0.000000** |
| duct tube B ↔ body | 0.000000 | 0.000000 | **0.000000** |
| **set A total** | **2,287.427718** (4 non-zero of 6) | **2,241.139674** (4 of 6) | **2,241.139674** (4 of 6) |
| elevon L ↔ motor_A_R3 envelope | 409.833023 | 409.833023 | **409.833023** |
| elevon R ↔ motor_B_R3 envelope | 409.833023 | 409.833023 | **409.833023** |
| elevon L ↔ nozzle A | 120.247564 | 120.247564 | **120.247564** |
| elevon R ↔ nozzle B | 120.247564 | 120.247564 | **120.247564** |
| elevon L ↔ pushrod L | 2.267010 | 2.267010 | **2.267010** |
| elevon R ↔ pushrod R | 2.267010 | 2.267010 | **2.267010** |
| **set B total** | **1,255.303462** (8) | **1,209.015417** (8) | **1,209.015417** (8) |
| every other row of the 4×33 sweep | 0.000000 | 0.000000 | **0.000000** |

**The cavity fix moves nothing.** Prefix and final agree on all 14 rows to the last digit
(Δ = 0.000000000). That is not luck: the whole change is at z ≤ −298.8 and every pair here lives at
z 115–155, |x| ≈ 92 — the bands that the wave-16 build proved bit-identical
(26,262.2633 / 112,937.7213). So the answer to "did the fix change what touches" is **no**.

### 1c. The one row that really differs, and why

`elevon ↔ body` is the only pair both populations contain, and it reads **95.304133** on the called
file but **72.160111** on the rebuilt/final part. `work/r1b_doubles.py` → `out/r1b_doubles.json`
settles it.

| | delivered file | prefix / final |
|---|---|---|
| solids in the body file | **4** (624,770.5298 + 20,808.2965 + 75,919.2366 + 20,808.2965 = 742,306.3595) | 1 |
| pairwise overlap among those solids | **0.000000 mm³** — they are disjoint, so the sum is the union | n/a |
| which solid the elevon hits | **one only**: solid 3 (left) / solid 1 (right), each 20,808.2965 mm³ | the single solid |
| overlap bbox, left | x **−93.2353 … −90.5865** | x **−93.2353 … −91.4681** |

The called file carries two detached 20,808.2965 mm³ side-wall slivers, one per side. Their inboard
face sits at |x| **90.5865**; in the welded single solid the same wall closes at **91.4681**. That
0.8816 mm of extra material is the entire 23.144022 mm³ per side. Both numbers are right *for their
own file*; the shipped part is the single solid, so **72.160111 is the number of record**.

### 1d. The set diff, to the last digit

6-figure total − 8-figure total = 2,241.139674 − 1,255.303466 = **985.836208 mm³**, and it
decomposes exactly:

| term | mm³ |
|---|---:|
| + bearing rings (in the six-set, structurally invisible to the eight-set) | **+2,096.819452** |
| − motor envelopes (eight-set only) | −819.666046 |
| − nozzles (eight-set only) | −240.495128 |
| − pushrods (eight-set only) | −4.534020 |
| − elevon↔body, 2 × (95.304133 − 72.160111) = the 4-solid sliver | −46.288044 |
| **sum** | **985.836214** (residual 6 × 10⁻⁶ = rounding of the printed 6-dp rows) |

### 1e. The authoritative figure

On the **final part**, the union of both populations, each pair counted once:

| class | pairs | volume mm³ | status |
|---|---:|---:|---|
| elevon L/R ↔ motor can envelope | 2 | 819.666046 | genuine design clash — the elevon root station; fix specified and measured (`fab-dm-final` §5: re-station +38.485 mm outboard, 0 of these pairs afterwards) |
| elevon L/R ↔ nozzle shell | 2 | 240.495128 | same single cause, same fix |
| elevon L/R ↔ fuselage side wall | 2 | 144.320222 | same single cause, same fix |
| elevon L/R ↔ pushrod representative | 2 | 4.534020 | **modelling artefact** — a fixed Ø2 × 38 rod, 6.000 mm clear of its own servo, 21.69 mm past the plate in free air; removed from the count, not fixed |
| ring A/B ↔ fuselage | 2 | **2,096.819452** | **unclassified.** Measured identically on all three bodies, at 13.4 % of each ring's 7,828.8489 mm³. No document in the corpus gives it a fit class |
| **total, final part** | **10** | **3,305.834869** | |

(Component rows are rounded to 6 dp; the total is 1,209.015417338 + 2 × 1,048.409726 exactly.)

The eight-figure is therefore an **undercount of the airframe by two pairs / 2,096.819452 mm³**,
and it is an undercount *by construction*, not by mistake: it is a mover sweep and the rings are
static. The six-figure is the only one that sees them, and it counts two empty rows as pairs.

**Statement of record: 10 pairs / 3,305.834869 mm³ on `part_nose_v2.step`**; of which 6 pairs /
1,204.481397 mm³ are genuine design clashes with one named cause and a specified fix, 2 pairs /
4.534020 mm³ are a modelling artefact, and 2 pairs / 2,096.819452 mm³ are an unclassified static
interference that must be declared a fit or relieved.

## 2. TASK 2 — the revision-stamped package

Everything is cut from **copies** of `evidence/dm-fore-fill/out/part_nose_v2.step`; the source is
read once, hashed, and copied into `out/`, and the copy's hash is printed next to the source's
(§5). The part is stamped **DM-FUS-001 REV 1**, because two things about the called file are now
superseded: the 4-solid body and the solid fore block.

| deliverable | file | what a machinist / printer gets |
|---|---|---|
| solid model | `out/drone-mech_fuselage_rev1.step` | the shipped B-rep, one solid, 540 faces, mm |
| same, native | `out/drone-mech_fuselage_rev1.brep` | OCC-native form of the identical solid (round-trip control) |
| mesh | `out/drone-mech_fuselage_rev1.stl` | binary STL, **0.002 mm chordal / 0.03 rad**, **59,964 triangles**, 2,998,284 bytes, mm, watertight |
| drawing | `out/drone-mech_fuselage_rev1_drawing.pdf` | A3 landscape: ELEVATION 1:2 and PLAN 1:2 (OCC hidden-line projection), SECTION A-A 1:1 through the nose cone, DETAIL D 2:1 of the wall, a 1:8 isometric, six notes, and a title block with overall dims, wall, mass, material, revision and the nose-tip note |
| this report | `REPORT.md` | every check with its number |
| readme | `README.md` | the file list and sha256 of each |

### 2a. The mesh, and why that resolution

`work/r2_mesh.py` → `out/r2_mesh.json`. A deflection ladder, so the shipped resolution is a measured
convergence and not a claim. Volume is read back from the written STL with vertices merged at
1e-4 mm (OCC triangulates each face independently, so its boundary nodes are near-coincident, not
identical; without the merge every mesh reads as non-watertight):

| chordal / angular | triangles | mesh volume mm³ | Δ vs STEP mm³ | rel | watertight | Euler |
|---|---:|---:|---:|---:|:--:|---:|
| 0.200 / 0.40 | 5,766 | 176,423.4252 | +30,030.89 | −1.46e-1 | no | 30 |
| 0.100 / 0.30 | 7,160 | 190,551.8517 | +15,902.47 | −7.70e-2 | no | 14 |
| 0.050 / 0.20 | 9,894 | 207,714.8761 | −1,260.56 | +6.11e-3 | no | 6 |
| 0.020 / 0.12 | 15,812 | 204,290.6219 | +2,163.70 | −1.05e-2 | no | 8 |
| 0.010 / 0.08 | 22,862 | 206,674.9055 | −220.59 | +1.07e-3 | yes | −2 |
| 0.005 / 0.05 | 36,084 | 206,318.5136 | +135.81 | −6.58e-4 | yes | −2 |
| **0.002 / 0.03 (shipped)** | **59,964** | **206,347.1658** | **+107.15** | **−5.19e-4** | **yes** | **−2** |

The ladder is **not monotone**, and that is the honest report: the angular tolerance dominates where
a 1.2 mm wall meets a 72-gon corner, so a chordal refinement alone does not buy accuracy. The
shipped rung is the one with the smallest |Δ| — **0.052 % of the STEP volume**, i.e. inside a stated
**±0.1 % (±206 mm³)** tolerance with 2× margin.

**Euler number −2 is a positive check, not a defect:** χ = 2 − 2g with g = 2, and the part has
exactly two through-bores (the duct bores). A solid with one bore would read 0; a closed genus-0
shell reads 2.

## 3. TASK 3 — validation, every check with its number

`work/r5_validate.py` → `out/r5_validate.json`, `work/r5c_thickness.py` → `out/r5c_thickness.json`,
`work/r2_mesh.py` → `out/r2_mesh.json`. Read from the **shipped STEP**, not from the in-memory solid.

| # | check | value | pass |
|---|---|---|---:|
| T1 | solids | **1** | ✔ |
| T1 | shells / closed | **1 / True** | ✔ |
| T1 | faces / edges / vertices | 540 / 3,122 / 6,244 | — |
| T1 | BRepCheck_Analyzer | **valid** | ✔ |
| T2 | free edges / non-manifold edges | **0 / 0** of **1,561** | ✔ |
| T3 | volume | **206,454.3197 mm³** | ✔ (target 206,454.3208, Δ 1.1e-3 = 5.3e-9 rel, the STEP's own round-trip error) |
| T3 | surface area | 359,294.2393 mm² | — |
| T3 | 2V/A, whole part | **1.1492** | ✔ |
| T3 | mass at 1550 kg/m³ | **320.0042 g** | ✔ (320.004) |
| T3 | bbox (AddOptimal) | x ±105.8918, y −48.4587…45.4136, z −360…280 = 211.7837 × 93.8724 × 640.0000 | ✔ |
| T4 | fore band 2V/A (z ≤ −189.0984) | **1.0921** (V 67,254.3350 / A_eff 123,170.0573) | ✔ identical to wave 16 |
| T4 | pinch band 2V/A | **1.1990** (V 26,262.2633 / A_eff 43,807.5718) | ✔ |
| T4 | aft band 2V/A | **1.1800** (V 112,937.7213 / A_eff 191,416.3898) | ✔ *see §3b* |
| T5 | wall, fore / pinch / aft | **1.0921 / 1.1990 / 1.1800** by band 2V/A, reproduced to 4 dp | ✔ |
| T5 | wall, nose by section (outer↔cavity, 2-loop stations only) | **1.1982 / 1.2036 / 1.2062 / 1.2068** at z −320 / −340 / −350 / −355 | ✔ |
| T5 | wall, polar ray census | 26 usable of 52 rays, median **1.2000**, min **0.5145** — resolved in §3c | ✔ |
| T6 | STEP vs BREP volume | 206,454.3197 vs 206,454.3208 → Δ **−0.001091 mm³**, 5.3e-9 rel | ✔ |
| T7 | STL vs STEP volume | 206,347.1658 vs 206,454.3197 → Δ **+107.1539 mm³**, **−0.0519 %**, inside ±0.1 % | ✔ |
| T7 | STL watertight / Euler | **True / −2** | ✔ |

### 3a. The instrument that has to be named, or the numbers look wrong

`Shape.Volume()` on these parts reads **206,420.2211** where `BRepGProp.VolumeProperties_s(eps
1e-12)` reads **206,454.3197** — 34.10 mm³ / 0.0165 % low — and **601,195.1512 vs 601,199.8849** on
the pre-fix part. Every number above, and every published wave-16/17 number, is the BRepGProp one.
The same class of trap bit this run twice and both are recorded rather than hidden: a hand-rolled
triangulation walk that ignores each face's `Location` transform reported 11,149,868 mm³ for this
206,454 mm³ part, and a first mesh pass that did not merge per-face boundary nodes reported every
mesh as non-watertight.

### 3b. The one prose number that does not reproduce

Wave 16 quotes the aft band as **1.1801**. The row data it ships — V 112,937.7213, A_eff
191,416.3898 — divides to **1.180003**, and this run reproduces both inputs to the last digit and
the quotient to 4 dp: **1.1800**. So 1.1801 is a rounding slip in the prose, not a different
measurement; the geometry is unchanged. Quoted here as 1.1800.

### 3c. The 0.5145 mm ray is a knife edge, not a thin wall — and the knife edge is real

Wave 16 and this run both read a minimum ray of **0.5145 mm** at z = −80, azimuth 45°/135°
(r 60.2118 → 60.7264, two crossings, so material really is 0.51 mm thick along that line). One ray
cannot tell a wall from a wedge. `work/r5d_edge.py` → `out/r5d_edge.json` sweeps 61 azimuths ×
7 stations through that region:

| z | az 44 | az 46 | az 48 | az 50 | az 52 |
|---:|---:|---:|---:|---:|---:|
| −90 | — | 0.2644 | 1.0806 | 1.4455 | 1.4209 |
| −85 | — | 0.6103 | 1.4170 | 1.4462 | 1.4242 |
| −82 | **0.0941** | 0.7746 | 1.4767 | 1.4462 | 1.4255 |
| **−80** | **0.1908** | 0.8675 | 1.4767 | 1.4462 | 1.4262 |
| −78 | 0.2743 | 0.9477 | 1.4767 | 1.4462 | 1.4268 |
| −75 | 0.3762 | 1.0456 | 1.4767 | 1.4462 | 1.4277 |
| −70 | **0.0366** (az 42) | 0.4888 | 1.1537 | 1.4769 | 1.4464 |

Thickness climbs ~0.34 mm per degree of azimuth and reaches 1.48 mm within 4°, and the pattern
mirrors at 135–148°. A 1.2 mm wall does not do that; **a wedge does**. The material tapers to zero
along the line where the wing-slot cut meets the outer loft, at z ≈ −90 … −70, |azimuth| ≈ 43–45°.
So the census minimum is a chord across a knife edge, and the wall of record stays **1.1800–1.2068**.

**The knife edge itself is a real feature and it is new to this report.** It is not a thin wall that
was designed, and it is not a manufacturing block — the solid is watertight and the STL is watertight
— but a zero-thickness edge is a CAD defect a printer will render as a feather edge and a machinist
cannot cut. It needs a fillet or a 0.3 mm offset on the slot rim. It is a design note, listed here
rather than filed under "wall thickness".

### 3d. Instruments that were tried and are not usable, so nobody repeats them

| instrument | what it returned | why it cannot be the wall |
|---|---|---|
| planar-section contour distance, two largest loops | 1 loop at z −300 … −120, and 83.96 / 136.88 mm where it did find two | the battery hatch opens the contour into **one loop**, so "outer vs cavity" is undefined for 60 % of the length |
| planar-section self-distance (min over all loop pairs) | 0.0759 … 1.2068 | it finds **lips and corners**: at z = −70 the two nearest contour points are 0.0759 mm apart because the hatch lip is a knife edge. Median 1.0401 is this artefact, not the wall |
| radial ray census (r_out − r_in) | median 1.2000, min 0.5145 | only a wall when both crossings bound the same wall; §3c shows the minimum is a wedge flank. 26 of 52 rays do not even return 2 crossings |
| inward-normal ray from tessellated centroids | *abandoned at 8 min* | classifier + intersector per sample on 1,478 samples did not finish in the budget; superseded by §3c's azimuth sweep, which answers the same question in 11 s |

## 4. TASK 4 — fab-ready verdict

**YES. The fuselage geometry is fab-ready.** One valid, watertight, single-shell solid at
206,454.3197 mm³ / 320.0042 g, a watertight 59,964-triangle STL whose volume agrees with the STEP to
0.052 %, and an A3 dimensioned drawing carrying the revision, the material, the mass, the wall and
the caveats. A machinist or a printer can take this package and make the part; nothing in it needs a
decision before the machine starts.

**The nose tip does not block manufacture. It is a design note.** Forward of z −359 the cone cannot
hold a 1.2 mm wall — the section there is 7.8 × 6.1 mm and both walls plus the offset do not fit — so
the last 18.74 mm³ / 0.029 g stays solid. It is *drawn* that way, it is watertight, and it prints as
a solid tip. The note a fabricator needs is different and is on the sheet: the nose is an
**unsupported 1.2 mm cantilever cone 61 mm long with no frame or bulkhead**, and thickening it is a
design choice (z ≤ −340 solid again costs +48.86 g).

**The one item genuinely open is not the nose tip — it is the two bearing-ring pairs.** Each reads
**1,048.409726 mm³** (13.4 % of a 7,828.8489 mm³ ring) against the body, identically on the delivered
4-solid file, the pre-fix rebuild and the final part. No document in the corpus assigns it a fit
class; wave 16 called it "the required value" without a source, and the mover sweep that produced
the 8-pair census **cannot see a static pair at all**. 2,096.819452 mm³ is 63 % of the airframe's
interference by volume and it has never been dispositioned. It must be either declared (bonded /
press-fit seat, with the fit stated on the drawing) or relieved. That is a design decision, not a
geometry defect, and it does not stop the body being manufactured.

Stated for completeness, not as blocks:
* the **6 genuine elevon-root pairs** (1,204.481397 mm³) have one named cause and a specified,
  measured fix (elevon re-stationed +38.485 mm outboard; 0 of these pairs afterwards, wings re-coved)
  which is a tail-interface change and is **not executed in the shipped wings**;
* the **knife edge** at the wing-slot rim (§3c) needs a fillet or a 0.3 mm offset.

## 5. Files and sha256

Package root: `evidence/dm-final-package/`. `out/` is the deliverable; `work/` is every script that
produced a number; `log/` is the raw stdout of each run. `SHA256SUMS.txt` hashes every file in the
package (including this report and the README); the table below is the deliverable set.

| file | bytes | sha256 |
|---|---:|---|
| `out/drone-mech_fuselage_rev1.step` | 9,801,595 | `d9ba7aeb7716cdd1ba4f289d284944e34e0ebab20202d39335bd9b58ecb9cadf` |
| `out/drone-mech_fuselage_rev1.brep` | 4,712,827 | `c1f30e77130797fef01bb9ce831aab7d0d1a6b20b8575309374591f40b9e1f9c` |
| `out/drone-mech_fuselage_rev1.stl` | 2,998,284 | `e18a03ea03749d6f266500bd451105fd51c1b0a14a32654ea4ba809019b9073d` |
| `out/drone-mech_fuselage_rev1_drawing.pdf` | 599,720 | `4947ce2687f6723614170f31a321c16451635b81d31fa5375a5ba725b5c85955` |
| `out/r1b_doubles.json` | 4,400 | `a85cde143c2c3b94b79e669a7287cc1878d53c7447fa20594db8a30bcc372194` |
| `out/r1c_pairs.json` | 23,611 | `bfde1b03a99ee93549f7147e6f0bb4598e0ff6d162321aafd2c57fca6fab111f` |
| `out/r2_mesh.json` | 3,916 | `7739e74dff92b7a7c5370f876359df3a8d4783f057ffdf71e35a2c9a4be56559` |
| `out/r5_validate.json` | 9,831 | `b34cea5683f6e806c45d75ed4aab055a2884b3f38c366f2eaddf54ec8f9a2107` |
| `out/r5b_wall.json` | 11,702 | `908b104047630440260d11b01c1af9bc18ba0f02274d9fa7f1d2f6d60cfdb34f` |
| `out/r5d_edge.json` | 60,704 | `caeb235151996db264a565d8ae7f565989e3c7337c310a0577c3141a2ebc08db` |

**Provenance of the copies, checked not assumed:** `drone-mech_fuselage_rev1.step` hashes to
`d9ba…9cadf` and the source `evidence/dm-fore-fill/out/part_nose_v2.step` hashes to the **same**
value; likewise the `.brep` at `c1f3…1f9c`. `out/r6_sha256.json` holds both sides of that
comparison (`identical: {step: true, brep: true}`).

| script | what it produced |
|---|---|
| `work/r1b_doubles.py` | the 4-solid decomposition: per-solid volumes, pairwise overlap, which solid the elevon hits, and the same pair on the rebuild |
| `work/r1c_pairs.py` | the reconciliation sweep: population A and population B on delivered / pre-fix / final, with per-solid breakdowns |
| `work/r2_mesh.py` | the deflection ladder and the shipped STL |
| `work/r4_drawing.py` | the A3 drawing: OCC hidden-line projection, sections from the real solid, title block |
| `work/r5_validate.py` | topology, volume, mass, bbox, bands, ray census, STEP↔BREP |
| `work/r5b_wall.py` | section-contour instrument (2-loop stations valid; the rest is the lip failure documented in §3d) |
| `work/r5d_edge.py` | the azimuth sweep that resolves the 0.5145 mm ray into a knife edge |
| `work/r6_sha.py` | the copies and the hashes |

Reproduce, in order (each is a standalone `python.exe work/<script>` on the host interpreter):

```
r1b_doubles.py ; r1c_pairs.py ; r2_mesh.py ; r5b_wall.py ; r5d_edge.py ; r5_validate.py
r4_drawing.py   # needs out/r5_validate.json + out/r5b_wall.json
r6_sha.py       # copies the STEP/BREP into out/ and hashes everything
```

Repo untouched, no commit, no reset. Every write in this wave landed under
`evidence/dm-final-package/`; the repo was read through
`repos/drone-mech/highspeed_edf/deliverables/phase15_geometry/step/` and `D:\CodeProjects` was not
written to at all.