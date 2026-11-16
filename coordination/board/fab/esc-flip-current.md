# The FLIP CURRENT — at what per-phase current the 2 oz / 4 oz choice stops being a guess

**Unit:** `esc-flip-current` · **Wave:** 9 · **Assignment:** find the current at which the ESC's branch
choice flips, so the decision does not wait on CdA.

**Host:** KiCad 9.0.7 (`pcbnew` 9.0.7 / Python 3.11) for board measurement; CPython 3.12 for the
arithmetic; matplotlib 3.9.2 for one figure. **Nothing was written into a repo.** No commit, push,
reset, or `audit/*` branch. Every board read is an existing **copy** inside another unit's evidence
directory, opened read-only; every artefact below is written in this directory only.

| artefact | what it is |
|---|---|
| `01_phase_layers.py` → `orig_layers.json` | per-net, per-layer copper census of the board of record (§2) |
| `03_corridor.py` → `03_corridor.json` | FET pitch, FET body, phase-pour geometry → the corridor (§3) |
| `02_flip.py` → `02_flip.json` | 14 controls + the current-vs-capability table + the crosses (§1, §4–§6) |
| `04_chart.py` → `04_capability_vs_current.png` | the decision figure |
| `05_audit.py` → `05_audit.json` | **unit audit of this report**: 29 derived numbers recomputed from their own inputs, 0 mismatches |
| `*.log` | every run's stdout, kept as run |

---

## 0. The answer

**On current capability, 4 oz is weakly dominant at every CdA — it never loses, in any state, on
either k profile. What CdA decides is not *which* branch is stronger but whether the current
question is live at all.** The number that makes the decision decidable today:

| | 2 oz | 4 oz |
|---|---|---|
| **capability, as drawn** (no rail fix) | **20.81 A** — BATP rail binds | **23.08 A** — BATP rail binds |
| **capability, rail fixed** | **32.18 A** — phase corridor binds | **47.12 A** — phase corridor binds |
| **capability, each branch's own redesign executed** (priced, not drawn) | 45.77 A — needs B.Cu freed of BATN and a 23.349 mm pitch | 49.67 A — BATP binds; two-face phase is 75.66 A |
| binding constraint at the flip | **copper (phase corridor)** | **copper (phase corridor)** |
| FET junction with the mandatory spreader | 372.2 A | 372.2 A |

```
FLIP  = 32.2 A   above it 2 oz fails and 4 oz still passes (band 30.9-33.9 A over the measured corridor)
BOTH PASS below 32.2 A (as drawn: below 20.8 A)
BOTH FAIL above 47.1 A (as drawn: above 23.1 A)
```

**At the flip, pick 4 oz; margin 47.12 / 32.18 = 1.46×.** At the spec's own pessimistic CdA
(0.0015 m² → 37.2 A) the margin is **1.27×** and 2 oz is **0.87× the demand — 5.0 A short, 13.5 %**,
i.e. it cannot get there without either trusting a single-layer phase reading or buying the margin
with a 30 K rise.

**Which constraint binds at the flip: copper, not the FETs.** At 32.18 A the junction sits at
**106.3 °C** (4 oz) and **116.7 °C** (2 oz) against a 175 °C limit — the FET thermal limit is 52.1 /
47.2 A without a spreader and **372 A** with it. So the spreader takes the die out of the argument
entirely, and the copper weight is the only thing that moves.

**Decision rule, one sentence:** *if CdA measures below 0.00086 m² either weight carries the aircraft
as drawn; from 0.00086 to 0.00095 m² only 4 oz does; from 0.00095 to 0.00133 m² both need the rail
re-pour and then both pass; and above 0.00133 m² — which includes the spec's own 0.0015 — only 4 oz
passes, at 1.27×, so adopt 4 oz unless CdA proves to be under 0.00086 m².*

---

## 1. The instrument, and the fourteen controls it must pass first

Everything below is IPC-2221 §6.2 in the closed form every prior unit used:

```
A[mil²] = ( I / (k · ΔT^0.44) )^(1/0.725)          k = 0.048 outer, 0.024 inner
I(A)    = k · ΔT^0.44 · (A[mil²])^0.725             ΔT = 20 K
```

`02_flip.py` refuses to print the table unless it first reproduces fourteen numbers this programme
has already published. It does:

| control | computed | published | residual |
|---|---|---|---|
| C1 60 A / 20 K / 0.14 mm width | 13.9813 mm | 13.981 | +0.002 % |
| C2 60 A / 20 K / 0.0525 mm width | 96.9910 mm | 96.991 | −0.000 % |
| C3 45 barrels ampacity | 47.3913 A | 47.4 | −0.018 % |
| C4 60 A / 20 K cross-section at k=0.024 | 5.0920 mm² | 5.092 | +0.001 % |
| C5 BATP 4 oz as drawn (0.5242 mm²) | 23.0845 A | 23.1 | −0.067 % |
| C6 BATP 2 oz as drawn (0.4542 mm²) | 20.8061 A | 20.8 | +0.029 % |
| C7 BATN as drawn (1.4139 mm²) | 47.3957 A | 47.4 | −0.009 % |
| C8 BATP 4 oz fix2 (1.5082 mm²) | 49.6670 A | 49.7 | −0.066 % |
| C9 BATP 2 oz executed fix (1.4401 mm²) | 48.0308 A | 48.0 | +0.064 % |
| C10 BATN fix2 (1.7595 mm²) | 55.5383 A | 55.5 | +0.069 % |
| C11 phase F.Cu only @2 oz, 7.400 mm | 22.8862 A | 22.9 | −0.060 % |
| C12 phase F.Cu∥In2 @2 oz, 7.400 mm | 32.1751 A | 32.2 | −0.077 % |
| C13 4 oz 63-barrel rail (1.9792 mm²) | 60.4840 A | 60.5 | −0.026 % |
| C14 spreader junction | 372.2 A | 372 | +0.05 % |

**One correction the controls caught, recorded rather than smoothed.** My first aggregation summed
each sub-area's own ampacity across a mixed cut and returned **27.8 A** where the programme says
**23.1 A** for the same BATP cut. Cause: the programme evaluates a min-cut as **one area at one k**,
and `x^0.725` is sub-additive, so `(a+b)^0.725 < a^0.725 + b^0.725`. The one-area rule *is* the
conservative one, so it is the rule used here (profile **P_A**) — but it means **every heterogeneous
rail cut on this board is understated by up to 20 % relative to the phase rows**, which are computed
as parallel layers each at its own k. That asymmetry is real and is carried into §9 correction 4.

Profile **P_B** carries the other live convention — barrels at **k = 0.024**, because a plated barrel
sits inside FR4 (`esc-battery-rail/REPORT.md:197-201` calls this "the honest one") — and halves every
barrel number. Both are reported; §8 shows what each does to the flip.

---

## 2. Measurement 1 — the phase current does not flow on one layer, and that moves the answer

The single number the whole branch comparison rides on has been **asserted, not measured**: the board
and `esc-branch-2oz` both quote **22.9 A @2 oz** from a *"phase corridor F.Cu only"* reading, while the
same report also listed *"phase on F.Cu+In2 (the layers the orig uses) — 32.2 A"* without ever
checking which layer the copper is actually on. `01_phase_layers.py` measures it net by net:

| net class | F.Cu | In1.Cu | In2.Cu | B.Cu |
|---|---|---|---|---|
| **18 phase nets, total** | **7,932.62 mm²** | 2,592.00 | **14,928.13 mm²** | 2,592.00 |
| per phase net | 440.5 mm² | 144.0 (pad discs only) | **766–881 mm²** | 144.0 (pad discs only) |
| **zone fills on the net** | **183.7 mm²** | — | **622.3–736.8 mm²** | — |
| stitching vias on the net | 64 | 64 | 64 | 64 |

So each of the 18 phases has **a dedicated pour on F.Cu *and* a dedicated pour on In2**, with 64
through vias tying them, and In2 carries **1.7–2.0× more phase copper than F.Cu does**. The phase
path is **F.Cu ∥ In2** by construction. 36 FET footprints (18 phases × 2 devices) confirm the phase
count.

**That is the like-for-like basis**, and it gives **32.2 A @ 2 oz** and **47.1 A @ 4 oz** — not
22.9 / 48.0. The F.Cu-only figure is retained in every table as row **(e)**, the conservative reading,
because a designer who does not trust the In2 pour should still be able to see that number.

**The same run re-measures the rails as an instrument check** (`01_phase_layers.py`, pad-bbox method):

| net | F.Cu | In1.Cu | In2.Cu | B.Cu | settled figure it reconciles |
|---|---|---|---|---|---|
| `/M1_BATP` | 1,218.27 | **5,044.77** | 5.76 | 5.76 | In1 5,039.01 (**+0.11 %**) |
| `/M1_BATN` | 364.43 | 159.21 | 159.21 | **5,265.82** | B.Cu zone 5,106.61 (pads/vias added) |

The earlier disagreement about *"1,217.29 mm² in 14 components does not reproduce"*
(`esc-branch-4oz/REPORT.md:335`) is now explained rather than left open: **1,218.27 mm²** is what the
pad-**bounding-box** method returns, **922.51 mm²** is what the union method returns. Same population,
two pad-area conventions — not two different populations. See §9 correction 6.

---

## 3. Measurement 2 — the corridor is 7.0–7.9 mm, and 7.400 sits inside it

The flip current scales as `w^0.725`, so the corridor was measured rather than inherited from the
hard-coded 7.400 mm in `esc-branch-2oz/02_widths.py:128`.

| board | distinct x-pitches | FET body (bbox) | `pitch − body − 2×0.250` |
|---|---|---|---|
| board of record | 19.063 / 19.064 / 19.212 mm | 11.560 × 14.920 mm | **7.003 mm** |
| power-first placement | 20.000 mm | 11.560 × 14.920 mm | **7.940 mm** |

Triangulated a third way on the board of record: adjacent **phase pours** are `19.063 − 11.600 =
7.463 mm` apart, and a new trace with 2 × 0.250 mm clearance fits **6.96 mm** — which is the same
7.0 mm as the pitch-minus-body calculation, from a completely different element. The prior units'
**7.400 mm is inside the measured band** and is used as the nominal; the band's ends give the flip
band **30.9–33.9 A** (§4). The conclusion does not depend on which of the three is right.

---

## 4. Current vs capability — the table the item asked for

ΔT = 20 K. `cap` = the ampacity of the element; **PASS** iff the demand current is ≤ the cap.
`(e)` is the conservative F.Cu-only phase reading; `(c)` is the measured F.Cu∥In2 path.

### 4.1 State S1 — as drawn, no battery-rail fix (today's board)

| constraint | cap 2 oz | 15 | 20 | 25 | 30 | 35 | 40 | 45 | cap 4 oz |
|---|---|---|---|---|---|---|---|---|---|
| (a) BATP rail min-cut | 20.8 | P | P | **F** | F | F | F | F | **23.1** |
| (b) BATN via barrels | 47.4 | P | P | P | P | P | P | P | **47.4** |
| (c) phase F.Cu∥In2 | 32.2 | P | P | P | P | **F** | F | F | **47.1** |
| (e) phase F.Cu only | 22.9 | P | P | **F** | F | F | F | F | **37.8** |
| (d) FET junction, spreader fitted | 372.2 | P | P | P | P | P | P | P | **372.2** |
| (d′) FET junction, no spreader | 47.2 | P | P | P | P | P | P | P | **52.1** |

`2 oz capability 20.81 A (BATP)` · `4 oz capability 23.08 A (BATP)` · **flip 20.81 A** ·
**both fail above 23.08 A**.

### 4.2 State S2 — after the battery-rail fix both branches already cost

| constraint | cap 2 oz | 15 | 20 | 25 | 30 | 35 | 40 | 45 | cap 4 oz |
|---|---|---|---|---|---|---|---|---|---|
| (a) BATP rail min-cut | 48.0 | P | P | P | P | P | P | P | **49.7** |
| (b) BATN via barrels | 67.3 | P | P | P | P | P | P | P | **60.5** |
| (c) phase F.Cu∥In2 | **32.2** | P | P | P | P | **F** | F | F | **47.1** |
| (e) phase F.Cu only | 22.9 | P | P | **F** | F | F | F | F | **37.8** |
| (d) FET junction, spreader fitted | 372.2 | P | P | P | P | P | P | P | **372.2** |
| (d′) FET junction, no spreader | 47.2 | P | P | P | P | P | P | P | **52.1** |

`2 oz capability 32.18 A (phase)` · `4 oz capability 47.12 A (phase)` · **flip 32.18 A** ·
**both fail above 47.12 A**.

The rail figures used are the **executed** ones, not aspirations: 2 oz BATP **1.4401 mm² → 48.0 A**
with BATN **2.2937 mm² → 67.3 A** (`esc-branch-2oz/09_remeasure.json`); 4 oz BATP **1.5082 mm² →
49.7 A** with BATN at the specified **63 barrels → 60.5 A** (`esc-branch-4oz/21_rail_4oz.py`).

---

## 5. The crosses, and what CdA has to be

Demand current is proportional to CdA (`P_d ∝ CdA` at fixed speed), anchored on the settled point
**16.8 A ↔ CdA 0.000693 m²**:

```
I = 16.8 · CdA / 0.000693        (equivalently the same thresholds read backwards)
```

| threshold | current | CdA it corresponds to | what it means |
|---|---|---|---|
| 2 oz fails **as drawn** | 20.81 A | **0.000858 m²** | above this, 2 oz needs rail work to be legal |
| 4 oz fails **as drawn** | 23.08 A | **0.000952 m²** | above this, *both* weights need rail work |
| 2 oz fails **after rail fix** | **32.18 A** | **0.001327 m²** | **the FLIP** — 4 oz still passes to 47.1 |
| the spec's own alternative point | 37.2 A | 0.0015 stated (0.001535 by this law) | 4 oz passes 1.27×; 2 oz fails (0.87×) |
| 2 oz after its own redesign | 45.77 A | 0.001888 m² | needs B.Cu freed + 23.349 pitch |
| 4 oz fails **after rail fix** | 47.12 A | 0.001944 m² | above this neither weight works |

*Anchor note, because the chain's own two points are 2.3 % inconsistent:* `16.8 A ↔ 0.000693` and
`37.2 A ↔ 0.0015` do not lie on one proportional law (a strictly proportional law gives **36.4 A** at
0.0015). This report uses the proportional law anchored at the **design point**, which is the
conservative end for the decision, and quotes the spec's 37.2 A as the pessimistic demand rather than
its 36.4 A equivalent. The difference is 0.8 A and does not move any verdict.

**Read against the two candidates the programme actually has:**

| CdA | demand | as drawn | with rail fix |
|---|---|---|---|
| **0.000693** (the design point) | 16.8 A | 2 oz 1.24× · 4 oz 1.37× | 2 oz 1.92× · 4 oz 2.80× |
| **0.0015** (the spec's own alternative) | 37.2 A | 2 oz **FAIL** · 4 oz **FAIL** | 2 oz **FAIL** (0.87×) · 4 oz **PASS** (1.27×) |

That last row is the actionable result, and it **reverses the board's current steer**: at the
pessimistic CdA the A/B question does *not* move in favour of 2 oz — 2 oz is the weight that fails.

---

## 6. Why the FETs are not the constraint, and what would make them one

The junction model is the one `esc-branch-2oz/05_thermal.py` built and validated (RthJA control
22.36 °C/W, and it returns 39.4 A where the datasheet says 37 A at 25 °C):

```
P(I) = 1.33e-3 · I² + 0.0424 · I     W per device    (1.4 mΩ × 1.9 hot, half duty + switching)
Tj   = 45 °C + P · RthJA              limit 175 °C    RthJA 22.36 (4 oz) / 26.14 (2 oz)
```

| I (A) | P/device (W) | Tj 2 oz (°C) | Tj 4 oz (°C) |
|---|---|---|---|
| 15 | 0.94 | 69.4 | 65.9 |
| 20 | 1.38 | 81.1 | 75.9 |
| 25 | 1.89 | 94.4 | 87.3 |
| 30 | 2.47 | 109.5 | 100.2 |
| **32.18 (the flip)** | **2.74** | **116.7** | **106.3** |
| 40 | 3.82 | 145.0 | 130.5 |
| 45 | 4.60 | 165.3 | 147.9 |
| 52.1 (4 oz limit) | 5.82 | 197.1 | 175.1 |
| 60 | 7.33 | 236.7 | 208.9 |

So:

* **With the mandatory spreader** (RthJC 0.4, case 95 °C, 200 W budget) the limit is **372.2 A** in
  both branches — **11.6×** the flip current, and **7.9×** the 4 oz copper limit. The die is out of
  the argument, exactly as `esc-branch-2oz` concluded.
* **Without** it, the limit is 47.2 A (2 oz) / 52.1 A (4 oz). At 4 oz that is **only 1.11×** the
  copper limit of 47.1 A — so at 4 oz the copper and the die converge at ~47–52 A, and the spreader
  is the thing that keeps copper the binding constraint. At 2 oz the gap is wider (47.2 vs 32.2).
* **The FETs never bind at or below the flip in either branch.** Copper binds. If the demand ever
  reaches 60 A, the no-spreader junction hits **208.9 °C (4 oz) / 236.7 °C (2 oz)** — the spreader is
  not optional at any current above ~52 A, which is consistent with the settled "mandatory" call.

Two secondary bounds stay clear at the flip and are not re-derived here: the shunts sit at **0.52 W**
of a 10 W rating at 32.2 A (the settled 1.8 W at 60 A, scaled by I²), and the sense chain saturates
at 145 A.

---

## 7. Which branch at the flip, and the margin, stated conservatively

**At 32.18 A: 4 oz. Margin 1.46×.** Above 32.18 A and below 47.12 A there is no 2 oz design *at
today's placement* that is legal; the 2 oz branch would have to take the re-place it already costs
(23.349 mm pitch, 415.8 cm², +3,528 vias) to reach 45.77 A.

**A conservative design uses the pessimistic CdA, and the conservative CdA does not flatter 2 oz:**

| basis | demand | 2 oz | 4 oz | verdict |
|---|---|---|---|---|
| design point, as drawn | 16.8 A | 20.81 (1.24×) | 23.08 (1.37×) | either weight, but neither comfortably |
| design point, rail fixed | 16.8 A | 32.18 (1.92×) | 47.12 (2.80×) | either weight |
| **pessimistic CdA, as drawn** | 37.2 A | **20.81 — FAIL** | **23.08 — FAIL** | **the rail is mandatory at either weight** |
| **pessimistic CdA, rail fixed** | 37.2 A | **32.18 — FAIL (0.87×, 5.0 A short)** | **47.12 — PASS (1.27×)** | **4 oz only** |
| pessimistic CdA, rail fixed, **30 K** rise | 37.2 A | 38.46 — PASS (1.03×) | 56.32 — PASS (1.51×) | 2 oz survives on a 1.03× margin |

The third row is the one that changes the decision's shape: **at the pessimistic CdA the branch choice
was never the binding question** — the battery rail is, and it is binding in *both* branches. The
branch only becomes decidable in the fourth row, and there 2 oz loses.

The last row is stated because it is the one escape hatch 2 oz has: at a 30 K allowed rise it reaches
38.46 A. That is not a design margin (1.03×), it is a way of not answering the question, and it costs
temperature headroom that the mandatory-spreader budget assumes.

---

## 8. Everything that could still move the flip

| input | value used | if it changes | effect on the flip |
|---|---|---|---|
| **corridor width** | 7.400 mm nominal | measured band **7.003–7.940** | flip **30.9–33.9 A**; 4 oz ceiling **45.3–49.6 A** |
| **barrel plating k** | P_A k=0.048 (programme) | P_B k=0.024 | **halves every rail number.** As drawn: 2 oz 16.83 / 4 oz 19.86. Fixed: 2 oz 24.02 / 4 oz 24.83 — **the 4 oz advantage shrinks from 1.46× to 1.03×, and the design point (16.8 A) sits 0.2 % under the as-drawn 2 oz floor** |
| **ΔT** | 20 K | 30 K | fixed-state caps 38.46 / 56.32 → 2 oz passes 37.2 A at 1.03× |
| | | 50 K | 48.15 / 70.51 → both pass everything in the table |
| **plated wall** | 25 µm | 38 µm | barrel **area** +50 %, so ampacity +34 %: BATN 47.4 → **63.5 A**; both rails then clear the phase floor in every state, and the flip would be set by the phase corridor alone |
| **rail DC vs phase RMS** | 1:1 (programme convention) | true factor 0.9841 | rail floors +1.6 % in phase-equivalent terms (21.15 / 23.45 as drawn); **no effect on the flip**, which is phase-bound in S2 |
| **demand provenance** | P_d = 2,580.6 W → 16.8 A | see §9 correction 5 | the table's 15–45 A range is only valid on the P_d reading |

**The two that matter are the corridor band (±3 A) and the barrel k (a factor of two on the rails).**
Neither moves the *direction* of the answer: 4 oz is never worse than 2 oz on copper, and the only
world in which the flip vanishes is P_B, where both branches fail together at ~25 A.

---

## 9. BOARD CORRECTIONS filed

**1. The board's branch table compares two different populations and two different states.**
`AGENT_BOARD.md` carries *"2 oz gives 22.9 A max per phase; 4 oz gives 48.0 A max per phase."*
22.9 A is a **phase-corridor** number computed on **F.Cu alone**; 48.0 A is the **BATP rail after
the 2 oz rail fix** (`1.4401 mm² → 48.03 A`, control C9) — arithmetically a *2 oz* number, printed in
the 4 oz column. Neither is a 4 oz phase number. Like-for-like, on the layers the copper is actually
on: **phase 32.2 A @2 oz / 47.1 A @4 oz**; rail, as drawn **20.8 / 23.1 A**; rail, fixed
**48.0 / 49.7 A**. The published 48.0 A is accidentally close to the right answer (49.7 rail, 47.1
phase), which is why the error survived — the provenance is wrong even where the number is not.

**2. "2 oz … its 22.9 A ampacity covers the design point with margin" is the conservative reading,
not the design's own copper.** The phase nets carry a dedicated **In2 pour of 622–737 mm² per phase**
(measured, §2), tied with 64 through vias. The design's own phase capacity at 2 oz is **32.2 A** —
a **1.92×** margin at 16.8 A once the rail is fixed. On the board as it stands today the **branch**
margin is **1.24×**, set by the rail rather than by the phase, which is not "with margin" in any sense
a warranty would accept.

**3. "The A/B question changes again — and this time in favour of 2 oz" does not survive the
pessimistic CdA.** At 37.2 A, 2 oz fails (32.18 A) and 4 oz passes (47.12 A). The 2 oz lean is valid
only if CdA ≤ 0.00133 m². Nothing about the U201 package cost changed, so if the owner wants 2 oz the
argument has to be made on packages and area — not on current.

**4. The rail and phase rows are evaluated on different k-aggregation rules.** Rail cuts are one area
at one k; phase corridors are parallel layers each at its own k. Because `x^0.725` is sub-additive,
this makes the **rail rows up to 20 % conservative** relative to the phase rows (my first run returned
27.8 A for BATP where the programme says 23.1 A on identical geometry). This is a conservative
inconsistency, not an optimistic one, but the two bases must not be compared as if identical, and this
report does not.

**5. The `×6 = 75.6 N` line in the 16.8 A derivation is not a consistency check — it contradicts the
P_d it sits beside by a factor of six.** `T = ½ρv²CdA = 12.60 N` is the **whole aircraft's** drag at
200 m/s (CdA 0.000693 m² is the aircraft's). Multiplying it by 6 gives 75.6 N of *thrust at 200 m/s*,
which is **15.1 kW of aero power**, not the 2,580.6 W the chain uses, and would imply **~100 A per
phase**. Comparing 75.6 N against the 78.5 N *weight* is a hover check applied to a cruise drag —
thrust equals drag in level flight, not weight. **The 16.8 A figure survives because P_d is the
correct whole-aircraft power for D ≈ 12.9 N, not because of that line.** Anyone who "fixes" the line by
making P_d consistent with 75.6 N moves the demand by 6× and the ESC into a different product. The
table in §4 is valid on the P_d reading only.

**6. `1,217.29 mm²` is reproducible, and `esc-branch-4oz:335` was wrong to call it a different
population.** The pad-**bounding-box** method returns **1,218.27 mm²**; the union method returns
**922.51 mm²**. Same copper, two pad-area conventions — a 0.08 % match, not a mystery.

---

## 10. What is NOT settled, written as open

| id | item |
|---|---|
| **F1** | **The phase min-cut was never measured per layer.** §2 measures the *population* (both pours exist, 64 vias each) and §3 the *placement corridor*; crediting In2 with the same 7.400 mm is conservative for a layer holding 1.7–2.0× more copper, but a `railmc` per-layer cut on one phase net would close it. That is the next measurement, and it can only *raise* the 2 oz number. |
| **F2** | **The barrel k is worth a factor of two and is still open.** `esc-battery-rail:197-201` calls k=0.024 "the honest one" for barrel copper and every other row on the board uses k=0.048 for it. Under P_B both branches fail the pessimistic CdA at ~25 A and the branch question reverts to packages. **Settle this before quoting any rail number in either direction.** |
| **F3** | **The 2 oz redesigned state (45.77 A) is priced, not drawn** — it needs B.Cu freed of BATN, and BATN's 5,265.82 mm² plane would have to move to In1, which is already 16.00 mm against 94.88 mm needed. That cascade is not costed anywhere. |
| **F4** | **Plating wall:** 25 µm is assumed everywhere; at 38 µm every barrel gains 50 % of **area** (= +34 % of current, since I ∝ A^0.725) and BATN rises 47.4 → 63.5 A, so the rails stop being the constraint as drawn. One fab question, and it is the same one `esc-battery-rail` A2 already flagged. |
| **F5** | The ΔT = 20 K assumption is the programme's (A1 in the rail unit). It is worth ±20 % on every number here and the repo states none of its own. |
| **F6** | The spreader's 200 W budget at a 95 °C case is inherited from `esc-branch-2oz/05_thermal.json`, not solved here. If the real case temperature is 120 °C, the spreader limit falls to 306 A — still 9.5× the flip, so this one does not bite. |

---

## 11. Reproduce

```powershell
$kpy = "C:\Program Files\KiCad\9.0\bin\python.exe"
$py  = "C:\Program Files\Python312\python.exe"
$ev  = "E:\engineering-portfolio-audit\evidence\esc-flip-current"
cd $ev
& $kpy 01_phase_layers.py     # per-net per-layer copper -> orig_layers.json
& $kpy 03_corridor.py         # FET pitch / body / phase pours -> 03_corridor.json
& $py  02_flip.py             # 14 controls, the table, the crosses -> 02_flip.json
& $py  04_chart.py            # -> 04_capability_vs_current.png
& $py  05_audit.py            # 29-line unit audit of REPORT.md -> 05_audit.json (exit 0 = clean)
```

`02_flip.py` exits non-zero and prints **NOT quotable** if any control misses by more than its
tolerance, so the table cannot be produced on a broken instrument. `05_audit.py` exits non-zero if any
number quoted in this report disagrees with its own recomputation by more than 0.5 %.

**Tiers:** every cross-section, width, area and ampacity here is **ANALYTICAL** on **MEASURED**
geometry (board copper, FET pitch, pour areas). The demand current (16.8 / 37.2 A) is **ANALYTICAL**
on an **ASSUMED** CdA and is the one input this unit does not verify. No SOLVER tier is claimed.