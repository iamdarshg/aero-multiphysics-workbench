"""Run one real OpenVSP/VSPAERO case and emit its governed result envelope."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "packages" / "airframe"))
sys.path.insert(0, str(REPO / "packages" / "core"))
sys.path.insert(0, str(REPO / "packages" / "geometry"))
sys.path.insert(0, str(REPO / "packages" / "semantics"))
sys.path.insert(0, str(REPO / "solvers"))

from aeroworkbench_airframe.external_aero import (  # noqa: E402
    case_from_payload,
    reference_from_conditions,
    solve_vspaero,
)


def main() -> int:
    fixture = REPO / "tests" / "airframe" / "external_aero" / "rectangular_wing.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    case = case_from_payload(payload)
    conditions = payload["reference"]
    reference = reference_from_conditions(
        case.geometry_reference(),
        density_kg_m3=float(conditions["densityKgM3"]),
        velocity_m_s=float(conditions["velocityMS"]),
        speed_of_sound_m_s=float(conditions["speedOfSoundMS"]),
        viscosity_pa_s=float(conditions["viscosityPaS"]),
        altitude_m=conditions.get("altitudeM"),
        atmosphere_model=conditions.get("atmosphereModel", "declared"),
    )
    result = solve_vspaero(case, reference, run_id="gcp-openvsp-native")
    print(json.dumps(result.canonical(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
