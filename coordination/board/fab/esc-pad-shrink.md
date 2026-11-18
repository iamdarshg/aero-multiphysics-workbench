# ESC pad-to-pad 0.200 mm shrink study — wave 12

**Status:** COMPLETE — steps 1–4 done.

ONE QUESTION: can the ESC's 371 pad-to-pad gaps at exactly 0.200 mm be cleared by
SHRINKING the pads to 0.150 mm, keeping the same parts — and if so, is the result
still solderable?

Input board: `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb` (4,988,844 B,
sha256 992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD after copy).
All work on a COPY under `evidence/esc-pad-shrink/runs/`. Repo untouched.
Host: KiCad 9.0.7, kicad-cli 9.0.7, pcbnew 9.0.7.

Prior work reused: `evidence/esc-footprint-fix/{pairs_parsed.json, footprints_probe.json,
parse_rows.py, probe_footprints.py, rings_and_parts.py, probe_usbc.py, probe_pad41.py}`.
The board was **not** re-parsed for the gap census — `pairs_parsed.json` was read as-is.

---

## 0. Method / provenance

- Gap rows: `pairs_parsed.json` (prior wave) → 371 rows, **all** `actual == 0.2000`,
  **all** `intra == True` (same footprint), **all** `same_net == False`.
- Pad geometry per type: from the same file (w/h/x/y per pad) and cross-checked
  against the installed KiCad 9.0.7 land patterns via `pcbnew.FootprintLoad`.
- DRC: `kicad-cli pcb drc --format json --severity-all` against a copy, with the
  prior wave's own rule file `esc_rev_b.kicad_dru` (4 oz / 0.25 mm variant "025",
  9 rules) installed beside the board so it is picked up by basename.
- **Baseline validated before use:** my run reproduces the settled figure exactly —
  `Found 523 violations` (523 rows, 523 unique keys; 504 error / 19 warning).
  Instrument check: 414 clearance + 70 annular_width + 16 via_diameter + 16
  via_dangling + 4 track_width + 3 connection_width = 523. ✔
- Provenance labels: **local tool run** = kicad-cli/pcbnew output on this host;
  **datasheet/standard** = vendor document; **analytical** = arithmetic on the above.

## 1. The 371 gaps grouped by footprint type

| # | Footprint type | Parts (refs) | footprint instances | pads | gaps | pitch | pad (across pitch) | gap |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| A | QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm | U201 = **RP2354B** (RP2350B) | 1 | 90 | **75** | 0.400 | 0.200 | 0.200 |
| B | LQFP-48_7x7mm_P0.5mm | U1102/1202/1302/1402/1502/1602 = **STM32G431CBT6** | 6 | 288 | **258** | 0.500 | 0.300 | 0.200 |
| C | USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal | J202 (CTRL_USB_C), J203 (MOTOR_DFU_USB_C) | 2 | 44 | **38** | 0.500 / 0.650 / 0.800 | 0.300 / 0.600 / 0.600 | 0.200 |

- **3 distinct footprint types, 9 footprint instances, 422 pads, 371 gaps**
  (75 + 258 + 38 = 371 ✔).
- Family C is not one pitch: 14 gaps at 0.500 (0.300↔0.300), 8 at 0.650
  (0.600↔0.300), 16 at 0.800 (0.600↔0.600). 14+8+16 = 38 ✔.
- Cross-check against the clearance DRC type: 414 clearance rows, of which 372
  report `actual 0.2000`. The 372nd is a **pad-to-track** row, not pad-to-pad;
  the pad↔pad 0.200 subset is exactly the 371 above. The remaining 42 clearance
  rows are 0.225/0.2434/0.2462/0.2478, i.e. not at 0.200 and not in scope.

## 2. Pad width that yields a 0.250 mm gap

`w = pitch − 0.250`, both pads shrunk equally:

| Type | pitch | current w | **required w** | shrink | gap if w = 0.150 |
|---|---:|---:|---:|---:|---:|
| A QFN-80 | 0.400 | 0.200 | **0.150** | −0.050 (−25 %) | 0.250 |
| B LQFP-48 | 0.500 | 0.300 | **0.250** | −0.050 (−17 %) | 0.350 (over-shrunk) |
| C USB-C @0.500 | 0.500 | 0.300 | **0.250** | −0.050 | 0.350 |
| C USB-C @0.650 | 0.650 | 0.600+0.300 | **0.400 each** (or 0.500+0.300) | 0.600→0.400 | 0.500 |
| C USB-C @0.800 | 0.800 | 0.600 | **0.550** | 0.600→0.550 | 0.650 |

**The 0.150 mm number is only right for type A.** At 0.5 mm pitch a 0.150 mm pad
gives 0.350 mm — three types cannot be treated with one width, and 0.150 is
arithmetically the wrong shrink for B and C.

## 3. SOLDERABILITY CHECK (decisive)

First, the load-bearing observation: **the board's pads are pad-for-pad identical to
the land patterns shipped with KiCad 9.0.7** — not an over-padded variant. Verified by
loading each `.kicad_mod` with pcbnew and comparing:

| Type | installed land pattern pad | board pad | identical? |
|---|---|---|---|
| A | 0.800 × 0.200 (40) + 0.200 × 0.800 (40) | 0.800 × 0.200 / 0.200 × 0.800 | **yes** |
| B | 0.300 × 1.475 (48) | 0.300 × 1.475 | **yes** |
| C | 0.300×1.15 (8), 0.600×1.15 (8), … | same | **yes** |

So the 0.200 mm gap is not a stuffing error to be patched — it *is* the standard
land pattern at these pitches. The shrink therefore moves the footprint off-pattern,
and the question becomes how far off-pattern is still solderable.

Land-pattern floor used: IPC-7351B derives pad width as `W(component terminal,
max) + 2·Js` with side fillet `Js ≥ 0`, so **pad width may never be narrower than
the terminal/lead it must wet**
([IPC-7351B pad-width formula: pad width = W(max) + 2·Js](https://www.rantle.com/pcb-pad-size-calculator/)).
That floor is validated against the shipped library: every installed pattern meets
it (A: 0.200 pad vs 0.200 nominal terminal; B: 0.300 vs 0.220 nominal lead; C: 0.300
vs 0.300 contact), so the instrument does not condemn the standard footprints.

| Type | Part | terminal / lead width | required w | verdict |
|---|---|---|---:|---|
| A QFN-80 P0.4 | RP2354B (RP2350B, [datasheet](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf)) | 0.200 nom (no-lead, `ipc_noLead_generator`) | 0.150 | **0.150 < 0.200 → NOT a candidate.** The pad would be 0.025 mm narrower than the terminal on each side: no side fillet, and 0.150 mm is below the 0.250 mm minimum pattern in the very 4 oz rule set used to count these violations (Eurocircuits table in `.dru` stops at 105 µm copper / 0.250 mm pattern). Not manufacturable at 4 oz, let alone solderable. |
| B LQFP-48 P0.5 | STM32G431CBT6 (JEDEC MS-026 BBC) | 0.220 nom / 0.270 max lead | 0.250 | **0.250 > 0.220 → candidate, with a stated derate.** The pad still fully spans a nominal lead (0.015 mm each side); it is 0.020 mm below the worst-case lead (0.270) and below IPC-7351B least density (0.270). Acceptable for nominal parts, no worst-case margin. |
| C USB-C 16P | GCT USB4105 | 0.300 contact | 0.250 | **0.250 < 0.300 → NOT a candidate** at 0.5 pitch, and the connector needs three different widths (0.250 / 0.400 / 0.550) — no single consistent shrink. |

**1 of 3 types is a shrink candidate: B (LQFP-48), 258 of the 371 gaps.**

Corollary for the programme: at 0.4 mm pitch with a 0.200 mm terminal, a 0.200 mm pad
is the *widest* pad that still leaves a 0.200 mm gap — 0.200 mm is the maximum gap this
part can ever have. Type A therefore can never satisfy a 0.250 mm pad-gap rule with the
RP2354B; the rule needs an exception there, not a copper edit. Same shape of argument
for C (0.300 contact at 0.5 pitch ⇒ 0.200 gap is already maximal).

## 4. Execute shrink on candidates → DRC set diff → new total

Executed on the **one** candidate type only, on the copy
`runs/SHRINK/esc_rev_b.kicad_pcb` (+ the same `.kicad_dru`/`.kicad_pro` so the
4 oz/0.25 mm rules load by basename):

- 288 pads in 6 footprints (U1102/1202/1302/1402/1502/1602), across-pitch dimension
  **0.300 → 0.250 mm**; radial length 1.475 mm and all pad centres unchanged.
- Proven by read-back from the saved board: `(0.3, 1.475) ×288 → (0.25, 1.475) ×288`.
- Shrink is symmetric about each pad centre, so predicted gap gain is +0.025 mm per
  side = +0.050 mm per pad↔pad pair. Both observed deltas match exactly.

| | baseline | after shrink | Δ |
|---|---:|---:|---:|
| total violations (4 oz / 0.25 mm) | **523** | **253** | **−270** |
| — clearance rows | 414 | 144 | −270 |
| — PTH annular ring 0.20 mm | 42 | 42 | 0 |
| — via annular / via diameter / via dangling | 28 / 16 / 16 | 28 / 16 / 16 | 0 |
| — track width / zone neck | 4 / 3 | 4 / 3 | 0 |
| footprint-bound (pad↔pad 0.200 + PTH rings) | 413 | 155 | −258 |
| copper-bound (remainder) | 110 | 98 | −12 |

**SET DIFF (row identity, not totals): GONE = 270, ADDED = 0.** Nothing new appeared.
Every gone row is on the LQFP-48 family:

- 258 × clearance, pad↔pad, `actual 0.2000` → **the whole LQFP gap group, gone**
- 12 × clearance, pad↔track, `actual 0.2250` → collateral: 0.2250 + 0.025 = 0.2500
  (the pad's other side moved away from a track); also gone

| type | pad↔pad 0.200 gaps | cleared | remaining |
|---|---:|---:|---:|
| A QFN-80 (RP2354B) | 75 | 0 | 75 |
| B LQFP-48 (STM32G431CBT6) | 258 | **258** | 0 |
| C USB-C (GCT USB4105) | 38 | 0 | 38 |
| **total** | **371** | **258 (69.5 %)** | **113** |

**New DRC total = 253** (from 523; −51.6 %). Reconciled against the settled figures:
523 = 413 footprint-bound + 110 copper-bound ✔ reproduces exactly; after = 155 + 98 = 253 ✔.

**Solderability cost of the executed shrink:** pad area 0.4425 → 0.3688 mm² (−16.7 %)
per pad, so joint volume falls by about the same fraction; toe/heel are untouched
(length unchanged). The new pad is 0.250 mm — *exactly* the 0.250 mm minimum pattern
in the 4 oz rule set's own provenance table — and the resulting gap is *exactly* the
0.250 mm rule. **Both are zero-margin numbers**, so a ±0.075 mm etch tolerance can
still deliver a 0.175 mm gap in production. The 258 rows are cleared *nominally*, not
demonstrably FAB-REAL; that is a fab sign-off question, not a layout one.

## 5. Verdict

**No — 0.150 mm is wrong, and the answer is per type, not global.** The 371 gaps are
three standard land patterns, not a stuffing error: the board's pads are identical to
the installed KiCad 9.0.7 patterns. Required width for a 0.250 gap: QFN-80 P0.4
**0.150**; LQFP-48 P0.5 **0.250**; USB-C 16P **0.250/0.400/0.550** (three sub-pitches).
So 0.150 is only arithmetically right for the QFN — and there it is fatal: the RP2354B
terminal is 0.200 mm, and 0.150 mm copper is under the 0.250 mm minimum pattern of the
4 oz rule set that counted these violations. Not solderable. USB-C's 0.5-pitch pads
would fall below the 0.300 mm contact. **1 of 3 types is a candidate: LQFP-48
(STM32G431CBT6), 258 gaps**, because 0.250 still spans the 0.220 mm nominal lead.
Executed: 288 pads 0.300→0.250. **DRC 523 → 253, −270, nothing added, 258 of 371
cleared.** Solderable but zero-margin (−16.7 % pad area, gap exactly at the rule and
at the 4 oz floor). The other 113 gaps cannot be shrunk away at all — they need a
fine-pitch pad-gap rule exception.

---

### Evidence files

`REPORT.md` · `groups.json` · `required_widths.json` · `landpatterns.json` ·
`shrink_applied.json` · `setdiff.json` · `runs/BASE/{esc_rev_b.kicad_pcb,.kicad_dru,.kicad_pro,drc_base.json}` ·
`runs/SHRINK/{esc_rev_b.kicad_pcb,.kicad_dru,.kicad_pro,drc_shrink.json}` ·
scripts `step1_group.py`, `step2_widths.py`, `step2_landpattern.py`, `step3_parts.py`,
`step4_shrink.py`, `step4_setdiff.py`, `drclib.py`.
Repo `repos/drone-arm/...` was read only via the prior-wave artefacts and an untouched copy.