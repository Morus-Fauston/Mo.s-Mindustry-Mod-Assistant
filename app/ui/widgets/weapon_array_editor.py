"""Weapon array editor widget for unit type forms.

A dedicated component that renders the `weapons` field as a list of
foldable cards. Each weapon card supports two modes:
- Reference mode: name dropdown + optional override fields + [展开为内联]
- Inline mode: full weapon field form + embedded bullet sub-form

Interface:
    .value   — get/set the weapons list [dict, ...]
    .valueChanged — Qt Signal, emitted when the list changes
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

# NOTE: These are imported lazily or at module level depending on need
from ...core.commands import ArrayInsertCommand, ArrayRemoveCommand, CommandStack
from ...core.metadata import Metadata
from ...core.project import Project


# ── config: default override fields shown on weapon reference cards ──────

DEFAULT_OVERRIDE_FIELDS = ["x", "y", "reload", "top", "rotate", "mirror"]

# ── predefined bullet types (first-class subclasses) ────────────────────

BULLET_TYPE_CHOICES = [
    "BasicBulletType",
    "LaserBulletType",
    "MissileBulletType",
    "ArtilleryBulletType",
    "FlakBulletType",
]

# ── centralized config ───────────────────────────────────────────────────

from ...core.config_loader import (
    display_name as _display_name_fn,
    get_category_names_zh,
    get_field_docs,
    get_field_groups,
    get_field_names_zh,
    get_vanilla_weapon_names_zh,
)

# Backward-compatible aliases (used by reference_panel.py)
VANILLA_WEAPON_NAMES_ZH = get_vanilla_weapon_names_zh()
CATEGORY_NAMES_ZH = get_category_names_zh()


def _load_field_names_zh() -> dict[str, str]:
    return get_field_names_zh()


def _load_field_docs() -> dict[str, str]:
    return get_field_docs()


def _display_name(field_name: str, names_zh: dict[str, str]) -> str:
    return _display_name_fn(field_name, names_zh)


class WeaponArrayEditor(QWidget):
    """List of weapon cards with [+] add and per-card [×] remove."""

    valueChanged = Signal()

    def __init__(
        self,
        data: dict,  # the unit's full data dict (for CommandStack access)
        path: str,   # path to weapons array, e.g. "weapons"
        command_stack: CommandStack,
        metadata: Metadata,
        project: Project,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data = data
        self._path = path
        self._commands = command_stack
        self._metadata = metadata
        self._project = project
        self._cards: list[WeaponCard] = []
        self._field_names_zh = _load_field_names_zh()
        self._field_docs = _load_field_docs()

        self._setup_ui()

    # ── public interface ─────────────────────────────────────────────────

    @property
    def value(self) -> list[dict]:
        arr = self._data.get(self._path, [])
        if not isinstance(arr, list):
            return []
        return arr

    @value.setter
    def value(self, new_value: list[dict]) -> None:
        self._data[self._path] = new_value
        self._rebuild_cards()
        self.valueChanged.emit()

    # ── UI setup ─────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Card container
        self._card_container = QVBoxLayout()
        layout.addLayout(self._card_container)

        # [+] add button
        add_btn = QPushButton("+ 添加武器")
        add_btn.clicked.connect(self._add_weapon)
        layout.addWidget(add_btn)

        layout.addStretch()

        # Initial render
        self._rebuild_cards()

    def _rebuild_cards(self) -> None:
        """Clear all cards and recreate from current value."""
        # Clear
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        while self._card_container.count() > 0:
            item = self._card_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Recreate
        for i, weapon_data in enumerate(self.value):
            card = WeaponCard(
                weapon_data=weapon_data,
                index=i,
                parent_data=self._data,
                parent_path=self._path,
                commands=self._commands,
                metadata=self._metadata,
                project=self._project,
                field_names_zh=self._field_names_zh,
                field_docs=self._field_docs,
            )
            card.modified.connect(self._on_card_modified)
            card.removeRequested.connect(self._remove_weapon)
            self._cards.append(card)
            self._card_container.addWidget(card)

    # ── slots ────────────────────────────────────────────────────────────

    def _add_weapon(self) -> None:
        dlg = _AddWeaponDialog(self._project, self._metadata, self)
        if dlg.exec():
            weapon_data = dlg.result_data()
            if weapon_data is not None:
                cmd = ArrayInsertCommand(
                    data=self._data,
                    path=self._path,
                    index=len(self.value),
                    element=weapon_data,
                    on_change=lambda: self._rebuild_cards(),
                )
                self._commands.execute(cmd)
                self.valueChanged.emit()

    def _remove_weapon(self, index: int) -> None:
        cmd = ArrayRemoveCommand(
            data=self._data,
            path=self._path,
            index=index,
            on_change=lambda: self._rebuild_cards(),
        )
        self._commands.execute(cmd)
        self.valueChanged.emit()

    def _on_card_modified(self) -> None:
        self.valueChanged.emit()


# ═══════════════════════════════════════════════════════════════════════════
# WeaponCard — single weapon entry
# ═══════════════════════════════════════════════════════════════════════════

class WeaponCard(QGroupBox):
    """A foldable card representing one weapon in the array."""

    modified = Signal()        # emitted when weapon data changes
    removeRequested = Signal(int)  # emitted with self index

    def __init__(
        self,
        weapon_data: dict,
        index: int,
        parent_data: dict,
        parent_path: str,
        commands: CommandStack,
        metadata: Metadata,
        project: Project,
        field_names_zh: dict[str, str] | None = None,
        field_docs: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self._weapon_data = weapon_data
        self._index = index
        self._parent_data = parent_data
        self._parent_path = parent_path
        self._commands = commands
        self._metadata = metadata
        self._project = project
        self._field_names_zh = field_names_zh or {}
        self._field_docs = field_docs or {}
        self._field_groups = get_field_groups()

        self._is_inline = "bullet" in weapon_data
        self._setup_ui()

    # ── helpers ──────────────────────────────────────────────────────────

    def _weapon_name(self) -> str:
        return self._weapon_data.get("name", f"武器 #{self._index + 1}")

    def _data_path(self, sub_path: str = "") -> str:
        """Build full dotted path into parent data, e.g. 'weapons[0].reload'."""
        base = f"{self._parent_path}[{self._index}]"
        return f"{base}.{sub_path}" if sub_path else base

    # ── UI ───────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)

        # Header: name + mode badge + [×] remove
        header = QHBoxLayout()
        title = QLabel(f"<b>{self._weapon_name()}</b>")
        header.addWidget(title)

        mode_badge = QLabel("内联" if self._is_inline else "引用")
        mode_badge.setStyleSheet(
            "color: #2196F3; font-size: 11px;" if self._is_inline
            else "color: #4CAF50; font-size: 11px;"
        )
        header.addWidget(mode_badge)
        header.addStretch()

        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setStyleSheet("color: red; font-weight: bold;")
        remove_btn.clicked.connect(lambda: self.removeRequested.emit(self._index))
        header.addWidget(remove_btn)
        layout.addLayout(header)

        if self._is_inline:
            self._build_inline_form(layout)
        else:
            self._build_reference_form(layout)

    def _build_reference_form(self, layout: QVBoxLayout) -> None:
        """Reference mode: name, override fields, expand button."""
        form = QFormLayout()

        # Name
        name_input = QLineEdit()
        name_input.setText(self._weapon_data.get("name", ""))
        name_input.textChanged.connect(
            lambda t: self._set_field("name", t if t else None)
        )
        form.addRow("名称", name_input)

        # Override fields (default set: x, y, reload, top, rotate, mirror)
        override_names = [
            f for f in DEFAULT_OVERRIDE_FIELDS
            if f in self._weapon_data
        ]
        # Always show name field, plus any override fields that exist in data
        for fname in override_names:
            widget = self._create_override_widget(fname)
            if widget:
                label_text = _display_name(fname, self._field_names_zh)
                row_label = QLabel(label_text)
                doc = self._field_docs.get(fname, "")
                if doc:
                    row_label.setToolTip(doc)
                    widget.setToolTip(doc)
                form.addRow(row_label, widget)

        layout.addLayout(form)

        # "+ 添加覆盖" button
        add_override_btn = QPushButton("+ 添加覆盖字段")
        add_override_btn.clicked.connect(self._show_add_override_menu)
        layout.addWidget(add_override_btn)

        # [展开为内联] button
        expand_btn = QPushButton("展开为内联")
        expand_btn.clicked.connect(self._expand_to_inline)
        layout.addWidget(expand_btn)

    def _build_inline_form(self, layout: QVBoxLayout) -> None:
        """Inline mode: config-driven weapon fields + bullet sub-form."""
        form = QFormLayout()

        # Read weapon fields from field_groups.json config
        weapon_groups = self._field_groups.get("Weapon", {})
        shown_fields: list[str] = []
        for group_def in weapon_groups.values():
            if group_def is None:
                continue
            for fname in group_def.get("required", []):
                if fname not in shown_fields and fname != "bullet":
                    shown_fields.append(fname)
            for fname in group_def.get("optional", []):
                if fname in self._weapon_data and fname not in shown_fields and fname != "bullet":
                    shown_fields.append(fname)

        # Fallback: if no config, use a minimal set
        if not shown_fields:
            shown_fields = ["name", "reload", "x", "y", "mirror", "alternate"]

        for fname in shown_fields:
            if fname in self._weapon_data:
                widget = self._create_override_widget(fname)
                if widget:
                    label_text = _display_name(fname, self._field_names_zh)
                    row_label = QLabel(label_text)
                    doc = self._field_docs.get(fname, "")
                    if doc:
                        row_label.setToolTip(doc)
                        widget.setToolTip(doc)
                    form.addRow(row_label, widget)

        layout.addLayout(form)

        # Bullet sub-form (delegates to BulletEditor → PolymorphicTypeEditor)
        from .bullet_editor import BulletEditor
        bullet_editor = BulletEditor(
            data=self._parent_data,
            path=self._data_path("bullet"),
            command_stack=self._commands,
        )
        bullet_editor.valueChanged.connect(lambda: self.modified.emit())
        layout.addWidget(bullet_editor)

    # ── field mutation ───────────────────────────────────────────────────

    def _set_field(self, field_name: str, new_value: Any) -> None:
        from ...core.commands import SetFieldCommand
        cmd = SetFieldCommand(
            data=self._parent_data,
            path=self._data_path(field_name),
            new_value=new_value,
        )
        self._commands.execute(cmd)
        self.modified.emit()

    def _set_bullet_field(self, field_name: str, new_value: Any) -> None:
        from ...core.commands import SetFieldCommand
        cmd = SetFieldCommand(
            data=self._parent_data,
            path=self._data_path(f"bullet.{field_name}"),
            new_value=new_value,
        )
        self._commands.execute(cmd)
        self.modified.emit()

    def _on_bullet_type_changed(self, new_type: str) -> None:
        """Handle bullet type change in inline weapon."""
        self._set_bullet_field("type", new_type)
        self._rebuild_card()

    # ── override field widgets ───────────────────────────────────────────

    def _create_override_widget(self, fname: str) -> QWidget | None:
        val = self._weapon_data.get(fname)
        if val is None:
            return None
        return self._create_widget_for_value(fname, val, self._set_field)

    def _create_primitive_widget(self, data: dict, fname: str) -> QWidget | None:
        val = data.get(fname)
        if val is None:
            return None

        # Build a path-aware setter
        def setter(v: Any) -> None:
            if data is self._weapon_data:
                self._set_field(fname, v)
            else:
                self._set_bullet_field(fname, v)

        return self._create_widget_for_value(fname, val, setter)

    def _create_widget_for_value(
        self, fname: str, val: Any,
        on_change: Any,
    ) -> QWidget | None:
        if isinstance(val, bool):
            cb = QCheckBox()
            cb.setChecked(val)
            cb.toggled.connect(on_change)
            return cb
        elif isinstance(val, float):
            spin = QDoubleSpinBox()
            spin.setRange(-999999.0, 999999.0)
            spin.setDecimals(3)
            spin.setValue(val)
            spin.valueChanged.connect(on_change)
            return spin
        elif isinstance(val, int):
            spin = QSpinBox()
            spin.setRange(-999999, 999999)
            spin.setValue(val)
            spin.valueChanged.connect(on_change)
            return spin
        elif isinstance(val, str):
            edit = QLineEdit()
            edit.setText(val)
            edit.textChanged.connect(on_change)
            return edit
        return None

    # ── actions ──────────────────────────────────────────────────────────

    def _show_add_override_menu(self) -> None:
        """Let user pick additional override fields from the default set."""
        available = [f for f in DEFAULT_OVERRIDE_FIELDS
                     if f not in self._weapon_data]

        if not available:
            QMessageBox.information(self, "提示", "没有更多可覆盖的字段")
            return

        item, ok = QInputDialog.getItem(
            self, "添加覆盖字段", "选择要覆盖的字段:",
            available, 0, False,
        )
        if ok and item:
            defaults = {"x": 0.0, "y": 0.0, "reload": 1.0, "top": True,
                        "rotate": False, "mirror": True}
            default_val = defaults.get(item, 0.0)
            self._set_field(item, default_val)
            self._rebuild_card()

    def _expand_to_inline(self) -> None:
        """Replace the reference entry with a full inline weapon definition."""
        weapon_name = self._weapon_data.get("name", "")
        full_data = _load_weapon_data(weapon_name, self._project, self._metadata)
        if full_data is None:
            reply = QMessageBox.question(
                self, "找不到武器定义",
                f"找不到武器 '{weapon_name}' 的定义。\n\n"
                "是否创建空白内联定义？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
            full_data = {"name": weapon_name, "reload": 1.0, "bullet": {
                "type": "BasicBulletType", "damage": 1.0, "speed": 1.0,
            }}

        # Merge: keep overrides from reference, fill rest from full_data
        merged = dict(full_data)
        # Preserve any overrides the user has set on the reference
        for k, v in self._weapon_data.items():
            if k != "name":
                merged[k] = v

        # Replace entire weapon entry
        from ...core.commands import SetFieldCommand
        cmd = SetFieldCommand(
            data=self._parent_data,
            path=self._data_path(),
            new_value=merged,
        )
        self._commands.execute(cmd)

        # Update card's reference to the new dict and rebuild UI
        self._weapon_data = merged
        self._is_inline = True
        self._rebuild_card()
        self.modified.emit()

    def _rebuild_card(self) -> None:
        """Rebuild this card's UI (e.g. after adding override fields).

        Qt-safe: reparent old layout to a temporary widget so it is
        destroyed cleanly before installing a new one.
        """
        self._is_inline = "bullet" in self._weapon_data
        old = self.layout()
        if old is not None:
            from PySide6.QtWidgets import QWidget as _Q
            _Q().setLayout(old)  # old layout dies with temp widget
        self._setup_ui()


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _load_weapon_data(
    name: str,
    project: Project,
    metadata: Metadata,
) -> dict | None:
    """Try to load full weapon data from project or metadata instances."""
    # 1. Check project's content/weapons/
    try:
        content = project.contents.get(name)
        if content:
            return dict(content.data)
    except Exception:
        pass

    # 2. Check metadata instances/Weapons/
    try:
        inst = metadata.get_instance("Weapons", name)
        if inst:
            return dict(inst)
    except Exception:
        pass

    return None


def _list_project_weapons(project: Project) -> list[str]:
    """List weapon names in the current project."""
    try:
        refs = project.contents.list("weapons")
        return [r.name for r in refs]
    except Exception:
        return []


def _list_vanilla_weapons(metadata: Metadata) -> list[str]:
    """List vanilla weapon names from metadata."""
    try:
        return metadata.list_instances("Weapons")
    except Exception:
        return []


class _AddWeaponDialog(QDialog):
    """Dialog for choosing how to add a weapon."""

    def __init__(
        self,
        project: Project,
        metadata: Metadata,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("添加武器")
        self._project = project
        self._metadata = metadata
        self._result: dict | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>选择添加方式:</b>"))

        # Reference button
        ref_btn = QPushButton("引用已有武器")
        ref_btn.clicked.connect(self._choose_reference)
        layout.addWidget(ref_btn)

        # Inline button
        inline_btn = QPushButton("内联新建武器")
        inline_btn.clicked.connect(self._choose_inline)
        layout.addWidget(inline_btn)

        # Cancel
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _choose_reference(self) -> None:
        """Pick an existing weapon to reference."""
        project_weapons = _list_project_weapons(self._project)
        vanilla_weapons = _list_vanilla_weapons(self._metadata)
        all_weapons = project_weapons + vanilla_weapons

        # Build display list with Chinese names
        display_items: list[str] = []
        name_map: dict[str, str] = {}
        for w in all_weapons:
            if w in VANILLA_WEAPON_NAMES_ZH:
                display_name = f"{VANILLA_WEAPON_NAMES_ZH[w]} ({w})"
            else:
                display_name = w
            display_items.append(display_name)
            name_map[display_name] = w

        item, ok = QInputDialog.getItem(
            self, "引用武器", "选择武器:",
            display_items, 0, True,
        )
        if ok and item:
            # Extract the actual weapon name from the display string
            actual_name = name_map.get(item, item)
            self._result = {
                "name": actual_name,
                "x": 0.0,
                "y": 0.0,
                "reload": 1.0,
                "top": True,
                "rotate": False,
                "mirror": True,
            }
            self.accept()

    def _choose_inline(self) -> None:
        """Create a blank inline weapon."""
        name, ok = QInputDialog.getText(
            self, "内联新建", "武器名称 (英文, 小写+连字符):",
        )
        if ok and name:
            self._result = {
                "name": name,
                "reload": 1.0,
                "x": 0.0,
                "y": 0.0,
                "bullet": {
                    "type": "BasicBulletType",
                    "damage": 1.0,
                    "speed": 1.0,
                },
            }
            self.accept()

    def result_data(self) -> dict | None:
        return self._result
