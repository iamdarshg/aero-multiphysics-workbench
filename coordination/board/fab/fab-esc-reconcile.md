# fab-esc-reconcile — Task 1 (the two unconnected counts) and Task 2 (the 110 pads)

**Owner:** fab-esc-reconcile (wave 4)
**Board:** `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb`
(sha256 `992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD`, 4,988,844 B,
171,757 lines, last written 2026-11-11 22:57)
**Host:** KiCad 9.0.7 — `C:\Program Files\KiCad\9.0\bin\kicad-cli.exe`, `...\bin\python.exe` (pcbnew 9.0.7)
**Evidence dir:** `evidence/fab-esc-reconcile/` — the repo was read only. Every board that was
modified is a copy under this directory. Nothing was committed, pushed or branched.

---

## Result in one table

| question | answer | method |
|---|---|---|
| kicad-cli unconnected items | **499** | `kicad-cli pcb drc` (saturated — see §2) |
| pcbnew `GetUnconnectedCount` | **1542** | `pcbnew` connectivity |
| **true number of unrouted connections** | **1542** | 6 complete sub-reports sum to 1542 |
| **nets with ≥1 unrouted connection** | **537** of 666 | complete per-net data |
| **unrouted pad-to-pad connections** | **1437** | endpoint classification of all 1542 |
| 110 × 0.200 mm pads in the three named packages | **0** | pad-by-pad drill + footprint map |
| **pads that REMAIN after the three package swaps** | **110** | — |

---

## 1a. The two commands and their raw output

### Command 1 — kicad-cli

```
kicad-cli pcb drc --format json --severity-all --units mm ^
  --output evidence\fab-esc-reconcile\drc_all.json ^
  "repos\drone-arm\hardware\esc\rev_b\esc_rev_b.kicad_pcb"
```

Raw output file `drc_all.json` (419,144 B), header fields verbatim:

```
"coordinate_units": "mm", "kicad_version": "9.0.7", "source": "esc_rev_b.kicad_pcb",
"unconnected_items": 499 items, "violations": 16 items
```

→ **499 unconnected items.** Every entry has exactly two items
(`items-per-entry histogram: {2: 499}`), i.e. each entry is a *pair*.

### Command 2 — pcbnew

```
"C:\Program Files\KiCad\9.0\bin\python.exe" t1_connectivity.py ^
  "repos\drone-arm\hardware\esc\rev_b\esc_rev_b.kicad_pcb" t1_pcbnew_raw.json
```

`t1_connectivity.py` does `LoadBoard` → `BuildConnectivity()` → `RecalculateRatsnest()` →
`GetUnconnectedCount(False)`. Raw output (`t1_pcbnew_raw.log`):

```
footprints            : 687
pads                  : 3454
nets (ByName)         : 667
conn.GetNetCount()    : 667
conn.GetPadCount()    : 3002
conn.GetNodeCount()   : 5280
GetUnconnectedCount(False) : 1542
GetUnconnectedCount(True)  : 1542
```

→ **1542 unconnected items.** Visibility flag makes no difference (1542 both ways).

Ratio 1542 / 499 = **3.09** — the "factor of three".

---

## 1b. What each number actually counts — established by experiment, not assumption

### The 499 is a hard reporting cap in the DRC engine

I did not infer this; I built boards whose ratsnest count is known by construction and ran both
tools on them (`t1c_mkboards.py`, `t1d_stubtests.py`; DRUs in `drc_t*.json`).
Full table: **`t1_cap_experiments.csv`**.

| board | edges by construction | kicad-cli | pcbnew |
|---|---|---|---|
| `t1_5x2` (5 nets × 2 pads) | 5 | **5** | 5 |
| `t2_1x10` (1 net × 10 pads) | 9 | **9** | 9 |
| `t4_chain` (9 of 10 pads chained) | 1 | **1** | 1 |
| `t5_200x3` (200 nets × 3 pads) | 400 | **400** | 400 |
| `t6_400x2` | 400 | **400** | 400 |
| `t6_499x2` | 499 | **499** | 499 |
| `t6_500x2` | 500 | **499** ✗ | 500 |
| `t6_501x2` | 501 | **499** ✗ | 501 |
| `t6_550x2` | 550 | **499** ✗ | 550 |
| `t6_700x2` (=`t3_700x2`) | 700 | **499** ✗ | 700 |
| `t6_1000x2` | 1000 | **499** ✗ | 1000 |

The boundary is **exactly 499**: reported correctly at 499, floored at 499 for every larger value.
The same cap exists in the text report (`--format report` on the 700-gap board prints
`Found 499 unconnected items`, 499 `Missing connection` lines — `drc_t3_report.txt`). The DRC
*violations* list has its own cap of **399** (that 700-net board also emits exactly 399
`lib_footprint_issues`), so this is an engine-side limit, not a JSON writer artefact.

**Consequence: on the ESC the kicad-cli figure is saturated — it reports "≥499", not "499".** The
truncation even cuts *mid-net*: of the 67 nets that appear, 66 have identical counts in both tools
and `/M4_BATN` appears with **3** of its true **56** because the list ended inside it
(`t1i_validate.log`).

### What the counted object is

Both tools count **ratsnest edges**, i.e. for each net, *(number of connected components of its
copper items) − 1*. It is not a pad count and it is not a net-pair count:

- **Not a pad count.** On `t2_1x10` (10 pads, one net) both report **9**, not 10. `GetPadCount()`
  is 3002 on the ESC while the count is 1542, so the pad population is not the metric.
- **Not net pairs.** 1542 edges live on **537** nets — a net-pairs figure could not exceed
  C(537,2).
- **Pad-less copper is a node.** `t7_padless_stub` adds one detached track island to an otherwise
  complete net → **1**; `t8_padless_via` adds one orphan via → **1**; `t9_3pads_2stubs` (3 pads +
  2 detached islands = 5 components) → **4**. Both tools agree in every case.
- **T-junctions connect** (`t10_tjunction` → 1, not 2), so the graph is KiCad's real connectivity,
  not endpoint-matching.

So the pair of numbers differs **only** by the cap. Same definition, different reporting limit.

### Independent confirmation at full scale

If the two instruments share a definition, then splitting the ESC into net-disjoint copies — nets
cannot interact, so a net's connectivity is unchanged — must reproduce the total from sub-reports
that are each small enough to escape the cap. Done with `t1f_build_one.py` (one `LoadBoard` per
process) and `t1g_census.py`; partitions in `partitions/`.

| partition | nets kept | pcbnew | kicad-cli unconnected |
|---|---|---|---|
| part0 | 111 | 271 | **271** |
| part1 | 111 | 265 | **265** |
| part2 | 111 | 214 | **214** |
| part3 | 111 | 324 | **324** |
| part4 | 111 | 227 | **227** |
| part5 | 111 | 241 | **241** |
| **sum** | **666** | **1542** | **1542** |

Both sums equal the full board's 1542 exactly, and every partition is below 499, so each list is
complete. A no-op round trip was checked first: load→save→reload still reports 1542
(`roundtrip.kicad_pcb`). Method receipt: `partitions/` + `t1h_reconcile.py`.

---

## 1c. The reconciled three-figure answer

Definitions are stated so that a future report cannot pick the flattering one. Population:
**666 nets carry pads or copper**; 2,982 pads sit on nets; 2,144 track/via objects sit on nets.

| # | figure | value | definition |
|---|---|---|---|
| 1 | **nets with ≥1 unrouted connection** | **537** | nets among the 666 whose copper items fall into ≥2 connected components, i.e. the net is not fully connected. (129 nets are fully connected: 110 are single-pad nets with no copper, 13 are routed and complete, 6 are otherwise degenerate.) |
| 2 | **unrouted pad-to-pad connections** | **1437** | ratsnest edges whose *two* endpoints are both pads (Pad–Pad 1328, PTH–Pad 103, PTH–PTH 6). This is the number of connections that must be drawn pad-to-pad. |
| 3 | **total unrouted connections** | **1542** | all ratsnest edges on the board, including the 105 that terminate on a via, track end or zone rather than a second pad (Pad–Zone 54, Pad–Via 41, Via–Via 7, Pad–Track 3). |

**Quote all three together, with these definitions.** 1437 + 105 = 1542, and those 105 non-pad
edges are spread over **52 nets** (3 each on `/M1_BATN`…`/M6_BATN` and the six `*_STATUS_LED`
nets, 2 each on `/3V3` and the twelve `*_PHASE_B/C` nets, 1 each on the 24 `*_SH[ABC]_I` sense
nets and 2 others). **499 must never be quoted again**: it is a truncated report, 3.09× low, and it is
low by an unknown amount — its own list is cut mid-net.

Largest incomplete nets (of 537): `/DGND` 85, `/3V3` 59, and `/M1_BATN` … `/M6_BATN` 56 each;
then `/M1_3V3I` … `/M6_3V3I` 20 each. Full per-net table in `t1_reconciled.json`.

Two per-net facts worth carrying into the routing budget: **612 of 666 nets carry no copper at
all**, and only **13 nets are fully routed**. (The board's "16 nets routed / 540 of 556 nets"
uses a different denominator — 556 — and is not reconciled with my 666; flagged, not restated.)

**Population cross-check against the board's own numbers:** the copper inventory enumerated here is
**154 segments + 1,990 vias + 0 arcs = 2,144 objects**, which reproduces `AGENT_BOARD.md:669`
("154 segments totalling 628.27 mm … 1,978 of 1,990 vias") exactly. Two independent censuses of the
same board agree, so the 537-net / 1542-edge decomposition is over the same population.

---

## 2. The 110 × 0.200 mm pads — mapped

Rule applied: 4 oz needs a **0.30 mm minimum finished hole** (LeitOn at 140 µm). Every plated hole
in the board was enumerated (`t2_pads.py`). PTH drill histogram:

| drill (mm) | count | verdict |
|---|---|---|
| **0.200** | **110** | **fails 0.30** |
| 0.600 × 1.400 | 4 | pass |
| 0.600 × 1.700 | 4 | pass |
| 0.650 | 30 | pass |
| 1.000 | 7 | pass |
| 1.020 | 2 | pass |
| 1.100 | 24 | pass |
| 1.200 | 12 | pass |
| 5.500 | 30 | pass |

Nothing sits between 0.200 and 0.650, so the failing set is exactly **110**, all at **0.200 mm**
(no NPTH pad is below 0.30 — those are unplated and out of scope).

### 2a/2b. All 110 mapped, grouped by footprint

Full 110-row listing (footprint, pad, drill, net, type, pad size, X, Y):
**`t2_110_pads.csv`**.

| footprint | count | footprint type | pad no. | net |
|---|---|---|---|---|
| U1101 | **16** | WQFN-40-EP_6x6_P0.5 | 41 | /M1_BATN |
| U1201 | **16** | WQFN-40-EP_6x6_P0.5 | 41 | /M2_BATN |
| U1301 | **16** | WQFN-40-EP_6x6_P0.5 | 41 | /M3_BATN |
| U1401 | **16** | WQFN-40-EP_6x6_P0.5 | 41 | /M4_BATN |
| U1501 | **16** | WQFN-40-EP_6x6_P0.5 | 41 | /M5_BATN |
| U1601 | **16** | WQFN-40-EP_6x6_P0.5 | 41 | /M6_BATN |
| U701 | **6** | HSOP-8-1EP_3.9x4.9mm_P1.27mm_EP2.41x3.1mm_ThermalVias | 9 | /AUX_GND |
| U703 | **6** | HSOP-8-1EP_…_ThermalVias | 9 | /AUX_GND |
| U204 | **2** | TPS3430_WSON10_EP | 11 | /DGND |
| **total** | **110** | **9 footprints, 3 families** | | |

**Every one of the 110 is a thermal via inside an exposed pad** — pad 41 is the WQFN-40 EP,
pad 9 the HSOP-8 EP, pad 11 the WSON10 EP — and every one sits on a power or ground net
(`/M1..M6_BATN`, `/AUX_GND`, `/DGND`). Measured thermal-pad geometry (`t2_geometry.json`):

| ref | EP pad size | via array | grid |
|---|---|---|---|
| U1101/U1201/U1301/U1401/U1501/U1601 | 4.15 × 4.15 mm | 16 vias, 2.7 × 2.7 mm extent | 4 × 4 at **0.90 mm** pitch |
| U701/U703 | 2.41 × 3.1 mm | 6 vias, 2.6 × 1.91 mm extent | 3 × 2 at 1.30 × 1.91 mm |
| U204 | 1.65 × 2.4 mm | 2 vias | 1 × 2 at 1.20 mm |

### 2c. If the three fine-pitch packages were replaced

The three packages named for Option B, checked directly on the board (`t2b_packages.log`):

| package | footprint id | pads | drill histogram | sub-0.30 pads |
|---|---|---|---|---|
| U201 | QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm | 90 | all `0.0` (**SMD, no holes at all**) | **0** |
| U1102, U1202, U1302, U1402, U1502, U1602 | LQFP-48_7x7mm_P0.5mm | 48 each | no drills (SMD) | **0** |
| J202, J203 | USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal | 22 | 0.65 ×2, 0.6×1.7 ×2, 0.6×1.4 ×2, SMD ×16 | **0** |

**0 of the 110 pads would be fixed. All 110 REMAIN.** None of the three packages contains a single
plated hole below 0.30 mm — U201 and the six LQFP-48s contain no plated holes at all.

**So the 110 are the true and entire residual cost of Option B, and Option B's package swap touches
none of them.** They are fixed only by editing the thermal-via drill 0.200 → 0.300 mm in the nine
footprints above. That is a footprint edit, not a package change and not a route change: the vias
are same-net inside a single exposed pad, so no inter-via clearance rule applies, and there is room
at the measured pitch (0.90 mm grid, 0.30 mm drill). The cost that *is* real is process-side —
via-in-pad must be plugged/tented (IPC-4761) or solder wicks down 0.30 mm holes, and a wider hole
in a thermal pad marginally reduces the copper cross-section.

### 2d. Every additional footprint implicated

More than the three packages are implicated — **nine** footprints, and **none of the nine is one of
the three Option-B packages**. Every additional footprint, named:

1. **U1101** — WQFN-40-EP_6x6_P0.5 — 16 pads
2. **U1201** — WQFN-40-EP_6x6_P0.5 — 16 pads
3. **U1301** — WQFN-40-EP_6x6_P0.5 — 16 pads
4. **U1401** — WQFN-40-EP_6x6_P0.5 — 16 pads
5. **U1501** — WQFN-40-EP_6x6_P0.5 — 16 pads
6. **U1601** — WQFN-40-EP_6x6_P0.5 — 16 pads
7. **U701** — HSOP-8-1EP_3.9x4.9mm_P1.27mm_EP2.41x3.1mm_ThermalVias — 6 pads
8. **U703** — HSOP-8-1EP_3.9x4.9mm_P1.27mm_EP2.41x3.1mm_ThermalVias — 6 pads
9. **U204** — TPS3430_WSON10_EP — 2 pads

---

## Board corrections (per board rule 4)

**BOARD CORRECTION — `AGENT_BOARD.md:510` and `:550-553`** ("499-vs-1,542 unconnected
unreconciled"). Resolved: **they are the same quantity, and 1542 is the count.** 499 is the DRC
engine's reporting cap (exactly 499, proven by construction at 500/501/550/700/1000), so the
kicad-cli figure is not a measurement of this board at all. The three quotable figures are
**537 nets / 1437 pad pairs / 1542 connections**.

**BOARD CORRECTION — `AGENT_BOARD.md:530-535`** ("changing the three fine-pitch packages may not
fix it, because the 110 offending pads have not yet been mapped"). Now mapped: it does not fix it
at all. **0 fixed, 110 remain**, on nine footprints none of which is U201, an LQFP-48 or a USB-C.
The `:530` sentence "110 × 0.200 mm PTH pads" is correct as a count.

---

## Method receipts

| file | what it is |
|---|---|
| `drc_all.json` | full-board kicad-cli DRC (499 unconnected, 16 violations) |
| `t1_connectivity.py` / `t1_pcbnew_raw.log` | pcbnew census (1542) |
| `t1a_drc_payload.py` / `.log` | proof that each DRC entry is a 2-item pair |
| `t1c_mkboards.py`, `t1d_stubtests.py`, `drc_t*.json` | synthetic boards with known counts |
| `t1_cap_experiments.csv` | the cap table (499 boundary) |
| `t1f_build_one.py`, `t1g_census.py`, `partitions/` | net-partitioned copies + their DRC |
| `t1h_reconcile.py` / `t1_reconciled.json` | 1542 = 537 / 1437 / 105 decomposition |
| `t1i_validate.py` / `.log` | per-net invariance; `/M4_BATN` truncation; population |
| `t2_pads.py`, `t2_110_pads.csv` | the 110 pads, one row each |
| `t2b_packages.py` / `.log` | the three named packages contain 0 of the 110 |
| `t2c_detail.py`, `t2_geometry.json` | EP sizes and via-grid pitches |

## Limitations

- `CONNECTIVITY_DATA.GetNetItems`/`GetConnectedItems` need a `std::vector<KICAD_T>` that the
  Python wrapper does not expose, so per-net decomposition could not be read from the API. It was
  obtained the harder way — six complete sub-reports — which also cross-checks the total twice.
- The 2 edges that differ between the full-board run and the complete set for `/3V3` and
  `/Auxiliary power/LM2_FB` are **MST tie-breaks**: per-net *counts* are identical, only which pad
  pairs the spanning tree joins differs. Counts, not pair identities, are what is reported here.
- Per-net figures assume nets are mutually independent, which they are by construction; the
  partition sum reproducing 1542 exactly is the check on that assumption.
- The 0.30 mm figure is taken from the published LeitOn 140 µm row as recorded on the board; it was
  not re-fetched in this unit.
- Drill numbers are pad-libraries values, not finished-hole measurements; finished hole differs by
  the plating allowance, which only makes the 0.200 mm pads worse, not better.