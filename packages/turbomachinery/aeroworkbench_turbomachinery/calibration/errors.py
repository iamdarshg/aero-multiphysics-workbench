"""Calibration-specific errors; every failure fails closed."""

from __future__ import annotations

__all__ = [
    "CalibrationCapabilityUnavailable",
    "CalibrationError",
    "CalibrationInputError",
]


class CalibrationError(Exception):
    """Base error for the turbomachinery calibration subpackage."""


class CalibrationInputError(CalibrationError):
    """Raised when calibration inputs violate their typed contracts."""


class CalibrationCapabilityUnavailable(CalibrationError):
    """Raised when a requested native calibration capability is unavailable."""
