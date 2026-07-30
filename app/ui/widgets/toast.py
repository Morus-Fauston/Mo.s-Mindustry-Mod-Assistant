"""Toast 提示控件：右下角滑入、停留后自动消失。

用于自动保存、操作反馈等轻量提示，不打断编辑流程。

用法：
    toast = Toast(host_widget)
    toast.show_message("已保存 · 蓝钢")
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QLabel, QWidget


class Toast(QLabel):
    """悬浮在父控件右下角的短暂提示。"""

    def __init__(self, host: QWidget, duration_ms: int = 2000, parent: QWidget | None = None) -> None:
        super().__init__(parent or host)
        self.setObjectName("toast")
        self._host = host
        self._duration = duration_ms
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(False)
        self.hide()

    def show_message(self, message: str) -> None:
        """显示一条提示，自动计时消失。重复调用会刷新内容与计时。"""
        self.setText(message)
        self.adjustSize()
        self._reposition()
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()
        self._timer.start(self._duration)

    def _reposition(self) -> None:
        margin = 14
        x = self._host.width() - self.width() - margin
        y = self._host.height() - self.height() - margin
        self.move(max(margin, x), max(margin, y))

    def _fade_out(self) -> None:
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(250)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InQuad)
        anim.finished.connect(self.hide)
        anim.start()
        # 保持引用，避免被垃圾回收
        self._anim = anim
