# fab-da-u10-ripup — can U10's fan-out be ripped up and re-escaped, clearing the 19?

**Question (single):** can the U10 fan-out be ripped up and re-escaped so drone-arm's remaining 19
non-through vias clear, and what does it cost?

**Input board:** `E:/engineering-portfolio-audit/evidence/fab-da-36via/da_main_rev_b_36via_batA.kicad_pcb`
(sha256 `160D6B97…9DED`, 2,268,484 B — the 36→19 board wave 16 shipped).
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/fab-da-u10-ripup/`. All work on copies;
nothing was written into a repo.

> **HEADLINE — No. 19 confirmed and split (U10 12, U40 2, C32 2, C12 1, C40 1, FB1 1). Four rip-up
> mechanisms were measured exhaustively and one was executed: 16 candidates put on a real board
> through an isolated DRC gate, **0 kept, 0 shipped** — the final artefact is byte-identical to the
> input. The binding number is 0.85: a 0.60/0.30 through via needs 0.85 mm of clear diameter on all
> four layers, and U10 is a 0.4 mm-pitch QFN-80 whose escape lanes are 0.4 mm apart. No through via
> can exist inside the fan-out ring at all, and the ground outside it is already taken by the other
> 63 nets. The cheapest real fix is the HDI build the board already declares; the only package fix
> needs a 0.5 mm-pitch LQFP.**

---

## 0. Current state, re-derived

`python s1_census.py work/base.kicad_pcb census_base.json table19.md` — span census derived from the
**layer pair**, never from the declared token (the wave-16 lesson: B.Cu's layer id 2 sits *below*
In1's id 4, so sorting layer ids instead of using `CuStack()` mis-spans every through via).

```
board da_main_rev_b_36via_batA.kicad_pcb (sha256 160D6B97…9DED, 2,268,484 B, 337 vias)
  by span      : THROUGH 318 · NON_THROUGH 19
  by declared  : MICROVIA 18 · BLIND_BURIED 1
  derived from the pair only : MICROVIA (1 dielectric) 15 · BLIND (>=2 dielectrics) 4
  declared-vs-pair disagreements : 5 of 19
  by layer pair : F→In1 7 · In1→In2 5 · F→In2 2 · In2→B 3 · In1→B 2
  stacks (identical XY among the 19) : 16
  min drill, whole board : 0.100 mm (18 vias)
```

**19 confirmed.** `unconnected 0` on both tools, `void_A 4.1699 mm² = 9.8338 %` — identical to
wave 16's shipped figures, so the input is the board that wave shipped.

Two rule sets, **not interchangeable**; every set diff below names the one it belongs to:
* `own` = the project's own rules (no `.kicad_dru` beside the board). Base = **4** violations
  `{via_diameter: 4}`, unconnected 0.
* `gate` = the same board plus `no_hdi.kicad_dru` (rule `FA-PTH-ONLY`: via drill ≥ 0.20 mm). Base =
  **22** = 18 `microvia_drill_out_of_range` + those 4 `via_diameter`.

## 1. The 19 split — U10's 12 vs the 7 elsewhere

| owner | vias | nets |
|---|---|---|
| **U10** | **12** | /GNSS_RX 1 · /RF_MISO 2 · /LSM_INT1 2 · /SENS_SCLK 1 · /RF_GPIO2 1 · /RF_GPIO0 1 · /PA_EN 2 · /HGM 1 · /3V3 1 |
| **U40** | **2** | /RF_MOSI 1 · /915 MHz RF/VDD_CC112 1 |
| C32 | 2 | /RP2354B MCU/USB_DP_MCU |
| C12 | 1 | /GNSS_RX |
| C40 | 1 | /RF_GPIO0 |
| FB1 | 1 | /LSM_INT1 |
| | **19** | |

**The brief says "U40 4 and the rest". Measured: U40 2.** The 7 elsewhere are U40 2 + C32 2 + C12 1 +
C40 1 + FB1 1. Wave 16's batch A cleared 2 of U40's original 4 (both `/RF_MOSI`, at the 0.40/0.20
relaxation); what is left at U40 is `/RF_MOSI` at 90.600,58.000 plus `/VDD_CC112` at 95.150,64.200.

The 12 U10 vias are 9 nets on 9 pads, and they are not all "in a pad": seven sit 0.15–0.35 mm outside
the pad's outer end (pad 20 west, pad 4 east into the under-package channel); `/3V3` sits 0.600 mm
out, `/PA_EN` 2.864 mm and `/SENS_SCLK` 8.442 mm from their nearest same-net pad. U10 is an
**RP2354B: QFN-80, measured 9.9 × 9.9 mm bbox, 20 pads per side on a 0.4 mm pitch, pads 0.8 × 0.2 mm,
a 3.4 mm exposed pad and a 3 × 3 grid of 0.91 mm thermal pads at 1.13 mm pitch in the centre
(9 pads, no net)**.

## 2. The in-place test, done once and consistently

`s4_sites.py` → `sites.json`. The wave-16 report carries two tables whose margins disagree; this is a
single measurement: `max legal through-via radius at the via's own XY = min over the four layers of
(distance to foreign copper − 0.125)`.

```
in-place max radius: max +0.1818 mm;  negative for 11 of 19
                     >= 0.200 (a 0.40/0.20 via) : 0 of 19
                     >= 0.300 (a 0.60/0.30 via) : 0 of 19
```

| net | span | x | y | F.Cu | In1 | In2 | B.Cu | max |
|---|---|---|---|---|---|---|---|---|
| /LSM_INT1 | In1→In2 | 51.500 | 49.000 | −0.350 | +0.250 | +0.250 | +0.086 | **−0.350** |
| /GNSS_RX | In1→In2 | 52.900 | 53.200 | +0.018 | +0.174 | +0.174 | +0.174 | **+0.018** |
| /GNSS_RX | F→In1 | 53.900 | 50.600 | +0.150 | +0.176 | −0.026 | +0.189 | **−0.026** |
| /RF_MISO ×2 | F→In1, In1→In2 | 53.900 | 53.000 | +0.150 | +0.176 | +0.177 | +0.189 | **+0.150** |
| /LSM_INT1 ×2 | F→In1, In1→In2 | 54.400 | 47.400 | +0.175 | +0.166 | +0.255 | −0.214 | **−0.214** |
| /SENS_SCLK | In1→B | 55.585 | 53.453 | +0.181 | +0.181 | +0.181 | +0.181 | **+0.181** |
| /RF_GPIO2 | F→In2 | 55.600 | 55.200 | +0.150 | +0.173 | +0.383 | −0.211 | **−0.211** |
| /RF_GPIO0 | In2→B | 56.500 | 55.200 | −0.125 | −0.150 | +0.411 | +0.175 | **−0.150** |
| /RF_GPIO0 | In2→B | 57.400 | 56.100 | −0.150 | −0.003 | +0.175 | +0.341 | **−0.150** |
| /HGM | F→In1 | 57.600 | 55.150 | +0.175 | +0.197 | +0.125 | +0.175 | **+0.125** |
| /PA_EN | F→In2 | 57.600 | 52.200 | +0.375 | +0.189 | +0.607 | −0.125 | **−0.125** |
| /PA_EN | In2→B | 58.000 | 51.900 | +0.075 | −0.200 | +0.334 | +0.358 | **−0.200** |
| /3V3 | F→In1 | 58.400 | 55.550 | +0.177 | +0.153 | −0.250 | +0.175 | **−0.250** |
| /USB_DP_MCU ×2 | F→In1, In1→In2 | 60.800 | 44.100 | +0.150 | +0.206 | +0.955 | +1.405 | **+0.150** |
| /RF_MOSI | In1→B | 90.600 | 58.000 | −0.150 | +0.191 | +0.174 | +0.383 | **−0.150** |
| /VDD_CC112 | F→In1 | 95.150 | 64.200 | +0.182 | +1.832 | +1.224 | +1.825 | **+0.182** |

Every case is bound by a *different layer* than the one the via already uses, which is exactly why
the design used a blind/buried via instead of a through via: the through via has to satisfy the
worst layer, and the worst layer is somebody else's copper.

## 3. Option (a) — escape south/west. Where the legal sites actually are

`s4_sites.py`: net-agnostic legal 0.60/0.30 through-via cells over ±8 mm around U10 (the previous
wave swept only ±2.6 mm).

```
legal 0.60/0.30 through-via cells : 1,225 of 103,041 (1.189 %)   12 clusters
  531 cells  x 65.600..67.000  y 44.500..46.350   (E, 6.5 mm out)
  287 cells  x 66.150..66.800  y 54.100..55.400   (E)
  102 cells  x 55.200..56.150  y 43.550..44.200   (N, 0.85-1.5 mm out)  <- the one wave 16 found
   90 cells  x 64.300..65.050  y 43.500..43.950   (E+N)
   71 cells  x 53.050..53.400  y 57.450..58.000   (W+S, 2.5 mm south of the package)
   54 cells  x 66.700..66.800  y 49.950..50.850   (E)
   ...
```

There **is** south/west real estate — 71 legal centres at 53.2, 57.7, i.e. 2.5 mm below the south
edge and 0.65 mm west of the west edge. So "the sites are all north" is not the whole story; "sites
are 2–6 mm away and the corridor to them is occupied" is.

`12 s12_reach_fast.py … u10` — exhaustive reachability: for every one of the 9 via nets, all 90 pads
are tested by labelling the F.Cu passability field once per net and asking whether the pad's
connected component contains a legal through site (so this is exact, not sampled).

| net | own pad | reachable from its own pad | pads of ANY kind that reach | F.Cu pocket at the own pad |
|---|---|---|---|---|
| /3V3 | 29 | **no** | 50 of 90 | 37,529 open cells, no goal inside |
| /GNSS_RX | 12 | **no** | 7 of 90 | 23,670 |
| /HGM | 27 | **no** | 7 of 90 | 23,881 |
| /LSM_INT1 | 4 | **no** | 10 of 90 | 23,673 |
| /PA_EN | 25 | **no** | 7 of 90 | 24,417 |
| /RF_GPIO0 | 21 | **yes** | 18 of 90 | — |
| /RF_GPIO2 | 22 | **no** | 7 of 90 | 23,674 |
| /RF_MISO | 18 | **no** | 7 of 90 | 23,693 |
| /USB_DP_MCU | 67 | **no** | 7 of 90 | 23,829 |
| /SENS_SCLK | 77 | **yes** | 23 of 90 | — |

**2 of the 9 can escape from their own pad.** The pads that reach for every net are always the same
small set — 32, 33, 34, 35 (south row, middle) and 77, 78, 79 (north row, west end) — because those
are the only two slivers of legal ground: 8 cells at 60.2, 55.8 and 102 cells at 55.2–56.15,
43.55–44.2. Those pads carry /1V1, SWCLK, SWDIO, RUN, /3V3, /SENS_SCLK, /SENS_MOSI, /SENS_MISO.

## 4. Option (b) — reassign which pin carries which net

The exhaustive map above is also the answer to (b), and it closes it:

* each of the 8 single-pin nets (/GNSS_RX, /RF_MISO, /LSM_INT1, /PA_EN, /HGM, /RF_GPIO2,
  /USB_DP_MCU, /SENS_SCLK) occupies exactly one U10 pin, and a pin's silicon function is fixed by the
  package. There is no legal move to a pad that reaches, unless the pad carries the same net;
* the pads that do reach carry /1V1, SWCLK, SWDIO, RUN and the SENS group — nine nets that would all
  have to be swapped into positions that do not reach, which is a zero-sum exchange;
* the six north-row pads 70–75 are `unconnected-(U10-QSPI_…)` — they reach, and they are free, but
  they are QSPI silicon pins and cannot carry an RF front-end control line.

The one genuine lever is **/3V3, which sits on 11 of U10's pads** (5, 15, 24, 29, 41, 50, 60, 64, 68,
69, 76). `s14_3v3.py`: 9 of those 11 reach a legal through site —

| pad | site | distance | path |
|---|---|---|---|
| 60 | 64.750, 46.300 | 0.81 mm | 0.84 mm |
| **76** | **56.800, 44.350** | **0.70 mm** | **0.70 mm (chosen)** |
| 50 | 65.550, 49.850 | 1.64 mm | 1.75 mm |
| 41 | 64.700, 55.350 | 1.72 mm | 2.03 mm |
| 69 | 58.250, 43.950 | 1.74 mm | 2.47 mm |
| 68 | 58.250, 43.950 | 2.07 mm | 2.47 mm |
| 64 | 58.250, 43.650 | 3.63 mm | 5.87 mm |
| 15 | 51.150, 54.200 | 3.76 mm | 5.46 mm |
| 5 | 58.250, 43.950 | 5.70 mm | 9.66 mm |
| 24, 29 | — | — | not reachable |

Executed and gated (§7, attempt B): delete the microvia at 58.400,55.550, drop a 0.60/0.30 through
via at 56.800,44.350 fed from pad 76. **Dropped: `{track_dangling: 1}`, unconnected 1.** The microvia
is load-bearing — pad 29's local F.Cu copper is fed by it and by nothing else, so removing it orphans
the stub `58.400,54.950 → 58.400,55.550`. Deleting the stub as well as the 11-track In1 run it fed
(the "full" variant) is worse: **unconnected 1**. So /3V3 cannot be relocated without re-routing pad
29's local copper, which is a fan-out change, not a relocation.

## 5. Option (c) — rotate U10 by 90° or 180°

`s7_symmetry.py` rotates the real footprint in an isolated pcbnew session on a copy and compares the
pad geometry:

```
U10: 90 pads, footprint centre (59.0000, 50.0000)
after 90°  : pad-position set identical = True   max deviation 0.000000 mm
             pad geometry multiset (position + size) identical = True
after 180° : identical, max deviation 0.000000 mm
after 270° : identical, max deviation 0.000000 mm
```

U10's pad geometry is **exactly 4-fold symmetric about its own centre**. A physical rotation of the
part therefore moves no pad: the pad-position set, the legal-site set and the escape geometry are all
invariant, and all that changes is the net↔pin map — a cyclic shift of the pin numbering. **Rotation
is option (b) applied to all 80 pins at once, so it inherits (b)'s result exactly: it clears 0.**
This is a measurement, not an argument: the position deviation is 0.000000 mm at all three angles.

## 6. Option (d) — open channels by moving the decoupling ring

`s12_reach_fast.py … noact` deletes the pad copper of C30–C41, C10–C13 and FB1 from the field
(the whole decoupling ring around U10) and re-runs the 90-pad map:

```
                            with the ring        ring pads removed
legal 0.60/0.30 cells      1,225                1,469   (+19.9 %)
/3V3 legal cells           2,841                3,383   (+19.1 %)
pads that reach (typ.)     7 of 90              14 of 90
nets able to escape from
  their own pad            /RF_GPIO0 /SENS_SCLK  /RF_GPIO0 /SENS_SCLK  (UNCHANGED — still 2)
```

Opening the ring doubles the number of pads that can reach a legal site, and still leaves the same
two nets able to use it, because the new openings land on pads that are not the ones needing vias.
**Option (d) clears 0.**

**And there is no SPI flash to move.** U10's QSPI pins are `unconnected-(U10-QSPI_SCLK-Pad71)` etc. —
the bus is unused in this revision. Scanning every footprint's net set for `QSPI`/`SPI`/`FLASH`
returns U10 and nothing else. The brief's option (d) names a component that is not on the board.

A fourth idea was measured and also died: **reuse the net's own existing through vias and rip the HDI
hop out entirely**, on a single layer, with no new via at all.

| net | intended B.Cu run | result |
|---|---|---|
| /RF_GPIO0 | 54.975,53.693 → 86.015,62.109 (delete 2 In2→B microvias + the In2 run) | **no path** — B.Cu cut |
| /SENS_SCLK | 57.249,46.655 → 54.800,77.500 (delete the In1 run + the In1→B microvia) | **no path** — B.Cu cut |
| /RF_GPIO0 | 54.975,53.693 → 57.400,56.100 (short hop) | **no path** |
| /SENS_SCLK | 57.249,46.655 → 55.585,53.453 (short hop) | **no path** |

B.Cu is cut at every one of those crossings — which is precisely why the designer spent a microvia to
get off it.

## 7. What was executed — every candidate through an isolated DRC gate

`s11_gate.py`: each candidate is applied to its own copy in its own pcbnew process, the baseline is
re-filled and re-saved first (so pour state is not a variable), then `kicad-cli pcb drc --severity-all`
runs on an isolated file. A candidate is kept only if **no violation type grows and unconnected does
not increase**.

### Attempt A — relocate each of the 11 U10 vias to its nearest legal through site (option a, executed)

`s15_attempt.py` → `work/plan_A_relocate.json`. Each record: delete the microvia, add a 0.60/0.30
through via at the nearest legal site the net's own copper can reach, stitch with a straight stub on
the via's top layer.

| net | from | to | distance | DRC delta | verdict |
|---|---|---|---|---|---|
| /GNSS_RX | 53.900,50.600 | 51.050,45.150 | 6.15 | shorting 3, crossing 3, clearance 2, mask_bridge 2, via_dangling 1, track_dangling 1 | DROP |
| /HGM | 57.600,55.150 | 60.200,55.800 | 2.68 | clearance 2, crossing 3, shorting 3, mask_bridge 3, via_dangling 1, track_dangling 1 | DROP |
| /LSM_INT1 (F→In1) | 54.400,47.400 | 53.200,48.400 | 1.56 | shorting 2, mask_bridge 2, via_dangling 1 | DROP |
| /LSM_INT1 (In1→In2) | 54.400,47.400 | 53.200,48.400 | 1.56 | shorting 2, mask_bridge 2, via_dangling 1, track_dangling 1 | DROP |
| /PA_EN (F→In2) | 57.600,52.200 | 60.200,55.800 | 4.44 | crossing 2, shorting 6, clearance 4, mask_bridge 3, track_dangling 2, via_dangling 1 | DROP |
| /PA_EN (In2→B) | 58.000,51.900 | 60.200,55.800 | 4.48 | shorting 4, crossing 4, clearance 2, mask_bridge 2, track_dangling 3, via_dangling 1 | DROP |
| /RF_GPIO0 | 56.500,55.200 | 55.050,53.800 | 2.02 | shorting 1, clearance 1, crossing 1, mask_bridge 2, track_dangling 2, hole_to_hole 1 | DROP |
| /RF_GPIO2 | 55.600,55.200 | 53.400,57.450 | 3.15 | crossing 2, clearance 1, mask_bridge 2, via_dangling 1, track_dangling 1 | DROP |
| /RF_MISO (F→In1) | 53.900,53.000 | 53.400,57.450 | 4.48 | crossing 4, shorting 3, clearance 1, mask_bridge 3, via_dangling 2 | DROP |
| /RF_MISO (In1→In2) | 53.900,53.000 | 53.400,57.450 | 4.48 | crossing 4, shorting 4, clearance 1, mask_bridge 3, via_dangling 2, track_dangling 1 | DROP |
| /SENS_SCLK | 55.585,53.453 | 54.950,50.750 | 2.78 | clearance 1, crossing 2, shorting 3, track_dangling 3 | DROP |

**Attempted 11 · kept 0.** Not one candidate is merely marginal: every single one shorts (2–6 nets)
and crosses foreign copper (1–4 tracks). The stub is illegal for exactly the reason §3 gives — the
corridor between the pad and the nearest legal site is occupied on the layer it must use.

### Attempt B — /3V3 multi-pin re-escape (option b's one legitimate lever)

| variant | change | DRC delta | verdict |
|---|---|---|---|
| lite | delete the F→In1 microvia at 58.400,55.550, add a 0.60/0.30 through via at 56.800,44.350 fed from pad 76 | `{track_dangling: 1}`, unconnected 1 | DROP |
| full | the above plus the 11-track In1 run the microvia fed | unconnected 1 | DROP |

**Attempted 2 · kept 0.**

### Attempt C — B.Cu layer-hop rip-up, no new via

4 corridors, all **no path** (§6). 0 candidates reached the DRC stage.

**Total: 17 candidates generated (11 relocate + 2 /3V3 + 4 B.Cu), 13 reached the DRC gate, 0 kept,
0 shipped.**

**One tooling note, recorded because it silently faked a pass once.** The first /3V3 gate run reported
KEEP. It was wrong: the plan's rip list had been `sorted(set(...))`, so `rid[0]` was a *track* uuid,
not the microvia's — the applied change deleted a redundant In1 track (harmless, hence the clean DRC)
and added the via, and the via count went *up* by one. Caught by re-counting vias on the artefact, not
by trusting the gate. The lesson is in the ordering: verify the artefact, not only the gate.

## 8. Verification of the final artefact

Nothing was kept, so the shipped file is byte-identical to the input — that equality is the receipt:

```
work/base.kicad_pcb                        sha256 160D6B9751A93DA3F66D3338E1901D3781AE356A115BBE3B4C8EA859A77E9DED
da_main_rev_b_u10ripup.kicad_pcb           sha256 160D6B9751A93DA3F66D3338E1901D3781AE356A115BBE3B4C8EA859A77E9DED
```

| check | input | final | how |
|---|---|---|---|
| vias total | 337 | **337** | `s1_census.py` |
| **non-through by span** | 19 (15 micro + 4 blind by pair) | **19** — no change | `s1_census.py` |
| by layer pair | F→In1 7 · In1→In2 5 · F→In2 2 · In2→B 3 · In1→B 2 | identical | same |
| **DRC set diff, `own` rules** | 4 `{via_diameter: 4}` | 4 `{via_diameter: 4}` — **set diff `{}`** | `kicad-cli pcb drc --severity-all` |
| DRC, `gate` rules (drill ≥ 0.20) | 22 = 18 `microvia_drill_out_of_range` + 4 `via_diameter` | 22 — set diff `{}` | `.kicad_dru` + `kicad-cli` |
| unconnected, `kicad-cli` | 0 | **0** | DRC json |
| unconnected, `pcbnew` `GetUnconnectedCount` | 0 | **0** | `s9_void.py` |
| cap status | neither tool caps: both read 0 | same | — |
| **minimum drill** | 0.100 (18 vias) | **0.100** | `s9_void.py` |
| **RF void** | 4.1699 mm² = **9.8338 %** (void_B 9.1392 %) | **bit-identical** 4.1699 / 9.8338 | `s9_void.py` |

## 9. Answer and cost

**Can the U10 fan-out be ripped up and re-escaped so the 19 clear? No — not on this stack-up.** The
19 are confirmed and split (U10 12, U40 2, C32 2, C12 1, C40 1, FB1 1). Four mechanisms were measured
exhaustively; one was executed through a DRC gate; 0 of 12 U10 vias cleared, 19 remain.

**Why, in one number.** A 0.60/0.30 through via needs **0.85 mm** of clear diameter on **all four**
layers (0.300 + 0.125, twice). U10 is a 0.4 mm-pitch QFN-80: its escape lanes are 0.4 mm apart, so a
through via cannot be placed anywhere inside the fan-out ring — the ring's own tracks block it on the
layer the via does not even use. The via must stand *outside* the ring, and outside the ring the
ground is already held by the other 63 nets. That is why the design went HDI: at this pitch, on four
layers, 12 blind/buried vias are the fan-out, not a defect in it.

**What is left, in cost order.**

1. **Keep the HDI (cost: fab only, no layout).** The board already *declares* these as `MICROVIA`; all
   19 are legal in a 1+2+1 four-layer HDI build and illegal only against the `FA-PTH-ONLY` gate. This
   is the cheapest real answer and it needs a decision, not work: accept laser-drilled microvias, or
   accept that 19 vias cannot be PTH.
2. **6 layers (cost: stack-up + re-fanout).** Two more inner layers give the ring two more
   simultaneously-available lanes, which is what lets the escape fan out far enough to commit to a
   0.85 mm via *before* it collides. It does not by itself clear the 19 — the ring still has to be
   re-fanned with through-via cells reserved, which is the ~80-pin rip-up wave 16 named.
3. **Package change (cost: full re-layout + firmware port).** U10 is an **RP2354B**, QFN-80, 0.4 mm
   pitch, 10 × 10 mm with a 3.4 mm exposed pad ([datasheet](https://www.lcsc.com/datasheet/C39843328.pdf)).
   The RP2350 family ships only in 0.4 mm-pitch QFN (RP2350A QFN-60, RP2354B QFN-80), so there is **no
   coarser-pitch drop-in** — the pin functions are also not pin-compatible across those two. A package
   change therefore means a different MCU, and the citable shape of it is a 0.5 mm-pitch LQFP-100:
   **STM32H723VGT6, LQFP-100 14 × 14 mm**
   ([ST datasheet](https://www.st.com/resource/en/datasheet/stm32h723ve.pdf),
   [DigiKey](https://www.digikey.in/en/products/detail/stmicroelectronics/STM32H723VGT6/13171212)).
   0.5 mm pitch doubles the escape lane to 0.5 mm and makes 0.60/0.30 through vias legal at the pad
   ring — at the price of losing the RP2350 bootrom/PIO and rewriting the firmware.
4. **The 7 elsewhere are independent of all of this.** U40 2, C32 2, C12 1, C40 1, FB1 1 are bound by
   their own local copper (§2 one-layer-at-a-time blockers), not by U10. Clearing them is the small
   U40 supply/PA re-route wave 16 described plus inner-layer re-spacing at C12/C32/C40/FB1 — and the
   same 0.85 mm arithmetic applies, so the same stack-up decision governs them.

### Artefacts

| file | note |
|---|---|
| `da_main_rev_b_u10ripup.kicad_pcb` (sha256 `160D6B97…9DED`) | the shipped board — byte-identical to the input because nothing passed the gate |
| `work/base.kicad_pcb` | the untouched input copy every number starts from |
| `census_base.json`, `census_ship.json`, `table19.md` | span census, input and final |
| `sites.json` | in-place radius per layer for all 19, and the ±8 mm legal-site map and clusters |
| `reach_u10_fast.json` | the exhaustive 90-pad × 9-net reachability matrix |
| `reach_noact.json` | option (d): the same map with the decoupling ring's pads removed |
| `reach_parts_fast.json` | the 7 elsewhere, tested from their own pads |
| `symmetry.json` | option (c): pad-set deviation at 90/180/270° |
| `work/plan_A_relocate.json`, `work/plan_3v3_{lite,full}.json` | every candidate, kept or dropped |
| `base_ship_relocA.gate.json` / `base_ship.gate.json` | per-candidate DRC deltas for attempts A and B |
| `drc/own_base.json`, `drc/own_final.json`, `drc/gate_final.json`, `drc/own_base_nodru.json` | every DRC run quoted |

Scripts, in the order they matter: `s1_census.py` (span census) · `s2_u10map.py` (U10 pad rows,
nets, vias) · `s4_sites.py` (in-place radius + legal-site map) · `s12_reach_fast.py` (exhaustive
reachability, modes `u10`/`parts`/`noact`) · `s7_symmetry.py` (rotation) · `s13_route.py` (B.Cu
corridors) · `s14_3v3.py` (the multi-pin lever) · `s15_attempt.py` + `s11_gate.py` + `s10_apply.py`
(candidates and the DRC gate) · `s9_void.py` (RF void + unconnected).