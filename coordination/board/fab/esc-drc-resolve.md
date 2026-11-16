# esc-drc-resolve — the ESC's DRC count, settled

**Owner:** esc-drc-resolve (fab-readiness wave 10)
**Board of record:** `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb`
sha256 `992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD`, 4,988,844 B,
687 footprints, 3,454 pads, 1,990 vias, 154 track segments.
The board has **no `.kicad_dru` of its own** in the repo (`hardware/esc/rev_b/` contains only
`.kicad_pcb`, `.kicad_pro`, schematics, `fp-lib-table`).
**Host:** KiCad 9.0.7 — `C:\Program Files\KiCad\9.0\bin\kicad-cli.exe`, `...\bin\python.exe` (pcbnew 9.0.7),
CPython 3.12.2 for analysis.
**Write scope:** everything below is a **copy** under `evidence/esc-drc-resolve/`. The repo was read only.
Nothing was committed, branched or pushed. Fable's tree was not touched.

---

## 0. Answer in one table

| question | answer |
|---|---|
| Does **523** reproduce? | **YES**, exactly, three times (identical 523 row identities) |
| Does **413** reproduce? | **YES** — but only as the total of a *different board* (the copper-free placement), and as the *footprint-bound subset* of the 523, never as a total of the shipped board |
| Are they the same population? | **No.** 523 = total of the routed board; 413 = its footprint-bound subset. **413 ∪ 110 = 523**, verified as a **row-level set diff** (common 413, gone 110, added 0), not by subtracting totals |
| What is the 110? | 28 via annular + 16 via_diameter + 16 via_dangling + 24 Track↔Track + 19 Pad↔Track clearance + 4 track_width + 3 zone neck. **It is NOT "98 pad rings + 12"** — the 98 pad rings are a third, DRC-invisible population absent from both totals |
| Does the `.kicad_dru` load? | **YES** — eight controls in §2. A file without `(version 1)` is silently ignored (byte-identical result to no rule file at all) |
| Is either total at a tool cap? | **No.** The clearance report caps at **499** (proven on a hand-checkable board); the 414 at 0.25 mm is below it and sits inside a monotone sweep |
| Definitive DRC baseline at 4 oz / 0.25 mm | **523 items (533 with `--all-track-errors`)**, of which **413 footprint-bound**, **110 copper-bound**; **plus 98 pad rings KiCad cannot report** → effective footprint-bound **511** |

---

## 1. Where 413 and 523 came from — file:line, command, board

### 1.1 The 523

| item | value |
|---|---|
| command | `kicad-cli pcb drc --format json --severity-all --units mm --output … "esc_rev_b.kicad_pcb"` |
| board | `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb` (the shipped board, sha `9925…5DDD`) |
| rules | `evidence/fab-esc-rules-first/variant-025/esc_rev_b.kicad_dru`, installed as `esc_rev_b.kicad_dru` beside the board |
| unit | kicad-cli 9.0.7 DRC *violations* (not unconnected) |

First recorded and re-recorded at:

- `evidence/fab-esc-rules-first/variant-025/analysis.json` → `"violations": 523`
- `evidence/fab-esc-rules-first/variant-025/drc.json` → 523 rows
- `evidence/fab-esc-rules-first/REPORT.md:20` (523 / 499), `:157` (variant table), `:177`, `:229`
- `evidence/esc-routability/orig-025/analysis.json` → `"violations_total": 523`; `REPORT.md:104`
- `evidence/esc-branch-4oz/summary_R1.json` → `"total": 523`; `summary_all.json` → `"R1 … total 523"`; `REPORT.md:58`
- `AGENT_BOARD.md:1668` ("523 … reproduces"), and the disagreement is stated at `AGENT_BOARD.md:524`

### 1.2 The 413 — two provenances, one population

**(a) as a TOTAL, on a different board**

- artefact: `evidence/esc-branch-2oz/drc/4oz_powerfirst/drc.json` → 413 violations
- board: `evidence/esc-branch-2oz/boards/esc_rev_b_2oz_powerfirst.kicad_pcb` (2,821,335 B,
  sha `BC10C208…3748A`) — the **power-first placement**. Measured on the same copy that was DRC'd:
  **0 segments, 0 vias, 0 zones**, 687 footprints — against the board of record's
  **154 segments, 1,990 vias, 96 zones**, 687 footprints. (Probe note: `\(segment ` with a trailing
  space returns 0 on *both* files, because KiCad writes a newline after the token; the working pattern
  is `\(segment\s`. A probe that returns a clean zero needs the same scepticism as one that returns a
  round number.)
- rules: the same 4 oz 0.25 mm file (`kicad/esc_rev_b.kicad_dru`)
- recorded: `evidence/esc-branch-2oz/drc/drc_summary.json` (`"tag": "4oz_powerfirst", "total": 413,
  "footprint_bound": 413`), `evidence/esc-branch-2oz/REPORT.md:229` ("4 oz rules, same placement |
  **413** = 371 clearance + 42 annular_width")

**(b) as the footprint-bound SUBSET of the 523**

- artefact: `evidence/esc-branch-4oz/summary_all.json` → `"R1  4 oz … ": {"total": 523, "footprint_bound": 413}`
- `evidence/esc-branch-4oz/summary_R1.json` → `"total": 523, "footprint_bound": 413`
- `evidence/esc-branch-4oz/REPORT.md:26` ("413 → 87"), `:99`, `:116`, `:167`, `:282`, `:340-342`
- carried into the board as "413 DRC items on every candidate" (`AGENT_BOARD.md:795`), "2 oz clears
  the 413" (`:570`, `:573`), "413 → 87 measured" (`:629`, `:637`)

**(a) and (b) are the same 413 objects.** Proof is a row-level diff keyed on KiCad item UUIDs
(§3.3): the power-first board and the routed board share **413 identical (type, uuid-tuple) rows**,
the routed board has **110 more**, and the placement board has **none** the routed board lacks.
The two figures agree to the object because intra-footprint pad gaps and PTH rings do not care where
the footprint sits. That is exactly why the population switch went unnoticed: **the placement-only
board's total and the routed board's footprint-bound subset are numerically identical at 413.**

### 1.3 Do they reproduce? — re-run, same board, same rules

| run | board | rules | violations | matches the historical figure |
|---|---|---|---|---|
| `A_own` | repo board | project `.kicad_pro`, **no** `.kicad_dru` | **16** | matches `summary_R0.json` (16) and `drc_summary.json` tag `2oz_orig` (16) |
| `B_4oz025` | repo board | `variant-025` (4 oz / 0.25 mm) | **523** | **YES — exactly, 3×, row-identical** |
| `C_4oz020` | repo board | `variant-020` (4 oz / 0.20 mm) | **102** | matches `variant-020/analysis.json` (102) |
| `P_powerfirst` | power-first placement | `variant-025` | **413** | **YES — exactly** (371 clearance + 42 annular, same rule names) |

So **523 reproduces on the board it describes; 413 reproduces on a board that is not that board.**
Neither figure is wrong — they answer different questions, and no previous unit ran the set diff
that makes the difference visible.

---

## 2. Instrument validation — the `.kicad_dru` really is being loaded

Every rule result below is worthless unless the rule file was parsed. Eight controls, all on the same
board copy:

| # | control | `.kicad_dru` | result | reads on |
|---|---|---|---|---|
| 1 | no rule file | none | **16** | baseline A |
| 2 | `(version 1)` present | `variant-025` | **523** | rules take effect |
| 3 | **version line removed**, rest byte-identical | `variant-025` minus `(version 1)` | **16** | **identical to control 1, 0 added / 0 gone** → file silently ignored |
| 4 | correct content, **wrong basename** (`other_name.kicad_dru`) | `variant-025` | **16** | 0/0 vs control 1 → the filename contract is real |
| 5 | **syntax error** in the file | `variant-025` + broken rule | **16** | 0/0 vs control 1 → a parse error rejects the whole file, it does not half-apply |
| 6 | deliberately wrong rule **0.30 mm clearance, placed FIRST** | +probe | **523** | probe did not take effect (precedence) |
| 7 | same probe **placed LAST** | +probe | **608** | **every one of the 499 clearance rows cites `rule 'PROBE clearance 0.30mm'`** |
| 8 | same probe with **no version line** | +probe, version removed | **16** | 0/0 vs control 1 → it is the version line that gates loading |

Positive evidence, not just counts: in run 7 the rule **name from the file** appears in the DRC text
(`Rule: PROBE clearance 0.30mm DELIBERATELY WRONG`), and the reported threshold changes with it.

Two further checks that the thresholds are honoured, not just the file:

- **Track-width probe, placed last** (`min track_width 0.30 mm`): total **673**, `track_width` **154** —
  and the board has exactly **154** track segments. The probe flagged every track, so the count is the
  full census, checkable by hand.
- **Threshold response**: a `track_width` violation on this board prints
  *"board setup constraints min width **0.2500** mm; actual 0.2000 mm"*, while the project's own
  `min_track_width` is **0.200**. The 0.2500 in the message can only come from the rule file.

**Precedence finding (worth keeping):** for the same constraint, the **last** matching rule wins.
Placed first, a probe is inert; placed last, it governs. Any future probe or rule edit must be appended,
not prepended.

### 2.1 A cap that would have made every big number unquotable — and proof of where it is

A suspicious plateau appeared while sweeping the clearance threshold: 0.30 mm → **499**, 0.50 mm → **499**,
and the row sets at those two thresholds were **not the same rows** (only 330 common, 278 gone, 266 added).
A count that repeats while the contents change is a truncation.

Known-good case, built here and checkable by hand (`mk_clearance_board.py`): N isolated pad pairs, each
with a 0.50 mm copper gap, under one rule `clearance min 2.00 mm` → exactly N violations by construction.

| pairs by construction | kicad-cli reports | verdict |
|---|---|---|
| 50 | **50** | exact |
| 400 | **400** | exact |
| 499 | **499** | exact |
| 550 | **499** | **truncated** |
| 700 | **499** | **truncated** |
| 1000 | **499** | **truncated** |

**kicad-cli 9.0.7 caps the clearance report at 499 markers** (same number as the unconnected cap; the
same boards also show the **399** `lib_footprint_issues` cap). The threshold sweep at 0.25 mm:

| clearance threshold (mm) | 0.20 | 0.22 | 0.24 | 0.245 | **0.25** | 0.255 | 0.26 | 0.27 | 0.28 | 0.30 | 0.40 | 0.50 | 0.60 | 0.80 | 1.00 | 2.00 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| clearance rows | 0 | 372 | 384 | 393 | **414** | 440 | 446 | 455 | 499 | 499 | 499 | 499 | 509 | 508 | 508 | 508 |

Monotone and unsaturated from 0.20 to 0.27, saturating from **0.28**; above the cap the count even goes
*down* (509 → 508) because the selected rows change. **The 414 at the 0.25 mm rule is 85 rows below the
cap and inside the monotone region, so it is a real count.** Every figure in §4 is likewise below a cap.

### 2.2 Determinism

Three identical repeats of the 523 run and two of the 533 run: **row-identical** (0 gone / 0 added on
item UUIDs). Coordinates can wobble in the last digit in the JSON (e.g. `92.839999` vs `92.84`), which
costs 2 rows on a coordinate-keyed diff — so **all set diffs here are keyed on item UUIDs**, and any
future set diff must be too.

### 2.3 One suppression that belongs in the baseline

`kicad-cli` without `--all-track-errors` reports **at most one clearance error per track**.
Adding the flag:

| | default | `--all-track-errors` | difference |
|---|---|---|---|
| total | 523 | **533** | +10 |
| clearance | 414 | **424** | +10 |
| every other type | unchanged | unchanged | 0 |

The 10 are all second conflicts on a track that already had one (e.g. the same `/3V3` track against a
second pad). **The complete count at the same rules is 533, not 523.** 523 is what the GUI/CLI default
and every earlier unit reported; 533 is what a fab review needs.

---

## 3. The three runs, with set diffs (row-level, UUID-keyed)

All three: same board copy, same `.kicad_pro`, differing only in the `.kicad_dru`.
"own rules" = the project `.kicad_pro` with no rule file (the board's own rules, since the repo ships none).

| run | rules | total | added vs own | gone vs own |
|---|---|---|---|---|
| **A** | own (`min_clearance 0.2`, `min_track_width 0.2`, `min_via_diameter 0.6`, `min_via_annular 0.1`) | **16** | — | — |
| **B** | 4 oz **0.25** mm (`variant-025`, ring 0.20, neck 0.25, PTH drill ≥0.20) | **523** | **+507** | **0** |
| **B'** | B + `--all-track-errors` | **533** | **+517** | **0** |
| **C** | 4 oz **0.20** mm (`variant-020`, same except pattern triple 0.20) | **102** | **+86** | **0** |

`gone = 0` in every case: the 4 oz rule sets are **strict supersets** of the board's own rules —
no rule relaxes anything, so nothing disappears when the rules are tightened. That is a real PASS and
it is the one thing about this board's DRC that was never in doubt.

### 3.1 B vs A — the 507 added, by type and rule

| type | severity | rule cited | n |
|---|---|---|---|
| clearance | error | `4oz-025 clearance 0.25mm min` | 414 |
| annular_width | error | `4oz-025 PTH annular ring 0.20mm min` | 42 |
| annular_width | error | `4oz-025 via annular ring 0.20mm min` | 28 |
| via_diameter | error | board setup (0.70 mm from the rule file) | 16 |
| track_width | error | board setup (0.2500 mm from the rule file) | 4 |
| connection_width | warning | `4oz-025 zone neck 0.25mm min` | 3 |
| **total** | | | **507** |

Retained from A: the 16 `via_dangling` warnings (present under every rule set).

### 3.2 C vs A — the 86 added

| type | rule cited | n |
|---|---|---|
| annular_width | `4oz-020 PTH annular ring 0.20mm min` | 42 |
| annular_width | `4oz-020 via annular ring 0.20mm min` | 28 |
| via_diameter | board setup | 16 |

At 0.20 mm every clearance, track-width and zone-neck violation disappears (414 + 4 + 3 = 421), and
**102 − 16 = 86** remain, all of them object-parameter violations that no routing can fix.

### 3.3 P vs B — the 110, as a set diff

| key | B (routed board) | P (placement-only) | common | gone | added |
|---|---|---|---|---|---|
| item UUIDs | 523 | 413 | **413** | **110** | **0** |

`common = 413` and `added = 0` is the whole reconciliation: the placement board's 413 rows are
**literally the same objects** as the routed board's 413 footprint-bound rows.

---

## 4. The 110, reconciled by type and coordinate

Full 110-row listing with coordinates: `110_items.csv` and `110_table.md` (reproduced in §7).

| type | rule | n | what fixes it |
|---|---|---|---|
| annular_width | `4oz-025 via annular ring 0.20mm min` | 28 | **via definition** (16 vias at 0.15 mm ring, 12 at 0.175 mm) |
| via_diameter | board setup 0.70 mm (from the rule file) | 16 | **via definition** (16 vias at 0.60 mm diameter) |
| via_dangling | board setup | 16 | **routing** (vias that connect nothing) |
| clearance — Track↔Track | `4oz-025 clearance 0.25mm min` | 24 | **routing** |
| clearance — Pad↔Track | `4oz-025 clearance 0.25mm min` | 19 | **routing** |
| track_width | board setup 0.2500 mm | 4 | **routing** (4 tracks at 0.200 mm) |
| connection_width | `4oz-025 zone neck 0.25mm min` | 3 | **zone/neck** (0.2217, 0.2049, 0.2000 mm necks) |
| **total** | | **110** | |

Grouped: **60 via-geometry + 47 routing + 3 zone neck = 110.** The 43 clearance rows are
**24 Track↔Track + 19 Pad↔Track**; `414 = 371 pad↔pad + 43`.

The four track-width rows and three zone-neck rows are all on F.Cu around U701/R712
(`/3V3`, `/Auxiliary power/LM2_FB`, `LM_FB`, `LM_RON`) — the same seven sites.

### 4.1 Why "98 pad rings + 12" is the wrong decomposition

The 110 is **not** 98 + 12. The 98 pad rings are a **third population that appears in neither 413 nor
523** (§5). The coincidence `140 − 42 = 98` and `523 − 413 = 110` are unrelated arithmetic:
`98 + 12 = 110` would be a coincidence with no row behind it, and a set diff produces **zero** of the
110 rows from pad-ring geometry. Anyone reproducing that arithmetic would be re-inventing the exact
defect class this programme keeps finding: **a correct measurement of the wrong population.**

---

## 5. The 98 pad rings — measured, explained, and invisible to DRC

Task 4 asks whether the 110 could be the 98 pad rings plus 12. It cannot. But the 98 is real and it
belongs beside the baseline, because **it is footprint-bound work the DRC total cannot see.**

### 5.1 Measurement

`pad_ring_census.py` (pcbnew 9.0.7) enumerated every hole:

| population | count |
|---|---|
| plated pads with a hole | 223 (5 NPTH separate) |
| **plated pads with ring < 0.200 mm** | **140** — 2 at 0.125, 12 at 0.150, 126 at 0.175 |
| vias | 1,990 (1,962 at 0.200, 12 at 0.175, 16 at 0.150) |
| **vias with ring < 0.200 mm** | **28** |

DRC at the 0.20 mm ring rule reports **42 pads + 28 vias**. Vias: **complete** (28 of 28).
Pads: **42 of 140** — the DRC sees **98 fewer ring defects than exist**.

### 5.2 Which 98, and why KiCad skips them

`ring_vs_drc.py` matched the reported-42 against the measured-140 by pad UUID:

| group | n | drill / pad / ring | footprints |
|---|---|---|---|
| reported | 42 | 0.65 / 1.00 / 0.175 (30) and 0.20 / 0.50 / 0.150 (12) | J1103–J1603 (5 each), U701 (6), U703 (6) |
| **not reported** | **96** | 0.20 / 0.55 / 0.175 | **U1101–U1601, pad "41" × 16 each** |
| **not reported** | **2** | 0.20 / 0.45 / 0.125 | **U204, pad "11" × 2** |

Every unreported pad shares its footprint pad number with a **larger covering pad** (U1101's pad 41 is
also a 4.15 × 4.15 mm F.Cu pad; U204's pad 11 is also a 1.65 × 2.40 mm F.Cu pad).

Mechanism proven on two hand-built boards (`mk_nested_ring_board.py`, `mk_same_number_board.py`),
each a 0.55 mm through pad with a 0.20 mm drill (ring 0.175) under a 0.20 mm ring rule:

| case | reported? |
|---|---|
| bare through pad | **yes** (1 violation) |
| through pad + 4.15 mm cover, **different** pad number | **yes** |
| through pad + 4.15 mm cover, **same** pad number | **no** |
| two small through pads, both number 1, far apart | **yes, both** |
| two small through pads, numbers 1 and 2 | **yes, both** |

So the skip is not "one report per pad number" and not "covered by copper" — it is
**"a same-numbered larger pad in the same footprint suppresses the smaller through pad(s)"**.
KiCad treats the pad number as one padstack and checks the largest.

### 5.3 Are they real defects, or a flooded-plane artefact?

`zone_cover_check.py` tested whether a same-net **filled zone** covers each of the 98 on each copper
layer (`HitTestFilledArea` per layer):

| layer | 98 pads covered by a same-net filled zone |
|---|---|
| F.Cu | 0 (they are covered by the 4.15 mm *pad*, not a zone) |
| In1.Cu | **0** |
| In2.Cu | **0** |
| B.Cu | 96 (the `/Mn_BATN` plane floods them) |

So on **F.Cu** the hole sits in a 4.15 mm pad (fine) and on **B.Cu** in the plane (fine), but on
**In1.Cu and In2.Cu** the drawn copper around the hole is a bare **0.175 mm** annulus with nothing
flooding it (U204's two are bare on three layers). **These are genuine sub-0.200 mm rings on the inner
layers that the DRC cannot report.** They are footprint-bound and no routing or placement clears them.

---

## 6. DEFINITIVE BASELINE — this table is the ESC's DRC baseline from now on

Command for every row: `kicad-cli pcb drc --format json --severity-all --units mm` on a copy of the
board with the named `.kicad_dru` installed as `<board basename>.kicad_dru`.

| rules | total (CLI default) | total (`--all-track-errors`) | added vs own | gone vs own | footprint-bound | copper-bound | of which routing-only |
|---|---|---|---|---|---|---|---|
| **own** (`.kicad_pro`, no `.kicad_dru`) | **16** | 16 | 0 | 0 | 0 | 16 | 16 (`via_dangling` only) |
| **4 oz 0.20 mm** (`variant-020`) | **102** | — | +86 | 0 | **42** | 60 | 16 |
| **4 oz 0.25 mm** (`variant-025`) | **523** | **533** | +507 / +517 | 0 | **413** | **110 / 120** | 47 + 16 dangling |
| **4 oz 0.25 mm, fab-real** (adds the 98 DRC-invisible rings) | **621** | **631** | +605 / +615 | 0 | **511** | 110 / 120 | 47 + 16 dangling |

Breakdown of the 4 oz / 0.25 mm row (default mode):

```
413  footprint-bound     371 pad<->pad clearance +  42 PTH annular   (no routing can touch it)
 60  via geometry         28 via annular + 16 via_diameter + 16 via_dangling
 47  routing              24 Track<->Track + 19 Pad<->Track +  4 track_width
  3  zone neck            3 connection_width
----
523  total                (533 with --all-track-errors: +10 more clearance rows
                          suppressed by the one-error-per-track default)
```

Severity split: **504 error / 19 warning** (16 `via_dangling` + 3 `connection_width`).

**Footprint-bound, by footprint** (413 rows; full coordinate list in `413_items.csv`, `413_table.md`):

| footprint(s) | items | type |
|---|---|---|
| U201 (QFN-80 P0.4) | 75 | clearance |
| U1102 / U1202 / U1302 / U1402 / U1502 / U1602 (LQFP-48 P0.5, 43 each) | 258 | clearance |
| J202 / J203 (USB-C, 19 each) | 38 | clearance |
| U701, U703 | 12 | annular_width |
| J1103–J1603 (5 each) | 30 | annular_width |

**The one number that must be quoted with a caveat:** 413 footprint-bound is what KiCad can see.
The measured footprint-bound pad population at the 0.20 mm ring rule is **511** (371 gaps + 140 rings).
So:

- **DRC-of-record: 523 items (533 complete).**
- **Fab-real at 4 oz / 0.25 mm: 621 items (631 complete)**, of which **511 are footprint-bound**.

Any claim of the form "413 → 87" or "413 disappears at 2 oz" is describing the footprint-bound subset
of a 523-item board and **silently omits 98 pad rings**. Replace it with: *at 2 oz the 421 pattern-driven
items go to 0 and 102 object-parameter items remain; 98 sub-0.200 mm pad rings are outside both counts
and stay until the padstacks change.*

---

## 7. Appendix — the 110, every row

`110_table.md` (also `110_items.csv`). Coordinates are mm, KiCad page frame, item 1 of each pair.

| # | type | rule | x | y | items |
|---|---|---|---|---|---|
| 1 | annular_width | via annular ring 0.20mm min | 111.417 | 18.955 | Via [/Controller and ADC/STATUS_LED] on F.Cu - B.Cu |
| 2 | annular_width | via annular ring 0.20mm min | 147.11 | 24.455 | Via [/Controller and ADC/CAN_SCK] on F.Cu - B.Cu |
| 3 | annular_width | via annular ring 0.20mm min | 152.61 | 24.455 | Via [/Controller and ADC/CAN_SCK] on F.Cu - B.Cu |
| 4 | annular_width | via annular ring 0.20mm min | 111.417 | 27.205 | Via [/Controller and ADC/STATUS_LED] on F.Cu - B.Cu |
| 5 | annular_width | via annular ring 0.20mm min | 78.174 | 86.563 | Via [/Motor 1 power cell/M1_STATUS_LED] on F.Cu - B.Cu |
| 6 | annular_width | via annular ring 0.20mm min | 163.174 | 86.563 | Via [/Motor 2 power cell/M2_STATUS_LED] on F.Cu - B.Cu |
| 7 | annular_width | via annular ring 0.20mm min | 66.625 | 91.332 | Via [/Motor 1 power cell/M1_DRV_SCLK] on F.Cu - B.Cu |
| 8 | annular_width | via annular ring 0.20mm min | 76.425 | 91.332 | Via [/Motor 1 power cell/M1_DRV_SCLK] on F.Cu - B.Cu |
| 9 | annular_width | via annular ring 0.20mm min | 151.625 | 91.332 | Via [/Motor 2 power cell/M2_DRV_SCLK] on F.Cu - B.Cu |
| 10 | annular_width | via annular ring 0.20mm min | 161.425 | 91.332 | Via [/Motor 2 power cell/M2_DRV_SCLK] on F.Cu - B.Cu |
| 11 | annular_width | via annular ring 0.20mm min | 81.424 | 93.063 | Via [/Motor 1 power cell/M1_STATUS_LED] on F.Cu - B.Cu |
| 12 | annular_width | via annular ring 0.20mm min | 166.424 | 93.063 | Via [/Motor 2 power cell/M2_STATUS_LED] on F.Cu - B.Cu |
| 13 | annular_width | via annular ring 0.20mm min | 78.174 | 169.063 | Via [/Motor 3 power cell/M3_STATUS_LED] on F.Cu - B.Cu |
| 14 | annular_width | via annular ring 0.20mm min | 163.174 | 169.063 | Via [/Motor 4 power cell/M4_STATUS_LED] on F.Cu - B.Cu |
| 15 | annular_width | via annular ring 0.20mm min | 66.625 | 173.832 | Via [/Motor 3 power cell/M3_DRV_SCLK] on F.Cu - B.Cu |
| 16 | annular_width | via annular ring 0.20mm min | 76.425 | 173.832 | Via [/Motor 3 power cell/M3_DRV_SCLK] on F.Cu - B.Cu |
| 17 | annular_width | via annular ring 0.20mm min | 151.625 | 173.832 | Via [/Motor 4 power cell/M4_DRV_SCLK] on F.Cu - B.Cu |
| 18 | annular_width | via annular ring 0.20mm min | 161.425 | 173.832 | Via [/Motor 4 power cell/M4_DRV_SCLK] on F.Cu - B.Cu |
| 19 | annular_width | via annular ring 0.20mm min | 81.424 | 175.563 | Via [/Motor 3 power cell/M3_STATUS_LED] on F.Cu - B.Cu |
| 20 | annular_width | via annular ring 0.20mm min | 166.424 | 175.563 | Via [/Motor 4 power cell/M4_STATUS_LED] on F.Cu - B.Cu |
| 21 | annular_width | via annular ring 0.20mm min | 78.174 | 251.563 | Via [/Motor 5 power cell/M5_STATUS_LED] on F.Cu - B.Cu |
| 22 | annular_width | via annular ring 0.20mm min | 163.174 | 251.563 | Via [/Motor 6 power cell/M6_STATUS_LED] on F.Cu - B.Cu |
| 23 | annular_width | via annular ring 0.20mm min | 66.625 | 256.332 | Via [/Motor 5 power cell/M5_DRV_SCLK] on F.Cu - B.Cu |
| 24 | annular_width | via annular ring 0.20mm min | 76.425 | 256.332 | Via [/Motor 5 power cell/M5_DRV_SCLK] on F.Cu - B.Cu |
| 25 | annular_width | via annular ring 0.20mm min | 151.625 | 256.332 | Via [/Motor 6 power cell/M6_DRV_SCLK] on F.Cu - B.Cu |
| 26 | annular_width | via annular ring 0.20mm min | 161.425 | 256.332 | Via [/Motor 6 power cell/M6_DRV_SCLK] on F.Cu - B.Cu |
| 27 | annular_width | via annular ring 0.20mm min | 81.424 | 258.063 | Via [/Motor 5 power cell/M5_STATUS_LED] on F.Cu - B.Cu |
| 28 | annular_width | via annular ring 0.20mm min | 166.424 | 258.063 | Via [/Motor 6 power cell/M6_STATUS_LED] on F.Cu - B.Cu |
| 29 | clearance | clearance 0.25mm min | 118.81 | 18.93 | Pad 67 [/Controller and ADC/CTRL_USB_DP_MCU] of U201 on F.Cu / Track [/3V3] on F.Cu, length 0.4000 mm |
| 30 | clearance | clearance 0.25mm min | 39.225 | 86.435 | Track [/Motor 1 power cell/M1_DRV_SCLK] on F.Cu, length 0.8485 mm / Track [/Motor 1 power cell/M1_DRV_SDI] on F.Cu, leng |
| 31 | clearance | clearance 0.25mm min | 39.225 | 86.435 | Track [/Motor 1 power cell/M1_DRV_SCLK] on F.Cu, length 6.2225 mm / Track [/Motor 1 power cell/M1_DRV_SDI] on F.Cu, leng |
| 32 | clearance | clearance 0.25mm min | 44.825 | 86.932 | Track [/Motor 1 power cell/M1_DRV_SCLK] on F.Cu, length 15.2000 mm / Track [/Motor 1 power cell/M1_DRV_SDI] on F.Cu, len |
| 33 | clearance | clearance 0.25mm min | 60.025 | 86.932 | Track [/Motor 1 power cell/M1_DRV_SCLK] on F.Cu, length 6.2225 mm / Track [/Motor 1 power cell/M1_DRV_SDI] on F.Cu, leng |
| 34 | clearance | clearance 0.25mm min | 129.825 | 86.932 | Track [/Motor 2 power cell/M2_DRV_SCLK] on F.Cu, length 15.2000 mm / Track [/Motor 2 power cell/M2_DRV_SDI] on F.Cu, len |
| 35 | clearance | clearance 0.25mm min | 145.025 | 86.932 | Track [/Motor 2 power cell/M2_DRV_SCLK] on F.Cu, length 6.2225 mm / Track [/Motor 2 power cell/M2_DRV_SDI] on F.Cu, leng |
| 36 | clearance | clearance 0.25mm min | 129.225 | 87.532 | Track [/Motor 2 power cell/M2_DRV_SCLK] on F.Cu, length 0.8485 mm / Track [/Motor 2 power cell/M2_DRV_SDI] on F.Cu, leng |
| 37 | clearance | clearance 0.25mm min | 38.18 | 87.77 | Pad 30 [/Motor 1 power cell/M1_DRV_nCS] of U1101 on F.Cu / Track [/Motor 1 power cell/M1_DRV_SCLK] on F.Cu, length 0.839 |
| 38 | clearance | clearance 0.25mm min | 123.68 | 87.77 | Pad 30 [/Motor 2 power cell/M2_DRV_nCS] of U1201 on F.Cu / Track [/Motor 2 power cell/M2_DRV_SCLK] on F.Cu, length 0.839 |
| 39 | clearance | clearance 0.25mm min | 63.225 | 89.435 | Track [/Motor 1 power cell/M1_DRV_SCLK] on F.Cu, length 6.2225 mm / Track [/Motor 1 power cell/M1_DRV_SDI] on F.Cu, leng |
| 40 | clearance | clearance 0.25mm min | 163.04 | 91.49 | Pad 14 [/Motor 2 power cell/M2_DRV_SDO] of U1202 on F.Cu / Track [/Motor 2 power cell/M2_DRV_SCLK] on F.Cu, length 0.850 |
| 41 | clearance | clearance 0.25mm min | 77.425 | 92.332 | Pad 14 [/Motor 1 power cell/M1_DRV_SDO] of U1102 on F.Cu / Track [/Motor 1 power cell/M1_DRV_SCLK] on F.Cu, length 0.850 |
| 42 | clearance | clearance 0.25mm min | 78.54 | 92.84 | Pad 16 [/Motor 1 power cell/M1_NTC] of U1102 on F.Cu / Track [/Motor 1 power cell/M1_DRV_SDI] on F.Cu, length 1.3500 mm |
| 43 | clearance | clearance 0.25mm min | 163.54 | 92.84 | Pad 16 [/Motor 2 power cell/M2_NTC] of U1202 on F.Cu / Track [/Motor 2 power cell/M2_DRV_SDI] on F.Cu, length 1.3500 mm |
| 44 | clearance | clearance 0.25mm min | 39.225 | 168.935 | Track [/Motor 3 power cell/M3_DRV_SCLK] on F.Cu, length 0.8485 mm / Track [/Motor 3 power cell/M3_DRV_SDI] on F.Cu, leng |
| 45 | clearance | clearance 0.25mm min | 145.245 | 168.935 | Track [/Motor 4 power cell/M4_DRV_SCLK] on F.Cu, length 0.8485 mm / Track [/Motor 4 power cell/M4_DRV_SDI] on F.Cu, leng |
| 46 | clearance | clearance 0.25mm min | 145.245 | 168.935 | Track [/Motor 4 power cell/M4_DRV_SCLK] on F.Cu, length 15.2000 mm / Track [/Motor 4 power cell/M4_DRV_SDI] on F.Cu, len |
| 47 | clearance | clearance 0.25mm min | 145.245 | 168.935 | Track [/Motor 4 power cell/M4_DRV_SCLK] on F.Cu, length 6.2225 mm / Track [/Motor 4 power cell/M4_DRV_SDI] on F.Cu, leng |
| 48 | clearance | clearance 0.25mm min | 44.825 | 169.432 | Track [/Motor 3 power cell/M3_DRV_SCLK] on F.Cu, length 15.2000 mm / Track [/Motor 3 power cell/M3_DRV_SDI] on F.Cu, len |
| 49 | clearance | clearance 0.25mm min | 60.025 | 169.432 | Track [/Motor 3 power cell/M3_DRV_SCLK] on F.Cu, length 6.2225 mm / Track [/Motor 3 power cell/M3_DRV_SDI] on F.Cu, leng |
| 50 | clearance | clearance 0.25mm min | 60.025 | 169.432 | Track [/Motor 3 power cell/M3_DRV_SCLK] on F.Cu, length 6.2225 mm / Track [/Motor 3 power cell/M3_DRV_SDI] on F.Cu, leng |
| 51 | clearance | clearance 0.25mm min | 60.025 | 169.432 | Track [/Motor 3 power cell/M3_DRV_SCLK] on F.Cu, length 6.2225 mm / Track [/Motor 3 power cell/M3_DRV_SDI] on F.Cu, leng |
| 52 | clearance | clearance 0.25mm min | 38.68 | 170.27 | Pad 30 [/Motor 3 power cell/M3_DRV_nCS] of U1301 on F.Cu / Track [/Motor 3 power cell/M3_DRV_SCLK] on F.Cu, length 0.839 |
| 53 | clearance | clearance 0.25mm min | 123.18 | 170.27 | Pad 30 [/Motor 4 power cell/M4_DRV_nCS] of U1401 on F.Cu / Track [/Motor 4 power cell/M4_DRV_SCLK] on F.Cu, length 0.839 |
| 54 | clearance | clearance 0.25mm min | 78.04 | 173.99 | Pad 14 [/Motor 3 power cell/M3_DRV_SDO] of U1302 on F.Cu / Track [/Motor 3 power cell/M3_DRV_SDI] on F.Cu, length 1.3500 |
| 55 | clearance | clearance 0.25mm min | 163.04 | 173.99 | Pad 14 [/Motor 4 power cell/M4_DRV_SDO] of U1402 on F.Cu / Track [/Motor 4 power cell/M4_DRV_SCLK] on F.Cu, length 0.850 |
| 56 | clearance | clearance 0.25mm min | 163.04 | 173.99 | Pad 14 [/Motor 4 power cell/M4_DRV_SDO] of U1402 on F.Cu / Track [/Motor 4 power cell/M4_DRV_SDI] on F.Cu, length 1.3500 |
| 57 | clearance | clearance 0.25mm min | 77.425 | 174.832 | Pad 14 [/Motor 3 power cell/M3_DRV_SDO] of U1302 on F.Cu / Track [/Motor 3 power cell/M3_DRV_SCLK] on F.Cu, length 0.850 |
| 58 | clearance | clearance 0.25mm min | 60.225 | 251.435 | Track [/Motor 5 power cell/M5_DRV_SCLK] on F.Cu, length 0.8485 mm / Track [/Motor 5 power cell/M5_DRV_SDI] on F.Cu, leng |
| 59 | clearance | clearance 0.25mm min | 60.225 | 251.435 | Track [/Motor 5 power cell/M5_DRV_SCLK] on F.Cu, length 6.2225 mm / Track [/Motor 5 power cell/M5_DRV_SDI] on F.Cu, leng |
| 60 | clearance | clearance 0.25mm min | 124.245 | 251.435 | Track [/Motor 6 power cell/M6_DRV_SCLK] on F.Cu, length 0.8485 mm / Track [/Motor 6 power cell/M6_DRV_SDI] on F.Cu, leng |
| 61 | clearance | clearance 0.25mm min | 124.245 | 251.435 | Track [/Motor 6 power cell/M6_DRV_SCLK] on F.Cu, length 6.2225 mm / Track [/Motor 6 power cell/M6_DRV_SDI] on F.Cu, leng |
| 62 | clearance | clearance 0.25mm min | 129.825 | 251.932 | Track [/Motor 6 power cell/M6_DRV_SCLK] on F.Cu, length 15.2000 mm / Track [/Motor 6 power cell/M6_DRV_SDI] on F.Cu, len |
| 63 | clearance | clearance 0.25mm min | 38.18 | 252.77 | Pad 30 [/Motor 5 power cell/M5_DRV_nCS] of U1501 on F.Cu / Track [/Motor 5 power cell/M5_DRV_SCLK] on F.Cu, length 0.839 |
| 64 | clearance | clearance 0.25mm min | 123.68 | 252.77 | Pad 30 [/Motor 6 power cell/M6_DRV_nCS] of U1601 on F.Cu / Track [/Motor 6 power cell/M6_DRV_SCLK] on F.Cu, length 0.839 |
| 65 | clearance | clearance 0.25mm min | 63.225 | 254.435 | Track [/Motor 5 power cell/M5_DRV_SCLK] on F.Cu, length 15.2000 mm / Track [/Motor 5 power cell/M5_DRV_SDI] on F.Cu, len |
| 66 | clearance | clearance 0.25mm min | 63.225 | 254.435 | Track [/Motor 5 power cell/M5_DRV_SCLK] on F.Cu, length 6.2225 mm / Track [/Motor 5 power cell/M5_DRV_SDI] on F.Cu, leng |
| 67 | clearance | clearance 0.25mm min | 65.425 | 254.435 | Track [/Motor 5 power cell/M5_DRV_SCLK] on F.Cu, length 6.2225 mm / Track [/Motor 5 power cell/M5_DRV_SDI] on F.Cu, leng |
| 68 | clearance | clearance 0.25mm min | 78.04 | 256.49 | Pad 14 [/Motor 5 power cell/M5_DRV_SDO] of U1502 on F.Cu / Track [/Motor 5 power cell/M5_DRV_SDI] on F.Cu, length 1.3500 |
| 69 | clearance | clearance 0.25mm min | 77.425 | 257.332 | Pad 14 [/Motor 5 power cell/M5_DRV_SDO] of U1502 on F.Cu / Track [/Motor 5 power cell/M5_DRV_SCLK] on F.Cu, length 0.850 |
| 70 | clearance | clearance 0.25mm min | 162.425 | 257.332 | Pad 14 [/Motor 6 power cell/M6_DRV_SDO] of U1602 on F.Cu / Track [/Motor 6 power cell/M6_DRV_SCLK] on F.Cu, length 0.850 |
| 71 | clearance | clearance 0.25mm min | 163.54 | 257.84 | Pad 14 [/Motor 6 power cell/M6_DRV_SDO] of U1602 on F.Cu / Track [/Motor 6 power cell/M6_DRV_SDI] on F.Cu, length 1.3500 |
| 72 | connection_width | zone neck 0.25mm min | 54.015 | 25.265 | Pad 1 [/Auxiliary power/LM2_FB] of R712 on F.Cu / Track [/Auxiliary power/LM2_FB] on F.Cu, length 1.6252 mm |
| 73 | connection_width | zone neck 0.25mm min | 66.905 | 27.715 | Pad 5 [/Auxiliary power/LM_FB] of U701 on F.Cu / Track [/Auxiliary power/LM_FB] on F.Cu, length 1.9568 mm |
| 74 | connection_width | zone neck 0.25mm min | 66.905 | 33.015 | Pad 4 [/Auxiliary power/LM_RON] of U701 on F.Cu / Track [/Auxiliary power/LM_RON] on F.Cu, length 1.8087 mm |
| 75 | track_width | (board setup) | 118.81 | 18.93 | Track [/3V3] on F.Cu, length 0.4000 mm |
| 76 | track_width | (board setup) | 54.015 | 25.265 | Track [/Auxiliary power/LM2_FB] on F.Cu, length 1.6252 mm |
| 77 | track_width | (board setup) | 68.67 | 28.56 | Track [/Auxiliary power/LM_FB] on F.Cu, length 1.9568 mm |
| 78 | track_width | (board setup) | 66.905 | 33.015 | Track [/Auxiliary power/LM_RON] on F.Cu, length 1.8087 mm |
| 79 | via_dangling | (board setup) | 111.417 | 18.955 | Via [/Controller and ADC/STATUS_LED] on F.Cu - B.Cu |
| 80 | via_dangling | (board setup) | 147.11 | 24.455 | Via [/Controller and ADC/CAN_SCK] on F.Cu - B.Cu |
| 81 | via_dangling | (board setup) | 152.61 | 24.455 | Via [/Controller and ADC/CAN_SCK] on F.Cu - B.Cu |
| 82 | via_dangling | (board setup) | 111.417 | 27.205 | Via [/Controller and ADC/STATUS_LED] on F.Cu - B.Cu |
| 83 | via_dangling | (board setup) | 78.174 | 86.563 | Via [/Motor 1 power cell/M1_STATUS_LED] on F.Cu - B.Cu |
| 84 | via_dangling | (board setup) | 163.174 | 86.563 | Via [/Motor 2 power cell/M2_STATUS_LED] on F.Cu - B.Cu |
| 85 | via_dangling | (board setup) | 81.424 | 93.063 | Via [/Motor 1 power cell/M1_STATUS_LED] on F.Cu - B.Cu |
| 86 | via_dangling | (board setup) | 166.424 | 93.063 | Via [/Motor 2 power cell/M2_STATUS_LED] on F.Cu - B.Cu |
| 87 | via_dangling | (board setup) | 78.174 | 169.063 | Via [/Motor 3 power cell/M3_STATUS_LED] on F.Cu - B.Cu |
| 88 | via_dangling | (board setup) | 163.174 | 169.063 | Via [/Motor 4 power cell/M4_STATUS_LED] on F.Cu - B.Cu |
| 89 | via_dangling | (board setup) | 81.424 | 175.563 | Via [/Motor 3 power cell/M3_STATUS_LED] on F.Cu - B.Cu |
| 90 | via_dangling | (board setup) | 166.424 | 175.563 | Via [/Motor 4 power cell/M4_STATUS_LED] on F.Cu - B.Cu |
| 91 | via_dangling | (board setup) | 78.174 | 251.563 | Via [/Motor 5 power cell/M5_STATUS_LED] on F.Cu - B.Cu |
| 92 | via_dangling | (board setup) | 163.174 | 251.563 | Via [/Motor 6 power cell/M6_STATUS_LED] on F.Cu - B.Cu |
| 93 | via_dangling | (board setup) | 81.424 | 258.063 | Via [/Motor 5 power cell/M5_STATUS_LED] on F.Cu - B.Cu |
| 94 | via_dangling | (board setup) | 166.424 | 258.063 | Via [/Motor 6 power cell/M6_STATUS_LED] on F.Cu - B.Cu |
| 95 | via_diameter | (board setup) | 111.417 | 18.955 | Via [/Controller and ADC/STATUS_LED] on F.Cu - B.Cu |
| 96 | via_diameter | (board setup) | 147.11 | 24.455 | Via [/Controller and ADC/CAN_SCK] on F.Cu - B.Cu |
| 97 | via_diameter | (board setup) | 152.61 | 24.455 | Via [/Controller and ADC/CAN_SCK] on F.Cu - B.Cu |
| 98 | via_diameter | (board setup) | 111.417 | 27.205 | Via [/Controller and ADC/STATUS_LED] on F.Cu - B.Cu |
| 99 | via_diameter | (board setup) | 78.174 | 86.563 | Via [/Motor 1 power cell/M1_STATUS_LED] on F.Cu - B.Cu |
| 100 | via_diameter | (board setup) | 163.174 | 86.563 | Via [/Motor 2 power cell/M2_STATUS_LED] on F.Cu - B.Cu |
| 101 | via_diameter | (board setup) | 81.424 | 93.063 | Via [/Motor 1 power cell/M1_STATUS_LED] on F.Cu - B.Cu |
| 102 | via_diameter | (board setup) | 166.424 | 93.063 | Via [/Motor 2 power cell/M2_STATUS_LED] on F.Cu - B.Cu |
| 103 | via_diameter | (board setup) | 78.174 | 169.063 | Via [/Motor 3 power cell/M3_STATUS_LED] on F.Cu - B.Cu |
| 104 | via_diameter | (board setup) | 163.174 | 169.063 | Via [/Motor 4 power cell/M4_STATUS_LED] on F.Cu - B.Cu |
| 105 | via_diameter | (board setup) | 81.424 | 175.563 | Via [/Motor 3 power cell/M3_STATUS_LED] on F.Cu - B.Cu |
| 106 | via_diameter | (board setup) | 166.424 | 175.563 | Via [/Motor 4 power cell/M4_STATUS_LED] on F.Cu - B.Cu |
| 107 | via_diameter | (board setup) | 78.174 | 251.563 | Via [/Motor 5 power cell/M5_STATUS_LED] on F.Cu - B.Cu |
| 108 | via_diameter | (board setup) | 163.174 | 251.563 | Via [/Motor 6 power cell/M6_STATUS_LED] on F.Cu - B.Cu |
| 109 | via_diameter | (board setup) | 81.424 | 258.063 | Via [/Motor 5 power cell/M5_STATUS_LED] on F.Cu - B.Cu |
| 110 | via_diameter | (board setup) | 166.424 | 258.063 | Via [/Motor 6 power cell/M6_STATUS_LED] on F.Cu - B.Cu |

---

## 8. What this settles, and what it does not

**Settled**

1. **523 is the shipped board's 4 oz / 0.25 mm total** and reproduces exactly and deterministically.
   With `--all-track-errors` it is **533**.
2. **413 is not a second total for the same board.** It is the footprint-bound subset of the 523, and
   separately the total of a copper-free placement board — the same 413 objects either way.
3. **The 110 is the copper-bound complement**: 60 via geometry, 47 routing, 3 zone necks.
   It is not 98 + 12.
4. **The `.kicad_dru` is loaded**, and a missing `(version 1)` silently voids the whole file.
   The last matching rule wins.
5. **The clearance report caps at 499.** The 0.25 mm figures sit well below it.
6. **98 of the 140 sub-0.200 mm pad rings are invisible to DRC** (same-numbered covering pad),
   and at least two of them are bare on In1/In2 — real footprint-bound defects.

**Not settled by this unit**

- Whether the 96 thermal-via rings are acceptable to a fab as *plated through thermal vias in a pad*
  rather than as annular ring: that is a fab question, and it is the one that decides whether the
  effective baseline is 523 or 621. Both numbers are stated; neither is asserted as the orderable one.
- The pad↔pad 371 are **real gaps at exactly 0.2000 mm** (the board's as-drawn geometry). Whether a
  4 oz fab can hold a 0.200 mm pad gap is `fab-esc-4oz`'s open question O1; this unit only counts them.
- `--all-track-errors` changes nothing else, but a fab review will want the 533 form, and every prior
  report used 523. Both are recorded here so neither is a surprise later.

---

## 9. Files in this directory

| file | what it is |
|---|---|
| `REPORT.md` | this report |
| `runs/<tag>/` | per-run board copies (`.kicad_pcb`, `.kicad_pro`, `.kicad_dru`) — all copies, never the repo |
| `out/<tag>.json` | raw kicad-cli DRC JSON for every run |
| `out/*.stdout.log` | raw kicad-cli console output |
| `rows/<tag>.csv` | every DRC row, one line each, with uuid/type/rule/coords |
| `rows/setdiff_*.log` | the set diffs quoted in §3 and §2 |
| `110_items.csv`, `413_items.csv` | every row of the two populations, with coordinates |
| `110_table.md`, `413_table.md` | the same, as the markdown tables in §4 and §6 |
| `baseline.json` | the §6 table in machine form, with the consistency checks |
| `ring_census.json`, `ring_vs_drc.log` | the 140 / 42 / 98 measurement and its explanation |
| `npth_followup.json`, `zone_cover.json` | the covering-pad and per-layer zone-coverage measurements |
| `known_good/` + `mk_*.py` | the hand-checkable boards (clearance cap 50/400/499/550/700/1000, nested ring, same pad number) |
| `rowsets.py`, `baseline_build.py`, `make_tables.py`, `pad_ring_census.py`, `ring_vs_drc.py`, `npth_followup.py`, `zone_cover_check.py` | the instruments; each reruns from the copies alone |