"""设置对话框：左侧分类列表 + 右侧设置项表单。

B 阶段范围（见 Docs/v021-UI设计需求书.md 第六章）：
- 外观 → 主题（浅色/深色）：可用，切换即时生效
- 外观 → 显示名模式：UI 存在，占位（禁用）
- 编辑 → 自动保存间隔：UI 存在，占位（禁用）
- 预览 → 精灵图缩放倍率：UI 存在，占位（禁用）
- 文件树 → 显示模式：UI 存在，占位（禁用）
- 游戏 → Mindustry 路径：禁用

主题切换通过 theme.apply_theme 即时生效，无需重启。
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from ...core.settings import get_settings

# 分类定义：(key, 显示名)
_CATEGORIES = [
    ("appearance", "外观"),
    ("editing", "编辑"),
    ("preview", "预览"),
    ("filetree", "文件树"),
    ("game", "游戏"),
]

# 显示名模式选项：(值, 显示文本)
_DISPLAY_MODES = [
    ("zh_en", "中文 (english)"),
    ("en_zh", "english (中文)"),
    ("zh", "仅中文"),
    ("en", "仅英文"),
]

_PLACEHOLDER_TIP = "将在后续版本生效"


class SettingsDialog(QDialog):
    """设置面板。主题切换即时生效并发出 theme_changed 信号。"""

    theme_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(680, 460)
        self._settings = get_settings()

        self._build_ui()
        self._load_values()

    # ── UI 构建 ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 左侧分类列表
        self._category_list = QListWidget()
        self._category_list.setObjectName("settingsCategoryList")
        self._category_list.setFixedWidth(150)
        for key, label in _CATEGORIES:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self._category_list.addItem(item)
        self._category_list.setCurrentRow(0)
        self._category_list.currentRowChanged.connect(self._on_category_changed)
        root.addWidget(self._category_list)

        # 右侧：分页 + 底部按钮
        right = QVBoxLayout()
        right.setContentsMargins(20, 18, 20, 14)
        right.setSpacing(14)

        self._pages = QStackedWidget()
        self._pages.addWidget(self._build_appearance_page())
        self._pages.addWidget(self._build_editing_page())
        self._pages.addWidget(self._build_preview_page())
        self._pages.addWidget(self._build_filetree_page())
        self._pages.addWidget(self._build_game_page())
        right.addWidget(self._pages, stretch=1)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("确定")
        ok_btn.setProperty("class", "primary")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        right.addLayout(btn_row)

        root.addLayout(right, stretch=1)

    def _build_appearance_page(self) -> QWidget:
        page = self._make_page("外观")
        form = QFormLayout()
        form.setSpacing(12)

        # 主题（可用）
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("浅色", "light")
        self._theme_combo.addItem("深色", "dark")
        self._theme_combo.setFixedWidth(200)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        form.addRow("主题", self._theme_combo)

        # 显示名模式（占位）
        self._display_mode_combo = QComboBox()
        for value, label in _DISPLAY_MODES:
            self._display_mode_combo.addItem(label, value)
        self._display_mode_combo.setFixedWidth(200)
        self._display_mode_combo.setEnabled(False)
        self._display_mode_combo.setToolTip(_PLACEHOLDER_TIP)
        form.addRow(self._labeled("显示名模式"), self._display_mode_combo)

        page.layout().addLayout(form)
        page.layout().addStretch(1)
        return page

    def _build_editing_page(self) -> QWidget:
        page = self._make_page("编辑")
        form = QFormLayout()
        form.setSpacing(12)

        self._autosave_spin = QSpinBox()
        self._autosave_spin.setRange(30, 3600)
        self._autosave_spin.setSuffix(" 秒")
        self._autosave_spin.setFixedWidth(120)
        self._autosave_spin.setEnabled(False)
        self._autosave_spin.setToolTip(_PLACEHOLDER_TIP)
        form.addRow("自动保存间隔", self._autosave_spin)

        page.layout().addLayout(form)
        page.layout().addStretch(1)
        return page

    def _build_preview_page(self) -> QWidget:
        page = self._make_page("预览")
        form = QFormLayout()
        form.setSpacing(12)

        zoom_row = QHBoxLayout()
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setRange(1, 8)
        self._zoom_slider.setFixedWidth(160)
        self._zoom_slider.setEnabled(False)
        self._zoom_slider.setToolTip(_PLACEHOLDER_TIP)
        self._zoom_label = QLabel("×4")
        self._zoom_label.setEnabled(False)
        zoom_row.addWidget(self._zoom_slider)
        zoom_row.addWidget(self._zoom_label)
        zoom_row.addStretch(1)
        form.addRow("精灵图缩放倍率", zoom_row)

        page.layout().addLayout(form)
        page.layout().addStretch(1)
        return page

    def _build_filetree_page(self) -> QWidget:
        page = self._make_page("文件树")
        form = QFormLayout()
        form.setSpacing(12)

        self._tree_mode_combo = QComboBox()
        self._tree_mode_combo.addItem("虚拟分组", "virtual")
        self._tree_mode_combo.addItem("原始目录", "raw")
        self._tree_mode_combo.setFixedWidth(200)
        self._tree_mode_combo.setEnabled(False)
        self._tree_mode_combo.setToolTip(_PLACEHOLDER_TIP)
        form.addRow("显示模式", self._tree_mode_combo)

        page.layout().addLayout(form)
        page.layout().addStretch(1)
        return page

    def _build_game_page(self) -> QWidget:
        page = self._make_page("游戏")
        form = QFormLayout()
        form.setSpacing(12)

        path_row = QHBoxLayout()
        self._path_edit = QLabel("未设置")
        self._path_edit.setObjectName("settingsPathLabel")
        self._path_edit.setEnabled(False)
        self._path_btn = QPushButton("选择文件夹...")
        self._path_btn.setEnabled(False)
        self._path_btn.setToolTip("v0.2.2 实现")
        path_row.addWidget(self._path_edit, stretch=1)
        path_row.addWidget(self._path_btn)
        form.addRow("Mindustry 路径", path_row)

        page.layout().addLayout(form)
        page.layout().addStretch(1)
        return page

    # ── 辅助 ───────────────────────────────────────────────────────────

    @staticmethod
    def _make_page(title: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        head = QLabel(title)
        head.setObjectName("settingsPageTitle")
        layout.addWidget(head)
        return page

    @staticmethod
    def _labeled(text: str) -> QLabel:
        """生成一个带占位提示的标签。"""
        label = QLabel(text)
        label.setEnabled(False)
        label.setToolTip(_PLACEHOLDER_TIP)
        return label

    def _on_category_changed(self, row: int) -> None:
        if 0 <= row < self._pages.count():
            self._pages.setCurrentIndex(row)

    def _on_theme_changed(self, index: int) -> None:
        theme = self._theme_combo.itemData(index)
        if theme:
            # 即时生效
            self.theme_changed.emit(theme)

    # ── 值的加载与收集 ─────────────────────────────────────────────────

    def _load_values(self) -> None:
        # 主题
        theme = self._settings.get("theme", "light")
        idx = self._theme_combo.findData(theme)
        if idx >= 0:
            self._theme_combo.blockSignals(True)
            self._theme_combo.setCurrentIndex(idx)
            self._theme_combo.blockSignals(False)

        # 显示名模式（占位，仅回填显示）
        mode = self._settings.get("display_name_mode", "zh_en")
        midx = self._display_mode_combo.findData(mode)
        if midx >= 0:
            self._display_mode_combo.setCurrentIndex(midx)

        # 自动保存间隔
        self._autosave_spin.setValue(int(self._settings.get("auto_save_interval", 180)))

        # 缩放倍率
        self._zoom_slider.setValue(4)

    def apply_settings(self) -> None:
        """确定时持久化设置（主题已在切换时即时生效）。"""
        theme = self._theme_combo.currentData()
        if theme:
            self._settings.set("theme", theme)
        self._settings.save()
