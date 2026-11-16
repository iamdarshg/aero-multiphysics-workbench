# Wave 12 — drone-arm: of the 36 non-through vias, how many ride the owed respin?

**Question (one):** of drone-arm's 36 non-through vias on the REPO board, how many belong to the
respin drone-arm already owes (7th actuator channel + servo rail) — i.e. how many are **FREE** to fix?

**Answer: 0 of 36.** None of the 36 sits on a 7th-actuator net or the servo rail. All 36 are on 14
preserved signal nets, so all 36 need real layout work. Details and the set diffs below.

Board under test: **copy** of `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb`
(sha256 `9B3BBA85…F89953C`), in `work/work.kicad_pcb`. 165 footprints, 175 nets, 4 copper layers
F.Cu / In1.Cu / In2.Cu / B.Cu. Read-only census; no repo write, no VCS command.

---

## 1. Census confirmed — 341 / 36 / 33+3 / 0.100

| metric | value | how |
|---|---|---|
| vias total | **341** | `GetTracks()`, `Type()==PCB_VIA_T` |
| through | 305 | span == F.Cu→B.Cu |
| **non-through** | **36** | span ≠ F.Cu→B.Cu (**not** drill) |
| declared MICROVIA | **33** | `GetViaType()` |
| declared BLIND_BURIED | **3** | `GetViaType()` |
| min drill | **0.100 mm** | `GetDrillValue()` |

All four settled figures reproduce exactly. The 33/3 split is corroborated independently by drill
**within the 36**: 0.100 mm → 33 vias, all declared MICROVIA; 0.300 mm → 3 vias, all declared
BLIND_BURIED; no cross-over. (Board-wide, 0.300 mm also appears on 24 through vias, so the drill
crosstab only discriminates the non-through population.)

### Set diff that the totals hide: declared type ≠ layer pair, for 10 of 36

| test | count |
|---|---|
| span = 2 copper layers (adjacent pair, microvia-legal) | **29** |
| span = 3 copper layers (true blind/buried) | **7** |
| declared type disagrees with its own layer pair | **10** |

The 10: **7 vias declared MICROVIA span In1.Cu→B.Cu or F.Cu→In2.Cu (3 layers)** — a microvia may
only join adjacent copper; and **3 vias declared BLIND_BURIED span only In2.Cu→B.Cu (adjacent)**.
So "33 microvia" is a *declared* count; the adjacent-pair population is 29. Either the type field is
mis-set on 10 vias or 7 of them are unmanufacturable as drawn — not resolved here (out of scope), but
the two numbers are not the same population and this board's HDI story rests on that 33.

Span breakdown: F→In1 14 · In1→In2 10 · In2→B 5 · In1→B 4 · F→In2 3.

---

## 2. All 36: footprint, pad, net

No via has a parent footprint (`GetParentFootprint()` = None for all 36), so attributions are
geometric: grouping = footprint of the nearest pad of any footprint; "pad" = nearest same-net pad.
Full machine table in [`tables.md`](tables.md) / [`via_census.json`](via_census.json).

| # | footprint | pad | net | span | x | y |
|---|---|---|---|---|---|---|
| 1 | **U10** | U10.29 | `/3V3` | F→In1 | 58.400 | 55.550 |
| 2 | **U10** | U10.12 | `/GNSS_RX` | F→In1 | 53.900 | 50.600 |
| 3 | **U10** | U10.27 | `/HGM` | F→In1 | 57.600 | 55.150 |
| 4 | **U10** | U10.4 | `/LSM_INT1` | F→In1 | 54.400 | 47.400 |
| 5 | **U10** | U10.4 | `/LSM_INT1` | In1→In2 | 54.400 | 47.400 |
| 6 | **U10** | U10.25 | `/PA_EN` | F→In2 * | 57.600 | 52.200 |
| 7 | **U10** | U10.25 | `/PA_EN` | In2→B | 58.000 | 51.900 |
| 8 | **U10** | U10.24 | `/RF_GPIO0` | In2→B | 56.500 | 55.200 |
| 9 | **U10** | U10.22 | `/RF_GPIO2` | F→In2 * | 55.600 | 55.200 |
| 10 | **U10** | U10.18 | `/RF_MISO` | F→In1 | 53.900 | 53.000 |
| 11 | **U10** | U10.18 | `/RF_MISO` | In1→In2 | 53.900 | 53.000 |
| 12 | **U10** | U10.17 | `/RF_MOSI` | F→In1 | 55.500 | 52.600 |
| 13 | **U10** | U10.17 | `/RF_MOSI` | In1→B * | 55.500 | 52.600 |
| 14 | **U10** | U10.20 | `/RF_RESET_N` | F→In1 | 53.800 | 54.000 |
| 15 | **U10** | U10.22 | `/SENS_SCLK` | In1→B * | 55.585 | 53.453 |
| 16 | U40 | U40.15 | `/915 MHz RF/VDD_CC112` | F→In1 | 95.150 | 64.200 |
| 17 | U40 | U40.4 | `/RF_GPIO2` | F→In1 | 91.562 | 60.750 |
| 18 | U40 | U40.7 | `/RF_MOSI` | In1→B * | 90.600 | 58.000 |
| 19 | U40 | U40.7 | `/RF_MOSI` | F→In1 | 91.562 | 62.250 |
| 20 | C12 | U10.12 | `/GNSS_RX` | In1→In2 | 52.900 | 53.200 |
| 21 | C12 | U10.16 | `/RF_SCLK` | F→In2 * | 52.950 | 52.200 |
| 22 | C32 | U10.67 | `/RP2354B MCU/USB_DP_MCU` | F→In1 | 60.800 | 44.100 |
| 23 | C32 | U10.67 | `/RP2354B MCU/USB_DP_MCU` | In1→In2 | 60.800 | 44.100 |
| 24 | C40 | U10.21 | `/RF_GPIO0` | In2→B | 57.400 | 56.100 |
| 25 | C40 | U10.22 | `/RF_GPIO2` | In2→B | 58.000 | 58.100 |
| 26 | R10 | R10.2 | `/RP2354B MCU/USB_DP_MCU` | F→In1 | 56.530 | 37.100 |
| 27 | R10 | R10.2 | `/RP2354B MCU/USB_DP_MCU` | In1→In2 | 56.530 | 37.100 |
| 28 | R32 | R32.2 | `/GNSS_RX` | F→In1 | 126.950 | 13.100 |
| 29 | R32 | R32.2 | `/GNSS_RX` | In1→In2 | 126.950 | 13.100 |
| 30 | U21 | U21.4 | `/LSM_INT1` | F→In1 | 58.100 | 83.900 |
| 31 | U21 | U21.4 | `/LSM_INT1` | In1→In2 | 58.100 | 83.900 |
| 32 | C13 | U10.4 | `/LSM_INT1` | In1→In2 | 50.600 | 56.600 |
| 33 | FB1 | U10.4 | `/LSM_INT1` | In1→In2 | 51.500 | 49.000 |
| 34 | C38 | U10.18 | `/RF_MISO` | In2→B | 63.000 | 60.200 |
| 35 | C52 | U20.13 | `/SENS_SCLK` | In1→B * | 54.800 | 77.500 |
| 36 | R22 | U10.20 | `/RF_RESET_N` | In1→In2 | 53.950 | 86.400 |

`*` = one of the 7 declared-MICROVIA vias that span 3 copper layers (§1). The two `/PA_EN` rows sit
1.10 mm / 0.78 mm from U10's exposed pad and >1 mm from U10.25, which is why several of them have no
tight pad attachment — they are mid-fan-out layer changes, not pad escapes.

### Grouped by footprint (this is where they cluster)

| footprint | n | nets |
|---|---|---|
| **U10** | **15** | /3V3 · /GNSS_RX · /HGM · /LSM_INT1 ×2 · /PA_EN ×2 · /RF_GPIO0 · /RF_GPIO2 · /RF_MISO ×2 · /RF_MOSI ×2 · /RF_RESET_N · /SENS_SCLK |
| U40 | 4 | /915 MHz RF/VDD_CC112 · /RF_GPIO2 · /RF_MOSI ×2 |
| C12 | 2 | /GNSS_RX · /RF_SCLK |
| C32 | 2 | /RP2354B MCU/USB_DP_MCU |
| C40 | 2 | /RF_GPIO0 · /RF_GPIO2 |
| R10 | 2 | /RP2354B MCU/USB_DP_MCU |
| R32 | 2 | /GNSS_RX |
| U21 | 2 | /LSM_INT1 |
| C13 · C38 · C52 · FB1 · R22 | 1 each | /LSM_INT1 · /RF_MISO · /SENS_SCLK · /LSM_INT1 · /RF_RESET_N |

Nets by load: /LSM_INT1 6 · /GNSS_RX 4 · /RF_MOSI 4 · /RP2354B MCU/USB_DP_MCU 4 · /RF_GPIO2 3 ·
/RF_MISO 3 · /PA_EN 2 · /RF_GPIO0 2 · /RF_RESET_N 2 · /SENS_SCLK 2 · /3V3 1 · /915 MHz RF/VDD_CC112 1 ·
/HGM 1 · /RF_SCLK 1 = 36.

Only **4** are true via-in-pad (via centre exactly on a pad, d = 0.000): U40.4, U40.7 and R10.2 ×2.
32 of the 36 lie within 1.50 mm of the nearest pad of any footprint and the other 4 within 3.73 mm;
the largest *same-net* gap is R22's via at 32.60 mm from its own net's nearest pad — i.e. it is a
long net, not a local pad escape.

---

## 3. Free-rider test — the answer is zero, and here is the board-side proof

The owed respin's netlist delta is already recorded (`evidence/fab-da-respin/REPORT.md:310-320`):
U10 pads **43–48** → `/ESC_PWM7`, `/ESC_TELEM7`, `/ESC_FAULT7`, `/ESC_PWM6`, `/ESC_TELEM6`,
`/ESC_FAULT6` (the 7th actuator channel), plus *a servo rail net added across the servo header*.
A via on one of those nets is free, because the respin re-lays that copper regardless.

Tested directly on the 341-via board:

| scope net | present on board? | pads on net | vias on net (any type) |
|---|---|---|---|
| `unconnected-(U10-GPIO34-Pad43)` | yes — the 7th channel pin exists, unassigned | 1 | **0** |
| `unconnected-(U10-GPIO35-Pad44)` | yes | 1 | **0** |
| `unconnected-(U10-GPIO36-Pad45)` | yes | 1 | **0** |
| `unconnected-(U10-GPIO37-Pad46)` | yes | 1 | **0** |
| `unconnected-(U10-GPIO38-Pad47)` | yes | 1 | **0** |
| `unconnected-(U10-GPIO39-Pad48)` | yes | 1 | **0** |
| `/CAN_5V` (the servo rail's net) | yes | **2** — F1.1, J2.1 | **0** |
| `/ESC_PWM7`, `/ESC_TELEM7`, `/ESC_FAULT7`, `/ESC_*6` | **do not exist** | — | — |

Board-wide net-family scan: `ESC 0 · PWM 0 · TELEM 0 · FAULT 0 · SERVO 0` matches out of 175 nets.
The 7th channel and the servo rail are *schematic intent*, not copper — there is no copper on them
to free.

Intersection of the 36's nets with the respin scope = **∅**. **FREE = 0 of 36; unrelated = 36.**

### Why the servo rail cannot host any of the 36 on this board

This variant has **no servo header at all**: connector refs are `J1, J2, J10, J30, J40` — no
J60…J66. `/CAN_5V` reaches exactly two pads (F1.1, J2.1) and carries **zero vias of any type**. The
J60–J65 servo headers that `evidence/dec-servo-rail/REPORT.md:47-53` measured (pin 2 = `/CAN_5V`)
are on a **different variant** — `main_rev_b_final.kicad_pcb`, which has 136 vias and **0
non-through**. So the "servo rail" half of the respin scope is physically absent from the board that
carries the 36.

---

## 4. What this means for the budget

- **Free: 0.** The owed respin cannot absorb a single one of the 36. Clearing them is new work, not
  free-riding — the respin's netlist delta touches none of their 14 nets.
- **Costly: 36.** All are on preserved signal nets (/LSM_INT1, /GNSS_RX, /RF_MOSI, USB_DP_MCU, the
  RF control set), which any respin must keep.
- **Single largest cluster: U10 — 15 of 36 (41.7 %)**, all around the QFN-80 escape. Widen U10's
  bbox by 2.00 mm and **21 of 36** fall inside that band.
- One honest qualifier, because it is easy to misread the 0: those 15 U10 vias sit inside the fan-out
  band that a respin *would* re-lay anyway — but `evidence/fab-da-respin/REPORT.md:407-424` prices
  exactly that L/B rip-up (288 segments, 38 nets, 112.5 % over-subscribed rows) as **NOT free**, "the
  actual work". So the 15 are co-located with the respin, not free-riding on it.

---

## 5. Method, and two instrument traps worth banking

- Classification is **span-based** (`TopLayer`/`BottomLayer` vs F.Cu/B.Cu) throughout; drill is used
  only as an independent cross-check of the declared type, never as the classifier.
- **Trap 1 — `PCB_VIA::GetWidth()` with no layer argument raises a modal wx assert** in the
  KiCad 9.0.7 Windows build (`pcb_track.cpp(381)`). Headless, the census blocked on the dialog for
  11 minutes and looked like a slow board load. Use `GetWidth(pcbnew.F_Cu)`. Any "hung" pcbnew job on
  this host should be suspected of this first.
- **Trap 2 — `GetEnabledLayers().CuStack()` returns layer-ID order**, `[F.Cu, B.Cu, In1.Cu, In2.Cu]`,
  not stack order. Sorting by ID makes In2.Cu→B.Cu look like a 3-layer span. The layer *names* were
  right, the span-depth integer was not; fixed by ordering on F.Cu/In1/In2/B.Cu explicitly.
- **Cross-check against the earlier wave.** `evidence/fab-da-respin/REPORT.md:290-291` lists two
  `/PA_EN` non-through vias on U10.25 at (57.600, 52.200) F.Cu→In2 and (58.000, 51.900) In2→B. This
  census finds both, at those exact coordinates and those exact spans, from a different board file
  and an independently written script. The instrument reproduces a published row-level result, which
  is the check that the totals agreeing did not earn.
- Reproduce:
  `& 'C:/Program Files/KiCad/9.0/bin/python.exe' evidence/fab-da-census/combined.py work/work.kicad_pcb via_census.json tables.md progress.log`
  then `verify_scope.py` for §3.

| artefact | contents |
|---|---|
| `work/work.kicad_pcb`, `work/work.kicad_pro` | the board copy tested (repo untouched) |
| `combined.py` | census + attribution + footprint/net grouping (one board load) |
| `verify_scope.py` | §3: servo headers, /CAN_5V, U10 pads 43–48, auto-net vias, bbox |
| `via_census.json` | 341 vias, 36 non-through with per-via net/span/pad/nearest-pad |
| `tables.md` | the same tables, machine-generated |
| `scope_check.txt`, `progress.log`, `run.log` | raw instrument output |
| `scan_boards.py` | found which of the 13 main-board variants is the 341/36 board |
| `analyse.py`, `crosstab.py`, `dist.py`, `facts.py`, `netfams.py` | ad-hoc checks behind §1–§2 numbers |

**Scope note:** not attempted — the 7 declared-MICROVIA/3-layer-span conflicts are reported, not
adjudicated; no DRC run; no fix proposed for any of the 36.
