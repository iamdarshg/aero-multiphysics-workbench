# FAB-DM-ELEVON — the two surviving elevon pairs, the cause, and the relief actually cut

**Scope:** drone-mech airframe, `repos/drone-mech/highspeed_edf/deliverables/phase15_geometry/`
(branch `work/2026-11-11`), **read-only**. No file under `repos/` was written; no git command was
run. Every artefact in this report lives in `evidence/fab-dm-elevon/`; the two re-cut wing sectors
are **copies** written there and nowhere else.

**Provenance:** every volume below is a **native OpenCascade boolean** (`BRepAlgoAPI` through
CadQuery 2.7.0 / OCP 7.8.1.1 on `C:/Program Files/Python312/python.exe`). Closed-form figures are
labelled. Nothing is a solver, a surrogate, or an estimate.

**Built on verified state, nothing re-derived:** the module baseline reproduces
**22 pairs / 331,033.5633 mm³** to the last digit in this run (`run_fab_dm_elevon.log:2`), and the
motor fix (delete R1+R2, keep R3, corrected Ø36 × 70) returns **0 pairs / 0.0000 mm³**
(`:3`). Both are reproduced here because the elevon number is meaningless unless the motor number
under it is the same one the board carries.

---

## VERDICT

**1. There are ten surviving elevon pairs, not two.** At the final motor state (R3 only, Ø36 × 70)
the elevon class measures **10 pairs / 2,373.4904 mm³**, not 2 / 1,186.1381. The board's 26-pair
airframe total counted only the elevon-vs-motor-envelope pairs (4) and never put the elevons
against the wing, the nozzle, the fuselage or their own pushrods.

**2. The pair the brief is tracking is the motor envelope, and it is NOT 593.069028 after the
resize.** `593.069028` is the **as-built Ø42** value. With the sourced Ø36 can the same pair is
**409.833028 / 409.833022** (left / right — mirrored solids, 6 × 10⁻⁶ mm³ apart, 819.666050
together).

**3. The relief is real, named correctly, and NOT delivered.** The generator does
`chord -= ELEVON_CHORD + ELEVON_GAP` over the elevon span, which promises a **+0.499 mm** gap at
every station. The delivered solid bulges **−10.754 mm** into the elevon at x = −170. **Cause: the
relief is a chord trim inside a `ruled=False` loft** whose relieved band carries only three of its
thirteen stations.

**4. The minimum change was executed: a planar cove cut 0.500 mm forward of the elevon's leading
edge, across its span, 0.500 mm taller than the plate each side.** Measured: **559.093479 →
0.000000000 mm³** on both wings, removing **973.493503 mm³** of wing per side, with a delivered
clearance of **0.500 mm at the root station rising to 1.213 mm at the tip**. The elevon did not
move.

**5. ZERO is NOT reached.** After the relief the airframe is **8 pairs / 1,255.3034 mm³**. The
remaining eight pairs are a **root-station** defect, not a relief defect: at the elevon's root
radius there is no wing material to relieve (measured — the wing ends at r = 42.5, the root is at
r = 11.250). Clearing them costs the flying surface: a **37.985 mm** root trim (−25.41 % span) or
the equivalent outboard re-stationing, plus a 2.267010 mm³ pushrod detail. Both are measured below
and **neither is executed**, because both change the flight control surface and one of them changes
its span.

**6. The number the board should carry: 8 pairs / 1,255.3034 mm³** — the airframe as it stands after
the motor fix and this relief. The as-built figure is **34 pairs / 334,227.9062 mm³**, not
26 / 332,674.0818.

---

## 1. The two surviving pairs, identified

At the final motor state, per side, measured (`fab_dm_elevon.json → elevon_after`):

| # | pair | volume mm³ | parts | feature |
|---:|---|---:|---|---|
| 1 | `elevon_left` ↔ `motor_A_R3` envelope | **409.833028** | elevon left / motor can A, z 92…162, r 18 | the plate's inboard end, x −65.000…−55.250 |
| 2 | `elevon_right` ↔ `motor_B_R3` envelope | **409.833022** | elevon right / motor can B | mirrored, x +55.250…+65.000 |
| 3 | `elevon_left` ↔ `lifting_wing_left_sector_…_reliefs` | **559.093479** | elevon left / wing sector left | plate forward chord band, x −199.755…−131.063, z 115.625…126.568 |
| 4 | `elevon_right` ↔ `lifting_wing_right_sector_…_reliefs` | **559.093479** | elevon right / wing sector right | mirrored |
| 5 | `elevon_left` ↔ `duct_A_separate_nozzle_and_exit_lip` | 120.247564 | elevon / nozzle shell | x −85.000…−82.978, r 38.978…41.000 |
| 6 | `elevon_right` ↔ `duct_B_separate_nozzle_and_exit_lip` | 120.247564 | mirrored | |
| 7 | `elevon_left` ↔ `fuselage_battery_bay_shell_endpoint_relief_42_6` | 95.304133 | elevon / 42_6 side wall | x −93.235…−90.586 |
| 8 | `elevon_right` ↔ `fuselage_42_6` | 95.304133 | mirrored | |
| 9 | `elevon_left` ↔ `elevon_pushrod_left` | 2.267010 | elevon / 2 × 38 × 2 mm rod | x −126.000…−124.000, z 115.592…117.000 |
| 10 | `elevon_right` ↔ `elevon_pushrod_right` | 2.267010 | mirrored | |
| | **total** | **2,373.4904** | | |

**Answers to the four candidate clash classes, each by measurement:** elevon-vs-**wing** (2 pairs,
1,118.186958), elevon-vs-**duct** (2 pairs, 240.495128 — the nozzle shell, not the tube, the collar,
the ring or the inlet, all of which bbox-miss), elevon-vs-**pushrod** (2 pairs, 4.534020),
elevon-vs-**elevon** (0 — the two plates' x ranges are 55.250…204.750 and −204.750…−55.250, which
do not meet), and the fifth class nobody had listed, elevon-vs-**motor envelope** and
elevon-vs-**fuselage** (4 pairs, 1,010.274316).

### 1a. The elevon is five solids, and the clash lives in one of them

`elevon_anatomy.json` (`probe_elevon_anatomy.py`), fused first because the members overlap:

| member | volume mm³ | bbox | what it is |
|---|---:|---|---|
| 0 | 8,987.637813 | x −204.750…−55.250, y −0.900…1.308, z 115.264…155.977 | the panel (2.209 mm at its thickest, not 3.5) |
| 1 | 360.000 | x −139…−121, y −2.000…0.000, z 116.620…126.620 | control horn |
| 2 | 42.411501 | x −64.250…−58.250, z 126.120…129.120 | root hinge knuckle |
| 3 | 42.411501 | x −133…−127, same | mid hinge knuckle |
| 4 | 42.411501 | x −201.750…−195.750, same | tip hinge knuckle |
| | **9,474.872 sum / 9,226.872 union** | | **248.000 mm³ of self-overlap** |

The wing pair is **99.0 % the panel**; the horn adds 2.909198 and the union subtracts the overlap.
Only member 2 (the root knuckle, 42.411501) touches the motor can, and it is inside the panel's own
626.697862 there — the can pair is the panel, not the hardware.

---

## 2. The cause of the wing pair: the relief is cut and not delivered

### 2a. What the generator promises

`phase15/optimization/phase15_generate_geometry.py:319-329`:

```python
if 55.25 <= abs(x) <= 204.75:
    chord -= ELEVON_CHORD + ELEVON_GAP          # 40.0 + 0.5 mm
```

so the wing's trailing edge inside the elevon band should sit at `te(x) − 40.5` while the elevon's
leading edge sits at `te(x) − 40.0` — a **+0.500 mm** gap, station after station, under sweep and
taper alike. With `WING_ROOT_LE_Z −270`, `WING_ROOT_CHORD 425`, `WING_TIP_CHORD 305`,
`WING_SPAN 520`, `WING_SWEEP_DEG 25`, `te(x) = 155.000 + 1.243·|x|/260`.

### 2b. What the solid does — measured on 0.5 mm slabs

`relief_line.json` (`probe_relief_line.py`). Gap = elevon leading edge − wing trailing edge, so
positive is clearance and negative is interference:

| x (mm) | wing TE measured | wing TE intended | elevon LE | **gap measured** | gap intended |
|---:|---:|---:|---:|---:|---:|
| −204.0 | 113.858 | 115.473 | 115.972 | **+2.114** | +0.499 |
| −200.0 | 115.957 | 115.454 | 115.953 | **−0.004** | +0.499 |
| −195.0 | 119.681 | 115.430 | 115.929 | **−3.752** | +0.499 |
| −190.0 | 122.513 | 115.406 | 115.905 | **−6.608** | +0.499 |
| −180.0 | 125.767 | 115.358 | 115.857 | **−9.910** | +0.499 |
| **−170.0** | **126.563** | 115.311 | 115.810 | **−10.754** | +0.499 |
| −160.0 | 125.593 | 115.263 | 115.762 | **−9.831** | +0.499 |
| −150.0 | 123.183 | 115.215 | 115.714 | **−7.469** | +0.499 |
| −140.0 | 119.648 | 115.168 | 115.666 | **−3.982** | +0.499 |
| −131.0 | 115.713 | 115.125 | 115.624 | **−0.089** | +0.499 |
| −130.0 | 115.239 | 115.120 | 115.619 | **+0.379** | +0.499 |
| −125.0 | 112.779 | 115.096 | 115.595 | +2.816 | +0.499 |
| −110.0 | 104.722 | 115.025 | 115.523 | +10.802 | +0.499 |
| −90.0 | 93.779 | 114.929 | 115.428 | +21.649 | +0.499 |
| −85.0 | 26.965 | 114.905 | 115.404 | +88.439 | +0.499 |
| −82.0 | −50.684 | 114.891 | 115.390 | +166.074 | +0.499 |
| −80.5 | −95.560 | 114.884 | 115.383 | +210.943 | +0.499 |

**Read the last three rows as the bore, not as a gap.** Inboard of |x| = 86.5 the wing's trailing
edge has retreated to z = 26.965 / −50.684 / −95.560, because that is where the duct bore relief
removes the section — the wing's material there survives only at |y| > ~22, outside the plate's
3.209 mm band. The plate has plenty of clearance at those stations for the trivial reason that there
is no wing in its path (§3).

**The relief is correct at its own stations and wrong between them.** At x = −204.0 (−204.75 is a
loft station) the gap is +2.114, at x = −130.0 (a station) it is +0.379 — both positive, as the
table says. Between them the interpolated surface swings **10.754 mm** the wrong way, and the whole
interference sits between x = −131.06 and −199.75, which is **exactly one loft bay**.

**Mechanism, and it is in the source, not inferred.** `:333-335`:

```python
xs = (-260.0, -205.01, -204.75, -130.0, -55.25, -54.99, 0.0, ...)
outer = cq.Solid.makeLoft([wing_wire(x) for x in xs], ruled=False)
```

The relieved band gets **three stations** (−204.75, −130.0, −55.25) out of thirteen, and each end of
the band is a **40.5 mm chord step across a 0.26 mm station gap** (−205.01 → −204.75 and
−54.99 → −55.25). A non-ruled loft interpolating through that pair overshoots: the same surface is
**+18.457 mm** past its own table at x = −205.5, **+102.4 mm** at x = −220 and **+16.6 mm** at
x = −258, all outside the elevon but all from the same table. The elevon simply occupies the one
place where the overshoot is negative.

**So the correct label is: an undersized relief cut in the delivered solid — nominal gap +0.500 mm,
delivered −10.754 mm, i.e. 11.254 mm of chord short at the worst station.** Not an undersized
relief in the *drawing*: the drawing is right.

---

## 3. The cause of the other eight pairs: the root station, and no relief can fix it

The elevon's root stands at |x| = **55.250**, i.e. **r = 11.250** from the duct axis at x = ±44.

| structure | radius it occupies | the root at r 11.250 is |
|---|---:|---|
| Ø85 duct bore (`duct_ID 78` → r 39; bore relief cut r 42.5) | r ≤ 42.5 | **31.250 mm inside it** |
| nozzle shell, z 110…245 | r 38.978…41.000 | inside it; the plate crosses it, x −85.000…−82.978 |
| 42_6 side wall | \|x\| 90.586…93.235 (r 46.586…49.235) | crossed, x −93.235…−90.586 |
| corrected motor can, z 92…162 | r 18.000 | **6.750 mm inside it** |

**The decisive measurement is a split of the elevon at the wing's own inboard limit** — the duct
bore relief, r = 42.5 about the duct axis at |x| = 44, i.e. **|x| = 86.5**. Cut the plate there and
measure both halves (`root_split.json`, `probe_root_split.py`):

| elevon half | elevon volume | ↔ wing | ↔ nozzle | ↔ 42_6 | ↔ Ø36 can |
|---|---:|---:|---:|---:|---:|
| **inboard**, \|x\| < 86.5 | 1,886.047 | **0.000000** | 120.247564 | 0.000000 | **409.833028** |
| **outboard**, \|x\| > 86.5 | 7,340.825 | **559.093478** | **0.000000** | 95.304133 | **0.000000** |

**The two defect classes are disjoint, and the split falls exactly on the duct bore.** The can and
nozzle pairs are **100 % inboard** of the wing's inboard limit, where the wing measures **zero** —
so a relief, which is a cut in the wing, has nothing to cut there. The wing pair is **100 %
outboard**, where no tail structure reaches. That is the measured proof that the relief can clear
one class and cannot touch the other, and it is why the eight tail-side pairs need the elevon's
station rather than the wing's cove.

**Which candidate cause this is:** an **elevon mounted at the wrong station** — the root is
**37.985 mm** too far inboard and the span (149.5 mm) is 37.985 mm more than the 111.515 mm the
layout leaves it. It is **not** the pushrod (its own pair is 2.267010, and it survives every root
trim), and it is **not** a hinge-axis error (the hinge is at `ELEVON_HINGE_FRACTION 0.30` of the
chord, the three knuckles sit at |x| 61.25 / 130.0 / 198.5, and no knuckle has a wing pair — the
knuckles are clean apart from the root one inside the can).

---

## 4. The minimum change, executed

**Chosen lever: the relief cut**, because it is a machining feature and the elevon is a flying
surface. The wing's own name says the reliefs are there; the fix restores the relief the drawing
already specifies.

**Method, and why not "offset the elevon and subtract":** the first attempt did exactly that and OCC
returned a **null** solid from every solid-offset route (`BRepOffsetAPI_MakeOffsetShape`
`PerformByJoin` in five argument forms, `BRepOffsetAPI_MakeThickSolid` both signs — see
`probe_offset_method.py`). That probe was **killed after 10 minutes without a valid shape and its
console log was lost to the buffered pipe**, so the failure is documented by the script and by the
`"offset FAILED (Null TopoDS_Shape object)"` string it wrote into `fab_dm_elevon.json → relief →
method`, not by a log file. The fallback in that first run subtracted the elevon untouched, i.e.
**zero clearance** — a contact, not a relief — so it was **superseded**, not kept. The operation that
is both physical and computable is a **planar cut along the hinge line**: remove wing material from
**z = 114.7635** (the elevon's leading edge at its root station, less the 0.500 mm gap) aft, across
x −205.250…−54.750 and y −1.400…1.808 (the plate's own 2.209 mm + 0.500 mm each side). That is what
a trailing-edge cove is, and its clearance is exact by construction.

| | left | right |
|---|---:|---:|
| elevon ↔ wing, before | 559.093479 | 559.093479 |
| **elevon ↔ wing, after** | **0.000000000** | **0.000000000** |
| wing material removed | **973.493503** | **973.495618** |
| wing volume 1,354,555.798 → | 1,353,582.305 | 1,353,582.303 |
| wing solids after | 1 | 1 |
| clearance delivered, root → tip | 0.500 → 1.213 | 0.500 → 1.213 |

`relief_cove.json`; artefacts `wing_left_reliefrecut.step`, `wing_right_reliefrecut.step`. The
**973.49 mm³** is 414.4 mm³ more than the 559.093479 interference because the cove also removes the
0.500 mm band the elevon does not occupy — that is the cost of a clearance instead of a contact, and
it is 0.072 % of the wing.

**Controls, so a zero cannot be a blind detector.** The same intersect returns 559.093479 on the
uncut wing in the same run; the two sides are independent solids and agree to 0.000000000; a control
box of the same shape placed outboard at z = 200 removes **1,114.388552 mm³**, so the cutter does
bite wing material where material exists; and the earlier compound-call false zero (a plain
`env.intersect(compound)` returning 0.000 for a real 819.6661) is why this measurement fuses first
and reads the *solid*, not the compound.

---

## 5. ZERO: not reached, and here is exactly what is left

The relief clears the wing pair and nothing else, because the other eight pairs have no wing in
them. The trims needed, measured directly against |x| (`trim_min.json`):

| root moved to \|x\| | trim | span left | span lost | can | nozzle | fuselage | wing |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 62.000 | **6.750** | 142.750 | 4.52 % | **0.000** | 120.248 | 95.304 | 559.093 |
| 85.000 | **29.750** | 119.750 | 19.90 % | **0.000** | **0.000** | 95.304 | 559.093 |
| 93.235 | **37.985** | 111.515 | **25.41 %** | **0.000** | **0.000** | **0.000** | 559.093 |
| 94.000 | 38.750 | 110.750 | 25.92 % | 0.000 | 0.000 | 0.000 | 559.093 |

**The binding constraint is the fuselage side wall at 37.985 mm.** The wing column does not move at
all down that table — a root trim cannot touch the wing pair, which is the measured proof that the
two defects are independent.

### 5a. The state table

| state | module (24 parts) | elevon class | **airframe** |
|---|---|---|---|
| **BEFORE**, six as-built Ø42 × 72 | 22 / 331,033.5633 | 12 / 3,194.3429 | **34 / 334,227.9062** |
| delete R1+R2, keep R3, Ø36 × 70 | 0 / 0.0000 | 10 / 2,373.4904 | **10 / 2,373.4904** |
| **+ relief re-cut (EXECUTED)** | 0 / 0.0000 | **8 / 1,255.3034** | **8 / 1,255.3034** |
| + 37.985 mm root trim (measured only) | 0 | 2 / 4.534020 | 2 / 4.534020 |
| + pushrod clevis stops at the horn | 0 | 0 / 0.0000 | **0 / 0.0000** |

**So: ZERO is reachable — in three steps, not one — and the expensive step is the elevon's station,
not the relief.** Of the three, the relief is the only one that touches nothing that flies, and it
is the one that was executed.

### 5b. The cheaper form of step two, which is not executed

The elevon's tip stands at |x| 204.750 against a wing tip at 260.000 — **55.250 mm of unused wing**.
Re-stationing the surface **37.985 mm outboard** (root 93.235, tip 242.735) keeps the **149.5 mm
span and the 40 mm chord** and clears the can, the nozzle and the fuselage by the same numbers,
because all three are radius constraints and the radius only grows. It moves a flying surface, so it
is a wing/tail interface decision and not a machining edit; it is measured here only as a station
shift (`trim_min.json` gives the geometry it would need) and **not executed**.

---

## 6. BOARD CORRECTIONS

1. **"TWO ELEVON PAIRS SURVIVE at 593.069028 mm³."** Two corrections. There are **ten** pairs, not
   two (§1), and `593.069028` is the **as-built Ø42** value — after the sourced Ø36 resize the same
   pair is **409.833025**, so the number does not survive the change it is attached to.
2. **"The airframe total is 26 pairs / 332,674.0818 mm³."** That total added 4 elevon pairs
   (1,640.5185) to the 22-pair module sweep. The **same 12-month-old neighbour set** with the same
   booleans gives **34 pairs / 334,227.9062 mm³** — 8 pairs / 1,553.8244 mm³ more, because the
   elevons were never put against the wing (1,118.186958), the nozzle (240.495128), the 42_6
   fuselage (190.608266) or their pushrods (4.534020).
3. **"TWO ELEVON PAIRS SURVIVE ... at 593.069028" is arithmetically a state mix.** 331,033.5633
   (as-built module) + 1,248.5946 (as-built module after deletion) + 593.069028 cannot be summed;
   the first two are alternative states of the same 22 pairs. The measured sequence is §5a.
4. **The board's "residual 628.32 mm³ of pilot-stub artefact inside the GENUINE class" is
   confirmed as a different population from the 628.119863 mm³ elevon figure.** 4 × π·2.5²·8 =
   **628.318531** is the stub class; **628.119863** is the elevon's per-solid over-count, which the
   fused method already removes. They agree to 0.03 % and are unrelated — a trap waiting for the
   next reader.
5. **The relief: "with_duct_and_elevon_reliefs" is an honest name.** Both reliefs are cut (the duct
   bore at r 42.5, the elevon chord trim at 40.5 mm). What fails is the loft's delivery of the
   second one (§2). Anyone reading the name and assuming the gap exists will get this wrong.

---

## 7. What this does NOT establish

- **The full 63.7 MB assembly was not re-parsed.** The neighbourhood is the 32-part set the two
  prior waves established plus the 19-part static set loaded here. A part outside both is not
  covered; the whole-airframe bbox screen that produced the elevon lead is the prior wave's, and it
  is a screen, not a proof.
- **No relief was added anywhere else.** Only the two wing sectors were re-cut, and only in copies.
- **No aero, mass, stiffness or flutter consequence is assessed** for either the 1,118.19 mm³ of
  wing removed or the 25.41 % span loss the root trim would cost. The trim table is geometry, not
  a control-effectiveness answer.
- **The 0.500 mm gap is the drawing's, not a tolerance stack.** No print/lamination tolerance, no
  hinge slop, no thermal growth is added. A real cove needs a margin this report does not set.
- **The elevon's 2.209 mm thickness is the model's** (the generator scales the NACA section by
  0.55 in y); nobody has weighed or measured a part.
- **One artefact label is known wrong and is superseded, not hidden:** `fab_dm_elevon.json →
  root_trims.fuselage_clear_37.750mm` was keyed by radius (93) and therefore cut at |x| = 137.000,
  a trim of 81.750 mm. Its measured numbers stand; its name is replaced by `trim_min.json` trial C
  (37.985 mm at |x| 93.235).
- **My own first relief execution was wrong and was replaced, not edited.** It subtracted the
  elevon untouched (**zero clearance** — a contact, legally an interference of 0.000000000 that no
  real surface can move inside) after OCC's solid offset returned null for every argument form.
  `fab_dm_elevon.json → relief` still records that run; `relief_cove.json` supersedes it and the
  two exported wing STEPs are from the cove, not from it. Anyone reading only `fab_dm_elevon.json`
  will read the zero-clearance version.

---

## 8. Artefacts and how to reproduce

| file | content |
|---|---|
| `fab_dm_elevon.py` / `fab_dm_elevon.json` | the module baseline + the 32-part elevon sweep at both motor states + the first (superseded, zero-clearance) relief + trim trials + totals |
| `fab_dm_elevon_relief.py` / `relief_cove.json` | **the executed change**: the planar cove with a real 0.500 mm clearance, both wings |
| `probe_offset_method.py` | the OCC solid-offset failure that forced the planar cut (no log: the run was killed mid-hang) |
| `wing_left_reliefrecut.step`, `wing_right_reliefrecut.step` | both wing sectors with the relief re-cut as a solid |
| `relief_tool_left.step`, `relief_tool_right.step` | the superseded zero-gap tool (kept for the record, do not use) |
| `probe_relief_line.py` / `relief_line.json` | the gap-by-station table in §2 — the cause |
| `probe_root_split.py` / `root_split.json` | the split at \|x\| 86.5 that proves the two defect classes are disjoint (§3) |
| `probe_elevon_anatomy.py` / `elevon_anatomy.json` | the five member solids, which one owns each clash |
| `probe_trim_min.py` / `trim_min.json` | the minimum root trim per structure, and the span it costs |
| `probe_parts.py` / `probe_parts.json` | bbox / solids / volume of all 28 candidate parts |
| `probe_left_elevon.py` / `run_probe_left.log` | the first, narrow census that found the wing pair |
| `probe_relief_map.py`, `probe_relief_classifier.py` | two superseded map attempts (3 s per cell, then 15 ms per point); `probe_relief_line.py` replaced both |
| `check_report.py` / `run_check_report.log` | **re-derives every number in this report from the JSON receipts; exits non-zero on drift** |
| `run_*.log` | console receipts, verbatim |

```powershell
cd E:/engineering-portfolio-audit/evidence/fab-dm-elevon
& "C:/Program Files/Python312/python.exe" probe_parts.py             #  8 s
& "C:/Program Files/Python312/python.exe" probe_elevon_anatomy.py    # 20 s
& "C:/Program Files/Python312/python.exe" probe_relief_line.py       # 28 s
& "C:/Program Files/Python312/python.exe" probe_trim_min.py          # 180 s
& "C:/Program Files/Python312/python.exe" fab_dm_elevon.py           # 320 s, writes json + STEPs
& "C:/Program Files/Python312/python.exe" fab_dm_elevon_relief.py    #  58 s, writes the two wings
& "C:/Program Files/Python312/python.exe" check_report.py            # asserts this report
```

Inputs are read-only: `repos/drone-mech/highspeed_edf/deliverables/phase15_geometry/step/*.step`.
No file under `repos/drone-mech` was written; no git command was run; nothing was committed.

---

## 9. Status line for `AGENT_BOARD.md` (for the lead to merge — I did not write outside my folder)

```
| fab-dm-elevon | ELEVON CLASS MEASURED AND HALVED. The board's "2 elevon pairs / 593.069028" is
| both too few and the wrong state: at the final motor state (R3, Ø36x70) the elevon class is
| 10 pairs / 2,373.4904, and 593.069028 is the AS-BUILT Ø42 value of the can pair (Ø36 -> 409.833025).
| Pairs no sweep had: elevon<->wing 2 x 559.093479, <->nozzle 2 x 120.247564, <->42_6 2 x 95.304133,
| <->pushrod 2 x 2.267010. Whole as-built airframe = 34 pairs / 334,227.9062, not 26 / 332,674.0818.
| CAUSE, wing pair: the relief IS cut (chord -= 40.5 mm, generator :321-322) but a ruled=False loft
| delivers a -10.754 mm interference at x=-170 where the table promises +0.499; the whole clash sits
| in ONE loft bay, x -199.75..-131.06. CAUSE, other 8 pairs: elevon root at r 11.250 from the duct
| axis = 31.25 mm inside the Ø85 bore; there is NO wing inboard of r 42.5, so no relief can reach it.
| EXECUTED: planar cove, 0.500 mm forward of the elevon LE and 0.500 mm clear each side, copies
| only -> 559.093479 -> 0.000000000 both sides, 973.493503 mm3 of wing removed per side.
| DISJOINTNESS PROOF: split the plate at |x| 86.5 (the bore relief); inboard half has wing 0.000000
| and can 409.833028, outboard half has wing 559.093478 and can 0.000000. Final airframe
| 8 pairs / 1,255.3034 mm3. ZERO NOT reached.
| Needed for zero: 37.985 mm root trim (span -25.41 %) + pushrod clevis at the horn, both MEASURED not
| executed. Cheaper form: re-station the surface 37.985 mm outboard, span and chord preserved.
```
