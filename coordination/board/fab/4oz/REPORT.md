# 4 oz copper: is 0.200 mm trace/space actually orderable?

**Unit:** fab-4oz-capability (wave 2, hotfix of the wave-1 "0.25 mm floor" extrapolation)
**Date:** 2026-11-15
**Scope:** published capability tables from real fabricators only. No blogs, no calculators, no
forum posts, no "PCB design rules guide" aggregators. Every number below is a quote from the
vendor's own page, and the quotes are stored verbatim in `sources/QUOTES.md`.

---

## 0. What was wrong before, and what this unit must settle

The wave-1 claim was: *"at 4 oz the pattern floor is 0.250 mm, therefore 371 pad-to-pad gaps of
0.2000 mm on the ESC are non-compliant."* The only support for 0.250 mm was **Eurocircuits' 3 oz
(105 µm) row**, which is the last row of their table. **No fabricator was asked.** 4 oz was never
in that table, so the number was an extrapolation one row above the data.

This unit asks the actual question: **does any real fab publish 0.200 mm (≈8 mil) trace/space at
140 µm (4 oz) copper?**

That single fact decides the ESC:
- **If yes** — the ESC ships exactly as drawn. Zero design work, 371 "violations" become a fab
  waiver, and blocker 5 on the board collapses to "pick the right house".
- **If no** — 4 oz as drawn is not orderable anywhere, and the choice is a copper-weight decision
  (drop to 2 oz, free) or three package changes (QFN-80 P0.4, 6 × LQFP-48 P0.5, 2 × USB-C).

---

## 1. The vendor table

Units: mm unless stated. "4 oz stated?" = does the table carry an explicit 4 oz / 140 µm row, or is
4 oz only implied by a range.

| # | fabricator | 4 oz stated? | min **trace** @ 4 oz | min **space** @ 4 oz | min **ring** @ 4 oz | source |
|---|---|---|---|---|---|---|
| 1 | **PCBWay** | **yes**, explicit row | **0.330** (13 mil) | **0.330** (13 mil) | 0.150 (generic, not oz-indexed) | [Thick Copper PCBs](https://www.pcbway.com/pcb_prototype/Thick_Copper_PCBs.html) |
| 2 | **Multi-CB** (DE) | **yes**, explicit 140 µm row | **0.300** std / **0.250** special | **0.300** std / **0.250** special | 0.300 std / **0.200** special | [Conductor / Copper thickness](https://www.multi-circuit-boards.eu/en/pcb-design-aid/surface/conductor-copper-thickness.html) |
| 3 | **Bay Area Circuits** | **yes**, explicit 4 oz row | **0.305** std / **0.279** adv | **0.305** std / **0.305** adv | 0.127 (generic, not oz-indexed) | [Capabilities](https://bayareacircuits.com/pcb-capabilities/) |
| 4 | **LeitOn** (DE) | **yes**, explicit 140 µm row | **0.300** | **0.400** | **0.250** | [Design rules, rigid](https://www.leiton.de/technologie-starre-leiterplatten.html) |
| 5 | **Advanced Circuits** (US) | **no — outer table stops at 3 oz** | 3 oz: 0.229 (no 4 oz row) | 3 oz: 0.229 (no 4 oz row) | — | [Manufacturing Capabilities](https://www.advancedpcb.com/en-us/resources/manufacturing-capabilities/) |
| 6 | **JLCPCB** | **no — heavy weights are 2-layer only** | 4-layer max 2 oz (0.160); 4.5 oz 2-layer: 0.300 | same | — | [Copper Weight Guide](https://jlcpcb.com/help/article/jlcpcb-copper-weight) |
| 7 | **Eurocircuits** | **no — copper column ends at 105 µm (3 oz)** | 3 oz: 0.250 (no 4 oz row) | 3 oz: 0.250 | 0.125 (class-based) | [Classification](https://www.eurocircuits.com/technical-guidelines/pcb-design-guidelines/classification/) + table image dated 07/05/2024 |
| 8 | **OSH Park** | **no — heaviest service is 2 oz, 2-layer** | — | — | — | [oshpark.com](https://oshpark.com/) |

Plus **PCBCart**, whose *DFM article* states "a 4 oz outer layer needs at least 9/9 mil
(0.23/0.23 mm)" ([source](https://www.pcbcart.com/article/content/heavy-copper-pcb-dfm)) — but that
is prose in an article, not a capability grid, so it is quoted as a supporting data point and not
counted as one of the tables above.

**The range across every explicit 4 oz row: trace 0.250–0.400 mm, space 0.250–0.400 mm.**
Five different houses, three countries, both pool and custom services — and the spread is the
chemistry, not a price tier: 0.250 mm is the tightest *published* 4 oz space anywhere in this set
(Multi-CB special production), and LeitOn needs 0.400 mm, i.e. **twice** the ESC's number.

Ratio check, which is the mechanism behind the whole table: published 4 oz space / 140 µm copper =
**1.8× (Multi-CB) to 2.9× (LeitOn)**, and 3 oz sits at 0.250/105 µm = 2.4×, 2 oz at 0.200/70 µm =
2.9×. Etch undercut scales with copper thickness, so the pattern floor tracks it almost linearly.
The ESC wants **0.200/140 µm = 1.43×** — below every published 4 oz figure and even below the
1 oz figure at Eurocircuits (0.125/35 µm = 3.6× but absolute 0.125).

---

## 2. Direct answer: is 0.200 mm at 4 oz available?

**No. Categorically no, from any of the eight fabricators surveyed, in any service tier
(standard, pool, advanced, custom).**

Evidence, in the strongest form available — not a missing row, but rows that exist and stop above it:

1. **PCBWay publishes 13 mil** (0.330 mm) for 4 oz on *both* outer and inner layers, and jumps to
   18 mil at 5 oz. 0.200 mm is 39 % below their published floor.
2. **Multi-CB publishes 0.300 mm** standard and **0.250 mm** even in "special production" for
   140 µm. Their 0.200 mm number exists — it belongs to the **105 µm (3 oz)** row.
3. **Bay Area Circuits publishes 0.012″ = 0.305 mm** for 4 oz outer, 0.011″/0.012″ advanced.
4. **LeitOn publishes 0.400 mm space** at 140 µm. Their 0.200 mm space number exists — it belongs to
   the **105 µm (3 oz)** row, in special production only.
5. **Advanced Circuits' outer-layer block has no 4 oz row at all** — it stops at 3 oz (0.009″ =
   0.229 mm), and 4 oz appears only as an inner-layer entry marked "N/A" in the advanced column.
6. **JLCPCB has no 4 oz row at all**; its heavy weights (2.5/3.5/4.5 oz) are restricted to 2-layer
   FR4, and the ESC is 4-layer.
7. **Eurocircuits' outer copper column ends at 105 µm.** No 140 µm row exists, so nothing at 4 oz
   is classifiable, let alone 0.200 mm.
8. **OSH Park** does not offer 4 oz at all.

**The nearest published number to 0.200 mm at 4 oz, anywhere, is 0.229 mm** (PCBCart's article;
0.250 mm from a real capability table). The ESC is therefore **0.029–0.200 mm short of the floor**,
i.e. 13 % to 50 % below it depending on house. This is not a margin question; it is a different
process window.

**Also disproved: the number is not a price tier.** If 0.200 mm at 4 oz were merely expensive, one
of the eight would have listed it as a premium/custom row — Multi-CB and LeitOn both *have* a
"special production / explicit request" column, and both of them put 4 oz *further away* from
0.200 mm than their standard row, not closer. Paying more does not buy this geometry at 4 oz.

---

## 3. Annular ring at 4 oz — and what the ESC actually has

Measured from the board, read-only, with KiCad's own bindings
(`measure_vias.py` → `esc_via_ring.json`, board `drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb`,
4,988,844 bytes):

| drill | pad Ø | **annular ring** | count |
|---|---|---|---|
| 0.40 mm | 0.80 mm | **0.200 mm** | 1,962 |
| 0.35 mm | 0.70 mm | **0.175 mm** | 12 |
| 0.30 mm | 0.60 mm | **0.150 mm** | 16 |
| | | **total vias** | **1,990** |

Through-hole pads: 215 PTH pads, **minimum ring 0.125 mm** (2 pads at 0.20 mm drill / 0.45 mm pad),
12 at 0.150 mm, 96 at 0.175 mm.

Against the 4 oz ring rules:

| fabricator | 4 oz min ring | ESC 0.150 mm | ESC 0.200 mm |
|---|---|---|---|
| **LeitOn** | **0.250 mm** | **FAIL** | **FAIL** |
| **Multi-CB** (special) | **0.200 mm** | **FAIL** | at limit |
| PCBWay (generic 6 mil) | 0.150 mm | at limit | pass |
| Bay Area (generic 0.005″) | 0.127 mm | pass | pass |

**Answer: at 4 oz, 0.10 mm is not legal at any house that indexes ring to copper weight, and 0.15 mm
is not legal at two of the three.** Concretely:
- **0.10 mm ring at 4 oz: not offered anywhere in this set.** (The ESC does not contain one — its
  floor is 0.125 mm — so this is context, not a defect.)
- **The ESC's 0.150 mm ring fails LeitOn (0.25) and Multi-CB (0.20) at 4 oz.**
- Worse, **at LeitOn's 0.25 mm 4 oz ring, all 1,990 vias fail** — the largest ring on the board is
  0.200 mm. A 4 oz LeitOn build needs every via pad grown from 0.80 to 0.90 mm.
- Only **PCBWay's generic 0.15 mm figure** would pass the board's current ring — and that line is
  not indexed to copper weight, so it is **UNVERIFIED at 4 oz**; PCBWay's own 4 oz table says
  nothing about ring.

So the ring is a **second, independent 4 oz blocker**. Even if a house waived trace/space in
writing, the 16 × 0.30/0.60 vias and the 2 × 0.20/0.45 PTH pads would still need re-padding, and a
LeitOn-class 4 oz process would need all 1,990 vias re-padded.

---

## 4. Cost tier — what 0.200 mm at 4 oz would cost

**It cannot be bought at any price from the surveyed set, so there is no tier to price.** What can
be priced is 4 oz itself, and that *is* a premium/custom tier almost everywhere:

| fabricator | how 4 oz is sold | price signal |
|---|---|---|
| Multi-CB | only under "**Special production**", explicitly **not** in the online calculator / standard column | custom quote |
| LeitOn | only "**auf explizite Anfrage**" (explicit request); their online calculator cannot order it | custom quote |
| Bay Area | inside "**Advanced Capability**" (outer copper 1–5 oz advanced vs 1–2 oz standard) | advanced tier |
| PCBWay | inside a dedicated **Heavy Copper** service page (own lead times 5–10 days vs 2–3 standard) | special service, quote |
| Eurocircuits | not in the classification system at all | UNVERIFIED whether offered |
| JLCPCB | not offered on 4-layer | n/a |

**No vendor publishes a percentage or dollar delta for 4 oz vs 1 oz.** The owner's real cost choice
is therefore not "pay for 0.200 mm at 4 oz" — that option does not exist — but "pay for 4 oz at
0.250–0.400 mm" (custom tier, plus three package changes) versus "2 oz, no design work, standard
tier".

---

## 5. What IS available at 4 oz, and where the cliff actually is

For judging the three options on the board, the useful ladder is the **highest copper weight at
which 0.200 mm space survives**:

| copper | tightest published space for 0.200 mm | verdict for 0.200 mm |
|---|---|---|
| **1 oz** (35 µm) | 0.125 (Eurocircuits), 0.100 (PCBWay/JLC/LeitOn/Multi-CB) | comfortable |
| **2 oz** (70 µm) | Eurocircuits **0.200** (exact), LeitOn **0.200** (exact), Multi-CB **0.150**, JLC **0.160** | **compliant, but at the limit at 2 of 4 houses** |
| **3 oz** (105 µm) | Multi-CB special **0.200/0.200**; LeitOn special **0.200 space** (0.250 track); Eurocircuits 0.250 | **0.200 mm space survives at one house; the 0.20 mm QFN pads sit exactly at Multi-CB's 0.200 track floor** |
| **4 oz** (140 µm) | 0.250 (Multi-CB special) to 0.400 (LeitOn) | **does not exist** |

Two consequences the board does not yet carry:

1. **2 oz is genuinely free of design work** — but it is *at the limit*, not inside it, at
   Eurocircuits and LeitOn, both of which explicitly say "do not design up to the limit"
   (Eurocircuits: "Do not design up to the limits of any given classification"). Multi-CB (0.150)
   and JLCPCB (0.160) give real margin at 2 oz.
2. **3 oz is the missing middle option.** It was not on the board's list of three. Multi-CB's
   "special production" 105 µm row permits **0.200 mm track and 0.200 mm space**, which the ESC
   already satisfies for its pad gaps; the QFN-80's 0.200 mm pads land exactly on the 0.200 mm track
   floor. That is at-the-limit engineering, not margin, and it is a custom-quote tier — but it keeps
   heavy copper in a way 4 oz cannot.

---

## 6. Verdict

**The ESC cannot ship at 4 oz as drawn. Not at 0.200 mm, not at any surveyed house, not in any
service tier.**

- The 371 pad-to-pad gaps of 0.2000 mm are **real and correctly counted** (they are the same
  geometric fact the wave-1 driver measured: U201 QFN-80 75, 6 × LQFP-48 43 each = 258, J202/J203
  19 each = 38, total 371 — `fab-esc-4oz/REPORT.md:170-174`), but the reason they fail is now
  sourced: **every explicit 4 oz row in the industry sits at 0.250–0.400 mm.**
- The board's blocker-5 text should change from "at 140 µm the pattern floor is 0.25 mm" (an
  extrapolation) to "**no surveyed fab publishes a 4 oz pattern below 0.229 mm; the tightest
  capability-table figure is 0.250 mm**". The conclusion is unchanged; the provenance is now real.
- The 523-violation DRC at "0.25 mm" rules was **optimistic**, not pessimistic: a LeitOn-class 4 oz
  build would be judged against 0.30/0.40/0.25, i.e. more violations, not fewer. The verdict is
  robust in the safe direction.
- **The ring is a second independent blocker**, and it is not "one number": 0.150 mm fails the two
  houses that publish a 4 oz ring, and all 1,990 vias fail a LeitOn 4 oz ring of 0.25 mm.

**Consequence for the owner's three options:**
1. *"The fab accepts 0.200 mm at 4 oz in writing"* — **dead as a plan.** There is no house to ask;
   the two houses with a written "special production" column price 4 oz *further* from 0.200 mm,
   not closer. This is not a waiver, it is a process that does not exist.
2. *"Drop the ESC to 2 oz"* — **works, zero design work, standard price**, with the caveat that
   0.200 mm is exactly at the limit at Eurocircuits/LeitOn (fine at Multi-CB 0.150 and JLC 0.160).
3. *"Change 3 packages"* — the honest engineering fix if 4 oz must stay. Note that even then the
   4 oz ring forces a via re-pad (0.80 → 0.90 mm at a LeitOn-class process), which is a routing
   change on 1,990 vias, so option 3 is larger than "3 packages".

A fourth option the board does not carry, offered as evidence rather than recommendation:
**3 oz at Multi-CB special production (0.200/0.200/0.170)** keeps heavy copper *and* keeps the
0.200 mm geometry — at the limit, custom quote, and the QFN pads exactly on the track floor.

---

## 7. Board corrections this unit proposes

- **BOARD CORRECTION, line 469** — "At 140 µm the pattern floor is 0.25 mm; these pads cannot be
  made compliant by any edit." The *conclusion* stands. The *number* was never a 4 oz number; it was
  Eurocircuits' 3 oz row. Replace with: **"no surveyed fab publishes a 4 oz pattern tighter than
  0.229 mm; capability tables give 0.250 (Multi-CB special), 0.305 (Bay Area), 0.330 (PCBWay),
  0.400 (LeitOn)."**
- **BOARD CORRECTION, line 469 (addition)** — the ring is a second 4 oz blocker and is not on the
  board at all: min via ring **0.150 mm** fails Multi-CB (0.200) and LeitOn (0.250) at 4 oz.
- **Addition to the option list** — 3 oz is the highest weight at which 0.200 mm space is published
  by a real fab (Multi-CB special production, 105 µm row). The board's three options omit it.

---

## 8. Limitations — what is UNVERIFIED and why

| item | status |
|---|---|
| **Würth Elektronik 4 oz** | **UNVERIFIED.** `we-online.com` design-rules PDF = HTTP 403 (Akamai). `wedirekt.com` mirror downloaded (1,306,679 B, 6 pages) but contains no copper-thickness table (PyMuPDF: 0 hits for 140/105/70 µm + copper). |
| **Sierra Circuits 4 oz** | **UNVERIFIED.** Public capability pages are marketing bullets (2 mil / 1.5 mil trace-space) with no copper-weight axis; the Trace & Space Handbook body is gated behind a form. No 4 oz row retrieved. |
| **Eurocircuits 4 oz** | **UNVERIFIED whether they offer it at all.** Their classification table has no 140 µm row, but their own text says "not all copper thicknesses are available in all services", so absence from the table is absence from the *classification system*, not proof that a custom 4 oz order is refused. |
| **Ruwel/Schweizer, TTM, Elco, Candor** | **UNVERIFIED / not usable.** No public copper-indexed table retrievable (Candor publishes trace limits with no oz axis; the others are quote-gated). Search returned nothing for the specific queries. |
| **4 oz price delta** | **UNVERIFIED.** No vendor publishes 4 oz vs 1 oz pricing; all four that offer it route to a quote. |
| **PCBWay 4 oz annular ring** | **UNVERIFIED at 4 oz.** Their 0.15 mm ring is a single generic figure covering 1–8 oz; the heavy-copper page is silent. Treated as "at limit, unconfirmed", not as permission. |
| **Whether the ESC's 371 gaps are on outer layers only** | assumed outer (all three are SMD land patterns: QFN-80, LQFP-48, USB-C receptacle) — consistent with `fab-esc-4oz/REPORT.md:170-174`, not independently re-measured here. |

---

## 9. Artefacts in this directory

| file | what it is |
|---|---|
| `REPORT.md` | this report |
| `sources/QUOTES.md` | verbatim vendor rows + URLs, and the "checked but unusable" list |
| `sources/wurth_basic_design_guide.pdf` | Würth mirror PDF (1,306,679 B) — kept to show the 403 fallback was tried and that it lacks the table |
| `measure_vias.py` | read-only pcbnew measurement of ESC via/pad rings |
| `esc_via_ring.json` | its output: 1,990 vias, drill/pad/ring histogram, 215 PTH pads |
| `vendors.csv` | the table in §1, machine-readable |
| `check_arithmetic.txt` | unit conversions and space/copper-thickness ratios used in §1 and §2 |