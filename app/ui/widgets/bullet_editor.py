"""Inline bullet editor for weapon forms.

Thin wrapper around PolymorphicTypeEditor (ADR-006) configured for
BulletType subclasses. Field display is driven by field_groups.json.

Interface:
    .value   — get/set the bullet dict
    .valueChanged — Qt Signal
"""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ...core.commands import CommandStack
from .polymorphic_editor import PolymorphicTypeEditor

# ── bullet type choices ─────────────────────────────────────────────────

BULLET_TYPES = [
    "BasicBulletType",
    "LaserBulletType",
    "MissileBulletType",
    "ArtilleryBulletType",
    "FlakBulletType",
]


class BulletEditor(QWidget):
    """Inline bullet sub-form for weapon editing.

    Delegates all rendering to PolymorphicTypeEditor with bullet-specific
    type choices. Maintains backward-compatible interface.
    """

    def __init__(
        self,
        data: dict,
        path: str,
        command_stack: CommandStack,
        parent: QWidget | None = None,
        field_names_zh: dict[str, str] | None = None,
        field_docs: dict[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._editor = PolymorphicTypeEditor(
            data=data,
            path=path,
            type_choices=BULLET_TYPES,
            command_stack=command_stack,
            title="子弹",
            type_label="类型",
        )
        layout.addWidget(self._editor)

    # ── public interface (backward-compatible) ───────────────────────────

    @property
    def value(self) -> dict:
        return self._editor.value

    @value.setter
    def value(self, new_value: dict) -> None:
        self._editor.value = new_value

    @property
    def valueChanged(self):
        return self._editor.valueChanged
