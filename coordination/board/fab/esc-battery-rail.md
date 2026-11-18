# ESC rev_b — can the battery rail carry its bus current, and on which layers?

**Unit:** `esc-battery-rail` · **Wave 6** · Owner constraints in force: **ESC single-sided, as
compact as possible; 4 oz on the ESC only; inners 1.5 oz; no HDI anywhere; $60 spend cap.**

**Host:** KiCad 9.0.7 (`kicad-cli` 9.0.7, `pcbnew` 9.0.7 / Python 3.11), arithmetic and
geometry in CPython 3.12 with shapely 2.1.2 / scipy 1.16.3.

**Nothing was written into a repo.** No commit, no push, no `audit/*` branch, no file outside
`E:/engineering-portfolio-audit/evidence/esc-battery-rail/`. Every board touched is a **copy**.

| artefact | sha256 / size |
|---|---|
| board of record, copy | `esc_rev_b_orig.kicad_pcb`, sha256 `992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD`, 4,988,844 B |
| power-first placement, copy | `esc_rev_b_powerfirst.kicad_pcb`, 2,957,981 B — **0 tracks, 0 vias, 0 zones** (measured, §2) |
| **executed fix** | `esc_rev_b_railfix2.kicad_pcb`, 5,084,168 B |
| instrument | `railmc.py` + 19 controls in `06_validate.json` (**PASS**) |

---

## 0. The answer

| question | answer |
|---|---|
| bus current per rail | **59.05 A** (`0.9841 × 60 A`); six rails, 354.3 A aggregate |
| is 360 A one conductor? | **No.** `REV_B_ARCHITECTURE.md:19`: *"360 A maximum, distributed by six external fused star/busbar taps; never by a shared PCB trunk"* |
| copper on BATP | 4 oz F.Cu **922.5 mm²** of copper, in two disjoint pours, + 1.5 oz In1 **5,039.0 mm²** plane |
| copper on BATN | 4 oz B.Cu **5,106.6 mm²** plane; F.Cu is **64 separate pad islands**, no pour |
| width the rail offers BATP | **F.Cu 0 mm in series; In1 16.00 mm** (0.0525 mm thick) |
| width the rail offers BATN | **B.Cu 38.00 mm** (0.14 mm thick) |
| width required at 59.05 A / 20 K | **4 oz 13.68 mm** (1.9146 mm²); **1.5 oz inner 94.87 mm** |
| **rail capacity as built** | **BATP 0.5242 mm² = 3.74 mm of 4 oz; BATN 1.4139 mm² = 10.10 mm** |
| **deficit** | **BATP −1.3904 mm² = −9.93 mm** (27 % of requirement); **BATN −0.5007 mm² = −3.58 mm** (74 %) |
| after the executed fix | BATP **1.5082 mm²** (79 %), BATN **1.7595 mm²** (92 %) — still short **2.90 mm** and **1.11 mm** |
| what binds | **via barrels**, not copper width: 48 and 56 barrels after the fix, 10 and 45 before |
| **RAIL PASSES?** | **NO.** Short by **9.93 mm** (BATP) and **3.58 mm** (BATN) of 4 oz-equivalent width at 59.05 A / 20 K |

---

## 1. What the rail must carry, and where that number comes from

```
I_phase,rms = 60 A                      REV_B_ARCHITECTURE.md:18 "60 A continuous design
                                        current per motor channel"
I_bus/I_ph  = 3·m·cosφ / (2√2·η) = 3·1.0·0.9/(2√2·0.97) = 0.9841     (m=1, cosφ=0.9, η=0.97)
I_bus       = 0.9841 × 60 A = 59.05 A   per cell rail
6 cells     = 354.3 A                   aggregate, but see below
```

`REV_B_ARCHITECTURE.md:19` settles the 360 A question: *"Aggregate 360 A maximum, distributed by
six external fused star/busbar taps; **never by a shared PCB trunk**"*. So:

* the **bus is not 360 A in one conductor**. 360 A is 6 × 60 A and it is distributed *externally*;
* each of the six battery nets (`/M1_BATP`…`/M6_BATP`, `/M1_BATN`…`/M6_BATN`) carries
  **59.05 A**, and that is the number the copper must carry;
* the netlist confirms six **independent** rails — 6 BATP, 6 BATP_IN, 6 BATN, no shared trunk
  (`01_net_census.json`). Each is a separate net because each cell is referenced only to its own
  `M<n>_BATN` (`REV_B_ARCHITECTURE.md:35-36`).

The 360 A figure survives only as a **sum of six separate rails that share no copper**, which is
why "360 A" is not a rail requirement. Using 360 A would have overstated the copper requirement
by 6×.

---

## 2. The rail's real copper, per layer

`02_geom.py`, `04_extract.py` → `04_rail_geom.json`. Copper is the **union** of zone fills, pad
shapes (`PAD::TransformShapeToPolygon`) and via pad discs — every element carries its own KiCad
layer id; nothing is inferred from a name.

```
/M1_BATP    F.Cu   2 zones  869.17 mm2   (a 70.10 mm2 patch at the bus shunt + a 799.07 mm2 strip
                                          at the FET drains, bboxes 9.2x9.9 and 57.0x15.7 mm)
                     + pads + via discs  -> 922.51 mm2 total copper on F.Cu
            In1.Cu 1 zone 5039.01 mm2   plane, covers the cell
            In2.Cu 0 zones                       (via pad discs only)
            B.Cu   0 zones                       (via pad discs only)
/M1_BATN    F.Cu   0 zones               333.31 mm2 = 80 pads + 45 via discs, in 64 components
            B.Cu   1 zone 5106.61 mm2   plane
            In1/In2  0 zones, PTH pad rings only
```

**The 4 oz outer is not in the BATP series path.** `12_perlayer.py` measures the per-layer
min-cut with the barrels removed (a layer that cannot connect its own terminals reports 0):

| layer | t | copper | width it offers the through current |
|---|---|---|---|
| BATP F.Cu | 0.140 mm | 922.5 mm² | **0 mm — two disjoint pours** (comp 81.31 mm² holds R1123.2; comp 804.28 mm² holds Q1101/03/05.9) |
| BATP In1.Cu | 0.0525 mm | 5,039.0 mm² | **16.00 mm** at the neck beside the shunt via cluster |
| BATN B.Cu | 0.140 mm | 5,106.6 mm² | **38.00 mm** |
| BATN F.Cu | 0.140 mm | 333.3 mm² | **0 mm — 64 isolated pads, no pour** |
| In2.Cu / B.Cu (BATP) | — | via discs only | **0 mm** |

So the topology is not the one the stackup implies. Battery current enters the BATP **pad on
F.Cu**, dives through **through-vias into the 1.5 oz In1 plane**, and comes back up to the FET
drain pads. **The positive rail's series conductor is the 1.5 oz inner plane**, and the 4 oz
outer carries it only within each local island.

**Fill currency (checked, because a stale fill would invalidate everything):** refilling a copy
of the board of record reproduces the saved zone areas to **< 0.01 mm²**
(`16_fillcheck.json`: BATP F.Cu 869.17 → 869.17, In1 5039.01 → 5039.01, BATN B.Cu 5106.61 →
5106.61). The fills describe copper the board really has.

---

## 3. What each layer needs at 59.05 A — and the instrument's calibration

IPC-2221 §6.2 closed form, `A[mil²] = (I/(k·ΔT^0.44))^(1/0.725)`, k = 0.048 external /
0.024 internal. **Calibration against the two settled programme figures:**

| check | computed here | settled | delta |
|---|---|---|---|
| 60 A / 20 K / 4 oz | **13.981 mm** | 13.980 mm | +0.010 % |
| 60 A / 20 K / 1.5 oz inner | **96.991 mm** | 96.990 mm | +0.001 % |

The arithmetic reproduces both to 0.01 %, so it is the same instrument every earlier wave used
and the comparison with 370.12 / 382.71 cm² stays valid.

Required width at **59.05 A**, by layer and by allowed rise (`20_numbers.py`):

| ΔT | 4 oz outer | 1.5 oz inner | 2 oz inner |
|---|---|---|---|
| 10 K | 20.83 mm | 144.49 mm | 108.37 mm |
| 15 K | 16.28 | 112.97 | 84.73 |
| **20 K** | **13.68** | **94.87** | **71.15** |
| 25 K | 11.94 | 82.86 | 62.14 |
| 30 K | 10.69 | 74.18 | 55.63 |
| 50 K | 7.84 | 54.40 | 40.80 |

Cross-section required at 20 K: **1.9146 mm²** (1.9572 mm² at 60 A).

**IPC-2152.** The standard is paywalled; its charts are not reproduced here and are not claimed.
What is used is the *published* IPC-2221↔IPC-2152 comparison (1 oz, 10 °C:
[TraceWidthCalculator](https://tracewidthcalculator.com/blog/ipc-2221-vs-ipc-2152-pcb-standards/)):
external widths **12–20 % narrower**, and the internal-layer penalty falls from **+154 %** to
**+100 %**. Scaled to this case: 4 oz outer **10.94–12.03 mm** (1.53–1.68 mm²), 1.5 oz inner
**65.48 mm**. **The verdict does not move**: the deficits below are 3–6× the requirement, far
outside any IPC-2152 correction, so no chart reading can rescue the rail.

---

## 4. Compare: the rail as built

### 4.1 The instrument, and four things it got wrong before it could be trusted

`railmc.py` computes the **min s-t cut** of the copper graph, with capacities in units of copper
cross-section: a lateral edge = `t_layer × h` (a cut through one cell wall), a barrel edge =
`π·d·t_plate` (a plated barrel is in series with everything that crosses it). The flow value is
therefore an **area**, and attributing the cut edges to layers gives a **width per layer**.

It is not trusted on assertion. `06_validate.py` runs **19 controls** with bottlenecks known by
construction, `06_validate.json` → **PASS**: strips 0.25–20 mm (exact), a notch at 1.2 and
0.5 mm, an L-channel 2.5 mm, a pour with a 2.5 mm neck, a 2 mm hole cutting a 6 mm strip to
4.0 mm, an edge notch to 4.8 mm, grid independence at h = 0.2/0.1/0.05/0.025 mm (identical),
parallel layers adding exactly, one barrel as a series limit (0.03142 mm² exactly), and a pad
with 4 × 0.5 mm thermal spokes → 1.92 mm.

Each control that did **not** pass on the first run is recorded as a correction rather than
edited away, and three of the four were my error, not the tool's:

| first-run symptom | cause |
|---|---|
| disc Ø10 measured 1.70 mm | **my test**: terminals sat on the rim, so the source was a 0.4 mm sliver. Control replaced by a pour with a known neck |
| 6 mm strip with a 2 mm hole measured 4.0 mm | **my expectation**: the hole really does remove 2 mm of the section. The tool was right |
| series through two barrels measured 0.0314 vs "0.0137" | **my formula**: ampacity in series is the **narrowest** element (min), not a harmonic sum — that is the resistance formula |
| inner plane contributed 0.021 mm² per via | **the tool**: a barrel was one point edge, so all current left through a single cell's 4 edges. Fixed: a barrel is now a chain of virtual nodes spread over every cell under its pad, so `π·d·t` is the binding element |

Two further instrument checks: the cut is verified to be a **cut** (removing the cut edges
disconnects source from sink; `10_cutcheck.py`, capacities sum to the flow exactly), and a
**layer-id trap** was caught — in this build `In1_Cu = 4`, `In2_Cu = 6`, `B_Cu = 2`, so a
`TopLayer() <= lid <= BottomLayer()` span test silently recorded **zero** vias on every inner
layer. Replaced with `PCB_VIA::IsOnLayer`.

### 4.2 The result

| rail | cut | composition | 4 oz-equivalent width | ampacity @20 K (k=0.048 / k=0.024) | % of requirement |
|---|---|---|---|---|---|
| **BATP** | **0.5242 mm²** | F.Cu pour exit 0.21 + **10 barrels** 0.3142 | **3.74 mm** | 23.1 A / 11.5 A | **27 %** |
| **BATN** | **1.4139 mm²** | **45 barrels** (3 × 15, one cluster per leg shunt) | **10.10 mm** | 47.4 A / 23.7 A | **74 %** |
| requirement | 1.9146 mm² | — | 13.68 mm | 59.05 A | 100 % |

**So: no, the rail does not carry 59.05 A — and the shortfall is in the vias, not the planes.**
The planes are generous (B.Cu 38 mm against 13.68 mm needed; `BATN` passes on plane width alone
by **+24.32 mm**). Both rails are limited by the number of barrels that can pass 59 A.

`BATN`'s 45 barrels are the return path for the three leg shunts — **15 barrels per leg**
(`13_batn_fcu.py`: R1120.2 / R1121.2 / R1122.2 each live in their own F.Cu component with
15 vias, 17.29 mm² each). Per leg the instantaneous worst case is one leg carrying the phase
current: 15 × 0.0314 = **0.471 mm²**, i.e. **21.3 A** at 20 K even on the generous external k —
against a leg that must pass 60 A.

The **third series element** is the pre-shunt section M1_BATP_IN (fused tap -> bus-shunt
input): **1.4280 mm² = 10.20 mm of 4 oz**, also below the 1.9146 mm² requirement (75 %), and it
is the one element the executed fix did not touch, because it has **no barrels at all**: it is a
plain **0.14 mm F.Cu pour**, so its 10.20 mm is its true width.

The k=0.024 column matters here: the cut is **100 % buried barrel copper** after the fix, and
a plated barrel sits inside FR4. On the k=0.024 basis the two rails carry **11.5 A** and
**23.7 A** — 19 % and 40 % of the design current. The bracketed k=0.048 numbers are the
generous reading; the honest one for copper that is inside the board is the lower column.

---

## 5. The options, in order of cost, in mm of width and mm² of copper

One 0.4 mm barrel with 25 µm plating = **0.03142 mm²**; 1.9146 mm² needs **60.9 barrels** per rail.

| # | option | cost in mm of width | cost in mm² of copper | does it close it? |
|---|---|---|---|---|
| **O1** | **widen by re-placing** — make the 4 oz F.Cu one continuous rail | **13.68 mm** of 4 oz alone; **8.77 mm** if In1's 16.00 mm stays in parallel | **330 mm² of pour per cell** (8.77 × 37.7 mm) = **1,979 mm² for six cells**, cross-section 1.228 mm² | **yes** — but see the free-width measurement below |
| **O2** | **stitching vias to parallel layers** | none (vias add area, not width) | **+51 barrels on BATP, +16 on BATN** = +1.60 / +0.50 mm², i.e. **+60 vias**; at 1.8 mm² of land per via = **+108 mm² of pad/land per cell** | **yes, if the land can grow** — measured: only **0.09 mm²** of the shunt patch is more than 1.0 mm from an existing via, so **the land is full** |
| **O3** | **split the bus into more parallel feeds** | none | none — it divides the current | **yes**: BATP 23.1 A capacity → **3 feeds**; BATN 47.4 A → **2 feeds** → **24 taps** instead of 6 (an architecture change; `:19` allows more taps, it forbids a shared trunk) |
| **O4** | **change the inner copper weight** 1.5 → 2 oz | In1 16.00 mm × 0.07 = **1.12 mm²** (+0.28) | ×1.33 on In1 only | **no** — a 2 oz inner still needs **71.15 mm**; 16 mm is 4.4× short. A fab change for nothing |

**O1 needs a corridor that does not exist.** `14_freewidth.py` / `15_freewidth_*.json` measure the
widest completely-clear vertical channel across the shunt-to-FET band (y 62–99.6) per layer:

| board | F.Cu | In1.Cu | In2.Cu | B.Cu |
|---|---|---|---|---|
| board of record | **2.75 mm** | **7.50 mm** | 3.25 mm | 0.00 mm |
| power-first placement | **3.25 mm** | **8.25 mm** | 8.25 mm | 8.25 mm |

O1 needs **8.77 mm on F.Cu**; the widest F.Cu channel anywhere is **2.75 mm** on the board of
record and **3.25 mm** on the power-first placement. **There is no 4 oz corridor to be had on
either placement** — O1 is a re-placement of the cell, not a tweak, which is why it is listed
first in cost even though it is last in effort-to-describe.

---

## 6. What was EXECUTED, and what it measured

`17_execute_fix.py` → `esc_rev_b_railfix.kicad_pcb`, then `18_extension.py` →
**`esc_rev_b_railfix2.kicad_pcb`**. The cheapest option that the geometry permits is **O2 with
the land grown** — because a bare via retrofit is impossible (0.09 mm² free). Executed:

1. **every shunt "pin 2" pad → SOLID zone connection** (24 pads) — removes the thermal-spoke
   exit limit on BATP (0.21 mm²) instead of adding copper;
2. **BATN: the leg-shunt land extended** by a same-net 5.60 × 2.50 mm F.Cu strip under each
   shunt, **+42.0 mm² per cell**, with **+15 vias** (0.4/0.8 through) in that strip;
3. **BATP: the shunt land extended** 4.0 × 4.0 mm, **+16.0 mm² per cell**, with **+9 vias**;
4. refill, save. Totals: **+90 vias, +348 mm² of 4 oz land** over six cells.

Re-measured with the same instrument (`04_rail_geom_fix2.json` → `07_measure_fix2.json`):

| rail | before | after | Δ | required | still short |
|---|---|---|---|---|---|
| **BATP** | 0.5242 mm² (27 %) | **1.5082 mm² (79 %)** | **+0.9840 mm² (+188 %)** | 1.9146 | **−0.4064 mm² = −2.90 mm of 4 oz** |
| **BATN** | 1.4139 mm² (74 %) | **1.7595 mm² (92 %)** | **+0.3456 mm² (+24 %)** | 1.9146 | **−0.1551 mm² = −1.11 mm of 4 oz** |

The cut is now **100 % barrels** on both rails (48 and 56 of them): the previous F.Cu spoke
limit is gone and the planes drop out of the cut entirely, so the rails are now limited purely
by how many barrels the land can hold.

**So the executed option does not pass, and the reason is measured, not argued.** It closes
**71 %** of BATP's deficit and **69 %** of BATN's. The residual is **+13 barrels on BATP and +5
on BATN** (0.41 / 0.16 mm²), which needs a **further +23 mm² and +9 mm² of land per cell** — O2
applied once more.

**The price of the executed change, measured, not asserted:** `kicad-cli pcb drc` on the same
project rules gives **16 → 58 violations**:

| type | original | after fix | delta |
|---|---|---|---|
| `via_dangling` | 16 | 40 | +24 (new vias in fresh fill, not yet routed) |
| **`clearance`** | 0 | **12** | **+12 — the added land and vias collide with existing copper** |
| **`zones_intersect`** | 0 | **6** | **+6 — the added BATN strips overlap existing zones** |
| total | **16** | **58** | **+42** |

Unconnected reads **499 on both boards**, which is `kicad-cli`'s cap and is quoted only as a cap
(the real figure is 1,542 by `pcbnew`). The 18 real geometry conflicts (12 + 6) are the honest
content of "land must grow": **the extra land does not fit either** — the same finding as O1's
free-width table, from a different direction.

---

## 7. Verdict

> **Does the ESC battery rail carry its bus current at 4 oz outer / 1.5 oz inner? NO.**
>
> At **59.05 A** and **ΔT = 20 K** the requirement is **1.9146 mm² = 13.68 mm of 4 oz width**
> (or 94.87 mm of 1.5 oz inner). The rail as built provides **0.5242 mm² = 3.74 mm** on BATP and
> **1.4139 mm² = 10.10 mm** on BATN.
>
> **Deficit: −1.3904 mm² = −9.93 mm on BATP; −0.5007 mm² = −3.58 mm on BATN.**
> This verdict is stated at the **25 µm minimum plated barrel**; at 38 µm both rails gain 1.5×
> and *both pass after the executed fix* (A2). That is the one input the answer is sensitive to.
> After the executed land + via retrofit: **−0.4064 mm² = −2.90 mm** and **−0.1551 mm² =
> −1.11 mm**. Still **no**.

**On which layers it *would* work:** only on the **4 oz outer**. The planes cannot do it: BATN's
B.Cu plane has 38.00 mm against 13.68 mm needed (**passes, +24.32 mm**), but BATP's only series
conductor is the 1.5 oz In1 plane at **16.00 mm against 94.87 mm needed (−78.87 mm)**. So the
rail must be rebuilt on **F.Cu (and B.Cu for the return) at ≥ 13.68 mm continuous**, or
**8.77 mm** continuous if In1's 16.00 mm is kept in parallel — and neither placement has a
channel that wide today (F.Cu best 2.75 mm / 3.25 mm).

**The consequence for the area question, which is what this item was blocking:** a 4 oz rail of
8.77 mm (with the inner plane helping) or 13.68 mm (without) must be reserved *through* the cell,
not fitted around the parts. Reserve **8.77 mm × 37.7 mm = 330 mm² per cell** (**1,979 mm²,
19.8 cm²** for six cells) if the inner plane is kept, or **515 mm² per cell** (**30.9 cm²**) if
not. At six cells that is **+19.8 cm²** of the 382.71 cm² power-first placement, or ~5.2 % of the
board — and it is the difference between an honest area claim and the 370.12 cm² figure, which
was reached by parking copper where the current cannot pass.

---

## 8. Assumption register

| # | assumption | value | direction if wrong |
|---|---|---|---|
| A1 | allowed copper rise | **20 K** (repo states none) | the 10–50 K table is in §3; at 50 K the requirement falls to 7.84 mm and BATN still fails, BATP still fails |
| A2 | plated barrel wall | **25 µm** (1 mil) | at 38 µm every barrel is 1.5× → the rails gain 50 %: BATP 2.26 mm², BATN 2.64 mm² — BATP would then pass, BATN comfortably; this is the one input the verdict is sensitive to |
| A3 | inner-layer k | 0.024 (IPC-2221 internal) | IPC-2152 suggests ~65.5 mm instead of 94.87; the deficit remains 4× |
| A4 | cell current model | 0.9841 × 60 A (m=1, cosφ=0.9, η=0.97) | at cosφ=0.85 the bus is 55.8 A; the deficit shrinks 5 %, nothing else changes |
| A5 | terminal identification | by refdes **and** pad geometry (14.19 mm² shunt land) | refdes are per-cell (R1120/R1220…); a refdes-only match silently skips five of six cells — that bug was hit and fixed |
| A6 | via land capacity | 0.8 mm pad, 0.4 mm drill, 0.5 mm clearance | the 0.09 mm² free-land figure is at 1.0 mm pitch, i.e. generous by 0.3 mm |

## 9. What this does NOT cover

* **Not a thermal solve.** The min-cut gives the copper's current capacity at a stated rise; it
  does not model the FR4, the spreader or the 265 W the cell dissipates. The spreader is still
  mandatory per the settled thermal bound (52.0 / 35.9 / 26.8 A at RthJA 22.4 / 40 / 62 °C/W).
* **A2 is the open sensitivity**, not a footnote: 25 µm vs 38 µm plating moves BATP across the
  pass line. Any claim about this rail should state the plating the fab will quote.
* The executed fix was placed **without a fab-clearance solve** — that is exactly what the +18
  clearance/zone violations in §6 measure.
* **The corridor instrument from this wave (`evidence/esc-corridor-instrument/`) does not exist**
  — the directory is absent — so the width instrument here is the unit's own `railmc.py`, built
  and validated inside this unit.
* `AGENT_BOARD.md` was **not** written: this unit's hard rule is to write only inside its own
  evidence directory.

## 10. Reproduce

```powershell
$kpy="C:\Program Files\KiCad\9.0\bin\python.exe"; $py="C:\Program Files\Python312\python.exe"
$ev="E:\engineering-portfolio-audit\evidence\esc-battery-rail"; cd $ev
& $kpy 01_net_census.py        # which nets, which copper, per layer, per board
& $kpy 02_geom.py              # M1 rail geometry: zone outlines, pads, vias, spans
& $kpy 03_pads.py              # pad census by refdes (defines the terminals)
& $kpy 04_extract.py           # polygons + barrels -> 04_rail_geom.json
& $py  05_topology.py          # components per layer
& $py  06_validate.py          # 17 instrument controls -> PASS
& $py  07_measure.py           # the min-cut of the rail, per layer + total
& $py  10_cutcheck.py          # is the computed cut a CUT
& $py  11_fillcheck.py         # does the plane actually touch the vias
& $py  12_perlayer.py          # per-layer width, barrels removed
& $py  13_batn_fcu.py          # BATN F.Cu components (64 islands)
& $kpy 14_freewidth.py         # widest clear channel per layer
& $kpy 16_fillcheck_refill.py  # are the saved fills current
& $kpy 17_execute_fix.py       # executes the fix -> esc_rev_b_railfix.kicad_pcb
& $kpy 18_extension.py         # BATP land growth -> esc_rev_b_railfix2.kicad_pcb
$env:BOARD="esc_rev_b_railfix2.kicad_pcb"; $env:OUT="04_rail_geom_fix2.json"; & $kpy 04_extract.py
$env:GEOM="04_rail_geom_fix2.json"; & $py 07_measure.py      # before/after
$env:GEOM="04_rail_geom_fix2.json"; & $py 12_perlayer.py
& $py  20_numbers.py           # every number quoted, from one script
& "C:\Program Files\KiCad\9.0\bin\kicad-cli.exe" pcb drc "$ev\esc_rev_b_railfix2.kicad_pcb" `
    -o "$ev\drc_railfix2.json" --format json --severity-all --units mm
```