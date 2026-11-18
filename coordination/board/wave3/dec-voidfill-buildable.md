# dec-voidfill-buildable — what a genuinely buildable version of the 13-segment void fix looks like

**Item.** Wave 2 proposed moving 13 In1 signal segments off In1 to kill the RF void, then measured
**1.307 %** on a *copy with those nets deleted* — not a rerouted board (board line 53, wave-2
`REPORT.md:323-331`). This item builds the fix as **real copper**, checks it with `kicad-cli` DRC,
and asks whether a cheaper path gets the same physics.

**Board:** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb` (branch `work/2026-11-11`,
read-only, never saved). **All writes are inside `evidence/dec-voidfill-buildable/`.**
**Tools:** KiCad 9.0.7 `pcbnew` (numpy 2.3.5 / scipy 1.17.1 in the KiCad interpreter),
`kicad-cli pcb drc --format json`.

---

## 0. Answers in one screen

| question | answer |
|---|---|
| Can the 13 segments go on B.Cu? | **YES for 10 of 13**, measured: **117.412 of 127.963 mm²** of the swept corridors is free of other-net solid copper (**91.8 %**). The 3 that fail fail in *both* an independent raster channel test and `kicad-cli` DRC. |
| Is "B.Cu is 12,728.8 of 14,036 mm² filled" a blocker? | **No.** That number is the **pour**, and a pour refills around new copper. B.Cu solid copper (tracks + pads + vias) is **238.635 mm²** = 1.70 % of the board; free of solid copper **13,761 mm²**. |
| Cheapest real option | **5 copper moves + 1 HDI bridge via + 2 zone values → 1.477 % void**, 0 unconnected items. |
| Wave-2's 13 moves | 1.307 % confirmed exactly as real copper (`b13`), but **4 of the 13 moves recover 0.000 mm²** and 15 DRC items remain. |
| Stackup re-spin (the expensive lever) | ≈ **1.1 %** — the vias that punch In1 still void it. **No better than the 5-move option.** Do not re-spin. |

---

## 1. Board corrections

**BOARD CORRECTION (line 75).** `...is 12,728.8 of 14,036 mm2 already filled`. The fill number is
exact (12,728.793 mm², `10_inventory_bcu.json`), but **14,036 is the bounding box** (140.15 ×
100.15 mm). The Edge_Cuts outline is **140.000 × 100.000 mm = 14,000.0 mm²** — the same 140 × 100
the board itself reports at line 56 — so the fill is **90.93 %**, not 90.68 %. More importantly the
inference attached to that line ("so there is no room") is **unsound**: 12,728.793 of B.Cu's
12,967.428 mm² of copper is *pour*, which refills around new copper. The routing constraint is the
**238.635 mm² of solid copper**, and it is not fragmented — the free area is one 13,662.6 mm²
component plus three slivers (`20_free_area_B_m0.8.json:board_free_components`).

**BOARD CORRECTION (lines 53 and 152).** Both say the fix is "moving **13** In1 segments". 13 is a
correct *upper bound* but **4 of the 13 are inert**: moving only the 4 `/RF_GPIO2` segments
(`b4`) returns **9.834 %**, i.e. **exactly the baseline, 0.0000 mm² recovered**, and costs 2 DRC
shorts. Wave-2's own data already showed it (tag `r`, 11 segments, = **2.010 %**, identical to my
7-segment build `b7`), it was just not read that way. The value-carrying set is **7 segments of
`/VDD_CC112` (7.82 pp)** + **2 GNSS segments (0.70 pp)**.

**Correction to `evidence/w2-da-voidfill/REPORT.md:297-299`** (not a board line): it says the fixed
corridor "returns to the solid-plane condition, i.e. the wave-1 solid-plane S11 of −10.5 dB". The
−10.5 dB figure is the **contiguous-void** case; the solid-plane case is **−32.40 dB**
(`da-em-field/REPORT.md:185-193`, table rows 1 and 6). Wave-2 swapped the two.

---

## 2. Method — three measurements that can disagree, and do agree

1. **Exact free-area geometry.** `SHAPE_POLY_SET` boolean ops, polygonisation error 0.002 mm:
   corridor (= each segment swept at `w + 2 × 0.8 mm`) minus **other-net solid B.Cu copper**
   (tracks, pads, vias). Zone fills are deliberately **not** obstacles (they refill) — this is the
   difference from wave-2's "B.Cu has room" hand-wave, and it is justified by the refill test in §5.
2. **Channel test on a raster.** Free space eroded by `w/2 + 0.125` (every netclass on this board
   is 0.125, `10_inventory_bcu.json:all_netclass_clearances`), then 8-connected labelling between
   the segment's two endpoints. A path anywhere inside the window counts, so a detour is allowed.
3. **Real built boards + DRC.** `30_build.py` moves each segment to B.Cu **at the same XY** with the
   same net and width — no rerouting, just a layer change — then `31_refill.py` and `40_measure.py`
   in separate processes (SWIG invalidates zones after track edits), then `kicad-cli pcb drc`.
   Baseline control: `v_base` = the untouched copy, **0 violations, 0 unconnected items**.

Void definition is wave-2's (`12_measure.py`): In1 copper union (fill + In1 tracks + In1 pads)
subtracted from each RF_50R F.Cu trace footprint. It reproduces the baseline **9.834 %** and the
wave-2 result **1.307 %** exactly, so every number below is comparable to the board.

---

## 3. Q1 — can the 13 be routed on B.Cu? (measured, per segment)

**Board-level:** B.Cu carries 12,728.793 mm² pour, **238.635 mm² solid copper** (304 tracks /
534.74 mm, 30 pads, 341 vias, 19 nets). Free of solid copper: **13,761 mm² of 14,000**.

**Along the needed paths** (`20_free_area_B_m0.8.json`), 13 corridors of 127.963 mm² total:

| measure | value |
|---|---|
| corridor area free of other-net solid copper | **117.412 mm² = 91.8 %** |
| segments with a legal `w/2+0.125` channel end-to-end | **10 of 13** |
| largest single free island seen in a corridor | **35.308 mm²** (the 5.116 mm horizontal) |
| same test with a ±2.0 mm window | **still 10 of 13** — the 3 failures are not a window artefact |

Per-segment detail (free / corridor, largest free island, channel):

| # | net | len mm | free mm² / corridor | island mm² | channel |
|---|---|---|---|---|---|
| 1 | VDD_CC112 | 2.167 | 6.211 / 6.701 (92.7 %) | 6.176 | **OK** |
| 2 | VDD_CC112 | 2.716 | 7.437 / 7.716 (96.4 %) | 7.464 | **OK** |
| 3 | VDD_CC112 | 5.116 | 12.155 / 12.155 (**100 %**) | 12.103 | **OK** |
| 4 | VDD_CC112 | 0.134 | 2.939 / 2.939 (100 %) | 2.938 | **OK** |
| 5 | VDD_CC112 | 1.538 | 4.926 / 5.537 (89.0 %) | 2.919 | **BLOCKED** — crosses `/HGM` |
| 6 | VDD_CC112 | 0.389 | 2.620 / 3.412 (76.8 %) | 2.092 | **OK** |
| 7 | VDD_CC112 | 0.207 | 3.074 / 3.074 (100 %) | 3.073 | **OK** (but see §4) |
| 12 | GNSS_RESET_OD | 22.147 | 42.798 / 43.663 (98.0 %) | 42.559 | **OK** |
| 13 | GNSS_UART_RX | 12.123 | 24.739 / 25.119 (98.5 %) | 24.601 | **OK** |
| 8 | RF_GPIO2 | 1.900 | 4.195 / 5.968 (70.3 %) | 2.142 | **BLOCKED** — U40 pad field |
| 9 | RF_GPIO2 | 2.000 | 2.140 / 6.148 (34.8 %) | 2.016 | **BLOCKED** — U40 pad 33 (/GND) |
| 10–11 | RF_GPIO2 | 0.241 | 2.09 / 2.77 | ~1.9 | OK |

**The two methods agree item-for-item.** The raster's three BLOCKED segments are exactly the three
`kicad-cli` reports as physical conflicts on `b13`: `/VDD_CC112` 1.538 mm **shorts `/HGM`** (a 12.8 mm
B.Cu track), `/RF_GPIO2` 2.000 mm **shorts /GND pad 33 of U40**, `/RF_GPIO2` 1.900 mm **crosses
`/HGM`**. Nothing else on B.Cu objects.

**So: B_CU_FEASIBLE = yes, 10 of 13 straight down, with the measured free area above.** The answer
that matters even more: **the 4 RF_GPIO2 segments are two of the three blockers and they recover
nothing**, so the practically buildable set is the 7 VDD + 2 GNSS.

### The one thing that blocks even the VDD set: the tee junction

`/VDD_CC112`'s 5.116 mm horizontal at y = 64.381 is bridged to the 0.1 mm micro via (drill 0.100 /
pad 0.300, **F.Cu–In1 only**) by a 0.207 mm tee at **(95.250, 64.381)**. Measurements
(`16_probe_via.py`, `15_probe_pad15.py`):

* the horizontal is the *only* path between U40 pad 15's branch and the rest of the net — splitting
  it leaves 1 unconnected item (`b5t`, `b5tc`);
* a **through** via at the junction needs `0.3 + 0.125 = 0.425 mm`, and `17_probe_clearance.py`
  measures **0.1081 mm** from that point to the nearest `CC_PA` F.Cu track edge — **illegal by
  0.317 mm**. (`b5f` proved the F.Cu bypass alternative fails too: U40 pad 14 `/CC_RBIAS` sits in
  the gap — 3 violations.)
* a **buried In1→B.Cu via has no F.Cu pad at all**, so the F.Cu clearance rule never applies to it;
  on In1 and B.Cu the junction is clear. Measured: `b5hk` is **0 unconnected items** with the
  bridge in place (vs 1 without it), and no clearance violation. Cost is on the fab side — a
  sequential-lamination buried via — which the owner's steer accepts outright.

With that bridge the net is whole: **`b5hk` = 0 unconnected items** (vs 1 without it).

---

## 4. Q2 — the cheaper options, each quantified

| lever | measured result | verdict |
|---|---|---|
| **thinner pour + clearance rule** (`/3V3` 0.25→0.125, min_thickness 0.25→0.10) | **8.967 %** (wave-2 tag `q`, cited) / **8.975 %** (tag `o`, 5 edits) | −0.87 pp for zero copper moves, but 96.5 % of the void area is *full width* (wave-2 §3), so Z0 still hits 118 Ω. **Not a fix.** |
| **0-ohm / F.Cu (double-sided) move** | F.Cu channel exists for **1 of 13**; free 76.9 % but max inscribed free radius **0.18–0.27 mm** against 0.225–0.250 needed | dead: the top side is the RF corridor. A 0-ohm adds 2 parts + 2 placements and saves no fab (vias are free). |
| **accept a defined void "where the trace is already over solid plane"** | = the as-built board: **9.834 %**, 0 effort | not expressible: a void *is* plane-absent. This is option O0, and it keeps S11 −10.5 dB. |
| **move the 13** | **1.307 %** (`b13`, exactly wave-2's deleted-net number, now real copper) | 15 DRC items, 6 vias, 4 inert moves |
| **move 13 + clearance rule** | **0.912 %** (`b13c`) | best void % of anything buildable; the extra 0.4 pp costs 4 GNSS vias |
| **stackup re-spin** (In1 all /GND) | ≈ **1.13 %** — the two `CC_LNA_N` vias still punch In1 (0.48 mm² of annulus voids, wave-2 `13`/`15_final`), *plus* every other via in the corridor | **no better than the 5-move option, at re-spin cost. Rejected.** |

B.Cu cost of the moves, measured by refill (`40_measure.json:pour`): 13 moves displace
**−26.76 mm²** of B.Cu GND (12,728.793 → 12,702.034), 7 moves **−5.23 mm²**, 5 moves **−5.14 mm²**.
B.Cu is not the RF reference (In1 is 0.200 mm away, B.Cu 1.510 mm), so this is shielding area, not
return-path impedance; F.Cu pour is unchanged (12,188.556) in every variant.

---

## 5. Q3 — options ranked by design effort

Ranked by effort = copper moves + rule edits + 2 × new vias (fab burden excluded, per the steer).
`void %` is method A (wave-2's definition); `Z0` is the da-em-field 2D FD sweep evaluated at the
measured residual void width (solid **52.61 Ω**, no-plane **118.12 Ω**, sweep in `fd_results.json`);
`run %` is the fraction of the 102.354 mm run sitting at the peak.

| rank | option | moves | vias | rules | score | **void %** | **Z0 spread** | DRC |
|---|---|---|---|---|---|---|---|---|
| 1 | **O0** accept as built, document it | 0 | 0 | 0 | 0 | **9.834** | 52.6 → 118.1 over **11.6 %** of run | 0/0 |
| 2 | **O1** thinner pour + clearance only | 0 | 0 | 2 | 2 | **8.967** | 52.6 → 118.1 over **10.6 %** | – |
| 3 | **O3** 5 VDD moves, no bridge via | 5 | 0 | 0 | 5 | **2.474** | 52.6 → 72.2 over 2.9 % | 0 err / **1 unconn** |
| 4 | **O3c** 5 VDD moves + rule edit, no bridge | 5 | 0 | 2 | 7 | **1.474** | 52.6 → 72.2 over **1.7 %** | 0 err / **1 unconn** |
| 5 | **O4b** 5 moves + bridge via, no rule edit | 5 | 1 | 0 | 7 | **2.476** | 52.6 → 72.2 over 2.9 % | 3 err / 0 |
| 6 | **O2** move 4 RF_GPIO2 segments | 4 | 2 | 0 | 8 | **9.834** | 52.6 → 118.1 over 11.6 % | 5 err / 2 |
| 7 | **O4 ← RECOMMENDED** 5 moves + bridge via + rule edit | 5 | 1 | 2 | 9 | **1.477** | 52.6 → 72.2 over **1.75 %** | 3 err / **0** |
| 8 | **O5** 7 VDD moves + rule edit (needs a /HGM jog) | 7 | 0 | 2 | 9 | **1.296** | 52.6 → 72.2 over 1.53 % | 5 err / 1 |
| 9 | **O6** all 13 + rule edit (wave-2's proposal) | 13 | 6 | 2 | 27 | **0.912** | 52.6 → 72.2 over 1.08 % | 15 err / 6 |
| 10 | **O7** stackup re-spin | 350 | – | – | 350 | ~1.13 | 52.6 → 71.6 over 1.34 % | UNVERIFIED |

`score = moves + rule_edits + 2 × new_vias` — fab burden is excluded per the steer, so a via costs
design time only in the sense of a constrained placement. Machine-readable: **`OPTIONS.csv`** /
`60_options.json`.

Two readings of this table:

* **The void fraction is not the cost driver any more.** Everything from rank 4 down is between
  0.912 % and 2.476 %, i.e. ≤ 2.9 % of the run at ~72 Ω and 97 %+ at 52.6 Ω. The step reflection per
  void is Γ = (72.2−52.6)/(72.2+52.6) = **0.157** over ≤ 1.8 mm = 0.010 λg → net two-step
  contribution ≈ 0.003 → **below −45 dB**, i.e. the void stops being the limiter. Wave-2's −41 dB
  two-step estimate was for 118 Ω steps; at 72 Ω it is smaller still.
* **The effort driver is the tie-break, and 4 of the 13 moves are pure cost.** Rank 3 exists only
  to show that: 4 moves, 2 vias, 2 shorts, **0.000 mm²**.

---

## 6. Q4 — the option I would take, and what it costs

**O4: five copper moves on `/VDD_CC112` + one 0.1 mm HDI bridge via + two zone values.
1.477 % void, 0 unconnected items, Z0 52.6 Ω nominal / 72 Ω peak over 1.75 % of the run.**

The five moves — segments 1, 2, 3, 4, 6 of wave-2's list, **10.522 mm of In1 track** (2.167 + 2.716 +
5.116 + 0.134 + 0.389), all `/VDD_CC112`, all at **the same XY** on B.Cu, so there is **no reroute at
all**: they are layer-property edits. Endpoints already sit on through vias except the tee.

Extra objects: **1 buried via, drill 0.100 / pad 0.300, layer pair In1 → B.Cu, at
(94.850, 64.381)** plus a 0.4 mm B.Cu stub and a 0.4 mm In1 stub to reach it — the tee junction
itself is only **0.1081 mm** from `CC_PA` on F.Cu, so the transition has to be one that carries no
F.Cu pad. Rule edits: In1 `/3V3` clearance **0.25 → 0.125**, min_thickness **0.25 → 0.10**.

What it deliberately does **not** do, and why:

* **does not move the 4 RF_GPIO2 segments** — measured **0.000 mm²** of recovery, 2 DRC shorts.
* **does not move the 2 GNSS diagonals** — 34.27 mm of reroute and 4 new vias for **0.16 pp**
  (wave-2 §8 called these poor value; my numbers agree).
* **does not touch `/HGM`** — the 7th segment needs a local jog on a slow control net for **0.18 pp**.
  If someone wants that 0.18 pp, O5 (1.296 %) is measured and waiting; it is 1 jog away.
* **does not re-spin the stackup** — ≈ 1.13 % for a full re-spin, i.e. *worse than the point it
  would replace*.

Remaining work before this is a release: the 3 DRC items on `b5hkc` — two are rule-scope
(`drill_out_of_range`, `via_diameter` on the 0.1 mm blind via; the board's existing 0.1 mm microvias
pass because a custom microvia rule is scoped to `VIATYPE_MICROVIA`, so the bridge needs
`BLIND_BURIED` added to that rule or to be re-typed) and one is a `track_dangling` on the 0.4 mm
B.Cu stub whose end lands on the new via pad. All three are rule/clean-up, not geometry.

---

## 7. NOT verified

* **The DRC clean-up above was not finished.** `b5hkc` is 0 unconnected but **3 violations**, all
  on the new bridge via/stub. No variant in this directory is a 0/0 board.
* **The HGM jog was not built.** O5's 1.296 % carries 3 unresolved `/HGM` shorts; the jog is
  bounded (a 12.8 mm B.Cu run at y ≈ 59.2–59.4, 0.28 mm of local displacement) but unbuilt.
* **S11 was not re-simulated.** The electrical argument in §5 is the da-em-field cascade model
  re-evaluated at the new peak (Tier C on Tier-B anchors), not a new EM run.
* **The 4.1701 mm² baseline was not re-derived** — it is wave-2's, reproduced to 9.834 % by my
  measurement of the untouched board (`v_base`), which is the check I can make.
* **mechanical/assembly and 3V3 current-carrying impact** of the moved traces: not assessed.
* **Bridge-via manufacturability.** A buried In1→B.Cu via with **no F.Cu pad** implies drilling
  between lamination cycles (2 lamination passes) — a fab-process consequence, not an electrical
  stackup change (thicknesses and εr are untouched). The owner's steer accepts fab burden, so it is
  priced as acceptable here; the fab's actual 0.1 mm buried-via capability was **not quoted**. The
  alternative if sequential lamination is refused is a 0.6 mm through via, which needs `CC_PA`'s
  escape moved **0.317 mm** — an RF-layer copper move, i.e. strictly worse per the steer.

---

## 8. Files

| file | what |
|---|---|
| `REPORT.md` | this document |
| **`OPTIONS.csv`**, `60_options.json` | the ranked option table (void %, Z0 spread, DRC counts) |
| `60_options.py` | table generator: measured numbers + wave-2 citations + FD Z0 mapping |
| `10_inventory_bcu.py/.json` | B.Cu occupancy: pour 12,728.793, solid 238.635, netclasses, design rules |
| `15_probe_pad15.py`, `16_probe_via.py` | the tee / micro-via / U40 pad topology probes |
| `20_free_area.py`, `20_free_area_B_m0.8.json`, `_B_m2.0.json`, `_F_m0.8.json` | exact free area, islands, channel test per segment |
| `20_*.out.txt`, `20_*.err.txt` | raw console output of the above |
| `30_build.py` | builds each variant as **real copper** (layer change, same XY) |
| `31_refill.py`, `40_measure.py`, `40_measure.json` | refill in a fresh process; void measurement with residuals and bboxes |
| `50_drc_*.json` | `kicad-cli` DRC, baseline `v_base` = 0 violations / 0 unconnected |
| `run_ladder.ps1`, `run_ladder2.ps1`, `ladder*.out.txt` | variant ladders |
| `fixwork/v_*.kicad_pcb`, `v_*.kicad_pro` | every built, refilled variant board (reproducible) |

Reproduce: `"C:/Program Files/KiCad/9.0/bin/python.exe" 10_inventory_bcu.py`,
`... 20_free_area.py B 0.8`, `... 30_build.py b5hkc && ... 31_refill.py b5hkc && ... 40_measure.py b5hkc`,
then `kicad-cli pcb drc --format json -o 50_drc_b5hkc.json fixwork/v_b5hkc.kicad_pcb`.