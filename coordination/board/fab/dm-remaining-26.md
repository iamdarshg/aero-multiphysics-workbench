# dm-remaining-26 — classify & disposition drone-mech's remaining 26 pairs / 5,415.519830 mm3

STATUS: **COMPLETE** — all 26 pairs classified on geometry, the six static interfaces named and
dispositioned, the pushrod withdrawn, **the one artefact executed** (elevon relief recut, 0.000000 on
both wings, set diff **−2 pairs / −1,123.992063 mm3 and nothing else moved**), the full closure sweep
re-run, and the fuselage re-verified byte-identical at 206,454.319709 mm3 / 320.0042 g with walls
1.0921 / 1.1990 / 1.1800 and ring v2 at **0.000000** against all 28 parts. **The authoritative total is
24 pairs / 4,291.527767 mm3 = 8 pairs / 2,140.555804 genuine clash + 14 pairs / 2,146.042809
dispositioned contact + 2 pairs / 4.929154 withdrawn placeholder.** No repo write, no commit, no reset.

The one-line answer, first: **the elevon root is NOT one class.** Its two `elevon ↔ wing` rows
(561.996031 each side, 20.8 % of the total) are a **modelling artefact** — the relief *is* cut, and the
generator cuts it to a designed 0.500 mm gap at every loft station, but the wing is lofted with
`ruled=False` between two stations 74.75 mm apart and the B-spline **overshoots 11.274 mm**, turning the
clearance into 10.774 mm of interference. The other eight rows are a **genuine clash at one station** —
the plate's root stands at r = 11.250 from the duct axis, inside the rotor's reserved r 18, through the
nozzle shell and through the fuselage side wall.

## 0. Basis and scope
- Target: 26 interfering pairs / 5,415.519830 mm3 remaining after the body<->wing 7,563.265475 mm3
  pair was removed as a modelling artefact (`evidence/dm-body-wing`).
- Split under test: elevon root 10 / 3,264.547867; static joints 14 / 2,146.042809;
  pushrod 2 / 4.929154; ring v2 0 / 0 (CLEAN).
- Input: `repos/drone-mech/highspeed_edf/deliverables/phase15_geometry/` (read only) via the operand
  copies already sha256'd in `evidence/dm-interference-reconcile/work/obj/`, re-copied here.
- Write scope: `E:/engineering-portfolio-audit/evidence/dm-remaining-26/` on COPIES only.
  No repo write, no commit, no reset; nothing written to `D:\CodeProjects` or `E:\1vm\TMP`.
- Invariant to preserve: fuselage byte-identical 206,454.319709 mm3 / 320.0042 g, 1 solid,
  walls 1.0921/1.1990/1.1800; ring clearances 0.000000.

Instrument for every number below: `C:\Program Files\Python312\python.exe`, cadquery 2.7.0 /
OCP 7.8.1.1 (OpenCASCADE). Volume by `BRepGProp.VolumeProperties_s` eps 1e-12 (never
`Shape.Volume()`); booleans `BRepAlgoAPI_Common` / `BRepAlgoAPI_Cut` at OCP default fuzzy 0.0;
rays by `IntCurvesFace_ShapeIntersector` tol 1e-7.

## 1. Prior evidence read
- [x] `evidence/dm-body-wing/REPORT.md` — the wing-root artefact: no planar root face, the root
  cap walked 82.568..86.500 while the body's outer mould line ran 85.281..98.591, 36 of 36 contact
  stations went 100 % through the wall; fixed by `wing − fuselage`, set diff −2 pairs /
  −7,563.265475 mm3 and nothing else moved.
- [x] `evidence/dm-interference-reconcile/REPORT.md` — the row-level C-28 table, the closure basis,
  and the arithmetic that makes `1,556.232076` and `9,125.712739` subsets rather than totals.

**The test this wave reuses** (stated by `dm-body-wing` §3, so the classification below is
comparable rather than ad hoc): *an interference that is a consequence of the two surfaces rather
than of a declared feature is a modelling artefact.* A declared feature has a designed boundary —
a plane, an axis, a fit allowance, a fastener pattern. A surface consequence has none: change the
wall thickness 1 % and the "interference" changes 1 %.

## 2. Elevon root — 10 pairs / 3,264.547867

The class is **not one thing**. Two rows are a modelling artefact; eight are a genuine clash with one
named cause. The geometry says so before any opinion does.

### 2a. The elevon HAS a root plane — it is not an unterminated loft

`s1_probe.py` / `s2_elevon_geom.py` (`out/s1_probe.json`, `out/s2_elevon_geom.json`). The part is a
5-solid compound; the panel is solid 0.

| solid | volume mm3 | faces | what it is | planar faces |
|---|---:|---:|---|---:|
| 0 | 8,987.637813 | 51 | the panel (40.713 mm chord band × 149.500 mm span) | **2** |
| 1, 2, 3 | 42.411501 each | 3 each | Ø3 × 6 hinge pins | 2 each (the pin ends) |
| 4 | 360.000000 | 6 | balance horn, 18 × 2 × 10 | 6 |
| **compound** | **9,474.872315** | 66 | | |

Both of the panel's planar faces are **normal to the span**, and they sit on the part's own ends:

| face | plane | area | bbox |
|---|---|---:|---|
| **root cap** | |x| = **55.250**, n = (−1,0,0) | **60.1180 mm2** | y −0.900165…1.308526, z 115.263498…155.263498 |
| **tip cap** | |x| = **204.750**, n = (−1,0,0) | **60.1180 mm2** | y −0.900165…1.308526, z 115.976493…155.976493 |

**This is the decisive difference from the wing root** (`dm-body-wing` §1b): there, *no* planar face
existed anywhere near the root — the only planar x-faces were the two tips at |x| = 260, and the
inboard end wandered 82.568…86.500 mm over a continuous curved cap. Here the control surface is
terminated by a real 60.118 mm² planar cap at each end. **The elevon is not an untrimmed loft.**

### 2b. The relief IS cut — and its span wall is plate-driven to 0.07 mm

The wing sector carries 51 faces (49 B-spline, 1 cylinder r 42.5 = the duct bore, 1 plane = the tip
cap at |x| = 260). So there is no *planar* relief wall to find; the relief had to be measured as a
surface. Rays along −z at the plate's own heights (`s2b_cliff.py`, `out/s2b_cliff.json`):

| quantity | measured |
|---|---|
| wing's aft-chord **step** at the plate's mid-height | **24.929 mm** (z 116.05 → 140.98) |
| the station it lands on | between |x| = 204.8200 and 204.8225, i.e. **|x| ≈ 204.821** |
| the plate's tip cap | |x| = **204.750** |
| clearance between them | **0.071 mm** |
| is the step a full-height wall? | yes — 27.1 mm at y = −8, 24.9 mm at y = 0.2, 27.6 mm at y = +8 |
| same step on the right wing | identical to 4 dp (both wings, byte-different files) |

So the wing carries an aft-chord cut-back over **exactly the plate's span band**, ending 0.071 mm
outboard of the plate's tip. The name `..._with_duct_and_elevon_reliefs` is **true**: the relief is
cut, not merely named.

### 2c. But the relief's chordwise floor is NOT plate-driven — it is loft overshoot

A relief cut for a hinged surface must leave the plate's nose clear along the whole span. Measured
aft-chord at the plate's mid-height, and the burial it implies (`out/s2_elevon_geom.json`, 1 mm
stations; burial = wing aft z − plate leading edge z):

| x | wing aft z | burial (mm) |
|---:|---:|---:|
| −130 | 115.120 | **−0.143** (0.143 clear) |
| −140 | 119.547 | 4.284 |
| −150 | 123.108 | 7.844 |
| −160 | 125.548 | 10.285 |
| **−170** | **126.560** | **11.296** |
| −180 | 125.719 | 10.456 |
| −190 | 122.392 | 7.129 |
| −200 | 115.754 | 0.491 |
| −204 | 113.609 | −1.654 (clear) |

Buried over **x −200…−131** (70 of 118 sampled stations, 68.69 mm of the 149.500 mm span = 46 %),
peaking at **11.304 mm chordwise at x = −171, y = 0.2** = **27.8 % of the plate's 40.713 mm chord**.
The burial is not a slab: at the plate's two faces it is 5.340 mm (y = 1.259) and 2.364 mm
(y = −0.850). The wing's surface bulges into the plate's mid-thickness.

**The cause is in the generator, and it is readable** — `phase15/optimization/phase15_generate_geometry.py`:

```python
def wing_wire(x, inner=False):
    le, chord = wing_le_and_chord(x)
    if 55.25 <= abs(x) <= 204.75:
        chord -= ELEVON_CHORD + ELEVON_GAP        # :321-322   = 40.0 + 0.5
...
def make_wing_shell():
    xs = (-260.0, -205.01, -204.75, -130.0, -55.25, -54.99, 0.0, ...)   # :333
    outer = cq.Solid.makeLoft([wing_wire(x) for x in xs], ruled=False)  # :335
```

with `ELEVON_CHORD = 40.0`, `ELEVON_GAP = 0.5`, `WING_ROOT_CHORD = 425.0`, `WING_TIP_CHORD = 305.0`,
`WING_ROOT_LE_Z = −270.0`, `WING_SWEEP_DEG = 25.0` (`:72-83`).

Three consequences, each measured:

1. **At every loft station the designed gap is exactly 0.500 mm.** The plate's leading edge is
   `te(x) − 40.0` and the relieved trailing edge is `te(x) − 40.5`, where `te` is affine in |x|. So the
   nominal gap is 0.5 mm *everywhere along the span*, not just at stations. Measured at the two
   stations that bound the buried band: **0.500 mm at x = −130** (wing 115.120, plate 115.620) and
   **0.500 mm at x = −204.75** (wing 115.430, plate 115.930). The design is right.
2. **Between stations the loft overshoots.** The relief spans the sections at −130 and −204.75
   (74.75 mm) with **no station in between**, and the loft is `ruled=False`, i.e. a B-spline through
   the sections, which overshoots. At x = −170 the wing's trailing edge reads 126.560 where the
   affine (nominal) value is 115.286: **11.274 mm of overshoot**.
3. **That overshoot turns the designed +0.500 mm clearance into −10.774 mm of interference** — which
   is the 11.304 mm burial measured independently by rays, and reproduces `fab-dm-final`'s
   "−10.754 mm interference at x = −170 against a nominal +0.500" to 0.02 mm.

### 2d. Classification of the 10 rows, row by row

**The criterion** (stated once, applied to all 26): *at a boundary the design declared, the overlap is
the fit allowance and is dispositioned as contact; at a surface the design declared CLEAR, an overlap
is a consequence of the surfaces — an artefact; and where two parts at their intended stations occupy
the same volume with no declared boundary at all, it is a genuine clash.*

| row (each side, ×2 for both wings) | mm3 | where it is (bbox, measured) | class |
|---|---:|---|---|
| `elevon ↔ wing sector` | **561.996031** | plate 559.086833 at x −199.755…−131.063, z 115.625…126.568 + horn 2.909198 at x −139.0…−133.206, z 116.620…119.140 | **MODELLING ARTEFACT** — loft overshoot through a declared 0.500 mm clearance |
| `elevon ↔ motor_A_R3 envelope` | **628.119864** | plate 585.708363 at x −65.0…−55.250, z 115.263…155.310 + one Ø3 hinge pin **100 % buried** (42.411501). r = 11.250…21.000 about the duct axis at x = −44, i.e. the plate's root stands **inside the rotor's reserved r 18 volume** | **GENUINE CLASH** — root station |
| `elevon ↔ motor_A_R2 envelope` | **249.750363** | plate 221.778419 + pin 27.971944, x −65.0…−55.250, z 115.263…128.000 | **GENUINE CLASH** — same cause |
| `elevon ↔ nozzle_A shell` | **120.247564** | x −85.000…−82.978 = **r 38.978…41.000**, z 115.396…155.405: the plate crosses the nozzle shell wall | **GENUINE CLASH** — same cause |
| `elevon ↔ fuselage REV 1` | **72.160111** | x −93.235277…−91.468077, z 115.437…155.442: the plate crosses the fuselage side wall | **GENUINE CLASH** — same cause |

Left side: 561.996031 + 628.119864 + 249.750363 + 120.247564 + 72.160111 = **1,632.273933**;
both sides **3,264.547866** (3,264.547867 published, 1e−6 from 6-dp rows).

**The single cause of the eight non-wing rows** is the plate's root station: |x| = 55.250 is
**r = 11.250** from the duct axis at |x| = 44.000, so the inboard 6.750 mm of the plate stands inside
the rotor's reserved r 18 cylinder, 2.978 mm through the nozzle shell's inner wall, and 2.649 mm
through the fuselage's side wall — three structures, one station. It is `fab-dm-final` §5's named
cause, whose measured remedy (+38.485 mm outboard, 0.000000000 on all four row classes) is *not*
executed here: it is a design change to the deliverable's control-surface station, and this task is
a classification and disposition task. What **is** executed here is the artefact (§5).

## 3. Static joints — 14 pairs / 2,146.042809

`s3_joints.py` → `out/s3_joints.json`, `log/s3_joints.log`. Every row was re-measured here with the
solid-by-solid algebra and its **mating surfaces** read out of the B-rep (cylinder radii and axes,
planar faces), so the fit class is named from geometry, not from a label. The 14 rows are **four
interfaces** made twice (A/B ducts), not fourteen joints.

### 3a. The four interfaces, named

| # | joint | rows | mm3 | the mating geometry, measured |
|---|---|---:|---:|---|
| **J1** | rotor containment collar on duct tube | 2 | **1,024.159206** | duct: cyl r **41.000** (OD Ø82) and r **39.000** (ID Ø78), z 0…110. collar: cyl r **42.000** (OD Ø84) and r **40.500** (bore Ø81), z **4…8** (1.500 mm wall). The collar's bore is **0.500 mm smaller in radius** than the duct's outer wall |
| **J2** | vector-vane blade root in servo-mount bracket | 4 | **1,032.274334** | vane: blade 2.000 mm thick (x −45.000…−43.000), span 30 mm, chord 40 mm; Ø3 shaft r 1.500 on axis (0,1,0). mount: 7 box solids, 42 planar faces, **no cylinder at all** — i.e. **no bore and no slot** |
| **J3** | vector-vane blade through the nozzle exit lip | 4 | **80.008340** | nozzle shell: cyl r **39.000…41.000** (2.000 mm wall), exit lip z 240…245 |
| **J4** | D84.0 retaining bead across the vane blade | 4 | **9.600928** | bead (code-built, `BEAD_RO 42.0 / BEAD_RI 41.0 / z 243.8 / len 1.20`), the row the ring wave introduced |

### 3b. Row by row, with the overlap decomposed

| row | mm3 | decomposition (all pieces measured) |
|---|---:|---|
| `duct_A ↔ collar_A`, `duct_B ↔ collar_B` | 512.079602535 each | **one annular piece each**, 4 faces, bbox exactly the collar's z band 4…8 — the annulus between the collar's bore (r 40.500) and the duct's outer wall (r 41.000). Not a corner contact, not a coincidence: an **interference band** |
| `vane_1 ↔ servo_mount_1` (A1, B1) | **320.137167** each | 174.000000 (blade through the bracket's plate: 2.000 × 3.000 × 29.000) + 132.000000 (blade through the bracket's **rib**: 2.000 × 2.000 × 33.000) + **14.137166941** (the Ø3 shaft through the rib: π·1.5²·2.000) |
| `vane_2 ↔ servo_mount_2` (A2, B2) | **196.000000** each | 174.000000 (blade through the plate) + 22.000000 (the control lug through the plate: 2.000 × 2.000 × 5.500). **No shaft piece** |
| `nozzle_A/B ↔ vane` | 20.002085 each | 8.000834089 (z 240…242, r 38.987…41.000) + 12.001251134 (z 242…245): the blade crossing the 2.000 mm nozzle wall over the 5 mm lip |
| `bead_A/B ↔ vane` | 2.400232 each | one box 2.000 (blade) × 1.200 (bead height) × 1.000 (radial, r 40.988…42.000) |

Every volume except J1 is an **exact product of three dimensions** (174.000000, 132.000000,
196.000000, 22.000000, 2.400232 = 2×1.2×1.0). That is the signature of a rectangular part drawn
into another rectangular part, not of a curved surface crossing a surface — i.e. these are
**modelled inserts at declared interfaces**.

### 3c. The one row that looks like a press fit, costed — and it fails

J1 is the only row that can be an interference fit, and the only one whose overlap is a full
circumference. It was costed exactly as the rings were (`dm-bearing-rings` §4):

| quantity | value |
|---|---:|
| duct outer radius / collar bore radius | 41.000 / 40.500 |
| **implied radial interference** | **0.500 mm** (1.000 mm diametral) |
| fit radius | 40.750 mm |
| hoop strain ε = δ/r | **0.012270** |
| E (6061-T6) | 69,000 MPa |
| **first-order hoop stress σ_θ = E·ε** | **846.6 MPa** |
| yield, 6061-T6 | 276 MPa |
| **stress / yield** | **3.07 ×** |
| interference at first yield (0.004006 strain) | **0.163 mm** = **32.6 %** of what the model asks |

So the collar's bore is 0.900 mm too small to be assembled: a 0.500 mm radial shrink fit on Ø82
reaches 3.07 × yield in aluminium, and 1.23 % hoop strain in the composite duct (allowable 0.3–0.5 %).
Unlike the rings (28 × yield), the *joint class* is legitimate — a containment collar is a shrink fit
by definition — so the disposition is **contact with a mandatory correction**, not a clash:
**bore Ø81.000 → Ø81.900** gives a 0.100 mm diametral fit, σ_θ = 84.7 MPa = 0.31 σ_y.

### 3d. The asymmetry that explains 320.137167 vs 196.000000

The two "mirror" servo mounts are **not** mirrors. Mount A1's rib sits at **y 54…56**, *inside* the
blade's own span (29…59); mount A2's rib sits at **y −70…−68**, *outboard* of it (−59…−29). So the
upper vane crosses the rib (and its Ø3 shaft end with it) and the lower one does not. The 124.137167
difference is exactly 132.000000 − 22.000000 + 14.137166941 = 124.137167 — the rib and the shaft,
which one mount has in the blade's path and the other does not. Stated as a modelling inconsistency
between the two mounts (their bboxes are y 51…71 and y −73…−53: centres 61.0 vs −63.0, 2.000 mm
apart, where a mirror would be exact).

### 3e. Disposition of the 14 rows

| disposition | rows | mm3 | what it means |
|---|---:|---:|---|
| **D-C1 contact, as-drawn buildable** | **12** | **1,121.883603** | J2 (4), J3 (4), J4 (4): the blade root / through-wall penetration / retaining bead is a declared interface; the overlap is the modelled insert. Bounded: 5.000 mm blade-root insertion, a 2.000 mm wall crossing, a 1.200 mm bead. The manufacturing operation each needs is named (a 2.000 × 29.000 mm bracket slot; an exit-lip slot; a bead notch) |
| **D-C2 contact fit, correction required** | **2** | **1,024.159206** | J1: a shrink fit by design, 3.07 σ_y as drawn; bore −0.900 mm |
| **total** | **14** | **2,146.042809** | **2,146.042809 is NOT interference** |

**What this disposition does and does not claim.** It claims the overlaps sit at declared interfaces
and are the fit allowance, so counting them as interference would double-count design intent. It does
not claim they are zero-clearance contacts: as drawn, twelve rows are solid-on-solid and need the
named slot/notch operation, and two need a bore correction. Both are one-line manufacturing
corrections, which is why they are dispositioned rather than treated as clashes.

## 4. Pushrod — 2 pairs / 4.929154

`s3c_pushrod.py` → `out/s3c_pushrod.json`. Measured, not inherited:

| quantity | value |
|---|---|
| solids / faces | **1 / 3** — one cylinder and two planar ends |
| volume | **119.380520836 mm3** = π·1²·38 to 6 × 10⁻⁷ (the rod's own definition) |
| cylinder | **r = 1.000**, axis (0,1,0) |
| bbox | x ±(124.000…126.000), y **−15.000…+23.000**, z 115.000…117.000 |
| the plate's own y band | −0.900165…1.308526 |
| rod beyond the plate's upper face | **21.690 mm**, ending in free air |
| row vs its elevon | **2.464576819** = panel 1.633361882 (x ±124…126, y −0.517…0.591, z 115.592…117.000) + horn 0.831214937 (y −2.000…0.000) |

**Disposition: MODELLING PLACEHOLDER — withdrawn from the count, not counted as clash and not
counted as contact.** Three measured reasons:

1. **It terminates nothing.** Both ends are free: y = −15.000 and y = +23.000 sit in air, and the part
   has 3 faces, so there is no clevis, no rod end, no thread, no adjustable link. A real pushrod ends
   at a clevis on the horn and at the servo arm; this one is a bare Ø2 cylinder on the axis
   (±125, 116) — the generator's `rod` (`phase15_generate_geometry.py:975`, quoted at `:1015-1016` as
   a representative).
2. **Its overlap is an artefact of passing through**, not of a joint: 2.464576819 mm³ is the volume of
   the rod that lies inside the plate's 2.209 mm thickness and inside the horn, i.e. the rod is drawn
   *through* the parts it is supposed to be pinned to.
3. **It must be redrawn anyway**, and `fab-dm-final` §3 said so before this task: after the +38.485 mm
   station change the horn moves 38.485 mm outboard and the link geometry changes with it.

So the row is **2 pairs / 4.929154 mm3, withdrawn** — published with its reason, not silently dropped.
Re-drawing it as a real link would change the *pair count* by zero (it would still touch the horn) and
is a modelling task outside a classification wave.

## 5. Executed fix — the relief recut

`s4_relief_fix.py`, `s4g_mirror_right.py` → `out/s4_relief_fix.json`, `out/s4g_mirror.json`,
`log/s4_relief_fix.log`. On COPIES: `work/obj_fix2/`, never the repo.

### 5a. What was cut, and why this cut

> **`wing_relieved = wing_trimmed_to_skin − offset(elevon panel, 0.500 mm)`**

One offset, one cutter, one single-solid `BRepAlgoAPI_Cut` per wing. The cutter is the panel
inflated by a stated **0.500 mm** — the same `ELEVON_GAP` the generator designs to — so the new
cove has real clearance and its surfaces are **not** coincident with the plate (coincident surfaces
are what cost 800 s per boolean on the body↔wing rows).

| cutter | value |
|---|---|
| operation | `BRepOffsetAPI_MakeOffsetShape.PerformBySimple(panel, 0.500)` |
| signed volume | **11,012.206132 mm3** (panel 8,987.637813) — positive, so not orientation-flipped |
| solids / validity | 1 / `BRepCheck` valid |
| bbox | x −204.751857…−55.247615, y **−1.400162…1.808523**, z **114.874212…156.476487** |

The plate's own bbox is x ±(55.250…204.750), y −0.900165…1.308526, z 115.263498…155.976493 — so the
cutter is the plate + 0.5 mm on the y and z faces, exactly as intended.

### 5b. Result

| | left | right |
|---|---:|---:|
| wing before (trimmed to skin) | 1,344,635.639764 | 1,344,635.639762 |
| **removed by the recut** | **1,028.761660** | **1,028.761660** (see §5c) |
| wing after | **1,343,606.878104** | **1,343,606.878104** |
| solids / faces / valid | 1 / 143 / **true** | 1 / 143 / **true** |
| bbox after | −260.000000…−80.329704, y −13.719369…25.371289, z −224.533238…266.895886 | mirror |
| **elevon ↔ wing, measured** | **0.000000000** | **0.000000000** |
| the other four elevon rows | 628.119863682 / 249.750363179 / 120.247564436 / 72.160111030 | **identical to the last digit** |
| mass | −1.5946 g | −1.5946 g |

**The bbox is unchanged**, i.e. the recut took nothing off the span, the tip or the leading edge: every
cubic millimetre removed lay inside the plate's own envelope in the aft chord, which is what a cove is.

### 5c. The right-hand boolean was rejected, and the symmetry used as the control

The two lifting-wing sectors are exact mirrors: identical volume to 9 dp before and after the body
trim (1,354,555.798302 / 1,344,635.639764 vs 1,344,635.639762) and **aft-surface equality to
0.000000 mm at 7 y stations across 51 span stations** (`work/s4f_mirror.py` → `out/s4f_mirror.json`).
The cutters are mirrors too (identical signed volume 11,012.206132, mirrored bbox).

Cutting mirrored operands with mirrored cutters removed **1,028.762** on the left and **2,158.243** on
the right — a **1,129.481 mm3 disagreement for identical inputs**. A boolean that disagrees with its
own mirror by 1,129 mm3 is not a measurement of the part. So **the right wing is taken as the mirror
of the verified left** (`s4g_mirror_right.py`): volume 1,343,606.878104189, 1 solid, 143 faces, valid,
bbox exactly the mirror, and `elevon_right ↔ wing` = **0.000000000**. The right's own boolean result is
kept in `out/s4g_mirror.json` as the rejected value, with its volume, so the rejection is auditable.

*(Both results are non-interfering — the right's own cut also measures 0.000000000 — so this changes no
row value. It changes the wing's mass by 1,129.481 mm3 = 1.751 g, which is exactly why it was not
averaged away.)*

### 5d. Three routes that failed, kept as negative results

| route | what happened | how it was caught |
|---|---|---|
| **compound cutter** (the five per-solid offsets fused, then one `Cut`) | `Cut` returned **invalid** geometry: 2 solids, one of them a copy of the cutter, wing volume *larger* after the cut | `nsolids` + `BRepCheck_Analyzer` + the volume identity — never reported as a fix |
| **per-solid offsets of the three hinge pins and the horn** | `PerformBySimple` returns **orientation-flipped** solids for those small shapes; cutting with them removed **55,808.54 mm3** of wing instead of ~860 | the volume identity `vol0 − vol1` and `BRepCheck`; run stopped, not massaged |
| **`cq.Workplane(obj=TopoDS_Solid)`** for the STEP export | wrote a **header-only 1,661-byte STEP** — a part with no geometry | the file size assertion `> 100 kB` and `s4b_roundtrip.py` |

### 5e. The STEP writer does not carry the cove — stated, not hidden

The OCP 7.8 STEP writer **re-heals the 0.500 mm cove**: re-importing `wing_left_relieved.step` returns
volume **1,344,635.639764** (the *pre-cut* value) with 144 faces, and the elevon row reads
**16.264960 mm3** instead of 0. The **BREP** re-imports at **1,343,606.878104**, 1 solid, row
**0.000000000**. So the executed geometry is carried as **BREP** and the closure sweep measures the
BREP operands. **This is a limit of this fix, not a property of the geometry:** before the relieved
wings can be shipped as STEP the writer settings (or the export route) need attention — the same
part shipped as STEP today would carry the interference.

## 6. Executed sweep — new authoritative total

`work/s5_closure.py --tag relieved` → `out/s5_closure_relieved.json`, `log/s5_closure_relieved.log`
(3,028 s). Same population (32 solids-groups = 30 STEPs + 2 code-built beads), same 95
bbox-prefiltered candidates of 496, same 401 bbox-separated and enumerated, same solid-by-solid
algebra, same default fuzzy, same eps 1e-12. **The only difference is the two wing operands**, which
are the relieved ones (BREP, §5e).

| | baseline C-26 | **this run** |
|---|---:|---:|
| part groups | 32 | **32** |
| candidate pairs (of 496) | 95 | **95** |
| bbox-separated, enumerated | 401 | **401** |
| examined and zero | 63 | **65** |
| non-zero rows | 26 | **24** |
| *excluded* envelope↔envelope | 6 / 200,446.177670 | **6 / 200,446.177670** |
| **closure total** | **5,415.519830** | **4,291.527767** |

**Set diff: −2 pairs / −1,123.992063 mm3, +0 pairs, 0 pairs changed in value.**
(`out/s5b_diff.json`: 30 rows SAME, 0 CHANGED, 2 REMOVED, 0 ADDED — including all 14 static-joint rows
and all 8 elevon-clash rows, each reproduced to the printed digit.)

The two removed rows:

| row | baseline | now |
|---|---:|---:|
| `elevon_left ↔ lifting_wing_left_sector` | 561.996031 | **0.000000** |
| `elevon_right ↔ lifting_wing_right_sector` | 561.996031 | **0.000000** |

### 6a. The 24 surviving rows, by population

| population | pairs | mm3 | disposition |
|---|---:|---:|---|
| **A1b** elevon root station — 4 structures per side | **8** | **2,140.555804** | **GENUINE CLASH** — one cause (root at r = 11.250 about the duct axis), remedy +38.485 mm outboard, *not executed* |
| ├ `elevon ↔ motor_R3 envelope` | 2 | 1,256.239728 | 585.708363 panel + 42.411501 hinge pin (100 % buried, per side) |
| ├ `elevon ↔ motor_R2 envelope` | 2 | 499.500726 | 221.778419 panel + 27.971944 pin (per side) |
| ├ `elevon ↔ nozzle shell` | 2 | 240.495128 | the plate crosses the r 38.978…41.000 shell wall |
| └ `elevon ↔ fuselage REV 1` | 2 | 144.320222 | the plate crosses the side wall at x −93.235…−91.468 |
| **C** static joints — 4 interfaces | **14** | **2,146.042809** | **DISPOSITIONED CONTACT** (§3e) |
| ├ collar on duct (J1) | 2 | 1,024.159206 | shrink fit; **bore correction −0.900 mm** |
| ├ vane root in servo bracket (J2) | 4 | 1,032.274334 | clamped root; slot 2.000 × 29.000 mm |
| ├ vane through nozzle exit lip (J3) | 4 | 80.008340 | wall crossing; exit-lip slot |
| └ bead across vane blade (J4) | 4 | 9.600928 | retaining bead; notch |
| **A2** pushrod placeholder | **2** | **4.929154** | **WITHDRAWN** (§4) |
| **total (C-24)** | **24** | **4,291.527767** | |
| *excluded* envelope ↔ envelope | 6 | 200,446.177670 | unchanged, non-parts (`dm-interference-reconcile` §2c) |

**Artefact class: 0 pairs / 0.000000** (was 2 / 1,123.992062).
**Dispositioned contact: 14 pairs / 2,146.042809** — 58.3 % of the pairs and 50.0 % of the volume.
**Genuine clash: 8 pairs / 2,140.555804** — 33.3 % of the pairs and 49.9 % of the volume.
**Withdrawn placeholder: 2 pairs / 4.929154.**

Fit-critical (moving parts only, A1b + A2) = **10 pairs / 2,145.484958 mm3**.

## 7. Invariants re-verified

`work/s6_verify.py` → `out/s6_verify.json`, `log/s6_verify.log`, run on the delivered STEP.

| check | measured | required | |
|---|---|---:|---|
| fuselage volume | **206,454.319709 mm3** | 206,454.319709 | ✔ |
| fuselage mass at 1550 kg/m3 | **320.0042 g** | 320.0042 | ✔ |
| topology | **1 solid / 1 shell / 540 faces**, `BRepCheck` valid | 1 solid / 540 faces | ✔ |
| bbox | x ±105.891846, y −48.458738…45.413633, z −360…280 | ✔ | ✔ |
| sha256 | `d9ba7aeb7716cdd1ba4f289d284944e34e0ebab20202d39335bd9b58ecb9cadf` | unchanged | ✔ |
| wall, fore band | V 67,254.3350 / A_eff 123,170.0573 → **2V/A = 1.0921** | 1.0921 | ✔ |
| wall, pinch band | V 26,262.2633 / A_eff 43,807.5718 → **2V/A = 1.1990** | 1.1990 | ✔ |
| wall, aft band | V 112,937.7213 / A_eff 191,416.3898 → **2V/A = 1.1800** | 1.1800 | ✔ |
| **ring v2 A** | **0.000000 against all 28 parts** (max row 0.000000000) | 0.000000 | ✔ |
| **ring v2 B** | **0.000000 against all 28 parts** (max row 0.000000000) | 0.000000 | ✔ |

The fix is wing-side only: the body was never opened, and the relieved wings' bbox is unchanged
(−260.000000…−80.329704 and its mirror), so the span, the tip and the leading edge are untouched.

## 8. Final one-line statement

> **drone-mech interference (closure basis, post elevon-relief recut): 24 pairs / 4,291.527767 mm3 =
> 8 pairs / 2,140.555804 genuine clash (elevon root station: motor R3 + R2 envelopes, nozzle shell,
> fuselage side wall; one cause, remedy +38.485 mm outboard, not executed) + 14 pairs / 2,146.042809
> dispositioned contact (collar-on-duct shrink fit 1,024.159 with a −0.900 mm bore correction; vane
> root in servo bracket 1,032.274; vane through nozzle exit lip 80.008; retaining bead across vane
> 9.601) + 2 pairs / 4.929154 withdrawn modelling placeholder; the elevon↔wing 1,123.992062 recut to
> 0.000000000 because a non-ruled loft overshoot turned the relief's designed 0.500 mm gap into
> 11.304 mm of interference; ring v2 CLEAN 0.000000; fuselage byte-identical 206,454.319709 mm3 /
> 320.0042 g, walls 1.0921/1.1990/1.1800 | evidence/dm-remaining-26/**

Board row, one cell:

> `interference | 24 pairs / 4,291.527767 mm3 (closure basis) = 8 genuine clash / 2,140.556 + 14 dispositioned contact / 2,146.043 + 2 withdrawn placeholder / 4.929; artefact class now 0 (elevon↔wing recut 0.000000, loft overshoot through a designed 0.500 mm gap); ring v2 CLEAN | fuselage byte-identical | evidence/dm-remaining-26/`
## Appendix — method, provenance, limits

### A. Instrument and provenance

| item | value |
|---|---|
| interpreter | `C:\Program Files\Python312\python.exe` (Python 3.12) |
| CAD kernel | cadquery 2.7.0 / OCP 7.8.1.1 (OpenCASCADE) — no KiCad, no solver involved |
| volume | `OCP.BRepGProp.VolumeProperties_s(shape, props, 1e-12)` — never `Shape.Volume()` |
| booleans | `OCP.BRepAlgoAPI_Common` / `BRepAlgoAPI_Cut`, OCP default fuzzy 0.0, **solid-by-solid** |
| rays | `OCP.IntCurvesFace_ShapeIntersector`, tol 1e-7, lines parameterised 0…900 mm |
| offset | `OCP.BRepOffsetAPI_MakeOffsetShape.PerformBySimple`, 0.500 mm |
| bbox | `OCP.BRepBndLib.AddOptimal_s`, pad 1e-6 mm |
| validity | `OCP.BRepCheck_Analyzer` |
| operands | 30 STEPs copied from `dm-interference-reconcile/work/obj/`, the two wings taken from `dm-body-wing/work/obj_fix/` (trimmed to skin) and, after the fix, from `work/obj_fix2/*.brep`; sha256 of the STEPs in `out/input_sha256.txt` |
| write scope | this directory only. **No repo write, no commit, no reset**; nothing written to `D:\CodeProjects` or `E:\1vm\TMP`. The repo was read only (and `phase15_generate_geometry.py` was read to establish authorship of the relief) |

| script | produced |
|---|---|
| `work/s1_probe.py` → `out/s1_probe.json` | census of all 30 parts + face-level detail of the elevons and the three wing sectors |
| `work/s2_elevon_geom.py` → `out/s2_elevon_geom.json` | elevon root/tip planes; wing aft-chord profile; y-sections; span overhang |
| `work/s2b_cliff.py` → `out/s2b_cliff.json`, `work/s2c_wall_fine.py` → `out/s2c_wall_fine.json` | the 24.9 mm full-height relief wall and its station to 0.0025 mm |
| `work/s3_joints.py` → `out/s3_joints.json` | the 14 static-joint rows with pieces, plus the mating-surface anatomy and the press-fit arithmetic |
| `work/s3b_elevon_rows.py` → `out/s3b_elevon_rows.json` | the 10 elevon rows with pieces and bboxes (total 3,264.547867) |
| `work/s3c_pushrod.py` → `out/s3c_pushrod.json` | the pushrod's own geometry and its two overlap pieces |
| `work/s4_relief_fix.py` → `out/s4_relief_fix.json` | the recut: cutter validation, volume identity, export |
| `work/s4g_mirror_right.py` → `out/s4g_mirror.json` | the right wing as the mirror of the verified left, and the rejected boolean |
| `work/s4f_mirror.py` → `out/s4f_mirror.json` | the symmetry control: aft-surface equality at 7 y × 51 stations |
| `work/s4b_roundtrip.py` → `out/s4b_roundtrip.json` | STEP/BREP round-trip check on the relieved wings |
| `work/s5_closure.py --tag relieved` → `out/s5_closure_relieved.json` | **the full closure sweep on the relieved assembly** |
| `work/s5b_diff.py` → `out/s5b_diff.json` | the row-level set diff against C-26 |
| `work/s6_verify.py` → `out/s6_verify.json` | fuselage invariants + the ring rows on the final assembly |

### B. Stated limits — what this report does not establish

1. **The fix is carried as BREP, not STEP.** The OCP 7.8 STEP writer re-heals the 0.500 mm cove: a
   re-imported STEP returns the pre-cut volume and a 16.264960 mm3 row (§5e). The geometry is right;
   the STEP export route is not, and is named as work rather than claimed as done.
2. **The right wing is the mirror of the left, by a stated control.** The right's own boolean removed
   1,129.481 mm3 more than its mirror for identical operands; the mirror is adopted and the rejected
   value is published (§5c). The discrepancy is therefore *neutralised*, not *diagnosed*: the ray
   census that should localise it returns only the forward surface beyond |x| = 125 mm on the cut
   shape, so no station-level account of the extra 1,129 mm3 is offered.
3. **The eight genuine-clash rows are classified, not fixed.** Their remedy (`+38.485 mm` outboard
   re-station, measured 0.000000000 on all four row classes) is a design change to the deliverable's
   control-surface station and is not executed here.
4. **The fourteen contact rows are dispositioned, not corrected.** The bracket slot, the exit-lip
   slot, the bead notch and the collar bore (−0.900 mm) are named operations; none of them is modelled
   in this wave.
5. **The two D84.0 beads are code-built** (`BEAD_RO 42.0 / BEAD_RI 41.0 / z 243.8 / len 1.20`), carried
   as in every prior sweep; their four rows have no STEP to cross-check.
6. **The eight motor-envelope rows use the repo's Ø42 × 72 envelopes.** The sourced can is Ø36 × 70
   (`fab-dm-final` §8.3), so those volumes would fall if the envelope were corrected; the *pair count*
   would not change.
7. **Masses are geometric** at 1550 kg/m³; no layup, ply drop or fastener.
8. **The three band walls are measured on the delivered STEP only** — no faired-body variant was cut.

### C. Arithmetic self-check

| identity | value | residual |
|---|---|---:|
| A1b 1,070.277902 × 2 | 2,140.555804 | 0 |
| C1 512.079602535 × 2 | 1,024.159205 | 1e−6 (printed rows give 1,024.159206) |
| C2 320.137167 × 2 + 196.000000 × 2 | 1,032.274334 | 0 |
| C3 20.002085 × 4 | 80.008340 | 0 |
| C4 2.400232349 × 4 | 9.600928 | 0 |
| C1+C2+C3+C4 | 2,146.042807 | vs 2,146.042809: **2 × 10⁻⁶**, printed-row rounding |
| A1a 561.996031 × 2 | 1,123.992062 | 0 (both sides 561.996031007 and …009) |
| A2 2.464576819 × 2 | 4.929154 | 0 |
| 1,123.992062 + 2,140.555804 + 2,146.042809 + 4.929154 | 5,415.519829 | vs 5,415.519830: **1 × 10⁻⁶** |
| 5,415.519830 − 1,123.992062 | **4,291.527768** | 0 |
| 2,140.555804 + 2,146.042809 + 4.929154 | 4,291.527767 | same 1 × 10⁻⁶ |
| 2 × 1,028.761660 mm3 × 1.55e−3 g/mm3 | 3.1892 g | — |
| 1,344,635.639764 − 1,343,606.878104 | 1,028.761660 | 0 |

