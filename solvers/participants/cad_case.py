"""CAD interchange participant: milestone-1 conversion through the governed runner.

Prepare validates the generic request and stages case.json. Execution builds
a small generic duct, exports STEP, and converts through FreeCAD when present
else the OCC fallback, recording face counts before and after. Parse and
validity enforce topology preservation (fail closed on silent change).
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


def _canonical_inputs(data: Mapping[str, object]) -> dict[str, Any]:
    n_rotating = data.get("n_rotating", 1)
    if isinstance(n_rotating, bool) or not isinstance(n_rotating, int):
        raise _fail("input n_rotating must be an integer")
    source_format = data.get("source_format", "step")
    if source_format not in {"step", "brep"}:
        raise _fail("input source_format must be step or brep")
    if n_rotating < 1 or n_rotating > 4:
        raise _fail("n_rotating must be within 1..4")
    dims: dict[str, Any] = {"n_rotating": int(n_rotating), "source_format": str(source_format)}
    for name in (
        "length_mm",
        "inner_diameter_mm",
        "outer_diameter_mm",
        "zone_length_mm",
        "zone_gap_mm",
    ):
        value = data.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _fail(f"input {name} must be a number")
        dims[name] = float(value)
    if not 0 < dims["inner_diameter_mm"] < dims["outer_diameter_mm"]:
        raise _fail("diameters must satisfy 0 < inner < outer")
    if dims["length_mm"] <= 0 or dims["zone_length_mm"] <= 0 or dims["zone_gap_mm"] < 0:
        raise _fail("duct dimensions out of range")
    return dims


def prepare_cad_case(inputs: dict[str, object], case_dir: Path) -> PrepareReceipt:
    canonical = _canonical_inputs(dict(inputs))
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(
        json.dumps(canonical, indent=2, sort_keys=True), encoding="utf-8"
    )
    return PrepareReceipt(
        participant_id="cad-interchange",
        case_id=case_dir.name,
        input_hash=digest,
        files=("case.json",),
        detail=f"source={canonical['source_format']}",
    )


def execute_cad_case(inputs: dict[str, object], case_dir: Path) -> None:
    """Run the milestone-1 interchange pipeline inside the governed job."""

    from aeroworkbench_geometry import build_duct_system
    from aeroworkbench_geometry.builder import live_shapes
    from aeroworkbench_geometry.parametric import export_artifacts
    from freecad.adapter import convert_cad, inspect_freecad  # noqa: PLC0415

    def _count_faces(path: Path) -> int | None:
        try:
            from cadquery import importers  # noqa: PLC0415

            suffix = path.suffix.lower()
            if suffix in (".step", ".stp"):
                imported = importers.importStep(str(path))
            elif suffix in (".brep", ".brp"):
                imported = importers.importBrep(str(path))
            else:
                return None
            shape = imported.val() if hasattr(imported, "val") else imported
            return len(shape.Faces())
        except Exception:  # noqa: BLE001
            return None

    canonical = _canonical_inputs(dict(inputs))
    n_rotating = int(canonical["n_rotating"])
    dims = {
        "outer_diameter_mm": float(canonical["outer_diameter_mm"]),
        "inner_diameter_mm": float(canonical["inner_diameter_mm"]),
        "length_mm": float(canonical["length_mm"]),
        "hub_diameter_mm": float(canonical["inner_diameter_mm"]) * 0.3,
        "zone_length_mm": float(canonical["zone_length_mm"]),
        "zone_gap_mm": float(canonical["zone_gap_mm"]),
    }
    built = build_duct_system(n_rotating=n_rotating, n_solids=1, **dims).build()
    records = export_artifacts(
        live_shapes(built), built.kernel, case_dir / "cad", basename="domain", export_stl=False
    )
    by_format: dict[str, Path] = {}
    for artifact in records["artifacts"]:
        if artifact["component"] == "duct":
            by_format[str(artifact["format"])] = Path(str(artifact["path"]))
    source_format = str(canonical["source_format"])
    source = by_format.get(source_format)
    if source is None:
        raise ParticipantError(
            NativeErrorCode.PREPARATION_FAILED, f"no {source_format} artifact exported"
        )
    target_suffix = ".brep" if source_format == "step" else ".step"
    intermediate = case_dir / f"intermediate{target_suffix}"
    forward = convert_cad(source, intermediate)
    if forward.state != "completed" or forward.product_sha256 is None:
        raise ParticipantError(
            NativeErrorCode.PROCESS_EXIT_NONZERO, f"forward conversion failed:{forward.code}"
        )
    product = case_dir / "product.step"
    back = convert_cad(intermediate, product)
    if back.state != "completed" or back.product_sha256 is None:
        raise ParticipantError(
            NativeErrorCode.PROCESS_EXIT_NONZERO, f"back conversion failed:{back.code}"
        )
    faces_before = _count_faces(source)
    faces_after = _count_faces(product)
    if faces_before is None or faces_before <= 0 or faces_after is None or faces_after <= 0:
        raise ParticipantError(NativeErrorCode.MESH_INVALID, "face count unavailable")
    (case_dir / "result.json").write_text(
        json.dumps(
            {
                "faces_before": faces_before,
                "faces_after": faces_after,
                "converter": forward.converter,
                "freecad_state": inspect_freecad().state,
                "product_sha256": back.product_sha256,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def parse_cad_result(case_dir: Path) -> ParseReceipt:
    target = case_dir / "result.json"
    if not target.is_file():
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "result.json is missing")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"result.json unreadable:{exc}"
        ) from exc
    product = case_dir / "product.step"
    if not product.is_file():
        product = case_dir / "product.brep"
    if not product.is_file():
        raise ParticipantError(NativeErrorCode.PARSER_FAILED, "converted product is missing")
    try:
        before = int(data["faces_before"])
        after = int(data["faces_after"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ParticipantError(
            NativeErrorCode.PARSER_FAILED, f"cad result fields invalid:{exc}"
        ) from exc
    return ParseReceipt(
        participant_id="cad-interchange",
        parser="participants.cad_case:parse_cad_result",
        scalars={"faces_before": float(before), "faces_after": float(after)},
        units={"faces_before": "dimensionless", "faces_after": "dimensionless"},
        detail=f"converter={data.get('converter', 'unknown')}",
    )


def validate_cad_result(
    scalars: Mapping[str, float], inputs: Mapping[str, object]
) -> ValidityReport:
    _ = inputs
    before = float(scalars.get("faces_before", 0.0))
    after = float(scalars.get("faces_after", -1.0))
    checks = {
        "faces_positive": before > 0,
        "topology_preserved": before == after,
    }
    return ValidityReport(
        participant_id="cad-interchange",
        passed=all(checks.values()),
        checks=checks,
        detail="face counts survive the interchange roundtrip",
    )
