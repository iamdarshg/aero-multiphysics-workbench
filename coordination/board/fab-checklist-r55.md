# Master pre-fab checklist — r55

**Generated from measured state, 2026-11-18.** Every cell is **PASS with evidence**, **WAIVED with a stated
reason**, or **OPEN with what remains**. No UNKNOWN cells.

**Provenance rule:** each number names its tool and whether it was measured here, reproduced across two
tools, or carried from a named report. Any figure at **499** is labelled **CAPPED** — that is a list limit,
not a measurement.

---

## 1. Conditions table — 6 boards × 5 conditions

| board | (i) DRC at correct rules | (ii) zero unconnected | (iii) zero geometry defects | (iv) package validated | (v) checklist closed |
|---|---|---|---|---|---|
| **Code-SDR V2** | **PASS** — 0 errors, 222 pre-existing warnings | **PASS** — 0 on kicad-cli **and** pcbnew | **PASS** — no unresolved defects | **PASS** — rev 2.1, SurfaceFinish ENIG, **19/19** manifest | **PASS** |
| **dev-board** | **PASS** — 0 errors, 2 lib-mismatch warnings (excluded, justified) | **PASS** — 0 on both tools | **PASS** — 8 real defects fixed, set diff 0 new | **PASS** — rev B, ENIG/ENIG, **28/28** manifest, 2085 hits | **PASS** |
| **ESC power rev_b** | **OPEN** — 527 listed = **499 CLEARANCE CAP** + 28 silk | **OPEN** — 0 for existing nets, but **756 of 1,581 pads are netless** | **PASS** — no geometry defect found | **OPEN** — no package produced | **OPEN** |
| **ESC control rev_a** | **OPEN** — 35 | **OPEN** — 249 | **OPEN** — remaining footprint/passive items resolved, but netlist incomplete | **OPEN** — no package | **OPEN** |
| **drone-arm main rev_b** | **OPEN** — 33 | **OPEN** — 8 | **OPEN** — 5 pads, **measured dead end** | **OPEN** — rev B package exists but **not sendable** | **OPEN** |
| **drone-mech assembly** | **N/A** (no PCB) → geometry condition | **N/A** | **PARTIAL** — **0 genuine clash**; knuckles unfastenable; knife edge open | **PARTIAL** — DM-FUS-001 rev exists | **OPEN** |

**Totals: 12 PASS / 0 WAIVED / 15 OPEN / 3 N/A — and one owner waiver outstanding (HDI on dev-board).**

*Correcting the previous sheet: it recorded dev-board at 2 PASS / 3 OPEN. That was true before this
round's fixes; dev-board is now 5/5 and its package is verified.*

---

## 2. Per-board one-line status

| board | status | the single thing that blocks it |
|---|---|---|
| **Code-SDR V2** | **ORDERABLE** | **nothing engineering** — 373 MPNs to source |
| **dev-board** | **ORDERABLE** (contingent on HDI acceptance) | **owner must accept HDI** — 201 non-through vias, proven unremovable (+545 violations, 80 shorts if forced) |
| **ESC power rev_b** | **routed, not complete** | **756 netless pads** (all 390 DRV8353) — the nets must exist before gate drive can route |
| **ESC control rev_a** | **not orderable** | **the schematic** — 7 sheets, 169 symbols, 725 labels, **12–17 h** |
| **drone-arm main rev_b** | **not sendable** | **U10 needs a placement or package change** — short 0.0027 mm on one track tie |
| **drone-mech** | fuselage **fab-ready**, assembly not released | **knuckles are unfastenable pegs**; knife edge needs the **+157.55 g fairing** |

---

## 3. Evidence per PASS cell

**Code-SDR V2**
- DRC 0 errors / 222 warnings; **0 unconnected on both tools**; package `cs-orderable-fix/package/`
- `SurfaceFinish` was **ABSENT as a key** (not merely empty) — fixed by re-export from design data
  (`copper_finish ENIG`) plus an idempotent `Finish`→`SurfaceFinish` copy
- Manifest **19 of 19**, verified with own parser **and** coreutils 8.32 **and** WSL 9.4, exit 0
- Drills **1213 + 2 G85 slots = 1215 hits** (my own count); POS **377**; outline **101.7000 × 101.7000 mm**;
  4 copper; **rev 2.1**

**dev-board**
- DRC **10 → 2** warnings, **0 errors**, **0 unconnected on both tools**
- The 52 `lib_footprint_issues` were **an isolation artefact of my own** — the libraries were in the repo
- 8 real defects fixed: 5 `copper_sliver`, 2 `holes_co_located`, 1 `track_dangling`; **set diff 0 new**
- `SurfaceFinish` empty → **ENIG**; POS **292 → 307** (root cause: `--smd-only` silently dropped **18
  through-hole connectors**); **rev B** stamped (board had no title block)
- Manifest **28/28**; drills **2069 + 16 slots = 2085 hits**; `front-in1` 183 + `front-in2` 1 + `in1-in2`
  17 = **201 = the non-through count exactly**

**ESC power**
- **Routed: 0 unconnected on both tools, DRC set diff 0 added / 0 gone**
- Gate loops **89.61 mm mean / 158.58 worst**, reproducing the placement measurement to 0.1 mm
- Power path untouched: 18 phases **6.00 mm = 26.4 A**, BATN **4.00 mm = 19.7 A**, BATP **16.0 A**;
  **only J_H1–J_H3 on B.Cu**
- **But 756 of 1,581 pads netless**, and gate drive's "0 unconnected" is an artefact of 36 nets each having
  a single netted pad

**drone-mech**
- **0 genuine clash**; 12 pairs / 197.519831 mm³ = 0 + 10 contact / 192.590677 + 2 withdrawn / 4.929154
- Vane slot cut on all four brackets (**396.917134 mm³ = 3.909 %**); collar **3.067 → 0.305 σ_y**
- Fuselage **byte-identical 206,454.319709 mm³ / 320.0042 g**, 1 solid, walls 1.0921 / 1.1990 / 1.1800;
  **ring v2 0.000000 × 28 parts**

---

## 4. Open questions — decisions, not measurements

| # | question | recommendation | cost |
|---|---|---|---|
| 1 | **Accept HDI on dev-board?** 201 non-through, unremovable | **Accept.** One blind span Top→Ground L1, cheapest class, already released | fab premium only |
| 2 | **drone-arm: change U10?** short 0.0027 mm on one tie | Needs a **placement or package change**. Twelve local attempts have all measured out the same | redesign |
| 3 | **drone-mech knife edge:** fairing or accept? | **Fairing** — 2.475 µm feather and 381–471 cm² of missing flank is not manufacturable | **+157.549 g** |
| 4 | **ESC control schematic:** 12–17 h of work | It is the gate. Code-SDR's 8-sheet schematic is the precedent | 12–17 h |
| 5 | **ESC power netlist:** net the 756 pads | Highest-value remaining item — the board is otherwise routed | in progress |

---

## 5. Corrections carried (52 total: 35 carried forward + 17 new)

Live and load-bearing:
- **BC-HDI:** classify HDI by **span**, never drill diameter. A 0.300 mm blind via is still HDI.
- **BC-DRU:** a `.kicad_dru` without `(version 1)` is **silently ignored** — prove rule load with a
  deliberately-wrong rule.
- **BC-499:** kicad-cli's unconnected list caps at **499**. Quote pcbnew; label any 499 **CAPPED**.
- **BC-COMPANION:** DRC outside the project dir **invents** footprint-library violations. This produced 52
  fake violations on dev-board.
- **BC-GETWIDTH:** **`PCB_VIA.GetWidth()` hangs indefinitely in KiCad 9.** It killed five runs. Read via
  size by text-parsing `(size …)`.
- **BC-VIATYPE:** via type ints are **1 micro / 2 blind-buried / 3 through**; `VIATYPE_BLIND`/`BURIED` do
  not exist.
- **BC-PACKAGE:** a "complete" claim must **verify the package against the board**. Three boards had
  finished boards and unorderable packages.
- **BC-GBRJOB:** KiCad 9.0.7 **never writes `SurfaceFinish` at all**. Set the finish as stackup design data
  and copy `Finish`→`SurfaceFinish` afterwards.
- **BC-SLOTS:** drills and G85 slots are **never one number**. 367 drills + 4 slots ≠ 371 drills.
- **BC-POS:** `--smd-only` **silently drops through-hole connectors**. Use `--exclude-dnp`.

---

## 6. Limits of this sheet

- **The ESC clearance figure is capped.** 527 listed = 499 cap + 28 silk; the true clearance count is ≥499
  and has not been enumerated.
- **drone-arm's dead-end finding is local-change scope only.** It does not establish that no redesign works.
- **No simulation substitutes for test.** Every number here is a static measurement or a hand calculation;
  none is a thermal, structural or electrical test result.
- **The HDI acceptance is the owner's call, not mine**, and dev-board's ORDERABLE verdict rests on it.