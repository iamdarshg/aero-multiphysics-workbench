# rev9 — publishing the drone-mech body deliverable with rev8's convergence claim withdrawn

**Deliverable:** `drone_mech_body_evidence_rev9.pdf` · 32 pages · 602,749 bytes ·
sha256 `5469453579C8DDDD5AF8E17C54A4075D1AE3DF72CD9EE8CCD30DDFB6039F436E`

Supersedes `evidence/pdf-rev8/drone_mech_body_evidence_rev8.pdf` (30 pages, 579,097 bytes,
sha256 `35781DB3A702BE8A3FE8FBD7A29D30F95233D3B5ACF0AEBBF868E9AA580AD9B6`) — verified byte-for-byte
before work started.

This was a **correction, not an addition**. rev8 published `Cl = −0.0149 ± 0.6 %` as CONVERGED from
a 64-row window on a trace that stopped at t/c 1.239. The trace now runs to t/c 1.8057 and the
coefficient swings 11.8 % across it. That claim is withdrawn and replaced with the measured result.

Nothing was written outside `E:\engineering-portfolio-audit\evidence\pdf-rev9\`. No repository was
written, no branch touched, nothing committed.

---

## 1. The retraction, and why it is not an arithmetic error

The strongest thing that can be said for this correction is that it was **reproduced before it was
published**. `inputs/force_trace.csv` was truncated at t/c 1.239 and rev8's own statistic re-run:
it returns `−1.49758e−2`, which is rev8's published figure to five significant figures
(`scripts/80_recompute.py`, `logs/recompute.json`). The arithmetic was always right. The **window**
was too short, so what rev8 measured was the noise at one station rather than the motion between
stations.

| | rev8's window | rev9's window |
|---|---|---|
| rows | 64 of 322 | 112 of 630 |
| t/c | 1.04 → 1.239 | 1.448 → 1.806 |
| mean Cl | −1.4976 × 10⁻² (reproduced exactly) | **−0.016412** |
| scatter inside | 0.6 % ← called convergence | 1.31 % |
| drift inside | −1.8 % (already moving) | +0.19 % (locally flat) |
| **0.5-chord block means** | **not measured by rev8** | −0.01510 → −0.01611 (**−6.70 %**); block before that 25.80 % away |
| status | CONVERGED ± 0.6 % — **WITHDRAWN** | **NOT CONVERGED**, quoted as a band |

This is the same error class as the three population mismatches already in §0.6: a statistic
computed over a narrow sample and applied to a wider one. §8.2 says so, and says that rev8 had
already withdrawn an extrapolated Cd asymptote for being an extrapolation before publishing a
convergence claim on evidence of the same shape.

## 2. What is now published, per quantity

| quantity | rev9 publishes | status |
|---|---|---|
| **Cl** | **−0.0164 ± 0.0011** | **NOT CONVERGED.** The ± is the measured half-chord block movement (1.01e−3) rounded *up* to 0.0011, so the band is wider than the measurement, not narrower. Printed with the status word in every sentence and every table row. |
| **Cd** | nothing | **Cannot be quoted.** The last sample (0.007901) sits 29.6 % below its own window mean (0.011228); the window contains a 13.15 % swing and a −40.13 % drift. rev8's "decaying geometric series → 0.010–0.011" reading is withdrawn too: the series reverses (local min 0.01124 near t/c 1.33, rebound 0.01261 by 1.57). |
| **Cs** | −0.3906 … −0.3884, an instrument bias | **Holds, independent of the retraction.** −0.3906 + 0.3997 = +0.0091 against the closed-surface +0.0066, ~2 % residual. |

**The sign of Cl is published as an open question.** Measured Cl is negative; lifting-line theory at
±0.5° for AR ≈ 1.03 gives |Cl| ≈ 0.017 — the magnitude fits, the sign does not. Either the section
sits at −0.5° in this frame or `liftDir (0 1 0)` is inverted. The axes are self-consistent (Cd and Cs
reproduce algebraically to ten digits) and self-consistency is not correctness, so no sign was
flipped. §8.5 states both hypotheses and declines to choose between them.

## 3. Everything the brief asked to be added, and where it sits

| item | where | verified on the page |
|---|---|---|
| Compute reality: 1,113 steps ≈ 9.2 h from here, ≈14.4 h from t = 0, the 9 h estimate **1.6× optimistic** | §8.9 | `1,113` ×1, `9.2` , `14.4` ×2, `1.6×` ×2 |
| Resumption free: nine checkpoints 0.000398 → 0.002398 s, ≈2.3 further 4-hour blocks | §8.9 | `9 checkpoints` ×1, `2.3` |
| Operational finding: `writeControl runTime` anchors writes to `startTime`; a kill cost ≈70 min, `adjustableRunTime` at 2.5e-4 s caps it at ≤30 min | §8.9 | `adjustableRunTime` ×1, `70`, `30` |
| Cs bias kept, reconciled to ~2 %, independent of the retraction | §8.6 | `0.3997` ×2, `+0.0091` ×1, `+0.0066` ×1 |
| `fsi` = 93.9 % wetted wing skin, area 0.13241 m² ≈ 2×Aref, planarity 0.060 vs rootWall 1.000, Σa = (−7.96e−3, 0, 0) = −rootWall area | §8.7 | `93.9` ×3, `0.13241` ×1, `0.0601` ×3, `1.000` |
| CFD vs analytical drag build-up: different instruments, different questions (87.96 / 67.04 / 30.03 cm²) | §8.8 | `87.96` ×13, `67.04` ×8, `30.03` ×10, `does not replace the analytical drag build-up` ×1 |
| Cumulative withdrawals table kept, **with the retracted Cl figure added** | §6.2 (p. 18) | see §4 below |
| Correction history kept, now nine waves | §0.6 | waves 8 and 9 added |
| Boxed disjoint-solids caveat kept | §7.3 | unchanged |
| "sha256 is not reproducible across rebuilds" kept | §B.5 | `creation date` ×2 |
| Bump to rev9 | cover, footer, ledger, filename | `rev9 (supersedes rev8)` |

## 4. The count of `-0.0149`, and where the one remaining occurrence sits

**One occurrence, on page 18, inside the §6.2 withdrawals table** — the first cell of the new last
row, struck through in red, labelled `(rev8 §8)`, with the reason *"convergence judged from a single
window; extending the trace showed an 11.8 % swing"* and the replacement `-0.0164 ± 0.0011, NOT
CONVERGED`. Zero occurrences anywhere else: no live sentence, no abstract, no figure, no caption.

Two things about this number are worth recording because they are how the check was made honest:

- The count must be taken on a **minus-normalised** string. The first build printed the figure with a
  Unicode minus (U+2212) in §8's retraction box, which an ASCII `-0.0149` probe does not see. That
  instance was found by **rendering the page and reading it**, not by the probe. Both the build gate
  (`G23`) and `scripts/66_checks_rev9.py` now normalise U+2212 → `-` before counting.
- The retraction box was then rewritten to name the claim (`CONVERGED ± 0.6 %`) without the digits,
  so the figure exists in exactly one place — the withdrawals table the brief asked for. The
  withdrawn **qualifier** `CONVERGED ± 0.6 %` appears twice (box and row), both times within 320
  characters of the word WITHDRAWN, and the probe enforces that.

## 5. Tier histogram

Computed from the ledger, not typed:

| revision | graded facts | MEASURED | SOLVER | ANALYTICAL | ASSUMED |
|---|---|---|---|---|---|
| rev7 | 453 | 132 | 36 | 235 | 50 |
| rev8 | 506 | 132 | 69 | 255 | 50 |
| **rev9** | **559** | **132** | **90** | **287** | **50** |

MEASURED and ASSUMED are unchanged, which is the load-bearing claim of the whole document: the
retraction moved no mass, area, volume, fraction or stress. SOLVER 69 → 90 (36 structural + 54
aerodynamic) and ANALYTICAL 255 → 287, because the aero block was re-derived from a delivered input
(53 transcribed facts replaced by 106 recomputed ones).

**One deliberate grade change, disclosed in §0.5:** rev8 graded its aero window means SOLVER, which
contradicted the legend two paragraphs above it (a mean of solver columns is an arithmetic
combination of tiers). rev9 grades means, scatters, drifts and block movements ANALYTICAL and keeps
SOLVER for what the solver printed — rows, last samples, row counts, checkpoints, patch geometry.

## 6. What makes this revision stronger than rev8, beyond the correction

1. **rev8's disclosed provenance gap is closed.** rev8 built §8 on statistics it had not been given
   and said so in §B.4. `inputs/force_trace.csv` (58,378 bytes, sha256
   `00D12F70F7DD2C6FDAFB7295BD69897C5EE7FE0B091EF29187A356D40D4DCE68`) is now a hash-stamped input
   in §B.2, and every §8 statistic is recomputed from it by `scripts/80_recompute.py`. **This is what
   made the retraction possible** — a number that cannot be recomputed cannot be refuted either.
2. **The figure now plots the trace, not sampled facts.** rev8 drew seven Cl samples and called the
   flatness convergence; that drawing *was* the error. Both panels now show all 630 rows, with rev8's
   window marked and the 11.8 % swing arrowed. The panels are clipped to the range the claims are
   about and say so in the caption: the impulsive start (+0.051, 0.121) is labelled off-scale rather
   than silently dropped.
3. **Two inherited table cells that rendered broken were fixed.** In §6.2 a cell of the form
   `m<sub>core</sub>` split across lines, leaving "m" on one line and "core" on the next; it now
   reads "the core mass, 145.739 g, and the mid-surface area, 979.4 cm²". The same artifact in the
   new rev9 row was avoided. Found by rendering pages, not by reading source.

## 7. Verification performed

All figures below are from the final build; every one is reproducible with the three commands.

| check | result |
|---|---|
| `scripts/80_recompute.py` (all §8 statistics from the trace) | reproduces every number in the brief: Cl −1.641236e−2 / sd 1.31 % / drift +0.19 %; Cd 1.122815e−2 / sd 13.15 % / drift −40.13 %; last samples −0.016027 and 0.007901; block means −0.01510 → −0.01611 (−6.70 %) and 0.01226 → 0.01132 (−7.71 %) |
| `scripts/02_unit_audit.py` | 787 format arguments across 331 strings, 579 unit words, **0 unit mismatches** |
| `scripts/17_decl_check.py` | **0 of 12 sections** have a declaration gap |
| `build_rev9.py` → `assert_clean()` | **G1–G28 pass**, 0 leaked escapes, 32 pages |
| `scripts/66_checks_rev9.py` | **33 probes, all pass** (`logs/checks_rev9.txt`) |
| `scripts/18_verify_rev9.py` | ledger describes the file (32 pp), all 559 facts graded and sourced, provenance CSV = ledger, 27 input hashes match §B.2, trace row count 630 (`logs/verify_rev9.txt`) |
| frame-overflow scan (`scripts/103_frame.py`) | **0 pages** overflow the text frame |
| visual review | pages 1, 16–18, 22–25, 27 rendered at 110–700 dpi and inspected; the struck withdrawal, the sign box, the stationarity table, the figure and the tier census all read correctly |

Key probe counts: `-0.0149` **1** · `-0.016412` 3 · `-0.0164` 13 · `-0.0164 ± 0.0011` 10 ·
`0.011228` 2 · `0.007901` 2 · `NOT CONVERGED` 12 · `WITHDRAWN` 4 · `lifting-line` 1 ·
`liftDir` 2 · `OPEN QUESTION` 1 · `1.6×` 2 · `adjustableRunTime` 1 · `9 checkpoints` 1.

## 8. Limitations, stated rather than buried

- **The coefficient is not converged and this document does not claim it is.** −0.0164 ± 0.0011 is a
  band whose width is a measured half-chord movement; the residual is bounded and shrinking (−25.8 %
  per half chord, then −6.7 %), which is what makes a band defensible and does not make it a value.
- **The sign is unresolved.** Two hypotheses predict the same numbers; settling it needs one run at a
  known positive incidence or one check of the suction-side orientation. It is published as open.
- **Cd is not published at all.** Fixing it needs a phase-averaged mean over ≥3 oscillation periods,
  which is a different experiment from a longer run and has not been performed.
- **The window is defined as the final 20 % of the time span, not of the row count.** The trace is not
  uniformly spaced (dt 4.4e−6 early, 5.1e−6 late), so a row-count window reaches further back in
  physical time and returns Cl −0.016330 with 1.91 % scatter instead of −0.016412 with 1.31 %. Both
  definitions are stated in `scripts/80_recompute.py`; the time-based one is the one that reproduces
  the run's own analysis and is the one quoted.
- **The sha256 of this file is not reproducible across rebuilds** — reportlab stamps a creation date
  and a document ID. A rebuild gives identical page text and a different hash, as §B.5 says.
- **This revision corrects one number and adds none.** Everything else in §1–§7 is rev8's text,
  carried unchanged, and the withdrawals table says so.

## 9. Files

| file | content |
|---|---|
| `drone_mech_body_evidence_rev9.pdf` | the deliverable |
| `build_rev9.py`, `content_rev9.py`, `content_aero_rev9.py`, `facts_rev9.py`, `facts_aero_rev9.py`, `facts_solver_rev9.py`, `facts_recost_rev9.py` | the builder and its fact/content modules |
| `inputs/` | 28 declared inputs, `MANIFEST.json` carrying every sha256 — including `force_trace.csv`, new at rev9 |
| `scripts/80_recompute.py` | recomputes every §8 number from the trace |
| `scripts/66_checks_rev9.py` | the brief's extraction probes on the finished page |
| `scripts/18_verify_rev9.py` | post-build checks on the PDF, the ledger and the input hashes |
| `scripts/02_unit_audit.py`, `17_decl_check.py` | unit and declaration gates |
| `logs/recompute.json`, `checks_rev9.txt`, `verify_rev9.txt`, `assert_clean.txt`, `unit_audit.json`, `frame.txt` | the evidence for every statement above |
| `png/` | page renders and zooms used in the visual review |
| `logs/rev9_verified.pdf`, `logs/rev9_verified.sha256` | byte-exact snapshot of the verified build |

### A note on concurrency, because it affects which file is the deliverable

Three files in this directory — `BIAS.txt`, `CHK.txt`, `FINAL.txt`, written 15:25–15:26 — were **not
produced by this unit**. They record a build of 577,432 bytes / sha256 `AAE9EE63…` with a different
fact census (77 SOLVER, 159 MEASURED) from the one this report describes (90 SOLVER, 132 MEASURED),
so a second writer was building a rev9 into the same path. The PDF on disk now is this unit's
(602,749 bytes, sha256 `54694535…`, all 33 probes passing at 16:03), and `logs/rev9_verified.pdf`
holds a byte-exact copy in case another writer overwrites it. **If the parent receives two rev9
artifacts, they are two different documents and need arbitrating — this report's numbers describe
only the 602,749-byte file.**