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
from ..core.config_loader import (
    display_name as _format_display_name,
    get_field_docs,
    get_field_groups,
    get_field_names_zh,
)
from ..core.content_store import ContentData
from ..core.metadata import ClassDef, FieldDef, Metadata
from ..core.project import Project
from ..core.validator import Validator
from .widgets.weapon_array_editor import WeaponArrayEditor
from .widgets.bullet_editor import BulletEditor


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
        """Rebuild form groups. Called on init and when fields are added/deleted.

        Each group in field_groups.json now has 'required' (always shown) and
        'optional' (shown only if the field already exists in JSON data).
        The '+' button on each group reveals that group's optional fields.

        Groups may have 'visible_for' to restrict visibility to specific subtypes.
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

        content_type = self._content.data.get("type", "")
        groups_config = self._field_groups.get(content_type, {})
        all_fields = {f.name: f for f in self._class_def.fields}

        # Infer subtype for visible_for filtering
        subtype = self._infer_subtype(content_type)

        # Collect all field names that appear in any visible group
        grouped_names: set[str] = set()
        for gd in groups_config.values():
            if not self._group_visible(gd, subtype):
                continue
            grouped_names.update(gd.get("required", []))
            grouped_names.update(gd.get("optional", []))

        # Fields already in JSON but not in any visible group → "其他"
        json_fields = set(self._content.data.keys()) - {"type"}
        extra_names = json_fields - grouped_names

        # Render configured groups: required always, optional only if in data
        for group_name, group_def in groups_config.items():
            if not self._group_visible(group_def, subtype):
                continue

            label = self.GROUP_LABELS.get(group_name, group_name)
            required = group_def.get("required", [])
            optional = group_def.get("optional", [])

            visible_names = list(required)
            for n in optional:
                if n in self._content.data:
                    visible_names.append(n)

            visible = [all_fields[n] for n in visible_names if n in all_fields]
            # Only render if there's at least one visible field or the group has optional fields
            if visible or optional:
                self._render_group(label, group_name, visible)

        # Render extra fields from JSON (not in any group) → "其他"
        if extra_names:
            extra = [all_fields[n] for n in sorted(extra_names) if n in all_fields]
            if extra:
                self._render_group("其他", "_other", extra)

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

    # ── visible_for / subtype helpers ────────────────────────────────────

    def _infer_subtype(self, content_type: str) -> str:
        """Infer the subtype key for visible_for filtering.

        For UnitType, checks data flags (flying, legCount, squareShape, etc.)
        to determine which subtype template was used.
        Returns e.g. 'UnitType-tank', 'UnitType-flying', 'UnitType-legs', 'UnitType'.
        """
        if content_type != "UnitType":
            return content_type

        data = self._content.data
        if data.get("squareShape") or data.get("crushDamage") is not None:
            return "UnitType-tank"
        if data.get("legCount"):
            return "UnitType-legs"
        if data.get("flying"):
            return "UnitType-flying"
        return "UnitType"

    @staticmethod
    def _group_visible(group_def: dict, subtype: str) -> bool:
        """Check if a group should be visible for the given subtype.

        A group with no 'visible_for' key is always visible.
        A group with 'visible_for' is visible only if subtype is in the list.
        """
        visible_for = group_def.get("visible_for")
        if visible_for is None:
            return True
        return subtype in visible_for

    def _get_group_default(self, group_name: str, field_name: str) -> Any:
        """Look up a configured default value for a field in a group.

        Returns None if no default is configured.
        """
        content_type = self._content.data.get("type", "")
        groups_config = self._field_groups.get(content_type, {})
        group_def = groups_config.get(group_name, {})
        defaults = group_def.get("defaults", {})
        return defaults.get(field_name)

    def _show_add_field_menu(self, group_name: str) -> None:
        """Popup menu listing available optional fields for this group.

        Each group's '+' only shows optional fields from that group.
        The '_other' group shows fields not in any group at all.
        """
        if self._class_def is None:
            return

        content_type = self._content.data.get("type", "")
        groups_config = self._field_groups.get(content_type, {})
        data_keys = set(self._content.data.keys())

        if group_name == "_other":
            # "其他" group: show all class fields not in any group at all
            all_grouped = set()
            for gd in groups_config.values():
                all_grouped.update(gd.get("required", []))
                all_grouped.update(gd.get("optional", []))
            candidates = [
                f for f in self._class_def.fields
                if f.name not in all_grouped
                and f.name not in data_keys
                and not self._is_internal_field(f)
            ]
        else:
            group_def = groups_config.get(group_name, {})
            optional_names = set(group_def.get("optional", []))
            candidates = [
                f for f in self._class_def.fields
                if f.name in optional_names
                and f.name not in data_keys
                and not self._is_internal_field(f)
            ]

        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        count = 0
        for f in candidates:
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
            if field_def.name == "weapons":
                return self._create_weapons_widget()
            label = QLabel(f"[{field_def.element_type or 'list'}] (编辑功能开发中)")
            label.setStyleSheet("color: gray;")
            return label
        elif field_def.mode == "INLINE_OBJECT":
            if field_def.name == "bullet":
                return self._create_bullet_editor()
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

        if java_type == "Color":
            return self._create_color_widget(field_def, value)

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
        """Create a BulletEditor for the bullet field."""
        editor = BulletEditor(
            data=self._content.data,
            path="bullet",
            command_stack=self._commands,
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
        if issue is not None:
            widget.setStyleSheet("border: 2px solid red; border-radius: 3px;")
            widget.setToolTip(issue.message)
        else:
            widget.setStyleSheet("")  # Clear
            # Restore original tooltip from field_docs
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

    # ── display name: delegates to config_loader (respects display mode) ──

    def _display_name(self, field_name: str) -> str:
        return _format_display_name(field_name, self._field_names_zh)

    # ── helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _is_internal_field(f: FieldDef) -> bool:
        """Fields users would almost never edit in a mod."""
        internal_suffixes = ("Region", "Sound", "Effect", "Controller")
        internal_names = {
            "id", "minfo", "stats", "localizedName",
            "alwaysUnlocked", "removed",
            "uiIcon", "fullIcon", "fullOverride", "shownPlanets",
            "databaseTabs", "allDatabaseTabs", "techNodes", "techNode",
            "constructor", "firstRequirements",
            "engineColorInner", "engineColor", "healColor",
            "generateIcons", "generateFullIcon", "internalGenerateSprites",
            "cachedRequirements", "totalRequirements",
            "dpsEstimate", "sample", "unlocked",
            "hideDatabase", "databaseCategory", "databaseTag",
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
