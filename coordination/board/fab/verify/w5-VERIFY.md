# verify-w5 — adversarial verification of fab-readiness wave 5

Everything here is my own measurement, run on **copies** in this directory. No repo was written,
no branch touched, nothing committed, nothing spent.

| item | my instrument | receipt |
|---|---|---|
| span census | `v1_span_census.py` (KiCad python 9.0.7, `GetViaType` + `TopLayer`/`BottomLayer`) | `census_fanout7copy.json`, `census_composed.json` |
| Excellon census | `v2_drill_census.py` (own parser, drills vs G85 slots) | `drill_pkg7.json`, `drill_pkgfinal.json` |
| unconnected | `v3_unconnected.py` (`GetUnconnectedCount(False)`), `kicad-cli pcb drc` | `unconn_*.json`, `drc/*.json` |
| gates | own `.kicad_dru` (span, and the old diameter form) + the board's own `.kicad_pro` | `drcenv/span/`, `drcenv/diam/` |
| interference | `v4_dm_check.py`, `v6_dm_check2.py`, `v8_pushrod.py` (OCCT `BRepAlgoAPI_Common`) | `dm_check.json`, `dm_check2.json`, `pushrod_check.json` |
| power requirement | IPC-2221B arithmetic, re-derived | console in `REPORT` §4 |

Board hashes I worked from (copies):

```
372C1D525BEBF651F86CB90C007FE8CAF71A41F7E46E28669D7AE956ECFA9077  fanout3/work.kicad_pcb
372C1D525BEBF651F86CB90C007FE8CAF71A41F7E46E28669D7AE956ECFA9077  fanout2/da_main_rev_b_fanout7.kicad_pcb
5DBAE23888059E0B6D6F18DC3066924FB8194C5FD4DFA250186D3B024F6F73B6  composed
A26EEADAC0D085865B7FD1C912520521C2085EB49DC20A6E2CB795184E99A007  esc compacted
992570571DEBC473972999D043E098BD3A5D4477ACFCCD3D2518092027995DDD  esc original
```

---

## 1. HDI count — 15, confirmed three independent ways

`evidence/fab-da-fanout7/` **does not exist** (fab-da-package7 §1.1 says so); the artefact is
`fab-da-fanout3/work.kicad_pcb`, byte-identical to `fab-da-fanout2/da_main_rev_b_fanout7.kicad_pcb`.
The hash, not the path, is the identity.

```
vias total 336   by decl type {3:321, 1:14, 2:1}   (1=micro 2=blind/buried 3=through)
by span class {'through':321, 'blind':11, 'buried':4}
NON-THROUGH 15
  F.Cu  -> In1.Cu  drill 0.100  n=5     blind
  F.Cu  -> In2.Cu  drill 0.100  n=2     blind
  In1.Cu-> B.Cu    drill 0.100  n=1     blind
  In2.Cu-> B.Cu    drill 0.100  n=2     blind
  In2.Cu-> B.Cu    drill 0.300  n=1     blind   <- the one a diameter gate cannot see
  In1.Cu-> In2.Cu  drill 0.100  n=4     BURIED
old <0.2 mm diameter gate sees: 14
```

Three readings of the same 15: **span class 11 blind + 4 buried**, **depth 12 one-dielectric +
3 deeper**, **declared type 14 microvia + 1 blind**.

**BOARD CORRECTION (AGENT_BOARD.md:522, and the wave-5 brief's verified state): "11 micro + 4
blind by span" is a category error twice over.** "Microvia" is a drill/process class, not a span
class; by span the split is 11 blind and 4 **buried** (the four `In1.Cu → In2.Cu` vias touch no
outer face). The count 15 is right on all three readings; the label is not. `fanout3` §1's
"12 micro + 3 blind by depth" is a different, also-correct, split.

**Gate integrity finding.** With the board's own project file present, the span gate
(`A.Type == 'Via' && A.Via_Type != 'Through'`) yields **22 = 15 HDI signals + 7 pre-existing
`via_diameter`**, and the diameter gate yields **21 = 14 + 7**. My first diameter run reported only
7 because I had omitted `(version 1)` from the head of the `.kicad_dru`: **kicad-cli silently
ignores a rule file without the version line and the gate runs as a no-op.** A gate that "passes"
with only the baseline violations is not evidence; check the rule file fired.

## 2. Excellon census — sound, with one slip

```
file                               DRILLS  SLOTS   HITS
main_rev_b-NPTH.drl                     6      0      6
main_rev_b-PTH.drl                    339      4    343
main_rev_b-front-in1.drl                5      0      5   Plated,1,2,Blind
main_rev_b-front-in2.drl                2      0      2   Plated,1,3,Blind
main_rev_b-in1-back.drl                 1      0      1   Plated,2,4,Blind
main_rev_b-in1-in2.drl                  4      0      4   Plated,2,3,Buried
main_rev_b-in2-back.drl                 3      0      3   Plated,3,4,Blind
TOTAL                                 360      4    364
tools carrying slots and no drills: T5 (0.600 mm) x4
```

5 blind/buried files, **15 non-through holes, all drills, no slots** — three-plus lamination
stages. The stale package (`fab-da-package-final/package`) reads **362 + 4 = 366**, PTH
**332 + 4 = 336 hits**, **24** non-through: the brief's "24 holes, 4 of 336 PTH hits are G85 slots"
reproduces exactly from my parser.

**Slip.** `fab-da-package7/REPORT.md:166` lists "0.300 ×33" and the list sums to **359** against
its own total of 360. The missing hole is the **0.300 mm blind in `main_rev_b-in2-back.drl`** —
i.e. the diameter-keyed list drops exactly the hole that a diameter gate is blind to. Harmless to
the headline; it is the wave's own defect class in miniature.

## 3. Unconnected — the number attached to the ESC is the wrong board's

| board | pcbnew `GetUnconnectedCount(False)` | kicad-cli | cap? |
|---|---|---|---|
| drone-arm fanout7 | **0** | 0 | far below any cap — trustworthy |
| routed block 1 | **112** | 112 | below 499 — trustworthy |
| ESC original | **1,542** | 499 | **kicad-cli capped** |
| **ESC compacted** | **1,620** | 499 | **kicad-cli capped** |

kicad-cli prints **exactly 499 on two different boards**, and its JSON carries exactly
`len(unconnected_items) == 499` for both. Two different boards cannot have the same count: that is
the cap, proved structurally rather than asserted.

So the wave-5 brief's "ESC unconnected = 1,542 … 2.88 % routed" is the **original** board's figure.
The compacted placement it is attached to measures **1,620**, i.e. **compaction added 78
unconnected ratlines (+5.1 %)** and no wave-5 document reports that. The 19−4−2=13 pad-population
reconciliation in `esc-routable2` §1 is a population statement; it cannot account for +78 ratlines.

`/M1_BATN` attribution re-derived by me from `esc-routable2/block1/drc_routed.json`
(`unconnected_items`, 112 entries, net parsed from `description`): **62 on `/M1_BATN`**, then 6
`3V3A`, 3 `NRST`, 2 `BATP`, 1 each on PHASE_A/B/C. The claim holds and it is not a round number.

## 4. Power path — the requirement is right; the compaction's clearance is not

Re-derived from IPC-2221B external (k = 0.048, ΔT 20 K, 60 A, 0.14 mm = 5.512 mil):

```
A = (60/(0.048*20^0.44))^(1/0.725) = 1.9574 mm2
width on 0.14 mm  = 13.981 mm      per outer of two = 6.991 mm
width on 0.0525 mm (1.5 oz inner) = 37.284 mm each
```

So the unit's 13.981 / 6.991 pair reproduces exactly.

**The defect is upstream, in the compaction unit.** `esc-placement/REPORT.md:110` declares
"Current-carrying copper width at 4 oz — NOT the binding constraint", on two bases:

1. a requirement of "≥ 3.3–5.1 mm", obtained by **paralleling all four layers** — but the inners are
   1.5 oz and need **37.284 mm each**, so the two 4 oz outers must carry it (6.991 each);
2. "every phase column already has 11.56 mm of FET plus a 20 mm slot — 3.9× the requirement" — the
   **FET land width**, not the corridor between parts. `esc-placement` §2(a)'s own table gives
   **14.00 mm on one outer** at ΔT 20.

Measured corridor afterwards: F.Cu phase 1.50–3.50 mm, BATP 11.00 mm pads-only. My own scanline
instrument (`v7_corridor.py`) is **not** comparable to a maximin path bound — it finds a 30 mm free
gap because it needs no connectivity to the pads and ignores zone fills — so I do **not** claim an
independent corridor number. What I do claim: the pre-placement clearance was made against the wrong
geometry and the wrong layer-share assumption, and the one executed routing experiment failed on
exactly the net whose corridor measured 0.300 mm (62 of 112, §3).

## 5. Interference — every number I could re-measure reproduced, to ~1e-9

Own OCCT booleans on the delivered STEPs (`v4/v6/v8`):

| claim | source | my re-measurement |
|---|---|---|
| 8-pair sum | 1,255.303465563 | **1,255.303465563** (arithmetic) |
| genuine six | 1,250.769445 | **1,250.769445334** |
| artefact two | 4.534020 | **4.534020229** |
| elevon ↔ repo 42×72 R3 envelope | 593.069028163 | **593.069028161** (fused operand) |
| elevon ↔ pushrod, delivered | 2.267010111 | **2.267010111** |
| of which horn corner clip | 0.831215 | **0.831214937** (panel 1.633361895, 3 knuckles 0.0) |
| elevon ↔ pushrod, after station change | 2.005056961 | **2.005056961** |
| moved elevon ↔ cove-min wing | 0.000000000 | **0.0** |
| moved elevon ↔ relief-recut wing, no extension (control) | 2,290.930691819 | **2,290.930691819** |
| pushrod volume / bbox | 119.380521 = π·1²·38 | **119.380521**, bbox x −126…−124, y −15…23, z 115…117 |
| pushrod to its own servo mount | 6.000 mm, 0.000000 mm³ | **6.000 mm, 0.000000 mm³** |
| `wing_left_reliefrecut` and `wing_left_cove_min` import reversed | −1,353,582.304799 / −1,343,828.356231 | **both negative exactly**; repaired +1,353,582.304799 / +1,343,828.356231 |
| deltoid of §8.1 (a reversed solid lies) | 9,226.872345 on reversal | **9,226.872345** = the plate's own volume |

Two operands I had to get right, and both are the report's own lesson: `Common` against a **raw
5-solid compound returns 0.0** (my first run), and against a compound the pushrod pair reads
585.708 not 593.069 — **fuse first**. After fusing, every number matched.

The artefact call therefore **is** backed by volumetric evidence, and I re-derived the decisive
pieces myself: the part is a fixed Ø2×38 cylinder, 6.000 mm clear of the servo that must drive it
with **0.000000 mm³** contact, its only attachment a **0.831215 mm³** corner clip of the horn, and
it ends 21.6915 mm past the panel (23.000 − 1.3085, the panel's own y extent). It is not removed by
assertion; it is removed by measurement, and the report states the 4.010114 mm³ cost rather than
folding it away.

**What the "true" figure is.** As delivered: **8 pairs / 1,255.303466 mm³** = 6 genuine
(1,250.769445) + 2 artefact (4.534020). After the executed station change on copies: **2 pairs /
4.010114 mm³, 100 % artefact, genuine 0**. The zero is a copy state, not design intent — §9 says so
and so must any quotation of it.

## 6. Constraint violations

| constraint | verdict |
|---|---|
| NO HDI | **violated by the board, known**: 15 non-through vias remain; package7's drill set is HDI |
| ESC only 4 oz | **held** — unchanged, both ESC copies 0.14 mm outer |
| $60 cap | **held** — $0 spent this wave |
| ESC single-sided | **held and verified**: 687 footprints, **0 on B.Cu** on both boards (43 have a through-hole pad on B.Cu, which is not a placed part) |
| ESC compact | **achieved in area only** (370.119 cm², −24.73 %), voided by the 60 A corridor |
| BOARD CORRECTION lines | **missing**: `fab-dm-final` supersedes `AGENT_BOARD.md:548-556` (8 pairs / 1,255.3034 as the state) and offers a merge line in §11 instead of a `BOARD CORRECTION:` line; `esc-routable2` §7 refutes `AGENT_BOARD.md:1180-1181` without the token either |

## 7. Verdict

**MOSTLY_SOUND.** Every load-bearing number I could re-measure reproduced — 15 non-through vias,
360+4 drills+slots, 4.010114, 593.069028, 2,290.930692, the reversed wing, the 112 unconnected and
its 62 on BATN. Three defects to carry: (1) the ESC's quoted 1,542 belongs to the original board,
the compacted board is **1,620**; (2) `esc-placement` cleared the power path against FET land width
and a four-layer-parallel requirement, which is why the compaction is **UNSAFE**;
(3) package7's per-diameter list is off by one, dropping the blind 0.300 mm hole. The wave's own
verdicts (drone-arm not sendable, block not routable, compaction unsafe) are the honest ones.