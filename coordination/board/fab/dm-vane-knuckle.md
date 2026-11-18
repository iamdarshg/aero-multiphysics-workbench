# dm-vane-knuckle — the vane-root slot designed and cut on all four brackets, the third-knuckle overhang analysed and refused on measurement, the knife edge adjudicated

STATUS: **COMPLETE** — (a) the slot is designed and cut on all four brackets with the mirror pair
rebuilt, residual 0.000000; (b) the 33.265 mm overhang is analysed and accepted, and a third knuckle is
refused on measurement; (c) the knife edge is adjudicated with the fairing's cost re-measured. The sweep
re-runs to **12 pairs / 197.519831 mm3, 0 genuine clash** (from 16 / 1,229.794165), set diff 18 SAME /
0 CHANGED / 4 REMOVED / 0 ADDED. Fuselage byte-identical, rings 28/28 clean. No repo write, no commit,
no reset.

## 0. Scope, instrument, invariants

- [x] **Write scope.** Everything under `E:/engineering-portfolio-audit/evidence/dm-vane-knuckle/`
      (a junction onto `D:\ep-audit-evidence\dm-vane-knuckle`, so the 20 MB of operands lands on D:).
      The repo was opened **read-only** (`deliverables/phase15_geometry/step`) and the upstream
      `dm-knife-fairing/out/*.step` read-only. **No repo write, no commit, no reset**; nothing written
      to `D:\CodeProjects` or `E:\1vm\TMP`. All operands are copies.
      Free space at start: **D: 140.70 GB, E: 10.90 GB**; this directory is < 25 MB, so no large
      intermediate needed moving.
- [x] **Instrument.** `C:\Program Files\Python312\python.exe`, cadquery 2.7.0 / OCP 7.8.1.1
      (OpenCASCADE). Volume `BRepGProp.VolumeProperties_s(shape, props, 1e-12)` — never
      `Shape.Volume()`. Booleans `BRepAlgoAPI_Common` / `BRepAlgoAPI_Cut`, OCP default fuzzy 0.0,
      **solid-by-solid** (one compound × compound boolean under-reports on this model). Distance
      `BRepExtrema_DistShapeShape`. Containment `BRepClass3d_SolidClassifier`. Sections by thin-slab
      `Common` with the slab volume reconciled against the solid's own volume to 0.000000.
      Second moments from the volume inertia tensor: `∫y²dV = (Izz + Ixx − Iyy)/2`.
- [x] **Baseline inherited, not re-derived.** `evidence/dm-close-clashes/REPORT.md` §5a — **16 pairs /
      1,229.794165 mm3 = 0 genuine clash / 0.000000 + 14 dispositioned contact / 1,224.865011 +
      2 withdrawn / 4.929154**, whose own basis is `dm-remaining-26`. This wave changes one row class
      (the vane root) and re-runs the whole sweep on the same population of 30 solids-groups + 2
      code-built D84.0 beads.
- [x] **Invariants to hold.** Fuselage 206,454.319709 mm3 / 320.0042 g, 1 solid, walls
      1.0921 / 1.1990 / 1.1800; ring v2 A/B 0.000000 against all 28 parts. §5.

## 1. (a) The vane root in the servo bracket — three features, designed, cut, and the mirror fixed

### 1a. What the joint is, measured

Both sides, both vanes, all four brackets (`work/s1_inspect.py` → `out/s1_inspect.json`):

| | measured |
|---|---|
| bracket (`servo_mount_vane_*`) | **7 box solids, 42 planar faces, 0 cylindrical faces**, 10,154.000000 mm3, bbox x ±29.5…±58.5, y 51…71, z 243.5…286.5 |
| bracket parts | plate 23 × 12 × 29 = 8,004.000000; rib 27 × 2 × 33 = 1,782.000000; 4 corner lugs 4 × 5 × 4 = 80.000000 each; post 2 × 2 × 12 = 48.000000 |
| vane (`duct_*_vector_vane_*`) | 3 solids, 2,617.646003 mm3: blade **2.000 × 30.000 × 40.000** = 2,400.000000 (x −45…−43); hub **Ø3.000 × 24.000** along y = 169.646003 (y 32…56); tab 12 × 2 × 2 = 48.000000 |
| row, vane_1 | **320.137167** = plate mortise 174.000000 (2 × 3 × 29) + rib through-cut 132.000000 (2 × 2 × 33) + hub bore 14.137167 (π·1.5²·2) |
| row, vane_2 | **196.000000** = plate mortise 174.000000 + post 22.000000 (2 × 2 × 5.5) |

So the joint is solid-on-solid in three distinct places and **nothing in the bracket has a hole of any
kind** — 0 cylindrical faces is the whole story: no bore for the hub, no slot for the blade.

### 1b. The three missing features, and the slot design

One geometry serves all four brackets (they are the same part, mirrored in y):

| # | feature | where | size | clearance | material removed |
|---|---|---|---|---:|---:|
| **F1** | blade groove | plate's front face (y = 56.000 on +y; y = −56.000 on −y), **through the plate's full 29.000 mm height** | **2.400 wide × 3.400 deep** | 0.200 per side on the 2.000 blade; **0.400 bottom** on the blade's 3.000 penetration | **236.640000** |
| **F2** | blade through-slot | the 2.000 mm rib, **full 33.000 mm height**, through its thickness | **2.400 × through 2.000 × 33.000** | 0.200 per side | **158.400000** |
| **F3** | hub bore | the rib, at the hub axis (x = −44.000/+44.000, **z = 260.000**) | **Ø3.100 through 2.000** | **0.050 radial** running fit on the Ø3.000 hub | **1.877134** (the incremental slivers; the bore's own envelope is π·1.55²·2 = 15.094 mm3) |

**What is left standing.** Plate: 12.000 → **8.600 mm** behind the groove, 8,004.000000 → 7,767.360000
(**97.044 %** kept). Rib: 1,782.000000 → 1,621.722890 (**91.006 %** kept) but **split in two 12.300 mm
straps** by the full-height slot — the solids count goes 7 → 8, and that is a real change in the load
path, not a book-keeping one. Bracket total 10,154.000000 → **9,757.082866** (−396.917134 = **3.909 %**).
At 6061-T6's 2700 kg/m3 (the sheet family the vane spec names) the slot costs **1.072 g** per bracket,
27.416 → 26.344 g.

### 1c. The 14.000 mm mirror asymmetry — measured, and corrected

`work/s3_slot.py` matches every +y bracket solid to the −y solid at the same x and z span and reports the
y residual:

| bracket feature | +y (datum) | mirror of it | −y as delivered | residual |
|---|---|---|---|---:|
| plate | 56.000…68.000 | −68.000…−56.000 | −68.000…−56.000 | **0.000** |
| **rib** (27 × 2 × 33) | 54.000…56.000 | −56.000…−54.000 | **−70.000…−68.000** | **−14.000** |
| 4 corner lugs (4 × 5 × 4) | 51.000…56.000 | −56.000…−51.000 | **−73.000…−68.000** | **−17.000** each |
| post (2 × 2 × 12) | 69.000…71.000 | −71.000…−69.000 | **−55.000…−53.000** | **+16.000** |

**The −y bracket's whole front frame is mounted on the back face.** Its rib and four lugs sit outboard of
the plate's *outer* face instead of on its *inner* face, and the post is flipped to the inner side, where
it stands inside the vane's sweep (the 22.000000 of the 196.000 row). So the named 14.000 mm is the rib;
the same error displaces the lugs by 17.000 and the post by 16.000 in the opposite direction, and no
single translation fixes it.

**Executed:** the −y brackets are rebuilt as the **exact mirror of the +y bracket** (`A2 := mirror(A1)`,
`B2 := mirror(B1)`, mirror plane y = 0, x and z preserved), then slotted with the same F1/F2/F3. The
identity control is that the corrected part reproduces the +y joint to the printed digit:

| | A2 as delivered | A2 corrected | A1 reference |
|---|---:|---:|---:|
| bracket volume | 10,154.000000 | **10,154.000000** | 10,154.000000 |
| overlap with its own vane, before the slot | 196.000000 | **320.137167** | **320.137167** |
| solids | 7 | 7 | 7 |

So the pair is now a pair, and the row that used to read 196.000000 becomes 320.137167 *before* the
slot is cut away — which is the proof that the 124.137167 gap was the missing rib and the intruding post,
not a lighter joint.

### 1d. Re-verified: all four joints now zero, valid, and assembles

| | A1 | A2 | B1 | B2 |
|---|---:|---:|---:|---:|
| bracket before | 10,154.000000 | 10,154.000000 | 10,154.000000 | 10,154.000000 |
| bracket after | 9,757.082866 | 9,757.082866 | 9,757.082866 | 9,757.082866 |
| removed (F1 + F2 + F3) | 396.917134 | 396.917134 | 396.917134 | 396.917134 |
| solids 7 → | 8 | 8 | 8 | 8 |
| `BRepCheck` valid | **true** | true | true | true |
| **residual common volume with its vane** | **0.000000** | **0.000000** | **0.000000** | **0.000000** |

Clearances measured on the cut part: **0.200 mm** at both slot walls (by construction 2.400 vs 2.000),
**0.050 mm** at the hub bore (Ø3.100 vs Ø3.000). One coplanar face pair remains by design: the hub's
outboard end face lies in the groove's mouth plane at y = 56.000 — **zero gap, zero interference**, a
nominal abutment rather than a contact. Artifacts: `work/fix/servo_mount_vane_{A1,A2,B1,B2}_slotted.brep`
+ sha256 in `out/s3_slot.json`.

**What this costs, stated.** (i) The rib is now two 12.300 mm straps instead of one 27.000 mm web — the
bracket's rib carries 91.006 % of its material but its continuity depends on the plate bond. (ii) The
hub is carried on a 2.000 mm bearing land = **0.67 d** — below the 1.5 d a running fit wants; that is a
pre-existing property of the joint (the rib is 2.000 mm thick and the slot does not change it), now
visible instead of hidden behind an interference. (iii) The 0.200 mm slot clearance is a relief, not a
fit: the Ø3.100/Ø3.000 bore is what locates the vane.

**The vane is untouched.** All three features are cut in the *bracket*; the vane's own STEP is used
unmodified, so the vane's mass, its 2,617.646003 mm3 and its hub stay exactly as delivered.

**It assembles in one motion.** All three features are open in the same direction: the groove runs
through the plate's height and out of its front face, the slot runs through the rib's height and
thickness, the bore runs through the rib's thickness — so the vane is fitted by **one linear insertion
along +y** (hub into bore, blade into slot and groove together). No rotation, no split bracket.

## 2. (b) The third knuckle and its bracket — the 33.265 mm overhang

### 2a. What it is

| quantity | measured |
|---|---|
| elevon after the trim | 7,033.997403 mm3 / **10.9027 g** at 1550 kg/m3, 4 solids |
| plate | 6,589.174401 mm3, x −204.750…**−93.735**, y −1.5…1.5, z 115.447…155.976 |
| **root station** | **x = −93.735** (the trim face); fuselage wall outboard face at **−93.235277** → **0.499723 mm** of free space |
| first remaining knuckle | x **−133.000…−127.000** (6.000 mm long, Ø3.000, axis **x**, at y = 0, z = 127.620) |
| **overhang** | **33.265 mm** to the knuckle face, **36.265 mm** to its centre |
| overhang mass, from the model | 1,999.824561 mm3 → **3.0997 g** (30.35 % of the surface's planform) |
| section in the overhang (measured) | chord 40.005, thickness **2.2087**, area 60.1180 mm2, **I_z = 16.8293 mm4** (inertia tensor), I/A = 0.2796 mm |

**The knuckles, measured — and they are not hinges.** Each is exactly `π·1.5²·6.000 = 42.411501 mm3`, a
**solid** Ø3.000 × 6.000 cylinder with **one** cylindrical face (its OD, r 1.500) and **no bore**: a pin
cannot pass through it and nothing can be bolted to it. It sits in a 6.000 mm pocket in the plate whose
section keeps 53.0494 of 60.1180 mm2 (88.16 %) — the difference is exactly π·1.5² = 7.0686 mm2, the
barrel's own footprint, i.e. the barrel *is* the material in that pocket. A hinge would need a Ø bore
through the barrel for a pin; there is none. **No mating ear, clevis, bushing or bracket for them exists anywhere in
the 30-group population**; the only parts within 40 mm of the surface are the pushrod (0.000), the wing
sector (0.000), the fuselage (**0.499723**), the nozzle (8.735), duct A (10.294) and the three motor
envelopes (28.735 / 28.735 / 37.087). So the delivered elevon is attached to the airframe by nothing.

### 2b. Clash

**None.** The trimmed elevon's common volume with every other part in the population is **0.000000**;
its nearest neighbours are 0.499723 mm (fuselage wall) and 0.000 mm (the pushrod horn — a joint — and
the wing sector's relief, which is a zero-clearance pocket, not a running gap: see §2d). There is no clash to fix on the overhang itself.

### 2c. First-order bending — the assumptions, all stated

Basis taken from the repo, not invented: **Vd = 720 km/h = 200 m/s at 3 km ISA**, `q = 18,180 Pa`
(`PHASE15_CONTROL_SURFACES.md` §2); high-speed deflection limit **12°** (§2); overhang planform
**666.608 mm2**; normal-force coefficient **CN = 0.60** at that deflection (assumption).
Cross-check of that assumption against the repo's own number: `F_total = q·CN·A = 23.96 N`, and on a
26.4 %-chord hinge with the centre of pressure at 50 % chord the hinge moment is
`23.96 × 0.00944 = 0.226 N·m` — inside the repo's stated **0.05–0.20–0.45 N·m** band at 720 km/h. So
the load is consistent with the design document before any result is quoted.

Uniform-load cantilever from the knuckle face, root section = the measured 40.005 × 2.2087 with
I_z = 16.8293 mm4:

| E, GPa | F on the overhang | M at the root | σ (c = 1.3085) | **δ (uniform load)** | δ, tip-load bound | f1 |
|---:|---:|---:|---:|---:|---:|---:|
| **60** (basis) | **7.271 N** | **120.941 N·mm** | **9.404 MPa** | **33.13 µm** | 132.5 µm | **1,665 Hz** |
| 20 (soft bound) | 7.271 N | 120.941 | 9.404 | **99.40 µm** | 397.6 µm | 961 Hz |
| 70 (stiff bound) | 7.271 N | 120.941 | 9.404 | **28.40 µm** | 113.6 µm | 1,798 Hz |

The moment then has to get into the first knuckle, and on its **Ø3.000 barrel** (Z = πd³/32 =
2.6507 mm3) that is **45.63 MPa** — **SF 6.05** on 6061-T6's 276 MPa, with 0.404 MPa of bearing over the
6.000 mm barrel. So the barrel, not the plate, is the loaded element, and it has margin.

**Verdict on strength and stiffness: the overhang is negligible.** 9.4 MPa against a CFRP UTS of
~600 MPa, 33 µm at the design dive speed against a 200 µm minimum leading-edge gap seal, and a first local
mode at ~1.7 kHz against a 5–15 Hz servo. A **gusset is not needed** for either strength or stiffness,
and adding one would be mass spent on a 9 MPa part.

### 2d. Can a third knuckle be fitted at all? — measured, and no

A hinge ear has to reach the hinge axis, and **the hinge axis is inside the plate's material**: at the
hinge station the section is 2.2087 mm thick, so the plate occupies r ≥ **1.104** from its own axis and
out to r = **27.97** (12.12 mm forward of the axis and 27.95 mm aft of it). The plate's swept region is therefore an
annulus **r 1.104 … 27.97 mm** about the hinge axis, at every x the plate occupies (−204.750 … −93.735).

The most generous bracket that could conceivably work was built and tested: a **1.000 mm** arm on the
axis from the fuselage wall (x −101.000…−93.235), a **2.000 × 12.000 × 12.000** ear at the axis, and a
2.000 mm pad on the wall. Rotating the plate over the specified range and measuring the common volume:

| plate rotation | −32° | −20° | −12° | 0° | +12° | +20° | +32° |
|---|---:|---:|---:|---:|---:|---:|---:|
| candidate bracket, mm3 | 65.541 | 60.117 | 58.080 | **56.939** | 57.928 | 59.844 | 65.044 |
| **ear alone**, mm3 | 59.804 | — | 52.315 | **51.174** | 52.163 | — | 59.279 |

It clashes at **every** angle — including 0°, and including the ear with no arm at all, because there is
no orientation in which an ear at the axis is outside the plate's material. Free space between the
fuselage wall and the plate root is **0.499723 mm**, so nothing can pass inboard of the root either. The
only remaining route is a **hinge cutout** — a notch through the plate at the ear's station, sized for
the rotation: with the arm running out radially it must clear the whole chord, which is
**5.18 mm at the leading edge / 12.05 mm at the trailing edge at ±12° (30.1 % of the 40.005 mm chord)**
and **15.21 / 35.44 mm at ±32° (88.6 % of the chord)**. That is not a gusset; it is the surface cut in
half — and the low-speed 32° case is the one the spec asks the servo to use.

**Plain verdict.** No gusset, no third knuckle, no redesign of the overhang: accept the 33.265 mm
overhang as trimmed. The item that is actually missing is the **hinge bracket set** — and it is missing
for *all three* stations, not just the trimmed one (the barrels are solid, unfastenable pegs and no ear
exists anywhere). That is the deliverable to raise, and the overhang does not make it worse: the load
path it adds is 7.271 N and 120.941 N·mm.

**If a gusset were still wanted**, the only clash-free place to put one is *on the surface itself*: a
2.000 mm doubler over the overhang planform costs **1,333.216 mm3 = 2.066 g (+18.9 % of a 10.9027 g
surface)** and would raise I_z by no more than **6.9×** (a symmetric 2.209 → 4.209 mm thickening), i.e.
take 33.13 µm to 4.8 µm — on a part at 9.404 MPa, i.e. 1.6 % of a CFRP UTS. An airframe-side gusset is
the option that clashes (§2d table); a surface doubler is the option that buys nothing. Neither is
recommended, and the overhang should be flown as trimmed.

**One related fact, measured:** the wing's elevon relief is cut to the surface's own footprint — the
gap to the wing sector is **0.000000 mm** with 0.000000 mm3 of interference, and the fuselage is
0.499723 mm away. So the delivered hinge has *no running clearance anywhere*, which is consistent with
no hinge hardware existing: the surface is confined to nothing and attached to nothing.

## 3. (c) The knife edge — plain verdict

Everything below is either re-measured here or carried with its provenance from
`evidence/dm-knife-fairing/REPORT.md`; the fairing's mass is re-measured, not quoted
(`work/s7_fairing.py` → `out/s7_fairing.json`).

### 3a. The residual, at manufacturing scale

| β (measured min convex material angle) | thickness 50 µm from the edge | 100 µm out | distance to a 1.2 mm wall | ramp |
|---|---:|---:|---:|---:|
| **2.8334°** (stock bore rim, z −70.98) | **2.475 µm** | 4.949 µm | **24.246 mm** | 1 : 20.2 |
| 4.0294° (2nd family) | 3.522 µm | 7.044 µm | 17.035 mm | 1 : 14.2 |
| **5.1162°** (faired part, z +172.013 — the residual) | **4.477 µm** | 8.953 µm | **13.403 mm** | 1 : 11.2 |

**Independent re-derivations here:** the aperture census reproduces upstream's stock ray count exactly —
**212 / 262 / 212 of 720 rays** open at z = 0 / 60 / 120, identical on both ducts (**106.0° / 131.0° /
106.0°** of azimuth return no material). That is 78.8–97.4 mm of arc per duct × 242 mm × 2 ducts =
**381.4–471.4 cm2 of flank the fuselage does not have**. And the fairing's cost, re-measured from the
executed STEP: **308,099.037122 mm3 / 477.553508 g / 1 solid / 564 faces / valid**, i.e.
**+101,644.717413 mm3 = +157.549312 g = +49.2335 %** on 320.004196 g — upstream's +157.5493 g reproduced
to 6 decimals.

### 3b. Is 2.8334° acceptable for CFRP manufacture? No.

A 2.475 µm feather is not a tolerance, it is the absence of material: the laminate has to reach zero
thickness, so the last ply is cut to a 2.5 µm wedge over a 24.2 mm band. No layup, print, trim or mould
operation in the drawn material (PLA-core-CF-wrap at 1550 kg/m3) produces that — the fibre ends are cut,
the edge has no land, and the same feature is the boundary of a **hole**: the skin is absent over 106°
of azimuth, so this is not a cosmetic edge, it is the fuselage not being closed (381.4–471.4 cm2). The
"blunt it" option does not exist either: blunting removes material the part does not have, and a fillet
has nowhere to sit because the shortfall is 3.13 mm.

### 3c. Recommendation, with the mass cost

**Recommend the fairing: accept +157.549312 g (+49.2335 %), fuselage 320.0042 → 477.5535 g.** Why:

1. **It is the only measured option that passes.** In-band (z −112…+130) the bore rim ceases to exist
   (0 open azimuths at z = 0/60/120/150) and the bore gets a real land: **1.913 / 1.913 / 1.325 mm** at
   z 0 / 120 / 150, 2.753 / 2.872 at z −90 / −30; still **1 solid**, `BRepCheck` valid, 564 faces.
2. **The alternatives are measured, not argued.** `BODY_HEIGHT 94.97`: **2 solids**, +83.7839 g
   (+26.2 %), +16.4 mm of y envelope, and it still fails the land aft of z ≈ 150. Re-stationing the loft:
   **3 solids** with no fairing at all. Both were built and refuted; nothing cheaper survives.
3. **Roughly half the cost is skin the part was missing anyway.** The smallest patch that would close the
   apertures with the same 1.2 mm skin is **70.9–87.7 g**; the fairing's premium over that is therefore
   **69.9–86.6 g** — the land and the band thickening (walls 1.1990 → 1.5060 and 1.1800 → 1.5766,
   measured upstream), not the hole.
4. **The z +172 residual is not closed by the fairing, and that must not be glossed.** The fairing's gate
   ends at +130; the part-wide minimum after it is **5.1162° at (±45.737, ±42.565, +172.013)**, with a
   land of 0.0242 mm at z 180 and 0.1285 mm at z 210 — i.e. the duct is still not properly shrouded aft.
   It is **bounded, and it is the best the delivered loft allows**: closing it needs either re-stationing
   (**3 solids**, measured) or fairing the tail to Ø89.2 through z ≈ 235, which puts fuselage material
   inside r 41.04 at z 239.8–243.8 — **the ring's Ø82.070 seat** (`dm-knife-fairing` §6, and the ring
   hashes are unchanged there).

So: **accept the fairing, and carry the 5.1162°/0.024 mm aft rim as a documented residual with a 1:11.2
ply ramp** — which is a manufacturable ramp, unlike 1:20.2 to zero thickness. If the bore is ever
required to be a structural seat over its full length, the tail is a separate job and it collides with
the ring seat; that is a redesign, not a fairing.

## 4. The full closure sweep, re-run — the new authoritative total

`work/s5_sweep.py --tag slotted` → `out/s5_sweep_slotted.json`, `log/s5_sweep_slotted.log` (3,443 s).
Same population (**30 as-built solids-groups + 2 code-built D84.0 beads**), same algebra (solid-by-solid
`BRepAlgoAPI_Common`, summed), same tolerance (fuzzy 0.0, bbox pad 1e-6 mm, row threshold 1e-9), same
tie-break: **89 bbox-prefiltered candidates of 496, 71 examined zero, 407 bbox-skipped** — every count
identical to the baseline, so the diff is like-for-like. Substitutions: relieved wings, trimmed elevons,
bored collars, **and the four slotted / mirror-corrected vane brackets**.

`work/s8_diff.py` → `out/s8_diff.json`, **set diff against the C-16 baseline: 18 SAME / 0 CHANGED /
4 REMOVED / 0 ADDED** (−1,032.274334 mm3):

| removed row | baseline | now |
|---|---:|---:|
| `duct_A_vector_vane_1 ↔ servo_mount_vane_A1` | 320.137167 | **0.000000** |
| `duct_B_vector_vane_1 ↔ servo_mount_vane_B1` | 320.137167 | **0.000000** |
| `duct_A_vector_vane_2 ↔ servo_mount_vane_A2` | 196.000000 | **0.000000** |
| `duct_B_vector_vane_2 ↔ servo_mount_vane_B2` | 196.000000 | **0.000000** |

Nothing else moved — not the collar (51.490704 each), not the nozzle lip (20.002085 ×4), not the bead
(2.400232 ×4), not the withdrawn pushrod rows (2.464577 ×2), and not the 6 excluded envelope↔envelope
pairs (200,446.177670). The four rows are gone because **the joint is now a design** (F1/F2/F3 with
0.200/0.050 mm of clearance), not because a number was talked down.

### 4a. The new authoritative total, same basis

| class | pairs | mm3 | vs baseline |
|---|---:|---:|---|
| **GENUINE CLASH** | **0** | **0.000000** | unchanged |
| **DISPOSITIONED CONTACT** | **10** | **192.590677** | was 14 / 1,224.865011 |
| ├ collar on duct (J1) — light press, 0.305 σ_y rigid bound | 2 | 102.981407 | unchanged |
| ├ vane through nozzle exit lip (J3) — lip slot, 0.796 % of the band | 4 | 80.008341 | unchanged |
| └ D84.0 retaining bead across vane (J4) — notch | 4 | 9.600929 | unchanged |
| **WITHDRAWN PLACEHOLDER** | **2** | **4.929154** | unchanged |
| **total (C-12)** | **12** | **197.519831** | was 16 / 1,229.794165 |

> **drone-mech interference, closure basis, after dm-vane-knuckle: 12 pairs / 197.519831 mm3 =
> 0 pairs / 0.000000 genuine clash + 10 pairs / 192.590677 dispositioned contact (collar light-press
> 102.981407; nozzle exit lip 80.008341; retaining bead 9.600929 — the 1,032.274334 vane-root class is
> gone, replaced by a designed running fit) + 2 pairs / 4.929154 withdrawn placeholder. Delta
> −1,032.274334 mm3 / −4 rows, +0 added, 18 rows byte-same.**

Arithmetic checks, to the printed digit: 192.590677 + 4.929154 = 197.519831;
1,229.794165 − 1,032.274334 = 197.519831; and the sweep's own total 200,643.697501 − 200,446.177670
(the 6 excluded envelope pairs) = 197.519831. The sweep's raw total fell 201,675.971835 →
200,643.697501, i.e. by exactly the four rows and nothing else.

## 5. Invariants — both held, byte-identical

`work/s6_verify.py` → `out/s6_verify.json`, run on the population the sweep measures (relieved wings,
trimmed elevons, bored collars, the four slotted/mirror-corrected brackets).

| check | measured | required | |
|---|---|---|---|
| fuselage volume | **206,454.319709018 mm3** | 206,454.319709 | ✔ |
| fuselage mass at 1550 kg/m3 | **320.0042 g** | 320.0042 | ✔ |
| topology | **1 solid / 1 shell / 540 faces**, `BRepCheck` valid | 1 / 540 | ✔ |
| bbox | x ±105.891846, y −48.458738…45.413633, z −360…280 | unchanged | ✔ |
| **sha256 of the operand file** | `d9ba7aeb7716cdd1ba4f289d284944e34e0ebab20202d39335bd9b58ecb9cadf` | unchanged | ✔ |
| wall, fore band | V 67,254.3350 / A_eff 123,170.0573 → **2V/A = 1.0921** | 1.0921 | ✔ |
| wall, pinch band | V 26,262.2633 / A_eff 43,807.5718 → **1.1990** | 1.1990 | ✔ |
| wall, aft band | V 112,937.7213 / A_eff 191,416.3898 → **1.1800** | 1.1800 | ✔ |
| **ring v2 A** | **0.000000 against all 28 parts** (max row 0.000000000) | 0.000000 | ✔ |
| **ring v2 B** | **0.000000 against all 28 parts** (max row 0.000000000) | 0.000000 | ✔ |

The sha256 is the same digest `dm-remaining-26` and `dm-close-clashes` recorded, so the fuselage is
**byte-identical**, not merely equal to six decimals. Neither part was opened by this wave: both fixes
are on the vane bracket (F1/F2/F3 + the mirror rebuild) and nothing else.

## 6. Honest ledger

**Fixed, measured, executed:**

1. **The vane root is assemblable.** Three features cut on all four brackets — F1 2.400 × 3.400 × 29.000
   groove (236.640000 mm3), F2 2.400 × through 2.000 × 33.000 slot (158.400000), F3 Ø3.100 bore
   (1.877134 incremental) — **396.917134 mm3 = 3.909 %** of the bracket, and the residual common volume
   with the vane is **0.000000 on all four** (was 320.137167 / 320.137167 / 196.000000 / 196.000000).
2. **The mirror asymmetry is corrected by rebuilding, not by nudging.** The −y brackets are now the exact
   mirror of the +y: rib +14.000, four lugs +17.000, post −16.000, and the corrected pair reproduces the
   +y joint's **320.137167** to the digit where the drawing had 196.000000.
3. **The overhang is bounded and accepted.** 33.265 mm, 3.0997 g, **33.13 µm** at the design dive speed
   (9.404 MPa in the plate, 45.63 MPa in the Ø3 barrel at SF 6.05, first local mode 1,665 Hz). No gusset.
4. **The third knuckle is refused on measurement, not on opinion**: the swept annulus about the hinge
   axis is r 1.104…27.97 mm, the free space between the fuselage wall and the plate root is 0.499723 mm,
   and every candidate bracket — including a bare ear with no arm — clashes at all seven rotations
   tested. The cutout it would need is 30.1 % of the chord at ±12° and 88.6 % at ±32°.
5. **The knife edge is adjudicated** and the fairing's cost re-measured: **+157.549312 g / +49.23 %**,
   of which 70.9–87.7 g is skin the part does not have at all.
6. **Both invariants held byte-identical** (§5).

**Open — named, not hidden:**

1. **The hinge bracket set does not exist — for all three stations.** The knuckles are solid Ø3 × 6 pegs
   (volume = πr²L to 1e-9, one cylindrical face = the OD, no bore), with no mating ear anywhere in the
   30-group population. The elevon is held to the airframe by nothing: pushrod and wing relief touch at
   0.000 mm, the fuselage is 0.499723 mm clear, and everything else is ≥ 8.735 mm away. This is older
   than the trim and larger than it: it is the deliverable the overhang question actually raises.
2. **The 2.000 mm bearing land** carries the hub at 0.67 d — below the 1.5 d a running fit wants. The
   Ø3.100 bore fixes the *fit*, not the *length*; a longer boss means moving the rib, which is outside
   this task.
3. **The rib is now two straps.** F2 splits the 27.000 mm rib into 12.300 + 12.300, joined only through
   the plate. 91.006 % of the rib's material survives, but its load path now depends on the plate bond,
   and the bracket is carried as BREP (7 → 8 solids), not as a bonded assembly.
4. **The aft bore rim at z +172 stays at 5.1162°** with a 0.0242 mm land at z 180 — bounded and
   documented, not closed (§3c).
5. **All masses are geometric at 1550 kg/m3 (CFRP) / 2700 kg/m3 (bracket, stated) — no layup, ply drop,
   bond line or fastener is modelled anywhere in this report.**
6. **The (b) load is a first-order uniform-load cantilever** with a stated CN = 0.60 and E band 20–70 GPa;
   it is not a finite-element result and it does not address flutter, which needs the whole surface and
   the hinge compliance that does not yet exist.

**The numbers to quote**

> **drone-mech: 12 pairs / 197.519831 mm3 on the closure basis = 0 genuine clash / 0.000000 +
> 10 dispositioned contact / 192.590677 + 2 withdrawn / 4.929154** (from 16 / 1,229.794165), all of the
> 1,032.274334 drop being the four vane-root rows that the F1/F2/F3 slot took to **0.000000**. The −y
> bracket pair is now a true mirror (+14.000 rib / +17.000 lugs / −16.000 post corrected). The 33.265 mm
> overhang is accepted at 33.13 µm / 9.404 MPa and needs no gusset; a third knuckle cannot be fitted
> (clash at 7/7 rotations, cutout 30.1 % of chord). The knife edge needs the fairing at **+157.549312 g**
> (+49.23 %), leaving a bounded 5.1162° aft rim. Fuselage byte-identical; rings 28/28 clean.
> | `evidence/dm-vane-knuckle/`

## Appendix — method, provenance, limits

| item | value |
|---|---|
| interpreter | `C:\Program Files\Python312\python.exe` (Python 3.12) |
| kernel | cadquery 2.7.0 / OCP 7.8.1.1 (OpenCASCADE) — no KiCad, no solver |
| volume | `BRepGProp.VolumeProperties_s(shape, props, 1e-12)` |
| booleans | `BRepAlgoAPI_Common` / `BRepAlgoAPI_Cut`, fuzzy 0.0, solid-by-solid |
| distance | `BRepExtrema_DistShapeShape`; containment `BRepClass3d_SolidClassifier` tol 1e-6 |
| section 2nd moment | `∫y²dV = (Izz + Ixx − Iyy)/2` from `GProp_GProps::MatrixOfInertia`, /dx |
| rays | `IntCurvesFace_ShapeIntersector`, 0.5° in azimuth in the x-y cross-section plane |
| operands | 30 STEPs + 6 BREPs copied from `dm-close-clashes/work/{obj,fix}`; `dm-knife-fairing/out/*.step` read-only; sha256 of every input and output in `SHA256SUMS.txt` |
| write scope | this directory only; no repo write, no commit, no reset |

| script | produced |
|---|---|
| `work/s1_inspect.py` → `out/s1_inspect.json` | the joint census (7 boxes / 0 cylinders), the four rows, the elevon's 4 solids, the pushrod gap |
| `work/s3_slot.py` → `out/s3_slot.json` | **the execution**: mirror residual per solid, `A2 := mirror(A1)`, F1/F2/F3 on all four, residual overlap and clearance |
| `work/s4b_section.py` → `out/s4b_section.json` | plate continuity by band (sum reconciles to 0.000000), measured A / thickness / **I_z = 16.8293 mm4** |
| `work/s4_knuckle.py` → `out/s4_knuckle.json` | overhang, knuckle census, support distances, the bending check, the 7-rotation fit test, the cutout widths |
| `work/s5_sweep.py --tag slotted` → `out/s5_sweep_slotted.json` | the full closure sweep |
| `work/s6_verify.py` → `out/s6_verify.json` | fuselage invariants (sha256, walls) and the two rings against 28 parts |
| `work/s7_fairing.py` → `out/s7_fairing.json` | the fairing's mass re-measured (+157.549312 g), the aperture ray census (212/262/212 of 720), the land/ramp table |