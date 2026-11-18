# fab-da-consolidate — ONE drone-arm rev_b board that is both via-fixed and void-fixed

**Item:** `fab-da-consolidate` · **Board of record:** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb`
**Artefact:** `evidence/fab-da-consolidate/da_main_rev_b_composed.kicad_pcb`
(sha256 `5DBAE23888059E0B6D6F18DC3066924FB8194C5FD4DFA250186D3B024F6F73B6`, 2,257,418 B)
**Tooling:** KiCad 9.0.7 `pcbnew` (Python 3.11.5) + `kicad-cli pcb drc` / `pcb export drill`
**Repo:** read-only throughout. Nothing was written, committed, pushed, reset or branched; every
product of this item is inside this directory. No fab was contacted, no money spent, no rule changed.

---

## 0. Answers in one screen

| question | answer |
|---|---|
| Is there now one board that is both via-fixed and void-fixed? | **YES.** `da_main_rev_b_composed.kicad_pcb` |
| Composition order | **via fix first, then the void reroute** — the reroute terminates on through vias A and B at their existing XY |
| DRC under the board's own rules | **0 violations, 0 unconnected** |
| DRC under the no-HDI gate | **23 violations**, all `microvia_drill_out_of_range`, **0 unconnected** |
| Unconnected nets | **0** (`kicad-cli` `unconnected_items` = 0; `pcbnew` `GetUnconnectedCount` = 0) |
| Minimum drill | **0.100 mm — still HDI.** 23 microvias + 1 blind via remain |
| Via census | **338** vias: 0.100 × 23, 0.300 × 34, 0.350 × 281; non-through **24** (23 microvia, 1 blind) |
| Void under the RF corridor | **1.2959 %** (0.5495 of 42.4040 mm²) = wave-2's definition; **0.6013 %** (0.2550 mm²) counting via annuli as copper |
| What remains | **24 non-through vias in 20 groups, 13 nets — all 20 groups need a fan-out re-escape**, not a via edit. 9 of the 20 (not 13 — §6.2) have the via centre inside another net's copper |
| New conflict introduced | **No DRC or connectivity conflict.** Two measured side-effects: the via fix's 9 new through vias take **2.516 mm²** of In1 `/3V3` copper the void fix alone restores, and the reroute halves a separate 82 mm² In1 `/GND` sliver. The RF void fraction is **bit-identical** to the void-fixed board, so the composition costs nothing on the metric it exists for |

---

## 1. The three artefacts, audited — what each contains and lacks

All six numbers per board below are measured from the board file itself (`s01_census.py`) and from
`kicad-cli` (`s04_drc.py`). Raw output: `census.json`, `drc/summary.json`.

| metric | `package/` | `fixed.kicad_pcb` | `v_r3.kicad_pcb` | **composed** |
|---|---|---|---|---|
| vias | **341** | 338 | **341** | **338** |
| drill histogram | 0.100×**33** / 0.300×27 / 0.350×281 | 0.100×**23** / 0.300×34 / 0.350×281 | 0.100×**33** / 0.300×27 / 0.350×281 | 0.100×**23** / 0.300×34 / 0.350×281 |
| vias below 0.2 mm | **33** | **23** | **33** | **23** |
| non-through vias | **36** | **24** | **36** | **24** |
| minimum drill | **0.100** | **0.100** | **0.100** | **0.100** |
| track segments | 2,279 | 2,301 | 2,279 | 2,301 |
| unconnected | 0 | 0 | 0 | 0 |
| DRC, own rules | 0 | 0 | 0 | **0** |
| DRC, no-HDI gate | **33** | **23** | **33** | **23** |
| void_A under the RF corridor | **9.8338 %** | **9.8338 %** | **1.2959 %** | **1.2959 %** |
| void_B (via annuli = copper) | 9.1392 % | 9.1392 % | 0.6013 % | 0.6013 % |

### 1.1 `evidence/fab-da-vias/fixed.kicad_pcb` — the via fix only

**Contains** the executed via work: **12 sub-standard vias deleted, 9 × 0.300 / 0.600 mm standard
through vias added, 22 track segments added** (`board_diff.json` re-derives these counts from the
saved boards by UUID, independently of `edits.json`). 341 → 338 vias, 33 → 23 below 0.2 mm,
non-through 36 → 24, 2,279 → **2,301 segments = +22**.

**Lacks** the void fix: its In1 fill is the base fill — **4.1699 mm² / 9.8338 %** void, identical to
`base.kicad_pcb` to 4 decimal places.

> **BOARD CORRECTION (this item's own predecessor report, `fab-da-vias/REPORT.md:251` and `:354`).**
> That report says the executed set "adds **19** track segments totalling 3.30 mm". Measured here and
> by the wave-2 verifier: **+22 segments** (2,279 → 2,301). `edits.json` carries 13 *polylines* —
> **nine of them are 3-point (2 segments) and four are 1 segment**, 9×2 + 4×1 = **22** — so `edits.json`
> is right and the prose count was a polyline count, off by the nine splits.

### 1.2 `evidence/fab-da-voidfill/fixwork/v_r3.kicad_pcb` — the void fix only

**Contains** the reroute: **5 In1 chain segments re-layered to B.Cu at identical XY (10.5205 mm of
copper), the 0.2069 mm tee deleted, one 1.3744 mm In1 link added** to existing through via A
(`93.7876, 64.3811`), and the In1 `/3V3` zone re-parameterised **clearance 0.250 → 0.125,
min_thickness 0.250 → 0.100**. void 9.8338 % → **1.2959 %**.

**Lacks** the via fix: **341 vias, all 33 × 0.100 mm microvias and all 3 blind 0.300 mm vias are
still there**, no-HDI gate 33, minimum drill 0.100 mm.

### 1.3 `evidence/fab-da-gerbers/package/` — neither fix (the verifier's step-1 description is wrong)

**Contains** 11 Gerbers + `.gbrjob` + a 161-row position file + 7 Excellon programs, revision-stamped
REV B.

**Lacks** both fixes. Measured:

| drill program | holes | tools |
|---|---|---|
| `-PTH.drl` (1–4) | 327 | 0.200, 0.300, 0.350, 0.600 |
| `-front-in1.drl` (1–2 blind) | 14 | **0.100** |
| `-front-in2.drl` (1–3 blind) | 3 | **0.100** |
| `-in1-back.drl` (2–4 blind) | 4 | **0.100** |
| `-in1-in2.drl` (2–3 buried) | 10 | **0.100** |
| `-in2-back.drl` (3–4 blind) | 5 | **0.100**×2, 0.300×3 |
| `-NPTH.drl` | 6 | 0.650, 4.300 |

**33 holes at 0.100 mm** across five layer pairs — the un-fixed number.

The package carries no `.kicad_pcb`, so its copper state was established by **reproducing it**:
`kicad-cli pcb export drill` run on `fab-da-gerbers/work/main_rev_b.kicad_pcb` yields files that are
**content-identical line-for-line** to the package's, differing only in the embedded creation
timestamp (`work/drill_pkg_repro/`, 7/7 files, 0 diff-lines except the date). That board measures
**341 vias / 33 sub-0.2 / 36 non-through / void 9.8338 %** — the un-fixed board.

> **BOARD CORRECTION (wave-2 verifier, restated in this item's brief).** *"package/ has the via fix"*
> is **refuted**. The package is a rev-stamped export of the **unfixed** board, and its own README
> says so: *"This package still contains 33 x 0.100 mm blind/buried vias across 5 layer pairs (36
> blind/buried vias in total)"* — `fab-da-gerbers/package/FAB-README-REV-B.txt:48-50`. So the three
> artefacts were **two, not three**: fixed.kicad_pcb (via only) and v_r3 (void only); the package is a
> third *rendering* of the **unfixed** board and never was a candidate.

---

## 2. Composition — order, and why that order

**Order: A = via fix, then B = void reroute.** The dependency is physical, not stylistic: the reroute
terminates on through vias **A** `(93.7876, 64.3811)` and **B** `(98.9978, 64.2865)` *at their
existing XY*, and re-layers In1 chain copper that the via fix does not touch. Choose the copper first
and you may land it on a via the via fix has since moved. Via set final ⇒ then the copper.

`s02_compose.py A` → `work/c_via.kicad_pcb` (stage A, refilled)
`s02_compose.py B` → `work/composed.kicad_pcb` (stage A + B, refilled)

| stage | edit | count |
|---|---|---|
| **A** | vias deleted by UUID (`edits.json`) | **12** (10 × 0.100 microvia, 2 × 0.300 blind) |
| **A** | standard through vias added, all 0.300 drill / 0.600 pad | **9** |
| **A** | track segments added (13 polylines → 22 segments) | **22** |
| **A** | UUIDs in `edits.json` not found on the board | **0** |
| **B** | In1 chain segments re-layered In1 → B.Cu at identical XY | **5** (10.5205 mm) |
| **B** | tee deleted | **1** (0.2069 mm) |
| **B** | In1 link added, microvia → through via A | **1** (1.3744 mm) |
| **B** | In1 diagonals of the net deliberately left on In1 | **1** (1.538 mm, its B.Cu drop would short `/HGM`) |
| **B** | zone parameters: In1 `/3V3` clearance 0.250 → 0.125, min_thickness 0.250 → 0.100 | **1 zone** |
| **B** | vias touched | **0** |

`compose_manifest.json` is the machine-readable manifest; `stage_A.json` / `stage_B.json` are the
per-stage receipts.

**Independent confirmation (`s06_diff.py` → `board_diff.json`).** Rather than trust the manifest, the
saved boards were diffed by object **UUID**:

```
removed 18 (vias 12, tracks 6) | added 37 (vias 9, tracks 28) | modified 0
layer-move pairs 5 | zone params changed 1
```

* removed tracks 6 = 5 re-layered chain segments + the tee ✔
* added tracks 28 = 22 (via fix) + 5 B.Cu replacements + 1 In1 link ✔
* 5 layer-move pairs matched by **identical endpoints and width, different layer** — the "identical
  XY" claim is verified, not restated ✔
* `modified 0` — no surviving object changed net, width, drill, pad or position ✔

**Process note (why the build is in three processes).** KiCad 9.0.7's SWIG bindings take an access
violation (`0xC0000005`) while destroying `ZONE_FILLER` state in a process that also holds track/via
references. The first attempt crashed mid-`Save`. So: `s02_compose.py` edits and saves **unfilled**,
`s03_refill.py` loads → fills → saves → `os._exit()` and nothing else, and every *observation* of
the result is another process (`s01_census.py`) or `kicad-cli`. The same class of trap as the wave-1
`PCB_TRACK(t)` finding — a saved board that is not the board you think you saved is the failure mode
this discipline prevents.

---

## 3. Verification of the composed board

### 3.1 DRC, both rule sets (`s04_drc.py`, `drc/`)

| board | own rules | unconnected | no-HDI gate | gate unconnected |
|---|---|---|---|---|
| `base.kicad_pcb` (control) | 0 | 0 | **33** | 0 |
| `pkg` = `fab-da-gerbers/work/main_rev_b.kicad_pcb` | 0 | 0 | **33** | 0 |
| `fixed.kicad_pcb` (artefact 1) | 0 | 0 | **23** | 0 |
| `v_r3.kicad_pcb` (artefact 2) | 0 | 0 | **33** | 0 |
| `c_via` (stage A intermediate) | 0 | 0 | **23** | 0 |
| **composed = published artefact** | **0** | **0** | **23** | **0** |

The gate is the one custom rule of `fab-da-vias/no_hdi.kicad_dru:13-16`
(`hole_size (min 0.2mm)`, `condition "A.Type == 'Via'"`) staged as `<board>.kicad_dru` beside a copy
of the board. It is **1 rule**, and on the baseline it returns exactly **33** — the 33 microvias, no
false positives — so the count is reproducible by a third party with one command.

The composed board's 23 gate violations are all the same type, `microvia_drill_out_of_range`: the 23
microvias that the via fix could not convert. **It is not a new violation class**: the same 23 exist
in `fixed.kicad_pcb`, and the void reroute adds none (v_r3 alone is 33 → composition takes it to 23,
exactly the via fix's remainder).

### 3.2 Unconnected = 0, by two independent checks

* `kicad-cli pcb drc` → `unconnected_items` = **0** on the composed board (all 23 gate violations are
  drill, not connectivity).
* `pcbnew` → `GetConnectivity().GetUnconnectedCount(False)` = **0** after `BuildConnectivity()` on
  the saved, refilled file.
* Stage B also measured `unconnected` = 0 **before** the refill (`stage_B.json`), so the connectivity
  does not depend on the pour closing a gap.

### 3.3 Minimum drill and via census (`s01_census.py`, `census.json`)

| | base | composed |
|---|---|---|
| vias | 341 | **338** |
| drill histogram | 0.100 × 33, 0.300 × 27, 0.350 × 281 | **0.100 × 23, 0.300 × 34, 0.350 × 281** |
| via types | through 305, microvia 33, blind 3 | **through 314, microvia 23, blind 1** |
| **MIN_DRILL** | 0.100 mm | **0.100 mm — unchanged** |
| non-through | 36 | **24** |

No new drill diameter was introduced (still 0.100 / 0.300 / 0.350). The 9 added vias are 0.300 /
0.600 mm, the dominant existing pair (0.350 / 0.700 elsewhere is a *different* drill; the 0.300 row
grows by exactly 7 = 9 added − 2 blind 0.300 deleted).

**Drill receipt** (`drill/`, `kicad-cli pcb export drill --excellon-separate-th`): the composed board
still needs **5 plating classes** —

| program | layer pair | holes | drill |
|---|---|---|---|
| `-PTH.drl` | 1–4 through | 336 | 0.200 / 0.300 / 0.350 / 0.600 |
| `-front-in1.drl` | 1–2 blind | 11 | **0.100** |
| `-front-in2.drl` | 1–3 blind | 2 | **0.100** |
| `-in1-back.drl` | 2–4 blind | 3 | **0.100** |
| `-in1-in2.drl` | 2–3 **buried** | 5 | **0.100** |
| `-in2-back.drl` | 3–4 blind | 3 | **0.100** ×2, 0.300 ×1 |
| `-NPTH.drl` | — | 6 | 0.650 / 4.300 |

**23 holes at 0.100 mm across five layer pairs.** That is a sequential-laminate (HDI) drill set, so
the board is **not** fabricable at a standard 4-layer PTH house. Composition does not fix that, and
nothing in this item claims it does.

### 3.4 Void — the actual filled-zone measure, not an estimate

`20_measure.py`'s definition (wave-2's) is reproduced exactly here: In1 copper = **stored filled zone
polygons** + In1 tracks + In1 pads, subtracted from each `RF_50R` F.Cu track footprint. `void_B` adds
through-via In1 annuli, which are copper under the trace by any physical reading.

| | RF footprint | void_A | **void_A %** | void_B | **void_B %** |
|---|---|---|---|---|---|
| base | 42.4040 mm² | 4.1699 mm² | **9.8338** | 3.8754 mm² | 9.1392 |
| viafix (artefact 1) | 42.4040 | 4.1699 | **9.8338** | 3.8754 | 9.1392 |
| v_r3 (artefact 2) | 42.4040 | 0.5495 | **1.2959** | 0.2550 | 0.6013 |
| c_via (stage A) | 42.4040 | 4.1699 | **9.8338** | 3.8754 | 9.1392 |
| **composed** | 42.4040 | **0.5495** | **1.2959** | **0.2550** | **0.6013** |

The baseline reproduces wave-2's **9.834 %** to 0.0002 mm² and v_r3's **1.296 % / 0.601 %** to 4
decimals, so the composition is measured on the same basis as both predecessors, and the RF corridor
is over solid In1 copper for **99.3987 %** of its area (was 90.86 %).

Zone fill is real, not stale: 2/2 In1 zones report `HasFilledPolysForLayer`, and the In1 `/3V3` fill
moves **12164.050 → 12588.955 mm²** (`s01_census.py` per-zone probe; base's 12164.050 reproduces
`fab-da-voidfill/REPORT.md:80` exactly).

---

## 4. Did applying both introduce a new conflict?

**DRC and connectivity: no.** 0 / 0 under the board's own rules, 0 unconnected, no new violation
type, no object modified.

**Two side-effects are real and are reported rather than blended away:**

1. **The via fix eats 2.516 mm² of the copper the void fix restores.** In1 `/3V3` fill:
   base 12164.050 → **stage A alone 12160.740** (−3.310: the antipads) → void fix alone 12591.471
   (`fab-da-voidfill/REPORT.md:80`) → **composed 12588.955**. Turning a F.Cu→In1 microvia into a
   through via punches an **In1 antipad that did not exist before**, so the reference pour loses
   ≈0.28 mm² per converted via (9 × 0.28 ≈ 2.5 ✓), and the void fix then restores 428.215 mm² on top
   of the reduced base. This is the expected physics of the conversion, and it is why the order
   matters for measurement: convert → refill → then measure.
2. **An independent 82.183 mm² In1 `/GND` sliver halves to 38.441 mm².** It is a separate zone from
   the `/3V3` reference pour and sits outside the RF corridor. Attribution is measured: base = stage
   A = **82.183**, composed = **38.441**, so it is stage B. The void_A figure is unchanged to 4
   decimal places and DRC reports 0 unconnected, so no island was orphaned — but the mechanism is
   flagged as an open observation, not explained away.

**Both effects are outside the RF footprint**: composed void_A and void_B are **identical**
(0.5495 / 0.2550 mm²) to the void-fixed board. Composition therefore buys the via fix at **zero cost
to the metric the void fix exists for.**

---

## 5. Constraint compliance

| constraint (`AGENT_BOARD.md:518-534`) | state |
|---|---|
| no HDI / no laser vias / no blind-buried process | **NOT met, unchanged.** 23 microvias + 1 blind remain. Composition reduced the gate count 33 → 23; it does not close it |
| standard PTH only | the 9 added vias **are** standard 0.300/0.600 PTH, and 2 blind 0.300 vias were removed (3 → 1) |
| 4-layer, 1 oz (0.035 mm) | unchanged: `main_rev_b.kicad_pcb:50-85`, every copper layer `(thickness 0.035)`. A 0.25 mm track moved In1 → B.Cu is same-weight copper, not a current change |
| $60 spend cap | **$0 spent.** No fab asked, no coupon ordered. (Deliberately not re-litigating the 4 oz floor that this wave's other unit owns.) |
| repo untouched | base read from byte copies; **0** writes outside `evidence/fab-da-consolidate/` |

---

## 6. What REMAINS

### 6.1 The 24 vias, measured on the composed board

`s05_remain.py` reads the composed board's **own** vias (not a list carried over), clusters them by
XY, and joins each cluster to the per-layer relief measurement in `fab-da-vias/relief.json`.
`remain_table.md` is the full 20-row table.

**24 non-through vias in 20 groups, 13 nets: 23 microvias at 0.100 mm + 1 blind at 0.300 mm.**
**All 20 groups need a fan-out re-escape.** Not one of them can be fixed by a via edit, because a
standard through via needs **0.425 mm** (0.300 pad radius + 0.125 clearance) on **all four layers**
and no group has that:

| relief group | net | vias | drill | worst-layer dist | centre inside foreign Cu | short by | binding item |
|---|---|---|---|---|---|---|---|
| G05 | /LSM_INT1 | 1 | 0.100 | −0.225 | **YES** | 0.650 | pad FB1.2 /3V3_ADC |
| G18 | /3V3 | 1 | 0.100 | −0.125 | **YES** | 0.550 | trk /LNA_EN w0.25 |
| G04 | /LSM_INT1 | 2 | 0.100 | −0.089 | **YES** | 0.514 | trk /ICM_nCS w0.25 |
| G16 | /RF_GPIO2 | 1 | 0.100 | −0.086 | **YES** | 0.511 | trk /SENS_SCLK w0.20 |
| G07 | /PA_EN | 1 | **0.300 (blind)** | −0.075 | **YES** | 0.500 | trk /RP2354B MCU/XIN w0.25 |
| G17 | /RF_GPIO0 | 1 | 0.100 | −0.025 | **YES** | 0.450 | trk /SENS_MOSI w0.25 |
| G19 | /RF_GPIO0 | 1 | 0.100 | −0.025 | **YES** | 0.450 | trk /1V1 w0.25 |
| G21 | /RF_MOSI | 1 | 0.100 | −0.025 | **YES** | 0.450 | trk /915 MHz RF/VDD_CC112 w0.25 |
| G09 | /PA_EN | 1 | 0.100 | 0.000 | **YES** | 0.425 | trk /RF_GPIO2 w0.20 |
| G06 | /GNSS_RX | 1 | 0.100 | 0.099 | no | 0.326 | trk USB_DM_MCU w0.25 |
| G12 | /GNSS_RX | 1 | 0.100 | 0.143 | no | 0.282 | pad C12.2 /GND |
| G14 | /RF_RESET_N | 1 | 0.100 | 0.193 | no | 0.232 | trk /RF_SCLK w0.25 |
| G15 | /HGM | 1 | 0.100 | 0.250 | no | 0.175 | trk /RF_MISO w0.20 |
| G11 | /RF_MISO | 2 | 0.100 | 0.275 | no | 0.150 | trk /RF_nCS w0.25 |
| G03 | USB_DP_MCU | 2 | 0.100 | 0.275 | no | 0.150 | trk /3V3 w0.25 |
| G24 | /RF_GPIO2 | 1 | 0.100 | 0.292 | no | 0.133 | trk /RF_MOSI w0.20 |
| G10 | /RF_MOSI | 2 | 0.100 | 0.300 | no | 0.125 | trk /RF_MISO w0.20 |
| G13 | /SENS_SCLK | 1 | 0.100 | 0.305 | no | 0.120 | via /RF_GPIO0 350 µm |
| G26 | VDD_CC112 | 1 | 0.100 | 0.307 | no | 0.118 | trk CC_PA w0.35 |
| G25 | /RF_MOSI | 1 | 0.100 | 0.337 | no | 0.088 | trk /RF_MISO w0.20 |

Four of the twenty are stacked pairs at one XY (G03, G04, G10, G11 → 8 vias), so 24 vias occupy 20
positions; 19 groups are below 0.2 mm drill and **1 group (G07 `/PA_EN`) is a legal 0.300 mm drill on
a forbidden process** (In2 → B.Cu blind).

**The size of the job, unchanged by this item:** of the 20 groups, **11 are freed by moving only other
nets' tracks** and **9 also need a component pad (U10 perimeter pads, C12.2, FB1.2) or another through
via to move** (`fab-da-vias/REPORT.md:195-197`). Freeing them means re-escaping the U10 (0.400 mm
pitch, 0.200 mm copper gap) and U40 (0.500 / 0.250) fan-outs — a routing pass at a trace/space width
the board's current `min_track_width 0.2 / min_clearance 0.125` cannot express (0.200 mm of gap
cannot hold a 0.2 mm trace: needs 0.45 mm). That is a **rule and package decision above this item's
remit**, and it is the only route to zero.

### 6.2 One number in the brief does not reproduce

The brief (and `AGENT_BOARD.md:465`) says **"13 of those have the via centre inside another net's
copper (dist ≤ 0)"**. Measured from `fab-da-vias/relief.json` — the only per-layer distance
measurement that exists:

* groups whose **minimum distance over all four layers ≤ 0**: **9**
* layer rows at dist ≤ 0: **10**
* groups at min distance ≤ **0.250 mm**: **13**

So **13 is the count at a 0.250 mm threshold, not at ≤ 0**. The substantive conclusion is unaffected
— all 20 groups fail the 0.425 mm requirement by 0.088–0.650 mm — but the number attached to
"dist ≤ 0" should be **9**. Flagged rather than repeated.

---

## 7. NOT verified, and what would settle it

* **No fab was asked**, here or for the via floor. Whether a house will run 0.100 mm drills at all is
  untouched; whether it would run the 0.300/0.600 PTH at 1 oz is not quoted (UNVERIFIED).
* **No EM re-simulation.** The RF statement is geometric — 1.2959 % void, 99.3987 % of the corridor
  over solid In1 — plus the existing Tier-B anchors (52.61 Ω solid / 118.12 Ω voided, unchanged and
  not re-derived). **S11 was not re-run.**
* **The 0.25 mm VDD_CC112 run now sits on B.Cu**, 1.510 mm from F.Cu, shielding not analysed.
* **The In1 `/GND` sliver halving** (§4.2) is measured, not explained.
* **No netlist/schematic parity check** — no net was added, removed or renamed; `board_diff.json`
  reports `modified 0`, so parity should be untouched, but it was not run.
* **The re-escape itself does not exist.** This item sizes and locates it (20 groups, 24 vias, 13
  nets, shortfalls 0.088–0.650 mm); it does not author it.

---

## 8. Artefacts and reproduction

| file | what |
|---|---|
| **`da_main_rev_b_composed.kicad_pcb`** (+ `.kicad_pro`) | **the deliverable** — via-fixed + void-fixed, refilled, DRC 0/0, 0 unconnected. sha256 `5DBAE238…F73B6` |
| `compose_manifest.json` | every edit, counted, both stages, with the ordering rationale |
| `stage_A.json`, `stage_B.json` | per-stage receipts (counts, zone before/after, pre-refill unconnected) |
| `board_diff.json` | **independent** UUID diff base → composed: 18 removed (12 via, 6 track), 37 added, 5 layer-move pairs at identical XY, 1 zone param change, 0 modified |
| `census.json` | per-board via census, drill histogram, min drill, unconnected, pour areas, void_A/void_B |
| `drc/summary.json` + `drc/drc_{own,gate}_*.json` | DRC under both rule sets, six boards |
| `drill/` | the composed board's 7 Excellon programs — the min-drill receipt |
| `remain.json`, `remain_table.md` | the 20 groups / 24 vias that remain, with per-layer binding item and shortfall |
| `s01_census.py` … `s06_diff.py` | the pipeline, in order |
| `work/` | intermediate boards (`c_via`, stage-B copy), staged DRC copies, reproduced package drills |

```
"C:/Program Files/KiCad/9.0/bin/python.exe" s02_compose.py A     # base  -> work/c_via.kicad_pcb
"C:/Program Files/KiCad/9.0/bin/python.exe" s03_refill.py work/c_via.kicad_pcb
"C:/Program Files/KiCad/9.0/bin/python.exe" s02_compose.py B     # c_via -> work/composed.kicad_pcb
"C:/Program Files/KiCad/9.0/bin/python.exe" s03_refill.py work/composed.kicad_pcb
"C:/Program Files/KiCad/9.0/bin/python.exe" s02_compose.py merge
"C:/Program Files/KiCad/9.0/bin/python.exe" s06_diff.py          # independent UUID diff
"C:/Program Files/KiCad/9.0/bin/python.exe" s01_census.py 'FINAL=da_main_rev_b_composed.kicad_pcb'
"C:/Program Files/KiCad/9.0/bin/python.exe" s04_drc.py       'FINAL=da_main_rev_b_composed.kicad_pcb'
"C:/Program Files/KiCad/9.0/bin/python.exe" s05_remain.py
"C:/Program Files/KiCad/9.0/bin/kicad-cli.exe" pcb export drill --format excellon \
    --excellon-separate-th --output drill/ da_main_rev_b_composed.kicad_pcb
```

One caveat for a re-runner: **the void measurement needs the matching `.kicad_pro` beside the board.**
Netclass names (`RF_50R`) live in the project file, so a bare `.kicad_pcb` copied into a directory
without its `.kicad_pro` measures **0 mm² of RF footprint** and would look like a perfect result. This
bit me on the package board (`work/pkg/` is staged with the project file for exactly that reason).

*Maintained by `fab-da-consolidate`. Written only inside `evidence/fab-da-consolidate/`; no repo
file, no commit, no push, no `audit/*` branch touched.*