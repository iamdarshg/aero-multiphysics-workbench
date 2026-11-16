# ESC POWER PATH ROUTING — fab-readiness wave 19

Scope: ONE task — route the ESC power path completely at the settled 36.6 A design point and push
unconnected down as far as constraints allow.

Input (read-only): `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb`
Prior evidence consumed: `evidence/esc-36a-build/`
All work on COPIES under `evidence/esc-route-power/boards/`.

Host: KiCad 9.0.7 (`kicad-cli.exe`), `C:\Program Files\Python312\python.exe` (cadquery 2.7.0 / OCP 7.8.1.1).

---

## Status — COMPLETE

| Step | Description | State |
|---|---|---|
| 0 | Skeleton + prior-evidence intake | DONE |
| 1 | 3 oz stackup + 0.200/0.200 rules, reproduce DRC 102 | **DONE — 102 = 70+16+16, reproduced exactly** |
| 2a | Clear pours local to each phase corridor, re-measure | **DONE — A 3.90→8.30, B −0.50→5.10, C 0.70→1.30 mm** |
| 2b | Route corridor first, re-pour around, width before/after ×6 | **DONE — 30 rows routed, 6 at the design point, DRC cost stated** |
| 3 | PHASE_B obstruction | **DONE — PHASE_B HAS a lane once pours clear (5.10 mm, = the pour-free control); PHASE_C is the one that does not respond, left unresolved** |
| 4 | Power then signal; unconnected on both tools after each | **DONE — pcbnew 1,542→1,638→1,638→1,612; kicad-cli 499 is a CAP** |
| 5 | GATE at 36.6 A, G1–G8 + exit code | **DONE — 4 PASS / 4 FAIL, EXIT 1** |
| 6 | Final state, set diff, complete yes/no, blocker | **DONE — power path NOT complete; blocker named** |

---

*(sections appended below as each step completes)*

---

## 1. The 3 oz / 0.200 build, reproduced on my own copy

Copied (never written in place): `repos/.../esc_rev_b.kicad_pcb` → `boards/escbase.kicad_pcb`,
with `escbase.kicad_pro` and `escbase.kicad_dru` (the 0.200 pattern-class rule file; sha256
identical to the wave-18 copy `975FDA8F…90DD0`, so the rule set is provenance-checked, not
retyped). Stackup read back from the board file **[native]**:

| layer | thickness | note |
|---|---:|---|
| F.Cu | 0.1050 mm | 3 oz outer |
| dielectric 1 (prepreg) | 0.200 | |
| In1.Cu | 0.0525 mm | 1.5 oz inner |
| dielectric 2 (core) | 0.865 | grown from 0.795 so the 1.60 mm board is held |
| In2.Cu | 0.0525 mm | |
| dielectric 3 (prepreg) | 0.200 | |
| B.Cu | 0.1050 mm | 3 oz outer |
| **total** | **1.600 mm** | |

DRC, `kicad-cli pcb drc --severity-all`, on my copy **[native]**:

```
exit 0   violations 102   unconnected 499       (10.6 s)
by type: 70 annular_width, 16 via_dangling, 16 via_diameter
```

**DRC 102 reproduced exactly, and the residual is the settled set: 70 + 16 + 16, nothing else.**

> Tool note, recorded because this programme has been burned by it twice: `kicad-cli pcb drc`
> exits **0 even when it reports violations** — the exit code of `drc` is "the run completed",
> not "the board is clean". Every count in this report is read out of the JSON, never off `$LASTEXITCODE`.

---

## 2. First correction: this is not an F.Cu/B.Cu board, and the inner layers carry the phases

`00_probe.py` **[native]**: 687 footprints, 2,144 tracks/vias, **96 zones**, 4 drawings,
board 173.9 × 283.1 mm. The 96 zones are **not** "96 F.Cu pours" (wave 18's wording):

| layer | zones | what they are | fill |
|---|---:|---|---:|
| F.Cu | 66 | per-cell terminal spreads: `BATP` ×3, `PHASE_A/B/C` ×2, `BATP_IN` ×1, `BATN` … | 10,972 mm² |
| B.Cu | 6 | **`M#_BATN` planes**, one per cell, ~5,100 mm² each | 30,596 mm² |
| In1.Cu | 6 | **`M#_BATP` planes**, one per cell, ~5,039 mm² each | 30,275 mm² |
| In2.Cu | 18 | **`M#_PHASE_A/B/C` pours**, 3 per cell, 622–737 mm² each | 12,336 mm² |

Tracks: 148 on F.Cu, 6 on In2.Cu, **0 on In1/B.Cu**, plus **1,990 vias**. The settled wave-18
instrument (`04_measure.py`) read **F.Cu and B.Cu only**. On that instrument every phase row
reads `FRAGMENTED / 0` — and that is a property of the *instrument*, not of the board: the
phase conductor of this stack-up lives on **In2.Cu**.

I re-measured all six power classes × 6 cells on **all four copper layers**, with IPC-2221
rated **per layer at its own k** (0.048 external for F.Cu/B.Cu, **0.024 internal for
In1/In2** — the settled constants). Grid 0.04 mm, calibration worst |err| **0.057 mm**,
instrument `corridor_lib` unchanged from the corridor-instrument wave.

**As-built, per class (6 cells identical within measurement noise) [native] — `02_base.json`:**

| class | span | F.Cu free | own conductor | In1 | In2 | B.Cu | ampacity | need | verdict |
|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| BATP_IN | 17.1 | 12.93 | **F.Cu 10.12** | — | — | — | **38.5 A** | 8.413 | PASS |
| BATP | 47.8 | 3.46 | F.Cu frag. | **In1 7.71** | — | — | **9.6 A** | 8.413 | **FAIL** |
| BATN | 19.7 | 13.12 | F.Cu frag. | — | — | **B.Cu 22.88** | **69.6 A** | 8.413 | PASS |
| PHASE_A | 30.6 | **3.90** | F.Cu frag. | — | **In2 12.39** | — | **13.5 A** | 9.427 | **FAIL** |
| PHASE_B | 30.5 | **−0.50** | F.Cu frag. | — | **In2 13.52** | — | **14.4 A** | 9.427 | **FAIL** |
| PHASE_C | 30.4 | **0.70** | F.Cu frag. | — | **In2 12.80** | — | **13.8 A** | 9.427 | **FAIL** |

Two numbers in this table are corrections to the settled record, and both are instrument
effects, not disagreements about the board:

1. **The phase corridor reproduces: 3.90 / −0.50 / 0.70 mm on F.Cu** (settled: 3.90 / no lane
   / 0.70). BATP reads **3.46** here against the settled 3.32 because this run is at 0.04 mm
   grid, not the 0.10 mm grid the 3.32 came from; the 0.10 mm re-run reproduces 3.32 exactly.
2. **The phase nets are not at 0 A.** In2.Cu carries a terminal-to-terminal conductor of
   **12.39 / 13.52 / 12.80 mm** — 13.5 / 14.4 / 13.8 A at the internal k. Wave 18's "19.4 A"
   was its own added **F.Cu** pour measured on F.Cu; it is not this conductor and it is not a
   contradiction. What *is* a contradiction is wave 18's `own FRAGMENTED, 0 A` for the phase
   nets: on In2 the pours conduct.

So the deficit at the settled design point is, per phase, **36.6 − 13.5…14.4 ≈ 22–23 A** to be
found on **F.Cu**, which needs **4.7–5.0 mm** of F.Cu conductor at 105 µm. The corridors offer
3.90 / −0.50 / 0.70 mm. That is the gap, and it is a *corridor* gap.

> **The k constant is load-bearing here and is applied per layer.** Rated at 0.048 the same
> In2 bands read 27.0 / 28.8 / 27.6 A and the phases look 75 % done. They are 37 %. An
> inner-layer ampacity taken at the external constant is precisely the kind of plausible-green
> number this programme has been shipping; `06_gate36.py` from wave 18 did it for every layer,
> but only ever read outer layers, so it never bit.

---

## 3. The pour-clearing experiment: the corridor opens — for two of the three phases

Method (`06_build.py`, deterministic, one pass, saves after each stage). An **F.Cu copper-pour
keepout** (rule area; vias, tracks and pads allowed) is placed along a corridor and then **all
zones are re-filled by KiCad's own filler**. That is "clear the pours local to the corridor"
expressed as a real, reviewable design object, and it removes *only pour* — never a pad, via or
track, which are the things that cannot move. Band = 10.13 mm wide (the 9.427 mm the design point
needs plus 2 × 0.200 pattern clearance plus 0.15 margin), centred on the maximin path where one
exists and on the straight FET→lug line where none does (PHASE_B at the start). Then measure,
clear again on the *new* path, until the lane stops moving. Three rounds per stage; the fixed point
is the answer.

**Corridor width per phase, before / after, all six power classes (mm; free gap, and the passable
width at 0.25 mm clearance in brackets) [native] — `06_build.json`, `02_base.json`, `02_final.json`:**

| class | as-built | after 1 clearing | after 2 clearings | fixed point | pour-free control (`NOZONES`) |
|---|---:|---:|---:|---:|---:|
| **PHASE_A** | 4.40 (3.90) | 7.40 (6.90) | **8.80 (8.30)** | 8.80 | 8.80 (8.30) |
| **PHASE_B** | **0.00 (−0.50)** | 1.60 (1.10) | **5.60 (5.10)** | 5.60 | 5.60 (5.10) |
| **PHASE_C** | 1.20 (0.70) | 1.80 (1.30) | 1.80 (1.30) | **1.80 — STUCK** | 5.80 (5.30) |
| **BATP** | 3.96 (3.46) | 3.96 | 6.20 (5.70) | 6.20 | 6.20 (5.70) |
| **BATP_IN** | 13.40 (12.90) | 13.40 | 13.40 | 13.40 | 6.20 |
| **BATN** | 13.56 (13.06) | 13.56 | 13.95 (13.45) | 13.95 | — |

(the same six numbers reproduce identically in all six cells — the cells are copies, checked)

**The hypothesis is confirmed for four of the six classes, and the confirmation is exact**: PHASE_A
lands on 8.80 mm and PHASE_B on 5.60 mm, *equal to the pour-free control's own values* (8.80 /
5.60). Two independent instruments — local clearing on the real board, and the wave-18
whole-board pour strip — agree to 0.00 mm. **PHASE_B was not lane-less. It was pour-closed, and
5.10 mm of legal corridor is recoverable by removing pour along the corridor only.**

**PHASE_C does not open — and it is left UNRESOLVED, not called blocked.** 0.70 → 1.30 mm and
there it stays: three further clearing rounds, placed on the **straight** FET→lug line instead of
on C's (detouring) maximin path, changed it by **0.00 mm** in all six cells (`05d_clearC.json`,
30 rule areas on that board). The band census explains why this is not yet a result
(`05c_bandcensus.py` `[native]`, 10.13 mm band, foreign pour fraction inside it):

| band | as built | after clearing | foreign vias in band | foreign F.Cu tracks in band |
|---|---:|---:|---|---|
| PHASE_A | 49.9 % | **18.1 %** | 1 (`M#_BATP`) | 0 |
| PHASE_B | 49.9 % | **2.5 %** | 0 | 0 |
| PHASE_C | 49.9 % | **45.9 %** | 4 (`M#_BATP`) | 0 |

A and B cleared as designed; **C's band still holds 45.9 % foreign pour after 12 keepouts**, and
adding 18 more straight-line keepouts moved neither the pour nor the lane. Two readings are
possible — the pour in C's band is not what binds its lane, or C's keepouts are not landing on
C's blockage — and **I could not separate them in the time available**. Against the pour-free
control's 5.80 mm (5.30 passable) that discrepancy is unexplained, and an unexplained discrepancy
is not evidence. So PHASE_C is reported as **1.30 mm measured / cause not established**, and the
claim in §4 is limited to what is proven: A and B open to their pour-free ceilings exactly; C does
not respond to pour clearing.

**The price of the clearing, as a set diff (rule file unchanged, 0.200/0.200) [native]:**

| board | DRC | by type | F.Cu pour fill | rule areas |
|---|---:|---|---:|---:|
| as built | **102** | 70 annular, 16 via_diameter, 16 via_dangling | 10,972.5 mm² | 0 |
| cleared (shipped state of stage 2) | **291** | 70 annular, 16 via_diameter, **199 via_dangling**, 6 starved_thermal | **5,952.3 mm²** (−45.8 %) | 48 |

```
SET DIFF cleared - base :  GONE 12 (via_dangling)   ADDED 195 via_dangling + 6 starved_thermal   unchanged 90
```

Two costs, both real and both stated: **183 vias lose one end** (the pour that used to land on them
is gone) and the `BATP_IN` conductor shrinks **10.12 → 7.52 mm** (38.5 → 31.1 A) because the phase
keepouts cut the `BATP_IN` spread. Neither is a short; both need attention before a fab order, and
both are avoidable by narrowing the band (the deficit needs only ~5 mm, not 10.13 mm), which was not
swept — that is a named, un-run refinement, not a claimed result.

## 4. PHASE_B: it has a lane. PHASE_C is the phase that does not respond.

The assignment's conditional — *"if PHASE_B genuinely has no lane, say so with the geometry"* —
does not fire. Measured:

| | as-built | after local pour clearing |
|---|---:|---:|
| PHASE_B corridor (FET source tab → motor lug pin 2) | **0.00 mm gap, −0.50 mm passable** | **5.60 mm gap, 5.10 mm passable** |
| what occupies the corridor | the `M#_PHASE_B` pour and its neighbours: **49.9 %** of the 10.13 mm band is foreign pour, and the 0.00 mm lane is what that costs | **2.5 %** — the band is clear (census in §3) |

What would have to move for PHASE_B: **the pours** — and they did, at a cost of 45.8 % of the F.Cu
pour area. Nothing else: the band census inside B's corridor finds **0 foreign vias**, and after
clearing the lane equals the pour-free control exactly. So B is a *copper-weight* problem, not a
placement problem.

PHASE_C is the exception and is **not** resolved here: 1.30 mm, unchanged by six clearing attempts,
with 45.9 % of its band still carrying foreign pour that the keepouts did not remove (table in §3).
Its band holds **no foreign F.Cu tracks** and only **4 foreign vias**, so neither the signal
fan-out nor the via field explains a 1.30 mm lane. The honest statement is that PHASE_C is the one
phase whose corridor I could not open **and** could not attribute, and that the next instrument to
run is a per-station pinch probe (`05b_pinch.py`, written, did not finish — an all-objects polygon
index over 3.4 k pads does not complete in the available time).

## 5. What was routed, and what the routing itself exposed

`07b_route.py` routes in the order the assignment asks — **power corridors first**, then the rails —
with the width set from the *measured deficit*, not from a millimetre target:

  * deficit = 36.6 A (or 33.7 A bus) minus what the row **already** conducts on its other layers
    (In2 phases 13.5–14.4 A, In1 BATP 10.1 A, B.Cu BATN 69.6 A);
  * `w = min(width_for(deficit), corridor − 2 × 0.200)`, centreline legal by construction
    (every chord re-checked), then each segment validated **exactly** in shapely against foreign
    copper (≥ 0.22 mm) and the board edge (≥ 0.52 mm) and narrowed if it fails;
  * seeds are the terminal pads' own copper, not a disc around a centroid — v1 seeded a 3 mm disc
    and placed 20 shorts because a 5 mm track's end cap overhung the neighbouring phase;
  * **all zones re-filled afterwards**, so the pours close around the conductor rather than through it.

| row | routed | planned w | measured own band | measured capacity | at 36.6 / 33.7 A |
|---|---|---:|---:|---:|---|
| PHASE_A ×6 | yes, 2 segs, 22.1 mm | 4.93 mm | **0.64 mm** | 13.7 + 5.2 = **18.9 A** | no (52 %) |
| PHASE_B ×6 | yes, 2 segs, 21.0 mm | 4.74 mm | **0.64 mm** | 14.4 + 5.2 = **19.6 A** | no (54 %) |
| PHASE_C ×6 | yes, 12 segs, 41.3 mm | 1.21 mm | 1.20 mm | 14.3 + 8.2 = **22.5 A** | no (62 %) |
| BATP ×6 | yes, 8 segs, 56.9 mm | 4.63 mm | 4.63 mm | 10.1 + 21.9 = **32.0 A** | no (95 %) |
| BATP_IN ×6 | yes, 1 seg, 16.1 mm | 0.25 mm | 7.52 mm (unchanged) | **31.1 A** | no (92 %) |
| BATN ×6 | none needed | — | 22.88 mm | **69.6 A** | **yes** |

**30 of 36 rows now carry a conductor spanning their terminals; 6 of 36 (all BATN) meet the design
point.** The routed board is **not** a fab-ready board, and the reason is the finding, not the
shortfall:

> **The corridors are not independent.** Each corridor was measured as *that net's* widest lane, so
> the six numbers in §3 each spend the same shared space. Routing all of them at once is what
> exposes it: the 5.14 mm `BATP` rail track lies **0.00 mm** from the `PHASE_A` corridor, and once
> it is there PHASE_A's free lane collapses **8.30 → −0.10 mm**. Result: **18 shorting_items, 6
> clearance, 6 tracks_crossing, 12 connection_width** — a routed-vs-cleared set diff of
> `GONE 68 / ADDED 110`. The 0.64 mm own-band on the phase rows is the same story from the other
> side: a 4.93 mm track that has a foreign net's 5.14 mm track lying across it is not a 4.93 mm
> conductor.
>
> So the honest capacity statement is **not** "the corridor is 8.30 mm, therefore 36.6 A". On one
> F.Cu layer, in that region, there is room for **one** wide power conductor and there are four
> (`BATP`, PHASE_A, PHASE_B, PHASE_C). That is a budget problem no per-net corridor measurement can
> see, and it is why the per-net number must never be quoted as a routability result.

## 6. Unconnected, on both tools, after each class — and the 499 is a cap

| state | kicad-cli `unconnected_items` | pcbnew ratsnest (uncapped) | what changed |
|---|---:|---:|---|
| as built (3 oz) | 499 | **1,542** | — |
| after power pour clearing | 499 | **1,638** | +96: the vias that lost their pour |
| after power routing (30 rows) | 499 | **1,638** | 0 — those 30 rows were already joined in KiCad's model (the In2/In1 planes join them); the tracks add capacity, not connectivity |
| after signal pass (26 edges closed) | 499 | **1,612** | −26, exactly one per edge |

**The 499 is the CLI's list cap, not a measurement.** It is identical on four different boards
(base, cleared, routed, signal) and against two different rule sets; pcbnew's uncapped ratsnest is
the only number that moves. That is the same cap the `kicad-board-audit` skill warns about, and it
means **every unconnected delta in this programme's ESC reports, including wave 18's "499
unchanged", was measuring the cap.** The corrected basis: **1,542 → 1,612 (−26 on the signal class,
+96 on power, net +70)**.

Where the unconnected actually is (CLI rows by net on the as-built board — the *shape* of the set
is still valid even though the count is capped): `M1/M2/M3_BATN` **56 each (168)**, `DGND` 85,
`3V3` 59, `5V` 19, `AUX_GND` 19, `M1/M2/M3_BATP` 7 each, phase rows 2–3 each. The three BATN cells
dominate: the decoupling pads and IC return pins are on F.Cu with the plane on B.Cu, and the
pad→plane transitions are the routing job — 168 of the 226 power-class rows.

The signal pass closed **26 of 69 addressable edges** (41 had no legal lane at 0.25 mm, 2 could not
be resolved to an item); it cost 7 shorting_items + 4 clearance + 4 solder_mask_bridge against 5
shorts + 1 crossing cleared — a net DRC loss, reported rather than hidden. Its real yield is the
**−26** in the pcbnew count.

## 7. The gate at 36.6 A — G1…G8 on the routed board (`10_gate.py`) [native]

| ID | condition | n | worst measured | required | verdict |
|---|---|---:|---:|---:|---|
| G1 | phase capacity ≥ 36.6 A | 18 | **18.9 A** (M1 PHASE_A; F.Cu own 0.64) | 36.6 | **FAIL** (18/18) |
| G2 | BATP_IN/BATP ≥ 33.7 A | 12 | **31.1 A** (M1 BATP_IN) | 33.7 | **FAIL** (12/12) |
| G3 | BATN ≥ 33.7 A | 6 | 69.6 A (B.Cu 22.88 mm) | 33.7 | PASS |
| G4 | no component on B.Cu/inner | 1 | 0 (F=687, B=0, inner=0) | 0 | PASS |
| G5 | spreader reserved and stated | 1 | rects=0, 0/36 TOLTs, no declaration | 36 | **FAIL** |
| G6 | barrels per transition @ 1.50 A | 60 | 2–4 barrels vs 15 needed | 15 | PASS* |
| G7 | Tj ≤ 175 °C at TA 45 °C | 1 | 84.9 °C (gate model) / 119.6 °C (settled) | 175 | PASS |
| G8 | back-layer budget ≤ 50 % | 6 | **64.0 %** (cell 6) | 50 | **FAIL** |

```
4 PASS, 4 FAIL (G1,G2,G5,G8), 0 UNMEASURABLE  ->  EXIT 1
```

\* **G6 passes only because of the transition test the gate of record declared**: a THT pad, or a
pad whose rail conductor is on the same side, needs no barrel. The measured population is **2–4
barrels per terminal against the 15 a 33.7 A transition would need**, and the In1/In2/B.Cu feeds do
have to change layer at some point — so G6's PASS is a statement about the test, not about the
board. Wave 18 recorded the same condition as FAIL (2 vs 15) when it read the rails on B.Cu. Both
readings are printed in `gate_routed.json`; the stricter one is the one a fab would quote.

## 8. Final state, and the single thing that blocks a fab order

| measure | as built | cleared | routed | signal |
|---|---:|---:|---:|---:|
| DRC (3 oz, 0.200/0.200, `kicad-cli`) | **102** | 291 | **333** | 342 |
| — shorts / crossings | 0 / 0 | 0 / 0 | **18 / 6** | 20 / 5 |
| — annular / via_diameter / via_dangling | 70/16/16 | 70/16/**199** | 70/16/199 | 70/16/199 |
| unconnected, pcbnew (uncapped) | **1,542** | 1,638 | 1,638 | **1,612** |
| unconnected, kicad-cli | 499 (cap) | 499 (cap) | 499 (cap) | 499 (cap) |
| power rows with an F.Cu conductor spanning the terminals | 6/36 | 6/36 | **30/36** | 30/36 |
| power rows AT the design point (any layer) | **12/36** | 12/36 | **6/36** | 6/36 |
| routed fraction (30 of 36 power rows) | — | — | **83 %** | 83 % |
| gate | — | — | **EXIT 1** | — |

**Power path complete at the settled 36.6 A design point: NO.**

**The single thing that blocks a fab order is the phase conductor's capacity, and it is now a space
budget rather than a corridor width.** In2.Cu already carries 13.5–14.4 A per phase (12.4–13.5 mm
bands at k = 0.024); 36.6 A needs another ~4.7–5.0 mm of F.Cu. Local pour clearing *does* produce
those lanes — 8.30 mm on PHASE_A and 5.10 mm on PHASE_B, both exactly the pour-free ceiling — but
on one F.Cu layer in that region there is room for **one** wide conductor while `BATP`, PHASE_A,
PHASE_B and PHASE_C all want one: the moment BATP's 5.14 mm track goes down, PHASE_A's lane reads
−0.10 mm and the board shorts in 18 places. PHASE_C is a second, separate blocker: 1.30 mm,
and six clearing attempts (30 keepouts, path-following and straight-line) moved it by 0.00 mm while its
band still held 45.9 % foreign pour — unresolved in this wave, and not to be quoted as
"structurally impossible". Fixing either needs a **design change** — a second dedicated power layer
(one phase per inner layer, which the stack-up does not have), a wider phase window from
re-placement, or more parallel terminals at the motor lug. Re-routing the same layer cannot close
it, and this wave measured that rather than argued it.

Second-order items a fab quote would still have to clear: the **+183 dangling vias and −45.8 % F.Cu
pour** that the clearing costs; `BATP_IN`'s conductor falling 10.12 → 7.52 mm as collateral; G5
(no spreader reservation on this file, 0 of 36 TOLTs); G8 (cell 6 back layer at 64 %); and the
102 → 70-row annular question, unchanged from wave 18 (0.150 mm ring clears 70 rows, a fab-quote
item).

---

## Files

| file | what it is |
|---|---|
| `00_probe.py/json` | 96-zone layer census (66 F.Cu / 6 B.Cu / 6 In1 / 18 In2), unconnected by net |
| `02_measure.py`, `02_base.json`, `02_final.json`, `02_routed.json` | the six classes on four layers with per-layer k — before, cleared, routed |
| `03_clear.py/json`, `drc_clear.json` | the single-band clearing experiment and its DRC cost |
| `04_iter.py`, `logs/04_iter.log` | the iterated clearing that found the fixed point (hung before saving; kept as evidence of the ladder) |
| `06_build.py/json`, `boards/escfinal*.kicad_pcb` | the staged, saving build: phase corridors then rails, 48 keepouts |
| `05b_pinch.py` | per-station pinch probe (written, did not finish: an all-objects polygon-distance index over 3.4 k pads does not complete) |
| `05c_bandcensus.py/json` | what is inside each phase band: foreign vias, tracks, pour fraction — the measurement that bounds PHASE_C |
| `05d_clearC.py/json`, `boards/esccC.kicad_pcb` | PHASE_C cleared on the straight line, 3 rounds: 0.00 mm change |
| `07b_route.py`, `07_route.json`, `boards/esfrouted2.kicad_pcb` | the routed power path (v2: pad-anchored, exact-validated) |
| `08_edges.py/json`, `boards/esfr_signal.kicad_pcb` | the signal-class edge closer (26 of 69) |
| `09_conn.py/json` | uncapped pcbnew ratsnest on base / cleared / routed |
| `10_gate.py`, `gate_routed.json` | G1–G8 at 36.6 A, exit 1 |
| `11_setdiff.py`, `11_setdiff.json`, `logs/11_setdiff.log` | row-level DRC set diffs, never totals |
| `boards/` | every board is a COPY; the repository file was never written |
