# ESC operating point — what speed does the aircraft actually reach, and what should the ESC be designed to?

Wave 17, ONE question. Evidence dir `E:/engineering-portfolio-audit/evidence/esc-operating-point/`
(all work on copies; every input is another unit's committed evidence, read-only).

**STATUS: COMPLETE.** Skeleton written first, then appended per step. Chain is `op_point.py` →
`op_point.json` / `op_point.log`; **12 of 12 controls PASS** before any number is quoted.

---

## 0. The answers

| question | answer |
|---|---|
| **The three numbers** (per-phase RMS, same node) | drag at 720 km/h **87.7–154.5 A (best 111.1 A)**; power system **43.48 A** (240 A pack / 6 / 0.92, and it is an *assumption*, never measured); PCB **18.21 A as drawn**, **36.58 A** over the full 9.42 mm corridor |
| **Speed at 18.2 A** | **394 km/h** (CdA 0.004162 m²) |
| **Speed at 34.5 A** | **488 km/h** — and 501 km/h if 34.5 A is read at the bus node (37.5 A phase) |
| **Speed at 43.5 A** | **527 km/h** |
| **Design current** | **36.6 A per phase / 33.7 A bus — a 35 A-class ESC.** 34.5 A is the shunt pad's *bus* ceiling as built; the phase corridor binds 2 % earlier. **43.5 A was never achievable on this board, and is not needed:** at 43.5 A the aircraft reaches 527 km/h, i.e. 193 km/h short of the 720 km/h it was sized for |
| **FETs at 36.6 A** | 3.33 W/device, **Tj 119.6 °C** at TA 45 °C with the mandated spreader — 55 °C under the 175 °C limit, 70 % of the 52 A thermal ceiling. **Comfortable.** At 43.5 A: 142.6 °C, **marginal** |
| **Recommendation** | design to **36.6 A phase / 33.7 A bus (35 A class)**, 4-layer 3 oz: **497 km/h**, **$450–870** per 5 pcs |

**Two figure corrections, because the brief's framing does not survive the row-level data:**

1. **"88–154 A" is right, and it is the jet-term chain.** Reproduced here as **87.68–154.47 A**
   (C5, C6) with the induced-velocity term inside the disk power. `esc-cda-bound` publishes
   **79.2–132.1 A** for the *same* build-up — that is this chain with `vi` omitted, and C8 shows the
   two differ by exactly the induced term (98.25 A vs 111.09 A at the best CdA). Both are the
   programme's own numbers; the jet version is the one used here **because it stays valid when the
   speed is no longer 720 km/h**, which is the only thing this unit computes.
2. **"34.5 A if the shunt land were fixed" is mislabelled.** 34.5 A **is** the as-built 23-barrel
   pad (23 × 1.50 A). A land that holds the 27 barrels it needs is **40.50 A**. Fixing the land
   moves the ceiling *up*, it does not produce 34.5 A.

---

## 1. The three numbers, with their sources

Same node for all three: **per-phase RMS current**, repo convention `I_phase = I_dc / 0.92`
(`esc-motor-demand/derive.json:phase_convention_factor`). The board's own numbers are usually quoted
at the **bus** node, and the two are 8.7 % apart — mixing them is the single easiest way to make this
board look compliant.

| # | What | Value | Node | Source | Tier |
|---|---|---|---|---|---|
| **A** | **Drag requires** at 720 km/h | **87.68 – 111.09 – 154.47 A**<br>(CdA 0.003354 / 0.004162 / 0.005594) | phase RMS | `esc-motor-demand/derive.py:307-323` chain run at this wave's CdA band (`esc-cda-bound/cda_analysis.json`) — `op_point.py` C5/C6/C7 | **ANALYTICAL** (build-up CdA, momentum-theory fan) |
| | drag force at the best CdA | 75.7 N, T/W 1.15, 27.23 kW electrical, 613.2 A bus | aircraft | same | ANALYTICAL |
| **B** | **Power system can supply** | **43.48 A** = 240 A pack ÷ 6 channels ÷ 0.92 | phase RMS | `derive.json:battery` — 12S 1.6 Ah 150C → 240 A; control "pack cap 150C × 1.6 Ah = 240 A" PASS | **ASSUMED** — a C-rate on a label, never measured, no sag data |
| | the motor is tighter than the pack | 1,600 W stock ÷ (0.92 × 44.4 V) = **39.17 A** | phase RMS | `derive.json:motor.stock_power_w` | ANALYTICAL (published rating) |
| **C** | **PCB can route** — as drawn today | **18.21 A** | phase RMS | 3.600 mm × 0.105 mm F.Cu, k 0.048, ΔT 20 K; corridor MEASURED in `esc-route-attempt/REPORT.md:293`, rating recomputed here (C1) | **MEASURED** corridor + ANALYTICAL ampacity |
| | — full corridor, no redesign | **36.58 A** | phase RMS | 9.42 mm measured corridor, `esc-layer-cost/02_ampacity.json:rows[0].cap_A` (C4) | MEASURED + ANALYTICAL |
| | — shunt pad, as built | **34.50 A bus** = 23 barrels × 1.50 A = 37.50 A phase-equiv | bus | `02_ampacity.json:barrels` | MEASURED count + ANALYTICAL A/barrel |
| | — shunt pad if land holds 27 | **40.50 A bus** = 44.02 A phase-equiv | bus | same, `bus_pad_need` | MEASURED pad area |

**The three numbers do not agree, and they are not supposed to.** They are 87.7–154.5 / 43.5 /
18.2 A. The gap is 6.1× between what drag asks and what the copper currently carries, and 2.6×
between what drag asks and what the pack claims. The only number in the set that is *measured on
hardware* is the 18.21 A.

### 1.1 The chain, verbatim (nothing retyped)

```
D      = q·CdA,  q = 18,182 Pa (3 km ISA, 200 m/s)          esc-cda-bound design_point
vi     = 0.5·(−V + sqrt(V² + 2T/(ρ·A)))   A = 0.0070434 m²  derive.py:311
p_disk = T·(V + vi);  p_shaft = p_disk/0.72;  p_elec = p_shaft/(0.90·0.97)   derive.py:312-313
I_bus  = p_elec/44.4;  per motor ÷6;  phase = per-motor/0.92                  derive.py:353-360
```

Controls that license quoting it: C5/C6 reproduce the brief's 88 A and 154 A to 0.4 %; C8 reproduces
`esc-cda-bound`'s 98.25 A to 4e-6; **C9 inverts the chain at 111.09 A and returns exactly 200.000 m/s
— the round trip closes**, which is the control that matters for everything in §2.

---

## 2. The speed the aircraft actually reaches

Inversion: at a current-limited operating point the fan absorbs the available power, so
`T·(V+vi) = p_elec·0.873·0.72`; equilibrium is where that thrust equals `0.5·ρ·CdA·V²`.
Solved by bisection on V. **CdA used: 0.004162 m²**, the build-up's nominal and this programme's
best estimate (band 0.003354–0.005594, floor 0.002702).

| per-phase current | where it comes from | speed | T | P_elec | static T/W |
|---:|---|---:|---:|---:|---:|
| **18.21 A** | the copper as routed today | **394 km/h** | 22.7 N | 4.46 kW | **0.78 — cannot lift off** |
| **34.50 A** | the brief's figure, read at the phase node | **488 km/h** | 34.7 N | 8.46 kW | 1.19 |
| **36.58 A** | the phase corridor, 9.42 mm 3 oz | **497 km/h** | 36.1 N | 8.97 kW | **1.24** |
| **37.50 A** | the shunt pad as built (34.5 A bus) | **501 km/h** | 36.7 N | 9.19 kW | 1.26 |
| **39.17 A** | motor stock 1,600 W | **509 km/h** | 37.8 N | 9.60 kW | 1.30 |
| **43.48 A** | the pack claim, 240 A / 6 / 0.92 | **527 km/h** | 40.5 N | 10.66 kW | 1.39 |
| *(111.09 A)* | *the drag demand at 720 km/h* | *720 km/h* | 75.7 N | 27.23 kW | 1.15 |

**The answer to the question asked: this aircraft reaches 394 km/h on the board as it is routed
today, and 527 km/h if every declared limit were real and it could use all of them. The 720 km/h
design point is 193–326 km/h beyond what any current available to it can hold.**

### 2.1 Sensitivity to CdA

Speed scales as ≈ CdA^(−1/3): **−3.46 % speed per +10 % CdA** (computed, not assumed). Across the
defensible CdA band, and at the friction floor that no real aircraft reaches:

| current (phase) | floor 0.002702 | low 0.003354 | **best 0.004162** | high 0.005594 |
|---:|---:|---:|---:|---:|
| 18.21 A | 461 | 426 | **394** | 353 km/h |
| 34.50 A | 570 | 528 | **488** | 437 km/h |
| 36.58 A | 582 | 538 | **497** | 446 km/h |
| 43.48 A | 616 | 570 | **527** | 472 km/h |

The whole CdA band moves the 36.6 A answer by −9 %/+17 % (445–582 km/h). **The conclusion is
CdA-insensitive: the aircraft is a 440–580 km/h aircraft at this copper, and no CdA in the physical
band makes it a 720 km/h one.**

### 2.2 The check that settles it without any CdA argument

Invert the other way — **what CdA would let each current hold 720 km/h?**

| current | CdA required for 720 km/h | verdict |
|---:|---:|---|
| 18.21 A | 0.00075 m² | **below the friction floor (0.002702)** |
| 34.50 A | 0.00140 m² | below the floor |
| 36.58 A | 0.00148 m² | below the floor |
| 43.48 A | 0.00174 m² | below the floor |
| 111.09 A | 0.00416 m² | physically possible |

A surface with CdA 0.00174 m² at 0.779 m² of wetted area would have a skin-friction coefficient
below the flat-plate value — i.e. **no 43.5 A-class ESC of this board can fly this airframe at
720 km/h at any CdA that exists.** That is the cleanest statement of the whole conflict, and it does
not depend on which build-up point is right.

### 2.3 The operational consequence nobody has stated

Static thrust from the same chain (ρ 1.225, 6.72 kg ⇒ 65.9 N weight):

| current | static thrust | T/W |
|---:|---:|---:|
| 18.21 A | 51.4 N | **0.78 — CANNOT LIFT** |
| 26.44 A | 65.9 N | 1.00 (minimum that flies) |
| 30.50 A | 72.5 N | 1.10 (minimum to climb) |
| 36.58 A | 81.8 N | **1.24** |
| 43.48 A | 91.8 N | 1.39 |

**The board as routed today does not take off.** 18.2 A is a corridor demonstration, not a
flight-capable rating. Any design below ~30 A per phase is not a derated aircraft, it is a static
test article.
---

## 3. The ESC design current that makes engineering sense

Every ceiling in one place, normalised to the phase node (÷0.92 where the source is at the bus node):

| ceiling | phase A | how it is set | tier |
|---|---:|---|---|
| router, as drawn 3.600 mm | **18.21** | measured corridor, IPC rating | MEASURED + ANALYTICAL |
| **phase corridor, 9.42 mm × 0.105 mm** | **36.58** | the width the placement actually offers | MEASURED + ANALYTICAL |
| shunt pad, 23 barrels (34.5 A bus) | 37.50 (34.50 bus) | 23 legal barrels × 1.50 A | MEASURED count |
| motor stock 1,600 W | 39.17 | published rating | ANALYTICAL |
| battery pack 240 A | 43.48 | 1.6 Ah × 150C claim | **ASSUMED, unmeasured** |
| shunt pad, 27 barrels (fixed land) | 44.02 (40.50 bus) | what a new footprint would give | MEASURED pad area |

**Joint ceiling = 36.58 A per phase**, and it is the copper corridor — not the pad, not the pack.

### 3.1 The answer, stated in the unit the evaluator will use

**Design to 36.6 A per phase = 33.7 A per bus rail — a 35 A-class ESC.** At that point:

* the corridor runs at **1.00×** its 20 K rating (9.42 mm, 3 oz, k 0.048 — the only pattern class a
  real house publishes at 0.200/0.200 mm, Multi-CB 105 µm special);
* the shunt pad carries **33.65 A of its 34.50 A — 97.5 %**, so the pad is *co-binding at the bus
  node* even though it stops being the binding constraint in phase units. This is why **34.5 A and
  36.6 A both keep appearing: they are the same design point at two nodes, 2.4 % apart**, and the
  programme has been quoting them as if they were alternatives.
* the motor runs 1,494 W of its 1,600 W stock rating.

### 3.2 Why 43.5 A was never achievable — four independent reasons, none of them layout

1. **It needs 11.963 mm of 3 oz copper** (`02_ampacity.json:required.phase_4L_3oz_mm`; C3 reproduces
   it to 1e-5) **and the placement offers 9.42 mm.** Ratio 0.79. On 4 oz it needs 8.972 mm and the
   width exists — but 4 oz outer fails 89 pad gaps at 0.200/0.200 (0.250 mm is the tightest published
   4 oz floor). **The two constraints are mutually exclusive on a 4-layer board.**
2. **43.5 A phase is 40.02 A of bus current** — the pad holds 34.50 A. Ratio 0.862. Six layers do not
   touch this: the deficit is 14.19 mm² of pad area, and a barrel is not made more numerous by adding
   laminations. The gap is 4 barrels (27 needed, 23 legal).
3. **43.5 A phase is 1,777 W per motor** against a 1,600 W published continuous rating. The motor is
   the second-tightest element after the corridor and it is *outside* the ESC's control.
4. **It buys nothing aerodynamic.** 43.5 A flies the aircraft at 527 km/h. The 720 km/h design point
   needs 111.09 A. The difference between an ESC that does 36.6 A and one that does 43.5 A is
   **30 km/h** — 4.1 % of the speed that was actually wanted, bought with a footprint change, a
   stack-up change or a heavier copper tier.

**The honest reading: 43.5 A is not a requirement that the board fails. It is a requirement that was
derived from a CdA the airframe does not have, and then defended as if it were electrical.**

---

## 4. The FETs at the design current

Model is the programme's own, both directions:
`P = 1.33e-3·I² + 0.0424·I` per device (conduction with hot Rds + a linear switching term) and
`Tj = 45 °C + P·Rth`, Rth = 22.4 C/W **with the mandatory spreader** (`av-esc-ampacity-gate`
`t1_basis.py:161`, `REPORT.md:182`). The forward model reproduces the published thermal limits
52.0 / 35.9 / 26.8 A at Rth 22.4 / 40 / 62 C/W (C10, C11) — the model is invertible and consistent.

| current | P/device | Tj with spreader | % of 175 °C | Tj without spreader |
|---:|---:|---:|---:|---:|
| 18.21 A | 1.21 W | 72.2 °C | 41 % | 120.2 °C |
| **36.58 A (design)** | **3.33 W** | **119.6 °C** | **68 %** | 251.5 °C |
| 37.50 A | 3.46 W | 122.5 °C | 70 % | 259.5 °C |
| 43.48 A | 4.36 W | 142.6 °C | 82 % | 315.2 °C |
| 111.09 A (720 km/h demand) | 21.12 W | 518 °C | 296 % | — |

**Verdict at the design current: comfortable, not marginal.** Tj 119.6 °C leaves **55 °C** to the
175 °C limit and sits at **70 % of the 52 A thermal current ceiling** — a 1.42× margin on current,
which is what a rating is supposed to look like. The FETs would only reach the limit at 52 A, which
the corridor cannot deliver.

**At 43.5 A: marginal.** 142.6 °C, 32 °C of margin, 84 % of the thermal ceiling. It passes, but it
passes on a 22.4 C/W number that is *asserted, not derived*, and on a spreader whose exchange area is
declared at 181.2 cm² where the settled loss model needs 314 cm² (`av-esc-ampacity-gate` §5, G5:
"PASS by declaration"). **The 43.5 A operating point has one undocumented number between it and a
thermal failure; the 36.6 A point has two.**

**Without the spreader nothing works** — 251 °C at the design current. The spreader is a flight
article, not a heatsink accessory.

---

## 5. Recommendation

**Design the ESC to 36.6 A per phase / 33.7 A per bus — a 35 A-class board — on the existing
4-layer, 3 oz, 382.709 cm² layout. That gives 497 km/h at the best-estimate CdA (445–582 km/h across
the defensible band), at $450–870 per 5-piece lot.** It is the only operating point where all five
independent ceilings pass at once: corridor 1.00×, shunt pad 0.975×, motor 0.93×, FET junction 68 %,
and static T/W 1.24 so the aircraft leaves the ground. Do **not** buy the six-layer 3/4 oz stack
($1,300–1,900, quote-only): its phase plane reaches 49.63 A and its 4 oz inner tier is real
engineering, but it still exits on G6 at the 34.5 A shunt pad, so the extra $430–1,450 buys a plane
that feeds a pad that cannot take the current. Do **not** fund another routability wave either: the
measured 3.6 mm corridor is a 4.4 mm free gap against a 6.0 mm `HIGH_CURRENT` rule, and no router
invents copper. Spend the next dollar on the shunt footprint (27 barrels, 14.19 → ~17 mm²) **and** a
full-configuration drag measurement, because the 720 km/h target is a CdA claim, not an ESC claim —
at 111.09 A needed and 27.2 kW on the shaft, it is a different aircraft, not a different board. State
the rating to the programme as **35 A continuous per phase, 43.5 A not offered**, and record 720 km/h
as withdrawn on this airframe rather than deferred.

---

## 6. Provenance, and what is not verified

| claim | tier | note |
|---|---|---|
| 18.21 A corridor rating; 36.58 A full corridor | MEASURED corridor + ANALYTICAL ampacity | corridor widths from `esc-route-attempt` (pcbnew, maximin inscribed disc); rating from IPC-2221 closed form, C1/C4 |
| drag 87.7/111.1/154.5 A at 720 km/h | ANALYTICAL | CdA build-up with a stated band; **no full-configuration drag measurement exists** — the CFD force extraction in this programme is on a cut plane and its Cd/CdA are not quotable |
| speeds 394 / 488 / 497 / 527 km/h | ANALYTICAL | equilibrium of the same chain; **assumes the fan can be throttled to the available power** (no measured fan map exists — checked, none in the repo), and that efficiencies hold at part load |
| 43.48 A power-system figure | **ASSUMED** | 1.6 Ah × 150C label; no sag, no connector, no harness limit modelled. A real pack will deliver less |
| FET Tj | ANALYTICAL on an **asserted** Rth | 22.4 C/W is not derived; Tj at 36.6 A stays legal up to Rth **39.0 C/W** — a 74 % degradation of the declared 22.4 (144.9 °C at 30 C/W, 178.2 °C at 40, i.e. a fail). At 43.5 A the threshold is **29.8 C/W**, only 33 % worse than declared |
| prices | ESTIMATE | heavy copper is quote-gated at every house checked; the $450–870 row is a published 1 oz list × a published 1.5–2× multiplier |

**Assumptions that could move the answer, in order of size:** (1) the fan's part-load behaviour — a
fixed-pitch ducted fan at reduced rpm is not guaranteed to sit on the momentum-theory locus, and if it
cannot be throttled down the aircraft simply cannot use the current it is given (the speed would fall,
not rise, so 497 km/h is an **upper** bound); (2) CdA, worth −9 %/+17 %; (3) pack sag, unquantified;
(4) FOM 0.72 installed — an optimistic 0.85 raises the 36.6 A speed to 525.5 km/h, a poor 0.62 lowers
it to 473.0 km/h.

**Reproduce:** `python op_point.py` → `op_point.log`, `op_point.json`. 12/12 controls PASS; the chain
refuses to print if any fails.

---

## 7. Return (the <=240-word answer)

**Three numbers (per-phase RMS):** drag at 720 km/h **87.7 / 111.1 / 154.5 A** (CdA 0.003354 /
0.004162 / 0.005594, jet-term chain; the brief's 88/154 reproduce as 87.7/154.5); power
system **43.48 A** (240 A pack/6/0.92; ASSUMED label rating); PCB **18.21 A** as routed
(3.600 mm), **36.58 A** over the 9.42 mm corridor, shunt pad **34.50 A bus** (23 barrels; 27 barrels
land gives 40.50 A, so the brief's "34.5 if fixed" is a mislabel).

**Speed at CdA 0.004162 m2:** 18.2 A -> **394 km/h**; 34.5 A -> **488**; 43.5 A -> **527**. Band
353-616 (-3.46 % per +10 % CdA).

**Design: 36.6 A phase / 33.7 A bus, a 35 A-class ESC.** The corridor binds; the pad sits at 97.5 %.
43.5 A was never achievable: it needs 11.963 mm 3 oz vs 9.42 offered, 40.02 A bus vs
34.50, 1,777 W/motor vs 1,600 W — and buys only 527 km/h.

**FETs:** 3.33 W/device, **Tj 119.6 C** at Rth 22.4 with the spreader, 68 % of 175 — **comfortable**
(legal to 39 C/W). At 43.5 A: 142.6 C, legal only to 29.8 C/W — marginal.

**Recommendation:** 36.6 A per phase (35 A-class), 4-layer 3 oz: **497 km/h, $450-870 per 5 pcs**.
Skip the $1,300-1,900 six-layer stack (it still fails the shunt pad) and further routing waves. Fix
the shunt footprint and measure drag: 720 km/h needs 111 A, 27.2 kW — a different aircraft, not a
different board.