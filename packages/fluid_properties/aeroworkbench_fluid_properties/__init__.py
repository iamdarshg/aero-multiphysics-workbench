"""Canonical working-fluid, atmosphere, and real-gas property system.

One authoritative property API for every downstream physics component:

* :class:`WorkingFluid` - revisioned fluid/composition identity with provenance.
* :class:`StandardAtmosphere` - layered ISA environment sharing fluid definitions.
* :class:`IdealGasModel` - ideal-gas and ideal-mixture property evaluation.
* :func:`evaluate_real_gas` / :func:`evaluate_equilibrium` - capability-gated
  native backends that fail closed when the library is absent.
* :func:`export_openfoam_fluid` and friends - adapters onto one fluid definition.

Every :class:`PropertyResult` carries source, fidelity, canonical SI unit,
validity range, input hash, software identity, and provenance.
"""

from __future__ import annotations

from .adapters import (
    export_cantera_fluid,
    export_openfoam_fluid,
    export_pycycle_fluid,
    export_reduced_fluid,
)
from .atmosphere import (
    GRAVITY_M_S2,
    ISA_TOP_ALTITUDE_M,
    SEA_LEVEL_PRESSURE_PA,
    SEA_LEVEL_TEMPERATURE_K,
    AtmosphereLayer,
    AtmosphereState,
    StandardAtmosphere,
    WindState,
    build_isa_layers,
    standard_atmosphere,
)
from .canonical import canonical_json, content_digest
from .capabilities import (
    BackendCapability,
    PropertyBackend,
    probe_backend,
    require_backend,
)
from .combustion import (
    EQUILIBRIUM_PROPERTIES,
    EquilibriumBackend,
    evaluate_equilibrium,
    require_equilibrium_capability,
)
from .composition import Composition
from .errors import (
    FluidCapabilityUnavailableError,
    FluidError,
    FluidValidationError,
    FluidValidityError,
)
from .fluid import FluidKind, WorkingFluid, fluid_digest
from .humidity import (
    SATURATION_VALIDITY,
    humid_air_composition,
    saturation_pressure_water_pa,
)
from .ideal_gas import (
    PRESSURE_VALIDITY,
    IdealGasEvaluation,
    IdealGasModel,
    evaluate_ideal_gas,
)
from .library import (
    AIR_TRANSPORT,
    DRY_AIR_COMPOSITION,
    ISA,
    combustion_products_fluid,
    dry_air_fluid,
    fluid_from_payload,
    humid_air_fluid,
    pure_species_fluid,
)
from .property_ids import (
    IDEAL_GAS_FIDELITIES,
    PROPERTY_UNITS,
    PropertyFidelity,
    PropertyId,
    unit_for,
)
from .real_gas import (
    DEFAULT_REAL_GAS_PROPERTIES,
    DERIVATIVE_INPUTS,
    JacobianResult,
    RealGasBackend,
    evaluate_real_gas,
    evaluate_real_gas_jacobian,
)
from .results import (
    SOFTWARE_NAME,
    SOFTWARE_VERSION,
    PropertyResult,
    SoftwareIdentity,
    analytical_provenance,
    native_provenance,
)
from .species import (
    R_UNIVERSAL_J_PER_MOL_K,
    STANDARD_REFERENCE_PRESSURE_PA,
    STANDARD_REFERENCE_TEMPERATURE_K,
    PolynomialCp,
    Species,
    get_species,
    register_species,
    registered_species_ids,
)
from .transport import SutherlandTransport
from .validity import ValidityRange

__all__ = [
    "AIR_TRANSPORT",
    "AtmosphereLayer",
    "AtmosphereState",
    "BackendCapability",
    "Composition",
    "DEFAULT_REAL_GAS_PROPERTIES",
    "DERIVATIVE_INPUTS",
    "DRY_AIR_COMPOSITION",
    "EQUILIBRIUM_PROPERTIES",
    "EquilibriumBackend",
    "FluidCapabilityUnavailableError",
    "FluidError",
    "FluidKind",
    "FluidValidationError",
    "FluidValidityError",
    "GRAVITY_M_S2",
    "IDEAL_GAS_FIDELITIES",
    "ISA",
    "ISA_TOP_ALTITUDE_M",
    "IdealGasEvaluation",
    "IdealGasModel",
    "JacobianResult",
    "PRESSURE_VALIDITY",
    "PROPERTY_UNITS",
    "PolynomialCp",
    "PropertyBackend",
    "PropertyFidelity",
    "PropertyId",
    "PropertyResult",
    "R_UNIVERSAL_J_PER_MOL_K",
    "RealGasBackend",
    "SATURATION_VALIDITY",
    "SEA_LEVEL_PRESSURE_PA",
    "SEA_LEVEL_TEMPERATURE_K",
    "SOFTWARE_NAME",
    "SOFTWARE_VERSION",
    "STANDARD_REFERENCE_PRESSURE_PA",
    "STANDARD_REFERENCE_TEMPERATURE_K",
    "SoftwareIdentity",
    "Species",
    "StandardAtmosphere",
    "SutherlandTransport",
    "ValidityRange",
    "WindState",
    "WorkingFluid",
    "analytical_provenance",
    "build_isa_layers",
    "canonical_json",
    "combustion_products_fluid",
    "content_digest",
    "dry_air_fluid",
    "evaluate_equilibrium",
    "evaluate_ideal_gas",
    "evaluate_real_gas",
    "evaluate_real_gas_jacobian",
    "export_cantera_fluid",
    "export_openfoam_fluid",
    "export_pycycle_fluid",
    "export_reduced_fluid",
    "fluid_digest",
    "fluid_from_payload",
    "get_species",
    "humid_air_composition",
    "humid_air_fluid",
    "native_provenance",
    "probe_backend",
    "pure_species_fluid",
    "register_species",
    "registered_species_ids",
    "require_backend",
    "require_equilibrium_capability",
    "saturation_pressure_water_pa",
    "standard_atmosphere",
    "unit_for",
]
