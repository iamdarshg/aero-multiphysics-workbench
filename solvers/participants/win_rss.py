"""Windows process-tree RSS probe without a shell.

Enumerates the descendant tree via a Toolhelp32 snapshot and sums working
sets via GetProcessMemoryInfo. Any measurement failure raises
SupervisorError so the supervisor fails closed instead of reading zero.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from aeroworkbench_api.process_supervisor import SupervisorError

_TH32CS_SNAPPROCESS = 0x00000002
_PROCESS_QUERY_INFORMATION = 0x0400
_PROCESS_VM_READ = 0x0010


class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class _MemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _snapshot_pids() -> dict[int, int]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    snapshot = kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if snapshot == wintypes.HANDLE(-1).value:  # INVALID_HANDLE_VALUE
        raise SupervisorError("RSS_MONITOR_UNAVAILABLE")
    try:
        entry = _ProcessEntry()
        entry.dwSize = ctypes.sizeof(_ProcessEntry)
        table: dict[int, int] = {}
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            table[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        return table
    finally:
        kernel32.CloseHandle(snapshot)


def _descendants(root: int, table: dict[int, int]) -> list[int]:
    children: dict[int, list[int]] = {}
    for pid, parent in table.items():
        children.setdefault(parent, []).append(pid)
    seen = {root}
    pending = [root]
    while pending:
        current = pending.pop()
        for child in children.get(current, []):
            if child not in seen:
                seen.add(child)
                pending.append(child)
    return sorted(seen)


def _working_set_mib(pid: int) -> float | None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    handle = kernel32.OpenProcess(
        _PROCESS_QUERY_INFORMATION | _PROCESS_VM_READ, False, pid
    )
    if not handle:
        return None
    try:
        counters = _MemoryCounters()
        counters.cb = ctypes.sizeof(_MemoryCounters)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return None
        return float(counters.WorkingSetSize) / 1024.0 / 1024.0
    finally:
        kernel32.CloseHandle(handle)


def windows_process_tree_rss_mib(pid: int) -> float:
    """Aggregate RSS for a root pid plus every live descendant."""

    if not isinstance(pid, int) or pid <= 0:
        raise SupervisorError("RSS_MONITOR_UNAVAILABLE")
    try:
        table = _snapshot_pids()
    except OSError as exc:
        raise SupervisorError("RSS_MONITOR_UNAVAILABLE") from exc
    if pid not in table:
        raise SupervisorError("RSS_MONITOR_UNAVAILABLE")
    total = 0.0
    for member in _descendants(pid, table):
        sample = _working_set_mib(member)
        if sample is None:
            if member == pid:
                raise SupervisorError("RSS_MONITOR_UNAVAILABLE")
            continue
        total += sample
    return total
