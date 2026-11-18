# drone-arm — close the last 5 pads by MOVING THE NAMED BLOCKERS (rev B, 6 layers)

STATUS: **COMPLETE — 0 of 5 pads closed, and all three named targets were executed and
measured before being rejected.** The `/3V3` via is real, it is the *second* of a
three-way cap tie (0.4223 / 0.4224 / 0.4231 mm against the 0.425 mm needed), moving it
0.020 mm opened **0 of 132 800** cells and cost **2 real clearance errors** — rolled
back. Pads 16/19/30 are not blocked 2.4–3.0 mm out: their legal 0.2 mm track exit is
**0.10 / 0.00 / 0.64 mm**, and the free region containing each is the pad itself
(0.198–0.237 mm²). The 23/24 pocket's reachable 0.4 via sites (**1** and **6**, all
within 0.12 mm) are all **electrically dead** — nearest same-net copper 0.260–0.469 mm
against a 0.200 mm via radius — so the `+1 via_diameter` trade buys nothing.
**Unconnected 8 → 8 on both tools, DRC 33 → 33 identical set, span 343 / 0 non-through,
min drill 0.200, RF void 4.1699 mm² / 9.8338 %, pad 5 still closed, board byte-identical
to the input.** Verdict: **NOT sendable.**

One task only: close pads 16, 19, 23, 24, 30 of U10 by relocating the objects that cap the
lanes — not by rebuilding the two-rank ring (already designed and measured to fail).

- Input: `evidence/da-staggered-refan/work/b0.kicad_pcb`, sha256 `21C000EF…A4223`,
  copied to `work/b0.kicad_pcb`; the source tree is never written.
- Output: `evidence/da-move-blockers/` (junction → `D:\ep-audit-evidence\da-move-blockers`).
- Host: KiCad 9.0.7, `kicad-cli.exe` + bundled `python.exe` (pcbnew). Board 6 Cu,
  165 footprints, 140.15 × 100.15 mm.

## 0. Preconditions — baseline reproduced, not quoted

Every number in this table was re-measured on `work/b0.kicad_pcb`
(sha256 `21C000EF…A4223`, byte-identical to the input). DRC ran in
`drc/b0/`, a directory holding the board **and** `b0.kicad_pro`; without that
companion the clearance reads 0 and every raster number in this report would be
wrong (the predecessor hit exactly that).

| check | required | measured here | verdict |
|---|---|---|---|
| DRC (`--format json --severity-all --units mm`) | 33 | **33** — 26 `track_dangling` (warning), 5 `via_diameter` (error, all 0.400 vs 0.600 min), 2 `track_width` (error, 0.150 vs 0.200 min) | reproduces |
| unconnected, kicad-cli / pcbnew | 8 / 8 | **8 / 8** | reproduces |
| vias, span | 343, 0 non-through | **343, all `THROUGH F.Cu → B.Cu`, 0 non-through** | reproduces |
| min drill | 0.200 | **0.200**; 4 PTH slot pads at 0.6 (J1) | reproduces |
| RF void | 4.1699 mm² / 9.8338 % | **4.1699 / 9.8338** (void_B 3.8754 / 9.1392) | reproduces |
| design rules actually loaded | 0.125 / 0.200 / 0.600 / 0.100 / 0.200 / 0.200 / 0.500 | `{'min_clearance': 0.125, 'track_min_width': 0.2, 'via_min_size': 0.6, 'via_min_annular': 0.1, 'hole_min': 0.2, 'hole_to_hole': 0.2, 'copper_edge': 0.5}` | reproduces |

### 0.1 The eight unconnected pairs, read exactly (not summarised)

From `drc/drc_b0.json`, resolved to board geometry by uuid (`work/t3_pairs.json`).
The five stranded pads are **single-item islands**: each pad is alone on its net,
and the rest of the net (tracks, vias, other pads) is one separate island. So each
pad has exactly one gap, and touching the partner island closes it.

| pad | net | pad at | partner (the island the DRC names) |
|---|---|---|---|
| 16 | `/RF_SCLK` | (54.050, 52.200) | In2.Cu track (54.300,54.050)–(54.350,54.050), w0.25, **0.050 mm** — a fragment; the real island holds 16 tracks + 1 via + U40.8 |
| 19 | `/RF_nCS` | (54.050, 53.400) | In2.Cu track (53.163,55.542)–(62.463,64.843), w0.25, 13.153 mm |
| 23 | `/RF_GPIO3` | (56.000, 54.950) | **F.Cu** track (54.051,54.973)–(54.680,55.602), w0.25, 0.890 mm |
| 24 | `/3V3` | (56.400, 54.950) | **F.Cu** track (58.400,54.950)–(58.400,55.550), w0.25, 0.600 mm |
| 30 | `/RP2354B MCU/XIN` | (58.800, 54.950) | In1.Cu track (58.850,55.300)–(58.350,54.800), w0.25, 0.707 mm |
| — | `/GND` | — | F.Cu zone ↔ F.Cu zone (pre-existing, untouched) |
| — | `/GNSS_RESET_N` | — | B.Cu 10.587 ↔ F.Cu 0.732 (cross-layer, pre-existing) |
| — | `/RF_GPIO0` | — | F.Cu 1.032 ↔ In2.Cu 2.143 (cross-layer, pre-existing) |

Two of the five partners are on the **same layer** as the pad (23 and 24), so those
two need no via at all in principle — only a legal F.Cu track. That is measured in §3.

### 0.2 Two instrument defects found and corrected mid-task

1. **`PCB_VIA.GetWidth()` with no argument hangs — reproduced, with the message.**
   `GetWidth()` asserted `PCB_VIA::GetWidth called without a layer argument`
   (`pcb_track.cpp:381`) and then never returned (killed after 90 s, PID 19652).
   `GetWidth(TopLayer())` returns in 0.00 s. `geo.py` uses only the layer form.
2. **A fine raster over a small window is not an instrument.** Refining the corner
   at 0.0025 mm reported a best headroom of 0.5627 mm at a point where the analytic
   distance to the nearest copper is 0.1743 mm — PIL fills polygons whose vertices
   all lie outside the crop unreliably. Every number in §1–§3 is therefore a
   **shapely** distance against the real geometry, or an A* over a mask built from
   the full-board copper, never a small-window raster.

## 1. TARGET 1 — the `/3V3` via stack, and why moving it opens nothing

**It exists, it is one via, and it is not the cap.** The brief's premise is off by
0.0001 mm, and that is enough to change the answer.

### 1.1 Which object

| field | value |
|---|---|
| uuid | `fee8b314-d0db-4b5c-8958-980b17740aa8` |
| net | `/3V3` |
| position | **(51.1834, 54.3593)** — 0.7724 mm from the best cell (1.44 mm of copper-to-copper path) |
| size / drill | **0.700 / 0.350** (not 0.6/0.3 — it is a 0.7 mm via, radius 0.35) |
| span | `THROUGH F.Cu → B.Cu`, type 3 |
| attached copper | 3 tracks end on it: F.Cu `bd2fa170` w0.25, B.Cu `6159268e` w0.25, In1 `92e139a2` w0.25 |

### 1.2 The best cell, and the three-way tie that caps it

Analytic refinement (`work/t2_exact.py`, ±0.35 mm at 0.005 then 0.001) puts the best
0.6-via centre in the 10 × 8.3 mm corner at **(51.7315, 54.9035)** with a headroom of
**0.4223 mm against the 0.425 mm** a 0.6/0.3 via needs. Shortfall **0.0027 mm**.
What caps it — exact distance to foreign copper, per layer:

| distance | layer | net | object |
|---|---|---|---|
| **0.4223** | In1.Cu | **`/ICM_INT2`** | track `f8aaa134` ← the actual cap |
| **0.4224** | all six | `/3V3` | **via `fee8b314`** ← the named blocker, second by 0.0001 |
| 0.4231 | In1.Cu | `/3V3` | track `92e139a2` |
| 0.4965 | B.Cu | `/ICM_INT1` | track `a21f876f` |
| 0.6067 | B.Cu | `/3V3` | tracks `6159268e`, `77028dbd` |

**The deciding measurement:** delete the entire `/3V3` net from the obstacle field and
re-measure that cell — the ceiling is **0.4223 mm, unchanged** (`ceiling_no_3v3` in
`work/t2_exact.json`). Moving the via cannot open this cell; the `/ICM_INT2` In1 track
is 0.0001 mm closer and stays.

### 1.3 The smallest legal move, and its own clearance

To clear the cell the via centre must sit 0.425 + 0.350 = **0.7750 mm** away; it is at
0.7724, so the **minimum push is 0.0026 mm** along (−0.7096, −0.7046) — away from the
cell, toward the `/LSM_INT1` copper. Its own clearance now is only **0.1334 mm**
(In1 `/LSM_INT1` track `534007c3`), i.e. **0.0084 mm of headroom over the 0.125 rule**.
Pushing 0.020 mm (the smallest *round* move, so the edit is stable) drops that to
**0.1187 mm** — below the rule. The via has room for 0.008 mm, not 0.020.

### 1.4 Measured: the move opens 0 cells and costs 3 violations — rejected

Batch `/3V3`-MOVE: `work/b1.kicad_pcb` = b0 with the via and all 3 track ends moved
0.020 mm along the push vector (`work/t7_3v3.json`).

| | b0 | b1 (via moved 0.020 mm) |
|---|---|---|
| legal 0.6 cells, 10 × 8.3 mm corner @0.025 (132 800 cells) | **0** | **0** |
| best raster headroom in the corner | 0.3998 | 0.4118 (a *different* cell, (51.7125,54.9125)) |
| unconnected, pcbnew | 8 | **8** |
| DRC | 33 | **36** |
| DRC set diff | — | **+3 `clearance`, 0 removed**: `/LSM_INT1` In1 0.1192 and 0.1187 (vs 0.125), and a **zone** clearance 0.1805 vs 0.2000 |

The zone hit is a stale-fill artefact (pours recede only on refill) — but the two track
hits are real, and the cell count is the point: **a move that costs 2 real clearance
errors opens nothing.** Rolled back; `b1` is kept as the artefact of the rejected
attempt, not as a deliverable.

### 1.5 The upper bound of any `/3V3` move — and it is still no good

Delete the **whole `/3V3` net** from the obstacle field (the best any relocation of
`/3V3` copper could ever achieve) and the corner does open: **223 of 132 800 cells**,
best headroom 0.7333. But those cells sit at the **window's own left edge**
(best at (51.0125, 54.5375), x ≈ 51.0–51.7) — **3.243 mm from pad 19, 3.833 mm from
pad 16, 5.0 mm from pad 23**, and better cells lie *outside* the window, i.e. further
from U10. So even the net-level deletion leaves no via site near a stranded pad, and
§2 shows that a 3.2–3.8 mm route out of these pads does not exist at the board's rules.

**TARGET 1 verdict: the named blocker is real but it is the second of a three-way tie
at 0.4223/0.4224/0.4231 mm; moving it opens 0 cells (measured, 0 → 0), costs 2 real
clearance errors, and even deleting its entire net puts the nearest 0.6 site 3.24 mm
from the closest stranded pad. This was not the cheap fix — it was not a fix at all.**

## 2. TARGET 2 — pads 16 / 19 / 30: the corridor is at the pad, and it is 0.00–0.10 mm long

The brief describes these pads as having "a legal 0.4 mm site 2.385 / 2.559 / 3.004 mm
away, behind 31–41 corridor objects". That measurement is correct as arithmetic and
**falsified as a diagnosis**: the corridor never gets 2.4 mm. Measured exactly — a
0.200 mm track grown from the pad's copper in 0.01 mm steps on each layer, stopped at
the first position that breaks the board's own 0.125 mm clearance
(`work/t12_exit.py`, results `work/t12_exit.json`):

| pad | net | F.Cu exit −x / +x / −y / +y (mm) | best exit on any layer |
|---|---|---|---|
| 16 | `/RF_SCLK` | **0.10** / 0.04 / 0.00 / 0.00 | In4 −y 1.50, In2 +x 0.96, In3 −y 1.50 |
| 19 | `/RF_nCS` | **0.00 / 0.01 / 0.00 / 0.00** | In4 −y 1.50, In4 +y 0.34 |
| 30 | `/RP2354B MCU/XIN` | 0.00 / 0.00 / **0.64** / 0.01 | In4 +y 1.50 (outboard, dead corner) |

Read the F.Cu row: **pad 19 cannot emit a single 0.2 mm track on its own layer**
(0.00 mm in every direction); pad 16 emits **0.10 mm** and stops; pad 30 emits
**0.64 mm inboard** under the package and stops. The 31–41 "corridor objects" are
objects along a straight line to a site the pad can never reach — the binding
objects are the ones within 0.2 mm of the pad edge.

### 2.1 The objects that actually cap each pad (identified, by layer)

`work/t11_cage_ident.py` → `work/t11_cage_ident.json`. Nearest foreign copper to the
pad's own copper, per layer, with 2-D distance (layers are listed separately because a
via needs all six clear while a track needs only its own):

| pad | F.Cu cap | In1 | In2 | In3 | In4 | B.Cu |
|---|---|---|---|---|---|---|
| 16 | **`/RF_MOSI` track `fcd6a169` w0.15 at 0.1666** | `/RF_MISO` track 0.2433 | `/RF_MISO` via `3c25f4e9` 0.2582 | `/GNSS_RX` track 0.0000 (under the pad) | `/RF_MISO` via 0.2582 | `/ICM_nCS` track 0.0000 |
| 19 | **`/GNSS_RX` via `37323635` at 0.1750** | `/RF_MISO` track 0.1750 | `/RF_MISO` track 0.1750 | `/BARO_DRDY` track 0.0000 | `/GNSS_RX` via 0.1750 | `/ICM_nCS` track 0.0000 |
| 30 | **`/RP2354B MCU/XOUT` track `f9ccec81` w0.25 at 0.1750** | `/3V3` via `81c6ecc8` 0.1793 | `/LNA_EN` track 0.0000 | `/RF_MISO` track 0.0000 | `/RF_MOSI` track 0.0000 | `/RF_GPIO2` track 0.0000 |

A 0.2 mm track needs **0.225 mm** from its centreline (0.125 clearance + 0.100 half
width). Every F.Cu cap above is 0.166–0.175 mm — short by 0.050–0.059 mm, which is
exactly why the exit table stops where it does. And a 0.6 mm via needs **0.425 mm on
all six layers** while inner layers carry copper *directly under* the pad (0.0000) on
16, 19 and 30: there is no via site at any class, which is the same fact §1 found from
the other direction.

### 2.2 Can the corridor be re-routed locally? — measured, no

`work/t5_route.py` (A* at the board's rules, 0.04 mm raster, 6 layers, endpoints =
the exact DRC partner) and `work/t6_cage.py` (clearance relaxation sweep):

| pad | free region containing the pad | legal 0.6 vias reachable | legal 0.4 vias reachable | path at the board's rules | clearance at which a path first exists | shortfall |
|---|---|---|---|---|---|---|
| 16 | **125 cells = 0.200 mm²** | 0 | 0 | **no path** | 0.050 mm | 0.175 |
| 19 | **124 cells = 0.198 mm²** | 0 | 0 | **no path** | 0.120 mm | 0.105 |
| 30 | **148 cells = 0.237 mm²** | 0 | 0 | **no path** | 0.050 mm | 0.175 |

(The 0.225 mm requirement minus the reached value: the lane is short by 0.105–0.175 mm.)
For 16/19/30 the free region is **the pad plus nothing** — 0.198–0.237 mm², i.e. the
0.16 mm² pad and a rounding halo. There is no corridor to re-route, and no via cell of
any class inside it (`work/t10_viasites.json`). **0 of 3 opened.**

A note on method, so the next session does not repeat it: I first tried to identify a
"pinch object" set from the relaxed path and delete it (`work/t8_unlock.py`,
`work/t9_cagecut.py`). That is the wrong instrument — removing the objects nearest a
path that is legal at 0.10 mm does not make that path legal at 0.225 mm, and the
pad-23 run showed **0 growth in the free region after 4 removals** (exp 1117 → 1117).
The cage-cut loop was stopped rather than reported; the numbers above come from the
exit-length and relaxation instruments, which do answer the question.

## 3. TARGET 3 — pads 23 / 24 and the inboard pocket

Both pads have exactly one exit: **inboard (−y), 0.83 mm (pad 23) and ≥1.50 mm
(pad 24)** — into the pocket the predecessor found. The pocket is real, and it is
**electrically empty**.

### 3.1 The pocket, re-measured with the reachability instrument

| pad | free region | reachable legal 0.6 via cells | reachable legal 0.4 via cells | where |
|---|---|---|---|---|
| 23 | 8 440 cells = **13.504 mm²** | **0** | **1** | (56.340, 54.170) |
| 24 | 7 780 cells = **12.448 mm²** | **0** | **6** | x 56.300–56.340, y 54.170–54.290 |

The six pad-24 sites span **0.12 mm** between their extremes; the sampled maximum
pair distance is 0.1200 mm against the 0.525 mm two 0.4/0.2 vias need. That
independently reproduces the predecessor's "no pair ≥ 0.525", with a different
instrument (A*-reachable cells, not a standalone raster). Two vias for 23 and 24 in
this pocket remain impossible, and since the nets differ (`/RF_GPIO3` vs `/3V3`) a
shared via is still impossible.

### 3.2 The deciding measurement: every reachable 0.4 site is dead

A 0.4 mm via adds copper of radius **0.200 mm** on every layer; it connects only if it
overlaps same-net copper. Nearest same-net copper from each reachable site, any layer
(`work/t13_pocketsites.py`):

| pad | site | nearest same-net copper | verdict |
|---|---|---|---|
| 23 | (56.340, 54.170) | **U10.23's own pad at 0.4686** | DEAD |
| 24 | (56.300, 54.170) … (56.340, 54.290) | **0.3827, 0.3800, 0.3430, 0.3400, 0.3034, 0.2600** — all U10.24's own pad | **DEAD ×6** |

**Not one of the seven sites is within 0.200 mm of any same-net copper on any of the
six layers.** A via dropped there is an isolated washer: it would add 1 `via_diameter`
error to the DRC (5 → 6) and close nothing. This is the mechanism behind the
predecessor's batch A, which moved the ratsnest line from *pad ↔ 0.6 mm track* to
*0.6 mm track ↔ 0.751 mm track* instead of closing it; "landed in a dead /3V3 pour
fragment" was a plausible guess, but there is no `/3V3` copper of any kind within
0.60 mm of the pocket — zone or track — so the via touched nothing at all.

### 3.3 Option B — route one pad on another layer entirely

Unavailable, and by the same measurement: **0 legal 0.6 via cells are reachable from
any of the five pads**, and the 0.4 sites that are reachable are dead (§3.2). A pad
cannot change layer at all, so "route it on another layer" has no via to enter it.
The F.Cu route to the partner that needs no via (23 and 24 both have F.Cu partners)
is the only remaining idea and it is 0.105–0.125 mm short (§3.4).

### 3.4 Decision

**Neither 0.4 via is acceptable — not because of the `via_diameter` trade, but because
the trade buys nothing.** The cost is stated as the brief asks: **+1 `via_diameter`
error (5 → 6)** for a 0.400 mm via on a board whose `via_min_size` is 0.600, i.e. a
rule change that is the owner's to make. The benefit is **zero**: every reachable
0.4 site is 0.26–0.47 mm from same-net copper against a 0.200 mm radius (§3.2), and
the pads' own F.Cu routes are 0.105 mm (pad 24) and 0.125 mm (pad 23) too tight at
4–5 named pinch objects, several of which are other nets' **pads** (immovable) —
`/GND` pad, `/1V1` pad, `/RF_RESET_N` pad, `/PA_EN` pad in the pinch set. The three
movable track objects in that set have 0.169–0.215 mm of their own headroom, so a
move is not blocked *per object* — it is blocked as a set.

## 4. Batches: kept / attempted, DRC set diff

| # | batch | what was done | unconnected | DRC set diff | outcome |
|---|---|---|---|---|---|
| `/3V3`-MOVE | the TARGET 1 fix | via `fee8b314` + all 3 track ends moved **0.020 mm** along the push vector; `work/b1.kicad_pcb` | 8 → **8** | **33 → 36**, `+3 clearance` (0 removed); **0 cells opened** of 132 800 | **REJECTED, rolled back** |
| 16 / 19 / 30 | local corridor re-route | **not applied — no legal path exists** (A* at the board's rules, 5 mm window, 6 layers, both via classes: `no path`; free region 0.198–0.237 mm²) | — | nothing to gate | nothing to gate |
| 23 / 24 | 0.4 via in the pocket | **not applied — every reachable 0.4 site is dead** (§3.2: nearest same-net copper 0.260–0.469 vs a 0.200 radius) | — | nothing to gate | nothing to gate |

**Kept / attempted: 0 pads closed, 1 batch attempted, 1 rolled back, 0 of 5 pads
improved. 0 mm of copper added, 0 objects removed.** `work/b0.kicad_pcb` is
byte-identical to the input (sha256 `21C000EF…A4223`), so the delivered board is the
input board and there is no set diff to report on it.

## 5. Whole-board verification

The final board **is** `work/b0.kicad_pcb` (= the input, unchanged). Every invariant
was re-measured here rather than carried:

| invariant | required | measured | verdict |
|---|---|---|---|
| span census | 0 non-through | **343 vias, all `THROUGH F.Cu → B.Cu`, 0 non-through** (`work/span_b0.json`) | **PASS** |
| min drill | 0.200 | **0.200** (4 PTH slot pads at 0.6, J1) | **PASS** |
| unconnected, kicad-cli | — | **8** | unchanged |
| unconnected, pcbnew | — | **8** | both tools agree |
| DRC set diff vs baseline | none | **identical** — 33 = 26 `track_dangling` + 5 `via_diameter` + 2 `track_width` | **PASS** |
| RF void | bit-identical 4.1699 / 9.8338 | **4.1699 mm² = 9.8338 %**, void_B 3.8754 = 9.1392 % | **PASS** |
| pad 5 | stays closed | **not among the 8 unconnected pairs** | **PASS** |
| input board untouched | sha256 unchanged | **`21C000EF…A4223`, 2 438 632 bytes** | **PASS** |

The package was **not** regenerated: its precondition is 0 unconnected with 0
non-through and a clean set diff, and this pass closes 0 of 5. Regenerating 20 Gerbers
and a drill pair off a board with 8 opens would produce the manufactured pass the
brief forbids.

## 6. Verdict — IS DRONE-ARM SENDABLE TO A FAB? **NO.**

Five pads remain open, and the reason is one step further back than the previous two
diagnoses. It is not the pad pitch (pads were never the cap), and it is not only the
inner-layer via field: **three of the five pads cannot emit a 0.2 mm track on their own
layer at all** (0.00–0.10 mm of legal exit), and **the two that can** emit copper into
the one inboard pocket find a pocket with **zero legal 0.6 via cells and seven 0.4 sites
that are all 0.26–0.47 mm from any same-net copper**.

What was established with numbers in this pass:

1. **The named `/3V3` blocker is real but second.** The best corner cell needs 0.425 and
   has 0.4223; the cap is `/ICM_INT2`'s In1 track at 0.4223, with the `/3V3` 0.7/0.35
   via at 0.4224 and a `/3V3` In1 track at 0.4231 — a three-way tie inside 0.0008 mm.
   Deleting the **entire `/3V3` net** leaves that cell at 0.4223: zero gain. The
   smallest legal push is 0.0026 mm; the via has 0.0084 mm of clearance slack, so the
   0.020 mm move that was actually applied costs **2 real clearance errors** (plus one
   stale zone fill) and opens **0 of 132 800 cells**. Rolled back.
2. **The corridor the brief measured is not the corridor that binds.** Pads 16/19/30's
   exits are 0.10 / 0.00 / 0.64 mm; the free region containing each is 0.198–0.237 mm² —
   the pad and a halo. Their cages are named in §2.1: an `/RF_MOSI` F.Cu track at
   0.1666 (pad 16), a `/GNSS_RX` F.Cu via at 0.1750 (pad 19), an `/XOUT` F.Cu track at
   0.1750 (pad 30), plus inner-layer copper passing **directly under** each pad
   (0.0000) that forbids any via at any class.
3. **The pocket cannot be used.** 1 reachable 0.4 site for pad 23, 6 for pad 24, inside
   0.12 mm; every one is dead — nearest same-net copper 0.260–0.469 mm against the
   0.200 mm copper radius of the via itself. A 0.4 via there would cost **+1
   `via_diameter`** and close **nothing**.
4. **What would actually move the answer**, in cost order: (a) a **0.4/0.2 via class
   declared by the owner** — this alone is **not enough**, since it opens only dead
   sites (§3.2); (b) **moving the F.Cu cage objects 0.05–0.13 mm** at pads 16/19/23/24
   — 4–5 objects each, several of them other nets' pads, which is a corner re-fan and
   therefore out of this task's scope and already measured to fail as a re-fan; (c) a
   **U10 fanout/layer-pair change** (laser-via HDI or a finer annular) — the only item
   on the list that addresses the inner-layer copper under the pads, i.e. 3 of the 5.

Deliverables: `work/b0.kicad_pcb` (verified reference, unchanged, sha256 `21C000EF…A4223`),
`work/b1.kicad_pcb` (**rejected** `/3V3` move, kept for the audit trail), `drc/drc_b0.json`,
`drc/drc_b1.json`, `work/span_b0.json`, the measurements `work/t1_cap.json`,
`work/t2_exact.json`, `work/t3_pairs.json`, `work/t4_netinv.json`, `work/t5_route.json`,
`work/t6_cage.json`, `work/t7_3v3.json`, `work/t8_p19.json`, `work/t8_p23.json`,
`work/t8_p24.json`, `work/t9_p23.json`, `work/t9_p24.json`, `work/t10_viasites.json`,
`work/t11_cage_ident.json`, `work/t12_exit.json`, `work/t13_pocketsites.json`, and the
logs in `logs/`.

## A. Appendix — instruments (all in `work/`, run with the KiCad 9.0.7 bundled python)

`t1_cap.py` worst-layer headroom raster + argmax (reproduces the 0.3998 corner figure) ·
`t2_exact.py` analytic shapely refinement of the best cell, its obstacle list, the
`/3V3` ceiling and the push sweep · `t3_pairs.py` the 8 unconnected pairs resolved to
geometry by uuid · `t4_netinv.py` per-net island inventory (proves each pad is a
one-item island) · `t5_route.py` A* from each pad to its exact DRC partner, two via
classes · `t6_cage.py` clearance relaxation sweep (the smallest clearance at which a
path exists, with the pinch set) · `t7_3v3.py` TARGET 1: identity, clearance, the move,
the moved board, and the three-way cell census · `t8_unlock.py`, `t9_cagecut.py`
abandoned candidate-set instruments, kept to document the defect · `t10_viasites.py`
reachable via-cell census per pad (0.6 and 0.4 classes) · `t11_cage_ident.py` cage
identification + pinch-object headroom · `t12_exit.py` exact 0.2 mm track exit length
per pad per layer per direction · `t13_pocketsites.py` electrical liveness of each
reachable 0.4 site · plus `geo.py`, `router.py`, `span_census7.py`, `s5_void.py`
inherited unmodified.

Two instrument facts worth carrying forward: `PCB_VIA.GetWidth()` with no argument
**hangs** (asserts `called without a layer argument`, `pcb_track.cpp:381`), and a
PIL-filled distance raster over a small window silently under-reports obstacles —
both are measured in §0.2.