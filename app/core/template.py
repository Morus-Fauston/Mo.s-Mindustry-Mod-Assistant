"""Template engine: generate minimal runnable content skeletons.

Interface (1 method):
    create(kind, name) -> dict
"""

from __future__ import annotations

from typing import Any

from .metadata import Metadata


class TemplateEngine:
    """Generates minimal content templates from metadata defaults."""

    def __init__(self, metadata: Metadata) -> None:
        self._meta = metadata

    def create(self, kind: str, name: str) -> dict[str, Any]:
        """Create a minimal template for the given content kind.

        kind: 'UnitType' | 'Wall' | 'ItemTurret' | 'Weapon'
        """
        generators = {
            "UnitType": self._unit_template,
            "Wall": self._wall_template,
            "ItemTurret": self._turret_template,
            "Weapon": self._weapon_template,
        }

        generator = generators.get(kind)
        if generator is None:
            raise ValueError(f"Unknown template kind: {kind}")

        return generator(name)

    def _unit_template(self, name: str) -> dict[str, Any]:
        return {
            "type": "UnitType",
            "name": name,
            "health": self._default("UnitType", "health", 100),
            "speed": self._default("UnitType", "speed", 1.0),
            "hitSize": self._default("UnitType", "hitSize", 8),
            "flying": False,
            "weapons": [],
        }

    def _wall_template(self, name: str) -> dict[str, Any]:
        return {
            "type": "Wall",
            "name": name,
            "health": self._default("Wall", "health", 400),
            "size": self._default("Wall", "size", 1),
        }

    def _turret_template(self, name: str) -> dict[str, Any]:
        return {
            "type": "ItemTurret",
            "name": name,
            "health": self._default("ItemTurret", "health", 200),
            "size": self._default("ItemTurret", "size", 1),
            "range": self._default("ItemTurret", "range", 100),
            "reload": self._default("ItemTurret", "reload", 30),
            "ammoTypes": {},
        }

    def _weapon_template(self, name: str) -> dict[str, Any]:
        return {
            "type": "Weapon",
            "name": name,
            "reload": 30,
            "x": 0,
            "y": 0,
            "bullet": {
                "type": "BasicBulletType",
                "damage": 10,
                "speed": 3,
                "lifetime": 40,
            },
        }

    def _default(self, class_name: str, field_name: str, fallback: Any) -> Any:
        """Try to get default from metadata, fall back to hardcoded value.
        
        Note: extractor reads defaults from freshly instantiated objects,
        which gives 0/0.0/false for most fields (game hasn't initialized them).
        Only trust non-zero numeric defaults and non-empty strings.
        """
        try:
            class_def = self._meta.get_class(class_name)
            for f in class_def.fields:
                if f.name == field_name and f.default is not None:
                    # Skip meaningless zero defaults from fresh instantiation
                    if isinstance(f.default, (int, float)) and f.default == 0:
                        return fallback
                    if isinstance(f.default, str) and f.default == "":
                        return fallback
                    return f.default
        except (KeyError, Exception):
            pass
        return fallback
