"""Content file storage: read/write/list/delete content JSON files.

Interface (4 methods):
    list(category) -> list[ContentRef]
    get(name) -> ContentData
    save(name, data)
    delete(name)
"""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ContentRef:
    """Lightweight reference to a content file."""
    name: str
    category: str  # units / blocks / weapons
    content_type: str  # UnitType / Wall / ItemTurret / Weapon
    path: Path


@dataclass
class ContentData:
    """Full content data loaded from a JSON file."""
    name: str
    category: str
    data: dict[str, Any] = field(default_factory=dict)
    path: Path | None = None


class ContentStore:
    """Manages content JSON files on disk within a mod project."""

    def __init__(self, content_dir: Path) -> None:
        self._dir = content_dir

    @property
    def content_dir(self) -> Path:
        return self._dir

    def list(self, category: str | None = None) -> list[ContentRef]:
        """List all content files, optionally filtered by category."""
        refs: list[ContentRef] = []
        categories = [category] if category else self._list_categories()

        for cat in categories:
            cat_dir = self._dir / cat
            if not cat_dir.is_dir():
                continue
            for f in sorted(cat_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    content_type = data.get("type", "Unknown")
                    refs.append(ContentRef(
                        name=f.stem,
                        category=cat,
                        content_type=content_type,
                        path=f,
                    ))
                except (json.JSONDecodeError, OSError):
                    continue
        return refs

    def get(self, name: str) -> ContentData:
        """Load a content file by name (searches all categories)."""
        for cat in self._list_categories():
            path = self._dir / cat / f"{name}.json"
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                return ContentData(name=name, category=cat, data=data, path=path)
        raise FileNotFoundError(f"Content not found: {name}")

    def save(self, name: str, data: dict[str, Any], category: str) -> Path:
        """Atomically write content data to disk. Returns the file path."""
        cat_dir = self._dir / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        target = cat_dir / f"{name}.json"

        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(cat_dir), suffix=".tmp", prefix=f".{name}_"
        )
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            shutil.move(tmp_path, str(target))
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

        return target

    def delete(self, name: str) -> None:
        """Delete a content file by name."""
        for cat in self._list_categories():
            path = self._dir / cat / f"{name}.json"
            if path.exists():
                path.unlink()
                return
        raise FileNotFoundError(f"Content not found: {name}")

    def _list_categories(self) -> list[str]:
        if not self._dir.is_dir():
            return []
        return sorted(d.name for d in self._dir.iterdir() if d.is_dir())
