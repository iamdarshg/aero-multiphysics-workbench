# DM-G2 — Wall Treatment (y+) Assessment of the Passing All-Tet Mesh

**Scope.** This document answers one question only: *what wall treatment does the
DM-G2 c1 mesh actually imply for the Phase-15 transonic campaign?* It makes **no**
claim about solver accuracy, convergence, or force/drag results. It is a
mesh/wall-treatment assessment.

**Mesh assessed.** `cand-c/wing_centerline_t30_c1.msh`
(`sha256 7fadb8d7bc42fad17d5f5d000fb34449ccdb31d95d0494e51058eda25cbae08d`),
1,690,534 cells, **100 % tetrahedra, zero prism layers**.

**Basis for the mesh quality claim.** `checkMesh -allTopology -allGeometry` in
`opencfd/openfoam-default:2406` prints `Mesh OK.` (0 failed checks). Full log:
[`checkMesh-c1-FINAL.log`](checkMesh-c1-FINAL.log).

---

## 1. Headline result

| Anchor | M | U (m/s) | Re_c root | Re_c tip | y+ (root) | y+ (tip) |
|---|---|---|---|---|---|---|
| 700 km/h IAS | 0.676 | 222.13 | 1.48e6 | 1.16e6 | **134** | **137** |
| 800 km/h IAS | 0.769 | 252.81 | 2.18e6 | 1.72e6 | **191** | **195** |
| 900 km/h IAS | 0.862 | 283.17 | 3.07e6 | 2.41e6 | **261** | **267** |

y+ is evaluated at the **median** wall-normal first-cell distance
(y = 0.8415 mm) measured from the actual mesh.

**Verdict: this mesh sits in the wall-function regime, but its margin shrinks to
nothing at the top anchor. It is never in the buffer region.**

- **700 / 800 km/h — wall-function treatment is appropriate** (median y+ 134 / 191;
  at most 0.9 % of the wall above y+ 300).
- **900 km/h — material limitation.** Median y+ is 261 and **21–24 % of the wall
  surface exceeds y+ 300** (max ~495). Nearly a quarter of the wall would sit
  outside the validated wall-function band. This is a quantified limitation to
  quote, not a footnote.

Crucially, **no part of the surface is in the buffer region (y+ 5–30) at any
anchor** — this is *not* a y+ 5–30 blocker. §5 gives the exact per-anchor
fractions.

---

## 2. Air properties and assumptions

- **Temperatures.** ISA at 3 km: `T = 288.15 − 0.0065 × 3000 = 268.65 K`.
- **Viscosity.** Sutherland's law at 268.65 K:
  `μ = 1.716e-5 (T/273.15)^1.5 (273.15+110.4)/(T+110.4) = 1.6936e-5 Pa·s`.
  (Catalog value at 288.15 K is 1.789e-5 Pa·s; using it instead would change y+
  by only −5 %.)
- **Density.** From the brief's static pressures, `ρ = p/(R T)`, `R = 287.05 J/(kg·K)`:

| Anchor | p (Pa) | ρ (kg/m³) | ν = μ/ρ (m²/s) |
|---|---|---|---|
| 700 km/h | 22,429 | 0.29085 | 5.823e-5 |
| 800 km/h | 29,053 | 0.37674 | 4.495e-5 |
| 900 km/h | 36,450 | 0.47266 | 3.583e-5 |

- **Chord.** Root 0.388 m, tip 0.305 m (Phase-15 half-wing section).
- **Boundary-layer model.** Flat-plate turbulent, as instructed. The real wing
  has pressure gradient, sweep and a TE region where this correlation is least
  accurate; the numbers below are the *estimate*, and the anchor-to-anchor trend
  (y+ rising with speed) is more reliable than any individual value.

---

## 3. Skin-friction and friction velocity

**Formulae used**, all evaluated as **local** flat-plate Cf at `Re_x = Re_c`:

| Correlation | Expression |
|---|---|
| Prandtl–Schlichting (local) | `Cf = 0.0592 / Re^0.2` |
| White, *Viscous Fluid Flow* 6.19 (local) | `Cf = 0.455 / ln²(0.06 Re)` |
| 1/7-power law, Massey | `Cf = 0.027 / Re^(1/7)` |
| 1/7-power law (variant) | `Cf = 0.026 / Re^(1/7)` |

The **central** Cf is the mean of these four; the spread is quoted as the band.
They agree to within ±1.9–3.4 %, which is far tighter than the modelling
uncertainty of the flat-plate assumption itself.

Then:
```
u_tau = U_inf · sqrt(Cf / 2)
y+    = ρ · u_tau · y / μ
```

### Why Karman–Schoenherr is NOT used

An initial attempt used `1/√(2Cf) = log₁₀(Re·Cf) − 0.65`. With that constant
the equation has a physical root near **Cf ≈ 3e-2** at Re ≈ 1.5e6 — an order of
magnitude above the accepted local value (~3.4e-3). Those constants belong to a
*different* definition (mean skin friction, ln-Re family). Using them would have
inflated u_tau by ~3x and produced y+ values around 400–780, i.e. a **false
buffer-region verdict**. It is excluded deliberately; this note exists so the
choice can be audited.

### Central values

| Anchor | Chord | Re_c | Cf (central) | band | u_tau (m/s) | band |
|---|---|---|---|---|---|---|
| 700 km/h | root | 1.480e6 | 3.480e-3 | 3.416–3.547e-3 | 9.266 | 9.180–9.355 |
| 700 km/h | tip | 1.164e6 | 3.622e-3 | 3.535–3.671e-3 | 9.453 | 9.339–9.517 |
| 800 km/h | root | 2.182e6 | 3.265e-3 | 3.196–3.356e-3 | 10.215 | 10.105–10.356 |
| 800 km/h | tip | 1.715e6 | 3.397e-3 | 3.345–3.473e-3 | 10.419 | 10.338–10.535 |
| 900 km/h | root | 3.066e6 | 3.089e-3 | 2.985–3.197e-3 | 11.129 | 10.940–11.321 |
| 900 km/h | tip | 2.410e6 | 3.213e-3 | 3.133–3.309e-3 | 11.349 | 11.207–11.517 |

---

## 4. The actual near-wall cell size (measured, not assumed)

`checkMesh` reports `Min/max edge length = 0.0007399138455 0.04672234702`.
An **edge length is not the wall-normal height**, so the real quantity was
measured directly from the converted `polyMesh` of the c1 mesh
(`tools/wall_distance.py`): for every one of the 21,680 `fsi` boundary faces,
the normal distance from the wall-face centre to the adjacent cell centre.
Cell centres are taken as the average of the cell's face centres (not the
volume centroid); for these near-wall tets the two differ by well under 1 %,
which is negligible against the spread reported below.

### Wall-normal distance, wall face centre → first cell centre (`fsi`)

| Statistic | Value (m) | Value (mm) |
|---|---|---|
| min | 4.5715e-4 | 0.457 |
| p1 | 6.1528e-4 | 0.615 |
| p5 | 6.7761e-4 | 0.678 |
| p25 | 7.6296e-4 | 0.763 |
| **median** | **8.4148e-4** | **0.841** |
| p75 | 9.4178e-4 | 0.942 |
| p95 | 1.1505e-3 | 1.150 |
| p99 | 1.2866e-3 | 1.287 |
| max | 1.5632e-3 | 1.563 |
| mean | 8.6626e-4 | 0.866 |

Minimum edge length of wall-adjacent cells: 7.3991e-4 m (min), 2.5749e-3 m (p5),
3.4055e-3 m (median), 4.3844e-3 m (max). Note that the *minimum edge* is a poor
proxy for the near-wall spacing: it is a tangential edge at the TE, whereas the
wall-normal first-cell distance is ~0.84 mm over half the surface.

Critically, **the variation is only ~3.4x from min to max** — this mesh has a
fairly uniform near-wall spacing because it has no boundary layers at all.
That uniformity is what makes a single y+ estimate meaningful.

---

## 5. Verdict, stated plainly

**Wall-function RANS is the only defensible treatment for this mesh at all three
anchors. It is well inside that regime at 700–800 km/h and only partly inside it
at 900 km/h. The mesh is never in the buffer region (y+ 5–30).**

| Anchor | y+ at median (0.841 mm) | y+ at min (0.457 mm) | y+ at p95 (1.150 mm) | y+ at max (1.563 mm) | % of wall > 300 | Status |
|---|---|---|---|---|---|---|
| 700 km/h | 134 / 137 | 73 / 74 | 183 / 187 | 249 / 254 | **0.0 %** | **OK** wall functions |
| 800 km/h | 191 / 195 | 104 / 106 | 261 / 267 | 355 / 362 | **0.6–0.9 %** | **OK**, marginal |
| 900 km/h | 261 / 267 | 142 / 145 | 357 / 364 | 485 / 495 | **21–24 %** | **WARNING — material** |

(root / tip values respectively.) The exceedance fractions are exact counts over
all 21,680 `fsi` faces (`tools/yplus_fraction.py`), not percentile interpolation:

| Anchor | u_tau root (m/s) | y+ median | % faces > 300 | % faces > 150 | % faces < 30 |
|---|---|---|---|---|---|
| 700 km/h | 9.266 | 134 | 0.0 | 24.8 | 0.0 |
| 800 km/h | 10.215 | 191 | 0.6 | 96.8 | 0.0 |
| 900 km/h | 11.129 | 261 | **21.2** | 100.0 | 0.0 |

### What this means

1. **700 km/h — clean.** Entire distribution 73–254; **no** wall face exceeds
   y+ = 300 and none falls below 30. A wall-function treatment is appropriate and
   y+ is not a limiting factor.
2. **800 km/h — usable, marginal.** Median ~191, and **only 0.6–0.9 %** of wall
   faces exceed y+ = 300 (up to 355–362 at the max). A sub-1 % tail is a normal
   modelling tolerance, not a validity failure.
3. **900 km/h — a material limitation, quote it as such.** Median ~261 is inside
   the upper band, and **21–24 % of the wall surface sits above y+ = 300**
   (reaching ~485–495 at the worst faces). Nearly a quarter of the wall would
   fall outside the wall-function validity range. This is **not** a footnote — it
   is a known, quantified limitation of this mesh at the top campaign anchor.

**No part of the surface is in the buffer region (y+ 5–30) at any anchor**
(`% faces < 30 = 0.0 %` everywhere). This is the crucial distinction: the mesh
never lands in the "neither wall functions nor low-Re is valid" regime.

### Robustness check — does the verdict survive a wrong turbulence assumption?

If the boundary layer on this small chord were **laminar** (Blasius,
`Cf = 0.664/√Re`, which gives a *lower* u_tau), the median y+ would be **53** at
700 km/h, **71** at 800 km/h and **92** at 900 km/h (max 99 / 132 / 170) — still
inside the wall-function band at every anchor, still never in 5–30. So the
"wall-function, not buffer" conclusion does not depend on the turbulent
correlation being exactly right; it would take a ~10x error in Cf to reach the
buffer region.

Note this cuts the other way for the 900 km/h warning: a laminar boundary layer
would *remove* the >300 tail. The 21–24 % exceedance figure assumes the fully
turbulent layer that a wall-function RANS model will itself impose, which is the
self-consistent assumption to use here.

**Consequence for DM-G3:** the mesh is not blocked by y+, but it forces a
wall-function wall treatment, and that choice must be fixed *before* the
campaign runs, because it determines the choice of wall function
(`nutkWallFunction` vs `nutUSpaldingWallFunction` vs a y+-insensitive variant)
and the near-wall turbulence modelling. `nutUSpaldingWallFunction` (a
continuous all-y+ formulation) is the safer choice for the 900 km/h anchor and
removes the sharpest edge of this problem without needing more mesh — that is a
modelling recommendation, not a measured result.

---

## 6. Cost of a wall-resolved (y+ ≈ 1) mesh

**First cell height for y+ = 1:**

| Anchor | h1 root (root chord) | h1 tip (tip chord) |
|---|---|---|
| 700 km/h | **6.28 µm** | 6.16 µm |
| 800 km/h | **4.40 µm** | 4.32 µm |
| 900 km/h | **3.22 µm** | 3.16 µm |

Design for the most demanding anchor (900 km/h): **h1 ≈ 3.2 µm**, roughly
**260x smaller** than the current 0.84 mm.

**Prism-stack thickness.** Using the turbulent flat-plate thickness at the TE,
`δ = 0.37 c Re_c^(−1/5)`, and requiring the stack to reach 30 % of δ (so the
outer prism edge lands in fully turbulent flow rather than mid-boundary-layer):

| Anchor | Chord | δ_TE (mm) | target stack (mm) |
|---|---|---|---|
| 700 km/h | root / tip | 7.40 / 6.91 | 2.22 / 2.07 |
| 800 km/h | root / tip | 7.75 / 6.39 | 2.32 / 1.92 |
| 900 km/h | root / tip | 7.24 / 5.97 | 2.17 / 1.79 |

**Layer count vs growth ratio** (900 km/h root, h1 = 3.22 µm, target 2.17 mm):

| Growth ratio r | Layers needed | Stack H (mm) | Mean layer height (mm) |
|---|---|---|---|
| 1.10 | 45 | 2.31 | 0.051 |
| 1.15 | 34 | 2.46 | 0.072 |
| 1.20 | 27 | 2.20 | 0.081 |
| 1.25 | 24 | 2.71 | 0.113 |

A practical specification is **~25–30 layers, h1 ≈ 3.2–4.4 µm, growth ratio
1.15–1.20**, stack thickness ~2.2–2.5 mm.

**Cell count.** Wall surface area measured from the c1 mesh:
`fsi` 0.132414 m² + `rootWall` 0.007960 m² = **0.140374 m²**, with
21,680 + 1,582 = **23,262** wall triangles. Prisms are one per wall triangle per
layer:

| Layers | Prism cells | vs current 1.69 M |
|---|---|---|
| 20 | 465,240 | +28 % |
| 25 | 581,550 | +34 % |
| 30 | 697,860 | +41 % |

So a wall-resolved mesh costs roughly **+0.5–0.7 M prism cells** on top of the
tet core — a moderate, not prohibitive, increase. The hard part is not the cell
count; it is that **Gmsh cannot build these prisms on this geometry** (see §7).

---

## 7. The real obstacle to wall resolution

The referenced constraint is that Gmsh refuses 3D boundary layers here:

```
Only 2D Boundary Layers are supported (curve N is adjacent to 2 surfaces)
```

The wing is a **closed solid**, so every trailing-edge and leading-edge curve is
shared by two surfaces. At t/c ≈ 0.077 (30 mm on a 388 mm chord) prisms require
either **a domain split at the trailing edge** or **per-surface extrusion**.

This is why the c1 mesh is 100 % tets and why y+ is uncontrolled: **there is no
prism layer to control it with.** Reaching y+ ≈ 1 is therefore a *geometry
engineering* task (TE split + O-grid or per-surface extrusion), not a meshing
parameter change. The +34 % cell count above understates the work involved.

A cheaper intermediate option exists: keep the all-tet mesh but add a
**near-wall refinement zone** with explicit first-cell height ~0.1 mm. That
would put y+ in the 30–70 range at 900 km/h (comfortably wall-function) without
any prism layers — at the cost of a large increase in tet count near the wall
and a much higher risk of exactly the sliver-cell problem documented in
[`REPORT_MESH.md`](REPORT_MESH.md). It is offered as an option, not a
recommendation, and its feasibility is unmeasured.

---

## 8. Summary for the campaign

| Question | Answer |
|---|---|
| Is the c1 mesh valid? | Yes — `checkMesh` prints `Mesh OK.` |
| What y+ does it imply? | 134 / 191 / 261 (root, median spacing) at 700 / 800 / 900 km/h |
| Wall function, low-Re, or buffer? | **Wall function.** Not buffer. |
| Safe at 700 km/h? | Yes, cleanly (73–254, 0 % above 300) |
| Safe at 800 km/h? | Yes, marginal (<1 % of wall above 300) |
| Safe at 900 km/h? | **No — material limitation: 21–24 % of wall above y+ 300** |
| First-cell height for y+ = 1 | ≈ 3.2 µm (900 km/h) to 6.3 µm (700 km/h) |
| Prism layers for y+ = 1 | ~25–30 layers, r = 1.15–1.20, stack ~2.2–2.5 mm |
| Cell-count cost | +0.5–0.7 M prisms (+28–41 %) — **blocked by Gmsh geometry**, needs a TE split |

---

## Reproducibility

Every number in this report is produced by a script in [`tools/`](tools/):

| Script | Produces |
|---|---|
| `wall_distance.py` | §4 near-wall first-cell distance distribution |
| `wall_area.py` | §6 wall patch areas |
| `screen_quality.py` | internal tet screening during meshing |
| `yplus.py` | §2–§5 properties, Cf, u_tau, y+, y+ = 1 heights |
| `yplus_fraction.py` | §5 exact % of all 21,680 `fsi` faces above/below y+ thresholds |
| `yplus_cost.py` | §6 layer count, stack thickness, prism counts |

Machine-readable outputs: [`logs/yplus.json`](logs/yplus.json) and
[`logs/yplus_cost.json`](logs/yplus_cost.json).

Re-run:
```
python tools/yplus.py      --y 0.000841476 --json logs/yplus.json
python tools/yplus_cost.py --area 0.140374 --mean-y 0.0008662634 --json logs/yplus_cost.json
python tools/wall_distance.py  work-yp --patches fsi
python tools/yplus_fraction.py work-yp
```
(`work-yp` is a scratch `gmshToFoam` conversion of the c1 `.msh`; it is rebuilt
by converting `cand-c/wing_centerline_t30_c1.msh` into a copy of `case-fine`.)