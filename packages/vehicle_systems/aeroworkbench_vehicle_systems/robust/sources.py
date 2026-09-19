"""Adapters from manufacturing and experimental evidence to uncertain inputs.

These helpers turn declarative evidence into typed :class:`UncertainVariable`
or :class:`ModelFormUncertainty` contracts without importing any specific
manufacturing or experiment package. They encode standard, documented
conversions (uniform tolerance band, three-sigma normal, lognormal material
scatter from a coefficient of variation) so a caller can feed #69/#70 evidence
while keeping every assumption provenance-visible.
"""

from __future__ import annotations

from math import log, sqrt

from .contracts import (
    ModelFormUncertainty,
    UncertaintyClass,
    UncertaintySource,
    UncertainVariable,
    VariableProvenance,
)
from .distributions import Distribution, DistributionKind
from .errors import UncertaintyError

__all__ = [
    "calibration_model_form",
    "calibration_variable",
    "material_scatter_variable",
    "tolerance_variable",
]


def tolerance_variable(
    name: str,
    unit: str,
    nominal: float,
    half_width: float,
    *,
    distribution: str = "uniform",
    reference: str = "declared-tolerance",
    revision: str = "1",
) -> UncertainVariable:
    """A manufacturing tolerance as a symmetric uncertain variable.

    ``uniform`` treats the band as a hard interval; ``normal`` interprets the
    half-width as a three-sigma limit. ``half_width`` must be positive.
    """
    if not half_width > 0.0:
        raise UncertaintyError(f"TOLERANCE_HALF_WIDTH_MUST_BE_POSITIVE:{name}")
    if distribution == "uniform":
        dist = Distribution(
            DistributionKind.UNIFORM, (nominal - half_width, nominal + half_width)
        )
        detail = "symmetric tolerance band"
    elif distribution == "normal":
        dist = Distribution(DistributionKind.NORMAL, (nominal, half_width / 3.0))
        detail = "half-width interpreted as three-sigma limit"
    else:
        raise UncertaintyError(f"UNKNOWN_TOLERANCE_DISTRIBUTION:{distribution}")
    return UncertainVariable(
        name=name,
        unit=unit,
        distribution=dist,
        provenance=VariableProvenance(
            UncertaintySource.MANUFACTURING_TOLERANCE, reference, revision, detail
        ),
        uncertainty_class=UncertaintyClass.ALEATORY,
    )


def material_scatter_variable(
    name: str,
    unit: str,
    mean: float,
    coefficient_of_variation: float,
    *,
    reference: str = "material-batch",
    revision: str = "1",
) -> UncertainVariable:
    """Material scatter as a lognormal with the requested mean and CV."""
    if not mean > 0.0:
        raise UncertaintyError(f"MATERIAL_MEAN_MUST_BE_POSITIVE:{name}")
    if not coefficient_of_variation > 0.0:
        raise UncertaintyError(f"MATERIAL_CV_MUST_BE_POSITIVE:{name}")
    sigma_sq = log(1.0 + coefficient_of_variation * coefficient_of_variation)
    sigma = sqrt(sigma_sq)
    mu = log(mean) - 0.5 * sigma_sq
    return UncertainVariable(
        name=name,
        unit=unit,
        distribution=Distribution(DistributionKind.LOGNORMAL, (mu, sigma)),
        provenance=VariableProvenance(
            UncertaintySource.MATERIAL_SCATTER,
            reference,
            revision,
            f"lognormal matched to mean {mean} and CV {coefficient_of_variation}",
        ),
        uncertainty_class=UncertaintyClass.ALEATORY,
    )


def calibration_variable(
    name: str,
    unit: str,
    mean: float,
    std: float,
    *,
    reference: str = "experiment-calibration",
    revision: str = "1",
) -> UncertainVariable:
    """A calibrated parameter as an epistemic (reducible) uncertain variable."""
    return UncertainVariable(
        name=name,
        unit=unit,
        distribution=Distribution(DistributionKind.NORMAL, (mean, std)),
        provenance=VariableProvenance(
            UncertaintySource.EXPERIMENT_CALIBRATION,
            reference,
            revision,
            "posterior of a calibrated parameter",
        ),
        uncertainty_class=UncertaintyClass.EPISTEMIC,
    )


def calibration_model_form(
    fidelity: str,
    response: str,
    bias: float,
    std: float,
    *,
    trusted: bool = False,
    reference: str = "experiment-calibration",
    revision: str = "1",
) -> ModelFormUncertainty:
    """Experimental evidence of model error, kept as model-form discrepancy."""
    return ModelFormUncertainty(
        fidelity=fidelity,
        response=response,
        distribution=Distribution(DistributionKind.NORMAL, (bias, std)),
        provenance=VariableProvenance(
            UncertaintySource.EXPERIMENT_CALIBRATION,
            reference,
            revision,
            "measured model discrepancy; not physical scatter",
        ),
        trusted=trusted,
    )
