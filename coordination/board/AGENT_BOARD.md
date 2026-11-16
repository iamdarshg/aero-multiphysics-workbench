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

### drone-arm: 17 → 1. And a correction to the "no free site exists" claim

**The obstruction is a crowd, not an object.** At its own site each of the 17 vias faces **3–24 infringing
objects, median 13**, and **15 of 17 include an immovable pad.** Binding items: **14 track-bound** with
shortfalls **0.119–0.650 mm** (`/LNA_EN` −0.550, `/XIN` −0.500, `/SENS_SCLK` −0.512, `/ICM_nCS` −0.514,
`/SENS_MOSI` −0.450, `/1V1` −0.450, `/USB_DM_MCU` −0.326, `/RF_nCS` −0.150), **2 pad-bound**
(C12.2 `/GND` −0.282, **FB1.2 `/3V3_ADC` −0.650**), **1 via-bound** (`/RF_GPIO0`, 350 µm, −0.119).

**A true zero-deletion conversion is impossible — searched, not assumed:** over **504 candidates per via**
(21 radii × 24 directions + chord jog + A* corridor), **0 of 17 convert**, with a best miss of **0.031 mm**
against the **0.450 mm** lane a 0.20 mm track needs. So a per-via clearing is required.

**Batches, and the sweep is what worked:**

| clearing radius | kept / 17 | non-through left | unconnected |
|---|---|---|---|
| **R = 0.70 mm** | **15 / 17** | **2** | **30** |
| R = 1.30 mm | 16 / 17 | **1** | 36 |
| R = 1.60 mm | 16 / 17 | 1 | — |

**Final at R = 1.30: ONE non-through** (`In2→B`), DRC set diff **`+clearance 1, +track_dangling 51,
+via_dangling 3, −via_diameter 1`**, **unconnected 36 on both tools**, RF void **bit-identical
4.1699 mm² / 9.8338 %**, pads sha identical. Re-routing restored **242 verbatim + 18 detoured + 10 vias**;
**123 remain unresolved.** freerouting was attempted at `-mt 5` and **wrote no `.ses` in 20 minutes** — no
result was taken from it.

**`/RF_GPIO0` at (57.400, 56.100) is the last one, and it is convertible on its own** — a legal site sits
**0.177 mm** away — **but the other 16 vias' corridors block it.** It also carries the single clearance
error and the 0.100 mm drill.

**So 0/0 is not reachable by this route, but the state improved from 10/17 with 81 unconnected to
15/17 with 30.** That is real progress and still not a pass.

### ESC split: assembles — as a board respin, at 151.77 × 122.55 × 55.80 mm

**The three-column header does not fit where two did.** Real footprint: **3 × `TSW-120-15-G-D` +
3 × `SSW-120-01-G-D` = 18.27 × 51.81 mm = 946.6 mm²** (a triple-row part traps its middle row on a 2-layer
escape, so three 2-column parts are correct). On the current 138.35 mm board the free margin is **7.85 mm**,
so forcing it on **overlaps the sink by 11.92 mm (617.6 mm²)** and drills **Q3CL and Q6CL.**

**All four conventional fixes fail, with numbers:**

| option | why it fails |
|---|---|
| (a) shrink/move sink | sink is only **0.72 mm** from the last FET body; shrinking **13.42 mm uncovers 4 FETs → 521 °C** |
| (b) route around | largest free rectangle is **162 mm²** against **315.5 mm²** needed — **0 of 3 sites** |
| (c) notch the sink | uncovers Q3CL/Q6CL → **521 °C** |
| (d) columns along the long edge | **10.6 mm** of depth exists against **19.77 mm** needed |

**Chosen: (b′) the columns stay at the sink's end and the board grows 13.42 mm in x** — **zero thermal
cost, nothing moved**, plus the busbar lands trimmed to **x 130.50** (the old site drilled the BATN land).
**120 pins verified: 1.50 mm to the sink, 1.50 mm to edge, 0 violations.**

**Tj stays 123.2 °C and the Sil-Pad is still the limiter (45.6 K of 78.2 K). Height 55.80 mm.
Envelope 151.77 × 122.55 × 55.80 mm. ASSEMBLES: YES — but only as a board respin,** not on 138.35 mm —
and the two-column stack did not either.

### drone-mech: the knife edge is a **2.83° rim**, not a 0° sliver — and the fix costs 157.55 g

**A correction to the previous diagnosis:** the minimum convex material angle on the Ø85.2 bore rim is
**2.8334°** at (±56.959, ±40.581, −70.98), across **268 rim edges** (116 samples under 10°). Width at
50 µm is **2.47 µm**. **The "0°" was wrong** — zero is the analytic tangency at **r 40.7627**, which lies
**inside the bore and carries no material.** Breakout depth is **3.1315 mm** worst (the shipped loft dips to
39.4685), **not 1.806 mm.**

**Three of four options were refuted by measurement:** (b) BODY_HEIGHT 94.97 → **2 solids**,
**403.7881 g (+26.2 %)** and the land only covers z −70…+120. (a) boss → introduces a tangent junction and a
floating sleeve. (d) accepted → rejected, because **no process lays a 2.47 µm feather** and **381.6 cm² of
flank is simply missing.**

**(c) chosen and executed** — `rev2_fairing.step`, a per-duct smooth-max fairing on the section wire,
**F = 44.60 (achieved Ø89.2)**, gate z −112…130, 11-station loft kept:

| | result |
|---|---|
| solid count | **1 solid, 564 faces, valid, 0 free / 0 non-manifold** |
| volume | **308,099.0371 mm³** |
| mass | **477.5535 g — +157.5493 g** |
| walls | **1.0804 / 1.5060 / 1.5766 mm** |
| interference | **9,125.712739 vs stock 9,134.218881 — 0 rows added, 0 removed, 4 changed (all down)** |
| Ø82 seat | **untouched** — ring STEPs **byte-identical**, bore r 41.035 = **Ø82.070**, 4.00 mm land, ring↔duct **0.000000**, ring↔fuselage **0** |

**Knife edges are NOT fully gone:** the band rim is eliminated (lands **1.91 / 1.91 / 1.33 mm**), but a
**residual 5.1162° at z +172** remains — closing it needs re-stationing (**measured: 3 solids**) or a tail
fairing that would sit inside the ring seat.

**Interference basis needs reconciling:** this unit reports **9,125.712739 mm³** where the ring fix reported
**1,556.232076 mm³ / 6 pairs**. Those are different files or different p-air populations, and one of them is
not the airframe total.

---

### drone-arm: growth is DEAD on every edge — and it was never an edge problem

**The "grow the board" recommendation is refuted.** Edge distances from U10's pad copper:

| direction | distance |
|---|---|
| **north** | **44.65 mm** (pad-row centre line 45.05; northmost blocked via 44.10) |
| south | 44.65 mm |
| west | 53.65 mm |
| east | 75.65 mm |

**Growth moves an edge outward, so the clearance grows by exactly G** — 44.65 → **46.65 / 48.65 / 52.65 mm**.
And **it gains nothing:**

| growth | kept / attempted |
|---|---|
| base | **0 / 17** |
| +2 mm | **0 / 17** |
| +4 mm | **0 / 17** |
| +8 mm | **0 / 17** |
| +44.65 mm control (+44.65 % area) | **still 0 kept** |

Five vias do have a legal through position within ±2.5 mm, **but every escape stub is illegal** (best slack
**−0.1606 mm** against the **+0.225 mm** needed). Twelve have no legal position at all.

**The classification settles it: 14 track-bound, 2 pad-bound, 1 via-bound — ZERO EDGE-BOUND.** Minimum edge
clearance is **+43.10 mm** against a worst copper shortfall of **0.650 mm**. **The obstruction is 43 mm
inside the board; no outline change can ever reach it.**

So the earlier "grow 0.73–2.76 mm for $0" recommendation was measuring the wrong thing — it described a
**copper-free ring around U10**, not a board outline change. Growth of the outline is dead on all four
edges and should not be revisited.

**What still works:** clearing copper inside a disk gets non-through to **0** (radical rip-up, best at
10 mm) at the cost of **81 unconnected**. So the fix is **clear the ring, then re-route the 48 nets that
were cut** — real layout work, no shortcuts.

### drone-mech: rings REDESIGNED, interference 4,631.82 → **1,556.23 mm³**

**The literal that caused it:** `phase15_generate_geometry.py:980` —
`ring = annulus(48.0, 41.0, 250.0, 4.0, xcentre)`. **The ro/ri are bare literals and are INDEPENDENT of
`VANE_RING_RADIUS = 44.0`** (defined at :88, used only for the pivot at :435–436 and export at :807).
**So the fix is at :980, not the pivot radius.**

**Three options evaluated, and only one works:**

| option | result |
|---|---|
| (a) shrink ro ≤ 44 mm | ring↔ring clears, but **fuselage still 312.042804 mm³** — the burial is **ro − r_bore = 5.5 mm and is spacing-independent**, so clearing it needs **ro ≤ 42.6**, which puts the r=44 pivot **outside the part** |
| (b) move centres ≥ 97 mm | **at 100 mm still 13.670233 mm³**, and it re-lofts the whole body |
| **(c) PARTIAL ARC** | **0.000000 on both — supported and EXECUTED** |

**The seat, designed properly.** **The fuselage cannot seat it** — half-height ≈ **26 mm** against a
**41 mm** bore radius, leaving only the **2.8 mm web**. So the ring moves onto the **lip at z 239.80–243.80**,
with a **bore Ø82.070 = H7/f7 bonded clearance (0.036–0.091 mm)** — **not H7/p6**, because a press fit
gives **525 MPa hoop stress in the 2 mm CFRP wall.** Plus a **4.00 mm land** and a new **Ø84.0 × 1.20 mm
moulded bead** as an axial stop. **Seat overlap 0.000000; shoulder 251.732 mm²; bond 1,030.442 mm².**

**Executed:** **notch ±47°**, **two 2.4 mm blade slots**, and the bead. **3 solids, 5,624.2454 mm³ /
15.1855 g.**

**And a THIRD clash surfaced that no census had:** **the 30 × 40 mm vane plate crosses the entire wall —
56.004744 mm³ × 4 = 224.019 mm³**, which needed the blade slots.

**Result:**

| | before | **after** |
|---|---|---|
| pairs | **13** | **6** |
| volume | **4,631.820365 mm³** | **1,556.232076 mm³** |
| ring ↔ ring | 754.749861 mm³ clash | **0.000000 — designed clearance** |
| ring ↔ fuselage | 2,096.819452 mm³ clash | **0.000000 — designed clearance** |
| rows removed / added | — | **7 removed, 0 added** |

**Fuselage re-verified: 1 solid, 206,454.319709 mm³, 320.0042 g — CONFIRMED, not corrected**, so the
fab-ready geometry survives the redesign untouched.

**Knife edge, quantified:** the bore **breaks out 1.806 mm** (hull minimum radius **40.7627 mm**), and the
rim dihedral starts at 0° giving **3.49 µm at 50 µm out.** Fix is **≥ 1.2 mm of land, i.e. a Ø87.6 per-duct
fairing**, which would need **BODY_HEIGHT 94.97 mm.** **It does not interact with the ring fix, and it must
not touch the Ø82 bore.**

---

### drone-mech bearing rings: **GENUINE CLASH — a design defect, not a fit**

**The disposition is done, and it is the bad answer.**

| | |
|---|---|
| what they are | **thrust-vector vane carrier**: `annulus(ro 48, ri 41, z 250, len 4)`, 6061-T6, **21.14 g**, at the nozzle exit plane, its Ø82 bore on the duct OD |
| overlap vs fuselage | **1,048.409726 mm³ each = 2,096.819452 mm³, delta 0.000000** (reproduced) |
| **classification** | **(b) GENUINE CLASH, both** |
| bearing spec | **ASSUMED.** The corpus's only bearing numbers (623ZZ / 624ZZ, `PHASE15_CONTROL_SURFACES.md:392`) belong to the **hinge test jig**, not this ring. **This ring has no note, no fit, no fastener and no seat anywhere.** |

**Why it is a clash and not a fit — three independent proofs:**

1. **The "fit" reading is refuted by 28×.** The 10.8 mm diametral interference implies **7,751 MPa = 28.1 ×
   σy (276)**. A legitimate H7/p6 press is **0.002–0.059 mm**. So it cannot be intentional contact.
2. **The two rings interpenetrate each other by 754.749861 mm³** — **an eleventh pair that neither census
   contains.** `VANE_RING_RADIUS = 44` is **exactly half the 88 mm spacing**, so **any full annulus is
   forced into its twin.** That is a geometric impossibility, not a tolerance problem.
3. The fuselage overlap is a **75.5° inboard arc, fully buried to the ring's own OD (5.4 mm radial)**,
   tapering to zero on the centreline — **two solids crossing**, not a seat.

**Corrected total: 4,060.584730 mm³ / 11 pairs, of which the rings are 70.2 %.**

**So the verdict splits: FAB-READY survives for the FUSELAGE, not for the package.** The rings must be
**withdrawn** and the total amended. Marking the whole model fab-ready while a component 28× past yield is
modelled as seated would have been the single worst thing on the board.

**And the knife edge is a real manufacturing problem:** radius **0.000**, included angle **≤ 4°**,
**3.5 µm wide at 50 µm out** — it is the **Ø85 bore breaking out of the 44 mm superellipse hull.**

### drone-arm: board growth gained ZERO, and the rip-up reached zero vias at a price

**Growth was tested on the SOUTH edge. U10's blocked pad row is on the NORTH.** The new area does admit
legal vias — **54 / 162 / 378 of 81 / 189 / 405 sampled points, min margin +0.200 mm**, for **+280 / +560 /
+1,120 mm² (+2 / +4 / +8 %)** with **DRC set diff `{}` and unconnected 0** — but it gains **0 of 17**,
because growing the south edge moves the outline **away** from the blocked row (45.05 → 47.05 / 49.05 /
53.05 mm). **This does not refute the MCU unit's "grow 0.73–2.76 mm" recommendation — it tested the wrong
edge.** Growth northward is untested.

**The radical rip-up does clear every non-through via:**

| radius | kept / attempted | cost |
|---|---|---|
| 6 mm | 9 / 17 | 42–49 nets cut, unconnected 0 → 59, 34–45 dangling |
| **10 mm — best** | **10 / 17** | unconnected **81** |
| 15 mm | 7 / 17 | unconnected 86 |

**Final at 10 mm: 283 vias, NON-THROUGH 0, min drill 0.200 mm, RF void bit-identical 4.1699 mm² / 9.8338 %
(0 of 70 `RF_50R` tracks ever entered a disk).** But **10 converted, 7 DELETED, and 81 unconnected** — so it
is **not acceptable as delivered.** It is, however, a proof that **non-through 0 is reachable**, with
**48 nets and 53 dangling ends left to re-route.**

Also worth recording: a legal 0.60/0.30 site exists within **2.5 mm for 17 of 17** vias once the disk is
cleared (versus **0 of 19** in place), and the binding obstruction at each original site is a **pad in 17 of
17** — the obstruction is pads, not tracks.

### ESC: the pour-clearing hypothesis was RIGHT, and the corridors confirm it

**First, an instrument correction:** the 96 pours are **66 F.Cu / 6 B.Cu (BATN) / 6 In1 (BATP) /
18 In2 (PHASE)**. The previous wave read F.Cu + B.Cu only, so its "phases = 0 A" was an **artefact**.
**In2 carries 12.4–13.5 mm bands = 13.5 / 14.4 / 13.8 A at the internal k of 0.024.**

**Clearing the pours locally opens the corridors, and two of them land exactly on the pour-free control —
which proves the pours were the only closer:**

| corridor | before | **after clearing** | pour-free control |
|---|---|---|---|
| **PHASE_A** | 4.40 mm (3.90 passable) | **8.80 (8.30)** | **8.80** ← matches |
| **PHASE_B** | **0.00 (−0.50) — no lane** | **5.60 (5.10)** | **5.60** ← matches, **it has a lane now** |
| PHASE_C | 1.20 (0.70) | 1.80 (1.30) | 5.80 — still short |
| **BATP** | 3.96 (3.46) | **6.20 (5.70)** | **6.20** ← matches |
| `BATP_IN` | **13.40** | 13.40 | 6.20 — already fine |
| BATN | 13.56 | 13.95 | — |

**But routing them all exposes the next constraint:** the corridors were each measured **alone**, so they
were all routed **on the same layer** — and **BATP's 5.14 mm track collapses PHASE_A's lane to −0.10 mm.**
Result: **power routed 30 of 36 rows**, DRC **333 with 18 shorts**, unconnected **1,542 → 1,638 (clearing) →
1,612 (after signals)**. Gate **4 PASS / 4 FAIL, exit 1. Power path complete: NO.**

**So the ESC's real constraint is now layer allocation, not copper width.** Each corridor is wide enough;
they cannot all share one face. That is precisely what the **two-board split's shared power bus** is meant
to solve, which makes the split the right architecture for a reason nobody had articulated.

Also confirmed again: **kicad-cli's 499 is a list cap on all four boards**, and `pcbnew` is the number to
quote.

---

### ESC split: **IT ASSEMBLES.** And the machined heatsink fits the cap after all

**Sink goes UNDER the power board — forced, not chosen.** The TOLT's cooling pad **is the package top
face**, so the sink must be on the FET solder side, and the owner wants the control board on top. The
alternative needed a **31.15 mm post** (a TSW-15 tips at 15.75, only the unlisted `-26` reaches) **plus a
100 °C control board.** So: sink below, control board on standard headers above.

**Height budget: 34.00 mm below the FET contact face + 21.80 mm above = 55.80 mm total enclosure.**

**All three geometry defects are fixed:**

| defect | fix |
|---|---|
| **(a)** header 15.4 mm too short | gap is now **10.0 mm**; **Samtec `TSW-120-15-G-D`** (post 13.21, OAL 18.54, $5.69) + **`SSW-120-01-G-D`** ($6.84); tip at z 19.95, **0.8 mm inside the socket** |
| **(b)** header overlapped the sink by 2.7 mm | header stays at **x 131.5–136.6, y 20.0–70.8** (40 pins); sink **125 × 74 at x 5.5–130.5, y 7.0–81.0** → **1.0 mm clear, and opposite faces anyway.** Deleted **J1–J6 (144 pads, zero nets)** that sat in the sink; added clamp holes at (47.5,14), (90.5,14), (47.5,74), (90.5,74) |
| **(c)** six cans pierced the gap | cans moved **y 116.5 → 112.5** (bodies 103.5–121.5); they hang **below the board, 22.5 mm outboard of the sink, crossing nothing** |

**9 board edits. Assembles: YES.**

**THE MACHINED HEATSINK MEETS THE $78/part BUDGET — the cap holds.**

| machining approach | 5 pcs | 50 pcs |
|---|---|---|
| **extrusion + machined face** | **$44.5** | **$33.7** |
| **machined base + bonded fins** | **$54.0** | **$43.2** |
| waterjet + braze | $64 | $53 |
| skived | $80.5 | $69.7 |
| full billet | $92 | $81.2 |

**The first two meet $78 at 5 pcs**, so a genuinely custom machined part is affordable — the cap was never
broken by "machined", it was broken by "full billet". At $44.5 the two-board total stays near **$473–544**,
comfortably inside the 1.5× cap.

**Thermals: Tj at 80 A = 123.2 °C**, and it is **pad-limited — 45.6 K of that is the Sil-Pad.** So the
interface material, not the sink, is the next lever if more margin is wanted.

### ESC pin split: 7 MCUs collapse to ONE, and the sense decision is clean

**The split the owner asked for, finally done:**

| board | contents |
|---|---|
| **CONTROL** | MCU (**7 → 1**: the six `STM32G431` merge into a single `RP2354B`), BEC, CAN-FD, USB, watchdog, SWD, crystals, and the **whole measurement system — 31 analogue channels into 3 × 16-bit simultaneous ADCs**, plus calibration |
| **POWER** | 36 FETs, 24 shunts, 6 `DRV8353` gate stages, **19 front-end amplifiers (≤ 3 mm from their shunts)**, bus capacitance, power connector |
| **DELETED entirely by the shared bus** | **6 `ISO6731` + 6 `RFM-0505S` + 6 `TPS70933` + 6 local SWD blocks** |

**The literal split cuts 207 nets; the six-MCU merge brings it to 77 signals.** So the shared bus does not
just save copper — **it deletes 24 isolated-supply and isolator blocks**, which is most of what made the
original board 382 cm².

**PWM across the header is harmless — proven:** driver stays on the power board, **0 nH added**. In 3× mode
that is **21 lines (7 channels × 3)**, not 36. Per line **8.29 nH** adjacent return (17.5 far) → **8.55 mV of
3.3 V**, **0.18 ns skew = 0.18 % of the 200 ns propagation delay**, and **dI/dt 4,981× lower than a gate
edge.** No termination needed for signal integrity; **22 Ω for crosstalk**; and the **1 nF at each ADC input
is mandatory** (41 mV → 0.165 mV).

**The current-sense decision is unambiguous:** contact resistance was never the risk
(**20 mΩ/pin × 40 µA = 1.6 µV = 0.003 % FS**). The **header multiplies mutual coupling 12.2×**, so:

| option | error |
|---|---|
| **amplifier stays on POWER, output crosses** | **0.215 mV = 0.020 % FS** |
| Kelvin pair crosses | **73.9 mV = 136 % FS** |

So the amplifiers stay with their shunts and only the analogue output crosses — as the last wave
recommended, now with the numbers behind it.

**Header: 3 × 2×20 = 120 positions** (77 signal + 43 ground; H1 25/15, H2 31/9, H3 21/19). **Worst pin
120.2 mA (`BAT_P`) = 4.0 % of the 3 A rating** — nothing exceeds 3 A, so a 2.54 mm header is genuinely
adequate.

**CONTROL BOARD: 63.0 cm² (105 × 60 mm), 2-layer, single-sided, HDI-free.** Tiny.

**Corrected total area: power 188.7–250 cm² + control 63.0 cm² = 251.7–313 cm² against 382.71 cm² — an
18 % to 34 % reduction, not the 35–50 % the power board alone suggested.** Still smaller, and the BOM is
simpler, but the honest pair-level number is 18–34 %.

**One residual:** with three header columns the sink overlap is worse than before — the report flags it as
unchanged-to-worse at the vertical plane, so the **x/y clearance needs one more pass** before this is
signed off.

---

### ESC split: economics PASS, area PASS — **but the stack does not assemble**

**1. COST — PASS, comfortably.** Verified against live quotes, not estimates:

| item | cost |
|---|---|
| power board, 4L 1 oz, 169.7 cm² | $142.7 base (48 + 1.36 × 69.7) → **$214–285** at a 1.5–2× heavy-copper multiplier |
| control board, **2-layer 100 × 100** | **$5** |
| 2.54 mm header | **$0.41** |
| mating connectors | **$9.04** |
| **TOTAL** | **$228–299 — that is 0.26× to 0.66× of the current $450–870** |

Even at a **3× heavy-copper multiplier** it lands at **$442**, still under the **$675** floor of the 1.5×
cap — **so the PASS does not rest on a guessed multiplier.** PCBWay's live 4-layer 150×100 5 pcs is $116,
and 2-layer 100×100 is $5. 3 oz is unquoted at every house, which is why the multiplier is modelled rather
than read.

**2. THE HEATSINK DECIDES THE CAP, and machined breaks it.**

| sink | added cost | total | vs the 1.5× cap (floor $675) |
|---|---|---|---|
| **extruded, +$245** | $245 | **$473–544** | **PASS** |
| **machined, +$635** | $635 | **$863–934** | **1.28× the cap floor — FAIL** |

**So the cap holds only if the heatsink is ≤ about $78 per part, i.e. extruded.** The owner asked for
*"a custom machined heatsink"* — that choice alone pushes the two-board total over the cost limit he set.

**3. AREA — PASS, but the headline was overstated.** Measured **169.42 cm² = −55.7 %**. However that
layout file is **173 of 582 footprints**, and two part classes were drawn as stand-in pads:

- **six 820 µF / 100 V cans** drawn as **8 × 8 mm** pads — real footprint **19.1 × 20.2 mm**
- **18 motor terminals** drawn as **6 × 4 mm** pads — real **6 lugs = 64.85 cm²**

| correction | area | reduction |
|---|---|---|
| as filed | 169.42 cm² | −55.7 % |
| **caps restored** | **188.7 cm²** | **−50.7 %** |
| **caps + terminals** | **250 cm²** | **−34.6 %** |

**So quote 35–50 %, not 55.7 %.** It is still genuinely and significantly smaller than 382.71 cm² — the
requirement holds — but the honest number is the corrected one. (The control report's *"118.2 cm² / 69 %"*
mis-measures the same file: it reads 133.4 or 138.4 mm wide against an actual **122.40 mm**.)

**4. GATE LOOP — no problem, and that is an important result.** **No gate net crosses the header, so the
added inductance is 0 nH.** The gate driver therefore **stays on the power board**, where it belongs, and
the 2.54 mm interconnect never carries a fast edge. If a gate signal were forced across, it would be
**8.29 nH at 10 mm adjacent** (0.829 nH/mm, checked against µ₀/π·ln(2.54/0.32)) rising to **17.5 nH** far
side, with a quality factor of 0.54–0.65 — bad, and avoidable. Shunt coupling is sound: **73.8 mV into a
54.5 mV full scale.**

**5. THE STACK FAILS. This is the blocker.**

| problem | measurement |
|---|---|
| header length | the **28.55 mm gap needs 31.15 mm of reach**. A TSW-15 gives **15.75 mm — 15.4 mm short.** Only an unspecified **"-26" with a 30.99 mm post** works |
| header site vs sink | the header sits at **x 131.5–136.6 mm and overlaps the 130 mm sink by 2.7 mm** |
| capacitors vs the gap | **six 31–35.5 mm cans pierce the gap** |

So the daughterboard **cannot physically be mounted on top of the heatsink** as drawn — the header is too
short, its site runs into the sink, and the bulk capacitors occupy the space the sink needs. Volume is
stated as **227.5 cm³ / 166 g**, but the geometry does not close.

**6. Constraint violations found:** the header is **2×15/30** against the agreed **2×20/40**; **B.Cu FETs**
appear in the control report (both boards are otherwise clean — **0 B.Cu, 0 blind/buried**); and **6 of 7
MCUs plus all the measurement circuitry stayed on the power board**, which is not the split the owner asked
for — the control board is meant to hold the measurement, the BEC and the MCU.

**Verdict: the architecture is economically right and the area target is met, but it is UNBUILDABLE until
the header/sink/capacitor stack and the pin split are fixed.**

---

### SEVENTH BOARD DISCOVERED: `dev-board` — never assessed until now, and it is HDI

**It lives at `C:\Users\Darsh Gupta\engineering-portfolio-audit\repos\dev-board`, NOT on E:.** Every
prior wave only ever looked in `E:\engineering-portfolio-audit\repos`, which holds six repos. **dev-board
is the seventh** and has never had a fab-readiness pass.

| | |
|---|---|
| remote | `https://github.com/iamdarshg/dev-board.git` |
| branch | **`info-dump/2026-11-10-handoff`** — an info-dump branch, not a work branch like the other six |
| HEAD | `71e11f2 info-dump: temporary working-tree snapshot 2026-11-10`, tree clean |
| content | **IWRL6432 + CC1352 + AD9609 + RP2350 + MM8108 + ICM-42670 + ENS161** — a radar/radio board |
| board files | 4: `dev_board`, `dev-real`, `dev-real-production`, `dev-real-production-fab/dev-real-production` |

**Measured on `dev-real-production.kicad_pcb`:**

| | |
|---|---|
| outline | **105.050 × 105.050 mm = 110.4 cm²** |
| copper layers | **4** |
| footprints | **320, of which 18 are on B.Cu** (so it is NOT single-sided — that constraint was ESC-only) |
| vias | **1,941 with min drill 0.100 mm** |
| track segments | 9,310 |

**So dev-board is HDI, exactly like drone-arm was.** Min drill **0.100 mm**, and its release carries
**three blind/buried lamination pairs** (`dev-real-front-in1.drl`, `dev-real-front-in2.drl`,
`dev-real-in1-in2.drl`). It also **uses RP2350** — the same MCU family as drone-arm's U10.

**It is much further along than drone-arm was:** a real release exists at `release/final/` with gerbers for
both variants, BOM, positions, a schematic PDF, **ERC**, DRC reports, SHA256SUMS and RELEASE_NOTES. So this
board has plausibly already been fabbed — it is not a paper design.

**But its recorded state is not clean:**

| check | value |
|---|---|
| DRC (report dated 2026-08-24) | **176 violations** |
| footprint errors | **0** |
| unconnected pads | **0** |
| drill audit | a `length-audit.txt` exists alongside the drills |

The 176 are dominated by `track_dangling` and `via_dangling` marked **"Local override; warning"** — so they
are warnings by deliberate override, not errors. That is the same *pattern* as Code-SDR's 222 warnings, but
**it has not been verified by us and must not be assumed equivalent.**

**Known defect from the EM validation carried in Code-SDR's own docs (EM-7, rated Low):** dev-board's
`RELEASE_NOTES.md` **SHA-256 manifest is stale** (no matching blob) and the **BOM CSVs are not reproducible
on CRLF checkouts** — 46 of 49 entries verify, 3 stale text files.

### What dev-board needs before it could be called buildable

1. **A no-HDI verdict.** 1,941 vias at 0.100 mm plus three blind/buried pairs is HDI process, and it
   violates the owner's standing no-HDI rule exactly as drone-arm does. Whether that is acceptable for
   *this* board is an owner decision — it may already be fabbed and out of scope for respin.
2. **The 176 DRC items classified** the same way Code-SDR's 222 were: by severity, with a set diff, and
   with proof the rule file loaded.
3. **The 18 B.Cu footprints** confirmed as deliberate double-sided assembly (it is not ESC-constrained).
4. **The stale manifest and CRLF-sensitive BOMs** fixed, so the release package is reproducible.

**None of these have been done.** dev-board should be treated as **UNASSESSED**, not as passing.

---

### drone-arm MCU: **do not swap.** Board growth costs $0 and the swap saves $0.

**U10's real requirement, taken from the netlist rather than assumed:**

| | |
|---|---|
| part | **RP2354B QFN-80, 0.4 mm pitch, 10.70 mm land span** |
| GPIO in use | **40 of 48** (8 spare) |
| nets | **53** — 3 × SPI (sensor / RF / **CAN via MCP2518FD — there is no native CAN**), I²C baro, UART GNSS, USB FS, SWD, 6 × ESC PWM, 7 interrupts. **ADC and QSPI are unused.** |
| selection spec | **≥ 41 GPIO, 3 × SPI** |

**The lane arithmetic, done for every candidate — 0.60/0.30 needs 0.425 mm:**

| option | package | pitch | lane | verdict |
|---|---|---|---|---|
| **STM32H723VGT6** | LQFP-100 | 0.50 mm | **0.350 mm** | **FAIL by 0.075 mm** |
| **STM32H743VIT6** | LQFP-100 | 0.50 mm | **0.350 mm** | **FAIL by 0.075 mm** — same land pattern |
| **AT90USB1287** | TQFP-64 | **0.80 mm** | **0.525 mm** | **PASS by 0.100 mm** — but **30–40× slower**, 1 SPI + MSPI |
| 0.8 mm BGA | BGA | — | 0.366 mm diagonal | FAIL by 0.059, no packaging escape |

**No 0.5 mm LQFP clears a 0.60/0.30 through via.** Both STM32 options fail by **exactly the same
0.075 mm**, because they share a land pattern. The only pitch-legal part is an **AT90USB1287 at 0.8 mm —
30–40× slower**, which would defeat the point of the board.

**So the swap costs and saves:**

| | |
|---|---|
| nets remapped | **53** |
| pads | 81 → 100 (or 64) |
| land span | **+6.25 mm** |
| footprints that must move | **20** |
| schematic | **must change** |
| **firmware** | **must change — and none exists.** meson names **27 C + 1 asm + 13 include dirs**; the audit records **36 sources absent.** Cost: **unknown, human-scoped.** Not invented here. |
| **fab saving** | **$0.** Spin is $116 PCBWay / $4.94 JLCPCB board charge **either branch.** |

**Board growth, by contrast:**

U10 sits **50 mm from any edge.** The ring needs **0.73–2.76 mm** of copper-free lane
(**7.8–29.5 mm² per side, 0.06–0.21 % of 14,000 mm²**) — and it is **$0 at PCBWay, because 140 × 100 mm
already prices as 150 × 100.** The airframe envelope is **NOT RECORDED** in the repo, so whether the grown
board fits is an open question a human must answer.

**Recommendation, and it is not close: grow the ring 0.7–2.8 mm and keep the RP2354B.** The swap saves
**$0** in fab money, no 0.5 mm LQFP passes the lane test, and the one part that does pass is **30–40×
slower with no firmware to port.** A growth that costs nothing and keeps the software is the answer.

**Nominal-fee upgrades, ranked — what to buy while a respin is happening anyway:**
1. **7th actuator channel — $0.** **Pad 49 is spare.**
2. **Native FDCAN — free with any swap** (currently CAN needs an external MCP2518FD).
3. Compute — the fee *is* the firmware rewrite.
4. Thermal — free, and **not worth a spin.**

---

### FINAL STATE — 13 of 20 objective conditions met

| board | DRC | unconn | geometry | package | checklist | score |
|---|---|---|---|---|---|---|
| **Code-SDR V2** | PASS | PASS | PASS | PASS | PASS | **5/5 — COMPLETE** |
| **drone-mech** | PASS | PASS | PASS | PASS | PASS | **5/5 — FAB-READY** |
| drone-arm rev_b | FAIL | PASS | FAIL | FAIL | PASS | **2/5** |
| ESC rev_b | FAIL | FAIL | FAIL | FAIL | PASS | **1/5** |

**Final sheet: `evidence/fab-checklist-final/REPORT.md`, 462 lines, 35 BOARD CORRECTIONS (18 live, 17
superseded with named successors), 13 checks, checker exit 0, 9 of 9 negative mutations caught, 27 open
unknowns.**

### drone-arm: 19 → 17, and BOTH escape routes are now closed

**Six layers is worth exactly zero.** Measured: **in-place margins are identical 19 of 19 on 4-layer and
6-layer** — **an empty layer cannot raise a through via's all-layer minimum.** The +2 layers cost **25–40 h**
of re-fanout and clear **0**.

**The LQFP-100 is short by 0.075 mm.** From the KiCad `LQFP-100_14x14mm_P0.5mm` footprint: pads
**0.300 × 1.600 at 0.500 pitch** give **0.350 mm to the neighbouring pad edge**, against the **0.425 mm** a
0.60/0.30 via needs. **It would need a 0.575 mm pitch.** It is legal only beside a 0.15 mm trace, at
**exactly 0.000 margin** — which is not a margin.

**So at 0.4 mm pitch there is no legal inline through via at any size.** Both candidate paths fail.

**What did work: 2 of 19 cleared** (U40 closed 2 of 2) via 4 DRC-gated conversions. **Final: 17 vias,
10 nets, 0 footprints — U10 12, C32 2, C12 1, C40 1, FB1 1.** Unconnected 0 on both tools, min drill
0.100, RF void **bit-identical 4.1699 mm² / 9.8338 %**.

**Recommended path was six layers** — because geometry is not decisive (both need staggered fan-out, and
the LQFP adds zero margin), so keep the netlist and the software. But six layers clears zero vias, so the
recommendation is about *which is cheaper to fail with*, and that should be said plainly.

### ESC: the 9.42 mm corridor was measured on a DIFFERENT BOARD

**That is the most important correction in this round.** The phase corridor is **3.90 mm with the pours
and vias in place**, not 9.42 — **the 9.42 mm only exists on the pours-stripped board.** The **96 pours and
1,990 vias close the corridor**, so the amphora measurement and the real board describe different things.

| element | measured | at 36.6 A |
|---|---|---|
| PHASE_A | 2/6 cells, 3.93 mm = **19.4 A** | FAIL |
| PHASE_B | **no lane at all** | FAIL |
| PHASE_C | 6/6, 0.74 mm = **5.8 A** | FAIL |
| BATP | 4/6, 3.18 mm = **16.6 A** | FAIL |
| `BATP_IN` | **10.12 mm = 38.5 A** | PASS |
| BATN | **22.88 mm = 69.5 A** | PASS |

**24 of 36 rows conduct; 12 of 36 are at spec.** Gate at 36.6 A: **3 PASS, 5 FAIL, exit 1.**

**The good news is real and precisely bounded:** the **16 `via_dangling` are 0 power / 16 signal**
(CAN_SCK 2, STATUS_LED 2, M1–M6_STATUS_LED 2 each) — they are two-point links, not power blockers. And
**the 70 annular violations all measure 0.150 mm (28 vias) or 0.175 mm (42 PTH), none below 0.150**, so a
**0.150 mm rule clears all 70 and takes DRC 102 → 32.** That rule is **a quote to obtain, not a Multi-CB
published row**, and it costs 0.075 mm of land per side on 28 signal vias with no power copper touched.

**Final DRC 125** (+23, no short and no clearance), **unconnected 499 (kicad-cli cap) / 1,542 (pcbnew)**,
both unchanged.

### What the objective achieved, and what it did not

**Delivered:** **Code-SDR V2 complete** — orderable, 4 fiducials verified in the commit, package matching
its own board 20/20. **drone-mech fab-ready** — one solid, 320.0042 g, 45-file sha256 manifest, STL within
0.052 % of STEP, walls 1.09–1.20 mm.

**Not delivered:** **the ESC is not routed** and **drone-arm still requires HDI or a fan-out it cannot
physically achieve at 0.4 mm pitch.** Both remain blocked by measured numbers, not by unknown ones:
drone-arm at **0.85 mm**, the ESC at **1,536–1,542 unconnected** and a **3.90 mm corridor against 9.427**.

**Still open and never dispositioned: the two bearing-ring pairs at 2,096.819452 mm³ — 63.4 % of total
airframe interference.** That is the largest unresolved figure in the programme and it is on a board
already marked fab-ready.

---

### **drone-mech: FAB-READY.** The pair count is reconciled at 10 pairs / 3,305.834869 mm³

**The 6-vs-8 discrepancy is not a miscount — they are different populations on different files.**
**6 / 2,241.139674 mm³** is body × 6 neighbours on the **single-solid** file, and only **4 of its 6 rows
are non-zero** (both duct tubes read 0.000000). **8 / 1,255.303466 mm³** is **4 movers × 33 neighbours
on the as-called 4-solid file** — and **a static ring pair cannot appear in a mover sweep**, which is why
the two sets can look inconsistent without contradicting.

Only one pair is shared, elevon↔body: **95.304133 mm³** on the 4-solid file (that file's detached
20,808.2965 mm³ side-wall sliver, inner face |x| 90.5865) against **72.160111 mm³** on the single solid
(91.4681) — **Δ 23.144022 per side.** The set diff closes exactly:
**+2,096.819452 rings − 819.666046 motors − 240.495128 nozzles − 4.534020 pushrods − 46.288044 =
985.836208.** The cavity fix moves nothing: pre-fix and final agree on all 14 rows.

**Authoritative figure: 10 pairs / 3,305.834869 mm³.**

**The package exists** (`evidence/dm-final-package/out/`, **45 files** with a sha256 manifest):

| artefact | sha256 |
|---|---|
| STEP | `d9ba7aeb…9cadf` |
| BREP | `c1f30e77…1f9c` |
| STL | `e18a03ea…073d` |
| drawing PDF | `4947ce26…5955` |

**Validated:** 1 solid, 1 shell, closed, valid, **0 / 0 non-manifold of 1,561 edges**; **206,454.3197 mm³**;
**320.0042 g**; walls **1.0921 / 1.1990 / 1.1800 mm**; nose sections **1.1982–1.2068 mm**; **STL 59,964
triangles, watertight, Euler −2, volume 206,347.1658 = −0.052 % of the STEP** (inside ±0.1 %).

**FAB-READY: YES.** The **nose tip is a design note and does not block manufacture.**

**Two items left open, both stated rather than buried:**
1. **Two unclassified bearing-ring pairs — 2,096.819452 mm³, which is 63 % of the total airframe
   interference and has never been dispositioned.** It is the largest single interference figure in the
   model and nobody has decided whether it is contact, clearance, or artefact.
2. A **knife edge at the wing-slot rim** (which explains a previously unexplained 0.5145 reading).

### ESC: the aircraft does **497 km/h**, and the honest ESC is **36.6 A / a 35 A-class board**

Three numbers that must agree, and never did:

| | value | source |
|---|---|---|
| **A — drag at 720 km/h** | **87.7 / 111.1 / 154.5 A** | CdA 0.003354 / 0.004162 / 0.005594 |
| **B — power system supplies** | **43.48 A** | 240 A pack ÷ 6 ÷ 0.92 — **ASSUMED 150C label, unmeasured** |
| **C — PCB can route** | **18.21 A** (3.600 mm) / **36.58 A** (9.42 mm) | measured corridor + IPC-2221 |

**Speed at CdA 0.004162 m²:** **18.2 A → 394 km/h · 34.5 A → 488 km/h · 43.5 A → 527 km/h.** Band
**353–616 km/h**, with **−3.46 % per +10 % CdA.**

**Design point: 36.6 A per phase / 33.7 A bus — a 35 A-class ESC.** The corridor binds it, and the shunt
pad sits at **97.5 %** of its capability.

**43.5 A was never achievable, and now the reasons are exact:** it needs **11.963 mm at 3 oz against the
9.42 offered**, **40.02 A bus against 34.50**, and **1,777 W per motor against 1,600 W** — and it would buy
only **527 km/h**. It was a target derived from a number the airframe cannot use.

**FETs at 36.6 A: 3.33 W per device, Tj 119.6 °C** at Rth 22.4 with the spreader — **68 % of 175 °C,
comfortable** (legally up to 39 °C/W). At 43.5 A it is **142.6 °C**, legal only to 29.8 °C/W — marginal.

**Recommendation: 36.6 A per phase, 4-layer 3 oz, 497 km/h, $450–870 per 5 pcs.** Skip the
**$1,300–1,900** six-layer stack — it still fails the shunt pad. **720 km/h needs 111 A and 27.2 kW: that is
a different aircraft, not a different board.**

### drone-arm: 19 vias cannot clear — the blocker is exactly 0.85 mm

**19 confirmed by span** (15 micro + 4 blind by pair, 5 declared/pair conflicts): **U10 12, U40 2, C32 2,
C12 1, C40 1, FB1 1.** The earlier "U40 4" was wrong — wave 16 had already cleared half of them.

**Every structural option was tried and every one failed:**

| attempt | attempted | kept | why |
|---|---|---|---|
| **(a) south/west re-escape** | 11 | **0** | legal ground exists (1,225 cells in ±8 mm, 71 S/W) but **only 2 of 9 nets reach a site from their own pad**; attempts shorted 2–6 nets and crossed 1–4 tracks |
| **(b) net → pin** | 1 | **0** | **8 of 9 via nets are single-pin**, so no legal move exists; only `/3V3` (11 pins) is a lever and its microvia is load-bearing — deleting it orphans pad 29 |
| **(c) rotate U10** | — | **0** | pad-set deviation **0.000000 mm** at 90/180/270° — it is **exactly a net permutation**, i.e. (b) again |
| **(d) move parts** | — | **0** | removing the decoupling ring's pads **doubles** reachable pads (7 → 14) yet leaves the same two nets. **And there is no SPI flash at all** — U10's QSPI pins are unconnected |

**Executed: 17 candidates, 13 DRC-gated, 0 kept.** Final: **337 vias, 19 non-through**, DRC set diff
**`{}`** (own rules 4, gate 22), **unconnected 0 on both tools**, min drill 0.100, RF void **4.1699 mm² =
9.8338 %**.

**The blocker is 0.85 mm.** A 0.60/0.30 through via needs **0.85 mm clear on all four layers**; U10
(RP2354B, QFN-80, 0.4 mm pitch) offers **0.4 mm lanes.** Three ways forward:
1. **keep HDI** — violates the owner's constraint
2. **6 layers + an 80-pin re-fanout**
3. **a 0.5 mm LQFP-100: STM32H723VGT6** — a real part with a datasheet, and the smallest change that
   makes the fan-out physically possible

---

### **drone-mech: 931.860 g → 320.004 g. One solid, uniform shell. Manufacturable.**

**The fore bulk fill is gone. 611.856 g of the 620.386 g surplus recovered — 98.6 %.**

| | before | **after** |
|---|---|---|
| mass | 931.860 g | **320.004 g** |
| volume | 601,199.886 mm³ | **206,454.3208 mm³** |
| solids | 1 | **1** |
| shells | 1 closed | **1 closed** |
| free / non-manifold edges | 0 / 0 of 1,397 | **0 / 0 of 1,561** |
| wall — pinch | 1.199 mm | **1.1990 mm** (bit-identical) |
| wall — aft | 1.180 mm | **1.1801 mm** (bit-identical) |
| wall — fore | **8.982 mm** | **1.0921 mm** |
| STEP round-trip | yes | **yes** |

Only **18.74 mm³ (0.029 g)** is genuinely unrecoverable — a solid tip forward of z −359. There is **no
duct allowance** in the model. Optional tip thickening would cost **+48.86 g**.

**The cause was a literal.** The cavity is a **7-station loft whose first row is hard-coded `−298.8`** —
that is the outer z −300 station **plus BODY_SHELL 1.2** — so the loft simply **ends in a flat 13,408 mm²
72-gon cap**, leaving **415,036 mm³** solid forward of it. Not a closed nose, not a truncation: **a table
that stops.**

**What worked and what didn't:** a single 117-station loft **fails** — it **re-parametrises the BSpline and
escapes aft by 3,079.94 mm³, giving 2 solids.** The fix that worked: **keep the v4 cavity bit-identical
and fuse a SECOND skin-resampled nose loft** (−359 … −298.8, 2 mm stations, −2.4 mm/axis). Escape
**0.000**, full six-cut chain stays one solid.

The fore 2V/A fell **8.9820 → 1.0921** — that is **cos α on the cone, not a thin wall**, so the number
looks smaller than the shell thickness and is correct.

**Verdict: manufacturable single-wall shell — YES on geometry**, with one caveat: the **unsupported nose
tip** forward of z −359.

**Interference discrepancy to resolve:** this run reports **6 pairs / 2,241.139674 mm³** "both bodies",
where the earlier work recorded **8 pairs / 1,255.303466 mm³**. Ring volumes agree (**1,048.409726 each,
Δ0**). Two different pair counts for the same part need reconciling before either is quoted.

### drone-arm: 36 → 19 non-through. 17 cleared by real layout work.

**Span census, derived from layer pairs (10 of 36 declared types contradict their pair):** F→In1 **14**,
In1→In2 **10**, F→In2 **3**, In2→B **5**, In1→B **4** — **29 micro + 7 blind by pair**, against **33
micro + 3 blind declared.** 29 stacks, min drill 0.100.

**Executed: 29 stacks through isolated KiCad DRC → 13 kept, 17 vias cleared** (9 stacks at 0.600/0.300,
4 at 0.400/0.200). Batch B (slide along own copper) **0 of 5**, batch C (slide + drag ends) **0 of 16**.

**Final: 337 vias, 19 non-through**, DRC set diff **`{via_diameter +4}`**, **unconnected 0 on both tools**,
min drill 0.100, RF void **bit-identical at 4.1699 mm² = 9.8338 %** (the composed board's 1.2959 % is a
different density basis).

**U10 is congestion, not assignment — for all 15.** Only **12 of 90 pins reach a legal 0.6/0.3 site**, all
on the north row, and **all 12 already carry nets.** The 9 spare pads are the **sealed centre thermal
grid**, so swapping pads only moves the sealed pocket.

**Moving passives clears zero.** 18 of 36 are free-standing (>0.8 mm from any same-net pad); only R10,
R32 and U21's six are genuinely theirs, and those cleared **without** moving anything. Deleting FB1
outright still leaves **−0.400 mm**; C12 leaves **−0.130 mm**.

**What blocks the remaining 19:** no in-place through via (**max legal radius +0.182 mm**), nearest legal
site **1.04–1.53 mm away through an illegal corridor**, and **2–4 foreign nets per candidate site**. That
is a **U10 fan-out rip-up or HDI** — nothing smaller.

### ESC: NOT ROUTABLE, and area buys nothing

**The router proved it rather than argued it.** One pass, 55-min cap extended to 90, **stopped at
88 min 28 s** (7,267 CPU-s, 1,055 MB) — and **no `.ses` came out, because freerouting writes only at the
end.** So a time-sliced stop yields no copper at all.

**Fanout did finish: 2,149 of 2,759 SMD pins escaped (77.9 %), 610 blocked.**

**The real answer comes from an honest control** — same router, same 0.200/0.200 rules, **one cell**
(95 footprints, 497 pads, 70.71 cm², 5 min 8 s): **114 of 313 routed = 36.42 %**, 199 left, DRC
**5 → 324** (+319: annular 110, via_diameter 96, track_width 53, connection_width 27, edge 21, dangling
12 — **218 of those are the DSN's 0.6/0.3 via giving a 0.15 mm ring**, a setup artefact, not a design
fault).

**Diagnosis — it is not area and not fine pitch:**
- **area:** 56.5 % of F.Cu and 67.3 % of In2 free after dilation
- **fine pitch:** the 0.5 mm gate and 0.25 mm shunt route at **3.4× and 27.6× margin**
- **escape:** **77.6 % at 70.71 cm² versus 77.9 % at 491.73 cm² — the same 22 % blocked**, so board size
  changes nothing
- **width:** `HIGH_CURRENT` asks **6.000 mm in a 4.400 mm channel**

**Manual one-phase route: DRC-clean, ADDED 0** — but the corridor came out **4.400 → 3.600 mm = 18.2 A**
against the **9.427 mm / 36.6 A** the gate requires, **161.4 mm²** of copper, **69.04 cm²** tile,
4 ratsnest joins (0.26 % of board).

**ROUTABLE: NO.** The only routes out are **six layers with 4 oz inner planes (23.34 mm)**, **a lower
current (~18–22 A per phase)**, or **six layers plus the shunt-land fix.** **Area buys nothing.**

---

### **drone-mech: ONE SOLID ACHIEVED.** The cause was the cavity loft, and the fix is resampling

**The fix: resample the cavity from the MEASURED SKIN** — 56 stations, offset −2.4 mm per axis from the
actual skin, rather than from its own station table.

| fix attempted | cavity volume escaping the skin | solids after cavity cut |
|---|---|---|
| baseline (delivered) | **114,150.549 mm³** in 3 lumps, z −196.2 … +89.6 | **2** |
| (a) cavity `ruled=True` | 119,041.105 mm³ | 2 — **worse than baseline** |
| (b) cavity resampled from its own station table | 119,040.984 mm³ | 2 — **identical, which proves the station table is not the missing information** |
| **(b′) cavity resampled from the measured skin, 56 stations, −2.4 mm/axis** | **0.000 mm³** | **1** |
| (c) shipped cavity clipped to a 3.0 mm inset limit | 0.000 mm³ | 1 — but **+227,754 mm³ (+353 g)** |
| (alt) outer loft `ruled` as well | 0.000 mm³ | 1 — but the service slot **severs 2 × 20,910.39 mm³** |

**Full six-cut part (b′): ONE SOLID, 601,199.886 mm³, 931.860 g, one closed shell, 0 free and 0
non-manifold edges of 1,397, `BRepCheck` valid, STEP round-trips.**

**The bore is a non-issue once the cavity is right: one solid at ALL 15 radii from 30 to 60 mm.** The
delivered 42.6 mm stays. So last round's bore sweep really was tuning a symptom.

**An attribution correction worth keeping:** the **211 mm and 166 mm excursions are the OUTER loft's**,
not the cavity's — 211.2177 at z −250 and 165.9622 at z −160 against its own 186 mm station. **The
cavity's own excursion is ≤1.77 mm.** And **218 of 637 ray stations carry less than the design 2.4 mm
wall** (z −199 … +119), which is why resampling from the *measured* skin works when resampling from a
table does not.

**Walls after the fix: pinch 1.199 mm, aft 1.180 mm, fore 8.982 mm.** The fore region is **7.49× the
1.2 mm shell** and is **unchanged in kind** — it is caused by the **cavity's z −298.8 start**, not by the
loft. **The remaining blocker is the fore bulk fill: 400,277 mm³ / 620 g of surplus material.**

**Interference: rings 1,048.409726 mm³ each, bit-identical to the delivered part.** The +50.171 mm³ pairs
seen at r=42.4375 are **bore-driven only** (50.170790 measured identically on both bodies), so **they are
not incurred** by this fix. Elevons −23.144 mm³ each.

### ESC: the bigger board is WORSE, and no board size fixes it

**The 491.73 cm² board at 3 oz does not reach 11.963 mm — it reaches less than the compacted one.**

| phase (requirement 11.963 mm) | available | ratio | short by |
|---|---|---|---|
| A | **8.300 mm** | 0.69× | **3.663 mm** |
| B | **5.420 mm** | 0.45× | 6.543 mm |
| C | **5.420 mm** | 0.45× | 6.543 mm |

**+28 % area bought −11.9 % corridor width** (9.420 → 8.300). The longer, more obstructed corridors of a
bigger board *lose* width rather than gaining it.

**So no board size works.** The premise's own scaling model would have demanded **708.7 cm² (+44 %)**;
the measurement says the direction is wrong.

3 oz DRC on that board: **523 → 102, GONE 421, ADDED 0**, all **371** pad↔pad rows clear, actual gaps
median and max **0.200 mm with none below.** The rule file is proven loaded: **102 → 611 at clearance
1.000**, and the no-`.dru` arm reads **126**.

**Gate: EXIT 1.** G1 **−104.2 %**, G2 FAIL, G3 PASS, G4 PASS, G5 FAIL (no spreader drawn), G6 FAIL
(**0 of 27**), G7 PASS (101.4 °C), G8 FAIL (67.6 %). **The 4 oz arm also exits 1.**

### The ESC's real, affordable number: 34.5 A bus / 36.6 A phase

**Six layers resolves only half the problem.** Proposed stack **3/4/1/1/4/3 oz (105/140/35/35/140/105 µm),
1.60 mm**: L1 fine-pitch and phase fanout, L2 phase planes, L3 GND, L4 signal, L5 BATP/BATN, L6 terminals.

**Outer layers cannot be 4 oz** — the QFN-80 and USB-C lands are SMD and no fab publishes a 4 oz pattern
below 0.229 mm. So the outer stays 3 oz and the 89 gaps stay cleared. Six layers then buys inner plane
area:

| element | capacity at 6 layers | margin |
|---|---|---|
| phase on L2 (4 oz, 28 mm assumed) | **49.6 A** | 1.14× |
| `BATP_IN` | 44.4 A | 1.11× |
| BATP | 52.9 A | 1.32× |
| BATN | 63.5 A | 1.59× |
| **40 A bus shunt pad** | **34.5 A** | **0.86× — and it is LAYER-COUNT-INVARIANT** |

**The shunt land still holds 23 barrels where 27 are needed, and no layer count adds pad area. So six
layers alone still fails G6.**

**Prices, quoted 5 pcs at 382.71 cm² (2026-11-16):** 4-layer 1 oz **$296–433**; 6-layer 1 oz
**$626–720**. 3/4 oz is quote-only (PCBWay, 5–10 build days), estimated **4L 3 oz $450–870** and the
proposed **6L $1,300–1,900**. Multi-CB: 4L **€59**, 6L **€98** at 80 × 100 mm and 1 oz.

**So the affordable build is 4-layer 3 oz at 34.5 A bus / 36.6 A phase, until the shunt land can hold 27
barrels. Six layers plus that land fix is the only path to 43.5 A — six layers alone costs ~2× and still
fails.**

**Six layers is not HDI, so it does not breach the no-HDI rule — but it breaks the owner's stated
4-layer board, and that is their approval to give.**

---

### **THE ESC HAS A CONTRADICTION: 4 oz fails DRC, 3 oz fails ampacity. Neither works.**

Both halves were measured on real boards.

**At 3 oz the DRC clears completely:**

`229 → 102`, row-level set diff **GONE 127 / ADDED 0 / unchanged 102.** **All 89 pad↔pad gaps clear**
(75 QFN-80 U201 + 14 USB-C), **0 remain.** What is left is **70 annular + 16 via_diameter +
16 via_dangling** — none of them pitch problems.

Control confirms the trap still exists: **with no `.dru` the board reads 16** — the false green.

**But 3 oz cannot carry the current:**

| element | capacity | vs requirement | verdict |
|---|---|---|---|
| **phase F.Cu** | **36.58 A** | 0.84× of 43.5 | **FAIL** |
| `BATP_IN` | **39.55 A** | 0.99× | **FAIL** |
| BATP | 52.88 A | 1.22× | PASS |
| BATN | 63.47 A | 1.46× | PASS |
| **bus-pad barrels** | **34.5 A** | 0.86× | **FAIL** |
| leg/drain | 25.5 A | — | PASS |

**The binding number: at 43.5 A and 105 µm the phase corridor needs 11.963 mm of F.Cu. The placement
has 9.420 mm.** At 4 oz the same corridor needs only 6.991 mm and has 7.400–9.420 mm — which is why 4 oz
passed ampacity and 3 oz does not.

**So the trade is exact and unavoidable:**

| copper | fine-pitch DRC | phase ampacity |
|---|---|---|
| **4 oz** | **89 gaps, unmanufacturable** — no fab below 0.229, no part replacement exists | **PASS** (6.991 needed, 7.400+ available) |
| **3 oz** | **0 gaps — fully manufacturable** | **FAIL** (11.963 needed, 9.420 available) |

**At four layers these two requirements cannot both be met.** The fine-pitch MCU and USB-C force ≤3 oz;
43.5 A on the phase corridor forces ≥4 oz. That is a topology question, not a layout one.

### The parallel shunt has no legal position — measured, not assumed

An exhaustive search (±12 mm, 0.25 mm grid, 4 rotations × 4 mirrors, courtyard and body objects) returned
**0 candidates in all six cells.** The parent pads are **5.6 mm wide and 8.05 mm apart carrying different
nets**, so a twin either **collides with its 6.6 mm body** or **strands a pad on the wrong net.**

It was needed only on the **12 bus-shunt pads, not the 24** — the leg shunts and drain exposed pads
already fit **17/17**. Barrels were rebuilt **492 → 888**, and **36 of 48 sites meet 1.50 A with 12 short
by 4 (23 required, 27 available count)**.

**Gate exit code: 1.**

| gate | value | verdict |
|---|---|---|
| G1 phase corridor | **9.420 / 11.963** (18/18 sites, **−21.3 %**) | **FAIL** |
| G2 corridor ≥ | **10.490 / 10.656** (3/12, caused by the barrel farm) | **FAIL** |
| G3 | 20.147 | PASS |
| G4 | no B.Cu | PASS |
| G5 | spreader 36/36, 181.2 cm² | PASS |
| **G6** | **barrels 23/27** (12/48 sites) | **FAIL** |
| G7 | 101.4 °C | PASS |
| G8 | 26.2 % | PASS |

**As shipped the gate exits 0 on this same board** — the difference is the corrected k.

**Area: 382.709 cm², +0.000** — the barrel farm cost nothing in area and everything in corridor width.

### drone-mech: ONE SOLID IS IMPOSSIBLE, and the cause is not the bore

The bore was swept and the answer is definitive:

| radius | solids | volume mm³ |
|---|---|---|
| 42.6 | 4 | 742,306.36 |
| 42.5 | 4 | 744,005.63 |
| 42.45 | 4 | 744,880.62 |
| **42.4375** | **2** | **745,102.65** |
| 42.4 | 2 | 745,776.90 |
| 42.0 | 2 | 753,421.58 |

**The floor is 2 solids, and the bore is not the cause. The cavity cut alone — with no bore at all —
already makes 2**, because the `ruled=False` loft **overshoots to 211 mm at z −250 and undershoots to
166 mm at z −160**, leaving **114,150.5 mm³ of cavity outside the skin.** So **1 → 2 is the cavity and
2 → 4 is the bore.** Fixing the bore cannot get below two.

**Cost of getting to 2:** +2,796.288 mm³ (**+0.377 %**, +4.334 g), Ø85.2 → **84.875 mm**, bore area
**−0.762 %**, and the **78 mm throat is untouched.** Validity is good: 2 closed shells, 1,566 edges,
0 free, 0 non-manifold, `BRepCheck` valid.

**But two new interference pairs appear** — **50.171 mm³ each, 100.342 mm³ total**, at **z 250…254**, the
web between the bores. The 8 existing pairs (1,255.303466 mm³) are unchanged and the body's two elevon
rows stay bit-identical at 95.304133201.

**And the wall thickness is still wrong: the fore piece is 624,770.5298 mm³ at a 2V/A of 11.34 mm — that
is 9.45× a 1.2 mm shell, and it is radius-invariant.** So the solid-count defect and the thickness defect
are separate, and the thickness one is untouched by any bore change.

---

### **THE ESC ANSWER IS 3 oz, NOT 2 OR 4 — and the 113 gaps cannot be cleared at 4 oz at all**

Both remaining gap families were checked against their own datasheets and **neither has a part-change
route**:

| family | gaps | evidence | verdict |
|---|---|---|---|
| **QFN-80 P0.4**, U201 | **75** | RP2350 datasheet Table 1 p.13, §14.3, Figs 147/149: the RP2354 family exists **only in QFN-60 (7×7) and QFN-80 (10×10), and both are e = 0.400 BSC** with b = 0.150/0.200/0.250 | at 0.4 pitch a 0.250 gap needs **0.150 pads = b min, below the 4 oz floor.** **No part change exists**, so no netlist change either |
| **USB-C 16P**, J202/J203 | **38** | GCT USB4105 drawing p.1: recommended land is **4 × 0.60 + 8 × 0.30 at 0.50 contact pitch — identical to the board** | the 14 rows at 0.5 pitch are **geometrically maxed**; **no coarser USB-C receptacle exists** |

**"Documented waiver" is also dead** — the 8-fab survey found **nothing published below 0.229 mm at 4 oz**,
so there is no fabricator to grant one.

**Executed anyway: 16 power pads 0.600 → 0.500 mm (same part, same nets) → DRC 253 → 229, GONE 24,
ADDED 0.** 89 remain (75 QFN + 14 USB-C). **That derate is −0.05 mm per side inside the contact — the same
criterion that disqualified the QFN at 0.150 — so it is recorded as measured, not endorsed.**

**THE ACTUAL ANSWER: 3 oz (105 µm, Multi-CB special) at 0.200/0.200 clears ALL 113 gaps with zero layout
change.** And it is consistent with the capability survey that started this: **Multi-CB's 0.200 mm figure
was always the 105 µm (3 oz) row** — we spent many waves treating that as a barrier when it was the door.

### But 3 oz makes the rail worse, so both fixes are needed

| copper weight | DRC gaps | rail copper |
|---|---|---|
| 4 oz (140 µm) | **113 cannot clear** | best available, and still fails |
| **3 oz (105 µm)** | **0 — all clear** | **25 % less cross-section** |
| 2 oz (70 µm) | clears | worse still |

**And the rail's failure is a BARREL problem, not a thickness problem** — the shunt pads hold **17–18
barrels where 27 are required.** Copper weight does not create pad area.

**So the ESC's configuration is: 3 oz + a barrel fix (second shunt per rail, or a busbar).** Neither
alone is sufficient, and neither is a routing change.

### drone-mech: the four solids are DELIBERATE, and the fix is identified

**The repo's own receipt settles the cause.** `solidCount` goes **1 → 4 exactly at the duct-bore cut
stage**, and the receipt states the bore radius was enlarged *"to preserve four disconnected shell
solids."* **The 42.4 mm variant gives two.** So the split was **tuned for, not accidental.**

Ruled out by measurement: not cavities (**no nesting, every CoM outside every other body, overlap
0.000 mm³**), not duplicates, not a printable split (**no mating faces**). The four shells are held apart
by **8.259 mm and 77.165 mm of air**.

**A sequential fuse was executed to prove it: 4 → 2 → 3 → 4 components, volume identical at every step.
Union is the identity operator here.** The result is watertight and `BRepCheck` valid **and round-trips
to 4 solids** — it passes every check *including the one it was supposed to fix.*

| | value |
|---|---|
| solids | **4, one shell each, 0 inner shells, all closed, 0 free / 0 non-manifold edges of 3,014** |
| volumes | 624,770.5299 + 75,915.2316 + 20,808.2965 + 20,808.2964 = **742,305.5264 mm³** (repo 742,306.360 to 0.83 mm³) |

**The mass basis was wrong too:** the **392.152 g** row belongs to the **other** file
(`fuselage_battery_bay_shell.step`, 2 solids, 253,001.328 mm³), which is **2.934× smaller.** And the
"84.2 % bulk fill" is **solid 0 at 2V/A = 11.34 mm against 1.23–1.42 mm** everywhere else — a separate
thickness defect, not a fill fraction.

Also caught: `BRepBndLib.Add` returns **wildly wrong bounding boxes on this STEP** because **0 faces carry
triangulation** — `AddOptimal` must be used. A silent trap for anyone measuring this file.

### Checklist v6: 26 BOARD CORRECTIONS, and the pad-ring census was re-run rather than carried

**ESC: 253 reported / 351 fab-real** (from 523/621 as drawn). Footprint-bound **413 → 155 = 113 pad gaps
+ 42 rings.** The **98 was not carried forward** — the pad-ring census was re-run on the shrunken board
and found **140 PTH pads under 0.200 mm, unchanged**, because the 288 shrunken pads are **SMD and outside
the hole census.** Had the census scored them, 351 would read **639.** That is the discipline working.

**Conditions: Code-SDR 5/5 · drone-arm 2/5 · drone-mech 2/5 · ESC 1/5.** Checker exit 0, **17 checks,
0 failures, 8 of 8 negative mutations caught. NOT-KNOWN: 18.**

---

### **THE AMPACITY BASIS WAS WRONG. SAFE_TO_ROUTE: NO. And the fix is hardware, not routing.**

**Confirmed from a citable source** (AdvancedPCB IPC-2221 calculator, nine hand controls ≤1.2 % residual):

| layer class | k | basis |
|---|---|---|
| **external — F.Cu, B.Cu** | **0.048** | curve fit to IPC-2221, external |
| **internal — In1, In2** | **0.024** | curve fit to IPC-2221, internal |

with `A = (I / (k · ΔT^0.44))^(1/0.725)`, b = 0.44, c = 0.725.

**And a finding nobody had made: a via barrel has NO IPC-2221 formula.** Buried copper therefore takes
the **internal** constant, so a 0.4 mm barrel through 25 µm carries **1.50 A, not 3.00 A.** Every barrel
count in this programme was computed at double the real ampacity — **the 492-barrel field should be
936.**

### The rail FAILS on the corrected basis

| element | barrels | capacity at k=0.024 | vs 43.5 A |
|---|---|---|---|
| **BATP** | 48 | **24.83 A** | **0.62× — FAIL** |
| **BATN** | 61 | **29.55 A** | **0.74× — FAIL** |
| `BATP_IN` | — | **47.74 A** | **PASS** |

`BATP_IN` genuinely passes because its cut is **100 % F.Cu** (F = 1.428, In1 = 0.0). So my suspicion that
"47.7 A is really 24.8 A" was **wrong** — that element is all outer copper. The failure is in the
**barrels**, not the pour.

### The placement gate exits 1

| gate | condition | result |
|---|---|---|
| G1 | phase corridor | PASS, 9.42 vs 8.972 (**+5 %**, vector 9.458, but 3.50 seed-pinned) |
| G2 | corridor ≥ 12.52 | PASS |
| G3 | 20.77 | PASS |
| G4 | no B.Cu parts | PASS |
| G5 | spreader footprint | **PASS BY DECLARATION** — 181.2 vs 181.2, a **text token checked against its own formula**; 314 cm² at 4.36 W/device |
| **G6** | **barrel count** | **FAIL — 14 barrels where 27 are needed; 9 where 17 are needed; and 24 of 48 sites were never measured** (`key is None: continue`) |
| G7 | FET junction | PASS, 101.4 °C |
| G8 | 19.8 % (a budget, not packing) | PASS |

**Exit 0 only at k = 0.048. At k = 0.024 it exits 1.**

So the earlier "exit 0" was **riding the constant that had been withdrawn 20 minutes earlier.** That is
the sixth time in this programme a green result came from a superseded input.

### The conclusion, and it is a design one

**Copper — not area — is the binding constraint, and the barrel count is limited by the shunt pads.**

**The shunt pads physically hold 17–18 barrels where 27 are required.** No amount of placement or
routing creates barrel sites that the footprint does not have. So the ESC needs one of:

1. **a part change** to a shunt with more pad area,
2. **a second shunt in parallel** per rail,
3. **a busbar** carrying the current past the shunt transition.

**This means the ESC cannot be made buildable by layout work at all.** The board needs a component-level
change before routing is meaningful — which is precisely why the owner's instruction to be careful with
placement first was right: routing would have burned weeks against a constraint no trace can satisfy.

### Also stale, caught by the verifier

- the gate's DRC figures were **413 pre-shrink**, not the current **253 / 113**.
- one wrong-k figure: `BATP_IN` 23.87 A (internal k applied to external copper).

---

### Objective assessment, per board

| board | DRC-clean | 0 unconnected | 0 geometry defect | validated package | no open cell | verdict |
|---|---|---|---|---|---|---|
| **Code-SDR V2** | **PASS** | **PASS** | **PASS** | **PASS** | **PASS** | **COMPLETE** |
| drone-arm rev_b | FAIL | PASS | FAIL | FAIL | PASS | blocked: **36 non-through vias** |
| ESC rev_b | FAIL | FAIL | FAIL | FAIL | PASS | blocked: **1,536–1,542 unconnected** |
| drone-mech | FAIL | PASS | FAIL | FAIL | PASS | blocked: **4 disjoint solids** |

**Tally: 25 PASS / 16 FAIL / 11 WAIVED of 52 cells. Checker exit 0, 6 of 6 mutations caught.**

### Code-SDR is complete

All five conditions pass. **4 fiducials on the committed board (HEAD `fbf2eca`), 377 footprints,
minimum gap 1.5005 mm = +0.2505 mm margin** — not the 0.0005 mm I flagged, because the fiducials were
placed at a proper clearance rather than barely clearing. Package manifest 20/20, `.pos` 377, BOM 373.
Two independent controls confirm the zero is real: "own rules 0 vs span-gate 36" varies one variable,
and **316 pads renumbered still gives 222/0**, so Code-SDR's zero is not an artefact of a clean rule
set. **Orderable: YES, 0 errors.** Assembly blocked only on 373 missing MPNs — sourcing.

### ESC: the LQFP pad shrink clears 69.5 % of the footprint blockers

The three footprint types, measured:

| type | part | footprints | pads | gaps | pad width needed | verdict |
|---|---|---|---|---|---|---|
| QFN-80 P0.4 | **U201 RP2354B** | 1 | 90 | 75 | 0.150 | **NOT a candidate** — 0.150 < the 0.200 mm terminal and below the 0.250 pattern floor |
| LQFP-48 P0.5 | **6 × STM32G431CBT6** | 6 | 288 | 258 | 0.250 | **candidate** — 0.250 > the 0.220 mm lead |
| USB-C 16P | **GCT USB4105** | 2 | 44 | 38 | 0.250/0.400/0.550 | **NOT a candidate** — 0.250 < the 0.300 mm contact |

**Executed: 288 LQFP pads shrunk 0.300 → 0.250 mm, length unchanged.**

**DRC at 4 oz / 0.25 mm: 523 → 253. GONE 270, ADDED 0.** That is 258 pad↔pad gaps at 0.200 mm plus 12
pad↔track at 0.225 mm, all LQFP. **258 of 371 cleared (69.5 %)** with **zero new violations.**

**113 remain and cannot be shrunk away** — QFN 75 and USB-C 38 — because their parts' land patterns do
not permit a narrower pad. Those need either a part change or an explicit fab rule exception. That is a
much smaller and more tractable problem than 413.

### drone-arm: the free-rider set is ZERO

I expected the owed respin to absorb some of the 36 vias. It absorbs **none**:

- **Zero vias sit on any 7th-channel net.** U10 pads 43–48 exist as **single-pad auto-nets carrying 0
  vias**, and `/ESC_PWM7` and friends **do not exist** in this variant.
- **None on `/CAN_5V`** — 2 pads, **0 vias**, and this variant has **no J60–J66 at all**.

So all 36 are **real layout work on preserved signals**. Distribution: **U10 15** (41.7 % — /LSM_INT1×2,
/RF_MOSI×2, /RF_MISO×2, /PA_EN×2, /3V3, /GNSS_RX, /HGM, /RF_GPIO0, /RF_GPIO2, /RF_RESET_N, /SENS_SCLK) ·
**U40 4** · C12, C32, C40, R10, R32, U21 **2 each** · C13, C38, C52, FB1, R22 **1 each**. **21 of 36 lie
within U10's bounding box +2 mm.**

Also found: **10 of the 36 have a declared type that disagrees with their actual layer pair** — 7
"microvia" span In1→B or F→In2, and 3 "blind" span only In2→B. By layer pair it is **29 adjacent / 7
spanning three layers.** So the declared types on this board are unreliable and span must be derived from
the layer pair, not read from the via type.

### drone-mech: interference is zero but the model is FOUR DISJOINT SOLIDS

The checklist's blocking number for drone-mech is not interference — it is **4 disjoint solids**. The
body is modelled as four separate solids (of 742,306.360 mm³, with 84.2 % bulk fill). **A single
manufactured part cannot be four disconnected bodies.** Interference being zero does not make it
printable or machinable.

So drone-mech has two separate defects: interference (solved, 0 genuine) and **topology (unresolved)**.

---

### Corrections: the fab-real DRC count is 621/631, and the rail margin is coefficient-dependent

**1. The DRC number a fab would actually see is 621 (631 all-track), not 523.** The 523 is what KiCad
**reports**; there is a **98-item population it cannot report at all** — sub-0.200 mm pad rings. The
verifier's independent split:

| class | count |
|---|---|
| **footprint-bound at 4 oz / 0.25 mm** | **413** (371 pad↔pad at 0.200 + 42 PTH rings) |
| **copper-bound** | **110** (43 clearance: 24 T↔T, 19 pad↔T; 28 via ring; 16 via diameter; 16 dangling; 4 width; 3 neck) |
| **pad rings KiCad cannot report** | **98** (140 total sub-0.200 rings, of which 42 are already counted above) |
| **reported total** | **523** (533 with `--all-track-errors`) |
| **fab-real total** | **621** (631 with `--all-track-errors`) |

Also confirmed from the verifier's own controls: at the board's **own rules the count is 16** — that is
the number most ESC reports were really describing. At **4 oz / 0.20 mm it is 102**. The clearance
report caps at **499** (proven with 550 and 1,000 pad pairs).

**2. The rail passes only on one IPC coefficient.** Reproduced independently: BATP 0.5242 → **23.09 A**,
BATN 1.4139 → **47.40 A**, re-poured 1.5082 → **49.67 A** (48 barrels), 1.9166 → **59.09 A**,
`BATP_IN` 1.428 → **47.74 A**, corridor 47.12 A.

**43.5 A is met at the stated 20 K basis with k = 0.048. At k = 0.024 the same copper gives 24.8 A.**
So the rail's adequacy is **coefficient-dependent**, and it should be stated with the constant, not as a
bare pass. Four further qualifications:
- **the re-pour exists only in evidence — the repo board is still at 23.1 A**
- it covers **cell 1 only**, not the other five rails
- the **corridor figure is inherited**, not re-measured
- at k = 0.024 the rail **fails** at 24.8 A against 43.5 A

**3. drone-arm's repo board has 36 non-through vias, not 15.** The verifier measured the board of record
directly: **341 vias, 36 non-through (33 microvia + 3 blind/buried), min drill 0.100 mm.** The **15 is the
`fanout3` work artefact**, not the repo file. Every reference to "15 vias" in this board should be read
as "15 on the best work artefact, **36 on the repo board of record**."

The conclusion does not change — both numbers are HDI, and both are unfixable by local edit — but the
repo board is **worse than the number that has been quoted**, and that has to be said plainly.

**4. Nothing regressed.** Verifier-confirmed on the ESC: 371 gaps, 140 rings, 687/687 on F.Cu, **0
non-through vias**, unconnected **1,542 → 1,536**. drone-arm work board byte-identical. Code-SDR
untouched.

**5. Protocol breach, mine:** two wave-10 reports correct this board without a BOARD CORRECTION line.
That is the same discipline I have demanded of every unit, and I should have applied it to the board
first. Corrected here.

---

### ESC rail re-pour: EXECUTED, and 43.5 A is met

| element | before | after | verdict |
|---|---|---|---|
| **BATN** | 1.4139 mm² = **47.40 A** | 1.9166 mm² = **59.09 A** | **×1.358 of the 43.5 A requirement** |
| `M1_BATP_IN` (pre-shunt) | 1.4280 mm² = **47.74 A** | unchanged to the digit | **×1.098** |
| **BATP** | 0.5242 mm² = **23.08 A** | **49.67 A** | **×1.142** |

**The rails are no longer the binding element.** The chain is `BATP_IN` **47.74 A** → `BATP` **49.67 A** →
`BATN` **59.09 A**, all above the **43.5 A** design current.

DRC went **523 → 524**, with a **pair diff of 5 added / 4 gone** and — the number that matters — a
**site diff of 0 new sites**: the fifth marker is a second marker at a pre-existing site. So the re-pour
created no new geometry defect.

The instrument was re-validated before any figure was believed: **19 controls PASS**, and it reproduces
every previously-published number to **≤ 0.07 %** (60 A/20 K width 13.981 mm, 96.991 mm at 0.0525,
45 barrels 47.39 A, BATP 0.5242 → 23.08 A, BATN 1.4139 → 47.40 A, one barrel 0.03142 mm²). That
reproduction is what makes the new numbers quotable.

### The 413-vs-523 discrepancy is settled: they were never the same population

**413 ∪ 110 = 523, verified as a row-level set diff** (common 413, gone 110, added 0) — not by
subtracting totals.

| figure | what it actually is |
|---|---|
| **523** | the **total** of the shipped routed board at 4 oz / 0.25 mm |
| **413** | the **footprint-bound subset** of that 523 — and separately the total of a *different, copper-free placement board* |
| **110** | the copper-bound remainder |

**The 110 is not "98 pad rings + 12".** It is: **28 via annular + 16 via_diameter + 16 via_dangling +
24 Track↔Track + 19 Pad↔Track clearance + 4 track_width + 3 zone neck.** The **98 pad rings are a third
population that KiCad cannot report at all** and they appear in neither total.

**Definitive ESC DRC baseline at 4 oz / 0.25 mm: 523 items** (533 with `--all-track-errors`), of which
**413 footprint-bound** and **110 copper-bound**, **plus 98 pad rings KiCad cannot report → effective
footprint-bound 511.**

Two traps confirmed and closed:
- **A `.kicad_dru` without `(version 1)` is silently ignored** — the result is **byte-identical to having
  no rule file at all.** Eight controls now prove the file loads.
- **Neither total is at a tool cap.** The clearance report caps at **499**, proven on a hand-checkable
  board; the 414 at 0.25 mm sits below it inside a monotone sweep.

### drone-arm: the 15 vias are unfixable by ANY structural patch, and that is now derived

**Zero of 15 cleared**, from six conversion trials placed on real boards and judged by `kicad-cli` DRC.

What makes the zero trustworthy is the **positive controls: three of the six trials came back
DRC-clean.** A legal 0.600/0.300 through via **does exist on this board** at **(65.550, 50.250)**, fed by
a legal 0.200 mm stub from `/3V3` pad 50, for **0 added violations and 0 unconnected.** The board simply
**cannot reach that site from any pad that needs a via.**

So this is no longer "we couldn't do it" — it is **"the board's topology cannot route these nets to a
legal through via."** drone-arm needs a **schematic-level respin**, not a layout patch, a net swap, or a
package change. That is the honest end state for rev_b.

---

### **THE AIRCRAFT DOES ~550 km/h, NOT 720.** And both CdA values were impossible.

**BOARD CORRECTION — supersedes the 60 A error AND the 16.8 A correction.** Both candidate CdA values
are **below the friction floor** and therefore cannot describe any real aircraft.

The verifier re-measured all **19 STEPs** with an independent OCP summation:

| quantity | value |
|---|---|
| wetted area S_wet | **0.7768 m²** (the unit's own 0.7789; agree per-part to the digit) |
| form factor, body | 1.525 |
| form factor, wing at x/c 0.30 | 1.341 |
| **independent buildup** | **0.004158** (the unit: 0.00416) |
| **friction floor** Cf·S_wet with zero form, interference or wave drag | **0.002710** |

**So CdA = 0.000693 is 3.9× below the friction floor and CdA = 0.0015 is 1.8× below it. Neither is a
possible aircraft.** The floor is the absolute minimum: skin friction alone, with every other drag
source set to zero. Both quoted values are *less than that.*

**Defensible CdA: 0.0034–0.0056 m², best 0.0042.**

### What that does to the current, and to the aircraft

| CdA | per-phase current | status |
|---|---|---|
| 0.000693 | 16.8 A | **impossible** — below friction floor |
| 0.0015 | 37.2 A | **impossible** — below friction floor |
| **0.0042 (best)** | **111 A rms** | the real drag-derived demand |
| range 0.0034–0.0056 | **88–154 A rms** | the defensible band |

**The aircraft supplies 43.5 A per phase.** So there is a **2.0–3.5× shortfall between what the
airframe's drag demands and what the power system delivers.** That is not an ESC problem and no PCB
change fixes it.

**The honest conclusion: at 43.5 A per phase the aircraft reaches roughly 545–570 km/h, not 720 km/h.**
720 km/h is unachievable with this power system, this propeller and this airframe. Every design figure
quoted at 720 km/h inherits that.

### The ESC decision, now settled

**Build 4 oz with the BATP/BATN re-pour.** As drawn, neither weight passes: **20.8 A (2 oz) and
23.1 A (4 oz) against a 40 A bus rail.** With the rail re-poured: **32.2 A (2 oz) against 47.1 A
(4 oz)**, i.e. **0.74× versus 1.08× of the 43.5 A requirement.**

**4 oz passes with 8 % margin. 2 oz does not pass at all.** So the answer to A/B is **4 oz plus the
rail fix** — and the earlier "2 oz is cheaper" conclusion was built on an impossible CdA and is
withdrawn.

The flip current **32.18 A** is arithmetically exact (22.89 A from 2 oz F.Cu + 9.29 A from 1.5 oz In2,
IPC-2221). But the "CdA under 0.00086 flips it to 2 oz" escape **cannot exist** — that CdA is **3.1×
below the friction floor.** So there is no branch in which 2 oz is correct for this airframe.

### Code-SDR: FIDUCIALS ARE NOW ON THE COMMITTED BOARD

**Verified from `git show HEAD:`, not from a copy:**

| check | result |
|---|---|
| footprints | **377** (373 + 4 fiducials) |
| `Fiducial:Fiducial_1mm_Mask2mm` | **4** |
| `FID` strings | **4** |
| clearance properties | **4** at `(clearance 1.5)` |
| references | **FID1, FID2, FID3, FIDL_U63_U64** at the claimed coordinates |

**DRC set diff: 0 added / 0 gone.** 222 → 222, **0 unconnected**, histogram identical — measured by the
verifier on both commits, not taken from the report.

**Package matches board: YES.** Manifest **20/20** against committed blobs, **`.pos` 377 rows**,
**BOM 373 rows**.

So **Code-SDR V2 is now genuinely orderable as a bare board**: 0 DRC errors, 0 unconnected, 0 non-through
of 1,085 vias, 4 fiducials with a real clearance, and a package that provably matches its board.
**Assembly remains blocked on 373 missing MPNs** — a sourcing task.

### One inconsistency left standing

**The ESC has no DRC set diff anywhere, and its two totals disagree — 413 against 523, a gap of 110.**
Both cannot describe the same board at the same rules. That needs resolving before the ESC's DRC count
is quotable.

---

### **THE 60 A WAS WRONG BY 3.6×.** Real per-phase current is 16.8 A RMS.

**BOARD CORRECTION — this supersedes every ESC decision made on a 60 A basis.** The 60 A figure was
never a phase current. **44.4 V × 60 A = 2.664 kW**, which is a *system* power figure for a **4-motor,
8 kg** aircraft, later relabelled as per-phase current. The board has **6** motors.

**Derived from drag, independently re-derived by the verifier:**

```
T  = ½ · 0.909 · 200² · 0.000693 = 12.60 N per motor
     × 6 motors = 75.6 N   against an 8 kg airframe weighing 78.5 N   ← consistent
P_d = 2,580.6 W
÷ 0.72 (prop)        = 3,584.0 W
÷ (0.90 · 0.97)      = 4,105.6 W   (motor · ESC)
÷ 44.4 V             = 92.5 A bus
÷ 6 motors           = 15.4 A per motor
÷ 0.92               = 16.8 A RMS per phase
```

Cited: `PHASE15_DESIGN_SPEC.md:244, :301, :337, :358`; `phase15_robu_final_config.py:114`;
`REV_B_ARCHITECTURE.md:18`; `FA4119_PROPULSION_DECISION.md:40-54`.

**Range: 14.7–22.2 A** (FOM 0.62–0.82 with a reconciled meanline), rising to **37.2 A** at the spec's own
CdA of 0.0015. **Binding assumption: CdA 0.000693 m², ASSUMED** — and it is the spec's own *"UNRESOLVED
#1 gate."*

**There is no motor map and no motor current rating anywhere in the repo** — `PHASE15_DESIGN_SPEC.md:305`
explicitly refuses to supply one. So this chain starts from **drag**, not from a motor datasheet. That
is a legitimate derivation, but it means the whole ESC sizing rests on a CdA that the design itself
flags as unresolved.

### What this does to every ESC conclusion

| prior conclusion | at 60 A | **at 16.8 A RMS (range 14.7–22.2)** |
|---|---|---|
| BATP In1 capacity 23.1 A | fails 2.6× | **passes at design point**, marginal at 22.2 A |
| BATN barrels 47.4 A | fails | **passes comfortably** |
| 2 oz max 22.9 A | fails | **passes at design point** |
| 4 oz max 48.0 A | fails | **passes with margin** |
| rail redesign needed | yes | **no — the rail is adequate** |
| 4 oz mandatory | yes | **no — 2 oz becomes viable, and 2 oz removes 413 footprint DRC items** |

So: **the ESC is not a 60 A board. It is a ~17 A board with a 37 A worst case.** The A/B question
changes again — and this time in favour of **2 oz**, because 2 oz clears the 413 footprint-bound DRC
items *and* its 22.9 A ampacity covers the design point with margin.

**Do not act on this until the CdA uncertainty is bounded** — 37.2 A at the spec's own CdA sits between
the two branches' capability (22.9 / 48.0 A). The answer genuinely depends on which CdA is right.

### The rate to use, going forward

**43.5 A per phase, not 60 A.** One unit's "hard ceiling" of **40.0 A** is a **bus** current printed in
a **per-phase** table; its phase equivalent is **43.5 A**. Every row that compared 22.9 A or 48.0 A of
phase ampacity against a 40 A bus overstated its margin — **4 oz's "1.20×" is really 1.10×.** The
verdicts survive; the multipliers do not.

### Code-SDR: the shipped board has NO FIDUCIALS AT ALL

The package shipped correctly — **22 files, all added, 0 modified, 0 deleted**, HEAD `1a20bd6` equals
the remote, tree clean, board still `309414D2`. An independent re-export reproduces **F_Cu, In1.Cu and
Edge_Cuts byte-identically**, with drills **1,213 + 2 G85 = 1,215** = 1,085 vias + 128 PTH + 2 NPTH,
4 layers, 373 footprints, **rev 2.1**.

**But the fiducial work never reached the repo board.** Measured: the repo board contains **0 `FID`
strings, 0 fiducial properties, 373 footprints.** The 1.2505 mm gap belongs to the **`fid9` copy** in
evidence. So:

- the old **"1.22 FAIL"** does not apply — that board is gone
- the new **"1.2505 PASS"** does not apply either — it is a copy, not the shipped board
- **the board being shipped has no fiducials, so it cannot be assembled**

This is the ship-blocking defect, and it is worse than either earlier verdict because both described
boards that are not the one going to fab.

### Checklist v4: 56/56 machine-derived, and one false claim inside it

56/56 cells machine-derived, **checker exit 0**. Two defects: §3.3's *"on the repo board the requirement
is met by +0.0005 mm"* is **false** for the reason above, and it carries **no BOARD CORRECTION line**
while contradicting `fab-cs-ship` §4 and this board. Also **Code-SDR col 12 states a 0.15 mm stroke**
where the measured value is **0.100** (101.6 + 0.15 = 101.75 ≠ 101.70), and its file count says **16**
where the commit added **22**.

### Confirmed clean

**ESC 1,990 of 1,990 vias through** (0 HDI). **drone-arm 336 vias = 321 through + 11 blind + 4 buried**
by span. **Code-SDR 0 non-through of 1,085.** ESC unconnected independently re-run: **1,542** via
`pcbnew`, not the 499 cap. Slots kept separate throughout: **CS 1,213 + 2**, **DA 360 + 4**. No
constraint violation on HDI, copper weight or spend.

---

### ESC verdict: neither branch reaches 60 A, and 4 oz is the cheaper one

**BOARD CORRECTION** — this replaces the earlier framing that A/B was a simple choice about footprint
geometry. Both branches were priced as full redesigns. Neither reaches the design current.

| | **2 oz** | **4 oz + packages** |
|---|---|---|
| footprint work | avoids only **U201** | **600 pads across 21 footprints** edited, **netlist invariant** |
| DRC at its own rules | 0 — but at **exactly the 0.200 mm fab floor, 0.0000 margin** | **413 → 87 measured** |
| area | **415.8 cm²** (larger, needs +3.35 mm pitch) | 382.71 cm² |
| routing | **full re-route**, **+3,528 vias** | existing route largely survives |
| rail | **loses 19 %** off the only rail fix — **49.7 → 40.2 A** | keeps it |
| **max current per phase** | **22.9 A of 60** | still short of 60 |
| verdict | **NO** | **NO** |

**So the answer to "A or B" is: 4 oz.** It is cheaper by every measure that matters — netlist
invariant, no re-route, keeps the rail fix at 49.7 A instead of losing 19 % of it, and 413 → 87 DRC
measured rather than 0-at-zero-margin. **2 oz avoids exactly one part (U201) and costs a full re-route
plus 3,528 unclassified vias.**

**But the bigger finding is that 60 A per phase is not achievable in this board either way.** 2 oz
tops out at **22.9 A**. So the ESC's premise needs revisiting before any more layout work: either the
real per-phase demand is lower than 60 A, or this form factor needs a different topology — more
parallel FETs, a heavier stackup, or more layers.

### Three false greens caught, and one is mine twice over

1. **The fiducial was actually FIXED and reported as failing.** `fab-cs-close` measured FID1/FID2 pour
   gap at **1.2505 mm** — passing 1.25 — while `fab-checklist-v3:486` still charged Code-SDR
   *"1.22 vs 1.25 FAIL"*. Same wave, opposite verdicts, unreconciled. So the 1.22 figure is stale and
   the checklist is wrong.
2. **A board that does not exist was reported.** `esc-branch-2oz:277` lists a 382.709 cm² rail-fixed
   board at 1,530 unconnected. No such artefact exists: the power-first placement has **0 tracks,
   0 vias, 0 zones**, and `railfix2` sits on a different board record.
3. **A DRC improvement omitted 98 pad rings.** `esc-branch-4oz:283`'s **"413 → 87"** leaves out the
   98 pad rings that KiCad's annular check skips. The real figures: checklist **523 → 629**, with
   **140 below 0.200 mm**, and DRC reporting **42**.

### Threshold notes

- No threshold was moved *upward* — the good news. But **2 oz's "0 DRC" passes at exactly 0.200 mm
  with 0.0000 margin**, which is a pass that carries no safety at all.
- `2oz:231` claims a fallback to project rules yields "110 drill". **False** — its own rules give **16**;
  the 110 is KiCad's 0.30 mm default appearing because that copy has **no `.kicad_pro`**.
- The probe reading 1.00 mm → **499** is hitting the **unconnected cap**, so "+483" is not a quantity.

### Capacity arithmetic that does reproduce

C1–C4 reproduce in `02_widths.log`: **0.4542 mm² → 20.8 A**, **1.4401 mm² → 48.0 A**. But 4 oz's
**8.56 mm** appears in no script or JSON, and `21_fcu_batp.json` measures **full_width 63.55 mm** where
the prose uses **67.5** — so the deficit is **114 mm², not 60**.

### The package recommendation is not sourced

4 oz recommends an **unnamed LQFP-100** — the datasheet fetch failed — and its "no equivalent" claim is
family-level only. The measuring unit says **one impossible part plus 23 footprint edits**, while
`2oz:332` and the checklist `:389` still say **"3 packages."** Those two statements cannot both stand.

### Code-SDR: bare-board yes, assembly no

- **Etch: orderable.** 222 warnings, 0 new, 0 gone — and **247 without the `.dru`**, which proves the
  rule file is being loaded.
- **Assembly: blocked.** **373 of 373 BOM rows have no MPN.**
- **The orderable package copy `8EC5741A` ≠ the repo board `309414D2`**, and **the repo holds zero
  packages.** So the package exists in evidence, not in the repo — the last mile is still open.
- `FIDL_U20_A` clears its requirement by only **0.014 mm**.

### Checklist: best-instrumented artefact in the programme

**52/52 cells, no blank, no TBD, checker exit 0, negative-tested 3 of 3.** Two weak cells: the
drone-mech column asking *outline + area* is answered with **solids**, and the ESC entry still carries
the placeholder token "1,542 unconnected".

---

### The rail, settled properly — and my own report did the PASS-over-FAIL thing

**BATP fails by 2.6×. BATN fails on its barrels. And the 2 oz option makes both worse.**

Verified independently (the verifier's own census reproduces the instrument's areas to the digit):

| net | layer | copper | topology | capacity |
|---|---|---|---|---|
| **BATP** | F.Cu | 1,217.29 mm² | **14 components, terminals NOT joined → 0 mm in series** | contributes nothing |
| **BATP** | In1 | 5,044.71 mm² | 1 component, min-cut **12.5–17.7 mm** | **23.1 A / 11.5 A → fails 59.05 A by 2.6×** |
| **BATN** | B.Cu | 5,231.22 mm² | 1 component, **14.1–20.0 mm** | plane **passes (101–143 %)** |
| **BATN** | — | — | **45 via barrels = 1.414 mm²** | **47.4 A** — the barrels are the limit, not the plane |

So **BATN's plane is adequate and its vias are not**, surviving only on an unmeasured one-third per-leg
sharing assumption. **BATP is simply short.**

**Why this reframes the whole A/B decision:**

| option | footprint DRC | power path |
|---|---|---|
| **A — 2 oz** | 413 items **disappear** (geometry already 2 oz-compliant) | **worse.** 2 oz is 0.07 mm, half of 4 oz — the rail that already fails at 23.1 A gets thinner |
| **B — 4 oz + 3 packages** | 413 items **fixed by package work** | **unchanged, still 23.1 A** |

**Neither option fixes the rail.** A removes the footprint blocker and doubles the copper problem; B
keeps the copper and costs three package changes. **The rail needs redesign under either**, so the A/B
question is about *footprint geometry and copper weight*, not about whether the ESC can carry 60 A —
it cannot, as drawn, either way.

### My own report committed the PASS-over-FAIL

`esc-area-honest` §0 states **"defensible 382.71 cm²"** while its own §3 says the demonstrable area
**"DOES NOT EXIST."** That is the same defect I have been flagging in other units for four waves, and
one of my agents did it.

Its **43.30 A** figure is also wrong: it adds a **pads-only gap** to a **series** element. BATP's real
capacity is **13.6–35.0 A** depending on the cut assumed.

Corrected statement: **382.71 cm² is the smallest placement with the 18 phases proven. It is not
demonstrable at 60 A, because no placement is.**

### Other corrections

- The corridor instrument's **min-cut returned flow 0 on both rails** (reversed sink edges) and was
  excluded from its own verdict — so **4.225 mm is a corridor width, not a cross-section.** Its
  `REPORT.md:245` saying "cross-section ≤ 4.225" is **inverted**: min-cut ≥ widest-path, confirmed by
  control K1 giving 8.100 against 5.100.
- `esc-battery-rail:328` calls the corridor directory **"absent"** — it is not. And its F.Cu
  **922.51 mm²** does not reconcile: its own parts sum to **1,262.24 mm²**.
- Phase widths differ between units: **7.600 / 3.700** in one report against **7.400 / 7.674** on the
  board. **Zero BOARD CORRECTION lines** were filed for any of these contradictions.
- The back-layer arm puts BATP on B.Cu **where BATN's plane already sits** — unchecked, so it is not
  yet a viable option.

### Clean, and worth stating

The rebuilt instrument **is verified correct in method** — `corridor_lib.py:102-138` reads pads,
tracks, vias and **zone fill** (`GetFilledPolysList`), with **0 unfilled zones across 4 boards.** No
constraint violations: **HDI 0 of 1,990 by span, single-sided 687/687, $0 spent, inners 0.0525 mm.**

---

### The battery rail FAILS, and the real binding constraint is the footprint rule

**Six independent rails, not one bus.** The netlist confirms **6 × BATP and 6 × BATN with no shared
trunk** (`REV_B_ARCHITECTURE.md:35-36`), so each rail carries **59.05 A** — not 360 A divided by
something. That changes the deficit by a factor of six and it was never noticed until the rail was
measured per-net.

**Measured at 59.05 A, ΔT 20 K, 4 oz = 0.14 mm outer / 1.5 oz = 0.0525 mm inner:**

| rail | copper it actually offers | capacity as built | **deficit** |
|---|---|---|---|
| **BATP** | F.Cu **0 mm in series**; In1 16.00 mm at 0.0525 mm | 0.5242 mm² = 3.74 mm of 4 oz | **−1.3904 mm² = −9.93 mm (27 % of requirement)** |
| **BATN** | B.Cu 38.00 mm at 0.14 mm | 1.4139 mm² = 10.10 mm | **−0.5007 mm² = −3.58 mm (74 %)** |

Required: **13.68 mm of 4 oz (1.9146 mm²)**, or **94.87 mm of 1.5 oz inner.**

**After an executed fix** (`esc_rev_b_railfix2.kicad_pcb`) it improves to BATP **1.5082 mm² (79 %)** and
BATN **1.7595 mm² (92 %)** — **still short 2.90 mm and 1.11 mm.** **RAIL PASSES: NO.**

### The honest area does not exist yet

Three areas are verified by two independent methods agreeing to **0.0000**: **491.732 / 370.119 /
382.709 cm².** But the **demonstrable** area — six phases proven, rail passing, 0 on B.Cu, DRC at the
correct rules — **DOES NOT EXIST. Two of those four conditions fail: the battery rail, and DRC.**

The range, with the binding constraint named:

| option | area | reduction vs 491.732 |
|---|---|---|
| X | −104.31 cm² | −21.2 % |
| Y | −105.98 cm² | −21.6 % |
| Z | −101.25 cm² | −20.6 % |
| back-layer arm | −109.02 cm² | −22.2 % |

**What to build: 382.71 cm², with BATP on the bare B.Cu plane**, after the 4 oz footprint decision.

### The binding constraint is NOT area — it is the 4 oz footprint rule

**413 DRC items on every candidate, and 100 % of them are footprint-bound.** No amount of placement
or routing clears them, because they live inside pad geometry. So the ESC's remaining problem is not
"make it smaller" — it is **the A/B decision**, and it always was.

### The heat spreader is outside the board and nearly doubles it

**MANDATORY** (60 A is 1.67× the board-only junction limit). Top-side over the TOLT tops, **outside
the board outline**, and **352–528 cm² at 250 W/m²K — that is 0.92× to 1.38× the board's own area.**
So the ESC's true packaging footprint is **roughly 735–911 cm²**, not 382.71. That is the number an
airframe bay has to accommodate, and it has never been stated before.

### Instrument discipline, finally working

The rebuilt corridor instrument carries **19 validation controls, all PASS** (`railmc.py`,
`06_validate.json`), and it measures foreign **copper** — tracks, vias, pads and **filled zone
polygons** — not foreign pads. It also refuses to sum a layer a net does not occupy, which is what
produced the fabricated B.Cu figure.

Area was measured by **two independent methods** (`GetBoardPolygonOutlines().Area()` and a shoelace
walk of Edge.Cuts loops) which agree to 0.0000 on all three boards.

One more fact worth carrying: **the power-first placement has 0 tracks, 0 vias, 0 zones.** It is
placement only. Any claim about its routability was necessarily about a board with no copper on it.

---

### ESC: 60 A is the documented design current — and it needs a heat spreader

**60 A per phase is not an assumption. It is written down:** `REV_B_ARCHITECTURE.md:18` — *"60 A
continuous design current per motor channel"*, `:19` 360 A total. The IPTC014N10NM5 datasheet was
verified verbatim: **1.4 mΩ at 10 V, Tj 175 °C, RthJA 40 / 62 °C/W.**

**But the board alone cannot carry it.** The thermal solve gives:

| RthJA | current at TA 45 °C |
|---|---|
| 22.4 °C/W | **52.0 A** |
| 40 °C/W | 35.9 A |
| 62 °C/W | 26.8 A |

So **60 A is 1.67× the board-only junction limit.** A **heat spreader is mandatory** — that is a
design requirement, not a defect, and it means the ESC's packaging answer must include the spreader.

The other bounds are comfortable: the shunts dissipate **1.8 W of 10 W**, and the sense chain has
headroom to **145 A** saturation. So the binding limit is thermal, not sensing.

### Three areas are in circulation and none is yet demonstrable

| area | status |
|---|---|
| **491.73 cm²** | original — routable, certainly oversized |
| **382.71 cm²** | power-first: phases PASS at 7.400 / 7.674 mm against 6.991 — but **the battery rail is unproven** |
| **370.12 cm²** | compacted: **UNSAFE**, power path 2.0–4.7× short |

**382.71 cm² is the smallest area with the 18 phases proven.** It is not quotable as the answer,
because the battery rail has never been honestly measured — see below.

### The corridor instrument printed a PASS over its own −80 % FAIL

Three defects in the one tool every battery-rail conclusion rested on:

1. **Its own output returns `BATP 1.400 mm` (−80 %) and `BATN "no path"`** — while the summary table
   calls **7.400 mm the "narrowest"** and marks the rail **PASS**. A PASS printed over its own FAIL.
2. **It adds "B.Cu 9.5 mm" to BATP's cross-section for a net with ZERO copper on B.Cu.** Measured:
   F.Cu 869.17 mm², In1 5,039.01 mm². The real deficit is **1.761 mm², not 0.431**, and the In1 neck is
   **33.55 mm, not 8.21**. **The instrument fabricated copper.**
3. **It counts only foreign PADS** (`08_corridor_bottleneck.py:25-33`), so "corridor" is not the
   "foreign copper" that its own §10 claims to measure.

So the battery rail is **unproven, not passing**. A replacement instrument is being built that
measures all copper — tracks, vias, pads and **filled zone polygons** — per layer, with a sanity check
against a known-good measurement before any of its output is trusted.

### What was confirmed clean

- **HDI counts reproduce exactly** by span: drone-arm **15** (11 blind + 4 buried), repo 36, **ESC 0 of
  1,990**, **Code-SDR 0 of 1,085.** Package: 5 blind/buried files, 15 holes, 360 drills + 4 G85 slots
  = 364 hits.
- **ESC unconnected 1,542** (pcbnew, uncapped); the `kicad-cli` 499 is a cap and appears in all three
  rule runs, which is exactly how a cap should look.
- **drone-arm and Code-SDR are 0 unconnected** on both tools.
- **The respin free-rider claim is justified**: 4 riders shown, 3 non-riders explicitly refused, and
  the converted board came out **byte-identical** (kept 0 of 10 attempts).
- **Checklist v1: 52/52 cells, no blank and no TBD**, checker exits 0. **One cell is wrong:** the
  drone-mech "surface finish" cell is answered with a **mass**, and should be WAIVED — so it is 1/3/9,
  not 2/3/8.
- **No constraint violation** on HDI, 4 oz, spend ($0) or single-sidedness (**0 footprints on B.Cu**;
  43 THT pads legitimately span both layers).

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
