"""Test-only launcher: CDP attaches to the real Windows WebView2 host."""

import sys
import os
import threading
import time
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


def watch_stop():
    deadline = time.monotonic() + 120
    while not stop_path.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    # Test teardown may discard its temporary project even after a failed assertion.
    for guard in close_guards:
        guard.approve()


threading.Thread(target=watch_stop, daemon=True).start()
desktop_main.main()
