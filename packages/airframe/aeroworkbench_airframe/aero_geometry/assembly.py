"""Composition of aerodynamic geometry primitives as a regeneration participant.

An :class:`AeroGeometryAssembly` composes lifting surfaces, lofted bodies and
control surfaces into a single governed CAD definition. It reuses the existing
:class:`GeometryRegenerationRequest` / :func:`regenerate` path (there is no
second CAD pipeline) and the shared semantic/topology reconciliation, so a
parameter mutation regenerates real OpenCascade geometry, small shape changes
preserve semantic identity, and impossible shapes return invalid receipts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from aeroworkbench_geometry import (
    GeometryReceipt,
    GeometryRegenerationRequest,
    ParameterDef,
    ParameterSet,
    ParametricModel,
    SemanticBinding,
    regenerate,
)
from aeroworkbench_semantics import SemanticAssignment

from ..canonical import content_digest
from .body import LoftedBody
from .control import ControlSurface
from .robustness import GeometryDiagnostic, aero_geometry_diagnostics
from .seam import SurfaceSeam
from .surface import LiftingSurface


@dataclass(frozen=True, slots=True)
class AeroGeometryAssembly:
    """Composed generic aerodynamic geometry (surfaces, bodies, controls)."""

    assembly_id: str
    surfaces: tuple[LiftingSurface, ...] = ()
    bodies: tuple[LoftedBody, ...] = ()
    controls: tuple[ControlSurface, ...] = ()

    def __post_init__(self) -> None:
        if not self.assembly_id.strip():
            raise ValueError("ASSEMBLY_ID_REQUIRED")
        if not self.surfaces and not self.bodies and not self.controls:
            raise ValueError("ASSEMBLY_REQUIRES_COMPONENTS")
        identifiers = [
            *(surface.surface_id for surface in self.surfaces),
            *(body.body_id for body in self.bodies),
            *(control.control_id for control in self.controls),
        ]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("ASSEMBLY_DUPLICATE_COMPONENT_ID")

    def surface(self, surface_id: str) -> LiftingSurface:
        for surface in self.surfaces:
            if surface.surface_id == surface_id:
                return surface
        raise ValueError(f"UNKNOWN_SURFACE:{surface_id}")

    def cad_parameter_defs(self) -> tuple[ParameterDef, ...]:
        definitions: list[ParameterDef] = []
        for surface in self.surfaces:
            definitions.extend(surface.cad_parameter_defs())
        for body in self.bodies:
            definitions.extend(body.cad_parameter_defs())
        for control in self.controls:
            definitions.extend(control.cad_parameter_defs())
        return tuple(definitions)

    def cad_parameter_values(self) -> dict[str, float]:
        values: dict[str, float] = {}
        for definition in self.cad_parameter_defs():
            values[definition.name] = float(definition.value or 0.0)
        return values

    def with_parameters(self, values: dict[str, float]) -> AeroGeometryAssembly:
        return replace(
            self,
            surfaces=tuple(surface.with_parameters(values) for surface in self.surfaces),
            bodies=tuple(body.with_parameters(values) for body in self.bodies),
            controls=tuple(
                replace(
                    control,
                    deflection_deg=values.get(
                        f"{control.control_id}.deflection", control.deflection_deg
                    ),
                    hinge_fraction=values.get(
                        f"{control.control_id}.hinge", control.hinge_fraction
                    ),
                )
                for control in self.controls
            ),
        )

    def semantic_assignments(self) -> tuple[SemanticAssignment, ...]:
        assignments: list[SemanticAssignment] = []
        for surface in self.surfaces:
            assignments.extend(surface.semantic_assignments())
        for body in self.bodies:
            assignments.extend(body.semantic_assignments())
        for control in self.controls:
            assignments.extend(control.semantic_assignments())
        return tuple(assignments)

    def semantic_bindings(self) -> tuple[SemanticBinding, ...]:
        bindings: list[SemanticBinding] = []
        for surface in self.surfaces:
            bindings.append(surface.semantic_binding(surface.surface_id))
        for body in self.bodies:
            bindings.append(body.semantic_binding(body.body_id))
        for control in self.controls:
            bindings.append(control.semantic_binding(control.control_id))
        return tuple(bindings)

    def seams(self) -> tuple[SurfaceSeam, ...]:
        bodies: list[SurfaceSeam] = []
        for surface in self.surfaces:
            bodies.append(surface.seam())
        for body in self.bodies:
            bodies.append(body.seam())
        for control in self.controls:
            bodies.append(control.seam(self.surface(control.parent_id)))
        return tuple(bodies)

    def diagnostics(self) -> tuple[GeometryDiagnostic, ...]:
        return aero_geometry_diagnostics(self.surfaces, self.bodies, self.controls)

    def parametric_model(self, name: str) -> ParametricModel:
        """Build the governed CAD definition for the current parameter values."""

        model = ParametricModel(name, ParameterSet(self.cad_parameter_defs()))
        for surface in self.surfaces:
            model.loft_profiles(
                surface.surface_id,
                surface.section_loops(),
                offsets_mm=surface.offsets_mm(),
                ruled=True,
            )
        for body in self.bodies:
            model.loft_profiles(
                body.body_id,
                body.section_loops(),
                offsets_mm=body.offsets_mm(),
                ruled=True,
            )
        for control in self.controls:
            parent = self.surface(control.parent_id)
            model.loft_profiles(
                control.control_id,
                control.section_loops(parent),
                offsets_mm=control.offsets_mm(parent),
                ruled=True,
            )
        return model

    def regeneration_request(
        self,
        name: str,
        *,
        values: dict[str, float] | None = None,
        parent: GeometryReceipt | None = None,
        permitted_topology_change: str = "preserve",
        export_artifacts: bool = False,
        required_semantic_keys: tuple[str, ...] = (),
    ) -> GeometryRegenerationRequest:
        working = self.with_parameters(values) if values else self
        return GeometryRegenerationRequest(
            model=working.parametric_model(name),
            semantic_bindings=working.semantic_bindings(),
            semantic_assignments=working.semantic_assignments(),
            required_semantic_keys=required_semantic_keys,
            parent=parent,
            permitted_topology_change=permitted_topology_change,
            export_artifacts=export_artifacts,
        )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "assemblyId": self.assembly_id,
            "surfaces": [
                surface.canonical_payload()
                for surface in sorted(self.surfaces, key=lambda item: item.surface_id)
            ],
            "bodies": [
                body.canonical_payload()
                for body in sorted(self.bodies, key=lambda item: item.body_id)
            ],
            "controls": [
                control.canonical_payload()
                for control in sorted(self.controls, key=lambda item: item.control_id)
            ],
        }

    @property
    def digest(self) -> str:
        return content_digest(self.canonical_payload())


def regenerate_assembly(
    assembly: AeroGeometryAssembly,
    name: str,
    *,
    values: dict[str, float] | None = None,
    parent: GeometryReceipt | None = None,
    permitted_topology_change: str = "preserve",
    export_artifacts: bool = False,
    required_semantic_keys: tuple[str, ...] = (),
) -> GeometryReceipt:
    """Regenerate real CAD for an assembly through the shared governance path."""

    request = assembly.regeneration_request(
        name,
        values=values,
        parent=parent,
        permitted_topology_change=permitted_topology_change,
        export_artifacts=export_artifacts,
        required_semantic_keys=required_semantic_keys,
    )
    return regenerate(request)


class AeroGeometryRegenerator:
    """Memoized assembly evaluator: parameter values in, geometry receipts out."""

    def __init__(self, assembly: AeroGeometryAssembly, name: str) -> None:
        if not isinstance(assembly, AeroGeometryAssembly):
            raise TypeError("AERO_GEOMETRY_REGENERATOR_NEEDS_ASSEMBLY")
        self._assembly = assembly
        self._name = name
        self._cache: dict[str, GeometryReceipt] = {}
        self._hits = 0

    @property
    def cache_hits(self) -> int:
        return self._hits

    def evaluate(self, bound_parameters: dict[str, float] | None = None) -> GeometryReceipt:
        merged = {**self._assembly.cad_parameter_values(), **(bound_parameters or {})}
        key = content_digest({name: float(value) for name, value in sorted(merged.items())})
        cached = self._cache.get(key)
        if cached is not None:
            self._hits += 1
            return cached
        receipt = regenerate_assembly(
            self._assembly, self._name, values=bound_parameters
        )
        self._cache[key] = receipt
        return receipt


__all__ = [
    "AeroGeometryAssembly",
    "AeroGeometryRegenerator",
    "regenerate_assembly",
]
