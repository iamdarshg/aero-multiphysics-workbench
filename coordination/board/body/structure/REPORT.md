# Body structure — first solver-backed check of the fuselage wall

**Agent:** body-structure (audit wave). **Date:** 2026-11-15.
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/body-structure/`.
**Host:** Windows 11, `C:/Program Files/Python312/python.exe` (cadquery 2.7.0 / OCP, numpy);
CalculiX 2.21 in WSL Ubuntu2404. **Nothing was written to a repository.** No commit, branch,
reset, or `audit/*` touched. One WSL runner lives in `scripts/` as required
(`scripts/body_struct_run.sh`).

Tier vocabulary: **MEASURED** (file read or pure geometry) · **SOLVER** (this run) ·
**ANALYTICAL** (stated closed form on MEASURED inputs) · **ASSUMED** (no source, always swept).

---

## 0. Verdict

1. **The 1.2 mm wall is ADEQUATE — not marginal — under the governing load case.** Peak wall
   stress **2.85 MPa** (1.43× refinement: **3.23 MPa**) at 12 g ultimate, against a PLA allowable
   of **17.3 MPa** → **FoS 5.4–6.1** at the worst point and **9.7** on the bay field stress.
   Peak deflection **0.139 mm** at E = 10 GPa (band **0.069–0.277 mm** over E = 20→5 GPa).
   `SOLVER`
2. **It has margin to thin to 0.8 mm** — FoS 3.4 worst-point / 5.3 field — but the *local* peaks
   (rail land, clamped ring, aperture corner) scale worse than the field (×1.81 for ×0.67
   thickness). Thin the sides, not the aperture or the rail pad. `SOLVER`
3. **The 42.7 g replacement wall for the C1 end cone is not needed for strength.** The cone wall
   sits at **0.44 MPa** (2.5 % of allowable) at 1.2 mm and **0.75 MPa** at 0.8 mm; it is a
   *surface*, not a strength member. **The −69.121 g C1 row is therefore CONSERVATIVE**, by up to
   ~14 g (the part of the 42.7 g that 1.2→0.8 mm thinning could recover). `SOLVER` + `ANALYTICAL`
4. **The exported body cannot carry this load at all**, and that is not a stress problem: the four
   solids are disjoint over **77.165 mm** (z −189.098 … −111.933). The +97 g Boolean repair is a
   *prerequisite* for any structural statement about the bay; the model below is the repaired
   design intent and says so throughout. `MEASURED` (re-confirmed here, §2.1)
5. **The mass work's open-top section modulus was 2.4× conservative** (2,134 mm³ as used vs
   5,146.3 mm³ for the same section here, with the same area to 1.2 %). Its stress conclusions are
   therefore conservative, not optimistic — and the solver corroborates them: 1.81 MPa
   ANALYTICAL vs 1.78 MPa SOLVER at the bay field, **1.7 %**. `ANALYTICAL` + `SOLVER`

---

## 1. Load case: what I ran, and what I rejected with numbers

### 1.1 Chosen — (a) battery-pack inertia under a hard landing, 12 g ultimate

| quantity | value | tier / source |
|---|---|---|
| pack mass | **0.28 kg** each, two packs = 0.56 kg | MEASURED — `phase15_generate_geometry.py:1024` (`add_part(... 0.28 ...)`) |
| pack envelope | 185 × 65 × 55 mm, pair side-by-side in the bay | MEASURED — `:93`, `BATTERY_PACK` |
| retention requirement | **≥ 6 g** | MEASURED — `design/HANDOFF_GEOMETRY_AGENT.md:177` |
| safety factor on case | **2.0** (the spec's band is 2.0–2.5–3.5; 2.0 taken, as the mass work did) | MEASURED — `design/PHASE15_DESIGN_SPEC.md:178` |
| ⇒ ultimate g-load | **12 g** | ANALYTICAL |
| ⇒ battery inertia force | **65.92 N** on the rails/end stops | ANALYTICAL |
| load introduction | two rail lines `x = ±68`, `y = −31`, `z = −300…−115`, 2 × 4 × 185 mm | MEASURED — generator `:1026-1027`; independently confirmed by the exported `battery_sliding_rails_and_6g_end_stops.step` bbox (x ±68, y −33…−27, z −300…−115) |
| battery CG station | z = −207.5 | MEASURED — `BATTERY_Z_CENTRE`, `:92` |

**Why this one.** It is the only one of the three in which the wall thickness is the *variable
under test* rather than a consequence of something else:

- it is a **mandatory retention requirement already in the programme** (≥ 6 g), so it cannot be
  designed away — unlike a performance load, which a lower speed would reduce;
- it is a **concentrated mass** introduced through a **2 × 4 mm rail land** into the **open-top bay
  section** — the weakest section in the body and the one the mass work proposes to thin
  (§5 of `body-mass-opt`: open-top Zx is 14 % of the closed ring);
- it is **rigid-body inertia**, i.e. a real force on the wall; the alternatives are pressures on
  parts that are themselves separate bodies.

### 1.2 Rejected, with the arithmetic

| case | moment at the wing station | wall stress | why rejected |
|---|---|---|---|
| **(b) wing-join bending, 720 km/h lift** | **29.67 N·m** ult (3 g × SF 2 on payload 1.0 kg @ −320, packs 0.56 kg @ −207.5, forward shell 0.968 kg @ −300) — the settled prior-wave figure | **2.53 MPa** = 29,670 / 11,737 mm³ `ANALYTICAL` | 3.2× the moment of (a) (29.67 vs 9.31 N·m) on a section 2.3× stronger (Zx 11,737 vs 5,146 mm³) ⇒ only 1.4× the stress: at z = −88 the crown is **not** open (the aperture ends at −106.5) and the section is limited by the 42.5 mm duct bores, not by the 1.2 mm wall. It therefore tests the *bore layout*, not the thickness decision, and it is the one case already covered analytically. Also the 1 kg payload it rests on is `not-geometrized` (0 mm³ in the mass model), so it cannot be run against a real mass without inventing one. |
| **(c) duct thrust reaction** | 7.1 N·m from 40 N @ z = +90 (20 N per duct) `ASSUMED` | **0.60 MPa** | Two disqualifiers. (i) **No citable thrust exists**: the programme's CFD force integration sits on the fsi cutting plane, so no CL/CD/thrust may be quoted (recorded project fact) — any number would be ASSUMED with no source at all. (ii) Structurally the duct is a *separate* 82 OD tube bonded to the body over a 4 × 110 mm bore land, so the body sees distributed shear, not a concentrated reaction. Least constraining of the three even on the most favourable reading. |

Honest note on the ranking: (a) and (b) are within a factor 1.4 on *nominal* stress (1.78 vs
2.53 MPa), so "most constrains" is a claim about **utilisation at the critical feature**, not about
magnitude. (a) wins on that: it loads the open-aperture bay and the rail land, and its peak
utilisation is the highest of the three. All three are far below every allowable, which is itself
the finding (§4).

---

## 2. Geometry: what is valid, and what the model actually is

### 2.1 BRepCheck_Analyzer on all six shells (the brief's "3 of 6 invalid" — confirmed)

`measure_body.py` → `measure_body.json`. `MEASURED`

| file | valid | solids | all solids valid | volume mm³ | verdict |
|---|---|---:|---|---:|---|
| `fuselage_battery_bay_shell.step` | **yes** | 2 | 2/2 | 253,001.328 | compound-cut collapse (excluded, per record) |
| `…_candidate_brep.step` | **NO** | 4 | 0/4 | 744,004.682 | invalid |
| `…_compoundcut_repair.step` | **NO** | 4 | 0/4 | 744,004.681 | invalid |
| `…_compoundcut_repair_order2.step` | **NO** | 4 | 0/4 | 744,004.682 | invalid |
| `…_endpoint_relief.step` (42.4) | **yes** | 2 | 2/2 | 745,805.106 | variant, not the body |
| **`…_endpoint_relief_42_6.step`** | **yes** | **4** | **4/4** | **742,305.526** | **BODY OF RECORD** |

So: exactly **three of six invalid**, and they are precisely the three 4-solid repairs — never the
body of record. The body also has **0 free edges** and `t_eff = 2V/A = 5.205 mm` (a 1.2 mm shell
plus a solid nose, which is why that ratio is not 1.2).

Per-solid, this run (matches `body-mass-opt`/`body-record-final` §7.2 to the µm):

| solid | volume mm³ | area mm² | t_eff = 2V/A | what it is |
|---:|---:|---:|---:|---|
| 0 | 624,770.530 | 110,192.1 | 11.34 | bulk nose/pod = the "fill" (624,770.5 mm³ of the record) |
| 1 | 20,808.296 | 33,843.8 | 1.23 | lateral wall, +x |
| 2 | 75,915.232 | 107,336.0 | 1.415 | keel + skin |
| 3 | 20,808.296 | 33,843.8 | 1.23 | lateral wall, −x |

Wall = solids 1+2+3 = **117,531.8 mm³** = the record's printed PLA core (145.739 g at
1,240 kg/m³). **The body is 4 disjoint solids**: no solid spans z −189.098 … −111.933 (77.165 mm),
so the as-exported body has **no load path from the battery bay to the wing**. That is not a
modelling choice; it is the geometry. **Any structural number for the bay is a statement about the
repaired body** (+97 g Boolean repair, `body-mass-opt` §7), and this report says so everywhere.

### 2.2 The idealisation (and why it is adequate for the question)

The exported geometry is unusable for stress (4 disjoint solids; the bay's forward half is solid
bulk, its aft 77 mm missing). What the question needs is the **skin**: a 1.2 mm superellipse loft
with the service aperture cut out, unstiffened, carrying the battery into the wing carry-through.
So the model is built from the **generator's own design intent**, not from the broken export:

| input | value | tier / source |
|---|---|---|
| section | superellipse, exponent **n = 2.6**, station table (w,h) at z | MEASURED — `phase15_generate_geometry.py:70, 274-280` |
| loft | **monotone cubic** (Fritsch–Carlson) through those stations | idealisation of `makeLoft(ruled=False)`, `:281` |
| wall | **1.2 mm** nominal (cavity = outer − 2 × 1.2, `:283-288`) | MEASURED |
| service aperture | 139 × 24 × 202 box at (0, 39.5, −207.5) ⇒ crown removed where \|x\| < 69.5, y > 27.5, \|z+207.5\| < 101 | MEASURED — `:306` |
| model extent | **z = −350 … −112** (nose to the front face of the 42.5 mm duct bores, `:293-295`) | MEASURED |
| excluded | duct bores (start at z = −112), 84 mm side capture slots (z = −70), hatch lid, fasteners | stated |
| element | **S4** (4-node shell, 6 dof/node), midsurface, `*SHELL SECTION OFFSET=0` | — |
| mesh | 112 angular × 64 axial = **5,786 elements / 5,953 nodes / 35,718 dof**; refinement 160 × 84 = 10,816 / 11,047 / 66,282 | — |
| support | fully clamped ring at z = −112 (the wing carry-through front face) | — |
| model wall mass | **209.3 g** = **154.7 g** of the bay/aft wall + **54.7 g** over the C1 cone region. The C1 row charges **42.7 g** for that cone wall; the model is **1.28× heavier** there (it takes the whole cone surface at the record's 2,568 g/m² wall areal), which makes the cone conclusion below conservative relative to the row | MEASURED/SOLVER |

**Why this is adequate.** (i) t/R = 1.2/44 = 0.027, so thin-shell theory is valid; the same domain
in solids at 0.4 mm elements would need ~10⁷ tets to resolve a 1.2 mm wall, and would answer the
same membrane+bending question. (ii) The geometry genuinely has **no frames and no stiffeners**
(`make_body_shell()` creates none — the "internal frames at Z = −100/+100" is a text claim in the
manufacturing report), so an unstiffened shell *is* the structure, not an approximation of it.
(iii) The model covers the bay wall plus the C1 cone wall and carries 100 % of the battery load
path. It omits the aft bore-cut slivers (~85 g of the 251.5 g wall), which carry no battery load.

**One idealisation error found and fixed, reported because it changed a number.** With a
piecewise-linear loft (a kink at every station) the peak stress came out at **3.83 MPa exactly at
z = −300**, the station kink — a discretisation artefact 35 % above the converged answer. The
smooth C1 loft took it to 2.85 MPa and moved the peak to the clamped ring. `SOLVER`

---

## 3. Material model, E sweep, and the scaling checks

### 3.1 What is modelled

The wall is a 1.2 mm printed PLA core plus a two-face CF/glass wrap the CAD does not carry. The
model is **one equivalent isotropic layer**, thickness 1.2 mm, ν = 0.30, E swept:

| E | provenance |
|---|---|
| **5 / 10 / 20 GPa** | 10 GPa is the deck's equivalent-isotropic seed (E = 10 GPa in `phase15_wing_load_stress_gate.json`, used by the wing sector and by the previous body buckling run) — **unsourced**; 5 and 20 GPa bracket a soft glass-heavy and a stiff CF-heavy 1.2 mm laminate |
| **2,140 kg/m³ (equivalent)** | not a material property: the wall's measured areal mass, 2.568 kg/m² (251.518 g over 0.0979 m², the record's own wall), divided by 1.2 mm. It is there so the shell's *self-inertia* is right |

The 0.8 mm case is run at the **1.2 mm wall's inertial load** (same 209.3 g), i.e. its own weight is
overstated by 20 %. That is conservative and it keeps the comparison a stiffness comparison rather
than a mass comparison. `ASSUMED`/stated.

### 3.2 Allowables (both ASSUMED, both swept in words)

| material | allowable | derivation |
|---|---:|---|
| printed PLA core | **17.3 MPa** | effective wall strength **34.5 MPa** = 0.725 × 45 MPa (the 0.87 mm of two perimeters, solid) + 0.275 × 0.15 × 45 MPa (the 0.33 mm residual at 15 % infill), with 45 MPa the in-plane printed tensile `ASSUMED` (no coupon data; the programme's materials audit is "blocked": no supplier, no layup, no allowables); ÷ SF **2.0** (`PHASE15_DESIGN_SPEC.md:178`) |
| CF/glass wrap | **250 MPa** | 540 g/m² per face 2-ply woven ≈ 500 MPa tensile `ASSUMED` ÷ SF 2.0. Coincides with the repo's own illustrative 250 MPa — that is a coincidence of magnitude, not a shared source |

The core governs by strain: it fails at 34.5 MPa / 3.5 GPa = **1.0 %** while the wrap fails at
250 / 10 GPa = **2.5 %**. So the strain at which the wall fails is set by the core, which is why the
core allowable is the binding check below. (Using the homogeneous model's stress against the core
allowable is conservative by ≈ E_eq/E_core ≈ 2.9, since the core only sees its share.)

### 3.3 The E sweep, and both scaling behaviours

`results.json`, `scaling.json`. `SOLVER`

| E GPa | u_max mm | uy at bay station mm | σ_vm peak MPa | σ field (bay) MPa |
|---:|---:|---:|---:|---:|
| 5 | 0.2771 | −0.0548 | 2.847 | 1.778 |
| **10** | **0.1385** | **−0.0274** | **2.847** | **1.778** |
| 20 | 0.0693 | −0.0137 | 2.847 | 1.778 |

**1/E check (the brief's test):** u·E = **1.38541** at E = 5, 10 and 20 GPa — identical to 8
significant figures; u-ratios 2.000000 and 0.500000. The sweep scales as **exactly 1/E**, so the
result satisfies the wing sector's established behaviour and the sweep is not hiding a
non-linearity. **Stress is E-invariant** (ratio 1.000000), which is the correct answer for a
load-controlled homogeneous model and is the second independent check: the sweep is about
stiffness only.

**√E:** that behaviour belongs to frequency- and eigenvalue-type quantities (f ∝ √E, buckling λ ∝
E), which this model does not compute. **I did not run a frequency or buckle step, so I cannot
verify it here and do not claim to.** The two invariants I can test are exact.

---

## 4. Results — the quantities that decide a design

Wall time **8.9 s / 334 MB** for the 5,953-node model, **17.4 s / 626 MB** for the 11,047-node
refinement, single-threaded and niced alongside a live 6-rank `rhoPimpleFoam` (1.28 GB available;
the solve never took more than half of it). Six solves total, ~80 s of solver time. `SOLVER`

### 4.1 Peak deflection

| | E = 20 GPa | **E = 10 GPa** | E = 5 GPa |
|---|---:|---:|---:|
| **u_max (nose tip, all 3 components)** | 0.0693 mm | **0.1385 mm** | 0.2771 mm |
| **sag at the pack station** (z = −207.5, uy) | −0.0137 mm | **−0.0274 mm** | −0.0548 mm |

**Band: 0.069–0.277 mm.** 0.14 mm is 0.16 % of the 88 mm body height. **Deflection is not a design
driver** for this case; the E uncertainty is worth ±0.1 mm and nothing breaks either way.

Refinement moved u_max 0.1385 → 0.1277 mm (**−8 %**), so the deflection is mesh-converged to ~8 %
and the band above is honest, not optimistic.

### 4.2 Peak stress in the wall, and where it is

`SOLVER`, E = 10 GPa, t = 1.2 mm. Coarse mesh → refined mesh in brackets.

| location | σ_vm MPa | note |
|---|---:|---|
| **clamped ring at z = −112** | **2.847 [3.226]** | global peak; a fully-clamped shell edge is the stiffest boundary there is, so this is an upper bound on what the real transition frame sees (+13 % under refinement = still rising) |
| **bay field, at the rail load land** | 1.778 [1.858] | the real, load-introduction-driven number; converged to 4 % |
| 95th percentile over the whole wall | 1.471 [1.538] | converged to 5 % |
| cone body (z < −335) | 0.440 [0.498] | |
| hatch forward corner (z ≈ −303, \|x\| ≈ 70) | 2.686 [3.226] | an aperture corner in a 1.2 mm shell with no doubler |

Applied root moment from the deck's own `*CLOAD`s: **M = 9.306 N·m** (battery 6.30 N·m over the
95.5 mm arm + 3.0 N·m of wall self-inertia). At the pack station the moment is **2.658 N·m**.

**Analytical cross-check, and it agrees to 1.7 %.** The same section integrated independently
(`section_check.py`, thin-wall ∫y²ds over the superellipse with the aperture removed, t = 1.2):
A = 384.9 mm², **Zx = 5,146.3 mm³**, ybar = −18.29 mm. σ = M/Zx = 9,306/5,146.3 = **1.81 MPa**
against the solver's bay field **1.78 MPa**. Two independent routes, 1.7 % apart. `ANALYTICAL`

**And a correction to the prior closed form.** `body-mass-opt/bay_section.py` used **open-top
Zx = 2,134 mm³**; the same section here gives **5,146.3 mm³** — a factor **2.41**. The two models
remove the same crown (their A = 380.3 mm² vs 384.9 mm² here, 1.2 %), so the divergence is in the
second moment, not the geometry: for the *closed* ring the two agree (15,767 vs 15,238 mm³, 3.5 %).
Consequence: **the mass work's open-top stress numbers are 2.4× conservative**, i.e. its conclusion
"this body is not strength-driven and never was" is conservative and correct, and this run confirms
it with a solver instead of a second closed form.

### 4.3 Factors against allowables

| case | σ MPa | FoS vs PLA 17.3 | FoS vs wrap 250 | verdict |
|---|---:|---:|---:|---|
| t = 1.2, bay field | 1.78 | **9.7** | 140 | adequate |
| t = 1.2, peak (clamp, refined) | 3.23 | **5.4** | 78 | adequate |
| t = 1.2, aperture corner | 3.23 | 5.4 | 78 | adequate |
| **t = 0.8, bay field** | 3.25 | **5.3** | 77 | adequate |
| **t = 0.8, peak (clamp)** | 5.15 | **3.4** | 49 | adequate |
| cone body, t = 1.2 | 0.44 | 39 | 568 | barely loaded |
| cone body, t = 0.8 | 0.75 | 23 | 333 | barely loaded |

**Is the 1.2 mm wall adequate, marginal or inadequate? ADEQUATE, with margin.** Nothing in the load
case gets above **19 % utilisation** of the PLA allowable, and the mesh-sensitive peak is at a
clamped boundary that the real structure does not have. The sequential scaling is well behaved
too: t 1.2 → 0.8 (×0.67) raises the peak 1.81× and the deflection 2.73×, between the pure-bending
limits (1/t² = 2.25, 1/t³ = 3.375) and the pure-membrane limit (1/t = 1.5) — exactly what a
restrained shell should do.

### 4.4 Two secondary results worth having

**The aperture is a stiffness hole and the lid closes it.** Adding the 139 × 202 lid as a 1.2 mm
fastened skin (`m3`, which also adds its own 70.1 g): u_max **−31 %** (0.1385 → 0.0956 mm), 95th
percentile stress **−9 %** (1.471 → 1.341 MPa), bay field **−4 %**. So the lid buys back most of the
*deflection* but little of the *stress* — because the peak stress is local (rail land, clamped
ring), not global bending. That refines the mass work's "make the hatch a structural cap"
recommendation: the cap is a stiffness measure, not a strength one, and it is worth doing for
deflection/aeroelastic reasons rather than for stress.

**The peak is at the load introduction, not at the apex of the bending moment.** The bay field peak
(1.78 MPa) sits at the rail land at x ≈ +85, and the refined run keeps it there. The wall's detail
design should therefore thicken the **2 × 4 mm rail land and the aperture corners**, not the
mid-bay skin: the local peak is as large as the global bending stress at 12 g, which is unusual for
a body this over-strengthened and is the one place where the mass work's "thin the sides" advice
needs a rider.

---

## 5. The question the mass work left open: is the 42.7 g replacement wall needed?

**The premise, taken as given:** hollowing an end cone costs **42.7 g** of replacement wall, and the
C1 row banks **−69.121 g** net. (A different wave records the merged C1 row at −64.2 g; the item
under test is the 42.7 g charge, so the conclusion holds for either. Not re-derived here.)

**What the check says.** The C1 cone is z −360 … −298.8, i.e. the forward part of this model, whose
wall is the **54.7 g** of the model's 209.3 g — 1.28× the 42.7 g the row charges, because the model
takes the whole cone surface at the record's wall areal mass. So the test is *conservative* with
respect to the row: more wall, same load. Under the governing case that wall is loaded by
**nothing but its own inertia**:

| quantity | t = 1.2 mm | t = 0.8 mm |
|---|---:|---:|
| σ_vm in the cone body (z < −335) | **0.44 MPa** | **0.75 MPa** |
| utilisation of the PLA allowable | **2.5 %** | 4.3 % |
| FoS vs PLA | 39 | 23 |

**Finding 1 — the replacement wall is not needed for strength.** 0.44 MPa is a 39× margin. The
42.7 g buys a **surface**, not a load path: a hollow cone has to have an outer skin, but the skin
does not have to be 1.2 mm. **1.2 → 0.8 mm is structurally free here** and would recover
≈ 14 g of the 42.7 g (one third of the wall mass, the same one-third the mass work already accepted
for the side band).

**Finding 2 — and it survives the obvious objection.** The reason to hollow the nose at all is to
put the 1 kg payload in it (currently a `not-geometrized` point mass sitting inside solid
material). If the payload does ride in the hollowed nose, it adds 1 kg × 12 g = 118 N at z = −320,
arm 208 mm ⇒ **24.5 N·m** at the root, and the cone's local closed-ring Zx = 10,782 mm³ gives
**σ = 2.28 MPa** (13 % of allowable; 1.56 MPa at the bay front). Still adequate at 1.2 mm *and* at
0.8 mm. So the conclusion is not an artefact of my load case ignoring the payload. `ANALYTICAL` on
MEASURED geometry

**Finding 3 — the only genuine structural cost of hollowing is buckling and handling**, not
strength: a hollow cone is a thin unstiffened shell you pick the aircraft up by. The prior wave's
own buckling sector (R = 200, t = 1.2) gives σ_cr = 19.45 MPa vs 0.44 MPa applied here — FoS 44 at
1.2 mm, 25 at 0.8 mm after a 0.5 imperfection knockdown. That does not challenge the wall either,
but it is the mode that *would* if the wall went below ~0.6 mm, and it is the one I did not re-run
in this model.

**Answer: the −69.121 g C1 row is CONSERVATIVE, not optimistic.** It charges a 42.7 g wall whose
structural demand is 2.5 % of its allowable, so the achievable saving is *at least* 69.121 g —
up to ~14 g more if the cone wall is thinned to 0.8 mm. The row errs on the safe side in the
direction that matters a mass optimisation: it understates the gain and overstates the cost.
The 42.7 g is not removable *in full* (a printed surface must exist, and ~28 g of it is that
surface), so the honest correction is **−69.121 g → −69.1 … −83 g**, still written as a band.

---

## 6. Limitations — what this does and does not establish

1. **All stress numbers are the repaired design intent, not the file on disk.** The exported body
   is four disjoint solids over 77.165 mm; until the +97 g Boolean repair lands, no load path
   exists and the wall's stress is undefined, not large.
2. **No duct bores and no side slots in the model.** Deliberate: they start at z = −112 and z = −70,
   aft of the region that carries the battery. The bore-limited section at the wing station is
   where case (b) lives, and it is evaluated ANALYTICALLY only (§1.2). A model that included the
   bores would be the right tool for case (b), not for this one.
3. **The clamped ring at z = −112 is the least physical thing in the model**, and it owns the global
   peak stress. The real boundary is a transition frame; a clamped shell edge over-predicts both
   stiffness and peak stress. Treat 2.85–3.23 MPa as an **upper bound**, and 1.78 MPa as the
   number to design to.
4. **Peak stress is not fully mesh-converged** (+13 % from 1.43× refinement at the clamp, +4 % in the
   bay field, +5 % on the 95th percentile). That is why every judgement above uses the refined
   value, and why the verdicts are stated against a 5× margin rather than a tight one.
5. **Untested modes:** buckling was not re-run in this model (the prior sector result is cited, not
   reproduced); no frequency/eigenvalue step, hence no √E check; no fatigue, no impact, no
   handling, no fastener pull-through, no bond-line shear, no printed anisotropy, no creep.
6. **The allowables are ASSUMED.** The programme's materials audit is blocked — no supplier, no
   layup, no coupon data. 17.3 and 250 MPa are engineering placeholders derived as stated in §3.2;
   a real coupon could move the PLA number by 2×, which is the largest single uncertainty here.
   The *ranking* (adequate / conservative C1) survives ±2×.
7. **The 6 g limit is the programme's own retention requirement, not a landing-impact measurement.**
   A wing-drop or a 3 m/s hard landing on this mass would plausibly produce more; the scaling is
   linear, so at 20 g (ASSUMED crash) the peak becomes 5.4 MPa and the FoS 3.2 — still adequate.

---

## 7. Files

| file | what it is |
|---|---|
| `REPORT.md` | this report |
| `measure_body.py` → `measure_body.json` | BRepCheck on all six shells, per-solid volumes/areas/bboxes/t_eff, rail hardware footprint |
| `make_decks.py` → `runs/*/body.inp`, `meta.json` | the shell generator: superellipse loft + aperture + loads → six CalculiX decks |
| `post.py` → `results.json`, `scaling.json` | displacement and von Mises extraction from each `.dat`, zone breakdown, applied root moment, the 1/E and E-invariance checks |
| `section_check.py` → `section_check.json` | independent thin-wall section properties (Zx, ybar) and the M/Zx cross-check |
| `runs/<case>/ccx_stdout.log` | CalculiX 2.21 stdout, `Total CalculiX Time` and `maxRSS` per case |
| `E:/engineering-portfolio-audit/scripts/body_struct_run.sh` | WSL runner (scripts dir, not a repo), `OMP_NUM_THREADS=1`, niced |

Reproduce:

```
cd E:/engineering-portfolio-audit/evidence/body-structure
"C:/Program Files/Python312/python.exe" measure_body.py      # ~3 min (STEP imports)
"C:/Program Files/Python312/python.exe" make_decks.py
wsl -d Ubuntu2404 -- bash /mnt/e/engineering-portfolio-audit/scripts/body_struct_run.sh
"C:/Program Files/Python312/python.exe" post.py
"C:/Program Files/Python312/python.exe" section_check.py
```

No BOARD CORRECTION is raised: `AGENT_BOARD.md` carries no Phase-15 body structural figure.