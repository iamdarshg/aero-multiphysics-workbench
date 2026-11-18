# FAB-DM-INTERFERENCE — the 22-pair airframe interference

**Scope:** drone-mech airframe (`repos/drone-mech/highspeed_edf/deliverables/phase15_geometry`),
branch `work/2026-11-11`, **read-only** — nothing was written into the repo and no git operation
was performed. All artefacts are in `evidence/fab-dm-interference/`.

**Provenance labels.** Every volume here is **native CAD boolean** (OpenCascade `BRepAlgoAPI`
through CadQuery 2.7.0 / OCP 7.8.1.1 on `C:/Program Files/Python312/python.exe`), or **closed
form** where marked. No solver, no surrogate, no invented supplier number. The one supplier
envelope is labelled **LISTING**, with its URL, and it is listing text, not a drawing.

---

## Verdict

The reported figure is exact, and the cause is neither a duplicated part nor a wrong pitch — it
is **a motor envelope 40.2 % too large in volume, placed coaxially inside a 110 mm duct module
that cannot hold it**.

| | |
|---|---|
| pairs | **22** (reproduced by two scripts, same answer) |
| volume | **331,033.5633 mm³** — matches the brief to the last digit |
| duplicated placement | **0 pairs** |
| press-fit / thread engagement wrongly counted | **0 pairs** |
| genuine design clash | **20 pairs / 330,719.4040 mm³** |
| modelling artefact (pilot stub) | **2 pairs / 314.1593 mm³** |
| envelope as built | Ø42.000 × 72.000 + Ø5 × 8 stub = **99,908.93 mm³** |
| envelope it should be | **Ø36.000 × 70.000 + Ø5 × 17 shaft** = 71,251.29 mm³ |
| minimum change | **delete 4 of 6 envelopes, keep one per duct** → **0 pairs / 0.0000 mm³** |
| does the 42_6 Boolean repair change the count | **NO** — measured, see §6 |

---

## 1. Reproduce

Two scripts, two routes, same answer.

| route | how | result |
|---|---|---|
| `fab_dm_interference.py` | 54-pair sweep (15 motor–motor + 18 motor–rotor + 18 motor–stator), per-member-solid accumulation | `as-built: 22 pairs 331033.5633 mm3` |
| `fab_dm_fix.py` | full pair list **including envelope-vs-envelope**, against 23 neighbour parts | `BEFORE as-built, six motors: FAIL 22 pairs 331033.5633 mm3` |

Console receipts: `run_fab_dm_interference.log`, `run_fab_dm_fix.log`.

The 22 pairs, as measured (both ducts are numerically identical, so each row is two):

| # | set | pair | mm³ | group |
|---:|---|---|---:|---|
| 1–2 | motor–motor | `motor_*_R1` – `motor_*_R2` | 50,033.004601 | b1 axial |
| 3–4 | motor–motor | `motor_*_R2` – `motor_*_R3` | 50,033.004601 | b1 axial |
| 5–6 | motor–motor | `motor_*_R1` – `motor_*_R3` | 157.079633 | a artefact |
| 7–8 | motor–rotor | `motor_*_R1` – `duct_*_rotor_R2` | 20,779.265829 | b2 radial |
| 9–12 | motor–rotor | `motor_*_R1/R2` – `duct_*_rotor_R3` | 20,696.470270 | b2 radial |
| 13–22 | motor–stator | `motor_*_R{1,2,3}` – `duct_*_stator_S{1,2,3}` | 624.297292 | b3 radial |

### Closed-form cross-checks (all agree with the booleans)

```
50,033.004601 = π·21²·36  + π·2.5²·8  = 49,875.925 + 157.080      can-on-can 36 mm + stub
   157.079633 = π·2.5²·8                                            stub alone (R1–R3)
   624.297292 = π(21² − 20.4²)·8 = π·24.84·8                        can r21 vs carrier bore r20.4, 8 mm
20,779.265829 = π(20² − 2.525²)·16 + 993.55 = 19,785.72 + 993.55    hub engulfed in full + blade roots
```

### Method hazard, and the controls that prove the detector is not blind

A compound-level `Shape.intersect()` returns **0.0 mm³ for a partial overlap** (found in the
earlier wave, re-tested here), so every volume against a multi-solid part is summed over its
**member solids** with a per-solid bounding-box prefilter. Three controls, from
`fix_before_after.json`:

| control | expected | measured | verdict |
|---|---|---:|---|
| sourced Ø36 envelope at the **R1** station vs `duct_A_rotor_R2` | non-zero | **15,965.542450** | detector sees the radial class |
| as-built Ø42 envelope, can start **105.0** vs `stator_S3` | non-zero | **78.037162** | resolves 1 mm |
| same at **106.0** | zero | **0.0** | and 106.0 is where it stops |

A detector that returned 0 for the first control would be blind to the class it is grading; one
that returned 0 at 105.0 could not be trusted at 106.0. Both are non-zero.

**Agreement with the earlier wave.** `evidence/dm-g1-interference/` (different author, different
scripts) reached the same 22 pairs / 331,033.5633 mm³ and the same per-pair volumes. This wave
adds four things it did not have: the **sourced** Ø36×70 envelope (§4), the **closed-form identity
of the sourced radial rows** (§4c), the **before/after from a fix script that also grades
envelope-vs-envelope and carries negative controls** (§5b), and the **42_6 answer with the two
unrecorded inlet penetrations** (§6). No number here contradicts it.

---

## 2. The 22 pairs grouped by root cause

| group | pairs | mm³ | class | why |
|---|---:|---:|---|---|
| **b1** axial, can-on-can | 4 | 200,132.0184 | genuine design clash | Two 72 mm cans at a **36.000 mm** station pitch overlap **36 mm** axially. Verified closed form and by boolean. |
| **b2** radial, can swallows hub | 6 | 124,344.4127 | genuine design clash | Can radius **21.000** > hub radius **20.000**, so any axial co-location is a *total* engulfment of the hub chord (16 mm) plus blade roots. |
| **b3** radial, can vs stator carrier | 10 | 6,242.9729 | genuine design clash, marginal | Can r 21.000 vs carrier **bore r 20.400** → 0.6 mm radial interference over 8 mm of chord. |
| **a** pilot-stub artefact | 2 | 314.1593 | **modelling error** | The 8 mm × Ø5 stub is built *behind* the can (`can_start − 8`). On row R3 it lands inside row R1's can. A real motor's shaft enters **its own** hub bore; there is no neighbouring can behind it. |
| **c** press-fit / thread / shrink | **0** | 0 | — | The only interference-fit-like feature in the model — the 2.500 mm shaft in the 2.525 mm hub bore — is modelled **with 0.025 mm radial clearance and measures 0.000 mm³**. Nothing intentional is being miscounted. |
| | **22** | **331,033.5633** | | |

**Root cause, one line:** the generator emits a can that is 21.0 mm in radius where the hub is
20.0 and the stator carrier bore is 20.4, and 72 mm long where the row pitch is 36 mm. Two of the
three pair classes are pure *radius* consequences of that 1.0 mm; the third is a pure *length*
consequence of `L = 72` vs `p = 36`.

The repo knows and says so, at
`phase15/optimization/phase15_generate_geometry.py:864`: *"adjacent motor envelopes overlap
axially by 36 mm. This violates physical buildability; the sourced motor size and rotor-row
pitch cannot both be met with coaxial direct drive. The STEP intentionally shows the envelope
collision; no overlap is hidden or boolean-subtracted."*

---

## 3. The 36 mm × 36 mm co-location — what it actually is

Everything below is measured from the STEP solids, not read from the generator constants.

| quantity | **measured** | source of the measurement |
|---|---:|---|
| motor can radius | **21.000 mm** (Ø42.000) | cylinder-face radius in `motor_*_envelope.step`; bbox 42.000 across |
| motor can length | 72.000 mm body; **80.000 mm** with stub | bbox z 12.000…92.000 for R1 |
| motor can start (both ducts) | **20.000 / 56.000 / 92.000 mm** | bbox z_min + 8 |
| hub radius | **20.000 mm** (Ø40.000), bore **2.525 mm**, chord **16.000 mm** | cylinder faces of `duct_*_rotor_R*.step` |
| hub row windows | 4–20 / 40–56 / 76–92 mm | rotor-stage bboxes |
| stator carrier | **bore 20.400, OD 21.100**, chord 8 mm | `duct_*_stator_S*.step` |
| **axial pitch** | **36.000 mm**, both gaps, both ducts | consecutive can-start difference |
| **axis separation, within a duct** | **0.000 mm** | all three envelopes and all three hubs sit at x = −44.000 (duct A) / +44.000 (duct B), y = 0.000 |
| axis separation, duct A ↔ duct B | 88.000 mm | measured |
| **circumferential pitch of blades** | **27.6923° / 30.0000° / 32.7273°** | 360/13, 360/12, 360/11 |

**Diagnosis: the parts were not placed at the same angular position. A circumferential offset
between them is meaningless, because they are coaxial.**

The **circumferential pitch between the clashing parts is 0.000 mm of arc** — not because they were
put at the same angle by mistake, but because they share one axis. The meaningful circumferential
pitch is *within* a row: **27.6923° / 30.0000° / 32.7273°** between blades.

* The three motors of one duct are three *distinct* instances (R1/R2/R3, three different design
  speeds and three different blade counts) on **one common axis** — a single 3-row shaft. Their
  axis separation is 0.000 mm *by design*, not by copy-paste.
* **36 mm is an axial station pitch, not a circumferential one.** 36 = 16 (rotor chord) + 6 +
  8 (stator chord) + 6. The two 6 mm gaps are 2 mm wider than the spec's `1.5–2.5–4 mm` band
  (`design/PHASE15_DESIGN_SPEC.md:196`), i.e. the pitch errs *toward* rub margin.
* So the pitch is **correct**; the **radius** is wrong by 1.0 mm (can 21.0 vs hub 20.0) and by
  0.6 mm (can 21.0 vs carrier bore 20.4); and the **fatal number is the count** — three 72 mm cans
  (216 mm of can) cannot occupy a module whose rows are 36 mm apart (108 mm of station span).

---

## 4. What the motor envelope should be — now sourced

### 4a. The repo contradicts itself

| source | value |
|---|---|
| `design/PHASE15_DESIGN_SPEC.md:302` (**SELECTED MOTOR**) | Surpass Hobby "Rocket" 3670 4-pole 1550 KV — **"36×70 can"**, ~270–276 g |
| `phase15/optimization/phase15_generate_geometry.py:104-105` | `MOTOR_CAN_D = 42.0`, `MOTOR_CAN_LENGTH = 72.0` |
| difference | **+6 mm diameter, +2 mm length** |

### 4b. The listing says the spec line is right and the generator is wrong

Three independent listings, one search:

| listing | text |
|---|---|
| [Rocket Boat 3670 1200/1550/… KV](https://www.amazon.com/Rocket-1200KV-1550KV-Brushless-Diameter/dp/B0GL2258WS) | **"Motor Size: ø36x70mm; Shaft Diameter: ø5mm; Length of Extend Shaft: 17mm; Mounting Screw: ø25mm M3\*6, 4 Poles 12-Slot"** |
| [Surpass Hobby Rocket V2 Supersonic 3670 (digitec)](https://www.digitec.ch/en/s1/product/surpass-hobby-rocket-v2-supersonic-3670-4-poles-2260kv-rc-motors-17212617) | "a **diameter of 36 millimetres and a length of 70 millimetres** … weight of only 295 grams" |
| [Surpass Hobby Rocket 3670 (Ingenium Drives)](https://ingeniumdrives.in/product/surpass-hobby-rocket-3670-1200kv-brushless-inrunner-motor/) | "3670 … Brushless **Inrunner** Motor \| 4 Pole \| 1500W \| **5mm Shaft**" |

**This is the error that produced 42 mm.** The "36 mm stator ⇒ ≈42 mm bell" rule is an
**outrunner** rule. The Surpass 3670 is an **inrunner** with a "CNC Machined 6061 T6 Billet
Aluminum Heatsink Can" (same listing): its Ø36 mm **is** the outside diameter. Applying the
outrunner rule to an inrunner manufactured 6 mm of diameter and 2 mm of length that do not exist.

**Envelope of record (LISTING-tier, not a drawing):** Ø36.000 × 70.000 mm can, Ø5.000 mm shaft
extending 17.000 mm, Ø25 mm M3 mounting circle on the front face.

`42 × 72 = 99,908.93 mm³` modelled; `36 × 70 = 71,251.29 mm³` sourced → **the as-built
envelope is 40.2 % too large in volume.**

### 4c. Effect of correcting it — measured

Native, with the sourced envelope left at the **as-built stations** (`sourced_effect` in
`fab_dm_interference.json`):

| class | as built (Ø42×72) | corrected (Ø36×70) | why |
|---|---:|---:|---|
| b3 can vs stator carrier bore 20.4 | 10 pairs / 6,242.9729 | **0 pairs / 0** | 18.0 < 20.4 → the can passes through the bore |
| b2 can vs hub r 20 | 6 pairs / 124,344.4127 | **6 pairs / 91,801.8691** | reduced but **not cleared**: 18.0 < 20.0, so the can is still inside the hub annulus. **4 × 15,965.542450 + 2 × 13,969.849643**, which is exactly π(18²−2.525²)·16 and π(18²−2.525²)·14 — at Ø36 the blade roots no longer reach inside the can |
| b1 can-on-can at 36 mm pitch | 4 pairs / 200,132.0184 | **4 pairs / 139,059.46** (closed form) | π·18²·34 = 34,764.86 each |
| a stub | 2 pairs / 314.1593 | **2 pairs / 589.05** (closed form) | the sourced 17 mm shaft is *longer*: π·2.5²·15 = 294.52 each |
| **total** | **22 / 331,033.5633** | **12 / ≈231,450** | **−30.1 %, still FAIL** |

**So the envelope correction removes exactly the 10 stator-carrier pairs, and none of the rest.**
It does not make the board fab-ready on its own, and no envelope that is a real 3670 clears the
axial class: can-body-plus-shaft ≤ 36 mm would need `L ≤ 19 mm` with the sourced 17 mm shaft.

---

## 5. The minimum geometric change

### 5a. What is provably impossible (measured, not argued)

| requirement | measurement |
|---|---|
| can body vs can body | needs **p ≥ 70 + 17 = 87 mm** at the sourced length; the pitch is 36 mm and the module is 110 mm for 3 rows |
| can vs next hub | needs the can to start at or aft of the next hub's aft face |
| can vs stator carrier | needs **can radius ≤ 20.4 mm** — the sourced 18.0 satisfies it |

Three motors per duct on one axis is unsatisfiable at any pitch, at either envelope. **The count
must change.** Any fix that keeps six coaxial motors inside the duct will fail this check again.

### 5b. The change, and its before/after — from an actual run

**`fab_dm_fix.py`** (CadQuery, in this directory) evaluates the full pair list twice — envelopes
against each other **and** against 23 neighbour parts (all 6 rotor stages, all 6 stator stages, the
10 duct/nozzle/collar/ring/inlet parts, and the 42_6 fuselage):

```
BEFORE as-built, six motors                                     FAIL 22 pairs  331033.5633 mm3
AFTER  minimum change (sourced Ø36x70, one per duct at R3 +1mm) PASS  0 pairs       0.0000 mm3
AFTER  alt (as-built Ø42x72, one per duct, can start 106)       PASS  0 pairs       0.0000 mm3
```

**Minimum change = delete four of the six envelopes, keep one motor per duct on the R3 station,
and rebuild it to the sourced envelope with the can's front face 1.000 mm aft of the hub's aft
face.**

| | value |
|---|---|
| envelopes deleted | 4 (R1 and R2, both ducts) |
| can | Ø36.000 × 70.000, z **93.000 … 163.000** |
| shaft | Ø5.000 × 17.000, z **76.000 … 93.000** (enters its own hub bore, 0.025 mm radial clearance) |
| axial clearance to its own hub aft face | **1.000 mm** |
| radial clearance to the stator carrier bore | **2.400 mm** |
| remaining clashes | **0 pairs, 0.0000 mm³** over 23 neighbours + envelope-vs-envelope |
| mass | **−4 × 0.274 kg = −1.096 kg** |
| deviation from spec | **6 motors → 2**, against `design/PHASE15_DESIGN_SPEC.md:170` ("6 motors, 3/duct") |

`fixed_motor_layout.step` (written by the same script) is the two surviving envelopes.

### 5c. What it costs, and why the cheaper-looking alternative is not cheaper

* **21.30 % of the nozzle throat is blocked.** Measured: nozzle `z 110…245`, bore r **39.000** →
  4,778.362 mm²; the can presents π·18² = 1,017.876 mm². 53 mm of the can is inside the nozzle.
  The alternative (keep the as-built Ø42 at can start 106) is also interference-clean but blocks
  π·21²/π·39² = **29.0 %** — worse.
* Interference-clean is not flow-clean. The fix clears the *geometric* blocker and leaves a
  *performance* one that needs its own decision.

**Recommendation.** Take the deletion. It is four part instances and no new geometry; it is
verified clean against every part in the module; and it costs less than any alternative that
keeps three coaxial motors. But it is an **architecture decision, not a CAD edit** — if six
motors are mandatory, they must come off the flow axis (belt/coupling drive, or aft of the duct
exit), which is a redesign and must be priced as one.

---

## 6. The 42_6 disjoint solids — the harder issue, answered by measurement

### 6a. What the export actually is

| property | measured |
|---|---|
| member solids | **4** |
| part volume | **742,305.5264 mm³** (sum of solids 742,302.3544; Δ 3.17 mm³ = 4.3e-6, boolean-integration tolerance) |
| **self-overlap** (pairwise intersection of its own solids) | **0.000 mm³** |
| outer z span | **640.000 mm** (−360.000 … 280.000) |
| **through-gaps in z** | **exactly one: 77.1654 mm** (−189.0984 … −111.9330) |

| solid | mm³ | z (mm) | x (mm) |
|---|---:|---|---|
| 0 | 624,770.5299 | −360.000 … −189.0984 | ±105.8918 |
| 1 | 20,808.2965 | −107.4729 … 195.6651 | +56.2808 … +95.2820 |
| 2 | 75,915.2316 | −111.9330 … 280.0000 | ±48.1787 |
| 3 | 20,808.2964 | −107.4729 … 195.6651 | −95.2820 … −56.2808 |

Solids 1, 2 and 3 overlap in **z** but are disjoint in **x** — they are the two side rails and the
central body. So "4 disjoint solids **over 77.165 mm**" describes the **single through-gap**,
not the extent; the part is 640 mm long, which matches the repo's "640 mm master shell"
(`phase15_generate_geometry.py:862`).

### 6b. Is the disjointness why some "interference" appears?

**No — in either direction, and both are measured.**

1. **It cannot inflate a total.** A per-solid accumulation double-counts only if the solids
   overlap. Measured self-overlap = **0.000 mm³**.
2. **It cannot hide a motor clash.** 42_6 against all six as-built motor envelopes and against
   four candidate placements (`asbuilt_R3`, `asbuilt_aft106`, `sourced_R3`, `sourced_aft106`) —
   **0.0000 mm³ for every one**.
3. **No 42_6 solid is a member of any of the 22 pairs.** The 22 are motor–motor, motor–rotor and
   motor–stator only. The disjointness of a part that appears in none of them cannot be their
   cause.

### 6c. What the enumeration does surface: two pairs nobody counts

42_6 against the side inlets (`inlet_vs_42_6.json`):

| pair | mm³ | which 42_6 solid |
|---|---:|---|
| `duct_A_side_inlet_100mm` – 42_6 | **1,654.856341** | solid 3, the **left** rail (x −95.28 … −56.28) — duct A is at x = −44 |
| `duct_B_side_inlet_100mm` – 42_6 | **1,885.906929** | solid 1, the **right** rail (x +56.28 … +95.28) — duct B is at x = +44 |

These are **intentional** (the side inlet must pierce the body shell — that is the intake) and
belong in the waived class, but they are in **no existing receipt**, because the repo's checks
never test inlet-vs-fuselage. They also share the through-gap's z window (inlets −117 … +4 vs gap
−189.10 … −111.93, a 5.07 mm overlap), which is where a repair would add material.

### 6d. Would the +97 g Boolean repair change the pair count?

**No.** The repair adds union material inside the 42_6 footprint — around the four solids and
across the 77.1654 mm gap — and:

* **the 22 pairs are unchanged**, because no 42_6 solid is in any of them and 42_6 measures
  0.0000 mm³ against every motor envelope at every candidate placement. The nearest motor
  material after the fix is at **z = 76.000**, i.e. **187.9 mm aft** of the gap close (z = −111.933);
* **the two inlet pairs may change value** — unioning the rails to the shell turns a 1,654.86 /
  1,885.91 mm³ overlap into a shared boundary — but they are the *waived* class, not the blocked
  class. **That is a modelling consequence of the repair, not a reason to defer it.**

The +97 g is still a prerequisite for manufacture, exactly as the AUDIT board records — it is
simply **orthogonal to the 22**. Reproducing a stress or mass number from an unrepaired 4-solid
export is still invalid; reproducing an *interference* count is not.

---

## 7. BOARD CORRECTIONS

1. **"331,033.5633 decomposes as 4 × 50,033.0046 + 2 × 157.0796"** — **that sum is
   200,446.1777, not 331,033.5633.** It is exactly the *motor–motor subtotal*; the grand total
   needs the 16 radial pairs, **+130,587.3856**, which is how the remainder decomposes. The earlier
   "4 pairs / 50,033 mm³" reported **one pair's** volume against four pairs; those four pairs are
   **200,132.0184 mm³** between them. Same population error in a new place: a correct measurement
   of the wrong subset.
2. **"The motor can overlaps the hub by 36 mm at a 36 mm pitch"** — 36 mm is **can-on-can**.
   The can-on-**hub** overlap is **16.000 mm**, and it is *total* engulfment of the hub's chord
   (19,785.72 mm³ closed form, 20,779.27 measured with blade roots). The repo's own receipt field
   `motor_can_overlap_mm: 36.0` is the can-on-can figure.
3. **"42_6 is 4 disjoint solids over 77.165 mm"** — 77.1654 mm is the **single through-gap**;
   the part spans **640.000 mm**. The 4 solids do not overlap (0.000 mm³).
4. **"The motor envelope 42×72 is UNSOURCED"** — it is now **sourced and wrong**. The spec's
   "36×70" (`PHASE15_DESIGN_SPEC.md:302`) is correct; 42 mm came from applying an *outrunner
   bell* rule to an *inrunner*. Envelope of record: Ø36.000 × 70.000, Ø5 × 17 shaft.
5. **Not a correction, a cross-check that agrees:** 42_6 volume 742,305.5264 mm³ vs the board's
   742,306.360 mm³ — Δ 0.83 mm³, 1.1e-6 relative. Different import path; no action.

---

## 8. FAB-READINESS CHECKLIST LINE

| item | line | basis |
|---|---|---|
| **mechanical interference, duct module** | **FAIL — design, not fab.** 22 pairs / 331,033.5633 mm³. Minimum clearing change specified and verified (0 pairs / 0.0000 mm³): delete 4 of 6 motor envelopes, one per duct at can z 93.000–163.000 with the sourced Ø36×70 envelope. **Blocked on an architecture decision** (6 motors per `PHASE15_DESIGN_SPEC.md:170` vs 2 that the geometry can hold). | `fab_dm_interference.py`, `fab_dm_fix.py`, `fix_before_after.json` |
| **motor envelope** | **WAS unsourced; now LISTING-tier** Ø36×70 + Ø5×17. Correcting it alone takes 22 → 12 pairs but does not clear them. | §4, `fab_dm_interference.json:sourced_effect` |
| **intentional penetrations** | **WAIVED, with reason**: side inlets pierce the body shell by 1,654.86 and 1,885.91 mm³ — that is the intake, and no check tests inlet-vs-fuselage. | `inlet_vs_42_6.json` |
| **42_6 export** | **FAIL — prerequisite for manufacture**, but **does not affect the pair count**. 4 disjoint solids, one 77.1654 mm through-gap, +97 g Boolean repair still required. | §6 |
| **nozzle throat** | **NEW DEFECT, not interference**: the interference-clean fix blocks 21.30 % of the throat (4,778.362 mm² → the can takes 1,017.876 mm²). Needs a flow decision, not a geometry tweak. | `duct_z_windows.json` |

---

## 9. What this does NOT establish

* **No supplier drawing.** The Ø36 × 70, Ø5 shaft and 17 mm extension are **listing text** from
  three retail pages; the 17 mm extension and the Ø25 M3 circle come from **one** of them. A
  drawing or a physical part could move the length by a millimetre or two, which changes the
  numbers in §4c slightly and the conclusions not at all.
* **No flowpath, thermal, containment, rotor-dynamic or balance assessment** of the surviving
  motor inside the nozzle. §5c quantifies the area loss only.
* **No whole-airframe clearance proof.** The neighbour set is the 23 parts that share the duct
  module's axial window — 6 rotor stages, 6 stator stages, and per duct the tube, nozzle+exit lip,
  containment collar, vane bearing ring and side inlet — plus the 42_6 fuselage. The 63 MB full
  assembly STEP was deliberately not imported: a part whose z window does not reach the module
  cannot collide with the motors, but that is a reasoned exclusion, not an exhaustive proof.
* **No stress or mass re-derivation.** Those belong to the body workstream and are on the board.

---

## 10. Artefacts and how to reproduce

| file | content |
|---|---|
| `fab_dm_interference.py` | the diagnostic: geometry measurement, 54-pair sweep, grouping, sourced-envelope effect, 42_6 audit, candidate trials |
| `fab_dm_interference.json` | its output |
| `fab_dm_fix.py` | **the minimum change**, with envelope-vs-envelope pairs, before/after, negative controls, and `fixed_motor_layout.step` |
| `fix_before_after.json` | BEFORE 22 / 331,033.5633 → AFTER 0 / 0.0000, plus the three controls |
| `fixed_motor_layout.step` | the two surviving envelopes, as built geometry |
| `fab_dm_42_6.py`, `fab_dm_42_6.json` | 42_6 solids, self-overlap, through-gap audit (the 22-part boolean sweep against a 7 MB shell was stopped as uneconomical — >13 min, no result — and the facts that decide the question do not need it) |
| `duct_z_windows.py`, `duct_z_windows.json` | z windows + cylindrical radii of the 10 duct parts, throat area, gap occupancy |
| `inlet_vs_42_6.py`, `inlet_vs_42_6.json` | the two unrecorded, intentional inlet-through-shell penetrations |
| `check_report.py`, `run_check_report.log` | **58 assertions** re-deriving every number in this report from the JSON receipts; all pass, exits non-zero on drift |
| `run_*.log` | console receipts, verbatim |

```powershell
cd E:/engineering-portfolio-audit/evidence/fab-dm-interference
& "C:/Program Files/Python312/python.exe" fab_dm_interference.py   # ~145 s
& "C:/Program Files/Python312/python.exe" fab_dm_fix.py            # ~100 s, writes the STEP
& "C:/Program Files/Python312/python.exe" fab_dm_42_6.py           # ~7 s
& "C:/Program Files/Python312/python.exe" duct_z_windows.py        # <5 s
& "C:/Program Files/Python312/python.exe" inlet_vs_42_6.py         # ~60 s
& "C:/Program Files/Python312/python.exe" check_report.py          # asserts this report
```

Inputs are read-only: `repos/drone-mech/highspeed_edf/deliverables/phase15_geometry/step/*.step`.
Nothing was written into the repo (verified: no file under `repos/drone-mech` has a modification
time after 2026-11-15T17:50, the start of this session); no git operation was performed.

---

## 11. Status line for `AGENT_BOARD.md` (for the lead to merge — I did not write outside my folder)

```
| fab-dm-interference | 22 pairs / 331,033.5633 mm³ reproduced. 20 genuine clash + 2 stub artefacts,
0 press-fit. NOT duplicate placement — coaxial by design (axis sep 0.000 mm, 36 mm is AXIAL pitch).
Radius is wrong: can r21.0 vs hub r20.0 vs carrier bore r20.4. Envelope should be Ø36×70 + Ø5×17
(LISTING-sourced; 3670 is an inrunner, 42 mm was an outrunner rule). Correcting it alone: 22→12
pairs, 331,033.56→231,450 mm³, still FAIL. MINIMUM change: delete 4 of 6 envelopes, one per duct,
sourced Ø36×70 at can z 93.000-163.000 → 0 pairs / 0.0000 mm³, −1.096 kg, costs 21.30 % throat.
Script: evidence/fab-dm-interference/fab_dm_fix.py. 42_6's 4 disjoint solids are NOT the cause
(self-overlap 0.000, 0.0000 mm³ vs every motor envelope); the +97 g repair does not change the 22,
though it may consume the two unrecorded 1,654.86 / 1,885.91 mm³ inlet-through-shell penetrations. |
```