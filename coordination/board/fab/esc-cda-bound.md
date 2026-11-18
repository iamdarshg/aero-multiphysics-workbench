# CdA bound for the 720 km/h airframe — and what it does to the ESC current

**Wave 9 · evidence/esc-cda-bound · 2026-11-16**
Scope: bind the whole-aircraft CdA that the ESC's current decision rests on. No repo writes; all
measurements were taken on copies/read-only reads. Solver files: `evidence/dm-cfd-final/`.

---

## 0. Answer first

| | value | status |
|---|---|---|
| **Candidate A** | **CdA = 0.000693 m²** | `phase15_*` code, "canonical raster CdA" |
| **Candidate B** | **CdA = 0.0015 m²** | `PHASE15_DESIGN_SPEC.md:244`, nominal of the declared band |
| **Independent build-up, nominal** | **CdA = 0.00416 m²** | this work, on CAD-measured wetted area |
| **Build-up range** | **0.00335 – 0.00559 m²** | low / high columns |
| **Hard physical floor** (skin friction only) | **0.00270 m²** | Cf × S_wet, no form factor at all |
| **Per-phase current, build-up range** | **79 – 132 A rms** | same chain as the settled 16.8 A |
| **Per-phase current, best estimate** | **98 A rms** | at 0.00416 m² |
| **Per-phase current at CdA 0.0015** | 35.4 A | (37.2 A is in circulation; see §6.2) |

**Both candidates sit below the skin-friction floor of the aircraft's own wetted area.** A is 3.9×
below it; B is 1.8× below it. No attached-flow body of this geometry can have either value as a
whole-aircraft CdA. The 16.8 A per-phase figure is therefore **withdrawn**, and the ESC is not a
17 A board — at the physical CdA it is a **~80–130 A** board, i.e. worse than the 60 A figure the
programme spent several waves correcting downward.

---

## 1. The two candidates, exactly where each comes from, and what each describes

### Candidate A — 0.000693 m² (the number the ESC decision actually used)

Provenance chain, all `repos/drone-mech/highspeed_edf/`:

| link | file:line | content |
|---|---|---|
| 1 | `phase15/optimization/phase15_frontal_area_model.py:151-152` | `cda_ratio = total_frontal_solid_cm2 / reference.total_frontal_solid_cm2`; `estimated_cda = 0.0009 * cda_ratio` |
| 2 | `phase15/results/phase15_frontal_area_model.csv:26` | row `80,40,side_by_side,front,True`: frontal solid **247.51 cm²**, ratio 0.7703, **CdA 0.0006933** |
| 3 | `phase15/reports/phase15_benchmark_report.md:121-131` | the table, captioned *"CdA at the same reference Cd as the old 0.0009 m² baseline"* |
| 4 | `phase15/optimization/phase15_losses_and_config.py:28` | `CDA = 0.000693  # canonical raster CdA (was 0.000654)` |
| 5 | `phase15/optimization/phase15_range_and_cost.py:36` | same constant, `# canonical: 80 mm / 40 mm hub / front inlet / 30 mm wing (raster model)` |
| 6 | `phase15/optimization/phase15_low_cost_benchmark.py:74-78` | same constant, returned regardless of fan diameter |
| 7 | `phase15/optimization/phase15_phase9_reconciliation.py:90` | same constant |

**What it describes: the whole aircraft, but it is not a drag calculation.** It is an *area ratio*
times an inherited guess: 0.0009 × (247.51 / 321.33). The "constant reference Cd" held constant
across that scaling is 0.0009/0.32133 = **0.028 on frontal solid area** — a number that appears
nowhere in the repo as a derived quantity and that the same report calls an assumption
(`phase15_benchmark_report.md:142-145`: *"the 0.0009 m² CdA target is therefore optimistic … it
needs a fresh VLM/CFD-derived polar rather than an assumed number"*).

**The mechanism of the error is visible in the arithmetic.** The old 0.0009 m² belonged to a
**75 cm²** frontal gate — 0.0009 on 0.0075 m² is exactly **Cd 0.12** on frontal area. The corrected
raster says the frontal solid area is **247.5–321.3 cm²**, i.e. 3.3–4.3× larger. Rescaling at that
same Cd would have given **0.0030–0.0039 m²**. Instead the CdA was rescaled by the *area ratio*
against a reference row that already carried the corrected area — so the frontal area grew 4.3×
while the implied Cd fell 4.3× and the CdA came out 23 % *lower*. The programme corrected the area
and, in the same step, divided the drag coefficient by the same factor.

Two further facts about A:
- **It is below the spec's own band.** `PHASE15_DESIGN_SPEC.md:244` gives 0.0008–0.0015–0.0030 m².
  0.000693 is **0.87× the most optimistic member** of that band.
- **It was chosen, not measured.** `DESIGN_DECISIONS_FOR_VERDICT.md:18-25` records option A
  ("assume slippery 0.0007–0.0008"), option B ("assume draggy 0.0015–0.0030", **DISCARDED**,
  +₹10–30k) and "measure it" (**DISCARDED**, +₹5–15k), then: *"if the real aircraft is fatter than
  assumed, it will not reach 720 km/h"*. The optimistic end was a documented, accepted risk. This
  wave prices that risk.

### Candidate B — 0.0015 m²

| file:line | content |
|---|---|
| `design/PHASE15_DESIGN_SPEC.md:244` | `CdA at 720 (UNRESOLVED — #1 gate) · 0.0008 – 0.0015 – 0.0030 m² · … · VLM/CFD polar + tunnel; the old 0.0009 was an assumption, not a measurement · whole aircraft` |
| `:245` | implied Cd on the 270 cm² silhouette 0.03 – 0.055 – 0.11 (= CdA ÷ 0.027 m²) |
| `:58`, `:502`, `:554`, `:577` | same band repeated; stretch target ≤ 0.0005 |
| `OBSOLETE.md:22` | the 0.0009 m² of the superseded basis replaced by the band |
| `DESIGN_DECISIONS_FOR_VERDICT.md:19` | the band's upper half, discarded on cost |

**What it describes: the whole aircraft** — explicitly, in the "where" column of the spec table.
It is a **placeholder with a stated nominal**, not a measurement: the "how" column says the polar
does not exist yet. Its implied Cd on the 270 cm² frontal silhouette is 0.055, and the spec itself
calls the band's pessimistic end (0.11) *"the edge of missile-class body"*.

> **Note on `FA4119_PROPULSION_DECISION.md`.** The board cites it in the CdA chain. It contains **no
> CdA at all**. It is a four-motor, 8-inch-propeller, ~8 kg prototype record
> (`repos/drone-arm/hardware/motor_release/FA4119_PROPULSION_DECISION.md:7, :40-54`), and its only
> contributions to the chain are 44.4 V, ~8 kg and "60 A at nominal 12S" — a **bus** current for a
> **four**-motor aircraft. The 6-motor ducted-fan configuration is a different aircraft; carrying
> those three constants across is an inference, not a datum.

---

## 2. Independent derivation from geometry

### 2.1 Design point and constants

3 km ISA, 720 km/h: T = 268.65 K, ρ = 0.9091 kg/m³ (matches `controlDict.final` `rhoInf`),
μ = 1.6937e-5, **V = 200 m/s, M = 0.6087, q = 18,182 Pa, Re/m = 1.0735e7**.
Turbulent flat plate Cf = 0.455/(log₁₀Re)^2.58 with the Raymer compressibility factor
/(1+0.144M²)^0.65. Form factors: wing `[1+0.6/(x/c)(t/c)+100(t/c)⁴]·[1.34M^0.18(cosΛ)^0.28]`,
fuselage `0.9+5/f^1.5+f/400`. Method and every coefficient form: Raymer ch. 12 as tabulated in
[the CODE Lab drag-buildup worksheet](https://computationaldesignlab.github.io/aircraft-design/aerodynamics/drag_buildup.html).

### 2.2 Wetted area, measured from the actual CAD

`measure_step.py` (OCP/cadquery 2.7.0) imports each STEP and sums face areas. Axes: X lateral,
Y vertical, Z flight axis; units mm in file, converted here.

| part (STEP in `deliverables/phase15_geometry/step/`) | measured area | used as | note |
|---|---|---|---|
| `fuselage_battery_bay_shell_endpoint_relief_42_6.step` | **0.28522 m²** | lifting-body OML | 511 faces, bbox 211.8 × 93.9 × 640 mm |
| `lifting_wing_right_sector_…reliefs.step` | 0.13997 m² | wing, both sides | bbox X 80.3→260.0 (= the CFD semi-span) |
| `lifting_wing_left_sector_…reliefs.step` | 0.13997 m² | wing, both sides | mirror |
| `lifting_wing_centre_bridge_…reliefs.step` | 0.02840 m² | wing, both sides | X ±8.96 mm |
| `elevon_right_40x150.step` (×2) | 0.01283 m² each | protuberance | |
| `canted_tail_fin_right_…rudder_cut.step` (×2) | 0.01411 m² each | protuberance | |
| `duct_A_vector_vane_1_30x40.step` (×4) | 0.00302 m² each | protuberance | |
| `twin_landing_skids_and_legs.step` | 0.01435 m² | protuberance | |
| `duct_A_side_inlet_100mm.step` (×2) | 0.05573 m², **45 % external** | inlet fairing | rest is buried in the OML |
| `duct_A_separate_nozzle_and_exit_lip.step` (×2) | 0.06987 m², **35 % external** | nozzle/lip | rest is the duct bore |
| `single_right_fin_rudder_27mm.step` | 0.00600 m² (est.) | protuberance | not re-measured; < 1 % of total |

**S_wet = 0.7789 m²** (of which 0.3083 wing, 0.2852 body, 0.1854 protuberances/duct externals).

Three independent checks that 0.2852 m² is a *single-surface OML* and not a two-sided shell or an
OML-plus-bores count:
- the loft cross-section is 195.4 cm² (measured front projection), giving an equivalent diameter of
  158 mm and a fineness ratio of **4.06**; a superellipse perimeter of 0.50 m, tapered to ~0.85 over
  0.64 m, gives ≈ **0.27 m²** — 5 % from the measured value;
- if the 42_6 solid also carried the two 78 mm duct bores (2 × π × 0.078 × ~0.36 m ≈ 0.18 m²) the
  total would be ≥ 0.46 m², which the measured 0.2852 rules out.
- the programme's own allowance for all skins is **0.45 – 0.57 – 0.70 m²**
  (`PHASE15_DESIGN_SPEC.md:257`). The CAD sums to 0.68 m² of OML + fairings before the protuberance
  externals are added — the spec's allowance is optimistic by 10–25 %.

### 2.3 The build-up

Wing term is taken from the programme's own solver (§3) rather than from a correlation; everything
else is Cf × FF × Q × S_wet. Low / nominal / high columns propagate FF and Q, not "± a fudge".

| component | S_wet | Re | Cf | cda low | **cda nom** | cda high |
|---|---:|---:|---:|---:|---:|---:|
| lifting-body OML | 0.28522 | 6.87M | 0.00309 | 0.00128 | **0.00134** | 0.00185 |
| elevons (2) | 0.02566 | 1.61M | 0.00396 | 0.00012 | **0.00013** | 0.00016 |
| tail fins (2) | 0.02822 | 0.97M | 0.00435 | 0.00015 | **0.00016** | 0.00019 |
| rudder + fin | 0.00600 | 0.97M | 0.00435 | 0.00003 | **0.00003** | 0.00004 |
| vector vanes (4) | 0.01210 | 0.43M | 0.00509 | 0.00008 | **0.00009** | 0.00012 |
| landing skids | 0.01435 | 2.77M | 0.00360 | 0.00007 | **0.00009** | 0.00012 |
| side-inlet fairings (2, ext) | 0.05015 | 1.30M | 0.00412 | 0.00024 | **0.00028** | 0.00036 |
| nozzle / exit lips (2, ext) | 0.04891 | 1.45M | 0.00404 | 0.00022 | **0.00025** | 0.00031 |
| **subtotal, non-wing** | | | | 0.00218 | **0.00238** | 0.00314 |
| **wing (2 panels + bridge) — SOLVER band** | 0.30833 | 3.72M | 0.00342 | 0.00098 | **0.00140** | 0.00163 |
| subtotal | | | | 0.00317 | **0.00378** | 0.00477 |
| leakage / protuberance / gaps | | | | +3 % | **+5 %** | +10 % |
| base, probe, inlet spillage | | | | +0.00010 | **+0.00020** | +0.00035 |
| **TOTAL CdA (m²)** | | | | **0.00335** | **0.00416** | **0.00559** |

Form-factor values used (published forms, not fitted): body f = 4.06 → **1.522** (Raymer 12.36) with
1.908 as the high column (Raymer 12.31); wing t/c = 0.0866, Λ = 40°, M = 0.609 → **1.341**; fins
**1.252**. Interference Q = 1.00 body/wing, 1.04 tails, 1.05–1.10 fairings.

### 2.4 The three cross-checks that make this a measurement and not an opinion

1. **The correlation reproduces the solver.** Wing by Cf × FF × Q × S_wet = **0.00141 m²**; the
   solver's own wing band mean is **0.00140 m²** — **+1.1 %**. The same method applied to the one
   surface the programme has actually solved agrees with it to 1 %. That is the calibration for every
   other row in the table.
2. **Equivalent skin friction lands in the textbook class.** CdA/S_wet = **0.00534** nominal
   (0.0043–0.0072 across the band). Raymer's Cfe for light aircraft is ≈ 0.0055. Candidate A implies
   **Cfe = 0.00089** — no aircraft class has that; it is a *laminar* number, at M 0.61, on a
   printed shell with two inlet lips and six rotors.
3. **The friction floor.** Cf × S_wet summed over the same components = **0.00270 m²** with *zero*
   form factor, *zero* interference, *zero* wave drag, *zero* protuberance allowance. This is not a
   design target; it is the smallest drag area that can physically exist for this wetted area in
   attached turbulent flow. Both candidates are below it (A by 3.9×, B by 1.8×).

---

## 3. Cross-check against the CFD evidence — and exactly why its Cd is not authoritative

`evidence/dm-cfd-final/v2/seg1.dat + seg2.dat`, re-analysed here from the raw trace (498 rows,
t/c 0.255–1.806; column order from the `fCoeffs` header: `Time, Cd, Cd(f), Cd(r), Cl, Cl(f),
Cl(r), CmPitch, CmRoll, CmYaw, Cs, Cs(f), Cs(r)`).

| quantity | my recompute (last-20 % window, n=112) | `TRACE_CORRECTION.md` / board |
|---|---|---|
| Cd mean | 0.011228 | 0.011228 ✔ |
| Cd scatter | **13.2 %** | 13.15 % ✔ |
| Cd first → last | 0.01195 → **0.00790** (−33.9 % over the window) | last sample 30 % below its own mean ✔ |
| Cd min / max | **0.00790 / 0.01306** (final half-chord of my window; the quoted table's max is 0.0126) | oscillation 0.0079–0.0126 ✔ |
| Cl mean | **−0.01641**, scatter 1.3 % | −0.01646, band −0.0149…−0.0167 ✔ |
| Cs mean | **−0.38919**, scatter 0.2 % | −0.3886…−0.3906 ✔ |

**Which object the solver describes.** Not the aircraft. `Aref = 0.062249 m²` is the planform of
**one wing panel**: the same CAD panel measures 0.06268 m² via its XZ projection (**0.7 %**), its
bbox X extent is 0.17967 m — identical to the CFD semi-span — and the mesh has a `rootWall`
symmetry plane at x = 0.0803 plus `farfield`/`inlet`/`outlet`. `Aref` is therefore a *half-wing*
reference and the reported force is *one panel's* force. **Full-wing drag area = 2 × Cd × Aref.**
The case contains no fuselage, no duct, no inlet, no vane, no fin, no skid.

**Why its Cd is not authoritative — four independent reasons:**
1. **It is not converged and not converging monotonically.** The final-20 % window still moves
   −33.9 % end-to-end at 13.2 % scatter, and the report's own longer window shows **+39.9 %**
   (it reverses). A phase-averaged mean over ≥ 3 periods (period ≈ 0.3–0.5 chords) is the correct
   extraction, and that experiment was not run (`TRACE_CORRECTION.md:24-29, :77-80`).
2. **It is a sector, not a configuration.** Whatever value it settles to, it cannot be a
   whole-aircraft CdA — it is missing ~60 % of the wetted area.
3. **Its own force decomposition is not physical.** The solver prints `Cd(f)` and `Cd(r)`, which sum
   to `Cd` exactly (max residual 1e-12). One of them is positive throughout (0.01258–0.01658, mean
   0.01474); the other runs **−0.00468 … +0.01585, mean −0.00013, and is negative for 372 of 498
   rows and 100 % of the final 200**. A net-negative viscous (or any single-sign) share of drag is not
   physical on a no-slip wall, so *no part* of this decomposition can be quoted as a component value.
   The most likely cause is the 6.1 % of `fsi` faces that are the **embedded root cut plane** (a face
   inside the solid where wall shear has no meaning) contributing a spurious term — the same surface
   that carries the known `p_ref` bias in Cs.
4. **It is a fixed-Mach, fixed-incidence point** (M 0.652, Cl ≈ −0.016), not a polar.

**What it *is* good for: a floor.** The full-wing drag area implied by the trace is
**0.00098 / 0.00140 / 0.00163 m²** at the oscillation minimum / mean / maximum. Since total aircraft
drag must exceed its own wing's drag, **CdA_aircraft ≥ 0.00098 m² even at the lowest excursion of an
unconverged trace** — which already refutes candidate A (0.000693) by 42 %, and consumes 65 % of
candidate B before a fuselage, two ducts, two inlets, four vanes, two fins and two skids are counted.
The withdrawal of the Cd does not weaken this argument: the *lowest* sample is the most favourable
value the trace ever produced, and it still exceeds A.

---

## 4. Real comparables — is CdA 0.000693 plausible for a ducted EDF?

CdA is a physical area, so it can be compared directly with aircraft whose cd and wing area are
published. On this aircraft's own wing area (**0.1300 m²** = 2 × 0.06225 half-panel + 0.00555 centre
bridge):

| aircraft (published cd, wing-area referenced, from [Wikipedia, Drag coefficient](https://en.wikipedia.org/wiki/Drag_coefficient), sourcing Aerospaceweb) | cd | what CdA this aircraft would have if it were *that* clean |
|---|---:|---:|
| F-4 Phantom II (subsonic) | 0.021 | 0.00273 m² |
| Learjet 24 | 0.022 | 0.00286 m² |
| Cessna 172/182 | 0.027 | 0.00351 m² |
| Boeing 747 | 0.031 | 0.00403 m² |
| F-104 Starfighter | 0.048 | 0.00624 m² |

- **cd = 0.011** (which is what CdA 0.000693 would mean on the wing area) is **below every one of
  these, including the F-104** — and it is being claimed for a vehicle **1/13 to 1/30 the length** of
  those aircraft, i.e. at **1.3–1.8× their skin-friction coefficient** by Reynolds scaling, with two
  inlet lips, four vanes, two fins and a printed surface. The answer to "is 0.011 plausible for a
  ducted EDF?" is **no — by a factor of ~3–4 against the build-up, and below the cleanest large
  aircraft in the table**, and the shortfall is not subtle.
- The build-up's nominal **0.00416 m²** sits between the 747 and the F-104 on the same scale — which
  is what a fat-bodied, small-winged, small-scale airframe should be.
- Cross-checks at the *component* level: a streamlined body of fineness 4 in the subsonic
  [streamlined-body table](https://web.archive.org/web/20070715171817/http://aerodyn.org/Drag/tables.html)
  (Filippone, after Hoerner) runs at Cd 0.02–0.05 on frontal area; the build-up's body term
  (0.00134 m² / 0.0195 m²) is **Cd 0.069** on frontal area — the "streamlined but not laminar" end of
  that range, appropriate for a superellipse pod with n = 2.6 corners at M 0.61.
- A published drag-buildup worksheet for a comparable subsonic aircraft records the same lesson this
  programme is relearning: its *detailed* build-up gave **CD0 0.0336** against **0.028 assumed** for
  sizing ([CODE Lab, parasitic drag](https://computationaldesignlab.github.io/aircraft-design/aerodynamics/drag_buildup.html),
  "this value is higher than what was assumed … during initial sizing").

**Combination note, because it changes the mechanism but not the number:** the six rotors are **not
exposed**. They are three rotor rows **inside each of two 82 mm ducts** buried in the lifting body
(`phase15_benchmark_report.md:164`, `phase15_twin_ducts_and_fans.step`), fed by side inlets and
exhausting through aft nozzles. So there is no propeller-wake excrescence drag — but there are two
inlet lips, two nozzle lips, four vanes in the jet and duct external surface, and those are carried
explicitly in the table above (0.00053 m² of the 0.00416). A fan-in-duct installation trades propeller
drag for lip and internal-flow loss; it does not make the airframe area disappear.

---

## 5. The current that follows — same chain, at both ends

Chain is the settled one verbatim (`board`: T = q·CdA; ÷0.72; ÷(0.90·0.97); ÷44.4 V; ÷6; ÷0.92),
scaled linearly in CdA. `cda_analysis.py` reproduces the settled 16.8 A as **16.36 A** at
CdA = 0.000693, i.e. **within 2.6 %** (the settled 2,580.6 W is 2.4 % above q·CdA·V = 2,520 W;
that residual is unexplained in the settled chain and is immaterial here).

**Low end, CdA = 0.00335 m²**
```
D = 18,182 × 0.00335 = 61.0 N
P_d = 61.0 × 200 = 12.20 kW
÷ 0.72          = 16.94 kW shaft
÷ (0.90 × 0.97) = 19.40 kW electrical
÷ 44.4 V        = 437.0 A bus
÷ 6 motors      = 72.8 A per motor
÷ 0.92          = 79.2 A rms per phase
```
**High end, CdA = 0.00559 m²**
```
D = 18,182 × 0.00559 = 101.7 N
P_d = 20.34 kW  ÷ 0.72 = 28.25 kW  ÷ 0.873 = 32.36 kW
÷ 44.4 V = 728.9 A bus  ÷ 6 = 121.5 A  ÷ 0.92 = 132.1 A rms per phase
```
**Best estimate, CdA = 0.00416 m²:** D = 75.7 N, 24.1 kW electrical, **98.3 A rms per phase.**
**Friction floor, CdA = 0.00270 m²:** 63.7 A — the lowest physically possible number.

For completeness: **CdA 0.0015 → 35.4 A** (not the 37.2 A in circulation; the circulating figure
needs CdA ≈ 0.00158 or a slightly different chain — at this scale a 5 % discrepancy on a value that
is itself withdrawn).

The 1.12× momentum term (jet-induced velocity, vi = 24.6 m/s for 0.00754 m² of annulus) is **not**
applied above; applying it would raise the 98 A figure to ~110 A. It is excluded so the comparison
is strictly like-for-like with the settled 16.8 A.

### 5.1 The chain has a units defect worth recording

The settled paragraph multiplies the 12.60 N drag by **6 motors** and calls 75.6 N "consistent with
78.5 N weight". That is a population error: `q·CdA = 12.60 N` is the **whole-aircraft** drag (the
2,580.6 W ÷ 200 m/s = 12.9 N confirms it), not a per-motor thrust. The 75.6 N figure would be the
whole-aircraft drag only at **CdA = 75.6/18,182 = 0.00416 m²** — the build-up's nominal, to 0.2 %.
So the one line in the settled chain that reads like a sanity check is arithmetic on six times the
drag: it validates nothing, and its implied area is this wave's answer by accident of the motor count.

---

## 6. Conclusion

### 6.1 Defensible range

**CdA = 0.0034 – 0.0056 m², best estimate 0.0042 m²**, with a hard floor of **0.0027 m²** that no
real aircraft reaches because it excludes every form, interference and wave term.

Basis, in order of strength:
1. **Hard floor:** Cf × S_wet (0.7789 m² measured) = 0.00270 m². Candidates are 3.9× and 1.8× below.
2. **Wing alone:** solver-implied 0.00098–0.00163 m² (mean 0.00140). Candidate A is below the wing's
   *lowest* sample.
3. **Build-up:** 0.00335 / 0.00416 / 0.00559, calibrated against the solver wing to +1.1 %.
4. **Cfe:** 0.0053 nominal, inside the textbook light-aircraft band; A gives 0.00089, outside any band.
5. **Comparables:** A implies cd = 0.011 on the aircraft's own wing area — cleaner than an F-104, at
   1/13–1/30 the length of the aircraft in that table.

### 6.2 What is withdrawn

| withdrawn | replaced by |
|---|---|
| **CdA 0.000693 m²** as a whole-aircraft value | 0.0034–0.0056 m² (best 0.0042) |
| **16.8 A rms per phase** | **79–132 A (best 98 A)** |
| "range 14.7–22.2 A" | **≈71–107 A** at the low CdA, 118–179 A at the high CdA (FOM spread × CdA spread); i.e. **70–180 A**, not 15–22 A |
| "37.2 A at the spec's CdA of 0.0015" | **35.4 A** — still a *withdrawn-class* number, because 0.0015 is itself 1.8× below the friction floor |
| "the ESC is a ~17 A board with a 37 A worst case" | the ESC is an **~80–130 A** board, worse than the 60 A it was corrected down from |
| "the battery rail is adequate" (at 16.8 A) | not adequate at any physical CdA; BATP's 23.1 A and BATN's 47.4 A both fail |
| "2 oz becomes viable" | not viable; 2 oz 22.9 A is 4.3× short at best estimate |

### 6.3 Which CdA would I design to, and why

**Design to CdA = 0.0056 m² — the pessimistic end — and therefore to ~130 A rms per phase, not 17 A.**

Three reasons, in the board's own currency:
1. **The physics has a one-sided error.** Every uncertain term (form factor on a superellipse body,
   interference at two inlets, wave drag on a 4-fineness body at M 0.61, printed surface roughness)
   can only add drag. There is no plausible mechanism that removes 40 % of the build-up. So the
   distribution of possible truths is skewed *up* from 0.0042, which is exactly the case where a
   design should sit at the top of the band rather than the middle.
2. **The cost asymmetry is the board's own governing principle.** Under-sizing copper is a respin plus
   a warranty/fire risk; over-sizing it costs area and mass. At 4 oz, going from 98 A to 132 A costs
   copper width on 18 phase nets; getting it wrong the other way costs the board.
3. **At this value the A/B question is already decided by default — and that is the finding.** 132 A
   exceeds the 4 oz branch (48.0 A) by 2.75× and the 2 oz branch (22.9 A) by 5.8×. The copper weight
   no longer selects the branch; it only sizes a board that must be re-architected anyway.

### 6.4 What that means for the programme (stated plainly, not as a decision I can make)

At the best-estimate CdA, 720 km/h needs **75.7 N of thrust — T/W 0.96 at 8 kg — and 24.1 kW
electrical**. Six FA4119s at their *published* 3.47 kW / 74 A point give 20.8 kW electrical, which
caps the aircraft at **≈ 686 km/h**. So the 720 km/h design point is **at or beyond the airframe's
drag limit even with every motor at its published maximum**, and the honest options are:

| option | consequence |
|---|---|
| keep 720 km/h | ESC is a 6-channel ~100 A+ design (not this 4-layer 383 cm² board); battery must supply ~543 A bus |
| keep this ESC (4 oz, 48 A phase) | top speed **≈ 567 km/h** at CdA 0.00416 |
| keep this ESC (2 oz, 22.9 A phase) | top speed **≈ 443 km/h** at CdA 0.00416 |
| keep 60 A (the legacy number) | top speed **≈ 611 km/h** |

And the correct next measurement is not another ESC layout: it is **a full-configuration drag
measurement** (a duct+body+wing half-model in a tunnel, or a full-configuration RANS at the same
M 0.61 with a *converged, phase-averaged* force extraction over ≥ 3 periods). Until then the CdA is
a build-up with a stated band, which is a legitimate basis for a *design* and not for a *claim*.

---

## 7. Limitations — what this analysis does not cover

1. **No full-configuration CFD or tunnel data exists.** The wing sector is the only solved surface in
   the programme; the body/duct terms are correlation-based (Raymer-class), accurate to roughly ±15 %
   each, not ±5 %.
2. **The `42_6` body of record is a repaired design intent** (4 disjoint solids over 77.165 mm, per the
   board). Its wetted area is therefore that of the intent, not of a manufacturable part; the Boolean
   repair could change S_wet by a few per cent.
3. **Wetted-area choice carries ±8 %.** The 0.7789 m² total includes estimated external fractions for
   the inlet fairings (45 %) and nozzles (35 %) and an estimated rudder area; the two structural
   surfaces (body 0.2852, wing 0.3083) are measured, and they are 76 % of the total.
4. **The 45 %/35 % external fractions are judgement.** If both inlet and nozzle externals are zero
   (fully buried), S_wet falls to 0.680 m² and the nominal CdA falls to **0.0036 m² (85 A)**. The
   conclusion is unchanged.
5. **Laminar flow is not credited.** If a printed, filled and painted shell held 30 % laminar flow the
   Cf terms would fall ~15 %, i.e. CdA ~0.0037 — still inside the stated band and still 5× candidate A.
6. **The momentum (jet-induced velocity) term is excluded** for comparability; including it raises the
   current ~12 %.
7. **`Aref` half-wing interpretation** is established from CAD + mesh (0.7 % area, exact span match)
   and the `rootWall` symmetry plane. If the mesh in fact models a *full* wing, the solver wing term
   halves to 0.00070 m² and total CdA becomes **0.0034 m² (81 A)** — still 4.9× candidate A.
8. **The efficiency constants are inherited, and optimistic.** FOM 0.72, motor 0.90, ESC 0.97 and the
   0.92 phase factor are taken verbatim from the settled chain. At ~100 A a 41 mm-class outrunner is
   below its 74 A published point, so 0.90 (and probably 0.92) are high; the current figures above are
   therefore **lower bounds**, not central estimates.

---

## 8. Reproducibility

| artefact | what it is |
|---|---|
| `cda_analysis.py` | trace re-analysis + build-up + current chain; writes `cda_analysis.json` |
| `measure_step.py` | STEP face-area measurement (OCP/cadquery 2.7.0), the wetted-area source |
| `cda_analysis.json` | every number in this report, machine-readable |
| inputs (read-only) | `repos/drone-mech/.../phase15_geometry/step/*.step`, `evidence/dm-cfd-final/v2/seg{1,2}.dat` |

Run: `python cda_analysis.py` (numpy only, ~2 s). Geometry: `python measure_step.py <step>...`
(cadquery/OCP, ~4 s per part). No repo file was modified and no branch was touched.

Inputs read (sha256, first 16 hex):

```
59ABEDADCAA269A5  evidence/dm-cfd-final/v2/seg1.dat
9F5A1F5F6E21B466  evidence/dm-cfd-final/v2/seg2.dat
CDB613A80D0CE10B  evidence/dm-cfd-final/controlDict.final   (Aref 0.062249, lRef 0.34646, U 222.1322, rho 0.9091)
C4B81DC302C66500  phase15_geometry/step/fuselage_battery_bay_shell_endpoint_relief_42_6.step
A3B1D7E09D603455  phase15_geometry/step/lifting_wing_right_sector_with_duct_and_elevon_reliefs.step
3732631744B605E5  phase15_geometry/step/lifting_wing_centre_bridge_sector_with_duct_and_elevon_reliefs.step
7C81B619E28333D4  phase15_geometry/step/duct_A_side_inlet_100mm.step
65A55228C17E5E84  phase15_geometry/step/duct_A_separate_nozzle_and_exit_lip.step
```

Provenance tiers, stated so nothing is mis-read as solver output: **wing term = SOLVER band
(unconverged, used only as a floor/band); every other row = ANALYTICAL (Cf × FF × Q on MEASURED
areas); the currents = ANALYTICAL on the inherited chain.** No number in this report is a converged
solver coefficient, and none is presented as one.