# drone-arm — the coupon set that fits $60 and still settles Z0

**Item:** decide the single measurable uncertainty that can change a drone-arm board decision, design
the smallest coupon that resolves it, price it, and state what reading would refute the 2D FD model.
**Board (read-only, nothing written):** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb`,
branch `work/2026-11-11`.
**Evidence dir:** `evidence/dec-coupon-60/`. Nothing was written to any repo; no commit, no push.
**Nature of the work:** design + costing + decision analysis. **No coupon exists and nothing was
measured.** Every Z0 below is analytical (2D quasi-static FD, reused from `w2-da-tdr`, cited).

---

## 0. TL;DR

| | |
|---|---|
| THE_ONE_UNCERTAINTY | Z0 of the **as-built** cross-section where In1 is absent, with the 0.25 mm-gap stitched F.Cu coplanar pour present (74.5 Ω) **or inert** (118.1 Ω) |
| Coupon set | **2 coupons on one 100 × 100 mm panel, 2 SMA launches total**, 5 boards ordered (6 coupons/board: 3 × CA + 3 × CB) |
| CA predicted | 74.53 Ω (as-built model) vs 118.12 Ω (wave-1 model) — **43.6 Ω apart** |
| CB predicted | 50.19 Ω (control; the same line with In1 solid) |
| Cost | **$54.24** booked (metrology launches) / **$37.74** (commodity launches) |
| Fits $60 | **yes** — $5.76 / $22.26 headroom; V2 breaks $60 only above $25.76 shipping |
| Launch count vs the struck design | **2 vs 35**; coupons **2 vs 20** |
| Larger spend justified? | **no** — the whole 20-coupon set now costs $29.72 in parts; shrinking is an *information* choice, not a budget one (§7) |

---

## 1. THE_ONE_UNCERTAINTY — and the two I rejected

### 1.1 The one: is the coplanar return live where the plane is gone?

The board is not a microstrip. A stitched F.Cu /GND pour runs 0.25 mm from the trace edge (the zone's
own `connect_pads clearance 0.25`, `main_rev_b.kicad_pcb:50522`), both sides over 50.4 % of the run and
one side over 46.1 % (`w2-da-tdr/REPORT.md:72-82`). Where In1 is absent — 7.99 % of the run is
"plane absent, ≥ 2 mm half-width" (`w2-da-tdr/REPORT.md:53-61`) — that pour is the only nearby copper.
Two defensible 2D solves disagree about whether it is a return path:

| model | where In1 is absent | where In1 is solid | ratio void/solid |
|---|---|---|---|
| MICRO (wave-1, no coplanar term) | **118.12 Ω** | 52.61 Ω | 2.245 |
| GCPW as built (0.25 mm gap, both sides) | **74.53 Ω** | 50.19 Ω | **1.485** |

(All four from `w2-da-tdr/coupon_expected.json:solved`, keys `(0.35, 'open', 'MICRO')`,
`(0.35, 'solid', 'MICRO')`, `(0.35, 'open', 'GCPW')`, `(0.35, 'solid', 'GCPW')`.)

**What decision it changes.** The two readings map to two different board actions:

| if CA measures | board Z0 mean / worst S11 | action |
|---|---|---|
| 70–80 Ω | 52.9 Ω mean, **−17.5 dB** (`w2-da-tdr/REPORT.md:114-120`) | void fill is routine; **do not re-pour In1**; ship the current plane assignment |
| ≥ 95 Ω | 59.4 Ω mean, **−10.6 dB** (`da-em-field/REPORT.md:192`) | the void **is** the defect; In1 must become a real RF ground before fab |

That is a re-pour of 12,164 mm² of In1 in 3 islands plus the 13 In1 segment moves the void-fill item
already needed (`AGENT_BOARD.md:193-195`), versus not doing it at all. One number picks one branch.

### 1.2 Rejected: the εr of the actual laminate

It moves Z0 by ±0.25 Ω for er 4.2 ± 0.15 (`w2-da-tdr/REPORT.md:269`). Both branches (50.2 and 52.6 Ω)
sit at ≈ −32 dB. **No action changes at any plausible εr.** Worse, the ratio test in §5 measures εr's
effect for free, because it cancels between CA and CB.

### 1.3 Rejected: the effect of the proposed void fill

Two reasons, and the second is the interesting one.

1. A coupon cannot contain rev_b's specific fill. The 9.83 % → 1.31 % result is 13 named In1 segment
   moves on the real netlist (`AGENT_BOARD.md:96`, still not fabbable). A coupon of "some filled
   geometry" measures a substitute and proves nothing about those moves.
2. **A successful fill *is* solid In1 — which is coupon CB.** CB already measures the post-fix
   cross-section to ±1 Ω. So the fill question is inside this set at $0 extra; buying a separate
   "fill" coupon is paying twice for one answer. This is the cleanest application of the brief's rule
   that a coupon confirming what the model says is waste.

---

## 2. THE COUPON SET

**Two coupons. Two SMA launches. One panel.**

| id | line | In1 under the line | coplanar pour | purpose |
|---|---|---|---|---|
| **CA** | 60.0 mm × 0.35 mm | **absent** within ±6 mm of the centreline, full length | both sides, 0.25 mm gap, stubbed to the ground ring | the measurement |
| **CB** | 60.0 mm × 0.35 mm | **solid**, tied to In2/B.Cu | identical | the control and the launch proof |

### 2.1 The design choice that removes the hard part

The struck 20-coupon set put a **15 mm** defect window inside a 60 mm line and then needed a ≥ 9 GHz
instrument to resolve it (2.9 mm), a void-transfer curve, and a 6 mm vs 15 mm length check
(`w2-da-tdr/REPORT.md:243-252`). This set makes each coupon **uniform over its whole length** instead.
Consequences:

* there is no window to resolve, so no transfer curve and no length-independence coupon;
* the plateau is read over ~40–50 mm of line, so **the instrument requirement drops from ≥ 9 GHz to
  ≥ 3.5 GHz** (table §4.1) — the largest single cost-of-access reduction in this design;
* the fabricating stubs (6 mm pitch) and the pour are the *board's own*, so the answer includes the via
  inductance and the discrete-stitch effect that the 2D Dirichlet model omits. The coupon is therefore
  a test of the model *and* of the assumption the model cannot make.

### 2.2 Why no on-board calibration standards, no width ladder, no DC witness

The struck set spent 4 coupons and 5 launches on C1–C4 and 6 coupons on a width ladder, all to resolve
a **1.2 Ω** separation (`w2-da-tdr/REPORT.md:158-173`, `hf2_numbers.json:508`). This set resolves a
**43.6 Ω** separation: 45× the RSS error of ±0.96 Ω (§4.2). Every one of those structures buys
precision that the 43.6 Ω gap does not need, and CB already proves the launch: a line the model calls
50.19 Ω reading 50.2 ± 1 Ω *is* the fixture check.

Calibration is done at the SMA reference plane with the lab's 3.5 mm SOLT kit + port extension — the
one thing that genuinely needs a kit rather than an on-board standard.

### 2.3 Why one port, not two

A 2-port measurement exists to remove the load mismatch from the reading. Here the far end is an
**open** (Γ = +1 exactly, no component, no solder, no cost) and the TDR gate sits between the launch and
the open's return. One port halves the launches (the dominant line item at metrology prices) and halves
the re-mating labour. The cost is that εeff is not independently measurable from S21 — which is
precisely why the result is judged as a **ratio to CB** (§5), not as an absolute against a modelled εr.

### 2.4 No probe-station option

The brief prefers zero launches. It is genuinely cheaper *if* the station exists: a 1 mm-pitch GS pad
pair adds no part cost. But (a) probe-station availability is **UNVERIFIED** here, and (b) a probe's own
launch discontinuity is no better characterised than a soldered SMA without a cal substrate. Publishing
a zero-launch plan whose metrology depends on an unverified fixture would be a plan, not a design.
It is recorded as Plan B (cost $14.00 + $1.06 = **$15.06**) and the two-launch set is costed because it
is the cheapest plan that is certainly executable.

---

## 3. GEOMETRY

| parameter | value | basis |
|---|---|---|
| coupon outline | 68 × 12 mm (60 mm line + 4 mm launch lip each end) | 60 mm = 0.33 λg, 671–716 ps round trip, so the open's return is separable |
| trace | 0.35 mm, ±0.02 | the board's `RF_50R` netclass (`main_rev_b.kicad_pro:355-363`, width at `:359`) |
| stackup | F.Cu 0.035 / prepreg 0.200 er 4.2 / In1 0.035 / core 1.040 / In2 0.035 / prepreg 0.200 / B.Cu 0.035, 1.6 mm, ENIG | `main_rev_b.kicad_pcb:50-97` — unchanged from the board |
| In1 (CA) | copper absent within ±6 mm of the centreline | matches the FD domain's `x = 6 mm` Neumann boundary, `da-em-field/REPORT.md:77-84` |
| In1 (CB) | solid, tied to the In2/B.Cu ring by the stub fence | the post-fix state |
| coplanar pour | both sides, 0.25 mm gap from the trace edge | measured board geometry, `w2-da-tdr/REPORT.md:72-82` |
| stitching | 0.3 mm drill, **6 mm pitch**, 1.2 mm from the trace edge, to the ground ring, 2 rows | board: 14 GND vias within 5 mm, nearest 2.46 mm (`w2-da-tdr/REPORT.md:81`); 6 mm < λg/20 = 9.0 mm, so the fence behaves as a boundary at 915 MHz |
| launch | **1 SMA end-launch jack per coupon, 1.6 mm (0.062 in) board edge** | only 2 in the whole order |
| far end | **open**, no component | removes load-mismatch error and all assembly |
| panel | 100 × 100 mm, **6 coupon sites (3 CA + 3 CB)**, 5 boards (JLC minimum) | 3 × 14 mm rows need 78 × 92 mm — **asserted in `coupon_min.py`, not asserted by eye** (§9 correction 3) |

Layout, one board:

```
        <- 100 mm ->   need 78 x 92 mm incl. 5 mm rails
  +-----------------------------------+
  |  ============== CA ============   |   6 rows at 14 mm pitch:
  |  ============== CB ============   |   1 launch per row, at the left edge,
  |  ============== CA ============   |   so the VNA port reaches the coupon
  |  ============== CB ============   |   without a cable
  |  ============== CA ============   |
  |  ============== CB ============   |
  +-----------------------------------+
       each coupon 68 x 12 mm; 5 identical
       boards per order = 15 CA/CB pairs
```

---

## 4. MEASUREMENT

### 4.1 What instrument is actually needed

1-port S11, 100 MHz – 4 GHz, 1601 points, IF BW 100 Hz, 0 dBm; SOLT at the 3.5 mm kit then port
extension to the launch tip; TDR by IFFT (Kaiser-Bessel, β = 6). Plateau read between the launch
settle and 1.5·tr before the open's return (`coupon_min.json:timing`):

| tr | instrument | CA plateau | CB plateau | two-way res | usable |
|---|---|---|---|---|---|
| 40 ps | 8.75 GHz | 571 ps = 51.1 mm | 616 ps = 51.6 mm | 3.4–3.6 mm | yes |
| 58 ps | 6.03 GHz | 526 ps = 47.0 mm | 571 ps = 47.8 mm | 4.9–5.2 mm | yes |
| **100 ps** | **3.5 GHz** | **421 ps = 37.7 mm** | **466 ps = 39.0 mm** | 8.4–8.9 mm | **yes** |
| 233 ps | 1.5 GHz | 89 ps = 7.9 mm | 133 ps = 11.2 mm | 19.5–20.8 mm | **no** |

So the floor is **≈ 3.5 GHz**, not the 9 GHz the windowed design needed. A 4 GHz lab VNA is common;
this is the difference between "borrow the 6 GHz instrument" and "book the 20 GHz scope".

Procedure: fit the **one CA and one CB that carry jacks**, measure each 3× with re-mating, and report
the spread as the repeatability term. The 5 boards × 3 CA/CB pairs exist as launch insurance: a jack is
desoldered and moved to a fresh coupon if one lifts, which is why the panel is 6 sites and not 2 — the
area is charged regardless, so the spares are free. With V1's commodity jack, buy 4 ($2.68) and fit two
CA/CB pairs on two boards, so board-to-board variation is sampled too. Read the mean plateau; do not
read edges.

### 4.2 Uncertainty, and why the ratio is the result

| term | 1σ | note |
|---|---|---|
| launch + gate | ±0.80 Ω | commodity SMA-KE; ±0.40 with the Amphenol jack |
| trace width | ±0.16 Ω | only if a cross-section is taken; ±2.0 Ω otherwise |
| dielectric thickness | ±0.40 Ω | |
| εr | ±0.25 Ω | |
| repeatability | ±0.20 Ω | 3 re-mates |
| **RSS** | **±0.96 Ω** | |

The separation is 43.6 Ω = **45σ**. Even with no cross-section at all (±2.0 Ω width term, RSS ≈ 2.2 Ω)
it is 20σ. **A cross-section is not needed for this decision** — that is a ~$150–300 lab line item
dropped, and it is dropped *because the question is coarse*, not because it is unimportant.

**The ratio test.** Because CA and CB share εr, h, etch and launch, the reported quantity is
CA/CB, not CA alone:

| CA/CB | reading | meaning |
|---|---|---|
| 1.42–1.55 | as-built model | coplanar return live; the 65–118 Ω bracket is refuted |
| 1.55–1.90 | neither | one-sided pour or partial stitch; escalate |
| **≥ 1.90** | **wave-1 model** | coplanar return inert; **the 2D FD coplanar boundary condition is refuted** |

Ratio uncertainty is ±0.03 (1σ, from ±0.96 Ω on a 50 Ω denominator against a 1.485 nominal).

---

## 5. Expected readings and the decision table

| coupon | as-built model | wave-1 model | reading that triggers it |
|---|---|---|---|
| **CA** (In1 absent, pour both) | **74.53 Ω** | **118.12 Ω** | the one number that matters |
| CB (In1 solid, pour both) | 50.19 Ω | 52.61 Ω | must read 49.5–53.0 or the fixture/track is off nominal |

| observation | call |
|---|---|
| CA 70–80, CB 49.5–53 | coplanar return is real and dominant → **void fill only, no In1 re-pour**; board S11 −17.5 dB; the plane *net* is second-order |
| CA ≥ 95 | coplanar return is inert → **In1 re-pour is mandatory**; board S11 −10.6 dB; wave-1 stands |
| CA 80–95 | neither published model; the 1-sided case (89.67 Ω) is the likeliest truth → re-pour or a much denser fence, decided by CB's post-fix number |
| CB outside 49.5–53.0 | **fail closed.** The launch, the etch, or the stackup is off nominal; CA is inadmissible |
| CA/CB ≈ 1.0 | the "plane absent" coupon still has a plane → fab error, re-order |
| spread of 3 CA copies > 1.5 Ω | repeatability fails → better launches, same design |

---

## 6. REFUTATION_CRITERION

**One line:** *If CA/CB ≥ 1.90 — equivalently CA ≥ 95 Ω with CB ≈ 50 Ω — the F.Cu coplanar return is
inert; the Dirichlet "pour = 0 V" boundary condition in the 2D FD solver is wrong, so every as-built
number in `w2-da-tdr` (50.19 / 51.35 / 74.53 / 89.67 Ω and S11 −17.5 dB) is inadmissible and wave-1's
microstrip column (52.61 / 118.12 Ω, S11 −10.5 dB) stands. If CA/CB = 1.485 ± 0.03 the coplanar model
is confirmed and wave-1's 65–118 Ω bracket is refuted instead.*

This is the only result worth paying for, because it is the only one where **both** outcomes are
informative. A reading of 74.5 kills a planned re-pour (2 engineer-days and a lot of In1 copper);
a reading of 118 makes the re-pour non-negotiable before the fab order. A reading of 50.2 on CB alone
would confirm a model nobody doubts — that is why CB is a control and not the deliverable.

Note the asymmetry deliberately built in: the coupon can also **refute the coupon** (CB off nominal,
CA/CB ≈ 1) and the report says so. A test that cannot fail is not a test.

---

## 7. COST

Two connector choices, same everything else. FX 94.2897 INR/USD (`open.er-api.com/v6/latest/USD`,
2026-11-14).

| line item | qty | unit | V2 booked | V1 commodity |
|---|---|---|---|---|
| PCB, 4-layer, 1.6 mm, ENIG, 100 × 100 mm panel, **5 pcs** | 1 | — | **$14.00** | $14.00 |
| SMA end launch, Amphenol **132289** (0.062 in = 1.6 mm), element14 India ₹904.27 | 2 | $9.59 | **$19.18** | — |
| SMA-KE male, DC–12.4 GHz, Sunrom India ₹63.00 | 4 | $0.67 | — | $2.68 |
| Shipping, PCB China → India (booked; user reports $15–35) | 1 | — | $20.00 | $20.00 |
| Shipping, connectors, domestic (₹100) | 1 | — | $1.06 | $1.06 |
| Assembly: 2 launches, hand, 2 h | — | — | $0 | $0 |
| VNA + 3.5 mm cal kit, in-house | — | — | $0 | $0 |
| **TOTAL** | | | **$54.24** | **$37.74** |
| headroom under $60 | | | **$5.76** | **$22.26** |
| breaks $60 at this shipping | | | $25.76 | $42.26 |

PCB basis, itemised: 0.05 m² order (5 × 0.01 m²) × **$70.6/m²** published 4-layer board charge =
$3.53, + ENIG ≈ ₹200 = $2.12, + **$8.35 allowance for the unpublished 4-layer order minimum** =
$14.00. The $8.35 is the only invented number in the table and it is labelled: the instant quote is
JavaScript-only and could not be obtained here.

**Fits $60: yes, both variants.** V2 is the booked set because the Amphenol part is specified for
0.062 in board thickness and the coupon is 1.6 mm; the Sunrom SMA-KE is listed as a 1.2 mm part, so V1
is contingent on a 1.6 mm variant being in stock (UNVERIFIED). If it is not, V1's price with a 1.2 mm
part on a 1.6 mm board is not a launch — do not use it to save $16.54.

**Excluded from the cap, stated rather than hidden:** VNA time, cal kit, operator hours. Outsourcing
the measurement is $300–600/day and is not proposed. If no in-house VNA exists, the coupon is
unbuildable-in-budget and that is a fact about the lab, not about the coupon.

### 7.1 Does it need to share a panel with a production order? No — and it cannot

`rev_b` has no production order to share: it ships only rev_a gerbers, and rev_b's own fab block is the
still-unverified void fill (`AGENT_BOARD.md:191-195`). So the coupon is its own order, and that is the
cheaper choice anyway: co-paneling with rev_b would put the coupon on the same huge panel that made the
struck set cost $115 in PCB (152 × 233 mm = 35,416 mm²,
`hf2_numbers.json:panel.best_with_rails.panel_mm2`), whereas the coupon alone is
$14.00. **If** rev_c is ordered, add the same two coupons to that panel for **+$6.33** as a same-lot
process check — optional, and worth less than the first measurement because CB has already bounded the
post-fix cross-section.

---

## 8. The governing principle: is a larger spend justified?

**8.1 No.** I looked for the larger-spend case the principle asks me to argue for, and it does not
survive pricing:

* A 2-port version (+2 launches, +1 load) buys ±0.4 Ω instead of ±0.8 Ω. On a 43.6 Ω separation both
  are decisive; **it changes no decision** and costs ~$20 more.
* A transfer-curve set (V2/V3/X3: 3 more coupons, 6 more launches) buys the partial-void mapping. The
  board's voids are **plane-absent, not narrow** — 7.99 % of the run at ≥ 2 mm half-width, only 0.33 %
  in the 0.5–1.0 mm band (`w2-da-tdr/REPORT.md:53-61`). There is almost nothing on the board for a
  transfer curve to map. **It answers a question this board does not ask.**
* The full 20-coupon set is *not* an affordability case at all — see §9.

**8.2 What the $54.24 actually buys, quantified both sides.** The honest probability first: I put
**P(coplanar return live) ≈ 0.80**, on the physical ground that the stubs sit at 5–7 mm against a
λg/20 = 9.0 mm fence rule (`da-em-field/REPORT.md:181`, `w2-da-tdr/REPORT.md:81`) — not on a model
preference. Then:

| | |
|---|---|
| acting on the model, no coupon | 80 % right; 20 % chance of shipping a −10.6 dB board and paying a respin |
| respin cost, assumed | **$400** (the board's own steer: "a respin is worth several hundred", `AGENT_BOARD.md:19`) |
| expected respin avoided | 0.20 × $400 = **$80.00** |
| coupon cost | **$54.24** |
| net | **+$25.76**; break-even at P(live) = **0.136** |

So the cash case is *thin but positive*, and I will not inflate it. The stronger argument is schedule:
8–10 days lead time **fully overlaps** the rev_b work that is already open (J60–J66 lanes, the 0.75 A
PTC that cannot carry 3–9 A, the rev field). Serial schedule cost is ~0 days, which is what makes a
$54 buy on a +$26 expected cash return a good trade. **I am not assuming a respin is coming** — at
P = 0.80 it is the minority branch, and the coupon is justified by it being cheap and parallel, not by
a respin being likely.

---

## 9. BOARD CORRECTIONS

`BOARD CORRECTION:` **`AGENT_BOARD.md:202`, `:210`** and `w2-da-tdr/REPORT.md:344-363`,
`hf2_numbers.json:455-474` price 4-layer FR4 at **$0.055–0.075/cm²**. JLCPCB publishes **$70.6/m²**
board charge for small-batch 4-layer (`jlcpcb.com/news/discount-on-quality-4-layer-pcbs`) = **$0.00706/cm²**,
i.e. the PCB line was inflated **≈ 9.2×**. The struck $115 panel is $12.50 at the published rate.

`BOARD CORRECTION:` **`AGENT_BOARD.md:210`** ("Authorise the $283 coupon spend") and `:202` ("The TDR
coupon design is not yet buildable") frame the obstacle as money. At an Indian distributor's SMA-KE
price (₹63, `sunrom.com` product 7431) the *same 20-coupon set* is **$23.39 of launches + $6.33 of PCB
= $29.72 in parts** (`coupon_min.json:full_set_at_commodity_prices`), ~$50 shipped — inside the $60
cap. The $283/$310 figure is a **metrology-jack price list** ($3.50–5.50 each), not a floor. The real
reason to shrink to 2 coupons is §1 (18 of the 20 buy no decision) plus 35 hand-soldered launches
re-mated 3× — labour, not dollars. Board decision item 5 is therefore a false choice and should be
re-posed as "authorise $54 for 2 coupons".

`BOARD CORRECTION:` **`w2-da-tdr/REPORT.md:203-206`** — a 140 mm-wide panel cannot hold two 70 mm
columns with any rail; the corrected 2-column strip is 152 × 118 mm (`hf2_numbers.json:348-370`). This
set avoids the whole class of error by making the panel **6 rows of 68 × 12 mm at 14 mm pitch on
100 × 100 mm**, and `coupon_min.py` **asserts** `need_w <= 100 and need_h <= 100` (78 × 92 mm) so the
arithmetic cannot be asserted by eye. For the record the first draft of *this* layout did not fit —
7 rows need 106 mm — and the assertion caught it.

`BOARD CORRECTION:` **`w2-da-tdr/REPORT.md:186`** cites `main_rev_b.kicad_pro:358` for the 0.35 mm
`RF_50R` width. `:358` is `schematic_color`; the netclass block is `:355-363` and `track_width` 0.35 is
`:359` (via 0.6 / drill 0.3 at `:360-361` — a standard through via, so nothing here needs HDI).
Corrected in this report; the *number* 0.35 mm was right.

Not corrected, inherited as-is: 52.61 / 118.12 Ω and the S11 −10.5 dB (`da-em-field`), 50.19 / 74.53 /
89.67 Ω and S11 −17.5 dB (`w2-da-tdr`), the stackup (`main_rev_b.kicad_pcb:50-97`), the void geometry
(`w2-da-tdr/REPORT.md:53-61`).

---

## 10. UNVERIFIED / assumptions

1. **No coupon exists. Nothing measured.** Every Z0 here is 2D quasi-static FD. The coupon is the
   instrument that converts those tables into data, and this report is a specification, not a result.
2. **No coupon PCB was drawn.** Bounds, zones, footprints and DRC are the next item (~1 day of CAD).
3. **The 4-layer order minimum is an allowance ($8.35), not a quote.** JLCPCB's instant quote is
   JavaScript-only; the published $70.6/m² charge is real, the checkout minimum is not verified.
4. **Shipping $20 is a user-reported range ($15–35), not a quote.** Both variants are shown with the
   shipping level at which each breaks $60, so the risk is bounded rather than hidden.
5. **V1's ₹63 SMA-KE is listed for a 1.2 mm board**, the coupon is 1.6 mm. V1 is conditional; V2 is
   booked because 132289 is a 0.062 in (1.6 mm) end launch.
6. **No cross-section is bought.** The ±0.96 Ω budget assumes one; without it the width term is ±2.0 Ω
   and the RSS ≈ 2.2 Ω, still 20σ on the separation. If the reading lands in the 80–95 Ω band, *then*
   buy the cross-section before re-designing — that ordering saves the line item in the likely case.
7. **The 6 mm stub pitch is the model's assumption, not a measured board value.** The board has 14 GND
   vias within 5 mm of the run, nearest 2.46 mm (mean ≈ 7 mm along the run). A coupon at 6 mm is
   therefore slightly better stitched than the board: if CA reads low, the board's own stretches are
   worse, and that is the direction that costs money. Stated, not assumed away.
8. **The 2D model's grid uncertainty (±2.6 %, `da-em-field/REPORT.md:109-120`) is not in the ±0.96 Ω
   RSS** because the RSS is a measurement budget. It is the reason the refutation threshold is a ratio
   (1.90) and not a tight absolute.
9. **$400/respin and P(live) = 0.80 are judgements**, labelled. The net EV in §8.2 is therefore an
   order-of-magnitude argument, not a result.

---

## 11. Reproduction

```powershell
# coupon sizing, decision bands, cost table, EV  -> coupon_min.json
& "C:/Program Files/Python312/python.exe" E:/engineering-portfolio-audit/evidence/dec-coupon-60/scripts/coupon_min.py
```

| file | contents |
|---|---|
| `REPORT.md` | this document |
| `coupon_min.json` | geometry, timing windows at 4 rise times, decision bands, ratio thresholds, cost variants, EV |
| `scripts/coupon_min.py` | everything above; reads `w2-da-tdr/coupon_expected.json` directly |

**Sources used for price only** (all fetched 2026-11-15): JLCPCB 4-layer rate
(https://jlcpcb.com/news/discount-on-quality-4-layer-pcbs), Amphenol 132289 at element14 India via
(https://www.findchips.com/search/132289), SMA-KE ₹63 at (https://www.sunrom.com/p/sma-male-pcb-edge-mount-sma-ke-pcb-size-12mm),
FX at (https://open.er-api.com/v6/latest/USD). `web_search` is unavailable in this session
(provider-conflict error); direct fetches were used instead, and every number above that came from the
web is a listed price on a cited page, never a scraped estimate.