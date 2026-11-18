# FAB-DM-FINAL — the eight remaining pairs, what each one is, and the one change that takes the airframe to zero

**Scope:** drone-mech airframe, `repos/drone-mech/highspeed_edf/deliverables/phase15_geometry/`
(branch `work/2026-11-11`), **read-only**. No file under `repos/` was written; no git command was
run; nothing was committed. Every artefact lives in `evidence/fab-dm-final/`; every geometry that
changed is a **copy** written there.

**Provenance:** every volume in this report is a **native OpenCascade boolean** (`BRepAlgoAPI`
through CadQuery 2.7.0 / OCP 7.8.1.1 on `C:/Program Files/Python312/python.exe`). Nothing is a
solver, a surrogate, an estimate or a composed aggregate. Where a number is arithmetic it says so.

**Self-check:** `check_report.py` re-derives all **95** asserted numbers from the JSON receipts and
exits non-zero on drift. It passes (`run_check_report.log`).

---

## VERDICT

**1. The eight pairs are identified, and they are not one story — they are two.** Six are a genuine
design clash with a single cause; two are a modelling artefact and come **out** of the count.

| class | pairs | volume mm³ |
|---|---:|---:|
| genuine design clash | **6** | **1,250.769445** |
| modelling artefact (pushrod representative) | **2** | **4.534020** |
| intentional contact (press-fit / thread / bonded) | **0** | **0** |
| **total as the board carries it** | **8** | **1,255.303466** |

**2. The six genuine pairs have ONE cause — the elevon's root station.** The plate's root stands at
`|x| = 55.250`, i.e. `r = 11.250` from the duct axis at `|x| = 44`. Three structures stand in its
path and each has a measured boundary: the motor can's reserved `r 18` (root must be ≥ 62.000), the
nozzle shell at `r 38.978…41.000` (≥ 85.000), and the fuselage side wall at `|x| 90.586…93.235`
(≥ 93.235). So a third of the plate is cantilevered through the duct exit and a further 2.65 mm
through the fuselage's own side wall. It is **not** an undersized relief (that was the wing pair,
already cut) and **not** a hinge-axis error (measured: the mid and tip knuckles are clean).

**3. The two artefact pairs are a 38 mm Ø2 rod that is not a linkage.** It is 6.000 mm clear of its
own servo mount with **0.000000 mm³** contact, its only contact with the horn is a **0.831215 mm³**
corner clip, and it ends **21.6915 mm past the plate in free air**. The generator calls it a
"pushrod representative" (`phase15_generate_geometry.py:1010`) and builds it as a fixed cylinder
(`:1015-1016`). Removed from the count, not fixed — §4.

**4. The minimum change was EXECUTED, in the smallest form that clears the plate:** the elevon moves
**+38.485 mm outboard** (root 55.250 → 93.735, tip 204.750 → 243.235, span 149.5 mm and chord
40 mm **unchanged**), and the wing's aft-chord cove is extended over the new band, removing
**9,753.948578 / 9,753.946712 mm³** per side. Can, nozzle, fuselage and wing pairs all measure
**0.000000000** afterwards.

**5. ZERO IS REACHED.** Final airframe interference, genuine class:
**0 pairs / 0.0000 mm³.** The only thing left in the sweep is the 2 artefact pairs,
**4.010114 mm³**, which are excluded by classification and stated, not hidden.

**6. What it costs, named:** a tail-interface change — the elevon's station moves 38.485 mm
outboard, its hinge line moves with it, the horn goes from `|x| 121…139` to `159.485…177.485`, and
the pushrod must be re-drawn (the servo mount stays at `|x| 125`, now 34.485 mm inboard of the
horn). **No duct-module change and no span loss.** The root-trim alternative is measured and
**not** executed: it costs **25.41 %** of the flying surface (§6).

---

## 1. The eight pairs, identified

Measured on the delivered artefact — the prior wave's cove re-cut into both wing sectors, with the
left copy's orientation repaired (§8.1) — by a 4-mover × 32-neighbour sweep plus the two corrected
motor envelopes. Receipt: `fab_dm_final.json → state_delivered`.

| # | pair | volume mm³ | what the overlap actually is |
|---:|---|---:|---|
| 1 | `elevon_left` ↔ `motor_A_R3` envelope | **409.833027583** | plate's inboard end, x −62.000…−55.250, y ±1.5, z 115.2635…155.2957. **100 % inboard** of \|x\| 86.5. By member: panel 405.280696, root knuckle 26.396631, and the fusion removes 21.844298 of the knuckle that lies inside the panel (distinct knuckle share **4.552332**). Inside the can's reserved cylinder `r 18` about (−44, 0) |
| 2 | `elevon_right` ↔ `motor_B_R3` | **409.833022484** | mirrored; 6.1 × 10⁻⁶ mm³ apart from #1 |
| 3 | `elevon_left` ↔ `duct_A_separate_nozzle_and_exit_lip` | **120.247564436** | x −85.000…−82.978 = `r 38.978…41.000` about the duct axis; y −0.9002…1.3085; z 115.3958…155.4054. The plate crosses the **nozzle shell wall** |
| 4 | `elevon_right` ↔ nozzle B | **120.247564437** | mirrored |
| 5 | `elevon_left` ↔ `fuselage_battery_bay_shell_endpoint_relief_42_6` | **95.304133195** | x −93.2353…−90.5865; y −0.9002…1.3085; z 115.438…155.442. **100 % outboard** of \|x\| 86.5. Caught in the fuselage side-wall solid (x −95.282…−56.281, 20,808.296 mm³) |
| 6 | `elevon_right` ↔ 42_6 | **95.304133199** | mirrored |
| 7 | `elevon_left` ↔ `elevon_pushrod_left` | **2.267010111** | x −126.000…−124.000, y −2.000…0.5908, z 115.5918…117.000 |
| 8 | `elevon_right` ↔ `elevon_pushrod_right` | **2.267010118** | mirrored |
| | **sum** | **1,255.303465563** | |

**The sum reproduces the board's figure, and here is exactly how far.** Direct summation of the eight
exact pair volumes gives **1,255.303465563 mm³**. The board's `1,255.3034` was never a measured sum:
it is the composition `2,373.4904 − 1,118.186958 = 1,255.303442` — a rounded class aggregate minus a
rounded relief total. The direct sum is **2.3563 × 10⁻⁵ mm³** above that composition (relative
1.88 × 10⁻⁸), which is the rounding of the two aggregates, not a geometric difference. Both render as
`1,255.3034` at 4 dp; the number of record is **1,255.303466**.

Every individual pair also reproduces the prior wave's per-pair table to < 1 × 10⁻⁶
(`fab_dm_final.json → pair_reproduction`, 8/8 `pass`).

---

## 2. Classification, one pair at a time

| # | pair | class | why |
|---:|---|---|---|
| 1, 2 | elevon ↔ motor can envelope | **genuine design clash** | A bounding envelope that reserves the sourced motor's volume is an interface constraint, not geometry to negotiate. The plate occupies space the Ø36 × 70 can and its Ø5 × 17 shaft must have. The envelope is `spec:302` tier, and the can was already resized from Ø42 × 72 to Ø36 × 70 for exactly this class |
| 3, 4 | elevon ↔ nozzle shell | **genuine design clash** | The nozzle is a fixed structural shell (`r 38.978…41.000`, z 110…242). The plate passes through the wall |
| 5, 6 | elevon ↔ fuselage 42_6 | **genuine design clash** | The 42_6 side wall is structure. A moving surface cannot pass through it. Note it is caught by **every** 42_6 variant in the deliverable — `candidate_brep`, `compoundcut_repair`, `compoundcut_repair_order2`, `endpoint_relief`, `endpoint_relief_42_6` **all read 95.304133201** — so it is not an artefact of any one Boolean repair state |
| 7, 8 | elevon ↔ pushrod | **modelling artefact** | see §3 |

**Intentional contacts: none.** The one interference-fit-like feature in the model — the 2.500 mm
shaft in the 2.525 mm hub bore — is modelled with 0.025 mm radial clearance and measures 0.000 mm³
(`evidence/fab-dm-interference/REPORT.md:99`). No bonded joint or thread engagement is inside the
eight.

**Re-reported, artefact removed from the count:**

| | pairs | volume mm³ |
|---|---:|---:|
| as carried | 8 | 1,255.303466 |
| **artefact removed (7, 8)** | **6** | **1,250.769445** |
| residual artefact, stated and excluded | 2 | 4.534020 |

---

## 3. Why the pushrod pair is an artefact, measured four ways

The part is `elevon_pushrod_{left,right}.step`: one solid, **119.380521 mm³** = `π·1²·38`, bbox
x ±(124…126), y −15…23, z 115…117 — a Ø2 × 38 mm cylinder on the axis `(±125, −15, 116)` pointing
straight aft in +y (`phase15_generate_geometry.py:1015-1016`).

| test | result | what it means |
|---|---|---|
| distance to its own servo mount | **6.000 mm**, contact **0.000000 mm³** | it does not reach the thing that must drive it |
| distance to the horn, and contact | 0 mm bbox-touch; intersection **0.831215 mm³** of a 360.000 mm³ horn | its only attachment is a 0.38 mm clip of the horn's bottom-front corner |
| where it ends | **21.6915 mm past the panel's own y extent**, in free air | it is not a link, it is a rod lying across the surface |
| how much of it is inside the plate | 1.90 % of its volume | the rest is a cantilever with no load path |
| source intent | `:1010` "pushrod representatives"; `:1012` servo centre (±125, −27, 112) | the model's own words are "representative" |

**Disposition: removed from the count, not fixed.** A real pushrod terminates at a clevis on the
horn and at the servo arm; re-drawing it is a modelling task that is **already compulsory** after the
station change in §5 (the horn moves 38.485 mm outboard), so paying for it twice would be the
expensive choice. The number it costs the airframe is **4.534020 mm³ as delivered, 4.010114 mm³ after
the station change** — stated, not folded into a genuine total.

---

## 4. Cause of each genuine pair, against the four candidate classes

The decisive measurement is a root-trim ladder: cut the plate at `|x| = x_keep` and re-measure each
structure (`fab_dm_final.json → root_trim_ladder`).

| root moved to \|x\| | trim mm | span left mm | span lost | ↔ can | ↔ nozzle | ↔ fuselage |
|---:|---:|---:|---:|---:|---:|---:|
| 62.000 | 6.750 | 142.750 | 4.52 % | **0.000000** | 120.247564 | 95.304133 |
| 85.000 | 29.750 | 119.750 | 19.90 % | 0.000000 | **0.000000** | 95.304133 |
| 93.235 | 37.985 | 111.515 | 25.41 % | 0.000000 | 0.000000 | **0.000000981** |
| 93.735 | 38.485 | 111.015 | 25.74 % | 0.000000 | 0.000000 | **0.000000000** |

| pair class | cause | the measured boundary |
|---|---|---|
| 1, 2 (can) | **wrong station** — the root sits 6.750 mm too deep for the can's `r 18` | clears at root `|x| = 62.000` |
| 3, 4 (nozzle) | **a part passing through structure** — the plate crosses the nozzle shell wall; the same station error, three times larger | clears at `|x| = 85.000` (`r 41.000`) |
| 5, 6 (fuselage) | **a part passing through structure** — the plate crosses the side wall; this is the binding constraint | clears at `|x| = 93.235`, and there it is only *tangent* (9.81 × 10⁻⁷ mm³) — a real clearance needs 93.735 |

**The two classes it is NOT, both by measurement:**

- **Not an undersized relief.** The relief *was* undersized — by 11.254 mm of chord, delivered as
  −10.754 mm interference at x = −170 against a nominal +0.500 — and it produced the two
  elevon↔wing pairs at **559.093479** each. The executed cove took those to **0.000000000**. Those
  pairs are gone and are not in the eight. A relief is a cut in the wing; measured, the can, nozzle
  and fuselage pairs are **100 % where the wing is not** (split at the duct bore `|x| 86.5`: can in
  409.833027 / out 0.000, nozzle in 120.247564 / out 0.000, fuselage in −4 × 10⁻⁹ / out
  95.304133). No wing-side cut can reach them.
- **Not a hinge-axis error.** The three knuckle pins are collinear: `z 126.12…129.12`, `y ±1.5`, at
  `|x| 58.25…64.25 / 127…133 / 195.75…201.75`. Only the **root** knuckle is inside anything (the can,
  26.396631 mm³, and it lies inside the panel there). The mid and tip knuckles measure **0.000000**
  against the can, the nozzle, the fuselage and the wing. A hinge-axis error would put all three in
  the same place; they are not.

---

## 5. The change, executed on copies, per step

**Step 1 — the cove (executed by the prior wave, re-measured here and not counted as new work).**
Planar cut along the hinge line: wing minus a box `x |54.750…205.250|`, `y −1.4002…1.8085`,
`z 114.7635…204.7635`. Both wings reimport at **1,353,582.304799 / 1,353,582.302684 mm³** against the
repo originals at **1,354,555.798301** — i.e. **973.493502 / 973.495617 mm³** removed, reproducing
`evidence/fab-dm-elevon/relief_cove.json` to 1 × 10⁻⁶. Effect: elevon↔wing **559.093478510 →
0.000000000** (both sides).

**Step 2 — the station change and the minimum cove extension (EXECUTED here).**
Each elevon solid (panel + horn + three knuckles, fused) is translated **±38.485 mm** outboard; the
new bbox is `x ∓(93.735…243.235)`, `y −2.0…1.5`, `z 115.2635…155.9765`. The wing's cove is extended
over the new band with the **smallest** box that clears the plate:
`x |204.750…243.750|`, `y −3.0…3.0`, `z 114.7635…157.000`.

| | left | right |
|---|---:|---:|
| wing before | 1,353,582.304799 | 1,353,582.302684 |
| wing after | 1,343,828.356221 | 1,343,828.355972 |
| material removed | **9,753.948578** | **9,753.946712** |
| elevon ↔ wing after | **0.000000000** | **0.000000000** |

Of that removal, **9,639.731506 mm³ lies below z = 156.5** — the drawing's own trailing edge at the
band's inboard end is 156.052, so ~99 % of the cut is real aft-chord airfoil and the last 114.2 mm³ is
the 0.5 mm above the table.

**The cut height is a measured choice, not a guess.** A 90 mm tall box — the height the first cove
used — removes **20,124.221163 / 20,124.218962 mm³**, i.e. **10,370.272585 mm³ per side more**, and
that extra is not wing trailing edge: it is the loft artefact of §8.2. Cutting only to `z = 157.000`
clears a plate whose own top is `155.9765` and leaves the artefact in place to be reported rather
than quietly deleted.

**Pair-by-pair, before → after (both sides independently):**

| pair | before | after | Δ |
|---|---:|---:|---:|
| elevon ↔ motor can envelope | 409.833027583 | **0.000000000** | −409.833027583 |
| elevon ↔ motor can envelope | 409.833022484 | **0.000000000** | −409.833022484 |
| elevon ↔ nozzle shell | 120.247564436 | **0.000000000** | −120.247564436 |
| elevon ↔ nozzle shell | 120.247564437 | **0.000000000** | −120.247564437 |
| elevon ↔ fuselage 42_6 | 95.304133195 | **0.000000000** | −95.304133195 |
| elevon ↔ fuselage 42_6 | 95.304133199 | **0.000000000** | −95.304133199 |
| elevon ↔ pushrod (artefact) | 2.267010111 | 2.005056961 | −0.261953150 |
| elevon ↔ pushrod (artefact) | 2.267010118 | 2.005056963 | −0.261953155 |
| **total** | **1,255.303465563** | **4.010113924** | **−1,251.293351639** |

**Step 3 — the artefact, removed from the count, not fixed.** 4.010113924 mm³ of pushrod
representative, per §3.

### The state sequence, now measured end to end

| state | module (23 neighbours) | elevon class | **airframe** |
|---|---|---|---|
| as-built, six Ø42 × 72 | 22 / 331,033.5633 | 12 / 3,194.3429 | **34 / 334,227.9062** |
| motor fix: R3 only, Ø36 × 70 | **0 / 0.0000** | 10 / 2,373.4904 | **10 / 2,373.4904** |
| + cove (executed) | 0 / 0.0000 | **8 / 1,255.303466** | **8 / 1,255.303466** |
| − artefact from the count | 0 | **6 / 1,250.769445** | **6 / 1,250.769445** |
| + station change (EXECUTED) | 0 / 0.0000 | 2 / 4.010114 (artefact) | 2 / 4.010114 |
| − artefact from the count | 0 | **0 / 0.000000** | **0 / 0.000000** |

The module row is re-measured in this run, not carried: `fab_dm_final.json → module_final_state` is
**0 pairs / 0.000000 mm³**.

---

## 6. Zero: reached, and what it would take to reach it the other way

**ZERO IS REACHED as a measured state**, at **0 pairs / 0.0000 mm³** genuine, on a copy, by:

1. one station change — the elevon **+38.485 mm outboard** (span 149.5 mm and chord 40 mm preserved);
2. the wing cove extended over the new band — **9,753.95 mm³ per side** of aft-chord airfoil;
3. the pushrod re-drawn as a real link (compulsory after 1, and 4.010114 mm³ of placeholder is the
   only thing the sweep still sees).

**The alternative that was measured and NOT executed: a root trim.** It clears the same three
structures by deleting the inboard end of the flying surface instead of moving it:

| trim | span left | span lost | what it clears | what it does not |
|---:|---:|---:|---|---|
| 6.750 mm | 142.750 | 4.52 % | the can | nozzle, fuselage |
| 29.750 mm | 119.750 | 19.90 % | the can, the nozzle | fuselage |
| **37.985 mm** | **111.515** | **25.41 %** | all three, but **tangent** to the wall (9.81 × 10⁻⁷ mm³) | — |
| 38.485 mm | 111.015 | 25.74 % | all three with 0.500 mm clearance | — |

**A quarter of the flying surface for one machining edit is the expensive choice**, so the
span-preserving station change was the one executed. On the owner principle — more spend now, less
effort later — the trim would have bought a cheaper cut and a worse aircraft.

**What is honestly NOT established about the executed change** is in §9. The one thing a reviewer
must know before believing the zero: the wing sector outboard of `|x| 204.750` is a **loft
artefact**, so the fixture the moved plate now sits in does not exist in the drawing's own table
(§8.2). The plate's space is real — the cove is a chord trim of `114.7635…157.000`, which is the
drawing's own relief form — but the surrounding solid out there is not.

---

## 7. Controls — so a zero cannot be a dead detector

| control | result | what it proves |
|---|---|---|
| delivered elevon ↔ the **repo** (uncut) wing, same process, same call | **559.093478510 / 559.093478515** | the detector is live: the same code that reports 0.000000000 against the cut wing reports 559.09 against the uncut one |
| moved elevon ↔ the delivered wing **without** the cove extension | **2,290.930691819** both sides | the cove extension is the operation that clears the moved plate, and without it the station change would create a 2,290.93 mm³ clash |
| elevon ↔ the corrected Ø5 × 17 shaft alone | **0.000000000** both sides | none of the six stub elements (§8.4) is inside any of the eight |
| orientation, two-sided: reverse the correct right wing | elevon pair **0.000000 → 9,226.872345** | the sign of the volume is the whole diagnosis, and it fails both ways (§8.1) |
| 83-file bbox screen of every part in the deliverable | 32 hits, every one a known part or a self-pair | the 32-part pool is not hiding a ninth pair (§8.5) |

---

## 8. Four defects found on the way — each one changes a number the board carries

### 8.1 The delivered left wing re-imports orientation-reversed, and every pair against it was never measured

`wing_left_reliefrecut.step` imports at **−1,353,582.304799 mm³**. Against a reversed solid a
boolean is meaningless: `elevon_left ∩ wing_left` returns **9,226.872345 mm³** — the elevon's *own*
volume, i.e. "the whole plate is inside the wing". Reversing the shape (`TopoDS_Shape.Reverse`)
restores **+1,353,582.304799** and the pair measures **0.000000000**. The control runs both ways:
reversing the *correct* right wing flips it to −1,353,582.302684 and turns its 0.000000 into
9,226.872345.

**Cause, in the source:** `phase15_generate_geometry.py:922-925` deliberately reverses the port wing
solid before writing STEP —

```python
if label == "left":
    # Reversed orientation is the OCCT STEP-writer convention needed for
    # a positive-volume round-trip of the mirrored port wing sector.
    placed_solid = cq.Solid(wing_solid.wrapped.Reversed())
```

The convention holds for the generator's own export path and is **not** inherited by a re-export of a
cut result. So the prior wave's two "re-cut" copies cannot be measured as delivered, and the board's
`8 pairs / 1,255.3034` was **composed** (`2,373.4904 − 1,118.186958`), never re-measured on the
artefact. **This report measures it directly for the first time: 8 pairs / 1,255.303465563 mm³, every
pair within 1 × 10⁻⁶ of the prior table.** The composed figure was right; the method was not.

### 8.2 The wing sector outboard of |x| 204.750 carries up to 109 mm of phantom trailing edge

The same `ruled=False` loft that under-delivered the relief (`:333-335`) **over**-delivers past the
band. Cutting 0.5 mm slabs and comparing the solid's own extent to the generator's table
(`te(x) = 155 + 1.243·|x|/260`, `:311-316`):

| x | solid's section z | table's TE | **overshoot** |
|---:|---|---:|---:|
| 206.0 | −173.432…182.419 | 155.985 | **+26.434** |
| 215.0 | −165.860…244.114 | 156.028 | **+88.086** |
| 220.0 | −162.541…258.356 | 156.052 | **+102.305** |
| 225.0 | −159.593…265.470 | 156.076 | **+109.394** |
| 243.0 | −151.704…246.059 | 156.162 | **+89.897** |
| 259.0 | −148.775…165.678 | 156.238 | **+9.440** |

**Material above the table's own trailing edge, outboard of |x| 204.750: 41,775.812500 mm³ (right)
/ 41,775.812222 mm³ (left)** — **3.09 %** of the 1,353,582 mm³ sector, and identical on both sides
because both come from the same loft. This is the same defect class as the −10.754 mm relief
under-delivery, with the opposite sign, in the same loft. **It is not fixed here** — it is not part of
the eight and fixing it is a wing-loft change with mass and aero consequences nobody has assessed. It
is why the station change's cove must be cut at `z ≤ 157.000` and why the 90 mm box was rejected.

### 8.3 The board's `593.069028` is the repo's own Ø42 × 72 envelope, not the sourced Ø36

The screen found the delivered elevon against the **repo's own** envelope files:

| repo envelope file | elevon pair mm³ |
|---|---:|
| `motor_B_R3_3670_42x72_envelope.step` | **593.069028163** |
| `motor_B_R2_3670_42x72_envelope.step` | **227.190222963** |
| `motor_B_R1_3670_42x72_envelope.step` | absent (R1 is at z = 20, the plate at z ≥ 115.26) |

So `593.069028` is the **as-built Ø42 × 72** pair, exactly as the prior wave said — but it is also
better evidence than that: it is the **deliverable's own envelope file**, and it means the
as-delivered airframe carries **two** elevon↔can pairs per side (R2 and R3). The as-built elevon
class then recomposes exactly:

```
2,373.4904  +  2 × (593.069028163 − 409.833027583)  +  2 × 227.190222963
= 2,373.4904 + 366.472001 + 454.380446 = 3,194.342847   vs the board's 3,194.3429
```

### 8.4 The 942.478 mm³ stub artefact is exactly six elements, and none of it is in the eight

`6 × π·2.5²·8 = 942.477796 mm³`, i.e. **three stub-in-neighbour-can pairs per duct**: R2's stub
(z 48…56) lies inside R1's can (z 20…92), and R3's stub (z 84…92) lies inside **both** R1's can and
R2's can (z 56…128). The board's 942.478 is that sum to 3 dp (Δ −2.0 × 10⁻⁴ = rounding).

**None of it survives into the final state, and that is measured, not assumed:** the corrected
envelope's shaft is Ø5 × 17 at `z 75…92`, which is **below** the plate (`z ≥ 115.2635`), and
`elevon ∩ shaft = 0.000000000` on both sides.

### 8.5 The 32-part pool is complete, by a screen of all 83 parts

Every `*.step` in `step/` was bbox-screened against four mover states (both elevons as delivered, both
elevons moved, both pushrods): **83 files, 81 screened, 2 skipped** (`phase15_airframe_full_assembly`
63.7 MB and `phase15_twin_ducts_and_fans` 54.0 MB — aggregates of parts screened individually), **32
booleans hit**. Every hit is one of: the two wings, the nozzle, a 42_6 variant, a repo envelope, a
pushrod, or the mover against its own file / its own old station. **No ninth pair exists.**

*One arithmetic lesson the screen re-taught:* the same pushrod pair reads **2.464577** when the
elevon is left as a 5-solid compound (pairwise sums double-count) and **2.267010** when it is fused
first — the 0.197567 difference is the 248.000 mm³ elevon self-overlap. Fuse before you measure.

---

## 9. What this does NOT establish

- **The 63.7 MB full assembly was not re-parsed.** The screen covers the 81 individually-written
  parts in `step/`; the two aggregates were skipped by size and by the fact that their members are
  among the 81. A part that exists only inside an aggregate is not covered.
- **No aero, mass, stiffness or flutter consequence is assessed** for the 9,753.95 mm³ per side of
  wing cove removed or for the 38.485 mm station change. The wing's CAD is a solid envelope while the
  mass model bills skin area × 1.2 mm, so quoting a mass from 9,754 mm³ would be a category error —
  no mass is claimed.
- **The 0.500 mm clearance is the drawing's own `ELEVON_GAP`, not a tolerance stack.** No lamination
  tolerance, hinge slop or thermal growth is added. A production cove needs a margin this report does
  not set.
- **The 41,775.81 mm³ phantom outboard (§8.2) is left in place.** It does not touch the moved plate,
  but it means the outboard wing solid is not a manufacturable surface and anyone mounting anything
  there is working against an artefact.
- **The pushrod is not re-drawn.** Its 4.010114 mm³ is excluded by classification; a real link has
  not been built or measured.
- **The station change is a tail-interface decision, executed on a copy for measurement only.** It
  has not been carried into the design intent, and it moves a flying surface.

---

## 10. Artefacts and how to reproduce

| file | content |
|---|---|
| `fab_dm_final.py` / `fab_dm_final.json` | the delivered-state sweep (8 pairs), the classification evidence, the station change, the changed sweep (2 pairs), the controls, the trim ladder, the orientation repair receipts |
| `probe_features.py` / `probe_features.json` | per-pair feature bboxes, the in/outboard split at the duct bore, the elevon's five members, the pushrod's joints |
| `probe_orientation.py` / `probe_orientation.json` | the reversed left wing and the two-sided proof that the sign is the diagnosis |
| `probe_cove_min.py` / `probe_cove_min.json` | **the executed minimum cove**: 9,753.95 mm³ per side, pair 0.000000000 |
| `probe_bulge.py` / `probe_bulge.json` | the overshoot-by-station table and the 20,124.22 split (9,639.73 below z 156.5 / 10,484.49 above) |
| `probe_phantom.py` / `probe_phantom.json` | 41,775.81 mm³ above the table's own TE, outboard |
| `probe_section.py` / `probe_section.json` | the same finding from 0.5 mm slabs |
| `probe_screen.py` / `probe_screen.json` | all 83 parts vs all 4 movers; 32 hits, 2 size skips |
| `elevon_{left,right}_station_plus38.485.step` | the plate at its new station (copies) |
| `wing_{left,right}_cove_extension.step` | the wing with the 90 mm extension (superseded — kept so the rejected height is auditable) |
| `wing_{left,right}_cove_min.step` | **the delivered change** (cove to z 157.000) |
| `check_report.py` / `run_check_report.log` | **re-derives all 95 numbers in this report; exits non-zero on drift** |
| `run_*.log` | console receipts, verbatim — including `run_fab_dm_final_v1_inverted_wing.log`, the corrupted-boolean run that found §8.1 |

```powershell
cd E:/engineering-portfolio-audit/evidence/fab-dm-final
& "C:/Program Files/Python312/python.exe" probe_features.py       #  39 s
& "C:/Program Files/Python312/python.exe" probe_orientation.py    #  40 s
& "C:/Program Files/Python312/python.exe" fab_dm_final.py         # 201 s, writes json + 4 STEPs
& "C:/Program Files/Python312/python.exe" probe_cove_min.py       #  30 s, the executed change
& "C:/Program Files/Python312/python.exe" probe_bulge.py          #  23 s
& "C:/Program Files/Python312/python.exe" probe_phantom.py        #   9 s
& "C:/Program Files/Python312/python.exe" probe_screen.py         # 213 s
& "C:/Program Files/Python312/python.exe" check_report.py         #  < 1 s, 95/95 PASS
```

Inputs are read-only: `repos/drone-mech/highspeed_edf/deliverables/phase15_geometry/step/*.step`,
plus the prior wave's two wing copies in `evidence/fab-dm-elevon/` (read, orientation-repaired in
memory, never modified). No file under `repos/drone-mech` was written; no git command was run.

---

## 11. Status line for `AGENT_BOARD.md` (for the lead to merge — I did not write outside my folder)

```
| fab-dm-final | AIRFRAME INTERFERENCE = ZERO, MEASURED, ON A COPY. The 8 pairs / 1,255.3034 are
| re-measured at last (they were only ever composed): 8 / 1,255.303465563 = 2 x can envelope
| 409.833027583 + 409.833022484, 2 x nozzle shell 120.247564436 + 120.247564437, 2 x 42_6 side wall
| 95.304133195 + 95.304133199, 2 x pushrod 2.267010111 + 2.267010118. CLASSIFIED: 6 genuine /
| 1,250.769445 (one cause: the elevon root at |x| 55.250 = r 11.250 is 6.750 mm inside the can's
| r 18, 31.25 mm inside the duct bore, and 2.649 mm through the fuselage side wall at |x| 90.586..
| 93.235) + 2 MODELLING ARTEFACT 4.534020 (a Ø2x38 rod 6.000 mm clear of its own servo, 0.831215
| mm3 corner-clip of the horn, ending 21.6915 mm past the plate in free air) + 0 intentional.
| EXECUTED: elevon +38.485 mm outboard (root 93.735, span 149.5 and chord 40 PRESERVED) + cove
| extended over |x| 204.75..243.75 to z 157.000, removing 9,753.948578 / 9,753.946712 mm3 ->
| can/nozzle/fuselage/wing all 0.000000000, airframe 2 pairs / 4.010114 = the artefact only.
| ZERO REACHED: 0 pairs / 0.0000 mm3 genuine. The root-trim alternative (37.985 mm, 25.41 % span)
| is measured and NOT executed. THREE CORRECTIONS: (1) wing_left_reliefrecut.step reimports
| orientation-REVERSED (-1,353,582.305) and every boolean against it lies (returns the elevon's
| own 9,226.872345) - cause phase15_generate_geometry.py:922-925; (2) the wing sector outboard of
| |x| 204.750 carries 41,775.812 mm3 (3.09 %) above its OWN station table's trailing edge, overshoot
| +109.394 mm at x=225 - same loft as the -10.754 relief, opposite sign, NOT fixed; (3) the board's
| 593.069028 is the repo's own Ø42x72 R3 envelope (R2 adds 227.190223), reconciling the as-built
| elevon class to 3,194.342847. The 942.478 stub artefact = 6 x pi*2.5^2*8 and none of it is in
| the eight (elevon vs shaft = 0.000000000). 83-file screen: no ninth pair. 95/95 self-checks pass.
```
