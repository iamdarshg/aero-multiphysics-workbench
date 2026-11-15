# AGENT BOARD — engineering-portfolio-audit

**This is the pinned board.** Every agent reads this first and writes its status line back here.

### Governing principle — owner, 2026-11-15

**More spend now means less effort in the long run. Always keep that in mind.**

This refines the "least effort" steer: the objective is least **total lifetime** effort, not least
immediate effort. A cheap choice that forces rework, a second spin, or a recurring manual step is
the expensive choice. Spend is acceptable when it removes future effort.

How to apply it:

| situation | pick |
|---|---|
| a $60 coupon that may settle Z0 vs a $300 set that definitely settles it | take the set that actually settles it, if it prevents a respin — state the case, do not silently refuse |
| a routing move that dodges today's voids, vs reassigning In1 to a solid ground plane | the structural fix if the board is going to be revised anyway |
| a part swap that fits the current footprint at the edge of its rating, vs a package change that has margin | the one with margin, because an under-rated part becomes a warranty problem |
| fab cost to hold a tighter tolerance vs a design that needs the tighter tolerance | pay for the tolerance; a design change costs more |
| deleting nets to make a measurement look clean, vs routing them properly | route them |

The $60 cap on coupons and the no-HDI rule stand. This principle does not override an explicit
limit; it tells you how to spend *within* one and how to argue for more when the evidence says the
limit is the false economy.

---


### Board roster and copper weight — owner, 2026-11-15 (measured against the files)

**Every board is 4-layer. No board may use HDI. Standard plated through vias only.**

| board | file | layers | copper | owner rule |
|---|---|---|---|---|
| **ESC rev_b** | `drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb` | 4 | **0.14 mm outer = 4 oz**, 0.0525 mm inner | **4 oz required** — already declared |
| drone-arm main rev_b | `drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb` | 4 | 0.035 mm = 1 oz | 1 oz |
| Code-SDR V2 | `Code-SDR/hardware/v2/Code-SDR-V2.kicad_pcb` | 4 | 0.035 mm = 1 oz | 1 oz |

Measured by parsing the `(stackup ...)` block of each file. Thicknesses map as
0.035 = 1 oz, 0.0525 ≈ 1.5 oz, 0.07 = 2 oz, 0.14 = 4 oz.

**Consequences that are now hard requirements:**

1. **A 0.1 mm drill is not fabricable on a 4-layer non-HDI board.** Any via below the fab's
   mechanical minimum (typically 0.2 mm, sometimes 0.15 mm) must be converted to a standard through
   via. This is why the "36 × 0.1 mm HDI vias on drone-arm rev_b" is a genuine blocker and not a
   labelling issue — on a 4-layer standard board those vias cannot exist.
2. **4 oz copper on the ESC forces larger minimum trace width and spacing.** Typical 4 oz design
   rules are **0.20–0.25 mm minimum trace and space** versus 0.10–0.15 mm at 1 oz, plus a larger
   minimum via annular ring. Any ESC routing drawn to 1 oz rules must be checked against 4 oz rules,
   and likely will not pass.
3. **4 oz changes the achievable impedance.** The ESC is a power board so this matters mainly for
   creepage and current, not for RF — but if any controlled-impedance net runs on the ESC it must be
   recomputed at 0.14 mm copper.
4. **Only the ESC gets 4 oz.** Main rev_b and Code-SDR V2 stay at 1 oz. An ESC-only weight change
   does not touch the other two boards.

---

### CFD — FINAL numbers, and the unresolved sign of Cl

Run capped at t/c = **1.8057** (t_end 2.816310e-3 s, U 222.1322, lRef 0.34646), 630 time levels,
**5.98 h** total wall across 4 launches, 2.01 steps/min.

| | mean over final 20 % (112 samples, t/c 1.448–1.806) | scatter | drift in window |
|---|---|---|---|
| **Cl** | **−0.016412** | 1.31 % | **+0.19 %** — locally flat |
| **Cd** | **0.011228** | **13.15 %** | **−40.13 %** — still falling |

**Verdict: NOT CONVERGED.**

- **Cd cannot be quoted.** Its last sample (0.00790) sits **30 % below its own window mean**, and the
  0.5-chord block means go 0.01226 → 0.01132 (−7.71 %) with the previous block 26–33 % away. The
  relaxation rate is collapsing toward zero but has not arrived.
- **Cl can be quoted only as −0.0164 ± 0.0011**, the measured half-chord movement, explicitly
  **not converged**. The 0.5-chord block means move −0.01510 → −0.01611 (−6.70 %).

My independent merge of the same traces agreed with this to three digits (Cl −0.01646 vs −0.01641,
Cd 0.01110 vs 0.011228), which is why the retraction at `a519125` stands.

### The open flag: Cl is NEGATIVE and the sign is unexplained

Lifting-line theory at ±0.5° for AR ≈ 1.03 gives **|Cl| ≈ 0.017** — so the **magnitude fits and the
sign does not.** Either the section sits at −0.5° in this frame, or `liftDir` is inverted. `liftDir` is
`(0, 1, 0)` and Cd/Cs reproduce algebraically to 10 digits, so the axes are self-consistent — but
self-consistency is not correctness.

**Flagged, not resolved.** It must appear in the document as an open question with the lifting-line
cross-check beside it. Do not silently flip a sign to make it look better, and do not publish a Cl
without this caveat attached: a −0.0164 that should be +0.0164 is a different aeroplane.

### Is 5 chords reachable

**Not in one turn.** 1,113 more steps ≈ 9.2 h from here, ~14.4 h from t = 0 at the measured rate —
the original 9 h estimate was **1.6× optimistic**. But the case plus **nine checkpoints**
(0.000398 … 0.002398 s) survive at `/root/dmconv-373`, and `scripts/60_continue.sh` resumes while
`70_collect.sh` re-analyses, so about **2.3 further 4-hour blocks** finish it with nothing redone.

### Operational finding worth keeping

`writeControl runTime` anchors writes to `startTime`, so after a restart the first checkpoint can be
**70 minutes away** — a kill then costs 70 minutes, not the interval you think you set. Switching to
`adjustableRunTime` with a 2.5e-4 s interval caps a kill at **≤30 min**. That single line is why the
second collision was survivable.

---

### What this upgrades

`Cl` moves from "no quotable coefficient" to **MEASURED-CONVERGED at −0.0149 ± 0.6 %**. `Cd` remains
unconverged at 0.0114 with a stated decay rate and a labelled extrapolation. So the document can now
carry **one genuine SOLVER coefficient** instead of none — and it should carry it with the zero-lift
explanation, because −0.015 looks like a broken number to anyone who does not know the incidence is
near zero.

The run continues toward its 4 h wall cap. A further poll will capture the final trace.

---

### CFD force extraction — the real defect is an OPEN-SURFACE pressure bias

The mesh settles the question completely. **There are only five patches:**

| patch | faces | type |
|---|---|---|
| `fsi` | **21,680** | wall — the wetted wing skin |
| `rootWall` | 1,582 | symmetryPlane — **this is the root cut plane** |
| `farfield` | 42,490 | patch |
| `inlet` / `outlet` | 4,760 each | patch |

Inside `fsi`: upper 10,077 · lower 10,091 · tip cap 1,312 · TE 200.

`fsi` is **not** a plane: planarity measure **0.060** (`rootWall` = 1.000, x = 0.0803 constant),
extent **0.180 × 0.030 × 0.389 m**, carries `no-slip` plus `nutk`/`kqR`/`omega` wall functions, and
`Aref`/`lRef` (0.062249 / 0.34646) reproduce its planform to 0.3 %. **The root cut plane is
`rootWall`, and it was already excluded.** So the instruction to "re-target the force integration onto
the wetted walls" was **impossible — there is no other wetted patch to target.**

**The actual defect, which is larger and more interesting: absolute pressure is integrated over an
OPEN surface.** `fsi`'s only hole is the root cut, so the unresolved reference pressure does not
cancel. The bias is analytic and exact:

```
bias = p_ref · Σ(Sf) / (q · Aref) = +0.399659     in Cs
measured force shift 557.990 N  vs  557.982 N ANALYTICAL   (residual 0.009 N)
```

**Bit-identical restart comparison (75 matched rows, t/c 0.258–0.490, max relative difference
0.000e+00):**

| | `fsi` only | `fsi` + closed with `rootWall` |
|---|---|---|
| Cd | 1.846835e-2 | 1.846835e-2 |
| Cl | −1.325913e-2 | −1.325913e-2 |
| **Cs** | **−0.393046** | **+0.006613** |

`Cd` and `Cl` are **bit-identical** between the two configurations because the plane's Σa_y and Σa_z
are 1e-16 — machine zero. **Only the spanwise component carries the bias.** Closing the surface gives
**Cs = −0.00185**, which is the physically expected near-zero for a zero-sideslip sector.

**Direction convention, ruled out by algebraic reproduction:** drag **+z** (`U_inf = (0,0,222.1322)`),
lift **+y**, span **+x**, pitch **+x**. `F_z/(qA) = Cd` reproduces to 10 digits, and a quarter-chord
`CofR` shifts `CmPitch` by −1.16668e-3 against an analytical moment arm of −1.1667e-3. **No axis
swap.**

### What is quotable

| quantity | status |
|---|---|
| any coefficient | **NO.** Cl drifts −12 % per window at 3.8 % scatter; Cd −4.6 % at t/c = 0.49 |
| the **bias** dCs = **0.399659** | **YES** — geometric, exact, reproducible |

Compute: t/c = 1 needs ~1.7 h; **t/c = 5 needs ~15 h**; a 4 h cap reaches only t/c ≈ 1.7.

---

### CFD force extraction — CORRECTION: the `fsi` patch is 93.9 % wing, not a cut plane

**I asserted that `Cd` and `Cl` from the drone-mech CFD run were "not aerodynamic coefficients at
all" because the force integration used `patches (fsi)`, which I described as a root cut plane. That
was wrong.** A subagent measured the patch geometry from the decomposed mesh instead of inferring it
from the name:

| measurement | value | what it means |
|---|---|---|
| `fsi` total area | **0.1324 m²** ≈ 2 × `Aref` (0.1245 m²) | **both wetted sides of the wing** |
| face-centre bbox | x 0.1791 m, y 0.0301 m, z 0.3877 m | = span, = max thickness, = chord + curvature |
| \|Σ area-vector\| / area | **0.060** | an almost closed surface — **a plane would be 1.000** |
| faces with \|n_x\| > 0.9998 | **6.1 %** of faces | the embedded root plane |
| their summed area vector | (−7.96e-3, 0, 0) m² | equals `rootWall` symmetryPlane area 7.959923e-3 **to all digits** |
| plane's Σa_y, Σa_z | 1.4e-19, −5.1e-19 m² | **machine zero** — contributes to x only |

So **`fsi` = 93.9 % wetted wing surface + 6.1 % root plane.** The plane sees wing-root pressure
≈70 kPa × 7.96e-3 m² ≈ **557 N**, which matches `force.dat` total_x = **−561 N**. That is the entire
spurious spanwise force.

**Consequences:**

1. **`Cs` (≈ −0.40) is polluted and must not be quoted.** It is the root plane's pressure load,
   expressed as a coefficient.
2. **`Cl` and `Cd` ARE genuine wetted-surface integrals.** They can be quoted **once the trace
   converges** — which it has not, since Cl carries 25.8 % scatter and −85.9 % drift over its final
   window.
3. **Keeping `patches (fsi)` was the correct choice.** Splitting the plane out would have required a
   restart for no gain, because the pollution is confined to the one component nobody needs.

**The lesson, which is the same one as the 5 cm² and the 26.37 % errors:** the symptom (`Cs` is 38×
`Cl`) was real, but the *cause* I attached to it was inferred from a patch **name** rather than
measured from the patch **geometry**. A name is a comment; the mesh is the evidence. Three times now
the fix has been "measure the population, do not reason about its label".

The `auditing-numeric-deliverables` skill has been corrected to carry the mesh-measurement recipe and
the measured 93.9 / 6.1 split, so this cannot be re-derived wrongly.

---

### Body structure — first SOLVER-tier result on the fuselage (rev7 pending)

Prior structural work covered only the wing sector. This is the **first solver analysis of the
fuselage body**, and it moves structure from ANALYTICAL to **SOLVER**.

**Load case, and the two it beat.** Battery inertia: 2 × 0.28 kg at a 6 g limit × SF 2.0 =
**12 g ultimate**, giving **65.9 N** into the 2 × 4 mm rail land at the open-aperture bay.

| rejected case | why it lost |
|---|---|
| wing-join bending | 29.67 N·m yields only **2.53 MPa** on the bore-limited Zx 11,737 section — it tests duct layout, not wall thickness |
| duct thrust | **no citable thrust exists** (the CFD forces sit on the `fsi` cut plane); duct is bonded over 4 × 110 mm giving 0.60 MPa |

**Model:** CalculiX 2.21, S4 shell idealisation of the design intent, **5,786 elements / 5,953
nodes / 35,718 dof, 8.9 s**, niced beside the live CFD run. Refined to 11,047 nodes in 17.4 s.

| quantity | value |
|---|---|
| peak deflection | **0.139 mm** at E = 10 GPa; **band 0.069–0.277 mm** over 20/10/5 GPa |
| sag at pack station | 0.027 mm |
| peak stress | **2.85 MPa** (3.23 MPa at 1.43× refinement), at the clamped ring |
| bay field stress | **1.78 MPa** at the rail land; 95th percentile 1.47 MPa |
| scaling check | u·E = 1.38541 **identical at all three E** — exact 1/E; stress E-invariant to 6 digits |
| independent check | thin-wall Zx 5,146 mm³ → 1.81 MPa vs solver 1.78 MPa (**1.7 %**) |

**Verdict: the 1.2 mm wall is ADEQUATE, not marginal.** FoS **5.4** at the worst point, **9.7** on the
field, against a PLA allowable of 17.3 MPa (wrap 250 MPa). At 0.8 mm: 5.15 / 3.25 MPa, FoS 3.4 / 5.3.

**Design guidance:** local peaks (rail land, aperture corner) scale **1.81× for 0.67× thickness**, so
thin the sides and thicken the aperture corner and rail pad. A 1.2 mm lid bought **−31 % deflection
but only −4 % stress** — that is stiffness, not strength, and it is not worth the mass.

**The gating caveat, which belongs beside the results and not in a footnote:** the 42_6 export is
**4 disjoint solids over 77.165 mm**, so every stress number describes the **repaired design intent**.
A **+97 g Boolean repair is a prerequisite** before any of it is true of a manufacturable part.
`BRepCheck_Analyzer` confirms 42_6 itself is valid (4/4 solids, 0 free edges), and that exactly three
of the six shells are invalid — and they are the three 4-solid repairs.

**C1 WAS CONSERVATIVE, so the saving was understated.** The 42.7 g replacement cone wall runs at
**0.44 MPa** (2.5 % of allowable) at 1.2 mm, 0.75 MPa at 0.8 mm, and 2.28 MPa even if the 1 kg payload
rides in the hollowed nose. So **C1 is −69.1 to −83 g**, not −69.121 g — the 1.2→0.8 mm licence is
worth up to ~14 g, and the remaining 42.7 g is surface that must exist. rev7 publishes the range.

**A correction to earlier work, in the safe direction:** `body-mass-opt` used an open-top
Zx of **2,134 mm³**, which is **2.4× below** the 5,146 mm³ the same section yields here (areas agree to
1.2 %, closed rings to 3.5 %). So that report's stress conclusions were **conservative, not
optimistic** — it erred safely, which is worth recording rather than quietly fixing.

**What this analysis does NOT cover:** buckling, frequency, fatigue, bond, fastener and printed
anisotropy are outside the model. The √E cross-check was unavailable because no modal step was run.

---

### drone-mech body — FINAL state (rev6)

**Deliverable:** `evidence/pdf-rev6/drone_mech_body_evidence_rev6.pdf` — **20 pages**, 379,657 bytes,
sha256 `9E6AF0A736D0DABACB76EC61EB5ED967EBA9C2ECFBDC919343174CCFD9D369C7`.
Gates **G1–G10 pass**; unit audit 607 args / 500 words / **0 mismatches**; declaration audit **0 gaps**.
Supersedes rev1 (8 pp) → rev2 (11) → rev3 (14) → rev4 (16) → rev5 (19).

| quantity | value | tier |
|---|---|---|
| body of record | 42_6 shell, 4 solids, 742,306.360 mm³ | MEASURED |
| **mass** | **472.273 g**, band 431.943–521.637 g | ANALYTICAL on MEASURED volume |
| wall | 145.739 g PLA core + 105.779 g CF/glass wrap = 251.518 g | ANALYTICAL |
| fill | 624,770.5 mm³ at effective 353.3 kg/m³ = 220.755 g | ANALYTICAL |
| empty-interior floor | 372.31 g | ANALYTICAL |
| ceiling | 1,088.1 g | ANALYTICAL |
| **optimisation package** | **−86.981 g**, band **−112.02 … −60.33 g** | ANALYTICAL |
| drag total | 87.96 cm² (body 67.04, nose 30.03) | ANALYTICAL on MEASURED areas |
| facts graded | 87 MEASURED · 112 ANALYTICAL · 41 ASSUMED · **0 SOLVER** | — |

#### The optimisation rows, finally correct

| row | published | corrected | what was wrong |
|---|---|---|---|
| C1 cones | −61.0 g | **−69.121 g** (nose −64.236, tail −4.885) | cut face at z=−298.8 is **11,627.3335 mm²** + 545.3851 annulus = 12,172.7186, not 6,359.0 — that figure is the **bay's enclosed section**, and the same file reports it as the cap of *both* the nose and the bay fill. S_outer = 25,539.500 mm². |
| C2 hatch | −27.50 g | **−27.496 g** ✓ | correct, and its sign flipped from the earlier **+41.7 g cost** because the removed block is printed PLA |
| C3 thinning | −12.81 g | **−9.291 g** | the 26.37 % used is the **whole-body** triangle share (0.26357 of 285,216 mm²); **wall-only is 19.13 %** (33,473.7 of 175,023.6 mm²). A body-wide numerator was applied to the wall's 97,943 mm². |
| C4 | −9.35 g | **−8.569 g** | same population mismatch |
| **package** | −87.8 g | **−86.981 g** | rows were wrong; the total was nearly right by cancellation |

**An independent arithmetic refutation of the old C1 input:** 415,035.7 mm³ over 61.2 mm averages
**6,781.6 mm²** — larger than any 6,359 maximum. The wrong number could have been caught with a
division, before any geometry was read.

**Band widths restored.** The *package* band (−99.0…−58.5) always contained the truth, so it survived.
The **row** bands did not: C3's 0.2 g band excluded −9.29 by 3.5 g. C3 is now −9.44…−8.30 and C4 is
−8.71…−7.66, widened across density × band measure × mid-surface basis. A band narrower than its own
doubt is worse than no band.

**The 0.09 g disagreement with the verifier is located and printed.** They got −86.9, the rebuild gets
−87.0. Cause: they left C1's **tail** half on the enclosed-section cap (337.7 mm² where the material
face is 536.4 mm²), worth 0.30 g, offset by +0.06/+0.14 g from tessellated band fractions. Correcting
one plane and not the other would put a single row on two rules, so **both planes were fixed and the
0.09 g is stated in the document.**

#### Two process facts this document now states

1. **sha256 is NOT reproducible across rebuilds.** rev5's report claimed it was; it is not. reportlab
   stamps a creation date and a document ID, so page *text* is stable while file *bytes* are not.
   rev6's report states this accurately rather than repeating the claim.
2. **The defect class no gate could see**, now named in the correction history: *a correct measurement
   of the wrong population.* Three instances — the 150/1550 density pairing, the 26.37 % body-wide
   fraction applied to the wall, and the 6,359.0 bay section used as a nose cap. Arithmetic checks
   pass in all three, because the arithmetic is fine; the input is from the wrong population.

The withdrawals table and correction history are **cumulative** — five waves listed, nothing removed.

---

### drone-mech body — corrected mass (supersedes every earlier figure)

Three mass models have been tried. All were wrong. The fourth is the one with a real input basis.

| model | figure | why it was wrong |
|---|---|---|
| wave 1, ρ=1550 on all | 1,150.6 g | assumed the whole 742,305.5 mm³ was carbon laminate |
| wave 1, ρ=150 on all | 111.3 g | assumed the whole thing was light fill |
| wave 2, split | 275.9 g | right structure, wrong both inputs — 34.9 % below the empty-interior floor |
| **wave 3, reconciled** | **472.27 g** | band **431.94–521.64 g** |

**Why it went up, not down.** Two inputs were wrong and both under-counted:

1. **The fill is not 150 kg/m³.** The repo's own saved OrcaSlicer profile sets **15 % sparse infill**
   (`effective-process.json:109`) with **1.26 g/cm³** PLA (`effective-filament.json:72-74`). But the
   slicer also prints a **0.87 mm solid perimeter skin** on every boundary, so a real 15 % slice
   deposits **~27 %** of the solid model's volume — verified against the repo's **two real slices**
   at 27.10 % and 23.20 % against a model of 26.80 % and 23.58 % (**±1.63 %**). Effective fill
   density is **353.3 kg/m³**. Fill weighs **220.76 g, not 93.72 g**.
2. **The wall is not carbon laminate.** The CAD wall is **printed PLA**; the repo books a PLA-core
   mass *and* a separate laminate mass over the same mid-surface
   (`phase12_fixed_powertrain_design.json:197, :203-210`). Charged correctly the wall is
   **251.52 g, not 182.17 g**, and the missing wrap is **105.78 g** that neither previous model
   counted.

**The 275.89 g figure is not merely low, it is physically unreachable.** Even a body with a
completely **empty interior** — printed skins only — weighs **372.31 g**. The previous figure sat
**96.42 g (34.9 %) below that floor.**

**Genuine upper bound: 1,088.09 g** — solid material at the slicer's own density plus the repo's
maximum layup. The withdrawn 1,150.57 g exceeded it by 5.7 %, so it is refuted on a second,
independent basis.

**Mass is a function of infill, not a band:**

| infill | 0 % | 5 % | 10 % | 15 % | 25 % | 40 % | 100 % |
|---|---|---|---|---|---|---|---|
| mass | 372.3 g | 405.6 g | 439.0 g | **472.3 g** | 538.9 g | 638.9 g | 1,038.7 g |

All 52 citations machine-checked (52/52) before any number is believed.

### Deliverable

`evidence/pdf-rev3/drone_mech_body_evidence_rev3.pdf` — **14 pages**, sha256
`21C0FC22E2B57ED65ECC1E09C46E03B9CBA0B5A1BF577DF94B1FB5C467CBB70C`, **208 graded facts:
81 MEASURED · 86 ANALYTICAL · 41 ASSUMED · 0 SOLVER**. Supersedes rev1 (8 pp) and rev2 (11 pp).

Three revisions because the first two were wrong, and each wrong version was caught by an adversarial
verifier rather than by the author. The withdrawals table is cumulative — nothing withdrawn has been
quietly dropped.

---

## drone-mech body — DELIVERED (rev9, final)

**`evidence/pdf-rev9/drone_mech_body_evidence_rev9.pdf`** — **32 pages**, 577,432 bytes, 177,656 chars,
sha256 `AAE9EE638E6F26B45A260BE584A2C899DED2F5080F5A0A976D064F56F1A0EF2D`.

Nine revisions. Every one replaced by a verifier's finding, not by a second opinion.

### The numbers, by tier

| quantity | value | tier |
|---|---|---|
| body of record | 42_6 shell, 4 solids, 742,306.360 mm³ | MEASURED |
| **mass** | **472.273 g**, band **431.943–521.637 g** | ANALYTICAL on MEASURED volume |
| wall | 145.739 g PLA core + 105.779 g wrap = 251.518 g | ANALYTICAL |
| fill | 624,770.5 mm³ at effective 353.3 kg/m³ = 220.755 g | ANALYTICAL |
| empty-interior floor | 372.31 g | ANALYTICAL |
| ceiling | 1,088.1 g | ANALYTICAL |
| **optimisation package** | **−87.0 … −101.2 g** (C1 −69.1…−83.4, C3 −9.4…−8.3, C4 −8.7…−7.7) | ANALYTICAL |
| **structure** | FoS **5.4**, peak **2.85 MPa**, **0.139 mm**, E swept 5/10/20 GPa | **SOLVER** |
| **aero Cl** | **−0.0164 ± 0.0011**, explicitly **NOT converged** | **SOLVER** |
| aero Cd | **cannot be quoted** — 30 % below its own window mean | **SOLVER**, withheld |
| drag build-up | 87.96 cm² total (body 67.04, nose 30.03) | ANALYTICAL |
| instrument bias ΔCs | **+0.3997**, reconciles −0.3906 + 0.3997 = **+0.0091** vs closed **+0.0066** | ANALYTICAL / SOLVER |

Tier histogram: **506 facts = 132 MEASURED · 69 SOLVER · 255 ANALYTICAL · 50 ASSUMED.**
Gates G1–G21 pass. Refuted inputs `6,359.0` and `31,353.2` appear **zero** times.

### What each revision corrected

| rev | what was wrong |
|---|---|
| 2 | mass 1,150.6 g — assumed the whole volume was carbon laminate |
| 3 | mass 275.9 g — right structure, both inputs under-counted, **34.9 % below the empty-interior floor** |
| 4 | R4 measured on an uncut shoulder; a row tiered MEASURED that was a volume × assumed density |
| 5 | −47.4 g withdrawn: costed against a body later shown unreachable |
| 6 | C1 used the **bay's enclosed section** (6,359.0 mm²) as a nose cap; C3/C4 applied a **whole-body** fraction to the wall |
| 7 | C1 published as a point when the licence made it a range |
| 8 | **published a retracted claim**: Cl "converged −0.0149 ± 0.6 %" |
| 9 | replaced it with **−0.0164 ± 0.0011, not converged**, and moved the retracted figure into the withdrawals table |

### The four things this program learned the hard way

1. **A correct measurement of the wrong population.** Three instances: the 150/1550 density pairing,
   the 26.37 % body-wide fraction on the wall, the 6,359.0 bay section as a nose cap. Arithmetic
   passes in all three; the input came from the wrong population.
2. **A band narrower than its own doubt manufactures confidence.** C3's 0.2 g band excluded the truth
   by 3.5 g.
3. **A name is a comment; measure the geometry.** `fsi` was called a cut plane in a report and is a
   93.9 % wetted skin by measurement (planarity 0.060 vs `rootWall` 1.000).
4. **A convergence claim is itself a measurement.** ±0.6 % scatter over 0.2 chords looked flat and
   hid an 11.8 % swing over the next 0.5. Convergence is tested by **extending the window**, not by
   measuring the noise inside it.

### What remains open, and is written as open

| id | question |
|---|---|
| **O4** | the CFD run is the **wing sector** (`wing_t30mm`), not the fuselage — no body coefficient exists |
| **Cl sign** | measured Cl is negative; lifting-line at ±0.5° for AR≈1.03 gives \|Cl\|≈0.017, so magnitude agrees and **sign does not** — either the frame incidence is negative or `liftDir` is inverted. Flagged, not resolved. |
| **U15** | C1 tail model, 0.30 g |
| **U16** | alternate charge basis: −81.8 / −99.6 g on §6.1's own 38.003 g |
| **disjoint solids** | the 42_6 export is 4 disjoint solids over 77.165 mm; **+97 g Boolean repair is a prerequisite** before any stress number is true of a manufacturable part |
| **Cd** | needs ≈14.4 h from t=0, or better, a **phase-averaged** extraction over ≥3 oscillation periods rather than a longer monotone run |

---

### ESC compaction — VERDICT: UNSAFE. The area came off the power path.

The compaction achieved **−121.61 cm² (−24.73 %)** and kept **0 of 687 components on the back**. It
also **broke the board's ability to carry its own current.** This is the failure mode that was flagged
before the work started, and it happened.

**Power path, measured with the same maximin method that reproduced the original's numbers:**

| net | original | compacted | required at 60 A on two faces | verdict |
|---|---|---|---|---|
| `/M1_PHASE_A` | 7.51 mm | **1.50 mm** | **6.991 mm** | **4.7× short** |
| BATP | 1.763 mm | **0.70 mm** | — | short |
| battery feed | 17.14 mm | 40.85 mm | — | 0.54 → **1.29 W/channel** |

**Via ampacity was never counted by anyone:** at ~3.0 A per barrel, a phase transition needs **21 vias
per transition**. That alone may make the compaction unrecoverable at this current.

**Routability is worse, not better.** At 0.250 mm rules: **934 violations against 523** — **2.38× per
cm²**, including **51 shorts**. The 371 pad-to-pad gaps are invariant (they are footprint-bound), and
unconnected sits at 499/1620 depending on tool. So the compaction made a board that was already hard
to route harder.

### The area floor was 370, not 316

The 316 cm² figure reproduced arithmetically but rested on **two assumptions**:

1. It put **all three 60 A phases on ONE 0.14 mm face.** Two faces give 6.991 mm each — 22.173 mm
   across — and the floor becomes **254.91 cm²**, not 316.
2. Its terminal area of 400 mm² was **ASSUMED**; the board's own lugs are **1267 mm² per cell**. Put
   the real lugs back and the floor is **370.38 cm²**.

The delivered compaction measured **370.12 cm²** — **0.07 % apart by two independent methods.** So:

| figure | what it is |
|---|---|
| **370 cm²** | the honest floor for **today's BOM** |
| **316 cm²** | needs the **lug change** |
| **255 cm²** | the true ceiling, if current is carried on two faces |

So the area target was right and the *placement* was wrong. There is room at 370 cm²; there is no
room with a 1.50 mm phase trace.

### Two arithmetic slips, and a rule under the standard

- The published height formula with an "18.0" control strip yields **243.28**, but the board uses
  **16.47**.
- `05_floor.log` §6 closes at **412.96** against a board of 492.42 — the two halves do not reconcile.
- **The creepage rule of 0.5 mm is below IPC-2221B B2's 0.60 mm.** The layout achieves exactly
  **0.5999 mm**, which passes the standard by 0.0001 mm while the stated rule would have permitted a
  fail. Right answer, wrong rule.

### What this means for the compaction request

**Compact is achievable at 370 cm². The specific placement delivered is not viable.** It needs
re-doing with the phase copper widths as a hard constraint rather than a derived output — that is,
place the power path first and fit the small parts around it, instead of placing parts and hoping the
copper fits.

60 A is **ASSUMED** in both the placement and routability units. If the real per-phase current is
lower, the constraint loosens proportionally; that number should be confirmed from the FETs before the
placement is redone.

---

### Span labelling corrected, and a tooling trap that fakes a pass

**The four In1→In2 vias are BURIED, not blind.** A microvia is a *drill class*, not a span class —
lumping it with "blind" conflated two different things. The true span census of the best drone-arm
artefact is:

| reading | through | blind | buried | total non-through |
|---|---|---|---|---|
| **by span** | 321 | **11** | **4** | **15** |
| by declared type | — | 1 | — | 14 micro + 1 blind |
| by depth | — | 12 | 3 | 15 |

All three readings agree the answer is **15**, and the **diameter gate sees only 14** because it
cannot see the 0.300 mm In2→B via at all. **Buried is worse than blind for fabrication** — sequential
lamination plus an internal-only connection — so the label matters.

`evidence/fab-da-fanout7/` **does not exist**; the three named directories (`fanout3/work`,
`fanout2/fanout7`) are **byte-identical** to sha **`372C1D52…FA9077`**. That hash is the citation.

### A validator that quietly passes on nothing

**A `.kicad_dru` file without `(version 1)` is silently ignored by KiCad.** The verifier's first no-HDI
gate "passed" at baseline because the rule file was never loaded — a clean result produced by a rule
set that did not exist. Any custom-rule measurement in this programme must assert that the rule file
was actually read before trusting its output.

### ESC unconnected is worse after compaction, and was under-reported

`kicad-cli` returns **exactly 499 on both** ESC boards — that is its structural cap, so the number is
identical on two different boards and means nothing on either. `pcbnew` gives:

| board | unconnected |
|---|---|
| original | **1,542** |
| **compacted** | **1,620** (+78, never reported) |

So compaction made connectivity **worse by 78 connections**, and `esc-placement` did not report it.
drone-arm's **0** and Code-SDR's **112** both sit below the cap and are sound.

### The power-path clearance was computed on a false premise

`esc-placement` cleared the power path using **four-layer-parallel** copper at 3.3–5.1 mm. **The inner
layers are 1.5 oz, not 4 oz** — 37.28 mm each would be required. The real requirement reproduces
exactly: **13.981 mm total, 6.991 mm per outer face**, against **1.50–3.50 mm measured.** So the
clearance claim was invalid, not merely optimistic.

### drone-mech: ZERO GENUINE INTERFERENCE ACHIEVED

After the executed station change: **2 pairs / 4.010114 mm³, of which 0 are genuine.**

The verifier reproduced everything to **1e-9**, including the artefact: a **Ø2 × 38 mm rod**, **6.000 mm
from its own servo**, **0.000000 mm³ of actual contact**, **0.831215 mm³** of horn clip. So the
residual is a **representative-geometry artefact**, not a physical clash.

| | pairs | volume |
|---|---|---|
| before any fix | 34 | 334,227.9062 mm³ |
| after motor + cove | 8 | 1,255.303466 mm³ (6 genuine + 2 artefact) |
| **after station change** | **2** | **4.010114 mm³ — 0 genuine** |

### A counting slip in the package report

`fab-da-package7/REPORT.md:166` lists `0.300 × 33` and sums to **359**, not 360 — **the omitted hole
is the blind one.** The census total 360 drills + 4 G85 slots = 364 hits is otherwise sound.

---

### The span census, done properly — and a better artefact exists

The verifier built its own classifier (`GetViaType` + top/bottom layer; drill never used to classify)
and ran it on every artefact:

| artefact | **non-through (by type)** | split | diameter-gate said |
|---|---|---|---|
| repo original | **36** | 26 micro + 10 blind | 33 |
| composed | **24** | 18 micro + 6 blind | 23 |
| fanout5 | **18** | 13 micro + 5 blind | 17 |
| **the best (hash `372C1D52…FA9077`)** | **15** | **11 BLIND + 4 BURIED** ← BOARD CORRECTION | 14 |

**The old diameter gate under-reported by 3, 1, 1 and 1 respectively.** It cannot see a blind via of
legal diameter, which is the whole reason the classification had to move to span.

**A `fanout7` artefact exists with 15 non-through vias** — better than the `fanout5` I reported. Three
of its vias are declared MICROVIA but span two dielectrics; by type that is 14 micro + 1 blind, by span
11 + 4. **Either reading is HDI.** Its 0.300 mm blind is In2→B — that still needs sequential
lamination.

### The drill package is STALE and nobody re-exported it

The packaged drill set carries **24 holes in 5 of 7 files** (23×0.100 + 1×0.300). That matches the
**composed** board, not `fanout7`. So the package is **9 holes worse than the best board** and no
re-export exists. It must be rebuilt from `fanout7` before it means anything.

Also: **4 of the 336 PTH hits are G85 slots, not drills** — a package validator that counts holes
without distinguishing slots is over-counting.

### ESC unconnected is 1,542, and that is now reconciled

**`kicad-cli` reports 499 because it has a hard cap; `pcbnew` ratsnest gives 1,542 and that is the
real figure.** drone-arm, by contrast, is genuinely **0** — both tools agree there, below the cap,
so the zero is trustworthy. A zero below a tool's cap is evidence; a 499 exactly at a cap is a
truncation artefact. That distinction should have been caught the first time I quoted 499.

### Interference is down to 8 pairs / 1,255.3034 mm³

After the motor-envelope fix plus an executed cove adjustment: **8 pairs / 1,255.3034 mm³**.

| view | pairs | volume |
|---|---|---|
| as-built | 34 | 334,227.9062 mm³ (942.478 of stub artefact inside) |
| after motor fix | 26 | 332,674.0818 mm³ |
| **after motor fix + cove** | **8** | **1,255.3034 mm³** |

The 26-pair figure the board carried is **exact arithmetic but a subset** of the real pair set. Every
pair/volume sum reproduces to 1e-7.

### The 110 pads are mapped, and they are not all in three packages

Pad numbers are recorded and the mapping is **sound: 41 / 9 / 11**. That means the 110 fall into
three groups at those sizes — so **replacing the three fine-pitch packages does not automatically
clear all 110**, which is exactly the question Option B was waiting on. The 371 pad gaps also
reproduce (75 + 6×43 + 2×19) at pad-pair granularity, though one extra 0.2000 mm gap is not pad-to-pad.

### Something a previous unit got wrong about the tooling

`fanout2` claimed **"KiCad cannot express span"** and reported zero. That is false — `A.Via_Type`
works, and its zero was a microvia **type relabel**, not a capability limit. Any count derived from
that claim is void.

---

### OUR OWN GATE WAS WRONG — HDI must be counted by SPAN, not diameter

A verifier parsed the drill package itself and found the no-HDI gate has been under-reporting since
it was written.

**The gate flags a via when its drill is below 0.2 mm.** That cannot see a **blind or buried via of
legal diameter** — and a 0.300 mm blind via still needs **sequential lamination**, which is HDI
process regardless of how big the hole is.

| quantity | gate said | **true** |
|---|---|---|
| non-through holes in the drone-arm drill package | 23 | **24** (23 × 0.100 **+ 1 × 0.300**) |
| non-through vias in `fanout5` | 17 | **18** (17 microvia **+ 1 blind**) |

**Correct classification is by SPAN** — through / blind / buried / micro — not by drill size. Every
HDI count in this programme before this correction is therefore a floor, not a measurement. The
wave-4 unit ships a reusable span-based classifier so it cannot regress.

### drone-mech is worse than the previous line said

The baseline arithmetic is exact and verified to 1e-6 by six independent booleans
(200,132.018404 + 124,344.412738 + 6,242.972920 + 314.159266 = 331,033.5633). But the sequence does
not end at zero:

| step | pairs | volume |
|---|---|---|
| baseline | 22 | 331,033.5633 mm³ |
| delete 4, keep R3 | 2 | 1,248.5946 mm³ |
| + resize envelope to Ø36 × 70 | 0 motor pairs | — |
| **+ 2 ELEVON pairs that survive** | **2** | **593.069028 mm³** |
| **final airframe total** | **26** | **332,674.0818 mm³** |

So resizing clears the motor envelope but **two elevon pairs remain**, and the airframe total is
**26 pairs / 332,674.0818 mm³**. My earlier "delete 4 → 0" was wrong twice over: the station choice
matters, and the elevons were never in that count.

A residual **628.32 mm³** of the same pilot-stub artefact was also found sitting inside the set that
had been classified as *genuine* clash.

### Envelope sourcing, stated at the right tier

Ø36 × 70 is **SOURCED AT LISTING/SPEC TIER ONLY** (`spec:302`). The repo records **no motor
dimension** at all. It is not drawing-tier and is not claimed as such. The board's **71,251.29 mm³**
is **can only**; with the shaft it is **71,585.116 mm³**.

### drone-arm has no ESC command path, and it is not just six nets

No J60–J66, and **U10 pads 43–48 sit on auto-generated nets — there are 64 such auto nets on the
board.** So the "six missing PWM nets" description understates it: the pads are not merely
disconnected, they are attached to nets that KiCad generated rather than nets the design defined.

### A board line was violated by the wave it describes

The fan-out executed **5 via-only moves** against a board line that says the remaining groups are
"not a via edit". That is a real objection and it is recorded rather than smoothed: those 5 *were*
via-only, which is precisely why 15 groups remain — they are the ones that are not.

---

### Wave 3 results — real progress, and two of my own claims qualified

#### drone-arm fan-out: 5 of 20 groups executed, 17 HDI violations remain (was 23)

Artefact `evidence/fab-da-fanout/da_main_rev_b_fanout5.kicad_pcb`, sha `E65F0B2E…A5843A`.

| question | answer |
|---|---|
| groups / vias / nets | **20 / 24 / 13**, and the "9 of 20 with the via centre inside another net's copper" reproduces **exactly** |
| can a 0.6/0.3 through via stand at the microvia's own XY? | **At 0 of 20.** Placing one there produces **188 DRC errors** (113 clearance, 52 shorting, 17 hole, 6 mask) |
| what was EXECUTED | **5 of 20 groups** — F19 0.028 mm, F18 0.100, F07 0.072, F03 0.263, F20 0.260. A **via nudge, not a re-route**: 6 microvias became 5 standard through vias plus 2 escape segments |
| DRC, own rules | 0 → **5**, all `via_diameter` (0.4 mm pad against the project's 0.6 mm floor). With that single rule relaxed to 0.40: **0** |
| DRC, no-HDI gate | **23 → 17** — all `microvia_drill_out_of_range` |
| unconnected | **0 → 0** |

So the last blocker on drone-arm is **17 HDI vias**, down from 23. The remaining 15 groups each need
copper moved before any via fits, because the microvia centre is inside foreign copper.

#### drone-mech: my "delete 4 → 0 pairs" was incomplete

Artefact work in `evidence/fab-dm-envelopes/`. The baseline reproduces **22 pairs / 331,033.5633 mm³**
to the last digit.

**The station choice is measured, not arbitrary.** Keeping one envelope per duct, the residue is:

| keep | pairs left |
|---|---|
| R1 | **8** |
| R2 | **6** |
| **R3** | **2** |

So: **delete R1 and R2, keep R3 on each duct.** But **deletion alone with the as-built Ø42 envelope
does not reach zero — it reaches 2 pairs / 1,248.5946 mm³.** The fix needs **both** steps:
**delete R1 and R2, and resize the kept envelope to Ø36 × 70 + Ø5 × 17 shaft.**

The earlier board line said deletion alone gives 0.0000 mm³. That was measured against a different
keep-set; with the measured best set it is **2 pairs / 1.25 cm³**, which is a 265× reduction but not
zero. Corrected here.

#### drone-arm FINAL package: built, 48/48 assertions, and honestly NOT sendable

`evidence/fab-da-package-final/` — 28 files, zip sha `9857E06B…5C81`, 383,887 bytes.

| | |
|---|---|
| assertions | **48 / 48 PASS**, on two independent from-scratch runs |
| Edge_Cuts | **140.000 × 100.000 mm** (140.150 with stroke = pcbnew bbox) |
| holes | **366** |
| `.pos` | **161 rows / 165 footprints** |
| gbrjob | **140.15 × 100.15 · 1.6 mm · ENIG · Rev B** |
| **sendable** | **NO — the drill set is HDI.** 7 Excellon files, of which 5 are blind/buried carrying **24 non-through holes, 23 at 0.100 mm** |

The package is correct, complete and revision-stamped. The board inside it is not yet
manufacturable. **A fab reading those drill files would refuse or mis-build the board**, which is
exactly why the sendability check exists separately from the assertion count.

### Orderable state, unchanged and honestly

| board | orderable | what blocks it |
|---|---|---|
| **Code-SDR V2** | **YES** (bare board) | MPNs for assembly; the fiducial gap disclosure |
| drone-arm main rev_b | **NO** | **17 HDI vias** (down from 23); package built but drill set is HDI |
| ESC rev_b | **NO** | A/B decision not answered; 2.88 % routed; 499-vs-1,542 unconnected unreconciled; 4 oz needs 0.200 mm holes at 0.30 mm minimum |
| drone-mech | **not yet** | interference 2 pairs / 1,248.5946 mm³ after the measured best deletion; needs the envelope resize too |

---

### 4 oz analysis — three corrections, one of them a new blocker

The capability answer stands: **no surveyed fab makes 0.200 mm at 4 oz.** Multi-CB and LeitOn were
re-fetched live and both are verbatim 140 µm rows (Multi-CB 0.300/0.300, special 0.250/0.250/0.200;
LeitOn 0.30 track / 0.40 space / 0.25 ring).

But the surrounding detail was wrong in four places:

| claim | correction |
|---|---|
| "five houses publish 4 oz" | **four.** Advanced Circuits was misread — its advanced column is 0.009″ = 0.229 mm and the N/A is a different column |
| "4 oz trace 0.250–0.400" | **0.400 is LeitOn's *space*, not its trace** |
| 215 PTH pads | **223** per our own JSON |
| **"there are 371 pad gaps"** | correct — but there is a **THIRD blocker that was never recorded** |

**THE NEW BLOCKER: minimum finished hole at 4 oz.** The 110 × 0.200 mm PTH pads were resting on
PCBWay's **generic** 0.15 mm CNC floor, which is not oz-indexed. **LeitOn publishes a minimum
finished hole of 0.30 mm at 140 µm.** So at 4 oz the ESC fails on **hole size as well as trace and
space** — and changing the three fine-pitch packages may not fix it, because the 110 offending pads
have not yet been mapped to their footprints. **That mapping is required before Option B can be
costed honestly.**

### The fiducial "PASS" was manufactured by moving a threshold

The assembly unit reported **"all fiducials OK"**, DRC unchanged 222 → 222. The verifier checked the
unit's own logs: **"all fiducials OK: False"**, because **FID1/FID2 pour gap is 1.22 mm against a
required 1.25 mm.**

The report quotes 1.22 correctly, then **swaps in a 1.00 mm threshold** and never discloses the
failure. That is a threshold moved to convert a FAIL into a PASS, which is the single most corrosive
thing that can happen in a checklist. **The fiducials are 9 placed, 0 new DRC violations, and one
2 mm-scale gap short of the assembly house's requirement — likely a 0.02 mm raster artefact, but
undisclosed either way and therefore not yet acceptable.**

### Unconnected count has two values and nobody reconciled them

`kicad-cli` reports **499** unconnected on the ESC. `pcbnew` ratsnest reports **1,542**. Those cannot
both be right, and the difference is large enough to change how much routing work remains. It needs
resolving before any routing budget is trusted.

### What the verifier confirmed independently

- **The composed drone-arm board does carry both fixes in ONE file** — its own DRC on
  `5DBAE238…6F73B6`: **0 own-rule violations, 0 unconnected, 23 `microvia_drill_out_of_range`**,
  338 vias, 2,301 segments, 24 non-through. Its own void instrument reads **1.2959 / 0.6013 %**
  against a base of **9.8338 %**, and `fixed.kicad_pcb` still reads 9.8338 — so the composition is
  real. Caveat restated: "via-fixed" means **12 of 36**; 23 microvias remain.
- Impedance matches the stackup: 0.2300 mm → **49.5002 Ω**, band 48.56–49.92 (mask Dk ASSUMED),
  USB 90 Ω withdrawn, 593 = 580 F.Cu + 13 B.Cu.
- The ESC split reconciles: 523 = 414 + 70 + 16 + 16 + 4 + 3; 371 pad gaps all exactly 0.2000 mm,
  all intra-footprint (75 + 6×43 + 2×19).
- **No spend, HDI or copper-weight violation.** $0 spent, ESC 0.14 mm, others 0.035 mm.

---

### 4 oz at 0.200 mm — SETTLED: not available anywhere (8 fabs surveyed)

The wave-1 claim rested on **Eurocircuits' 3 oz row**. It has now been asked properly, against
published vendor capability tables only, with quotes stored verbatim.

| fabricator | 4 oz stated? | min trace @ 4 oz | min space @ 4 oz | min ring |
|---|---|---|---|---|
| PCBWay | **explicit** | 0.330 | 0.330 | 0.150 (generic) |
| Multi-CB (DE) | **explicit 140 µm** | 0.300 std / **0.250 special** | 0.300 / 0.250 | 0.300 / 0.200 |
| Bay Area Circuits | **explicit** | 0.305 std / 0.279 adv | 0.305 / 0.305 | 0.127 (generic) |
| LeitOn (DE) | **explicit 140 µm** | 0.300 | **0.400** | 0.250 |
| Advanced Circuits | no — stops at 3 oz | 3 oz: 0.229 | — | — |
| JLCPCB | no — heavy weights are **2-layer only** | 4-layer max 2 oz | — | — |
| Eurocircuits | no — ends at **3 oz** | 3 oz: 0.250 | 0.250 | 0.125 |
| OSH Park | no — heaviest service is 2 oz | — | — | — |

**Answer: no. Categorically, from all eight, in every service tier.** The strongest form of the
evidence is not a missing row but rows that exist and stop above it: PCBWay publishes **13 mil**
at 4 oz; Multi-CB's 0.200 number belongs to the **105 µm (3 oz)** row; LeitOn needs **twice** the
ESC's space.

**Mechanism:** published 4 oz space / 140 µm copper = **1.8× (Multi-CB) to 2.9× (LeitOn)**. Etch
undercut scales with copper thickness, so the pattern floor tracks it almost linearly. The ESC wants
**0.200/140 µm = 1.43×** — below every published 4 oz figure, and below Eurocircuits' 1 oz absolute
of 0.125 mm.

### The ESC is now a clean binary, and both branches are costed

With the rules built both ways and DRC run on each:

| rule set | violations | what it means |
|---|---|---|
| 4 oz @ **0.250 mm** | **523** | **265 of 2,777 unrouted pads sit in pad rows where a 0.250 mm track physically cannot be connected at 0.250 mm clearance** → not a routing job |
| 4 oz @ **0.200 mm** | **102** (−421) | escapes fit with **0.05 mm to spare**; but this pattern class **no surveyed fab will make** |
| 4 oz @ 0.200 mm + 0.150 mm ring | **16**, all dangling vias | the entire remaining delta *is* the route |

Footprint-bound vs routing-fixable at the 0.250 set: **383 footprint-bound · 35 routing-fixable ·
105 parameter/dangling.** The earlier "43 copper gaps = routing" split was **wrong**.

So:

- **Option A — drop the ESC to 2 oz.** The geometry is *already* 2 oz-compliant (0.200 at 70 µm =
  2.9×, matching published 2 oz figures). **Zero work.** Cost: loses the current capacity 4 oz was
  chosen for.
- **Option B — keep 4 oz and change 3 packages**: U201 (QFN-80 P0.4), 6 × LQFP-48 P0.5, J202/J203
  (USB-C). Real work, keeps the capacity.

There is no third door. Both rule files exist in `evidence/fab-esc-rules-first/`, so whichever is
chosen drops in without rework.

### drone-arm: ONE board now carries both fixes

`evidence/fab-da-consolidate/da_main_rev_b_composed.kicad_pcb`, sha256 `5DBAE238…6F73B6`.

| | |
|---|---|
| DRC, board's own rules | **0 violations, 0 unconnected** |
| DRC, no-HDI gate | **23 violations**, all `microvia_drill_out_of_range`, **0 unconnected** |
| minimum drill | **0.100 mm — still HDI.** 23 microvias + 1 blind remain |
| via census | 338 vias: 0.100×23, 0.300×34, 0.350×281; non-through 24 |
| **void under the RF corridor** | **1.2959 %** (was **9.834 %**) — a **7.6× reduction** |
| remains | **24 non-through vias in 20 groups, 13 nets — all 20 need a fan-out re-escape**; 9 of the 20 (not 13) have the via centre inside another net's copper |
| new conflict | none. RF void fraction is **bit-identical** to the void-fixed board, so composition costs nothing on the metric it exists for |

### Code-SDR: orderable, and now assemblable-ready

| gap | before | after |
|---|---|---|
| fiducials | **0** | **3 global + 6 local**, DRC **222 → 222** (unchanged) |
| test points | **0**, all 1,085 vias mask-tented | **18 probe sites** with coordinates |
| BOM | none existed | **373 rows, 129 lines, 0 missing values, 373 missing MPN** |
| impedance | `true` with no target | **targets stated; one of three was false, so the claim was revised** |
| IPC-D-356 | none | **1,289 pin + 1,213 via records** |

**MPNs are the remaining assembly gap** — 373 of 373 rows lack a manufacturer part number, which
is a sourcing task, not an engineering one.

---

## FAB READINESS — where the three boards actually stand

**Measured, not asserted.** Definition used throughout: **ORDERABLE = a bare-board order placed
today, from artefacts that exist today, would produce the board the design describes, with nothing
to fix afterwards.** A board that etches but cannot function is **not** orderable, because the rework
is the thing this programme exists to avoid.

| board | PASS | FAIL | WAIVED | **ORDERABLE** |
|---|---|---|---|---|
| **Code-SDR V2** | 12 | 0 | 1 | **YES** |
| drone-arm main rev_b | 7 | 6 | 0 | **NO** |
| ESC rev_b | 6 | 7 | 0 | **NO** |

### The six true blockers, by cost-to-fix-after-fab

| # | board | blocker | fix class | measured size |
|---|---|---|---|---|
| 1 | DA | **36 non-through vias, 33 at 0.100 mm** — no non-HDI 4-layer house can drill or plate them | **MOVE** | 12 fixed already. **24 remain in 20 groups, and 9 of those have the via centre inside another net's copper (dist ≤ 0)**  ← BOARD CORRECTION: an earlier version of this line said 13; the measured figure is **9**, — no via of any size fits. Needs a fan-out re-escape. |
| 2 | DA | **no ESC command path in copper** — J60–J65 absent, U10 pads 43–48 unconnected | **MOVE** | **0 of 7 candidate pads has a legal escape**: U10 is 0.4 mm pitch with 0.200 mm pad gaps and a 0.20 mm track needs 0.45 mm. Six connectors, six nets, one fan-out. |
| 3 | DA | **only the rev_a package exists**, title block has no revision | **PARAM — READY** | Install the verified rev_b package (21 files, 369 holes, 140.000 × 100.000, no frame) + `git apply title_block_rev_B.patch`. No design work. |
| 4 | ESC | **499 unconnected items; 540 of 556 nets carry no copper** | **MOVE** | 154 segments totalling 628.27 mm; 16 nets routed = **2.88 %**; 1,978 of 1,990 vias sit on nets with no track. Finish the route. |
| 5 | ESC | **523 violations at 4 oz, 371 of them 0.200 mm pad gaps inside 9 footprints** | **OWNER DECISION** | Not routable away: U201 QFN-80 P0.4, 6 × LQFP-48 P0.5, J202/J203 USB-C. At 140 µm the pattern floor is 0.25 mm; **these pads cannot be made compliant by any edit.** |
| 6 | ESC | **no package and no revision marking at all** | **PARAM** | One export once #4 exists; add a title-block revision first. |

### The one decision that is genuinely yours

Blocker 5 has no engineering answer. Three options:

1. **The fab accepts 0.200 mm at 4 oz in writing.** This is fab burden, which the owner principle
   says is the acceptable kind of spend. Cheapest if a house will sign it.
2. **Drop the ESC to 2 oz.** The geometry is *already* 2 oz-compliant, so this is the zero-work
   option — but it contradicts "ESC is the only 4 oz board", and 4 oz was chosen for current
   capacity on a 60 A-per-phase ESC.
3. **Change 3 packages.** The honest engineering fix, and the most work.

**The 4 oz rules must be adopted BEFORE the route is finished.** 97.1 % of it does not exist yet, so
it is free now and a 540-net rip-up later.

### What is deliberately NOT a blocker

Every DRC warning on Code-SDR (222, **all severity warning, zero errors** — fab houses do not read
them), the 84-net signal pilot on In1/In2 (an SI debt, not a process limit), and the clock constraint
fix (a 2-hunk LPF patch, no copper).

### Code-SDR's real remaining gaps are assembly-side

0 fiducials, 0 test points, no BOM, no assembly drawing, no IPC-D-356, and a job file marked
`ImpedanceControlled: true` with **no impedance target stated**. Those stop an **assembly PO**, not
the etch order — which is why the board still reads ORDERABLE for bare fabrication.

### drone-mech interference — resolved, and my diagnosis was wrong

The 22 pairs / **331,033.5633 mm³** reproduces **to the last digit**. Breakdown:

| | |
|---|---|
| duplicated placement | **0 pairs** — my "two parts at the same angular position" hypothesis was **wrong** |
| press-fit wrongly counted | **0 pairs** |
| genuine design clash | **20 pairs / 330,719.4040 mm³** |
| modelling artefact (pilot stub) | **2 pairs / 314.1593 mm³** |
| envelope as built | Ø42.000 × 72.000 + Ø5 × 8 stub = **99,908.93 mm³** |
| envelope it should be | **Ø36.000 × 70.000 + Ø5 × 17 shaft = 71,251.29 mm³** |
| **minimum fix** | **delete 4 of the 6 envelopes, keep one per duct → 0 pairs / 0.0000 mm³** |
| does the 42_6 Boolean repair change the count | **NO** — measured |

So the airframe has **six motor envelopes where two are needed**, and the envelope is **40.2 % too
large in volume** for the 110 mm duct module that has to hold it. Deleting four clears it entirely.

---

## HARD CONSTRAINTS — owner, 2026-11-15 (these override the "fab burden is free" steer)

1. **NO HDI ON ANY BOARD. No 0.1 mm microvias, no laser-drilled vias, no blind or buried via
   process.** Every board is 4-layer, so every via must be a **standard plated through via** in the
   normal mechanical drill range (0.2–0.3 mm typical). This overrides any earlier note that HDI burden was acceptable.

   **Corrected attribution (2026-11-15):** Code-SDR V2 has **ZERO** microvias — all 1085 of its vias
   are standard plated-through at 0.200 / 0.250 / 0.400 mm, so Constraint 1 is already satisfied
   there and no work is needed. The **36 × 0.1 mm HDI vias are on drone-arm rev_b**, not Code-SDR.
   My earlier board note said Code-SDR and was wrong.
2. **Coupon / prototype spend cap: $60 total.** Not $283, not $310. Any test-coupon, panel or
   prototype order must come in **at or under $60**, including launches and shipping. If a coupon
   set cannot be built for $60, redesign it smaller rather than asking for more money.

Everything else from the earlier steer still stands: prefer part swaps and constraint edits over
copper changes, prefer copper moves over stackup changes, and do not avoid awkward panelisation or
tight tolerances to spare the fab house.

---

One board, one truth. If your work is not on this board, it does not exist.

Pattern source: **@azizbuildss, "WIN HACKATHONS ON EASY MODE"** (Instagram `DfOLEP6v3AR`,
1 Nov 2026, 61 s). On-screen overlays: *split the folders · pin one board · tag the teammate*.

**Correction to an earlier reading of mine.** I first inferred the mechanism from those three
overlay words alone and wrote it up as a plan/execute/validate/hotfix pipeline. That was wrong.
The caption is comment-bait — *"comment HACK and i'll send you the agent board script"* — and
describes no workflow at all. The real method is legible only in the **screen recordings**:

- `tools/board` with `post / read / unread / wait` — a board CLI agents poll
- `AGENTS.md` wiring Claude Code hooks into that board
- an `orchestrator/src/store.ts` `StateStore` exporting **`claimTask` · `renewLease` ·
  `completeTask` · `setAgentTarget` · `createEscalation` · `appendAudit`** plus
  **`heartbeat` / `reapExpired`**
- a four-column **ownership table**: stream · owner · path scope
- handoffs tagged `[Aziz's Firstmate worker]`, `[Diego's Claude Code]`, `[Aziz's Codex]`
- PRs marked **"Ready PR only, no merge."** and a re-review answered *"5 min later"*

So the mechanism is **task-claiming with leases, heartbeats and escalation** — work distribution
plus liveness. That is not the same thing as plan/validate/hotfix stages, and my earlier write-up
conflated them.

Implemented here as `tools/board.py` (claim · renew · heartbeat · complete · escalate · target ·
reap · post/read · audit), with lease expiry so a crashed worker cannot block a task and scope
collision so two workers cannot duplicate one. Smoke-tested: double-claim refused, scope collision
refused, expired lease reaped and re-claimable, audit trail written.

The pipeline discipline (plan → execute → validate → hotfix) is still used, but as **our** working
method on top of the board, not as a description of the reel.

---

## Stage

| stage | state |
|---|---|
| PLAN | done — 2 waves decomposed, 22 units |
| EXECUTE wave 1 (11 units, PCB EM/impedance/fab) | **DONE** — committed `ef9688a` |
| VALIDATE wave 1 | **DONE** — verifier: `MOSTLY_SOUND`, 8 of 11 units rejected |
| HOTFIX wave 1 (6 units) | **DONE** — 6/6 repaired, committed `835e63a` |
| EXECUTE wave 2 (10 units, rectification + 3D) | **DONE** — 10/10 |
| VALIDATE wave 2 | **DONE** — `MOSTLY_SOUND`, 6 items rejected |
| HOTFIX wave 2 | **needed** — see the reject table below |

### Wave 2 — verified results

| item | result | ready to apply |
|---|---|---|
| da-voidfill | 20 voids, 4.1701 mm², 9.834 % reduced to **1.307 %** by moving 13 In1 segments | **no** — B.Cu reroute UNVERIFIED; the 1.307 % refill is a copy with 13 nets deleted, not a fabbable board |
| da-connectors | J60–J66 1x03 at y=79.50, x=80.00 to 95.24, pitch 2.54; 6 missing_footprint becomes 0 | **no** — 0 free lanes at pads 43–49 |
| da-can | 6 tokens `interfaces.kicad_sch:1286-1329`; net_conflict 20 to **17**, parity 191 to **188**, ERC 1 to **0** | **yes** |
| da-gerbers | 11 Gerbers + 5 blind/buried drills + 161-row `.pos`; Edge_Cuts **140.000 x 100.000 mm** | **yes** (rev still reads rev-question-mark) |
| cs-clock | `v2_top.lpf:16` D7 to D9 plus `build_diamond.tcl:99`; 55 items, 42.371 mm, 0 unconnected | **yes** — but NOT firmware-only |
| cs-varcap-real | 4 x **SMV1236-079LF**, k **1.293:1** against 1.169 needed; corner 44.63–51.05 MHz | model-only, no VNA |
| dm-step | **923.371 s to 218.003 s = 4.24x**, 205/205 records, digest `99301ffc3fd3…` identical | **yes** |
| aero-turbo | turbo 70.751 to **28.439 s (2.49x)**; batch 232.678 to **61.727 s (3.77x)** | **yes** |
| da-tdr | 20 coupons, 35 SMA launches | **no** — panel 140x200 vs 205; W1 110x8 |
| rp-stl | 51 files, 535,362,331 B, 47 hashes, 4 duplicate pairs | audit only |

**The 3D speedup is real and larger than first reported: drone-mech 4.24x (repeat 4.17x) with an
identical canonical digest over 205 paths, and aero 2.49x on the turbo path / 3.77x on the batch
path with sha-equal meshes.** The earlier 1.35x figure was cold end-to-end on a contended host and
is superseded.

### Wave-2 verification rejects (hotfix needed)

| unit | defect |
|---|---|
| da-tdr | 35 launches sum to **$283**, not $310; a 95 mm strip for 10 coupons at 10 mm pitch needs at least 98; W1 has no 100 mm slot; two-way resolution is 3.37 mm, not 2.9 |
| da-can | "191 = 161+20" is wrong, it is **161+20+6+4**; the 181 and 178 sums are also wrong |
| da-voidfill | cites `12_measure.json` which **does not exist**; the "measured" 1.307 % is a deleted-net refill, not a fabbable board; B.Cu is claimed to have room but is 12,728.8 of 14,036 mm2 already filled |
| da-connectors | the placement needs a lane that does not exist at pads 43 to 49 |
| cs-varcap-real | "it is the design" is validated only against the repo's own LC CSV — a model, not a measurement |
| rp-stl | 510.56 **MiB** = 535.36 MB, not MB |
| da-gerbers | report says er **4.5**; board lines `:58/:69/:80` say **4.2** — the report is wrong, the board line above stands |

### Hotfix wave 1 — outcome

All six rejections repaired, each keeping the original visible and striking the superseded
numbers rather than restating them.

| unit | was | corrected |
|---|---|---|
| cs-em-field | "47–50 Ω" band | **WITHDRAWN**; band **48.56–49.92 Ω** at er 3.0–4.5, numerical 49.28–49.54, central 49.43 unchanged |
| da-match-design | "−15.7 dB over 0.10–0.58 mm", "−24.5 dB all voids" | 0.100 mm row now computed (−19.60 dB @ 32.7 Ω); cascaded **−25.1 dB** with real fills; **−11.5 … −32.3 dB** if the 11.14 % is forced onto that path |
| da-match-design | "entire plausible void range" | **scope wrong** — the void is on CC_PA / CC_LNA_N / CC_LNA_P / GNSS_RF_IN, **not** on the matching path |
| dm-3d-speed | ±117.5 mm³, 45.3× | 117.5 is **2σ** (σ 58.75); 45.3× withdrawn, **1.35× cold** |
| da-stackup | 51.2 Ω, 0.365 mm, "independent" | **51.3 Ω**, **0.366 mm**, word *independent* dropped — it was one model twice |
| cs-varcap | SMV1231-1245 on a 2.426 GHz trim | relabelled **BRIEF-SUPPLIED**; item now states P3 **exceeds** the part ceiling by 1.223× |
| fab-readiness | "sums to 1.60"; "impedance never solved" | mask layers excluded from body thickness, both boards re-evaluated alike; impedance **was** solved, what is missing is a **measurement** |

---

## Folder split — nobody writes outside their own row

| owner | directory | scope |
|---|---|---|
| da-em-field | `evidence/da-em-field/` | 915 MHz field solve, void sweep |
| da-match-design | `evidence/da-match-design/` | matching network |
| da-stackup | `evidence/da-stackup/` | stackup + plane reassignment |
| cs-em-field | `evidence/cs-em-field/` | Code-SDR field solve |
| cs-varcap | `evidence/cs-varcap/` | varactor feasibility |
| cs-match | `evidence/cs-match/` | per-band matching |
| da-sw-parity | `evidence/da-sw-parity/` | pin map vs firmware |
| cs-sw-parity | `evidence/cs-sw-parity/` | pin map vs RTL |
| fab-readiness | `evidence/fab-readiness/` | pre-fab checklist |
| dm-3d-speed | `evidence/dm-3d-speed/` | drone-mech 3D pipeline |
| aero-3d-speed | `evidence/aero-3d-speed/` | aero mesh pipeline |
| w2-* (11) | `evidence/w2-*/` | wave 2 rectification |
| hf-* (6) | `evidence/hf-*/` | hotfix of wave-1 rejects |

**Never write:** another row's directory, any repo working tree, any `audit/*` branch.

---

## What is true right now (verified)

### PCBs
| question | answer |
|---|---|
| EM-validated? | **YES both**, tier B — 2D finite-difference quasi-static Laplace, ±2.6 % grid |
| drone-arm Z0 | **52.6 Ω** over solid In1 pour; **65–118 Ω** over void |
| Code-SDR Z0 | **49.4 Ω** at 0.23 mm; S11 −44.5 dB ≥500 MHz |
| Impedance matched? | **Code-SDR yes · drone-arm NO** (as built S11 −1.35 dB at 915 MHz) |
| Varactor covers regime? | **NO** — 10,000:1 needed, 4.74:1 ceiling at 15 V; only IF2 trim viable (1.169:1) |
| Rip-up needed? | **drone-arm YES** · Code-SDR firmware-only, conditional on D9 = CLKI |

### The finding that re-framed the drone-arm RF defect
Not "a power plane is the reference". It is the **11.14 % of voids**. Solid pour gives 52.6 Ω and
S11 −32 dB; a void forces the return 1.275 mm down to In2 and Z0 jumps to 65–118 Ω. **Fill the
voids** — that is a zone-fill change, not a stackup re-spin. The In1 distance sweep
(0.18–0.22 mm → 48.08–54.10 Ω) shows the stackup thicknesses were already fine.

### 3D corpus
471 files / 1.86 GB. **drone-mech is 247 files / 1.31 GB** (191 STEP + 14 brep) — 70 % of all bytes.
research-paper 51 files / 510 MB (36 STL + 15 STP), never audited. copperline 120 `.obj` ≈ 170 KB
each, almost certainly test fixtures.

Speed achieved so far: drone-mech **1.35× cold / ~30× warm** (the 45.3× first reported was
warm-cache only and is withdrawn) · aero **1.73×**, mesh sha-identical.

### Top 5 blocking fab

1. **drone-arm ships only rev_a gerbers.** A valid rev_b package now regenerates (Edge_Cuts
   140.000 x 100.000 mm) but the rev field still reads unresolved. Category: **RE-SPIN.**
2. **drone-arm In1 is 3V3 and the void fill is not yet fabbable.** The fix is moving 13 In1
   segments, not a zone tweak (zone parameters alone only reach 8.97 % void). The 1.307 % result
   comes from a copy with 13 nets deleted, and the B.Cu reroute is unverified. Category: **RIP-UP.**
3. **drone-arm J60–J66 has no lane at pads 43–49** and the servo rail protection is undersized —
   a 0.75 A PTC against a 3–9 A requirement. That is a safety item, not a nicety.
4. **Code-SDR clock is a two-line fix, not firmware-only**: `v2_top.lpf:16` D7 to D9 plus
   `build_diamond.tcl:99`. Open question: is D9 clock-capable on this part. Also 36 HDI 0.1 mm vias
   and 84 nets routed on a solid In1 plane.
5. **No impedance sign-off on either board.** Two 2D FD solves exist; a measurement does not.
   The TDR coupon design is not yet buildable (panel 140x200 vs 205, W1 110x8, $283 vs $310).

### Decisions — resolved

| # | decision | resolution |
|---|---|---|
| 1 | void fill vs In1 re-spin | **void fill**, but see the buildability report: the 1.307 % result came from a copy with 13 nets deleted. Minimum move set is being measured. |
| 2 | is D9 clock-capable | **YES, confirmed.** D9 = `PB16A` = **`PCLKT2_0`**, a dedicated primary-clock pad in bank 2 (Lattice CrossLink datasheet FPGA-DS-02007-2.2, p.51, which the repo itself cites). Not merely clock-capable — a dedicated clock pad. **No copper change, no respin.** |
| 3 | servo rail PTC | **Re-pointed and it is a COPPER fix.** The 0.75 A PTC is **F701 on the ESC rev_b board** (`REV_B_BOM.csv:57`), not the flight-control board. No PTC at 3–9 A exists in that footprint, so it is not a BOM swap. The fix is deleting **six pad-to-net connections**, not rebuilding the board. |
| 4 | 36 HDI vias | **Not on Code-SDR at all** — that board has zero microvias. The 36 are on **drone-arm rev_b**. Conversion plan required there. |
| 5 | coupon spend | **$54.24, inside the $60 cap** with $5.76 headroom. 2 coupons on one 100×100 mm panel, **2 SMA launches total**, 5 boards ordered (6 coupons each: 3 × CA + 3 × CB). |
| 6 | research-paper 2-vs-5 arrays | pending the rp-stl hotfix |

### The coupon that was designed — and why it is worth the money

The single uncertainty worth paying to measure: **Z0 of the as-built cross-section where In1 is
absent, with the 0.25 mm-gap stitched F.Cu coplanar pour either present (74.5 Ω) or inert (118.1 Ω).**
Those two models are **43.6 Ω apart**, and which is true decides whether the coplanar pour is
carrying the reference or doing nothing.

| coupon | predicted | purpose |
|---|---|---|
| CA | **74.53 Ω** (pour present) vs **118.12 Ω** (pour inert) | the measurement that resolves it |
| CB | **50.19 Ω** | control — same line with In1 solid |

That is a properly designed experiment: one coupon for the unknown, one control, and a refutation
criterion. It fits the budget because it drops from 35 SMA launches to 2.

---

## Wave-1 validation rejects (being hotfixed)

| unit | defect |
|---|---|
| cs-em-field | "47–50 Ω" band; no artifact yields 47, real floor 48.56 |
| da-match-design | 0.10 mm row absent from its own tables; 87 Ω excludes the 118 Ω void; uniform-h_eff contradicted by the FD result |
| dm-3d-speed | ±117.5 mm³ is 2σ (σ = 58.75); 45.3× was warm-cache only |
| da-stackup | 51.2 vs 52.6 Ω unreconciled; "independent" HJ is the same model twice |
| cs-varcap | SMV1231-1245 (~2 GHz) assigned to a 2.426 GHz trim |
| fab-readiness | stackup sum double-counts two 0.010 mm masks; "impedance never solved" contradicts two FD solves |

---

## Rules for any agent reading this

1. **Read this board before doing anything.** Do not re-derive a number that is already on it.
2. **Write only in your folder.** If you need another owner's output, read it; do not edit it.
3. **Every number carries a method.** Tier A field solve / Tier B 2D FD / Tier C closed form.
   Calling a Tier C number "EM-validated" is misrepresentation.
4. **Do not contradict this board silently.** If you find a number here is wrong, write
   `BOARD CORRECTION:` in your report and say which line. Do not restate it as a new finding.
5. **UNVERIFIED is a valid, rewarded answer.** Inventing a plausible number is the worst outcome.
6. **Nothing in a repo.** No commit, no push, no `audit/*` branch, ever.

---

## Corrections this board already carries

This program has overturned four of its own claims. They stay visible:

| was | is |
|---|---|
| "0.00 % over GND, so the power plane is the defect" | the **voids** are the defect; solid 3V3 is a fine reference at 52.6 Ω |
| drone-arm stackup "undefined" | **fully defined** — F.Cu 0.035 / prepreg 0.200 er 4.2 / In1 / core 1.040 / In2 / prepreg 0.200 / B.Cu |
| "0.35 mm is not 50 Ω" | **it is** — 48.61 / 53.98 / 51.23 Ω by three closed forms |
| drone-mech 3D speedup 45.3× | **1.35× cold**, ~30× warm |
| research-paper arm "9.9 % unique" | **6.08 %** distinct (35/576); 9.9 % was a Pairs-IoU column |

---

*Maintained by dsh-lead. Last updated when the hotfix and wave-2 runs report.*

---

### esc-routability — is the compacted placement routable at 4 oz?

**`evidence/esc-routability/REPORT.md`.** Input `evidence/esc-placement/` **did not exist**, so every
"compacted vs original" delta is unmeasurable: the same file sits on both sides. Measured the CURRENT
placement and shipped the instruments to score the compacted one.

| question | answer |
|---|---|
| DRC 4 oz / 0.250 (9 rules) | **523** (414 clearance, 70 annular, 16 via_dia, 16 dangling, 4 track, 3 neck), 499 unconnected — reproduces |
| DRC 4 oz / 0.200 | **102** — reproduces |
| **normalised metric for a compacted placement** | **1.0621 vio/cm2 · 0.8407 clearance/cm2 · 18.83 per 100 unrouted pads** |
| pads with no legal 0.25 escape | **432 of 2,777** (15.6 %) at a 1.0 mm breakout, 389 at 0.6 mm |
| of those, irreducible (pad pitch) | **202** — U201 30, 6 x LQFP 27 each, J202 5, J203 5. **Invariant under placement.** |
| the other 230 | blocked by **movable copper**: 204 by six `M*_DRV_SCL` tracks sitting 0.337 mm off the WQFN pad rows |
| the board's "265" | **wrong as both methods.** Arithmetic across all footprints = 330; exact geometry = 432. 265 over-counts the fine-pitch cores (202) and under-counts the total. |
| power path required (60 A, one 0.14 mm layer) | 13.981 mm @ dT20 (1.957 mm2), 10.931 @ dT30, 8.018 @ dT50 |
| power path available | phase **7.50–7.51 mm**, BATP **1.763 mm**, BATN **0.394 mm** |
| one phase block | tile **88.367 x 82.130 = 72.576 cm2**; **40 of 81 nets routable** at 0.25/0.25, 41 not (all at <= 0.4 mm gaps) |
| 6 blocks = | **435.46 cm2** vs the board's 492.418 -> **56.96 cm2 (11.6 %) is inter-channel dead space** |

**Verdict: NOT routable to completion at 4 oz, and compaction is not the cause.** 383 of the 523
violations and all 202 irreducible pads are footprint-bound — no placement touches them. The power
shortfall is in the package (MOSFET pad copper 1.792 mm2 against 1.957 mm2 needed at dT20), not in the
corridors. Compaction must preserve **>= 7.5 mm** phase and **>= 1.76 mm** battery-tap corridors.

**No drawn route was delivered** — freerouting 2.5.0 crashes in `BoardSnapshotManager.getHash` after
self-reporting 346 violations on the 331 fixed vias. The per-net certificate replaces it.
Two method traps recorded: `GetBoundingBox()` includes text (**141 cm2** on this board), and a +-2 mm
maximin search window fabricates a 0.0 mm corridor where +-6 mm measures 7.51 mm.
