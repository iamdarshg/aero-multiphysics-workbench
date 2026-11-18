# ESC corrections — post, sink, 144 netless pads, 11 new DRC items

Status: **FINAL.** One task, answered. Both boards are geometrically clean of every item this task
names; the only open number is the power board's clearance **total**, which this CLI cannot report
(§0.1) and which is not a defect count.

Input: `evidence/esc-header-mate-fix/esc_power_board_matefixB.kicad_pcb` + its REPORT.md,
`evidence/esc-split-layout/esc_control_board.kicad_pcb`.
Output: this directory — `esc_power_board_final.kicad_pcb`, `esc_control_board_final.kicad_pcb`,
`11_section.png/.svg`, `fab/{power,control}/`, scripts `01..17_*.py` with their JSON.
All work on COPIES. Nothing written into a repo; nothing committed.

Host: KiCad 9.0.7 (`C:/Program Files/KiCad/9.0/bin/`), DRC = `kicad-cli.exe pcb drc --severity-all
--units mm --format json`, geometry = bundled `python.exe` with `pcbnew`, drawing = Python 3.12 +
matplotlib.

> `REPORT_draft1.md` is the interrupted unit's draft. Every number was re-run. Three of its claims are
> corrected here: the "rules are not loaded" inference (§0.1), the trim-uncovered formula (§2.2), and
> the "bank cannot move past +1.27 mm" conclusion (§2.3/§4.2). Where a number is carried, it says
> CARRIED.

## 0. THE ANSWER

| question | answer |
|---|---|
| **the post** | **Samtec `TSW-120-07-G-D`** — post **.230 in = 5.842 mm**, **OAL .430 in = 10.922 mm**, tail .200 in = 5.080 mm. Inside the required 5.05–6.66 mm band. Replaces `TSW-120-15-G-D` (13.21 mm post, 10.70 mm too long). Retagged on all three headers. |
| **post tip** | z **+12.58** = 3.33 mm into the socket, **1.62 mm** clear of the control board's F.Cu (+14.20). No bottoming, no through-strike. |
| **stack height** | **49.80 mm as built** (fin tips z −34.00 … control B.Cu +15.80) against the **55.80 mm** envelope → **6.00 mm headroom**. The control board is F.Cu-down, so its 6.00 mm parts sit inside the 10.00 mm gap, not above it. |
| **the sink trim** | **0.00 mm — not applied.** The 1.04 mm trim is **not FET-safe**: it uncovers **6.16 mm² of drain land** (9.49 mm² of all FET copper) on Q3CH/Q3CL/Q6CH/Q6CL. The correction is a **+2.54 mm bank shift**, which restores the design intent **1.500 mm** exactly with **no** sink cut. Sink stays **125.00 × 74.00 mm**. |
| **sink clearance** | **1.500 mm**, measured: moulding at 132.00, sink edge 130.50, at the adopted +2.54 mm bank position. (The flip at the old bank x gave −1.040; the shift, not a trim, is the fix.) |
| **Tj at 80 A** | **123.15 °C** (T_sink 77.57 °C, all 36 devices). **PAD-LIMITED**: 45.6 K junction-to-sink, **40.8 K of it the Sil-Pad** (3.43 K/W × 11.9 W). A 1.04 trim would be 124.29 °C on four devices and lose 6.16 mm² of drain land; no trim keeps 123.15. |
| **144 netless pads** | **deleted** — 6 × `Conn_02x12_Pin` (J1…J6), 144 PTH pads, all `GetNetname()==""`. PTH 264 → **120**; **0** PTH inside the sink rectangle. |
| **the 11 DRC items** | 3 `shorting_items` + 8 `solder_mask_bridge`, all `J_H1` against **BAR2 pad 1 [BATN]** and the gate pads of **Q3CL / Q6CL / Q6CH**. Cleared by shifting the bank **+2.54 mm** in x on **both** boards (measured minimum 0.80 mm). |
| **set diff** | power **+{} / −{shorting 3, mask 8}** on the named items; plus **−1 silk** (U11's ref over a deleted J1…J6 pad). The raw list also shows a +1/−1 `clearance` pair, which is a **cap-boundary renumbering of the same Q6BL pair**, not a new defect (§4.3). Control **+{} / −{}** → 37. |
| **final DRC** | power **527 listed** = 499 `clearance` (**CAP**, §0.1) + 28 `silk_over_copper`; unconnected **187**. Control **37** (10 clearance, uncapped) + **41** unconnected. |
| **B.Cu components** | power **3** — `J_H1`, `J_H2`, `J_H3` (the headers); 0 B.Cu-only pads. Control **0** — 148/148 footprints on F.Cu. |
| **SurfaceFinish** | both job files: **`"Finish": "ENIG"`** — `fab/power/esc_power_board_final-job.gbrjob` (9 files), `fab/control/esc_control_board_final-job.gbrjob` (7 files). KiCad names this field `Finish`; it is the Ucamco SurfaceFinish field. |
| **mate** | **120/120** within 1 µm, max residual **0.000000000 mm**, 0 net mismatches, on the shipped pair. |

### 0.1 The 499 line is a LIST CAP, and the rules DO load — this corrects the draft

The draft claimed `kicad-cli` never loaded the `.kicad_pro`/`.kicad_dru` because a 40 mm probe rule
did not change the count. **That inference is wrong.** 499 is a per-type **list cap** (500 − 1), and
the clearance list was already full, so a stricter rule could not add visible items.

Measured this run (`15_rule_gate/`, raw JSON kept). The baseline row was run on the +1.27 build;
the adopted +2.54 build's first DRC is also 499/527, so the cap result is build-independent:

| experiment | clearance items | total | reading |
|---|---:|---:|---|
| final power (+1.27 build) + its `.kicad_pro` + `.kicad_dru` | 499 | 527 | baseline |
| same board, **no companions** | 114 | 142 | rules read as zero ⇒ only actual overlaps |
| invalid `.kicad_dru`, no `.kicad_pro` | 114 | 142 | invalid rule file ignored, as expected |
| empty `.kicad_dru` `(version 1)` | 114 | 142 | no rule ⇒ zero-clearance run |
| **`hole_size (min 5mm)` on PTH pads** | 499 | **647** | **+120 `drill_out_of_range` ⇒ custom rules ARE evaluated** |
| `clearance (min 5mm)`, pad–pad | **499** | 527 | **cap, not the rule** |
| clearance 0.20 / 0.24 / 0.25 / 0.26 / 0.30 / 0.50 / 1.00 / 5.00 mm | **499 every time** | 527 | value cannot change a full list |
| **control board**, clearance 5 mm | **499** | 526 | the cap is per-type, not board-specific |

So: the `.kicad_dru` and `.kicad_pro` **are** loaded; the 499 is a **floor**, not a measurement. The
power board's true clearance count is **≥499** and is not quotable from this tool. The 11 target items
are `shorting_items`/`solder_mask_bridge`, **outside** the cap, so their 3→0 and 8→0 are complete
measurements. Set diffs are used everywhere below, per the brief. The control board's 37 is below the
cap and is a true total.

## 1. THE POST

### 1.1 The requirement (CARRIED from `esc-header-mate-fix` §2)

Control board F.Cu at z +14.20, 4.95 mm socket body (cavity entry z +9.25), 2.54–4.15 mm usable
insertion ⇒ the post tip must land in **z +11.79 … +13.40**, i.e. a post of **5.05 – 6.66 mm** above
the insulator. The specified TSW-15's 13.21 mm post puts its tip at +19.95, 10.70 mm past the cavity
entry.

### 1.2 The part

| | value |
|---|---|
| part number | **`TSW-120-07-G-D`** (Samtec TSW, .025 in square post, 2×20, 2.54 mm pitch, 10 µin Au) |
| lead style | **07** |
| post (above insulator) | **.230 in = 5.842 mm** |
| OAL | **.430 in = 10.922 mm** |
| tail (OAL − post) | .200 in = **5.080 mm** |
| fits 5.05–6.66? | **yes** — 0.792 mm above the floor, 0.818 mm below the ceiling |

Sources, retrieved **2026-11-17**:

* product page <https://www.samtec.com/products/tsw-120-07-g-d> — the page title itself carries
  *".100in/2.54mm Through Hole Header, 40 Pin, 2 Row, 10µin Gold/Flash, **.230in Post, .430in OAL**"*;
* series print <https://suddendocs.samtec.com/prints/tsw-xxx-xx-xxx-x-xx-xxx-mkt.pdf>;
* spec sheet <https://suddendocs.samtec.com/productspecs/tsw-sxx.pdf> (linked from the product page).

Lead-style neighbours on the same series page, same retrieval:

| style | post | OAL | verdict |
|---|---|---|---|
| 06 | .105 in = 2.667 mm | .300 in | rejected — tip only reaches z +9.41, 0.16 mm into a 4.95 mm cavity |
| **07** | **.230 in = 5.842 mm** | **.430 in** | **chosen** |
| 15 (as specified) | 13.21 mm | 16.00 mm | rejected — 10.70 mm past the cavity entry |

### 1.3 The stack, re-derived

| | value |
|---|---|
| insulator | z +4.20 → +6.74 (2.54) |
| post | +6.74 → **+12.58** (5.842) |
| insertion into the socket | **3.33 mm** (cavity entry +9.25) |
| tip to control F.Cu | **1.62 mm** (+14.20) |
| tail | +4.20 → **−0.88** (5.080; 3.48 mm below F.Cu) |
| tail copper in plan | starts x **132.95** (even column 133.27 − Ø0.635/2), **2.45 mm** clear of the 130.50 sink edge; the sink is not under the bank, so the −0.88 tail is not a clash |
| solder access | the whole bank is outside the sink footprint; F-side joints are reachable before the sink is fitted |

### 1.4 Stack height vs the 55.80 mm envelope

| z | item | thk |
|---|---|---|
| −34.00 | fin tips, 16 fins | 30.00 |
| −4.00 | base plate, machined contact face | 4.00 |
| 0.00 | Sil-Pad 2000 0.010 in | 0.25 |
| +0.25 | FET | 2.35 |
| +2.60 | power PCB 1.60 | 1.60 |
| +4.20 | 10.00 mm face gap: insulator 2.54 + post 5.842, 3.33 inserted into the 4.95 socket | 10.00 |
| +14.20 | control PCB 1.60 | 1.60 |
| **+15.80** | **control PCB B.Cu — top of the stack** | — |
| +21.80 | **envelope limit** (55.80 above the fin tips) | — |

**As built: 49.80 mm** (−34.00 → +15.80) with **6.00 mm of headroom** to the 55.80 envelope. The
control board is F.Cu-down: all 148 footprints, including the 6.00 mm Bourns SRR1260, face into the
gap and its lowest point is z +8.20, leaving **1.46 mm** to the header insulator at +6.74. Nothing
sits on the control board's B side. The old ladder's `ctrl_part_top = +21.80` was the **F.Cu-up**
case; with F.Cu-down the parts are inside the gap, and the drawing/table are corrected accordingly.

## 2. THE SINK

### 2.1 Where −1.040 comes from

The moulding = pads ± 1.27 mm. At the delivered position the bank's odd column was at 133.27, so the
moulding began at **132.00** = **+1.500 mm** clear of the sink's right edge at 130.50. The B.Cu flip
mirrors the pad geometry 2.54 mm toward −x (`aFlipLeftRight=False`), so the moulding's left edge goes
to **129.46** = **−1.040 mm**: 1.04 mm past the sink's edge line. That is a plan-view keep-out
incursion only — the moulding is 4.20 mm above the sink's contact face — but the 1.500 was the design
intent.

### 2.2 The 1.04 mm trim is not FET-safe — measured, not assumed

Every `IPTC014N10NM5` drain (thermal) pad is **10.2 × 7.0 = 71.4 mm²**; the four right-hand devices
**Q3CH, Q3CL, Q6CH, Q6CL** have their drain rect at **x 119.48 … 129.68**. A 1.04 mm trim puts the
edge at 129.46, cutting **0.22 mm × 7.0 mm = 1.54 mm² per device, 6.16 mm² total** (0.24 % of the
2 570.4 mm² drain land). The full FET pad field reaches **129.78**, so the all-copper loss is
**9.488 mm²**.

The draft's `04_geom2.uncovered()` / `04b.ov()` used `b − a` instead of `b − max(a, edge)` and
returned either 0 or the covered width; the 6.16 mm² figure was right by hand, the instrument was
not. `14_sink_trim.py` recomputes it correctly.

### 2.3 The fix is the bank shift, not a trim: 0.00 mm applied

The DRC correction already requires moving the bank at least 0.80 mm. Moving it **+2.54 mm** — one
full pitch — instead of the minimal amount puts the moulding at **132.00**, i.e. **1.500 mm** from the
untrimmed sink edge. That is the design intent restored exactly, with no sink cut, no FET loss, and
no thermal penalty. The control-board sockets move with it, and their rightmost courtyard ends at
**149.79**, still **1.36 mm inside** the 151.15 mm control outline (`17_verify_dx254.json`).

| trim mm | edge x | drain uncovered | all FET copper uncovered | sink w | clearance @ dx 2.54 | Tj °C |
|---:|---:|---:|---:|---:|---:|---:|
| **0.00 (applied)** | **130.50** | **0.000** | **0.000** | **125.00** | **1.500** | **123.15** |
| 0.62 | 129.88 | 0.000 | 0.000 | 124.38 | 2.120 | 123.29 |
| 0.72 | 129.78 | 0.000 | 0.000 | 124.28 | 2.220 | 123.32 |
| 0.82 | 129.68 | 0.000 | 1.040 (non-drain) | 124.18 | 2.320 | 123.34 |
| 1.04 (specified) | 129.46 | **6.160** | **9.488** | 123.96 | 2.540 | 124.29 (4 right) |

The partial trims buy clearance beyond the 1.500 intent at the cost of sink area and (at 0.82) 1.04 mm²
of non-drain copper; 1.04 buys nothing but loses 6.16 mm² of drain land. **0.00 is the correct
correction**, and it is why the specified trim is not applied.

### 2.4 Tj at 80 A, restated

Carried model (`esc-sink-clearance/03_numbers.json`): Ta 45 °C, Q80 = 448 W, Pdev = 11.9 W,
Rth_jc 0.4, Rth_tim 3.43 K/W, Rth_sa ∝ 1/area. Recomputed by `14_sink_trim.py`:

| | value |
|---|---|
| Rth_sa (125.00 wide) | 0.0661 K/W |
| T_sink | **77.57 °C** |
| Tj | **123.15 °C** |
| junction-to-sink | **45.6 K** (0.4 + 3.43 K/W × 11.9 W) |
| of which Sil-Pad | **40.8 K** (3.43 × 11.9) |
| verdict | **PAD-LIMITED** — more aluminium cannot recover the Sil-Pad drop; a 0.006 in Sil-Pad or PTM7950-class TIM would (CARRIED options: 110.3 °C / 90.9 °C) |

The rejected 1.04 trim would cost **+1.14 K** on the four right devices and remove 6.16 mm² of drain
land; the adopted no-trim case is the baseline 123.15 °C.

## 3. THE 144 NETLESS PADS

Six `Conn_02x12_Pin` at (4.1, 10.3) (47.2, 10.3) (90.3, 10.3) (4.1, 50.3) (47.2, 50.3) (90.3, 50.3),
references **J1…J6**, 2×12 PTH Ø1.0 drill / Ø1.7 pad, body 5.08 × 29.64 × 2.54.

| check | before | after |
|---|---|---|
| footprints on the power board | 173 | **167** |
| pads | 1 581 | **1 437** (−144) |
| PTH pads on the board | 264 | **120** (header bank only) |
| netless pads | 144 | **0** |
| PTH pad centres inside sink rect (x 5.5–130.5, y 7.0–81.0) | 120 | **0** |
| min PTH copper x | 4.10 − 0.85 = **3.25** | **132.42** (1.92 mm clear of BAR2, 2.64 mm clear of the gate pads) |
| DRC items naming them | **0 of 499** | — |

All 144 read `GetNetname() == ""` before deletion, so nothing was disconnected (`12_pth_check.py`,
`12_pth_final.json`). The sink rectangle is now clear of **all** PTH; the nearest copper is 1.92 mm
outside it.

## 4. THE 11 NEW DRC ITEMS

### 4.1 Identification (exact, from `drc/base/drc.json`)

All eleven are `J_H1` — the leftmost strip — against copper just left of it. `BAR2` pad 1 is the
**BATN** bus-bar land: 113.50 × 4.50 mm at x 17.00 … **130.50**, y 42.00 … 46.50. The gate pads are
0.80 × 2.60 at x 128.98 … 129.78.

| # | type | item A | item B (net) | location (J_H1 pad, before shift) |
|---:|---|---|---|---|
| 1 | `shorting_items` | `J_H1` pad 18 (SWCLK) | `BAR2` pad 1 (BATN) | 130.73, 41.59 |
| 2 | `shorting_items` | `J_H1` pad 20 (DGND) | `BAR2` pad 1 (BATN) | 130.73, 44.13 |
| 3 | `shorting_items` | `J_H1` pad 22 (UART_RX) | `BAR2` pad 1 (BATN) | 130.73, 46.67 |
| 4 | `solder_mask_bridge` | `J_H1` pad 18 (SWCLK) | `BAR2` pad 1 (BATN) | 130.73, 41.59 |
| 5 | `solder_mask_bridge` | `J_H1` pad 20 (DGND) | `BAR2` pad 1 (BATN) | 130.73, 44.13 |
| 6 | `solder_mask_bridge` | `J_H1` pad 22 (UART_RX) | `BAR2` pad 1 (BATN) | 130.73, 46.67 |
| 7 | `solder_mask_bridge` | `J_H1` pad 10 (DGND) | `Q3CL` pad 8 (M3_GCL) | 130.73, 31.43 |
| 8 | `solder_mask_bridge` | `J_H1` pad 12 (DGND) | `Q3CL` pad 8 (M3_GCL) | 130.73, 33.97 |
| 9 | `solder_mask_bridge` | `J_H1` pad 28 (DGND) | `Q6CL` pad 8 (M6_GCL) | 130.73, 54.29 |
| 10 | `solder_mask_bridge` | `J_H1` pad 30 (SPI_MOSI) | `Q6CL` pad 8 (M6_GCL) | 130.73, 56.83 |
| 11 | `solder_mask_bridge` | `J_H1` pad 40 (DGND) | `Q6CH` pad 8 (M6_GCH) | 130.73, 69.53 |

**Cause, one line:** the B.Cu flip mirrors the even column from x 135.81 to **130.73**; its Ø1.7
annulus then reaches x **129.88**, while `BAR2` pad 1 reaches **130.50** and the gate pads reach
**129.78** — a 0.62 mm overlap into a 3-oz bus bar, and a mask web of zero into four gate lands.
The draft attributed item 11 to Q6CL; measured, it is **Q6CH pad 8**.

### 4.2 The fix: +2.54 mm bank shift on both boards

* **Minimum measured, not estimated.** Swept `dx` and re-ran the full DRC at each:
  **0.55** → 2 shorting + 3 mask; **0.62** → 1 shorting + 3 mask; **0.70** → 2 mask; **0.80** → **0**.
  0.90, 1.00, 1.15, 1.27, 2.54 → 0. `sweep/` + `work_dx254/`; clearance stays 499 at every `dx`
  because of the cap.
* **Applied 2.54 mm** = one full pitch, 3.2× the minimum. It is the value that restores the sink
  clearance to 1.500 (§2.3), so it does two jobs with one move. Final measured margins: **1.92 mm**
  to BATN (132.42 − 130.50), **2.64 mm** to the gate pads (132.42 − 129.78), **1.85 mm** between
  J_H1's odd pad and J_H2's even pad, **2.98 mm** from the bank's outer copper (148.84) to the plate
  edge (151.82), and **1.36 mm** from the control J_H3 courtyard (149.79) to its 151.15 outline. All
  above the 0.25 mm rule.
* **Pitch integrity:** 2.54 mm is one pitch; each strip keeps its own 2.54 mm internal pitch and its
  6.09 mm centre, so the wire list is untouched. The control board's three sockets move by the same
  +2.54 mm; its outline, pad count and B.Cu census do not change.
* **Value retagged** to `TSW-120-07-G-D` on all three headers, so the BOM and the board agree.

### 4.3 Set diff after

Item-level, key = `(type, severity, sorted item descriptions)` (`08_setdiff.py`, `08_setdiff.json`):

| | before (matefixB) | after (final) | plus | minus |
|---|---:|---:|---|---|
| **power** | 539 | **527** | `{clearance\|error: 1}` | `{shorting_items\|error: 3, solder_mask_bridge\|error: 8, clearance\|error: 1, silk_over_copper\|warning: 1}` |
| **control** | 37 | **37** | `{}` | `{}` |

**All 11 are gone; nothing of the 11 was replaced.** Two honest footnotes:

1. **The +1/−1 `clearance` is the same physical pair, renumbered at the cap boundary.** Base reports
   `Q6BL` pad 9 [M6_PHB] vs its netless pad at (112.08, 60.50); final reports pad 8 [M6_GBL] vs the
   same netless pad. The footprint never moved. Both pairs collide at 0.25 and 0.30 mm on **both**
   boards (checked with `SHAPE.Collide`: both `True`), so the cap simply listed the other one after
   six footprints were deleted. Normalised by physical pair: **+{} / −{11}**.
2. **The −1 `silk_over_copper`** is `U11`'s reference field, which was silkscreened over a `J1…J6`
   pad. Deleting the six connectors removed it. That is a real −1, not a renumbering.

Unconnected: **187 → 187**, unchanged — the deleted pads carried no nets.

## 5. FINAL DRC AND THE TWO BOARDS

Run per board in its own scratch directory with companions (`drc/final_power/`,
`drc/final_control/`; copies in `drc/verified_*`), JSON read from disk, never from stdout. **Read
§0.1 before quoting the power total.**

| | power **final** | control **final** |
|---|---:|---:|
| violations | **527 listed** | **37** |
| breakdown | 499 `clearance` (**CAP**) + 28 `silk_over_copper` | 10 `clearance`, 2 `courtyards_overlap`, 4 `solder_mask_bridge`, 7 `silk_edge_clearance`, 5 `silk_over_copper`, 9 `silk_overlap` |
| 11 target items | **0** | 0 |
| set diff | **+{} / −{11}** normalised | **+{} / −{}** |
| unconnected (JSON list) | **187** | **41** |
| footprints / pads | 167 / 1 437 | 148 / 768 |
| outline (pcbnew bbox) | 151.87 × 122.65 mm, 186.27 cm² | 107.10 × 60.10 mm, 64.37 cm² |
| copper layers | 4 (3 / 1.5 / 1.5 / 3 oz) | 2 (1 oz) |
| tracks / vias / zones | **0 / 0 / 0** | **0 / 0 / 0** |
| **footprints on B.Cu** | **3 — `J_H1`, `J_H2`, `J_H3`** | **0** |
| B.Cu-*only* pads | 0 | 0 |

* **Control board: 0 components on B.Cu** — layer census, not by eye (`07_verify.py`). All 148
  footprints, including the three sockets, are on F.Cu; the board is 100 % single-sided.
* **Power board: 3 components on B.Cu** — the three headers and nothing else. They must be there:
  the F.Cu face is spent on the 36 FETs, which must sit on the sink. No B.Cu-only pads, so every pad
  in that bank is a through-hole land on both faces, as a THT part requires.
* **The 187 unconnected** is the routed-span list on an **unrouted** board (0 tracks/vias/zones),
  identical before and after this task. It is not a `kicad-cli` list cap: `len(unconnected_items)` is
  187 and the cap is 499. Routing is the sibling unit's job; this task did not route.
* **Mate re-verified on the shipped pair**: **120/120** pads coincide within 1 µm, max residual
  **0.000000000 mm**, **0 net mismatches** (`07_verify.json`).
* The 37 on the control board are inherited (10 clearance, 2 courtyard, 4 mask, 21 silk); the +2.54
  socket move changed none of them, and the set diff is empty.

## 6. SURFACE FINISH IN BOTH .gbrjob FILES

`kicad-cli pcb export gerbers` writes a Ucamco job file, but its default `Finish` is **`"None"`** —
the exact empty-value trap that blocks a fab order. Both are now **ENIG**:

| board | job file | files listed | `GeneralSpecs.Finish` |
|---|---|---:|---|
| power | `fab/power/esc_power_board_final-job.gbrjob` | 9 (F/B Cu, In1/In2 Cu, F/B mask, F/B silk, Edge) | **`ENIG`** |
| control | `fab/control/esc_control_board_final-job.gbrjob` | 7 (F/B Cu, F/B mask, F/B silk, Edge) | **`ENIG`** |

Generated 2026-11-17 with `kicad-cli 9.0.7` from the adopted +2.54 boards, then the
`"Finish": "None"` token was replaced with `"Finish": "ENIG"` and the JSON re-parsed
(`ConvertFrom-Json`) to confirm: power `Size 151.87 × 122.65`, `LayerNumber 4`, `BoardThickness 1.6`;
control `107.10 × 60.10`, `LayerNumber 2`. ENIG is the right finish for 3-oz outer copper and the
0.25 mm pattern class (HASL's thickness variation is not acceptable). **The gerbers are of the
unrouted boards** — re-export after routing; the `Finish` field is the deliverable here.

## 7. DIMENSIONED SECTION DRAWING

![stack section](11_section.png)

`11_section.png` / `.svg`, drawn to scale (1 unit = 1 mm) from the measured numbers in §1–§2:

* **A** — full stack at y = 44.25 (through the bank). Sink 34.00 deep under a machined contact face at
  z 0.00, the 4-layer power board, the 10.00 mm gap carrying the header insulator/post/socket **and**
  the control board's 6.00 mm SRR1260, the control board F.Cu-down. The dashed line at +21.80 is the
  **55.80 mm envelope limit**, not a part; the stack tops out at +15.80. Dimensioned **49.80 mm as
  built**.
* **B** — the bank/sink edge. The 5.842 mm post with its tip at +12.58 inside the socket (1.62 mm
  clear of the control board), the **1.92 mm** gap to `BAR2`'s BATN land that replaces the 0.62 mm
  overlap, the **2.54 mm** shift, the tail ending at −0.88, the **1.500 mm** moulding-to-sink
  clearance, and the untrimmed sink edge at **130.50**.

## 8. WHAT I DID NOT DO / WHAT NOT TO ASSUME

1. **The specified 1.04 mm sink trim was not applied.** It uncovers 6.16 mm² of drain land (9.49 mm²
   of FET copper) on four devices. The +2.54 mm bank shift restores the 1.500 mm intent exactly with
   no trim and no FET loss. The sink is a mechanical part, so the trim/clearance lives in this spec
   and the drawing, not in the `.kicad_pcb`.
2. **The power clearance total is capped at 499** (§0.1). 527 is a **floor**, not a measurement. Do
   not quote it as "the board has 527 violations" without the cap. The 11 target items and the silk
   warnings are outside the cap and are complete.
3. **No routing, no copper pour, no via work.** The input `esc_power_board_matefixB.kicad_pcb` is
   unrouted (0 tracks/vias/zones, 187 unconnected). The brief said earlier waves had routed the power
   path; that routed variant is **not this input file**. These corrections are geometric (part value,
   sink spec, pad deletion, bank shift) and would carry to a routed copy, but the DRC totals quoted
   here are for the provided board. The 187 is not a regression.
4. **The gerbers are unrouted.** The job files' `Finish` is valid; the copper content will change when
   the sibling routing unit lands.
5. **The `.kicad_dru`'s edge/annular/hole rules are evaluated** — no `edge_clearance`/`annular_width`/
   `hole_size` violations were reported at the board's own 0.25/0.20 settings (the 120
   `drill_out_of_range` only appeared under the deliberate 5 mm probe).
6. **No schematic parity** was run (`--schematic-parity` not used); the netlist is the input's.
7. **Tj is the carried analytical model**, not a measurement: Ta 45 °C, Q80 448 W, Pdev 11.9 W,
   Rth_jc 0.4, Rth_tim 3.43 K/W, Rth_sa ∝ 1/area. It says pad-limited, and the no-trim case is the
   baseline 123.15 °C.

## 9. PROVENANCE

| number | instrument |
|---|---|
| post / OAL / tail | Samtec product page (HTML, 2026-11-17) + series print; tail = OAL − post |
| post tip, insertion, cavity clearance | arithmetic on the carried z ladder (`esc-sink-clearance/03_numbers.json`) and the 5.842 post |
| sink coverage, 6.16 / 9.488 mm², drain extents | `14_sink_trim.py` — pad rectangles from `pcbnew`, clipped at the trim line (`14_sink_trim.json`) |
| Tj, Rth_sa | `14_sink_trim.py` — carried model, rescaled by its own 1/A proportionality |
| 144 netless pads, PTH-in-sink = 0 | `12_pth_check.py` / `12_pth_final.json` — `PAD_ATTRIB_PTH` + point-in-rect + copper extents |
| 11 DRC items, type / pads / nets / positions | `drc/base/drc.json` item descriptions |
| the dx sweep, 0.55 … 2.54 | `05_build.py`, `16_build_dx254.py` + `kicad-cli` DRC at each offset (`sweep/`, `work_dx254/`) |
| set diffs | `08_setdiff.py` / `08_setdiff.json`, key = (type, severity, sorted descriptions) |
| 499 cap, rule-load positive control | `15_rule_gate/` — 8 runs, raw JSON kept |
| 120/120 mate, B.Cu census, 1.500 clearance | `07_verify.py` / `07_verify.json`, `17_verify_dx254.py` / `17_verify_dx254.json` |
| final DRC | `kicad-cli 9.0.7`, `drc/final_power/`, `drc/final_control/` |
| `Finish` field | `kicad-cli` job file + JSON re-parse (`fab/*/...-job.gbrjob`) |
| drawing | `11_section.py` — matplotlib, from the numbers above |

## 10. FILES

```
01_probe_pwr.py / .json                power board census, pads, nets, setup
02_geom.py / 02_geom.json              board boxes, F/B courtyards, footprint bboxes
03_fet_h1.py, 03b_vals.py              FET identification
04_geom2.py / 04_geom2.json            FET extents, Conn_02x12 netlessness  (uncovered() was buggy; superseded by 14)
04b_fet_detail.py                      right-hand drain pads vs the trim line (same formula bug; superseded)
05_build.py                            dx builder (move bank, delete J1-J6)
06_final_build.py                      the +1.27 pair (superseded, kept)
07_verify.py / 07_verify.json          120/120 mate + layer census on the shipped pair
08_setdiff.py / 08_setdiff.json        item-level set diff, both boards
09_obst.py                             BAR2 / gate pad coordinates
10_thermal.py / 10_thermal.json        draft Tj model (0.82/1.04 cases; 14 extends it)
11_section.py / .png / .svg            THE SECTION DRAWING (sink untrimmed, 1.500, +2.54)
12_pth_check.py / 12_pth_final.json    PTH census after the deletion
13_analytic_clear.py / .json           pad-pair proximity probe (over-counts local clearance; NOT used as a total)
14_sink_trim.py / 14_sink_trim.json    corrected coverage + thermal for 0.00/0.62/0.72/0.82/1.04
15_rule_gate/                          8 DRC runs: cap + rule-load proof, raw JSON + summary
16_build_dx254.py                      the adopted +2.54 pair builder
17_verify_dx254.py / .json             mate, census, 1.500/1.92/2.64/1.85/2.98/1.36 clearances
esc_power_board_final.kicad_pcb        THE POWER BOARD (+2.54, 167 fps, B.Cu = 3 headers, 0 tracks)
esc_control_board_final.kicad_pcb      THE CONTROL BOARD (+2.54, 148 fps, B.Cu = 0, 0 tracks)
esc_*_dx127.kicad_pcb                  the superseded +1.27 pair (kept for provenance)
work_dx254/                            the +2.54 build inputs and DRC runs
fab/power/                             gerbers + esc_power_board_final-job.gbrjob (Finish ENIG)
fab/control/                           gerbers + esc_control_board_final-job.gbrjob (Finish ENIG)
drc/{base,base_control,final_power,final_control,verified_power,verified_control,...}/
REPORT_draft1.md                       the interrupted draft (kept for provenance)
```