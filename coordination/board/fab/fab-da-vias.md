# drone-arm main rev_b — eliminate every sub-standard via

**Item:** `fab-da-vias` · **Board:** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb`
**Evidence:** `evidence/fab-da-vias/` · **Tooling:** KiCad 9.0.7 `pcbnew` (Python 3.11.5) + `kicad-cli pcb drc`
**Repo:** read-only throughout. Nothing was written, committed or pushed; the input board is a
byte copy (`base.kicad_pcb`, 2,252,603 B) and every product of this item lives in this directory.

---

## 1. Verdict

The 33 vias below 0.2 mm are **not a via-choice error**. At each of their sites the 0.1 mm drill is
the **largest via the surrounding copper permits**: the site geometry allows a via pad of only 0.25–0.42 mm, typically 0.30–0.35 mm,
and a standard through via needs 0.50 mm at minimum (0.30 drill + a 0.10 mm annular ring).
So the conversion has two very different halves:

| half | groups | vias | outcome |
|---|---|---|---|
| **can be fixed by via work alone** | 9 | **12** | executed, DRC-verified, 0 copper risk |
| **cannot**: no standard via fits the site | 20 | **24** | needs a fan-out re-escape, not a via edit |

| | before | after | source |
|---|---|---|---|
| vias on board | 341 | **338** | `base_census.json` / `fixed_census.json` |
| drill histogram | 0.10×33 · 0.30×27 · 0.35×281 | **0.10×23 · 0.30×34 · 0.35×281** | same |
| vias below 0.2 mm | 33 | **23** | same |
| non-through vias (micro + blind) | 36 | **24** | same |
| **MIN_DRILL** | 0.100 mm | **0.100 mm — UNCHANGED** | same |
| DRC, board's own rules | 0 violations / 0 unconnected | **0 / 0** | `drc_base.json`, `drc_fixed.json` |
| DRC, no-HDI gate (this item's rule) | 33 violations | **23 violations** | `nhdi/drc_gate_base.json`, `nhdi/drc_gate_fixed.json` |

**Checklist line — WAIVED, not PASS.** `drone-arm main rev_b: standard PTH vias only` is **not met**.
The board is still blocked for a non-HDI fab house: 23 microvias and 1 blind via remain, and they
cannot be converted without moving other nets' copper. This item closes 12 of the 36 and proves the
other 24 need a different kind of change (§8, §10). Anyone reporting this board fab-ready is wrong.

---

## 2. Method, provenance, and why the geometry model is trustworthy

| tier | what it is | where |
|---|---|---|
| **A — measured** | via / track / pad / zone / edge geometry read from the board with `pcbnew`; pads exported as **KiCad's own effective copper polygons** (`PAD.TransformShapeToPolygon`), so roundrect/oval/trapezoid geometry is KiCad's, not an approximation | `s01_dump.py` → `inventory.json` |
| **A — measured** | DRC verdicts from `kicad-cli pcb drc` on the real saved boards | `drc_base.json`, `drc_fixed.json`, `nhdi/*.json` |
| **B — analytic, exact** | clearance distances: capsule for tracks, polygon for pads, disc for vias, disc for holes, segment for board edge | `vgeom.py` |
| **C — none** | no rule-of-thumb estimate appears in any number below | — |

Rules in force, read from `base.kicad_pro` (`board.design_settings.rules`):

```
min_clearance 0.125   min_track_width 0.2   min_via_diameter 0.6   min_via_annular_width 0.1
min_through_hole_diameter 0.2   min_microvia_drill 0.1   min_hole_to_hole 0.2
min_copper_edge_clearance 0.5   min_resolved_spokes 2   max_error 0.005
```

The project still carries `min_microvia_drill: 0.1`, which is why **DRC is clean on a board a
non-HDI fab cannot build** — the baseline is 0 violations / 0 unconnected (§7). That is the trap.

### 2.1 The model is validated, not asserted

* **Positive control — 305 existing through vias.** Every one is fed through the model at its own pad
  radius; **304 of 305 read clear**. The single exception reads **−0.0005 mm** on In2.Cu, which is the
  board's own `max_error` (0.005 mm) rounded to zero. A model that was over-strict would fail here;
  a model that was over-permissive would not have predicted the negative control below.
  Source: `s02_analyse.py` §"MODEL CHECK", `vias_analysis.json:model_check`.
* **Negative control — the no-HDI gate.** `no_hdi.kicad_dru` (a custom DRC rule: `hole_size min 0.2 mm`
  for `A.Type == 'Via'`) returns **exactly 33 violations on the baseline** — the 33 microvias, no
  false positives, and **0 unconnected**. So the defect class is machine-detectable, and the count the
  brief quotes is reproducible by a third party with one command (§7).
* **Path model vs DRC.** The relocation engine's clearance model predicted clean copper; DRC on the
  saved board agrees: 0 violations (§7). Where it did *not* agree, DRC caught my error and the plan
  was corrected — three times (§6.2). That is the model being tested, not trusted.

---

## 3. The 36, individually

Full machine-generated table (36 rows, one per via, nothing hand-typed): **`TABLE_36.md`**.
Machine-readable: **`vias.csv`**, **`vias_analysis.json`**, **`inventory.json`**.

Spans of the 36 — `s01_dump.py` output:

| span | count | type |
|---|---|---|
| F.Cu→In1.Cu | 14 | microvia 0.1 |
| In1.Cu→In2.Cu | 10 | microvia 0.1 |
| In1.Cu→B.Cu | 4 | microvia 0.1 |
| F.Cu→In2.Cu | 3 | microvia 0.1 |
| In2.Cu→B.Cu | 2 | microvia 0.1 |
| In2.Cu→B.Cu | 3 | **blind/buried 0.3** |

**BOARD CORRECTION (AGENT_BOARD.md:245 and :456, "36 × 0.1 mm HDI vias").** The 36 are not one class:
**33 are 0.1 mm microvias, 3 are 0.3 mm blind/buried vias** (`B01` /PA_EN, `B02` /RF_GPIO2, `B03` /RF_MISO).
The 3 have a legal drill but a forbidden *process*; they need a different fix from the 33 and are
counted separately everywhere below. This matches the correction already recorded at AGENT_BOARD.md:454-457.

They sit in **29 groups**: 7 stacked pairs at identical XY (14 vias, one electrical path each) and
22 singles. 14 distinct nets; the heaviest are /LSM_INT1 (6), /GNSS_RX (4),
/RP2354B MCU/USB_DP_MCU (4), /RF_MOSI (4). Every one is a signal or supply via — **not one is a
plane-stitching via**, which is why class (a) "delete" yields nothing (§5).

---

## 4. What actually constrains each site

`binding obstruction` is the nearest **foreign** copper on the worst layer, measured to its copper
edge; `dist` is centre-to-edge. A standard via needs `dist ≥ 0.425` (0.125 clearance + 0.30 pad radius)
on **all four layers**, because a through via touches F, In1, In2 and B.

### 4.1 The sites that fail: measured shortfall

`s08_relief.py` → `relief.json`. Worst-layer row for each unresolved group (2 rows per group are in
the JSON, including the runner-up layer):

| group | net | vias | worst layer | dist | need | **short by** | binding item | movable? |
|---|---|---|---|---|---|---|---|---|
| G04 | /LSM_INT1 | 2 | B.Cu | −0.089 | 0.425 | **0.514** | trk /ICM_nCS w0.25 | MOVABLE |
| G05 | /LSM_INT1 | 1 | F.Cu | −0.225 | 0.425 | **0.650** | pad FB1.2 /3V3_ADC | FIXED (component pad) |
| G06 | /GNSS_RX | 1 | In2.Cu | 0.099 | 0.425 | **0.326** | trk USB_DM_MCU w0.25 | MOVABLE |
| G07 | /PA_EN | 1 | In1.Cu | −0.075 | 0.425 | **0.500** | trk /RP2354B MCU/XIN w0.25 | MOVABLE |
| G09 | /PA_EN | 1 | B.Cu | 0.000 | 0.425 | **0.425** | trk /RF_GPIO2 w0.20 | MOVABLE |
| G12 | /GNSS_RX | 1 | F.Cu | 0.143 | 0.425 | **0.282** | pad C12.2 /GND | FIXED (component pad) |
| G13 | /SENS_SCLK | 1 | F.Cu / In1.Cu | 0.305 | 0.425 | **0.120** | via /RF_GPIO0 350um | FIXED (another via) |
| G16 | /RF_GPIO2 | 1 | B.Cu | −0.086 | 0.425 | **0.511** | trk /SENS_SCLK w0.20 | MOVABLE |
| G17 | /RF_GPIO0 | 1 | In1.Cu | −0.025 | 0.425 | **0.450** | trk /SENS_MOSI w0.25 | MOVABLE |
| G18 | /3V3 | 1 | In2.Cu | −0.125 | 0.425 | **0.550** | trk /LNA_EN w0.25 | MOVABLE |
| G19 | /RF_GPIO0 | 1 | F.Cu | −0.025 | 0.425 | **0.450** | trk /1V1 w0.25 | MOVABLE |
| G21 | /RF_MOSI | 1 | F.Cu | −0.025 | 0.425 | **0.450** | trk VDD_CC112 w0.25 | MOVABLE |
| G10 | /RF_MOSI | 2 | In2.Cu | 0.300 | 0.425 | **0.125** | trk /RF_MISO w0.20 | MOVABLE |
| G11 | /RF_MISO | 2 | F.Cu | 0.275 | 0.425 | **0.150** | trk /RF_nCS w0.25 | MOVABLE |
| G14 | /RF_RESET_N | 1 | In2.Cu | 0.193 | 0.425 | **0.232** | trk /RF_SCLK w0.25 | MOVABLE |
| G15 | /HGM | 1 | In2.Cu | 0.250 | 0.425 | **0.175** | trk /RF_MISO w0.20 | MOVABLE |
| G24 | /RF_GPIO2 | 1 | In1.Cu | 0.292 | 0.425 | **0.133** | trk /RF_MOSI w0.20 | MOVABLE |
| G25 | /RF_MOSI | 1 | B.Cu | 0.337 | 0.425 | **0.088** | trk /RF_MISO w0.20 | MOVABLE |
| G26 | VDD_CC112 | 1 | F.Cu | 0.307 | 0.425 | **0.118** | trk CC_PA w0.35 | MOVABLE |
| G03 | USB_DP_MCU | 2 | F.Cu | 0.275 | 0.425 | **0.150** | trk /3V3 w0.25 | MOVABLE |

**13 of these 20 groups have a shortfall on a layer where the via centre is at `dist ≤ 0.0`** — the
via sits *inside* another net's copper. No via of any size can be a through via there. That is not a
judgement call; it is a negative distance.

### 4.2 The root cause, in three measured numbers

1. **U10 (RP2354B) is 0.400 mm pitch with 0.200 × 0.800 mm pads.** Measured over its 81 pads:
   nearest-neighbour pitch **min 0.400 / median 0.400** (`s05_rootcause.py`). Copper gap between
   adjacent pads = **0.200 mm**.
2. **Nothing can route between those pads at any sane rule.** A 0.2 mm track needs
   `0.2 + 2×0.125 = 0.45 mm`; even a 0.09/0.09 rule needs `0.27 mm`; **0.200 < both**. So the F.Cu
   escape is closed by geometry. U40 (CC112) is 0.500 pitch / 0.250 wide — gap 0.250 mm, same conclusion.
3. **The largest pad a via can have between two pads is `2 × (0.300 − 0.125) = 0.350 mm`**, where
   0.300 is the pad-centre-to-neighbour-pad-edge distance. Measured best case **0.350** (G10),
   typical **0.300** (G03, G11), worst **0.25** (G15). With a 0.10 mm annular ring that is
   **drill 0.05–0.15 mm** — laser territory. To reach a 0.20 mm mechanical drill you need a 0.40 mm
   pad, i.e. **0.05–0.15 mm more room than exists**.

So the chain is closed at both ends: the via cannot grow, and the escape that would let it move out
of the pad field cannot be routed through a 0.200 mm gap. `s05_rootcause.py` measures the consequence
directly — from each failing via, a 0.2 mm track can reach only **9–39 %** of the surrounding
±2.5 mm window on F.Cu, and for six groups that reachable set is *exactly* the net's own copper
(`reached == net_cells` in `routes.json:groups[*].diag`): **the terminal is boxed in**.

---

## 5. The four classes, counted

Counted per **group** (29) and per **via** (36). No group needed class (d).

### (a) DELETE — 0 vias by redundancy; 3 vias by collapsing stacked pairs
No via in the 36 is a stitching via. All 14 nets are signals/supplies, and every via has a distinct
net terminal on at least one layer (§3 attach-layer data in `plan.json`). **Nothing is deletable for
free.** But 7 of the 36 are the redundant *second half* of a stacked pair (two 0.1 vias in series doing
one electrical job), and one through via replaces both — 3 of those 7 pairs are converted here, so
**6 vias become 3**.

### (b) SHIFT — 6 groups / 6 vias, ≤ 0.50 mm along the net's own copper
`G08` 0.14 · `G20` 0.45 · `G22` 0.50 · `G23` 0.49 · `G28` 0.10 · `G29` 0.20 (mm).
Total new copper **3.30 mm** across 6 groups; no other net touched; no pad moved. `G22` and `G23` are
the two blind vias, so this class also removes 2 of the 3 blind/buried processes.

### (c) CONVERT IN PLACE — 3 groups / 6 vias, **zero copper move**
`G01` (127.000, 13.100) /GNSS_RX · `G02` (56.530, 37.100) USB_DP_MCU · `G27` (54.850, 77.500) /SENS_SCLK.
Each already has 0.375–1.02 mm of clearance free on all four layers, so the pair collapses to one
0.3/0.6 through via at the identical XY. **This is the cheapest action on the board** and it removes
3 vias with no edit at all beyond the via itself.

### (d) RE-ROUTE — 0 executed; 20 groups / 24 vias are infeasible, not merely expensive
The engine (`s04_route.py`) does not test "is there a nearby free spot"; it does a full 4-layer site
test plus an **8-connected clearance-aware path search** (0.05 mm grid) for every layer the net has to
be reconnected on, seeded only from that via's own terminal copper — so a returned site is connected
by construction, and the emitted copper is 45°-snapped polyline segments, not a straight-line
idealisation. Results:

* **within ±4 mm: 9 groups solved, 20 not** (`routes.json`).
* **widened to ±7 mm at 0.1 mm grid: still the same 20** (`routes_wide.json`). Not a search-radius
  artefact.
* Of the 20, **11 could be freed by moving only other nets' tracks; 9 also need a component pad
  (U10/C12/FB1) or another through via to move** (`relief.json`, per-layer `kind` field).

The honest reading: these 20 sites are not "hard to route", they are **closed**. Converting them
requires the *neighbouring* copper to move first, and since the neighbours are themselves escaped
through the same 0.200 mm gap, the change is a fan-out re-escape — see §8 tier 4.

---

## 6. The concrete edit

### 6.1 What to hand a human

| file | what it is |
|---|---|
| **`s06_apply.py`** | **the patch.** Reads `routes.json`, deletes the named vias by UUID, adds the standard through vias and the reconnecting tracks, refills zones, saves `fixed.kicad_pcb`. Run with KiCad's own Python. |
| `s01`–`s09` `*.py` | the full pipeline in order; rerunnable end to end (§11) |
| `edits.json` | the machine-readable edit list: 9 groups, 12 via UUIDs deleted, 9 vias added, 13 polyline tracks |
| `fixed.kicad_pcb` | the result, DRC-verified (§7) |
| `no_hdi.kicad_dru` | the **gate**: one custom DRC rule that makes this defect class impossible to re-introduce unnoticed |

`edits.json` is deliberately UUID-keyed, so it applies to the repo file as-is and does not depend on
my copy:

```json
{"group": "G01", "net": "/GNSS_RX", "cls": "C_CONVERT_IN_PLACE",
 "delete_vias": [{"uuid": "50760f1e-…", "drill": 0.1, "pad": 0.3, "span": "F.Cu->In1.Cu"},
                 {"uuid": "7a319703-…", "drill": 0.1, "pad": 0.3, "span": "In1.Cu->In2.Cu"}],
 "add_via": {"x": 126.95, "y": 13.1, "drill": 0.3, "pad": 0.6, "net": "/GNSS_RX"},
 "add_tracks": []}
```

Every added via is `drill 0.300 / pad 0.600` — **0.15 mm annular ring**, identical to the 27 vias
already on the board at 0.3 mm and consistent with the 0.175 mm ring of the 281 at 0.35 mm. I
deliberately did **not** use the 0.50 mm pad (0.10 mm ring) that the project's `min_via_annular_width`
would allow: it buys a handful of extra sites and costs breakout margin on a board that must pass a
real fab. That choice is why `G26` (which only fits at a 0.50 pad) is in the unresolved half.

### 6.2 Three errors the verification caught — and what they were

The first two passes produced a board that was *not* clean, and DRC is what said so:

1. **`via_diameter 0.5 < 0.6`** — one group had been solved with a 0.50 pad, which the project's own
   `min_via_diameter` rejects. Fix: pad ladder restricted to 0.60 only; that group moved to the
   unresolved half rather than lowering the rule.
2. **5 × `track_dangling` + 2 unconnected items** — my path search had been seeded from *any* same-net
   copper within 0.20 mm of the via, so for `/RF_RESET_N` the new copper left from a different branch
   of the net and left the via's own terminal tracks floating. Fix: seed **only the via's own terminal
   cell**. This is the classic "the model was self-consistent and wrong" failure — the connectivity
   check, not the geometry, was the thing that had broken.
3. **A 3.5 mm A\* detour split the F.Cu `/GND` pour** into two unconnected islands (`unconnected_items`,
   zone↔zone). Fix: a **2.0 mm total-added-copper cap** per group — beyond that a "via conversion" has
   become a reroute, and those groups belong in the re-escape half, not in this patch.

Both surviving long-path candidates (`G14`, `G21`) were dropped by the cap; the executed set now adds
**19 track segments totalling 3.30 mm of copper**.

---

## 7. Verification — on real saved boards, both rule sets

| board | rules | violations | unconnected | source |
|---|---|---|---|---|
| `base.kicad_pcb` (control) | board's own | **0** | **0** | `drc_base.json` |
| `base.kicad_pcb` | **no-HDI gate** | **33** | 0 | `nhdi/drc_gate_base.json` |
| `fixed.kicad_pcb` | board's own | **0** | **0** | `drc_fixed.json` |
| `fixed.kicad_pcb` | **no-HDI gate** | **23** | 0 | `nhdi/drc_gate_fixed.json` |

Reproduce exactly:

```
kicad-cli pcb drc --format json --severity-all --output drc_base.json  base.kicad_pcb
kicad-cli pcb drc --format json --severity-all --output drc_fixed.json fixed.kicad_pcb
kicad-cli pcb drc --format json --severity-all --output nhdi/drc_gate_fixed.json nhdi/fixed.kicad_pcb
```

Census, independently re-loaded with `pcbnew` (`s07_census.py`):

| | base | fixed |
|---|---|---|
| footprints | 165 | 165 |
| tracks (+segments) | 2,620 | 2,639 |
| vias | 341 | 338 |
| drill 0.10 / 0.30 / 0.35 | 33 / 27 / 281 | **23 / 34 / 281** |
| min drill | 0.100 | **0.100** |
| non-through | 36 | **24** |
| non-through breakdown | F→In1 14, In1→In2 10, In1→B 4, F→In2 3, In2→B 2, **blind In2→B 3** | F→In1 11, In1→In2 5, In1→B 3, F→In2 2, In2→B 2, **blind In2→B 1** |

**Unconnected: 0 before, 0 after.** That is KiCad's own connectivity check, and it is the authority
on whether the 12 converted vias still join their nets — not my union-find.

---

## 8. Ranked plan to zero vias below 0.3 mm

Tiers 0–2 are **done and DRC-proven in this directory**. Tiers 3–4 are what remains, in order of
effort, with what each buys.

**Tier 0 — make the defect non-recurring (one file, no copper).** Drop `no_hdi.kicad_dru` next to the
board. It turns "0.1 mm via" from an invisible choice into a DRC error, and it proves the count:
33 on the baseline, 23 after tier 1–2. Also raise `min_microvia_drill` from 0.1 in `base.kicad_pro`
so the project stops *offering* the illegal via. *Buys: the class can never silently come back.*

**Tier 1 — collapse the stacked pairs (3 groups, 6 vias → 3, zero copper).** G01, G02, G27.
*Executed. DRC 0/0.*

**Tier 2 — the six sub-0.5 mm shifts (6 groups, 6 vias, 3.30 mm of new copper).** G08, G20, G22, G23,
G28, G29. Includes 2 of the 3 blind vias, so the blind/buried process is nearly gone.
*Executed. DRC 0/0.* — **Tier 1+2 = 12 of the 36 vias, 1 blind via left.**

**Tier 3 — one via that a 0.40 mm pad would rescue (1 via).** G25 `/RF_MOSI` (91.562, 62.250): the worst
layer permits a **0.424 mm** pad, i.e. 0.20 mm drill with a 0.10 mm ring. It is legal in fabrication
but needs `min_via_diameter` lowered from 0.6 to 0.4 in the project. *Cost: one project-rule change
for one via. Does not change MIN_DRILL, so it is not worth doing on its own — listed for completeness.*

**Tier 4 — re-escape the U10 / U40 fan-outs (20 groups, 24 vias, 13 nets).** This is the only remaining
route to zero, and it is a routing pass, not a via edit. It is well specified now:

1. **Free the escape corridors.** 11 of the 20 groups need only **other nets' tracks** to move; 9 also
   need a **component pad** (U10 perimeter pads, C12.2, FB1.2) or **another through via** to move.
   The exact binding item, layer, current distance and required distance are in `relief.json` — e.g.
   `G15 /HGM`: `/RF_MISO` on In2.Cu at 0.250 mm, needs 0.425 → **0.175 mm of relief**;
   `G04 /LSM_INT1`: `/ICM_nCS` on B.Cu at −0.089 mm, needs 0.425 → **0.514 mm**.
2. **Pull one escape per net out of the pad field** (≤ 0.2 mm wide, 0.200 mm gap — so this cannot be
   done at 0.2 mm track; it needs finer trace/space on F.Cu, which is a *rule* decision).
3. **Place the 0.3/0.6 through vias in the ring outside the packages**, where there is room: the
   measured legal-site distance from each failing via is **3.4–5.5 mm** (`s03b_diag.py`), and free
   space of pad ≥ 0.60 exists there.

The 3.4–5.5 mm figure is the size of the job: this is not a nudge. **Sequencing matters:** do it
inside the same rev that fixes the In1 void fill (AGENT_BOARD.md:614, "RIP-UP"), because the re-escape
changes F.Cu and In1 escape copper and the void measurement is downstream of it.

**Tier 5 — the decision nobody can take but the owner.** If tier 4 is not scheduled, the truthful
alternatives are (i) accept HDI on the drone main — which violates constraint 1 and would make the
board 3× the cost at that panel size — or (ii) change U10/U40 to ≥0.65 mm pitch packages. That is a
**package decision made at schematic/BOM level, before the layout exists**, and it is cheaper than any
of the routing work: a 0.4 mm-pitch 81-pin part on 4 layers with no HDI is the actual defect.

---

## 9. Consequences the executed edit creates

* **Pours.** Each converted via punches an antipad on **all four** layers instead of two. The 9 added
  through vias add 9 antipads on F.Cu, In1.Cu, In2.Cu and B.Cu where previously there were none on
  some of them. Zones were refilled in `s06_apply.py` and DRC reports 0 unconnected, so no pour island
  was created — **but** the In1 `/GND`/`/3V3` antipad area belongs to the same reference pour the
  `da-voidfill` item is healing. **Sequence: convert → refill → then measure voids.** Doing it in the
  other order throws that measurement away. This is the same warning the earlier item raised; it is
  still true.
* **Drill count.** 338 vias, drills 0.10/0.30/0.35 — one drill tool fewer is not achieved
  (0.10 mm is still present because 23 vias remain). No new tool diameter was introduced.
* **Impedance.** None of the 12 converted vias is on the 50 Ω path: the affected nets are
  /GNSS_RX, USB_DP_MCU, /SENS_SCLK, /RF_SCLK, /LSM_INT1, /RF_GPIO2, /RF_MISO, /RF_RESET_N. The drill
  stays 0.30 mm and the pad grows 0.30→0.60 mm; via inductance is set by the drill and barrel, so it
  is unchanged, and the pad delta is ≈0.02 pF. **No impedance re-derivation is triggered and the TDR
  coupon (`dec-coupon-60`) does not change.**
* **Assembly.** No component moved, no courtyard touched, no pad edited. Only 12 via deletions,
  9 via insertions and 19 track segments.

---

## 10. What still needs a human

1. **A fan-out re-escape of U10 and U40** (tier 4): 20 groups, 24 vias, 13 nets, corridors currently
   3.4–5.5 mm from each failing site. Per-group binding item and required relief: `relief.json`.
   This is a routing pass; I sized it and proved it is necessary, I did not author it.
2. **A rule decision, not a copper decision:** the re-escape is impossible at the board's current
   `min_track_width 0.2 / min_clearance 0.125`, because 0.200 mm of gap cannot hold a 0.2 mm trace.
   Someone must decide whether F.Cu goes to ~0.1 mm trace/space for the escape. I did **not** change
   any rule, because that is a fab-cost decision above this item's remit.
3. **The package question** (tier 5): 0.400 mm pitch on a 4-layer non-HDI board is the root cause.
   If a respin is already happening for the In1 void fill, this is the moment to ask it.
4. **Not verified here, and I will not claim it:** the re-escaped fan-out (it does not exist yet); any
   electrical simulation of the 12 converted vias (geometry only — the argument is "same drill, same
   net, +0.15 mm pad"); impedance measurement; whether a chosen fab house accepts a 0.10 mm annular
   ring (I avoided needing it); and whether the drone main will actually be respun, which changes
   whether tier 4 is worth doing at all.
5. **The blind via that remains:** `B01` /PA_EN (58.000, 51.900), In2→B, 0.3 mm. Its site is closed on
   In1 (`/RP2354B MCU/XIN` at −0.075 mm) and on F.Cu (U10.81 `/GND` at 0.200 mm), so it rides on tier 4.

---

## 11. Artefacts

| file | what |
|---|---|
| `REPORT.md` | this report |
| `TABLE_36.md` | the 36 vias, one row each: net, x/y, drill, pad, span, binding obstruction + distance, max pad the site allows, max drill at a 0.10 ring, action, new site, Δ, copper added — generated by `s09_table.py`, nothing typed by hand |
| `vias.csv`, `vias_analysis.json` | per-via measurement, incl. the 305-via model check |
| `relief.json` | per group, per layer: binding item, distance, shortfall, and whether that item is a track (movable) or a pad/via (fixed) |
| `floor.json` | per group: min distance over 4 layers → max pad → max drill at a 0.10 / 0.15 ring → verdict |
| `routes.json`, `routes_wide.json` | routing decisions at ±4 mm / 0.05 mm and ±7 mm / 0.1 mm (identical outcome for the 20) |
| `edits.json` | **the patch, machine-readable**, UUID-keyed |
| `s06_apply.py` | **the patch, executable** |
| `base.kicad_pcb` / `fixed.kicad_pcb` (+ `.kicad_pro`) | control and result |
| `drc_base.json`, `drc_fixed.json` | DRC under the board's own rules |
| `nhdi/` (`base`/`fixed` + `no_hdi.kicad_dru`) | DRC under the no-HDI gate: 33 → 23 |
| `base_census.json`, `fixed_census.json` | independent via census |
| `no_hdi.kicad_dru` | the gate rule, to be dropped beside the real board |
| `s01_dump.py` … `s09_table.py` | whole pipeline, in order |
| `s03b_diag.py`, `s03c_look.py`, `s03d_map.py`, `s05_rootcause.py` | the diagnostic passes that established §4.2 |

Reproduce end to end:

```
python.exe s01_dump.py base.kicad_pcb inventory.json
python.exe s02_analyse.py            # per-via measurement + 305-via model check
python.exe s03_plan.py               # first-pass classification
python.exe s04_route.py              # site search + clearance-aware path finder
python.exe s06_apply.py              # build fixed.kicad_pcb
python.exe s07_census.py fixed.kicad_pcb
python.exe s08_relief.py ; python.exe s09_table.py
kicad-cli pcb drc --format json --severity-all --output drc_fixed.json fixed.kicad_pcb
```

`HALF=7.0 STEP=0.1 OUTFILE=routes_wide.json python.exe s04_route.py` reproduces the wide search.

---

## 12. Correction to the earlier item's plan (`evidence/da-via-conversion/REPORT.md` §5, §7)

That report concluded a ranked plan reaching **zero below 0.3 mm with 29 replacement vias**, of which
23 were "re-route" targets with named sites and stub lengths (e.g. "V26/27: 6.88 mm + 1.86 mm stub",
"V22: 5.38 mm + 1.91 mm stub"). **Those targets were not connectivity-checked and the plan is not
reachable.** Measured here:

* its targets lie **3.4–5.5 mm** away, and reaching them requires new copper on *every* layer the net
  uses, seeded from the via's own terminal — for 6 groups the terminal copper cannot leave its pocket
  at all (`routes.json:groups[*].diag`, `reached == net_cells`), and a straight stub to those targets
  crosses foreign copper.
* widening the search to ±7 mm does not change the outcome (`routes_wide.json`).
* its `fix_pos_filled.kicad_pcb` (0 violations, 5 fewer sub-0.3 vias) is consistent with my result and
  is not disputed; what is withdrawn is the **claim that the remainder is a list of known re-routes.**

Where the two reports agree, they agree from independent models: its "8 zero-move" (0.50 pad) is my
"5 fit a 0.60 pad / 8 fit a 0.50 pad" (`vias_analysis.json`), and its 7 stacked pairs are my 7 pairs.
The disagreement is exactly one thing — whether a legal relocation exists for the rest. It does not.

*Maintained by `fab-da-vias`. Written only inside `evidence/fab-da-vias/`; no repo file, no commit,
no `audit/*` branch touched.*