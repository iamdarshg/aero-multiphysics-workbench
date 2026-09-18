"""Real parametric CAD layer backed by CadQuery/OpenCascade.

Every operation constructs actual OpenCascade topology. When CadQuery is not
importable the kernel probe reports ``unavailable`` and construction fails
closed instead of returning placeholder shapes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from typing import Any, Literal

from .parameters import ParameterSet

Axis = Literal["X", "Y", "Z"]


@dataclass(frozen=True, slots=True)
class ParameterRef:
    """Typed reference to a named parameter, resolved at evaluation time.

    The unit is carried so a bound dimension is checked against the
    parameter's declared unit before any kernel execution.
    """

    name: str
    unit: str = "mm"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("PARAMETER_REF_NAME_REQUIRED")
        if not self.unit.strip():
            raise ValueError("PARAMETER_REF_UNIT_REQUIRED")


def param(name: str, unit: str = "mm") -> ParameterRef:
    """Bind an operation argument to a named parameter path."""

    return ParameterRef(name, unit)


BindArg = float | int | ParameterRef
BindValue = BindArg | tuple[Any, ...] | list[Any]


@dataclass(frozen=True, slots=True)
class KernelIdentity:
    available: bool
    cadquery_version: str | None
    ocp_version: str | None
    detail: str


def probe_kernel() -> KernelIdentity:
    """Report the real CAD kernel identity without constructing geometry."""

    try:
        import cadquery as cq  # noqa: PLC0415
    except ImportError as exc:
        return KernelIdentity(False, None, None, f"cadquery is not installed: {exc}")
    try:
        import OCP  # noqa: PLC0415
        ocp_version: str | None = getattr(OCP, "__version__", "unknown")
    except ImportError:
        ocp_version = None
    return KernelIdentity(True, cq.__version__, ocp_version, "cadquery/OCP available")


def require_kernel() -> Any:
    try:
        import cadquery as cq  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError("CAD_KERNEL_UNAVAILABLE:cadquery is not installed") from exc
    return cq


@dataclass(frozen=True, slots=True)
class Frame:
    """Reference axis/plane: origin point plus direction vector (mm)."""

    name: str
    origin_mm: tuple[float, float, float]
    direction: tuple[float, float, float]


@dataclass
class ParametricModel:
    """Ordered generic CAD operations over named components.

    Operations record their intent and parameters; :meth:`build` executes them
    against OpenCascade in order, so the parameter dependency graph plus the
    operation log fully determine the output topology.
    """

    name: str
    parameters: ParameterSet
    operations: list[dict[str, Any]] = field(default_factory=list)
    frames: dict[str, Frame] = field(default_factory=dict)

    # -- construction helpers -------------------------------------------------
    def _record(self, operation: dict[str, Any]) -> ParametricModel:
        self.operations.append(operation)
        return self

    def add_box(
        self,
        name: str,
        dx_mm: BindArg,
        dy_mm: BindArg,
        dz_mm: BindArg,
        *,
        center_mm: tuple[BindArg, BindArg, BindArg] = (0.0, 0.0, 0.0),
    ) -> ParametricModel:
        return self._record(
            {
                "op": "box",
                "name": name,
                "dx": dx_mm,
                "dy": dy_mm,
                "dz": dz_mm,
                "center": list(center_mm),
            }
        )

    def add_cylinder(
        self,
        name: str,
        diameter_mm: BindArg,
        height_mm: BindArg,
        *,
        axis: Axis = "Z",
        center_mm: tuple[BindArg, BindArg, BindArg] = (0.0, 0.0, 0.0),
    ) -> ParametricModel:
        return self._record(
            {
                "op": "cylinder",
                "name": name,
                "diameter": diameter_mm,
                "height": height_mm,
                "axis": axis,
                "center": list(center_mm),
            }
        )

    def add_sphere(
        self,
        name: str,
        diameter_mm: BindArg,
        *,
        center_mm: tuple[BindArg, BindArg, BindArg] = (0.0, 0.0, 0.0),
    ) -> ParametricModel:
        return self._record(
            {"op": "sphere", "name": name, "diameter": diameter_mm,
             "center": list(center_mm)}
        )

    def add_cone(
        self,
        name: str,
        diameter_base_mm: BindArg,
        diameter_top_mm: BindArg,
        height_mm: BindArg,
        *,
        axis: Axis = "Z",
        center_mm: tuple[BindArg, BindArg, BindArg] = (0.0, 0.0, 0.0),
    ) -> ParametricModel:
        return self._record(
            {
                "op": "cone",
                "name": name,
                "diameterBase": diameter_base_mm,
                "diameterTop": diameter_top_mm,
                "height": height_mm,
                "axis": axis,
                "center": list(center_mm),
            }
        )

    def extrude_profile(
        self,
        name: str,
        profile_mm: tuple[tuple[BindArg, BindArg], ...],
        depth_mm: BindArg,
        *,
        plane: str = "XY",
        offset_mm: tuple[BindArg, BindArg, BindArg] = (0.0, 0.0, 0.0),
    ) -> ParametricModel:
        if len(profile_mm) < 3:
            raise ValueError("EXTRUDE_PROFILE_NEEDS_AT_LEAST_THREE_POINTS")
        return self._record(
            {
                "op": "extrude",
                "name": name,
                "profile": [list(p) for p in profile_mm],
                "depth": depth_mm,
                "plane": plane,
                "offset": list(offset_mm),
            }
        )

    def revolve_profile(
        self,
        name: str,
        profile_mm: tuple[tuple[BindArg, BindArg], ...],
        angle_deg: BindArg = 360.0,
        *,
        axis: Axis = "Z",
    ) -> ParametricModel:
        if len(profile_mm) < 3:
            raise ValueError("REVOLVE_PROFILE_NEEDS_AT_LEAST_THREE_POINTS")
        return self._record(
            {
                "op": "revolve",
                "name": name,
                "profile": [list(p) for p in profile_mm],
                "angleDeg": angle_deg,
                "axis": axis,
            }
        )

    def loft_profiles(
        self,
        name: str,
        profiles_mm: tuple[tuple[tuple[BindArg, BindArg], ...], ...],
        *,
        offsets_mm: tuple[BindArg, ...] | None = None,
        ruled: bool = True,
    ) -> ParametricModel:
        if len(profiles_mm) < 2:
            raise ValueError("LOFT_NEEDS_AT_LEAST_TWO_PROFILES")
        return self._record(
            {
                "op": "loft",
                "name": name,
                "profiles": [[list(p) for p in profile] for profile in profiles_mm],
                "offsets": list(offsets_mm) if offsets_mm else None,
                "ruled": ruled,
            }
        )

    def sweep_profile(
        self,
        name: str,
        profile_mm: tuple[tuple[BindArg, BindArg], ...],
        path_mm: tuple[tuple[BindArg, BindArg, BindArg], ...],
    ) -> ParametricModel:
        if len(profile_mm) < 3:
            raise ValueError("SWEEP_PROFILE_NEEDS_AT_LEAST_THREE_POINTS")
        if len(path_mm) < 2:
            raise ValueError("SWEEP_PATH_NEEDS_AT_LEAST_TWO_POINTS")
        return self._record(
            {
                "op": "sweep",
                "name": name,
                "profile": [list(p) for p in profile_mm],
                "path": [list(p) for p in path_mm],
            }
        )

    def fillet(self, name: str, radius_mm: BindArg) -> ParametricModel:
        return self._record({"op": "fillet", "name": name, "radius": radius_mm})

    def chamfer(self, name: str, length_mm: BindArg) -> ParametricModel:
        return self._record({"op": "chamfer", "name": name, "length": length_mm})

    def boolean(
        self,
        name: str,
        operation: Literal["union", "cut", "intersection"],
        left: str,
        right: str,
    ) -> ParametricModel:
        if operation not in ("union", "cut", "intersection"):
            raise ValueError("UNKNOWN_BOOLEAN_OPERATION")
        return self._record(
            {"op": "boolean", "name": name, "boolean": operation,
             "left": left, "right": right}
        )

    def circular_pattern(
        self,
        name: str,
        source: str,
        count: int | ParameterRef,
        *,
        axis: Axis = "Z",
        center_mm: tuple[BindArg, BindArg, BindArg] = (0.0, 0.0, 0.0),
    ) -> ParametricModel:
        if not isinstance(count, ParameterRef) and count < 2:
            raise ValueError("PATTERN_COUNT_MUST_BE_AT_LEAST_TWO")
        return self._record(
            {
                "op": "circular-pattern",
                "name": name,
                "source": source,
                "count": count,
                "axis": axis,
                "center": list(center_mm),
            }
        )

    def linear_pattern(
        self,
        name: str,
        source: str,
        count: int | ParameterRef,
        spacing_mm: BindArg,
        *,
        direction: tuple[BindArg, BindArg, BindArg] = (1.0, 0.0, 0.0),
    ) -> ParametricModel:
        if not isinstance(count, ParameterRef) and count < 2:
            raise ValueError("PATTERN_COUNT_MUST_BE_AT_LEAST_TWO")
        return self._record(
            {
                "op": "linear-pattern",
                "name": name,
                "source": source,
                "count": count,
                "spacing": spacing_mm,
                "direction": list(direction),
            }
        )

    def add_frame(
        self,
        name: str,
        origin_mm: tuple[float, float, float],
        direction: tuple[float, float, float],
    ) -> ParametricModel:
        if name in self.frames:
            raise ValueError(f"DUPLICATE_FRAME:{name}")
        self.frames[name] = Frame(name, origin_mm, direction)
        return self

    # -- binding resolution ---------------------------------------------------
    def resolved_parameters(self) -> dict[str, float]:
        """Evaluate the parameter graph to concrete millimetre values."""

        return self.parameters.resolve()

    def resolved_operations(self) -> list[dict[str, Any]]:
        """Return the operation log with every :class:`ParameterRef` bound.

        Resolution is deterministic and happens before any kernel execution.
        Unknown references, unit mismatches, and non-finite bindings fail
        closed.
        """

        values = self.resolved_parameters()
        units = {item.name: item.unit for item in self.parameters.definitions}
        return [
            _resolve_operation(operation, values, units)
            for operation in self.operations
        ]

    # -- execution ------------------------------------------------------------
    def build(self) -> BuiltModel:
        """Execute all operations against OpenCascade and fingerprint faces."""

        from .builder import execute  # local import keeps module import light

        return execute(self)


@dataclass(frozen=True, slots=True)
class ComponentTopology:
    """Stable fingerprint record for one built component."""

    name: str
    face_fingerprints: tuple[str, ...]
    volume_mm3: float
    center_mm: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class BuiltModel:
    """Result of executing a parametric model against the CAD kernel."""

    model_name: str
    parameter_hash: str
    shape_hash: str
    kernel: KernelIdentity
    components: tuple[ComponentTopology, ...]
    operation_count: int
    definition_hash: str = ""

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "modelName": self.model_name,
            "parameterHash": self.parameter_hash,
            "definitionHash": self.definition_hash,
            "kernel": {
                "cadquery": self.kernel.cadquery_version,
                "ocp": self.kernel.ocp_version,
            },
            "components": [
                {
                    "name": component.name,
                    "faces": list(component.face_fingerprints),
                    "volumeMm3": component.volume_mm3,
                    "centerMm": list(component.center_mm),
                }
                for component in sorted(self.components, key=lambda c: c.name)
            ],
        }


def built_model_digest(built: BuiltModel) -> str:
    encoded = json.dumps(
        built.canonical_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def export_artifacts(
    built_shapes: dict[str, Any],
    kernel: KernelIdentity,
    directory: Path,
    *,
    basename: str,
    export_stl: bool = True,
) -> dict[str, Any]:
    """Export STEP/BREP (+STL) artifacts and record digests.

    `built_shapes` maps component name to its CadQuery shape. The combined
    assembly is exported as ``<basename>.step``/``.brep``; each component is
    exported individually as well.
    """

    cq = require_kernel()
    directory.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    visible = {name: shape for name, shape in built_shapes.items()
               if not name.startswith("_")}
    if not visible:
        raise ValueError("NO_EXPORTABLE_COMPONENTS")
    combined = cq.Compound.makeCompound(list(visible.values()))
    for filename, shape in [("assembly", combined), *visible.items()]:
        for extension in ("step", "brep"):
            path = directory / f"{basename}-{filename}.{extension}"
            cq.exporters.export(shape, str(path))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            records.append(
                {
                    "component": filename,
                    "format": extension,
                    "path": str(path),
                    "sha256": digest,
                    "bytes": path.stat().st_size,
                }
            )
    if export_stl:
        path = directory / f"{basename}-assembly.stl"
        cq.exporters.export(combined, str(path))
        records.append(
            {
                "component": "assembly",
                "format": "stl",
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
        )
    return {
        "basename": basename,
        "kernel": {
            "cadquery": kernel.cadquery_version,
            "ocp": kernel.ocp_version,
        },
        "artifacts": records,
    }


def _resolve_value(
    value: Any,
    values: Mapping[str, float],
    units: Mapping[str, str],
    path: str,
) -> Any:
    if isinstance(value, ParameterRef):
        if value.name not in values:
            raise ValueError(f"UNKNOWN_GEOMETRY_PARAMETER:{value.name}")
        declared = units.get(value.name)
        if declared is not None and declared != value.unit:
            raise ValueError(
                f"GEOMETRY_PARAMETER_UNIT_MISMATCH:{value.name}:"
                f"{value.unit}!={declared}"
            )
        resolved = float(values[value.name])
        if not isfinite(resolved):
            raise ValueError(f"GEOMETRY_PARAMETER_NOT_FINITE:{value.name}")
        return resolved
    if isinstance(value, (tuple, list)):
        return [_resolve_value(item, values, units, path) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if not isfinite(float(value)):
            raise ValueError(f"GEOMETRY_VALUE_NOT_FINITE:{path}")
        return value
    if value is None:
        return None
    return value


def resolve_operation(
    operation: Mapping[str, Any],
    values: Mapping[str, float],
    units: Mapping[str, str],
) -> dict[str, Any]:
    """Bind every parameter reference in one operation record."""

    resolved: dict[str, Any] = {}
    for key, value in operation.items():
        resolved[key] = _resolve_value(value, values, units, str(key))
    return resolved


def _resolve_operation(
    operation: dict[str, Any],
    values: Mapping[str, float],
    units: Mapping[str, str],
) -> dict[str, Any]:
    return resolve_operation(operation, values, units)


def _definition_value(value: Any) -> Any:
    if isinstance(value, ParameterRef):
        return {"$param": value.name, "unit": value.unit}
    if isinstance(value, (tuple, list)):
        return [_definition_value(item) for item in value]
    return value


def geometry_definition_payload(model: ParametricModel) -> dict[str, Any]:
    """Canonical serialization of the CAD definition, excluding resolved values.

    Bound parameter references are serialized by name/unit and the parameter
    structure records expressions/units only, so a bound value change alters
    the resolved parameter hash but not this definition hash.
    """

    return {
        "name": model.name,
        "operations": [
            {
                key: _definition_value(value)
                for key, value in sorted(operation.items())
            }
            for operation in model.operations
        ],
        "frames": {
            name: {
                "originMm": list(frame.origin_mm),
                "direction": list(frame.direction),
            }
            for name, frame in sorted(model.frames.items())
        },
        "parameterStructure": [
            {"name": item.name, "expression": item.expression, "unit": item.unit}
            for item in sorted(model.parameters.definitions, key=lambda d: d.name)
        ],
    }


def geometry_definition_digest(model: ParametricModel) -> str:
    """Deterministic SHA-256 of the geometry definition (bindings, not values)."""

    encoded = json.dumps(
        geometry_definition_payload(model),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "Axis",
    "BindArg",
    "BindValue",
    "BuiltModel",
    "ComponentTopology",
    "Frame",
    "KernelIdentity",
    "ParameterRef",
    "ParametricModel",
    "built_model_digest",
    "export_artifacts",
    "geometry_definition_digest",
    "geometry_definition_payload",
    "param",
    "probe_kernel",
    "require_kernel",
    "resolve_operation",
]
