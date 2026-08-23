"""Inline editor for Mindustry's string-or-object Research configuration."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core.commands import CommandStack, DeleteFieldCommand, SetFieldCommand
from ...core.config_loader import get_content_names_zh, get_field_names_zh
from ...core.ref_candidates import UNLOCKABLE_CATEGORIES
from ...core.research_model import (
    OBJECTIVE_CATEGORIES,
    OBJECTIVE_TARGET_FIELDS,
    as_research_object,
    serialize_research,
)
from .content_ref_selector import ContentRefSelector


class ResearchEditor(QWidget):
    """Edit the seven supported Research fields without changing legacy strings."""

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
        self.setObjectName("researchEditor")
        self._data = data
        self._path = path
        self._commands = command_stack
        self._metadata = metadata
        self._project = project
        self._names = get_field_names_zh()
        self._content_names = get_content_names_zh()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._build()

    @property
    def value(self) -> Any:
        return self._data.get(self._path)

    def _build(self) -> None:
        self._clear_layout()
        research = as_research_object(self.value)

        self._parent_selector = self._selector(UNLOCKABLE_CATEGORIES)
        self._parent_selector.setObjectName("researchParentSelector")
        self._parent_selector.set_value(str(research.get("parent", "")))
        self._parent_selector.valueChanged.connect(
            lambda value: self._replace_field("parent", value or None)
        )
        self._layout.addLayout(self._field_row("parent", self._parent_selector))

        self._requirements_box = QWidget()
        self._requirements_box.setObjectName("researchRequirements")
        requirements_layout = QVBoxLayout(self._requirements_box)
        requirements_layout.setContentsMargins(0, 0, 0, 0)
        requirements_layout.setSpacing(4)
        for index, requirement in enumerate(research.get("requirements", [])):
            if isinstance(requirement, dict):
                requirements_layout.addLayout(self._requirement_row(index, requirement))
        add_requirement = QPushButton("添加需求")
        add_requirement.setObjectName("addResearchRequirement")
        add_requirement.clicked.connect(self._add_requirement)
        requirements_layout.addWidget(add_requirement)
        self._layout.addLayout(self._field_row("requirements", self._requirements_box))

        self._objectives_box = QWidget()
        self._objectives_box.setObjectName("researchObjectives")
        objectives_layout = QVBoxLayout(self._objectives_box)
        objectives_layout.setContentsMargins(0, 0, 0, 0)
        objectives_layout.setSpacing(4)
        for index, objective in enumerate(research.get("objectives", [])):
            if isinstance(objective, dict):
                objectives_layout.addLayout(self._objective_row(index, objective))
        add_objective = QPushButton("添加目标")
        add_objective.setObjectName("addResearchObjective")
        add_objective.clicked.connect(self._add_objective)
        objectives_layout.addWidget(add_objective)
        self._layout.addLayout(self._field_row("objectives", self._objectives_box))

        self._more_fields = QWidget()
        more_layout = QVBoxLayout(self._more_fields)
        more_layout.setContentsMargins(0, 0, 0, 0)
        more_layout.setSpacing(4)
        planet = self._selector(("Planets",))
        planet.setObjectName("researchPlanetSelector")
        planet.set_value(str(research.get("planet", "")))
        planet.valueChanged.connect(lambda value: self._replace_field("planet", value or None))
        more_layout.addLayout(self._field_row("planet", planet))
        root = QCheckBox(self._label("root"))
        root.setObjectName("researchRoot")
        root.setChecked(bool(research.get("root", False)))
        root.toggled.connect(lambda value: self._replace_field("root", value or None))
        more_layout.addWidget(root)
        from PySide6.QtWidgets import QLineEdit

        name_input = QLineEdit(str(research.get("name", "")))
        name_input.setObjectName("researchName")
        name_input.editingFinished.connect(
            lambda input_widget=name_input: self._replace_field("name", input_widget.text().strip() or None)
        )
        more_layout.addLayout(self._field_row("name", name_input))
        requires_unlock = QCheckBox(self._label("requiresUnlock"))
        requires_unlock.setObjectName("researchRequiresUnlock")
        requires_unlock.setChecked(bool(research.get("requiresUnlock", False)))
        requires_unlock.toggled.connect(
            lambda value: self._replace_field("requiresUnlock", value or None)
        )
        more_layout.addWidget(requires_unlock)
        self._layout.addWidget(self._more_fields)

        self._more_toggle = QCheckBox("显示更多科技树设置")
        self._more_toggle.setObjectName("researchMoreToggle")
        has_low_frequency_value = any(
            field in research for field in ("planet", "root", "name", "requiresUnlock")
        )
        self._more_toggle.setChecked(has_low_frequency_value)
        self._more_fields.setVisible(has_low_frequency_value)
        self._more_toggle.toggled.connect(self._more_fields.setVisible)
        self._layout.addWidget(self._more_toggle)

    def _field_row(self, field: str, widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel(self._label(field))
        label.setFixedWidth(86)
        row.addWidget(label)
        row.addWidget(widget, 1)
        return row

    def _selector(self, categories: tuple[str, ...]) -> ContentRefSelector:
        return ContentRefSelector(
            metadata=self._metadata,
            project=self._project,
            categories=categories,
            names_zh=self._content_names,
        )

    def _requirement_row(self, index: int, requirement: dict[str, Any]) -> QHBoxLayout:
        row = QHBoxLayout()
        selector = self._selector(("Items",))
        selector.setObjectName(f"researchRequirementItem{index}")
        selector.set_value(str(requirement.get("item", "")))
        selector.valueChanged.connect(
            lambda value, target=index: self._replace_requirement(target, "item", value)
        )
        row.addWidget(selector, 1)
        amount = QSpinBox()
        amount.setObjectName(f"researchRequirementAmount{index}")
        amount.setRange(1, 999999)
        amount.setValue(int(requirement.get("amount", 1)))
        amount.valueChanged.connect(
            lambda value, target=index: self._replace_requirement(target, "amount", value)
        )
        row.addWidget(amount)
        remove = QPushButton("删除")
        remove.clicked.connect(lambda _=False, target=index: self._remove_requirement(target))
        row.addWidget(remove)
        return row

    def _objective_row(self, index: int, objective: dict[str, Any]) -> QHBoxLayout:
        row = QHBoxLayout()
        objective_type = str(objective.get("type", "Research"))
        type_selector = QComboBox()
        type_selector.setObjectName(f"researchObjectiveType{index}")
        for type_name in OBJECTIVE_CATEGORIES:
            type_selector.addItem(self._label(f"objective.{type_name}"), type_name)
        type_selector.setCurrentIndex(max(0, type_selector.findData(objective_type)))
        type_selector.currentIndexChanged.connect(
            lambda _index, target=index, widget=type_selector: self._replace_objective_type(target, str(widget.currentData()))
        )
        row.addWidget(type_selector)
        target_selector = self._selector(OBJECTIVE_CATEGORIES.get(objective_type, UNLOCKABLE_CATEGORIES))
        target_selector.setObjectName(f"researchObjectiveContent{index}")
        target_field = OBJECTIVE_TARGET_FIELDS.get(objective_type, "content")
        target_selector.set_value(str(objective.get(target_field, "")))
        target_selector.valueChanged.connect(
            lambda value, target=index: self._replace_objective_content(target, value)
        )
        row.addWidget(target_selector, 1)
        remove = QPushButton("删除")
        remove.clicked.connect(lambda _=False, target=index: self._remove_objective(target))
        row.addWidget(remove)
        return row

    def _replace_field(self, field: str, value: Any) -> None:
        research = as_research_object(self.value)
        if value is None or value == "":
            research.pop(field, None)
        else:
            research[field] = value
        self._commit(research)

    def _add_requirement(self) -> None:
        research = as_research_object(self.value)
        requirements = deepcopy(research.get("requirements", []))
        requirements.append({"item": "copper", "amount": 1})
        research["requirements"] = requirements
        self._commit(research)

    def _replace_requirement(self, index: int, field: str, value: Any) -> None:
        research = as_research_object(self.value)
        requirements = deepcopy(research.get("requirements", []))
        if not 0 <= index < len(requirements) or not isinstance(requirements[index], dict):
            return
        requirements[index][field] = value
        research["requirements"] = requirements
        self._commit(research)

    def _remove_requirement(self, index: int) -> None:
        research = as_research_object(self.value)
        requirements = deepcopy(research.get("requirements", []))
        if not 0 <= index < len(requirements):
            return
        requirements.pop(index)
        if requirements:
            research["requirements"] = requirements
        else:
            research.pop("requirements", None)
        self._commit(research)

    def _add_objective(self) -> None:
        research = as_research_object(self.value)
        objectives = deepcopy(research.get("objectives", []))
        objectives.append({"type": "Research", "content": "copper-wall"})
        research["objectives"] = objectives
        self._commit(research)

    def _replace_objective_type(self, index: int, objective_type: str) -> None:
        research = as_research_object(self.value)
        objectives = deepcopy(research.get("objectives", []))
        if not 0 <= index < len(objectives) or not isinstance(objectives[index], dict):
            return
        objectives[index]["type"] = objective_type
        for field in set(OBJECTIVE_TARGET_FIELDS.values()):
            objectives[index].pop(field, None)
        research["objectives"] = objectives
        self._commit(research)

    def _replace_objective_content(self, index: int, content: str) -> None:
        research = as_research_object(self.value)
        objectives = deepcopy(research.get("objectives", []))
        if not 0 <= index < len(objectives) or not isinstance(objectives[index], dict):
            return
        objective_type = str(objectives[index].get("type", "Research"))
        target_field = OBJECTIVE_TARGET_FIELDS.get(objective_type, "content")
        objectives[index][target_field] = content
        research["objectives"] = objectives
        self._commit(research)

    def _remove_objective(self, index: int) -> None:
        research = as_research_object(self.value)
        objectives = deepcopy(research.get("objectives", []))
        if not 0 <= index < len(objectives):
            return
        objectives.pop(index)
        if objectives:
            research["objectives"] = objectives
        else:
            research.pop("objectives", None)
        self._commit(research)

    def _commit(self, research: dict[str, Any]) -> None:
        serialized = serialize_research(self.value, research)
        if serialized is None:
            command = DeleteFieldCommand(self._data, self._path, on_change=self.valueChanged.emit)
        else:
            command = SetFieldCommand(self._data, self._path, serialized, on_change=self.valueChanged.emit)
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

    def _label(self, field: str) -> str:
        return self._names.get(field, field)
