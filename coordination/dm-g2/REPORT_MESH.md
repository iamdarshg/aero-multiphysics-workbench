# DM-G2 — Mesh Quality Report: from `Failed 2` to `Mesh OK.`

**Goal.** Get the Phase-15 half-wing transonic CFD mesh to `Failed 0 mesh checks`
under OpenFOAM `checkMesh -allTopology -allGeometry`.

**Result: achieved.** The c1 candidate prints `Mesh OK.` with zero failed checks.

**Final mesh.** `cand-c/wing_centerline_t30_c1.msh`
(`sha256 7fadb8d7bc42fad17d5f5d000fb34449ccdb31d95d0494e51058eda25cbae08d`),
1,690,534 cells, 100 % tetrahedra.

---

## 1. Progression

| Stage | Mesh | Cells | Failed checks | Worst defect | max non-ortho | max skew |
|---|---|---|---|---|---|---|
| Baseline (committed) | `wing_centerline_t30_bl.msh` | 49,208 | **2** | 411 cells det < 0.001 (min 0); 14 faces interp wt < 0.05 | 83.4644 | 2.7743 |
| Fine candidate | `fine/wing_centerline_t30_fine.msh` | 1,537,282 | **1** | 1 cell det < 0.001 (min 7.215e-4) | 70.975 | 0.8715 |
| **c1 (final)** | `cand-c/wing_centerline_t30_c1.msh` | 1,690,534 | **0** | *none* — `Mesh OK.` | **69.2962** | **0.8748** |

c1 vs the fine candidate: cell count +10 %, one extra Netgen pass budget, and a
trailing-edge refinement field. The failing cell is gone and the single
non-orthogonal face (70.98°) drops to 69.30°, just inside the 70° gate.

---

## 2. Where the defect was

The instruction was to locate the failing cell before regenerating. It was
located by parsing the `underdeterminedCells` and `nonOrthoFaces` sets that
`checkMesh` writes, then mapping the centroid onto the exact casegen geometry
(`tools/locate_cell.py`, `tools/where_is_cell.py`, `tools/wing_section.py`).

**The bad cell was cell 74880:**

| Quantity | Value |
|---|---|
| centroid | (0.210368, −0.001049, 0.155391) m |
| volume | 1.4912e-09 m³ |
| nodes / faces | 4 / 4 (tetrahedron) |
| attached wall patch | **`fsi`** (wing surface), one boundary face |
| spanwise position | x = 130.04 mm from root — **72.4 % span** |
| **chordwise position** | f = 0.9981 — **99.81 % chord, ~0.6 mm from the TE** |
| local chord / thickness | 327.91 mm / **0.380 mm** (t/c 0.0915) |
| side | **lower surface**, 0.71 mm below it, at fraction 2.87 of half-thickness |
| wall-normal distance | 0.91 mm |

**The single non-orthogonal face (69.3°→70.98°) was face 253060 — a face of the
same cell.** So both remaining failures were one location, not two.

**Interpretation.** The failure was at the **trailing edge on the lower
surface, 72 % span**, where the NACA-00-like tail closes to 0.38 mm. The
near-wall tets there carried edges of 5.7–6.1 mm, so each was a long thin wedge
>10:1. A near-TE census (`tools/te_cluster.py`, half-extents 12 × 6 × 12 mm about the
failing centroid) showed **282 tets inside that 6.9 cm³ probe box, all at the
TE**, the smallest only 1.39x worse than the checkMesh winner — i.e. the failing
cell was the worst member of a cluster, not an isolated accident.

**This is why global parameter tweaking was the wrong lever:** the defect was
a *geometric mismatch between wall-tet size and the local TE wedge*, not an
unlucky element.

---

## 3. What was tried, in order

| # | Attempt | Outcome |
|---|---|---|
| 1 | Locate the failing cell via `checkMesh` sets + geometry mapping | ✅ Both remaining failures resolve to one TE lower-surface cell at 72 % span |
| 2 | Near-TE cluster census to characterise the defect class | ✅ 282-cell TE cluster; failing cell is its worst member |
| 3 | **Trace the root cause**: measure the global edge-length floor | ✅ A hard 0.7399 mm minimum edge appears in *every* mesh — set by `MeshSizeFromCurvature` on the TE arc, not by any size field |
| 4 | Establish that `Mesh.MeshSizeFromBoundary` **does not exist** in Gmsh 4.15 (the originally-planned lever) | ✅ Verified against `option.getNumber`; planned API was wrong |
| 5 | Enumerate the options that *do* exist (`MeshSizeMin/Max`, `MeshSizeFromCurvature`, `MeshSizeExtendFromBoundary`, `Smoothing`, `OptimizeThreshold`, background fields) | ✅ Background size field is the only usable lever |
| 6 | Coarse smoke mesh to validate the field pipeline end-to-end (gmsh → `gmshToFoam` → `checkMesh`) | ✅ Pipeline validated: 358,348 cells, conversion + checkMesh clean |
| 7 | **c1: TE refinement box field** (`--te-field 1 --te-frac 0.15 --te-size 0.0012`), 3 Netgen passes | ✅ **`Mesh OK.`** |
| 8 | Internal tet screening of c1 vs fine (`tools/screen_quality.py`) | ⓘ Worst shape metric barely moved (0.0509→0.0545), *yet checkMesh passed* |

### The winning change

A **`Box` size field** over the aft 15 % of chord, composed with the existing
distance-based `Threshold` field via a `Min` field, so the mesher is forced to
respect an explicit element size right where the TE wedge closes:

```
x  [0.0683, 0.2720]  (span + 3x pad)
y  ± 0.0140          (both surfaces, camber and wake)
z  [-0.0028, 0.2562] (root TE 0.15538 .. tip TE 0.15624, padded)
VIn  = 0.0012 m      (in-box size, ~3x the local TE tail thickness)
VOut = 0.020 m       (ramp back to the wall-field size)
Thickness = 0.10 m   (25 x pad transition band)
```

Te box geometry was verified against the actual TE locus
(root TE z = 0.15538, tip TE z = 0.15624) and the failing cell at z = 0.15539 sits
directly inside it.

Parameters changed vs the fine candidate: `--te-field 1 --te-frac 0.15
--te-size 0.0012 --te-out-size 0.020 --te-pad 0.004 --te-half-height 0.014`,
`--netgen-passes 3`. All wall-field sizes left at the fine candidate's values
(`--surface-min 0.004 --surface-max 0.020 --dist-min 0.008 --dist-max 0.100
--curvature 24`).

### An honest note on *why* it passed

The internal shape metric (`6V/Lmax³`) moved only marginally. The mechanism that
actually cleared the gate is **not** cleaner tet shapes; it is that the TE
cluster was spread over a wider spanwise extent (worst tets now run from
x = 0.095 to 0.26 instead of clustering at one spot), which shifted the specific
worst cell's determinant above 1e-3. This is a real, reproducible pass verified
by `checkMesh`, but it should be understood as **moving the distribution clear of
the threshold, not eliminating the underlying >10:1 near-wall TE tets**. Adding
near-wall resolution in that region would still be the principled fix; see
`REPORT_YPLUS.md` §7 for what that costs and why Gmsh cannot easily do it.

---

## 4. Final checkMesh log

`checkMesh -allTopology -allGeometry`, `opencfd/openfoam-default:2406`.
Full log: [`checkMesh-c1-FINAL.log`](checkMesh-c1-FINAL.log).

```
Mesh stats
    points:           302814
    faces:            3418704
    internal faces:   3343432
    cells:            1690534
    faces per cell:   4
    boundary patches: 5
    point zones:      0
    face zones:       0
    cell zones:       1

Overall number of cells of each type:
    hexahedra:     0
    prisms:        0
    wedges:        0
    pyramids:      0
    tet wedges:    0
    tetrahedra:    1690534
    polyhedra:     0

Checking topology...
    Boundary definition OK.
    Cell to face addressing OK.
    Point usage OK.
    Upper triangular ordering OK.
    Face vertices OK.
    Topological cell zip-up check OK.
    Face-face connectivity OK.
    Number of regions: 1 (OK).

Checking patch topology for multiply connected surfaces...
    Patch               Faces    Points     Surface topology  Bounding box
    fsi                 21680    10955    ok (non-closed singly connected)   (0.08033 -0.01520058561 -0.2325415058) (0.26 0.01489108218 0.1562399911)
    rootWall            1582     906      ok (non-closed singly connected)   (0.08033 -0.01520058561 -0.2325415058) (0.08033 0.01488073249 0.1553831096)
    farfield            42490    21431    ok (non-closed singly connected)   (-0.4045757692 -0.35 -0.6204661212) (0.7449057692 0.35 1.320013837)
    outlet              4760     2474     ok (non-closed singly connected)   (-0.4045757692 -0.35 1.320013837) (0.7449057692 0.35 1.320013837)
    inlet               4760     2474     ok (non-closed singly connected)   (-0.4045757692 -0.35 -0.6204661212) (0.7449057692 0.35 -0.6204661212)
    ".*"                75272    37640    ok (closed singly connected)       (-0.4045757692 -0.35 -0.6204661212) (0.7449057692 0.35 1.320013837)

Checking faceZone topology for multiply connected surfaces...
    No faceZones found.

Checking basic cellZone addressing...
    CellZone            Cells        Points       Volume       BoundingBox
    fluid               1690534      302814       1.560104825  (-0.4045757692 -0.35 -0.6204661212) (0.7449057692 0.35 1.320013837)

Checking basic pointZone addressing...
    No pointZones found.

Checking geometry...
    Overall domain bounding box (-0.4045757692 -0.35 -0.6204661212) (0.7449057692 0.35 1.320013837)
    Mesh has 3 geometric (non-empty/wedge) directions (1 1 1)
    Mesh has 3 solution (non-empty) directions (1 1 1)
    Boundary openness (-3.118136798e-18 3.913610839e-18 1.103826499e-16) OK.
    Max cell openness = 2.833437635e-16 OK.
    Max aspect ratio = 6.122065947 OK.
    Minimum face area = 2.932383389e-07. Maximum face area = 0.0007134658641.  Face area magnitudes OK.
    Min volume = 2.283713206e-10. Max volume = 5.978781673e-06.  Total volume = 1.560104825.  Cell volumes OK.
    Mesh non-orthogonality Max: 69.29622863 average: 14.41836477
    Non-orthogonality check OK.
    Face pyramids OK.
    Max skewness = 0.8748047081 OK.
    Coupled point location match (average 0) OK.
    Face tets OK.
    Min/max edge length = 0.0007399138455 0.04672234702 OK.
    All angles in faces OK.
    All face flatness OK.
    Cell determinant (wellposedness) : minimum: 0.001171646759 average: 0.2154366022
    Cell determinant check OK.
    Concave cell check OK.
    Face interpolation weight : minimum: 0.1255347383 average: 0.459857367
    Face interpolation weight check OK.
    Face volume ratio : minimum: 0.1435560036 average: 0.8573925451
    Face volume ratio check OK.

Mesh OK.

End
```

### Gate-by-gate

| Check | Baseline | Fine candidate | **c1** |
|---|---|---|---|
| Cells with determinant < 0.001 | 411 (min 0) | 1 (min 7.215e-4) | **0 (min 1.1716e-3)** ✅ |
| Faces with interpolation weight < 0.05 | 14 | 0 | **0 (min 0.1255)** ✅ |
| max non-orthogonality | 83.4644 | 70.975 (1 face > 70) | **69.2962 (0 faces > 70)** ✅ |
| max skewness | 2.7743 | 0.8715 | **0.8748** ✅ |
| **Failed checks** | **2** | **1** | **0 — `Mesh OK.`** ✅ |

---

## 5. Standing constraints (do not re-derive)

- **3D prism layers are impossible on this geometry.** Gmsh raises
  `Only 2D Boundary Layers are supported (curve N is adjacent to 2 surfaces)`.
  The wing is a closed solid, so every TE/LE curve is shared by two surfaces. At
  t/c ≈ 0.077 (30 mm on a 388 mm chord) prisms need either a domain split at the
  TE or per-surface extrusion. **This is an all-tet problem.**
- **`Mesh.MeshSizeFromBoundary` does not exist in Gmsh 4.15.** Verify any option
  name with `gmsh.option.getNumber(name)` before building on it.
- **The `Box` field accepts only** `VIn`, `VOut`, `XMin/Max`, `YMin/Max`,
  `ZMin/Max`, `Thickness` — not `Box` or `VIncBuffer`.
- **`gmshToFoam` needs a complete case** (`system/controlDict` present) or it
  aborts with a `nullptr` dereference that looks like a mesh failure but is not.
- **A stale/partial case directory** likewise produces a `nullptr` abort. Build a
  clean case per attempt (see `tools/checkmesh.sh`).

---

## 6. Artefacts

| Path | Contents |
|---|---|
| `cand-c/wing_centerline_t30_c1.msh` | **the passing mesh** (1,690,534 tets) |
| `cand-c/dm_g2_candidate_c1.json` | sizing record + sha256 |
| `checkMesh-c1-FINAL.log` | full `checkMesh` log, `Mesh OK.` |
| `logs/gen-c1.log` | gmsh generation log |
| `tools/generate_dm_g2_candidate.py` | generator (TE box field, `Min` composition) |
| `tools/locate_cell.py` | parse `checkMesh` sets → centroid, volume, extent |
| `tools/where_is_cell.py` | which wall patch the bad cell touches |
| `tools/wing_section.py` | map a point to chordwise fraction / local thickness |
| `tools/te_cluster.py` | near-TE tet census |
| `tools/screen_quality.py` | internal tet quality screening (no OpenFOAM needed) |
| `tools/checkmesh.sh` | container-side convert + `checkMesh` harness |
| `tools/run-checkmesh.ps1` | Windows-side driver |
| `REPORT_YPLUS.md` | wall-treatment / y+ assessment of this mesh |

### Generator invocation

```
python tools/generate_dm_g2_candidate.py \
  --repo E:\engineering-portfolio-audit\repos\drone-mech \
  --output cand-c --tag c1 \
  --surface-min 0.004 --surface-max 0.020 --far-max 0.120 \
  --dist-min 0.008 --dist-max 0.100 --curvature 24 \
  --algorithm3d 1 --te-field 1 --te-frac 0.15 --te-size 0.0012 \
  --te-out-size 0.020 --te-pad 0.004 --te-half-height 0.014 \
  --netgen-passes 3
```

---

## 7. Boundaries

- Mesh quality only. **No** claim of solver convergence, force, drag, or
  accuracy. `Mesh OK.` is a geometry/topology statement, not a CFD result.
- The passing cell has `det = 1.17e-3` against a `1e-3` threshold — a **17 %
  margin**, not a comfortable one. A different `gmsh` build or option default
  could shift it back below the gate. Re-verify with `checkMesh` if the mesh is
  regenerated.
- The mesh has **no boundary layers**; wall treatment is therefore uncontrolled
  by construction. See `REPORT_YPLUS.md` — median y+ is 134/191/261 at
  700/800/900 km/h, which forces a wall-function treatment, and at 900 km/h
  21–24 % of the wing surface exceeds y+ 300 (a material limitation).