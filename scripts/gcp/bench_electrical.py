#!/usr/bin/env python3
"""Generic electrical/machine/drive/battery energy-closure benchmark (SOLVER-CORR 03).

Uses the repo's generic participants only (OpenMDAO coordinator + ROSS/PyBaMM
backed scalars where declared) and checks explicit energy residuals:
  electrical power == mechanical power + losses, and the machine/drive heat
  loads reach the thermal network.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RECEIPTS = Path(os.environ.get("RECEIPTS", "/var/log/proofs/receipts"))
RECEIPTS.mkdir(parents=True, exist_ok=True)


def main() -> int:
    out: dict = {
        "benchmark": "electrical-machine-drive-battery-energy-closure",
        "status": "BLOCKED",
    }
    try:
        from aeroworkbench_convergence import assess_closure
        from aeroworkbench_electrical import solve_electrical_thermal
    except Exception as exc:  # noqa: BLE001
        out["reason"] = f"import failed: {type(exc).__name__}:{exc}"
        (RECEIPTS / "issue39_electrical.json").write_text(json.dumps(out, indent=2, sort_keys=True))
        print("WROTE issue39_electrical.json status=BLOCKED")
        return 0
    try:
        cases = []
        for speed, torque in ((20000.0, 0.0), (20000.0, 0.01), (12000.0, 0.0)):
            try:
                result = solve_electrical_thermal(speed_rpm=speed, load_torque_n_m=torque)
            except Exception as exc:  # noqa: BLE001 - envelope fail-closed is data
                cases.append(
                    {
                        "speedRpm": speed,
                        "loadTorqueNm": torque,
                        "status": "BLOCKED",
                        "reason": f"{type(exc).__name__}:{exc}",
                    }
                )
                continue
            values = dict(result.values)
            electrical = values.get("rotating-electrical-machine.electrical_power_w")
            mechanical = values.get("rotating-electrical-machine.mechanical_power_w")
            machine_loss = values.get("rotating-electrical-machine.total_loss_w")
            thermal_machine = values.get("thermal-scalar-lumped.machine_loss_w")
            drive_loss = values.get("power-electronics-drive.total_loss_w")
            thermal_drive = values.get("thermal-scalar-lumped.drive_loss_w")
            pack_v = values.get("battery-scalar-pack.pack_voltage_v")
            dc_i = values.get("power-electronics-drive.dc_current_a")
            delivered = pack_v * dc_i if None not in (pack_v, dc_i) else None
            consumed = (
                mechanical + machine_loss + drive_loss
                if None not in (mechanical, machine_loss, drive_loss)
                else None
            )
            power = None
            heat = None
            if None not in (electrical, mechanical, machine_loss):
                power = assess_closure(
                    "energy", {"energy": mechanical + machine_loss}, {"energy": electrical}
                )
            if None not in (machine_loss, thermal_machine, drive_loss, thermal_drive):
                heat = assess_closure(
                    "heat-balance",
                    {"heat-flow": thermal_machine + thermal_drive},
                    {"heat-flow": machine_loss + drive_loss},
                    required=("heat-flow",),
                )
            cases.append(
                {
                    "speedRpm": speed,
                    "loadTorqueNm": torque,
                    "engine": result.engine,
                    "converged": result.converged,
                    "iterations": result.iterations,
                    "residualNorm": result.residual_norm,
                    "closureResidual": result.closure_residual,
                    "electricalPowerW": electrical,
                    "mechanicalPowerW": mechanical,
                    "machineLossW": machine_loss,
                    "driveLossW": drive_loss,
                    "deliveredPowerW": delivered,
                    "consumedPowerW": consumed,
                    "couplingClosureResidualW": (
                        None if None in (delivered, consumed) else delivered - consumed
                    ),
                    "thermalMachineLossW": thermal_machine,
                    "thermalDriveLossW": thermal_drive,
                    "powerBalancePassed": None if power is None else power.passed,
                    "powerBalanceReason": None if power is None else power.reason,
                    "powerBalanceChecks": None if power is None else power.as_dict()["checks"],
                    "heatBalancePassed": None if heat is None else heat.passed,
                    "heatBalanceReason": None if heat is None else heat.reason,
                }
            )
        out["cases"] = cases
        executed = [c for c in cases if "converged" in c]
        out["status"] = (
            "EXECUTED" if executed and all(c["converged"] for c in executed) else "PARTIAL"
        )
    except Exception as exc:  # noqa: BLE001
        out["reason"] = f"{type(exc).__name__}:{exc}"
        out["status"] = "FAILED"
    (RECEIPTS / "issue39_electrical.json").write_text(json.dumps(out, indent=2, sort_keys=True))
    print("WROTE issue39_electrical.json status=", out["status"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
