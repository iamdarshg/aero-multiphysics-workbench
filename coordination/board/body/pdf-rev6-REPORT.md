# pdf-rev6 — the input correction

**Unit:** pdf-rev6 (this session) · **Supersedes:** `evidence/pdf-rev5/drone_mech_body_evidence_rev5.pdf`
(19 pp, sha256 `EBD80EA4…`) · **Date:** 2026-11-15

**Deliverable:** `evidence/pdf-rev6/drone_mech_body_evidence_rev6.pdf`
**20 pages · 379,657 bytes · sha256 `9E6AF0A736D0DABACB76EC61EB5ED967EBA9C2ECFBDC919343174CCFD9D369C7`**
**351 graded facts: 125 MEASURED · 183 ANALYTICAL · 43 ASSUMED · 0 SOLVER**

This revision corrects **two inputs**, re-sums the rows they feed, prints the basis of both fractions,
and widens the two row bands that were narrower than their own uncertainty. It changes no physics, no
mass, no volume and no area outside §6.1. Nothing was written outside this directory; no repo file was
written, no commit, no branch, no `audit/*`.

---

## 0. The answer, first

| question | answer |
|---|---|
| Was the verifier's C1 finding right? | **Yes — independently confirmed.** The material cut face at z = −298.8 measures **11,627.3335 + 545.3851 = 12,172.7186 mm²**, not the 6,359.0 that was subtracted. Printed surface **25,539.500 mm²**; nose row **−64.236 g**, not −61.002 g. |
| Was the C3/C4 finding right? | **Yes on the basis, 0.06–0.14 g off on the two rows.** The wall-only share is **19.13 %** (33,473.724 of 175,023.642 mm²) by exact slab-clip; the verifier's **19.25 %** (33,692 of 175,033) is the same basis read off a tessellation. Rows: **−9.291 g** and **−8.569 g**. |
| What is the corrected package? | **−86.98 g** (printed **−87.0 g**), band **−112.02 … −60.33 g**, 1.83× the withdrawn −47.4 g. |
| Does the band survive? | **The published band does** — −86.98 lies inside both rev5's −99.0 … −58.5 and the new −112.0 … −60.3. **The row bands did not survive the audit and are replaced**: C3's 0.2 g band excluded the truth by 3.5 g. |
| Did rev5's total pass while its rows were wrong? | **Yes.** The two errors point opposite ways and nearly cancel (0.77 g net). A total inside its band certified rows that were wrong — that is the lesson this revision records. |
| Is `87.8` gone from the text? | **Yes, except one occurrence** in §0.6's correction-history row recording what rev5 published. `6,359.0` and `31,353.2` are **gone entirely** (0 hits); `19.25` and `86.9` appear once each, as the verifier's figures in the cross-check. |

---

## 1. What was actually wrong

Neither row's arithmetic was wrong. Both rows carried a correct measurement **of a different set**.

### 1.1 C1 — the cut face was the bay's enclosed section

rev5 took `S_cut = 6,359.0 mm²` at z = −298.8 and printed `S_outer = 37,712.219 − 6,359.017 = 31,353.2 mm²`.
Three independent signs say that is not the material face:

1. **The same file reports 6,359.017 as the cap of two different solids.** `inputs/recost_partner_geom.json`
   gives `nose.cap_section_mm2 = 6,359.017` **and** `bayfill.cap_section_mm2 = 6,359.017`. One plane
   cannot cap two solids at their own areas — the number is an enclosed/interior section, not a material
   band.
2. **It was arithmetically impossible.** 415,035.713 mm³ over the band's 61.2 mm z-span **averages
   6,781.6 mm²** of material section. A section cannot average more than its own maximum.
3. **Measured face by face, it is 12,172.72 mm².** The z = −298.8 plane cuts two faces out of the nose
   band: **11,627.3335 mm²** (the lump) and **545.3851 mm²** (a separate annulus) — the verifier's
   11,627.3 and +545.4, to the digit. At z = −300.0 the same computation gives **12,013.27 mm²**, which
   matches the 12,013 rev5's own prose quoted for that plane: the two planes differ by 1.2 mm and the
   faces differ by 160 mm², as they should, and 6,359.0 belongs to neither.

With `S_outer = 25,539.500 mm²`:

| quantity | rev5 | rev6 (MEASURED → ANALYTICAL) |
|---|---|---|
| band volume | 415,035.713 mm³ | 415,035.713 mm³ (unchanged) |
| cut face | 6,359.017 mm² | **12,172.719 mm²** |
| printed surface | 31,353.201 mm² | **25,539.500 mm²** |
| 2V/A | 22.0107 mm | 22.0107 mm (unchanged) |
| deposit share / density | 20.586 % / 259.4 kg/m³ | **19.551 % / 246.3 kg/m³** |
| material as it stands | 107.656 g | **102.239 g** |
| 1.2 mm printed PLA wall | 46.654 g | **38.003 g** |
| **nose row** | **−61.002 g** | **−64.236 g** |

The tail half of C1 carries the *same* defect and was not challenged: its cap was 337.704 mm², again the
enclosed section, where the material cut face at z = +247.0 is **536.409 mm²** (three faces). Corrected
consistently, the tail is **−4.885 g** instead of −4.590 g. Correcting one plane and not the other would
leave one row on two different rules, so both are corrected and the 0.30 g difference from the
verifier's total is stated rather than absorbed.

### 1.2 C3/C4 — a whole-body numerator over a wall denominator

`0.263687` is the share of the **whole body's** 285,215.7 mm² of surface inside |y| < 22 mm — and
110,192.1 mm² of that surface is the nose lump, which no thinning candidate touches. The rows applied
that share to the **wall's** 97,943.2 mm² mid-surface.

Measured two ways, the wall-only share:

| method | numerator | denominator | share |
|---|---|---|---|
| exact slab-clip (surface of the wall in the band, less the two new planar cut faces) | 33,473.724 mm² | 175,023.642 mm² | **0.191253** |
| tessellated, 0.1 mm and 0.02 mm | 33,485 / 33,485 mm² | 175,172.8 mm² | 0.191154 |
| the verifier's tessellation | 33,692 mm² | 175,033 mm² | 0.19249 |

The exact method is adopted. It rests on an identity that is checked in the script: `A(in band) +
A(out of band) = A(total)` to **−0.0023 mm²** on 175,023.6 (1.3 × 10⁻⁸), and `V(in) + V(out) = V(total)`
to **+0.388 mm³** on 117,531.8 — so no cut face is missed, which would have biased every area below.

Note the whole-body share is itself **25.03 %** by the exact method; the 26.37 % rev5 printed is a
tessellation artefact of the same family (whole triangles binned by centroid on large planar faces that
straddle the plane). Both the population *and* the measure were wrong; only the population mattered for
the rows, because the body share was never the right quantity.

| quantity | rev5 | rev6 |
|---|---|---|
| band area \|y\| < 22 mm | 25,826.4 mm² (0.263687 × 97,943.187) | **18,731.9 mm²** (0.191253 × 97,943.187) |
| removed core C3 | 10,330.6 mm³ | **7,492.8 mm³** |
| **C3 row** | **−12.810 g** | **−9.291 g** |
| incremental band 22–33 mm | 18,857.3 mm² (0.192583 × 97,943.187 — again a *difference of body shares*) | **17,275.9 mm²** (0.176387 × 97,943.187, wall-only) |
| removed core C4 | 7,542.9 mm³ | **6,910.4 mm³** |
| **C4 row** | **−9.353 g** | **−8.569 g** |

### 1.3 The package

`C1 + C3 + C4`, the withdrawn figure's own membership:

**−69.1213 − 9.2910 − 8.5688 = −86.9811 g** · band **−112.0166 … −60.3316 g** ·
−18.42 % of the 472.273 g body of record · −15.82 % of the repaired design-intent body ·
**1.83×** the withdrawn −47.4 g · even the corner closest to zero is **1.27×** it ·
the shell falls to **385.292 g** before the mandatory +77.600 g repair.

The two errors very nearly cancel: rev5's −87.755 g becomes −86.981 g, a **0.774 g** net move made of
−3.24 g (C1) and +3.16 g (C3+C4). **A total that lands inside its band is not evidence that its rows
do.**

---

## 2. The three-line reconciliation

| figure | rev5 printed | verifier's independent flow | this unit (MEASURED geometry → ANALYTICAL rows) |
|---|---|---|---|
| C1 nose | −61.002 g | −64.2 g | **−64.236 g** |
| C1 tail | −4.590 g | not re-checked (kept) | **−4.885 g** |
| C1 row | −65.592 g | ≈ −68.8 g | **−69.121 g** |
| C2 | −27.496 g | −27.50 g ✓ | **−27.496 g** (re-measured, unchanged) |
| C3 | −12.810 g | −9.35 g | **−9.291 g** |
| C4 | −9.353 g | −8.71 g | **−8.569 g** |
| **package** | **−87.755 g** | **−86.9 g** | **−86.981 g** |
| package band | −99.03 … −58.54 | "still contains the truth" ✓ | **−112.02 … −60.33** |
| ratio to −47.4 g | 1.85× | ~1.83× | **1.83×** |
| board line (AGENT_BOARD.md) | 18 pp, −95.9 g | — | **20 pp, −87.0 g** (not updated — §10) |

**The 0.09 g residual between the verifier's −86.9 and this unit's −87.0 is located, not smoothed:**

| term | difference | cause |
|---|---|---|
| C1 tail | −0.296 g | they kept rev5's enclosed-section cap (337.7) where the material face is 536.4 |
| C3 | +0.059 g | their band fraction 19.25 % (tessellated) vs 19.13 % (exact) |
| C4 | +0.142 g | same, plus the incremental band's tessellation bias |
| C1 nose | +0.036 g | rounding of their −64.2 |
| **net** | **−0.09 g** | |

Every disagreement is attributable to a tessellation convention or to an input they did not re-check.
**Nothing in the verifier's report is refuted**; one row of their total is under-corrected.

---

## 3. Do the bands survive?

**The package band does; the row bands did not, and are replaced.**

* **rev5's package band −99.0 … −58.5 g contains −86.98 g.** The band was valid even though two of the
  three rows inside it were not.
* **C3's row band −13.0 … −12.8 g did not contain −9.29 g.** It was 0.2 g wide — the density sweep
  alone (1,240 → 1,260) — and it excluded the measured truth by 3.5 g. A band that excludes the truth is
  worse than no band: it claims precision the row never had. **C4's −9.5 … −9.4 had the same defect.**
* **The new row bands sweep what the rows are actually uncertain about**, multiplicatively:
  * density 1,240 → 1,260 on the removed core (×1.016);
  * the band measure: exact vs tessellated (×0.9995 — negligible, recorded);
  * **the mid-surface basis** (×0.8935): the ledger's own `A_mid = V_lam / 1.2 = 97,943.2 mm²` versus
    the measured shell's `S/2 = 87,511.8 mm²`. A 10.7 % population question of exactly the family this
    revision is correcting, so it is swept rather than ignored.
  * → **C3 −9.44 … −8.30 g**, **C4 −8.71 … −7.66 g** (widened from 0.2 g and 0.1 g to 1.1 g and 1.1 g).
* **The package band widens with them, from 40.5 g to 51.7 g**: −112.0 … −60.3 g. Most of the widening
  is C1's sparse sweep, whose corners moved with the corrected surface (−44.4 g at 10 %, −93.9 g at
  20 %); the two row bands account for about ±1.1 g of it. The band is now the sum of its rows' doubts
  instead of a subset of them, and the least-favourable corner is still **1.27×** the withdrawn figure,
  so the direction survives the widening.

---

## 4. What the document now says that it did not before

1. **The basis, beside the fraction.** `wall-only 19.13 % of 175,024 mm²` is printed in the subtitle,
   in the §6.1 correction paragraph, in the C3 table row and in the C3/C4 prose; the build now fails if
   the phrase `wall-only` is missing from the rendered page (**G10**). This is the control: the defect
   survived because `26.37` and `19.25` appeared **nowhere** in rev5's text, so no reader could see the
   population.
2. **The refutation, not just the replacement.** The mean-section argument (415,035.7 / 61.2 = 6,781.6
   mm² > any 6,359 maximum) is on the page, so the reader can refute the old input without re-measuring.
3. **The cross-check paragraph**, including the one figure this revision does not adopt and why (§2).
4. **New withdrawal rows (§6.2, added, nothing removed):** the enclosed-section cut face and the
   body-wide band fraction, each with its reason, its arithmetic refutation and its replacement.
5. **A fifth wave in the correction history (§0.6, added):** rev5 produced −87.8 g; what rev6 caught in
   it was two wrong inputs whose corrections cancel. Plus a new paragraph naming the **third defect
   class** — *a correct measurement of the wrong population* — which neither the unit audit (D1) nor
   the escape gate (D2) can see, and which only a printed basis catches.
6. **U15 added to §7:** the residual question this revision's own correction opens (does the C1 tail
   half's wall stand on the band's whole printed boundary or on the mid-surface? worth 0.30 g).
7. **Every legacy figure updated**: −61.0, −12.81, −9.35 and −87.8 are gone from the running text;
   −87.8 survives once, in the correction-history row that records what rev5 published. `6,359.0` and
   `31,353.2` are gone entirely — the withdrawal row names the *quantity* (the bay's enclosed section)
   and prints the replacement, so the dead digits are not re-printed as a quote.

---

## 5. Verification of the rebuilt artifact

Extracted from the PDF itself (`logs/VERIFY.txt`, 0 failing checks):

```
pages 20   bytes 379,657   chars 112,410
sha256 9E6AF0A736D0DABACB76EC61EB5ED967EBA9C2ECFBDC919343174CCFD9D369C7
```

| probe | count | verdict |
|---|---|---|
| `87.8` | **1** | correction-history record only (gate G7 caps it at 1) |
| `6,359.0` | **0** | gone (G8) |
| `31,353.2` | **0** | gone (G8) |
| `19.25` | **1** | the verifier's fraction, in the cross-check (G9) |
| `86.9` | **1** | the verifier's package, in the cross-check (G9) |
| `19.13` | 9 | the published wall-only basis |
| `wall-only` | 7 | G10 requires ≥ 2 |
| `-61.0` / `12.81` / `9.35`-as-C4 | 0 / 0 / — | replaced; `9.35` appears once, as the verifier's C3 |
| `-69.1` / `-64.2` / `-9.3` / `-8.6` / `-87.0` | 5 / 2 / 8 / 7 / 13 | the corrected rows and total |
| `12,172.7` / `25,539.5` | 5 / 4 | the corrected C1 inputs |

Gates: `assert_clean: 20 pages, 112410 chars, 0 escapes, G1-G10 pass`.
Audits: unit audit **607 format arguments, 500 unit words, 0 mismatches**; declaration audit **0 gaps
in 10 sections**; MEASURED re-audit **exhaustive, 125 = 52 + 72 + 1** (read 52, geometry 72, unit 1).

---

## 6. Metadata

| property | value |
|---|---|
| pages | **20** (rev5: 19; +1 from the added correction and appendix text) |
| bytes | **379,657** |
| sha256 | **9E6AF0A736D0DABACB76EC61EB5ED967EBA9C2ECFBDC919343174CCFD9D369C7** |
| extracted text | 112,410 characters |
| facts | **351 = 125 MEASURED · 183 ANALYTICAL · 43 ASSUMED · 0 SOLVER** |
| inputs hashed | **26** files in `inputs/` (`MANIFEST.json`, sha256 of every copy, drift-checked) |
| rendered escapes | 0 |
| REV-PENDING | 8 mentions, all historical/definitional; no row pending |

**The sha/page-count mismatch rev5 left is fixed at its source.** rev5's REPORT §7 and §9 printed
`sha256 C854D1CE…` while the file it produced was `EBD80EA4…`, and its board line said 18 pp / −95.9 g
against a 19-page / −87.8 g build. In this revision every metadata figure above is **measured from the
produced file in one command** (`scripts/18_verify_rev6.py`, V1), and the same numbers are printed in the
PDF's own footer and metadata table from the build's own state — so there is one number, taken once.

**Determinism, stated accurately.** The page **text** is deterministic: a rebuild with no changed fact
reuses every section stamp verbatim (observed: 111,656 characters before and after a no-op rebuild).
The **file bytes are not**: reportlab stamps a creation date and a document ID into the PDF catalog, so
two identical builds differ in sha256 (build 2 `53CDF86D…`, build 3 `9F91F55B…`, identical page text).
rev5's REPORT claimed "a re-run reproduces the same sha256"; that claim was wrong and is not repeated.
The sha above identifies this file.

---

## 7. Files

| file | what it is |
|---|---|
| `drone_mech_body_evidence_rev6.pdf` | **the deliverable**, 20 pp, sha256 `9E6AF0A7…` |
| `REPORT.md` | this file |
| `scripts/40_recompute_rev6.py` | **MEASURE**: body solids, both cut planes, the wall band (exact + tessellated), C1/C2/C3/C4 and the package → `recost_corrected.json` |
| `scripts/43_manifest_rev6.py` | copies that file into `inputs/`, re-hashes all 26 inputs, fails on drift |
| `scripts/44_fix_population_rev6.py` | **the one edit the build gates caught** — the facts module had the wall and body populations swapped (see §10) |
| `scripts/42_retarget_rev6.py` | the builder's identity strings, retargeted rev5 → rev6 by script, not by hand |
| `scripts/18_verify_rev6.py` | post-build checks on the PDF **and** the ledger → `logs/VERIFY.txt`; V5 rewritten, because rev5's V5 certified the two wrong inputs |
| `scripts/17_decl_check.py`, `02_unit_audit.py` | declaration audit; D1 unit audit (both retargeted, both run as gates) |
| `facts_recost_rev6.py` | the recost facts, **read from `inputs/recost_corrected.json`** — no number typed in |
| `facts_rev6.py`, `content_rev6.py`, `build_rev6.py` | the ledger, the text, the builder + `assert_clean()` G1–G10 |
| `recost_corrected.json`, `inputs/recost_corrected.json` | this revision's measurement (identical copies, hashed) |
| `logs/` | `assert_clean.txt`, `VERIFY.txt`, `unit_audit.json`, `decl_check.log` |
| `png/` | the 20 page rasters read for layout |
| `scripts/01_measure_hatch.py`, `03_recost.py`, `inputs/recost_partner*.json` | **rev5's** measurement and the partner file it read, carried unchanged so the correction can be audited against what it corrects |

---

## 8. Reproduce it

```
cd E:/engineering-portfolio-audit/evidence/pdf-rev6
& 'C:/Program Files/Python312/python.exe' scripts/40_recompute_rev6.py   # MEASURE (≈12 min; intersections)
& 'C:/Program Files/Python312/python.exe' scripts/43_manifest_rev6.py    # hash 26 inputs, drift fails
& 'C:/Program Files/Python312/python.exe' scripts/02_unit_audit.py       # D1 gate (must exit 0)
& 'C:/Program Files/Python312/python.exe' scripts/17_decl_check.py       # declarations (must exit 0)
& 'C:/Program Files/Python312/python.exe' build_rev6.py                  # PDF + assert_clean() G1-G10
& 'C:/Program Files/Python312/python.exe' scripts/18_verify_rev6.py      # PDF + ledger verification
```

Reads `repos/drone-mech/.../phase15_geometry/step/*.step` read-only. Writes only inside this directory.

---

## 9. What this unit is least sure of

1. **The tail half of C1 is a model, not a measurement** (U15). It prices 1.2 mm over the band's whole
   printed boundary — which for a shell that is already 4.01 mm thick includes both faces. On the
   mid-surface reading alone the row moves 0.30 g. It is small against C1's 25 g sparse sweep, it is
   disclosed, and it is the one place where this unit's number differs from the verifier's.
2. **The mid-surface basis of C3/C4** (97,943.2 vs 87,511.8 mm²) is now swept into the row bands but not
   resolved. If the measured `S/2` is the right basis, the wrap mass in §3.3 is also 10 % high — a much
   larger change than this revision is entitled to make. Flagged, swept, not decided.
3. **The sparse setting inside the nose lump** (U13) still moves C1 between −44.4 g and −93.9 g. It
   dominates the package band and only a slice on the real machine settles it.
4. **`03_recost.py`'s closed form is unchanged** and still uses the 13,964 mm² enclosed shoulder area as
   `S_cut` for its own candidate; that is why the closed-form cross-check reads −78.5 g. It is labelled
   as the closed form and is not the published basis, but a reader who diffs the two scripts will find
   the same idiom in both, and should know it.
5. **Tessellation-based band measures are biased by up to 0.7 pp** on this body. The exact slab-clip
   method is the one adopted; the tessellated figures are reported beside it so the disagreement is
   visible rather than hidden.
6. **This unit's own first fix was wrong in the same way as the defect.** The facts module read
   `bands_exact["wall"]` into a name used for the body and vice versa, so the first build printed
   "wall-only 25.03 % of 285,216 mm²" — the body share over the body total, under a wall label. The
   build's own gates and a text probe caught it; `scripts/44_fix_population_rev6.py` records the
   episode. It is in this list because a correction unit that cannot report its own population slip has
   no business correcting anyone else's.

---

## 10. What this unit did not do

**The board was not updated, by design.** The brief says work not on `AGENT_BOARD.md` does not exist,
but this unit's hard rule is to write only inside its own evidence directory. The board still carries the
rev5 line (**18 pp, −95.9 g**) — stale against rev5's own 19 pp / −87.8 g, and staler against this
revision. Suggested replacement line for the delegating agent:

> **drone-mech body rev6** — `evidence/pdf-rev6/drone_mech_body_evidence_rev6.pdf`, **20 pp**, sha256
> `9E6AF0A7…`, 351 facts (125 MEASURED · 183 ANALYTICAL · 43 ASSUMED · 0 SOLVER). Two wrong inputs under
> the −47.4 g re-cost corrected: C1's cut face (12,172.7 mm² material, not 6,359.0 enclosed) and the
> C3/C4 band population (wall-only 19.13 % of 175,024 mm², not the whole body's 26.37 %). Package
> **−87.0 g, band −112.0 … −60.3 g**, 1.83× the withdrawn figure; row bands widened to contain their own
> uncertainty. Supersedes rev5.

No structural analysis, no new measurement of the print, no change to §1–§5. Nothing withdrawn at
rev2–rev5 was deleted: the withdrawals table and the correction history were **added to**, and the only
figure that left the text entirely is one that was wrong.