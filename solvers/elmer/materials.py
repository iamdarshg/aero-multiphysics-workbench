"""Material mapping for the native Elmer thermal participant.

Thermal conduction needs conductivity, heat capacity, and density. Values come
from immutable material revisions (constant or temperature-tabulated). A missing
or unrepresentable property is a hard failure; the mapper never substitutes a
default. Only temperature tables can be expressed directly as an Elmer
``Variable Temperature`` material law, so any other independent axis is
rejected instead of being silently frozen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from participants.errors import NativeErrorCode, ParticipantError

REQUIRED_THERMAL_PROPERTIES = ("conductivity", "heat_capacity", "density")

_CANONICAL_UNITS = {
    "conductivity": "W/(m K)",
    "heat_capacity": "J/(kg K)",
    "density": "kg/m^3",
}

# Elmer property keyword for each required thermal property.
_ELMER_KEYWORD = {
    "conductivity": "Heat Conductivity",
    "heat_capacity": "Heat Capacity",
    "density": "Density",
}

_SUPPORTED_KINDS = frozenset(
    {"constant", "temperature_dependent", "tabulated", "temperature_table"}
)


def _fail(detail: str) -> ParticipantError:
    return ParticipantError(NativeErrorCode.PREPARATION_FAILED, detail)


@dataclass(frozen=True, slots=True)
class ElmerProperty:
    """One material property in the form the SIF can express."""

    name: str
    unit: str
    kind: str  # "constant" | "temperature_table"
    constant: float | None
    samples: tuple[tuple[float, float], ...]
    source: str

    def sif_lines(self) -> list[str]:
        keyword = _ELMER_KEYWORD[self.name]
        if self.kind == "constant":
            assert self.constant is not None
            return [f"  {keyword} = {self.constant:.6e}"]
        lines = [f"  {keyword} = Variable Temperature", "    Real"]
        lines.extend(f"      {axis:.6e}  {value:.6e}" for axis, value in self.samples)
        lines.append("    End")
        return lines

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "kind": self.kind,
            "constant": self.constant,
            "samples": [[axis, value] for axis, value in self.samples],
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class ElmerMaterial:
    """A material revision resolved into Elmer thermal properties."""

    name: str
    identity: str
    properties: tuple[ElmerProperty, ...]

    def __post_init__(self) -> None:
        present = {prop.name for prop in self.properties}
        missing = [name for name in REQUIRED_THERMAL_PROPERTIES if name not in present]
        if missing:
            raise _fail(f"MATERIAL_PROPERTY_MISSING:{self.name}:{','.join(missing)}")

    def property(self, name: str) -> ElmerProperty:
        for prop in self.properties:
            if prop.name == name:
                return prop
        raise _fail(f"MATERIAL_PROPERTY_MISSING:{self.name}:{name}")

    def sif_block(self, index: int) -> str:
        lines = [f"Material {index}", f'  Name = "{self.name}"']
        for name in REQUIRED_THERMAL_PROPERTIES:
            lines.extend(self.property(name).sif_lines())
        lines.append("End")
        return "\n".join(lines)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "identity": self.identity,
            "properties": [prop.canonical_payload() for prop in self.properties],
        }


def _value_from_payload(name: str, payload: Any) -> ElmerProperty:
    """Coerce one property payload into an :class:`ElmerProperty`."""

    unit = _CANONICAL_UNITS[name]
    if isinstance(payload, (int, float)):
        if isinstance(payload, bool):
            raise _fail(f"MATERIAL_PROPERTY_UNSUPPORTED:{name}:bool")
        value = float(payload)
        if value != value or value in (float("inf"), float("-inf")):
            raise _fail(f"MATERIAL_PROPERTY_NOT_FINITE:{name}")
        return ElmerProperty(name, unit, "constant", value, (), "input")
    if isinstance(payload, dict):
        kind = str(payload.get("kind", ""))
        source = str(payload.get("source", "input"))
        if kind in {
            "temperature_dependent",
            "frequency_dependent",
            "tabulated",
            "temperature_table",
        }:
            axis_unit = str(payload.get("axisUnit", payload.get("axis_unit", "")))
            if axis_unit and axis_unit.upper() not in {"K", "KELVIN"}:
                raise _fail(f"MATERIAL_PROPERTY_UNSUPPORTED_AXIS:{name}:{axis_unit}")
            raw_samples = payload.get("samples", ())
            samples = _coerce_samples(name, raw_samples)
            if not samples:
                raise _fail(f"MATERIAL_PROPERTY_HAS_NO_SAMPLES:{name}")
            return ElmerProperty(
                name, str(payload.get("unit", unit)), "temperature_table", None, samples, source
            )
        if kind not in {"", "constant"}:
            raise _fail(f"MATERIAL_PROPERTY_UNSUPPORTED:{name}:{kind}")
        raw = payload.get("constant")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise _fail(f"MATERIAL_PROPERTY_UNSUPPORTED:{name}:constant")
        value = float(raw)
        if value != value or value in (float("inf"), float("-inf")):
            raise _fail(f"MATERIAL_PROPERTY_NOT_FINITE:{name}")
        return ElmerProperty(
            name, str(payload.get("unit", unit)), "constant", value, (), source
        )
    # An already-typed MaterialValue-like object (duck-typed, no import cycle).
    evaluate = getattr(payload, "evaluate", None)
    kind = getattr(payload, "kind", None)
    if callable(evaluate) and kind is not None:
        if kind == "constant":
            return _value_from_payload(
                name,
                {"kind": "constant", "constant": float(payload.constant), "unit": payload.unit,
                 "source": payload.source},
            )
        samples = tuple((float(a), float(v)) for a, v in getattr(payload, "samples", ()))
        axis_unit = getattr(payload, "axis_unit", "") or ""
        if axis_unit and axis_unit.upper() not in {"K", "KELVIN"}:
            raise _fail(f"MATERIAL_PROPERTY_UNSUPPORTED_AXIS:{name}:{axis_unit}")
        return ElmerProperty(
            name, str(payload.unit), "temperature_table", None, samples, str(payload.source)
        )
    raise _fail(f"MATERIAL_PROPERTY_UNSUPPORTED:{name}")


def _coerce_samples(name: str, raw: Any) -> tuple[tuple[float, float], ...]:
    if not isinstance(raw, (list, tuple)):
        raise _fail(f"MATERIAL_PROPERTY_SAMPLES_INVALID:{name}")
    samples: list[tuple[float, float]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise _fail(f"MATERIAL_PROPERTY_SAMPLES_INVALID:{name}")
        try:
            axis = float(item[0])
            value = float(item[1])
        except (TypeError, ValueError) as exc:
            raise _fail(f"MATERIAL_PROPERTY_SAMPLES_INVALID:{name}:{exc}") from exc
        if axis != axis or value != value:
            raise _fail(f"MATERIAL_PROPERTY_NOT_FINITE:{name}")
        samples.append((axis, value))
    if len(samples) >= 2:
        axes = [sample[0] for sample in samples]
        if any(not axis < nxt for axis, nxt in zip(axes, axes[1:], strict=False)):
            raise _fail(f"MATERIAL_PROPERTY_SAMPLES_NOT_INCREASING:{name}")
    return tuple(samples)


def _property_payloads(payload: Any) -> tuple[str, str, dict[str, Any]]:
    """Return (name, identity, property-payload mapping) for a revision payload."""

    if hasattr(payload, "properties") and hasattr(payload, "identity"):
        properties = {str(key): value for key, value in payload.properties.items()}
        return "", str(payload.identity), properties
    if isinstance(payload, dict) and "properties" in payload:
        properties = payload.get("properties")
        if not isinstance(properties, dict):
            raise _fail("MATERIAL_REVISION_PROPERTIES_INVALID")
        identity = f"{payload.get('materialId', 'material')}@{payload.get('revision', 'unknown')}"
        return "", identity, {str(key): value for key, value in properties.items()}
    if isinstance(payload, dict):
        return "", "inline-material", {str(key): value for key, value in payload.items()}
    raise _fail("MATERIAL_REVISION_UNSUPPORTED")


def map_material(name: str, payload: Any) -> ElmerMaterial:
    """Resolve one named material into Elmer thermal properties.

    ``payload`` may be a ``MaterialRevision``, its canonical payload, or a plain
    mapping of property names to scalar/table values. All three required thermal
    properties must be present; anything missing raises rather than defaulting.
    """

    if not name.strip():
        raise _fail("MATERIAL_NAME_REQUIRED")
    _, identity, properties = _property_payloads(payload)
    resolved: list[ElmerProperty] = []
    for property_name in REQUIRED_THERMAL_PROPERTIES:
        if property_name not in properties:
            raise _fail(f"MATERIAL_PROPERTY_MISSING:{name}:{property_name}")
        resolved.append(_value_from_payload(property_name, properties[property_name]))
    return ElmerMaterial(name=name, identity=identity, properties=tuple(resolved))


def map_materials(payloads: dict[str, Any]) -> dict[str, ElmerMaterial]:
    if not payloads:
        raise _fail("MATERIALS_REQUIRED")
    return {name: map_material(name, payload) for name, payload in payloads.items()}


def material_digest(materials: dict[str, ElmerMaterial]) -> str:
    """Content digest of the resolved material set, ordered by name."""

    import hashlib
    import json

    payload = [materials[name].canonical_payload() for name in sorted(materials)]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
