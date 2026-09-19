"""Small typed linear-algebra helpers over NumPy for the aeroelastic layer.

Aeroelastic stability and mistuning analyses reduce to eigenvalues of small
real matrices. This module keeps the NumPy boundary in one typed place so the
physics modules stay pure and deterministic, and so an ill-conditioned or
non-real-spectrum request fails closed rather than silently decaying.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite

import numpy as np
from numpy.typing import NDArray

from .errors import AeroelasticError

FloatMatrix = tuple[tuple[float, ...], ...]


def _as_matrix(matrix: Sequence[Sequence[float]], name: str) -> NDArray[np.float64]:
    if not matrix:
        raise AeroelasticError(f"{name} must be non-empty")
    width = len(matrix[0])
    if width == 0 or any(len(row) != width for row in matrix):
        raise AeroelasticError(f"{name} must be rectangular")
    for row in matrix:
        for value in row:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise AeroelasticError(f"{name} entries must be numbers")
            if not isfinite(float(value)):
                raise AeroelasticError(f"{name} entries must be finite")
    return np.asarray(matrix, dtype=np.float64)


def complex_eigenvalues(matrix: Sequence[Sequence[float]]) -> tuple[complex, ...]:
    """Return the eigenvalues of a small real square matrix in a stable order."""

    array = _as_matrix(matrix, "matrix")
    if array.shape[0] != array.shape[1]:
        raise AeroelasticError("matrix must be square")
    values = np.linalg.eigvals(array)
    ordered = sorted(
        (complex(value) for value in values),
        key=lambda value: (round(value.real, 12), round(value.imag, 12)),
    )
    return tuple(ordered)


def solve(matrix: Sequence[Sequence[float]], rhs: Sequence[Sequence[float]]) -> FloatMatrix:
    """Return ``matrix^-1 @ rhs`` for small square systems."""

    left = _as_matrix(matrix, "matrix")
    right = _as_matrix(rhs, "rhs")
    if left.shape[0] != left.shape[1]:
        raise AeroelasticError("matrix must be square")
    if right.shape[0] != left.shape[0]:
        raise AeroelasticError("rhs row count must match matrix")
    result = np.linalg.solve(left, right)
    return tuple(
        tuple(float(entry) for entry in row) for row in result
    )


def symmetric_eigenpairs(
    matrix: Sequence[Sequence[float]],
) -> tuple[tuple[float, ...], tuple[tuple[float, ...], ...]]:
    """Return ascending eigenvalues and orthonormal eigenvectors of a symmetric matrix."""

    array = _as_matrix(matrix, "matrix")
    if array.shape[0] != array.shape[1]:
        raise AeroelasticError("matrix must be square")
    if not np.allclose(array, array.T, atol=1e-12):
        raise AeroelasticError("matrix must be symmetric")
    values, vectors = np.linalg.eigh(array)
    modes = tuple(
        tuple(float(entry) for entry in vectors[:, column])
        for column in range(vectors.shape[1])
    )
    return tuple(float(value) for value in values), modes


__all__ = ["FloatMatrix", "complex_eigenvalues", "solve", "symmetric_eigenpairs"]
