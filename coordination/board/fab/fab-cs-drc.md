# Code-SDR V2 — DRC debt cleared? classification, repair, and what a fab actually needs

**Board** `repos/Code-SDR/hardware/v2/Code-SDR-V2.kicad_pcb` · rev **2.1** (title block) ·
4 copper layers, all four at **0.035 mm = 1 oz** · 373 footprints · 11,168 tracks · 1,085 vias ·
Edge.Cuts **101.7 × 101.7 mm**.
**Host** KiCad **9.0.7** (`kicad-cli` 9.0.7; python 3.11 + pcbnew 9.0.7) on Windows 11.
**Repo state** clean tree at `6fbc004` on `work/2026-11-11`; **no write of any kind into the repo**
(§9). Everything below is reproducible from the scripts in this directory.

Tier label on every number: **MEASURED** = tool output in this directory; **DERIVED** = arithmetic
on a measured number; **UNVERIFIED** = stated as such.

---

## 1. The 222 is confirmed, down to the item

```
kicad-cli pcb drc --format json --severity-all --units mm -o drc_baseline.json <board>
Found 222 violations
Found 0 unconnected items
```

| type | count | severity |
|---|---|---|
| `lib_footprint_mismatch` | **199** | warning |
| `via_dangling` | **13** | warning |
| `track_dangling` | **10** | warning |
| **total** | **222** | **zero errors** |

MEASURED — `drc_baseline.json`; severity tally printed by `s20_report_numbers.py`.

Two facts that matter more than the total:

1. **Every one of the 222 is severity *warning*.** There is not a single `error`-severity
   violation on this board, and there are no unconnected items.
2. **0 unconnected items** with `--severity-all` and no exclusions: the project file holds
   `"drc_exclusions": []` and sets all three types to `warning`
   (`Code-SDR-V2.kicad_pro`, `rule_severities`). So the netlist is complete as drawn.

Reproduction control: `drcenv/V0.kicad_pcb` is a **byte-identical copy** of the repo board
(sha256 `309414D2…FF486` matches). Its DRC gives 222 and **the identical set of 199 reference
designators** — so the measurement is stable and the copy environment used for the experiments is
faithful.

---

## 2. The 199 `lib_footprint_mismatch`: measured, not assumed

### 2.1 What was compared

Two independent comparisons were run, because a signature-based comparison can lie:

* **API comparison** (`s01_mismatch.py`): board footprint vs `pcbnew.FootprintLoad()` of the
  library item, component by component (pads, silkscreen, courtyard, F.Fab, 3-D models, footprint
  attributes), normalised for placement and rotation.
* **Raw s-expression comparison** (`s03_sexpr.py`): parse the footprint block out of the
  `.kicad_pcb` and the `.kicad_mod` from the library, drop only placement/identity nodes
  (`at`, `uuid`, `net`, `path`, `property`, `layer` at footprint level), then diff the token
  multiset. This is the check of record; it cannot be fooled by an API detail.
* **Text diff** of individual footprints (`s07_textdiff.py`) to print exactly what differs.

### 2.2 The aggregate over all 373 footprints (MEASURED)

| what differs | footprints |
|---|---|
| **any pad node** (shape, size, drill, layers, offset, roundrect, chamfer, mask/paste) | **0** |
| **3-D model** (path, offset, scale, rotation) | **0** |
| **courtyard** | **0** |
| silkscreen graphics (`F.SilkS`) | 267 |
| pad `zone_connect` written explicitly on the board | 233 |
| `F.Fab` graphics | 21 |
| flagged by DRC | 199 |

**There is not one footprint on this board whose pads differ from its library in any way.**
Not a size, not a shape, not a drill, not a layer set, not an offset. The 199 warnings are
silkscreen/Fab artwork and a routing preference — nothing that exists in copper.

### 2.3 Sample of 26, itemised (`s21_sample_table.py`)

| ref | library item | DRC | what differs | electrical? |
|---|---|---|---|---|
| C1 | Capacitor_SMD:C_0805_2012Metric | flagged | 2 lib silk lines missing on board, pad zone_connect | no |
| C205 | C_0402_1005Metric | flagged | 2 silk lines missing, zone_connect | no |
| C60 | C_0402_1005Metric | flagged | 2 silk lines missing, zone_connect | no |
| C78 | C_0402_1005Metric | flagged | 2 silk lines missing, zone_connect | no |
| C226 | C_0402_1005Metric | flagged | 2 silk lines missing, zone_connect | no |
| U10 | QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm_ThermalVias | flagged | 8 silk lines missing, zone_connect | no |
| L91 | L_0603_1608Metric_Pad1.05x0.95mm_HandSolder | flagged | 2 silk lines missing | no |
| R132 | R_0402_1005Metric | flagged | 2 silk lines missing | no |
| J63 | SMA_Molex_73251-1153_EdgeMount_Horizontal | flagged | 3 silk lines missing, zone_connect | no |
| J60 | SMA_Molex_73251-1153_EdgeMount_Horizontal | flagged | 3 silk lines missing, zone_connect | no |
| U21 | LFCSP-32-1EP_5x5mm_P0.5mm_EP3.6x3.6mm_ThermalVias | flagged | 8 silk lines missing, zone_connect | no |
| SW1 | SW_SPST_TL3342 | flagged | 8 silk lines missing, zone_connect | no |
| Y40 | Oscillator_SMD_SiT_PQFN-4Pin_3.2x2.5mm | flagged | 2 silk lines missing, zone_connect | no |
| F1 | Fuse_1812_4532Metric | flagged | 2 silk lines missing | no |
| T60 | Transformer_MiniCircuits_AT224-1A | flagged | 7 silk lines missing, zone_connect | no |
| J30 | RJ45_Pulse_JK0654219NL_Horizontal | flagged | 9 silk lines missing | no |
| U51 | LFCSP-24-1EP_4x4mm_P0.5mm_EP2.5x2.5mm_ThermalVias | **not** flagged | 8 silk lines missing, zone_connect | no |
| R1 | R_0402_1005Metric | **not** flagged | 2 silk lines missing | no |
| R105 | R_0201_0603Metric | **not** flagged | nothing after normalisation | no |
| C314 | C_0402_1005Metric | **not** flagged | zone_connect only | no |
| C311 | C_0402_1005Metric | **not** flagged | zone_connect only | no |
| FB34 | L_0402_1005Metric | **not** flagged | nothing | no |
| L98 | L_0402_1005Metric | **not** flagged | nothing | no |
| U70 | CodeSDR:Infineon_TSNP6_1.1x0.7mm | **not** flagged | F.Fab text + zone_connect | no |
| C22 | C_0603_1608Metric | **not** flagged | zone_connect only | no |
| C9 | C_0603_1608Metric | **not** flagged | 2 silk lines missing, zone_connect | no |

The recurring difference is the same one everywhere: **the designer deleted the library's
silkscreen body-outline lines** (`fp_line` on `F.SilkS`, width 0.12) from the passive and IC
footprints — 2 lines per 0402/0603/0805, 7–9 lines per QFN/RJ45/SMA. That is a board-authoring
choice for a dense board, not a defect. `zone_connect` is a *routing* preference (which pads the
zones may flood onto), written explicitly by whoever last edited the pads; it changes zone fill,
not pad copper.

### 2.4 Controlled experiments prove the mechanism

Each variant is a copy in `drcenv/` differing from the baseline by **one** thing; DRC re-run with
the same arguments (`s09_surgery.py`, `s10_batch_restore.py`, `drc_V*.json`).

| variant | single change | result |
|---|---|---|
| V0 | none (byte-identical copy) | 222, same 199 refs — control |
| **V1** | restore the 2 library silk lines on **L91 only** | **L91 leaves the flagged set** |
| **V2** | remove the explicit `zone_connect` from **C1** | **C1 still flagged** — zone_connect is not the trigger |
| **V3** | remove `zone_connect` from **C205** | **C205 still flagged** |
| **V5** | restore the library silkscreen on **246** footprints | **199 → 0 mismatches**; 222 → 24 total |

So the entire 199 is **silkscreen geometry, and nothing else**. V5's residual 24 = 13 via + 10
track + **1 new `silk_over_copper`** ("Silkscreen clipped by solder mask", `Polygon of U30 on
F.Silkscreen`): putting the artwork back costs one cosmetic warning of its own.

**Is any of it electrically real? No.** Nothing in the 199 changes copper: pad size, shape, drill,
layer set, offset, mask/paste, courtyard and 3-D model are identical on all 373 footprints (§2.2),
and the only other differences are silkscreen ink and a zone-flood preference.

**Should the fab care? No.** A fab house builds from the Gerbers it is sent. The silkscreen it
receives is whatever Gerber says — this board's `F_Silkscreen.gto` is 7,370 bytes and
`B_Silkscreen.gbo` 469 bytes, i.e. deliberately sparse, and that is exactly what will be printed.
The library-parity warning is a statement about the *designer's library*, not about the board.

**Honest anomaly (UNVERIFIED).** The flagged membership is not a clean function of footprint
content. Two instances of the same library item with textually identical board blocks (e.g. R1
unflagged vs L91 flagged, both "2 silk lines deleted") receive different verdicts, and restoring
one footprint's silk (V1) let a *different, untouched* footprint (C309) into the set. Restoring
246 footprints at once (V5) is monotone and clean. I did not reverse-engineer KiCad's internal
equivalence rule for the single-footprint case and will not pretend to. It does not affect the
conclusion: V5 shows the class is silkscreen, and §2.2 shows it is never pad copper.

---

## 3. The 13 `via_dangling` + 10 `track_dangling`: not a fill artefact

### 3.1 The zone-fill hypothesis, tested

The board carries four filled zones — GND on F.Cu (22 outlines, 3,340.07 mm²), GND on In1.Cu
(17 outlines, 8,808.72 mm²), +3V3_DIG on In2.Cu (7, 4,465.05 mm²), +3V3_ANA on In2.Cu (3,
4,215.35 mm²) — all `IsFilled=True`.

I refilled every zone with `pcbnew.ZONE_FILLER` on the copy (`s14_refill.py`) and compared:

```
before refill: {(0,F.Cu):(22,3340.07), (1,In1.Cu):(17,8808.72), (2,In2.Cu):(7,4465.05), (3,In2.Cu):(3,4215.35)}
after  refill:  identical, to 0.01 mm² and to the outline count
CHANGED: nothing
```

DRC on the refilled board: **222, 0 unconnected — unchanged** (`drc_V6_refilled.json`).

**Verdict: the stored fill is current. These dangling items are not artefacts of an unfilled or
stale zone.** (The "GND vias not connected on F.Cu" ones sit where the F.Cu GND pour genuinely has
no copper — the F.Cu pour is only 3,340 mm² on a 101.7 mm square board.)

### 3.2 Are they load-bearing? Measured one item at a time

For each of the 23 items: remove it, rebuild connectivity, read `GetUnconnectedCount()`, put it
back (`s16_peritem.py`, `s16_peritem.json`). Baseline unconnected = 0.

| item | net | layer | length | unconnected if removed |
|---|---|---|---|---|
| track | +3V3_ANA | F.Cu | 5.1200 mm | **1** |
| via | ADC_CLK | F.Cu | – | **1** |
| track | ADC_D6 | F.Cu | 1.0625 mm | **1** |
| via | ADC_REFB | F.Cu | – | **1** |
| track | FPGA_AUX_2V5 | F.Cu | 0.8427 mm | **1** |
| via | FPGA_VCCIO2_3V3 | F.Cu | – | **2** |
| track | GND | F.Cu | 1.7678 mm | **1** |
| via ×6 | GND | F.Cu | – | **0** |
| track | GRF2013_RFOUT_VDD | F.Cu | 4.6519 mm | **0** |
| track | GRF2013_RFOUT_VDD | F.Cu | 0.4123 mm | **0** |
| via | MDIO | F.Cu | – | **1** |
| track | PHY_AVDDL_1V2 | F.Cu | 1.9800 mm | **1** |
| via | QSPI_SD1 | F.Cu | – | **1** |
| via | REF_100M_ADC | F.Cu | – | **1** |
| via | RGMII_RXC_FPGA | F.Cu | – | **1** |
| track | RGMII_TXD0 | B.Cu | 1.6971 mm | **1** |
| track | RGMII_TXD2 | B.Cu | 8.0000 mm | **1** |
| track | HSW_V1_CHIP | F.Cu | 0.0800 mm | **0** |

**9 of the 23 are electrically free** (6 GND stitching vias that only reach the In1 pour, two
`GRF2013_RFOUT_VDD` stubs, one 0.08 mm `HSW_V1_CHIP` stub). **14 are load-bearing**: deleting them
disconnects a net. Their warning is "this end is free" / "connected on one layer", not "this item
is useless".

### 3.3 Deletion is the wrong repair — measured twice

| attempt | method | result |
|---|---|---|
| V7 | delete **all 23** | 220 violations **and 15 unconnected items** — a fab-blocking regression. Wrong. |
| V8 / V9_round1 | delete the **9** electrically-free items | 215, **0 unconnected** — safe |
| V9_round2, round3 | continue on the newly exposed stubs | 215, 16 dangling, **unchanged** — the stub chains shorten by ~0.05–0.08 mm per round instead of disappearing |

The cascade is the real lesson: `HSW_V1_CHIP` is a chain of 0.08 mm segments; deleting one exposes
the next, and the DRC count does not fall. **The only correct repair for the 14 is a trim** —
shorten the segment from the free end back to the last junction — which is a copper edit on a
1 oz RF board, and there is no fab benefit to it (see §5).

The two long stubs deserve a separate note because they are the only ones with an electrical
smell: `RGMII_TXD2` carries an **8.0 mm** free-ended segment on B.Cu, and `GRF2013_RFOUT_VDD` a
**4.65 mm** one on F.Cu. As a *rough* line-length estimate at er 4.2 (DERIVED, not simulated) a
4.65 mm stub is ≈31 ps, i.e. a quarter-wave null near **7.9 GHz** — inside this board's advertised
100 MHz–10 GHz span. It is on the RF *output bias* net, not the signal path, so the consequence is
a supply-feed resonance, not a signal notch. Flagged, not measured: this board has no EM model of
that stub and I did not build one.

---

## 4. DRC after, broken down the same way

| board | violations | `lib_footprint_mismatch` | `via_dangling` | `track_dangling` | other | unconnected |
|---|---|---|---|---|---|---|
| **as found** (repo) | **222** | 199 | 13 | 10 | 0 | **0** |
| control copy (byte-identical) | 222 | 199 | 13 | 10 | 0 | 0 |
| after zone refill | 222 | 199 | 13 | 10 | 0 | 0 |
| **after removing the 9 free-scrap items** | **215** | 199 | 7 | 9 | 0 | **0** |
| after deleting all 23 (rejected) | 220 | 199 | 0 | 21 | 0 | **15** |
| after restoring library silk on 246 fp (diagnostic) | 24 | **0** | 13 | 10 | 1 silk_over_copper | 0 |

MEASURED — `drc_baseline.json`, `drc_V0.json`, `drc_V6_refilled.json`, `drc_V8_scrap.json`,
`drc_V7_fixed.json`, `drc_V5_all_silk.json`.

**What the number means for ordering: nothing.** The deliverable a fab house quotes and builds from
is the Gerber/drill/position set, and that set exports cleanly from this board today
(`fabpkg/`, `fabpkg-clean/`):

* 4 copper layers + 2 masks + 2 silkscreens + 2 paste + Edge_Cuts, plus `job.gbrjob`
* **PTH drill tools 0.200 / 0.250 / 0.300 / 0.400 / 0.460 / 0.600 / 0.650 / 0.850 / 0.890 /
  1.025 / 1.300 / 1.570 mm**, NPTH 3.200 mm — every via drill is ≥ 0.200 mm, so the **no-HDI,
  standard-PTH constraint is satisfied on this board** (drills measured: 983 × 0.20, 89 × 0.25,
  13 × 0.40)
* `.pos` ASCII, 1 oz copper on all four layers, rev **2.1** in the title block and carried in every
  filename

Two adjacent notes, so nobody is surprised later: the outline is **101.7 × 101.7 mm**, which misses
the 100 mm panel/price tier by 1.7 mm, and the **minimum track width is 0.100 mm** (1,510 segments)
— manufacturable at 1 oz at every house I know of, but it is the tightest thing on the board and
the one parameter worth confirming with the chosen fab.

---

## 5. What a fab actually needs from DRC — which categories stop an order

A fab house receives artwork, not a project file. It has no access to your library and no interest
in it. What it checks is that the artwork is internally consistent and inside its process window.
So the categories sort like this:

| DRC category | stops an order? | why |
|---|---|---|
| **clearance / shorts / tracks_crossing** | **YES** | the panel would short. Must be zero. |
| **annular_width / min drill / via_diameter** | **YES** | below the drill/plating capability it cannot be built at all — this is where the *no-HDI, ≥0.2 mm* rule lives |
| **min track width / spacing below the copper-weight rule** | **YES** | at 4 oz (ESC only) 0.2 mm is the floor; at 1 oz 0.1 mm is fine |
| **unconnected items** | **YES, functionally** | the board etches but will not work. Here: **0** |
| **hole_to_hole, hole_clearance** | **YES** (drill breakage) | here: none reported |
| **courtyard / malformed_courtyard** | no (assembly, not fab) | placement/assembly check |
| **silk_over_copper / silk edge clipping** | no | cosmetic; the fab prints what the Gerber says, and clipped silk is the designer's artwork choice |
| **lib_footprint_mismatch** | **no — never** | a comparison between your board and your library. It is not in the Gerber set. Zero fab relevance. |
| **via_dangling / track_dangling** | **no** | a stub is copper that etches and plates like any other copper. It is a design-hygiene warning, not a manufacturing constraint. |
| **unconnected_items (as a *warning*)** | — | on this project it is an error severity and it is 0 |

The asymmetry worth stating plainly: **the 222 warnings are exactly the three categories a fab
house never looks at.** The categories that *do* stop an order (clearance, annular ring, drill
size, shorts, unconnected) are all at zero on this board.

---

## 6. Checklist line

> **Code-SDR V2 rev 2.1 — DRC: PASS with waiver.**
> 222 warnings, **0 errors, 0 unconnected items** (`drc_baseline.json`, KiCad 9.0.7).
> 199 `lib_footprint_mismatch` = silkscreen-artwork parity only: **0 of 373 footprints differ from
> library in any pad node or 3-D model** (§2.2); restoring the library silk on 246 footprints
> removes all 199 (§2.4, V5) but adds a `silk_over_copper` warning, so the deletions are kept.
> **Waived**: harmless by construction, invisible to a fab house.
> 13 `via_dangling` + 10 `track_dangling` = 9 electrically free scrap items (safe removal verified,
> 215 warnings / 0 unconnected) + 14 load-bearing one-ended segments whose only correct repair is a
> copper trim with no fabrication benefit. **Waived** (§3, §5).
> Zone fill verified current by refill-and-compare (§3.1). Gerber/drill/position package exports
> cleanly with all via drills ≥ 0.200 mm (§4).

**ORDERABLE: YES.** Nothing on this board requires a respin, a stackup change, or an HDI process.

---

## 7. Artefacts in this directory

| file | what it is |
|---|---|
| `drc_baseline.json` | the 222 (repo board), full JSON |
| `drc_baseline2.json` | second run — identical, proves determinism |
| `s01_mismatch.py` / `s01_mismatch_rows.json` | API-level footprint comparison, all 373 |
| `s03_sexpr.py` / `s03_sexpr_rows.json` | raw s-expression comparison (check of record) |
| `s07_textdiff.py` / `s06_full_out.txt` | unified text diffs of individual footprints |
| `s09_surgery.py`, `s10_batch_restore.py` | variant builder (repo read-only) |
| `drcenv/V0…V9_*.kicad_pcb` | the variant boards; V0 is byte-identical to the repo board |
| `drc_V0/V1/V2/V3/V4/V5/V6/V7/V8/V9_*.json` | DRC result for every variant |
| `s11_dangling.py`, `s12_connectivity.py`, `s13_dangling2.py` | dangling-item characterisation |
| `s14_refill.py` | zone refill experiment (fill unchanged) |
| `s16_peritem.py` / `s16_peritem.json` | per-item load-bearing measurement |
| `s17_fix_scrap.py` | **the patch**: removes only the 9 measured-safe items |
| `s19_round.py` | one removal round per process (pcbnew cannot save+reload in one interpreter) |
| `fabpkg/`, `fabpkg-clean/` | exported Gerbers, PTH/NPTH drills, `.pos`, `.gbrjob` |
| `repo-before-state.txt` | 3,726-file snapshot of the repo before any command ran |

---

## 8. UNVERIFIED / not done

1. **Why the DRC flags 199 of the 267 silk-differing footprints** (and why V1 let C309 in). The
   class is proved (V5: 199→0); the per-instance boundary is KiCad-internal. UNVERIFIED.
2. **`pcbnew`'s `TestTrackEndpointDangling()` mutates the track it tests** — after the call the
   segment's start collapses onto its end (length 2.9 m → 0.0). I discarded those results and used
   the remove/measure/re-add method instead. Anyone scripting this API should know.
3. **No EM model of the 8.0 mm `RGMII_TXD2` and 4.65 mm `GRF2013_RFOUT_VDD` stubs.** The 7.9 GHz
   quarter-wave figure in §3.3 is closed-form arithmetic, not a solve.
4. **Minimum track width 0.1 mm at 1 oz** is taken as manufacturable; I did not check it against a
   specific fabricator's published 1 oz rule. Confirming it with the chosen house is one email.
5. **Assembly/DFM beyond DRC** (courtyard overlaps, paste apertures, part rotation vs the pick-and-
   place convention) was not audited — out of scope for this item.

---

## 9. Repo hygiene

`repo-before-state.txt` records all 3,726 non-`.git` files with size and mtime before the first
command; `repo-after-state.txt` is the same snapshot taken at the end. Every artefact above was
written to `evidence/fab-cs-drc/`; the repo was only opened read-only by `kicad-cli` and `pcbnew`,
and the one library directory KiCad had to *read* for the variant runs (`CodeSDR.pretty`) was
**copied** into `drcenv/` rather than referenced in place. No commit, no push, no `audit/*` branch,
no write to any working tree.

**One honest exception, not attributable to this item:** `hardware/v2/build/ROUTE_STATISTICS.csv`
(11,429 B) has a *different mtime* at the end (2026-11-15T11:05Z vs 2026-11-14T12:15Z) with
**identical content** — `git status --porcelain` is empty (0 lines) at both the start and the end
of this item, so the tree is clean. Nothing in this item's command list writes to `build/`; a
concurrent worker in the same wave regenerating route statistics is the likely author. Flagged so
the orchestrator can attribute it, not hidden.