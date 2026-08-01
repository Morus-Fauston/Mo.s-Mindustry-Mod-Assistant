"""Widgets library — deep modules for the editor UI.

Each widget is self-contained, exposes a small interface (.value + signals),
and encapsulates a specific editing concern.
"""

from .weapon_array_editor import WeaponArrayEditor
from .polymorphic_editor import PolymorphicTypeEditor
from .field_widget_factory import create_value_widget

__all__ = ["WeaponArrayEditor", "PolymorphicTypeEditor", "create_value_widget"]
