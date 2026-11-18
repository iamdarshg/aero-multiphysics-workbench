# fab-da-fanout — the fan-out re-escape for drone-arm's last 24 non-through vias

**Item:** `fab-da-fanout` · **Board of record:** `evidence/fab-da-consolidate/da_main_rev_b_composed.kicad_pcb`
(sha256 `5DBAE23888059E0B6D6F18DC3066924FB8194C5FD4DFA250186D3B024F6F73B6`)
**Artefact:** `evidence/fab-da-fanout/da_main_rev_b_fanout5.kicad_pcb`
(sha256 `E65F0B2EED47E575AA82397ED662945BE395870C7C6B4E93CA899B9C82A5843A`, 2,260,448 B)
**Tooling:** KiCad 9.0.7 `pcbnew` (Python 3.11.5) + `kicad-cli pcb drc` / `pcb export drill`
**Constraints honoured:** 4-layer, standard PTH only, no HDI, no repo write, no commit/branch, no spend.
Every product of this item is inside this directory; the board was worked on COPIES only.

---

## 0. Answers in one screen

| question | answer |
|---|---|
| How many groups, and does the 9-of-20 finding reproduce? | **20 groups, 24 vias, 13 nets. 9 of 20 have the via centre inside another net's copper (dist ≤ 0)** — reproduced exactly (§1) |
| Can a 0.6 mm / 0.3 mm through via stand at the microvia's own XY anywhere? | **At 0 of 20.** A 0.6/0.3 via in place produces **188 kicad-cli DRC errors** (113 clearance, 52 shorting, 17 hole, 6 mask) and 0 unconnected (§2) |
| What was actually **EXECUTED**? | **5 of 20 groups** — F19 0.028 mm, F18 0.100, F07 0.072, F03 0.263, F20 0.260: a via nudge, not a re-route. 6 microvias → 5 standard through vias, 2 escape segments (§3) |
| DRC, board's own rules | before **0** → after **5** — *all 5 are `via_diameter`*, i.e. the 0.4 mm pad vs the project's 0.6 mm floor. With that one rule at 0.40: **0** (§4) |
| DRC, no-HDI gate | before **23** → after **17** (all `microvia_drill_out_of_range`) |
| Unconnected | **0 → 0** |
| Via census | **338 → 337**; 0.100 mm drills **23 → 17**; non-through **24 → 18** |
| Minimum drill | **0.100 → 0.100 mm** — unchanged, because 17 microvias at 0.100 mm remain |
| RF void under the RF corridor | **1.2959 % → 1.2959 %**, bit-identical (0.5495 of 42.4040 mm²); void_B 0.6013 % → 0.6013 % (§6) |
| What the remaining 15 need | **11 of them cannot take a via of any size at their own XY** (centre inside / within 0.125 mm of foreign copper). Of the 15: **2 need only foreign tracks pushed** (F16 one track, F17 seven), **2 need a sub-rule annular ring** (F05 0.050, F08 0.083), **2 need a bundle push their neighbours have no room for** (F12, F15), and **9 are pinned by a component pad** — `FB1`, `C12`, `C40`, `U10` pads 11/24/25/26/81 — which no routing clears (§5) |
| The finding that changes the plan | **The blocker is the 0.6 mm via floor, not the drill.** A 0.40 mm pad on a 0.20 mm drill is a standard mechanical through hole, sits inside the board's **own** `min_via_annular_width 0.10`, and passes the no-HDI gate unchanged (§7) |

**Partial result, as briefed.** 5 executed and verified; 15 blocked with a measured reason, a named item,
and a quantified move. No claim rests on a model that DRC has not corroborated (§2.3).

---

## 1. The 20 groups, measured on the composed board

Read from the board itself (`f01_dump.py`, `f02_groups.py`), not carried over from wave 1: the composed
board has 3 fewer vias and 22 more segments than the board wave-1's relief data was taken from.

`f02_groups.py` output: `work/groups.json`, `work/groups_table.md`, `work/f02_groups.out.txt`.
Distances are **from the group centre to the nearest foreign-net copper EDGE** on each layer, computed
against KiCad's own pad polygons (`TransformShapeToPolygon`), pass 5 µm inscribed.

| # | relief | net | vias | drill/pad | layer span | F.Cu | In1.Cu | In2.Cu | B.Cu | centres inside foreign Cu |
|---|---|---|---|---|---|---|---|---|---|---|
| F16 | G03 | /RP2354B MCU/USB_DP_MCU | 2 | 0.100/0.300 | F→In1, In1→In2 | +0.275 | +0.331 | +1.080 | +1.530 | – |
| F06 | G04 | /LSM_INT1 | 2 | 0.100/0.300 | F→In1, In1→In2 | +0.300 | +0.290 | +0.380 | **−0.089** | B.Cu |
| F01 | G05 | /LSM_INT1 | 1 | 0.100/0.300 | In1→In2 | **−0.225** | +0.375 | +0.375 | +0.211 | F.Cu |
| F04 | G06 | /GNSS_RX | 1 | 0.100/0.300 | F→In1 | +0.275 | +0.301 | +0.099 | +0.314 | – |
| F14 | G07 | /PA_EN | 1 | **0.300/0.600** | In2→B | +0.200 | **−0.075** | +0.459 | +0.483 | In1.Cu |
| F12 | G09 | /PA_EN | 1 | 0.100/0.300 | F→In2 | +0.500 | +0.314 | +0.732 | **0.000** | B.Cu |
| F07 | G10 | /RF_MOSI | 2 | 0.100/0.300 | F→In1, In1→B | +0.355 | +0.355 | +0.300 | +0.355 | – |
| F05 | G11 | /RF_MISO | 2 | 0.100/0.300 | F→In1, In1→In2 | +0.275 | +0.301 | +0.302 | +0.314 | – |
| F02 | G12 | /GNSS_RX | 1 | 0.100/0.300 | In1→In2 | +0.143 | +0.299 | +0.299 | +0.299 | – |
| F08 | G13 | /SENS_SCLK | 1 | 0.100/0.300 | In1→B | +0.311 | +0.308 | +0.311 | +0.311 | – |
| F03 | G14 | /RF_RESET_N | 1 | 0.100/0.300 | F→In1 | +0.320 | +0.320 | +0.193 | +0.320 | – |
| F13 | G15 | /HGM | 1 | 0.100/0.300 | F→In1 | +0.300 | +0.322 | +0.250 | +0.300 | – |
| F09 | G16 | /RF_GPIO2 | 1 | 0.100/0.300 | F→In2 | +0.275 | +0.298 | +0.508 | **−0.086** | B.Cu |
| F10 | G17 | /RF_GPIO0 | 1 | 0.100/0.300 | In2→B | **0.000** | **−0.025** | +0.536 | +0.300 | F.Cu, In1.Cu |
| F15 | G18 | /3V3 | 1 | 0.100/0.300 | F→In1 | +0.302 | +0.278 | **−0.125** | +0.300 | In2.Cu |
| F11 | G19 | /RF_GPIO0 | 1 | 0.100/0.300 | In2→B | **−0.025** | +0.122 | +0.300 | +0.466 | F.Cu |
| F17 | G21 | /RF_MOSI | 1 | 0.100/0.300 | In1→B | **−0.025** | +0.316 | +0.299 | +0.507 | F.Cu |
| F18 | G24 | /RF_GPIO2 | 1 | 0.100/0.300 | F→In1 | +0.375 | +0.290 | +0.625 | +0.715 | – |
| F19 | G25 | /RF_MOSI | 1 | 0.100/0.300 | F→In1 | +0.375 | +0.815 | +0.351 | +0.336 | – |
| F20 | G26 | /915 MHz RF/VDD_CC112 | 1 | 0.100/0.300 | F→In1 | +0.307 | +1.957 | +1.349 | +1.950 | – |

**Reproduced:** 20 groups, 24 vias, 13 nets, 9 groups with a centre inside foreign copper (F06, F01, F14,
F12, F09, F10, F15, F11, F17), 19 groups with a drill below 200 µm (F14 is the 0.300 blind via, still
non-through), 338 vias (0.100×23, 0.300×34, 0.350×281), 338→ non-through 24 (23 microvia, 1 blind).

**Nine of the spans are stacked microvia chains** (F→In1→In2 at one XY, etc.). They are one electrical
path, so they collapse to **one** through via — 24 vias become 20 through vias, not 24.

The binding layer splits **F.Cu 7, In2.Cu 5, In1.Cu 4, B.Cu 4**. Two of the 20 are pinned by a
**component pad** (F01 by `FB1.2 /3V3_ADC`, F02 by `C12.2 /GND`); the other 18 worst-case binders are
*routing*, which is why a fan-out was attempted rather than declared impossible.

---

## 2. The fan-out design — and why it is a re-escape, not a via swap

### 2.1 What a standard via needs

A 0.6 mm pad / 0.3 mm drill through via clears foreign copper by **0.300 + 0.125 = 0.425 mm** from its
centre. A 0.30/0.100 microvia needs **0.275 mm**. The through via is therefore **0.15 mm wider on every
layer, including the two layers the microvia never touched** — that is the whole problem: converting a
F→In1 microvia puts a 0.6 mm disc on In2 and B.Cu as well.

### 2.2 The null fan-out — the obstacle set, measured by KiCad's own engine

Before designing anything I built `work/inplace.kicad_pcb`: every microvia replaced by a 0.6/0.3 through
via **at its own XY**, nothing else changed, pours refilled (`f08_inplace.py`). Connectivity cannot change
(a through via joins the same copper plus the layers between), so the DRC delta is *pure clearance*:

| experiment | violations | unconnected | by type |
|---|---|---|---|
| 0.6/0.3 in place, zones refilled | **188** | 0 | clearance 113, shorting 52, hole 17, mask 6 |
| 0.6/0.3 in place, zones **not** refilled | 245 | 0 | +57 phantom zone hits — the pour gives way on refill, so 245 is wrong |
| 0.4/0.2 in place, zones refilled | **105** | 0 | clearance 72, shorting 24, hole 6, mask 3 |

Every one of the 188 (and 105) maps to exactly one of the 20 groups (`f09_drcan.py`,
`work/drc_violations_by_group.json`, `work/violations40.json`). That table is the item's real product:
it says, per group, **which item** is in the way and **by how many mm**.

> **Board correction to anyone re-running this:** refill the pours before reading the DRC. An unrefilled
> zone reports a via as shorting a pour it never touches, and inflates 188 to 245.

### 2.3 Where a through via can legally stand, and whether the net can reach it

`f05_scan.py` → `f11_param.py` → work/reach_v40.json. For each group, on a 6.0 × 6.0 mm grid at 0.02 mm:

1. **legal site** — the 0.4/0.2 via is clear of every foreign item on **all four layers**, hole-to-hole
   ≥ 0.200 mm, copper-to-edge ≥ 0.500 mm (pours are *not* obstacles: they retract).
2. **reach** — per layer of the span that has same-net copper, a flood fill of the region a 0.2 mm track
   can reach from that layer's anchor, through real clearance (`w/2 + 0.125`). Layers with no same-net
   copper are stack hops and carry no corridor requirement — a bug I had to fix: demanding a corridor on a
   layer with no copper rejects everything (it cost me the first pass, which found 1 group instead of 6).
3. **feasible** — a legal site inside *every* span layer's reach.

Result: **6 of 20 groups have a legal and reachable site at all**; the other 14 have none within 3.0 mm.

**Corroboration.** The model is not taken on trust: the 0.4/0.2 in-place DRC (105 errors) and the model's
own margin agree on *which* groups have zero room, and every executed group was re-checked by
`kicad-cli` afterwards (§4). Where the model and DRC disagree, DRC wins — see F08 in §5.

---

## 3. What was EXECUTED

`f15_select.py` executes only a **nudge** (site ≤ 0.30 mm away and ≥ 0.005 mm clearance margin), because
a longer move is a re-route of a signal through the U1/U40 fan-out, not a via fan-out. `f12_apply.py`
then, per group: deletes the microvia(s) by UUID, adds one standard through via, and adds escape segments
that are **each** checked against the copper model before being added.

| # | net | microvias → | standard via at | move | clearance margin | escape |
|---|---|---|---|---|---|---|
| **F19** | /RF_MOSI | 1 → 1 | (91.560, 62.230) | **0.028 mm** | +0.030 | none needed — lands inside pad U40.7 (F.Cu) and its In1 track |
| **F18** | /RF_GPIO2 | 1 → 1 | (91.660, 60.750) | 0.100 mm | +0.050 | none — inside pad U40.4 and its In1 track |
| **F07** | /RF_MOSI | **2 → 1** | (55.560, 52.560) | 0.072 mm | +0.010 | none — inside both the F.Cu and B.Cu tracks (the In1 hop disappears) |
| **F03** | /RF_RESET_N | 1 → 1 | (53.760, 54.260) | 0.263 mm | +0.080 | F.Cu 0.263 mm, w 0.20, from (53.800, 54.000); slack 0.0948 mm |
| **F20** | /915 MHz RF/VDD_CC112 | 1 → 1 | (95.250, 63.960) | 0.260 mm | +0.074 | In1 0.281 mm, w 0.25, from (95.150, 64.200) |

Totals: **6 microvias removed, 5 standard through vias added, 2 track segments added, 5 groups converted.**
Record: `work/apply_fanout5.json`. The board: `da_main_rev_b_fanout5.kicad_pcb`, full sha256 in §9.

Three of the five land **inside existing same-net copper** — F19/F18 in a QFN land (via-in-pad, which the
0.1 mm microvia already was), F07 in both of its tracks. Those needed no copper at all: only the via moved.

### 3.1 The via size is the decision, and it is a rule decision

Every executed via is **0.40 mm pad / 0.20 mm drill** (annular ring 0.100 mm). That is:

- a **standard mechanical through hole** — the no-HDI gate's own floor is 0.200 mm, unchanged;
- **inside the board's own** `min_via_annular_width = 0.10` (0.4 and 0.2 give exactly 0.100);
- blocked only by `min_via_diameter = 0.60`, a *preference* in the project, not a fab limit.

So the item's completion requires **one rule change in the board's `.kicad_pro`: `min_via_diameter`
0.60 → 0.40**, and **nothing else**. `f13_drc.py` runs both ways so the cost of that rule is isolated
(§4). A 0.6 mm floor is what made "no room anywhere" true; at 0.4 the geometry opens up.

**Fab note (flagged, not resolved here):** a 0.10 mm annular ring is at the tight end of 1 oz 4-layer
capability (published house minimums run 0.10–0.15 mm), and two of the executed vias are via-in-pad —
a 0.20 mm through hole in a QFN land wants plugged/filled vias or it wicks paste. Both are quotes to get,
not design work, and both are cheaper than a respin.

---

## 4. The five numbers, before and after, with one tool

`f13_drc.py work/fanout5.kicad_pcb` → `drc/summary_fanout5.json`. Each state is staged as a copy inside
this directory; `own04`/`gate04` differ from `own`/`gate` only in `min_via_diameter = 0.40`.

| # | metric | before | after | delta |
|---|---|---|---|---|
| 1 | **DRC, board's own rules** | **0** | **5** | +5, **all `via_diameter`** (the 0.4 mm pad vs the 0.6 mm floor) |
| 1b | DRC, own rules with `min_via_diameter 0.40` | 0 | **0** | **0** |
| 2 | **DRC, no-HDI gate** | **23**, all `microvia_drill_out_of_range` | **17**, all `microvia_drill_out_of_range` | **−6** |
| 2b | gate + `min_via_diameter 0.40` | 23 | 17 | −6 (the gate's own question, drill ≥ 0.2 mm) |
| 3 | **unconnected** (kicad-cli `unconnected_items`, and pcbnew `GetUnconnectedCount`) | **0** | **0** | **0** |
| 4 | **via census** | 338 = 0.100×23, 0.300×34, 0.350×281; pads 0.3×23, 0.6×28, 0.7×287; non-through 24 | **337** = 0.100×17, **0.200×5**, 0.300×34, 0.350×281; pads 0.3×17, **0.4×5**, 0.6×28, 0.7×287; non-through **18** | −1 via, −6 microvia |
| 5 | **minimum drill** | **0.100 mm** | **0.100 mm** | unchanged — 17 microvias remain |

`f14_census.py` produced row 4/5 from the boards; `f20_drill.py` cross-checks it in the **Excellon
programs** the fab actually reads (`drill_before/` vs `drill/`):

| | before | after |
|---|---|---|
| 0.100 mm holes (5 blind/buried programs) | **23** | **17** |
| 0.200 mm holes (PTH) | 18 | **23** |
| holes below 0.2 mm | 23 of 366 | **17 of 365** |

**The honest reading of row 5:** the minimum drill did **not** improve. 17 HDI vias remain, so the board
is still not fabricable as an order. What changed is that 5 of 20 groups are *finished* and the remaining
work is enumerated rather than unknown.

---

## 5. The 15 groups that remain, and exactly what would have to give

For each: what a 0.4/0.2 through via in place would break, from **kicad-cli** (`work/violations40.json`),
and the largest annular ring that would fit in place with a 0.2 mm drill
(`ring = worst_dist − 0.125 − 0.10`; the board's own rule is 0.10, so a ring below 0.10 fails).

| # | net | in-place 0.4/0.2 | worst deficit | max ring that fits in place | blockers: movable / pad / via / far-side-blocked |
|---|---|---|---|---|---|
| F16 | /RP2354B MCU/USB_DP_MCU | **1** violation | 0.050 | 0.050 | 1 / 0 / 0 / 0 |
| F17 | /RF_MOSI | 7 | 0.026 | none | 7 / 0 / 0 / 0 |
| F05 | /RF_MISO | 9 | 0.050 | **0.050** | 8 / 0 / 0 / 1 |
| F08 | /SENS_SCLK | 2 | 0.019 | **0.083** | 0 / 0 / 1 / 1 |
| F06 | /LSM_INT1 | 12 | 0.035 | none | 7 / 1 / 0 / 4 |
| F01 | /LSM_INT1 | 6 | 0.200 | none | 2 / 3 / 0 / 1 |
| F04 | /GNSS_RX | 5 | 0.050 | none | 1 / 1 / 0 / 3 |
| F14 | /PA_EN | 3 | 0.100 | none | 0 / 2 / 0 / 1 |
| F02 | /GNSS_RX | 5 | 0.158 | none | 1 / 3 / 1 / 0 |
| F13 | /HGM | 8 | 0.075 | **0.025** | 6 / 1 / 0 / 1 |
| F09 | /RF_GPIO2 | 6 | 0.050 | none | 1 / 1 / 0 / 4 |
| F10 | /RF_GPIO0 | 10 | 0.200 | none | 1 / 4 / 0 / 5 |
| F11 | /RF_GPIO0 | 12 | 0.035 | none | 8 / 2 / 0 / 2 |
| F12 | /PA_EN | 5 | 0.011 | none | 4 / 0 / 0 / 1 |
| F15 | /3V3 | 8 | 0.047 | none | 7 / 0 / 0 / 1 |

Counts are per blocking item from `work/slack40.json`; 15 groups, 105 items: **56 movable, 18 component
pads, 3 other nets' vias, 28 with no room on their far side.** Primary obstacle per group:

| class | groups | count |
|---|---|---|
| **A** every blocker is a movable track | F16, F17 | **2** |
| **B** a sub-rule annular ring would fit in place | F05 (0.050), F08 (0.083) | **2** |
| **C** a component pad is in the way — a part or pad move | F01, F02, F04, F06, F09, F10, F11, F13, F14 | **9** |
| **D** tracks only, but a blocker has no room on its far side | F12, F15 | **2** |

(F13 needs both a pad move *and* a 0.025 mm ring; F05 needs a ring *and* one track has no far-side room.)

### Class A — a local copper push finishes it (2 groups)

`f19_slack2.py` (`work/slack40.json`) shifted every blocking track perpendicular, away from the via,
by exactly the clearance it owes, and re-checked the shifted segment against all other copper.

- **F16** — **one** blocker: `Track [/3V3] on F.Cu, length 5.1628 mm` (the vertical run at x = 61.200),
  needs **+0.050 mm** away from the via. The shifted segment is legal. *Executable by moving one /3V3
  segment, or by pulling the adjacent /3V3 polylines with it.*
- **F17** — **all 7** blockers movable: /VDD_CC112 ×2 (+0.023), /LNA_EN (+0.026), the rest ≤ 0.02.
- **F07** and **F20** were also "all movable" — they were finished by *moving the via* instead, which is
  strictly better (no other net touched).

I did **not** execute F16/F17: translating a segment breaks its joints, so it is a polyline drag of
**another net's** route, not a via edit. Measured and handed over rather than half-done. A router drag
finishes F16 in one gesture.

### Class B — a smaller annular ring (3–4 groups)

- **F05** fits at its own XY with a **0.050 mm ring** (0.30 mm pad / 0.20 mm drill); **F13** with
  **0.025 mm**; **F08** with **0.083 mm**. All three are **below the board's own 0.10 mm annular rule**,
  and 0.025/0.050 are not fabricable at 1 oz in any service found. So class B is only real for F08
  (0.083 mm, marginally inside published house capability) — and F08's alternative is worse: its nearest
  legal *and reachable* 0.4/0.2 site is **2.611 mm away with +0.0014 mm of margin**, a 2.6 mm re-route of
  a sensor clock with no manufacturing margin. **Rejected as not robust** (`f15_select.py` refuses it).

### Class C — a component pad is in the way (9 groups)

`FB1` pad 2 (`/3V3_ADC`, F.Cu, **0.200 mm**), `U10` pad 24 (`/3V3`, 0.200), `U10` pad 25 (`/PA_EN`,
0.100), `U10` pad 81 (`/GND`, 0.100), `C12` pad 2 (`/GND`, 0.158), `C40` pad 2 (`/GND`, 0.035),
`U10` pad 11 (`/GNSS_TX`, 0.025), `U10` pad 26 (`/LNA_EN`, 0.025).

A pad does not move without a **part move**, a pad-shape change, or a footprint re-placement, and every
one of them is inside a 0.4–0.5 mm-pitch land pattern where nothing can shrink. **This is the residue no
routing can clear** — which also means it is the answer to "would a fan-out sweep close this blocker?":
**no, for 9 of the 20 groups.**

### Class D — tracks only, but one has no room on its far side (2 groups)

F12 (`/PA_EN`) needs 4 tracks moved and one of them is already against its neighbour; F15 (`/3V3`) needs
7 and hits the same wall. Moving a track in a 0.5 mm-pitch bundle just pushes the violation to the other
side — the bundle has to shift as a unit, which is the U10 escape field, not a via.

**The most important line in this section:** the blockers are *short stubs (0.05–0.31 mm) inside the
fan-out*, and the deficits are **0.011–0.200 mm**. Six of the 15 (F16, F17, F12, F15, F05, F08) are
therefore genuinely a *routing* job — a bundle push and a re-verify — not a stackup or part decision;
the other 9 are a pad/part problem. Both are cheaper than a respin, and neither is a via edit.

---

## 6. RF void — did the fan-out cost anything?

`f17_void.py`, the definition from `evidence/fab-da-voidfill/20_measure.py` so it is comparable to the
1.2959 % already on the board: RF_50R-class F.Cu track footprints minus the In1 copper union.

| board | RF footprint | void_A (wave-2 def.) | void_B (+ via annuli) |
|---|---|---|---|
| before (`fanout.kicad_pcb`) | 42.4040 mm² | 0.5495 mm² = **1.2959 %** | 0.2550 mm² = 0.6013 % |
| after (`fanout5`) | 42.4040 mm² | 0.5495 mm² = **1.2959 %** | 0.2550 mm² = 0.6013 % |
| **delta** | 0.0000 | **+0.0000 mm² / +0.0000 pp** | +0.0000 |

**No regression — bit-identical.** The before board reproduces the consolidated 1.2959 % and 0.6013 %
exactly, which validates the measurement; the after board is unchanged because the two added segments
(`/RF_RESET_N`, `/915 MHz RF/VDD_CC112`) are **not** RF_50R-class and no new via annulus falls inside an
RF_50R footprint. Adding the 5 vias costs the corridor nothing.

---

## 7. What this changes for the board

1. **5 of 20 groups are closed** and cost the RF void nothing (§3, §6).
2. **The route to closing the rest is not a fan-out sweep, it is a decision plus a fan-out:**
   - **decide the via floor.** 0.40/0.20 (ring 0.10) is inside the board's own annular rule and passes the
     no-HDI gate. Keeping 0.60 is what makes every group look impossible — and it is the *only* rule the
     5 executed groups need changed.
   - **then** F16 (one /3V3 track, +0.050 mm), F17 (seven RF tracks, ≤ 0.026 mm) and F12/F15 (a bundle
     push) are fan-out work on other nets' routing — measurable, bounded, and each verified by the same
     method this item used;
   - **and** the **9 pad-pinned groups** (F01, F02, F04, F06, F09, F10, F11, F13, F14 — `FB1`, `C12`,
     `C40`, `U10` pads 11/24/25/26/81) need a **part or pad move**, which no amount of routing fixes.
     **That is the true residual on this blocker, and it is 9 of 20, not 24 vias.**
3. **The 0.100 mm drills that remain are 17, all microvias.** The board is **not orderable**; the
   no-HDI gate reads 17, down from 23.

---

## 8. Method, files, reproduction

| script | does | output |
|---|---|---|
| `f01_dump.py` | inventory of the composed copy (same schema as wave 1's) | `work/inventory_fanout.json` |
| `f02_groups.py` | the 20 groups + per-layer foreign-copper distances | `work/groups.json`, `groups_table.md` |
| `f05_scan.py` | nearest legal site for 0.6/0.3 and the pad radius that would fit in place | `work/scan.json` |
| `f08_inplace.py` | the null fan-out (all vias replaced in place, pours refilled) | `work/inplace*.kicad_pcb` |
| `f09_drcan.py` | attributes every DRC error to its group | `work/violations40.json`, `drc_violations_by_group.json` |
| `f10_slack.py`, `f19_slack2.py` | is each blocker movable, by how much, in which direction | `work/slack40.json` |
| `f11_param.py` | legal sites + track-reach corridors, per via geometry | `work/reach_v40.json` |
| `f13_drc.py` | the five numbers, 4 rule configurations, on copies | `drc/summary_fanout5.json` |
| `f14_census.py` | via census / min drill / unconnected, one tool | `work/census_*.json` |
| `f15_select.py` | nudge-or-reject selection with the reason recorded | `work/exec_design*.json` |
| `f12_apply.py` | the executed edits, each segment model-checked | `work/apply_fanout5.json` |
| `f17_void.py` | RF void, wave-2 definition | `work/void_*.json` |
| `f20_drill.py` | Excellon programs before/after | `drill_before/`, `drill/` |

`vgeom.py` is copied verbatim from `evidence/fab-da-vias/` (track=capsule, pad=KiCad polygon, via=disc,
zone=not an obstacle, hole-to-hole 0.200, edge 0.500) so the geometry model is the one wave 1 verified.

Reproduce: `python f01_dump.py && python f02_groups.py && python f08_inplace.py work/fanout.kicad_pcb
work/inplace40.kicad_pcb` (with `VIA_PAD=0.4 VIA_DRILL=0.2`) … then `f13_drc.py work/fanout5.kicad_pcb`.

---

## 9. Artefact

`evidence/fab-da-fanout/da_main_rev_b_fanout5.kicad_pcb` — byte-identical to `work/fanout5.kicad_pcb`:

```
sha256 E65F0B2EED47E575AA82397ED662945BE395870C7C6B4E93CA899B9C82A5843A   2,260,448 B
source da_main_rev_b_composed.kicad_pcb sha256 5DBAE23888059E0B6D6F18DC3066924FB8194C5FD4DFA250186D3B024F6F73B6
```

**Verified on the artefact itself**, not only on the working copy — `f13_drc.py da_main_rev_b_fanout5.kicad_pcb
final` reproduces §4 exactly (own 5 / own@0.40 0 / gate 17 / gate@0.40 17 / unconnected 0), and
`f14_census.py` + `f17_void.py` on the artefact give 337 vias, 0.100×17, 0.200×5, non-through 18,
tracks 2303, void 1.2959 %.

It is **not** an orderable board and is not presented as one: it carries 17 remaining microvias.
Two project files ship with it: `da_main_rev_b_fanout5.kicad_pro` (the board's rules as they stand,
which report the 5 `via_diameter` violations) and `da_main_rev_b_fanout5_minvia040.kicad_pro`
(`min_via_diameter 0.40`, which reports **0**).

---

## 10. Limits — what this item does NOT establish

1. **F16/F17 are not executed.** The copper move is measured (§5 class A) but a segment translation must
   be a polyline drag with its joints; doing it by shifting one segment would silently disconnect another
   net, and I will not ship that. **UNVERIFIED as an applied edit.**
2. **The 0.10 mm annular ring and the via-in-pad plugging are fab questions, not engineering answers.**
   No quote was obtained; no fab was contacted. If a house refuses 0.10 mm at 1 oz, the 5 executed groups
   fall back to the 0.15 mm ring the board already has (0.6 mm pad), and their geometry does not allow it
   — i.e. that refusal re-opens all 5.
3. **The 3.0 mm search radius is a scope choice.** A site further than 3.0 mm might exist for some of the
   15; it would be a re-route through the fan-out, not a via fan-out, and was not attempted.
4. **The impedance/RF consequence of re-routing /RF_MOSI, /RF_GPIO0 etc. is not assessed.** The executed
   moves are 0.028–0.263 mm and add 0 mm and 0.281 mm of copper, so no impedance claim is changed; the
   *blocked* re-routes in class A/C would, and are out of this item's scope.
5. **DRC is the board's rules, not a fab's.** `own04` uses `min_via_diameter 0.40`; that rule does not
   exist in the board of record yet. The 5 vias are `via_diameter` violations until it does — stated as
   +5 in §4, not hidden.
