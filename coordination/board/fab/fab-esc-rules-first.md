# ESC rev_b — 4 oz rules installed BEFORE the route finishes

**Item:** `fab-esc-rules-first` — wave 2, specialist unit.
**Board of record:** `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb`
sha256 `992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD`
(re-measured this run; every copy used here is byte-identical — §9).
**Evidence:** `E:/engineering-portfolio-audit/evidence/fab-esc-rules-first/`
**Tooling:** KiCad 9.0.7 `kicad-cli pcb drc`, KiCad 9.0.7 `python.exe` + `pcbnew`,
CPython 3.12 for analysis. No repo was written to: `git status --porcelain` on
`repos/drone-arm` (`work/2026-11-11`) shows only the known stray `MEMORY.md`, which
this unit left alone.

---

## 0. The answers

| question | answer |
|---|---|
| How many rules in each `.kicad_dru`? | **9** in each — the previous wave's "11" was wrong, the verifier's "9" is right |
| DRC at 4 oz / 0.250 mm pattern | **523 violations**, 499 unconnected |
| DRC at 4 oz / 0.200 mm pattern | **102 violations**, 499 unconnected |
| Cost of the 0.200 mm decision | **−421 violations** (414 clearance + 4 track width + 3 zone neck) |
| DRC at 0.200 mm pattern **and** 0.150 mm ring | **16 violations**, all 16 are dangling vias — i.e. unrouted nets |
| Footprint-bound vs routing-fixable (0.250 set) | **383 footprint-bound · 35 routing-fixable · 105 parameter/dangling** — the brief's "371 / rest" split is close but the "43 copper = routing" part is **wrong**, see §4 |
| Is the remaining work purely routing? | **NO at 0.250 mm. YES, and only, at 0.200 mm + a 0.150 mm ring waiver** — §7 |

The single sentence: **at 0.250 mm the ESC is not a routing job, because 265 of its 2,777
unrouted pads sit in pad rows where a 0.250 mm track physically cannot be connected at
0.250 mm clearance; at 0.200 mm the same escapes fit with 0.05 mm to spare and the entire
remaining delta is 16 dangling vias, which are the route itself.**

---

## 1. The two rule files

| | variant-025 | variant-020 |
|---|---|---|
| path | `variant-025/esc_rev_b.kicad_dru` | `variant-020/esc_rev_b.kicad_dru` |
| install as | `hardware/esc/rev_b/esc_rev_b.kicad_dru` | same |
| **rules** | **9** | **9** |
| sha256 | `641AF0C597C1A20F4C532F2E70FB78CA9748B72FF1F8EE0D3E63ABFAD026517A` | `0CC8EF1688F2BF4EF38A03D071D963D3560EB1135B04B8A491B2ED10B10E0251` |
| patch | `patches/install-variant-025.patch` | `patches/install-variant-020.patch` |
| pattern (track/clearance/pad gap/zone neck) | **0.250 mm** | **0.200 mm** |
| **annular ring (via and PTH pad)** | **0.200 mm** | **0.200 mm** (held — see §2.3) |
| **zone neck (connection width)** | **0.250 mm** | **0.200 mm** |
| via drill / via diameter | 0.300 / 0.700 mm | 0.300 / 0.700 mm |
| PTH drill / copper-edge | 0.200 / 0.500 mm | 0.200 / 0.500 mm |

Rule count, reproducible:

```
PS> (Select-String -Path variant-025\esc_rev_b.kicad_dru -Pattern '^\(rule ').Count   -> 9
PS> (Select-String -Path variant-020\esc_rev_b.kicad_dru -Pattern '^\(rule ').Count   -> 9
```

Both patches pass `git apply --check` against the real repo without writing anything:

```
PS> git -C repos/drone-arm apply --check --verbose evidence\...\patches\install-variant-025.patch
Checking patch hardware/esc/rev_b/esc_rev_b.kicad_dru...        (exit 0)
```

The two files differ in **exactly three values** and nothing else, so the DRC delta in §3
is attributable to the 0.200/0.250 decision alone. That is the whole point of doing this
before the route is finished.

A third file, `sensitivity-020-ring015/esc_rev_b.kicad_dru` (9 rules, sha256
`D80CAC9B…2712DE9`), is **not a deliverable**. It exists to price the *second* parameter the
class scheme ties to the first (§2.3, §3.2).

---

## 2. Where every number comes from

### 2.1 The pattern values

Primary source: Eurocircuits "PCB Design Classification Overview", `eC-classification
Table - 07/05/2024`, downloaded during the previous wave to
`../fab-esc-4oz/sources/EC-classification-ENGLISH-5-2024-V3.png`
(sha256 `47c81c3d…962080`), re-read this run. The `Base Cu OL` min-pattern block reads:

| Base Cu OL | OTT-OTP-OPP | OTW |
|---|---|---|
| 35 µm 1 oz | 0.125 | 0.125 |
| 70 µm 2 oz | 0.200 | 0.200 |
| 105 µm 3 oz | 0.250 | 0.250 |

`OPP` is pad-to-pad, and the page states *"The smallest of these values determines the
pattern class."* **0.200 mm appears in that column only at 70 µm.** 0.250 mm is the last
published step; 4 oz (140 µm) is not in the table at all. So:

- **variant-025 = 0.250 mm** = the last published step, an extrapolation in the *safe*
  direction only. Still not a measured 4 oz capability (§8, O1).
- **variant-020 = 0.200 mm** = an extrapolation *downward*, which the same page's own rule
  forbids: *"Thicker copper needs a wider isolation for reliable etching."* It is legal only
  if a named fab writes it down. **Status: UNVERIFIED — that is what variant-020 is for.**

### 2.2 The zone-neck value

Same class number as the pattern: the copper neck between a pad and its zone is etched
through the same resist, so it carries `OTW`. 0.250 mm in variant-025, 0.200 mm in
variant-020. Measured population that this rule touches: `board_state.json` →
`zone_min_thickness_hist_mm = {0.20: 90, 0.25: 6}`, i.e. **90 of 96 zones are filled at a
0.20 mm minimum thickness parameter**. Under variant-025 that parameter is illegal; the
DRC counts only **3** actual sub-0.250 necks today (§3.1) because the polygons were filled
at 0.20. A refill at 0.25 exposes more — the previous wave measured 42 after refilling
(`../fab-esc-4oz/kicad_fixed/drc_4oz_after.json`), **inherited, not re-measured here** (§8).

### 2.3 The annular ring value

**0.200 mm in both variants.** Three independent anchors:

1. **Published row, matching the pattern class.** The same Eurocircuits image, `Pattern
   Class` block: class 3 = `OTW 0.250 / OTT-OTP-OPP 0.250 / OAR 0.200`; class 4 =
   `0.200 / 0.200 / 0.150`. `OAR` is defined on the page as *"smallest OAR (Outer layer
   Annular Ring = 1/2 (Outer layer pad diameter - TOOLSIZE))"*. So the ring that belongs
   with a 0.250 mm pattern class **is 0.200 mm**, and the ring that belongs with a
   0.200 mm class is 0.150 mm. This is a read-off row, not an assumption.
2. **Fab floor.** PCBWay, `https://www.pcbway.com/capabilities.html` (fetched in the
   previous wave, recorded verbatim in `../fab-esc-4oz/sources/SOURCES.md`): *"Min Width of
   Annular Ring 0.15mm(6mil) — For pads with vias in the middle…"*. 0.200 mm is 1.33× that
   blanket 1 oz floor, which is the right direction for 140 µm plating and etch spread.
3. **Derivation of the via diameter**, not a citation: 0.300 drill + 2 × 0.200 = 0.700 mm.

**Why variant-020 does not also relax the ring.** In the class scheme the two move
together, but bundling both into one file destroys the measurement: the 0.200 decision
would then be credited with violations the ring relieved. The ring relief is therefore
measured separately in `sensitivity-020-ring015/` and reported as its own number (§3.2).
If the fab grants 0.200 mm pattern, **ask for 0.150 mm ring in the same sentence** — that
single addition is worth 86 violations.

### 2.4 The two values that are not sourced

- **copper-to-edge 0.500 mm** — ANALYTICAL (rout burr vs a 140 µm foil). No fab publishes
  it. It drives **0** violations in all three runs, so it changes nothing either way.
- **PTH drill 0.200 mm** — follows the owner rule (standard PTH 0.2–0.3 mm, no HDI) and the
  board's own minimum: `board_state.json` → `pth_pad_drill_hist_mm` has **110 pads at
  0.20 mm**. PCBWay's CNC floor is 0.15 mm. The rule is set at the real process floor on
  purpose: tightening it to 0.30 mm was measured in the previous wave to abort 48
  neighbouring pads — 48 new violations to fix 110 cosmetic ones.

---

## 3. DRC: two variants, one board, plus the baseline

Command, identical except for the `.kicad_dru` beside the copy:

```powershell
$cli = "C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"
& $cli pcb drc "$ev\variant-025\esc_rev_b.kicad_pcb" -o "$ev\variant-025\drc.json" --format json --severity-all --units mm
```

### 3.1 Headline

| run | rules in force | **violations** | errors | warnings | unconnected |
|---|---|---|---|---|---|
| **variant-025** | pattern 0.250 / ring 0.200 / neck 0.250 | **523** | 504 | 19 | 499 |
| **variant-020** | pattern 0.200 / ring 0.200 / neck 0.200 | **102** | 86 | 16 | 499 |
| sensitivity-020-ring015 | pattern 0.200 / ring 0.150 / neck 0.200 | **16** | 0 | 16 | 499 |
| baseline (project rules only, previous wave) | 0.20 / 0.10 ring | 16 | 0 | 16 | 499 |

`variant-025` reproduces the previous wave's **523 / 499 exactly** — an independent chain
check that this run is measuring the same board under the same rule semantics.

### 3.2 Violations by type

`analysis.json` in each variant directory.

| type | severity | variant-025 | variant-020 | sensitivity |
|---|---|---|---|---|
| `clearance` | error | **414** | 0 | 0 |
| `annular_width` | error | 70 | 70 | 0 |
| `via_diameter` | error | 16 | 16 | 0 |
| `track_width` | error | 4 | 0 | 0 |
| `connection_width` | warning | 3 | 0 | 0 |
| `via_dangling` | warning | 16 | 16 | **16** |
| **total** | | **523** | **102** | **16** |

### 3.3 The cost of the 0.200 mm decision — stated explicitly

**523 − 102 = 421 violations.** Broken down by the rule each one trips:

| change | violations removed by going 0.250 → 0.200 | of which |
|---|---|---|
| `clearance` 0.250 → 0.200 | **414** | 371 pad↔pad @ **0.2000** exactly · 12 pad↔track @ 0.2250 · 24 track↔track @ 0.2434–0.2478 · 7 pad↔track @ 0.2000/0.2462 |
| `track_width` 0.250 → 0.200 | **4** | `/3V3`, `/Auxiliary power/LM_FB`, `LM2_FB`, `LM_RON`, 0.200 mm × 5.79 mm |
| `connection_width` 0.250 → 0.200 | **3** | necks at 0.2217 / 0.2049 / 0.2000 mm (U701 pads 4, 5; R712 pad 1) |
| **total** | **421** | **88 % of it (371/421) is one geometric fact: 0.2000 mm pad gaps** |

Second decision, priced separately: **102 − 16 = 86** violations are *not* pattern-driven.
They are ring/diameter only — 28 vias (ring 0.150 × 16, 0.175 × 12) + 42 PTH pads (30 =
J1103–J1603 `PinHeader_1x05_P1.27mm` at ring 0.175, 12 = U701/U703 thermal-via pads) + 16
vias at 0.600 mm diameter. At a class-4 ring of 0.150 mm **all 86 disappear** and the board
is left with 16 dangling vias.

### 3.4 Is the `.kicad_dru` actually in force? Yes — two independent proofs

1. **The rule name is in the DRC text.** 487 of the 523 descriptions cite a rule from the
   file being tested, e.g. `(rule '4oz-025 clearance 0.25mm min' …)`. `rules_hit` in
   `variant-025/analysis.json` = 414 / 42 / 28 / 3, and in `variant-020/analysis.json` the
   names are the `4oz-020 …` set. Renaming the file's rules renames the DRC output.
2. **The reported minimum follows the file, not the project.** `via_diameter` reports
   *"board setup constraints min diameter 0.7000 mm"* — the project's own value is
   **0.6** (`variant-025/esc_rev_b.kicad_pro:135` `"min_via_diameter": 0.6`), so the
   printed 0.7000 can only come from the `.kicad_dru`. Same for `track_width`, which
   prints *"min width 0.2500 mm"* against `:133 "min_track_width": 0.2`. The 4
   track-width errors exist only in variant-025; they vanish in variant-020 **because the
   file changed**, which is only possible if the file is being read. (Project values, for
   the record: clearance 0.2 `:120`, track 0.2 `:133`, via ring 0.1 `:134`, via diameter
   0.6 `:135`, PTH drill 0.2 `:132`.)

---

## 4. Routing-fixable vs footprint-bound — the brief's split, corrected

Measured on `variant-025/drc.json` (the strict set — the only one where these classes are
distinguishable). 523 violations, every one classified:

| bucket | count | what it is |
|---|---|---|
| **FOOTPRINT-BOUND — pad↔pad** | **371** | all 371 are **exactly 0.2000 mm** and all 371 are **inside a single footprint** (measured: `same_footprint: 371, cross_footprint: 0`) |
| **FOOTPRINT-BOUND — escape-forced** | **12** | pad↔track at **0.2250 mm**, all pad 14/16 of an LQFP-48 P0.5 — **this is the geometric maximum**, see the proof below |
| ROUTING-FIXABLE — bus spacing | 24 | track↔track at 0.2434 (9) / 0.2478 (15), on `M*_DRV_SCLK` vs `M*_DRV_SDI`: 2.2–6.6 µm short |
| ROUTING-FIXABLE — track width | 4 | 0.200 → 0.250 mm on `/3V3`, `LM_FB`, `LM2_FB`, `LM_RON` |
| ROUTING-FIXABLE — *undetermined* | 7 | pad↔track at 0.2462 (6, pad 30 of U1101–U1601 WQFN-40) and 0.2000 (1, U201 pad 67). Geometry differs from the 0.2250 family; **UNVERIFIED** which class |
| OBJECT-PARAMETER | 86 | 28 via ring + 42 PTH pad ring + 16 via diameter — resize/re-place, not a route, not a footprint |
| ZONE-PARAMETER | 3 | connection width 0.2000–0.2217 mm |
| DANGLING (warning) | 16 | 8 nets × 2 vias, placed but never tracked |
| **total** | **523** | |

Under the brief's two-way framing: **383 footprint-bound (73.2 %) · 35 routing-fixable
(6.7 %) · 105 neither (20.1 %)**.

### 4.1 The proof that the 12 at 0.2250 mm are forced, not sloppy

A track of width `w` connected to a pad in a row of pitch `p` and pad edge `a` (measured
perpendicular to the row) can never do better than

```
max_clearance = p - a/2 - w/2
```

because the track must touch its own pad and its nearest legal position is centred on that
pad. LQFP-48 `7x7mm_P0.5mm`: `p = 0.500`, `a = 0.300`, `w = 0.250` → **0.500 − 0.150 −
0.125 = 0.2250 mm**. DRC measures **0.2250 mm**, to four decimal places, twelve times.

So at 0.250 mm track / 0.250 mm clearance, **no legal connection to any pad in a
0.5 mm-pitch / 0.30 mm-pad row exists.** Not "hard" — arithmetically impossible. The same
formula for U201 `QFN-80-1EP_10x10mm_P0.4mm` (`p = 0.400`, `a = 0.200`) gives
**0.175 mm** — 75 µm short, worse. At 0.200 mm track: LQFP gives **0.250 mm** (legal, 0.05
margin) and QFN-80 gives **0.200 mm** (legal, zero margin).

`measure_all_gaps.py` → `all_gaps.json` scans all 77 footprints that have a pad row of ≥ 6
same-sized pads: **exactly 9 fall below a 0.250 mm gap**, and they are the same 9 the DRC
names. No tenth footprint exists.

### 4.2 What this corrects in the previous wave

- **"43 copper clearance violations … 49 distinct segments need re-spacing"** — the 43 is
  right, but only **24** are re-spacing. **12 are at the geometric maximum** and **7 are
  undetermined**. Re-spacing all 43 would fix 24 and fail 12 by construction.
- **"the 62 copper objects, 28 vias, 49 bus segments and 90 zones are not
  footprint-bound"** — those are *object* counts, and they do not map 1:1 to violations:
  28 vias → 28 of the 70 annular; 90 zones → only **3** actual necks (90 is a *parameter
  census*, `zone_min_thickness_hist_mm`); 49 bus segments → 24 track↔track.
- **"371 pad gaps are the blocker; the other 43 are movable"** — corrected to **383
  unmovable** (371 + 12) and **35 movable**.

---

## 5. The 9 footprints, named, with pitch

`fine_pitch.json` (pad row only — the exposed/shield pads are excluded because they fake a
smaller pitch; that bug was caught and fixed mid-run: U201 first reported 0.13 mm).

| ref | footprint | pad (mm) | pitch (mm) | pad gap (mm) | pad↔pad violations | **max clearance for a 0.25 track** |
|---|---|---|---|---|---|---|
| **U201** | `QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm` | 0.200 × 0.800 | **0.400** | 0.200 | **75** | **0.175** ✗ |
| **U1102** | `LQFP-48_7x7mm_P0.5mm` | 0.300 × 1.475 | **0.500** | 0.200 | 43 | 0.225 ✗ |
| **U1202** | `LQFP-48_7x7mm_P0.5mm` | 0.300 × 1.475 | **0.500** | 0.200 | 43 | 0.225 ✗ |
| **U1302** | `LQFP-48_7x7mm_P0.5mm` | 0.300 × 1.475 | **0.500** | 0.200 | 43 | 0.225 ✗ |
| **U1402** | `LQFP-48_7x7mm_P0.5mm` | 0.300 × 1.475 | **0.500** | 0.200 | 43 | 0.225 ✗ |
| **U1502** | `LQFP-48_7x7mm_P0.5mm` | 0.300 × 1.475 | **0.500** | 0.200 | 43 | 0.225 ✗ |
| **U1602** | `LQFP-48_7x7mm_P0.5mm` | 0.300 × 1.475 | **0.500** | 0.200 | 43 | 0.225 ✗ |
| **J202** | `USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal` | 0.600 × 1.150 | **0.800** | 0.200 | 19 | 0.375 ✓ |
| **J203** | `USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal` | 0.600 × 1.150 | **0.800** | 0.200 | 19 | 0.375 ✓ |
| | | | | **371** | | |

Seven of the nine are hard fails for *routing*, two (`J202`, `J203`) are hard fails only for
the *pad gap*. The distinction matters: the USB-C pads can be escaped, the LQFP and QFN
pads cannot.

**A DRC-invisible companion fact.** `U1101–U1601` are `WQFN-40-EP_6x6_P0.5` with
**0.220 mm** pads on 0.5 mm pitch. Their gap is 0.280 mm, so they pass the clearance rule
and do not appear in the 371 — but a 0.220 mm copper feature is still below the 0.250 mm
class-3 pattern. `track_width` constraints do not check pads, so **"0 violations" would not
mean "class 3 compliant"**. Flagged, not counted (§8).

---

## 6. Routing brief — the rules the remaining 540 nets must follow

### 6.1 The state being routed into (`nets.json`, `board_state.json`, both measured)

| quantity | measured | note |
|---|---|---|
| 4 layers, 687 footprints, 3,454 pads, 667 nets | yes | F.Cu / In1 / In2 / B.Cu |
| nets with ≥ 2 pads | **556** | 110 further nets have exactly 1 pad and need no copper |
| nets carrying a track | **16 → 2.88 %** | confirms the brief |
| nets with ≥ 2 pads and no track | **540** | confirms the brief |
| pads on those 540 nets | **2,777** | the actual routing workload |
| segments / total length | **154 / 628.273 mm** | F.Cu 569.473, In2 58.8 |
| segment widths | 0.25 × 150, **0.20 × 4** | the 4 track-width errors |
| vias | **1,990** | drill 0.40 × 1962, 0.30 × 16, 0.35 × 12; ring 0.20 × 1962, 0.15 × 16, 0.175 × 12 |
| vias on nets with no track at all | **1,978 of 1,990** | 99.4 % |
| zones / fill parameter | 96 zones, min thickness 0.20 × 90, 0.25 × 6 | refill needed at 0.25 |
| pads on the 540 nets sitting in the 9 fine-pitch footprints | **301** | U201 37, 6 × LQFP 38 each, J202/J203 18 each |
| **of those, pads with no legal 0.25 escape** | **265** | U201 37 + 6 × 38 |

### 6.2 The rules, per variant

**If the fab grants 0.200 mm (variant-020 in force):**

1. track width **≥ 0.200 mm** everywhere. Nothing forces the 154 existing 0.250 mm
   segments to narrow; 0.250 remains legal and is what the six motor power blocks are
   already drawn at.
2. clearance **≥ 0.200 mm** to every other net, all layers.
3. **the fine-pitch escapes now fit**: a 0.200 mm track leaving an LQFP-48 P0.5 pad centred
   has 0.250 mm to the neighbour (0.05 mm margin); from a QFN-80 P0.4 pad it has
   **0.200 mm — exactly the rule, zero margin**. Route these escapes dead straight,
   radially, one per pad; do not jog them, there is no budget.
4. via: drill **≥ 0.300 mm**, diameter **≥ 0.700 mm**, ring **≥ 0.200 mm** — or ≥ 0.600 mm
   diameter if and only if the 0.150 mm ring waiver is granted (§3.3).
5. zone necks ≥ 0.200 mm: set every zone `min_thickness` to 0.200 (90 are already) and
   refill at the end, once.
6. no microvia, no blind/buried. Every via must be a standard PTH.
7. copper to edge ≥ 0.500 mm.

**If the fab grants only 0.250 mm (variant-025 in force):** rules 1–3 become 0.250, and
**rule 3 is unsatisfiable for 265 pads**. Stop and take the decision in §7 — do not route.

### 6.3 The exceptions a fab would have to accept in writing

This is the letter, per §1/§5 of the previous wave's §6 step 2, now with the corrected
population and the seven-vs-two split:

> 4-layer FR-4, 4 oz (140 µm) outer copper, standard PTH only, no HDI. Please confirm **in
> writing** that you can build, at 140 µm final outer copper:
>
> 1. **0.200 mm pad-to-pad pattern** in nine footprints — `QFN-80-1EP_10x10mm_P0.4mm`
>    (U201, 0.400 mm pitch, 75 gaps), six × `LQFP-48_7x7mm_P0.5mm` (U1102–U1602, 0.500 mm
>    pitch, 43 gaps each = 258), two × `USB_C_Receptacle_GCT_USB4105-16P` (J202/J203,
>    0.800 mm pitch, 19 gaps each = 38). **371 gaps, all exactly 0.2000 mm.**
> 2. **A 0.250 mm track connected to those pads will sit 0.2250 mm from the adjacent pad**
>    (LQFP) and **0.1750 mm** (QFN-80) — that is the geometric maximum, not a
>    drawing error. Either accept 0.2250/0.1750 mm pad-to-track on 265 pads, or accept
>    0.200 mm track width on the escapes from those 265 pads.
> 3. **0.150 mm outer annular ring** on 28 vias and 42 PTH pads (0.150/0.175 mm as drawn,
>    0.200 mm is the class-3 value).
> 4. **0.600 mm via diameter** on 16 vias (0.300 mm drill + 2 × 0.150 ring).
> 5. **0.200 mm drill** in 110 thermal-via pads inside exposed pads (0.65 mm drill on the
>    30 J1103–J1603 header pads).
> 6. **0.200 mm copper necks** at three pad-to-zone connections (0.2000–0.2217 mm measured).
>
> Items 1 and 2 are the ones that cannot be fixed by routing. **Items 3–5 are worth 86
> violations on their own** and cost nothing to ask for in the same paragraph.

If the answer to items 1–2 is **no**, the board is not a routing job and the §7 decision
applies.

---

## 7. Is the ESC's remaining work purely routing?

**NO — not with the rules installed as they must be at 0.250 mm.** And the reason is not
the 371 static pad gaps, which were already known; it is that the *remaining* route cannot
be drawn:

- **265 pads on the 540 unrouted nets sit in pad rows where a 0.250 mm track cannot be
  connected at 0.250 mm clearance.** The arithmetic is in §4.1 and it is not a matter of
  care: 0.2250 mm is the *maximum*, twelve violations are measured at exactly that value,
  and the required number is 0.250. U201 is worse at 0.175.
- So under variant-025, finishing the route would **add** violations at 265 pads rather
  than clear the board. The board would go from 523 to 523 + (≥265 new escapes minus the
  ones that never get drawn). That is the respin this programme exists to avoid.

**It becomes purely routing under exactly one condition:** a fab accepts 0.200 mm pattern
**and** 0.150 mm ring at 140 µm outer copper. Then:

| after the waiver | remaining violations | what they are |
|---|---|---|
| `sensitivity-020-ring015` DRC, measured | **16** | 16 `via_dangling` warnings on 8 nets (`CAN_SCK`, `STATUS_LED`, `M1..M6_STATUS_LED`) — vias with no track |
| unconnected items | 499 | the route itself |

Those 16 dangling vias are not defects; they are vias placed for tracks that have not been
drawn. **Draw the 540 nets and they disappear.** At that point the ESC's remaining work is
one activity: routing. No copper needs to move, no package needs to change, no zone
parameter needs a decision.

**If the waiver is refused**, the board is **not** a routing job. It is either a 2 oz board
(the geometry is already 2 oz-compliant — the previous wave's run B: 16 violations,
all dangling) or a **7-package** change: U201 QFN-80 P0.4 **plus all six LQFP-48** — not the
3 packages the board currently lists, because the LQFPs, not the USB-C connectors, are what
block the routing.

### 7.1 The actionable recommendation

1. **Install `variant-020`'s rules file today**, and dispatch the waiver letter in §6.3
   today. Routing must not start before the pattern class is settled; it is the only free
   moment.
2. If the fab's answer is 0.200 mm: route at 0.200 with the escape rules in §6.2.
3. If the answer is 0.250 mm: **do not route.** Take 2 oz vs 7 packages to the owner with
   §4.1 in hand. Under 4 oz/0.250 the design is unbuildable with these packages at any
   routing quality, and that is a one-paragraph decision, not a redesign.
4. `variant-025` stays in the tree as the strict set. Run it again after routing to prove
   the result, whichever variant was used to route.

---

## 8. Corrections this unit puts on the record

| # | previous statement | corrected | evidence |
|---|---|---|---|
| **BOARD CORRECTION 1** | the 4 oz `.kicad_dru` "contains 11 rules" | **9** | `Select-String '^\(rule '` → 9 in both new files and in the previous wave's file |
| **BOARD CORRECTION 2** | "43 copper clearance violations … 49 bus segments need re-spacing" | **24** are re-spacing, **12** are at the geometric maximum (0.2250), **7** undetermined | §4.1, `variant-025/drc.json` |
| **BOARD CORRECTION 3** | "the other 43 are movable by routing" | **383** violations are footprint-bound (371 + 12), not 371 | §4 |
| **BOARD CORRECTION 4** | "90 zone[s]" as violations | 90 is a **parameter census**; the DRC finds **3** actual necks at 0.250 | `board_state.json`, `variant-025/drc.json` |
| **BOARD CORRECTION 5** | blocker 5: "change 3 packages (U201, J202, J203)" | if 0.200 mm is refused it is **7 packages** (U201 + six LQFP-48); the USB-C parts block the *pad gap*, not the *routing*, and the LQFPs block routing | §4.1, §5 |

### Open / UNVERIFIED

| id | question |
|---|---|
| **O1** | **Is 0.200 mm available at 140 µm outer copper?** Not answered here and not resourced. The sibling capability unit owns it; variant-020 exists so its answer can be dropped in with no rework. |
| **O2** | **Is 0.150 mm outer annular ring available at 4 oz?** Same class of extrapolation. Worth 86 violations (§3.3). |
| **O3** | **Zone necks after a 0.250 refill.** Measured 3 now; the previous wave measured **42** after refilling at 0.250 (`../fab-esc-4oz/kicad_fixed/`). Inherited, not re-measured — the fill must be redone once the route exists anyway. |
| **O4** | **The 7 undetermined clearance violations** (6 at 0.2462 on pad 30 of WQFN-40, 1 at 0.2000 on U201 pad 67). Class not proven; 1.3 % of 523 either way. |
| **O5** | **Pad width vs pattern class.** `U1101–U1601` carry 0.220 mm pads, below 0.250; no DRC constraint checks pad width, so a clean clearance result would not prove class-3 compliance. |
| **O6** | **Assembly at 4 oz** — paste volume and heel fillet on 0.200/0.400 pitch pads at 140 µm. Not analysed; could be a second, independent objection. |

---

## 9. Artefacts and reproduction

| file | what |
|---|---|
| `variant-025/esc_rev_b.kicad_dru` | **deliverable** — 4 oz, pattern 0.250, ring 0.200, neck 0.250 (9 rules) |
| `variant-020/esc_rev_b.kicad_dru` | **deliverable** — 4 oz, pattern 0.200, ring 0.200, neck 0.200 (9 rules) |
| `sensitivity-020-ring015/esc_rev_b.kicad_dru` | not a deliverable — pattern 0.200 + ring 0.150 (9 rules) |
| `patches/install-variant-0{25,20}.patch` | `git apply`-checked patches that add the file at `hardware/esc/rev_b/esc_rev_b.kicad_dru` |
| `variant-*/*.kicad_pcb`, `.kicad_pro` | byte-identical board copies (sha256 verified each) |
| `variant-*/drc.json`, `analysis.json` | DRC + classification per variant |
| `board_state.json` | segments, vias, zones, drills, rings, nets |
| `nets.json` | 556 / 16 / 540 census, unrouted-pad distribution |
| `fine_pitch.json` | the 9 footprints, pitch, gap, max escape clearance |
| `all_gaps.json` | every footprint scanned; exactly 9 below 0.250 mm |
| `measure_board.py`, `measure_nets.py`, `measure_fine_pitch.py`, `measure_all_gaps.py`, `analyse_drc.py` | the measurements |

```powershell
$cli="C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"; $kpy="C:\Program Files\KiCad\9.0\bin\python.exe"
$ev="E:\engineering-portfolio-audit\evidence\fab-esc-rules-first"
foreach($v in "variant-025","variant-020","sensitivity-020-ring015"){
  & $cli pcb drc "$ev\$v\esc_rev_b.kicad_pcb" -o "$ev\$v\drc.json" --format json --severity-all --units mm
}
& $kpy "$ev\measure_board.py"      "$ev\variant-025\esc_rev_b.kicad_pcb" "$ev\board_state.json"
& $kpy "$ev\measure_nets.py"       "$ev\variant-025\esc_rev_b.kicad_pcb" "$ev\nets.json"
& $kpy "$ev\measure_fine_pitch.py" "$ev\variant-025\esc_rev_b.kicad_pcb" "$ev\fine_pitch.json" 0.25
& $kpy "$ev\measure_all_gaps.py"   "$ev\variant-025\esc_rev_b.kicad_pcb" "$ev\all_gaps.json" 0.25 0.25
python "$ev\analyse_drc.py" "$ev\variant-025\drc.json" variant-025 "$ev\variant-025\analysis.json"
```

Nothing was written to `repos/drone-arm`. The board and project were copied out; the rules
files live in this directory; the patches were validated with `git apply --check`, which
writes nothing. The stray untracked `MEMORY.md` in `repos/drone-arm` was left exactly as
found.

**Trap worth recording for the next run:** `PCB_VIA.GetWidth()` with no layer argument
asserts in KiCad 9's Python and pops a modal dialog, which hangs a headless measurement
silently. Pass the layer — `v.GetWidth(pcbnew.F_Cu)`.