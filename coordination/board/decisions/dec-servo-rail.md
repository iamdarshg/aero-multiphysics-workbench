# dec-servo-rail — the 0.75 A PTC and GPIO40 on drone-arm rev_b

**Verdict: COPPER.** No PTC part swap exists that restores physical fidelity, so this is
not a BOM fix; and it is not a respin either — the fix is deleting six pad-to-net
connections, not rebuilding the board.

Read-only audit. Board cited as `AGENT_BOARD.md`; no repo was written, no git touched.

---

## 1. The finding, verified — and re-pointed

The board's clause (`AGENT_BOARD.md:153`): *"the servo rail protection is undersized — a
0.75 A PTC against a 3–9 A requirement."* **The numbers are right. The attachment point is
not the one the board implies.**

There are **two** instances of the same part, and the one in the servo path is on the
**ESC** board, not the flight-control board:

| ref | board | schematic / BOM | pads |
|---|---|---|---|
| **F701** | ESC rev_b | `REV_B_BOM.csv:57` | 1 = `/Auxiliary power/CAN_5V_RAW`, 2 = `/Auxiliary power/CAN_5V_OUT` |
| **F1** | Flight Control rev_b | `power_usb.kicad_sch:3019–3096`, `REV_B_BOM.csv:140` | 1 = `/CAN_5V`, 2 = `/Power and USB/CAN_5V_FUSED` |

Part number and rating — identical on both:

| field | value | source |
|---|---|---|
| MPN | **1206L075/24WR** | `power_usb.kicad_sch:3064`; `REV_B_BOM.csv:57,140` |
| manufacturer | Littelfuse | `power_usb.kicad_sch:3055` |
| value / rating | **"PTC 0.75A"** | `power_usb.kicad_sch:3037`; BOM rows above |
| footprint | **`Fuse:Fuse_1206_3216Metric`** (EIA 1206, 3216 metric) | `power_usb.kicad_sch:3046` |
| land measured | 4.610 × 2.310 mm, pads 1.250 × 1.750 mm at 2.80 mm pitch | `raw/probe.out` §1 |

The part number encodes the rating: `1206L`**`075`**`/`**`24**`WR` → 0.75 A hold, 24 V
stand-off. **The trip current and the exact datasheet I-hold/I-trip curve are UNVERIFIED**
— littelfuse.com, digikey.com and the web-search provider all failed in this session
(HTTP 403 / provider misconfiguration). Everything below that depends on the 0.75 A figure
depends on the part-number field plus the schematic `Value`, i.e. on the design's own
declaration, not on a datasheet I read.

### 1.1 What is actually on the servo rail

Header pads, measured from copper (`raw/probe.out` §3):

```
J60  ESC_PWM_1  pin1 /CAN_GND   pin2 /CAN_5V   pin3 /RP2354B MCU/PWM_ESC1
J61  ESC_PWM_2  pin1 /CAN_GND   pin2 /CAN_5V   pin3 /RP2354B MCU/PWM_ESC2
J62  ESC_PWM_3  pin1 /CAN_GND   pin2 /CAN_5V   pin3 /RP2354B MCU/PWM_ESC3
J63  ESC_PWM_4  pin1 /CAN_GND   pin2 /CAN_5V   pin3 /RP2354B MCU/PWM_ESC4
J64  ESC_PWM_5  pin1 /CAN_GND   pin2 /CAN_5V   pin3 /RP2354B MCU/PWM_ESC5
J65  ESC_PWM_6  pin1 /CAN_GND   pin2 /CAN_5V   pin3 /RP2354B MCU/PWM_ESC6
J66  ABSENT from the board
```

So pin 2 of all six servo headers is **`/CAN_5V`** — the rail the board calls the servo
rail. Full chain, one cable:

```
ESC U703 LM5164DDA buck → L702 "33u 1.8A" → CAN_5V_RAW
   → F701 (PTC 0.75 A) → CAN_5V_OUT → J702.1 ──cable──> J2.1 → /CAN_5V
   → J60..J65 pin 2                                                     (servo rail)
   → and, on the flight board, /CAN_5V → F1 (second 0.75 A PTC) → D2 PMEG2010ER → /SYS_5V
```

Note the asymmetry this exposes: **F1 is not in the servo path.** F1 protects the flight
controller's own `/SYS_5V` branch; the servo headers tap `/CAN_5V` on the *upstream* side
of F1 (`raw/probe.out` §2 — `F1.1` and `J60..J65.2` share the net). The PTC that limits
the servo rail is **F701 on the ESC**.

## 2. What the servo rail actually needs

Requirement, `repos/drone-mech/highspeed_edf/design/PHASE15_CONTROL_SURFACES.md`:

| line | requirement |
|---|---|
| `:280` | Actuator count **6** |
| `:282` | Rail voltage **6.0 – 7.4 – 8.4 V**, *How* column: **"dedicated BEC"** |
| `:283` | Rail current (all 6, peak) **3 – 9 – 15 A**, *How*: "BEC + capacitors" |
| `:293` | Rail isolation **separate from ESC 5 V aux** — *hold* |
| `:344` | Actuator rail **6.0 – 7.4 – 8.4 V, 3 – 9 – 15 A** |
| `:349` | Actuator connector **keyed, ≥3 A contacts** |

Cross-checked in the repo's own acceptance catalog: `engineering_acceptance/catalog/
requirements.yaml:139` — `expected: {effectors: 7, board_pwm_outputs: 6, ...}`.

**REQUIRED: 3 A minimum, 9 A nominal, 15 A peak, at 6.0–8.4 V, isolated from the ESC 5 V
aux.** Delivered: 0.75 A at 5 V, sharing the ESC aux. Ratio at the nominal point
**0.75 / 9 = 0.083×**; per header 0.125 A available against 0.5 A needed at the 3 A floor.

Two of the three shortfalls have nothing to do with the PTC:

- **Voltage.** The rail is a 5 V output. Feedback divider R711 45.3 k / R712 14.3 k on
  `LM2_FB` (`raw/probe.out` §6) gives Vout = VREF × (1 + 45.3/14.3) = VREF × 4.1678;
  at the LM5164's 1.2 V reference that is **5.00 V**. Even at a 1.25 V reference it is
  5.21 V — **still below the 6.0 V floor**, and no servo torque spec survives 5 V when the
  requirement is written for 6.0–8.4 V.
- **Source current.** `REV_B_ARCHITECTURE.md:127` — "two independent LM5164 **1 A** buck
  rails"; `:130` — "one fused 5 V rail exported to the flight-control board". The buck
  feeding this rail is U703 `LM5164DDA`, and its inductor is L702, value literally
  **"33u 1.8A"**. The rail is capped three times over: **1 A converter / 1.8 A inductor /
  0.75 A PTC.**

That is why the PTC is the smallest of the three problems, and why changing it alone would
be cosmetic.

## 3. The requested search: is there a 1206 PTC at 3–9 A?

**No drop-in exists.** A 1206 PPTC lands at roughly 2 A hold at the top of the families
known to this audit (Littelfuse `1206L` → the `200` = 2.0 A member); 3 A is outside the
1206 thermal envelope. **This is UNVERIFIED** — external datasheet access was blocked
(§8), so I cannot cite a datasheet row for the family's ceiling. The honest statement is:
*no 1206 part rated 3–9 A is known to this audit, and nothing in the repository proposes
one.*

Package ladder, for the next-smallest step:

| package | body (nominal) | typical PPTC ceiling | reaches 3 A? |
|---|---|---|---|
| 1206 / 3216 | 3.2 × 1.6 mm | ~2 A | **no** |
| 1812 / 4532 | 4.5 × 3.2 mm | ~2 A | **no** |
| **2920 / 7452** | **7.2 × 5.2 mm** | **3 A class** (e.g. Littelfuse `2920L300`) | yes |

So the next-smallest package change is **1206 → 2920, skipping 1812** (1812 does not reach
3 A either). All the ratings in that table except the 1206/1812 body sizes are
**UNVERIFIED-against-datasheet**.

**Boards a package change would affect: 2** — F1 on `main_rev_b` and F701 on `esc_rev_b`,
one placement each, no other instances of the MPN in either BOM.

**And it does not fit.** The F1 site is a 4.61 × 2.31 mm land with a 2920 land needing
~7.90 × 5.30 mm. Measured clearance (`raw/probe.out` §5, identical on
`main_rev_b_completed` and `main_rev_b_final`):

```
D2   PMEG2010ER        gap_x =  1.275 mm   (directly east)
D50  PESD2CANFD24L-T   gap_y =  1.120 mm   (directly south)
```

1.275 mm of air where ~3.3 mm more is needed. A 2920 at F1 therefore requires **moving D2
and D50** — a copper change, i.e. exactly the rework the owner steer says to avoid when a
part swap would do. It would not.

## 4. GPIO40

**Not brought out.** `U10` (RP2354B, QFN-80) pad **49** is `GPIO40/ADC0` and carries the
net `unconnected-(U10-GPIO40/ADC0-Pad49)` — measured on copper (`raw/probe.out` §4) at
(61.030, 39.100). `mcu_pinmap.json` maps exactly **40** pins, keys `"0"`–`"39"`, so GPIO40
is absent from the board's own pin map as well.

**Does the firmware need it?** *Cannot be established from source*: the repo contains
**zero `.c`/`.h` files** (recursive count = 0), and `docs/engineering/
FIRMWARE_SOURCE_AUDIT.md:5–9` records that 36 source files and 13 include dirs are absent
and "a main-board or ESC image cannot be built from this checkout". **UNVERIFIED.**

What *is* decidable is the contract: `requirements.yaml:139` expects
`{effectors: 7, board_pwm_outputs: 6}` with the condition *"each current-configuration
effector has a unique realizable command and feedback path; **do not invent a seventh
pin**"*, and the acceptance fixture is `seven_independent_servos_with_six_outputs`
(`mandatory_checks.yaml:36`, BASE-013). So the stated contract does **not** require a
seventh PWM pin. Bringing GPIO40 out is optional, not mandatory.

**Can a spare pad on an existing connector carry it, with no new footprint?** Yes — and
the fix in §5 is what creates the pad. Once pin 2 of `J60–J65` stops being `/CAN_5V`,
**six 2.54 mm pads on six already-placed headers become spare**, any one of which can take
`PWM_ESC7`. The only other unconnected connector pads on the board are `J1.A8`/`J1.B8`
(USB-C SBU1/SBU2), which are inside a receptacle and not a harness exit. No new footprint
is needed in either case. Cost: U10.49 → J60.2 is **≈38.7 mm** of new route
(√(19.51² + 33.40²)); that is copper, and the lane pressure is already the recorded
reason this connector block was rejected once (`AGENT_BOARD.md:54`, 0 free lanes at pads
43–49). **Routability of that 38.7 mm is UNVERIFIED here.**

## 5. The least-effort fix that keeps physical fidelity

Under the owner steer — part swap beats copper, copper beats stackup, fab burden free,
design rework is what we avoid — the ordering inverts, because the part swap that would
be needed does not exist:

1. **A bigger PTC is not available.** §3: no 1206 or 1812 reaches 3 A; a 2920 does not fit
   the site without moving D2 and D50.
2. **Even a hypothetical 3 A PTC does not fix it.** §2: the rail is 5.00 V against a 6.0 V
   floor, fed by a 1 A LM5164 through a 1.8 A inductor, and the requirement at
   `PHASE15:293` demands the servo rail be *isolated* from the ESC 5 V aux — which is
   precisely what this rail is. A 3 A PTC on a 5 V, 1 A, non-isolated rail is a false
   green.
3. **The requirement never intended the board to power servos.** Its own *How* column for
   the rail is **"dedicated BEC"** (`PHASE15:282`) and "BEC + capacitors" (`:283`).
   Pin 2 on the servo headers is a design error, not an under-specification.

So the minimal physically-faithful change is to make the headers what they should have
been — signal + signal ground — and let a BEC carry 7.4 V:

- **Disconnect pin 2 of `J60–J65` from `/CAN_5V`** (6 pad connections deleted; the net
  survives for `J2`/`F1`/`D2`, which is its real job).
- **No new footprint, no new layer, no stackup change, no outline change.**
- Optionally route `GPIO40` to one freed pin-2 pad for a 7th channel (§4): one new route,
  no new part.
- Keep `F1` and `F701` at 0.75 A. They become correct once they are no longer asked to
  carry servo stall current — F1 protects the FC's own 5 V branch, F701 the exported aux
  rail, and 0.75 A is right for both.

This is a **copper** fix (deletion, plus one optional route). Not a BOM fix, because
nothing can be fixed by changing a part number. Not a respin, because no footprint, layer,
stackup or outline changes.

## 6. BOARD CORRECTION

**BOARD CORRECTION: `AGENT_BOARD.md:165`** — option 1, *"Respecify"* the PTC, is not
physically available. No 1206 or 1812 PPTC reaches the 3 A floor, a 2920 does not fit the
F1 site (1.275 mm clearance to D2 where ~3.3 mm is needed), and even a 3 A part would leave
the rail at 5.00 V (floor 6.0 V, `PHASE15:282`) behind a 1 A LM5164 and a 1.8 A inductor
(`REV_B_ARCHITECTURE.md:127`, L702 "33u 1.8A"). Only the second option — split the rail to
a dedicated BEC — is real.

**No number on the board is wrong.** `:153`'s "0.75 A PTC against a 3–9 A requirement" is
correct as far as it goes; it understates in that the rail also misses on *voltage* and on
*source current*, which is why the PTC swap reads as sufficient when it is not.

**Observation, not a correction (belongs to da-gerbers / da-connectors):** the outline
differs between board variants — `main_rev_b_completed.kicad_pcb` Edge.Cuts = **140.150 ×
100.150 mm** with **no** J60–J65 populated; `main_rev_b_final.kicad_pcb` Edge.Cuts =
**130.050 × 74.570 mm** with J60–J65 at y = 72.500. The servo-header board and the
140 × 100 gerber package are not the same outline. Flagged, not resolved here.

## 7. UNVERIFIED

1. **Littelfuse 1206L075/24WR datasheet values** — I-hold 0.75 A and Vmax 24 V are taken
   from the part-number fields (`075`, `24`) and the schematic `Value`, not read off a
   datasheet. I-trip, I-max and the trip-time curve are unknown. littelfuse.com and
   digikey.com both returned HTTP 403; the web-search provider is misconfigured at host
   level ("multiple usable web providers are registered"), which a subagent cannot change.
2. **PPTC package ceilings** (1206 ≈ 2 A, 1812 ≈ 2 A, 2920 = 3 A class) — same block, plus
   the `2920L300` part number is from memory, not a fetched page. Treat §3's ladder as a
   hypothesis that needs one datasheet fetch to become evidence.
3. **LM5164 feedback reference = 1.2 V** — assumed; the 5.00 V figure is therefore
   `VREF × 4.1678`. Bounded: any VREF in 1.0–1.25 V gives 4.17–5.21 V, all below the 6.0 V
   floor, so the conclusion survives the assumption.
4. **Whether the firmware wants a 7th PWM channel** — no firmware source in the repo (§4).
5. **Routability of GPIO40 → a freed pin-2 pad** over ≈38.7 mm.
6. The `.xml` netlists in `reports/` (`main_rev_b_netlist.xml`, `netlist.xml`,
   `main_net.xml`) contain **no J60–J66 nodes at all** and list `/CAN_5V` as only
   {F1.1, J2.1}. Every connector claim here therefore comes from the **`.kicad_pcb`
   copper**, which is authoritative; the netlist files are stale or sheet-partial. Earlier
   work that cited "net 49 CAN_5V = {F1.1, J2.1, J60–J65.2}" (`evidence/w2-da-connectors/
   REPORT.md:242`) agrees with the copper, so the two sources are reconciled — the XML is
   the one that is wrong.

## 8. Reproduce / artefacts

```
& 'C:/Program Files/KiCad/9.0/bin/python.exe' evidence/dec-servo-rail/probe.py
```

| file | contents |
|---|---|
| `probe.py` | the read-only measurement script (pcbnew, no board writes) |
| `raw/probe.out` | its full output: F1 pads, `/CAN_5V` membership, J60–J65 pad nets, U10.49, F1 clearances, ESC F701/L702/R711/R712/U703 |
| `raw/source-citations.txt` | schematic / BOM / requirement / architecture line citations with line numbers |

pcbnew runs: `main_rev_b_final.kicad_pcb`, `main_rev_b_completed.kicad_pcb`,
`esc_rev_b.kicad_pcb`. Load only — no `SaveBoard`, no repo file touched.