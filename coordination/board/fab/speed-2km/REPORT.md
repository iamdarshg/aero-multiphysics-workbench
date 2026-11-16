# ESC SPEC — 600–650 km/h AT 2 km ASL (target); 720 km/h AT 2 km (upgrade)

**Unit:** esc-2km-spec · **Date:** 2026-11-16 · **Author:** specialist unit (delegated)
**Evidence:** this directory. Model: `model.py` (re-runnable, `python model.py`) → `model.json`, `tables.md`.
**Provenance labels:** `[MODEL]` analytical, `[EVID]` read from programme evidence dirs,
`[LIST]` vendor published list price, `[EST]` estimate (method stated), `[MEAS]` measured on hardware.

## THE ANSWER, SIX LINES

| | |
|---|---|
| **497 @ sea level** | needs **43.5 A/phase**. The board has 36.6 A -> 469.05 km/h at SL, **500.78 km/h at 2 km** |
| **600 / 650 / 720 @ 2 km** | **63.0 / 80.0 / 108.8 A** per phase (15.43 / 19.62 / 26.66 kW) |
| **TARGET ESC (650 @ 2 km)** | 6 phases, **6 of 12 FETs populated**, 3 oz outer / 1.5 oz inner, 4L. Needs corridor **7.41 mm** and **50 barrels/ch**; the shared board builds **11.31 mm and 67**, so the copper is already 720-class. **449.9 cm2 (155.15 x 290 mm)**. $522-1,048 PCBWay / $538-717 Multi-CB, 5 pcs |
| **UPGRADE ESC (720 @ 2 km)** | **the same PCB**, all **12 FETs populated**, corridor 11.31 mm, 67 barrels/ch, same 449.9 cm2 |
| **THE SWAP** | **simple** - same outline, bolt pattern, connectors and thermal interface. It is a population change of **36 FETs, +$166** |
| **CHEAPEST LEVERS** | 16S +65.4 km/h @ 0.65 km/h/$ > ESC swap +70 @ 0.42 > CdA -1 % +2.2 @ 0.029 > prop +1 pt +3.0 @ 0.012 |

## 0. THE CORRECTED SPEC — read twice

| he said | how this report treats it |
|---|---|
| "497 for level flight at sea level is acceptable" | a **pass threshold, not the target**. The existing board already clears it at 2 km (500.8 km/h) and misses it at sea level (469.1). |
| "600-650 at 2 km is also fine … i want a clear upgrade path to 720" | **600-650 km/h AT 2 km ASL (rho 1.0066) is the design point.** |
| "720 needs to be the target at 2 km above ASL … probably with a simple ESC swap" | **720 km/h at 2 km is the stretch goal**, reached by re-populating one shared PCB. |

The earlier "600-650 at sea level" briefing is withdrawn, and it was not a cheap mistake: 650 at
sea level costs **97.4 A/phase, 23.87 kW**; 650 at 2 km costs **80.0 A/phase, 19.62 kW**. The wrong
reading buys a bigger board for a smaller deliverable.

Density is the reason the 2 km target is reachable. rho(2000 m)/rho(SL) = **0.82163** [MODEL]
(0.82171 declared). Since P_prop ~ rho*v^3:

- equal power -> 2 km speed = SL speed x (1/0.8217)^(1/3) = **x1.0677**
- equal speed -> 2 km power = **82.2 %** of the sea-level power.

So: 650 @ 2 km = 608.8 @ SL; 720 @ 2 km = 674.3 @ SL; 497 @ SL = 530.6 @ 2 km.

## 1. Model and constants

`P_prop = 0.5*rho*v^3*CdA` (thrust T = 0.5*rho*v^2*CdA, P = T*v). Every constant used:

| constant | value | provenance |
|---|---|---|
| rho sea level / 2000 m / 2500 m | 1.225 / 1.0066 / 0.9569 kg/m3 | ISA, recomputed below [MODEL] |
| eta prop / motor / ESC | 0.72 / 0.90 / 0.97 -> chain **0.62856** | programme |
| V_bus | 44.4 V (12S nominal) | programme |
| channels | 6, independent, one 3-phase bridge each | programme |
| per-phase RMS | I_phase = (I_bus_total / 6) / 0.92 | programme |
| CdA | band 0.0034-0.0056, **best 0.004162** m2 | programme |
| copper ampacity | A[mil2] = (I/(k*dT^0.44))^(1/0.725), k_ext **0.048**, k_int **0.024**, dT **20 K** | [EVID] `esc-ampacity-basis/01_k_basis.json`, controls pass |
| copper thickness | 3 oz outer = 0.105 mm, 1.5 oz inner = 0.0525 mm | [EVID] `esc-3oz-bigboard/08_ampacity.json` |
| via barrel | 1.50 A per 0.4 mm barrel through 25 um | programme; pad 23 barrels vs 27 needed at 40 A |
| FET | IPTC014N10NM5, 1.4 mOhm @ 10 V, Tj 175 C, RthJA 40 / 62 C/W | programme |
| thermal basis | Ta 50 C, Tj design 150 C (86 % of rating) | stated assumption |
| existing board | 36.6 A phase / 33.7 A bus per channel, 382.709 cm2 (155.15 x 246.80 mm), corridor 3.90 mm | programme |

ISA check (computed, not looked up):

| altitude | rho model | rho declared | error | ratio to SL (model / declared) |
|---:|---:|---:|---:|---|
| 0 m | 1.22501 | 1.2250 | +0.001 % | 1.00001 / 1.00000 |
| 2000 m | 1.00650 | 1.0066 | -0.010 % | 0.82163 / 0.82171 |
| 2500 m | 0.95687 | 0.9569 | -0.003 % | 0.78112 / 0.78114 |

**Excluded on physics, not on taste:** CdA 0.000693 and 0.0015 sit below the friction floor
0.002710 and are impossible; they appear in no table here. The 0.0034-0.0056 band is used as given.

## 2. Validation against the 36.6 A board — no tuning

| quantity | model | programme | verdict |
|---|---:|---|---|
| speed at 2 km, 36.6 A, CdA 0.004162 | **500.78 km/h** | 497-501 | inside the band |
| speed at sea level, same point | **469.05 km/h** | ~469 | match |
| bus current, per channel | 33.67 A (202.0 A total) | 33.7 A | match |
| electrical power | 8.97 kW | - | - |

**Reconciliation of the 0.8 km/h gap to the 501 edge, stated rather than tuned away.** The quote
"497-501" is itself a CdA band at fixed 36.6 A: 497 km/h needs CdA 0.004258, 501 needs 0.004156.
The best measured value, 0.004162, therefore sits at the *top* of the quoted speed band, and the
model lands 0.22 km/h inside it. The residual is a CdA effect of +0.14 %, not a current or
efficiency error - so the constants are left alone and the band is reported as a band [MODEL].

Three independent hits against the measured board, which is what makes the copper basis safe to
reuse for a new design:

1. a 3.90 mm corridor on all four layers carries **50.3 A** at dT 20 K, against 36.6 A required
   (+37 % margin) - consistent with a board that passed at 36.6 A;
2. barrels for 33.67 A at 1.50 A each = **23**, exactly the 23 barrels the existing pad holds
   (and 40 A would need 27 - the known shortfall, reproduced);
3. 497 km/h at sea level needs **3.20 mm** of corridor, i.e. below today's 3.90 mm - the existing
   board is *power*-limited at 497 SL, not copper-limited, which is the honest explanation of why
   it delivers 469 there.

## 3. Speed table at 2 km ASL (rho 1.0066) and at sea level

Generated by `model.py`, reproducible. `I_phase` is per phase in each of the 6 channels;
`I_bus total` is the whole board; `corridor` and `barrels/ch` are the copper each speed demands
on the measured basis (dT 20 K, 1.50 A/barrel).

**2 km ASL, CdA 0.004162 (best)**

| km/h | I_phase A | I_bus total A | P_elec kW | shaft/motor kW | corridor mm | barrels/ch |
|---:|---:|---:|---:|---:|---:|---:|
| 450 | 26.6 | 146.6 | 6.51 | 0.95 | 1.62 | 17 |
| 500 | 36.4 | 201.1 | 8.93 | 1.30 | 2.50 | 23 |
| 550 | 48.5 | 267.7 | 11.88 | 1.73 | 3.71 | 30 |
| 600 | 63.0 | 347.5 | 15.43 | 2.24 | 5.32 | 39 |
| 625 | 71.2 | 392.8 | 17.44 | 2.54 | 6.30 | 44 |
| **650** | **80.0** | **441.8** | **19.62** | **2.85** | **7.41** | **50** |
| 675 | 89.6 | 494.8 | 21.97 | 3.20 | 8.66 | 55 |
| 700 | 100.0 | 551.8 | 24.50 | 3.56 | 10.06 | 62 |
| **720** | **108.8** | **600.5** | **26.66** | **3.88** | **11.31** | **67** |
| 750 | 123.0 | 678.7 | 30.13 | 4.38 | 13.39 | 76 |

**2 km ASL, CdA 0.0034 (optimistic)**

| km/h | I_phase A | I_bus total A | P_elec kW | shaft/motor kW | corridor mm | barrels/ch |
|---:|---:|---:|---:|---:|---:|---:|
| 450 | 21.7 | 119.8 | 5.32 | 0.77 | 1.22 | 14 |
| 500 | 29.8 | 164.3 | 7.29 | 1.06 | 1.89 | 19 |
| 550 | 39.6 | 218.7 | 9.71 | 1.41 | 2.81 | 25 |
| 600 | 51.4 | 283.9 | 12.60 | 1.83 | 4.02 | 32 |
| 625 | 58.1 | 320.9 | 14.25 | 2.07 | 4.76 | 36 |
| 650 | 65.4 | 360.9 | 16.02 | 2.33 | 5.60 | 41 |
| 675 | 73.2 | 404.2 | 17.95 | 2.61 | 6.55 | 45 |
| 700 | 81.7 | 450.8 | 20.01 | 2.91 | 7.61 | 51 |
| 720 | 88.9 | 490.5 | 21.78 | 3.17 | 8.56 | 55 |
| 750 | 100.4 | 554.4 | 24.62 | 3.58 | 10.13 | 62 |

**Sea level, CdA 0.004162 — for comparison only**

| km/h | I_phase A | I_bus total A | P_elec kW | shaft/motor kW | corridor mm | barrels/ch |
|---:|---:|---:|---:|---:|---:|---:|
| 450 | 32.3 | 178.4 | 7.92 | 1.15 | 2.12 | 20 |
| 500 | 44.3 | 244.7 | 10.87 | 1.58 | 3.28 | 28 |
| 550 | 59.0 | 325.7 | 14.46 | 2.10 | 4.86 | 37 |
| 600 | 76.6 | 422.9 | 18.78 | 2.73 | 6.97 | 47 |
| 625 | 86.6 | 478.0 | 21.22 | 3.09 | 8.25 | 54 |
| 650 | 97.4 | 537.7 | 23.87 | 3.47 | 9.71 | 60 |
| 675 | 109.1 | 602.1 | 26.73 | 3.89 | 11.35 | 67 |
| 700 | 121.7 | 671.5 | 29.82 | 4.34 | 13.19 | 75 |
| 720 | 132.4 | 730.7 | 32.45 | 4.72 | 14.83 | 82 |
| 750 | 149.6 | 826.0 | 36.67 | 5.34 | 17.55 | 92 |

**Sea level, CdA 0.0034**

| km/h | I_phase A | I_bus total A | P_elec kW | shaft/motor kW | corridor mm | barrels/ch |
|---:|---:|---:|---:|---:|---:|---:|
| 450 | 26.4 | 145.7 | 6.47 | 0.94 | 1.60 | 17 |
| 500 | 36.2 | 199.9 | 8.88 | 1.29 | 2.48 | 23 |
| 550 | 48.2 | 266.1 | 11.81 | 1.72 | 3.68 | 30 |
| 600 | 62.6 | 345.5 | 15.34 | 2.23 | 5.27 | 39 |
| 625 | 70.7 | 390.5 | 17.34 | 2.52 | 6.25 | 44 |
| 650 | 79.6 | 439.2 | 19.50 | 2.84 | 7.35 | 49 |
| 675 | 89.1 | 491.9 | 21.84 | 3.18 | 8.59 | 55 |
| 700 | 99.4 | 548.6 | 24.36 | 3.54 | 9.98 | 61 |
| 720 | 108.1 | 597.0 | 26.51 | 3.86 | 11.22 | 67 |
| 750 | 122.2 | 674.7 | 29.96 | 4.36 | 13.28 | 75 |

Reading: the sea-level table needs ~21.7 % more current for the same speed - that is exactly the
density ratio, and it is why a 650-at-sea-level board is a 720-at-2-km board. Note also that the
existing 36.6 A board lands at 500.8 km/h at 2 km: **it already beats the 497 pass threshold where
it matters**, and what it misses is the 600-650 band - 600 needs 1.72x its present current, 650
needs 2.19x.

## 4. THE FIVE NUMBERS

| # | case | I_phase (per phase, RMS) | I_bus total | P_elec | corridor | barrels/ch |
|---|---|---:|---:|---:|---:|---:|
| a | **497 km/h at sea level** | **43.5 A** | 240.3 A | 10.67 kW | 3.20 mm | 27 |
| b | **600 km/h at 2 km** | **63.0 A** | 347.5 A | 15.43 kW | 5.32 mm | 39 |
| c | **650 km/h at 2 km** | **80.0 A** | 441.8 A | 19.62 kW | 7.41 mm | 50 |
| d | **720 km/h at 2 km** | **108.8 A** | 600.5 A | 26.66 kW | 11.31 mm | 67 |
| - | **existing 36.6 A board at 2 km** | 36.6 A | 202.0 A | 8.97 kW | 3.90 mm | 23 |

- (a) 497 at SL needs **43.5 A**, i.e. 18.9 % more than the board's 36.6 A - that is the whole
  sea-level shortfall in one number (469.05 km/h delivered vs 497 asked).
- (c) is the design point: **80.0 A**, 2.19x the present phase current, 19.62 kW.
- (d) is 2.97x the present current, 26.66 kW.

Sensitivity, because it decides the answer more than the ESC does:

| case | CdA 0.0034 | CdA 0.004162 | CdA 0.0056 |
|---|---:|---:|---:|
| 650 @ 2 km, I_phase | 65.4 A | 80.0 A | **107.7 A** |
| 720 @ 2 km, I_phase | 88.9 A | 108.8 A | **146.4 A** |

At the pessimistic CdA the 650 target needs 107.7 A - the entire 720 ESC. **The CdA measurement is
worth more than the ESC specification**; measure it before cutting 3 oz copper.

## 5. TARGET ESC — 600-650 km/h at 2 km ASL

Design point 650 km/h, 2 km, CdA 0.004162: 80.0 A per phase, 441.8 A bus, 19.62 kW.

| item | target | check against the measured basis | verdict |
|---|---|---|---|
| phases / channels | **6**, unchanged, one 3-phase bridge each | keeps the 6 independent motor channels | OK |
| FETs per phase | **6 populated** (1 per switch position x 3 half-bridges), **12 sites available** | 12 sites is what makes the 720 swap a population change | OK |
| current per phase | **80.0 A RMS** (73.6 A bus per channel, 441.8 A board) | 2.19x today's 36.6 A | OK |
| copper weight | **3 oz outer (105 um) + 1.5 oz inner (52.5 um)** | same stack the 36.6 A board was measured on | OK |
| layers | **4**, single-sided, all components top, **no HDI** | 4L suffices - see below | OK |
| phase corridor | **7.41 mm** required at dT 20 K (3.90 mm today) | shared board builds 11.31 mm -> at 650 it runs at **~10 C** rise, not 20 K | OK, with margin |
| shunt barrels | **50 per channel = 300 board** (23 today = 138) | 73.6 A / 1.50 A per barrel = 49.1 -> 50 | OK |
| FET junction temp | 4.48 W per device, **161 W board**, needs **Rth_j-a <= 22.3 C/W** | at the 8 C/W spreader budget Tj = **85.9 C**; on the bare part (40 C/W) it is 229 C | **spreader is the enabling element, not an accessory** |
| board area | **449.9 cm2 = 155.15 x 290 mm** (+17.6 % on 382.71 cm2) | same width; length +43.2 mm | OK |

Why 4 layers and not 6: a 6L 3 oz stack would cut the corridor from 11.31 mm to 8.48 mm at 720,
but costs **+$567 to +$644 at 5 pcs** and needs the owner's explicit approval. The corridor is not
the binding constraint at 450 cm2, so **4 layers is the answer** and no approval is required.

**Free fallback, and the reason to buy 12 sites.** The 161 W board dissipation is the one number
that depends on an unmeasured thermal path. If the first article measures worse than 22.3 C/W,
populate the second FET bank - the pads are already there - and the same board becomes 1.12 W per
device, needing only 89.2 C/W (+36 FETs, +$166, **zero layout change**). That is a bench-test
decision, not a redesign.

## 6. UPGRADE ESC — 720 km/h at 2 km ASL

Design point 720 km/h, 2 km, CdA 0.004162: 108.8 A per phase, 600.5 A bus, 26.66 kW.

| item | upgrade | check against the measured basis | verdict |
|---|---|---|---|
| phases / channels | **6**, unchanged | - | OK |
| FETs per phase | **12 populated** (2 per switch position), 72 total - all sites full | conduction loss falls as 1/N | OK |
| current per phase | **108.8 A RMS** (100.1 A bus per channel, 600.5 A board) | 2.97x today's current | OK |
| copper weight | 3 oz outer + 1.5 oz inner (identical to target) | - | OK |
| layers | **4**, single-sided, no HDI | corridor 11.31 mm is exactly the 108.8 A / 20 K width | OK |
| phase corridor | **11.31 mm** (the target already carries it) | sized for 720, so no copper change on swap | OK |
| shunt barrels | **67 per channel = 402 board** | 100.1 / 1.50 = 66.7 -> 67 | OK |
| FET junction temp | 2.07 W per device, **149.1 W board**, needs **Rth_j-a <= 48.3 C/W** | at 8 C/W Tj = **66.6 C**; even the bare part (40 C/W) gives 132.8 C | OK |
| board area | **449.9 cm2 = 155.15 x 290 mm** - identical to target | one PCB, one tooling charge | OK |

**The counter-intuitive bit, stated so nobody trips on it:** the 650 variant dissipates *more*
(161 W) than the 720 variant (149 W), because conduction loss falls with the square of the
current per device. The 650 board is the thermally critical one, so the spreader is specified by
the target and the upgrade simply inherits the margin.

## 7. The swap question — is it simple?

**Yes. One PCB, two populations. The 650 ESC is the 720 ESC with half the FETs left off.**

That is the whole answer, and it is a design decision taken now, not a hope:

| element | shared specification (this is what to order) |
|---|---|
| bare PCB | **one part number**, 4L, 3 oz outer / 1.5 oz inner, 449.9 cm2, 155.15 x 290 mm |
| FET sites | **72 total** = 12 per channel = 2 per switch position |
| target population | **36 FETs** - one per switch position (A-bank only) |
| upgrade population | **72 FETs** - both banks |
| copper | corridor **11.31 mm** per channel and **67 barrels** per channel: 720-class in *both* variants |
| connectors | identical set - 6 phase harnesses, DC input, signal; same gate drivers, same shunt network, same firmware |
| mounting | same 155.15 mm width, same bolt pattern, same thermal interface plane / TIM / spreader |
| swap procedure | unplug the harnesses, 4 bolts, swap the board. **No harness, no airframe, no firmware change.** |

Nothing is derated on copper in the target: only silicon. So the swap is a population change, and
the only thing that changes is 36 FETs and their gate resistors.

**Why this beats "small board now, big board later":** a second outline would need its own tooling
charge, its own DRC pass, its own brackets and its own harness lengths - and then the "simple swap"
would touch the airframe. Sharing the outline turns the upgrade into a BOM line (+$166), not a
programme.

**Honest caveat:** because the PCB is identical, buying the target does not save any of the 720's
PCB cost - it saves the 36 FETs ($166). If the owner prefers 720 capability from day one, order
the full population instead and skip a swap entirely. The staged path is cost staging, not a
capability ladder, and the owner should know that before choosing it.

## 8. Cost — three boards, two fabricators

5 pcs each, 4-layer, 3 oz, 1.6 mm, at the **actual areas**. USD unless stated.

| board | area cm2 | PCBWay (USD) | Multi-CB (EUR) | Multi-CB (USD @1.08) | PCBWay 6L 3 oz |
|---|---:|---|---|---|---|
| existing 36.6 A | 382.71 | **$444-865** (mid 654) | **EUR 423-564** | $457-610 (mid 533) | $940-1,439 |
| **target 650** | 449.94 | **$522-1,048** (mid 785) | **EUR 498-664** | $538-717 (mid 627) | $1,089-1,692 |
| **upgrade 720** | 449.94 | same bare PCB | same bare PCB | same bare PCB | same |

Lead time: PCBWay heavy copper **5-10 build days** (plus shipping); Multi-CB **5 working-day tier**
(heavy copper is "special production" there). Currency as quoted: USD / EUR.

**Increments**

| step | cost | what changes physically |
|---|---|---|
| **target over existing** | **+$131** (PCBWay mid) / **+$94** (Multi-CB mid) | +67 cm2 area, corridor 3.90 -> 11.31 mm, barrels 23 -> 67 per channel. FET count unchanged at 36. |
| **upgrade over target** | **+$166** = 36 FETs @ $4.00 ($144; range $90-234) + $22 assembly | FETs only. PCB, harness, mounts and thermal interface unchanged. |

**Provenance of these prices, because two of the four rows are estimates.** The 1 oz rows are
vendor list prices [LIST]: PCBWay $116 for 4L 150x100 mm and $48 for 4L 100x100 mm (the $116 page
was fetched live during this session and matches the programme's record), Multi-CB EUR 59 for 4L
and EUR 98 for 6L at 80x100 mm. The 3 oz rows are [EST] = 1 oz list x the published heavy-copper
multiplier of 1.5-2x, because **no house publishes a 3 oz list price and both quote-gate heavy
copper**. The estimator is the same one used in `evidence/esc-layer-cost/03_prices.md`, and it
reproduces that report's $450-870 at 382.71 cm2 exactly - no new pricing assumption has entered.
A formal quote is required from both houses before any PO; treat the ranges as the estimator's
spread, not the fabs'.

## 9. The cheapest levers, ranked by km/h per dollar

All measured from the 650 km/h @ 2 km base point (80.0 A, 19.62 kW, CdA 0.004162).

| lever | what it buys | mechanism | cost | km/h per $ |
|---|---|---|---:|---:|
| **cell count 16S** (59.2 V nom) | **+65.4 km/h** | v ~ V^(1/3) at fixed phase current | ~$100 | **0.654** |
| **ESC swap to 720** | **+70 km/h** | more silicon, same copper | **$166** | **0.422** |
| cell count 14S (51.8 V nom) | +34.3 km/h | same | ~$100 | 0.343 |
| **CdA -1 %** | **+2.18 km/h** | v ~ CdA^(-1/3) | ~$75 | 0.029 |
| **prop +1 point** (0.72 -> 0.73) | **+3.0 km/h** | v ~ eta^(1/3) | ~$250 | 0.012 |

Costs in the aero and prop rows are `[EST]` planning figures, not quotes (the ESC row is the priced
one). The ranking is insensitive to them: even at a third of those costs, prop stays 30x behind 16S.

- **Prop efficiency:** +1 point = +3.0 km/h at 650 (and +3.3 at 720). It is the *weakest* lever per
  dollar on the board by a factor of 50 - do not spend the effort here first.
- **CdA:** -1 % = +2.18 km/h at 650, +2.4 at 720; -10 % = **+22.6 km/h**. Aero is not cheap per
  point, but it is also the lever that *reduces* ESC current, so it pays twice.
- **Cell count:** at fixed phase current, 14S = +34.3 and 16S = **+65.4 km/h** (v ~ N^(1/3)). At
  fixed *power*, current falls 14.3 % (14S) or **25 % (16S)** - 650 at 2 km then needs **60.0 A**
  (16S) instead of 80.0 A, a corridor of 4.98 mm and 37 barrels instead of 7.41 mm and 50.
- **Voltage margin:** the 100 V FETs see 58.8 V max at 14S (59 % of rating) and 67.2 V at 16S
  (67 %) - both comfortable, 33 % headroom at 16S. The FETs are not the limit.

**Two things the cell-count lever does not solve, both of which must be checked before buying a
pack:** (1) the 12S design's bulk capacitors are typically 63 V parts - a 16S retap needs them
re-rated to 80 V or more, and that is a board change, not a pack change; (2) motor Kv rises with
voltage, so 16S spins the props 33 % faster - if the tips sit at 0.6 Mach today they sit near
0.8 Mach at 16S on a 2 km day (a ~332 m/s sound speed), which is a noise, efficiency and flutter
question, not an ESC question.

**Ranked conclusion:** 16S is the cheapest speed in the programme (0.65 km/h per $), and the ESC
swap the owner already asked for is second (0.42) - because it is 36 FETs, not a new board.
Prop work is last. But the *first* dollar should go to measuring CdA, because the 0.0034-0.0056
band moves the required current by 65 % and no component choice fixes that.

## 10. Residuals — what this report does not verify

1. **CdA dominates every other uncertainty.** 650 @ 2 km runs 65.4 A at CdA 0.0034 and 107.7 A at
   0.0056. Everything else in this model is worth +-3 %. Measure CdA before releasing copper.
2. **The spreader Rth of 8 C/W is an analytical budget, not a measurement** (junction-to-case ~0.6,
   TIM ~1.44, spreader + forced convection 2-8 C/W). It is the one number that decides whether the
   36-FET target passes its 22.3 C/W requirement. Bench-verify on the first article; the free
   fallback is populating the second FET bank.
3. **3 oz prices are quote-gated at both houses.** The 1 oz rows are real vendor list prices; the
   3 oz rows are list x the published 1.5-2x heavy-copper multiplier. Get formal quotes.
4. **The FET unit price ($4.00, range $2.50-6.50) is the only unverified BOM line.** Web search was
   unavailable in this session (the configured provider "duckduckgo" is not registered), so the
   IPTC014N10NM5 datasheet could not be pulled and its 1.4 mOhm / 175 C / RthJA 40 C/W figures are
   taken as given by the programme, not independently re-checked here.
5. **No KiCad DRC or ERC was run.** This is a specification, not a layout. The corridor and barrel
   numbers are the basis a layout must be checked against, on the same basis as
   `esc-ampacity-basis` and `esc-3oz-bigboard`.
6. **The 290 mm length assumes the envelope can grow 43 mm.** If it cannot, the only 4-layer
   alternative is 6 layers (corridor 11.31 -> 8.48 mm) at **+$567 to +$644** for 5 pcs, which needs
   the owner's explicit approval.
7. **Thermal at altitude is modelled at Ta = 50 C** (avionics bay). ISA at 2 km is 11.5 C; a cold
   airframe is more forgiving, a heat-soaked one is not. That is why the pass is quoted against
   150 C, not 175 C.