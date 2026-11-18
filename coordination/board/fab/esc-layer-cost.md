# ESC — what does six layers buy, and what does it cost?

**Wave 15 specialist report.** ONE question: *what does six layers buy the ESC, and what does it
cost — in fabrication money and in the owner's stated constraints?*

Evidence dir: `E:/engineering-portfolio-audit/evidence/esc-layer-cost/` (all work on copies; the
repository board is read-only input).
Input facts: `esc-3oz-build/REPORT.md`, `esc-branch-4oz/REPORT.md`, `fab-4oz-capability/REPORT.md`,
`esc-corridor-instrument/REPORT.md`, `esc-ampacity-basis/REPORT.md`.

---

## 0. Status

| Step | State |
|---|---|
| Report skeleton | written |
| 1. Six-layer stackup proposed | **done — 3/4/1/1/4/3, 1.60 mm; outer must be 3 oz, not 4 oz** |
| 2. Ampacity of the stackup | **done — phase 49.6 A, rails 44.4 A, bus barrels still 34.5 A** |
| 3. Real 4-layer vs 6-layer prices | **done — published list prices + quote-gated heavy copper** |
| 4. Constraint impact (4-layer promise, no HDI) | **done** |
| 5. Recommendation | **done — 6 layers is necessary but not sufficient; do not buy it alone** |

**Basis check (`00_board.py` → `00_board.json`):** the repository board `esc_rev_b.kicad_pcb` is the
**original 491.73 cm² layout** (my edge bbox: 173.95 × 283.08 = 492.4 cm² including the edge line),
4 copper layers, 1.60 mm, 687 footprints, 0 on B.Cu, 1,990 vias, stackup 0.14/0.0525/0.0525/0.14
over a 0.795 mm core. Every number in this report is for the **382.709 cm² power-first placement of
record**, not the repository original; the two must not be mixed.

---

## 1. Proposed six-layer stackup

### 1.1 The premise that fails first: outer layers cannot be 4 oz

The obvious six-layer plan — "4 oz outer for the phase corridors, fine pitch unchanged" — does not
exist. The fine-pitch parts (QFN-80 U201 at 0.200 mm pads, USB-C J202/J203, the LQFP-48s) are SMD
lands **on the outer layers**. At 4 oz the board's 89 remaining pad-to-pad gaps (U201 75, USB-C 14)
are below every published 4 oz pattern floor: 0.250 mm is the tightest capability-table figure
(Multi-CB special), 0.305 Bay Area, 0.330 PCBWay, 0.400 LeitOn (`fab-4oz-capability/REPORT.md`
§1). A six-layer board has the same outer layers as a four-layer one, so it cannot move those
lands off 4 oz. **Six layers does not let you keep 4 oz outer.** Outer copper must be 3 oz
(105 µm) for the fine-pitch geometry, exactly as the 3 oz four-layer build already proved
(229 → 102 DRC rows, 89 gaps gone, ADDED 0).

What six layers actually buys is **inner-layer real estate for wide phase and rail planes at a
copper weight the 4-layer stack cannot afford**: four inner layers instead of two, so a 4 oz
phase plane and a 4 oz rail plane can coexist with a ground plane and a signal layer. That is the
real mechanism, and it is why the phrase "more copper on outer layers" is the wrong model.

### 1.2 The stack

| layer | copper | thickness | function |
|---|---|---:|---|
| L1 F.Cu | **3 oz** | 0.105 mm | fine-pitch lands, FET pads, phase fan-out |
| prepreg | FR4 | 0.100 mm | 2 × 1080 |
| L2 In1.Cu | **4 oz** | 0.140 mm | **PHASE_A / PHASE_B / PHASE_C planes** |
| core | FR4 | 0.360 mm | |
| L3 In2.Cu | 1 oz | 0.035 mm | GND plane |
| prepreg | FR4 | 0.100 mm | |
| L4 In3.Cu | 1 oz | 0.035 mm | signal / return |
| core | FR4 | 0.360 mm | |
| L5 In4.Cu | **4 oz** | 0.140 mm | **BATP / BATN / BATP_IN planes** |
| prepreg | FR4 | 0.100 mm | 2 × 1080 |
| L6 B.Cu | **3 oz** | 0.105 mm | bus terminals, motor terminals, rails |
| mask | | 0.010 × 2 | |

Copper 0.560 mm + dielectric 1.020 mm + mask 0.020 mm = **1.600 mm**, symmetric
(3/4/1/1/4/3, PP-core-PP-core-PP), so the board thickness and the single-sided assembly are
unchanged. The 0.100 mm prepregs and 0.360 mm cores are nominal; the fab rebalances to 1.60 mm
(the 4-layer board already does this, 0.14/0.0525/0.0525/0.14 over a 0.795 mm core).

Why 4 oz on L2/L5 rather than 3 oz everywhere: at 3 oz an inner phase plane needs **31.12 mm** of
width; at 4 oz it needs **23.34 mm**. In a 155.15 mm-wide board carrying three phases, 3 × 23.3 =
70 mm is comfortable, 3 × 31.1 = 93 mm is tight, and the rail planes compete for the same width.
The 4 oz inner tier is the cost this buys (see §3).

**UNMEASURED:** no inner-layer plane geometry was cut. The 23.34 mm / 20.79 mm requirements are
computed, not measured against a routed plane; the claim is that the width exists on an
unobstructed inner layer, and that must be proven by a layout, not by this report.

---

## 2. Ampacity of the proposed stackup

Basis unchanged from the gate of record: `A[mil²] = (I/(k·ΔT^0.44))^(1/0.725)`, ΔT = 20 K,
k = 0.048 external, k = 0.024 internal, 1.50 A per 0.4 mm / 25 µm barrel
(`02_ampacity.py` → `02_ampacity.json`). Provenance: the corridor width 9.420 mm and the barrel
counts (23 bus / 17 leg) are MEASURED by the earlier units; every capacity in the table below is
ANALYTICAL from the formula, not a measurement; the plane widths are ASSUMED layout allowances.

| element | layer | t | width | capacity | required | ratio | verdict |
|---|---|---:|---:|---:|---:|---:|---|
| PHASE_A/B/C | L2 4 oz inner | 0.140 | 28.0 mm | **49.63 A** | 43.5 | **1.14** | PASS |
| PHASE_A/B/C | L2 4 oz inner | 0.140 | 23.34 mm (minimum) | 43.50 A | 43.5 | 1.00 | at limit |
| BATP_IN | L5 4 oz inner | 0.140 | 24.0 mm | **44.39 A** | 40.0 | **1.11** | PASS |
| BATP | L6 3 oz outer | 0.105 | 15.66 mm | 52.88 A | 40.0 | 1.32 | PASS |
| BATN | L6 3 oz outer | 0.105 | 20.147 mm | 63.47 A | 40.0 | 1.59 | PASS |
| bus shunt pad | 23 barrels | — | — | **34.50 A** | 40.0 | **0.86** | **FAIL** |
| leg / drain pads | 17 barrels | — | — | 25.50 A | 25.11 | 1.02 | PASS |
| Tj at TA 45 °C | — | — | — | 101.4 °C | 175 | — | PASS |

**43.5 A is reachable on the phase with +14 % margin (49.63 A), and the 40 A bus rail on the
inner plane with +11 % (44.39 A). It is NOT reachable at the bus shunt pad: 23 legal barrels ×
1.50 A = 34.5 A against 40 A.** The pad is 14.19 mm² (CSS4J-4026, 5.6 × 2.55 mm); the 0.90 mm
barrel pitch and the 0.30 mm border cap it at 23 positions, and need is 27. Six layers makes the
barrels **longer**, not more numerous: the deficit is pad area, and it is invariant to layer
count.

### 2.1 One basis correction found while checking the 4-layer comparison

The settled block's "4 oz needs 6.991 mm" is a **ΔT = 30 K** number (this script reproduces
7.015 mm at 30 K). On the gate's own 20 K basis — the one that produces 11.963 mm at 3 oz —
4 oz needs **8.972 mm**, and the 9.420 mm corridor carries **45.06 A (1.04×)**. As a width ratio
the comparison is 9.420/6.991 = 1.35× on the 30 K basis versus 9.420/8.972 = 1.05× on the 20 K
basis. Both bases pass 43.5 A at 4 oz, so the verdict does not move, but the 4 oz current margin
is **4 %, not 24 %**; 6.991 mm must not be quoted as a 20 K result.

---

## 3. Real prices: 4-layer vs 6-layer

Vendor-published prices, accessed **2026-11-16**; full quotes and URLs in `03_prices.md`.
Quantity 5 pieces. No vendor publishes a 3 oz or 4 oz list price; heavy copper is quote-gated at
every house checked, so the heavy-copper rows are ESTIMATES from published multipliers.

| option (382.709 cm², 5 pcs) | currency | price | tier |
|---|---|---:|---|
| 4-layer, 1 oz (PCBWay list, 100/150 cm² points scaled) | USD | **296–433** | published list, extrapolated |
| 6-layer, 1 oz (same method) | USD | **626–720** | published list, extrapolated |
| 4-layer, 3 oz | USD | **450–870** | ESTIMATE (1.5–2×) |
| **6-layer, 3/4 oz (proposed)** | USD | **1,300–1,900** | ESTIMATE; quote only |
| 6-layer, 3 oz uniform (cheaper fallback) | USD | 940–1,440 | ESTIMATE (1.5–2×) |
| Multi-CB entry, 80×100 mm, 1 oz | EUR | 4L €59 (5 WD) / 6L €98 (5 WD) | published |
| PCBWay heavy-copper build time | — | 5–10 days | published |

The six-layer premium at 1 oz is **1.7–2.1×** the four-layer price at this area; at heavy copper
the same layer delta plus a 4 oz inner tier puts the proposed stack at about **2× on midpoints**
(end-to-end range 1.5–4× because both heavy-copper terms are quote-gated). On a 5-piece prototype
that is a **$400–1,000** mid-range delta. The dominant cost is copper weight, not layers: 3 oz is
1.5–2× 1 oz on its own, and 4 oz inner is a second step. Lead time moves from the standard tier
to 5–10 build days.

The real cost statement is therefore: **the 6-layer premium is real but second-order; the heavy
copper is first-order; and neither can be turned into a firm number without a quote**, because
both fabs that can make 0.200 mm at 105 µm sell 140 µm only as special production.

---

## 4. Constraint impact

| constraint | status |
|---|---|
| **No HDI** | **Kept.** All vias are through-hole 0.4 mm drill; no microvia, no blind/buried, no via-in-pad. Six layers is not HDI. |
| **"The boards are 4-layer"** | **Broken.** This is the decision the owner must make. It is a change from what they understood, not a reinterpretation: 6 copper layers, two more lamination steps, a second heavy-copper tier, and a new stackup to qualify. It must be approved explicitly, not slipped in as an implementation detail. |
| **Fab base** | **Narrowed, not widened.** The fine-pitch geometry still needs 3 oz at 0.200/0.200, which only Multi-CB special publishes; the 4 oz inner adds PCBWay/Multi-CB heavy copper. Six layers does not create a second source for the fine pitch. |
| **Board thickness / assembly** | **Unchanged.** 1.60 mm, 687 footprints, 0 on B.Cu, single-sided assembly. |
| **Heat spreader** | **Unchanged.** It is outside the outline (181.2 cm² contact declared); the stack is 1.60 mm and the spreading path is through the outer copper. |
| **Cost** | **~2× the 4-layer 3 oz estimate**, i.e. $400–1,000 more per 5-piece lot, quote-gated. |

---

## 5. Recommendation

**Six layers resolves the fine-pitch half and the phase/rail half of the ampacity contradiction.
It does not resolve the contradiction.** The 40 A bus still fails at 34.5 A because of the 14.19 mm²
shunt pad, and no layer count changes that. A six-layer board bought as "the 43.5 A escape" would
be a $1,300–1,900 lot that still exits the gate on G6.

**What I would build: the 4-layer 3 oz board at reduced current — 34.5 A bus / 36.6 A phase —
and not the six-layer board, until the shunt land is changed.** Reasons: (1) it is the only
variant whose pattern class is published by a real house (Multi-CB 105 µm special, with its
annular/via rows still on the 0.150–0.175 mm ring floor); (2) it keeps the owner's 4-layer
constraint; (3) it costs roughly half; and (4) the six-layer spend does not remove the binding
blocker. The moment 43.5 A / 40 A is a hard requirement, the compliant path is **six layers +
a shunt land that holds 27 barrels**, funded as one revision — not six layers alone.

If the owner will not change the shunt footprint and will not accept derating, then no stack in
this study passes, and the honest answer is that the electrical requirement and the layout are
incompatible.

---

## 6. Limitations — what is UNVERIFIED

| item | status |
|---|---|
| Inner plane widths (23.34 mm phase, 20.79 mm BATP_IN) | **COMPUTED requirement, not measured.** No inner-layer geometry was cut or DRC'd. |
| 4 oz inner availability at Multi-CB | **UNVERIFIED.** Their table is headed "Outer and Inner layers", but 140 µm is special production and is not in the calculator. |
| 3/4 oz mixed-copper 6-layer price | **UNVERIFIED / quote only.** No vendor publishes it; rows in §3 are ESTIMATES. |
| 6-layer 3 oz at 0.200/0.200 | **UNVERIFIED.** Proven at 4-layer 3 oz on this board; a 6-layer stack changes lamination, not the pattern class, but that is an inference. |
| Barrels at 6 layers | The 1.50 A/barrel basis is held; a longer barrel through 1.60 mm is not separately derated. |
| Whether the phase plane fits around 1,990 via antipads | **UNVERIFIED.** Needs a routed inner layer, not an area argument. |