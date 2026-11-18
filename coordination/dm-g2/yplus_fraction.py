"""Exact fraction of wall faces above y+ thresholds, using every fsi face.

wall_distance.py reports percentiles; for the "how much of the surface is
outside the wall-function band" question we need the exact count. This rescans
the c1 polyMesh and reports, for each anchor and chord, the fraction of the
21,680 fsi faces whose first-cell y+ exceeds 300 (upper wall-function limit).

Re-run: python yplus_fraction.py <case>
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import numpy as np

import locate_cell as lc

R_AIR = 287.05
T = 268.65
MU = 1.716e-5 * (T / 273.15) ** 1.5 * (273.15 + 110.4) / (T + 110.4)

ANCHORS = [("700", 222.13, 22429.0), ("800", 252.81, 29053.0), ("900", 283.17, 36450.0)]
CHORDS = [("root", 0.388), ("tip", 0.305)]

# y+ is evaluated with the ROOT-chord Cf for both chords of the root figure and
# the tip-chord Cf for the tip figure (matching yplus.py).
def cf_central(re: float) -> float:
    v = [0.0592 / re ** 0.2, 0.455 / math.log(0.06 * re) ** 2,
         0.027 / re ** (1 / 7), 0.026 / re ** (1 / 7)]
    return sum(v) / len(v)


def read_boundary(path: Path):
    body = path.read_text(errors="replace").split("// * * *", 1)[-1]
    return [(n, int(c), int(s)) for n, c, s in
            re.findall(r"(\w+)\s*\{[^}]*?nFaces\s+(\d+);\s*startFace\s+(\d+);", body, re.S)]


def main() -> int:
    case = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("../work-c1")
    mono = case / "constant" / "polyMesh"
    points = np.asarray(lc.read_points(mono / "points"), dtype=np.float64)
    faces = lc.read_faces(mono / "faces")
    owner = np.asarray(lc.read_labellist(mono / "owner"), dtype=np.int64)
    neigh = np.asarray(lc.read_labellist(mono / "neighbour"), dtype=np.int64)
    patches = read_boundary(mono / "boundary")
    wall = [(n, c, s) for n, c, s in patches if n == "fsi"]
    if not wall:
        raise SystemExit("no fsi patch")
    _, nf, sf = wall[0]

    # cell centres of wall-adjacent cells (face-centre average)
    cells = sorted({int(owner[f]) for f in range(sf, sf + nf)})
    cset = set(cells)
    acc = {c: [np.zeros(3), 0] for c in cells}
    for fi in range(len(faces)):
        o = int(owner[fi])
        if o in cset:
            acc[o][0] += points[faces[fi]].mean(axis=0)
            acc[o][1] += 1
    for fi in range(len(neigh)):
        nb = int(neigh[fi])
        if nb in cset:
            acc[nb][0] += points[faces[fi]].mean(axis=0)
            acc[nb][1] += 1

    dist = np.empty(nf)
    for k, fi in enumerate(range(sf, sf + nf)):
        p = points[faces[fi]]
        if len(p) == 3:
            Sf = np.cross(p[1] - p[0], p[2] - p[0]) / 2.0
        else:
            Sf = np.zeros(3)
            for m in range(1, len(p) - 1):
                Sf += np.cross(p[m] - p[0], p[m + 1] - p[0]) / 2.0
        fc = p.mean(axis=0)
        c = int(owner[sf + k])
        C = acc[c][0] / acc[c][1]
        dist[k] = abs(float(np.dot(Sf, C - fc))) / np.linalg.norm(Sf)

    print(f"fsi faces: {nf}   dist: min={dist.min():.4e} med={np.median(dist):.4e} "
          f"max={dist.max():.4e}")
    print(f"\n{'anchor':>6} {'chord':>5} {'u_tau':>7} {'y+med':>6} "
          f"{'%>300':>7} {'%>150':>7} {'%<30':>6}")
    for name, U, p in ANCHORS:
        rho = p / (R_AIR * T)
        nu = MU / rho
        for label, c in CHORDS:
            re = U * c / nu
            cfa = cf_central(re)
            utau = U * math.sqrt(cfa / 2)
            yp = rho * utau * dist / MU
            print(f"{name:>6} {label:>5} {utau:7.3f} {np.median(yp):6.0f} "
                  f"{100*np.mean(yp>300):6.1f}% {100*np.mean(yp>150):6.1f}% "
                  f"{100*np.mean(yp<30):5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())