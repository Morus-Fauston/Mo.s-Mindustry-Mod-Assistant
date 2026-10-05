"""Small JSON boundary exposed to the application's own desktop page."""

from __future__ import annotations

import re
from pathlib import Path
from threading import RLock, BoundedSemaphore
from typing import Any, Callable

from app.core.metadata import Metadata

PROTOCOL_VERSION = 1


class DesktopApi:
    def __init__(self, metadata_dir: Path | str, choose_directory: Callable[[], str | None] | None = None,
                 on_close: Callable[[], None] | None = None, on_close_ready: Callable[[], None] | None = None,
                 *, choose_sprite: Callable[[], str | None] | None = None,
                 reveal_file: Callable[[Path], None] | None = None) -> None:
        self._metadata_dir = Path(metadata_dir)
        self._lock = RLock()
        self._bootstrap: dict[str, Any] | None = None
        self._choose_directory = choose_directory
        self._choose_sprite, self._reveal_file = choose_sprite, reveal_file
        self._workspace = None
        self._admission = BoundedSemaphore(32)
        self._on_close = on_close
        self._on_close_ready = on_close_ready

    def close_ready(self) -> bool:
        """Called only after the page installs its close event listener."""
        if self._on_close_ready is not None:
            self._on_close_ready()
        return True

    def request_result(self, request_id: str) -> dict[str, Any]:
        """Query a timed-out operation without executing it again."""
        if self._workspace is None:
            return {"state": "unknown"}
        return self._workspace.request_result(request_id)

    def request(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Bound waiting callers before entering the serialized workspace."""
        if not self._admission.acquire(blocking=False):
            return {"ok": False, "protocolVersion": PROTOCOL_VERSION,
                    "requestId": envelope.get("requestId") if isinstance(envelope, dict) else None,
                    "sessionId": None,
                    "error": {"code": "BUSY", "message": "操作较多，请等待当前任务结束后重试。"}}
        try:
            with self._lock:
                if self._workspace is None:
                    from app.desktop.workspace import WorkspaceService
                    self._workspace = WorkspaceService(self._metadata_dir, self._choose_directory,
                        choose_sprite=self._choose_sprite, reveal_file=self._reveal_file)
            result = self._workspace.request(envelope)
            if (isinstance(envelope, dict) and envelope.get('action') == 'close_window'
                    and result.get('ok') and result.get('data', {}).get('closeApproved')
                    and self._on_close is not None):
                self._on_close()
            return result
        finally:
            self._admission.release()

    def bootstrap(self, protocol_version: int) -> dict[str, Any]:
        """Read the offline catalogue once; retries cannot create sessions."""
        if type(protocol_version) is not int or protocol_version != PROTOCOL_VERSION:
            return {
                "ok": False, "protocolVersion": PROTOCOL_VERSION,
                "error": {"code": "PROTOCOL_MISMATCH", "message": "界面与程序版本不匹配，请使用同一发行包。"},
            }
        with self._lock:
            if self._bootstrap is None:
                try:
                    metadata = Metadata(self._metadata_dir)
                    manifest = metadata.manifest
                    if not isinstance(manifest, dict):
                        raise ValueError("Metadata manifest must be an object")
                    version = manifest.get("gameVersion")
                    if not isinstance(version, str) or not version.strip():
                        raise ValueError("Metadata game version is missing")
                    for key in ("classes", "instanceCategories"):
                        names = manifest.get(key)
                        if not isinstance(names, list) or any(
                            not isinstance(name, str)
                            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$-]*", name)
                            for name in names
                        ):
                            raise ValueError(f"Invalid metadata {key}")
                    for category in metadata.instance_categories:
                        if not (self._metadata_dir / "instances" / category).is_dir():
                            raise ValueError("Metadata instance directory is missing")
                    self._bootstrap = {
                        "metadata": {
                            "gameVersion": metadata.game_version,
                            "classCount": len(metadata.available_classes),
                            "categories": [
                                {"name": name, "count": len(metadata.list_instances(name))}
                                for name in metadata.instance_categories
                            ],
                        },
                    }
                except (OSError, ValueError):
                    return {
                        "ok": False, "protocolVersion": PROTOCOL_VERSION,
                        "error": {
                            "code": "METADATA_UNAVAILABLE",
                            "message": "无法读取离线元数据，请检查程序资料是否完整后重试。",
                        },
                    }
            return {"ok": True, "protocolVersion": PROTOCOL_VERSION, "data": self._bootstrap}
