"""Scalar multidisciplinary coupling contracts."""

from .openmdao_problem import (
    CouplingParticipant,
    ScalarCouplingProblem,
    ScalarCouplingResult,
    checkpoint_digest,
)

__all__ = [
    "CouplingParticipant", "ScalarCouplingProblem", "ScalarCouplingResult", "checkpoint_digest"
]
