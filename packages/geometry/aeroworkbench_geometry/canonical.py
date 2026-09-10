"""Small, deterministic geometry model used by CAD and meshing adapters.

The model deliberately stores semantic surfaces and normalized millimetre
parameters rather than pretending to be a CAD kernel. Native STEP/BREP output
is produced only by a capability-backed adapter; this module supplies the
stable input identity that such an adapter must consume.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True, slots=True)
class Surface:
    """A named topological surface with a stable semantic key."""

    surface_id: str
    role: str
    semantic_key: str


@dataclass(frozen=True, slots=True)
class GeometryModel:
    """Canonical parametric geometry independent of a particular CAD kernel."""

    name: str
    parameters_mm: tuple[tuple[str, float], ...]
    surfaces: tuple[Surface, ...]

    def __post_init__(self) -> None:
        if not self.name or not self.parameters_mm or not self.surfaces:
            raise ValueError("GEOMETRY_FIELDS_REQUIRED")
        keys = [key for key, _ in self.parameters_mm]
        if len(keys) != len(set(keys)):
            raise ValueError("DUPLICATE_GEOMETRY_PARAMETER")
        for key, value in self.parameters_mm:
            if not key or not isfinite(value) or value <= 0:
                raise ValueError("INVALID_GEOMETRY_PARAMETER")
        surface_ids = [surface.surface_id for surface in self.surfaces]
        if len(surface_ids) != len(set(surface_ids)):
            raise ValueError("DUPLICATE_SURFACE_ID")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "parametersMm": {key: value for key, value in sorted(self.parameters_mm)},
            "surfaces": [
                {
                    "surfaceId": surface.surface_id,
                    "role": surface.role,
                    "semanticKey": surface.semantic_key,
                }
                for surface in sorted(self.surfaces, key=lambda item: item.surface_id)
            ],
        }


def shape_hash(model: GeometryModel) -> str:
    """Return the content identity of canonical geometry."""

    encoded = json.dumps(
        model.canonical_payload(), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def make_edf_geometry(
    *,
    diameter_mm: float = 70.0,
    hub_diameter_mm: float = 24.0,
    blade_count: float = 12.0,
) -> GeometryModel:
    """Create the reference 70 mm EDF envelope with persistent surface keys."""

    if hub_diameter_mm >= diameter_mm:
        raise ValueError("HUB_MUST_BE_SMALLER_THAN_SHROUD")
    if blade_count < 1 or blade_count != int(blade_count):
        raise ValueError("INVALID_BLADE_COUNT")
    surfaces = (
        Surface("inlet", "fluid-inlet", "edf.inlet"),
        Surface("outlet", "fluid-outlet", "edf.outlet"),
        Surface("shroud", "solid-shroud", "edf.shroud"),
        Surface("hub", "solid-hub", "edf.hub"),
        Surface("blade-root", "rotor-interface", "edf.blade-root"),
        Surface("blade-tip", "rotor-interface", "edf.blade-tip"),
    )
    return GeometryModel(
        name="edf-70mm",
        parameters_mm=(
            ("diameter", float(diameter_mm)),
            ("hubDiameter", float(hub_diameter_mm)),
            ("bladeCount", float(blade_count)),
        ),
        surfaces=surfaces,
    )
