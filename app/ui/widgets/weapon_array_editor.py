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
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .check_toggle import CheckToggle
from .num_spin import NumSpinBox, NumDoubleSpinBox
from .auto_width_edit import AutoWidthEdit
from .label_helper import rich_label
from .polymorphic_editor import BULLET_TYPES

# NOTE: These are imported lazily or at module level depending on need
from ...core.commands import ArrayInsertCommand, ArrayMoveCommand, ArrayRemoveCommand, CommandStack
from ...core.metadata import Metadata
from ...core.project import Project


# ── config: default override fields shown on weapon reference cards ──────

DEFAULT_OVERRIDE_FIELDS = ["x", "y", "reload", "top", "rotate", "mirror"]

# ── 武器覆盖字段分组标签（二级菜单用） ────────────────────────────────────

_WEAPON_GROUP_LABELS = {
    "basic": "基础",
    "behavior": "行为",
    "shooting": "射击",
    "targeting": "目标",
    "continuous": "持续射击",
    "effects": "音效与特效",
    "rendering": "渲染",
}

# 覆盖字段的默认值（按分组推断类型）
_OVERRIDE_DEFAULTS = {
    "x": 0.0, "y": 0.0, "shootX": 0.0, "shootY": 0.0, "reload": 1.0,
    "top": True, "rotate": False, "mirror": True, "alternate": True,
    "rotateSpeed": 5.0, "shootCone": 15.0, "inaccuracy": 0.0,
    "controllable": True, "aiControllable": True,
    "shots": 1, "shotDelay": 5.0, "recoil": 1.0, "recoilTime": 20.0,
    "shake": 0.0, "velocityRnd": 0.0, "cooldownTime": 30.0,
    "autoTarget": False, "predictTarget": True, "targetInterval": 40,
    "continuous": False, "alwaysContinuous": False,
    "shootSoundVolume": 0.5, "layerOffset": 0.0, "shadow": 0.0,
}


def _override_default(fname: str) -> Any:
    """返回覆盖字段的默认值，未知字段返回 0.0。"""
    return _OVERRIDE_DEFAULTS.get(fname, 0.0)

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
        total = len(self.value)
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
                total=total,
            )
            card.modified.connect(self._on_card_modified)
            card.removeRequested.connect(self._remove_weapon)
            card.moveRequested.connect(self._move_weapon)
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

    def _move_weapon(self, from_index: int, to_index: int) -> None:
        """调整武器顺序（可撤销）。"""
        arr = self.value
        if not (0 <= from_index < len(arr) and 0 <= to_index < len(arr)):
            return
        cmd = ArrayMoveCommand(
            data=self._data,
            path=self._path,
            from_index=from_index,
            to_index=to_index,
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
    moveRequested = Signal(int, int)  # (from_index, to_index) 拖拽/按钮排序

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
        total: int = 1,
    ) -> None:
        super().__init__()
        self._weapon_data = weapon_data
        self._index = index
        self._total = total
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

        # Header: name + mode badge + 排序按钮 + [×] remove
        header = QHBoxLayout()
        title = QLabel(f"<b>{self._weapon_name()}</b>")
        header.addWidget(title)

        mode_badge = QLabel("内联" if self._is_inline else "引用")
        mode_badge.setObjectName("badgeInline" if self._is_inline else "badgeRef")
        header.addWidget(mode_badge)
        header.addStretch()

        # 排序按钮：上移 / 下移（纯文本箭头）
        up_btn = QToolButton()
        up_btn.setObjectName("weaponMoveBtn")
        up_btn.setText("↑")
        up_btn.setFixedSize(20, 20)
        up_btn.setToolTip("上移")
        up_btn.setEnabled(self._index > 0)
        up_btn.clicked.connect(lambda: self.moveRequested.emit(self._index, self._index - 1))
        header.addWidget(up_btn)

        down_btn = QToolButton()
        down_btn.setObjectName("weaponMoveBtn")
        down_btn.setText("↓")
        down_btn.setFixedSize(20, 20)
        down_btn.setToolTip("下移")
        down_btn.setEnabled(self._index < self._total - 1)
        down_btn.clicked.connect(lambda: self.moveRequested.emit(self._index, self._index + 1))
        header.addWidget(down_btn)

        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setObjectName("weaponRemoveBtn")
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
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setSpacing(4)

        # Name
        name_input = AutoWidthEdit()
        name_input.setText(self._weapon_data.get("name", ""))
        name_input.textChanged.connect(
            lambda t: self._set_field("name", t if t else None)
        )
        form.addRow(rich_label(self._field_names_zh.get("name", ""), "name"), name_input)

        # Override fields (default set: x, y, reload, top, rotate, mirror)
        override_names = [
            f for f in DEFAULT_OVERRIDE_FIELDS
            if f in self._weapon_data
        ]
        # Always show name field, plus any override fields that exist in data
        for fname in override_names:
            widget = self._create_override_widget(fname)
            if widget:
                zh = self._field_names_zh.get(fname, "")
                row_label = rich_label(zh, fname)
                doc = self._field_docs.get(fname, "")
                if doc:
                    row_label.setToolTip(doc)
                    widget.setToolTip(doc)
                form.addRow(row_label, widget)

        layout.addLayout(form)

        # "+ 添加覆盖" button（左对齐文本按钮）
        add_override_btn = QPushButton("+ 添加覆盖字段")
        add_override_btn.setObjectName("weaponActionBtn")
        add_override_btn.clicked.connect(self._show_add_override_menu)
        layout.addWidget(add_override_btn)

        # [展开为内联] button（左对齐文本按钮）
        expand_btn = QPushButton("展开为内联")
        expand_btn.setObjectName("weaponActionBtn")
        expand_btn.clicked.connect(self._expand_to_inline)
        layout.addWidget(expand_btn)

    def _build_inline_form(self, layout: QVBoxLayout) -> None:
        """Inline mode: config-driven weapon fields + bullet sub-form."""
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setSpacing(4)

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
                    zh = self._field_names_zh.get(fname, "")
                    row_label = rich_label(zh, fname)
                    doc = self._field_docs.get(fname, "")
                    if doc:
                        row_label.setToolTip(doc)
                        widget.setToolTip(doc)
                    form.addRow(row_label, widget)

        layout.addLayout(form)

        # Bullet sub-form (PolymorphicTypeEditor, ADR-006)
        from .polymorphic_editor import BULLET_TYPES, PolymorphicTypeEditor
        bullet_editor = PolymorphicTypeEditor(
            data=self._parent_data,
            path=self._data_path("bullet"),
            type_choices=BULLET_TYPES,
            command_stack=self._commands,
            title="子弹",
            type_label="类型",
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
            cb = CheckToggle()
            cb.setChecked(val)
            cb.toggled.connect(on_change)
            return cb
        elif isinstance(val, float):
            spin = NumDoubleSpinBox()
            spin.setRange(-999999.0, 999999.0)
            spin.setDecimals(3)
            spin.setFixedWidth(70)
            spin.setValue(val)
            spin.valueChanged.connect(on_change)
            return spin
        elif isinstance(val, int):
            spin = NumSpinBox()
            spin.setRange(-999999, 999999)
            spin.setFixedWidth(70)
            spin.setValue(val)
            spin.valueChanged.connect(on_change)
            return spin
        elif isinstance(val, str):
            edit = AutoWidthEdit()
            edit.setText(val)
            edit.textChanged.connect(on_change)
            return edit
        return None

    # ── actions ──────────────────────────────────────────────────────────

    def _show_add_override_menu(self) -> None:
        """按分组筛选的二级菜单：分组名 → 字段列表。

        不平铺全部字段，而是按 field_groups.json 的 Weapon 分组组织，
        每个分组一个子菜单，列出该组尚未覆盖的 optional 字段。
        """
        weapon_groups = self._field_groups.get("Weapon", {})
        data_keys = set(self._weapon_data.keys())

        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        total = 0

        for group_name, group_def in weapon_groups.items():
            if group_name == "bullet":
                continue  # 子弹走独立编辑器，不作为覆盖字段
            optional = group_def.get("optional", [])
            candidates = [f for f in optional if f not in data_keys]
            if not candidates:
                continue

            label = _WEAPON_GROUP_LABELS.get(group_name, group_name)
            submenu = menu.addMenu(label)
            for fname in candidates:
                action = submenu.addAction(_display_name(fname, self._field_names_zh))
                action.setData(fname)
                doc = self._field_docs.get(fname, "")
                if doc:
                    action.setToolTip(doc)
                total += 1

        if total == 0:
            menu.addAction("(无更多可覆盖字段)").setEnabled(False)
            menu.exec(self.mapToGlobal(self.rect().center()))
            return

        chosen = menu.exec(self.mapToGlobal(self.rect().center()))
        if chosen and chosen.data():
            fname = chosen.data()
            self._set_field(fname, _override_default(fname))
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
    """完整的新建武器对话框：名称 + 模式选择 + 子弹类型预览。"""

    def __init__(
        self,
        project: Project,
        metadata: Metadata,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建武器")
        self.setMinimumWidth(380)
        self._project = project
        self._metadata = metadata
        self._result: dict | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 模式选择（放在最前面）
        layout.addWidget(QLabel("<b>添加方式</b>"))
        self._ref_radio = QRadioButton("引用已有武器")
        self._ref_radio.setChecked(True)
        self._inline_radio = QRadioButton("内联新建武器")
        layout.addWidget(self._ref_radio)
        layout.addWidget(self._inline_radio)

        # 引用模式：武器下拉
        self._ref_combo = QComboBox()
        self._ref_combo.setEditable(True)
        self._ref_combo.setFixedWidth(240)
        self._populate_weapon_list()
        layout.addWidget(self._ref_combo)

        # 内联模式：名称输入框（引用模式隐藏）
        self._name_edit = AutoWidthEdit()
        self._name_edit.setPlaceholderText("英文, 小写+连字符, 如 salvo-mk2")
        self._name_edit.setVisible(False)
        layout.addWidget(self._name_edit)

        # 内联模式：子弹类型下拉 + 预览
        self._bullet_combo = QComboBox()
        self._bullet_combo.setFixedWidth(240)
        self._bullet_combo.addItems(BULLET_TYPES)
        self._bullet_combo.setVisible(False)
        layout.addWidget(self._bullet_combo)

        self._bullet_preview = QLabel(self._bullet_type_desc(BULLET_TYPES[0]))
        self._bullet_preview.setWordWrap(True)
        self._bullet_preview.setObjectName("bulletPreview")
        self._bullet_preview.setVisible(False)
        layout.addWidget(self._bullet_preview)

        # 模式切换联动
        self._ref_radio.toggled.connect(self._on_mode_changed)
        self._bullet_combo.currentTextChanged.connect(
            lambda t: self._bullet_preview.setText(self._bullet_type_desc(t))
        )

        # 确定 / 取消
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _populate_weapon_list(self) -> None:
        project_weapons = _list_project_weapons(self._project)
        vanilla_weapons = _list_vanilla_weapons(self._metadata)
        for w in project_weapons + vanilla_weapons:
            if w in VANILLA_WEAPON_NAMES_ZH:
                self._ref_combo.addItem(f"{VANILLA_WEAPON_NAMES_ZH[w]} ({w})", w)
            else:
                self._ref_combo.addItem(w, w)

    def _on_mode_changed(self, ref_checked: bool) -> None:
        self._ref_combo.setVisible(ref_checked)
        self._name_edit.setVisible(not ref_checked)
        self._bullet_combo.setVisible(not ref_checked)
        self._bullet_preview.setVisible(not ref_checked)

    def _on_accept(self) -> None:
        if self._ref_radio.isChecked():
            actual = self._ref_combo.currentData() or self._ref_combo.currentText()
            if not actual:
                QMessageBox.warning(self, "提示", "请选择或输入一个武器引用")
                return
            self._result = {
                "name": actual,
                "x": 0.0, "y": 0.0, "reload": 1.0,
                "top": True, "rotate": False, "mirror": True,
            }
            # 引用模式下 name 指向被引用武器
        else:
            name = self._name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "提示", "请输入武器名称")
                return
            bullet_type = self._bullet_combo.currentText()
            self._result = {
                "name": name,
                "reload": 1.0, "x": 0.0, "y": 0.0,
                "bullet": {"type": bullet_type, "damage": 1.0, "speed": 1.0},
            }
        self.accept()

    @staticmethod
    def _bullet_type_desc(bullet_type: str) -> str:
        descs = {
            "BasicBulletType": "基础子弹：直线飞行，命中造成伤害。最通用的子弹类型。",
            "LaserBulletType": "激光：瞬时命中，穿透多个目标，无飞行时间。",
            "MissileBulletType": "导弹：带制导追踪，可拐弯追击目标。",
            "ArtilleryBulletType": "火炮：抛物线弹道，落地造成范围溅射伤害。",
            "FlakBulletType": "高射炮：在空中引爆，对范围内目标造成伤害。",
        }
        return descs.get(bullet_type, "")

    def result_data(self) -> dict | None:
        return self._result
