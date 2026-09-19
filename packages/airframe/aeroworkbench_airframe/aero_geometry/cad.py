"""Capability-gated native CAD seam for aerodynamic geometry.

The primitives are kernel-independent; real OpenCascade solids are produced
only by the shared parametric CAD layer through the existing regeneration path.
This module only reports and enforces the kernel capability: when the kernel is
unavailable every native entry point fails closed instead of returning a
placeholder.
"""

from __future__ import annotations

from typing import Any

from aeroworkbench_geometry import KernelIdentity, probe_kernel, require_kernel

__all__ = ["KernelIdentity", "probe_cad", "require_cad", "require_kernel"]


def probe_cad() -> KernelIdentity:
    """Report the shared CAD kernel identity without constructing geometry."""

    return probe_kernel()


def require_cad() -> Any:
    """Fail closed when the native CAD kernel is unavailable."""

    return require_kernel()
