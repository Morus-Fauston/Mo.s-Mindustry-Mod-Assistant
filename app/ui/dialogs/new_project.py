"""New project dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class NewProjectDialog(QDialog):
    """Dialog for creating a new mod project."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建工程")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Mod ID
        self._id_edit = QLineEdit()
        self._id_edit.setPlaceholderText("my-first-mod")
        id_hint = QLabel("小写字母、数字、连字符。如: my-first-mod")
        id_hint.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow("模组 ID:", self._id_edit)
        form.addRow("", id_hint)

        # Display name
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("我的第一个模组")
        form.addRow("模组名称:", self._name_edit)

        # Author
        self._author_edit = QLineEdit()
        self._author_edit.setPlaceholderText("可选")
        form.addRow("作者:", self._author_edit)

        # Path
        path_layout = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("选择保存位置...")
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse)
        path_layout.addWidget(self._path_edit)
        path_layout.addWidget(browse_btn)
        form.addRow("保存位置:", path_layout)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择保存位置")
        if path:
            self._path_edit.setText(path)

    def get_result(self) -> tuple[str, str, str]:
        """Returns (path, mod_id, display_name)."""
        return (
            self._path_edit.text(),
            self._id_edit.text().strip(),
            self._name_edit.text().strip(),
        )
