"""DM-G2 wall-treatment analysis: what y+ does the passing all-tet mesh imply?

Computes, for the three Phase-15 campaign anchors, the turbulent skin-friction
coefficient, friction velocity and the resulting y+ for the first cell centre
of the c1 mesh, then states the wall-function verdict.

Formulae and assumptions are stated inline; every number in REPORT_YPLUS.md is
produced by this script so it can be re-run.

Air properties (ISA at 3 km, quoted by the campaign brief):
  p = 22,429 / 29,053 / 36,450 Pa   -> rho = p/(R T),  T = 268.65 K (ISA 3 km)
  (ISA 3 km: T = 288.15 - 0.0065*3000 = 268.65 K, p = 70121 Pa is sea level;
   the brief gives p directly, so rho is computed from the brief's p.)

Skin friction - four LOCAL flat-plate correlations, all at Re_x = Re_c:
  (a) Prandtl-Schlichting, local      Cf = 0.0592 / Re_x^0.2
  (b) White (Viscous Fluid Flow 6.19) Cf = 0.455 / ln^2(0.06 Re_x)
  (c) 1/7-power law                   Cf = 0.027 / Re_x^(1/7)
  (d) 1/7-power law (0.026 variant)   Cf = 0.026 / Re_x^(1/7)

  These four agree to within ~4% over Re 1.2e6-3.1e6, so the *central* Cf is
  their mean and the spread is quoted as the band. Karman-Schoenherr is
  deliberately NOT used: the 1/sqrt(2Cf) = log10(Re Cf) - 0.65 form with that
  constant gives Cf ~ 3e-2 at these Reynolds numbers, an order of magnitude
  above the accepted local value, i.e. its constants are for a different
  (mean-skin-friction, ln-Re family) definition and it is not applicable here.

Friction velocity: u_tau = U_inf * sqrt(Cf/2)
y+              = rho * u_tau * y / mu ,  y = distance wall -> first cell centre

The near-wall cell distance is measured from the actual c1 polyMesh by
wall_distance.py, not assumed.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

R_AIR = 287.05  # J/(kg K)
T_ISA_3KM = 268.65  # K
MU = 1.789e-5  # Pa s, Sutherland at 268.65 K is close; stated as a constant
# Sutherland at 268.65 K: mu = 1.716e-5*(T/273.15)^1.5*(273.15+110.4)/(T+110.4)


def sutherland(t: float) -> float:
    return 1.716e-5 * (t / 273.15) ** 1.5 * (273.15 + 110.4) / (t + 110.4)


ANCHORS = [
    {"name": "700 km/h IAS", "mach": 0.6760, "u": 222.13, "p": 22429.0},
    {"name": "800 km/h IAS", "mach": 0.7694, "u": 252.81, "p": 29053.0},
    {"name": "900 km/h IAS", "mach": 0.8618, "u": 283.17, "p": 36450.0},
]

CHORDS = {"root": 0.388, "tip": 0.305}


def cf_prandtl_schlichting(re: float) -> float:
    # Prandtl-Schlichting, LOCAL flat-plate skin friction.
    return 0.0592 / re ** 0.2


def cf_white(re: float) -> float:
    # White, Viscous Fluid Flow eq. 6.19, LOCAL turbulent flat-plate Cf.
    return 0.455 / math.log(0.06 * re) ** 2


def cf_powerlaw(re: float, k: float) -> float:
    # 1/7th-power velocity profile, LOCAL Cf = k / Re_x^(1/7).
    return k / re ** (1.0 / 7.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--y", type=float, default=None,
                    help="wall-normal distance to first cell centre (m)")
    ap.add_argument("--y-p5", type=float, default=None)
    ap.add_argument("--y-min", type=float, default=None)
    ap.add_argument("--y-median", type=float, default=None)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    mu = sutherland(T_ISA_3KM)
    print(f"T = {T_ISA_3KM} K (ISA 3 km), mu = Sutherland = {mu:.5e} Pa s "
          f"(catalog 1.789e-5 Pa s at 288.15 K)")
    print(f"R = {R_AIR} J/kg/K\n")

    out = {"temperatureK": T_ISA_3KM, "muPas": mu, "anchors": []}
    for a in ANCHORS:
        rho = a["p"] / (R_AIR * T_ISA_3KM)
        nu = mu / rho
        row = {"name": a["name"], "mach": a["mach"], "u": a["u"],
               "p": a["p"], "rho": rho, "nu": nu, "chords": {}}
        print(f"=== {a['name']}: M={a['mach']} U={a['u']} m/s p={a['p']:.0f} Pa")
        print(f"    rho = {rho:.5f} kg/m3   mu = {mu:.4e} Pa s   nu = {nu:.5e} m2/s")
        for label, c in CHORDS.items():
            re = a["u"] * c / nu
            cf_ps = cf_prandtl_schlichting(re)
            cf_wh = cf_white(re)
            cf_pl = cf_powerlaw(re, 0.027)
            cf_pl2 = cf_powerlaw(re, 0.026)
            vals = [cf_ps, cf_wh, cf_pl, cf_pl2]
            cf = sum(vals) / len(vals)
            cf_lo, cf_hi = min(vals), max(vals)
            utau = a["u"] * math.sqrt(cf / 2.0)
            utau_lo = a["u"] * math.sqrt(cf_lo / 2.0)
            utau_hi = a["u"] * math.sqrt(cf_hi / 2.0)
            print(f"    chord {label} = {c:.3f} m")
            print(f"      Re_c                          = {re:.4e}")
            print(f"      Cf Prandtl-Schlichting 0.0592/Re^.2 = {cf_ps:.5e}")
            print(f"      Cf White 0.455/ln^2(0.06Re)        = {cf_wh:.5e}")
            print(f"      Cf 1/7-law 0.027/Re^(1/7)          = {cf_pl:.5e}")
            print(f"      Cf 1/7-law 0.026/Re^(1/7)          = {cf_pl2:.5e}")
            print(f"      -> Cf central = {cf:.5e}   band {cf_lo:.4e}..{cf_hi:.4e} "
                  f"(+/-{100*(cf_hi-cf_lo)/2/cf:.1f}%)")
            print(f"      u_tau = U sqrt(Cf/2) = {utau:.4f} m/s   "
                  f"(band {utau_lo:.3f}..{utau_hi:.3f})")
            if args.y:
                ypl = rho * utau * args.y / mu
                ypl_lo = rho * utau_lo * args.y / mu
                ypl_hi = rho * utau_hi * args.y / mu
                print(f"      y+ at y={args.y*1e3:.4f} mm  = {ypl:.0f}   "
                      f"(band {ypl_lo:.0f}..{ypl_hi:.0f})")
            y1 = mu / (rho * utau)
            print(f"      y for y+=1  : {y1*1e6:.3f} um  ({y1*1e3:.5f} mm)")
            print(f"      y for y+=30 : {30*y1*1e3:.4f} mm   "
                  f"y for y+=300 : {300*y1*1e3:.4f} mm")
            row["chords"][label] = {
                "chord": c, "re": re,
                "cf_prandtl_schlichting": cf_ps, "cf_white": cf_wh,
                "cf_027": cf_pl, "cf_026": cf_pl2,
                "cf": cf, "cf_lo": cf_lo, "cf_hi": cf_hi,
                "utau": utau, "utau_lo": utau_lo, "utau_hi": utau_hi,
                "yplus": (rho * utau * args.y / mu) if args.y else None,
                "yplus_lo": (rho * utau_lo * args.y / mu) if args.y else None,
                "yplus_hi": (rho * utau_hi * args.y / mu) if args.y else None,
                "y_for_yplus1_um": y1 * 1e6,
                "y_for_yplus30_mm": 30 * y1 * 1e3,
                "y_for_yplus300_mm": 300 * y1 * 1e3,
            }
        out["anchors"].append(row)
        print()

    if args.json:
        args.json.write_text(json.dumps(out, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())