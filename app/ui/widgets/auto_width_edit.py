"""名称档自动撑宽输入框。

最小 120px，按字体度量随文本撑长，上限 280px。
textChanged 时动态调宽。
"""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QSizePolicy

_MIN_W = 120
_MAX_W = 280
_PAD = 24  # 左右 padding + 光标余量


class AutoWidthEdit(QLineEdit):
    """随文本撑宽的单行输入框（名称档）。"""

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        # QLineEdit 默认 Expanding，会在 QHBoxLayout 里跟 stretch 竞争→飞到中间
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.textChanged.connect(self._adjust_width)

    def _adjust_width(self) -> None:
        fm = self.fontMetrics()
        w = fm.horizontalAdvance(self.text()) + _PAD
        self.setFixedWidth(max(_MIN_W, min(_MAX_W, w)))

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(text)
        self._adjust_width()
