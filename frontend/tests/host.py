"""Test-only launcher: CDP attaches to the real Windows WebView2 host."""

import sys
import os
import threading
import time
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
print(f"MOMA_HOST_PID={os.getpid()}", flush=True)
sys.path.insert(0, str(root))
port, stop_path = int(sys.argv[1]), Path(sys.argv[2])
missing_metadata = len(sys.argv) > 3 and sys.argv[3] == "missing-metadata"
sys.argv = [sys.argv[0]]

import webview
from app.core import paths
from app.desktop import main as desktop_main

paths.user_config_dir = lambda: stop_path.parent / "config"
if missing_metadata:
    desktop_main.metadata_dir = lambda: stop_path.parent / "metadata"

webview.settings["REMOTE_DEBUGGING_PORT"] = port
close_guards = []
original_guard = desktop_main.WindowCloseGuard


def tracked_guard(*args, **kwargs):
    guard = original_guard(*args, **kwargs)
    close_guards.append(guard)
    return guard


desktop_main.WindowCloseGuard = tracked_guard

# Integration-only native page zoom. This uses the actual WebView2 controller,
# never a CDP-emulated device scale. The Windows monitor DPI remains unchanged.
test_zoom = float(os.environ.get("MOMA_TEST_PAGE_ZOOM", "1"))
if test_zoom not in (1, 1.25, 1.5, 2):
    raise ValueError("Unsupported test page zoom")
original_create_window = webview.create_window


def create_test_window(*args, **kwargs):
    window = original_create_window(*args, **kwargs)

    def configure_view():
        from System import Action
        import ctypes

        def apply():
            native = window.native
            # WinForms DeviceDpi may stay at 96 under its compatibility mode.
            # Read the actual monitor scale separately from the WebView zoom.
            user32 = ctypes.windll.user32
            user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            user32.MonitorFromWindow.restype = ctypes.c_void_p
            monitor = user32.MonitorFromWindow(native.Handle.ToInt64(), 2)
            scale = ctypes.c_int()
            get_scale = ctypes.windll.shcore.GetScaleFactorForMonitor
            get_scale.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            get_scale.restype = ctypes.c_long
            if get_scale(monitor, ctypes.byref(scale)) != 0:
                raise RuntimeError("Cannot read test monitor scale")
            native.browser.webview.ZoomFactor = test_zoom
            print("MOMA_NATIVE_VIEW=" + json.dumps({
                "zoomFactor": native.browser.webview.ZoomFactor,
                "deviceDpi": native.DeviceDpi,
                "monitorScalePercent": scale.value,
                "clientWidth": native.ClientSize.Width,
                "clientHeight": native.ClientSize.Height,
            }), flush=True)

        window.native.Invoke(Action(apply))

    window.events.loaded += configure_view
    return window


webview.create_window = create_test_window


def watch_stop():
    deadline = time.monotonic() + 120
    while not stop_path.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    # Test teardown may discard its temporary project even after a failed assertion.
    for guard in close_guards:
        guard.approve()


threading.Thread(target=watch_stop, daemon=True).start()
desktop_main.main()
