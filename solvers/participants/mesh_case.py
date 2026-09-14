"""Gmsh mesh participant: milestone-1 native meshing through the governed runner.

Prepare validates generic duct-mesh inputs and stages case.json. Execution
runs the milestone-1 native mesh pipeline in-process (Gmsh python API) and
records result.json. Parse re-verifies the mesh artifact from disk; validity
enforces quality gates (no inverted elements, bounded SICN).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from participants.errors import NativeErrorCode, ParticipantError
from participants.receipts import ParseReceipt, PrepareReceipt, ValidityReport


def _fail(detail: str) -> ParticipantError:
    return ParticipantError(NativeErrorCode.PREPARATION_FAILED, detail)


def _require_float(inputs: Mapping[str, object], name: str) -> float:
    value = inputs.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(f"input {name} must be a number")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise _fail(f"input {name} must be finite")
    return result


def _require_int(inputs: Mapping[str, object], name: str) -> int:
    value = inputs.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(f"input {name} must be an integer")
    return int(value)


def _canonical_inputs(data: Mapping[str, object]) -> dict[str, Any]:
    n_rotating = _require_int(data, "n_rotating")
    base_size = _require_float(data, "base_size_mm")
    length = _require_float(data, "length_mm")
    inner = _require_float(data, "inner_diameter_mm")
    outer = _require_float(data, "outer_diameter_mm")
    zone_length = _require_float(data, "zone_length_mm")
    zone_gap = _require_float(data, "zone_gap_mm")
    if n_rotating < 1 or n_rotating > 8:
        raise _fail("n_rotating must be within 1..8")
    if base_size <= 0 or length <= 0 or zone_length <= 0 or zone_gap < 0:
        raise _fail("mesh dimensions out of range")
    if not 0 < inner < outer:
        raise _fail("diameters must satisfy 0 < inner < outer")
    return {
        "n_rotating": n_rotating,
        "base_size_mm": base_size,
        "length_mm": length,
        "inner_diameter_mm": inner,
        "outer_diameter_mm": outer,
        "zone_length_mm": zone_length,
        "zone_gap_mm": zone_gap,
    }


def prepare_mesh_case(inputs: dict[str, object], case_dir: Path) -> PrepareReceipt:
    canonical = _canonical_inputs(dict(inputs))
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(
        json.dumps(canonical, indent=2, sort_keys=True), encoding="utf-8"
    )
    return PrepareReceipt(
        participant_id="domain-mesh",
        case_id=case_dir.name,
        input_hash=digest,
        files=("case.json",),
        detail=f"n_rotating={canonical['n_rotating']}",
    )


def execute_mesh_case(inputs: dict[str, object], case_dir: Path) -> None:
    """Run the milestone-1 native mesh pipeline inside the governed job."""

    from aeroworkbench_geometry import build_duct_system, rotating_zone_names
    from aeroworkbench_geometry.builder import live_shapes
    from aeroworkbench_geometry.parametric import export_artifacts
    from aeroworkbench_mesh import build_native_mesh, duct_mesh_spec, probe_gmsh

    canonical = _canonical_inputs(dict(inputs))
    capability = probe_gmsh()
    if not capability.available:
        raise ParticipantError(
            NativeErrorCode.CAPABILITY_UNAVAILABLE, f"gmsh unavailable:{capability.detail}"
        )
    n_rotating = int(canonical["n_rotating"])
    built = build_duct_system(
        n_rotating=n_rotating,
        n_solids=1,
        outer_diameter_mm=float(canonical["outer_diameter_mm"]),
        inner_diameter_mm=float(canonical["inner_diameter_mm"]),
        length_mm=float(canonical["length_mm"]),
        hub_diameter_mm=float(canonical["inner_diameter_mm"]) * 0.3,
        zone_length_mm=float(canonical["zone_length_mm"]),
        zone_gap_mm=float(canonical["zone_gap_mm"]),
    ).build()
    records = export_artifacts(
        live_shapes(built), built.kernel, case_dir / "cad", basename="domain", export_stl=False
    )
    files = {
        artifact["component"]: Path(artifact["path"])
        for artifact in records["artifacts"]
        if artifact["format"] == "step" and artifact["component"] != "assembly"
    }
    rotating = rotating_zone_names(n_rotating)
    stationary = ("fluid_inlet", "fluid_outlet") + tuple(
        f"stator_zone_{i}" for i in range(n_rotating - 1)
    )
    spec = duct_mesh_spec(
        name="domain",
        rotating=rotating,
        stationary_fluid=stationary,
        solids=(),
        length_mm=float(canonical["length_mm"]),
        inner_diameter_mm=float(canonical["inner_diameter_mm"]),
        base_size_mm=float(canonical["base_size_mm"]),
    )
    receipt = build_native_mesh(spec, files, built.shape_hash, case_dir / "mesh")
    if receipt.state != "completed" or receipt.mesh_path is None:
        raise ParticipantError(NativeErrorCode.MESH_INVALID, receipt.detail)
    quality = receipt.quality
    (case_dir / "result.json").write_text(
        json.dumps(
            {
                "mesh_path": receipt.mesh_path,
                "mesh_hash": receipt.mesh_hash,
                "geometry_hash": receipt.geometry_hash,
                "element_count": quality.element_count if quality else 0,
                "min_sicn": quality.min_sicn if quality else None,
                "inverted_count": quality.inverted_count if quality else None,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    mesh_target = case_dir / "domain.msh"
    if Path(receipt.mesh_path) != mesh_target:
        mesh_target.write_bytes(Path(receipt.mesh_path).read_bytes())


def parse_mesh_result(case_dir: Path) -> ParseReceipt:
    target = case_dir / "result.json"
    if not target.is_file():
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "result.json is missing")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"result.json unreadable:{exc}"
        ) from exc
    mesh_path = case_dir / "domain.msh"
    if not mesh_path.is_file():
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "domain.msh is missing")
    try:
        elements = int(data["element_count"])
        min_sicn = float(data["min_sicn"])
        inverted = int(data["inverted_count"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"mesh result fields invalid:{exc}"
        ) from exc
    return ParseReceipt(
        participant_id="domain-mesh",
        parser="participants.mesh_case:parse_mesh_result",
        scalars={"element_count": float(elements), "min_sicn": min_sicn},
        units={"element_count": "dimensionless", "min_sicn": "dimensionless"},
        detail=f"inverted={inverted}",
    )


def validate_mesh_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    _ = inputs
    elements = float(scalars.get("element_count", 0.0))
    min_sicn = float(scalars.get("min_sicn", float("nan")))
    checks = {
        "has_elements": elements > 0,
        "quality_bounded": min_sicn == min_sicn and min_sicn > 0.05,
    }
    return ValidityReport(
        participant_id="domain-mesh",
        passed=all(checks.values()),
        checks=checks,
        detail="positive element count and SICN above 0.05",
    )
