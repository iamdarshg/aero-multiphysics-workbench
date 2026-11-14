# drone-arm — the TDR coupon that settles Z0

**Item:** design a coupon set that resolves 51.2 / 52.6 / 65–118 Ω without a full board spin.
**Board:** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb`, branch `work/2026-11-11`,
read-only — nothing in the repo was modified, nothing was committed.
**Evidence dir:** `evidence/w2-da-tdr/`. Every number below is either a file:line in the repo,
a JSON in this dir, or a wave-1 citation.
**Nature of the work:** design + analysis. **No coupon exists yet and nothing was measured.**
All Z0 values here are analytical (2D quasi-static FD, same solver as wave-1).

---

## 0. TL;DR

| | |
|---|---|
| Coupon count | **20 coupons** (16 two-port 60 mm lines, 3 one-port standards, 1 witness) on one 140 × 205 mm panel with the board |
| Line geometry | 60.0 mm, 0.30/0.35/0.40 mm, same 4-layer stackup, SMA end-launch, 2-port |
| The decisive coupon | **X2** — board-exact void (In1 absent over 15 mm) with the coplanar pour as built |
| Published FD model predicts | X2 = **118.1 Ω**, S11 −7.5 dB |
| This item's as-built model predicts | X2 = **74.5 Ω**, S11 −14.7 dB |
| Separation | **43.6 Ω** = ~65× the measurement uncertainty (§5) |
| Why it matters | on the *board*, the same two models give S11 **−10.6 dB** vs **−17.5 dB** (§4) |
| Cost | ~US$310 hardware (estimate, not a quote), ~8–10 days |
| Refutation | one line, §6 |

Two facts about the board were **missing from wave-1** and both change the coupon design:

1. **The In1 void is not a narrow slot.** 88.79 % of the 102.35 mm RF run has In1 copper
   within 0.05 mm of the trace; the voided 11.21 % is almost entirely **≥ 2 mm half-width**
   (7.99 % of the run) — the plane is simply *absent*, not "0.25–1 mm clearanced"
   (`board_void_scan.json`). Wave-1's 65–118 Ω bracket is therefore not a bracket for this
   board: the board sits at the 118 Ω end, if the microstrip model applies at all.
2. **The line is not a microstrip.** An F.Cu /GND pour runs **0.25 mm from the trace edge over
   96.5 % of the run** (both sides for 50.4 %) — exactly the item wave-1 recorded as
   "UNVERIFIED … can move Z0 by several ohms" (`da-em-field/REPORT.md:226-228`). Including it
   takes solid Z0 from **52.6 → 50.2 Ω** and plane-absent from **118.1 → 74.5 Ω**.

So the three published numbers are all *microstrip* numbers. None of them describes the board
as built, and the 1.4 Ω disagreement between 51.2 and 52.6 is smaller than the geometric term
that was left out. The coupon is what decides which cross-section is real.

---

## 1. What the board actually is (measurements made for this item)

### 1.1 Lateral In1 geometry — the dimension wave-1 said was missing

`scripts/board_void_scan.py` ray-marches 0.02 mm outward from every point of the 0.35 mm F.Cu
RF run (68 segments, 102.35 mm, same filter as wave-1: `/915 MHz RF/` + `/GNSS/`) and records
the first In1.Cu copper on each side. Result (`board_void_scan.json`):

| In1 void half-width (mean of the two sides) | run length | % of run |
|---|---|---|
| < 0.05 mm (solid) | 90.88 mm | **88.79 %** |
| 0.05 – 0.25 mm | 0.12 mm | 0.11 % |
| 0.25 – 0.50 mm | 0.23 mm | 0.23 % |
| 0.50 – 1.0 mm | 0.34 mm | 0.33 % |
| 1.0 – 2.0 mm | 2.61 mm | 2.55 % |
| **≥ 2.0 mm (plane absent)** | **8.18 mm** | **7.99 %** |

* 88.79 % solid here vs **88.86 %** over /3V3 in wave-1's area-based count — two independent
  methods agreeing to 0.07 % (`da-em-field/REPORT.md:127-128`). The 11.21 % void also matches
  the 11.14 % area figure. The scan is trustworthy.
* Contiguous void stretches (a **lower bound**: a trace-segment end splits a run): **5 runs,
  10.78 mm total, longest 2.94 mm** (`board_void_scan.json:void_runs_ge1mm`).
* Consequence: the board's voided 11 % is a **2.9 mm-long, wide-open hole in the reference**,
  not a clearance-sized slot. That is below TDR resolution (§3) but easy to magnify on a coupon.

### 1.2 Coplanar copper — the term that was left out

Same scan, F.Cu zones (`board_void_scan.json:fcu_pour`):

| | |
|---|---|
| Distance from trace centreline to F.Cu /GND pour | **0.44 mm everywhere** (min = median = 0.44; ray grid 0.02 mm ⇒ true edge 0.425 mm) |
| ⇒ gap from trace edge | **0.25 mm** — the F.Cu zone's own `connect_pads clearance 0.25` (`main_rev_b.kicad_pcb:50522`) |
| Pour present on **both** sides | **50.4 %** of the run |
| Pour present on **one** side | **46.1 %** |
| No pour within 3 mm | 3.5 % |
| GND stitching vias near the run | 162 on the board, **14 within 5 mm**, nearest 2.46 mm (`stitch_vias.json`) |

So the line is a **grounded coplanar waveguide with a 0.25 mm gap, stitched at ≈ 5–7 mm
average spacing**, over a /3V3 plane. Neither wave-1 model (microstrip over 3V3) nor the
skrf model (microstrip over GND) is this structure.

### 1.3 The two competing cross-sections, solved

Same FD solver as wave-1 (`scripts/da_em_fd_solve.py`), extended with a coplanar Dirichlet
region and a full-domain (asymmetric) variant. All values in `coupon_expected.json`.

| reference state | 0.30 mm | 0.35 mm | 0.40 mm |
|---|---|---|---|
| **MICRO** solid (wave-1 model) | 57.06 | **52.61** | 48.86 |
| **GCPW** solid, pour both sides | 54.33 | **50.19** | 46.69 |
| **GCPW** solid, pour one side | – | **51.35** | – |
| MICRO, single 1.0 mm slot (wv = 0.5) | 88.37 | **83.06** | 78.36 |
| GCPW both, same slot | 75.55 | **71.83** | 68.55 |
| GCPW one, same slot | – | **76.90** | – |
| MICRO, In1 absent | 123.22 | **118.12** | 113.67 |
| GCPW both, In1 absent | 77.82 | **74.53** | 71.75 |
| GCPW one, In1 absent | – | **89.67** | – |

Solver check: the full-domain both-side solve (50.193 Ω) reproduces the half-domain symmetric
solve (50.193 Ω) to 0.001 Ω, and the MICRO column reproduces wave-1's 52.61 / 83.06 / 118.12 Ω
exactly. The extension is a geometry change, not a method change.

**The point of the table:** the coplanar term costs 2.4 Ω on a solid reference but **43.6 Ω**
on a void. It is a second-order effect on the good 89 % of the line and a first-order effect on
the bad 11 % — which is precisely why the 51.2 vs 52.6 argument could never settle the board.

Applying the measured geometry to both columns (`coupon_expected.json:board_*`):

| model applied to the *measured* per-0.1 mm geometry | mean Z0 | max Z0 | S11 worst 902–928 |
|---|---|---|---|
| MICRO (wave-1) | 59.37 Ω | 116.93 Ω | **−10.6 dB** |
| GCPW (as built) | 52.88 Ω | 74.53 Ω | **−17.5 dB** |

The MICRO row reproduces wave-1's −10.5 dB (`da-em-field/REPORT.md:192`) from an independent
geometry scan — a second cross-check that both the scan and the cascade are right. The gap
between the rows is 7 dB of return loss and it is a **geometry question a coupon answers in
one afternoon**.

---

## 2. COUPON_SET

20 coupons on one panel: **16 two-port 60 mm lines, 3 one-port standards, 1 witness**, in five
families. Every coupon is a 60.0 mm line (70 × 8 mm outline) unless stated. `R` = reference
(In1 solid), `V` = controlled single void, `X` = board-exact void, `C` = calibration,
`W` = witness.

| id | family | coplanar pour | width | defect | what it isolates |
|---|---|---|---|---|---|
| R1 | R | none | 0.30 | – | width slope, no-coplanar anchor |
| **R2** | R | none | 0.35 | – | **the 52.6 Ω number under test** |
| R3 | R | none | 0.40 | – | width slope |
| R4 | R | both, stitched | 0.30 | – | as-built + width |
| **R5** | R | both, stitched | 0.35 | – | **the board's real cross-section** |
| R6 | R | both, stitched | 0.40 | – | as-built + width |
| **R7** | R | one side, stitched | 0.35 | – | the 46 % of the run with one-sided pour |
| **R8** | R | both, but In1 = /3V3 | 0.35 | – | "is a 3V3 plane an RF ground?" (wave-1 limitation #4) |
| V1 | V | none | 0.35 | 1.0 mm slot, 15 mm | void transfer curve, no coplanar |
| **V2** | V | both | 0.35 | 1.0 mm slot, 15 mm | **void transfer curve, as built** |
| V3 | V | one | 0.35 | 1.0 mm slot, 15 mm | void transfer curve, one-sided |
| X1 | X | none | 0.35 | plane absent, 15 mm | board-exact void, no coplanar |
| **X2** | X | both | 0.35 | plane absent, 15 mm | **board-exact void, as built — decisive** |
| X3 | X | one | 0.35 | plane absent, 15 mm | board-exact void, one-sided |
| X4 | X | both | 0.35 | plane absent, **6 mm** | 2D length-independence check |
| C1 | C | both | 0.35 | – | known 50 Ω thru (2-port), 50.19 Ω by model |
| C2 | C | both | 0.35 | open end | OPEN standard |
| C3 | C | both | 0.35 | short to In1 | SHORT standard |
| C4 | C | both | 0.35 | 49.9 Ω 0402 | LOAD standard |
| W1 | W | both | 0.35 | – | 100 mm DC witness + destructive cross-section |

Why exactly these:

* **R1–R3 / R4–R6** are a width ladder on *each* cross-section. A coupon measures Z0; it cannot
  by itself separate "the model is 1.4 Ω high" from "the fab etched 25 µm narrow" — that is
  +2.0 Ω at dZ0/dw = −0.081 Ω/µm (0.81 Ω per 10 µm, `da-stackup/REPORT.md:160`). The ladder plus
  W1's cross-section separates them; without it the whole exercise is a coin toss.
* **R7** exists because the board's pour is one-sided over 46 % of the run. One-sided pour gives
  51.35 Ω — i.e. *between* the two published numbers, which is a good warning that a numerical
  coincidence (51.2) is not evidence.
* **R8** is the only coupon that tests the assumption wave-1 could not test: a /3V3 plane held at
  RF ground by decoupling. If R8 = R5 within 0.5 Ω, the plane *net* genuinely does not matter
  once the coplanar pour is present — which would demote the whole "In1 is 3V3" finding.
* **V2 vs X2** separate "narrow void" from "no plane". The board has almost no narrow voids
  (§1.1), so V2's real job is to validate the *transfer curve* between the two endpoints.
* **X4** tests the 2D assumption itself: if a 6 mm and a 15 mm window of the same cross-section
  read differently by >2 Ω, the local-cross-section model is invalid and every number in this
  report (and in wave-1) is unusable.
* **C1–C4** are the calibration structures asked for; §4 says honestly what they can and cannot do.

---

## 3. GEOMETRY

### 3.1 Per-coupon dimensions

| parameter | value | basis |
|---|---|---|
| line length (launch plane to launch plane) | **60.0 mm** | 0.334 λg at 915 MHz; 715 ps round trip, so a TDR gate fits between launch and far-end reflection |
| coupon outline | 70 × 8 mm | 5 mm launch pad each end, 2 mm rail |
| trace width | **0.30 / 0.35 / 0.40 mm**, ±0.02 | task spec; 0.35 is the board's `RF_50R` netclass (`main_rev_b.kicad_pro:358`) |
| copper | 35 µm (1 oz), ENIG | `main_rev_b.kicad_pcb:52,97` |
| stackup | 0.20 prepreg / 1.04 core / 0.20 prepreg, εr 4.2, tanδ 0.02 | `main_rev_b.kicad_pcb:50-97`, unchanged |
| In1 reference | solid /GND pour, zone clearance 0.25 mm | the *only* deliberate change from the board (which has /3V3 at `:56070-56079`); R8 keeps /3V3 |
| coplanar pour | F.Cu /GND, **0.25 mm gap** from trace edge, both sides (or one side for R7/V3/X3) | measured §1.2; matches the F.Cu zone clearance `:50522` |
| stitching | 0.3 mm drill vias, **5 mm pitch**, 1.2 mm from the trace edge, both sides; 4 vias per launch | board has 14 GND vias within 5 mm of the run (nearest 2.46 mm) |
| defect window | **15 mm long, centred**; slot **1.0 mm wide** (V: wv = 0.5 mm) or **6 mm wide** (X: plane absent) | 5 TDR resolution cells at 35 ps (§4) |
| launch | **SMA end-launch jack**, 1.6 mm PCB, 50 Ω, 2 per line coupon; ground tabs soldered to the pour and via-stitched at the launch | metrology-standard, removable, re-matable |
| far end | VNA port (2-port) — no on-board termination for R/V/X; C4 is the only 50 Ω load | removes the load-mismatch error from Z0 |

The line **must be measured 2-port**. A 1-port measurement with a chip load adds the load's own
mismatch (±0.3 Ω after transformation) to a budget that has to resolve 1.2 Ω.

### 3.2 How it panels with the real board

| | |
|---|---|
| Panel | **140 × 205 mm**, one panel, one stackup note, one etch lot |
| Board | 140 × 100 mm at the top (`main_rev_b.kicad_pcb`, edges at `-0.075 … 140.075 / 100.075`) |
| Coupon strip | **140 × 100 mm** below it: 2 columns × 10 coupons, 70 × 8 mm each, 10 mm pitch |
| Join | 5 mm web, **3 × 2 mm mouse-bite tabs** per column; no V-score anywhere near a launch (V-score debris and stress wreck SMA launches) |
| Break-off | after measurement; measure the strip flat on the bench, board still attached or already broken — either is fine, the launches are on the strip |

Why co-panel: the coupon must share the *panel* with the board, not just the order. Dielectric
lot, prepreg ply thickness (0.200 vs 0.2104 mm is +3 % on Z0, `da-stackup/REPORT.md:170-175`),
etch bias and plating all vary panel-to-panel; a coupon built on a different panel measures a
different board. If rev_b is not being ordered, order the coupon strip alone (140 × 95) with the
**identical stackup note** and treat its Z0 as a process baseline, not as this board's number —
state that limitation in the report of the measurement.

---

## 4. Measurement procedure

### 4.1 Order of operations (this order matters)

1. **Cross-section first, on W1 and one spare of each family.** Measure w (±2 µm), h (±5 µm for
   both prepregs), t, and the coplanar gap (±5 µm). Cost: one coupon, 2 days at a lab.
   Without it, a 1.2 Ω model difference cannot be separated from etch bias.
2. **4-wire DC resistance on W1** (100 mm × 0.35 mm × 35 µm ⇒ 0.140 Ω nominal): a 25 µm width
   error is 10 % of that = 14 mΩ, easily read. This is the cheap, non-destructive width witness.
3. **2-port S-parameters, 100 MHz – 6 GHz**, 1601 points, IF BW 100 Hz, 0 dBm.
   Calibration: **SOLT with a 3.5 mm kit at the SMA reference plane**, then **2 mm port
   extension** to the launch tip. Verify on C1/C2/C3/C4 before touching a DUT:
   C1 |S11| < −40 dB at 1–3 GHz, C2/C3 |Γ| = 1.00 ± 0.01 over 0.5–3 GHz, C4 < −30 dB.
4. **TDR from S11** (port 1, port 2 terminated in the calibrated 50 Ω): Kaiser-Bessel window
   β = 6, **rise time tr ≤ 40 ps**. tr = 0.35/BW ⇒ **VNA bandwidth ≥ 9 GHz** (a 13.5 GHz 2-port
   VNA gives ~26 ps and is the realistic lab instrument; a 20 GHz sampling scope is better).
   Two-way resolution = tr·c/(2√εeff) = **2.9 mm** at εeff 3.2.
5. **Read the plateaus, not the edges.** Gate windows (round trip from the launch plane):
   * solid plateau **100 – 250 ps** (22.5 mm of line, ends before the defect at 268 ps);
   * defect plateau **290 – 420 ps** (the 15 mm window is 169 ps long, ends at 437 ps);
   * stop before **700 ps** (far-end reflection at 715 ps).
   Z0 = mean of the plateau. This is a *direct* impedance reading — no model, no fit.
6. **εeff from the S21 phase slope** over 0.5–2 GHz (±0.5 %). Then the pair (Z0, εeff) separates
   h from εr: Z0 alone cannot, and εr 4.2 ± 0.15 is worth ±0.65 Ω on its own.
7. Repeat every coupon 3× with re-mating; report the spread as the repeatability term.

### 4.2 Why tr ≤ 40 ps and why the coupon magnifies the void

A 1.0 mm slot in the reference is 2.3 ps of two-way delay — **three orders of magnitude below
any TDR**. The coupon does not try to resolve the board's void; it sets the void to a known
width over a length the instrument *can* resolve (15 mm = 5 resolution cells), measures the
impedance there, and thereby calibrates the FD transfer curve Z0(wv). The board's own geometry
(measured, §1.1: wide-open voids, 2.9 mm longest) is then read off that calibrated curve.

This is the honest chain, and it has a testable weak link: if X4 (6 mm) and X2 (15 mm) disagree,
length matters and the chain breaks (§6).

### 4.3 What the on-board calibration structures can and cannot do

C1–C4 are **not** a substitute for a traceable cal kit: an on-board open has fringing
capacitance and an on-board short has via inductance, both of which differ from the kit's
definition. Their job is (i) to verify the launch and the fixture, (ii) to allow a self-cal with
a stated penalty (≈ ±1 Ω instead of ±0.4 Ω) if no kit is available, and (iii) C1 is the system
check: a line that the model says is 50.19 Ω must read 50.2 ± 0.5 Ω or the launch is lying.

### 4.4 Uncertainty budget (1σ, per coupon)

| term | value | how it is controlled |
|---|---|---|
| launch + gate | ±0.40 Ω | 2-port TRL/port extension, gate away from the launch |
| trace width | ±0.16 Ω | cross-section ±2 µm (without it: ±2.0 Ω — the dominant term) |
| dielectric thickness | ±0.40 Ω | cross-section ±5 µm |
| εr | ±0.25 Ω | εeff from S21, not assumed |
| repeatability | ±0.20 Ω | 3 re-mates |
| **RSS** | **±0.66 Ω** | |

So: the 1.2 Ω gap between the reference variants is **1.8σ** (needs the cross-section — with it,
R2 vs R5 vs R7 is a real measurement), and the 43.6 Ω gap at X2 is **66σ** (a single
measurement decides it, no statistics needed).

---

## 5. Expected readings if the FD model is right

Two columns, because "the FD model" is now ambiguous and that ambiguity is the finding.
**M** = the published 2D model, microstrip over In1 (/3V3 or GND, no coplanar copper) —
`da-em-field/REPORT.md`. **C** = this item's as-built model (coplanar pour, 0.25 mm gap).
All from `coupon_expected.json`; S11 is the 2-port 60 mm line terminated in 50 Ω at 915 MHz.

| coupon | M: Z0 | C: Z0 | M: S11 @915 | C: S11 @915 | TDR plateau |
|---|---|---|---|---|---|
| R1 0.30 micro | 57.06 | – | −19.0 dB | – | 57.06 |
| **R2 0.35 micro** | **52.61** | – | −27.3 dB | – | **52.61** |
| R3 0.40 micro | 48.86 | – | −34.2 dB | – | 48.86 |
| R4 0.30 both | – | 54.33 | – | −22.8 dB | 54.33 |
| **R5 0.35 both** | – | **50.19** | – | −49.6 dB | **50.19** |
| R6 0.40 both | – | 46.69 | – | −24.6 dB | 46.69 |
| **R7 0.35 one** | – | **51.35** | – | −32.9 dB | **51.35** |
| R8 0.35 3V3 | (52.6 if ideal 0 V) | 50.2 … 52.6 | – | – | 50.2 – 52.6 |
| V1 slot, micro | 83.06 | – | −11.8 dB | – | 83.06 |
| **V2 slot, both** | – | **71.83** | – | −15.5 dB | **71.83** |
| V3 slot, one | – | 76.90 | – | −13.6 dB | 76.90 |
| X1 absent, micro | **118.12** | – | −7.5 dB | – | 118.12 |
| **X2 absent, both** | – | **74.53** | – | −14.7 dB | **74.53** |
| X3 absent, one | – | 89.67 | – | −11.0 dB | 89.67 |
| X4 absent 6 mm, both | – | 74.53 | – | −22.0 dB | 74.53 |
| C1 thru | 52.61 | 50.19 | −27.3 | −49.6 | 50.19 |
| C2 open | n/a (Γ = 1) | n/a (Γ = 1) | 0 dB | 0 dB | ∞ |
| C3 short | n/a (Γ = 1) | n/a (Γ = 1) | 0 dB | 0 dB | 0 Ω |
| C4 load | 49.9 | 49.9 | < −30 | < −30 | 49.9 |

Reading the table: **the reference coupons separate by 1.2 Ω steps (R2 52.6 / R7 51.4 / R5 50.2)
and the void coupons separate by 44 Ω (X1 118.1 / X2 74.5).** Any single run of the X family
settles the question; the R family then says *which* variant of the coplanar model the board is.

Also note what the board would read if you could probe it directly (from the measured geometry,
`coupon_expected.json:board_*`): **−10.6 dB (M) vs −17.5 dB (C)** worst in band. That is the
stake: 7 dB of return loss and a decision about whether to re-pour In1 at all.

---

## 6. REFUTATION_CRITERION

**One line:** *If X2 (board-exact void, stitched coplanar, 0.35 mm) measures ≥ 95 Ω the coplanar
return is inert and wave-1's microstrip void bracket 65–118 Ω stands; if it measures 70–80 Ω
wave-1's bracket is refuted and the In1 void is not this board's defect; if it measures 85–95 Ω
the truth is the one-sided pour and both models are wrong.*

The full decision table (each row is a coupon result, not a model preference):

| observation | conclusion | consequence for the board |
|---|---|---|
| X2 = 74.5 ± 2 and X1 = 118 ± 2 | coplanar return is real and dominant | board Z0 50–75 Ω, S11 ≈ −17.5 dB; the In1 net assignment is second-order; the fix is void + stitching, not a re-pour |
| X2 = 118 ± 3 (≈ X1) | coplanar pour is floating / too sparse to matter | wave-1 stands: 11.2 % of the run at 114–118 Ω, S11 −10.5 dB, re-pour In1 |
| X2 = 89.7 ± 2 (≈ X3, ≠ X1, ≠ X2-as-built) | the board's real pour is one-sided | neither published number is usable; Z0 51.4 solid / 89.7 voided |
| V2 ≠ 71.8 ± 2 while X2 = 74.5 ± 2 | endpoints right, transfer curve wrong | partial voids do not behave as modelled; the 11.2 % area fraction cannot be mapped at all |
| X4 (6 mm) ≠ X2 (15 mm) by > 2 Ω | the local-cross-section (2D) assumption fails | every Z0 number in this report and in wave-1 is inadmissible; go 3D |
| R2 ∉ 52.6 ± 0.8 or R5 ∉ 50.2 ± 0.8 | the 2D cross-section solver is wrong (h, εr, edge profile) | the model must be recalibrated before any S11 claim is made |
| R2 − R5 < 0.5 Ω | the coplanar pour has no electrical effect | R4/R6/R7 are moot; use the microstrip column |
| R8 ≠ R5 by > 0.5 Ω | a decoupled 3V3 plane is not an RF ground | wave-1's "ideal 0 V" assumption is refuted; the net name matters after all |

The **most valuable single outcome** is the first row: if X2 lands at 74.5 Ω, then the entire
published 65–118 Ω bracket was an artifact of a missing 0.25 mm of copper, and the board's real
problem is not the plane net at all.

---

## 7. Cost (estimate — no quote obtained; `web_search` unavailable in this session)

| line item | qty | unit | total |
|---|---|---|---|
| PCB, 4-layer 1.6 mm ENIG, panel 140 × 205, 5 pcs | 1 | ~US$85–120 | **$100** |
| SMA end-launch jack, 1.6 mm, 50 Ω | 33 | $3.50–5.50 | **$150** |
| 49.9 Ω 0402 thin film | 10 | $0.30 | $3 |
| Assembly (hand, 2 h) | – | – | $0 (or $30 JLC SMT setup) |
| Shipping (DHL, 8–10 days) | 1 | – | $30 |
| **Hardware total** | | | **≈ $310 ± 60** |
| Measurement | | 2–3 h on a ≥9 GHz 2-port VNA with TDR option + 3.5 mm cal kit | in-house $0; outsourced $300–600/day |

Basis: 5 pcs × 287 cm² = 1435 cm² at the typical 4-layer ENIG rate of $0.055–0.075/cm².
**This is an estimate, not a quote.** JLCPCB's 4-layer price for a customer-panelled
140 × 205 mm design must be confirmed before ordering.

**Reduced set if the budget is < $150:** R2, R5, V2, X1, X2, C1–C4 (9 coupons, 14 SMA,
~70 × 95 mm strip ≈ $45 PCB + $60 SMA + $30 shipping ≈ **$135**). It still answers the central
question (which cross-section) but loses the width ladder, so the 1.2 Ω reference separation
falls inside the etch-bias uncertainty.

---

## 8. Provenance, assumptions, UNVERIFIED

**Made for this item (every number reproducible from a file here):**
`board_void_scan.json` (lateral In1 geometry, coplanar pour, void runs), `stitch_vias.json`,
`coupon_expected.json` (all coupon Z0/εeff/S11 + the board cascades), `coupon_list.json`,
`scripts/board_void_scan.py`, `scripts/coupon_expected.py`, `scripts/oneside_check.py`,
`scripts/build_coupon_list.py`.

**Reused from wave-1, cited, not re-derived:** 52.61 / 118.12 / 83.06 Ω and the 65–118 Ω bracket
(`da-em-field/REPORT.md:16-21,156-166`); S11 −10.5 dB (`:192`); the 0.20 mm dielectric and
εr 4.2 (`:66-74`); 51.2 Ω and 0.365 mm (`da-stackup/REPORT.md:160,163-166`); 102.35 mm run and
the 88.86 %/11.14 % split (`:54-62`); the coplanar-pour caveat (`da-em-field/REPORT.md:226-228`).

**UNVERIFIED / assumptions:**

1. **No coupon exists; nothing was measured.** Every expected reading is analytical 2D. The
   coupon is the instrument that converts this table into data.
2. **2D quasi-static, no radiation, no via inductance.** The coplanar ground is modelled as a
   perfect 0 V Dirichlet region. Real stitching vias have ~1 nH each; at 5 mm pitch the return
   impedance is small but not zero, and it is exactly what R4–R6 (stitched) vs R7 (one side)
   bracket rather than assume.
3. **The board's mixed pour is bracketed, not reproduced.** 50 % both-side + 46 % one-side
   becomes three coupons (R5, R7, and the same for the void cases); the true mixed line is
   somewhere between and is *not* a coupon in this set.
4. **In1 is /3V3 on the board, /GND on the coupons** (except R8). The coupon therefore measures
   the geometry, not the plane's RF impedance; R8 is the single probe of that question.
5. **The defect window (15 mm) is 5× the board's longest measured void (2.94 mm)** — deliberate,
   for TDR resolution — and X4 exists to prove that length does not change the plateau. If X4
   fails, this magnification is invalid.
6. **The board-side void scan has a 0.02 mm ray grid and steps 0.1 mm along the run**; widths
   are ±0.02 mm and contiguous-run lengths are a lower bound (segment ends split runs).
7. **Cost figures are estimates**, and the JLC 4-layer price for a customer-panelled design was
   not obtainable here (`web_search` returns a provider-conflict error, as wave-1 also found).
8. **No coupon PCB was drawn.** This is a specification complete enough for a CAD tech; the
   `.kicad_pcb` (footprints, zones, DRC) is the next item.

---

## 9. Reproduction

```powershell
# board geometry: lateral In1 void + coplanar pour  (KiCad 9 pcbnew, read-only)
& "C:/Program Files/KiCad/9.0/bin/python.exe" E:/engineering-portfolio-audit/evidence/w2-da-tdr/scripts/board_void_scan.py

# coupon expectations: 18 FD cross-sections (Windows python 3.12, numpy/scipy)
& "C:/Program Files/Python312/python.exe" E:/engineering-portfolio-audit/evidence/w2-da-tdr/scripts/coupon_expected.py

# full-domain / one-sided check
& "C:/Program Files/Python312/python.exe" E:/engineering-portfolio-audit/evidence/w2-da-tdr/scripts/oneside_check.py

# assemble the orderable list
& "C:/Program Files/Python312/python.exe" E:/engineering-portfolio-audit/evidence/w2-da-tdr/scripts/build_coupon_list.py
```

| file | contents |
|---|---|
| `REPORT.md` | this document |
| `coupon_list.json` | the 20-coupon orderable specification |
| `coupon_expected.json` | every Z0/εeff/S11, both models, all widths |
| `board_void_scan.json` | per-0.1 mm In1 void width, coplanar pour distance, void runs |
| `stitch_vias.json` | GND via distances to the RF run |
| `scripts/*.py` | everything above, re-runnable |
| `coupon_run.log` | solver log |