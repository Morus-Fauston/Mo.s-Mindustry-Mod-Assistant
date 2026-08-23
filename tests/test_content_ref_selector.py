"""UI behavior of the shared content-reference selector."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QListWidget, QToolButton

from app.ui.widgets.content_ref_selector import ContentRefSelector


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Metadata:
    def list_instances(self, category: str) -> list[str]:
        return {
            "Blocks": ["copper-wall"],
            "UnitTypes": ["dagger"],
            "Items": ["copper"],
        }.get(category, [])


def test_selector_filters_bilingual_candidates_and_emits_the_english_identifier(qapp):
    selector = ContentRefSelector(
        metadata=_Metadata(),
        categories=("Blocks", "UnitTypes"),
        names_zh={"blocks": {"copper-wall": "铜墙"}, "units": {"dagger": "尖刀"}},
    )
    selector.show()
    qapp.processEvents()
    selected: list[str] = []
    selector.valueChanged.connect(selected.append)

    selector.open_popup()
    selector.set_search_text("铜")
    candidate_list = selector.findChild(QListWidget, "contentRefList")
    assert candidate_list is not None and candidate_list.count() == 2
    QTest.mouseClick(
        candidate_list.viewport(),
        Qt.MouseButton.LeftButton,
        pos=candidate_list.visualItemRect(candidate_list.item(1)).center(),
    )

    assert selector.value == "copper-wall"
    assert selected == ["copper-wall"]


def test_selector_keyboard_moves_between_candidates_and_confirms(qapp):
    selector = ContentRefSelector(
        metadata=_Metadata(),
        categories=("Blocks", "UnitTypes"),
        names_zh={"blocks": {"copper-wall": "铜墙"}, "units": {"dagger": "尖刀"}},
    )
    selector.show()
    qapp.processEvents()
    selected: list[str] = []
    selector.valueChanged.connect(selected.append)

    selector.open_popup()
    input_widget = selector.findChild(QLineEdit, "contentRefInput")
    assert input_widget is not None
    QTest.keyClick(input_widget, Qt.Key.Key_Down)
    QTest.keyClick(input_widget, Qt.Key.Key_Return)

    assert selector.value == "dagger"
    assert selected == ["dagger"]


def test_selector_bookmarks_jump_in_both_directions(qapp):
    selector = ContentRefSelector(
        metadata=_Metadata(), categories=("Blocks", "UnitTypes", "Items")
    )
    selector.show()
    qapp.processEvents()
    selector.open_popup()
    qapp.processEvents()

    bottom = selector.findChild(QToolButton, "contentRefBookmark")
    assert bottom is not None and bottom.text().startswith("下方：")
    bottom.click()
    qapp.processEvents()

    bookmarks = selector.findChildren(QToolButton, "contentRefBookmark")
    assert any(button.text().startswith("上方：") for button in bookmarks)
