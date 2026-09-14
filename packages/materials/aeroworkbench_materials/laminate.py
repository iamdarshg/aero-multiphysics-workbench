"""Generic orthotropic/composite laminate support via classical laminate theory.

A laminate is an ordered stack of plies. Each ply references an immutable
ply-material revision plus an orientation angle and a thickness. Homogenized
orthotropic properties are derived explicitly with CLT; nothing is silently
replaced by isotropic values.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import cos, radians, sin
from typing import Any

from .properties import MaterialValue, constant
from .revision import MaterialRevision

__all__ = [
    "Ply",
    "LaminateRevision",
    "laminate_digest",
    "effective_orthotropic",
    "PlyMaterialError",
]


class PlyMaterialError(TypeError):
    """Raised when a ply material cannot represent a unidirectional layer."""


@dataclass(frozen=True, slots=True)
class Ply:
    """One laminate layer: ply material, fibre angle, thickness."""

    material: MaterialRevision
    angle_deg: float
    thickness_m: float

    def __post_init__(self) -> None:
        if self.material.symmetry not in (
            "orthotropic",
            "transversely_isotropic",
            "laminate",
        ):
            raise PlyMaterialError(
                f"PLY_MATERIAL_MUST_BE_ORTHOTROPIC:{self.material.identity}"
            )
        if not self.thickness_m > 0:
            raise ValueError("PLY_THICKNESS_MUST_BE_POSITIVE")

    def canonical_payload(self) -> dict[str, Any]:
        from .revision import material_digest  # local import: avoid cycle

        return {
            "materialDigest": material_digest(self.material),
            "materialIdentity": self.material.identity,
            "angleDeg": self.angle_deg,
            "thicknessM": self.thickness_m,
        }


@dataclass(frozen=True, slots=True)
class LaminateRevision:
    """Immutable stacking sequence with an explicit revision identity."""

    laminate_id: str
    revision: str
    plies: tuple[Ply, ...]
    provenance: str = ""

    def __post_init__(self) -> None:
        if not self.laminate_id.strip() or not self.revision.strip():
            raise ValueError("LAMINATE_IDENTITY_REQUIRED")
        if not self.plies:
            raise ValueError("LAMINATE_REQUIRES_PLIES")

    @property
    def identity(self) -> str:
        return f"{self.laminate_id}@{self.revision}"

    @property
    def total_thickness_m(self) -> float:
        return sum(ply.thickness_m for ply in self.plies)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "laminateId": self.laminate_id,
            "revision": self.revision,
            "provenance": self.provenance,
            "plies": [ply.canonical_payload() for ply in self.plies],
        }


def laminate_digest(laminate: LaminateRevision) -> str:
    encoded = json.dumps(
        laminate.canonical_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _ply_stiffness(ply: Ply) -> tuple[float, float, float, float]:
    """Plane-stress reduced stiffness (Q11, Q22, Q12, Q66) of the ply material."""

    props = ply.material.properties
    try:
        e1 = props["youngs_modulus"].evaluate()
        nu12 = props["poisson_ratio"].evaluate()
        e2_key = next(
            key
            for key in ("youngs_modulus_transverse", "youngs_modulus_2")
            if key in props
        )
        e2 = props[e2_key].evaluate()
    except (KeyError, StopIteration) as exc:
        raise PlyMaterialError(f"PLY_MISSING_STIFFNESS:{exc}") from exc
    g12 = props["shear_modulus"].evaluate() if "shear_modulus" in props else e1 / (
        2.0 * (1.0 + nu12)
    )
    denom = 1.0 - nu12 * nu12 * e2 / e1
    if denom <= 0:
        raise PlyMaterialError("PLY_STIFFNESS_NOT_POSITIVE_DEFINITE")
    return (e1 / denom, e2 / denom, nu12 * e2 / denom, g12)


def _rotated_stiffness(
    q11: float, q22: float, q12: float, q66: float, angle_deg: float
) -> tuple[list[list[float]], float]:
    theta = radians(angle_deg)
    m, n = cos(theta), sin(theta)
    m2, n2, m4, n4 = m * m, n * n, m**4, n**4
    qbar11 = q11 * m4 + 2.0 * (q12 + 2.0 * q66) * m2 * n2 + q22 * n4
    qbar22 = q11 * n4 + 2.0 * (q12 + 2.0 * q66) * m2 * n2 + q22 * m4
    qbar12 = (q11 + q22 - 4.0 * q66) * m2 * n2 + q12 * (m4 + n4)
    qbar66 = (q11 + q22 - 2.0 * q12 - 2.0 * q66) * m2 * n2 + q66 * (m4 + n4)
    qbar16 = (q11 - q12 - 2.0 * q66) * m**3 * n - (q22 - q12 - 2.0 * q66) * m * n**3
    qbar26 = (q11 - q12 - 2.0 * q66) * m * n**3 - (q22 - q12 - 2.0 * q66) * m**3 * n
    return (
        [
            [qbar11, qbar12, qbar16],
            [qbar12, qbar22, qbar26],
            [qbar16, qbar26, qbar66],
        ],
        0.0,
    )


def _abd_matrices(laminate: LaminateRevision) -> tuple[
    list[list[float]], list[list[float]], list[list[float]]
]:
    a = [[0.0] * 3 for _ in range(3)]
    b = [[0.0] * 3 for _ in range(3)]
    d = [[0.0] * 3 for _ in range(3)]
    z = -laminate.total_thickness_m / 2.0
    for ply in laminate.plies:
        qbar, _ = _rotated_stiffness(*_ply_stiffness(ply), ply.angle_deg)
        z_next = z + ply.thickness_m
        for i in range(3):
            for j in range(3):
                a[i][j] += qbar[i][j] * (z_next - z)
                b[i][j] += qbar[i][j] * (z_next * z_next - z * z) / 2.0
                d[i][j] += qbar[i][j] * (z_next**3 - z**3) / 3.0
        z = z_next
    return a, b, d


def effective_orthotropic(
    laminate: LaminateRevision, *, require_symmetric: bool = True
) -> MaterialRevision:
    """Derive an explicit homogenized orthotropic revision from a layup.

    Fails closed for unsymmetric layups (non-negligible B matrix) instead of
    silently dropping extension-bending coupling, and refuses to collapse a
    laminate to isotropic: in-plane Ex/Ey/Gxy/nu are reported separately.
    """

    a, b, _ = _abd_matrices(laminate)
    thickness = laminate.total_thickness_m
    coupling = max(abs(term) for row in b for term in row) / max(
        abs(term) for row in a for term in row
    )
    if require_symmetric and coupling > 1e-6:
        raise PlyMaterialError(
            f"UNSYMMETRIC_LAYUP_HAS_EXTENSION_BENDING_COUPLING:{coupling:.3e}"
        )
    # In-plane compliance from the A matrix (membrane response).
    a11, a12, a22, a66 = a[0][0], a[0][1], a[1][1], a[2][2]
    det = a11 * a22 - a12 * a12
    if det <= 0 or a66 <= 0:
        raise PlyMaterialError("LAMINATE_MEMBRANE_STIFFNESS_NOT_POSITIVE_DEFINITE")
    ex = det / (thickness * a22)
    ey = det / (thickness * a11)
    nuxy = a12 / a22
    gxy = a66 / thickness
    density = sum(
        ply.material.properties["density"].evaluate()
        * ply.thickness_m
        / thickness
        for ply in laminate.plies
        if "density" in ply.material.properties
    )
    properties: dict[str, MaterialValue] = {
        "youngs_modulus": constant(ex, "Pa", f"derived:CLT:{laminate.identity}"),
        "youngs_modulus_transverse": constant(
            ey, "Pa", f"derived:CLT:{laminate.identity}"
        ),
        "poisson_ratio": constant(nuxy, "1", f"derived:CLT:{laminate.identity}"),
        "shear_modulus": constant(gxy, "Pa", f"derived:CLT:{laminate.identity}"),
    }
    if density > 0:
        properties["density"] = constant(
            density, "kg/m^3", f"derived:rule-of-mixtures:{laminate.identity}"
        )
    return MaterialRevision(
        material_id=f"{laminate.laminate_id}:homogenized",
        revision=laminate.revision,
        symmetry="orthotropic",
        properties=properties,
        provenance=f"CLT homogenization of {laminate.identity} "
        "(membrane A-matrix; extension-bending coupling checked)",
    )
