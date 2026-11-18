# body-fab-assumptions — CORRECTIVE wave

**Assignment:** the fabbability verdict rests on a nozzle diameter the repo never states, and on
ignoring the CF-wrap ply minimum. Fix the assumptions so the manufacturability conclusion is real.

**Verdict, up front.** The premise of the defect is *half* right, and correcting it makes the
conclusion **worse** for the previous wave, not better:

1. The repo **does** state its process, its printer, its bed **and its nozzle** — 0.4 mm, in a saved
   OrcaSlicer machine profile, with two slices actually run on it. So "the nozzle is invented" is
   **wrong**: 0.4 mm is sourced, and 0.42 mm is the repo's own saved **outer-wall line width**
   (1.05 × 0.4). The previous wave's failure was not inventing a nozzle; it was never finding the
   one the repo pins, then calling it UNVERIFIED while using it (`body-mass-opt/REPORT.md:354`).
2. The **real** defect is worse: **0.80 mm is not an integral loop count at any of the three
   nozzles** (0.87 / 0.63 / 0.84 mm), and — decisively — **0.8 mm cannot be a total wall at all**
   on this design, because the CF/glass ply stack alone is **0.591–0.775 mm** and the remaining
   "core" would be **0.099 mm = 0.49 of a single 0.20 mm printed layer**.
3. Therefore **"fabbable without a process change" does not hold**, on either route, and the repo's
   own screen already says `BLOCKED` (`phase15_manufacturability_screen.md:3`).
4. The bed conflict is real and quantified: the repo asks for **≤260 mm FDM pieces** on a
   **180 mm** bed — **80 mm over, 1.44× the bed** — and the 640 mm body needs **4 pieces, not 3**.

Nothing here is a SOLVER result. There is **no solver tier in this unit at all**; every number is
MEASURED from a file or ANALYTICAL from a stated closed form. That is stated once here and not
re-litigated per row.

---

## 0. Method, tiers, and what I did not do

**Provenance tiers used**

| tier | meaning in this report |
|---|---|
| **MEASURED** | read from a file in the repo or in a sibling evidence dir, at a cited `file:line` |
| **ANALYTICAL** | closed form on MEASURED inputs, formula stated |
| **ASSUMED** | an input with no source in the repo; always swept or bracketed, never a result |
| **SOLVER** | *not used in this unit* |

**Citation discipline.** Every `file:line` in this report is machine-checked by
`scripts/00_verify_citations.py`, which reads the cited line and fails if the expected string is not
there. **83/83 verified.** This is the same failure mode as `pdf:113` (D7): a previous unit attributed
a claim to `AGENT_BOARD.md` that does not exist. I therefore do not trust a citation I have not read.

**Not re-done** (instructed credible): shell volumes (742,305.5 mm³), the 3e-3 agreement across four
code paths, bore 41.47 mm against 42.5 mm, the 1.03 mm clearance at 83 of 125 stations, the 2 µm
web *as an upper bound*, CRLF pins, and the total absence of solver-tier drag. The forebody meridian, the duct-land
widths and the exported shell bbox are **reused** from `body-aero-shape`, `body-manufacture` and
`body-bounds` and re-cited, not re-derived.

**Scope fence.** I wrote only inside `evidence/body-fab-assumptions/`. No repo file was written, no
git operation was performed, no `audit/*` branch was touched.

---

## 1. The process the repo actually assumes — **STATED**, three routes

The claim under test is "the repo never states a nozzle / a process". Both halves are false.

### 1.1 FDM route — the body shell's core. Fully pinned, down to loop counts.

| what | value | source |
|---|---|---|
| printer | **Bambu Lab A1 mini** | `phase15_manufacturability_screen.json:695` (`"selectedPrinter": "Bambu Lab A1 mini (user-stated)"`), `:248` `"printer_model"` |
| **nozzle** | **0.4 mm** | `effective-machine.json:6` `"nozzle_diameter"`, `:9` `"printer_variant": "0.4"`, `slice_manifest.json:161` `"nozzleDiameterMm": 0.4` |
| **line widths** | outer **0.42**, inner **0.45**, first layer **0.50** mm | `effective-process.json:76`, `:45`, `:40` |
| **wall loops saved** | **2** | `effective-process.json:170`, `slice_manifest.json:163` |
| layer height | 0.20 mm | `effective-process.json:66` |
| bed | **180 × 180 × 180 mm** | `effective-machine.json:221-225` (`printable_area` polygon `0x0 … 180x180`) and `:125` (`printable_height 180`); sourced by the repo to Bambu's spec sheet, `phase15_manufacturability_screen.json:693` |
| filament / plate | Bambu PLA Basic, textured PEI, 220 °C / 65 °C | `slice_manifest.json:169-172` |
| slicer actually run | **OrcaSlicer 2.4.2, `return_code: 0`** | `print_subset_slice/README.md:3`, `manufacturing-software-screen.md:9` |

**This is a stronger footing than the previous wave believed.** It is not a brand-name inference: a
saved machine+process profile exists **and two hash-pinned STEP parts were sliced with it**. The
0.4 mm is not a guess about what an A1 mini ships with.

### 1.2 Composite route — the skin. Also fully pinned.

| what | value | source |
|---|---|---|
| construction | printed PLA core + **hand CF/glass layup**, *not* CNC | `phase12_fixed_powertrain_design.json:197` |
| core | **1.2 mm PLA** | `:203` `"PLAcoreMm": 1.2`; `phase12_release_report.md:19` |
| per face | **200 gsm CF + 100 gsm glass** | `:204`, `:205`; `phase12_release_report.md:19`; `phase13_cad_cam_report.md:62` |
| resin : fibre | **0.8** by mass | `:206` |
| laminate area / mass | 0.415152 m² / 0.224182 kg | `:207`, `:209` |
| parameter box | CF 160–200–240 gsm, glass 60–100–150, plies/face 1–2–3, r:f 0.6–0.8–1.0, **shell 0.8–1.2–2.0 mm** | `PHASE15_DESIGN_SPEC.md:438-442` |
| shell thickness band | 0.8 – 1.2 – 2.0 mm, "PLA core + CF wrap" | `HANDOFF_GEOMETRY_AGENT.md:108` |
| **ply overlap** | **≥ 10 mm** | `HANDOFF_GEOMETRY_AGENT.md:177` |
| **duct wall floor** | **1.5 mm** (range 1.5–2–3) | `PHASE15_DESIGN_SPEC.md:173` |
| PLA density | 1240 kg/m³ | `phase12_generate.py:69` |

The repo's own manufacturing note states the build plan and the split in one line: *"Body and wing
are modeled as 1.2 mm skins over cold-side PLA core … section the master at those planes into
**≤260 mm FDM pieces** and use sealed scarf/flange joints … Main shell and wing use composite wrap"*
(`phase15_geometry_manufacturing_report.md:18`).

### 1.3 CNC route — **not applicable to the body**.

The repo does run a CNC route, but only for rotor/stator/hub blanks in 6061: GRBL controller,
**nominal 300 × 180 × 40 mm travel**, 2 mm carbide roughing
(`phase10_edf_fuselage_cam_release_notes.md:43`), machine identifier `233018 Pro`
(`phase15_manufacturability_screen.json:711`). The repo is explicit that the shell is **not** on this
route: *"composite shell parts are printed PLA plus hand layup, not 6061 plate CNC"*
(`phase12_fixed_powertrain_design.json:197`), and the CAM notes warn *"Do not use these files on
carbon fibre"* (`phase10_edf_fuselage_cam_release_notes.md:47`).

**So the body shell has exactly two candidate processes: FDM (core) and hand layup (skin). They are
not alternatives — the design *is* the combination.** That is what makes the "either/or" nozzle
argument from the previous wave unusable, and it is what makes item 4 below fail.

---

## 2. The CF-wrap route: ply stack, minimum wall, minimum ply radius

### 2.1 The ply stack is a computable number, and it is not 1.2 mm

Cured ply thickness from areal weight and resin:fibre mass ratio (closed form, ANALYTICAL):

```
t_ply = w_fibre/rho_fibre + (R * w_fibre)/rho_resin          [g/m2 / (g/cm3 * 1000) -> mm]
```

with `rho_CF 1.80`, `rho_glass 2.54`, `rho_resin 1.20` g/cm³ (**ASSUMED**, standard values — the repo
states areals and a ratio but never a thickness). Over the repo's **own** parameter box:

| case | CF | glass | r:f | t_CF | t_glass | one face | **two faces** | laminate ρ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MIN | 160 | 60 | 1.00 | 0.2222 | 0.0736 | 0.2958 | **0.5917 mm** | 1487 |
| **NOMINAL** | **200** | **100** | **0.80** | **0.2444** | **0.1060** | **0.3505** | **0.7010 mm** | **1541** |
| MAX | 240 | 150 | 0.60 | 0.2533 | 0.1341 | 0.3874 | **0.7748 mm** | 1611 |

*(ANALYTICAL on MEASURED areals, `PHASE15_DESIGN_SPEC.md:438-441`; densities ASSUMED. Sensitivity:
ρ_CF ±0.05 → 1.76 % of the stack; ρ_resin ±0.05 → 4.76 %; ρ_glass ±0.05 → 0.44 %. The stack is
0.685–0.718 mm for all plausible densities, so nothing below turns on the constants.)*

**Independent cross-check that the stack is right.** 540 g/m² per face × 0.415152 m² = **0.224182 kg
vs the repo's 0.224182 kg — 0.000 %**. And the same areal weight at the wave's 1550 kg/m³ gives
`t = 540/1550 = 0.3484 mm`, within **0.60 %** of the 0.3505 mm derived from material densities.

Two consequences I will not overclaim but should not hide:

- **1550 kg/m³ is the solid cured laminate density**, and 150 kg/m³ is the bulk density of the whole
  sandwich. That is the physical origin of the D1 contradiction, and it means the mass agent's
  volume→density pairing can be checked against this stack. *Density assignment is that agent's lane;
  I record the cross-check only.*
- The wall the mass work calls "1.2 mm at 1550" is, as designed, **1.2 mm core + 0.7010 mm laminate =
  **1.901 mm**, areal mass **2.028 kg/m²** against the mass work's 1.860 kg/m² (**×1.09**).

### 2.2 Minimum wall: the ply stack sets a floor the 0.8 mm target cannot reach

Wall = ply stack + core. The question "can 0.8 mm be a wall?" reduces to "is there core left?":

| target total wall | layup | laminate | core left | **core in 0.20 mm layers** | printable? |
|---|---:|---:|---:|---:|---|
| **0.8 mm** (mass work thinning) | min | 0.5917 | 0.2083 | **1.04** | one layer — a core in name only |
| **0.8 mm** | **nominal** | **0.7010** | **0.0990** | **0.49** | **NO** |
| **0.8 mm** | max | 0.7748 | 0.0252 | 0.13 | **NO** |
| 1.2 mm (mass work Item 1) | nominal | 0.7010 | 0.4990 | 2.50 | yes, but a 0.5 mm core, not 1.2 |
| 2.0 mm (spec max) | nominal | 0.7010 | 1.2990 | 6.50 | yes |
| 1.5 mm (duct floor) | nominal | 0.7010 | 0.7990 | 4.00 | yes |

**The number the assignment asks for: the minimum wall of a two-face CF/glass wrapped panel is
0.591 mm (minimum layup, zero core) to 0.775 mm (maximum layup, zero core) — nominally 0.701 mm of
laminate before any core exists.** A 0.8 mm total wall therefore leaves **0.099 mm of core at the
nominal layup, which is 0.49 of a single 0.20 mm printed layer**. You cannot print half a layer, so
**0.8 mm is not a wall this construction can have.**

Note the layer-height criterion uses the repo's own `0.20 mm` (`effective-process.json:66`), so it
adds no new assumption.

### 2.3 Minimum ply radius: the repo states none, and the geometry offers r = 0

**The repo does not state a ply radius anywhere.** The only related tolerance is **ply overlap
≥10 mm** (`HANDOFF_GEOMETRY_AGENT.md:177`). So the radius must be derived, and I state the derivation
rather than a number:

```
outer-fibre bending strain   eps = t / (2R)     ->     R_min = t / (2 * eps_allow)
```

| eps_allow (ASSUMED) | R_min, CF ply (t = 0.2444) | R_min, glass ply (t = 0.1060) |
|---|---:|---:|
| 0.5 % (no matrix cracking) | **24.44 mm** | 10.60 mm |
| 1.0 % | **12.22 mm** | 5.30 mm |
| 2.0 % (permissive) | **6.11 mm** | 2.65 mm |

Adopt the most permissive value — **6.1 mm** — and the wrap still fails, because the body offers
**zero-radius** features by construction:

- **The forebody meridian is a faceted cone, not a curve.** The half-angle runs in discrete bands —
  **69.0°** (z −360…−355), **60.9°** (−350…−335), **45.0°** (−330…−305), **0.0°** (−300)
  (`body-aero-shape/scripts/loft_occ.json:18`, `:28`, `:48`, `:78`) — with the tip closing to a
  1.0 mm half-width (`:17`). Each band boundary is an **r = 0 crease** in the meridian, i.e. exactly
  the direction the ply must turn.
- **Hatch aperture: 90° cut through the 1.2 mm skin, edge radius 0**, no flange or land
  (`body-manufacture/REPORT.md:129`).
- **Side-port bore intersects the skin at a zero-radius edge**, and there is 0 mm bond land
  (`body-manufacture/REPORT.md:135-138`).
- **The 2 µm web** (`body-baseline/REPORT.md:202`) leaves no room for even one ply —
  `body-baseline/REPORT.md:228` already said so, and my stack number says it is **1/122nd of one ply**.
- **The duct land is 0.647 mm at z = −60 and 0.000 mm at 83 of 125 stations**
  (`body-manufacture/REPORT.md:121-122`), against the repo's own **1.5 mm duct-wall floor**
  (`PHASE15_DESIGN_SPEC.md:173`) — and the duct is the one part the repo assigns to *hot-side CF
  composite* (`phase15_geometry_manufacturing_report.md:19`). 0.647 mm is **2.65× one CF ply** but
  **0.43× the floor**; where it is 0.000 mm no ply exists.

A ply at an r = 0 crease must either bridge (void) or be **gored/darted**, and each gore is bought
with the overlap the repo does specify. **The 1.2 mm wrap is not a drapeable skin on this loft; it is
a cut-and-overlap panel set that has not been designed.**

### 2.4 What this does to the walls the mass work wants to thin

The mass work's items 3 and 4 remove 0.4 mm from a **1.2 mm solid at 1550 kg/m³**. On the actual
sandwich, thinning the wall thins the **core**; the laminate — the part that carries the bending
stiffness — is untouched by a core change. Re-costing its own band area (51,613 mm², back-solved from
its quoted 32 g):

| item | mass work | on the real sandwich | why |
|---|---:|---:|---|
| 3, thin \|y\| < 0.5b 1.2 → 0.8 | −32.0 g | **−25.6 g** | only the 1240 kg/m³ core goes, not 1550 |
| 4, extend to \|y\| < 0.75b | −25.0 g | **−20.0 g** | same factor 1240/1550 = 0.80 |
| quoted ΔZx for the pair | −4.2 % | **not the penalty of removing core** | the laminate is not thinned |

And if "0.8 mm" is meant as the **total** wall, §2.2 shows it is not manufacturable at all, so the
saving is not 32 g — it is unbuildable.

**If the two thinning items are ever reinstated they are worth 45.6 g, not 57 g, and they no longer
carry the ΔZx claim that justified them.**

---

## 3. The FDM route: results as a function of nozzle

The repo pins the nozzle at 0.4. But the assignment is right that the *conclusion* should not hang on
one number, so here is the dependence. The width law is **not assumed** — it is read back off the
saved 0.4 profile and reproduces it exactly:

| width | law | 0.4 mm calc | repo | |
|---|---:|---:|---:|---|
| outer wall | 1.05 × N | 0.4200 | 0.4200 | **MATCH** (`effective-process.json:76`) |
| inner wall | 1.125 × N | 0.4500 | 0.4500 | **MATCH** (`:45`) |
| first layer | 1.25 × N | 0.5000 | 0.5000 | **MATCH** (`:40`) |

Extending that same law to 0.6 / 0.8 is an **ASSUMED** extrapolation (stated); the 0.4 column is
MEASURED.

### 3.1 Achievable integral wall thicknesses (mm)

| loops | **N = 0.4** | N = 0.6 | N = 0.8 |
|---|---:|---:|---:|
| 1 | 0.420 | 0.630 | 0.840 |
| **2** (the repo's saved setting) | **0.870** | **1.305** | **1.740** |
| 3 | 1.320 | 1.980 | 2.640 |
| 4 | 1.770 | 2.655 | 3.540 |

### 3.2 Nearest achievable wall to the two targets that matter

| target | N = 0.4 | N = 0.6 | N = 0.8 |
|---|---|---|---|
| **0.80 mm** (mass work thinning) | **0.870 (+8.7 %)** | 0.630 (−21.3 %) | 0.840 (+5.0 %) |
| 1.20 mm (Item 1 wall / shell nominal) | 1.320 (+10.0 %) | 1.305 (+8.7 %) | 0.840 (−30.0 %) |

**Result: 0.80 mm is not an integral loop count at *any* of the three nozzles.** The best fit is
0.87 mm at N = 0.4 — which is the repo's own 2-loop setting. So:

- `body-mass-opt/REPORT.md:353` — *"0.8 mm is exactly two 0.4 mm perimeters"* — is **wrong by
  0.07 mm (+8.7 %)**: two of the profile's loops are `0.42 + 0.45 = 0.87`, not `2 × 0.40 = 0.80`.
- `body-manufacture/REPORT.md:120` — *"1.2 mm = 3 × 0.4 mm perimeters, printable"* — is **wrong by
  0.12 mm**: three loops on the saved profile are `0.42 + 0.45 + 0.45 = 1.32`.
- `body-manufacture/REPORT.md:122` — *"0.42 mm line width gives 0.84 mm for two lines"* — uses the
  outer width twice; the profile has an inner width of 0.45, so two loops are 0.87.
- Both would become exactly right only by switching the slicer to variable-width (Arachne) fill, and
  **the saved profile's wall generator is not pinned in the manifest**. That is a process change,
  which is the thing item 4 is about.

### 3.3 Minimum resolvable feature vs the tolerances that depend on it

| nozzle | one bead | tolerance 0.3 mm in beads (`handoff:177`) | tip clearance 0.5–1.0 mm in beads (`handoff:175`) |
|---|---:|---|---|
| 0.4 | 0.42 mm | **0.71 bead — sub-bead** | 1.19–2.38 beads |
| 0.6 | 0.63 mm | **0.48 bead — sub-bead** | 0.79–1.59 beads |
| 0.8 | 0.84 mm | **0.36 bead — sub-bead** | 0.60–1.19 beads |

**Duct roundness ≤0.3 mm is finer than one extrusion bead at every nozzle in the table.** Careful
about what this is: the bead ratio is an **order-of-magnitude** argument (ANALYTICAL), **not** a
measured printed roundness. It says the tolerance is finer than the process can express by
construction; settling it needs a printed-part measurement or a different process. What it does
establish is that **no nozzle choice rescues the tolerance** — the ratio moves 0.71 → 0.36, i.e. it
gets worse, never better.

### 3.4 Does a 0.8 mm nozzle ever conflict with the CF-wrap ply minimum? — **Yes, three ways**

1. **It cannot print the part that is composite.** The duct land is **0.647 mm** at z = −60; a 0.8
   nozzle cannot lay a bead thinner than **0.84 mm**. The 0.647 mm land is unprintable at 0.8 nozzle
   *and* under the 1.5 mm floor.
2. **Its bead is thicker than the entire ply stack.** One 0.8 nozzle bead is 0.84 mm against a
   0.701 mm two-face laminate (**0.83 beads**). Where the core is one bead, "1.2 mm core + wrap" has
   no core geometry to wrap.
3. **It abandons the wrap without saying so.** A 0.84 mm printed wall *is* the finished wall on the
   0.8-nozzle route, so the CF/glass plies in `PHASE15_DESIGN_SPEC.md:438-442` are no longer part of
   the part. That is a construction change, not a nozzle change — see §4.

---

## 4. Does "fabbable without a process change" hold? — **No. It fails on both routes.**

The claim is `body-mass-opt/REPORT.md:354`: *"0.8 mm is exactly two 0.4 mm perimeters on the specified
Bambu A1 mini, so it is fabbable without a process change; the printer's nozzle size is not stated in
the repo and that is UNVERIFIED."*

| # | test | result |
|---|---|---|
| 1 | Is the nozzle stated? | **Yes** — 0.4 mm, saved profile + two executed slices (§1.1). The clause "not stated in the repo" is **false**. |
| 2 | Is 0.8 mm two perimeters? | **No** — 0.87 mm on the owned profile; 0.80 is off-lattice at 0.4/0.6/0.8 (§3.2). |
| 3 | Is 0.8 mm a legal **total** wall? | **No** — core left is 0.099 mm = **0.49 of one layer** (§2.2). |
| 4 | Can the body be printed as one part? | **No** — 640 mm on a 180 mm bed needs **4 pieces / 3 joints**; the repo's own note asks for a split with *"sealed scarf/flange joints"* (`phase15_geometry_manufacturing_report.md:18`). A split **is** a process change. |
| 5 | Is the wrap drapeable? | **No** — r = 0 creases and a 2 µm web (§2.3). |
| 6 | What does the repo's own screen say? | **`BLOCKED`** — *"BLOCKED machine-specific CAM and FDM feasibility. Fabrication release is not supported by this screen"* (`phase15_manufacturability_screen.md:3`), and `:38` says FDM feasibility **"remains blocked despite the user-stated printer"**. `:44`: *"Do not infer fabrication readiness from STEP validity or this screen."* |

**The verdict inverts.** It is not "fabbable without a process change"; it is **not fabricable as
designed on either route, and the repo already recorded that**. The only honest version of the
previous sentence is: *"a 0.87 mm printed wall is producible on the owned profile; the body it belongs
to is not."*

Cost of the mandatory split, for completeness (ANALYTICAL, §5): each joint consumes **10 mm of ply
overlap on two faces = 2,941 mm³ = 4.53 g** of laminate; at 3 joints that is **+13.6 g**, against the
**45.6 g** the two thinning items are actually worth (§2.4). **The joints eat 30 % of the thinning.**

---

## 5. Bed size vs the piece sizes proposed — a hard contradiction

### 5.1 The two beds the repo assumes

| bed | dims | source |
|---|---|---|
| Bambu A1 mini (the selected printer) | **180 × 180 × 180 mm** | `effective-machine.json:221-225` (`printable_area`) and `:125`; `phase15_manufacturability_screen.json:696-697`; Bambu official specs, `:693` |
| 3018-class CNC (blanks only) | 300 × 180 × 40 mm | `phase10_edf_fuselage_cam_release_notes.md:43` |
| **envelope the spec demands of the CNC** | **≥ 320 × 140 × 45 mm** | `PHASE15_DESIGN_SPEC.md:460` |

**The CNC is short too:** the spec demands ≥320 mm of X and its own nominated machine travels 300 mm
(**20 mm short**), and ≥45 mm of Z against 40 mm (**5 mm short**). That is a second bed contradiction,
independent of the printer.

### 5.2 The contradiction the assignment asks about

| piece | length | pieces at 180 mm | pieces at the repo's 260 mm | repo's 260 mm vs 180 mm bed |
|---|---:|---:|---:|---|
| fuselage master shell | 640.0 | **4** | 3 | **OVER by 80 mm** |
| wing span | 520.0 | **3** | 2 | **OVER by 80 mm** |
| wing sector STEP | 498.607 | **3** | 2 | OVER by 80 mm |
| exported shell (X) | 194.037 | 2 | 1 | OVER by 80 mm |

**260 mm is 1.44× the bed.** The repo's own geometry note asks for *"≤260 mm FDM pieces"* and *"two
260 mm panels"* (`phase15_geometry_manufacturing_report.md:18`) on a printer with a 180 mm bed — a
**80 mm contradiction**, and it under-splits the body by at least one piece (**4 needed, 3 implied**).

The repo is aware of part of this: `phase15_manufacturability_screen.md:34` already records that *"the
geometry notes describe a 640 mm master divided into sections up to 260 mm"* while the exported shell
is only 194.04 mm, and `:35` records that the shell *"direct fit fails one axis"*. My contribution is
the arithmetic: **80 mm over, 1.44×, 4 pieces not 3.**

### 5.3 Rotation cannot rescue it

A 180 mm cube holds two points at most `180√3 = 311.769 mm` apart — the repo's own 311.77 figure
(`phase15_manufacturability_screen.md:35`). Any part with two points further apart fails in **every**
orientation, and a tight bbox extent `E` guarantees two part points `E` apart:

| part | span | vs 311.769 mm | verdict |
|---|---:|---|---|
| body of record | 640.0 | **2.05×** | **cannot fit at any rotation** |
| wing sector | 498.607 | 1.60× | cannot fit at any rotation |
| wing centre bridge | 425.054 | 1.36× | cannot fit at any rotation |

For the **194.037 mm exported fragment** the answer is narrower. Axis-aligned it is **14.037 mm over**
(agreeing with `body-bounds/shell_bounds_measurement.json:148`, 14.036971). Its bounding **box** needs ≥ **190.986 mm** in any
rotation (brute-force SO(3) search, 3° net + refinement), so the "just rotate it in" escape is closed
for its envelope — but since the part lies *inside* its box, that does **not** prove the curved shell
cannot fit, and I do not claim it does. It is moot anyway: that file is a 194 mm slice of a 640 mm
body.

### 5.4 One more volume check

The shell's material volume is 742,305.5 mm³ = **0.742 L**, against the spec's own print-volume band
**0.5 – 0.7 – 1.0 L** (`PHASE15_DESIGN_SPEC.md:465`) — **above nominal, inside max**. A single shell
already exceeds the nominal budget before joints, brim or supports.

---

## 6. Board check

`AGENT_BOARD.md` is grepped for `nozzle | Bambu | FDM | layup | bed size | CF wrap | ply` and carries
**no line on the drone body's process, nozzle, ply stack or bed**. Nothing on the board is wrong here,
so **no `BOARD CORRECTION:` is owed by this unit**.

Consequence for **D7**: any wave text that attributes a nozzle, a bed or a ply figure to
`AGENT_BOARD.md` is citing a line that does not exist. The board's drone-mech content is the 3D corpus
and its speedups (`AGENT_BOARD.md:215-222`).

---

## 7. What this changes in the wave's verdict

| previous | corrected | tier |
|---|---|---|
| "nozzle not stated in repo, UNVERIFIED" (`mass:354`) | **0.4 mm stated** in the saved profile, two slices run; 0.42 is the saved outer-wall width | MEASURED |
| "0.8 mm is exactly two 0.4 mm perimeters" (`mass:353`) | **0.87 mm**; 0.80 is off-lattice at 0.4/0.6/0.8 | ANALYTICAL |
| "1.2 mm = 3 × 0.4 perimeters" (`mfg:120`) | **1.32 mm** on the saved profile | ANALYTICAL |
| "0.42 gives 0.84 for two lines" (`mfg:122`) | **0.87** (inner wall is 0.45) | MEASURED |
| "fabbable without a process change" (`mass:354`) | **does not hold**; split is mandatory, repo says `BLOCKED` | MEASURED |
| implicit "1.2 mm skin" | **1.901 mm sandwich** (1.2 core + 0.701 laminate), 2.028 kg/m² (×1.09) | ANALYTICAL |
| thinning worth −57 g | **−45.6 g**, and ΔZx claim not transferable | ANALYTICAL |
| "≤260 mm pieces on the A1 mini" | **260 > 180: 80 mm over, 4 pieces not 3** | MEASURED + ANALYTICAL |
| ply minimum unquantified (`base:228`) | **0.591–0.775 mm of laminate**; 6.1–24.4 mm ply radius; body offers r = 0 | ANALYTICAL |

**My own residual uncertainties, stated:** the three material densities are ASSUMED (swept, ≤4.8 %
effect); `eps_allow` is ASSUMED (bracketed 0.5–2 %); the saved profile's wall generator is not pinned,
so "off-lattice" could be resolved by Arachne at a cost in width control; and the 0.6/0.8 nozzle
columns are an explicit extrapolation of the 0.4 law. **None of these flips a conclusion** — the
0.8 mm wall fails on the layer-height test and the ply-stack floor regardless.

---

## 8. Files

| file | what it is |
|---|---|
| `REPORT.md` | this report |
| `scripts/00_verify_citations.py` | machine-checks all 83 `file:line` citations; exits 1 on a miss |
| `scripts/01_ply_stack.py` | ply thickness, min wall, layer test, drape radius, joint overhead, thinning re-cost |
| `scripts/02_nozzle_and_bed.py` | nozzle/loop/wall table, tolerance comparison, bed vs piece arithmetic, SO(3) min enclosing cube |
| `scripts/03_key_numbers.py` | flattens both JSONs into `KEY_NUMBERS.csv`; asserts no SOLVER row exists |
| `data/citations.json` | every citation with the actual line text and file sha256 |
| `data/ply_stack.json` | all §2 numbers |
| `data/nozzle_bed.json` | all §3 and §5 numbers |
| `data/KEY_NUMBERS.csv` | flat table for merging |

Reproduce (Windows python, no WSL needed — there is no solver in this unit):

```
& 'C:\Program Files\Python312\python.exe' scripts\00_verify_citations.py
& 'C:\Program Files\Python312\python.exe' scripts\01_ply_stack.py
& 'C:\Program Files\Python312\python.exe' scripts\02_nozzle_and_bed.py
& 'C:\Program Files\Python312\python.exe' scripts\03_key_numbers.py
```

All four exit 0. Runtime ≈ 2 s / 1 s / 6 s / 1 s. `00` must pass before anything else is believed.