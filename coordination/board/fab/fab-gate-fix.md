# The no-HDI gate was diameter-only. Corrected counts: 36 / 24 / 18, not 33 / 23 / 17.

**Wave 4 · fab-readiness · `evidence/fab-gate-fix/`**
Every number below is reproduced by `run_all.py` and `verify_gate.py` in this directory.

---

## 1. The defect, stated exactly

The programme's gate is a KiCad custom rule, `evidence/fab-da-vias/no_hdi.kicad_dru:13-16`:

```
(rule "FA-PTH-ONLY: via drill >= 0.20 mm mechanical (no laser microvia)"
	(constraint hole_size (min 0.2mm))
	(condition "A.Type == 'Via'")
)
```

It tests one property: **drill diameter**. `AGENT_BOARD.md:32` and `:721-728` ban HDI, not
small holes. Those are different predicates and they do not coincide:

| via | blind/buried? | needs sequential lamination? | old gate | correct |
|---|---|---|---|---|
| 0.100 mm F.Cu→In1.Cu | blind | yes | flags | flags |
| **0.300 mm In2.Cu→B.Cu** | **blind** | **yes** | **passes clean** | **must flag** |
| 0.300 mm F.Cu→B.Cu | no | no | passes | passes |

A **0.300 mm blind via still requires sequential lamination**, which is HDI process regardless of
its diameter. Measured cost of the blind spot: **3 / 1 / 1 vias**, all at 0.300 mm.

The correct predicate is **SPAN**, and it is available from the board itself:
`PCB_VIA.GetViaType()` (THROUGH / BLIND_BURIED / MICROVIA) plus `TopLayer()`/`BottomLayer()`.

---

## 2. The classifier — `via_span_classifier.py`

```
"C:/Program Files/KiCad/9.0/bin/python.exe" via_span_classifier.py <command> ... [--out DIR] [--tag NAME] [--layers N] [--quiet]
```

| command | what it does |
|---|---|
| `board <a.kicad_pcb> [...]` | full span census: per-class counts, per-class drill histogram, every non-through via listed with drill / layer pair / span / net / XY. Writes `<stem>.span_census.json`. |
| `drill <dir-or-glob> [...]` | Excellon census file by file from `TF.FileFunction`: plating, layer pair, PTH / NPTH / Blind / Buried, tool table, hits per diameter. Writes `<stem>.drill_census.json`. |
| `check <board>` | the shippable gate. Exit **0** = no HDI via, **1** = HDI vias present, **2** = board unreadable. One line per offending via. |
| `oldgate <board> [...]` | prints the diameter-only count beside the true count, so the miss is a measured delta. |

Classification rules, in order — **drill value is recorded as an attribute and never decides the class**:

1. `THROUGH` — spans the full copper stack (F.Cu → B.Cu on a 4-layer board).
2. `MICRO` — declared `VIATYPE_MICROVIA` **and** span = exactly 1 dielectric.
3. `BLIND` — not through, one end on an outer copper layer.
4. `BURIED` — not through, both ends on inner copper.
5. `UNKNOWN` — a layer outside the board's own copper stack; never silently passes.

`HDI = BLIND + BURIED + MICRO`. Copper order comes from the board (`GetCopperLayerCount`), not from
a hard-coded list.

**Trap encoded in the script:** `PCB_VIA.GetWidth()` with no layer argument trips a wx assert on
Windows and **blocks the process in a modal dialog** (hit during development, `work/probe_drc_coverage.py`
documents it). Always pass a layer — the script uses `GetWidth(pcbnew.F_Cu)`.

---

## 3. True census, all four drone-arm artefacts

Boards loaded as copies in `work/`; sha256 recorded in `receipt.json` and matched against the
programme's own citations (composed `5DBAE238…6F73B6`, fanout5 `E65F0B2E…A5843A`).

### 3.1 Original board — `base.kicad_pcb` (341 vias)

| class | count | drill histogram (mm) | layer pairs |
|---|---|---|---|
| THROUGH | **305** | 0.300 ×24, 0.350 ×281 | F.Cu→B.Cu |
| BLIND | **10** | 0.100 ×7, **0.300 ×3** | F.Cu→In2.Cu ×3 (0.1), In1.Cu→B.Cu ×4 (0.1), **In2.Cu→B.Cu ×3 (0.3)** |
| BURIED | **0** | — | (the 5 holes a fab would call buried are declared MICROVIA, In1→In2) |
| MICRO | **26** | 0.100 ×26 | F.Cu→In1.Cu ×14, In1.Cu→In2.Cu ×10, In2.Cu→B.Cu ×2 |
| **HDI** | **36** | **0.100 ×33, 0.300 ×3** | |

### 3.2 Consolidated composed board — `da_main_rev_b_composed.kicad_pcb` (338 vias)

| class | count | drill histogram (mm) | layer pairs |
|---|---|---|---|
| THROUGH | **314** | 0.300 ×33, 0.350 ×281 | F.Cu→B.Cu |
| BLIND | **6** | 0.100 ×5, **0.300 ×1** | F.Cu→In2.Cu ×2, In1.Cu→B.Cu ×3, **In2.Cu→B.Cu ×1 (0.3)** |
| BURIED | **0** | — | |
| MICRO | **18** | 0.100 ×18 | F.Cu→In1.Cu ×11, In1.Cu→In2.Cu ×5, In2.Cu→B.Cu ×2 |
| **HDI** | **24** | **0.100 ×23, 0.300 ×1** | |

### 3.3 fanout5 — `da_main_rev_b_fanout5.kicad_pcb` (337 vias)

| class | count | drill histogram (mm) | layer pairs |
|---|---|---|---|
| THROUGH | **319** | 0.200 ×5, 0.300 ×33, 0.350 ×281 | F.Cu→B.Cu |
| BLIND | **5** | 0.100 ×4, **0.300 ×1** | F.Cu→In2.Cu ×2, In1.Cu→B.Cu ×2, **In2.Cu→B.Cu ×1 (0.3)** |
| BURIED | **0** | — | |
| MICRO | **13** | 0.100 ×13 | F.Cu→In1.Cu ×6, In1.Cu→In2.Cu ×5, In2.Cu→B.Cu ×2 |
| **HDI** | **18** | **0.100 ×17, 0.300 ×1** | |

The five 0.200 mm through vias are fan-out5's own work (0.1 mm microvia → 0.2 mm through), and the
through population moved 314 → 319 accordingly.

**Two independent counting conventions, same total.** By **declared type**, fanout5 is
**17 MICROVIA + 1 BLIND_BURIED = 18**, which is the split the verifier reported. By **span**, it is
13 one-dielectric microvias + 4 vias declared MICROVIA but spanning **two** dielectrics + 1 blind.
The 4 (5 on composed, 7 on base) are listed under `inconsistencies` in the census JSON: KiCad allows
a MICROVIA flag on a span-2 via, which is not a legal microvia geometry. Both conventions are HDI, so
**the totals are 18 / 24 / 36 either way** — but a tool that counts the type flag alone will call a
span-2 blind via a "microvia", and a tool that counts drill diameter alone will miss it entirely.

### 3.4 The drill package — `evidence/fab-da-package-final/package/` (7 Excellon files)

Parsed from `TF.FileFunction`, which is the authority. **`TA.AperFunction` is a trap:** every
non-through file declares `TA.AperFunction,Plated,Buried,ViaDrill` — including the *Blind* ones
(`main_rev_b-in2-back.drl:9` says `Buried` while `:6` correctly says `Plated,3,4,Blind`). A parser
keyed on the aperture function would label all five files "buried".

| file | TF.FileFunction | span | holes | per diameter (mm) |
|---|---|---|---|---|
| `main_rev_b-NPTH.drl` | `NonPlated,1,4,NPTH` | 3 | 6 | 0.65 ×2, 4.30 ×4 |
| `main_rev_b-PTH.drl` | `Plated,1,4,PTH` | 3 | 336 | 0.20 ×18, 0.30 ×33, 0.35 ×281, 0.60 ×4 |
| `main_rev_b-front-in1.drl` | `Plated,1,2,**Blind**` | 1 | **11** | 0.10 ×11 |
| `main_rev_b-front-in2.drl` | `Plated,1,3,**Blind**` | 2 | **2** | 0.10 ×2 |
| `main_rev_b-in1-back.drl` | `Plated,2,4,**Blind**` | 2 | **3** | 0.10 ×3 |
| `main_rev_b-in1-in2.drl` | `Plated,2,3,**Buried**` | 1 | **5** | 0.10 ×5 |
| `main_rev_b-in2-back.drl` | `Plated,3,4,**Blind**` | 1 | **3** | 0.10 ×2, **0.30 ×1** |

**Confirmed as asked: 5 blind/buried files carrying 24 holes = 23 × 0.100 mm + 1 × 0.300 mm.**
The other two files are the through set (PTH + NPTH). All 366 drill hits = 336 PTH + 6 NPTH + 24.

**Board ↔ Excellon agree hole-for-hole, per layer pair** (not just in total):

| board | 1-2 | 1-3 | 2-4 | 2-3 | 3-4 | Σ |
|---|---|---|---|---|---|---|
| base (drill set `work/drill_pkg_repro`) | 14 | 3 | 4 | 10 | 5 (2×0.1 + **3×0.3**) | **36** |
| composed (`package/`, `consolidate/drill/`) | 11 | 2 | 3 | 5 | 3 (2×0.1 + **1×0.3**) | **24** |
| fanout5 (`fanout/drill/`) | 6 | 2 | 2 | 5 | 3 (2×0.1 + **1×0.3**) | **18** |

Every pair matches the board-side census exactly. The original board's own export carries **36**
HDI holes (33 × 0.100 + **3 × 0.300**) — the package in `fab-da-package-final` carries 24 because it
was built from the composed board.

---

## 4. Corrected HDI counts, and how far the old gate was off

The old gate's number was measured here, not quoted: `kicad-cli pcb drc` with
`no_hdi.kicad_dru` staged beside each board (`drc/oldgate_*.json`, `drc/gate_verify/*/drc_oldgate.json`).

| artefact | old gate (diameter only) | **corrected (span)** | missed | missed diameters | under-count |
|---|---|---|---|---|---|
| original `base.kicad_pcb` | 33 | **36** | **3** | 0.300 ×3 | **8.33 %** |
| composed `.kicad_pcb` | 23 | **24** | **1** | 0.300 ×1 | 4.17 % |
| fanout5 `.kicad_pcb` | 17 | **18** | **1** | 0.300 ×1 | 5.56 % |
| package drill files | (never seen by the gate) | **24 holes in 5 HDI files** | — | 0.300 ×1 | — |

**The number every later claim must use: drone-arm main rev_b has 24 non-through vias — 23 at
0.100 mm and 1 at 0.300 mm — and the gate reports 23. Fan-out took it from 36 to 24, not from 23
to 17.**

Where the programme's published figures stand:

| published | verdict |
|---|---|
| `AGENT_BOARD.md:460` "no-HDI gate **23 → 17**" | **superseded: 24 → 18.** The delta of −6 is right; both endpoints were one low. |
| `AGENT_BOARD.md:628` "minimum drill 0.100 mm — still HDI. 23 microvias + 1 blind" | **superseded: 17 microvias + 1 blind = 18** on fanout5; 23 of the count were already the *diameter* set. |
| `AGENT_BOARD.md:498` package "5 blind/buried carrying 24 non-through holes, 23 at 0.100 mm" | **confirmed exactly**, and it is the one place the count was already right — because it came from the drill files, not the gate. |
| `AGENT_BOARD.md:629` via census "0.100×23, 0.300×34, 0.350×281; non-through 24" | **confirmed exactly** (pcbnew census, not the gate). |
| `AGENT_BOARD.md:666` "36 non-through vias, 33 at 0.100 mm" | **confirmed exactly** — the board line knew 36 while the gate said 33. |

So the defect did not corrupt every number: wherever a count came from `pcbnew` or from the drill
files it is sound. It corrupted **every count that came from the gate**, which is the number quoted in
the fan-out progression and in the orderable-state table.

---

## 5. Two further findings the fix surfaced

### 5.1 The DRC gate *can* express span — `no_hdi_span.kicad_dru`

`A.Via_Type` **is** available in the KiCad 9 DRC expression language, with values `'Through'`,
`'Blind/buried'`, `'Micro'`. Probed on the base board (`drc/dru_probe/`):

| probe | rule | violations | truth |
|---|---|---|---|
| `min 0.4mm`, `A.Via_Type == 'Through'` | selects through vias | 199 → **capped, see 5.2** | 305 |
| `min 0.4mm`, `A.Via_Type == 'Blind/buried'` | | **3** | 3 |
| `min 0.4mm`, `A.Via_Type == 'Micro'` | | **33** | 33 |
| `min 0.4mm`, `A.Via_Type != 'Through'` | | **36** | **36** |

The shipped gate is `no_hdi_span.kicad_dru`, and `verify_gate.py` proves it against the pcbnew census:

| board | span census | gate | old gate | verdict |
|---|---|---|---|---|
| base | 36 | **36** | 33 | AGREE |
| composed | 24 | **24** | 23 | AGREE |
| fanout5 | 18 | **18** (+5 unrelated `via_diameter`) | 17 | AGREE |

Three caveats, all written into the gate file:
- A DRC rule fires only when its **constraint** is violated; the condition only selects items. There
  is no `disallow` that works here — `(constraint disallow)` was silently ignored (0 violations on a
  board with 36). So selected vias are asked to satisfy `hole_size (max 0.05mm)`, a **tripwire**, not
  a process number. The gate makes no claim about any legal diameter.
- If a future KiCad drops `A.Via_Type`, the condition matches nothing and the gate **silently reports
  zero**. That is the exact failure class this wave exists to end, so **the pcbnew classifier is the
  authority** and the `.dru` is the cheap pre-fab alarm; `verify_gate.py` is what keeps them honest.
- The gate cannot see the drill **files**. A package can carry stale blind files under a clean board —
  `via_span_classifier.py drill <dir>` covers that, and that is how the 24-hole figure was caught.

### 5.2 Custom-rule violations are truncated at **199 per type** — a programme-wide hazard

While validating that the gate counts *all* vias, a rule that must fail on **every** via
(`hole_size (max 0.05mm)`, `A.Type == 'Via'`) reported **232 of 341** vias on the original board. The
shortfall is not the via census — it reproduces as a **ceiling of 199** on four independent runs:

| run (file under `drc/dru_probe/`) | candidates | reported |
|---|---|---|
| base, `hole_size (max 0.05mm)` — `out_R0_all_vias.json` | 341 | `drill_out_of_range` **199** + `microvia…` 33 |
| base, `hole_size (min 0.352mm)` — `out_S1_base_min352.json` | 341 | **199** + 33 |
| base, `annular_width (min 0.5mm)` — `out_T1_annular.json` | 341 | `annular_width` **199** |
| composed, `hole_size (max 0.05mm)` — `out_T2_composed.json` | 338 | **199** + 23 |
| composed, `annular_width` — `out_ann_probeC.json` | 338 | **199** |
| fanout5, `hole_size (max 0.05mm)` — `out_S3_fanout5_max005.json` | 337 | **199** + 17 (+5 unrelated `via_diameter` = 221) |
| fanout5, `annular_width` — `out_ann_probe5.json` | 337 | **199** (+5 unrelated `via_diameter` = 204) |

Built-in checks are **not** limited this way — the ESC's 4 oz rule set reports **414 clearance**
violations (`drc/dru_probe/esc4oz/`, total **523**, unconnected **499**, both reproducing the
programme's published figures). So the ceiling applies to **custom-rule** violations, per type.

Consequence: **any custom-rule violation count at or near 199 in this programme is a truncation, not
a total.** The counts this assignment depends on are 36 / 24 / 18, far below the ceiling, so they are
exact — and that is a second, independent reason the pcbnew census must be the authority for counting
whenever a custom rule is involved.

### 5.3 HDI is drone-arm-only, now checked with the corrected tool

| board | vias | THROUGH | BLIND | BURIED | MICRO | HDI | drills |
|---|---|---|---|---|---|---|---|
| Code-SDR V2 | 1085 | **1085** | 0 | 0 | **0** | **0** | 0.20 ×983, 0.25 ×89, 0.40 ×13 |
| ESC rev_b | 1990 | **1990** | 0 | 0 | **0** | **0** | 0.30 ×16, 0.35 ×12, 0.40 ×1962 |

This independently confirms `AGENT_BOARD.md:725-727` — Code-SDR has **zero** microvias and all 1085
vias are standard plated-through at 0.200 / 0.250 / 0.400 mm. The corrected gate changes nothing on
the other two boards; it is a drone-arm finding.

---

## 6. Reproduce

```
cd E:/engineering-portfolio-audit/evidence/fab-gate-fix
"C:/Program Files/KiCad/9.0/bin/python.exe" run_all.py       # census + drill + old-gate DRC + cross-checks
"C:/Program Files/KiCad/9.0/bin/python.exe" verify_gate.py   # shipped .dru vs pcbnew census
```

`run_all.py` fails if the board census and the drill set disagree. Current state: **all cross-parser
checks PASS** (`receipt.json: all_checks_pass = true`, `census/gate_verify.json: all_agree = true`).

### Artefacts

| path | what |
|---|---|
| `via_span_classifier.py` | the classifier / gate (documented CLI above) |
| `no_hdi_span.kicad_dru` | corrected KiCad gate, span-based, with caveats in-file |
| `verify_gate.py` | proves the `.dru` against the pcbnew census |
| `run_all.py` | reproduces every number in this report |
| `receipt.json` | board sha256, drill sets, DRC counts, cross-check verdicts |
| `census/*.span_census.json` | per-board census incl. every non-through via with net and XY |
| `census/*.drill_census.json` | per-drill-set file-by-file census |
| `census/gate_verify.json` | gate vs truth |
| `drc/oldgate_*.json` | the old gate's own output, per board |
| `drc/gate_verify/<board>/` | staged copies + both DRC runs |
| `drc/dru_probe/` | the `A.Via_Type` probe series and the 199-ceiling evidence |
| `work/` | board copies, `run_all.log`, `verify_gate.log`, `drc_coverage.json` |

### Status lines for `AGENT_BOARD.md`

- drone-arm main rev_b: **24 non-through vias — 23 × 0.100 mm + 1 × 0.300 mm** (was published as 23).
  fanout5: **18** — 17 microvia + 1 blind (was published as 17).
- The no-HDI gate is now **span-based** and agrees with an independent `pcbnew` census on all three
  boards; the old diameter-only gate under-counted by 3 / 1 / 1 vias, all at 0.300 mm.
- `kicad-cli` truncates **custom-rule** violations at **199 per type**; built-in clearance checks are
  not truncated (ESC 4 oz: 414 clearance, 523 total). Counts at 199 are not totals.

### Scope note

I re-ran the corrected classifier on the three drone-arm artefacts, the drill sets that exist, and the
two other boards above. Any other board, or any DRC-derived number elsewhere in the programme, still
has to be re-run to be believed — the tool and the 199 ceiling are the two reasons to do it.