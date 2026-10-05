"""Cancel native closing before asking the page asynchronously."""

from __future__ import annotations

import logging
from threading import Lock, Timer
from typing import Callable


def _defer(callback: Callable[[], None]) -> None:
    task = Timer(0.01, callback)
    task.daemon = True
    task.start()


class WindowCloseGuard:
    def __init__(self, notify: Callable[[], None], destroy: Callable[[], None],
                 defer: Callable[[Callable[[], None]], None] = _defer):
        self._notify, self._destroy, self._defer = notify, destroy, defer
        self._ready = False
        self._approved = False
        self._notifying = False
        self._lock = Lock()

    def ready(self) -> None:
        with self._lock:
            self._ready = True

    def on_closing(self) -> bool:
        with self._lock:
            if self._approved or not self._ready:
                return True
            if not self._notifying:
                self._notifying = True
                self._defer(self._send)
        return False

    def _send(self) -> None:
        try:
            self._notify()
        except Exception:
            logging.exception('Could not notify page of native close request')
        finally:
            with self._lock:
                self._notifying = False

    def approve(self) -> None:
        with self._lock:
            if self._approved:
                return
            self._approved = True
        self._defer(self._destroy)
