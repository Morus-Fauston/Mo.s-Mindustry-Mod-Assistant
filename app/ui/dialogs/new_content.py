"""New content dialogs: choose type/subtype before creating."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


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
        hint.setStyleSheet("color: gray; font-size: 11px;")
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
    """Dialog for creating a new block (asks for type first)."""

    BLOCK_TYPES = [
        ("Wall", "墙"),
        ("ItemTurret", "物品炮台"),
        ("PowerTurret", "电力炮台"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建方块")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._type_combo = QComboBox()
        for type_id, label in self.BLOCK_TYPES:
            self._type_combo.addItem(f"{label} ({type_id})", type_id)
        form.addRow("类型:", self._type_combo)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("my-turret")
        hint = QLabel("小写字母、数字、连字符")
        hint.setStyleSheet("color: gray; font-size: 11px;")
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
        """Returns (block_type, name)."""
        return (
            self._type_combo.currentData(),
            self._name_edit.text().strip(),
        )
