# DM Knife Edge — Per-Duct Fairing Design & Verification

Status: **COMPLETE** — the knife edge is confirmed at 2.8334°, four options are evaluated, one is executed on a copy, and the residual is bounded and measured.

Inputs (read-only, on COPIES):
- `evidence/dm-ring-redesign/out/drone-mech_fuselage_rev1.step` (ring fix — must not move)
- `evidence/dm-final-package/out/drone-mech_fuselage_rev1.step`

Evidence dir: `evidence/dm-knife-fairing/`

---

## 0. Method & tooling

`C:/Program Files/Python312/python.exe` (cadquery 2.7.0 / OCP 7.8.1.1). Deterministic reproduction
before any claim:

| instrument | how |
|---|---|
| volume | `BRepGProp.VolumeProperties_s(shape, props, eps=1e-12)` — never `Shape.Volume()` |
| mass | volume × 1550 kg/m³ (`PLA-core-CF-wrap`, the material the part is drawn in) |
| bbox | `BRepBndLib.AddOptimal` |
| face/edge census | `TopExp_Explorer`, `BRepAdaptor_Surface` type + cylinder axis/radius |
| **dihedral** | for every edge, `ShapeAnalysis_Surface::ValueOfUV` → `BRepAdaptor_Surface::D1` → outward normals `n1, n2`; **material included angle β = 180° − angle(n1,n2)**; convex/concave decided by `BRepClass3d_SolidClassifier` on `P + ε·(n1+n2)/|n1+n2|` (outside ⇒ convex). A knife edge is a **convex** edge with β → 0. |
| ray profile | `IntCurvesFace_ShapeIntersector` from the duct axis, 0.5° in azimuth |

**Identity control (passed).** The shipped rev1 copy (`sha256 D9BA7AEB…CB9CADF`) is 1 solid / 1 shell /
540 faces / 3,122 edges / 206,454.319709 mm³ / 320.0042 g / `BRepCheck` valid, bbox x ±105.8918,
y −48.4587…+45.4136, z −360…280. Rebuilt from the pinned generator with the delivered rule (two-piece
skin-resampled cavity, bore r 42.6, six cuts in repo order) it comes back **206,454.320759 mm³ /
320.0042 g / 1 solid**, and every intermediate stage reproduces digit-for-digit
(5,977,767.7043 → 4,002,371.4373 → 257,250.2708 → 248,771.1984 → 240,292.1269 → 206,454.3208).
So the build chain below is the part.

## 1. Knife edge confirmed on the CURRENT final part

**It is real, it is on the Ø85.2 bore rim, and it is sharper than 3°.**

The bore is **6 cylindrical faces at r = 42.600 mm exactly** (axes x = ±44, y = 0, tool z −112…290). Its
rim has **268 edges**. Measured material included angle over them:

| quantity | value |
|---|---|
| **minimum convex β on the bore rim** | **2.8334°** at (±56.959, ±40.581, **−70.984**) — r = 42.600 from the duct axis, azimuth 72.3° (outboard-upper), and its three mirrors |
| next worst | 2.8402° at (±56.994, ±40.570, −54.431); 4.0294° at (±47.708, ±42.438, −56.967); 4.923° at (±56.282, ±40.791, −62.783) |
| **global census, all 3,122 edges of the part** | **min convex β = 4.0294°**, at the same feature; histogram has 32 edges in 0–5°, 16 in 5–10° |
| rim edges with β < 10° | **28**, confined to **z −87.5 … −8.6** |
| rim edges with β < 20° | **92**, spanning z −109.5 … +195.3 |

**Minimum local radius and breakout depth (corrected).** Measured on the shipped loft (ray cast about each
duct axis, 0.5°):

| z | −110 | −70 | −30 | 0 | 60 | 120 | 150 | 180 | 210 | 245 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| min hull r from duct axis | **39.4685** | 42.3982 | 41.7582 | **40.7256** | 39.9047 | 40.7256 | 40.5105 | 38.7540 | 34.1307 | 16.5433 |

The brief's **40.7627** is the *ideal* superellipse value (azimuth 102.8°) and is reproduced analytically,
but the shipped surface is a 72-point spline loft and dips to **39.4685** at z = −110. So
breakout = 42.6 − 39.4685 = **3.1315 mm** worst, **1.8744 mm** at z = 0. The earlier **1.806 mm** is
42.5 − 40.694: it used the nominal r 42.5 and an ideal-section radius, so it is **understated by
0.07 mm** against its own basis and by **1.33 mm** against the shipped surface. Direction unchanged,
magnitude corrected downward in the sense that matters here: the bore breaks out *more* than reported.

**Width at 50 µm and 100 µm out, from the measured β** (`w = δ·tan β`; the two faces bound the material,
so this is the material thickness δ along the surface from the edge):

| β | basis | w at 50 µm | w at 100 µm |
|---|---|---:|---:|
| **2.8334°** | measured minimum, shipped part | **2.473 µm** | **4.946 µm** |
| 4.0294° | measured 2nd family | 3.522 µm | 7.045 µm |
| 4.0° | the figure the prior wave quoted | **3.49 µm** | 6.99 µm |

So the prior **3.49 µm at 50 µm reproduces exactly at β = 4°**, and the true minimum is worse:
**2.47 µm**.

**Correction to "the dihedral starts at 0°".** Zero is the *analytic* tangency of the superellipse with
the bore circle, at azimuth 102.8° where the hull radius is 40.7627 — and that azimuth lies **inside** the
bore, where the material has been cut away entirely. No material exists at 0°; the smallest angle that
exists on a real edge of the shipped solid is **2.8334°**. The direction of the prior conclusion (a
vanishing wedge, unmanufacturable) is right; the "0°" is not, and neither is "an R0.5 fillet would be
enough" — the shortfall is 3.13 mm, so there is nowhere for a fillet to sit.

## 2. Four options evaluated

What the rim needs: the outer mould line must stay **outside r = 42.6 from the duct axis** wherever the
bore passes, by at least the 1.2 mm land, i.e. **r ≥ 43.8**. Anything less leaves material that tapers
to zero. That single inequality decides all four options.

**(b) BODY_HEIGHT 88 → 94.97, re-loft — BUILT AND REFUTED, three ways.** The generator's own station
table with `BODY_HEIGHT = 94.97` and the delivered cavity rule, all six cuts:

| | stock | BODY_HEIGHT 94.97 | Δ |
|---|---:|---:|---:|
| **solids** | 1 | **2** | **fails the one-solid condition** |
| volume mm³ | 206,454.3208 | 260,508.4823 | +54,054.16 (+26.2 %) |
| mass g | 320.0042 | 403.7881 | **+83.7839 (+26.2 %)** |
| outer volume mm³ | 7,953,163.97 | 8,511,736.61 | +7.0 % |
| outer area mm² | 283,428.15 | 289,534.52 | +2.2 % |
| bbox y | −48.4587…45.4136 (93.872) | −55.1538…55.1538 (**110.308**) | **+16.4 mm envelope** |

and it does not even reach the land it was aimed at — measured minimum hull radius from the duct axes on
the 94.97 loft: z −110 **41.63**, −70 46.10, −30 44.89, 0 43.77, 60 43.52, 120 43.77, 150 **42.44**,
180 **39.39**, 210 **33.94**, 245 **16.54**. The 43.8 land is met only between roughly z −70 and +120;
forward of −110 and aft of 150 the radius falls back **below the 42.6 bore** and the window reopens. The
reason is structural: `BODY_HEIGHT` only scales the seven constant stations — the aft taper
(200: 170×80, 250: 112×54) is untouched, and that is where half the breakout lives. So (b) buys a
two-solid part, +83.8 g, +16.4 mm of envelope and still leaves the knife edge. **Not chosen.**

**(a) a raised boss around the bore "without changing the hull" — refuted.** The land has to sit
*outside* r = 42.6, which is outside the current skin, so the outer mould line must change locally no
matter how the material is delivered. A coaxial boss ring (42.6…43.8) costs the same annulus as (c),
adds a *second* tangent junction where its OD meets the skin (β = arctan(R′/R) ≈ 7–8°, i.e. the same
disease at a bigger radius), and on the inboard side — where the skin is at r 47.8…137 — the annulus
would hang in the cabin void as a floating sleeve. Same mass, worse geometry.

**(c) a local raised pad / thickened rim only where the bore breaks out — CHOSEN.** A per-duct fairing
on the section wire, **not** a separate solid: the distance of each of the 72 section samples from each
duct axis is pushed out to a **smooth max** of itself and 43.8 mm, `t = ½(d + F + √((d−F)² + s²))`,
gated in z to the band that carries the rim. Because it is a smooth max and not a boolean union, the
surface leaves the superellipse **C¹** — no new crease, no new tangent edge, and the envelope barely
moves. It is a *local re-loft* of the flank band, not a re-loft of the hull: the nose, the tail, the
cavity, the slots, the hatch and the bore radius are all untouched, and the box does not grow.

**(d) accept with a handling note — rejected on process, not taste.** At β = 2.8334° the wall reaches
1.2 mm only **24.3 mm** from the edge (1.2/tan β). The part is drawn in PLA-core-CF-wrap; no layup,
print or trim operation can produce a 2.47 µm feather, and the same feature is the boundary of a real
hole — the skin is *absent* over 106° of azimuth about each duct in the prismatic band (measured: 212 of
720 rays from the duct axis return no material at z = 0, 60 and 120). That is not a
cosmetic edge; it is the fuselage not being closed — 78.8 mm of arc × 242 mm × 2 ducts = **381.6 cm²** of missing flank.

## 3. BODY_HEIGHT consequence (quantified before choosing)

Answered in §2 and enough to close the question: raising `BODY_HEIGHT` to 94.97 **breaks the
ONE-SOLID condition (2 solids)**, costs **+83.78 g / +26.2 %**, grows the y envelope by **16.4 mm**, and
still fails to reach the 43.8 mm land outside z ≈ −70…+120 — so it is both larger *and* incomplete. It
was therefore rejected before execution of any other option, not after.

## 4. Executed option — results

**What was built.** `work/k4_build.py --mode fair --fair 44.6 --zgate=-112,130`. The delivered 186 × 88
superellipse section is regenerated wire by wire, and for each of the 72 samples the distance from each
duct axis is replaced by

    t = ½·(d + F + √((d−F)² + s²))        F = 44.60 mm, s = 1.0 mm,
    gate = 1 for z ∈ [−112, 130], 0 outside (the delivered loft itself provides the runout to the
    −200 and +200 stations)

then the point is pushed radially from that duct axis from d to t. Nothing else is touched: **the same
cavity rule, the same two slots, the same hatch, the same bore radius 42.60, and the same 11-station
loft.** Commanded F is **44.60**, not 43.80, because the delivered 11-station loft interpolates
0.5–0.7 mm *below* its own wires between stations, so 44.60 is what actually achieves ≥ 43.8 of land on
the finished surface (the brief's Ø87.6 is the *requested* diameter; Ø89.2 is the *achieved* one).

**The loft cannot be re-stationed — measured, not assumed.** The obvious improvement (pin extra stations
through the dip) was built and rejected: `--mode stock2` is the **same** station table with **no fairing
at all**, and it comes back **3 SOLIDS, 212,498.999 mm³, 329.373 g** (versus the delivered 1 solid /
206,454.3208). Adding a station to a `ruled=False` 72-gon loft splits the part. So the fairing is
constrained to the delivered station table, and its axial extent is locked to the span between the
stations it can touch (−100 … +120) plus the loft's own runout. That is the reason the band ends at 130.

| | stock rev1 | **fairing (executed)** | Δ |
|---|---:|---:|---:|
| solids / shells | 1 / 1 | **1 / 1** | 0 |
| faces / edges | 540 / 3,122 | 564 / 3,326 | +24 / +204 |
| `BRepCheck` valid | true | **true** | — |
| free / non-manifold edges | 0 / 0 | **0 / 0** | 0 |
| volume mm³ | 206,454.3197 | **308,099.0371** | +101,644.7174 |
| **mass @1550 kg/m³** | 320.0042 g | **477.5535 g** | **+157.5493 g (+49.2 %)** |
| bbox x | ±105.8918 | ±105.8984 | +0.0066 |
| bbox y | −48.4587…45.4136 | −48.4579…**46.2251** | **+0.8115** on the top |
| bbox z | −360…280 | −360…280 | 0 |
| outer volume / area | 7,953,163.97 / 283,428.15 | 8,139,920.98 / 286,378.54 | +186,757.01 / +2,950.39 |

**Walls, same instrument, same bands** (`2V/A_eff`, artificial cut-plane faces removed — the
`dm-final-package::zband` definition, which reproduces the published 1.0921 / 1.1990 / 1.1800 exactly on
the stock part, so the comparison is like-for-like):

| band | z | stock | fairing | Δ |
|---|---|---|---:|---:|
| fore | −360…−189.0984 | 1.0921 | 1.0804 | −0.0117 |
| pinch | −189.0984…−111.9330 | 1.1990 | **1.5060** | +0.3070 |
| aft | −111.9330…280 | 1.1800 | **1.5766** | +0.3966 |

The two bands that gain are exactly the bands the fairing sits in — it is thickening, never thinning.
The fore band loses 0.0117 mm (0.5 %) because the fairing's runout slightly re-parameterises the loft
forward of −112.

**Interference sweep, row level, set diff only.** Same part set (v2 rings included), same code, stock and
faired fuselage measured back to back so the diff is instrument-matched:

| row | stock | fairing | Δ |
|---|---:|---:|---:|
| fuselage ↔ wing_left_sector | 3,781.632735 | 3,777.427682 | −4.205053 |
| fuselage ↔ wing_right_sector | 3,781.632740 | 3,777.427681 | −4.205059 |
| fuselage ↔ elevon_left | 72.160111 | 72.112096 | −0.048015 |
| fuselage ↔ elevon_right | 72.160111 | 72.112096 | −0.048015 |
| elevon_L ↔ nozzle_A | 120.247564 | 120.247564 | 0 |
| elevon_R ↔ nozzle_B | 120.247564 | 120.247564 | 0 |
| elevon_L ↔ motor_A_R3 | 593.069028 | 593.069028 | 0 |
| elevon_R ↔ motor_B_R3 | 593.069028 | 593.069028 | 0 |
| **total (8 rows)** | **9,134.218881** | **9,125.712739** | **−8.506142** |

**Set diff: 0 rows added, 0 rows removed, 4 rows changed** (all four by ≤ 4.21 mm³ and all *down*).
6 further pairs are bbox-separated and recorded as skipped, never as zero-by-assumption.

*Reconciliation, stated not hidden.* The wave-17 figure this report inherits is **1,556.232076 in 6
rows**, and its motor row is **585.708363** where my own instrument reads **593.069028** on the same
file with the stock fuselage as well as the faired one. So that 7.36 mm³/row is a convention difference
in the prior wave, not a fairing effect — it is identical before and after and cancels in the set diff.
The two `fuselage ↔ wing_sector` rows (**3,781.632735** each) are **pre-existing too**; they are simply
not part of the 6-row figure. On my instrument the airframe carries 8 fuselage-inclusive rows before the
fix and the same 8 after.

**Cost, stated plainly.** +157.5493 g is +49.2 % of a 320.0042 g fuselage. That is not a tuning number:
it is the mass of the flank skin that the part does not have today. Measured, the skin is *absent* around
each duct over **106° of azimuth** at z = 0, 60 and 120 (212 of 720 rays from the duct axis return no
material), i.e. a 78.8 mm-wide × 242 mm-long opening per duct. The fairing closes it and pays for it in
composite.

## 5. Ring seat untouched — verification

| check | result |
|---|---|
| `ring_v2_A.step` sha256 | `996B66E8…09C2` — **identical** to `dm-ring-redesign/SHA256SUMS.txt` |
| `ring_v2_B.step` sha256 | `37CE87A2…004B` — **identical** to `dm-ring-redesign/SHA256SUMS.txt` |
| ring bore, measured on those files | cylindrical faces at **r 41.035 = Ø82.070** and r 48.0 — unchanged |
| ring axial engagement, measured | bbox z **239.8 … 243.8 = 4.00 mm** land — unchanged |
| ring_v2_A ∩ duct_A (Ø82) | **0.000000 mm³** |
| ring_v2_B ∩ duct_B (Ø82) | **0.000000 mm³** |
| ring_v2_A/B ∩ faired fuselage | **0.000000** — bbox-separated: the fuselage's radius from the duct axis at z 239.8–243.8 is **16.5–16.7 mm**, 24 mm inside the ring's Ø82.070 bore |
| did this wave write to the ring or duct files? | **No** — they were opened read-only and the hashes above are the proof |

The seat is bit-identical because the *seat is not on the fuselage*: the ring is bonded to the Ø82 duct
OD at z 239.8–243.8, and the fuselage has never had material inside r 41 there. The fairing's gate ends
at z = 130 and its loft runout dies on the z = 200 station, so it never reaches the seat. What the
fairing does move near the tail is the fuselage's own surface (minimum radius from the duct axis at
z = 245: 16.5433 → 16.7244, +0.18 mm) — 24 mm away from any seat surface.

## 6. Final edge condition

**In the band, there is no bore/skin edge left to have an angle.** A ray census from each duct axis at
0.5° shows **0 open azimuths** at z = 0, 60, 120 and 150 (stock: 212, 262, 212 and 222) — the Ø85.2
cylinder is entirely inside the skin, so it cuts nothing on the flanks and the "rim" ceases to exist
there. What replaces it is a **land**: the wall between the bore (r 42.60) and the fairing surface.

| z | −90 | −70 | −30 | 0 | 60 | 120 | 150 | 180 | 210 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stock min land mm | 0.0006 | 0.0059 | 0.0270 | 0.0657 | 0.0375 | 0.0657 | 0.0293 | 0.0393 | 0.1672 |
| **faired min land mm** | **2.7529** | 0.7465 † | **2.8716** | **1.9129** | 0.1875 ‡ | **1.9129** | **1.3250** | 0.0242 | 0.1285 |

† at z = −70 the minimum is **not the bore** — it is the pre-existing **side-capture-slot lip**
(`dm-final-package` §3c / fab-checklist N22, z −90…−70, |azimuth| 43–45°), which this task does not own.
‡ at z = 60 the commanded 44.60 mm is not reached: the delivered 11-station loft interpolates to
**42.7875 mm** between its own stations, so the land falls to 0.1875 mm at the lower flank. Pinning a
station there *fixes the dip and splits the part into 3 solids* (§4) — the two are not separable.

**Final numbers.**

| quantity | value |
|---|---|
| **bore rim, min convex material angle, in the fairing band (z −112…+130)** | **none — the rim does not exist; the bore is fully enclosed** |
| land achieved in band | **1.91 / 1.91 / 1.33 mm** at z 0 / 120 / 150; 2.75 / 2.87 at z −90 / −30 |
| **part-wide minimum convex edge, faired part** | **5.1162°** at (±45.737, ±42.565, **+172.013**) — the bore rim *aft of the fairing*, where the 170 × 80 → 112 × 54 tail taper is unchanged |
| part-wide minimum on the stock part | 2.8334° at z −70.98 — the same feature, in the band the fairing fixes |
| rim samples below 10° | 136, over z −111.96 … +182.17 (was 116 over z −89.67 … −8.56) |

**Is the part free of knife edges? Not entirely, and the remainder is now bounded.** The Ø85.2 bore
breaks out at a 2.83° feather today; after this fix it breaks out nowhere between z −112 and +130, and
the worst edge anywhere on the part is **5.12° at z +172**, where the tail is narrower than the duct
(tail section 112 × 54 at z 250 versus a Ø85.2 bore at x = ±44). Closing *that* is a different job with
its own two proofs against it, both measured here: (i) the loft cannot be re-stationed — `stock2`, the
same table with no fairing, is **3 solids**; (ii) fairing the tail to Ø89.2 through z ≈ 235 would put
fuselage material inside r 41.04 at z 239.8–243.8, which is **the ring's Ø82.070 seat**. Either route
breaks something this wave was told not to break.

## 7. Reproduction and provenance

| script | produced |
|---|---|
| `work/k0_sizing.py` → `out/k0_sizing.json` | pre-build sizing: added area per section, the three mass routes, envelope check |
| `work/k1_probe.py` → `out/k1_probe.json` | face census of the shipped part: 6 cylinders at r 42.600, axis x = ±44; bbox; volume; validity |
| `work/k3_rimedges.py` → `out/k3_rimedges.json` | the bore-rim dihedral census (268 edges) and the global convex census over all 3,122 edges |
| `work/k4_build.py --mode stock` → `out/k4_stock.json` | identity control: reproduces 206,454.3208 / 320.0042 g / 540 faces / 1 solid, every stage to the digit |
| `work/k4_build.py --mode h9497` → `out/k4_h9497.json` | option (b), built: 2 solids, 403.7881 g |
| `work/k4_build.py --mode stock2` → `out/k4_stock2.json` | control for the station table: 3 solids with no fairing at all |
| `work/k4_build.py --mode fair --fair 44.6 "…"` → `out/k4_fair.json` | the executed fairing (`out/drone-mech_fuselage_rev2_fairing.step`) |
| `work/k4_build.py --mode fair --fair 43.8 …` (log `log/k4_fair.log`) | the Ø87.6 variant (`…_F43p8_variant.step`), 417.0968 g, land 0.38–1.89 mm |
| `work/k5_measure.py` → `out/k5_{stock,fair_v1,fair_v4}.json` | integrity, walls (2V/A per band), rim census, land profile |
| `work/k6_interference.py` → `out/k6_{stock,fair_v1,fair_v4}.json` | row-level pair sweep and the ring-seat checks |

Build chain copied verbatim from `dm-fore-fill/work/` (`s1_sections`, `s2_cavity_baseline`, `s3_fix`) and
the generator at `copy/highspeed_edf/phase15/optimization/phase15_generate_geometry.py`
(sha256 `8CC6E5DA…42BF51`, textually identical to the repo file; the byte difference is CRLF vs LF).
Inputs opened read-only from `evidence/dm-final-package/out/` and `evidence/dm-ring-redesign/out/`.
Nothing was written to a repo, nothing committed or reset, nothing written to `D:\CodeProjects` or
`E:\1vm\TMP`.

**Stated limits.** (i) The aft band z > 130 keeps a 5.12° rim; §6 gives the two measured reasons it
cannot be closed inside this task's constraints. (ii) The 0.1875 mm land at z = 60 is a loft
interpolation dip, not a fairing target shortfall; fixing it means re-stationing the loft, which is
measured to split the part. (iii) The pre-existing side-capture-slot lip knife edge at z −70 (0.75 mm
land) is a different feature and is untouched. (iv) The fairing is verified against the part set in
`dm-ring-redesign/out` only; the wing sectors were not re-coved, and the two `fuselage ↔ wing_sector`
rows (3,781.63 mm³ each) are pre-existing. (v) All masses are geometric at
1550 kg/m³ — no layup schedule, ply drop or fastener is modelled.

