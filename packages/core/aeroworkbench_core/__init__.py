"""Typed analytical physics primitives for Aero Multiphysics Workbench.

See :mod:`aeroworkbench_core.result_contract`: these are Task-1 analytical
baseline classes, not the durable Task-3 ``ResultEnvelope`` API.
"""

from .result_contract import TASK1_ANALYTICAL_RESULT_CONTRACT

__all__ = ["TASK1_ANALYTICAL_RESULT_CONTRACT"]
