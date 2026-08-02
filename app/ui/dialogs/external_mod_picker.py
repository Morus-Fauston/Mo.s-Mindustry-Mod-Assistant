"""外部 mod 参考选择对话框（F-52）。

导入 mod 文件夹/zip → 列出其 content 分类与文件 → 选择一条作为参考。

入口由 main_window 提供文件路径（QFileDialog 已选好），本对话框只做
「选分类 → 选内容 → 确定」三步。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QSplitter,
    QVBoxLayout,
)

from ...core.external_mod import ExternalMod


class ExternalModPicker(QDialog):
    """选择外部 mod 中的一个 content 作为参考对比对象。"""

    def __init__(self, mod: ExternalMod, parent=None) -> None:
        super().__init__(parent)
        self._mod = mod
        self._category: str | None = None
        self._name: str | None = None
        self.setWindowTitle(f"选择参考：{mod.name}")
        self.setMinimumSize(480, 380)
        self._setup_ui()

    @property
    def selected_category(self) -> str | None:
        return self._category

    @property
    def selected_name(self) -> str | None:
        return self._name

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"<b>{self._mod.name}</b> — 选择要对比的内容"))

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._cat_list = QListWidget()
        cats = self._mod.categories()
        # 优先展示常见分类（units/blocks/weapons 前置），其余按字母
        def _sort_key(c: str) -> tuple:
            return (0, c) if c in ("units", "blocks", "weapons") else (1, c)

        for cat in sorted(cats, key=_sort_key):
            self._cat_list.addItem(cat)
        self._cat_list.currentTextChanged.connect(self._on_category_changed)
        splitter.addWidget(self._cat_list)

        self._name_list = QListWidget()
        splitter.addWidget(self._name_list)

        layout.addWidget(splitter, stretch=1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_category_changed(self, cat: str) -> None:
        self._category = cat
        self._name_list.clear()
        for n in self._mod.names(cat):
            self._name_list.addItem(n)

    def _accept(self) -> None:
        item = self._name_list.currentItem()
        if item is None:
            self.reject()
            return
        self._name = item.text()
        self.accept()
