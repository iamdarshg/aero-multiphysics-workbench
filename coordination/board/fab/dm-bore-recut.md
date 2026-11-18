# DM bore re-cut — the largest duct-bore radius that yields exactly ONE solid

**Status: COMPLETE**

One question: what duct-bore radius yields exactly ONE valid solid for the drone-mech body, and
what does it cost in volume and interference?

Input: `repos/drone-mech/highspeed_edf/deliverables/phase15_geometry/`.
Read first: `evidence/dm-solid-weld/` (4 solids, one shell each, 742,305.5264 mm³ by the generator's
own integrator, 8.259 / 77.165 mm air gaps, the 42.4 variant reported at two solids).
All work is on COPIES under `evidence/dm-bore-recut/work/`; the repo was not written to.

**Headline.** No duct-bore radius yields one solid, in either direction (20 … 60 mm surveyed).
The count floors at **2**, and the floor is reached at **42.4375 mm** (42.45 gives 4). The split is
*not* the bore: the **cavity cut alone, with no bore at all, already makes two solids**, because the
outer loft's spline undershoots 20 mm inside its own station over a 77 mm band. The re-cut therefore
buys 2 solids for **+2,796.288 mm³ (+0.377 %)** and **−0.762 % of bore area** — and it
**reintroduces interference**: 2 new pairs, **100.342 mm³**, against the vector-vane bearing rings.

## 0. Instrument provenance

| item | value |
|---|---|
| python | `C:\Program Files\Python312\python.exe` 3.12.2 |
| cadquery / OCP | 2.7.0 / 7.8.1.1 |
| volume | `BRepGProp.VolumeProperties_s(shape, eps=1e-12)` — the converged figure the programme quotes (742,306.3595 mm³), not the generator's default 742,305.5263 |
| bbox | `BRepBndLib.AddOptimal_s(shape, box, False, False)` throughout; **0 of 523 faces carry triangulation**, so plain `Add` is never used |
| solid / shell count | `TopExp_Explorer(SOLID / SHELL)` on the re-imported BREP |
| watertight | per-shell `TopExp.MapShapesAndAncestors(EDGE→FACE)`; free = 1 face, non-manifold = >2 |
| bore wall | radial ray cast (`IntCurvesFace_ShapeIntersector`) from each bore axis to the outer loft: 2 mm × 5° grid, 14,184 rays (`work/out/screen1.json`) |

### 0a. The repo's generator cannot be run as checked in — a line ending, not a revision

`phase15_generate_fuselage_shell_endpoint_relief.py` pins `BASE_GENERATOR sha256 = 53353da1…abd47`;
the working tree hashes to `8CC6E5DA…BF51`. Set diff: the working tree is the same content with
**CRLF** (67,667 B, 1,209 CRLF) against the committed blob's **LF** (66,458 B). `git status` is clean
because git normalises on checkout; a byte hash does not. The blob restored from
`git show ff670b8:…` reproduces the pinned hash exactly and the generator then runs unmodified.
Recorded so the mismatch is not mistaken for a geometry revision, and so no green run is credited to
a file that was not the pinned one.

## 1. Current radius, and the four-solid result reproduced

**Current radius: 42.6 mm** (`--duct-radius` default; source baseline 42.5 mm; bore **Ø85.2 mm**).

Rebuilt from the pinned generator into `work/out/r42_6.step/.brep`, six cuts in the repo's own order
(duct A, duct B, cavity, slot −x, slot +x, hatch):

| stage | cut | solids | volume mm³ |
|---:|---|---:|---:|
| 1 | duct A | 1 | 5,979,465.23 |
| 2 | duct B | 1 | 4,001,690.52 |
| 3 | **cavity** | **4** | 865,419.18 |
| 4 | slot −x | 4 | 842,737.92 |
| 5 | slot +x | 4 | 820,056.67 |
| 6 | hatch | 4 | 742,305.53 |

**4 solids reproduced**, converged volume 742,306.3595 mm³ against the receipt's 742,305.5264
(Δ 0.833 mm³, 1.1e-6 — the integrator tolerance the v6 checklist documents). Per solid:
624,770.5298 (2V/A 11.34) · 20,808.2965 · 75,919.2366 · 20,808.2965 (2V/A 1.23 / 1.41).

**The receipt's "1 → 4 at the duct-bore cut stage" is mislabelled.** The ducts are stages 1–2 and
leave **one** solid; the jump to 4 is the **cavity** cut at stage 3. That distinction decides the
question.

## 2. The split is two cuts, and the first has no radius in it

`work/probe_cuts.py` runs the cavity cut **alone** on the uncut outer loft — **no bore at all**:

| cuts applied | solids | volume mm³ | pieces |
|---|---:|---:|---|
| none | 1 | 7,953,163.97 | — |
| **cavity only** | **2** | 1,039,785.74 | 702,419.28 (2V/A 10.04, z −360 … −189.0984) + 337,366.46 (2V/A 2.14, z −111.933 … 280) |

The count decomposes **1 → 2 (cavity) → 4 (bores)**, and the 77.165 mm fore/aft gap that
`dm-solid-weld` measured is already there with zero bore.

### 2a. Mechanism: the cavity lies 114,150.5 mm³ OUTSIDE the skin (`work/probe_pinch.py`)

`inner.cut(outer)` — cavity material outside the skin, i.e. where the shell wall is negative:

| quantity | measured |
|---|---|
| cavity outside the skin | **114,150.549 mm³** |
| bbox | x ±91.8201, y ±42.7766, **z −196.2375 … +89.6146** |

Section census (0.02 mm slabs, `work/out/pinch.json`), widths in mm:

| z | outer | inner | wall/side |
|---:|---|---|---|
| −250 | **211.22** | 185.37 | +12.9 (overshoot) |
| −200 | 186.01 | 183.60 | +1.2 |
| **−190** | **179.48** | 183.35 | **−1.9** |
| −160 | **165.96** | 183.03 | **−8.5** |
| −112 | 179.12 | 183.44 | −2.2 |
| −100 | 186.01 | 183.60 | +1.2 |

The outer loft is `ruled=False` through stations that step 2.0 → 54 → 126 → **186** mm between
z −360 and −300. It overshoots to 211 mm at z −250 and then **undershoots to 166 mm at z −160** —
20 mm narrower than its own station. Across z −196…−90 the cavity is outside the skin, so the cavity
cut removes the full section and severs the body.

**Therefore no duct-bore radius can yield one solid.** A proof, not an extrapolation: the cavity cut
is radius-independent, and removing more or less copper at the bore cannot join two bodies that the
cavity has already separated.

## 3. The sweep

Full 6-cut parts were built at every radius in the table (pinned generator, `work/out/r*.json`).

| radius mm | solids | shells | volume mm³ (ε 1e-12) | watertight | min radial wall at z=0 mm | per-solid 2V/A |
|---:|---:|---:|---:|---|---:|---|
| **42.6** current | **4** | 4 | 742,306.3595 | 4/4 | −1.851 | 11.34 · 1.23 · 1.41 · 1.23 |
| 42.5 | 4 | 4 | 744,005.6303 | 4/4 | −1.751 | 11.34 · 1.22 · 1.41 · 1.22 |
| 42.45 | **4** | 4 | 744,880.6245 | 4/4 | −1.701 | 11.34 · 1.22 · 1.41 · 1.22 |
| **42.4375** | **2** | 2 | 745,102.6472 | 2/2 | −1.688 | 11.34 · 1.34 |
| 42.425 | 2 | 2 | 745,326.1879 | 2/2 | −1.676 | 11.34 · 1.34 |
| 42.4 | 2 | 2 | 745,776.8979 | 2/2 | −1.651 | 11.34 · 1.34 |
| 42.0 | 2 | 2 | 753,421.5761 | 2/2 | −1.251 | 11.34 · 1.34 |

Screen (2 ducts + cavity only — a lower bound on the final count), 18 radii:

| radius | 42.4 | 41.5 | 41.0 | 40.5 | 40.0 | 39.0 | 38.0 | 36.0 | 34.0 | 32.0 | 30.0 | 26.0 | 20.0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| solids | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |

And *upward*, to close the loophole that a bore large enough to annihilate the aft shell would also
leave one solid (`work/out/screen_up.json`): 44 → **7**, 46 → **7**, 48 → **7**, 50 → **5**,
55 → **3**, 60 → **3**. One solid does not exist at any radius from 20 to 60 mm.

Min-wall column: signed radial clearance from the bore wall to the skin at the full-width station;
negative means the bore breaks out there (the skin's tightest radial distance from the bore axis is
40.749 mm at azimuth 80°). It turns positive only below **40.749 mm**, which is a real landmark (the
bore stops cutting the mid-body skin) but changes no count.

## 4. ANSWER

**The largest duct-bore radius that yields exactly ONE solid does not exist.**
Floor = **2** solids, from the fore/aft split of §2, which is caused by the loft, not the bore.

The largest radius that reaches that floor is **42.4375 mm** (2 solids); **42.45 mm gives 4**. The
4 → 2 transition lies in (42.4375, 42.45], within 0.0125 mm — the radius at which the two duct-side
flaps stop being severed and merge back into the aft shell. The repo's own 42.4 mm test also gives 2
and is reproduced here (745,776.8979 mm³, 2 solids).

## 5. Cost at 42.4375 mm

| | 42.6 (current) | 42.4375 (largest 2-solid) | change |
|---|---:|---:|---:|
| solids | 4 | **2** | −2 |
| volume mm³ (ε 1e-12) | 742,306.3595 | 745,102.6472 | **+2,796.288 (+0.377 %)** |
| mass at 1550 kg/m³ | 1,150.575 g | 1,154.909 g | +4.334 g |
| bore diameter mm | 85.200 | **84.875** | −0.325 |
| bore area per duct mm² | 5,701.237 | 5,657.824 | **−43.413 (−0.762 %)** |
| radial clearance to the 82 mm duct OD | 1.600 | **1.438** | −0.162 |

No volume is *lost*: the answer is a **smaller** bore, so the part gains 2,796.288 mm³ (+0.377 %) and
4.334 g. The 42.4 variant in the receipt costs +3,470.538 mm³ (+0.468 %, +5.379 g) and −0.937 % of
bore area. As a cross-check, the difference shape `new.cut(old)` measures **2,772.380 mm³**
(`work/out/delta_42_4375_vs_42_6.brep`), 0.85 % from the integral difference — the integrator
tolerance, and the reason both are quoted rather than one.

**Flow area.** The duct's flow passage is its own 78 mm ID throat — **4,778.362 mm² per duct,
unchanged**. The bore is a clearance tunnel: what shrinks is the clearance annulus between bore and
duct OD (420.219 → 376.807 mm²). So the change costs **0.76 % of bore area and 0.162 mm of radial
clearance**, and costs the throat nothing.

## 6. Validity of the resulting part (42.4375 mm) — everything passes except the count

| check | instrument | result |
|---|---|---|
| **solid count** | `TopExp_Explorer(SOLID)` | **2 — not one** |
| shell count | `TopExp_Explorer(SHELL)` | 2, one per solid |
| each shell closed | `Shell.Closed()` | True, True |
| free edges (open boundary) | per-shell `MapShapesAndAncestors(EDGE→FACE)`, count == 1 | **0** of 1,566 edges (405 + 1,161) |
| non-manifold edges (count > 2) | same map | **0** |
| watertight | free == 0 and non-manifold == 0 and closed | **YES** on both |
| BRep valid | `BRepCheck_Analyzer(shape, True)` | **valid** |
| volume / surface | `BRepGProp`, ε 1e-12 | 745,102.6472 mm³ / 290,285.462 mm² |
| mass at 1550 kg/m³ (`PLA-core-CF-wrap`) | V × ρ | **1,154.909 g** |
| STEP round-trip | generator receipt `r42_4375.json` | 2 solids, valid, 745,390.1634 mm³ (its integrator) |
| faces carrying triangulation | `BRep_Tool.Triangulation` per face | **0 of 523** — hence `AddOptimal` for every bbox |

Pieces: 624,770.5298 mm³, bbox x ±105.8918, y −48.4587…+41.7705, **z −360 … −189.0984**; and
120,332.1173 mm³, bbox x ±95.2820, y ±45.4136, **z −111.933 … +280**. The 77.165 mm through-gap
between them is the pinch of §2a.

## 7. The 84.2 % bulk fill — a thickness defect, and it SURVIVES unchanged

| piece | volume mm³ | surface mm² | 2V/A mm | shell-equivalent at 1.2 mm | ratio |
|---|---:|---:|---:|---:|---:|
| fore piece (solid 0) | 624,770.5298 | 110,192.05 | **11.3397** | 66,115.23 | **9.45×** |
| aft piece (solid 1) | 120,332.1173 | 180,093.41 | 1.3363 | 108,056.05 | 1.11× |
| whole part | 745,102.6472 | 290,285.46 | 5.1336 | 174,171.28 | 4.28× |

**The bore change does not touch it.** Solid 0's volume is 624,770.5298 mm³ and its 2V/A is 11.3397
at **every** radius in §3 — 42.6, 42.5, 42.45, 42.4375, 42.425, 42.4, 42.0 — identical to 4 dp,
because no bore surface reaches the fore body. Its share moves only because the denominator grows:
84.166 % at 42.6 → 83.85 % at 42.4375.

Two independent causes, both upstream of the bore:
1. the cavity loft starts at z −298.8, so z −360 … −298.8 is **solid**;
2. the pinch (§2a) means the cavity cannot hollow the wall between z −196 and −90 at all.

So the part carries **+558,655 mm³ (+866 g) of surplus material in the fore piece alone** against a
nominal 1.2 mm wall — 9.45× — and "2 solids instead of 4" repairs none of it.

## 8. Interference at 42.4375 mm — the change DOES reintroduce clashes

The change adds material only in the annulus r 42.4…42.6 about each bore axis (measured difference
shape **2,772.380 mm³**), so any new overlap lies in that band. Two instruments:
difference-shape probe (`work/out/delta_probe.json`), and clipped absolute booleans
(`work/out/clash_local.json`).

| pair | at 42.6 mm³ | at 42.4375 mm³ | change |
|---|---:|---:|---:|
| `fuselage × elevon_left` | 95.304133201 | 95.304133201 | **0.000000000** |
| `fuselage × elevon_right` | 95.304133201 | 95.304133201 | **0.000000000** |
| **`fuselage × duct_A_vector_vane_bearing_ring`** | 1,048.410 | **1,098.581** | **+50.171 (NEW PAIR)** |
| **`fuselage × duct_B_vector_vane_bearing_ring`** | 1,048.410 | **1,098.581** | **+50.171 (NEW PAIR)** |
| `fuselage × duct_A_side_inlet` (waived) | 802.547 in-box | 901.267 in-box | +98.72 (probe) |
| `fuselage × duct_B_side_inlet` (waived) | 802.547 in-box | 843.674 in-box | +41.13…+98.72, unsettled |
| `fuselage × duct_A/B 82OD_78ID` | 0 | 0 | 0 |
| `fuselage × duct_A/B nozzle+lip` | 0 | 0 | 0 |
| `fuselage × pushrod_left/right` | 0 | 0 | 0 |
| `fuselage × motor_A/B_R3 envelope` | 0 | 0 | 0 |

*Basis of the columns: the two `elevon` rows and all the `0` rows are direct body-vs-part booleans
at both radii; the ring and inlet absolutes come from clipped-body booleans (the full-body pair is
minutes per boolean), while every **increment** quoted is confirmed by the independent difference
shape, which needs no clip.*

**The delivered 8 pairs / 1,255.303466 mm³ are unchanged.** The body is a member of exactly two of
them (`elevon_left ↔ fuselage_42_6` 95.304133195, `elevon_right ↔ fuselage_42_6` 95.304133199 in
`evidence/fab-dm-final/fab_dm_final.json → state_delivered`); both are reproduced here on the rebuilt
file to 8e-9 and are **bit-identical at the new radius**. The 2 residual pushrod-placeholder pairs
(4.534020 mm³ as delivered, **4.010114 mm³** after the station change) do not involve the body and
are untouched.

**But two pairs appear that the mover sweep cannot see.** `fab_dm_final.py` sweeps only the four
movers (elevons, pushrods) against parts, so a static `body × ring` pair is outside its population
entirely — the same blind spot that hid the two inlet pairs. Measured between the two radii, the
bearing-ring overlap grows by **50.171 mm³ per side, 100.342 mm³ in total** — the two independent
instruments agree to 2e-6 (50.170788 from the difference probe, 50.170790 from the clipped
booleans). Location: **z 250…254, x −11.11…+2.86, y ±26.83** — the web between the two bores at the
aft taper, which the smaller bore thickens. That is a genuine clash, not a waiver: the ring is a
real part.

The side-inlet class is the **waived** intentional penetration; its increment is +98.72 mm³ per side
by the difference probe, but the clipped re-measure was not box-invariant on the B side
(41.13 vs 98.72), so that class's absolute change is **not settled** — stated, not smoothed. It does
not change the blocking number.

## 9. Consequences for the programme

1. **The 4-solid blocker is not a bore parameter.** It is (a) a `ruled=False` loft whose spline
   oscillates 20 mm outside/inside its own stations, and (b) a cavity that starts at z −298.8. Any
   wave that tunes the bore radius to fix the solid count is tuning the wrong variable; the count
   cannot go below 2 at any radius from 20 to 60 mm.
2. **The +97 g Boolean repair cannot deliver one solid either**, for the same reason.
3. If 2 solids is accepted as the target, **42.4375 mm** is the cheapest radius (+0.377 % volume,
   −0.762 % bore area) — but it buys 2 new ring clashes of 50.171 mm³ each, which must be resolved by
   a ring or web change, not by moving the bore back (42.6 has 0 but 4 solids).
4. The 84.2 % bulk fill is untouched by any of this and is 9.45× the shell it should be.

## 10. Files

| file | what |
|---|---|
| `work/sweep_screen.py` / `out/screen1.json` / `out/screen_up.json` | 18 radii down (2 ducts + cavity) + 6 radii up, and the 14,184-ray skin scan |
| `work/probe_cuts.py`, `logs/probe_cavity_only.log` | cavity cut alone → 2 solids, piece volumes and bboxes |
| `work/probe_pinch.py`, `out/pinch.json` | cavity outside the skin: 114,150.549 mm³, z −196.2375…+89.6146, section census |
| `work/analyze_solid.py`, `out/r*.metrics.json` | per radius: solids, shells, closed, free/non-manifold, volume ε1e-12, optimal bbox, 2V/A, mass |
| `work/out/r42_6.*`, `r42_5.*`, `r42_45.*`, `r42_4375.*`, `r42_425.*`, `r42_40.*`, `r42_00.*` | the seven 6-cut builds (STEP + BREP + receipt) |
| `work/interference_check2.py`, `out/interference_42_4375.json` | 10 direct body-vs-part pairs at both radii |
| `work/radial_exclusion.py`, `out/radial_exclusion.json` | 37 neighbours classified by nearest-axis radial extent (28 provably out of reach) |
| `work/delta_probe.py`, `out/delta_probe.json`, `out/delta_42_4375_vs_42_6.brep` | the 2,772.380 mm³ difference shape vs 7 band-touching neighbours |
| `work/clash_localise.py`, `out/clash_local.json` | absolute ring/inlet pair volumes (clipped) |

Repo untouched: every build wrote into `evidence/dm-bore-recut/work/`.