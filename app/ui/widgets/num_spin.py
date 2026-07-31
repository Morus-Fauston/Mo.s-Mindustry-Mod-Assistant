"""去尾零数值输入框。

QSpinBox / QDoubleSpinBox 固定 setDecimals(N) 会显示 N 位小数（300.000）。
子类化 override textFromValue 用 Python f"{v:g}" 格式化，显示时去尾零，
输入精度不变。

v0.2.4：override wheelEvent —— 未聚焦时忽略滚轮，防止滚动页面误改值。
"""

from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox


class NumSpinBox(QSpinBox):
    """整数框：显示时去前导/无意义格式（实际 QSpinBox 本就无小数问题，
    但统一子类方便后续扩展）。"""

    def textFromValue(self, value: int) -> str:  # noqa: N802
        return str(value)

    def wheelEvent(self, event) -> None:  # noqa: N802
        # 未聚焦时滚轮交给父级（滚动页面），不修改值
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)


class NumDoubleSpinBox(QDoubleSpinBox):
    """浮点框：显示时去尾零（300.000→300, 1.500→1.5, 0.100→0.1）。"""

    def textFromValue(self, value: float) -> str:  # noqa: N802
        # :g 格式自动去尾零，精度用当前 decimals 限制
        return f"{value:.{self.decimals()}g}"

    def wheelEvent(self, event) -> None:  # noqa: N802
        # 未聚焦时滚轮交给父级（滚动页面），不修改值
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)
