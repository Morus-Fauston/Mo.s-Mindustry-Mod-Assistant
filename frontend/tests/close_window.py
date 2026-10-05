"""Send WM_CLOSE only to windows owned by the supplied test process."""

import ctypes
import sys
from ctypes import wintypes

pid = int(sys.argv[1])
user32 = ctypes.windll.user32
callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


@callback_type
def close_owned_window(hwnd, _):
    owner = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
    if owner.value == pid:
        user32.PostMessageW(hwnd, 0x0010, 0, 0)
    return True


user32.EnumWindows(close_owned_window, 0)
