# da-connectors — the drone-arm ESC servo connector gap

**Verdict: the gap is not a connector gap.** On the board of record the six servo
connectors the netlist calls for are *entirely absent*, and the six MCU pads that
would feed them have **no legal escape at all** — 0 of 7 candidate pads. The
seventh channel is **not required**: the airframe design of record picks the
**six**-servo configuration. So the item's premise ("7 needed, 6 exist, add the
7th") is wrong twice over, and the real work is a QFN fan-out change, not a part
choice.

All numbers below come from `pcbnew` 9.0.7 or `kicad-cli` 9.0.7 on the files in
`repos/drone-arm/hardware/main/rev_b/` at branch `work/2026-11-11`. Nothing was
written into a repo; the copy lives in `evidence/fab-da-connectors/work/`.

---

## 1. Is the 7th channel required? **No. Six is the design of record.**

The airframe requirement lives in the **drone-mech** repo, and the version
drone-arm pins (`aircraft_system.yaml:14` → drone-mech `5246c906`) already
contains the answer. In `highspeed_edf/design/PHASE15_CONTROL_SURFACES.md`:

- `:35` — `| **Effector/servo total** | 2 elevons + 3–4 vanes + 1 rudder = **6–7 servos** |`
- `:432` — **"Pick B."** … the cheapest set with full yaw authority at *all* speeds
- `:435` — **"That is **6 servos instead of 7**"**
- `:446` — "**If the two ducts must stay separate** (no common exit), Option A (4 vanes + rudder, 7 servos) is the fallback"

Option A (7) and Option B (6) differ by exactly one part: **the 4th vector vane**.
B keeps 3 tangential single-axis vanes in a merged exit (rank-3 control by the
determinant 2.598 argument at §9c) plus the fin rudder; A keeps 4 vanes (2 per
duct) plus the rudder. So the 7th actuator *is* a 4th vane, and it exists only in
the rejected-by-default configuration. The one thing that can force it is a
mechanical decision the airframe has not made: whether the two duct exits merge.

The electrical design of record agrees, independently:
`reports/main_net.xml` contains **exactly six** servo connectors `J60–J65`
(`PinHeader_1x03_P2.54mm_Vertical`, values `ESC_PWM_1..6`) with
pin1=`/CAN_GND`, pin2=`/CAN_5V`, pin3=`/RP2354B MCU/PWM_ESCn` →
`U10` pads **43–48**. **There is no J66 anywhere in the netlist or the schematic.**

So `aircraft_interfaces/system_interface.json` (`"modeled_effector_count": 7`,
`"available_pwm_output_count": 6`) and
`engineering_acceptance/catalog/mandatory_checks.yaml:18`
(`expected: {current_effectors: 7, declared_pwm_outputs: 6}`) are **stale**: they
record the pre-§9c effector count. They should read **6 / 6** and cite §9c. That
is a contract correction, not a board change. The previous attempt's "J60–J66"
(seven connectors) invented a part the design does not have.

---

## 2. The measured physical constraint at U10 pads 43–49

Board of record = `main_rev_b.kicad_pcb` (140 × 100 mm, 165 footprints,
2,620 tracks, 341 vias, 33 below 0.2 mm — matches the wave's measured state).

U10 is a `QFN-80-1px_10x10mm_P0.4mm` at (59.000, 50.000). Pads 43–49 sit on the
**east** column, x = 63.950, pad 0.80 × 0.20 mm, pitch **0.400 mm**, tip at
x = **64.350**, y = 53.000 down to 50.600.

Rules applied (`main_rev_b.kicad_pro` → `board.design_settings.rules` and the
`Default` netclass): `min_track_width` **0.200 mm**, `min_clearance` **0.125 mm**.
A 0.2 mm track therefore needs a **0.450 mm** corridor.

**Result: 0 of 7 pads has a legal escape.**

| measurement | value | evidence |
|---|---|---|
| nearest foreign copper east of the pad tips | `/GNSS_PWR_EN` trace, 0.25 mm wide, on **x = 64.819**, y 50.944–53.019 | `07_blockers.log` |
| its copper edge | x = 64.694 | same |
| clear gap from pad tip 64.350 | **0.344 mm** | same |
| needed for 0.2 mm / 0.125 mm | **0.450 mm** | rules |
| **shortfall** | **0.106 mm** | derived |
| barrier vertical extent | y 50.46 (0.70 mm via at 64.951, 50.812) → y 53.42 | `07_blockers.log` |
| pad row it seals | pads 43–49 = y 50.6–53.0 — the **entire** row | derived |
| escape-fan test, ±75° at 5°, out to 1.0 mm | pads **44, 45, 46, 47 → no free cell at any angle**; 43/48/49 → pockets of 0.18–0.42 mm², reach 0.6–0.8 mm | `09b_escape_fan.log` |
| free area in the row's corridor (x 64.35–70, y 50–54) | **42.0 % = 10.24 mm² free — but 0 of 7 pads can reach any of it** | `13b_corridor_area.log` |
| free area within the first 1.15 mm of the pad tips | **4.8 % = 0.24 mm²** (the 0.344 mm sliver, and nothing else) | same |
| free area beyond the fence (x 66–70) | **55.1 % = 9.72 mm²** — real open space, walled off from the pads | same |

The 0.32–0.42 mm² "pockets" are just the 0.344 mm sliver between pad tip and
barrier — 0.344 × 1.2 mm = 0.41 mm². They are not lanes.

**Sensitivity, so the cost of opening a lane is not a guess** (`12_sensitivity.json`):

| scenario | best pocket any pad reaches |
|---|---|
| as built | 0.42 mm² / 1.22 mm reach |
| delete **C36** only | 0.42 mm² (unchanged) |
| delete the whole `/GNSS_PWR_EN` net escape (7 objects) | 1.69 mm² / 2.7 mm |
| delete C36 **and** the escape (8 objects) | **2.20 mm² / 2.7 mm — still a pocket** |

The fence is not one trace. It is **C35 / C36 / C37 (three 0402 decoupling caps
at x = 65.50), Y1 (crystal at x = 70.00), the `/GNSS_PWR_EN` fan-out, and the
3V3/GND escapes feeding those caps** — a 2.7 mm-deep ring. Opening a lane means
moving placed decoupling capacitors and a crystal and re-routing the signals they
serve. That is a **fan-out re-layout**, i.e. a re-spin, not a connector change.

**This confirms the earlier "0 free lanes at pads 43–49" finding and, for the
first time, explains it with numbers.**

---

## 3. The board of record does not have *six* channels — it has none

Contrary to the item brief, "6 channels exist" is **not** true of
`main_rev_b.kicad_pcb`. Measured (`14_netlist_vs_board.json`):

```
netlist comps: 167   board footprints: 165
MISSING from board (6): ['J60','J61','J62','J63','J64','J65']
EXTRA on board (4):     ['H1','H2','H3','H4']      (mounting holes — normal)
nets in netlist but not on the board:
  /RP2354B MCU/PWM_ESC1 … PWM_ESC6
```

U10 pads 43–48 carry `unconnected-(U10-GPIO34-Pad43)` … `unconnected-(U10-GPIO39-Pad48)`
on the PCB, i.e. **single-pad nets**. The six headers exist only in the older
130 × 74.52 mm variant `main_rev_b_final.kicad_pcb` (J60–J65 at y = 72.5), which
measures **7 violations / 55 unconnected** and is not a fabrication candidate.

**And the current board passes DRC 0/0** (`drc_before_main_rev_b.json`).
KiCad DRC cannot see a netlist component that was never placed. So the fab
checklist's "DRC clean, 0 unconnected" is a clean measurement of the wrong
population — the exact defect class this programme has already been bitten by
three times. On the board of record the defect is **six missing connectors, not
one**.

---

## 4. Options (a), (b), (c): each tested, none delivers

**(a) repurpose a spare pad already broken out on an existing connector (zero new copper).**
Enumerated every connector pad on the board (`03_connectors.txt`):

| connector | pads | free pads |
|---|---|---|
| J1 USB-C | A1…B12, S1×4 | **A8 (SBU1), B8 (SBU2)** — the only unallocated pads on the whole board |
| J2 ESC_CAN_POWER (JST GH 1x04) | 1–4 | none (CANH, CANL, CAN_5V, CAN_GND) |
| J10 SWD (JST SH 1x03) | 1–3 | none (SWCLK, SWDIO, GND) |
| J30 / J40 U.FL | 1,2 | none (RF + GND) |

J1's SBU pads are electrically usable but they are **USB-C auxiliary pins inside
the USB receptacle**: a servo lead would have to be plugged into the USB-C port,
2 pins only, and it would make the USB port unusable. **Rejected** — not a
"zero-effort win", a field failure waiting to happen.

**(b) test point / castellated edge finger (minimal copper).** This only works if
some PWM-capable MCU pad has a lane. Escape-fan over every unconnected U10 pad
(`09b_escape_fan.log`) shows the only unconnected pads with real open space are
**QSPI 71/72/73** (5.18 mm², 5.5–5.9 mm reach) — and on RP2354B the QSPI pins are
dedicated flash pins, not PWM-capable GPIO. The six PWM-capable pads are exactly
the blocked ones. **Not possible.**

**(c) fine-pitch connector (0.5 mm FFC).** The blocker is **2.1 mm from the QFN
pad tip**, not at the board edge — the board edge has 52.6 × 4.5 mm of clear
space (`13_strip.json`). A smaller connector cannot manufacture a lane that the
MCU fan-out does not have. **Does not apply.** (No part number is proposed,
because no such part would help.)

---

## 5. The edit, on a copy, DRC-verified

Since no option can route the six signals, the edit isolates the part that *can*
be built for free, so the remaining work is unambiguous:

- **6 × `Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical`**, refs
  J60–J65, value `ESC_PWM_n`, at (6.50 / 15.50 / 24.50 / 33.50 / 42.50 / 51.50,
  **y = 10.30**), 9.00 mm pitch, rotated 90°.
  Nets exactly as the netlist of record: pin1 `/CAN_GND`, pin2 `/CAN_5V`,
  pin3 `/RP2354B MCU/PWM_ESCn`; U10 pads 43–48 re-assigned to the six PWM nets.
- **Rails**: `/CAN_5V` bus on F.Cu at y = 8.90 (x 7.8 → 54.04) with a stub to
  every pin 2; `/CAN_GND` bus on F.Cu at y = 12.80 (x 3.0 → 51.5) with a stub to
  every pin 1; each bus dropped on **B.Cu** through 0.70 mm / 0.35 mm through
  vias to the existing `/CAN_GND` and `/CAN_5V` copper at J2 (pads 2 and 1).
- Placement pre-flighted against the measured clearance field
  (`24c_build_v4.py`, "pad pre-flight: OK"), zones re-filled, then DRC.

| | before (`main_rev_b`) | after (`work/main_rev_b_servo6.kicad_pcb`) |
|---|---|---|
| DRC violations (severity-all) | **0** | **0** |
| unconnected items | **0** | **6** |
| footprints | 165 | 171 |
| tracks / vias | 2,279 seg + 341 via | 2,297 seg + 345 via |
| via drills present | 0.100 / 0.300 / 0.350 | 0.100 / 0.300 / 0.350 (unchanged) |
| vias below 0.2 mm | 33 | 33 (**none added**) |
| nets | 175 | 175 |
| netlist components present | 165 of 167 | **171 of 171** |

The 6 remaining unconnected are exactly the six PWM connections, named by DRC:

```
PTH pad 3 [/RP2354B MCU/PWM_ESC1] of J60 … Pad 43 of U10   (×6, ESC1…ESC6)
```

That is the honest state of the design of record, and it is an **improvement in
truth**: the previous 0/0 hid six absent parts; this artefact names them.

Why they are not routed: §2. There is no legal 0.2 mm path from pads 43–48, with
a 0.106 mm shortfall at the very first millimetre.

---

## 6. Second defect found — the servo rail cannot feed six servos

Not in the brief, but it invalidates the connector fix on its own:

- The netlist puts **pin 2 of every servo connector on `/CAN_5V`**.
  `/CAN_5V` on this board is fed through **F1**, and F1 is
  **`1206L075/24WR`, a 0.75 A PTC** — `docs/hardware/REV_B_BOM.csv:140`
  (`Flight Control Rev-B, Littelfuse, 1206L075/24WR, PTC 0.75A, Fuse:Fuse_1206_3216Metric, 1, F1`).
- The airframe requires an **actuator rail of 6.0 – 7.4 – 8.4 V, 3 – 9 – 15 A**
  (`PHASE15_CONTROL_SURFACES.md:344`).

So the rail of record is **5.0 V (below the 6.0 V minimum)** and fused at
**0.75 A (a quarter of the 3 A minimum, a twentieth of the 9 A nominal)**. Six
digital metal-gear servos will trip a 0.75 A PTC on the first simultaneous
deflection.

`BOARD CORRECTION:` the board's decision #3 states the 0.75 A PTC "is F701 on the
ESC rev_b board … not the flight-control board". That is true of F701, but there
is a **second** `1206L075/24WR` at **F1 on the flight-control board**
(`REV_B_BOM.csv:140`), and it is the one in series with the servo rail this item
is about. The connector gap and the rail rating are the same defect viewed twice.

Consequence for the recommendation: adding six connectors to a 0.75 A / 5 V rail
would not make the aircraft fly. The servo interface needs a **dedicated BEC
(6–8.4 V, ≥3 A) and a proper rail**, which is a schematic change, i.e. part of
the same revision.

---

## 7. What needs a human

1. **The ducts.** Does the airframe merge the two duct exits? Yes → 6 servos
   (design of record). No → 7, and the 7th is a 4th vector vane
   (`PHASE15_CONTROL_SURFACES.md:446`). This is a mechanical decision; it is the
   only thing that makes the count 7.
2. **Accept that this is a re-spin, and merge it with the via conversion.** Rev-B
   already must be re-spun to convert the 33 sub-0.2 mm vias (a separate wave
   item). The servo fan-out belongs in *that* pass: move C35/C36/C37 and the
   `/GNSS_PWR_EN` escape, then fan out pads 43–48 to J60–J65. Doing it once is
   the cheap path; a connector hack now costs a second spin later.
3. **The servo rail.** Approve a real BEC (6.0–8.4 V, ≥3 A) with its own
   connector pin, replacing `pin2 = /CAN_5V` behind a 0.75 A PTC. Without this,
   the six connectors are decoration.
4. **The stale contract.** Change `system_interface.json`
   (`modeled_effector_count` 7 → 6) and `mandatory_checks.yaml:18`
   (`current_effectors: 7` → 6, cite §9c Pick B), or the acceptance framework
   will keep demanding a part the airframe rejected.

## 8. What is UNVERIFIED

- Whether the two duct exits merge is an airframe/CAD decision not recorded in
  either repo at the pinned revisions — I did not measure it.
- The *mechanical* fit of a 130 × 74.5 mm vs 140 × 100 mm outline to the airframe
  is not established; I make no claim about which outline ships.
- Servo current draw per channel is not measured anywhere; "3–9–15 A" is the
  airframe's own requirement band, not a measurement.
- My clearance field ignores zone fill (deliberate: zones re-pour around new
  copper) and models roundrect pads as rectangles. The final authority used here
  is `kicad-cli pcb drc` 9.0.7, which returned 0 violations.

---

## 9. Artefacts and reproduction

| file | what |
|---|---|
| `REPORT.md` | this report |
| `work/main_rev_b_servo6.kicad_pcb` | the edited **copy** (repo untouched), sha256 `77C247979468C993D373F0D31E8EFDB4098A14744E6E9D0B56276A3E6A9F2640`, 2,338,974 B — rebuild is byte-stable |
| `work/main_rev_b_servo6.kicad_pro` | project rules copied alongside (0.125 mm clearance) |
| `patch/add_J60_J65_and_rails.py` | **replayable** edit — the "patch"; rebuilds the copy from the repo board |
| `drc_before_main_rev_b.json` | DRC of the board of record: 0 violations / 0 unconnected |
| `drc_before_main_rev_b_final.json` | DRC of the 130 mm variant: 7 / 55 |
| `drc_after_routed.json` | DRC of the copy: 0 violations / 6 unconnected |
| `14_netlist_vs_board.json` | proves J60–J65 + the 6 PWM nets are absent |
| `07_blockers.log` | the 0.344 mm barrier, named objects |
| `09b_escape_fan.log` | escape-fan result, all unconnected U10 pads |
| `12_sensitivity.json`, `12b_sens.py` | cost of opening a lane |
| `21_rail_clearance.json`, `22b_probe.py` | rail route pre-checks |
| `05…13_*.py/.log`, `25_copy_verify.json` | every measurement, re-runnable |

```bat
rem before
"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe" pcb drc --format json --severity-all ^
  --output drc_before_main_rev_b.json ^
  repos\drone-arm\hardware\main\rev_b\main_rev_b.kicad_pcb

rem rebuild the copy, then DRC it
"C:\Program Files\KiCad\9.0\bin\python.exe" patch\add_J60_J65_and_rails.py
"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe" pcb drc --format json --severity-all ^
  --output drc_after_routed.json evidence\fab-da-connectors\work\main_rev_b_servo6.kicad_pcb
```

Note: `kicad-cli pcb drc` on a board **without** its `.kicad_pro` next to it falls
back to built-in defaults (0.2 mm clearance) and reported **652** violations on
this board before the project file was copied in. The project file must sit beside
the copy — that is why `work/main_rev_b_servo6.kicad_pro` is an artefact.

## 10. One-line answer per checklist question

| question | answer |
|---|---|
| is a 7th channel required? | **NO** — §9c picks 6; the 7th is the 4th vector vane of the rejected Option A |
| is there a lane at pads 43–49? | **NO** — 0 of 7; 0.344 mm available, 0.450 mm required, 0.106 mm short |
| do 6 channels exist on the fab board? | **NO** — 0 of 6; netlist has J60–J65, board has none, DRC shows 0/0 anyway |
| least-effort path that gives the required channels? | **none by connector choice** — move C35/C36/C37 + the GNSS_PWR_EN escape and re-fan-out pads 43–48 in the same re-spin that converts the 33 sub-0.2 mm vias |
| does the copy pass DRC? | **YES** — 0 violations, 6 unconnected, exactly the six PWM nets, no new sub-0.2 mm drill |
| can a fab house build this board today? | **NO** — it has no servo interface, and the rail behind it is 0.75 A at 5.0 V |