"""Polymorphic type editor: unified widget for type-select → field-group → form.

Used for:
- BulletType editing (inside weapons)
- Ability editing (inside units, v0.2.2)
- Any future polymorphic inline object

Interface:
    .value        — get/set the data dict (must contain "type" key)
    .valueChanged — Signal, emitted on any mutation

Architecture (ADR-006):
    Type dropdown → read field_groups.json for selected type → render form.
    Adding a new polymorphic type only requires a config entry, no code change.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core.commands import CommandStack, SetFieldCommand
from .check_toggle import CheckToggle
from .num_spin import NumSpinBox, NumDoubleSpinBox
from .auto_width_edit import AutoWidthEdit
from .label_helper import rich_label
from ...core.config_loader import (
    display_name,
    get_field_docs,
    get_field_groups,
    get_field_names_zh,
)


class PolymorphicTypeEditor(QGroupBox):
    """A type selector + config-driven field form for polymorphic inline objects.

    Args:
        data: The parent data dict (e.g. weapon data containing "bullet").
        path: Dot-path to the polymorphic object within data (e.g. "bullet").
        type_choices: List of valid type names for the dropdown.
        command_stack: For undo/redo support.
        title: Group box title (e.g. "子弹", "能力").
        type_label: Label for the type dropdown (e.g. "类型", "能力类型").
    """

    valueChanged = Signal()

    def __init__(
        self,
        data: dict,
        path: str,
        type_choices: list[str],
        command_stack: CommandStack,
        title: str = "对象",
        type_label: str = "类型",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)
        self._data = data
        self._path = path
        self._type_choices = type_choices
        self._commands = command_stack
        self._type_label = type_label

        self._field_groups = get_field_groups()
        self._field_names_zh = get_field_names_zh()
        self._field_docs = get_field_docs()
        self._widgets: dict[str, QWidget] = {}

        self._setup_ui()

    # ── public interface ─────────────────────────────────────────────────

    @property
    def value(self) -> dict:
        return self._data.get(self._path, {})

    @value.setter
    def value(self, new_value: dict) -> None:
        self._data[self._path] = new_value
        self._rebuild_fields()

    # ── UI setup ─────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)

        # Type selector row
        type_form = QFormLayout()
        type_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        type_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        type_form.setSpacing(4)
        self._type_combo = QComboBox()
        self._type_combo.addItems(self._type_choices)
        current_type = self.value.get("type", "")
        if current_type in self._type_choices:
            self._type_combo.setCurrentText(current_type)
        elif self._type_choices:
            self._type_combo.setCurrentIndex(0)
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        type_form.addRow(self._type_label, self._type_combo)
        layout.addLayout(type_form)

        # Field form (rebuilt on type change)
        self._field_form = QFormLayout()
        self._field_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self._field_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._field_form.setSpacing(4)
        layout.addLayout(self._field_form)

        self._rebuild_fields()

    # ── field rendering ──────────────────────────────────────────────────

    def _rebuild_fields(self) -> None:
        """Clear and rebuild field widgets based on current type's config."""
        while self._field_form.count() > 0:
            item = self._field_form.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._widgets.clear()

        obj_data = self.value
        obj_type = obj_data.get("type", "")
        groups_config = self._field_groups.get(obj_type, {})

        if not groups_config:
            # Fallback: show all existing fields flat (no grouping)
            for fname, val in obj_data.items():
                if fname == "type":
                    continue
                widget = self._create_widget(fname, val)
                if widget:
                    self._add_field_row(fname, widget)
            return

        # Render groups: required always, optional only if present in data
        for group_name, group_def in groups_config.items():
            required = group_def.get("required", [])
            optional = group_def.get("optional", [])

            visible_names = list(required)
            for n in optional:
                if n in obj_data:
                    visible_names.append(n)

            for fname in visible_names:
                if fname == "type":
                    continue
                val = obj_data.get(fname)
                widget = self._create_widget(fname, val)
                if widget:
                    self._add_field_row(fname, widget)

    def _add_field_row(self, fname: str, widget: QWidget) -> None:
        """Add a labeled row to the field form with tooltip support."""
        zh = self._field_names_zh.get(fname, "")
        row_label = rich_label(zh, fname)
        doc = self._field_docs.get(fname, "")
        if doc:
            row_label.setToolTip(doc)
            widget.setToolTip(doc)
        self._field_form.addRow(row_label, widget)

    # ── data mutation ────────────────────────────────────────────────────

    def _data_path(self, field_name: str = "") -> str:
        if field_name:
            return f"{self._path}.{field_name}"
        return self._path

    def _set_field(self, field_name: str, new_value: Any) -> None:
        cmd = SetFieldCommand(
            data=self._data,
            path=self._data_path(field_name),
            new_value=new_value,
        )
        self._commands.execute(cmd)
        self.valueChanged.emit()

    def _on_type_changed(self, new_type: str) -> None:
        """Handle type dropdown change: update data and rebuild fields."""
        self._set_field("type", new_type)
        self._rebuild_fields()

    # ── widget factory ───────────────────────────────────────────────────

    def _create_widget(self, fname: str, val: Any) -> QWidget | None:
        """Create the appropriate widget for a field value."""
        if isinstance(val, bool):
            cb = CheckToggle()
            cb.setChecked(val)
            cb.toggled.connect(lambda v, n=fname: self._set_field(n, v))
            self._widgets[fname] = cb
            return cb
        elif isinstance(val, float):
            spin = NumDoubleSpinBox()
            spin.setRange(-999999.0, 999999.0)
            spin.setDecimals(3)
            spin.setFixedWidth(70)
            spin.setValue(val)
            spin.valueChanged.connect(lambda v, n=fname: self._set_field(n, v))
            self._widgets[fname] = spin
            return spin
        elif isinstance(val, int):
            spin = NumSpinBox()
            spin.setRange(-999999, 999999)
            spin.setFixedWidth(70)
            spin.setValue(val)
            spin.valueChanged.connect(lambda v, n=fname: self._set_field(n, v))
            self._widgets[fname] = spin
            return spin
        elif isinstance(val, str):
            edit = AutoWidthEdit()
            edit.setText(val)
            edit.textChanged.connect(
                lambda t, n=fname: self._set_field(n, t if t else None)
            )
            self._widgets[fname] = edit
            return edit
        else:
            # Unsupported type: show read-only label
            label = QLabel(str(val) if val is not None else "(空)")
            label.setObjectName("mutedText")
            return label
