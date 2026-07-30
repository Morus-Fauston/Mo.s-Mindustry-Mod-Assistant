"""可折叠字段分组控件。

替代原生 QGroupBox：点击组头折叠/展开，箭头旋转，
组头右侧 hover 显示操作按钮（+ 添加字段 / ✕ 删除整组），
锁定组（basic 等）显示锁图标且不可删除。

objectName: collapsibleGroup / groupHead / groupBody，配合 QSS。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class CollapsibleGroup(QFrame):
    """可折叠的字段分组容器。

    继承 QFrame 而非 QWidget：Qt QSS 对 QWidget 不支持 border/border-radius
    渲染，只有 QFrame 及其子类才支持。这是组卡片边框一直不显示的根因。
    """

    add_field_requested = Signal(str)   # group_name
    delete_group_requested = Signal(str)  # group_name

    def __init__(
        self,
        group_name: str,
        title: str,
        english: str = "",
        locked: bool = False,
        expanded: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("collapsibleGroup")
        self.group_name = group_name
        self._locked = locked
        self._expanded = expanded
        self._setup_ui(title, english)
        self.set_expanded(expanded)

    # ── UI ──────────────────────────────────────────────────────────────

    def _setup_ui(self, title: str, english: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 组头
        self._head = QFrame()
        self._head.setObjectName("groupHead")
        head_layout = QHBoxLayout(self._head)
        head_layout.setContentsMargins(10, 0, 8, 0)
        head_layout.setSpacing(8)

        # 折叠箭头（纯文本字符，不依赖图标）
        self._chevron = QToolButton()
        self._chevron.setText("▾")
        self._chevron.setAutoRaise(True)
        self._chevron.setFixedSize(16, 16)
        self._chevron.setObjectName("groupChevron")
        self._chevron.clicked.connect(self.toggle)
        head_layout.addWidget(self._chevron)

        # 标题
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        head_layout.addWidget(title_label)
        if english:
            en_label = QLabel(english)
            en_label.setObjectName("groupEnglish")
            head_layout.addWidget(en_label)

        head_layout.addStretch()

        # 操作按钮（hover 显示，锁定组不显示删除）
        self._add_btn = QToolButton()
        self._add_btn.setText("+")
        self._add_btn.setToolTip("添加字段")
        self._add_btn.setFixedSize(22, 22)
        self._add_btn.clicked.connect(lambda: self.add_field_requested.emit(self.group_name))
        head_layout.addWidget(self._add_btn)

        if self._locked:
            lock_label = QLabel("锁定")
            lock_label.setObjectName("groupLock")
            head_layout.addWidget(lock_label)
        else:
            self._del_btn = QToolButton()
            self._del_btn.setText("✕")
            self._del_btn.setToolTip("删除整组字段")
            self._del_btn.setFixedSize(22, 22)
            self._del_btn.clicked.connect(lambda: self.delete_group_requested.emit(self.group_name))
            head_layout.addWidget(self._del_btn)

        layout.addWidget(self._head)

        # 组体（字段行容器）
        self._body = QFrame()
        self._body.setObjectName("groupBody")
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(12, 8, 12, 10)
        self._body_layout.setSpacing(4)
        layout.addWidget(self._body)

        # 组头点击折叠（点标题区域也触发）
        self._head.mousePressEvent = self._on_head_click  # type: ignore[method-assign]

    def _on_head_click(self, event) -> None:  # noqa: N802
        self.toggle()

    # ── 公共接口 ────────────────────────────────────────────────────────

    @property
    def body_layout(self) -> QVBoxLayout:
        """往组体里添加字段行的布局。"""
        return self._body_layout

    @property
    def expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._body.setVisible(expanded)
        self._chevron.setText("▾" if expanded else "▸")

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)
