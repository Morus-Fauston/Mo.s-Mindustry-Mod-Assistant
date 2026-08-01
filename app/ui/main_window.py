"""Main window: menu bar + toolbar + dockable sidebars + tabbed editor."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabBar,
    QTabWidget,
    QToolBar,
    QWidget,
)

from ..core.project import Project
from ..core.session import ProjectSession
from .file_tree import FileTreePanel
from .editor_panel import EditorPanel
from .preview_panel import PreviewPanel
from .welcome_page import WelcomePage
from .widgets.toast import Toast
from .widgets.reference_panel import ReferencePanel, _ReferencePicker

# 应用版本号（与 pyproject.toml 同步）
APP_VERSION = "0.2.4.batch2"


class _StatusBar(QStatusBar):
    """自管消息区的状态栏。

    Qt 内置 showMessage 依赖懒创建的 qt_statusbar_temp_label，在当前
    PySide6 + 自定义 QSS 组合下该 label 不进入对象树，导致铜橙条无文字。
    故 override showMessage，把文本写入我方 addWidget 的真实 QLabel，
    颜色走 QSS #statusMessage（@SB_INK@），彻底脱离不可靠的内置路径。
    Python 方法解析会让现有 self.statusBar().showMessage(...) 调用自动走此类。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._msg = QLabel()
        self._msg.setObjectName("statusMessage")
        self.addWidget(self._msg, 1)  # 临时区，stretch 占满左侧

    def showMessage(self, message: str, timeout: int = 0) -> None:  # noqa: ARG002
        self._msg.setText(message)

    def clearMessage(self) -> None:
        self._msg.setText("")


class MainWindow(QMainWindow):
    def __init__(self, metadata_dir: Path) -> None:
        super().__init__()
        self.setWindowTitle("Mo's Mindustry Mod Assistant")
        self.resize(1400, 900)

        # Core services are assembled inside the ProjectSession deep module.
        self._session = ProjectSession(metadata_dir)
        self._metadata = self._session.metadata
        self._command_stack = self._session.command_stack
        self._validator = self._session.validator

        # Auto-save timer
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.timeout.connect(self._auto_save)
        self._auto_save_timer.start(180_000)  # 3 minutes

        # Wire undo/redo change notification
        self._command_stack.set_on_change(self._on_command_stack_changed)

        # editor_state persistence is handled by config_loader

        # 自管消息区的状态栏（须在首次 self.statusBar() 之前安装）
        self.setStatusBar(_StatusBar())

        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._restore_last_project()

        # Toast 提示（右下角浮层）
        self._toast = Toast(self)

        # 状态栏错误指示器（可点击跳转到第一个错误）
        self._first_error_panel: EditorPanel | None = None
        from PySide6.QtWidgets import QPushButton
        self._error_chip = QPushButton(self.statusBar())
        self._error_chip.setObjectName("statusErrorChip")
        self._error_chip.setFlat(True)
        self._error_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self._error_chip.hide()
        self._error_chip.clicked.connect(self._jump_to_first_error)
        self.statusBar().addPermanentWidget(self._error_chip)

        self.statusBar().showMessage(
            f"就绪 | 游戏版本: v{self._metadata.game_version}"
        )

    @property
    def _project(self) -> Project | None:
        """Current project, owned by the session (single source of truth)."""
        return self._session.project

    # ── UI setup ────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        # 中央：QStackedWidget 在「欢迎页」与「标签页」之间切换
        self._center_stack = QStackedWidget()

        # 欢迎页（无工程时显示）
        self._welcome = WelcomePage()
        self._welcome.new_project_requested.connect(self._new_project)
        self._welcome.open_project_requested.connect(self._open_project)
        self._welcome.restore_requested.connect(self._restore_project_path)
        self._center_stack.addWidget(self._welcome)  # index 0

        # 标签页（打开内容文件）
        self._tabs = QTabWidget()
        # 关闭按钮改用文本 × 按钮（原生 close-button 无法放文本字符）
        self._tabs.setTabsClosable(False)
        self._tabs.setMovable(False)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        # 标签页右键菜单
        self._tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tabs.tabBar().customContextMenuRequested.connect(self._show_tab_context_menu)
        self._center_stack.addWidget(self._tabs)  # index 1

        # 左侧：文件树
        self._file_tree = FileTreePanel()
        self._file_tree.content_opened.connect(self._open_content)
        self._file_tree.content_renamed.connect(self._on_content_renamed)

        # 右侧：预览 + 图层
        self._preview = PreviewPanel()
        # v0.2.4.batch4：预览 SpinBox 改坐标 → 当前活动编辑器标 dirty + 刷新表单
        self._preview.content_modified.connect(self._on_preview_content_modified)

        # QSplitter 三栏：左 200 / 中自适应 / 右 280
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._file_tree)
        self._splitter.addWidget(self._center_stack)
        self._splitter.addWidget(self._preview)
        self._splitter.setSizes([200, 920, 280])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        self._splitter.setChildrenCollapsible(False)

        self.setCentralWidget(self._splitter)

        # 默认显示欢迎页
        self._center_stack.setCurrentIndex(0)

    def _setup_menu(self) -> None:
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("文件(&F)")
        self._add_action(file_menu, "新建工程...", self._new_project, "Ctrl+Shift+N")
        self._add_action(file_menu, "打开工程...", self._open_project, "Ctrl+O")
        file_menu.addSeparator()
        self._add_action(file_menu, "保存", self._save, "Ctrl+S")
        file_menu.addSeparator()
        self._close_project_action = self._add_action(file_menu, "关闭工程", self._close_project)
        self._close_project_action.setEnabled(False)
        file_menu.addSeparator()
        self._add_action(file_menu, "退出", self.close, "Ctrl+Q")

        # Edit menu
        edit_menu = menubar.addMenu("编辑(&E)")
        self._undo_action = self._add_action(edit_menu, "撤销", self._undo, "Ctrl+Z")
        self._redo_action = self._add_action(edit_menu, "重做", self._redo, "Ctrl+Y")

        # Settings menu (independent top-level)
        settings_menu = menubar.addMenu("设置(&S)")
        self._add_action(settings_menu, "设置...", self._open_settings)

        # Tools menu
        tools_menu = menubar.addMenu("工具(&T)")
        self._add_action(tools_menu, "导入参考...", self._import_reference)

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
        toolbar.addSeparator()
        self._undo_tb = self._add_toolbar_button(toolbar, "撤销", self._undo)
        self._redo_tb = self._add_toolbar_button(toolbar, "重做", self._redo)
        self._undo_tb.setEnabled(False)
        self._redo_tb.setEnabled(False)

    # ── actions ─────────────────────────────────────────────────────────

    def _new_project(self) -> None:
        from .dialogs.new_project import NewProjectDialog
        dlg = NewProjectDialog(self)
        if dlg.exec():
            path, mod_id, name = dlg.get_result()
            self._session.create_project(path, mod_id, name)
            self._file_tree.set_project(self._project)
            self._enter_project_view()
            self.statusBar().showMessage(f"已创建工程: {mod_id}")

    def _open_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择 mod 工程目录")
        if not path:
            return
        self._load_project_path(path)

    def _restore_project_path(self, path: str) -> None:
        """从欢迎页「上次打开」恢复工程。"""
        self._load_project_path(path)

    def _load_project_path(self, path: str) -> None:
        try:
            self._session.open_project(path)
            self._file_tree.set_project(self._project)
            self._enter_project_view()
            self.statusBar().showMessage(f"已打开: {self._project.mod_info.display_name}")
        except (FileNotFoundError, ValueError) as e:
            QMessageBox.warning(self, "打开失败", str(e))

    def _enter_project_view(self) -> None:
        """切换到标签页视图并启用关闭工程。"""
        self._center_stack.setCurrentIndex(1)
        self._close_project_action.setEnabled(True)
        if self._project is not None:
            self._welcome.set_last_project(str(self._project.root))

    def _close_project(self) -> None:
        """关闭当前工程，清空标签页，回到欢迎页。"""
        if self._project is None:
            return
        # 关闭所有标签（不逐个询问，统一提示）
        if self._has_unsaved():
            reply = QMessageBox.question(
                self, "关闭工程",
                "有未保存的修改，关闭前是否保存？",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._save()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        # 清空标签页
        self._tabs.clear()
        self._session.close_project()
        self._file_tree.set_project(None)
        self._center_stack.setCurrentIndex(0)
        self._close_project_action.setEnabled(False)
        self.statusBar().showMessage("未打开工程")

    def _has_unsaved(self) -> bool:
        """是否有未保存的标签页。"""
        for i in range(self._tabs.count()):
            panel = self._tabs.widget(i)
            if isinstance(panel, EditorPanel) and panel.is_dirty:
                return True
        return False

    def _save(self) -> None:
        if self._project is None:
            return
        # Collect open contents; remember panel by name for jump-to-error.
        panels: dict[str, EditorPanel] = {}
        items = []
        for i in range(self._tabs.count()):
            panel = self._tabs.widget(i)
            if isinstance(panel, EditorPanel):
                items.append(panel.content)
                panels[panel.content.name] = panel
        # Deep save+validate lives in the session.
        report = self._session.save_contents(items)
        for panel in panels.values():
            panel.mark_saved()
        if report.error_count > 0:
            self.statusBar().showMessage(f"已保存 ({report.error_count} 个验证错误)")
            self._toast.show_message(f"已保存 · {report.error_count} 个验证错误")
            # 记录第一个错误面板，供状态栏点击跳转
            self._first_error_panel = panels.get(report.first_error_content or "")
            self._error_chip.setText(f"⚠ {report.error_count} 个错误 · 点击跳转")
            self._error_chip.show()
        else:
            self.statusBar().showMessage("已保存")
            self._toast.show_message(f"已保存 · {self._project.mod_info.display_name}")
            self._first_error_panel = None
            self._error_chip.hide()

    def _auto_save(self) -> None:
        if self._project and self._project.is_dirty:
            self._save()
            self._toast.show_message("已自动保存")

    def _jump_to_first_error(self) -> None:
        """切换到含错误的标签页并滚动高亮第一个错误字段。"""
        panel = self._first_error_panel
        if panel is None:
            return
        idx = self._tabs.indexOf(panel)
        if idx >= 0:
            self._tabs.setCurrentIndex(idx)
        if panel.jump_to_first_error():
            self._toast.show_message("已定位到错误字段")
        else:
            self._toast.show_message("未找到可定位的错误")

    # ── state persistence ───────────────────────────────────────────────

    def _restore_last_project(self) -> None:
        """Auto-open the last project on startup."""
        last_path = self._session.last_project_path()
        if last_path and Path(last_path).exists():
            try:
                self._session.open_project(last_path)
                self._file_tree.set_project(self._project)
                self._welcome.set_last_project(last_path)
                self._enter_project_view()
                self.statusBar().showMessage(
                    f"已恢复上次工程: {self._project.mod_info.display_name}"
                )
            except (OSError, FileNotFoundError, ValueError):
                pass

    def _undo(self) -> None:
        self._command_stack.undo()
        self._refresh_all_editors()

    def _redo(self) -> None:
        self._command_stack.redo()
        self._refresh_all_editors()

    def _on_command_stack_changed(self) -> None:
        """Update undo/redo button states + tooltips after command stack changes."""
        can_undo = self._command_stack.can_undo
        can_redo = self._command_stack.can_redo
        undo_desc = self._command_stack.undo_description
        redo_desc = self._command_stack.redo_description

        if hasattr(self, '_undo_tb'):
            self._undo_tb.setEnabled(can_undo)
            self._undo_tb.setToolTip(f"撤销: {undo_desc}" if undo_desc else "撤销")
        if hasattr(self, '_redo_tb'):
            self._redo_tb.setEnabled(can_redo)
            self._redo_tb.setToolTip(f"重做: {redo_desc}" if redo_desc else "重做")
        if hasattr(self, '_undo_action'):
            self._undo_action.setEnabled(can_undo)
            self._undo_action.setToolTip(f"撤销: {undo_desc}" if undo_desc else "撤销")
        if hasattr(self, '_redo_action'):
            self._redo_action.setEnabled(can_redo)
            self._redo_action.setToolTip(f"重做: {redo_desc}" if redo_desc else "重做")

    def _refresh_all_editors(self) -> None:
        """Refresh ALL open editor panels after undo/redo.

        数据是共享 dict，一次撤销可能影响多个已打开的标签；只刷新活动
        标签会导致其他标签显示过期值，切回后编辑会把旧值写回。
        """
        for i in range(self._tabs.count()):
            panel = self._tabs.widget(i)
            if isinstance(panel, EditorPanel):
                panel.refresh_from_data()

    def _new_unit(self) -> None:
        if self._project is None:
            QMessageBox.information(self, "提示", "请先打开或新建一个工程")
            return
        from .dialogs.new_content import NewUnitDialog
        dlg = NewUnitDialog(self)
        if dlg.exec():
            unit_kind, name = dlg.get_result()
            if name:
                self._do_create_content(unit_kind, name, "units")

    def _new_block(self) -> None:
        if self._project is None:
            QMessageBox.information(self, "提示", "请先打开或新建一个工程")
            return
        from .dialogs.new_content import NewBlockDialog
        dlg = NewBlockDialog(self)
        if dlg.exec():
            block_type, name = dlg.get_result()
            if name:
                self._do_create_content(block_type, name, "blocks")

    def _new_weapon(self) -> None:
        if self._project is None:
            QMessageBox.information(self, "提示", "请先打开或新建一个工程")
            return
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "新建武器", "名称 (英文, 小写+连字符):")
        if ok and name:
            self._do_create_content("Weapon", name, "weapons")

    def _do_create_content(self, kind: str, name: str, category: str) -> None:
        if self._project is None:
            return
        if self._session.content_exists(name):
            reply = QMessageBox.question(
                self, "内容已存在",
                f"已存在名为 '{name}' 的内容，是否覆盖？",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._session.create_content(kind, name, category)
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
        except (FileNotFoundError, ValueError):
            return

        panel = EditorPanel(
            content=content,
            metadata=self._metadata,
            command_stack=self._command_stack,
            validator=self._validator,
            project=self._project,
        )
        # v0.2.4.batch2：抬头重命名信号 → 文件树重命名逻辑
        panel.rename_requested.connect(self._file_tree._rename_content_by_name)
        # v0.2.4.batch4：数据变更 → 预览实时刷新
        panel.data_changed.connect(lambda p=panel: self._preview.show_content(p.content, self._project))
        idx = self._tabs.addTab(panel, name)
        self._add_tab_close_button(idx, panel)
        self._tabs.setCurrentIndex(idx)

    def _add_tab_close_button(self, index: int, panel: QWidget) -> None:
        """给指定标签注入文本 × 关闭按钮（纯文本，对齐设计稿）。

        捕获 panel 引用而非固定 index，关闭其他标签导致索引漂移时仍正确。
        """
        from PySide6.QtWidgets import QPushButton
        btn = QPushButton("×")
        btn.setObjectName("tabCloseBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(
            lambda checked=False, p=panel: self._close_tab(self._tabs.indexOf(p))
        )
        self._tabs.tabBar().setTabButton(
            index, QTabBar.ButtonPosition.RightSide, btn
        )

    def _on_preview_content_modified(self) -> None:
        """v0.2.4.batch4：预览 SpinBox 改坐标后，标记当前活动编辑器 dirty + 刷新表单。"""
        idx = self._tabs.currentIndex()
        if idx < 0:
            return
        panel = self._tabs.widget(idx)
        if isinstance(panel, EditorPanel):
            panel._mark_dirty()
            panel.refresh_from_data()

    def _on_content_renamed(self, old_name: str, new_name: str) -> None:
        """内容重命名后，同步已打开的标签页（名称 + 标题）+ 刷新预览。"""
        for i in range(self._tabs.count()):
            panel = self._tabs.widget(i)
            if isinstance(panel, EditorPanel) and panel.content.name == old_name:
                panel.content.name = new_name
                self._tabs.setTabText(i, new_name)
                # F-81: 重命名后预览/图层树立即显示新名
                if self._tabs.currentIndex() == i:
                    self._preview.show_content(panel.content, self._project)

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
                # 统一走 session 保存（带验证 + 错误跳转），与 Ctrl+S 一致
                self._save()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        self._tabs.removeTab(index)

    def _show_tab_context_menu(self, pos) -> None:
        """标签页右键菜单：关闭 / 关闭其他 / 关闭全部。"""
        tab_bar = self._tabs.tabBar()
        index = tab_bar.tabAt(pos)
        menu = QMenu(self)

        close_act = menu.addAction("关闭")
        close_act.setEnabled(index >= 0)
        close_others_act = menu.addAction("关闭其他")
        close_others_act.setEnabled(index >= 0 and self._tabs.count() > 1)
        close_all_act = menu.addAction("关闭全部")
        close_all_act.setEnabled(self._tabs.count() > 0)

        chosen = menu.exec(tab_bar.mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == close_act:
            self._close_tab(index)
        elif chosen == close_others_act:
            self._close_other_tabs(index)
        elif chosen == close_all_act:
            self._close_all_tabs()

    def _close_other_tabs(self, keep: int) -> None:
        """关闭除 keep 之外的所有标签（从后往前关，避免索引漂移）。"""
        for i in range(self._tabs.count() - 1, -1, -1):
            if i != keep:
                self._close_tab(i)

    def _close_all_tabs(self) -> None:
        for i in range(self._tabs.count() - 1, -1, -1):
            self._close_tab(i)

    def _on_tab_changed(self, index: int) -> None:
        if index < 0:
            return
        panel = self._tabs.widget(index)
        if isinstance(panel, EditorPanel):
            # 切换标签时从数据重建表单，防止跨标签撤销/重做后显示过期值
            panel.refresh_from_data()
            self._preview.show_content(panel.content, self._project)

    def _import_reference(self) -> None:
        dlg = _ReferencePicker(self._metadata, self)
        if dlg.exec():
            category = dlg.selected_category
            name = dlg.selected_name
            if category and name:
                self._show_reference_comparison(category, name)

    def _show_reference_comparison(self, category: str, name: str) -> None:
        """Show comparison between current content and a reference instance."""
        idx = self._tabs.currentIndex()
        if idx < 0:
            QMessageBox.information(self, "提示", "请先打开一个内容文件")
            return
        panel = self._tabs.widget(idx)
        if not isinstance(panel, EditorPanel):
            return

        try:
            ref_data = self._metadata.get_instance(category, name)
        except KeyError:
            QMessageBox.warning(self, "错误", f"找不到参考实例: {category}/{name}")
            return

        # Create or reuse reference panel in right dock
        if not hasattr(self, '_ref_panel'):
            self._ref_panel = ReferencePanel(self._metadata)
            self._ref_dock = QDockWidget("参考对比", self)
            self._ref_dock.setWidget(self._ref_panel)
            self._ref_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._ref_dock)
        else:
            self._ref_dock.show()

        self._ref_panel.set_comparison(panel.content.data, ref_data)

    def _open_settings(self) -> None:
        from .dialogs.settings_dialog import SettingsDialog
        from .theme import apply_theme, get_current_theme

        dialog = SettingsDialog(self)
        # 主题切换即时生效
        dialog.theme_changed.connect(lambda t: apply_theme(QApplication.instance(), t))
        if dialog.exec():
            dialog.apply_settings()
            # 确保最终主题与设置一致
            apply_theme(QApplication.instance(), get_current_theme())

    def _about(self) -> None:
        QMessageBox.about(
            self, "关于",
            f"Mo's Mindustry Mod Assistant v{APP_VERSION}\n\n"
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

    def _add_toolbar_button(self, toolbar: QToolBar, text: str, slot) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(slot)
        toolbar.addAction(action)
        return action

    def closeEvent(self, event) -> None:
        # 统计所有有未保存修改的标签页，统一确认（不静默丢弃）
        dirty_count = sum(
            1
            for i in range(self._tabs.count())
            if isinstance(self._tabs.widget(i), EditorPanel)
            and self._tabs.widget(i).is_dirty
        )
        if dirty_count > 0:
            reply = QMessageBox.question(
                self, "退出",
                f"有 {dirty_count} 个标签页有未保存的修改，确定退出？\n\n未保存的修改将丢失。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        event.accept()
