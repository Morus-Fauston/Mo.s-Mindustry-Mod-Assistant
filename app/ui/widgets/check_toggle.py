"""自绘布尔开关：圆角方框 + 勾选态白勾。

零外部图片资源，深浅色自适应（颜色从 theme 令牌读取）。
替代原生 QCheckBox——原生 indicator 在 QSS 下无法用纯文本画勾，
故用 paintEvent 自绘，符合「纯文本/直观、不依赖丑图标」的设计取向。

用法与 QCheckBox 兼容：setCheckable 已开启，提供 toggled 信号、
setChecked / isChecked，可作为 FieldRow 的 control。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton

from ..theme import get_tokens


class CheckToggle(QAbstractButton):
    """22×22 自绘复选框：未选=淡底描边方框，选中=深色底+白色对勾。

    v0.2.4：18→22px，与 26px 字段行高 / 马卡龙色条比例协调。
    """

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(22, 22)

    def paintEvent(self, event) -> None:  # noqa: ANN001, N802
        t = get_tokens()
        fill = QColor(t.get("F_BOOL", "#F4FBF4"))
        stroke = QColor(t.get("S_BOOL", "#C0E6C4"))
        checked_fill = QColor(t.get("B_BOOL", "#A8DCAD"))

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(float(r.x()), float(r.y()), float(r.width()), float(r.height()), 3, 3)

        if self.isChecked():
            p.fillPath(path, checked_fill)
            p.setPen(QPen(checked_fill, 1))
            p.drawPath(path)
            # 白色对勾（两段折线）
            p.setPen(QPen(
                QColor("#FFFFFF"), 2.0,
                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin,
            ))
            x, y, w, h = r.x(), r.y(), r.width(), r.height()
            p.drawLine(int(x + w * 0.28), int(y + h * 0.52), int(x + w * 0.45), int(y + h * 0.70))
            p.drawLine(int(x + w * 0.45), int(y + h * 0.70), int(x + w * 0.74), int(y + h * 0.34))
        else:
            p.fillPath(path, fill)
            p.setPen(QPen(stroke, 1))
            p.drawPath(path)
        p.end()
