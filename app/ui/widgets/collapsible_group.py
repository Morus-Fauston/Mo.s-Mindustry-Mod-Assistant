"""可折叠字段分组控件。

替代原生 QGroupBox：点击组头折叠/展开，箭头旋转，
组头右侧 hover 显示操作按钮（+ 添加字段 / ✕ 删除整组），
锁定组（basic 等）显示锁图标且不可删除。

v0.2.4.batch2：能力开关组（capability=True）组头 = ▾ ☐ 标题 …
复选框管能力开关、箭头管折叠，二者正交。

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

from .check_toggle import CheckToggle


class CollapsibleGroup(QFrame):
    """可折叠的字段分组容器。

    继承 QFrame 而非 QWidget：Qt QSS 对 QWidget 不支持 border/border-radius
    渲染，只有 QFrame 及其子类才支持。这是组卡片边框一直不显示的根因。
    """

    add_field_requested = Signal(str)   # group_name
    delete_group_requested = Signal(str)  # group_name
    expandedChanged = Signal(str, bool)  # (group_name, expanded) — v0.2.4 统一记忆通道
    capability_toggled = Signal(str, bool)  # (group_name, enabled) — v0.2.4.batch2

    def __init__(
        self,
        group_name: str,
        title: str,
        english: str = "",
        locked: bool = False,
        expanded: bool = True,
        capability: bool = False,
        capability_enabled: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("collapsibleGroup")
        self.group_name = group_name
        self._locked = locked
        self._expanded = expanded
        self._capability = capability
        self._capability_enabled = capability_enabled
        self._setup_ui(title, english)
        if capability:
            self._apply_capability_state(capability_enabled, emit=False)
        else:
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

        # 能力开关组：复选框在箭头和标题之间
        self._cap_toggle: CheckToggle | None = None
        if self._capability:
            self._cap_toggle = CheckToggle()
            self._cap_toggle.setFixedSize(18, 18)
            self._cap_toggle.toggled.connect(self._on_capability_toggled)
            head_layout.addWidget(self._cap_toggle)

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
        # v0.2.4.batch2：能力组须排除复选框子控件的点击
        self._head.mousePressEvent = self._on_head_click  # type: ignore[method-assign]

    def _on_head_click(self, event) -> None:  # noqa: N802
        """组头点击 → 折叠/展开。能力组排除复选框区域。"""
        if self._cap_toggle is not None:
            # 检查点击是否在复选框上
            pos = self._cap_toggle.mapFromGlobal(event.globalPosition().toPoint())
            if self._cap_toggle.rect().contains(pos):
                return  # 让复选框自己处理
        self.toggle()

    def _on_capability_toggled(self, checked: bool) -> None:
        """复选框状态变化 → 发射信号，不触发折叠。"""
        self._capability_enabled = checked
        self._apply_capability_state(checked, emit=True)

    def _apply_capability_state(self, enabled: bool, emit: bool = True) -> None:
        """应用能力开关状态：未勾选=禁用态+组体不渲染。"""
        if self._cap_toggle is not None:
            self._cap_toggle.blockSignals(True)
            self._cap_toggle.setChecked(enabled)
            self._cap_toggle.blockSignals(False)

        if enabled:
            # 勾选：组头正常，组体可见，首次默认展开
            self._head.setEnabled(True)
            self._chevron.setEnabled(True)
            self._body.setVisible(self._expanded)
            self._chevron.setText("▾" if self._expanded else "▸")
        else:
            # 未勾选：组头禁用态，组体不渲染
            self._head.setEnabled(True)  # head 本身要能点复选框
            self._chevron.setEnabled(False)
            self._chevron.setText("▸")
            self._body.setVisible(False)

        if emit:
            self.capability_toggled.emit(self.group_name, enabled)

    # ── 公共接口 ────────────────────────────────────────────────────────

    @property
    def body_layout(self) -> QVBoxLayout:
        """往组体里添加字段行的布局。"""
        return self._body_layout

    @property
    def expanded(self) -> bool:
        return self._expanded

    @property
    def is_capability(self) -> bool:
        return self._capability

    @property
    def capability_enabled(self) -> bool:
        return self._capability_enabled

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        if self._capability and not self._capability_enabled:
            # 能力未开启时不展开组体
            self._body.setVisible(False)
            self._chevron.setText("▸")
        else:
            self._body.setVisible(expanded)
            self._chevron.setText("▾" if expanded else "▸")
        # 统一记忆通道：组头点击与 chevron 点击都经由此信号
        self.expandedChanged.emit(self.group_name, self._expanded)

    def toggle(self) -> None:
        if self._capability and not self._capability_enabled:
            return  # 能力未开启时不允许折叠操作
        self.set_expanded(not self._expanded)
