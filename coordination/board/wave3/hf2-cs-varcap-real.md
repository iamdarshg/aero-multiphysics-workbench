# HOTFIX — cs-varcap-real: the design was never validated, and it does not survive a 20 % C(V) error

Hotfix of `evidence/w2-cs-varcap-real/REPORT.md` (wave 2, item Code-SDR).
Repo `repos/Code-SDR`, branch `work/2026-11-11`, read-only: nothing committed,
nothing written into any repo, no `audit/*` branch touched. Everything below is
in `evidence/hf2-cs-varcap-real/`.

**What this hotfix does.** It does not produce a measurement — it removes a
claim. Every wave-2 result was produced by the same nodal solver run against the
repo's own `FILTER_RESPONSE.csv`; that file is itself a generated calculation
(`docs/em-validation/scripts/redesign/README.md:11-12`: *"`NOISE_BUDGET.csv`,
`FILTER_RESPONSE.csv` and `RF_ANALYSIS.md` are generated calculation results"*).
Agreement with it proves the solver implements the same equations, not that the
board behaves as the equations say. Every number is therefore relabelled
**MODEL-DERIVED**.

**Then the practical question.** With the varactor C(V) curve 20 % low, the
corner range becomes **46.369 – 52.008 MHz** and the **46.25 MHz edge is missed
by 0.119 MHz**. With the curve 20 % high, **43.097 – 50.147 MHz**, window still
covered. The design tolerates a curve error of **−18.7 % / +23.3 %** and no
more. The 1.293:1 figure being a model result is not the problem; the problem is
that the model's own margin against the datasheet's *typical* curve is only
18.7 % on the side that matters.

---

## 1. Label applied — every wave-2 result, restated

| # | wave-2 result | label | artefact |
|---|---|---|---|
| 1 | k = 0.887…1.148, **1.293 : 1** | MODEL-DERIVED | `cs_varcap_cv_vs_vc.csv`, reproduced here §3 |
| 2 | corner **44.63 … 51.05 MHz** | MODEL-DERIVED | `cs_varcap_design_run.log:3,15` |
| 3 | placements 46.25 / 48.00 / 50.00 MHz at Vc 2.541 / 1.846 / 0.768 V | MODEL-DERIVED | `cs_varcap_corner_placement.csv` |
| 4 | "the solver **is** the design", 0.001 dB vs `FILTER_RESPONSE.csv` | **MODEL-vs-MODEL self-consistency** — not validation | `cs_varcap_model_validation.log` |
| 5 | requirement 1.161 vs 1.169 (0.7 % agreement) | MODEL-DERIVED (closed form + nodal) | `cs_varcap_scaling_law.log` |
| 6 | Q = 455 at 50 MHz | MODEL-DERIVED from **typ** Rs, no published max | datasheet Table 3 |
| 7 | Rs costs −0.007 dB (26.25) / −0.056 dB (46.25) | MODEL-DERIVED | `cs_varcap_loss_run.log` |
| 8 | tolerance stack 46.00 … 50.21 MHz (±2.1) | MODEL-DERIVED (assumed ±2 %/±5 % L) | `cs_varcap_tolerance_run.log` |
| 9 | ±0.32 MHz temperature drift | MODEL-DERIVED from a **plot axis bound**, not the curve | datasheet Fig. 3 |
| 10 | 0.84 % node modulation, ≈ −47 dBc | ANALYTICAL | `REPORT.md:311-315` |
| 11 | stock corner 47.90 MHz | MODEL-DERIVED — the −3 dB crossing of a table that starts at −3.514 dB for 48 MHz | `FILTER_RESPONSE.csv:7` |
| 12 | pot rotation map, 27.7 … 90.2 % | MODEL (loaded divider, closed form) | `cs_varcap_bias_run.log` |
| 13 | "absorbs 4.2 MHz of worst-case spread" | MODEL-DERIVED, and **conditional on the curve** (§3) | this report |

Direction of the correction: no number changed. What changed is that none of
them may be read as a property of hardware. Where the original report wrote
*"the solver is not an approximation of the design - it is the design"* (§2,
line 69), the correct statement is: *the solver is the design's model, and the
design's model is all this repository contains.*

## 2. The one fact that settles it, from the repo itself

`hardware/HARDWARE_VALIDATION.md:14-16`:

> "The analog design and CAD checks can be completed in this repository, but a
> 10 GHz design is not production-qualified until first articles have passed
> VNA, phase-noise, noise-figure, blocker and thermal tests."

and its release gate 8, `hardware/HARDWARE_VALIDATION.md:254`: *"VNA launches,
every RF branch, BAW path and anti-alias filter."* So the repo's own release
gate contains the measurement that would validate this trim, and it has not been
run. The wave-2 report's §9 already admitted *"No VNA measurement of the board
exists"* (`REPORT.md:372-374`) while its §2 and its headline verdict asserted
the design. That is the defect: an admission in §9 cannot be outvoted by a
verdict in the abstract.

## 3. Worst case if the varactor C(V) curve is off by 20 %

Method: the same solver, with the SMV1236 Table 4 row multiplied by a scale
`s`; `s = 1` reproduces the wave-2 numbers exactly (51.052 / 44.630 MHz,
1.293:1 — deltas 0.000 / 0.000 MHz / 0.0004).
`tools/hf2_cv20_sweep.py` → `hf2_cv20_sweep.log`, `hf2_cv20_sweep.csv`.
PROVENANCE: MODEL-DERIVED.

| s | C(V) error | corner range (MHz) | k ratio | vs 1.169 | 46.25 reachable | 50.00 reachable | window |
|---|---|---|---|---|---|---|---|
| 0.80 | **−20 %** | **46.369 … 52.008** | 1.243 | +6.3 % | **NO (+0.119 MHz)** | yes | **NO** |
| 0.90 | −10 % | 45.471 … 51.523 | 1.269 | +8.5 % | yes | yes | yes |
| 1.00 | 0 % | 44.630 … 51.052 | 1.293 | +10.6 % | yes | yes | yes |
| 1.10 | +10 % | 43.841 … 50.593 | 1.317 | +12.7 % | yes | yes | yes |
| 1.20 | **+20 %** | **43.097 … 50.147** | 1.340 | +14.7 % | yes | yes | **yes** |

To the ±20 % question: **the worst case is the −20 % side, and the window is not
covered.** The 46.25 MHz edge is unreachable — the trim floor is 46.369 MHz, a
0.119 MHz miss (0.26 %). The +20 % side is harmless (more varactor fraction,
more authority), which is why the answer is asymmetric.

Exact authority band, by bisection on `s` (`hf2_cv20_sweep.log` §4):

    both window edges reachable for  s in [0.813, 1.233]
      = C(V) curve may read -18.7 % .. +23.3 %

So the design has **18.7 % of curve-error protection on the low side**, not the
+10.6 % the headline implied. −20 % is 1.3 points outside; +20 % is 3.3 points
inside.

**Why the pot cannot rescue it.** The floor is set by the control-voltage end
stop, VR = 0.30 V. At the producing tool's ceiling (Vc = 3.00 V) the corner is
46.369; at the pot's real maximum (Vc = 2.895 V, `cs_varcap_bias_run.log`) it is
worse, 46.79 MHz (`edge_check.log`). There is no setting left to turn.

**Why 0.12 MHz is not noise.** At the s = 1 design point for 46.25 MHz the four
nodes sit at 55.24 / 59.94 pF; at s = 0.80 with the pot at its stop they sit at
54.95 / 59.65 pF — 0.29–0.30 pF low. The measured per-node sensitivities sum to
−0.459 MHz/pF (`cs_varcap_scaling_law.log`), predicting +0.13 MHz, observed
+0.119. The decomposition closes.

**The trap in the original argument.** At s = 0.80 the k ratio is still
**1.243 : 1, i.e. +6.3 % above the 1.169 requirement** — it passes the metric
and fails the window, because a curve error also shifts the *centre* of the
achievable range while the fixed capacitors (36.5 / 41.2 pF) do not move. The
remote observation is that "k ratio ≥ 1.169" is a necessary and **not
sufficient** test: only "both corner targets reachable within Vc ∈ [0, 2.895]"
is sufficient. The original report states the margin in k and the coverage in
frequency, which let the two diverge unnoticed.

**It compounds with the tolerance stack.** The trim must also reach 46.00 MHz to
absorb the −2.1 MHz stack (`REPORT.md:281-282`), which had 1.37 MHz of spare at
s = 1. At s = 0.80 the floor is 46.369 MHz: 0.37 MHz short of that requirement
instead of 0.12 MHz short of the nominal window.

**Stopband is untouched** — placing the corner at 46.25 MHz still gives
−26.9 / −27.0 / −26.8 dB at 53.75 MHz for s = 0.80 / 1.00 / 1.20
(`hf2_repair_e96.log`). The trim's failure mode is coverage, not rejection.

## 4. What a measurement would actually have to confirm

No figure below exists in this repository. Each line is a thing the model
assumes and the bench must decide.

| # | measurement | confirms / removes | acceptance number from the model |
|---|---|---|---|
| 1 | C(V) of the **fitted lot** at VR = 0.30 / 0.76 / 1.45 / 2.53 / 3.30 V (LCR at 1 MHz or impedance analyser, fixture < 0.2 pF) | the whole §3 worst case; replaces a typical table with a part number | C_v(0.30 V) ≥ **18.75 pF** (81.3 % of the 23.07 typ); C_v(3.30 V) ≤ **10.47 pF** (123 % of 8.49 typ) — `hf2_gate.csv` |
| 2 | 100 Ω differential S21 vs pot setting at 6.25 / 26.25 / 46.25 / 48.00 / 50.00 / 53.75 MHz | the corner, the −3 dB definition, the whole placement table | 46.25 and 50.00 MHz corners both reachable, S11@26.25 ≤ −18 dB everywhere |
| 3 | bare-board S21 with the varactors unfitted | the ±0.2 pF parasitic assumption (2 % of a 51 pF node, `REPORT.md:368-369`) | fits within ±0.2 pF per node |
| 4 | Zin of U73 output / U74 input with RF off | LT5560 1200 Ω ∥ 0.7 pF and AD8351 5000 Ω ∥ 0.8 pF — currently *read off the ADI datasheets* (`REPORT.md:370-371`) | ±20 % on both |
| 5 | per-node C(V) of D70–D73 individually (populate one at a time) | four separate SC-79 dies tracking each other — explicitly not specified by Skyworks (`REPORT.md:375-376`) | ≤ 3 % node-to-node at one bias |
| 6 | S21 at 26.25 MHz vs temperature, −40…+85 °C | Figure 3, read only as an axis bound so far | ≤ 5 % C drift (the ±0.32 MHz figure depends on it) |
| 7 | two-tone at full blocker level | the 0.84 % modulation / −47 dBc estimate | ≥ 45 dBc |

Items 1 and 2 are the two that decide the design; item 1 is a 5-minute bench
task and is the cheapest way to retire the entire §3 table. The repo's own gate
(`hardware/HARDWARE_VALIDATION.md:254`) already asks for 2, 6 and 7.

## 5. The datasheet — checked against the file, not against memory

`SMV1236-079LF` is a real part in **Skyworks SMV123x Series, 200058AB**
(`datasheets/SMV123x_skyworks_F9C9BC.pdf`).

| check | result |
|---|---|
| PDF integrity | `%PDF-1.4`, 1,207,008 B, 12 pages, SHA-256 `55F728EF…DD87DB` |
| metadata | `/Author` = *Skyworks Solutions, Inc*, `/Title` = *SMV123x Series*, `200058AB` on all 12 pages |
| part in Table 1 | `SMV1236-079LF`, SC-79, marking "Cathode and HY" — dump line 60-61 |
| Table 3 row | `SMV1236 15.50 18.50 9.20 5.30 1.6 2.0 3.0 3.5 0.50` — exact (`pdf_provenance.log`) |
| Table 4 row | 26.75 / 20.61 / 17.02 / 14.38 / 12.29 / 10.56 / 9.16 / 8.04 / 7.19 / … / 3.80 at 15 V — matches `if2_ladder.py:60-62` term for term |
| abs. max | VR 15 V, IF 20 mA, P 250 mW, −55…+125 °C |

So the capacitance numbers used by the design **are** the datasheet's, and are
**not** UNVERIFIED in the sense of "invented". Two caveats that matter more than
the verification itself:

1. **Table 4 is a typical table.** Min/max exist only at CT@1 V (15.50–18.50 pF)
   and for the two ratios; the draft also says *"Performance is guaranteed only
   under the conditions listed in this table"* and *"Tested with -079 package"*.
   The 0.3–3.3 V shape the design integrates against is **typical, not
   guaranteed** — which is exactly the space a 20 % error lives in.
2. **The guaranteed bin still passes, the 20 % error does not.** The 1 V bin
   15.50–18.50 pF is s = 0.9107…1.0870; at s = 0.9107 the floor is **45.379** MHz
   and the ceiling 51.472, at s = 1.0870 it is 43.941…50.652 — so any part inside
   the published bin covers 46.25 MHz (`bin_check.log`). The failure at −20 % is a
   failure of the *shape*, which no table in this datasheet bounds.

Provenance defects in the wave-2 evidence, both now recorded:

- `datasheets/SMV123x_mouser_200058R.pdf` is **13,897 B of HTML** — the page
  body reads *"Access to this page has been denied"*. It is not a datasheet and
  must not be cited as a second source.
- `datasheets/SMV1234_datasheets_com.pdf` (987,384 B, valid PDF) is an
  aggregate page for the **1234**, not the 1236.
- The PDF's own metadata shows CreationDate 2020-01-20 and ModDate 2026-05-11
  (iText), consistent with a re-issued document carrying the "May 7, 2026"
  footer. Not a defect — but it is one document, not two independent sources.

**Independent cross-check: NOT DONE.** `web_search` in this session returns
*"multiple usable web providers are registered (deepseek-official,
deepseek-search-api); configure one explicitly"* — a provider misconfiguration,
not a network failure. No second copy of this datasheet was obtained, so the
figures are **verified against the file present in the repo's evidence tree and
against nothing else**. Flagged, not papered over.

## 6. What to do — the least-effort path that keeps physical fidelity

Owner steer: part swaps and constraint edits before copper; copper before
stackup; fab burden free. The failure in §3 is a *value* problem, so it is
solved with values.

**Recommendation (no copper, no stackup, no topology, no new refdes).**
Measure C(V) on the first article (§4 item 1), then fit C262/C268 and
C264/C266 from the table below. Nothing else changes: D70–D73, the 1 nF
blocks, the 100 k feeds and the pot stay as designed.

| measured s | C262/C268 | C264/C266 | corner range (MHz) | 46.25 | 50.00 | S11@46.25 | S21@26.25 |
|---|---|---|---|---|---|---|---|
| 0.80 (−20 %) | **39.2 pF** | **44.2 pF** | 45.206 … 50.377 | yes | yes | −35.9 dB | −0.47 dB |
| 0.90 | 38.3 | 42.2 | 45.018 … 50.846 | yes | yes | −28.9 | −0.47 |
| 1.00 (today) | 36.5 | 41.2 | 44.630 … 51.052 | yes | yes | −25.4 | −0.47 |
| 1.10 | 34.8 | 40.2 | 44.247 … 51.245 | yes | yes | −23.0 | −0.48 |
| 1.20 (+20 %) | 33.2 | 38.3 | 44.110 … 51.804 | yes | yes | −20.1 | −0.48 |

(`tools/hf2_repair_e96.py` → `hf2_repair_e96.log`, `hf2_repair_e96.csv`; E96 1 %
C0G 0402 values, same footprints.) With this fit, **every** s from 0.75 to 1.30
covers both window edges — the ±20 % case becomes a two-line BOM edit instead of
a re-spin.

Note what must *not* be done: scaling all four fixed caps with `s` (the obvious
move) fails at both ends — `hf2_cv20_sweep.log` §5a, e.g. s = 0.80 with
29.2 / 33.0 pF gives 50.074 … 57.339 MHz. The correct rule is to hold the
**nominal node capacitance** (at VR = 1.45 V), not to scale the fixed values:
`C_fix_new = C_fix_old + C_v_nom·(1 − s)`, `C_v_nom = 14.64 pF`.

Two things this does not fix, and should not be sold as fixing:
- It does not make the ±20 % error *known*; it makes the design insensitive to
  it **after** the measurement, which is the alignment flow the trim already
  assumes ("one-time ATE setting by pot", `REPORT.md:214-215`).
- The four-part gang still tracks the curve four ways; §4 item 5 is the only
  check on that.

**Cheaper-but-worse alternative already costed in wave 2:** one SMV1237 at F3
covers the window with a single part (`REPORT.md:141-148`) but costs 0.26–0.28 dB
of passband tilt and −20.0/−18.1 dB of match at the window edges. Not preferred;
kept as the fallback if the four-part gang fails its tracking check.

## 7. Board status

**No BOARD CORRECTION.** `AGENT_BOARD.md:58` already reads *"4 x SMV1236-079LF,
k 1.293:1 against 1.169 needed; corner 44.63–51.05 MHz | model-only, no VNA"* —
that line is correct, and `AGENT_BOARD.md:77` records the right defect. The
wave-2 report, not the board, carried the unsupported claim.

Proposed replacement for the two cells of line 58, if the lead wants the
worst-case on the board:

> cs-varcap-real | 4 x SMV1236-079LF; k 1.293:1 vs 1.169 needed; corner
> 44.63–51.05 MHz **at datasheet-typ C(V)**; **MODEL-DERIVED, no VNA**;
> survives −18.7 %/+23.3 % curve error, **fails at −20 % (46.369 MHz floor,
> +0.119 MHz miss)**; fix = four E96 C values after first-article C(V)
> measurement, no copper

## 8. Files

| file | what it is |
|---|---|
| `tools/hf2_lib.py` | the solver, physics-identical to `design_production.py`, plus the `s` knob and E96 table |
| `tools/hf2_cv20_sweep.py` | §3: baseline reproduction, ±20 % sweep, authority band, repairs, acceptance gate |
| `tools/hf2_repair_e96.py` | §6: the E96 fit and its coverage/stopband check |
| `tools/pdfcheck.py` | §5: PDF page/metadata/table extraction with `pypdf` |
| `tools/edge_check.py` | the pot-limit check (2.895 vs 3.00 V) and the 0.3 pF decomposition |
| `tools/bin_check.py` | corners at the datasheet's guaranteed 1 V bin limits |
| `hf2_cv20_sweep.log` / `.csv` | every §3 number, re-runnable |
| `hf2_cv20_fixscale.csv` | the rejected "scale all fixed caps" repair |
| `hf2_repair_e96.log` / `.csv` | every §6 number |
| `hf2_gate.csv` | the two acceptance gates for the first-article measurement |
| `pdf_provenance.log` | 12 pages, metadata, Table 3/4 text out of the actual PDF |
| `edge_check.log` | pot-ceiling corners and the sensitivity sum |
| `bin_check.log` | the 1 V bin limits mapped to corner range |

Run: `C:\Program Files\KiCad\9.0\bin\python.exe tools\hf2_cv20_sweep.py`
(Python 3.11.5, numpy 2.3.5, pypdf present; matplotlib absent, hence tables).

## 9. UNVERIFIED

- **No measurement of any kind.** No VNA, no LCR, no temperature data, no
  first article. Every figure in this report and in the wave-2 report is a model
  output or a datasheet reading.
- **The C(V) of the fitted parts is unknown.** The ±20 % case is bounded here;
  the actual error is not, and cannot be without §4 item 1.
- **Datasheet independently cross-checked: no** — one document, no second
  source (`web_search` provider misconfiguration, §5).
- **Rs maximum** not published (0.50 Ω typ only), so Q = 455 and the loss
  figures are typical-case.
- **Temperature curves** (Figs. 1–4) are plots; only axis bounds were read.
- **Inductor value tolerance and Q** for the real BOM parts remain assumptions
  (`REPORT.md:365-367`); the ±2.1 MHz stack inherits them.
- **Board parasitics** (±0.2 pF assumed), **LT5560/AD8351 port models**
  (datasheet readings), and **four-die tracking** are all unmeasured.
- **s as a uniform scale is a model of the error, not the error.** A
  non-monotonic or bias-dependent shape error is not covered by §3; the
  low-VR-only "tilted" case in `hf2_cv20_sweep.log` §2 was run and lands on the
  same 46.369 MHz floor, which is why the low side is reported as the worst case.