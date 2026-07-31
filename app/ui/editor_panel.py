"""Editor panel: auto-generated property form for a content item.

Design principles:
- Only show fields in configured groups + fields already in the JSON
- Each group has a "+" button to add more fields from metadata
- Field labels use "中文 (英文)" format
- No dumping of all 272 fields onto the user
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Signal

from ..core.commands import CommandStack, DeleteFieldCommand, SetFieldCommand
from ..core.config_loader import (
    display_name as _format_display_name,
    get_field_docs,
    get_field_groups,
    get_field_names_zh,
)
from ..core.content_store import ContentData
from ..core.form_plan import (
    GroupPlan,
    compute_form_plan,
    get_addable_fields,
    type_default,
)
from ..core.metadata import ClassDef, FieldDef, Metadata
from ..core.project import Project
from ..core.validator import Validator
from .widgets.weapon_array_editor import WeaponArrayEditor
from .widgets.polymorphic_editor import BULLET_TYPES, PolymorphicTypeEditor
from .widgets.check_toggle import CheckToggle
from .widgets.collapsible_group import CollapsibleGroup
from .widgets.field_row import FieldRow
from .widgets.reserved_panel import ReservedPanel
from .widgets.num_spin import NumSpinBox, NumDoubleSpinBox
from .widgets.auto_width_edit import AutoWidthEdit
from .widgets.label_helper import rich_label
from .theme import field_type_property


# 展开状态记忆：{content_name: {group_name: bool}}，跨标签页切换保持。
# 默认只展开 basic 组（见 _is_group_expanded）。
_EXPANDED_STATE: dict[str, dict[str, bool]] = {}

# 删组/禁用能力组时的字段值缓存：{content_name: {group_name: {field: value}}}
_CACHED_VALUES: dict[str, dict[str, dict[str, Any]]] = {}

# 手动删除的组集合：{content_name: set(group_name)}
# 能力组默认始终显示，只有手动删除才消失。
_DELETED_GROUPS: dict[str, set[str]] = {}

# 能力组复选框启用状态：{content_name: set(group_name)}
# 独立于 data 推导——勾选后即使 data 中暂无字段也保持启用。
_ENABLED_GROUPS: dict[str, set[str]] = {}


class EditorPanel(QWidget):
    """Generates a form from metadata for editing a single content item.

    Only shows: configured group fields + fields already in the JSON.
    Each group has a "+" button to add more fields from metadata.
    """

    GROUP_LABELS = {
        "basic": "基础属性",
        "movement": "移动属性",
        "combat": "战斗属性",
        "mining": "采矿",
        "building": "建造",
        "capacity": "容量",
        "boost": "加速",
        "tank": "坦克/履带",
        "flying_engine": "飞行引擎",
        "legs": "腿部",
        "mech": "机甲",
        "segment": "节段",
        "abilities": "技能",
        "appearance": "外观设置",
        "sound": "音效",
        "death": "死亡与残骸",
        "ai": "AI与控制",
        "physics": "物理与碰撞",
        "env": "环境",
        "meta": "研究树与说明",
        "defense": "防御属性",
        "visual": "视觉",
        "build": "建造需求",
        "shooting": "射击模式",
        "targeting": "目标选择",
        "continuous": "持续射击",
        "consumption": "消耗",
        "behavior": "行为",
        "effects": "音效与特效",
        "rendering": "渲染",
        "bullet": "子弹",
    }

    def __init__(
        self,
        content: ContentData,
        metadata: Metadata,
        command_stack: CommandStack,
        validator: Validator,
        project: Project,
    ) -> None:
        super().__init__()
        self._content = content
        self._metadata = metadata
        self._commands = command_stack
        self._validator = validator
        self._project = project
        self._field_widgets: dict[str, QWidget] = {}
        self._dirty = False

        self._field_groups = get_field_groups()
        self._field_names_zh = get_field_names_zh()
        self._field_docs = get_field_docs()
        self._class_def: ClassDef | None = None
        self._form_layout: QVBoxLayout | None = None
        self._setup_ui()

    @property
    def content(self) -> ContentData:
        return self._content

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def refresh_from_data(self) -> None:
        """Rebuild the form from current data. Called after undo/redo."""
        self._rebuild_form()

    # ── UI setup ────────────────────────────────────────────────────────

    # 重命名信号（抬头双击编辑 / 右键重命名）
    rename_requested = Signal(str, str)  # (old_name, new_name)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── 抬头标题栏（v0.2.4.batch2：名字可编辑 + 类型小字底对齐 + 添加字段组按钮）──
        title_bar = QHBoxLayout()
        title_bar.setSpacing(8)

        # 名字（大字粗，可双击原地编辑）
        self._title_label = QLabel(self._content.name)
        self._title_label.setObjectName("editorTitle")
        self._title_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._title_label.setToolTip("双击编辑文件名")
        self._title_label.mouseDoubleClickEvent = self._on_title_double_click  # type: ignore[method-assign]
        self._title_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._title_label.customContextMenuRequested.connect(self._on_title_context_menu)
        title_bar.addWidget(self._title_label)

        # 类型小字（12px 淡化，同行底对齐，去括号）
        type_label = QLabel(self._content.data.get("type", "?"))
        type_label.setObjectName("editorTypeLabel")
        title_bar.addWidget(type_label, 0, Qt.AlignmentFlag.AlignBottom)

        title_bar.addStretch()

        # [添加字段组] 按钮
        self._add_group_btn = QPushButton("+ 添加字段组")
        self._add_group_btn.setObjectName("addGroupBtn")
        self._add_group_btn.setFixedHeight(24)
        self._add_group_btn.clicked.connect(self._show_add_group_menu)
        title_bar.addWidget(self._add_group_btn)

        layout.addLayout(title_bar)

        # Scrollable form area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # QSS background 不传播到 viewport，且 QWidget 默认不渲染 QSS background
        scroll.viewport().setObjectName("editorViewport")
        scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll_widget = QWidget()
        scroll_widget.setObjectName("editorViewport")
        scroll_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._form_layout = QVBoxLayout(scroll_widget)
        self._form_layout.setContentsMargins(8, 8, 8, 8)
        self._form_layout.setSpacing(12)  # 组间 12px（对齐 HTML .group margin-bottom）

        # Get class definition
        content_type = self._content.data.get("type", "")
        try:
            self._class_def = self._metadata.get_class(content_type)
        except KeyError:
            self._form_layout.addWidget(QLabel(f"无法加载类型定义: {content_type}"))
            scroll.setWidget(scroll_widget)
            layout.addWidget(scroll)
            return

        self._rebuild_form()

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

    def _rebuild_form(self) -> None:
        """Rebuild form groups from the computed form plan.

        All "what to show" decisions (group visibility, required/optional
        filtering, subtype inference, locking, expansion) live in
        core.form_plan. This method only renders the plan into Qt widgets.
        """
        if self._class_def is None or self._form_layout is None:
            return

        # Clear existing widgets (groups + notes + stretch)
        while self._form_layout.count() > 0:
            item = self._form_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._field_widgets.clear()

        expanded_state = _EXPANDED_STATE.get(self._content.name)
        deleted_groups = _DELETED_GROUPS.get(self._content.name, set())
        enabled_groups = _ENABLED_GROUPS.get(self._content.name, set())
        plan = compute_form_plan(
            class_def=self._class_def,
            data=self._content.data,
            field_groups=self._field_groups,
            expanded_state=expanded_state,
            group_labels=self.GROUP_LABELS,
            deleted_groups=deleted_groups,
            enabled_groups=enabled_groups,
        )

        for group_plan in plan:
            self._render_group(group_plan)

        # Re-add user notes box
        notes_box = QGroupBox("用户备注")
        notes_layout = QVBoxLayout(notes_box)
        self._notes_edit = QTextEdit()
        self._notes_edit.setMaximumHeight(60)
        self._notes_edit.setPlaceholderText("在此添加备注...")
        # 备注持久化在 data["$notes"]（编辑器私有键；游戏加载 JSON 时忽略未知字段）
        self._notes_edit.setPlainText(self._content.data.get("$notes", "") or "")
        self._notes_edit.textChanged.connect(self._on_notes_changed)
        notes_layout.addWidget(self._notes_edit)
        self._form_layout.addWidget(notes_box)

        self._form_layout.addStretch()

    def _on_notes_changed(self) -> None:
        """备注写入 data['$notes']。不经过命令栈（编辑器私有笔记，无需撤销）。"""
        text = self._notes_edit.toPlainText()
        if text:
            self._content.data["$notes"] = text
        else:
            self._content.data.pop("$notes", None)

    def _render_group(self, plan: GroupPlan) -> None:
        """Render a collapsible group from a GroupPlan."""
        # 能力组：使用 form_plan 计算的 capability_enabled
        # （由 _ENABLED_GROUPS 状态 + data 中字段共同决定）
        cap_enabled = plan.capability_enabled

        group = CollapsibleGroup(
            group_name=plan.group_name,
            title=plan.label,
            english=plan.group_name if plan.group_name != "_other" else "",
            locked=plan.locked,
            expanded=plan.expanded,
            capability=plan.capability,
            capability_enabled=cap_enabled,
        )
        group.add_field_requested.connect(self._show_add_field_menu)
        group.delete_group_requested.connect(self._delete_group)
        group.expandedChanged.connect(self._remember_expanded)
        if plan.capability:
            group.capability_toggled.connect(self._on_capability_toggled)

        # Field rows — 逐行 VBox 布局（替代 QFormLayout 网格）
        rows_layout = QVBoxLayout()
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(4)

        for fp in plan.fields:
            f = fp.field_def
            widget = self._create_field_widget(f)
            if widget is None:
                continue

            # 富文本标签
            zh = self._field_names_zh.get(f.name, "")
            label_widget = rich_label(zh, f.name)
            doc = self._field_docs.get(f.name, "")
            # tooltip 补英文字段名 + field_docs
            en_name = label_widget.property("_en_name") or f.name
            tip_parts = [en_name]
            if doc:
                tip_parts.append(doc)
            tip = "\n".join(tip_parts)
            label_widget.setToolTip(tip)
            widget.setToolTip(tip)

            # 右键菜单
            widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            widget.customContextMenuRequested.connect(
                lambda pos, fn=f.name, w=widget: self._show_field_context_menu(pos, fn, w)
            )

            # 描述档（方案 Y）：标签独占一行，控件撑满下一行
            if f.name == "description":
                rows_layout.addWidget(label_widget)
                rows_layout.addWidget(widget)
                continue

            # 普通行：标签固定宽 + 控件在右
            row_h = QHBoxLayout()
            row_h.setSpacing(8)
            label_widget.setFixedWidth(180)
            row_h.addWidget(label_widget)

            # v0.2.4：仅普通字段行（PRIMITIVE/STRING_REF）统一行高；
            # 复合控件行（weapons 武器列表、子弹等）必须自适应高度，
            # 否则会被压扁成一条窄条
            is_plain_row = f.mode in ("PRIMITIVE", "STRING_REF")
            if is_plain_row:
                ft = field_type_property(f.mode, f.java_type)
                field_row = FieldRow(widget, ft, deletable=fp.deletable)
                if fp.deletable:
                    field_row.deleteRequested.connect(
                        lambda fn=f.name: self._delete_field(fn)
                    )
                row_h.addWidget(field_row)
            else:
                row_h.addWidget(widget)
            row_h.addStretch()
            row_container = QWidget()
            row_container.setLayout(row_h)
            row_h.setContentsMargins(0, 0, 0, 0)  # 去掉 QWidget 默认 margin
            if is_plain_row:
                # 统一普通字段行高（复选框/输入框/色条高度一致）
                row_container.setFixedHeight(26)
            rows_layout.addWidget(row_container)

        group.body_layout.addLayout(rows_layout)

        self._form_layout.addWidget(group)

    # ── 折叠状态记忆 ─────────────────────────────────────────────────────

    def _remember_expanded(self, group_name: str, expanded: bool) -> None:
        _EXPANDED_STATE.setdefault(self._content.name, {})[group_name] = expanded

    # ── 能力开关组联动（v0.2.4.batch2）──────────────────────────────────

    def _on_capability_toggled(self, group_name: str, enabled: bool) -> None:
        """能力开关组复选框状态变化。

        勾选 → 从缓存恢复字段值（无缓存则用 defaults）；
        取消 → 缓存当前字段值，然后从 data 移除。
        联动：勾 mining → 自动勾 capacity（单向）。
        """
        from ..core.form_plan import CAPABILITY_LINKAGE

        content_type = self._content.data.get("type", "")
        groups_config = self._field_groups.get(content_type, {})
        group_def = groups_config.get(group_name, {})
        all_fields = (
            list(group_def.get("required", []))
            + list(group_def.get("default", []))
            + list(group_def.get("optional", []))
        )
        content_name = self._content.name

        if enabled:
            # 从缓存恢复（Bug1 修复）
            cached = _CACHED_VALUES.get(content_name, {}).get(group_name, {})
            defaults = group_def.get("defaults", {})
            for field_name in all_fields:
                if field_name not in self._content.data:
                    # 优先用缓存值，其次 defaults，最后 type_default
                    if field_name in cached:
                        val = cached[field_name]
                    elif field_name in defaults:
                        val = defaults[field_name]
                    else:
                        field_def = next(
                            (f for f in self._class_def.fields if f.name == field_name), None
                        ) if self._class_def else None
                        val = type_default(field_def) if field_def else None
                    if field_name in group_def.get("required", []) or field_name in group_def.get("default", []):
                        cmd = SetFieldCommand(
                            data=self._content.data,
                            path=field_name,
                            new_value=val,
                            on_change=self._mark_dirty,
                        )
                        self._commands.execute(cmd)
            # 恢复 optional 级缓存字段（用户之前手动添加的）
            for field_name, val in cached.items():
                if field_name not in self._content.data and field_name in group_def.get("optional", []):
                    cmd = SetFieldCommand(
                        data=self._content.data,
                        path=field_name,
                        new_value=val,
                        on_change=self._mark_dirty,
                    )
                    self._commands.execute(cmd)

            # 若 required+default 都为空且无缓存，写第一个 optional 作为存在标记
            written = any(fn in self._content.data for fn in all_fields)
            if not written and group_def.get("optional"):
                first_opt = group_def["optional"][0]
                if first_opt not in self._content.data:
                    val = cached.get(first_opt) or defaults.get(first_opt)
                    if val is None:
                        fd = next((f for f in self._class_def.fields if f.name == first_opt), None) if self._class_def else None
                        val = type_default(fd) if fd else None
                    cmd = SetFieldCommand(
                        data=self._content.data, path=first_opt,
                        new_value=val, on_change=self._mark_dirty,
                    )
                    self._commands.execute(cmd)

            # 记入 _ENABLED_GROUPS
            _ENABLED_GROUPS.setdefault(content_name, set()).add(group_name)

            # 单向联动
            linked = CAPABILITY_LINKAGE.get(group_name)
            if linked and linked not in self._get_enabled_capabilities():
                linked_def = groups_config.get(linked, {})
                linked_cached = _CACHED_VALUES.get(content_name, {}).get(linked, {})
                linked_defaults = linked_def.get("defaults", {})
                linked_fields = (
                    list(linked_def.get("required", []))
                    + list(linked_def.get("default", []))
                )
                for fn in linked_fields:
                    if fn not in self._content.data:
                        val = linked_cached.get(fn, linked_defaults.get(fn))
                        if val is None:
                            fd = next(
                                (f for f in self._class_def.fields if f.name == fn), None
                            ) if self._class_def else None
                            val = type_default(fd) if fd else None
                        cmd = SetFieldCommand(
                            data=self._content.data,
                            path=fn,
                            new_value=val,
                            on_change=self._mark_dirty,
                        )
                        self._commands.execute(cmd)
        else:
            # 缓存当前值（Bug1 修复）
            cache = {}
            for field_name in all_fields:
                if field_name in self._content.data:
                    cache[field_name] = self._content.data[field_name]
            if cache:
                _CACHED_VALUES.setdefault(content_name, {})[group_name] = cache
            # 移除该组所有字段
            for field_name in all_fields:
                if field_name in self._content.data:
                    cmd = DeleteFieldCommand(
                        data=self._content.data,
                        path=field_name,
                        on_change=self._mark_dirty,
                    )
                    self._commands.execute(cmd)
            # 从 _ENABLED_GROUPS 移除
            _ENABLED_GROUPS.get(content_name, set()).discard(group_name)

        self._rebuild_form()

    def _get_enabled_capabilities(self) -> set[str]:
        """返回当前 data 中已启用的能力组名集合。"""
        from ..core.form_plan import CAPABILITY_GROUPS
        content_type = self._content.data.get("type", "")
        groups_config = self._field_groups.get(content_type, {})
        enabled = set()
        for gname in CAPABILITY_GROUPS:
            gdef = groups_config.get(gname, {})
            all_fields = (
                set(gdef.get("required", []))
                | set(gdef.get("default", []))
                | set(gdef.get("optional", []))
            )
            if all_fields & set(self._content.data.keys()):
                enabled.add(gname)
        return enabled

    def _delete_group(self, group_name: str) -> None:
        """删除整组字段（通过 CommandStack 可撤销）。

        v0.2.4.batch2：包含 default 字段；弹确认对话框。
        Bug1 修复：缓存字段值。
        Bug2 修复：记入 _DELETED_GROUPS（能力组手动删除后才消失）。
        """
        from PySide6.QtWidgets import QMessageBox
        label = self.GROUP_LABELS.get(group_name, group_name)
        reply = QMessageBox.question(
            self, "删除字段组",
            f"确定删除「{label}」组的所有字段？\n"
            f"字段值将缓存在编辑器中，重新添加组时可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        content_type = self._content.data.get("type", "")
        groups_config = self._field_groups.get(content_type, {})
        group_def = groups_config.get(group_name, {})
        names = (
            list(group_def.get("required", []))
            + list(group_def.get("default", []))
            + list(group_def.get("optional", []))
        )
        content_name = self._content.name

        # Bug1：缓存当前值
        cache = {}
        for name in names:
            if name in self._content.data:
                cache[name] = self._content.data[name]
        if cache:
            _CACHED_VALUES.setdefault(content_name, {})[group_name] = cache

        # Bug2：记入已删除集合 + 从启用集合移除
        _DELETED_GROUPS.setdefault(content_name, set()).add(group_name)
        _ENABLED_GROUPS.get(content_name, set()).discard(group_name)

        deleted = False
        for name in names:
            if name in self._content.data:
                cmd = DeleteFieldCommand(
                    data=self._content.data,
                    path=name,
                    on_change=self._mark_dirty,
                )
                self._commands.execute(cmd)
                deleted = True
        if deleted:
            self._rebuild_form()

    def _show_add_field_menu(self, group_name: str) -> None:
        """Popup menu listing available optional fields for this group."""
        if self._class_def is None:
            return

        candidates = get_addable_fields(
            class_def=self._class_def,
            data=self._content.data,
            field_groups=self._field_groups,
            group_name=group_name,
        )

        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        count = 0
        for f in candidates:
            action = menu.addAction(self._display_name(f.name))
            action.setData(f.name)
            doc = self._field_docs.get(f.name, "")
            if doc:
                action.setToolTip(doc)
            count += 1
            if count >= 60:
                break

        if count == 0:
            menu.addAction("(无更多可用字段)").setEnabled(False)

        # Position the menu near the '+' button that was clicked
        # Bug3 修复：sender 是 CollapsibleGroup（信号转发），
        # 需要找到组内的 _add_btn 来定位。
        sender = self.sender()
        pos = None
        if isinstance(sender, CollapsibleGroup):
            add_btn = getattr(sender, '_add_btn', None)
            if add_btn:
                pos = add_btn.mapToGlobal(add_btn.rect().bottomLeft())
        elif isinstance(sender, QPushButton):
            pos = sender.mapToGlobal(sender.rect().bottomLeft())
        if pos is None:
            pos = self.mapToGlobal(self.rect().center())

        chosen = menu.exec(pos)
        if chosen and chosen.data():
            field_name = chosen.data()
            field_def = next(
                (f for f in self._class_def.fields if f.name == field_name), None
            )
            if field_def:
                # Use configured default if available, else type zero value
                default_val = self._get_group_default(group_name, field_name)
                new_value = (
                    default_val
                    if default_val is not None
                    else type_default(field_def)
                )
                # 走命令栈，保证与删除对称（可撤销）
                cmd = SetFieldCommand(
                    data=self._content.data,
                    path=field_name,
                    new_value=new_value,
                    on_change=self._mark_dirty,
                )
                self._commands.execute(cmd)
                self._rebuild_form()

    def _get_group_default(self, group_name: str, field_name: str) -> Any:
        """Look up a configured default value for a field in a group."""
        content_type = self._content.data.get("type", "")
        groups_config = self._field_groups.get(content_type, {})
        group_def = groups_config.get(group_name, {})
        defaults = group_def.get("defaults", {})
        return defaults.get(field_name)

    # ── field widget creation ───────────────────────────────────────────

    def _create_field_widget(self, field_def: FieldDef) -> QWidget | None:
        current_value = self._content.data.get(field_def.name)

        if field_def.mode == "PRIMITIVE":
            return self._create_primitive_widget(field_def, current_value)
        elif field_def.mode == "STRING_REF":
            return self._create_ref_widget(field_def, current_value)
        elif field_def.mode == "ARRAY":
            if field_def.name == "weapons":
                return self._create_weapons_widget()
            return ReservedPanel("数组字段")
        elif field_def.mode == "INLINE_OBJECT":
            if field_def.name == "bullet":
                return self._create_bullet_editor()
            return ReservedPanel("内联对象")
        return None

    def _create_primitive_widget(self, field_def: FieldDef, value: Any) -> QWidget:
        java_type = field_def.java_type

        if java_type == "boolean":
            cb = CheckToggle()
            cb.setChecked(bool(value) if value is not None else False)
            cb.toggled.connect(
                lambda checked, n=field_def.name: self._on_field_changed(n, checked)
            )
            self._field_widgets[field_def.name] = cb
            return cb

        if java_type in ("int", "long", "short"):
            spin = NumSpinBox()
            spin.setRange(-999999, 999999)
            spin.setFixedWidth(70)  # 短值档
            spin.setValue(int(value) if value is not None else 0)
            spin.valueChanged.connect(
                lambda v, n=field_def.name: self._on_field_changed(n, v)
            )
            self._field_widgets[field_def.name] = spin
            return spin

        if java_type in ("float", "double"):
            spin = NumDoubleSpinBox()
            spin.setRange(-999999.0, 999999.0)
            spin.setDecimals(3)
            spin.setFixedWidth(70)  # 短值档
            spin.setValue(float(value) if value is not None else 0.0)
            spin.valueChanged.connect(
                lambda v, n=field_def.name: self._on_field_changed(n, v)
            )
            self._field_widgets[field_def.name] = spin
            return spin

        if java_type == "Color":
            return self._create_color_widget(field_def, value)

        # 描述档：多行文本框，撑满整列
        if field_def.name == "description":
            desc = QTextEdit()
            desc.setFixedHeight(70)  # 初始 3 行
            desc.setPlainText(str(value) if value else "")
            desc.textChanged.connect(
                lambda n=field_def.name: self._on_field_changed(
                    n, desc.toPlainText()
                )
            )
            self._field_widgets[field_def.name] = desc
            return desc

        # 名称档：自动撑宽（name 字段只读镜像文件名，ADR-009）
        edit = AutoWidthEdit()
        edit.setText(str(value) if value is not None else "")
        if field_def.name == "name":
            edit.setReadOnly(True)
            edit.setToolTip(
                "内容标识符由文件名决定，不能在此修改。\n"
                "想改身份？请双击抬头名字或右键重命名。"
            )
        else:
            edit.textChanged.connect(
                lambda t, n=field_def.name: self._on_field_changed(n, t)
            )
        self._field_widgets[field_def.name] = edit
        return edit

    def _create_ref_widget(self, field_def: FieldDef, value: Any) -> QWidget:
        combo = QComboBox()
        combo.setFixedWidth(150)  # 名称档（引用下拉略宽于数字）
        combo.setEditable(True)
        if field_def.ref_source:
            try:
                instances = self._metadata.list_instances(field_def.ref_source)
                combo.addItems([""] + instances)
            except Exception:
                pass
        if value is not None:
            idx = combo.findText(str(value))
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(str(value))
        combo.currentTextChanged.connect(
            lambda t, n=field_def.name: self._on_field_changed(n, t if t else None)
        )
        self._field_widgets[field_def.name] = combo
        return combo

    def _create_color_widget(self, field_def: FieldDef, value: Any) -> QWidget:
        """Create a color picker button for Color fields.

        Mindustry stores colors as hex strings (e.g. 'ff7700') or
        rgba objects {'r': 1, 'g': 0.5, 'b': 0, 'a': 1}.
        We display a clickable color swatch button that opens QColorDialog.
        """
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QColorDialog

        container = QWidget()
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)

        # Parse current color value
        color = QColor(255, 255, 255)
        display_text = ""
        if isinstance(value, str) and value:
            display_text = value
            hex_str = value.lstrip("#")
            if len(hex_str) == 6:
                color = QColor(f"#{hex_str}")
            elif len(hex_str) == 8:
                color = QColor(f"#{hex_str[:6]}")
        elif isinstance(value, dict):
            r = int(value.get("r", 1) * 255)
            g = int(value.get("g", 1) * 255)
            b = int(value.get("b", 1) * 255)
            color = QColor(r, g, b)
            display_text = f"{r:02x}{g:02x}{b:02x}"

        # Color swatch button（背景色动态 hex 为唯一内联例外，描边/圆角走 QSS）
        swatch = QPushButton()
        swatch.setObjectName("colorSwatch")
        swatch.setFixedSize(48, 24)
        swatch.setStyleSheet(f"background-color: {color.name()};")

        # Text label showing the hex value
        hex_label = QLineEdit(display_text)
        hex_label.setMaximumWidth(100)

        def on_swatch_click():
            chosen = QColorDialog.getColor(color, self, "选择颜色")
            if chosen.isValid():
                hex_val = chosen.name().lstrip("#")
                hex_label.setText(hex_val)
                swatch.setStyleSheet(f"background-color: {chosen.name()};")
                self._on_field_changed(field_def.name, hex_val)

        def on_text_edit(text: str):
            text = text.strip().lstrip("#")
            if len(text) == 6:
                try:
                    int(text, 16)
                    c = QColor(f"#{text}")
                    swatch.setStyleSheet(f"background-color: {c.name()};")
                    self._on_field_changed(field_def.name, text)
                except ValueError:
                    pass

        swatch.clicked.connect(on_swatch_click)
        hex_label.textChanged.connect(on_text_edit)

        h_layout.addWidget(swatch)
        h_layout.addWidget(hex_label)
        h_layout.addStretch()

        self._field_widgets[field_def.name] = container
        return container

    def _create_weapons_widget(self) -> QWidget:
        """Create a WeaponArrayEditor for the weapons field."""
        # Ensure the weapons array exists
        if "weapons" not in self._content.data:
            self._content.data["weapons"] = []

        editor = WeaponArrayEditor(
            data=self._content.data,
            path="weapons",
            command_stack=self._commands,
            metadata=self._metadata,
            project=self._project,
        )
        editor.valueChanged.connect(self._mark_dirty)
        self._field_widgets["weapons"] = editor
        return editor

    def _create_bullet_editor(self) -> QWidget:
        """Create a PolymorphicTypeEditor for the bullet field."""
        editor = PolymorphicTypeEditor(
            data=self._content.data,
            path="bullet",
            type_choices=BULLET_TYPES,
            command_stack=self._commands,
            title="子弹",
            type_label="类型",
        )
        editor.valueChanged.connect(self._mark_dirty)
        self._field_widgets["bullet"] = editor
        return editor

    def _show_field_context_menu(self, pos, field_name: str, widget: QWidget) -> None:
        """Right-click context menu on a field widget: delete field."""
        menu = QMenu(self)
        delete_action = menu.addAction(f"删除字段 \"{self._display_name(field_name)}\"")
        chosen = menu.exec(widget.mapToGlobal(pos))
        if chosen == delete_action:
            self._delete_field(field_name)

    def _delete_field(self, field_name: str) -> None:
        """删除单个字段（可撤销），红 X 按钮与右键菜单共用。"""
        if field_name in self._content.data:
            cmd = DeleteFieldCommand(
                data=self._content.data,
                path=field_name,
                on_change=self._mark_dirty,
            )
            self._commands.execute(cmd)
            self._rebuild_form()

    # ── data operations ─────────────────────────────────────────────────

    def _on_field_changed(self, field_name: str, new_value: Any) -> None:
        cmd = SetFieldCommand(
            data=self._content.data,
            path=field_name,
            new_value=new_value,
            on_change=self._mark_dirty,
        )
        self._commands.execute(cmd)

        # Real-time validation: red border + tooltip on error
        self._validate_field_widget(field_name, new_value)

    def _validate_field_widget(self, field_name: str, value: Any) -> None:
        """Apply validation styling to the widget for a specific field."""
        widget = self._field_widgets.get(field_name)
        if widget is None or self._class_def is None:
            return

        # Find field definition
        field_def = self._find_field_def(field_name)
        if field_def is None:
            return

        issue = self._validator.validate_field_value(field_def, value)
        has_error = issue is not None
        # 走 QSS 属性选择器 [error="true"]，不写内联 setStyleSheet
        widget.setProperty("error", "true" if has_error else "")
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        if has_error:
            widget.setToolTip(issue.message)
        else:
            doc = self._field_docs.get(field_name, "")
            if doc:
                widget.setToolTip(doc)

    def _find_field_def(self, field_name: str) -> FieldDef | None:
        """Find a field definition by name in the current class."""
        if self._class_def is None:
            return None
        for f in self._class_def.fields:
            if f.name == field_name:
                return f
        return None

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._project.is_dirty = True

    def save(self) -> int:
        """保存当前内容（带验证），返回验证错误数。

        与主窗口 Ctrl+S 路径（session.save_contents）等价：
        写盘 + 校验 + 清空 dirty 标志。
        """
        issues = self._validator.validate(self._content.data, "content")
        errs = [iss for iss in issues if iss.severity == "error"]
        self._project.contents.save(
            self._content.name,
            self._content.data,
            self._content.category,
        )
        self._dirty = False
        self._project.is_dirty = False
        return len(errs)

    def mark_saved(self) -> None:
        """Clear the dirty flag without writing (session already persisted)."""
        self._dirty = False

    def error_count(self) -> int:
        """返回当前内容的验证错误数量。"""
        issues = self._validator.validate(self._content.data, "content")
        return sum(1 for iss in issues if iss.severity == "error")

    def jump_to_first_error(self) -> bool:
        """滚动并高亮第一个错误字段。返回是否找到错误。"""
        issues = self._validator.validate(self._content.data, "content")
        err_fields = [iss.path.split("[")[0].split(".")[0]
                      for iss in issues if iss.severity == "error"]
        for fname in err_fields:
            widget = self._field_widgets.get(fname)
            if widget is not None:
                widget.setFocus()
                # 滚动到控件可见
                self._scroll_to_widget(widget)
                # 短暂高亮
                widget.setProperty("error", "true")
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                return True
        return False

    def _scroll_to_widget(self, widget: QWidget) -> None:
        """把控件滚动到编辑区可见范围。"""
        scroll = self._find_scroll_area()
        if scroll is not None:
            scroll.ensureWidgetVisible(widget, 50, 50)

    def _find_scroll_area(self):
        """向上查找包裹表单的 QScrollArea。"""
        from PySide6.QtWidgets import QScrollArea
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                return parent
            parent = parent.parent()
        return None

    # ── display name: delegates to config_loader (respects display mode) ──

    def _display_name(self, field_name: str) -> str:
        return _format_display_name(field_name, self._field_names_zh)

    # ── 抬头交互（v0.2.4.batch2）─────────────────────────────────────────

    def _on_title_double_click(self, event) -> None:  # noqa: N802
        """双击名字 → 原地变成 QLineEdit 编辑。"""
        old_name = self._content.name
        edit = QLineEdit(old_name, self._title_label.parent())
        edit.setFixedWidth(max(self._title_label.width(), 120))
        edit.setFixedHeight(self._title_label.height())
        edit.move(self._title_label.pos())
        edit.show()
        edit.setFocus()
        edit.selectAll()
        self._title_label.hide()

        def finish():
            new_name = edit.text().strip()
            edit.deleteLater()
            self._title_label.show()
            if new_name and new_name != old_name:
                self.rename_requested.emit(old_name, new_name)

        edit.editingFinished.connect(finish)
        edit.returnPressed.connect(edit.clearFocus)

    def _on_title_context_menu(self, pos) -> None:
        """右键名字 → 重命名菜单。"""
        menu = QMenu(self)
        menu.addAction("重命名...", self._trigger_rename_via_dialog)
        menu.exec(self._title_label.mapToGlobal(pos))

    def _trigger_rename_via_dialog(self) -> None:
        """通过对话框触发重命名（走 file_tree 的 _rename_content 逻辑）。"""
        from PySide6.QtWidgets import QInputDialog
        import re
        old_name = self._content.name
        new_name, ok = QInputDialog.getText(
            self, "重命名", "新名称 (英文, 小写+连字符):", text=old_name
        )
        if ok and new_name and new_name.strip() != old_name:
            self.rename_requested.emit(old_name, new_name.strip())

    def _show_add_group_menu(self) -> None:
        """抬头 [添加字段组] 按钮 → 列出当前未显示的可见组。"""
        if self._class_def is None:
            return

        content_type = self._content.data.get("type", "")
        groups_config = self._field_groups.get(content_type, {})
        from ..core.form_plan import infer_subtype, group_visible
        subtype = infer_subtype(content_type, self._content.data)

        # 当前已显示的组名
        current_groups = set()
        for i in range(self._form_layout.count()):
            w = self._form_layout.itemAt(i).widget()
            if isinstance(w, CollapsibleGroup):
                current_groups.add(w.group_name)

        menu = QMenu(self)
        count = 0
        for group_name, group_def in groups_config.items():
            if group_name in current_groups:
                continue
            if not group_visible(group_def, subtype):
                continue
            label = self.GROUP_LABELS.get(group_name, group_name)
            action = menu.addAction(f"{label}  ({group_name})")
            action.setData(group_name)
            count += 1

        if count == 0:
            menu.addAction("(无更多可添加的字段组)").setEnabled(False)

        chosen = menu.exec(self._add_group_btn.mapToGlobal(
            self._add_group_btn.rect().bottomLeft()
        ))
        if chosen and chosen.data():
            group_name = chosen.data()
            content_name = self._content.name
            group_def = groups_config.get(group_name, {})

            # Bug2：从已删除集合移除
            _DELETED_GROUPS.get(content_name, set()).discard(group_name)

            # Bug1：从缓存恢复字段值
            cached = _CACHED_VALUES.get(content_name, {}).get(group_name, {})
            defaults = group_def.get("defaults", {})
            all_fields = (
                list(group_def.get("required", []))
                + list(group_def.get("default", []))
                + list(group_def.get("optional", []))
            )
            # 恢复 required + default 级字段
            for field_name in all_fields:
                if field_name not in self._content.data:
                    if field_name in cached:
                        val = cached[field_name]
                    elif field_name in defaults:
                        val = defaults[field_name]
                    else:
                        field_def = next(
                            (f for f in self._class_def.fields if f.name == field_name), None
                        ) if self._class_def else None
                        val = type_default(field_def) if field_def else None
                    if field_name in group_def.get("required", []) or field_name in group_def.get("default", []):
                        cmd = SetFieldCommand(
                            data=self._content.data,
                            path=field_name,
                            new_value=val,
                            on_change=self._mark_dirty,
                        )
                        self._commands.execute(cmd)
            # 恢复 optional 级缓存字段（用户之前手动添加的）
            for field_name, val in cached.items():
                if field_name not in self._content.data and field_name in group_def.get("optional", []):
                    cmd = SetFieldCommand(
                        data=self._content.data,
                        path=field_name,
                        new_value=val,
                        on_change=self._mark_dirty,
                    )
                    self._commands.execute(cmd)

            # Bug3 修复：若 required+default 都为空且无缓存，写第一个 optional 作为存在标记
            written = any(fn in self._content.data for fn in all_fields)
            if not written and group_def.get("optional"):
                first_opt = group_def["optional"][0]
                if first_opt not in self._content.data:
                    val = cached.get(first_opt) or defaults.get(first_opt)
                    if val is None:
                        fd = next((f for f in self._class_def.fields if f.name == first_opt), None) if self._class_def else None
                        val = type_default(fd) if fd else None
                    cmd = SetFieldCommand(
                        data=self._content.data, path=first_opt,
                        new_value=val, on_change=self._mark_dirty,
                    )
                    self._commands.execute(cmd)

            # 能力组：记入 _ENABLED_GROUPS
            from ..core.form_plan import CAPABILITY_GROUPS
            if group_name in CAPABILITY_GROUPS:
                _ENABLED_GROUPS.setdefault(content_name, set()).add(group_name)

            self._rebuild_form()

    # ── helpers ─────────────────────────────────────────────────────────
