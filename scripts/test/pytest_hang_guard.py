"""Hard per-test watchdog for tiered runs (issue #30).

Loaded explicitly by ``scripts/test/tier.mjs`` as ``pytest -p pytest_hang_guard``
with the ``scripts/test`` directory on ``PYTHONPATH``. It arms only when
``AERO_TEST_TIMEOUT_SECONDS`` is a positive float; otherwise it is inert, so a
plain ``pytest`` run is never affected. On timeout it dumps the live traceback
and exits 3 so the tier runner can fail closed with diagnostics.
"""

from __future__ import annotations

import faulthandler
import os
import tempfile
import threading

_TIMEOUT_SECONDS = 0.0
_timer: threading.Timer | None = None
_current = ""
_HANG_EXIT_CODE = 42


def _arm(item_id: str) -> None:
    global _timer, _current
    if _TIMEOUT_SECONDS <= 0:
        return
    _current = item_id
    _timer = threading.Timer(_TIMEOUT_SECONDS, _fire)
    _timer.daemon = True
    _timer.start()


def _cancel() -> None:
    global _timer
    if _timer is not None:
        _timer.cancel()
        _timer = None


def _fire() -> None:
    # pytest captures fd 1/2, so a plain stderr dump is lost when we hard-exit.
    # Write diagnostics to a dedicated file the tier runner echoes.
    path = os.environ.get("AERO_HANG_GUARD_LOG") or os.path.join(
        tempfile.gettempdir(), f"pytest-hang-guard-{os.getpid()}.log"
    )
    try:
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(
                f"[hang-guard] test exceeded {_TIMEOUT_SECONDS:g}s: {_current}\n"
            )
            stream.flush()
            faulthandler.dump_traceback(file=stream)
            stream.flush()
    except OSError:
        pass
    os._exit(_HANG_EXIT_CODE)


def pytest_configure(config) -> None:  # type: ignore[no-untyped-def]
    global _TIMEOUT_SECONDS
    _cancel()
    _TIMEOUT_SECONDS = 0.0
    raw = os.environ.get("AERO_TEST_TIMEOUT_SECONDS", "").strip()
    if raw:
        try:
            value = float(raw)
        except ValueError:
            value = 0.0
        if value > 0:
            _TIMEOUT_SECONDS = value


def pytest_runtest_setup(item) -> None:  # type: ignore[no-untyped-def]
    _arm(item.nodeid)


def pytest_runtest_teardown(item, nextitem) -> None:  # type: ignore[no-untyped-def]
    _cancel()
