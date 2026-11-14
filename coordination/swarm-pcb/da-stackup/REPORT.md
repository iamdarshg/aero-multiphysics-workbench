# drone-arm rev_b — 4-layer stackup with GND under the RF corridor

**Item:** define an orderable stackup that puts GROUND under the RF corridor instead of 3V3,
and compute the resulting Z0 for the existing 0.35 mm traces.

**Board:** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb` (read-only; nothing written to the repo).
**Evidence dir:** `evidence/da-stackup/`. **Date:** 2026-11-14.

---

## 0. TL;DR

| | |
|---|---|
| Construction | JLCPCB 4-layer 1.6 mm, 1 oz, 7628-prepreg construction ("JLC04161H-7628" style) — the thickness set this board already declares |
| Layer roles after change | F.Cu signal / **In1 = solid GND** / **In2 = split 3V3 + 1V1** / B.Cu GND+signal |
| Z0 at 0.35 mm, h = 0.200 mm | **51.2 Ω** (38.5 dB return loss @ 915 MHz) |
| Width for exactly 50 Ω @ 0.200 mm | **0.365 mm** (+15 µm — inside etch tolerance, no change needed) |
| KiCad block | `stackup_block.sexp` (verified: KiCad 9 parses it, reports 1.600 mm, 4 copper) |
| Reroute | Outline survives untouched. **92.7 %** of the RF run gets a solid GND reference from the zone net swap alone; the remaining **7.5 mm** is voided by 3 nets (73 % of it `VDD_CC112`) that must move off In1 |

**The headline finding: this board's stackup geometry was never the RF defect.** The L1→In1
dielectric is already 0.200 mm, which is the spacing that puts the already-drawn 0.35 mm traces
at ~50 Ω. The defect is purely *plane assignment*: In1 is a 3V3 pour at priority 1 that
displaces the GND pour at priority 0, so the RF corridor's reference plane is a power net with
return-path holes in it. Fixing that is a net-name change, not a re-spin of the geometry.

---

## 1. Measured starting state

All numbers from `scripts/zone_geometry.py`, `scripts/filled_areas.py`,
`scripts/plane_vias.py`, `scripts/inner_layer_routing.py` (KiCad 9 `pcbnew`, read-only).

### 1.1 Zones (5 total)

| Layer | Net | Priority | Zone outlines | Filled polys | **Filled area (mm²)** |
|---|---|---|---|---|---|
| F.Cu | /GND | 0 | 1 | 14 | 12,188.6 |
| B.Cu | /GND | 0 | 1 | 4 | 12,728.8 |
| **In1.Cu** | **/3V3** | **1** | 1 | **3** | **12,164.1** |
| **In1.Cu** | **/GND** | **0** | 1 | **177** | **82.2** |
| In2.Cu | /1V1 | 1 | 1 | 2 | 256.0 |

Board area 14,036.0 mm² (140.15 × 100.15 outer bbox).

- The **12,164.1 mm²** filled area over **3 filled outlines** reproduces the brief's
  "12,164 mm², 3 outlines" **exactly** — method cross-validated.
- The In1 /GND pour is **82.2 mm² of slivers**. It is priority 0 under a priority-1 pour that
  spans the whole board, so it is fully displaced. **In1 has effectively zero GND copper today.**

### 1.2 RF corridor

RF signal = nets in the schematic groups `/915 MHz RF/` and `/GNSS/` at the 0.35 mm width
(`/RF_SCLK`, `/RF_nCS` are SPI and were excluded — see `scripts/zone_geometry.py` v2 note).

| | |
|---|---|
| F.Cu 0.35 mm RF segments | **68**, total **102.4 mm** |
| In2.Cu 0.35 mm RF segments | 2, total 1.8 mm (`/915 MHz RF/CC_LNA_N`) |
| Corridor bbox | x 83.0–135.0, y 15.0–68.0 → **52 × 53 mm** |
| Reference over the F.Cu RF run | **/3V3 = 102.4 mm (100.0 %)**, /GND = 0.0 mm, neither = 0.0 mm |

The brief's 88.86 % / 0 % pair: I confirm **0 % GND** independently. My 100 % /3V3 is a
*run-length* test against zone outlines with priority applied (3V3 wins everywhere it overlaps);
88.86 % is presumably an *area*-based test over filled copper. For reference, the /3V3 pour
covers 12,164.1 / 14,036.0 = **86.7 %** of the board bbox. The figures differ in method but all
say the same thing: **no GND under the RF run.**

---

## 2. Proposed stackup

### 2.1 Construction chosen

**JLCPCB 4-layer, 1.6 mm finished, 1 oz outer and inner, 7628-style prepreg — the
`JLC04161H-7628` construction family.**

Why this one, honestly: it is the construction this board *already sums to*. Copper 4 × 0.035 =
0.140, dielectric 0.200 + 1.040 + 0.200 = 1.440, mask 2 × 0.010 = 0.020 → **1.600 mm exactly**
(verified numerically, §4). Choosing anything else would force a new fab qualification for no
return-path benefit, and would move the 0.35 mm traces off 50 Ω (see §3).

### 2.2 Layer table

| # | Layer | Type | Thickness (mm) | Material | εr | tanδ | Cu weight |
|---|---|---|---|---|---|---|---|
| — | F.Mask | solder mask | 0.010 | — | — | — | — |
| 1 | **F.Cu** | copper — signal + RF corridor | **0.035** | Cu, ENIG | — | — | **1 oz** |
| 2 | dielectric 1 | **prepreg** (7628 ply) | **0.200** | FR4 | **4.20** | **0.020** | — |
| 3 | **In1.Cu** | copper — **SOLID GND** | **0.035** | Cu | — | — | **1 oz** |
| 4 | dielectric 2 | **core** | **1.040** | FR4 | **4.20** | **0.020** | — |
| 5 | **In2.Cu** | copper — **split /3V3 + /1V1** | **0.035** | Cu | — | — | **1 oz** |
| 6 | dielectric 3 | **prepreg** (7628 ply) | **0.200** | FR4 | **4.20** | **0.020** | — |
| 7 | **B.Cu** | copper — GND pour + signal | **0.035** | Cu | — | — | **1 oz** |
| — | B.Mask | solder mask | 0.010 | — | — | — | — |
| | **Total** | | **1.600** | | | | |

Copper is symmetric (all 1 oz) and the dielectric is symmetric about the core (0.200 / 1.040 /
0.200), so the panel is warp-balanced. **Do not** rebalance this — it is already correct.

The only change relative to the shipped board is the **net assigned to In1 and In2**. The
numbers in `stackup_block.sexp` are therefore numerically identical to the current block; the
value of the file is that it is the verified-good artefact to paste, and the plane assignment
that makes it mean something lives in §2.3.

### 2.3 Plane assignment (this is the actual change)

| Layer | Before | **After** |
|---|---|---|
| F.Cu | GND pour + signal + RF | unchanged (GND pour + signal + RF) |
| In1.Cu | **/3V3 (priority 1)** + dead /GND (priority 0) | **solid /GND, single pour, single priority** |
| In2.Cu | /1V1 (256 mm²) | **split: /3V3 bulk + /1V1 retained** |
| B.Cu | GND pour + signal | unchanged |

Zone operations (`scripts/` reproduces every count):

1. **In1 /3V3 zone → change net to /GND.** One zone, one outline (filled as 3 disjoint polys),
   12,164.1 mm² filled. This single edit converts the entire RF reference from power to ground.
2. **Delete the redundant In1 /GND zone** (82.2 mm² of priority-0 slivers). It contributes
   nothing and its 177 filled outlines will otherwise fight the new pour's fill order.
3. **Add /3V3 on In2.Cu**, keeping the existing /1V1 zone (714.3 mm² outline / 256.0 mm² filled,
   bbox x 45.5–74.1, y 36.5–61.5) and splitting In2 between them.
4. **Delete 1 via:** the single `/3V3` via spanning `F.Cu..In1.Cu` becomes a 3V3→GND short. The
   **10** `/3V3` vias that span `F.Cu..B.Cu` need **no change** — they pass through In2 and will
   pick up the new 3V3 pour there automatically.
5. **Move 2 RF segments off In2:** `/915 MHz RF/CC_LNA_N`, 0.44 mm + 1.40 mm, currently on
   In2.Cu. In2 stops being a reference plane, so these must go to F.Cu.

---

## 3. Z0 computation for 0.35 mm traces

### 3.1 Method and validation

- Solver: **scikit-rf 1.9.0 `MLine`**, `model='hammerstadjensen'` (Hammerstad–Jensen 1980
  quasi-static) with `disp='kirschningjansen'` dispersion. Run with
  `C:/Program Files/Python312/python.exe` — `scripts/z0_microstrip.py`.
- Inputs from the board: w = 0.35 mm, t = 0.035 mm, εr = 4.20, tanδ = 0.020
  (`main_rev_b.kicad_pcb:52,58,59`).
- **Independent cross-check** (`scripts/z0_crosscheck.py`, no library — hand-coded Hammerstad–
  Jensen 1980 + the 1975 thickness correction): agreement with skrf is **0.09–0.20 %** at every
  thickness. The numbers are trustworthy.

> Note: IPC-2141A was also evaluated and **rejected** — it returns 19.7 Ω at h = 0.09 mm and
> diverges 11.7–54 % from H&J across this geometry. It is not valid for w/h > 2 and must not be
> used for a 0.35 mm trace on a thin dielectric. Do not quote it.

> skrf gotcha for anyone re-running: in this install `skrf.media` (attribute) is shadowed by
> `skrf.media.media`, so `rf.media.MLine` raises `AttributeError`. Use
> `importlib.import_module("skrf.media").MLine`, and note `ep_eff` was renamed `ep_reff`.

### 3.2 Sweep — fabs offer 0.09 / 0.10 / 0.15 / 0.20 mm L1→In1

| h (mm) | Z0 @ 0.35 mm, 915 MHz | ε_eff | **W for exactly 50 Ω** | w/h for 50 Ω | RL @ 915 MHz | dZ0 / 10 µm width |
|---|---|---|---|---|---|---|
| **0.09** | **30.3 Ω** | 3.274 | **0.153 mm** | 1.704 | 12.2 dB | 0.60 Ω |
| **0.10** | **32.7 Ω** | 3.243 | **0.172 mm** | 1.724 | 13.6 dB | 0.63 Ω |
| **0.15** | **42.9 Ω** | 3.129 | **0.268 mm** | 1.789 | 22.4 dB | 0.74 Ω |
| **0.20** | **51.2 Ω** | 3.056 | **0.365 mm** | 1.826 | **38.5 dB** | 0.81 Ω |

**Answer: 0.20 mm is the only offered thickness that gives ~50 Ω with the existing 0.35 mm
traces — and 0.20 mm is what the board already has.** 51.2 Ω is +2.4 % from nominal, i.e.
38.5 dB return loss: ≈0.001 dB mismatch loss at 915 MHz, far below the insertion loss of the
matching network and the SAW filter. The exact 50 Ω width is 0.365 mm — 15 µm wider, well inside
JLC's ±20 µm etch tolerance on 1 oz copper, so **leave the traces at 0.35 mm**.

### 3.3 Thickness robustness

If the fab builds the catalogue 0.2104 mm single-7628 ply instead of the declared 0.200 mm:

| h (mm) | 0.180 | 0.190 | 0.200 | 0.2104 | 0.220 |
|---|---|---|---|---|---|
| Z0 (Ω) | 48.08 | 49.67 | 51.20 | 52.73 | 54.10 |
| Δ vs 0.200 | −6.1 % | −3.0 % | 0 | +3.0 % | +5.7 % |

Across the whole plausible build window Z0 stays inside **48–54 Ω**, i.e. ≥26 dB return loss.
The design does not need to be on a coupon to be safe.

### 3.4 Why not go thinner for a tighter RF field?

h = 0.10 mm would give better field containment and lower radiation, but it drops Z0 to 32.7 Ω
at the drawn width and forces every one of the 68 RF segments to be redrawn at 0.172 mm, plus a
re-tune of MATCH_A / MATCH_B / the SAW and PA matching networks. That is a re-design, not a
stackup fix, and it buys nothing for a 915 MHz FR4 design where 51.2 Ω is already fine. Keep it
in the back pocket for a rev C that is being re-laid out anyway.

---

## 4. KiCad stackup block — verified

**File: `evidence/da-stackup/stackup_block.sexp`** — paste inside `(setup ... )` of
`main_rev_b.kicad_pcb`, replacing the existing `(stackup ... )` block at
`main_rev_b.kicad_pcb:39–99`.

Verification (`scripts/verify_stackup.py`): the block was spliced into a **copy** of the board
under the evidence dir and reloaded with `pcbnew.LoadBoard`:

```json
{ "block_parses_in_kicad": true,
  "kicad_reported_finished_thickness_mm": 1.6,
  "kicad_reported_copper_layers": 4,
  "block_arithmetic_sum_mm": 1.6,
  "delta_mm": -0.0 }
```

Full record in `stackup_verify.json`. The spliced test board is `_verify_board.kicad_pcb`
(evidence dir only — the repo was never modified).

---

## 5. Re-route impact

### 5.1 Does the outline survive?

**Yes, completely.** 140 × 100 mm outline, mounting, connectors, and all 1.6 mm mechanical
constraints are untouched — the change is board-internal (zone nets + a handful of tracks). No
footprint moves are forced by the stackup.

### 5.2 How much of the RF run actually gets a clean reference?

This is the number that decides the cost. In1 today carries **1,390.1 mm** of routing, of which
**1,100.7 mm belongs to nets other than /GND and /3V3** (1,002.1 mm at 0.25 mm, 98.5 mm at
0.20 mm). Those tracks force the pour to void around them, so "solid GND" is not automatic.

For every point along the 102.4 mm F.Cu RF run, distance to the nearest foreign In1 track
centreline (`scripts/rf_reference_cleanliness.py`, radius 0.6 mm ≈ 3h):

| | mm | % |
|---|---|---|
| Clean GND reference after the net swap | **94.8** | **92.7 %** |
| Voided by a foreign In1 track | **7.5** | 7.3 % |

**92.7 % of the RF run is fixed by the zone net change alone.** The obstructed 7.5 mm, by which
RF net is affected:

| Net | obstructed | % clean |
|---|---|---|
| `/915 MHz RF/CC_LNA_N` | 1.7 mm | 49.9 % |
| `/GNSS/GNSS_RF_IN` | 2.0 mm | 81.5 % |
| `/915 MHz RF/CC_PA` | 2.0 mm | 61.9 % |
| `/915 MHz RF/CC_LNA_P` | 1.6 mm | 67.3 % |
| `/915 MHz RF/CC_PA_BIAS` | 0.1 mm | 97.9 % |

The critical nets are **already 100 % clean**: `/915 MHz RF/ANT_915` (15.4 mm),
`/GNSS/GNSS_RF_ANT` (17.9 mm), `/915 MHz RF/MATCH_A` (12.1 mm), `/MATCH_B` (7.8 mm),
`/RF_PA_OUT` (4.7 mm), `/SAW_PA` (3.9 mm), `/RF_TR_SW` (2.8 mm). The obstructed section is the
short CC1120/CC1190 pin-escape fan-out — the least electrically sensitive part of the run.

**Three nets cause all of it, dominated by one** (`obstructed_len_by_nearest_foreign_net_mm`
in `rf_reference_cleanliness.json`, measured over the full obstructed length — not a sample):

| Nearest foreign In1 net | obstructed RF run |
|---|---|
| `/915 MHz RF/VDD_CC112` (CC1120 supply rail, 12.3 mm on In1 in the corridor) | **5.48 mm** (73 %) |
| `/GNSS/GNSS_UART_RX_2V8` | 1.03 mm |
| `/GNSS/GNSS_RESET_OD` | 1.02 mm |

Move those three off In1 inside the corridor and the reference repair goes from 92.7 % to ~100 %.
Two of the three are GNSS control lines and are cheap to move.

### 5.3 Surgery list (ordered)

1. In1 /3V3 zone → net `/GND`; delete the In1 /GND sliver zone. **No trace moves.**
2. Re-pour. Expect DRC to flag the `/3V3` `F.Cu..In1.Cu` via as a short — delete it (§2.3 item 4).
3. Move `/915 MHz RF/VDD_CC112` (5.48 mm of obstruction), `/GNSS/GNSS_UART_RX_2V8` (1.03 mm) and
   `/GNSS/GNSS_RESET_OD` (1.02 mm) off In1 inside the corridor → recovers the last 7.5 mm of RF
   reference.
4. Add `/3V3` pour on In2, split against the existing `/1V1` pour.
5. Move `/915 MHz RF/CC_LNA_N`'s 1.84 mm off In2.Cu to F.Cu.
6. B.Cu rule: **do not cross the In2 3V3/1V1 split boundary** on B.Cu. B.Cu's reference changes
   from /1V1 (retained, quiet) to /3V3 (switching) over part of the board — the 4 `/1V1` vias and
   the 162 `/GND` vias are unaffected, but any B.Cu trace that today relies on a continuous /1V1
   reference must be checked. This is the one real regression of the change and it is a routing
   rule, not a stackup cost.

Estimated effort: **~15 mm of track to move plus one via deleted and one pour added.** No re-route.

---

## 6. Provenance and honest limitations

**Verified by command/file** (every number above):
`zone_geometry.json`, `filled_areas.json`, `inner_layer_routing.json`, `plane_vias.json`,
`corridor_obstruction.json`, `rf_reference_cleanliness.json`, `z0_results.json`,
`z0_crosscheck.json`, `h_bracket.json`, `stackup_verify.json` — regenerated by the ten scripts
in `scripts/`.

**UNVERIFIED — needs a real fab quote:**

1. **The exact JLCPCB catalogue part number and its published dielectric thicknesses.** The JLC
   impedance-calculator page is JavaScript-rendered and returns no stackup table to a plain
   fetch, and `web_search` is unavailable in this session (provider conflict). So
   "JLC04161H-7628" is named as the construction *family* this board's own thicknesses match —
   I could **not** confirm that string, or JLC's published 7628 ply thickness, against JLC's
   stackup table. Confirm with the fab before release.
2. **Whether JLC builds the L1–L2 ply at 0.200 mm or 0.2104 mm.** This board declares 0.200; the
   common catalogue nominal for a single 7628 ply is 0.2104. The difference is +3.0 % on Z0
   (52.7 Ω, §3.3) — acceptable, but it must be pinned in the fab note.
3. **Z0 is analytical, not measured.** Hammerstad–Jensen + Kirschning–Jansen, cross-checked to
   0.2 % by a second independent H&J implementation. **No field solver, no TDR coupon, no
   measured S-parameters exist.** The 38.5 dB return loss is a geometry-only figure and excludes
   connector, matching-network, and SAW-filter mismatch.
4. **No DRC/ERC was run on the modified board.** The change was not applied to the repo (read-only
   mandate) and the zone surgery in §5.3 is specified, not executed.
5. **The "88.86 % / 0 %" in the brief was reproduced as 12,164.1 mm² / 3 outlines (exact) and
   0 % GND (independent confirmation), but my 100 % /3V3 differs in method** — run-length vs
   area. Both support the same conclusion; the exact percentage is method-dependent.

---

## 7. Files

| File | What |
|---|---|
| `stackup_block.sexp` | **The deliverable** — paste-ready KiCad 9 stackup block, verified to parse and sum to 1.600 mm |
| `REPORT.md` | this report |
| `scripts/z0_microstrip.py` | Z0 sweep, skrf MLine (H&J) |
| `scripts/z0_crosscheck.py` | independent hand-coded H&J + IPC-2141A cross-check |
| `scripts/zone_geometry.py` | zones, RF corridor, reference coverage |
| `scripts/filled_areas.py` | true filled copper areas (reproduces 12,164.1 mm²) |
| `scripts/inner_layer_routing.py` | per-net routing on In1/In2 |
| `scripts/plane_vias.py` | via/pad inventory on the plane layers |
| `scripts/corridor_obstruction.py` | tracks/vias/pads inside the RF corridor |
| `scripts/rf_reference_cleanliness.py` | 92.7 % clean-reference measurement |
| `scripts/verify_stackup.py` | splices the block into a board copy; KiCad round-trip check |
| `*.json` | raw results backing every figure |
| `_verify_board.kicad_pcb` | throwaway spliced board used for the round-trip check |