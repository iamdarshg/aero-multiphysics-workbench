# ESC per-phase current, derived from the aircraft it flies in

**Unit:** fab-readiness wave 8 — `esc-motor-demand`
**Date:** 2026-11-16
**Question:** everything about the ESC is blocked on 60 A per phase. Is 60 A the right number?
**Short answer:** no. The design point needs **16.8 A per phase**. The hard ceiling the
aircraft can ever draw is **40 A**, and that ceiling is the *battery*, not the board. 60 A is
2.664 kW ÷ 44.4 V — a *desired input power* from a decision record written for a **four-motor,
8 kg** aircraft — which was later relabelled "phase current" and then assumed as a continuous
requirement. It is conservative by 3.6× at the design point and unreachable as a continuous
rating. **The ESC is nearly done at 4 oz, and passes continuous at 2 oz.**

All numbers below are produced by [`derive.py`](derive.py), which parses every input out of the
repos and refuses to emit if any of **13 controls** fail. Outputs:
[`derive.log`](derive.log), [`derive.json`](derive.json).

---

## 0. Verdict box

| quantity | value | tier |
|---|---|---|
| **phase current at the 720 km/h design point** | **16.8 A** | ANALYTICAL (Froude chain, 13/13 controls) |
| — over my own FOM band (0.72–0.82) plus the reconciled meanline | **14.7 – 22.2 A** | ANALYTICAL |
| — over **the spec's own stated** 0.7–1.3 kW per motor | **17.1 – 31.8 A** | ANALYTICAL |
| — over the whole spec CdA band | up to **37.2 A** (CdA 0.0015) / 77.7 A at 0.0030, which is **not deliverable** | ANALYTICAL |
| **worst sustained case (180 km/h climb, TWR 1.1)** | 44.5 A — needs 245 A of a 240 A pack, i.e. at the cap | ANALYTICAL |
| **hard ceiling, specified 12S 1.6 Ah 150C pack** | **40.0 A/channel** (240 A ÷ 6) | MEASURED (pack arithmetic) |
| **60 A per phase** | **not the design current. 3.6× conservative at cruise, 1.5× above the pack, and never derived from this aircraft** | — |
| binding assumption | **CdA at 720 km/h** = 0.000693 m², which the spec itself calls *"UNRESOLVED — #1 gate"* | ASSUMED |

The unattainable ideal (FOM 1.00) is 12.1 A; it is listed in §10 for completeness and is not part of
the band, because a real 80 mm ducted fan does not achieve it.

---

## 1. Which aircraft and which motor — the repo holds three, and they are not the same

Before any current can be computed the configuration has to be identified, because the repo is
internally split into three mutually exclusive powertrains. This is the first finding and it is
not cosmetic: each one gives a different current.

| family | duct | motor | battery | all-up | 720 km/h bus power | where |
|---|---|---|---|---|---|---|
| **P9/10/11** | 90 mm, geared | 6 × Flycci FA4119 350KV, 7 pp, 12.5 krpm | 2 × Turnigy 6S 5000 (12S 5 Ah) | **11.5 kg** | **13.0 kW** (meanline) | `phase9_geometry_mass_summary.json:17,43` |
| **P15** | 80 mm, 3 rows/duct, direct | 6 × **Rocket 3670** 4-pole, rewound ~925 KV, 41 krpm | 2 × Bonka 6S 1600 150C (12S 1.6 Ah) | **6.72 kg** | **4.11 kW** (loss stack) | `PHASE15_DESIGN_SPEC.md:302,358,422` |
| **drone-arm decision record** | 8×4.5 prop, no duct | 4 × FA4119 | 12S | **8 kg** | — | `FA4119_PROPULSION_DECISION.md:40-45` |

**I use the P15 family**, because that is the one the *as-built CAD geometry* matches
(`phase15_generate_geometry.py:104-106` builds a Ø42 × 72 motor envelope per duct row, mass
0.274 kg — the 3670 can), and the one the *airframe mass of record* matches. I carry the P9
meanline as the pessimistic alternative and show in §6 why its power figure cannot be used.

> **The 60 A does not belong to any of these three.** It comes from the *fourth* configuration —
> the drone-arm decision record — and §7 traces it line by line.

---

## 2. The motor

**Selected unit:** Surpass Hobby "Rocket" 3670, 4-pole (2 pole pairs), 1550 KV stock, rewound to
~925 KV for direct drive.

| property | value | citation |
|---|---|---|
| make/model/class | **Surpass Hobby "Rocket" 3670 4-pole, 1550 KV**, "3670-class" outrunner | `drone-mech/highspeed_edf/design/PHASE15_DESIGN_SPEC.md:302` |
| can size | **Ø36 × 70 mm** — **listing/spec tier only, no vendor drawing in the repo** | `PHASE15_DESIGN_SPEC.md:302` |
| CAD envelope built | **Ø42 × 72 mm**, mass 0.274 kg/row (deliberately padded, labelled "envelope") | `phase15/optimization/phase15_generate_geometry.py:104,105,106,968-970` |
| pole count | **4 poles = 2 pole pairs**, mandatory (no gearbox → direct drive) | `PHASE15_DESIGN_SPEC.md:307` |
| KV | 1550 stock → **925 KV target after rewind** (×1.68 turns, phase R ×2.81) | `PHASE15_DESIGN_SPEC.md:302,308`; `phase15_losses_and_config.py:123,136` |
| mass each | **120 – 220 – 280 g** (band); CAD uses **274 g**; P9 builds 280 g | `PHASE15_DESIGN_SPEC.md:304`; `phase15_generate_geometry.py:106` |
| max power (stock) | **~1600 W** — a *stock* listing figure, not a rating of this motor | `PHASE15_DESIGN_SPEC.md:302` |
| **max continuous current** | **NOT AVAILABLE.** The spec refuses to state one: *"re-derive after rewind; do not quote stock … the continuous rating may fall BELOW stock, not above it"* | `PHASE15_DESIGN_SPEC.md:305` |
| continuous input at 720 | **0.7 – 1.3 kW** needed per motor | `PHASE15_DESIGN_SPEC.md:305` |
| peak 30 s input | 2.0 – 2.6 – 3.4 kW | `PHASE15_DESIGN_SPEC.md:306` |
| **thrust at the design point** | **NOT AVAILABLE.** There is no motor, fan or thrust data anywhere in either repo — no dyno, no bench, no test stand. | — |

**This matters for instrument discipline.** The `esc-motor-demand` chain cannot start from a
measured motor map, because none exists. It starts from *airframe drag* instead — which is the
one quantity in the programme with real inputs — and works **towards** the motor. So the motor's
efficiency enters as an assumption (η = 0.90, `phase15_losses_and_config.py:37`), not as data.

**Note the motor selection itself is unvalidated:** the 1550 KV is a retail listing number, the
925 KV is a *rewind target* ("a target, not a value to print on the motor before spin
measurement" — `FA4119_PROPULSION_DECISION.md:169`), and no winding has been measured. The
entire motor side of this aircraft is ANALYTICAL.

---

## 3. The propulsor — and a correction to the brief

**As-built propulsor** (`phase15_generate_geometry.py:35-57`, `PHASE15_DESIGN_SPEC.md:166-199`):

| item | value |
|---|---|
| duct count / layout | **2, side-by-side at X ±44 mm (88 mm centres)** |
| duct OD / bore | 82.0 / **78.0 mm** |
| fan OD | 72 – **80** – 90 mm |
| hub | 34 – **40** – 46 mm |
| rows per duct | **3 rotor rows + 3 stator rows** (6 motors, 3/duct) |
| rotor blades per row | **13 / 12 / 11** (spec allows 10–12–14) |
| stator vanes per row | **23 / 21 / 19** (spec allows 17–21–25) |
| rotor chord | **16 mm**, radial span 20 mm |
| rpm per row | **36,000 / 41,000 / 47,000**; design point **41,070 rpm** |
| tip speed at design | **π × 0.080 × 41070/60 = 172.0 m/s** |
| tip Mach at 3 km | **0.459 / 0.523 / 0.599** across the three rows (a = 328.6 m/s) |
| annulus, both ducts | 2 × π/4 × (0.078² − 0.040²) = **70.43 cm²** |

Two independent checks that this area basis is the real one, not a guess:
`DUCT_ID (78.0) == FAN_MM − 2 (78.0)` and `HUB_D (40.0) == HUB_MM (40.0)` to the digit; and
70.43 cm² sits inside the spec's own 55 – 70 – 90 cm² annulus band.

### The CFD case is NOT a duct — correcting the brief

The brief says *"U_inf 222.1322 m/s and Aref 0.062249 m² — that is a duct, so the prop is inside
it."* **It is not a duct.** It is a half-wing sector, and the arithmetic proves it:

```
Aref = sector span × lRef = (260.00 − 80.33 mm) × 0.34646 m
     = 0.17967 m × 0.34646 m = 0.0622485 m²        (claimed 0.062249 — 8 ppm)
```

Candidates and citations:

| evidence | value | source |
|---|---|---|
| case name | **`wing_t30mm`** | `phase15/fsi/cases/wing_t30mm/fluid/` |
| source geometry | *"Phase-15 nominal wing section schedule; **outboard sector x=80.33..260 mm**"* | `candidate.json:3` |
| inflow | `internalField uniform (0 0 200.0)` → **200.0 m/s = 720 km/h**, not 222.13 | `0/U:11` |
| free stream | flowSpeedMps **200.0**, altitude 3000 m, AoA 0.5°, **M 0.6087**, q 18,180 Pa | `candidate.json:5-9` |
| force object | `type forces; patches (fsi); rhoInf 0.909` — no `forceCoeffs`, **no Aref in the case at all** | `system/controlDict:24-29` |

So the case is a **wing-drag** instrument. It cannot produce propulsive power, and its `Aref` was
never a duct reference area — it is `sector span × lRef`, squared off. The 222.1322 m/s figure
belongs to a *different* run of the same wing sector (799.7 km/h); either way it is a wing, and
either way it says nothing about the fan.

**Consequence:** there is **no duct or fan CFD anywhere in the programme.** The only duct CFD is
`docs/diagnostics-2026-11-10/compressible_audit_cfd_duct_compressible_diagnostic_lowflow.json`
— 7,008 cells, Mach 0.09, whose own file says *"unvalidated isolated duct; solver residual stop
alone is not evidence of converged performance."* So the fan efficiency used in §6 is an
**assumption**, and it is the second-largest lever after drag.

---

## 4. The battery — 12S confirmed, and it binds

| property | value | citation |
|---|---|---|
| flight basis | **12S LiPo, 50.4 V maximum** | `drone-arm/docs/hardware/REV_B_ARCHITECTURE.md:16` |
| sprint pack | **2 × Bonka 6S 1600 mAh 150C → 12S 1.6 Ah, 240 A** | `PHASE15_DESIGN_SPEC.md:358` |
| energy | 1.6 Ah × 44.4 V = **71.0 Wh**; **60.4 Wh usable** (85 %) | `PHASE15_DESIGN_SPEC.md:154-155` |
| C needed at 720 | 75 – 100 – **150 C** | `PHASE15_DESIGN_SPEC.md:360` |
| pack R0 assumed | 10 – 20 – 30 mΩ (**assumed, never measured**) | `PHASE15_DESIGN_SPEC.md:364` |
| TVS | **SM8S51A, 51 V standoff** → consistent with 50.4 V max, i.e. 12S | `REV_B_ARCHITECTURE.md:157` |
| other packs in the repo's list | 4200/35C = 147 A; 1300/130C = 169 A; 5200/35C = 182 A | `phase15_robu_final_config.py:56-61` |

**The 12S question asked in the brief is settled, and both routes agree:** a 51 V standoff TVS
cannot protect a 6S bus (25.2 V) and the architecture doc says 50.4 V outright. The earlier
"Bonka 6S 1600" record was **two** packs in series, which is 12S — I confirmed this the hard way
by initially computing 3.2 Ah and having my own control fail (§9, C3), which is why the Ah figure
in this report is 1.6 and not 3.2.

**The pack is the binding power source, and no ESC analysis in the programme has used this fact:**

```
1.6 Ah × 150 C = 240 A  →  240 / 6 channels = 40.0 A per channel, absolute.
```

60 A per channel requires **360 A** — that is **225 C** on the 1.6 Ah sprint pack. Nothing in the
repo's battery list exceeds **182 A** (5200/35C); the best is **240 A** (Bonka 1600/150C).
**The ESC's 360 A aggregate rating exceeds its own power source by 1.5×**, and every pack in the
BOM is therefore incapable of feeding it.

---

## 5. Mass and thrust requirement

**Six motors: yes.** `PHASE15_DESIGN_SPEC.md:301` — *"Count | 6 (2 ducts × 3 rows) | hold | Rev-B
is 6-ch"*. The duct, not the motor, makes the thrust: 3 stages in series per duct, 2 ducts.

**Which mass to use — and why the 472.273 g is not it.** The body of record is 472.273 g
(band 372–1088 g), but the spec budgets the lifting-body shell at **0.20 – 0.27 – 0.38 kg**
(`PHASE15_DESIGN_SPEC.md:413`). The measured body is therefore **92 g above the shell's own
ceiling** — a real finding, but it is one line of a 13-line mass table. Using 472 g as "the
aircraft" would understate all-up mass by **14×**.

I use **6.72 kg** — the spec's own row-summed all-up (`PHASE15_DESIGN_SPEC.md:422`,
4.3 – 6.72 – 8.5 kg), which also lands within 2.7 % of the 6.541 kg the coupled-design screen
uses (`phase15_aero_multiphysics_screen.py:77`). The superseded 11.5 kg P9 figure is not used.

| mission point | thrust required | basis |
|---|---|---|
| **cruise 720 km/h, 3 km** | **12.60 N total** (2.10 N/motor, 6.30 N/duct) | drag at CdA 0.000693, q ≈ 18.18 kPa |
| cruise at the spec's CdA ceiling | 54.55 N | CdA 0.0030 m² |
| **climb 180 km/h, TWR 1.10** | **72.5 N** | 1.10 × 6.72 × 9.80665 |
| **static, TWR 1.0 → 2.1** | **65.9 N → 138.4 N** | spec's own static TWR band |

Per-phase "thrust" is not a well-defined quantity on a ducted multi-stage fan — one duct's three
stages share one annulus — so the requirement is stated per duct and per aircraft, not per motor.

---

## 6. The chain, with the arithmetic

Froude / actuator-disk, `derive.py:cruise()`, at V₀ = 200 m/s, ρ = 0.909128 kg/m³ (3 km ISA),
A = 0.007044 m² (two ducts), FOM 0.72, η_motor 0.90, η_esc 0.97:

```
 1  drag        T   = ½·ρ·V₀²·CdA = ½ × 0.909128 × 200² × 0.000693      =  12.60 N
 2  induced     vi  = ½(−V₀ + √(V₀² + 2T/ρA))                            =   4.81 m/s
 3  disk work   P_d = T(V₀ + vi) = 12.60 × 204.81                        = 2 580.6 W
 4  shaft       P_s = P_d / FOM = 2580.6 / 0.72                          = 3 584.2 W
 5  electrical  P_e = P_s / (η_m·η_e) = 3584.2 / (0.90 × 0.97)           = 4 105.6 W
 6  bus current I_dc = P_e / 44.4                                        =   92.5 A  total
 7  per motor   I_dc / 6                                                 =   15.4 A
 8  PHASE RMS   I_ph = I_dc/0.92  (repo convention, robu:114)            =   16.8 A
```

**Steps 1–7 reproduce the repo's own published loss stack to 0.03 W**
(`phase15_losses_and_config.json`: `bus_power_w 4105.6`, `ideal_disk_power_w 2580.6`,
`pack_current_a 92.5`, `useful_thrust_power_w 2520.1` — all four match). That is the control
that licenses the chain.

**Peak or RMS?** **RMS, and it is the phase-winding current.** The ESC's `0.5 mΩ` shunt sits in
the phase leg (`REV_B_ARCHITECTURE.md:41`), the DRV8353S CSAs measure phase-leg current, and the
60 A contract is written "A RMS/channel" (`PHASE15_DESIGN_SPEC.md:337`). The conversion from DC
bus to phase RMS is convention-dependent, and I quote the repo's own — the *most* conservative of
the three:

| convention | I_ph / I_dc | at 15.4 A bus |
|---|---|---|
| **repo: I_dc / 0.92** (`robu_final_config.py:114`) | **1.087** | **16.8 A** ← used |
| fundamental, m = 1, cos φ = 1.0 | 0.943 | 14.5 A |
| fundamental, m = 1, cos φ = 0.90 | 1.048 | 16.1 A |

The motor runs at the voltage ceiling by design (925 KV × 44.4 V = 41,070 rpm = the fan's design
speed), so m ≈ 1 is the correct regime. **The physical phase current is therefore ~14.5–16.1 A;
16.8 A is the conservative quote.**

### Why the other instrument's 13 kW is not used

The P9 meanline prints `cycleBusPowerW = 13,013.7` for the same 720 km/h point — **3.2× my
4,106 W**. I tested whether it can be used, and it cannot, on its own numbers:

| quantity the meanline itself supplies | J/kg |
|---|---|
| isentropic rise it charges the fan for (`overallPressureRatio 1.0617`) | **4 658.8** |
| jet kinetic rise its own nozzle produces (`Vj 209.72 m/s`) | **1 990.9** |
| what its own outlet PR (`1.0407`) would give | **3 097.7** |

Three numbers for one machine, spread **2.34×**. It charges 4,659 J/kg and delivers 1,991 J/kg of
jet energy — the difference has nowhere to go. **So its power is rejected**; a meanline that
charged its *own jet* would print **5,440 W = 22.2 A phase**, not 53.1 A. Its thrust closure
(1.0202×) is fine and unaffected — only the power column is unusable.

That reconciled 5,440 W is the top of my honest band, and it sits **5.7× closer to the loss
stack (4,106 W) than to the printed row (13,014 W)** — the printed figure is the outlier, not
the chain.

---

## 7. Where 60 A actually came from — the provenance

This is the whole answer to the brief's question, and it is four lines in two repos:

| # | statement | source |
|---|---|---|
| 1 | *"Desired nominal input per motor \| approximately **2.7 kW**"* | `FA4119_PROPULSION_DECISION.md:42` |
| 2 | *"Desired current point \| approximately **60 A** at nominal 12S"* | `FA4119_PROPULSION_DECISION.md:43` |
| 3 | *"44.4 V x 60 A = 2.664 kW"* — the derivation, written out | `FA4119_PROPULSION_DECISION.md:50-54` |
| 4 | *"60 A continuous design current per motor channel"* | `REV_B_ARCHITECTURE.md:18` |
| 5 | *"Phase current, continuous \| ≤60 A RMS/channel (hard)"* | `PHASE15_DESIGN_SPEC.md:337` |

So **60 A is a desired input power divided by a nominal voltage** — a *bus* current, backwards
from a power target. By step 5 it has become a *phase RMS* current, and by `REV_B_ARCHITECTURE:18`
it is a *continuous design current* with no derivation attached at all.

And the aircraft that 2.7 kW was desired for is not this one:

| the decision record says | the P15 aircraft is |
|---|---|
| **4 motors** (`FA4119_PROPULSION_DECISION.md:40`) | **6 motors** (`PHASE15_DESIGN_SPEC.md:301`) |
| **8 kg** (`:45`) | **6.72 kg** (4.3–8.5) |
| 8×4.5 open prop, no duct (`:196`) | 2 × 80 mm ducted, 3 rows |
| 20 kgf aspirational static (`:46`) | 12.3 kgf at 6 × 60 A |

**Two independent reasons 60 A is not this aircraft's number:** the aircraft needs 0.68 kW per
motor at 720 km/h, not 2.7 kW (4× less); and the specified pack cannot deliver 60 A per channel
even if it did (40 A ceiling).

There is exactly one way to derive 60 A from the P15 aircraft — 8.5 kg, 180 km/h, TWR 1.10, at
the CdA ceiling — and that case **needs 335 A from a 240 A pack** and lands at 60.7 A only because
it is 40 % outside what the battery can do. It is not a design point; it is an infeasibility.

---

## 8. What this means for the ESC

I do not re-derive the board's capacity figures; I use the ones already measured in earlier waves
(2 oz → **22.9 A**, 4 oz → **48.0 A**, thermal 52.0 / 35.9 / 26.8 A at R_thJA 22.4 / 40 / 62 °C/W).
**Caveat on the 2 oz number:** earlier waves carry *two* figures for it — **20.8 A**
(`02_widths.log`, 0.4542 mm²) and **22.9 A** (the branch report's "max current per phase"). I use
the higher, 22.9 A, so the margin below is not understated *for that reading*; at 20.8 A the cruise
still passes at **1.24×** and no conclusion below changes.

| channel rating | vs 16.8 A cruise | vs 40 A pack cap | static thrust / TWR it can make | verdict |
|---|---|---|---|---|
| **2 oz — 22.9 A** | **PASS, 1.37×** | FAIL (0.57×) | **63.3 N / 0.96** | buildable today; cruise-only; needs a catapult |
| **40 A — the pack cap** | **PASS, 2.39×** | **PASS, 1.00×** | **91.8 N / 1.39** | **the real channel requirement** |
| **4 oz — 48.0 A** | **PASS, 2.87×** | **PASS, 1.20×** | **103.7 N / 1.57** | **covers everything the aircraft can do** |
| 60 A contract | PASS, 3.58× | PASS | 120.3 N / 1.83 | unreachable: needs 361 A from a 240 A pack |

**Thermal:** at 16.8 A the board passes at **all three** R_thJA — even 62 °C/W (26.8 A). The heat
spreader is only mandatory if the channel must carry the pack cap (40 A > 35.9 A at 40 °C/W).

**The battery rail, re-costed at the real current.** The rail carries the *bus* current of one
channel (15.4 A at cruise), not the phase current. BATP's measured 23.1 A min-cut capacity:

- at the **16.8 A design point → 1.50× PASS** (it needs 15.4 A on the bus);
- at the **40 A pack cap → 0.58× FAIL** (it needs 40 A on the bus).

So **the rail fails only if the channel is sized to 60 A.** At the real design current BATP
passes with 50 % margin and BATN's 47.4 A barrel limit is 3× clear. This is the same failure mode
as everything else on this board: *sized to 59.05 A, judged at 59.05 A.*

**What I would do:** rate the channel at **40 A continuous** — the pack's limit, not the desire's
— and choose 4 oz. That number is derivable, it is 1.2× covered by the 4 oz geometry, it covers
every case the aircraft can actually fly, and it retires the heat-spreader argument for
everything except launch. **Do not quote 60 A again without this chain attached.**

---

## 9. Instrument discipline

`derive.py` will not emit unless all controls pass. **13 run, 13 PASS, 0 FAIL**, plus one
instrument-rejection test that must also fire.

| # | control | result |
|---|---|---|
| 1 | reproduce repo loss stack: `bus_power_w` | 4,105.63 vs **4,105.6** |
| 2 | reproduce repo loss stack: `ideal_disk_power_w` | 2,580.64 vs **2,580.6** |
| 3 | reproduce repo loss stack: `pack_current_a` | 92.47 vs **92.5** |
| 4 | reproduce repo loss stack: `useful_thrust_power_w` | 2,520.10 vs **2,520.1** |
| 5 | meanline 13 kW row from its own ṁ, PR, FOM, η | 12,729.7 vs 13,013.7 (2.2 %) — self-consistent, so its *shape* is right |
| 6 | pack cap = 150 C × 1.6 Ah = 240 A → 40 A/ch | PASS **after I fixed my own series/parallel error (3.2 → 1.6 Ah)** |
| 7 | tip Mach from π·D·rpm/a inside the spec band | 0.524, band 0.42–0.50–0.70 |
| 8 | `Aref` = sector span × lRef | 0.0622485 vs 0.062249 (8 ppm) |
| 9 | 60 A provenance: 44.4 × 60 = 2,664 W | PASS — matches the "2.7 kW desired" |
| 10 | annulus inside the spec's 55–70–90 cm² band | 70.43 cm² |
| 11 | **negative control** — 180.00 mm must give a *different* Aref | 0.062363 ≠ 0.062249 (must differ) |
| 12 | CAD `DUCT_ID` == `FAN_MM−2`, `HUB_D` == `HUB_MM` | 78.0 == 78.0, 40.0 == 40.0 |
| 13 | row tip Mach at 36/41/47 krpm all inside band | 0.459 / 0.523 / 0.599 |
| **R** | **rejection test** — the meanline's three energy statements must disagree | spread **2.34×** → its power is refuted, and the run halts if it is not |

The one instrument I **reject** is the P9 meanline's power column (§6), and I reject it on its own
numbers rather than on a preference. The one number I **correct** is my own 3.2 Ah (§4).

---

## 10. What I could not find, and how much it moves the answer

| missing | tier | how much the answer moves |
|---|---|---|
| **CdA at 720 km/h** — *"UNRESOLVED — #1 gate"* (`PHASE15_DESIGN_SPEC.md:244`) | ASSUMED 0.000693 | **This is the binding assumption.** CdA 0.0015 → **37.2 A** (+122 %); CdA 0.0030 → 77.7 A (+364 %), but that case needs 429 A of a 240 A pack, i.e. **not deliverable at all**. If drag is 2× worse, the answer is 37 A, still under 40, still under 60. |
| **installed fan FOM** — 0.72 is an analyst estimate (`:61`) | ASSUMED | 0.62 → 19.5 A (+16 %); 0.82 → 14.7 A (−12 %); ideal 1.0 → 12.1 A. Second-largest lever; bounded. |
| **motor efficiency & no-load losses** — no map, no dyno, no measured winding | ASSUMED 0.90 | ±10 % on η_m moves phase current ±10 %. |
| **motor continuous current rating** — spec refuses to quote it (`:305`) | ABSENT | Does not move the aircraft answer; it moves whether the *motor* survives 16.8 A, which is a different question and unanswerable today. |
| **thrust, anywhere** — zero measured thrust in the programme | ABSENT | My chain derives thrust from drag and never needs a measured fan map, which is why it holds. But it means no thrust number here is MEASURED. |
| **battery DCIR** — 10/20/30 mΩ assumed (`:364`) | ASSUMED | Affects sag and heat, not the commanded current — **but the heat is not small**: at the 92.5 A *total* bus current, I²R₀ = **86 / 171 / 257 W** (I first wrote 7–21 W by putting one channel's 15.4 A through the whole pack; that is a per-channel number and the pack carries all six). The spec's own 142–285–427 W at 5.3 kW agrees with the 92.5 A arithmetic, so the model is consistent. |
| **the P9 vs P15 vs drone-arm configuration split** (§1) | ABSENT | **The largest structural risk.** If the P9 family is the real aircraft, cruise power is 13.0 kW (unreconciled) or 5.4 kW (reconciled) → 53 A or 22 A. **Even the pessimistic reconciliation is under 60 A.** |
| a duct/fan CFD | ABSENT | Would replace the FOM assumption with a number. None exists; the only "duct CFD" is 7,008 cells at Mach 0.09 and its own file disclaims it. |

**The answer is robust at the level that matters:** every reconciled route lands between **14 A and
40 A**. The pack cannot exceed 40 A. **60 A is above the ceiling imposed by the aircraft's own
battery on every route**, and the only paths that reach or exceed it (CdA 0.0030, the 8.5 kg TWR
1.1 climb) are separately infeasible on that battery.

---

## 11. Contradictions found in the repo (for the board, not fixed here)

1. **Three powertrains in one repo**, none reconciled: 90 mm/FA4119/5 Ah/11.5 kg vs
   80 mm/Rocket 3670/1.6 Ah/6.72 kg vs the drone-arm record's 4-motor/8 kg/8-inch-prop design.
2. **`PHASE15_DESIGN_SPEC.md:170` says "Duct layout | side-by-side | NOT coaxial"**, while
   `phase15_generate_geometry.py:970` notes *"overlaps adjacent **coaxial** cans"* — the second
   refers to the 3 stages sharing one axis, which is correct; the words collide but the geometry
   is consistent. Recorded so it is not re-flagged as a defect.
3. **The measured body (472.273 g) exceeds the spec's lifting-body shell ceiling (0.38 kg) by
   92 g** (`PHASE15_DESIGN_SPEC.md:413`). The mass table is stale against the body of record.
4. **All-up mass exists as 4.3–6.72–8.5 kg, 4.5–6.7–8.5 kg, 6.541 kg, 11.5 kg and 10.5 kg** in
   five different files. I used 6.72.
5. **`REV_B_ARCHITECTURE.md:18` states 60 A as a design current with no derivation**; the only
   derivation in either repo is `FA4119_PROPULSION_DECISION.md:50-54`, and it is a *power*
   division for a *four*-motor aircraft.
6. **The 360 A aggregate is 1.5× the best battery in the BOM** (240 A). No ESC document mentions
   this. It is not a pad-clearance issue, so no DRC or thermal instrument could ever have seen it.

---

## 12. Files

| file | what it is |
|---|---|
| [`derive.py`](derive.py) | the instrument: parses the repos read-only, 13 controls, refuses to emit on failure |
| [`derive.log`](derive.log) | full run output (controls, chain, sensitivity) |
| [`derive.json`](derive.json) | machine-readable results + every citation with file:line |
| [`check_report.py`](check_report.py) | **reconciles this document to the instrument**: 29 headline figures must exist in `derive.log` *and* here, and a corrected figure may not appear as a live claim — it fails closed |
| [`cites.py`](cites.py) | citation index printer (provenance audit) |
| `REPORT.md` | this document |

Reproduce everything:

```powershell
cd E:\engineering-portfolio-audit\evidence\esc-motor-demand
python derive.py          # 13/13 controls, chain, sensitivity -> derive.log + derive.json
python check_report.py    # 29/29 claims reconcile REPORT.md to the instrument
```

**Both exit 0.** Nothing was written outside this directory; no repo was modified; no branch
touched. The board line is *not* written here — a shared 1,515-line board must be merged by the
orchestrator, not by a parallel worker.