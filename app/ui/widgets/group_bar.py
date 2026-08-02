"""复合字段组色条容器（E-2 / ADR-012 19.3）。

普通字段用 FieldRow（3px 细色条）；复合字段（资源列表/资源槽/科技引用/
消耗定义/weapons/abilities）用 GroupBar 包裹：4px 宽色条（马卡龙原色）
+ 淡染背景容器 + 可选标签行。

设计定稿（grill 会话）：
- 色条保持马卡龙原色（arr=青 / obj=黄 / ref=紫），不淡化
- 容器淡染背景比字段控件的淡底更淡（QSS @F_*@ 令牌 + 降低透明度）
- 容器自带标题的编辑器（如 PolymorphicTypeEditor 的 QGroupBox 标题）
  不再重复加标签；裸编辑器由 GroupBar 负责加标签行

用法：
    bar = GroupBar(editor, field_type="arr", label="建造需求")
    rows_layout.addWidget(bar)

QSS 命中：
    #groupBar[fieldType=...]             — 色条
    #groupBarContainer[fieldType=...]    — 容器淡染
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .label_helper import rich_label


class GroupBar(QWidget):
    """复合字段容器：4px 色条 + 淡染背景 + 内嵌编辑器。"""

    def __init__(
        self,
        editor: QWidget,
        field_type: str,
        label: str = "",
        english: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("groupBarWidget")
        self._editor = editor
        self._field_type = field_type

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 色条（4px 宽，颜色由 QSS #groupBar[fieldType=...] 决定）
        self._bar = QFrame()
        self._bar.setObjectName("groupBar")
        self._bar.setProperty("fieldType", field_type)
        self._bar.setFixedWidth(4)
        layout.addWidget(self._bar)

        # 容器（淡染背景，QSS 命中）
        container = QFrame()
        container.setObjectName("groupBarContainer")
        container.setProperty("fieldType", field_type)
        inner = QVBoxLayout(container)
        inner.setContentsMargins(8, 4, 8, 6)
        inner.setSpacing(4)

        if label:
            label_widget = rich_label(label, english)
            label_widget.setObjectName("groupBarLabel")
            inner.addWidget(label_widget)

        inner.addWidget(editor)
        layout.addWidget(container, stretch=1)

    @property
    def field_type(self) -> str:
        return self._field_type

    @property
    def editor(self) -> QWidget:
        return self._editor

    def refresh_style(self) -> None:
        """动态属性变更后调用，让 QSS 重新生效。"""
        for w in (self._bar,):
            w.style().unpolish(w)
            w.style().polish(w)
