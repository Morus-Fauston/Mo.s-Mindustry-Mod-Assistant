"""Inline bullet editor for weapon forms.

Renders the `bullet` field of a weapon as a type selector dropdown
followed by relevant fields for the chosen BulletType subclass.

Interface:
    .value   — get/set the bullet dict
    .valueChanged — Qt Signal
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core.commands import CommandStack, SetFieldCommand

# ── bullet type choices ─────────────────────────────────────────────────

BULLET_TYPES = [
    "BasicBulletType",
    "LaserBulletType",
    "MissileBulletType",
    "ArtilleryBulletType",
    "FlakBulletType",
]

# Core fields shown for each bullet type (user-expandable later via config)
BULLET_COMMON_FIELDS = [
    "damage", "speed", "lifetime", "pierce", "knockback",
    "splashDamage", "splashDamageRadius", "status", "statusDuration",
    "homingPower", "homingRange", "lightning", "lightningLength",
    "width", "height", "shrinkX", "shrinkY", "collidesAir", "collidesGround",
    "collidesTiles", "collidesTeam", "reflectable", "absorbable",
    "hitShake", "despawnHit",
]


def _load_field_names_zh() -> dict[str, str]:
    path = Path(__file__).parent.parent.parent / "config" / "field_names_zh.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _load_field_docs() -> dict[str, str]:
    path = Path(__file__).parent.parent.parent / "config" / "field_docs.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _display_name(field_name: str, names_zh: dict[str, str]) -> str:
    zh = names_zh.get(field_name)
    if zh:
        return f"{zh} ({field_name})"
    return field_name


class BulletEditor(QGroupBox):
    """Inline bullet sub-form for weapon editing."""

    valueChanged = Signal()

    def __init__(
        self,
        data: dict,          # the parent weapon data dict
        path: str,           # path to bullet, e.g. "bullet"
        command_stack: CommandStack,
        parent: QWidget | None = None,
        field_names_zh: dict[str, str] | None = None,
        field_docs: dict[str, str] | None = None,
    ) -> None:
        super().__init__("子弹")
        self._data = data
        self._path = path
        self._commands = command_stack
        self._widgets: dict[str, QWidget] = {}
        self._field_names_zh = field_names_zh or _load_field_names_zh()
        self._field_docs = field_docs or _load_field_docs()

        self._setup_ui()

    # ── public interface ─────────────────────────────────────────────────

    @property
    def value(self) -> dict:
        return self._data.get(self._path, {})

    @value.setter
    def value(self, new_value: dict) -> None:
        self._data[self._path] = new_value
        self._rebuild()

    # ── UI ───────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)

        # Type selector
        type_layout = QFormLayout()
        self._type_combo = QComboBox()
        self._type_combo.addItems(BULLET_TYPES)
        current_type = self.value.get("type", "BasicBulletType")
        idx = self._type_combo.findText(current_type)
        if idx >= 0:
            self._type_combo.setCurrentIndex(idx)
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addRow("类型", self._type_combo)
        layout.addLayout(type_layout)

        # Field form
        self._field_form = QFormLayout()
        layout.addLayout(self._field_form)

        self._rebuild_fields()

    def _rebuild(self) -> None:
        """Rebuild the entire widget."""
        while self.layout().count() > 0:
            item = self.layout().takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._setup_ui()

    def _rebuild_fields(self) -> None:
        """Rebuild field widgets from current bullet data."""
        # Clear existing
        while self._field_form.count() > 0:
            item = self._field_form.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._widgets.clear()

        bullet_data = self.value
        for fname in BULLET_COMMON_FIELDS:
            if fname in bullet_data:
                widget = self._create_widget(fname, bullet_data[fname])
                if widget:
                    label_text = _display_name(fname, self._field_names_zh)
                    row_label = QLabel(label_text)
                    doc = self._field_docs.get(fname, "")
                    if doc:
                        row_label.setToolTip(doc)
                        widget.setToolTip(doc)
                    self._field_form.addRow(row_label, widget)

    # ── field mutation ───────────────────────────────────────────────────

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
        self._set_field("type", new_type)
        self._rebuild_fields()

    # ── widget creation ──────────────────────────────────────────────────

    def _create_widget(self, fname: str, val: Any) -> QWidget | None:
        if isinstance(val, bool):
            cb = QCheckBox()
            cb.setChecked(val)
            cb.toggled.connect(lambda v, n=fname: self._set_field(n, v))
            self._widgets[fname] = cb
            return cb
        elif isinstance(val, float):
            spin = QDoubleSpinBox()
            spin.setRange(-999999.0, 999999.0)
            spin.setDecimals(3)
            spin.setValue(val)
            spin.valueChanged.connect(lambda v, n=fname: self._set_field(n, v))
            self._widgets[fname] = spin
            return spin
        elif isinstance(val, int):
            spin = QSpinBox()
            spin.setRange(-999999, 999999)
            spin.setValue(val)
            spin.valueChanged.connect(lambda v, n=fname: self._set_field(n, v))
            self._widgets[fname] = spin
            return spin
        elif isinstance(val, str):
            edit = QLineEdit()
            edit.setText(val)
            edit.textChanged.connect(lambda t, n=fname: self._set_field(n, t if t else None))
            self._widgets[fname] = edit
            return edit
        return None
