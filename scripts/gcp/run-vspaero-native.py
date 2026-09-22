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
sys.path.insert(0, str(REPO / "packages" / "fluid_properties"))
sys.path.insert(0, str(REPO / "solvers"))

from aeroworkbench_airframe.external_aero import (  # noqa: E402
    reference_from_conditions,
    solve_vspaero,
)
from aeroworkbench_airframe.aero_geometry import AirfoilProfile, LiftingSurface, Planform  # noqa: E402
from aeroworkbench_airframe.external_aero import ExternalAeroCase  # noqa: E402


def case_from_payload(payload: dict[str, object]) -> ExternalAeroCase:
    surfaces = []
    for item in payload["surfaces"]:  # type: ignore[index]
        item = dict(item)  # type: ignore[arg-type]
        plan = dict(item["planform"])  # type: ignore[index]
        profile = dict(item["profile"])  # type: ignore[index]
        surfaces.append(
            LiftingSurface.from_planform(
                str(item["surfaceId"]),
                str(item["role"]),
                Planform(
                    span_mm=float(plan["spanMm"]),
                    root_chord_mm=float(plan["rootChordMm"]),
                    tip_chord_mm=float(plan["tipChordMm"]),
                    sweep_deg=float(plan.get("sweepDeg", 0.0)),
                    dihedral_deg=float(plan.get("dihedralDeg", 0.0)),
                    twist_root_deg=float(plan.get("twistRootDeg", 0.0)),
                    twist_tip_deg=float(plan.get("twistTipDeg", 0.0)),
                ),
                AirfoilProfile(
                    family=str(profile.get("family", "parametric")),
                    thickness_ratio=float(profile.get("thicknessRatio", 0.12)),
                    camber_ratio=float(profile.get("camberRatio", 0.0)),
                    camber_position=float(profile.get("camberPosition", 0.4)),
                ),
                frame=str(item.get("frame", "surface-local")),
                n_stations=int(item.get("nStations", 3)),
            )
        )
    return ExternalAeroCase(
        case_id=str(payload["caseId"]),
        surfaces=tuple(surfaces),
        symmetry=str(payload.get("symmetry", "mirror")),
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
