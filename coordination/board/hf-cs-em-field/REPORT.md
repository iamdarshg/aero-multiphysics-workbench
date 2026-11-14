# hf-cs-em-field — HOTFIX 1 mirror

This item's first report lives at `../cs-em-field/REPORT.md` (kept for the record,
with the superseded numbers struck through). The hotfix below is the same text as
`HOTFIX 1` in that report; the solver artefacts it cites are in `../cs-em-field/`
(`05_hotfix_z0_band.py`, `hotfix_z0_band.json`, `hotfix_z0_band.csv`,
`hotfix_log.txt`, plus the original `02_fd_solve.py` / `fd_solve.json`), and copies
of the new files sit next to this one. Nothing was re-run for this mirror and the
repo was not touched.

---

# HOTFIX 1 — Z0 band re-derived from solver rows (supersedes the "47–50 Ω" claim)

**Verdict:** the band **47–50 Ω** printed in §4.5 and Finding 1 is **WITHDRAWN**. No
artefact row yields 47 Ω for the 0.23 mm design line. The corrected, row-traceable
band is **48.56–49.92 Ω** (mask εr 3.0–4.5 at the declared laminate Dk 4.2) with a
numerical band of **49.28–49.54 Ω**; the central value **49.43 Ω is unchanged**.
New artefacts: `05_hotfix_z0_band.py`, `hotfix_z0_band.json`, `hotfix_z0_band.csv`,
`hotfix_log.txt` (all in this directory; the four original scripts were not modified).

## H1.1 Where 47 came from — and why it was not a row

`47 = 49.43 × (1 − 0.05)`: §4.5's own ±5 % closed-form-vs-FD spread, applied
*downwards* to the masked solve. Four independent checks show it is not a row:

| check | result |
|---|---|
| any solve at w = 0.23 mm giving 47 Ω? | no. `fd_solve.json` `mask_sensitivity` floors at **48.561** (εr_mask 4.5); the entire mask-εr space 3.0–4.5 spans 48.56–49.92 |
| where does a row near 47 actually live? | `fd_solve.json` `width_sweep`: **w = 0.250 mm → 47.41 Ω, w = 0.255 mm → 47.07 Ω** — a *different, unrouted* width, not the 0.23 mm design line |
| what εr_mask would give exactly 47 Ω? | **6.83** (`05` §D, bisection). Solder-mask Dk is 3.0–4.5; 6.8 is not a solder mask |
| what laminate Dk would give exactly 47 Ω? | **4.80** vs the declared 4.2 (line 64) — 0.6 above anything the board file says |

So the old band was either the ±5 % multiplier counted as if it were a solve, or the
width-sweep rows of another geometry. Both are non-rows. The 5 % spread also points the
wrong way to be a ±5 % envelope on 49.43: the closed forms (50.01 / 50.21 / 53.18 Ω at
t = 35 µm) bracket the FD **no-mask** solve (52.57 Ω) from 50.0 to 53.2 Ω, none of them
models the mask, and none of them lands near 49.43 — the spread constrains the unmasked
limit only.

## H1.2 CORRECTED band, with the row that produces it

| quantity | Z0 (Ω) | source row (this directory) |
|---|---:|---|
| primary solve, mask 0.010 mm, **εr_mask = 3.5 (ASSUMED)** | **49.43** | `hotfix_z0_band.csv` row `3.500`; `fd_solve.json` `nominal.Z0_with_mask` |
| band floor, εr_mask = 4.5 | **48.56** | `hotfix_z0_band.csv` row `4.500` (48.5607) |
| band top, εr_mask = 3.0 | **49.92** | `hotfix_z0_band.csv` row `3.000` (49.9199) |
| numerical band, box 11 h → 45 h @ h/60 | **49.28–49.54** | `fd_solve.json` `nominal.Z0_band_from_box`; reproduced in `hotfix_z0_band.json` `box_sweep` |
| strictest box pairing (h/120, 11 h and 45 h) | 49.19–49.45 | `hotfix_z0_band.json` `box_sweep` |
| resolution h/120 (box 30 h) | 49.43 | `hotfix_z0_band.json` `resolution_sweep` |

> **Corrected statement:** Z0(0.23 mm) = **49.43 Ω** (−1.14 % from 50 Ω) at the assumed
> mask εr of 3.5; **artifact band 48.56–49.92 Ω** across a plausible mask εr of
> 3.0–4.5; **numerical band 49.28–49.54 Ω**. 47.0 Ω is not part of any of these.

## H1.3 Mask εr assumption + sensitivity table (the table the report lacked)

The board file carries **no** solder-mask εr (only 0.010 mm thickness, lines 54/95), so
**εr_mask = 3.5 is an assumption**, not a fact. Sensitivity, same solver, h/120, box 30 h:

| εr_mask | 3.00 | 3.25 | 3.50 (assumed) | 3.75 | 4.00 | 4.25 | 4.50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Z0 (Ω)** | 49.92 | 49.67 | **49.43** | 49.20 | 48.98 | 48.77 | **48.56** |
| εeff | 3.229 | 3.261 | 3.293 | 3.324 | 3.354 | 3.383 | 3.412 |
| S11 @ 100 MHz (dB) | −36.9 | −36.8 | **−36.4** | −35.9 | −35.3 | −34.6 | −34.0 |

`hotfix_z0_band.csv` (full 0.125 grid). Mask rows sit at h/120, the laminate rows at
h/90 — the grid costs ≤0.03 Ω and does not move any band edge. Slope **dZ0/dεr_mask = −0.906 Ω per unit εr**,
so ±0.5 in the mask εr is worth ∓0.45 Ω — the assumption is worth **1.36 Ω end to end**.

**Two other unknowns are larger**, and both were already in the artefacts:

| unknown | values | Z0 (Ω) | S11 @ 100 MHz |
|---|---|---:|---:|
| mask *geometry* (does it fill the side trench?) | fills / only above copper / no mask | 49.43 / 51.92 / 52.57 | −36.4 / −32.4 / −30.7 dB |
| **laminate Dk** (declared 4.2, never measured) | 3.8 / 4.0 / 4.2 / 4.4 / 4.6 | 51.41 / 50.40 / 49.46 / 48.57 / 47.73 (h/90) | — |

Per unit εr the **laminate term is ~5× stronger** (−4.6 Ω/unit vs −0.91 Ω/unit): the
declared Dk, not the mask, is the dominant impedance assumption. Cross-corner envelope
for 4.0 ≤ Dk ≤ 4.4 × 3.0 ≤ εr_mask ≤ 4.5: **Z0 = 47.70 … 50.88 Ω** at h/120
(47.73 … 50.91 Ω at h/90; ~58 % of that spread is the laminate term alone). This is the
only place where a 47.x Ω value appears at all — the corner Dk 4.4 + εr_mask 4.5 — and
it is stated as a sensitivity tail, **not** as the band endpoint, because neither
corner is supported by a measurement.

## H1.4 S11 re-stated with the corrected band

Worst edge is LOW @ 100 MHz in every configuration (pure skin effect: R = 13.2 Ω/m vs
131.7 Ω/m at 10 GHz, so Z0 = 49.47 − 1.41j at the low edge). Above 500 MHz the
mismatch is a flat ≈ −44.5 dB and is not the binding case.

| case | Z0 (Ω) @ 100 MHz | S11 (dB) | VSWR |
|---|---:|---:|---:|
| **central (εr_mask 3.5)** | 49.47 − 1.41j | **−36.39** | 1.031 |
| band floor 48.56 (εr_mask 4.5) | 48.60 − 1.39j | −33.98 | 1.041 |
| band top 49.92 (εr_mask 3.0) | 49.96 − 1.42j | −36.92 | 1.029 |
| laminate corner 47.70 (Dk 4.4, εr_mask 4.5) | 47.74 − 1.36j | −31.38 | 1.056 |
| laminate corner 50.88 (Dk 4.0, εr_mask 3.0) | 50.92 − 1.46j | −35.35 | 1.035 |
| mask present, no trench fill | 51.96 − 1.48j | −32.37 | 1.049 |
| no mask at all | 52.61 − 1.49j | −30.67 | 1.060 |

> **Corrected S11 statement:** worst band edge **−36.4 dB @ 100 MHz** at the assumed
> mask (unchanged), degrading to **−34.0 dB** at the band floor 48.56 Ω and to
> **−31.4 dB** at the worst cross-corner. Over the whole unknown-εr envelope
> |S11| ≤ 0.0270 (VSWR ≤ 1.056) with the mask present; only the *mask-absent* case
> reaches −30.7 dB (VSWR 1.06). The line is a low-reflection launch in every case
> in which its own unknowns are bounded — but "≤ −30 dB" is now the honest floor, not
> "−36 dB everywhere".

## H1.5 Corrected EM-5 regrade

Replace the superseded wording with:

> EM-5: Z0 = **49.43 Ω (−1.1 %)** on the declared stackup at an assumed mask εr of 3.5,
> **artefact band 48.56–49.92 Ω** (mask εr 3.0–4.5), **numerical band 49.28–49.54 Ω**;
> 50 Ω sits 0.16 % above the top of that band. Allowing the unmeasured laminate Dk
> 4.0–4.4 widens the band to 47.7–50.9 Ω, so the width closes to ≈1 % **only if** the
> laminate Dk is confirmed near 4.2. The failure mode is not the trace width.

## H1.6 Still UNVERIFIED (narrowed, not closed)

- **εr_mask and tanδ_mask** — absent from the board file; the whole 48.56–49.92 Ω band
  and the trench-fill geometry are assumptions. A mask datasheet or a TDR coupon
  closes this and nothing else here does.
- **Laminate Dk** — 4.2 is declared (line 64), never measured; §H1.3 shows Dk 4.6 puts
  Z0 at 47.73 Ω. A coupon measurement is the only closer.
- **Pressed stackup / etch trapezoid** — unchanged: 0.13 mm prepreg nominal, 45° etch
  bound 58.8 Ω, so the as-fabricated value stays in a 49.4–58.8 Ω bracket.
- **Discontinuities, B.Cu-over-split-In2 segments, connector launch** — unchanged; no
  3D full-wave or VNA run exists.
- **No measurement of any kind.** Every number here is a 2D quasi-static field solve.
- The value **47.0 Ω** is withdrawn: it is 49.43 × 0.95, or the w = 0.250–0.255 mm
  width-sweep rows. Do not restate it as this line's band.

## H1.7 Reproduce the correction

```
cd E:/engineering-portfolio-audit/evidence/cs-em-field
python 05_hotfix_z0_band.py     # ~3 min; writes hotfix_z0_band.{json,csv}, hotfix_log.txt
```

Verified against the original artefacts: the rerun reproduces `fd_solve.json`
bit-identically at the three anchor points — 49.4297 (nominal, εr_mask 3.5), 49.9199 /
48.5607 (εr_mask 3.0 / 4.5), and the box band 49.2778–49.5417 — so the new band is the
same solver, not a different model. Repo untouched: no checkout, no writes, no commits.
