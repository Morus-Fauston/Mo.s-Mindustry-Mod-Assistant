"""Widgets library — deep modules for the editor UI.

Each widget is self-contained, exposes a small interface (.value + signals),
and encapsulates a specific editing concern.
"""

from .weapon_array_editor import WeaponArrayEditor
from .bullet_editor import BulletEditor

__all__ = ["WeaponArrayEditor", "BulletEditor"]
