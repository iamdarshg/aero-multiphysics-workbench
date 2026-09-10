"""Deterministic geometry contracts for the engineering workbench."""

from .canonical import GeometryModel, make_edf_geometry, shape_hash

__all__ = ["GeometryModel", "make_edf_geometry", "shape_hash"]
