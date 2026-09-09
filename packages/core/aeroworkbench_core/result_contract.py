"""Task-1 result contract for the analytical physics baseline.

The concrete result classes in :mod:`aeroworkbench_core.models`, envelope, and
resonance modules are intentionally a lightweight Task-1 analytical baseline.
They are not the canonical durable result representation. Task 3 must define
and integrate a durable ``ResultEnvelope`` carrying units, validity, software
identity/version, and a provenance identifier for persisted and exchanged
results. Until that contract exists, callers must not treat these baseline
classes as a substitute for the Task-3 envelope.
"""

from typing import Final

TASK1_ANALYTICAL_RESULT_CONTRACT: Final[str] = (
    "Task-1 analytical baseline; durable ResultEnvelope with units, validity, "
    "software identity/version, and provenance identifier is deferred to Task 3."
)
