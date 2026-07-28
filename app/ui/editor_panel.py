"""Editor panel: auto-generated property form for a content item.

Design principles:
- Only show fields in configured groups + fields already in the JSON
- Each group has a "+" button to add more fields from metadata
- Field labels use "中文 (英文)" format
- No dumping of all 272 fields onto the user
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.commands import CommandStack, SetFieldCommand
from ..core.content_store import ContentData
from ..core.metadata import ClassDef, FieldDef, Metadata
from ..core.project import Project
from ..core.validator import Validator


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

        self._field_groups = self._load_field_groups()
        self._field_names_zh = self._load_field_names_zh()
        self._field_docs = self._load_field_docs()
        self._class_def: ClassDef | None = None
        self._form_layout: QVBoxLayout | None = None
        self._setup_ui()

    @property
    def content(self) -> ContentData:
        return self._content

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    # ── UI setup ────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Title
        title = QLabel(f"{self._content.name}  ({self._content.data.get('type', '?')})")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(title)

        # Scrollable form area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self._form_layout = QVBoxLayout(scroll_widget)
        self._form_layout.setContentsMargins(4, 4, 4, 4)

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
        """Rebuild form groups. Called on init and when fields are added/deleted."""
        if self._class_def is None or self._form_layout is None:
            return

        # Clear existing widgets (groups + notes + stretch)
        while self._form_layout.count() > 0:
            item = self._form_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._field_widgets.clear()

        content_type = self._content.data.get("type", "")
        groups_config = self._field_groups.get(content_type, {})
        all_fields = {f.name: f for f in self._class_def.fields}

        # Fields in configured groups
        grouped_names: set[str] = set()
        for field_names in groups_config.values():
            grouped_names.update(field_names)

        # Fields already in JSON but not in any group → "自定义字段"
        json_fields = set(self._content.data.keys()) - {"type"}
        extra_names = json_fields - grouped_names

        # Render configured groups
        for group_name, field_names in groups_config.items():
            label = self.GROUP_LABELS.get(group_name, group_name)
            visible = [all_fields[n] for n in field_names if n in all_fields]
            self._render_group(label, group_name, visible)

        # Render extra fields from JSON
        if extra_names:
            extra = [all_fields[n] for n in sorted(extra_names) if n in all_fields]
            if extra:
                self._render_group("自定义字段", "_custom", extra)

        # Re-add user notes box
        notes_box = QGroupBox("用户备注")
        notes_layout = QVBoxLayout(notes_box)
        self._notes_edit = QTextEdit()
        self._notes_edit.setMaximumHeight(60)
        self._notes_edit.setPlaceholderText("在此添加备注...")
        notes_layout.addWidget(self._notes_edit)
        self._form_layout.addWidget(notes_box)

        self._form_layout.addStretch()

    def _render_group(self, label: str, group_name: str, fields: list[FieldDef]) -> None:
        """Render a group box with header (title + '+' button) and field rows."""
        group_box = QGroupBox()
        group_layout = QVBoxLayout(group_box)
        group_layout.setContentsMargins(8, 4, 8, 8)

        # Header: label + add button
        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>{label}</b>"))
        header.addStretch()
        add_btn = QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setToolTip("添加字段")
        add_btn.setStyleSheet("font-size: 14px; font-weight: bold;")
        add_btn.clicked.connect(lambda _, gn=group_name: self._show_add_field_menu(gn))
        header.addWidget(add_btn)
        group_layout.addLayout(header)

        # Field rows
        form = QFormLayout()
        for f in fields:
            widget = self._create_field_widget(f)
            if widget:
                label_widget = QLabel(self._display_name(f.name))
                # Attach tooltip from field_docs.json
                doc = self._field_docs.get(f.name, "")
                if doc:
                    label_widget.setToolTip(doc)
                    widget.setToolTip(doc)
                # Right-click to delete field
                widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                widget.customContextMenuRequested.connect(
                    lambda pos, fn=f.name, w=widget: self._show_field_context_menu(pos, fn, w)
                )
                form.addRow(label_widget, widget)
        group_layout.addLayout(form)

        self._form_layout.addWidget(group_box)

    def _show_add_field_menu(self, group_name: str) -> None:
        """Popup menu listing available fields to add."""
        if self._class_def is None:
            return

        # Already shown fields
        shown = set(self._content.data.keys())
        content_type = self._content.data.get("type", "")
        for names in self._field_groups.get(content_type, {}).values():
            shown.update(names)

        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        count = 0
        for f in self._class_def.fields:
            if f.name in shown or self._is_internal_field(f):
                continue
            action = menu.addAction(self._display_name(f.name))
            action.setData(f.name)
            # Tooltip in menu
            doc = self._field_docs.get(f.name, "")
            if doc:
                action.setToolTip(doc)
            count += 1
            if count >= 60:
                break

        if count == 0:
            menu.addAction("(无更多可用字段)").setEnabled(False)

        chosen = menu.exec(self.mapToGlobal(self.rect().center()))
        if chosen and chosen.data():
            field_name = chosen.data()
            field_def = next(
                (f for f in self._class_def.fields if f.name == field_name), None
            )
            if field_def:
                self._content.data[field_name] = self._type_default(field_def)
                self._mark_dirty()
                self._rebuild_form()

    # ── field widget creation ───────────────────────────────────────────

    def _create_field_widget(self, field_def: FieldDef) -> QWidget | None:
        current_value = self._content.data.get(field_def.name)

        if field_def.mode == "PRIMITIVE":
            return self._create_primitive_widget(field_def, current_value)
        elif field_def.mode == "STRING_REF":
            return self._create_ref_widget(field_def, current_value)
        elif field_def.mode == "ARRAY":
            label = QLabel(f"[{field_def.element_type or 'list'}] (编辑功能开发中)")
            label.setStyleSheet("color: gray;")
            return label
        elif field_def.mode == "INLINE_OBJECT":
            label = QLabel(f"[{field_def.inline_type or 'object'}] (编辑功能开发中)")
            label.setStyleSheet("color: gray;")
            return label
        return None

    def _create_primitive_widget(self, field_def: FieldDef, value: Any) -> QWidget:
        java_type = field_def.java_type

        if java_type == "boolean":
            cb = QCheckBox()
            cb.setChecked(bool(value) if value is not None else False)
            cb.toggled.connect(
                lambda checked, n=field_def.name: self._on_field_changed(n, checked)
            )
            self._field_widgets[field_def.name] = cb
            return cb

        if java_type in ("int", "long", "short"):
            spin = QSpinBox()
            spin.setRange(-999999, 999999)
            spin.setValue(int(value) if value is not None else 0)
            spin.valueChanged.connect(
                lambda v, n=field_def.name: self._on_field_changed(n, v)
            )
            self._field_widgets[field_def.name] = spin
            return spin

        if java_type in ("float", "double"):
            spin = QDoubleSpinBox()
            spin.setRange(-999999.0, 999999.0)
            spin.setDecimals(3)
            spin.setValue(float(value) if value is not None else 0.0)
            spin.valueChanged.connect(
                lambda v, n=field_def.name: self._on_field_changed(n, v)
            )
            self._field_widgets[field_def.name] = spin
            return spin

        # String or fallback
        edit = QLineEdit()
        edit.setText(str(value) if value is not None else "")
        edit.textChanged.connect(
            lambda t, n=field_def.name: self._on_field_changed(n, t)
        )
        self._field_widgets[field_def.name] = edit
        return edit

    def _create_ref_widget(self, field_def: FieldDef, value: Any) -> QWidget:
        combo = QComboBox()
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

    def _show_field_context_menu(self, pos, field_name: str, widget: QWidget) -> None:
        """Right-click context menu on a field widget: delete field."""
        menu = QMenu(self)
        delete_action = menu.addAction(f"删除字段 \"{self._display_name(field_name)}\"")
        chosen = menu.exec(widget.mapToGlobal(pos))
        if chosen == delete_action:
            if field_name in self._content.data:
                del self._content.data[field_name]
                self._mark_dirty()
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

    # ── display name: 中文 (英文) ───────────────────────────────────────

    def _display_name(self, field_name: str) -> str:
        zh = self._field_names_zh.get(field_name)
        if zh:
            return f"{zh} ({field_name})"
        return field_name

    # ── helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _is_internal_field(f: FieldDef) -> bool:
        """Fields users would almost never edit in a mod."""
        internal_suffixes = ("Region", "Sound", "Effect", "Controller")
        internal_names = {
            "id", "minfo", "stats", "localizedName", "description",
            "details", "credit", "alwaysUnlocked", "removed",
            "uiIcon", "fullIcon", "fullOverride", "shownPlanets",
            "databaseTabs", "techNodes", "constructor",
            "engineColorInner", "engineColor", "healColor",
        }
        if f.name in internal_names:
            return True
        if any(f.name.endswith(s) for s in internal_suffixes):
            return True
        if f.mode == "PRIMITIVE" and f.java_type not in (
            "float", "double", "int", "long", "short", "boolean", "String", "Color"
        ):
            return True
        return False

    @staticmethod
    def _type_default(f: FieldDef) -> Any:
        if f.java_type in ("float", "double"):
            return 0.0
        if f.java_type in ("int", "long", "short"):
            return 0
        if f.java_type == "boolean":
            return False
        if f.mode == "ARRAY":
            return []
        if f.mode == "INLINE_OBJECT":
            return {}
        return None

    @staticmethod
    def _load_field_groups() -> dict:
        config_path = Path(__file__).parent.parent / "config" / "field_groups.json"
        if config_path.exists():
            return json.loads(config_path.read_text(encoding="utf-8"))
        return {}

    @staticmethod
    def _load_field_names_zh() -> dict[str, str]:
        config_path = Path(__file__).parent.parent / "config" / "field_names_zh.json"
        if config_path.exists():
            return json.loads(config_path.read_text(encoding="utf-8"))
        return {}

    @staticmethod
    def _load_field_docs() -> dict[str, str]:
        config_path = Path(__file__).parent.parent / "config" / "field_docs.json"
        if config_path.exists():
            return json.loads(config_path.read_text(encoding="utf-8"))
        return {}
