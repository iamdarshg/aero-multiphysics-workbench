"""DA-G2 note: quasi-static impedance estimate for Rev B RF traces.

Stackup read from main_rev_b.kicad_pcb:
  F.Cu 35 um -> prepreg FR4 200 um (Er 4.2) -> In1.Cu

Microstrip, top layer referenced to In1. Two independent closed-form
estimates are reported (IPC-2141 and Hammerstad-Jensen) so the number is
bracketed rather than pinned to one formula.

BOUNDARY: this is a hand-calculated quasi-static estimate from geometry. It is
NOT a field solve, NOT an S-parameter result and NOT a fab sign-off. The board
has no impedance targets recorded, so this reports distance from 50 ohm, not
a pass/fail against a fab control spec.
"""
from __future__ import annotations

import math

W_M = 0.35e-3          # measured RF trace width on F.Cu
H_M = 0.200e-3         # prepreg F.Cu -> In1.Cu
T_M = 0.035e-3         # 1 oz copper
ER = 4.2               # FR4, from the board stackup block

H_MM, W_MM, T_MM = H_M * 1e3, W_M * 1e3, T_M * 1e3


def ipc2141(w_mm: float, h_mm: float, t_mm: float, er: float) -> float:
    """IPC-2141 microstrip impedance (ohms)."""
    return (87.0 / math.sqrt(er + 1.41)) * math.log(5.98 * h_mm / (0.8 * w_mm + t_mm))


def hammerstad(w_mm: float, h_mm: float, t_mm: float, er: float) -> float:
    """Hammerstad-Jensen microstrip impedance with finite thickness (ohms)."""
    # Effective width correction for thickness.
    dw = (t_mm / math.pi) * math.log(1.0 + 4.0 * math.e / ((t_mm / h_mm) ** 2 + (1.0 / math.pi) / (w_mm / h_mm + 1.1) ** 2))
    we = w_mm + dw
    u = we / h_mm
    e_eff = (er + 1) / 2 + ((er - 1) / 2) * (1 + 12 / u) ** -0.5
    if u <= 1:
        z01 = 60.0 / math.sqrt(e_eff) * math.log(8 / u + u / 4)
    else:
        z01 = 120.0 * math.pi / (math.sqrt(e_eff) * (u + 1.39 + 0.667 * math.log(u + 1.444)))
    # Z0 at free space scaled by sqrt(1/er_eff) blend.
    return z01


def width_for_50(h_mm: float, t_mm: float, er: float) -> float:
    """Bisection for the trace width giving 50 ohm under Hammerstad."""
    lo, hi = 0.05, 5.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if hammerstad(mid, h_mm, t_mm, er) > 50.0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


results = {
    "stackup": {
        "trace_width_mm": W_MM,
        "dielectric_height_mm": H_MM,
        "copper_thickness_mm": T_MM,
        "epsilon_r": ER,
        "reference_plane": "In1.Cu",
    },
    "impedance_ohm": {
        "ipc2141": round(ipc2141(W_MM, H_MM, T_MM, ER), 2),
        "hammerstad_jensen": round(hammerstad(W_MM, H_MM, T_MM, ER), 2),
    },
    "width_for_50_ohm_mm": round(width_for_50(H_MM, T_MM, ER), 4),
    "claim_boundary": (
        "Quasi-static hand calculation from measured geometry and the board's own "
        "stackup. Not a field solve, not an S-parameter result, not fab sign-off."
    ),
}

for key, value in results["impedance_ohm"].items():
    print(f"{key:22s} Z0 = {value:6.2f} ohm   (target 50)")
print(f"{'width for 50 ohm':22s}      = {results['width_for_50_ohm_mm']:.4f} mm   (board uses {W_MM} mm)")
spread = max(results["impedance_ohm"].values()) - min(results["impedance_ohm"].values())
print(f"estimate spread        = {spread:.2f} ohm")