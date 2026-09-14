"""Deterministic geometry contracts for the engineering workbench."""

from .canonical import GeometryModel, Surface, make_edf_geometry, shape_hash

__all__ = ["GeometryModel", "Surface", "make_edf_geometry", "shape_hash"]
