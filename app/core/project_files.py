"""Read a regular project file through the same verified OS handle.

Path checks alone do not protect the gap before open(). The opened handle's
actual path and identity are checked before exposing bytes and again on exit.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import stat
import sys
from typing import BinaryIO, Iterator


def _handle_path(stream: BinaryIO) -> Path:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        import msvcrt

        final_path = ctypes.WinDLL("kernel32", use_last_error=True).GetFinalPathNameByHandleW
        final_path.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
        final_path.restype = wintypes.DWORD
        handle = msvcrt.get_osfhandle(stream.fileno())
        length = final_path(handle, None, 0, 0)
        if not length:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_unicode_buffer(length + 1)
        written = final_path(handle, buffer, len(buffer), 0)
        if not written or written >= len(buffer):
            raise OSError("无法确认工程文件句柄的实际路径")
        value = buffer.value
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
        return Path(value)
    if sys.platform.startswith("linux"):
        return Path(os.readlink(f"/proc/self/fd/{stream.fileno()}"))
    if sys.platform == "darwin":
        import fcntl

        value = fcntl.fcntl(stream.fileno(), getattr(fcntl, "F_GETPATH", 50), bytes(1024))
        return Path(os.fsdecode(value.split(b"\0", 1)[0]))
    raise OSError("当前平台无法核实工程文件句柄路径")


def _identity(info: os.stat_result) -> tuple:
    # Windows path stat and CRT fstat disagree on ctime (creation/change time).
    # File identity, length and last-write time are comparable on both paths.
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


@contextmanager
def open_project_file(root: Path, path: Path) -> Iterator[BinaryIO]:
    """Fail closed on escaped, replaced, renamed or modified input files.

    This is a bounded single-file read guard, not a multi-file snapshot or a
    write transaction. Internal file links retain their existing semantics.
    """
    root = root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise OSError("读取文件超出工程范围")
    expected = resolved.stat()
    if not stat.S_ISREG(expected.st_mode):
        raise OSError("工程来源不是普通文件")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    try:
        stream = os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise
    with stream:
        def verify() -> None:
            actual = os.fstat(stream.fileno())
            actual_path = _handle_path(stream)
            if (not stat.S_ISREG(actual.st_mode) or not actual_path.is_absolute()
                    or not actual_path.is_relative_to(root) or actual_path != resolved
                    or _identity(actual) != _identity(expected)
                    or path.resolve(strict=True) != resolved
                    or _identity(resolved.stat()) != _identity(expected)):
                raise OSError("工程来源在读取时发生变化，请刷新后重试")

        verify()
        yield stream
        verify()
