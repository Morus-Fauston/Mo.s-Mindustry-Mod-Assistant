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

        kind: 'UnitType' | 'UnitType-flying' | 'UnitType-tank' | 'UnitType-legs'
              | 'Wall' | 'ItemTurret' | 'PowerTurret' | 'Weapon'
        """
        generators = {
            "UnitType": self._unit_ground_template,
            "UnitType-flying": self._unit_flying_template,
            "UnitType-tank": self._unit_tank_template,
            "UnitType-legs": self._unit_legs_template,
            "Wall": self._wall_template,
            "ItemTurret": self._item_turret_template,
            "PowerTurret": self._power_turret_template,
            "Weapon": self._weapon_template,
        }

        generator = generators.get(kind)
        if generator is None:
            raise ValueError(f"Unknown template kind: {kind}")

        return generator(name)

    # ── Unit templates ──────────────────────────────────────────────────

    def _unit_ground_template(self, name: str) -> dict[str, Any]:
        """Standard ground unit (bipedal)."""
        return {
            "type": "UnitType",
            "name": name,
            "health": 150,
            "armor": 0,
            "speed": 1.5,
            "hitSize": 8,
            "flying": False,
            "rotateSpeed": 15,
            "weapons": [],
        }

    def _unit_flying_template(self, name: str) -> dict[str, Any]:
        """Flying unit with engine."""
        return {
            "type": "UnitType",
            "name": name,
            "health": 200,
            "armor": 0,
            "speed": 2.0,
            "hitSize": 10,
            "flying": True,
            "lowAltitude": False,
            "drag": 0.06,
            "accel": 0.08,
            "rotateSpeed": 3,
            "engineOffset": 5,
            "engineSize": 3,
            "weapons": [],
        }

    def _unit_tank_template(self, name: str) -> dict[str, Any]:
        """Tank/tread unit."""
        return {
            "type": "UnitType",
            "name": name,
            "health": 300,
            "armor": 5,
            "speed": 1.0,
            "hitSize": 12,
            "flying": False,
            "omniMovement": False,
            "rotateMoveFirst": True,
            "squareShape": True,
            "rotateSpeed": 3,
            "crushDamage": 1,
            "weapons": [],
        }

    def _unit_legs_template(self, name: str) -> dict[str, Any]:
        """Multi-legged (spider) unit."""
        return {
            "type": "UnitType",
            "name": name,
            "health": 200,
            "armor": 2,
            "speed": 1.2,
            "hitSize": 10,
            "flying": False,
            "legCount": 4,
            "rotateSpeed": 5,
            "weapons": [],
        }

    # ── Block templates ─────────────────────────────────────────────────

    def _wall_template(self, name: str) -> dict[str, Any]:
        return {
            "type": "Wall",
            "name": name,
            "health": 400,
            "size": 1,
            "armor": 0,
            "requirements": [
                {"item": "copper", "amount": 6}
            ],
            "category": "defense",
        }

    def _item_turret_template(self, name: str) -> dict[str, Any]:
        return {
            "type": "ItemTurret",
            "name": name,
            "health": 200,
            "size": 1,
            "range": 100,
            "reload": 30,
            "targetAir": True,
            "targetGround": True,
            "ammoTypes": {
                "copper": {
                    "type": "BasicBulletType",
                    "damage": 10,
                    "speed": 3,
                    "lifetime": 40,
                }
            },
            "requirements": [
                {"item": "copper", "amount": 25}
            ],
            "category": "turret",
        }

    def _power_turret_template(self, name: str) -> dict[str, Any]:
        return {
            "type": "PowerTurret",
            "name": name,
            "health": 250,
            "size": 1,
            "range": 120,
            "reload": 40,
            "targetAir": True,
            "targetGround": True,
            "shootType": {
                "type": "LaserBulletType",
                "damage": 20,
                "length": 120,
                "width": 10,
            },
            "consumes": {
                "power": 2,
            },
            "requirements": [
                {"item": "copper", "amount": 30},
                {"item": "lead", "amount": 15},
            ],
            "category": "turret",
        }

    # ── Weapon template ─────────────────────────────────────────────────

    def _weapon_template(self, name: str) -> dict[str, Any]:
        return {
            "type": "Weapon",
            "name": name,
            "reload": 30,
            "x": 0,
            "y": 0,
            "mirror": True,
            "alternate": True,
            "bullet": {
                "type": "BasicBulletType",
                "damage": 10,
                "speed": 3,
                "lifetime": 40,
                "width": 7,
                "height": 10,
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
