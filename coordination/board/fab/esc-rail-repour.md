# ESC rev_b — the BATP/BATN re-pour: executed, measured, and DRC-diffed

**Unit:** `esc-rail-repour` · **Wave 10** · Assignment: execute the rail re-pour that takes the
4 oz ESC from **23.1 A** to the capability the settled decision claims (**47.1 A**), and prove it
with the validated instrument rather than with arithmetic.

**Host:** KiCad 9.0.7 (`kicad-cli` 9.0.7 for DRC, `pcbnew` 9.0.7 / Python 3.11 for board edits,
shapely 2.2.0 / scipy 1.17.1), CPython 3.12.2 for the analysis and the IPC-2221 arithmetic.

**Write scope respected:** nothing was written into a repo, no commit, no push, no `audit/*`
branch. The board of record was **read once and copied**; every artefact below is inside this
directory. `esc_base.kicad_pcb` is byte-identical to
`repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb` (sha256
`992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD`).

| artefact | what it is |
|---|---|
| `esc_repour_v4.kicad_pcb` **32E15DA8…26481**, 5,132,919 B | **the deliverable board**: re-poured, refilled |
| `esc_base.kicad_pcb` **992570571DEB…95DDD** | the board of record, copied |
| `esc_control_refill.kicad_pcb` **992570571DEB…95DDD** | control: loaded + refilled + saved, **no edit — byte-identical to the base** |
| `esc_attr_solid.kicad_pcb` **8FF829C5…52361** | attribution board: the pad property only, no new copper |
| `esc_repour_v2 / v3` | superseded attempts (v2 = one zone per net, v3 = per-pad zones) |
| `railmc.py`, `06_validate.py`, `07_measure.py`, `04_extract.py` | the instrument, **its 19 controls re-run here → PASS** (`01_validate.log`) |
| `07_repour.py` (v1), `08_repour.py` (v2/v3/v4), `18_refill_only.py`, `20_invariants.py`, `21_unconnected_diff.py` | the edits and the invariant checks |
| `13_drcdiff.py`, `19_sitediff.py`, `22_numbers.py` | DRC pair diff, DRC **site** diff, every number quoted |
| `drc_base/`, `drc_ctl/`, `drc_v4/` | three `kicad-cli pcb drc` JSON reports at the 4 oz 0.25 mm rule set |

---

## 0. The answer

| question | answer |
|---|---|
| as-drawn capability reproduced? | **YES** (to 0.07 %): BATP **0.5242 mm² = 23.08 A** (published 23.1), BATN **1.4139 mm² = 47.40 A** (published 47.4) |
| required at 43.5 A / ΔT 20 K (IPC-2221) | **1.2561 mm²** = **8.972 mm of 4 oz outer**, or **62.244 mm of 1.5 oz inner**, or **40 barrels** of 0.4 mm / 25 µm |
| the target 47.1 A | **1.4017 mm²** = **10.012 mm of 4 oz** = **45 barrels** |
| what was executed | **24 land-extension zones** (per-pad, self-clearing) + **186 terminal pads → SOLID** + **240 through vias 0.80/0.40** (24 BATP + 16 BATN **per cell**, all six cells), refilled |
| BATP before → after | **0.5242 → 1.5082 mm²** = **23.08 → 49.67 A** (×1.142 of 43.5, ×1.054 of 47.1) |
| BATN before → after | **1.4139 → 1.9166 mm²** = **47.40 → 59.09 A** (×1.358 of 43.5, ×1.255 of 47.1) |
| pre-shunt element `M1_BATP_IN` | **1.4280 mm² = 47.74 A — unchanged to the digit** |
| DRC at 4 oz 0.25 mm rules | **523 → 524**. Pair diff **5 added / 4 gone**; **site diff: 0 new sites**, the 5th is a second marker at a pre-existing 0.2478 mm site. **0 added markers involve added copper** (no Via, no battery net, no Zone item) |
| unconnected (pcbnew) | **1,542 → 1,536** — it **changed** by **−6**; the pad property alone leaves it at 1,542 |
| components on B.Cu | **0 → 0** (687/687 on F.Cu on both boards) |
| vias | 1,990 → **2,230** (+240), **0 non-through**, all F.Cu→B.Cu |
| **is 43.5 A met?** | **YES.** Chain: `BATP_IN` **47.74 A**, `BATP` **49.67 A**, `BATN` **59.09 A** → the rails are no longer the binding element; capability becomes the phase corridor **47.1 A**, i.e. **1.08× of 43.5 A** — the settled figure, now **supported** by a rail measurement that clears it (the corridor itself is inherited, not re-measured) |

---

## 1. The instrument, re-validated before any number was believed

`railmc.py` (min s-t cut of the copper graph, capacities in copper cross-section) is the same file
`evidence/esc-battery-rail/` validated. **The brief points at `evidence/esc-corridor-instrument/
(railmc.py, 19 controls, PASS)`; that directory contains `corridor_lib.py`, not `railmc.py`.** The
19-control `railmc.py` lives in `evidence/esc-battery-rail/`, so it was copied here and its controls
were **re-run in this unit** rather than cited:

```
01_validate.log  -> 19 controls, VERDICT: PASS
  strips 0.25/1/3/6/12/20 mm exact; notch 1.2 and 0.5 mm exact; L-channel 2.5 mm exact;
  pour with a 2.5 mm neck 2.5 exact; 2 mm hole in a 6 mm strip -> 4.0; edge notch -> 4.8;
  grid independence h = 0.2 / 0.1 / 0.05 / 0.025 all 3.000; parallel layers add (0.3848 vs 0.3850);
  series through 2 barrels = exactly one barrel section (0.03142); 4 x 0.5 mm thermal spokes -> 1.92
```

`22_numbers.py` then refuses to print the table unless the same closed form reproduces **five
already-published figures** — it does, to ≤0.07 % (`22_numbers.log`): 60 A/20 K width 13.981 mm,
0.0525 mm width 96.991 mm, 45 barrels 47.39 A, BATP 0.5242 → 23.08 A, BATN 1.4139 → 47.40 A,
1.5082 → 49.67 A, one barrel 0.03142 mm².

**As-drawn reproduction, row level** (`03_measure_base.json`, grid h = 0.10 mm):

| net | cut | composition | ampacity |
|---|---|---|---|
| `/M1_BATP` | **0.5242 mm²** | **F.Cu 0.21 mm²** (a 1.5 mm neck at x = 34.15–34.45, y = 101.8 and 107.7) **+ 10 barrels 0.3142 mm²** | **23.08 A** |
| `/M1_BATN` | **1.4139 mm²** | **100 % barrels — 45 of them** (15 per leg-shunt island) | **47.40 A** |
| `/M1_BATP_IN` | **1.4280 mm²** | F.Cu 10.20 mm wide, no barrels | 47.74 A |

So **YES**, both figures reproduce (0.067 % and 0.009 % — inside the instrument's own 0.07 % control tolerance) and the earlier diagnosis is confirmed at row level:
BATP fails because its 4 oz F.Cu is **two disjoint pours** joined only through the 1.5 oz inner
plane, and the shunt pad's exit is a **thermal-spoke neck**; BATN fails on **barrels**, not plane.

---

## 2. The design

### 2.1 What IPC-2221 asks for at 43.5 A, ΔT 20 K (`22_numbers.py`, controls passed)

| basis | cross-section | width |
|---|---|---|
| **4 oz outer**, k = 0.048 | **1.2561 mm²** | **8.972 mm** |
| 2 oz outer, k = 0.048 | 1.2561 mm² | 17.945 mm |
| **1.5 oz inner**, k = 0.024 | **3.2678 mm²** | **62.244 mm** |
| at the 47.1 A target, 4 oz | **1.4017 mm²** | **10.012 mm** |

Barrels: one 0.4 mm barrel with 25 µm plating = **0.03142 mm²**, so **43.5 A needs 40 barrels**
(integer) and **47.1 A needs 45**. At 38 µm plating 43.5 A needs **26.3**.

### 2.2 Which option, and why not the strap

Three options were on the table. **The strap was measured out, not argued out.** The assignment's
option "pour F.Cu into a continuous strap" needs **8.972 mm of clear 4 oz corridor**; the widest
completely-clear F.Cu channel between the shunt land and the FET drains is **2.75 mm** on this
placement (**3.25 mm** on the power-first placement) — inherited from
`esc-battery-rail/14_freewidth.py`, and consistent with this unit's own copper map (`05_localmap_*`):
the shunt land is ringed by foreign pads and tracks on every side. A strap of the required width
does not exist on this placement; fitting one is a re-placement, not a re-pour.

"Parallel In2" was also refused on a measured fact: In2 carries **14,928.13 mm² of the 18 phase
pours** (`esc-flip-current` §2), so a BATP plane on In2 would have to displace phase copper.

What is left is the cheapest real lever, and it is the one that the instrument shows is binding:
**more barrels where the current dives into the plane, plus the pad-property change that stops the
spoke from throttling them.** Layer assignment of the finished rail:

* **BATP**: 4 oz **F.Cu** land (zone-extended) → **48 through barrels** → 1.5 oz **In1** plane →
  4 oz **F.Cu** drain strip. The cut is now **48 × 0.03142 = 1.5082 mm²**, 100 % barrels.
* **BATN**: 4 oz **F.Cu** land (zone-extended, 3 pads per cell) → **61 barrels** → 4 oz **B.Cu**
  plane. Cut **1.9166 mm²**, 100 % barrels.
* **In2 / B.Cu do not carry BATP** at all — as before, and now measured again: BATP still has
  0 zones on In2 and B.Cu.

### 2.3 The three mechanisms, each safe by construction

1. **Pad property, not geometry.** The shunt output pads and the high-side drain pads
   (186 pads = 6 cells × (28 BATP + 3 BATN)) get zone connection **SOLID**. The gap comes from the
   zone, not the pad, so no clearance can be created by it. Measured effect alone: **0.5242 →
   1.3196 mm² (42 barrels) = 45.08 A** — it clears 43.5 A at **1.036×**, but it is only **0.96× of
   the 47.1 A target**, so on its own it does not get the board where the decision needs it.
2. **Land extension as ZONES.** 24 same-net F.Cu zones (4 per cell: one around `R1<n>23`, one
   around each of `R1<n>20/21/22`), each `pad bbox + 1.6 mm`, priority 1, clearance 0.50,
   min thickness 0.25, island removal ALWAYS. KiCad's filler opens its own clearance, so the change
   **cannot** create the clearance/zone collisions a hard-coded strip did (the earlier executed fix
   produced **+12 clearance and +6 zones_intersect** that way). Setting priority 1 is what removed
   the **6 zones_intersect** this unit's own first per-pad attempt produced (`13_drc_diff.log`,
   v3 run).
3. **Barrels placed by explicit geometry, not by eye.** 240 × through via **0.80 / 0.40 mm**
   (ring 0.20 ≥ 0.20, drill 0.40 ≥ 0.30, dia 0.80 ≥ 0.70 — all three 4 oz rules cleared). Candidate
   points on a 0.25 mm grid inside the net's own F.Cu fill, accepted only if
   **≥ 0.75 mm from foreign copper** (0.35 radius + 0.25 rule + 0.15 margin), **≥ 0.70 mm from every
   existing hole of any net**, **≥ 0.65 mm from own SMD pads** (no via-in-pad; that needs a filled
   process), **≥ 0.90 mm from the board edge**, and **≥ 1.20 mm apart**. Zone fills are *not*
   treated as fixed: they are refilled, so a foreign plane opens its own antipad.

---

## 3. What was executed

`08_repour.py` → `esc_repour_v4.kicad_pcb` (`14_execute_v4.log`, plan in `14_execute_v4.json`):

| edit | count | detail |
|---|---|---|
| land-extension zones | **24** | 4 per cell, per shunt pad, `pad bbox + 1.6 mm`, F.Cu, priority 1 |
| pads → SOLID | **186** | 6 × 28 BATP (shunt out + 25 drain pads of `Q1<n>01/03/05` pin 9) + 6 × 3 BATN |
| through vias 0.80/0.40 | **240** | 6 × (24 BATP at `R1<n>23` + 16 BATN across `R1<n>20/21/22`) |
| barrels per cell | 24 BATP / 16 BATN | the BATP figure is the **land limit**, not a chosen cap: after the fill only **13.79 mm²** of the 98.19 mm² host was more than 0.75 mm from foreign copper and 0.70 mm from an existing hole; BATN had 43.15 mm² free and was budget-capped |
| refill | all zones | then saved |

All six cells received the identical edit; the instrument measures cell 1 because its terminal
definition is per-cell (`07_measure.py TERM`), and the six cells are geometrically identical
(`14_execute_v4.json` shows the same host/free areas to 0.03 mm²).

**Superseded, and recorded rather than deleted:** v1 (`07_repour.py`) matched refdes `R<n>123`,
which exists only for cell 1 — the board nets are `R1<n>23` — so it edited one cell and put its
barrels in the FET strip rather than at the binding cut (`08_execute_v1.log`). v2 built **one zone
per net**, whose bbox spanned 45 mm and cut 45 mm² out of the neighbouring `M1_BATP_IN` pour; the
per-pad zones of v3/v4 removed that. v3 was correct in copper but left **6 `zones_intersect`**
(equal priority with the existing BATP pour); **v4 sets priority 1 and is the deliverable.**

---

## 4. Verification — the same instrument, both boards

`11_geom_v3`/`15_geom_v4` → `16_measure_v4.json` (h = 0.10 mm, identical terminal definition):

| net | before | after | Δ | barrels in the cut |
|---|---|---|---|---|
| `/M1_BATP` | 0.5242 mm² = **23.08 A** | **1.5082 mm² = 49.67 A** | **+0.9840 mm² (+188 %), +26.6 A** | 10 → **48** |
| `/M1_BATN` | 1.4139 mm² = **47.40 A** | **1.9166 mm² = 59.09 A** | **+0.5027 mm² (+36 %), +11.7 A** | 45 → **61** |
| `/Motor 1 power cell/M1_BATP_IN` | 1.4280 mm² = 47.74 A | **1.4280 mm² = 47.74 A** | 0.0000 | 0 |

Two checks that the after-numbers describe the board and not the script:

* the cut is **100 % barrels** on both rails (`per_layer_mm2` all 0.0), i.e. the value is
  `n_barrels × 0.03142` exactly: 48 × 0.03142 = 1.5082, 61 × 0.03142 = 1.9166, and the JSON reports
  48 and 61 cut edges;
* `16_measure_v4.json` was produced from `15_geom_v4.json`, extracted from
  `esc_repour_v4.kicad_pcb`, whose via census is **2,230** (`20_invariants.json`) — not from a
  neighbouring unit's board. v3 and v4 measure **identically**, which is expected: they carry the
  same 240 barrels and the cut is barrel-only.

**The attribution chain, measured, not asserted:** 0.5242 (as drawn) → **1.3196 mm² = 45.08 A**
(SOLID pads only, no new copper) → **1.5082 mm² = 49.67 A** (+ the zones and 240 barrels). So the
pad property alone buys **+22.0 A** and reaches 1.036× of 43.5 A but only 0.96× of the 47.1 A
target; the barrels are what turn 1.036× into 1.142×. BATN's attribution is flat — **1.4139 → 1.4139 mm² (47.40 A)** — which is the
control that says BATN was already 100 % barrel-limited and the pad property could not have helped it.

---

## 5. DRC at the 4 oz 0.25 mm rules — set diff, added and gone

Rule sheet: `fab-esc-rules-first/variant-025/esc_rev_b.kicad_dru` (**9 rules, `(version 1)`
present** — the missing-version trap that silently disables a `.kicad_dru` is not in play), installed
next to each board under the same basename, with the board's own `.kicad_pro`
(`min_clearance 0.2`, `min_via_annular_width 0.1`, …). `kicad-cli pcb drc --format json
--severity-all --units mm`.

**Instrument control first.** A copy of the board of record, loaded + refilled + saved with **no
edit**, is **byte-identical** to the original (sha256 `992570571DEB…95DDD`) and gives **523
violations, 0 added / 0 gone** against it (`drc_ctl`, `13_drcdiff.log`). A third, independent run of
the same board in `esc-area-honest/drc/orig_025` also differs by **0 added / 0 gone**. So this DRC
is stable run to run and the diff below is not scatter.

**Result: 523 → 524.**

| type | base | v4 | gone | added |
|---|---|---|---|---|
| `clearance` | 414 | 415 | 4 | 5 |
| `annular_width` | 70 | 70 | 0 | 0 |
| `via_diameter` | 16 | 16 | 0 | 0 |
| `via_dangling` | 16 | 16 | 0 | 0 |
| `track_width` | 4 | 4 | 0 | 0 |
| `connection_width` | 3 | 3 | 0 | 0 |
| `zones_intersect` | 0 | 0 | 0 | 0 |
| **total** | **523** | **524** | **4** | **5** |

**Which items.** All nine are `clearance` items on the gate-driver bus and one 3V3 stub — **none is
a Via, none is a battery net, none is a Zone**: `DRV_SDI ↔ DRV_SDO / NTC` at `U1<n>02` for cells 1/2/3/5,
`DRV_SCLK ↔ DRV_SDI` for cells 1/3, and the 0.400 mm `3V3` stub at `U201` pad 67/70.

**Site diff (`19_sitediff.py`, key = type + site + the `actual` gap printed in the description).**
Four of the five "added" markers are the **same physical site** as a "gone" one, with KiCad naming the
other of two neighbouring pads at the same gap — e.g. base names `Pad 14 (DRV_SDO)` and v4 names
`Pad 16 (NTC)` for the same `M1_DRV_SDI` track at the same **actual 0.225 mm**. The fifth is a
**second marker at a site base already flags**: `M1_DRV_SCLK` × `M1_DRV_SDI` at **actual 0.2478 mm**,
where base reports that site against the 4.2426 mm segment and v4 against the 21.0000 mm segment as
well. **Both segments belong to the same net pair at the same measured 0.2478 mm gap, so no new
defect exists — one site, one gap, two named pairings.**

**So: 0 violations involve any copper the re-pour added; 0 new violation sites; +1 marker by
item-pair re-selection at a pre-existing site.** The 240 new barrels added **zero**
`via_diameter`, `annular_width` and `via_dangling` items — the geometric pre-check is doing the work,
not luck. And the +6 `zones_intersect` that the first per-pad attempt produced is **gone** in v4.

**Unconnected**: `kicad-cli` reports **499 on both** — that is the cap, identical in every run of
every unit, and is quoted here only as a cap.

---

## 6. The invariants

`20_invariants.json` (pcbnew):

| | base | v4 |
|---|---|---|
| unconnected (`GetUnconnectedCount(False)`) | **1,542** | **1,536** |
| footprints | 687 | 687 |
| footprints on **F.Cu** | **687** | **687** |
| footprints on **B.Cu** | **0** | **0** |
| pads existing only on B.Cu (pre-existing THT) | 2 | 2 |
| vias | 1,990 | **2,230** |
| vias non-through (by span) | **0** | **0** |
| via sizes | 1,962 × 0.8/0.4 · 16 × 0.6/0.3 · 12 × 0.7/0.35 | **2,202 × 0.8/0.4** · same two others |

**Unconnected DID change: 1,542 → 1,536 (−6).** It is reported as a change, not as "unchanged",
because the brief expected 1,542. Direction: **six connections closed**. Attribution: the
**pad-SOLID-only board is still 1,542** (`esc_attr_solid`), so the six closures come from the added
land + barrels, not from the pad property. The per-edge identity could **not** be extracted:
`CONNECTIVITY_DATA.RunOnUnconnectedEdges` in this pcbnew build rejects a Python callable
(`21_unconnected.log`, "0 edges reported"), so `21_unconnected_diff.json` is an empty result and is
kept as the record of a failed probe rather than a measurement.

No component moved: **687 footprints, 687 on F.Cu, 0 on B.Cu, before and after**. Single-sided is
preserved by construction — the script adds no footprint and moves none.

---

## 7. Verdict

> **The re-pour is executed and it works.** Measured with the instrument that reproduces the
> as-drawn 23.1 A and 47.4 A to 0.07 %: **BATP 23.08 → 49.67 A**, **BATN 47.40 → 59.09 A**, the
> pre-shunt element unchanged at **47.74 A**.
>
> **43.5 A is met with the rail as the non-binding element.** The binding element of the board is
> now the **phase corridor 47.1 A** (measured in `esc-flip-current`, **not** re-measured here), so the
> board capability is **47.1 A = 1.08× of 43.5 A** — which is the settled claim, now
> supported at the rails: they are no longer the binding element, and the element that binds is
> the corner the settled decision already named. The rails clear the design current by **1.142×** (BATP) and
> **1.358×** (BATN); the tightest element in the battery chain is `M1_BATP_IN` at **47.74 A
> (1.097×)**, and it is the next thing that binds.
>
> DRC: 523 → 524, **0 added violations of any kind on added copper, 0 new violation sites**.
> Unconnected **improves** by 6. Nothing moved to B.Cu.

---

## 8. Assumptions, sensitivities and what this does NOT cover

| # | input | value | if wrong |
|---|---|---|---|
| A1 | allowed copper rise ΔT | **20 K** (the repo states none) | at 30 K the 43.5 A requirement falls to 0.9821 mm² = 7.015 mm / 31.3 barrels; both rails already clear it |
| A2 | barrel plating wall | **25 µm** | at 38 µm a barrel carries 1.520× the area = 1.355× the current, 43.5 A needs 26.3 barrels and 47.1 A needs 29.4, so both rails gain ~35 % |
| A3 | inner-layer k | **0.024** for the In1 plane row only | the measured cuts are on barrels (k = 0.048) so the verdict does not ride on it |
| A4 | terminal definition | by refdes and pad geometry, per cell | a refdes-only match silently skips five cells — that bug was hit in v1 and is why v1 is recorded as superseded |
| A5 | 4 oz rules are extrapolated | 0.250 mm at 140 µm copper | EP class table stops at 105 µm / 3 oz; 0.25 mm is the last published step, so the rules are a floor, not a measured 4 oz capability |

**What this does NOT cover.**
* **Not a thermal solve.** The heat spreader is still MANDATORY and still outside the outline
  (352–528 cm², settled); the 240 barrels add copper but remove no heat.
* **Only cell 1 is measured.** Cells 2–6 received the identical edit (same host areas to 0.03 mm²)
  but were not measured; a per-cell measurement is 6 × the runtime of this unit.
* **The phase corridor is inherited, not re-measured** (`esc-flip-current` §2/§3). If it is wrong,
  the board capability moves but the rails' 1.142× / 1.358× do not.
* **The BATP land is exhausted.** 13.79 mm² of free area remained after the fill and the 24 barrels
  use it. Going past 48 barrels in the cut needs a bigger land, i.e. a re-placement — the same wall
  the earlier fix hit, but now the wall is at **49.67 A** instead of 23.1 A.
* **No barrel-count headroom was bought by shrinking the edge or hole clearances**; the two
  constants that decide the count are stated in §2.3 as margins over the rule values.

---

## 9. Reproduce

```powershell
$kpy = "C:\Program Files\KiCad\9.0\bin\python.exe"
$py  = "C:\Program Files\Python312\python.exe"
$cli = "C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"
$ev  = "E:\engineering-portfolio-audit\evidence\esc-rail-repour"; cd $ev

& $py  06_validate.py                      # 19 controls -> PASS            (01_validate.log)
$env:BOARD="esc_base.kicad_pcb"; $env:OUT="02_geom_base.json"; & $kpy 04_extract.py
$env:GEOM="02_geom_base.json";    $env:OUTJ="03_measure_base.json"; & $py 07_measure.py
$env:MAPLAYER="F.Cu,In1.Cu"; & $kpy 04_localmap.py        # the copper map the design was drawn on
& $kpy 05_components.py                    # where the 10 F.Cu islands are
$env:SRC="esc_base.kicad_pcb"; $env:DST="esc_repour_v4.kicad_pcb"; $env:ZONES="1"; `
  $env:BUD_BATP="24"; $env:BUD_BATN="16"; & $kpy 08_repour.py      # EXECUTE -> v4
$env:BOARD="esc_repour_v4.kicad_pcb"; $env:OUT="15_geom_v4.json"; & $kpy 04_extract.py
$env:GEOM="15_geom_v4.json"; $env:OUTJ="16_measure_v4.json"; & $py 07_measure.py
& $kpy 18_refill_only.py                   # control: no edit, byte-identical to base
$env:BOARDS="esc_base.kicad_pcb,esc_repour_v4.kicad_pcb"; & $kpy 20_invariants.py
# attribution: pad property only, no new copper  (-> 24_measure_solidonly.json)
$env:SRC="esc_base.kicad_pcb"; $env:DST="esc_attr_solid.kicad_pcb"; $env:ZONES="0"; `
  $env:BUD_BATP="0"; $env:BUD_BATN="0"; & $kpy 08_repour.py
$env:BOARD="esc_attr_solid.kicad_pcb"; $env:OUT="23_geom_solidonly.json"; & $kpy 04_extract.py
$env:GEOM="23_geom_solidonly.json"; $env:OUTJ="24_measure_solidonly.json"; & $py 07_measure.py

# DRC, all three runs on the same 4 oz 0.25 mm rules (each dir: board + .kicad_pro + .kicad_dru)
& $cli pcb drc drc_base\base.kicad_pcb -o drc_base\drc.json --format json --severity-all --units mm
& $cli pcb drc drc_ctl\ctl.kicad_pcb   -o drc_ctl\drc.json   --format json --severity-all --units mm
& $cli pcb drc drc_v4\v4.kicad_pcb     -o drc_v4\drc.json    --format json --severity-all --units mm
$env:A="drc_base/drc.json"; $env:B="drc_v4/drc.json"; & $py 13_drcdiff.py     # pair diff
$env:A="drc_base/drc.json"; $env:B="drc_v4/drc.json"; & $py 19_sitediff.py    # site diff
$env:MEAS_BASE="03_measure_base.json"; $env:MEAS_AFTER="16_measure_v4.json"; & $py 22_numbers.py
```



