"""Read process identity through Win32; WMI/CIM is not required."""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import os


def identity(pid):
    if os.name != 'nt':
        raise RuntimeError('The portable launcher requires Windows.')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    handle = kernel.OpenProcess(0x1000, False, int(pid))
    if not handle:
        if ctypes.get_last_error() == 5:
            raise PermissionError('Cannot verify recorded process identity.')
        return None
    try:
        size = wintypes.DWORD(32768)
        path = ctypes.create_unicode_buffer(size.value)
        creation, exit_time, cpu_kernel, cpu_user = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            raise OSError(ctypes.get_last_error(), 'Could not read launcher process executable.')
        if not kernel.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time),
                                      ctypes.byref(cpu_kernel), ctypes.byref(cpu_user)):
            raise OSError(ctypes.get_last_error(), 'Could not read launcher process creation time.')
        ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        return {'executable': os.path.normcase(os.path.realpath(path.value)), 'created': ticks}
    finally:
        kernel.CloseHandle(handle)


def matches(live, saved):
    if not live or not saved:
        return False
    if 'created' in saved:
        return live == saved
    # Migrate old launcher records without requiring Get-CimInstance again.
    old_path = saved.get('ExecutablePath')
    stamp = saved.get('CreationDate')
    if not old_path or not isinstance(stamp, str):
        return False
    if os.path.normcase(os.path.realpath(old_path)) != live['executable']:
        return False
    if stamp.startswith('/Date('):
        import re
        found = re.match(r'/Date\((-?\d+)(?:[+-]\d+)?\)/', stamp)
        if not found:
            return False
        saved_ms = int(found.group(1))
    else:
        try:
            saved_ms = int(datetime.fromisoformat(stamp.replace('Z', '+00:00')).astimezone(timezone.utc).timestamp() * 1000)
        except ValueError:
            return False
    live_ms = (live['created'] - 116444736000000000) // 10000
    return live_ms == saved_ms
