# dm-bearing-rings — Disposition of the two unclassified bearing-ring interference pairs

Wave 19 · specialist task · **drone-mech fuselage rev1** (DM-FUS-001 REV 1)
Started 2026-11-16. Status: **COMPLETE — all six steps answered.**

Inputs (read-only) copied into `out/`, never modified:

| file | bytes | sha256 |
|---|---:|---|
| `out/drone-mech_fuselage_rev1.step` | 9,801,595 | `d9ba7aeb7716cdd1ba4f289d284944e34e0ebab20202d39335bd9b58ecb9cadf` |
| `out/duct_A_vector_vane_bearing_ring.step` | 9,354 | `0bce6baa2722afdc1f3563456039876ca6834f5165fe3415ad770ebcb58f6abb` |
| `out/duct_B_vector_vane_bearing_ring.step` | 9,349 | `c457f221ce7a26cc037a37290fa20d064a1b6185f195d4ed391a4ed7c7657692` |

The fuselage hash equals the one in `evidence/dm-final-package/REPORT.md` §5, so this is the
same solid, not a rebuild. Ring STEPs are byte-identical copies of
`repos/drone-mech/highspeed_edf/deliverables/phase15_geometry/step/…` (read through
`D:/CodeProjects/drone-mech/…`, never written).

Claim under test: two unclassified **bearing-ring** pairs = **2,096.819452 mm³** = **63.4 %** of the
airframe's 10-pair / 3,305.834869 mm³ interference, on a part already marked FAB-READY.

---

## 0. Method, provenance labels, and the instrument that had to be named

Every number is tagged:
`[MEASURED]` computed here from the STEP copies · `[PRIOR]` from `dm-final-package/REPORT.md`, not re-derived ·
`[SRC]` read from repo source · `[ASSUMED]` unstated assumption · `[ANALYTIC]` closed form from measured inputs.

Instruments (`work/r1_measure.py`, `r2_shape.py`):
* volume — `BRepGProp.VolumeProperties_s(eps = 1e-12)`;
* boolean — `BRepAlgoAPI_Common` on native OCC B-reps;
* bbox — `BRepBndLib.AddOptimal`;
* radial census — `IntCurvesFace_ShapeIntersector` rays from the duct axis.

**Instrument control, not a claim.** On this exact part the eps-1e-12 volume is
**206,454.319709 mm³ [MEASURED]** and the default-precision form is 206,420.221088 mm³ — Δ 34.0986,
which reproduces the wave-17 §3a warning digit for digit. The eps-1e-12 value is what is quoted
everywhere below.

## 1. The two pairs, identified

| pair | ring solid | ring volume mm³ | interference mm³ |
|---|---|---:|---:|
| A | `duct_A_vector_vane_bearing_ring` @ x = −44 | 7,828.848893 | **1,048.409726** |
| B | `duct_B_vector_vane_bearing_ring` @ x = +44 | 7,828.848893 | **1,048.409726** |
| | | | **2,096.819452** |

**The claim holds exactly: measured sum 2,096.819452 mm³, delta vs the claim 0.000000 mm³
[MEASURED].** Each interference is a **single** solid (no sliver population, no multi-body artefact).
Each ring is one valid solid of 7,828.848893 mm³, which is the closed form
π(48² − 41²) × 4 = π × 2,492 = 7,828.848893 mm³ to the last digit — so the ring **is** the
`annulus(ro 48, ri 41, z0 250, length 4)` of the generator, with no extra feature.

Where they are [MEASURED]:

| | x mm | y mm | z mm | size mm |
|---|---|---|---|---|
| ring A | −92.0000 … 4.0000 | −48.0000 … 48.0000 | 250.0000 … 254.0000 | 96 × 96 × 4 |
| interference A | −10.909321 … 2.779773 | −26.960454 … 26.960454 | 250.0000 … 254.0000 | 13.689 × 53.921 × 4 |

Read relative to ring A's axis (−44, 0): the interference's **bounding box sits wholly on the +x side**
(x_rel +33.09 … +46.78, y ±26.96), so it is confined to **azimuth −36° … +36° about the +x direction** —
the ring's **inboard** face, the side turned toward the aircraft centreline. (The bbox corner is not the
radial band; the band itself is r 42.6 … 48.0, given immediately below.) Ring B is the mirror:
interference azimuth 142.5° … 217.5°, centred on 180°, also inboard. A 0.5°-step census returns **151 of
720 azimuths = 75.5° = 21.0 % of the circumference** for each ring, identically [MEASURED].

The overlap is a radial band, not a chip: the intersection's **inner** boundary is a constant
r = **42.6 mm** (the fuselage's duct-bore wall) at every azimuth, and its **outer** boundary runs all the
way out to r = **48.0 mm** — the ring's own outer diameter — over 80 of the 151 samples. **Maximum
radial penetration 5.4 mm** (= 48.0 − 42.6, the *measured* bore radius) [MEASURED]. Note the shipped
part's bore is r 42.6, not the r 42.5 the Phase-15 generator writes (`makeCylinder(42.5, 402.0)`), so the
nominal overlap would be 5.5 mm — the shipped solid is 0.1 mm larger, consistent with wave 17's finding
that the delivered body is not the generator's body. In other words, over that 75.5° arc
the ring does not merely touch the fuselage: it is **entirely buried inside it**, with no part of it
protruding.

Fuselage material measured along that arc from ring A's axis at z = 252 [MEASURED]:

| azimuth° | 0 | 5 | 10 | 15 | 20 | 25 | 30 | 34 | 36 | 38 |
|---|---|---|---|---|---|---|---|---|---|---|
| material radius mm | 42.6 … **42.6** | …45.76 | …46.90 | …49.00 | …52.55 | …58.98 | …52.18 | …46.59 | …44.28 | *nothing* |

So the clashing material is a tongue whose thickness is **zero at azimuth 0** — exactly on the aircraft
centreline, where the two duct bores pinch the web out — and which swells to 16.4 mm at azimuth 25°
before the arc ends at 38°. The interference therefore occupies the **inter-duct web**, and its inner
edge is the bore wall.

## 2. What the geometry IS, and whether the spec is sourced

**Identity [SRC].** The part is the **thrust-vector vane bearing carrier** at the nozzle exit plane:

```
phase15_generate_geometry.py:938-939
  ring = annulus(48.0, 41.0, 250.0, 4.0, xcentre)          # ro, ri, z0, length, x0
  add_part(f"duct_{letter}_vector_vane_bearing_ring", ring, "6061-T6", aluminum_color)
```

* axis **+Z**, z 250 … 254 — 5 mm **aft of the nozzle exit lip** (the nozzle ends at z = 242 and the
  exit lip at 245), so the ring sits in the exit plane, coaxial with the duct;
* bore **r = 41**, exactly `DUCT_OD/2` with `DUCT_OD = 82` and `DUCT_ID = 78`. So the one interface the
  ring was designed around is **bore-on-duct, line-to-line at nominal** — and consistently, ring↔duct
  is *not* an interfering pair anywhere in the two censuses;
* **radial wall 7.0 mm, axial thickness 4.0 mm**, 6061-T6, 21.14 g each (`mass_cg.csv`);
* function: two vanes per duct, `VANE_RING_RADIUS = 44.0`, pivoting at azimuth 90° / 270°. The 7 mm wall
  exists to carry a Ø44 pivot circle — that number is the whole problem (§3).

**The bearing specification is ASSUMED, and this is the sourced basis for saying so.** The **only**
bearing designations anywhere in the drone-mech corpus are `623ZZ (3×10×4)` and `624ZZ (4×13×5)`, at
`design/PHASE15_CONTROL_SURFACES.md:392`. That table is the **hinge test rig** — base plate, hinge
pillars, hinge pin, protractor, "knife-edge CG stand". It is a **bench fixture**, not the airframe. So:

* no bearing part number, bore, or load rating exists for the vane pivot → **ASSUMED**;
* **no fit class, no interference, no torque, no bond, no fastener** is stated for this ring anywhere.
  Its `note=` argument in the generator is **absent**, and its `note` column in `mass_cg.csv` is the
  **empty string** — the only Phase-15 part in that file with no note at all;
* the fuselage build never cuts a seat for it: `make_wing_shell` cuts `makeCylinder(42.5, 700.0)`
  (Ø85 pass-through) and nothing else near this station, so there is **no counterbore, boss recess, or
  relief pocket** anywhere in the modelled airframe.

Geometry identity is therefore **sourced**; the bearing and the fit are **ASSUMED / undeclared**.

## 3. Classification — both pairs are **(b) GENUINE CLASH**

Not (a), not (c). The evidence is geometric and it is decisive, so it is ordered by strength.

**E1 — The ring's OD is 8 mm larger than the duct centre spacing, so the two rings interpenetrate each
other.** `DUCT_CENTRES_X = (-44.0, 44.0)` → **88 mm** centres; the ring's OD is **96 mm**. Measured
directly: ring A ∩ ring B = **754.749861 mm³**, bbox x −3.539773 … 3.539773, y −19.183326 … 19.183326,
z 250 … 254 [MEASURED]. Two solid 6061-T6 annuli cannot occupy the same space, so **at least one of the
two bearing rings cannot exist as drawn — independently of the fuselage.** Neither published census
contains this pair: the six-set was body × 6 named neighbours, and the eight-set was a *mover* sweep,
which by construction cannot see a static↔static pair.

**E2 — The cause is structural, so no tolerance can absorb it.** `VANE_RING_RADIUS = 44.0` is **exactly
half** the 88 mm spacing, so the two vane pivot circles are *tangent at the centreline*. Any full annulus
that carries a pivot at r = 44 must have material outboard of it, i.e. OD > 88 mm → it necessarily
crosses the centreline and reaches into its twin's annulus. The 96-vs-88 mismatch is **forced by the
pivot radius**, not an oversight in one dimension. Consistent with this, each ring's OD also reaches
**2.6 mm inside the twin's Ø85 duct bore** (ring A's OD at x = +4.0 against that bore's wall at
x = +1.4); measured against a nominal-radius bore cylinder the overlap is **140.954606 mm³ per ring**.

**E3 — The overlap is not fit-shaped.** No fit class in engineering is a **75.5° arc** that starts
exactly at the bore wall (constant r 42.6), runs out to the ring's **own OD**, and **tapers to zero
thickness at both ends and at azimuth 0** — where the fuselage material measures `[[42.6, 42.6]]`, a
zero-thickness cusp on the aircraft centreline. A press fit or a bonded seat is a **full-circumference,
uniform-depth** band. What is here is the signature of **two independently authored solids crossing**:
the ring from one `annulus()` call, the fuselage from a body/wing loft, meeting in a wedge. Over the
arc the ring is **fully buried** (outer boundary = its own 48.0 mm OD) under up to 16.4 mm of airframe
skin — there is no exposed seat for a fit to act on, and no surface a machinist could size.

**E4 — A press fit is quantitatively impossible.** See §4: the implied diametral interference is
**10.8 mm**, which is **28.1×** the strain at which 6061-T6 yields. This alone excludes (a).

**E5 — Nothing in the corpus declares it.** No fit class, no bearing part number, no fastener pattern,
no bond spec, no pocket, no note (§2). Wave 16's "the required value" was an assertion, not a source.

**E6 — It is not a stand-in.** (c) is excluded too: unlike the motor cans and servo mounts, which the
generator explicitly labels `electronics-envelope`, this part is declared **`6061-T6`** — a real
machined aluminium part, mass-accounted at 21.14 g in `mass_cg.csv`. The 2,096.819452 mm³ is real
aluminium inside real airframe, not a nominal envelope and not a boolean-tolerance sliver (each
interference is a single valid solid, E1 in §1). The only "representative" thing about it is the
*annulus shape*, and E1 shows the shape error is in the **OD**, which is as real as the part.

**Verdict: (b) GENUINE CLASH for both pairs — 1,048.409726 mm³ each. Parts occupy the same space and
one must move: the carrier must be redesigned (a two-boss clevis at azimuth 90/270, OD ≤ 88, instead of
a full annulus), and the ring must be withdrawn from the fab-ready set until it is.** Relieving the
fuselage instead is **not available**, on two independent grounds measured here:

* a Ø96 + clearance pocket at ring A reaches **x = +4.0** (−44 + 48) while the twin Ø85 bore's wall
  nearest the centreline is at **x = +1.4** (44 − 42.6) — the relief would run **2.6 mm past it and
  merge the two duct bores into one**;
* at the arc ends the web is thinner than the cut: at azimuth **34° and 36°** the fuselage material is
  only **3.99 mm and 1.68 mm** thick, and the ring needs **5.6 mm** of relief there (out to r 48.2 —
  its OD plus 0.2 mm clearance) — so the relief would cut clean **through** the inter-duct web into open
  air over the last ~4° at each end.

## 4. The fit that is not there — computed, because that is how (a) is refuted

Classification is (b), so this section is the quantitative refutation of (a) rather than a fit
declaration. Materials and wall from [SRC] §2.

| quantity | value | note |
|---|---|---|
| fit surface | ring OD **Ø96** against the fuselage web | the only surface in contact |
| ring radial wall / axial length | **7.0 mm / 4.0 mm** | 41 → 48, 250 → 254 |
| modelled radial overlap | **5.4 mm** | 48.0 − 42.6 measured bore (nominal 42.5 → 5.5) |
| **modelled diametral interference** | **10.8 mm** | 2 × 5.4 |
| implied circumferential strain ε = δ_r / r | **0.1125** = 112,500 µε | at r = 48 |
| 6061-T6 | E = 68.9 GPa, σ_y = 276 MPa | [SRC] material |
| yield strain ε_y = σ_y / E | **0.004006** = 4,006 µε | |
| **elastic hoop stress if forced** σ_θ = E·ε | **7,751.2 MPa** | ≈ 7.8 GPa |
| Lamé thick-wall check (a = 41, b = 48) | 7,847.7 MPa | same conclusion |
| **stress vs yield** | **28.1 × σ_y** | not within yield — by 28× |
| max interference this ring can take elastically | **0.385 mm diametral** (ε_y × Ø96) | the model demands 10.8 mm |
| legitimate ISO 286 **H7/p6 on Ø96** | **0.002 … 0.059 mm** diametral | band 80–120 mm: H7 0/+0.035, p6 +0.037/+0.059 |
| model vs legitimate fit | **183× to 5,400×** | |

Two things follow, and both matter:

1. **Not within yield, by any reading.** Whichever radius is taken for the fit surface — 7,751 MPa at
   r = 48, 9,074 MPa at r = 41 — the first-order hoop stress is 7.8–9.1 GPa; the Lamé thick-wall form
   gives 7,848 MPa; and all of them are **28–33×** the 276 MPa yield of 6061-T6. A 6061-T6 ring forced
   over a 5.4 mm radial interference would yield grossly and split long before assembly was complete.
2. **The wall is strong enough for a real fit — which is the point.** At the top of the H7/p6 band
   (0.059 mm diametral) the hoop stress is only **42.3 MPa = 0.15 σ_y**. So the 7 mm × 4 mm section is
   not the problem; the *geometry* is. And the seat is a **1.2 mm PLA-core / CF-wrap shell**
   (`BODY_SHELL = 1.2`), which cannot carry a metal-to-metal press fit at all — a real joint here would
   be bonded or bolted, and neither is specified.

**So the 2,096.819452 mm³ is not a press fit, not a thread, and not a bonded joint. It is 10.8 mm of
diametral interference where the correct number is 0.06 mm or less.**

## 5. Final interference figure, and the FAB-READY verdict

**Disposition applied: both pairs classified GENUINE CLASH. Nothing is declared a fit and nothing is
removed from the count as an artefact — because nothing here is one.** The figure therefore does not
fall; it becomes *fully classified*, and it grows, because the same geometry error exposes a pair the
ten-pair census could not see.

| # | pair | mm³ | class |
|---|---|---:|---|
| 6 | elevon L/R ↔ motor can envelope, nozzle shell, fuselage wall | 1,204.481397 | genuine clash — one cause, fix specified [PRIOR] |
| 2 | elevon L/R ↔ pushrod representative | 4.534020 | modelling artefact, removed [PRIOR] |
| **2** | **ring A/B ↔ fuselage** | **2,096.819452** | **genuine clash — this report** |
| **+1** | **ring A ↔ ring B (new)** | **754.749861** | **genuine clash — OD 96 on 88 mm centres** |
| | **total as modelled** | **4,060.584730** | **11 pairs, 0 unclassified** |

* **Final interference on the final part: 4,060.584730 mm³ in 11 pairs** (was 3,305.834869 in 10).
  The increase is not a recount of existing volume — it is **754.749861 mm³ of previously uncounted
  interference**, ring A against ring B, measured here for the first time.
* Ring-involved interference is now **2,851.569313 mm³ = 70.2 %** of the airframe total, up from the
  63.4 % that started this task.
* If the carrier is redesigned as specified in §3 (two bosses at azimuth 90/270, OD ≤ 88), **all three**
  ring pairs go to zero and the airframe falls to **1,209.015417 mm³ / 8 pairs** — exactly the mover
  sweep's own total. That fix is **specified, not executed**.

### Does FAB-READY survive?

**For the fuselage solid: YES, unchanged. For the package: NO — it must be amended.**

* The fuselage (DM-FUS-001 REV 1) **needs no change and gets no change**. Every measurement here puts
  the intruder on the ring side: the fuselage material is intact and correctly shaped, the ring is
  buried in it, and the ring is the part that is geometrically impossible on its own (E1). A fabricator
  can cut this body tomorrow, exactly as the wave-17 package says.
* But the wave-17 verdict's one open item said the ring pairs "must be either declared (bonded /
  press-fit seat, with the fit stated on the drawing) or relieved". **That was a false fork.** Neither
  branch is available: there is no fit class that survives §4, and relieving the web merges the two duct
  bores. The correct disposition is **a design change to the carrier**, which is why the amendment is
  not cosmetic:
  1. the interference paragraph must be re-issued — "unclassified" → **"genuine clash: two Ø96 rings on
     88 mm centres cannot coexist; carrier to be redesigned"**;
  2. the total must be re-issued **3,305.834869 → 4,060.584730 mm³** (11 pairs);
  3. the two bearing rings (**2 × 21.14 g**) must be **withdrawn from the fab-ready part set**. They
     machine fine; they cannot be installed, and as drawn they cannot both exist.

Everything else in the package stands: one valid watertight 540-face solid at 206,454.319709 mm³ /
320.0042 g, wall 1.1800–1.2068 mm, and the 0.052 % STL agreement are untouched by this work.

## 6. Knife edge at the wing-slot rim — measured, and it is worse than the prose said

Two separate questions: the **fillet radius**, and the **included angle**.

**Minimum radius: 0.000 mm — there is no blend of any radius at any edge of this part.** Face census of
the shipped solid: **410 BSpline + 124 plane + 6 cylinder**, and **0 torus, 0 sphere, 0 cone**
(`out/r3_edge.json`) [MEASURED]. A fillet or chamfer must appear as a torus, a cone, or an extra blend
face; and `phase15_generate_geometry.py` contains **no `fillet`, `chamfer` or `blend` call anywhere**
(grep: zero matches) [SRC]. Every edge on the part is therefore a sharp C0 edge.

**Included angle: ≤ 4.0°, i.e. below the probe's own 4° resolution.** Instrument
(`work/r5_wedge_rim.py`): at an edge point with tangent **t**, probe the plane perpendicular to **t** at
radius δ = 0.05 mm and test which of 90 directions (4° step) are inside the solid; the included material
angle is the largest contiguous run of inside directions. 144 candidate edges in the band, 168 probes:

| included material angle | probes |
|---|---:|
| ≤ 2° | **0** |
| ≤ 4° | **23** |
| ≤ 8° | 36 |
| ≤ 12° | 40 |
| ≤ 45° | 72 |

The 23 probes at 4° are **exactly one lit direction out of 90** (`material_fraction` 0.011), so the true
angle lies in (0°, 4°] and is **not resolved by this instrument** — the honest statement is "≤ 4°, one
4° sample". They form **8 distinct edge/face pairs across all four quadrants** (±x, ±y), so the defect is
symmetric, not a local accident:

| edge | mid point x, y, z (mm) | azimuth | included angle |
|---|---|---|---:|
| 370 | 56.282, 40.791, −62.783 | 35.93° | **4.0°** |
| 725 | 47.708, 42.438, −56.967 | 41.65° | **4.0°** |
| 695 | 47.708, −42.438, −56.967 | −41.65° | **4.0°** |
| 620 | −47.708, −42.438, −56.967 | −138.35° | **4.0°** |
| 496 / 525 / 752 / 1259 | mirrors of the above | — | **4.0°** |

Edge 370 runs from (56.8532, 40.6147, −54.9108) to (56.8438, 40.6177, −70.6531) — a **15.7 mm line** —
and reads 4.0° at all five stations sampled along it (frac 0.15 / 0.30 / 0.50 / 0.70 / 0.85), so the
wedge is a **line**, not a point defect.

**What the wedge actually is.** Every one of the 8 sharpest edges is the meeting of a **Ø85 duct-bore
cylinder face** and a **narrow BSpline face lying immediately outside the bore**. For edge 370: face 93
is the bore cylinder (bbox x 56.281…86.600, y 0…40.791, z −112…195.665) and face 172 is a BSpline sliver
whose bbox is **0.643 × 0.176 × 15.742 mm**. The mechanism is dimensional, and it is a wall-thickness
failure:

* the bore is **r 42.6** (measured) and the body's outer half-height is **44 mm** → only **1.4 mm** of
  clearance at the duct's widest point;
* the hull is a **superellipse of exponent 2.6**, so that clearance collapses as |x| leaves the duct
  axis: at **12.28 mm** off-axis the hull is already at **|y| = 38.97** while the bore demands **40.79**.

So the Ø85 bore **breaks out through the upper and lower hull skin**, and the rim it leaves is a
zero-angle wedge instead of a 1.2 mm land. Wave 17 correctly read the **0.5145 mm** ray as a chord across
a wedge and correctly asked for a fillet; what it did not have is the **angle** (≤ 4°, §6 above) or the
**cause** (the bore breaking out of the superellipse hull, not a wing-slot cut).

**Verdict: yes — a manufacturing problem, and it is the one that should have been the open item.**
At δ = 0.05 mm from the edge line the material is **3.5 µm wide** (2δ·tan 2°). That is not a feature:

* an FDM/FFF printer renders it as a feather edge that the slicer either drops entirely or prints as a
  single near-zero-extrusion perimeter — the classic source of a finished-part sliver and a nozzle blob;
* a machinist cannot hold 3.5 µm of remaining wall; the tool will simply break through, and the drawing
  would have to say where;
* any bond line, paint or powder coat bridges it instantly, turning a through-feature into a seal;
* it is a **handling** risk: it sits at y ≈ +41 (the upper shoulder of a body whose half-height is 44),
  x ≈ ±56, along z −55…−71 — a surface a hand picks the airframe up by.

**Fix, one line: a 0.3 mm offset or a ≥ R0.5 fillet on the bore ↔ hull rim**, which converts the wedge
into a land. This is the *same class* of defect as the ring clash — a feature authored to nominal
without a check against its neighbour — so both belong in one correction pass.

**Naming correction.** The brief calls this "the wing-slot rim". The generator's slot
(`phase15_generate_geometry.py:298-304`) is a **side-facing Ø84 capture port** centred at z = −70 and
extruded 40 mm along ±x — not a wing slot; the body has **no wing-slot cut at all**. The sharp edges are
on the **duct-bore ↔ outer-hull** intersection. Wave 17's window (z −90…−70, azimuth 43–45°) sits on the
same family; extending the window aft to z −50 finds the same edge continuing and reaching the ≤ 4° limit
at z −54.9…−70.7.

**Coverage limit, stated.** 144 of 1,561 edges were probed — the band z −110…−50, r 50…80. The all-edge
scan costs ≈ 3.7 h at 31.9 ms per classifier call and was **not** run, so 4.0° is the minimum **in the
rim band**, not a proof about the rest of the part. It is the band the brief named.

## 7. Reproduction

| script | what it produced |
|---|---|
| `work/r1_measure.py` → `out/r1_measure.json` | ring volumes, both interferences, bbox, 2° radial census at three z |
| `work/r2_shape.py` → `out/r2_shape.json` | ring A ∩ ring B, penetration into the twin bore, 0.5° lobe, fuselage profile, press-fit refutation |
| `work/r3_edge.py` → `out/r3_edge.json` | plane-normal included angle + face census — **not usable for the angle**, see below; the face census is used |
| `work/r4_wedge.py` | all-edge wedge scan — **abandoned** (3.7 h budget), superseded |
| `work/r5_wedge_rim.py` → `out/r5_wedge_rim.json` | targeted wedge probe at the rim, 144 edges / 168 probes, 1,537 s |
| `work/r6_identify.py` → `out/r6_identify.json` | which two faces form each 4° wedge (bore cylinder + BSpline sliver) |

Run order: `r1_measure.py` → `r2_shape.py` → `r3_edge.py` → `r5_wedge_rim.py` → `r6_identify.py`.
All are standalone `"C:/Program Files/Python312/python.exe"` (cadquery 2.7.0 / OCP 7.8.1.1) scripts on
the copies in `out/`. Raw stdout is in `log/`.

**Instrument that was tried and cannot answer the angle question, recorded so nobody repeats it.** The
plane-normal included angle in `r3_edge.py` measures 116 edges and returns a floor of **exactly
90.000°** — meaningless. Reason: this part is **410 BSpline + 124 plane + 6 cylinder** faces, so the
loft faces at the rim carry no single normal, and 1,445 of 1,561 edges were skipped as non-planar. The
angle needs a local wedge probe, not a face-pair angle.

**Second instrument limit, stated plainly.** `BRepClass3d_SolidClassifier` costs **31.9 ms/call** on this
540-face solid, so the all-edge wedge scan (`r4_wedge.py`) needs ≈ 3.7 h; it was killed after 25 min
and replaced by the targeted probe. §6 is therefore a **banded** measurement, and its coverage is stated
there rather than generalised to the whole part.

Repo untouched, no commit, no reset, nothing written to `D:\CodeProjects` or `E:\1vm\TMP`. Every write in
this wave landed under `evidence/dm-bearing-rings/`; `SHA256SUMS.txt` hashes every file in the package.

Provenance of the copies, checked not assumed: all three `out/*.step` files hash **identically** to their
sources (fuselage → `evidence/dm-final-package/out/`, rings → the repo's `step/` folder). `git status` in
`D:/CodeProjects/drone-mech` reports one untracked file, `MEMORY.md`, created **2026-11-14 18:10** — two
days before this session, and not written by this wave.