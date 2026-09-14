"""Minimal mypy stubs for the CadQuery native CAD kernel.

The real package ships no py.typed marker, so without these stubs mypy
follows the import into site-packages and chokes on third-party stub bugs.
Runtime resolution is unaffected (mypy-only search path).
"""

from typing import Any

__version__: str

def __getattr__(name: str) -> Any: ...
