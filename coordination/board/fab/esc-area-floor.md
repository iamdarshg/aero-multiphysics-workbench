# ESC rev_b — the honest single-sided minimum area

**Unit:** `esc-area-floor` · wave: ESC compaction, owner constraint 2026-11-15
(*compact as much as possible without placing any component on the back*)
**Host:** KiCad 9.0.7, `C:/Program Files/KiCad/9.0/bin/` — `kicad-cli.exe` and the bundled `python.exe` (pcbnew 9.0.7).
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/esc-area-floor/`
**Board examined:** a **copy** of `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb`
→ `esc_rev_b_COPY.kicad_pcb`, sha256 `992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD`.
No repo file was written, no git operation was performed.

---

## VERDICT

| | |
|---|---|
| **FLOOR** | **316 cm²** including a 5 % edge/routing margin (**300.7 cm²** of structure) |
| **as a board** | **177.7 × 177.7 mm** at 1 : 1 — the aspect the airframe's own CAD placeholder uses — or **227 × 139 mm** at today's 1 : 1.63 |
| **today** | 173.950 × 283.080 mm = **492.42 cm²** |
| **necessary** | **300.7 cm² = 61.1 %** of the present board |
| **dead space** | **191.7 cm² = 38.9 %** |
| **shrink available** | **−176.7 cm² (−35.9 %)**, i.e. 492.4 → 316 |
| **150 × 150 mm placeholder** | **UNREACHABLE single-sided.** The floor is 177.7 × 177.7; the repo's own 150 × 150 attempt only closed because it put control parts on B.Cu (`docs/superpowers/specs/2026-08-27-esc-150mm-six-layer-design.md:11`). |

**The single-sentence answer to the owner's constraint:** the back side was never the problem —
**687 of 687 footprints are already on F.Cu** (`01_inventory.log`, `SIDE_CENSUS {'F.Cu': 687}`), so the
single-sided rule is met today. The problem is that 492.4 cm² buys 300.7 cm² of structure, and the
191.7 cm² difference is slack in four measurable places, not mysterious inefficiency.

**And the honest limit on that number:** the floor is set by **copper cross-section for 60 A on 4 oz
(119.2 cm²)** and by **the per-cell control/instrumentation bay (81.6 cm²)** — not by creepage
(6.2 cm²) and not by footprint bounding boxes. Anyone who compacts this board by packing courtyards
tighter has attacked the third-largest term and left the two largest alone.

---

## 1. Current-carrying nets and their currents

### 1.1 The requirement IS stated in the repo — no derivation needed

| quantity | value | source |
|---|---|---|
| battery | 12S LiPo, **50.4 V** max charged | `docs/hardware/REV_B_ARCHITECTURE.md:16` |
| **design current** | **60 A continuous per motor channel** | `REV_B_ARCHITECTURE.md:18` |
| aggregate | 360 A max, by six *external* fused star taps | `REV_B_ARCHITECTURE.md:19` |
| **no PCB trunk** | "No 360 A copper trunk is present on the ESC PCB" | `REV_B_ARCHITECTURE.md:137` |
| 60 A is the *devices'* current | "60 A through each conducting MOSFET path, with six motors capable of 360 A aggregate—not 60 A shared across the board" | `Past_Conversation.md:1470` |
| shunt scaling at 60 A | "60 A signal: 0.6 V from midscale"; "60 A shunt dissipation: 1.8 W" | `REV_B_ARCHITECTURE.md:79,81` |
| 60 A point is 2.664 kW | `44.4 V x 60 A = 2.664 kW` | `FA4119_PROPULSION_DECISION.md:50-56` |
| **it is a BURST, not continuous** | "Burst duration under discussion \| up to 50 s at approximately 2.7 kW; requires test validation" | `FA4119_PROPULSION_DECISION.md:44` |

**So there is a live conflict inside the repo**, and it is material to the floor:

- `REV_B_ARCHITECTURE.md:18` sizes the ESC for **60 A continuous × 6**.
- `FA4119_PROPULSION_DECISION.md:44` sizes the *aircraft* for **2.7 kW for up to 50 s**.
- `REV_B_ARCHITECTURE.md:163-166` itself says the outline is large *because* the channels are treated
  as continuous, and that reducing it needs "a documented duty cycle, lower current, a different
  mechanical busbar/heatsink assembly, or separate per-motor modules".

I compute the floor at the **architecture document's stated 60 A continuous**, because that is the
declared design basis and a floor must respect the declared basis. §5.5 gives the floor at the
50 s-burst reading as a second, clearly-labelled case. **A 50 s burst does not help much** either:
one 14 mm × 0.14 mm × 45 mm conductor holds 88 mm³ of copper = 0.30 J/K, and its own 1.42 W of I²R
gives 4.7 K/s, so 50 s would be a **233 K adiabatic rise** — 50 s is quasi-steady, not transient. The only lever a burst buys is a *lower*
required ΔT margin, which §5.4 quantifies.

### 1.2 The nets, measured on the board

From `01_inventory.log` (pad counts per net) and `04_calc.log` §1:

| class | nets | 60 A? | pads/net |
|---|---|---|---|
| `/M<n>_PHASE_[ABC]` | **18** (6 cells × 3) | **yes** | 19 |
| `/M<n>_BATP` | **6** | **yes** | 42 |
| `/M<n>_BATN` | **6** | **yes** | 80 |
| `/AUX_BATT`, `/DGND`, `/AUX_GND` | 3 | no — mA-level aux | 11 / 90 / 34 |

**30 conductors at 60 A on this board.** No conductor carries 360 A; the six BATP/BATN domains are
separate by design (`REV_B_ARCHITECTURE.md:139` "no `BATN` domains are joined").

> **Population note, stated because it changes what "necessary" means.** The ESC has **six** cells;
> the propulsion record is for a **four**-motor, ~8 kg aircraft (`FA4119_PROPULSION_DECISION.md:8,40,45`).
> Six cells × 60 A = 360 A = 16 kW, which no 8 kg airframe in this repo establishes as an operating
> point. I do **not** exploit that to shrink the floor — the board is a six-channel board and the floor
> is a six-channel floor — but it belongs in front of the owner, because it is the difference between a
> 316 cm² board and a ~215 cm² one.

---

## 2. Copper width for 60 A at 4 oz

### 2.1 Method

IPC-2221 §6.2 external-conductor relation, the curve family that IPC-2152 replaced but which is still
the published closed form:

```
A[mils²] = ( I / (k · ΔT^0.44) )^(1/0.725)          k = 0.048 external, 0.024 internal
w[mm]    = A[mils²] / t[mils] × 0.0254
```

`t = 0.14 mm = 5.512 mil` for the 4 oz outer layers and `0.0525 mm = 2.067 mil` for the 1.5 oz
inners (measured from the stackup block, `AGENT_BOARD.md:36`).

**Stated allowed rise: ΔT = 20 K.** That is the conventional power-board design point and it is
**ASSUMED** — the repo states no copper temperature limit. §5.4 sweeps it 10–30 K so the owner can
pick a different one and read the answer off.

### 2.2 Result (`04_calc.log` §2)

| ΔT | 4 oz external | 1.5 oz internal |
|---|---|---|
| 10 K | 21.29 mm | 147.72 mm |
| 15 K | 16.65 mm | 115.49 mm |
| **20 K** | **13.98 mm** | 96.99 mm |
| 25 K | 12.21 mm | 84.71 mm |
| 30 K | 10.93 mm | 75.83 mm |
| 50 K | 8.02 mm | 55.62 mm |

**Adopted: 13.98 mm of 4 oz copper per 60 A conductor, per net.**

**The consequential finding is in the right-hand column.** A 1.5 oz inner layer needs **97 mm** of width
for the same 60 A — **6.9× wider**, which cannot exist inside a cell. Therefore:

> **The inner layers cannot carry the motor current on this stackup.** `REV_B_ARCHITECTURE.md:141-148`
> assigns In1 to BATP and In2 to the three phase paths. At 1.5 oz that is physically impossible, so
> **both 60 A layers must be the two 4 oz outers (F.Cu and B.Cu)**. This is a stackup/architecture
> correction that follows from the standard, not a preference.

### 2.3 Two independent cross-checks

**(a) First-principles 1-D balance** (`I²ρ/(w·t) = h_eff·(w+2t)·ΔT`, both faces, ρ corrected by
α=0.00393/K). At h_eff = 16 W/m²K it wants 38.5 mm; at 25, 30.8; at 40, 24.3 — **1.7–2.75× the IPC
figure.** The bare-PCB 1-D model is more conservative than IPC, never less, so 13.98 mm is not
optimistic on that axis.

**(b) Loss-budget balance** — the basis that actually applies to a heatsinked board: cap copper loss at
**≤ 10 % of the FET conduction loss**. P_cond(25 °C) = 15.12 W/cell → budget 1.51 W → R ≤ 0.420 mΩ over
a 45 mm path → **w = 13.16 mm**.

**13.98 (IPC) · 13.16 (loss budget) · 24–38 (bare 1-D)** — the two board-realistic methods agree within
**6 %**, and the disagreeing one is the one that ignores the heatsink. **13.98 mm is adopted.**

---

## 3. Creepage and clearance between phases and to the battery side

### 3.1 Voltage

| case | differential | source |
|---|---|---|
| phase ↔ phase, phase ↔ battery, battery ↔ control (steady) | **50.4 V** | `REV_B_ARCHITECTURE.md:16` |
| switch node ↔ ground, TVS-clamped transient | **82.4 V** | `REV_B_ARCHITECTURE.md:157` (SM8S51A max clamp) |

**Both land in the same IPC-2221 row (51–100 V),** which makes the requirement robust to whichever of
the two you call "the voltage".

### 3.2 Standard and spacing

**IPC-2221B Table 6-1** (peak voltage, not rail voltage), 51–100 V row — values confirmed against a
published conversion of the table:

| column | 51–100 V | applies here |
|---|---|---|
| B1 internal conductors | 0.10 mm | inner layers only |
| **B2 external, uncoated** | **0.60 mm** | **governs: this board has bare 4 oz copper** |
| B4 external, permanent polymer (conformal coat) | 0.13 mm | only if the coat is continuous over every gap |

**IEC 60664-1** cross-check at 50.4 V DC, pollution degree 2, overvoltage category II, rated impulse
0.8 kV, material group IIIa (FR-4): clearance **0.20 mm**, creepage **0.60 mm** — the creepage figure
**agrees with IPC-2221 B2 at 0.60 mm**, which is why 0.60 mm is quoted as *the* requirement rather than
a choice.

Sources: <https://indipcb.com/blog/ipc-2221-clearance-spacing> (IPC-2221 Table 6-1 in mm);
<https://www.atlaspcb.com/tools/conductor-spacing-calculator/> and
<https://volteq.io/creepage-clearance> (IEC 60664-1 tables).

### 3.3 What the board actually has, and what that costs

Measured: minimum track width **0.200 / 0.250 mm** (`01_inventory.log`, `SEG_WIDTHS_MM {0.2: 4, 0.25: 150}`),
and **371 pad gaps of exactly 0.2000 mm inside 9 footprints** (`AGENT_BOARD.md:623`).

- 0.2000 mm is **3.0× short** of the 0.60 mm uncoated requirement.
- 0.2000 mm is **1.54× above** the 0.13 mm coated requirement.

> **The board as drawn is legal at 50.4 V only with a continuous conformal coat, or after package
> changes on those 9 footprints.** This is not a new blocker — it is the same 371 gaps already carried
> as blocker 5 in `AGENT_BOARD.md:729` — but it is now *stated in standard terms*: the gap class is
> legal under **B4**, not under **B2**.

**Area forced by creepage, and why it is small** (`05_floor.log` §5b):

```
boundary length per cell = 2×43 (phase-phase) + 43 (phase-batt) + 43 (power-control) + 2×43 (cell-cell)
                        = 258 mm
band area               = 258 × 0.60 = 154.8 mm²/cell  →  9.29 cm² for 6 cells (gross)
less the phase-phase band already counted inside the copper width  →  6.19 cm² net
```

**6.19 cm², i.e. 2.0 % of the floor.** On a 14 mm conductor a 0.60 mm gap is **4.3 %** of the pitch.
The common intuition that creepage drives ESC area at this voltage is **wrong by an order of
magnitude** — 50.4 V is a low-creepage voltage. It costs packages, not area.

---

## 4. Thermal

### 4.1 Dissipation, per cell and total (`04_calc.log` §4)

Inputs: 6 × IPTC014N10NM5, **RDS(on) max 1.4 mΩ @ 25 °C** (`Past_Conversation.md:3846`, datasheet tier),
**× 1.6 at temperature (ASSUMED)**, I_rms = 60 A, f_sw = 20 kHz (`REV_B_ARCHITECTURE.md:21`),
t_sw = 30 ns combined (**ASSUMED**), 4 × 0.5 mΩ shunts (`REV_B_ARCHITECTURE.md:76`).

| term | per cell | 6 cells | where the heat goes |
|---|---|---|---|
| FET conduction (hot) | 24.19 W | 145.1 W | out the **TOLT tops** |
| FET switching | 5.44 W | 32.6 W | out the **TOLT tops** |
| 4 × 0.5 mΩ shunts | 4.50 W | 27.0 W | into the **PCB** |
| copper I²R (5 × 60 A, 0.395 mΩ, 45 mm) | 7.12 W | 42.7 W | into the **PCB** |
| **total** | **41.25 W** | **247.5 W** | 178 W top / 70 W board |

The shunt term is validated against the repo's own arithmetic: bus shunt 60² × 0.5 mΩ = **1.8 W**,
which is exactly `REV_B_ARCHITECTURE.md:81`.

### 4.2 Copper area to spread the board-side 69.7 W at ΔT = 20 K

| cooling | h_eff (ASSUMED) | copper area needed |
|---|---|---|
| bare PCB, natural convection + radiation | 16 W/m²K | **2 178 cm²** — impossible |
| board on the design heatsink, airflow | 250 W/m²K | **139.4 cm²** |

The copper block that the *current-width* requirement already forces is **119.2 cm² per face**
(1987 mm² × 6). Add B.Cu, which is bare 4 oz copper, and there is **238 cm² of copper**, against
139 cm² needed.

> **THERMAL AREA = 0 cm² ADDED.** The board-side loss is spread by copper that the current path
> already pays for. There are **not** two additive terms here; the current-width block *is* the heat
> spreader. Reporting them separately and summing would double-count 139 cm².

### 4.3 What the thermal term really constrains — and it is not the PCB

The **177.8 W** that leaves the TOLT tops is a **heatsink** requirement, not a board requirement:

| h_eff of the spreader/fin surface | wetted area at ΔT = 20 K above a 45 °C ambient (**ASSUMED**) |
|---|---|
| 25 W/m²K (natural) | 3 556 cm² |
| 50 W/m²K | 1 778 cm² |
| 100 W/m²K | 889 cm² |
| 250 W/m²K (forced) | **356 cm²** |

**This is the number that should worry the programme more than 492.4 cm² does.** 247.5 W of dissipation
on a 316 cm² board is **7.83 kW/m² of board (0.78 W/cm²)**, and the mechanical heatsink needed to remove it at 250 W/m²K
is **larger than the PCB**. A 492 cm² outline is a packaging problem; a 356 cm² heatsink is an
airframe-integration problem. Junction temperature is *not* the limit — TOLT R_th(j-c) is ≈0.3 K/W, so
4.9 W per device is ≈1.5 K — the spreader and its interface dominate.

---

## 5. The floor

Method: build each term from measured geometry, sum, then reconcile the sum back to the measured
492.42 cm² and require the reconciliation to **close to 0.01 cm²**. It does.

### 5.1 (a) Current-width area — 119.2 cm²

The governing layer must carry the three phase conductors (the other 60 A nets can be split across the
two 4 oz outers):

```
across the layer = 3 × 13.98 mm + 2 × 0.60 mm creepage        = 43.14 mm
series depth     = HS landing 14.92 + LS landing 14.92
                 + phase shunt 11.02 + 2 × 0.60 + terminal 4.00 = 46.06 mm
block            = 43.14 × 46.06 = 1987 mm² = 19.87 cm²/cell  →  119.23 cm² for 6 cells
```

Every depth term is a **measured courtyard**, not an estimate: the TOLT is
`11.560 × 14.920 mm = 172.48 mm²` and the shunt is `7.620 × 11.020 = 83.97 mm²`
(`03_cellinventory.log`). The six FET landings plus four shunts occupy 1370.8 mm² of the 1987 mm²
block — **69 % fill**, which is dense but not impossible. The only ASSUMED term in the depth is the
4.00 mm terminal landing.

### 5.2 (b) Creepage area — 6.19 cm²

As §3.3. Gross 9.29, net of what is already inside (a) = **6.19 cm²**.

### 5.3 (c) Thermal area — 0 cm²

As §4.2. Stated explicitly rather than omitted, because "0" is the finding.

### 5.4 (d) Unavoidable components outside the block — 22.94 cm²/cell

| item | per cell | basis |
|---|---|---|
| local control bay | **13.60 cm²** | 884.1 mm² of measured footprint bbox (`03_cellinventory.log`, cell 11 total 4055.9 minus lugs/FETs/shunts/cap/TVS) ÷ 65 % packing (**ASSUMED**) |
| bulk cap 820 µF / 100 V, D18 mm | 3.54 cm² | measured `CP_Radial_D18.0mm_P7.50mm` = 354.20 mm² |
| TVS SM8S51A (DO-218AB) | 1.80 cm² | measured 179.85 mm² |
| 60 A terminals | 4.00 cm² | **ASSUMED 400 mm²** — see §5.6: the present M5 lugs use **1267 mm²** |
| **subtotal** | **22.94 cm²** | |

### 5.5 The sum

```
(a) current width      119.23 cm²
(b) creepage             6.19
(c) thermal              0.00
(d) components         137.64   (22.94 × 6)
    supervisor + aux    37.66   (18.83 cm² measured bbox ÷ 50 % ASSUMED)
                              ------
    raw                    300.72 cm²
    + 5 % edge/routing margin (ASSUMED)   15.04
                              ------
    FLOOR                  315.76  →  **316 cm²**
```

**As a board:**

| aspect | dimension | = cm² |
|---|---|---|
| **1 : 1** (the airframe CAD placeholder's aspect) | **177.7 × 177.7 mm** | 315.8 |
| **1 : 1.63** (today's aspect) | **227 × 139 mm** | 315.6 |
| 1 : 1.5 | 218 × 145 mm | 316 |

**Sensitivity to the one ASSUMED thermal input** (`05_floor.log`):

| allowed copper rise | width | copper block | **FLOOR** | % of 492.4 |
|---|---|---|---|---|
| 10 K | 21.29 mm | 29.98 cm² | **379 cm²** | 77 % |
| 15 K | 16.65 mm | 23.56 cm² | **339 cm²** | 69 % |
| **20 K (adopted)** | **13.98 mm** | **19.87 cm²** | **316 cm²** | **64 %** |
| 25 K | 12.21 mm | 17.43 cm² | 300 cm² | 61 % |
| 30 K | 10.93 mm | 15.66 cm² | 289 cm² | 59 % |

So the floor is **289–379 cm² over 30–10 K**, with **316 cm² at the adopted 20 K**. The band is honest:
the single biggest lever on the answer is a temperature limit the repo has never stated.

### 5.6 Reconciliation — the sum closes exactly

| term | cm² |
|---|---|
| 6 motor cells at floor density | 263.08 |
| supervisor + aux at floor | 37.66 |
| in-cell slack (57.09 bbox − 43.85 floor, ×6) | 79.46 |
| grid gaps between the six cells | 46.78 |
| supervisor strip beyond its parts | 37.47 |
| x / y margins around the cell block | 27.96 |
| **TOTAL** | **492.42** ✓ (= `BOARD_AREA_CM2`) |

**Independent triangulation, and it is the reason to believe 316.** The repo's own most aggressive
placement attempt was 150 × 150 mm = **225 cm²** — achieved only by allowing control parts on B.Cu
(`2026-08-27-esc-150mm-six-layer-design.md:9,11`). The single-sided rule forbids that, and the six
control bays total **81.6 cm²**. 225 + 82 = **307 cm²**, against this floor's 316 — **within 3 %**,
reached by a completely different route. Two independent estimates of the same number to 3 % is the
strongest result in this report.

---

## 6. Necessary versus dead — plainly

| | cm² | % |
|---|---|---|
| **structurally necessary** | **300.7** | **61.1 %** |
| **dead space** | **191.7** | **38.9 %** |
| of which: in-cell slack | 79.5 | 16.1 % |
| of which: gap between the six cell boxes | 46.8 | 9.5 % |
| of which: supervisor strip beyond its parts | 37.5 | 7.6 % |
| of which: x/y margins around the cell block | 28.0 | 5.7 % |

**Where the dead space is, in words the layout can act on:**

1. **79.5 cm² — inside each cell.** A cell's power pads span 57.09 cm² but its floor is 43.85. The gap
   is available width: the three FET columns sit on an **≈19.3 mm x-pitch for an 11.56 mm part** — a
   **7.75 mm** gap where 0.60 mm is required (`03_cellinventory.log`, x = 28.69 / 47.75 / 47.94 / 67.15 /
   67.48). That is **7.15 mm of recoverable width per gap, 2 gaps, 6 cells.**
2. **46.8 cm² — between cells.** The grid runs at **85.0 × 82.5 mm pitch for a 79.6 × 71.7 mm cell**
   (`02_geometry.log`), i.e. 5.4 and 10.8 mm of interstitial air. Cell-to-cell requires 0.60 mm.
3. **37.5 cm² — the supervisor strip.** 75.1 cm² of board holds 18.8 cm² of components. It is a 25 %
   filled strip, and at a normal 50 % it is 37.7 cm².
4. **28.0 cm² — margins.** 6.1 mm left, 3.3 mm right, 3.2 mm bottom of pure edge.

**None of that is creepage, and none of it is component crowding.** Two-thirds of the dead space is
**pitch**, which is why a compaction pass that does not change the grid cannot recover it.

### 6.1 The three levers that would move the floor itself

Each lever is stated against the baseline it actually moves.

| lever | effect | note |
|---|---|---|
| **Consolidate the six local control bays** into one supervisor domain (the architecture explicitly rejects this — `REV_B_ARCHITECTURE.md:28-51`) | **316 → 230 cm²** (−81.6 × 1.05 = −85.7) | by far the biggest lever; an architecture decision, not a layout one |
| **Document a duty cycle.** `FA4119_PROPULSION_DECISION.md:44` already says 50 s at 2.7 kW; at a 30 K copper rise the whole floor is 289 cm² | **316 → 289 cm²** (−27) | needs a written thermal acceptance, not a layout change |
| **Right-size the power terminals.** Present lugs are `POWER_LUG_M5_3P_P20` = **776.49 mm²** and `M5_2P_P20` = **490.49 mm²** → **1267 mm² per cell, 76.02 cm² total = 15.4 % of the board.** Three Ø5.5 mm holes on a 20 mm pitch is a 200 A-class interface; 60 A needs ~16 mm² of copper | **worth 52 cm² of the 176.7 cm² shrink** (already credited: §5.4 uses 400 mm²/cell, not 1267) | purely mechanical; the repo records no harness interface that forces 20 mm pitch |

All three together land near **205 cm²**, i.e. roughly what six commercial single-channel 60 A ESCs
would occupy (≈12–15 cm² each). **The gap between 316 and ~205 is the price of the six-local-MCU +
four-Kelvin-shunt + per-cell-isolation architecture.** That is an owner decision about what the board
is *for*, not a layout defect — and it is the honest frame for any compaction target below ~300 cm².

---

## 7. Assumption register

Every number not measured, with the direction it moves the answer.

| # | assumption | value | why | sensitivity |
|---|---|---|---|---|
| A1 | allowed copper temperature rise | **20 K** | repo states none | **±20 % of the floor over 15–30 K** |
| A2 | RDS(on) hot/cold ratio | ×1.6 (1.4 → 2.24 mΩ) | typical 100 V trench | ±20 % on the FET term only; does not touch area |
| A3 | switching transition time | 30 ns combined | no double-pulse data exists (`REV_B_ARCHITECTURE.md:114`) | ±30 % on 32.6 W |
| A4 | ambient | 45 °C | unstated | shifts heatsink area only |
| A5 | h_eff bare PCB / on heatsink | 16 / 250 W/m²K | no thermal model in repo | 16→40 changes width 2.75×→1.74× the IPC value |
| A6 | control-bay packing density | 65 % | measured board achieves 71 % at cell level | ±10 % → ±8 cm² of floor |
| A7 | supervisor-strip packing | 50 % | mixed digital/RF/USB | ±10 % → ±4 cm² |
| A8 | 60 A terminal area | 400 mm² | sized by hand, see §6.1 | ±150 mm² → ±9 cm² |
| A9 | conductor series length | 45 mm | measured span 55.4 mm, reduced by compaction | affects the loss-budget cross-check only |
| A10 | edge/routing margin | 5 % | conventional | ±3 % → ±9 cm² |
| A11 | TOLT heat leaves via the top | all 178 W | top-side-cooled package per `REV_B_ARCHITECTURE.md:154-155` | if half exits the PCB, thermal area +70 cm² |

---

## 8. What this analysis does NOT cover

- Not a layout. The floor says *what must fit*, not *where it goes*.
- Mounting holes, board-edge chamfers, connector access, test points, fiducials, and the front
  spreader's clamp envelope are **not** in the 5 % margin — they are small, but they are not counted.
- The isolation barrier (RFM-0505S / ISO6731F) is governed by those modules' own ratings, not by
  IPC-2221; its creepage was not calculated.
- The 540 unrouted 2+-pad nets (`fab-esc-rules-first/nets.json`) are not costed. I did not measure
  the unconnected count; the floor does not depend on it, and `kicad-cli` 499 vs `pcbnew` 1,542
  (`AGENT_BOARD.md:608-612`) is a sibling unit's question.
- Copper *thickness tolerance* and etch factor are not derated; a 4 oz pour etches to less than 0.14 mm.
- No thermal solver was run. §4 is ANALYTICAL throughout.

## 9. Artefacts

| file | what |
|---|---|
| `esc_rev_b_COPY.kicad_pcb` | the board copy worked on (sha256 `992570571DEBC4…`) |
| `01_inventory.py` / `.log` | board bbox, footprint census, net census, tracks, zones |
| `02_geometry.py` / `.log` | per-cell extents and pitch, global footprint inventory |
| `03_cellinventory.py` / `.log` | full cell-1 footprint inventory, class summary, lug/TOLT/cap/shunt pad geometry |
| `04_calc.py` / `.log` | §1–§4: widths, cross-checks, creepage, thermal |
| `05_floor.py` / `.log` | §5–§6: the sum, dimension, sensitivity, reconciliation |
| `08_verify.py` / `.log` | **74 assertions, all PASS** — re-derives every headline number in this report from the measured constants and fails loudly if one drifts |
| `07_figure.py` → `plan.svg`, `plan.png`, `plan.html` | the figure in this report |
| `floor.json`, `floor_final.json` | machine-readable inputs and outputs |

Reproduce: `& 'C:\Program Files\KiCad\9.0\bin\python.exe' <script>.py` from any directory; every path is absolute.
The verification gate is `08_verify.py`; it exits 0 only if all 74 assertions hold.

---

## 10. Correction history

- **Nothing withdrawn.** This is the first report of this unit.
- One internal correction was made during the work and is recorded because it changed the answer by
  139 cm²: my first draft added the copper-spreading area (139 cm²) as a separate thermal term. It is
  **not** separate — the copper block that the current requirement already forces is the spreader.
  Adding both would have produced a floor of 455 cm² and the false conclusion "this board cannot
  shrink". §4.2 and §5.3 now carry the reasoning in full.

![the plan](plan.png)