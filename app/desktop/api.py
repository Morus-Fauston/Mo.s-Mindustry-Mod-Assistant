"""Small JSON boundary exposed to the application's own desktop page."""

from __future__ import annotations

import re
from pathlib import Path
from threading import RLock
from typing import Any

from app.core.metadata import Metadata

PROTOCOL_VERSION = 1


class DesktopApi:
    def __init__(self, metadata_dir: Path | str) -> None:
        self._metadata_dir = Path(metadata_dir)
        self._lock = RLock()
        self._bootstrap: dict[str, Any] | None = None

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
