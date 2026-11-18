"""Measure the real wall-normal first-cell distance on the c1 (passing) mesh.

checkMesh reports Min/max edge length = 0.0007399138455 m, but an edge length
is not the wall-normal height. This walks the actual polyMesh:

  for every `fsi` (and `rootWall`) boundary face:
      d_wall = | Sf_patch . (C_cell - Cf) | / |Sf|      # normal distance
                                                          from wall face
                                                          centre to cell centre
      and the exact OpenFOAM face-normal distance delta = Sf.(C - Cf)/|Sf|^2 * |Sf|

Reports the distribution (min, percentiles, max) of that distance, restricted to
the fsi patch so it is the *wing* wall spacing that matters.

Also reports, for the cells adjacent to the wall, their minimum edge length, so
the "first cell height" can be quoted either way.

Usage: python wall_distance.py <case> [--patches fsi rootWall]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import locate_cell as lc


def read_boundary(path: Path):
    text = path.read_text(errors="replace")
    body = text.split("// * * *", 1)[-1]
    import re
    blocks = re.findall(
        r"(\w+)\s*\{[^}]*?nFaces\s+(\d+);\s*startFace\s+(\d+);", body, re.S)
    return [(n, int(c), int(s)) for n, c, s in blocks]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("case", type=Path)
    ap.add_argument("--patches", nargs="*", default=["fsi", "rootWall"])
    args = ap.parse_args()

    mono = args.case / "constant" / "polyMesh"
    print(f"reading {mono}")
    points = np.asarray(lc.read_points(mono / "points"), dtype=np.float64)
    faces = lc.read_faces(mono / "faces")
    owner = np.asarray(lc.read_labellist(mono / "owner"), dtype=np.int64)
    neigh = np.asarray(lc.read_labellist(mono / "neighbour"), dtype=np.int64)
    n_cells = int(max(owner.max(), neigh.max())) + 1
    patches = read_boundary(mono / "boundary")
    print(f"points={len(points)} faces={len(faces)} cells={n_cells}")
    print("patches:", patches)

    # cell centres: average of the cell's face centres (OPENFOAM uses the
    # volume centroid; for these near-wall tets the two differ by <1%, which is
    # far below the spread we are reporting - noted as an approximation).
    cf_sum = np.zeros((n_cells, 3))
    cf_cnt = np.zeros(n_cells, dtype=np.int64)

    def face_data(fi):
        vs = faces[fi]
        p = points[vs]
        n = len(p)
        fc = p.mean(axis=0)
        if n == 3:
            Sf = np.cross(p[1] - p[0], p[2] - p[0]) / 2.0
        else:
            Sf = np.zeros(3)
            for k in range(1, n - 1):
                Sf += np.cross(p[k] - p[0], p[k + 1] - p[0]) / 2.0
        return fc, Sf

    rows = []
    for name, nf, sf in patches:
        if name not in args.patches:
            continue
        idx = range(sf, sf + nf)
        for fi in idx:
            fc, Sf = face_data(fi)
            c = int(owner[fi])
            rows.append((name, fi, c, fc, Sf))
            cf_sum[c] += fc
            cf_cnt[c] += 1

    # cell centres from boundary faces only is not enough; use full averaging
    # over ALL faces of each wall-adjacent cell instead
    wall_cells = sorted({r[2] for r in rows})
    print(f"wall-adjacent cells: {len(wall_cells)}")
    wallset = set(wall_cells)
    cf_sum = np.zeros((n_cells, 3))
    cf_cnt = np.zeros(n_cells, dtype=np.int64)
    for fi in range(len(faces)):
        o = int(owner[fi])
        if o in wallset:
            fc, _ = face_data(fi)
            cf_sum[o] += fc
            cf_cnt[o] += 1
    for fi in range(len(neigh)):
        n = int(neigh[fi])
        if n in wallset:
            fc, _ = face_data(fi)
            cf_sum[n] += fc
            cf_cnt[n] += 1
    C = np.zeros((n_cells, 3))
    mask = cf_cnt > 0
    C[mask] = cf_sum[mask] / cf_cnt[mask, None]

    dist = {p: [] for p in args.patches}
    for name, fi, c, fc, Sf in rows:
        Smag = np.linalg.norm(Sf)
        if Smag <= 0:
            continue
        d = abs(float(np.dot(Sf, C[c] - fc))) / Smag
        dist[name].append(d)

    for name in args.patches:
        a = np.asarray(dist[name])
        if a.size == 0:
            continue
        print(f"\n=== wall-normal distance, wall face centre -> first cell centre, patch '{name}' ===")
        print(f"  n = {a.size}")
        print(f"  min    = {a.min():.6e} m")
        for p in (1, 5, 25, 50, 75, 95, 99):
            print(f"  p{p:<2}    = {np.percentile(a, p):.6e} m")
        print(f"  max    = {a.max():.6e} m")
        print(f"  mean   = {a.mean():.6e} m  median = {np.median(a):.6e} m")

    # also: minimum edge length of the wall-adjacent cells
    emin_list = []
    owner_to_cells = {}
    for fi in range(len(faces)):
        o = int(owner[fi])
        if o in wallset:
            owner_to_cells.setdefault(o, []).append(fi)
    for fi in range(len(neigh)):
        n = int(neigh[fi])
        if n in wallset:
            owner_to_cells.setdefault(n, []).append(fi)
    for c, fl in owner_to_cells.items():
        vs = sorted({v for fi in fl for v in faces[fi]})
        p = points[vs]
        if len(p) < 2:
            continue
        d = np.linalg.norm(p[:, None, :] - p[None, :, :], axis=2)
        d[d == 0] = np.inf
        emin_list.append(d.min())
    e = np.asarray(emin_list)
    print(f"\n=== minimum edge length of wall-adjacent cells ===")
    print(f"  min={e.min():.6e} p5={np.percentile(e,5):.6e} median={np.median(e):.6e} max={e.max():.6e} m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())