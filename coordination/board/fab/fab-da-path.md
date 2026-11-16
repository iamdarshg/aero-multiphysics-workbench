# fab-da-path — the cheapest path that clears drone-arm's 19 non-through vias

**Question (single):** of (i) six layers + an 80-pin re-fanout and (ii) a 0.5 mm LQFP-100 MCU, which
is cheaper — cost both, pick one, execute what `pcbnew` allows, and verify.

**Input board:** `evidence/fab-da-36via/da_main_rev_b_36via_batA.kicad_pcb`
(sha256 `160D6B97…9DED`, 2,268,484 B, 337 vias, **19 non-through**) — re-derived here, not trusted:
census 19 (15 micro + 4 blind by pair), DRC `{via_diameter: 4}`, unconnected 0 on both tools,
min drill 0.100, RF void `void_A 4.1699 mm² = 9.8338 %` / `void_B 3.8754 = 9.1392 %`.
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/fab-da-path/`. All work on copies; nothing
written into a repo.

> **HEADLINE — recommend (i), and it is not close on cost: (i) changes 0 nets, 0 pins, 0 footprints,
> 0 lines of firmware; (ii) changes 60 pins/47 nets, moves 20 footprints, and needs a firmware and
> schematic rewrite for source that is not in this repo. But the honest geometry is that neither
> candidate's pitch is 0.85 mm: the LQFP-100 is short by 0.075 mm between pads and legal only at
> exactly 0.000 mm margin on a 0.15 mm escape trace. Executed: the two layers were added (measured
> worth **0.000 mm and 0 clears**), and 2 of 19 vias were converted to through vias — **2 cleared,
> 17 remain** (U10 12 · C32 2 · C12 1 · C40 1 · FB1 1), U40 now fully clear.**

---

## 0. Instrument validation before any number is trusted

| check | base board | how |
|---|---|---|
| non-through by span | **19** (15 micro + 4 blind), 16 stacks | `s6_verify.py` — span from `CuStack()` pair, never from the declared token |
| declared vs pair | 5 of 19 disagree | same |
| DRC, board's own rules | **4** `{via_diameter: 4}` | `kicad-cli pcb drc --severity-all` |
| DRC, no-HDI gate (`no_hdi.kicad_dru`, drill ≥ 0.20) | **22** = 18 `microvia_drill_out_of_range` + 4 `via_diameter` | same + `.kicad_dru` |
| unconnected | **0** (`kicad-cli`) and **0** (`pcbnew GetUnconnectedCount`) | both tools, as required |
| min drill | 0.100 (18 vias) | `s0_dump.py` |
| RF void | 4.1699 mm² = 9.8338 % (void_B 3.8754 = 9.1392 %) | `s5_void.py` |

Every figure reproduces wave 17's shipped board, so the input is the board that wave shipped and the
instruments agree with the previous specialist. Board: 4 copper layers, 165 footprints, 2,301 tracks,
657 pads, netclass clearance **0.125 mm**, via 0.60/0.30, `m_MinThroughDrill` **0.200**,
`m_ViasMinAnnularWidth` **0.100**, `m_ViasMinSize` **0.600**, board 14,036 mm².

---

## 1. Where the 19 actually are, and what each one costs to free

`s1_neighbourhood.py` + `s2_sixlayers.py` + `sixL.json`. U10 is an RP2354B **QFN-80, 0.4 mm pitch,
pads measured 0.200 × 0.800 mm**, 9.9 × 9.9 mm, 60 live pads carrying **47 distinct nets**, 20 spare
pads (7 `GPIO34-40`, 7 `GPIO41-47`, 6 `QSPI*`), 9 no-net thermal pads and a 3.4 mm exposed pad.

A 0.60/0.30 through via needs **0.425 mm** from the via centre to foreign copper *edge* on **every**
layer (0.300 + 0.125). Per via, run over all four layers:

```
in-place legal at 0.60/0.30 : 0 of 19   (best case /VDD_CC112 at −0.118 mm)
negative on 4 layers        : 10 of 19
negative on 3 layers        :  4 of 19      negative on 2 layers : 4 of 19
negative on 1 layer         :  1 of 19      (/915 MHz RF/VDD_CC112, trk /CC_PA, short 0.118)
blocked LAYER-INSTANCES, total : 61         (mean 3.2 per via)
binding item kind           : track 16 · pad 2 (C12.2 /GND, FB1.2 /3V3_ADC) · foreign via 1
```

So the work per via is "move 2–4 pieces of somebody else's copper laterally", 61 pieces in all —
and 2 of the binding items are **pads that cannot move** without moving a part or re-assigning a pin
(both closed in waves 16–17).

---

## 2. Cost of (i): six layers + an 80-pin re-fanout

| item | count | note |
|---|---|---|
| nets changed | **0** | netlist, schematic and firmware untouched |
| pads/pins moved | **0** | U10 stays at (59.000, 50.000), orientation 0° |
| footprints moved | **0** | |
| foreign copper pieces to move | **61** layer-instances over 19 vias (16 tracks + 2 pads + 1 via binding) | measured, §1 |
| pins to re-escape | **60** live pads on a 0.4 mm pitch | measured |
| stackup work | 4 → 6 copper layers (In3/In4), stackup block + owner approval | executed here at board level |
| fab cost | unquoted for drone-arm. This programme measured ESC 4L 3oz $450–870 / 5 pcs vs 6L 3oz $1,300–1,900 = **1.5–2.9×**; drone-arm is 1 oz 140 × 100 mm and has no 6L quote in evidence | not measurable here |
| effort estimate | **25–40 h** (61 copper moves at ~20 min, 60 escapes at ~10 min, plus a DRC gate per change) | estimate from the measured item counts, not a measurement |

**What the two extra layers are actually worth — measured, and the answer is nothing in place:**
a through via is legal on the *minimum* over all layers, so an empty new layer can never raise that
minimum. `s2_sixlayers.py` rebuilds the same board with In3/In4 and re-runs the model:

```
stack 4 : F.Cu In1.Cu In2.Cu B.Cu
stack 6 : F.Cu In1.Cu In2.Cu In3.Cu In4.Cu B.Cu
in-place 0.60/0.30 margin identical on both stacks : 19 of 19   (Δ = 0.0000 mm)
in-place legal at 0.60/0.30                        : 4L 0 · 6L 0
```

Consequence, and it is the decisive sentence for (i): **the layer count changes the routing capacity
of the board, never the legality of a through via.** Inside U10's fan-out every escape is on F.Cu
(the pads are F.Cu SMD; reaching In1/In2/In3/In4 needs a via — the thing that will not fit), so more
inner layers buy *the rest of the board* somewhere to move to, not the ring.

---

## 3. Cost of (ii): STM32H723VGT6, 0.5 mm LQFP-100

| item | count | note |
|---|---|---|
| net ↔ pin changes | **60** live pads, **47 distinct nets** | every pin number changes; a schematic + netlist edit, not a layout edit |
| pads | 90 → **101** (100 + EP) | 9 centre thermal pads disappear, 20 spare QSPI/GPIO pads become 40 |
| pad positions preserved | **0 of 60** | QFN perimeter vs 25-per-side leaded body |
| land span | QFN 9.9 × 9.9 mm body → LQFP **16.95 mm** land span | §3.1 |
| footprints that must move | **20** | measured `collide_land_count`: C30–C42 (13), C10–C13 (4), FB1, R4, L1 |
| schematic edits | U10 symbol swap + 47 net renames + ERC | |
| firmware | **not in this repo** | see below |
| fab cost | 4-layer unchanged (same board, same 1 oz) | one saving: only the part changes |

**Firmware is not in this repo.** `Get-ChildItem -Include *.c,*.h,...` returns **zero** source files.
`meson.build` names 36 sources and 13 include directories (`src/main_board/low_level/*`, `boot2_w25q080.S`,
`PICO_SDK 2.1.0`, `-DRP2350`), and `docs/engineering/FIRMWARE_SOURCE_AUDIT.md` records that
"the source tree … does not contain the firmware inputs listed by meson.build … an image cannot be
built from this checkout". So (ii) is not a firmware *port* with a measurable diff — it is a rewrite
from a build description against an RP2350 bootrom (boot2 W25Q080 stage-2, 20 low-level drivers),
with **no baseline source to port from**. That is the unbounded line item, and it lands on top of the
20 footprints and 60 pin remaps that (i) does not pay.

### 3.1 Datasheet check — does a 0.5 mm LQFP-100 really permit a 0.85 mm through via?

Two sources, kept separate because only one of them could be read from this host:

* **Package (ST):** STM32H723VE datasheet DS13313, `LQFP100 — 100-pin, 14 × 14 mm low-profile quad
  flat package`, lead pitch **e = 0.50 mm BSC** ([ST datasheet PDF](https://www.st.com/resource/en/datasheet/stm32h723ve.pdf),
  [package-information page](https://www.st.com/content/st_com/en/technical-documents/stm32c551cc_asset/chunk-017-topic-1l-lqfp100-14x14-pi.html)).
  **Provenance note:** both ST URLs returned `fetch failed` from this host (two attempts), so the
  *drawing's numeric table* could not be read directly; the body/pitch designation above is from the
  datasheet title and the ST package-information page title, not from a fetched table.
* **Land pattern (measured on this host):** KiCad 9 `Package_QFP:LQFP-100_14x14mm_P0.5mm`, loaded with
  `pcbnew.FootprintLoad` and measured pad by pad: **100 pads, 25 per side, pitch 0.5000 mm,
  pad 0.300 × 1.600 mm**, pad tips at ±8.475 mm (**land span 16.95 mm**).

Arithmetic at the board's own 0.125 mm netclass clearance and the standard 0.10 mm annular ring:

| lane | pitch | copper beside the via | available | need (0.300 + 0.125) | margin |
|---|---|---|---|---|---|
| QFN-80, pad beside | 0.400 | 0.200 pad | 0.3000 | 0.425 | **−0.1250** |
| QFN-80, trace beside | 0.400 | 0.150 trk | 0.3250 | 0.425 | **−0.1000** |
| LQFP-100, pad beside | 0.500 | 0.300 pad | 0.3500 | 0.425 | **−0.0750** |
| LQFP-100, trace beside | 0.500 | 0.150 trk | 0.4250 | 0.425 | **+0.0000** |

**Verdict: no, not as stated.** A 0.60/0.30 through via does not fit between LQFP-100 land pads —
it needs **0.575 mm** of pitch and 0.500 mm is short by **0.075 mm**. It is legal only on the
*trace-only* part of a lane once the escape is a 0.15 mm trace, at **exactly 0.000 mm margin** (i.e.
no margin at all, and a 0.20 mm trace breaks it at −0.025 mm). And at 0.4 mm pitch the same test says
something stronger — the largest inline via a 0.20 mm QFN pad allows is 0.35 mm diameter, whose drill
(0.15 mm with a 0.10 annular) is below the board's own 0.20 mm through-drill floor, so **there is no
legal inline through via at 0.4 mm pitch at any size**. The brief's "0.5 mm gives 0.85 mm-capable
lanes directly" is therefore *conditionally* true: it buys 0.075–0.100 mm of a 0.125 mm shortfall and
leaves zero margin, with a staggered two-row fan-out still required either way.

---

## 4. Recommendation

**Take (i): six layers plus the U10 re-fanout.** The geometry difference is not decisive — both
packages need the same staggered two-row fan-out and the LQFP-100 clears the 0.85 mm test only at
0.000 mm margin — while (ii) charges 60 pin remaps, 20 moved footprints, a schematic swap and a
firmware rewrite (against source that is not in this repo) for that 0.075 mm. Keep the RP2354B, its
netlist and its software; spend the money on routing, and note in the record that the two extra
layers buy routing capacity, **not** via legality (measured: 0.000 mm, §2).

---

## 5. What was executed

### 5.1 The six-layer stackup (executed, DRC-neutral)

`s2_sixlayers.py`: `SetCopperLayerCount(6)`, In3.Cu/In4.Cu named and enabled, zones re-filled, saved.
`work/sixL.kicad_pcb` (2,268,531 B). `(layers …)` now reads
`F.Cu(0) In1.Cu(4) In2.Cu(6) In3.Cu(8) In4.Cu(10) B.Cu(2)`; **there is no `(stackup)` block** — the
orderable dielectric/thickness set is still an owner decision (the 4-layer equivalent was authored in
`evidence/da-stackup/stackup_block.sexp`). DRC on the 6-layer board: `{via_diameter: 4}`,
unconnected 0 — **set diff `{}` against the 4-layer board**, i.e. the layer add moved no copper.

### 5.2 The U10 re-fanout attempt, and why the layer add does not help

`s3_plan.py` tried the move that the extra layers were supposed to enable: **bow the blocking foreign
track** away from the via site, keeping both of its endpoints. All 19 are ineligible:

```
bows legal on their own layer            : 0 of 19
bow slack on the blocked layers           : −0.325 … −0.600 mm
blockers that are not tracks              : 2 pads (C12.2 /GND, FB1.2 /3V3_ADC) + 1 via (/RF_GPIO0 350 µm)
tracks whose two ends sit on through vias
  (so they could re-lay on In3 for free)  : 0 of 16
```

Every inner layer around the ring is already at its clearance budget, and the one place with free
copper is In3/In4 — reachable only through a via, which is the thing that does not fit. That is the
measurement behind §2's conclusion, and it is why the layer add clears **0** of the 19.

### 5.3 The conversions that did work (2 of 19)

`s3b_sites.py` / `s3c_sites.py` search ±2.0 mm (also re-run at ±2.6 mm) around each microvia's own XY
for a *through* via site plus a legal stub on every layer the microvia connected, in two tiers:

```
tier 1  0.60/0.30 (the board's netclass)          : 0 of 19 have a legal site + stub
tier 2  0.40/0.20 (smallest THROUGH via the board's
        own rules allow: drill 0.200 = m_MinThroughDrill,
        annular 0.100 = m_ViasMinAnnularWidth)    : 2 of 19
        /915 MHz RF/VDD_CC112  site 0.050 mm away  (F.Cu->In1.Cu)
        /RF_MOSI               site 0.552 mm away  (In1.Cu->B.Cu)
```

`s4_exec.py` puts each on its own copy in its own `pcbnew` process and gates it with an isolated
`kicad-cli pcb drc`; keep only if no violation *type* grows except `via_diameter` and unconnected does
not increase.

| # | net | span | move | DRC delta | verdict |
|---|---|---|---|---|---|
| 1 | /915 MHz RF/VDD_CC112 | F.Cu→In1.Cu | 0.050 mm | `{}` (+1 via_diameter) | **KEEP** |
| 2 | /LSM_INT1 (FB1) | In1.Cu→In2.Cu | 1.010 mm | `via_dangling 1, track_dangling 1`, unc 1 | DROP |
| 3 | /RF_MOSI | In1.Cu→B.Cu | 0.552 mm, stubs In1+In2+B | `track_dangling 1` | DROP |
| 4 | /RF_MOSI (retry) | In1.Cu→B.Cu | 0.552 mm, stubs In1+B only | `{}` (+1 via_diameter) | **KEEP** |

**Attempted 4 · kept 2.** Both kept ones are the **U40 pair**, so the U40 cluster is now closed (2/2)
and the remaining 17 are all outside U40.

Two tooling notes, recorded because each one silently lied once:

1. **Dangling from an invented stub layer.** Attempt 3 failed on `track_dangling` — and the dangling
   track was *mine*: I had stubbed In2.Cu where the microvia had no In2 track at all (its node only
   had track ends on In1 and B). The fix is to stub only layers where a same-net track actually
   terminates at the node, which is why attempt 4 differs from attempt 3 by **one layer list**.
2. **Totals hide a set diff.** With the no-HDI gate the violation *total* is 22 before and after this
   wave (`22 = 18 + 4` → `22 = 16 + 6`), while the set moved by `{microvia_drill_out_of_range: −2,
   via_diameter: +2}`. A total-only check would have called a real improvement "no change".

---

## 6. Verification of the final artefact

`da_main_rev_b_path6L.kicad_pcb` (sha256 `DE80636F308A8BAD3FA944AE…`, 2,270,141 B). Step-3 and
step-4 boards are retained as receipts (`work/sixL.kicad_pcb` `6B998305…`, `sixL_t2.kicad_pcb`
`F9AD7B53…`).

| check | base (4L) | + 2 layers | **final (6L)** | how |
|---|---|---|---|---|
| copper layers | 4 | 6 | **6** | `s6_verify.py` |
| vias total | 337 | 337 | **337** | same |
| **non-through by span** | **19** | **19** | **17** | same |
| by layer pair | F→In1 7 · In1→In2 5 · F→In2 2 · In2→B 3 · In1→B 2 | identical | **6 · 5 · 2 · 3 · 1** | same |
| non-through stacks | 16 | 16 | **14** | same |
| declared vs pair mismatches | 5 | 5 | 5 | same |
| **DRC, own rules — set diff** | `{via_diameter: 4}` | `{}` vs base | **`{via_diameter: +2}`** — nothing else added | `kicad-cli pcb drc --severity-all` |
| **DRC, no-HDI gate — set diff** | 22 = 18 micro + 4 via_dia | — | **22 = 16 micro + 6 via_dia** → `{microvia: −2, via_diameter: +2}` | `.kicad_dru` + `kicad-cli` |
| unconnected, `kicad-cli` | 0 | 0 | **0** | DRC json |
| unconnected, `pcbnew` | 0 | 0 | **0** | `s5_void.py` |
| cap status | neither tool caps | — | same | — |
| **minimum drill** | 0.100 | 0.100 | **0.100** (16 vias at 0.1, was 18) | `s6_verify.py` |
| drill < 0.20 | 18 | 18 | **16** | same |
| **RF void A** | 4.1699 mm² = 9.8338 % | **identical** | **identical 4.1699 / 9.8338** | `s5_void.py` |
| **RF void B** | 3.8754 = 9.1392 % | identical | **identical 3.8754 / 9.1392** | same |

The `via_diameter` growth is the *declared* cost, not a defect: 0.40/0.20 is the smallest **through**
via the board's own rules permit (`m_MinThroughDrill` 0.200, `m_ViasMinAnnularWidth` 0.100) and it is
only flagged because `m_ViasMinSize` is 0.600 — the same class wave 16 shipped for 5 vias. It is not
HDI: both vias pass the `FA-PTH-ONLY` gate at 0.200 mm drill.

---

## 7. Final count and the honest remaining work

**2 of 19 cleared (10.5 %).** 19 → 17. All 19 stay non-HDI-clean; the two conversions are through
vias at the board's own drill and annular floors.

**What remains, in footprints and nets: 0 footprints, 17 vias on 10 nets.**

| owner | vias | nets |
|---|---|---|
| **U10** (RP2354B, 0.4 mm QFN-80) | **12** | /3V3 · /GNSS_RX · /HGM · /LSM_INT1 ×3 · /PA_EN ×2 · /RF_GPIO0 ×2 · /RF_GPIO2 · /RF_MISO ×2 · /USB_DP_MCU ×2 · /SENS_SCLK |
| C32 | 2 | /RP2354B MCU/USB_DP_MCU |
| C12 | 1 | /GNSS_RX |
| C40 | 1 | /RF_GPIO0 |
| FB1 | 1 | /LSM_INT1 |
| U40 | **0** | closed by this wave (2/2) |

What the remaining 17 need, in the order the evidence supports:

1. **Nothing that the layer add can give them.** Measured: 19/19 identical in-place margins on 6
   layers, 0 of 16 blockers re-layable for free, 0 of 19 bows legal. `via_diameter` aside, the board
   is exactly as blocked at 6 layers as at 4.
2. **The fan-out rip-up: 61 pieces of foreign copper moved laterally** (16 tracks binding 16 vias,
   2 pads, 1 foreign via) across 2–4 layers per via, plus 60 escapes re-drawn on a 0.4 mm pitch —
   the 25–40 h of §2, 0 footprints.
3. **Or the HDI the board already declares** (all 17 are `MICROVIA`/`BLIND_BURIED` and legal in a
   1+2+1 build): a decision, not work — still the cheapest real answer, and still out of scope here.
4. **Or the LQFP-100**, which by §3.1 buys 0.075 mm of margin (to exactly 0.000) and costs 20
   footprints, 60 pin remaps, a schematic swap and a firmware rewrite from absent source.

### Artefacts

| file | note |
|---|---|
| `da_main_rev_b_path6L.kicad_pcb` (sha256 `DE80636F…`, 2,270,141 B) | **the shipped board**: 6 layers, 17 non-through (from 19), DRC own set diff `{via_diameter: +2}`, gate set diff `{microvia: −2, via_diameter: +2}`, unconnected 0 on both tools, min drill 0.100, RF void bit-identical |
| `work/sixL.kicad_pcb` (sha256 `6B998305…`) | the layer add alone: 19 non-through, DRC set diff `{}` — the receipt for "the layers changed nothing" |
| `sixL_t2.kicad_pcb`, `sixL_t2_t4.kicad_pcb` | the two gate steps (`+1`, then `+2` conversions) |
| `drc/own_sixL.json`, `drc/own_final.json`, `drc/gate_base.json`, `drc/gate_final.json` | every DRC run quoted |
| `sixL.json`, `sites_through.json`, `sites_through2.json`, `neighbourhood.json`, `lqfp100_land.json` | 4L-vs-6L margins, site searches, U10 neighbourhood, LQFP-100 land measurements |
| `plan.json`, `plan_rejected.json`, `candidates*.json`, `sixL_t2.gate.json`, `sixL_t2_t4.gate.json` | every candidate, kept or dropped |
| `census_base.json`, `census_final.json`, `void_measure.json` | census and void, both boards |

Scripts, in the order they matter: `s0_dump.py` (inventory) · `s6_verify.py` (span census, min drill,
unconnected) · `s1_neighbourhood.py` (U10 window, LQFP collision set, live pins) · `s2_sixlayers.py`
(6-layer build + the 4L/6L margin proof) · `s3_plan.py` (blocker-bow plan) · `s3b_sites.py` /
`s3c_sites.py` (through-site search, two tiers) · `s4_apply.py` + `s4_exec.py` (DRC-gated conversions)
· `s5_void.py` (RF void + unconnected).