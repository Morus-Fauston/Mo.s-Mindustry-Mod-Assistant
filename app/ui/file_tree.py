"""File tree panel: displays mod project structure with virtual grouping."""

from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.project import Project
from ..core.content_store import ContentRef


class FileTreePanel(QWidget):
    """Left sidebar: mod project file tree with two-level virtual grouping for blocks."""

    content_opened = Signal(str)  # emits content name

    def __init__(self) -> None:
        super().__init__()
        self._project: Project | None = None
        self._block_categories = self._load_block_categories()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 面板区域标题（对齐设计稿 .panel-h）
        header = QLabel("文件")
        header.setObjectName("panelHeader")
        layout.addWidget(header)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(18)  # 标准缩进 18px/级
        self._tree.itemDoubleClicked.connect(self._on_item_clicked)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._tree)

    # 数据角色：UserRole(256)=名称, +1=分类, +2=文件路径
    ROLE_NAME = Qt.ItemDataRole.UserRole
    ROLE_CATEGORY = Qt.ItemDataRole.UserRole + 1
    ROLE_PATH = Qt.ItemDataRole.UserRole + 2

    def set_project(self, project: Project) -> None:
        self._project = project
        self.refresh()

    def refresh(self) -> None:
        self._tree.clear()
        if self._project is None:
            return

        # Root: mod name
        root = QTreeWidgetItem(self._tree, [self._project.mod_info.display_name or self._project.mod_info.name])
        root.setExpanded(True)

        # content/
        content_item = QTreeWidgetItem(root, ["content"])
        content_item.setExpanded(True)

        refs = self._project.contents.list()

        # Group by category
        units = [r for r in refs if r.category == "units"]
        blocks = [r for r in refs if r.category == "blocks"]
        weapons = [r for r in refs if r.category == "weapons"]

        # Units
        if units:
            units_item = QTreeWidgetItem(content_item, ["units"])
            units_item.setExpanded(True)
            for ref in units:
                self._add_content_child(units_item, ref)

        # Blocks (with virtual grouping)
        if blocks:
            blocks_item = QTreeWidgetItem(content_item, ["blocks"])
            blocks_item.setExpanded(True)
            self._add_blocks_grouped(blocks_item, blocks)

        # Weapons
        if weapons:
            weapons_item = QTreeWidgetItem(content_item, ["weapons"])
            weapons_item.setExpanded(True)
            for ref in weapons:
                self._add_content_child(weapons_item, ref)

        # sprites/
        sprites_item = QTreeWidgetItem(root, ["sprites"])
        self._add_sprites(sprites_item)

    def _add_content_child(self, parent: QTreeWidgetItem, ref: ContentRef) -> None:
        """添加一个内容文件节点，带元数据（纯文本，无图标）。"""
        child = QTreeWidgetItem(parent, [ref.name])
        child.setData(0, self.ROLE_NAME, ref.name)
        child.setData(0, self.ROLE_CATEGORY, ref.category)
        child.setData(0, self.ROLE_PATH, str(ref.path))

    def _add_blocks_grouped(self, parent: QTreeWidgetItem, blocks: list[ContentRef]) -> None:
        """Add blocks with two-level virtual grouping based on block_categories.json."""
        # Build type -> (category_name, sub_name) mapping
        type_to_group: dict[str, tuple[str, str]] = {}
        for cat in self._block_categories.get("categories", []):
            for sub in cat.get("subCategories", []):
                for t in sub.get("types", []):
                    type_to_group[t] = (cat["name"], sub["name"])

        # Group blocks
        groups: dict[str, dict[str, list[ContentRef]]] = {}
        ungrouped: list[ContentRef] = []

        for ref in blocks:
            if ref.content_type in type_to_group:
                cat_name, sub_name = type_to_group[ref.content_type]
                groups.setdefault(cat_name, {}).setdefault(sub_name, []).append(ref)
            else:
                ungrouped.append(ref)

        # Add grouped
        for cat_name, subs in groups.items():
            cat_item = QTreeWidgetItem(parent, [cat_name])
            cat_item.setExpanded(True)
            for sub_name, refs in subs.items():
                sub_item = QTreeWidgetItem(cat_item, [sub_name])
                sub_item.setExpanded(True)
                for ref in refs:
                    self._add_content_child(sub_item, ref)

        # Add ungrouped
        if ungrouped:
            other_item = QTreeWidgetItem(parent, ["其他"])
            other_item.setExpanded(True)
            for ref in ungrouped:
                self._add_content_child(other_item, ref)

    def _add_sprites(self, parent: QTreeWidgetItem) -> None:
        if self._project is None:
            return
        sprites_dir = self._project.sprites_dir
        if not sprites_dir.is_dir():
            return
        for sub in sorted(sprites_dir.iterdir()):
            if sub.is_dir():
                sub_item = QTreeWidgetItem(parent, [sub.name])
                for f in sorted(sub.glob("*.png")):
                    QTreeWidgetItem(sub_item, [f.name])

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        name = item.data(0, self.ROLE_NAME)
        if name:
            self.content_opened.emit(name)

    def _show_context_menu(self, pos) -> None:
        """Right-click context menu on tree items."""
        item = self._tree.itemAt(pos)
        if item is None:
            return

        name = item.data(0, self.ROLE_NAME)
        if not name:
            return  # Not a content item (e.g. category header)

        path = item.data(0, self.ROLE_PATH)

        menu = QMenu(self)
        open_action = menu.addAction("打开")
        rename_action = menu.addAction("重命名")
        menu.addSeparator()
        reveal_action = menu.addAction("在文件管理器中打开")
        menu.addSeparator()
        delete_action = menu.addAction("删除")

        chosen = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == open_action:
            self.content_opened.emit(name)
        elif chosen == rename_action:
            self._rename_content(item, name)
        elif chosen == reveal_action and path:
            self._reveal_in_file_manager(path)
        elif chosen == delete_action:
            self._delete_content(name)

    def _rename_content(self, item: QTreeWidgetItem, old_name: str) -> None:
        """重命名内容文件（文件名 + JSON 内 name 字段）。"""
        if self._project is None:
            return
        category = item.data(0, self.ROLE_CATEGORY)
        new_name, ok = QInputDialog.getText(
            self, "重命名", "新名称 (英文, 小写+连字符):", text=old_name
        )
        if not ok or not new_name or new_name == old_name:
            return
        try:
            content = self._project.contents.get(old_name)
            content.data["name"] = new_name
            self._project.contents.save(new_name, content.data, category)
            self._project.contents.delete(old_name)
            self.refresh()
        except FileNotFoundError:
            QMessageBox.warning(self, "重命名失败", f"找不到文件: {old_name}")

    def _reveal_in_file_manager(self, path: str) -> None:
        """在系统文件管理器中定位文件。"""
        p = Path(path)
        if not p.exists():
            return
        import subprocess
        if os.name == "nt":
            # explorer /select 精确选中文件
            subprocess.Popen(["explorer", f"/select,{p}"])
        else:
            subprocess.Popen(["xdg-open", str(p.parent)])

    def _delete_content(self, name: str) -> None:
        """Delete a content file after confirmation."""
        if self._project is None:
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除 '{name}' 吗？\n\n此操作不可撤销，文件将从磁盘删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._project.contents.delete(name)
            self.refresh()
        except FileNotFoundError:
            QMessageBox.warning(self, "删除失败", f"找不到文件: {name}")

    @staticmethod
    def _load_block_categories() -> dict:
        config_path = Path(__file__).parent.parent / "config" / "block_categories.json"
        if config_path.exists():
            return json.loads(config_path.read_text(encoding="utf-8"))
        return {"categories": []}
