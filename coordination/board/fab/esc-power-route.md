# ESC POWER — route the remaining 187 connections → **unconnected 0**

**Status: COMPLETE.** The 60 unconnected items the handed-over board still had are now **0 on
both tools** (pcbnew uncapped 0, `kicad-cli` 0), with **0 of the 94 added copper objects appearing in
any DRC violation row** in either rule configuration. 76 tracks and 18 vias were added; **0 objects
were removed or modified**, so no power-path width was reduced.

| field | value |
| --- | --- |
| assignment | route the ESC POWER board to zero unconnected |
| input | `evidence/esc-route-power/boards/p1_routed.kicad_pcb` sha256 `F474B704…4F8D5C` (636,257 B) |
| input unconnected (measured here) | **60** — pcbnew uncapped and my island instrument agree exactly |
| output | `boards/p2_routed.kicad_pcb` sha256 `DFE2FFD1…D927B7` (650,402 B) |
| output unconnected | **0** on both tools |
| host | KiCad 9.0.7, `C:/Program Files/KiCad/9.0/bin/` (+ bundled `python.exe`, `kicad-cli.exe`) |
| router | raster A\* at 0.04 mm; **straight/L-first** with exact shapely validation, A\* only where the straight run is illegal |
| board | 151.87 × 122.65 mm, 4 Cu layers 3/1.5/1.5/3 oz, double-sided, ENIG, 173 fps / 1,581 pads |

---

## 0. What is being handed over, and what the brief's numbers really are

The brief says "this is the remaining 187 connections". The handed-over board is **not** at 187: the
previous pass routed the power path and took it to **60**. Measured here, on the file I was given:

| state | unconnected (pcbnew, uncapped) | unconnected (my island instrument) | kicad-cli list |
| --- | ---: | ---: | ---: |
| `p1_routed` (the input) | **60** | **60** (agrees exactly) | 60 |
| `p0_base` (the pre-route board, also in the prior dir) | **187** | **187** (agrees exactly) | 187 |
| `p2_routed` (this pass) | **0** | **0** (agrees exactly) | **0** |

So both numbers are real, they describe two different boards, and §1 enumerates the 187 (as asked)
while §5–§7 close the 60 that were actually left. I report both rather than substituting one silently.

**Method guard rails that were used, not assumed:**

- `PCB_VIA.GetWidth()` is never called anywhere in these scripts; the 12 pre-existing vias are read
  by text parse of the `.kicad_pcb` (`(via (at …) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu"))`).
- `CONNECTIVITY_DATA.GetUnconnectedCount()` in this build **requires** a `aVisibileOnly` positional
  argument — `GetUnconnectedCount(False)`. Without it the call raises (the first attempt died on it).
- **Rule-load assert.** Two configurations were run for every board, in isolated directories that
  carry the companions:

  | cfg | companions | input | routed |
  |---|---|---:|---:|
  | **A** | `.kicad_pro` only (netclass/min clearance 0.25 mm) | 539 violations, 60 unc | 539, 0 unc |
  | **B** | `.kicad_pro` + the 3 oz `.kicad_dru` (pattern class 0.200 mm) | 159, 60 unc | 159, 0 unc |

  The rules are provably loaded because A and B report **different clearance populations from the
  same board** (499 vs 119). In **A the clearance row count is exactly 499 on both boards** — the
  documented list cap — so A's clearance figure is quoted as *capped (`≥499`)*; B's 119 is below the
  cap and is the honest violation count. The brief's carried "DRC 527 listed = 499 + 28 silk" was
  measured here as **539 = 499 (capped) + 29 silk_over_copper + 8 solder_mask_bridge + 3
  shorting_items**; the extra rows are present in the input *and* the output, so they cannot flatter
  the set diff.

---

## 1. The 187 unconnected, enumerated by net and by cause

Measured on `p1_routed`'s predecessor `p0_base` (uncapped pcbnew 187, island instrument 187 — they
agree set for set). Grouped the way the task asked.

| group | nets | unconnected | what the net physically is | cause |
| --- | ---: | ---: | --- | --- |
| **sense — leg-shunt taps** | 18 (`M1_SNA`…`M6_SNC`) | **126** (7 each) | each net = the 7-pad source row of one low-side FET + the shunt's tap pad: **8 pads, 8 islands** | no copper at all: 7 of the 8 pads are the FET's split source row, which does not connect to itself inside the footprint, and nothing was routed to the shunt tap |
| **header — grounds** | 2 (`DGND`, `AGND`) | **41** (23 + 18) | header pins of `J_H1`/`J_H2` (DGND, 24 pads) and `J_H3` (AGND, 19 pads), 1.70 mm pads on 2.54 mm pitch | every pin is its own island; zero copper on either net |
| **sense — Kelvin** | 1 (`BATN_K`) | **17** | the outboard Kelvin pad of all 18 leg shunts, 9 at y 37.10 and 9 at y 51.40 | zero copper; each Kelvin pad is boxed in 0.30 mm from the shunt's own 5.00 × 1.80 mm force pads above and below, so no track can pass beside it on any layer |
| **power distribution** | 2 (`BATN` 2, `BATP` 1) | **3** | two 2-pad cells at the far left column (x 13.38) cut off from the main BATN net; the two BATP islands split by the BAR2 wall | geometry: the left-most cells are outside the routed BATN plates; BAR2 is an unbroken 113.5 mm wall |
| **gate drive** | 36 (`M#_GAH`/`GAL`…`M#_GCH`/`GCL`) | **0** | — | **not counted as unconnected because each has exactly ONE netted pad** (see §2) |
| **signal** | 131 nets (`CSA_*`, `PWM_*`, `nCS_*`, `SPI_*`, `CAN_*`, `SWD*`, `NTC_*`, `BUS_*`, …) | **0** | — | same: 131 nets with exactly 1 netted pad |
| **total** | | **187** | | |

**Why 36 gate and 131 signal nets can have 0 unconnected items and still be unbuilt:** an
unconnected *item* is a ratsnest edge, and a net with one pad has no edge. The board has
**756 netless pads of 1,581**, including **all 390 pads of the six DRV8353** (65 pads each, 65 of 65
netless on every one — measured, not assumed) and 152 pads of the 19 INA296A2. So the "signal" and
"gate drive" columns are not finished — they are **unroutable from this netlist**, which §2 and §3
quantify.

---

## 2. GATE DRIVE — measured per phase, and why 0 mm of gate etch exists

The task said gate drive first. It was measured first, and the measurement is a negative:

| measurement | result |
| --- | --- |
| DRV8353 in place | 6 (U11–U16) |
| pcbnew pad count of every gate net | **{1 pad: 36 nets}** — 0 of 36 have a second terminal |
| driver pads that hold any net | **0 of 390** |
| gate etch this pass could add | **0.00 mm** |

The loop was therefore measured the only way it exists — as the placement loop, which is exactly the
metric carried in the brief (**loop = 2 × nearest driver pad to the FET gate pad**), recomputed here
from scratch on the delivered board:

| cell | driver | achieved loop mean | worst loop in cell | broken out per phase (worst FET) |
| --- | --- | ---: | ---: | --- |
| M1 | U11 | **54.61 mm** | 80.62 mm | A 46.70 / B 61.23 / C 80.62 |
| M2 | U12 | 137.88 mm | 154.46 mm | A 154.46 / B 150.28 / C 149.73 |
| M3 | U13 | 140.10 mm | **158.58 mm** | A 149.74 / B 152.19 / C 158.58 |
| M4 | U14 | 69.89 mm | 90.24 mm | A 77.13 / B 80.16 / C 90.24 |
| M5 | U15 | 69.65 mm | 89.83 mm | A 77.13 / B 79.95 / C 89.83 |
| M6 | U16 | 65.52 mm | 81.16 mm | A 78.34 / B 77.13 / C 81.16 |
| **global** | | **89.61 mm mean of cell means** | **158.58 mm worst single** | best cell 54.61 mm |

My instrument reproduces the prior placement measurement to **0.1 mm** (89.61 vs 89.6, 54.61 vs
54.6, 158.58 vs 158.6) — an independent check that both measurements are the same quantity.

**Verdict on this step: no gate loop was improved, because no gate loop can be routed.** The gate
drive is not "unrouted"; the driver's pins carry no net, so there is no second terminal to reach. The
fix is a netlist/schematic action (assign the DRV8353 pins), not a routing action, and inventing
copper between a netless pin and a gate pad would be a manufactured pass. Routing added **0.00 mm**
of gate copper and the loop stays at 89.61 mm mean / 158.58 mm worst.

## 3. Front-end amplifier outputs (19) to the header — also unrealizable

Same defect, same reason: the 19 INA296A2 carry 152 netless pads, so all 21 `CSA_*` nets hold
**exactly one netted pad** (the header pin). 0 of 19 amplifier outputs were routed, and 0 of 19 could
be: there is no net joining an amplifier output to its header pin.

## 4. Remaining signals

0 unconnected items were in the signal class for the reason above (131 nets × 1 pad). No signal copper
was added — adding it would have required inventing connectivity.

---

## 5. The routing pass — batch by batch, kept / attempted, running unconnected

Input `boards/p1_in.kicad_pcb` → output `boards/p2_routed.kicad_pcb`. Every candidate geometry is
validated with shapely against **all** foreign copper on its layer at the board's own 0.25 mm
clearance **+0.01 mm numerical margin**, and inside the 0.50 mm edge keep-out, before it is written.
Vias are validated against every copper layer. Nothing was written that did not pass.

| batch | element | attempted | kept | refused | running unconnected (pcbnew, measured after the batch) |
| --- | --- | ---: | ---: | ---: | ---: |
| — | start | — | — | — | **60** |
| B1 | AGND bus, `J_H3` column x 142.91 (19 pins), In1.Cu 0.80 mm | 1 | **1** | 0 | **42** |
| B2 | DGND: two inter-column buses (x 132.00 / x 138.09) + 24 stubs + 1 link, In1.Cu 0.30 mm | 27 | **27** | 0 | **19** |
| B3a | BATN_K: one 0.70/0.30 through via at each Kelvin pad | 18 | **18** | 0 | **19** |
| B3b | BATN_K: In1.Cu sense bus (3 runs at y 39.60 / x 8.00 / y 49.00) + 18 stubs, 0.30 mm | 19 | **19** | 0 | **2** |
| B4 | BATN: the two left-most islands joined to the main net, F.Cu, **4.00 mm** | 2 | **2** | 0 | **0** |
| | **total** | **67** | **67** | **0** | **0** |

*B3a shows no movement (19 → 19) and that is the truth, not a bookkeeping slip: a via dropped in a
pad connects nothing until the bus that reaches it exists, which is B3b. The measurement is taken
after each batch, not derived by subtracting kept counts.*

Copper actually written: **76 tracks + 18 vias** = 1 AGND, 27 DGND, 2 BATN_K F.Cu reach-backs,
21 BATN_K In1, 25 BATN F.Cu, 18 vias (0.30 mm drill).

**Two measurement-driven corrections inside this pass, recorded because they were failures first:**

1. *BATN_K vias at R1C.4 (x 41.78) and R2C.4 (x 84.88) are illegal.* The BATP **B.Cu** crossing lanes
   occupy x 42.10–46.05 and x 85.00–89.00 for y 4.5–83.0; a 0.70 mm through via at the pad centre
   lands 0.03 mm into a lane — a short to BATP. Measured distances: pad centre → lane edge =
   0.32 mm / 0.12 mm against the 0.60 mm a 0.70 via needs. Fix: a short F.Cu reach-back stub and an
   offset via at x 41.48 (0.30 mm) and x 84.38 (0.50 mm). Both are legal, both are in-pad.
2. *The first BATN_K bus was placed at y 38.75 / y 50.00 and hit the J1–J6 barrels*: their 1.70 mm
   pads occupy y 37.39–39.09 and y 49.45–51.15, not the 1.70 mm centres I had assumed. Moved to
   y 39.60 and y 49.00 — measured clearances 0.36 mm and 0.30 mm at 0.25 mm clearance.

---

## 6. DRC — row-level set diff, both rule sets

Keyed by `(type, sorted item uuids)` — a set diff, never a total.

```
cfg B (+ 3 oz .kicad_dru, 0.200 mm floor)  input 159 -> routed 159   GONE 0   ADDED 0
cfg A (.kicad_pro, 0.25 mm floor, CAPPED)  input 539 -> routed 539   GONE 1   ADDED 1  *
```

| type | A in | A out | B in | B out |
| --- | ---: | ---: | ---: | ---: |
| clearance | 499 (**capped**) | 499 (**capped**) | 119 | 119 |
| silk_over_copper | 29 | 29 | 29 | 29 |
| solder_mask_bridge | 8 | 8 | 8 | 8 |
| shorting_items | 3 | 3 | 3 | 3 |
| unconnected_items | 60 | **0** | 60 | **0** |

**\* The single flipped row in cfg A is an artefact of the 499 cap, and it was proved to be one.**
The row is `actual 0.2000 mm` between two **pads of the same footprint** `Q6BL`: its `<no net>` pad at
(112.08, 60.50) against either P9 `M6_PHB` (as the input reports it) or P1 `M6_SNB` (as the routed
board reports it). Both partners are pads that were in the input file; **no added object takes part in
that row or in any other**. Three independent facts pin it down:

1. **0 of the 94 added copper objects appears in any violation row**, in either config (uuid set
   difference then searched against every row: `scripts/10_addedcheck.py`).
2. **cfg B — uncapped at 119 rows — is GONE 0 / ADDED 0**, i.e. the violation *population* did not
   change; only a partner label inside a truncated list did.
3. **The same routing pass was run twice.** Its geometry is identical both times (76 tracks, 18 vias,
   0 unconnected), but object uuids are regenerated on every run, and the two runs of the *identical*
   board gave `GONE 0/ADDED 0` and `GONE 1/ADDED 1` in cfg A. A set diff at the 499 cap therefore
   cannot be read as an exact claim at the row level — which is why the added-object search (fact 1)
   and cfg B are the load-bearing evidence, and cfg A's counts are quoted as capped.
   *(29 of the uuids appearing in rows are silkscreen graphics, not pads/tracks/vias — exactly the 29
   `silk_over_copper` rows; they are not resolvable in a pad/track map.)*

The 159 standing violations in cfg B are inherited — 119 clearance rows, 29 silk, 8 mask bridges, 3
shorts (the BAR2/BATN wall against three `J_H1` pins) — and are **not** cleared by this pass; they are
reported, not hidden.

---

## 7. Verification

| check | result | how |
| --- | --- | --- |
| **unconnected, pcbnew (uncapped)** | **0** | `CONNECTIVITY_DATA.GetUnconnectedCount(False)` after `Build` + `RecalculateRatsnest` |
| **unconnected, kicad-cli** | **0** | `drc.json → unconnected_items`, both cfg A and cfg B (below the 499 cap, so quoted directly) |
| my island instrument | **0**, and it agrees exactly at 60 and at 187 on the other two boards | union-find over pads/tracks/vias per layer, through vias mapped to all copper layers |
| **DRC, added-object search** | **0 of the 94 added objects appears in any violation row**, cfg A and cfg B | uuid set difference vs every row |
| **DRC row-level set diff** | cfg B (uncapped): **GONE 0 / ADDED 0**; cfg A (capped): 1 partner-label flip, proved not to involve added copper (§6) | §6 |
| **copper set diff** | tracks **58 → 134** (gone **0**, added **76**), vias **12 → 30** (gone **0**, added **18**) | multiset diff on `(net, layer, endpoints, width)` |
| **power-path width reduced?** | **NO** — nothing was removed or modified; the only new power-class copper is **2 BATN links at 4.00 mm** | the same multiset diff |
| **phase ampacity still holds** | **yes — 18/18 phases measure 6.00 mm = 26.4 A**, identical to the carried figure | width read back off the routed board, IPC-2221 k = 0.048, 105 µm, ΔT 20 K |
| shunt taps | 4.00 / 4.10 mm = **19.7 / 20.0 A** (9 + 9) | same |
| **BATN** | now uniformly **4.00 mm = 19.7 A** (43 segments, min = max = 4.00) | same |
| BATP | F.Cu 3.00 mm = **16.0 A**; B.Cu 3.95/4.00 mm = 19.5/19.7 A (via-limited 9.0 A) | same |
| **parts on B.Cu** | **J_H1, J_H2, J_H3 only** — before and after | `footprint.IsFlipped()` census |
| degenerate tracks | 0 | every added track length > 0.05 mm |
| new drills | 18 × 0.30 mm (via 0.70 mm, annular 0.20 = the board minimum) | text parse of the saved board |

**What the 60 were, and what closed them:**

| net | was | now | element that closed it |
| --- | ---: | ---: | --- |
| DGND | 23 | **0** | 27 In1.Cu tracks: bus in the `J_H1` inter-column corridor (x 132.00, y 25.08–69.53), bus in the `J_H2` corridor (x 138.09, y 23.81–61.91), a link at y 25.08 through the 0.84 mm row gap, and one stub to each of the 24 pins |
| AGND | 18 | **0** | 1 In1.Cu track, x 142.91, y 21.27–66.99 — every `J_H3` even pin is AGND, so the column itself is the bus |
| BATN_K | 17 | **0** | 18 through vias + 21 In1.Cu tracks: two horizontal sense buses (y 39.60 top, y 49.00 bottom) joined by a vertical at x 8.00, clear of the J1–J6 barrel columns |
| BATN | 2 | **0** | 2 A\* polylines at **4.00 mm** on F.Cu, each 12.50 mm, from the two isolated left-edge cells to the main net |
| **total** | **60** | **0** | |

**Widths this pass added, and their honest ampacity** (IPC-2221, ΔT 20 K, that layer's own k):

| new copper | width | ampacity | note |
| --- | ---: | ---: | --- |
| DGND, In1.Cu (27 runs) | 0.30 mm | **0.9 A per run** | capped by geometry: the 2.54 mm header pitch leaves a 0.84 mm corridor, so no layer can carry more than 0.34 mm there. 24 pins in parallel; this is a header return, not the power return |
| AGND, In1.Cu (1 run) | 0.80 mm | **1.9 A** | 19 pins in parallel |
| BATN_K, In1.Cu (21 runs) | 0.30 mm | 0.9 A per run | Kelvin sense: µA–mA |
| BATN_K reach-backs, F.Cu | 0.25 mm | 2.6 A | 2 of 18 pads |
| BATN links, F.Cu | **4.00 mm** | **19.7 A** | matches the surrounding 4.00 mm BATN plates exactly. The width sweep starts at 4.00 mm — the straight run was illegal, the A\* path at 4.00 mm was legal — so no narrower width was ever needed |

**Manufacturing note (real, not cosmetic):** all 18 `BATN_K` vias sit in their Kelvin pad, and 16 of
them are dead-centre. Via-in-pad at 0.30 mm drill needs plugged/filled vias in production, or the
sense pads will wick solder. The alternative — a dogbone beside the pad — is not available: the
Kelvin pads are boxed by the shunt's own 5.00 × 1.80 mm force pads 0.80 mm above and below and by the
BATP B.Cu lanes for the two right-most cells.

---

## 8. Verdict

**IS THE POWER BOARD ROUTED: YES — 0 unconnected on both tools, no added object in any DRC
violation row, nothing thinned, 3 parts on B.Cu.**

"Routed" means every connection the netlist actually contains is now made. It does **not** mean the
board ships, and the two reasons are design facts, not effort:

1. **The netlist.** 756 of 1,581 pads carry no net, including **all 390 DRV8353 pads**. So **36 gate
   nets and 131 signal nets (including all 19 amplifier outputs to the header) have exactly one
   terminal and cannot be routed by any tool.** Gate drive is at its placement loop of 89.61 mm mean
   / 158.58 mm worst and this pass added 0.00 mm. Closing the budget needs a schematic/netlist fix.
2. **Ampacity.** All 18 phases stay at **6.00 mm = 26.4 A** against **27.72 mm = 80 A** needed
   (33 %); BATN 4.00 mm = 19.7 A; BATP 3.00 mm = 16.0 A on F.Cu (3 % of the 480 A six-phase bus). **No width was
   reduced and no new limit was introduced**, so the speed envelope carried from the 600–650 km/h / 2 km ASL basis is
   unchanged — the board still cannot reach the 80 A/phase design point.

---

## 9. Files and provenance

| file | what it is |
| --- | --- |
| `boards/p1_in.kicad_pcb` | the input, copied, sha256 `F474B704…4F8D5C` |
| `boards/p2_routed.kicad_pcb` | **the delivered board**, sha256 `DFE2FFD1…D927B7` |
| `boards/p2_routed.kicad_pro`, `boards/p2_routed.kicad_dru` | the companions, so the delivered board can be DRC'd in place: the `.kicad_pro` is the sibling project (netclasses), the `.kicad_dru` is the 3 oz / 0.200 mm pattern-class rule set = **cfg B**, the fab-accurate gate. A DRC run there reports **159**, not cfg A's capped 539 |
| `boards/p0_in.kicad_pcb` | the pre-route board (from the prior pass), used only to enumerate the 187 |
| `scripts/router2.py` | exact-validated copper adder: shapely STRtree clearance at 0.25 + 0.01 mm, raster A\* at 0.04 mm, via legality on all layers |
| `scripts/01_census.py` | board census, netless-pad census, `GetUnconnectedCount(False)` |
| `scripts/02_islands.py` | island instrument; **reproduces pcbnew at 187 / 60 / 0** |
| `scripts/04_windows.py` | THT pad bands and the occupancy of the routing windows |
| `scripts/05_route.py` | the pass: batches B1–B4, width sweep, kept/attempted |
| `scripts/06_diag.py` | the named blockers (lane distances, barrel rows) |
| `scripts/07_verify.py` | copper multiset diff, B.Cu census, width + IPC-2221 ampacity |
| `scripts/08_setdiff.py` | DRC row-level set diff by `(type, uuids)` |
| `scripts/09_gateloop.py` | gate loop per FET / phase / cell, and the 1-pad proof |
| `scripts/10_addedcheck.py` | uuid set difference of the two boards, searched against every DRC row |
| `drc/a_p0,a_p1,a_p2` + `drc/b_p0,b_p1,b_p2` | six DRC runs (3 boards × 2 rule configs), each in a directory holding the board's companions |
| `rows/census_*.json`, `rows/islands_*.json`, `rows/route_p2.json`, `rows/verify_p2.json`, `rows/gateloop.json`, `rows/drc_*.json` | every number above, machine-readable |
| `logs/*.log` | raw run logs |

All work was done on copies under `boards/` and `drc/`; the input files were never written. Nothing
was committed to, or written into, any repository. Free space at close: 141.72 GB on the evidence
volume.