# fab-da-radical — rip-up vs board growth on drone-arm's 17 non-through vias

**Question (single):** two approaches that have NOT been tried — (1) a radical rip-up of ALL copper
within 6/10/15 mm of U10, then via-first re-placement; (2) local board growth of +2/+4/+8 mm on the
edge nearest U10, with the escape corridors in the new area. Which works, and what does it cost?

**Input board:** `evidence/fab-da-path/da_main_rev_b_path6L.kicad_pcb` (sha256 `DE80636F…`,
2,270,141 B, 6 copper layers, 337 vias, **17 non-through**). Re-derived here, not trusted.
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/fab-da-radical/`. Copies only; nothing
written into a repo.

> **HEADLINE — the rip-up works and the growth does not, and neither is shippable.**
> **(1) Radical rip-up: 9, 10 and 7 of 17** kept (attempted 17 each) at **6 / 10 / 15 mm**. It does
> break the 0.85 mm ceiling — a legal 0.60/0.30 through-via site exists within 2.5 mm for **17 of 17**
> at every radius, where wave 18 found **0 of 19** in place — but the binding obstruction at each
> *original* site after erasing everything within 10 mm is a **pad in 17 of 17** cases (only 2 of 17
> sites are freed), and the erasure cuts 42–49 nets: **unconnected 0 → 59 / 81 / 86**. The 10 mm board
> reaches **non-through 0, min drill 0.200**, but with **81 unconnected, 45 dangling tracks, 8 dangling
> vias**. **(2) Board growth: new area admits legal vias (54/162/378 of 81/189/405 sampled points,
> min margin +0.200 mm) at +280 / +560 / +1,120 mm² (+2.00 / +4.00 / +8.00 %), DRC set diff `{}`,
> unconnected 0 — and gains 0 of 17 vias**, because growing an outline can only move it *away* from
> the blocked row: U10's pad row → edge goes 45.05 → 47.05 / 49.05 / **53.05 mm**. Best: rip-up at
> 10 mm. Final non-through **0**, area **14,000 mm²**, **not acceptable** — the 7 remaining vias were
> deleted, not converted: 10 converted, 7 gone with their fan-out.

---

## 0. Instrument validation before any number is trusted

The input reproduces wave 18's shipped board exactly, on both tools:

| check | value here | wave 18 value | how |
|---|---|---|---|
| copper layers | 6 | 6 | `s0_dump.py` |
| vias / non-through | 337 / **17** | 337 / **17** | `s1_verify.py`, span from `CuStack()` pair |
| by layer pair | F→In1 6 · In1→In2 5 · F→In2 2 · In2→B 3 · In1→B 1 | identical | same |
| non-through stacks | 14 | 14 | same |
| DRC, own rules | `{via_diameter: 6}` | `{via_diameter: 6}` | `kicad-cli pcb drc --format json --severity-all` |
| DRC, no-HDI gate | `22 = 16 microvia + 6 via_diameter` | identical | `no_hdi.kicad_dru` + same command |
| unconnected | 0 (`kicad-cli`) / 0 (`pcbnew`) | 0 / 0 | both tools |
| min drill | 0.100 (16 vias) | 0.100 | `s1_verify.py` |
| RF void A / B | 4.1699 mm² = 9.8338 % / 3.8754 = 9.1392 % | identical | `s5_void.py` |
| board | 140.000 × 100.000 = **14,000.0000 mm²** (`GetBoardPolygonOutlines`); U10 at (59.000, 50.000) | 14,036 quoted | `s2_radii.py` |

The 14,036 in wave 18 is the **edge-stroke bounding box** (140.15 × 100.15 mm, which includes the
0.15 mm `Edge.Cuts` line width); the outline polygon itself is 14,000.0000 mm². Both are right about
different objects and the difference is 0.26 %; this report uses the polygon, and the growth numbers in
§2 are on the same basis so the percentages are comparable.

**Three instrument faults caught in this wave, each of which produced a plausible wrong number:**

1. **A 0.15 mm stub is illegal on this board** (`m_TrackMinWidth` = 0.200). The first apply pass used
   0.15 and DRC returned **22 `track_width` violations** that looked like rip-up damage but were my
   own geometry. Re-run at 0.20.
2. **A min-over-vertices test called a crossing stub legal.** `vgeom.stub_ok` measured segment-to-pad
   distance as min over the pad's vertices, which is blind to a segment that enters and leaves a
   polygon between vertices. The first pass **shorted 7 nets**. Fixed to exact segment↔polygon
   (0 if any edge crosses, else nearest edge) — shorts went to 0.
3. **`pcbnew.SHAPE_POLY_SET(other)` copy-constructs a `SHAPE` in KiCad 9.0.7's Python**, and the next
   `LoadBoard` in the same process returns a board whose `Tracks()` is not iterable. Every radius now
   runs in its own `pcbnew` process, and clipping is done with `BooleanAdd` into a fresh set.

One counting note so the tables are comparable: `PCB_VIA` subclasses `PCB_TRACK` in pcbnew, so a naive
`isinstance(t, PCB_TRACK)` sweep counts vias as tracks. `s2_radii.py` reports **410** tracks at 6 mm
for that reason; the authoritative erasure counts (376) come from `s3_erase.py`, which tests the via
class first.

---

## 1. Approach 1 — radical rip-up at 6 / 10 / 15 mm

### 1.1 What "erase all copper" actually is

`s3_erase.py R` deletes every track whose segment comes inside the disk of radius R about U10's
centre, and every via whose centre is inside it, on **all six layers**, then **refills** the zones.

The zone fill is *refilled*, not deleted. A fill is derived geometry, not authored copper: deleting it
and not refilling leaves a hole in the pour, which is a different board and would break the RF void
invariant outright. Refilling is what a rip-up does, and it is the only operation that both holds the
pour and lets the pour retract around the new vias. The pour copper that the refill re-creates inside
the disk is measured and charged separately (column below) — it is not free space, it is the same
copper coming back with the new via clearances around it.

| quantity | 6 mm | 10 mm | 15 mm |
|---|---|---|---|
| tracks erased | 376 | 696 | 806 |
| vias erased (all spans) | 34 | 64 | 81 |
| … of which non-through | 11 | **17** | **17** |
| nets cut | 42 | 48 | 49 |
| pour copper re-created in the disk | 129.10 mm² | 484.05 mm² | 1,469.19 mm² |
| … per layer (F / In1 / In2 / In3 / In4 / B) | 26.18 / 17.77 / 24.47 / **0** / **0** / 60.68 | 114.94 / 116.21 / 79.00 / **0** / **0** / 173.91 | 426.31 / 382.70 / 215.03 / **0** / **0** / 445.15 |

All 17 non-through vias sit within **r = 2.147 … 7.566 mm** of U10's centre, so 6 mm reaches 11 of
them and both 10 mm and 15 mm reach all 17. **In3.Cu and In4.Cu carry zero copper and zero pour
anywhere on this board** — the two layers wave 18 added are still empty, which is the second
independent confirmation that they change nothing.

### 1.2 Via-first placement, and the one number that decides the approach

`s4_sites.py R` searches ±2.5 mm around each original XY on a 0.10 mm grid for a 0.60/0.30 **through**
via ranked by worst-case margin over all six layers plus hole-to-hole plus copper-to-edge; then it
requires a legal **0.20 mm** stub from the owner pad to the site (on the layer the microvia started
from) and a legal **0.20 mm** trunk from the site to the nearest *surviving* same-net copper outside
the disk (on the far layer). Accepted items are inserted back into the geometry model, so each later
via is checked against the ones already placed exactly as it is against the board.

| | 6 mm | 10 mm | 15 mm |
|---|---|---|---|
| attempted | 17 | 17 | 17 |
| legal through-via site within 2.5 mm | **17** | **17** | **17** |
| **kept** (site + stub + trunk legal, DRC-clean) | **9** | **10** | **7** |
| original XY still legal — copper only | 2 of 17 | 2 of 17 | 2 of 17 |
| original XY still legal — incl. hole-to-hole | 1 of 17 | 1 of 17 | 1 of 17 |
| unconnected after erase, before via work | 62 | 85 | 86 |
| unconnected after via work | **59** | **81** | **86** |
| non-through remaining | 6 | **0** | **0** |
| min drill | 0.100 | **0.200** | **0.200** |
| RF void A / B | 4.1699 / 9.8338 · 3.8754 / 9.1392 | **identical** | **identical** |

**Definition of "kept", stated because it is easy to overclaim:** a kept row means a through via was
placed at a site legal on all six layers, with a legal 0.20 mm stub from its owner pad and a legal
0.20 mm trunk to surviving copper, and the placement added no `shorting_items`, `clearance`,
`tracks_crossing` or `track_width` violation. It does **not** mean the net still conducts — the
erasure cuts each net elsewhere, and that is charged in the unconnected row.

`s7_blockers.py` states why the original sites stay illegal, per layer, per via, before and after the
erasure. It is the row-level heart of this wave:

```
binding obstruction at the ORIGINAL XY, 0.60/0.30 through via, all 6 layers
  before rip-up : track 14, pad 2, via 1      (two sites already pad-bound)
  after  R=6    : pad 9,  track 8             — freed by the rip-up: 2 of 17
  after  R=10   : pad 17, track 0             — freed: 2 of 17
  after  R=15   : pad 17, track 0             — freed: 2 of 17
```

The two that the rip-up frees are `/PA_EN` (F.Cu, −0.425 → **+0.075**) and `/SENS_SCLK` (In1.Cu,
−0.119 → **+0.672**). Everything else is bound by a **pad** — `U10.81 /GND` at −0.225, `U10.13
/GNSS_PPS` at −0.125, `U10.3 /ICM_INT2` at −0.125, `U10.28 /CAN_SCK` at −0.125, `U10.24 /3V3` at
−0.425, `U10.17 /RF_MOSI` at −0.125, `U10.23 /RF_GPIO3` at −0.125, `C32.2 /GND` at −0.099, `C40.2
/GND` at −0.135, `C12.2 /GND` at −0.282 (and that one is illegal on **all 6 layers** at 6 mm),
`FB1.2 /3V3_ADC` at −0.650. **You cannot erase a pad**, so no radius converts these in place; the
rip-up's entire contribution is the legal *off-site* site, and the offset that comes with it is
0.000–2.596 mm (6 mm) / 0.000–0.860 mm (10 mm) / 0.300–2.302 mm (15 mm).

### 1.3 DRC on the ripped-up boards — set diffs, not totals

`s5_apply.py R` places the accepted vias, stubs and trunks, refills, and each board is gated by its own
`kicad-cli` run. Set diff against the input board:

| radius | DRC own-rules set diff | DRC no-HDI gate set diff |
|---|---|---|
| 6 mm | `{track_dangling +43, via_dangling +6, via_diameter −1}` | `{microvia_drill_out_of_range −10, track_dangling +43, via_dangling +6, via_diameter −1}` |
| **10 mm** | **`{track_dangling +45, via_dangling +8, via_diameter −2}`** | **`{microvia_drill_out_of_range −16, track_dangling +45, via_dangling +8, via_diameter −2}`** |
| 15 mm | `{isolated_copper +3, track_dangling +34, via_dangling +7, via_diameter −2}` | `{microvia_drill_out_of_range −16, isolated_copper +3, track_dangling +34, via_dangling +7, via_diameter −2}` |

No shorts, no `clearance`, no `tracks_crossing`, no `track_width` and no `isolated_copper` at 6 and
10 mm: after the two instrument fixes of §0 the placement itself is clean. What the set diff shows is
the price, and it is not a DRC artefact — `track_dangling` 34–45 and `via_dangling` 6–8 are the cut
ends of the 42–49 nets the erasure severed. The `via_diameter` *decrease* is not an improvement in
the design: those vias were deleted.

Note also that 15 mm is **worse than 10 mm on every axis** (7 kept vs 10, 86 unconnected vs 81, and it
is the only radius that produces `isolated_copper`). Past ~8 mm — the farthest of the 17 — the extra
disk adds nothing but collateral.

---

## 2. Approach 2 — local board growth at +2 / +4 / +8 mm

### 2.1 What was executed

`s6_growth.py G` moves the **south** board edge (the nearest edge: U10 sits at y = 50.000 on a
0 … 100 board, so north and south are both 50.000 mm away, west 59.000, east 81.000) outward by G mm
and extends the two vertical edges to keep the outline a closed rectangle. Three edge segments move,
no component, track, via or zone is touched, zones are not refilled (nothing under them changed).

### 2.2 Does the new area admit legal vias, and what does it cost?

The new strip is sampled on a 5 mm × 0.5 mm grid at every point more than 0.5 mm inside the new edge,
and tested for a 0.60/0.30 through via against **all six layers** of copper, hole-to-hole, and the
**grown** outline's copper-to-edge rule (0.5 mm + 0.3 mm via radius = 0.8 mm band):

| | +2 mm | +4 mm | +8 mm |
|---|---|---|---|
| board area | **14,280.0000 mm²** | **14,560.0000 mm²** | **15,120.0000 mm²** |
| added | +280.0000 (**+2.00 %**) | +560.0000 (+4.00 %) | +1,120.0000 (+8.00 %) |
| strip sample points | 81 | 189 | 405 |
| points legal for 0.60/0.30 | **54** | **162** | **378** |
| blocked, and blocked only by the mandatory 0.8 mm edge band | 27 | 27 | 27 |
| min legal margin | **+0.2000 mm** | **+0.2000 mm** | **+0.2000 mm** |
| U10 pad row → south edge | 45.050 → **47.050 mm** | 45.050 → **49.050 mm** | 45.050 → **53.050 mm** |
| DRC own-rules set diff | `{}` | `{}` | `{}` |
| DRC no-HDI gate set diff | `{}` | `{}` | `{}` |
| unconnected (`kicad-cli` / `pcbnew`) | 0 / 0 | 0 / 0 | 0 / 0 |
| vias / non-through | 337 / **17** | 337 / **17** | 337 / **17** |
| **vias gained** | **0** | **0** | **0** |

So: **yes, the new area allows legal vias — trivially, and it is the only place on the board that
does — and the area cost is +2.00 / +4.00 / +8.00 %.** It buys nothing, for one reason that the table
makes unavoidable: **growth moves the outline away from U10.** The blocked row is 45.050 mm from the
nearest edge; +2/+4/+8 mm makes that 47.050/49.050/53.050 mm. A corridor placed in the new area
starts 47–53 mm from the pad row it is meant to serve, and the 45.05 mm in between is already
populated board that growth cannot empty. The growth is DRC-neutral and connectivity-neutral — a
clean, free, useless change.

The corollary quantifies the ceiling: to bring new area *to* the row you would have to extend the
outline by 45.05 mm, i.e. 140 × 45.05 = **6,307 mm² = +45.1 %** of the board, and even then the
"new" region would be the old routed region, not empty space. The board-growth framing cannot work
for a component in the middle of a 140 × 100 board.

---

## 3. Verification of the best result — rip-up at 10 mm

`work/rip10_applied.kicad_pcb` (the highest conversion count: 10 of 17, 0 non-through, 0 shorts).

| check | base (6L, 17 non-through) | **rip-up @ 10 mm** | how |
|---|---|---|---|
| copper layers | 6 | **6** | `s1_verify.py` |
| vias total | 337 | **283** (−64 erased, +10 placed) | same |
| **non-through by span** | **17** | **0** | span from `CuStack()` pair |
| by layer pair | F→In1 6 · In1→In2 5 · F→In2 2 · In2→B 3 · In1→B 1 | **{}** | same |
| non-through stacks | 14 | **0** | same |
| **DRC own-rules set diff** | `{via_diameter: 6}` | **`{track_dangling +45, via_dangling +8, via_diameter −2}`** | `kicad-cli pcb drc --format json` |
| **DRC no-HDI gate set diff** | 22 = 16 micro + 6 via_dia | **`{microvia −16, track_dangling +45, via_dangling +8, via_diameter −2}`** | `.kicad_dru` + same |
| **unconnected, `kicad-cli`** | 0 | **81** | DRC json |
| **unconnected, `pcbnew`** | 0 | **81** | `s1_verify.py` + `s5_void.py` |
| **minimum drill** | 0.100 | **0.200** | `s1_verify.py` |
| drill histogram | 0.35 × 281 · 0.30 × 34 · 0.20 × 6 · 0.10 × 16 | **0.35 × 242 · 0.30 × 37 · 0.20 × 4** | same |
| **RF void A** | 4.1699 mm² = 9.8338 % | **4.1699 / 9.8338 — bit-identical** | `s5_void.py` |
| **RF void B** | 3.8754 = 9.1392 % | **3.8754 / 9.1392 — bit-identical** | same |
| **board area** | 14,000.0000 mm² | **14,000.0000 mm²** (outline untouched) | `s2_radii.py` |
| conversion record | 17 non-through | **10 converted to legal through vias, 7 deleted with their fan-out** | `plan_R10.json` |

Two honest notes on that table. The **RF void is preserved exactly** because **0 of the board's 70
`RF_50R` tracks lie inside any of the three disks** (measured at 6, 10 and 15 mm) — the invariant is
held structurally, because the rip-up never reaches RF class copper, not because the pour was
protected. And the **"non-through 0" is not a conversion record**: 10 of the 17 became through
vias, and the other 7 were *deleted* — their nets are among the 81 unconnected. A count of zero
non-through vias is only a win if the copper still conducts, and here it does not.

---

## 4. Final count, area, and the honest remaining work

**Approach 1:** 9 / 10 / 7 of 17 kept at 6 / 10 / 15 mm (17 attempted at each). **Approach 2:** 0 of
17 at every size, at +2.00 / +4.00 / +8.00 % area.

**Best: the rip-up at 10 mm.** Final **non-through count 0** of 283 vias, min drill **0.200**, board
area **14,000.0000 mm²**, RF void **4.1699 mm² / 9.8338 %** unchanged — and **not acceptable**:
**81 unconnected** on both tools, 45 dangling tracks, 8 dangling vias, 7 vias deleted rather than
converted.

**What this wave actually established, in the order the evidence supports:**

1. **The 0.85 mm ceiling is breakable, and this is where it breaks.** Erasing all copper in a 10 mm
   disk creates a legal 0.60/0.30 through-via site within 2.5 mm for **17 of 17** vias, against
   **0 of 19** in place from wave 18. That is the rip-up's real result: the site problem is solvable,
   it just is not solvable *at the site*.
2. **It is solvable at the site for 2 of 17 only**, and the reason is pad copper: after the 10 mm
   erasure the binding obstruction is a **pad in 17 of 17** cases (`U10.81 /GND` −0.225, `FB1.2
   /3V3_ADC` −0.650, `C12.2 /GND` −0.282 …). A pad cannot be erased, moved, or shrunk here — C12,
   C32, C40 and FB1 are 0402/0603 bypass parts 0.4–1.0 mm from U10's land, and wave 18 already
   measured 0 of 15 local edits and 0 of 11 south-west re-escapes as legal.
3. **The price of the erasure is the whole board, not the ring**: 42–49 nets cut, 59–86 unconnected,
   34–45 dangling track ends. Re-routing that is strictly more work than the 25–40 h fan-out job the
   incremental path already costed, so the radical rip-up is **not a cheaper route to the same
   place — it is a more expensive one**.
4. **Board growth is the wrong axis.** The new area is legal, free of collateral, and 47–53 mm from
   the pad row; growth increases the distance it was supposed to reduce. For a mid-board component
   the growth framing is dead, and it is dead by 45.05 mm.
5. **What is left is the same two doors wave 18 left open, now with the geometry proof attached:**
   the agent-board's own HDI 1+2+1 build (all 17 are `MICROVIA`/`BLIND_BURIED` by pair, legal at
   0.10 mm laser drill, and the board already declares them) — a decision, not work; or the
   LQFP-100, which buys 0.075 mm of a 0.125 mm shortfall, i.e. still not 0.85 mm, for 20 moved
   footprints and a firmware rewrite from absent source. Neither is unlocked by anything measured
   here.

### Artefacts

| file | note |
|---|---|
| `work/rip10_applied.kicad_pcb` | **the best rip-up result**: 10 of 17 converted, non-through 0, min drill 0.200, unconnected 81 |
| `work/rip6_applied.kicad_pcb`, `work/rip15_applied.kicad_pcb` | the other two radii (9 and 7 kept) |
| `work/rip6/10/15.kicad_pcb` | the erasure alone, before any via — the receipt for the collateral (62/85/86 unconnected) |
| `work/grow2/4/8.kicad_pcb` | the three grown outlines (+2/4/8 mm on the south edge) |
| `drc/own_base.json`, `gate_base.json` | the input board's two DRC runs |
| `drc/own_rip{6,10,15}.json`, `gate_rip{6,10,15}.json` | every rip-up gate |
| `drc/own_grow{2,4,8}.json`, `gate_grow{2,4,8}.json` | every growth gate (all set-diff `{}`) |
| `scene.json`, `erase_R{6,10,15}.json` | the scene, and what each radius erases |
| `plan_R{6,10,15}.json`, `blockers_R{6,10,15}.json` | every attempt, kept or not; blocker identity per layer |
| `grow_R{2,4,8}.json`, `census_rip{6,10,15}.json`, `census_grow8.json`, `void_measure.json` | area/legality, census, and RF void for every board |

Scripts in the order they matter: `s0_dump.py` (inventory) · `s2_radii.py` (scene: U10, edges,
edge distances, erasure envelope) · `s3_erase.py R` (rip-up; one process per radius) · `s4_sites.py R`
(via-first site + stub + trunk search, incremental geometry) · `s5_apply.py R` (place, refill, save) ·
`s6_growth.py G` (board growth + strip legality) · `s7_blockers.py R` (what binds the original XY) ·
`s1_verify.py` (span census, min drill, unconnected) · `s5_void.py` (RF void, both tools).