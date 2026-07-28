"""Preview panel: static sprite rendering + sprite layer tree."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.content_store import ContentData
from ..core.project import Project


class PreviewPanel(QWidget):
    """Right sidebar: sprite preview (static layered) + sprite layer management tree."""

    def __init__(self) -> None:
        super().__init__()
        self._project: Project | None = None
        self._content: ContentData | None = None
        self._sprite_layers_config = self._load_sprite_layers()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Preview area
        self._preview_label = QLabel("无预览")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumSize(200, 200)
        self._preview_label.setStyleSheet(
            "background-color: #1a1a2e; border: 1px solid #333; border-radius: 4px;"
        )
        layout.addWidget(self._preview_label, stretch=1)

        # Import button (shown when no sprite)
        self._import_btn = QPushButton("导入精灵图")
        self._import_btn.clicked.connect(self._import_main_sprite)
        self._import_btn.setVisible(False)
        layout.addWidget(self._import_btn)

        # Sprite layer tree
        layer_label = QLabel("精灵图图层")
        layer_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(layer_label)

        self._layer_tree = QTreeWidget()
        self._layer_tree.setHeaderHidden(True)
        self._layer_tree.setMaximumHeight(200)
        self._layer_tree.itemClicked.connect(self._on_layer_clicked)
        layout.addWidget(self._layer_tree)

    def show_content(self, content: ContentData, project: Project | None) -> None:
        self._content = content
        self._project = project
        self._refresh_preview()
        self._refresh_layer_tree()

    def _refresh_preview(self) -> None:
        if self._content is None or self._project is None:
            self._preview_label.setText("无预览")
            self._import_btn.setVisible(False)
            return

        # Try to load main sprite
        category = self._content.category
        name = self._content.name
        sprite_path = self._project.sprite_path(category, name)

        if sprite_path.exists():
            pixmap = QPixmap(str(sprite_path))
            if not pixmap.isNull():
                # Scale up for visibility (sprites are tiny)
                scaled = pixmap.scaled(
                    192, 192,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                self._preview_label.setPixmap(scaled)
                self._import_btn.setVisible(False)
                return

        # No sprite found
        self._preview_label.setText("无精灵图")
        self._import_btn.setVisible(True)

    def _refresh_layer_tree(self) -> None:
        self._layer_tree.clear()
        if self._content is None or self._project is None:
            return

        content_type = self._content.data.get("type", "")
        layers = self._sprite_layers_config.get(content_type, [])
        if not layers:
            # Fallback: just show main sprite
            layers = [{"suffix": "", "label": "主体", "required": True}]

        category = self._content.category
        name = self._content.name

        root = QTreeWidgetItem(self._layer_tree, [f"{name} 图层"])
        root.setExpanded(True)

        for layer in layers:
            suffix = layer.get("suffix", "")
            label = layer.get("label", suffix or "主体")
            required = layer.get("required", False)

            sprite_path = self._project.sprite_path(category, name, suffix)
            status = "有" if sprite_path.exists() else ("缺失" if required else "可选")

            item = QTreeWidgetItem(root, [f"{label}  [{status}]"])
            item.setData(0, 256, str(sprite_path))
            item.setData(0, 257, suffix)

            if not sprite_path.exists():
                item.setForeground(0, Qt.GlobalColor.gray)

    def _import_main_sprite(self) -> None:
        if self._content is None or self._project is None:
            return
        self._import_sprite_for_suffix("")

    def _on_layer_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        path_str = item.data(0, 256)
        if not path_str:
            return
        sprite_path = Path(path_str)
        if not sprite_path.exists():
            suffix = item.data(0, 257) or ""
            self._import_sprite_for_suffix(suffix)

    def _import_sprite_for_suffix(self, suffix: str) -> None:
        if self._content is None or self._project is None:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择精灵图 (PNG)", "", "PNG 图片 (*.png)"
        )
        if not file_path:
            return

        # Copy to correct location
        import shutil
        category = self._content.category
        name = self._content.name
        target = self._project.sprite_path(category, name, suffix)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, str(target))

        self._refresh_preview()
        self._refresh_layer_tree()

    @staticmethod
    def _load_sprite_layers() -> dict:
        config_path = Path(__file__).parent.parent / "config" / "sprite_layers.json"
        if config_path.exists():
            return json.loads(config_path.read_text(encoding="utf-8"))
        return {}
