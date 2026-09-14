"""Scalar multidisciplinary coupling contracts.

``openmdao_problem`` is the dependency-light fallback/screening solver.
``manifest_coordinator`` is the real OpenMDAO-backed coordinator built from
participant declarations; ``field`` owns spatial field exchange;
``resonance`` generalizes forcing/modal proximity to arbitrary participants.
"""

from .dag import ComputationDAG, ContentCache, NodeResult, NodeSpec
from .field import FieldCoupler, SideSpec, register_mesh, transfer_field
from .manifest_coordinator import (
    CoordinatorCheckpoint,
    CoordinatorPolicy,
    CoordinatorResult,
    CouplingLink,
    IterationRecord,
    ManifestCoordinator,
    ScalarParticipantSpec,
    VariableSpec,
    participant_from_manifest,
)
from .openmdao_problem import (
    CouplingParticipant,
    ScalarCouplingProblem,
    ScalarCouplingResult,
    checkpoint_digest,
)
from .policy import ExpertPolicy, expand_coupling_strength
from .resonance import (
    ForcingSpectrum,
    ModalSpectrum,
    ProximityReport,
    ResonancePolicy,
    ResonanceTrigger,
    check_resonance,
    separation,
)
from .units import convert_value, dimension_of, units_compatible

__all__ = [
    "ComputationDAG",
    "ContentCache",
    "CoordinatorCheckpoint",
    "CoordinatorPolicy",
    "CoordinatorResult",
    "CouplingLink",
    "CouplingParticipant",
    "ExpertPolicy",
    "FieldCoupler",
    "ForcingSpectrum",
    "IterationRecord",
    "ManifestCoordinator",
    "ModalSpectrum",
    "NodeResult",
    "NodeSpec",
    "ProximityReport",
    "ResonancePolicy",
    "ResonanceTrigger",
    "ScalarCouplingProblem",
    "ScalarCouplingResult",
    "ScalarParticipantSpec",
    "SideSpec",
    "VariableSpec",
    "check_resonance",
    "checkpoint_digest",
    "convert_value",
    "dimension_of",
    "expand_coupling_strength",
    "participant_from_manifest",
    "register_mesh",
    "separation",
    "transfer_field",
    "units_compatible",
]
