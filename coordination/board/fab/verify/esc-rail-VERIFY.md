# Adversarial verification — ESC battery-rail wave

**Unit:** `av-esc-rail-wave` · 2026-11-16 · adversarial verifier
**Host:** KiCad 9.0.7 `C:/Program Files/KiCad/9.0/bin/python.exe` (numpy 2.3.5, scipy 1.17.1,
shapely 2.2.0) · CPython 3.12.2 for arithmetic.
**Nothing written into a repo.** No commit, push, or `audit/*` branch. Every board is a **copy**
in `boards/`; sha256 in `01_my_census.log:2-4`. No file written outside this directory. **$0.**

Boards measured (copies, hashes verified):

| tag | file | sha256 |
|---|---|---|
| orig | `boards/orig.kicad_pcb` | `992570571DEBC473…5DDD` |
| compact_stalefix | `boards/compact_stalefix.kicad_pcb` | `9F1963109C5ACB4B…4F3` |
| compact370 | `boards/compact370.kicad_pcb` | `A26EEADAC0D08586…007` |
| powerfirst | `boards/powerfirst.kicad_pcb` | `4FB519AB85026694…32C` |

Stackup parsed from each file: **F.Cu 0.140 / In1 0.0525 / In2 0.0525 / B.Cu 0.140 mm**
(`01_my_census.log:2`). Inner layers are 1.5 oz on all four boards.

---

## 1. The instrument question: pads vs copper

**Verified: YES, the replacement measures copper.** `corridor_lib.py:102-138` converts
pads through `TransformShapeToPolygon`, traces as capsules, vias as discs, and zones through
**`GetFilledPolysList(layer)`** — the fill, not the outline — and refuses an unfilled zone
rather than reading it as "no copper" (`:135-137`). Foreign obstacles are
`all copper − the measured net` (`:19-21`).

My independent census reproduces its numbers to the printed digit (`01_my_census.log:5-13`):

| net | layer | zone fill | pads | mine (zone+pads) | corridor-instrument |
|---|---|---|---|---|---|
| BATP | F.Cu | 869.165 | 348.125 | **1,217.290** | 1,217.29 |
| BATP | In1 | 5,039.008 | 5.701 | **5,044.709** | 5,044.71 |
| BATN | B.Cu | 5,106.610 | 124.605 | **5,231.215** | 5,231.22 |
| PHASE_A | In2 | 622.252 | 112.860 | **735.112** | 735.11 |

**0 unfilled zones** on all four boards (my assertion; two files, `01_my_census.log`). So no
zone outline was mistaken for copper and none was silently dropped.

### Two defects that survive in the replacement

**(a) Its min-cut check failed and was excluded — so the published neck is not a cross-section.**
`04_verdict.json:41-64` records `flow 0` on **both** `BATP|In1.Cu` and `BATN|B.Cu`, with the note
"max-flow returned 0; not a measurement, excluded". My first build of the same check returned
zero too; the cause was **reversed sink edges** (`t → b` instead of `b → t`), which leaves the
sink at in-degree 0. With the direction fixed and the terminal seeded as a *disc of that
component* rather than its whole extent, the same board returns 17.700 mm, not 0.

Consequence: the number the report publishes for BATP (4.225 mm) is a **widest-path**, and a
widest path is not a cross-section — parallel copper adds to a cut but not to a corridor.

**(b) §5F's bound is stated backwards.** `REPORT.md:245-247` claims "**min-cut ≤ 4.225 mm** …
the true cross-section is **at most** what is reported, never more". For parallel conductors the
min cut is the **sum** and the widest corridor is the narrowest single one, so `min-cut ≥
widest-path` (control K1, §2: two parallel strips 5.0 + 3.0 mm → min-cut 8.100, widest-path
5.100). Measured, BATP's In1 section is **12.5–17.7 mm — 3.0 to 4.2× wider** than published.
The FAIL direction survives; the stated bound does not.

---

## 2. My instrument, and its controls

`02_geom.py`. Same code path for controls and measurement; the measurement refuses to run if a
control fails (`02_geom.log` first block):

| control | known answer | measured |
|---|---|---|
| K1 two parallel strips 5.0 + 3.0 mm | cut 8.000 / path 5.000 | **8.100 / 5.100** |
| K2 one 4.0 mm strip | cut 4.000 / path 4.000 | **4.050 / 4.100** |
| K3 6.0 mm strip, 2.0 mm hole | cut 4.000 | **4.000** |
| K4 5.0 mm strip at 30° | cut ∈ [4.066, 5.750], 4-connected predicts 5/cos30 = 5.774 | **5.750** |

**CONTROLS PASS.** The 4-connected grid cannot cut a diagonal conductor perpendicular to its
axis, so every min-cut below is quoted as a **bracket `[C/√2, C]`**; the K4 control measures that
anisotropy rather than assuming it.

Two failure modes were found and fixed **before** any board number was quoted, both by their own
controls (`dbg_cut.py`): the reversed sink edge above (flow = 0 on a connected graph), and
seeding the terminal as the whole copper component, which made source = sink and put the cut
through the super-source edges (flow 1.25e11 mm).

---

## 3. Per-layer copper, my own measurement (board of record)

`01_my_census.log:5-18`, `02_geom.log`. Components are connected components of the union of
pad + track + zone-fill polygons **plus via pads**; "joined" asks whether the two rail terminals
sit in one component.

| net | layer | in-plane mm² | components | terminals joined | min-cut (h=.10) | widest-path |
|---|---|---|---|---|---|---|
| **BATP** | **F.Cu** | 1,217.29 | **14** | **NO** | **0 — no path** | **none** |
| **BATP** | **In1.Cu** | 5,044.71 | 1 | yes | **17.700 mm**, bracket [12.516, 17.700] | 10.198 |
| BATP | In2.Cu | 5.70 | 91 | – | via annuli only, not a conductor | – |
| BATP | B.Cu | 5.70 | 91 | – | via annuli only | – |
| **BATN** | **B.Cu** | 5,231.22 | 1 | yes | **20.000 mm**, bracket [14.142, 20.000] | 22.000 |
| BATN | F.Cu | 327.56 | 64 | **NO** | no path | none |
| PHASE_A | In2.Cu | 735.11 | 1 | – | (not needed for this verdict) | – |

Grid convergence (h = 0.40 / 0.20 / 0.10 mm): BATP In1 **18.400 → 17.800 → 17.700**;
BATN B.Cu **19.200 → 20.000 → 20.000**. Both flat to ≤ 0.5 % over a 4× refinement.

Compacted (`compact_stalefix`): BATP In1 **19.100** [13.506, 19.100]; BATN B.Cu **18.200**
[12.869, 18.200].

### The finding that decides hunt item 2

**BATP's F.Cu cannot conduct in series: 14 separate copper components, terminals not joined,
and no path at any of three grid pitches** (`02_geom.log`, orig-FCu case: "terminals on same
copper component: False", widest-path `-`). Independently, the corridor instrument reaches the
same conclusion by a different route (5 islands, `REPORT.md:134-141`) and so does `railmc`
(0 mm, `esc-battery-rail/REPORT.md:89`).

So `esc-area-honest/05b_verify.py:134-139` — `fcu_batp = 6.400  # pads-only (upper bound)` →
34.05 A, then **`BATP_rail_total = 34.05 + 9.25 = 43.30 A`** — fails twice:

1. **A gap between pads is not a conductor.** 6.400 mm is free space measured by a pads-only
   tool on a board with copper in it; that unit's own §1.3 says such a reading "on a copper-bearing
   board is an upper bound" on *free space*. Using it as a conductor width, then converting it
   to amperes, inverts its own stated logic.
2. **Series elements do not add.** F.Cu, the barrels and the In1 plane are in series; the rail's
   capability is their **minimum**, not their sum. Adding them is what turns 13.6–35.0 A into 43.30 A.

---

## 4. Does the rail carry its bus current

`04_numbers.py`, calibrated against the two settled figures to 0.01 %:
60 A, ΔT 20 K → **1.9574 mm²** (k = 0.048) or **5.0920 mm²** (k = 0.024);
4 oz width **13.981 mm**, 1.5 oz inner **96.991 mm** — both reproduce the settled numbers exactly.

| element | section | 60 A needs | at k=.048 | at k=.024 | verdict |
|---|---|---|---|---|---|
| **BATP** F.Cu local exit | 0.21 mm² | 1.957 | – | – | series, narrow |
| **BATP** via barrels in the cut | 10 × 0.03142 = 0.314 | – | – | – | series |
| **BATP** In1 plane | 0.657–0.929 | 1.957 | 27.2–35.0 A | 13.6–17.5 A | **FAIL** |
| **BATP as a series path** | **0.5242** | 1.957 | **23.1 A** | **11.5 A** | **FAIL 2.6×** |
| **BATN** B.Cu plane | 1.980–2.800 | 1.957 | **60.5–77.8 A** | 30.2–38.9 A | **passes, marginally** |
| **BATN** 45-barrel bundle | 1.4137 | 1.957 | 47.4 A | 23.7 A | **FAIL on vias** |
| BATN per-leg cluster | 15 × 0.03142 = 0.471 | – | 21.4 A | – | 19.7 A needed if 3 legs share ⅓ |

One barrel = π·d·t = π × 0.4 × 0.025 = **0.03142 mm²**. My count of vias on each net (90 BATP,
45 BATN) agrees with `esc-battery-rail`'s 45 and reproduces its 1.4137 mm² bundle exactly.

**Answer: no rail is proven at its bus current.**
- **BATP fails on copper**, by 2.6× on the k = 0.048 basis and 5.2× on k = 0.024 — and it fails
  at the *plane's own* widest section, before any barrel is counted.
- **BATN's plane passes** (101–143 % of requirement, so 60.5–77.8 A). Its **via transitions do
  not**: 45 barrels = 1.4137 mm² = 72 % = 47.4 A. BATN passes only if the three 15-barrel leg
  clusters genuinely share the return at ⅓ each (19.7 A needed vs 21.4 A capacity) — **that
  sharing is assumed by `esc-battery-rail/REPORT.md:187-191`, not measured**, and it is the
  single assumption that flips BATN's verdict.

**The three units disagree by up to 8.4× on the same physical neck** (BATP In1: 4.225 corridor /
7.360 plane-neck / 16.00 per-layer min-cut / **12.516–17.700 mine**), and by 1.8× on BATN
(35.407 / 16.700 / 38.00 / **14.142–20.000**). Every one of them is far below 1.957 mm², so the
BATP FAIL is robust to the disagreement; the *reported widths* are not.

---

## 5. The honest minimum area at 60 A

**The three areas are sound and I reproduce all three exactly** (`01_my_census.log`):
**491.732 / 370.119 / 382.709 cm²** — two independent methods in `esc-area-honest` agree to
0.0000, and my `GetBoardPolygonOutlines().Area()` agrees too. All 687 footprints are on F.Cu on
every board. No averaging, no picking between them.

**But no area at 60 A is demonstrable, and the binding constraint is not area.**
`esc-area-honest/REPORT.md:20` says so itself ("Demonstrable area today: DOES NOT EXIST"), and
my §4 confirms the rail half of that.

The constraint that actually binds is the **4 oz footprint rule**: 413 DRC items at 4 oz /
0.250 mm, **100 % footprint-bound** — 371 intra-footprint 0.2000 mm gaps + 42 PTH annular rings
— identical on all three placements, so shrinking the board moves none of them
(`esc-area-honest/REPORT.md:203-204, :228-229`). Plus LeitOn's **0.30 mm minimum finished hole
at 140 µm** against the board's 110 × 0.200 mm PTH pads (`AGENT_BOARD.md:849-853`).

The figure I can defend is therefore: **382.71 cm² is the smallest placement whose 18 phase
conductors pass at the conservative 6.991 mm requirement — and it is a placement answer, not a
60 A answer.** Its own instrumentation reads 3.700 mm at a 0 mm fan-out
(`esc-area-honest/REPORT.md:199`), so even the 18 phases are fan-out-dependent by 1.9×.

**One hole in the recommended arm that nobody checked.** `esc-area-honest/REPORT.md:249`
prices the fix as "BATP wholly on the bare B.Cu plane … costs 0 cm²". On the board of record
**BATN's 5,106.6 mm² plane already occupies B.Cu** (§3). Two 60 A rails on one layer, needing
separation, is not costed by either unit; "the layer is bare" is a statement about *parts*
(0 of 687), not about *nets*.

---

## 6. PASS over FAIL — checked against each report's own rows

| unit | verdict derived from rows? | contradiction found |
|---|---|---|
| **corridor-instrument** | **YES** — `04_verdict.py:204-210` computes `deficit ≤ 0 → PASS` from the per-layer table only | `04_verdict.json` matches `REPORT.md` §6 to the digit (0.2218 / −88.7 % / 4.957 / +153.2 %). **Clean.** |
| **esc-battery-rail** | yes | §0 and §7 both say **NO**; the before/after rows are consistent. **Clean.** |
| **esc-area-honest** | **no** | §0 row 2 "**The area that is defensible | 382.71 cm²**" and row 6 "**What I would build**" against its own §3 "**DOES NOT EXIST**… two of the four conditions fail" and §2.2 "Still not demonstrable". A scored recommendation over its own FAIL state. |

So the specific defect that started this wave — a PASS printed over its own −80 % FAIL — is
**fixed in the replacement** and has **moved, in weaker form, into the area unit's scorecard**.

---

## 7. Constraint compliance

| constraint | status | evidence |
|---|---|---|
| NO HDI anywhere | **PASS** | all **1,990** vias are `F.Cu→B.Cu` **through**, 0 non-through by span; drill census 1,962 × 0.4 + 16 × 0.3 + 12 × 0.35 |
| 4 oz **only** the ESC | **PASS** | 0.14 parsed on all four boards' F/B.Cu; **no instrument applies 0.14 to an inner layer** |
| inners **1.5 oz** | **PASS** | 0.0525 parsed; `corridor_lib.py:48`, `esc-area-honest/04_rail.py:16` both carry T_INNER = 0.0525 |
| ESC single-sided | **PASS** | 687/687 footprints on F.Cu, **0** with layer B.Cu (2 have a B.Cu-only *pad*, not a back-placed part) |
| $60 spend cap | **PASS** | $0 |
| **BOARD CORRECTION line for any contradiction** | **VIOLATED** | **0** occurrences of "BOARD CORRECTION" in all three reports, while `esc-area-honest/REPORT.md:374-376` corrects the board's settled phase numbers (board: 7.400 / 7.674 / 7.674 against 6.991; measured 7.600 at R = 2 and **3.700 at R = 0**) and `:21` re-quotes 382.71 as "defensible" against `AGENT_BOARD.md:473` "not quotable as the answer". |

---

## 8. Credibility — what does not reconcile

1. **`esc-battery-rail/REPORT.md:328` — "The corridor instrument from this wave
   (`evidence/esc-corridor-instrument/`) does not exist — the directory is absent".** It exists,
   with 30 artefacts including the `REPORT.md` the board cites. The claim is falsifiably wrong.
2. **`esc-battery-rail/REPORT.md:27` — "4 oz F.Cu 922.5 mm² of copper".** Does not reconcile
   with its own stated components: 869.17 zone + 348.13 pads + 44.95 vias = **1,262.24 mm²**, and
   both my census and the corridor instrument give **1,217.29** (zone + pads). 922.51 leaves
   53.34 mm² unaccounted for a rail with 348 mm² of pads.
3. **Two different "compacted" boards.** `9F1963109C5ACB4B…` (corridor instrument) and
   `A26EEADAC0D08586…` (area unit) are different files; both measure 370.119 cm² and identical
   per-net copper, so no conclusion changes — but neither report says they are different files.
4. **`k` is mixed inside single rows.** `esc-battery-rail/REPORT.md:31` gives "4 oz 13.68 mm
   (1.9146 mm²); 1.5 oz inner 94.87 mm" — the first is k = 0.048, the second k = 0.024, presented
   as one requirement. The report does disclose the two coefficients later (`:199-202`), but not
   at the point of use, and every "of 60 A" percentage inherits the choice.

---

## 9. Verdict

> **RAIL: does not carry its bus current.** BATP fails by 2.6× on copper even crediting its
> 1.5 oz plane at its widest section (0.5242 mm² = 23.1 A of 60 A at k = 0.048; 11.5 A at
> k = 0.024). BATN's plane passes (1.98–2.80 mm², 101–143 %); its 45-barrel transition bundle
> does not (1.414 mm² = 47.4 A), and BATN's PASS survives only on an unmeasured ⅓ current-sharing
> assumption.
>
> **AREA: 382.71 cm²** is the smallest proven *placement*; **no area at 60 A exists**, and the
> binding constraint is the 4 oz footprint rule (413 footprint-bound DRC items, identical on
> every placement), not copper and not area.
>
> **INSTRUMENT: verified — it measures copper.** Its areas reproduce to the digit. But the neck
> it publishes is a corridor width with an inverted bound, so the *number* 4.225 mm is 3–4×
> smaller than the section it claims to be.
>
> **VERDICT: MOSTLY_SOUND.**

## 10. Reproduce

```powershell
$ev="E:\engineering-portfolio-audit\evidence\av-esc-rail-wave"
$kpy="C:\Program Files\KiCad\9.0\bin\python.exe"; $py="C:\Program Files\Python312\python.exe"
cd $ev
& $kpy 01_my_census.py     # copper census, components, connectivity -> 01_my_census.log
& $kpy 02_geom.py          # controls K1-K4 gate, then min-cut + widest-path -> 02_geom.log
$env:AV_CASE="fcu"; & $kpy 02_geom.py; Remove-Item Env:\AV_CASE   # BATP F.Cu: no path
& $py  04_numbers.py       # every capacity, calibrated -> 04_numbers.log
```

## 11. What this does NOT cover

- **No 2-D current solve.** The min-cut is the best scalar statement this instrument can make;
  a plane's real capacity needs a field solve.
- **Via ampacity is not measured**, only the barrel's geometric cross-section. 25 µm vs 38 µm
  plating moves every barrel number by 1.5× and flips BATN — that is the one input worth a quote.
- **The 4 oz footprint decision is not mine**, and 413 DRC items stay unresolved without it.
- The `(version 1)` `.kicad_dru` trap is **out of scope here**: no DRC was run, so no rule file
  was relied on. The 413 / 523 / 934 counts are cited, not re-derived.