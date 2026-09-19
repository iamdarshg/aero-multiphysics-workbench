"""Deterministic canonical serialization for fluid definitions and results.

Every canonical payload is a plain, JSON-safe structure with integral-float
normalization so that identity digests are stable across hosts and languages.
This mirrors the serialization contract already used by the materials and
turbomachinery packages rather than introducing a new units system.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from math import isfinite
from typing import Any


def canonical_number(value: float) -> int | float:
    """Normalize a finite number: ``-0`` becomes ``0`` and integral floats become ints."""
    number = float(value)
    if not isfinite(number):
        raise ValueError("NONFINITE_CANONICAL_VALUE")
    if number == 0:
        return 0
    if number.is_integer() and abs(number) < 2**53:
        return int(number)
    return number


def normalize_numbers(value: Any) -> Any:
    """Recursively normalize floats so identical definitions serialize identically."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return canonical_number(value)
    if isinstance(value, Mapping):
        return {str(key): normalize_numbers(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_numbers(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Deterministic JSON with sorted keys and no insignificant whitespace."""
    return json.dumps(
        normalize_numbers(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def content_digest(value: Any) -> str:
    """SHA-256 over the canonical JSON encoding."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
