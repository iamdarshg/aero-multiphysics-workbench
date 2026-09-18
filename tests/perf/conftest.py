"""Make the perf harness importable from the tiered perf test suite.

``tests/perf`` is intentionally outside the default pytest ``testpaths`` (the
perf suite is tiered and bounded, never part of the normal edit/test loop).
When the directory is collected, this conftest puts ``scripts/perf`` on the
import path so the tests exercise the exact harness the CLI runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PERF_SCRIPTS = _REPO_ROOT / "scripts" / "perf"
if str(_PERF_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_PERF_SCRIPTS))
