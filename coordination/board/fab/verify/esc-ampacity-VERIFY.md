# ESC rev_b — adversarial verification: k per layer, rail verdict, placement gate

**Unit:** `av-esc-ampacity-gate` · adversarial verifier, ESC ampacity/placement wave · 2026-11-16
**Host:** KiCad 9.0.7 (`C:/Program Files/KiCad/9.0/bin/`), pcbnew 9.0.7, CPython 3.12.
**Write scope:** this directory only (`E:/engineering-portfolio-audit/evidence/av-esc-ampacity-gate/`),
on copies. `evidence/` is git-ignored (`.gitignore`: `repos/ tools/ inputs/ evidence/ *.log`) — checked,
so nothing here can reach the repo index. No commit, push or reset; nothing written to `D:\CodeProjects`
or `E:\1vm\TMP`.

**Objects under test.**

1. `esc-ampacity-basis` (09:44) — k = 0.048 external / 0.024 internal confirmed; BATP and BATN **FAIL**
   at 40 A (24.83 / 29.55 A) because their measured min-cut is 100 % via barrels; BATP_IN **PASSES** at
   47.74 A because it is F.Cu; the earlier 49.67 / 59.09 A PASS is withdrawn.
2. `esc-placement-gate` (10:04) — a placement exists (`safe.kicad_pcb`, 382.709 cm²) whose gate exits
   **0**, therefore **safe to route**.

> **STATUS: COMPLETE.** Skeleton written first (§0 at 10:07), then appended as each step finished.
> Every quoted number is derived in a logged script in this directory and cross-checked (§6).
> **The headline: the gate's exit 0 is produced by the exact constant this wave proved wrong.
> At the correct k, G6 fails and the rail's own transitions physically cannot be re-placed.
> The placement is NOT safe to route.**

---

## 0. The answers

| question | answer |
|---|---|
| **k for F.Cu / B.Cu** (0.140 mm, 4 oz) | **0.048** — external. Confirmed verbatim from an IPC-based calculator: *"For IPC-2221 internal layers: k = 0.024, b = 0.44, c = 0.725 / For IPC-2221 external layers: k = 0.048"* ([AdvancedPCB](https://www.advancedpcb.com/en-us/tools/trace-width-calculator/)). The constants are *"constants resulting from curve fitting to the IPC-2221 curves"* — the standard's own §6.2 is charts, and this closed form is the accepted fit to them. |
| **k for In1 / In2** (0.0525 mm, 1.5 oz) | **0.024** — internal. Same source. Consequence: I ∝ k, so identical copper carries **half** the current; equal current needs **2^(1/0.725) = 2.60×** the area. |
| **k for a via barrel** | **No k exists in IPC-2221 — it publishes no via formula.** The buried-copper assignment is **0.024** (conservative; the barrel is laminate-buried). The optimistic public convention applies the external **0.048** to the barrel section *"as a rough estimate"*. This choice, not the In1 question, is what the rail verdict rides on. |
| **does the rail pass 40 A** | **At the correct k, NO.** BATP 48 barrels one-area at 0.024 = **24.83 A (0.62×)**; BATN 61 barrels = **29.55 A (0.74×)**; the as-placed 14-barrel bus site = **21.0 A per-via / 10.2 A one-area**. BATP_IN's 47.74 A is genuine and **PASSES** (F.Cu). |
| **placement gate conditions** | 7 PASS / 1 **FAIL** at the correct k. G6 fails at every one of the 48 transition sites (14 needed 27; 9 needed 17), and **24 of 48 sites were never measured at all** — `gate.py` silently drops any site with no row. |
| **SAFE_TO_ROUTE** | **NO.** |
| **figures using the wrong k** | **3.00 A per barrel** (⇒ the whole 492-barrel requirement, should be 936); **BATP_IN = 23.87 A "at k=0.024"** in the gate report (that cut is 100 % F.Cu — the internal k was applied to external copper, a false *fail*); the withdrawn 49.67 / 59.09 A still appear as the gate's comparison column. |
| **CONSTRAINT_VIOLATION** | **YES.** The unit that declares SAFE uses the barrel constant the sister unit withdrew the rail PASS for, 20 minutes earlier, on the same board family. |
| **CREDIBLE** | `esc-ampacity-basis`: **yes** — row-level, 6 controls, and my independent recomputation reproduces every figure to ≤0.13 %. `esc-placement-gate`: **no, not as a PASS** — its corridors are real (vector-confirmed, §6.4) but its exit 0 rests on the withdrawn constant and on half its sites being unmeasured. |
| **VERDICT** | **Placement is NOT safe to route.** The rail's transition at the shunt pads is short by 1.9× in barrels, and those pads physically hold only 17–18 of the 27 needed — so it is not a re-pour and not a re-route: the shunt landing (part, or a second shunt per rail) has to change. The phase corridors alone are a genuine PASS. |

---

## 1. K per layer, verified against the standard

`t1_basis.py` re-implements IPC-2221 from the published constants — no prior unit's code — and refuses
to print an ESC row unless nine controls pass.

```
A[mil²] = ( I / (k · ΔT^0.44) )^(1/0.725)      I[A] = k · ΔT^0.44 · A[mil²]^0.725
width[mil] = A[mil²] / (thickness[oz] · 1.378)
```

| control | computed | published | residual | source |
|---|---|---|---|---|
| C1 10 mil / 1 oz / 10 K external → A | 0.8855 A | 0.88 | +0.63 % | published worked example |
| C2 5 A / 10 K / 1 oz external → mil | 108.88 | 110 | −1.02 % | published worked example |
| C3 5 A / 10 K / 1 oz **internal** → mil | 283.24 | 280 | +1.16 % | published table — this is the control that validates 0.024 |
| C4 60 A / 20 K / 4 oz external → mm | 13.9813 | 13.981 | +0.002 % | programme settled |
| C5 43.5 A / 20 K / 4 oz external → mm | 8.9725 | 8.972 | +0.005 % | programme settled |
| C6 43.5 A / 20 K / 1.5 oz internal → mm | 62.2435 | 62.244 | −0.001 % | programme settled |
| C7 1.50816 mm² at k=.024 → A | 24.833 | 24.83 | +0.01 % | ties the two units |
| C8 0.4 mm/25 µm barrel at k=.048 | 3.0000 A | 3.00 | −0.0005 % | the gate's constant |
| C9 same barrel at k=.024 | 1.5000 A | 1.50 | −0.0005 % | half of it |

`t1_basis.log`. All nine pass; the instrument is quotable.

**The convention question, answered.** It is real and it is not a memory: 0.048 external / 0.024 internal,
ratio exactly 2, b = 0.44, c = 0.725. Two things the reports say about it that a reader should keep:

* the constants are a **curve fit to IPC-2221's charts**, not text in the standard — the standard draws
  current *vs* area for external and internal conductors and the fit is a community artefact;
* the *internal* half is not a thermal law but a historical fit for buried copper with no air path. That is
  exactly why it applies to a via barrel: a barrel is buried copper. The gate's own defence of 3.00 A/barrel
  ("the programme's constant applied to the barrel", `gate.py:41`) is the withdrawn convention.

---

## 2. The layer each current path actually runs on (row-level)

From `esc-rail-repour/16_measure_v4.json` — the same rows the programme settled on:

| net | cut mm² | **per-layer mm² F / In1 / In2 / B** | barrel mm² | edges | measured width |
|---|---|---|---|---|---|
| `/M1_BATP` | 1.50816 | **0.0 / 0.0 / 0.0 / 0.0** | 1.5082 | 48 | 0.0 |
| `/M1_BATN` | 1.91662 | **0.0 / 0.0 / 0.0 / 0.0** | 1.9166 | 61 | 0.0 |
| `M1_BATP_IN` | 1.42800 | **1.428 / 0.0 / 0.0 / 0.0** | 0.0 | 102 | **10.20 mm on F.Cu** |

Three consequences, in order of importance.

1. **BATP and BATN have no planar copper in their min-cut at all.** The bottleneck is a barrel row, not the
   In1 plane (5,009.86 mm²) and not the B.Cu plane (5,077.28 mm²). The layer of the *rail* is In1/B.Cu; the
   layer of its *min-cut* is "buried barrel", and that is the layer whose k governs.
2. **BATP_IN's bottleneck is 10.20 mm of F.Cu.** It never touches an inner layer in the cut. Any internal-k
   figure applied to it is wrong in the conservative direction (§5, finding F2).
3. **BATP's series path is topologically on In1 but ampacity-wise on barrels.** The brief's premise is
   correct and its conclusion is not: the In1 copper k does not govern BATP.

---

## 3. The rail, recomputed row by row

`t1_basis.py`, ΔT = 20 K. "Capacity" is `I = k·ΔT^0.44·A^0.725` on the measured section with the constant of
the layer that section is made of.

| path | layer / k | measured mm² | capacity A | 40 A | verdict |
|---|---|---|---|---|---|
| BATP_IN F.Cu 10.20 mm | F.Cu 4 oz / **0.048** | 1.4280 | **47.74** | 1.19× | **PASS** |
| BATP 48 barrels, one-area | barrel / **0.024** | 1.5082 | **24.83** | 0.62× | **FAIL** |
| BATN 61 barrels, one-area | barrel / **0.024** | 1.9166 | **29.55** | 0.74× | **FAIL** |
| phase F.Cu 7.400 mm alone | F.Cu / 0.048 | 1.0360 | 37.83 | 0.87× | FAIL (needs In2 in parallel) |
| phase F.Cu ∥ In2, 7.400 mm | F.Cu 0.048 ∥ In2 0.024 | 1.0360 + 0.3885 | 47.12 | 1.08× | PASS at 43.5 A |
| *(control)* BATP 48 barrels at k=.048 | barrel / 0.048 | 1.5082 | 49.67 | 1.24× | the withdrawn PASS |
| *(control)* BATP_IN at k=.024 | **wrong** | 1.4280 | 23.87 | 0.60× | the gate report's figure |

**The three numbers the brief asked to settle.** 49.67 A is real *arithmetic* and wrong *physics*: it is the
external constant on a 100 % barrel cut. 24.83 A is the same instrument at the internal constant, exactly
half because I ∝ k. 47.74 A is neither — it is BATP_IN, a different net, on F.Cu, and it is correct.

**BATP on In1 — is the 49.7 A real?** No. The In1 plane is not the limiting element (5,009.86 mm²); the
48-barrel transition is. Its capacity is **24.83 A** on the conservative one-area basis (FAIL) and
**72.0 A** if 48 barrels are rated independently (PASS). The 2.9× spread is an aggregation artefact, larger
than the k correction itself, and no public standard settles it: IPC-2221 has no via formula and IPC-2152's
via appendix is not public. So the honest rail statement is: **not established to 40 A by any public
standard, and the conservative floor is a FAIL.**

---

## 4. The placement gate, condition by condition

`gate.py` on `safe.kicad_pcb` exits **0** with all 8 PASS (`gate_safe.json`). Re-derived below from its own
JSON and from the board; `t1_basis.py`, `t2_sites.py`, `t4b_pinch.py`. The board under test carries
**0 tracks, 0 zones and 492 vias** (re-counted): every corridor number below is *free space on a bare pad
field*, which is legitimate for a placement gate and is not a routed check.

| ID | condition | gate says | my re-derivation | verdict |
|---|---|---|---|---|
| **G1** | phase ≥ 8.972 mm on F.Cu | PASS 9.420 (+5.0 %) | reproduced by an independent vector instrument at 9.458 (+0.04 mm) — but that number exists only because the path may start within 3 mm of the pad; pinned at the pad centroid the same instrument gives **3.500 mm** | **PASS, conditional** |
| **G2** | BATP_IN/BATP ≥ 7.992 mm on B.Cu | PASS 12.519 (M3) | vector 15.44 at that row — the gate **understates** it; B.Cu is bare (0 tracks, 0 zones, 492 via discs) | **PASS** (space is real; see G8) |
| **G3** | BATN ≥ 7.992 mm on B.Cu | PASS 20.768 | vector-confirmed 20.789 | **PASS** |
| **G4** | no part on B.Cu / inner | PASS 0 | 687 F.Cu, 0 B.Cu, 0 inner — re-counted | **PASS** |
| **G5** | spreader reserved, area declared ≥ 181.2 cm² | PASS 36/36 markers, 68.8 cm², decl 181.202 | the "measurement" is a **text token compared with its own derivation** (181.202 vs 181.200, +0.002); `SPREADER_OUTSIDE=1` is never checked against the outline; P uses conduction only | **PASS by declaration** |
| **G6** | barrels ≥ ceil(I/3.00 A) | PASS 492, margin **0** at every row | at k=.024 it is **ceil(I/1.50)**: **FAIL at all 48 sites** (14 < 27, 9 < 17); and only **24 of 48 sites are in the row table** — the other 24 are dropped by `if key is None: continue` | **FAIL** |
| **G7** | Tj ≤ 175 °C at TA 45 °C with spreader | PASS 101.4 °C | 101.4 at P = 2.52 W/device; **142.7 °C** on the settled P = 4.36 W/device; board-only 201–315 °C | **PASS** (spreader mandatory) |
| **G8** | back-layer budget ≤ 50 % | PASS 19.8 % | arithmetic reproduces; it is a budget, not a packing — stated as such | **PASS** (weak) |

**Gate exit code at the correct constant: 1.** One condition fails, and it fails by 1.90× on the total
(936 required vs 492 placed).

### 4.1 Why G6 cannot be patched by adding barrels

The builder stops the moment it has placed `need` barrels (`03_build_safe.py:151`), so the board never
records how many *would* fit. `t2_sites.py` removes the early stop and counts every position that satisfies
the same clearance rule (0.25 mm to foreign pads, 0.90 mm between barrels, 0.30 mm inside a pad edge):

| site family | sites | placed | physically fits | needed at k=.024 | outcome |
|---|---|---|---|---|---|
| bus shunt pad (40 A) | 12 | 14 | **17–18** | **27** | **cannot fit** |
| BATN leg shunt pad (25.1 A) | 18 | 9 | 13–18 | **17** | **capacity short at 12 of 18** |
| BATP HS drain tab (25.1 A) | 18 | 9 | 81–109 | 17 | fits easily |

**24 of 48 sites cannot hold the correct-k barrel field.** The two families that fail are the *shunt*
landings — the pads with the least room and the most current. 17 barrels × 1.50 A = 25.5 A is the most that
pad can carry; the rail wants 40 A through it.

That closes the door on "re-pour" and on "re-route": at the shunt the choice is a **bigger landing (footprint
/ part change), a second shunt per rail in parallel (2 × 20 A ⇒ 14 barrels each, which fits), or a
non-PCB busbar** — plus, if the programme wants to keep 14 barrels, an IPC-2152 via-appendix rating or a
4-wire coupon test at 40 A. All four are placement or component decisions. That is the owner's point
arriving from the copper side.

---

## 5. The six hunt items

| # | hunt | finding |
|---|---|---|
| **1** | **k=0.048 on an inner/buried layer** | **FOUND, and it is the gate's load-bearing constant.** `gate.py:41` `I_BARREL = 0.048 * 20**0.44 * A_MIL**0.725`; `03_build_safe.py:33` the same. A 0.4 mm/25 µm barrel is buried copper: 3.00 A at 0.048, **1.50 A at 0.024**. Every one of the 48 sites is therefore at half the required barrels, and the 492-barrel placement should be 936. `esc-ampacity-basis` had already withdrawn the identical convention 20 minutes earlier. **This is the wave contradicting itself.** |
| **2** | **ampacity figure without layer / thickness / ΔT / k** | Gate §1.3's table gives `BATP_IN 47.74 → 23.87 A` with the column headed *"at k=0.024 (correct for In1)"*. BATP_IN's cut is **F.Cu, 1.4280 mm², In1 = 0.0** (§2). The internal k was applied to external copper: a **false fail**, not a false green — but it is the same class of error in the mirror, and it is used to justify moving a rail that did not need moving for that reason. The gate's G6 rows quote 3.00 A/barrel with no layer stated at all. |
| **3** | **placement declared safe without the gate exiting zero on every condition** | The gate *does* exit 0 — but only at k=.048; at k=.024 G6 fails. And 24 of 48 G6 sites have no row, so the exit-0 cannot be "every condition" even on its own terms: half of one condition is unmeasured and silently skipped rather than reported UNMEASURABLE. |
| **4** | **condition stated but not measured / measured on the wrong object** | (a) **G5's exchange area is a text string compared with its own formula** — 181.202 ≥ 181.200, margin +0.002 cm², and "outside the outline" is a tag `SPREADER_OUTSIDE=1` that no code reads. (b) **G6 sites 25–48 skipped** (`if key is None: continue`) — the gate checks 4 of the 8 transitions per cell. (c) **the DRC figures are on a superseded board**: `orig.kicad_pcb` is sha `992570…`, the *input* of `esc-pad-shrink`; after that wave the same rule set reads **253**, with **113** footprint gaps (QFN 75 + USB-C 38) — not the "371 pad gaps + 42 annular = 413 that no placement can move" the gate reports at 10:04, 58 minutes after the shrink. 258 of those 371 were already cleared. |
| **5** | **area figure that shrinks below what the gate demands** | Not violated by the artefact: 370.12 fails G1/G2/G3 as reported, and 382.709 is the smallest board that passes the *corridors*. But "382.71 is the smallest safe area" is not established, because **no area is safe while G6 fails**; the barrel fix is local (cm² scale at the shunt), not a board-area question. |
| **6** | **FET thermal claim without spreader and ambient** | Not violated — both units carry TA = 45 °C and both fail without the spreader (201 °C at the gate's P; 219–315 °C at the settled P). Two inconsistencies: the gate's P = 2.52 W/device is **conduction only**, while the settled formula `1.33e-3·I² + 0.0424·I` gives **4.36 W** (+42 %), which moves the required exchange area from 181.2 to **314 cm²** — and the mandated band is **352–528 cm²**, so 181.2 is under-declared whatever P model you use. `RthJA = 22.4 C/W "with spreader"` is asserted, not derived, and is inconsistent with the declared 181 cm² plate (which implies ≈0.4 C/W/device); G7 survives either way (it fails only above ≈30 C/W). |

---

## 6. Instrument validation

Six instruments in this programme gave plausible green numbers while wrong, so each number quoted above was
tied to a hand-checkable case first.

### 6.1 The formula instrument (used for every ampacity figure)
Nine controls, §1; worst residual 1.16 % on a rounded published table entry, ≤0.13 % on the programme's own
settled figures. It refuses to run if any control fails (`sys.exit(1)`).

### 6.2 The barrel capacity instrument
0.03142 mm², `I = k·ΔT^0.44·A^0.725` → 3.0000 A at 0.048, 1.5000 A at 0.024, i.e. exactly the gate's own
number and exactly half of it. The 1.9× shortfall is not a modelling choice: 40 A / 1.50 A = 27 barrels, and
27 > 14 by arithmetic.

### 6.3 The via-connection instrument (`t2_sites.py`)
The gate counts vias "within 7 mm of the terminal" (`02_measure.py:205`). I re-counted by *annulus touching
the pad polygon*: **connected = 14/14 and 9/9 at every one of the 48 sites, identical to the 7 mm window**.
No over-count, no stray barrels, no double-booking across sites. The gate's census is honest; its
*constant* is not.

### 6.4 The corridor instrument (`t4b_pinch.py`)
The gate's corridor is a raster EDT maximin (`scipy.ndimage`, h = 0.04, 12 mm window, 3 mm seeds). I
recomputed the same quantity with **vector geometry** — binary search on R with shapely `buffer` and
component connectivity, no raster, no EDT:

| row | gate (raster) | vector (disc seed) | Δ | vector (point seed) |
|---|---|---|---|---|
| M1 PHASE_A | 12.140 | 12.125 | −0.015 | 9.733 |
| M1 PHASE_A_H | **9.420** | 9.458 | +0.038 | **3.500** |
| M6 PHASE_A_H | 9.456 | 9.458 | +0.002 | 3.500 |
| M6 PHASE_C_H | 9.456 | 9.458 | +0.002 | 3.500 |
| M3 PHASE_C | 13.260 | 13.300 | +0.040 | 9.733 |
| M1 BATN (B.Cu) | 20.768 | 20.789 | +0.021 | 15.402 |
| M3 BATP_IN (B.Cu) | 12.519 | 15.435 | +2.916 | 11.764 |

Six of seven rows agree within **0.04 mm** — the raster corridor instrument is validated, and where it is
wrong (M3 BATP_IN) it is **conservative**. The one caveat is structural, not numerical: G1's thinnest
margin (+0.448 mm) is smaller than the instrument's sensitivity to the seed convention (**5.96 mm** at the
phase pad). The 9.42 mm is a "an 8.972 mm trunk exists within 3 mm of each terminal" reading, not a
"the conductor is 9.42 mm wide at the pad" reading; the phase must fan out from its pads to reach it, which
is routing the gate does not budget.

### 6.5 A dead end, kept honest
`t3_corridor.py` (straight line A→B, minimum clearance) returns **0.000 mm for every phase**, because a
straight line between two pads necessarily crosses other FETs' pads. It is a valid refutation of the naive
shortest-path reading and an invalid corridor instrument; it is superseded by §6.4 and is kept only as a log.

---

## 7. Limits of this verification

| # | limit | effect if wrong |
|---|---|---|
| V1 | ΔT = 20 K is inherited, not derived | at 30 K every capacity ×1.195: BATP 29.7 A, BATN 35.3 A, 14 barrels 25.1 A — **all still below 40 A**; the verdict does not move |
| V2 | the one-area vs per-via aggregation for barrels is **not settled by any public standard** | one-area 24.83 A (the floor I charge) vs 72.0 A per-via; I report both and charge the floor, as the sister unit does |
| V3 | barrel capacity is sized at 25 µm plating and 0.4 mm drill | at 38 µm the area ×1.52 and the current ×1.36: 14 barrels → 28.6 A per-via, still < 40 A; 27 → 36.7 A, still marginal |
| V4 | my capacity count uses the builder's own candidate rule (0.45 mm grid, 0.25 mm clearance, 0.90 mm via pitch) | a finer grid or via-in-pad with plugging might find 1–3 more positions per shunt pad; it will not find 10 |
| V5 | "current per FET tab = 43.5/√3" and "P per device uses I = 43.5 A" are inherited from the programme | if 6 devices share a phase, the per-device loss is far lower and the thermal margin is larger; it does not affect the barrel or corridor arithmetic |
| V6 | the gate's boards are the pre-pad-shrink rev | the shrink only makes pads smaller (more free space), so no ampacity verdict improves or worsens — but the *DRC* numbers in the gate report are stale |
| V7 | I did not run DRC myself | DRC counts are quoted from the two units' JSON, which agree on the 523 baseline and the 199-cap |

---

## 8. Verdict

**The suspected error is confirmed, and it is not where the brief placed it.** k = 0.048 is external,
0.024 internal, verified from the standard's own calculator lineage and hand-checked (C1–C3). But the
rail does not fail because someone applied 0.048 to In1 copper — the rail's min-cut has **no In1 copper in
it**; it is 100 % barrels. The error is that the **buried barrel** was rated at the **external** constant,
which is exactly what produced 49.67 / 59.09 A, and exactly what the placement gate then used to size its
replacement barrel field.

**So the wave fixed the number and re-used the bug.** `esc-ampacity-basis` withdrew the rail PASS at 24.83 /
29.55 A. `esc-placement-gate`, twenty minutes later, built a gate whose barrel bar is
`0.048·20^0.44·A^0.725 = 3.00 A`, and declared 492 barrels — half of the 936 the correct constant requires —
sufficient. The gate's corridors are real and vector-confirmed; the phase trunk is real (conditional on
fan-out); the thermal margin is real; the back-layer space is real. The one thing that actually carries the
40 A at the shunt is not.

**And the placement cannot be rescued by routing.** 24 of 48 transition sites physically cannot hold the
correct-k barrel count: the bus shunt pads fit 17–18 barrels where 27 are required, the BATN leg pads fit
13–18 where 17 are required. Whatever else is decided, the shunt landing has to change — a part change, a
second shunt per rail, or a busbar.

**Answers.** Correct k: 0.048 external (F.Cu/B.Cu), 0.024 internal (In1/In2), 0.024 for a buried barrel.
Rail: **FAIL at 40 A** (BATP 24.83 A = 0.62×, BATN 29.55 A = 0.74×; BATP_IN 47.74 A passes and is not a
rail pass because the rail's series path goes through the barrels). Placement gate: 7 PASS, **G6 FAIL**;
**SAFE_TO_ROUTE: NO**. Figures on the wrong k: 3.00 A/barrel and everything derived from it (the 492-barrel
requirement, the G6 PASS, the exit 0); plus BATP_IN's 23.87 A, which applies the internal constant to an
external cut. Constraint violated: yes — the SAFE verdict rides on the constant the same wave withdrew.
Credible: `esc-ampacity-basis` (yes), `esc-placement-gate` (no, as a PASS). **The owner is right: this
placement is not ready to be routed, and the reason is copper, not area.**

---

## 9. Reproduce

```
t1_basis.py    IPC-2221 re-implementation, 9 controls, every path recomputed   -> t1_basis.json/.log
t2_sites.py    barrels actually touching each pad + physical capacity per site -> t2_sites.json/.log
t3_corridor.py  discarded straight-line probe (kept as a logged dead end)     -> t3_corridor.json/.log
t4b_pinch.py   vector-geometry corridor, disc seed vs point seed              -> t4b_pinch.json/.log
```

```powershell
$py  = "C:\Program Files\KiCad\9.0\bin\python.exe"
$py3 = "C:\Program Files\Python312\python.exe"
cd E:\engineering-portfolio-audit\evidence\av-esc-ampacity-gate
& $py3 t1_basis.py      # formula only, no pcbnew
& $py  t2_sites.py      # 48 sites, capacity
& $py  t4b_pinch.py     # 7 corridor rows, two seed conventions
```

Inputs read-only: `esc-rail-repour/16_measure_v4.json`, `esc-placement-gate/{02_safe.json, gate_safe.json,
01_standard.json, drc_safe.json, boards/safe.kicad_pcb}`, `esc-pad-shrink/REPORT.md`,
`esc-gaps-113/REPORT.md`.