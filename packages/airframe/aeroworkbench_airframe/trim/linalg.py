"""Small typed NumPy boundary for trim linear algebra and mode extraction.

Trim Newton steps and linearized 4-DoF flight-dynamics modes both reduce to
small dense systems. Keeping NumPy in one module keeps the physics pure and
deterministic, and makes a non-finite or non-square request fail closed.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite

import numpy as np
from numpy.typing import NDArray

from .errors import TrimSolverError

FloatMatrix = tuple[tuple[float, ...], ...]


def _as_matrix(matrix: Sequence[Sequence[float]], name: str) -> NDArray[np.float64]:
    if not matrix:
        raise TrimSolverError(f"{name} must be non-empty")
    width = len(matrix[0])
    if width == 0 or any(len(row) != width for row in matrix):
        raise TrimSolverError(f"{name} must be rectangular")
    for row in matrix:
        for value in row:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TrimSolverError(f"{name} entries must be numbers")
            if not isfinite(float(value)):
                raise TrimSolverError(f"{name} entries must be finite")
    return np.asarray(matrix, dtype=np.float64)


def solve_linear(matrix: Sequence[Sequence[float]], rhs: Sequence[float]) -> tuple[float, ...]:
    """Solve ``A x = b`` for a small dense system, failing closed when singular."""

    left = _as_matrix(matrix, "matrix")
    if left.shape[0] != left.shape[1]:
        raise TrimSolverError("matrix must be square")
    vector = np.asarray(rhs, dtype=np.float64)
    if vector.shape[0] != left.shape[0]:
        raise TrimSolverError("rhs length must match matrix")
    for entry in vector:
        if not isfinite(float(entry)):
            raise TrimSolverError("rhs entries must be finite")
    try:
        solution = np.linalg.solve(left, vector)
    except np.linalg.LinAlgError as error:
        raise TrimSolverError("SINGULAR_LINEAR_SYSTEM") from error
    return tuple(float(entry) for entry in solution)


def complex_eigenvalues(matrix: Sequence[Sequence[float]]) -> tuple[complex, ...]:
    """Eigenvalues of a small real square matrix in a deterministic order."""

    array = _as_matrix(matrix, "matrix")
    if array.shape[0] != array.shape[1]:
        raise TrimSolverError("matrix must be square")
    values = np.linalg.eigvals(array)
    ordered = sorted(
        (complex(value) for value in values),
        key=lambda value: (round(value.real, 12), round(value.imag, 12)),
    )
    return tuple(ordered)


__all__ = ["FloatMatrix", "complex_eigenvalues", "solve_linear"]
