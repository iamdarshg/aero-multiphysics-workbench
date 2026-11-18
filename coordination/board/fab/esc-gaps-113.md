# ESC 113 remaining footprint gaps — part change vs documented fab rule exception

Wave 13 specialist report. Scope: the one question only.
Evidence dir: `E:/engineering-portfolio-audit/evidence/esc-gaps-113/` (all work on copies).
Repo board **READ ONLY**: `repos/drone-arm/hardware/esc/rev_b/esc_rev_b.kicad_pcb`.
Input: `evidence/esc-pad-shrink/` (post-LQFP-shrink board + its DRC, 253 violations).
Host: KiCad 9.0.7 (kicad-cli 9.0.7, pcbnew 9.0.7), Python 3.12 for PDF/vision checks.

**Status: COMPLETE.** QFN-80 answer = **none of (a)(b)(c)**. USB-C answer = **(a) none, (b) no,
(c) only as a waiver** — plus one measured, executable derate that clears 24 of the 38 and is
*not* offered as a compliant fix.

## 0. Question

For the ESC's 113 remaining footprint gaps (QFN-80 U201 RP2354B = 75; USB-C 16P J202/J203
GCT USB4105 = 38), what actually clears them — a part change, or a documented fab rule
exception — and can either be executed?

---

## 1. Baseline re-derived from row-level data (not from the settled totals)

I re-classified the 253 post-shrink DRC rows from the board itself (`step1_rows.py`,
`rows_after_shrink.json`), matching every violation item UUID to a pad in the board:

| | count |
|---|---:|
| total violations (4 oz / 0.25 mm rule set) | **253** |
| — clearance | 144 |
| — annular_width (70 via + PTH) | 70 |
| — via_diameter / via_dangling / track_width / connection_width | 16 / 16 / 4 / 3 |
| **pad↔pad, same footprint (the subject)** | **113** |
| — pad↔pad, different footprints | **0** |

The 113 decompose exactly as settled, and the USB-C family splits into three sub-groups that
the settled figure lumped together:

| ref | footprint | pitch | pads (wA×wB) | rows | can a 0.250 gap exist? |
|---|---|---|---:|---:|---|
| U201 | QFN-80-1EP_10x10mm_P0.4mm | 0.400 | 0.200 / 0.200 | **75** | **no** (§2) |
| J202 | GCT USB4105-xx-A 16P | 0.500 | 0.300 / 0.300 | 7 | **no** (§3) |
| J203 | GCT USB4105-xx-A 16P | 0.500 | 0.300 / 0.300 | 7 | **no** (§3) |
| J202 | GCT USB4105-xx-A 16P | 0.650 | 0.600 / 0.300 | 4 | **yes** — needs 0.500/0.300 |
| J203 | GCT USB4105-xx-A 16P | 0.650 | 0.600 / 0.300 | 4 | **yes** — 0.500/0.300 |
| J202 | GCT USB4105-xx-A 16P | 0.800 | 0.600 / 0.600 | 8 | **yes** — needs 0.550/0.550 |
| J203 | GCT USB4105-xx-A 16P | 0.800 | 0.600 / 0.600 | 8 | **yes** — 0.550/0.600 |
| | | | | **113** | 14 no / 24 arithmetic-only |

75 + 14 + 8 + 16 = 113 ✔. The "38" is therefore **14 impossible + 24 arithmetic-only**, and the
settled framing ("0 of 38 cleared, contact 0.300 forbids 0.250") is correct only for the 14.
Row identity, not totals — two independent runs (253 then 229) were matched by
(rule text, sorted item UUIDs); no row was inferred from a count.

---

## 2. Step 1 — QFN-80 U201 RP2354B, 75 gaps: **none of (a), (b), (c)**

The datapoint that decides it: **the gap is a function of pitch and pad width only.**
`gap = e − w` for equal pads. On this board e = 0.400 and w = 0.200, so gap = 0.200. For a
0.250 gap the pad must be **0.150**.

### (a) A different package for the same die — DOES NOT EXIST, and would not help

[RP2350 datasheet](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf)
(11,094,994 B, downloaded to `sources/rp2350-datasheet.pdf`, rendered pages in `sources/`):

- **Table 1, p. 13** — the entire family is four products in **two** packages:
  RP2350A/RP2354A = **QFN-60**, RP2350B/**RP2354B** = **QFN-80**. No third package, no larger body.
- **§14.3, p. 1327** — "RP2354A and RP2354B … use the same QFN-60 (RP2354A) and QFN-80
  (RP2354B) packages." So there is no flash-in-package variant outside these two.
- **§14.1, Fig. 147 (QFN-60), p. 1324** — D/E = 7 BSC, b = 0.130/0.180/0.230, **e = 0.400 BSC**.
- **§14.2, Fig. 149 (QFN-80), p. 1326** — D/E = 10 BSC, b = **0.150/0.200/0.250**, **e = 0.400 BSC**.

**Both packages are e = 0.400 BSC.** A package change to QFN-60 therefore changes nothing about
the gap: at 0.4 pitch the 0.250 mm gap still requires 0.150 mm on both pads. And the QFN-60 is
not a swap anyway — 60 pins vs 80, 30 GPIO vs 48 (Table 1) — so it would be a re-layout with no
gain. **Option (a): none.**

The same table also shows 0.150 is *exactly* `b min`: a 0.150 pad equals the narrowest lead the
part can legally have, i.e. no side fillet on any part above the tolerance floor (b rises to
0.250), and 0.150 mm copper is below the 0.250 mm published 4 oz pattern floor (§2b). Two
independent grounds, both fatal — this confirms the wave-12 rejection and sharpens its basis.

### (b) A documented exception from a fabricator — NOT AVAILABLE, and the survey says why

`evidence/fab-4oz-capability/REPORT.md` §2 (8 vendors, 5 with an explicit 4 oz row, quotes in
`sources/QUOTES.md`): **no surveyed house publishes a 4 oz space below 0.229 mm**; the tightest
capability-table figure is 0.250 (Multi-CB *special production*, 140 µm). PCBWay 0.330, Bay Area
0.305, LeitOn 0.400. Multi-CB and LeitOn both *have* a special/on-request column and both price
4 oz **further** from 0.200, not closer — so this is not a price tier. The ESC needs 0.200/140 µm
= 1.43×, under every published 4 oz figure.

**There is nobody to ask, so there is no exception to document.** A "waiver" here would be a
waiver of a capability that does not exist, i.e. not a waiver at all.

### (c) Local 3 oz / 2 oz copper under one part — NOT POSSIBLE

Copper weight is a foil/plating property of the laminate stack-up; it is uniform across the board
per layer. There is no such thing as a locally thinner outer layer on a single build. (A mixed
stack — 2 oz outer / 4 oz inner — is a real fab option, but it is a *board-level* outer weight
change, not a local one, and it is exactly the same decision as (b) below.)

### What actually clears the 75: a board-level copper-weight change (outside the three options)

At **3 oz (105 µm)** Multi-CB special production publishes **0.200 track / 0.200 space**
(`fab-4oz-capability/REPORT.md` §5, 105 µm row) — the ESC's gap is exactly 0.200, so **all 113
clear with zero layout change**; the 0.200 QFN pads sit exactly on that house's 0.200 track floor.
At 2 oz, 0.200 space is comfortably published (Eurocircuits/LeitOn 0.200, Multi-CB 0.150,
JLC 0.160). This is the only route that works, and it is a current-capacity decision on the
43.5 A phase rail, not a footprint decision.

---

## 3. Step 2 — USB-C 16P J202/J203 GCT USB4105, 38 gaps: **(a) none, (b) no, (c) waiver only**

### Datasheet check: the board's footprint *is* the vendor's recommended land pattern

[GCT USB4105 drawing, rev B3, 24/02/23](https://media.digikey.com/pdf/Data%20Sheets/GCT%20PDFs/USB4105%20-%20Product%20Drawing.pdf)
(452,595 B, `sources/gct_usb4105_1.pdf`, rendered `sources/gct_page1.png` — the page is vector
line-work with no extractable text, so it was read as an image). "Recommended PCB Layout, as
viewed from component side, tolerance ±0.05 mm":

| drawing callout | board |
|---|---|
| **4x 0.60** solder areas | 8 pads at 0.600×1.150 (A4/B4 and A9/B9 coincide → 4 physical) |
| **8x 0.30** solder areas | 8 pads at 0.300×1.150 |
| **0.50** between the 0.30 pads | 0.500 pitch ✔ |
| **12x 1.15** | 12 physical solder areas = 16 board pads (the 4 power positions carry an overlaid A/B pad pair), all 1.150 long ✔ |
| 2x Ø0.65, 2x 2.10 / 2x 1.70 | Ø0.65 ×2 + shield 1.0×2.1 / 1.0×1.8 ✔ |

So the 0.200 mm gaps are the connector vendor's own pattern, not an over-padded variant. The
0.65 and 0.80 spacings are the vendor's inter-group spacings (power contact to first signal
contact, power contact to power contact), not a choice the board made.

### (a) A coarser-contact USB-C receptacle — DOES NOT EXIST

The drawing fixes the signal contact pitch at **0.50** and the power contacts at 4x0.60. That is
the USB Type-C receptacle contact geometry: 16P and 24P receptacles both use 0.5 mm contact pitch,
because the plug is 0.5 mm pitch by standard — corroborated by an independent layout guide,
"[the USB Type-C receptacle] packs 24 pins into a 8.94 mm × 7.30 mm body, with **pad pitches as
tight as 0.5 mm**" ([hillmancurtis](https://hillmancurtis.com/usb-c-connector-pcb-layout/)). No 16P
receptacle with coarser contacts was found, so there is no part to check pinout compatibility
against. **Option (a): none.**

At 0.5 pitch with 0.300 pads the gap is *already* the maximum this connector can have
(0.500 − 0.300 = 0.200). The 14 rows at 0.5 pitch can never reach 0.250 with this part or any
USB-C part.

### (b) Local copper weight — same non-option as §2(c).

### The 24 rows at 0.65/0.80 are arithmetically clearable — measured, not asserted

`gap = pitch − (wA + wB)/2`, so:
- **0.65 pitch** (power 0.600 vs signal 0.300): keep 0.300, take the power pad to **0.500** →
  gap = 0.650 − 0.400 = **0.250 exactly**.
- **0.80 pitch** (0.600 vs 0.600): take both to **0.550** → gap = 0.300.

Executed on a copy (`runs/USBC/`, `step3_shrink_usbc.py`): the 16 pads at 0.600×1.150
(A1/A4/A9/A12/B1/B4/B9/B12 on both connectors) → **0.500×1.150**, read back from the saved file
(16 pads at 0.5×1.15, 16 at 0.3×1.15). Nothing else touched; same footprint, same part, same nets.

**DRC set diff (`setdiff_usbc.json`): 253 → 229. GONE 24, ADDED 0.** All 24 gone rows are
clearance rows inside J202/J203 (8 each). Re-classifying the 229-row board
(`rows_after_usbc.json`) leaves **89** pad↔pad rows: **75 QFN + 14 USB-C at 0.5 pitch**, both
sub-groups unchanged in count and geometry. The arithmetic and the instrument agree exactly.

| type | pad↔pad before | cleared | remaining |
|---|---:|---:|---:|
| QFN-80 (RP2354B) | 75 | 0 | 75 |
| USB-C @0.5 | 14 | 0 | 14 |
| USB-C @0.65 | 8 | **8** | 0 |
| USB-C @0.80 | 16 | **16** | 0 |
| **total** | **113** | **24** | **89** |

### Cost of that shrink — which is why it is not offered as a fix

- The power pads go **0.100 mm narrower than the drawing's 0.60 land**: −0.05 mm per side, pad
  narrower than the contact it must wet — **the same criterion that disqualifies the QFN 0.150**.
  Applying one rule to both families, this is a derate, not a compliant pattern.
- Pad area 0.690 → 0.575 mm² (**−16.7 %**), on the pads the drawing rates **5.00 A collectively
  for VBUS / 6.25 A collectively for GND** (i.e. 2.5 A per merged VBUS contact pair). At 4 oz that
  land is 0.070 mm² of copper. I have **not** certified that joint thermally.
- The gap lands on **0.250 exactly** = zero margin; ±0.075 mm etch tolerance can deliver 0.175.
- It buys 24 rows and leaves 89, so it cannot make the board compliant on its own.

---

## 4. Step 3 — exact change list (the answer to "what changes")

| # | ref | now | change | PN / package | pins | drop-in? | netlist? | exists / stock |
|---|---|---|---|---|---|---|---|---|
| 1 | U201 | RP2354B, QFN-80-1EP 10×10 P0.4 | **no change exists** | RP2354A QFN-60 7×7 is the only other package and is **also e = 0.400 BSC** | 60 vs 80 | no | yes (30 vs 48 GPIO) | exists; **useless** — same pitch, same gap, loses 18 GPIO |
| 2 | J202/J203 | GCT USB4105-xx-A 16P | **no change exists** | no 16P USB-C receptacle has coarser than 0.50 contact pitch | 16 | n/a | n/a | n/a |
| 3 | all | 4 oz / 140 µm outer | **reduce to 3 oz (105 µm)**, Multi-CB special production publishes 0.200/0.200 | — | — | — | **none** | capability published; custom quote tier |

Rows 1 and 2 are *absences*, not proposals: no orderable part substitution exists for either
family. The only line item that actually changes the outcome is **#3, a stack-up change**, which
is outside both options the question offered. Stock checks are moot for rows 1–2 since there is
nothing to order. (One search snippet listed RP2354B out of stock at LCSC — external text, not
verified against a live stock API, and not used in any conclusion.)

---

## 5. Step 4 — executed vs designed

**Executed (real, on a copy, with a DRC receipt):**
- Classified all 253 post-shrink rows against the board's own pad UUIDs → the 113 and its
  sub-groups (§1). Both counts reconcile with the settled figures exactly.
- Shrank the 16 USB-C 0.600 power pads to 0.500 in `runs/USBC/` (same part, same nets, read-back
  verified) and ran `kicad-cli pcb drc --severity-all` with the same 4 oz `.kicad_dru`:
  **253 → 229, GONE 24, ADDED 0** (§3).
- Downloaded and read both datasheets; both checks are primary-document, not secondary.

**Designed / not executed (deliberately):**
- No pad edit for U201: every 0.250-gap option there is 0.150 mm, which is both `b min` and
  under the 4 oz pattern floor.
- No pad edit for the 14 USB-C @0.5 rows: 0.250 pads < 0.300 contact.
- No part-order or stack-up change: requires a purchase/quote decision and (for #3) an owner
  call on the 43.5 A rail.

---

## 6. Verdict

**QFN 75: none.** No package in the RP2354 family has a pitch other than **e = 0.400 BSC**
(RP2350 datasheet Table 1 p.13, Fig. 147 p.1324, Fig. 149 p.1326), so no part change can move the
gap; no fab publishes 0.200 at 4 oz (8-fab survey) so no exception can be written; local copper
weight is not a real option. The 75 gaps sit at the maximum this part allows with any pad that
still spans the nominal lead (0.200); reaching 0.250 needs a 0.150 pad, which equals `b min` —
zero fillet on any part above the tolerance floor — and is under the 4 oz pattern floor.

**USB-C 38: none as a part change; 24 clear by a measured pad derate; 14 are unwinnable.**
The board's pads *are* the GCT drawing's recommended land (4x0.60 + 8x0.30, 0.50 pitch), and no
USB-C receptacle has coarser contacts. Shrinking the 0.600 power pads to 0.500 cleared 24 rows
(253 → 229, GONE 24, ADDED 0) but puts the pad 0.05/side inside the contact and lands on a
zero-margin 0.250 gap.

**So the honest answer for the ESC is neither "part changes" nor "documented waivers" at 4 oz:
it is a copper-weight decision.** At 4 oz the 113 are unorderable and unwaivable — there is no
fabricator to waive them. At **3 oz** all 113 become legal with **zero layout change**
(Multi-CB 105 µm special: 0.200/0.200), and at 2 oz they are comfortable. That choice trades the
rail's current capability, which is a board-level electrical decision, not a footprint one.

If 4 oz must be kept, then the waiver route is dead and the ESC needs a different MCU package
family and a different connector standard — i.e. a re-architecture, not a change list.

---

### Evidence files

`REPORT.md` · `rows_after_shrink.json` (253 rows → 113) · `rows_after_usbc.json` (229 rows → 89) ·
`pads_census.json` (per-pad geometry/nets for U201, J202, J203) · `setdiff_usbc.json` (row-level
set diff) · `usbc_shrink_applied.json` (16 pads, before/after + read-back) ·
`runs/USBC/{esc_rev_b.kicad_pcb,.kicad_dru,.kicad_pro,drc_usbc.json}` ·
`step1_rows.py`, `step2_pads.py`, `step3_shrink_usbc.py`, `step4_setdiff.py` ·
`sources/{rp2350-datasheet.pdf, gct_usb4105_1.pdf, gct_page1.png, rp2350_qfn80_pkg.png,
rp2350_qfn60_pkg.png, rp2350_pkg2.txt}`.
Repo `repos/drone-arm/...` was never written; the repo board was read only through the wave-12 copy.

### Limitations

- The 4 oz floor (0.250) that *counts* the 113 is Eurocircuits' 3 oz row carried one step up —
  the .dru's own provenance block says so. The count is therefore a conservative estimate, not a
  measured 4 oz capability; the verdict is unchanged either way (every real 4 oz row is ≥0.229).
- The USB-C VBUS/GND joint at 0.500 land is arithmetic only; no thermal or peel-strength
  calculation was run, and it is not endorsed here.
- U201's pad pattern was taken from the board and cross-checked against the KiCad 9.0.7 shipped
  land pattern in wave 12; I did not re-load the library file this wave.