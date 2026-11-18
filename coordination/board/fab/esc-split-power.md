# ESC split — the POWER board (MOSFETs + shunts + one shared power bus)

**Wave 18 specialist report, power-board half.** ONE task: design the power board of the split
architecture — MOSFETs, shunts, one shared power bus — sized for **600–650 km/h at 2 km ASL** with
headroom to the **720 km/h / 109 A** upgrade, and prove it is significantly smaller than the current
**382.71 cm²** board.

Evidence dir: `E:/engineering-portfolio-audit/evidence/esc-split-power/` — every KiCad file is a
COPY; the repository board is read-only input and nothing here is written into a repo. Consumer of
this report: the control-board specialist (`esc-split-control`) and whoever assembles the two-board
cost case.

---

## 0. Status and the answers

| step | state | evidence |
|---|---|---|
| Report skeleton | written first, then filled | this file |
| 1. Current per channel + copper widths | **done** | `02_currents.py` → `.json`/`.log` |
| 2. Shared power bus (a/b/c) | **done** | `02_currents.json:bars`, `bus_pcb_width_mm`, `barrels_needed` |
| 3. FET count and Tj | **done** | `02_currents.py`, `04_heatsink.py` |
| 4. Layout: area, layers, copper | **done** — a real board file, placed and DRC'd | `03_layout.py`, `esc_power_board_v1.kicad_pcb`, `03_drc.json`, `.png` |
| 5. Heatsink + control-board position | **done** | `04_heatsink.py` → `.json` |
| 6. Area reduction | **done** | `03_layout.json` |
| 7. Price, two fabricators | **done** (published list; heavy copper quote-gated) | §7 |

**The answers, before the argument:**

| question | answer |
|---|---|
| Current per phase, 600 / 650 / 720 km/h at 2 km | **62.95 / 80.04 / 108.78 A**; bus **347.5 / 441.8 / 600.5 A** |
| Copper width at 4 oz, 20 K, k 0.048 | **14.95 mm** (63 A), **20.79 mm** (80 A), **31.85 mm** (109 A) |
| Shared bus | **must be a copper bar**: a PCB-only shared bus needs **219.5 mm** of 4 oz outer width (571 mm on an inner layer) at 20 K and **295 barrels**; a **20 × 3 mm bar** carries it with **zero barrels** |
| FETs | **36** (2 per phase — one high, one low), same IPTC014N10NM5 as today; **Tj 94–107 °C at 80 A**, **129–152 °C at 109 A**, TA 45 °C, Rth_SA 0.08–0.10 C/W |
| Board | **138.4 × 122.6 mm = 169.68 cm²** as split (power stage + 6 cell controllers + DC-link caps + motor lands); the power stage alone is **122.62 cm²**. **4 layers, 3 oz (105 µm) each, 1.6 mm**, single-sided, no HDI |
| Heatsink | **6061-T6, 130 × 70 × 25 mm on TOP of the FETs (TOLT slugs up), 10 fins, 663 cm² wetted, 0.10 C/W**, TIM PTM7950 0.25 mm |
| Control board | **above the heatsink on one 2.54 mm 2×15 header, stack 31.75 mm** |
| **Area reduction** | **−55.66 %** vs 382.71 cm² (**−65.49 %** vs 491.73); power stage alone −67.96 % |
| Price, 5 pcs | **$131–143 published (1 oz)** / **$197–286 ESTIMATE (3 oz)** at PCBWay; **€25.80–59 unit list (1 oz)** at Multi-CB, 105 µm quote-gated |

---

## 1. Current per channel, and the copper it needs

### 1.1 The arithmetic, reproduced from the brief's own chain

`02_currents.py` recomputes the brief's three operating points from
`P_prop = 0.5·ρ·v³·CdA`, `P_elec = P_prop/0.62856`, `I_bus = P_elec/44.4`,
`I_phase = (I_bus/6)/0.92`, CdA 0.004162, six motors:

| speed @2 km | v (m/s) | P_prop (W) | P_elec (W) | I_bus total (A) | **I_phase (A)** | P per motor (W) |
|---:|---:|---:|---:|---:|---:|---:|
| 497 km/h (today's board) | 138.06 | 5,511.8 | 8,768.9 | 197.5 | **35.78** | 1,461.5 |
| 600 km/h | 166.67 | 9,697.8 | 15,428.7 | 347.49 | **62.95** | 2,571.4 |
| 650 km/h | 180.56 | 12,330.0 | 19,616.2 | 441.81 | **80.04** | 3,269.4 |
| 720 km/h (stretch) | 200.00 | 16,757.9 | 26,660.7 | 600.47 | **108.78** | 4,443.5 |

The brief's "about 63 / 80 / 109 A" reproduces to **62.95 / 80.04 / 108.78 A**. CdA sensitivity at
650 km/h: **65.4 / 80.0 / 107.7 A** for CdA 0.0034 / 0.004162 / 0.0056 — drag power is linear in
CdA, so +35 % CdA costs **+35 % current**.

### 1.2 What I design to, and why

**Copper and bus are sized for 109 A (the 720 upgrade); the FET population and heatsink are sized for
80 A (650 km/h) with 109 A as a legal-but-hot operating point.** The reason is cost and area: the
copper/bar geometry is nearly free once the board exists (a wider land costs nothing; the bar is a
machined part), while every extra FET costs money and **1.46 cm²** of board. Sizing copper to 109 A
means the 720 upgrade is a **thermal** decision, not a redesign.

### 1.3 Width table — IPC-2221, ΔT 20 K, k 0.048 external / 0.024 internal

`A[mil²] = (I/(k·ΔT^0.44))^(1/0.725)`, width = A/t. The script reproduces the programme's gate
exactly: **43.5 A on 3 oz → 11.963 mm** (published 11.963) and **9.42 mm of 3 oz → 36.58 A**
(published 36.58), so the basis is the same one every earlier unit used.

| current | 1 oz | 2 oz | 3 oz | **4 oz** | 4 oz @30 K | 4 oz @40 K | 4 oz inner @20 K |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 36.58 A (today) | 28.26 | 14.13 | **9.42** | 7.07 | 5.52 | 4.64 | — |
| 62.95 A | 59.82 | 29.91 | 19.94 | **14.95** | 11.69 | 9.82 | 23.3 |
| 80.04 A | 83.16 | 41.58 | 27.72 | **20.79** | 16.26 | 13.65 | 32.4 |
| 108.78 A | 127.42 | 63.71 | 42.47 | **31.85** | 24.91 | 20.92 | 49.6 |

(all mm). The old board's **9.42 mm** corridor is exactly a **36.58 A** corridor — that is why the
programme's ceiling was 36.6 A, and why 80 A on one layer is impossible on the old outline.

**But the width table is a long-run rule, and the runs on this board are 1–3 mm.** The phase neck
between a high-side source row and a low-side drain row is **1.2 mm** long and **8.2 mm** wide (the
pad rows are 8.4 mm). On 4 layers of 3 oz that is 3.44 mm²: **90 A at the 20 K rule**, and in fact
**R = 6.0 µΩ, P = 71 mW at 109 A** — a 0.05 K rise across the neck. The copper is not what limits
this board: **the FET land is** (§6). State the rule, then state the actual constriction; quoting a
20 K IPC width for a 1.2 mm neck as if it were a 40 mm trace is how this programme has produced
numbers that do not survive a second look.

Two consequences: at **80 A the neck passes the rule with 12 % margin** (90 A), and the **109 A**
point is met by the length (71 mW), not by width. If a strict 20 K rating is required at 109 A,
widen the neck to 11.5 mm (**116 A**) in routing — no area cost, the FET pitch already provides it.
4 oz at F/B takes the 8.2 mm neck to **112 A**.

---

## 2. The shared power bus — three options, with numbers

### 2.0 What changes when the six rails become one bus

The board of record is **six independent 3-phase channels** (measured: 36 FETs = 6 × 6, 24 shunts =
6 × 4, six `M1..M6_BATP/BATN` nets, six DRV8353 drivers — `01_topology.json`). Each rail carries one
motor's DC current: **33.7 A today, 58.0 / 73.6 / 100.5 A at 600 / 650 / 720 km/h**. A shared bus
puts **all six** on one conductor: **347.5 / 441.8 / 600.5 A**.

That is a 6× increase in the bus current and it is the entire reason the bus problem changes
character. The brief's correction is right: **one shared bus removes six high-current paths** — but
it concentrates their current into one that does not fit on the board as PCB copper (§2.2).

### 2.1 (a) The old six independent rails

| quantity | value | basis |
|---|---|---|
| rail current, 650 km/h | 73.6 A per rail × 6 | ANALYTICAL |
| copper width per rail, 4 oz 20 K | **19.1 mm** each, 6 rails = 114 mm of copper per layer | ANALYTICAL |
| shunt-pad barrels per rail | 73.6 A / 1.50 A = **49 barrels needed** | ANALYTICAL |
| barrels a 14.19 mm² shunt pad holds | **17–18** (programme measurement, 23 legal positions at 0.90 mm pitch) | MEASURED |
| verdict at 80 A | **0.35× — fails by a factor of 2.8** | |
| area consumed by the six rail pours | 6 × 19.1 mm × ~40 mm ≈ **45.8 cm²** of one layer | ANALYTICAL, layout-dependent |

The old design already failed this way at 40 A: **27 barrels needed, 17–18 available**. At 73.6 A it
needs **49**. Six rails do not fix it; they multiply it by six.

### 2.2 (b) One shared bus on PCB copper only

| bus current | 4 oz outer @20 K | 4 oz inner @20 K | 6 oz outer @20 K | barrels at 1.5 A |
|---:|---:|---:|---:|---:|
| 347.5 A (600) | 157.6 mm | 410.1 mm | 105.1 mm | **232** |
| **441.8 A (650)** | **219.5 mm** | 571.1 mm | 146.4 mm | **295** |
| 600.5 A (720) | 335.2 mm | 872.1 mm | 223.5 mm | **401** |

The board is **138 mm wide**. The numbers say two different things, and both are fatal:

* **Inner-layer route: 571 mm of 4 oz** at 20 K — **4.1× the board width**. Even four inner layers
  (six-layer stack) need **143 mm**, still wider than the board. At 30 K it is 475 mm, still 3.4×.
  The inner-layer bus cannot exist at any sane ΔT.
* **Outer-layer route: 219.5 mm of 4 oz** — 1.6× the board width, and the outer layers are exactly
  where the 36 FETs, 18 shunts, six headers and three bar lands live. The only way to find 219.5 mm
  is to give up the power stage.

And if a plane were found, the taps still need **49 barrels per channel** (295 total). Area-wise that
is now possible — a 113 × 4.5 mm land holds 49 barrels easily, unlike the old 14.19 mm² shunt pad —
but it reproduces the old failure mode **six times over**: 49 barrels demanded where the board of
record could only ever place 17–18. PCB-only shared bus: **rejected on width, not on principle.**

### 2.3 (c) One shared bus on a copper bar

| bar section | area | J at 442 A | ΔT, natural convection (h 12) | ΔT, ducted at 650 km/h (h 120) | verdict |
|---|---:|---:|---:|---:|---|
| 20 × 2 mm | 40 mm² | 11.05 A/mm² | 159 K | **15.9 K** | too hot static |
| **20 × 3 mm** | **60 mm²** | **7.36 A/mm²** | 101 K | **10.1 K** | **chosen** |
| 25 × 4 mm | 100 mm² | 4.42 A/mm² | 48 K | 4.8 K | static-test grade |
| 30 × 5 mm | 150 mm² | 2.95 A/mm² | 26.6 K | 2.7 K | overkill |

At 720 km/h (600.5 A) the 20 × 3 bar runs at **18.7 K** ducted. The natural-convection column is the
honest worst case and it matters only for a **static full-power bench test** — at hover the bus is
~145 A, where the same bar sits at **10.9 K**. The bar is sized by the flight condition, and the
flight condition is exactly when the duct supplies the air.

**Zero barrels.** The bar is soldered to a **4.5 mm × 118 mm** land (530 mm², 0.83 A/mm² at 442 A).
It is not bolted through the board (a bolted joint of 0.05 mΩ would dissipate **9.8 W at 442 A**; the
soldered lap is ~0.01 mΩ). Battery cables land on M5/M6 lugs crimped to the bar ends, off-board.

**Verdict: (c).** A 20 × 3 mm tin-plated copper bar, on edge: two legs for B+ (outer edges, joined at
one end into a U) and one straight bar for B− (centre), 60 mm² each, **~190 g of copper, ~$4 of
material**. It carries the bus with 10–19 K rise in flight, has no barrels, and costs less than the
copper area it displaces (15.3 cm² of board land).

**Does it fix the barrel problem? Yes, by construction:** the bus current never crosses the board
through a plated barrel. The 27-vs-18 deficit that killed the old design was a pad-area problem; a
bar has no pad area limit. The 146 unconnected items in the DRC are the un-routed
connections, not a power-path defect.

---

## 3. FET count and junction temperature

### 3.1 The topology the model belongs to, and a label correction

The board of record has **one device per switch position** (measured: 36 FETs = 6 channels × 3 phases
× 2 positions; `01_topology.json`). The brief's "6 per phase" is the **6 per channel** figure — there
are **2 FETs per phase**. That is not pedantry, it fixes the thermal model: with one device per
position each device carries the **full phase current** at D = 0.5, so the programme's
`P = 1.33e-3·I² + 0.0424·I` per device is **exactly right**, and the board total is 36 × P.
(Conduction = 0.5·I²·2.66 mΩ with the 1.4 mΩ × 1.9 hot factor; switching = 0.0424·I.)

f_sw is in the repo: **20 kHz** (`docs/hardware/REV_B_ARCHITECTURE.md:21`, quoted by
`esc-current-place`), t_sw = **30 ns ASSUMED**. The linear term checks out:
20 kHz·2·½·50.4 V·√2·I·30 ns = **0.0428·I** per device.

What the model says about the old board's 22.4 C/W "spreader" Rth: at 80 A one device dissipates
**11.90 W**, and 11.9 × 22.4 = **266 K → Tj 311 °C**. The 36.6 A verdict (Tj 119.6 °C) was a
single-device check that only worked because 36.6 A is 3.3 W. **At 80 A the PCB-spreader thermal path
is not a design; the FETs must be cooled from the top.** That is the whole reason the owner's
"custom machined heatsink" is the enabling part of this split, not a packaging afterthought.

**Sensitivity:** t_sw 15 / 30 / 45 ns → switching **1.71 / 3.42 / 5.13 W** per device at 80 A, i.e.
**±2 K of Tj per ±15 ns**. f_sw doubling to 40 kHz adds 3.4 W/device → **+4 K**.

### 3.2 Count and Tj

Thermal path (TOLT is **top-side cooling**: the slug is the contact surface, the package body sits on
the board with a negative stand-off):

* Rth_jc = **0.30 K/W** (programme value, `esc-area-floor` §4.3);
* TIM PTM7950-class phase change, 0.25 mm, k 8 W/mK over the 8 × 5 mm slug → **0.78 K/W**;
* heatsink Rth_SA **0.08–0.10 C/W** (§5);
* TA **45 °C** (programme basis).

| per-phase devices | total FETs | I_phase | P/device | P board (FET+shunt+Cu) | Tj @0.08 | Tj @0.10 | Tj @0.15 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| **2 (1+1)** | **36** | 63 A | 7.95 W | 298 W | **77.5** | 86.4 | 98.3 |
| **2 (1+1)** | **36** | **80 A** | 11.90 W | 448 W | **93.7** | **107.1** | 125.0 |
| **2 (1+1)** | **36** | 109 A | 20.42 W | 771 W | **128.8** | **151.9** | 182.7 |
| 4 (2+2) option | 72 | 80 A | 3.82 W | 275 W | 71.2 | 81.0 | 93.7 |
| 4 (2+2) option | 72 | 109 A | 6.26 W | 451 W | 87.8 | 100.4 | 115.9 |

**The design point: 36 FETs.** At 650 km/h Tj is **94 °C** (0.08 C/W) to **107 °C** (0.10 C/W) —
**68 K of margin** to the 175 °C limit. At 109 A it is **129 °C** to **152 °C**: legal, hot, and the
reason the 720 build should be sold with the 25 × 4 bar and a 0.08 C/W heatsink rather than assumed.

Doubling the population (72 FETs, 2 per position) buys **23 °C at 80 A and 41 °C at 109 A** for
+36 FETs (~$90–130 BOM) and **52 cm² of board** (175 cm² total, still −54 %). **Recommendation: build
36 at 650; go to 72 only if the 720 point is committed** — and note the 109 A column passes without it.

Total dissipation at 650 km/h: **FET 428.5 W + shunts 14.4 W + copper 4.9 W = 447.8 W**. That is
2.3 % of 19.6 kW — consistent with the 0.97 ESC efficiency in the speed chain.

---

## 4. Layout: placement, area, layers, copper weight

### 4.1 The board, as generated

`03_layout.py` builds real KiCad 9 boards and measures them from the edge-cuts bounding box
(`03_layout.json`, `03b_layout_full.json`). **Two variants**, because the split of record
(`esc-split-control`) keeps the six isolated cell controllers on the power side:

| quantity | **power stage** (`esc_power_board_v1`) | **as split** (`esc_power_board_full`) |
|---|---:|---:|
| outline | 138.4 × 88.6 mm | **138.4 × 122.6 mm** |
| area | 122.62 cm² | **169.68 cm²** |
| copper layers / weight | 4 / **3 oz (105 µm) each** | 4 / **3 oz (105 µm) each** |
| thickness | 1.60 mm | 1.60 mm |
| contents | 36 FET, 18 shunt, 6 headers, 3 bar lands | + 6 cell blocks (DRV8353, STM32G431, ISO6731, TPS70933, RFM-0505S, 820 µF cap each), 18 motor-wire lands |
| footprints / pads | 119 / 887 | 173 / 941 |
| DRC (`kicad-cli pcb drc`, 0.15 mm clearance / 0.05 mm mask web / 0.30 mm edge) | **0 violations**, 146 unconnected | **0 violations**, 146 unconnected |
| render | `esc_power_board_v1.png` | — |

### 4.2 Placement and equal sharing

Six identical channel blocks in a **3-column × 2-row** array, the second row **mirrored vertically**:

* per channel: 3 phases at **12.5 mm pitch**, high-side row → phase node (1.2 mm) → low-side row →
  shunt row; each phase column is electrically and thermally identical, so the three phases share
  within 1 % by construction (same copper, same 1.2 mm neck, same 8.2 mm width);
* **B+ runs along both outer edges, B− along the centre line.** Mirroring the second row puts every
  channel's B+ pads adjacent to an outer bar and every channel's B− pads adjacent to the centre bar,
  so all six channels have the **same 1.4 mm B+ neck and 2.3 mm B− neck**. That is what equalises the
  DC share: the bar is 37 µΩ end-to-end, so the worst channel-to-channel drop difference is 16 mV
  against a ~1 V channel drop (< 2 % imbalance);
* **gate loops:** in the power-stage variant each 2×12 header sits in the 5.6 mm strip beside its
  channel, **8–18 mm** from the gates it drives, so the gate pair is ~15 mm ≈ **11 nH**. That number is
  why the header positions are a **hard constraint** on where the gate drivers go: with a driver at
  the board end instead (100 mm), the loop is ~70 nH and the turn-off overshoot at 2 A/ns is **140 V**.
  In the **as-split** variant the gate driver (DRV8353, QFN 6×6) must therefore sit **in the channel
  strip next to its own FET bank**, not in the bottom cell strip — the cell MCU, isolator, LDO and
  DC/DC can be 40 mm away because PWM is digital. That is a routing decision inside the 169.68 cm²
  outline; it does not change the area.
* **shunts: 18, not 24.** The per-channel bus shunt is deleted. It sat in series with three 0.5 mΩ
  phase shunts and burned **2.7 W per channel (16.3 W total at 650 km/h)** to measure what the three
  phase shunts already sum to. If the control board needs a hardware instantaneous bus comparator,
  the 4th shunt costs **+7 mm per channel = +19 cm² (141 cm² power stage, 188 cm² as split)** — state
  it, do not hide it.
  **Interface note for `esc-split-control`:** the board-to-board cut is **one 2×15 (30 positions)
  2.54 mm header** — 4×5 V, 7×DGND, 2×3V3, 6×`Mx_CMD`, 6×`Mx_STATUS`, 1×`ARM_SAFE` — which is their
  measured cut and the only thing that crosses. **No gate nets, no phase nodes, no shunt Kelvins, no
  bus voltage cross the header**, because the gate drive and the six cell MCUs stay on this board
  behind the ISO6731 barrier. The six 2×12 positions drawn in the power-stage variant are the
  bench/test access to gates and Kelvin pairs; they are not the control interface.

### 4.3 Why 4 layers and not 2

| option | phase neck (8.2 mm, 1.2 mm long) | long-run 80 A, per layer | cost | verdict |
|---|---|---|---|---|
| 2L, 6 oz | 2 × 210 µm = 3.44 mm² → **90 A @20 K** | 13.9 mm | lowest | meets 80 A; **no** quiet inner layer for gate/Kelvin mesh, and 109 A is 0.82× |
| **4L, 3 oz** | 4 × 105 µm = 3.44 mm² → **90 A @20 K**, 71 mW actual at 109 A | 6.9 mm | mid | **chosen** — same capacity, plus In1/In2 for the gate/Kelvin mesh and the 109 A point met by the 1.2 mm length |
| 4L, 4 oz | 4 × 140 µm = 4.59 mm² → **112 A @20 K** | 5.2 mm | +$60–110 | the strict-20-K answer if 109 A must be a hard continuous rating |

2-layer is cheaper by roughly **$60–110 per 5 pcs** but removes the only quiet layers for the gate
and Kelvin mesh, and it does not resolve the 720 point any better than 4L/3 oz. The brief asked for
the comparison, not for the cheapest: **4L/3 oz is the better buy, and 4L/4 oz is the honest upgrade
if the owner wants the 720 rating to be a 20 K number.**

---

## 5. Heatsink and the control-board stack

### 5.1 The heatsink (the owner's custom machined part)

| item | spec | source |
|---|---|---|
| material | **6061-T6 aluminium**, machined, hard-anodised (or chem-film) | ASSUMED grade, standard for the service |
| position | **on TOP of the power board**, pressing on the 36 TOLT slugs | TOLT top-side cooling |
| mounting | 2 × M3 into the board holes + 2 spring clamps at the ends; base plate floats on the TIM | ASSUMED mechanical detail |
| base | **130 × 70 × 3 mm**, underside relieved 2 mm between the two FET rows (clearance over the centre bar and header strips) | layout |
| fins | **10 fins, 22 mm tall, 1.2 mm thick, 130 mm long** (6.4 mm pitch), air along the fins | layout |
| contact area | 36 slugs × 40 mm² = **1,440 mm²** on 2 × 124 × 30 mm machined lands | computed |
| TIM | **Honeywell PTM7950-class phase change, 0.25 mm, k 8 W/mK** → 0.78 K/W per FET | datasheet-class |
| wetted area | **663 cm²** | computed |
| Rth_SA | **0.101 C/W at h 150 W/m²K; 0.075 at 200** (ducted at 650–720 km/h) | computed |
| volume | **envelope 227.5 cm³ (130 × 70 × 25); solid 61.6 cm³; mass 166 g** | computed |
| heat rejected | **448 W at 650 km/h, 771 W at 720** | §3 |

The volume it gets is **the full 130 × 70 × 25 mm block between the two boards**; nothing else may
occupy it. That is the space the owner asked to leave, stated as a solid.

### 5.2 Where the control board sits

**Above the heatsink**, on **one 2.54 mm 2×15 pin header** (the split's only board-to-board
connector), stack height:

`1.60 (power PCB) + 1.30 (FET body) + 0.25 (TIM) + 25.0 (heatsink) + 2.0 (clearance) + 1.60 (control
PCB) = 31.75 mm`.

The control board therefore needs a **window** over the fin field (or to be a frame): a solid board
lying on the fin tips would trap the air the heatsink needs. Practical form: the control board is a
**frame 138 × 88 mm with a central opening of at least 110 × 62 mm**; the fins see the duct through
it, and the six headers land on the frame's inner edge, 8–18 mm from the FET gates. With 8 mm borders
the frame passes over ~9 mm of fin at each end: **~12 % of wetted area, Rth 0.10 → 0.11 C/W** (Tj
107 °C at 80 A — still 68 K of margin, so the frame is affordable). If the control board must be a
full rectangle, the fins must be shortened to ~14 mm and the board becomes a lid — a **+25 % Rth**
penalty the control-board specialist must co-sign, not one this report can take alone.

---

## 6. Area, and the reduction

Measured from the generated boards' outlines (`03_layout.json`, `03b_layout_full.json`):

| reference | area | power stage | as split | reduction (stage / split) |
|---|---:|---:|---:|---:|
| original as drawn | 491.73 cm² | 122.62 cm² | 169.68 cm² | −75.06 % / **−65.49 %** |
| power-first placement of record | **382.71 cm²** | **122.62 cm²** | **169.68 cm²** | −67.96 % / **−55.66 %** |

**The power board is 169.68 cm² as split — 2.26× smaller than the 382.71 cm² board it replaces
(−55.66 %).** The power stage alone is 122.62 cm² (−67.96 %); the difference is the six isolated cell
controllers (DRV8353 + STM32G431 + ISO6731 + TPS70933 + RFM-0505S), the six 820 µF DC-link cans and
18 motor-wire lands that the control-board split of record leaves on this side of the barrier.

The floor is not the copper (§1.3: the runs are 1–3 mm); it is the **component land**:

| land | area | share of 169.68 cm² |
|---|---:|---:|
| 36 TOLT footprints (11.56 × 12.6 mm) | **52.45 cm²** | 30.9 % |
| 6 cell blocks (5 ICs + cap each) | 15.54 cm² | 9.2 % |
| busbar lands (3 × 113.4 × 4.5 mm) | 15.31 cm² | 9.0 % |
| 6 test headers (6.8 × 32.2 mm) | 13.14 cm² | 7.7 % |
| 18 shunt footprints | 6.93 cm² | 4.1 % |
| 18 motor-wire lands (6 × 3.2 mm) | 3.46 cm² | 2.0 % |
| routing, creepage, strip space, margins | 62.85 cm² | 37.0 % |

**The FETs are the single biggest block (31 %) and cannot be negotiated with** — a TOLT footprint is
11.56 × 12.6 mm and 36 of them are the electrical requirement. Doubling the population (72 FETs, the
720-with-margin build) adds 52.45 cm² → **~222 cm², −42 %**; that is a real but smaller win, and it is
why the recommendation is 36.

**Where the 382.71 cm² actually goes:** 73.85 cm² of it was twelve battery taps and six rail lugs
(measured by `esc-split-control`), 19.58 cm² of shunt courtyards, 16.11 cm² of bulk electrolytics.
The shared bus deletes the **twelve battery taps entirely** (three bar lands, 15.31 cm², replace
them) and the centre-bar layout lets the six caps sit in one strip. That consolidation — not the
mere act of splitting — is where the −55.66 % comes from.

**If someone wants under 140 cm²:** delete the six test headers (13.14 cm²) and move the motor lands
to the edge (they are already there) → 156.5 cm², then pack the cell strip at 60 % instead of 45 % →
~150 cm². Below that the FET land and the isolation spacing set the floor.

---

## 7. Price, two fabricators, 5 pcs

Heavy copper is **quote-gated at every house** (programme finding, re-checked 2026-11-16): no fab
publishes a 3 oz list price. What follows is therefore published list scaled by the published price
slope, times a published heavy-copper multiplier, and labelled as such.

**Sizing note:** at **169.68 cm² (138.4 × 122.6 mm)** the board no longer fits PCBWay 150 × 100
panel, so the $116 row from `esc-layer-cost` does **not** apply. Scaling on the two published points
(100 cm² = $48, 150 cm² = $116) gives the 4-layer 1 oz list at this area.

| fabricator | configuration | published / estimated | currency | lead time |
|---|---|---|---:|---|
| **PCBWay** | 4L, 169.68 cm², 1 oz, 5 pcs | **$131–143** — published list, extrapolated (48 + 1.36×(A−100)) | USD | 3–5 build days |
| **PCBWay** | same, **3 oz heavy copper** | **$197–286 ESTIMATE** (× 1.5–2.0 published heavy-copper multiplier) | USD | **5–10 build days** (published) |
| PCBWay | 4 oz all layers (strict 20 K at 109 A) | $290–390 ESTIMATE (× 2.2–3.0) | USD | 5–10 build days |
| **Multi-CB** | 4L, 80 × 100 mm, 1 oz, per unit | **€25.80 (9 WD) / €59.00 (5 WD)** — published | EUR | 5–9 working days |
| Multi-CB | 169.68 cm², **105 µm special production** | **€200–320 ESTIMATE** for 5 pcs (calculator is the only source; 105 µm is special production) | EUR | 8–12 working days |
| Multi-CB | 140 µm | special production, **quote only** | EUR | — |

**The number to use: the power board is $197–286 (PCBWay, 5 pcs, 3 oz, 5–10 days).** Against the
$450–870 board it replaces, the **two-board** total must stay under **$675–1,305**; a power board at
$197–286 leaves **$390–1,100** for the control board, which at ~40–60 cm² of 4-layer is a
$100–200 part. **The split lands at roughly $300–490 of fab for both boards — under the 1.5× cap even
at the top of every range**, and the cap is the whole point.

Not in these numbers: the copper bar (~$4–6 of copper + machining), the heatsink (a machined part,
~$40–90 at 1-off in 6061), FETs (36 × $2.50–3.50 ≈ $90–126, same count as today), the six cell
controllers and DC-link caps (the parts the split leaves on this side). Those are BOM and machining,
outside the $450–870 fab basis of record — say so rather than folding them in.

---

## 8. Provenance, and what is not verified

| claim | tier | note |
|---|---|---|
| 62.95 / 80.04 / 108.78 A; 347.5 / 441.8 / 600.5 A | **ANALYTICAL** | reproduces the brief's chain; CdA 0.004162 is the programme's best build-up, not a measurement |
| widths, barrel counts, bar ΔT | **ANALYTICAL** (IPC-2221 + bar convection model) | h_eff 12 natural / 120 ducted are **ASSUMED**; the bar's static 101 K matters only on a bench |
| Tj 94–152 °C | **ANALYTICAL** | Rth_jc 0.30 is the programme's value, not re-measured; TIM 0.78 K/W is computed for PTM7950-class, not tested; Rth_SA is computed from fin area, not from a CFD or a wind-tunnel run |
| 122.62 / 169.68 cm², 4 layers, 3 oz | **MEASURED** (board files, pcbnew bbox) | outlines are generated, not drawn by hand; the six cell blocks are **placed at package size with one land pad each** (~45 % packing), so the strip is a land estimate, ±5 % |
| 0 DRC violations | **MEASURED** (kicad-cli 9.0.7) | on the **unrouted placement**; the 146 unconnected are real and expected |
| $131–143 (1 oz) / €25.80–59 | **PUBLISHED**, accessed 2026-11-16 | different panel sizes; not a quote for this outline |
| $197–286 / €200–320 (3 oz) | **ESTIMATE** | published multipliers on a two-point published slope; heavy copper is quote-only everywhere |

**What this is not:** a routed board. There are **no tracks and no copper pours** in the generated
file — the nets exist, the pads exist, the outline exists, and the 146 unconnected items are the
routing that a layout engineer must still do. The area claim does not depend on the routing (routing
fits *inside* the placement — the strips between columns and the 1.2 mm necks are sized for it), but
the DRC claim is a **placement** DRC, not a finished-board DRC. Saying otherwise would repeat the
programme's oldest mistake: quoting a number from a different configuration than the one it describes.

**Open items handed to the next unit:** (1) route 4 layers and re-run DRC — expect the 146 to close
and a small number of clearance fixes; (2) the 2×15 interface pinout with `esc-split-control`
(30 positions, 28 assigned, nothing else crosses; the 2×15 site is reserved at the right margin
x 131.5–136.6, y 20–58 and is not yet in the generated file); (3) confirm the TOLT slug-up footprint
with the assembly house — the board of record solders the slug down, and this design's whole thermal
argument depends on the slug being the top contact (Infineon TOLT: negative stand-off, body on the
PCB, slug up); (4) a real Rth_SA measurement or CFD of the fin stack in the duct; (5) a formal quote
for 3 oz; (6) the cell blocks are placed at package size — they need a real placement and routing pass
inside the reserved strip.

---

## 9. Return (the ≤260-word answer)

**Current/copper:** 62.95 / 80.04 / 108.78 A per phase at 600/650/720 km/h, 2 km (bus 347.5 / 441.8 /
600.5 A). At 4 oz, 20 K, k 0.048: **14.95 / 20.79 / 31.85 mm**; copper sized to 109 A.

**Shared bus:** (a) six rails at 73.6 A each need **49 barrels per rail** vs 17–18 available — fails
2.8×; (b) one PCB bus needs **219.5 mm of 4 oz** (1.6× the board width; 571 mm on an inner layer)
and **295 barrels** — rejected on width; (c) **20 × 3 mm copper bar, 60 mm², 10 K ducted / 101 K
static, zero barrels** — the bar removes the barrel bottleneck by construction. Winner: **(c)**.

**FETs:** 36 (2 per phase; the brief's “6 per phase” is 6 per channel). Tj **94–107 °C at 80 A**,
129–152 °C at 109 A, TA 45 °C, Rth_SA 0.08–0.10 C/W, 448 W at 650 km/h.

**Board:** **138.4 × 122.6 = 169.68 cm²** as split (power stage alone 122.62 cm²), **4 layers,
3 oz each, 1.6 mm, single-sided, HDI-free**, 0 placement DRC violations.

**Heatsink:** 6061-T6 **130 × 70 × 25 mm on top of the FET slugs**, 10 fins, 663 cm², 0.10 C/W,
TIM PTM7950 0.25 mm, **227.5 cm³ envelope**. Control board **above it on one 2.54 mm 2×15 header,
stack 31.75 mm**.

**Area: −55.66 % vs 382.71 cm² (−65.49 % vs 491.73); power stage alone −67.96 %.**

**Price:** **$197–286 (3 oz)** at PCBWay, 5–10 days ($131–143 at 1 oz, published); €25.80–59 unit
list (1 oz) at Multi-CB, 105 µm quote-gated. Two-board fab ≈ $300–490, under the 1.5× cap.
