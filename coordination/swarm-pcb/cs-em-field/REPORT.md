# Code-SDR V2 — 0.23 mm RF50 traces field-solved on the board's own stackup

**Scope:** one item — EM-validate the V2 50 Ω traces with a real field solve on the
declared stackup. Read-only on the repo; every artefact is under
`E:/engineering-portfolio-audit/evidence/cs-em-field/`.
**Board commit:** `6fbc004af4bec9c5ec78e57709c7127a280489f6` on `work/2026-11-11`
(read only — no checkout, no write, no commit).

**Result in one line:** the 0.23 mm F.Cu microstrip solves to **49.4 Ω** on the
declared stack (50 Ω needs 0.2275 mm), i.e. the width *is* the matched width to
within ~1.1 %, and the worst band-edge mismatch is **−36.4 dB at 100 MHz**. The
impedance problem on this board is not the trace width.

---

## 1. Stackup, read from the board file (not assumed)

Source: `repos/Code-SDR/hardware/v2/Code-SDR-V2.kicad_pcb`, `(setup (stackup …))`
lines 44–105. `general.thickness` = 1.6 mm (line 6).

| # | layer / material | type | t (mm) | εr | tanδ |
|---:|---|---|---:|---:|---:|
| 1 | F.Mask | Top Solder Mask | 0.010 | **absent** | **absent** |
| 2 | F.Cu | copper | 0.035 | – | – |
| 3 | dielectric 1 | **prepreg** | **0.130** | **4.2** | **0.02** |
| 4 | In1.Cu | copper | 0.035 | – | – |
| 5 | dielectric 2 | core | 1.200 | 4.2 | 0.02 |
| 6 | In2.Cu | copper | 0.035 | – | – |
| 7 | dielectric 3 | prepreg | 0.130 | 4.2 | 0.02 |
| 8 | B.Cu | copper | 0.035 | – | – |
| 9 | B.Mask | Bottom Solder Mask | 0.010 | **absent** | **absent** |

- `epsilon_r 4.2` at **line 64**, `loss_tangent 0.02` at **line 65** — the
  dielectric table **is** present; only the solder-mask εr/tanδ are missing
  (mask thickness is given at lines 54 and 95, no material properties).
- `copper_finish "ENIG"` (line 103), `dielectric_constraints yes` (line 104).
- Nominal sum = **1.62 mm** vs the declared 1.60 mm — the same discrepancy the
  repo already flags in `STACKUP_DRAWING.md` (lines 19–21). The 0.13 mm prepreg
  is therefore a *nominal* value, not a pressed/finished one: this is an
  UNVERIFIED input to every number below (see §6).

**Reference plane for the traces that matter:** all 49 RF50 nets are on F.Cu
(580 of 593 segments), referenced to In1.Cu, which the design documents as an
uninterrupted ground plane (`FABRICATOR_IMPEDANCE_NOTE.md:13`). The 13 remaining
segments sit on B.Cu over the *split* In2 power plane — my microstrip model does
**not** apply to those (see §5.4).

## 2. Geometry actually routed (parsed, not quoted)

`01_extract_board.py` → `board_extract.json`.

- 12,253 track objects = 11,168 `segment` + 1,085 `via` (everything), layers:
  F.Cu 5,402, B.Cu 3,876, In1.Cu 786, In2.Cu 1,104.
- 49 RF50 nets present (the set in `tools/export_rf50_dsn.py:34-46`),
  **593 segments, all width 0.23 mm**, 10 vias, 660.0 mm total length.
  Width/layer histogram: `0.23 @ F.Cu` 580, `0.23 @ B.Cu` 13 → **uniform 0.23 mm
  is confirmed**, no 0.10/0.15 offenders on these 49 nets.
- Netclass `RF_50` in `Code-SDR-V2.kicad_pro` carries `track_width 0.23`
  (line 325) and `clearance 0.18` (line 314), but
  `"netclass_assignments": null` (**line 335**) and an empty
  `netclass_patterns` — **no net is actually assigned to RF_50**, so KiCad's
  DRC never enforces the 0.23 mm impedance width on this board. The width holds
  by router script convention only (`hardware/v2/tools/export_rf50_dsn.py:9-10`).

## 3. Method — 2D quasi-static Laplace, finite volume, written for this task

`02_fd_solve.py`. Solve ∇·(ε∇φ)=0 on the cross-section; rectilinear grid with
node lines forced onto every material interface (y = 0, h, h+t, h+t+t_mask and
x = ±w/2) so no cell straddles a boundary.
Dirichlet φ=1 on the copper bar, φ=0 on In1 and on a far box (11–45 h).
C from stored energy, cross-checked against total flux on the conductor
(`Q/C = 1.000000` at every resolution — the assembly, RHS and energy formula are
mutually consistent).

TEM relations: εeff = C_die/C_air, L = µ0ε0/C_air,
**Z0 = 1/(c·√(C_air·C_die))**. Dielectric loss from partial capacitances
(G = ω·(tanδ·C_sub_part + tanδ_mask·C_mask_part)), conductor loss from a
surface-resistance model, `Z0(f)=√((R+jωL)/(G+jωC))`,
`S11=(Z0−50)/(Z0+50)`.

Thickness is **geometric** (a real 0.23 × 0.035 mm bar), not a Δw correction.

### Validation of the solver

| check | value |
|---|---|
| w/h = 30 wide-strip limit vs ε0w/h | FD/analytic = 1.1005 (expected fringing, not error) |
| zero-thickness limit vs Hammerstad-Jensen 53.49 Ω | FD 53.71 Ω (**+0.4 %**) |
| resolution h/18 → h/120 (222×60 → 754×156) | 50.57 → 49.43 Ω, monotone, step −0.03 Ω at the end |
| box 11 h → 45 h | 49.28 → 49.54 Ω; 1/box fit → 49.65 Ω |
| flux vs energy | Q/C = 1.000000 |

Numerical uncertainty on Z0: **±0.2 Ω** (resolution + box).

Note on `compare_skrf.json`: that sweep runs the FD at h/30 for speed, where the
grid noise is ±0.8 Ω (it makes the t = 0/5/10 µm column look non-monotone). The
converged values are the ones in §4.1; the HJ column there reproduces skrf to
0.07 % on every row, which is how the closed-form cross-check was validated.

## 4. Results

### 4.1 Z0 at the width actually used

| model | Z0 (Ω) | εeff |
|---|---:|---:|
| **FD, mask 0.010 mm / εr 3.5, fills the trace trench (primary)** | **49.43** | 3.293 |
| FD, mask only above the copper (no trench fill) | 51.92 | – |
| FD, no mask at all | 52.57 | 2.912 |
| Hammerstad-Jensen, no mask (my implementation of the paper eqs.) | 50.05 | 3.017 |

C = 1.2246e-10 F/m, L = 2.9920e-7 H/m at the primary point.

### 4.2 Mask sensitivity (the mask εr is **not in the board file**)

| εr_mask | 3.0 | 3.5 | 4.0 | 4.5 |
|---|---:|---:|---:|---:|
| Z0 (Ω) | 49.92 | **49.43** | 48.98 | 48.56 |

±0.5 in εr_mask moves Z0 by ∓0.47 Ω. The mask *geometry* assumption is worth
2.5 Ω — larger than every numerical error here.

### 4.3 Width sweep 0.15–0.35 mm

`width_sweep.csv`, plot `z0_and_s11.png` (left panel). Monotone, ~−0.65 Ω per
+5 µm near the target:

| w (mm) | 0.150 | 0.180 | 0.200 | 0.210 | **0.230** | 0.250 | 0.300 | 0.350 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Z0 (Ω) | 60.46 | 55.76 | 53.08 | 52.05 | **49.50** | 47.41 | 42.89 | 39.30 |

**50 Ω width = 0.2275 mm** (bisection on the same model; Z0(0.23) = 49.43 Ω,
−1.1 % from 50 Ω). The 0.230 mm design width is 2.5 µm *wider* than the matched
width, which is why Z0 lands just under 50 Ω.

### 4.4 S11 at every band edge (`s11_vs_f.csv`, plot right panel)

Bands from `hardware/redesign/FREQUENCY_PLAN.csv`.

| band | edge | f (MHz) | Z0 (Ω) | S11 (dB) |
|---|---|---:|---|---:|
| LOW | lo | 100 | 49.47 − 1.41j | **−36.39** |
| LOW | hi | 2500 | 49.43 − 0.03j | −44.82 |
| HIGH_A | lo | 2300 | 49.43 − 0.04j | −44.81 |
| HIGH_A | hi | 4200 | 49.43 + 0.05j | −44.78 |
| HIGH_B | lo | 4200 | 49.43 + 0.05j | −44.78 |
| HIGH_B | hi | 6800 | 49.43 + 0.11j | −44.65 |
| HIGH_C high-side | lo | 6800 | 49.43 + 0.11j | −44.65 |
| HIGH_C high-side | hi | 7350 | 49.43 + 0.12j | −44.63 |
| HIGH_C low-side | lo | 7150 | 49.43 + 0.11j | −44.64 |
| HIGH_C low-side | hi | 9200 | 49.43 + 0.14j | −44.56 |
| HIGH_D | lo | 8000 | 49.43 + 0.13j | −44.60 |
| HIGH_D | hi | 10000 | 49.43 + 0.15j | −44.53 |

Worst: **−36.4 dB @ 100 MHz**, purely skin-effect: R = 13.2 Ω/m at 100 MHz vs
131.7 Ω/m at 10 GHz, which makes Z0 complex (49.47 − 1.41j) at the low edge.
Above 500 MHz the mismatch is a flat ≈ −44.5 dB.

### 4.5 Independent cross-check — scikit-rf MLine (1.9.0)

`skrf.media.mline.MLine`, quasi-static `zl_eff`, three internal models:

| model | t = 0 | t = 35 µm | vs FD no-mask (52.57) |
|---|---:|---:|---:|
| hammerstadjensen | 53.49 | 50.01 | −4.9 % |
| wheeler | 53.48 | 50.21 | −4.5 % |
| schneider | 53.18 | 53.18 (no t term) | +1.2 % |

At zero thickness my solver, my Hammerstad-Jensen implementation and all three
skrf models agree within 1 %. At the real 35 µm the closed forms split 50.0 /
50.2 / 53.2 and my exact-geometry solve gives 52.6 — the whole 5 % spread is the
strip-thickness correction, which the closed forms implement as a Δw fit
(`t/h = 0.27` here, outside the fit's stated range) while the FD carries the
copper as actual geometry. **That 5 % is a model-form uncertainty, not a
numerical one.** Applying it to the masked case gives Z0(0.23) ∈ [47, 50] with
49.4 as the central value.

## 5. Findings

1. **The width is right, within a percent — as drawn.** On the declared stack
   the 50 Ω width is 0.2275 mm and the board uses 0.230 mm (49.4 Ω, −1.1 %).
   As-etched the trace narrows and Z0 rises (§6). The earlier
   `docs/em-validation/EM_VALIDATION_REPORT.md` EM-5 figure of 46.6 Ω coincides
   with the IPC-2141 closed form on these dimensions
   (87/√(εr+1.41)·ln(5.98h/(0.8w+t)) = 46.5 Ω); a field solve does not
   reproduce it. EM-5 should be
   re-graded from "Z0 does not close at 50 Ω" to "matched to ≈1 %, model band
   47–50 Ω".
2. **The solder mask is uncharacterised** — 0.010 mm of material with no εr or
   tanδ anywhere in the board or the fab note. It is worth 0–3.1 Ω, i.e. more
   than the width error it is supposed to protect against.
3. **The impedance constraint is not enforced.** `RF_50` exists with
   `track_width 0.23` but `netclass_assignments` is null, so DRC cannot catch a
   0.23 → 0.15 regression. (The audit-era report's 0.10/0.15 mm offenders no
   longer exist on this commit; all 49 nets are 0.23 today — by script
   convention, not by rule.)
4. **Five nets leave the matched environment** — `LO_LOW_P/N`,
   `RF_HB_LNA_OUT`, `RF_HD_LNA_OUT`, `IF_SELECTED` route 13 segments on B.Cu
   over the **split** In2 power plane. Same reference-plane defect class the
   audit already reviewed. My number does not apply there.
5. **0.13 mm prepreg + 0.035 mm copper is a hard geometry** (t/h = 0.27). Every
   closed form in common use is outside its validity range, which is exactly
   why the field solve was needed and why the residual 5 % spread is model-form.

## 6. What is UNVERIFIED

- **PRESSED stackup.** The 0.13 mm prepreg, finished 0.035 mm copper and the
  etched trapezoid are nominal. The 49.4 Ω above is a *rectangular* 0.23 mm
  trace. At a 45° etch the top width would be 0.16 mm, whose rectangular bound
  is **58.8 Ω** (`fd_solve.json`); a true trapezoid lies between the two, so the
  as-fabricated Z0 is in the **49.4–58.8 Ω bracket** with the etch penalty
  unquantified — this is the single biggest reason the fab must return a coupon
  measurement, and it is exactly what `FABRICATOR_IMPEDANCE_NOTE.md` demands.
- **Laminate Dk vs frequency/position.** εr 4.2 flat, no Djordjevic-Svensson
  model, no glass-weave or thickness dependence. Only the fab's coupon data can
  close this.
- **Solder-mask εr/tanδ and the mask cross-section** (trench fill or not).
- **Discontinuities.** This is a 2D uniform-line solve: no pads, no 0.6/0.3 mm
  vias, no connector launch, no 0402/0603 pads, no line-to-line coupling, no
  ground-stitch spacing. Real S11 is set by those, not by the 0.23 mm width —
  they need a 3D full-wave solve (openEMS on WSL is available; none was run
  here) or a VNA/TDR coupon.
- **The 13 B.Cu segments over split In2** — no valid 2D model; needs the same
  full-wave/return-path work.
- **No measurement.** Nothing here is a measured S-parameter.

## 7. Artefacts and reproduction

All under `E:/engineering-portfolio-audit/evidence/cs-em-field/`:

| file | content |
|---|---|
| `01_extract_board.py` → `board_extract.json` | stackup, track counts, RF50 width/layer/per-net |
| `02_fd_solve.py` → `fd_solve.json`, `width_sweep.csv`, `s11_vs_f.csv`, `z0_and_s11.png` | primary solve, sweep, S11, plots |
| `03_crosscheck_skrf.py` → `compare_skrf.json` | FD vs skrf across w and t |
| `04_convergence.py` → `convergence_log.txt` | resolution/box study, closed-form comparison |
| `run_log.txt`, `crosscheck_log.txt`, `convergence_log.txt` | verbatim console output |

```
& "C:/Program Files/Python312/python.exe" 01_extract_board.py
& "C:/Program Files/Python312/python.exe" 02_fd_solve.py
& "C:/Program Files/Python312/python.exe" 03_crosscheck_skrf.py
& "C:/Program Files/Python312/python.exe" 04_convergence.py
```

Python 3.12.2, numpy 2.2.6, scipy 1.16.3, scikit-rf 1.9.0 (system interpreter;
the KiCad 9 python has no scikit-rf). Repo untouched: no branch operations, no
file writes, no commits.