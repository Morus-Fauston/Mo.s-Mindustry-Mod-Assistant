"""颜色选择控件——色块按钮 + hex 文本输入。

Mindustry 颜色存储格式：
- hex 字符串（如 'ff7700' 或 '#ff7700'）
- rgba 对象 {'r': 1, 'g': 0.5, 'b': 0, 'a': 1}（0~1 浮点）

本控件统一解析两种格式，对外只暴露：
    .value        — 当前 hex 字符串（无 # 前缀）
    .valueChanged — Signal(str)，值变化时发射

色块背景色走内联 setStyleSheet（动态 hex 是 AGENTS.md 允许的唯一例外），
描边/圆角走 QSS #colorSwatch。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)


def parse_color(value: Any) -> tuple[QColor, str]:
    """解析 Mindustry 颜色值为 (QColor, 显示文本)。

    支持：
    - hex 字符串 'ff7700' / '#ff7700' / 'ff770080'（8位取前6）
    - rgba dict {'r': 1.0, 'g': 0.5, 'b': 0.0, 'a': 1.0}
    - None / 空 → 白色 + 空文本
    """
    if isinstance(value, str) and value:
        hex_str = value.lstrip("#")
        if len(hex_str) == 6:
            return QColor(f"#{hex_str}"), value
        if len(hex_str) == 8:
            return QColor(f"#{hex_str[:6]}"), value
        return QColor(255, 255, 255), value
    if isinstance(value, dict):
        r = int(value.get("r", 1) * 255)
        g = int(value.get("g", 1) * 255)
        b = int(value.get("b", 1) * 255)
        return QColor(r, g, b), f"{r:02x}{g:02x}{b:02x}"
    return QColor(255, 255, 255), ""


class ColorPicker(QWidget):
    """色块 + hex 输入的颜色编辑控件。"""

    valueChanged = Signal(str)  # 发射无 # 前缀的 hex 字符串

    def __init__(self, value: Any = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color, display_text = parse_color(value)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 色块按钮（背景色动态 hex 为唯一内联例外，描边/圆角走 QSS）
        self._swatch = QPushButton()
        self._swatch.setObjectName("colorSwatch")
        self._swatch.setFixedSize(48, 24)
        self._swatch.setStyleSheet(f"background-color: {self._color.name()};")

        # hex 文本输入
        self._hex_edit = QLineEdit(display_text)
        self._hex_edit.setMaximumWidth(100)

        self._swatch.clicked.connect(self._on_swatch_click)
        self._hex_edit.textChanged.connect(self._on_text_edit)

        layout.addWidget(self._swatch)
        layout.addWidget(self._hex_edit)
        layout.addStretch()

    @property
    def value(self) -> str:
        """当前颜色（无 # 前缀的 hex 字符串）。"""
        return self._color.name().lstrip("#")

    def _on_swatch_click(self) -> None:
        chosen = QColorDialog.getColor(self._color, self, "选择颜色")
        if chosen.isValid():
            self._color = chosen
            hex_val = chosen.name().lstrip("#")
            self._hex_edit.setText(hex_val)
            self._swatch.setStyleSheet(f"background-color: {chosen.name()};")
            self.valueChanged.emit(hex_val)

    def _on_text_edit(self, text: str) -> None:
        text = text.strip().lstrip("#")
        if len(text) == 6:
            try:
                int(text, 16)
            except ValueError:
                return
            self._color = QColor(f"#{text}")
            self._swatch.setStyleSheet(f"background-color: {self._color.name()};")
            self.valueChanged.emit(text)
