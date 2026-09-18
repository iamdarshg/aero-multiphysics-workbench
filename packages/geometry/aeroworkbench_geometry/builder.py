"""OpenCascade execution backend for parametric models."""

from __future__ import annotations

import hashlib
from typing import Any

from .parameters import parameter_digest
from .parametric import (
    BuiltModel,
    ComponentTopology,
    ParametricModel,
    geometry_definition_digest,
    probe_kernel,
)

_FACE_PRECISION = 4


def _face_fingerprint(face: Any) -> str:
    geom_type = type(face.geomObject()).__name__ if hasattr(face, "geomObject") else "Face"
    try:
        area = round(float(face.Area()), _FACE_PRECISION)
    except Exception:
        area = 0.0
    try:
        center = face.Center()
        point = (
            round(float(center.x), _FACE_PRECISION),
            round(float(center.y), _FACE_PRECISION),
            round(float(center.z), _FACE_PRECISION),
        )
    except Exception:
        point = (0.0, 0.0, 0.0)
    return f"{geom_type}|A={area}|C={point[0]},{point[1]},{point[2]}"


def _as_count(value: Any, detail: str) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"PATTERN_COUNT_INVALID:{detail}") from exc
    if count != float(value) or count < 2:
        raise ValueError(f"PATTERN_COUNT_MUST_BE_AT_LEAST_TWO:{detail}")
    return count


def _oriented(workplane: Any, axis: str) -> Any:
    axis = axis.upper()
    if axis == "X":
        return workplane.rotate((0, 0, 0), (0, 1, 0), 90)
    if axis == "Y":
        return workplane.rotate((0, 0, 0), (1, 0, 0), -90)
    if axis == "Z":
        return workplane
    raise ValueError(f"UNKNOWN_AXIS:{axis}")


def _execute_operation(
    cq: Any, operation: dict[str, Any], shapes: dict[str, Any]
) -> None:
    op = operation["op"]
    if op == "box":
        dx, dy, dz = operation["dx"], operation["dy"], operation["dz"]
        if not (dx > 0 and dy > 0 and dz > 0):
            raise ValueError("BOX_DIMENSIONS_MUST_BE_POSITIVE")
        cx, cy, cz = operation["center"]
        solid = (
            cq.Workplane("XY")
            .box(dx, dy, dz)
            .translate((cx, cy, cz))
            .val()
        )
        shapes[operation["name"]] = solid
    elif op == "cylinder":
        diameter, height = operation["diameter"], operation["height"]
        if not (diameter > 0 and height > 0):
            raise ValueError("CYLINDER_DIMENSIONS_MUST_BE_POSITIVE")
        axis = operation.get("axis", "Z").upper()
        cx, cy, cz = operation["center"]
        base = (
            _oriented(cq.Workplane("XY"), axis)
            .circle(diameter / 2.0)
            .extrude(height / 2.0, both=True)
            .val()
        )
        solid = base.translate((cx, cy, cz))
        shapes[operation["name"]] = solid
    elif op == "sphere":
        diameter = operation["diameter"]
        if diameter <= 0:
            raise ValueError("SPHERE_DIAMETER_MUST_BE_POSITIVE")
        cx, cy, cz = operation["center"]
        shapes[operation["name"]] = (
            cq.Workplane("XY").sphere(diameter / 2.0).translate((cx, cy, cz)).val()
        )
    elif op == "cone":
        base, top, height = (
            operation["diameterBase"],
            operation["diameterTop"],
            operation["height"],
        )
        if not (base > 0 and top >= 0 and height > 0):
            raise ValueError("CONE_DIMENSIONS_MUST_BE_POSITIVE")
        cx, cy, cz = operation["center"]
        shapes[operation["name"]] = (
            _oriented(cq.Workplane("XY"), operation.get("axis", "Z"))
            .circle(base / 2.0)
            .workplane(offset=height)
            .circle(top / 2.0)
            .loft(ruled=True)
            .translate((cx, cy, cz - height / 2.0))
            .val()
        )
    elif op == "extrude":
        depth = operation["depth"]
        if depth <= 0:
            raise ValueError("EXTRUDE_DEPTH_MUST_BE_POSITIVE")
        profile = operation["profile"]
        ox, oy, oz = operation.get("offset", (0.0, 0.0, 0.0))
        workplane = cq.Workplane(operation.get("plane", "XY")).polyline(profile).close()
        shapes[operation["name"]] = (
            workplane.extrude(depth).translate((ox, oy, oz)).val()
        )
    elif op == "revolve":
        profile = operation["profile"]
        angle = operation["angleDeg"]
        base = cq.Workplane("XZ").polyline(profile).close()
        shapes[operation["name"]] = base.revolve(angle, (0, 0, 0), (0, 1, 0)).val()
    elif op == "loft":
        profiles = operation["profiles"]
        offsets = operation.get("offsets")
        if offsets is not None and len(offsets) != len(profiles):
            raise ValueError("LOFT_OFFSETS_MUST_MATCH_PROFILES")
        stations = list(offsets) if offsets else [float(i) for i in range(len(profiles))]
        loft_wp = cq.Workplane("XY", origin=(0, 0, stations[0])).polyline(
            profiles[0]
        ).close()
        previous = stations[0]
        for profile, station in zip(profiles[1:], stations[1:], strict=True):
            loft_wp = (
                loft_wp.workplane(offset=station - previous).polyline(profile).close()
            )
            previous = station
        shapes[operation["name"]] = loft_wp.loft(
            ruled=operation.get("ruled", True)
        ).val()
    elif op == "sweep":
        profile = operation["profile"]
        path = operation["path"]
        path_wire = cq.Workplane("XY").spline(path)
        shapes[operation["name"]] = (
            cq.Workplane("XY").polyline(profile).close().sweep(path_wire).val()
        )
    elif op == "fillet":
        target = shapes.get(operation["name"])
        if target is None:
            raise ValueError(f"FILLET_TARGET_MISSING:{operation['name']}")
        try:
            shapes[operation["name"]] = (
                cq.Workplane(obj=target).edges().fillet(operation["radius"]).val()
            )
        except Exception as exc:
            raise ValueError(f"FILLET_FAILED:{operation['name']}:{exc}") from exc
    elif op == "chamfer":
        target = shapes.get(operation["name"])
        if target is None:
            raise ValueError(f"CHAMFER_TARGET_MISSING:{operation['name']}")
        try:
            shapes[operation["name"]] = (
                cq.Workplane(obj=target).edges().chamfer(operation["length"]).val()
            )
        except Exception as exc:
            raise ValueError(f"CHAMFER_FAILED:{operation['name']}:{exc}") from exc
    elif op == "boolean":
        left = shapes.get(operation["left"])
        right = shapes.get(operation["right"])
        if left is None or right is None:
            raise ValueError(
                f"BOOLEAN_INPUT_MISSING:{operation['left']}+{operation['right']}"
            )
        left_wp, right_wp = cq.Workplane(obj=left), cq.Workplane(obj=right)
        kind = operation["boolean"]
        if kind == "union":
            result = left_wp.union(right_wp).val()
        elif kind == "cut":
            result = left_wp.cut(right_wp).val()
        elif kind == "intersection":
            result = left_wp.intersect(right_wp).val()
        else:  # pragma: no cover - validated at record time
            raise ValueError(f"UNKNOWN_BOOLEAN_OPERATION:{kind}")
        shapes[operation["name"]] = result
    elif op == "circular-pattern":
        source = shapes.get(operation["source"])
        if source is None:
            raise ValueError(f"PATTERN_SOURCE_MISSING:{operation['source']}")
        count = _as_count(operation["count"], str(operation["name"]))
        axis = operation.get("axis", "Z").upper()
        axis_vector = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}[axis]
        copies = [source]
        for index in range(1, count):
            copies.append(
                source.rotate(
                    tuple(operation.get("center", (0, 0, 0))),
                    axis_vector,
                    360.0 * index / count,
                )
            )
        shapes[operation["name"]] = cq.Compound.makeCompound(copies)
    elif op == "linear-pattern":
        source = shapes.get(operation["source"])
        if source is None:
            raise ValueError(f"PATTERN_SOURCE_MISSING:{operation['source']}")
        count = _as_count(operation["count"], str(operation["name"]))
        direction = tuple(operation["direction"])
        spacing = operation["spacing"]
        copies = [source]
        for index in range(1, count):
            vector = tuple(d * spacing * index for d in direction)
            copies.append(source.translate(vector))
        shapes[operation["name"]] = cq.Compound.makeCompound(copies)
    else:  # pragma: no cover - operations are allowlisted at record time
        raise ValueError(f"UNKNOWN_GEOMETRY_OPERATION:{op}")


def execute(model: ParametricModel) -> BuiltModel:
    """Run a parametric model's operation log against OpenCascade."""

    kernel = probe_kernel()
    if not kernel.available:
        raise RuntimeError("CAD_KERNEL_UNAVAILABLE")
    import cadquery as cq  # noqa: PLC0415

    # Deterministic resolution before kernel execution: bound parameter
    # references become concrete millimetre values here.
    operations = model.resolved_operations()
    shapes: dict[str, Any] = {}
    for operation in operations:
        _execute_operation(cq, operation, shapes)
    components: list[ComponentTopology] = []
    fingerprint_source: list[str] = []
    export_shapes: dict[str, Any] = {}
    for name in sorted(shapes):
        if name.startswith("_"):
            continue  # construction blank: input to booleans, not a component
        export_shapes[name] = shapes[name]
        shape = shapes[name]
        faces = list(shape.Faces())
        fingerprints = tuple(sorted(_face_fingerprint(face) for face in faces))
        try:
            volume = float(shape.Volume())
        except Exception:
            volume = 0.0
        try:
            center = shape.Center()
            centroid = (
                round(float(center.x), 4),
                round(float(center.y), 4),
                round(float(center.z), 4),
            )
        except Exception:
            centroid = (0.0, 0.0, 0.0)
        components.append(
            ComponentTopology(
                name=name,
                face_fingerprints=fingerprints,
                volume_mm3=volume,
                center_mm=centroid,
            )
        )
        fingerprint_source.append(f"{name}:{volume:.6f}:{len(fingerprints)}")
        fingerprint_source.extend(fingerprints)
    param_hash = parameter_digest(model.parameters)
    shape_hash = hashlib.sha256(
        "\n".join(fingerprint_source).encode("utf-8")
    ).hexdigest()
    built = BuiltModel(
        model_name=model.name,
        parameter_hash=param_hash,
        shape_hash=shape_hash,
        kernel=kernel,
        components=tuple(components),
        operation_count=len(operations),
        definition_hash=geometry_definition_digest(model),
    )
    # Stash live shapes on the side for exporters without polluting the hash.
    built_live_shapes[id(built)] = shapes
    return built


built_live_shapes: dict[int, dict[str, Any]] = {}


def live_shapes(built: BuiltModel) -> dict[str, Any]:
    """Return the live OpenCascade shapes for an executed model."""

    try:
        return built_live_shapes[id(built)]
    except KeyError as exc:
        raise RuntimeError("LIVE_SHAPES_EXPIRED:rebuild the model") from exc
