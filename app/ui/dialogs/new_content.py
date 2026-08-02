"""New content dialogs: choose type/subtype before creating."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

# 已有模板的方块类型（与 TemplateEngine.create 的 generators 保持一致）
_BLOCK_TEMPLATES = {
    "Wall", "ItemTurret", "PowerTurret",
    "GenericCrafter", "Drill", "Conveyor", "Battery", "MendProjector",
}


def _load_block_categories() -> list[dict]:
    """读取 block_categories.json 的大类/子类结构。"""
    path = Path(__file__).parent.parent.parent / "config" / "block_categories.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("categories", [])
    except (OSError, json.JSONDecodeError):
        return []


class NewUnitDialog(QDialog):
    """Dialog for creating a new unit (asks for movement subtype)."""

    UNIT_TYPES = [
        ("UnitType", "地面单位 (双足)"),
        ("UnitType-flying", "飞行单位"),
        ("UnitType-tank", "坦克 (履带)"),
        ("UnitType-legs", "多足单位 (蜘蛛)"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建单位")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._type_combo = QComboBox()
        for type_id, label in self.UNIT_TYPES:
            self._type_combo.addItem(label, type_id)
        form.addRow("移动方式:", self._type_combo)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("my-soldier")
        hint = QLabel("小写字母、数字、连字符。如: my-soldier")
        hint.setObjectName("mutedText")
        form.addRow("名称:", self._name_edit)
        form.addRow("", hint)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_result(self) -> tuple[str, str]:
        """Returns (unit_kind, name)."""
        return (
            self._type_combo.currentData(),
            self._name_edit.text().strip(),
        )


class NewBlockDialog(QDialog):
    """Dialog for creating a new block (asks for type first).

    类型列表按 block_categories.json 的大类分组显示，只列出已有模板的类型。
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建方块")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._type_combo = QComboBox()
        self._populate_types()
        form.addRow("类型:", self._type_combo)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("my-turret")
        hint = QLabel("小写字母、数字、连字符")
        hint.setObjectName("mutedText")
        form.addRow("名称:", self._name_edit)
        form.addRow("", hint)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_types(self) -> None:
        """按大类分组填充类型下拉，只列已有模板的类型。"""
        model = QStandardItemModel(self)
        first_real_index = None
        row = 0
        for cat in _load_block_categories():
            # 收集本大类下已有模板的类型
            entries: list[tuple[str, str]] = []
            for sub in cat.get("subCategories", []):
                for t in sub.get("types", []):
                    if t in _BLOCK_TEMPLATES:
                        entries.append((t, sub.get("name", t)))
            if not entries:
                continue
            # 大类分组标题（不可选）
            header = QStandardItem(cat.get("name", ""))
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            model.appendRow(header)
            row += 1
            for type_id, label in entries:
                item = QStandardItem(f"    {label} ({type_id})")
                item.setData(type_id, Qt.ItemDataRole.UserRole)
                model.appendRow(item)
                if first_real_index is None:
                    first_real_index = row
                row += 1
        self._type_combo.setModel(model)
        if first_real_index is not None:
            self._type_combo.setCurrentIndex(first_real_index)

    def get_result(self) -> tuple[str, str]:
        """Returns (block_type, name)."""
        return (
            self._type_combo.currentData(),
            self._name_edit.text().strip(),
        )
