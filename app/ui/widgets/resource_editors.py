"""Resource and technology reference editor widgets (interface stubs).

These define the public interface for three composite field editors:
- ResourceListEditor: multi-row item/liquid + amount lists (requirements, consumes)
- ResourceSlotEditor: single item/liquid + amount (outputItem, outputLiquid)
- TechRefEditor: string or string[] reference (research)

Full implementation is planned for v0.2.2. Currently these render as
placeholder labels so the UI skeleton is in place.

Interface contract (all three):
    .value        — get/set the field data
    .valueChanged — Signal, emitted on mutation
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ...core.commands import CommandStack


class ResourceListEditor(QWidget):
    """Multi-row resource list: [{item/liquid: str, amount: int, booster?: bool}].

    Used for: requirements, consumes.items, consumes.liquids.

    Args:
        data: Parent data dict.
        path: Dot-path to the list field (e.g. "requirements").
        command_stack: For undo/redo.
        resource_type: "item" or "liquid" — determines dropdown source.
        has_booster: Whether rows can have a 'booster' boolean flag.
    """

    valueChanged = Signal()

    def __init__(
        self,
        data: dict,
        path: str,
        command_stack: CommandStack,
        resource_type: str = "item",
        has_booster: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data = data
        self._path = path
        self._commands = command_stack
        self._resource_type = resource_type
        self._has_booster = has_booster

        # TODO(v0.2.2): Full implementation with add/remove rows,
        # item/liquid dropdowns, amount spinboxes, booster checkboxes.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        placeholder = QLabel(f"[资源列表: {resource_type}] (v0.2.2 实现)")
        placeholder.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(placeholder)

    @property
    def value(self) -> list[dict]:
        val = self._data.get(self._path, [])
        return val if isinstance(val, list) else []

    @value.setter
    def value(self, new_value: list[dict]) -> None:
        self._data[self._path] = new_value
        self.valueChanged.emit()


class ResourceSlotEditor(QWidget):
    """Single resource slot: {item/liquid: str, amount: int}.

    Used for: outputItem, outputLiquid, boostItem.

    Args:
        data: Parent data dict.
        path: Dot-path to the slot field (e.g. "outputItem").
        command_stack: For undo/redo.
        resource_type: "item" or "liquid".
    """

    valueChanged = Signal()

    def __init__(
        self,
        data: dict,
        path: str,
        command_stack: CommandStack,
        resource_type: str = "item",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data = data
        self._path = path
        self._commands = command_stack
        self._resource_type = resource_type

        # TODO(v0.2.2): Full implementation with item/liquid dropdown + amount.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        placeholder = QLabel(f"[资源槽: {resource_type}] (v0.2.2 实现)")
        placeholder.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(placeholder)

    @property
    def value(self) -> dict:
        val = self._data.get(self._path, {})
        return val if isinstance(val, dict) else {}

    @value.setter
    def value(self, new_value: dict) -> None:
        self._data[self._path] = new_value
        self.valueChanged.emit()


class TechRefEditor(QWidget):
    """Technology reference: string or list of strings.

    Used for: research field (prerequisite tech node names).

    Args:
        data: Parent data dict.
        path: Dot-path to the field (e.g. "research").
        command_stack: For undo/redo.
        multi: If True, allows multiple references (list). Otherwise single string.
    """

    valueChanged = Signal()

    def __init__(
        self,
        data: dict,
        path: str,
        command_stack: CommandStack,
        multi: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data = data
        self._path = path
        self._commands = command_stack
        self._multi = multi

        # TODO(v0.2.2): Full implementation with searchable dropdown(s).
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        mode_text = "多选" if multi else "单选"
        placeholder = QLabel(f"[科技引用: {mode_text}] (v0.2.2 实现)")
        placeholder.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(placeholder)

    @property
    def value(self) -> Any:
        return self._data.get(self._path)

    @value.setter
    def value(self, new_value: Any) -> None:
        self._data[self._path] = new_value
        self.valueChanged.emit()
