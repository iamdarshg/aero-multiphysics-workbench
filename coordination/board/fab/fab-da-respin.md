# fab-da-respin — drone-arm main rev_b: the structural change that clears the last 15

**Wave 6, drone-arm fan-out.** Input `evidence/fab-da-fanout3/da_main_rev_b_fanout3.kicad_pcb`
(sha256 `372C1D525BEBF651F86CB90C007FE8CAF71A41F7E46E28669D7AE956ECFA9077`, 2,262,079 bytes —
byte-identical to `fanout7`). Every number below is produced by a script in this directory; the
script is named beside the table. No repo write, no branch touched, no schematic touched. The input
board's sha256 is **unchanged at the end of the wave**, which is the receipt.

**HEADLINE.** The previous wave's "0 of 15 has a legal through-via site" is a **search-radius
artefact**. At ±1.50 mm instead of ±0.50 mm, **10 of 15 do have a legal 0.600/0.300 site** — and DRC
still keeps **0 of 10**, because what is missing is not the site, it is the **escape lane**. The
obstruction is **U10's own fan-out**: **51 of the 52 distinct blocking items belong to nets on U10's
own pads**, and the two rows that carry the 15 (left and bottom) are **112.5 % over-subscribed** at
the board's own track and clearance rules. That is a property of a 0.40 mm-pitch QFN-80, not of the
routing, so no local edit can reach it — and the fix is one netlist-neutral change.

---

## 0. What was executed

| artefact | what it is | non-through | DRC (board's own rules) | unconnected |
|---|---|---|---|---|
| `work.kicad_pcb` | the input, unmodified | **15** | **7** (all `via_diameter`) | **0** (both tools) |
| `converted.kicad_pcb` | the DRC gate's best attempt, all 10 candidates dropped | **15** | **7** | **0** |
| **`respin_canvas_v3.kicad_pcb`** | the structural change executed as far as pcbnew can take it | **0** | 139 | 77 (both tools agree) |

`converted.kicad_pcb` is byte-identical to `work.kicad_pcb` (`sha256 372C1D52…9077` on both): the
gate kept nothing, so nothing was shipped. `respin_canvas_v3` is a **CANVAS, not a deliverable** —
§5 says exactly why and what its 139 violations are.

Verification used `s16_verify.py` (kicad-cli DRC + the pcbnew ratsnest, both, every time):

```
before        vias 336  non-through  15  |  kicad-cli DRC   7  unconnected  0  |  pcbnew 0
canvas_v3     vias 321  non-through   0  |  kicad-cli DRC 139  unconnected 77  |  pcbnew 77
```

---

## 1. What specifically blocks each of the 15, by layer

`s5_blockers.py inv_before.json blockers.json`

A through via on this board needs, on **all four** copper layers at once:
**0.325 mm** of edge-to-edge space for a 0.400/0.200 via (0.325 = 0.200 pad radius + 0.125
`m_MinClearance`), or **0.425 mm** for a 0.600/0.300 via. The board's own rules are internally
inconsistent — `m_ViasMinSize` is **0.600** and its 7 pre-existing 0.400 vias are the board's own 7
DRC errors — so **both floors are reported**.

| # | net | span | F.Cu | In1 | In2 | B.Cu | layers below 0.325 | worst layer / item |
|---|---|---|---|---|---|---|---|---|
| 1 | /3V3 | F→In1 | 0.302 | 0.278 | **−0.125** | 0.300 | 4 | **In2** trk /LNA_EN w0.25 |
| 2 | /GNSS_RX | F→In1 | 0.275 | 0.302 | **0.099** | 0.314 | 4 | **In2** trk /USB_DM_MCU w0.25 |
| 3 | /GNSS_RX | In1→In2 | **0.143** | 0.299 | 0.299 | 0.299 | 4 | **F** pad C12.2 /GND |
| 4 | /HGM | F→In1 | 0.300 | 0.322 | **0.250** | 0.300 | 4 | **In2** trk /RF_MISO w0.20 |
| 5 | /LSM_INT1 | F→In1 | 0.300 | 0.291 | 0.380 | **−0.089** | 3 | **B** trk /ICM_nCS w0.25 |
| 6 | /LSM_INT1 | In1→In2 | **−0.225** | 0.375 | 0.375 | 0.211 | 2 | **F** pad FB1.2 /3V3_ADC |
| 7 | /LSM_INT1 | In1→In2 | 0.300 | 0.291 | 0.380 | **−0.089** | 3 | **B** trk /ICM_nCS w0.25 |
| 8 | /PA_EN | F→In2 | 0.500 | 0.314 | 0.732 | **0.000** | 2 | **B** trk /RF_GPIO2 w0.20 |
| 9 | /PA_EN | In2→B | 0.200 | **−0.075** | 0.459 | 0.483 | 2 | **In1** trk /XIN w0.25 |
| 10 | /RF_GPIO0 | In2→B | 0.000 | **−0.025** | 0.536 | 0.300 | 3 | **In1** trk /SENS_MOSI w0.25 |
| 11 | /RF_GPIO0 | In2→B | **−0.025** | 0.122 | 0.300 | 0.466 | 3 | **F** trk /1V1 w0.25 |
| 12 | /RF_GPIO2 | F→In2 | 0.275 | 0.298 | 0.508 | **−0.087** | 3 | **B** trk /SENS_SCLK w0.20 |
| 13 | /RF_MISO | F→In1 | **0.275** | 0.302 | 0.302 | 0.314 | 4 | **F** trk /RF_nCS w0.25 |
| 14 | /RF_MISO | In1→In2 | **0.275** | 0.302 | 0.302 | 0.314 | 4 | **F** trk /RF_nCS w0.25 |
| 15 | /SENS_SCLK | In1→B | 0.306 | 0.306 | 0.306 | **0.306** | 4 | **B** via /RF_GPIO0 350µm |

A **negative** distance is not an error: it means the foreign copper is **over the point**. Ten of
15 are in that state on at least one layer.

### The number that decides everything

```
layers below the 0.325 floor per via :  4 layers → 7 vias,  3 layers → 5,  2 layers → 3
vias with exactly ONE blocking layer  :  0 of 15
worst layer sits on F or B (outer)     :  10 of 15   (F 5, B 5)
worst layer sits on In1 or In2 (inner) :   5 of 15   (In2 3, In1 2)
worst blocking item is a track         :  12   pad 2   via 1   zone fill 0
```

**No via has a single blocking layer.** Every one needs at least two items displaced at once, and
seven need four. This is the measurement that closes the "just nudge the blocking feature" family
before any geometry is attempted.

---

## 2. The 15 grouped by obstruction type

`s6_evict.py` (exact eviction set per via — every foreign item inside 0.325 mm on every layer),
`s9_ownership.py` (who owns those items).

| group | vias | what blocks it | layer | the blocking item is |
|---|---|---|---|---|
| **A — U10's own fan-out crossing on an INNER layer** | 1, 2, 4 (In2) · 9, 10 (In1) | **5** | In1 / In2 | a load-bearing 0.25 mm signal track of another U10 net |
| **B — U10's own fan-out crossing on an OUTER layer** | 5, 7, 8, 12 (B) · 11, 13, 14 (F) | **7** | F / B | same, on the outer film |
| **C — a passive's pad sitting on the point** | 3 (C12.2 /GND), 6 (FB1.2 /3V3_ADC) | **2** | F | a 0402 capacitor pad / a 0603 ferrite pad |
| **D — another net's existing through via** | 15 (/RF_GPIO0 350 µm at 0.306) | **1** | B | a 0.35 mm through via belonging to /RF_GPIO0 |

5 + 7 + 2 + 1 = 15. Outer-layer-limited = B(7) + C(2) + D(1) = **10**; inner-layer-limited = A = **5**
— which matches the "outer 10 / inner 5" line in §1 exactly, from an independent computation.

### Ownership: the obstruction is U10's own fan-out

```
distinct blocking items                                 52
  belonging to nets on U10's own pads                   51
  belonging to any other net                             1   (/RP2354B MCU/MAIN_LED_A on In1)
vias whose ENTIRE eviction set is U10's own fan-out       7   (#3, 4, 6, 10, 11, 12, 15)
```

So the blockers are not "foreign circuitry" that could be persuaded to move aside. They are **the
design's own escape copper**, routed at exactly the 0.125 mm floor, in front of the part that owns
the vias.

---

## 3. Why the cheap structural changes clear nothing

Each option was measured, not argued.

### (a) Move the blocking component or its pad → **clears 0 of 15**

From §1 there is no via with a single blocking layer, so removing one item cannot legalise any site.
Made concrete for the only two vias whose worst blocker *is* a component pad:

* **#3 /GNSS_RX** — remove C12 and the site is still blocked on **all three** other layers
  (In1 0.2988, In2 0.2988, B 0.2988, all below 0.325). Also inside the eviction set: a /RF_nCS
  through via on all four layers.
* **#6 /LSM_INT1** — remove FB1 and B.Cu is still 0.2106 against a 0.325 floor, with /VREG_AVDD
  and two /3V3_ADC track segments still inside.

`evidence/fab-da-fanout3/REPORT.md:207` reached the same conclusion for the "two nets that would
have to swap layers". **A pad move buys nothing because the pad is never the only blocker.**

### (b) Re-assign which GPIO each net lands on → **clears 0 in place; enables all 15**

Measured two ways.

*In place* (swap net names between U10 pads, keep the copper): **0**. `s4_field.py` walked all 81
U10 pads in four axis directions looking for a 0.200 mm legal escape lane:

```
side L  n=20  min 0.00  median 0.00  max 0.00   >=1.5mm: 0
side B  n=20  min 0.00  median 0.00  max 0.00   >=1.5mm: 0
side R  n=20  min 0.00  median 0.04  max 1.32   >=1.5mm: 0
side T  n=20  min 0.00  median 0.00  max 1.32   >=1.5mm: 0
```

**Not one of the 81 pads can launch a 0.200 mm track more than 0.24 mm** out of the pad row. The
board's best pad manages 1.32 mm. Relocating a net to another pad therefore cannot produce a legal
through via, because *no* pad has a lane.

*As design freedom* (after a re-fan-out): the same nine nets go from **1 of 9 reachable to 9 of 9**
— see §4. So the remap is not a fix; it is the degree of freedom that makes the fix possible.

### (c) Change the package to a larger pitch → **clears 0 of 15; not available**

U10 is `QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm`. The RP2354B exists **only** in QFN-80-EP 10×10 mm
at **0.40 mm pitch** ([3DContentCentral](https://www.3dcontentcentral.com/Download-Model.aspx?catalogid=171&id=2810373),
[The Pi Hut](https://thepihut.com/products/raspberry-pi-rp2354b-microcontroller)), and the only
other family member, RP2350A, is QFN-60 — also 0.40 mm, and it lacks GPIO 30–47, which this design
uses ([RP2350 datasheet](https://pip.raspberrypi.com/documents/RP-008373-DS-2-rp2350-datasheet.pdf)).
There is no larger-pitch option for this MCU.

Even if there were, it would not solve this: a 0.600 through-via landing pad needs **0.850 mm of
frontage = 2.13 pitches** at 0.40 mm, and would still need 1.7 pitches at 0.50 mm.

### (d) In1 plane priority, or a local In1 keepout → **clears 0 of 15**

Two independent measurements:

1. **0 of the 52 blocking items is zone fill.** Every one is a track, a pad or a via. A keepout
   removes copper the nets need; it cannot remove a load-bearing track.
2. Of the 5 inner-limited vias, **2 are limited on In1 and 3 on In2**, and all 5 have at least one
   *outer* layer below the floor as well (In1 0.291–0.314, B −0.089 … 0.300). Clearing In1 alone
   legalises nothing.

### The sum of the cheap options is zero

(a) 0, (b) 0 in place, (c) unavailable, (d) 0. The previous wave reached the same end point from a
different direction (`fab-da-fanout3/REPORT.md:199-218`); this wave shows it is **structural**, not
geometric luck.

---

## 4. The minimum structural change that clears all 15

### 4.1 The real constraint is frontage, and it is measurable

`s9_ownership.py`, `s7_band.py`. A QFN-80 at 0.40 mm pitch gives each side **20 pads × 0.400 mm =
8.000 mm** of frontage. One 0.200 mm lane needs `0.200 + 2 × 0.125 = 0.450 mm`. So a side holds
**17 lanes for 20 pads = 112.5 %** — before a single via is placed:

| side | pads | netted | frontage | capacity | demand | utilisation | after the 6 ESC nets land here |
|---|---|---|---|---|---|---|---|
| **L** | 20 | **20** | 8.000 | 17 | 9.000 | **112.5 %** | 112.5 % |
| **B** | 20 | **20** | 8.000 | 17 | 9.000 | **112.5 %** | 112.5 % |
| R | 20 | 6 | 8.000 | 17 | 2.700 | 33.8 % | **67.5 %** |
| T | 20 | 14 | 8.000 | 17 | 6.300 | 78.8 % | 78.8 % |

**The left and bottom rows — the two rows that carry all 15 vias — are over-subscribed by 12.5 %.**
That is a property of 0.40 mm pitch versus 0.450 mm lane width. It is why the designer used
via-in-pad microvias, and it is the reason the fan-out is drawn at zero slack.

A through-via landing pad needs `0.600 + 2 × 0.125 = 0.850 mm = 1.89 lanes`. **A via field cannot
exist in front of a row that is over-subscribed by even one lane.**

Lane width is the only free variable:

| rule | lane | lanes in 8.000 mm | 20 pads at |
|---|---|---|---|
| 0.200 / 0.125 (today) | 0.450 | 17 | **112.5 %** |
| **0.150 / 0.125** | **0.400** | **20** | **100 %** |
| 0.200 / 0.100 | 0.400 | 20 | 100 % |
| **0.150 / 0.100** | **0.350** | **22** | **91 %** |
| 0.100 / 0.100 | 0.300 | 26 | 77 % |

### 4.2 The change, and the dose-response that proves it is sufficient

**One change: reserve a fan-out band around U10 and re-lay its escapes at 0.150 mm into a staggered
through-via field.** Netlist-neutral — no schematic change is required for it.

`s7_band.py` measured how many of the 15 can host a legal through via as the band is opened, with
each via held at its **original** XY (so this is a lower bound; a re-lay may move the via too):

| band depth | level 1 (only other nets displaced) | level 2 (U10's own fan-out re-drawn) |
|---|---|---|
| 0.00 mm (as drawn) | − | **3/15** at 0.600 · **6/15** at 0.400 |
| 0.80 mm | 3/15 | 8/15 · 10/15 |
| **1.20 mm** | 3/15 | **11/15 · 13/15** |
| 1.60 – 3.00 mm | 3/15 | 11/15 · 13/15 |

Level 1 barely moves (3/15) because **of the 288 track segments and 21 vias inside a 2.00 mm band,
all but 2 items belong to U10's own nets** — `s7b_write_band.py`: `d=2.0 L2 → displaced 2 items of 1
net`. The band is U10's own fan-out. That is the whole finding: **a re-fan-out is the change, and
nothing outside U10 has to move for the vias.**

Reachability is the decisive test (`s8_escape.py`, BFS on a 0.200 mm F.Cu legality field):

| net | bandwidth as drawn | on the cleared canvas |
|---|---|---|
| /3V3 | lane 0.25 mm, **no path** | lane 2.10 mm, reachable at 0.700 mm |
| /GNSS_RX | lane 0.00, no path | lane 1.35, reachable at 0.700 |
| /HGM | 0.00, no path | 2.10, reachable at 0.700 |
| /LSM_INT1 | 0.00, no path | 3.55, reachable at 0.700 |
| /PA_EN | 0.00, no path | 2.10, reachable at 0.700 |
| /RF_GPIO0 | 0.00, no path | 2.10, reachable at 0.700 |
| /RF_GPIO2 | 0.00, no path | 2.10, reachable at 0.700 |
| /RF_MISO | 0.60, no path | 1.55, reachable at 0.750 |
| /SENS_SCLK | 0.55, **reachable** | 2.70, reachable at 0.700 |
| **reachable** | **1 of 9** | **9 of 9** |

Caveat, stated because it matters: **9 of 9 is per-net independent.** A simultaneous fan-out must
stagger the via field over ≥2 depths — the canvas in §5 fails to do that properly and its DRC says so.

### 4.3 What it costs

`s11_band_occupants.py work.kicad_pcb band_occupants.json 2.0`

```
band 2.00 mm: 288 track segments, 21 vias, over 38 nets
components with a pad inside the band: 16
  completely inside (must move)      : 12  C30 C31 C32 C33 C34 C35 C36 C37 C38 C39 C40 C41
  one pad inside                     :  4  C10 C11 C12 C13
```

All 16 are 0402 decoupling capacitors on /3V3, /1V1 and /GND — they must stay electrically close,
so they move **outward by ~2.6–3.4 mm**, not away. The real labour is the **38-net, 288-segment
fan-out rip-up**, which is a U10-local re-route of the same order as the ESC's remaining route.

---

## 5. The design, as coordinates, and what was executed

### 5.1 The edit plan

`s13_canvas.py` / `s15_canvas.py` compute one legal 0.600/0.300 site per via on the cleared band and
write them into `respin_canvas_v3.kicad_pcb`. The dogbone geometry is **pad centre + 0.700 mm along
the pad's outward normal** (duplicates stepped 0.750 mm further out so two 0.600 vias cannot touch):

| # | net | pad | old XY | new through-via XY | span replaced |
|---|---|---|---|---|---|
| 1 | /3V3 | U10.29 | (58.400, 55.550) | (58.400, 55.650) | F.Cu→In1.Cu |
| 2 | /GNSS_RX | U10.12 | (53.900, 50.600) | (53.350, 50.600) | F.Cu→In1.Cu |
| 3 | /GNSS_RX | U10.12 | (52.900, 53.200) | (52.600, 50.600) | In1.Cu→In2.Cu |
| 4 | /HGM | U10.27 | (57.600, 55.150) | (57.600, 55.650) | F.Cu→In1.Cu |
| 5 | /LSM_INT1 | U10.4 | (54.400, 47.400) | (53.350, 47.400) | F.Cu→In1.Cu |
| 6 | /LSM_INT1 | U10.4 | (51.500, 49.000) | (52.600, 47.400) | In1.Cu→In2.Cu |
| 7 | /LSM_INT1 | U10.4 | (54.400, 47.400) | (51.850, 47.400) | In1.Cu→In2.Cu |
| 8 | /PA_EN | U10.25 | (57.600, 52.200) | (56.800, 55.650) | F.Cu→In2.Cu |
| 9 | /PA_EN | U10.25 | (58.000, 51.900) | (56.800, 56.400) | In2.Cu→B.Cu |
| 10 | /RF_GPIO0 | U10.21 | (56.500, 55.200) | (55.200, 55.650) | In2.Cu→B.Cu |
| 11 | /RF_GPIO0 | U10.21 | (57.400, 56.100) | (55.200, 56.400) | In2.Cu→B.Cu |
| 12 | /RF_GPIO2 | U10.22 | (55.600, 55.200) | (55.600, 55.650) | F.Cu→In2.Cu |
| 13 | /RF_MISO | U10.18 | (53.900, 53.000) | (53.350, 53.000) | F.Cu→In1.Cu |
| 14 | /RF_MISO | U10.18 | (53.900, 53.000) | (52.600, 53.000) | In1.Cu→In2.Cu |
| 15 | /SENS_SCLK | U10.77 | (55.585, 53.453) | (56.400, 44.350) | In1.Cu→B.Cu |

Plus: 16 × 0402 moved radially outward **4.40 mm each** — one uniform step, from the canvas writer;
a production placement would move each one only as far as its own clearance needs, which
`s12_canvas.py`'s per-part exit search put at 1.3–1.8 mm for the same set — the 0.150 mm escape rule
on the L and B rows, and the 38-net band rip-up.

### 5.2 Schematic delta

**For the minimum change: none.** Moving 16 capacitors, re-laying the fan-out and narrowing the
escape tracks changes no net, no pad and no pin assignment. This is a PCB-only revision — which is
why it can be ridden onto the respin drone-arm owes.

The **owed** schematic delta is a separate, pre-existing debt and is unchanged by this wave:

```
U10.GPIO34 (pad 43)  unconnected-(U10-GPIO34-Pad43)  ->  /ESC_PWM7   (7th actuator channel)
U10.GPIO35 (pad 44)  unconnected-(U10-GPIO35-Pad44)  ->  /ESC_TELEM7
U10.GPIO36 (pad 45)  unconnected-(U10-GPIO36-Pad45)  ->  /ESC_FAULT7
U10.GPIO37 (pad 46)  unconnected-(U10-GPIO37-Pad46)  ->  /ESC_PWM6
U10.GPIO38 (pad 47)  unconnected-(U10-GPIO38-Pad47)  ->  /ESC_TELEM6
U10.GPIO39 (pad 48)  unconnected-(U10-GPIO39-Pad48)  ->  /ESC_FAULT6
(then J60–J65 gain those nets; and a servo rail net is added across the servo header)
```

Measured basis: `s3_u10.py` shows **20 of U10's 81 numeric pads sit on auto-generated nets**
(`unconnected-(U10-GPIOxx-Padnn)`), and `u10.json:board_auto_nets` = **64** distinct auto net names
board-wide — the board record's "64 auto nets" reproduces.

### 5.3 What was executed, and what the canvas proves

`s15_canvas.py` executes steps 1–3 of the plan on a copy: moves the 16 capacitors, rips the 309 band
items, writes 15 × 0.600/0.300 through vias at the sites above, removes every remaining non-through via.

```
components moved out of the band:  16
track/via items removed:          309 over 38 nets
through vias written:              15
residual non-through vias removed:  9
SPAN CENSUS: 336 -> 321 vias, NON-THROUGH 15 -> 0
DRC (board's own rules): 139
```

DRC, by type — and this is the honest reading of the canvas:

```
track_dangling 66 · shorting_items 23 · via_dangling 17 · clearance 9
solder_mask_bridge 9 · via_diameter 6 · hole_clearance 4
courtyards_overlap 4 · hole_to_hole 1        unconnected 77 (kicad-cli and pcbnew agree)
```

**The canvas is not a deliverable and is not offered as one.** Steps 1–3 remove copper whose
replacement routes do not exist yet; the 77 unconnected items and the 66 dangling tracks are
precisely that missing route, and the 23 shorts are the moved capacitors landing on copper the
re-route would have vacated. What the canvas establishes is the two things that were in doubt:
**all 15 can be through vias (0 non-through, 0 new HDI)**, and **the debt is bounded and countable —
38 nets, 77 items.** It does not establish that the respin is finished.

### 5.3.1 The sites, checked one by one

Every site in the table above was re-tested against the cleared-band copper for a 0.600/0.300 via
(need 0.425 mm on all four layers):

```
legal: 14 of 15
/RF_MISO  (53.350, 53.000)  dmin 0.4000 vs 0.425 needed  -- BLOCKED by trk /GNSS_RX w0.20
```

**That blocker is a track the canvas itself drew** — the /GNSS_RX dogbone escape, 0.400 mm away in
x, short by exactly 0.025 mm. So the count is **14 of 15 legal, and the fifteenth fails only because
two hand-drawn escapes were put 0.400 mm apart** — which is the same staggering defect this report
already names in §7.2. An independent search with no hand-drawn copper in the way (`s12_canvas.py`,
±2.50 mm on the same cleared inventory) finds **15 of 15**.

### 5.4 The DRC-gated attempt on the real board (the new measurement)

`s10_convert.py` — the board's own via rule (0.600/0.300) and a **±1.50 mm** search, which the
previous wave did not use (it swept ±0.50 mm with a 0.400/0.200 via):

```
candidates with a legal 0.600/0.300 through-via site within 1.50 mm: 10 of 15
```

`/3V3`, `/HGM`, `/PA_EN` ×2 and `/RF_GPIO2` have no legal site even at 1.50 mm (`/3V3` tops out at a
0.550 pad, `/HGM` at 0.600 at 0.056 mm, `/PA_EN` at 0.500, `/RF_GPIO2` at 0.354). The other ten reach
0.769 – 1.000 mm of pad.

Then DRC, one candidate at a time, with a zone refill (ten trials; the seven distinct delta shapes):

```
/GNSS_RX   clearance 5, via_dangling 1, track_dangling 1            -> DROP
/LSM_INT1  clearance 1, shorting_items 1, solder_mask_bridge 1      -> DROP
/LSM_INT1  tracks_crossing 1, track_dangling 1                      -> DROP
/RF_GPIO0  clearance 5, track_dangling 1                            -> DROP
/RF_GPIO0  shorting_items 4, track_dangling 1                       -> DROP
/RF_MISO   clearance 11, shorting_items 5, hole_clearance 2, hole_to_hole 1 -> DROP
/SENS_SCLK clearance 4                                              -> DROP
                 kept 0    dropped 10
```

**kept 0 of 10.** The site is available; the **lane** is not. `/SENS_SCLK` is the sharpest case — it
is 4 clearance violations and nothing else, because the 0.200 mm escape has to cross copper that is
already at the floor.

This is wave 5's "connectable but not legal" (`fab-da-fanout3/REPORT.md:161-169`) reproduced at
1.5× the search radius and with a fab-legal via. The conclusion survives; **the stated reason had to
change from "no site exists" to "no lane exists".**

---

## 6. Free-riders on the respin drone-arm already owes

drone-arm owes a respin anyway: the **7th actuator channel**, the **servo rail**, and the **6 ESC
command nets** that pads 43–48 currently leave on auto-generated nets.

| item | free-rider? | measured reason |
|---|---|---|
| The U10 pinout rewrite | **YES** | pads 43–48 are already unconnected auto nets; 20 of 81 pads are unassigned |
| The 6 ESC nets' fan-out on the **R** row | **YES** | R is at **33.8 %** and reaches only **67.5 %** with all six added — no displacement needed |
| The via-rule change 0.400/0.200 → **0.600/0.300** | **YES** | the respin must clear the board's own 7 `via_diameter` DRC errors regardless |
| Board revision stamp, fab/assembly package, re-quote | **YES** | owed |
| The **L and B fan-out rip-up** (288 segments, 38 nets) | **NO** | 112.5 % over-subscribed; it is the actual work, ≈ a U10-local re-route |
| Moving the **16 × 0402** decoupling capacitors ~2–4 mm | **NO** | new placement work, small but real |
| 0.150 mm escape tracks on L and B | **NO** | a rule change, but only usable once the fan-out is re-laid |

So: **the schematic side is free, the right row is free, the via rule is free — the left and bottom
fan-out is not.** Half the change rides the respin; the half that does not is a bounded re-route, not
a board-wide one.

---

## 7. What remains

1. **Re-lay the L and B escapes at 0.150 mm into a staggered via field** and re-route the 38 nets
   that the band rip-up cut. This is the remaining engineering, and it is the only path to zero.
2. **Stagger the via field.** The canvas places duplicate layer-changes at 0.750 mm steps along the
   normal, which is enough to avoid hole-to-hole but not enough to be a finished fan-out. A real
   fan-out alternates two depths across the row.
3. **Adopt 0.150 mm on the U10 escape layer only.** 0.150 mm at 1 oz is inside every 1 oz service
   this programme has surveyed; the ESC's 4 oz constraint does not apply to drone-arm (1 oz).
4. **Then** re-run `s16_verify.py` and expect `non-through 0, DRC < 7, unconnected 0`. Nothing in
   this wave reaches that number and no artefact here is offered as if it did.
5. **Not attempted, and it should be said:** no fully-connectable fully-legal zero-HDI board exists
   yet. The distance to it is 38 nets and 77 items, and that is the number a work estimate should
   start from, not "15 vias".

---

## 8. Line discipline from this wave

1. **A DRC count is meaningless without the rules file it was run under.** `converted.kicad_pcb`
   reads **581 violations** with no `.kicad_pro` beside it and **7** with the board's own — the same
   bytes, the same `sha256 372C1D52…9077`. Both numbers are correct and only one is about the board.
   Every table in this report names the rules file.
2. **"No site exists" was a search-radius artefact.** Wave 5 swept ±0.50 mm and found 0 of 15; at
   ±1.50 mm, **10 of 15** have a legal site. The wave-5 conclusion survived, but its *reason* did
   not, and a wrong reason is how the wrong fix gets bought.
3. **A negative clearance is data, not an error.** Ten of 15 have foreign copper *over* the point.
   Any tool that clamps at zero turns "inside another net" into "touching", which is the difference
   between impossible and nearly-possible.
4. **The obstruction can be the design's own copper.** 51 of 52 blocking items belong to U10's own
   nets, and all but 2 items in the band are U10's. "Foreign copper" was the wrong mental model;
   measuring the net ownership was the right one. This is the fourth instance of the programme's
   recurring defect class — *a correct measurement of the wrong population* — and the first one
   caught before a number was published.
5. **Frontage, not pitch, is the fan-out limit.** 0.450 mm of lane against 0.400 mm of pitch is the
   entire problem, it is one division, and it predicts the 112.5 % over-subscription on the two rows
   where all the microvias are.

---

## 9. Artefacts

| file | what it is |
|---|---|
| `work.kicad_pcb` (+`.kicad_pro`) | the input, unmodified, `sha256 372C1D52…9077` |
| `converted.kicad_pcb` | DRC gate output — byte-identical to the input (kept 0 of 10) |
| `respin_canvas_v3.kicad_pcb` | **the structural change executed; 0 non-through; canvas, not a deliverable** |
| `respin_canvas.kicad_pcb`, `respin_canvas_v2.kicad_pcb` | earlier canvas iterations, kept because their DRC deltas show the staggering effect (193 → 145 → 138) |
| `census_before.json`, `census_canvas_v3.json` | span census, before and after |
| `blockers.json`, `evict.json`, `ownership.json` | per-via per-layer distances, eviction sets, net ownership |
| `field.json`, `band.json`, `escape.json` | 4-layer via field, band dose-response, reachability |
| `band_occupants.json`, `u10.json` | band census (16 capacitors, 288 segments, 21 vias), U10 pad map |
| `verify_before.json`, `verify_canvas_v3.json` | both-tool verification |
| `drc/own_before.json`, `drc/final_*.json`, `drc/canvas*.json`, `drc/conv_*.json` | DRC evidence |

Scripts, in the order that matters: `s1_census.py` (span) · `s5_blockers.py` (layers below floor) ·
`s6_evict.py` (exact eviction set) · `s9_ownership.py` (who owns it, per-side frontage) ·
`s4_field.py` (per-pad escape lane) · `s7_band.py` (band dose-response) · `s8_escape.py`
(reachability) · `s11_band_occupants.py` (band census) · `s10_convert.py` (DRC-gated attempt) ·
`s13/s15_canvas.py` (execute) · `s16_verify.py` (verify, both tools).
