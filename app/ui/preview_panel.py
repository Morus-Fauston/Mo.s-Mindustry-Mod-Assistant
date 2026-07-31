"""Preview panel: QGraphicsView sprite rendering (zoom/pan) + sprite layer tree."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.config_loader import get_sprite_layers
from ..core.content_store import ContentData
from ..core.project import Project


class SpriteView(QGraphicsView):
    """支持滚轮缩放 + 拖动平移的精灵预览视口。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("previewViewport")
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        # 像素精灵用 FastTransformation 保持锐利（不模糊）
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._zoom = 1.0

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        """设置要显示的精灵图，None 表示清空。"""
        self._scene.clear()
        self._pixmap_item = None
        if pixmap is not None and not pixmap.isNull():
            self._pixmap_item = self._scene.addPixmap(pixmap)
            # 像素画放大不模糊
            self._pixmap_item.setTransformationMode(
                Qt.TransformationMode.FastTransformation
            )
            self._scene.setSceneRect(self._pixmap_item.boundingRect())
            self.fit_to_view()

    def fit_to_view(self) -> None:
        """自适应缩放，让精灵填满视口（放大像素图）。"""
        if self._pixmap_item is None:
            return
        rect = self._pixmap_item.boundingRect()
        if rect.isEmpty():
            return
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        # 记录当前缩放（相对原始像素）
        self._zoom = self.transform().m11()

    def wheelEvent(self, event) -> None:  # noqa: N802
        """滚轮缩放。"""
        factor = 1.15
        if event.angleDelta().y() > 0:
            self.scale(factor, factor)
            self._zoom *= factor
        else:
            self.scale(1 / factor, 1 / factor)
            self._zoom /= factor

    def reset_zoom(self) -> None:
        self.fit_to_view()


class PreviewPanel(QWidget):
    """Right sidebar: sprite preview (zoom/pan) + sprite layer management tree."""

    def __init__(self) -> None:
        super().__init__()
        self._project: Project | None = None
        self._content: ContentData | None = None
        self._sprite_layers_config = self._load_sprite_layers()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 面板区域标题（对齐设计稿 .panel-h）
        header = QLabel("预览")
        header.setObjectName("panelHeader")
        layout.addWidget(header)

        # 垂直分割器：预览视口 / 图层区（可拖拽调整比例）
        self._splitter = QSplitter(Qt.Orientation.Vertical)

        # 上半：预览视口 + 空态 + 导入按钮
        preview_area = QWidget()
        preview_layout = QVBoxLayout(preview_area)
        preview_layout.setContentsMargins(4, 4, 4, 4)
        preview_layout.setSpacing(6)

        self._view = SpriteView()
        self._view.setMinimumSize(200, 120)
        preview_layout.addWidget(self._view, stretch=1)

        self._empty_overlay = QLabel("无精灵图\n点击「导入精灵图」添加主体贴图")
        self._empty_overlay.setObjectName("previewEmpty")
        self._empty_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_overlay.setWordWrap(True)
        preview_layout.addWidget(self._empty_overlay)

        self._import_btn = QPushButton("导入精灵图")
        self._import_btn.clicked.connect(self._import_main_sprite)
        self._import_btn.setVisible(False)
        preview_layout.addWidget(self._import_btn)

        self._splitter.addWidget(preview_area)

        # 下半：图层树
        layer_area = QWidget()
        layer_layout = QVBoxLayout(layer_area)
        layer_layout.setContentsMargins(4, 4, 4, 4)
        layer_layout.setSpacing(4)

        layer_label = QLabel("精灵图图层")
        layer_label.setObjectName("previewLayerTitle")
        layer_layout.addWidget(layer_label)

        self._layer_tree = QTreeWidget()
        self._layer_tree.setHeaderHidden(True)
        self._layer_tree.itemClicked.connect(self._on_layer_clicked)
        layer_layout.addWidget(self._layer_tree)

        self._splitter.addWidget(layer_area)
        self._splitter.setSizes([360, 240])  # 6:4 ratio
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)
        layout.addWidget(self._splitter, stretch=1)

    def show_content(self, content: ContentData, project: Project | None) -> None:
        self._content = content
        self._project = project
        self._refresh_preview()
        self._refresh_layer_tree()

    def _refresh_preview(self) -> None:
        if self._content is None or self._project is None:
            self._view.set_pixmap(None)
            self._view.setVisible(False)
            self._empty_overlay.setText("无预览")
            self._empty_overlay.setVisible(True)
            self._import_btn.setVisible(False)
            return

        # Try to load main sprite
        category = self._content.category
        name = self._content.name
        sprite_path = self._project.sprite_path(category, name)

        if sprite_path.exists():
            pixmap = QPixmap(str(sprite_path))
            if not pixmap.isNull():
                self._view.set_pixmap(pixmap)
                self._view.setVisible(True)
                self._empty_overlay.setVisible(False)
                self._import_btn.setVisible(False)
                return

        # No sprite found
        self._view.set_pixmap(None)
        self._view.setVisible(False)
        self._empty_overlay.setText("无精灵图\n点击「导入精灵图」添加主体贴图")
        self._empty_overlay.setVisible(True)
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
        return get_sprite_layers() or {}
