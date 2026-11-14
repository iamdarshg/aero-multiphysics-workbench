# drone-arm 915 MHz matching network — design to 50 Ω over 902–928 MHz

> ## ⛔ SUPERSEDED IN PART — HOTFIX 1 (2026-11-14)
>
> This is the **original report** (`evidence/da-match-design/REPORT.md`, SHA256
> `4B9FF55…07E6E`), kept unedited for the record. An adversarial verifier rejected
> two claims. Every number marked **⛔** below is superseded; the repair is
> **HOTFIX 1 at the end of this file**, and that section is the text to quote.
>
> | superseded claim | why it failed | replacement |
> |---|---|---|
> | "≤ −15.7 dB for every effective height 0.10–0.58 mm (Z0 33–87 Ω)" (§0, §7) | the 0.10 mm row was never in `tables.txt` (lowest 0.200); 87 Ω stops short of the 118 Ω void the FD item measured | 0.100 mm row computed (−19.60 dB at Z0 32.7); range extended to the FD void limit, Z0 118.3 Ω (h 1.39 mm), where the uniform model gives −3.78 dB |
> | "−24.5 dB worst over all void fractions" (§0, §5.1) | rests on a *uniform effective height*, i.e. one Z0 for the whole line; the FD solve shows 52.6 Ω solid pour alternating with 118 Ω void sections | cascaded sections at 52.61/118.12 Ω: **−25.1 dB** with the board's actual fills (0.00 mm void on the PA→J40 path); **−11.5 … −32.3 dB** if the 11.14 % fraction is forced onto that path |
> | "the entire plausible void range and well past it" (§0) | the 11.11 % void is real, but it lies on CC_PA / CC_LNA_N / CC_LNA_P / GNSS_RF_IN — not on the matching path | scope corrected in HOTFIX 1 §H3 |
>
> Unaffected by the rejection: the as-built diagnosis (§4), the topology read from the
> netlist (§1), the R_opt = 10.07 Ω criterion (§2), the E24 value set (§5), and the
> stub-length corrections (§5.3). Those numbers stand.

Evidence directory: `E:/engineering-portfolio-audit/evidence/da-match-design/`
HOTFIX 1 evidence: `E:/engineering-portfolio-audit/evidence/hf-da-match/`
Scripts: `E:/engineering-portfolio-audit/scripts/da_match_*.py`
Read-only on all repos. Nothing in any repo was modified.

---

## 0. Summary

| | worst in band, 902–928 MHz |
|---|---|
| as-built (MATCH_A/MATCH_B as populated) | **−0.86 … −2.34 dB** (badly mismatched, VSWR 6.7–18) |
| proposed (six component changes on existing pads, no layout change) | **−24.5 dB** at the worst of the four void fractions; −19.3 dB even if C94 is left unfitted |

> ⛔ **SUPERSEDED (−24.5 dB).** That figure assumed one uniform effective height for
> the whole line. The FD solve measures two alternating impedances (52.61 Ω solid /
> 118.12 Ω void). Cascaded: **−25.09 dB** on the board as drawn, where the PA→J40
> path has **0.000 mm** of void; **−11.46 dB** worst placement if 11.14 % of that path
> is voided. See HOTFIX 1 §H3.

The central worry in the brief — "the void is what makes impedance unknown" — turns out **not** to be
the limiting error. The proposed network holds ≤ −15.7 dB for every effective height from 0.10 mm to
0.58 mm (Z0 33 … 87 Ω), i.e. the entire plausible void range and well past it. The limiting errors are
component tolerance and the fact that the In1 plane is **3V3, not a ground plane** — neither of which
this analysis can settle.

> ⛔ **SUPERSEDED (the 0.10–0.58 mm / Z0 33–87 Ω / "entire plausible range" claim).**
> Three separate faults: (a) the 0.10 mm row exists nowhere in `tables.txt`, whose lowest
> row is 0.200 mm; (b) 87 Ω is 0.576 mm, but the FD item's void state is 118 Ω; (c) the
> uniform model has no standing once the line is modelled as alternating sections.
> The 0.10 mm row is now computed (**−19.60 dB, Z0 32.7 Ω**), the sweep is extended to
> the FD void limit (Z0 118.3 Ω at h = 1.39 mm, **−3.78 dB**), and the corrected
> statement is scoped in HOTFIX 1 §H2/§H3. The part that survives: the void is still
> not the dominant error *on the matching path*, because the matching path has no void.

---

## 1. What the files actually contain

### 1.1 Netlist (authoritative for connectivity)

```
"C:/Program Files/KiCad/9.0/bin/kicad-cli.exe" sch export netlist --format kicadxml \
  -o evidence/da-match-design/main_rev_b.net.xml \
  repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_sch
```
→ exit 0, 285 655 bytes. Every net below is quoted from that export.

Schematic labels for these nets live at
`repos/drone-arm/hardware/main/rev_b/rf_915.kicad_sch:8265-8635`
(`SAW_PA` 8265/8315/8335, `MATCH_A` 8485…8595, `MATCH_B` 8585…8635).

### 1.2 Current MATCH_A / MATCH_B topology (one line)

CC1121 (U40) → FL40 balun/filter → FL41 B39921 SAW → `SAW_PA` → L42 10 nH + C88 0.8 pF →
CC1190 PA_IN (U41) → `RF_PA_OUT` → **C90 47 pF (DC block)** → `MATCH_A` → **L48 2.9 nH**
( ‖ `C94` 2.4 pF, **DNP**) → `MATCH_B` → **L49 9.1 nH** → `ANT_915` → U.FL J40,
with shunts **C91 3.3 pF** on MATCH_A, **C95 7.5 pF** on MATCH_B, **C96 2.7 pF (DNP)** on ANT_915,
and the receive tap **L47 7.5 nH → C92 12 pF → TR_SW** also hanging on MATCH_A.

Net contents from the export (`ref(pin)`):

```
/915 MHz RF/MATCH_A : C90(2), C91(1), C94(1), L47(1), L48(1)
/915 MHz RF/MATCH_B : C94(2), C95(1), L48(2), L49(1)
/915 MHz RF/ANT_915 : C96(1), J40(1), L49(2)
/915 MHz RF/RF_PA_OUT : C90(1), L46(2), U41(2)
/915 MHz RF/SAW_PA  : C88(1), FL41(2), L42(1)
```

Values (netlist `<components>`, all 0402 except L46 0603 and the two filters):

| ref | value | part | role |
|---|---|---|---|
| C90 | 47 pF C0G | 0402 | PA DC block |
| L46 | 22 nH | 0603 | PA bias choke (TI reference: 10 nH) |
| C91 | 3.3 pF C0G | 0402 | shunt, MATCH_A |
| L48 | 2.9 nH | 0402 | series MATCH_A→MATCH_B (TI: 2.2 nH) |
| C94 | 2.4 pF **DNP** | 0402 | parallel across L48 |
| C95 | 7.5 pF C0G | 0402 | shunt, MATCH_B (TI: 8.2 pF) |
| L49 | 9.1 nH | 0402 | series MATCH_B→ANT (TI: **3.9 nH**) |
| C96 | 2.7 pF **DNP** | 0402 | shunt, ANT_915 (TI: 0.5 pF) |
| L47 | 7.5 nH | 0402 | RX tap (matches TI L22 7.5 nH) |
| C92 | 12 pF C0G | 0402 | RX tap (matches TI C22 12 pF) |
| FL41 | B39921B3588U410 | — | 915 MHz SAW |
| U41 | CC1190RGVR | — | PA / LNA front end |

The chain is a de-tuned copy of the TI CC1190EM 915 MHz reference (datasheet Table 1, p.5 of
`docs/datasheets/main/ti-cc1190.pdf`, extracted to `cc1190_text.txt:229-244`). Two departures matter:
**L49 is 2.3× the reference value** and **L48 1.3×**, while C94/C96 are not fitted at all.

### 1.3 Physical geometry (from pcbnew, not guessed)

`scripts/da_match_pcb_geom.py` via `"C:/Program Files/KiCad/9.0/bin/python.exe"` → `pcb_geom.json`.
All RF copper is on F.Cu, 0.35 mm wide. Lengths used in the model:

| element | length | note |
|---|---|---|
| U41.2 → C90.1 | 1.668 mm | |
| **choke stub** C90.1 → L46.2 | **3.055 mm** | bias choke sits 3 mm off the trace |
| C90.2 → MATCH_A node | 2.535 mm | |
| MATCH_A → C94 tee T | 1.595 mm | |
| T → C91.1 | **4.920 mm** | C91 shunt stub is **6.52 mm** total |
| MATCH_A → L47.1 | 3.035 mm | RX tap stub |
| MATCH_B → C94.2 stub | 1.595 mm | dangles when C94 is DNP |
| L48.2 → L49.1 | 3.030 mm | |
| MATCH_B → C95.1 | 3.140 mm | |
| L49.2 → C96.1 | 3.922 mm | |
| L49.2 → J40 | **11.506 mm** | the long run to the U.FL |

Two things a schematic-only reading gets wrong, and which change the answer:

1. **The shunts are not at the nodes.** C91 sits 6.5 mm of line away from MATCH_A, C95 3.1 mm from
   MATCH_B, C96 3.9 mm from the L49 pad. Those stubs already contribute 0.35–0.75 pF of shunt
   capacitance on their own, which is why the as-built 3.3 pF / 7.5 pF parts are *far too large*.
2. **There is 19 mm of 0.35 mm line** in the series path. At 915 MHz that is ~38° of electrical
   length — a matching element in its own right, not a wire.

### 1.4 Stackup and the reference plane

`main_rev_b.kicad_pcb:50-60`:

```
F.Cu 0.035 mm | dielectric 1 prepreg 0.200 mm FR4 er 4.2 tan_d 0.02 | In1.Cu 0.035 mm
dielectric 2 core 1.04 mm | In2.Cu | prepreg 0.200 mm | B.Cu
```

`docs/diagnostics-2026-11-10/rf_ground_audit.json` samples 11 centreline points of the ANT_915 run and
finds **In1.Cu = `/3V3`** at every one (lines 12, 26, … — 11 occurrences), with `/GND` only on B.Cu at
1.275 mm. So the RF trace is referenced to a **power plane**, and the nearest ground is 6× further away.

Microstrip Z0 for 0.35/0.200 mm, er 4.2 (scikit-rf `MLine`, Hammerstad-Jensen):
**51.20 Ω** with 35 µm copper, **53.79 Ω** at zero thickness. This sits inside the host-supplied
48.6–54.0 Ω bracket; the bracket is treated as model uncertainty, not as extra data.

---

## 2. The criterion — and why the obvious one is wrong

The brief asks for "S11 with a 50 Ω port at the antenna side". Taken literally as a 50 Ω/50 Ω two-port,
**TI's own reference network scores −2.32 dB** on this board's port pair
(`scripts/da_match_criterion.py`, ideal elements, no parasitics). A known-good design cannot fail by
12 dB, so the 50 Ω/50 Ω number is the wrong metric for this port pair, and I do not use it as the target.

The reason: the CC1190 is a 26.5 dBm PA running from 3.3 V, so its load-line optimum is

```
R_opt = (Vdd − Vsat)² / (2·Pout) = (3.3 − 0.3)² / (2 × 0.447 W) = 10.07 Ω
```

TI's reference match presents **|Z| = 10.2 Ω** (6.8 − j7.6) at the PA node — independent confirmation
that ~10 Ω, not 50 Ω, is what belongs at that end. **So the network is a 50 Ω ↔ 10 Ω transformer**, and
a 50/50 two-port *must* reflect.

Criterion actually used everywhere below:

* port 2 = **J40, 50 Ω** — this is the "50 ohm port at the antenna side" the brief asks about;
* port 1 = the CC1190 PA plane, terminated in **R_opt = 10.07 Ω**;
* Γ_ant = (Zin_J40 − 50)/(Zin_J40 + 50); target ≤ −10 dB for 902–928 MHz.

Both conventions are reported in §5 so nothing is hidden.

---

## 3. Model

`scripts/da_match_model.py`. Cascade of ABCD sections, one per real copper segment and part:

* every F.Cu segment at its measured length, width and stub topology, including dangling stubs where
  C94/C96 are unfitted (copper is there whether or not the part is);
* `Z0`, `γ`, `er_eff` from scikit-rf `MLine` at each void fraction;
* L: series R from Q = 45 at 915 MHz; C: ESR from Q = 200 plus 0402 ESL = 0.45 nH
  (the 47 pF DC block is near its own series resonance at 915 MHz, so the ESL is not cosmetic);
* C94, when fitted, joins MATCH_A and MATCH_B **in parallel with L48** — handled by adding the two
  paths' Y-matrices, not by a cascade;
* VDD / VSS at the top of L46 taken as AC ground through the choke.

**Validation — three independent algorithms, same netlist:**

| method | max ‖ΔΓ‖ vs ABCD cascade |
|---|---|
| admittance walk (tanh composition), `da_match_xcheck.py` | **8.3e-16** |
| nodal Y-matrix solve, `da_match_nodal.py` (incl. C94-fitted path) | **1.2e-14** |

Both agree with the ABCD cascade to machine precision, so the arithmetic and the topology
implementation are not in question. What remains uncertain is physics, not code (§7).

Sanity checks: a bare 19 mm line loses 0.10 dB (tan_d 0.02) and is passive; an ideal L+C network comes
out exactly passive (|S11|²+|S21|² = 1.000000).

### 3.1 Void / effective-er model

A void in In1 forces return current down to the B.Cu ground at 1.275 mm instead of the In1 plane at
0.200 mm. This is modelled as a current-weighted effective height,

```
h_eff(f_void) = 0.200 + f_void × (1.275 − 0.200)   [mm]
```

fed to `MLine`; the resulting `er_eff` and `Z0` are the effective-er perturbation the brief asks for.

| void | h_eff | Z0 @915 | er_eff @915 |
|---|---|---|---|
| 0 % | 0.200 mm | 51.2 Ω | 3.056 |
| 5 % | 0.254 mm | 58.6 Ω | 3.002 |
| 11.14 % | 0.320 mm | 66.1 Ω | 2.955 |
| 20 % | 0.415 mm | 75.0 Ω | 2.909 |
| 35 % | 0.576 mm | 86.5 Ω | 2.867 |

This is a first-order electrostatic argument (linear interpolation of return-path depth), **not** a
field solution; it deliberately spans a pessimistic range so the design cannot be flattered by it.
The 11.14 % figure is the host-supplied measurement; it is not reproducible from any file in the repo
(searched `docs/`, `evidence/`) and is carried as an input, not as my own result.

> ⛔ **SUPERSEDED as a model (the table above is kept only as the old sensitivity).**
> "One effective height for the whole line" is the wrong object. An In1 void does not raise
> the impedance of the whole trace; it inserts 118 Ω *sections* into a 52.6 Ω line. The
> corrected model cascades sections at the two FD-measured states. Two corrections to the
> paragraph above: the 11.14 % figure **is** now reproducible — the board's own In1 filled
> polygons give 11.371 mm of void in the 102.354 mm 0.35 mm RF set = **11.11 %** — and it is
> not spread over the run: 100 % of it sits on CC_PA, CC_LNA_N, CC_LNA_P and GNSS_RF_IN.
> HOTFIX 1 §H3.

---

## 4. Result — the as-built network

Γ_ant, PA plane at R_opt = 10.07 Ω (`da_match_final.py`):

| void | Γ@915 | worst in band | at | Zin at J40 |
|---|---|---|---|---|
| 0 % | −2.63 dB | −2.34 dB | 928 MHz | 22.4 + j67.8 |
| 5 % | −1.86 dB | −1.66 dB | 928 MHz | 17.0 + j72.5 |
| **11.14 %** | **−1.35 dB** | **−1.20 dB** | **928 MHz** | **13.2 + j77.0** |
| 20 % | −0.95 dB | −0.86 dB | 928 MHz | 10.2 + j82.1 |

At the designed void fraction the antenna sees 13.2 + j77.0 Ω — VSWR ≈ 13, so about 73 % of the
incident power is reflected. Under the literal 50/50 convention it is S22 = −1.48 dB (0 %) /
−1.00 dB (11.14 %). The device end is no better: with a 50 Ω antenna the PA plane sees
2.8 + j16.6 Ω, i.e. −1.28 dB against R_opt.

Node-by-node walk (`da_match_profile.py`, port 1 terminated in R_opt, f_void = 11.14 %, 915 MHz).
Each row is the impedance at that node looking back toward the PA:

```
after section                    Zin (ohm)        G (dB)
U41.2                            10.1  +3.6j       -3.55
+ 22 nH choke (3.05 mm stub)      9.7  +4.0j       -3.37
+ C90 47 pF DC block              9.7  +2.9j       -3.39
+ 2.535 mm line -> MATCH_A        9.8  +8.4j       -3.37
+ L47/C92 RX tap                  6.5  +8.2j       -2.20
+ C91 3.3 pF (6.52 mm stub)      11.1  +7.8j       -3.81
+ L48 2.9 nH                     11.4 +24.5j       -3.21
+ C94 stub (unfitted)            11.9 +24.9j       -3.33
+ 3.030 mm line -> L49           13.1 +32.5j       -3.18
+ C95 7.5 pF (3.14 mm stub)       4.6 -19.4j       -1.40   <-- collapses
+ L49 9.1 nH                      5.8 +32.9j       -1.41
+ C96 stub (unfitted)             6.7 +35.0j       -1.56
+ 11.506 mm line -> J40          13.2 +77.0j       -1.35   = antenna sees this
```

The network is least wrong nearest the device: Γ sits at −3.2 … −3.8 dB from U41.2 through to L48 and
then degrades monotonically outward to −1.35 dB at J40. The 9.8 + j8.4 Ω at MATCH_A is at least the
right order for an optimum of 10.07 Ω, but the antenna half is where it fails — C95 (7.5 pF) drags the
node to 4.6 − j19.4 Ω, L49 (9.1 nH, +52 Ω at 915 MHz) swings it to +j33 Ω, and 11.5 mm of line turns
that into 13.2 + j77 Ω. L49 alone, as a series element into a 50 Ω antenna, caps the achievable match
at −6.7 dB.

---

## 5. Proposed design

Six component changes on pads that **already exist** — four re-values plus two DNP pads now
populated. No track, no layer, no footprint, no layout change. The board is reworked by swapping
0402 parts.

| | pad | now | **proposed** | line |
|---|---|---|---|---|
| C91 | shunt on MATCH_A, 6.52 mm stub | 3.3 pF | **4.7 pF** C0G 0402 | existing, fitted |
| L48 | series MATCH_A→MATCH_B | 2.9 nH | **1.5 nH** 0402 | existing, fitted |
| C94 | parallel across L48 | 2.4 pF DNP | **2.7 pF** C0G 0402 | existing pad, **now fit it** |
| C95 | shunt on MATCH_B, 3.14 mm stub | 7.5 pF | **0.82 pF** C0G 0402 | existing, fitted |
| L49 | series MATCH_B→ANT_915 | 9.1 nH | **1.0 nH** 0402 | existing, fitted |
| C96 | shunt on ANT_915, 3.92 mm stub | 2.7 pF DNP | **3.3 pF** C0G 0402 | existing pad, **now fit it** |

Unchanged: C90 47 pF, L46 22 nH, L47 7.5 nH, C92 12 pF, and all four filter/IC parts.
All six values are on the E24 ladder (verified in `tables.txt`; note C95 = 0.82 pF, not 0.8 pF).

### 5.1 Modelled performance

| void | Γ@915 | worst in band | at | Zin at J40 |
|---|---|---|---|---|
| 0 % | −29.57 dB | −26.16 dB | 902 MHz | 52.9 − j1.8 |
| 5 % | −28.56 dB | −24.70 dB | 902 MHz | 53.2 − j2.1 |
| 11.14 % | −32.55 dB | −26.29 dB | 902 MHz | 51.5 − j1.8 |
| **20 %** | −32.44 dB | **−24.48 dB** | 928 MHz | 47.7 + j0.3 |
| 35 % | −18.30 dB | −15.66 dB | — | — |

**Worst over the four required void fractions: −24.48 dB.** Margin over the −10 dB target: 14.5 dB.
Worst-case VSWR ≈ 1.13.

> ⛔ **SUPERSEDED (−24.48 dB, and "worst over the four void fractions").** Four uniform-h
> points are not "all void fractions" — that is the overstatement the verifier caught. With
> the same uniform model swept to its own end point it degrades to −15.67 dB at 0.576 mm and
> −3.78 dB at Z0 118.3 Ω. With the FD-correct cascade: −25.09 dB on the board as drawn,
> −11.46 dB in the worst forced-void placement. HOTFIX 1 §H2/§H3.

If C94 is left unfitted (fewer parts to place), the same other five values still give **−19.29 dB**
worst in band — so C94 is a fine-tune, not a requirement.

### 5.2 In-band detail (Γ, dB, 2 MHz steps; full 521-point data in `sweep_915.csv`)

```
   MHz   now/0%  now/11%  now/20%   prop/0%  prop/11%  prop/20%
   902    -2.98    -1.52    -1.07    -26.16    -26.29    -37.51
   910    -2.76    -1.41    -1.00    -28.44    -30.02    -40.27
   916    -2.61    -1.33    -0.95    -29.72    -32.97    -31.48
   920    -2.51    -1.29    -0.92    -30.02    -33.79    -28.44
   928    -2.34    -1.20    -0.86    -28.98    -31.00    -24.48
```

### 5.3 Why these values — and what the stubs mean

The optimizer's answer is physically sensible once the stubs are counted:

* **C95 falls to 0.82 pF** because its 3.14 mm stub is already ≈ 0.35 pF of shunt capacitance. The
  as-built 7.5 pF was 6× too much.
* **C91 rises to 4.7 pF** because its 6.52 mm stub presents ≈ 0.75 pF and then *transforms* the
  capacitor; the fitted part has to be larger, not smaller, than the reference value.
* **L49 9.1 nH → 1.0 nH**: at 915 MHz 9.1 nH is +52 Ω in series with a 50 Ω antenna. That alone limits
  the match to −6.7 dB. 1.0 nH is essentially "a short with the lowest inductance 0402 allows".
* **C94 fitted at 2.7 pF** across the new 1.5 nH L48 turns the series element from +j8.6 Ω into
  +j10.0 Ω. A 15 % reactance shift, but it pushes the worst-case null 5 dB deeper
  (−19.3 → −24.5 dB). It is a trim, not a structural element — see §5.1.

### 5.4 Per-void tuning chart (if you measure the real void fraction)

`e24_refine.json`. Every column is the best E24 set for that void fraction alone; the values barely
move, which is the real reason one value set covers the whole range:

| void | worst | C91 | L48 | C94 | C95 | L49 | C96 |
|---|---|---|---|---|---|---|---|
| 0 % | −30.43 dB | 5.1 | 1.6 | 2.2 | 0.91 | 1.0 | 3.3 |
| 5 % | −30.52 dB | 5.1 | 1.6 | 2.4 | 0.91 | 1.1 | 3.3 |
| 11.14 % | −29.17 dB | 4.7 | 1.5 | 1.5 | 0.82 | 1.0 | 3.3 |
| 20 % | −29.06 dB | 4.7 | 1.5 | 3.3 | 0.75 | 1.0 | 3.3 |

Units pF for capacitors, nH for inductors.

---

## 6. Robustness (all on the proposed set)

| perturbation | worst in band |
|---|---|
| effective height 0.10 → 0.576 mm (Z0 33 → 87 Ω) | −19.75 … −15.66 dB; deepest −28.0 dB at 0.15 mm, degrades to −6.7 dB only beyond 1 mm |

> ⛔ **SUPERSEDED row, with the missing point now filled in.** The 0.10 mm value existed
> only in the script output, never in `tables.txt`; re-run against the final BOM (C95 =
> 0.82 pF, not the 0.80 pF used for this row) it is **−19.60 dB** at Z0 32.68 Ω, and the
> 0.15 mm point is −27.63 dB. The row also stopped at 87 Ω; the full sweep to the FD void
> limit is −19.60 … −3.78 dB over h = 0.100 … 1.390 mm, and −3.01 dB at 1.60 mm.
> Complete table: HOTFIX 1 §H2. **A −15.7 dB floor is not a property of this design; it is
> a property of a 0.10–0.58 mm slice of one model.**
| ±5 % on every L and C, ±0.10 mm on every stub, 400 trials | median **−21.4 dB**, 10–90 % **−19.5 … −23.5 dB**, meets −10 dB in **100 %** of trials |
| R_opt = 7 Ω (PA more compressed than assumed) | −13.76 dB |
| R_opt = 12 Ω | −22.15 dB |
| receive tap open instead of grounded at TR_SW | −12.11 dB worst (fv = 20 %) |

The design survives every one of these variants above −10 dB. The two that eat the most margin are
**R_opt below 8 Ω** and **the RX tap being open rather than grounded in TX** — both are modelling
assumptions, not measurements (§7).

---

## 7. Residual risk — what fabrication and a VNA must settle

Stated plainly, in order of how much it can move the answer:

1. **The In1 plane is 3V3, not ground.** This model treats it as a solid reference and only
   parameterises its *voids*. In reality a power plane with 11 % void and no local stitching is a
   poor and lossy RF reference; it also carries digital switching current under the RF run. The
   effective height sweep bounds the *impedance* consequence (≤ −15.7 dB across 0.10–0.58 mm) but
   **cannot** bound coupling from whatever else is on 3V3. The only real fix is a ground pour with a
   stitching fence along the trace, which is a layout change and outside this assignment.

> ⛔ The parenthetical **"(≤ −15.7 dB across 0.10–0.58 mm)"** is superseded; the sentence's
> physical point stands. The bound is not −15.7 dB — see HOTFIX 1 §H2 (uniform model,
> −19.60 … −3.78 dB over 0.10–1.39 mm) and §H3 (cascade, −25.1 dB real / −11.5 dB worst
> forced void).
2. **R_opt = 10.07 Ω is a load-line estimate, not a load-pull measurement.** TI does not publish the
   CC1190's optimum load impedance in SWRS089; AN001/SWRA090 was not available. Margin holds at
   −13.8 dB for R_opt = 7 Ω and −22.2 dB at 12 Ω, but a substantially lower optimum would need a re-tune.
3. **Component tolerance in situ is larger than the ±5 % modelled.** At 1.0–1.5 nH the 0402 body
   inductance is comparable to the pad and trace inductance, so L48/L49 will read high. Expect the
   built board to need one iteration on L48/L49 — tune those two against a VNA, in that order
   (L49 first: it dominates).
4. **The TR_SW state in TX is assumed, not known.** Grounded (used for the headline numbers) vs open
   costs about 12 dB of margin: −24.5 dB vs −12.1 dB.
5. **C94 = 2.7 pF across L48 is a fine-tune whose value depends on assumptions 1–3.** If it is left
   unfitted the design still meets the target by 9 dB, which is the safer build.

### What a VNA must confirm (all currently UNVERIFIED)

* **S11 at J40, 902–928 MHz, board powered, PA in TX** — the only number that settles the design. No
  VNA measurement of any kind exists for this board in the repo; every figure here is modelled.
* TDR or a swept S11 with the PA plane terminated in 10 Ω, to establish the real Z0 of the 19 mm run
  and hence the true void/effective-height condition.
* The actual void fraction and copper coverage of In1 under the RF corridor (the 11.14 % figure is
  carried from the brief; nothing in the repo computes it).
* Load-pull or a power sweep of the CC1190 at 3.3 V to replace R_opt = 10.07 Ω with a measured value.
* No full-wave solver was run. openEMS exists for WSL but was not used: no simulation of the plane
  void, no 3-D model of the U.FL launch or the 3V3 reference.

---

## 8. Reproducing this

```
# netlist and geometry
"C:/Program Files/KiCad/9.0/bin/kicad-cli.exe" sch export netlist --format kicadxml \
    -o evidence/da-match-design/main_rev_b.net.xml hardware/main/rev_b/main_rev_b.kicad_sch
"C:/Program Files/KiCad/9.0/bin/python.exe" scripts/da_match_pcb_geom.py > .../pcb_geom.json

# model, validation, synthesis, tables  (system python 3.12 + scikit-rf 1.9.0)
python scripts/da_match_model.py       # media table + as-built result
python scripts/da_match_criterion.py   # why R_opt, not 50 ohm, is the criterion
python scripts/da_match_xcheck.py      # validation 1: admittance walk   (8e-16)
python scripts/da_match_nodal.py       # validation 2: nodal solve       (1e-14)
python scripts/da_match_synth.py       # E12 grid + E24 coordinate descent
python scripts/da_match_e24.py         # strict E24 re-refinement
python scripts/da_match_final.py       # results.json, sweep_915.csv
python scripts/da_match_tables.py      # tables.txt
python scripts/da_match_profile.py     # nodewalk.txt
python scripts/da_match_sens.py        # effective-height sweep (§6, §7)
```

Provenance of every number: **analytical / transmission-line model** (scikit-rf `MLine` + ABCD
cascade), never a solver result. The only measured inputs are the KiCad board data (track lengths,
pad positions, stackup) and the host-supplied 11.14 % void fraction. Files in this directory:

| file | what |
|---|---|
| `main_rev_b.net.xml` | netlist export the topology is read from |
| `pcb_geom.json` | track, pad, zone and stackup dump |
| `cc1190_text.txt` | extracted CC1190 datasheet text (Table 1 reference values) |
| `results.json` | all Γ / Zin tables, Monte Carlo, R_opt sweep |
| `sweep_915.csv` | 521-point Γ and Zin, current and proposed, four void fractions |
| `e24_refine.json` | final E24 search results and per-void optima |
| `synth_search.json` | first-pass E12 grid and descent |
| `tables.txt` | human-readable tables quoted above |
| `nodewalk.txt` | node-by-node impedance walk of the as-built network |
---

# HOTFIX 1 — repair of the two rejected claims (2026-11-14)

Scope of this repair: **the two defects only.** The topology read from the netlist, the
as-built diagnosis, the R_opt = 10.07 Ω criterion, the E24 component set and the stub
corrections are not re-derived here and are not challenged by the rejection.

## H1. What the verifier rejected (verbatim)

> It claims -15.7 dB over 0.10-0.58 mm with Z0 33-87, but the 0.10 mm point is absent from
> its own tables.txt (lowest is 0.200), and 87 ohm excludes the 118 ohm void that the sister
> FD report measured, so the claim to cover the entire plausible void range is false.
> Separately, the -24.5 dB figure across all void fractions rests on a uniform effective-height
> model that the FD report contradicts.

Both findings are correct. Defect 1 is a **scope** defect: a real number was attached to a range
it does not cover, and one point of that range was never tabulated. Defect 2 is a **model**
defect: with a uniform effective height, "void fraction" cannot produce a 118 Ω section, so the
−24.5 dB answer was computed in a model the sister item had already falsified.

## H2. Defect 1 — the void range and the missing 0.10 mm row

### H2.1 The 0.10 mm row, computed

`tables.txt` (original) stops at 0.200 mm. The 0.10 mm point existed only in a script sweep, and
that sweep ran with C95 = 0.80 pF, not the 0.82 pF final BOM — which is why the quoted −19.75 dB
does not reproduce. Re-run against the final six values, uniform effective-height model, 521 points
902–928 MHz, Γ at J40 with the PA plane terminated in 10.07 Ω:

| h_eff (mm) | Z0 (Ω) | er_eff | Γ @ 915 | worst in band | at |
|---|---|---|---|---|---|
| **0.100** | **32.68** | 3.243 | **−21.36 dB** | **−19.60 dB** | 928 MHz |
| 0.150 | 42.92 | 3.129 | −34.78 | −27.63 | 928 |
| 0.200 | 51.20 | 3.056 | −29.57 | −26.16 | 902 |
| 0.300 | 64.02 | 2.968 | −30.70 | −25.50 | 902 |
| 0.415 | 75.01 | 2.909 | −32.44 | −24.48 | 928 |
| 0.576 | 86.50 | 2.863 | −18.31 | −15.67 | 928 |
| 0.700 | 93.46 | 2.840 | −13.69 | −11.87 | 928 |
| 0.850 | 100.44 | 2.821 | −10.17 | −8.83 | 928 |
| 1.000 | 106.33 | 2.807 | −7.81 | −6.75 | 928 |
| 1.100 | 109.79 | 2.799 | −6.63 | −5.72 | 928 |
| 1.200 | 112.96 | 2.793 | −5.69 | −4.91 | 928 |
| 1.275 | 115.17 | 2.788 | −5.10 | −4.40 | 928 |
| **1.390** | **118.32** | 2.782 | −4.36 | **−3.78** | 928 |
| 1.600 | 123.48 | 2.773 | −3.39 | −3.01 | 928 |

Z0 here is skrf `MLine` (Hammerstad-Jensen, t = 35 µm, er 4.2) at 915 MHz. The relation used to
extend the sweep to the FD void limit: 118.12 Ω is h_eff ≈ 1.385 mm in this model, hence the
1.390 mm row. Source: `scripts/hf_cascade.py`, table D of `hf_tables.txt`.

### H2.2 What the claim may now say

The original sentence — "holds ≤ −15.7 dB for every effective height from 0.10 mm to 0.58 mm
(Z0 33 … 87 Ω), i.e. the entire plausible void range and well past it" — is **withdrawn**. Three
separate problems, fixed as follows:

1. **0.10 mm not in the table** → computed and tabulated above (−19.60 dB). The value is real;
   the presentation was not.
2. **87 Ω is not the top of the plausible range** → the sister FD item's void state is
   **118.12 Ω**. The uniform sweep now runs to Z0 118.30 Ω (h = 1.39 mm), giving −3.78 dB. A
   −15.7 dB floor therefore does **not** hold over the range the original sentence claimed to
   cover; it only holds over a narrow slice of it.
3. **"the entire plausible void range"** → false as a scope statement and, after H3, wrong as a
   model. The void does not scale the line; it splits it.

Accurate statement of the uniform model alone:

> Uniform-line model, final BOM, 902–928 MHz: worst in band stays between −19.6 and −27.6 dB for
> h_eff ≤ 0.30 mm (Z0 ≤ 64 Ω), is −24.5 dB at 0.415 mm (75 Ω), then degrades monotonically —
> −15.7 dB at 0.576 mm (86.5 Ω), −6.8 dB at 1.00 mm (106 Ω), **−3.8 dB** at 118.3 Ω. This model
> is superseded by H3 and is not evidence about this board.

## H3. Defect 2 — the −24.5 dB figure, re-modelled as a cascaded line

### H3.1 The two states, as measured by the FD item

`evidence/da-em-field/REPORT.md` §4.1, 2D quasi-static Laplace solve on the real stackup:

| state | Z0 | eps_eff | provenance |
|---|---|---|---|
| In1 /3V3 solid under the trace | **52.61 Ω** (±2.6 % grid) | 3.328 | FD solve, `fd_results.json` |
| In1 absent (void), return via In2 /GND at 1.275 mm | **118.12 Ω** | 3.065 | FD solve |

A 2.25× impedance step. These are the two states the cascade uses; every line section is one or
the other, with γ from eps_eff and tanδ = 0.02 (dielectric loss only, matching the FD item's
convention).

### H3.2 Where the void sections actually are (measured, not assumed)

`scripts/hf_void_geom.py` and `scripts/hf_void_all.py` read the board's **own In1.Cu filled
polygons** (pcbnew 9.0.7) and sample every 0.35 mm F.Cu track at 10 µm. The 0.35 mm RF set is the
102.35 mm "RF_50R run" of the brief — 16 nets, two radios:

| net | len (mm) | void (mm) | void % | runs |
|---|---|---|---|---|
| CC_PA | 5.322 | 3.820 | 71.78 | 6 |
| CC_LNA_N | 3.463 | 3.433 | 99.14 | 2 |
| CC_LNA_P | 4.938 | 2.938 | 59.51 | 1 |
| GNSS_RF_IN | 11.070 | 1.179 | 10.65 | 2 |
| ANT_915 / MATCH_A / MATCH_B / RF_PA_OUT / SAW_PA / RF_PA_INOUT / RF_TR_SW / RX_COMBINE / RF_LNA_IN / CC_PA_BIAS / CC1121_RF / GNSS_RF_ANT | 77.561 | **0.000** | 0.00 | 0 |
| **TOTAL** | **102.354** | **11.371** | **11.11** | |

Two things follow, and they matter more than the S11 number:

* **The 11.14 % input is now reproduced from the board: 11.11 %.** The fills are the same data
  the brief summarised, and the 0.03 pp difference is sampling step. The original report's
  statement that the figure "is not reproducible from any file in the repo" is corrected: it is
  not in a document, but it is in the copper.
* **None of it is on the matching path.** The 11.371 mm of void is entirely on the CC1121 side
  (balun/LNA/PA pins, x ≈ 95–101 mm, y ≈ 61–65 mm, listed run by run in `hf_tables.txt`) and on
  GNSS_RF_IN at (94.6, 16.4). The run the matching network sees — U41.2 → J40, **20.334 mm** —
  is **0.000 mm void, 0.00 %**. Per line:

| line | path (mm) | model (mm) | void (mm) |
|---|---|---|---|
| L_PA_TO_C90 | 1.668 | 1.668 | 0.000 |
| L_C90_TO_MA | 2.535 | 2.535 | 0.000 |
| L_MA_TO_TEE | 1.602 | 1.595 | 0.000 |
| L_MB_MAIN | 3.030 | 3.030 | 0.000 |
| L_ANT_RUN | 11.506 | 11.506 | 0.000 |
| (stubs: L_CHOKE, L_TEE_TO_C91, L_MA_TO_L47, L_MB_TO_C94TAP, L_C95_STUB, L_C96_STUB) | 19.99 | 17.40 | 0.000 |

The pad-to-pad walk reproduces the model's measured lengths to ≤ 0.4 % (the exception,
L_C95_STUB 5.783 vs 3.140 mm, is a routing difference — the model attaches C95 at the MATCH_B
node, the copper hangs it off the junction 2.6 mm down the main run; both are solid).

### H3.3 The cascade

Same ABCD cascade, same component parasitics, same stub topology as `da_match_model.build()` —
the only change is the medium: each line section is assigned the FD state (Z0, eps_eff) of the
copper above it, and a line containing both states is split at the transition. Result at J40,
PA plane terminated in 10.07 Ω, worst over 902–928 MHz in 521 points:

| scenario | worst in band | at | Γ @ 915 | scope |
|---|---|---|---|---|
| **board as drawn, proposed set** | **−25.09 dB** | 928 MHz | −27.68 | measured fills, 0.000 mm void |
| board as drawn, as-built set | −1.94 dB | 928 | −2.19 | measured fills (sanity: still broken) |
| 11.14 % forced, 1 contiguous 2.265 mm, **worst placement** | **−11.46 dB** | 928 | −12.31 | synthetic |
| 11.14 % forced, contiguous, best placement (start 3.75 mm) | −32.34 dB | 928 | −44.78 | synthetic |
| 11.14 % forced, 4 voids × 0.566 mm | −19.33 dB | 928 | −20.77 | synthetic |
| 11.14 % forced, 8 voids × 0.283 mm | −20.86 dB | 928 | −22.58 | synthetic |
| 11.14 % forced, 16 voids × 0.142 mm | −24.20 dB | 928 | −26.54 | synthetic |

Contiguous-void placement sweep (73 positions, 0–18 mm from the PA plane):

| start (mm) | 0.00 | 1.00 | 2.00 | 3.00 | 4.00 | 5.00 | 6.00 | 8.00 | 10.0 | 12.0 | 14.0 | 16.0 | 18.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| worst (dB) | −11.53 | −11.47 | −11.74 | −18.31 | −28.53 | −17.95 | −13.28 | −20.79 | −21.83 | −22.36 | −22.96 | −23.63 | −24.40 |

**The answer to "if the cascaded result is worse than −24.5 dB, that is the answer": it is worse,
and by a lot, in the case that matters.** One contiguous 2.265 mm void in the first 2 mm of the
path costs ~13 dB: −11.46 dB. That still passes the −10 dB target, but by 1.5 dB, not 14.5 dB.
Why: a 118 Ω section sitting between the DC block and MATCH_A raises the impedance the L48/C91
pair was tuned against; the same void moved past 8 mm costs 4.3 dB or less because the network is
already transforming there and the two transitions partially cancel (H6, check 3).

### H3.4 Corrected S11 statement

> **Cascaded-line S11, real 52.61/118.12 Ω alternation, 902–928 MHz, PA plane at 10.07 Ω:**
> **−25.09 dB** on the board as drawn, where the PA→J40 path carries **0.000 mm of In1 void**
> (fills measured). If the brief's 11.14 % void fraction is instead forced onto that path, the
> same cascade gives **−11.46 dB to −32.34 dB** depending on placement, −20.86 dB for eight
> evenly spread voids. The void does not enter the matching-network answer through a uniform
> er/nothing model; it enters as 118 Ω sections, and only if the pour under this 20.3 mm is
> actually voided.

That is the scope-matched range: each number above is attached to the exact set of sections used
to compute it. There is no longer a single "worst over all void fractions", because "void
fraction" is not the right independent variable — **placement is**.

## H4. What may and may not be quoted now

Standing:
* board as drawn, proposed set: **−25.09 dB** worst in band (fills measured; 0.00 % void on path);
* as-built set: −1.94 dB (same conclusion as before: badly mismatched);
* E24 set, topology, criterion, stub corrections: unchanged from the original report;
* 118 Ω void state and 52.61 Ω solid state: attributed to `evidence/da-em-field/`, ±2.6 % grid.

Withdrawn, do not restate:
* "−24.5 dB across all void fractions" — superseded by H3.4;
* "≤ −15.7 dB for the entire plausible void range, 0.10–0.58 mm, Z0 33–87 Ω" — superseded by H2.2;
* "the void is not the limiting error in this design" as a general claim — it is true only for
  the board as drawn; a void on the match path costs up to 13 dB (H3.3);
* "the 11.14 % figure is not reproducible from any file in the repo" — it is now measured
  (11.11 %, `void_geom_all.json`).

## H5. STILL UNVERIFIED

1. **The fills are as saved.** The 0 % void on the match path is a property of this snapshot's
   `filled_polygon` data. A re-fill with different clearances, or a fabrication re-pour, changes
   it. Nothing here is a measurement of physical copper.
2. **The 52.61 / 118.12 Ω pair is a 2D quasi-static solve**, not full-wave: ±2.6 % grid, ideal
   0 V planes, no coplanar F.Cu pour, no connector or via discontinuity (da-em-field §5). The
   2.25× step is robust; the absolute values are not better than a few percent.
3. **Where a real void would sit is unknown** if the pour does change — the forced-void range
   (−11.46 … −32.34 dB) spans the answer, and no board data chooses a point in it.
4. **The −11.46 dB case keeps only 1.5 dB of margin**, inside the ~1 dB model error and the
   component-tolerance spread already reported (median −21.4 dB, p10 −23.5 dB on the uniform
   model). It is not a comfortable pass.
5. **No VNA measurement exists** for this board, and no load-pull for R_opt = 10.07 Ω. Unchanged
   from the original report.
6. **What would settle it:** a TDR / swept S11 at J40 with the PA plane at 10 Ω, plus the In1
   copper-to-trace clearance histogram along the 20.3 mm run (the quantity that decides whether
   the path is 52.6 Ω or partly 118 Ω).

## H6. Validation of this hotfix

1. **Reproduction** — `hf_cascade.build()` with MLine media returns **−26.16 dB**, identical to
   the original `da_match_model.build()` (−26.16 dB), so the topology/parts port is faithful.
2. **Segmentation invariance** — splitting every section into 7 sub-runs changes the answer by
   **3.6e−15 dB**; splitting a forced-void section into 3 changes it by 7.1e−15 dB. No
   per-section bookkeeping error.
3. **Hand check** — a single 52.61 → 118.12 Ω step is |Γ| = 0.3837 = **−8.32 dB**; 10 mm of
   52.6 Ω line containing 2.265 mm of 118 Ω gives **−20.80 dB** at 50/50 (the two transitions
   cancel over that length), consistent with the FD item's own sanity anchor (da-em-field §4.3).
4. **Passivity** — max |S11|² + |S21|² = 0.9493 (board fills), 0.9464 (forced void), 0.9476
   (8 voids): passive, loss from the L/C Q models.
5. **Cross-check of the void map** — per-net void lengths sum to 11.371 mm / 102.354 mm =
   **11.11 %** against the host-supplied **11.14 %**.

## H7. Reproducing HOTFIX 1

```
# KiCad python (pcbnew 9.0.7) - geometry, from the board's own fills
"C:/Program Files/KiCad/9.0/bin/python.exe" evidence/hf-da-match/scripts/hf_void_geom.py
"C:/Program Files/KiCad/9.0/bin/python.exe" evidence/hf-da-match/scripts/hf_void_all.py

# system python 3.12 + scikit-rf 1.9.0 - cascade and tables
python evidence/hf-da-match/scripts/hf_cascade.py     # cascade_results.json
python evidence/hf-da-match/scripts/hf_validate.py    # H6 checks
python evidence/hf-da-match/scripts/hf_tables.py      # hf_tables.txt
```

HOTFIX 1 artefacts (this directory):

| file | what |
|---|---|
| `void_geom.json` | per-line ordered SOLID/VOID runs along PA→J40, from In1 fills |
| `void_geom_all.json` | per-net void length and void runs for all 16 RF tracks |
| `cascade_results.json` | every scenario, the 73-position placement sweep, the h sweep, validation deltas |
| `hf_tables.txt` | tables A–E as printed |
| `scripts/hf_void_geom.py` | pcbnew fill sampling along the model's real line paths |
| `scripts/hf_void_all.py` | pcbnew fill sampling for every 0.35 mm F.Cu track |
| `scripts/hf_cascade.py` | FD-media ABCD cascade, forced-void placement, h sweep |
| `scripts/hf_validate.py` | reproduction / invariance / passivity / step checks |
| `scripts/hf_tables.py` | table generator |

Provenance label for every number in HOTFIX 1: **analytical cascade** over **FD-solve media**
(da-em-field) and **board-measured geometry** (pcbnew fills). No new field solve was run here; no
VNA data exists.
