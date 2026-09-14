"""Real parametric CAD layer backed by CadQuery/OpenCascade.

Every operation constructs actual OpenCascade topology. When CadQuery is not
importable the kernel probe reports ``unavailable`` and construction fails
closed instead of returning placeholder shapes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .parameters import ParameterSet

Axis = Literal["X", "Y", "Z"]


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
        dx_mm: float,
        dy_mm: float,
        dz_mm: float,
        *,
        center_mm: tuple[float, float, float] = (0.0, 0.0, 0.0),
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
        diameter_mm: float,
        height_mm: float,
        *,
        axis: Axis = "Z",
        center_mm: tuple[float, float, float] = (0.0, 0.0, 0.0),
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
        diameter_mm: float,
        *,
        center_mm: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> ParametricModel:
        return self._record(
            {"op": "sphere", "name": name, "diameter": diameter_mm,
             "center": list(center_mm)}
        )

    def add_cone(
        self,
        name: str,
        diameter_base_mm: float,
        diameter_top_mm: float,
        height_mm: float,
        *,
        axis: Axis = "Z",
        center_mm: tuple[float, float, float] = (0.0, 0.0, 0.0),
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
        profile_mm: tuple[tuple[float, float], ...],
        depth_mm: float,
        *,
        plane: str = "XY",
        offset_mm: tuple[float, float, float] = (0.0, 0.0, 0.0),
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
        profile_mm: tuple[tuple[float, float], ...],
        angle_deg: float = 360.0,
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
        profiles_mm: tuple[tuple[tuple[float, float], ...], ...],
        *,
        offsets_mm: tuple[float, ...] | None = None,
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
        profile_mm: tuple[tuple[float, float], ...],
        path_mm: tuple[tuple[float, float, float], ...],
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

    def fillet(self, name: str, radius_mm: float) -> ParametricModel:
        return self._record({"op": "fillet", "name": name, "radius": radius_mm})

    def chamfer(self, name: str, length_mm: float) -> ParametricModel:
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
        count: int,
        *,
        axis: Axis = "Z",
        center_mm: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> ParametricModel:
        if count < 2:
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
        count: int,
        spacing_mm: float,
        *,
        direction: tuple[float, float, float] = (1.0, 0.0, 0.0),
    ) -> ParametricModel:
        if count < 2:
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

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "modelName": self.model_name,
            "parameterHash": self.parameter_hash,
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


__all__ = [
    "Axis",
    "BuiltModel",
    "ComponentTopology",
    "Frame",
    "KernelIdentity",
    "ParametricModel",
    "built_model_digest",
    "export_artifacts",
    "probe_kernel",
    "require_kernel",
]
