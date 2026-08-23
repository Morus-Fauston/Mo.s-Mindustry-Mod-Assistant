"""Shared searchable selector for vanilla and current-project content references."""

from __future__ import annotations

from typing import Any, Iterable

from PySide6.QtCore import QEvent, QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...core.ref_candidates import RefCandidate, resolve_candidates


class ContentRefSelector(QWidget):
    """Select a content identifier with grouped Chinese/English search results."""

    valueChanged = Signal(str)

    def __init__(
        self,
        metadata: Any,
        project: Any | None = None,
        categories: Iterable[str] = (),
        names_zh: dict[str, dict[str, str]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._metadata = metadata
        self._project = project
        self._categories = tuple(categories)
        self._names_zh = names_zh or {}
        self._value = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._input = QLineEdit()
        self._input.setObjectName("contentRefInput")
        self._input.setProperty("fieldType", "ref")
        self._input.textEdited.connect(self._on_text_edited)
        self._input.returnPressed.connect(self._choose_current_candidate)
        self._input.installEventFilter(self)
        layout.addWidget(self._input)

        self._open_button = QToolButton()
        self._open_button.setText("▾")
        self._open_button.setToolTip("选择内容")
        self._open_button.clicked.connect(self.open_popup)
        layout.addWidget(self._open_button)

        # Qt.Popup makes this a top-level surface even with a QObject parent.
        # Keeping the parent lets automated UI checks find the popup widgets.
        self._popup = QFrame(self, Qt.WindowType.Popup)
        self._popup.setObjectName("contentRefPopup")
        popup_layout = QVBoxLayout(self._popup)
        popup_layout.setContentsMargins(4, 4, 4, 4)
        self._list = QListWidget()
        self._list.setObjectName("contentRefList")
        self._list.itemClicked.connect(self._choose_item)
        self._list.itemActivated.connect(self._choose_item)
        self._list.verticalScrollBar().valueChanged.connect(self._update_navigation)
        popup_layout.addWidget(self._list)

        self._sticky_header = QFrame(self._list.viewport())
        self._sticky_header.setObjectName("contentRefStickyHeader")
        sticky_layout = QHBoxLayout(self._sticky_header)
        sticky_layout.setContentsMargins(8, 2, 8, 2)
        self._sticky_label = QLabel()
        self._sticky_label.setObjectName("contentRefStickyLabel")
        sticky_layout.addWidget(self._sticky_label)

        self._top_bookmarks = QFrame(self._list.viewport())
        self._top_bookmarks.setObjectName("contentRefTopBookmarks")
        self._top_bookmarks_layout = QHBoxLayout(self._top_bookmarks)
        self._top_bookmarks_layout.setContentsMargins(4, 2, 4, 2)
        self._top_bookmarks_layout.setSpacing(2)

        self._bottom_bookmarks = QFrame(self._list.viewport())
        self._bottom_bookmarks.setObjectName("contentRefBottomBookmarks")
        self._bottom_bookmarks_layout = QHBoxLayout(self._bottom_bookmarks)
        self._bottom_bookmarks_layout.setContentsMargins(4, 2, 4, 2)
        self._bottom_bookmarks_layout.setSpacing(2)
        self._popup.resize(360, 280)

    @property
    def value(self) -> str:
        return self._value

    def set_value(self, value: str, emit: bool = False) -> None:
        self._value = value
        self._input.setText(self._label_for_value(value))
        self._input.setCursorPosition(0)
        if emit:
            self.valueChanged.emit(value)

    def set_search_text(self, query: str) -> None:
        self._input.setText(query)
        self._rebuild_candidates(query)

    def open_popup(self) -> None:
        self._rebuild_candidates("")
        origin = self.mapToGlobal(QPoint(0, self.height()))
        self._popup.move(origin)
        self._popup.show()
        self._resize_overlays()
        self._input.setFocus()

    def _on_text_edited(self, text: str) -> None:
        if not self._popup.isVisible():
            self.open_popup()
        self._rebuild_candidates(text)

    def _rebuild_candidates(self, query: str) -> None:
        candidates = resolve_candidates(
            self._metadata,
            self._project,
            self._categories,
            query,
            self._names_zh,
        )
        self._list.clear()
        current_category = ""
        for candidate in candidates:
            if candidate.category != current_category:
                current_category = candidate.category
                header = QListWidgetItem(_category_title(current_category))
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                header.setData(Qt.ItemDataRole.UserRole, None)
                self._list.addItem(header)
            item = QListWidgetItem(candidate.label)
            item.setData(Qt.ItemDataRole.UserRole, candidate)
            self._list.addItem(item)
        if not candidates:
            empty = QListWidgetItem("没有匹配的内容")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(empty)
        self._select_first_candidate()
        self._update_navigation()

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        if watched is self._input and event.type() == QEvent.Type.KeyPress:
            key = event.key()  # type: ignore[attr-defined]
            if key == Qt.Key.Key_Down:
                self._move_current(1)
                return True
            if key == Qt.Key.Key_Up:
                self._move_current(-1)
                return True
            if key == Qt.Key.Key_Escape and self._popup.isVisible():
                self._popup.hide()
                return True
        return super().eventFilter(watched, event)

    def _select_first_candidate(self) -> None:
        for index in range(self._list.count()):
            item = self._list.item(index)
            if isinstance(item.data(Qt.ItemDataRole.UserRole), RefCandidate):
                self._list.setCurrentItem(item)
                return

    def _move_current(self, offset: int) -> None:
        index = self._list.currentRow() + offset
        while 0 <= index < self._list.count():
            item = self._list.item(index)
            if isinstance(item.data(Qt.ItemDataRole.UserRole), RefCandidate):
                self._list.setCurrentItem(item)
                self._list.scrollToItem(item)
                return
            index += offset

    def _choose_current_candidate(self) -> None:
        item = self._list.currentItem()
        if item is not None:
            self._choose_item(item)

    def _choose_item(self, item: QListWidgetItem) -> None:
        candidate = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(candidate, RefCandidate):
            return
        self.set_value(candidate.value, emit=True)
        self._popup.hide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_overlays()

    def _resize_overlays(self) -> None:
        viewport = self._list.viewport()
        width = viewport.width()
        self._sticky_header.setGeometry(0, 0, width, 24)
        self._top_bookmarks.setGeometry(0, 24, width, 28)
        self._bottom_bookmarks.setGeometry(0, max(0, viewport.height() - 28), width, 28)
        self._sticky_header.raise_()
        self._top_bookmarks.raise_()
        self._bottom_bookmarks.raise_()

    def _update_navigation(self, current_row: int | None = None) -> None:
        category_titles = {_category_title(category) for category in self._categories}
        headers = [
            (index, self._list.item(index))
            for index in range(self._list.count())
            if self._list.item(index).data(Qt.ItemDataRole.UserRole) is None
            and self._list.item(index).text() in category_titles
        ]
        if len(headers) <= 1:
            self._sticky_header.hide()
            self._top_bookmarks.hide()
            self._bottom_bookmarks.hide()
            return

        if current_row is None:
            current_row = self._list.indexAt(QPoint(0, 1)).row()
        current_position = 0
        for position, (row, _) in enumerate(headers):
            if row <= current_row:
                current_position = position
            else:
                break
        self._sticky_label.setText(headers[current_position][1].text())
        self._sticky_header.show()
        self._fill_bookmarks(self._top_bookmarks_layout, headers[:current_position], True)
        self._fill_bookmarks(self._bottom_bookmarks_layout, headers[current_position + 1:], False)
        self._top_bookmarks.setVisible(current_position > 0)
        self._bottom_bookmarks.setVisible(current_position < len(headers) - 1)
        self._resize_overlays()

    def _fill_bookmarks(self, layout: QHBoxLayout, headers, upward: bool) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for row, header in headers:
            button = QToolButton()
            button.setObjectName("contentRefBookmark")
            button.setText(("上方：" if upward else "下方：") + header.text())
            button.setToolTip("跳转到" + header.text())
            button.clicked.connect(lambda _=False, target=row: self._jump_to_group(target))
            layout.addWidget(button)
        layout.addStretch()

    def _jump_to_group(self, row: int) -> None:
        item = self._list.item(row)
        self._list.scrollToItem(item, self._list.ScrollHint.PositionAtTop)
        # scrollToItem updates the viewport on the next event-loop turn.  Use
        # the clicked header immediately so opposite-direction bookmarks are
        # available without waiting for another scroll event.
        self._update_navigation(row)

    def _label_for_value(self, value: str) -> str:
        if not value:
            return ""
        for candidate in resolve_candidates(
            self._metadata,
            self._project,
            self._categories,
            names_zh=self._names_zh,
        ):
            if candidate.value == value:
                return candidate.label
        return value


def _category_title(category: str) -> str:
    labels = {
        "Blocks": "方块",
        "UnitTypes": "单位",
        "Items": "物品",
        "Liquids": "液体",
        "StatusEffects": "状态效果",
        "Planets": "星球",
        "SectorPresets": "战区",
        "Weapons": "武器",
    }
    return labels.get(category, category)
