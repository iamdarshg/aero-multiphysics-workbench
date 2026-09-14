"""Minimal mypy stub for the Gmsh Python API."""

from typing import Any

GMSH_API_VERSION: str

def __getattr__(name: str) -> Any: ...
