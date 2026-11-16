# dm-ring-redesign — vane bearing ring: partial-arc redesign + a real seat

Wave · specialist task · **drone-mech highspeed_edf / phase15_geometry** (DM-FUS-001 REV 1).
Started 2026-11-17. Status: **COMPLETE — all six steps answered, fix executed on copies.**

Scope: stop the two vane-bearing rings interpenetrating, give them a defined seat, re-issue a
defensible interference figure, and dispose of the knife edge. Inputs read-only; everything
executed on **copies** under `out/`. No write to any repo, no commit, no reset, nothing written to
`D:\CodeProjects` or `E:\1vm\TMP`.

Prior work not re-derived: `evidence/dm-bearing-rings/REPORT.md` — ring↔ring 754.749861 mm³,
ring↔fuselage 1,048.409726 mm³ each, OD 96 on 88 mm centres, `VANE_RING_RADIUS = 44` = half the
spacing, the "fit" = 10.8 mm diametral = 28.1 σ_y.

Tags: `[SRC]` repo source · `[MEASURED]` computed here from the copies · `[PRIOR]` from
`dm-bearing-rings` · `[ANALYTIC]` closed form · `[DESIGN]` a decision made here.

### Instrument control before any claim

Volume = `BRepGProp.VolumeProperties_s(eps = 1e-12)`; boolean = `BRepAlgoAPI_Common` on native
B-reps; census = `IntCurvesFace_ShapeIntersector` radial rays; bbox = `BRepBndLib.AddOptimal`.

Two identity checks, because a hash match is not a geometry match and here it is the reverse:

| check | result |
|---|---|
| repo ring STEPs (9,598 / 9,593 B) vs the copies measured in `dm-bearing-rings` (9,354 / 9,349 B) | **bytes differ, geometry identical**: 1 solid, 4 faces, **7,828.848893 mm³** each — serialization only, so the prior measurements carry over |
| `phase15_geometry/…/fuselage_battery_bay_shell_endpoint_relief_42_6.step` | a **4-solid / 511-face / 742,306.359538 mm³ compound**; ring∩compound = ring∩REV 1 = **1,048.409726** exactly, so the body of record inside it is DM-FUS-001 REV 1 (**1 solid, 540 faces, 206,454.319709 mm³**) |

---

## 1. Where the ring radius is defined, and what is derived from what

Four definitions, all in `highspeed_edf/phase15/optimization/phase15_generate_geometry.py`:

```python
:35-38   DUCT_OD = 82.0                  # +2 from nominal 80 to keep 2 mm radial wall
         DUCT_ID = 78.0
         DUCT_WALL_RADIAL = (DUCT_OD - DUCT_ID) / 2.0
         DUCT_CENTRES_X = (-44.0, 44.0) # 88 mm centre spacing
...
:88      VANE_RING_RADIUS = 44.0
...
:199     def annulus(ro: float, ri: float, z0: float, length: float,
                     x0: float = 0.0, y0: float = 0.0) -> cq.Solid:
:201         outer = cq.Solid.makeCylinder(ro, length, Vector(x0, y0, z0), Vector(0, 0, 1))
:202         inner = cq.Solid.makeCylinder(ri, length, Vector(x0, y0, z0), Vector(0, 0, 1))
:203         return outer.cut(inner)
...
:980         ring = annulus(48.0, 41.0, 250.0, 4.0, xcentre)
:981         add_part(f"duct_{letter}_vector_vane_bearing_ring", ring, "6061-T6", aluminum_color)
```

**`ro = 48.0` is independent of `VANE_RING_RADIUS`.** It is a bare literal in the call. The whole
file references `VANE_RING_RADIUS` in exactly four places, none of them the ring:

```python
:88      VANE_RING_RADIUS = 44.0
:435     px = xcentre + VANE_RING_RADIUS * math.cos(th)      # vane pivot
:436     py = VANE_RING_RADIUS * math.sin(th)
:807     "vaneCount": 4, "vaneSizeMm": list(VANE_SIZE), "vaneRingRadiusMm": VANE_RING_RADIUS,
```
plus `phase15_servo_torque_screen.py:48`, which only reads `vaneRingRadiusMm` back out of the
parameter register. `ri = 41.0` is likewise a literal, equal to `DUCT_OD/2` but not written as it.

The relationship exists only as **intent**, not as code: `41 + 7 = 48` is the 7 mm wall, and
`41 + 3 = 44` puts the pivot 3 mm out into that wall. So the ring is the only part in the file whose
two governing dimensions are both un-derived magic numbers — which is exactly why nothing caught
OD 96 on 88 mm centres.

**Therefore the number to change is the literal at `:980` — not `VANE_RING_RADIUS`.** The pivot
radius must stay 44: the vanes are placed from it (`:435`), the servo mounts are placed from a
literal 44 (`:987`), and `:807` publishes it. Shrinking the pivot radius would move the control
surfaces, which is not this task.

## 2. The arithmetic that constrains the fix — three options, measured

Two full annuli of outer radius **R** on 88 mm centres do not touch iff `2R ≤ 88`, i.e. **R ≤ 44 /
OD ≤ 88**. The part is OD 96, so each pair is forced to overlap by the lens `{r_A ≤ 48} ∩ {r_B ≤ 48}`
— measured **754.749861 mm³**, bbox x ±3.539773, y ±19.183326 [MEASURED, reproduces `[PRIOR]` to
the last digit].

| option | measured result | verdict |
|---|---|---|
| **(a)** shrink `ro` ≤ 44 (OD ≤ 88) | `ro=44`: twin **0.000000** (but *exactly tangent* — zero clearance) and fuselage still **312.042804**; `ro=43` (OD 86): fuselage still **89.230888** | **refuted on function** |
| **(b)** move the duct centres apart | needs spacing ≥ 96 + clearance = **≥ 97 mm (+10.2 %)**; measured against the as-drawn body: ±48.5 → 260.552961, ±49 → 156.508670, ±50 → **13.670233** | **refuted on arithmetic** |
| **(c)** partial arcs that stop before the mid-plane | notch half-angle **47°** → ring↔twin **0.000000**, ring↔fuselage **0.000000** | **supported — executed** |

**(a) is refuted by an identity, not a tolerance.** The burial depth is
`ro − r_bore = 48.0 − 42.5 = 5.5 mm` nominal (`48.0 − 42.6 = 5.4` measured) — it depends on the
bore radius alone and **not at all on the duct spacing**. So (a) only clears the fuselage at
`ro ≤ 42.6`, which leaves a wall from r 41.0 to 42.6 — and then the pivot circle at r = 44 lies
**1.4 mm outside the part**. The clash is removed by removing the part's function. `ro = 44` also
puts the pivot exactly *on* the outer edge, i.e. zero material outboard of a bearing that needs a
boss around it.

**(b) is refuted by the same identity**: the burial is spacing-independent, so moving the ducts buys
ring↔ring and nothing else — at 100 mm centres the ring is *still* 13.670233 mm³ inside the web.
It also re-lofts the body, the wing centre bridge, the bore positions and the inlet paths for no gain.

**(c) is what the geometry supports, and it is the only option that is also a real part.** A vane
carrier is a bracket around two pivot boss locations at azimuth 90° / 270°; it has no reason to be
continuous at the inboard 94° where the two ducts meet. The inboard notch is where the part was
never needed — and it is exactly the arc that was (i) buried in the inter-duct web and (ii) reaching
into its twin.

Notch selection is measured, not chosen by eye. Census of fuselage material inside the ring's radial
band (r 41…48) about each duct axis, at three stations across the part:

| z | material half-width about the inboard radial | ring↔fuselage at notch 45° / 46° / 47° |
|---|---|---|
| 239.9 | **45.5°** | 0.365692 / 0.000071 / **0.000000** |
| 241.8 | 44.5° | (same sweep) |
| 243.7 | 43.0° | (same sweep) |

So **notch = 47°**, giving a 1.5° margin = **1.26 mm** of clearance at the OD — and the boolean says
so: 45° leaves 0.365692 mm³, 46° leaves a 0.000071 mm³ sliver, **47° is exactly 0.000000**. Ring↔twin
is 0.000000 from 45° upward (the notch, not the OD, is what separates them). Sweep in `out/r2_redesign.json`.

### The third clash, which neither census contains: ring ↔ vane, 56.004744 mm³ × 4

Sweeping the ring against the whole part set found **4 more pairs**:

| pair | mm³ | solids |
|---|---:|---:|
| ring A ↔ vane A1 | **56.004744** | 1 |
| ring A ↔ vane A2 | **56.004744** | 1 |
| ring B ↔ vane B1 | **56.004744** | 1 |
| ring B ↔ vane B2 | **56.004744** | 1 |

The vane solid is three pieces totalling 2,617.646003 mm³ = blade 2,400.000 + shaft 169.646 + horn
48.000 [MEASURED, exact]. The **blade is 30 mm radially × 2 mm tangentially × 40 mm axially**
(bbox x −45…−43, y **29…59**, z 240…280): centred at the pivot r = 44, it spans r 29…59 and therefore
crosses the ring's entire 7 mm wall (41…48) — 7 × 2 × 4 = 56 mm³, which is the measured volume.

This is not negotiable by tolerancing: the blade has **no radial hole**, so any ring material that
straddles r 41…48 at azimuth 90° / 270° is cut by it, and any clearance cut is a **slit through the
wall**. The carrier is therefore **slotted at the two pivots**, and the slot severs the arc. The same
defect makes the vane itself impossible: the blade also passes through the duct wall —
**vane ↔ nozzle+lip = 20.002085 mm³** (r 39…41, z 240…242) [MEASURED] — so a 30 mm plate at r = 44
cannot physically exist in this duct. That is a vane/actuator redesign, out of scope, recorded so it
is not mistaken for a ring defect.

## 3. The seat

**First, the finding that governs the design: the ring has no seat anywhere, and the fuselage cannot
give it one.** As filed the ring is at z 250…254 while the duct ends at z 245 (nozzle 110…242, exit
lip 242…245) — so its Ø82 bore engages **nothing at all**: the part floats 5 mm aft of the duct.
And at those stations the body is a tapered tail: the fuselage's half-height is ≈ 26 mm at z = 252,
which is **less than the ring's bore radius of 41 mm**, so **0 of the 360° of the ring's bore circle
can touch the fuselage**; the only body material inside r 41…48 is the inter-duct web — a ~2.8 mm
wide membrane on the centreline — and that is precisely the material the ring is buried in. A
counterbore in the fuselage is not merely inadvisable (as `dm-bearing-rings` §3 showed on two
independent grounds); **there is no material there to cut one in**. The seat must be on the duct OD,
which is the interface the ring's bore was always aimed at.

**DESIGN — bonded collar on the exit-lip OD with a moulded stop bead.**

| item | value |
|---|---|
| ring position | **z 239.80 … 243.80** (moves 10.2 mm forward, onto the duct: nozzle to 242, lip 242…245) |
| cylindrical engagement | **4.00 mm** on the Ø82 duct OD (was 0.00 mm) |
| ring bore | **Ø82.070** |
| duct OD | Ø82.000 (`annulus(41, 39)` — the duct's OD is a single Ø82 cylinder from z 0 to 245, no shoulder anywhere) |
| **fit class** | **H7 / f7** — H7 = +0.000/+0.035, f7 = −0.036/−0.056 on Ø82 → clearance **0.036…0.091 mm diametral** = an 18…46 µm radial bondline; modelled at Ø82.070 = **0.035 mm radial, measured min = max = 0.035** |
| seat depth | **4.00 mm** land, plus a **1.20 mm** stop shoulder |
| axial stop | new moulded **bead Ø84.00 × 1.20 mm wide at z 243.80…245.00** (the last 1.2 mm of the lip, flush with its aft face); ring's aft face bears on the bead's forward face → takes the aft/thrust case, the bond takes the forward case |
| contact areas | shoulder **251.732 mm²**; bonded land **1,030.442 mm²** |
| **seat overlap volume** | **0.000000 mm³** — by construction; see below |
| measured | ring ∩ (nozzle + bead) = **0.000000** each; bead ∩ fuselage = **0.000000**, min radial clearance to the web **1.4715 mm** |

**Why H7/f7 and not H7/p6.** The legitimate press the prior report named (H7/p6 on Ø82 = 0.002…0.059
mm diametral) is fine *in 6061* — at 0.059 mm the ring sees 42.3 MPa = 0.15 σ_y. The receiver is the
problem: the duct is a **2 mm CFRP wall** (`annulus(41, 39)`). At the p6 mid-band interference of
0.0305 mm the contact pressure is ≈ E·δ/d = 68.9e3 × 0.0305/82 ≈ **25.6 MPa**, and the tube's hoop
stress is p·d/2t = 25.6 × 82 / 4 ≈ **525 MPa** — roughly an order of magnitude past the transverse
strength of a CF/epoxy tube (~50–80 MPa). A press would crush the duct, not grip it. So the joint is
a **bonded clearance fit**, and the deliberate contact is a declared bondline plus a bearing
shoulder face — not a volume. For the record, if a press *were* used the deliberate overlap would be
**15.72 mm³ per ring** [ANALYTIC] (0.0305 mm diametral × π·Ø82 × 4 mm); stated, not used.

*On the brief's "60 mm-class bore".* No bore in this assembly is 60 mm-class: the ring bore is **Ø82**,
the fuselage duct bore **Ø85**, the pivot circle **Ø88**. The fit is therefore cited on the actual
Ø82 interface, in the ISO 286 band *over 80 to 120 mm* (IT7 = 35 µm, IT6 = 22 µm). Nothing here
assumes a Ø60 bearing — `dm-bearing-rings` §2 established that the only bearing numbers in the corpus
(623ZZ/624ZZ) belong to the hinge test rig, so a bearing cannot be assumed at all.

## 4. Executed, on copies

`work/r2_redesign.py`, `work/r3_final.py`, `work/r4_options.py` (cadquery 2.7.0 / OCP 7.8.1.1,
`C:/Program Files/Python312/python.exe`). Outputs `out/ring_v2_A.step`, `out/ring_v2_A.brep` (+B).

Ring v2 = `annulus(ro 48.0, ri 41.035, z 239.8, len 4.0)` **minus** an inboard wedge **±47°**
**minus** two **2.4 mm** through-wall slots at azimuth 90° / 270° (0.2 mm clear per face on the
2.0 mm blade). Neutral section unchanged: 7 mm wall, 4 mm thick, 6061-T6.

**The part is three solids per duct** — unavoidable, because the vane slot is a slit through the wall:

| piece | azimuth span | volume mm³ | mass g |
|---|---|---:|---:|
| stiffener arc | 91.6 … 268.4 | **3,829.511858** | 10.340 |
| pivot ear (90°) | 47 … 88.4 | **897.366771** | 2.423 |
| pivot ear (270°) | 271.6 … 313 | **897.366771** | 2.423 |
| **total** | 259.7° of arc (266° before the two slots) | **5,624.245400** | **15.1855** |

All three pieces are individually bonded to the same Ø82 land, so all three are retained. If a
single-piece part is required, drop the mid arc: **2 ears = 1,794.733543 mm³ / 2 solids / 4.8458 g**
[MEASURED] — recommended, since the mid arc carries no pivot, but not delivered because it stops the
object being "the ring".

Pair sweep, all with bbox prefilter then exact boolean — **13 distinct pair booleans** on the executed
part (12 bbox-overlapping rows in `r3`, plus the ring↔ring pair verified explicitly in `r2` and `r4`,
whose bboxes do not overlap), 46 rows excluded by bbox (never assumed):

| pair | volume mm³ |
|---|---:|
| ring_A_v2 ↔ ring_B_v2 | **0.000000** |
| ring_A_v2 ↔ fuselage_rev1 | **0.000000** |
| ring_A_v2 ↔ wing_left | 0.000000 |
| ring_A_v2 ↔ nozzle_A | 0.000000 |
| ring_A_v2 ↔ vane_A1 / vane_A2 | 0.000000 / 0.000000 |
| ring_A_v2 ↔ bead_A | 0.000000 |
| ring_B_v2 ↔ the six mirrors | 0.000000 (each) |

Ring A v2 also passes the twin's nominal Ø85 bore (0.000000) and its own (0.000000). Total over every
ring row: **0.000000 mm³**.

## 5. The interference figure (row-level, set diff)

As modelled, measured here on the same copies (the 7 ring rows are the ones this fix acts on):

| # | pair | mm³ | class |
|---|---|---:|---|
| 1 | ring A ↔ fuselage | 1,048.409726 | genuine clash — buried in the web |
| 2 | ring B ↔ fuselage | 1,048.409726 | genuine clash — buried in the web |
| 3 | ring A ↔ ring B | 754.749861 | genuine clash — OD 96 on 88 mm centres |
| 4-7 | ring A/B ↔ vane A1/A2/B1/B2 | 56.004744 ×4 = **224.018976** | genuine clash — **new, found here** |
| | **ring subtotal (7 rows)** | **3,075.588289** | |
| 8-13 | the six elevon ↔ {motor R3, nozzle, fuselage} rows | **1,556.232076** | unchanged by this fix |
| | **airframe total as modelled** | **4,631.820365** | **13 pairs, 0 unclassified** |

**After the fix:** ring rows **3,075.588289 → 0.000000**; total **4,631.820365 → 1,556.232076** in
**6 pairs**. Set diff: **7 rows removed, 0 rows added, 0 rows changed**.

**Fuselage: one valid solid still holds — and the earlier figure is CONFIRMED, not corrected.**
1 solid, 540 faces, **206,454.319709 mm³**, **320.0042 g** at 1.55 g/cm³ (PLA-core-CF-wrap). It is
untouched: this fix makes no cut in it, which is the point — the relief that `dm-bearing-rings` ruled
out is now unnecessary.

**Mass set diff:** ring 21.14 → **15.1855 g** each (−5.9545, ×2 = −11.909); bead **+0.485 g** each
(312.93 mm³ CFRP, ×2 = +0.970); **net −10.939 g** on the airframe.

**One reconciliation item, flagged not hidden.** My six elevon rows measure **1,556.232076**, while
`dm-bearing-rings` records **1,204.481397** for the same six *named* pairs (+351.750679), and my two
elevon↔pushrod rows measure **0.000000** where it records 4.534020. Same parts, same copies, so the
difference lies in wave 17's pair definitions (which motor-can row; whether "fuselage wall" meant the
body or the wing sector) — which is `[PRIOR]`, explicitly not re-derived there, and re-deriving it is
a different task. **It does not touch this wave's conclusion**, because all seven rows this fix
removes are ring rows measured identically before and after.

## 6. Knife edge at the duct-bore / hull rim

Mechanism, reproduced analytically from the generator's own constants (`BODY_WIDTH 186`,
`BODY_HEIGHT 88`, `BODY_EXPONENT 2.6`, bore `makeCylinder(42.5, …)` at x = ±44):

* the hull's **minimum radius from a duct axis is 40.7627 mm** (at azimuth 102.8°), while the bore
  wall needs **42.5 / 42.6 mm** — so the Ø85 bore **breaks out through the upper and lower hull skin**;
* maximum breakout depth **1.806 mm**;
* cross-check against the two numbers `dm-bearing-rings` measured independently: at 12.28 mm off-axis
  (x = −56.28) this model gives hull |y| = **38.965** and bore demand **40.792**, against their
  **38.97 / 40.79** — agreement to 0.005 mm, so the mechanism is confirmed, not assumed;
* the rim is a *breakout boundary*, so the dihedral starts at **0°** and grows only like √depth. At
  ≤ 4° the material 50 µm from the line is 2 × 50 × tan 2° = **3.49 µm**, reproducing the measured
  3.5 µm exactly. The edge is not a sharp corner that could be chamfered; it is a vanishing wedge.

**What removes it:** give the hull a land. The hull's radius from each duct axis must reach
**42.6 + 1.2 = 43.8 mm**, i.e. a **Ø87.6 fairing circle** around each duct over the breakout band —
practically a **per-duct fairing boss blended ~20 mm axially** into the loft (this is the real fix:
a duct where it passes through a skin gets a fairing). The global equivalent is `BODY_HEIGHT`
**88 → 94.97 mm (+7.9 %)**, which is not affordable. **A 0.3 mm offset or an R0.5 fillet alone is not
enough** — the shortfall is 1.806 mm, so there is nowhere for the fillet to exist; once the land
exists the rim is a ~70–90° edge and an R0.5 at the bore exit becomes good practice rather than the
fix. This corrects the prior recommendation's magnitude while keeping its direction.

**Interaction with the ring fix: none, and one coupling to guard.** Geometrically they are 300 mm
apart (knife edge z −55…−71; ring z 239.8…245) and the fuselage solid is untouched by this wave, so
206,454.319709 mm³ / 320.0042 g stands. The coupling to name: the fairing must **not** alter the duct
OD (Ø82) — if the knife edge were instead "fixed" by shrinking the Ø85 bore, the duct OD/ID (82/78)
and therefore the ring's Ø82 seat would move with it. The fairing is the right lever precisely
because it leaves Ø82 alone.

## 7. Reproduction and provenance

| script | produced |
|---|---|
| `work/v0_probe.py` → `out/v0_probe.json` | geometry identity of all 18 STEP copies vs the two prior copies; the 4-solid compound check |
| `work/r1_pairs.py` → `out/r1_pairs.json` | as-filed row-level sweep (ring↔ring, ring↔fuselage, ring↔vane) + band census at the filed station |
| `work/r2_redesign.py` → `out/r2_redesign.json` | notch sweep 45…52° × slots, executed part, seat check, ears-only variant |
| `work/r3_final.py` → `out/r3_final.json` | full-set ring sweep (bbox-prefiltered), bead check, elevator census, integrity + mass |
| `work/r4_options.py` → `out/r4_options.json` | options (a) ro 44/43, (b) centres ±48.5/49/50, per-solid volumes, vane solid census |
| `work/r5_knife.py` → `out/r5_knife.json` | min hull radius, breakout depth, required land, global lever, wedge arithmetic |
| `work/r6_vane.py` → `out/r6_vane.json` | vane ↔ duct wall (20.002085 mm³), context for why the carrier must be slotted |

Raw stdout in `log/`. Every input in `out/*.step` is a byte-identical copy of
`repos/drone-mech/highspeed_edf/deliverables/phase15_geometry/step/…` except
`drone-mech_fuselage_rev1.step`, copied from `evidence/dm-bearing-rings/out/` (sha256
`D9BA7AEB…CB9CADF`, volume 206,454.319709 — the same solid). Repo untouched, nothing committed,
nothing reset.

**Stated limits.** (i) The full airframe was swept for the *rings* only, so the six elevon rows are
carried at their measured current values and were not re-attributed; (ii) the notch/seat was solved
against DM-FUS-001 REV 1 as shipped, so if the body is re-lofted for the §6 fairing the 47° notch
must be re-censused (it is a 1.5° margin); (iii) the ring still has **no load path to the vane** — the
vane's stub axle sits at z 260 while any carrier at the blade's station is slotted by the blade, so
the pivot bearing needs a clevis outside the blade's plane, which is a vane/actuator redesign and is
**declared, not executed**; (iv) no bearing is specified, because the corpus contains no bearing for
this part.