# fab-da-route-35 — route drone-arm's 35 remaining unconnected connections

**Task (single):** route the 35 remaining unconnected connections on the zero-HDI drone-arm board
(`F2.kicad_pcb` from `fab-da-last-via`). Everything else is done: 0 non-through vias, 328 through,
min drill 0.200, DRC 58 with set diff `+{}` / `-{clearance 1, track_dangling 1}`, RF void
4.1699 mm2 / 9.8338 pct. Do **not** trade the zero-HDI property for fewer unconnected.

**Input:** `evidence/fab-da-last-via/work/F2.kicad_pcb` → copied to `work/in.kicad_pcb`
(sha256 `CFCF122BBF81B9D9D31978A92D85FCAD5FEEB9AAC7E3E0F27FD5434908E6F03E`, **byte-identical to the
input**) with `in.kicad_pro` (the project's own rules) and `no_hdi.kicad_dru` (the PTH-only gate: any via
drill < 0.20 mm is a violation). All work is on copies inside this evidence directory; nothing is written
into a repo, nothing is committed.

Baseline to hold (re-measured here, not quoted — §1):

| quantity | must stay |
|---|---|
| non-through vias (by span, both tools) | **0** |
| min drill | **>= 0.200** |
| RF void | **4.1699 mm2 / 9.8338 pct**, bit-identical |
| DRC set diff vs input | `+{}`; nothing new |
| pads / pad gap census | 657 pads, sha unchanged |

**Status: DONE — 35 → 15 unconnected, 0 non-through, DRC set diff `+{}`, nothing else regressed.**
The exact residual and the reason for each of the 15 is in §5.

## 1. Baseline reproduced (step 0)

Every row below is measured **here**, on the copy `work/in.kicad_pcb`, with the project's own
`.kicad_pro` beside it (`work/in.kicad_pro`) and `no_hdi.kicad_dru` for the gate run.

| check | measured | instrument |
|---|---|---|
| copper layers | F, In1, In2, In3, In4, B (6) | `s0_dump.py` (pcbnew) |
| vias / **non-through** | **328 / 0** | `s0_dump.py` — `nontrough_by_pair {}` |
| drill counts | `{0.2: 5, 0.3: 48, 0.35: 275}`, **min drill 0.200**, 0 below 0.2 | same |
| **DRC, own rules** | **58 = track_dangling 50 · via_diameter 5 · via_dangling 3**, 0 clearance | `kicad-cli pcb drc --format json --severity-all --units mm` → `drc/w0_in_own.json` |
| DRC, `no_hdi` gate | **58 — identical** (no sub-0.20 drill exists to catch) | `drc/w0_in_gate.json` |
| **unconnected** | **35 on kicad-cli and 35 on pcbnew** (499 cap not in play) | DRC json + `GetUnconnectedCount(False)` |
| pads / pad identity | **657 pads, sha256 `fad11a71c92532d9`** | `s9_verify.py` |
| pad-to-pad gap census | 671 pad pairs tested; gaps `<0.20/0.25/0.30 mm = 145/219/309` (U10 field 40/84/84) | same |
| RF void | **4.1699 mm2 / 9.8338 pct** (A) · 3.8754 / 9.1392 (B) | `void/s5_void.py` |

**Instrument fault caught and fixed (this is the one that mattered).** `work/cur.kicad_pcb` had no
sibling `.kicad_pro`, so `pcbnew` reported the *built-in defaults* — `min_clearance 0.0` instead of
0.125 — and every clearance argument in the router silently used zero clearance. Four batches were
produced that way and all of them were rejected by DRC (356–388 `clearance` violations, all involving
new copper). `work/cur.kicad_pro` is now always placed beside the working copy and `s3_route.py`
**fails closed** (`assert abs(min_clearance - 0.125) < 1e-9`) if the rules did not load. The same
fault is what the input report §1 recorded for `R130.kicad_pcb`; it bit again because the working
copy is renamed.

**On the "371 pad-to-pad gaps"** carried in the task brief: it does not reproduce with the census
used here (671 pad pairs tested; `<0.30 mm` = 309, `<0.35 mm` = 358, `<0.40 mm` = 413 — no threshold
gives 371), so the pad geometry is verified the stronger way instead: **sha256 over every pad's
ref/pad/x/y/size/rotation/copper outline is bit-identical** (`fad11a71c92532d9`), which subsumes any
gap census.

## 2. The 35 unconnected connections, enumerated (step 1)

Read from `drc/w0_in_own.json` `unconnected_items` (KiCad's own ratsnest, 35 entries) resolved by
uuid into item geometry, then grouped with an island model built from KiCad's own copper polygons
(`s1_enum.py`). **Instrument control: the island model reproduces KiCad exactly — 25/25 nets have
`islands - 1 == ratsnest pairs`, `sum(islands-1) = 35 == GetUnconnectedCount`.**

`gap` = nearest approach between the two islands on a shared layer; `items A/B` = how many copper
objects each island holds (a 1 means that pad/track is alone); `-` means the halves share **no**
layer at all, so only a via can join them.

| # | net | from | to | layer | gap mm | items A/B | why it is unrouted |
|---:|---|---|---|---|---:|---|---|
| 0 | `/1V1` | C41.1 | C40.1 | F.Cu | 2.440 | 2 / 1 | bare pad - every track on it was deleted |
| 1 | `/1V1` | trk F 1.22 | C40.1 | F.Cu | 1.375 | 50 / 1 | bare pad - every track on it was deleted |
| 2 | `/3V3` | U10.5 | trk F 0.87 | F.Cu | 3.046 | 1 / 219 | bare U10 pad - its fanout microvia was removed |
| 3 | `/3V3` | U10.24 | trk F 0.60 | F.Cu | 1.609 | 1 / 219 | bare U10 pad - its fanout microvia was removed |
| 4 | `/3V3` | C33.1 | trk F 1.12 | F.Cu | 0.845 | 12 / 219 | dangling stub - the corridor between the stub and its trunk was deleted |
| 5 | `/3V3_ADC` | trk In2 3.15 | trk F 0.04 | F.Cu | 9.737 | 11 / 10 | dangling stub - the corridor between the stub and its trunk was deleted |
| 6 | `/BARO_DRDY` | trk In1 0.61 | trk In1 20.25 | In1.Cu | 17.002 | 8 / 5 | dangling stub - the corridor between the stub and its trunk was deleted |
| 7 | `/BARO_SDA` | trk F 1.58 | trk In1 1.20 | F.Cu | 3.138 | 2 / 16 | corridor deleted - the connecting run is gone, a new path is needed |
| 8 | `/CAN_MOSI` | trk In1 0.78 | trk In1 12.33 | In1.Cu | 16.816 | 9 / 5 | corridor deleted - the connecting run is gone, a new path is needed |
| 9 | `/GNSS_PPS` | trk B 21.66 | U10.13 | F.Cu | 22.542 | 7 / 1 | bare U10 pad - its fanout microvia was removed |
| 10 | `/GNSS_RESET_N` | trk B 10.59 | trk F 0.73 | F.Cu | 12.328 | 13 / 3 | corridor deleted - the connecting run is gone, a new path is needed |
| 11 | `/GNSS_RX` | trk In1 0.07 | trk In1 1.10 | In1.Cu | 0.910 | 22 / 10 | dangling stub - the corridor between the stub and its trunk was deleted |
| 12 | `/HGM` | via@57.58,55.65 | trk In1 0.14 | In1.Cu | 0.151 | 9 / 61 | dangling stub - the corridor between the stub and its trunk was deleted |
| 13 | `/ICM_nCS` | trk B 0.44 | trk F 0.15 | B.Cu | 7.314 | 12 / 4 | dangling stub - the corridor between the stub and its trunk was deleted |
| 14 | `/LNA_EN` | trk In2 1.70 | trk In2 1.40 | In2.Cu | 1.013 | 39 / 10 | dangling stub - the corridor between the stub and its trunk was deleted |
| 15 | `/LSM_INT2` | trk In1 0.16 | trk In1 6.24 | In1.Cu | 27.180 | 2 / 6 | dangling stub - the corridor between the stub and its trunk was deleted |
| 16 | `/LSM_INT2` | trk In1 1.57 | trk F 0.13 | - | - | 2 / 3 | layer split - the two halves have no common layer, needs a via |
| 17 | `/LSM_nCS` | trk In1 0.47 | trk In1 6.03 | In1.Cu | 25.515 | 10 / 9 | corridor deleted - the connecting run is gone, a new path is needed |
| 18 | `/RF_GPIO0` | trk In2 2.14 | trk F 1.03 | F.Cu | 0.960 | 6 / 3 | dangling stub - the corridor between the stub and its trunk was deleted |
| 19 | `/RF_GPIO0` | via@56.48,55.77 | trk In2 1.56 | B.Cu | 3.624 | 6 / 10 | dangling stub - the corridor between the stub and its trunk was deleted |
| 20 | `/RF_GPIO2` | via@55.58,55.70 | trk In2 1.56 | In2.Cu | 0.616 | 7 / 23 | dangling stub - the corridor between the stub and its trunk was deleted |
| 21 | `/RF_GPIO2` | trk B 0.14 | trk B 0.10 | B.Cu | 2.500 | 23 / 73 | dangling stub - the corridor between the stub and its trunk was deleted |
| 22 | `/RF_GPIO3` | trk F 0.89 | U10.23 | F.Cu | 1.128 | 13 / 1 | bare U10 pad - its fanout microvia was removed |
| 23 | `/RF_MISO` | trk In2 0.30 | trk In2 0.05 | In2.Cu | 0.446 | 67 / 97 | dangling stub - the corridor between the stub and its trunk was deleted |
| 24 | `/RF_MOSI` | trk F 0.06 | U10.17 | F.Cu | 0.950 | 1 / 1 | bare U10 pad - its fanout microvia was removed |
| 25 | `/RF_MOSI` | trk F 0.06 | trk B 0.06 | - | - | 1 / 2 | layer split - the two halves have no common layer, needs a via |
| 26 | `/RF_MOSI` | trk B 0.85 | trk B 1.40 | B.Cu | 3.720 | 2 / 45 | dangling stub - the corridor between the stub and its trunk was deleted |
| 27 | `/RF_SCLK` | U10.16 | trk In2 0.05 | F.Cu | 37.756 | 1 / 18 | bare U10 pad - its fanout microvia was removed |
| 28 | `/RF_nCS` | U10.19 | trk In2 13.15 | F.Cu | 33.233 | 1 / 10 | bare U10 pad - its fanout microvia was removed |
| 29 | `/RP2354B MCU/SWDIO` | trk F 0.39 | trk In1 0.52 | In1.Cu | 22.654 | 6 / 7 | dangling stub - the corridor between the stub and its trunk was deleted |
| 30 | `/RP2354B MCU/XIN` | trk In1 1.56 | trk In1 1.11 | In1.Cu | 1.896 | 14 / 9 | dangling stub - the corridor between the stub and its trunk was deleted |
| 31 | `/RP2354B MCU/XIN` | trk In1 0.71 | U10.30 | - | - | 14 / 1 | layer split - the two halves have no common layer, needs a via |
| 32 | `/RP2354B MCU/XIN` | trk In2 0.91 | trk In1 0.71 | In1.Cu | 9.896 | 8 / 14 | dangling stub - the corridor between the stub and its trunk was deleted |
| 33 | `/SENS_MOSI` | trk In1 3.78 | trk In1 0.47 | In1.Cu | 26.550 | 11 / 7 | corridor deleted - the connecting run is gone, a new path is needed |
| 34 | `/SENS_SCLK` | trk In1 0.37 | trk B 0.11 | In1.Cu | 6.186 | 13 / 70 | dangling stub - the corridor between the stub and its trunk was deleted |

**Shape of the problem.** 25 nets, no net with more than 3 pairs, and 35 = sum(islands-1), so the board
is 25 independent broken nets rather than one broken region:

| cause | count | what it means |
|---|---:|---|
| dangling stub, corridor deleted | 18 | one end is a 0.05-0.6 mm stub; the run that joined it to its trunk was deleted |
| bare U10 pad, fanout microvia removed | 7 | U10 is a QFN-80, 0.4 mm pitch, 0.2 x 0.8 mm pads; the pad has **no copper at all** |
| corridor deleted | 5 | both ends are real copper, 3-27 mm apart, nothing joins them |
| layer split (needs a via) | 3 | the two halves are geometrically coincident but on different layers |

Three location clusters: **the U10 QFN field** (7 bare pads + pairs 20/24/25/30/31/32 whose nearest
approach is inside the 11 mm package footprint), **the RF cluster** at x 55-60 / y 53-58 (pairs 11,
12, 18, 19, 20, 21, 23, 24, 26), and **long-haul In1/B.Cu runs** (5-27 mm, pairs 6, 8, 9, 10, 15, 17,
29, 33).

**Why U10 is the hard edge.** The 0.4 mm pitch leaves 0.2 mm between pad edges. A 0.20 mm track with
the project's 0.125 mm clearance needs 0.45 mm of lane, so no track can pass *between* pads; the only
legal exit is along a pad's own axis, where the neighbours are 0.4 mm away. U10's fanout was built for
the 0.100 mm microvias that the zero-HDI conversion removed, and a 0.600/0.300 through via needs a
0.425 mm exclusion radius, which the 0.4 mm pitch cannot supply. That is the structural reason the
seven bare pads are the residual, measured below rather than assumed.

## 3. Routing: attempt log, DRC-gated batches (steps 2-3)

**Method.** `freerouting` was not relied on (see §3.3), so the routing is a purpose-built raster
A* (`router.py`): KiCad's own copper is rasterised at 0.04 mm, the *foreign* copper of the net being
routed is dilated by `0.125 + w/2 + 0.012`, and the search runs over `(layer, i, j)` with 8-neighbour
moves plus via transitions (through 0.6/0.3 only). Own-net copper is free space (a track inside own
copper moves no boundary); **pours are free space too, because the zone filler recedes them around new
copper on refill** — that is why every batch ends with a `ZONE_FILLER` pass. Every proposed path is
then re-checked with **exact shapely geometry** at 0.125 mm clearance, hole-to-hole 0.2 mm and
copper-edge 0.5 mm before a single object is added, and the net's island count is re-measured after
the edit — a route that does not actually merge is removed again.

**Five batches, four rejected.** The DRC gate is what killed each one, which is the point of gating.

| batch | attempted | kept | unconnected after | DRC on the result | verdict |
|---|---:|---:|---:|---|---|
| 1 `route_log` | 35 | 30 | **9** | **407 = clearance 283 · shorting 88 · crossing 10 · dangling 21 · via_diameter 5** | **REJECTED** |
| 3 `route_log3` | 35 | 29 | 8 | **388 = clearance 356 · dangling 27 · via_diameter 5** | **REJECTED** |
| 4 `route_log4` | 40 | 17 | 18 | 45 = dangling 40 · via_diameter 5, set diff **+1 dangling** | **REJECTED** |
| 5 `route_log5` | 40 | 19 | 16 | 43, set diff **+1 dangling** | kept after tidy |
| **5 + tidy + /GND repair** | 40 | **19** | **15** | **42 = dangling 37 · via_diameter 5, set diff `+{}` / −16** | **DELIVERED** |

The three failures are worth recording because each was a real instrument fault, not bad luck:

1. **Batches 1–3 used clearance 0.** The working copy was named `cur.kicad_pcb` and had no sibling
   `cur.kicad_pro`, so `pcbnew` loaded the built-in defaults (`min_clearance 0.0`). The router therefore
   aimed at 0.012 mm instead of 0.137 mm and every route was ~0.125 mm too close. `s3_route.py` now
   asserts the rules loaded and refuses to run otherwise.
2. **Batches 1–3 had a stale raster**: copper added by one route was invisible to the next, so routes
   ran over each other (88 `shorting_items`). `Raster.add_geom()` now updates the raster as copper is
   added, and the window carries a 1.5 mm halo so no cell is scored against a crop edge.
3. **Batch 4 had one dangling end** where a route finished one grid cell inside the target's round cap.
   Fixed by snapping each polyline end onto an existing copper **anchor** of the island (0.18 mm
   tolerance) and by `s5_tidy.py`, which removes *only newly added* micro-stubs (≤0.15 mm) that have
   one end on copper and the other on nothing. It removed 12; unconnected did not change.

**What batch 5 routed, net by net** (19 connections over 40 attempts):

| net | gap routed | segs / vias | net | gap routed | segs / vias |
|---|---:|---|---|---:|---|
| `/RF_MOSI` (F↔B) | 0.000 | 14 / 1 | `/RF_GPIO0` | 3.624 | 8 / 0 |
| `/HGM` | 0.151 | 1 / 0 | `/RF_MOSI` | 3.720 | 44 / 1 |
| `/RF_MISO` | 0.446 | 19 / 0 | `/SENS_SCLK` | 6.186 | 17 / 0 |
| `/RF_GPIO2` | 0.616 | 6 / 0 | `/ICM_nCS` | 7.314 | 35 / 0 |
| `/GNSS_RX` | 0.910 | 15 / 0 | `/RP2354B MCU/XIN` | 9.896 | 49 / 1 |
| `/LNA_EN` | 1.012 | 8 / 1 | `/BARO_DRDY` | 17.002 | 48 / 1 |
| `/1V1` | 1.375 | 40 / 2 | `/RP2354B MCU/SWDIO` | 22.654 | 27 / 0 |
| `/RP2354B MCU/XIN` | 1.895 | 22 / 0 | `/LSM_nCS` | 25.515 | 62 / 1 |
| `/RF_GPIO2` | 2.500 | 17 / 0 | `/SENS_MOSI` | 26.550 | 86 / 1 |
| `/BARO_SDA` | 3.138 | 14 / 0 | | | |

Per net, before → after: **13 nets fully cleared** (`/1V1`, `/BARO_DRDY`, `/BARO_SDA`, `/GNSS_RX`,
`/HGM`, `/ICM_nCS`, `/LNA_EN`, `/LSM_nCS`, `/RF_GPIO2`, `/RF_MISO`, `/RP2354B MCU/SWDIO`,
`/SENS_MOSI`, `/SENS_SCLK`), **3 partly** (`/RF_GPIO0` 2→1, `/RF_MOSI` 3→1, `/RP2354B MCU/XIN` 3→1),
**9 untouched**. TOTAL **35 → 15, i.e. −20 pairs**.

### 3.1 The one defect this wave created, and how it was closed

The 19 routes made the F.Cu `/GND` pour recede and **severed one pour island** (12.115 mm², F.Cu only)
from the main ground body — it appeared as a new `Zone <> Zone` unconnected pair. It could not be
stitched with a single via (measured: the island does not overlap the main body on *any* other layer,
because the long In3/In4 runs receded those pours too), and it could not be bridged at the neck
(measured: the 0.751 mm gap at (51.395,57.962)–(50.645,57.962) is occupied by a pre-existing
`/3V3_ADC` track). It was therefore **routed back** with the same instrument: 9 segments and 2 vias of
`/GND` (`s11_gnd_route.py`), after which the GND net is **one component** again and unconnected went
16 → 15. No foreign net was touched.

### 3.2 Instrument control: refill alone changes nothing

Reloading the input board and running `ZONE_FILLER` without adding any copper (`work/ctl_refill.kicad_pcb`,
`drc/ctl_refill.json`) gives **the same 58 violations and the same 35 unconnected** — so the pour
re-flow is not what moves the numbers; the added copper is.

### 3.3 freerouting, with a longer bounded budget

`freerouting-cli` 2.5.0 is on this host (`evidence/esc-routability/tools/fr/freerouting-cli.exe`,
16 cores / 19 GB reported). The delivered board was exported to Specctra (`fr/deliver.dsn`, 407 KB,
`pcbnew.ExportSpecctraDSN`) and freerouting was launched on it with no pass limit and a **stated wall
of 600 s**; the outcome is recorded in §3.4 verbatim from the run, not predicted. The earlier
observation that a 20-minute wall produced no `.ses` is why the scripting path was built first and
freerouting was run as a comparison, not as the primary.

### 3.4 freerouting result

**No session file. Stated wall: 436 s (limit 600 s), CPU consumed 8.4 s — it was idle, not routing.**
`freerouting-cli` v2.5.0 loaded `fr/deliver.dsn` (6 layers, 176 nets), printed its design warnings,
and then sat at ~2 % CPU until it was stopped; `deliver.ses` was never written. That reproduces the
earlier "20-minute wall, no `.ses`" observation, so the failure is not a budget problem.

The run also produced a **measurement disagreement that disqualifies its numbers for this board**:

* its own log records `Set DEFAULT clearance (all layers): 1250 (0.03125 mm) from DSN value 125.0` and
  `default trace width: DSN=250.0 → board=2500 (0.0625 mm)` — i.e. it scales the DSN's rules by 4, so
  its clearance model is **not** this project's 0.125 mm;
* it then reports **116 pre-existing clearance violations**, while the board's own DRC
  (`drc/del_own.json`) reports **0**. I checked the worst case it names — `FixedVia#4886` (net
  `/SENS_SCLK`, a **pre-existing** via at (55.560, 53.428)) against `/RP2354B MCU/MAIN_LED_A` on
  In1.Cu — with exact geometry: **0.1244 mm** against a 0.125 mm rule, a **0.6 µm** shortfall. That is
  a rounding-boundary case, not a clearance failure, and KiCad's own integer-nm DRC is the authority
  on this board.

So freerouting contributed **no routing** here, and its violation count is not quoted as a finding.

## 4. Final verification (step 4)

`work/deliver.kicad_pcb` — every row measured here, nothing estimated, on the copy with the project's
own `.kicad_pro` beside it.

| check | input | **delivered** | required | verdict |
|---|---|---|---|---|
| copper layers | 6 | **6** | 6 | ok |
| vias total | 328 | **339** (11 added: 9 route + 2 `/GND`) | — | — |
| **non-through by span** | 0 `{}` | **0 `{}`**, 339 through | **0** | **PASS** |
| drill counts | `{0.2:5, 0.3:48, 0.35:275}` | **`{0.2:5, 0.3:59, 0.35:275}`** | ≥0.6/≥0.3 vias | ok |
| **min drill** | 0.200 | **0.200** | ≥0.200 | **PASS** |
| tracks | 2451 | 2980 (+529) | — | — |
| **DRC, own rules** | 58 = dangling 50 · via_diameter 5 · via_dangling 3 | **42 = dangling 37 · via_diameter 5** | nothing new | **PASS** |
| **DRC set diff vs input** | — | **`+{}` / −{track_dangling 13, via_dangling 3}`** | `+{}` | **PASS** |
| DRC, `no_hdi` gate | 58 | **42 — identical to own rules** | — | **PASS** |
| `clearance` / `shorting` / `crossing` / `hole_clearance` | 0 / 0 / 0 / 0 | **0 / 0 / 0 / 0** | 0 | **PASS** |
| **unconnected, `pcbnew`** | 35 | **15** | 0 | **FAIL (partial)** |
| **unconnected, `kicad-cli`** | 35 | **15** (own and gate rulesets) | 0 | agrees |
| **RF void A / B** | 4.1699 mm² / 9.8338 % · 3.8754 / 9.1392 | **4.1699 / 9.8338 · 3.8754 / 9.1392 — bit-identical** | unchanged | **PASS** |
| pads / pad identity | 657, sha `fad11a71c92532d9` | **657, sha `fad11a71c92532d9` — bit-identical** | untouched | **PASS** |
| pad gap census | `<0.20/0.25/0.30 mm = 145/219/309` (U10 40/84/84) | **145/219/309 (U10 40/84/84) — identical** | untouched | **PASS** |
| board area | 14 000.0000 mm² | 14 000.0000 (outline untouched) | — | ok |

**U10's pad rows are untouched** by construction: the pad hash covers every pad's reference, number,
position, size, rotation and copper outline, and it is identical. No pad was moved, added or removed;
the case the routing never got through is the QFN escape *around* those pads, not the pads themselves.

## 5. Verdict (step 6)

**0 unconnected is NOT reached: the exact residual is 15, and each one is named below.** The board is
otherwise strictly better than the input and nothing regressed:

* **0 non-through vias** (339/339 through), **min drill 0.200** — the zero-HDI property is intact;
* **DRC set diff `+{}`** — 42 violations, all inherited (37 `track_dangling`, 5 `via_diameter`), and
  16 inherited violations are *gone* (13 dangling, 3 via_dangling);
* **RF void bit-identical** (4.1699 mm² / 9.8338 %), **pad geometry bit-identical**, gap census identical;
* **unconnected 35 → 15 (−20)**, agreed by both tools and both rulesets.

### 5.1 The residual 15, by cause

| # | net | pair | layer | gap mm | why it is still open |
|---:|---|---|---|---:|---|
| 1 | `/3V3` | U10.5 ↔ trk | F.Cu | 3.046 | **bare U10 pad** — no legal exit (see below) |
| 2 | `/3V3` | U10.24 ↔ trk | F.Cu | 1.609 | bare U10 pad |
| 3 | `/3V3` | trk ↔ trk (C33.1 island) | F.Cu | 0.845 | A* found no path in a ±10 mm window (900 k expansions, 6 layers, vias allowed) |
| 4 | `/3V3_ADC` | trk ↔ trk | F.Cu | 9.737 | same: 2.5 s and 60 s variants both exhausted, no path |
| 5 | `/CAN_MOSI` | trk ↔ trk | In1.Cu | 16.816 | same: no path across 17 mm within the window; every corridor is at the 0.125 mm limit |
| 6 | `/GNSS_PPS` | trk ↔ **U10.13** | F.Cu | 22.542 | bare U10 pad |
| 7 | `/GNSS_RESET_N` | trk ↔ trk | F.Cu | 12.328 | no path (B.Cu trunk to an F.Cu stub, 12.3 mm, both windows exhausted) |
| 8 | `/LSM_INT2` | trk ↔ trk | In1.Cu | 27.180 | no path across 27 mm |
| 9 | `/LSM_INT2` | trk ↔ trk | In1/F | 1.719 | **layer split**: needs a via, and the only via sites near it are inside U10's 0.4 mm field |
| 10 | `/RF_GPIO0` | trk ↔ trk | F.Cu | 0.960 | no path: the corridor is blocked by `/RF_GPIO2` at the 0.125 mm limit |
| 11 | `/RF_GPIO3` | trk ↔ **U10.23** | F.Cu | 1.128 | bare U10 pad |
| 12 | `/RF_MOSI` | trk ↔ **U10.17** | F.Cu | 0.830 | bare U10 pad |
| 13 | `/RF_SCLK` | **U10.16** ↔ trk | F.Cu | 37.756 | bare U10 pad |
| 14 | `/RF_nCS` | **U10.19** ↔ trk | F.Cu | 33.233 | bare U10 pad |
| 15 | `/RP2354B MCU/XIN` | trk ↔ **U10.30** | F.Cu | 5.511 | bare U10 pad |

**8 of the 15 are the U10 QFN-80 escape, and that is a hard rule limit, not a search failure:** pads
are 0.2 x 0.8 mm on a 0.4 mm pitch, so adjacent pad edges are 0.2 mm apart. A 0.20 mm track with
0.125 mm clearance needs 0.45 mm of lane between pads; a 0.600/0.300 through via needs a 0.425 mm
exclusion radius, and 0.4 mm pitch cannot supply it. U10's fanout was built around 0.100 mm microvias
that the zero-HDI conversion removed. Nothing that is legal under this project's rules can reach those
pads, which is exactly the trade the previous wave recorded and this wave did not reverse.

**The other 7** are corridors the A* could not open inside a bounded window (2–10 mm pad, up to
900 k expansions × 6 layers, vias allowed, exact verification): each attempt was made at least four
times with different windows/corridors. That is evidence the corridor is blocked in that window; it is
not a proof of impossibility over the whole board, and it is not claimed as one.

**What 0/0 would need** (unchanged from the previous wave, now measured on 15 pairs instead of 35):
an HDI build (the U10 fanout vias), a U10 re-escape, or board-level re-work of the corridors listed in
§3.1 of `fab-da-last-via`. The zero-HDI property was **not** traded away to buy any of these.

### 5.2 Artefacts

| file | note |
|---|---|
| `work/deliver.kicad_pcb` | **delivered board**: 15 unconnected, 0 non-through, min drill 0.200, DRC 42 with set diff `+{}` |
| `work/in.kicad_pcb` | input copy (byte-identical to `fab-da-last-via/work/F2.kicad_pcb`) |
| `drc/w0_in_own.json`, `drc/w0_in_gate.json` | baseline DRC, both rulesets |
| `drc/del_own.json`, `drc/del_gate.json` | delivered DRC, both rulesets (identical) |
| `drc/ctl_refill.json` | control: refill alone, 58 / 35 — the pours do not move the numbers |
| `drc/b1_own.json`, `drc/b3_own.json`, `drc/b4_own.json`, `drc/b5_own.json` | the four rejected batches |
| `work/table.md`, `work/table.json` | §2 enumeration, machine-generated |
| `work/route_log5.json` | every attempt of the delivered batch: window, expansions, segments, vias, why |
| `work/residual.json` | the 15, machine-generated |
| `work/inv_in.json`, `work/inv_del.json`, `work/ver_in.json`, `work/ver_del.json` | inventories + census |
| `void/void_measure.json` | RF void, input vs delivered |
| `work/ctl_refill.kicad_pcb` | refill-only control board |
| `fr/deliver.dsn`, `fr/fr_stdout.log` | the Specctra export and freerouting's own log (§3.4) |

Scripts: `s1_enum.py` (enumeration + island control) · `s2_report.py` (island composition) ·
`s3_route.py` + `router.py` (raster A*, exact verify, DRC-gated application) · `s4_table.py` (§2 table) ·
`s5_tidy.py` (new-copper micro-stubs) · `s8_gndsplit.py` (finds the severed pour) ·
`s11_gnd_route.py` (routes it back) · `s0_dump.py` / `s9_verify.py` / `void/s5_void.py` (census, pads, void).

**Provenance.** All numbers are measured here with `pcbnew` (KiCad 9.0.7 bundled python) and
`kicad-cli pcb drc --format json --severity-all --units mm`, on copies, in this evidence directory.
The two inherited claims that did not reproduce are reported as such: the "371 pad-to-pad gaps"
(no threshold gives 371; 671 pairs tested, 309 below 0.30 mm) and the freerouting time-box (§3.4).