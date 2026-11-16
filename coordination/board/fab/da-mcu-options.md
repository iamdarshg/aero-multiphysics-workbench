# da-mcu-options-v2 — MCU swap / board growth / nominal-fee performance, with real numbers

**Owner's question (verbatim):** "if board growth doesnt work suggest some options for a different mcu,
how much will i save if i increase size or swap the mcu, and if im able to increase performance for a
nominal fee"

**Three parts:** (a) MCU options, (b) the money each saves or costs, (c) whether a nominal fee buys
more performance.

**Input board:** `evidence/fab-da-path/da_main_rev_b_path6L.kicad_pcb` — the shipped 6-layer artefact
(2,270,141 B, **17 non-through vias**, DRC `{via_diameter}`, unconnected 0 on both tools). The repo's
`hardware/main/rev_b/main_rev_b.kicad_pcb` is the older 4-layer file and still has **36** non-through
vias; it is not the board under discussion and every number below is measured on the 6L copy.
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/da-mcu-options-v2/`. Work on copies only.

> **HEADLINE —** The swap does not save fab money and it does not buy an escape either: **every
> 0.5 mm LQFP fails the board's own 0.60/0.30 via by 0.075 mm**, and the one package that passes
> (+0.100 mm) is a 0.8 mm 8-bit AVR that is ~30–40× slower with no firmware in the repo to port.
> A 4-layer 5-piece spin is **$116 at PCBWay** and ~**$5 of board charge at JLCPCB**, and it is the
> same order line whether you grow the board or swap the MCU — the branch that differs is *doing
> nothing*, which keeps the 17 microvias and buys an HDI build neither fab prices publicly.
> **Board growth to 150×100 mm is $0 in PCB money at PCBWay's own price tier.** The 7th actuator
> channel costs **$0**: pad 49 (GPIO40/ADC0) is an unconnected spare on the part already fitted.

---

## 0. Method and instrument validation

| item | value | how |
|---|---|---|
| board read | `shipped6L.kicad_pcb` (copy) + `shipped6L.kicad_pro` companion | `pcbnew` in KiCad 9.0.7 bundled python |
| design rules as loaded | clearance **0.125**, via **0.60/0.30**, min TH drill **0.200**, min annular **0.100** | `s0_dump.py` |
| **trap caught** | dropping the `.kicad_pro` companion makes the netclass clearance load as **0.000** and inflates every margin by 0.125 mm | first ring run did exactly this; re-run with the companion |
| lane test | a via needs **0.300 (radius) + 0.125 (clearance) = 0.425 mm** centre-to-foreign-copper-edge on **every** layer | the programme's calibrated model, `fab-da-path/REPORT.md` §3.1 |
| geometry | tracks = capsules, pads = KiCad's own copper polygons, vias = discs, zones not obstructions | `vgeom.py`, reused unchanged |

Two via tiers are reported, because the board already ships both: **0.60/0.30** (netclass, needs
0.425 mm) and **0.40/0.20** (the smallest the board's own rules permit, needs 0.325 mm — the shipped
board already carries **6** through vias at 0.20 mm drill).

## 1. U10's functional spec — what the replacement must provide

Measured twice, from two instruments that agree: the schematic netlist
(`hardware/main/rev_b/reports/main_net.xml`) and the board's own pads (`s1_ring.py`).

| item | measured | source |
|---|---|---|
| part / package | RP2354B, **QFN-80** (80 perimeter + 1 exposed pad) | footprint in board |
| land span / pitch / pad | **10.70 mm**, **0.400 mm**, pads **0.200 × 0.800 mm** | `pcbnew` |
| GPIO in use | **40** | netlist: 48 GPIO pins, 8 no-connect |
| spare GPIO | **8** (GPIO40, 41–47) + **6** QSPI pins, all no-connect | netlist |
| nets touching U10 | **53 distinct** (67 netted pins of 81; 14 no-connect) | netlist |
| SPI buses | **3** — sensor (`SENS_SCLK/MOSI/MISO` + `ICM_nCS` + `LSM_nCS`), radio (`RF_SCLK/MOSI/MISO/nCS` + `RF_RESET_N`, `RF_GPIO0/2/3`, `PA_EN`, `LNA_EN`, `HGM`), CAN (`CAN_SCK/MOSI/MISO/nCS/INT` → **MCP2518FD**) | netlist + `REV_B_ARCHITECTURE.md` |
| I²C | 1 — barometer (`BARO_SCL/SDA/DRDY`) | netlist |
| UART | 1 — GNSS (`GNSS_TX/RX/PPS/RESET_N/PWR_EN`) | netlist |
| USB | 1 — `USB_DM/DP` (device) | netlist |
| debug | SWD `SWCLK/SWDIO/RUN`; crystal `XIN/XOUT` | netlist |
| PWM / interrupts | **6** ESC PWM (`PWM_ESC1–6`) + `STATUS_LED`; **7** interrupt-capable inputs (`ICM_INT1/2`, `LSM_INT1/2`, `BARO_DRDY`, `CAN_INT`, `GNSS_PPS`) | netlist |
| ADC / QSPI | **0 used** — all 8 ADC pins and all 6 QSPI pins are no-connect (there is no SPI flash) | netlist |

**So the selection spec is: ≥ 41 GPIO (40 + one for the 7th actuator), 3× SPI, 1× I²C, 1× UART,
USB 2.0 device, SWD, ≥ 7 interrupt inputs, no ADC, no QSPI.** Native CAN is *not* required — the
CAN controller is external (MCP2518FD over SPI) and stays external on any swap.

## 2. Three options at 0.5 mm pitch or coarser — with the pad-lane arithmetic

Every pad figure is **measured from the KiCad 9 land pattern** the footprint is built from
(`s2_packages.py`), not typed in; `available = pitch − (neighbouring pad width)/2` for QFP/QFN and
`pitch/√2 − pad_d/2` for BGA; the need is **0.425 mm** (0.60/0.30 via) and **0.325 mm** (0.40/0.20).

| # | part | package | pitch | pads | pad | **lane** | vs 0.425 (0.60/0.30) | vs 0.325 (0.40/0.20) | verdict |
|---|---|---|---:|---:|---|---:|---:|---:|---|
| — | *RP2354B (current)* | QFN-80 | 0.400 | 81 | 0.20×0.80 | **0.3000** | **−0.1250** | **−0.0250** | the problem |
| **1** | **STM32H723VGT6** | LQFP-100 14×14 | 0.500 | 100 | 0.30×1.60 | **0.3500** | **−0.0750** | **+0.0250** | **FAIL** at netclass via |
| **2** | **STM32H743VIT6** | LQFP-100 14×14 | 0.500 | 100 | 0.30×1.60 | **0.3500** | **−0.0750** | **+0.0250** | **FAIL**, same land pattern |
| **3** | **AT90USB1287-AU** | TQFP-64 14×14 | 0.800 | 64 | 0.55×1.475 | **0.5250** | **+0.1000** | **+0.2000** | **PASS** |
| *neg.* | *0.8 mm BGA (H743XI class)* | TFBGA-216 land | 0.800 | 216 | 0.40 round | **0.3657** | **−0.0593** | **+0.0407** | **FAIL** — BGA does not escape |

Sources: STM32H723VGT6 = LQFP-100, 550 MHz M7 ([element14 STM32H723VGT6 listing](https://in.element14.com/stmicroelectronics/stm32h723vgt6/mcu-32bit-550mhz-lqfp-100/dp/3576957), fetched 2026-11-16; ST DS13313, LQFP100 14×14, e = 0.50 mm BSC). STM32H743VIT6 = the H743 die in the same ST LQFP-100 package — **the land pattern is measured, not the die attributes** (480 MHz / 2 MB / 1 MB is datasheet knowledge, not re-verified here: st.com returned `fetch failed` twice). AT90USB1287-AU = **TQFP-64, 16 MHz AVR** ([element14 listing](https://in.element14.com/microchip/at90usb1287-au/mcu-8bit-avr-16mhz-tqfp-64/dp/1748496), stock 209, fetched 2026-11-16); its 48 I/O and USB 2.0 FS are **datasheet knowledge, not re-verified** (microchip.com returned HTTP 403).

**The arithmetic, stated plainly.**

* At 0.500 mm pitch a 0.30 mm pad leaves a **0.350 mm** lane. Need 0.425 → **short 0.075 mm**.
  To pass at 0.60/0.30 a leaded package needs **pitch ≥ 0.575 mm**; at 0.40/0.20, **≥ 0.475 mm**.
* At 0.800 mm pitch a 0.55 mm pad leaves **0.525 mm** → **+0.100 mm margin, PASS**.
* BGA is *worse* than it looks: the binding neighbour is the **diagonal** ball, not the one beside it.
  0.8 mm pitch with 0.4 mm pads gives **0.3657 mm**, i.e. **−0.0593 mm** — a fancier package buys
  nothing. Holding the 0.4 mm pad, clearing 0.425 mm needs **pitch ≥ 0.884 mm**, so 0.8 mm fails and
  0.9 mm would just clear it.
* Option 2 is not a separate geometry: it is option 1 with more flash/RAM, so it inherits the same
  −0.075 mm and the same land pattern (a re-spin can go straight to H743 without a second layout).

**The negative that matters:** there is **no 32-bit MCU with ≥ 41 GPIO at 0.5 mm pitch or coarser that
passes at the board's netclass via.** Every modern 32-bit part in this class is 0.5 mm LQFP (fails
−0.075) or ≤0.8 mm BGA (fails −0.059). The only passing parts at 0.8 mm are 8-bit QFPs.

## 3. What changes per option

| | **1. H723VGT6** | **2. H743VIT6** | **3. AT90USB1287** |
|---|---|---|---|
| pads | 81 → **100** | 81 → **100** | 81 → **64** |
| land span | 10.70 → **16.95 mm** = **+6.25 mm** | same **+6.25 mm** | 10.70 → **16.80 mm** = **+6.10 mm** |
| nets remapped | **53** (every U10 pin number changes) | **53** | **53** |
| footprints that must move | **20** — C30–C42 (13), C10–C13 (4), FB1, R4, L1 (prior `collide_land_count`) | **20** | **20** |
| schematic | **yes** — symbol swap + 53 net renames + ERC | yes | yes |
| firmware | **yes, and it does not exist** | yes | yes |
| clears 0.60/0.30? | no (−0.075) | no | **yes (+0.100)** |
| clears 0.40/0.20? | **yes (+0.025)** | yes | yes (+0.200) |
| bus count vs the 3-SPI spec | 6× SPI — fine | 6× SPI — fine | **1× SPI + 1 MSPI + TWI (datasheet)** → the third bus must be shared with a second CS line or bit-banged |
| performance vs RP2354B | **~3–5× (estimate, core class — not benchmarked)** | ~3–4× (estimate) | **~30–40× slower (estimate)** |

**Firmware — quoted, not estimated.** There is no firmware source in the repo. `meson.build` names
**27 C sources + 1 assembly file** (`src/main_board/low_level/boot_stage2/boot2_w25q080.S`) and
**13 include directories**, builds `-mcpu=cortex-m33 -mfpu=fpv5-d16`, `-DPICO_RP2350B`, and converts
via `tools/uf2conv.py -f rp2350-arm-s` — it is wired to the RP2350 bootrom and the Pico SDK 2.1.0.
`docs/engineering/FIRMWARE_SOURCE_AUDIT.md` records that the tree "does not contain the firmware
inputs listed by `meson.build`: **36 source files and 13 include directories are absent**" and that
"a main-board or ESC image cannot be built from this checkout". A swap therefore replaces a build
description with a rewrite against a different vendor SDK, **with no baseline source to port from**.

**Firmware cost = UNKNOWN. No number is invented here; a human must scope it.** It is the only line
item that can dwarf everything else on this page, and it is mandatory for all three options.

## 4. Fabrication cost — 4-layer, 1 oz, 5 pcs, 140 × 100 mm

| house | price | basis | lead time |
|---|---|---|---|
| **PCBWay** | **$116.00 USD** | 4-layer prototype, 150×100 mm product (smallest published tier that contains 140×100), 5 pcs, 1.6 mm, 1 oz, HASL — [page fetched 2026-11-16, HTTP 200](https://www.pcbway.com/pcb_prototype/4_Layer_pcb/150x100mm.html) | 2–3 build days standard (PCBWay's own page, as recorded in `fab-4oz-capability/REPORT.md:149`) |
| **JLCPCB** | **$4.94 board charge** for 0.07 m² | published small-batch 4-layer rate **$70.6/m²** ([JLCPCB news, fetched 2026-11-16](https://jlcpcb.com/news/discount-on-quality-4-layer-pcbs)) × 5 × 0.014 m² | 24-hour production turnaround advertised on the same page |
| *JLCPCB caveat* | order **total not quotable** | its instant quote is JavaScript-only; the $70.6/m² board charge is real, the checkout floor is not verified | — |

**Delta between the two branches: $0.** Not because shipping is free, but because *both* re-spin the
same 4-layer, 140×100, 1 oz board — grow it or swap the MCU and the PCB order is the identical line
item. **Delta versus doing nothing is negative but unmeasurable:** doing nothing keeps the 17
microvias and therefore an HDI (1+2+1) build, and neither fabricator publishes an HDI price (both gate
it behind a quote — searched both sites and every prior wave in this programme: **NOT QUOTED**). So the
honest cash statement is: **fab money does not decide this; the 25–40 h of layout does, and the
firmware rewrite does.**

## 5. Board growth — the branch the owner asked about

### 5.1 What the board already has room for

| measurement | value |
|---|---|
| outline | **140.00 × 100.00 mm = 14,000.0 mm²** (4 Edge.Cuts segments, shoelace) |
| U10 centre | **(59.000, 50.000)** |
| U10 → board edge | **W 59.00 · E 81.00 · S 50.00 · N 50.00 mm** |

The outline is **not** the constraint: the nearest edge is 50 mm away. What is crowded is the
**ring of copper around U10** — decoupling caps C30–C42, C10–C13, FB1, R4, L1 and the tracks between
them.

### 5.2 How deep a free ring a through via needs, and how deep it is today

`s1_ring.py` (measured, correct clearance loaded) marches outward along each live pad's own escape
axis and asks, at every 0.02 mm, whether a **0.60/0.30** via would be legal on all four layers.
"61" is the count of U10 pads carrying a firm net on the shipped board (the footprint carries 90 pad
items: 80 perimeter + exposed pad + 9 thermal-via pads); the netlist counts the same part as 67 netted
pins of 81 because it lists no thermal-via pads.

| result | value |
|---|---|
| 17 non-through vias legal **in place** at 0.60/0.30 | **0 of 17** (worst **−0.650 mm**, binding item FB1.2 `/3V3_ADC` pad; best **−0.119 mm**, `/SENS_SCLK` against a 350 µm via) |
| U10 pads with a legal 0.60/0.30 via site on their own axis within 3.0 mm | **13 of 61** |
| depth beyond the pad tip where that site appears | min **0.460**, **median 1.160**, max **2.760 mm** |
| U10 pads with **no** legal site within 3.0 mm | **48 of 61** |
| by side (median depth, pads that have a site at all) | N **0.520** (n=3) · E **2.280** (n=4) · S **1.080** (n=6) · **W: 0 of its pads have any legal site within 3.0 mm** |

Read it plainly: **the ring is not a 0.1 mm problem, it is a 1–3 mm problem.** The east side has the
deepest median (2.28 mm), the west side has **no** legal site at all, and 48 of 61 pads cannot host a
netclass through via within 3 mm of the pad tip, because the decoupling ring and its tracks sit
exactly where the escape has to go.

### 5.3 The mm, and the money

Target ring depth, from the same arithmetic as §2: the via can sit **0.301 mm beyond the neighbouring
pad tip** (diagonal clearance `√(0.425² − 0.300²) = 0.301`) and then needs its own 0.30 mm radius plus
0.125 mm clearance, i.e. **copper-free out to 0.726 mm beyond the pad tips** for a single row, and
**1.451 mm** for the staggered second row a 0.4 mm pitch fan-out requires. The measured values in
§5.2 (1.16 mm median, 2.76 mm maximum) sit above that floor because the real track/component copper
occupies the lane, not because the geometry is wrong.

Area is charged **per side** (`10.70 mm land span × depth`), because the ring is only needed where
each side's vias escape — a full square annulus over-counts the corners:

| ring depth | extra copper-free area, per side | share of the 14,000 mm² board | PCBWay delta | JLCPCB delta (at $70.6/m²) |
|---|---|---:|---:|---:|
| **0.726 mm** — single-row geometric floor | **7.8 mm²** | 0.06 % | **$0** | **$0.0006** |
| **1.16 mm** — measured median need | **12.4 mm²** | 0.09 % | **$0** | **$0.0009** |
| **2.76 mm** — measured maximum (S side) | **29.5 mm²** | 0.21 % | **$0** | **$0.0021** |
| *if the whole ring is cleared at 1.16 mm (annulus, over-count)* | *55.0 mm²* | *0.39 %* | *$0* | *$0.0039* |

Unit check, because it is the easy place to be wrong: 1 m² = 10⁶ mm², so 29.5 mm² = 2.95 × 10⁻⁵ m²,
and 2.95 × 10⁻⁵ × $70.6/m² = **$0.0021**. Growth at this scale is **sub-cent at JLCPCB and $0.00 at
PCBWay**.

**A 140×100 board is already inside PCBWay's 150×100 price tier, so growing it by up to 10 mm of
width costs exactly $0 there.** At JLCPCB's published area rate it costs cents. Growth is
therefore **free in fab money and expensive in engineering**: it moves the 20 ring footprints and
re-draws their tracks — the same 25–40 h the re-fanout already costs, with **0 net changes and 0
firmware changes**, which is the whole reason to prefer it to a swap.

**Airframe envelope: NOT RECORDED.** The repo contains no dimension for the main-board mounting
envelope. The only airframe statement is a failure: `docs/acceptance/independent_review.md:15` —
"the fuselage battery-bay shell misses its reserved envelope". There is no mm figure to test a
150×100 outline against, so **whether a grown board fits the airframe cannot be answered from this
repo** — quote it from CAD or measure it, do not assume it.

## 6. The nominal-fee angle — ranked by value per dollar

1. **7th actuator channel — $0, do it regardless of every other decision.** Pad 49 is
   `GPIO40/ADC0`, **no-connect**, one of 8 spare GPIO on the part already fitted. The programme
   already records the need: "seven effectors exceed six outputs"
   (`docs/acceptance/independent_review.md:15`). No package, no pitch, no fab money — firmware only.
2. **Native FDCAN — free *if* you swap.** The board carries an external **MCP2518FD + TCAN3413**
   because RP2354B has no CAN controller (`REV_B_ARCHITECTURE.md`). H723/H743 carry 2× FDCAN
   (datasheet), so a swap deletes one IC and one SPI bus. Value: one fewer part and one fewer failure
   mode; cost: part of the same schematic change, so **only worth it inside a swap you were doing anyway**.
3. **More compute — the fee is the swap, not the part.** Roughly 3–5× the RP2354B's dual M33
   (estimate from core class, not benchmarked).
   But the price is 53 net remaps + 20 footprints + a firmware rewrite from absent source. **Rank 3,
   because the software bill is unbounded and the silicon bill is not.**
4. **Thermal — free with the swap, not worth a spin alone.** The QFN-80's 3.4 mm exposed pad becomes
   6.9 mm on LQFP-100. Real improvement, zero incremental cost, zero reason to spin by itself.

**The nominal-fee answer, bluntly:** the fee that buys performance here is **software**, and there is
no software in the repo to buy it with. The only genuinely nominal-fee upgrade is #1 at **$0**.

## 7. Recommendation — one sentence

**Do not swap: grow the ring (a 0.73–2.76 mm copper-free lane, 7.8–29.5 mm² per side, $0 at PCBWay
because 140×100 already prices as 150×100) and keep the RP2354B, because the swap saves $0 in fab
money, every 0.5 mm LQFP still fails the 0.60/0.30 lane by 0.075 mm, and the only pitch-legal
alternative is ~30–40× slower with no firmware in the repo to port — and spend the free win on pad 49
for the 7th actuator.**

## 8. Provenance and limits

* **Measured here (this run):** board outline/area, U10 land pattern, pad/pitch, 53 nets, 40 GPIO,
  the three package land patterns, ring geometry. Tools: `pcbnew` KiCad 9.0.7 + `vgeom.py`; scripts
  `work/s0_dump.py`, `work/s1_ring.py`, `work/s2_packages.py`; outputs `work/ring.json`,
  `work/packages.json`.
* **Carried from prior evidence (not re-derived):** the 0.425 mm need and its calibration, the
  20-footprint collision set, 25–40 h effort, the 17-via census, PCBWay standard lead time.
* **Fetched from the web this run:** PCBWay $116 and $48 tier pages, JLCPCB $70.6/m² article,
  element14 package/price listings for the three parts.
* **Unknown / not quotable:** firmware effort (no source exists — human must scope); HDI price at
  either fab (quote-gated); JLCPCB checkout total; **part prices** (distributor listings returned
  stock, not price, for these parts — no part price is invented here); airframe envelope (not in repo).
* **A failed instrument, recorded:** the first ring run loaded the board without its `.kicad_pro`
  companion and silently used clearance **0.000** instead of 0.125, inflating every margin by
  0.125 mm. Caught by asserting the loaded rule value; the numbers quoted are from the re-run.