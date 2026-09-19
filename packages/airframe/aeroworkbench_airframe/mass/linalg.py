"""Deterministic 3x3 linear algebra for mass-property composition.

Parallel-axis translation, inertia-matrix rotation, and positive-definiteness
checks are pure functions over the AIRFRAME 01 ``Mat3``/``InertiaTensor``
contracts. No mass or geometry value is fabricated here.
"""

from __future__ import annotations

from math import cos, sin

from ..frames import IDENTITY, Mat3, matmul, transpose
from ..state import InertiaTensor
from ..units import Quantity, require_dimension

ROTATION_TOLERANCE = 1e-9


def determinant(matrix: Mat3) -> float:
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def is_orthonormal(matrix: Mat3, *, tolerance: float = ROTATION_TOLERANCE) -> bool:
    """True when ``matrix`` is a proper (determinant +1) orthonormal rotation."""
    product = matmul(matrix, transpose(matrix))
    for row in range(3):
        for column in range(3):
            if abs(product[row][column] - IDENTITY[row][column]) > tolerance:
                return False
    return abs(determinant(matrix) - 1.0) <= tolerance


def axis_rotation(axis: str, angle: Quantity) -> Mat3:
    """Right-handed rotation about a principal axis, mapping into the target frame."""
    require_dimension(angle, "angle", f"axisRotation.{axis}")
    value = angle.value_si
    c, s = cos(value), sin(value)
    if axis == "x":
        return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))
    if axis == "y":
        return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))
    if axis == "z":
        return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))
    raise ValueError(f"UNKNOWN_ROTATION_AXIS:{axis}")


def parallel_axis_matrix(offset: tuple[float, float, float]) -> Mat3:
    """``|r|^2 I - r r^T`` in SI; the parallel-axis term for a unit mass."""
    x, y, z = offset
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    return (
        (yy + zz, -xy, -xz),
        (-xy, xx + zz, -yz),
        (-xz, -yz, xx + yy),
    )


def inertia_matrix(tensor: InertiaTensor) -> Mat3:
    """Full symmetric matrix (SI) with negative products of inertia."""
    ixx = tensor.ixx.value_si
    iyy = tensor.iyy.value_si
    izz = tensor.izz.value_si
    ixy = tensor.ixy.value_si
    ixz = tensor.ixz.value_si
    iyz = tensor.iyz.value_si
    return (
        (ixx, -ixy, -ixz),
        (-ixy, iyy, -iyz),
        (-ixz, -iyz, izz),
    )


def tensor_from_matrix(matrix: Mat3, frame: str) -> InertiaTensor:
    """Rebuild an :class:`InertiaTensor` from a symmetrized SI matrix."""
    ixy = -0.5 * (matrix[0][1] + matrix[1][0])
    ixz = -0.5 * (matrix[0][2] + matrix[2][0])
    iyz = -0.5 * (matrix[1][2] + matrix[2][1])
    return InertiaTensor(
        ixx=Quantity(matrix[0][0], "kg.m2"),
        iyy=Quantity(matrix[1][1], "kg.m2"),
        izz=Quantity(matrix[2][2], "kg.m2"),
        ixy=Quantity(ixy, "kg.m2"),
        ixz=Quantity(ixz, "kg.m2"),
        iyz=Quantity(iyz, "kg.m2"),
        frame=frame,
    )


def leading_principal_minors(matrix: Mat3) -> tuple[float, float, float]:
    first = matrix[0][0]
    second = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    return (first, second, determinant(matrix))


def is_positive_definite(matrix: Mat3, *, tolerance: float = 0.0) -> bool:
    """Sylvester's criterion; every leading principal minor must be positive."""
    return all(minor > tolerance for minor in leading_principal_minors(matrix))
