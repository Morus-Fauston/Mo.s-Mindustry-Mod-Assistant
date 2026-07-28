"""Project management: open/create mod projects.

Interface (2 static methods):
    Project.open(path) -> Project
    Project.create(path, mod_id, name) -> Project
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .content_store import ContentStore


@dataclass
class ModInfo:
    """mod.json metadata."""
    name: str = ""
    display_name: str = ""
    author: str = ""
    description: str = ""
    version: str = "1.0"
    min_game_version: str = "146"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "displayName": self.display_name,
            "author": self.author,
            "description": self.description,
            "version": self.version,
            "minGameVersion": self.min_game_version,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> ModInfo:
        return ModInfo(
            name=d.get("name", ""),
            display_name=d.get("displayName", ""),
            author=d.get("author", ""),
            description=d.get("description", ""),
            version=d.get("version", "1.0"),
            min_game_version=d.get("minGameVersion", "146"),
        )


class Project:
    """A mod project directory with mod.json + content/ + sprites/."""

    def __init__(self, root: Path, mod_info: ModInfo) -> None:
        self.root = root
        self.mod_info = mod_info
        self.contents = ContentStore(root / "content")
        self.sprites_dir = root / "sprites"
        self.is_dirty = False

    @staticmethod
    def open(path: str | Path) -> Project:
        """Open an existing mod project."""
        root = Path(path)
        mod_json = root / "mod.json"
        if not mod_json.exists():
            raise FileNotFoundError(f"No mod.json found in {root}")

        data = json.loads(mod_json.read_text(encoding="utf-8"))
        mod_info = ModInfo.from_dict(data)
        return Project(root, mod_info)

    @staticmethod
    def create(path: str | Path, mod_id: str, display_name: str, author: str = "") -> Project:
        """Create a new mod project skeleton."""
        root = Path(path) / mod_id
        root.mkdir(parents=True, exist_ok=True)

        # Create directory structure
        (root / "content" / "units").mkdir(parents=True, exist_ok=True)
        (root / "content" / "blocks").mkdir(parents=True, exist_ok=True)
        (root / "content" / "weapons").mkdir(parents=True, exist_ok=True)
        (root / "sprites" / "units").mkdir(parents=True, exist_ok=True)
        (root / "sprites" / "blocks").mkdir(parents=True, exist_ok=True)
        (root / "sprites" / "weapons").mkdir(parents=True, exist_ok=True)

        # Write mod.json
        mod_info = ModInfo(name=mod_id, display_name=display_name, author=author)
        mod_json = root / "mod.json"
        mod_json.write_text(
            json.dumps(mod_info.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        return Project(root, mod_info)

    def save_mod_info(self) -> None:
        """Write mod.json back to disk."""
        mod_json = self.root / "mod.json"
        mod_json.write_text(
            json.dumps(self.mod_info.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def sprite_path(self, category: str, name: str, suffix: str = "") -> Path:
        """Get the expected sprite path for a content item."""
        return self.sprites_dir / category / f"{name}{suffix}.png"
