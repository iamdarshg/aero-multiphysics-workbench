"""Make the workspace importable for standalone perf runs.

The repo's Python import path lives in ``services/api/pyproject.toml`` under
``[tool.pytest.ini_options].pythonpath``. pytest applies it automatically; the
standalone perf harness runs the same way by reading that file instead of
hard-coding package locations, so a new package added to the pytest config is
picked up here too.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def path_entries() -> list[Path]:
    """Resolved import roots: the API dir, the repo root, and every pytest pythonpath entry."""

    root = repo_root()
    api_dir = root / "services" / "api"
    entries: list[Path] = [api_dir, root]
    pyproject = api_dir / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return entries
    match = re.search(r"pythonpath\s*=\s*\[(.*?)\]", text, re.S)
    if not match:
        return entries
    for entry in re.findall(r'"([^"]+)"', match.group(1)):
        entries.append((api_dir / entry).resolve())
    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[Path] = []
    for item in entries:
        key = str(item)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def python_path_string() -> str:
    import os

    return os.pathsep.join(str(item) for item in path_entries())


def ensure_sys_path() -> Path:
    """Insert the workspace import roots into ``sys.path`` and return the repo root."""

    for item in reversed(path_entries()):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)
    return repo_root()
