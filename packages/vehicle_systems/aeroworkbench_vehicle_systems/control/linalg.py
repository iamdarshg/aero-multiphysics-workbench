"""Small typed NumPy boundary for control allocation linear algebra.

Allocation reduces to small dense least-squares and square solves. Keeping
NumPy in one module keeps the allocation logic pure and deterministic, and
makes a non-finite or misshapen request fail closed.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite

import numpy as np
from numpy.typing import NDArray

from .errors import AllocationError

__all__ = ["least_squares", "solve_linear"]


def _as_matrix(matrix: Sequence[Sequence[float]], name: str) -> NDArray[np.float64]:
    if not matrix:
        raise AllocationError(f"{name} must be non-empty")
    width = len(matrix[0])
    if width == 0 or any(len(row) != width for row in matrix):
        raise AllocationError(f"{name} must be rectangular")
    for row in matrix:
        for value in row:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise AllocationError(f"{name} entries must be numbers")
            if not isfinite(float(value)):
                raise AllocationError(f"{name} entries must be finite")
    return np.asarray(matrix, dtype=np.float64)


def _as_vector(vector: Sequence[float], name: str) -> NDArray[np.float64]:
    if not vector:
        raise AllocationError(f"{name} must be non-empty")
    for entry in vector:
        if isinstance(entry, bool) or not isinstance(entry, (int, float)):
            raise AllocationError(f"{name} entries must be numbers")
        if not isfinite(float(entry)):
            raise AllocationError(f"{name} entries must be finite")
    return np.asarray(vector, dtype=np.float64)


def solve_linear(matrix: Sequence[Sequence[float]], rhs: Sequence[float]) -> tuple[float, ...]:
    """Solve ``A x = b`` for a small dense system, failing closed when singular."""
    left = _as_matrix(matrix, "matrix")
    if left.shape[0] != left.shape[1]:
        raise AllocationError("matrix must be square")
    vector = _as_vector(rhs, "rhs")
    if vector.shape[0] != left.shape[0]:
        raise AllocationError("rhs length must match matrix")
    try:
        solution = np.linalg.solve(left, vector)
    except np.linalg.LinAlgError as error:
        raise AllocationError("SINGULAR_LINEAR_SYSTEM") from error
    return tuple(float(entry) for entry in solution)


def least_squares(
    matrix: Sequence[Sequence[float]], rhs: Sequence[float]
) -> tuple[tuple[float, ...], int]:
    """Minimum-norm least-squares solution and the matrix rank, fail closed."""
    left = _as_matrix(matrix, "matrix")
    vector = _as_vector(rhs, "rhs")
    if vector.shape[0] != left.shape[0]:
        raise AllocationError("rhs length must match matrix rows")
    solution, _, rank, _ = np.linalg.lstsq(left, vector, rcond=None)
    return tuple(float(entry) for entry in solution), int(rank)
