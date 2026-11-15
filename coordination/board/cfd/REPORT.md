# DM-CFD-WALLS — patch inventory, and the fsi-vs-wall force comparison

Provenance labels used throughout: **SOLVER** (this run), **MEASURED** (read
from mesh/case files), **ANALYTICAL** (closed-form), **ASSUMED** (stated, not
verified).  Nothing in this document is a converged aerodynamic coefficient —
see §7.

Case under audit: `/root/dmconv` (WSL Ubuntu2404), `rhoPimpleFoam` 2406,
1,690,534 cells, 6 ranks, 8 vCPU / 3.9 GB RAM.
Output tree: `E:\engineering-portfolio-audit\evidence\dm-cfd-walls\`.

---

## 0. Verdict

1. **The brief's stated defect is falsified.** `fsi` is *not* the root cut
   plane.  It is the wetted wing skin (21,680 faces, 0.13241 m², no-slip with
   full turbulent wall functions).  The actual root cut plane is `rootWall`
   (1,582 faces, `symmetryPlane`) and it was already **excluded** from the
   force set.  Relative to that hypothesis, the case was already correct.
2. **A real and larger defect exists at the same place, for a different
   reason.** The forces are integrated with *absolute* pressure over an
   *open* surface (`fsi`'s only hole is the root cut, which `rootWall`
   closes).  The resulting bias is exactly
   `p_ref · Σ Sf = 70,100 × (−0.0079598) = −557.99 N`, i.e.
   **Cs = −0.39966**.  Measured contamination: **ΔCs = +0.399659**
   (SOLVER), *identical at all 75 matched instants* because it is a geometric
   property, not a flow property.  That is 1.02× the quoted magnitude of
   `Cs = −0.3944`, because the true spanwise coefficient is positive: the
   corrected value is **Cs = +0.0061** (window mean, SOLVER), 64× smaller.
4. **Cd and Cl are *not* contaminated by this**, and this is a
   machine-precision result, not a judgement: `Σ Sf_y` and `Σ Sf_z` over the
   patch are zero to 1e-16 m², so the bias has *no* lift or drag component
   (ANALYTICAL + MEASURED).  Confirmed by SOLVER: `Cd_wall/Cd_fsi = 1.000000`
   and `Cl_wall − Cl_fsi = 0` at every one of the 75 instants.  The earlier
   instruction that "Cd and Cl … must not be quoted" is over-broad: they are
   unaffected by the patch/pressure error.  They are, however, unconverged
   (§7), which is a separate and sufficient reason not to quote them.
5. **No axis mis-sign.** Streamwise drag is +z, lift +y, spanwise +x,
   confirmed three independent ways (§3).
6. **No coefficient is quotable.** The transient is still developing: `Cl`
   still drifts −12 % per window with 3.8 % scatter at t/c ≈ 0.49 (§7).

---

## 1. Patch inventory (MEASURED)

`constant/polyMesh/boundary` contains exactly **five** patches — there is no
separate `walls`/`wingUpper`/`wingLower`/`tip` patch set to switch to.  Areas,
planarity (`|ΣSf| / Σ|Sf|`; 1.0 = perfectly flat) and bounding boxes computed
by direct integration over `points`/`faces` (`scripts/02_patch_geom.py`).

| # | patch | type | nFaces | area [m²] | planarity | bbox x / y / z [m] | classification |
|---|-------|------|--------|-----------|-----------|--------------------|----------------|
| 1 | `fsi` | wall | 21,680 | 0.13241 | 0.0601 | [0.0803, 0.2600] / [−0.0152, 0.0149] / [−0.2325, 0.1562] | **wetted aerodynamic wall** — wing upper + lower + LE + TE + tip cap |
| 2 | `rootWall` | symmetryPlane | 1,582 | 0.00796 | **1.0000** | x = 0.0803 const | **root cut plane** (not wetted; a plane of mathematical symmetry) |
| 3 | `farfield` | patch | 42,490 | 7.17776 | 0.0000 | [−0.4046, 0.7449] / [−0.3500, 0.3500] / [−0.6205, 1.3200] | farfield / freestream |
| 4 | `outlet` | patch | 4,760 | 0.80464 | 1.0000 | z = +1.3200 const | outlet (downstream, +z) |
| 5 | `inlet` | patch | 4,760 | 0.80464 | 1.0000 | z = −0.6205 const | inlet (upstream, −z) |

Total boundary area 8.92741 m² (`fsi` is 1.5 % of it).

**Region census *inside* the one wetted patch** (`scripts/04_fsi_regions.py`,
`42_areavec.py`) — because the mesh does not split the wing into per-surface
patches, the brief's expected "wing upper / lower / tip" categories exist only
as face subsets:

| region | faces | area [m²] | ΣSf_x [m²] | ΣSf_y [m²] | ΣSf_z [m²] |
|--------|-------|-----------|------------|------------|------------|
| upper (n_y > 0.5) | 10,077 | 0.06265 | −0.000862 | +0.062099 | +0.000101 |
| lower (n_y < −0.5) | 10,091 | 0.06261 | −0.000482 | −0.062099 | −0.000870 |
| tip cap (n_x < −0.9, x = 0.26000 exactly) | 1,312 | 0.00626 | −0.006258 | 0.000000 | 0.000000 |
| TE flank (n_z > 0.5) | 200 | 0.00090 | −0.000358 | 0.000000 | +0.000769 |
| **Σ fsi** | **21,680** | **0.13241** | **−0.007960** | **−0.000000** | **−0.000000** |

Note the y-column: upper and lower cancel to the last printed digit, which is
what makes the lift bias identically zero.

---

## 2. `fsi` is the wetted wing, not a plane — five independent proofs

1. **Planarity 0.060 vs 1.000.** A flat plane has `|ΣSf| = Σ|Sf|`.  `fsi`
   has `|ΣSf| = 0.00796` against `Σ|Sf| = 0.13241` — five hundredths.  The
   actual plane, `rootWall`, scores exactly 1.0000 (MEASURED).
2. **Extent on all three axes.** `fsi` spans 0.1797 m (span x), 0.0301 m
   (thickness y), 0.389 m (chord z).  A cut plane has zero extent along its
   normal (MEASURED).
3. **It reproduces the reference quantities.** Planform area from the patch is
   0.062449 m² vs `Aref` 0.062249; mean chord 0.34752 m vs `lRef` 0.34646
   (both 0.3 % — bin-integration coarseness) (MEASURED).  `Aref` and `lRef`
   were evidently taken *from this wetted surface*, which is only consistent
   if it is the wing.
4. **Full turbulent wall treatment in every field.** `U noSlip`,
   `nut nutkWallFunction`, `k kqRWallFunction`, `omega omegaWallFunction`,
   `alphat compressible::alphatWallFunction`, `p/T/h/rho zeroGradient`
   (MEASURED).  A coupling/root plane would not carry wall functions.
5. **`ΣSf(fsi) = −ΣSf(rootWall)` exactly** — (−0.007960, 0, 0) vs
   (+0.007960, 0, 0) (MEASURED).  The skin's single opening is precisely the
   root aperture that `rootWall` closes.  This is the geometric statement that
   `fsi` is an *open* wetted surface, and it is the root cause of §4.

Conclusion: the prior report's warning ("the fsi patch is a plane, not a
wetted surface … would double-count and add a spurious spanwise force") is
correct in its *mechanism* — an open-surface integration *does* add a spurious
spanwise force — but it is attached to the wrong patch and the wrong remedy.
The patch that must not be integrated *alone* is `fsi`, and the fix is to
close it (or subtract `p_ref`), not to move the integration to another patch,
because there is no other wetted patch in this mesh.

---

## 3. Direction convention — the mis-sign hypothesis, tested and rejected

Stated explicitly (this is the contract for every number below):

| quantity | axis | evidence |
|---|---|---|
| streamwise / drag | **+z** | `U` inlet/farfield `(0 0 222.132204297)` (MEASURED) |
| lift | **+y** | `liftDir (0 1 0)`, and the wing's thickness is along y (MEASURED) |
| spanwise / side | **+x** | `sideDir (1 0 0)`, span x ∈ [0.0803, 0.2600] (MEASURED) |
| pitch axis | **+x** | `pitchAxis (1 0 0)`, `rollAxis +z`, `yawAxis +y` (MEASURED) |
| leading edge → trailing edge | min z → max z | planform sweep, `scripts/07_mac.py` (MEASURED) |

The flow therefore runs LE→TE in +z, which is the same sense as `dragDir` —
consistent.  Three checks were made:

1. **Algebraic reproduction from the raw force components** (SOLVER).  At the
   final instant t = 7.64634850e-4 s the `fsi` raw force is
   `F = (−548.757, −18.512, +25.785)` N (absolute `p`) and
   `(+9.233, −18.512, +25.785)` N (gauge); with `q·Aref = 1396.166 N`,
   `F_z/(qA) = +0.018468` = reported `Cd`,
   `F_y/(qA) = −0.013259` = reported `Cl`,
   `F_x/(qA) = −0.393046` = reported `Cs`.  The coefficient file is a
   pure projection of the force vector onto `(dragDir, liftDir, sideDir)`;
   no swap, no sign flip.  Note `F_y` and `F_z` are *identical* between the
   two conventions — the only component that moves is `F_x`.
2. **`directForceDirs` equivalent.** OpenFOAM 2406's `forces` object has **no
   `directForceDirs` entry** — that is a Fluent concept (source checked:
   `src/functionObjects/forces/forces/forces.C`); the OpenFOAM equivalent is
   the `(dragDir, liftDir, sideDir)` triple plus `coordinateSystem`/`CofR`.
   The requested sanity check was therefore implemented as the *second `CofR`*
   option (below), plus the algebraic check (1).
3. **Second `CofR` at the MAC quarter chord** (SOLVER), `CofR (0.16658 0
   −0.10529)` — MAC station measured as x = 0.16658, chord there
   0.34813 m, LE z = −0.19233 (MEASURED).  `Cd`, `Cl`, `Cs` stay
   **bit-identical** (a force must not depend on `CofR`), while `CmPitch`
   moves `1.113686e-2` (origin) → `9.970178e-3` (quarter chord), i.e.
   `−1.16668e-3`.  That shift is not free: at t = 4.028e-4 s,
   `F = (−1.9728, 5.3599, 40.2115) N` (gauge) and `d = CofR`,
   `ΔM_x = −(d × F)_x = −(−0.10529 × 5.3599) = −0.56435 N·m`, and
   `ΔCmPitch = −0.56435/(q·Aref·lRef) = −1.1667e-3` (ANALYTICAL) against the
   measured −1.16668e-3.  The moment arm is therefore arithmetically
   consistent with the stated axes and reference area/length.  It also drives
   `CmRoll` to `−9.1e-6` (≈0) at the quarter chord, as expected for a wing
   whose load is carried near mid-chord.

**Conclusion: the `Cs` anomaly is not a mis-signed or swapped axis.** `Cs` is
genuinely the +x (spanwise) force component, and it is genuinely large in the
absolute-pressure integral — for the reason in §4.

---

## 4. The actual defect: reference-pressure bias over an open surface

### 4.1 The identity

For a patch `P` integrated with pressure `p = p_ref + p'`,

```
F(P) = Σ_P p · Sf = Σ_P p' · Sf  +  p_ref · Σ_P Sf
                    └ gauge ┘      └ bias ┘
```

For a **closed** surface `Σ Sf = 0` and the bias vanishes identically — which
is why this trap is invisible on closed bodies.  `fsi` is **open** at the root
(§2.5), so `Σ Sf = (−0.007960, 0, 0) ≠ 0` and the bias is real (ANALYTICAL).

### 4.2 Numbers (all three agree)

| quantity | value | label |
|---|---|---|
| `p_ref` (outlet/farfield fixed pressure) | 70,100 Pa | MEASURED |
| `Σ Sf_x` over `fsi` | −0.0079598 m² | MEASURED |
| predicted bias force | −557.982 N | ANALYTICAL |
| predicted bias in `Cs` | **−0.399653** | ANALYTICAL |
| measured shift, `F_x(gauge) − F_x(abs)`, final instant | **+557.990 N** | SOLVER |
| measured shift, `Cs(gauge) − Cs(abs)`, all 75 instants | **+0.399659** (identical every row) | SOLVER |
| residual vs ANALYTICAL | 0.009 N = 1.5e-5 relative | derived |
| `Cs` absolute-p (final instant) | −0.393046 | SOLVER |
| `Cs` gauge / pRef (final instant) | +0.006613 | SOLVER |
| `Cs` closed surface `fsi+rootWall` (final instant) | −0.001800 | SOLVER |
| `q`, `q·Aref`, `q·Aref·lRef` | 22,428.73 Pa, 1396.166 N, 483.72 N·m | ANALYTICAL |

The measured and predicted shifts agree to 1.5e-5 relative; the residual is
the difference between my own triangulated `ΣSf` and OpenFOAM's face vectors
on warped faces, not a physical discrepancy.

### 4.3 Attribution of the bias (MEASURED geometry, ANALYTICAL force)

| region | bias_x [N] | share |
|---|---|---|
| tip cap (1,312 faces at x = 0.26000, normals −x) | −438.71 | 78.6 % |
| upper + lower skin (sweep-induced x-projection) | −94.18 | 16.9 % |
| TE flank | −25.10 | 4.5 % |
| **total** | **−557.99** | 100 % |

So the "spurious spanwise force" is not the physical spanwise load of a
tapered wing either: it is `p_ref` acting on the projected area of the *open*
integration surface, four fifths of it on the tip cap whose pressure is simply
the freestream pressure.

### 4.4 Why `Cd`, `Cl` (and `CmPitch`) are immune, exactly

`Σ Sf_y = −8.6e-17 m²` and `Σ Sf_z = −6.9e-18 m²` (MEASURED), so
`p_ref · ΣSf_y = −6e-12 N` and `p_ref · ΣSf_z = −5e-13 N` — below the
10-digit output precision.  Confirmed by SOLVER: `Cd`, `Cl`, and `CmPitch` are
bit-identical between the absolute-p and the pRef objects at every matched
instant.  Moments that mix `F_x` with a moment arm are affected (at
t = 4.028e-4 s): `CmYaw` 6.969e-2 → −1.031e-2, `CmRoll` 1.170e-3 → 1.837e-3
(SOLVER).

Remedy: `pRef 70100;` on the `forces`/`forceCoeffs` object.  OpenFOAM 2406
honours it for compressible runs — `rho(p)` returns 1 for a dimensional `p`
(`forces.C`), so `fP = Sf·(p − pRef)`.  This was verified from the source
*and* from the solver acknowledging `Reference pressure (pRef) set to 70100`
in the log.

---

## 5. Corrected configuration actually run

Function objects are built at startup, so the case was **restarted from the
latest written time** (t = 3.97942340e-4 s), not from zero and not by editing
the dictionary under the running job.

`system/controlDict` (full text: `case-artefacts/controlDict.walls`); physics,
schemes, solvers, `deltaT`, `endTime`, `writeInterval` byte-identical to the
pre-restart case:

| object | type | patches | pRef | CofR | purpose |
|---|---|---|---|---|---|
| `fForces`, `fCoeffs` | forces / forceCoeffs | `(fsi)` | — | (0 0 0) | **the old numbers, kept** for a same-instant A/B |
| `wForces`, `wCoeffs` | forces / forceCoeffs | `(fsi)` | 70100 | (0 0 0) | **corrected** wetted-surface force |
| `cCoeffs` | forceCoeffs | `(fsi rootWall)` | — | (0 0 0) | independent cross-check: closing the surface |
| `qCoeffs` | forceCoeffs | `(fsi)` | 70100 | (0.16658 0 −0.10529) | quarter-chord `CofR` sanity |

Restart fidelity (SOLVER): at **all 69 instants** present in both the
pre-restart trace and the new `fCoeffs` trace all twelve coefficients agree to
**max relative difference 0.000e+00** — bit-identical.  The restart therefore
changed the measurement, not the flow.

Ranks/RAM: 6 ranks held (`~420 MB`/rank, `available` 3.4 GB at launch).  No
reduction was forced; an 8-rank decomposition was not attempted because the
box has 3.9 GB total and the 6-rank decomposition was already validated.

End state of the case: the run stopped at its own 3300 s wall cap
(exit 124, 76 steps, `t = 7.6954e-4`, `.done` written, no NaN / no bounding /
no fatal).  `system/controlDict` currently **holds the corrected version with
all five objects**; the exact pre-restart dictionary is preserved at
`case-artefacts/before-restart/controlDict.fsi-only`, so either configuration
can be relaunched from `latestTime` without touching the mesh or the
decomposition (which were never modified).

---

## 6. The fsi-versus-wall comparison (SOLVER)

Same patch, same instant, same field — the only difference is `pRef`.  This
is the cleanest possible controlled comparison: it isolates the integration
convention with zero flow-history confound.

75 matched instants, t = 4.0282147e-4 … 7.6463485e-4 s (t/c 0.258 … 0.490),
6 ranks, 76 steps, wall 3303 s.

| t [s] | t/c | Cd_fsi | Cd_wall | Cl_fsi | Cl_wall | Cs_fsi | Cs_wall | ΔCs |
|---|---|---|---|---|---|---|---|---|
| 4.0282147e-4 | 0.258 | 2.880138e-2 | 2.880138e-2 | +3.839012e-3 | +3.839012e-3 | −4.0107218e-1 | −1.412999e-3 | +3.9965918e-1 |
| 6.1283440e-4 | 0.393 | 2.089895e-2 | 2.089895e-2 | −8.59566e-3 | −8.59566e-3 | −3.9590655e-1 | +3.75262e-3 | +3.9965918e-1 |
| 6.8622499e-4 | 0.440 | 1.949267e-2 | 1.949267e-2 | −1.148338e-2 | −1.148338e-2 | −3.9439984e-1 | +5.25934e-3 | +3.9965918e-1 |
| 7.6463485e-4 | 0.490 | 1.846835e-2 | 1.846835e-2 | −1.325913e-2 | −1.325913e-2 | −3.9304590e-1 | +6.61328e-3 | +3.9965918e-1 |
| **final 20 % window mean (n=15)** | 0.45–0.49 | **1.889100e-2** | **1.889100e-2** | **−1.258550e-2** | **−1.258550e-2** | **−3.9360e-1** | **+6.057e-3** | **+3.9965918e-1** |

The `t = 6.8622499e-4` row is worth noting: its absolute-p `Cs = −0.3943998`
reproduces the brief's quoted `−0.3944` to five digits, which is the direct
confirmation that the number under audit came from exactly this quantity.

| metric | value | label |
|---|---|---|
| **Cd_wall / Cd_fsi** | **1.000000** (mean = min = max over n = 75; bit-identical rows) | SOLVER |
| **Cl_wall − Cl_fsi** | **0.000e+00** at all 75 instants | SOLVER |
| **\|ΔCs\| = Cs_wall − Cs_fsi** | **0.399659**, constant to six decimals at all 75 instants | SOLVER |
| `Cs` from closed surface `cCoeffs` (window mean) | −1.849e-3 (scatter 0.8 %) | SOLVER |
| gauge-vs-closed difference in `Cs` | 7.906e-3 = root cut-plane gauge load | SOLVER |

Reading of the comparison:

- **The contamination is exactly one number, and it is spanwise.** `Cd` and
  `Cl` are bit-identical; there is no drag or lift contamination to report.
  So the requested ratio is 1.000000 by construction, not by cancellation.
- **Two independent corrections bracket the true `Cs`.** Subtracting `p_ref`
  on the open skin gives `Cs = +6.06e-3`; closing the surface with `rootWall`
  and integrating absolute pressure gives `Cs = −1.85e-3`.  Both are
  ~O(1e-3–1e-2), i.e. **~60–200× smaller than the quoted −0.394**.  They
  differ by the gauge pressure load carried on the root cut plane, which is
  the physical spanwise load transmitted into the structure and correctly
  *not* part of the wing's aerodynamic coefficient.
- The bias is therefore not a modelling subtlety that convergence will fix:
  it will sit at `−0.3997` no matter how long the run continues, because it
  depends only on `p_ref` and the patch's projected area.

---

## 7. Convergence — no coefficient is quotable

**No. Nothing here is converged, and no coefficient below should be quoted as
an aerodynamic coefficient.**

Method: final-20 %-window statistics (mean, standard deviation, linear drift),
the same criterion the case's own `analysis.md` used — not visual inspection.

| series (final 20 % window) | n | mean | sd | scatter | drift over window |
|---|---|---|---|---|---|
| `Cd` (wall = fsi, identical) | 15 | 1.8891e-2 | 2.791e-4 | 1.5 % | −8.73e-4 (−4.6 % of mean) |
| `Cl` (wall = fsi, identical) | 15 | −1.2586e-2 | 4.724e-4 | 3.8 % | −1.474e-3 (−11.7 %) |
| `Cs` wall (gauge) | 15 | +6.057e-3 | 3.728e-4 | 6.2 % | +1.166e-3 (+19 %) |
| `Cs` closed surface | 15 | −1.849e-3 | 1.500e-5 | 0.8 % | +4.30e-5 (+2 %) |

Why these are still transient, not coefficients:

- **`Cl` changes sign and moves 0.017 over 0.23 chords** (+3.84e-3 →
  −1.3259e-2 between t/c 0.258 and 0.490), and is still drifting −12 % per
  window at the end of the run.  A quantity drifting 12 % per window is not
  converged by any criterion.
- **`Cd` falls 36 %** over the same stretch (2.880e-2 → 1.8468e-2) and is
  still drifting −4.6 % per window.
- The brief's quoted 26 % scatter / −86 % drift came from a 27-row window of
  the spliced 148-row trace ending at t/c 0.418.  On the trace I actually
  have (69 rows, final 20 % = 14 rows) I measure `Cl` scatter 4.7 % and drift
  −14 %.  The two are not contradictory — the earlier window sat on the
  steeper part of the startup transient — but the conclusion is the same:
  **non-stationary**.
- The *contamination* number is the exception: `ΔCs = 0.399659` is quotable
  because it is geometric (§4) and does not depend on convergence.

Remaining compute (ANALYTICAL, from the measured 38.4 s/step clean-case rate
and mean Δt = 4.906e-6 s):

| target | t [s] | steps from t/c = 0.49 | clean config | with the 5 diagnostic objects |
|---|---|---|---|---|
| t/c = 1 | 1.5597e-3 | 159 | **1.7 h** | 2.4 h |
| t/c = 2 | 3.1194e-3 | 470 | **5.0 h** | 7.2 h |
| t/c = 5 (the case's own `endTime` = 8e-3 s) | 7.7985e-3 | 1406 | **15.0 h** | 21.5 h |

A single **4 h** wall cap — the cap the superseded run carried — buys 374
steps = 1.87e-3 s of convective time, reaching only **t/c ≈ 1.7**.  Reaching
t/c = 5 is a ~15 h clean run, so any claim of a converged coefficient on this
mesh requires either that budget or the usual steady-state alternative
(which this transonic case does not obviously admit).  Also note the wall
budget is RAM-bound, not core-bound: 6 ranks × ~420 MB is the limit at
3.9 GB total, so more ranks would need more RAM, not more vCPU.

---

## 8. Limitations and provenance notes

### 8.1 Provenance ledger

Every quantitative claim in this report, counted by provenance.  Nothing that
is ANALYTICAL or ASSUMED is presented as a measurement.

| provenance | what it covers | count |
|---|---|---|
| **SOLVER** | `Cd/Cl/Cs/Cm*` for all four objects at every instant; raw `F` components; restart-fidelity (0.000e+00); the 557.99 N measured shift; window statistics | 6 series + 2 scalar checks |
| **MEASURED** | patch face counts, areas, planarity, bounding boxes, `ΣSf` per patch and per region, planform/MAC/quarter-chord station, BC types, refs (`Aref`, `lRef`, `rhoInf`, `magUInf`), `p_ref` = 70,100 Pa, `ΔSf` residual 0.04 % | 5 patches + 4 regions |
| **ANALYTICAL** | `p_ref·ΣSf = −557.99 N`; bias `−0.399659` in `Cs`; zero bias in `Cl`/`Cd`; `ΔM_x = −0.56435 N·m → ΔCmPitch = −1.1667e-3`; `q`; `Re`; remaining-compute hours | 7 |
| **ASSUMED** | (i) the farfield thermodynamic state is uniform at 70,100 Pa / 268.65 K so a single `pRef` is exact; (ii) `rhoInf 0.9091` is the intended reference density; (iii) the case's `Aref`/`lRef` are the intended normalisers (0.3 % off the measured planform) | 3 |

### 8.2 Unknown / not established

- **The true converged `Cd`, `Cl`, `Cs` are unknown.** No value in this report
  is a converged coefficient. What is established is the *difference* between
  integration conventions, which is an exact property of the mesh and does not
  need convergence.
- **Whether the flow is physically converged at all** is unknown: the run has
  reached only t/c ≈ 0.4–0.6 of a 5-chord target, with 25 % scatter in `Cl`.
- **Not attempted:** an 8-rank decomposition (3.9 GB total RAM, 6 ranks already
  at 2.6 GB used); a sub-patch mesh split to make `forces` integrate
  upper/lower/tip separately (would require `topoSet`/`createPatch` +
  re-decomposition, and changes the mesh the running state lives on); a
  `foamToVTK` per-face decomposition (would have cost ~200 MB of conversion
  while the solver was RAM-limited).
- **Not attempted:** re-running from zero. Unnecessary — the restart is
  bit-identical (§5), so the corrected objects sit on exactly the state the
  contaminated ones were measuring.

### 8.3 Other notes

- Flow conditions for context only (ANALYTICAL; not used in any force
  calculation): `p = 70,100 Pa`, `T = 268.65 K`, `ρ = 0.9091 kg/m³`,
  `U∞ = 222.132 m/s`, `a = 328.6 m/s` → **M∞ = 0.676**;
  Sutherland μ ≈ 1.69e-5 Pa·s → **Re_c ≈ 4.1e6**; `q = 22,428.7 Pa`.
  The wing is at essentially zero incidence (chord along the freestream), so
  a small `Cl` near zero is the physically expected answer, not itself a
  symptom — the `Cs = −0.394` anomaly is a separate integration artefact.
- Every force/coefficient number here is **SOLVER** output from this run; the
  geometry, faces, areas and bounding boxes are **MEASURED** from
  `constant/polyMesh`; `p_ref·ΣSf` and the axis algebra are **ANALYTICAL**.
- The `q`/`Aref` normalisation was **taken as configured** (`rhoInf 0.9091`,
  `magUInf 222.1322`, `Aref 0.062249`, `lRef 0.34646`).  `Aref`/`lRef` were
  cross-checked against the measured planform (0.3 % agreement) and are fit
  for purpose.  `rhoInf 0.9091` corresponds to 70,100 Pa at 268.65 K
  (ANALYTICAL) and is consistent with the fixed inlet/farfield thermodynamic
  state.
- The reference pressure could in principle be taken as the *local*
  freestream rather than a single constant; `pRef 70100` is exact here because
  `inlet`/`outlet`/`farfield` all pin 70,100 Pa.
- The face areas and `ΣSf` are from my own triangulation of the polygonal
  faces; OpenFOAM's own `Sf` differs in the last digits on warped faces.  This
  is the residual in §4.2: ANALYTICAL 557.982 N vs SOLVER 557.990 N, i.e.
  **0.009 N (1.5e-5 relative)** — consistent with face-vector round-off, not a
  physical discrepancy.
- I did not re-run from zero, did not alter the mesh, did not commit, push or
  touch any `audit/*` branch, and wrote nothing outside
  `E:\engineering-portfolio-audit\evidence\dm-cfd-walls\` (the solver case
  stayed at `/root/dmconv` in WSL).

---

## Appendix — files

| file | contents |
|---|---|
| `REPORT.md` | this document |
| `case-artefacts/controlDict.walls` | corrected `controlDict` that was installed |
| `case-artefacts/controlDict.walls.installed` | the copy read back from the case |
| `case-artefacts/before-restart/` | the pre-restart `controlDict`, `solve.log`, the full 69-row contaminated trace, `polyMesh.boundary` |
| `case-artefacts/after-restart/postProcessing/` | all six corrected traces (`fCoeffs`, `wCoeffs`, `cCoeffs`, `qCoeffs`, `fForces`, `wForces`) + `solve.walls.log` |
| `case-artefacts/after-restart/comparison.csv` | per-instant fsi-vs-wall table (75 rows) |
| `window-stats.md` | raw output of the convergence/window computation |
| `scripts/02_patch_geom.py` | patch areas, planarity, bounding boxes |
| `scripts/04_fsi_regions.py` | face-region census and spanwise bins |
| `scripts/07_mac.py` | planform / MAC / quarter-chord station |
| `scripts/42_areavec.py` | exact `ΣSf` per region and bias attribution |
| `scripts/40_analyze.py` | comparison, window statistics, direction algebra |
| `scripts/41_repro.py` | restart-fidelity check |
| `scripts/43_convergence.py` | final-window statistics + remaining-compute estimate |
| `scripts/09_backup.sh`, `10_stop.sh`, `11_solve_walls.sh`, `12_launch.sh` | backup / graceful stop / corrected solve / detached launch |
| `scripts/20_sync.sh`, `21_peek.sh`, `23_probe.sh` | artefact sync and progress probes |