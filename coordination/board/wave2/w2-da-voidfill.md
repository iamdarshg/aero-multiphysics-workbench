# Wave-2 · drone-arm · In1 /3V3 void-fill for the RF impedance defect

**Item:** design the void-fill that fixes the RF impedance.
**Board:** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb` (2,252,603 B, 62,836 lines), branch `work/2026-11-11`.
**Evidence dir:** `evidence/w2-da-voidfill/` (all scripts + outputs below; nothing written outside it).
**Tools:** KiCad 9.0.7 `C:/Program Files/KiCad/9.0/bin/python.exe` → `pcbnew` (verified `pcbnew.Version()` = 9.0.7).
**Git:** read-only; no commit/push/reset, no `audit/*` touched.

Every number below is produced by a script in this directory or cites a wave-1 file. Wave-1 numbers are
cited as wave-1, never restated as mine.

---

## 0. TL;DR

| quantity | value | source |
|---|---|---|
| void polygons under the 16 RF_50R F.Cu traces | **20** | `06_void_polys.json` |
| total void area | **4.170 mm²** | `06_void_polys.json` |
| void as % of RF trace footprint | **9.834 %** (F.Cu) / **10.96 %** incl. 2 In2 segments | `12_measure.json` |
| wave-1 reference figure | 11.14 % (cited) | wave-1 |
| root cause, all 20 voids | **clearance** | `08_cause.json` |
| dominant blocker | In1 routing of `/915 MHz RF/VDD_CC112` | `08_cause.json`, corroborated by wave-1 `da-stackup/rf_reference_cleanliness.json` |
| minimal fix | move **13** In1 signal segments off In1 | `15_movetracks.json` |
| measured after fix | **1.307 %** void | `12_measure.json` tag `s` |
| Z0 after fix | **52.6 Ω** over 98.7 % of corridor | wave-1 solid anchor + `16_z0_model.json` |

**The fix is not a zone-parameter tweak.** Zone parameters alone reach 8.97 % (`q`/`o`). The defect is
that the *reference plane layer itself* carries signal routing.

---

## 1. Board facts established (not assumed)

| fact | value | command/file |
|---|---|---|
| copper layers | 4 (F.Cu, In1.Cu, In2.Cu, B.Cu) | `01_inventory.py` |
| board bbox | 140.150 × 100.150 mm | `01_inventory.py` `GetBoardEdgesBoundingBox` |
| stackup | 1.6 mm total; F.Cu→In1 dielectric **0.200 mm**; In1→In2 core **1.04 mm**; εr 4.2, tanδ 0.02 | wave-1 `da-stackup/stackup_verify.json` (cited) |
| board zones | 5 | `02_zones.py` |
| footprint keepouts | 2 (J40 antenna, J30 antenna) | `04_hotspot.py` |
| `RF_50R` netclass | **16 nets**, track 0.35 mm, clearance 0.125 mm | `.kicad_pro` `net_settings.classes`, `02_zones.py` |
| total RF_50R F.Cu run | 102.354 mm | `02_zones.py` (wave-1 `rf_run_mm` 102.4 — agrees) |
| RF trace footprint on F.Cu | 42.404 mm² | `12_measure.py` |

The 16 `RF_50R` nets (netcodes): 6 ANT_915, 7 CC1121_RF, 17 CC_LNA_N, 18 CC_LNA_P, 21 CC_PA,
22 CC_PA_BIAS, 27 MATCH_A, 28 MATCH_B, 29 RF_LNA_IN, 30 RF_PA_INOUT, 31 RF_PA_OUT, 32 RF_TR_SW,
33 RX_COMBINE, 34 SAW_PA, 58 GNSS_RF_ANT, 59 GNSS_RF_IN.

### In1 zone geometry (`02_zones.py`)

| layer | net | priority | clearance | thermal gap | spoke | filled area | outlines |
|---|---|---|---|---|---|---|---|
| In1.Cu | `/3V3` | **1** | **0.25** | 0.40 | 0.35 | 12,164.05 mm² | 3 |
| In1.Cu | `/GND` | 0 | 0.20 | 0.50 | 0.50 | **82.18 mm²** | **177** |

Cited lines: `/3V3` zone at
[main_rev_b.kicad_pcb:56077](../../repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb#L56077)
(`priority 1`) and
[:56079](../../repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb#L56079) (`clearance 0.25`);
`/GND` zone at
[:58870](../../repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb#L58870) (`clearance 0.2`).

**The shape of the defect:** In1 is 86.7 % `/3V3` by area, and the `/GND` zone on In1 is shattered into
177 slivers totalling 82 mm² (avg 0.46 mm² each). In1 is therefore *not* a reference plane — it is a
plane that has been cut up by In1-layer routing.

---

## 2. Method (reproducible)

1. `01_inventory.py`, `02_zones.py` — board/zone/netclass/zone-fill inventory.
2. `03_void_segments.py` — builds the In1 copper union = (filled zone polys) ∪ (In1 tracks) ∪ (In1 pads),
   then subtracts it from each RF trace's swept polygon. `SHAPE_POLY_SET.BooleanSubtract`,
   polygonisation error 0.002 mm.
3. `05_map.py` — 0.20 mm ASCII raster of In1 copper vs RF trace, used to eyeball the defect shape.
4. `06_voidpolys.py` — void polygons with along-track / across-track extents.
5. `08_cause.py` — for every void polygon, minimum distance to every In1 copper object of another net
   (exact point-to-segment minimum over polygon outlines).
6. `07_probe.py`, `14_zones.py` — plane-boundary vertex dump; zone fill dump per variant.
7. `11_make.py` → `13_refill.py` → `12_measure.py` — each variant built, refilled and measured in **three
   separate processes** (SWIG invalidates `board.Zones()` after `PCB_TRACK` removal in-process).
8. `16_z0_model.py`, `17_table.py` — Z0 mapping and the void table.

**Fill trust check:** refilling the unmodified board reproduces the stored fill *exactly*
(12,164.050 mm² vs stored 12,164.05). The stored fill is current, so the baseline is trustworthy.

---

## 3. Void inventory

Full table: **[VOID_TABLE.csv](VOID_TABLE.csv)** (20 rows, columns: id, net, bbox, along, across, area,
unsupported %, root cause, blocker, Z0).

Baseline: **20 void polygons, 4.1701 mm², 9.834 % of the 42.404 mm² RF F.Cu footprint.**
Across all RF layers (including the two `CC_LNA_N` segments on In2) the figure is **10.96 %**
(4.7400 / 43.2416 mm²). Wave-1 reported 11.14 %; the 0.2 pp difference is denominator definition
(wave-1 used a 0.6 mm-radius corridor length test, `da-stackup/rf_reference_cleanliness.json`), not a
different defect.

### Distribution — one hotspot

| cluster | voids | area mm² | share |
|---|---|---|---|
| U40(CC1121) → FL40/FL41 RF front-end, x≈95–102, y≈58–66 | 15 | 3.8466 | **92.2 %** |
| GNSS_RF_IN, x≈93–95, y≈16–17 | 4 | 0.2980 | 7.1 % |
| RF_LNA_IN @ U41, x≈112.3, y≈60.2 | 1 | 0.0255 | 0.6 % |
| | **20** | **4.1701** | |

**14 of the 20 voids (4.026 mm² = 96.5 % of void area) span the full trace width** (`across` = 0.350 mm).
These are not "the plane pulled back a little" — the reference is **100 % absent** beneath those sections.

Per-net obstruction (mine, `08_cause.json`, vs wave-1's independent corridor test):

| net | my worst void | my void % of that net's run | wave-1 % clean (cited) |
|---|---|---|---|
| CC_LNA_N | 0.7094 mm² | — | 49.9 % |
| CC_LNA_P | 0.8996 mm² | — | 67.3 % |
| CC_PA | 0.5456 mm² | — | 61.9 % |
| GNSS_RF_IN | 0.0877 mm² | — | 81.5 % |

The two rankings agree: the same four nets are the worst in both measurements.

---

## 4. Root cause — one word per void: **clearance** (all 20)

`08_cause.json` measures the nearest non-`/3V3` In1 copper object to each void. Result: **every** void
has such an object at distance ≈ 0.000–0.05 mm, and the void boundary sits at the `/3V3` zone's
0.25 mm clearance from it.

Worked example, the single largest void (V01, `RF:CC_LNA_P`, 0.8996 mm²):

- Void bbox x[96.263..98.873], y[61.575..61.925]. The RF trace is the segment
  (96.438, 61.750) → (101.375, 61.750), 0.35 mm wide.
- Nearest blocker: In1 track `/915 MHz RF/VDD_CC112` w=0.25 mm at
  (97.466, 60.038) → (98.998, 61.571), **distance 0.000 mm** — the void touches it.
- The `/3V3` fill's own edge in that window runs at **x = 99.373**
  (`07_probe.py`, vertex k=5043). The clearance envelope of the vertical In1 track
  `VDD_CC112` at x = 98.998, width 0.25, is 98.998 + 0.125 + 0.25 = **99.373**. Exact match.

So the void is the intersection of (RF trace footprint) with (the 3V3 plane's 0.25 mm pull-back from
In1 signal copper). Nothing else.

### Corroboration from wave-1 (independent method, same conclusion)

wave-1 `da-stackup/rf_reference_cleanliness.json` (cited) reports obstructed RF run length by nearest
foreign net:

```
"/915 MHz RF/VDD_CC112":      5.48 mm
"/GNSS/GNSS_UART_RX_2V8":     1.03 mm
"/GNSS/GNSS_RESET_OD":        1.02 mm
```
and `foreign_in1_tracks: 293`, `foreign_in1_len_mm: 1100.7`.

Both methods, built independently, rank the same three nets. `VDD_CC112` dominates in both.

### Why NOT the other three candidate causes — each ruled out with evidence

| candidate | verdict | evidence |
|---|---|---|
| **keepout** | **ruled out** | The only two keepout/rule areas are footprint-embedded. J40: (135.485,61.55)–(137.575,63.45); J30: (83.485,18.05)–(85.575,19.95) (`04_hotspot.py`). Neither intersects the hotspot (95–102, 58–66) nor either smaller cluster. `no-copper-pour=True` on both, so if they were the cause we would see voids there — the RF traces do not pass there. |
| **thermal** | **ruled out** | The U40 EP (3.45 mm, 9 × 0.5 mm GND thermal vias) *does* get GND fill on In1: fill outline FILL[63] covers x[92.68..95.25] y[59.80..62.46] (`05_map.py`). Thermal relief is working there; it is not creating void under any RF trace. |
| **priority** | **ruled out as the mechanism** | `/3V3` is priority 1 and `/GND` priority 0, so `/3V3` fills first. If priority were the cause we would see GND filling the gaps. Setting the In1 `/GND` zone island removal to `NEVER` changed the result by **0.000 mm²** (`09_experiments.json` tag `C` — byte-identical to tag `B`). The gaps are not lost islands; they are never generated. |
| **clearance** | **confirmed** | See above: 20/20 voids, blocker at d≈0, plane edge at exactly 0.125+w/2+0.25. |

One correction to the obvious hypothesis: I also tested adding a **GND corridor pour** on In1 at
priority 3 above `/3V3` (variant `j`, `14_zones.py`). It made things **worse** — 9.83 % → **18.52 %**.
It filled only 19.39 mm² across the three corridor rectangles (73.5 mm² total) while removing 73.87 mm²
of `/3V3` (12,164.05 → 12,090.18), and introduced new clearance voids along its own boundary.
**Do not do this.**

---

## 5. Proposed change

### Rule change

None of the four offered levers (tighten clearance / move via-pad / stitch row / zone priority) is
sufficient as a clearance edit, and I measured that. The change is the second lever — **move the
offending routing off the reference layer** — applied to exactly 13 segments.

No zone parameter needs to change. The `/3V3` zone stays at priority 1 / clearance 0.25 / thermal 0.4 /
min_thickness 0.25 exactly as at
[main_rev_b.kicad_pcb:56077-56085](../../repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb#L56077).

### Exact segments to move off In1 (`15_movetracks.json`)

7 × `/915 MHz RF/VDD_CC112`, w=0.250, all on In1.Cu:

| # | x1, y1 | x2, y2 | len mm |
|---|---|---|---|
| 1 | 97.466, 60.038 | 98.998, 61.571 | 2.167 |
| 2 | 98.998, 61.571 | 98.998, 64.287 | 2.716 |
| 3 | 98.903, 64.381 | 93.788, 64.381 | 5.116 |
| 4 | 98.998, 64.287 | 98.903, 64.381 | 0.134 |
| 5 | 97.466, 60.038 | 96.378, 58.951 | 1.538 |
| 6 | 96.378, 58.951 | 96.378, 58.562 | 0.389 |
| 7 | 95.150, 64.200 | 95.250, 64.381 | 0.207 |

4 × `/RF_GPIO2`, w=0.200, on In1.Cu:

| # | x1, y1 | x2, y2 | len mm |
|---|---|---|---|
| 8 | 95.500, 58.600 | 95.500, 60.500 | 1.900 |
| 9 | 95.500, 60.500 | 93.500, 60.500 | 2.000 |
| 10 | 95.600, 58.400 | 95.600, 58.500 | 0.100 |
| 11 | 95.600, 58.500 | 95.500, 58.600 | 0.141 |

2 × GNSS, w=0.250, on In1.Cu (these merely clip the GNSS corridor corner):

| # | x1, y1 | x2, y2 | len mm |
|---|---|---|---|
| 12 | /GNSS/GNSS_RESET_OD: 100.173, 23.042 → 84.513, 7.382 | | 22.147 |
| 13 | /GNSS/GNSS_UART_RX_2V8: 99.869, 22.149 → 91.297, 13.577 | | 12.123 |

Target layer: **B.Cu**. B.Cu carries 12,728.8 mm² of 14,036 mm² GND fill, so it has room, but this is
the one part of the proposal I did **not** verify — see §9.

**Leave alone:** the 12 mm `/GND` In1 track (95.000, 60.000) → (95.000, 48.000). Removing it changed
nothing measurable (variant `h` = variant `s` = 1.307 %), and GND is a legitimate plane net.

### Why not "just tighten clearance" — measured

| variant | change | void % | Δ |
|---|---|---|---|
| `s0` | none (control) | 9.834 | — |
| `q` | `/3V3` clearance 0.25→0.125, min_thickness 0.25→0.10 | 8.967 | −0.87 pp |
| `o` | both In1 clearances →0.125, `/3V3` minth 0.15, `/GND` minth 0.10, `/GND` island never | 8.975 | −0.86 pp |
| `D` | `/3V3` clearance 0.10 | 8.992 | −0.84 pp (no further gain below 0.125) |
| `A` | `/3V3` clearance 0.125 only | 8.992 | −0.84 pp |
| `j` | GND corridor pour prio 3 | **18.522** | **+8.7 pp — worse** |
| `r` | move 11 In1 segments (VDD_CC112 + RF_GPIO2) | **2.010** | −7.82 pp |
| `s` | move 13 In1 segments (r + 2 GNSS) | **1.307** | −8.53 pp |
| `h` | move all 14 In1 signal segments | 1.307 | −8.53 pp |
| `f` | move all 350 In1 non-3V3 tracks board-wide | 1.307 | −8.53 pp |

Two things this table says:

1. **Clearance tuning saturates at ~8.97 %.** Halving the clearance only halves a 0.125 mm sliver; it
   cannot restore a 2.6 mm-long plane cutout. The shortfall is structural.
2. **13 segments achieve the entire board-wide benefit.** `s` = `h` = `f` = 1.307 % exactly. The other
   337 In1 signal tracks are irrelevant to the RF corridor. This is what makes the fix minimal.

(`f`/`h`/`s` measured in isolated processes via `11_make.py` → `13_refill.py` → `12_measure.py`;
`12_measure.json`, tags `r`,`s`,`h`,`f`.)

---

## 6. Result

### Residual after the fix (`15_final.py`, variant `h`)

5 residual polygons, **0.5542 mm²**, **1.307 %**:

| net | area mm² | location | cause |
|---|---|---|---|
| CC_LNA_N | 0.2384 | x[98.749..99.476] y[60.824..61.218] | layer-change via at (99.300, 61.000), drill 0.300 / pad 0.600 |
| CC_LNA_N | 0.2384 | x[100.824..101.469] y[60.624..61.316] | layer-change via at (101.000, 60.800), drill 0.300 / pad 0.600 |
| CC_PA | 0.0331 | x[95.194..95.550] y[64.254..64.600] | L41 land clearance |
| CC_PA | 0.0106 | x[95.439..95.550] y[64.254..64.470] | L41 land clearance |
| RF_LNA_IN | 0.0255 | x[112.300..112.425] y[60.190..60.522] | U41 pad 17 (/GND) clearance |

The two dominant residuals are **irreducible without changing layer transitions** — a CC_LNA_N via must
punch In1 to reach In2. Getting them to zero needs blind/buried vias or moving the In2 transition out of
the corridor. I did not take that on.

### VOID_PCT after fix

**1.307 %** (0.5542 / 42.404 mm²), down from 9.834 %. That is **−86.7 %** of the void area.
If the 2 In2 segments are included the same way as the baseline: 0.5542+0.57 = 1.124 / 43.2416 = **2.60 %**.

### Z0_BAND after fix

Anchors, all cited from wave-1 or calibrated against it:

| condition | Z0 | source |
|---|---|---|
| solid In1 `/3V3` at h = 0.200 mm | **52.6 Ω** | wave-1 `da-em-field` 2D FD quasi-static (cited) |
| same, analytic check | 51.20 Ω | wave-1 `da-stackup/z0_results.json` h=0.20 row (cited) |
| full-width void, In1 absent, In2 absent → B.Cu at h = 1.510 mm | **119.6 Ω** | `16_z0_model.json`, HJ calibrated ×0.951 |
| wave-1 measured void band, top | 118 Ω | wave-1 `da-em-field` (cited) |

My Hammerstad-Jensen implementation reproduces wave-1's published table at a constant +5.2 %
(51.20 → my 53.83 at h=0.2), i.e. wave-1's skrf run included the 0.035 mm copper-thickness correction I
omitted. After the ×0.951 calibration it matches to 0.02 %. Extending it to h = 1.510 mm gives **119.6 Ω**,
which coincides with wave-1's independently measured 118 Ω band top. In2 is not a usable fallback
reference: `/1V1` holds only 256.05 mm² on 2 outlines (x[45.49..74.06] y[36.5..61.5] and one 2nd), none
under the RF corridor — so a voided In1 sees B.Cu.

**Z0_BAND = 52.6 Ω over 98.7 % of the corridor.** The residual 1.3 % sits at two 0.73 mm via entries.
At 915 MHz, εeff ≈ 3.17 → λg ≈ 184 mm, so a 0.73 mm section is 0.004 λg; the transition reflection
per step is Γ = (118−52.6)/(118+52.6) = 0.384 and the net two-step contribution is
≈ 2·0.384·sin(π·0.73/184) ≈ **0.009** → S11 ≈ −41 dB. Electrically negligible.

So the corridor returns to the solid-plane condition, i.e. the **wave-1 solid-plane S11 of −10.5 dB**
(902–928 MHz worst), from the −1.35 dB as-built figure. *(That −10.5 dB is a wave-1 model result, not
re-simulated here; note it is itself marginal for a 915 MHz link and is a separate defect.)*

---

## 7. Exact parameters, for the record

Nothing in the zone definitions changes. If the implementer instead wants the no-reroute option, the
best measured zone-only setting is variant `o`:

```
In1 /3V3 zone  (file line 56071):  (connect_pads yes (clearance 0.125))    <- from 0.25
                                   (min_thickness 0.15)                    <- from 0.25
In1 /GND zone  (file line 58863):  (connect_pads yes (clearance 0.125))    <- from 0.2
                                   (min_thickness 0.10)                    <- from 0.25
                                   island_removal: never
=> 8.975 % void  (from 9.834 %)   -- measured, tag `o`
```
That is a **0.86 pp** improvement, i.e. it does not fix the impedance. It is listed only so the
alternative is not left untested.

---

## 8. Risk

**Moving 13 segments is a real reroute, not a free edit.** My 1.307 % is a *geometric* measurement: I
deleted those segments and refilled, which proves the plane recovers, but the replacement routing must
still reach the same pads on B.Cu. `VDD_CC112` feeds U40 pads 1/5/12/13/15/22/25/27/28 and C85/C106/R41;
B.Cu is 90.7 % GND-filled and already carries its own routing, so the reroute may fail DRC on B.Cu and
could push `VDD_CC112` onto F.Cu — where it would then cut the *top-side* GND pour instead. That
trade has not been evaluated. Second risk: the two CC_LNA_N layer-change vias keep 0.48 mm² of void
(0.65 % of the corridor) no matter what, so a "0 % void" acceptance criterion is unachievable without
blind vias. Third: `RF_GPIO2`/`GNSS_*` legs 12–13 are long diagonals (22 mm and 12 mm); moving them for
0.30 mm² of gain is poor value and can be deferred without materially changing Z0.

---

## 9. NOT verified

- **That the reroute fits on B.Cu.** The bottleneck of this proposal. UNVERIFIED.
- **S11 after the fix.** Inherited from wave-1's solid-plane model; not re-simulated. UNVERIFIED as a
  fresh EM result.
- **Mechanical/assembly impact** of changing In1 copper (the 3V3 plane's current-carrying area drops by
  the moved traces' clearance envelopes). Not assessed.
- **DRC cleanliness** of any variant. No DRC was run — variants were refilled and measured, not checked.
- The two-In2-segment accounting (10.96 % vs 9.834 %) uses a different reference layer (In2's reference
  is In1/B.Cu, not In1 alone); those two segments are 1.9 % of the run and do not change any conclusion.

---

## 10. File index

| file | what |
|---|---|
| `01_inventory.py`, `02_zones.py`, `02_zones.json` | board, zone, netclass, fill inventory |
| `03_void_segments.py`, `03_void_segments.json` | per-segment void, all RF layers |
| `04_hotspot.py`, `07_probe.py`, `05_map.py`, `05_map.out.txt` | hotspot diagnosis, plane-edge vertices, ASCII raster |
| `06_void_polys.py`, `06_void_polys.json` | **20 void polygons with extents** |
| `08_cause.py`, `08_cause.json`, `08_cause.out.txt` | nearest-blocker distance per void → root cause |
| `09_experiments.py/json`, `10_experiments2.py` | first-pass variants (clearance, island, min_thickness) |
| `11_make.py`, `13_refill.py`, `12_measure.py`, `void_results.json` | 3-process variant build → refill → measure |
| `14_zones.py` | zone fill dump per variant |
| `15_final.py`, `15_movetracks.json`, `15.out.txt` | **the 13 segments** + residual voids |
| `16_z0_model.py`, `16_z0_model.json` | HJ validation vs wave-1 + extension to void reference distances |
| `17_table.py`, `17.out.txt` | generates the table |
| **`VOID_TABLE.csv`** | **the deliverable table** |
| `fixwork/v_*.kicad_pcb`, `v_*.kicad_pro` | every variant board, refilled (reproducible artefacts) |

Scripts are numbered in execution order; all are runnable with
`"C:\Program Files\KiCad\9.0\bin\python.exe" <script>`.