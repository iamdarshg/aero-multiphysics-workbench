# dev-board HDI removal — measured, and it does not work

**Verdict: the 201 non-through vias cannot be converted to through vias on this board.**
Not "difficult" — **measured, and both routes fail.** The owner's instinct that this is "a pretty small
issue" is wrong, and this file is the evidence.

Source: `dev-real-production.kicad_pcb` (read-only). Evidence: `D:/devboard-evidence/hdi/`. E: untouched.

---

## Why it is not small

| | |
|---|---|
| microvias | **186** — **size 0.200 / drill 0.100** ×174, **size 0.300 / drill 0.150** ×12 |
| blind + buried | **15** — 0.127 ×7, 0.150 ×8 |
| **annular ring on a microvia** | **0.050 mm** |
| **annular ring a through via needs** | **≥ 0.150 mm** |
| smallest through via the board already uses | **size 0.254 / drill 0.127 → annular 0.0635 mm** |

**A microvia has 0.050 mm of copper. A legal through via needs 0.150 mm.** So every converted via must
grow by **+0.227 mm of copper diameter** (0.127 drill + 0.300 = 0.427 mm minimum). That growth is what
breaks the board.

## Attempt 1 — convert all 201 (the naive fix)

**Result: 10 → 555 violations. +545 new.** Unconnected stayed 0.

| type | before | after | delta |
|---|---|---|---|
| annular_width | 0 | **174** | **+174** |
| clearance | 0 | **151** | **+151** |
| hole_clearance | 0 | **124** | **+124** |
| shorting_items | 0 | **80** | **+80** |
| solder_mask_bridge | 0 | 9 | +9 |
| holes_co_located | 2 | 5 | +3 |
| hole_to_hole | 0 | 2 | +2 |
| lib_footprint_issues | 0 | 4 | +4 |

**80 shorting items** means the enlarged pads **collide with neighbours** — the board would be
electrically broken. This is not a fix.

## Attempt 2 — convert only the 15 blind/buried, keep the micros

**Result: 10 → 48 violations. +38 new,** for 15 vias.

| type | before | after | delta |
|---|---|---|---|
| hole_clearance | 0 | 13 | **+13** |
| solder_mask_bridge | 0 | 9 | **+9** |
| shorting_items | 0 | 6 | **+6** |
| clearance | 0 | 6 | **+6** |
| via_dangling | 0 | 2 | +2 |
| lib_footprint_issues | 0 | 4 | +4 |

**~2.5 new violations per converted via.** Even the easy 15 are not free.

## Where the 186 microvias actually are — not what I assumed

I expected a QFN fanout. **They are spread across 99 grid cells, clustered around the power section:**

| cluster centre | count | nearby parts |
|---|---|---|
| x 65–70, y 55–60 | 6 | **C5** at 0.3 mm, **RPG1** 2.1 mm, C2 3.2 mm |
| x 55–60, y 60–65 | 6 | **CIN2** (1210), COUT2, R1, REN1, CSS1 |
| x 65–70, y 65–70 | 5 | power section |
| x 55–60, y 20–25 | 4 | separate cluster |

**This is power/ground stitching around the MIC28516 buck converter, not a fine-pitch escape.** That
matters: it means the microvias are **deliberate stitching**, and 186 of them are doing real electrical
work — which is exactly why removing them is not a mechanical swap.

## What would actually be required

1. **Re-route the power section** — the 186 stitching microvias sit in the buck converter's current
   loops. Removing them means re-doing that layout, not converting vias.
2. **Grow every via by 0.227 mm** — which needs clearance that does not exist at 0.200/0.100 geometry.
3. **A layer-count change would not help either.** drone-arm went 4→6 layers and reached zero non-through,
   but that worked because its vias were 0.300 mm with adequate annular ring; the extra layers bought
   *routing*, not *pad space*. Here the blocker is **pad diameter vs neighbour spacing**, which no layer
   count changes.

## The honest options

| option | cost | outcome |
|---|---|---|
| **Accept HDI for this board** | fab cost only; it is a **single-span Top→Ground Layer 1** pattern (183 of 201), the cheapest HDI class, and the board has plausibly already been fabbed this way | **recommended** |
| Re-route the power section and convert | days of layout work, and the 0.227 mm growth may be infeasible at this density | uncertain |
| Shrink the design rules | not available — 0.150 mm annular is already the minimum | impossible |

**Recommendation: accept HDI on dev-board.** It is one blind span, laser-drilled at 0.100 mm, on a board
that already exists in fabbed form. Removing it costs a power-section re-layout with no guarantee of
success, and the attempt above shows it makes the board electrically broken rather than better.

## Instrument note (cost me three failed runs)

**`PCB_VIA.GetWidth()` HANGS in KiCad 9** — it blocks indefinitely and never returns. It killed my three
scans *and* the dispatched agent's `s1_census.py`, which is why that unit returned nothing. Use
`GetDrillValue()`, `GetViaType()`, `TopLayer()`, `BottomLayer()`, or parse the `.kicad_pcb` text for
`(size …)`. Never call `GetWidth()` on a via.

**Via type constants (KiCad 9, measured):** `1 = micro`, `2 = blind/buried`, `3 = through`.
`VIATYPE_BLIND` and `VIATYPE_BURIED` do not exist as separate constants.