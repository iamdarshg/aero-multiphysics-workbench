# ESC rev_b — the current, then the placement that carries it

**Unit:** `esc-current-place` · **Wave:** 6 · **Owner constraints in force:** ESC single-sided
and as compact as possible; 4 oz on the ESC only; no HDI anywhere; $60 spend cap.

**Host:** KiCad 9.0.7 `C:/Program Files/KiCad/9.0/bin/` — `kicad-cli` 9.0.7, `pcbnew` 9.0.7
(Python 3.11), arithmetic in CPython 3.12.

**Nothing was written into a repo.** No commit, no push, no `audit/*` branch. Every board in
this unit is a **copy** under `E:/engineering-portfolio-audit/evidence/esc-current-place/`.

| artefact | sha256 / size |
|---|---|
| board of record, copy | `esc_rev_b_orig.kicad_pcb`, sha256 `992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD`, 4,988,844 B |
| **power-first placement** | `esc_rev_b_powerfirst.kicad_pcb`, 2,957,981 B, 687 footprints, **0 on B.Cu** |
| compacted board + stale repair (attempt 1) | `esc_rev_b_compact_stalefix.kicad_pcb` |
| compacted board + stale repair (attempt 2) | `esc_rev_b_compact_stalefix2.kicad_pcb` |

---

## 0. The answer

| question | answer |
|---|---|
| Is 60 A per phase right? | **RIGHT — as the design/burst rating.** It is 1.67× the FET's board-only continuous junction limit, so 60 A continuous needs the top-side spreader the architecture document already mandates. |
| FET topology | **3 high-side + 3 low-side per cell**, one device per switch position, no paralleling. 6 FETs = 3 half-bridges = the 3 motor phases. |
| Thermal bound (no spreader) | **26.8 – 52.0 A**, central **35.9 A** at a 45 °C ambient, Tj = 175 °C |
| Shunt bound | **not binding.** Part is 10 W, not 5 W; 60 A is 1.8 W on the bus shunt = 18 % |
| Sense bound | **not binding.** INA296A2 is **20 V/V**, not 50; 60 A = 2.25 V, saturation at **145 A** |
| Motor cross-check | FA4119 KV350 outrunner, manufacturer's 12S point **74 A / 3.47 kW**; repo's own hard limit **60–65 A** |
| Required width at 4 oz, 60 A, ΔT 20 K | **13.980 mm total → 6.990 mm per face** |
| Power-first area | **382.71 cm²** |
| Does it beat 370.12 cm²? | **NO — +12.59 cm² (+3.40 %)**. The corridor is what the 370.12 cm² compaction spent. |
| Narrowest power corridor | **7.400 mm** vs **6.990 mm** required → **PASS, +5.9 %** |
| components on B.Cu | **0** |
| The 8 stale segments | **NOT FIXED.** Two repairs executed, both measured, both failed; residual and cause stated (§6). |

---

# PART 1 — THE CURRENT

## 1. The device, from its datasheet

`IPTC014N10NM5`, Infineon OptiMOS 5, 100 V N-channel, package **PG-HDSOP-16** — the
TO-Leaded **Top-side cooling** (TOLT) package. Datasheet Rev 2.0, 2022-05-24, 13 pp.

<https://www.infineon.com/assets/row/public/documents/24/49/infineon-iptc014n10nm5-datasheet-en.pdf>

| quantity | value | where |
|---|---|---|
| **RDS(on) max @ VGS = 10 V, ID = 150 A** | **1.4 mΩ** (typ 1.3) | Table 4, p. 4 |
| RDS(on) max @ VGS = 6 V, ID = 75 A | 2.0 mΩ (typ 1.6) | Table 4, p. 4 |
| **VGS(th)** | 2.2 / 3.0 / 3.8 V | Table 4, p. 4 |
| Qg total | 168 nC typ / 211 nC max | Table 5, p. 5 |
| **Tj, Tstg** | **−55 … +175 °C** | Table 2, p. 3 |
| **RthJC** | **0.2 typ / 0.4 max K/W** | Table 3, p. 3 |
| **RthJA**, 6 cm² 70 µm Cu drain land, 40×40 board, still air | **40 °C/W** | Table 3 footnote 2 |
| RthJA, minimal footprint | 62 °C/W | Table 3 |
| ID continuous | 365 A (TC 25 °C) · 258 A (TC 100 °C) · **37 A (TA 25 °C, RthJA 40)** | Table 2, p. 3 |
| Ptot | 375 W (TC 25 °C) · 3.8 W (TA 25 °C) | Table 2, p. 3 |
| RDS(on) normalised to 25 °C at Tj = 175 °C | **≈ 1.9×** | Diagram 9, p. 8 |

**The gate drive the board actually uses.** U1101 is a `DRV8353SRTAR`. Per the DRV835x
datasheet (SLVSDY6A, revised June 2019, §8.3.1.3 p. 35):
the high-side supply is a doubler charge pump *"regulated to keep a fixed output voltage of
V<sub>VDRAIN</sub> + 10.5 V"*; the low-side VGLS regulator output is *"fixed at 14.5 V and
further regulated to 11-V on the GLx outputs"*.
So VGS ≈ **10.5 V high side, 11 V low side** — both above the datasheet's 10 V column.
**The 1.4 mΩ figure is the right one to use**, and the 6 V column (2.0 mΩ, 43 % worse) is
not.

## 2. The topology, read from the netlist (not inferred from names)

`01_netlist_facts.py` → `01_netlist_facts.json`. 681 components, 666 nets.
**36 × IPTC014N10NM5** and **24 × CSS4J-4026R-L500F** and **6 × INA296A2IDR** and
**6 × DRV8353SRTAR** and **7 × SM8S51A** (D1101…D1601 one per cell, plus D701 on the
auxiliary rail).

Pads, from the netlist's own connectivity:

```
Q1101  pin 9 -> /M1_BATP     pin 1 -> /M1_PHASE_A    pin 8 -> M1_GHA    HIGH SIDE
Q1102  pin 9 -> /M1_PHASE_A  pin 1 -> M1_SHA_I       pin 8 -> M1_GLA    LOW SIDE
Q1103  pin 9 -> /M1_BATP     pin 1 -> /M1_PHASE_B    pin 8 -> M1_GHB
Q1104  pin 9 -> /M1_PHASE_B  pin 1 -> M1_SHB_I       pin 8 -> M1_GLB
Q1105  pin 9 -> /M1_BATP     pin 1 -> /M1_PHASE_C    pin 8 -> M1_GHC
Q1106  pin 9 -> /M1_PHASE_C  pin 1 -> M1_SHC_I       pin 8 -> M1_GLC
R1120  0.5 mΩ between M1_SHA_I and /M1_BATN   (low-side leg A shunt)
R1123  0.5 mΩ between M1_BATP_IN and /M1_BATP (DC-input bus shunt)
```

**So the answer to (b) is yes: 3 high-side + 3 low-side, one device per switch position,
no paralleling anywhere on the board.** 36 devices = 6 cells × 3 phases × 2 positions.
The 6 FETs are not "6 per phase" — they are 6 per **cell**, two per phase.

**A correction to the brief's inventory.** The 24 shunts are not "4 × 0.5 mΩ per phase".
They are **per cell**: three low-side leg shunts (one in each leg's source return, carrying
that leg's current for its conduction interval) plus **one DC-input bus shunt** in series
with the cell's battery feed. They are in different circuits and are not in parallel, so
"4 × 0.5 mΩ in parallel" would be a 4× error in the shunt bound.

## 3. The thermal bound, with the arithmetic

Per device, phases A/B/C of one cell, I = phase RMS current:

```
P_cond = RDS(on)(Tj) · I_dev,rms²      with I_dev,rms² = I²/2   (one device conducts
        = 1.4 mΩ × 1.9 × I²/2           half the RMS-square over a sine-triangle cycle)
P_sw   = f_sw · 2 · ½ · V_ds · (√2·I) · t_sw     f_sw = 20 kHz, t_sw = 30 ns (ASSUMED)
        = 20e3 · 50.4 · √2 · I · 30e-9
P(I)   = 1.33e-3 · I²  +  0.0424 · I            [W, I in A]
```

`f_sw = 20 kHz` is stated in the repo (`docs/hardware/REV_B_ARCHITECTURE.md:21`
"Initial PWM 20 kHz"); `t_sw` is not in the repo and is the one assumed input.
Tj = 175 °C, **TA = 45 °C** (stated; the repo states no ambient).

| RthJA used | basis | P budget | **continuous I** |
|---|---|---|---|
| **22.4 °C/W** | area-scaled from the board's own copper | 5.81 W | **52.0 A** |
| **40 °C/W** | datasheet, 6 cm² 70 µm land | 3.25 W | **35.9 A** |
| **62 °C/W** | datasheet, minimal footprint | 2.10 W | **26.8 A** |

The area-scaled figure is not a guess: `02_cell.py` measured the six 60 A nets of one cell
at **F.Cu 1,643.2 + In1 5,039.0 + In2 2,056.0 + B.Cu 5,106.6 mm²**, which in 70 µm-
equivalent terms is **3,137 mm² per FET — 5.23× the datasheet's 6 cm² reference land.**
Fitting the datasheet's own two anchors (600 mm² → 40 °C/W, 172.5 mm² → 62 °C/W) gives
Rth ∝ A<sup>−0.352</sup> and 22.4 °C/W here.

**Cross-check that the model is right:** at TA = 25 °C with RthJA = 40 it returns **39.5 A**
against the datasheet's own **37 A** — 6.8 % apart, with the difference explained by my
30 ns switching assumption. The model is not free-parameter.

**The spreader is the answer to (c), and it is not optional.** With the TOLT top-side
interface (RthJC 0.4 max) and a case held at 95 °C, the junction bound exceeds 300 A per
device — **junction temperature stops being the limit entirely**, and the limit becomes the
spreader, the 12S supply and the motor. The architecture document already says so
(`REV_B_ARCHITECTURE.md:154-155` "the headline MOSFET current rating is not a thermal
qualification"; `:204` "thermal soak at 60 A with the production heat spreader").

**Total dissipation at 60 A: 7.36 W per FET** (4.79 conduction + 2.57 switching) **× 36 =
265 W.** That is the number the airframe has to move, and it is the real cost of 60 A.

## 4. The shunt and the sense chain — neither is binding

**Shunt.** `CSS4J-4026R-L500F` is a Bourns CSS4J-4026 4-terminal metal-strip shunt,
0.5 mΩ ±1 %, and the datasheet row is **`CSS4J-4026R-L500x  0.5 mΩ / 10 W` at a 70 °C
terminal temperature**, with a linear derate to 130 °C
(<https://www.bourns.com/docs/product-datasheets/css4j-4026.pdf>, Electrical
Characteristics and the Terminal Temperature Derating Curve).

> **The board's own BOM value string says "0.5m 1% 5W". That is wrong by 2×.** The part
> is a 10 W part. This does not change any verdict in the programme, but it is the number
> a future thermal check would be run against.

| shunt | carries | at 60 A | % of 10 W |
|---|---|---|---|
| R1123, DC-input bus shunt | the cell's whole battery current, continuously | **1.8 W** | **18 %** |
| R1120/21/22, leg shunts | one leg, half-duty | **0.9 W** | 9 % |

At what current does a shunt reach **5 W**? `I = √(5 / 0.0005) = 100.0 A`. At **10 W**:
`I = √(10 / 0.0005) = 141.4 A`. At 60 A the shunt is nowhere near either.

**Sense.** The fitted part is `INA296A2IDR`. **INA296A2 is 20 V/V, not 50 V/V.** The gain
table is explicit — INA296**A1** 10, **A2 20**, **A3 50**, A4 100, A5 200 V/V
(<https://www.ti.com/lit/ds/symlink/ina296a.pdf>, Table 4-1 p. 2; the 50 V/V part is the
INA296A3). The `A2` suffix is 20.

What the board actually does with it (`01_netlist_facts.json`): IN+ / IN− on the **bus
shunt** `M1_BUS_SH_P/N`; **REF1 → `/M1_BATN` (0 V)**, **REF2 → `M1_3V3A` (3.3 V)**;
the INA296 reference is the mean of the two pins, so VREF = **1.65 V**.

```
scale   = 0.5 mΩ × 20 V/V          = 10.0 mV/A
Vout    = 1.65 + 0.010 · I
60 A    -> 1.65 + 0.60             = 2.250 V
saturate at VS − 0.2 V (max spec)  -> (3.10 − 1.65)/0.010 =  145 A
at VS − 0.07 V (typ)               -> (3.23 − 1.65)/0.010 =  158 A
```

**The amplifier does not saturate first.** 60 A uses **41 %** of the available headroom;
the INA296 bound is 145 A, i.e. 2.4× the design current.

And the repo's own arithmetic now closes exactly, which it could not with a 50 V/V part:
`REV_B_ARCHITECTURE.md:77-80` gives gain **20 V/V**, scale **10 mV/A**, **0.6 V from
midscale at 60 A**, and *"approximate linear range with 0.25–3.05 V ADC guard limits:
±140 A"*. Check: `(3.05 − 1.65)/0.010 = 140.0 A`. **That is an identity, not an
approximation** — the document, the fitted part and the board's wiring agree.

The three **leg** shunts go to the DRV8353's integrated CSAs (SHA/SHB/SHC → SPx/SNx,
outputs `M{n}_CSA_{A,B,C}_RAW`), whose VREF pin is tied to `M{n}_3V3A` (again 1.65 V) and
whose gain is an **SPI register** (5/10/20/40 V/V). The document's 0.6 V at 60 A implies
20 V/V is programmed. **If firmware selects 40 V/V instead, that channel saturates at
82.5 A** — a firmware dependency, not a hardware bound, and it is recorded here because
nothing in the repo pins the register.

## 5. The motor cross-check — the brief's premise is wrong, and the repo is better

The brief suggested a 3670-class EDF at 1.2–2 kW. **The aircraft has no EDF.** The repo's
propulsion decision record names the motor and the current:

`repos/drone-arm/hardware/motor_release/FA4119_PROPULSION_DECISION.md`

| fact | value | line |
|---|---|---|
| motor | **Flycci FA4119 KV350** outrunner, 12 slots / 14 poles | :15-17 |
| size | 41 mm stator OD × 19 mm active stack, ≈50.5 × 44 mm, ≈280 g | :18-20 |
| manufacturer recommendation | **10S–12S, 80 A ESC, 13-inch propeller** | :22 |
| manufacturer's published 12S point | **≈3.47 kW, 74 A, 11,256 rpm, 8.18 kgf** (HQ 13×9 3-blade) | :23-24 |
| desired input per motor | ≈2.7 kW | :42 |
| **desired current point** | **≈60 A at nominal 12S** | :43 |
| burst | **up to 50 s at ≈2.7 kW, requires test validation** | :44 |
| `44.4 V × 60 A` | **2.664 kW** | :53 |
| soft battery-current rollback | **55 A** | :243 |
| **hard battery-current limit** | **60–65 A** | :244 |
| second profile | nominal 60 A, short overcurrent ceiling 70–75 A | :257-258 |

So the motor cross-check does not give 27–45 A. It gives **60 A as the stated design point**
and **74 A** as the motor's own published operating current. The 1.2–2 kW EDF range simply
does not describe this aircraft: 2.664 kW into one of four 41 mm outrunners driving an
8×4.5 propeller, on an ≈8 kg airframe (`:45`).

Two further checks that make 60 A not a free choice:

- **The sense chain is built for it.** 0.6 V at 60 A is the exact centre of the documented
  ±140 A range and 41 % of the hardware saturation. A designer who intended 40 A would not
  size for 60.
- **The bus and phase currents are the same number.** For a 3-phase inverter at SVPWM with
  m = 1, cos φ = 0.9, η = 0.97: `I_bus/I_ph,rms = 3·m·cosφ/(2√2·η) = 0.984`. So "60 A per
  phase" and "60 A from the battery" differ by 1.6 % and the ambiguity in the brief does
  not matter.

## 6. The one number, and whether 60 A is right

> **I = 60 A per phase.** Basis: the repo's declared design current and burst operating
> point, corroborated independently by the board's own sense scaling (0.6 V from midscale
> at exactly 60 A, the centre of the documented ±140 A range), by the shunt arithmetic
> (1.8 W = the repo's own figure), and by the motor (74 A published, 60–65 A hard limit).

**60 A is RIGHT, and here is what it is not.** It is not a board-only continuous rating.
Without the top-side spreader the junction limit is **26.8–52.0 A** at a 45 °C ambient
(central **35.9 A**), so 60 A continuous is **1.67× the board-limited continuous current**
and requires the spreader that `REV_B_ARCHITECTURE.md:204` already lists as a test
prerequisite. **The binding limit at 60 A is the spreader, not the FET, not the shunt, not
the sense chain, and not the copper.**

The copper still has to be sized for 60 A, because a burst does not shrink the requirement:
`esc-area-floor` §1.1 showed a 50 s burst on these conductors is a **233 K adiabatic rise**,
i.e. quasi-steady, not transient.

---

# PART 2 — PLACE POWER-FIRST

## 7. The required width

**Method.** IPC-2221 §6.2 external-conductor closed form —
`A[mil²] = (I / (k·ΔT^0.44))^(1/0.725)`, k = 0.048, `w = A/t`, t = 0.14 mm = 5.512 mil for
4 oz. It is the published closed form of the curve family IPC-2152 replaced; IPC-2152
proper gives somewhat *narrower* conductors for thick copper, so this is the conservative
direction and it is the same instrument every earlier wave used, which is what makes the
comparison with 370.12 cm² valid.

**Stated rise: ΔT = 20 K.** The repo states no copper temperature limit; 20 K is the
conventional power-board point and the sensitivity is given.

| I (A) | 10 K | 15 K | **20 K** | 25 K | 30 K | 50 K |
|---|---|---|---|---|---|---|
| **60** | 21.29 | 16.65 | **13.98** | 12.21 | 10.93 | 8.02 |
| 55 | 18.89 | 14.77 | 12.40 | 10.83 | 9.70 | 7.11 |
| 37 | 10.93 | 8.55 | 7.18 | 6.27 | 5.61 | 4.12 |

```
required at 60 A / 20 K : 13.980 mm of 0.14 mm copper  = 1.9572 mm² cross-section
split over the two 4 oz faces (the 1.5 oz inners would need 96.99 mm, so they cannot
carry it as traces)      : 6.990 mm on F.Cu and 6.990 mm on B.Cu
needed FET-column gap    : 6.990 + 2 × 0.25 clearance = 7.490 mm
```

## 8. Placing the power path first

**The design's own pitch makes the corridor possible, so the corridor is a geometry, not an
outcome.** The motor lug `POWER_LUG_M5_3P_P20` has a **20.0 mm pin pitch**. Setting the FET
column pitch to the lug's own pitch gives an **8.44 mm courtyard gap** between FETs — which
is exactly what the board of record has, and why its phase corridor measures 7.51 mm
against a 6.991 mm requirement.

So the cell is built in this order:

1. **The 15 parts the 60 A path owns are anchored**, not packed: `J1102` motor lug, the six
   FETs on the 20.0 mm pitch, the three leg shunts, the bus shunt `R1123`, the TVS `D1101`,
   the 820 µF bulk cap `C1130`, the battery tap `J1101`, and the cell thermistor `TH1`.
2. **The two 8.44 mm channels between the FET columns are reserved** — no part may enter
   them (cell-local x 12.93–21.37 and 32.93–41.37, y 15.50–46.42, on every one of the six
   cells). These are the phase corners of all three phases of that cell.
3. **Only then are the other 82 parts packed** into what is left, at a **0.6 mm
   part-to-part** rule — the board's own 0.5 mm zone clearance plus margin, and equal to
   IPC-2221B Table 6-1 column B2's 0.60 mm creepage for 51–100 V uncoated — with the cell
   height growing until they all fit.
4. **Then the control strip**, carried over unchanged from the verified compaction
   (152.01 × 16.47 mm, 105 parts), because it is not on any current path.

The sweep found **cell 76.30 × 75.26 mm = 5,742 mm², fill 70.7 %** (parts 4,060 mm² incl.
the thermistor). Cost of the corridor, isolated: the compaction's own cell was
75.30 × 73.26 = 5,516 mm² at 73.6 %; reserving **522 mm² of channel per cell (9.5 %)** costs
**226 mm² per cell (4.1 %)**.

**Array:** 2 × 3 + control strip. 3 × 2 was computed and loses (**233.9 × 170.0 = 397.6 cm²**);
4 × 2 loses badly (**310.7 × 170.0 = 528.2 cm²**). 2 × 3 is also the widest arrangement that
leaves the 152.01 mm control strip room to sit unchanged, so the strip does not have to be
re-packed.

## 9. What was achieved, measured on the saved board

```
outline          155.10 × 246.75 mm  (edge bbox 155.15 × 246.80 including the 0.05 stroke)
polygon area     38,270.93 mm² = 382.709 cm²          (GetBoardPolygonOutlines)
footprints       687        on B.Cu   0
copper           0 tracks, 0 vias, 0 zones  (removed: the compaction's 2,144 carried
                 items and 96 pours all described the OLD part positions)
```

| | area | vs 370.12 |
|---|---|---|
| compacted placement (`esc-placement`) | 370.119 cm² | — |
| **power-first placement (this unit)** | **382.709 cm²** | **+12.59 cm² = +3.40 %** |

> **It does not beat 370.12 cm², and the reason is measured, not argued.** The 12.59 cm² is
> 6 × 226 mm² of cell growth = the seven 10 µF DC-link caps per cell plus the parts they
> displaced, evicted from the two channels they were actually decoupling. The 370.12 cm²
> figure is reachable only by parking decoupling in the phase corridor — which is precisely
> the defect wave 5 found.

**DRC, 4 oz 0.250 mm rule set** (`kicad-cli pcb drc --severity-all`, the 9-rule file from
`evidence/fab-esc-rules-first/` copied in beside the board):

| type | count |
|---|---|
| `clearance` | 371 |
| `annular_width` | 42 |
| **total** | **413** |

**All 413 are pad-bound**: 371 intra-footprint pad gaps at exactly 0.2000 mm plus 42 PTH
annular rings. That is the *same* 413 the previous wave measured on both the original and
the compacted board (`esc-routable2` §2.3: `413 = 413`, per-footprint identical to the pad).
**This placement adds zero violations of its own** — no short, no mask bridge, no courtyard
overlap, no copper-edge, no dangling (there is no copper to dangle).
`kicad-cli` unconnected: **499**, which is its cap and is quoted as such, not as a figure.

## 10. The corridor, measured — and what it costs

The esc-routable2 instrument answers "can this net be tied together" (it follows the net's
two most distant pads, which for a phase net includes the DRV8353 SHx sense pins wherever
they were placed). The question here is narrower and harder: **is there 6.990 mm of free
F.Cu between the half-bridge and the motor-lug pin?** So the same bottleneck method was
applied to a **stated pad pair** — HS source → lug pin — with foreign copper as the only
obstacle set.

`08_corridor_bottleneck.py` → `08_corridor_bottleneck.json`. One instrument, three boards:

| board | phase A | phase B | phase C | **narrowest** | vs 6.990 mm |
|---|---|---|---|---|---|
| **power-first (this unit)** | **7.400** | **7.674** | **7.674** | **7.400 mm** | **PASS +5.9 %** |
| compacted 370.12 | 2.700 | 3.400 | 4.912 | 2.700 mm | **FAIL −61.4 %** |
| board of record | 7.674 | 5.346 | 5.400 | 5.346 mm | FAIL −23.5 % |

**So the power path is satisfied for the first time in the programme**: 7.400 mm of F.Cu
where 6.990 mm is required, on the narrowest of the eighteen phase conductors. And the
370.12 cm² compaction is confirmed non-viable at 2.700 mm — a 2.6× shortfall, in the same
direction and of the same size wave 5 reported.

**Read the tool's own headline, and read it fairly.** `08_corridor_bottleneck.py` prints
`powerfirst narrowest 1.400 mm -> FAIL`, because that summary takes the minimum over *all
five* pairs it measures, and one of them is BATP. The three phase conductors — the ones the
F.Cu test can actually see — are 7.400 / 7.674 / 7.674 and pass. The FAIL is carried by the
two nets that are planes, and those are the next paragraph, not a footnote.

**BATP and BATN do not appear in that table, and that is the honest open item.**
The same instrument reads BATP at **1.4 mm** and finds **no F.Cu path at all** for BATN,
because neither is carried on F.Cu:

| net | F.Cu | B.Cu | In1 | In2 |
|---|---|---|---|---|
| `/M1_BATP` | 869.2 mm² | — | **5,039.0 mm²** | — |
| `/M1_BATN` | — | **5,106.6 mm²** | — | — |
| `/M1_PHASE_A` | 183.7 | — | — | 622.3 |

These are **planes, not traces**, and a trace-width test cannot see a plane. The
cross-section arithmetic that would settle them:

```
needed 1.9572 mm²
BATP: F.Cu 1.4 × 0.14 = 0.196 + B.Cu 9.5 × 0.14 = 1.330  ->  1.526 mm², short 0.431
      so the 1.5 oz In1 pour must still be >= 0.431 / 0.0525 =  8.21 mm wide at its neck.
BATN: B.Cu alone 13.93 × 0.14 = 1.950 mm²  ->  short by 0.4 %
```

**Whether the In1 BATP pour necks below 8.21 mm is NOT measured here**, and it is the one
measurement that could reopen the area question — because a plane-based BATP would let
F.Cu be given entirely to parts. It is written here as an open item, not as a result.

## 11. The 8 stale segments — reported NOT FIXED, with both attempts measured

esc-placement's own accounting: *"route carried with its cell: 150 segments + 1986 vias;
8 left stale (cross-cell nets)"* (`esc-placement/REPORT.md:276-277`), and its DRC table
carries **`track_dangling: 26`** (`:318`).

**What I measure.** KiCad's own DRC on that same board, project rules (`drc_compact_proj.json`):
**`track_dangling` = 26**, total **446** — the previous unit reported 447 with `clearance 71`;
I read 446 with `clearance 70`, a one-violation difference stated rather than smoothed. So
the *count* of dangling items reproduces exactly; the *narrative's "8"* does not — and no
test I ran produces 8. Twenty-six dangling ends sit on **14 nets**:
`/3V3`, `/Auxiliary power/LM2_FB`, and `M{1..6}_DRV_{SCLK,SDI}`. Every one of them is a
**stub beside a single pad**, and its net's two pads are **29.6–75.6 mm apart**, so the lost
copper is a *route*, not a stub that can be snapped.

**Attempt 1 — remove the 26 segments my own dangling test flags.** `09_stale.py` →
`esc_rev_b_compact_stalefix.kicad_pcb`. Segments 154 → 128. Re-DRC: **`track_dangling`
26 → 24, total 446 → 444.** Two cleared, twenty-four left. My segment-level test and
KiCad's disagree on *which* segments (my "touches another segment" predicate compares
object identity, which is unreliable for multi-segment nets), so the wrong 26 were removed.

**Attempt 2 — take KiCad's own list and pull each free endpoint onto a pad.**
`11_stale2.py` → `esc_rev_b_compact_stalefix2.kicad_pcb`. 26 of 26 endpoints moved.
Re-DRC: `track_dangling` **26 → 18**, but `shorting_items` **51 → 91**, `solder_mask_bridge`
**81 → 200**, `tracks_crossing` **0 → 20**, total **446 → 656**. **Rejected**: dragging a
0.25 mm track's end 30–75 mm onto a pad sweeps it across neighbouring copper. The snap is
the wrong operation; the connection needs a *routed* path.

> **Verdict: NOT FIXED.** The defect class is a routing repair, not a placement repair, and
> it cannot be cleared by deleting or snapping stubs without either leaving the net open or
> committing new shorts. The measured residual is **24 dangling items** on
> `esc_rev_b_compact_stalefix.kicad_pcb`. **The power-first placement does not inherit it**:
> that board carries no copper at all, so its `track_dangling` is 0 by construction — which
> is the honest way to not carry a defect forward, and it is why the route must be drawn
> *after* the placement, not carried through it.

---

# 12. Assumption register

| # | assumption | value | direction if wrong |
|---|---|---|---|
| A1 | ambient | 45 °C | 10 K lower raises the continuous bound 12 % |
| A2 | switching transition time | 30 ns combined | ±30 % on the 2.57 W switching term only |
| A3 | RDS(on) hot/cold ratio | 1.9× at 175 °C (Diagram 9) | ±10 % on conduction loss |
| A4 | allowed copper rise | 20 K | the width table in §7 covers 10–50 K |
| A5 | the spreader is fitted | yes, per `REV_B_ARCHITECTURE.md:204` | without it 60 A continuous is not supportable |
| A6 | DRV8353 CSA gain | 20 V/V programmed | at 40 V/V the leg channels saturate at 82.5 A |
| A7 | In1 BATP pour neck | **not measured** | if < 8.21 mm, BATP does not close on the inner plane |
| A8 | packer is area-driven, not netlist-aware | yes | decoupling caps are placed by area, not adjacency — a designer must re-order them, which can only make the cell larger |

# 13. What this does NOT cover

- **Not routed.** 0 % — the board carries parts, an outline and nothing else. Routing is the
  next job and the corridor is now a geometric guarantee rather than a hope.
- **No zone refill**, because there are no zones. The pours must be re-drawn for the new
  positions; their areas above are the *old* board's and are used only for the thermal and
  cross-section arithmetic.
- **The In1/In2 plane widths are not measured** (A7). That is the one open measurement that
  could recover the 12.59 cm².
- **The packer places by area, not by netlist** (A8): the seven DC-link caps are within the
  cell but not necessarily beside the half-bridge they decouple.
- The 371 pad gaps and 42 annular rings (413) are unchanged and are the known 4 oz blocker
  (`AGENT_BOARD.md` blocker 5). Nothing in this unit touches them.
- **`AGENT_BOARD.md` was not written** — the unit's hard rule is to write only inside its own
  evidence directory.

# 14. Reproduce

```powershell
$kpy="C:\Program Files\KiCad\9.0\bin\python.exe"; $py="C:\Program Files\Python312\python.exe"
$ev="E:\engineering-portfolio-audit\evidence\esc-current-place"
cd $ev
& $py  01_netlist_facts.py          # topology, shunts, INA296 wiring, TVS
& $kpy 02_cell.py                   # cell census + copper area per 60 A net
& $py  04_current.py                # RDS(on), thermal bound, shunt, sense, width
& $kpy 05_repack.py                 # corridor-reserved repack, sweep, board geometry
& $kpy 06_execute.py                # build esc_rev_b_powerfirst.kicad_pcb
& $kpy 08_corridor_bottleneck.py    # narrowest corridor on three boards
& $kpy 09_stale.py                  # stale repair attempt 1
& $kpy 11_stale2.py                 # stale repair attempt 2
& "C:\Program Files\KiCad\9.0\bin\kicad-cli.exe" pcb drc "$ev\esc_rev_b_powerfirst.kicad_pcb" `
    -o "$ev\drc_powerfirst_025.json" --format json --severity-all --units mm
```

`03_place.py` is the first-cut power-first cell (rigid 21-part anchor column); it is kept
because it produced the negative result quoted in §8 — that a full-width vertical power
stack minimises area by narrowing without limit and cannot beat the anchored repack.