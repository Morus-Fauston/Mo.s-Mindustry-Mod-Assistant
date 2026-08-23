"""Editable Planet-name set used by UnlockableContent.shownPlanets."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ...core.commands import CommandStack, DeleteFieldCommand, SetFieldCommand
from ...core.config_loader import get_content_names_zh
from .content_ref_selector import ContentRefSelector


class PlanetSetEditor(QWidget):
    """Edit ``shownPlanets`` as a unique JSON array of Planet identifiers."""

    valueChanged = Signal()

    def __init__(
        self,
        data: dict[str, Any],
        path: str,
        command_stack: CommandStack,
        metadata: Any,
        project: Any | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("planetSetEditor")
        self._data = data
        self._path = path
        self._commands = command_stack
        self._metadata = metadata
        self._project = project
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._build()

    @property
    def value(self) -> list[str]:
        value = self._data.get(self._path, [])
        return [str(item) for item in value] if isinstance(value, list) else []

    def _build(self) -> None:
        self._clear_layout()
        planets = self.value
        for index, planet in enumerate(planets):
            row = QHBoxLayout()
            selector = self._selector()
            selector.setObjectName(f"shownPlanetsSelector{index}")
            selector.set_value(planet)
            selector.valueChanged.connect(
                lambda value, target=index: self._replace(target, value)
            )
            row.addWidget(selector, 1)
            remove = QPushButton("删除")
            remove.setObjectName(f"removeShownPlanet{index}")
            remove.clicked.connect(lambda _=False, target=index: self._remove(target))
            row.addWidget(remove)
            self._layout.addLayout(row)

        add = QPushButton("添加星球")
        add.setObjectName("addShownPlanet")
        add.clicked.connect(self._add)
        self._layout.addWidget(add)

    def _selector(self) -> ContentRefSelector:
        return ContentRefSelector(
            metadata=self._metadata,
            project=self._project,
            categories=("Planets",),
            names_zh=get_content_names_zh(),
        )

    def _add(self) -> None:
        candidates = self._metadata.list_instances("Planets")
        if not candidates:
            return
        self._commit([*self.value, candidates[0]])

    def _replace(self, index: int, planet: str) -> None:
        planets = self.value
        if not planet or not 0 <= index < len(planets):
            return
        planets[index] = planet
        self._commit(planets)

    def _remove(self, index: int) -> None:
        planets = self.value
        if not 0 <= index < len(planets):
            return
        planets.pop(index)
        self._commit(planets)

    def _commit(self, planets: list[str]) -> None:
        unique_planets = list(dict.fromkeys(planets))
        if unique_planets:
            command = SetFieldCommand(
                self._data, self._path, unique_planets, on_change=self.valueChanged.emit
            )
        else:
            command = DeleteFieldCommand(
                self._data, self._path, on_change=self.valueChanged.emit
            )
        self._commands.execute(command)
        self._build()

    def _clear_layout(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget() is not None:
                        child.widget().deleteLater()
