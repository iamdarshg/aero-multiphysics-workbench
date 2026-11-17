# dm-body-wing — the body ↔ lifting-wing interference: located, classified (c), fixed to 0.000000

STATUS: **COMPLETE** — both pairs located to the coordinate and to three disjoint patches; the
condition classified as a **modelling artefact (c)**, not a joint and not a clash; the fix executed
as a boolean (**wing root trimmed to the fuselage skin**), verified by three independent
instruments; the closure sweep re-run on the fixed assembly. **The two rows go 3,781.632735 /
3,781.632740 → 0.000000, and the authoritative airframe total becomes 26 pairs / 5,415.519830 mm3
with a set diff of exactly −2 pairs / −7,563.265475 mm3 and nothing else moved.** The fuselage is
byte-identical (206,454.319709 mm3 / 320.0042 g, 1 solid, walls 1.0921 / 1.1990 / 1.1800). No repo
write, no commit, no reset.

Scope: the one task — locate, classify and fix the two `fuselage ↔ lifting-wing sector` interference
pairs that carry **7,563.265475 mm3 of the authoritative 12,978.785305 mm3 (58.3 %)**. Input read-only from
`repos/drone-mech/highspeed_edf/deliverables/phase15_geometry/` and from the copies already taken in
`evidence/dm-interference-reconcile/work/obj/`. All work on COPIES in this directory. No repo write, no
commit, no reset, nothing written to `D:\CodeProjects` or `E:\1vm\TMP`.

---

## 0. Baseline carried in (from `dm-interference-reconcile`, closure basis C-28)

| class | pairs | mm3 |
|---|---:|---:|
| A1 elevon-root clash | 10 | 3,264.547867 |
| A2 pushrod artefact | 2 | 4.929154 |
| **B body ↔ lifting-wing sector** | **2** | **7,563.265475** |
| C static bonded-joint overlap | 14 | 2,146.042809 |
| **total C-28** | **28** | **12,978.785305** |

Ring v2 = 0 pairs / 0.000000. Fuselage DM-FUS-001 REV 1 = 206,454.319709 mm3 / 320.0042 g,
1 solid / 540 faces, sha256 `d9ba7aeb7716cdd1ba4f289d…`.

**Skeleton was written first and every section was appended as its step landed**, per the brief.

---

## 1. The two pairs, located

### 1a. The parts, named exactly and measured

| file | solids | faces | volume mm3 | bbox (x, y, z) |
|---|---:|---:|---:|---|
| `drone-mech_fuselage_rev1.step` (DM-FUS-001 REV 1, sha256 `d9ba7aeb…`) | **1** | 540 | **206,454.319709** | x ±105.891846, y −48.458738…45.413633, z −360…280 |
| `lifting_wing_left_sector_with_duct_and_elevon_reliefs.step` | 1 | 51 | 1,354,555.798302 | x **−260.000000…−80.329704**, y −13.719369…25.371289, z −231.711291…266.895886 |
| `lifting_wing_right_sector_with_duct_and_elevon_reliefs.step` | 1 | 52 | 1,354,555.798302 | x **+80.329704…+260.000000**, mirror of the left, y/z identical |
| `lifting_wing_centre_bridge_sector_…` | 1 | 52 | 57,099.460704 | x ±8.96393, y −12.423965…24.056678, z −270…155.053582 |

The two sector files are exact mirrors: same volume to 9 dp (1,354,555.798302), same y/z
extent, x-sign flipped. So the two interference rows are one geometric condition made twice,
and the second row must equal the first to the last digit it is measured to.

**Pair 1** = `fuselage_rev1` × `wing_left` → **3,781.632735 mm3**
**Pair 2** = `fuselage_rev1` × `wing_right` → **3,781.632740 mm3**
**Sum = 7,563.265475 mm3** (the value this task was given; reproduced row-level in §1c).

The 5 × 10⁻⁶ mm3 difference between the two rows is the mirror-image boolean noise seen
through the same instrument (the two operands are byte-different files, 728,201 B vs
861,011 B — the right sector carries 52 faces against the left's 51).

### 1b. Where the overlap is — coordinates, not adjectives

The overlap is **not** at a root plane, because **the wing has no root plane at all**. Every
planar face on the wing whose normal is ±x is a *tip*:

| wing | planar x-faces found | x | normal | area mm2 | y-z footprint of that face |
|---|---:|---:|---|---:|---|
| left | 1 | **−260.000000** | −1.000 | 6,355.0852 | y −11.169017…19.586400, z −148.760009…156.239991 |
| right | 1 | **+260.000000** | −1.000 | 6,355.0852 | identical |

So the inboard termination of each wing is a **curved cap**, never a butt face. Its abscissa
is not a constant: sampled over the root footprint the wing's inboard end runs from
**|x| = 82.56799 mm to |x| = 86.499584 mm** — i.e. the root is a shallow shell, not a joint
surface (measured by ray census, `work/s4_penetration.py` → `out/s4_penetration.json`).

Against that, the body's own side surface, measured on the same rays:

| quantity (stations where both body walls were measurable) | min | median | max |
|---|---:|---:|---:|
| body outer mould line \|x\| **at the 36 contact stations** | 85.281 | — | **98.591** |
| body inner (cavity) surface \|x\| at the same stations | 83.874 | — | 97.391 |
| local wall thickness (outer − inner) | 0.2301 | 1.2220 | 1.7238 |
| wing inboard end \|x\| | 82.568 | — | 86.500 |
| **contact depth (outer − wing_in)** where the wing is inside the outer envelope — **36 stations** | 2.512 | 5.326 | **12.421** |
| **cavity penetration (inner − wing_in)** where the root is inside the cavity — **36 stations** | 2.512 | 4.124 | **11.188** |
| gap (wing_in − outer) where the wing stops short of the skin — **27 stations** | 1.282 | 3.386 | **19.312** |
| *excluded*: the same difference measured inside the wing's **duct reliefs** — 53 stations, 31.3…131.9 mm, which is not a gap between a root and a fuselage | — | — | — |

Station ledger, so the three counts cannot be mistaken for each other: **36 in contact + 27
genuine gaps + 53 inside duct reliefs = 116** with both walls measurable, of 157 with wing
material and 41 where the body has no wall at all on that side (§3d).

So the two solids overlap over a footprint of

> **y −12.2159 … 17.8539 mm, z −217.0464 … +76.2522 mm, |x| 82.6 … 98.6 mm**,

and the overlap is the **fuselage's own skin between |x| 82.6 and 98.6**, at those stations.

### 1c. The row volumes as measured here — and the 1.4 × 10⁻⁵ mm3 reconciliation

`work/s2_pairs.py` → `out/s2_pairs.json`, `log/s2_pairs.log`. Instrument: one
`BRepAlgoAPI_Common` per pair (both operands are single solids, so the solid-by-solid sum of
the closure sweep degenerates to one boolean), default fuzzy, `BRepGProp` eps 1e-12. Both
wings are measured, not inferred from the mirror.

| pair | Common, this run | pieces (volume / area / faces / bbox) | CUT identity vol(W)−vol(W−B) | residual |
|---|---:|---|---:|---:|
| fuselage × **wing_left** | **3,781.632744** | p0 1,248.083384 (2,440.83 mm2, 31 f) z −225.070…−177.272<br>p1 451.170708 (1,011.84 mm2, 34 f) z −124.0…−105.9<br>p2 **2,082.378646** (3,800.14 mm2, 43 f) z −31.66…+94.69 | 3,781.632748 | **3.8e−6** |
| fuselage × **wing_right** | **3,781.632745** | p0 1,248.083384 · p1 451.170709 · p2 2,082.378646 | 3,781.632746 | **1.2e−6** |
| **sum** | **7,563.265489** | 6 pieces | 7,563.265494 | — |

**Reconciliation against the 7,563.265475 this task was given: Δ = +1.4 × 10⁻⁵ mm3
(1.9 × 10⁻⁹ relative).** It is not geometry — it is operand order. The baseline sweep
`s3_closure.py` sorts the part names and computes `Common(fuselage_rev1, wing)`; this run
computes `Common(wing, fuselage)`. Reversing the operands of an OCC boolean moves the result by
9 × 10⁻⁶ mm3 on the left row and 5 × 10⁻⁶ on the right. The baseline's own per-row values
(3,781.632735 / 3,781.632740) are reproduced by this run to that same order, so **both bases
are the same measurement**; the report uses **mine** below and states the 1.4e−5 delta
wherever the sum is quoted.

**Two structural findings in this table, both new:**

1. **The overlap is three disjoint patches, not one.** Fore (z −225.07…−177.27, 33 % of the
   volume), mid (z −124.0…−105.9, 12 %), aft (z −31.66…+94.69, **55 %**). Three lenses where
   the body's side surface bulges out past the wing's root cap — see §2/§3.
2. **The two rows agree to 6–7 digits piece-by-piece** (1,248.083384 / …384; 451.170708 /
   …709; 2,082.378646 / …646). The wing sectors are mirrors so the condition is one condition
   made twice; a design intent would not be, an untrimmed loft cap is.

## 2. Classification

**[C] MODELLING ARTEFACT — the wing root is an untrimmed loft end, not a joint.**

Not (a) intentional contact: an intentional bonded/bolted joint has a defined mating surface.
Here the wing's inboard end is a **curved cap with no planar face anywhere** (§1b) and its
station wanders over 3.93 mm while the body's skin wanders over 13.31 mm on the same footprint.
No joint design produces a 12.42 mm GAP at one station and an 11.19 mm penetration into the
cavity at another on the same continuous surface.

Not (b) a genuine clash — nothing has been moved from a design position, both parts are at
their delivered coordinates, and the overlap is not a localised penetration of one part into
another at a designed interface.

It is (c), and specifically the sub-case this corpus already has a name for: **the wing was
lofted outboard-to-inboard and terminated by an end cap that was never trimmed to the fuselage
skin.** The proof is not a judgement call — it is in §3.

## 3. Geometric evidence for the classification

The standard used on the rings was: an interference that is a *consequence of the two
surfaces* rather than of a *declared feature* is a modelling artefact. Four measurements meet
that standard here.

### 3a. The overlap volume is exactly the skin the wing displaces — it has no geometry of its own

`3,781.632735 / 3,781.632740 mm3` is not a solid feature: it is a thin slab of somebody else's
wall. Decompose it as footprint × wall and it closes:

> 3,781.6327 mm3 ÷ median local wall **1.2220 mm** = **3,094.6 mm2** of skin occupied;
> an independent lattice census of the contact footprint (§1b, cell 88.2 mm2) gives
> **3,175 mm2** — a 2.5 % difference, which is the lattice quantisation, not a discrepancy.

A clash or a joint has a volume that belongs to one of the parts. This volume belongs to
*neither*: it is the intersection of a wall with a beam that happens to cross it. Change the
wall thickness by 1 % and the "interference" changes by 1 % — the signature of an occlusion,
not of a feature.

### 3b. Where the wing crosses the skin it goes 100 % of the way through

Of the 36 stations where the wing is inside the outer mould line, **36 of 36 also penetrate the
inner (cavity) surface**. Not one station sits *within* the wall (a bonded lap) — the wing
never stops at the skin anywhere it touches it. A lap joint is a solid that ends inside the
wall; this one cannot, because it ends wherever its loft cap happens to fall.

### 3c. The same continuous root surface both buries itself in the body and stands clear of it

The gap statistic and the penetration statistic are the *same surface*, sampled along one
continuous root cap: it runs from **+12.421 mm past the outer mould line** (of which
**+11.188 mm is past the inner surface**, inside the cavity) to **19.312 mm clear of the skin**
(median gap 3.386 mm on the 27 gap stations). Across the sampled root the total travel is
**31.7 mm** between deepest intrusion and widest clearance, at the same |x| to within 4 mm.
A design intent that produces a 12 mm intrusion and a 19 mm stand-off on one continuous edge is
not an intent — it is the absence of a trim operation.

### 3d. The body's side is not even continuous where the wing crosses it

On 41 of 157 stations the second ray finds **no body wall on that side at all** (body side
openings, at z ≈ −99.7, −70.4, −41.1, 222.9, 252.2 — the battery-bay and aft-duct openings).
The wing's root cap runs across those openings too. A joint cannot be designed against a
surface that is not there; a loft end cap does not care.

**Conclusion carried into §4:** the overlap is the fuselage skin material occupied by an
untrimmed wing root. Therefore the fix is a boolean — trim the wing at the skin — and **no
design change is required or permitted**: the fuselage must stay bit-identical at
206,454.319709 mm3 / 320.0042 g.

### 3e. What the fix must be, derived rather than assumed

Because the overlap *is* the wall band, there is exactly one class of cut that removes it:

* cut the wing at the **inner** surface (remove only what is in the cavity) → the wall band is
  untouched → **the 3,781.63 mm3 row does not move at all**. Provably ineffective.
* cut the wing at the **outer mould line** (remove what shares space with the body) → the wall
  band is removed with it → **row goes to 0.000000**, and the wing's visible surface is
  unchanged, because everything removed was behind the skin.

So the executed fix is `wing_fixed = wing − fuselage`, with the buried slug that the skin
severs removed as a remnant (stated and enumerated in §4).

## 4. Executed fix

### 4a. The boolean, and why this one

Classification (c) ⇒ the fix is a boolean, not a design change. But which boolean is decided by
§3e, not by taste: the overlap **is** the wall band, so only a cut that removes the wing's
material where the body's material is can move the row. Executed:

> **`wing_fixed = wing − fuselage_solid`** — one OCC `BRepAlgoAPI_Cut` per wing, default fuzzy.

This is the wing trimmed at the fuselage skin. It removes *exactly* the shared material, so the
post-fix row is zero by construction, and it touches nothing that is not inside the body — the
fuselage is not cut, not edited, not re-lofted, and remains byte-for-byte the delivered part.

### 4b. What the cut produced — measured, both wings

`work/s5_fix.py` (left, stopped after its export — `log/s5_fix.log`) and
`work/s5b_fix_right.py` (right, plus the left's round-trip census) → `out/s5b_fix.json`,
`log/s5b_fix.log`.

| | wing_left | wing_right |
|---|---:|---:|
| volume before | 1,354,555.798302 | 1,354,555.798302 |
| removed by the Cut | **3,781.632748** | **3,781.632746** |
| volume after the Cut | 1,350,774.165553 | 1,350,774.165555 |
| solids after the Cut | **2** | **2** |
| solid 0 (the wing) | 1,344,635.639762, 132 faces | 1,344,635.639761, 134 faces |
| solid 1 (**severed buried remnant**) | **6,138.525801**, 23 faces | **6,138.525801**, 24 faces |
| remnant bbox | x −99.756…−82.220, y −12.540…18.587, z −231.711…−182.008 | mirror (x +82.220…+99.756) |
| **after dropping the remnant** | **1 solid, 1,344,635.639762** | **1 solid, 1,344,635.639761** |
| net mass change at 1550 kg/m3 | −9,920.158540 mm3 = **−15.376 g** | −9,920.158541 mm3 = **−15.376 g** |
| validity / round-trip | 1 solid, valid, STEP re-import Δ 2e−6 mm3 | 1 solid, valid |

The **removed volume by Cut = 3,781.632748 / 3,781.632746**, against the independently measured
Common rows **3,781.632744 / 3,781.632745** (`s2_pairs.json`). Two different OCC operators,
same number to 4 × 10⁻⁶ mm3 — the same agreement the baseline report demanded of the rings.

**The remnant is the only thing that needed a decision, and it is enumerated, not hidden.** The
skin patch at the fore root cuts the wing's buried slug clean off (the other two patches are
bounded slits that the material flows around, which is why the wing survives as one solid). A
6,138.525801 mm3 piece of wing floating loose inside the fuselage cavity is not a part by any
reading, so the keep rule is stated once — *keep a resulting solid iff its bbox is not wholly
inside the body's bbox* — and the dropped piece is published with volume, face count and bbox.

**What did NOT change, and why that is provable:** the external mould line of the wing is
untouched, because every cubic millimetre removed lay inside the body. The wing's x-extent is
identical before and after (−260.000000 … −80.329704 / mirror), i.e. **the span is unchanged**;
the only bbox change is the fore-root z extent, which is the dropped remnant's own bbox
(−231.711 → −224.533).

### 4c. The variant that was measured and rejected on arithmetic, not on taste

`wing − cavity` (trimming at the **inner** surface, which is what the task text suggests when it
says "cut the wing root at the fuselage inner surface"): the intersection of the wing with the
body's material is *entirely* the wall band, and the cavity is not body material, so trimming
inside the cavity removes **none** of the 3,781.63 mm3. Verified on the operands themselves: the
`inner` surface lies *outboard* of the wing's root cap at 36 of 36 contact stations (§1b), i.e.
the wing is never "inside the wall only". That variant is therefore not a fix and was not
executed.

The **butt-joint** variant (also remove the wing material that pokes into the cavity but stays
connected around the slits) is a legitimate further step and gives a pure outer-mould-line butt
with a bond patch of ≈3,095–3,175 mm2 per side (§5c). It is *not* executed here because it is a
joint-design decision, not an interference decision, and it would remove wing material that
carries no interference. Its cost is stated in §5c and its volume is a limit, not a guess.

## 5. Re-verification

### 5a. The new body ↔ wing rows — three instruments, one answer

| instrument | original wing | trimmed wing |
|---|---:|---:|
| **full-size `BRepAlgoAPI_Common`** (this report's row instrument) | 3,781.632744 / 3,781.632745 | **0.000000** — and exactly `0.0`, not a residual sliver: the boolean returns zero volume after 808.39 s (left) / 753.17 s (right), §5f |
| **CUT identity** `vol(W) − vol(W−B)` | 3,781.632748 / 3,781.632746 | the Cut *is* the fix, so the removed volume **is** the row: 3,781.632748 / 3,781.632746 |
| **ray quadrature**, 12,800 stations, no boolean at all (`work/s10_verify_census.py`) | **3,787.1836** | **0.0000**, max line overlap **0.000000 mm**, **0 of 12,800 cells** |

Note on the cost of the primary instrument: on the trimmed wings the two solids are separated by a
coincident surface, and the boolean that resolves it takes **808 / 753 s** against **536 / 548 s**
for the original pair. It terminates, and it terminates at exactly zero.

The quadrature is the instrument that can disagree, because it shares no code path with the
boolean: it recovers the row volume on the original wing to **+0.147 %** (3,787.1836 vs
3,781.632744 — midpoint-rule discretisation on a 0.987 mm2 cell) and returns **exactly zero,
cell by cell, with a maximum line overlap of 0.000000 mm** on the trimmed wings. Not "small" —
zero, at every one of 12,800 stations, on both sides.

### 5b. Fuselage: unchanged, and that is a control rather than a claim

`work/s6_walls.py` → `out/s6_walls.json`, `log/s6_walls.log`, run on the delivered STEP:

| quantity | value | expected |
|---|---|---|
| volume | **206,454.319709 mm3** | 206,454.319709 ✔ |
| mass at 1550 kg/m3 | **320.0042 g** | 320.0042 g ✔ |
| topology | **1 solid / 1 shell / 540 faces**, `BRepCheck` valid | 1 solid / 540 faces ✔ |
| bbox | x ±105.891846, y −48.458738…45.413633, z −360…280 | ✔ |
| **wall, fore band** (z ≤ −189.0984) | V 67,254.3350, A_eff 123,170.0573, **2V/A = 1.0921** | **1.0921** ✔ |
| **wall, pinch band** (−189.0984…−111.9330) | V 26,262.2633, A_eff 43,807.5718, **2V/A = 1.1990** | **1.1990** ✔ |
| **wall, aft band** (−111.9330…280) | V 112,937.7213, A_eff 191,416.3898, **2V/A = 1.1800** | **1.1800** ✔ |

Every band's V and A_eff reproduce `dm-final-package` to the last digit, so the walls are not
"still about 1.1" — they are the same three numbers on the same bands with the same
artificial-face removal. The fix is wing-side only and the body was never opened.

### 5c. The joint this leaves behind — stated, with its measured area

Trimming at the skin creates a **coincident-surface interface**: the wing's new inboard faces
are copies of the fuselage's own faces, so the joint is a zero-volume contact rather than a
zero-gap one. The mating area per side, from two independent routes:

| route | value |
|---|---:|
| row volume / median local wall = 3,781.6327 / 1.2220 | **3,094.6 mm2** |
| lattice footprint census (s4, cell 88.2 mm2) | **3,175 mm2** |

So **≈3,095–3,175 mm2 per side** is the bond/contact patch a joint design would be written
against — one number a disposition document can carry, with its basis. No fastener pattern was
added: the fuselage is untouchable, so any fastener is wing-side or the joint is bonded.

**Residual the trim does not close (stated, not hidden):** because the wing's root cap was
never body-aware, it also *stops short* of the skin at **27 of 116** sampled stations, by
**1.282 … 19.312 mm, median 3.386 mm** (§1b; the 53 stations inside the duct reliefs are
excluded — those numbers are 31…132 mm and are holes, not gaps). A gap is not interference, so
it is outside this task, but the wing does not seat on the fuselage along its whole chord and
that is a fit question the corpus has not dispositioned. Closing it, if design authority wants
it closed, is a *different* fix (extend the root), not part of the artefact removal.

### 5d. ONE-SOLID condition

| part | solids | faces | valid |
|---|---:|---:|---|
| fuselage DM-FUS-001 REV 1 | **1** | 540 | ✔ |
| wing_left (fixed) | **1** | 132 | ✔ |
| wing_right (fixed) | **1** | 134 | ✔ |

The two-solid Cut result was collapsed to one solid by dropping the buried remnant (§4b) —
published with its volume and bbox, so the solid count is 1 by a stated rule, not by silence.
The STEP exports re-import to the same volume (Δ 2 × 10⁻⁶ mm3) and are valid.

### 5e. Mass consequence

Net wing material removed, per side: **9,920.158540 mm3** (3,781.632748 shared with the skin +
6,138.525801 severed remnant). At 1550 kg/m3, the composite density the corpus uses for the
body: **−15.376 g per side, −30.752 g both sides**. This is a mass *reduction* that comes from
removing material which was not a designed feature; it is not an optimisation and must not be
booked as one — the airframe mass of record (472.273 g) was built on the untrimmed wing, so
whatever the wings were previously credited with has to be decremented by 30.752 g as a
correction, not counted as a saving.

### 5f. The full closure sweep, re-run on the fixed assembly

`work/s9_closure_fixed.py` + `work/s11_finalise.py` → `out/s9_closure_fixed.json`,
`log/s9_closure_fixed.log`, `log/s11_finalise.log`. Same population, same solid-by-solid
algebra, same default fuzzy, same eps 1e-12 as the C-28 baseline — the only difference is the two
wing STEPs, sha256 `1CCEE72A…` (left) and `FDCEDB45…` (right) in `out/input_sha256.txt`.

| | baseline (C-28) | **fixed, this run** |
|---|---:|---:|
| part groups | 32 | 32 |
| candidate pairs (of 496) | 95 | **95** |
| bbox-separated, enumerated | 401 | **401** |
| examined and zero | 61 | **63** |
| non-zero rows | 28 | **26** |
| excluded: envelope-on-envelope | 6 / 200,446.177670 | **6 / 200,446.177670** |
| **closure total** | **12,978.785305** | **5,415.519830** |

**Set diff: −2 pairs / −7,563.265475 mm3, +0 pairs, 0 pairs changed in value.**

The two removed rows are exactly `fuselage_rev1 ↔ lifting_wing_left` and
`fuselage_rev1 ↔ lifting_wing_right`, both now **0.000000** — measured by the same
`BRepAlgoAPI_Common`, on the same files, in the same sweep:

| row | baseline | **fixed** |
|---|---:|---:|
| fuselage ↔ wing_left | 3,781.632735 | **0.000000** |
| fuselage ↔ wing_right | 3,781.632740 | **0.000000** |
| fuselage ↔ wing_centre_bridge | 0.000000 | **0.000000** |

Every one of the 26 surviving rows reproduces its baseline value to the printed digit — the
elevon-root rows (628.119864 / 561.996031 / 249.750363 / 120.247564 / 72.160111), the pushrod
rows (2.464577), the static joint rows (512.079603 / 320.137167 / 196.000000 / 20.002085 /
2.400232) and the excluded envelope class (200,446.177670). **The trim moved nothing else**,
which is the point of quoting a *set diff* rather than a total: `−7,563.265475` is the only
change, so the fix's blast radius is provably the two rows it was aimed at.

## 6. New authoritative airframe total

> **drone-mech interference (authoritative, closure basis, post body↔wing fix): 26 pairs /
> 5,415.519830 mm3** on DM-FUS-001 REV 1 (one solid, 206,454.319709 mm3, 320.0042 g) +
> ring v2 A/B + bead A/B, with the two lifting-wing sectors trimmed to the fuselage skin
> (sha256 `1CCEE72A…` / `FDCEDB45…`).

| class | pairs | mm3 | was (C-28) | change |
|---|---:|---:|---:|---|
| **A1** elevon-root clash | 10 | **3,264.547867** | 3,264.547867 | 0 |
| **A2** pushrod modelling artefact | 2 | **4.929154** | 4.929154 | 0 |
| **B** body ↔ lifting-wing sector | **0** | **0.000000** | 2 / 7,563.265475 | **−2 / −7,563.265475** |
| **C** static bonded-joint overlap | 14 | **2,146.042809** | 2,146.042809 | 0 |
| **total (C-26)** | **26** | **5,415.519830** | 28 / 12,978.785305 | **−2 / −7,563.265475** |
| *excluded* envelope ↔ envelope | 6 | 200,446.177670 | same | 0 (unchanged) |

Ring v2 remains **0 pairs / 0.000000 mm3**. Fit-critical (moving parts only, A1 + A2) is
**12 pairs / 3,269.477021 mm3**, unchanged — the fix removes a static modelling artefact and
touches no moving-part row.

Board-replacement text, one line:

> `interference | 26 pairs / 5,415.519830 mm3 (closure basis) — elevon root 3,264.548 + pushrod 4.929 + body↔wing 0.000 + static joints 2,146.043; ring v2 CLEAN 0.000000 | body↔wing rows cut from 2 pairs / 7,563.265475 to 0 by trimming the wing roots to the skin (fuselage byte-identical, 206,454.319709 mm3 / 320.0042 g; walls 1.0921/1.1990/1.1800) | evidence/dm-body-wing/`

**What this does not fix, and what it now is not:** the airframe still carries 26 pairs /
5,415.520 mm3, of which **3,269.477 mm3 is moving-part clash** (A1 + A2) and
**2,146.043 mm3 is undispositioned static joint overlap** (C). The body↔wing item was 58.3 % of
the old total; it is now zero, and the largest single remaining class is the elevon root
(60.3 % of the new total), which is the item the corpus already has a named cause and a measured
fix for (`fab-dm-final` §5, +38.485 mm outboard re-station).

## Appendix — method, provenance, limits

### A. Instrument and provenance

| item | value |
|---|---|
| interpreter | `C:\Program Files\Python312\python.exe` (Python 3.12) |
| CAD kernel | cadquery 2.7.0 / OCP 7.8.1.1 (OpenCASCADE) — no KiCad, no solver involved |
| volume | `OCP.BRepGProp.VolumeProperties_s(shape, props, 1e-12)` — never `Shape.Volume()` (which is 34.0986 mm3 low on this body, `dm-final-package:201`) |
| boolean | `OCP.BRepAlgoAPI_Common` (rows) and `BRepAlgoAPI_Cut` (the fix and the identity), OCP default fuzzy 0.0 |
| bbox | `OCP.BRepBndLib.AddOptimal_s`, pad 1e-6 mm |
| rays | `OCP.IntCurvesFace_ShapeIntersector`, tolerance 1e-7, infinite-line parameterised 0…800 mm |
| topology | `TopExp_Explorer`, `BRepCheck_Analyzer` |
| inputs | body + 3 wing sectors + 7 context parts copied from `evidence/dm-interference-reconcile/work/obj/` and the repo's `phase15_geometry/step/`; sha256 in `out/input_sha256.txt`. **The body copy is sha256 `d9ba7aeb…`, byte-identical to `dm-final-package/out/`, `dm-bearing-rings/out/`, `dm-ring-redesign/out/` and `dm-interference-reconcile/work/obj/`** |
| write scope | this directory only. No repo write, no commit, no reset; nothing written to `D:\CodeProjects` or `E:\1vm\TMP`. The repo was read only |

**On the wing file hashes — asked before it is asked of this report.** The repo's delivered wing
STEPs are **not** byte-identical to the evidence copies the C-28 population was measured on
(repo left `B1FB7CD6…`, 713,596 B; evidence left `5CE725D1…`, 728,201 B). They are the same
*geometry*: `work/s12_repo_vs_evidence.py` → `out/s12_repo_vs_evidence.json` reads
**1,354,555.798302 mm3 on both, delta +0.000000000**, identical bbox to 6 dp, identical
51 / 52 / 52 face counts, identical 1 solid / 1 shell, for all three sectors. The difference is
the STEP writer's header, not the part. The fix was applied to the C-28 operand so the row stays
comparable to the baseline; on identical geometry the trimmed result is the same either way.

| script | produced |
|---|---|
| `work/s1_probe.py` → `out/s1_probe.json` | census: 6 files, solids/faces/volume/bbox, per-solid split |
| `work/s3_locate.py` → `log/s3_locate.log` | the planar-x-face hunt on the wings (found **only** the two tips) and the first x-ray survey of the body's walls |
| `work/s4_penetration.py` → `out/s4_penetration.json` | the penetration profile: 157 stations per wing × 2 ray censuses |
| `work/s4b_profile.py`, `work/s4c_contact.py`, `work/s4d_gaps.py` → `log/*.log` | the contact / gap / duct-hole classification of those stations |
| `work/s2_pairs.py` → `out/s2_pairs.json` | **the two row volumes**, their 3 pieces each, face counts, bboxes, CUT identity |
| `work/s5_fix.py` (left), `work/s5b_fix_right.py` (right) → `out/s5b_fix.json`, `work/obj_fix/*.step|.brep` | **the fix**: the Cut, the remnant, the exports |
| `work/s6_walls.py` → `out/s6_walls.json` | body volume / mass / topology / validity and the three band walls |
| `work/s9_closure_fixed.py` + `work/s11_finalise.py` → `out/s9_closure_fixed.json` | **the closure sweep re-run on the fixed assembly** (89 pairs in s9, 95 in the closed record) |
| `work/s10_verify_census.py` → `out/s10_verify_census.json` | the independent (non-boolean) zero check on the fixed wings |
| `work/s8_localised.py` → `out/s8_localised_orig_left.json` | a localised-boolean attempt that returned 0.000000 where 3,781.63 exists, because the clipped body is a **compound** and one compound × compound boolean drops the overlap (the same algebra failure `dm-interference-reconcile` §1c documented). **Kept as a negative result, not as evidence** — it is why the verification uses the ray census instead |

### B. Stated limits — what this report does not establish

1. **The closure sweep was closed in two passes, and that is stated rather than smoothed.** The
   sweep process measured **89 of the 95 candidate pairs** — including all three
   `fuselage ↔ wing` rows, which is what the wave needed — and was stopped before the last six.
   `work/s11_finalise.py` then rebuilt the candidate list identically (same sort order, same bbox
   prefilter, 95 of 496 confirmed), established that the six unmeasured pairs were exactly the
   six motor-envelope pairs, measured them (0.02 s each), and wrote the single
   `out/s9_closure_fixed.json` with all 95 pairs, with `n_pairs_measured_here_vs_carried`
   recording the split (89 carried, 6 measured here). Those six reproduce the baseline's
   excluded envelope class exactly (200,446.177670 mm3), so the two-pass route changed no number.
2. **Bond area is a two-route estimate** (3,094.6 mm2 by volume/wall, 3,175 mm2 by lattice),
   not a surface boolean — a surface boolean on coincident faces is the one operation this
   geometry does not do cheaply (the volume boolean alone costs 808 s).
3. **Mass is geometric** at 1550 kg/m3: no layup, ply drop or fastener.
4. **The gap residual is measured on a 13 × 17 lattice per wing**, not on the continuous
   surface; the extremes (1.282 / 19.312 mm) are lattice samples and are quoted as such.
5. **The two bead rows are unchanged and code-built** (no STEP exists for them); they were
   carried through the re-run with the constants from `r3_final.py`, not re-derived.
6. **The motor envelopes are the repo's Ø42 × 72 parts.** The A1 class is contingent on them
   (`dm-interference-reconcile` §B5) and this report does not touch that contingency.
7. **The fix changes the wing only.** No joint (bond line drawing, adhesive call-out, fastener
   pattern) was authored — the report measures the interface and leaves the joint to design
   authority, because furnishing it would change the wing's mass beyond the trim.

### C. Arithmetic self-check

| identity | value | residual |
|---|---|---:|
| 3,781.632735 + 3,781.632740 (the figure this task was given) | 7,563.265475 | 0.000000 |
| **3,781.632744 + 3,781.632745 (measured here)** | **7,563.265489** | vs given: **+1.4e−5** |
| 1,248.083384 + 451.170708 + 2,082.378646 (left pieces) | 3,781.632738 | 6e−6 (printed-row rounding) |
| 1,248.083384 + 451.170709 + 2,082.378646 (right pieces) | 3,781.632739 | 6e−6 |
| 1,354,555.798302 − 3,781.632748 (left wing after Cut) | 1,350,774.165554 | 1e−6 |
| 1,344,635.639762 + 6,138.525801 (left pieces of the Cut) | 1,350,774.165563 | 1e−5 (boolean noise on a shared boundary) |
| 9,920.158540 mm3 × 1.55e−3 g/mm3 | 15.3762 g per side | — |
| A1 3,264.547867 + A2 4.929154 + C 2,146.042809 | **5,415.519830** | 0.000000 |
| old C-28 12,978.785305 − B 7,563.265475 | **5,415.519830** | 0.000000 |
---

**Verdict.** The two `body ↔ wing` pairs were not a joint and not a clash: they were an
**untrimmed wing root** — a curved loft end cap at |x| ≈ 82.6–86.5 that cuts through a fuselage
side whose outer mould line runs 85.3–98.6, producing three lens-shaped patches whose total
volume is simply the skin the wing displaces (3,781.632748 / 3,781.632746 mm3). The fix is a
boolean, not a design change: `wing − fuselage`, wing-side only, fuselage byte-identical, external
mould line untouched, one solid each, −15.376 g per side. The two rows measure **0.000000** by the
primary instrument, the CUT identity and a 12,800-station ray census that finds a maximum line
overlap of **0.000000 mm**. The airframe's authoritative total drops from 28 pairs /
12,978.785305 mm3 to **26 pairs / 5,415.519830 mm3**, with a set diff of **−2 pairs /
−7,563.265475 mm3 and nothing else moved**.
