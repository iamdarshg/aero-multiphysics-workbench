# fab-da-growth-north — grow the NORTH edge toward U10's blocked pad row

**Question (single):** the prior growth test grew the **south** edge and gained **0 of 17** non-through
vias. U10's blocked pad row faces **north** (y ≈ 44.2). If the outline is grown **northward** by
+2 / +4 / +8 mm, can the 17 vias be placed as legal **0.60/0.30 through vias**, DRC as the arbiter?

**Input:** `evidence/fab-da-path/da_main_rev_b_path6L.kicad_pcb` — the clean 17-via state
(337 vias, **17 non-through**, DRC `{via_diameter: 6}`, unconnected 0 on both tools). Copied to
`work/base.kicad_pcb`; nothing written into any repo.
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/fab-da-growth-north/`. All work on copies.

> **HEADLINE — growth gains 0 of 17 at every amount, and it is not a direction error, it is a
> category error: an outline can only move AWAY from everything inside it.** Measured northward:
> the blocked row's pad copper goes **44.65 → 46.65 / 48.65 / 52.65 mm** from the edge, and the
> northmost blocked via **44.10 → 46.10 / 48.10 / 52.10 mm**. Area cost **+280 / +560 / +1,120 mm²
> = +2.00 / +4.00 / +8.00 %** of 14,000 mm². Attempted 17 at each size: **0 kept** (0 at base too).
> DRC SET DIFF `{}` on both rulesets, unconnected **0 on both tools**, non-through stays **17**,
> min drill **0.100**, RF void **4.1699 mm² / 9.8338 %** bit-identical. The board's copper hash is
> **43e694dd146f65aa** before and after every growth — growth moves nothing, so the via arithmetic
> cannot change. **Verification path: not applicable — no via was gained, so nothing was converted.**
> The per-site proof is in §5: 14 of the 17 are bound by a **track**, 2 by a **pad**, 1 by a **via**,
> and **0 by the board edge** — the minimum edge clearance at any site is **+43.10 mm** against a
> worst copper shortfall of **0.650 mm**. Growth is dead at 44 mm, on every edge.

---

## 0. Instrument validation — and four faults caught before any number was quoted

The input reproduces the shipped 6-layer board on both tools, and the per-site model reproduces the
prior wave's published extremes, so the instrument is calibrated against an independent run:

| check | measured here | prior evidence |
|---|---|---|
| copper layers | 6 | 6 (`fab-da-path`, `fab-da-radical`) |
| vias / **non-through** | 337 / **17** | 337 / 17 |
| by layer pair | F→In1 6 · In1→In2 5 · F→In2 2 · In2→B 3 · In1→B 1 | identical |
| DRC own rules | `{via_diameter: 6}` | `{via_diameter: 6}` |
| DRC no-HDI gate | 22 = 16 `microvia_drill_out_of_range` + 6 `via_diameter` | identical |
| unconnected | 0 (`kicad-cli`) / 0 (`pcbnew`) | 0 / 0 |
| min drill | 0.100 (16 vias) | 0.100 |
| board | 140.000 × 100.000 = **14,000.0000 mm²** | 14,000.0000 |
| RF void A / B | **4.1699 mm² = 9.8338 % / 3.8754 = 9.1392 %** | identical |
| worst copper margin at a site | **−0.6500** (pad FB1.2 `/3V3_ADC`) | −0.650 (mcu-options §5.2) |
| best copper margin at a site | **−0.1192** (`/SENS_SCLK` vs a 350 µm via) | −0.119 |
| legal in place, 0.60/0.30 | **0 of 17** | 0 of 17 |

**Four instrument faults caught in this wave (each produced a plausible wrong number):**

1. **Vertex-only nearest point.** The rip-up wave's `nearest_poly_pt` returned the nearest polygon
   *vertex*, which reported a **6.502 mm** stub for `/3V3` where the pad copper is **1.785 mm** away.
   Every stub in this report uses exact segment projection (`s4_common.py`).
2. **Owner pad chosen by U10's centre, not by the microvia.** `pad_of_net` sorted same-net pads by
   distance to U10's centre, so a conversion could be fed from a pad the via never served. Fixed: the
   owner is the same-net pad nearest the **original via XY** (which matches the nearest-footprint
   attribution in `fab-da-36via` §0).
3. **A print bug that looked like an instrument fault.** The first site table printed `best +0.0000`
   for rows that *do* have legal positions. The real maxima are **+0.0103 … +0.0467 mm** — small, but
   non-zero and usable by DRC. Caught by re-deriving the constraint terms per row (`s4b_diag.py`).
4. **"Move nothing" asserted, then checked as a hash.** A strip of `growG.kicad_pcb` is only a growth
   if no copper moved, so the whole copper inventory (vias + tracks + pads + zones **including fill
   area per layer**) is canonicalised and hashed: `43e694dd146f65aa` on base and on every grown
   board. The outline is deliberately excluded — it is the one thing that moves.

---

## 1. Which edge is nearest the blocked row, and by how much

Y grows **downward** in the KiCad board file, so **north = min Y**. U10 is at (59.000, 50.000) on a
0 … 100 board; its north row is the min-Y row. Distances measured to the copper, not to the body:

| direction | pad-row **centre line** | pad copper **tip** | nearest of the 17 blocked vias | U10 centre |
|---|---:|---:|---:|---:|
| **North** (min Y, the row faces this) | **45.05 mm** | **44.65 mm** | **44.10 mm** (`/USB_DP_MCU`) | 50.00 |
| South (max Y) | 45.05 mm | 44.65 mm | 43.90 mm (`/RF_GPIO0`) | 50.00 |
| West (min X) | 54.05 mm | 53.65 mm | 51.50 mm | 59.00 |
| East (max X) | 76.05 mm | 75.65 mm | 79.20 mm | 81.00 |

**The prior wave's 45.05 mm is reconciled exactly**: it is the **pad-row centre line** to its own
edge (U10 half-body 4.95 mm), measured on the **south** row. The row U10's blocked vias actually face
is the north row, at the same 45.05 mm centre-line / **44.65 mm copper** distance — the outline is
symmetric about U10, so the two nearest edges are tied and both are 44.65 mm from pad copper.

**Which direction relaxes the blocked row: none.** Growing an outline moves its edge **outward**, i.e.
away from every component inside it, by exactly G. Measured on the saved boards:

* U10 north pad copper → north edge: **44.65 → 46.65 / 48.65 / 52.65** (+2/+4/+8 mm)
* northmost blocked via → north edge: **44.10 → 46.10 / 48.10 / 52.10**

So the prior test's 0 of 17 was **not** caused by choosing the south edge. Both edges gain 0, for the
same reason: the new area sits on the far side of the old outline, 44 mm from the row, and the strip
between is populated board that growth cannot empty. (`+2/+4/+8` northward is the honest execution of
the brief's hypothesis; the result is the same 0.)

---

## 2. Growth attempts: +2 / +4 / +8 mm northward — kept / attempted

Three edge segments move per attempt (the north segment and the north end of each vertical); no
component, track, via or zone is touched (hash: §0.4). Each grown board gets its own DRC run in a
directory carrying its `.kicad_pro`, and a second run with the no-HDI `.kicad_dru`. The site test
repeats the rip-up wave's acceptance: a legal 0.60/0.30 through position on all 6 layers, plus a
legal 0.20 mm stub from the owner pad and a legal 0.20 mm trunk to same-net copper on the far layer.

| | base | **+2 mm** | **+4 mm** | **+8 mm** |
|---|---:|---:|---:|---:|
| board area (mm²) | 14,000.0000 | **14,280.0000** | **14,560.0000** | **15,120.0000** |
| added | — | **+280.0000 (+2.00 %)** | **+560.0000 (+4.00 %)** | **+1,120.0000 (+8.00 %)** |
| U10 N pad copper → edge (mm) | 44.65 | 46.65 | 48.65 | 52.65 |
| northmost blocked via → edge (mm) | 44.10 | 46.10 | 48.10 | 52.10 |
| **attempted** | 17 | **17** | **17** | **17** |
| **kept** (site+stub+trunk legal) | **0** | **0** | **0** | **0** |
| … legal through position within ±2.5 mm | 5 | 5 | 5 | 5 |
| … legal **in place** at the original XY | 0 | 0 | 0 | 0 |
| **vias GAINED by the growth** | — | **0** | **0** | **0** |
| new-strip sample points legal for 0.60/0.30 | — | 81 / 81 | 189 / 189 | 405 / 405 |
| DRC own-rules SET DIFF vs base | — | `{}` | `{}` | `{}` |
| DRC no-HDI gate SET DIFF vs base | — | `{}` | `{}` | `{}` |
| unconnected — `kicad-cli` / `pcbnew` | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| vias / non-through | 337 / 17 | 337 / **17** | 337 / **17** | 337 / **17** |
| min drill | 0.100 | 0.100 | 0.100 | 0.100 |
| RF void A / B | 4.1699 / 9.8338 · 3.8754 / 9.1392 | identical | identical | identical |

**The new area is legal and useless.** Every sampled point in the added strip admits a 0.60/0.30
through via — it is bare board, and the board was already bare there: the nearest copper to the north
edge on the base board is **3.0000 mm** inside it, and **no copper item lies north of y = 0**, so the
growth bolts empty board onto empty board. It buys nothing, because a via placed at y = −1 … −7 is
**46–52 mm** from the pad row it is supposed to serve, and the 44 mm between is the existing routed
region. A per-point check confirms the numbers never move: at every growth amount the site margins
and the count of legal positions are **bit-identical to base** (`sites_by_growth.json`), which is what
the copper hash already predicted.

---

## 3. Area cost per attempt

| growth | area added | share of 14,000 mm² | U10-row gap change |
|---|---:|---:|---:|
| +2 mm | +280.0000 mm² | **+2.00 %** | 44.65 → 46.65 mm (**+2.00 mm worse**) |
| +4 mm | +560.0000 mm² | **+4.00 %** | 44.65 → 48.65 mm (**+4.00 mm worse**) |
| +8 mm | +1,120.0000 mm² | **+8.00 %** | 44.65 → 52.65 mm (**+8.00 mm worse**) |
| *control: +44.65 mm* | *+6,251.0000 mm²* | *+44.65 %* | *44.65 → 89.30 mm — still 0 kept* |

Fab money for +2/+4/+8 is **$0** at PCBWay because 140 × 100 already prices inside the 150 × 100 tier
(carried from `da-mcu-options-v2` §5.3, not re-quoted here). The cost that matters is the engineering
one and it buys a negative: the gap to the blocked row grows by exactly the amount paid for.

---

## 4. Full conversion and verification — NOT APPLICABLE, and why that is the result

The condition for this section was "if growth gains any vias". It gained **0 of 17 at every amount**,
so no via was converted and there is no converted board to verify. To keep the record complete, the
same verification battery was run on all five boards and it certifies identity rather than change:

| check | result on base and on +2 / +4 / +8 / +44.65 |
|---|---|
| span census by layer pair | F→In1 **6** · In1→In2 **5** · F→In2 **2** · In2→B **3** · In1→B **1** = **17 non-through**, unchanged |
| DRC SET DIFF vs base, own rules | `{via_diameter: 6}` → `{}` at every growth |
| DRC SET DIFF vs base, no-HDI gate | `{microvia 16, via_diameter 6}` → `{}` at every growth |
| unconnected, `kicad-cli` | **0** — the `unconnected_items` list is empty (this build emits no `unconnected`/`counts` scalar at all, so the 499 list cap cannot be in play) |
| unconnected, `pcbnew` | **0** (`GetUnconnectedCount`) |
| min drill | **0.100 mm** (16 vias at 0.100) — unchanged |
| RF void A / B | **4.1699 mm² / 9.8338 %** and **3.8754 / 9.1392 %**, bit-identical |
| copper inventory sha256 | **43e694dd146f65aa** — identical to base on all four |

A refill check was added because a grown outline is a *derived* change for zone fill: refilling the
+8 mm board adds **+79.99 mm²** of pour on F.Cu and **+79.99 mm²** on In1.Cu (0.57 mm of creep per
layer), and the refilled board still measures **4.1699 / 9.8338 %** — the RF void is not disturbed by
the growth. Refilling the base changes nothing (its fill is already current).

---

## 5. Why growth still gains 0 — the geometry, per via

### 5.1 What binds each of the 17, at its own XY (0.60/0.30 through via, all 6 layers)

| net | span | copper margin | binding item | via→edge |
|---|---|---:|---|---:|
| `/3V3` | F→In1 | −0.5500 | trk `/LNA_EN` w0.25 | 44.45 |
| `/GNSS_RX` | F→In1 | −0.3260 | trk `/USB_DM_MCU` w0.25 | 49.40 |
| `/GNSS_RX` | In1→In2 | −0.2818 | **pad** C12.2 `/GND` | 46.80 |
| `/HGM` | F→In1 | −0.1750 | trk `/RF_MISO` w0.20 | 44.85 |
| `/LSM_INT1` | F→In1 | −0.5141 | trk `/ICM_nCS` w0.25 | 47.40 |
| `/LSM_INT1` | In1→In2 | **−0.6500** | **pad** FB1.2 `/3V3_ADC` | 49.00 |
| `/LSM_INT1` | In1→In2 | −0.5141 | trk `/ICM_nCS` w0.25 | 47.40 |
| `/PA_EN` | F→In2 | −0.4250 | trk `/RF_GPIO2` w0.20 | 47.80 |
| `/PA_EN` | In2→B | −0.4998 | trk `/XIN` w0.25 | 48.10 |
| `/RF_GPIO0` | In2→B | −0.4498 | trk `/SENS_MOSI` w0.25 | 44.80 |
| `/RF_GPIO0` | In2→B | −0.4500 | trk `/1V1` w0.25 | 43.90 |
| `/RF_GPIO2` | F→In2 | −0.5115 | trk `/SENS_SCLK` w0.20 | 44.80 |
| `/RF_MISO` | F→In1 | −0.1500 | trk `/RF_nCS` w0.25 | 47.00 |
| `/RF_MISO` | In1→In2 | −0.1500 | trk `/RF_nCS` w0.25 | 47.00 |
| `/USB_DP_MCU` | F→In1 | −0.1500 | trk `/3V3` w0.25 | **44.10** |
| `/USB_DP_MCU` | In1→In2 | −0.1500 | trk `/3V3` w0.25 | **44.10** |
| `/SENS_SCLK` | In1→B | −0.1192 | **via** `/RF_GPIO0` 350 µm | 46.55 |

Binding kind: **track 14 · pad 2 · via 1 · board edge 0**. The shortages run **0.1192 – 0.6500 mm**.
The board edge is **+43.10 to +48.60 mm** clear at these same sites, while the largest copper
shortfall anywhere on the list is **0.650 mm** — the edge clearance is at least **66×** the shortage
that actually decides legality. **Nothing at any of the 17
sites is edge-bound**, so moving the edge cannot change one of them. That is the whole result, and it
is why the answer does not depend on which edge is chosen.

### 5.2 The five sites that do have a legal through position — and the second wall behind them

Five of the 17 have a legal 0.60/0.30 position within ±2.5 mm (margins +0.0103 … +0.0467 mm, i.e.
real but thin). None can be used, because the escape lane out of the pad is illegal before it reaches
the site — a 0.20 mm stub needs **0.225 mm** (0.100 + 0.125) from foreign copper on each side, and a
0.4 mm-pitch QFN lane is **0.300 mm** wide:

| net | layer | legal positions | best stub slack (need +0.225) | binding item | stub length |
|---|---|---:|---:|---|---:|
| `/LSM_INT1` | F.Cu | 4 | **−0.1606** | via `/ICM_INT2` 350 µm | 1.024 mm |
| `/LSM_INT1` | In1.Cu | 101 | −0.1990 | trk `/MAIN_LED_A` w0.25 | 1.074 mm |
| `/3V3` | F.Cu | 2 | −0.3500 | trk `/1V1` w0.25 | 1.785 mm |
| `/RF_GPIO2` | F.Cu | 11 | −0.3500 | trk `/1V1` w0.25 | 3.169 mm |

The five rows are four distinct stacks: `/LSM_INT1` In1 appears twice (its two vias share the same
legal region), each with 4 legal positions. The `/LSM_INT1` In1 row with 101 positions is the same
net at the other via — the widest legal region found anywhere in this test, and still unfed.

**Best stub slack over all 17: −0.1606 mm. Zero of the five can be fed.** This is the wall the
rip-up wave broke with its 10 mm erasure (which cut 42–49 nets and left 81 unconnected) — and it is a
*pad-lane* wall, which no amount of board area can touch.

### 5.3 Why no growth amount could ever help — three independent proofs

1. **The edge is not in the budget.** Minimum edge clearance at any of the 17 is **+43.10 mm**; the
   worst copper shortfall is **0.650 mm**. Growth changes the first number only, in the wrong
   direction, and the second is the one that decides legality.
2. **Reaching the row destroys it.** To bring the north edge to the northmost blocked via you need
   **+44.10 mm** = 140 × 44.10 = **6,174 mm² = +44.1 %** of the board, and at that point the via sits
   on the outline, i.e. off the board. The **+44.65 mm control run** was executed anyway: 20,251 mm²,
   +44.65 %, and it still keeps **0 of 17** with a DRC set diff of `{}` — the site margins are
   bit-identical to base, because they are computed against pads and tracks, not the outline.
3. **A lane from the pad to the new area is illegal in the first millimetre.** At +8 mm the new strip
   is 51.85–62.55 mm from the pads. The best straight 0.20 mm lane from any owner pad to a point in
   that strip has slack **−0.3500 mm** (`/GNSS_RX`, `/LSM_INT1`, `/PA_EN`) and the worst is −0.5700;
   **none of the 17 is legal**. So even a via placed in the new area could not be connected to the row
   it is meant to replace.

**And the row is not one row.** Attribute the 17 by owner-pad side: **N 3 · S 7 · W 7** (E 0). Even a
hypothetically perfect northward relief could only ever address 3 of 17; the other 14 are bound by
tracks and pads on the south and west sides, which no outline change reaches. The blocked set is
**boxed in by copper on all sides**, not by the board edge on one side.

---

## 6. Verdict

**Board growth does not work, on any edge, at any amount, and this is now settled geometrically.**

* Measured northward as asked: **0 of 17 kept at +2 / +4 / +8 mm** (17 attempted each), **+2.00 /
  +4.00 / +8.00 %** area, DRC set diff `{}`, unconnected 0 on both tools, non-through still 17.
* Growing north makes the gap to the blocked row **worse by exactly G** (44.65 → 46.65 / 48.65 /
  52.65 mm of pad copper); 14 of 17 are track-bound and 2 pad-bound, and **0 are edge-bound**, so the
  outline was never the obstruction.
* The prior wave's 0 of 17 was not a wrong-edge mistake. Growth is a **category error** for a
  mid-board component: it adds area *outside* the outline, and the outline is 44 mm from the row.
* What would work is unchanged from wave 18/19: clear the **pad-lane + local copper** (the rip-up's
  off-site conversion, 9–10 of 17, at 59–86 unconnected), or accept HDI 1+2+1, or the LQFP-100 which
  still misses 0.85 mm by 0.075 mm. Growth is not among the options.

### Artefacts

| file | note |
|---|---|
| `work/base.kicad_pcb` | the clean 17-via base (copy), copper sha `43e694dd146f65aa` |
| `work/grow2/4/8.kicad_pcb` | the three northward growths, **0 vias gained** |
| `work/grow44.65.kicad_pcb` | control: edge moved to the pad-copper line (+44.65 %), still **0 kept** |
| `work/grow8_filled.kicad_pcb`, `base_filled.kicad_pcb` | refilled variants (pour creep +79.99 mm²/layer; RF void unchanged) |
| `drc/*_own/drc.json`, `drc/*_gate/drc.json` | every DRC run; set diffs in `work/drc_all.json` |
| `work/geom.json` | board, U10 pad rows by side, edge distances, the 17 vias with owner pads |
| `work/base_sites.json` | per-site copper / hole / edge decomposition (the §5.1 table) |
| `work/sites_by_growth.json` | kept/attempted per growth amount, plus the identity check |
| `work/legal_site_diag.json`, `work/stub_diag.json` | the five legal positions and why their stubs fail |
| `work/far_stub.json` | pad → new-strip lanes at +8 mm (all illegal) |
| `work/identity.json` | span census, min drill, pcbnew unconnected, copper sha per board |
| `work/void_measure.json` | RF void on all six boards (incl. refilled) |
| `work/grow_R*.json` | area, segment count, edge-distance pair per growth |

Scripts in the order they matter: `s1_geom.py` (edges + U10 pad rows + the 17) · `s2_base.py`
(per-site constraint decomposition, instrument validation) · `s3_grow.py G` (grow north, save) ·
`s4_sites.py` (kept/attempted per growth, strip sampling) · `s4b_diag.py` / `s4c_stub.py` (the five
legal positions and their stub shortfall) · `s5_gate.py` (DRC, both rulesets, set diffs) ·
`s6_ident.py` (census, copper hash, both-tool unconnected) · `s7_refill.py` (zone refill + fill delta) ·
`s8_void.py` (RF void) · `s9_far.py` (pad → strip lanes) · `s4_common.py` (exact owner-pad / nearest-
point geometry).

**Provenance.** Everything above is **measured here** with `pcbnew` (KiCad 9.0.7 bundled python) and
`kicad-cli pcb drc --format json --severity-all --units mm`, on copies, in this evidence dir, except:
the fab price ($0 at PCBWay for ≤150 × 100) and the 0.425 mm lane need, which are **carried** from
`da-mcu-options-v2` §5.3 and `fab-da-path` §3.1 and were not re-derived.


