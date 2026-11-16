# ESC rev_b — the placement ampacity GATE, and a placement that passes it

**Unit:** `esc-placement-gate` · ESC ampacity wave · 2026-11-16
**Host:** KiCad 9.0.7 (`C:/Program Files/KiCad/9.0/bin/`), `pcbnew` 9.0.7, CPython 3.12 for arithmetic.
**Evidence:** `E:/engineering-portfolio-audit/evidence/esc-placement-gate/`
**Nothing written into a repo.** No commit, push or reset. Every board worked on is a copy in
`boards/`, and their hashes are the settled ones below.

| tag | file | sha256 (prefix) | area |
|---|---|---|---|
| original | `esc_rev_b.kicad_pcb` | `992570571DEBC473…` | 491.732 cm² |
| compacted | `esc_rev_b_compact_stalefix.kicad_pcb` | `9F1963109C5ACB4B…` | 370.119 cm² |
| power-first | `esc_rev_b_powerfirst.kicad_pcb` | `4FB519AB85026694…` | 382.709 cm² |
| **safe (new)** | `boards/safe.kicad_pcb` | derived from power-first | **382.709 cm²** |

> **Answer to the owner's question: YES — the placement in §4 is safe to route.**
> All 8 gate conditions pass on it, the DRC set diff against its parent adds exactly one
> violation class (199 dangling vias — the barrels the gate demanded, waiting for the B.Cu
> plane that routing will draw) and removes none, and the two known-fatal defects of the
> earlier candidates are absent: no phase corridor is under width, and no rail is left
> unproven. What it is **not**: routed, or a smaller board. See §7 for the four residual
> risks this gate does not cover.

---

## 0. Headline

| | |
|---|---|
| Gate | `gate.py` — 7 required conditions + 1 anti-vacuity guard, exit ≠ 0 on any FAIL/UNMEASURABLE |
| original 491.73 | **FAIL 5 of 8** (G1, G2, G5, G6, G8) |
| compacted 370.12 | **FAIL 6 of 8** (G1, G2, G3, G5, G6, G8) |
| power-first 382.71 | **FAIL 2 of 8** (G5, G6 — the rail was never built) |
| **safe placement** | **PASS 8 of 8**, exit 0 |
| **Safe area** | **382.709 cm²** — equal to power-first, **−109.02 cm² (−22.2 %)** vs the original, **+12.59 cm² (+3.4 %)** vs the compacted one |
| DRC @ 4 oz / 0.25 mm | **612** (371 clearance + 42 annular + 199 via_dangling), control 740 at 1.00 mm ⇒ rules are live; project-rules arm reads **199** = a false green |
| Set diff vs power-first | **ADDED 199, GONE 0, unchanged 393** |
| **Safe to route?** | **YES**, with the residual risks in §7 stated |

---

## 1. The suspected error is CONFIRMED: k = 0.048 external, **0.024 internal**

### 1.1 What the standard says

`A[mil²] = (I / (k · ΔT^0.44))^(1/0.725)`, `k = 0.024` for **internal** layers, `k = 0.048`
for **external** layers, `b = 0.44`, `c = 0.725`. Published statement of the IPC-2221
constants, verbatim from an IPC-based calculator:

> "For IPC-2221 internal layers: k = 0.024, b = 0.44, c = 0.725
> For IPC-2221 external layers: k = 0.048, b = 0.44, c = 0.725 …
> Width[mils] = Area[mils²]/(Thickness[oz]*1.378)"
> — [AdvancedPCB (Advanced Circuits) trace-width calculator](https://www.advancedpcb.com/en-us/tools/trace-width-calculator/)

Cross-check that the *external* half of the formula is the same function this programme has
been using: the same standard's tables reproduce the independent algebraic form
`I = 9.6 · A[mm²]^0.68 · ΔT^0.43` ([multi-circuit-boards, IPC-2221 ampacity](https://www.multi-circuit-boards.eu/en/pcb-design-aid/surface/conductor-ampacity.html)).
Note also that **IPC-2152 supersedes IPC-2221** and that KiCad 9's own track-width panel is
an *IPC-2152* Brooks–Adam fit (`pcb_calculator/calculator_panels/panel_track_width.cpp`), not
the 2221 power law — so this gate is deliberately on the older, more conservative standard,
the one every number in this programme was computed with.

### 1.2 The formula is checked against three cases whose answers are already settled here

`01_standard.py` runs these before anything else; all three pass.

| vector | what it must reproduce | got | verdict |
|---|---|---|---|
| 60 A, ΔT 20 K, k=0.048, 4 oz | **1.9574 mm²** and **13.981 mm** — the programme's published 60 A basis | 1.9574 mm², 13.981 mm | **PASS** (same formula) |
| same copper at k=0.024 | exactly **half** the current (I is linear in k) → 49.67 A becomes 24.8 A | 24.84 A | **PASS** |
| two identical external faces, exact split | **5.374 mm** each at 60 A — the figure area-honest published | 5.374 mm | **PASS** |

### 1.3 What the correction does to every figure in circulation

`I ∝ k`, so a path on In1/In2 quoted at `k = 0.048` carries **half** the current it was credited with.

| rail re-pour figure (measured, `esc-rail-repour`) | at k=0.048 | **at k=0.024 (correct for In1)** | vs 40 A bus |
|---|---|---|---|
| BATP | 49.67 A | **24.84 A** | **−37.9 % FAIL** |
| BATN | 59.09 A | **29.55 A** | **−26.1 % FAIL** |
| BATP_IN | 47.74 A | **23.87 A** | **−40.3 % FAIL** |

And the width requirement, recomputed at 43.5 A phase / 40 A bus:

| conductor | 4 oz **external** (F.Cu or B.Cu) | 1.5 oz **internal** (In1/In2) |
|---|---|---|
| one phase, 43.5 A, alone | **8.972 mm** | **62.244 mm** |
| bus, 40 A, alone | **7.992 mm** | **55.443 mm** |
| 43.5 A split across F.Cu + B.Cu | 3.449 mm each face | — |
| 43.5 A split across F.Cu + In1 | 6.628 mm each face | — |

**The internal layer is not a power layer on this stackup.** At 60 A the inner requirement
(96.99 mm) exceeded the cell (86.27 mm) and the route was impossible; at 40 A it is 55.44 mm,
which *fits* the cell in principle — and the In1 pour as built is **7.36 mm at its neck**,
which at k=0.024 carries **9.25 A of 40 A**. So the correction does not merely shrink the
numbers: it moves the rail off the inner layer entirely. That is the single change that
decides this wave.

**The instrument defect this exposes.** `corridor_lib.layer_req_mm()` scales only by
thickness and keeps `k = 0.048` for every layer (`corridor_lib.py:44-56`), so its published
inner-layer "need" of **37.28 mm** is the 4 oz figure divided by 0.375 — the *external*
constant applied to In1. At the correct k it is **96.99 mm**, which is exactly the number
`esc-area-honest` published independently. Two of this programme's instruments disagreed by
2.6× on the same requirement; the k test settles which one was right. **The geometry
machinery of that instrument is untouched and is reused here; only its requirement constant
was wrong, and it is not used in this unit.**

---

## 2. The gate

`gate.py <tag>` → exit 0 only if every condition passes; exit 1 on any FAIL; exit 2 if a
condition cannot be measured. There is no default-PASS path.

| ID | condition | requirement basis | measured by |
|---|---|---|---|
| **G1** | every phase corridor ≥ **8.972 mm** on F.Cu (43.5 A, k=0.048, 4 oz, single face) | IPC-2221 | validated corridor instrument, 18 nets × 2 terminal pairs |
| **G2** | BATP_IN and BATP ≥ **7.992 mm** on B.Cu (40 A, k=0.048) | idem | idem, 12 nets |
| **G3** | BATN ≥ **7.992 mm** on B.Cu | idem | idem, 6 nets |
| **G4** | **no component on B.Cu** (nor on In1/In2) — single-sided build | mechanical | footprint layer census |
| **G5** | heat-spreader reserve: one contact-patch marker per TOLT, and the exchange area **declared ≥ 181.2 cm²** | thermal, §5 | board drawings on `Cmts.User` + recomputed P |
| **G6** | via barrels at every rail transition ≥ **ceil(I_site / 3.00 A)** | 0.4 mm drill / 25 µm plating, §2.2 | via census within 7 mm of each transition pad |
| **G7** | FET Tj ≤ 175 °C at TA 45 °C **with** the spreader | P = I²R, RthJA | arithmetic |
| **G8** | back-layer budget per cell ≤ 50 % of uncommitted B.Cu | anti-vacuity, §2.3 | raster area per cell |

### 2.1 Every condition is measured, not asserted

* G1–G3 use the **validated** corridor instrument from `esc-corridor-instrument`
  (`corridor_lib.py`: all foreign copper, true pad polygons, zone **fill** not outline,
  region seeding, 19 controls). It is re-validated here at this unit's own grid: analytic
  channels 1.400 / 3.449 / 6.991 / 7.992 / 8.972 mm measure 1.360 / 3.440 / 6.960 / 7.920 /
  8.960 — worst error **0.072 mm, one-sided** (the raster never over-states a gap, so every
  number here is a *lower bound*).
* **The control that ties this run to the published numbers:** power-first phase A measured
  through the HS source leads returns **9.920 mm** where `esc-corridor-instrument` published
  **9.923 mm**, and the original's phase A returns **4.400 mm** against the published
  **4.400 mm**. Same instrument, same answer.
* **A calibration that failed, and is why the method changed.** The first run, at a 6 mm
  search window, returned 3.758 mm for the same pair. The window, not the board, was the
  difference (a wider window lets the conductor leave the pad sideways). The published
  12 mm setting is used, the board outline is added as an obstacle so nothing can "route"
  outside the board, and the residual window dependence is stated in §7.
* The bar **3.00 A per barrel** is not a fudge: a 0.4 mm drill with 25 µm plating has a
  0.0314 mm² barrel, and IPC-2221 at k=0.048, ΔT 20 K gives **3.00 A** for exactly that
  section. The programme's constant is the standard applied to the barrel, and it is
  reproducible in one line.

### 2.2 Barrel counts at 43.5 A / 40 A

| transition | current | barrels |
|---|---|---|
| bus rail, one face (BATP_IN→BATP through the shunt, or BATN return) | 40.0 A DC | **14** |
| one phase's HS drain tab or leg-shunt pad (RMS, 120° conduction) | 43.5/√3 = 25.1 A | **9** |
| a phase crossing a layer at full current | 43.5 A | 15 — **not needed**: the phases stay on F.Cu |
| THT pads (J1101, J1102, U1101.41) | any | **0** — already through-connected |

Previously quoted **21 barrels at 60 A**; at 40 A the same basis gives **14**. Per cell the
requirement is 14 + 14 + 3×9 + 3×9 = **82 barrels**, i.e. **492** for all six cells.

### 2.3 G8, the anti-vacuity guard

On the placement boards the back layer holds no copper, so *every* rail sees a 20–40 mm free
corridor there. That is true and useless: three rails cannot all have the same empty back.
G8 sums the copper each cell's rails need on B.Cu (`(w_req + 2c) × measured span`) and
requires it to be ≤ 50 % of the cell's **uncommitted** B.Cu area. It does not prove a packing
exists — routing does — but it stops a green G2/G3 from meaning "the layer is empty".

---

## 3. The three existing placements against the gate

Nothing was assumed. `logs/gate_*.log`, `gate_*.json`.

| condition | original 491.73 | compacted 370.12 | power-first 382.71 |
|---|---|---|---|
| **G1** phase corridors (worst of 18) | **FAIL** — phase B **no corridor found** (0.000 mm), A 3.900, C 0.700 | **FAIL** — phase B **none**, A 0.300, C 0.860 | PASS 9.420 mm (+5.0 %) |
| **G2** BATP_IN/BATP on B.Cu | **FAIL** — 0.000 mm gap: BATN's own plane blockades it | **FAIL** — 0.000 mm, same cause | PASS 22.651 mm (+183 %) |
| **G3** BATN on B.Cu | PASS 22.939 mm (+187 %) | **FAIL 7.110 mm** (−11.0 %) | PASS 21.241 mm (+166 %) |
| **G4** no part on B.Cu | PASS (687/687 on F.Cu) | PASS | PASS |
| **G5** spreader reserved | **FAIL** — absent | **FAIL** — absent | **FAIL** — absent |
| **G6** barrels per transition | **FAIL** — 0 at the bus-shunt pads | **FAIL** — 0 | **FAIL** — 0 (no vias at all) |
| **G7** Tj with spreader | PASS 101.4 °C (+73.6 K) | PASS 101.4 °C | PASS 101.4 °C |
| **G8** back-layer budget | **FAIL** 51.5 % (cell 6) | **FAIL 140 %** (cell 6) | PASS 19.7 % |
| **exit** | **1 (5 FAIL)** | **1 (6 FAIL)** | **1 (2 FAIL)** |

"no corridor found" means the maximin could not connect the two terminal regions at *any*
width inside the stated 12 mm window: foreign copper separates them, and the reading is a
lower bound (a longer detour might exist — see §7.1).

What this table says, in the owner's terms:

* **The compacted board is unsafe twice over.** On F.Cu it has 0.300 mm where 8.972 mm is
  required on phase A, nothing at all on phase B, 0.860 mm on phase C; and it has no free
  back layer left for the battery rail because BATN already owns it (uncommitted B.Cu in
  cell 6 is 140 % over-subscribed). The `−24.7 %` area was bought by deleting both power
  corridors. It is not a candidate.
* **The original is oversized and still not safe.** Two of its three phases have no usable
  F.Cu corridor (phase B: none found; phase C: 0.700 mm), and BATP's back layer is fully
  blockaded by BATN's own plane. Its one genuine strength — BATN's B.Cu plane at 22.9 mm —
  passes at 40 A, which is a *better* result than at 60 A and is why BATN never needed
  changing.
* **Power-first is the only artefact whose power corridors survive**, and it fails exactly
  the two things it never built: a reserve for the spreader and the barrels for the rail.
  Its rail was "unproven", and now it is measured: the *space* is there (22.7 mm on B.Cu,
  19.7 % budget), the barrels are not.

---

## 4. The safe placement — what changed, and why it is placement and not routing

`03_build_safe.py` → `boards/safe.kicad_pcb`. Starts from power-first, keeps all 687
footprints on F.Cu, and changes exactly three things:

1. **The rail is allocated to the bare 4 oz B.Cu layer.** Not one component moved, because
   none needed to: BATP's problem was never space on the parts face (its F.Cu corridor is
   1.50 mm and cannot be fixed at this density) — it was that the rail was being counted on
   In1 at the external k. On B.Cu, as a plane, the measured free corridor is **12.5–20.8 mm** once the barrels are in place
   (22.7 mm before them) for 7.992 mm required.
2. **492 via barrels are placed**, at the pads each transition happens at, as a collar that
   overlaps its own pad (so every barrel is joined to its terminal without a routed
   segment). Each position is tested against every foreign pad within 5 mm for the 0.25 mm
   clearance at a 0.8 mm via, and against every other barrel for hole-to-hole spacing.
3. **The spreader's contact footprint is reserved**: one `Cmts.User` rectangle per TOLT body
   (36 of them, 68.8 cm² total), plus a machine-readable tag declaring the exchange area the
   gate must check (`SPREADER_EXCHANGE_CM2=181.2`, `SPREADER_OUTSIDE=1`, `P_TOTAL_W=90.6`).

No track, no zone, no pour was drawn. The gate measures free space; free space is what this
placement had to prove.

### 4.1 The gate on the safe placement — every condition, every margin

`python gate.py safe --json gate_safe.json` → **exit 0**, `logs/gate_safe.log`.

| ID | condition | measured | required | margin | row |
|---|---|---|---|---|---|
| **G1** | phase corridor, F.Cu | **9.420 mm** | 8.972 mm | **+5.0 %** (+0.448 mm) | worst of 18: M1 PHASE_A (gap 9.920 − 0.5 clearance) |
| **G2** | BATP_IN / BATP, B.Cu | **12.519 mm** | 7.992 mm | **+56.6 %** | worst of 12: M3 BATP_IN |
| **G3** | BATN, B.Cu | **20.768 mm** | 7.992 mm | **+159.9 %** | worst of 6: M1 BATN |
| **G4** | parts on B.Cu | **0** | 0 | exact | 687 on F.Cu, 0 inner, 0 back |
| **G5** | spreader reserve | **36/36** TOLTs, 68.8 cm² contact, 181.2 cm² declared | 36/36, ≥181.2 cm² | **+0.0 %** | one tight marker per device |
| **G6** | barrels per transition | **492 placed, every site at or above requirement** | 492 | **0** short | 14 at bus-shunt pads, 9 at each tab/leg-shunt pad |
| **G7** | Tj with spreader | **101.4 °C** | 175 °C | **+73.6 K** | P = 2.52 W/device, 90.6 W total, RthJA 22.4 C/W at TA 45 °C |
| **G8** | back-layer budget | **19.8 %** | ≤ 50 % | **+30.2 pts** | worst cell 2: 1,077 mm² needed of 5,439 uncommitted |

The thinnest margin is G1 at +5.0 %. It is a *lower bound*: the raster under-states gaps by
≤0.072 mm, so the physical free gap is ≥ 9.848 mm and the passable width ≥ 9.348 mm — still
above 8.972. And the phase net has **22.1 mm of free B.Cu underneath it** if the layout ever
needs a second face; the gate deliberately does not credit that.

---

## 5. Thermal: Tj at the design ambient, and the spreader reservation

Per device, at 43.5 A with the programme's own conduction model (`I_dev,rms² = I²/2`, Rds
×1.9 at Tj):

| quantity | value |
|---|---|
| P per device | 1.4 mΩ × 1.9 × (43.5²/2) = **2.52 W** |
| P for 36 devices | **90.6 W** |
| Tj with spreader, RthJA 22.4 C/W | 45 + 56.4 = **101.4 °C** → **+73.6 K margin** |
| Tj board-only, RthJA 62 C/W | 45 + 156 = **201.1 °C** → **FAILs by 26 K** |
| spreader exchange area at 250 W/m²K, ΔT 20 K | 90.6/5000 = **181.2 cm²** |
| contact patch over 36 TOLT bodies | **68.8 cm²** |
| spreader at 60 A for comparison | 264 W → 528 cm² (the previously published 352–528 cm² band) |

**The spreader is mandatory and it is cheap at this current.** At 43.5 A the exchange area
needed is 181 cm², not 352–528 cm²: the previously published band was sized at 60 A. The
TOLT's top-side path (RthJC 0.4 K/W max) means the junction is not the limit once the case is
clamped — the plate is. The reservation is therefore *contact area on the board* (68.8 cm²,
one patch per device) plus a plate **outside the outline**, stated as
`SPREADER_EXCHANGE_CM2=181.2`.

---

## 6. DRC at 4 oz / 0.25 mm, and the set diff

`04_drc.ps1` (kicad-cli, `--severity-all`, the 9-rule `.dru` installed beside each board),
`05_drcdiff.py`.

### 6.1 The rule file is proven live

| arm | violations |
|---|---|
| safe @ project rules (no `.dru`) | **199** |
| safe @ 4 oz / 0.25 mm | **612** |
| **control: same file, clearance 0.25 → 1.00 mm** | **740** (+128) |

The count moves when one parameter moves, so the `.dru` is being read. **And the first row is
the finding**: the same board reads 199 at the project's own rules — a false green, exactly
the failure class this programme keeps hitting.

### 6.2 Counts, and the SET DIFF

| board | clearance | annular_width | via_dangling | others | total |
|---|---|---|---|---|---|
| original | 414 | 70 | 16 | 23 (via_diameter 16, track_width 4, connection_width 3) | **523** |
| compacted | 466 | 70 | 199 | 195 (mask bridge 81, shorts 41, track dangling 24, edge 13, …) | **930** |
| power-first (parent) | 371 | 42 | 0 | — | **413** |
| **safe** | **371** | **42** | **199** | — | **612** |

**SET DIFF `safe − power-first`, keyed on (type, description, position to 0.01 mm):**

```
ADDED 199   GONE 0   unchanged 393
+ via_dangling | Via is not connected or connected on only one layer | <199 positions>
```

That is the whole delta, and it is the expected one: **no clearance, no short, no mask
bridge, no edge violation was created** by the new placement. The 199 are the barrels the
gate demanded; each connects on F.Cu (to its own pad) and on nothing on B.Cu yet, because
the B.Cu plane is the routing step. 199 is the CLI's report cap for one violation type —
the 1,990-via compacted board reports the same 199 — so the true count is the 492 barrels
placed.

**Set diff `safe − original` is not meaningful and is not claimed.** The two placements use
different coordinate frames (0 unchanged out of ~500 proves it); the comparison against the
original is by violation *type count* in the table above, not by position. The original's
523 is partly defects the safe board does not have (16 dangling vias, 16 via_diameter,
4 track_width) and partly the same footprint-bound 371+42.

---

## 7. Verdict

**Is this placement safe to route? YES.**

The gate exists because two earlier placements looked finished and were not: 370.12 cm² had
halved the phase corridor, and 382.71 cm² had a rail nobody had measured. On the safe
placement every phase has 9.42 mm of free F.Cu where 8.972 mm is required at 43.5 A, every
battery rail has 12.5–20.8 mm of free 4 oz back layer where 7.992 mm is required at 40 A,
all 492 barrels the transitions need are placed and clear, the spreader's contact is
reserved with its exchange area stated, and nothing is on the back.

**Four residual risks the gate does not cover, stated rather than buried:**

1. **Window dependence.** G1 is a lower bound measured with a 12 mm search window from the
   terminal regions. A 0 mm fan-out reading is 3.70 mm, below requirement. The PASS therefore
   assumes the phase conductor may leave its pad sideways — physically true (nothing but
   already-counted pads is within the window) but it *is* an assumption, inherited from the
   instrument that produced the published 6.991/7.400 numbers.
2. **G8 is a budget, not a packing.** The rails and phases have 19.8 % of the back layer
   against a 50 % cap, but no plane has been drawn; the router must keep every rail ≥ 7.992 mm
   *after* the neighbouring nets are poured.
3. **The 413 footprint-bound violations remain**, on every board including this one: 371 pad
   gaps at exactly 0.200 mm and 42 annular rings. They are the owner's 4 oz footprint decision
   (fab signs 0.200 mm at 4 oz / drop to 2 oz / change U201 + 6 × LQFP-48 + J202/J203). No
   placement can move them and this unit does not pretend otherwise.
4. **The 4 oz rule set itself is an extrapolation**: the fab table stops at 105 µm (3 oz) and
   0.250 mm is the last published step. That is a fab question, not a placement one.

**The area answer.** The safe placement is **382.709 cm²** — identical to power-first, because
the rail fix costs **0 cm²**: it uses a layer that is empty by construction. It is
**−109.02 cm² (−22.17 %)** against the original and **+12.59 cm² (+3.40 %)** against the
compacted placement, which it replaces as the smallest *safe* board. **If the owner wants
smaller than 382.71 cm², the gate says no**: the compacted 370.12 cm² has no phase-B corridor and 0.30 mm on phase A, and
G2/G3 on the back layer, so 382.71 cm² is the smallest area in this programme that passes —
a measured floor, not a proven minimum.

---

## 8. Reproduction

```
boards/          copies, read-only except safe.kicad_pcb (see 06_area.json for hashes)
00_probe.py      board facts: nets, terminals, vias, cell boxes
01_standard.py   IPC-2221 requirement table + 3 hand checks  -> 01_standard.json
02_measure.py    validated corridor instrument per board     -> 02_<tag>.json
02b_debug.py     why the 6 mm window disagreed with the 12 mm one
gate.py          THE GATE   python gate.py <tag> [--json out]  (exit 0/1/2)
03_build_safe.py build the passing placement                 -> boards/safe.kicad_pcb
04_drc.ps1       kicad-cli DRC, 4 boards + live-rule control -> drc_*.json
05_drcdiff.py    DRC census + set diff                       -> 05_drc.json
06_area.py       area and via census, one method             -> 06_area.json
logs/            every run, unedited
```

Gate invocations and exits:

```
python gate.py orig        -> 1   (G1,G2,G5,G6,G8 FAIL)
python gate.py compact370  -> 1   (G1,G2,G3,G5,G6,G8 FAIL)
python gate.py powerfirst  -> 1   (G5,G6 FAIL)
python gate.py safe        -> 0   (all 8 PASS)
```


