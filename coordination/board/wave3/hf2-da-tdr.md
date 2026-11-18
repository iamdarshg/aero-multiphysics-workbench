# hf2-da-tdr — hotfix of the TDR coupon report (4 rejects)

**Repairs:** `evidence/w2-da-tdr/REPORT.md` (read-only here; nothing in it was edited).
**Evidence dir:** `evidence/hf2-da-tdr/`. **Repo:** `repos/drone-arm` at `work/2026-11-11`, read-only —
no commit, no push, no working-tree write, no `audit/*` branch touched.
**Pinned board read first:** `AGENT_BOARD.md`. Every derived number below comes from
`hf2_numbers.json`, produced by `scripts/hf2_recompute.py`, which reads the w2 artefacts and nothing else.
**Owner steer applied:** least-effort path that keeps physical fidelity; fab burden accepted freely.
So: constraint edits and coupon-mask edits are taken, no board copper is touched, no stackup change.

---

## 0. Verdict

| # | count | was | **is** |
|---|---|---|---|
| 1 | launch count / cost | "33 SMA … ~$310"; itemised lines sum $283 | **35 launches; $305.60 ≈ $306** (range $253–358) |
| 2 | two-way resolution | 2.9 mm "at εeff 3.2" | **3.37 mm** at εeff 3.171 (tr 40 ps) |
| 2b | 15 mm window | 169 ps | **178.2 ps** at 3.171; 167.8 ps at the defect εeff 2.8113 (the 169 ps is V2's defect εeff, wrong family) |
| 2c | solid plateau | "22.5 mm of line" | **12.63 mm** of line, at 8.42–21.04 mm; 22.5 mm is the defect's *near edge*, not a span |
| 3 | panel | 140×205 / 140×200 / 140×95 / 140×100 | **152 × 233 mm** (one number) |
| 4 | W1 100 mm witness | panel assumed 20 × 70×8; W1 is 110×8 with no slot | **own 110 × 8 row**; DC witness stands at 0.1404 Ω |

The *design intent* survives intact: the coupon set, the cross-sections, the transfer curve and the
refutation criterion are untouched. What changes is arithmetic, W1's panel slot, one coupon's defect
window (X4, §2.5), the panel, the cost and the measurement gates.

---

## 1. Count 1 — launch count and cost

### 1.1 The count

`coupon_list.json` is the orderable specification and it carries a `ports` field per coupon —
**2** at `:20,36,52,68,84,100,116,132,148,164,180,196,212,228,244,260` (16 coupons),
**1** at `:276,292,308` (3 coupons), **0** at `:324` (W1). Summing it:

| class | coupons | ports each | launches |
|---|---|---|---|
| two-port lines: R1–R8, V1–V3, X1–X4, C1 | 16 | 2 | 32 |
| one-port standards: C2, C3, C4 | 3 | 1 | 3 |
| W1 witness (DC + cross-section, no launch) | 1 | 0 | 0 |
| **total** | **20** | | **35** |

16 × 2 + 3 × 1 + 1 × 0 = **35**. The board already carries this count
(`AGENT_BOARD.md:61`, "20 coupons, 35 SMA launches"), and so does the report's own coupon-set
paragraph (`REPORT.md:128`, "16 two-port 60 mm lines, 3 one-port standards, 1 witness"). The only
place the count was wrong is the cost table (`REPORT.md:349`, "33") — i.e. the report disagreed with
itself, and the table is what the price was computed from.

The struck "$310" was never the sum of its own table: PCB 100 + SMA 150 + loads 3 + assembly 0 +
shipping 30 = **$283**, which is exactly the figure the validator quoted. `$310` was $283 × 1.095 —
an undocumented contingency. Both numbers are struck.

### 1.2 The cost, recomputed

Two inputs changed: launches 33 → 35, and the panel (§3) 140×205 = 287 cm² → 152×233 = 354.16 cm².
Unit rates are the report's own (`REPORT.md:346-356`): $0.055–0.075/cm² for 4-layer ENIG, SMA
$3.50–5.50, and the same 5-off quantity basis (5 pcs × 354.16 cm² = 1770.8 cm²).

| line item | qty | unit | total |
|---|---|---|---|
| PCB, 4-layer 1.6 mm ENIG, panel **152 × 233**, 5 pcs | 1770.8 cm² | $0.055–0.075/cm² (mid $0.065) | **$115.10** (97.39–132.81) |
| SMA end-launch jack, 1.6 mm, 50 Ω | **35** | $3.50–5.50 (mid $4.50) | **$157.50** (122.50–192.50) |
| 49.9 Ω 0402 thin film | 10 | $0.30 | $3.00 |
| Assembly (hand, 2 h) | – | – | $0 (or $30 JLC SMT setup) |
| Shipping (DHL, 8–10 d) | 1 | – | $30.00 |
| **Hardware total** | | | **$305.60 ≈ $306** (range $252.89–358.31) |

Check: 115.10 + 157.50 + 3.00 + 0 + 30.00 = **305.60**.

If the struck table's own implied rate is held instead of the range midpoint ($100 for 1435 cm² =
$0.06969/cm²), the PCB line is $123.42 and the total is **$313.9**. Either way the headline is
"≈ $306–314", not $310-by-accident and not $283.

**Delta against the struck itemisation: $305.60 − $283.00 = +$22.60** (PCB +$15.10, SMA +$7.50).
The coincidence that $306 lands near the struck $310 is arithmetic, not vindication: the struck $310
was 33 launches on a 287 cm² panel.

### 1.3 The reduced set (also wrong, fixed here)

`REPORT.md:360-363` offers a 9-coupon fallback with "14 SMA". Recounting the same `ports` field:
R2, R5, V2, X1, X2 (5 × 2 = 10) + C1 (2) + C2, C3, C4 (3) = **15 launches, not 14**.

| | struck | corrected |
|---|---|---|
| launches | 14 | **15** |
| strip | "70 × 95 mm" | 152 × 58 mm (2 columns × 5 rows, same rules as §3) |
| panel co-panelled | — | 152 × 173 mm → PCB $85.46 → **$186 total** |
| panel strip alone | "≈ $45 PCB … ≈ $135" | 152 × 58 → PCB $24.62 → **$129 total** |

So the "< $150" promise only holds if the strip is ordered alone — which forfeits the co-panel lot /
ply / etch argument the source report makes at `REPORT.md:208-213`. **The reduced set no longer meets
a $150 cap without giving up the thing it is for.** It is listed here rather than quietly dropped.

---

## 2. Count 2 — resolution and every derived length at εeff 3.171

### 2.1 One εeff, stated

`coupon_expected.json` carries a different εeff per cross-section. The report silently used four of
them. This hotfix pins **εeff = 3.171** for everything on the solid line — it is
`REF-GCPW-w0.30.eps_solid` (`coupon_expected.json:24` → `solved["(0.3,'solid','GCPW')"].eps_eff =
3.1705128`, `:287`), the GCPW cross-section the report calls "as built". Values for the 0.35 mm
coupon (3.1968) and the defect sections (2.8113 / 2.8524) are used only where labelled.

    v = c/√εeff = 0.299792458 / √3.171 = 0.299792458 / 1.780730 = 0.168352 mm/ps
    λg at 915 MHz = 168.352 mm/ns ÷ 0.915 GHz = 183.99 mm
    two-way delay per mm of line = 2/v = 11.880 ps/mm   ⇒  mm per ps of round trip = 0.084176

### 2.2 The resolution cell

    Δz = tr · c / (2√εeff) = 40 ps × 0.168352 mm/ps / 2 = 3.3671 mm  → 3.37 mm

**RESOLUTION_MM = 3.37.**

Why 2.9 mm was impossible as written (`REPORT.md:233`: "tr·c/(2√εeff) = **2.9 mm** at εeff 3.2"): with
tr = 40 ps the formula returns 3.35 mm even at εeff 3.2, so "2.9 mm at εeff 3.2" is not reproducible
from its own inputs. It is reproducible two other ways,
and both are wrong for the stated purpose:

| reconstruction | result | verdict |
|---|---|---|
| tr 40 ps, **εr 4.2** (laminate, not εeff) | 40 × 0.146283/2 = **2.9257 mm** | the number 2.9 actually came from here |
| tr **35 ps**, εeff 3.2 | 35 × 0.167588/2 = **2.9328 mm** | contradicts the report's own tr ≤ 40 ps |
| tr 40 ps, εeff 3.2 (what it claims) | 40 × 0.167588/2 = **3.3518 mm** | not 2.9 |
| **tr 40 ps, εeff 3.171 (adopted)** | **3.3671 mm** | ✔ |

So the slip is a variable substitution (εr for εeff), not a typo. §3.1's "5 TDR resolution cells at
35 ps" is the same 35/40 ps confusion: 15 mm / 3.37 mm = **4.46 cells**, at εeff 2.8113 it is
4.20 cells. Both are ≥ 3, so the 15 mm window is still a readable plateau and **no coupon geometry
needs to change for it** — which matters, because changing it would re-open six coupons' expected
values.

### 2.3 Every derived length and time, recomputed

| quantity | was | **is** | arithmetic |
|---|---|---|---|
| 60 mm line in wavelengths | 0.334 λg | **0.326 λg** | 60 / 183.99. (0.334 needs εeff 3.3265, i.e. the *microstrip* 0.35 mm value — third εeff in one document) |
| 60 mm round trip | 715 ps | **712.8 ps** | 2 × 60 / 0.168352 = 120/0.168352. (715 ps implies εeff 3.1907, ≈ the 0.35 mm GCPW value) |
| resolution cell | 2.9 mm | **3.37 mm** | §2.2 |
| solid plateau gate 100–250 ps | "22.5 mm of line" | **12.63 mm**, line positions **8.42 – 21.04 mm** | 100 × 0.084176 = 8.418; 250 × 0.084176 = 21.044; span = 12.627. The struck 22.5 mm is 150 ps × c/2 = 150 × 0.29979/2 — i.e. half the round-trip distance at **c in vacuum**, with the dielectric left out |
| defect near edge | 268 ps | **267.3 ps** ✔ | 22.5 mm × 11.880 ps/mm = 267.3. This one was right — which is what exposes 22.5 mm as a *position*, not a length |
| 15 mm defect window transit | 169 ps | **178.2 ps** at 3.171 | 15 × 11.880 = 178.2 |
| 15 mm window in cells | "5 cells at 35 ps" | **4.46 cells** | 15 / 3.3671 |
| 6 mm window (X4) | — | **71.28 ps, 1.78 cells** | 6 × 11.880; 6 / 3.3671 |
| far edge of the 15 mm window | 437 ps | **445.5 ps** at 3.171 | 37.5 × 11.880 |
| gate 290 ps | — | **24.41 mm** | 290 × 0.084176 |
| gate 420 ps | — | **35.35 mm** | 420 × 0.084176 |
| 1.0 mm slot, two-way | 2.3 ps, "three orders below any TDR" | **11.88 ps = 0.30 of a cell** | 2 × 1.0 / 0.168352. 2.3 ps is reproducible only as 2 × 0.35 mm / c = 2.335 ps — the *trace width in air*, not the slot in dielectric |
| board's longest void 2.94 mm | — | **34.9 ps = 0.87 of a cell** | 2 × 2.94 / 0.168352 |
| "stop before 700 ps" | 700 ps | **58.92 mm** of line | 700 × 0.084176; far-end reflection at 712.8 ps |

The magnification argument survives, at its true size: a 1 mm slot is 0.30 of a resolution cell
(invisible), a 15 mm window is 4.46 cells (readable). The struck text claimed "three orders of
magnitude"; the real ratio is 15× in length and 0.30 → 4.46 in cells. The 2.94 mm board void is
0.87 of a cell, so the coupon still has to magnify — just not by 1000×.

### 2.4 The 169 ps is a *mixed-εeff* calculation, and it used the wrong family

This one deserves care, because the obvious repair is wrong.

    15 mm at εeff 2.8524 = 169.01 ps     ← exactly the struck figure
    15 mm at εeff 2.8113 = 167.79 ps     ← the correct defect εeff for X2/X4
    15 mm at εeff 3.171  = 178.20 ps     ← single-εeff value (§2.3)

2.8524 is `VOID1-GCPW-w0.35.eps_defect` (`coupon_expected.json:133`) — the **1 mm slit** coupon V2.
The window being timed is X2's **plane-absent** window, whose ε_defect is 2.8113 (`:206`). So the
report did switch εeff deliberately for the defect section — that part is sound practice — but it
switched to **the wrong coupon's** defect εeff. Under the correct defect εeff:

* 15 mm window = 167.8 ps, and the far edge lands at 267.3 + 167.8 = **435.1 ps**, not 437.
* the cell in the voided section is 40 × 0.178799/2 = 3.58 mm; 15 mm = 4.20 cells; 6 mm = 1.68 cells.

**Rule adopted here:** solid-line quantities at εeff 3.171 (§2.3); defect-section transit at that
coupon's own `eps_defect`, labelled. The single-εeff column stays in the table because it is what the
report *claims* to be doing; the labelled-exception column is what it should do. Both are written
down so the next reader does not have to guess which one a number came from.

### 2.5 Consequence for X4 (the one coupon geometry change)

X4 exists to prove length-independence: if a 6 mm and a 15 mm window read differently by > 2 Ω, the
2D local-cross-section model is invalid. At the corrected resolution, **6 mm is 1.78 cells (1.68 in
the voided section)** — under two, so a null result there is an instrument artifact and the test
proves nothing.

Least-effort fix, and it costs nothing at the fab: **X4's window 6 mm → 12 mm** (3.56 cells at
3.171, 3.36 at 2.8113). Same 70 × 8 slot, same mask layer, one dimension in the DXF. Expected
plateau is unchanged (74.53 Ω — length-independence is the thing under test), and the expected S11
must be recomputed: the report's −22.0 dB is for 6 mm. A closed form that reproduces the report's own
numbers to 0.3–0.5 dB (6 mm → −21.7 vs −22.0; 15 mm → −14.2 vs −14.7) gives **≈ −15.9 dB at 12 mm**
(10 mm would be −17.4 dB). Marked Tier C estimate, `hf2_numbers.json:x4_check`.

The alternative — leave X4 at 6 mm and call it a null test with a stated blind spot — is admissible
but weaker, and this is a coupon, not the board: 12 mm costs nothing and no design rework follows.

### 2.6 Measurement gates (procedure edit, no copper)

With the corrected cell the struck gates sit inside one rise time of the window edges, so they read
the transition rather than the plateau:

| gate | struck | adopt |
|---|---|---|
| solid plateau | 100–250 ps (250 ps is 17 ps before the 267.3 ps edge, inside a 40 ps rise) | **110–225 ps** (9.26 – 18.94 mm) |
| defect plateau | 290–420 ps (22.7 ps and 15 ps from the edges) | **310–395 ps** (26.10 – 33.26 mm; 1 tr inside both edges under either εeff reading) |
| stop | 700 ps | 700 ps still fine (58.9 mm; far end 712.8 ps) |

---

## 3. Count 3 — the panel, one number

### 3.1 The contradiction, located

| claim | source | needs |
|---|---|---|
| "panel 140 × 205" | `REPORT.md:17` (§0 TL;DR) | strip 140 × 100 |
| "coupon strip 140 × 100 mm below it" | `REPORT.md:204` | 10 rows @ 10 mm pitch |
| "panel 140 × 200 (… strip 140 × 95)" | `coupon_list.json:8`, and `scripts/build_coupon_list.py:68` | strip 140 × 95 |
| "coupon strip alone (140 × 95)" | `REPORT.md:211` | strip 140 × 95 |

The strip height arithmetic is unambiguous: 10 rows on a 10 mm pitch with an 8 mm outline needs
(10 − 1) × 10 + 8 = **98 mm**, before any perimeter rail. So 95 cannot be right and 100 is only right
if the strip has a 2 mm total margin — i.e. 1 mm per edge, which is not a panel. 205 vs 200 is the
same defect surfacing twice.

The deeper fault is that `panel_mm` is a hand-written string (`build_coupon_list.py:68`), never
derived from the coupon list it sits in. It also never allocated a slot for **W1's 110 mm outline**,
which the same function appends at `:55-59` — that is count 4 seen from the panel side.

### 3.2 What the coupon set actually needs

20 coupons, outlines from `coupon_list.json`: **19 × 70 × 8 mm + 1 × 110 × 8 mm**
(coupon outline area 11,520 mm²). Rules, all minimal and all fab-acceptable under the owner steer:

* 8 mm coupon width, **10 mm pitch** (2 mm break web) — the report's own pitch, kept;
* 2 columns of 70 mm + a 2 mm break web = 142 mm of inner strip width;
* W1 (110 mm) cannot share a row with a 70 mm coupon (110 + 2 + 70 = 182 > 142) → **its own row**;
* **5 mm perimeter rail** on all four sides (tooling, mouse-bite break-off, and a place to hold the
  panel) — the struck panel had zero rail, which is why it looked small;
* board 140.000 × 100.000 (`AGENT_BOARD.md:56`, Edge_Cuts) co-panelled above the strip with a 5 mm web.

    rows = 1 (W1) + ⌈19/2⌉ = 11
    strip height = (11 − 1) × 10 + 8 + 2 × 5 = 108 + 10 = 118 mm
    strip width  = 70 + 2 + 70 + 2 × 5          = 152 mm
    panel width  = max(140 + 2 × 5, 152)        = 152 mm
    panel height = 5 + 100 + 5 + 118 + 5        = 233 mm
    panel area   = 152 × 233 = 35,416 mm²

### 3.3 Why this and not another arrangement

Shelf-packed from the real outlines, same rules, 5 mm rail:

| columns | strip | rows | panel | area mm² |
|---|---|---|---|---|
| 1 | 120 × 208 | 20 | 150 × 323 | 48,450 |
| **2** | **152 × 118** | **11** | **152 × 233** | **35,416** ← minimum |
| 3 | 224 × 78 | 7 | 224 × 193 | 43,232 |
| 4 | 296 × 68 | 6 | 296 × 183 | 54,168 |
| 2, no rail | 142 × 108 | 11 | 142 × 213 | 30,246 (not buildable) |

**PANEL_MM = 152 × 233.**

The no-rail row is included on purpose: it shows that the struck 140 × 205 was in the right family
size-wise but had no rail, no W1 slot and a 95 mm strip. With the rail it is 152 × 233, **+23.4 % area
against 140 × 205** (and +26.5 % against 140 × 200). That is the honest cost of buildability, and the
owner steer says to accept it rather than shave geometry. Both dimensions are ≤ 250 mm, which is the
small-panel tier at every fab I know of — unverified here, since no fab was contacted (§8.1).

### 3.4 Slot map (for the CAD tech)

Inner strip 142 mm wide, rows 1–11 from the top, 10 mm pitch:

| row | left slot | right slot |
|---|---|---|
| 1 | **W1** (110 × 8, no SMA, 4 Kelvin pads) | — |
| 2 | R1 | R2 |
| 3 | R3 | R4 |
| 4 | R5 | R6 |
| 5 | R7 | R8 |
| 6 | V1 | V2 |
| 7 | V3 | X1 |
| 8 | X2 | X3 |
| 9 | X4 (window 12 mm) | C1 |
| 10 | C2 | C3 |
| 11 | C4 | — |

Row 11 carries only C4: 19 line coupons need 10 rows in 2 columns, so one slot stands empty. W1 has a
row to itself at the top, so a destructive cross-section can be taken without touching a neighbour.

### 3.5 Buildability note forced by the geometry (corrects `REPORT.md:206`)

`REPORT.md:206` says the strip may be measured "flat on the bench, board still attached or already
broken". That cannot be true: coupons are joined launch-end to launch-end across a 2 mm web, and an
SMA end-launch jack barrel is ~10 mm long on the coax axis, so **two facing launches cannot both be
fitted while the coupons are still in the strip**. The correct sequence is *break out, then fit
connectors, then measure*. The strip exists to put the board and all 20 coupons on one panel, one
stackup note and one etch lot — process fidelity — not to be probed in situ. That also removes any
need for 12 mm gaps between coupons, which is why 2 columns still fit.

---

## 4. Count 4 — the 100 mm DC witness W1

### 4.1 The defect

`coupon_list.json:315-329` specifies W1 as `line_len_mm 100.0`, `outline_mm "110 x 8"`, `ports 0`.
The panel string it was built alongside (`:8`) allocates 140 × 95 with 10 slots of 70 × 8, and
`REPORT.md:129` says "Every coupon is a 60.0 mm line (70 × 8 mm outline) unless stated" while
`REPORT.md:204` panels "2 columns × 10 coupons, 70 × 8 mm each". So the one coupon that is *not*
70 × 8 had nowhere to go: the witness that the cross-section plan depends on did not exist on the
panel. `AGENT_BOARD.md:61` already records "W1 110x8" as the finding; this hotfix gives it a slot.

`REPORT.md:224-225` compounds it by asking for a 4-wire DC measurement on "100 mm × 0.35 mm × 35 µm".
There is no 100 mm length anywhere on a 70 mm coupon.

### 4.2 Options, and the choice

| option | DC witness | cost | verdict |
|---|---|---|---|
| **A. own 110 × 8 row (row 1)** | 100 mm, exact | +10 mm strip height (already in 152 × 233) | **chosen** — least effort, keeps the claim true, costs one empty slot |
| B. shorten W1 to a 70 × 8 coupon (60 mm line) | 0.0842 Ω instead of 0.1404 Ω | free | kills the "100 mm" claim and halves the width-witness signal |
| C. two 50 mm coupons in series | 100 mm | needs a jumper, adds a contact resistance | worse metrology than A |
| D. delete W1, rely on the C1 thru | no cross-section, no width witness | frees one 110 × 8 slot; saves no connector (W1 has none) | destroys the ±2 µm width term and the 1.2 Ω separation (`REPORT.md:262-276`) |

Option A is a layout fact, not a new coupon, so the coupon set, cost per coupon and stackup note are
untouched. W1 gets **4 Kelvin pads on 2.54 mm pitch (2 force + 2 sense)** — `ports: 0` stays right,
because a 4-wire measurement is not a launch and must not be counted as one (§1.1).

### 4.3 The DC arithmetic (one struck number inside the fix)

    R = ρL/(w·t) = 1.72e-8 × 0.100 / (0.35e-3 × 35e-6) = 1.72e-9 / 1.225e-8 = 0.1404 Ω   ✔ 0.140 Ω stands

    a 25 µm width error on a 350 µm trace = 25/350 = 7.14 %, not 10 %
    ΔR = 0.1404 × 0.0714 = 0.0100 Ω = 10.0 mΩ                                          (struck: 14 mΩ)

`REPORT.md:224-225` says "a 25 µm width error is 10 % of that = 14 mΩ". 10 % of 0.140 is 14 mΩ, so the
internally consistent pair is simply off by the fraction: 25 µm on 0.35 mm is 7.14 %, i.e. 10.0 mΩ.
The *conclusion* is unchanged and still good — 10 mΩ on a 140 mΩ resistor is trivially readable on a
4-wire bench DMM, which is the whole point of the witness. Only the number moves.

---

## 5. Every struck number, in one place

| was | is | why |
|---|---|---|
| "33 SMA launches" | **35** | 16 × 2 + 3 × 1 + 1 × 0 |
| "≈ $310", items sum $283 | **$305.60 ≈ $306** (range $253–358) | 35 launches + 354.16 cm² panel, same unit rates |
| reduced set "14 SMA", "< $150" | **15 launches**; $186 co-panelled, $129 strip-alone | recount; co-panelling is why the set exists |
| "2.9 mm at εeff 3.2" | **3.37 mm at εeff 3.171** | 2.9 = 40 ps at εr 4.2 |
| "5 resolution cells at 35 ps" | **4.46 cells at 40 ps** | tr confusion |
| "15 mm … is 169 ps long" | **178.2 ps at 3.171** (167.8 ps at that coupon's ε_defect) | 169.0 ps = 15 mm at *V2's* ε_defect 2.8524 |
| "ends at 437 ps" | **445.5 ps** (435.1 ps mixed-εeff) | 37.5 mm |
| "solid plateau 22.5 mm of line" | **12.63 mm**, positions 8.42–21.04 mm | 22.5 mm was computed at c, in vacuum |
| "0.334 λg" | **0.326 λg** | εeff 3.3265 is the microstrip value |
| "715 ps round trip" | **712.8 ps** | 2 × 60 / 0.168352 |
| "1.0 mm slot is 2.3 ps … three orders below any TDR" | **11.88 ps = 0.30 cell**; 15× length ratio | 2.3 ps = 2 × 0.35 mm at c |
| "panel 140 × 205 / 140 × 200 / strip 95 / strip 100" | **152 × 233** | §3 |
| W1 "110 × 8" with no slot | own 110 × 8 row (row 1 of the slot map) | §4 |
| "25 µm = 10 % = 14 mΩ" | **7.14 % = 10.0 mΩ** | 25/350 |
| "±0.66 Ω RSS", "43.6 Ω = 66σ" | **±0.67 Ω** (√0.4481 = 0.6694); 43.6/0.669 = **65σ**; 1.2 Ω = 1.79σ | RSS rounding; 65× was already used in §0 |

Unchanged and re-verified because they are the load-bearing numbers: 52.61 / 118.12 / 83.06 Ω,
50.19 / 74.53 / 89.67 Ω, the 43.6 Ω X1–X2 separation, the 7 dB S11 gap, $3.50–5.50 SMA and the
−10.6 / −17.5 dB board cascades. None of them depended on any number fixed above.

---

## 6. Cross-check against the pinned board

`AGENT_BOARD.md:61` (da-tdr row), `:73` (wave-2 reject table), `:159` (top-5 blocking fab, item 5)
all state the four defects correctly: "35 launches sum to $283, not $310; a 95 mm strip for 10
coupons at 10 mm pitch needs at least 98; W1 has no 100 mm slot; two-way resolution is 3.37 mm, not
2.9". **No BOARD CORRECTION.** Every board number I touched agrees with this hotfix, including the
98 mm check (10 × 10 − 2 = 98 ✓) and W1 110 × 8.

One thing now needs updating, and it is a consequence rather than an error:
`AGENT_BOARD.md:167` ("Authorise the **$283** coupon spend") and the "$283 vs $310" phrasing at
`:159` describe the struck cost table. The spend to authorise is **$306** on a **152 × 233** panel.
I am not writing `BOARD CORRECTION` for it — $283 was a correct sum of a wrong table — but the lead
should carry $306 forward.

---

## 7. Files and reproduction

```powershell
# everything in this hotfix, from the w2 artefacts, one run
& "C:/Program Files/Python312/python.exe" E:/engineering-portfolio-audit/evidence/hf2-da-tdr/scripts/hf2_recompute.py
```

| file | contents |
|---|---|
| `REPORT.md` | this document |
| `hf2_numbers.json` | every number asserted above, keyed: speed, resolution, derived, defect_eps, panel, w1, x4_check, cost, reduced_set, uncertainty |
| `hf2_run.log` | the console output of the run quoted above |
| `scripts/hf2_recompute.py` | the arithmetic: launch sum, cost model, εeff conversions, shelf-packing panel search, W1 DC, X4 closed form, RSS |
| `slot_map.json` | the 11-row slot map of §3.4 (machine-readable, for CAD) |

Read-only inputs: `w2-da-tdr/coupon_list.json` (ports at `:20,36,52,68,84,100,116,132,148,164,180,196,212,228,244,260` = 2,
`:276,292,308` = 1, `:324` = 0; `panel_mm` string at `:8`), `w2-da-tdr/coupon_expected.json` (`solved`
at `:274-401`, `one_sided` at `:402-427`, `eps_defect` at `:133,206`), `w2-da-tdr/REPORT.md`,
`w2-da-tdr/scripts/build_coupon_list.py:55-68` (the hand-written `panel_mm`, the W1 append),
`AGENT_BOARD.md:56,61,73,159,167` (Edge_Cuts 140.000 × 100.000; the four rejects; the spend line).

---

## 8. UNVERIFIED / limits

1. **No quote exists.** No fab was contacted; `web_search` returns *"multiple usable web providers are
   registered (deepseek-official, deepseek-search-api); configure one explicitly"* — the same failure
   the source report records. Every price here is the source report's own unit rates re-applied to a
   corrected quantity and area. **$306 is an estimate, not a quote.**
2. **The panel is geometric, not process-validated.** 152 × 233 assumes a 5 mm rail, a 2 mm web,
   mouse-bite break-off and no V-score near a launch. A fab that wants 8 mm rails or an 18 mm tooling
   strip will quote a bigger panel; the *derivation* stands even if the rail changes.
3. **SMA barrel length is not from a datasheet.** The break-out-before-fit conclusion (§3.5) uses
   ~10 mm for an end-launch jack barrel, from general practice, not a specific part number. If the
   chosen jack is shorter, in-strip measurement becomes possible again — the number does not change,
   only the sequence.
4. **X4 at 12 mm has no FD solve.** Its plateau (74.53 Ω) transfers from the 15 mm X2 solve by the 2D
   length-independence assumption itself; its S11 (≈ −15.9 dB) is a Tier C closed form calibrated to
   reproduce the existing −22.0 dB (6 mm) and −14.7 dB (15 mm) to 0.3–0.5 dB. Re-run
   `coupon_expected.py` with `defect_len 12` for a real number — that file is the other owner's and
   was not written here.
5. **The 60 mm line and the 15 mm window were deliberately left alone.** Both survive the corrected
   resolution (4.46 cells); changing either would re-derive six coupons and buy nothing.
6. **Nothing was measured, still.** This is the same class of evidence as the source report: design
   and arithmetic. The coupon remains the instrument.