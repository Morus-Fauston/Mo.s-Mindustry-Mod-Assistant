"""C 阶段功能预留的统一禁用态控件。

B 阶段为尚未实现的功能（资源列表、科技引用、技能编辑等）提供视觉统一的
禁用骨架：一个禁用按钮 + tooltip「v0.2.2 实现」，而非灰色"开发中"文字标签。

用法：
    panel = ReservedPanel("资源列表", "item")
"""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

_RESERVED_TIP = "v0.2.2 实现"


class ReservedPanel(QWidget):
    """统一的 C 阶段预留禁用面板。"""

    def __init__(self, feature_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("reservedPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        btn = QPushButton(f"编辑{feature_name}")
        btn.setObjectName("reservedButton")
        btn.setEnabled(False)
        btn.setToolTip(_RESERVED_TIP)
        layout.addWidget(btn)
