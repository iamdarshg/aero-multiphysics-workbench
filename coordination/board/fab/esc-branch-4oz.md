# ESC rev_b at 4 oz — the FULL REDESIGN priced, for comparison with the 2 oz branch

**Item:** price the ESC at **4 oz with the package changes as a full redesign**, in the same shape as
the 2 oz branch so the two can be compared line for line.
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/esc-branch-4oz/`
**Board of record:** `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb`,
sha256 `992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD`, 4,988,844 B.
Copied byte-identically to `kicad/esc_rev_b.kicad_pcb` (same sha256). **The repo was never written
to**: every edited board in this unit is a copy under `kicad/e5`, `kicad/e6`, `kicad/e7`.
**Tooling:** KiCad 9.0.7 `kicad-cli pcb drc`; KiCad 9.0.7 `python.exe` + `pcbnew` 9.0.7; CPython 3.12.
**Copper weight, re-asserted from the file:** `esc_rev_b.kicad_pcb:52` = 0.14, `:63` = 0.0525,
`:74` = 0.0525, `:85` = 0.14 → **4 oz outer / 1.5 oz inner**.

---

## 0. The answer in one table

| question | answer |
|---|---|
| Packages that must change **as parts** | **ONE — U201 (RP2354B, QFN-80, P0.4)**. **No equivalent found** at a coarser pitch. |
| Footprints that must change **as geometry** | **24** (the 413 items live in 17; the sub-0.25 mm pads and the 0.20 mm holes add 7 more) |
| Netlist impact | **NO — if U201 stays.** **YES — if U201 is replaced**, and then it is a new MCU: symbol, pin mapping and firmware. |
| BATP rail fix at 4 oz | join the **10** F.Cu components, keep In1's 16.00 mm in parallel → **≥8.56 mm continuous 4 oz neck** → **59.05 A (100 %)** |
| BATN rail fix at 4 oz | **45 → 63 barrels** (+18) → 1.9792 mm² → **60.5 A (103.4 %)** |
| Achievable area at 4 oz after the package work | **382.71 cm² unchanged** (+1.19 cm² only if the MCU grows to an LQFP-100) |
| Footprint-bound DRC after | **413 → 87** at the bill-of-record rules (measured); **523 → 197** at the task's 0.30 mm-hole rules (measured) |
| Footprints changed (effort) | **24 required / 945 pads; 21 executed and DRC-verified / 600 pads** |
| **BUILDABLE + CAPABLE at 4 oz** | **NO** — 4 oz is buildable for 23 of 24 footprints, but **not with U201**, and the rail is only capable after a re-pour that has not been drawn. |

The single sentence: **at 4 oz this ESC is not a "three packages" job — it is one impossible one (the
0.4 mm-pitch MCU) plus 23 footprint edits that keep their parts and their netlist.**

---

## 1. Rule basis, controls, and the two instrument fixes this unit had to make

### 1.1 The rule set is inherited, not invented

`0.25 mm` trace / space and `0.20 mm` annular ring come from `evidence/fab-esc-4oz/kicad/esc_rev_b.kicad_dru`
(11 rules, `(version 1)` present) and its basis, the Eurocircuits classification table
(`evidence/fab-esc-4oz/sources/EC-classification-ENGLISH-5-2024-V3.png`): 1 oz → 0.125, 2 oz → 0.200,
3 oz → 0.250 mm, and the table **stops at 3 oz**, so 0.250 is the last published floor and 4 oz can
only be equal or wider. The task's `0.30 mm` minimum finished hole is the *only* change in this unit's
rule set (rule file `kicad/r2_task/esc_rev_b.kicad_dru`, line 45).

### 1.2 EVENT 4 — the `.kicad_dru` was proven READ, not assumed

Every DRC run below names its rules in the violation text, e.g.
`Annular width (rule '4oz via annular ring 0.20mm min' min annular width 0.2000 mm; actual 0.1500 mm)`.
`11_map_drc.py` counts those rule names and prints them; a run that names none is declared VOID. The
counts are in `logs/11_map_fixed.log`.

### 1.3 Known-good reproduction, twice

| run | board | rules | violations | unconnected | matches |
|---|---|---|---|---|---|
| R0 control | as-built | 2 oz class (0.20/0.20, ring 0.15, via 0.60) | **16** | 499 | `fab-esc-4oz` run B = 16 ✓ |
| R1 | as-built | 4 oz (0.25/0.25, ring 0.20, PTH ≥0.20) | **523** | 499 | `fab-esc-4oz` run C = 523 ✓ |
| R2 | as-built | 4 oz **task** (PTH ≥0.30) | **633** | 499 | 523 + 110 = 633 ✓ |

`633 − 523 = 110` is not a coincidence: it is exactly the 110 pads drilled 0.200 mm
(`fab-esc-reconcile`, `t2_110_pads.csv`). The new rule finds the same 110 and nothing else.

### 1.4 Instrument bug #1 I had to fix — the PTH-pad description form

My first classifier returned **371** footprint-bound items, not 413. Cause: `kicad-cli` writes pad
items in **two** forms —

```
Pad 67 [/Controller and ADC/CTRL_USB_DP_MCU] of U201 on F.Cu     ← SMD/generic
PTH pad 41 [/M1_BATN] of U1101                                   ← through-hole: no " on "
```

A regex that required ` on ` after the reference silently dropped **all 42 PTH-pad annular items**
and under-reported by exactly 42 (371 + 42 = 413). Fixed in `11_map_drc.py:47-53` with the bug
documented in place. This is the same defect class as the five broken instruments on the board: an
ASCII-shaped assumption (one description format) missing real rows.

### 1.5 Instrument bug #2 — a DRC rule set that cannot see pad width

KiCad constrains **track** width and clearance. It has **no rule for "this pad is narrower than the
process minimum"**. So the DRC count is a **floor** on the package work, and I measured the rest
directly (`14_pad_width_census.py`): **330 pads are narrower than 0.25 mm** in **3 footprint ids /
8 footprints** — 240 at 0.22 mm (DRV8353), 80 at 0.20 mm (U201), 10 at 0.24 mm (TPS3430). Of those,
**no DRC item exists for 250 of them.** Any answer built on the 413 alone understates the package work.

---

## 2. Task 1 — exactly which packages must change, and to what

### 2.1 The 413, mapped (row-level, `rows_R1.csv`, `summary_R1.json`)

**FOOTPRINT-BOUND, stated before the result:** a violation is footprint-bound iff *every* item in it
is a Pad carrying an owning footprint reference. A pad is inside a footprint by construction, so its
geometry cannot be moved by routing, placement or refill.

| footprint-bound | routing/refill-movable |
|---|---|
| **413** | **110** |
| 371 `clearance` (pad↔pad) + 42 `annular_width` (PTH pad) | 43 clearance + 28 via annular + 16 via_diameter + 16 via_dangling + 4 track_width + 3 connection_width |

(The 110 non-footprint-bound is a numerical coincidence with the 110 drilled pads — they are
different populations. Stated so it is not mistaken for one.)

All 371 pad↔pad gaps are **exactly 0.2000 mm** — one number, repeated.

| ref | footprint id | part | items | pitch | pad across pitch | gap | compliant pad at 0.25 space | verdict |
|---|---|---|---|---|---|---|---|---|
| **U201** | `QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm` | **RP2354B** | **75** | **0.40** | 0.20 | 0.20 | **0.15** | **IMPOSSIBLE** — 0.15 < 0.25 min feature, and 0.15 > 0 gap is itself unetchable |
| U1102…U1602 (×6) | `LQFP-48_7x7mm_P0.5mm` | **STM32G431CBT6** | 43 ea = **258** | 0.50 | 0.30 | 0.20 | **0.25** | **FIXED — executed**, same part |
| J202, J203 | `USB_C_Receptacle_GCT_USB4105-xx-A_16P` | **GCT USB4105-16P** | 19 ea = **38** | 0.50 | 0.30 | 0.20 | **0.25** | **FIXED — executed**, same part |
| J202, J203 (fingers) | same | same | (in the 38) | 0.80 | 0.60 | 0.20 | **0.55** | **FIXED — executed**, same part |
| J1103…J1603 (×6) | `PinHeader_1x05_P1.27mm` | LOCAL_SWD | 5 ea = **30** | 1.27 | 1.00 | 0.27 | ring 0.20 needs **drill ≤0.60** | **FIXED — executed** by drill 0.65→0.60 (pad growth to 1.05 would give 0.22 gap — worse) |
| U701, U703 | `HSOP-8-1EP_…_EP2.41x3.1_ThermalVias` | **LM5164DDA** | 6 ea = **12** | 1.30 / 1.91 | pad 0.55, drill 0.20 | 0.60 / 1.21 | pad **0.70** + drill 0.30 | fixable, **not executed** |

**17 footprints, 413 items.** Only **one** of them is a real package change; the other 16 are
footprint geometry on the same part.

### 2.2 The part that has no equivalent

**U201 = RP2354B, QFN-80-EP, 10 × 10 mm, 0.40 mm pitch, 80 perimeter pads + EP.**
Board-measured, not name-inferred: 20 pads/side, pad 0.20 mm, gap **0.2000 mm**, pitch **0.40 mm**
(`13_fp_geometry.json`; footprint `descr` cites the RP2350 datasheet,
[rp2350-datasheet.pdf](https://pip.raspberrypi.com/documents/RP-008373-DS-rp2350-datasheet.pdf), and the
board's `Value` is `RP2354B`).

At 0.40 mm pitch, a 0.25 mm space leaves a **0.15 mm** pad. That is **below the 0.25 mm minimum
feature and below any 4 oz etch on earth**. There is no pad width that complies. **No equivalent
found:** every RP2350-family variant is the same fine pitch (RP2350A is QFN-60 at 0.40 mm too), and
the *geometric* check confirms it — 20 pins/side × 0.40 = 8.0 mm of a 10 mm body, which is the normal
QFN land, whereas 20 × 0.50 = 10.0 mm leaves no land at all. So this is not a KiCad footprint bug; the
part really is 0.4 mm pitch.

A 0.5 mm-pitch replacement exists **as a class** (e.g. an LQFP-100 14 × 14, 0.5 mm pitch, 25 pads/side,
which is 4 oz-compatible at pad 0.25 / gap 0.25). It is **not pin-compatible** with RP2354B: different
package, different pinout, different peripherals, new symbol, new firmware. That is the netlist break.

> Tier: package pitch is **MEASURED** on the board. The datasheet itself could not be fetched
> (`pip.raspberrypi.com` → `pip-assets` cross-origin redirect), so the "RP2354B is 0.4 mm pitch"
> statement rests on board geometry + the geometric infeasibility of 0.5 mm at 80 pins. Flagged in §9.

### 2.3 Datasheet citations I could and could not close

| part | citation | status |
|---|---|---|
| STM32G431CBT6 (LQFP-48 0.5 mm) | land-pattern edit needs no new citation: the **part does not change**, only pad width 0.30→0.25 on 0.50 pitch | **CITED BY NON-CHANGE** |
| GCT USB4105-16P | likewise: USB-C contacts are 0.5 mm pitch by standard, so 0.25 pad / 0.25 space is the only compliant option | **CITED BY NON-CHANGE** |
| RP2354B | [RP2350 datasheet](https://pip.raspberrypi.com/documents/RP-008373-DS-rp2350-datasheet.pdf), [RP2350B QFN-80](https://rp2350b.pinout.xyz/) | **PARTIAL** — package confirmed QFN-80, pitch board-measured |
| 4 oz pattern floor | `evidence/fab-esc-4oz/sources/EC-classification-ENGLISH-5-2024-V3.png` | **CITED (file retained)** |

---

## 3. Task 2 — the engineering cost, measured by execution

I did not estimate this. I applied each edit to a copy, asserted the netlist invariant, and re-ran DRC.

| transaction | board | footprints | pads edited | assertion | DRC result |
|---|---|---|---|---|---|
| **E5** | `kicad/e5` | 8 (6 LQFP + 2 USB-C) | 304 | pad numbers + nets identical ✓ | 523 → **239** |
| **E6** | `kicad/e6` | 14 (+6 headers, drill only) | 350 | identical except drills (intended) ✓ | 523 → **185** |
| **E7** | `kicad/e7` | 21 (+6 DRV8353, +1 TPS3430) | 600 | identical ✓ | **185** (no new) |

### 3.1 Footprint-bound count is derivable, and it landed exactly

| state | total | footprint-bound | what is left |
|---|---|---|---|
| as-built, R1 | 523 | **413** | 371 pad↔pad (9 fp) + 42 PTH annular (8 fp) |
| E5 (LQFP+USB-C pads) | 239 | **141** | LQFP 258 → **0** (exact); USB-C 38 → 24 (the 0.60 mm fingers were not yet touched) |
| E6 (+USB-C fingers, +header drills) | 185 | **87** | **predicted 87 = 75 U201 + 12 HSOP — measured 87** |
| E7 (+DRV8353/TPS3430 pads 0.22/0.24→0.25) | 185 | **87** | unchanged; the sub-0.25 census drops 330 → **80, all on U201** |

The E6 prediction was made from the row-level map *before* the run and the run reproduced it to the
item. That is the validation that makes the 413 map quotable.

### 3.2 The change alters the schematic netlist — yes or no

**NO for all 23 non-U201 footprints.** Each edit changes a pad dimension or a drill on a footprint
that keeps its part, its pad numbers and its nets. Asserted in code, not asserted in prose:
`15_exec_pad_shrink.py` and `18_exec_full_fixable.py` build `(pad_number, net)` maps before and after
and `assert` them equal — output `pad numbers + nets identical: True`.

**YES for U201**, and it is the expensive kind: a new MCU means a new schematic symbol, a new pin
mapping into 48 GPIO nets, a new footprint, and a firmware port. **23/24 footprints are cheap; 1/24
forces a schematic and firmware revision.**

### 3.3 Function preserved in the same package?

| family | same function, same package? |
|---|---|
| STM32G431CBT6 ×6 | **yes** — same part, narrower pads |
| GCT USB4105-16P ×2 | **yes** — same part, narrower pads |
| DRV8353SRTAR ×6 | **yes** — same part, pads widened 0.22→0.25 |
| TPS3430WDRCR | **yes** — same part |
| LM5164DDA ×2 | **yes** — same part, thermal-via pad/drill change |
| PinHeader ×6 | **yes** — same part, drill 0.65→0.60 (0.40 mm pin in a 0.60 mm hole) |
| **RP2354B** | **NO — no equivalent found** |

---

## 4. Task 3 — the rail fix at 4 oz

**Control first** (`21_rail_4oz.py`, `logs/21_rail.log`): the IPC-2221 closed form reproduces both
settled widths —

| check | computed | settled | delta |
|---|---|---|---|
| 60 A / 20 K / k=0.048 / 4 oz | **13.981 mm** | 13.981 | +0.0024 % |
| 60 A / 20 K / k=0.024 / 1.5 oz inner | **96.991 mm** | 96.991 | −0.0000 % |

**Requirement at 59.05 A** (six independent rails — `REV_B_ARCHITECTURE.md:18-19`, `:137`, per-rail
current 59.05 A from the 3·cosφ/(2√2·η) bus factor):

| quantity | 4 oz (0.140) | 1.5 oz inner (0.0525) |
|---|---|---|
| cross-section | **1.9148 mm²** | 4.9812 mm² |
| width, one face | **13.677 mm** | **94.879 mm** |
| width, two 4 oz faces | **6.838 mm each** | — |

### 4.1 BATP: 23.1 A → 59.05 A

**As built:** F.Cu contributes **0 mm in series** (terminals not joined); In1 min-cut 12.5–17.7 mm →
23.1 A / 11.5 A. **FAILS by 2.6×.**

**Why In1 cannot be the answer at 4 oz:** In1 is **1.5 oz**. Widening it from 17.7 mm to 94.879 mm is a
**5.4×** width increase on a 173.95 mm-wide board — not a routing fix, a new layer stack.

**The concrete change:** move the series element to the **4 oz outer** and retain In1 in parallel.

1. **Join the F.Cu components.** Measured on `/M1_BATP` (`22_fcu_reconcile.py`): zone fill 869.17 mm²
   in **2** polygons; **all** F.Cu copper (fill + 90 tracks + 42 pads) = **922.95 mm² in 10
   components**. Joining them is the whole fix; no new net, no new layer.
2. **Keep In1's 16.00 mm** (0.84 mm²) in parallel. Using the prior unit's parallel method
   (0.5-weighted 0.725-power sum, `20_numbers.py:108-113`), the F.Cu width needed is
   **8.56 mm** at 59.05 A (8.75 mm at 60 A, scaled by (59.05/60)^1.3793 = 0.9782).
3. **Check it fits** (derived, not asserted): 8.56 mm × the measured **71.9 mm** max pad-to-pad span =
   **615 mm²** required against **922.95 mm²** of copper already on the net → **1.50× margin.**
   *F.Cu alone* would need 13.677 mm and is **short**: 922.95 / 13.677 = 67.5 mm of full-width path
   against a 71.9 mm span, a **60 mm² deficit**.

**Resulting capacity: 59.05 A (100 %)**, contingent on the join being drawn with an ≥8.56 mm
continuous neck and re-measured. **This is a specification with a proven-fittable geometry, not a
measured pass** — the join has not been drawn, and the standing rule is that a PASS must come from the
rows. Label: **ANALYTICAL, margin 1.50×.**

### 4.2 BATN: 45 barrels → what count

One 0.4 mm barrel at 25 µm plating = π·d·t = **0.03142 mm²**.

| barrels | cross-section | ampacity (k=0.048, 20 K) | % of 1.9148 mm² |
|---|---|---|---|
| **45 (as built)** | 1.4137 mm² | **47.4 A** | 73.8 % |
| 56 (prior tranche) | 1.7593 mm² | 55.5 A | 91.9 % |
| 61 | 1.9164 mm² | 59.1 A | 100.1 % |
| **63** | **1.9792 mm²** | **60.5 A** | **103.4 %** |

**Needed: 63 barrels (+18).** At 61 the margin is 0.08 % — inside the uncertainty of the plating
thickness — so **63** is the answer, and at 63 the **B.Cu plane becomes the limit**: 14.1 mm × 0.14 =
1.974 mm² → **60.4 A (102 %)**.

**Rail verdict: BATP FAIL as built (23.1 A) → 59.05 A only after a re-pour; BATN FAIL as built
(47.4 A) → 60.4 A after +18 barrels.** Neither is executed here.

---

## 5. Task 4 — the four report numbers

### 5.1 Achievable area at 4 oz

**382.71 cm², unchanged.** Copper weight does not change board area, and 23 of the 24 footprint edits
keep the footprint outline or change pads inside it. The placement was already solved at 4 oz phase
widths (6.991 mm per outer face — settled set, `AGENT_BOARD.md`), so the 4 oz branch does not buy or cost
area. The one exception: **if U201 becomes an LQFP-100-class MCU**, the land grows from ~11 × 11 mm
(121 mm²) to ~15.5 × 15.5 mm (240 mm²) → **+119 mm² = +1.19 cm² → 383.90 cm² (+0.31 %)**.

The packaging envelope is unchanged and still dominated by the **mandatory heat spreader**:
**735–911 cm² total** (382.71 board + 352–528 cm² spreader).

### 5.2 Footprint DRC count after

| rules | before | after E6+E7 (measured) | after the vias are re-arrayed (computed) | after U201 changes part |
|---|---|---|---|---|
| R1: 0.25/0.25, PTH ≥0.20 | **413** | **87** (75 U201 + 12 HSOP) | **75** | **0** |
| R2: task, 0.25/0.25, **PTH ≥0.30** | **523** | **197** (75 + 12 + 110) | **75** | **0** |

Total violations, same states: 523 → **185** (R1) and 633 → **295** (R2).

The 110 sub-0.30 mm holes are fixable without touching a neighbour — measured geometry, computed
clearance: the DRV8353 exposed pad is **4.15 mm** square with a 4 × 4 array at 0.90 mm; a 0.30 mm drill
with a 0.20 mm ring needs a **0.70 mm** pad, which gives a 0.20 mm gap at 0.90 pitch (FAIL) but
**0.25 mm gap at 0.95 pitch**, and 3 × 0.95 + 0.70 = **3.55 ≤ 4.15 mm** → it fits inside the pad. The
HSOP (1.30 × 1.91) and WSON10 (1.20) arrays fit at 0.70 mm pads with no pitch change.

### 5.3 Rail verdict after

**BATP: 23.1 A → 59.05 A (100 %) analytically, 1.50× area margin, not drawn. BATN: 47.4 A → 60.4 A
after +18 barrels, not executed. Rail PASSES: NO** — as with the 2 oz branch, the rail is a design
task that neither branch has executed.

### 5.4 Engineering effort in footprints

| | count |
|---|---|
| footprints requiring change | **24** |
| pads inside them | **945** |
| pads actually edited and DRC-verified | **600** in **21** footprints |
| footprints not done | **3** (U201 90 pads; U701/U703 40 pads) + via re-array on 9 |
| edits that keep the part and the netlist | **23 footprints** |
| edits that break the netlist | **1 footprint — U201** |

---

## 6. Task 5 — verdict

**BUILDABLE + CAPABLE at 4 oz: NO.**

- **Not buildable as drawn at 4 oz**: 413 footprint-bound items, of which 371 are one repeated
  0.2000 mm pad gap. **338 of the 523 total are clearable today** and I cleared them.
- **Still not buildable after all the package work, because of U201.** At 0.40 mm pitch a compliant
  pad would be 0.15 mm — narrower than the trace minimum. **No equivalent part exists** for RP2354B at
  a coarser pitch, so the fix is a different MCU, i.e. a netlist and firmware revision.
- **Not capable**: the rail is **23.1 A against 59.05 A**. At 4 oz the answer exists (13.677 mm on one
  face) but it is a re-pour of BATP plus 18 more barrels on BATN, not a footprint edit.
- **Effort, stated plainly: 24 footprints / 945 pads**, of which **21 footprints / 600 pads are done
  and verified**, and **1 footprint (U201) cannot be done at all** without changing the MCU.

**Comparison with the 2 oz branch, same shape:** 2 oz removes the 413 at zero copper cost but makes the
rail worse (0.07 mm vs 0.14 mm). 4 oz keeps the rail achievable in one face but **cannot carry a 0.4 mm
pitch MCU**. The binding constraint is therefore the same in both branches and is **not copper weight
at all — it is the package mix**, and in the 4 oz branch it is exactly one part.

---

## 7. Reconciliation and disclosures (things that would otherwise look like rounding)

1. **`1,217.29 mm² in 14 components` does not reproduce on `/M1_BATP`.** Measured: zone fill
   **869.17 mm² in 2** components; all F.Cu copper **922.95 mm² in 10** components. The 869.17 agrees
   with `AGENT_BOARD.md:610` and 922.95 agrees with its **922.51** to 0.05 %. So two of the three
   figures reconcile and **1,217.29 / 14 must be a different population** (a six-net sum, or a union
   including via pads). I did **not** use it; every rail number above uses the measured per-net values.
2. **413 vs 414 vs 523.** 414 clearance = 371 pad↔pad + 43 copper. 70 annular = 28 via + 42 PTH pad.
   413 = 371 + 42 = the footprint-bound subset. 523 = the whole list. All three are consistent; none is
   a rounding difference. 371 + 43 + 28 + 42 + 16 + 16 + 4 + 3 = 523 ✓.
3. **My own first classifier under-reported by 42** (§1.4). Recorded rather than quietly fixed, because
   it is the same defect class as the five instruments on the board.
4. **`523` is a real count here, not a cap artefact** — the cap is on *unconnected* items (499, proven
   by construction in `fab-esc-reconcile`), not on violations. But violations have their own cap of 399
   for `lib_footprint_issues`, so a large violation count should always be sanity-checked.
5. **E5 left 24 USB-C items while E6 cleared them**, because the USB-C land pattern is **not** one
   pitch: 8 contacts at 0.50 mm (pad 0.30) **and** 8 VBUS/GND fingers at 0.80 mm (pad 0.60). A pure
   0.30→0.25 shrink cannot fix the 0.60 mm pads; both must move. `17_usbc_detail.py` holds the pad-by-pad
   evidence.
6. **The 0.25 mm pad is at the floor, with zero margin.** LQFP and USB-C at pad 0.25 / space 0.25 is
   legal and is what I executed, but it is the tightest legal combination at 0.5 mm pitch and reduces
   joint volume ~17 % against 0.30 mm. That is an **assembly** risk, separate from etchability, and it
   is not analysed here.

---

## 8. Artefacts and reproduction

| file | what |
|---|---|
| `kicad/esc_rev_b.kicad_pcb`, `.kicad_pro`, `.kicad_dru` | byte-identical board copy + the 4 oz rule set |
| `kicad/r2_task/` | the task rule set (PTH 0.30) and its board copy |
| `kicad/r0_2oz/` | the 2 oz control rule set |
| `kicad/e5/`, `kicad/e6/`, `kicad/e7/` | the three executed states |
| `01_drc_4oz.json` … `07_drc_e7_taskrules.json` | every DRC run, JSON |
| `rows_R1.csv`, `rows_R0.csv`, `rows_R2.csv` | **row-level** DRC classification (523/16/633 rows) |
| `summary_*.json` | counts by type, by owner footprint, rule names, footprint-bound split |
| `13_fp_geometry.json` | per-footprint pitch, pad width, gap histogram |
| `14_pad_width_census.json` | the 330 sub-0.25 mm pads, by footprint |
| `21_rail_4oz.json`, `22_fcu_reconcile.json` | rail arithmetic + the two F.Cu populations |
| `logs/` | every run's stdout, including the two instrument-fix notes |

```powershell
$cli="C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"; $py="C:\Program Files\KiCad\9.0\bin\python.exe"
$ev="E:\engineering-portfolio-audit\evidence\esc-branch-4oz"
& $cli pcb drc "$ev\kicad\esc_rev_b.kicad_pcb" -o "$ev\01_drc_4oz.json" --format json --severity-all --units mm
python "$ev\11_map_drc.py"                       # 413 footprint-bound / 371 pad-pad @0.2000
& $py "$ev\18_exec_full_fixable.py" "$ev\kicad\esc_rev_b.kicad_pcb" "$ev\kicad\e6\esc_rev_b.kicad_pcb"
& $cli pcb drc "$ev\kicad\e6\esc_rev_b.kicad_pcb" -o "$ev\05_drc_e6.json" --format json --severity-all --units mm
& $py "$ev\21_rail_4oz.py" "$ev\kicad\esc_rev_b.kicad_pcb"
```

Nothing was written into `repos/`. No commit, push, reset or `audit/*` branch was touched.

---

## 9. What is UNVERIFIED

- **The RP2354B datasheet pitch.** Could not be fetched (cross-origin redirect). The 0.4 mm pitch is
  **board-measured** and is the only value geometrically consistent with 80 pins on a 10 mm body; if a
  datasheet landing pattern for 0.50 mm pitch exists, U201 stops being the blocker and the whole
  verdict flips to "buildable after 23 footprints". **This is the single fact worth closing first.**
- **Whether any fab will quote 4 oz at 0.20 mm space.** If one will, in writing, U201 is a waiver and
  the 413 collapses to the copper edits — the `fab-esc-4oz` §6.2 quote question still stands.
- **The BATP re-pour.** The 8.56 mm neck is a computed requirement with a 1.50× area margin; the
  min-cut after joining has not been measured.
- **The 0.95 mm via re-array** is arithmetic (3·0.95+0.70 = 3.55 ≤ 4.15 mm), not a DRC run.
- **Assembly at 0.25 mm pads** (paste volume, heel fillet at 4 oz thickness) is untouched.
- **Cost.** No quote obtained; the $60 coupon cap is untouched by this item.