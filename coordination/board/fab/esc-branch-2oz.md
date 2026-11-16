# ESC rev_b at 2 oz — the full redesign, priced

**Unit:** `esc-branch-2oz` · **Wave:** 7 · **Host:** KiCad 9.0.7 (`kicad-cli` 9.0.7, `pcbnew`
9.0.7 / Python 3.11), arithmetic in CPython 3.12. Every board below is a **copy** in
`evidence/esc-branch-2oz/boards/`. Nothing was written into a repo, nothing was committed,
no `audit/*` branch was touched.

**The question.** Price the ESC at 2 oz as a full redesign, so the owner can put it beside
the 4 oz branch. The 2 oz branch buys one thing: the **413 footprint-bound DRC items
disappear**. §3 shows that is real and reproduces. §1–§2 show what it costs.

| artefact | bytes | sha256 |
|---|---|---|
| `boards/orig.kicad_pcb` (board of record, copy) | 4,988,844 | `992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD` |
| `boards/esc_rev_b_2oz.kicad_pcb` (stackup only) | 4,817,087 | `0598F07B0543707FA52394923F28CFFE62FDB9894361E0BFA969EDDB30EB58AA` |
| `boards/esc_rev_b_2oz_powerfirst.kicad_pcb` | 2,821,335 | `BC10C208FA110A7795E7526CC63E377903EDC1BA0800A4B6ED3DB0B1EFD3748A` |
| `boards/esc_rev_b_2oz_railfix.kicad_pcb` (+1,590 vias) | 5,457,744 | `BF21E80EDD38E6BAF41542BC3AE8DFD2897B9D710EA6E0D59FFF2D8ADE5C38BB` |
| `boards/esc_rev_b_2oz_railfix2.kicad_pcb` (+1,938 vias, 48 solid pads) | 6,011,647 | `9CB48F40BB306FF9582E5AB56252E4168EAD93CB7F7068BEF061692863DC4482` |
| `boards/powerfirst.kicad_pcb` (4 oz, untouched) | 2,957,981 | `4FB519AB85026694BCD6287472CD759E93A80AD014C1B7F7E09C1819D743132C` |

The 2 oz copies are the 4 oz originals with exactly two substitutions — F.Cu and B.Cu
`(thickness 0.14)` → `0.070` — asserted at 2 substitutions and re-parsed before anything was
believed (`04_build.py:set_outer_thickness`).

---

## 0. The answer

| question | answer |
|---|---|
| Required width per phase at 2 oz | **27.963 mm on one outer face** (1.9574 mm²); **10.749 mm each** if F.Cu and B.Cu are paralleled; **17.479 mm** if F.Cu+In2 |
| What the placement offers | **7.400 mm** — 26.5 % of the required width, which carries **22.9 A = 38.2 % of 60 A** |
| Required width per battery rail | **1.9148 mm² = 27.963 mm of 2 oz** per rail, or **96.991 mm** if it stays on In1 (1.5 oz) |
| Rail fix, and the barrel count | **61 barrels per rail** (0.03142 mm² each). Executed: BATN **67.3 A (114 %) PASS**, BATP **48.0 A (81.3 %) FAIL** |
| MAX continuous per phase at 2 oz, spreader mandatory | **22.9 A** at ΔT 20 K — the copper, not the die. Junction with the spreader is **372 A**, so the spreader does nothing for the binding limit |
| Achievable area | **382.709 cm²** is achievable as a *placement* (0 DRC at 2 oz) but **not as a 60 A design**: 60 A forces **415.8 cm²** at best |
| Footprint DRC at 2 oz | **0** (from 413). Proven live, not asserted (§3) |
| Rail verdict | **BATP FAIL 48.0 A, BATN PASS 67.3 A** after an executed fix that itself costs 347 DRC items |
| Unconnected (pcbnew, uncapped) | **2,196** on the placement, **1,542** on the board of record, **1,530** after the fix (kicad-cli's 499 is its cap on every board) |
| Components on B.Cu | **0** on every state |
| **BUILDABLE + CAPABLE at 2 oz** | **NO.** Binding constraint: **the phase corridor's copper width** — 7.400 mm where 60 A needs 27.963 mm on F.Cu, so 22.9 A per phase |

---

## 1. The width book, and the four controls that let it be quoted

`02_widths.py` → `02_widths.json`, log `logs/02_widths.log`. IPC-2221 §6.2 closed form,
`A[mil²] = (I/(k·ΔT^0.44))^(1/0.725)`, k = 0.048 external / 0.024 internal.

**The instrument was run on four numbers this programme already settled by hand, and all
four reproduce:**

| control | got | settled | residual |
|---|---|---|---|
| C1 60 A, 20 K, 0.14 mm, k=.048 | 13.9813 mm | 13.981 | +0.002 % |
| C2 60 A, 20 K, 0.0525 mm, k=.024 | 96.9910 mm | 96.991 | −0.000 % |
| C3 45 barrels (0.4 drill, 25 µm) | 47.3913 A | 47.4 | −0.018 % |
| C4 cross-section at k=.024 | 5.0920 mm² | 5.092 | +0.001 % |

### 1.1 Required width at 2 oz, ΔT 20 K

2 oz means the **outers become 0.070 mm**; the inners stay 0.0525 mm (1.5 oz) and the via
plating stays 25 µm. That asymmetry is the whole story of this branch.

| conductor | 60 A (mm) | cross-section | 59.05 A (mm) |
|---|---|---|---|
| F.Cu alone @2 oz | **27.963** | 1.9574 mm² | 27.354 |
| B.Cu alone @2 oz | 27.963 | 1.9574 | 27.354 |
| F.Cu+B.Cu parallel @2 oz | **10.749** | 1.5048 (2×0.7524) | 10.515 |
| F.Cu+In1 parallel @2 oz | 17.479 | 2.1412 | 17.098 |
| F.Cu+In2 parallel @2 oz | **17.479** | 2.1412 | 17.098 |
| F.Cu+In1+In2 parallel | 12.319 | 2.1559 | 12.051 |
| all four parallel | 6.719 | 1.6461 | 6.573 |
| In1 alone @1.5 oz (unchanged by 2 oz) | **96.991** | 5.0920 | 94.879 |
| In1 alone if the inner were 2 oz | 72.743 | 5.0920 | 71.159 |
| In1+In2 parallel @1.5 oz | 37.284 | 3.9148 | 36.472 |

Note the 4 oz branch's own convention — "6.991 mm per face" — is a simple halving of
13.981. The exact parallel split of two 0.14 mm faces is **5.374 mm**; at 2 oz the same
two faces need **10.749 mm**. Both conventions are printed because the 4 oz branch was
priced on the conservative one.

### 1.2 Ground

The 60 A return is **/Mn_BATN, not GND**: every leg shunt returns to it
(`R1120/21/22` pin 2 → `/M1_BATN`) and the battery tap is `J1101.2` → `/M1_BATN`
(`esc-current-place/REPORT.md:78-80`). GND is `/DGND`, `/AUX_GND`, `/SVC_USB_GND` — gate
drive and controller only. Its requirement at 2 oz: **0.099 mm at 1 A**, 0.908 mm at 5 A
(`02b_ground.json`). It is not a power path and it is not a constraint.

### 1.3 What the layout offers, measured

| path | offers | needs at 2 oz | width % | carries | current % of 60 A |
|---|---|---|---|---|---|
| phase corridor, F.Cu only (worst of 18) | 7.400 mm | 27.963 | **26.5 %** | **22.9 A** | **38.2 %** |
| phase corridor, F.Cu only (best of 18) | 7.674 mm | 27.963 | 27.4 % | 23.5 A | 39.2 % |
| phase on F.Cu+In2 (the layers the orig uses) | 7.400 | 17.479 | 42.3 % | 32.2 A | 53.7 % |
| phase on F.Cu+B.Cu (B.Cu must be freed of BATN) | 7.400 | 10.749 | 68.8 % | 45.8 A | 76.3 % |
| BATP In1 plane (1.5 oz, unchanged by 2 oz) | 16.000 mm | 96.991 | 16.5 % | 16.2 A | 27.0 % |
| BATN B.Cu plane @2 oz | 37.800 mm | 27.963 | 135.2 % | 74.7 A | 124.5 % |

The two percentage columns are **different bases** and are printed separately on purpose:
a width ratio is not an ampacity ratio, because I ∝ A^0.725. Every PASS/FAIL in this
report is taken on the **current** basis.

**A correction to a settled number, stated rather than smoothed.** BOARD says BATN's B.Cu
plane is *"14.1–20.0 mm, passes at 101–143 %"*. My per-layer min-cut on the board of
record returns **37.800 mm (5.2920 mm²)** — `03_rail.log:12`, and the same instrument
reproduces `esc-battery-rail/12_perlayer.json`'s 5.32 mm² / 38.0 mm on the fix2 geometry
to 0.5 %. So the plane is ~1.9× wider than the settled band says, and at 2 oz it still
carries 74.7 A. **The plane was never BATN's problem; the barrels are** (§2). The settled
14.1–20.0 mm reading is a different quantity (a maximin corridor), not a min-cut, and the
two must not be mixed.

The 7.400 mm corridor has a hand-check (`02b_ground.py`): 20.000 mm pitch − 11.560 mm body
= 8.440 mm free, less 2 × 0.25 clearance = 7.940 mm; the measured 7.400 is 0.540 mm below
that because the corridor tool measures to pad **bounding boxes**.

---

## 2. The rail fix, executed, and the barrel count

### 2.1 The instrument, validated before anything else

`03_rail.py` (`logs/03_rail.log`) runs the same min-cut instrument the rail branch built,
with four controls:

| control | result | verdict |
|---|---|---|
| C1 4 oz fix2 geometry | BATP **1.50816**, BATN **1.75952** mm² | **PASS** — exact to 5 decimals |
| C2 grid independence h = 0.20 vs 0.10 | 1.50816 / 1.75952 at both | **PASS** |
| C3 per-layer 4 oz fix2 | In1 **0.84 mm² / 16.00 mm**, B.Cu **5.292 / 37.80** vs settled 0.84 / 16.0 and 5.32 / 38.0 | **PASS** (0.5 %) |
| C4 per-layer 4 oz orig | In1 0.8400 / 16.000 mm (settled band 12.5–17.7 ✓) ; B.Cu 5.2920 / 37.800 (settled band 14.1–20.0 ✗) | 1 of 2 inside |

### 2.2 The barrel arithmetic — and the trap in it

A 0.4 mm barrel with 25 µm plating is **0.03142 mm²**. Ampacity is **A^0.725**, so barrels
add *sub-linearly*: **45 barrels is not 45 × one barrel.**

| barrels | mm² | carries | % of 59.05 |
|---|---|---|---|
| 10 | 0.3142 | 15.9 A | 27 % |
| **45** (BATN as built) | 1.4137 | **47.4 A** | **80 %** |
| 56 (after the 4 oz branch's fix) | 1.7593 | 55.5 A | 94 % |
| **61** (the requirement) | 1.9148 | **59.1 A** | **100 %** |
| 73 (achieved here) | 2.2937 | 67.3 A | 114 % |

For scale: linear summation would have called 45 barrels **135 A**. The correct figure is
**47.4 A**, and the two differ by 2.8×. The script prints both so the error cannot recur.

### 2.3 What 2 oz does to each rail

Same geometry, outer 0.140 → 0.070:

| rail | 4 oz cut | 2 oz cut | why |
|---|---|---|---|
| BATP (orig) | 0.5242 mm² = **23.1 A** | 0.4542 mm² = **20.8 A** | mixed cut: F.Cu lateral 0.21 → 0.14 **+** 10 barrels 0.3142 unchanged |
| BATN (orig) | 1.4139 mm² = **47.4 A** | 1.4139 mm² = **47.4 A** | 100 % barrel — a barrel does not care what the foil weighs |
| **the 4 oz branch's own rail fix (fix2), re-measured here at 2 oz** | BATP 1.5082 = **49.7 A** | **BATP 1.1259 = 40.2 A** | at 4 oz that cut is 100 % barrel (48 of them); at 2 oz the cut **moves** to 0.6860 lateral + 0.4399 barrel (14) |
| (same, BATN) | 1.7595 = 55.5 A | 1.7595 = **55.5 A** | again pure barrel, unchanged |

**That third row is the branch comparison the owner needs.** The 4 oz branch's executed rail
fix carries **49.7 A** at 4 oz and only **40.2 A** at 2 oz, because its cut is partly made of
F.Cu that halves. So 2 oz does not merely fail to help the rail — it **takes 19 % off the
one rail fix that already exists**. (`03_rail.log`, geometry `geom_fix2.json`, all six cells
identical to 4 decimals.)

**That is the honest asymmetry of the 2 oz branch: it costs BATP 10 % and costs BATN
nothing, because BATN's failure was never made of copper weight.** The plane under it
halves (5.292 → 2.646 mm²) and still carries 74.7 A, with margin.

One arithmetic note a reader will want: the F.Cu lateral goes 0.2100 → 0.1400 mm², not
0.1050, because the min-cut is rasterised at h = 0.20 mm and the neck is read as 1.5 mm at
4 oz and 2.0 mm at 2 oz. The cut is a grid-quantised width times an exact thickness, so
the *area* is exact for the width it reports; the 0.035 mm² difference between 0.1050 and
0.1400 is grid, not copper.

### 2.4 The fix that was executed, and what it could not do

Three attempts, each measured, in order (`07`, `08`, `09`):

1. **+1,590 vias placed wherever the same net had copper on both F.Cu and In1/In1**
   (`07_railfix.py`, 265 per rail, 0.65 mm edge keep-out). Result (`08_remeasure.json`):
   **the cut moved exactly 0.0000 mm²** — BATP still 0.4542, BATN still 1.4139. The vias
   were legal, same-net, and **decoration**, because they lie outside the cut. This is the
   single most useful negative result in the unit: *a via count is not an ampacity.*
2. **Put the barrels where the cut is** (`09_fix2.py`): the terminal lands' zone
   connection set SOLID (the measured `padconn` on `/M1_BATP`'s own pour is `THERMAL` and
   on the other `NONE` — a thermal-relief pad has four spokes), and +1,938 vias on a
   1.05 mm grid inside the lands.
3. Re-measured (`09_remeasure.json`):

| rail | cut | composition | carries | % of 59.05 | verdict |
|---|---|---|---|---|---|
| **BATN** ×6 | **2.2937 mm²** | 2.2937 barrel (73 barrels) | **67.3 A** | **114 %** | **PASS** |
| **BATP** ×6 | **1.4401 mm²** | 0.6860 lateral (9.8 mm of F.Cu) + 0.7541 barrel (24) | **48.0 A** | **81.3 %** | **FAIL** |

So **the barrel fix closes BATN and does not close BATP.** BATP needs a further
**0.4747 mm²**, which is either **+15 barrels in series** or the F.Cu lateral widened from
**9.8 mm to 27.963 mm**. It cannot be barrels alone: 61 barrels need **67 mm² of terminal
land per rail** (1.1025 mm² per 0.8 mm via on a 0.25 mm grid) = **27.96 × 2.4 mm** — which
is the same 28 mm rail the phases want. **The rail and the phase are competing for the
same copper, and that is the redesign.**

### 2.5 Cost of the fix

`kicad-cli pcb drc` at the 2 oz rule set on `esc_rev_b_2oz_railfix2.kicad_pcb`:
**347 violations** — 199 `hole_to_hole`, 112 `via_dangling`, 24 `clearance`, 12
`hole_clearance`. Footprint-bound **0**. So the fix that makes BATN pass is **not clean**;
it is a measured improvement with a measured cost, not a solution.

---

## 3. DRC at 2 oz — and proof the rule file was read

`06_drc.ps1` (`logs/06_drc.log`, `drc/drc_summary.json`). Rule set `drc/rules_2oz.kicad_dru`:
pattern **0.200 mm** — a *published* row (Eurocircuits eC-classification, 70 µm: OTT-OTP-OPP
0.200 / OTW 0.200), ring 0.150 mm (PCBWay published minimum), via 0.60/0.30, PTH ring 0.150,
edge 0.50. Deliberately the same parameter set as `esc-branch-4oz/kicad/r0_2oz`, so the two
branches are comparable.

**The rule file is proven live, because a clean count is worthless otherwise** (BOARD: a
`.kicad_dru` without `(version 1)` is silently ignored):

| arm | violations | what it proves |
|---|---|---|
| 2 oz rules, board of record | **16** (16 `via_dangling`) | the 413 are gone |
| 2 oz rules, power-first placement | **0** | the placement is clean at 2 oz |
| 4 oz rules, same placement | **413** = 371 clearance + 42 annular_width, **footprint-bound 413** | the count is rule-driven, and reproduces the settled 413 exactly |
| probe: same file, clearance 0.20 → 1.00 | **499** (+483) | the file **is** being read |
| same file with `(version 1)` deleted | **110** `drill_out_of_range` | falls back to the project's own rules — the guard is real, demonstrated on this host |
| 2 oz + rail fix2 | **347** | §2.5 |

---

## 4. Thermal: what 2 oz does to the current, with the spreader mandatory

`05_thermal.py` → `05_thermal.json`. Controls: RthJA(3,137 mm²) = **22.36 °C/W** against
the settled 22.4, and the model returns **39.4 A** where the datasheet says 37 A at
TA 25 °C — both PASS.

**The junction.** P(I) = 1.33e-3·I² + 0.0424·I W per device (1.4 mΩ × 1.9 hot, half-duty
conduction + 20 kHz / 30 ns switching at 50.4 V), Tj 175 °C, TA 45 °C. Rth∝A^−0.352 fitted
through the datasheet's own two anchors (600 mm² → 40 °C/W, 172.5 mm² → 62 °C/W).

| | 4 oz | 2 oz |
|---|---|---|
| 70 µm-equivalent copper per FET | 3,136.8 mm² | **2,011.8 mm²** |
| RthJA | 22.36 °C/W | **26.14 °C/W (+16.9 %)** |
| P budget | 5.81 W | 4.97 W |
| continuous I, no spreader | 52.0 A | **47.1 A (−9.4 %)** |

**With the top-side spreader** (TOLT, RthJC 0.4 max, case 95 °C): P budget 200 W →
**I = 372 A**. The die stops being the limit entirely — so **the spreader cannot buy back
what 2 oz costs, because 2 oz does not cost junction temperature. It costs copper.**

**The copper is the limit, and the arithmetic is the IPC-2221 one:**

```
corridor as placed   7.400 mm x 0.070 = 0.5180 mm2 -> 22.9 A @ dT 20 K, 27.4 @ 30 K, 34.3 @ 50 K
2 oz requirement    27.963 mm x 0.070 = 1.9574 mm2 -> 60.0 A @ dT 20 K
```

**MAX continuous per phase at 2 oz, spreader fitted: 22.9 A** (26.3 % of the design
current). Even at a 50 K rise it is 34.3 A. 60 A is unreachable in this placement at any
temperature the laminate will tolerate.

---

## 5. Place and route, as far as a copy will go

| state | area (2 methods) | footprint DRC | unconnected | B.Cu components |
|---|---|---|---|---|
| board of record 4 oz | 491.732 / 491.732 cm² | — | 1,542 | **0** |
| **board of record 2 oz** | 491.732 / 491.732 | **16**, fb 0 | 1,542 | **0** |
| power-first placement 2 oz | **382.709 / 382.709 cm²** | **0** | 2,196 | **0** |
| + rail fix (3,528 vias, 48 solid pads) | 382.709 | 347, fb 0 | **1,530** | **0** |

Area by two independent methods (`GetBoardPolygonOutlines().Area()` and a shoelace walk of
the Edge_Cuts loops) agreeing to **0.000000 cm²** on all four states — the same 491.732 /
382.709 the programme already verified.

**The achievable area at 2 oz.** 382.709 cm² is achievable *as a placement* — 0 DRC at 2 oz
rules, 0 on B.Cu. It is **not achievable as a 60 A design**, because the phase corridor
must grow from 7.400 mm and the corridor is set by the FET courtyard pitch. Measured pitch
law: corridor = pitch − 12.600 mm (20.000 pitch, 11.560 body, 7.400 measured). So:

| phase solution | corridor | pitch | board width | area |
|---|---|---|---|---|
| F.Cu alone @2 oz | 27.963 | **40.563 mm** (+20.56) | 237 mm | **585.6 cm² (+53.0 %)** |
| F.Cu+In2 @2 oz | 17.479 | 30.079 (+10.08) | 195 mm | **482.2 cm² (+26.0 %)** |
| **F.Cu+B.Cu @2 oz** (best case, displaces BATN from B.Cu) | 10.749 | **23.349 (+3.35)** | 169 mm | **415.8 cm² (+8.6 %)** |
| 4 oz, two faces (the settled branch) | 5.374 | 17.974 (−2.03) | 147 mm | 362.7 cm² (−5.2 %) |

The last row is why the 4 oz branch's placement passes and this one cannot: at 4 oz the
requirement (5.374 mm) is **below** the corridor the layout already offers (7.400); at 2 oz
the requirement (10.749) is **above** it, and only the extreme measures above close the gap.

**What this unit did not execute:** the re-route that puts each phase on a 10.749 mm
two-face corridor and each rail on a 27.963 mm strip. That is a new placement with a new
pitch, and it was priced in the table above (415.8 cm², +8.6 %) rather than drawn. What
was executed and measured is the stackup change, the DRC suite on three board states, and
the rail fix in two iterations.

---

## 6. Verdict

### BUILDABLE + CAPABLE at 2 oz: **NO.**

**Binding constraint: the phase corridor's copper width.** At 60 A the phase needs
**27.963 mm of 2 oz on F.Cu** (10.749 mm on each of two outer faces); the power-first
placement offers **7.400 mm** — 26.5 % of the required width. That corridor carries
**22.9 A, 38.2 % of the 60 A design current**, and it is fixed by the FET courtyard pitch
(20.000 mm), which is a placement property, not a routing one.

Second, separately: **BATP reaches only 48.0 A (81.3 %) after an executed fix**, and the
fix that gets there costs 347 DRC items. BATN does pass (67.3 A, 114 %) once its lands are
made solid and 73 barrels are in the cut.

### What 2 oz actually buys and costs

| | 4 oz branch | 2 oz branch |
|---|---|---|
| footprint DRC | **413**, 100 % footprint-bound | **0** |
| rule set | has to extrapolate past the fab's 105 µm row | **published row** (70 µm: 0.200 mm) |
| phase corridor needed | 5.374 mm (2 faces) | **10.749 mm (2 faces)** — 2.0× |
| phase requirement vs 7.400 mm offered | PASS (+38 %) | **FAIL (−31 %)** |
| rail barrels needed | 61 per rail | **61 per rail — identical** |
| the 4 oz branch's own rail fix, re-measured | BATP 49.7 A, BATN 55.5 A | **BATP 40.2 A, BATN 55.5 A** |
| area for 60 A | 362.7 cm² fits inside 382.709 | **415.8 cm²** — does not fit |
| cost | three package changes | a new placement, +33 cm², +3.35 mm pitch |

**The comparison the owner asked for, in one line:** 2 oz removes the footprint blocker and
**doubles the copper problem**. The 413 DRC items are real and 2 oz does clear them; but at
2 oz the ESC cannot carry 60 A on any placement this outline allows without moving the FET
pitch and re-routing every phase, and the rail still needs the same 61 barrels either way.
**Neither weight fixes the rail** — that conclusion now stands on an executed fix at both
weights, not on an argument.

---

## 7. Open items

| id | item |
|---|---|
| **U1** | The 27.963 mm one-face / 10.749 mm two-face phase corridor was **priced, not drawn**. A placement at 23.349 mm pitch is the next unit's job. |
| **U2** | The settled "BATN plane 14.1–20.0 mm" does not reproduce as a min-cut (37.800 mm). Two different quantities are circulating; §1.3 states which is which and neither is withdrawn silently. |
| **U3** | The rail fix's 347 DRC items (199 hole_to_hole) are the price of the 1.05 mm via grid. A 1.15 mm grid would need more land. |
| **U4** | 73 barrels in the cut for BATN is 20 % above the 61 required; the margin is land area, and no analysis of land-area asymmetry between the six cells was done (all six measured identical to 4 decimals). |
| **U5** | Barrels are evaluated at k = 0.048, which is what reproduces the settled 47.4 A. A barrel is plated copper in a hole and is arguably an internal conductor (k = 0.024); at 0.024 every barrel number above **halves**. The 4 oz branch's own numbers use 0.048, so this branch matches it — flagged, not changed. |

---

## 8. Files

| file | what |
|---|---|
| `00_probe.{py,log,json}` | nets, FET pitch, pad geometry, lugs |
| `02_widths.{py,json,log}`, `02b_ground.{py,json,log}` | the width book, its 4 controls, ground rows, corridor hand-check |
| `03_rail.{py,json,log}`, `03a_timing.{py,log}` | min-cut at 4 oz (controls) and 2 oz (all 6 cells × 2 rails × 2 geometries) |
| `04_build.{py,json,log}` | the 2 oz copies, area by two methods, B.Cu, unconnected, stackup |
| `05_thermal.{py,json,log}` | junction and copper limits, with controls |
| `06_drc.ps1`, `logs/06_drc.log`, `drc/` | DRC suite + the rule-loaded proof |
| `07_railfix.{py,json,log}` | attempt 1: 1,590 vias (moved the cut 0.0000) |
| `08_remeasure.{py,log}` | measurement of attempt 1 |
| `09_fix2.{py,json,log}`, `09_remeasure.{py,json,log}` | attempt 2: solid lands + 1,938 vias |
| `10_area_2oz.{py,json,log}` | pitch→area, land→barrels, uncapped unconnected |
| `extract.py`, `railmc.py`, `rail07.py` | the instruments (copied from `esc-battery-rail`) |
| `geom_orig.json`, `geom_fix2.json`, `geom_railfix.json`, `geom_railfix2.json` | extracted copper geometry per board |