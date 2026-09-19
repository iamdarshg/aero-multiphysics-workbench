"""Sourced, revisioned, validity-bounded material-life curves.

Every curve carries where it came from and the domain (temperature, stress,
stress ratio, stress-intensity range) over which it is valid. Evaluating a
curve outside its domain, or without a required material property, raises
:class:`DataUnavailable` instead of extrapolating an invented life.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log, log10, pi, sqrt

from .validity import DataUnavailable, Validity, finite

__all__ = [
    "CrackGrowthCurve",
    "CreepRuptureCurve",
    "SNCurve",
    "StrainLifeCurve",
]


def _check_monotonic(
    samples: tuple[tuple[float, float], ...], label: str, *, increasing: bool
) -> None:
    if len(samples) < 2:
        raise DataUnavailable(f"{label}_NEEDS_AT_LEAST_TWO_SAMPLES")
    axes = [axis for axis, _ in samples]
    ordered = all(
        (a < b if increasing else a > b) for a, b in zip(axes, axes[1:], strict=False)
    )
    if not ordered:
        direction = "increasing" if increasing else "decreasing"
        raise DataUnavailable(f"{label}_AXES_MUST_BE_STRICTLY_{direction.upper()}")


def _interpolate(
    samples: tuple[tuple[float, float], ...], axis: float, label: str
) -> float:
    if axis < samples[0][0] or axis > samples[-1][0]:
        raise DataUnavailable(f"{label}_OUT_OF_VALIDITY_RANGE")
    for (x0, y0), (x1, y1) in zip(samples, samples[1:], strict=False):
        if x0 <= axis <= x1:
            if x1 == x0:
                return y0
            return y0 + (axis - x0) / (x1 - x0) * (y1 - y0)
    raise DataUnavailable(f"{label}_INTERPOLATION_FAILED")  # pragma: no cover


def _require_temperature(
    temperature_k: float | None, minimum_k: float, maximum_k: float, curve_id: str
) -> float:
    if temperature_k is None:
        raise DataUnavailable(f"{curve_id}_TEMPERATURE_REQUIRED")
    value = finite(temperature_k, "temperature_k", positive=True)
    if value < minimum_k or value > maximum_k:
        raise DataUnavailable(
            f"{curve_id}_TEMPERATURE_OUT_OF_VALIDITY:{value}<>{minimum_k}..{maximum_k}"
        )
    return value


@dataclass(frozen=True, slots=True)
class SNCurve:
    """High-cycle stress-life curve: ``sigma_a = sigma_f' * N**b`` (Basquin)."""

    curve_id: str
    revision: str
    source: str
    fatigue_strength_coefficient_pa: float
    fatigue_strength_exponent: float
    temperature_min_k: float
    temperature_max_k: float
    r_ratio: float = 0.0
    stress_min_pa: float = 0.0
    stress_max_pa: float | None = None
    endurance_limit_pa: float | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.curve_id.strip() or not self.revision.strip() or not self.source.strip():
            raise DataUnavailable("SN_CURVE_IDENTITY_AND_SOURCE_REQUIRED")
        finite(
            self.fatigue_strength_coefficient_pa,
            "fatigue_strength_coefficient_pa",
            positive=True,
        )
        exponent = finite(self.fatigue_strength_exponent, "fatigue_strength_exponent")
        if exponent >= 0.0:
            raise DataUnavailable("SN_EXPONENT_MUST_BE_NEGATIVE")
        if self.temperature_max_k <= self.temperature_min_k:
            raise DataUnavailable("SN_TEMPERATURE_RANGE_INVALID")
        if self.endurance_limit_pa is not None:
            finite(self.endurance_limit_pa, "endurance_limit_pa", positive=True)

    @property
    def identity(self) -> str:
        return f"{self.curve_id}@{self.revision}"

    def life_cycles(self, stress_amplitude_pa: float, *, temperature_k: float) -> float:
        """Cycles to failure at a stress amplitude; fails closed when invalid."""

        amplitude = finite(stress_amplitude_pa, "stress_amplitude_pa", positive=True)
        _require_temperature(
            temperature_k, self.temperature_min_k, self.temperature_max_k, self.curve_id
        )
        if self.stress_max_pa is not None and amplitude > self.stress_max_pa:
            raise DataUnavailable(f"{self.curve_id}_AMPLITUDE_ABOVE_VALIDITY")
        if amplitude < self.stress_min_pa:
            raise DataUnavailable(f"{self.curve_id}_AMPLITUDE_BELOW_VALIDITY")
        if self.endurance_limit_pa is not None and amplitude <= self.endurance_limit_pa:
            return float("inf")
        return float(
            (amplitude / self.fatigue_strength_coefficient_pa)
            ** (1.0 / self.fatigue_strength_exponent)
        )

    def stress_amplitude_pa(self, life_cycles: float) -> float:
        cycles = finite(life_cycles, "life_cycles", positive=True)
        return float(
            self.fatigue_strength_coefficient_pa
            * cycles**self.fatigue_strength_exponent
        )

    def validity(
        self, *, temperature_k: float | None, stress_amplitude_pa: float | None = None
    ) -> Validity:
        checks: dict[str, bool] = {}
        if temperature_k is None:
            checks["temperature_declared"] = False
        else:
            checks["temperature_declared"] = True
            checks["temperature_range"] = (
                self.temperature_min_k <= temperature_k <= self.temperature_max_k
            )
        if stress_amplitude_pa is not None:
            checks["stress_min"] = stress_amplitude_pa >= self.stress_min_pa
            if self.stress_max_pa is not None:
                checks["stress_max"] = stress_amplitude_pa <= self.stress_max_pa
        passed = all(checks.values()) if checks else False
        return Validity(passed, checks, f"sn-curve:{self.identity}")


@dataclass(frozen=True, slots=True)
class StrainLifeCurve:
    """Low-cycle strain-life curve: Coffin-Manson with optional Morrow offset."""

    curve_id: str
    revision: str
    source: str
    fatigue_strength_coefficient_pa: float
    fatigue_strength_exponent: float
    fatigue_ductility_coefficient: float
    fatigue_ductility_exponent: float
    youngs_modulus_pa: float
    temperature_min_k: float
    temperature_max_k: float
    note: str = ""

    def __post_init__(self) -> None:
        if not self.curve_id.strip() or not self.revision.strip() or not self.source.strip():
            raise DataUnavailable("STRAIN_LIFE_IDENTITY_AND_SOURCE_REQUIRED")
        finite(
            self.fatigue_strength_coefficient_pa,
            "fatigue_strength_coefficient_pa",
            positive=True,
        )
        finite(
            self.fatigue_ductility_coefficient,
            "fatigue_ductility_coefficient",
            positive=True,
        )
        finite(self.youngs_modulus_pa, "youngs_modulus_pa", positive=True)
        if self.fatigue_strength_exponent >= 0.0 or self.fatigue_ductility_exponent >= 0.0:
            raise DataUnavailable("STRAIN_LIFE_EXPONENTS_MUST_BE_NEGATIVE")
        if self.temperature_max_k <= self.temperature_min_k:
            raise DataUnavailable("STRAIN_LIFE_TEMPERATURE_RANGE_INVALID")

    @property
    def identity(self) -> str:
        return f"{self.curve_id}@{self.revision}"

    def _elastic_plastic(self, reversals: float, mean_stress_pa: float) -> float:
        elastic = (
            (self.fatigue_strength_coefficient_pa - mean_stress_pa)
            / self.youngs_modulus_pa
            * reversals**self.fatigue_strength_exponent
        )
        plastic = self.fatigue_ductility_coefficient * (
            reversals**self.fatigue_ductility_exponent
        )
        return float(elastic + plastic)

    def strain_amplitude(self, cycles: float, *, mean_stress_pa: float = 0.0) -> float:
        life = finite(cycles, "cycles", positive=True)
        return self._elastic_plastic(2.0 * life, mean_stress_pa)

    def reversals_to_failure(
        self,
        strain_amplitude: float,
        *,
        mean_stress_pa: float = 0.0,
        temperature_k: float,
    ) -> float:
        """Reversals to failure at a total strain amplitude (Morrow mean stress)."""

        amplitude = finite(strain_amplitude, "strain_amplitude", positive=True)
        mean = finite(mean_stress_pa, "mean_stress_pa")
        _require_temperature(
            temperature_k,
            self.temperature_min_k,
            self.temperature_max_k,
            self.curve_id,
        )
        if mean >= self.fatigue_strength_coefficient_pa:
            raise DataUnavailable(f"{self.curve_id}_MEAN_STRESS_EXCEEDS_FATIGUE_STRENGTH")

        def residual(log_reversals: float) -> float:
            return self._elastic_plastic(10.0**log_reversals, mean) - amplitude

        if residual(0.0) < 0.0:
            raise DataUnavailable(f"{self.curve_id}_STRAIN_EXCEEDS_ONE_REVERSAL")
        if residual(30.0) > 0.0:
            raise DataUnavailable(f"{self.curve_id}_STRAIN_BELOW_RESOLVABLE_LIFE")
        low, high = 0.0, 30.0
        for _ in range(200):
            middle = 0.5 * (low + high)
            if residual(middle) > 0.0:
                low = middle
            else:
                high = middle
        return float(10.0 ** (0.5 * (low + high)))

    def cycles_to_failure(
        self, strain_amplitude: float, *, mean_stress_pa: float = 0.0, temperature_k: float
    ) -> float:
        return 0.5 * self.reversals_to_failure(
            strain_amplitude, mean_stress_pa=mean_stress_pa, temperature_k=temperature_k
        )


@dataclass(frozen=True, slots=True)
class CreepRuptureCurve:
    """Larson-Miller creep-rupture curve: ``P = T * (C + log10(t_r))``.

    ``samples`` are ``(stress_pa, lm_parameter)``; stress increases while the
    Larson-Miller parameter decreases (longer life at lower stress). Temperature
    is in kelvin and time in hours.
    """

    curve_id: str
    revision: str
    source: str
    larson_miller_constant: float
    samples: tuple[tuple[float, float], ...]
    temperature_min_k: float
    temperature_max_k: float
    note: str = ""

    def __post_init__(self) -> None:
        if not self.curve_id.strip() or not self.revision.strip() or not self.source.strip():
            raise DataUnavailable("CREEP_CURVE_IDENTITY_AND_SOURCE_REQUIRED")
        finite(self.larson_miller_constant, "larson_miller_constant", positive=True)
        if self.temperature_max_k <= self.temperature_min_k:
            raise DataUnavailable("CREEP_TEMPERATURE_RANGE_INVALID")
        _check_monotonic(self.samples, "CREEP_SAMPLES", increasing=True)
        params = [param for _, param in self.samples]
        if any(a <= b for a, b in zip(params, params[1:], strict=False)):
            raise DataUnavailable("CREEP_LARSON_MILLER_MUST_DECREASE_WITH_STRESS")
        for stress, _ in self.samples:
            finite(stress, "creep_stress_pa", positive=True)

    @property
    def identity(self) -> str:
        return f"{self.curve_id}@{self.revision}"

    def lm_parameter(self, stress_pa: float) -> float:
        stress = finite(stress_pa, "stress_pa", positive=True)
        return _interpolate(self.samples, stress, "CREEP_STRESS")

    def rupture_time_hours(self, stress_pa: float, *, temperature_k: float) -> float:
        temperature = _require_temperature(
            temperature_k, self.temperature_min_k, self.temperature_max_k, self.curve_id
        )
        parameter = self.lm_parameter(stress_pa)
        hours = 10.0 ** (parameter / temperature - self.larson_miller_constant)
        if hours <= 0.0 or hours != hours or hours == float("inf"):
            raise DataUnavailable(f"{self.curve_id}_RUPTURE_TIME_NOT_RESOLVABLE")
        return float(hours)

    def allowable_stress_pa(self, *, temperature_k: float, time_hours: float) -> float:
        temperature = _require_temperature(
            temperature_k, self.temperature_min_k, self.temperature_max_k, self.curve_id
        )
        hours = finite(time_hours, "time_hours", positive=True)
        parameter = temperature * (self.larson_miller_constant + log10(hours))
        inverted = sorted((p, s) for s, p in self.samples)
        if parameter < inverted[0][0] or parameter > inverted[-1][0]:
            raise DataUnavailable(f"{self.curve_id}_LIFE_OUT_OF_VALIDITY")
        return _interpolate(tuple(inverted), parameter, "CREEP_LM_PARAMETER")


@dataclass(frozen=True, slots=True)
class CrackGrowthCurve:
    """Paris crack-growth curve: ``da/dN = C * delta_K**m`` (SI, Pa*m^0.5)."""

    curve_id: str
    revision: str
    source: str
    paris_coefficient: float
    paris_exponent: float
    threshold_delta_k_pa_m05: float
    delta_k_min_pa_m05: float
    delta_k_max_pa_m05: float | None
    fracture_toughness_pa_m05: float | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.curve_id.strip() or not self.revision.strip() or not self.source.strip():
            raise DataUnavailable("CRACK_CURVE_IDENTITY_AND_SOURCE_REQUIRED")
        finite(self.paris_coefficient, "paris_coefficient", positive=True)
        finite(self.paris_exponent, "paris_exponent", positive=True)
        finite(self.threshold_delta_k_pa_m05, "threshold_delta_k_pa_m05", positive=True)
        finite(self.delta_k_min_pa_m05, "delta_k_min_pa_m05", positive=True)
        if self.delta_k_min_pa_m05 < self.threshold_delta_k_pa_m05:
            raise DataUnavailable("CRACK_DELTA_K_MIN_BELOW_THRESHOLD")
        if self.delta_k_max_pa_m05 is not None:
            finite(self.delta_k_max_pa_m05, "delta_k_max_pa_m05", positive=True)
            if self.delta_k_max_pa_m05 <= self.delta_k_min_pa_m05:
                raise DataUnavailable("CRACK_DELTA_K_MAX_NOT_ABOVE_MIN")
        if self.fracture_toughness_pa_m05 is not None:
            finite(self.fracture_toughness_pa_m05, "fracture_toughness_pa_m05", positive=True)

    @property
    def identity(self) -> str:
        return f"{self.curve_id}@{self.revision}"

    def growth_rate_m_per_cycle(self, delta_k_pa_m05: float) -> float:
        delta_k = finite(delta_k_pa_m05, "delta_k_pa_m05", positive=True)
        if delta_k < self.threshold_delta_k_pa_m05:
            raise DataUnavailable(f"{self.curve_id}_BELOW_THRESHOLD")
        if delta_k < self.delta_k_min_pa_m05:
            raise DataUnavailable(f"{self.curve_id}_DELTA_K_BELOW_VALIDITY")
        if self.delta_k_max_pa_m05 is not None and delta_k > self.delta_k_max_pa_m05:
            raise DataUnavailable(f"{self.curve_id}_DELTA_K_ABOVE_VALIDITY")
        return float(self.paris_coefficient * delta_k**self.paris_exponent)

    def critical_crack_length_m(
        self, stress_pa: float, *, geometry_factor: float = 1.0
    ) -> float:
        if self.fracture_toughness_pa_m05 is None:
            raise DataUnavailable(f"{self.curve_id}_FRACTURE_TOUGHNESS_UNDECLARED")
        stress = finite(stress_pa, "stress_pa", positive=True)
        geometry = finite(geometry_factor, "geometry_factor", positive=True)
        return float(
            (self.fracture_toughness_pa_m05 / (geometry * stress)) ** 2 / pi
        )

    def cycles_to_grow(
        self,
        initial_crack_m: float,
        final_crack_m: float,
        stress_range_pa: float,
        *,
        geometry_factor: float = 1.0,
    ) -> float:
        start = finite(initial_crack_m, "initial_crack_m", positive=True)
        final = finite(final_crack_m, "final_crack_m", positive=True)
        stress = finite(stress_range_pa, "stress_range_pa", positive=True)
        geometry = finite(geometry_factor, "geometry_factor", positive=True)
        if final <= start:
            raise DataUnavailable("CRACK_FINAL_LENGTH_MUST_EXCEED_INITIAL")
        beta = self.paris_coefficient * (geometry * stress * sqrt(pi)) ** self.paris_exponent
        exponent = 1.0 - 0.5 * self.paris_exponent
        if abs(exponent) < 1e-9:
            cycles = (1.0 / beta) * log(final / start)
        else:
            cycles = (1.0 / beta) / exponent * (final**exponent - start**exponent)
        if cycles <= 0.0 or cycles != cycles or cycles == float("inf"):
            raise DataUnavailable(f"{self.curve_id}_CYCLES_NOT_RESOLVABLE")
        return float(cycles)
