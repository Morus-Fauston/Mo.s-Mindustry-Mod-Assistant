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
    QFrame,
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
from .theme import field_type_property, get_tokens


# 展开状态记忆：{content_name: {group_name: bool}}，跨标签页切换保持。
# 默认只展开 basic 组（见 _is_group_expanded）。
_EXPANDED_STATE: dict[str, dict[str, bool]] = {}


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

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Title
        title = QLabel(f"{self._content.name}  ({self._content.data.get('type', '?')})")
        title.setObjectName("editorTitle")
        layout.addWidget(title)

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
        plan = compute_form_plan(
            class_def=self._class_def,
            data=self._content.data,
            field_groups=self._field_groups,
            expanded_state=expanded_state,
            group_labels=self.GROUP_LABELS,
        )

        for group_plan in plan:
            self._render_group(group_plan)

        # Re-add user notes box
        notes_box = QGroupBox("用户备注")
        notes_layout = QVBoxLayout(notes_box)
        self._notes_edit = QTextEdit()
        self._notes_edit.setMaximumHeight(60)
        self._notes_edit.setPlaceholderText("在此添加备注...")
        notes_layout.addWidget(self._notes_edit)
        self._form_layout.addWidget(notes_box)

        self._form_layout.addStretch()

    def _render_group(self, plan: GroupPlan) -> None:
        """Render a collapsible group from a GroupPlan."""
        group = CollapsibleGroup(
            group_name=plan.group_name,
            title=plan.label,
            english=plan.group_name if plan.group_name != "_other" else "",
            locked=plan.locked,
            expanded=plan.expanded,
        )
        group.add_field_requested.connect(self._show_add_field_menu)
        group.delete_group_requested.connect(self._delete_group)
        # 折叠状态变化时记忆
        group._chevron.clicked.connect(  # noqa: SLF001
            lambda gn=plan.group_name, g=group: self._remember_expanded(gn, g.expanded)
        )

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
            if doc:
                label_widget.setToolTip(doc)
                widget.setToolTip(doc)

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
            label_widget.setFixedWidth(150)
            row_h.addWidget(label_widget)

            if f.mode in ("PRIMITIVE", "STRING_REF"):
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
            rows_layout.addWidget(row_container)

        group.body_layout.addLayout(rows_layout)

        self._form_layout.addWidget(group)
    def _add_group_separator(self) -> None:
        """在 _form_layout 末尾插入一条 1px 分隔线（组间/块间）。"""
        sep = QFrame()
        sep.setObjectName("groupSeparator")
        sep.setFixedHeight(1)
        sep.setAutoFillBackground(True)  # QFrame 默认不填充背景→QSS background 不可见
        self._form_layout.addWidget(sep)
    # ── 折叠状态记忆 ─────────────────────────────────────────────────────

    def _remember_expanded(self, group_name: str, expanded: bool) -> None:
        _EXPANDED_STATE.setdefault(self._content.name, {})[group_name] = expanded

    def _delete_group(self, group_name: str) -> None:
        """删除整组字段（通过 CommandStack 可撤销）。"""
        content_type = self._content.data.get("type", "")
        groups_config = self._field_groups.get(content_type, {})
        group_def = groups_config.get(group_name, {})
        names = list(group_def.get("required", [])) + list(group_def.get("optional", []))
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
        sender = self.sender()
        if sender and isinstance(sender, QPushButton):
            pos = sender.mapToGlobal(sender.rect().bottomLeft())
        else:
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
                if default_val is not None:
                    self._content.data[field_name] = default_val
                else:
                    self._content.data[field_name] = type_default(field_def)
                self._mark_dirty()
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

        # 名称档：自动撑宽
        edit = AutoWidthEdit()
        edit.setText(str(value) if value is not None else "")
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

        # Color swatch button
        swatch = QPushButton()
        swatch.setFixedSize(48, 24)
        swatch.setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid #999; border-radius: 3px;"
        )

        # Text label showing the hex value
        hex_label = QLineEdit(display_text)
        hex_label.setMaximumWidth(100)

        def on_swatch_click():
            chosen = QColorDialog.getColor(color, self, "选择颜色")
            if chosen.isValid():
                hex_val = chosen.name().lstrip("#")
                hex_label.setText(hex_val)
                swatch.setStyleSheet(
                    f"background-color: {chosen.name()}; border: 1px solid #999; border-radius: 3px;"
                )
                self._on_field_changed(field_def.name, hex_val)

        def on_text_edit(text: str):
            text = text.strip().lstrip("#")
            if len(text) == 6:
                try:
                    int(text, 16)
                    c = QColor(f"#{text}")
                    swatch.setStyleSheet(
                        f"background-color: {c.name()}; border: 1px solid #999; border-radius: 3px;"
                    )
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

    def save(self) -> None:
        self._project.contents.save(
            self._content.name,
            self._content.data,
            self._content.category,
        )
        self._dirty = False

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

    # ── helpers ─────────────────────────────────────────────────────────
