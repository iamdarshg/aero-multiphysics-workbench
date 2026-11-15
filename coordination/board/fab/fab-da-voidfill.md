# fab-da-voidfill — the RF void fix, rebuilt as a fab-buildable board with **zero new vias**

**Item.** The RF void fix was blocked because both candidate repairs needed a **buried In1→B.Cu via**
at the tee junction (95.250, 64.381), which the no-HDI constraint forbids: a 0.6 mm through via there
needs 0.425 mm to the CC_PA edge and has 0.1081 mm.

**Result in one line.** The buried via was never required. Move the In1 chain to B.Cu **at identical
XY** and it lands on **through vias that already exist at both ends**; the one micro-via tap is then
reached from an existing through via *over In1*, west of every RF_50R footprint. **Vias added: 0.
Vias removed: 0. Void 9.834 % → 1.296 % (physically real copper: 9.139 % → 0.601 %). DRC 0 / 0.**

**Board:** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb`, branch `work/2026-11-11`,
read-only, never saved. Every write is inside `evidence/fab-da-voidfill/`.
**Tools:** KiCad 9.0.7 `pcbnew` (numpy 2.3.5 / scipy 1.17.1), `kicad-cli pcb drc`,
`kicad-cli pcb export drill`.

---

## 0. Answers in one screen

| question | answer |
|---|---|
| Is a route legal with standard through vias only? | **YES — and it needs no new via at all.** 5 segments change layer at identical XY; both ends land on existing `VIATYPE_THROUGH` vias. |
| Copper moves made | **6 In1 objects removed, 6 added**: 5 segments (10.5205 mm) re-layered In1→B.Cu, the 0.2069 mm tee deleted, one 1.3744 mm In1 link added to the existing through via A. **0 vias touched.** |
| UNCONNECTED after | **0** (`kicad-cli` `unconnected_items` = 0; `pcbnew` `GetUnconnectedCount` = 0) |
| DRC after | **0 violations** (baseline control `v_r0` is also 0, so the ruleset is live, not suppressed) |
| MIN_DRILL after | **0.100 mm — unchanged, and not this fix's population.** The fix adds no via. The board still carries **33 × 0.100 mm microvias + 3 × 0.300 mm blind vias**; the 0.100 mm one the design *needs* here sits at U40 pad 15 and **cannot** become a 0.2 mm through via under the board's own rules (measured: 0.018 mm short — §6). |
| VOID after | **1.296 %** (0.5495 of 42.4040 mm²) by wave-2's definition; **0.601 %** (0.2550 mm²) when via annuli count as the copper they are |
| Over solid reference? | **YES over 99.399 %** of the RF area. The 0.601 % left is 3 discrete spots: **0.1627 mm²** at the GNSS crossing and **2 × 0.0461 mm²** at CC_LNA_N's *own* via annuli. CC_PA and CC_LNA_P are **100.00 %** supported. |
| Script / patch | `10_build.py` (build), `11_refill.py` (refill), `20_measure.py` (void), `15_patch.py` → **`patch_r3.json`**; board artefact **`fixwork/v_r3.kicad_pcb`** |

---

## 1. Why the buried via was never needed — the topology, measured

`01_probe.py` / `01_probe.json` dump every object of `/915 MHz RF/VDD_CC112`. The In1 wire had
**four standard through vias already sitting on it**:

| via | at | drill / pad | layers |
|---|---|---|---|
| **A** | (93.7876, 64.3811) | 0.350 / 0.700 | F–In1–In2–B (`via_type` 3) |
| B (through the 0.134 mm stub) | (98.9978, 64.2865) | 0.350 / 0.700 | F–In1–In2–B |
| C | (97.4658, 60.0385) | 0.350 / 0.700 | F–In1–In2–B |
| D | (96.3783, 58.5625) | 0.350 / 0.700 | F–In1–In2–B |
| **M** | (95.150, 64.200) | **0.100 / 0.300** | **F–In1 microvia only** |

The chain `A → horizontal → B → …` was **one In1 wire with the tee hanging off its middle**
(`01_probe.out.txt:308`: the 0.2069 mm In1 stub (95.150,64.200)→(95.250,64.3811)). A middle tap on a
single-layer wire is what forces a mid-span layer transition — hence the buried via.

**Re-layer the wire and the middle tap disappears.** With the whole chain on B.Cu, both ends of the
wire land on A and B, which are through vias; the microvia's In1 pad is then fed **from A over In1**
(1.3744 mm, entirely west of x = 95.17 where CC_PA's footprint begins) instead of from a buried via
at the tight point. Nothing about the topology needs a via that does not already exist.

---

## 2. The patch (`patch_r3.json`, `15_patch.py` → `15_patch.out.txt`)

Zone (In1, `/3V3`): **local clearance 0.250 → 0.125, min_thickness 0.250 → 0.100**. Two values, no
copper. Justification: 0.125 mm is already the board's global minimum clearance
(`01_probe.json:rules.min_clearance`) and every In1 netclass clearance is 0.125.

| # | edit | object |
|---|---|---|
| 1 | **In1 → B.Cu**, identical XY | (98.9978,61.5705)→(98.9978,64.2865) w 0.250, 2.7160 mm |
| 2 | **In1 → B.Cu**, identical XY | (98.9032,64.3811)→(93.7876,64.3811) w 0.250, 5.1156 mm |
| 3 | **In1 → B.Cu**, identical XY | (97.4658,60.0385)→(98.9978,61.5705) w 0.250, 2.1666 mm |
| 4 | **In1 → B.Cu**, identical XY | (96.3783,58.9510)→(96.3783,58.5625) w 0.250, 0.3885 mm |
| 5 | **In1 → B.Cu**, identical XY | (98.9978,64.2865)→(98.9032,64.3811) w 0.250, 0.1338 mm |
| 6 | **In1 deleted** | the 0.2069 mm tee (95.1500,64.2000)→(95.2500,64.3811) |
| 7 | **In1 added** | (95.1500,64.2000)→(93.7876,64.3811) w 0.250, 1.3744 mm (microvia → through via A) |
| — | **left on In1** | (97.4658,60.0385)→(96.3783,58.9510) 1.538 mm — its B.Cu drop **shorts /HGM** (see §7) |

Total copper moved: **10.5205 mm** of In1 track. In1 signal length for this net: 12.2654 mm → 2.9124 mm.
**No net was deleted** — every segment kept its net code; the moves are layer-property edits, so no
rerouting, no length change, no new object except the single In1 link.

Cost, measured by refill (`11_refill.py`): B.Cu `/GND` pour **12728.793 → 12723.667 mm² = −5.126 mm²**.
F.Cu `/GND` pour unchanged (12188.556). In1 `/3V3` pour 12164.050 → 12591.471 (**+427.421 mm²** of
reference copper, of which +405.5 comes from the clearance value and +21.9 from the moves).
Stackup (`main_rev_b.kicad_pcb:50-85`): every copper layer is `(thickness 0.035)` — In1 and B.Cu are
the **same 1 oz copper**, so re-layering a 0.25 mm power track from In1 to B.Cu is **not** a
current-carrying change.

---

## 3. Results, every variant built as real copper

`10_build.py` → `11_refill.py` (separate process, SWIG invalidates zones after track edits) →
`20_measure.py` → `kicad-cli pcb drc`. `VOID_TABLE.csv`, `20_measure.json`, `50_drc_*.json`.

| tag | what it is | void_A mm² | **void_A %** | void_B mm² | **void_B %** | DRC | unconn |
|---|---|---|---|---|---|---|---|
| **r0** | untouched copy (**control**) | 4.1699 | **9.834** | 3.8754 | 9.139 | **0** | **0** |
| r1 | zone values only | 3.8025 | 8.967 | 3.5080 | 8.273 | 0 | 0 |
| r2 | r1 + 5 moves, tee left orphaned | 0.6249 | 1.474 | 0.3304 | 0.779 | 0 | **1** |
| **r3** | r2 + tee replaced by the In1 link — **RECOMMENDED** | **0.5495** | **1.296** | **0.2550** | **0.601** | **0** | **0** |
| r3n | r3 **without** the zone values (isolates the copper lever) | 0.8521 | 2.010 | 0.5576 | 1.315 | 0 | 0 |
| r5 | r3 + U40 pad 15's microvia → 0.2/0.3 through via | 0.5495 | 1.296 | 0.2550 | 0.601 | **2 (rule)** | 0 |
| r5b | r5 with that via's pad grown to 0.400 | — | — | — | — | **4** | 0 |
| r6 | scope probe: all 33 microvias → 0.2/0.4 through | — | — | — | — | 156 | 0 |

`void_A` is wave-2's definition (In1 tracks + pads + zone fill) and reproduces the board's **9.834 %**
to 0.0002 mm² on the untouched copy, so every number is comparable to wave-2 and to
`dec-voidfill-buildable`. `void_B` adds the one object that definition omits: **through-via In1
annuli**, which are copper under the trace by any physical reading.

**The two levers, separated.** Copper alone (r3n) takes 9.834 → 2.010 %; the zone values alone (r1)
take 9.834 → 8.967 %; together (r3) 1.296 %. Neither is optional: the zone values buy 0.71 pp on top
of the moves, the moves buy 6.96 pp on top of the values.

---

## 4. Per-net table — what is still not solid (`VOID_TABLE.csv`)

| net | footprint mm² | r0 void_A % | **r3 void_A %** | **r3 void_B %** |
|---|---|---|---|---|
| `/915 MHz RF/CC_PA` | 2.5399 | 60.40 | **0.00** | 0.00 |
| `/915 MHz RF/CC_LNA_N` | 1.5024 | 88.15 | 25.75 | **6.14** |
| `/915 MHz RF/CC_LNA_P` | 1.8249 | 54.14 | **0.00** | 0.00 |
| `/GNSS/GNSS_RF_IN` | 4.2615 | 6.99 | 3.82 | **3.82** |
| `/915 MHz RF/RF_LNA_IN` | 1.0546 | 2.42 | 0.00 | 0.00 |
| 11 other RF_50R nets | 31.2207 | 0.00 | 0.00 | 0.00 |
| **TOTAL** | **42.4040** | **9.834** | **1.296** | **0.601** |

**Attribution of the 3 residual spots** (`21_cause.py` → `21_cause_r3.json`, which lists the In1
objects within 0.62 mm of each void's centroid):

| residual | void_A | void_B | cause, measured |
|---|---|---|---|
| CC_LNA_N @ (99.175, 61.015) | 0.1934 | **0.0461** | **CC_LNA_N's own through via**, `(99.300, 61.000)`, In1 pad r 0.300, drill 0.300 — the "void" is the 3V3 pour clearing around the RF net's own annulus |
| CC_LNA_N @ (101.104, 60.917) | 0.1934 | **0.0461** | same, via at `(101.000, 60.800)` |
| GNSS_RF_IN @ (94.218, 16.792) | 0.1462 | 0.1462 | `/GNSS/GNSS_RESET_OD` and `/GNSS/GNSS_UART_RX_2V8` In1 tracks (0.25 wide), each 0.208 mm from the void centre |
| GNSS_RF_IN @ (94.542, 16.470) | 0.0165 | 0.0165 | same two tracks |

So **no residual void is caused by `/915 MHz RF/VDD_CC112` any more** — the net this item was
assigned to contributes **0.0000 mm²** of the 0.5495 left.

---

## 5. Is the RF corridor over solid reference? Yes — 99.399 % of its area

RF_50R F.Cu footprint **42.4040 mm²**, all traces 0.35 mm wide → **121.15 mm of run**.

| | unsupported area | unsupported run | supported |
|---|---|---|---|
| as built (r0) | 3.8754 mm² | 11.07 mm | **90.86 %** |
| **r3** | **0.2550 mm²** | **0.73 mm** | **99.40 %** |

Of the 0.73 mm that is still not over In1 copper: **0.46 mm** at the GNSS crossing, **0.13 + 0.13 mm**
at CC_LNA_N's own two vias. Two of the four RF nets that had voids (CC_PA and CC_LNA_P) are now
**100 %** over solid pour.

**What this does and does not license.** The da-em-field Tier-B anchors are unchanged and not
re-derived here: **52.61 Ω** over solid In1, **118.12 Ω** with In1 absent. The corridor now sits at
the first value for 99.4 % of its length instead of 90.9 %. **S11 was not re-simulated** (UNVERIFIED);
what is measured is the geometry the model consumes.

---

## 6. MIN_DRILL — the honest answer, and the exact obstruction at this spot

**The fix adds no via**, so aggregate min drill is unchanged: **0.100 mm**, 33 sub-0.2 vias
(`20_measure.json:r3.vias_below_200um = 33`; via census **305 through + 33 microvia + 3 blind = 341**,
the same as the untouched board).

A drill-file receipt makes the fab consequence concrete — `kicad-cli pcb export drill` on `v_r3`
emits **six programs** because the board needs five plating classes:

| file | layer pair | holes | drill |
|---|---|---|---|
| `v_r3.drl` | 1–4 through | 333 | 0.200 / 0.300 / 0.350 / 0.600 |
| `v_r3-front-in1.drl` | 1–2 blind | 14 | 0.100 |
| `v_r3-front-in2.drl` | 1–3 blind | 3 | 0.100 |
| `v_r3-in1-back.drl` | 2–4 blind | 4 | 0.100 |
| `v_r3-in1-in2.drl` | 2–3 **buried** | 10 | 0.100 |
| `v_r3-in2-back.drl` | 3–4 blind | 5 | 0.100 ×2 + 0.300 ×3 |

**At the one via this design genuinely needs — U40 pad 15, (95.150, 64.200) — a standard through via
does not fit, and this is measured, not argued.** `fcu_tracks_near_tee` (`01_probe.out.txt:221`) puts
the CC_PA F.Cu edge **0.3068 mm** from that point.

* 0.6 mm pad (board rule `min_via_diameter`) → needs 0.300 + 0.125 = **0.425 mm** → **0.118 mm short**.
* 0.4 mm pad → needs **0.325 mm** → **0.018 mm short**. Built as **r5b** and DRC'd: the violation is
  reported at **exactly** this via — `netclass 'RF_50R' clearance 0.1250; actual 0.1068` (= 0.325 −
  0.3068 = 0.0182), plus `zone [/3V3] In1 … actual 0.1005` and `zone [/GND] B.Cu … actual 0.1505`.
* 0.3 mm pad → needs 0.275 mm → **fits** (0.032 mm margin). Built as **r5**: **0 unconnected**, but
  DRC reports `via_diameter 0.300 < 0.600` and `annular_width 0.050 < 0.100` — two **board-rule**
  errors, not geometry. Accepting them means running **0.05 mm annular ring**, the IPC class-2 floor,
  which is a fab-risk decision, not mine to take alone.
* There is no second placement to try. Westward is closed by U40's 0.5 mm pad pitch: `/CC_RBIAS`
  pad 14 sits at (94.750, 63.438) and its escape runs at **x = 94.650**, w 0.2 → copper edge at
  **x = 94.750** (`01_probe.out.txt:224-225`). A 0.6 pad 0.175 mm west of the microvia would need
  0.425 mm to CC_PA (0.3068 − 0.175 = 0.132) *and* 0.425 mm to CC_RBIAS (0.150) — worse on both
  sides. Eastward CC_PA's diagonal closes immediately. The window is genuinely one point wide.

**Board-wide conversion, scoped** (`13_build_hdi.py` → `r6`, `13_vias_r6.json`, `50_drc_r6.json`):
all 33 sub-0.2 vias converted to 0.2 drill / 0.4 pad through vias. DRC: **156 violations**, of which
33 are the `via_diameter` rule (0.4 < 0.6, expected) and the rest are geometric. Of the **26 unique
sites**, **3 convert cleanly** at 0.2/0.4 — `(91.562,62.25) /RF_MOSI`, `(52.95,52.2) /RF_SCLK`,
`(54.8,77.5) /SENS_SCLK` — and **23 are blocked**, 20 by clearance and 3 by `holes_co_located`
(stacked microvias at one XY, which cannot become two coincident through holes, only one).

**Conclusion for the min-drill gate:** it cannot be closed by conversion. It needs a **fanout
re-plan** around U40 and the RP2354B, i.e. the separate HDI item — and this fix neither adds to nor
depends on more of it, except at U40 pad 15 where the dependency is now quantified to 0.018 mm.

---

## 7. The remaining lever, with its obstruction measured (not attempted)

Residual **0.1627 mm²** (63 % of what is left) is the GNSS crossing at (94.2, 16.8), where
`/GNSS/GNSS_RESET_OD` (100.173,23.042)→(84.513,7.382) and `/GNSS/GNSS_UART_RX_2V8`
(99.869,22.149)→(91.297,13.577) pass under `/GNSS/GNSS_RF_IN`.

Both are **exactly 45°** lines, `y = x − 77.131` and `y = x − 77.720`, i.e. **0.4165 mm apart
perpendicular**. A 0.6 mm through via standing on either track needs **0.425 mm** to the other →
**short by 0.0085 mm.** So a straight cut-and-dive on those tracks is illegal by 8.5 µm; it would need
either a **0.55 mm pad** (below the board's 0.6 rule) or a **0.5 mm perpendicular In1 jog** per via
(4 vias + 4 jogs + 2 B.Cu stubs). Priced, that is more design and more risk than 0.38 pp of void is
worth — and unlike the VDD_CC112 moves it cannot be done as a layer-property edit, so it *is* a
reroute. **Not attempted; recorded so nobody re-derives it.**

The 1.538 mm diagonal that stays on In1 (`97.4658,60.0385)→(96.3783,58.9510)`) is the same story:
`dec-voidfill-buildable` measured its straight B.Cu drop shorting **/HGM**. It contributes
**0.0000 mm²** of the residual (no RF_50R trace above it), so it stays.

---

## 8. Corrections this item carries

**BOARD CORRECTION (line 615-616 and 629 of `AGENT_BOARD.md`; `dec-voidfill-buildable/REPORT.md:189-199`
and `:230-235`).** The board records the B.Cu reroute as unverified and the buildability report prices
the fix as "5 copper moves + **one 0.1 mm HDI bridge via** + 2 zone values", adding that "the
alternative if sequential lamination is refused is a 0.6 mm through via, which needs CC_PA's escape
moved 0.317 mm". The *blockage* was real; the *conclusion* was not. The bridge via was an artefact of
keeping `A → B` as a single In1 wire. Re-layering it costs 5 layer-property edits and **zero vias** —
and it is now **cheaper than the buried-via version it replaces**: O4 (5 moves + buried via + 2 zone
values) = **1.477 %**, 0 unconnected, **3 DRC items**; **r3 = 1.296 %**, 0 unconnected, **0 DRC
items**, and it needs no extra lamination cycle for the bridge.

**Definitional correction (wave-2 `12_measure.py`, `dec-voidfill-buildable:5-6`).** The void union
counts In1 tracks and pads but **not through-via annuli**, so the headline number overstates the
missing copper. Measured both ways here: baseline **9.834 % → 9.139 %**, r3 **1.296 % → 0.601 %**.
The 0.7 pp gap is not noise; on r3 it is 54 % of the residual, and 2 of the 4 residual spots are
*the RF net's own vias*. Wave-2's number is kept for comparability, not because it is physical.

**Process note, self-caught.** The first build in this directory used `pcbnew.PCB_TRACK(t)` believing
it was a copy constructor; in KiCad 9 SWIG it returns a **zero-length track at (0,0) with no net**.
The result measured 1.474 % by *deleting* 5 segments — the exact defect this wave exists to correct
(board line 539: "the 1.307 % is a copy with 13 nets DELETED"). It was caught by a `copper_edge_clearance`
at (0,0) and 5 `track_dangling` items in DRC, rebuilt with `PCB_TRACK(b)` + explicit start/end/width/
net, and the B.Cu pour then moved by −5.126 mm², proving the copper is on B.Cu. **The number that
survived is from the second build**; `v_r2`/`v_r3`/`v_r3n`/`v_r5` in `fixwork/` are all post-fix.

---

## 9. NOT verified

* **S11 was not re-simulated.** The electrical statement is geometric (99.4 % of the run over solid
  In1) plus the existing Tier-B anchors 52.61 Ω / 118.12 Ω. No new EM run.
* **The zone-clearance edit was not thermally or current-wise reviewed** for `/3V3`: In1 `/3V3` pour
  area rises 12164.050 → 12591.471 mm² (+3.5 %), which is help, but 0.125 mm 3V3-to-signal spacing is
  a design-rule decision beyond void fill.
* **The 0.05 mm annular-ring option (r5) is not accepted** — it is built and measured, but whether a
  fab will run 0.2/0.3 PTH at 1 oz for standard money is not quoted here.
* **Mechanical/assembly impact** of the B.Cu power run under the RF corridor (shielding, not return
  path — B.Cu is 1.510 mm below F.Cu) was not re-analysed.
* **The GNSS lever was not built** (§7), and **r6 is a scope probe**, not a fix: it deliberately
  breaks the 0.6 mm via rule 33 times to see which sites are geometrically reachable.
* **No netlist/schematic parity check** was run; no net changed, so parity should be untouched.

---

## 10. Files and reproduction

| file | what |
|---|---|
| **`fixwork/v_r3.kicad_pcb`**, `v_r3.kicad_pro` | **the deliverable board** — refilled, 0 DRC, 0 unconnected |
| **`patch_r3.json`**, `15_patch.py`, `15_patch.out.txt` | object-level patch: 6 removed / 6 added / 0 vias |
| `01_probe.py/.json/.out.txt` | net topology, the 5 vias, netclass/design rules, stackup, pads |
| `10_build.py`, `10_build_r*.json` | the builder, one tag per variant |
| `11_refill.py` | zone refill in a fresh process (required after track edits) |
| `12_build_via.py`, `14_build_tightvia.py` | pad-15 via conversion (r5) and its 0.4 mm pad probe (r5b) |
| `13_build_hdi.py`, `13_vias_r6.json` | the 33-via conversion scope probe |
| `20_measure.py`, `20_measure.json`, `22_table.py`, `VOID_TABLE.csv`, `22_pernet.json` | void measurement, per net and per variant |
| `21_cause.py`, `21_cause_r3.json` | attribution of every residual void to a concrete object |
| `50_drc_*.json` | `kicad-cli` DRC for r0 (control), r1, r2, r3, r3n, r5, r5b, r6 |
| `drill_r3/*.drl` | the six NC drill programs of the fixed board (the min-drill receipt) |

```
"C:/Program Files/KiCad/9.0/bin/python.exe" 10_build.py r3
"C:/Program Files/KiCad/9.0/bin/python.exe" 11_refill.py r3
"C:/Program Files/KiCad/9.0/bin/python.exe" 20_measure.py r3
"C:/Program Files/KiCad/9.0/bin/python.exe" 21_cause.py r3
"C:/Program Files/KiCad/9.0/bin/python.exe" 15_patch.py r3
"C:/Program Files/KiCad/9.0/bin/kicad-cli.exe" pcb drc --format json -o 50_drc_r3.json fixwork/v_r3.kicad_pcb
```

**Verdict: the RF void fix is BUILDABLE.** 1.296 % void (0.601 % by real copper), 0 unconnected,
0 DRC violations, **no via added**, no HDI introduced, and the RF corridor is over solid In1
reference for 99.4 % of its length. The one remaining fab gate on this board — 33 sub-0.2 mm
microvias — is **untouched by this fix**, and its conversion is measured to be blocked at 23 of 26
sites, with the one site this design depends on short by exactly 0.018 mm.