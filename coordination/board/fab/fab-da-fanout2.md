# fab-da-fanout2 — the last 15 non-through vias on drone-arm rev_b, by SPAN

**Item:** fab-readiness wave 4 · **Board of record:** `evidence/fab-da-fanout/da_main_rev_b_fanout5.kicad_pcb`
(sha256 `E65F0B2EED47E575AA82397ED662945BE395870C7C6B4E93CA899B9C82A5843A`, 2,260,448 B — checked on the
copy used here, `work/base.kicad_pcb`, same hash).
**Artefact:** `evidence/fab-da-fanout2/da_main_rev_b_fanout7.kicad_pcb`
(sha256 `372C1D525BEBF651F86CB90C007FE8CAF71A41F7E46E28669D7AE956ECFA9077`, 2,262,079 B).
**Tooling:** KiCad 9.0.7 `pcbnew` (Python 3.11.5), `kicad-cli pcb drc`, `kicad-cli pcb export drill`.
**Constraints honoured:** 4-layer, standard plated through vias only, no HDI, no repo write, no commit,
no branch, no spend ($0). Every product is inside this directory; the board was worked on COPIES only.

---

## 0. Answers in one screen

| question | answer |
|---|---|
| Does the 15-group / 18-via count reproduce? | **Yes.** 15 groups, **18 vias**, **11 nets** (the input's 20 groups / 24 vias / 13 nets minus the 5 wave-3 groups), **9 with the via centre inside another net's copper**. Non-through **measured by span**, not drill (§1) |
| What is wrong with the old gate? | On the input board the **span gate reads 18, the diameter-only gate reads 17.** The difference is exactly one hole: the **0.300 mm blind via** at R12. A diameter rule cannot see a blind via of legal diameter, so **17 was never the violation count** (§1) |
| What was EXECUTED here? | **2 of 15 groups — R14 (F16) and R15 (F17).** 3 microvias → 2 through vias; 4 foreign segments replaced by 7 (2 shifted, 1 bent, 1 bumped) and 7 foreign joints dragged; no escape track needed (§3) |
| DRC, board's own rules | **5 → 7**, all seven `via_diameter` (a 0.40 mm pad against the project's 0.60 mm floor). With that one rule at 0.40: **0 → 0** |
| DRC, span-based no-HDI gate | **18 → 15** non-through vias, classified by layer pair |
| unconnected | **0 → 0** (`kicad-cli`, and `pcbnew GetUnconnectedCount`) |
| via census by span | 337 → 336 vias; **non-through 18 → 15**; 0.100 mm drills 17 → 14; 0.200 5 → 7 |
| minimum drill | **0.100 mm → 0.100 mm — unchanged**, 14 microvias remain |
| RF void under the corridor | **1.2959 % → 1.2959 %** (0.5495 of 42.4040 mm²), void_B 0.6013 % → 0.6013 % — bit-identical |
| How close to zero non-through vias? | **Not close: 15 of the input 18 remain.** 7 of 20 groups are now closed (5 in wave 3, 2 here). The other **13 are blocked**, each with a measured reason and a per-group "what would have to give" (§5). The arrest is structural: 8 of the 13 sit inside a 0.40 mm-pitch land pattern whose 0.600 mm gap is 0.050 mm short of the 0.650 mm a legal through via needs (§5) |

**Partial result, stated as partial.** Two groups are finished and DRC-clean. Thirteen are not, and §5
gives, per group, the item that blocks it, the millimetres it is short, and what would have to give.

---

## 1. The gate: classify by SPAN, not by diameter

A via is non-through iff its `(TopLayer, BottomLayer)` pair is not `F.Cu..B.Cu`, **or** its type is not
`THROUGH`. Implemented in `t07_verify.py` (pcbnew), because **KiCad's custom-rule language cannot express a
via's span** — tested, not assumed: a `.kicad_dru` rule with `A.Via_Type == 'Micro'` fired on **0** items,
and `A.Layer != 'F.Cu' && A.Layer != 'B.Cu'` also fired on **0**, while the same file with
`A.Type == 'Via'` raised **199** `drill_out_of_range` violations. So the span gate is a pcbnew check with the rule written
out in `drc/gate_span_<tag>.json`, and the diameter-only gate is reported **beside** it, labelled, never as
the count.

| board | span gate (non-through) | diameter-only gate (`drill < 0.200`) | the difference |
|---|---|---|---|
| input `fanout5` | **18** | **17** | the 0.300 mm blind via at R12 (0.300 drill, In2→B span) |
| artefact `fanout7` | **15** | **14** | same one hole |

Span census, input → artefact:

```
F.Cu..In1.Cu   6 → 5
In1.Cu..In2.Cu 5 → 4
F.Cu..In2.Cu   2 → 2
In2.Cu..B.Cu   3 → 3      <- includes the 0.300 mm BLIND via (R12)
In1.Cu..B.Cu   2 → 1
```

**The blind via is HDI process at any diameter.** It requires sequential lamination — a second drill and
lamination cycle with the inner layers pre-bonded — which is what "no HDI on any board" forbids. Its 0.300 mm
drill passes every diameter rule the project has, which is precisely why a diameter gate reported 17.

---

## 2. The 15 groups, re-enumerated with full geometry

`t02_groups.py` → `work/groups15.json`, `work/groups15.out.txt`. Distances are **from the group centre to the
nearest FOREIGN-net copper EDGE**, per layer, against KiCad's own pad polygons. A 0.40 mm pad / 0.20 mm drill
through via needs **0.325 mm** (0.200 pad radius + 0.125 clearance) on **all four layers** — including the two
the microvia never touched. `pad-clear max`, `pad+via max` and `best legal` are the **largest clearance
achievable anywhere in a 3.4 × 3.4 mm window** at 0.02 mm, counting pads only / pads+vias+holes / everything
(`t09_limits.py`, `work/limits.json`).

| # | w3 | net | vias | span | in-place worst (layer: item @ mm) | blockers (trk/pad/via) | pad-clear max | pad+via max | best legal | status |
|---|---|---|---|---|---|---|---|---|---|---|
| R01 | F01 | `/LSM_INT1` | 1 | In1-In2 | F.Cu: pad FB1.2 `/3V3_ADC` @ **−0.225** | 3/1/0 | +1.962 | +1.008 | +0.315 | infeasible |
| R02 | F02 | `/GNSS_RX` | 1 | In1-In2 | F.Cu: pad C12.2 `/GND` @ +0.143 | 3/1/4 | +1.234 | +0.465 | +0.020 | infeasible |
| R03 | F04 | `/GNSS_RX` | 1 | F-In1 | In2: trk `/RP2354B MCU/USB_DM_MCU` @ +0.099 | 7/2/0 | +1.200 | +0.296 | **−0.017** | infeasible |
| R04 | F05 | `/RF_MISO` | 2 | F-In1, In1-In2 | F.Cu: trk `/RF_nCS` @ +0.275 | 13/2/0 | +1.200 | +0.313 | **−0.045** | infeasible |
| R05 | F06 | `/LSM_INT1` | 2 | F-In1, In1-In2 | B.Cu: trk `/ICM_nCS` @ **−0.089** | 11/2/0 | +1.654 | +0.248 | +0.090 | infeasible |
| R06 | F08 | `/SENS_SCLK` | 1 | In1-B | In1: trk `/LSM_INT2` @ +0.308 | 1/0/4 | +1.662 | +0.600 | **−0.095** | infeasible |
| R07 | F09 | `/RF_GPIO2` | 1 | F-In2 | B.Cu: trk `/SENS_SCLK` @ **−0.086** | 5/2/0 | +1.200 | +0.591 | **−0.165** | infeasible |
| R08 | F10 | `/RF_GPIO0` | 1 | In2-B | In1: trk `/SENS_MOSI` @ **−0.025** | 7/2/0 | +1.061 | +0.591 | +0.021 | infeasible |
| R09 | F11 | `/RF_GPIO0` | 1 | In2-B | F.Cu: trk `/1V1` @ **−0.025** | 10/1/0 | +1.140 | +0.689 | **−0.040** | infeasible |
| R10 | F12 | `/PA_EN` | 1 | F-In2 | B.Cu: trk `/RF_GPIO2` @ **0.000** | 6/0/0 | +1.669 | +0.609 | **−0.163** | infeasible |
| R11 | F13 | `/HGM` | 1 | F-In1 | In2: trk `/RF_MISO` @ +0.250 | 7/2/0 | +1.152 | +0.600 | **−0.055** | infeasible |
| R12 | F14 | `/PA_EN` | 1 | **In2-B (0.300 blind)** | In1: trk `/RP2354B MCU/XIN` @ **−0.075** | 1/1/0 | +1.593 | +0.600 | **−0.144** | infeasible |
| R13 | F15 | `/3V3` | 1 | F-In1 | In2: trk `/LNA_EN` @ **−0.125** | 11/0/4 | +0.819 | +0.491 | +0.030 | infeasible |
| R14 | F16 | `/RP2354B MCU/USB_DP_MCU` | 2 | F-In1, In1-In2 | F.Cu: trk `/3V3` @ +0.275 | 2/1/0 | +1.140 | +0.815 | −0.030 | **EXECUTED** |
| R15 | F17 | `/RF_MOSI` | 1 | In1-B | F.Cu: trk `/915 MHz RF/VDD_CC112` @ **−0.025** | 7/0/0 | +2.060 | +0.846 | +0.073 | **EXECUTED** |

**`best legal < 0` is a hard statement**: in that 3.4 mm window there is **no point at all** where a
0.40/0.20 through via is legal, even with every track ignored — so copper must move, exactly as briefed.
Eight of the thirteen have `best legal < 0`; the other five have a legal point somewhere in the window that
the net cannot reach, or that could not be completed (§5).

**Why 0.40 mm pad / 0.20 mm drill and not 0.60/0.30.** A 0.60 mm pad needs **0.425 mm** of clearance and at
that budget the input board is hopeless — wave 3 measured **188 DRC errors** from the null fan-out at 0.6/0.3
and **0 of 20 groups** feasible. 0.45/0.25 keeps the 0.100 mm ring but needs 0.350, still above the 0.325 the
geometry offers. The smallest pad that keeps the board's **own** `min_via_annular_width 0.10` on a 0.200 mm
mechanical drill is **0.400 mm**; anything smaller drops the ring to 0.075, which no surveyed 1 oz house
publishes. **0.40/0.20 is the floor**, and it is the size wave 3 shipped, so the two waves are comparable.

The full per-group blocker list — every foreign item within the keepout, with its net, kind, uuid and
deficit — is in `work/groups15.json`; the per-layer maps are printed in `work/groups15.out.txt`.

---

## 3. What was EXECUTED (2 groups, real routing edits)

`t03_solve.py` (design + per-edit verification) → `t06_apply.py` (board edits, pours refilled) →
`work/apply_fix4.json`. Record of every planned edit: `work/plan_final.json`.

### R14 — w3 F16, `/RP2354B MCU/USB_DP_MCU`, 2 microvias (F→In1→In2)

The via moves **0.050 mm** in +y and one `/3V3` F.Cu segment is shifted **0.070 mm** in +x;
the two `/3V3` tracks that ended on its joints are dragged with it (0.0379 / 1.6007 mm of slack).

```
del_via  8744cab2… , del_via 74fb7d73…            (the two stacked microvias)
shift    F.Cu /3V3 w0.25  (61.200,44.3628)-(61.200,39.200) -> x = 61.270   lift 0.070, slack +0.038
         retarget 4b30cb5d end (61.2,44.3628) -> (61.27,44.3628)  slack +0.0379
         retarget 8850dbd3 start (61.2,39.2)  -> (61.27,39.2)     slack +1.6007
add_via  0.40/0.20 THROUGH at (60.800, 44.150)   clearance margin after = +0.0062 mm
```

Wave 3 handed F16 over as "one `/3V3` track needs +0.050 away from the via". It is now done — **by moving the
via 0.050 mm and the track 0.070 mm**, i.e. both halves of that move, and DRC agrees.

### R15 — w3 F17, `/RF_MOSI`, 1 microvia (In1→B)

The via stays **exactly at its own XY**; three foreign segments move and five foreign joints are dragged:

```
del_via  5c6a0674…
shift    F.Cu /VDD_CC112 w0.25  x=90.500 (y 57.585..58.297) -> x=90.130  lift 0.370, slack +0.561
         retarget 30b5d2e7 start (90.5,57.5851) -> (90.13,57.5851)  slack +0.0251
         retarget 3c1f93ef start (90.5,57.5851) -> (90.13,57.5851)  slack +0.3038
         retarget 36fab6ea start (90.5,58.2967) -> (90.13,58.2967)  slack +0.0547
jog      In2 /LNA_EN w0.25 (90.6,58.6)-(91.2,58.0)     bump 0.058, slack +0.071
shift    In1 /CC_EXTCLK w0.25 (91.0405,57.9839)-(91.6191,58.5625) -> +0.104/+0.104   lift 0.147, slack +0.158
         retarget d9fc39cb end (91.0405,57.9839) -> (91.14454,57.87986)  slack +0.158
         retarget f89c754a end (91.6191,58.5625) -> (91.72314,58.45846) slack +0.125
add_via  0.40/0.20 THROUGH at (90.600, 58.000)   clearance margin after = +0.0200 mm
```

Wave 3 said F17 needed "seven RF tracks moved ≤0.026 mm" and declined it as "a polyline drag of another
net's route". That is what it was, and it is now done: **3 segments shifted/bent, 5 joints dragged, one via
at its own coordinate, no escape track, +0.020 mm margin.**

### The edit vocabulary that produced them

| op | what it does | why it is safe |
|---|---|---|
| `jog` | bend one foreign segment away from the via; **endpoints fixed** | every joint on that net survives, so no net can be split |
| `shift_seg` | move a whole foreign segment sideways, **both joints dragged** | each attached track is re-pointed and re-verified; used when the violation spans the segment |
| `bend_end` | corner drag: keep the far end, add a corner at the clearance boundary, move the near joint | same, one joint |
| `drag` | move a foreign joint only | **re-verified against the via**, not only against other copper (this was a bug — §7) |
| `move_via` | move a foreign through via, re-pointing the tracks that ended on it | its own connectivity survives |
| `escape` | same-net 0.20 mm track from the old centre to an offset site | only added when the site would otherwise leave the via a dangling stub |

Budget: ≤ 6 jogs, ≤ 2 foreign-via moves, ≤ 3 cascade steps, site search ≤ 1.7 mm. Over budget is reported as
infeasible rather than forced, because a 14-track rip-up of a 0.4 mm-pitch field is not a fan-out edit.

---

## 4. Verification — before and after, one tool, on the artefact itself

`t07_verify.py <board> <tag>`; every number below was re-run on
`da_main_rev_b_fanout7.kicad_pcb`, not only on the working copy.

| # | metric | before (`fanout5`, E65F0B2E…) | after (`fanout7`, 372C1D52…) |
|---|---|---|---|
| 1 | **DRC, own rules** | **5** (all `via_diameter`) | **7** (all `via_diameter`) |
| 1b | DRC, own rules with `min_via_diameter 0.40` | **0** | **0** |
| 2 | **DRC, span-based no-HDI gate** | **18** | **15** |
| 2b | diameter-only gate, for contrast | 17 | 14 |
| 3 | **unconnected** | **0** (kicad-cli) / 0 (pcbnew) | **0** / **0** |
| 4 | **via census** | 337 = 0.100×17, 0.200×5, 0.300×34, 0.350×281; **non-through 18** | 336 = 0.100×14, **0.200×7**, 0.300×34, 0.350×281; **non-through 15** |
| 5 | **minimum drill** | **0.100 mm** | **0.100 mm** (unchanged) |
| 6 | **RF void** under the RF corridor | 0.5495 mm² = **1.2959 %** | 0.5495 mm² = **1.2959 %** (Δ 0.0000) |
| 6b | void_B (incl. via annuli) | 0.2550 mm² = 0.6013 % | 0.2550 mm² = 0.6013 % |
| 7 | tracks | 2,303 | **2,306** (4 segments replaced by 7: 2 shifted, 1 bent, 1 bumped) |

`t10_drill.py` cross-checks in the **Excellon programs a fab would open** (`drill_before/` vs `drill_after/`):

| | before | after |
|---|---|---|
| blind/buried programs | **5** (`front-in1`, `front-in2`, `in1-back`, `in1-in2`, `in2-back`) | **5** |
| 0.100 mm holes in those programs | **17** | **14** |
| 0.300 mm blind holes (`in2-back`) | **1** | **1** |
| **non-through holes total** | **18** | **15** |
| holes below 0.200 mm | 17 of 365 | 14 of 364 |

**The honest reading of rows 1 / 5 / 7-of-drill:** the board is **not** orderable. It carries 14 microvias
and one 0.300 mm blind via; a fab reading those five programs would refuse or mis-build it. What changed is
that 2 more groups are finished, and the remaining 13 are enumerated with numbers instead of adjectives.

---

## 5. The 13 that remain — what blocks each, and what would have to give

Each line is measured: the binding item, its distance from the group centre, and the shortfall against
0.325 mm. "escape" = a same-net track from the old centre to an offset site; "shift/jog" = moving foreign
copper. Failure counts are the actual solver attempts (`work/plan_final.json`, `fails`).

### Class A — a component pad is inside the keepout and the via is inside a pad row (8 groups)

| # | pad at | shortfall | and on the other layers | what would have to give |
|---|---|---|---|---|
| **R01** | `FB1.2` `/3V3_ADC`, centre **inside** the pad (−0.225) | 0.550 | F.Cu `/3V3_ADC` tracks at +0.025/+0.087; B.Cu `/VREG_AVDD` +0.211 | the via must leave FB1.2; the only anchors for In1/In2 are at that XY, and every escape to a legal site crosses `/BARO_SDA` (12 attempts blocked) or lands on `FB1.x` (8). **A 0.55 mm footprint move of FB1** clears it |
| **R02** | `C12.2` `/GND` +0.143 | 0.182 | `/RF_nCS` 350 µm via at 0.299 on **all four** layers (+0.026) | the via is 0.026 mm too close to another net's through via whose hole cannot move (hole-to-hole). **C12 must move ≥0.18 mm** or that via be re-escaped |
| **R03** | `U10.13` `/GNSS_PPS`, `U10.11` `/GNSS_TX` at **0.300 each** | 0.025 each | In2 `/USB_DM_MCU` at +0.099 (+0.226); In1 `/MAIN_LED_A` +0.301 | **the pad gap is 0.600 mm; the via needs 0.650.** No position between the rows clears 0.325 — 7 tracks must move, every shift lands on the next (`pad+via max 0.296`) |
| **R04** | `U10.17` `/RF_MOSI`, `U10.19` `/RF_nCS` at **0.300** | 0.025 each | F.Cu `/RF_nCS` +0.275 (+0.050); In1 `/MAIN_LED_A` +0.301 | same pad pitch; 13 blocker items, all attempts land on `/RF_SCLK` tracks (12) |
| **R05** | `U10.3` `/ICM_INT2`, `U10.5` `/3V3` at **0.300** | 0.025 each | B.Cu `/ICM_nCS` **−0.089** (+0.414); In1 `/SENS_SCLK` +0.290 | pad pitch + 11 blockers; `/SENS_SCLK` shifts hit `U10` pads. The via cannot sit in the row |
| **R07** | `U10.23` `/RF_GPIO3`, `U10.21` `/RF_GPIO0` at **0.300** | 0.025 each | B.Cu `/SENS_SCLK` **−0.086** (+0.411) | pad pitch; 5 track blockers; `/RF_GPIO3` shifts hit a via (18 attempts) |
| **R08** | `U10.24` `/3V3` at **0.000** (centre **on** the pad edge), `U10.25` `/PA_EN` +0.200 | 0.325 / 0.125 | In1 `/SENS_MOSI` **−0.025** (+0.350) | the 0.200 mm gap between adjacent 0.2 mm pads cannot hold a 0.40 mm via at any position. Needs the via out of the row and a 0.35 mm `/SENS_MOSI` push — blocked in 12 attempts |
| **R09** | `C40.2` `/GND` +0.290 | 0.035 | F.Cu `/1V1` **−0.025** (+0.350); In1 `/BARO_DRDY` +0.122 | `/1V1` shift lands on `C41.2` (24 attempts). C40 move is the cheap fix |
| **R11** | `U10.28` `/CAN_SCK`, `U10.26` `/LNA_EN` at **0.300** | 0.025 each | In2 `/RF_MISO` +0.250 (+0.075); B.Cu `/RF_GPIO2` +0.300 | pad pitch; 7 blockers; `/LSM_nCS` shifts hit `/SENS_MOSI` |
| **R12** | `U10.81` `/GND` thermal pad (3.4 × 3.4 mm) at **0.200** | 0.125 | In1 `/XIN` **−0.075** (+0.400); B.Cu `/RF_GPIO2` +0.483 | **this is the 0.300 mm blind via.** In1 copper sits under the thermal pad, so the via must leave the pad edge *and* push `/XIN`; that lands on `/BARO_DRDY` |

**The pad-row arithmetic, which is the whole point of class A:** U10 is a 0.40 mm-pitch land. Where the
microvia sits between two facing pad rows the gap is **0.600 mm**; where it sits between two pads of one row
the gap is **0.200 mm**. A 0.40 mm pad via needs **0.650 mm** edge-to-edge at 0.125 clearance. For the
0.600 mm rows the deficit is **exactly 0.050 mm**, and it is a property of the pitch, not of the routing:
**no position inside the row is legal.** That is why 8 of 13 fail with a pad at 0.300.

### Class B — track-bound: the foreign copper has to move, and the move lands on the next track (5 groups)

| # | binding foreign copper | deficit | attempts that failed, and on what | what would have to give |
|---|---|---|---|---|
| **R06** | In1 `/LSM_INT2` at +0.308 **and** `/RF_GPIO0` 350 µm via at 0.311 on all four layers | 0.017 / 0.014 | 13 × `/SENS_MOSI`, 11 × `/LSM_INT2`, blocked by each other — the two are 0.2 mm apart | `/RF_GPIO0`'s via cannot move (hole-to-hole 0.436 short); the two tracks must move as a pair and there is 0.125 mm of room for 0.014 mm of need — **a bundle push of 2 tracks on In1** |
| **R10** | B.Cu `/RF_GPIO2` at **0.000** (centre inside the track) | 0.325 | 19 × `/BARO_DRDY`, 14 × `/RF_GPIO2`, blocked by `/CAN_*` vias | a **0.325 mm B.Cu bundle push** of `/RF_GPIO2`; the bundle's far side is a via row |
| **R13** | In2 `/LNA_EN` at **−0.125**, F/In1 `/XIN` at 0.302/0.278, B.Cu `/RF_GPIO2` +0.300 | up to 0.450 | `/LNA_EN` shift hits `/RP2354B MCU/XIN` via; `/XIN` shifts hit `/1V1` | **4 layers of bundles**; this is a U10-escape rip-up, not a via move |
| **R14↑** | — | — | **executed** | — |
| **R15↑** | — | — | **executed** | — |

(Class B lists R06, R10, R13 as open; R03/R04/R05/R07/R08/R09/R11/R12 in class A also have track
blockers behind the pad, which is why they are not merely "move the via".)

### The single most useful line in this section

**The blocker is never the drill and never the annular ring.** Every remaining failure is a **clearance
budget of 0.325 mm** against a land pattern built for a 0.275 mm microvia (0.150 pad radius + 0.125). The
0.050 mm by which the U10 rows miss is the same 0.050 mm that separates a 0.30 mm microvia pad from a 0.40 mm
through pad. **No legal through via exists at any of those 8 coordinates**, and that is a geometry fact, not
a routing opinion.

---

## 6. Options that would close the rest, costed

| option | closes | what it costs, and what it breaks |
|---|---|---|
| **0.35 mm pad / 0.20 mm drill** (ring 0.075) | the 0.600 mm rows — exactly, with **0** margin | ring 0.075 is below every published 1 oz minimum (0.10–0.15) and below the board's own 0.10 rule. **Not fabricable** — rejected |
| **clearance 0.125 → 0.100** | same 0.600 mm rows at 0.300 need, **0** margin | a zero-margin design at a fab's absolute floor. Rejected as not robust |
| **move C12 / C40 / FB1** (3 parts) | R01, R02, R09 | 3 footprint moves, no copper; each is 0.03–0.55 mm. Cheapest real fix for those three |
| **re-fan-out U10** (the 0.4 mm-pitch escape field) | R03, R04, R05, R07, R08, R11, R12 | a rip-up of ~40 segments on 4 layers. This is the only fix that closes the pad-row class, and it is a routing job, not a via job |
| **U10 package change** to a ≥0.5 mm pitch part | the pad-row class at the root | part change, layout change, BOM change. The structural fix if the board is revised anyway |

The owner principle says pay now to avoid rework. On that basis the **U10 re-fan-out** is the honest
recommendation: it is bounded work with a known target (0.325 mm of clearance), it costs nothing but routing,
and it closes 7 of the 13 at once. The three part moves are one afternoon and close 3 more. The remaining
R06/R10/R13 are 1–2 bundle pushes each.

---

## 7. Four defects in my own tooling, all found by kicad-cli and not by the model

Recorded because the method matters as much as the result. The first pass "solved" **5 of 15** and the board
then carried **4 clearance errors and 2 shorts**. Each was a model gap, not a DRC quirk:

1. **A drag cleared the joint, not the segment.** `plan_drag` verified only the distance from the joint to
   the via, so a track whose *middle* passed 0.16 mm from the via was marked resolved. Two working tracks were
   relocated on the strength of a 0.0014 mm "fix". Fixed: every dragged segment is now re-checked against the
   via, and a drag that does not move the segment clear is rejected.
2. **The jog's diagonal dips inside the radius.** Two points each exactly R from the via are joined by a
   straight line that passes *closer* than R. The first R15 attempt was 0.298 mm from the via where 0.325 was
   designed. Fixed: the bump height iterates until the whole polyline, not just its corner, clears.
3. **An escape test that only looked at one layer.** `same_net_anchor` searched all four layers, so a site
   touching F.Cu copper suppressed the In2 escape and would have left the via a dangling stub. Two "solutions"
   at 0.9055 mm and 1.5572 mm were exactly this artefact and **were discarded**. Fixed: the anchor is
   per-layer, and a site touching fewer than two span layers is rejected as a stub.
4. **Generated ids collided between the planning clone and the board.** Retargets referenced `ED-0`-style
   names that did not exist at apply time. Fixed: retargets carry the joint's **coordinate**, resolved by
   position at apply time.

The lesson is the same one the programme keeps relearning: **the model is a hypothesis; `kicad-cli` is the
measurement.** Every one of the four was invisible in the model and immediate in DRC.

---

## 8. Files and reproduction

| script | does | output |
|---|---|---|
| `t01_dump.py` | inventory of the copy (schema shared with `fab-da-vias/s01_dump.py`) | `work/inv_base.json` |
| `t02_groups.py` | the 15 groups, per-layer foreign copper, blockers with identity | `work/groups15.json`, `.out.txt` |
| `t03_solve.py` | site search + edit planner (jog / shift_seg / bend_end / drag / move_via / escape) | `work/plan_final.json`, `work/plan7.out.txt` |
| `t04_diag.py` | margin fields per group (what only routing can fix vs what nothing can) | `work/diag.json` |
| `t05_probe.py` | one candidate site, every blocker printed | stdout |
| `t06_apply.py` | applies the plan to a copy, refills pours, saves | `work/fix4.kicad_pcb`, `work/apply_fix4.json` |
| `t07_verify.py` | DRC own / own@0.40 / diameter gate, span gate, census, unconnected, void | `drc/summary_*.json`, `drc/gate_span_*.json` |
| `t08_why.py` | model-vs-DRC reconciliation on one site | stdout |
| `t09_limits.py` | the max achievable clearance fields (§2 columns) | `work/limits.json` |
| `t10_drill.py` | hole census from the Excellon programs | `work/drill_*.json` |
| `t11_table.py` | the §2 table, generated from the JSONs | `work/table15.md` |
| `vgeom.py` | the geometry model, **copied verbatim** from `fab-da-fanout/vgeom.py` | — |

Reproduce: `python t01_dump.py && python t02_groups.py && python t03_solve.py && python t06_apply.py
work/plan_final.json work/base.kicad_pcb work/fix4.kicad_pcb && python t07_verify.py work/fix4.kicad_pcb fix4`.

---

## 9. Artefact and limits

```
evidence/fab-da-fanout2/da_main_rev_b_fanout7.kicad_pcb
  sha256 372C1D525BEBF651F86CB90C007FE8CAF71A41F7E46E28669D7AE956ECFA9077   2,262,079 B
  source E65F0B2EED47E575AA82397ED662945BE395870C7C6B4E93CA899B9C82A5843A   (fanout5, verified on the copy)
  verified ON THE ARTEFACT: own 7 / own@0.40 0 / span gate 15 / unconnected 0 / 336 vias / void 1.2959 %
```

Ships with `da_main_rev_b_fanout7.kicad_pro` (the board's rules as they stand: 7 `via_diameter` violations)
and `da_main_rev_b_fanout7_minvia040.kicad_pro` (`min_via_diameter 0.40`: **0**).

**Limits, stated plainly:**

1. **13 of 15 groups are not closed.** The board is **not orderable**: 15 non-through vias remain, 14 at
   0.100 mm. The 7-of-20 total is 5 from wave 3 + 2 here.
2. **R14's clearance margin after the edit is +0.0062 mm** — legal, but thin. R15's is +0.0200. Both pass
   DRC; neither has design margin to spare.
3. **The 0.10 mm annular ring is a fab question, not an engineering answer.** No quote was obtained. If a
   house refuses 0.10 mm at 1 oz, all 7 executed groups re-open, because 0.6 mm pads do not fit anywhere
   they do.
4. **The impedance/RF consequence of the R15 edit is not assessed.** It moves three `/VDD_CC112` and
   `/CC_EXTCLK` segments by 0.10–0.37 mm and changes no RF_50R geometry (void is bit-identical), but no
   EM solve was re-run on the shifted segments.
5. **The site search is bounded to 1.7 mm** and the edit budget to 6 jogs / 2 foreign via moves. Beyond that
   it is a re-route, and a re-route was out of scope for this item — so "infeasible" here means **infeasible
   within a fan-out edit**, never "impossible on the board".
6. **No status line was written to `AGENT_BOARD.md`** — the brief forbids writing in the repo. The line for
   the orchestrator to place is in the return message.


