# ESC rev_b at 4 oz — fab-readiness verdict

**Item:** make `drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb` buildable at 4 oz.
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/fab-esc-4oz/`
**Board of record:** `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb`
sha256 `992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD` (measured, copied
byte-identical into `kicad/`; repo untouched, `git status` clean on `work/2026-11-11`).
**Tooling:** KiCad 9.0.7 `kicad-cli pcb drc`, KiCad 9.0.7 `python.exe` + `pcbnew`.

---

## 0. Verdict

| question | answer |
|---|---|
| Can the ESC be ordered at 4 oz **as drawn**? | **NO.** 523 violations under 4 oz rules, 499 unconnected items |
| Is 0.20 mm trace legal at 4 oz? | **NO** — 0.20 mm is a **2 oz-class** geometry |
| Do the 4 × 0.20 mm tracks fail? | **YES** — 4 objects, 5.79 mm of copper total, trivial to fix |
| Are they the blocker? | **NO.** The blocker is **371 pad-to-pad gaps of exactly 0.2000 mm inside 9 footprints** |
| Is the board mid-route? | **YES — 2.88 % of routable nets carry any copper.** 154 segments, 628.27 mm |
| Cost of adopting 4 oz rules now | **zero rework** — 97.1 % of the route does not exist yet |

The single sentence: **the ESC is drawn to a 0.20 mm pattern class; 4 oz needs 0.25 mm; the
delta is 371 pad gaps that live inside component footprints and 43 copper gaps that don't.**
Only the 43 copper gaps are movable by routing.

---

## 1. The rule set, and its source

### 1.1 What was used

| rule | value | why |
|---|---|---|
| track width (all layers) | **0.25 mm** | 4 oz outer = 140 µm; heaviest published step is 3 oz = 0.250 mm |
| clearance (track/track, pad/track, pad/pad) | **0.25 mm** | same table, `OTT/OTP/OPP` |
| zone neck (connection width) | **0.25 mm** | same table |
| via annular ring | **0.20 mm** | fab floor is 0.15 mm at 1 oz; heavy copper adds plating/etch spread |
| via drill | **0.30 mm min** | owner rule (0.2–0.3 mm, no microvia); board min is already 0.300 |
| via diameter | **0.70 mm min** | 0.30 drill + 2 × 0.20 ring |
| PTH pad drill | **0.20 mm min** | owner window is 0.2–0.3; fab mechanical min 0.15 |
| copper to board edge | **0.50 mm** | routing burr + heavy copper |

### 1.2 Sources (all fetched during this run)

1. **Eurocircuits PCB Design Classification table**, `eC-classification Table 07/05/2024`,
   downloaded to `sources/EC-classification-ENGLISH-5-2024-V3.png`
   (from `https://www.eurocircuits.com/pcb-design-guidelines-classification/`).
   The per-copper-weight block reads:

   | Base Cu OL | OTT-OTP-OPP | OTW |
   |---|---|---|
   | 35 µm (1 oz) | 0.125 mm | 0.125 mm |
   | 70 µm (2 oz) | 0.200 mm | 0.200 mm |
   | 105 µm (3 oz) | 0.250 mm | 0.250 mm |

   Two things matter and neither is an inference:
   - **`OPP` (pad-to-pad) is part of the same pattern class as `OTW` (track width).** The page
     states: *"The smallest of these values determines the pattern class"*, and
     *"Thicker copper needs a wider isolation for reliable etching."*
   - **Eurocircuits' table stops at 105 µm (3 oz).** 4 oz is not in their classification at
     all, so 0.250 mm at 3 oz is the last *published* floor. Extrapolating downward is
     indefensible; 4 oz can only be equal or wider.

2. **PCBWay PCB capabilities**, `https://www.pcbway.com/capabilities.html`:
   outer copper `1oz/2oz/3oz/4oz/.../8oz (35um/70um/105um/140um/...)` — 4 oz is a real,
   orderable layer weight; min annular ring **0.15 mm**, min drill **0.15 mm**, and (blanket,
   i.e. 1 oz) min trace/space 0.1 mm. The 0.1 mm figure is their standard-copper number; they
   do not publish a per-weight pattern table, so it cannot be used to justify 0.2 mm at 4 oz.

3. **JLCPCB rigid PCB capabilities**, `https://jlcpcb.com/capabilities/pcb-capabilities`:
   *"Finished Outer Layer Copper — 2-layer: 1/2/2.5/3.5/4.5 oz; **Multi-layer: 1 oz / 2 oz**"*.
   **A 4-layer 4 oz board cannot be bought from JLCPCB at all.** This matters for cost, not for
   the rule set: the ESC must go to a heavy-copper shop.

### 1.3 Is 0.20 mm achievable at 4 oz — the decisive question

**No.** 0.200 mm is exactly the **2 oz (70 µm)** row. At 4 oz (140 µm) the copper is twice as
thick as the material the 0.200 mm pattern is specified for, and the only weight ≥ 3 oz with a
published number requires 0.250 mm. Every 0.200 mm feature on this board is therefore a
2 oz-class feature.

Consequence for the audit's 4 tracks: **they fail.** They are also irrelevant to the outcome —
see §6.

---

## 2. Measured board state (and two corrections to the tasking brief)

Command: `python measure_lean.py` → `board_state.json`; raw-file cross-check in §2.3.

| quantity | measured | note |
|---|---|---|
| copper layers | **4** | F.Cu / In1.Cu / In2.Cu / B.Cu |
| stackup | F.Cu **0.14**, In1 0.0525, In2 0.0525, B.Cu **0.14**, ENIG | `esc_rev_b.kicad_pcb:39-97`, `:52` and `:85` = 0.14 |
| board size | **173.95 × 283.08 mm** | edge bounding box |
| footprints | **687** | |
| pads | **3,454** | |
| nets | **667** | |
| zones | **96**, all filled | |
| copper objects | **2,144** = **154 segments + 1,990 vias** | |
| track width histogram | **0.20 mm × 4**, 0.25 mm × 150 | |
| via drill histogram | 0.30 × 16, 0.35 × 12, **0.40 × 1,962** | min 0.300 |
| via annular ring | 0.15 × 16, 0.175 × 12, **0.20 × 1,962** | |
| PTH pad drills | **110 pads at 0.20 mm** in 9 footprints | thermal vias inside exposed pads |
| zone min-thickness parameter | **0.20 mm × 90 zones**, 0.25 mm × 6 | |

### 2.1 BOARD CORRECTION (tasking brief, not the board)

The brief gives the ESC as *"2,144 tracks, 1,990 vias, 341 vias, 33 vias below 0.2 mm, min
drill 0.100 mm, track widths 0.2 / 0.25"* — those are **drone-arm main rev_b's** numbers
concatenated with the ESC's. Measured on the ESC:

- **1,990 vias**, not 341. `2,144 = 154 segments + 1,990 vias` — the "2,144 tracks" figure is
  the *sum of both object classes*.
- **min via drill 0.300 mm**, **0 vias below 0.2 mm**, **0 HDI vias**. The 0.100 mm drill and
  the 33 sub-0.2 vias are drone-arm main's. *(`(via` count in the raw file = 1,990; `(segment` = 154.)*
- **track widths are 0.20 × 4 and 0.25 × 150** — the brief's framing that "0.2 / 0.25" is the
  width set is right, but only 4 segments are at 0.20 mm, so "4 track violations" was correct.

The one number in the brief that is *under*-stated: **110 PTH pads are drilled at 0.20 mm**, so
the board does contain sub-0.3 mm holes — they are just modelled as pads, not vias, which is why
a via-only count reports "0 below 0.2".

---

## 3. DRC, three rule sets, same board

All runs: `kicad-cli pcb drc <board> --format json --severity-all --units mm`.
Rule sets differ only by the `.kicad_dru` sitting beside the board copy.

| run | rule set | violations | unconnected |
|---|---|---|---|
| **A. as-drawn** | project rules: track 0.20, clearance 0.20, ring 0.10 (`esc_rev_b.kicad_pro:133,120,134`) | **16** | **499** |
| **B. 2 oz class** | track 0.20, clearance 0.20, ring 0.15, via dia 0.60 | **16** | **499** |
| **C. 4 oz** | track 0.25, clearance 0.25, ring 0.20, via dia 0.70, PTH drill 0.20, edge 0.50 | **523** | **499** |

### 3.1 True violation count by type — 4 oz (run C, the answer asked for)

`kicad/drc_4oz_final.json`:

| count | severity | type |
|---|---|---|
| **414** | error | `clearance` |
| **70** | error | `annular_width` (28 vias + 42 PTH pads) |
| **16** | error | `via_diameter` |
| **16** | warning | `via_dangling` |
| **4** | error | `track_width` |
| **3** | warning | `connection_width` |
| **523** | | **total violations** |
| **499** | error | **unconnected items** |

The clearance population is almost entirely one geometric fact — measured actual gaps:

| count | pair | actual gap |
|---|---|---|
| **371** | Pad ↔ Pad | **0.2000 mm** |
| 15 | Track ↔ Track | 0.2478 mm |
| 12 | Pad ↔ Track | 0.2250 mm |
| 9 | Track ↔ Track | 0.2434 mm |
| 6 | Pad ↔ Track | 0.2462 mm |
| 1 | Pad ↔ Track | 0.2000 mm |

**Runs A and B differ from C by exactly the pattern class.** At 0.20 mm the board is clean apart
from 16 dangling vias; at 0.25 mm, 414 clearances appear and 371 of them are the same 0.2000 mm
number repeated inside nine footprints. That is the whole story of this item.

### 3.2 The 371 pad gaps are 9 footprints, not routing

| ref | footprint | pad-pairs flagged |
|---|---|---|
| U201 | `QFN-80-1EP_10x10mm_P0.4mm` | 75 |
| U1102–U1602 (×6) | `LQFP-48_7x7mm_P0.5mm` | 43 each = **258** |
| J202, J203 | `USB_C_Receptacle_GCT_USB4105-16P` | 19 each = 38 |

`measure_footprints.py` → `footprint_geometry.json` confirms the cause at pad level: the LQFP is
0.30 mm pads on 0.5 mm pitch (gap 0.20), the QFN-80 is 0.20 mm pads on 0.4 mm pitch (gap 0.20),
the USB-C is 0.30 mm pads at 0.5 mm pitch. **At 4 oz, min track width is 0.25 mm, so a pad
narrower than 0.25 mm is itself below process — these pad arrays cannot be made 4 oz-compliant
by any edit. U201 and the two USB-C connectors are physically incompatible with a 4 oz etch.**

---

## 4. Is it mid-route? — verified, twice

### 4.1 The prior audit's two numbers, checked

- **"154 track segments":** confirmed by three independent methods — `pcbnew` `GetTracks()`
  minus vias = 154; raw file `(segment` = 154; `midroute.py` = 154. It is the *total* routed
  copper on the board, 628.27 mm long (F.Cu 569.47, In2 58.8).
- **"499 unconnected items":** confirmed by my own DRC under all three rule sets, and matches
  every stored report in the repo (`reports/drc_final.json`, `esc_all_front_499_drc.json`, …).

### 4.2 How mid-route, exactly (`midroute.json`)

| measure | value |
|---|---|
| nets with ≥ 2 pads | **556** |
| nets with any copper | **16** → **2.88 %** |
| nets with pads but zero copper | **540** |
| total track length | **628.27 mm** |
| vias on nets that have no track at all | **1,978 of 1,990** |
| the only real routing | 12 nets: `M1..M6_DRV_SCLK` (58.78 mm each) and `M1..M6_DRV_SDI` (~45 mm each) |

Unconnected items span **67 distinct nets**, dominated by `/DGND` (170), `/3V3` (118) and
`/M1..M3_BATN` (112 each) — i.e. the power distribution has not been poured/stitched yet.

The 16 dangling vias are 8 nets × 2: `/Controller and ADC/CAN_SCK`, `/Controller and ADC/STATUS_LED`,
`/M1..M6_STATUS_LED` — vias placed, tracks never drawn. **That is a board mid-route, not a board
with 154 defects.**

### 4.3 Why this matters (the point of the item)

**97.1 % of the route does not exist.** Adopting the 4 oz rules now changes 43 existing copper
objects (see §5.2) and constrains work that has not been done. Adopting them after routing
finishes changes thousands. This is the cheapest possible moment — the only moment cheaper would
have been before the vias were dropped.

---

## 5. The .kicad_dru, and the exact edits

### 5.1 Deliverable

**`kicad/esc_rev_b.kicad_dru`** — the file to install. Copy it next to the board (KiCad resolves
`<board>.kicad_dru` from the project directory):

```
copy evidence\fab-esc-4oz\kicad\esc_rev_b.kicad_dru  repos\drone-arm\hardware\esc\rev_b\
```

It contains 11 rules with the §1.1 numbers and inline provenance comments. Verified loaded:
the DRC descriptions name the rules (`rule '4oz track width 0.25mm min'`, …).

### 5.2 Objects that must move — the clean set

`fix_4oz_minimal.py` → `edit_ledger_minimal.csv` (every row: object, net, layer, before, after,
x_mm, y_mm).

| edit | objects | what | side effects |
|---|---|---|---|
| E1 | **4** | tracks 0.200 → 0.250 mm (`/3V3`, `LM_FB`, `LM2_FB`, `LM_RON`, 5.79 mm total) | none |
| E2 | **28** | vias ring 0.15/0.175 → 0.20 (16 × 0.3/0.6, 12 × 0.35/0.7) | **+54 new clearance** hits — these vias were *placed* at the smaller diameter, so they must be re-positioned, not just grown |
| E4 | **30** | J1103–J1603 header pads ring 0.175 → 0.20 (pad +0.05) | none (2.54 mm pitch) |
| | **62** | **copper objects edited** | 523 → 496 violations (`kicad_min/drc_after_minimal.json`): **468** clearance, 12 annular, 16 dangling (the 28 via growths created 54 new clearance hits) |

Deliberately **not** applied, with reason:

- **110 thermal-via pads (0.20 mm drill, ring 0.15–0.175)** in 9 footprints
  (U1101–U1601 pad 41 = 96, U701/U703 pad 9 = 12, U204 pad 11 = 2). Growing them to 0.30/0.70 was
  applied and measured: it **abuts 48 neighbouring pads** (48 new `PTH pad ↔ PTH pad` clearance
  violations, `kicad_fixed/drc_4oz_after.json`) and still leaves 12 failing. 0.20 mm is inside
  the owner's 0.2–0.3 mm window and inside the fab's 0.15 mm mechanical minimum, so the rule was
  set to 0.20 mm instead. **These 110 are a waiver, or a footprint re-array — not a size bump.**
- **90 zone min-thickness 0.20 → 0.25 + refill** (`kicad_fixed/`): applied and measured. Removing
  sub-0.25 copper exposes **42 zone-neck violations** (36 zone-only, 6 pad↔zone) where the
  0.20-filled board showed 3. Parameter edit, not an object move; must be done with the final
  refill, not before it.
- **43 copper clearance violations (24 track↔track, 19 pad↔track)** on the `M*_DRV_SCLK` /
  `M*_DRV_SDI` buses — 49 distinct segments, gaps 0.2434–0.2478 mm, i.e. 2–6 µm short. These move
  when the bus is dragged, which is a routing action on 49 segments.

**Total, honest count: 62 copper objects have a mechanical fix; the 28 vias additionally need
re-placement (+54 conflicts); 49 bus segments need re-spacing; 90 zones need a parameter +
refill.** So ~90 moved objects plus a re-route of 49 segments — and that still leaves the 371 pad
gaps.

### 5.3 Reconciliation with the prior audit's violation table

| prior claim | measured under 4 oz | verdict |
|---|---|---|
| 4 track | **4** segments at 0.2000 mm | **exact** |
| 28 via | **28** vias (16 ring 0.15 + 12 ring 0.175) | **exact** |
| 6 clearance | **414** (371 pad↔pad @0.2000, 43 copper) | **wrong by 69×** — the prior run cannot have had a 0.25 mm rule applied to pads |
| 140 pad | **42** pad ring < 0.20 **+ 110** pads drilled 0.20 = 152 pad-class items | close but not reproducible as 140 |
| 90 zone | **90 zones carry the 0.20 mm *parameter***; the DRC finds **3** actual necks at 0.25 (42 after a 0.25 refill) | prior number was a parameter census, not a violation count |
| 154 track segments | **154** | **exact** |
| 499 unconnected | **499** | **exact** |

The prior audit's counts were right where they were object counts and wrong where a *rule* had to
be applied across pads and zones.

---

## 6. Can it be ordered at 4 oz as drawn — and the shortest path to yes

**No.** Not by any fab, at any price, without one of two decisions.

The reason is not the 4 tracks and it is not the routing. It is that **0.20 mm is a 2 oz-class
geometry and 9 of this board's footprints are built to exactly 0.2000 mm pad gaps.** At 4 oz the
process floor for both track width and pad gap is 0.25 mm; the pads that would have to shrink to
0.15 mm are already at the minimum trace width of the layer. Runs A and B prove the point
quantitatively: **identical board, 2 oz rules → 16 violations; 4 oz rules → 523.**

### Shortest path to yes (in order, cheapest first)

1. **Install `esc_rev_b.kicad_dru` now, before routing continues.** Cost: one file copy. It makes
   the remaining 540 nets route at 0.25/0.25 instead of 0.20/0.20, which is the entire point of
   this item — **zero rework, because 97.1 % of the route does not exist.**
2. **Get one written answer from the heavy-copper fab**, in the quote, and keep it:
   *"4-layer, 4 oz outer (140 µm), min pattern 0.200 mm, min pad gap 0.200 mm in
   `QFN-80-1P_10x10_P0.4`, `LQFP-48_P0.5`, `USB-C 16P`; annular ring 0.15 mm on 28 vias;
   0.20 mm drills in exposed pads."*
   - **If accepted** (fab burden — the acceptable spend): the board needs only **62 copper edits**
     (§5.2) plus a re-place of the 28 vias, then finish the route at 0.25 and re-run DRC. **This is
     the shortest path to a fabbable 4 oz board, and it is ~1 day of mechanical work.**
   - **If refused** (fabs publishing 0.25 mm at ≥ 3 oz: Eurocircuits-class): **4 oz is
     incompatible with U201 (QFN-80 P0.4), J202 and J203 (USB-C 0.5 pitch).** No copper move
     fixes it. The choice is then:
     - **(2a) 2 oz outer, 1.5 → 2 oz inner.** Geometry *already compliant* — run B is 16
       dangling vias and nothing else. Zero copper rework, orderable the day routing finishes.
       This contradicts the owner rule "4 oz required", so it is the owner's call, not mine.
     - **(2b) keep 4 oz and change 3 packages** (U201, J202, J203) plus narrow the 6 LQFP pad
       arrays 0.30 → 0.25 mm. That is a placement respin of the fine-pitch section — the exact
       rework this programme exists to avoid.
3. **Do not finish the 499-item route at 0.2 mm rules.** That is the failure mode: it converts a
   free rule change into a rip-up of 540 nets.

**Recommended:** step 1 unconditionally; step 2 as a quote question to two heavy-copper shops
(PCBWay lists 4 oz; JLCPCB cannot build 4-layer 4 oz at all). If the answer is "0.25 mm only",
escalate 4 oz vs 2 oz to the owner with §3.1 in hand — it is a one-line decision with a measured
cost on each side, and it is not mine to take.

---

## 7. Checklist line for the fab-readiness pack

| check | state | evidence |
|---|---|---|
| 4 oz rules defined with source | **PASS** | §1, `kicad/esc_rev_b.kicad_dru` |
| DRC clean under correct rules | **FAIL — 523** | `kicad/drc_4oz_final.json` |
| Zero unconnected nets | **FAIL — 499** | same file; 540 nets carry no copper |
| Pattern class compatible with 4 oz | **FAIL — 9 footprints at 0.2000 mm** | §3.2, `footprint_geometry.json` |
| No HDI / standard PTH only | **PASS** | 0 vias < 0.30 mm; 1,990 standard through vias |
| Copper weight as declared | **PASS** | `:52` and `:85` = 0.14 mm = 4 oz |
| Revision-stamped gerber/drill/pos package | **FAIL (not produced)** | board is 2.88 % routed; a package would be meaningless — deliberately not generated |
| Waiver candidates | 110 thermal vias at 0.20/ring 0.15–0.175 (inside EPADs, mask-covered); 371 pad gaps **if** the fab accepts 0.200 mm at 4 oz | §5.2, §6 |

---

## 8. Artefacts and reproduction

| file | what |
|---|---|
| `kicad/esc_rev_b.kicad_dru` | **the deliverable** — 4 oz rule set |
| `kicad/esc_rev_b.kicad_pcb`, `.kicad_pro` | byte-identical copy of the repo board (sha256 verified) |
| `kicad/drc_4oz_final.json`, `.rpt` | authoritative 4 oz DRC: 523 / 499 |
| `kicad_baseline/drc_default.json`, `.rpt` | as-drawn project rules: 16 / 499 |
| `kicad_2oz/drc_2oz.json` | 2 oz counterfactual: 16 / 499 |
| `kicad_fixed/` | full edit set incl. thermal vias + zone refill: 520 violations |
| `kicad_min/` | minimal edit set (62 objects): 496 violations |
| `edit_ledger.csv` | 262 edits with coordinates (full set) |
| `edit_ledger_minimal.csv` | **62 edits with coordinates (recommended set)** |
| `board_state.json`, `footprint_geometry.json`, `midroute.json` | measurements |
| `measure_lean.py`, `measure_footprints.py`, `midroute.py` | measurement scripts |
| `fix_4oz.py`, `fix_4oz_minimal.py` | edit scripts (operate on copies, never the repo) |
| `analyse_drc.py` … `analyse5.py` | DRC population analysis |
| `sources/EC-classification-ENGLISH-5-2024-V3.png` | Eurocircuits classification table (primary source) |

Reproduce:

```powershell
$cli="C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"
$py="C:\Program Files\KiCad\9.0\bin\python.exe"
$ev="E:\engineering-portfolio-audit\evidence\fab-esc-4oz"
& $cli pcb drc "$ev\kicad\esc_rev_b.kicad_pcb" -o "$ev\kicad\drc_4oz_final.json" --format json --severity-all --units mm
& $py "$ev\measure_lean.py" "$ev\kicad\esc_rev_b.kicad_pcb" "$ev\board_state.json"
& $py "$ev\midroute.py"    "$ev\kicad\esc_rev_b.kicad_pcb" "$ev\midroute.json"
& $py "$ev\fix_4oz_minimal.py" "$ev\kicad_min\esc_rev_b.kicad_pcb" "$ev\kicad_min\esc_rev_b.kicad_pcb" "$ev\edit_ledger_minimal.csv"
```

Nothing was written to `repos/drone-arm`: board and project were copied out, edits applied to the
copies only. `git status --porcelain -uno` on `work/2026-11-11` is empty.

---

## 9. What is UNVERIFIED

- **The fab's actual 4 oz pattern capability.** No shop publishes a per-weight table that
  includes 4 oz; §1 rests on the 3 oz row plus the direction of the trend. The §6 step-2 quote
  question is the only way to close it, and it must be answered in writing before routing
  finishes.
- **Whether 0.15 mm annular ring is acceptable on a 4 oz board.** Measured/flagged, not
  researched; 0.20 mm is assumed as the safe target.
- **Zones after a 0.25 mm refill.** The 42 zone-neck violations in `kicad_fixed/` are what KiCad
  reports after my refill; the final fill must be re-checked once the route is complete, because
  neck count depends on the copper that does not exist yet.
- **Assembly.** The QFN-80 and USB-C findings are copper-etch findings; whether the same pads
  solder at 4 oz (paste volume, heel fillet) was not analysed and could be a second, independent
  objection from the assembly house.
- **Cost.** No quote was obtained. PCBWay and JLCPCB capability pages were read, nothing was
  priced; the $60 coupon cap is untouched by this item.