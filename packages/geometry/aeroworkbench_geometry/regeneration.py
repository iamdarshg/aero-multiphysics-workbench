"""Governed geometry regeneration as a first-class design participant.

A :class:`GeometryRegenerationRequest` carries a typed generic CAD definition
plus normalized bound parameter values; :func:`regenerate` resolves the
parameter graph, executes real OpenCascade geometry, runs the robustness
gates, reconciles semantics/topology, and returns an immutable
:class:`GeometryReceipt`.

The request never accepts script text or caller-supplied filesystem paths: the
definition is an in-process :class:`ParametricModel` operation graph and any
artifact export happens inside a private temporary directory whose results are
content-addressed. Invalid geometry becomes an explicit ``invalid`` receipt so
downstream campaigns can treat it as an invalid sample rather than crashing or
fabricating metrics.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from math import isfinite
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, cast

from .builder import live_shapes
from .parameters import resolved_parameter_digest
from .parametric import (
    BuiltModel,
    ComponentTopology,
    KernelIdentity,
    ParametricModel,
    export_artifacts,
    geometry_definition_digest,
    probe_kernel,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from aeroworkbench_semantics import (
        EntityKind,
        ReconciliationReport,
        SemanticAssignment,
        TopologyModel,
        TopologyReport,
    )


@dataclass(frozen=True, slots=True)
class SemanticBinding:
    """Bind a semantic entity to one built geometry component (generic)."""

    semantic_key: str
    kind: str
    region: str
    component: str

    def __post_init__(self) -> None:
        for label, value in (
            ("semantic_key", self.semantic_key),
            ("kind", self.kind),
            ("region", self.region),
            ("component", self.component),
        ):
            if not value.strip():
                raise ValueError(f"SEMANTIC_BINDING_{label.upper()}_REQUIRED")


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    """Content-addressed reference to one exported native CAD artifact."""

    component: str
    format: str
    sha256: str
    bytes: int


@dataclass(frozen=True, slots=True)
class GeometryReceipt:
    """Immutable evidence of one real geometry regeneration."""

    definition_hash: str
    parameter_hash: str
    shape_hash: str
    topology_digest: str
    kernel: KernelIdentity
    components: tuple[ComponentTopology, ...] = ()
    bounds_mm: tuple[tuple[str, tuple[float, float, float, float, float, float]], ...] = ()
    resolved_parameters: tuple[tuple[str, float], ...] = ()
    artifact_refs: tuple[ArtifactReference, ...] = ()
    semantic_assignments: tuple[SemanticAssignment, ...] = ()
    topology: TopologyModel | None = None
    semantic_report: ReconciliationReport | None = None
    topology_report: TopologyReport | None = None
    validity_state: str = "valid"
    warnings: tuple[str, ...] = ()
    invalid_reasons: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return self.validity_state == "valid"

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "definitionHash": self.definition_hash,
            "parameterHash": self.parameter_hash,
            "shapeHash": self.shape_hash,
            "topologyDigest": self.topology_digest,
            "kernel": {
                "cadquery": self.kernel.cadquery_version,
                "ocp": self.kernel.ocp_version,
                "available": self.kernel.available,
            },
            "components": [
                {
                    "name": component.name,
                    "volumeMm3": component.volume_mm3,
                    "centerMm": list(component.center_mm),
                    "faces": list(component.face_fingerprints),
                }
                for component in sorted(self.components, key=lambda c: c.name)
            ],
            "boundsMm": {
                name: list(bounds) for name, bounds in sorted(self.bounds_mm)
            },
            "resolvedParameters": dict(sorted(self.resolved_parameters)),
            "artifacts": [
                {
                    "component": artifact.component,
                    "format": artifact.format,
                    "sha256": artifact.sha256,
                    "bytes": artifact.bytes,
                }
                for artifact in self.artifact_refs
            ],
            "semanticAssignments": [
                {
                    "surfaceId": item.surface_id,
                    "semanticKey": item.semantic_key,
                    "role": item.role,
                    "boundary": item.boundary,
                }
                for item in sorted(
                    self.semantic_assignments, key=lambda item: item.semantic_key
                )
            ],
            "semanticReport": None
            if self.semantic_report is None
            else {
                "persistent": [item.semantic_key for item in self.semantic_report.persistent],
                "missing": list(self.semantic_report.missing),
                "added": [item.semantic_key for item in self.semantic_report.added],
                "ambiguous": list(self.semantic_report.ambiguous),
            },
            "topologyReport": None
            if self.topology_report is None
            else {
                "preserved": [item.semantic_key for item in self.topology_report.preserved],
                "added": [item.semantic_key for item in self.topology_report.added],
                "missing": list(self.topology_report.missing),
                "ambiguous": list(self.topology_report.ambiguous),
                "changed": [
                    {"change": item.change, "key": item.semantic_key}
                    for item in self.topology_report.changed
                ],
                "requiresRemesh": self.topology_report.requires_remesh,
                "reason": self.topology_report.reason,
            },
            "validityState": self.validity_state,
            "warnings": list(self.warnings),
            "invalidReasons": list(self.invalid_reasons),
        }


def geometry_receipt_digest(receipt: GeometryReceipt) -> str:
    """Deterministic content digest of a regeneration receipt."""

    encoded = json.dumps(
        receipt.canonical_payload(),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class GeometryRegenerationRequest:
    """Typed request for one governed geometry regeneration."""

    model: ParametricModel
    bound_parameters: Mapping[str, float] = field(default_factory=dict)
    semantic_bindings: tuple[SemanticBinding, ...] = ()
    semantic_assignments: tuple[SemanticAssignment, ...] = ()
    required_semantic_keys: tuple[str, ...] = ()
    parent: GeometryReceipt | None = None
    permitted_topology_change: str = "preserve"
    export_artifacts: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.model, ParametricModel):
            raise TypeError("GEOMETRY_REQUEST_NEEDS_PARAMETRIC_DEFINITION")
        if self.permitted_topology_change not in {"preserve", "remesh", "any"}:
            raise ValueError(
                f"UNKNOWN_TOPOLOGY_POLICY:{self.permitted_topology_change}"
            )
        if self.parent is not None and not isinstance(self.parent, GeometryReceipt):
            raise TypeError("GEOMETRY_REQUEST_PARENT_MUST_BE_RECEIPT")
        for binding in self.semantic_bindings:
            if not isinstance(binding, SemanticBinding):
                raise TypeError("GEOMETRY_REQUEST_BINDING_MUST_BE_SEMANTIC")


def _bounds(
    shape: Any, warnings: list[str], name: str
) -> tuple[float, float, float, float, float, float]:
    try:
        box = shape.BoundingBox()
        values = (
            float(box.xmin),
            float(box.xmax),
            float(box.ymin),
            float(box.ymax),
            float(box.zmin),
            float(box.zmax),
        )
    except Exception:  # noqa: BLE001 - kernel box shape varies by binding
        warnings.append(f"BOUNDS_UNAVAILABLE:{name}")
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    if not all(isfinite(value) for value in values):
        warnings.append(f"BOUNDS_NOT_FINITE:{name}")
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    return values


def _topology_digest(topology: TopologyModel) -> str:
    payload = {
        "entities": [
            {
                "key": entity.semantic_key,
                "kind": entity.kind,
                "region": entity.region,
                "fingerprint": entity.fingerprint,
            }
            for entity in sorted(topology.entities, key=lambda e: e.semantic_key)
        ]
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _failure(
    kernel: KernelIdentity,
    definition_hash: str,
    parameter_hash: str,
    reason: str,
) -> GeometryReceipt:
    return GeometryReceipt(
        definition_hash=definition_hash,
        parameter_hash=parameter_hash,
        shape_hash="",
        topology_digest="",
        kernel=kernel,
        validity_state="invalid",
        invalid_reasons=(reason,),
    )


def regenerate(request: GeometryRegenerationRequest) -> GeometryReceipt:
    """Regenerate real CAD for the bound request and return a receipt.

    All failure paths return an ``invalid`` receipt (fail closed); arbitrary
    script text or filesystem paths are never accepted because the definition
    is the in-process operation graph.
    """

    model = request.model
    kernel = probe_kernel()
    definition_hash = geometry_definition_digest(model)

    try:
        parameters = model.parameters.with_literals(dict(request.bound_parameters))
        resolved = parameters.resolve()
    except ValueError as exc:
        return _failure(
            kernel, definition_hash, "", f"PARAMETER_RESOLUTION_FAILED:{exc}"
        )

    parameter_hash = resolved_parameter_digest(resolved)
    invalid: list[str] = []
    warnings: list[str] = []
    for name, value in resolved.items():
        if not isfinite(value):
            invalid.append(f"NONFINITE_PARAMETER:{name}")

    if not kernel.available:
        return _failure(kernel, definition_hash, parameter_hash, "CAD_KERNEL_UNAVAILABLE")

    bound_model = replace(model, parameters=parameters)
    try:
        built: BuiltModel = bound_model.build()
        shapes: dict[str, Any] = live_shapes(built)
    except Exception as exc:  # noqa: BLE001 - kernel errors fail closed
        return _failure(
            kernel,
            definition_hash,
            parameter_hash,
            f"CAD_EXECUTION_FAILED:{type(exc).__name__}:{exc}",
        )

    components = tuple(sorted(built.components, key=lambda component: component.name))
    bounds: list[tuple[str, tuple[float, float, float, float, float, float]]] = []
    for name in sorted(shapes):
        if name.startswith("_"):
            continue
        shape = shapes[name]
        try:
            if not bool(shape.isValid()):
                invalid.append(f"SHAPE_INVALID:{name}")
        except Exception:  # noqa: BLE001 - validity probe unavailable
            warnings.append(f"SHAPE_VALIDITY_UNAVAILABLE:{name}")
        bounds.append((name, _bounds(shape, warnings, name)))
    if not components:
        invalid.append("NO_COMPONENTS_BUILT")
    for component in components:
        if not all(isfinite(value) for value in component.center_mm):
            invalid.append(f"NONFINITE_CENTER:{component.name}")
        if not isfinite(component.volume_mm3):
            invalid.append(f"NONFINITE_VOLUME:{component.name}")
        elif component.volume_mm3 <= 0.0:
            invalid.append(f"NON_POSITIVE_VOLUME:{component.name}")

    from aeroworkbench_semantics import (
        reconcile_surfaces,
        reconcile_topology,
        topology_from_components,
    )

    topology: TopologyModel | None = None
    if request.semantic_bindings:
        assignments = tuple(
            (
                binding.semantic_key,
                cast("EntityKind", binding.kind),
                binding.region,
                binding.component,
            )
            for binding in request.semantic_bindings
        )
        face_fingerprints = {
            component.name: component.face_fingerprints for component in components
        }
        try:
            topology = topology_from_components(assignments, face_fingerprints)
        except KeyError as exc:
            invalid.append(f"SEMANTIC_BINDING_UNKNOWN_COMPONENT:{exc}")
            topology = None
    topology_digest = _topology_digest(topology) if topology is not None else ""

    semantic_report = None
    topology_report = None
    if request.parent is not None:
        semantic_report = reconcile_surfaces(
            request.parent.semantic_assignments, request.semantic_assignments
        )
        for key in semantic_report.missing:
            invalid.append(f"SEMANTIC_MISSING:{key}")
        for key in semantic_report.ambiguous:
            invalid.append(f"SEMANTIC_AMBIGUOUS:{key}")
        if topology is not None and request.parent.topology is not None:
            topology_report = reconcile_topology(request.parent.topology, topology)
            for key in topology_report.ambiguous:
                invalid.append(f"TOPOLOGY_AMBIGUOUS:{key}")
            if request.permitted_topology_change == "preserve":
                for key in topology_report.missing:
                    invalid.append(f"TOPOLOGY_MISSING:{key}")
                if any(
                    item.change in ("split", "merged")
                    for item in topology_report.changed
                ):
                    invalid.append("TOPOLOGY_IDENTITY_CHANGED")
            elif request.permitted_topology_change == "remesh" and any(
                item.change in ("split", "merged") for item in topology_report.changed
            ):
                warnings.append("TOPOLOGY_REMESH_REQUIRED")

    present_keys = {item.semantic_key for item in request.semantic_assignments}
    if topology is not None:
        present_keys |= {entity.semantic_key for entity in topology.entities}
    for key in request.required_semantic_keys:
        if key not in present_keys:
            invalid.append(f"SEMANTIC_REQUIRED_ROLE_MISSING:{key}")

    artifact_refs: list[ArtifactReference] = []
    if request.export_artifacts:
        try:
            with TemporaryDirectory(prefix="geometry-regen-") as workspace:
                records = export_artifacts(
                    shapes,
                    kernel,
                    Path(workspace),
                    basename="geometry",
                    export_stl=False,
                )
            for record in records["artifacts"]:
                reference = ArtifactReference(
                    component=str(record["component"]),
                    format=str(record["format"]),
                    sha256=str(record["sha256"]),
                    bytes=int(record["bytes"]),
                )
                if len(reference.sha256) != 64 or reference.bytes <= 0:
                    invalid.append(
                        f"ARTIFACT_HASH_INVALID:{reference.component}:{reference.format}"
                    )
                artifact_refs.append(reference)
        except Exception as exc:  # noqa: BLE001 - export is optional evidence
            warnings.append(f"ARTIFACT_EXPORT_FAILED:{type(exc).__name__}")

    return GeometryReceipt(
        definition_hash=definition_hash,
        parameter_hash=parameter_hash,
        shape_hash=built.shape_hash,
        topology_digest=topology_digest,
        kernel=kernel,
        components=components,
        bounds_mm=tuple(bounds),
        resolved_parameters=tuple(sorted(resolved.items())),
        artifact_refs=tuple(
            sorted(artifact_refs, key=lambda ref: (ref.component, ref.format))
        ),
        semantic_assignments=tuple(request.semantic_assignments),
        topology=topology,
        semantic_report=semantic_report,
        topology_report=topology_report,
        validity_state="invalid" if invalid else "valid",
        warnings=tuple(warnings),
        invalid_reasons=tuple(sorted(set(invalid))),
    )


class GeometryRegenerator:
    """Memoized evaluator: bound parameter values in, geometry receipts out."""

    def __init__(self, request: GeometryRegenerationRequest) -> None:
        if not isinstance(request, GeometryRegenerationRequest):
            raise TypeError("GEOMETRY_REGENERATOR_NEEDS_REQUEST")
        self._request = request
        self._cache: dict[str, GeometryReceipt] = {}
        self._hits = 0

    @property
    def cache_hits(self) -> int:
        return self._hits

    def evaluate(self, bound_parameters: Mapping[str, float]) -> GeometryReceipt:
        bound = {str(name): float(value) for name, value in bound_parameters.items()}
        key = self._cache_key(bound)
        cached = self._cache.get(key)
        if cached is not None:
            self._hits += 1
            return cached
        receipt = regenerate(replace(self._request, bound_parameters=bound))
        self._cache[key] = receipt
        return receipt

    def _cache_key(self, bound: Mapping[str, float]) -> str:
        request = self._request
        payload = {
            "definition": geometry_definition_digest(request.model),
            "bound": {
                name: (float(value) if isfinite(float(value)) else f"nonfinite:{value}")
                for name, value in sorted(bound.items())
            },
            "policy": request.permitted_topology_change,
            "required": list(request.required_semantic_keys),
            "bindings": [
                [binding.semantic_key, binding.kind, binding.region, binding.component]
                for binding in request.semantic_bindings
            ],
            "parent": None if request.parent is None else geometry_receipt_digest(request.parent),
            "export": request.export_artifacts,
        }
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "ArtifactReference",
    "GeometryReceipt",
    "GeometryRegenerationRequest",
    "GeometryRegenerator",
    "SemanticBinding",
    "geometry_receipt_digest",
    "regenerate",
]
