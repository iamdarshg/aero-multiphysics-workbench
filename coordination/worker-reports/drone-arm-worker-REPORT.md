# Engineering Audit — `drone-arm` (drone-arm repository)

**Role:** worker agent, read-only audit. **Scope:** this repository only.

| Item | Value |
|---|---|
| Repository | `E:\engineering-portfolio-audit\repos\drone-arm` |
| Commit audited | `07268c3966b8bec2b2587d8b848e6fa50ff80ee2` |
| Branch (checked out) | `work/2026-11-11` |
| Date of audit | Thu Nov 12 2026 |
| KiCad CLI | 9.0.7 |
| pcbnew (bundled Python 3.11.5) | 9.0.7 |
| Board under audit | `hardware/main/rev_b/main_rev_b.kicad_pcb` |
| Root schematic | `hardware/main/rev_b/main_rev_b.kicad_sch` |

**Read-only statement.** No PCB or schematic file was modified. Every `pcbnew` script
calls `LoadBoard()` and never `SaveBoard()`. No `git reset`, no history rewrite, no push.
Branch `audit/drone-arm-da-g1` was **not** checked out and not touched. Verified after the
audit: `git status --porcelain` clean, `HEAD` still `07268c39`, `git diff --name-only HEAD --
"*.kicad_pcb" "*.kicad_sch"` returns 0 files.

> **Directory-collision note.** This evidence directory is also being written by a concurrent
> process (files `01_*` … `21_make_report.py`, and a 20 091-byte `REPORT.md` that is not mine).
> That process overwrote my `REPORT.md` once during this session. My authoritative copy is
> **`REPORT_worker-drone-arm-agent.md`**; `REPORT.md` is kept identical as a best-effort copy.

---

## Established facts — independently re-verified

| Claim given | Verified? | Evidence |
|---|---|---|
| DRC on `main_rev_b.kicad_pcb` → 0 violations, 0 unconnected | **Yes** | `drc_stdout.txt`, `drc_main_rev_b.json` ("Found 0 violations / Found 0 unconnected items") |
| ERC on ROOT sheet → 1 warning, `lib_symbol_mismatch` on `L_Coupled` | **Yes** | `erc_root.json`, `erc_stdout.txt` → `warning \| lib_symbol_mismatch \| Symbol 'L_Coupled' doesn't match copy in library 'Device'` |
| Stackup F.Cu 35 µm → prepreg 200 µm FR4 Dk4.2 → In1.Cu → core 1.04 mm → In2.Cu → prepreg 200 µm → B.Cu | **Yes** | `stackup_raw.txt` (parsed from the board's `(stackup)` block) |

I did **not** run ERC on `rf_915.kicad_sch` standalone, per instruction.

---

# TASK 1 — Which plane do the RF traces reference?

## 1.1 Method

1. `pcbnew.LoadBoard()` on `main_rev_b.kicad_pcb`.
2. Enumerated all 5 zones; recorded net, layer set, fill state, fill outline count, and
   **filled** area from the zone's filled polygon set (`ZONE::GetFilledPolysList()` /
   `GetFilledArea()`), never the zone outline.
3. **Defined the RF set objectively**: the board assigns nets to a netclass called
   **`RF_50R`** (16 nets). This is the design's own declaration of which nets are the RF
   signal path, so it is used as the primary set — not a name-matching heuristic.
   (An initial naive regex on `915|RF|ANT|GNSS` over-matched `inte*rf*ace` and
   `Redund*ant*`; that is why the netclass anchor is used instead.)
4. Collected every **F.Cu** track segment on those nets, sampled along each at 0.05 mm
   (plus 0.025 and 0.01 mm as a stability check), and for each sample point tested
   containment against the filled polygons of the **In1.Cu** `/3V3` and `/GND` zones.
5. Cross-validated the containment test with an independent API.

## 1.2 Zone inventory

| # | Net | Layer | Filled? | Fill outlines | Filled area (mm²) |
|---|---|---|---|---|---|
| 0 | `/GND` | F.Cu | yes | 14 | 12188.556 |
| 1 | `/GND` | B.Cu | yes | 4 | 12728.793 |
| 2 | `/3V3` | **In1.Cu** | yes | 3 | **12164.050** |
| 3 | `/GND` | **In1.Cu** | yes | 177 | **82.183** |
| 4 | `/1V1` | In2.Cu | yes | 2 | 256.050 |

Board outline bbox: 140.15 × 100.15 mm (14036 mm²).

**In1.Cu is effectively a /3V3 power plane.** Of ~12246 mm² of In1.Cu zone copper,
12164.050 mm² is `/3V3` and only **82.183 mm² (0.67%) is `/GND`**, fragmented into 177 small
outlines. There are no other nets on In1.Cu. In2.Cu carries only `/1V1` on 256.05 mm² — it is
not a return plane either.

**The real ground planes are F.Cu (12188 mm²) and B.Cu (12728 mm²), and both are on the
wrong side of the dielectric to serve as a reference for F.Cu traces** (see §1.8).

## 1.3 Headline result — RF traces on F.Cu

Totals over **68** F.Cu segments / **102.354 mm** of total RF length, all **0.35 mm** wide.
Lengths are attributed per sample point (each sample carries `segment_length / n_samples`).

| Underneath (In1.Cu), at sample step | over `/GND` | over `/3V3` | over neither | over other | over both |
|---|---|---|---|---|---|
| 0.05 mm (primary) | **0.00%** | **88.91%** | **11.09%** | 0.00% | 0.00% |
| 0.025 mm | 0.00% | 88.91% | 11.10% | 0.00% | 0.00% |
| 0.01 mm | 0.00% | 88.89% | 11.11% | 0.00% | 0.00% |

The result is stable to <0.03 percentage points across a 5× change in sample density, so it
is not a sampling artifact. Sanity check: attributed length sums to 102.3543 mm = measured
length exactly.

## 1.4 Per-net detail (step 0.05 mm)

| Net | Class | Segs | Length (mm) | Width | /GND | /3V3 | neither |
|---|---|---|---|---|---|---|---|
| `/915 MHz RF/ANT_915` | RF_50R | 4 | 15.428 | 0.35 | 0.00 | 100.00 | 0.00 |
| `/915 MHz RF/CC1121_RF` | RF_50R | 1 | 1.175 | 0.35 | 0.00 | 100.00 | 0.00 |
| `/915 MHz RF/CC_LNA_N` | RF_50R | 3 | 3.463 | 0.35 | 0.00 | 1.30 | **98.70** |
| `/915 MHz RF/CC_LNA_P` | RF_50R | 1 | 4.938 | 0.35 | 0.00 | 41.00 | 59.00 |
| `/915 MHz RF/CC_PA` | RF_50R | 7 | 5.322 | 0.35 | 0.00 | 27.79 | 72.21 |
| `/915 MHz RF/CC_PA_BIAS` | RF_50R | 4 | 4.722 | 0.35 | 0.00 | 100.00 | 0.00 |
| `/915 MHz RF/MATCH_A` | RF_50R | 9 | 12.092 | 0.35 | 0.00 | 100.00 | 0.00 |
| `/915 MHz RF/MATCH_B` | RF_50R | 6 | 7.772 | 0.35 | 0.00 | 100.00 | 0.00 |
| `/915 MHz RF/RF_LNA_IN` | RF_50R | 2 | 2.460 | 0.35 | 0.00 | 100.00 | 0.00 |
| `/915 MHz RF/RF_PA_INOUT` | RF_50R | 3 | 1.947 | 0.35 | 0.00 | 100.00 | 0.00 |
| `/915 MHz RF/RF_PA_OUT` | RF_50R | 5 | 4.722 | 0.35 | 0.00 | 100.00 | 0.00 |
| `/915 MHz RF/RF_TR_SW` | RF_50R | 4 | 2.778 | 0.35 | 0.00 | 100.00 | 0.00 |
| `/915 MHz RF/RX_COMBINE` | RF_50R | 2 | 2.625 | 0.35 | 0.00 | 100.00 | 0.00 |
| `/915 MHz RF/SAW_PA` | RF_50R | 4 | 3.912 | 0.35 | 0.00 | 100.00 | 0.00 |
| `/GNSS/GNSS_RF_ANT` | RF_50R | 9 | 17.929 | 0.35 | 0.00 | 100.00 | 0.00 |
| `/GNSS/GNSS_RF_IN` | RF_50R | 4 | 11.070 | 0.35 | 0.00 | 89.37 | 10.63 |

**No RF net touches In1 `/GND` anywhere.** Every net that deviates from 100% `/3V3` does so
by passing over a *void* in the In1 pour, not by passing over ground.

Broader context set (all F.Cu in the `/915 MHz RF/` and `/GNSS/` sheets, incl. power/decoupling
nets — 212 segments, 278.789 mm): `/GND` 0.24%, `/3V3` 79.43%, neither 20.32%. The same
conclusion holds.

## 1.5 What is actually below the trace (full stack)

Splitting the 11.09% "neither" by what else lies under each sample point:

| In1 `/3V3` | In1 `/GND` | In2 `/1V1` | B.Cu `/GND` | Length (mm) | % |
|---|---|---|---|---|---|
| yes | no | no | yes | 90.4709 | 88.39 |
| **no** | no | no | yes | 10.3124 | 10.08 |
| **no** | no | no | no | 1.0382 | 1.01 |
| yes | no | no | no | 0.5328 | 0.52 |

Check: 88.39 + 0.52 = 88.91 (the `/3V3` figure) and 10.08 + 1.01 = 11.09 (the "neither"
figure), consistent with §1.3. Where In1 has no copper, the nearest In1 copper is
0.29–2.01 mm away laterally (mean 0.29–1.14 mm per net) — these are pour voids, not board
edges. In 10.08% of the run the only conductor below is **B.Cu `/GND`, 1.510 mm away**
(200 + 35 + 1040 + 35 + 200 µm). In2 `/1V1` is beneath **0%** of the RF run.

## 1.6 Coplanar return (measured, not assumed)

F.Cu does carry a 12188 mm² `/GND` pour, so coplanar return is a real possibility — worth
measuring rather than dismissing. Distance from the RF **centreline** to the nearest F.Cu
`/GND` copper: min 0.4255 mm, median 0.4255 mm, p90 0.7505 mm, max 1.7252 mm; **0%** of
samples are within 0.35 mm. With a 0.35 mm trace (half-width 0.175 mm) that is an edge gap of
≥0.2505 mm (median), i.e. the pour is held back by the zone clearance. Coplanar return
coupling therefore exists but is loose and geometry-dependent, not a controlled CPW.

## 1.7 Verdict on the claim

> Claim: *all 915 MHz and GNSS RF traces (0.35 mm, F.Cu) run 100% over the In1 `/3V3` zone and 0% over `/GND`.*

| Element of claim | Verdict | Measured |
|---|---|---|
| RF traces are 0.35 mm on F.Cu | **Confirmed** | 68/68 F.Cu RF_50R segments exactly 0.35 mm |
| **0% over `/GND`** | **Confirmed exactly** | **0.00%** at all three sample densities |
| **100% over `/3V3`** | **Refuted as stated** | **88.91%** — 11.09% runs over no In1 copper at all |

The claim's *direction* is right and important: the RF lines reference the **3V3 power plane**,
never the In1 ground plane. Its *magnitude* is overstated — "100%" is really 88.9%, and the
remaining 11.1% has no reference plane on In1 whatsoever.

Scope note: the claim concerns F.Cu only and that is what is measured above. For completeness,
2 further RF_50R segments run on **In2.Cu** (net `/915 MHz RF/CC_LNA_N`, 1.84 mm total, 0.35 mm
wide) reached by **two F.Cu→B.Cu through-vias** (0.3 mm drill / 0.6 mm pad) at (101.0, 60.8) and
(99.3, 61.0). Those are outside the F.Cu claim but are part of the RF path and are worth noting.

## 1.8 Engineering consequence

Stated carefully, as a **design-review geometry finding**:

- The stackup places the nearest plane 200 µm below the F.Cu RF traces (verified from the
  board's own `(stackup)` block). That nearest plane is `/3V3`, occupying 12164 mm² of In1.Cu.
- **A microstrip assumes a solid return plane directly beneath the trace. A power plane is not
  a ground return.** The `/3V3` pour is not a 0 V node and is not the reference the RF driver
  and receiver use. Return current must complete its loop through that plane and find its way
  back to the ground reference of U30/U40 — a path this geometry does not define. That means
  an uncontrolled return path with a large loop area, and direct coupling of the RF return into
  the 3V3 supply network (and the supply's noise into the RF path).
- The next genuine ground is B.Cu `/GND` at **1.510 mm**. At that separation a 0.35 mm trace is
  not a controlled-impedance transmission line in any useful sense; the field spreads far wider
  than the trace and the structure is effectively an uncontrolled printed inductor with
  capacitive coupling to whatever is nearby. The 10.08% of the run that has only B.Cu `/GND`
  below it is the weakest case.
- In2.Cu cannot help: it carries `/1V1` on 256 mm² and lies beneath 0% of the RF run.

**What this is not.** No field solver was run. No S-parameters, no characteristic impedance,
no insertion loss, no common-mode rejection figure is produced or implied. This report asserts
nothing about how much the 915 MHz or GNSS links actually degrade — only that the return-plane
geometry does not match the microstrip assumption, that 88.9% of the RF run references a power
plane, and that 11.1% references nothing on In1. Quantifying insertion loss / impedance
discontinuity requires a 3-D field solve or VNA measurement, neither of which was performed.

## 1.9 Validation of the measurement itself

`task1_validation.py` → `task1_validation.json`:

- Two **independent** containment APIs (`SHAPE_POLY_SET::Contains` vs
  `ZONE::HitTestFilledArea`) agree on **8000/8000** random board-wide trials (100.00%).
- In1 `/GND` and `/3V3` filled areas **never overlap** (0 hits in 2000 random trials), so the
  "both" category being 0.00% is real, not a category collision.
- Each zone's largest fill-outline centroid tests inside its own polyset (self-test passes).
- A point 50 mm outside the board tests outside both polysets (negative control passes).

---

# TASK 2 — CAN common-mode choke FL50

## 2.1 Identity

| Field | Value |
|---|---|
| Reference | `FL50` |
| Value / MPN | `ACT45B-110-2P-TL003` (manufacturer field: **TDK**) |
| Footprint | `Inductor_SMD:L_CommonModeChoke_Coilank_ACM4532` |
| Footprint description | "Coilank common-mode choke, 4 Pin (lcsc C49073870), generated with kicad-footprint-generator ipc_noLead_generator.py" |
| Position / rotation | (15.000, 20.000) mm, 0°, F.Cu |
| Pad style | 4 × SMD, 1.15 × 1.55 mm, no drill |

Note the footprint is a **Coilank ACM4532** land pattern while the fitted part is a **TDK
ACT45B**. Both are 4532-size CAN common-mode chokes, so this reads as a deliberate
cross-reference — but it is exactly the situation where a pinout difference would be
introduced silently.

## 2.2 Pads, nets, exact positions

| Pad | Net | X (mm) | Y (mm) | Grid slot |
|---|---|---|---|---|
| **1** | `/CAN interface/U50_CANH` (transceiver side) | 13.175 | 18.875 | top-left |
| **4** | `/CANL` (bus side) | 16.825 | 18.875 | top-right |
| **2** | `/CANH` (bus side) | 13.175 | 21.125 | bottom-left |
| **3** | `/CAN interface/U50_CANL` (transceiver side) | 16.825 | 21.125 | bottom-right |

## 2.3 Geometry — the pairing

The four pads form a clean 2 × 2 grid on axes:

- Columns (shared x): **x = 13.175** → {1, 2}; **x = 16.825** → {4, 3}. Column pitch **3.65 mm**.
- Rows (shared y): **y = 18.875** → {1, 4}; **y = 21.125** → {2, 3}. Row pitch **2.25 mm**.
- Diagonals {1,3} and {2,4}: **4.2878 mm**.

The **short** axis is vertical (2.25 mm), and the pads that share an **x column** are the
2.25 mm-apart pair. Geometry therefore groups the part as **{1,2}** and **{3,4}** — two
windings, one per column. These are also the consecutive pad numbers.

## 2.4 What the board actually does

With column pairing:

- **Winding {1→2}** carries `/CAN interface/U50_CANH` → `/CANH`. That is: U50 (TCAN3413)
  transceiver CANH → choke → bus-side CANH (to J2 / D50 / R122).
- **Winding {3→4}** carries `/CAN interface/U50_CANL` → `/CANL`. Transceiver CANL → choke →
  bus-side CANL.

So **each winding sits in series with exactly one differential line, and the two lines are not
interchanged.** That is the standard common-mode-choke application topology, and it is what the
board implements. Supporting evidence: pads 1/2/3/4 each carry exactly one net, and each net
appears on exactly one pad of FL50 (no pad-to-pad shorts, `task2_fl50.json` →
`tracks_leaving_pads`).

The **schematic agrees with the board**. `Device:L_Coupled` in `interfaces.kicad_sch` defines
pins at 1 = (−5.08, 2.54), 2 = (−5.08, −2.54), 4 = (5.08, 2.54), 3 = (5.08, −2.54) — i.e. left
coil {1,2}, right coil {3,4}, the same grouping and the same physical ordering as the footprint.

The sibling board is consistent too: `FL201` on `hardware/esc/rev_b/esc_rev_b.kicad_pcb` has
pad 1 = `U206_CANH`, pad 2 = `CANH`, pad 3 = `U206_CANL`, pad 4 = `CANL`, in the identical
2 × 2 arrangement (`task2_crosscheck_esc.txt`). So this is a repeated design decision across
both boards, not a one-off placement slip.

## 2.5 The open question (deliberately not resolved)

**Whether the board is correct depends on the TDK ACT45B-110-2P-TL003 datasheet's
terminal-to-winding assignment, which is not present in this repository.** I checked: 37 PDFs
exist under `docs/datasheets/` and `docs/reference-designs/`, and **none is a TDK ACT45B**
common-mode-choke datasheet. The schematic's `Datasheet` field for FL50 is empty.

Two hypotheses, both consistent with the geometry:

| If the ACT45B windings are… | Then this board… | Consequence |
|---|---|---|
| **{1,2} and {3,4}** (what the board assumes) | is **correct** | Each line through one winding; CM flux from the pair cancels in the core; DM sees ~0 inductance. Intended behaviour. |
| **{1,4} and {2,3}** (the other common 4-pin CMC convention) | **crosses the pair** | Winding {1,4} = U50_CANH ↔ bus CANL; winding {2,3} = bus CANH ↔ U50_CANL. CANH and CANL would be swapped transceiver-to-bus, and the windings' relative sense would be reversed, so the choke's common-mode vs differential-mode behaviour would invert — CM rejection degraded and differential series inductance added to the CAN FD edges. |

I am **not** asserting it is wrong. What can be said without the datasheet:

- The board, the schematic symbol, and the ESC board all commit to the **{1,2} / {3,4}** grouping.
- The footprint used is a **Coilank ACM4532** pattern, not a TDK-authored ACT45B pattern. If the
  two vendors number terminals differently, a correct-looking footprint/label pairing can still
  produce a wrong winding assignment. The ACM4532 land pattern being used for an ACT45B part is
  the specific risk factor here.
- **The decisive check is two-part and cheap:** (a) obtain the TDK ACT45B-110-2P-TL003 datasheet
  terminal-to-winding map; (b) confirm on a physical part with an ohmmeter — winding continuity
  should read ~110 µH/low DC resistance between pads **1–2 and 3–4** if this board is correct,
  and between **1–4 and 2–3** if it is not. That measurement settles it; nothing in this
  repository can.

Related observation: ERC's single warning on this design is
`lib_symbol_mismatch: Symbol 'L_Coupled' doesn't match copy in library 'Device'` — and
`L_Coupled` **is FL50's symbol**. The symbol in the schematic has diverged from the library
copy, so even the symbol's pin definition cannot be assumed pristine. This makes the datasheet
check more, not less, worth doing.

For context: the CAN front end also has `D50` (PESD2CANFD24L-T ESD array on CANH/CANL),
`R122` (120 Ω, marked **DNP**) across `U50_CANH`/`U50_CANL`, and `R3` (0 Ω "STAR") tying
`/CAN_GND` to `/GND`. FL50 has **no** centre-tap/ground pad — it is a 2-winding, 4-terminal part.

---

# TASK 3 — Schematic/board parity for ESC PWM

## 3.1 Method

`kicad-cli sch export netlist --format kicadsexpr` run on the **root** sheet
(`main_rev_b.kicad_sch`), parsed for net → node connectivity, then compared against
`LoadBoard()`. Netlist export exit code 0, 288 668 bytes.

## 3.2 Schematic side — the nets and parts DO exist

Six nets exist, all in the `/RP2354B MCU/` hierarchy:

| Net | U10 node | Connector node |
|---|---|---|
| `/RP2354B MCU/PWM_ESC1` | `U10` pad **43** (GPIO34) | `J60` pad 3 |
| `/RP2354B MCU/PWM_ESC2` | `U10` pad **44** (GPIO35) | `J61` pad 3 |
| `/RP2354B MCU/PWM_ESC3` | `U10` pad **45** (GPIO36) | `J62` pad 3 |
| `/RP2354B MCU/PWM_ESC4` | `U10` pad **46** (GPIO37) | `J63` pad 3 |
| `/RP2354B MCU/PWM_ESC5` | `U10` pad **47** (GPIO38) | `J64` pad 3 |
| `/RP2354B MCU/PWM_ESC6` | `U10` pad **48** (GPIO39) | `J65` pad 3 |

The connectors are `ESC_PWM_1` … `ESC_PWM_6`,
footprint `Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical`, with
pin 1 = `/CAN_GND`, pin 2 = `/CAN_5V`, pin 3 = `PWM_ESCn`.

## 3.3 Board side — they are absent

| Check | Result |
|---|---|
| `J60`…`J65` footprints on board | **none** (all six `false`) |
| Board connectors present | only `J1`, `J2`, `J10`, `J30`, `J40` |
| Any board footprint matching `J6x` | **none** |
| Board nets containing `PWM_ESC` | **0** |
| `U10` footprint on board | **yes** |

`U10` pads 43–48 physically exist on the board but carry **no net** — KiCad names them with the
`unconnected-` prefix:

| Pad | Board net | Schematic net | Match |
|---|---|---|---|
| 43 (GPIO34) | `unconnected-(U10-GPIO34-Pad43)` | `/RP2354B MCU/PWM_ESC1` | **MISMATCH** |
| 44 (GPIO35) | `unconnected-(U10-GPIO35-Pad44)` | `/RP2354B MCU/PWM_ESC2` | **MISMATCH** |
| 45 (GPIO36) | `unconnected-(U10-GPIO36-Pad45)` | `/RP2354B MCU/PWM_ESC3` | **MISMATCH** |
| 46 (GPIO37) | `unconnected-(U10-GPIO37-Pad46)` | `/RP2354B MCU/PWM_ESC4` | **MISMATCH** |
| 47 (GPIO38) | `unconnected-(U10-GPIO38-Pad47)` | `/RP2354B MCU/PWM_ESC5` | **MISMATCH** |
| 48 (GPIO39) | `unconnected-(U10-GPIO39-Pad48)` | `/RP2354B MCU/PWM_ESC6` | **MISMATCH** |
| 49 (GPIO40) | `unconnected-(U10-GPIO40/ADC0-Pad49)` | `unconnected-(U10-GPIO40/ADC0-Pad49)` | match (control) |

Pad 49 is the control case: unconnected on **both** sides, and the comparison correctly reports
agreement there. The divergence is specific to pads 43–48.

## 3.4 Component-level delta (both directions checked)

| Direction | Count | Refs |
|---|---|---|
| In schematic netlist | 167 | — |
| On board | 165 | — |
| **In schematic, NOT on board** | **6** | `J60`, `J61`, `J62`, `J63`, `J64`, `J65` |
| On board, NOT in schematic | 4 | `H1`, `H2`, `H3`, `H4` (mounting holes — expected board-only) |

The delta is **exactly** the six ESC PWM connectors plus four mounting holes. Nothing else
diverges.

## 3.5 Verdict

**Claim verified, in both directions.**

- **Schematic has them; board does not.** `PWM_ESC1..6` and `J60..J65` exist in the root-sheet
  netlist and are entirely absent from `main_rev_b.kicad_pcb` (no footprints, no nets).
- So the PCB implements **no ESC PWM interface at all** — not a miswired one, an absent one.
- The `U10` pads that would drive it (43–48) are present but floating.

Additional finding worth flagging: **`J60`–`J65` are also absent from the BOM.**
`docs/hardware/REV_B_BOM.csv` and `hardware/rev_b_grouped_bom.csv` contain no `ESC_PWM` or
`J6x` entries. So the BOM and the board agree with each other and both disagree with the
schematic. This is a coherent story — an ESC PWM connector block that was drawn in the
schematic and never carried through to layout or BOM — rather than an isolated layout omission.

I make no claim about *intent* (deferred feature vs. regression); that is not determinable from
the repository contents alone.

---

# Verification status

**Verified with commands whose full output is saved:**
DRC (0/0), ERC on root (1 warning), stackup, zone inventory and filled areas, RF netclass
membership, RF geometry and plane-overlap percentages at three sample densities, containment
cross-check against a second API, FL50 pad geometry/nets/positions, schematic netlist
connectivity for FL50 and for the ESC PWM block, board-vs-schematic component delta.

**Explicitly NOT verified / not verifiable here:**

1. **No field solve, no S-parameters, no impedance, no loss numbers** for the RF traces. Task 1
   is a geometry finding only. The quantitative RF penalty is unknown from this repository.
2. **Whether FL50 is electrically correct** — requires the TDK ACT45B-110-2P-TL003 datasheet
   (not in this repository) and/or a continuity measurement on a physical part.
3. **Whether the ESC PWM block was intentionally deferred** — not determinable from the repo.
4. **Whether RF traces actually meet any impedance target** — no impedance target is stated
   anywhere I found, so "meets/does not meet target" cannot be assessed.
5. Zone fill state was read **as stored in the file**; I did not re-run a zone fill. If the
   stored fills are stale relative to the current outlines, the In1 geometry could differ. The
   file reports all 5 zones as filled, so this is a low but non-zero risk.

---

# Evidence file index

Location: `E:\engineering-portfolio-audit\evidence\drone-arm-agent\`

**Tooling / provenance**
- `tool-versions.txt` — kicad-cli 9.0.7, pcbnew 9.0.7, Python 3.11.5
- `stackup_raw.txt` — `(stackup)` block extracted verbatim from the board

**DRC / ERC**
- `drc_stdout.txt`, `drc_main_rev_b.json` — DRC on `main_rev_b.kicad_pcb`
- `erc_stdout.txt`, `erc_root.json` — ERC on root sheet
- `sch_netlist.net` (288 668 B), `netlist_stdout.txt` — root-sheet netlist export

**Task 1**
- `probe_api.py` — pcbnew 9.0 zone/polyset API surface probe
- `probe_netclass.py`, `probe_netclass.txt` — netclass discovery (found `RF_50R`)
- `task1_rf_plane.py`, `task1_stdout.txt`, `task1_rf_plane.json` — main analysis
- `task1_validation.py`, `task1_validation.txt`, `task1_validation.json` — independent-API cross-check
- `task1_under_trace_stack.py`, `.txt`, `task1_under_trace_stack.json` — full-stack breakdown
- `task1_layer_distribution.py`, `.txt`, `task1_layer_distribution.json` — RF geometry by layer
- `task1_rf_non_fcu.py`, `.txt`, `task1_rf_non_fcu.json` — the In2.Cu segments and through-vias

**Task 2**
- `task2_fl50.py`, `task2_stdout.txt`, `task2_fl50.json` — pads, nets, positions, pairwise geometry
- `task2_crosscheck_esc.py`, `task2_crosscheck_esc.txt` — FL201 comparison on the ESC board

**Task 3**
- `task3_parity.py`, `task3_stdout.txt`, `task3_parity.json` — netlist-vs-board parity
- `task3_component_delta.py`, `.txt`, `task3_component_delta.json` — both-direction component delta