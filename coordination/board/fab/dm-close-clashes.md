# dm-close-clashes — the 8 genuine clashes cleared, and the collar shrink fit opened to a real fit

STATUS: **COMPLETE** — the 8 rows are itemised with their envelope/real split, adjudicated against the
**real** rotors, and **executed**: one straight cut per side at |x| = 93.735 clears all four causes per
side to **0.000000**. The collar bore is opened Ø81.000 → Ø81.900 and its hoop stress drops from
**3.067 σ_y (rigid bound; 0.915–1.495 σ_y two-body) to 0.305 σ_y (0.113–0.173 σ_y two-body)**. The full
closure sweep re-runs to a **new authoritative total of 16 pairs / 1,229.794165 mm3 with
0 pairs / 0.000000 genuine clash**, +0 added rows, 20 rows byte-same. Fuselage re-verified byte-identical
(same sha256) at 206,454.319709 mm3 / 320.0042 g, walls 1.0921/1.1990/1.1800, ring v2 **0.000000**
against all 28 parts. No repo write, no commit, no reset.
*(This directory already contained an earlier unit's evidence from 18:19–19:33 today, reported nowhere,
which reached the same totals independently — declared in §0a, with its JSONs kept and checksummed.)*

Basis inherited, not re-derived: `evidence/dm-remaining-26/REPORT.md` §2d/§3a/§3c — the authoritative
split **24 pairs / 4,291.527767 mm3 = 8 genuine clash / 2,140.555804 + 14 dispositioned contact /
2,146.042809 + 2 withdrawn / 4.929154**, with the elevon↔wing artefact already recut to 0.000000 and
ring v2 CLEAN. The 8 are 4 causes × 2 sides, all at one station (the plate's root at r = 11.250 from
the duct axis):

| # | row (per side) | mm3 | per side | envelope? |
|---|---|---:|---:|---|
| 1 | `elevon ↔ motor_A_R3 envelope` | 628.119864 | 585.708363 panel + 42.411501 pin | **YES** |
| 2 | `elevon ↔ motor_A_R2 envelope` | 249.750363 | 221.778419 panel + 27.971944 pin | **YES** |
| 3 | `elevon ↔ nozzle_A shell` | 120.247564 | panel | no — real part |
| 4 | `elevon ↔ fuselage REV 1` | 72.160111 | panel | no — real part |
| | ×2 sides | **2,140.555804** | 1,070.277902 | |

## 0. Write scope, instrument, invariants

### 0a. This directory already held a previous unit's evidence — declared

`evidence/dm-close-clashes/` was **not empty** when this wave started. It contained a complete pipeline
from an earlier unit that ran **today 18:19–19:33** (`work/s1_census.py … s8_diff.py`, `out/s1_census.json
… out/s8_diff.json`, its own `work/obj_fix/` and `work/obj_fix2/`). That unit's pipeline stops at
`out/s8_diff.json` (19:33:25) and it **left no REPORT.md** — this file is the first report for this
directory. Its JSONs are untouched and are still SHA256-listed in `SHA256SUMS.txt`; its scripts are
distinguished from mine by name (`s1_census, s2_rows, s3_trim, s4_collar, s5_closure, s6_joints,
s7_verify, s8_diff` vs my `s1_rows, s1b_envelopes, s1c_subset, s2_fix, s3_sweep, s4_joints, s5_verify,
s6_diff, s7_extra`). Its relieved-wing BREPs are byte-identical to the ones used here
(sha256 `430a8b33…`), i.e. both units worked from the same `dm-remaining-26` operands.

**Why this matters and is repeated below rather than buried:** that unit reached the same numbers
independently, which is a real cross-check of this wave's arithmetic — and where its analysis goes
further than mine (the two-body collar stress, the envelope-resize test) I re-derived the quantity myself
(`work/s7_extra.py`) instead of quoting it. The agreement, quantity by quantity:

| quantity | this wave | prior unit, same directory |
|---|---:|---:|
| `elevon ↔ motor R3 envelope`, per side | 628.119864 | 628.119863682 |
| `elevon ↔ motor R2 envelope`, per side | 249.750363 | 249.750363179 |
| trimmed elevon volume | 7,033.997403 | 7,033.997403057 |
| removed by the trim | 2,440.874912 | 2,440.874911935 |
| gap to the fuselage after the trim | 0.499723 | 0.499723141 |
| collar row after the bore change | 51.490704 | 51.490703592 |
| collar volume after | 1,094.4995 | 1,094.499464584 |
| closure total / rows | **1,229.794165 / 16** | **1,229.794165 / 16** |
| delta vs C-24 | −3,061.733602 | −3,061.733603 (its own rounding) |
| fuselage volume | 206,454.319709 | 206,454.319709018 |
| ring v2, parts / max row | 28 / 0.000000000 | 28 / 0.000000000 |

Not independent of the *inputs* (same STEP operands, same directory) — independent of the *code*, which
is the part an arithmetic slip would live in. The BREP bytes differ (different boolean tools, same
volume to 1e-9), so the agreement is not a shared file.

- [x] **Write scope.** Everything written under `E:/engineering-portfolio-audit/evidence/dm-close-clashes/`
      only. The repo was read only (`deliverables/phase15_geometry/step` for the real rotors).
      **No repo write, no commit, no reset**; nothing written to `D:\CodeProjects` or `E:\1vm\TMP`.
      Operands are copies: 30 STEPs + the two relieved-wing BREPs from `dm-remaining-26/work/`, now in
      `work/obj/` and `work/fix/`. Free space at start: C: 20.20 GB, D: 142.90 GB, E: 10.86 GB; the
      whole evidence dir is < 100 MB, so no large intermediate was moved to D:.
- [x] **Instrument.** `C:\Program Files\Python312\python.exe`, cadquery 2.7.0 / OCP 7.8.1.1
      (OpenCASCADE). Volume `BRepGProp.VolumeProperties_s(shape, props, 1e-12)` — never
      `Shape.Volume()`. Booleans `BRepAlgoAPI_Common` / `BRepAlgoAPI_Cut`, OCP default fuzzy 0.0,
      **solid-by-solid** (one compound × compound boolean under-reports on this model — `dm-interference-
      reconcile` §1c; it bit again here, see §1b). Distance `BRepExtrema_DistShapeShape`.
      Containment `BRepClass3d_SolidClassifier`, tol 1e-6.
- [x] **Invariants to preserve.** Fuselage 206,454.319709 mm3 / 320.0042 g, 1 solid, walls
      1.0921 / 1.1990 / 1.1800; ring v2 0.000000 against all 28 parts. §6.

## 1. The 8 rows, itemised — parts, volume, envelope-versus-real

`work/s1_rows.py` → `log/s1_rows.log` (left side re-measured here solid-by-solid; the right side is
quoted from `dm-remaining-26/out/s3b_elevon_rows.json`, same instrument, and the left reproduced it to
the printed digit: 628.119864 / 249.750363 / 120.247564 / 72.160111).

| # | the two parts | mm3 | the intersection piece, measured | envelope? |
|---|---|---:|---|---|
| 1 | elevon panel + Ø3 hinge pin ↔ `motor_A_R3_3670_42x72_envelope` | **628.119864** | 585.708363 at x −65.000…−55.250, z 115.263…155.310, r 11.286…21.041 (51 faces) + the pin 42.411501 at x −64.250…−58.250, z 126.120…129.120, **100 % buried** | **ENVELOPE** |
| 2 | elevon panel + the same pin ↔ `motor_A_R2_3670_42x72_envelope` | **249.750363** | 221.778419 at the same x/r, z 115.263…**128.000** (23 faces) + 27.971944 of the *same* pin, z 126.120…128.000 | **ENVELOPE** |
| 3 | elevon panel ↔ `duct_A_separate_nozzle_and_exit_lip` | **120.247564** | x −85.000…−82.978, z 115.396…155.405, r **38.988…41.021** — the plate crosses the r 39…41 shell wall | no — **REAL** |
| 4 | elevon panel ↔ `drone-mech_fuselage_rev1` | **72.160111** | x −93.235277…−91.468077, z 115.437…155.442, r **47.477…49.253** — the plate crosses the side wall | no — **REAL** |

**The split.** Envelope-vs-structure **1,755.740454 mm3 = 82.02 %** (rows 1–2); structure-vs-structure
**384.815350 mm3 = 17.98 %** (rows 3–4). Both sides, 2,140.555804.

### 1b. What the envelopes actually say — the decisive test

Three checks, because "an envelope overlapping structure" has two possible meanings.

**(a) The real rotor is 23.26 mm away.** The closure population has no rotor solids, so the envelope is
the only representable rotor — but the rotors are in the repo, and they are **not** what the plate hits:

| part | z bounds, measured | the plate's z | gap | common volume |
|---|---|---|---:|---:|
| `duct_A/B_rotor_R3_N11` (real) | **76.000…92.000** | 115.263…155.976 | **23.263498 mm** | **0.000000** |
| `duct_A/B_rotor_R2_N12` (real) | **40.000…56.000** | 115.263…155.976 | **59.263498 mm** | **0.000000** |

So no envelope row is about the rotor sweep. What the plate hits is the **motor can** the model places
above each rotor station — an 80 mm extent from z 84 to 164 (R3) and 48 to 128 (R2).

**(b) That can placement is itself impossible — and the repo says so.** `phase15/reports/
motor_pitch_bounds_20261101.json` (disposition `BLOCKED_CURRENT_36MM_PITCH_EXCEEDS_NATIVE_STEP_MOTOR_
ENVELOPE`) records: the three cans sit at 36 mm pitch, each 80 mm tall (72 mm can + 8 mm pilot stub), so
adjacent principal can bodies overlap **36 mm**, full components **44 mm**, and R1/R3 by 8 mm. Measured
here: **R2 ∩ R3 = 50,033.004601 mm3** per duct, identical A and B. Three Ø42 cans cannot occupy one
Ø42 bore — at most one of the three is placeable. **The envelope rows therefore overlap a keep-out whose
own arrangement is declared BLOCKED.** They are not evidence that a motor sits there; they are evidence
that the plate stands where *some* motor might be put.

**(c) The R2 row is the R3 row, twice counted.** Both envelopes are Ø42 about the same axis with the
same xy footprint; R3 spans z 84…164 and R2 z 48…128, so the plate's R2 material (z 115.263…128.000) is
inside R3. Proved by classification, not by nesting booleans (the chained `Common(Common(plate,R2),R3)`
returns 0.000000 — the compound-under-report trap again): **276 of 276** interior samples of the R2
row's two pieces are inside the R3 envelope, on both sides (`out/s1c_subset.json`).
R2's row is a **strict spatial subset** of R3's, so the 8 rows carry **3 distinct volumes per side**:

| distinct, per side | mm3 |
|---|---:|
| R3 envelope | 628.119864 |
| nozzle shell | 120.247564 |
| fuselage wall | 72.160111 |
| **distinct per side** | **820.527539** |
| **both sides** | **1,641.055078** |
| R2 row, counted twice | 499.500726 |

**Verdict on the envelope split.** 82.02 % of the headline is envelope-vs-structure, it is **not
independently verifiable** (real rotor clear by 23.263 mm; the stack that the envelope represents is
BLOCKED), and **28.4 %** of the envelope volume is a duplicate of the row above it. **But the plate still
has to move**, and not because of the envelopes: it crosses two real parts (§1 rows 3–4). The envelope
rows clear themselves once the real rows are satisfied — which is what §2 executes.

## 2. Decision and execution per row

**One geometry fact decides all eight.** The plate is a **radial fin** about the duct axis: r = √((x∓44)² +
y²) and the plate is 2.209 mm thick in y, so r is set by |x| to within 1.3 mm across the whole section
(root cap |x| = 55.250 → r = 11.250 nominal, 11.286 measured at the thick side; tip |x| = 204.750 →
r = 160.755). So "clear the fan tube and the fuselage wall" is exactly **one straight cut at
|x| = 93.735**, not a shape cut. 93.735 = 55.250 + **38.485**, and 38.485 is `fab-dm-final`'s measured
remedy; it is re-derived here as **93.235 (the fuselage wall's outboard face, measured in row 4) +
0.500 mm** — the same clearance convention the wing relief uses.

| row | decision | why |
|---|---|---|
| 1 `R3 envelope` | **CUT** (by X1) | the plate's inboard 38.485 mm stands in the fan's passage; the throw is what the real rows require anyway, and the envelope row clears with them |
| 2 `R2 envelope` | **CUT** (by the same X1) | same material as row 1 (276/276 samples); no separate action exists |
| 3 `nozzle shell` | **CUT** (by X1) | a real r 39…41 shell wall is crossed at r 38.988…41.021 — cannot be dispositioned as clearance |
| 4 `fuselage wall` | **CUT** (by X1) | a real side wall is crossed at r 47.477…49.253 — cannot be dispositioned as clearance |
| `collar` (§3) | **BORE OPEN** (X2) | a shrink fit is legitimate; 3.07 σ_y is not |

**The "resize the envelope" option was tested, not gestured at** (`work/s7_extra.py` →
`out/s7_extra.json`). The delivered keep-out is Ø42 (r 21), but the sourced donor motor in the repo is a
**"36×70 can"** and the repo's own screen marks the 42×72 planning envelope *"actual SKU dimensions
unverified"*. Shrinking the keep-out to the sourced can (r ≤ 18) is therefore a live option, and it does
this to the rows:

| keep-out | `elevon ↔ R3` per side | `elevon ↔ R2` per side | clears? |
|---|---:|---:|---|
| as delivered, Ø42 (r 21) | 628.119864 | 249.750363 | no |
| resized to the sourced Ø36 can (r 18), axial placement kept | **431.677341** | **170.961462** | **no** |
| margin sitting in the r 18…21 shell alone | 196.442523 (31.28 %) | 78.788901 (31.55 %) | — |

So resizing would be honest book-keeping of 275.231424 mm3 per side (550.462848 both sides, 31.3 % of
the 1,755.740454 envelope total) — **and would still leave 431.677341 mm3 of plate inside a real
motor.** The resize option is rejected for that reason, not for tidiness: no plausible motor diameter
makes the plate's r = 11.250 root acceptable. What actually makes the row unacceptable is rows 3–4 —
a real shell wall and a real fuselage wall — which no envelope edit touches.

**Executed — X1, both sides** (`work/s2_fix.py`, `work/fix/elevon_{left,right}_trimmed.brep`):

| quantity | left | right |
|---|---:|---:|
| elevon volume before | 9,474.872315 | 9,474.872315 |
| elevon volume after | **7,033.997403** | **7,033.997403** |
| removed (panel 2,398.463411 + inboard pin 42.411501) | **2,440.874912** | **2,440.874912** |
| solids | 5 → **4** | 5 → **4** |
| bbox after | −204.750…**−93.735** | **93.735**…204.750 |
| control-surface span | 149.500 → **111.015 mm** (−25.7 %) | same |

**The 8 rows after X1 — all zero, both sides:**

| row | left | right |
|---|---:|---:|
| `elevon ↔ motor_R3 envelope` | **0.000000** | **0.000000** |
| `elevon ↔ motor_R2 envelope` | **0.000000** | **0.000000** |
| `elevon ↔ nozzle shell` | **0.000000** | **0.000000** |
| `elevon ↔ fuselage` | **0.000000** | **0.000000** |
| *control:* `elevon ↔ duct` | 0.000000 | 0.000000 |
| *control:* `elevon ↔ relieved wing` | 0.000000 | 0.000000 |
| *control:* `elevon ↔ centre bridge` | 0.000000 | 0.000000 |
| *control:* real rotor R3 / R2 | 0.000000 | 0.000000 |
| *control:* `elevon ↔ pushrod` (withdrawn, unchanged) | 2.464577 | 2.464577 |

Measured clearance after the cut: **0.499723 mm to the fuselage** (BRepExtrema — the plate is now 0.500
clear of the wall's outboard face at |x| = 93.235277), 8.735 mm to the nozzle. The trim bracket
(`out/s2_fix.json` → `trim_sweep`) fixes the number rather than choosing it: at trim **37.485** (root
−92.735) and **37.985** (root −93.235) the distance to the fuselage is **0.000000** — the plate is still
inside the wall; at **38.485** (root −93.735) it is **0.499723 mm**. So 38.485 is the smallest trim that
buys a declared 0.500 mm clearance, and the wing's relief gap (0.500 mm) is unchanged because the cut is
inboard of the plate's leading edge.

Mass at the fuselage's own 1550 kg/m3 basis (stated so the two numbers are comparable): the elevon goes
14.686 g → **10.903 g**, i.e. **−3.783 g per side / −7.566 g both**.

**What the fix costs, stated.** (i) The control surface loses 25.7 % of its span. (ii) The inboard of the
three Ø3 hinge knuckles (x 58.250…64.250, r 14.329…20.306 — inside the fan tube) is deleted with the
trim; the two that remain are at |x| 127.000…133.000 and 195.750…201.750. (iii) The plate's new root
overhangs its first knuckle by **33.265 mm** unsupported: a third knuckle and a hinge bracket at the new
root are **required and NOT modelled** — that is the one open knock-on, named in §7, not claimed as done.

## 3. The collar shrink fit — opened from 3.07 σ_y to 0.31 σ_y

As drawn (`dm-remaining-26` §3c, re-derived here): duct OD r 41.000 (Ø82), collar bore r 40.500 (Ø81),
**0.500 mm radial / 1.000 mm diametral interference**, fit radius 40.750, ε = 0.012270,
σ_θ = E·ε = 69,000 × 0.012270 = **846.6 MPa = 3.067 σ_y** (6061-T6, 276 MPa); first yield at
ε_y = 0.004000 → **δ = 0.163 mm**, i.e. the model asks for 3.07× the interference aluminium can take.

**Executed — X2** (`work/fix/collar_{A,B}_bore81p900.brep`): bore r 40.500 → **40.950** (Ø81.000 →
**Ø81.900**), i.e. the "open by 0.900" option, not a material change and not a redesign.

| quantity | as drawn | now |
|---|---:|---:|
| collar bore r / Ø | 40.500 / Ø81.000 | **40.950 / Ø81.900** |
| wall at the bore | 1.500 mm | **1.050 mm** |
| collar volume | 1,555.0884 mm3 | **1,094.4995 mm3** (−460.5889) |
| radial / diametral interference | 0.500 / 1.000 mm | **0.050 / 0.100 mm** |
| **hoop stress, rigid bound E·δ/a** | **846.6 MPa = 3.067 σ_y** | **84.2 MPa = 0.305 σ_y** |
| hoop stress, two-body at E_duct 20 GPa | 252.4 MPa = **0.915 σ_y** | 31.1 MPa = **0.113 σ_y** |
| hoop stress, two-body at E_duct 45 GPa | 412.6 MPa = **1.495 σ_y** | 47.7 MPa = **0.173 σ_y** |
| contact pressure p at the interface | 7.62 / 12.46 MPa | 0.77 / 1.18 MPa |
| duct elastic hoop strain (−, %) | 0.825 / 0.600 (allowable 0.3–0.5) | **0.074 / 0.051** ✔ |
| geometric interference strain δ/a | 1.227 % | 0.122 % |
| assembly ΔT (23.6e-6/K) | 520 K | **51.7 K** |
| axial friction the fit can carry | 1.69 kN | 0.16 kN |
| duct ∩ collar, measured | **512.079603** | **51.490704** |

The two-body numbers matter because a 1.050 mm aluminium collar does **not** take the whole
interference — a 2.000 mm composite duct shares it, so the rigid bound (3.07 σ_y) is the pessimistic end
of the range, not the truth. At the as-drawn fit the two-body stress is **0.915–1.495 σ_y**, i.e. the
collar is at or past first yield either way — the 3.07 figure overstates the stress but not the verdict.
`work/s7_extra.py` → `out/s7_extra.json` (`p = δ / (a(C_c + C_d))`, `C_c = (a²+r_o²)/(E_c(r_o²−a²)) +
ν_c/E_c`, `C_d = (a²+r_i²)/(E_d(a²−r_i²)) − ν_d/E_d`, E_c 69 GPa / ν_c 0.33, ν_d 0.30, duct r_i 39.0,
r_o_c 42.0, E_d 20 and 45 GPa). The prior unit in this directory solved the same two-body problem
independently and its **executed** stress agrees with mine to 0.1 % (31.11 vs 31.08 MPa; 47.76 vs
47.73 MPa); its as-drawn numbers are 5–8 % higher (273.3 / 436.9 MPa), i.e. the same verdict.

The residual 51.490704 mm3 is exactly π(41.000² − 40.950²) × 4.000 — **the fit allowance itself, not a
defect**. At 2700 kg/m3 the collar goes 4.199 g → **2.955 g** (−1.244 g each, −2.488 g a pair), and its
wall 1.500 → 1.050 mm.
**Fit class now claimed: light press / locational interference fit** — 0.100 mm diametral on Ø82 =
**0.122 %**, the band an H7 bore with a p6/r6-class shaft produces at Ø80–100 mm, assembled by heating the
collar ~52 K. It is explicitly *not* the as-drawn 1.000 mm diametral = **1.22 %**, which is outside every
ISO 286 fit band for a Ø82 aluminium ring.

## 4. The two weak joints, bounded

`work/s4_joints.py` → `out/s4_joints.json`.

### 4a. Vane root in the servo bracket (320.137167 / 196.000000) — **it needs a slot**

The bracket is 7 box solids, 42 planar faces and **0 cylindrical faces** (`Geom_CylindricalSurface`
count = 0). It has no bore and no slot; the blade and its shaft are solid-on-solid inside it:

| mount | plate (box 0) | rib (box 1) | shaft | lug (box 6) | row |
|---|---|---|---:|---:|---:|
| A1 / B1 | 174.000000 = 2.000 × 3.000 × 29.000 | 132.000000 = 2.000 × 2.000 × 33.000 | 14.137167 = π·1.5²·2.000 | — | **320.137167** |
| A2 / B2 | 174.000000 = 2.000 × 3.000 × 29.000 | — (blade never reaches it) | — | 22.000000 = 2.000 × 2.000 × 5.500 | **196.000000** |

**Verdict: a slot is required, and three features, not one.** Cutting the bracket with the piece's own
footprint (`out/s4_joints.json` → `J2.slot`): a **3.000 mm deep mortise 2.000 × 29.000 in the plate's
side face** — 174.000000 of that solid's 8,004.000000 mm3 (2.17 %), leaving **9.000 of the plate's
12.000 mm** behind it; a **2.000 mm wide through-slot in the 2.000 mm rib** — 132.000000 of
1,782.000000 (7.41 %), splitting the rib's 27.000 mm width into 25.000 (two ligaments joined by the
plate); and a **Ø3 bore through the rib that does not exist at all** — 14.137167 mm3 as the true shaft
volume (0.79 % of the rib), 18.000000 by its 3 × 2 × 3 bbox envelope. Without them the joint cannot be
assembled; with them the plate keeps 97.8 % of its material and the rib **91.8 %** (92.6 % before the Ø3
bore).

**And the "mirror" pair is not a mirror.** A1's rib sits at y **54.000…56.000**; a true mirror is
y −56.000…−54.000, but A2's rib sits at y **−70.000…−68.000** — **14.000 mm outboard of its mirror**,
beyond the blade's span (−59…−29). That single displacement *is* the 124.137167 difference
(132.000000 + 14.137167 − 22.000000). So `196.000000` is not a lighter joint: it is the same joint with
its rib missing from the blade's path. Mirroring the rib would add **146.137167 mm3** to each −y row.

### 4b. Vane through the nozzle exit lip (20.002085) — a slot, bounded

Per vane: x −45.000…−43.000, **z 240.000…245.000** (the 5.000 mm exit lip), r **38.987177…41.000** — the
blade crosses the 2.000 mm wall over the lip's full 5 mm. The slot it needs removes **20.002085 mm3** from
the lip band, whose material volume is π(41² − 39²) × 5.000 = **2,513.274 mm3** — **0.796 % of the band**,
and 2.000 mm of a 251.3 mm mean circumference (**0.796 %** again, as it must be for a prismatic band).
Bound: acceptable as a local exit-lip slot; the disposition stays contact. Neither J2 nor J3 changes the
14-row dispositioned-contact count.

*Correction kept on the record:* the first version of this line divided the 20.002085 mm3 by the
**area** π(41² − 39²) = 502.6548 mm² and printed 3.98 % — a volume over an area. `out/s4_joints.json` has
been regenerated with the volume-over-volume form (0.7959 %) and the wrong field name
(`section_removed_pct`) is gone.

## 5. Full closure sweep, re-run on the fixed assembly

`work/s3_sweep.py --tag fixed` → `out/s3_sweep_fixed.json`, `log/s3_sweep_fixed.log`;
`work/s6_diff.py` → `out/s6_diff.json`. Same population (30 solids-groups + 2 code-built beads), same
algebra (solid-by-solid `Common`, summed), same tolerance (fuzzy 0.0, bbox pad 1e-6, row threshold
1e-9), same tie-break: 89 bbox-prefiltered candidates of 496, 67 examined zero, 407 bbox-skipped.

**Set diff against the C-24 baseline: −8 rows / −2,140.555804 mm3, +0 added, 2 rows changed,
20 rows same.** (`out/s6_diff.json`: `{'SAME': 20, 'CHANGED': 2, 'REMOVED': 8, 'ADDED': 0}`; the 20
SAME include the 6 excluded envelope↔envelope pairs, unchanged at 200,446.177670.)

The 8 removed rows are exactly the assignment's 8, one cause per side cleared by one cut:

| removed row | mm3 |
|---|---:|
| `elevon_left ↔ motor_A_R3 envelope` / `elevon_right ↔ motor_B_R3 envelope` | 628.119864 each |
| `elevon_left ↔ motor_A_R2 envelope` / `elevon_right ↔ motor_B_R2 envelope` | 249.750363 each |
| `elevon_left ↔ nozzle_A shell` / `elevon_right ↔ nozzle_B shell` | 120.247564 each |
| `elevon_left ↔ fuselage REV 1` / `elevon_right ↔ fuselage REV 1` | 72.160111 each |

The 2 changed rows are the collar fit, still a contact by design, now at 0.305 σ_y (rigid bound) /
0.113–0.173 σ_y (two-body):

| changed row | baseline | now | delta |
|---|---:|---:|---:|
| `duct_A ↔ collar_A` | 512.079603 | **51.490704** | −460.588899 |
| `duct_B ↔ collar_B` | 512.079603 | **51.490704** | −460.588899 |

### 5a. The new authoritative total, same basis

| class | pairs | mm3 | vs baseline |
|---|---:|---:|---|
| **GENUINE CLASH** | **0** | **0.000000** | was 8 / 2,140.555804 |
| **DISPOSITIONED CONTACT** | **14** | **1,224.865011** | was 14 / 2,146.042809 |
| ├ collar on duct (J1) — light press fit, 0.31 σ_y | 2 | 102.981407 | was 1,024.159206 |
| ├ vane root in servo bracket (J2) — slot required | 4 | 1,032.274334 | unchanged |
| ├ vane through nozzle exit lip (J3) — lip slot | 4 | 80.008341 | unchanged |
| └ D84.0 retaining bead across vane (J4) — notch | 4 | 9.600929 | unchanged |
| **WITHDRAWN PLACEHOLDER** | **2** | **4.929154** | unchanged |
| **total (C-16)** | **16** | **1,229.794165** | was 24 / 4,291.527767 |

> **drone-mech interference, closure basis, after dm-close-clashes: 16 pairs / 1,229.794165 mm3 =
> 0 pairs / 0.000000 genuine clash + 14 pairs / 1,224.865011 dispositioned contact (collar light-press
> fit 102.981407 at 84.2 MPa = 0.305 σ_y rigid bound, 0.113–0.173 σ_y two-body; vane root 1,032.274334
> with a required slot; nozzle exit lip 80.008341; retaining bead 9.600929) + 2 pairs / 4.929154
> withdrawn placeholder. Delta −3,061.733602 mm3 / −8 rows, +0 added, 20 rows byte-same.**

Arithmetic check, to the printed digit: 1,224.865011 + 4.929154 = 1,229.794165;
4,291.527767 − 2,140.555804 − 921.177798 = 1,229.794165; and the sweep's own total
201,675.971835 − 200,446.177670 (the 6 excluded envelope pairs) = 1,229.794165.

## 6. Invariants re-verified

`work/s5_verify.py` → `out/s5_verify.json`, `log/s5_verify.log`, run on the fixed assembly (relieved
wings, trimmed elevons, bored collars — the same population §5 sweeps).

| check | measured | required | |
|---|---|---:|---|
| fuselage volume | **206,454.319709 mm3** | 206,454.319709 | ✔ |
| fuselage mass at 1550 kg/m3 | **320.0042 g** | 320.0042 | ✔ |
| topology | **1 solid / 1 shell / 540 faces**, `BRepCheck` valid | 1 solid / 540 faces | ✔ |
| bbox | x ±105.891846, y −48.458738…45.413633, z −360…280 | unchanged | ✔ |
| sha256 of the operand file | `d9ba7aeb7716cdd1ba4f289d284944e34e0ebab20202d39335bd9b58ecb9cadf` | unchanged | ✔ |
| wall, fore band | V 67,254.3350 / A_eff 123,170.0573 → **2V/A = 1.0921** | 1.0921 | ✔ |
| wall, pinch band | V 26,262.2633 / A_eff 43,807.5718 → **2V/A = 1.1990** | 1.1990 | ✔ |
| wall, aft band | V 112,937.7213 / A_eff 191,416.3898 → **2V/A = 1.1800** | 1.1800 | ✔ |
| **ring v2 A** | **0.000000 against all 28 parts** (max row 0.000000000) | 0.000000 | ✔ |
| **ring v2 B** | **0.000000 against all 28 parts** (max row 0.000000000) | 0.000000 | ✔ |

The fuselage was never opened by this wave: both fixes are on the elevon (trim) and the collar (bore).
The sha256 above is the same digest `dm-remaining-26` recorded, i.e. the file is **byte-identical**, not
merely equal to 6 decimals.

## 7. Honest ledger — what is fixed, what is still open

**Fixed, measured, executed (not proposed):**

1. **All 8 genuine-clash rows are gone**: `0 pairs / 0.000000 mm3` (was 8 / 2,140.555804). One straight
   cut per side at |x| = 93.735 removed 2,440.874912 mm3 of plate per side (panel 2,398.463411 + the
   inboard hinge pin 42.411501) and left **0.499723 mm** clearance to the fuselage wall.
2. **The collar is now an achievable fit**: 0.500 → 0.050 mm radial interference; **σ_θ 846.6 →
   84.2 MPa (3.067 → 0.305 σ_y) on the rigid bound**, and **0.915–1.495 → 0.113–0.173 σ_y** on the
   two-body solution with the duct compliant; duct elastic hoop strain 0.825/0.600 % → **0.074/0.051 %**;
   assembly ΔT 520 K → 52 K; fit class **light press / locational interference (0.122 % diametral)**.
   Row: 1,024.159206 → 102.981407.
3. **The envelope question is answered, including the "resize" option**: 82.02 % of the headline was
   envelope-vs-structure, the R2 row is a 276/276 duplicate of the R3 row (−499.500726 of double count),
   and the real rotor is **23.263 mm** clear — but two real parts (nozzle shell, fuselage wall) were
   crossed, which is why the plate had to move regardless; shrinking the keep-out to the sourced Ø36 can
   still leaves 431.677341 mm3 per side, so the resize option cannot clear it.
4. **Both weak joints are now bounded by measurement instead of by adjective**: J2 needs a slot (3
   features, none of which exist — the bracket has 0 cylindrical faces) and J3's lip slot removes
   0.796 % of the exit-lip band.
5. **Invariants held**: fuselage byte-identical (same sha256) at 206,454.319709 mm3 / 320.0042 g, walls
   1.0921 / 1.1990 / 1.1800; ring v2 A/B **0.000000 against all 28 parts**.

**Open — named, not hidden:**

1. **The third hinge knuckle and its bracket do not exist.** The trimmed root overhangs the first
   remaining knuckle (|x| 127.000) by **33.265 mm** unsupported. A third knuckle at |x| ≈ 100 and a
   fuselage-side hinge bracket are required; neither is modelled here.
2. **The motor can stack is still `BLOCKED`** at the repo level (36 mm pitch, 80 mm cans, 36/44 mm
   overlap, R2∩R3 = 50,033.004601 mm3). This wave moved the plate out of the argument; it did not
   resolve where three Ø42 motors go in one Ø42 bore.
3. **The collar's containment margin is not re-analysed.** Its wall is now 1.050 mm, not 1.500 mm. The
   *fit* stress is fine (0.11–0.31 σ_y); a rotor-burst containment check of the thinner wall is a
   separate analysis and is not claimed. The fit also carries only **0.16 kN** of axial friction (was
   1.69 kN), so axial retention of the collar is now a design item rather than a given.
4. **Aerodynamic authority after a 25.7 % span loss is not assessed** — outside this instrument.
5. **The servo-mount "mirror" pair is still wrong** (A2's rib 14.000 mm outboard of its mirror). If it
   were mirrored, the blade would cross the rib and the contact total would *rise* by 292.274334 mm3
   (2 × 146.137167). It is left as drawn rather than silently corrected.
6. **Fixed geometry is carried as BREP, not STEP** — for the *wing* (the OCP 7.8 STEP writer re-heals
   the 0.500 mm cove, `dm-remaining-26` §B1); the trimmed elevon does round-trip (§B1) but was not
   re-exported by this wave. Nothing here is claimed as a STEP-delivered part.

**The one number to quote**

> **drone-mech: 16 pairs / 1,229.794165 mm3 on the closure basis, of which genuine clash is
> 0 / 0.000000 mm3** (from 24 / 4,291.527767 with 8 / 2,140.555804). The collar fit went from
> 3.067 σ_y to 0.305 σ_y rigid bound (0.915–1.495 → 0.113–0.173 σ_y two-body). Fuselage
> byte-identical; ring v2 clean. | `evidence/dm-close-clashes/`

## Appendix — method, provenance, limits

### A. Instrument and provenance

| item | value |
|---|---|
| interpreter | `C:\Program Files\Python312\python.exe` (Python 3.12) |
| CAD kernel | cadquery 2.7.0 / OCP 7.8.1.1 (OpenCASCADE) — no KiCad, no solver involved |
| volume | `OCP.BRepGProp.VolumeProperties_s(shape, props, 1e-12)` — never `Shape.Volume()` |
| booleans | `OCP.BRepAlgoAPI_Common` / `BRepAlgoAPI_Cut`, OCP default fuzzy 0.0, **solid-by-solid** |
| distance | `OCP.BRepExtrema.BRepExtrema_DistShapeShape` |
| containment | `OCP.BRepClass3d.BRepClass3d_SolidClassifier`, tol 1e-6 (used instead of nesting booleans) |
| bbox | `OCP.BRepBndLib.AddOptimal_s`, pad 1e-6 mm |
| validity | `OCP.BRepCheck_Analyzer` |
| operands | 30 STEPs + 2 relieved-wing BREPs copied from `dm-remaining-26/work/`; real rotor STEPs read from the repo's `deliverables/phase15_geometry/step/` (read only). sha256 of every operand and of every produced BREP in `out/input_sha256.txt` |
| write scope | this directory only. **No repo write, no commit, no reset**; nothing written to `D:\CodeProjects` or `E:\1vm\TMP` |

| script | produced |
|---|---|
| `work/s1_rows.py` → `log/s1_rows.log` | the 4 rows per side, solid-by-solid, with pieces, bboxes and radial stations |
| `work/s1b_envelopes.py` → `out/s1b_envelopes.json` | the real-rotor test (z gap and common volume) and the R2/R3 envelope stack |
| `work/s1c_subset.py` → `out/s1c_subset.json` | the R2⊂R3 subset proof by point classification (276/276) |
| `work/s2_fix.py` → `out/s2_fix.json` | **the execution**: X1 trim, X2 bore, the 8 rows re-measured, the trim bracket, gaps |
| `work/s3_sweep.py --tag fixed` → `out/s3_sweep_fixed.json` | **the full closure sweep** on the fixed assembly |
| `work/s4_joints.py` → `out/s4_joints.json` | J2/J3 bounds: the slot volumes and the mirror measurement |
| `work/s5_verify.py` → `out/s5_verify.json` | fuselage invariants and the ring rows on the fixed assembly |
| `work/s6_diff.py` → `out/s6_diff.json` | the row-level set diff against the C-24 baseline |
| `work/s7_extra.py` → `out/s7_extra.json` | the envelope-resize test (r 18 vs r 21) and the two-body collar stress |

The directory also holds the **prior unit's** pipeline (`work/s1_census.py … work/s8_diff.py`, its
`out/s1_census.json … out/s8_diff.json` and its `work/obj_fix*/`), left intact and checksummed — see §0a
for the agreement table and for which of its results were re-derived here.

### B. Stated limits — what this report does not establish

1. **The fix is carried as BREP, not STEP — with one correction to the inherited note.** The trimmed
   elevon *does* round-trip: this directory's prior unit measured BREP 7,033.997403057 → STEP
   7,033.997403057 with all three rows still 0.000000 (`out/s3_trim.json` → `roundtrip`), and I did not
   reproduce a STEP export myself. What does **not** round-trip is the **wing** relief's 0.500 mm cove
   (`dm-remaining-26` §B1, measured there): the relieved wings are therefore consumed as BREP here, as
   they were by every prior wave. No fixed part is claimed as STEP-delivered.
2. **The motor envelopes are not adjudicated as parts.** The stack they represent is `BLOCKED` by the
   repo's own `motor_pitch_bounds_20261101.json` (36 mm pitch, 80 mm cans). This wave shows the plate
   must clear the *real* structures (nozzle shell, fuselage wall) and that the envelope rows clear with
   them; it does not decide where the motors go.
3. **The collar's containment margin is not re-analysed.** Opening the bore costs 30 % of the wall
   (1.500 → 1.050 mm). The hoop stress of the *fit* is now 0.305 σ_y rigid / 0.11–0.17 σ_y two-body, but a
   rotor-burst containment check of the thinner wall is a separate analysis and is not claimed. The fit
   also carries only 0.16 kN of axial friction (was 1.69 kN).
4. **No aerodynamic consequence is assessed.** The control surface loses 25.7 % of its span and its
   inboard knuckle; whether the remaining 111.015 mm span still meets a roll/pitch authority
   requirement is a flight-dynamics question this evidence cannot answer.
5. **The third knuckle is not modelled.** The trimmed root overhangs its first knuckle by 33.265 mm; a
   third knuckle and a fuselage-side hinge bracket are required and are left as named work (§7).