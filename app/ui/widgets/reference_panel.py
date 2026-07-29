"""Reference comparison panel.

Displays a table comparing the current content's values against a
vanilla reference instance. Shows: field, my value, reference value, diff.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QSplitter,
)

from ...core.metadata import Metadata
from ...core.config_loader import (
    display_name as _display_name_fn,
    get_category_names_zh,
    get_field_names_zh,
    get_vanilla_weapon_names_zh,
)

# ── Chinese translations (from centralized config) ───────────────────────

CATEGORY_NAMES_ZH = get_category_names_zh()


def _load_field_names_zh() -> dict[str, str]:
    return get_field_names_zh()


def _display_name(field_name: str, names_zh: dict[str, str]) -> str:
    return _display_name_fn(field_name, names_zh)


class ReferencePanel(QWidget):
    """Shows a field-by-field comparison table between current and reference data."""

    def __init__(self, metadata: Metadata, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._metadata = metadata
        self._current_data: dict | None = None
        self._ref_data: dict | None = None
        self._field_names_zh = _load_field_names_zh()

        self._setup_ui()

    # ── public interface ─────────────────────────────────────────────────

    def set_comparison(self, current_data: dict, ref_data: dict) -> None:
        """Set the two datasets to compare and refresh the table."""
        self._current_data = current_data
        self._ref_data = ref_data
        self._update_table()

    def clear(self) -> None:
        """Clear the comparison."""
        self._current_data = None
        self._ref_data = None
        self._table.setRowCount(0)

    # ── UI ───────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("<b>参考对比</b>")
        layout.addWidget(title)

        # Table: field | my value | ref value | diff
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["字段", "我的值", "参考值"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

    def _update_table(self) -> None:
        """Rebuild the comparison table from current and reference data."""
        if self._current_data is None or self._ref_data is None:
            self._table.setRowCount(0)
            return

        # Collect all field names from both datasets
        all_fields = sorted(set(self._current_data.keys()) | set(self._ref_data.keys()))

        self._table.setRowCount(len(all_fields))
        for row, field_name in enumerate(all_fields):
            my_val = self._current_data.get(field_name, "-")
            ref_val = self._ref_data.get(field_name, "-")

            # Field name (Chinese if available)
            field_label = _display_name(field_name, self._field_names_zh)
            self._table.setItem(row, 0, QTableWidgetItem(field_label))

            # My value
            my_item = QTableWidgetItem(_format_value(my_val))
            ref_item = QTableWidgetItem(_format_value(ref_val))

            if my_val != ref_val:
                my_item.setBackground(Qt.GlobalColor.yellow)
                ref_item.setBackground(Qt.GlobalColor.yellow)
            elif my_val == "-":
                my_item.setForeground(Qt.GlobalColor.gray)
            elif ref_val == "-":
                ref_item.setForeground(Qt.GlobalColor.gray)

            self._table.setItem(row, 1, my_item)
            self._table.setItem(row, 2, ref_item)


# ═══════════════════════════════════════════════════════════════════════════
# Reference picker dialog
# ═══════════════════════════════════════════════════════════════════════════

class _ReferencePicker(QDialog):
    """Dialog for selecting a reference instance to compare against."""

    # Map from original category name to its reverse lookup by Chinese label
    _CAT_TO_DISPLAY: dict[str, str] = {}
    _DISPLAY_TO_CAT: dict[str, str] = {}

    def __init__(self, metadata: Metadata, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("导入参考")
        self.setMinimumSize(500, 400)
        self._metadata = metadata
        self._selected: str | None = None
        self._category: str | None = None
        self._field_names_zh = _load_field_names_zh()

        self._setup_ui()

    @property
    def selected_category(self) -> str | None:
        return self._category

    @property
    def selected_name(self) -> str | None:
        return self._selected

    def _category_display(self, cat: str) -> str:
        return CATEGORY_NAMES_ZH.get(cat, cat)

    def _instance_display(self, name: str, category: str) -> str:
        """Show instance with Chinese name where available."""
        if category == "Weapons":
            vanilla_names = get_vanilla_weapon_names_zh()
            zh = vanilla_names.get(name)
            if zh:
                return f"{zh} ({name})"
        return name

    def _instance_original(self, display_name: str) -> str:
        """Extract original instance name from display name."""
        # If it has "(original)" suffix, extract it
        if "(" in display_name and display_name.endswith(")"):
            start = display_name.index("(") + 1
            end = display_name.rindex(")")
            return display_name[start:end]
        return display_name

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: categories
        cat_list = QListWidget()
        cats = self._metadata.list_instance_categories()
        for cat in cats:
            cat_list.addItem(self._category_display(cat))
        cat_list.currentTextChanged.connect(self._on_category_changed)
        splitter.addWidget(cat_list)

        # Right: instances
        self._instance_list = QListWidget()
        splitter.addWidget(self._instance_list)

        layout.addWidget(splitter)

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_category_changed(self, display_cat: str) -> None:
        # Reverse map display category to original
        for orig, display in CATEGORY_NAMES_ZH.items():
            if display == display_cat:
                self._category = orig
                break
        else:
            self._category = display_cat

        self._instance_list.clear()
        instances = self._metadata.list_instances(self._category)
        for inst in instances:
            self._instance_list.addItem(self._instance_display(inst, self._category))

    def _accept(self) -> None:
        item = self._instance_list.currentItem()
        if item:
            self._selected = self._instance_original(item.text())
            self.accept()
        else:
            self.reject()


def _format_value(val: Any) -> str:
    """Format a value for display in the comparison table."""
    if isinstance(val, dict):
        return "{...}"
    elif isinstance(val, list):
        return f"[{len(val)} 项]"
    elif isinstance(val, bool):
        return str(val).lower()
    elif isinstance(val, float):
        return f"{val:.2f}"
    elif val is None or val == "-":
        return "-"
    return str(val)
