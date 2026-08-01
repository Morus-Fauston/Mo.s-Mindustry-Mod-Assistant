"""去尾零数值输入框。

QSpinBox / QDoubleSpinBox 固定 setDecimals(N) 会显示 N 位小数（300.000）。
子类化 override textFromValue 用 Python f"{v:g}" 格式化，显示时去尾零，
输入精度不变。

v0.2.4：
- 彻底禁用滚轮改值（无论是否聚焦）——hover 滚轮时焦点可能转移，判断焦点不可靠；
  数值一律只允许键盘/点击调整，滚轮只用于滚动页面。
- 内部 QLineEdit 局部样式补偿：Windows 11 样式下内部 lineEdit 继承基础 QSS 的
  border+padding，使文本起点比普通 QLineEdit 多 ~4px（左留白不一致）。
  QSS 后代选择器无法命中 QAbstractSpinBox 内部 lineEdit，只能实例级局部样式。
"""

from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox

# spinbox 内部 QLineEdit 的局部样式：去掉自身 border/padding，
# 文本起点 = spinbox 的 editfield 起点（与普通 QLineEdit 一致）。
_INNER_EDIT_STYLE = "padding: 0; border: none;"


class NumSpinBox(QSpinBox):
    """整数框：显示时去前导/无意义格式（实际 QSpinBox 本就无小数问题，
    但统一子类方便后续扩展）。"""

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.lineEdit().setStyleSheet(_INNER_EDIT_STYLE)

    def textFromValue(self, value: int) -> str:  # noqa: N802
        return str(value)

    def wheelEvent(self, event) -> None:  # noqa: N802
        # 彻底禁用滚轮改值：事件交给父级（滚动页面），数值不变
        event.ignore()


class NumDoubleSpinBox(QDoubleSpinBox):
    """浮点框：显示时去尾零（300.000→300, 1.500→1.5, 0.100→0.1）。"""

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.lineEdit().setStyleSheet(_INNER_EDIT_STYLE)

    def textFromValue(self, value: float) -> str:  # noqa: N802
        # 定点格式 + 去尾零。不用 :g（有效数字格式）——decimals 小时
        # 会吞小数位（1.1→"1"）或产生科学计数法（10→"1e+01"）。
        s = f"{value:.{self.decimals()}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s

    def wheelEvent(self, event) -> None:  # noqa: N802
        # 彻底禁用滚轮改值：事件交给父级（滚动页面），数值不变
        event.ignore()
