"""New block dialog: choose block type before creating."""

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


class NewBlockDialog(QDialog):
    """Dialog for creating a new block (asks for type first)."""

    BLOCK_TYPES = [
        ("Wall", "墙"),
        ("ItemTurret", "物品炮台"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建方块")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Block type
        self._type_combo = QComboBox()
        for type_id, label in self.BLOCK_TYPES:
            self._type_combo.addItem(f"{label} ({type_id})", type_id)
        form.addRow("类型:", self._type_combo)

        # Name
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("my-wall")
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
