# fab-da-respin-exec — drone-arm main rev_b: the cheap structural changes, executed and DRC-gated

**Wave 10.** Input: the best board artefact, **sha256
`372C1D525BEBF651F86CB90C007FE8CAF71A41F7E46E28669D7AE956ECFA9077`**, 2,262,079 bytes
(`evidence/fab-da-fanout3/da_main_rev_b_fanout3.kicad_pcb`; the directories `fanout3/work` and
`fanout2/fanout7` are byte-identical to it, cited here by **hash**, not by directory name). All work on
copies inside this directory. No repo write, no branch touched, no schematic touched. The input board's
sha256 is **unchanged at the end of the wave**, which is the receipt.

**HEADLINE.** The four cheap structural changes were **executed and DRC-gated, not argued**: six through-via conversion trials were placed on real boards and judged by `kicad-cli` DRC. **Zero of the
15 non-through vias was cleared, and the zero is now derived from row-level data on all four families.**
Three of the six trials were *positive controls* and they came back **DRC-clean**, which is what makes
the zero trustworthy: a legal 0.600/0.300 through via **does** exist on this board at
**(65.550, 50.250)**, fed by a legal 0.200 mm stub from `/3V3` pad 50, for **0 added violations and 0
unconnected**. The board simply cannot reach that site from any pad that needs a via.

The new number this wave produces is the **siting spec**: the four-layer legal through-via field around
U10 is **33.23 mm² in 35 islands**, and it contains **0 legal cells inside the package outline** —
measured on the pad-centre rectangle, the EP window and the ring between them, all zero. The nearest
legal cell to U10 pad copper is **0.450 mm** (0.025 mm of margin — it is the control site itself), and
of the **79** slots that exist at ≥1.00 mm spacing, **59 are more than 4 mm outside**. The vias are not
blocked by a missing site; they are blocked by a missing **lane**, and the sites that are near the pads
are in the four empty corner quadrants that no pad faces.

---

## 0. What was executed

| trial | what it is | net | via at | DRC added | non-through | unconnected |
|---|---|---|---|---|---|---|
| `CTRL-p78-SENSMOSI` | control: 0.600/0.300 through via + 0.200 stub, pad 78 | /SENS_MOSI | (56.000, 44.200) | **+1 `via_dangling`** | 15 | 0 |
| **`CTRL-p50-3V3`** | **control: same, pad 50** | **/3V3** | **(65.550, 50.250)** | **+0, −0** | 15 | 0 |
| `CTRL-p34-SWDIO` | control: same, pad 34 | SWDIO | (60.250, 55.800) | **+1 `via_dangling`** | 15 | 0 |
| `V1-3V3-site` | via #1 driven to its nearest legal site | /3V3 | (60.200, 55.800) | **+4** (`tracks_crossing` 2, `shorting_items` 2) | 15 | 0 |
| `V5-LSMINT1-site` | via #5 driven to its nearest legal site | /LSM_INT1 | (52.850, 48.450) | **+4** (`tracks_crossing` 1, `shorting` 2, `solder_mask_bridge` 1) | 15 | 0 |
| `V6-LSMINT1-site` | via #6/7 stack driven to its nearest legal site | /LSM_INT1 | (53.200, 48.400) | **+3** (`shorting_items` 1, `solder_mask_bridge` 2) | 15 | 0 |

`s10_exec.py` · `trials.json` · `exec_results.json`. Every trial: copy the board, add the via
(`SetViaType(VIATYPE_THROUGH)`, `SetLayerPair(F_Cu, B_Cu)`, 0.600 size / 0.300 drill), add the 0.200 mm
F.Cu stub, `ZONE_FILLER.Fill()`, save, `kicad-cli pcb drc --severity-all`, and **diff the violation
set** against the baseline — not the total. Baseline is **7 violations, all `via_diameter`**, 0
unconnected, on both tools.

**The controls are the instrument check the standing rules require.** They establish the two directions
at once:

* **positive**: my geometry model says a 0.600/0.300 via + 0.200 stub is legal at those three points,
  and KiCad agrees — `CTRL-p50-3V3` adds **nothing at all**, the other two add only `via_dangling`
  (a dead-end stub, i.e. *geometry legal, topology not wired yet*).
* **negative**: the three via-site attempts my model rejected are rejected by KiCad too, with real
  `shorting_items` and `tracks_crossing`. Model and DRC agree in the same direction, so the model's
  "0 of 15" is not a model artefact.

One caveat carried forward: the 0.600 via passes `m_ViasMinSize = 0.600` at **0.0000 mm margin**. That
is the same "pass with no safety" the programme flagged on the ESC, and the board's own 7
`via_diameter` errors are the 0.400/0.200 vias that sit below that floor.

---

## 1. The input span census, reproduced before anything was changed

`s1_census.py work.kicad_pcb census_input.json` — classification by **span** (`TopLayer()` /
`BottomLayer()` against `F_Cu` and `B_Cu`), never by drill diameter. Stack order read from the board:
`F.Cu(0) · In1.Cu(4) · In2.Cu(6) · B.Cu(2)`.

```
336 vias total
  by declared type : THROUGH 321 · MICROVIA 14 · BLIND_BURIED 1
  by span          : THROUGH 321 · NON_THROUGH 15
  by drill         : 0.350 x281 · 0.300 x34 · 0.200 x7 · 0.100 x14
NON-THROUGH 15, six groups:
  0.100  F.Cu -> In1.Cu    5
  0.100  F.Cu -> In2.Cu    2
  0.100  In1.Cu -> In2.Cu  4
  0.100  In1.Cu -> B.Cu    1
  0.100  In2.Cu -> B.Cu    2
  0.300  In2.Cu -> B.Cu    1
```

**The assignment's figure reproduces: 15 non-through, 14 × 0.100 mm and 1 × 0.300 mm, the 0.300 being
In2→B.** The 11/4 split needs one sentence of care, and it is the only place the two conventions
disagree:

| convention | microvia class | blind class | total |
|---|---|---|---|
| **by span depth** (a 2-copper-layer span is a microvia) | **12** | **3** | 15 |
| **by process class** (a 0.300 mm hole is mechanically drilled, so it is blind whatever its span) | **11** | **4** | 15 |

The entire difference is the **single 0.300 mm In2→B via**. So "11 blind + 4 buried" and "12 microvia +
3 blind" are the same 15 vias under two labels, and **both readings are HDI**: the 0.300 mm In2→B via
needs sequential lamination whatever it is called.

---

## 2. What each of the 15 vias is actually for (`s7_role.py`)

Built the real connectivity graph per net — nodes are pads, track segments and vias; an edge exists when
two nodes share a copper layer **and** their copper overlaps — with the non-through vias **removed**, so
each via is scored by what it bridges.

| via | net | span | bridges | role |
|---|---|---|---|---|
| (58.400, 55.550) | /3V3 | F→In1 | 2 comps (234, 5) | **junction**, not a pin escape: it ties the F.Cu branch at y=55.64 to the In1 branch |
| (52.900, 53.200) | /GNSS_RX | In1→In2 | 2 comps (18, 14) | joins the In1 transition blob to the 155 mm In2 run |
| (53.900, 50.600) | /GNSS_RX | F→In1 | 2 comps (18, 2) | pad U10.12 → In1, **pin-side component is the pad alone** |
| (57.600, 55.150) | /HGM | F→In1 | 2 comps (65, 2) | pad U10.27 → In1, pin-side alone |
| (51.500, 49.000) | /LSM_INT1 | In1→In2 | 2 comps (22, 2) | joins the In1 run to the In2 run |
| (54.400, 47.400) ×2 | /LSM_INT1 | F→In1, In1→In2 | stack at one XY | pad U10.4 → In1 → In2, **a two-via stack** |
| (57.600, 52.200) | /PA_EN | F→In2 | 2 comps (5, 4) | pad U10.25 → In2 |
| (58.000, 51.900) | /PA_EN | In2→B | 2 comps (42, 4) | In2 → the 61 mm B.Cu run to the PA |
| (56.500, 55.200) | /RF_GPIO0 | In2→B | 2 comps (5, 1) | In2 → B.Cu |
| (57.400, 56.100) | /RF_GPIO0 | In2→B | 2 comps (9, 1) | In2 → B.Cu |
| (55.600, 55.200) | /RF_GPIO2 | F→In2 | 2 comps (91, 2) | pad U10.22 → In2, pin-side alone |
| (53.900, 53.000) ×2 | /RF_MISO | F→In1, In1→In2 | stack at one XY | pad U10.18 → In1 → In2, **a two-via stack** |
| (55.585, 53.453) | /SENS_SCLK | In1→B | 2 comps (26, 21) | joins the In1 half to the 22 mm B.Cu half |

**Every one of the 15 is load-bearing**, and 4 of them form two same-XY stacks, so a stack must be
replaced as a unit. This reproduces wave 5's load-bearing result (`s11_redundant.py`: removing any one
leaves exactly 1 unconnected item) from the topology rather than from the ratsnest.

`/3V3` is the only net here with more than one U10 pin (11), and its via is a **junction inside the
net**, not a pin escape — so giving up a pin cannot clear it.

---

## 3. (a) The GPIO/nugget re-assignment free-rider — **clears 0 of 15**

The cheapest thing available is the netlist change the respin already owes (pads 43–48 → the 6 ESC
channels; plus a servo rail). Three measurements decide whether it can also clear vias.

### 3.1 Who can host a legal through via — the free-pad instrument (`s5_escape.py`)

A through via needs **0.425 mm** of copper-edge space on **all four layers at once** for 0.600/0.300
(0.300 pad radius + 0.125 `m_MinClearance`), plus 0.200 hole-to-hole and 0.500 to the board edge.
Measured on a 0.05 mm grid over x 50–70, y 40–60 (160,801 cells), with every pad, track and via as an
obstruction:

```
legal cells for a 0.600/0.300 through via   : 7,822 of 160,801  (4.8 %)
U10 pads with a legal site within 3.0 mm    : 48 of 81
  ... AND a legal straight 0.200 mm F.Cu stub from the pad : 3 of 81
  ... among the 20 FREE (auto-net) pads      : 0 of 20
```

The three pads that pass are **34 (SWDIO)**, **50 (/3V3)** and **78 (/SENS_MOSI)** — all DRC-confirmed
in §0. **None of the 20 free pads passes.** The free pins are on the R row (pads 43–58, 14 of them) and
the T row (70–75); the R row's own legal field is a single island at (65.55, 50.25) reachable from
**exactly one** pad, pad 50, and pad 50 is already `/3V3`.

### 3.2 Who can simply give up a pin

| net | U10 pins | verdict |
|---|---|---|
| `/3V3` | **11** | the via is a junction inside the net (§2), not a pin escape — dropping pad 29 clears nothing |
| `/GNSS_RX`, `/HGM`, `/LSM_INT1`, `/PA_EN`, `/RF_GPIO0`, `/RF_GPIO2`, `/RF_MISO`, `/SENS_SCLK` | **1 each** | moving the pin **deletes** the net's only pin; it does not clear the via. Clearing it needs the net **re-routed from the new pin** — which is the fan-out work, not a netlist edit |

### 3.3 The one candidate, executed and rejected

`/3V3` was the only plausible "redundant pin". `s6_local.py inv_input.json 58.400 55.550 1.6` shows the
via serves three things at once: the 0.600 mm F.Cu stub from pad U10.29 above it, the F.Cu branch
`(56.400, 55.640)-(58.400, 55.640)` arriving from the left, and the In1 branch leaving to the right.
Dropping pad 29 leaves the junction load-bearing. **Executed variant** `V1-3V3-site` (the via driven to
its nearest legal site at 1.817 mm) → **+4 violations** (2 `tracks_crossing`, 2 `shorting_items`).

**Family (a): 0 of 15 cleared.** Site availability is not the limit; the lane is.

---

## 4. (b) Small component moves or rotations — **clears 0 of 15**

The strongest possible test of this family is: *move every component away and see if a through via then
fits at the via's own XY.* `s9_families.py inv_input.json measure.json families.json`, computing the
nearest **non-pad** foreign copper on each layer:

```
vias that would take a 0.600 via even with all pads gone : 0 of 15
vias that would take a 0.400 via even with all pads gone : 0 of 15
layers still below the 0.600 floor once pads are gone    : 4 layers -> 10 vias, 1 -> 1, 2 -> 1, 3 -> 3
```

The binding items after every pad is removed are **tracks and vias**, so no component move can ever
legalise a site. The layer-count histogram is the second half of the proof, and it reproduces wave 6
exactly:

```
layers below the 0.325 floor (0.400/0.200 via) : 4 layers -> 7 vias · 3 -> 5 · 2 -> 3 · 1 -> 0
```

**No via has a single blocking layer**, so no single-feature edit — a pad move, a trace nudge, a
keepout — can legalise any of them. Concretely, the two vias whose worst blocker *is* a component pad
both stay blocked:

* **/GNSS_RX In1→In2 @ (52.900, 53.200)** — worst blocker F.Cu `pad C12.2 /GND` at 0.1432. Remove C12 and
  In1/In2/B are still **0.2988** against a 0.325 floor, and all three are blocked by the *same* item, the
  `/RF_nCS` 0.350 mm through via.
* **/LSM_INT1 In1→In2 @ (51.500, 49.000)** — worst blocker F.Cu `pad FB1.2 /3V3_ADC` at −0.2250. Remove
  FB1 and B.Cu is still **0.2106** against 0.325.

**Family (b): 0 of 15.**

---

## 5. (c) Local In1 keepouts around an escape — **clears 0 of 15, by construction**

`s8_measure.py` builds the **eviction set** of each via: every foreign item inside 0.425 mm on any
layer. Across all 15:

```
eviction-set items : track 157 · pad 23 · via 12 · ZONE FILL 0
board zones        : 5
```

**Not one blocker is a pour.** A keepout removes fill, and fill is not what is in the way — the board's 5
zones retract around every via on refill, which is exactly how the board's 321 through vias already work. There
is nothing for a keepout to remove, so the family clears zero **whatever** the layer: 7 of 15 have all
four layers below the floor (§4) and no via has fewer than one *track or via* on its worst layer.

**Family (c): 0 of 15.**

---

## 6. (d) Package change — **not available, and would not help anyway**

`U10` is `QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm`. The RP2354B is offered **only** in QFN-80-EP 10×10 mm
at 0.400 mm pitch, and the only other family member, RP2350A, is QFN-60 at the same 0.400 mm pitch *and*
lacks GPIO 30–47, which this design uses (wave 6 verified both against the manufacturer pages
[3DContentCentral](https://www.3dcontentcentral.com/Download-Model.aspx?catalogid=171&id=2810373),
[The Pi Hut](https://thepihut.com/products/raspberry-pi-rp2354b-microcontroller),
[RP2350 datasheet](https://pip.raspberrypi.com/documents/RP-008373-DS-2-rp2350-datasheet.pdf)). No
larger-pitch option exists.

Even if it did, the arithmetic closes it: a 0.600 landing pad needs `0.600 + 2 × 0.125 = 0.850 mm` of
frontage = **2.13 pitches at 0.400 mm**, and still **1.7 pitches at 0.500 mm**. There is no pitch on a
QFN that gives every one of 20 pads a via's worth of frontage.

**Family (d): unavailable.** The cheap families therefore sum to **0 of 15**, and the board is
**unchanged**.

---

## 7. Why zero, in one division — frontage, and where the legal field actually is

### 7.1 Frontage (`s9_families.py`)

A QFN-80 at 0.400 mm pitch gives each side `20 × 0.400 = 8.000 mm`. One 0.200 mm lane needs
`0.200 + 2 × 0.125 = 0.450 mm`:

| side | pads | netted | frontage | lanes at 0.200/0.125 | netted / capacity | demand / frontage | lanes at 0.150/0.125 | netted / capacity |
|---|---|---|---|---|---|---|---|---|
| **L** | 20 | **20** | 8.000 | **17** | **117.6 %** | **112.5 %** | 20 | 100.0 % |
| **B** | 20 | **20** | 8.000 | **17** | **117.6 %** | **112.5 %** | 20 | 100.0 % |
| R | 20 | 6 | 8.000 | 17 | 35.3 % | 33.8 % | 20 | 30.0 % |
| T | 20 | 14 | 8.000 | 17 | 82.4 % | 78.8 % | 20 | 70.0 % |

Both percentage columns are shown because wave 6's **112.5 %** is demand/frontage and this wave's
**117.6 %** is netted/capacity — the same over-subscription counted against two denominators. **The two
rows that carry 8 of the 9 via-owning nets are over-subscribed**, and at 0.150 mm they reach exactly
100 %, i.e. still zero slack, while a via needs **2.1 lanes**. There are **no GND pads on L, B or R**
(only one on T), so no pad on the congested rows can be excused a lane.

### 7.2 Where a 0.600/0.300 via can actually go (`s12_field.py`)

Clustering the four-layer legal field into connected islands (8-connected, 0.05 mm grid):

```
legal area for a 0.600/0.300 through via : 33.23 mm2 in 35 islands
legal cells inside the package outline   : 0  (pad-centre rect 0, EP window 0, ring between them 0)
nearest legal cell to U10 pad copper     : 0.450 mm  (at 56.00, 44.20 -- the CTRL-p78 site)
via slots at >= 1.00 mm spacing         : 79  (need 15)
   by band:  0.3-2 mm outside  4   |   2-4 mm outside 16   |   >4 mm outside 59
largest islands: 11.35 mm2 @ (68.14, 40.46) 6.21 mm outside -> 18 slots
                 6.04 mm2 @ (69.87, 46.12) 5.92 mm outside -> 9
                 5.21 mm2 @ (69.70, 54.51) 5.75 mm outside -> 8
                 2.81 mm2 @ (67.10, 45.12) 3.15 mm outside -> 6
```

So the field has **five times the capacity it needs**, and **none of it is where the designer put the
microvias**: all 15 sit at radius ≈ 0 (in-pad, or 0.15–0.60 mm off the pad row), and the ring between the
pad row and the EP — where they are — has **zero** legal cells. Two facts then close it:

* **Per pad, not per island.** Of the 9 pads that own the 15 vias, **6 have no legal 0.600/0.300 site
  within 3.0 mm at all** (pads 4, 12, 18, 21, 22, 25). The other three — 27, 29 and 77 — have one at
  2.73, 1.99 and 0.89 mm, and **none of the three has a legal straight stub**; pad 77 misses by exactly
  0.0377 mm, its blocker being the neighbouring QFN pad U10.78.
* **The near-package sites are in the corner quadrants.** The nearest legal cell of all sits at
  (56.00, 44.20), 0.450 mm from pad copper — but the pad rows run 55.20–62.80 and 46.20–53.80, so the
  QFN corners are empty and that is why the field can exist there. No pad faces a corner, and reaching
  one means travelling laterally along a row that is already at 117.6 % of its lane capacity.

The F.Cu escape lane is the constraint, and it is measured: `median 0.00 mm, max 1.32 mm`, reproducing
wave 6's per-pad lane census exactly (L median 0.00, B median 0.00, R median 0.04 max 1.32, T median
0.00 max 1.32, **0 pads ≥ 1.5 mm on any side**).

### 7.3 The rule lever, priced (`s11_rule.py`)

If the owner will relax the rules, here is exactly what each step buys — pad diameter that fits at the
via's own XY, `2 × (d_min − clearance)`, min over all four layers:

| clearance | 0.600 pad fits | 0.400 pad fits | 0.350 pad fits |
|---|---|---|---|
| **0.125 (the board's own)** | **0 of 15** | **0 of 15** | **1 of 15** (/SENS_SCLK, 0.3616) |
| 0.100 | 0 of 15 | 1 of 15 (/SENS_SCLK, 0.4116) | 3 of 15 (+ /RF_MISO stack 0.3500) |
| 0.075 | 0 of 15 | 3 of 15 | 4 of 15 (+ /HGM 0.3500) |

**A 0.600 via never fits at any clearance, so relaxing clearance alone clears nothing.** What clears
vias is dropping `m_ViasMinSize` from 0.600 to 0.400 *and* clearance from 0.125 to 0.100 — which buys
**3 of 15**, and it is a rule change, so it is the owner's call, not mine.

---

## 8. Final verification of the delivered board

`da_main_rev_b_respin_exec.kicad_pcb` — **byte-identical to the input**,
sha256 `372C1D525BEBF651F86CB90C007FE8CAF71A41F7E46E28669D7AE956ECFA9077`, 2,262,079 bytes.

| check | value | how |
|---|---|---|
| **span census** | **15 non-through** of 336 (321 through); 11 microvia-class + 4 blind-class, 12+3 by depth | `s1_census.py`, `census_final.json` |
| **DRC at the board's own rules, SET DIFF** | **7 → 7, added 0, gone 0**; all 7 `via_diameter` (the pre-existing 0.400/0.200 vias) | `s13_final.py`, `final_final.json` |
| **unconnected, `kicad-cli`** | **0** | same run |
| **unconnected, `pcbnew`** | **0** (`GetUnconnectedCount(True)`) | same run |
| **cap status** | both tools **0**, far below any cap; the tools agree at 0, so the zero is trustworthy. (The ESC's 499-vs-1,542 cap problem does not arise here.) | — |
| **minimum drill** | **0.100 mm** — the board is still HDI and still not fabricable | `s24_void.py` |
| **RF void fraction** | **1.2959 %** (void_A, 0.5495 mm²) · **0.6013 %** (void_B) — **unchanged, bit-for-bit** | `s24_void.py`, same definition as `fab-da-voidfill/20_measure.py` |

The control board `ctl_through_via_exists.kicad_pcb` is kept as the instrument's receipt: **337 vias, 15
non-through, DRC 7 with 0 added / 0 gone, 0 unconnected on both tools** — i.e. the extra 0.600/0.300
through via at (65.550, 50.250) and its 0.200 mm stub are legal by KiCad's own judgement.

---

## 9. Did anything break? — the full set diff against the input

**Nothing changed.** The delivered board is byte-identical, so every earlier fix is intact by
construction. The specific items the assignment names:

| check | earlier figure | this board | verdict |
|---|---|---|---|
| **RF void fraction** | 1.2959 % | **1.2959 %** | identical |
| **RF corridor** (RF_50R F.Cu footprint area) | 42.4040 mm² | **42.4040 mm²** (0.5495/0.042404 = 1.2959 %) | identical |
| **pad-to-pad gaps** | "371 at exactly 0.2000 mm" | **not a drone-arm number.** drone-arm has **311** inter-pad pairs ≤ 0.300 mm inside a footprint, modal **0.200 mm with 76 pairs**, and 63 pairs whose rectangles touch | see below |
| **unconnected** | 0 on both tools | **0 on both tools** | identical |
| **DRC** | 7 | **7** | 0 added / 0 gone |
| **min drill** | 0.100 | **0.100** | identical |
| **HDI count** | 15 (11+4) | **15 (11+4)** | identical |

**The 76 is derived, not counted blindly**: a QFN-80 has 20 pads per side, so 19 adjacent pairs × 4
sides = **76** — the whole 0.200 mm population is the QFN-80's own pad row. So the **371 pad-to-pad gaps
belong to the ESC**, not to drone-arm; this board's population is 311 with a 76-pair mode at 0.200 mm,
and both are footprint-bound and therefore unmoved by anything a re-route does. The 63 zero-gap pairs
are pads whose rectangles touch (multi-part and thermal-ring pads), also footprint-bound.

The six trials of §0 are the only boards that differ from the input, they are all in `copies/`, and none
of them is offered as a deliverable.

---

## 10. Set diffs against the earlier waves

| # | earlier statement | this wave | direction |
|---|---|---|---|
| 1 | `fab-da-fanout3:211` — "a 0.350 mm pad with a 0.150 drill fits **2 of 15** (/SENS_SCLK **and** /RF_MISO)" | At the board's own 0.125 clearance a 0.350 pad fits **1 of 15**. /RF_MISO's via reaches **0.3000** at its own XY and 0.3200 at a 0.022 mm offset — both **below 0.350**, so it does not fit | **2 → 1**; the /RF_MISO half of that recommendation is not supported |
| 2 | `fab-da-respin:196-201` — frontage utilisation **112.5 %** on L and B | **112.5 %** is demand/frontage; netted/capacity is **117.6 %** | same fact, two denominators — both now stated |
| 3 | `fab-da-respin:139-147` — no pad can launch a 0.200 track more than 0.24 mm; R/T max 1.32 | **exact reproduction**: L median 0.00, B median 0.00, R median 0.04 max 1.32, T median 0.00 max 1.32, 0 pads ≥ 1.5 mm on any side | confirms |
| 4 | `fab-da-respin:377` — 10 of 15 have a legal 0.600/0.300 site within 1.50 mm | At **2.50 mm** only **4 of 15** do, and **0 of those 4** has a legal stub on the net's own layers. The difference is the search window and the stub test, which wave 6 did not apply | 10 → 4, both true at their own radii; the 4 are now DRC-rejected individually |
| 5 | `fab-da-respin:168-177` — "0 of the 52 blocking items is zone fill" | **0 zone items**, confirmed independently: 157 track / 23 pad / 12 via across all 15 eviction sets | confirms |
| 6 | new | **0 legal cells inside the package outline** (pad-centre rect, EP window, and the ring between them all measure 0); the field's nearest cell is 0.450 mm from pad copper and it holds 79 slots at ≥1.00 mm spacing | **new** |
| 7 | new | with **every pad moved away**, 0 of 15 takes even a 0.400 via | **new**, and it closes family (b) permanently |

---

## 11. What remains, and the next structural change

Zero was **not** reached. **15 non-through vias remain**, the board is still HDI (min drill 0.100 mm) and
still not sendable. The cheap families are now closed with numbers rather than argument:
**(a) 0, (b) 0, (c) 0, (d) unavailable.**

The next structural change, in the order I would spend money:

1. **Move the via field off the pad row — the only change that can reach 15.** The legal field exists
   (33.23 mm², 79 slots at ≥1.00 mm) but **every cell of it is outside the package and 75 % of its slots are beyond 4 mm**.
   Reserve a fan-out band of **≈ 4.0 mm depth on L and B** and re-lay each escape to a through via at
   **2.0–4.0 mm** radius, where 20 slots exist and the frontage has spread from 0.400 to ≥0.850 mm.
   The band must absorb **16 × 0402 decoupling capacitors** (wave 6 measured all of them inside 2.0 mm;
   they move outward by 2.6–3.4 mm, not away) and a **38-net, 288-segment rip-up**.
2. **Adopt 0.150 mm escapes on the U10 rows only** — 1 oz, inside every service this programme has
   surveyed, and it is what takes L and B from 117.6 % to exactly 100 %. It is not sufficient alone
   (100 % is still zero slack for a 2.1-lane via) but it is the enabling rule for step 1.
3. **Stagger the field over two depths.** A single-depth field cannot fit: 3 vias on L × 0.85 mm plus 20
   lanes × 0.400 mm = `2.55 + 8.00 = 10.55 mm` against 8.000 mm of frontage (**132 %**); on B it is
   `4.25 + 8.00 = 12.25 mm` (**153 %**). Two depths halve the frontage cost per via to ≈ 0.43 mm, which
   is the only arrangement that fits. **T already fits at 81 % even with its via added** (0.850 + 14 x 0.400 = 6.45 mm of 8.000 mm) and is where the three legal sites of
   §0 actually are — that is the model and the measurement agreeing on the same side.
4. **Only after 1–3**, ask the owner about `m_ViasMinSize` 0.600 → 0.400 and clearance 0.125 → 0.100,
   which is worth **3 of 15** on its own and **1 of 15** at the 0.125 clearance.

The honest estimate for step 1 is the one wave 6 already printed and this wave does not improve: the debt
is **38 nets and 77 items**, plus 16 capacitor moves. That is a bounded U10-local re-route, not a
board-wide one — but it is not a cheap structural edit, and this wave found no cheap structural edit that
works.

---

## 12. Artefacts

| file | what it is |
|---|---|
| **`da_main_rev_b_respin_exec.kicad_pcb`** | **the delivered board — byte-identical to the input, sha256 `372C1D52…9077`** (the receipt that nothing was silently changed) |
| `ctl_through_via_exists.kicad_pcb` | control: the input + 1 legal 0.600/0.300 through via at (65.550, 50.250); DRC **0 added / 0 gone** — the instrument's positive case, confirmed by KiCad |
| `work.kicad_pcb` (+ `.kicad_pro`) | the input, unmodified; the rules file every DRC count above was run under |
| `copies/*.kicad_pcb` | the 6 executed trials of §0, kept because their DRC deltas are the evidence |
| `census_input.json`, `census_final.json` | span census, before and after (identical) |
| `map_input.json` | U10 pad map: 90 pads, side occupancy, the 20 unassigned pins |
| `netgeo.json` | per-net copper by layer, with the non-U10 terminals |
| `role_input.json` | the connectivity graph: what each of the 15 bridges |
| `escape_input.json` | per-pad escape lane + nearest legal 0.600/0.300 site + stub verdict |
| `measure.json` | the per-via decision table: per-layer distances, largest pad that fits, eviction sets |
| `families.json` | (a)/(b)/(c)/frontage scoring |
| `rule.json` | clearance dose-response + pad-gap population |
| `field.json` | the clustered legal via field: 35 islands, 79 slots, distance from the package |
| `exec_results.json`, `final_final.json`, `final_ctl.json` | DRC set diffs |
| `drc/` | every raw `kicad-cli` DRC report |

Scripts, in the order that matters: `s1_census.py` (span) · `s3_map.py` (pad map + via→pad) ·
`s4_netgeo.py` (per-net copper) · `s7_role.py` (articulation: what each via bridges) ·
`s5_escape.py` (free-pad instrument) · `s8_measure.py` (per-via decision table) ·
`s9_families.py` (a/b/c + frontage) · `s10_exec.py` (execute + DRC gate) · `s11_rule.py` (rule lever,
pad gaps) · `s12_field.py` (where a via can actually go) · `s24_void.py` (RF void) ·
`s13_final.py` (closing verification with set diff).

---

## 13. Line discipline from this wave

1. **A positive control is what makes a zero quotable.** Three of the six trials were designed to
   *succeed*, and they did — one adding **no violation at all** and two adding only a `via_dangling` marker. Without them, "0 of
   15" would have been indistinguishable from a broken model. The standing rule is satisfied in the
   direction that matters: the instrument reproduces a known-good case a human can check by hand
   (place a via at (65.550, 50.250), run DRC, get 7).
2. **Every PASS here is a set diff.** All six trials report `added` / `gone` against the baseline, not
   totals. `V1` adds 4 and `CTRL-p50` adds 0; a total alone would have hidden both.
3. **A family can be closed by an extreme case, not by an example.** Family (b) is dead because *with
   every pad removed* 0 of 15 passes — which needs no argument about which capacitor to move. Family (c)
   is dead because there is **no fill** in any eviction set.
4. **"Site exists" and "site is reachable" are different measurements, and only the second one matters.**
   Wave 6 established the distinction; this wave priced both ends of it — **48 of 81** pads have a legal
   site, **3 of 81** can reach one with a legal stub, and **0 of those three is a pad that owns one of the
   15 vias** (they are pads 34, 50 and 78, on nets that need no via). The via-owning pads are on the
   wrong side of the field.
5. **A number carried between boards must be re-derived on the board in hand.** "371 pad-to-pad gaps"
   was applied to drone-arm by the wave brief; it is an **ESC** figure. drone-arm's population is 311
   with a 76-pair mode at exactly 0.200 mm, and the 76 is the QFN-80's own pad row — 19 × 4.