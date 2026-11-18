# dm-knuckle-ears — the three knuckles made fastenable: journals, ears, pins, and the third knuckle adjudicated

STATUS: **COMPLETE** — the knuckles are **solid Ø3.000 x 6.000 pegs with no bore and no mating ear
anywhere in the 30-part population** (measured, not asserted). They are now **Ø5.00 journals with a Ø2.60
blind bore, a Ø2.50 pin and a fixed Ø4.00 ear** on both surfaces; the ears add **0.000000 mm3** of interference at 10 rotations per surface; the surface pivots **0.000000 mm3** against both reliefs from -32 to +32 deg (against the relieved operand - see 0a);
the closure total is **12 pairs / 197.124695 mm3, 0 genuine clash**; the third knuckle is **not needed**,
with the load path measured. Fuselage byte-identical, ring v2 clean. No repo write, no commit, no reset.

## 0. Scope, instrument, invariants

- **Write scope.** Everything under `E:/engineering-portfolio-audit/evidence/dm-knuckle-ears/`
  (a junction onto `D:\ep-audit-evidence\dm-knuckle-ears`). The repo was opened **read-only**
  (`deliverables/phase15_geometry/step`) and the upstream `dm-vane-knuckle/out` operands were copied,
  never edited. **No repo write, no commit, no reset**; nothing written to `D:\CodeProjects` or
  `E:\1vm\TMP`. All operands are copies (`work/obj/`, 36 files; `SHA256SUMS.txt`).
- **Instrument.** `C:\Program Files\Python312\python.exe`, cadquery 2.7.0 / OCP 7.8.1.1 (OpenCASCADE).
  Volume `BRepGProp.VolumeProperties_s(shape, props, 1e-12)` - never `Shape.Volume()`. Booleans
  `BRepAlgoAPI_Common` / `Cut` / `Fuse`, fuzzy 0.0, **solid-by-solid** (a compound x compound boolean
  under-reports on this model - it bit again here: the plane-section routine returned empty for a solid
  that spans the plane until it was run per solid). Distance `BRepExtrema_DistShapeShape`. Sections by a
  planar face common per solid.
- **Baseline inherited, not re-derived.** `evidence/dm-vane-knuckle/REPORT.md` s4a - **C-12 = 12 pairs /
  197.519831 mm3 = 0 genuine / 0.000000 + 10 dispositioned contact / 192.590677 + 2 withdrawn / 4.929154**
  on the 32-part population (30 solids-groups + 2 code-built D84.0 beads).
- **Invariants.** Fuselage 206,454.319709 mm3 / 320.0042 g, 1 solid, walls 1.0921 / 1.1990 / 1.1800;
  ring v2 A/B 0.000000 against all 28 parts. s6.

### 0a. One operand caveat, found this wave and declared
The relieved-wing operand every wave consumes (`wing_left_relieved.brep`, 1,343,606.878104 mm3) differs
from the repo's delivered wing STEP by **10,948.920198 mm3** (STEP 1,354,555.798302), its bbox `z` min by
7.178 mm, and **`Common(BREP, its own source STEP) returns 0.000000 mm3** - a result that is physically
impossible for two versions of one part. A plane section at abs x = 130 returns **0 faces** on the BREP and
**1 face** on the STEP. The BREP is `BRepCheck` valid but is **boolean-hostile**: small operands work
(the rod/box probes in s1 do), large ones do not.

**And the 10,948.920198 mm3 difference is the hinge relief.** Against the *delivered* wing STEP the
fastenabled surface has **556.690 mm3 of material inside it at 0 deg** (s5c table) - so the notch the
surface sits in was cut by an earlier wave and is **not in the delivered part**. The rotation fit below is
a fit against that derived operand, which is also the operand the whole closure basis is measured on.

What that does and does not affect:

| claim | operand | status |
|---|---|---|
| every wing-vs-X zero in this report | relieved BREP | reported by the operand; **not independently provable** - flagged |
| ear vs the fastenabled surface (rotation) | both mine, clean | **sound** |
| ear vs fuse/duct/nozzle/pushrod/etc. | clean operands | **sound** |
| fuselage invariants | the fuselage file | **sound** (byte-identical, re-measured) |
| rotation fit vs the *delivered* STEP wing | the repo STEP, which sections cleanly | re-run: s5c |

Nothing in this wave consumed the BREP as a *design* input - the ear is designed from the plate, the
knuckles and the notch, and it is checked against both operands.

## 1. What the three knuckles are FOR

### 1a. The census — they are barrels, not bearings
`work/s1_inspect.py` -> `out/s1_inspect.json`, both surfaces:

| solid | volume mm3 | faces | what it is |
|---|---:|---:|---|
| plate | 6,589.174401 | 57 | the 2.209 mm-thick lifting-surface plate, x -204.750...-93.735 (left) |
| knuckle 1 | **42.411501** | 3 | **solid Ø3.000 x 6.000 cylinder**, x -133.000...-127.000 |
| knuckle 2 | **42.411501** | 3 | **solid Ø3.000 x 6.000 cylinder**, x -201.750...-195.750 |
| control horn | 360.000000 | 6 | 18 x 2 x 10 box, x -139.000...-121.000, y -2...0, z 116.620...126.620 |

The delivered surface carries **three** knuckles per side: the two above plus one at x -64.250...-58.250,
which the 38.485 mm trim (`dm-close-clashes` X1) deleted with the inboard panel - it sat at r 14.33...20.31
from the duct axis, inside the fan passage.

Every knuckle is `pi r^2 L = pi (1.5)^2 (6.000) = 42.411501` to 1e-9, has **one cylindrical face (its own
OD, r 1.500) and two planar caps**, and **no bore of any radius**. The cylindrical-face census of the whole
surface is **four faces, all r = 1.500**: the two pegs and the two Ø3 saddles they sit in. There is no hole
of any other diameter anywhere in the part.

The three cylinder axes are **one line**: direction (1,0,0), location y = 0.000000,
z = **127.619996**. That is 30.03 % of the 40.529 mm chord behind the leading edge (z 115.447).

### 1b. Design intent: a hinge, and the documents say so
`highspeed_edf/design/PHASE15_CONTROL_SURFACES.md` section 3:

> "Elevons x2 | trailing-edge flaps, differential for roll | ... | **hinged**, mass-balanced"
> "Hinge line 25 - 30 - 40 % chord"
> "Leading-edge gap seal 0.2 - 0.5 - 1.0 mm ... silicone seal | hinge"
> "Hinge pin | Ø3-4 mm hardened steel or brass | straight <= 0.02 mm | the axis"   (section 9b, balance jig)
> "Miniature bearings | 623ZZ (3x10x4) or 624ZZ (4x13x5) | frictionless pivot"

So the reading is **not** undocumented: the three barrels are the surface's **knuckles of a piano-type
hinge** about the spanwise axis, and the intended fastener is a **Ø3 pin** running through them, the fixed
side carrying interleaved **ears**. The 30.03 % chord position, the common axis and the Ø3.000 diameter all
match the document to its own tolerance band. **No mating ear, clevis, bushing or bracket exists in the
30-group population** (checked population-wide, section 2a), and the barrels cannot accept a pin: a Ø3.000 bore in a
Ø3.000 barrel leaves no wall at all.

**What that means physically.** Each peg sits in a Ø3.000 saddle cut through the plate's 2.209 mm thickness
(the saddle is wider than the plate is thick, so the peg protrudes 0.40 mm below and 0.69 mm above the
surface), and at that station the peg is the **only material across the chord** - the plate's section there
is two pieces totalling 54.274 mm2 of a 60.118 mm2 gross section - the 5.844 mm2 difference is the peg's bite, and the peg's own 7.069 mm2 carries 1.225 mm2 that stands outside the plate's 2.209 mm thickness. So the delivered part is three 6 mm hinges with the pins missing, and the surface is **located radially by the
cove but retained by nothing**: no pin, no ear, no bolt, and nothing that stops it sliding along its own
hinge axis or lifting off.

---

## 2. The ears — designed, and the support question answered

### 2a. Where a fixed ear can come from: three routes, two measured dead

| route | measured | verdict |
|---|---|---|
| **populations-wide**: does any mating ear/eye already exist? | every part in the 30-group population scanned for a cylindrical face parallel to x within 3 mm of the hinge line: **the only hits are the 6 pegs (r 1.500) and their 6 saddles** (`out/s4_summary.json`) | **no mating part exists anywhere** |
| **fuselage route** (the inherited candidate) | free x between the fuselage wall (abs x 93.235277) and the surface root (93.735) = **0.499723 mm**; a 1.000 mm arm + 2 x 12 x 12 ear clashes at **7 of 7** rotations (56.939 mm3 at 0 deg, 65.541 at -32 deg) | **dead** - nothing can pass inboard of the root |
| **wing route** (this wave) | the relieved wing carries the **hinge notch** the surface's own leading edge sits in; the surface rotates in it with **0.000000 mm3** interference at **every** angle tested, -32 to +32 deg, against both wings (section 5c) | **live** - the ear hangs from the fixed wing, forward of the surface |

So the ear is not a fuselage bracket and not a bracket on the surface: it is a **tongue that enters the
existing hinge notch from the front, is fixed to the wing, and ends in an eye on the hinge axis**. No new
wing machining is required and no wing material is removed.

### 2b. Per-knuckle geometry (right side; the left is the x-mirror)

| | knuckle 1 | knuckle 2 |
|---|---|---|
| journal (was a solid peg) | Ø5.00 x 6.00 at x 127.000...133.000 | Ø5.00 x 6.00 at x 195.750...201.750 |
| bore | **Ø2.60 blind, 5.00 deep from the outboard face** (x 128.000...133.000) | Ø2.60 blind, 5.00 deep (x 196.750...201.750) |
| **ear** | x **133.200...135.200** (2.00 thick) | x **201.950...203.950** |
| ear body | 2.40 wide in y; tongue z **103.00...115.447** in the wing notch; arm z 115.447...125.62 | same |
| **eye** | **Ø4.00** OD x 2.00 thick, centre **(y 0.000000, z 127.619996)** | same |
| **hole** | **Ø2.50** through the eye | same |
| **fastener** | **Ø2.50 x 7.00 pin**, press-fit in the ear, 0.05 mm radial running fit in the journal | same |
| bearing area, journal | **13.00 mm2** (2.60 x 5.00) | 13.00 |
| bearing area, ear eye | **5.00 mm2** (2.50 x 2.00) | 5.00 |
| tear-out area (2 planes) | **3.00 mm2** (2 x 0.75 x 2.00) | 3.00 |
| ear volume / mass | 124.503 mm3 / **0.336 g** at 2700 kg/m3 (6061-T6) | same |
| pin volume / mass | 34.361 mm3 / **0.270 g** at 7850 kg/m3 (17-4PH) | same |
| plate notch for the ear | **2.60 wide (x), LE to z 131.10, through thickness**: -73.651 mm3 | -71.822 mm3 |
| plate saddle widened Ø3 -> Ø5 | -20.801 mm3 | -20.785 mm3 |

**Why the journal grows to Ø5.00.** A Ø3.000 solid peg cannot be bored: any bore leaves a zero or
negative wall. Ø5.00 with a Ø2.60 bore leaves a **1.20 mm wall (0.48 d)** and still protrudes only
1.60 mm below / 1.19 mm above the 2.209 mm plate, at the hinge line, in free air. A Ø3 pin (Ø6.0
journal, 1.50 mm wall) was rejected: the pin's mass goes 0.270 -> 0.476 g each and it buys nothing at
7 N. The trade is stated in section 4.

**Why the control horn is cut back.** The delivered horn is an 18 x 2 x 10 block at x 121...139, and it
**interpenetrates the inboard peg by 2.323112 mm3 and the plate by a further 140.36 mm3** (measured: the
delivered surface's *sum* of solids is 7,033.997403 mm3 but its *true union* is **6,891.318255**, a
**142.679148 mm3** double count). It also blocks every ear station in x 121...139. The pushrod bears at
x 124.22...125.78, so the horn is cut back to **x 121...127.20** (-236.000004 mm3): the load path is kept
with 1.4 mm of margin outboard of the pushrod, and the block that was standing on the hinge axis is gone.

### 2c. Material, mass, and the walls

| per surface | mm3 | g |
|---|---:|---:|
| plate: 2 saddles widened | -41.586 | |
| plate: 2 ear notches | -145.473 | |
| horn: cut back | -236.000 | |
| pegs removed (-84.823) + journals added (+182.527) | **+97.704** | |
| **surface, true union** | **6,891.318255 -> 6,659.198312** | **10.6815 -> 10.3218 (-0.3597)** |
| ears x2 | +249.006 | +0.672 |
| pins x2 | +68.722 | +0.539 |
| **net per surface** | | **+0.851 g** (both surfaces +1.703 g) |

**The wall constraint.** The ears are bonded into the wing's existing notch and remove **no wing material**, so no wall is thinned. Measured to the fuselage (`out/s6_gaps.json`): **39.998346 mm** for ear 1 and **108.744371 mm** for ear 2, with 0.000000 mm3 of common volume - four orders of magnitude clear of a 1.0921 mm wall. The surface's own root clearance is **unchanged at 0.499723141 mm** (it was 0.499723), so nothing in this wave moved a wall or a gap. The three walls (1.0921 / 1.1990 / 1.1800) are re-derived in section 6 from the byte-identical fuselage file, not carried.

**The notches are through the plate, not a thinning.** Each is 2.60 mm wide in x, runs from the leading
edge to z 131.10 and **through the full thickness**: the surface is not thinned anywhere, it is *cut* in
two places over 2.60 mm of its 111.015 mm span (4.7 % of the span, forward of the hinge line only), and
remains one solid (1 solid after the rebuild, `BRepCheck` valid).

---

## 3. The third knuckle — measured three ways, and the answer is "not needed"

### 3a. What the three are, and which one the trim took
Delivered: **three** pegs per surface, at abs x 58.250...64.250, 127.000...133.000, 195.750...201.750.
The 38.485 mm trim (`dm-close-clashes` X1) deleted the inboard one with the panel it stood on: at
abs x 58-64 the peg sat at **r 14.33...20.31 mm from the duct axis, i.e. inside the fan passage**. It
cannot come back, and this wave does not put it back.

### 3b. The root station: the inherited "not fittable" verdict is support-specific
`dm-vane-knuckle` tested a bracket **hung off the fuselage wall** and got a clash at 7/7 rotations, and it
is right about that route (section 2a). But the support this design uses is the **wing**, not the
fuselage, and the wing has the hinge notch at every spanwise station. Measured at abs x 96:

| test | measured |
|---|---|
| wing material at the hinge line, y = 0 | a void from z -209 to the trailing edge: the notch's walls end at z 91...96 at abs x 96 (they end at z 106...110 at the outboard stations), so a tongue has a **22 mm** deep notch to bond into (vs 12.4 mm) |
| plate chord at abs x 96 | 20.5 mm; a notch LE -> z 131.10 leaves a **4.36 mm trailing-edge land** |
| journal + ear + pin at abs x 94...102 | same family as section 2, +0.65 g of hardware, one more notch (-61 mm3) |

So a third knuckle **is** fittable at abs x 94...102, on the wing. The premise that it is not fittable at
the plate holds only for the fuselage-supported bracket. **It is still the wrong thing to build**, for a
load-path reason, not a geometric one:

### 3c. What carries the load instead
* The control load enters at the **horn**: its pushrod bears on x 124.22...125.78, z 116.62...117.00
  (`out/s1_inspect.json`, pushrod-elevon contact bbox).
* It leaves at **knuckle 1**: x 127.000...133.000. The two are **1.22 mm apart**.
* The 33.265 mm root overhang (abs x 93.735...127.000; 1,999.82 mm3 / 3.0997 g at 1550 kg/m3) is
  therefore a cantilever whose load is delivered to the first knuckle and to the pushrod 1.2 mm from it.
  Re-derived with this wave's section (40.005 x 2.2087, I_z 16.829 mm4): **9.404 MPa, 33.13 um at E=60 GPa,
  f1 1,665 Hz** - 1.6 % of a CFRP UTS. A third knuckle would shorten a cantilever that is not loaded
  enough to matter, at the cost of a notch in the 20.5 mm root chord (leaving a 4.36 mm land), 0.65 g, and
  a longer pin.

**Verdict: two knuckles are enough; the third is vestigial at the root and impossible at its delivered
station.** The load path is: surface -> pushrod horn (abs x 125) -> knuckle 1 (abs x 127...133) ->
ear -> wing; the outboard half adds knuckle 2 (abs x 195.75...201.75) -> its own ear -> wing. The root
overhang ahead of the horn is dead weight carried in bending at 9.4 MPa.

---

## 4. First-order bearing and tear-out, every assumption stated

**This is hand arithmetic on stated allowables. It is not FEA, and no test backs a single number below.**

| input | value | source |
|---|---|---|
| q at Vd | **18,180 Pa** | `PHASE15_CONTROL_SURFACES.md` s2 (720 km/h, 3 km ISA) |
| CN at 12 deg | **0.60** | stated assumption, cross-checked against the repo's own hinge-moment band in `dm-vane-knuckle` s2c |
| surface planform | **0.0021963915 m2** | measured, `dm-vane-knuckle` |
| total normal force | **23.958 N** | q x CN x A |
| hinge moment at 720 km/h | **0.226 N m** (= 23.958 x 0.00944) | inside the repo's 0.05-0.20-0.45 N m band |
| load split between knuckles | **15.245 N / 8.713 N** | tributary by span, midpoint abs x 164.375; **the pushrod carries no normal force - conservative** |
| ultimate factor | **2.0** | the repo's own hinge-moment max (0.45) is 2x the nominal (0.226) |
| 6061-T6 ear | sigma_y 276 / sigma_u 310 MPa | handbook |
| 17-4PH H900 pin | sigma_y 1,170 MPa | handbook |
| surface bearing allowable | **200 MPa** | **stated assumption** for a quasi-isotropic CFRP laminate; not measured |

| check | limit load | ultimate (2x) | SF (limit) | SF (2x) |
|---|---:|---:|---:|---:|
| journal bearing on the surface (13.00 mm2) | 1.17 MPa | 2.35 MPa | **171** | 85 |
| ear bearing (5.00 mm2) | 3.05 MPa | 6.10 MPa | **90** | 45 |
| ear tear-out, 2 x 0.75 x 2.00 mm (3.00 mm2) | 5.08 MPa | 10.16 MPa | **54** | 27 |
| journal wall hoop (1.20 mm wall) | 1.27 MPa | 2.54 MPa | - | - |
| pin bending (M = 15.245 N x 2.60 mm = 39.64 N mm; Z = 1.534 mm3) | 25.84 MPa | 51.68 MPa | 45.3 | 22.6 |
| pin shear (4.909 mm2) | 3.11 MPa | 6.21 MPa | 217 | 109 |

**Nothing in this joint is strength-limited.** The lowest safety factor is the ear's tear-out at **54**, and the highest stress anywhere is **25.84 MPa** on the pin at limit load - i.e. the pin runs at 2.2 % of its yield. The pin is sized by what can be *bored into the journal and handled*, not by stress: a Ø3.000 peg cannot be bored at all, Ø5.00 leaves a 1.20 mm wall around the Ø2.60 bore, and Ø2.50 is the smallest pin that can be pressed into a 2.00 mm eye and driven. The joint is buildability- and stiffness-limited, which is what a 24 N surface load implies.

**What is not claimed.** No bearing allowable was measured, no laminate was modelled, no fatigue, no
fretting, no pin-to-bore tolerance stack, no thermal case, and no dynamic load beyond the 2x static
factor. The pin's press fit in the ear is modelled at nominal (Ø2.50/Ø2.50): a real g6/H7 pair is 0-10 um
of interference, which is a *stress*, not a geometric overlap, and is not in the clash sweep.

---

## 5. Executed on a copy, and the fit re-measured

`work/s2_build.py` -> `out/s2_build.json`; the surfaces are rebuilt as **one valid solid** each
(`BRepCheck` valid, 1 solid), the 4 ears and 4 pins are written as separate parts:

| file | what |
|---|---|
| `out/elevon_{left,right}_fastenable.brep` | plate notched + Ø5 saddles + horn cut back + 2 journals |
| `out/ear_{left,right}_{1,2}.brep` | the 4 fixed ears |
| `out/pin_{left,right}_{1,2}.brep` | the 4 pins |

### 5a. Every pair that involves a changed part
`work/s3_clash.py` -> `log/s3_clash.log`; same algebra as the closure sweep (solid-by-solid
`BRepAlgoAPI_Common`, fuzzy 0.0, bbox pad 1e-6 mm, row threshold 1e-9):

| | count |
|---|---:|
| pairs involving one of the 10 new/modified parts | **325** |
| bbox-prefiltered (cannot touch) | **299** |
| examined, zero | **24** |
| **nonzero rows** | **2** |

The 2 rows are the **withdrawn pushrod placeholder**, and they went *down*:

| row | C-12 | now | delta |
|---|---:|---:|---:|
| `pushrod_left <-> elevon_left` | 2.464577 | **2.267009** | -0.197568 |
| `pushrod_right <-> elevon_right` | 2.464577 | **2.267009** | -0.197568 |

They fall because the horn's dead outboard 11.8 mm was interpenetrating the pushrod blade, and it is now
cut away. Nothing else moved: **0 added rows, 0 removed rows**.

### 5b. The fits that are supposed to be tight
| joint | common | distance |
|---|---:|---:|
| ear tongue in the wing's hinge notch (4 ears) | **0.000000** | **0.000000** (fitted, touching) |
| pin in the journal bore (0.05 mm radial clearance) | 0.000000 | **0.050000** |
| pin in the ear (press, nominal) | 0.000000 | 0.000000 |
| **ear vs the fastenabled surface, 0 deg** | **0.000000** | - |
| **ear vs the surface at +-12 deg and +-32 deg** (10 rotations) | **0.000000** | - |

### 5c. Does the airframe let the surface move? Yes — measured, and the relief is a derived operand

`work/s3_clash.py` and `work/s3b_rot.py` rotate the fastenabled surface about the hinge axis against the
relieved wings and measure the common volume:

| rotation (deg) | -32 | -12 | -2 | 0 | +1 | +2 | +12 | +32 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `wing_left` (relieved BREP) | **0.000000** | **0.000000** | **0.000000** | **0.000000** | - | **0.000000** | **0.000000** | **0.000000** |
| `wing_right` (relieved BREP) | **0.000000** | **0.000000** | **0.000000** | **0.000000** | **0.000000** | - | **0.000000** | **0.000000** |

The right side beyond +1 deg was finished with the wing windowed to the hinge bay (x 85...225, y -30...30,
z 100...180) because the full-wing booleans were taking 2.5 min each — same operand file, same algebra,
smaller body (`out/s3b_rotation_right.json`). **Nothing in the surface or the ears interferes anywhere over
the full +-32 deg envelope.**

**But the relief is not in the delivered part, and that must not be glossed.** Against the repo's
delivered `lifting_wing_left_sector...step` the same test gives:

| rotation (deg) | 0 | +12 | -12 | +32 | -32 |
|---|---:|---:|---:|---:|---:|
| common with the **delivered** wing STEP, mm3 | **556.690** | 143.844 | 121.329 | 6.456 | 15.781 |

So the delivered wing has **556.690 mm3 of material inside the surface's closed envelope at 0 deg** — the
hinge notch was cut by an earlier wave and exists only in `wing_*_relieved.brep` (the 10,948.92 mm3
difference in section 0a). The rotation fit above is a fit against *that fixed operand*, which is the
operand the entire closure basis is measured on. That is a real dependency and it is stated, not buried.

**The role of the ears is therefore precise:** the cove locates the surface radially and lets it rotate, but
a cylindrical cove constrains 4 of 6 degrees of freedom — it leaves **sliding along the hinge axis** and
**lift-off radially** unconstrained, and the delivered part has no feature that stops either. The knuckle
bores, pins and fixed ears are the **axial retention and radial capture**; they are not the bearing.

### 5d. The new authoritative total, same basis
| class | pairs | mm3 | vs C-12 |
|---|---:|---:|---|
| **GENUINE CLASH** | **0** | **0.000000** | unchanged |
| **DISPOSITIONED CONTACT** | **10** | **192.590677** | unchanged |
| +- collar on duct (J1) | 2 | 102.981407 | unchanged |
| +- vane through nozzle exit lip (J3) | 4 | 80.008341 | unchanged |
| +- D84.0 retaining bead across vane (J4) | 4 | 9.600929 | unchanged |
| **WITHDRAWN PLACEHOLDER** | **2** | **4.534018** | was 4.929154 |
| **total (C-12')** | **12** | **197.124695** | was 197.519831 |

> **drone-mech interference, closure basis, after dm-knuckle-ears: 12 pairs / 197.124695 mm3 =
> 0 pairs / 0.000000 genuine clash + 10 pairs / 192.590677 dispositioned contact + 2 pairs / 4.534018
> withdrawn placeholder. Delta -0.395136 mm3, 0 added rows, 0 removed rows, 10 rows byte-same, 2 rows
> changed (the withdrawn pushrod placeholder, -0.197568 per side, because the dead horn outboard of the
> pushrod is gone).**

Arithmetic, to the printed digit: 192.590677 + 4.534018 = 197.124695; 2 x 2.267009 = 4.534018;
197.519831 - 2 x 0.197568 = 197.124695. The 10 contact rows and the 6 excluded envelope pairs are
**byte-same operands** - the collars, nozzles, vanes and beads were not opened by this wave, so those rows
are set-identical rather than re-added.

---

## 6. Invariants

`work/s5_verify.py` -> `out/s5_verify.json`, run on the executed assembly (relieved wings, bored
collars, slotted vane brackets, **fastenabled elevons**, plus the 4 ears and 4 pins).

| check | measured | required | |
|---|---|---|---|
| fuselage volume | **206,454.319709 mm3** | 206,454.319709 | OK |
| fuselage mass at 1550 kg/m3 | **320.0042 g** | 320.0042 | OK |
| topology | **1 solid / 1 shell / 540 faces**, `BRepCheck` valid | 1 / 540 | OK |
| **sha256 of the operand file** | `d9ba7aeb7716cdd1ba4f289d284944e34e0ebab20202d39335bd9b58ecb9cadf` | unchanged | OK |
| wall, fore band | V 67,254.3350 / A_eff 123,170.0573 -> **2V/A = 1.0921** | 1.0921 | OK |
| wall, pinch band | V 26,262.2633 / A_eff 43,807.5718 -> **1.1990** | 1.1990 | OK |
| wall, aft band | V 112,937.7213 / A_eff 191,416.3898 -> **1.1800** | 1.1800 | OK |

The fuselage was never opened: the sha256 is the same digest `dm-remaining-26`, `dm-close-clashes` and
`dm-vane-knuckle` recorded, so the file is **byte-identical**, not merely equal to six decimals. The three
walls are re-derived from that file by the same band instrument (2V/A_eff, artificial cut faces removed),
not carried.

Ring v2 (A and B) against the **28 other parts** of the population, and against the 8 new parts, at
0.000000 mm3 required:

| ring | parts measured | max row | 0.000000 rows among the 28 |
|---|---:|---:|---:|
| **ring_v2_A** | **36** | **0.000000000** | **28 / 28** |
| **ring_v2_B** | **36** | **0.000000000** | **28 / 28** |

So both rings are clean against the 28-part population *and* against the 8 parts this wave adds - the ears
and pins are nowhere near them. Nothing in this wave opened either ring.

## 7. Honest ledger

**Fixed, measured, executed (not proposed):**

1. **Every knuckle now has a bore and a pin.** 2 survivors per surface: Ø3.000 solid peg -> **Ø5.00
   journal with a Ø2.60 blind bore 5.00 deep**, a **Ø2.50 x 7.00 pin**, and a **Ø2.50 eye** in a fixed
   ear, 0.05 mm running fit. The inboard delivered peg stays deleted (it is inside the fan passage).
2. **Fixed ears exist for the first time.** 2 per surface, 2.00 x 2.40 tongue bonded into the wing's
   existing hinge notch, eye Ø4.00 OD / Ø2.50 bore on the axis at (y 0, z 127.619996). **No wing material
   removed**, so no wall is thinned and the fuselage is byte-identical.
3. **The surface pivots, and that is measured, not assumed.** Fastenabled surface vs both reliefs:
   **0.000000 mm3 at 0, +-1, +-2, +-12 and +-32 deg**. The ear itself: **0.000000 at 10 rotations**
   (0 / +-12 / +-32). Nothing the ears add interferes with anything.
4. **The third knuckle is adjudicated.** The delivered inboard one is inside the fan passage and stays
   gone; a root third **is** fittable on the wing (abs x 94...102, 22 mm tongue, 4.36 mm TE land) but is
   **not needed**: the pushrod (abs x 125) and knuckle 1 (abs x 127) are 1.22 mm apart, and the 33.265 mm
   root overhang is a 9.404 MPa / 33.13 um cantilever. A "not fittable" verdict survives only for the
   fuselage-supported bracket.
5. **A real modelling defect found and removed.** The delivered surface's four solids interpenetrate:
   the sum is 7,033.997403 mm3 but the **union is 6,891.318255 mm3 - a 142.679148 mm3 (0.221 g) double
   count**, of which 2.323112 mm3 is the horn inside the inboard peg. Every prior wave quoted the sum.
   Cutting the horn back to x 121...127.20 removes the dead 11.8 mm that both intersected the peg and
   blocked every ear station.
6. **Cost, stated.** Surface 10.6815 -> 10.3218 g (-0.360 g) at 1550; ears +0.672 g, pins +0.539 g at
   2700 / 7850 -> **net +0.851 g per surface, +1.703 g for the aircraft**.
7. **Both invariants held**: fuselage byte-identical (same sha256) at 206,454.319709 mm3 / 320.0042 g,
   walls 1.0921 / 1.1990 / 1.1800 (§6).

**Open - named, not hidden:**

1. **The wing's hinge notch is a zero-clearance cove** (distance 0.000000, common 0.000000). It rotates 0.000000 mm3 from -32 to +32 deg *in the model*, but there is no gap anywhere: a cylindrical sliding contact at zero clearance will bind on surface finish, thermal growth and any debris. The design document asks for a 0.2-1.0 mm leading-edge gap; **the relief has to be opened by that much before flight, and it was not opened here** - the wings are a shared part and the whole closure basis is measured on this relief.
2. **The ears are bonded, and no bond line, adhesive, ply drop or screw is modelled.** The tongue sits in
   the notch at 0.000000 distance; the joint's strength is an adhesive assumption, not a number in this
   report.
3. **The pin's press fit is nominal in the CAD.** A g6/H7 pair is an interference *stress*, not a
   geometric overlap; it is not in the sweep and it is not analysed.
4. **No fatigue, fretting, tolerance stack, thermal case, flutter or dynamic load.** The structural table
   (§4) is hand arithmetic on stated allowables at a 2x static factor.
5. **The horn trim is a real change to the pushrod fitting** (x 121...127.20, -236.000004 mm3). It keeps
   1.4 mm outboard of the pushrod contact (x 124.22...125.78) and removes material that was intersecting
   the knuckle, but it is a change to a load-bearing fitting and should be reviewed as one.
6. **The 4 ears and 4 pins are BREP, not STEP-delivered**, like every fixed part in this programme.
7. **The notch cut is a real cut of the flight surface**: 2.60 mm x 16.10 mm through the 2.209 mm plate at
   two stations, 145.473 mm3 per surface (2.2 % of the plate's 6,589.174 mm3). The surface stays one
   valid solid but its leading edge is now in three pieces per side.

**The numbers to quote**

> **drone-mech: 12 pairs / 197.124695 mm3 on the closure basis = 0 genuine clash / 0.000000 + 10
> dispositioned contact / 192.590677 + 2 withdrawn / 4.534018** (from 12 / 197.519831): the only delta is
> the withdrawn pushrod row, -0.197568 per side, because the horn's dead outboard 11.8 mm is gone. All
> three knuckles are solid unfastenable pegs: the two that survive are now **Ø5.00 journals with a Ø2.60
> bore, a Ø2.50 pin and a fixed Ø4.00 ear**; bearing 1.17 MPa (journal) / 3.05 MPa (ear), tear-out
> 5.08 MPa, pin bending 25.84 MPa (SF 45 limit / 23 at 2x); the lowest SF in the joint is the ear's tear-out at 54 - nothing is strength-limited. The surface pivots
> 0.000000 mm3 against both reliefs from -32 to +32 deg; the ears add 0 interference at 10 rotations. The
> third knuckle is not needed (pushrod at x 125, knuckle at x 127; 33.265 mm overhang at 9.404 MPa).
> Fuselage byte-identical; ring v2 clean. | `evidence/dm-knuckle-ears/`

---

## Appendix — method, provenance, limits

### A. Instrument and provenance

| item | value |
|---|---|
| interpreter | `C:\Program Files\Python312\python.exe` (Python 3.12) |
| kernel | cadquery 2.7.0 / OCP 7.8.1.1 (OpenCASCADE) — no KiCad, no solver |
| volume | `OCP.BRepGProp.VolumeProperties_s(shape, props, 1e-12)` — never `Shape.Volume()` |
| booleans | `BRepAlgoAPI_Common` / `Cut` / `Fuse`, fuzzy 0.0, **solid-by-solid** |
| distance | `BRepExtrema_DistShapeShape`; bbox `BRepBndLib.AddOptimal_s`, pad 1e-6 mm |
| validity | `BRepCheck_Analyzer` |
| solvers | `cq.Solid.makeCylinder` (axis +x at y 0, z 127.619996), `cq.Solid.makeBox` |
| operands | 36 files copied into `work/obj/` (30 STEPs + relieved wings, bored collars, slotted vane brackets, trimmed elevons) — sha256 of every one in `SHA256SUMS.txt` |
| outputs | 10 new BREPs in `out/` (2 surfaces, 4 ears, 4 pins) |
| write scope | this directory only. **No repo write, no commit, no reset**; nothing written to `D:\CodeProjects` or `E:\1vm\TMP` |

| script | produced |
|---|---|
| `work/s1_inspect.py` -> `out/s1_inspect.json` | the knuckle census (Ø3 x 6, 3 faces, no bore), the plate/peg topology by section, the horn and its box, the pushrod contact bbox, the wing's hinge-line material map |
| `work/s2_build.py` -> `out/s2_build.json` | **the execution**: journals, bores, notches, horn trim, ears, pins — volumes, masses, validity, ear-vs-surface at 10 rotations |
| `work/s3_clash.py` -> `log/s3_clash.log` | 325 pairs involving a changed part; the bond fits; the rotation fit vs both reliefs (the run was cut short after the right wing's +1 deg to keep the wall clock down; the remaining right-side angles were finished as `work/s3b_rot.py` -> `out/s3b_rotation_right.json`) |
| `work/s4_summary.py` -> `out/s4_summary.json` | true union vs sum volumes, the hinge-axis cylinder census over the whole population, the bearing/tear-out/SF arithmetic, sha256 |
| `work/s5_verify.py` -> `out/s5_verify.json` | fuselage invariants (sha256, volume, mass, topology, three walls) and ring v2 A/B vs 28 parts + the 8 new ones |
| `work/s6_gaps.py` -> `out/s6_gaps.json` | ear / surface distance to the fuselage |
| `work/s7_rot_stepwing.py` -> `out/s7_rot_stepwing.json` | the rotation fit re-run against the **delivered repo STEP wing**, the cross-check of the BREP caveat in section 0a |
| `work/s9_manifest.py` -> `SHA256SUMS.txt` | 82 entries |

### B. What this report does not establish

1. **No FEA.** Section 4 is hand arithmetic on handbook allowables with a stated 2x static factor. The
   surface's 200 MPa bearing allowable is an assumption, not a test.
2. **No bond analysis.** The ears are bonded into the wing's hinge notch; the bond line, adhesive, surface
   preparation and peel are not modelled or calculated.
3. **No fatigue, fretting, tolerance stack, thermal or dynamic case.** The hinge moment used (0.226 N m)
   is a steady 720 km/h value inside the repo's own 0.05-0.20-0.45 band, not a gust or flutter load.
4. **The relieved-wing BREP cannot be independently trusted for wing-vs-X zeros** (section 0a): it is
   boolean-hostile against large operands. The rotation claim is measured against that operand and
   cross-checked against the delivered STEP, which shows **556.690 mm3** of interference at 0 deg - i.e.
   the relief is a fix made by an earlier wave, not the delivered geometry. Both facts are reported.
5. **The ears and pins are BREP, not STEP-delivered.** No fixed part in this programme is STEP-delivered
   (the 0.500 mm cove does not round-trip; `dm-remaining-26` B1).
6. **The notch is a real cut of the flight surface** (2.60 x 16.10 mm through 2.209 mm at two stations,
   145.473 mm3 per surface). Its aero and structural consequence is not assessed beyond "the surface stays
   one valid solid and pivots cleanly".
7. **The 4.36 mm root land in the third-knuckle option (section 3b) was measured on the plate, not
   built.** The option was rejected on load path, not on geometry, so it was not executed.
8. **All masses are geometric** at 1550 kg/m3 (surface), 2700 (6061-T6 ears), 7850 (17-4PH pins) — no
   fastener heads, washers, bond or paint.

### C. The one-line answer

> Three solid unfastenable pegs per surface, two of which survive the trim, became Ø5.00 journals with a
> Ø2.60 bore, a Ø2.50 pin and a Ø4.00 fixed ear — 0.851 g per surface net — with the surface pivoting
> 0.000000 mm3 against both reliefs from -32 to +32 deg, 0 added interference rows, and the third knuckle
> shown to be unnecessary because the pushrod and the first knuckle are 1.22 mm apart.


