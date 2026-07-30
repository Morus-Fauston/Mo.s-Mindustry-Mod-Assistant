"""字段行容器：3px 色条 + 2px 间隙 + 控件 + 可选红 X 删除按钮。

设计定稿（见 Docs/v021-风格规划.html）：
- 色条与控件分离，中间隔 2px
- 色条明度提高（用 B_* 令牌），控件淡底 + 同色系描边（QSS 属性选择器）
- 色条与控件都设置 fieldType 动态属性，走 QSS 属性选择器
- 可选字段右侧显示红 X 删除按钮（hover 时浮现），required 字段无红 X

用法：
    row = FieldRow(control, field_type="num", deletable=True)
    row.deleteRequested.connect(lambda: ...)
    form.addRow(label, row)
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QWidget


class FieldRow(QWidget):
    """包裹一个字段控件，左侧加 3px 类型色条（隔 2px），可选右侧删除按钮。"""

    deleteRequested = Signal()

    def __init__(
        self,
        control: QWidget,
        field_type: str,
        deletable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("fieldRow")
        self._control = control
        self._field_type = field_type

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)  # 色条与控件间隙

        # 色条（3px 宽，圆角，颜色由 QSS #fieldBar[fieldType=...] 决定）
        self._bar = QWidget()
        self._bar.setObjectName("fieldBar")
        self._bar.setProperty("fieldType", field_type)
        self._bar.setFixedWidth(3)
        layout.addWidget(self._bar)

        # 控件（设置 fieldType 属性，QSS 属性选择器命中淡底+描边）
        control.setProperty("fieldType", field_type)
        layout.addWidget(control)

        # 删除按钮（仅可选字段，hover 时浮现）
        self._del_btn: QToolButton | None = None
        if deletable:
            self._del_btn = QToolButton()
            self._del_btn.setObjectName("fieldDeleteBtn")
            self._del_btn.setText("✕")
            self._del_btn.setToolTip("删除字段")
            self._del_btn.setFixedSize(20, 20)
            self._del_btn.setVisible(False)  # 默认隐藏，hover 浮现
            self._del_btn.clicked.connect(self.deleteRequested.emit)
            layout.addWidget(self._del_btn)

    @property
    def control(self) -> QWidget:
        return self._control

    def refresh_style(self) -> None:
        """动态属性变更后调用，让 QSS 重新生效。"""
        for w in (self._bar, self._control):
            w.style().unpolish(w)
            w.style().polish(w)

    # ── hover 浮现删除按钮 ──────────────────────────────────────────────

    def enterEvent(self, event) -> None:  # noqa: N802
        if self._del_btn is not None:
            self._del_btn.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._del_btn is not None and not self._del_btn.underMouse():
            self._del_btn.setVisible(False)
        super().leaveEvent(event)
