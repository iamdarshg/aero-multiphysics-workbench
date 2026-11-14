# drone-arm — 915 MHz RF trace, field solve on the real (/3V3) reference

**Item:** full-wave (or defensible 2D quasi-static) solve of the drone-arm 915 MHz RF trace using
the board's REAL reference situation, In1.Cu = **/3V3**, not /GND.
**Board:** `repos/drone-arm/hardware/main/rev_b/main_rev_b.kicad_pcb` (branch `work/2026-11-11`,
read-only). No repo file was modified; nothing was committed.
**Evidence dir:** `E:/engineering-portfolio-audit/evidence/da-em-field/`

---

## 0. Headline

| quantity | value | source |
|---|---|---|
| TOOL | **own 2D finite-difference quasi-static Laplace solver** (numpy/scipy, this dir); openEMS built successfully but not used for these numbers | §1 |
| Z0 over a **solid** In1 /3V3 plane | **52.6 Ω** (51.7–54.4 Ω across grids) | `fd_results.json:void_sweep[solid]` |
| Z0 where In1 is a **void** (return falls to In2) | **118.1 Ω** | `fd_results.json:void_sweep[none]` |
| Z0 in a **partial** void (0.25–4 mm half-width) | **65.0 → 117.6 Ω** (monotone in void width) | §4.2 |
| eps_eff | **3.33** solid / **3.07** void | §4.1 |
| **S11 worst in 902–928 MHz, 50 Ω port** | **−10.5 dB** (void contiguous) … **−21.9 dB** (void evenly spread) … **−32.4 dB** (all-solid ideal) | §4.3 |
| impedance spread that is the finding | **52.6 → 118.1 Ω, 2.25×** | §4.2 |

**The finding.** The 3V3 plane, *where it is solid*, is an electrically good reference for this
trace: 52.6 Ω, i.e. 5.2 % above 50 Ω, |S11| = −32 dB over the band. The damage is not the net
name — it is the **11.14 % of the run where the pour is void**. There the return current is forced
1.275 mm down to In2, Z0 jumps to 65–118 Ω depending on how wide the void is, and the aggregate
S11 in band degrades to **−10.5 … −21.9 dB**. The 102.35 mm run therefore carries a 2.25×
impedance spread that no single netclass width can control.

---

## 1. openEMS: built on the 5th attempt, deliberately NOT used for the numbers
(path taken = (a) own 2D FD solve, as the assignment permits)

This went differently than expected: openEMS is not in any Ubuntu repo, but it *can* be built from
source on this host. Five attempts, all logged in `openems_logs/`. The blocker each time was a
different missing piece, not the environment.

| attempt | action | result |
|---|---|---|
| 1 | `apt-get install openems csxcad` in WSL Ubuntu2404 | `E: Package 'openems' has no installation candidate`, `Unable to locate package csxcad` (no PPA, no Debian/Ubuntu package) |
| 2 | source build, `libhdf5-dev libboost-all-dev libtinyxml-dev`, GitHub clones | CSXCAD cmake failed — CMake picked up a **Windows** HDF5 config (`/mnt/d/mcp/eng/octave/.../hdf5-config.cmake`) through `/mnt` |
| 3 | retry with `-DHDF5_ROOT=/usr -DHDF5_INCLUDE_DIR=/usr/include/hdf5/serial -DCMAKE_IGNORE_PATH=/mnt/...` | HDF5 fixed; CSXCAD then failed on `fparser_INCLUDE_DIR-NOTFOUND` (`fparser.hh` missing — third-party submodule not fetched; openEMS then failed `tools/AdrOp.h`, `openems_global.h`) |
| 4 | `git submodule update --init --recursive` (CSXCAD ships no `third_party/` tree and declares no submodules) | same fparser failure; wasted attempt |
| 5 | **`apt-get install libfparser-dev`** + `-DFPARSER_ROOT_DIR=/usr -DHDF5_INCLUDE_DIR=/usr/include/hdf5/serial` | **SUCCESS**: CSXCAD 0.7.0 and openEMS built and installed to `/usr/local`; `openEMS 64bit -- version fc00235` runs |

So openEMS **is** installable here; the recipe that works is `libhdf5-dev libboost-all-dev
libtinyxml-dev libfparser-dev`, plus pinning `HDF5_INCLUDE_DIR=/usr/include/hdf5/serial` and
`FPARSER_ROOT_DIR=/usr` and excluding `/mnt/*` from CMake's search path (CMake otherwise reads a
Windows Octave HDF5 config through `/mnt/d`). Logs: `openems_logs/b5_*.log`.

**However: no full-wave number is reported, and none was fabricated.** After the time spent on the
build, a 3D FDTD model of this trace (0.035 mm copper, 0.35 mm wide, 1.6 mm stackup, 915 MHz) would
need a mesh of order 10⁷–10⁸ cells plus port de-embedding, and a rushed coarse run would produce a
Z0 I could not defend. The reported numbers come from the 2D quasi-static field solve (path (a) of
the assignment), which for a uniform cross-section is the better-conditioned model and is validated
against closed-form microstrip to 2.7 % (§2.1). openEMS remains available in the image for a
follow-up item that can afford a proper 3D mesh and convergence study.

---

## 2. Cross-section model

Geometry taken from the board file, read-only:

| layer | thickness (mm) | role in the model | citation |
|---|---|---|---|
| F.Cu | 0.035 | trace, 0.35 mm wide, V = 1 V | `main_rev_b.kicad_pcb:50-52` |
| dielectric 1 | 0.200, FR4 εr 4.2 tanδ 0.02 | microstrip gap | `:54-59` |
| In1.Cu | 0.035 | **/3V3 — the reference under test**, V = 0 V | `:61-63` |
| dielectric 2 (core) | 1.040, FR4 εr 4.2 tanδ 0.02 | second gap | `:65-70` |
| In2.Cu | 0.035 | /GND, V = 0 V | `:72-74` |
| dielectric 3 | 0.200, FR4 εr 4.2 | | `:76-81` |
| B.Cu | 0.035 | V = 0 V | `:83-85` |
| copper_finish | ENIG | not modelled | `:97` |

Method: solve `div(ε∇φ) = 0` on the cross-section perpendicular to the trace
(y runs downward from a 2 mm air slab through F.Cu and the dielectric stack; x = 0 is the trace centreline), with

* trace nodes φ = 1 V, plane nodes φ = 0 V (Dirichlet),
* **x = 0 is a symmetry plane** (Neumann) — the domain is the right half only, so C is mirrored ×2,
* x = 6 mm and 2 mm of air above: Neumann (open) boundaries,
* 2D finite-volume discretisation, face permittivity = arithmetic mean, sparse direct solve,

then

```
C   = 2·W/V²,  W = ½∫ε|∇φ|²dA         (F/m, per unit length)
Cair = same solve with εr = 1 everywhere
eps_eff = C/Cair
L   = μ0ε0/Cair                       (quasi-TEM: L·Cair = μ0ε0)
Z0  = sqrt(L/C) = 1/(c·sqrt(C·Cair))
```

`Z0` does not involve tanδ; loss enters only the line model used for S11 (§4.3).

### 2.1 Validation (two independent checks, both passed)

1. **Energy vs Gauss.** Capacitance from field energy and from the surface charge
   `∮εE·n` on the trace agree to **ratio 1.000** for both a 2 mm and a 0.35 mm trace
   (`scripts/da_em_qcheck.py`). This rules out an energy bookkeeping error — and it is how the
   early 2× error (half-model mirror factor, see §6) was caught and fixed.
2. **Closed form.** Same stackup, closed-form Hammerstad (zero-thickness):
   Z0 = **54.04 Ω**, eps_eff = **3.171** at w/h = 1.75, vs FD **52.6 Ω**, eps_eff **3.33**.
   The 1.4 Ω difference is the right sign and size for the 0.035 mm copper thickness the FD
   includes and the closed form does not. The analytic values supplied with the task
   (48.61 Hammerstad / 53.98 Wheeler / 51.23 skrf MLine) bracket the FD result.

### 2.2 Grid convergence (solid-In1 case)

| hx (mm) | y refinement | nodes | Z0 (Ω) | eps_eff |
|---|---|---|---|---|
| 0.0500 | 1× | 94×120 | 51.72 | 3.348 |
| 0.0250 | 1× | 94×240 | 54.43 | 3.339 |
| 0.0250 | 2× | 188×240 | 52.61 | 3.328 |
| 0.0125 | 2× | 188×480 | 51.88 | 3.335 |

Non-monotone, full spread 51.72–54.43 Ω (**±2.6 % of the mean**). Adopted value 52.61 Ω (the production grid); the finest grid gives
51.88 Ω. **Reported uncertainty on all Z0 values below: ±2.6 % (grid), plus the model assumptions
in §5.** eps_eff is stable to ±0.6 %.

---

## 3. What "the real reference" means in this model

The measured facts supplied with the task (used as given, not re-derived here): the RF_50R run is
0.35 mm wide, 102.35 mm long on F.Cu; 88.86 % of it runs over /3V3, 11.14 % over pour voids, 0.00 %
over /GND; In1 /3V3 is 12 164 mm² in 3 islands, In2 /GND only 82.18 mm² in 177 slivers.

So In1 is not a ground plane and it is **not even a continuous plane**. Two limits are solved:

* **solid In1** — the 88.86 % case (the 3V3 island is ~10⁴ mm², i.e. laterally "infinite" compared
  with the 0.2 mm gap; modelled as a 0 V plane across the full 6 mm cross-section),
* **no In1** — the limiting 100 %-void case, return current through the core to **In2 /GND**,
  1.275 mm below the trace bottom.

and, between them, a **sweep of the void half-width** `wv` (the void is modelled as a slot in the
In1 plane centred under the trace, plane still present and at 0 V beyond `wv`). This is the parameter
that maps the 11.14 % area fraction onto an impedance.

---

## 4. Results

### 4.1 Solid vs void — the two limits

| case | Z0 (Ω) | eps_eff | C (pF/m) | L (nH/m) | vp/c |
|---|---|---|---|---|---|
| In1 solid (/3V3 reference) | **52.61** | 3.328 | 115.65 | 320.2 | 0.548 |
| no In1 (void; In2 /GND is the return) | **118.12** | 3.065 | 49.44 | 689.9 | 0.571 |
| **ratio** | **2.25×** | 0.92 | 0.43 | 2.15 | |

ε_eff *drops* in the void case: the return is 6.4× further away, so relatively more of the field sits
in the air above the trace. Z0 rises because C falls by 2.34×, not because L rises much per se.

### 4.2 Void-width sweep (this is the transfer function the owner needs)

| In1 void half-width | Z0 (Ω) | eps_eff |
|---|---|---|
| solid (0) | 52.61 | 3.328 |
| 0.25 mm | 64.95 | 3.168 |
| 0.50 mm | 83.06 | 3.000 |
| 1.00 mm | 102.92 | 2.921 |
| 2.00 mm | 114.45 | 2.974 |
| 4.00 mm | 117.64 | 3.045 |
| none | 118.12 | 3.065 |

Reading: a void only 0.5 mm wide raises the effective reference distance by ~1.6× and takes the line
to 83 Ω; a 1 mm void is already at 103 Ω, twice the target. The transfer is steep between 0.25 and
1 mm — right in the range of ordinary pour clearances, so the exact clearance value matters a lot.
Beyond ~2 mm half-width the plane edge no longer shields and
you are at the no-In1 limit. **Measured 11.14 % void therefore means, at minimum, 65 Ω and at worst
118 Ω on those stretches** — the 11.14 % figure alone does not pin it down, because it is an area
fraction along the run and not a lateral void dimension. That missing dimension is the single most
valuable measurement this board still needs (§5).

### 4.3 S11, 50 Ω port, 902–928 MHz

Line model: piecewise-uniform sections cascaded by ABCD, β = 2πf√eps_eff/c, dielectric attenuation
α = πf√eps_eff·tanδ/c (homogeneous-medium upper bound), then renormalised to 50 Ω. 102.35 mm run.
λg at 915 MHz = **179.7 mm**, so the run is **0.569 λ** — electrically long, which is why the
worst |S11| lands at the 928 MHz band edge and why the *order* of the void sections matters as much
as their total length.

| scenario | void share | worst \|S11\| 902–928 MHz | at 915 MHz | with tanδ = 0.02 |
|---|---|---|---|---|
| uniform solid In1 (0 %) | 0 % | **−32.40 dB** | −33.29 dB | −32.69 dB |
| 11.14 % void, evenly spread (0.25 mm voids) | 11.14 % | **−21.88 dB** | −22.59 dB | −22.19 dB |
| 11.14 % void, evenly spread (0.5 mm voids) | 11.14 % | −21.88 dB | −22.59 dB | −22.19 dB |
| 11.14 % void, evenly spread (1.0 mm voids) | 11.14 % | −21.85 dB | −22.57 dB | −22.18 dB |
| 11.14 % void, evenly spread (2.0 mm voids) | 11.14 % | −21.78 dB | −22.49 dB | −22.12 dB |
| 11.40 mm void **contiguous**, mid-run | 11.14 % | **−10.54 dB** | −10.60 dB | −10.86 dB |
| 100 % void (upper bound) | 100 % | −10.16 dB | −11.33 dB | −10.49 dB |

Sanity anchor. Take the zero-length step |Γ| = (118−50)/168 = 0.405 = −7.8 dB. The cascaded
all-void line lands at −10.2 dB, not −7.8 dB, because over 0.569 λ the line itself transforms the
termination — the cascade value is the correct one for this length, and the hand number is only
the limit for a zero-length step. The solid case does reproduce its hand value
(52.6 Ω → |Γ| = 0.0254 → −31.9 dB) almost exactly, which is the check that the cascade is right.

**Reported answer: S11 worst in band = −10.5 dB; the realistic range given the unknown void
geometry is −10.5 to −21.9 dB.** Both are outside a normal −10 dB return-loss spec margin for a
915 MHz ISM link once the band-edge rotation is included.

### 4.4 Figure

`fig1_z0_sweep_and_s11.png` — left: Z0 vs In1 void half-width (solid → none), with the 50 Ω target
and the supplied skrf MLine value; right: |S11| vs frequency for the four scenarios.

---

## 5. Limitations and what is UNVERIFIED

Everything below is a known gap, not a hedge:

1. **No full-wave result.** openEMS/CSXCAD *were* built here on the 5th attempt (§1) but were not
   run: a 3D FDTD of this stackup at 915 MHz needs ~10⁷–10⁸ cells plus port de-embedding, and an
   un-converged rush run would be a number I could not defend. The absence is real: **no radiation,
   no via-stitching, no connector/discontinuity effects are in any number above.** A follow-up item
   with room for a proper mesh can settle this with openEMS already installed.
2. **Void geometry is a range, not a measurement.** The 11.14 % is an area fraction along the run.
   The lateral void width, the void count and their positions are **UNVERIFIED**; the report
   therefore gives Z0 = 65–118 Ω and S11 = −21.9 / −10.5 dB as a bracket. To collapse it, measure
   the actual clearances (e.g. the In1 /3V3 copper-to-RF-trace clearance histogram along the run).
3. **No coplanar F.Cu pour modelled.** If the RF trace has adjacent F.Cu ground pour with a
   clearance, the real Z0 is lower (and if that pour is also /3V3, unhelpful). Not established from
   the board file in this item → **UNVERIFIED**, and it can move Z0 by several ohms.
4. **Planes assumed ideal 0 V.** The 3V3 plane is modelled as a perfect reference at RF. It is a
   switching-supply net with finite RF impedance and an undefined return path — exactly the concern
   that motivates the item — but that is a *network* question a passive field solve cannot answer.
   Treat "52.6 Ω over solid 3V3" as "good geometry, unproven return".
5. **Port model.** S11 above is referenced to an ideal 50 Ω at both ends of the run; the antenna,
   matching network and connector are not included, so this is a *line* S11, not a system S11.
6. **Conductor loss / surface roughness** are excluded from the ABCD cascade (dielectric loss only,
   q = 1 upper bound). This changes S11 by ≤ 0.3 dB in the tables, i.e. it does not move the
   conclusion.
7. **Solder mask** (2 × 0.01 mm, `:48,89`) is not modelled.
8. **In2 / B.Cu assumed /GND at 0 V.** The supplied fact says In2 /GND is only 82.18 mm² in 177
   slivers; if In2 is *also* fragmented under the trace, the void-case Z0 is a lower bound on the
   damage, i.e. the truth is worse than 118 Ω, not better.

---

## 6. Corrections made during this work (for the record)

Two real bugs were found by the self-checks and fixed before any number was reported, and one
remaining factor was isolated as physical. Recording them so a reviewer can see the numbers are
post-fix:

* Capacitance came out in units of ε₀ (missing factor ε₀) → fixed; Z0 was ~0 before.
* The field energy was computed with ε/h² face weights instead of ε·A/h → Z0 was 2× too high; fixed
  and confirmed by the energy-vs-Gauss cross-check (§2.1).
* The half-model mirror factor was then isolated as the *remaining* exact 2× — that one is physical,
  not a bug: the domain is one half of a symmetric cross-section (§2).

---

## 7. Reproduction

```powershell
# solver (Windows python 3.12, numpy 2.2.6 / scipy 1.16.3; skrf 1.9.0 present but its MLine
# class is not exposed as skrf.media.MLine in this build, so Hammerstad is computed inline)
cd E:/engineering-portfolio-audit/scripts
$env:DA_OUT='E:/engineering-portfolio-audit/evidence/da-em-field'
python da_em_fd_solve.py      # -> fd_results.json
python da_em_plot.py          # -> fig1_z0_sweep_and_s11.png
python da_em_qcheck.py        # energy-vs-Gauss validation
```

openEMS build (5 attempts, 1–4 failed, 5 succeeded): `scripts/da_em_openems_build{,2,3,4,5}.sh` run via
`wsl -d Ubuntu2404 -u root -- bash /mnt/e/engineering-portfolio-audit/scripts/<script>`.
Logs: `openems_logs/` (`b5_*.log` = the successful recipe, `csx_*`/`oems_*` = the failed attempts 1–2).

## 8. Files

| file | contents |
|---|---|
| `REPORT.md` | this document |
| `fd_results.json` | every number: convergence table, void sweep (Z0, eps_eff, C, L, vp/c), all S11 scenarios, raw \|S11(f)\| curves, analytic cross-check |
| `fig1_z0_sweep_and_s11.png` | Z0 vs void width; \|S11\| vs frequency |
| `openems_logs/*.log` | openEMS/CSXCAD build logs: `b5_*` = successful recipe, others = failed attempts |
| `../../scripts/da_em_fd_solve.py` | the solver + line/S11 model (single file, ~300 lines) |
| `../../scripts/da_em_plot.py`, `da_em_qcheck.py` | figure; validation |