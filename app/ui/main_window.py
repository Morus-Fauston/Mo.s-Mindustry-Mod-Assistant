"""Main window: menu bar + toolbar + dockable sidebars + tabbed editor."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QToolBar,
)

from ..core.metadata import Metadata
from ..core.project import Project
from ..core.commands import CommandStack
from ..core.template import TemplateEngine
from ..core.validator import Validator
from .file_tree import FileTreePanel
from .editor_panel import EditorPanel
from .preview_panel import PreviewPanel


class MainWindow(QMainWindow):
    def __init__(self, metadata_dir: Path) -> None:
        super().__init__()
        self.setWindowTitle("Mo's Mindustry Mod Assistant")
        self.resize(1400, 900)

        # Core services
        self._metadata = Metadata(metadata_dir)
        self._command_stack = CommandStack()
        self._template_engine = TemplateEngine(self._metadata)
        self._validator = Validator(self._metadata)
        self._project: Project | None = None

        # Auto-save timer
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.timeout.connect(self._auto_save)
        self._auto_save_timer.start(180_000)  # 3 minutes

        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()

        self.statusBar().showMessage(
            f"就绪 | 游戏版本: v{self._metadata.game_version}"
        )

    # ── UI setup ────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        # Central: tab widget for open content files
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self._tabs)

        # Left dock: file tree
        self._file_tree = FileTreePanel()
        self._file_tree.content_opened.connect(self._open_content)
        left_dock = QDockWidget("文件", self)
        left_dock.setWidget(self._file_tree)
        left_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, left_dock)

        # Right dock: preview + sprite layers
        self._preview = PreviewPanel()
        right_dock = QDockWidget("预览", self)
        right_dock.setWidget(self._preview)
        right_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, right_dock)

    def _setup_menu(self) -> None:
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("文件(&F)")
        self._add_action(file_menu, "新建工程...", self._new_project, "Ctrl+Shift+N")
        self._add_action(file_menu, "打开工程...", self._open_project, "Ctrl+O")
        file_menu.addSeparator()
        self._add_action(file_menu, "保存", self._save, "Ctrl+S")
        file_menu.addSeparator()
        self._add_action(file_menu, "退出", self.close, "Ctrl+Q")

        # Edit menu
        edit_menu = menubar.addMenu("编辑(&E)")
        self._undo_action = self._add_action(edit_menu, "撤销", self._undo, "Ctrl+Z")
        self._redo_action = self._add_action(edit_menu, "重做", self._redo, "Ctrl+Y")

        # Tools menu
        tools_menu = menubar.addMenu("工具(&T)")
        self._add_action(tools_menu, "导入参考...", self._import_reference)
        tools_menu.addSeparator()
        self._add_action(tools_menu, "设置...", self._open_settings)

        # Help menu
        help_menu = menubar.addMenu("帮助(&H)")
        self._add_action(help_menu, "关于", self._about)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._add_toolbar_button(toolbar, "+ 单位", self._new_unit)
        self._add_toolbar_button(toolbar, "+ 方块", self._new_block)
        self._add_toolbar_button(toolbar, "+ 武器", self._new_weapon)
        toolbar.addSeparator()
        self._add_toolbar_button(toolbar, "保存", self._save)

    # ── actions ─────────────────────────────────────────────────────────

    def _new_project(self) -> None:
        from .dialogs.new_project import NewProjectDialog
        dlg = NewProjectDialog(self)
        if dlg.exec():
            path, mod_id, name = dlg.get_result()
            self._project = Project.create(path, mod_id, name)
            self._file_tree.set_project(self._project)
            self.statusBar().showMessage(f"已创建工程: {mod_id}")

    def _open_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择 mod 工程目录")
        if not path:
            return
        try:
            self._project = Project.open(path)
            self._file_tree.set_project(self._project)
            self.statusBar().showMessage(f"已打开: {self._project.mod_info.display_name}")
        except FileNotFoundError as e:
            QMessageBox.warning(self, "打开失败", str(e))

    def _save(self) -> None:
        if self._project is None:
            return
        # Save all open tabs
        for i in range(self._tabs.count()):
            panel = self._tabs.widget(i)
            if isinstance(panel, EditorPanel):
                panel.save()
        self._project.is_dirty = False
        self.statusBar().showMessage("已保存")

    def _auto_save(self) -> None:
        if self._project and self._project.is_dirty:
            self._save()
            self.statusBar().showMessage("自动保存完成")

    def _undo(self) -> None:
        self._command_stack.undo()

    def _redo(self) -> None:
        self._command_stack.redo()

    def _new_unit(self) -> None:
        self._create_content("UnitType", "units")

    def _new_block(self) -> None:
        from .dialogs.new_content import NewBlockDialog
        if self._project is None:
            QMessageBox.information(self, "提示", "请先打开或新建一个工程")
            return
        dlg = NewBlockDialog(self)
        if dlg.exec():
            block_type, name = dlg.get_result()
            self._do_create_content(block_type, name, "blocks")

    def _new_weapon(self) -> None:
        self._create_content("Weapon", "weapons")

    def _create_content(self, kind: str, category: str) -> None:
        if self._project is None:
            QMessageBox.information(self, "提示", "请先打开或新建一个工程")
            return
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, f"新建 {kind}", "名称 (英文, 小写+连字符):")
        if ok and name:
            self._do_create_content(kind, name, category)

    def _do_create_content(self, kind: str, name: str, category: str) -> None:
        if self._project is None:
            return
        data = self._template_engine.create(kind, name)
        self._project.contents.save(name, data, category)
        self._file_tree.refresh()
        self._open_content(name)
        self.statusBar().showMessage(f"已创建: {name} ({kind})")

    def _open_content(self, name: str) -> None:
        # Check if already open
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == name:
                self._tabs.setCurrentIndex(i)
                return

        if self._project is None:
            return

        try:
            content = self._project.contents.get(name)
        except FileNotFoundError:
            return

        panel = EditorPanel(
            content=content,
            metadata=self._metadata,
            command_stack=self._command_stack,
            validator=self._validator,
            project=self._project,
        )
        idx = self._tabs.addTab(panel, name)
        self._tabs.setCurrentIndex(idx)

    def _close_tab(self, index: int) -> None:
        panel = self._tabs.widget(index)
        if isinstance(panel, EditorPanel) and panel.is_dirty:
            reply = QMessageBox.question(
                self, "未保存",
                f"'{self._tabs.tabText(index)}' 有未保存的修改，是否保存？",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                panel.save()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        self._tabs.removeTab(index)

    def _on_tab_changed(self, index: int) -> None:
        if index < 0:
            return
        panel = self._tabs.widget(index)
        if isinstance(panel, EditorPanel):
            self._preview.show_content(panel.content, self._project)

    def _import_reference(self) -> None:
        QMessageBox.information(self, "参考", "参考功能将在后续版本实现")

    def _open_settings(self) -> None:
        QMessageBox.information(self, "设置", "设置面板将在后续版本实现")

    def _about(self) -> None:
        QMessageBox.about(
            self, "关于",
            "Mo's Mindustry Mod Assistant v0.1.0\n\n"
            f"目标游戏版本: v{self._metadata.game_version}\n"
            "一个 GUI 化的 Mindustry 模组编辑器。"
        )

    # ── helpers ─────────────────────────────────────────────────────────

    def _add_action(self, menu, text: str, slot, shortcut: str | None = None) -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _add_toolbar_button(self, toolbar: QToolBar, text: str, slot) -> None:
        action = QAction(text, self)
        action.triggered.connect(slot)
        toolbar.addAction(action)

    def closeEvent(self, event) -> None:
        # Check for unsaved changes
        for i in range(self._tabs.count()):
            panel = self._tabs.widget(i)
            if isinstance(panel, EditorPanel) and panel.is_dirty:
                reply = QMessageBox.question(
                    self, "退出",
                    "有未保存的修改，确定退出？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.No:
                    event.ignore()
                    return
                break
        event.accept()
