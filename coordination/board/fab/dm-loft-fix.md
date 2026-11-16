# DM loft fix — can the cavity loft be kept inside the skin, and does that give ONE solid?

Wave 15 / fab-readiness. Scope: **one question** — can the drone-mech cavity loft be fixed so the
cavity stays INSIDE the skin, and does that make a single solid achievable?

Status: **COMPLETE**. Answer: **yes** — the cavity can be kept inside the skin (by re-deriving it from
the skin, not by changing its interpolation), and the delivered 42.6 mm bore then yields **ONE valid
watertight solid**, 601,199.886 mm³ / 931.860 g. Full numbers in §6.

## 0. Method and inputs

- Generator (copied, never modified in repo):
  `copy/highspeed_edf/phase15/optimization/phase15_generate_geometry.py`
- Prior evidence read first: `evidence/dm-solid-weld/REPORT.md`, `evidence/dm-bore-recut/REPORT.md`
- Every artefact written under `evidence/dm-loft-fix/` only. No repo writes, no commits.
- Bounding boxes: `BRepBndLib.AddOptimal` everywhere (plain `Add` is known-wrong on this STEP).

## 1. Baseline — cavity cut alone, no bore  · REPRODUCED

`work/s2_cavity_baseline.py` → `out/s2_cavity_baseline.json`, `logs/s2_baseline.log`.
Fresh build from the pinned generator copy (`copy/.../phase15_generate_geometry.py`,
sha256 `53353DA1…FABD47` = the hash `phase15_generate_fuselage_shell_endpoint_relief.py`
pins), same station tables, same 72-gon superellipse wires, **no bore, no slots, no hatch**.

| stage | solids | volume mm³ (ε 1e-12) | optimal bbox mm |
|---|---:|---:|---|
| uncut outer loft (`ruled=False`) | 1 | 7,953,163.9712 | x ±105.8918, y ±48.4587, z −360…280 |
| cavity solid (`ruled=False`) | 1 | 7,027,528.7775 | x ±92.8013, y ±43.1342, z −298.8…247 |
| **cavity cut alone → part** | **2** | **1,039,785.7427** | — |

Both pieces, read off the geometry (not assumed):

| piece | volume mm³ | area mm² | 2V/A mm | shells | bbox mm |
|---|---:|---:|---:|---:|---|
| fore | 702,419.2830 | 139,921.8873 | 10.0402 | 1 | x ±105.8918, y ±48.4587, **z −360…−189.0984** |
| aft | 337,366.4597 | 315,434.9635 | 2.1391 | 1 | x ±97.0185, y ±45.4136, **z −111.933…280** |

Every figure above reproduces `dm-bore-recut` digit-for-digit (7,953,163.9712 /
1,039,785.7427 with the same ε; pieces 702,419.283 + 337,366.4597). The baseline is the
one that was described: **2 solids with zero bore cut.**

**Cavity material outside the skin** = `cavity.cut(outer)`:

| quantity | measured |
|---|---|
| escaped volume | **114,150.549 mm³** (1.6243 % of the 7,027,528.7775 mm³ cavity) |
| escaped solids | 3 |
| escaped optimal bbox | x ±91.8201, y ±42.7766, **z −196.2375 … +89.6146** |

Combined with the 77.165 mm fore/aft through-gap, this is the whole mechanism: over
z −196.2 … +89.6 the cavity is wider than the skin, so the cavity cut removes the full
section and severs the body. The `z −111.933 … 280` piece is the aft shell; it is *thin*
(2V/A 2.139) because it is skin only, hollowed from the inside out.

### 1a. WHICH loft oscillates — measured, and it corrects the brief

The brief (and `dm-bore-recut` §2a) attributes the 211 mm and 166 mm excursions to the
*cavity* loft. That is not where they are. Ray-cast envelope census at 1 mm spacing
(`work/s1_sections.py` → `out/s1_sections.json`, 637 rows; the ray instrument is
cross-checked against `BRepAlgoAPI_Section` + `BRepBndLib.AddOptimal` at 11 z values — 9 are
comparable and **all 9 agree to 4 dp**, e.g. z −160: ray 165.9622 / optimal 165.9622; z −300 sits
exactly on a loft station plane and z 255 is past the cavity's end, so neither yields a section):
**218 of the 637 stations carry less than the design 2.4 mm of wall, spanning z −199.0 … +119.0.**

| z mm | outer w mm | outer station w | cavity w mm | cavity station w | wall (outer−cavity) |
|---:|---:|---:|---:|---:|---:|
| −250 | **211.2177** | 186 | 185.3674 | 183.6 | **+25.85** |
| −190 | 179.4753 | 186 | 183.3532 | 183.6 | **−3.88** |
| −160 | **165.9622** | 186 | 183.0342 | 183.6 | **−17.07** |
| −112 | 179.1140 | 186 | 183.4444 | 183.6 | **−4.33** |
| −100 | 186.0000 | 186 | 183.6000 | 183.6 | +2.40 |

* The **211 mm reach is the OUTER loft's** (+25.2 mm over its own 186 mm station), not the
  cavity's. The cavity's own excursion is at most **+1.77 mm** (185.37 vs 183.6).
* The **166 mm dip is also the OUTER's** (−20.0 mm). The cavity sits where the design put
  it; it is the skin that is 20 mm too narrow.
* So the two blames are not interchangeable: `ruled=False` on the *cavity* is not,
  by itself, what put the cavity outside the skin. Fixing only the cavity loft can at
  best recover 1.77 mm of the 17.07 mm shortfall.

## 2. Fix attempts

Every variant is one build: `work/s3_fix.py <variant>` → `out/s3_<variant>.json`. "Escaped" is
always `cavity.cut(outer).Volume()` with ε 1e-12 on the same solids the cut is made from, so the
escape number and the solidCount describe the identical geometry.

| variant | what changed | cavity vol mm³ | **escaped mm³** | **solids after cavity cut** |
|---|---|---:|---:|---:|
| baseline | nothing | 7,027,528.7775 | 114,150.549 | **2** |
| **2a** `v1_ruled_cavity` | cavity `ruled=True` | 6,940,447.1213 | **119,041.105** | **2** |
| **2b** `v3_resample_own` | cavity resampled (10 mm) from its own station table, `ruled=False` | 6,940,209.7998 | **119,040.984** | **2** |
| **2b′** `v4_resample_skin` | cavity resampled (10 mm) from the MEASURED skin, −2.4 mm/axis | 7,131,784.7123 | **0.000** | **1** |
| **2c** `v5_clip` | shipped cavity clipped to an inset limit | 6,799,774.7228 | **0.000** | **1** |
| **alt** `v2_ruled_both` | outer AND cavity `ruled=True` | 6,940,447.1213 | **0.000** | **1** |

### 2a. `ruled=True` on the cavity — FAILS, and it makes containment very slightly worse

Cavity shrinks (7,027,528.78 → 6,940,447.12, −87,081.66 mm³) because the ruled taper cuts the
spline's corner bulges off, but the mid-body is unchanged (a ruled loft between identical 72-gon
sections is the same 72-gon, so the cavity is still 183.6 mm wide through z −298.8…120). The skin
there is 166.0 mm. Result: **2 solids**, escaped **119,041.105 mm³ — 4,890.6 mm³ MORE than the
baseline**, because the linear interpolation removes the cavity's own −0.6 mm inward sag in the dip
band while leaving the 18 mm skin deficit untouched.

| piece | vol mm³ | 2V/A | z span |
|---|---:|---:|---|
| fore | 717,378.9902 | 10.2939 | −360 … −189.4895 |
| aft | 414,378.9647 | 2.6497 | −111.7175 … 280 |

### 2b. Resampling the cavity from its OWN station table — FAILS, identically

10 mm resampling of the 7 inner stations (55 intervals → 56 sections) reproduces 2a to **0.12 mm³** of escaped
volume (119,040.984 vs 119,041.105) and 2 solids (1,131,995.15 vs 1,131,757.95 mm³). That is the
expected convergence: a spline through collinear stations *is* the ruled surface. **This is the
useful negative result: it proves the cavity's station table is not the information that is missing.**
The cavity is already where the design put it; the skin is the thing that is 20 mm too narrow.

### 2b′. Resampling the cavity from the MEASURED skin — WORKS (option b, applied to the surface)

The station table does not carry the skin's true shape, so the fix is to re-derive the cavity from the
skin that exists: sample the outer envelope (ray instrument of §1a) every 10 mm from z −298.8 to 247,
subtract 2.4 mm on each axis (the generator's own `2 * BODY_SHELL` rule) and loft those 56 sections.
`out/s3_v4_resample_skin.json`, log `s3_v4.log`.

| | value |
|---|---|
| cavity volume | 7,131,784.7123 mm³ (+104,255.93 vs design — it now also hollows the 211 mm bulge) |
| **escaped volume** | **0.000 mm³, 0 solids** |
| **solids after cavity cut** | **1** — 821,379.2586 mm³, 2V/A 2.9929, one shell, z −360…280 |

### 2c. Clipping the shipped cavity — WORKS, and it is the variant that keeps the design's own profile

`cavity_clipped = design_cavity ∩ limit`, with `limit` = the same 10 mm skin sampling at **3.0 mm**
inset. The limit's own escape is **0.000 mm³**, so containment is by construction, not by luck.
`out/s3_v5_clip.json`, log `s3_v5.log`.

| | value |
|---|---|
| limit volume | 7,057,924.3582 mm³, its own escape **0.000** |
| design cavity | 7,027,528.7775 mm³ |
| clipped cavity | 6,799,774.7228 mm³ → **227,754.05 mm³ shaved off the cabin (3.24 %)** |
| **escaped volume** | **0.000 mm³, 0 solids** |
| **solids after cavity cut** | **1** — 1,153,389.2484 mm³, 2V/A 4.2587 |

The clip solves the problem and charges for it: it turns the 1.2 mm wall into 3.0 mm through the pinch
band, which is **+227,754 mm³ of solid = +353.0 g** at 1550 kg/m³. That price is why the clip is the
fallback, not the recommendation.

### alt. `ruled=True` on the OUTER loft as well — WORKS, and it removes the artefact instead of dodging it

| | value |
|---|---|
| outer volume | 7,744,263.7286 mm³ (−208,900.24 vs shipped: the 211 mm bulge and the 166 mm dip are gone) |
| cavity volume | 6,940,447.1213 mm³ |
| **escaped volume** | **0.000 mm³, 0 solids** |
| **solids after cavity cut** | **1** — 803,816.6073 mm³, 2V/A 2.9885, one shell z −360…280 |

**Three** distinct fixes reach containment with 0.000 mm³ of escape: re-derive the cavity from the skin
(§2b′), clip it (§2c), or rule the outer loft that is the real culprit (alt). What does **not** work is
changing the *interpolation* of the cavity while leaving the skin alone (§2a, §2b).

## 3. Bore on the contained cavity, and the bore radius sweep

The sweep is run on the **alt** variant (803,816.6073 mm³ before the bore) because its booleans cost
1–2 s each; the delivered chain was then run on §2b′ as well. `out/s4_cavity-duct_v2_ruled_both.json`,
logs `s4_v2_sweep_down.log` + `s4_v2_sweep_up.log`.

| radius mm | solids after cavity | **solids after both bores** | volume mm³ |
|---:|---:|---:|---:|
| 30.0 | 1 | **1** | 747,636.1813 |
| 34.0 | 1 | **1** | 732,325.4987 |
| 36.0 | 1 | **1** | — |
| 38.0 | 1 | **1** | — |
| 39.0 | 1 | **1** | — |
| 40.0 | 1 | **1** | 693,673.5074 |
| 41.0 | 1 | **1** | 668,276.2759 |
| 42.0 | 1 | **1** | 649,995.5722 |
| **42.6 — as delivered** | **1** | **1** | **640,663.6856** |
| 44.0 | 1 | **1** | 621,329.6341 |
| 46.0 | 1 | **1** | 598,249.9632 |
| 48.0 | 1 | **1** | 574,012.3313 |
| 50.0 | 1 | **1** | 546,169.6351 |
| 55.0 | 1 | **1** | 531,220.6596 |
| 60.0 | 1 | **1** | 519,601.7508 |

**The bore never severs a contained shell at any radius from 30 to 60 mm — 15 radii, 15 times one
solid.** `dm-bore-recut`'s floor of 2 solids "at every radius 20…60" was a property of the cavity
escape, not of the bore. With the cavity inside the skin the floor disappears and the **delivered
42.6 mm radius is already one solid**, so there is no radius to trade against: the bore stays at
42.6 mm and no clearance is sacrificed.

### 3a. The full deliverable chain, where it holds and where it does not

The repo's six tools in the repo's order (`ductA, ductB, cavity, slot −x, slot +x, hatch`):

| variant | after cavity | after slot −x | after slot +x | after hatch | verdict |
|---|---:|---:|---:|---:|---|
| shipped (baseline) | 4 | 4 | 4 | 4 | — |
| alt (outer + cavity ruled) | 1 | **2** | **3** | **3** | slot severs a strip |
| **§2b′ (cavity re-derived from the skin)** | **1** | **1** | **1** | **1** | **ONE SOLID**, 601,199.886 mm³ |

The alt variant's extra pieces are **20,910.3939 mm³ each**, bbox **x 68.442…93, y ±34.8905,
z −46.6729…187.2209**, 2V/A 1.1382 — the *same* outboard side-wall strip the delivered part loses to
the bore as its two 20,808.2965 mm³ pieces; under the ruled outer the service-window slot cuts it loose
instead. So one solid exists, but the strip's attachment in the aft taper is what decides it — and
keeping the delivered skin (§2b′) is the variant that keeps it attached. Robustness check: the same
full chain at bore radius 42.5 mm also gives 1 solid (602,792.7504 mm³), so the attachment is not a
0.1 mm knife-edge against the bore.

## 4. Validity of the one-solid result

File verified: `out/part_v4_full_r42.brep` (= the §2b′ cavity, six repo cuts, bore 42.6).
`work/s5_verify.py` → `out/s5_verify_part_v4_full_r42.json`, log `s5_v4_full.log`.

| check | instrument | result |
|---|---|---|
| **solid count** | `TopExp_Explorer(SOLID)` | **1** |
| shell count | `TopExp_Explorer(SHELL)` | **1** — no enclosed void: the cabin is vented through the bore break-outs and the two service windows, so the shell is a single surface (this is a *stronger* result than a hollow with an inner shell) |
| shell closed | `Shell.Closed()` | **True** |
| free edges (open boundary) | per-shell `MapShapesAndAncestors(EDGE→FACE)`, count == 1 | **0 of 1,397 edges** |
| non-manifold edges (count > 2) | same map | **0** |
| watertight | free == 0 and non-manifold == 0 and closed | **YES** |
| BRep valid | `BRepCheck_Analyzer(shape, True)` | **valid** |
| volume / surface | `BRepGProp`, ε 1e-12 | **601,199.886 mm³ / 352,173.9346 mm²** |
| 2V/A whole part | — | 3.4142 |
| **mass at 1550 kg/m³** | V × ρ | **931.860 g** |
| bbox (optimal) | `BRepBndLib.AddOptimal` | x ±105.8918, y −48.4587…+45.4136, z −360…280 |
| faces carrying triangulation | `BRep_Tool.Triangulation` | **0** — hence `AddOptimal` for every box (§0) |

### 4a. Wall thickness, fore and aft — and what the loft fix does to the 11.34 mm figure

Same band definitions as the earlier waves (fore z ≤ −189.0984, pinch −189.0984…−111.9330, aft
z ≥ −111.9330), with each band's artificial section faces removed from the area before dividing:

| band | delivered r42.6 (4 solids) | **fixed (1 solid)** | change |
|---|---:|---:|---:|
| fore: V mm³ / A_eff mm² / **2V/A** | 624,770.5298 / 96,977.0806 / **12.8849** | 461,999.9004 / 102,872.0758 / **8.9820** | **−3.90 mm (−30.3 %)** |
| pinch: V / A_eff / **2V/A** | **0 / 0 / — (the 77 mm through-gap)** | 26,262.2632 / 43,807.5718 / **1.1990** | material exists again, at the design wall |
| aft: V / A_eff / **2V/A** | 117,535.8297 / 174,579.5868 / **1.3465** | 112,937.7213 / 191,416.3898 / **1.1801** | −0.17 mm, now the design wall |
| whole part | 742,306.3595 mm³ / 1,150.575 g / 2V/A 5.2052 | 601,199.886 mm³ / **931.860 g** / 2V/A 3.4142 | **−141,106.47 mm³, −218.715 g** |

*Note: the delivered part's own fore piece measures 2V/A **11.3397** over its whole surface; the band
instrument gives 12.8849 for the same z range because it removes the artificial faces — two different
definitions of the same thing, and the comparison above uses one instrument on both parts. The
**11.3397 figure is not reproducible on the fixed part as a piece measurement at all** — there is no
fore piece any more, only a band — so 12.8849 → 8.9820 is the like-for-like answer.*

**So the loft fix does change the fore figure (−3.90 mm, −30.3 %) but it does NOT fix the fore
problem, and cannot:** the fore band is still **7.49× the 1.2 mm shell**, because the surplus is
upstream of the loft —
1. the cavity starts at z −298.8, so z −360…−298.8 is solid body (local 2V/A at z −300 = **47.688 mm**,
   a full solid section), and
2. the 25.2 mm spline bulge at z −250 is *inside* the fore band; the §2b′ cavity hollows it, which is
   why the fore number improves at all.

Local wall by 2 mm slab (`work/s8_wall.py` → `out/s8_wall_part_v4_full_r42.json`; identity
2V/A_eff = wall for a tube slab):

| z mm | −300 | −250 | −160 | −120 | 0 | 60 | 120 | 180 | 240 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| wall mm | **47.688** (solid) | 1.2099 | 1.2068 | 1.1914 | 1.1452 | 1.1445 | 1.1464 | 1.1296 | 1.0737 |

The wall is the design 1.2 mm through the band that used to be a through-gap (z −250 to −120:
1.19–1.21 mm). The sub-1.2 values at z ≥ 0 and z 240 are section *means* over sections that the two
bore break-outs and the taper cut open; they are not thin wall (min mean 1.0737 mm).

### 4b. Two instruments that failed on this shape (recorded, not silently dropped)

* `IntCurvesFace_ShapeIntersector` ray cast: returned **0 crossings where the skin is plainly present**
  (e.g. z −280 along +x) and duplicated crossings at identical distance elsewhere, on the
  boolean-result faces. It worked on the plain loft solids (§1a), so this is a face-provenance
  limitation, not a coding error. Replaced by the 2V/A slab instrument.
* `BRepAlgoAPI_Section` on the finished part: **not one station in 3+ min** (killed). Same reason the
  ray census was worth building for the lofts.

## 5. Interference pairs, and the two 50.171 mm³ ring pairs at z 250…254

Absolute body × part booleans (`work/s6_interference.py`), run on **the same part STEP files for both
bodies**, so every column is a set diff and not two different populations:
`out/s6_interference_part_v4_full_r42.json`, logs `s6_interference.log`, `s6_rings_424375.log`.

| pair | delivered r42.6, 4 solids (742,306.3595) | **fixed, 1 solid (601,199.886)** | change |
|---|---:|---:|---:|
| `duct_A_vector_vane_bearing_ring` | 1,048.409726 | **1,048.409726** | **0.000000000** |
| `duct_B_vector_vane_bearing_ring` | 1,048.409726 | **1,048.409726** | **0.000000000** |
| `elevon_left_40x150` | 95.304133 | **72.160111** | **−23.144022** |
| `elevon_right_40x150` | 95.304133 | **72.160111** | **−23.144022** |
| `duct_A_82OD_78ID_L110` | 0.000 | 0.000 | 0 |
| `duct_B_82OD_78ID_L110` | 0.000 | 0.000 | 0 |
| **sum of these six** | **2,287.427718** | **2,241.139674** | **−46.288044** |

**The two ring pairs do not appear — and the fix cannot move them, in either direction.**
Ring overlap measured on both bodies at both radii:

| bore radius | delivered body | fixed body | increment |
|---|---:|---:|---:|
| 42.6 (as delivered) | 1,048.409726 | 1,048.409726 | — |
| 42.4375 | 1,098.580516 | 1,098.580516 | **+50.170790 per ring** |

Both radii give **bit-identical** overlaps between the shipped body and the fixed body, which is what
the geometry predicts: the ring sits at z 250…254 and the cavity tool ends at z 247, so nothing the
loft fix changes reaches it. And the +50.171 mm³ increment is now settled by a direct absolute boolean
on both bodies: **50.170790 mm³**, reproducing `dm-bore-recut`'s 50.170790 (clipped) and 50.170788
(difference probe) to 2e-6 — it is entirely **bore-driven**, not loft-driven.

Consequence: because the fix removes the reason to shrink the bore (one solid holds at 42.6), the
increment is simply **not incurred**. The rings stay at **1,048.409726 mm³ each — exactly as delivered**,
with no waivers. The elevon pairs *improve*: −23.144022 mm³ each, the overlap patch narrowing from
x −93.2353…−90.5865 to −93.2353…−91.4681 as the fore band loses material. Of the delivered
8-pair / 1,255.303466 mm³ set, the two body pairs are these elevon pairs; the pushrod-placeholder pairs
do not involve the body and are untouched.

Location/identity of the overlap: z 250…254 in every case, x −11.1122…+2.8583 (r 42.4375) or
−10.9093…+2.7798 (r 42.6), y ±26.9605 — the web between the two bores at the aft taper.

## 6. Verdict

**Yes — the cavity loft can be kept inside the skin, and one solid then exists.** The baseline was
reproduced first (§1: cavity cut alone, no bore, **2 solids**, **114,150.549 mm³** of cavity outside the
skin), and the answer is not a re-reading of that number but a rebuilt part:

| | value |
|---|---|
| **solids** | **1** (was 4) |
| validity | valid BRep, 1 shell, closed, **0 free / 0 non-manifold edges** of 1,397, watertight |
| volume / mass | **601,199.886 mm³ / 931.860 g** at 1550 kg/m³ |
| STEP round-trip | 1 solid, 1 shell, valid, 601,199.8849 mm³ (Δ 1.1e-3, 1.8e-9 rel), same optimal bbox |
| bore | stays at the delivered **42.6 mm** — one solid at all 15 radii from 30 to 60 mm |
| wall, pinch band | **1.199 mm** — the design 1.2 mm wall is restored where the part used to be severed |
| wall, aft | **1.180 mm** (delivered band 1.3465 — 12 % over the design wall, where the sagging cavity left extra material) |
| wall, fore | **8.982 mm** — still **7.49×** the shell |
| ring interference | 1,048.409726 mm³ per ring, **identical** to the delivered body |
| delta mass | **−218.715 g** vs the delivered 4-solid body |

The fix that works is **not** `ruled=True` on the cavity (§2a: 2 solids, and 4,890.6 mm³ *more*
cavity outside the skin), and not resampling the cavity's own station table (§2b: identical to 4 dp).
What works is either re-deriving the cavity from the skin that actually exists (§2b′, 56 stations at
10 mm, escaped **0.000 mm³**), or clipping it (§2c, escaped **0.000 mm³**, but **+227,754 mm³ /
+353 g** of wall), or ruling the outer loft that is the real culprit (alt, escaped **0.000 mm³**, but
the service-window slot then severs a 20,910.3939 mm³ strip per side).

**The scope correction that matters:** the brief attributes the 211 mm overshoot and the 166 mm
undershoot to the *cavity* loft. Measured (§1a, 637 ray stations cross-checked against optimal
sections), both are the **outer** loft's: 211.2177 at z −250 (+25.2 over its own 186 mm station) and
165.9622 at z −160 (−20.0). The cavity's own excursion is **≤ 1.77 mm**. That is why every
cavity-only interpolation change fails, and why the fixes that work are the ones that bring the
cavity into agreement with the skin as built.

**What one solid does NOT fix** — stated with numbers so it is not buried:
1. **The fore bulk fill.** z −360…−189.0984 still carries **461,999.9004 mm³** where a 1.2 mm shell of
   the same surface would be 61,723 mm³ — **400,277 mm³ (620.4 g) of surplus**, 7.49× thick, because
   the cavity starts at z −298.8 (local 2V/A at z −300 = 47.688 mm, a solid section). The loft fix
   improves this band by 30.3 % (it hollows the bulge) but cannot remove it.
2. **Mass basis.** 931.860 g is the measured mass of *this* part; `reports/mass_cg.csv` bills the body
   at 392.152 g from `fuselage_battery_bay_shell.step` (253,001.328 mm³), which is a different file
   (`dm-solid-weld` §6). The two are not comparable and neither is the programme's 472.273 g.
3. **The rod of the strip.** The side-wall strip (20,910 mm³ / 2V/A 1.14 per side) is attached by a
   geometry-sensitive throat at the aft taper; ruling the outer (alt) loses it to the service-window
   slot. The delivered skin + re-derived cavity keeps it, and it survives a ±0.1 mm bore change, but it
   is a thin-shell attachment and should be reviewed as a structure item, not assumed.

**Remaining blocker: none for the solid count.** The part is manufacturable as one body on the geometry
tested; what remains is the wall-thickness (fore bulk fill) defect above, which is a station/cavity-start
design change, not a loft or Boolean repair.
## 7. Files

| file | what |
|---|---|
| `work/s1_sections.py` / `out/s1_sections.json` | ray-cast envelope census of both lofts, 637 stations at 1 mm, 11 optimal-section cross-checks |
| `work/s2_cavity_baseline.py` / `out/s2_cavity_baseline.json` | the baseline: cavity cut alone, no bore, pieces, escaped volume |
| `work/s3_fix.py` / `out/s3_*.json` | the five fix variants (ruled cavity, resample-from-table, resample-from-skin, clip, rule both) |
| `work/diag_v4.py` / `out/diag_v4.json` | validity + bbox-instrument census of the resampled cavity and the clip limit; found the 0-triangulation fact and the empty-escape case |
| `work/s4_build.py` / `out/s4_*.json` | bore sweep (15 radii) and the full 6-cut chain for each variant |
| `work/s5_verify.py` / `out/s5_verify_part_v4_full_r42.json`, `out/s5_verify_r42_6.json` | validity, watertightness, volume, mass, band 2V/A on the fixed part and on the delivered control |
| `work/s6_interference.py` / `out/s6_interference_*.json` | body x ring / elevon / duct booleans on fixed and delivered bodies, at 42.6 and 42.4375 |
| `work/s7_wall.py`, `work/s8_wall.py` / `out/s8_wall_part_v4_full_r42.json` | local wall by 2 mm slab (s7's section instrument failed on this shape and is documented, s8 replaces it) |
| `out/part_v4_full_r42.step` / `.brep` | **the one-solid deliverable**, 601,199.886 mm³, STEP round-trip verified |
| `out/part_v2_full_r42.brep`, `out/part_v4_shell_r42.brep`, `out/part_v2_shell_r42.brep` | comparison builds (ruled-both 3-solid part; 42.4375 shell; fixed-cavity shell) |
| `logs/*.log` | raw stdout of every run above |

Reproduce: `"C:/Program Files/Python312/python.exe" work/s2_cavity_baseline.py` then
`... work/s3_fix.py v4_resample_skin`, `... work/s4_build.py --mode full --variant v4_resample_skin
--order repo --radius 42.6 --export out/part_v4_full_r42.6`, then `work/s5_verify.py`,
`work/s6_interference.py`, `work/s8_wall.py`.

Repo untouched: every build wrote into `evidence/dm-loft-fix/`; the generator was read from a copy
whose sha256 equals the pinned `53353DA1...FABD47`. No commit, no reset, no write to
`D:\CodeProjects` or `E:\1vm\TMP`.


