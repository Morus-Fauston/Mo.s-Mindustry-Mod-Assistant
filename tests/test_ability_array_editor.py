"""Tests for AbilityArrayEditor (F-49) — offscreen Qt.

Covers the card-list editor contract:
- empty abilities (no JSON key) renders + adds via CommandStack
- add/remove are undoable with the exact granularity of one command
- default type is ShieldRegenFieldAbility
- 15 ability types are offered
- undo/redo restore data
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.core.commands import CommandStack
from app.ui.widgets.ability_array_editor import ABILITY_TYPES, AbilityArrayEditor


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_editor(data: dict | None = None):
    if data is None:
        data = {"type": "UnitType"}
    stack = CommandStack()
    editor = AbilityArrayEditor(
        data=data,
        path="abilities",
        command_stack=stack,
    )
    return editor, stack, data


class TestEmptyState:
    def test_no_key_renders_empty(self, qapp):
        """无 abilities 键时不预写数组，显示空列表。"""
        editor, _, data = _make_editor()
        qapp.processEvents()
        assert "abilities" not in data
        assert editor.value == []


class TestAddAbility:
    def test_add_creates_array_and_entry(self, qapp):
        editor, _, data = _make_editor()
        editor._add_ability()
        qapp.processEvents()
        assert "abilities" in data
        assert len(data["abilities"]) == 1

    def test_default_type(self, qapp):
        editor, _, data = _make_editor()
        editor._add_ability()
        assert data["abilities"][0]["type"] == "ShieldRegenFieldAbility"

    def test_default_values(self, qapp):
        editor, _, data = _make_editor()
        editor._add_ability()
        entry = data["abilities"][0]
        for k in ("amount", "max", "reload", "range"):
            assert k in entry, f"默认值缺 {k}"

    def test_fifteen_types(self):
        assert len(ABILITY_TYPES) == 15


class TestUndoRedo:
    def test_add_undo_removes_entry_then_array(self, qapp):
        """添加应可逐步撤销：条目 → 数组 → 无键。"""
        editor, stack, data = _make_editor()
        editor._add_ability()
        stack.undo()
        assert data["abilities"] == []
        stack.undo()
        assert "abilities" not in data

    def test_add_redo_restores(self, qapp):
        editor, stack, data = _make_editor()
        editor._add_ability()
        stack.undo()
        stack.undo()
        stack.redo()
        stack.redo()
        assert len(data["abilities"]) == 1
        assert data["abilities"][0]["type"] == "ShieldRegenFieldAbility"

    def test_remove_undo_restores(self, qapp):
        editor, stack, data = _make_editor()
        editor._add_ability()
        editor._add_ability()
        editor._remove_ability(0)
        assert len(data["abilities"]) == 1
        stack.undo()
        assert len(data["abilities"]) == 2


class TestTypeDropdown:
    def test_switch_type_rebuilds_form(self, qapp):
        """切换能力类型后字段表单重建（PolymorphicTypeEditor 行为）。"""
        editor, _, data = _make_editor()
        editor._add_ability()
        qapp.processEvents()
        cards = editor._cards
        assert cards, "应有卡片"
        from app.ui.widgets.polymorphic_editor import PolymorphicTypeEditor

        poly = cards[0].findChild(PolymorphicTypeEditor)
        assert poly is not None
        poly._type_combo.setCurrentText("RegenAbility")
        qapp.processEvents()
        assert data["abilities"][0]["type"] == "RegenAbility"


class TestCardRendering:
    """能力卡片渲染回归（v0.2.5 嵌套读值修复）。

    背景：PolymorphicTypeEditor.value 曾用 dict.get("abilities.0") 取不到
    嵌套路径 → 能力卡片字段全空（"仅有能力名"）。修复后必须渲染出字段。
    """

    def test_card_renders_fields(self, qapp):
        """ShieldRegenFieldAbility 卡片应渲染 amount/max/reload/range 字段。"""
        from app.ui.widgets.polymorphic_editor import PolymorphicTypeEditor

        editor, _, data = _make_editor({
            "type": "UnitType",
            "abilities": [{
                "type": "ShieldRegenFieldAbility",
                "amount": 1.0, "max": 100.0, "reload": 100.0, "range": 60.0,
            }],
        })
        qapp.processEvents()
        poly = editor._cards[0].findChild(PolymorphicTypeEditor)
        assert poly is not None
        # 修复前 field_form rows=0（根因：_get_nested 未用于读值）
        assert poly._field_form.rowCount() >= 4, f"能力字段应渲染≥4行，实际 {poly._field_form.rowCount()}"

    def test_card_fields_use_fieldrow(self, qapp):
        """能力字段应由 FieldRow 包裹（马卡龙，与武器卡片一致）。"""
        from app.ui.widgets.field_row import FieldRow
        from app.ui.widgets.polymorphic_editor import PolymorphicTypeEditor

        editor, _, _ = _make_editor({
            "type": "UnitType",
            "abilities": [{
                "type": "ShieldRegenFieldAbility",
                "amount": 1.0, "max": 100.0,
            }],
        })
        qapp.processEvents()
        poly = editor._cards[0].findChild(PolymorphicTypeEditor)
        assert len(poly.findChildren(FieldRow)) >= 2

    def test_delete_button_inside_card(self, qapp):
        """删除按钮应在能力卡片（QGroupBox）内部，而非框外。"""
        from PySide6.QtWidgets import QPushButton

        editor, _, data = _make_editor({
            "type": "UnitType",
            "abilities": [{"type": "ShieldRegenFieldAbility", "amount": 1.0}],
        })
        qapp.processEvents()
        card = editor._cards[0]
        btns = [b for b in card.findChildren(QPushButton) if b.objectName() == "weaponRemoveBtn"]
        assert len(btns) == 1, "卡片内应有删除按钮"

    def test_field_edit_undo(self, qapp):
        """修改能力字段后撤销一次恢复（多态编辑器内部命令栈）。"""
        from app.ui.widgets.polymorphic_editor import PolymorphicTypeEditor
        from app.ui.widgets.num_spin import NumDoubleSpinBox

        editor, stack, data = _make_editor({
            "type": "UnitType",
            "abilities": [{"type": "ShieldRegenFieldAbility", "amount": 1.0}],
        })
        qapp.processEvents()
        poly = editor._cards[0].findChild(PolymorphicTypeEditor)
        spin = poly.findChild(NumDoubleSpinBox)
        spin.setValue(5.0)
        qapp.processEvents()
        assert data["abilities"][0]["amount"] == 5.0
        stack.undo()
        qapp.processEvents()
        assert data["abilities"][0]["amount"] == 1.0, "撤销一次应恢复"

