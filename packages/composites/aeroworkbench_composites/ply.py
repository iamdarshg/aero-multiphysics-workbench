"""Orthotropic ply architecture, strength allowables, and environment modifiers.

A ply is an anisotropic layer: it carries fibre/matrix identity, an immutable
material revision, temperature-dependent engineering constants, and a
strength-allowable set bound to that exact material digest. Temperature and
moisture effects are applied through sourced, validity-bounded modifiers, and
out-of-validity use fails closed rather than extrapolating. Nothing here
collapses an orthotropic layer to a single isotropic modulus.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_durability.environment import DegradationModifier
from aeroworkbench_materials import MaterialRevision, Ply, material_digest

from .provenance import SOFTWARE_IDENTITY, SOFTWARE_VERSION, analytical_provenance
from .validity import DataUnavailable, Validity, finite

__all__ = [
    "MoistureModifier",
    "PlyArchitecture",
    "PlyConstants",
    "PlyStrength",
    "StrengthAssessment",
    "apply_environment",
    "ply_constants",
]

_PLY_SYMMETRIES = ("orthotropic", "transversely_isotropic", "laminate")


def _prop(
    material: MaterialRevision, name: str, *, temperature_k: float | None
) -> float | None:
    prop = material.properties.get(name)
    if prop is None:
        return None
    try:
        return float(prop.evaluate(temperature_k=temperature_k))
    except ValueError as exc:
        raise DataUnavailable(f"PLY_PROPERTY_EVALUATION_FAILED:{name}:{exc}") from exc


def _require(value: float | None, name: str, material: MaterialRevision) -> float:
    if value is None:
        raise DataUnavailable(f"PLY_MISSING_PROPERTY:{material.identity}:{name}")
    return finite(value, name)


@dataclass(frozen=True, slots=True)
class PlyStrength:
    """Strength allowables for one orthotropic ply material revision.

    Values are tension/compression strengths in the fibre (1) and transverse (2)
    directions plus the in-plane shear strength. Transverse (3) and interlaminar
    allowables are optional and required only by the criteria/seams that use
    them; a missing required allowable fails closed at evaluation time.
    """

    material_digest: str
    source: str
    revision: str
    x_tension_pa: float
    x_compression_pa: float
    y_tension_pa: float
    y_compression_pa: float
    shear_pa: float
    temperature_min_k: float
    temperature_max_k: float
    z_tension_pa: float | None = None
    z_compression_pa: float | None = None
    interlaminar_shear_pa: float | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if len(self.material_digest) != 64:
            raise DataUnavailable("PLY_STRENGTH_REQUIRES_MATERIAL_DIGEST")
        if not self.source.strip() or not self.revision.strip():
            raise DataUnavailable("PLY_STRENGTH_SOURCE_AND_REVISION_REQUIRED")
        for name in (
            "x_tension_pa",
            "x_compression_pa",
            "y_tension_pa",
            "y_compression_pa",
            "shear_pa",
        ):
            finite(getattr(self, name), name, positive=True)
        for name in ("z_tension_pa", "z_compression_pa", "interlaminar_shear_pa"):
            value = getattr(self, name)
            if value is not None:
                finite(value, name, positive=True)
        if self.temperature_max_k <= self.temperature_min_k:
            raise DataUnavailable("PLY_STRENGTH_TEMPERATURE_RANGE_INVALID")

    @property
    def identity(self) -> str:
        return f"ply-strength@{self.revision}"

    def in_temperature_range(self, temperature_k: float) -> bool:
        return self.temperature_min_k <= temperature_k <= self.temperature_max_k

    def value(self, allowable: str) -> float | None:
        mapping: dict[str, float | None] = {
            "x_tension_pa": self.x_tension_pa,
            "x_compression_pa": self.x_compression_pa,
            "y_tension_pa": self.y_tension_pa,
            "y_compression_pa": self.y_compression_pa,
            "shear_pa": self.shear_pa,
            "z_tension_pa": self.z_tension_pa,
            "z_compression_pa": self.z_compression_pa,
            "interlaminar_shear_pa": self.interlaminar_shear_pa,
        }
        if allowable not in mapping:
            raise DataUnavailable(f"UNKNOWN_ALLOWABLE:{allowable}")
        return mapping[allowable]

    def scaled(self, factors: dict[str, float], *, note: str) -> PlyStrength:
        """Return a copy with each named allowable multiplied by its factor."""

        def scaled_value(name: str) -> float | None:
            value = self.value(name)
            return None if value is None else value * factors.get(name, 1.0)

        return PlyStrength(
            material_digest=self.material_digest,
            source=self.source,
            revision=self.revision,
            x_tension_pa=scaled_value("x_tension_pa") or self.x_tension_pa,
            x_compression_pa=scaled_value("x_compression_pa") or self.x_compression_pa,
            y_tension_pa=scaled_value("y_tension_pa") or self.y_tension_pa,
            y_compression_pa=scaled_value("y_compression_pa") or self.y_compression_pa,
            shear_pa=scaled_value("shear_pa") or self.shear_pa,
            temperature_min_k=self.temperature_min_k,
            temperature_max_k=self.temperature_max_k,
            z_tension_pa=scaled_value("z_tension_pa"),
            z_compression_pa=scaled_value("z_compression_pa"),
            interlaminar_shear_pa=scaled_value("interlaminar_shear_pa"),
            note=note,
        )


@dataclass(frozen=True, slots=True)
class MoistureModifier:
    """A moisture-conditioned allowable knockdown with a declared validity band."""

    modifier_id: str
    revision: str
    source: str
    factor: float
    moisture_min_fraction: float
    moisture_max_fraction: float
    note: str = ""

    def __post_init__(self) -> None:
        if not self.modifier_id.strip() or not self.source.strip() or not self.revision.strip():
            raise DataUnavailable("MOISTURE_MODIFIER_IDENTITY_AND_SOURCE_REQUIRED")
        if finite(self.factor, "factor", positive=True) > 1.0:
            raise DataUnavailable("MOISTURE_FACTOR_MUST_NOT_EXCEED_ONE")
        if self.moisture_max_fraction <= self.moisture_min_fraction:
            raise DataUnavailable("MOISTURE_RANGE_INVALID")

    @property
    def identity(self) -> str:
        return f"{self.modifier_id}@{self.revision}"

    def apply(self, value: float, *, moisture_fraction: float) -> float:
        base = finite(value, "value", positive=True)
        moisture = finite(moisture_fraction, "moisture_fraction")
        if not self.moisture_min_fraction <= moisture <= self.moisture_max_fraction:
            raise DataUnavailable(
                f"{self.identity}_MOISTURE_OUT_OF_VALIDITY:"
                f"{moisture}<>{self.moisture_min_fraction}..{self.moisture_max_fraction}"
            )
        return base * self.factor


@dataclass(frozen=True, slots=True)
class PlyArchitecture:
    """Fibre/matrix architecture with revisioned material and allowables."""

    fiber: str
    matrix: str
    material: MaterialRevision
    strength: PlyStrength
    process: str = ""
    provenance: str = ""

    def __post_init__(self) -> None:
        if self.material.symmetry not in _PLY_SYMMETRIES:
            raise DataUnavailable(
                f"PLY_MATERIAL_MUST_BE_ORTHOTROPIC:{self.material.identity}"
            )
        if not self.fiber.strip() or not self.matrix.strip():
            raise DataUnavailable("PLY_FIBER_AND_MATRIX_REQUIRED")
        if self.strength.material_digest != material_digest(self.material):
            raise DataUnavailable(
                "PLY_STRENGTH_DIGEST_MISMATCH:"
                f"{self.strength.material_digest}!=material {self.material.identity}"
            )

    @property
    def identity(self) -> str:
        return f"{self.material.identity}[{self.fiber}/{self.matrix}]"

    def layer(self, *, angle_deg: float, thickness_m: float) -> Ply:
        return Ply(material=self.material, angle_deg=angle_deg, thickness_m=thickness_m)


@dataclass(frozen=True, slots=True)
class PlyConstants:
    """Evaluated orthotropic constants of one ply layer at a temperature."""

    material_digest: str
    material_identity: str
    angle_deg: float
    thickness_m: float
    e1_pa: float
    e2_pa: float
    nu12: float
    g12_pa: float
    g13_pa: float
    g23_pa: float
    alpha1_1_k: float
    alpha2_1_k: float
    density_kg_m3: float
    has_thermal_expansion: bool
    temperature_k: float | None
    assumptions: tuple[str, ...]
    provenance: Provenance


def ply_constants(ply: Ply, *, temperature_k: float | None = None) -> PlyConstants:
    """Evaluate one ply layer's orthotropic constants, failing closed if absent."""

    material = ply.material
    assumptions: list[str] = []
    e1 = _require(
        _prop(material, "youngs_modulus", temperature_k=temperature_k),
        "youngs_modulus",
        material,
    )
    e2 = _prop(material, "youngs_modulus_transverse", temperature_k=temperature_k)
    if e2 is None:
        e2 = _prop(material, "youngs_modulus_2", temperature_k=temperature_k)
    e2 = _require(e2, "youngs_modulus_transverse", material)
    nu12 = _require(
        _prop(material, "poisson_ratio", temperature_k=temperature_k),
        "poisson_ratio",
        material,
    )
    g12 = _require(
        _prop(material, "shear_modulus", temperature_k=temperature_k),
        "shear_modulus",
        material,
    )
    if e1 <= 0 or e2 <= 0 or g12 <= 0:
        raise DataUnavailable("PLY_MODULI_MUST_BE_POSITIVE")
    g13 = _prop(material, "shear_modulus_13", temperature_k=temperature_k)
    if g13 is None:
        g13 = g12
        assumptions.append("transverse shear modulus G13 defaulted to in-plane G12")
    g23 = _prop(material, "shear_modulus_23", temperature_k=temperature_k)
    if g23 is None:
        g23 = g12
        assumptions.append("transverse shear modulus G23 defaulted to in-plane G12")
    alpha1 = _prop(material, "thermal_expansion", temperature_k=temperature_k)
    has_thermal = alpha1 is not None
    if alpha1 is None:
        alpha1 = 0.0
        assumptions.append("longitudinal CTE unavailable; treated as zero for this layer")
    alpha2 = _prop(material, "thermal_expansion_2", temperature_k=temperature_k)
    if alpha2 is None:
        alpha2 = alpha1
        assumptions.append("transverse CTE defaulted to longitudinal CTE (declared assumption)")
    density = _prop(material, "density", temperature_k=temperature_k)
    if density is None:
        density = 0.0
        assumptions.append("density unavailable; mass properties will fail closed")
    provenance = analytical_provenance(
        "ply-constant-evaluation",
        {
            "material": material.identity,
            "materialDigest": material_digest(material),
            "angleDeg": ply.angle_deg,
            "thicknessM": ply.thickness_m,
            "temperatureK": temperature_k,
        },
        assumptions=tuple(assumptions),
    )
    return PlyConstants(
        material_digest=material_digest(material),
        material_identity=material.identity,
        angle_deg=ply.angle_deg,
        thickness_m=ply.thickness_m,
        e1_pa=e1,
        e2_pa=e2,
        nu12=nu12,
        g12_pa=g12,
        g13_pa=g13,
        g23_pa=g23,
        alpha1_1_k=alpha1,
        alpha2_1_k=alpha2,
        density_kg_m3=density,
        has_thermal_expansion=has_thermal,
        temperature_k=temperature_k,
        assumptions=tuple(assumptions),
        provenance=provenance,
    )


@dataclass(frozen=True, slots=True)
class StrengthAssessment:
    """A ply allowables set after temperature/moisture modifiers are applied."""

    base: PlyStrength
    strength: PlyStrength
    temperature_k: float
    moisture_fraction: float | None
    modifiers: tuple[tuple[str, float], ...]
    provenance: Provenance
    validity: Validity

    @property
    def reduction(self) -> float:
        return self.base.x_tension_pa - self.strength.x_tension_pa

    def as_dict(self) -> dict[str, Any]:
        return {
            "baseRevision": self.base.revision,
            "temperatureK": self.temperature_k,
            "moistureFraction": self.moisture_fraction,
            "modifiers": [
                {"id": identity, "factor": factor} for identity, factor in self.modifiers
            ],
            "xTensionPa": self.strength.x_tension_pa,
            "validity": self.validity.as_dict(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
            "software": SOFTWARE_IDENTITY,
            "softwareVersion": SOFTWARE_VERSION,
        }


def apply_environment(
    strength: PlyStrength,
    *,
    temperature_k: float,
    moisture_fraction: float | None = None,
    temperature_modifiers: tuple[DegradationModifier, ...] = (),
    moisture_modifiers: tuple[MoistureModifier, ...] = (),
) -> StrengthAssessment:
    """Apply temperature and moisture knock-downs to a ply allowables set.

    The base allowables' temperature validity is enforced, then every declared
    temperature modifier (in order) and moisture modifier is applied to each
    strength component. An out-of-validity modifier fails closed.
    """

    temperature = finite(temperature_k, "temperature_k", positive=True)
    if not strength.in_temperature_range(temperature):
        raise DataUnavailable(
            f"{strength.identity}_TEMPERATURE_OUT_OF_VALIDITY:"
            f"{temperature}<>{strength.temperature_min_k}..{strength.temperature_max_k}"
        )
    factors: dict[str, float] = {}
    applied: list[tuple[str, float]] = []
    component_names = (
        "x_tension_pa",
        "x_compression_pa",
        "y_tension_pa",
        "y_compression_pa",
        "shear_pa",
    )
    for name in component_names:
        base = strength.value(name)
        assert base is not None
        value = base
        for modifier in temperature_modifiers:
            value = modifier.apply(value, temperature_k=temperature)
            applied.append((modifier.identity, modifier.factor))
        if moisture_fraction is not None:
            for moisture in moisture_modifiers:
                value = moisture.apply(value, moisture_fraction=moisture_fraction)
                applied.append((moisture.identity, moisture.factor))
        factors[name] = value / base
    modified = strength.scaled(
        factors,
        note=(
            "environmentally modified allowables; temperature "
            f"{temperature:.3f} K"
            + (
                ""
                if moisture_fraction is None
                else f", moisture {moisture_fraction:.4f}"
            )
        ),
    )
    provenance = analytical_provenance(
        "ply-environment-modifiers",
        {
            "strength": strength.identity,
            "strengthDigest": strength.material_digest,
            "temperatureK": temperature,
            "moistureFraction": moisture_fraction,
            "modifiers": [
                {"id": identity, "factor": factor} for identity, factor in applied
            ],
        },
        assumptions=(
            "modifiers multiply each allowable in declared order",
            "each modifier applies only within its declared validity band",
            "environmental knock-downs are not an isotropic strength substitution",
        ),
    )
    return StrengthAssessment(
        base=strength,
        strength=modified,
        temperature_k=temperature,
        moisture_fraction=moisture_fraction,
        modifiers=tuple(applied),
        provenance=provenance,
        validity=Validity(
            passed=True,
            checks={"all_modifiers_in_validity": True},
            detail=f"ply-environment:{strength.material_digest[:12]}",
        ),
    )
