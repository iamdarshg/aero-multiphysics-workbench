# ESC header mate fix — single-sided board-to-board mating

Status: **FINAL** — one task, answered. Short answer in §0.

Assignment: make the control board mate onto the power board with **both boards single-sided**
(0 components on B.Cu). Measured starting defect: 60 odd pins coincide, 60 even pins mirror 5.08 mm.

Host: KiCad 9.0.7 (`C:/Program Files/KiCad/9.0/bin/`), `python.exe` = KiCad's bundled 3.11 with
`pcbnew`; DRC = `kicad-cli.exe pcb drc --severity-all --units mm`.
All work on COPIES in this directory. Nothing written into a repo, nothing committed.

## 0. THE ANSWER

| question | answer |
|---|---|
| cause | **not the connector.** The header and the socket are a correct stock male/female pair and the socket's numbering is *already* mirrored in the footprint. The boards do not mate because the **power board's single face is the sink face**: its 36 FETs and its 3 header strips are both on F.Cu, so the posts point at the heatsink instead of at the control board. |
| the pair | **unchanged** — `TSW-120-15-G-D` (`PinHeader_2x20_P2.54mm_Vertical`) + `SSW-120-01-G-D` (`PinSocket_2x20_P2.54mm_Vertical`). Only the **header's side** and the **post length** change. |
| orientation | header on the power board's **B.Cu** (posts up, at the control board); socket stays on the control board's **F.Cu**, the control board mounted **F.Cu-down** so its component face looks into the 10.00 mm gap. x/y transform = **identity** (the header's B-side mirror cancels the socket's stock mirror). |
| 120-pin mapping | **60/120 as delivered; 120/120 after the header flip, max residual 0.000000 mm.** |
| sink clearance | moulding-to-sink **1.500 → −1.040 mm** (the bank mirrors 2.54 mm left); the tail-to-sink-face z clearance is unchanged at **1.41 mm**. Trim the sink 1.04 mm, or accept the moulding overhang (it is 4.20 mm above the sink's face). |
| the 120 PTH inside the sink rect | 6 × `Conn_02x12_Pin` (144 PTH pads, **all netless**, inherited from the single-board design); the count is 120 only because the rect's left edge clips J1/J4's odd column. Removed by **deletion** — they carry nothing. |
| DRC set diff | power **+{} / −{}** (528: 499 clearance + 29 silk) · control **+{} / −{}** (37). The mate defect costs **0 DRC**. On the fixed copy: **+3 shorting, +8 mask-bridge** (528 → 539) where the mirrored bank meets `BAR2` / the FET gate pads; unconnected unchanged at 187. |
| **MATES SINGLE-SIDED** | **NO.** It mates 120/120 with the **control board 100 % single-sided**, but the 120 header pins must sit on the **power board's B.Cu**. "0 components on B.Cu on both boards" is unsatisfiable with the sink on the power board's component face. |

The price is exactly **3 footprints / 120 pins on the power board's B side** — nothing on the control
board's B side, and no change to the control board at all.

---

## 1. CAUSE, from the part definitions and the placements

### 1.1 What is actually fitted (read from both files)

| | power board | control board |
|---|---|---|
| refs | `J_H1`, `J_H2`, `J_H3` | `J_H1`, `J_H2`, `J_H3` |
| Value | `TSW-120-15-G-D` (Samtec TSW, male pin strip) | `SSW-120-01-G-D` (Samtec SSW, female socket strip) |
| footprint | `PinHeader_2x20_P2.54mm_Vertical` | `PinSocket_2x20_P2.54mm_Vertical` |
| origin | (133.27 / 139.36 / 145.45, 21.27), rot 0° | same three, rot 0° |
| side | **F.Cu** | **F.Cu** |
| pads | 40 thru-hole each, Ø1.0 / 1.7 pad | 40 thru-hole each, Ø1.0 / 1.7 pad |

So the pair is already **male + female**: hypothesis "both connectors are the same gender" is **ruled out**.

### 1.2 The footprint geometry is the stock KiCad geometry, unmodified

Read byte-for-byte from the installed library:

```
C:\Program Files\KiCad\9.0\share\kicad\footprints\Connector_PinHeader_2.54mm.pretty\
    PinHeader_2x20_P2.54mm_Vertical.kicad_mod :  pad "1" (0 0)    pad "2" ( 2.54 0)   pad "3" (0 2.54)
C:\Program Files\KiCad\9.0\share\kicad\footprints\Connector_PinSocket_2.54mm.pretty\
    PinSocket_2x20_P2.54mm_Vertical.kicad_mod :  pad "1" (0 0)    pad "2" (-2.54 0)   pad "3" (0 2.54)
```

and the boards reproduce exactly that (`01_probe_raw.json`, `02_local_pads.json`): on both boards pin 1
is at the footprint origin, the odd column on x = 0, the even column at **+2.54 on the header** and
**−2.54 on the socket**.

So: the socket's pin numbering **is mirrored in the footprint** — the property the brief asks for is
already there. It is not a hand-edited or wrongly-mirrored part, and "the socket was placed without
mirroring" is **ruled out**. Both parts are vertical through-hole 2x20, so "right-angle vs vertical" is
**ruled out** too.

### 1.3 The 5.08 mm even-pin offset is a *frame* artefact, and no pose mates the files as placed

`05_motion_sweep.py` applies all 8 axis-aligned rigid motions (4 with F.Cu up, 4 with F.Cu down) to the
control board, solves the translation from pin 1 of J_H1, and counts the pins that land within 1 µm:

| motion | coincident | max residual |
|---|---:|---:|
| **F.Cu up, 0° (the pose the comparison used)** | **60/120** | **5.080000 mm** |
| F.Cu up, 90° | 1/120 | 73.878175 |
| F.Cu up, 180° | 2/120 | 99.546572 |
| F.Cu up, 270° | 2/120 | 70.390056 |
| F.Cu down, mirror + 0° | 40/120 | 24.360000 |
| F.Cu down, mirror + 90° | 1/120 | 68.344410 |
| F.Cu down, mirror + 180° | 3/120 | 96.653592 |
| F.Cu down, mirror + 270° | 1/120 | 85.550514 |

The 60/120 with a 5.080 mm residual on the even pins **reproduces the reported symptom exactly**, and
that is the *maximum* over every rigid motion. **There is no pose in which these two files mate.** The
fault is therefore in how the two boards are placed relative to each other, not in the pads.

### 1.4 The reason: a vertical pair needs the two component faces to face each other — and the power board has only one usable face

A vertical header's posts point along its board's outward normal at the mounting face; a vertical
socket's cavity points along its board's outward normal too. To engage, those two normals must be
**antiparallel**, i.e. the boards' component faces must face each other. On the delivered boards both
component faces point the same way (both drawn F.Cu), which is a coplanar group, not a stack.

That alone is fixable by turning one board over. What makes it *unfixable in one move* is the sink:

* All **173** footprints on the power board are on **F.Cu** (1219 F-only SMD pads, 0 B-only) — the 36
  `IPTC014N10NM5` FETs **and** the 3 header strips.
* The FETs must sit on the heatsink (that is the whole thermal design: 2.60 mm component-face height,
  0.25 mm TIM, `esc-sink-clearance` z ladder), so the **sink is on the F.Cu side**.
* The header must point **away** from the sink, at the control board.

One face cannot do both jobs. The delivered file puts the posts on the sink side, so the control board
would have to be inside the heatsink. The stack's own model says the opposite: in
`esc-sink-clearance/03_numbers.json` the header is modelled with **post tip z = +19.95 (up)** and
**tail tip z = +1.41, i.e. 1.41 mm above the sink's contact face (down)** — a header mounted on the side
*away* from the sink. Same instruction appears in `esc-stack-v2` ("confirm the F.Cu-down mounting") and
`esc-pinsplit-v2` ("the FETs flipped to B.Cu for top-side cooling"). **Neither was applied: 0 footprints
on B.Cu on either board.**

So the cause, stated once: *the header and the FETs share one face of the power board; the stack needs
them on opposite faces. The pad geometry was never wrong.*

---

## 2. THE FIX

| item | value |
|---|---|
| header part | **`TSW-120-15-G-D`** — unchanged |
| header footprint | **`PinHeader_2x20_P2.54mm_Vertical`** — unchanged geometry, **moved to B.Cu** |
| socket part | **`SSW-120-01-G-D`** — unchanged |
| socket footprint | **`PinSocket_2x20_P2.54mm_Vertical`** — unchanged, stays on the control board's **F.Cu** |
| power board orientation | F.Cu **down** (toward the sink) — headers on the up side = **B.Cu** |
| control board orientation | F.Cu **down**, i.e. turned over in the assembly; all 148 footprints stay on F.Cu |
| x/y transform | **identity** — the two boards share the same x/y frame |
| z | control board's component face **14.20 mm** above the power board's component face (10.00 mm gap) |
| post length | **must change**: 5.05 – 6.66 mm above the insulator (a shorter TSW lead style), not 13.21 |

**Why identity works.** Flipping the header to B.Cu mirrors its pads *in its own frame* — pin 2 goes from
+2.54 to **−2.54** (`12_matefix_verify.json`: J_H1 pad 2 `(135.81, 21.27) → (130.73, 21.27)`, pins 1 and 3
unmoved) — and the stock socket already draws pin 2 at **−2.54**. The two mirrors cancel, so with the
boards in the same x/y frame **pin k meets pin k** and the row order is preserved. The move is also the
only one that satisfies the sink: the header's tails then point at the sink (1.41 mm above its contact
face, as the stack requires) while its posts point at the control board.

**Why the post must shorten.** With the control board's F.Cu down at +14.20 and a 4.95 mm socket body,
the cavity entry is at +9.25. The TSW-15 post tip is at +19.95, i.e. **5.75 mm past the control board's
near face** and 10.70 mm past the cavity entry — it would pass straight through the socket and the board.
The tip must land inside the cavity: **+11.79 … +13.40**, i.e. a post of **5.05 – 6.66 mm** above the
insulator (insertion 2.54 – 4.15 mm). Alternatively keep the 13.21 post and raise the control board to
+16.74…+18.35, which grows the 55.80 mm envelope by **+2.54 mm**.

**Why not the other B.Cu option** (moving the *sockets* to the control board's B.Cu, which the previous
wave recommended): it does make the pads coincide, but it needs the power board's F.Cu to face **up**
(posts up) — and the power board's F.Cu is the sink face. With the FETs on the sink, the posts then point
into the heatsink. It also leaves the control board's component side looking away from the power board.
The header-side flip is the only version that works with the sink where it is.

---

## 3. 120-PIN PROGRAMMATIC MAPPING

`12_matefix.py` writes `esc_power_board_matefixB.kicad_pcb` (the three headers flipped to B.Cu, nothing
else touched) and compares every pad against the **untouched** control board.

**Transform used:** `X_ctrl = X_power`, `Y_ctrl = Y_power`, `Z_ctrl = Z_power + 14.20` — a pure z
translation. Boards co-oriented (both F.Cu normals pointing the same way), the header on the power
board's B side, the socket on the control board's F side. No mirror, no rotation, no offset.

| | coincident (≤1 µm) | max residual |
|---|---:|---:|
| delivered boards (headers on F.Cu) | **60 / 120** | 5.080000 mm |
| after the header flip | **120 / 120** | **0.000000000 mm** |

Per-pin rows: `12_matefix_verify.json` (`pin_rows`, first 8 shown) and `05_motion_sweep.json` for the
sweep. Nothing was moved on the control board, so its pad coordinates are the ones already placed.

---

## 4. SINK CLEARANCE AFTER THE CHANGE

Sink plan (from `esc-sink-clearance/03_numbers.json`): x **5.5 – 130.5**, y 7.0 – 81.0.
Power-board plate: x −0.05 – **151.82** (measured Edge.Cuts, `03_outline.json`).

| basis | delivered (F.Cu) | after the flip (B.Cu) | Δ |
|---|---|---|---|
| moulding (pads ± 1.27), to sink / edge | **+1.500 / +2.560** | **−1.040 / +5.100** | −2.54 |
| courtyard, to sink / edge | +0.975 / +2.025 | −1.575 / +4.575 | −2.55 |
| pad copper, to sink / edge | +2.770 / +3.830 | +0.230 / +6.370 | −2.54 |
| header tail tip, above the sink's contact face (z) | **1.41 mm** | **1.41 mm** | 0 |

The 1.50 mm **body-to-sink** figure is confirmed on the delivered board (the moulding starts at
x = 132.00, the sink ends at 130.50). Note the earlier `bank_x = 132.00…150.27` over-counted one
column gap: the three columns are 2 × 6.09 + 5.08 = **17.26 mm** wide, not 18.27, so the edge figure is
**2.56 mm, not 1.50** — a slightly better number than was claimed, on the same basis.

**After the change the bank mirrors 2.54 mm to −x**, so the moulding ends **1.04 mm past the sink's edge
line** (courtyard 1.575 mm). This is a plan-view keep-out incursion, not a metal clash: the moulding sits
4.20 mm above the sink's contact face and the tails still end 1.41 mm above it. Two ways to restore 1.50:

1. **trim the sink 1.04 mm in x** (125.0 → 123.96 mm; −0.83 % of the sink's area, well inside the
   20 % the thermal sweep shows is free), or
2. shift the bank +3.81 mm — **not available**: the control board's sockets must shift with it
   (pin 1 ↔ pin 1) and its rightmost socket courtyard would then reach x = 153.61, 2.46 mm past its own
   151.15 outline and outside the 151.82 power-board plate.

The `05_sink_clearance.png` section is unaffected in z (the bank does not move in y).

---

## 5. THE 120 PRE-EXISTING PTH TAILS INSIDE THE SINK RECTANGLE

Measured (`03_pth_sink.json`): 264 thru-hole pads on the power board = 120 header + 144 in six
`Conn_02x12_Pin` footprints at (4.1, 10.3), (47.2, 10.3), (90.3, 10.3), (4.1, 50.3), (47.2, 50.3),
(90.3, 50.3) — 2×12, Ø1.0 drill / 1.7 pad, body 5.08 × 29.64 × 2.54 mm.

* **What they are:** the single-board design's six per-cell 2×12 headers, inherited byte-identically
  (`baseline_pwr_src.kicad_pcb` has the same six at the same coordinates). **All 144 pads carry no net**
  (`GetNetname() == ""`), so nothing connects to them any more.
* **Why exactly 120:** the sink rect starts at x = 5.5, which cuts J1 and J4 in half — their odd column
  (x = 4.1) is outside, their even column (x = 6.64) inside. 12 + 12 + 24 + 24 + 24 + 24 = **120 of 144**.
  The "120" is a rectangle artefact, not a connector count.
* **Do they block the sink?** No metal clash. The holes and their copper are inside the 1.60 mm board;
  at most the solder side protrudes 1.19 mm into a 2.60 mm gap (1.41 mm clear). The **moulding** is on the
  sink-facing side and is 2.54 mm tall against a 2.60 mm gap — **0.06 mm of margin, no margin at all** —
  and it sits in the two 7.8 mm inter-block corridors (x 43.58–51.38, 86.68–94.48) that carry the
  Ø3.3 sink clamp screws. `esc-stack-v2` measured this body as clashing by 0.19 mm on its own datum.
* **What removes them:** **deletion**. They are vestigial, carry zero nets, and deleting them is what
  frees the two clamp corridors (`esc-stack-v2` §"delete J1–J6"). A shorter connector, a sink cutout or
  an edge move are all unnecessary — there is nothing left to connect.
  Nothing about the mate fix touches them; after the header flip the bank is at x 130.7–145.5 and does
  not reach them.

---

## 6. DRC

Run in a companion-complete scratch directory (`drc/<tag>/`, carrying `.kicad_pro`, `.kicad_dru`,
`.kicad_prl`), `--severity-all --units mm`, JSON read from disk — never from stdout.

| board | violations | breakdown | unconnected (listed) | set diff vs stored baseline |
|---|---:|---|---:|---|
| power (delivered, re-run) | **528** | 499 clearance (error) + 29 silk_over_copper (warning) | 187 | **+{} / −{}** |
| control (delivered, re-run) | **37** | 10 clearance, 2 courtyards_overlap, 4 solder_mask_bridge, 7 silk_edge_clearance, 5 silk_over_copper, 9 silk_overlap | 41 | **+{} / −{}** |
| power, headers on B.Cu | *see `14_drc_fixed.json`* | — | — | *see below* |

The two delivered boards reproduce the stored baselines bit-for-bit, so the mate defect costs **zero
DRC**, and the instrument is faithful (an identical run is the determinism check).

**On the 499:** here 499 is the **clearance** count, not the unconnected list cap — the unconnected
lists are 187 and 41, neither at a round cap. The cap warning does not apply to this board pair.

### DRC on the fixed copy (`14_drc_fixed.json`, `15_drc_detail.py`)

| | violations | set diff vs the delivered board | unconnected |
|---|---:|---|---:|
| power, headers flipped to B.Cu **in place** | **539** | **+{shorting_items 3, solder_mask_bridge 8}, −{}** | 187 (unchanged) |

All 11 new items are the same thing: the flip mirrors the bank **2.54 mm toward the FET field**, so
`J_H1`'s even column lands at x = 130.73 where the delivered clearance to the FET pads was 1.92 mm
(`esc-sink-clearance`) — it becomes **−0.62 mm**. Concretely:

* 3 × `shorting_items`, all `J_H1` pads 18 / 20 / 22 (SWCLK, DGND, UART_RX) against **`BAR2` pad 1
  (BATN)** — a real copper land, so these are true shorts.
* 8 × `solder_mask_bridge`, the same three plus `J_H1` pads 10 / 12 / 28 / 30 / 40 against the gate pads
  of **`Q3CL`, `Q6CL`, `Q6CH`** (net M3_GCL / M6_GCL / M6_GCH).

The flip is **net-identical** (pin k keeps its own net and its own row; only the even column's hole
positions move), so the wire list is untouched — the 120-pin map is preserved. The cost is purely
geometric and it is bounded: clearing it needs the bank to move **≥ 2.2 mm back toward +x**, and since
the control board's sockets must follow (pin 1 ↔ pin 1) its rightmost socket courtyard would then reach
≈ 152.0 mm, **0.85 mm past its own 151.15 outline** — i.e. the control board grows ~1–2.5 mm, or the
`BAR2` / FET-field edge pads give up 2.54 mm. Either is a placement edit, not a connector decision.

---

## 7. VERDICT

**Do the boards now mate with both single-sided? NO.**

* They mate **120/120** (residual 0.000000 mm) the moment the three headers move to the power board's
  **B.Cu** — and the **control board stays 100 % single-sided** (148/148 footprints on F.Cu) with no
  change to any of its geometry.
* But the 120 header pins then sit on the **power board's B.Cu**, i.e. **3 footprints on B.Cu**. The
  brief's "0 components on B.Cu on both boards" cannot hold for the power board: its F.Cu face is spent
  on the FETs, which must sit on the heatsink.
* Completing the mate also needs three things that are not footprint geometry: a **post of 5.05–6.66 mm**
  (the TSW-15's 13.21 mm post is 10.70 mm too long for the 10.00 mm gap), a **1.04 mm sink trim** (or
  acceptance of a 1.04 mm moulding overhang, 4.20 mm above the sink's face), and **n~2.2 mm of bank
  shift** to clear the 11 new DRC items at the `BAR2` / FET-field edge (which the control board must
  follow, growing it ~1–2.5 mm).

The connector pair was never the defect and needs no substitution. Everything else in the split's
current state — 528 / 37 DRC, the sink's 1.50 mm, the 120-pin map's net assignment — is untouched.

## 8. Provenance

| number | instrument |
|---|---|
| part identity, sides, pad coordinates | `pcbnew` read of both files (`01_probe.py`, `02_local_pads.py`) |
| stock footprint pad offsets | direct read of the installed `Connector_Pin*.pretty` files |
| 8-motion coincidence sweep | `05_motion_sweep.py` (own rigid-motion enumerator, 1 µm threshold) |
| 60 → 120 coincidence after the flip | `12_matefix.py`, on a saved copy `esc_power_board_matefixB.kicad_pcb` |
| courtyards / sink gaps | `08_sink_z_mapping.py`, `13_clearance_fixed.py` (F_CrtYd / B_CrtYd bounding boxes) |
| 120 PTH pads in the sink rect | `03_outline_pth.py` (PTH attribute + point-in-rect) |
| DRC | `kicad-cli 9.0.7` JSON, `07_drc_run.py` / `14_drc_fixed.py`; set diff by (type, severity) |
| z budget | **arithmetic** on two carried inputs: the stack z ladder (`esc-sink-clearance/03_numbers.json`) and the Samtec lead lengths (TSW 2.54 / 13.21 / 2.79, SSW 4.95 / 2.64, carried from `esc-stack-v2` §3a). No datasheet re-fetch this wave — flagged as CARRIED. |

## 9. Files

```
01_probe.py / 01_probe_raw.json          footprint + pad dump, both boards
02_local_pads.py / 02_local_pads.json    header-vs-socket local frame, the 5.08 mm even-pin delta
03_outline_pth.py / 03_outline.json      plate outlines; 03_pth_sink.json the 120 PTH pads
04_j_connectors.py / 05_motion_sweep.py  8-motion sweep; 05_motion_sweep.json
06_control_occ.py / 06_control_occ.json  control-board occupancy (if the bank ever had to move)
08_sink_z_mapping.py / 08_sink_z_mapping.json   sink gaps, z budget, virtual mate
09_drc_setdiff.py / 09_drc_setdiff.json  delivered-vs-baseline set diff
10_face_check.py / 11_baseline_face.py   face census, baseline comparison
12_matefix.py / 12_matefix_verify.json   THE FIX: flip + 120/120 proof
13_clearance_fixed.py / 14_drc_fixed.py / 14_drc_fixed.json
esc_power_board_matefixB.kicad_pcb       the fixed power-board copy (headers on B.Cu)
drc/                                     DRC scratch runs with companions
```
