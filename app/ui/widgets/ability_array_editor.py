"""Ability array editor: card list of polymorphic ability objects.

Renders the unit `abilities` array as a list of collapsible cards, each
embedding a PolymorphicTypeEditor. No reference mode (abilities are always
inline). Add/remove go through the CommandStack.

Interface:
    .value        — get/set the abilities list
    .valueChanged — Signal, emitted on any mutation
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.commands import (
    ArrayInsertCommand,
    ArrayRemoveCommand,
    CommandStack,
    SetFieldCommand,
)
from .polymorphic_editor import PolymorphicTypeEditor

# 全部能力类型（提取器 v0.2.5 输出的 15 个子类）
ABILITY_TYPES = [
    "ShieldRegenFieldAbility",
    "RegenAbility",
    "MoveLightningAbility",
    "StatusFieldAbility",
    "ForceFieldAbility",
    "EnergyFieldAbility",
    "RepairFieldAbility",
    "ArmorPlateAbility",
    "MoveEffectAbility",
    "SpawnDeathAbility",
    "LiquidExplodeAbility",
    "LiquidRegenAbility",
    "SuppressionFieldAbility",
    "UnitSpawnAbility",
    "ShieldArcAbility",
]

# 新建能力时的默认类型与默认值（6 种常用，字段名以提取器元数据为准）
_ABILITY_DEFAULTS: dict[str, dict] = {
    "ShieldRegenFieldAbility": {"type": "ShieldRegenFieldAbility", "amount": 1.0, "max": 100.0, "reload": 100.0, "range": 60.0},
    "RegenAbility": {"type": "RegenAbility", "amount": 1.0},
    "MoveLightningAbility": {"type": "MoveLightningAbility", "damage": 10.0, "chance": 0.15, "length": 12},
    "StatusFieldAbility": {"type": "StatusFieldAbility", "duration": 60.0, "range": 60.0, "reload": 60.0},
    "ForceFieldAbility": {"type": "ForceFieldAbility", "max": 100.0, "regen": 0.5, "cooldown": 60.0, "radius": 60.0},
    "EnergyFieldAbility": {"type": "EnergyFieldAbility", "damage": 10.0, "reload": 30.0, "range": 60.0},
}


class AbilityArrayEditor(QWidget):
    """Card list editor for the `abilities` array field."""

    valueChanged = Signal()

    def __init__(
        self,
        data: dict,
        path: str,
        command_stack: CommandStack,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data = data
        self._path = path
        self._commands = command_stack
        self._cards: list[QWidget] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)

        self._rebuild_cards()

        add_btn = QPushButton("+ 添加能力")
        add_btn.clicked.connect(self._add_ability)
        self._layout.addWidget(add_btn)

    @property
    def value(self) -> list[dict]:
        val = self._data.get(self._path, [])
        return val if isinstance(val, list) else []

    @value.setter
    def value(self, new_value: list[dict]) -> None:
        self._data[self._path] = new_value
        self._rebuild_cards()
        self.valueChanged.emit()

    def _rebuild_cards(self) -> None:
        for card in self._cards:
            self._layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        for i, _ability in enumerate(self.value):
            card = self._make_card(i)
            # 插入到添加按钮之前
            self._layout.insertWidget(self._layout.count() - 1, card)
            self._cards.append(card)

    def _make_card(self, index: int) -> QWidget:
        """能力卡片：QGroupBox 容器 + 头部（能力名 + 删除按钮）+ 内嵌多态编辑器。

        仿武器卡片结构（v0.2.5 修复）：删除按钮在能力框内右上角，
        字段由 PolymorphicTypeEditor 渲染（马卡龙 + 可撤销）。
        """
        card = QGroupBox()
        v = QVBoxLayout(card)
        v.setContentsMargins(8, 4, 8, 8)
        v.setSpacing(4)

        # 头部：能力名 + 右对齐删除按钮（在框内）
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        title = QLabel(f"<b>能力 {index + 1}</b>")
        head.addWidget(title)
        head.addStretch(1)
        del_btn = QPushButton("×")
        del_btn.setObjectName("weaponRemoveBtn")
        del_btn.setFixedSize(24, 24)
        del_btn.setToolTip("删除该能力")
        del_btn.clicked.connect(lambda _, i=index: self._remove_ability(i))
        head.addWidget(del_btn)
        v.addLayout(head)

        # 内嵌多态编辑器，path 指向数组元素（title 置空，由卡片头部承载标题）
        editor = PolymorphicTypeEditor(
            data=self._data,
            path=f"{self._path}.{index}",
            type_choices=ABILITY_TYPES,
            command_stack=self._commands,
            title="",
            type_label="能力类型",
        )
        editor.valueChanged.connect(self.valueChanged.emit)
        v.addWidget(editor)

        return card

    def _add_ability(self) -> None:
        default_type = "ShieldRegenFieldAbility"
        new_ability = dict(_ABILITY_DEFAULTS.get(default_type, {"type": default_type}))
        # 无 abilities 键时先经命令栈创建空数组（v0.2.5：不再由 EditorPanel 预写）
        if self._path not in self._data or not isinstance(self._data.get(self._path), list):
            init = SetFieldCommand(
                self._data, self._path, [],
                on_change=self._rebuild_and_notify,
            )
            self._commands.execute(init)
        items = self.value
        cmd = ArrayInsertCommand(
            self._data, self._path, len(items), new_ability,
            on_change=self._rebuild_and_notify,
        )
        self._commands.execute(cmd)

    def _remove_ability(self, index: int) -> None:
        cmd = ArrayRemoveCommand(
            self._data, self._path, index,
            on_change=self._rebuild_and_notify,
        )
        self._commands.execute(cmd)

    def _rebuild_and_notify(self) -> None:
        self._rebuild_cards()
        self.valueChanged.emit()
