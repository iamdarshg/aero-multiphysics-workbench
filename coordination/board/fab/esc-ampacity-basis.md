# ESC rev_b — the ampacity constant k per layer, and every current path recomputed

**Unit:** `esc-ampacity-basis` · Assignment: settle whether IPC-2221's k = 0.048 is external-only and
k = 0.024 internal-only, what IPC-2152 changed, and what happens to every ESC current path when the
correct k is applied per layer. This decides whether the battery rail passes at all.

**Host:** KiCad 9.0.7; CPython 3.12 for analysis. **Write scope:** this directory only; the board of
record was read from copies in prior evidence units, nothing written to a repo. No commit, push or
reset.

> **STATUS: COMPLETE.** Skeleton was written first (`REPORT.md` at 09:33), then appended section by
> section as each step finished. Controls pass (C1–C6, §6).

---

## 0. The answer

| question | answer |
|---|---|
| **k for F.Cu / B.Cu** (0.140 mm, 4 oz, external) | **0.048** — confirmed, IPC-2221 §6.2 external |
| **k for In1 / In2** (0.0525 mm, 1.5 oz, internal) | **0.024** — confirmed, IPC-2221 §6.2 internal |
| **k for a via barrel** | **No k exists in IPC-2221** (it gives no via formula). Conservative convention **0.024** (buried copper); common estimate **0.048** (external). IPC-2152 has a via appendix but no public number. |
| **IPC-2152 changed** | 2009 chart + correction-factor method: copper weight, board thickness, laminate, **nearby planes**, environment; appendix on vias/conductor-via-plane/microvias. No closed form. IPC lists it "No Longer Maintained". |
| **BATP true capacity on In1** | **Not 49.7 A.** Its min-cut is **100 % barrels**, not In1 copper: **24.83 A** at the internal k (one-area rule) to **72.0 A** (per-via summation). The 49.67 A was **0.048 applied to a buried barrel cut** — the arithmetic the owner suspected. |
| **rail verdict** | **The earlier PASS is withdrawn: not established.** On the confirmed internal k the conservative floor **FAILS 40 A** — BATP **24.83 A (0.62×)**, BATN **29.55 A (0.74×)**. Phase **47.12 A PASS**, BATP_IN **47.74 A PASS**. |
| **what the fix requires** | Placement, not a re-pour: reserve a **planar external 4 oz corridor 7.99 mm per rail** at 40 A (8.97 mm at 43.5 A) and **6.63 mm per phase** (F.Cu∥In2). The widest clear F.Cu channel measured is **2.75 mm** (3.25 power-first) — a re-placement. |

**The one-sentence correction:** the k convention is real, but the prior error is not "In1 evaluated
at 0.048"; it is "a 100 % **barrel** cut evaluated at the external constant". BATP_IN's 47.74 A is
genuine external F.Cu and stands. BATP's 49.67 A does not.

---

## 1. The authoritative basis

### 1.1 The closed form and its units

IPC-2221 (Generic Standard on Printed Board Design) §6.2 gives current-carrying capacity as charts
(Figures 6-4 external, 6-5 internal). The form every calculator uses is a curve fit to those charts:

```
A[mil²] = ( I / (k · ΔT^0.44) )^(1/0.725)          I in A, ΔT in °C, A in mil²
I[A]    = k · ΔT^0.44 · (A[mil²])^0.725
```

- **k = 0.048 for external conductors** (outer layer, exposed to air).
- **k = 0.024 for internal conductors** (buried in laminate, no direct air cooling).

Because I ∝ k, an internal conductor of identical geometry is rated for **exactly half** the current;
equivalently, the same current needs **2^(1/0.725) = 2.60×** the cross-section. That 2.60× is the
number quoted by Standard Clarity as "about 2.6 times the cross-sectional area"; the "factor of two"
in the brief is the current ratio, and both are the same fact.

Sources, in order of authority:

1. **IPC-2221C**, *Generic Standard on Printed Board Design* — §6.2, current-carrying charts:
   <https://shop.ipc.org/ipc-2221/ipc-2221-standard-only/Revision-c/english>
2. **Volteq, "IPC-2221 PCB Trace Width Explained"** — states the formula, units, and the
   0.048/0.024 split explicitly: <https://volteq.io/guides/ipc-2221>
3. **Standard Clarity, "IPC-2221 vs IPC-2152"** — the split, the 2.6× area consequence, and the
   warning that the internal coefficient is a historical fit, not a universal thermal rule:
   <https://standardclarity.com/guides/ipc-2221-vs-ipc-2152/>
4. **Cadence, "IPC-2152 vs IPC-2221"** — "k = 0.048 for external copper, and k = 0.024 for internal
   copper, both assuming 1 oz"; the formula was developed for a single board type and a single copper
   weight: <https://resources.system-analysis.cadence.com/blog/ipc-2152-vs-ipc-2221-which-to-use-for-pcb-thermal-analysis>
5. **TraceWidthCalculator, "IPC-2221 vs IPC-2152"** — the comparison table used in §2:
   <https://tracewidthcalculator.com/blog/ipc-2221-vs-ipc-2152-pcb-standards/>

The convention is therefore **confirmed**: external 0.048, internal 0.024. The formula is a fit to
the standard's charts, not a first-principles thermal model; the charts are the authority and they are
for **traces**, not vias.

### 1.2 What the standard does *not* define: the via barrel

IPC-2221 gives **no via formula**. Two public sources state this and take opposite-but-labelled
positions on the barrel constant:

- **TraceWidthCalculator's via calculator** says: *"IPC-2221 itself gives no via formula"* and applies
  the trace power law with **k = 0.048** to the barrel cross-section *"as a rough estimate"*:
  <https://tracewidthcalculator.com/via-current-calculator/>
- **QueenEMS, "PCB Via Current Capacity"** treats the barrel as an **internal** conductor (k = 0.024)
  and calls it *"the conservative IPC-2221 method"*; it also notes *"IPC-2152 covers vias but
  publishes no single amp value for them"*:
  <https://www.queenems.com/blog/pcb-via-current-capacity/>

So there are two live conventions, and **the standard does not adjudicate between them**. The prior
programme used 0.048 for the barrel cuts and treated the choice as immaterial (`esc-rail-repour`
A3: *"the measured cuts are on barrels (k = 0.048) so the verdict does not ride on it"*). That is the
error: the entire rail verdict rides on exactly this choice.

### 1.3 The instrument controls

`01_k_basis.py` refuses to print the table unless it reproduces six hand-checkable values first. It
does (§6). Three are independent published worked examples (10 mil/1 oz/10 K → 0.88 A; 5 A/10 K/1 oz
external → 110 mil; internal → 280 mil), three are the programme's own settled IPC-2221 figures
(13.981 mm, 8.972 mm, 62.244 mm). The residuals are ≤ 1.74 %.

---

## 2. What IPC-2152 changed

IPC-2152, *Standard for Determining Current-Carrying Capacity in Printed Board Design* (2009, 97
pages), replaced the IPC-2221 charts as IPC's current-capacity method:
<https://webstore.ansi.org/standards/ipc/ipc21522009>

| | IPC-2221 | IPC-2152 |
|---|---|---|
| Method | charts + one empirical formula | charts **plus correction factors** |
| Inputs | current, ΔT, copper cross-section | above + copper weight, board thickness, laminate, **plane proximity**, environment (air/vacuum) |
| Vias | **no formula** | **appendix sections** on vias, conductor→via→plane, microvias |
| Form | closed form (0.048/0.024) | **no closed form**; chart reads + multipliers |
| Status | generic design standard | 2009 original; IPC document table lists it **"No Longer Maintained"** |

Sources: Sierra Circuits describes the section 5 chart plus copper-thickness / material / board-thickness
/ plane / environmental multipliers (<https://www.protoexpress.com/blog/how-to-optimize-your-pcb-trace-using-ipc-2152-standard/>);
Standard Clarity and the IPC revision table record the "No Longer Maintained" status
(<https://www.ipc.org/ipc-document-revision-table>); QueenEMS records the via appendix and the absence
of a public per-via amp number.

**Does IPC-2152 give different answers for these geometries?** It gives **no closed-form answer**; the
charts are not public. The only public quantitative comparison is the 5 A / 10 °C / 1 oz table:

| standard | external | internal |
|---|---|---|
| IPC-2221 | 110 mil | 280 mil |
| IPC-2152 | 95 mil | 190 mil |

At the same width that implies **1.11×** the external current and **1.33×** the internal current
(I ∝ A^0.725). Applied as a **chart-read sensitivity, not a computation**, it gives:

- phase corridor (F.Cu ∥ In2, 7.400 mm): **54.4 A** (vs 47.12 A on IPC-2221);
- BATP_IN: **53.1 A** (vs 47.74 A).

Those are indicative only; the true IPC-2152 values require the purchased charts and the plane
multiplier. Two things are certain: IPC-2152 is **less conservative for traces near planes**, which
helps the phase corridor and BATP_IN, and its **via appendix is the only standard-grounded way to rate
the barrel field** — and that appendix is not public. IPC-2152 therefore **cannot rescue the 49.67 A
headline**, because the headline is a barrel number, not a trace number.

**Is the 0.048/0.024 split superseded?** Not contradicted: the internal/external penalty survives in
the published comparison (~2×), and the split remains the right first-order convention for a board
whose IPC-2152 charts are not available. But IPC-2152 **supersedes it as the method** — chart read plus
multipliers, not a closed form — and the one element this board most needs rated, the barrel, is the
one the split cannot rate.

---

## 3. Every ESC current path, recomputed with the k of the layer it runs on

ΔT = 20 K (the programme's assumption; the repo states none). "Required" is the cross-section at the
demand current on that path's own layers; "available" is the row-level measured copper; capacity is
the closed form on that measured copper with the correct k. Demands: **43.5 A per phase**, **40 A bus**
per independent rail. `01_k_basis.json` holds every row.

| path | layer / k | required mm² | available mm² | capacity A | verdict |
|---|---|---|---|---|---|
| **6 phase corridors** | F.Cu 4 oz **0.048** ∥ In2 1.5 oz **0.024**, 7.400 mm | **1.2759** (F.Cu 0.9279 + In2 0.3480) | **1.4245** (1.0360 + 0.3885) | **47.12** | **PASS** 43.5 A, 1.08× |
| — F.Cu alone (control) | F.Cu 4 oz 0.048, 7.400 mm | 1.2561 | 1.0360 | 37.83 | **FAIL** 43.5 A, 0.87× |
| — In2 at the *wrong* k (control) | In2 1.5 oz 0.048, 7.400 mm | — | 0.3885 | 56.41 (total) | would overstate by 9.3 A |
| **BATP_IN** (bus) | **F.Cu** 10.20 mm, 4 oz, **0.048** | **1.1189** | **1.4280** | **47.74** | **PASS** 40 A, 1.19× |
| **BATP** (bus) | 48 barrels, **0.024** (internal one-area) | **2.9108** | **1.5082** | **24.83** | **FAIL** 40 A, 0.62× |
| — BATP at the prior k (control) | 48 barrels, **0.048** | 1.1189 | 1.5082 | 49.67 | the withdrawn PASS (1.24×) |
| **BATN / return "ground"** | 61 barrels, **0.024** (internal one-area) | **2.9108** | **1.9166** | **29.55** | **FAIL** 40 A, 0.74× |
| — BATN at the prior k (control) | 61 barrels, **0.048** | 1.1189 | 1.9166 | 59.09 | the withdrawn PASS (1.48×) |
| **BATP In1 plane** (not the min-cut) | In1 1.5 oz, 20 mm representative slice, **0.024** | 2.9108 | 1.0500 | **19.10** | FAIL at 20 mm; needs **55.44 mm** for 40 A |

**Ground.** The power return is BATN, the 4 oz B.Cu plane; there is no separate high-current "GND".
So the ground row is the BATN row: the plane is external, but the measured min-cut is the 61-barrel
transition, and that is where the k question lands. The 5,077.28 mm² B.Cu plane itself is not the
bottleneck.

**Why BATP_IN is not affected.** The 47.74 A figure is a **F.Cu** cut: 10.20 mm × 0.140 mm = 1.4280 mm²,
`per_layer_mm2` F.Cu = 1.428, barrel = 0.0. F.Cu is an outer layer, k = 0.048 is the correct constant,
and the row passes. The brief's suspicion that the 47.7 A figure "may be the 24.8 A one" is **not** true:
BATP_IN never touches an inner layer in the cut.

**What *does* move.** BATP's and BATN's cuts are **100 % barrels** (`per_layer_mm2` all 0.0; 48 and 61
edges, each 0.03142 mm²). A barrel is buried copper. At the internal k the same one-area instrument
that produced 49.67 / 59.09 A returns **24.83 / 29.55 A** — exactly half, because I ∝ k. That is the
suspected error, located precisely.

---

## 4. BATP on In1 — is the re-pour's 49.7 A real?

### 4.1 Topology and what the min-cut actually is

From `esc-rail-repour/16_measure_v4.json` (h = 0.10 mm):

```
/M1_BATP   cut 1.50816 mm² = 48 × 0.03142 mm²
           per_layer_mm2  F.Cu 0.0 · In1 0.0 · In2 0.0 · B.Cu 0.0
           barrel_mm2     1.5082     n_cut_edges 48
           layer areas    F.Cu 939.71 · In1 5,009.86 · In2 62.77 · B.Cu 62.77
```

The series path is topologically F.Cu land → 48 barrels → In1 plane → 48 barrels → F.Cu drain. But the
**minimum cut is the barrel row at both ends**, not the In1 copper: the instrument searched the whole
3-D copper graph and the cheapest cut is 48 barrels. The In1 plane is a 5,009.86 mm² 2-D sheet; current
spreads in it and it is not the bottleneck. So the prior 49.67 A was **not** "In1 copper at the external
k"; it was "**barrels** at the external k". The assignment's premise — "BATP's series path is on In1" —
is topologically right and **ampacity-wrong**: the k of In1 does not govern the measured cut.

### 4.2 The three candidate numbers, and why only one is a standard answer

| basis | BATP capacity | what it is |
|---|---|---|
| 48 barrels × one area, k = 0.048 | **49.67 A** | the withdrawn figure: external constant on buried copper |
| 48 barrels × one area, k = 0.024 | **24.83 A** | the same instrument at the internal constant |
| 48 barrels summed per-via, k = 0.024 | **72.01 A** | each 0.4 mm / 25 µm barrel rated **1.50 A** at 20 K, × 48 |

The per-via number is not a rescue: IPC-2221 gives no via formula, and the one-area rule is the
programme's own instrument. The gap between 24.83 and 72.01 is **2.9×**, larger than the k correction
itself (2×). It is an aggregation artefact: `x^0.725` is sub-additive, so merging 48 separate cylinders
into one 1.5082 mm² bar understates the bundle; summing 48 independent barrels overstates it if they
heat each other. The truth lies between, and **the standard does not settle it** — IPC-2152's via
appendix (purchased) or a 4-wire coupon test at 40 A would.

**BATP's true capacity on In1:** the In1 plane is not the limiting element. The 48-barrel transition
is. Its capacity is **24.83 A on the conservative internal-k one-area basis** (FAIL 40 A) and
**72.01 A on the per-via basis** (PASS). The honest statement is: **not 49.7 A; not established to
40 A by any public standard**. For a vital ESC the floor governs.

---

## 5. Corrected rail verdict and what the fix now requires

### 5.1 Verdict

| element | capacity | vs demand | verdict |
|---|---|---|---|
| phase corridor (F.Cu ∥ In2) | **47.12 A** | 43.5 A (1.08×) | **PASS** (survives the k correction) |
| BATP_IN (F.Cu 10.2 mm) | **47.74 A** | 40 A (1.19×) | **PASS** (survives; it is external) |
| BATP (48 barrels, internal k) | **24.83 A** | 40 A (0.62×) | **FAIL** on the conservative floor |
| BATN (61 barrels, internal k) | **29.55 A** | 40 A (0.74×) | **FAIL** on the conservative floor |

> **The rail's PASS is withdrawn as unproven.** The 49.67 / 59.09 A figures were produced by applying
> the **external** constant to a **100 % barrel** cut. At the internal constant — the one the standard
> assigns to buried copper — the same instrument gives **24.83 / 29.55 A**, both below 40 A. The
> per-via method gives 72 / 92 A, but it is an extrapolation IPC-2221 does not sanction, so it cannot
> be quoted as a PASS. The phase corridor still passes at 47.12 A, and BATP_IN still passes at
> 47.74 A; the **rail is now the binding element again**, not the phase.

This is the owner's point in numbers: the 370.12 cm² compaction spent the phase corridor to buy area
(7.51 → 1.50–3.50 mm), and the rail was declared safe on a constant that does not apply to its copper.
Placement drove the copper; the copper now says the placement is wrong.

### 5.2 What the fix requires

1. **Do not route 40 A through barrels as the only path.** Reserve a **planar external 4 oz corridor**
   of **7.99 mm per rail at 40 A** (8.97 mm at 43.5 A), or an equivalent B.Cu path. The widest
   completely-clear F.Cu channel measured on this placement is **2.75 mm** (3.25 mm power-first), so
   this is a **re-placement**, not a re-pour. With only **2.88 % routed (154 segments)**, this is the
   window.
2. **If barrels stay**, the conservative one-area k = 0.024 needs **78 barrels/cell at 40 A** (84 at
   43.5 A) versus the 48 now placed; the BATP land had room for only 48 (13.79 mm² free after fill), so
   that is also a placement change. Alternatively, validate the 48-barrel field with IPC-2152's via
   appendix or a 4-wire coupon at 40 A; until then quote **24.8 A**, not 49.7 A.
3. **Phase corridor:** reserve **6.63 mm** of F.Cu with the In2 pour in parallel at the correct k
   (6.628 mm required at 43.5 A), or **8.97 mm** of F.Cu alone. The compacted 1.50–3.50 mm gives
   **14.8–27.4 A** and fails.
4. **Correct the requirement number in the brief.** **6.991 mm is the 60 A requirement** — 60 A needs
   13.981 mm total of 4 oz, i.e. **6.991 mm per face across two 4 oz faces**. At **43.5 A** the two-face
   requirement is **4.486 mm per face**, and the F.Cu∥In2 requirement is **6.63 mm**. The compacted
   3.50 mm is 22 % short of 4.486 mm (not 2×), and 1.50 mm is 67 % short — still unsafe, but the honest
   shortfall is 22–67 %, not 2.0–4.7×.
5. **Heat spreader stays mandatory.** At 43.5 A the FET dissipation is 4.36 W/device
   (`1.33e-3·I² + 0.0424·I`), giving Tj ≈ 219 °C on the 40 C/W board-only figure and ≈ 142 °C with the
   spreader (22.36 C/W). The rail fix cannot trade the spreader for copper.

---

## 6. Instrument validation (hand-checkable cases)

`01_k_basis.py` exits non-zero and prints NOT QUOTABLE if any control misses its tolerance. All six
pass (`01_k_basis.log`):

| control | computed | published | residual | source |
|---|---|---|---|---|
| C1 10 mil / 1 oz / 10 K external → 0.88 A | 0.8818 A | 0.88 | +0.20 % | Volteq worked example |
| C2 5 A / 10 K / 1 oz external → 110 mil | 109.50 mil | 110 | −0.45 % | Standard Clarity worked example |
| C3 5 A / 10 K / 1 oz internal → 280 mil | 284.87 mil | 280 | +1.74 % | TraceWidthCalculator table |
| C4 60 A / 20 K / 4 oz external → 13.981 mm | 13.9813 mm | 13.981 | +0.002 % | programme settled figure |
| C5 43.5 A / 20 K / 4 oz external → 8.972 mm | 8.9725 mm | 8.972 | +0.005 % | programme settled figure |
| C6 43.5 A / 20 K / 1.5 oz internal → 62.244 mm | 62.2435 mm | 62.244 | −0.001 % | programme settled figure |

C3 is the one that validates the **internal** constant: the 1.74 % residual is the rounding in the
published 280 mil table entry (284.87 is the exact value). Without C3 the internal k would be an
unchecked assertion; with it, 0.024 reproduces a published internal-trace width.

---

## 7. Reproduce

```powershell
$py = "C:\Program Files\Python312\python.exe"
$ev = "E:\engineering-portfolio-audit\evidence\esc-ampacity-basis"
cd $ev
& $py 01_k_basis.py          # 6 controls -> PASS, 01_k_basis.json + 01_k_basis.log
```

Row-level inputs are the prior units' measured JSON, not re-derived here:
`esc-rail-repour/16_measure_v4.json` (BATP 1.50816 mm² / 48 barrels; BATN 1.91662 / 61;
BATP_IN 1.4280 on F.Cu), `esc-flip-current/02_flip.json` (phase corridor 7.400 mm, F.Cu∥In2),
`esc-flip-current/REPORT.md` §2 (In2 phase pour 622–737 mm² per phase, 64 vias).

---

## 8. Limits and what this does NOT cover

| # | assumption / limit | effect if wrong |
|---|---|---|
| A1 | ΔT = 20 K | at 30 K every capacity ×1.195: BATP 29.7 A, BATN 35.3 A — still FAIL 40 A; phase 56.3 A still PASS. The barrel verdict does not flip. |
| A2 | 25 µm barrel plating | at 38 µm area ×1.52, current ×1.355: BATP one-area 33.7 A, BATN 40.1 A — BATP still fails; the per-via estimate rises to ~98 A. Not a standard rating either way. |
| A3 | one-area aggregation for barrels | the dominant uncertainty: one-area 24.83 A vs per-via 72.01 A (2.9×), larger than k. No public standard settles it. |
| A4 | phase In2 credited at the same 7.400 mm width | conservative: In2 carries 1.7–2.0× more phase copper than F.Cu (`esc-flip-current` §2), so the phase PASS can only improve. |
| A5 | IPC-2152 numbers are a chart-read sensitivity from one published comparison table | not a first-principles IPC-2152 computation; the purchased charts/plane multiplier could move them ±10 %. |
| A6 | only cell 1 measured | cells 2–6 received the identical edit (same host areas to 0.03 mm²), not independently measured. |
| A7 | no thermal solve | the spreader is still mandatory; this unit does not model board temperature. |
| A8 | "40 A bus" applied per independent rail | if the 40 A is a shared total, the rail demand falls and every rail margin improves; the k conclusion is unchanged. |

**What this settles:** the k split is real (0.048 external / 0.024 internal), the 49.67 / 59.09 A
rail figures were **external-k numbers on a 100 % barrel cut**, and at the internal k the conservative
floor is **24.83 / 29.55 A — a FAIL at 40 A**. **What it does not settle:** the true ampacity of a
48-barrel array, because neither IPC-2221 nor the public IPC-2152 material gives one. That is a
coupon test or the purchased via appendix, and it must be done before any rail PASS is quoted again.