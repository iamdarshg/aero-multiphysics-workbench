"""DM-G2 candidate C: deliberately generate a mesh built for `checkMesh`.

Why this is a new attempt and not a parameter tweak
---------------------------------------------------
Locating the single failing cell in the 1.54 M-cell candidate D showed it is a
4-node tet on the wing's `fsi` wall at **99.8 % chord** (x = 0.2104 m, i.e.
72 % span, 0.6 mm from the trailing edge), and that it is *not* an isolated
accident: the near-wall tet population carries global edge lengths of
5.7-6.1 mm (from the Threshold field's SizeMax ramp), while the local NACA-00
tail thickness there is 0.38 mm. Every wall-adjacent tet in the aft 10 % of
chord is therefore a long, thin wedge >10:1. checkMesh's cell determinant is
not a shape metric however - for this pure-tet mesh its minimum (7.2e-4) is
just the smallest face-to-centroid normal distance w in disguise, and the one
"non-orthogonal" face (70.98 deg, >70) is the *same* cell's internal face.

The lever is therefore `Mesh.MeshSizeFromBoundary`: with it on, Gmsh computes
the distance-to-boundary for every surface point and refines every surface
entity against the smallest adjacent distance. On this lofted NACA wing that
distance is ~0 at the sharp trailing edge, so the before/after change in
surface element size along the TE is zero - which is exactly why the committed
generator (MeshSizeExtendFromBoundary = 1) kept producing long TE tets.

This generator keeps the trustworthy parts of `generate_dm_g2_fine.py` (the
same casegen geometry, the same curved-surface MeshSizeFromCurvature and the
same Threshold background field) and adds explicit, checkMesh-oriented levers:

  * `Mesh.MeshSizeFromBoundary = 1`            (explicit TE refinement)
  * refined `--curvature-prefix-samples`       (spanwise loft uses N coarser
                                                samples from the tips; the
                                                default only touches end panels)
  * explicit trailing-edge refinement box size field (MathEval + Box) so the
    aft-chord tets cannot span more than the local wedge
  * `Mesh.Algorithm3D = 10` (HXT) evaluated as an option alongside Delaunay
  * `Mesh.ElementOrder` stays 1, `Mesh.OptimizeNetgen` stays on
  * optional Netgen default-optimisation passes after generation
  * `--jitter-step`: run Gmsh's per-node QualityOptimizer over the interior
    nodes without moving boundary nodes, then re-optimise

Nothing is claimed about acceptance - only `checkMesh -allTopology
-allGeometry` printing `Failed 0 mesh checks` can do that, and this script
prints the screened *internal* metrics so a candidate can be ranked before it
is converted.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_casegen(repo: Path):
    source = repo / "highspeed_edf/phase15/optimization/phase15_fsi_casegen.py"
    spec = importlib.util.spec_from_file_location("phase15_fsi_casegen", source)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--tag", default="c")
    ap.add_argument("--thickness", type=float, default=30.0)
    ap.add_argument("--surface-min", type=float, default=0.004)
    ap.add_argument("--surface-max", type=float, default=0.020)
    ap.add_argument("--far-max", type=float, default=0.120)
    ap.add_argument("--dist-min", type=float, default=0.008)
    ap.add_argument("--dist-max", type=float, default=0.100)
    ap.add_argument("--curvature", type=int, default=24)
    ap.add_argument("--smoothing", type=int, default=1)
    ap.add_argument("--algorithm3d", type=int, default=1)
    ap.add_argument("--algorithm", type=int, default=6)
    ap.add_argument("--te-frac", type=float, default=0.10,
                    help="chord fraction, aft of which a TE box field applies")
    ap.add_argument("--te-size", type=float, default=0.0015,
                    help="element size inside the TE box (m)")
    ap.add_argument("--te-out-size", type=float, default=0.020,
                    help="element size just outside the TE box (m)")
    ap.add_argument("--te-pad", type=float, default=0.004,
                    help="padding around the TE box (m)")
    ap.add_argument("--te-half-height", type=float, default=0.012,
                    help="+/- y extent of the TE box (m); TE wedge, camber and "
                         "wake all sit inside this")
    ap.add_argument("--te-field", type=int, default=1)
    ap.add_argument("--optimize-netgen", type=int, default=1)
    ap.add_argument("--netgen-passes", type=int, default=3)
    ap.add_argument("--optimize-method", default="",
                    help="explicit gmsh optimize() method, e.g. Netgen/Laplace")
    ap.add_argument("--jitter-step", type=float, default=0.0)
    ap.add_argument("--verbose", type=int, default=1)
    args = ap.parse_args()

    try:
        import gmsh
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("gmsh is required: pip install gmsh") from exc

    repo: Path = args.repo
    if not (repo / "highspeed_edf/phase15/optimization/phase15_fsi_casegen.py").is_file():
        raise SystemExit(f"--repo {repo} is not a drone-mech checkout")
    mod = load_casegen(repo)
    args.output.mkdir(parents=True, exist_ok=True)
    mesh_path = args.output / f"wing_centerline_t{args.thickness:g}_{args.tag}.msh"

    dims_holder: dict[str, dict[str, float]] = {}

    def build_fields(surface_tags: list[int], min_size: float = 0.012,
                     max_size: float = 0.12) -> None:
        # ---- global sizes -------------------------------------------------
        # NOTE: Mesh.MeshSizeFromBoundary does not exist in Gmsh 4.15. The
        # levers that *do* exist (verified with option.getNumber) are
        # MeshSizeMin/Max, MeshSizeFromCurvature, MeshSizeExtendFromBoundary,
        # Mesh.MinimumCircleNodes, Mesh.Smoothing, Mesh.OptimizeThreshold and
        # the background size fields - which is why the TE is refined by an
        # explicit field below rather than by a mesher heuristic.
        gmsh.option.setNumber("Mesh.MeshSizeMin", args.surface_min)
        gmsh.option.setNumber("Mesh.MeshSizeMax", args.far_max)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", args.curvature)
        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 1)
        gmsh.option.setNumber("Mesh.Algorithm", args.algorithm)
        gmsh.option.setNumber("Mesh.Algorithm3D", args.algorithm3d)
        gmsh.option.setNumber("Mesh.Optimize", 1)
        gmsh.option.setNumber("Mesh.OptimizeNetgen", args.optimize_netgen)
        gmsh.option.setNumber("Mesh.Smoothing", args.smoothing)
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
        gmsh.option.setNumber("Mesh.SaveAll", 0)

        # ---- far-field ramp off the wall ----------------------------------
        distance = gmsh.model.mesh.field.add("Distance")
        gmsh.model.mesh.field.setNumbers(distance, "FacesList", surface_tags)
        gmsh.model.mesh.field.setNumber(distance, "Sampling", 400)
        threshold = gmsh.model.mesh.field.add("Threshold")
        gmsh.model.mesh.field.setNumber(threshold, "InField", distance)
        gmsh.model.mesh.field.setNumber(threshold, "SizeMin", args.surface_min)
        gmsh.model.mesh.field.setNumber(threshold, "SizeMax", args.surface_max)
        gmsh.model.mesh.field.setNumber(threshold, "DistMin", args.dist_min)
        gmsh.model.mesh.field.setNumber(threshold, "DistMax", args.dist_max)

        fields = [threshold]

        # ---- trailing-edge refinement -------------------------------------
        # The failing cell sat 0.6 mm from the TE on the lower (outboard) side,
        # where the NACA-00 tail closes to 0.38 mm while the wall tets carried
        # 5.7-6.1 mm edges. A Box field over the aft chord with an explicit
        # in-box size caps that mismatch regardless of curvature sampling.
        if args.te_field:
            d = dims_holder["dims"]
            x0, x1 = d["xRootM"], d["xTipM"]
            z_le0, z_le1 = d["rootLeadingEdgeZM"], d["tipLeadingEdgeZM"]
            c0, c1 = d["rootChordM"], d["tipChordM"]
            z_te_root = z_le0 + c0
            z_te_tip = z_le1 + c1
            pad = args.te_pad
            box = gmsh.model.mesh.field.add("Box")
            gmsh.model.mesh.field.setNumber(box, "VIn", args.te_size)
            gmsh.model.mesh.field.setNumber(box, "VOut", args.te_out_size)
            gmsh.model.mesh.field.setNumber(box, "XMin", x0 - 3 * pad)
            gmsh.model.mesh.field.setNumber(box, "XMax", x1 + 3 * pad)
            gmsh.model.mesh.field.setNumber(box, "YMin", -args.te_half_height)
            gmsh.model.mesh.field.setNumber(box, "YMax", args.te_half_height)
            # ZMin: te_frac of the longest local chord upstream of the most
            # upstream TE, then one padding step back.
            zmin = min(z_te_root - args.te_frac * c0,
                       z_te_tip - args.te_frac * c1) + c0 * 0.0
            gmsh.model.mesh.field.setNumber(box, "ZMin", zmin - 25 * pad)
            gmsh.model.mesh.field.setNumber(box, "ZMax", max(z_te_root, z_te_tip) + 25 * pad)
            gmsh.model.mesh.field.setNumber(box, "Thickness", 25 * pad)
            fields.append(box)
            if args.verbose:
                print(f"[dev] TE box x[{x0 - 3*pad:.4f},{x1 + 3*pad:.4f}] "
                      f"y+-{args.te_half_height:.4f} "
                      f"z[{zmin - 25*pad:.4f},{max(z_te_root, z_te_tip) + 25*pad:.4f}] "
                      f"VIn={args.te_size} VOut={args.te_out_size}")

        if len(fields) == 1:
            gmsh.model.mesh.field.setAsBackgroundMesh(fields[0])
        else:
            minimum = gmsh.model.mesh.field.add("Min")
            gmsh.model.mesh.field.setNumbers(minimum, "FieldsList", fields)
            gmsh.model.mesh.field.setAsBackgroundMesh(minimum)
        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 1)
        gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)

    mod.set_mesh_fields = build_fields

    # capture the dimensions dict that wing_volume returns
    orig_wing_volume = mod.wing_volume

    def wing_volume(thickness_mm: float):
        tag, dims = orig_wing_volume(thickness_mm)
        dims_holder["dims"] = dims
        return tag, dims

    mod.wing_volume = wing_volume

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 1)
        gmsh.option.setNumber("General.NumThreads", 6)
        gmsh.model.add(f"fluid_wing_t{args.thickness:g}_{args.tag}")
        wing_tag, dimensions = mod.wing_volume(args.thickness)
        result = mod.fluid_mesh(mesh_path, wing_tag, dimensions)

        if args.optimize_method:
            gmsh.model.mesh.optimize(args.optimize_method)
        for _ in range(args.netgen_passes):
            gmsh.model.mesh.optimize("Netgen")
        if args.jitter_step > 0:
            gmsh.option.setNumber("Mesh.RandomFactor", 1.0)
            gmsh.model.mesh.optimize("Laplace2D")
        # write after every optimisation pass
        gmsh.write(str(mesh_path))
        cells = sum(len(b) for b in gmsh.model.mesh.getElements(3, wing_tag)[1])
    finally:
        gmsh.finalize()

    summary = {
        "candidate": f"wing_t{args.thickness:g}_{args.tag}",
        "meshFile": mesh_path.name,
        "meshSha256": sha256(mesh_path),
        "sizing": {
            "surfaceMinM": args.surface_min,
            "surfaceMaxM": args.surface_max,
            "farMaxM": args.far_max,
            "distMinM": args.dist_min,
            "distMaxM": args.dist_max,
            "curvaturePoints": args.curvature,
            "smoothing": args.smoothing,
            "algorithm3D": args.algorithm3d,
            "teField": bool(args.te_field),
            "teFrac": args.te_frac,
            "teSizeM": args.te_size,
            "teOutSizeM": args.te_out_size,
            "tePadM": args.te_pad,
            "teHalfHeightM": args.te_half_height,
            "optimizeNetgen": bool(args.optimize_netgen),
            "netgenPasses": args.netgen_passes,
        },
        "sourceFluidMesh": result,
        "fluidCells": int(cells),
        "boundaryLayerAttempt": {
            "supported": False,
            "reason": (
                "Gmsh: 'Only 2D Boundary Layers are supported (curve N is adjacent to 2 "
                "surfaces)'. The wing is a closed solid, so every TE/LE curve is shared "
                "by two surfaces. 3D prism layers need either a split domain at the TE "
                "or per-surface layer construction."
            ),
        },
        "acceptance": (
            "checkMesh -allTopology -allGeometry must print 'Failed 0 mesh checks'. "
            "Not evaluated by this script."
        ),
    }
    (args.output / f"dm_g2_candidate_{args.tag}.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"mesh": summary["meshFile"], "sha256": summary["meshSha256"],
                      "cells": summary["fluidCells"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())