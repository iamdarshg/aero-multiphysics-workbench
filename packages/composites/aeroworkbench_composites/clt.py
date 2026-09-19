"""Canonical laminate definition and classical-laminate-theory analysis.

A laminate is an ordered stack of ply layers plus its declared manufacturing
metadata (symmetry/balance claims, reference surface, local material frame,
region). The content digest distinguishes ply order and orientation. Analysis
derives the full A/B/D matrices, membrane engineering properties, thermal
resultants, and per-ply stresses/strains under combined membrane/bending load.
An unsymmetric stack is never silently reduced: the extension-bending coupling
is reported, and callers that require symmetry get a fail-closed error.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import cos, radians, sin
from typing import Any

from aeroworkbench_core.types import Provenance
from aeroworkbench_materials import LaminateRevision, Ply, laminate_digest, material_digest

from .ply import PlyConstants, ply_constants
from .provenance import analytical_provenance
from .validity import DataUnavailable, Validity, finite

__all__ = [
    "LaminateAnalysis",
    "LaminateDefinition",
    "LaminateLoad",
    "MembraneProperties",
    "PlyResponse",
    "ThermalResultants",
    "abd_from_plies",
    "analyze_laminate",
    "is_balanced",
    "is_symmetric",
    "laminate_definition_digest",
    "ply_qbar",
    "ply_stresses",
    "ply_stresses_for",
]

Matrix3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
Vector3 = tuple[float, float, float]


def _zeros() -> list[list[float]]:
    return [[0.0] * 3 for _ in range(3)]


def _as_matrix3(rows: list[list[float]]) -> Matrix3:
    return (
        (rows[0][0], rows[0][1], rows[0][2]),
        (rows[1][0], rows[1][1], rows[1][2]),
        (rows[2][0], rows[2][1], rows[2][2]),
    )


def _fmt(rows: Matrix3) -> dict[str, list[list[float]]]:
    return {"rows": [list(row) for row in rows]}


def _rotate_q(
    q11: float, q22: float, q12: float, q66: float, angle_deg: float
) -> Matrix3:
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
        (qbar11, qbar12, qbar16),
        (qbar12, qbar22, qbar26),
        (qbar16, qbar26, qbar66),
    )


def ply_qbar(constants: PlyConstants) -> Matrix3:
    """Plane-stress reduced stiffness of a ply rotated into laminate axes."""

    nu21 = constants.nu12 * constants.e2_pa / constants.e1_pa
    denom = 1.0 - constants.nu12 * nu21
    if denom <= 0.0:
        raise DataUnavailable("PLY_STIFFNESS_NOT_POSITIVE_DEFINITE")
    q11 = constants.e1_pa / denom
    q22 = constants.e2_pa / denom
    q12 = constants.nu12 * constants.e2_pa / denom
    return _rotate_q(q11, q22, q12, constants.g12_pa, constants.angle_deg)


def _alpha_vector(constants: PlyConstants) -> Vector3:
    theta = radians(constants.angle_deg)
    m, n = cos(theta), sin(theta)
    a1, a2 = constants.alpha1_1_k, constants.alpha2_1_k
    return (
        m * m * a1 + n * n * a2,
        n * n * a1 + m * m * a2,
        2.0 * m * n * (a1 - a2),
    )


def _matvec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [
        sum(matrix[i][j] * vector[j] for j in range(3)) for i in range(3)
    ]


def _ply_geometry(
    plies: tuple[PlyConstants, ...], *, active: tuple[bool, ...] | None
) -> tuple[float, tuple[float, ...]]:
    thickness = sum(ply.thickness_m for ply in plies)
    half = thickness / 2.0
    interfaces = [-half]
    for ply in plies:
        interfaces.append(interfaces[-1] + ply.thickness_m)
    if active is not None and len(active) != len(plies):
        raise DataUnavailable("ACTIVE_MASK_LENGTH_MISMATCH")
    return thickness, tuple(interfaces)


def abd_from_plies(
    plies: tuple[PlyConstants, ...],
    *,
    active: tuple[bool, ...] | None = None,
) -> tuple[Matrix3, Matrix3, Matrix3, tuple[float, ...]]:
    """Assemble A/B/D from evaluated plies; inactive plies contribute no stiffness.

    The ``active`` mask lets progressive-failure analysis discard failed plies
    while keeping the z-geometry (and therefore total thickness) intact.
    """

    if not plies:
        raise DataUnavailable("LAMINATE_REQUIRES_PLIES")
    _, interfaces = _ply_geometry(plies, active=active)
    a, b, d = _zeros(), _zeros(), _zeros()
    for index, constants in enumerate(plies):
        if active is not None and not active[index]:
            continue
        qbar = ply_qbar(constants)
        z0, z1 = interfaces[index], interfaces[index + 1]
        for i in range(3):
            for j in range(3):
                a[i][j] += qbar[i][j] * (z1 - z0)
                b[i][j] += qbar[i][j] * (z1 * z1 - z0 * z0) / 2.0
                d[i][j] += qbar[i][j] * (z1**3 - z0**3) / 3.0
    return _as_matrix3(a), _as_matrix3(b), _as_matrix3(d), interfaces


def _thermal_resultants(
    plies: tuple[PlyConstants, ...],
    interfaces: tuple[float, ...],
    *,
    delta_temperature_k: float,
) -> tuple[Vector3, Vector3]:
    if delta_temperature_k == 0.0:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    n = [0.0, 0.0, 0.0]
    m = [0.0, 0.0, 0.0]
    for index, constants in enumerate(plies):
        if not constants.has_thermal_expansion:
            raise DataUnavailable(
                "THERMAL_RESULTANTS_REQUIRE_CTE:"
                f"{constants.material_identity}:set delta_temperature_k=0 or source a CTE"
            )
        qbar = ply_qbar(constants)
        alpha = list(_alpha_vector(constants))
        stress = _matvec([list(row) for row in qbar], alpha)
        z0, z1 = interfaces[index], interfaces[index + 1]
        for i in range(3):
            n[i] += stress[i] * delta_temperature_k * (z1 - z0)
            m[i] += stress[i] * delta_temperature_k * (z1 * z1 - z0 * z0) / 2.0
    return (n[0], n[1], n[2]), (m[0], m[1], m[2])


@dataclass(frozen=True, slots=True)
class LaminateDefinition:
    """Laminate stack plus declared manufacturing metadata."""

    laminate: LaminateRevision
    symmetric: bool
    balanced: bool
    reference_surface: str = "mid-surface"
    material_frame_deg: float = 0.0
    region: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.reference_surface.strip():
            raise DataUnavailable("LAMINATE_REFERENCE_SURFACE_REQUIRED")
        finite(self.material_frame_deg, "material_frame_deg")
        if self.symmetric and not is_symmetric(self.laminate):
            raise DataUnavailable(
                f"DECLARED_SYMMETRY_DOES_NOT_HOLD:{self.laminate.identity}"
            )
        if self.balanced and not is_balanced(self.laminate):
            raise DataUnavailable(
                f"DECLARED_BALANCE_DOES_NOT_HOLD:{self.laminate.identity}"
            )

    @property
    def identity(self) -> str:
        return self.laminate.identity

    @property
    def total_thickness_m(self) -> float:
        return self.laminate.total_thickness_m

    @property
    def angles_deg(self) -> tuple[float, ...]:
        return tuple(ply.angle_deg for ply in self.laminate.plies)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "laminateDigest": laminate_digest(self.laminate),
            "laminateIdentity": self.laminate.identity,
            "symmetric": self.symmetric,
            "balanced": self.balanced,
            "referenceSurface": self.reference_surface,
            "materialFrameDeg": self.material_frame_deg,
            "region": self.region,
            "note": self.note,
        }


def laminate_definition_digest(definition: LaminateDefinition) -> str:
    encoded = json.dumps(
        definition.canonical_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _angle_mod_180(angle: float) -> float:
    return angle % 180.0


def _close(a: float, b: float, *, tolerance: float = 1e-6) -> bool:
    return abs(a - b) <= tolerance


def is_symmetric(laminate: LaminateRevision) -> bool:
    """True when ply order, orientation, thickness and material mirror."""

    plies = laminate.plies
    for index in range(len(plies) // 2):
        first = plies[index]
        last = plies[len(plies) - 1 - index]
        if not _close(first.angle_deg, last.angle_deg):
            return False
        if not _close(first.thickness_m, last.thickness_m):
            return False
        if _ply_material_digest(first) != _ply_material_digest(last):
            return False
    return True


def _ply_material_digest(ply: Ply) -> str:
    return material_digest(ply.material)


def is_balanced(laminate: LaminateRevision) -> bool:
    """True when every off-axis +theta ply has a matching -theta ply."""

    counts: dict[float, int] = {}
    for ply in laminate.plies:
        key = round(_angle_mod_180(ply.angle_deg), 6)
        counts[key] = counts.get(key, 0) + 1
    for angle, count in counts.items():
        if _close(angle, 0.0) or _close(angle, 90.0):
            continue
        counterpart = round(_angle_mod_180(180.0 - angle), 6)
        if counts.get(counterpart, 0) != count:
            return False
    return True


@dataclass(frozen=True, slots=True)
class MembraneProperties:
    """In-plane engineering properties derived from the A matrix."""

    ex_pa: float
    ey_pa: float
    gxy_pa: float
    nuxy: float
    density_kg_m3: float

    def units(self) -> dict[str, str]:
        return {
            "ex_pa": "Pa",
            "ey_pa": "Pa",
            "gxy_pa": "Pa",
            "nuxy": "1",
            "density_kg_m3": "kg/m3",
        }

    def as_dict(self) -> dict[str, float]:
        return {
            "exPa": self.ex_pa,
            "eyPa": self.ey_pa,
            "gxyPa": self.gxy_pa,
            "nuxy": self.nuxy,
            "densityKgM3": self.density_kg_m3,
        }


@dataclass(frozen=True, slots=True)
class ThermalResultants:
    """Thermal membrane (N/m) and bending (N) resultants per unit width."""

    n_x_n_m: float
    n_y_n_m: float
    n_xy_n_m: float
    m_x_n: float
    m_y_n: float
    m_xy_n: float
    delta_temperature_k: float

    def units(self) -> dict[str, str]:
        return {
            "n_x_n_m": "N/m",
            "n_y_n_m": "N/m",
            "n_xy_n_m": "N/m",
            "m_x_n": "N*m",
            "m_y_n": "N*m",
            "m_xy_n": "N*m",
            "delta_temperature_k": "K",
        }

    def as_dict(self) -> dict[str, float]:
        return {
            "nXNM": self.n_x_n_m,
            "nYNM": self.n_y_n_m,
            "nXYNM": self.n_xy_n_m,
            "mXN": self.m_x_n,
            "mYN": self.m_y_n,
            "mXYN": self.m_xy_n,
            "deltaTemperatureK": self.delta_temperature_k,
        }


@dataclass(frozen=True, slots=True)
class LaminateLoad:
    """Combined membrane (N/m) and bending (N*m/m = N) resultants."""

    n_x_n_m: float = 0.0
    n_y_n_m: float = 0.0
    n_xy_n_m: float = 0.0
    m_x_n: float = 0.0
    m_y_n: float = 0.0
    m_xy_n: float = 0.0

    def __post_init__(self) -> None:
        for name in ("n_x_n_m", "n_y_n_m", "n_xy_n_m", "m_x_n", "m_y_n", "m_xy_n"):
            finite(getattr(self, name), name)

    def membrane(self) -> Vector3:
        return (self.n_x_n_m, self.n_y_n_m, self.n_xy_n_m)

    def moments(self) -> Vector3:
        return (self.m_x_n, self.m_y_n, self.m_xy_n)

    def units(self) -> dict[str, str]:
        return {
            "n_x_n_m": "N/m",
            "n_y_n_m": "N/m",
            "n_xy_n_m": "N/m",
            "m_x_n": "N*m",
            "m_y_n": "N*m",
            "m_xy_n": "N*m",
        }

    def as_dict(self) -> dict[str, float]:
        return {
            "nXNM": self.n_x_n_m,
            "nYNM": self.n_y_n_m,
            "nXYNM": self.n_xy_n_m,
            "mXN": self.m_x_n,
            "mYN": self.m_y_n,
            "mXYN": self.m_xy_n,
        }


@dataclass(frozen=True, slots=True)
class PlyResponse:
    """Stress/strain of one ply at its mid-surface under a laminate load."""

    ply_index: int
    angle_deg: float
    z_mid_m: float
    sigma_1_pa: float
    sigma_2_pa: float
    tau_12_pa: float
    sigma_x_pa: float
    sigma_y_pa: float
    tau_xy_pa: float
    eps_1: float
    eps_2: float
    gamma_12: float
    eps_x: float
    eps_y: float
    gamma_xy: float
    material_digest: str

    def units(self) -> dict[str, str]:
        return {
            "sigma_1_pa": "Pa",
            "sigma_2_pa": "Pa",
            "tau_12_pa": "Pa",
            "sigma_x_pa": "Pa",
            "sigma_y_pa": "Pa",
            "tau_xy_pa": "Pa",
            "eps_1": "1",
            "eps_2": "1",
            "gamma_12": "1",
            "eps_x": "1",
            "eps_y": "1",
            "gamma_xy": "1",
        }

    def as_dict(self) -> dict[str, float | int | str]:
        return {
            "plyIndex": self.ply_index,
            "angleDeg": self.angle_deg,
            "zMidM": self.z_mid_m,
            "sigma1Pa": self.sigma_1_pa,
            "sigma2Pa": self.sigma_2_pa,
            "tau12Pa": self.tau_12_pa,
            "sigmaXPa": self.sigma_x_pa,
            "sigmaYPa": self.sigma_y_pa,
            "tauXYPa": self.tau_xy_pa,
            "materialDigest": self.material_digest,
        }


@dataclass(frozen=True, slots=True)
class LaminateAnalysis:
    """Full CLT outcome: A/B/D, membrane properties, thermal, per-ply data."""

    laminate_identity: str
    laminate_digest: str
    total_thickness_m: float
    z_interfaces_m: tuple[float, ...]
    a: Matrix3
    b: Matrix3
    d: Matrix3
    membrane: MembraneProperties
    thermal: ThermalResultants
    symmetric: bool
    balanced: bool
    plies: tuple[PlyConstants, ...]
    provenance: Provenance
    validity: Validity

    def abd(self) -> tuple[Matrix3, Matrix3, Matrix3]:
        return self.a, self.b, self.d

    def units(self) -> dict[str, str]:
        return {
            "total_thickness_m": "m",
            "a_n_m": "N/m",
            "b_n": "N",
            "d_n_m": "N*m",
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "laminate": self.laminate_identity,
            "laminateDigest": self.laminate_digest,
            "totalThicknessM": self.total_thickness_m,
            "a": _fmt(self.a),
            "b": _fmt(self.b),
            "d": _fmt(self.d),
            "membrane": self.membrane.as_dict(),
            "thermal": self.thermal.as_dict(),
            "symmetric": self.symmetric,
            "balanced": self.balanced,
            "validity": self.validity.as_dict(),
            "inputsHash": self.provenance.inputs_hash,
            "source": self.provenance.source.value,
        }


def _membrane_from_a(a: Matrix3, thickness: float) -> tuple[float, float, float, float]:
    a11, a12, a22, a66 = a[0][0], a[0][1], a[1][1], a[2][2]
    det = a11 * a22 - a12 * a12
    if det <= 0.0 or a66 <= 0.0:
        raise DataUnavailable("LAMINATE_MEMBRANE_STIFFNESS_NOT_POSITIVE_DEFINITE")
    return (
        det / (thickness * a22),
        det / (thickness * a11),
        a66 / thickness,
        a12 / a22,
    )


def analyze_laminate(
    laminate: LaminateRevision,
    *,
    temperature_k: float | None = None,
    delta_temperature_k: float = 0.0,
    require_symmetric: bool = False,
) -> LaminateAnalysis:
    """Run classical laminate theory over an ordered ply stack."""

    finite(delta_temperature_k, "delta_temperature_k")
    symmetric = is_symmetric(laminate)
    balanced = is_balanced(laminate)
    if require_symmetric and not symmetric:
        raise DataUnavailable(
            "UNSYMMETRIC_LAYUP_REJECTED_FOR_REDUCED_ANALYSIS:" + laminate.identity
        )
    plies = tuple(ply_constants(ply, temperature_k=temperature_k) for ply in laminate.plies)
    thickness, interfaces = _ply_geometry(plies, active=None)
    a, b, d, _ = abd_from_plies(plies)
    ex, ey, gxy, nuxy = _membrane_from_a(a, thickness)
    density = sum(ply.density_kg_m3 * ply.thickness_m for ply in plies) / thickness
    n_thermal, m_thermal = _thermal_resultants(
        plies, interfaces, delta_temperature_k=delta_temperature_k
    )
    thermal = ThermalResultants(
        n_x_n_m=n_thermal[0],
        n_y_n_m=n_thermal[1],
        n_xy_n_m=n_thermal[2],
        m_x_n=m_thermal[0],
        m_y_n=m_thermal[1],
        m_xy_n=m_thermal[2],
        delta_temperature_k=delta_temperature_k,
    )
    assumptions: list[str] = [
        "classical laminate theory: plane stress, Kirchhoff kinematics, perfect bond",
        "ply data evaluated at a single declared temperature unless stated otherwise",
    ]
    for ply in plies:
        assumptions.extend(ply.assumptions)
    assumed = tuple(dict.fromkeys(assumptions))
    provenance = analytical_provenance(
        "classical-laminate-theory",
        {
            "laminate": laminate.identity,
            "laminateDigest": laminate_digest(laminate),
            "temperatureK": temperature_k,
            "deltaTemperatureK": delta_temperature_k,
            "plies": [
                {
                    "materialDigest": ply.material_digest,
                    "angleDeg": ply.angle_deg,
                    "thicknessM": ply.thickness_m,
                }
                for ply in plies
            ],
        },
        assumptions=assumed,
    )
    coupling = max(abs(term) for row in b for term in row) / max(
        1.0, max(abs(term) for row in a for term in row)
    )
    checks = {
        "symmetric": symmetric,
        "balanced": balanced,
        "extension_bending_coupling_present": coupling > 1e-6,
        "membrane_stiffness_positive_definite": True,
    }
    return LaminateAnalysis(
        laminate_identity=laminate.identity,
        laminate_digest=laminate_digest(laminate),
        total_thickness_m=thickness,
        z_interfaces_m=interfaces,
        a=a,
        b=b,
        d=d,
        membrane=MembraneProperties(
            ex_pa=ex, ey_pa=ey, gxy_pa=gxy, nuxy=nuxy, density_kg_m3=density
        ),
        thermal=thermal,
        symmetric=symmetric,
        balanced=balanced,
        plies=plies,
        provenance=provenance,
        validity=Validity(
            passed=True,
            checks=checks,
            detail=f"CLT:{laminate.identity}",
        ),
    )


def _solve6(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    size = 6
    augmented = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda r: abs(augmented[r][column]))
        if abs(augmented[pivot][column]) < 1e-30:
            raise DataUnavailable("LAMINATE_ABD_SINGULAR:load path has no stiffness")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        pivot_value = augmented[column][column]
        augmented[column] = [value / pivot_value for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0.0:
                continue
            augmented[row] = [
                augmented[row][k] - factor * augmented[column][k] for k in range(size + 1)
            ]
    return [augmented[i][size] for i in range(size)]


def _responses(
    plies: tuple[PlyConstants, ...],
    a: Matrix3,
    b: Matrix3,
    d: Matrix3,
    interfaces: tuple[float, ...],
    load: LaminateLoad,
    n_thermal: Vector3,
    m_thermal: Vector3,
) -> tuple[PlyResponse, ...]:
    matrix = [[0.0] * 6 for _ in range(6)]
    for i in range(3):
        for j in range(3):
            matrix[i][j] = a[i][j]
            matrix[i][j + 3] = b[i][j]
            matrix[i + 3][j] = b[i][j]
            matrix[i + 3][j + 3] = d[i][j]
    rhs = [
        load.n_x_n_m - n_thermal[0],
        load.n_y_n_m - n_thermal[1],
        load.n_xy_n_m - n_thermal[2],
        load.m_x_n - m_thermal[0],
        load.m_y_n - m_thermal[1],
        load.m_xy_n - m_thermal[2],
    ]
    solution = _solve6(matrix, rhs)
    eps0 = solution[0:3]
    kappa = solution[3:6]
    responses: list[PlyResponse] = []
    for index, constants in enumerate(plies):
        z_mid = (interfaces[index] + interfaces[index + 1]) / 2.0
        eps_lam = [eps0[i] + z_mid * kappa[i] for i in range(3)]
        theta = radians(constants.angle_deg)
        m, n = cos(theta), sin(theta)
        transform = [
            [m * m, n * n, m * n],
            [n * n, m * m, -m * n],
            [-2.0 * m * n, 2.0 * m * n, m * m - n * n],
        ]
        eps_mat = _matvec(transform, eps_lam)
        q_rows = [list(row) for row in ply_qbar(constants)]
        sigma_mat = _matvec(q_rows, eps_mat)
        sigma_lam = _matvec(q_rows, eps_lam)
        responses.append(
            PlyResponse(
                ply_index=index,
                angle_deg=constants.angle_deg,
                z_mid_m=z_mid,
                sigma_1_pa=sigma_mat[0],
                sigma_2_pa=sigma_mat[1],
                tau_12_pa=sigma_mat[2],
                sigma_x_pa=sigma_lam[0],
                sigma_y_pa=sigma_lam[1],
                tau_xy_pa=sigma_lam[2],
                eps_1=eps_mat[0],
                eps_2=eps_mat[1],
                gamma_12=eps_mat[2],
                eps_x=eps_lam[0],
                eps_y=eps_lam[1],
                gamma_xy=eps_lam[2],
                material_digest=constants.material_digest,
            )
        )
    return tuple(responses)


def ply_stresses(
    analysis: LaminateAnalysis, load: LaminateLoad
) -> tuple[PlyResponse, ...]:
    """Per-ply stress/strain at mid-surface under a combined laminate load."""

    thermal = analysis.thermal
    return _responses(
        analysis.plies,
        analysis.a,
        analysis.b,
        analysis.d,
        analysis.z_interfaces_m,
        load,
        (thermal.n_x_n_m, thermal.n_y_n_m, thermal.n_xy_n_m),
        (thermal.m_x_n, thermal.m_y_n, thermal.m_xy_n),
    )


def ply_stresses_for(
    plies: tuple[PlyConstants, ...],
    load: LaminateLoad,
    *,
    active: tuple[bool, ...] | None = None,
    delta_temperature_k: float = 0.0,
) -> tuple[PlyResponse, ...]:
    """Per-ply response with an optional discarded-ply mask (progressive use)."""

    a, b, d, interfaces = abd_from_plies(plies, active=active)
    n_thermal, m_thermal = _thermal_resultants(
        plies, interfaces, delta_temperature_k=delta_temperature_k
    )
    return _responses(plies, a, b, d, interfaces, load, n_thermal, m_thermal)

