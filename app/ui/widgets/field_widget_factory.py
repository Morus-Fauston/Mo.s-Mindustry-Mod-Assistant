"""数值/布尔/字符串控件工厂——消灭四处复制粘贴。

调用方只需：
    widget = create_value_widget(value, on_change)

内部统一处理：
- 类型判断（bool → CheckToggle, int → NumSpinBox, float → NumDoubleSpinBox, str → AutoWidthEdit）
- 范围 / 小数位 / 固定宽度
- 滚轮禁用（NumSpinBox/NumDoubleSpinBox 已内置）
- blockSignals 初始化（防 setValue 误触发信号写脏数据，v0.2.5 教训）

不包含 FieldRow 包裹——调用方自行决定是否包色条。
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import QWidget

from .auto_width_edit import AutoWidthEdit
from .check_toggle import CheckToggle
from .num_spin import NumDoubleSpinBox, NumSpinBox


def create_value_widget(
    value: Any,
    on_change: Callable[[Any], None],
    *,
    width: int = 70,
    decimals: int = 3,
) -> QWidget | None:
    """按 Python 值类型创建对应编辑控件，已接好信号。

    返回 None 表示不支持的类型（调用方可 fallback 到只读标签）。
    """
    if isinstance(value, bool):
        cb = CheckToggle()
        cb.setChecked(value)
        cb.toggled.connect(on_change)
        return cb

    if isinstance(value, float):
        spin = NumDoubleSpinBox()
        spin.setRange(-999999.0, 999999.0)
        spin.setDecimals(decimals)
        spin.setFixedWidth(width)
        spin.blockSignals(True)
        spin.setValue(value)
        spin.blockSignals(False)
        spin.valueChanged.connect(on_change)
        return spin

    if isinstance(value, int):
        spin = NumSpinBox()
        spin.setRange(-999999, 999999)
        spin.setFixedWidth(width)
        spin.blockSignals(True)
        spin.setValue(value)
        spin.blockSignals(False)
        spin.valueChanged.connect(on_change)
        return spin

    if isinstance(value, str):
        edit = AutoWidthEdit()
        edit.setText(value)
        edit.textChanged.connect(lambda t: on_change(t if t else None))
        return edit

    return None
