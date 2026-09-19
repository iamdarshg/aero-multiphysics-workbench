"""Pure-species thermophysical definitions with declared validity ranges.

Each species carries a molar mass, a heat-capacity model (constant or a
piecewise polynomial in temperature), a declared validity range, and a source.
A query outside the range raises :class:`FluidValidityError`. The registry is a
small, deterministic, extendable set; large mechanisms and real-gas data are
expected to arrive through capability-gated external libraries instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log

from .errors import FluidValidationError, FluidValidityError
from .validity import ValidityRange

R_UNIVERSAL_J_PER_MOL_K = 8.31446261815324
STANDARD_REFERENCE_TEMPERATURE_K = 298.15
STANDARD_REFERENCE_PRESSURE_PA = 101325.0


@dataclass(frozen=True, slots=True)
class PolynomialCp:
    """A single-temperature-range polynomial for ``cp/R`` as ``sum(a_i T**i)``."""

    coefficients: tuple[float, ...]
    temperature_min_k: float
    temperature_max_k: float
    reference_temperature_k: float = STANDARD_REFERENCE_TEMPERATURE_K

    def __post_init__(self) -> None:
        if not self.coefficients:
            raise FluidValidationError("CP_POLYNOMIAL_REQUIRES_COEFFICIENTS")
        if not all(isfinite(a) for a in self.coefficients):
            raise FluidValidationError("NONFINITE_CP_COEFFICIENT")
        if not (isfinite(self.temperature_min_k) and isfinite(self.temperature_max_k)):
            raise FluidValidationError("NONFINITE_CP_RANGE")
        if self.temperature_min_k <= 0 or self.temperature_min_k >= self.temperature_max_k:
            raise FluidValidationError("INVALID_CP_TEMPERATURE_RANGE")
        if not self.temperature_min_k <= self.reference_temperature_k <= self.temperature_max_k:
            raise FluidValidationError("CP_REFERENCE_TEMPERATURE_OUTSIDE_RANGE")

    def cp_over_r(self, temperature_k: float) -> float:
        """Dimensionless ``cp/R`` at a temperature inside the range."""
        if not self.temperature_min_k <= temperature_k <= self.temperature_max_k:
            raise FluidValidityError(f"CP_POLYNOMIAL_OUT_OF_RANGE:{temperature_k}")
        return sum(a * temperature_k**i for i, a in enumerate(self.coefficients))

    def integral_cp_over_r(self, t0: float, t1: float) -> float:
        """Analytic ``integral of cp/R dT`` from ``t0`` to ``t1``."""
        total = 0.0
        for i, a in enumerate(self.coefficients):
            power = i + 1
            total += a * (t1**power - t0**power) / power
        return total

    def integral_cp_over_r_over_t(self, t0: float, t1: float) -> float:
        """Analytic ``integral of (cp/R)/T dT`` from ``t0`` to ``t1``."""
        total = self.coefficients[0] * log(t1 / t0)
        for i, a in enumerate(self.coefficients[1:], start=1):
            total += a * (t1**i - t0**i) / i
        return total


@dataclass(frozen=True, slots=True)
class Species:
    """A pure species with a molar mass and one or more heat-capacity models."""

    species_id: str
    name: str
    molar_mass_kg_per_mol: float
    constant_cp_j_kg_k: float | None = None
    polynomials: tuple[PolynomialCp, ...] = ()
    temperature_min_k: float | None = None
    temperature_max_k: float | None = None
    source: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not self.species_id.strip() or not self.name.strip():
            raise FluidValidationError("SPECIES_IDENTITY_REQUIRED")
        if not isfinite(self.molar_mass_kg_per_mol) or self.molar_mass_kg_per_mol <= 0:
            raise FluidValidationError(f"INVALID_MOLAR_MASS:{self.species_id}")
        if self.constant_cp_j_kg_k is not None and not (
            isfinite(self.constant_cp_j_kg_k) and self.constant_cp_j_kg_k > 0
        ):
            raise FluidValidationError(f"INVALID_CONSTANT_CP:{self.species_id}")
        if not self.polynomials and self.constant_cp_j_kg_k is None:
            raise FluidValidationError(f"SPECIES_NEEDS_CP_MODEL:{self.species_id}")
        if not self.polynomials and (
            self.temperature_min_k is None or self.temperature_max_k is None
        ):
            raise FluidValidationError(f"CONSTANT_SPECIES_NEEDS_RANGE:{self.species_id}")
        self._validate_polynomials()

    def _validate_polynomials(self) -> None:
        previous_max: float | None = None
        for index, poly in enumerate(self.polynomials):
            if previous_max is not None and poly.temperature_min_k != previous_max:
                raise FluidValidationError(f"NONCONTIGUOUS_CP_RANGES:{self.species_id}")
            if index == 0:
                for piece in self.polynomials:
                    if piece.reference_temperature_k != poly.reference_temperature_k:
                        raise FluidValidationError(
                            f"INCONSISTENT_CP_REFERENCE:{self.species_id}"
                        )
            previous_max = poly.temperature_max_k

    @property
    def r_specific_j_kg_k(self) -> float:
        return R_UNIVERSAL_J_PER_MOL_K / self.molar_mass_kg_per_mol

    def temperature_range(self) -> ValidityRange:
        if self.polynomials:
            return ValidityRange(
                "temperature",
                "K",
                self.polynomials[0].temperature_min_k,
                self.polynomials[-1].temperature_max_k,
            )
        assert self.temperature_min_k is not None and self.temperature_max_k is not None
        return ValidityRange("temperature", "K", self.temperature_min_k, self.temperature_max_k)

    def supports_fidelity(self, *, temperature_dependent: bool) -> bool:
        return bool(self.polynomials) if temperature_dependent else (
            self.constant_cp_j_kg_k is not None
        )

    def cp_j_kg_k(self, temperature_k: float) -> float:
        self.temperature_range().require(temperature_k, label="temperature")
        if self.polynomials:
            for poly in self.polynomials:
                if poly.temperature_min_k <= temperature_k <= poly.temperature_max_k:
                    return poly.cp_over_r(temperature_k) * self.r_specific_j_kg_k
            raise FluidValidityError(f"CP_POLYNOMIAL_GAP:{self.species_id}:{temperature_k}")
        assert self.constant_cp_j_kg_k is not None
        return self.constant_cp_j_kg_k

    def enthalpy_j_kg(self, temperature_k: float) -> float:
        self.temperature_range().require(temperature_k, label="temperature")
        reference = self._reference_temperature_k()
        return self._cp_integral(reference, temperature_k)

    def entropy_j_kg_k(self, temperature_k: float, pressure_pa: float) -> float:
        self.temperature_range().require(temperature_k, label="temperature")
        if not (isfinite(pressure_pa) and pressure_pa > 0):
            raise FluidValidationError(f"INVALID_PRESSURE:{pressure_pa}")
        reference = self._reference_temperature_k()
        ideal = self._cp_over_t_integral(reference, temperature_k)
        reference_pressure = self._reference_pressure_pa()
        return ideal - self.r_specific_j_kg_k * log(pressure_pa / reference_pressure)

    def _reference_temperature_k(self) -> float:
        if self.polynomials:
            return self.polynomials[0].reference_temperature_k
        return STANDARD_REFERENCE_TEMPERATURE_K

    def _reference_pressure_pa(self) -> float:
        return STANDARD_REFERENCE_PRESSURE_PA

    def _cp_integral(self, t0: float, t1: float) -> float:
        if self.polynomials:
            total = 0.0
            for poly in self.polynomials:
                low = max(min(t0, t1), poly.temperature_min_k)
                high = min(max(t0, t1), poly.temperature_max_k)
                if high > low:
                    total += poly.integral_cp_over_r(low, high)
            if t1 < t0:
                total = -total
            return total * self.r_specific_j_kg_k
        assert self.constant_cp_j_kg_k is not None
        return self.constant_cp_j_kg_k * (t1 - t0)

    def _cp_over_t_integral(self, t0: float, t1: float) -> float:
        if self.polynomials:
            total = 0.0
            for poly in self.polynomials:
                low = max(min(t0, t1), poly.temperature_min_k)
                high = min(max(t0, t1), poly.temperature_max_k)
                if high > low:
                    total += poly.integral_cp_over_r_over_t(low, high)
            if t1 < t0:
                total = -total
            return total * self.r_specific_j_kg_k
        assert self.constant_cp_j_kg_k is not None
        return self.constant_cp_j_kg_k * log(t1 / t0)

    def canonical(self) -> dict[str, object]:
        return {
            "speciesId": self.species_id,
            "name": self.name,
            "molarMassKgPerMol": self.molar_mass_kg_per_mol,
            "constantCpJPerKgK": self.constant_cp_j_kg_k,
            "polynomials": [
                {
                    "coefficients": list(poly.coefficients),
                    "temperatureMinK": poly.temperature_min_k,
                    "temperatureMaxK": poly.temperature_max_k,
                    "referenceTemperatureK": poly.reference_temperature_k,
                }
                for poly in self.polynomials
            ],
            "temperatureMinK": self.temperature_min_k,
            "temperatureMaxK": self.temperature_max_k,
            "source": self.source,
            "note": self.note,
        }


def _constant(
    species_id: str,
    name: str,
    molar_mass_g_per_mol: float,
    cp_j_kg_k: float,
    *,
    source: str,
) -> Species:
    return Species(
        species_id=species_id,
        name=name,
        molar_mass_kg_per_mol=molar_mass_g_per_mol * 1e-3,
        constant_cp_j_kg_k=cp_j_kg_k,
        temperature_min_k=100.0,
        temperature_max_k=3000.0,
        source=source,
        note="Constant-cp ideal-gas representation for the analytical fidelity.",
    )


_BUILTIN_SPECIES: tuple[Species, ...] = (
    _constant("air", "Dry air (effective)", 28.9647, 1005.0, source="ISO 2533 / standard air"),
    _constant("n2", "Nitrogen", 28.0134, 1040.0, source="NIST/CODATA constant-cp air species"),
    _constant("o2", "Oxygen", 31.9988, 918.0, source="NIST/CODATA constant-cp air species"),
    _constant("ar", "Argon", 39.948, 520.3, source="NIST/CODATA constant-cp air species"),
    _constant("co2", "Carbon dioxide", 44.0095, 844.0, source="NIST/CODATA constant-cp species"),
    _constant("h2o", "Water vapour", 18.01528, 1860.0, source="NIST/CODATA constant-cp species"),
    _constant("co", "Carbon monoxide", 28.0101, 1040.0, source="NIST/CODATA constant-cp species"),
    _constant("ch4", "Methane", 16.0428, 2220.0, source="NIST/CODATA constant-cp species"),
    _constant("h2", "Hydrogen", 2.01588, 14310.0, source="NIST/CODATA constant-cp species"),
)

_REGISTRY: dict[str, Species] = {species.species_id: species for species in _BUILTIN_SPECIES}


def register_species(species: Species) -> Species:
    """Register or replace a species definition (deterministic, last write wins)."""
    _REGISTRY[species.species_id] = species
    return species


def get_species(species_id: str) -> Species:
    try:
        return _REGISTRY[species_id]
    except KeyError as exc:
        raise FluidValidationError(f"UNKNOWN_SPECIES:{species_id}") from exc


def registered_species_ids() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))
