"""macOS process-tree RSS probe without a shell.

Counterpart of ``win_rss``: walks the descendant tree with libproc
``proc_listpids(PROC_PPID_ONLY)`` and sums ``pti_resident_size`` from
``proc_pidinfo(PROC_PIDTASKINFO)``. A failure to measure the root process
raises SupervisorError so the supervisor fails closed instead of reading zero.
Descendants that exit between enumeration and sampling are skipped: they no
longer hold memory, and the root measurement still bounds the live tree.
"""

from __future__ import annotations

import ctypes
import ctypes.util
from typing import Any

from aeroworkbench_api.process_supervisor import SupervisorError

_PROC_PIDTASKINFO = 4
_PROC_PPID_ONLY = 6
_MAX_CHILDREN = 4096
_MAX_TREE = 65536


class _ProcTaskInfo(ctypes.Structure):
    """``struct proc_taskinfo`` from <sys/proc_info.h>."""

    _fields_ = [
        ("pti_virtual_size", ctypes.c_uint64),
        ("pti_resident_size", ctypes.c_uint64),
        ("pti_total_user", ctypes.c_uint64),
        ("pti_total_system", ctypes.c_uint64),
        ("pti_threads_user", ctypes.c_uint64),
        ("pti_threads_system", ctypes.c_uint64),
        ("pti_policy", ctypes.c_int32),
        ("pti_faults", ctypes.c_int32),
        ("pti_pageins", ctypes.c_int32),
        ("pti_cow_faults", ctypes.c_int32),
        ("pti_messages_sent", ctypes.c_int32),
        ("pti_messages_received", ctypes.c_int32),
        ("pti_syscalls_mach", ctypes.c_int32),
        ("pti_syscalls_unix", ctypes.c_int32),
        ("pti_csw", ctypes.c_int32),
        ("pti_threadnum", ctypes.c_int32),
        ("pti_numrunning", ctypes.c_int32),
        ("pti_priority", ctypes.c_int32),
    ]


_libproc: Any = None


def _lib() -> Any:
    global _libproc
    if _libproc is None:
        path = ctypes.util.find_library("proc") or "/usr/lib/libproc.dylib"
        try:
            lib = ctypes.CDLL(path, use_errno=True)
        except OSError:
            raise SupervisorError("RSS_MONITOR_UNAVAILABLE") from None
        lib.proc_pidinfo.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        lib.proc_pidinfo.restype = ctypes.c_int
        lib.proc_listpids.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        lib.proc_listpids.restype = ctypes.c_int
        _libproc = lib
    return _libproc


def _resident_bytes(pid: int) -> int | None:
    info = _ProcTaskInfo()
    size = ctypes.sizeof(info)
    written = _lib().proc_pidinfo(pid, _PROC_PIDTASKINFO, 0, ctypes.byref(info), size)
    if written != size:
        return None
    return int(info.pti_resident_size)


def _children(pid: int) -> list[int]:
    buffer = (ctypes.c_int * _MAX_CHILDREN)()
    used = _lib().proc_listpids(
        _PROC_PPID_ONLY, ctypes.c_uint32(pid), buffer, ctypes.sizeof(buffer)
    )
    if used <= 0:
        return []
    count = min(used // ctypes.sizeof(ctypes.c_int), _MAX_CHILDREN)
    return [int(buffer[i]) for i in range(count) if int(buffer[i]) > 0]


def macos_process_tree_rss_mib(pid: int) -> float:
    """Return resident memory of ``pid`` and all descendants in MiB."""

    if not isinstance(pid, int) or pid <= 0:
        raise SupervisorError("RSS_MONITOR_UNAVAILABLE")
    root = _resident_bytes(pid)
    if root is None:
        raise SupervisorError("RSS_MONITOR_UNAVAILABLE")
    total = root
    seen = {pid}
    frontier = _children(pid)
    while frontier:
        child = frontier.pop()
        if child in seen:
            continue
        seen.add(child)
        if len(seen) > _MAX_TREE:
            raise SupervisorError("RSS_MONITOR_UNAVAILABLE")
        resident = _resident_bytes(child)
        if resident is None:
            continue  # exited between enumeration and sampling
        total += resident
        frontier.extend(_children(child))
    return total / (1024.0 * 1024.0)
