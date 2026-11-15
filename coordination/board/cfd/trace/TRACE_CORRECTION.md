# CFD force trace — full trajectory, and a correction to two of my own claims

Analysed from the merged trace: `evidence/dm-cfd-final/v2/seg1.dat` (322 rows) + `seg2.dat` (183 rows),
deduplicated on time → **498 rows, t/c 0.255 → 1.806**. Case `rhoPimpleFoam` / `kOmegaSST`, 6 ranks,
1,690,534 cells, `Aref` 0.062249, `lRef` 0.34646, `U_inf` 222.1322 m/s, chord 0.34646 m.

## CORRECTION 1 — Cd is OSCILLATING, not decaying

I previously described the Cd history as "a decaying geometric series" approaching an asymptote near
0.010–0.011. **That was wrong.** Extending the trace to t/c = 1.806 shows the series reverses:

| t/c | Cd |
|---|---|
| 0.26 | 0.02906 |
| 0.53 | 0.01774 |
| 0.77 | 0.01426 |
| 1.01 | 0.01238 |
| 1.25 | 0.01133 |
| **1.33** | **0.01124** ← local minimum |
| 1.57 | **0.01261** ← it goes back UP |
| 1.73 | 0.00981 |
| 1.81 | 0.00790 |

Final 20 % window (99 rows, t/c 1.49–1.81): mean **1.11099e-2**, **scatter 13.8 %**, change over the
window **+39.9 %**.

So Cd is an **unsteady oscillation of roughly 0.0079–0.0126** about a mean near 0.0111, not an
asymptotic decay. The apparent "geometric decay" I read into the first 11 samples was the falling
half of an oscillation. **Any extrapolated asymptote is withdrawn.**

## CORRECTION 2 — Cl is NOT converged to the precision I claimed

I previously published Cl as converged at **−0.0149 ± 0.6 %**. The ±0.6 % was **short-window scatter
inside a window that happened to sit at a local plateau.** Extending the trace exposes a slower swing:

| t/c | Cl |
|---|---|
| 0.77 | −0.01544 |
| 1.25 | **−0.01487** ← local minimum in magnitude |
| 1.57 | **−0.01663** |
| 1.81 | −0.01603 |

Final 20 % window: mean **−1.64599e-2**, scatter **1.1 %**, change −1.3 %.

So Cl oscillates with **~1 % short-window scatter inside a slower ~11 % swing** between −0.0149 and
−0.0166. The honest statement is:

> **Cl ≈ −0.016, banded roughly −0.0149 … −0.0167, not converged to a single coefficient.**

That is a usable band and it is a real improvement on "no quotable value" — but it is **not** the
±0.6 % figure I reported, and the document must not carry that.

## What this correction is an instance of

Judging convergence from **one window** is the same error class as the three population mismatches in
this program: a statistic computed over a narrow sample applied to a wider one. A 0.6 % scatter over
0.2 chords is fully consistent with an 11 % swing over the next 0.5 chords. **Convergence has to be
tested by extending the window, not by measuring the noise inside it.**

I labelled the Cd asymptote an extrapolation, which is why withdrawing it costs nothing. I did **not**
label the Cl "converged" claim as provisional, which is why it has to be retracted. The lesson holds
either way: a claim of convergence is itself a measurement, and it needs its own evidence.

## What survives

| item | status |
|---|---|
| **Cs = −0.3886 … −0.3906**, constant | **holds.** The open-surface pressure bias. Reconciles with the analytic +0.399659 to ~2 %: −0.3906 + 0.3997 = +0.0091 against the closed-surface +0.0066. |
| Cd oscillates about ~0.0111 | **holds as a band, not a value** |
| Cl ≈ −0.016, band −0.0149…−0.0167 | **holds as a band, not a value** |
| the axis convention (drag +z, lift +y, span +x) | **holds** — algebraic reproduction to 10 digits |
| the `fsi` patch is 93.9 % wetted wing | **holds** — planarity 0.060 vs `rootWall` 1.000 |
| near-zero incidence explains small Cl | **holds** — and it makes an oscillating Cl near zero more likely, not less: at low incidence the loading is sensitive to unsteady separation |

## Compute

The solver runs under a wall-clock cap. Reaching a genuinely settled Cd would need several more
chords; the oscillation period appears to be on the order of ~0.3–0.5 chords, so **a phase-averaged
mean over at least three full periods** is the correct way to extract a coefficient from this data,
not a longer monotone run. That is a different experiment from the one attempted.

Do not describe any number above as converged. Do not quote the withdrawn asymptote.