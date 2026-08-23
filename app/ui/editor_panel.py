"""Editor panel: auto-generated property form for a content item.

Design principles:
- Only show fields in configured groups + fields already in the JSON
- Each group has a "+" button to add more fields from metadata
- Field labels use "中文 (英文)" format
- No dumping of all 272 fields onto the user
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Signal

from ..core.commands import CommandStack, DeleteFieldCommand, ReplaceDataCommand, SetFieldCommand
from ..core.config_loader import (
    display_name as _format_display_name,
    get_field_docs,
    get_field_groups,
    get_field_names_zh,
    get_content_names_zh,
)
from ..core.content_store import ContentData
from ..core.form_plan import (
    GroupPlan,
    compute_form_plan,
    get_addable_fields,
    type_default,
)
from ..core.field_dependencies import inactive_dependencies
from ..core.group_ops import (
    cache_group_fields,
    group_field_names,
    remove_group_fields,
    restore_group_fields,
)
from ..core.metadata import ClassDef, FieldDef, Metadata, normalize_content_type
from ..core.json_draft import format_json_draft, locate_path_line, parse_json_object
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
from .widgets.color_picker import ColorPicker
from .widgets.field_widget_factory import create_value_widget
from .widgets.label_helper import rich_label


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


# widgets 路由 → 组色条 fieldType 映射（E-2 / ADR-012 19.3）
_WIDGET_GROUP_TYPES = {
    "resource_list": "arr",
    "consumes": "obj",
    "resource_slot": "ref",
    "tech_ref": "ref",
}


def _group_bar_field_type(field_def, widget_cfg) -> str:
    """复合字段的组色条 fieldType（E-2）。

    widgets 路由优先（resource_list→arr 等）；无路由按字段模式：
    ARRAY→arr，INLINE_OBJECT→obj，其余按值猜。
    """
    if isinstance(widget_cfg, dict):
        wtype = widget_cfg.get("widget")
        if wtype in _WIDGET_GROUP_TYPES:
            return _WIDGET_GROUP_TYPES[wtype]
    if field_def.mode == "ARRAY":
        return "arr"
    if field_def.mode == "INLINE_OBJECT":
        return "obj"
    return "obj"  # 兜底：复合字段多数是对象形态


class EditorPanel(QWidget):
    """Generates a form from metadata for editing a single content item.

    Only shows: configured group fields + fields already in the JSON.
    Each group has a "+" button to add more fields from metadata.
    """

    GROUP_LABELS = {
        "basic": "基础属性",
        "movement": "移动属性",
        "combat": "战斗属性",
        "weapons_range": "武器与射程",
        "target_selection": "目标选择",
        "attack_behavior": "攻击行为",
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
        "tech_tree": "科技树",
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
        self._view_mode = "form"
        self._loading_json = False
        self._json_had_issues = False
        self._json_user_collapsed = False
        self._json_apply_timer = QTimer(self)
        self._json_apply_timer.setSingleShot(True)
        self._json_apply_timer.setInterval(500)
        self._json_apply_timer.timeout.connect(self._apply_json_draft)

        self._field_groups = get_field_groups()
        self._field_names_zh = get_field_names_zh()
        self._content_names_zh = get_content_names_zh()
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
        if self._sync_class_definition():
            self._rebuild_form()
        else:
            self._render_unknown_type()
        if self._view_mode == "json":
            self._load_json_from_data()

    # ── UI setup ────────────────────────────────────────────────────────

    # 重命名信号（抬头双击编辑 / 右键重命名）
    rename_requested = Signal(str, str)  # (old_name, new_name)
    # v0.2.4.batch4：数据变更信号（通知预览实时刷新）
    data_changed = Signal()

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
        self._type_label = QLabel(self._content.data.get("type", "?"))
        self._type_label.setObjectName("editorTypeLabel")
        title_bar.addWidget(self._type_label, 0, Qt.AlignmentFlag.AlignBottom)

        title_bar.addStretch()

        self._form_mode_btn = QPushButton("表单")
        self._form_mode_btn.setObjectName("formModeBtn")
        self._form_mode_btn.setCheckable(True)
        self._form_mode_btn.setChecked(True)
        self._form_mode_btn.clicked.connect(lambda: self._set_view_mode("form"))
        title_bar.addWidget(self._form_mode_btn)

        self._json_mode_btn = QPushButton("JSON")
        self._json_mode_btn.setObjectName("jsonModeBtn")
        self._json_mode_btn.setCheckable(True)
        self._json_mode_btn.clicked.connect(lambda: self._set_view_mode("json"))
        title_bar.addWidget(self._json_mode_btn)

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
        self._scroll_area = scroll  # 保存引用，rebuild 时恢复滚动位置
        scroll_widget = QWidget()
        scroll_widget.setObjectName("editorViewport")
        scroll_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._form_layout = QVBoxLayout(scroll_widget)
        self._form_layout.setContentsMargins(8, 8, 8, 8)
        self._form_layout.setSpacing(12)  # 组间 12px（对齐 HTML .group margin-bottom）

        # Get class definition
        if self._sync_class_definition():
            self._rebuild_form()
        else:
            self._render_unknown_type()

        scroll.setWidget(scroll_widget)
        self._editor_stack = QStackedWidget()
        self._editor_stack.addWidget(scroll)
        self._editor_stack.addWidget(self._build_json_page())
        layout.addWidget(self._editor_stack)

    def _build_json_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("jsonOutputPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.addStretch()
        self._format_json_btn = QPushButton("格式化 JSON")
        self._format_json_btn.setObjectName("formatJsonBtn")
        self._format_json_btn.clicked.connect(self._format_json_draft)
        toolbar.addWidget(self._format_json_btn)
        self._json_issue_toggle = QPushButton("问题")
        self._json_issue_toggle.setObjectName("jsonIssuesToggle")
        self._json_issue_toggle.setCheckable(True)
        self._json_issue_toggle.clicked.connect(self._toggle_json_issues)
        toolbar.addWidget(self._json_issue_toggle)
        layout.addLayout(toolbar)

        self._json_syntax_status = QLabel()
        self._json_syntax_status.setObjectName("jsonSyntaxStatus")
        self._json_syntax_status.hide()
        layout.addWidget(self._json_syntax_status)

        self._json_splitter = QSplitter(Qt.Orientation.Vertical)
        self._json_text = QPlainTextEdit()
        self._json_text.setObjectName("jsonOutputEditor")
        self._json_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._json_text.textChanged.connect(self._on_json_text_changed)
        self._json_splitter.addWidget(self._json_text)

        self._json_issues = QListWidget()
        self._json_issues.setObjectName("jsonIssuesList")
        self._json_issues.itemClicked.connect(self._jump_to_json_issue)
        self._json_issues.itemActivated.connect(self._jump_to_json_issue)
        self._json_issues.hide()
        self._json_splitter.addWidget(self._json_issues)
        layout.addWidget(self._json_splitter)
        return page

    def _set_view_mode(self, mode: str) -> None:
        is_json = mode == "json"
        self._form_mode_btn.setChecked(not is_json)
        self._json_mode_btn.setChecked(is_json)
        if mode == self._view_mode:
            return
        self._view_mode = mode
        self._editor_stack.setCurrentIndex(1 if is_json else 0)
        if is_json:
            self._load_json_from_data()
        else:
            self._json_apply_timer.stop()

    def _load_json_from_data(self) -> None:
        self._loading_json = True
        try:
            self._json_text.setPlainText(json.dumps(self._content.data, ensure_ascii=False, indent=2) + "\n")
        finally:
            self._loading_json = False
        self._set_json_error(None)
        self._refresh_json_issues(self._content.data)

    def _on_json_text_changed(self) -> None:
        if self._loading_json:
            return
        result = parse_json_object(self._json_text.toPlainText())
        if result.data is None:
            self._json_apply_timer.stop()
            self._set_json_error(result.error)
            self._refresh_json_issues(None)
            return
        self._set_json_error(None)
        self._refresh_json_issues(result.data)
        self._json_apply_timer.start()

    def _apply_json_draft(self) -> None:
        result = parse_json_object(self._json_text.toPlainText())
        if result.data is None:
            self._set_json_error(result.error)
            return
        if result.data != self._content.data:
            self._commands.execute(
                ReplaceDataCommand(
                    self._content.data,
                    result.data,
                    on_change=self._on_json_data_changed,
                )
            )
        self._refresh_json_issues(result.data)

    def _on_json_data_changed(self) -> None:
        self._mark_dirty()
        if self._sync_class_definition():
            self._rebuild_form()
        else:
            self._render_unknown_type()
        self.data_changed.emit()

    def _format_json_draft(self) -> None:
        source = self._json_text.toPlainText()
        formatted, error = format_json_draft(source)
        if error:
            self._set_json_error("JSON 语法错误，无法格式化")
            return
        self._loading_json = True
        try:
            self._json_text.setPlainText(formatted)
        finally:
            self._loading_json = False
        self._set_json_error(None)
        self._on_json_text_changed()

    def _set_json_error(self, message: str | None) -> None:
        has_error = bool(message)
        self._json_text.setProperty("error", "true" if has_error else "")
        self._json_text.style().unpolish(self._json_text)
        self._json_text.style().polish(self._json_text)
        self._json_syntax_status.setText(message or "")
        self._json_syntax_status.setVisible(has_error)

    def _refresh_json_issues(self, data: dict[str, Any] | None) -> None:
        issues = self._validator.validate(data, "content") if data is not None else []
        self._json_issues.clear()
        for issue in issues:
            severity = "错误" if issue.severity == "error" else "警告"
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, issue.path)
            self._json_issues.addItem(item)
            row = QWidget()
            row.setProperty("severity", issue.severity)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 5, 8, 5)
            label = QLabel(f"{severity}：{issue.message}")
            label.setWordWrap(True)
            row_layout.addWidget(label)
            item.setSizeHint(row.sizeHint())
            self._json_issues.setItemWidget(item, row)

        has_issues = bool(issues)
        if not has_issues:
            self._json_had_issues = False
            self._json_user_collapsed = False
            self._json_issues.hide()
            self._json_issue_toggle.setChecked(False)
            return
        if not self._json_had_issues and not self._json_user_collapsed:
            self._json_issues.show()
            self._json_issue_toggle.setChecked(True)
            self._json_splitter.setSizes([300, 120])
        self._json_had_issues = True

    def _toggle_json_issues(self, checked: bool) -> None:
        self._json_user_collapsed = not checked
        self._json_issues.setVisible(checked and self._json_issues.count() > 0)
        if checked:
            self._json_splitter.setSizes([300, 120])

    def _jump_to_json_issue(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(path, str):
            return
        location = locate_path_line(self._json_text.toPlainText(), path)
        if location.line is None:
            return
        block = self._json_text.document().findBlockByNumber(location.line - 1)
        cursor = QTextCursor(block)
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        self._json_text.setTextCursor(cursor)
        self._json_text.centerCursor()
        self._json_text.setFocus()

    def _sync_class_definition(self) -> bool:
        content_type = self._content.data.get("type", "")
        self._type_label.setText(content_type or "?")
        try:
            self._class_def = self._metadata.get_class(content_type)
        except KeyError:
            self._class_def = None
            return False
        return True

    def _render_unknown_type(self) -> None:
        if self._form_layout is None:
            return
        while self._form_layout.count() > 0:
            item = self._form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._field_widgets.clear()
        self._form_layout.addWidget(QLabel(f"无法加载类型定义: {self._content.data.get('type', '')}"))

    def _rebuild_form(self) -> None:
        """Rebuild form groups from the computed form plan.

        All "what to show" decisions (group visibility, required/optional
        filtering, subtype inference, locking, expansion) live in
        core.form_plan. This method only renders the plan into Qt widgets.
        """
        if self._class_def is None or self._form_layout is None:
            return

        # 保存滚动位置（rebuild 后恢复，避免跳顶）
        scroll_val = 0
        if hasattr(self, "_scroll_area") and self._scroll_area is not None:
            vbar = self._scroll_area.verticalScrollBar()
            if vbar is not None:
                scroll_val = vbar.value()

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

        # 恢复滚动位置（延迟到事件循环，等 deleteLater 完成布局计算）
        if hasattr(self, "_scroll_area") and self._scroll_area is not None:
            vbar = self._scroll_area.verticalScrollBar()
            if vbar is not None:
                QTimer.singleShot(0, lambda v=scroll_val: vbar.setValue(v))

    def _on_notes_changed(self) -> None:
        """备注写入 data['$notes']。不经过命令栈（编辑器私有笔记，无需撤销）。"""
        text = self._notes_edit.toPlainText()
        if text:
            self._content.data["$notes"] = text
        else:
            self._content.data.pop("$notes", None)

    def _render_group(self, plan: GroupPlan) -> None:
        """Render a collapsible group from a GroupPlan."""
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

        self._populate_group_body(group, plan)
        self._form_layout.addWidget(group)

    def _populate_group_body(self, group: CollapsibleGroup, plan: GroupPlan) -> None:
        """Fill a group's body with field rows. Clears existing content first.

        Extracted from _render_group so that capability toggle / add-field
        can refresh a single group in-place without rebuilding the entire form.
        """
        # Clear existing body content
        bl = group.body_layout
        while bl.count() > 0:
            item = bl.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        # Field rows — 逐行 VBox 布局（替代 QFormLayout 网格）
        rows_layout = QVBoxLayout()
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(4)

        # 获取当前组的 widgets 配置（F-50 资源控件路由）
        content_type = normalize_content_type(self._content.data.get("type", ""))
        groups_config = self._field_groups.get(content_type, {})
        group_cfg = groups_config.get(plan.group_name, {})
        widgets_cfg = group_cfg.get("widgets", {}) if isinstance(group_cfg, dict) else {}
        inactive = inactive_dependencies(
            self._content.data.get("type", ""), self._content.data
        )

        for fp in plan.fields:
            f = fp.field_def
            widget_cfg = widgets_cfg.get(f.name)
            widget = self._create_field_widget(f, widget_cfg)
            if widget is None:
                continue

            # 富文本标签
            zh = self._field_names_zh.get(f.name, "")
            label_widget = rich_label(zh, f.name)
            doc = self._field_docs.get(f.name, "")
            en_name = label_widget.property("_en_name") or f.name
            tip_parts = [en_name]
            if doc:
                tip_parts.append(doc)
            tip = "\n".join(tip_parts)
            label_widget.setToolTip(tip)
            widget.setToolTip(tip)

            prerequisite = inactive.get(f.name)
            if prerequisite:
                label_widget.setProperty("inactive", "true")
                inactive_tip = f"{tip}\n当前不生效，前置条件：{prerequisite}"
                label_widget.setToolTip(inactive_tip)
                widget.setToolTip(inactive_tip)
                widget.setEnabled(False)

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

            # widgets 路由字段（requirements/consumes/research/outputItem 等）
            # 即使是 PRIMITIVE mode（如 outputItem 元数据为 ItemStack），
            # 也是复合编辑器 → 套 GroupBar（E-2），不算普通行。
            is_compound = isinstance(widget_cfg, dict) and "widget" in widget_cfg
            is_plain_row = (
                not is_compound
                and f.mode in ("PRIMITIVE", "STRING_REF")
            )
            if is_plain_row:
                # E-1（ADR-012）：统一推断源。hint 来自元数据线索：
                # STRING_REF → ref；Color → col；其余按值猜。
                from .theme import field_type_for_value

                if f.mode == "STRING_REF":
                    hint = "ref"
                elif f.java_type == "Color":
                    hint = "col"
                else:
                    hint = None
                ft = field_type_for_value(
                    self._content.data.get(f.name), hint
                )
                field_row = FieldRow(widget, ft, deletable=fp.deletable)
                if fp.deletable:
                    field_row.deleteRequested.connect(
                        lambda fn=f.name: self._delete_field(fn)
                    )
                row_h.addWidget(field_row)
            else:
                # E-2（ADR-012）：复合字段套组色条（4px 色条 + 淡染容器）。
                # fieldType 按 widgets 路由推导；无路由按值/模式推断。
                # 行首 label_widget 已显示字段名，GroupBar 内不再重复标签。
                from .widgets.group_bar import GroupBar

                gft = _group_bar_field_type(f, widget_cfg)
                bar = GroupBar(
                    widget, gft,
                    label="", english=f.name,
                )
                row_h.addWidget(bar)
            row_h.addStretch()
            row_container = QWidget()
            row_container.setLayout(row_h)
            row_h.setContentsMargins(0, 0, 0, 0)
            if is_plain_row:
                row_container.setFixedHeight(26)
            rows_layout.addWidget(row_container)

        bl.addLayout(rows_layout)

    @staticmethod
    def _clear_layout(layout) -> None:
        """Recursively remove all items from a layout."""
        while layout.count() > 0:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                EditorPanel._clear_layout(item.layout())

    def _find_group_widget(self, group_name: str) -> CollapsibleGroup | None:
        """Find a CollapsibleGroup widget by group_name in the form layout."""
        for i in range(self._form_layout.count()):
            w = self._form_layout.itemAt(i).widget()
            if isinstance(w, CollapsibleGroup) and w.group_name == group_name:
                return w
        return None

    def _refresh_group(self, group_name: str) -> None:
        """Recompute and re-populate a single group's body in-place.

        Does NOT destroy/recreate the CollapsibleGroup widget itself,
        so scroll position and focus are preserved.
        """
        group = self._find_group_widget(group_name)
        if group is None:
            return
        # Recompute full plan (cheap pure logic) and find our group
        expanded_state = _EXPANDED_STATE.get(self._content.name)
        deleted_groups = _DELETED_GROUPS.get(self._content.name, set())
        enabled_groups = _ENABLED_GROUPS.get(self._content.name, set())
        plans = compute_form_plan(
            class_def=self._class_def,
            data=self._content.data,
            field_groups=self._field_groups,
            expanded_state=expanded_state,
            group_labels=self.GROUP_LABELS,
            deleted_groups=deleted_groups,
            enabled_groups=enabled_groups,
        )
        plan = next((p for p in plans if p.group_name == group_name), None)
        if plan is not None:
            self._populate_group_body(group, plan)

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

        content_type = normalize_content_type(self._content.data.get("type", ""))
        groups_config = self._field_groups.get(content_type, {})
        group_def = groups_config.get(group_name, {})
        content_name = self._content.name

        if enabled:
            # 从缓存恢复（Bug1 修复）—— 字段写回逻辑集中在 core.group_ops
            cached = _CACHED_VALUES.get(content_name, {}).get(group_name, {})
            restore_group_fields(
                self._content.data, group_def, cached, self._class_def,
                self._commands, self._mark_dirty,
            )

            # 记入 _ENABLED_GROUPS
            _ENABLED_GROUPS.setdefault(content_name, set()).add(group_name)

            # 单向联动（mining → capacity）：只补 required+default，不写存在标记
            linked = CAPABILITY_LINKAGE.get(group_name)
            if linked and linked not in self._get_enabled_capabilities():
                linked_def = groups_config.get(linked, {})
                linked_cached = _CACHED_VALUES.get(content_name, {}).get(linked, {})
                restore_group_fields(
                    self._content.data, linked_def, linked_cached, self._class_def,
                    self._commands, self._mark_dirty,
                    restore_optional=False, existence_marker=False,
                )
        else:
            # 缓存当前值（Bug1 修复）
            cache = cache_group_fields(self._content.data, group_def)
            if cache:
                _CACHED_VALUES.setdefault(content_name, {})[group_name] = cache
            # 移除该组所有字段
            remove_group_fields(
                self._content.data, group_def, self._commands, self._mark_dirty,
            )
            # 从 _ENABLED_GROUPS 移除
            _ENABLED_GROUPS.get(content_name, set()).discard(group_name)

        # 原地刷新受影响的组（不重建整个表单，保持滚动位置）
        self._refresh_group(group_name)

        # 联动组：同步视觉状态 + 刷新 body
        linked = CAPABILITY_LINKAGE.get(group_name)
        if linked and enabled:
            _ENABLED_GROUPS.setdefault(content_name, set()).add(linked)
            linked_widget = self._find_group_widget(linked)
            if linked_widget is not None:
                linked_widget.set_capability_enabled(True)
            self._refresh_group(linked)

    def _get_enabled_capabilities(self) -> set[str]:
        """返回当前 data 中已启用的能力组名集合。"""
        from ..core.form_plan import CAPABILITY_GROUPS
        content_type = normalize_content_type(self._content.data.get("type", ""))
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

        content_type = normalize_content_type(self._content.data.get("type", ""))
        groups_config = self._field_groups.get(content_type, {})
        group_def = groups_config.get(group_name, {})
        names = group_field_names(group_def)
        content_name = self._content.name

        # Bug1：缓存当前值
        cache = cache_group_fields(self._content.data, group_def)
        if cache:
            _CACHED_VALUES.setdefault(content_name, {})[group_name] = cache

        # Bug2：记入已删除集合 + 从启用集合移除
        _DELETED_GROUPS.setdefault(content_name, set()).add(group_name)
        _ENABLED_GROUPS.get(content_name, set()).discard(group_name)

        remove_group_fields(
            self._content.data, group_def, self._commands, self._mark_dirty,
        )

        # 原地移除组控件（不重建整个表单）
        group_widget = self._find_group_widget(group_name)
        if group_widget is not None:
            self._form_layout.removeWidget(group_widget)
            group_widget.deleteLater()
        # 清理 _field_widgets 中该组的字段引用
        for name in names:
            self._field_widgets.pop(name, None)

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
        content_type = normalize_content_type(self._content.data.get("type", ""))
        groups_config = self._field_groups.get(content_type, {})
        group_def = groups_config.get(group_name, {})
        defaults = group_def.get("defaults", {})
        return defaults.get(field_name)

    # ── field widget creation ───────────────────────────────────────────

    def _create_field_widget(self, field_def: FieldDef, widget_cfg: dict | None = None) -> QWidget | None:
        current_value = self._content.data.get(field_def.name)

        # F-50: widgets 配置路由（优先于 mode 分支）
        if widget_cfg and "widget" in widget_cfg:
            w = self._create_configured_widget(field_def, widget_cfg)
            if w is not None:
                return w

        if field_def.mode == "PRIMITIVE":
            return self._create_primitive_widget(field_def, current_value)
        elif field_def.mode == "STRING_REF":
            return self._create_ref_widget(field_def, current_value)
        elif field_def.mode == "ARRAY":
            if field_def.name == "weapons":
                return self._create_weapons_widget()
            if field_def.name == "abilities":
                return self._create_abilities_widget()
            return ReservedPanel("数组字段")
        elif field_def.mode == "INLINE_OBJECT":
            if field_def.name == "bullet":
                return self._create_bullet_editor()
            return ReservedPanel("内联对象")
        return None

    def _create_configured_widget(self, field_def: FieldDef, cfg: dict) -> QWidget | None:
        """F-50: 根据 field_groups.json 的 widgets 配置实例化对应控件。"""
        from .widgets.resource_editors import (
            ConsumesEditor,
            ResourceListEditor,
            ResourceSlotEditor,
        )
        from .widgets.planet_set_editor import PlanetSetEditor
        from .widgets.research_editor import ResearchEditor

        widget_type = cfg["widget"]
        data = self._content.data
        path = field_def.name
        stack = self._commands

        if widget_type == "resource_list":
            editor = ResourceListEditor(
                data, path, stack,
                resource_type=cfg.get("resource_type", "item"),
                has_booster=cfg.get("has_booster", False),
                metadata=self._metadata,
                project=self._project,
            )
            # committed=True：编辑器内部已走命令栈，这里只做副作用（v0.2.5 修复
            # 双重命令导致撤销失效/需撤多次）。
            editor.valueChanged.connect(lambda: self._on_field_changed(path, data.get(path), committed=True))
            return editor
        elif widget_type == "resource_slot":
            editor = ResourceSlotEditor(
                data, path, stack,
                resource_type=cfg.get("resource_type", "item"),
                metadata=self._metadata,
                project=self._project,
            )
            editor.valueChanged.connect(lambda: self._on_field_changed(path, data.get(path), committed=True))
            return editor
        elif widget_type in ("research", "tech_ref"):
            editor = ResearchEditor(
                data, path, stack,
                metadata=self._metadata,
                project=self._project,
            )
            editor.valueChanged.connect(lambda: self._on_field_changed(path, data.get(path), committed=True))
            return editor
        elif widget_type == "planet_set":
            editor = PlanetSetEditor(
                data, path, stack,
                metadata=self._metadata,
                project=self._project,
            )
            editor.valueChanged.connect(lambda: self._on_field_changed(path, data.get(path), committed=True))
            return editor
        elif widget_type == "consumes":
            editor = ConsumesEditor(
                data, path, stack,
                metadata=self._metadata,
                project=self._project,
            )
            editor.valueChanged.connect(lambda: self._on_field_changed(path, data.get(path), committed=True))
            return editor
        return None

    def _create_primitive_widget(self, field_def: FieldDef, value: Any) -> QWidget:
        java_type = field_def.java_type

        # bool/int/float 走统一工厂（range/decimals/宽度/滚轮/防误触全在内）
        if java_type == "boolean":
            coerced: Any = bool(value) if value is not None else False
        elif java_type in ("int", "long", "short"):
            coerced = int(value) if value is not None else 0
        elif java_type in ("float", "double"):
            coerced = float(value) if value is not None else 0.0
        else:
            coerced = None
        if coerced is not None or java_type == "boolean":
            w = create_value_widget(
                coerced,
                lambda v, n=field_def.name: self._on_field_changed(n, v),
            )
            if w is not None:
                self._field_widgets[field_def.name] = w
                return w

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
        from .widgets.content_ref_selector import ContentRefSelector

        categories = (field_def.ref_source,) if field_def.ref_source else ()
        selector = ContentRefSelector(
            metadata=self._metadata,
            project=self._project,
            categories=categories,
            names_zh=self._content_names_zh,
        )
        selector.set_value(str(value) if value is not None else "")
        selector.valueChanged.connect(
            lambda selected, n=field_def.name: self._on_field_changed(n, selected or None)
        )
        self._field_widgets[field_def.name] = selector
        return selector

    def _create_color_widget(self, field_def: FieldDef, value: Any) -> QWidget:
        """Color 字段 → ColorPicker 控件（色块 + hex 输入）。"""
        picker = ColorPicker(value)
        picker.valueChanged.connect(
            lambda hex_val, n=field_def.name: self._on_field_changed(n, hex_val)
        )
        self._field_widgets[field_def.name] = picker
        return picker

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
        # 武器列表（含 x/y）修改 → 通知预览/图层树实时刷新（v0.2.5 修复：
        # 否则图层树 spin 显示旧值，保存时被旧值覆写）。
        editor.valueChanged.connect(self.data_changed.emit)
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

    def _create_abilities_widget(self) -> QWidget:
        """Create an AbilityArrayEditor for the abilities field (F-49).

        不预写空数组：无 abilities 时 JSON 不产生该键，首次添加时才经命令栈创建
        （v0.2.5 修复：预写绕过命令栈且保存时污染空数组）。
        """
        from .widgets.ability_array_editor import AbilityArrayEditor

        editor = AbilityArrayEditor(
            data=self._content.data,
            path="abilities",
            command_stack=self._commands,
        )
        editor.valueChanged.connect(self._mark_dirty)
        editor.valueChanged.connect(self.data_changed.emit)
        self._field_widgets["abilities"] = editor
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

    def _on_field_changed(self, field_name: str, new_value: Any, committed: bool = False) -> None:
        """字段值变化处理。

        committed=False（默认）：简单控件（数字框/文本框/下拉/颜色等）自身不操作
        命令栈，这里创建 SetFieldCommand 保证可撤销。

        committed=True：复合编辑器（ResourceList/ResourceSlot/TechRef/Consumes）
        内部已通过命令栈提交修改，这里只做副作用（脏标记/校验/预览刷新），避免
        重复命令污染撤销栈（v0.2.5 修复：双重命令导致撤销失效或需撤多次）。
        """
        if not committed:
            cmd = SetFieldCommand(
                data=self._content.data,
                path=field_name,
                new_value=new_value,
                on_change=self._mark_dirty,
            )
            self._commands.execute(cmd)

        # Real-time validation: red border + tooltip on error
        self._validate_field_widget(field_name, new_value)
        if field_name in {"engineSize", "canBoost", "rotate", "continuous"}:
            self._rebuild_form()
        # v0.2.4.batch4：通知预览实时刷新
        self.data_changed.emit()

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

    def highlight_field(self, field_name: str) -> bool:
        """F-51: 全量验证报告点击跳转——滚动并高亮指定字段。

        字段控件可能被 FieldRow/GroupBar 包裹，直接找 _field_widgets 里的
        原始控件即可（它已在滚动区内部）。
        """
        widget = self._field_widgets.get(field_name)
        if widget is None:
            return False
        widget.setFocus()
        self._scroll_to_widget(widget)
        widget.setProperty("error", "true")
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        return True

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

        content_type = normalize_content_type(self._content.data.get("type", ""))
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

            # Bug1/Bug3：从缓存恢复字段值（含存在标记）—— 逻辑集中在 core.group_ops
            cached = _CACHED_VALUES.get(content_name, {}).get(group_name, {})
            restore_group_fields(
                self._content.data, group_def, cached, self._class_def,
                self._commands, self._mark_dirty,
            )

            # 能力组：记入 _ENABLED_GROUPS
            from ..core.form_plan import CAPABILITY_GROUPS
            if group_name in CAPABILITY_GROUPS:
                _ENABLED_GROUPS.setdefault(content_name, set()).add(group_name)

            self._rebuild_form()

    # ── helpers ─────────────────────────────────────────────────────────
