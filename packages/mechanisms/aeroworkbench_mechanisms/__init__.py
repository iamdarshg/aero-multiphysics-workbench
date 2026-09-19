"""Generic mechanical-interface participants: joints, supports, bearings,
seals, gears, and tribology.

The package provides typed, unit-bearing, deterministic models for the
mechanical interfaces that govern real assemblies. Every result carries
fidelity, validity, SI units, an input hash, software identity, and
provenance; declared limits fail closed; and native tribology/FEA seams are
capability-gated and fail closed when absent.
"""

from .bearings import (
    BearingCatalog,
    BearingGeometry,
    BearingKind,
    BearingResult,
    JournalBearingGeometry,
    evaluate_journal_bearing,
    evaluate_rolling_bearing,
)
from .gears import GearKind, GearPairSpec, GearResult, evaluate_gear_pair
from .joints import (
    BoltedJointSpec,
    JointKind,
    JointResult,
    JointSpec,
    PinJointSpec,
    evaluate_bolted_joint,
    evaluate_joint,
    evaluate_pin_hinge,
)
from .lubrication import (
    LUBRICANTS,
    LubricantSpec,
    LubricantSupply,
    LubricationState,
    dynamic_viscosity_at,
    evaluate_lubrication,
    get_lubricant,
    kinematic_viscosity_at,
)
from .participants import (
    MECHANISM_PARTICIPANTS,
    CapabilityState,
    ComponentParticipant,
    PortSpec,
    mechanism_participants,
    native_capability,
    participant_ids,
    require_native,
)
from .provenance import (
    SOFTWARE_IDENTITY,
    SOFTWARE_VERSION,
    analytical_provenance,
    catalog_provenance,
    native_provenance,
    reduced_provenance,
)
from .seals import SealKind, SealResult, SealSpec, evaluate_seal
from .supports import (
    SixDofProperties,
    SupportKind,
    SupportResult,
    SupportSpec,
    evaluate_support,
)
from .tribology import (
    ContactInterface,
    LubricationRegime,
    NativeTribologyStatus,
    TribologyResult,
    evaluate_contact_friction,
    native_tribology_status,
    solve_native_tribology,
)
from .units import SI_UNITS, UnitError, require_unit
from .validity import (
    CapabilityUnavailable,
    Fidelity,
    LimitExceeded,
    MechanismError,
    Validity,
    finite,
    finite_vector,
)

__all__ = [
    "LUBRICANTS",
    "MECHANISM_PARTICIPANTS",
    "SI_UNITS",
    "SOFTWARE_IDENTITY",
    "SOFTWARE_VERSION",
    "BearingCatalog",
    "BearingGeometry",
    "BearingKind",
    "BearingResult",
    "BoltedJointSpec",
    "CapabilityState",
    "CapabilityUnavailable",
    "ComponentParticipant",
    "ContactInterface",
    "Fidelity",
    "GearKind",
    "GearPairSpec",
    "GearResult",
    "JointKind",
    "JointResult",
    "JointSpec",
    "JournalBearingGeometry",
    "LimitExceeded",
    "LubricantSpec",
    "LubricantSupply",
    "LubricationRegime",
    "LubricationState",
    "MechanismError",
    "NativeTribologyStatus",
    "PinJointSpec",
    "PortSpec",
    "SealKind",
    "SealResult",
    "SealSpec",
    "SixDofProperties",
    "SupportKind",
    "SupportResult",
    "SupportSpec",
    "TribologyResult",
    "UnitError",
    "Validity",
    "analytical_provenance",
    "catalog_provenance",
    "dynamic_viscosity_at",
    "evaluate_bolted_joint",
    "evaluate_contact_friction",
    "evaluate_gear_pair",
    "evaluate_joint",
    "evaluate_journal_bearing",
    "evaluate_lubrication",
    "evaluate_pin_hinge",
    "evaluate_rolling_bearing",
    "evaluate_seal",
    "evaluate_support",
    "finite",
    "finite_vector",
    "get_lubricant",
    "kinematic_viscosity_at",
    "mechanism_participants",
    "native_capability",
    "native_provenance",
    "native_tribology_status",
    "participant_ids",
    "reduced_provenance",
    "require_native",
    "require_unit",
    "solve_native_tribology",
]
