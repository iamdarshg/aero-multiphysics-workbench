# ESC route attempt — can 4-layer 3 oz actually route the 1,536 unconnected?

Wave 16 · session fc94d1e6-7e15-4be9-b088-4a2d5acf2184

**THE ONE QUESTION:** at 4-layer 3 oz with the affordable configuration (34.5 A bus / 36.6 A phase),
how much of the ESC's 1,536 unconnected connections can actually be routed?

Evidence: `E:/engineering-portfolio-audit/evidence/esc-route-attempt/`. Every board here is a copy;
the repository board `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb` was read only.
Host: KiCad 9.0.7 (`C:/Program Files/KiCad/9.0/bin/`), `pcbnew` Python 3.11 (numpy 2.3.5,
scipy 1.17.1, shapely 2.2.0), `kicad-cli pcb drc`, freerouting **2.5.0** (jar,
`E:/engineering-portfolio-audit/evidence/esc-routable2/tools/freerouting-2.5.0.jar`,
downloaded by wave 5 — the native `freerouting-cli.exe` from `esc-routability` is unusable, see §2.3).

---

## 0. Status

| step | state |
|---|---|
| Report skeleton | written before any measurement |
| 1. 4-layer 3 oz board + 0.200/0.200, DSN export, freerouting (bounded) | **done — 1 pass, 55 min cap extended to 90 min, no session; the cell control completes in 5 min 8 s** |
| 2. Routed / unrouted of 1,542 + DRC set diff | **done — full-board pass overran its budget with no session written (88 min 28 s inside one pass); the routed/unrouted answer is the cell control, 114 of 313 = 36.42 %** |
| 3. Failure diagnosis with counts | **done** |
| 4. Manual one-phase-block route (pcbnew, drawn) | **done — DRC-clean, corridor 3.6 mm against 9.43 mm required** |
| 5. Verdict | **NO at the required width; the copper, not the router, is the limit** |

### 0.1 Which board is "the 4-layer 3 oz board with the 0.200/0.200 rules"

`esc-3oz-build/boards/base3oz.kicad_pcb` — the wave-14 build of record: the repository board with
the two shipped pad changes (288 LQFP-48 pads 0.300→0.250, 16 USB-C power pads 0.600→0.500), the
3 oz stackup (F.Cu/B.Cu **0.105 mm**, In1/In2 0.0525 mm, 1.600 mm total) and the
`rules_3oz_020.kicad_dru` (0.200 clearance / 0.200 track / 0.200 pattern) copied beside it as
`base3oz.kicad_dru`. re-measured this run (`00_probe.py` → `00_probe.json`):

| quantity | value |
|---|---|
| outline | 173.950 × 283.080 mm = **491.73 cm²** (polygon 49,173.2 mm²) |
| footprints / pads | **687 / 3,454** (0 footprints on B.Cu) |
| nets with ≥2 pads | **556**, of which **16** carry any track (**2.88 %**) |
| segments / vias / zones | **154 / 1,990 / 96** |
| **pcbnew unconnected** | **1,542** (the settled figure is 1,536–1,542; 1,542 is what this exact file says) |
| `kicad-cli drc` | **102 violations, 499 unconnected** (499 is kicad-cli's cap, not a count) |

The affordable configuration's width requirements are the settled ones
(`esc-3oz-build/08_ampacity.json`, k = 0.048 external, ΔT = 20 K, t = 0.105 mm), recomputed here in
`05_manual_route_v2.py`:

```
phase 36.6 A on one 105 um outer  =  9.427 mm      (cap of 9.42 mm = 36.58 A)
bus   34.5 A on one 105 um outer  =  8.690 mm
phase 43.5 A (the unaffordable ask) = 11.963 mm
```

**A defect found on the way in, and it matters for every router (§1.4): the zone fills stored in
`base3oz.kicad_pcb` are stale.** Refilling them (`07_refill.py` → `07_refill.json`) adds
**+2,771 mm² of copper (2.7 %)**: F.Cu 10,972.55 → 11,266.61 mm², In1 30,274.48 → 31,400.84,
In2 12,336.13 → 12,491.95, B.Cu 30,595.45 → 31,790.21. All routing below is done on the **refilled**
board `boards/base3oz_rf.kicad_pcb`, because `kicad-cli drc` (and every other tool that refills)
checks the fresh fill, not the stored one.

## 1. Specctra DSN export and the freerouting run

### 1.1 The export is complete and it carries the real rules

`01_dsn.py` → `01_dsn.json`, `work/base3oz.dsn` (461,898 bytes):

| in the DSN | value |
|---|---|
| layers / placement | 4 (`F.Cu In1.Cu In2.Cu B.Cu`) / **687 `(place …)`** |
| nets | 2,805 `(net …)` |
| classes | 6, widths and clearances as exported: `kicad_default 250/200`, `POWER 800/200`, `CAN_DIFF 250/200`, `CURRENT_SENSE 250/200`, **`HIGH_CURRENT 6000/200`**, `GATE_DRIVE 500/200` |
| fixed copper in the design | **96 `(plane …)`** (the zones, exported as fixed conducting areas), 1,991 `(via …)`, 149 `(wire …)` |
| keepouts | 12 |

The 0.200 mm clearance is in the DSN, so the "0.200/0.200 rules" reached the router. The exporter
reads the project **netclasses**, not the `.kicad_dru` — a known trap from wave 5 — and the
netclasses in `base3oz.kicad_pro` are already 0.2 mm (`rules.min_clearance 0.2`,
`min_track_width 0.2`, `Default.clearance 0.2`), so no patch was needed this time.

**`HIGH_CURRENT` = 6.000 mm** is worth naming here: every phase and bus net in this design is in a
class whose *class rule* asks the router for 6 mm tracks. That is 0.636 of the 9.427 mm the phase
actually needs and 3.3× the widest corridor the placement offers (§4). The rule set the board ships
with is already inconsistent with the copper the board needs.

### 1.2 The bounded run

```
java -Xmx3072m -jar freerouting-2.5.0.jar -de work/base3oz.dsn -do work/runA_p1.ses -mp 1 -mt 4 -l en
```

`-mp 1` = **one autorouter pass**, plus a **hard 55-minute wall cap** (13:16:15 → 13:27:31 fanout,
then the single autoroute pass; the process is stopped at the cap). The budget is deliberately
pass-bounded rather than time-sliced, because freerouting writes the `.ses` only at the end: a
time-sliced kill produces nothing and is unfalsifiable. **The cap was extended once to 90 minutes and
the pass still overran it — what that cost is in §2.2.**

### 1.3 What it reported before it routed anything

**1,872 pre-existing "unfixable" clearance violations in the loaded design**, every one of them
`FixedVia ↔ FixedVia` **on the same net** (`logs/runA_p1.log`). KiCad does not flag them
(`drc_rf_base.json`: 0 rows of that type) because same-net vias may touch; freerouting treats them
as violations it cannot fix. The tile run in wave 5 saw the same thing at smaller scale (346 rows).
So the router starts from a design it scores as 1,872 violations deep and can never clean.

### 1.4 Fanout — the first place the answer appears

```
Fanout stage started : 2,617 of 2,779 SMD pins needing fanout
13 passes, stopped after 3 passes with no progress
Fanout stage completed: escaped pins 2,149 / 2,759 (77.9 %), 610 SMD pins NOT escaped
Auto-routing stage started: baseline score 397.85 for 1,069 unrouted items
```

**610 of 2,759 SMD pins (22.1 %) could not be fanned out even onto an empty board** — fanout only
adds a short stub and a via, and it failed. This is before any signal competes for the same space.
The 2,149 pins that did escape consumed **963 extra free vias** (825 + 90 + 28 + 10 + 5 + 3 + 0 + 0 +
1 + 1 + 0 + 0 + 0 across the 13 passes).

## 2. Outcome

### 2.1 The number

| | |
|---|---|
| connections to place (pcbnew, this file) | **1,542** |
| freerouting unrouted items entering the autorouter | **1,069** |
| freerouting unrouted items after the bounded run | **not produced — no session file** |
| **routed by the router, proven** | **0** |
| **routed fraction of 1,542, full board** | **0 proven of 1,542** — a budget overrun, not a capability result |
| DRC set diff vs the unrouted board | **not applicable — there is no imported copper to diff** |
| **routed fraction, one-cell control (§2.4)** | **114 of 313 = 36.42 %** |

### 2.2 What the bounded run actually delivered on the full board

`13:16:15` start → `13:27:14` fanout complete (626.6 s) → `13:27:31` **one autorouter pass** begins on
**1,069 unrouted items** → stopped at `14:55:59` at the end of the extended budget: **88 min 28 s
inside that single pass, 7,267 CPU-seconds, 1,055 MB peak, and no `.ses` written.** freerouting writes
the session only at the very end, so a time-sliced stop yields no copper at all. The honest statement
is *the router did not finish*, not *the board cannot be routed*.

The budget as stated and as spent: **`-mp 1` (one pass) with a 55-minute wall cap**, extended once to
**90 minutes** to give the single pass a fair chance. The pass exceeded both, so it was stopped rather
than allowed to run unbounded. For scale, the same router on the same rules finished **2 passes on a
cell's 172 unrouted items in 5 min 8 s** — 6.2× fewer items and 39× less time per pass. The full board
is worse than 6× the cell by more than an order of magnitude, and that is itself a result about this
board: **1,990 fixed vias and 96 planes give freerouting's rip-up/reroute loop a search space it does
not converge in.**

**So the quantitative answer to the question comes from the cell control (§2.4) and the fanout census
(§1.4), not from a full-board session that never landed.**

### 2.3 The tooling trap that cost wave 5 its route

`freerouting-cli.exe` 2.5.0 (native image, `esc-routability/tools/fr`) **cannot autoroute at all**:
`BoardSnapshotManager.getHash` → `BasicBoard.getHash` serialises the board and dies with
`com.oracle.svm.core.jdk.UnsupportedFeatureError: SerializationConstructorAccessor class not found
for declaringClass: app.freerouting.board.model.items.ComponentOutline`
(`esc-routability/block1/fr.err.log`, `esc-routable2/block1/fr.log`). It burns 0.6 s of CPU in 45 s
of wall time and then writes a 0-byte `.ses`. The **jar** runs the same code on a JVM and routes
normally (`esc-routable2/block1/fr_jar3.log`). Anyone reading a 0-byte session file as "the router
failed on the geometry" is reading the wrong instrument.

### 2.4 The bounded control: one cell, same router, same rules (and it finishes in 5 minutes)

Because the full-board pass is the expensive one, the same router was given **one phase cell**
(`19_tile.py` → `19_tile.json`, `work/cell1.kicad_pcb`): 95 footprints / 497 pads / 96 nets, the
tile 87.27 × 81.03 = **70.71 cm²**, **copper stripped to pads only** (all 96 zones, 154 segments and
1,990 vias removed) so it is the same pads-only problem wave 5's compact tile was, with the 0.200 /
0.200 rules and the board's own class table. Two passes, `-mp 2`: 14:09:01 → 14:14:09, **5 min 8 s**.

| | full board | one cell |
|---|---:|---:|
| SMD pins needing fanout | 2,617 | 379 |
| **escaped in fanout** | **2,149 / 2,759 = 77.9 %** | **305 / 393 = 77.6 %** |
| unrouted items entering the autorouter | 1,069 | 172 |
| unrouted after the bounded run | **pass did not complete** (no session) | **83** |
| pcbnew unconnected before → after | 1,542 → **not measured** (no session) | **313 → 199** |
| **routed** | | **114 (36.42 %)** |
| copper drawn | | 833.9 mm², 727 tracks, 128 vias |
| DRC before → after | 102 → **not measured** (no session) | **5 → 324** |

**The escape rate reproduces to 0.3 points at 16× less area (70.71 cm² vs 491.73 cm²).** That is the
cleanest evidence in this report that the blocker is per-pin escape, not board congestion: give the
router a fourteenth of the board and the same 22 % of pins still cannot leave their pads.

The cell's DRC cost, by type (`21_import_cell1.json`): **319 rows added** — `annular_width` 110,
`via_diameter` 96, `track_width` 53, `connection_width` 27, `copper_edge_clearance` 21,
`via_dangling` 12. Read them carefully, because 218 of them are mine, not the router's:

* **218 via rows** (110 annular + 96 diameter + 12 dangling): the tile's DSN asked for **0.600 mm /
  0.300 mm** vias = a **0.150 mm ring**, and the board's rule is a **0.200 mm** ring. That is the
  same 0.150 ring the *existing* 28 vias on the board already fail (70 of the 102 baseline rows are
  annular). It is a DSN-settings artefact of this control, not a routing failure.
* **80 track/neck rows**: freerouting drew **0.1874 mm** tracks and 0.150 mm necks where the minimum
  is 0.200 mm, and 21 rows run to the synthetic tile rim. These are the router's own rule
  violations: it does not honour a 0.200 mm minimum it was given.

So even the *bounded* run does not hand back manufacturable copper, and its 36.4 % is achieved
before any of the 3.6-vs-9.43 mm power-corridor question is asked.

## 3. Failure diagnosis

Four candidate explanations were tested against counts. **Two of them are eliminated, and the
answer is the third and fourth.**

### 3.1 It is not area. Measured free area per layer

`17_freearea.py` → `17_freearea.json`: union of **all** copper on the layer (pads through KiCad's
own shape code, track capsules, via discs, zone **fills**), dilated by 0.200 mm so that "free" means
free for a track with its clearance; the board polygon is the frame.

| layer | bare copper | after clearance dilation | **free** | nets present |
|---|---:|---:|---:|---:|
| F.Cu | 184.10 cm² (37.4 %) | 213.95 cm² (43.5 %) | **278.36 cm² (56.5 %)** | 666 |
| In1.Cu | 345.01 cm² (70.1 %) | 360.14 cm² (73.2 %) | 132.17 cm² (26.8 %) | 92 |
| In2.Cu | 147.73 cm² (30.0 %) | 161.22 cm² (32.7 %) | **331.09 cm² (67.3 %)** | 92 |
| B.Cu | 353.90 cm² (71.9 %) | 371.55 cm² (75.5 %) | 120.76 cm² (24.5 %) | 92 |

**730 cm² of clearance-free space remains on three layers for 540 unrouted nets.** At 0.2 mm track
and 0.2 mm space that is a routing capacity of roughly 1.8 km of track. "The board is too dense" is
not supported by this measurement: 2.88 % routed is a *layout* fact, not a capacity fact.

### 3.2 It is not the fine pitch alone — the escape is what breaks

Every footprint is on the top side (**0 of 687 on B.Cu**), so all 3,454 pads must escape *downwards*
through one layer, and F.Cu is 43.5 % occupied before a single signal is drawn. freerouting's fanout
stage — which only asks "can this pin have a stub and a via" — could not do it:

```
2,617 of 2,779 SMD pins needed fanout
13 passes, stopped after 3 with no progress
escaped 2,149 / 2,759 = 77.9 %     ->  610 SMD pins have no legal via at all
extra free vias the escapes consumed: 825+90+28+10+5+3+0+0+1+1+0+0+0 = 963
```

**610 pins (22.1 %) are blocked before any net competes with any other net.** That is the
single-sided constraint showing up as a number: on a two-sided board those pins would escape to the
other side directly. Wave 5's independent escape census on the same footprints splits them the same
way: 202 pins are footprint-intrinsic (no escape at any placement) and 230 are placement-sensitive.

### 3.3 It IS copper width — the corridor measured at the ampacity the build is rated for

§4 measures the phase corridor at **4.400 mm of free gap → 4.000 mm passable → 3.600 mm DRC-clean**,
against **9.427 mm** required for 36.6 A on one 105 µm outer. That is **18.2 A of copper for a
36.6 A phase**. No router can beat a corridor that does not exist; this is a geometry result, not a
search result.

### 3.4 It IS a rule conflict, and the router says so itself

| conflict | count | consequence |
|---|---:|---|
| same-net `FixedVia ↔ FixedVia` clearance rows freerouting raises on load | **1,872** | the design is scored as 1,872 violations deep; freerouting refuses to fix any of them and starts from that state |
| `HIGH_CURRENT` class rule the DSN carries | **6.000 mm** track | it asks for 6.000 mm in a corridor that offers 4.000 mm — one outcome only: an unrouted item |
| `(clearance 50 (type smd_smd))` the KiCad exporter writes | **50 µm** pad rule | it would license the router to route pads to a 50 µm gap, i.e. to a board nobody can etch; patched to 200 µm in the tile DSN (§2.4), and the full-board DSN at 0.200/0.200 is clean of it |

The class table in `base3oz.kicad_pro` is the root of it: `HIGH_CURRENT 6.0 mm`, `POWER 0.8 mm`,
`GATE_DRIVE 0.5 mm` — a rule set written for a board whose corridors are 7–15 mm wide, exported onto
a board whose phase corridor is 4.4 mm. The router is being asked to satisfy a rule the copper
cannot satisfy, and it spends its budget on exactly that.

### 3.5 What the counts do and do not support

* **Not supported:** "the router failed because the board is dense." 56.5 % of F.Cu and 67.3 % of
  In2 are free.
* **Not supported:** "fine pitch makes it unroutable." The gate drive (0.5 mm) and the Kelvin shunt
  sense (0.25 mm) route with 3.4× and 27.6× margin around the same QFN/TOLT footprint (§4.1).
* **Supported:** 610 pins cannot escape at all, and every power net on the board is asked to be
  wider than its corridor. Those two facts account for the population that stays unrouted.

## 4. Manual route of one phase block — drawn, not asserted

The block is one hierarchical sheet, `/Motor 1 power cell/` (N = 1): **96 footprints, 81 nets,
587 pads**, footprint extent **86.27 × 80.03 mm = 69.04 cm²** (`02_block_probe.py`), which is
essentially wave 5's 88.367 × 82.130 = 72.576 cm² re-measured off this board. The unit of six.

The method is wave 15's validated corridor instrument (`esc-corridor-instrument/corridor_lib.py`,
imported unchanged): copper through KiCad's own `TransformShapeToPolygon`, zones by their **fill**
(with holes), obstacles = **all foreign copper on the layer**, terminals seeded **by region** (a
FET pin here is a 7-lead + tab group, so "first pad with that number" is wrong), and the measured
quantity is the **maximin inscribed-disc width** — the largest *t* for which the two terminals stay
connected through `distance-to-foreign-copper > t`. `gap = 2t`, `passable = 2t − 2·0.200`.
Then a corridor path through that free space is emitted as real `PCB_TRACK` segments — each segment
at `2·min(d along it) − 2·clearance − 0.30 mm` (the 0.30 is a raster-resolution safety derate).

### 4.1 The four connections, measured

`15_manual_route_v8.py` → `15_manual_v8.json`, board `work/manual_block1_v8.kicad_pcb`.

| connection | layer | required | free gap | passable at 0.2 clr | drawn (DRC-clean) | capacity delivered | % of requirement |
|---|---|---:|---:|---:|---:|---:|---:|
| `/M1_PHASE_A` Q1101.1 → Q1102.9 (hi↔lo bridge) | F.Cu | 9.427 | 7.300 | 6.900 | 6.40 (min) | 27.6 A | **73.2 %** |
| `/M1_PHASE_A` Q1102.9 → **J1102.1 motor terminal** (31 mm) | F.Cu | 9.427 | **4.400** | **4.000** | **3.60 (min)** | **18.2 A** | **42.4 %** |
| `/M1_GHA` Q1101.8 → R1101.2 (gate drive) | F.Cu | 0.500 | 2.100 | 1.700 | 0.500 | 4.35 A | **340 % (passes)** |
| `/M1_SHA_I` Q1102.1 → R1120.1 (shunt sense) | F.Cu | 0.250 | 7.300 | 6.900 | 0.250 | 2.63 A | **2760 % (passes)** |

**The block routes — and the phase corridor it routes is 3.60 mm wide where the affordable build
needs 9.427 mm.** That is 18.2 A of phase current, against the 36.6 A the configuration is rated
for and the 43.5 A the machine wants. The gate drive and the Kelvin shunt sense route with 3.4× and
27× margin — the block's problem is not fine pitch and not the driver, it is one 31 mm run of
power copper to the motor terminal.

The 6.4 mm bridge is not a corridor at all: the high-side source row (Q1101.1, 7 leads at
y 62.29–65.66) and the low-side drain group (Q1102.9, 9 pads from y 67.56) are **1.9 mm apart**, so
the phase node is a 2.5 mm long bridge, and a 6.4 mm wide track there is a ribbon, not a route.

### 4.2 Is it clean?

| | |
|---|---|
| `kicad-cli pcb drc` on the unrouted refilled board | **102** |
| `kicad-cli pcb drc` on the routed block board | **102** |
| row-level set diff (`14b_setdiff_v8.py`) | **ADDED 0 · GONE 0 · unchanged 102** |

**Routes cleanly, zero DRC cost.** Two earlier versions did not and are kept because they show
where the margin is: v6 drew each connection at one uniform width (the global maximin) and produced
`shorting_items` — the 6.73 mm ribbon swept into the high-side FET's BATP tab; v7 sized each
segment from its local clearance with only a 20 µm safety and produced **5 `clearance` rows** off
the 0.05 mm raster. **The corridor sits inside 0.2 mm of the DRC limit; a route at the geometric
maximum is not a manufacturable route.** 0.30 mm of derate is what makes it clean, and it is paid
out of the 3.6 mm above.

### 4.3 What it connects, and the area it costs

| | |
|---|---|
| connectivity, KiCad `GetUnconnectedCount` | 1,542 → **1,541** (one join registered) |
| connectivity, independent geometric graph (`16_check_joins_v8.py`) | `/M1_PHASE_A` 5 groups → **3 components**, `/M1_GHA` 3 → **2**, `/M1_SHA_I` 3 → **2** = **4 ratsnest joins closed** |
| segments added | 154 → **234** (80) |
| copper area added | **161.4 mm²** (bridges 18.2, corridor 137.4, gate 5.4, sense 0.5) |
| block tile | **69.04 cm²** (86.27 × 80.03) |
| ×6 for the six channels | **414.3 cm² of the board's 491.73 cm²** |

The 4-closed-ratnest figure is stated twice because the two instruments disagree and the honest
number is the geometric one: KiCad's counter moved by 1, while the graph of pad groups and drawn
capsules shows 4 joins (three groups of `/M1_PHASE_A` in one cluster). Either way **4 of the block's
~66 open ratsnest lines closed — 6 % of one sheet, 0.26 % of the board.** This is a corridor
demonstration, not a routed block; nobody should read it as one.

## 5. Verdict

**NO — the ESC is not routable at 4-layer 3 oz with the affordable 34.5 A / 36.6 A configuration, and
the reason is copper width plus single-sided escape, not the router.**

The four measurements that carry it:

1. **The unit of six does not route.** One cell — 95 footprints, 497 pads, 96 nets, 70.71 cm² — run
   to completion in 5 min 8 s by the same router at the same 0.200 mm rules: **114 of 313 (36.42 %)
   routed, 199 left, 319 new DRC rows.** That is the *charitable* case: pads only, no planes to
   negotiate, a fourteenth of the board.
2. **The phase corridor is 3.9× short before routing starts.** Measured free gap to the motor
   terminal **4.400 mm → 3.600 mm DRC-clean → 18.2 A**, against the **9.427 mm / 36.6 A** the
   affordable build is rated for. Six of those corridors are the board's power spine. This is
   geometry, not search: no router can beat a corridor that does not exist, and this report drew the
   best possible track through it (DRC-clean, ADDED 0).
3. **22 % of pins cannot escape.** 610 of 2,759 SMD pins fail fanout on the full board; **77.6 %**
   escape on a 70.71 cm² tile vs **77.9 %** on the 491.73 cm² board. The identical rate at 16× the
   area is the proof that this is the single-sided constraint (0 of 687 footprints on B.Cu) and the
   footprint set, not congestion.
4. **Neither area nor density is the limit.** 56.5 % of F.Cu and 67.3 % of In2 are clearance-free
   after dilation — 730 cm² of free space for 540 unrouted nets; 2.88 % routed is a layout fact, not
   a capacity fact.

### 5.1 What must change, in the order of what buys the most

| change | what it fixes | already costed |
|---|---|---|
| **Six layers with 4 oz inner phase/rail planes** (3/4/1/1/4/3) | an inner phase plane needs **23.34 mm** of width at 4 oz, which the board has — the 3.6 mm F.Cu corridor stops being the only path | `esc-layer-cost`: ~**2×** the 4-layer price, and the settled position is that six layers alone is *necessary but not sufficient* |
| **Lower current** — a ~18–22 A phase machine | a 3.6 mm × 0.105 mm corridor carries **18.2 A**; that is what this copper is | free, but it is a different aircraft |
| **The shunt-land fix + six layers** | the only path to the wanted 43.5 A (11.963 mm on F.Cu) | ~2×, per `esc-3oz-build` |
| **More area** | **nothing.** +28 % area bought −11.9 % corridor (settled), and this run measures the same escape rate at 70.71 and 491.73 cm² | do not spend it |
| **Fewer parts / two-sided assembly** | the 610 blocked pins. Wave 5's census of this same footprint set finds **202 pads with no legal escape at any placement** and 230 that are placement-sensitive, so a different package or the other side of the board is the only lever | the owner's single-sided constraint is what forbids it |

### 5.2 What is explicitly NOT claimed

* The full-board arm produced no session file inside 90 minutes — 88 min 28 s inside a single autorouter pass, 7,267 CPU-s, stopped — so it proves nothing about the other 1,428 connections. Nothing here says the *other* 1,428 connections are unroutable
  — only that this router, in this budget, on this board, did not route them.
* The manual block route is **4 ratsnest joins of one sheet's ~66**, i.e. **0.26 % of the board**.
  It is a corridor demonstration with a DRC receipt, not a routed block.
* No claim is made that 6 × 36.42 % = the board. Shared nets cross cells (6 × 313 = 1,878 > 1,542),
  so the cell rate is reported as a sample, not multiplied.

---

### Artefacts

| file | what it is |
|---|---|
| `00_probe.py/.json` | 3 boards measured: repo, base3oz, s3oz (the power-first placement has 0 tracks, 0 zones, 2,196 unconnected — it is not the build of record) |
| `01_dsn.py/.json` | DSN export and its census |
| `02_block_probe.py/.json`, `03_terminals.py/.json` | the block's refs, nets, extent, and every power-net pad |
| `04b_debug.py`, `04_manual_route.py`, `05_manual_route_v2.py`…`05_manual_route_v4.py` | corridor measurement, first (flawed) draws, kept for the record |
| `06_verify_manual.py`, `06b_zonecheck.py`, `09_check_joins.py` | DRC set diff, zone-fill check, join graph |
| `07_refill.py/.json` | the stale-fill finding |
| `10_manual_route_v6.py`, `13_manual_route_v7.py`, `15_manual_route_v8.py` | the three drawn versions (v6 shorts, v7 +5 clearance, v8 clean) |
| `12_ratsnest.py` | `RunOnUnconnectedEdges` needs a `std::function`; the SWIG signature takes two arguments and this build rejects a Python callable — recorded so the next unit does not try |
| `14b_setdiff_v8.py/.json` | the row-level set diff of record |
| `17_freearea.py/.json` | free area per layer after 0.200 mm clearance dilation |
| `18_intrablock.py/.json` | inconclusive: the cell-of-a-net rule it used classifies every shared rail as one cell, so the 666/0 split means nothing. Kept only so nobody builds on it |
| `19_tile.py` / `work/cell1.*` / `logs/cell1*.log` | the one-cell control: tile, DSN, session, log |
| `21_import_cell1.py/.json` | cell control: import, refill, DRC, set diff (114 of 313 routed, 319 rows added) |
| `work/runA_p1.ses` | absent by construction — the full-board run wrote none (see §2.2) |
| `logs/runA_p1.log` | the full-board freerouting log: fanout census, 1,872 pre-existing violations, the unfinished pass |




