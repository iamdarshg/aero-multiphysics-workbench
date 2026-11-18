# w2-da-connectors — missing ESC PWM connectors on drone-arm rev_b

**Unit:** wave 2, drone-arm connectors (re-dispatch after a lost report).
**Board under audit:** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb` (the
schematic-parity source; `evidence/drone-arm-final/parity-verify.json` → `"source"`).
**Method tiers used:** Tier C (closed-form/geometry raster from real KiCad geometry) and
Tier A-none (no field solve, none needed). Every number below comes from a script in this
folder or from a cited `file:line`.

---

## 0. Answer

| item | answer |
|---|---|
| channel count | **7**, of which the board implements **6** — one short, not six |
| 7th actuator | the **fin rudder servo** (2 elevons + 4 vanes + 1 rudder) |
| is "7" stale? | **no** — it is a costed decision (D3/B); the *board* froze the pre-D3 number |
| connector | 7 × 1x03 2.54 mm vertical THT header (`Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical`) |
| placement | row at y = 79.50 mm, x = 80.00 … 95.24 mm @2.54 pitch (J60…J66) |
| free area | **6103 mm² / 43.4 %** free; largest free rect **53.25 × 21.25 mm** at x[77.67–130.93] y[74.67–95.92] |
| fix type | **RIP-UP** inside rev_b (new copper); rev_b is un-fabbed, so no second spin |

---

## 1. Channel count: 7 is real, and it is the *rudder*

### 1.1 What the airframe asks for

| claim | source |
|---|---|
| "2 elevons + 3–4 vanes + 1 rudder = **6–7 servos**" | `drone-mech/highspeed_edf/design/PHASE15_CONTROL_SURFACES.md:35` |
| option B (3 vanes + merged exit + rudder) = 6; **option A (4 vanes + rudder) = 7** | same file `:426-429` |
| "If the two ducts must stay separate … **Option A (4 vanes + rudder, 7 servos) is the fallback — accept the extra servo**" | `:446-447` |
| **D3 decided: "B — 4 vanes (2/duct) + rudder (7 servos) — YES"**, because the 3-vane option needs a merged nozzle costing ₹5–15 k vs ₹0.6–0.9 k for one servo | `DESIGN_DECISIONS_FOR_VERDICT.md:49-53`, final picks `:122` |
| ducts stay **separate**: "Duct count 2 … **side-by-side**, NOT coaxial" | `PHASE15_DESIGN_SPEC.md:170,174` |
| "**F-05 — the 7th servo has no PWM channel.** D3 chose 4 vanes + 1 rudder = 7 servos, but the frozen drone-arm contract provides 6 PWM channels" | `DESIGN_DECISIONS_FOR_VERDICT.md:158-160` |
| machine-readable: `modeled_effector_count: 7`, `pwm_capacity.capacity: 6`, `actuators.mapping` BLOCKED "seven modeled effectors exceed six PWM outputs" | `drone-arm/aircraft_interfaces/system_interface.json:55,104-117,119-133` |

So the **7th actuator is the fin rudder**, and it is not decorative: at 720 km/h the vanes
fail yaw by 2.9× (`PHASE15_CONTROL_SURFACES.md:165`), and the rudder is the only yaw
authority above ~400 km/h (`DESIGN_DECISIONS_FOR_VERDICT.md:168-170`). Six channels is
**option C** — "4 vanes, no rudder … yaw above 400: **no** (authority hole)"
(`PHASE15_CONTROL_SURFACES.md:428`). The board as built is exactly that hole.

### 1.2 Why "6" got frozen — the stale number is on the board side

`PHASE15_CONTROL_SURFACES.md:280` still says **"Actuator count | 6 | hold | 2 + 4"** —
2 elevons + 4 vanes, no rudder. That line predates §9c and predates D3. The rev_b
schematic implements it literally: six `Conn_01x03` symbols, `PWM_ESC1..6`, nothing else
(`mcu.kicad_sch:4607-4688` and siblings).

**Therefore:** the airframe needs 7; the board is **one** channel short (not six), and the
missing channel is the rudder. Adding a 7th costs one header + one GPIO, not a redesign.

### 1.3 What is *not* claimed

`PHASE15_CONTROL_SURFACES.md:444` still keeps the escape clause "only move to 7 servos if
the common-exit merge costs more drag/loss than the servo saves". If the airframe later
merges the two ducts (D2/B, priced at +₹20–50 k, `DESIGN_DECISIONS_FOR_VERDICT.md:36`),
J66 becomes DNP and this board is correct as built. Until that decision flips, 7 stands.

---

## 2. Connector: part, pitch, orientation, placement

### 2.1 Part

| property | value | why |
|---|---|---|
| footprint | `Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical` | this is **already** the footprint J60's symbol declares (`mcu.kicad_sch:4635`); instantiating it closes the 6 `missing_footprint` items with **zero** schematic rework |
| pin count | 3 (pin1 CAN_GND, pin2 CAN_5V, pin3 PWM_ESCn) | netlist `PWM_ESC1` code 95 = {J60.3, U10.43}; `CAN_5V` code 49 = {F1.1, J2.1, J60…J65.2}; `CAN_GND` code 50 = {J2.2, J60…J65.1, R3.1} |
| pitch | 2.54 mm | as declared |
| orientation | vertical THT, pin column along +y | cables leave upward into the bay; THT means the 4 layers refill around the barrel automatically |
| MPN | `Commodity / unspecified` (KiCad standard footprint, no new library part; `revb.pretty` holds only customs) | matches the repo's own BOM convention for generic headers (`REV_B_BOM.csv:46`, the 1x03/1x05 pin headers) |

### 2.2 Free area — measured, not assumed

Script `freearea2.py`, 0.25 mm raster over the real board:
occupancy = footprint courtyards (F.CrtYd) + pad copper + tracks + vias + 0.25 mm
clearance + 1.0 mm board-edge inset.

```
EDGE_BBOX -0.075..140.075 x -0.075..100.075  => 140.150 x 100.150 mm, area 14036 mm2
thickness 1.6 mm, 4 copper layers, 165 footprints, 2620 track/via items
blocked 56.6 % | FREE 43.4 % = 6103 mm2
LARGEST free rect: 53.25 x 21.25 mm = 1145 mm2 at x[77.67..130.93] y[74.67..95.92]
```

Free fraction of the bands that matter:

| band | free |
|---|---|
| SE field x100–135 y70–95 | **89.7 %** (785/875 mm²) |
| SE quadrant x64–140 y54–100 | 60.6 % (2117/3496 mm²) |
| east of U10 x64–100 y40–54 | 38.2 % (193/504 mm²) |
| NE field x100–138 y20–55 | 67.1 % (893/1330 mm²) |
| SW field x20–80 y60–96 | 34.4 % (742/2160 mm²) |

A 7-up row of these headers needs 17.78 × 7.62 mm. The **nearest feasible** window on the
whole board is inside the largest free rect (37.0 mm from U10 pad 47), so the connectors go
there — not because it is the shortest path, but because it is the only measured place
where seven of them fit at once.

### 2.3 Placement (exact)

Row: `y = 79.50`, first centre `x = 80.00`, pitch 2.54 mm. Footprint rotation 0°.
Union = x[78.73–96.51] × y[75.69–83.31] = 17.78 × 7.62 mm, fully inside the measured free
rectangle, with >1.0 mm clear all round (`pick_place.py`: 1.0 mm halo 100 % free).

| ref | centre (mm) | pin 1 CAN_GND | pin 2 CAN_5V | pin 3 PWM | channel |
|---|---|---|---|---|---|
| J60 | 80.00, 79.50 | 80.00, 76.96 | 80.00, 79.50 | 80.00, 82.04 | PWM_ESC1 |
| J61 | 82.54, 79.50 | 82.54, 76.96 | 82.54, 79.50 | 82.54, 82.04 | PWM_ESC2 |
| J62 | 85.08, 79.50 | 85.08, 76.96 | 85.08, 79.50 | 85.08, 82.04 | PWM_ESC3 |
| J63 | 87.62, 79.50 | 87.62, 76.96 | 87.62, 79.50 | 87.62, 82.04 | PWM_ESC4 |
| J64 | 90.16, 79.50 | 90.16, 76.96 | 90.16, 79.50 | 90.16, 82.04 | PWM_ESC5 |
| J65 | 92.70, 79.50 | 92.70, 76.96 | 92.70, 79.50 | 92.70, 82.04 | PWM_ESC6 |
| **J66** | **95.24, 79.50** | 95.24, 76.96 | 95.24, 79.50 | 95.24, 82.04 | **PWM_ESC7 (rudder)** |

Robustness: the same row hit-tests clear (0 blocked cells per header) on all six 140×100
rev_b artefacts — `main_rev_b`, `_completed`, `_routed`, `_routed_clean`,
`_routed_iter2_filled`, `_shortfix` (`verify_row_all.py`).

**Naming trap worth recording:** `main_rev_b_final.kicad_pcb` and
`main_rev_b_final.before_diff_pair_ripup.kicad_pcb` are **not** this board — they are a
**130.05 × 74.57 mm** variant with U10 at (56.08, 38.50). Only the six files above are
140 × 100. Any future unit that reaches for "final" gets a different PCB.

---

## 3. Net map — and what the 20 "mismatches" actually are

### 3.1 Path (schematic == board, once the footprints exist)

| U10 pad | pin function | net | J pin | ESC channel | effector (proposed allocation) |
|---|---|---|---|---|---|
| 43 | GPIO34 | PWM_ESC1 | J60.3 | 1 | elevon L |
| 44 | GPIO35 | PWM_ESC2 | J61.3 | 2 | elevon R |
| 45 | GPIO36 | PWM_ESC3 | J62.3 | 3 | vane UL |
| 46 | GPIO37 | PWM_ESC4 | J63.3 | 4 | vane UR |
| 47 | GPIO38 | PWM_ESC5 | J64.3 | 5 | vane LL |
| 48 | GPIO39 | PWM_ESC6 | J65.3 | 6 | vane LR |
| **49** | **GPIO40/ADC0** | **PWM_ESC7** | **J66.3** | **7** | **rudder** |
| — | — | CAN_GND | J6x.1 | — | — |
| — | — | CAN_5V | J6x.2 | — | — (see RISK) |

Reference data: `mcu_pinmap.json:177-206` maps GPIO34–39 to pads 43–48 and nothing else;
the board stores no net named `*PWM_ESC*` at all (0 of 176 nets) and pads 43–49 all read
`unconnected-(U10-GPIOxx-PadNN)` (`verify_parity.py`).

The 7th pin is real and free: pads 43–49 are contiguous on the east face at 0.4 mm pitch
(x = 63.95, y = 53.0 → 50.6), and pad 49 sits between pad 48 (PWM_ESC6) and pad 50 (3V3),
so it is isolated but adjacent — one continuous 2.4 mm pin run for all seven channels.

**UNVERIFIED:** that GPIO40 muxes to a usable PWM slice is a firmware claim, not a layout
claim. It is not a hardware blocker (the family allows a GPIO-to-slice mux), but no
firmware artefact in either repo assigns it, so it is stated as a firmware gate, not a fact.

### 3.2 Parity arithmetic, corrected

`parity-verify.json` → `schematic_parity` = 191 items: 161 `footprint_symbol_mismatch`,
6 `missing_footprint`, 20 `net_conflict`, 4 `extra_footprint`.

Of the **20 net_conflicts**:

| class | count | real? |
|---|---|---|
| PWM_ESC1–6 on pads 43–48 | **6** | **yes** — this unit's defect |
| `/CANH` vs `/CANL` swap | 3 | yes — the known swap (`AGENT_BOARD.md:93`) |
| net-name escaping artefacts (`unconnected-(U10-GPIO40/ADC0-Pad49)` vs `…{slash}…`) | 11 | **no** — reporter artefact on nets the schematic itself leaves open |

So "0 match / 20 mismatch" should read **9 real / 11 escaping artefacts**. The 161
footprint_name mismatches are all library-prefix noise (`revb:X` vs `X`,
`Connector_JST:…` vs `…`) — none is a placing defect.

Existing `unconnected-(U10-GPIO40-Pad49)` on the board vs `PWM_ESC7` in the schematic is
exactly the parity item that the J66 addition resolves.

---

## 4. RIP-UP, not a bodge

**RIP-UP — new copper inside rev_b.** Reasons, in order:

1. **A bodge cannot create pads.** Seven THT headers with 21 pads do not exist on the
   board; wire-bodge only bypasses copper that is already there.
2. **rev_b has never been fabricated.** `AGENT_BOARD.md:91` — "drone-arm ships only
   **rev_a** gerbers … RE-SPIN". So editing rev_b *is* the no-second-spin path; the spin
   already on the board's critical path is for the gerber/sheet-frame defect, not for this.
3. **The escape is genuinely blocked, and that is what makes it a rip-up.** Measured
   (`escape_layer2.py`, per-layer, U10's own courtyard excluded so the fan-out area counts):

   ```
   free lanes >=0.30 mm across a vertical cut, y=44..60
    cut x   F.Cu  B.Cu   F.Cu lanes
    64.60     1     0    y58.67-59.42
    65.00     1     1    y57.67-59.92
    66.50     3     2    y44.42-44.92, y54.92-55.42, y56.42-59.92
    68.00     3     2    y44.42-47.42, y52.17-55.42, y56.42-59.92

   free lanes on F.Cu in the pads' own band (y 50.4..53.2):
    x=64.60: 0   x=65.00: 0   x=65.50: 0   x=66.50: 0
   ```

   Every one of pads 43–49 has **zero** free lane eastward at its own y on either outer
   layer. The seven traces cannot be added; the existing escape fan (and the 0402
   decoupling column at x = 65.5) must be opened up first.

### 4.1 Scope of the rip-up

| step | work |
|---|---|
| 1 | open a 7-trace channel through x 64.4–66.5, y 50.2–53.0 by rerouting the F.Cu traces currently crossing there (2.8 mm of band vs 7 × 0.30 mm = 2.1 mm needed) |
| 2 | route 7 × `PWM_ESC1..7` ≈37 mm into the free field to J60.3…J66.3 (width 0.15 mm is ample for ≤800 Hz PWM) |
| 3 | place J60–J66 at the coordinates in §2.3 |
| 4 | tie 7 × J6x.1 to CAN_GND (R3 0 Ω star already ties CAN_GND↔GND) |
| 5 | tie 7 × J6x.2 to CAN_5V — **only if** the RISK below is accepted |
| 6 | refill F.Cu / In1 / In2 / B.Cu; THT barrels clear automatically in the pour |
| 7 | re-run parity → expect 6 `missing_footprint` → 0, and 6 of the 20 net_conflicts gone |

---

## 5. BOM add

Exporter groups by `(Manufacturer, MPN, Value, Footprint)`
(`tools/hardware/export_rev_b_bom.py`), so the seven must share one `Value` to come out as
a single row. Recommended `Value` = `ESC_PWM` for all seven (the channel is already in the
net name); the existing `ESC_PWM_1..6` strings would otherwise emit seven qty-1 rows.

```
Flight Control Rev-B,Commodity / unspecified,ESC_PWM,ESC_PWM,Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical,7,"J60, J61, J62, J63, J64, J65, J66"
```

(column order = `REV_B_BOM.csv`: Board, Manufacturer, MPN, Value, Footprint, Quantity, References)

---

## 6. RISK

**As drawn, pin 2 is not an actuator rail.** All six connectors hang on `CAN_5V`, which is
behind **F1 = "PTC 0.75A"** (`power_usb.kicad_sch:3028`; net 49 `CAN_5V` = {F1.1, J2.1,
J60–J65.2}; F1.2 = `CAN_5V_FUSED`), and the ESC's exported rail behind it is a
**1 A LM5164** buck ("one fused 5 V rail exported to the flight-control board",
`REV_B_ARCHITECTURE.md:127-133`). The actuator requirement is **6.0–7.4–8.4 V, 3–9–15 A
peak** (`PHASE15_CONTROL_SURFACES.md:283,344`) — a 0.75 A PTC at 5.0 V misses it by >10×,
and 5.0 V is below the 6.0 V floor regardless of current.

Concrete fix inside this same rip-up, no extra spin: **leave pin 2 unconnected** on all
seven headers and let the harness carry 7.4 V from a dedicated BEC to the servos (signal +
signal-ground from the board, power from the BEC, grounds commoned at the servo). That
meets the rail requirement without adding a 15 A distribution layer to a 4-layer FC.

---

## 7. Corrections to the brief / board

- **Brief correction (not a board defect):** "0 match / 20 mismatch" is 9 real + 11 KiCad
  net-name escaping artefacts (§3.2). The 20 includes the CAN H/L swap, which is not a
  connector defect.
- **Brief premise checked:** "the ESC board … for the FL201 reference". FL201 is **not a
  connector** — it is a TDK `ACT45B-110-2P-TL003` common-mode choke on footprint
  `L_CommonModeChoke_Coilank_ACM4532` at (163.73, 23.88) on `esc_rev_b.kicad_pcb`
  (`esc_rev_b.kicad_pcb`, FL201 footprint block; BOM row `REV_B_BOM.csv:67`). No connector
  MPN can be derived from it. What it does supply is the repo's reconciliation template —
  symbol, board footprint and BOM row with a real MPN all agreeing — which is exactly what
  J60–J65 lack. The connector choice therefore comes from the schematic's own declared
  footprint (§2.1), not from FL201.
- **`AGENT_BOARD.md:93` stands** ("J60–J65 + six PWM nets unconnected; 7 actuators vs 6
  channels; CAN H/L swapped. RIP-UP.") — all three clauses verified here. No BOARD
  CORRECTION raised.
- Board facts re-confirmed by measurement, not re-derived: 140.15 × 100.15 mm edge bbox
  (= 140 × 100 design), 1.6 mm, 4 copper layers; In1 carries both 3V3 and GND zones, In2
  carries 1V1 (`verify_parity.py`), consistent with `AGENT_BOARD.md:92`.

## 8. UNVERIFIED

1. Firmware PWM-slice assignment for GPIO40 / pad 49 (§3.1).
2. End-to-end routability of the 7 nets after the channel is opened — step 1 is measured as
   *blocked today*, step 2 is *free*, the join between them is a routing task not done here.
3. Servo-rail current distribution if pin 2 is *kept* on CAN_5V (rejected in §6).

---

## 9. Reproduce

```
& 'C:/Program Files/KiCad/9.0/bin/python.exe' evidence/w2-da-connectors/freearea2.py     # free area + largest rect
& '...' pick_place.py       # exact row, both board artefacts
& '...' verify_row_all.py   # row clear on all six 140x100 boards
& '...' verify_parity.py    # nets/parity facts, layer map
& '...' escape_layer2.py    # per-layer escape lanes
& '...' probe_esc_conns.py  # ESC board connector inventory
```

Artefacts: `freearea2.out`, `pick_place.out`, `verify_row_all.out`, `verify_parity.out`,
`escape_layer2.out`, `corridor.out`, `esc_conns.json`.