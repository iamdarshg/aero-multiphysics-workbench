# DM fore bulk fill — can the nose surplus be hollowed out to a uniform shell while staying ONE solid?

Wave 16 / fab-readiness. Scope: **one question** — can the drone-mech fore bulk fill
(400,277 mm³ / 620 g surplus, fore band 2V/A **8.982 mm** against the design 1.2 mm shell) be
hollowed out so the whole part reaches a uniform shell thickness **while staying ONE valid solid**?

Status: **COMPLETE**. Answer: **yes** — the surplus is a solid nose block forward of the cavity's
forward cap, and re-deriving the cavity from the MEASURED SKIN over that z range turns the part into
**one valid solid at 206,454.3208 mm³ / 320.004 g**, a 1.199–1.286 mm shell everywhere, with the
interference pairs unchanged to the last decimal. Numbers in §7; the one thing that cannot be
recovered is the 1 mm solid tip (0.029 g).

Inputs (read-only): `repos/drone-mech/highspeed_edf/deliverables/phase15_geometry/`,
`evidence/dm-loft-fix/` (the wave that produced the one-solid part).
Every artefact written under `evidence/dm-fore-fill/` only. No repo writes, no commits,
no writes to `D:\CodeProjects` or `E:\1vm\TMP`.

## 0. Provenance of the generator

| file | sha256 | note |
|---|---|---|
| `copy/.../phase15_generate_geometry.py` | `53353DA1…FABD47` | the pinned version `phase15_generate_fuselage_shell_endpoint_relief.py` pins; byte-for-byte what `dm-loft-fix` used |
| `repos/.../phase15/optimization/phase15_generate_geometry.py` | `8CC6E5DA…42BF51` | **textually identical** (1209 lines, `Compare-Object` diff = 0 lines); the hash differs only by line ending (67667 vs 66458 bytes = 1 extra byte per line, CRLF vs LF) |

So the pinned copy is the repo file; the hash difference is an EOL artefact, not a content change.
Same for the six interference STEP files (§6).

## 1. Step 1 — reproduce the one-solid part (601,199.886 mm³ / 931.860 g)

Rebuilt from the pinned generator copy with the same rule `dm-loft-fix` used — cavity
**resampled from the MEASURED SKIN**, 10 mm stations, −2.4 mm/axis, lofted `ruled=False`, then the
repo's six cuts in the repo's order (ductA, ductB, cavity, slot−x, slot+x, hatch), bore 42.6 mm.

Commands (log `logs/s1_repro_full.log`, `logs/s1_repro_verify.log`):

```
python.exe work/s4_build.py --mode full --variant v4_resample_skin --order repo \
    --radius 42.6 --export out/part_v4_full_r42
python.exe work/s5_verify.py out/part_v4_full_r42.brep
```

| check | this wave | `dm-loft-fix` | Δ |
|---|---:|---:|---:|
| solids after all six cuts | **1** | 1 | 0 |
| volume mm³ (ε 1e-12) | **601,199.886** | 601,199.886 | **0.000** |
| mass at 1550 kg/m³ | **931.860 g** | 931.860 g | 0 |
| shells / closed / free / non-manifold | 1 / True / **0** / **0** of 1,397 edges | same | 0 |
| BRepCheck valid | **True** | True | 0 |
| 2V/A whole part | 3.4142 | 3.4142 | 0 |
| optimal bbox z | −360 … 280 | −360 … 280 | 0 |
| **fore band 2V/A (z ≤ −189.0984)** | **8.9820** (461,999.9004 mm³ / 102,872.0758 mm²) | 8.9820 | **0.0000** |
| pinch band 2V/A | 1.1990 | 1.1990 | 0 |
| aft band 2V/A | 1.1801 | 1.1801 | 0 |

**Reproduced digit-for-digit.** Every intermediate stage also matches (ductA 5,977,767.7043 →
ductB 4,002,371.4373 → cavity 667,808.5733 → slot− 659,329.5007 → slot+ 650,850.4293 → hatch
601,199.886).

### 1a. Where the 8.982 mm fore wall actually is: z −360 … −298.8

Same thin-slab instrument, 4 mm slabs, z −360 … −160 (`work/s2_foreprofile.py`,
`out/s2_foreprofile_part_v4_full_r42.json`, `logs/s2_foreprofile.log`). Per slab,
`shellEq = 1.2 · A_eff / 2` is the volume a 1.2 mm wall of that surface would have, so
`surplus = V − shellEq` decomposes the headline number row by row.

| z slab | V mm³ | A_eff mm² | **2V/A mm** | shellEq mm³ | surplus mm³ |
|---|---:|---:|---:|---:|---:|
| −360 … −356 | 544.37 | 384.40 | **2.83** | 230.64 | 313.7 |
| −352 … −348 | 6,290.98 | 1,134.94 | **11.09** | 680.96 | 5,610.0 |
| −340 … −336 | 19,358.05 | 1,571.50 | **24.64** | 942.90 | 18,415.2 |
| −324 … −320 | 36,891.42 | 1,825.17 | **40.43** | 1,095.10 | 35,796.3 |
| −312 … −308 | 47,352.90 | 1,927.03 | **49.15** | 1,156.22 | 46,196.7 |
| −304 … −300 | 46,945.52 | 1,995.02 | **47.06** | 1,197.01 | 45,748.5 |
| **−300 … −296** | 15,618.82 | 2,577.45 | **12.12** | 1,546.47 | 14,072.4 |
| **−296 … −292** | 1,625.75 | 2,853.92 | **1.139** | 1,712.35 | **−86.6** |
| −280 … −276 | 1,772.45 | 2,974.89 | **1.192** | 1,784.93 | −12.5 |
| −256 … −252 | 1,833.56 | 3,027.75 | **1.211** | 1,816.65 | +16.9 |
| −232 … −228 | 1,752.98 | 2,931.11 | **1.196** | 1,758.66 | −5.7 |
| −208 … −204 | 1,589.62 | 2,686.85 | **1.183** | 1,612.11 | −22.5 |
| −184 … −180 | 1,413.13 | 2,370.94 | **1.192** | 1,422.56 | −9.4 |
| −168 … −164 | 1,332.04 | 2,218.11 | **1.201** | 1,330.87 | +1.2 |

| aggregate, z −360 … −160 | value |
|---|---:|
| V / shellEq / **surplus** | 472,008.7368 / 71,759.5405 / **400,249.1965 mm³** |
| surplus in grams at 1550 kg/m³ | **620.386 g** |
| slabs thicker than 1.5 × 1.2 mm | **16** |
| **z range of those slabs** | **−360.0 … −296.0** |
| surplus inside them | 400,588.7081 mm³ (100.08 % of the total) |

**So the fore "bulk fill" is not a thick wall anywhere: it is a solid nose block.** From z −360 to
the cavity's end cap the section is solid (local 2V/A rises to 49.15 mm against a 2 mm slab — a full
section), and from z −296 forward the wall is the design 1.139–1.211 mm. The break is a step, not a
gradient, and it sits at the cavity start. **There is no thick wall to thin in the fore band: 100 % of
the surplus is the un-hollowed nose.**

## 2. Step 2 — why does the cavity stop at z −298.8?

`work/s3_diag.py` → `out/s3_diag.json`, `logs/s3_diag.log`. Nothing was changed in this step.

The generator's cavity is a **7-station loft**, and its forward station is a hard-coded literal:

```python
inner_stations = [(-298.8, BODY_WIDTH - 2*BODY_SHELL, BODY_HEIGHT - 2*BODY_SHELL),
                  (-200.0, …), (-100.0, …), (0.0, …), (120.0, …), (198.0, 167.6, 77.6), (247.0, 106.0, 50.0)]
cavity = cq.Solid.makeLoft([superellipse_wire(z, w, h) for z, w, h in inner_stations], ruled=False)
```

| question | measured answer |
|---|---|
| is it **a profile table that ends there**? | **YES.** 7 cavity stations, first at −298.8; 11 outer stations spanning −360…280. No cavity station exists forward of −298.8. |
| is it a **deliberate closed nose**? | **No.** A closed nose tapers its sections to a point; the first section is the FULL design section 183.6 × 85.6 = body − 2·1.2. |
| is it a **truncation**? | **No.** There is no larger cavity definition being clipped — the tool is exactly `makeLoft(stations)`. |
| what does the loft do at that end? | Its own flat end cap: the cavity solid has **74 faces = 72 lateral + 2 planar caps**; the forward cap is a 72-gon at z = −298.8 of area **13,408.3393 mm²**, dx 183.6, dy 85.6. |
| why −298.8 and not −300? | **−298.8 = −300.0 + 1.2 = the outer's z=−300 station plane + one `BODY_SHELL`** (exact to 1e-9; `isStationPlane+shell: true`). *Inference, labelled:* a cap 1 shell forward of an outer station plane avoids a coincident face in the boolean. It is a modelling convenience, not a structural requirement. |

**Consequence, measured:** forward of that cap the body is solid — the bare outer is
**432,505.2986 mm³** in z −360…−298.8, and the finished six-cut part carries **415,035.713 mm³**
there. The 17,469.586 mm³ difference is the battery-hatch aperture, whose tool reaches z −308.5
(`BATTERY_Z_CENTRE = −207.5`, z half-length 101 mm) — so **the nose is already vented to the
exterior** over z −308.5…−298.8 and hollowing it cannot create an enclosed void.

**Why the loft fix did not touch it:** `dm-loft-fix`'s `sample_skin()` derives its z range from the
cavity's own table (`z0 = inner_stations[0][0]`), so the re-derived cavity inherits the −298.8
truncation exactly.

## 3. Step 3 — extend the cavity into the fore region

### 3a. Attempt 1 — one long loft over the whole z range: FAILS

`work/s4_extend.py` (first form, single loft): 117 stations, 1 mm through the nose and 10 mm aft,
same ±2.4 mm skin offset, `ruled=False`. `out/s4_nose_v1.json`, `logs/s4_nose_v1.log`.

| quantity | value |
|---|---:|
| cavity volume | 7,542,913.8723 mm³ |
| **escaped (cavity outside the skin)** | **3,079.9378 mm³ in 7 solids, bbox z 186.2 … 246.5** |
| solids after the cavity cut | **2** (256,802.3759 mm³) |

The escape is **aft**, not in the nose: doubling the station count re-parametrises the global
BSpline and it bulges through the aft taper. Abandoned — this is the same failure mode as the
original loft, so "more stations" is not the fix.

### 3b. Attempt 2 — two-piece tool: the aft cavity kept bit-identical, a skin-resampled nose loft added

`work/s4_extend.py --variant nose_v2 --zstart -359 --nose-spacing 2` → `out/s4_nose_v2.json`,
`logs/s4_nose_v2.log`. Method is unchanged — ray the MEASURED skin, subtract 2.4 mm on each axis,
loft `ruled=False` — only the z range of the re-sampling moves:

* **main cavity** = `s3_fix.make_inner(…, "v4_resample_skin")`, the exact tool that reproduced the
  one-solid part (7,131,784.7123 mm³), untouched;
* **nose cavity** = the same rule sampled from −359.0 to the cap at −298.8, 2 mm stations (32
  sections), first section 5.369 × 3.726 mm, last 185.151 × 86.142 mm;
* fused into one cut tool.

| check | main | nose | fused tool |
|---|---:|---:|---:|
| **escape** (cavity outside the skin) | **0.000 mm³, 0 solids** | **0.000 mm³, 0 solids** | **0.000 mm³, 0 solids** |
| volume mm³ | 7,131,784.7123 | 410,558.3034 | 7,542,343.0144 |
| solids | 1 | 1 | **1** |

Chain, one solid at every stage:

| stage | solids | volume mm³ | seconds |
|---|---:|---:|---:|
| ductA | 1 | 5,977,767.7043 | 5.2 |
| ductB | 1 | 4,002,371.4373 | 6.0 |
| **cavity (main+nose)** | **1** | **257,250.2708** | 57.3 |
| slot −x | 1 | 248,771.1984 | 33.3 |
| slot +x | 1 | 240,292.1269 | 33.1 |
| hatch | **1** | **206,454.3208** | 25.4 |

Exported `out/part_nose_v2.step` / `.brep`; STEP round-trip (`work/s7_roundtrip.py`,
`logs/s7_roundtrip.log`): **1 solid, 1 shell, valid, 206,454.3197 mm³ (Δ 1.06e-3 mm³, 5.1e-9 rel),
same optimal bbox**.

## 4. Step 4 — solids / volume / mass / wall per attempt

`work/s5_verify.py` → `out/s5_verify_part_nose_v2.json`, `logs/s5_verify_nose_v2.log`.

| | reproduced (v4) | **attempt 1** (single loft) | **attempt 2** (two-piece) |
|---|---:|---:|---:|
| solids | 1 | **2 (FAIL)** | **1** |
| volume mm³ | 601,199.886 | 256,802.3759 (abandoned after the cavity cut) | **206,454.3208** |
| mass at 1550 kg/m³ | 931.860 g | — | **320.004 g** |
| **fore 2V/A** | **8.9820** | — | **1.0921** |
| **pinch 2V/A** | 1.1990 | — | **1.1990** (identical) |
| **aft 2V/A** | 1.1801 | — | **1.1801** (identical) |
| whole-part 2V/A | 3.4142 | — | **1.1492** |
| shells / closed | 1 / True | — | **1 / True** |
| free / non-manifold edges | 0 / 0 of 1,397 | — | **0 / 0 of 1,561** |
| BRepCheck valid | True | — | **True** |

Band volumes, set-diff form (this is the "SET DIFFS not totals" check):

| band | reproduced | attempt 2 | Δ |
|---|---:|---:|---:|
| fore (z ≤ −189.0984) | 461,999.9004 | **67,254.3350** | **−394,745.5654** |
| pinch (−189.0984 … −111.9330) | 26,262.2632 | 26,262.2632 | **0.0000** |
| aft (z ≥ −111.9330) | 112,937.7213 | 112,937.7213 | **0.0000** |
| whole part | 601,199.886 | 206,454.3208 | **−394,745.5652** |

**All of the change is in the fore band; the pinch and aft bands are bit-identical, which is the
mechanical reason the ring interference cannot move.**

### 4a. The wall is now 1.199–1.286 mm everywhere — measured, and one instrument correction

`work/s6_wallsection.py` → `out/s6_wallsection.json`, `logs/s6_wallsection.log`. Exact 2D instrument:
on each planar section, the minimum distance from every outer 72-gon vertex and mid-edge point to
the cavity 72-gon.

| z | −350 | −340 | −320 | −300 | −250 | −200 | 0 | 120 | 200 | 240 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **min normal wall mm** | 1.1992 | 1.1991 | 1.1991 | 1.1990 | 1.1990 | 1.1990 | 1.1990 | 1.1990 | 1.1990 | 1.1990 |
| mean wall mm | 1.241 | 1.235 | 1.228 | 1.224 | 1.222 | 1.224 | 1.224 | 1.224 | 1.224 | 1.224 |
| max (section corner) mm | 1.2861 | 1.2778 | 1.2684 | 1.2639 | 1.2615 | 1.2639 | 1.2639 | 1.2639 | 1.2634 | 1.2642 |

**Instrument correction (important, and it does not change any earlier conclusion):** the thin-slab
2V/A used in §1a and by `dm-loft-fix` equals `wall · cos α` where α is the surface slant from
vertical. In the near-cylindrical mid-body cos α ≈ 1 (1.196–1.211 as reported), but on the steep
nose cone it reads **0.63 at z −350 for a true 1.200 mm wall** (slab rows in
`out/s5_nosecheck_part_nose_v2.json`, `logs/s5_nosecheck.log`, where the ray sections give
`wall_x = wall_y = 1.2000` at every nose station). So the fore band's new 2V/A of 1.0921 is a
*conical-surface artefact*, not a thin shell: the section instrument says the nose wall is
1.199–1.286 mm.

Fore profile after the change (`out/s2_foreprofile_part_nose_v2.json`, `logs/s2_foreprofile_nose_v2.log`):
over z −360…−100 the surplus is **−7,016.98 mm³** and **0 slabs** exceed 1.5 × 1.2 mm; the band that
held 415,035.7 mm³ now holds **21,396.95 mm³** (z −360…−296).

## 5. Step 5 — how much of the 620 g is recoverable, and where it is not

| quantity | value |
|---|---:|
| reproduced part | 931.860 g |
| **after the nose is hollowed** | **320.004 g** |
| **recovered** | **−611.856 g (−65.7 %), 394,745.57 mm³** |
| headline surplus (row-level instrument, §1a) | 620.386 g / 400,249.20 mm³ |
| **recovered as a fraction of the headline** | **98.6 %** |
| geometrically NOT recoverable | **18.74 mm³ (0.029 g)** — the solid tip forward of z −359.0, where the section (7.8 × 6.1 mm at −359) only just admits a 1.2 mm wall |

**Where it is not recoverable: only the tip.** Every station forward of z −350 now carries a
1.199–1.286 mm wall (§4a), and nothing anywhere else is thick: 0 slabs > 1.5 × 1.2 mm over
z −360…−100. In particular there is **no structural allowance around the duct** — the duct lands
(x ±44, r 42.6, z −112…290) sit in the already-1.2 mm mid-body shell, and the aft/pinch bands are
unchanged to the digit (112,937.7213 and 26,262.2632).

**The 8.5 g difference between 611.856 g and 620.386 g is an accounting convention, not material.**
The headline used `shellEq = 0.6·A_eff`, which is exact only for a tube: over solid bands it omits the
missing inner surface, and on the cone the lateral area is inflated by 1/cos α. The number to quote
is the set diff, **611.856 g**.

**Structural caveat, stated so it is not buried:** the nose is now an empty 1.2 mm cantilever cone
61 mm long with no frame or bulkhead in the CAD. That is the design's own wall, but the nose is the
impact/ground-handling end. If a thickened tip is wanted, making **z ≤ −340 solid again costs
+31,525.75 mm³ = +48.86 g** (34,869.70 vs 3,343.95 mm³ over −360…−340), which would leave 563.0 g
recovered. That is a design judgement, not a geometric constraint — the geometry permits either.

## 6. Step 6 — interference re-check

`work/s6_interference.py out/part_nose_v2.brep out/part_v4_full_r42.brep` →
`out/s6_interference_part_nose_v2.json`, `logs/s6_interference_nose_v2.log`. Absolute body × part
booleans, **both bodies against the same part files**, so every column is a set diff.

| pair | **new body (320.004 g)** | reproduced body (931.860 g) | Δ |
|---|---:|---:|---:|
| `duct_A_vector_vane_bearing_ring` | **1,048.409726** | 1,048.409726 | **0.000000** |
| `duct_B_vector_vane_bearing_ring` | **1,048.409726** | 1,048.409726 | **0.000000** |
| `elevon_left_40x150` | 72.160111 | 72.160111 | **0.000000** |
| `elevon_right_40x150` | 72.160111 | 72.160111 | **0.000000** |
| `duct_A_82OD_78ID_L110` | 0.000 | 0.000 | 0 |
| `duct_B_82OD_78ID_L110` | 0.000 | 0.000 | 0 |
| **total of the six** | **2,241.139674** | **2,241.139674** | **0.000000** |

**Not one digit moved.** Both rings stay at exactly **1,048.409726 mm³** (the required value) and
their overlap bbox is unchanged to 4 dp (x −10.9093…+2.7798, y ±26.9605, z 250…254). The delivered
8-pair / 1,255.303466 mm³ set: the two body pairs in it are these elevon pairs, which are unchanged;
the pushrod-placeholder pairs do not involve the body and cannot be reached by a cavity change
(same files, neither member is the body). Part files: the audit copy and `D:\CodeProjects` are the
same 244-line STEP text with 0 content differences (EOL only, 9598 vs 9354 bytes), so this is
population-identical to the earlier wave's measurement.

## 7. Verdict

**Yes — the fore bulk fill can be hollowed to a uniform shell while staying ONE valid solid.**

| | value |
|---|---|
| **solids** | **1** (unchanged from the reproduced part) |
| validity | **valid** BRep, **1 shell**, closed, **0 free / 0 non-manifold** edges of 1,561 |
| **volume / mass** | **206,454.3208 mm³ / 320.004 g** at 1550 kg/m³ |
| STEP round-trip | 1 solid, 1 shell, valid, 206,454.3197 mm³ (Δ 1.1e-3, 5.1e-9 rel), same bbox |
| **wall, whole part** | **1.199 – 1.286 mm** (min/mean/max by section), design 1.2 mm |
| wall, fore band 2V/A | 8.9820 → **1.0921** (solid block → conical shell; the 2V/A reads low on the cone, §4a) |
| wall, pinch / aft 2V/A | 1.1990 / 1.1801 — **bit-identical to before** |
| **mass recovered** | **611.856 g of the 620.386 g headline (98.6 %)**, −65.7 % of the body |
| **not recoverable** | **18.74 mm³ / 0.029 g** — the solid tip forward of z −359 |
| interference | 6 pairs, **2,241.139674 → 2,241.139674**, rings **1,048.409726 each**, Δ **0** |

**The cause, in one sentence:** the cavity is a 7-station loft whose first row is the hard-coded
literal `−298.8` (= the −300 outer station + 1.2 mm), so the loft ends in a flat 13,408 mm² cap and
everything forward of it — 415,036 mm³ of solid nose — was never a wall at all.

**The fix, in one sentence:** keep the working cavity exactly as it is and add a second
skin-resampled loft over the fore range (−359 … −298.8, 2 mm stations, same −2.4 mm rule, same
`ruled=False`), fuse the two into one tool — a single long loft over the whole range does **not**
work (it re-parametrises the BSpline and escapes the skin aft by 3,079.94 mm³).

**Is it a manufacturable single-wall shell? Yes on geometry** — uniform 1.2 mm wall, one watertight
solid, unchanged interfaces. **With one flagged caveat:** the nose is now an empty 1.2 mm cone with
no internal structure; the CAD has none anywhere, so this is consistent with the rest of the body,
but the tip is the impact end and a local thickening (z ≤ −340 solid = +48.86 g) is the engineering
insurance worth taking.

## 8. Files

| file | what |
|---|---|
| `work/s1_sections.py`, `s2_cavity_baseline.py`, `s3_fix.py`, `s4_build.py`, `s5_verify.py`, `s6_interference.py`, `s8_wall.py` | unmodified `dm-loft-fix` instruments, copied; `s6`'s REPO_STEP repointed at the audit repo copy (read-only) |
| `work/s2_foreprofile.py` / `out/s2_foreprofile_part_v4_full_r42.json`, `…_nose_v2.json` | row-level z decomposition of the surplus; same instrument on both parts |
| `work/s3_diag.py` / `out/s3_diag.json` | the −298.8 diagnosis: station tables, cavity caps, nose envelope (1 mm), solid split |
| `work/s4_extend.py` / `out/s4_nose_v1.json`, `out/s4_nose_v2.json` | attempt 1 (single long loft, fails) and attempt 2 (two-piece, works) |
| `work/s5_nosecheck.py` / `out/s5_nosecheck_part_nose_v2.json` | ray sections vs slab 2V/A at the same stations — the cos α correction |
| `work/s6_wallsection.py` / `out/s6_wallsection.json` | exact section-level normal wall, 10 stations |
| `work/s7_roundtrip.py` / `out/s7_steproundtrip_part_nose_v2.json` | STEP round-trip of the deliverable |
| `out/part_nose_v2.step` / `.brep` | **the one-solid deliverable**, 206,454.3208 mm³, 320.004 g |
| `out/part_v4_full_r42.brep` / `.step` | the reproduced control (601,199.886 mm³) |
| `logs/*.log` | raw stdout of every run above |

Reproduce:

```
python.exe work/s4_build.py --mode full --variant v4_resample_skin --order repo --radius 42.6 --export out/part_v4_full_r42
python.exe work/s5_verify.py out/part_v4_full_r42.brep
python.exe work/s2_foreprofile.py out/part_v4_full_r42.brep 4 -360 -160 1.2
python.exe work/s3_diag.py
python.exe work/s4_extend.py --variant nose_v2 --zstart -359 --nose-spacing 2 --export out/part_nose_v2
python.exe work/s5_verify.py out/part_nose_v2.brep
python.exe work/s6_wallsection.py
python.exe work/s6_interference.py out/part_nose_v2.brep out/part_v4_full_r42.brep
python.exe work/s7_roundtrip.py out/part_nose_v2.step out/part_nose_v2.brep
```

Repo untouched: every build wrote into `evidence/dm-fore-fill/`; the generator was read from the
pinned copy (`53353DA1…FABD47`). No commit, no reset, no write to `D:\CodeProjects` or `E:\1vm\TMP`.