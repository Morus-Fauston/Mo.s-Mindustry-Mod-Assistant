"""Resource and technology reference editor widgets.

Four composite field editors:
- ResourceListEditor: multi-row item/liquid + amount lists (requirements, consumes.items)
- ResourceSlotEditor: single item/liquid + amount (outputItem, outputLiquid)
- TechRefEditor: string or string[] reference (research)
- ConsumesEditor: compound widget for the `consumes` object

Interface contract (all):
    .value        — get/set the field data
    .valueChanged — Signal, emitted on mutation
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core.commands import (
    ArrayInsertCommand,
    ArrayRemoveCommand,
    CommandStack,
    DeleteFieldCommand,
    SetFieldCommand,
    _NOT_FOUND,
    _get_nested,
    _set_nested,
)
from ...core.config_loader import get_config


# ── 数据源辅助 ─────────────────────────────────────────────────────────────


def _resource_options(metadata, project, resource_type: str) -> list[str]:
    """合并原版实例 + 工程自创内容，去重，原版在前。"""
    category = "Items" if resource_type == "item" else "Liquids"
    vanilla = metadata.list_instances(category) if metadata else []

    project_names: list[str] = []
    if project is not None:
        sub = "items" if resource_type == "item" else "liquids"
        sub_dir = project.contents.content_dir / sub
        if sub_dir.is_dir():
            project_names = sorted(p.stem for p in sub_dir.glob("*.json"))

    seen = set(vanilla)
    merged = list(vanilla)
    for name in project_names:
        if name not in seen:
            merged.append(name)
            seen.add(name)
    return merged


def _resource_display(name: str, resource_type: str) -> str:
    """资源下拉显示名：'copper' → '铜 (copper)'；无中文则原样。

    中文来自 app/config/resource_names_zh.json（原版物品/液体标准译名）。
    """
    if not name:
        return ""
    cat = "items" if resource_type == "item" else "liquids"
    zh_map = get_config("resource_names_zh").get(cat, {})
    zh = zh_map.get(name, "")
    return f"{zh} ({name})" if zh else name


def _resource_value(display: str) -> str:
    """下拉显示名反转回存储值：'铜 (copper)' → 'copper'。"""
    if not display:
        return ""
    if " (" in display and display.endswith(")"):
        return display[display.rfind(" (") + 2 : -1]
    return display


def _set_combo_text(combo: "QComboBox", display: str) -> None:
    """设置 editable combo 文本并把光标移到开头。

    v0.2.5 修复：直接 setEditText 后光标在末尾 → QLineEdit 视口滚动到末尾，
    长文本（如「爆破混合物 (blast-compound)」）左侧中文被滚出视野，
    看起来"文字右对齐、左边重点看不见"。
    """
    combo.setEditText(display)
    le = combo.lineEdit()
    if le is not None:
        le.setCursorPosition(0)


def _set_combo_view_width(combo: "QComboBox") -> None:
    """弹出列表按最长选项撑宽（fixedWidth 下 sizeAdjustPolicy 无效，需设 view 最小宽）。

    v0.2.5 修复：默认弹出宽度 = combo 宽度，长英文选项（blast-compound 等）
    被截断；固定宽度下 AdjustToMinimumContentsLengthWithIcon 不生效。
    """
    from PySide6.QtGui import QFontMetrics

    fm = QFontMetrics(combo.font())
    longest = 0
    for i in range(combo.count()):
        longest = max(longest, fm.horizontalAdvance(combo.itemText(i)))
    combo.view().setMinimumWidth(longest + 24)


# ── ResourceListEditor ─────────────────────────────────────────────────────


class ResourceListEditor(QWidget):
    """Multi-row resource list: [{item/liquid: str, amount: int, booster?: bool}]."""

    valueChanged = Signal()

    def __init__(
        self,
        data: dict,
        path: str,
        command_stack: CommandStack,
        resource_type: str = "item",
        has_booster: bool = False,
        metadata=None,
        project=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data = data
        self._path = path
        self._commands = command_stack
        self._resource_type = resource_type
        self._has_booster = has_booster
        self._metadata = metadata
        self._project = project
        self._options = _resource_options(metadata, project, resource_type)
        self._row_widgets: list[QWidget] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        self._rebuild_rows()

        add_btn = QPushButton("+ 添加")
        add_btn.setFixedWidth(80)
        add_btn.clicked.connect(self._add_row)
        self._layout.addWidget(add_btn)

    @property
    def value(self) -> list[dict]:
        """读取路径处列表。

        路径可能是嵌套点路径（如 'consumes.items'）或顶层键（如 'requirements'）。
        用 _get_nested 而非 dict.get，否则嵌套路径读不到（v0.2.5 修复：
        消耗定义 items/liquids 列表显示为空的根因）。
        """
        val = _get_nested(self._data, self._path)
        return val if isinstance(val, list) else []

    @value.setter
    def value(self, new_value: list[dict]) -> None:
        _set_nested(self._data, self._path, new_value)
        self._rebuild_rows()
        self.valueChanged.emit()

    def _rebuild_rows(self) -> None:
        for w in self._row_widgets:
            self._layout.removeWidget(w)
            w.deleteLater()
        self._row_widgets.clear()

        items = self.value
        for i, entry in enumerate(items):
            row = self._make_row(i, entry)
            self._layout.insertWidget(self._layout.count() - 1, row)
            self._row_widgets.append(row)

    def _make_row(self, index: int, entry: dict) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        key = "item" if self._resource_type == "item" else "liquid"
        # 下拉：显示「中文 (英文)」，fieldType=ref 走 QSS 马卡龙（与主面板一致）
        combo = QComboBox()
        combo.setEditable(True)
        combo.setFixedWidth(200)  # 容纳「爆破混合物 (blast-compound)」长选项
        combo.setProperty("fieldType", "ref")
        for opt in self._options:
            combo.addItem(_resource_display(opt, self._resource_type), opt)
        current = entry.get(key, "")
        display = _resource_display(current, self._resource_type)
        idx = combo.findData(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            le = combo.lineEdit()
            if le is not None:
                le.setCursorPosition(0)  # 防视口滚到末尾，左侧中文被遮（v0.2.5）
        else:
            _set_combo_text(combo, display)
        # 弹出列表按最长选项撑宽，避免英文长名被截断
        _set_combo_view_width(combo)
        combo.currentTextChanged.connect(
            lambda text, i=index, k=key: self._on_field_edit(
                i, k, _resource_value(text)
            )
        )
        h.addWidget(combo)

        spin = QSpinBox()
        spin.setRange(1, 99999)
        spin.setFixedWidth(80)
        spin.setProperty("fieldType", "num")
        spin.setValue(int(entry.get("amount", 1)))
        spin.editingFinished.connect(
            lambda i=index, s=spin: self._on_field_edit(i, "amount", s.value())
        )
        h.addWidget(spin)

        if self._has_booster:
            cb = QCheckBox("加速")
            cb.setChecked(bool(entry.get("booster", False)))
            cb.toggled.connect(
                lambda checked, i=index: self._on_field_edit(i, "booster", checked)
            )
            h.addWidget(cb)

        # 删除按钮：统一 weaponRemoveBtn 样式（QSS 已定义，红色 hover）
        del_btn = QPushButton("×")
        del_btn.setObjectName("weaponRemoveBtn")
        del_btn.setFixedSize(24, 24)
        del_btn.setToolTip("删除此行")
        del_btn.clicked.connect(lambda _, i=index: self._remove_row(i))
        h.addWidget(del_btn)

        h.addStretch(1)
        return row

    def _on_field_edit(self, index: int, key: str, new_val: Any) -> None:
        items = self.value
        if index >= len(items):
            return
        if items[index].get(key) == new_val:
            return
        cmd = SetFieldCommand(
            self._data, f"{self._path}.{index}.{key}", new_val,
            on_change=self.valueChanged.emit,
        )
        self._commands.execute(cmd)

    def _add_row(self) -> None:
        key = "item" if self._resource_type == "item" else "liquid"
        new_entry = {key: "", "amount": 1}
        items = self.value
        cmd = ArrayInsertCommand(
            self._data, self._path, len(items), new_entry,
            on_change=self._rebuild_and_notify,
        )
        self._commands.execute(cmd)

    def _remove_row(self, index: int) -> None:
        cmd = ArrayRemoveCommand(
            self._data, self._path, index,
            on_change=self._rebuild_and_notify,
        )
        self._commands.execute(cmd)

    def _rebuild_and_notify(self) -> None:
        self._rebuild_rows()
        self.valueChanged.emit()


# ── ResourceSlotEditor ─────────────────────────────────────────────────────


class ResourceSlotEditor(QWidget):
    """Single resource slot: {item/liquid: str, amount: int}."""

    valueChanged = Signal()

    def __init__(
        self,
        data: dict,
        path: str,
        command_stack: CommandStack,
        resource_type: str = "item",
        metadata=None,
        project=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data = data
        self._path = path
        self._commands = command_stack
        self._resource_type = resource_type
        self._options = _resource_options(metadata, project, resource_type)

        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)

        self._key = "item" if resource_type == "item" else "liquid"

        self._combo = QComboBox()
        self._combo.setEditable(True)
        self._combo.setFixedWidth(200)
        self._combo.setProperty("fieldType", "ref")  # QSS 马卡龙
        self._combo.addItem("")  # 空 = 清除字段
        for opt in self._options:
            self._combo.addItem(_resource_display(opt, resource_type), opt)
        current_val = self.value
        current = current_val.get(self._key, "") if isinstance(current_val, dict) else ""
        idx = self._combo.findData(current)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
            le = self._combo.lineEdit()
            if le is not None:
                le.setCursorPosition(0)  # 防视口滚到末尾（v0.2.5）
        else:
            _set_combo_text(self._combo, _resource_display(current, resource_type))
        _set_combo_view_width(self._combo)
        self._combo.currentTextChanged.connect(self._on_combo_changed)
        h.addWidget(self._combo)

        self._spin = QSpinBox()
        self._spin.setRange(1, 99999)
        self._spin.setFixedWidth(80)
        self._spin.setProperty("fieldType", "num")  # QSS 马卡龙
        amount = current_val.get("amount", 1) if isinstance(current_val, dict) else 1
        self._spin.setValue(int(amount))
        self._spin.editingFinished.connect(self._on_amount_changed)
        h.addWidget(self._spin)

        h.addStretch(1)

    @property
    def value(self) -> dict | None:
        val = _get_nested(self._data, self._path)
        return val if isinstance(val, dict) else None

    @value.setter
    def value(self, new_value: dict | None) -> None:
        if new_value is None:
            from ...core.commands import _del_nested

            _del_nested(self._data, self._path)
        else:
            _set_nested(self._data, self._path, new_value)
        self.valueChanged.emit()

    def _on_combo_changed(self, text: str) -> None:
        if not text:
            cmd = SetFieldCommand(
                self._data, self._path, None,
                on_change=self.valueChanged.emit,
            )
        else:
            current = self.value or {}
            new_val = dict(current)
            new_val[self._key] = _resource_value(text)
            if "amount" not in new_val:
                new_val["amount"] = 1
            cmd = SetFieldCommand(
                self._data, self._path, new_val,
                on_change=self.valueChanged.emit,
            )
        self._commands.execute(cmd)

    def _on_amount_changed(self) -> None:
        current = self.value
        if not current:
            return
        new_val = dict(current)
        new_val["amount"] = self._spin.value()
        cmd = SetFieldCommand(
            self._data, self._path, new_val,
            on_change=self.valueChanged.emit,
        )
        self._commands.execute(cmd)


# ── TechRefEditor ──────────────────────────────────────────────────────────


class TechRefEditor(QWidget):
    """Technology reference: string or list of strings."""

    valueChanged = Signal()

    def __init__(
        self,
        data: dict,
        path: str,
        command_stack: CommandStack,
        multi: bool = False,
        metadata=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data = data
        self._path = path
        self._commands = command_stack
        self._multi = multi

        self._options: list[str] = []
        if metadata:
            for cat in metadata.list_instance_categories():
                self._options.extend(metadata.list_instances(cat))
            self._options.sort()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if multi:
            self._tags_layout = QHBoxLayout()
            self._tags_layout.setSpacing(4)
            layout.addLayout(self._tags_layout)
            self._rebuild_tags()

        self._combo = QComboBox()
        self._combo.setEditable(True)
        self._combo.setFixedWidth(200)
        self._combo.setProperty("fieldType", "ref")  # QSS 马卡龙下拉样式
        self._combo.addItems(self._options)
        if not multi:
            current = self.value
            if isinstance(current, str):
                idx = self._combo.findText(current)
                if idx >= 0:
                    self._combo.setCurrentIndex(idx)
                    le = self._combo.lineEdit()
                    if le is not None:
                        le.setCursorPosition(0)
                else:
                    _set_combo_text(self._combo, current)
            self._combo.currentTextChanged.connect(self._on_single_changed)
        else:
            self._combo.setEditText("")
            self._combo.lineEdit().setPlaceholderText("输入后回车添加...")
            self._combo.lineEdit().returnPressed.connect(self._on_multi_add)
        _set_combo_view_width(self._combo)
        layout.addWidget(self._combo)

    @property
    def value(self) -> Any:
        val = _get_nested(self._data, self._path)
        return val if val is not _NOT_FOUND else None

    @value.setter
    def value(self, new_value: Any) -> None:
        if new_value is None:
            from ...core.commands import _del_nested

            _del_nested(self._data, self._path)
        else:
            _set_nested(self._data, self._path, new_value)
        if self._multi:
            self._rebuild_tags()
        self.valueChanged.emit()

    def _on_single_changed(self, text: str) -> None:
        cmd = SetFieldCommand(
            self._data, self._path, text if text else None,
            on_change=self.valueChanged.emit,
        )
        self._commands.execute(cmd)

    def _on_multi_add(self) -> None:
        text = self._combo.currentText().strip()
        if not text:
            return
        current = self.value
        items = list(current) if isinstance(current, list) else []
        if text not in items:
            cmd = ArrayInsertCommand(
                self._data, self._path, len(items), text,
                on_change=self._rebuild_and_notify,
            )
            self._commands.execute(cmd)
        self._combo.setEditText("")

    def _remove_tag(self, index: int) -> None:
        cmd = ArrayRemoveCommand(
            self._data, self._path, index,
            on_change=self._rebuild_and_notify,
        )
        self._commands.execute(cmd)

    def _rebuild_tags(self) -> None:
        while self._tags_layout.count():
            item = self._tags_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        current = self.value
        if not isinstance(current, list):
            return
        for i, name in enumerate(current):
            tag = QPushButton(f"{name} ×")
            tag.setFixedHeight(22)
            tag.clicked.connect(lambda _, idx=i: self._remove_tag(idx))
            self._tags_layout.addWidget(tag)
        self._tags_layout.addStretch(1)

    def _rebuild_and_notify(self) -> None:
        if self._multi:
            self._rebuild_tags()
        self.valueChanged.emit()


# ── ConsumesEditor ─────────────────────────────────────────────────────────

_CONSUMES_SLOTS = [
    ("items", "物品消耗", "resource_list"),
    ("power", "电力消耗", "spin"),
    ("liquid", "液体消耗", "resource_slot"),
    ("liquids", "多液体消耗", "resource_list"),
    ("coolant", "冷却液", "resource_slot"),
    ("heat", "热量消耗", "spin"),
]


class ConsumesEditor(QWidget):
    """Compound editor for the `consumes` object. Data-driven: renders sub-widgets
    for keys present in the current dict, plus an [添加消耗] dropdown."""

    valueChanged = Signal()

    def __init__(
        self,
        data: dict,
        path: str,
        command_stack: CommandStack,
        metadata=None,
        project=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data = data
        self._path = path
        self._commands = command_stack
        self._metadata = metadata
        self._project = project
        self._sub_widgets: dict[str, QWidget] = {}

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

        self._rebuild()

    @property
    def value(self) -> dict:
        val = _get_nested(self._data, self._path)
        return val if isinstance(val, dict) else {}

    @value.setter
    def value(self, new_value: dict) -> None:
        _set_nested(self._data, self._path, new_value)
        self._rebuild()
        self.valueChanged.emit()

    def _rebuild(self) -> None:
        for w in self._sub_widgets.values():
            self._layout.removeWidget(w)
            w.deleteLater()
        self._sub_widgets.clear()
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        consumes = self.value
        existing_keys = set(consumes.keys())

        for key, label, widget_type in _CONSUMES_SLOTS:
            if key not in existing_keys:
                continue
            row = self._make_sub_widget(key, label, widget_type)
            self._layout.addWidget(row)
            self._sub_widgets[key] = row

        missing = [(k, l) for k, l, _ in _CONSUMES_SLOTS if k not in existing_keys]
        if missing:
            add_row = QHBoxLayout()
            add_label = QLabel("+ 添加消耗:")
            add_combo = QComboBox()
            add_combo.setFixedWidth(150)
            # 占位项 index 0（data=None）：rebuild 后默认停在占位，用户每次选择
            # 真实类型都会改变 index → activated 必触发。若默认 index 0 就是
            # "物品消耗"，添加后 rebuild 回 index 0，重复点击同一项 Qt 不再发
            # activated → "点击无反应"（v0.2.5 修复）。
            add_combo.addItem("请选择消耗类型…", None)
            for k, l in missing:
                add_combo.addItem(l, k)
            add_combo.activated.connect(self._on_add_consumes)
            add_row.addWidget(add_label)
            add_row.addWidget(add_combo)
            add_row.addStretch(1)
            add_widget = QWidget()
            add_widget.setLayout(add_row)
            self._layout.addWidget(add_widget)
            self._sub_widgets["__add__"] = add_widget

        self._layout.addStretch(1)

    def _make_sub_widget(self, key: str, label: str, widget_type: str) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        # 标题行：标签 + 右对齐删除按钮（统一 weaponRemoveBtn 样式）
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(f"{label}:")
        head.addWidget(lbl)
        head.addStretch(1)
        del_btn = QPushButton("×")
        del_btn.setObjectName("weaponRemoveBtn")
        del_btn.setFixedSize(24, 24)
        del_btn.setToolTip(f"移除{label}")
        del_btn.clicked.connect(lambda _, k=key: self._remove_consumes(k))
        head.addWidget(del_btn)
        v.addLayout(head)

        sub_path = f"{self._path}.{key}"

        if widget_type == "resource_list":
            resource_type = "liquid" if key in ("liquids", "coolant") else "item"
            editor = ResourceListEditor(
                self._data, sub_path, self._commands,
                resource_type=resource_type,
                has_booster=(key == "items"),
                metadata=self._metadata,
                project=self._project,
            )
            editor.valueChanged.connect(self.valueChanged.emit)
            # 垂直布局：编辑器占满整行宽度，不被 HBox 挤压（v0.2.5 修复）
            v.addWidget(editor)
        elif widget_type == "resource_slot":
            editor = ResourceSlotEditor(
                self._data, sub_path, self._commands,
                resource_type="liquid",
                metadata=self._metadata,
                project=self._project,
            )
            editor.valueChanged.connect(self.valueChanged.emit)
            v.addWidget(editor)
        elif widget_type == "spin":
            spin = QDoubleSpinBox()
            spin.setRange(0, 99999)
            spin.setDecimals(2)
            spin.setFixedWidth(100)
            spin.setProperty("fieldType", "num")  # QSS 马卡龙
            current = self.value.get(key, 0)
            spin.setValue(float(current) if current else 0.0)
            spin.editingFinished.connect(
                lambda s=spin, k=key: self._on_spin_edit(k, s.value())
            )
            v.addWidget(spin)

        return container

    def _on_spin_edit(self, key: str, new_val: float) -> None:
        cmd = SetFieldCommand(
            self._data, f"{self._path}.{key}", new_val,
            on_change=self.valueChanged.emit,
        )
        self._commands.execute(cmd)

    def _on_add_consumes(self, index: int) -> None:
        combo = self.sender()
        key = combo.itemData(index)
        if not key:
            return
        defaults = {
            "items": [{"item": "", "amount": 1}],   # 初始一行，避免"添加后看不到内容"
            "power": 1.0,
            "liquid": {"liquid": "", "amount": 1},
            "liquids": [{"liquid": "", "amount": 1}],
            "coolant": {"liquid": "", "amount": 1},
            "heat": 1.0,
        }
        cmd = SetFieldCommand(
            self._data, f"{self._path}.{key}", defaults.get(key),
            on_change=self._rebuild_and_notify,
        )
        self._commands.execute(cmd)

    def _remove_consumes(self, key: str) -> None:
        cmd = DeleteFieldCommand(
            self._data, f"{self._path}.{key}",
            on_change=self._rebuild_and_notify,
        )
        self._commands.execute(cmd)

    def _rebuild_and_notify(self) -> None:
        self._rebuild()
        self.valueChanged.emit()
