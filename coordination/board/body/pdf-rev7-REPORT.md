# pdf-rev7 — rev7 of the drone-mech body evidence document

**Agent:** pdf-rev7 unit. **Date:** 2026-11-15.
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/pdf-rev7/`.
**Host:** Windows 11, `C:/Program Files/Python312/python.exe` (reportlab 5.0.1, matplotlib 3.9.2,
pypdf, PyMuPDF).
**Nothing was written outside this directory.** No repository was touched: no commit, no branch, no
reset, and no `audit/*` branch. The structural run this revision cites belongs to another unit and
was **not re-run** here — it was read, citation-guarded and folded in.

---

## 0. The artifact

| property | value |
|---|---|
| file | `drone_mech_body_evidence_rev7.pdf` |
| pages | **26** (rev6: 20; +6 from the new §7, the two range statements and the new history) |
| bytes | **490,813** |
| sha256 | **D06523F0033619BDA704866E536FD51C13B1423315B3B96C481FF31838864953** |
| extracted text | 144,874 characters |
| graded facts | **453 = 132 MEASURED · 36 SOLVER · 235 ANALYTICAL · 50 ASSUMED** |
| inputs hashed | **27** in `inputs/` (`MANIFEST.json`, every copy hash-verified, drift-checked) |
| gates | `assert_clean: 26 pages, 144874 chars, 0 escapes, G1-G16 pass` |
| verifier | `scripts/18_verify_rev7.py` → **PASS, 0 failing checks** |
| extraction checks | `scripts/66_checks_rev7.py` → **38 PASS, 0 FAIL** (`logs/rev7_checks.txt`) |
| unit audit | 807 format arguments, 591 unit words, **0 mismatches** |
| declaration audit | **0 gaps in 11 sections** |

**The sha256 identifies this file and makes no reproducibility claim** — reportlab stamps a creation
date and a document ID into the PDF catalog, so a rebuild yields the same page text and a different
hash. The document says so itself (Appendix B.5), which rev7 inherited as a requirement rather than
as a footnote: rev6 had the statement only in its own REPORT, and rev7 puts it **in the PDF**.

Base: `evidence/pdf-rev6/drone_mech_body_evidence_rev6.pdf`, 20 pp, 379,657 bytes,
sha256 `9E6AF0A736D0DABACB76EC61EB5ED967EBA9C2ECFBDC919343174CCFD9D369C7` (verified before the copy,
and unchanged in `pdf-rev6/`). The sources were **copied and edited**, never rebuilt:
`build_rev7.py`, `content_rev7.py`, `facts_rev7.py`, `facts_recost_rev7.py`.

---

## 1. The brief's eight requirements, and where each one lands

| # | requirement | where it is satisfied | verified by |
|---|---|---|---|
| 1 | move structure ANALYTICAL → SOLVER, count honestly | §0.2 legend row, §0.5 histogram paragraph, §8 census, page-1 tier-census cell | G12; check 1 |
| 2 | state the load case **and the two rejected alternatives with the numbers that rejected them** | §7.1, two tables + "an honest note on the ranking" | G-none (text); check 2 |
| 3 | the 4-disjoint-solids caveat **in the results section** | §7.3, boxed notice above the result tables | G13 (positional: `77.165` before §8); check 5 |
| 4 | state what was not done (buckling, frequency, fatigue, bond, fastener, anisotropy; no √E) | §7.6 table + §7.3 | G14; check 6 |
| 5 | the E band as a band with endpoints, never a point | §7 opening, §7.3, table + Figure 3, U2, §8 | G15; check 7 |
| 6 | keep the withdrawals table and the correction history; add, remove nothing | §6.2 (unchanged rows + one new), §0.6 (wave 6 added) | G7/G8; check 4 |
| 7 | do not claim sha256 reproducibility | Appendix B.5 + page-1 metadata row | G16; check 6 |
| 8 | extract the text and verify | `scripts/66_checks_rev7.py` → 38 checks | this file, §4 |

The load case is battery-pack inertia: 2 × 0.28 kg at 6 g limit × SF 2.0 = **12 g ultimate, 65.9 N**
into the 2 × 4 mm rail land. Rejected with numbers: **(b)** wing-join bending, 29.67 N·m ultimate,
only **2.53 MPa** on the bore-limited Zx 11,737 mm³ section — it tests the bore layout, not the wall;
**(c)** duct thrust, **0.60 MPa**, and no citable thrust exists because the CFD force integration sits
on the fsi cutting plane.

---

## 2. What changed in the text

1. **§7 is new** (5 pp): the first SOLVER-tier chapter. Load case (7.1), model and its one
   idealisation error (7.2), results **and the caveat that gates them** (7.3), verdict plus the
   independent section cross-check and the correction to `body-mass-opt` (7.4), the C1 consequence
   (7.5), and the list of what the model does not cover (7.6).
2. **§7 → §8** for the unknowns, with the two cross-references retargeted. **U2 moved from
   UNVERIFIED to SOLVER** for one load case, and **U16 is new** (which charge the C1 wall carries).
3. **C1 is a range**: `-69.1 … -83.4 g`; **the package follows**: `-87.0 … -101.2 g`; both ends and
   both bases are printed, and the **conservative end (low magnitude) is named in every place the
   range appears** (§0.1, §6.1 table, §6.1 paragraph, §6.2 row, §6.3 board marker, §7.5).
4. **The correction history gained wave 6** and a new paragraph: `body-mass-opt`'s open-top
   Zx 2,134 mm³ is **2.41× below** the 5,146.3 mm³ the same section yields, areas agree to 1.2 % and
   the closed ring to 3.5 %, so **that report's stress conclusions were conservative, not
   optimistic** — the first correction in this document's history that does not weaken an earlier
   claim.
5. **Appendix A** gained two file:line citations to `body-structure/REPORT.md`; **Appendix B** gained
   B.5 (determinism), the rev7 command list and the "no residual added" note.
6. Two layout holes were found by reading the rendered pages and fixed (a `keepWithNext` chain
   welded §0.3's and B.2's tables to their headings and pushed both to a fresh page).

### The C1 arithmetic, both bases

| basis | charge for the replacement wall | third removed by 1.2 → 0.8 mm | licensed end | package |
|---|---|---:|---:|---:|
| the structural report's (§5) | **42.7 g** | 14.233 g | **-83.354 g** | **-101.214 g** |
| §6.1's own measured row | **38.003 g** | 12.668 g | -81.789 g | -99.649 g |

Published: **C1 `-69.1 … -83.4 g`, package `-87.0 … -101.2 g`**, with the 38.003 g alternative stated
beside them (U16). The package is 18.42 % of the body of record at the conservative end and 21.43 %
at the licensed end. The **-60.3 … -112.0 g band is a different thing** — an infill/density sweep —
and the two are never added.

---

## 3. How the new numbers got in without being typed

`scripts/50_solver_inputs.py` reads `evidence/body-structure/REPORT.md` (386 lines, sha256
`075719ce05763e99…`) and, for each of **96 numbers**, asserts the exact printed form occurs on the
line cited for it, then **parses the value from that printed form**. A number the report does not
state cannot enter, and a citation cannot drift. `inputs/body_structure.json` (21,501 bytes) is that
extraction, hash-recorded in `MANIFEST.json` and added to `OPTIONAL_INPUTS` so it re-stamps only the
sections that declare a SOLVER fact.

Tiering follows the document's own rule: the run's displacements, stresses, mesh and run cost are
**SOLVER** (36 facts); ratios between runs, factors of safety, the licensed ends and the package that
follows are **ANALYTICAL** (they are `dv()` facts with the arithmetic in their `src`); the three E
values and both allowables are **ASSUMED**, as that report states; the load case's inputs are
**MEASURED** and are in the MEASURED re-audit's `read` class.

Two judgement calls worth naming:

* **The refined peak is quoted at 2 d.p. in the opening** (3.23 MPa) so it reads beside 2.85 MPa;
  the stress table keeps 3 d.p. (3.226). Both are the report's numbers.
* **A 0.8 mm cone stress and its utilisation were added as facts** (`slv_cone_08_MPa`,
  `slv_cone_util_08`) after the first render printed the 1.2 mm value twice in that column — a
  copy-paste defect the rendered page caught, which is the argument for reading the page.

---

## 4. Verification actually performed on the artifact

```
pages 26   bytes 490,813   chars 144,874   sha256 D06523F0033619BDA704866E536FD51C13B1423315B3B96C481FF31838864953
```

| probe | count | verdict |
|---|---|---|
| `36 SOLVER` | 3 | the ledger's own count, printed on the page (G12) |
| `0 SOLVER` | **1** | historical only — rev3's histogram, quoted as history |
| `no qualifying run exists` | **0** | the legend sentence rev6 carried is gone |
| `0.139` | 1 | the deflection headline (G11) |
| `5.4` / `9.7` | 11 / 4 | worst-point and field FoS (G11) |
| `-69.1` / `-83.4` | 15 / 10 | both ends of the C1 range (G11) |
| `-87.0` / `-101.2` | 17 / 6 | both ends of the package (G11) |
| `81.8` | 7 | the second basis, disclosed wherever the licensed end is quoted |
| `77.165` | 2 | the disjoint span — **before** §8 (G13) |
| `+97 g` | 1 | the repair that gates §7, in the caveat box |
| `creation date` / `document ID` | 2 / 2 | the determinism statement (G16) |
| `6,359.0` / `31,353.2` | **0 / 0** | the two refuted inputs stayed gone (G8) |
| `87.8` | 1 | the withdrawn package, correction-history record only (G7) |
| `275.890 kg` | 1 | the D1 defect, quoted struck once (G4) |

Tier histogram by revision, for the record: rev3 208 (81 · 86 · 41 · **0**) → rev5 309
(103 · 163 · 43 · **0**) → rev6 351 (125 · 183 · 43 · **0**) → **rev7 453
(132 · 36 · 235 · 50)**. The SOLVER column is no longer zero; the ANALYTICAL growth is that run's
arithmetic and is graded so on purpose.

---

## 5. Reproduce it

```
cd E:/engineering-portfolio-audit/evidence/pdf-rev7
& 'C:/Program Files/Python312/python.exe' scripts/50_solver_inputs.py    # citation guard -> inputs/body_structure.json
& 'C:/Program Files/Python312/python.exe' scripts/51_manifest_rev7.py    # 27 inputs hashed, drift fails
& 'C:/Program Files/Python312/python.exe' scripts/02_unit_audit.py       # must exit 0
& 'C:/Program Files/Python312/python.exe' scripts/17_decl_check.py       # must exit 0
& 'C:/Program Files/Python312/python.exe' build_rev7.py                  # PDF + assert_clean() G1-G16
& 'C:/Program Files/Python312/python.exe' scripts/18_verify_rev7.py      # PDF + ledger, V1-V8
& 'C:/Program Files/Python312/python.exe' scripts/66_checks_rev7.py      # the brief's own checks
```

The rev6 → rev7 text edits are scripted, so the diff is auditable rather than invisible:
`scripts/60_edit_s0.py`, `61_retarget_rev7.py`, `62_edit_s6.py`, `63_edit_s7.py`,
`64_edit_appB.py`, `65_polish_s7.py`. Each is all-or-nothing and refuses to write if an anchor moved.

---

## 6. What this unit is least sure of

1. **The 42.7 g vs 38.003 g basis (U16).** Two different charges for "the C1 replacement wall" are on
   the page. The solver's cone utilisation is independent of which is used; the licensed end of the
   row is not (1.6 g apart). It is disclosed, not resolved — one line from the structural report's
   author settles it.
2. **The refined peak is still rising** (+13 % at 1.43× refinement), so FoS 5.4 is the least firm of
   the factors of safety. The verdict is stated against a margin of 3 or better everywhere, so the
   conclusion does not hinge on it.
3. **Both allowables are ASSUMED** (17.3 / 250 MPa), and a real coupon could move the PLA number by
   2×. The document says so beside every verdict rather than once in a legend.
4. **§7.3's caveat makes the whole chapter conditional.** Everything in §7 is true of the repaired
   design intent. A reader who quotes "the wall is adequate" without the +97 g repair is quoting a
   model, and the box says exactly that.
5. **The 2 d.p./3 d.p. mix in the stress prose** is a deliberate readability choice, not an
   oversight, but it is the kind of thing a reviewer should be told rather than left to notice.
6. **This unit did not re-run the structural solve**, and cannot vouch for it beyond the citation
   guard: the 96 numbers are asserted against the lines they came from, which proves the document
   quotes the report, not that the report is right.

## 7. What this unit did not do

**No repository was read or written.** No commit, no branch, no reset, no `audit/*` branch. The
structural report was read from `evidence/body-structure/` (read-only) and extracted into this
directory. `evidence/pdf-rev6/` was not modified. **No BOARD CORRECTION was raised**: `AGENT_BOARD.md`
carries no Phase-15 body structural figure, so there is nothing on the board to correct — the same
finding as rev6, re-checked rather than assumed.