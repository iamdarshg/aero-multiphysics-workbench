# The pre-fab checklist, v2 — four boards, every cell measured, signed or refused

**Owner:** fab-checklist specialist, wave 6. **Date:** 2026-11-16. **Host:** KiCad 9.0.7
(`C:/Program Files/KiCad/9.0/bin/kicad-cli.exe`, bundled `python.exe` + `pcbnew` 9.0.7), CPython 3.12
for the arithmetic.
**Supersedes:** `evidence/fab-checklist/REPORT.md` (v1, 2026-11-15). v1 predates the span census, the
ESC compaction and the drone-mech zero; this sheet carries all three.
**Hard rule observed:** nothing was written into a repo, nothing committed or pushed, no `audit/*`
branch touched. Every board analysed here is a **byte copy** under `boards/`; every artefact is under
`evidence/fab-checklist-v2/`. The four copies reproduce the hashes the programme already records
(§2.0), so no measurement here is about a drifted file.

**Receipt that no repo was touched:** `git -C repos/drone-arm status --porcelain` shows only the
pre-existing stray `MEMORY.md` (recorded in `fab-esc-rules-first`), `repos/Code-SDR` is clean, and both
are on `work/2026-11-11`. No `audit/*` branch was read or written.

**Constraints in force:** NO HDI anywhere; ONLY the ESC is 4 oz; $60 coupon/prototype cap; ESC
single-sided and as compact as possible (owner, 2026-11-15).

---

## 0. The answer, before the evidence

| board | orderable today | the single number that decides it |
|---|---|---|
| **drone-arm main rev_b** | **NO** | **15 non-through vias** — 11 blind + 4 buried, 14 of them at 0.100 mm; the zero is **proved impossible** for the edit class "via edit + local copper move" |
| **ESC rev_b** | **NO** | **1,542 unconnected** (pcbnew; the 499 everyone quotes is `kicad-cli`'s cap) and at 4 oz **371 pad gaps at exactly 0.2000 mm** plus **110 holes at 0.200 mm** against a published 4 oz floor of 0.30 mm |
| **Code-SDR V2** | **YES**, bare board | **0 errors, 0 unconnected, 1,215 holes** in a frame-free package stamped `2.1` |
| **drone-mech airframe** | **NO** (mechanical) | interference is **0 pairs / 0.000000 mm³** in the genuine class, but the zero **costs a tail-interface change of +38.485 mm** that is not in the design intent |

Three of four are refused, and none of the refusals is a labelling argument.

**What "orderable" means here** — unchanged from v1, because the word does the most work on the page:

> **ORDERABLE = a bare-board fabrication order placed today, from artefacts that exist today, produces
> the board the design describes, with nothing to fix afterwards.**

Not "the design is finished" and not "assembly can be quoted". A board that etches but cannot function
is **not** orderable, because the rework is the thing this programme exists to avoid
(`AGENT_BOARD.md:5-25`). Assembly data (BOM, pick-and-place, fiducials, test points) is scored
separately in §8 — it stops an **assembly PO**, not the etch order.

**Counting rule for §1.** 13 verdict-bearing columns per board; column 14 is the verdict itself. Every
cell ends with exactly one of `PASS` / `FAIL` / `WAIVED`, so the tally in §9 can be counted from the
table by machine (`check_report.py`), not asserted by me.

---

## 1. THE CHECKLIST — one row per board, one column per line

Cell format: **value** `source tag` — **verdict**. Tags resolve in §2; the measurement behind each
column is in §2.1–2.13. The table needs horizontal scroll: 14 columns is the shape a sign-off needs.

| board | 1. layers | 2. copper weight | 3. min track | 4. min space | 5. min drill | 6. min annular ring | 7. non-through vias BY SPAN | 8. unconnected (tool, cap?) | 9. DRC count and severity | 10. gerber package state | 11. revision stamp | 12. panel outline and area | 13. surface finish | 14. orderable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **drone-arm main rev_b** <br>*(best artefact: fanout3 = fanout7, sha `372C1D52…FA9077`)* | **4 copper** `M-DA` — **PASS** | **1 oz, 0.035 mm ×4** `M-DA` — **PASS** | **0.200 mm**, 500 segments at that width `M-DA` — **PASS** | **0.1250 mm**, 509 pairs above the 0.30 mm probe floor `S-DA` — **PASS** | **0.100 mm** on 14 of the 15 non-through vias `M-DA` — **FAIL** (MOVE) | **0.100 mm** via (21) / **0.150 mm** PTH (`U41.17`) `M-DA` — **FAIL** (MOVE) | **15 = 11 blind + 4 buried**; 0.100 ×14, 0.300 ×1 (In2→B) `M-DA` — **FAIL** (MOVE — U10 fan-out re-escape) | **0** — pcbnew `GetUnconnectedCount(False)`, **not cap-limited**; `kicad-cli` also 0, both far below any cap `M-DA` `D-DA` — **PASS** | **7 error** own rules (all `via_diameter`); **22 error** under the span gate = 15 HDI + 7 `D-DA` — **FAIL** (MOVE) | **package7**: 63/63 assertions, 11 Gerbers + 7 Excellon, **360 drills + 4 slots**, **5 blind/buried files carrying 15 holes**, **SENDABLE = NO** `G-DA` — **FAIL** (MOVE) | repo `""`; the package reads **`B`** on 19 carriers `M-DA` `G-DA` — **FAIL** (PARAM: apply `title_block_rev_B.patch`) | **140.000 × 100.000 mm = 140.00 cm²**, 1-up, no rails `M-DA` — **PASS** | **ENIG** `M-DA` `G-DA` — **PASS** | **NO** |
| **ESC rev_b** <br>*(sha `992570571D…995DDD`)* | **4 copper** `M-ESC` — **PASS** | **0.140 mm outer (4 oz) / 0.0525 mm inner (1.5 oz)** `M-ESC` — **PASS** | **0.200 mm**, 4 segments, 5.79 mm of copper `M-ESC` — **FAIL** at 4 oz (PARAM) | **0.2000 mm**, 372 pairs at the 0.30 mm probe floor `S-ESC` — **FAIL** at 4 oz (RESPIN / owner decision) | via **0.300 mm** / PTH pad **0.200 mm on 110 pads** `M-ESC` — **FAIL** at 4 oz (PARAM + RESPIN) | **0.150 mm** via / **0.125 mm** PTH (`U204.11`); all 1,990 vias ≤ 0.200 mm `M-ESC` — **FAIL** at 4 oz (PARAM) | **0 of 1,990 — all through** `M-ESC` — **PASS** | **1,542** — pcbnew ratsnest, **no cap**; `kicad-cli` **499 exactly at its hard cap**, therefore a truncation `M-ESC` `D-ESC` — **FAIL** (MOVE) | **523** at 4 oz 0.250 (504 error / 19 warn); **102** at 0.200; **16** at 0.200 + 0.150 ring `D-ESC` — **FAIL** (PARAM + RESPIN + MOVE) | **none** — 0 gerber, 0 drill, 0 job, 0 pos anywhere under `hardware/esc` `SCAN` — **FAIL** (PARAM after the route) | `""`, and no silk revision text `M-ESC` — **FAIL** (PARAM) | **173.950 × 283.080 mm = 491.732 cm²**, 1-up; the compacted **370.119 cm² is UNSAFE** `M-ESC` `R-ESC2` — **PASS** (size is not the blocker) | **ENIG** `M-ESC` — **PASS** | **NO** |
| **Code-SDR V2** <br>*(sha `309414D2…`)* | **4 copper** `M-CS` — **PASS** | **1 oz, 0.035 mm ×4** `M-CS` — **PASS** | **0.100 mm**, 1,510 segments at that width `M-CS` — **PASS** | **0.1000 mm**, 513 pairs at the 0.30 mm probe floor `S-CS` — **PASS** | **0.200 mm** via and PTH pad `M-CS` — **PASS** | **0.100 mm** via (53) / **0.125 mm** (1,013) / **0.150 mm** PTH `M-CS` — **WAIVED**: below a 0.15 mm published house floor, above the board's own 0.10 mm rule; a quote line, not a redesign | **0 of 1,085 — all through**; 0.200/0.400 up to 1.0/0.4 `M-CS` — **PASS** | **0** — pcbnew and `kicad-cli` agree, both below cap `M-CS` `D-CS` — **PASS** | **0 error / 222 warning / 0 unconnected** under its own rules **and** its own `.kicad_dru` `D-CS` — **PASS** | **11 Gerbers + `.gbrjob` + 2 Excellon = 1,215 hits** (1,213 drills + 2 slots), **0 non-through**; not in the repo, exported here `X-CS` — **PASS** | **`2.1`** in the title block and in `cs-job.gbrjob` `M-CS` `X-CS` — **PASS** | **101.600 × 101.600 mm = 103.23 cm²**, 1-up; 1.7 mm over the 100 mm price tier `M-CS` — **PASS** | **ENIG** `M-CS` `X-CS` — **PASS** | **YES** (bare board) |
| **drone-mech airframe** <br>*(no PCB: measured 0 board files)* | n/a — no PCB in this deliverable `SCAN` — **WAIVED** (mechanical airframe) | n/a — no PCB `SCAN` — **WAIVED** (mechanical airframe) | n/a — no PCB `SCAN` — **WAIVED** | n/a — no PCB `SCAN` — **WAIVED** | n/a — no PCB `SCAN` — **WAIVED** | n/a — no PCB `SCAN` — **WAIVED** | n/a — 0 vias `SCAN` — **WAIVED** | n/a — 0 nets `SCAN` — **WAIVED** | **interference sweep instead of DRC: 0 pairs / 0.000000 mm³ genuine** `R-DM` — **PASS** | **no manufacturing package**: 205 STEP/brep, 0 drawings, 0 ply book; the executed change is **6 STEPs in `evidence/`, 0 in `repos/`** `R-DM` — **FAIL** | **no revision carries the +38.485 mm station change** `R-DM` — **FAIL** | not a panel: the 42_6 shell is **4 disjoint solids over 77.165 mm**; **41,775.81 mm³** phantom outboard loft `R-DM` `AGENT_BOARD.md:250-253` — **FAIL** | **printed PLA core 145.739 g + CF/glass wrap 105.779 g** `AGENT_BOARD.md:281-283` — **PASS** | **NO** |

**Row 4 is not padding.** A machined/composite airframe has no copper, so **eight of the thirteen**
columns are inapplicable — and that is measured, not asserted (0 `.kicad_pcb`, 0 gerber, 0 drill,
0 `.kicad_pro` under `repos/drone-mech`, against **205** STEP/brep). The **five** columns that do apply
carry the mechanical verdicts, and §3 gives the interference numbers in full.

---

## 2. How each line was measured

### 2.0 The four boards, and the proof they are the boards of record

`measure.py` loads each copy with `pcbnew` and **never saves**. Hashes are of the copies:

| board in §1 | copy | sha256 (prefix) | equals the programme's record for |
|---|---|---|---|
| drone-arm best | `boards/da_best.kicad_pcb` | `372C1D525BEBF651…` | `fab-da-fanout3/work.kicad_pcb` = `fab-da-fanout2/da_main_rev_b_fanout7.kicad_pcb` = `fab-verify-w4/work/fanout7.kicad_pcb` (`fab-da-package7/REPORT.md:24-32`) |
| drone-arm repo original | `boards/da_repo.kicad_pcb` | `9B3BBA85C01AAC9E…` | the repo board v1 measured (`fab-checklist/REPORT.md:364`) |
| ESC | `boards/esc.kicad_pcb` | `992570571DEBC473…` | every ESC unit in this programme |
| Code-SDR V2 | `boards/cs.kicad_pcb` | `309414D2B371C626…` | `fab-cs-drc/drcenv/V0.kicad_pcb` (`fab-checklist/REPORT.md:366`) |

Source tags used above:

| tag | file | produced by |
|---|---|---|
| `M-DA` `M-ESC` `M-CS` | `out/measure_{da_best,esc,cs}.json`, `out/{side_census,pth_drill_hist,da_conn_census}.json` | `"C:/Program Files/KiCad/9.0/bin/python.exe" measure.py` (pcbnew 9.0.7, read-only) |
| `S-DA` `S-ESC` `S-CS` | `drc/{da,esc,cs}_space/drc.json` | `kicad-cli pcb drc` with the clearance floor raised to 0.30 mm, then the minimum of KiCad's own `actual` values (`drc_run.py`) |
| `D-DA` `D-ESC` `D-CS` | `drc/da_own/`, `drc/da_span/`, `drc/esc_025/`, `drc/esc_020/`, `drc/cs_own/` | `kicad-cli pcb drc --format json --severity-all --units mm`; all eight runs exit 0, summarised in `out/drc_summary.json` |
| `G-DA` | `../fab-da-package7/package/` + `out/drill_census.log` | `drill_census_v2.py` re-counts the package that unit built |
| `X-CS` | `export_cs/` | my own export from a byte copy: `kicad-cli pcb export gerbers` + `export drill` |
| `SCAN` | run log | recursive artefact scan of `repos/drone-mech`, `repos/drone-arm/hardware/{main,esc}`, `repos/Code-SDR/hardware/v2` |
| `R-ESC2` `R-DM` | `../esc-routable2/REPORT.md`, `../fab-dm-final/REPORT.md` | sibling units of waves 5 and 6 |

### 2.1 Layer count and copper weight — read from each file's own stackup block
`M-*` parse the `(stackup …)` block and list every copper layer's thickness:

| board | copper | dielectrics | stackup over copper |
|---|---|---|---|
| drone-arm main | `F.Cu 0.035 / In1 0.035 / In2 0.035 / B.Cu 0.035` | prepreg 0.2 / core 1.04 / prepreg 0.2 | **1.580 mm** against a 1.60 declared (−1.25 %) |
| ESC | `F.Cu 0.14 / In1 0.0525 / In2 0.0525 / B.Cu 0.14` | prepreg 0.2 / core 0.795 / prepreg 0.2 | 1.575 mm over copper |
| Code-SDR V2 | `0.035 ×4` | prepreg 0.13 / core 1.2 / prepreg 0.13 | **1.600 mm**, exact |

These reproduce `AGENT_BOARD.md:34-41` exactly and are the only three boards in the roster. **No fourth
board exists**, and the 4 oz declaration is still ESC-only.

### 2.2 Minimum track width — the minimum over every segment, never over `segments + vias`
`M-*`: DA **0.200** with **500** segments at that exact width; ESC **0.200** with **4** segments
(5.79 mm of copper in total); CS **0.100** with **1,510** at that width. The v1/brief "2,620 tracks on
DA / 12,253 on CS / 2,144 on ESC" are **segments + vias** (2,306 + 336 = 2,642 on the best DA
artefact; 11,168 + 1,085 = 12,253; 154 + 1,990 = 2,144). Same slip, third wave; measured again here so
it is not inherited.

### 2.3 Minimum space — the only column where a plausible method gives a wrong answer
DRC reports a gap only when it breaks a rule, so "0 clearance violations" means *min space ≥ the rule*.
`S-*` raise the floor to 0.30 mm in a copy and read KiCad's own `actual` value off every violation; the
smallest actual found is the real minimum.

| board | own clearance rule | smallest actual found | pairs reported | self-check |
|---|---|---|---|---|
| DA | 0.125 | **0.1250** (1 pair at exactly 0.1250, 71 at 0.1255) | 509 | equals the rule, so nothing hides below it |
| ESC | 0.200 | **0.2000** (372 pairs) | 414 at 0.250 rules | equals the rule |
| CS | 0.100 | **0.1000** (6 pairs at exactly 0.1000) | 513 | equals the rule |

All three land exactly on their own floor. A probe that over-reported would have found something
*below* the rule (a hidden DRC miss); one that under-reported would have found something above it.
**The ESC's 372 pairs at 0.2000 are 371 intra-footprint pad gaps plus one other** — the pad-gap count
(371) is the number that matters at 4 oz and is carried from `fab-esc-rules-first` and
`fab-esc-4oz:§4`, reproduced here as the concentration of the population at one exact value.

### 2.4 Minimum drill — via and PTH pad reported separately, because on the ESC they differ by 0.1 mm
`M-*` + `out/pth_drill_hist.json`:

| board | min **via** drill | min **pad** drill | pad population at that size |
|---|---|---|---|
| drone-arm | **0.100** (the illegal class) | 0.200 | 18 × 0.200 + 4 × 0.600 = 22 PTH pads |
| ESC | **0.300** | **0.200** | **110 pads at 0.200** of 223 PTH pads |
| Code-SDR | 0.200 | 0.200 | 73 × 0.200 of 128 PTH pads |

A via-only count reports "0 below 0.2" on a board that contains 110 sub-0.3 mm holes — which is exactly
why v1's ESC cell and this one disagree (§9.2).

### 2.5 Minimum annular ring, with its population named
Ring = `(min(front, back diameter) − drill) / 2`, per via **and** per PTH pad. `PCB_VIA.GetWidth()` with
no layer argument asserts and hangs the process in 9.0.7 (measured: it printed
`PCB_VIA::GetWidth called without a layer argument` and never returned), so every diameter is read per
layer.

| board | via rings (count) | min PTH ring | owner |
|---|---|---|---|
| drone-arm | 0.100 (21) · 0.150 (28) · 0.175 (281) · 0.200 (6) | **0.150** | `U41.17` |
| ESC | 0.150 (16) · 0.175 (12) · **0.200 (1,962)** | **0.125** | `U204.11` |
| Code-SDR | 0.100 (53) · 0.125 (1,013) · 0.150 (6) · 0.300 (13) | 0.150 | `U10.57` |

The through-via population on drone-arm bottoms out at 0.150 — what a 1 oz house builds happily. Its
0.100 is a property of the vias that are illegal anyway, not a second defect.

### 2.6 Non-through vias BY SPAN — never a diameter-derived total
Classification is `GetViaType()` **plus the measured layer pair**: through = F.Cu→B.Cu; blind = touches
exactly one outer layer; buried = touches neither. Drill is never used to classify.

| artefact | vias | through | **blind** | **buried** | non-through | declared type | old 0.2 mm gate says |
|---|---|---|---|---|---|---|---|
| drone-arm repo original | 341 | 305 | 26 | 10 | **36** | 33 micro + 3 blind | 33 |
| **drone-arm best (fanout7)** | 336 | 321 | **11** | **4** | **15** | 14 micro + 1 blind | 14 |
| ESC rev_b | 1,990 | 1,990 | 0 | 0 | **0** | all THROUGH | 0 |
| Code-SDR V2 | 1,085 | 1,085 | 0 | 0 | **0** | all THROUGH | 0 |

The 15, layer pair by layer pair (`out/measure_da_best.json → via_table`):

```
0.100  F.Cu → In1.Cu   blind   5
0.100  F.Cu → In2.Cu   blind   2      <- micro by type, blind by span
0.100  In1.Cu → In2.Cu buried  4
0.100  In1.Cu → B.Cu   blind   1      <- micro by type, blind by span
0.100  In2.Cu → B.Cu   blind   2
0.300  In2.Cu → B.Cu   blind   1      <- legal drill, still sequential lamination
```

**Four distinct layer pairs plus one buried pair ⇒ at least three lamination stages.** The old 0.2 mm
diameter gate sees 14 of 15 and under-reports by exactly one — the 0.300 mm blind, whose only defect
is its span (`fab-da-package7/REPORT.md:60-76`, reproduced here).

### 2.7 Unconnected — the tool is named, and whether it is at its cap
| board | pcbnew ratsnest | kicad-cli | cap status |
|---|---|---|---|
| drone-arm | **0** | 0 | both far below any cap, they agree ⇒ the zero is evidence |
| ESC | **1,542** | **499** | 499 is `kicad-cli`'s hard cap ⇒ a truncation, not a measurement |
| Code-SDR | **0** | 0 | below cap |

A zero below a tool's cap is evidence; a number exactly at a round cap is a truncation. This is the
line the programme learned the hard way (`AGENT_BOARD.md:541-547`) and it is enforced in §1.

**The ESC's 1,542 is consistent with how little route exists**, and the populations are now measured
rather than inherited (`out/esc_net_census.json`):

| quantity | value |
|---|---|
| nets / nets that own pads | 667 / 666 |
| **nets with ≥2 pads — the routable population** | **556** |
| nets with ≥1 track segment | **16 = 2.88 % of 556** |
| nets with vias but no track (fan-out dropped, not connected) | 38 |
| **nets with ≥2 pads and no copper at all** | **540 of 556** |
| segments / vias / track length | 154 / 1,990 / **628.27 mm** |

Both v1 figures reproduce exactly: **2.88 % routed** and **540 of 556**. The 612-vs-540 difference is
only the population — 612 is "of all 666 pad-bearing nets", 540 is "of the 556 that need a route".

### 2.8 DRC — the rule set is part of the number
| board | rule set | violations | severity | unconnected in the same run |
|---|---|---|---|---|
| drone-arm | the board's **own** rules | **7** (`via_diameter` ×7) | 7 error | 0 |
| drone-arm | **span gate** (`A.Via_Type != 'Through'`) | **22** = 14 `microvia_drill_out_of_range` + 1 `drill_out_of_range` + 7 `via_diameter` | 22 error | 0 |
| ESC | **4 oz @ 0.250 mm** (9 rules) | **523** = 414 clearance + 70 annular + 16 via_diameter + 16 dangling + 4 track + 3 neck | 504 error / 19 warn | 499 |
| ESC | **4 oz @ 0.200 mm** | **102** = 70 annular + 16 via_diameter + 16 dangling | 86 error / 16 warn | 499 |
| ESC | **0.200 mm + 0.150 mm ring** | **16**, all dangling vias — i.e. the route itself | 0 error / 16 warn | 499 |
| Code-SDR | its **own project rules + `.kicad_dru`** | **222** = 199 `lib_footprint_mismatch` + 13 `via_dangling` + 10 `track_dangling` | **0 error / 222 warning** | 0 |

The ESC's 523 and 102 reproduce `fab-esc-rules-first/REPORT.md:20-23` and `esc-routability` to the
type, in my own run, under the same rule files copied in unmodified.

**The drone-arm 7 is a debt the fan-out created** — the composed board read 0. The fan-out placed
0.4 mm via pads where the project's own rule demands 0.6 mm. It is a project-config violation, not a
fab limit, and it is counted rather than smoothed.

### 2.9 Gerber package — three states, and the one that looks complete and is not

| board | files | holes | outline | verdict |
|---|---|---|---|---|
| drone-arm | 11 Gerbers, `.gbrjob`, **7 Excellon**, 7 drill maps, 1 pos (161 rows) | **360 drills + 4 slots = 364 hits**; **5 blind/buried files carrying 15 holes** | **140.000 × 100.000** (140.15 incl. stroke) | complete, revision-stamped `B`, **SENDABLE = NO** — the drill set is HDI (`fab-da-package7/REPORT.md:140-188`) |
| ESC | **0** | — | — | nothing exists anywhere under `hardware/esc` |
| Code-SDR | 11 Gerbers + `.gbrjob` + **2 Excellon** | **1,215 hits = 1,213 drills + 2 slots** (PTH 1,211 + NPTH 2) | **101.700 × 101.700** incl. stroke; job 4 layers, 1.6 mm, ENIG, `Revision 2.1` | complete and frame-free, **exported here** because the repo carries no package |

Two counting facts that a single "holes" number hides, both measured this run:

1. **The 0.600 mm tool carries slots, not drills** — 4 slots on drone-arm and 2 on Code-SDR, 0 drills on
   either board. A validator that adds `G85` lines into a drill count over-counts by exactly those.
2. **Code-SDR's 1,215 = 1,085 vias + 128 PTH pads + 2 NPTH** and reproduces from my own export; the
   programme's `fab-cs-drc/fabpkg/` declares a 0.600 mm tool, drills nothing with it, and is 2 holes
   short (`fab-checklist/REPORT.md:166`). Send the 1,215 package.

The drone-arm repo ships **14 artefacts** (11 `.gbr`, 2 `.drl`, 1 `.gbrjob`) — measured — and they are
the **rev_a** board: its own job file reads **`Size 75.05 × 50.05`**, **`Revision "rev?"`**,
**`Finish "None"`**, and v1 measured the plotted extents at **288.397 × 204.238 mm** because the A4
worksheet frame is plotted into all 11 layers (`fab-checklist/REPORT.md:§2.10`). That is a different
board, in a frame, with no finish and no revision. It is not an order candidate at any revision.

### 2.10 Revision stamp
`GetTitleBlock().GetRevision()` + the job file: drone-arm **`""`** (the package says `B` only because
that unit patched its own copy — `title_block_rev_B.patch`, 5 added lines, 19 carriers,
`fab-da-package7/REPORT.md:117-121`); ESC **`""`**, and no silk revision text anywhere on the board;
Code-SDR **`2.1`** in the title block **and** in `cs-job.gbrjob → GeneralSpecs.ProjectId.Revision`.

### 2.11 Panel outline and area
Edge polygon area, from `GetBoardPolygonOutlines().Area()` (nm², so `/1e12` is mm²):

| board | Edge_Cuts | polygon area | bbox incl. stroke | panelisation |
|---|---|---|---|---|
| drone-arm | **140.000 × 100.000** | **140.00 cm²** | 140.15 × 100.15 | none — 1-up, no rails, no breakaways |
| ESC | **173.950 × 283.080** | **491.732 cm²** | 173.95 × 283.08 | none — 1-up |
| Code-SDR | **101.600 × 101.600** | **103.23 cm²** | 101.70 × 101.70 | none — 1-up |
| drone-mech | not a panel | — | — | — |

**The ESC's compaction answer belongs here and nowhere else.** The owner asked for "as compact as
possible". The only compaction delivered is **370.119 cm² (−121.613 cm², −24.73 %)** and it is
**UNSAFE**: the 60 A phase corridor on F.Cu falls from **7.51 mm to 1.50–3.50 mm** against a **6.991 mm
per-layer** requirement (2.0× to 4.7× short), BATP fails even as a summed two-layer pour
(**11.00 against 13.981**), and its DRC is **935 against 523** at 0.250 with **41 shorts and 81 mask
bridges** that the original does not have (`esc-routable2/REPORT.md:20-36`, `:111-126`). Its pcbnew
unconnected is **1,620** (+78, and it carries **8 stale segments**).

The honest floor for today's BOM is **370 cm²** — which is why the target was right and the placement
was wrong (`esc-compaction-verify/REPORT.md:22-30`): **316 cm²** needs the M5 lugs replaced, **255 cm²**
is the ceiling if the phase pours also use B.Cu. There is room at 370 cm²; there is no room with a
1.50 mm phase trace.

**Single-sided is met, measured, and it was never the problem.** `out/side_census.json` tests every
footprint's pad layer set: **ESC 644 front-only + 43 with pads on both sides, 0 with copper only on
B.Cu** (the 43 are through-hole lugs and thermal pads, which are supposed to be on both). The same test
gives **0 back-only** on drone-arm and on Code-SDR. So the owner's single-sided rule is satisfied by the
board as it stands, and the compaction was an area exercise — not a side swap.

### 2.12 Surface finish
`(copper_finish "ENIG")` in all three board files, `"Finish": "ENIG"` in the drone-arm job file and in
my Code-SDR job file. The stale rev_a job file says `"Finish": "None"` — a third reason it cannot be the
order.

### 2.13 Orderable — the verdict column
Column 14 is not a new measurement; it is the reading of §1 under the definition in §0. A board is
**YES** only if every blocker in §4 is absent **and** a sendable package exists today.

---

## 3. drone-mech — the fourth row, in its own units

**Provenance:** every volume is a native OpenCascade boolean (`BRepAlgoAPI` via CadQuery 2.7.0 / OCP
7.8.1.1 on `C:/Program Files/Python312/python.exe`). Nothing is a solver, surrogate or estimate.
`fab-dm-final/check_report.py` re-derives **95/95** asserted numbers and exits non-zero on drift.

### 3.1 Interference, and what the eight pairs actually are

| class | pairs | volume mm³ |
|---|---:|---:|
| genuine design clash | **6** | **1,250.769445** |
| modelling artefact (pushrod representative) | **2** | **4.534020** |
| intentional contact | 0 | 0 |
| **as the board carries it** | **8** | **1,255.303466** |

The board's `1,255.3034` was never a measured sum — it was the composition `2,373.4904 − 1,118.186958`.
The direct sum of the eight exact pair volumes is `1,255.303466`, **2.3563 × 10⁻⁵ mm³** above that
composition (relative 1.88 × 10⁻⁸): the rounding of two aggregates, not a geometric difference
(`fab-dm-final/REPORT.md:79-84`).

### 3.2 Classification, and the single cause

| pair | volume mm³ | class | why |
|---|---:|---|---|
| elevon ↔ motor can envelope ×2 | 409.833027583 / 409.833022484 | **genuine** | the plate occupies space the Ø36 × 70 can and Ø5 × 17 shaft must have; the envelope is `spec:302` tier |
| elevon ↔ nozzle shell ×2 | 120.247564436 / 120.247564437 | **genuine** | a moving surface passes through a fixed structural shell (`r 38.978…41.000`) |
| elevon ↔ fuselage 42_6 ×2 | 95.304133195 / 95.304133199 | **genuine** | the plate passes through the side wall; caught by **every** 42_6 variant, so not a Boolean artefact |
| elevon ↔ pushrod ×2 | 2.267010111 / 2.267010118 | **modelling artefact** | a Ø2 × 38 mm rod **6.000 mm clear of its own servo mount**, contacting the horn only as a **0.831215 mm³** corner clip, ending **21.6915 mm past the plate in free air**; the generator calls it "representative" (`phase15_generate_geometry.py:1010`) |

All six genuine pairs have **one** cause: the elevon root stands at `|x| = 55.250` (`r = 11.250` from
the duct axis) — 6.750 mm inside the can's `r 18`, 31.25 mm inside the duct bore, and 2.649 mm through
the fuselage side wall at `|x| 90.586…93.235`. It is **not** an undersized relief (that pair was
measured at 559.093479 and the executed cove took it to 0.000000000) and **not** a hinge-axis error
(the mid and tip knuckles measure 0.000000).

### 3.3 ZERO, and the tail-interface change it costs

**ZERO IS REACHED as a measured state: 0 pairs / 0.000000 mm³ genuine**, on a copy, by three changes:

1. the elevon moves **+38.485 mm outboard** — root 55.250 → **93.735**, tip 204.750 → 243.235, **span
   149.5 mm and chord 40 mm unchanged**;
2. the wing's aft-chord cove is extended over the new band to `z 157.000`, removing
   **9,753.948578 / 9,753.946712 mm³** per side;
3. the pushrod must be re-drawn as a real link — compulsory after (1), and its **4.010114 mm³** of
   placeholder is the only thing the sweep still sees.

**What it costs, named:** a tail-interface change. The hinge line moves with the plate, the horn goes
from `|x| 121…139` to `159.485…177.485`, and the servo mount stays at `|x| 125` — now **34.485 mm
inboard of the horn**. **No duct-module change and no span loss.**

The alternative was measured and **not** executed: a **37.985 mm root trim** clears the same three
structures but costs **25.41 % of the flying surface** (span 149.5 → 111.515), and at that length it is
only *tangent* to the wing (9.81 × 10⁻⁷ mm³). A quarter of the wing for one machining edit is the
expensive choice.

### 3.4 What the zero does NOT buy — and why this row is still refused

1. **The change is not in the design intent.** It was executed on copies for measurement; nothing under
   `repos/` was written (`fab-dm-final/REPORT.md:390-391`). The design of record still carries the
   eight pairs.
2. **The solid is not manufacturable.** The 42_6 export is **4 disjoint solids over 77.165 mm**, and a
   **+97 g Boolean repair is a prerequisite** before any of the body work describes a part.
3. **The outboard wing is a loft artefact.** Outboard of `|x| 204.750` the solid carries up to
   **+109.394 mm** of trailing edge beyond its **own** station table, totalling **41,775.812 mm³
   (3.09 %)** per side. The moved plate's space is real; the fixture around it is not
   (`fab-dm-final/REPORT.md:307-327`).
4. **No manufacturing package exists**: 205 STEP/brep, no drawing, no ply book, no revision.

Controls so a zero cannot be a dead detector: the same code reports **559.093479** against the uncut
wing, and **2,290.930692** for the moved plate without the cove extension, and an 83-file bbox screen
(81 screened, 2 skipped aggregates) found **no ninth pair**.

---

## 4. The two settled constraints, and what each one costs

### 4.1 NO HDI — and therefore drone-arm is blocked at 15, with zero reachable by local edit

HDI is classified by **span** (through / blind / buried / micro), never by drill diameter. Under that
rule: **drone-arm 15, ESC 0, Code-SDR 0.**

**drone-arm's 15 is now a proved impossibility for the edit class "via edit + local copper move".**
Nine distinct conversion strategies were built; all 15 candidates went through KiCad's own DRC one at a
time with a zone refill: **kept 0, dropped 15** (`fab-da-fanout3/gated.kicad_pcb.gate.json`).

| the six measurements that close it | value |
|---|---|
| legal through-via pad at each site, sweeping ±0.50 mm on a 0.01 mm grid | **0 of 15** reach 0.400 mm |
| best `pad_max` anywhere in reach | **0.3754 mm** (`/SENS_SCLK`) — 24.6 µm short; `/RF_MISO` 0.3200 mm, 80 µm short |
| sites where foreign copper sits **on** the point (`pad@P ≤ 0`) | **10 of 15** |
| sites that cannot host even a 0.300 mm pad | **12 of 15** |
| converting all 15 in place with the board's own rules | **121 violations** (68 clearance, 20 shorting, 22 via_diameter, 6 hole, 3 mask, 2 co-located), 0 unconnected |
| re-escape that passed the *connectivity* guard | 6 of 15 — **all six then failed DRC on refill** (58 violations) |

The obstruction is a **routing** obstruction, not a via one: 11 of 15 sit inside the **U10 QFN-80 0.4 mm
pitch pad field** (adjacent pads 0.3000 mm edge-to-edge, pads cannot move), and 4 need to clear an
inner-layer bus whose tracks are all at the 0.125 mm floor so that none can move alone. **The zero needs
a U10 fan-out re-escape — a rip-up, not a nudge.** Every one of the 15 is load-bearing: removing any one
leaves exactly 1 unconnected item.

**One owner decision sits inside this constraint, and only one:** dropping the board's
`m_MinThroughDrill` from 0.200 to 0.150 (a standard 4-layer mechanical drill at every fab surveyed in
this programme, so still non-HDI) converts **2 of 15 and no more** (`/SENS_SCLK`, `/RF_MISO`). It is a
rule change, so it is not mine to make.

### 4.2 4 oz on the ESC only — and no surveyed fab makes 0.200 mm at 4 oz

Eight fabricators surveyed against published capability tables, quotes stored verbatim
(`fab-4oz-capability/REPORT.md:37-41`, `:53-91`): **no. Categorically no, from any of the eight, in any
service tier.**

| fabricator | 4 oz stated | min track @ 4 oz | min space @ 4 oz | min ring |
|---|---|---|---|---|
| PCBWay | explicit | 0.330 | 0.330 | 0.150 (generic) |
| Multi-CB (DE) | explicit 140 µm | 0.300 std / 0.250 special | 0.300 / 0.250 | 0.300 / 0.200 |
| Bay Area Circuits | explicit | 0.305 std / 0.279 adv | 0.305 / 0.305 | 0.127 (generic) |
| LeitOn (DE) | explicit 140 µm | 0.300 | 0.400 | 0.250 |
| Advanced Circuits | no — stops at 3 oz | 3 oz: 0.229 | — | — |
| JLCPCB | no — heavy weights 2-layer only | 4-layer max 2 oz | — | — |
| Eurocircuits | no — ends at 3 oz | 3 oz: 0.250 | 0.250 | 0.125 |
| OSH Park | no — heaviest service 2 oz | — | — | — |

**Re-fetched live for this sheet** (LeitOn, rigid design rules, the `140 µm` row only):

| LeitOn 140 µm row | standard (online) | on explicit request |
|---|---|---|
| smallest PTH drill (finished) | **not possible** | **0.30 mm** |
| smallest annular ring | **not possible** | **0.25 mm** |
| smallest track | **not possible** | 0.30 mm |
| smallest space | **not possible** | 0.40 mm |
| barrel plating | not possible | min 25 µm |

Source: <https://www.leiton.de/technologie-starre-leiterplatten.html> (fetched 2026-11-16; rows
"Kleinste Bohrung 140µm (Enddurchmesser)" and "Kleinster Restring 140µm").

**Consequences, measured on this board:**

1. **371 pad gaps at exactly 0.2000 mm** inside 9 footprints — U201 (QFN-80 P0.4), 6 × LQFP-48 P0.5,
   J202/J203 (USB-C). No placement or routing edit can make them 0.25-compliant; the pads are the
   package.
2. **110 PTH pads at 0.200 mm drill** against a 0.30 mm finished-hole floor at 140 µm. On a 4-layer
   non-HDI board with a standard mechanical drill window (0.2–0.3 mm), this one is **new since v1** and
   is not fixed by the three package changes — the 110 have never been mapped to their footprints.
3. **Every one of the 1,990 vias fails a 0.25 mm 4 oz ring** — the largest ring on the board is
   0.200 mm. A LeitOn-class 4 oz build needs every via pad grown **0.80 → 0.90 mm**.
4. Which leaves the three doors, unchanged and costed (`fab-esc-rules-first/REPORT.md:20-33`):

| rule set | violations | what it means |
|---|---:|---|
| 4 oz @ 0.250 | **523** | footprint-bound; not a routing job |
| 4 oz @ 0.200 | **102** (−421) | escapes fit with 0.05 mm to spare, but **no surveyed fab will make this pattern class** |
| 4 oz @ 0.200 + 0.150 ring | **16**, all dangling vias | the entire remaining delta *is* the route |

So: **Option A** drop the ESC to 2 oz (geometry already 2 oz-compliant — zero work, loses the current
capacity 4 oz was chosen for); **Option B** keep 4 oz and change 3 packages (real work, keeps the
capacity, plus the unknown 110-pad mapping); **Option C** a fab's written acceptance of 0.200 mm at
140 µm — which LeitOn's own page refuses, so it would have to be a bespoke process agreement. There is
no fourth door.

**And 60 A is repo-stated, not measured.** `REV_B_ARCHITECTURE.md:18` states 60 A continuous per motor
channel; no current waveform exists in the repo. At 50 A every requirement above softens
proportionally, so this number is worth confirming before the placement is redone.

---

## 5. What would stop this order today

Only true blockers: a wrong board, a refused quote, or guaranteed rework. Ordered by
cost-to-fix-after-fab.

| # | board | blocker | why it stops the order | fix class | measured size |
|---:|---|---|---|---|---|
| 1 | **DA** | **15 non-through vias** (11 blind + 4 buried; 14 at 0.100 mm) | no 4-layer non-HDI house can drill 0.100 mm or build a 1→4-family blind/buried set without sequential lamination; the package ships **5 blind/buried Excellon files carrying all 15** | **MOVE** | zero proved impossible for via edit + local copper move; needs a **U10 fan-out re-escape** (11 of 15 inside a 0.4 mm pitch pad field, 4 behind an inner-layer bus at the 0.125 mm floor) |
| 2 | **DA** | **no ESC command path in copper** | the board cannot command an ESC; fabricating it guarantees hand rework on a 0.4 mm-pitch QFN | **MOVE** | measured: **176 nets of which 64 are auto-generated**; `J` refs are `J1, J2, J10, J30, J40` — **no J60–J66**; `U10.43…48` all on `unconnected-(U10-GPIOxx)` nets |
| 3 | **DA** | **revision field empty, and the repo's only package is rev_a** | a fab reading `hardware/main` gets a **75.05 × 50.05 mm** board in an A4 frame with `Finish: None` and `Revision: "rev?"` | **PARAM** | apply `title_block_rev_B.patch` (5 lines); the rev_b package already exists (364 hits, 140.000 × 100.000, `B`, 19 carriers) but is **not sendable until #1** |
| 4 | **ESC** | **1,542 unconnected** — and the 499 everyone quotes is a tool cap | 2.88 % of the route exists (154 segments, 628.27 mm); 540 of 556 nets carry no copper, so there is nothing to fabricate | **MOVE** | finish the route. Free now, a 540-net rip-up later: **adopt the 4 oz rule set first** |
| 5 | **ESC** | **4 oz cannot be built from these packages** | 371 pad gaps at 0.2000 mm, **110 drill holes at 0.200 mm** and every via ring at ≤ 0.200 mm, against a published 140 µm floor of 0.30 mm hole / 0.25 mm ring | **OWNER DECISION** | 523 violations at 0.250; 102 at 0.200; 16 at 0.200 + 0.150 ring. Doors: 2 oz / 3 package changes / a written fab waiver |
| 6 | **ESC** | **no package and no revision marking at all** | nothing to export, nothing to stamp | **PARAM** | one export once #4 exists, plus a title-block revision |
| 7 | **ESC** | **do not ship the compaction** (if that placement is adopted) | it carries 60 A at **1.50–3.50 mm** where 6.991 mm is needed, commits **41 shorts + 81 mask bridges**, and reads **935** violations against 523 | **REJECT ARTEFACT** | 370.119 cm²; recover by moving the DC-link stack out of the FET-column gaps — **105.8 mm² per channel, 6.35 cm² board-wide = 5.2 %** of what the compaction won |
| 8 | **DM** | **the zero is not in the design intent** | the 0 pairs exist only on evidence copies; the design of record still has 8 pairs / 1,255.303466 mm³ | **MOVE + REV** | +38.485 mm station change, 9,753.95 mm³/side cove, pushrod re-draw; then `42_6` needs a **+97 g Boolean repair** (4 disjoint solids over 77.165 mm) |

**Not on this list, deliberately:** every Code-SDR warning (§6.1), the CS annular-ring quote line, the
CS 101.7 mm price tier, the CS package not being checked in, the drone-arm 7 `via_diameter` items, the
DA stackup being 1.580 mm over copper, the ESC's 16 dangling vias, and every assembly gap in §8.

---

## 6. What is cosmetic and should not stop an order

Use this list to end an argument. Each item is real, measured, and irrelevant to a fabrication order.

| # | item | board | why it is cosmetic |
|---:|---|---|---|
| 1 | **222 DRC items** | CS | **all severity warning, 0 error**: 199 `lib_footprint_mismatch` (a board-vs-library comparison; 0 of 373 footprints differs in any pad node or 3-D model), 13 `via_dangling`, 10 `track_dangling`. Fab houses do not read warnings (`fab-cs-drc/REPORT.md:§2.2-3`) |
| 2 | **0.100–0.125 mm annular ring** | CS | below a 0.15 mm published house floor but above the board's own 0.10 mm rule. This is "pay for the tighter tolerance", which costs less than a redesign — a quote line, hence WAIVED |
| 3 | **101.70 mm vs the 100 mm panel tier** | CS | 1.7 mm of **price class**, not a process limit. The next tier up is cheaper than redrawing a 101.6 mm board |
| 4 | **package not in the repo** | CS | the repo carries **0** gerber/drill/job files; a frame-free package with **1,215 holes** and `Revision 2.1` exports in one command, and was exported here |
| 5 | **7 `via_diameter` errors** | DA | 0.4 mm via pads against the project's own 0.6 mm floor — a **0.1 mm ring**, which some houses accept. A project-config debt the fan-out created, not a fab limit, and the board is refused for blocker #1 anyway |
| 6 | **stackup 1.580 mm over copper vs 1.60 declared** | DA | −1.25 %, inside a normal ±10 % laminate tolerance. One sentence on the fab drawing |
| 7 | **schematic-parity items (161 library-link strings)** | DA | not in the gerber set; a fab house never sees them (`fab-readiness/REPORT.md:§3`) |
| 8 | **16 `via_dangling`** | ESC | vias dropped, tracks not yet drawn — they get connected by the route blocker #4 requires. Zero action now |
| 9 | **0.0525 mm inner layers (1.5 oz)** | ESC | an inner-layer lamination input the shop controls; no customer-facing geometry and no rule depends on it |
| 10 | **the 8 stale segments** | ESC | `esc-placement` moved 687 footprints and carried the old route with them: pcbnew unconnected went 1,542 → 1,620 while `kicad-cli` stayed at its 499 cap. They are **routing noise, not a design defect** — and on the compacted board they are what the 41 shorts and 81 mask bridges are made of |
| 11 | **0 fiducials, 0 test points, no rails, no assembly drawing** | all three | these stop an **assembly PO**, not the etch order (§8) |
| 12 | **no silk revision on CS** | CS | the title block and `cs-job.gbrjob` both carry `2.1`; silk artwork is not the revision control of record |
| 13 | **41,775.81 mm³ phantom outboard loft** | DM | it does not touch the moved plate; it matters to anyone mounting hardware out there, not to the interference zero |

---

## 7. One line per board, unforgiving

**drone-arm main rev_b — NOT ORDERABLE.** *15 non-through vias* (11 blind + 4 buried, 14 at 0.100 mm)
in 5 blind/buried drill files; the zero was **proved impossible** for the edit class, so the fix is a
U10 fan-out re-escape, not a via edit. Behind it: no ESC command path (`U10.43–48` on auto nets, no
J60–J66), an empty revision field, and a repo whose only package is the rev_a board.

**ESC rev_b — NOT ORDERABLE.** *1,542 unconnected* (pcbnew; 499 is a tool cap) and no package at all —
and when it is routed, **4 oz cannot be built from these packages**: 371 pad gaps at exactly 0.2000 mm,
110 holes at 0.200 mm against a 0.30 mm 140 µm floor, and all 1,990 via rings at ≤ 0.200 mm against
0.25 mm. The compaction that was supposed to buy area spent the power path: *1.50–3.50 mm against
6.991 mm*.

**Code-SDR V2 rev 2.1 — ORDERABLE, bare board, today.** *0 errors, 0 unconnected, 1,215 holes*, a
frame-free package stamped `2.1`, a finish and a thickness that closes. Two quote lines, neither a
redesign: the 0.100–0.125 mm ring and the 0.100 mm track/space at 1 oz.

**drone-mech airframe — NOT READY, and for once not because of interference.** *0 pairs /
0.000000 mm³* genuine is real and measured — but it costs a **+38.485 mm tail-interface change** that
lives on evidence copies, and the solid it sits in is **4 disjoint bodies** with **41,775.81 mm³** of
phantom loft outboard.

---

## 8. Companion — what an *assembly* PO still needs (does not block the etch)

| item | DA | ESC | CS |
|---|---|---|---|
| BOM for this board | `REV_B_BOM.csv`, 172 data rows, 0 blank MPNs | same file covers the ESC (F701) | **missing** — 373 rows / 129 lines exported by `fab-cs-assembly`, **373 of 373 rows have no MPN** |
| pick-and-place | package7 `.pos`, 161 rows | none | 373 rows (371 with `--exclude-dnp`) |
| fiducials | 0 | 0 | **0 in the repo** (3 global + 6 local exist only as that unit's copies) |
| test points | 0 | 0 | **0 in the repo** (18 probe sites named, copies only) |
| panel / rails | none | none | none |

CS assembly is blocked by **MPNs, a sourcing task**, not by copper. DA and ESC have no fiducials or test
points either, which is an assembly decision at the next revision, not a reason to hold an etch.

---

## 9. Charge summary, and what changed since v1

Counted from §1 by `check_report.py` (which reads the markdown table, not a claim in prose):

| board | PASS | FAIL | WAIVED | counted cells | orderable |
|---|---:|---:|---:|---:|---|
| drone-arm main rev_b | 7 | 6 | 0 | 13 | **NO** |
| ESC rev_b | 5 | 8 | 0 | 13 | **NO** |
| Code-SDR V2 | 12 | 0 | 1 | 13 | **YES** |
| drone-mech airframe | 2 | 3 | 8 | 13 | **NO** |
| **all four** | **26** | **17** | **9** | **52** | **1 of 4** |

### Corrections and additions since v1

1. **drone-arm went 17 → 15**, and the zero is now *proved impossible* rather than pending. v1's
   headline number ("24 remain... 17 HDI vias") is superseded by the measured best artefact.
2. **v1's ESC minimum-drill cell was wrong at 4 oz.** It read "0.300 via / 0.200 pad — PASS" because
   it measured the vias. At 140 µm the floor is a **0.30 mm finished hole** (LeitOn, fetched today), so
   the **110 pads at 0.200 mm** are a second blocker. That cell is now **FAIL**, which moves the ESC
   tally from 6/7 to **5/8**.
3. **499 is a cap value; 1,542 is the measurement.** v1 carried both without adjudicating. This sheet
   names pcbnew as the instrument and 499 as the truncation.
4. **drone-arm's DRC is 7 errors, not 0.** The fan-out created 7 `via_diameter` items the composed
   board did not have. Under the span gate the count is **22 = 15 HDI + 7**, not "33".
5. **The 0.2 mm diameter gate is retired as a count.** It reports 14 where the truth is 15 on
   drone-arm — the 0.300 mm blind via is the one it cannot see.
6. **The 4 oz answer is a drill answer as much as a trace answer.** v1 said "4 oz needs 0.200 mm holes
   at 0.30 mm minimum" as a board line item; it is now measured (110 pads) and sourced (LeitOn 140 µm
   row), and the ring floor is 0.25 mm — which fails **all 1,990 vias**.
7. **The ESC's compacted 370.119 cm² is UNSAFE and must not be ordered.** The floor for today's BOM is
   370 cm²; 316 needs a lug change; 255 is the ceiling on two faces. Area was never the obstruction —
   copper width was.
8. **drone-mech reached zero in the genuine class**, with the artefact class stated and excluded, and
   the cost named as a tail-interface change.
9. **A brief-level correction, measured:** the ESC has **36 FETs = 2 per phase across 18 phase nets**
   (6 motor channels × 3 phases), i.e. **6 FETs per motor channel**, not "6 FETs per phase across 6
   phases". Basis: 18 `_PHASE_A/B/C` nets on the board; `REV_B_BOM.csv` gives 36 ×
   `IPTC014N10NM5ATMA1`, 24 × `CSS4J-4026R-L500F` (0.5 mΩ 1 % 5 W) and 7 × `SM8S51A`. The 12S /
   50.4 V bus against a 51 V standoff is consistent (`REV_B_ARCHITECTURE.md:16`, 50.4 V max; `REV_B_BOM.csv` SM8S51A row).
10. **A package can be complete and still be wrong, twice:** the CS `fabpkg/` is 2 holes short of its
    own board, and the 0.600 mm tool carries **slots, not drills**, on both CS and DA.

---

## 10. UNVERIFIED — what this sheet does not know

1. **Whether any heavy-copper house will accept 0.200 mm at 140 µm in writing.** LeitOn's published row
   says no; PCBWay lists 0.330. This is a quote, not a measurement.
2. **The mapping of the 110 × 0.200 mm PTH pads to their footprints.** It has never been done, and it
   decides whether Option B (three package changes) actually clears them.
3. **Whether a real per-phase current is 60 A.** Repo-stated (`REV_B_ARCHITECTURE.md:18`), never
   measured. Everything in §4.2 scales with it.
4. **DFM etch compensation** on the CS 0.100/0.125 mm ring after the house's own compensation. KiCad
   does not model it.
5. **Solder-mask dam width** between the 0.4–0.5 mm pitch pads on DA and ESC. Every board declares
   `solder_mask_min_width 0.05`; only the fab knows what its process yields.
6. **Every impedance number.** Two 2-D finite-difference solves exist, no measurement does, and the
   coupon that would settle the coplanar-pour question is designed but **not ordered**
   ($54.24 against the $60 cap; **$0 committed to date**). The cap does not bind any board on this
   sheet.
7. **Panelisation cost/feasibility** for any board — no panel drawing, no quote.
8. **drone-mech's 0.500 mm clearance** is the drawing's own `ELEVON_GAP`, not a tolerance stack: no
   lamination tolerance, hinge slop or thermal growth is in it.

---

## 11. Artefacts and reproduction

| file | what it is |
|---|---|
| `REPORT.md` | this sheet |
| `measure.py` → `out/measure_{da_best,da_repo,esc,cs}.json` | every §1 quantity, per board, from `pcbnew` on a copy (never saved). Also emits the span census, ring histograms, stackup and title block |
| `drc_run.py` → `drc/*/drc.json`, `out/drc_summary.json` | **all eight DRC runs** behind §1 and §2.8: own rules, span gate, 0.30 mm space probe, 4 oz 0.250, 4 oz 0.200, CS own rules. Runtime 3.1–86.3 s, exit 0 on all |
| `drill_census_v2.py` → `out/drill_census.log` | Excellon census with **drills and G85 slots separated**, for package7 and my CS export |
| `out/side_census.json` | single-sided check: DA 158 front-only + 7 both, ESC 644 + 43, CS 354 + 19, **0 back-only on every board** |
| `out/pth_drill_hist.json` | PTH pads by drill: ESC **110 × 0.200** of 223; CS 73 × 0.200 of 128; DA 22 total |
| `out/da_conn_census.json` | 176 nets, **64 auto-generated**, `J` refs `J1, J2, J10, J30, J40`, `U10.43–48` unconnected |
| `out/esc_net_census.json` | 667 nets / 666 with pads / **556 with ≥2 pads**, of which **16 carry a segment (2.88 %)** and **540 carry no copper**; 154 segments, 1,990 vias |
| `out/cells.json` | the machine-readable form of §1 (used by the checker) |
| `check_report.py` → `out/check_report.log` | verifies 4 data rows of 15 cells (label + 13 verdict columns + orderable), no empty cell, no `TBD`, exactly one verdict per column, and that §9's tally equals the table's |
| `probe_speed.py` | the bisect that located the `GetWidth` hang: loads the board, then times load / tracks / vias / bbox / outline / connectivity / footprints / pads separately |
| `boards/` | byte copies of all four boards + Code-SDR's `.kicad_dru`, `fp-lib-table` and `CodeSDR.pretty` (a DRC run outside its project directory invents violations — `fab-checklist/REPORT.md:§2.3`) |
| `export_cs/` | my Code-SDR package: 11 Gerbers, `.gbrjob`, PTH + NPTH Excellon, 2 drill maps |

```powershell
cd E:/engineering-portfolio-audit/evidence/fab-checklist-v2
& "C:/Program Files/KiCad/9.0/bin/python.exe"  measure.py                 # 4 boards, ~2 min
& "C:/Program Files/Python312/python.exe"      drc_run.py                 # 8 DRC runs, ~2.5 min
& "C:/Program Files/Python312/python.exe"      drill_census_v2.py export_cs `
        "E:/engineering-portfolio-audit/evidence/fab-da-package7/package"
& "C:/Program Files/Python312/python.exe"      check_report.py            # 52 cells, must pass
```

Three method traps re-learned in this item, all now recorded in code:

1. **`PCB_VIA.GetWidth()` with no layer argument asserts and hangs the process** in 9.0.7. It printed
   `PCB_VIA::GetWidth called without a layer argument` and never returned; every diameter is now read per layer (`measure.py:82-83`). Two 6-minute "measurements" were this.
2. **The stackup is nested, so a lazy regex silently returns nothing.** `(layer … (type) (thickness))`
   needs the block split on `(layer "`, not a `(.*?)` capture — the first attempt produced an empty
   copper dict and would have made "1 oz" an assumption.
3. **A DRC in a bare copy invents violations.** The Code-SDR run needs its `.kicad_dru`,
   `fp-lib-table` and `CodeSDR.pretty` beside it, or 25 edge-clearance and 24 library errors appear that
   the repo board does not have. With them, 222 — the number the programme records.

---

*One board, one truth. If a number here is not on a command or a file, it does not exist.*
---

## 12. Status line for `AGENT_BOARD.md` (for the lead to merge — I did not write outside my folder)

```
| fab-checklist-v2 | THE SHEET IS REWRITTEN: 4 rows x 13 verdict cells + orderable = 52 cells, every
| one a measured value with its source, counted by check_report.py (exit 0).
| PASS/FAIL/WAIVED: drone-arm 7/6/0 - ESC 5/8/0 - Code-SDR 12/0/1 - drone-mech 2/3/8 (its 8 WAIVED
| are the PCB-only columns; measured 0 board files under repos/drone-mech vs 205 STEP).
| ORDERABLE: Code-SDR YES (bare board); the other three NO.
| BLOCKING NUMBERS: drone-arm 15 non-through vias (11 blind + 4 buried, 14 at 0.100), zero PROVED
| impossible for via-edit + local copper move -> U10 fan-out re-escape; also no ESC command path
| (U10.43-48 on auto nets, no J60-J66, 64 auto nets) and an empty revision with only the rev_a
| package in the repo (75.05 x 50.05, Finish None, Rev "rev?"). ESC 1,542 unconnected (pcbnew; 499
| is kicad-cli's cap), 2.88 % routed, 540 of 556 nets with no copper; at 4 oz 523 violations at
| 0.250, 371 pad gaps at 0.2000, 110 holes at 0.200 mm against LeitOn's published 0.30 mm at 140 um,
| and ALL 1,990 via rings <= 0.200 against a 0.25 mm floor. The 370.12 cm2 compaction must NOT be
| ordered (phase corridor 1.50-3.50 vs 6.991 mm needed). drone-mech interference is ZERO in the
| genuine class (0 pairs / 0.000000 mm3) but the zero is not in the design intent and costs +38.485 mm
| of elevon station.
| TWO v1 CELLS CORRECTED: ESC minimum drill was PASS at v1 and is FAIL at 4 oz (110 pads at 0.200);
| and 499 is a cap, 1,542 is the measurement. 10 corrections listed in section 9.
```