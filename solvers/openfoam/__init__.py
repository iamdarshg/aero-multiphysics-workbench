"""OpenFOAM case preparation boundary."""

from .adapter import OpenFoamCapability, OpenFoamCase, inspect_openfoam, prepare_case

__all__ = ["OpenFoamCase", "OpenFoamCapability", "inspect_openfoam", "prepare_case"]
