"""Test-only launcher: CDP attaches to the real Windows WebView2 host."""

import sys
import threading
import time
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
port, stop_path = int(sys.argv[1]), Path(sys.argv[2])
missing_metadata = len(sys.argv) > 3 and sys.argv[3] == "missing-metadata"
sys.argv = [sys.argv[0]]

import webview
from app.desktop import main as desktop_main

if missing_metadata:
    desktop_main.metadata_dir = lambda: stop_path.parent / "metadata"

webview.settings["REMOTE_DEBUGGING_PORT"] = port


def watch_stop():
    deadline = time.monotonic() + 120
    while not stop_path.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    for window in tuple(webview.windows):
        window.destroy()


threading.Thread(target=watch_stop, daemon=True).start()
desktop_main.main()
