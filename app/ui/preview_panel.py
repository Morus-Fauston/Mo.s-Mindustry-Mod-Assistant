"""Preview panel: QGraphicsView sprite rendering (zoom/pan) + sprite layer tree.

v0.2.4.batch4:
- R1: 坐标 PPU=4（4像素=1世界单位，003 调研结论）
- D6: 引擎双实心圆 + engineColor/engineColorInner + 默认 z 在主体下
- D1: 武器图层树每把独立行 + 行内 QDoubleSpinBox
- D7: SpinBox valueChanged 实时预览 / editingFinished 标记 dirty
- D2: 引用武器 png 跟随 + x/y 无覆盖时读被引用武器默认值
- D8: 已存在图层双击替换 + 右键菜单（替换/打开/删除）
- R3: sprite_layers visible_for 子类型过滤
"""

from __future__ import annotations

import math
import os
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal, QTimer
from PySide6.QtGui import QBrush, QColor, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsColorizeEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolButton,
    QSplitter,
    QStyle,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.config_loader import get_sprite_layers
from ..core.content_store import ContentData
from ..core.metadata import normalize_content_type
from ..core.preview_math import (
    HEALTH_LEVELS,
    TEAM_COLORS,
    PreviewAnimationState,
    cell_color_hex,
    direction_degrees,
    team_color_hex,
)
from ..core.project import Project
from ..core.sprite_io import import_sprite, save_sprite
from .theme import get_tokens
from .widgets.num_spin import NumDoubleSpinBox


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
        self._zoom = 1.0
        # 主体精灵的边界（用于 fit_to_view）
        self._base_rect = None

    @property
    def scene(self) -> QGraphicsScene:
        return self._scene

    def clear_scene(self) -> None:
        """清空场景所有元素。"""
        self._scene.clear()
        self._base_rect = None

    def set_base_rect(self, rect) -> None:
        """设置主体精灵边界（fit_to_view 以此为基准）。"""
        self._base_rect = rect

    def fit_to_view(self) -> None:
        """自适应缩放，让主体精灵填满视口。"""
        if self._base_rect is None or self._base_rect.isEmpty():
            return
        self.fitInView(self._base_rect, Qt.AspectRatioMode.KeepAspectRatio)
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

    def set_zoom(self, level: float) -> None:
        """设置绝对缩放倍率（F-54 设置面板联动）。"""
        self.resetTransform()
        self.scale(level, level)
        self._zoom = level


class PreviewPanel(QWidget):
    """Right sidebar: sprite preview (zoom/pan) + sprite layer management tree."""

    # v0.2.4.batch4: 数据变更信号（通知编辑器标记 dirty + 刷新表单）
    content_modified = Signal()

    # 图层树数据角色
    _ROLE_PATH = Qt.ItemDataRole.UserRole        # 256: sprite 文件路径
    _ROLE_SUFFIX = Qt.ItemDataRole.UserRole + 1  # 257: suffix
    _ROLE_WEAPON_INDEX = Qt.ItemDataRole.UserRole + 2  # 258: 武器索引（-1=非武器）
    _ROLE_AUTOGEN = Qt.ItemDataRole.UserRole + 3  # 259: 可自动生成标记

    # 坐标缩放比：4 像素 = 1 世界单位（003 调研结论）
    _PPU = 4

    def __init__(self) -> None:
        super().__init__()
        self._project: Project | None = None
        self._content: ContentData | None = None
        self._sprite_layers_config = self._load_sprite_layers()
        # 图层可见性缓存（suffix → bool），跨刷新保持
        self._layer_visibility: dict[str, bool] = {}
        self._animation = PreviewAnimationState()
        self._dynamic_mode = False
        self._moving = False
        self._speed = 1.0
        self._direction_value = "右"
        self._team_color = "默认"
        self._health_level = "满血"
        self._last_animation_time: float | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(17)
        self._timer.timeout.connect(self._advance_animation)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 面板区域标题（对齐设计稿 .panel-h）
        header = QWidget()
        header.setObjectName("panelHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 4, 6, 4)
        header_layout.setSpacing(4)
        header_layout.addWidget(QLabel("预览"))
        header_layout.addStretch()
        self._dynamic_button = QToolButton()
        self._dynamic_button.setText("▶")
        self._dynamic_button.setToolTip("开启动态预览")
        self._dynamic_button.clicked.connect(self._toggle_dynamic)
        header_layout.addWidget(self._dynamic_button)
        layout.addWidget(header)

        controls = QWidget()
        controls.setObjectName("previewDynamicControls")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(6, 2, 6, 2)
        controls_layout.setSpacing(2)
        controls_top = QHBoxLayout()
        controls_top.setSpacing(3)
        self._play_pause_button = QToolButton()
        self._play_pause_button.setText("Ⅱ")
        self._play_pause_button.setToolTip("暂停动态预览")
        self._play_pause_button.clicked.connect(self._toggle_dynamic)
        controls_top.addWidget(self._play_pause_button)
        self._fire_button = QToolButton()
        self._fire_button.setText("●")
        self._fire_button.setToolTip("开火一次")
        self._fire_button.clicked.connect(self._fire_once)
        controls_top.addWidget(self._fire_button)
        self._direction_box = QComboBox()
        self._direction_box.setToolTip("预览朝向")
        self._direction_box.addItems(["右", "上", "左", "下"])
        self._direction_box.currentTextChanged.connect(self._set_direction)
        controls_top.addWidget(self._direction_box)
        self._speed_box = QComboBox()
        self._speed_box.setToolTip("动画速度")
        self._speed_box.addItems(["0.5x", "1x", "2x"])
        self._speed_box.setCurrentText("1x")
        self._speed_box.currentTextChanged.connect(self._set_speed)
        controls_top.addWidget(self._speed_box)
        controls_top.addStretch()
        controls_layout.addLayout(controls_top)

        controls_bottom = QHBoxLayout()
        controls_bottom.setSpacing(3)
        self._moving_box = QComboBox()
        self._moving_box.setToolTip("单位移动状态")
        self._moving_box.addItems(["原地", "移动"])
        self._moving_box.currentTextChanged.connect(self._set_moving)
        controls_bottom.addWidget(self._moving_box)
        self._team_box = QComboBox()
        self._team_box.setToolTip("队伍色")
        self._team_box.addItems(list(TEAM_COLORS))
        self._team_box.currentTextChanged.connect(self._set_team_color)
        controls_bottom.addWidget(self._team_box)
        self._health_box = QComboBox()
        self._health_box.setToolTip("单位血量")
        self._health_box.addItems(list(HEALTH_LEVELS))
        self._health_box.currentTextChanged.connect(self._set_health_level)
        controls_bottom.addWidget(self._health_box)
        controls_bottom.addStretch()
        controls_layout.addLayout(controls_bottom)
        controls.setVisible(False)
        self._dynamic_controls = controls
        layout.addWidget(controls)

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
        self._layer_tree.setObjectName("layerTree")
        self._layer_tree.setColumnCount(2)
        self._layer_tree.setHeaderHidden(True)
        # 图层树不需要选中态（用户决策）：NoSelection 从根源上阻止 Qt 绘制
        # 任何选中视觉（windows11 原生选中框 QSS 覆盖不掉），右键/双击均用
        # itemAt 或 item 参数，不依赖选中。
        self._layer_tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        # 列0 固定 220px：容纳最深缩进的复选框 + 最宽图层名（含"引擎示意"
        # 等 4 字名），不再按内容自适应（RTC 在带 itemWidget 的行上会算窄，
        # 导致名称被截断成"引擎..."）。列1 保持默认拉伸吃剩余。
        self._layer_tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self._layer_tree.setColumnWidth(0, 220)
        self._layer_tree.itemDoubleClicked.connect(self._on_layer_double_clicked)
        self._layer_tree.itemChanged.connect(self._on_layer_check_changed)
        self._layer_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._layer_tree.customContextMenuRequested.connect(self._show_layer_context_menu)
        # 拦截复选框区域的双击：点击复选框 toggle 不应触发"更换图片"（D8）。
        self._layer_tree.viewport().installEventFilter(self)
        layer_layout.addWidget(self._layer_tree)

        self._splitter.addWidget(layer_area)
        self._splitter.setSizes([360, 240])  # 6:4 ratio
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)
        layout.addWidget(self._splitter, stretch=1)

        # 设置面板缩放倍率（F-54）
        self._base_zoom = 4

    def set_base_zoom(self, zoom: int) -> None:
        """设置面板缩放倍率，重新渲染当前内容。"""
        self._base_zoom = zoom
        if self._content is not None:
            self.show_content(self._content, self._project)

    def show_content(self, content: ContentData, project: Project | None) -> None:
        self._content = content
        self._project = project
        self._reset_animation()
        self._refresh_preview()
        self._refresh_layer_tree()

    def is_showing(self, category: str, name: str) -> bool:
        """当前预览是否正展示该 content（F-21 归属判定）。"""
        return (
            self._content is not None
            and self._content.category == category
            and self._content.name == name
        )

    def refresh(self) -> None:
        """按当前 content/project 重新渲染预览 + 图层树（F-21 外部改图刷新）。

        与 show_content 的区别：不重置可见性缓存、不换 content 引用，
        只重读精灵文件并重建场景。
        """
        if self._content is None:
            return
        self._refresh_preview()
        self._refresh_layer_tree()

    def _toggle_dynamic(self) -> None:
        self._dynamic_mode = not self._dynamic_mode
        self._dynamic_controls.setVisible(self._dynamic_mode)
        self._update_dynamic_buttons()
        if self._dynamic_mode:
            self._last_animation_time = time.monotonic()
            self._timer.start()
        else:
            self._timer.stop()
            self._last_animation_time = None
            self._refresh_preview()

    def _update_dynamic_buttons(self) -> None:
        """Keep the persistent entry and in-mode pause control in sync."""
        text = "Ⅱ" if self._dynamic_mode else "▶"
        tooltip = "暂停动态预览" if self._dynamic_mode else "开启动态预览"
        self._dynamic_button.setText(text)
        self._dynamic_button.setToolTip(tooltip)
        self._play_pause_button.setText(text)
        self._play_pause_button.setToolTip(tooltip)

    def _fire_once(self) -> None:
        self._animation.fire()
        self._refresh_preview()

    def _advance_animation(self) -> None:
        if self._dynamic_mode:
            now = time.monotonic()
            previous = self._last_animation_time or now
            self._last_animation_time = now
            delta_tick = min((now - previous) * 60.0 * self._speed, 3.0)
            data = self._content.data if self._content is not None else {}
            self._animation.advance(
                delta_tick,
                recoil_time=float(data.get("recoilTime", 10.0)),
                cooldown_time=float(data.get("cooldownTime", 20.0)),
                moving=self._moving,
            )
            if self._animation.recoil <= 0 and self._animation.heat <= 0:
                self._animation.fire()
            self._refresh_preview()

    def _reset_animation(self) -> None:
        self._timer.stop()
        self._last_animation_time = None
        self._animation = PreviewAnimationState()
        self._dynamic_mode = False
        self._moving = False
        self._speed = 1.0
        self._direction_value = "右"
        self._team_color = "默认"
        self._health_level = "满血"
        if hasattr(self, "_dynamic_controls"):
            self._dynamic_controls.setVisible(False)
            self._update_dynamic_buttons()
            self._speed_box.setCurrentText("1x")
            self._moving_box.setCurrentText("原地")
            self._direction_box.setCurrentText("右")
            self._team_box.setCurrentText("默认")
            self._health_box.setCurrentText("满血")

    def _set_direction(self, value: str) -> None:
        self._direction_value = value
        if self._dynamic_mode:
            self._refresh_preview()

    def _set_speed(self, value: str) -> None:
        self._speed = float(value[:-1])

    def _set_moving(self, value: str) -> None:
        self._moving = value == "移动"

    def _set_team_color(self, value: str) -> None:
        self._team_color = value
        if self._dynamic_mode:
            self._refresh_preview()

    def _set_health_level(self, value: str) -> None:
        self._health_level = value
        if self._dynamic_mode:
            self._refresh_preview()

    def eventFilter(self, obj, event) -> bool:  # noqa: ANN001
        """拦截图层树 viewport 的双击：若双击落在复选框 indicator 上，
        吞掉事件（只 toggle 复选框），不触发「更换图片」（D8）。"""
        if (
            obj is self._layer_tree.viewport()
            and event.type() == QEvent.Type.MouseButtonDblClick
        ):
            pos = event.position().toPoint()
            item = self._layer_tree.itemAt(pos)
            if item is not None and (
                item.flags() & Qt.ItemFlag.ItemIsUserCheckable
            ):
                r = self._layer_tree.visualItemRect(item)
                opt = QStyleOptionViewItem()
                opt.initFrom(self._layer_tree)
                opt.rect = r
                opt.features = QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
                opt.checkState = item.checkState(0)
                opt.text = item.text(0)
                opt.index = self._layer_tree.indexFromItem(item)
                ind = self._layer_tree.style().subElementRect(
                    QStyle.SubElement.SE_ItemViewItemCheckIndicator,
                    opt, self._layer_tree,
                )
                if ind.adjusted(-6, -6, 6, 6).contains(pos):
                    return True
        return super().eventFilter(obj, event)

    # ── 预览渲染 ─────────────────────────────────────────────────────────

    def _refresh_preview(self) -> None:
        """重建预览场景：多层精灵合成 + 武器叠加 + 引擎圆。

        每个精灵图层作为独立 QGraphicsPixmapItem 加入场景，
        可见性由 _layer_visibility 控制（F-73）。
        """
        self._view.clear_scene()
        self._scene_items: dict[str, list] = {}  # suffix → [QGraphicsItem]

        if self._content is None or self._project is None:
            self._view.setVisible(False)
            self._empty_overlay.setText("无预览")
            self._empty_overlay.setVisible(True)
            self._import_btn.setVisible(False)
            return

        category = self._content.category
        name = self._content.name
        content_type = normalize_content_type(self._content.data.get("type", ""))

        # 获取该类型的图层配置
        layers = self._sprite_layers_config.get(content_type, [])
        if not layers:
            layers = [{"suffix": "", "label": "主体", "required": True}]

        # 主体精灵（确定场景边界）
        main_path = self._project.sprite_path(category, name)
        if not main_path.exists():
            self._view.setVisible(False)
            self._empty_overlay.setText("无精灵图\n点击「导入精灵图」添加主体贴图")
            self._empty_overlay.setVisible(True)
            self._import_btn.setVisible(True)
            return

        main_pixmap = QPixmap(str(main_path))
        if main_pixmap.isNull():
            self._view.setVisible(False)
            self._empty_overlay.setText("精灵图加载失败")
            self._empty_overlay.setVisible(True)
            self._import_btn.setVisible(True)
            return

        main_item = self._view.scene.addPixmap(main_pixmap)
        main_item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        main_item.setZValue(0)
        base_rect = main_item.boundingRect()
        self._view.set_base_rect(base_rect)
        self._scene_items.setdefault("", []).append(main_item)

        # 主体尺寸 → 中心点（Mindustry 坐标系原点在精灵中心）
        cx = base_rect.width() / 2.0
        cy = base_rect.height() / 2.0

        # 加载其他精灵图层（-cell, -full, -treads 等）
        subtype = self._content.data.get("type", "")
        z = 1
        for layer in layers:
            suffix = layer.get("suffix", "")
            if suffix == "":
                continue  # 主体已加载
            # R3: visible_for 子类型过滤（与图层树一致）
            visible_for = layer.get("visible_for")
            if visible_for and subtype not in visible_for:
                continue
            layer_path = self._project.sprite_path(category, name, suffix)
            if suffix == "-treads":
                animated_tread = self._animated_tread_path(category, name)
                if animated_tread is not None:
                    layer_path = animated_tread
            if not layer_path.exists():
                continue
            layer_pixmap = QPixmap(str(layer_path))
            if layer_pixmap.isNull():
                continue
            item = self._view.scene.addPixmap(layer_pixmap)
            item.setTransformationMode(Qt.TransformationMode.FastTransformation)
            # z-order（v0.2.5 修复）：阴影在最底（-3），轮廓次之（-2），
            # 引擎 -1，主体 0，其余图层在主体上方。原实现所有图层 z 递增，
            # 阴影被画在主体之上 → 半透明黑盖住主体，视觉上"渲染在上方"。
            if suffix == "-shadow":
                item.setZValue(-3)
            elif suffix == "-outline":
                item.setZValue(-2)
            else:
                item.setZValue(z)
                z += 1
            # 居中对齐到主体
            item.setPos(
                cx - layer_pixmap.width() / 2.0,
                cy - layer_pixmap.height() / 2.0,
            )
            self._scene_items.setdefault(suffix, []).append(item)

        # F-72: 武器叠加
        self._draw_weapons(cx, cy)

        # F-72: 引擎示意圆
        self._draw_engine(cx, cy)

        self._draw_heat_overlay(cx, cy)
        self._draw_muzzle_flash(cx, cy, base_rect)

        # 应用图层可见性（F-73）
        self._apply_all_layer_visibility()
        self._apply_dynamic_appearance(cx, cy)

        self._view.setVisible(True)
        self._empty_overlay.setVisible(False)
        self._import_btn.setVisible(False)
        self._view.set_zoom(float(self._base_zoom))

    def _apply_all_layer_visibility(self) -> None:
        """根据 _layer_visibility 设置所有场景元素的可见性。"""
        for suffix, items in self._scene_items.items():
            visible = self._layer_visibility.get(suffix, True)
            for item in items:
                item.setVisible(visible)

    def _animated_tread_path(self, category: str, name: str) -> Path | None:
        """Return the generated tank-tread frame selected by simulated movement.

        The game generates these regions as ``name-treads<rect>-<frame>``.
        MoMA keeps the existing static tread image unless dynamic mode, movement,
        and at least one generated frame are all present.
        """
        if not self._dynamic_mode or not self._moving or self._content is None:
            return None
        frames = max(int(self._content.data.get("treadFrames", 18)), 1)
        paths = [
            self._project.sprite_path(category, name, f"-treads0-{index}")
            for index in range(frames)
        ]
        available = [path for path in paths if path.exists()]
        if not available:
            return None
        return available[self._animation.tread_frame(len(available))]

    def _draw_heat_overlay(self, cx: float, cy: float) -> None:
        """Draw the optional heat sprite using the shared recoil/heat state."""
        if (
            not self._dynamic_mode
            or self._animation.heat <= 0
            or self._content is None
            or self._project is None
        ):
            return
        path = self._project.sprite_path(self._content.category, self._content.name, "-heat")
        if not path.exists():
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        item = self._view.scene.addPixmap(pixmap)
        item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        item.setPos(cx - pixmap.width() / 2.0, cy - pixmap.height() / 2.0)
        item.setZValue(12)
        item.setOpacity(self._animation.heat)
        effect = QGraphicsColorizeEffect()
        effect.setColor(QColor("#ff795e"))
        effect.setStrength(1.0)
        item.setGraphicsEffect(effect)
        item.setToolTip("热图")
        self._scene_items.setdefault("__heat__", []).append(item)

    def _draw_muzzle_flash(self, cx: float, cy: float, base_rect) -> None:
        """Draw a deliberately simple three-tick muzzle flash for the demo."""
        if not self._dynamic_mode or self._animation.muzzle_flash_opacity() <= 0:
            return
        radius = max(3.0, min(base_rect.width(), base_rect.height()) / 8.0)
        flash = self._view.scene.addEllipse(
            cx - radius,
            cy - base_rect.height() * 0.42 - radius,
            radius * 2,
            radius * 2,
            QPen(Qt.PenStyle.NoPen),
            QBrush(QColor("#fff3a1")),
        )
        flash.setZValue(20)
        flash.setOpacity(self._animation.muzzle_flash_opacity())
        flash.setToolTip("枪口闪光")
        self._scene_items.setdefault("__muzzle_flash__", []).append(flash)

    def _apply_dynamic_appearance(self, cx: float, cy: float) -> None:
        """Translate pure dynamic state to Qt-only transforms and color effects."""
        if not self._dynamic_mode:
            return

        team_color = QColor(team_color_hex(self._team_color))
        for item in self._scene_items.get("-team", []):
            effect = QGraphicsColorizeEffect()
            effect.setColor(team_color)
            effect.setStrength(1.0)
            item.setGraphicsEffect(effect)

        cell_color = QColor(
            cell_color_hex(self._team_color, self._health_level, self._animation.time_tick)
        )
        for item in self._scene_items.get("-cell", []):
            effect = QGraphicsColorizeEffect()
            effect.setColor(cell_color)
            effect.setStrength(1.0)
            item.setGraphicsEffect(effect)

        rotation = direction_degrees(self._direction_value)
        for items in self._scene_items.values():
            for item in items:
                pos = item.pos()
                item.setTransformOriginPoint(cx - pos.x(), cy - pos.y())
                item.setRotation(rotation)

    def _draw_weapons(self, cx: float, cy: float) -> None:
        """按 weapons 数组叠加武器精灵图（PPU=4 坐标映射）。

        Mindustry 坐标系：x 右正、y 上正；Qt 场景：x 右正、y 下正。
        转换：scene_x = cx + wx * PPU, scene_y = cy - wy * PPU
        """
        if self._content is None or self._project is None:
            return
        weapons = self._content.data.get("weapons")
        if not isinstance(weapons, list):
            return

        ppu = self._PPU
        for i, w in enumerate(weapons):
            if not isinstance(w, dict):
                continue
            w_name = w.get("name", "")
            if not w_name:
                continue

            # D2: 引用武器 x/y 无覆盖时读被引用武器默认值
            wx, wy = self._resolve_weapon_xy(w, w_name)
            mirror = bool(w.get("mirror", False))

            w_pixmap = self._find_weapon_sprite(w_name)
            if w_pixmap is None or w_pixmap.isNull():
                continue

            w_cx = w_pixmap.width() / 2.0
            w_cy = w_pixmap.height() / 2.0

            # R1: PPU=4 坐标映射
            scene_x = cx + wx * ppu - w_cx
            recoil_offset = (
                -self._animation.recoil_offset(
                    distance=float(w.get("recoil", 1.0)),
                    power=float(w.get("recoilPow", 1.8)),
                ) * ppu
                if self._dynamic_mode
                else 0.0
            )
            scene_y = cy - wy * ppu - w_cy + recoil_offset
            item = self._view.scene.addPixmap(w_pixmap)
            item.setTransformationMode(Qt.TransformationMode.FastTransformation)
            item.setPos(scene_x, scene_y)
            item.setZValue(10)
            item.setToolTip(f"武器: {w_name}  ({wx}, {wy})")
            self._scene_items.setdefault(f"__weapon_{i}__", []).append(item)

            if mirror:
                flipped = w_pixmap.transformed(
                    QTransform().scale(-1, 1),
                    Qt.TransformationMode.FastTransformation,
                )
                scene_x_m = cx - wx * ppu - w_cx
                item_m = self._view.scene.addPixmap(flipped)
                item_m.setTransformationMode(Qt.TransformationMode.FastTransformation)
                item_m.setPos(scene_x_m, scene_y)
                item_m.setZValue(10)
                item_m.setToolTip(f"武器: {w_name}  ({-wx}, {wy}) (镜像)")
                self._scene_items.setdefault(f"__weapon_{i}__", []).append(item_m)

    def _resolve_weapon_xy(self, w: dict, w_name: str) -> tuple[float, float]:
        """D2: 引用武器 x/y 无覆盖时读被引用武器 JSON 的默认值。"""
        wx = w.get("x")
        wy = w.get("y")
        if wx is not None and wy is not None:
            return float(wx), float(wy)
        # 尝试读被引用武器 JSON
        if self._project is not None:
            try:
                ref = self._project.contents.get(w_name)
                if wx is None:
                    wx = float(ref.data.get("x", 0))
                if wy is None:
                    wy = float(ref.data.get("y", 0))
                return float(wx), float(wy)
            except (FileNotFoundError, ValueError):
                pass
        return float(wx or 0), float(wy or 0)

    def _draw_engine(self, cx: float, cy: float) -> None:
        """D6: 引擎双实心圆（外圈 engineColor + 内圈 engineColorInner）。

        默认 z 在主体下（zValue=-1）；engineLayer>0 时提升到主体上。
        PPU=4 坐标映射。
        """
        if self._content is None:
            return
        data = self._content.data
        engine_size = float(data.get("engineSize", 0))
        if engine_size <= 0:
            return
        engine_offset = float(data.get("engineOffset", 0))
        ppu = self._PPU

        # 默认引擎位置：单位中心正后方（y 取反 → 精灵上向下）
        ex = cx
        ey = cy + engine_offset * ppu
        radius = engine_size * ppu
        if self._dynamic_mode:
            radius *= 1.0 + self._animation.pulse() * 0.25

        # 外圈颜色：engineColor 未设置 → 亮黄/橙占位（= 默认队伍色）
        outer_hex = data.get("engineColor")
        if outer_hex:
            outer_color = QColor(f"#{outer_hex}" if not outer_hex.startswith("#") else outer_hex)
        else:
            outer_color = QColor(255, 200, 50)  # 亮黄/橙占位

        # 内圈颜色：engineColorInner 默认白色
        inner_hex = data.get("engineColorInner")
        if inner_hex:
            inner_color = QColor(f"#{inner_hex}" if not inner_hex.startswith("#") else inner_hex)
        else:
            inner_color = QColor(255, 255, 255)

        # z-order：默认在主体下（-1），engineLayer>0 时提升
        engine_layer = float(data.get("engineLayer", -1))
        z = 11 if engine_layer > 0 else -1

        # 外圈
        pen_outer = QPen(Qt.PenStyle.NoPen)
        brush_outer = QBrush(outer_color)
        outer = self._view.scene.addEllipse(
            ex - radius, ey - radius, radius * 2, radius * 2, pen_outer, brush_outer
        )
        outer.setZValue(z)
        outer.setToolTip(f"引擎外圈 (大小={engine_size}, 偏移={engine_offset})")
        self._scene_items.setdefault("__engine__", []).append(outer)

        # 内圈（半径=外圈/2，沿 rotation 方向偏移 rad/4）
        inner_radius = radius / 2.0
        rotation_deg = -90.0  # 默认引擎 rotation
        rot_rad = math.radians(rotation_deg)
        inner_offset = radius / 4.0
        ix = ex - math.cos(rot_rad) * inner_offset
        iy = ey - math.sin(rot_rad) * inner_offset

        pen_inner = QPen(Qt.PenStyle.NoPen)
        brush_inner = QBrush(inner_color)
        inner = self._view.scene.addEllipse(
            ix - inner_radius, iy - inner_radius,
            inner_radius * 2, inner_radius * 2, pen_inner, brush_inner
        )
        inner.setZValue(z)
        inner.setToolTip(f"引擎内圈")
        self._scene_items["__engine__"].append(inner)

    def _find_weapon_sprite(self, weapon_name: str) -> QPixmap | None:
        """查找武器精灵图：weapons 目录 → 单位同目录 → 递归搜索。"""
        if self._project is None or self._content is None:
            return None

        # 1. sprites/weapons/{name}.png
        p = self._project.sprite_path("weapons", weapon_name)
        if p.exists():
            return QPixmap(str(p))

        # 2. 单位精灵同目录（蓝钢风格：武器 png 与单位 png 同文件夹）
        unit_sprite = self._project.sprite_path(
            self._content.category, self._content.name
        )
        sibling = unit_sprite.parent / f"{weapon_name}.png"
        if sibling.exists():
            return QPixmap(str(sibling))

        # 3. sprites/ 下递归搜索
        sprites_dir = self._project.sprites_dir
        if sprites_dir.is_dir():
            matches = list(sprites_dir.rglob(f"{weapon_name}.png"))
            if matches:
                return QPixmap(str(matches[0]))

        return None

    # ── 图层树 ───────────────────────────────────────────────────────────

    def _refresh_layer_tree(self) -> None:
        """重建图层树（R3: visible_for 过滤 + D1: 每武器独立行+SpinBox）."""
        self._layer_tree.blockSignals(True)
        self._layer_tree.clear()

        if self._content is None or self._project is None:
            self._layer_tree.blockSignals(False)
            return

        content_type = normalize_content_type(self._content.data.get("type", ""))
        subtype = self._content.data.get("type", "")  # tank/flying/legs/...（游戏值）
        layers = self._sprite_layers_config.get(content_type, [])
        if not layers:
            layers = [{"suffix": "", "label": "主体", "required": True}]

        category = self._content.category
        name = self._content.name

        root = QTreeWidgetItem(self._layer_tree, [f"{name} 图层", ""])
        root.setExpanded(True)

        for layer in layers:
            suffix = layer.get("suffix", "")
            label = layer.get("label", suffix or "主体")
            required = layer.get("required", False)

            # R3: visible_for 子类型过滤
            visible_for = layer.get("visible_for")
            if visible_for and subtype not in visible_for:
                continue

            sprite_path = self._project.sprite_path(category, name, suffix)
            exists = sprite_path.exists()
            status = "有" if exists else ("缺失" if required else "可选")

            # 列0 只放图层名（状态 [有]/[可选]/[缺失] 移到列1，避免把列0
            # 撑宽导致武器行输入框远离文本 / 被压缩交叠，见 v0.2.5 修复）
            item = QTreeWidgetItem(root, [label, f"[{status}]"])
            item.setTextAlignment(
                1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            tokens = get_tokens()
            status_color = QColor(tokens["ERR"]) if not exists else QColor(tokens["INK2"])
            item.setForeground(1, status_color)
            item.setData(0, self._ROLE_PATH, str(sprite_path))
            item.setData(0, self._ROLE_SUFFIX, suffix)
            item.setData(0, self._ROLE_WEAPON_INDEX, -1)
            autogen = bool(layer.get("autoGenerable", False))
            item.setData(0, self._ROLE_AUTOGEN, autogen)

            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            visible = self._layer_visibility.get(suffix, True)
            item.setCheckState(
                0,
                Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked,
            )
            if not exists:
                item.setForeground(0, Qt.GlobalColor.gray)
                # F-20: 可自动生成且缺失 → 列1 显示 [生成] 按钮
                if autogen:
                    gen_btn = QPushButton("[生成]")
                    gen_btn.setFixedWidth(50)
                    gen_btn.setFlat(True)
                    gen_btn.setProperty("gen_suffix", suffix)
                    gen_btn.clicked.connect(self._on_generate_clicked)
                    self._layer_tree.setItemWidget(item, 1, gen_btn)

        # D1: 武器独立行
        if category == "units":
            self._add_weapon_layer_items(root)
            self._add_engine_layer_item(root)

        self._layer_tree.blockSignals(False)

    def _add_weapon_layer_items(self, root: QTreeWidgetItem) -> None:
        """D1: 每把武器独立行 + 行内 QDoubleSpinBox 编辑 x/y."""
        data = self._content.data if self._content else {}
        weapons = data.get("weapons")
        if not isinstance(weapons, list) or not weapons:
            return

        weapon_parent = QTreeWidgetItem(root, ["武器", ""])
        weapon_parent.setExpanded(True)

        for i, w in enumerate(weapons):
            if not isinstance(w, dict):
                continue
            w_name = w.get("name", f"weapon-{i}")
            wx, wy = self._resolve_weapon_xy(w, w_name)

            item = QTreeWidgetItem(weapon_parent, [w_name, ""])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            visible = self._layer_visibility.get(f"__weapon_{i}__", True)
            item.setCheckState(
                0,
                Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked,
            )
            item.setData(0, self._ROLE_SUFFIX, f"__weapon_{i}__")
            item.setData(0, self._ROLE_WEAPON_INDEX, i)

            # 行内 SpinBox 容器
            spin_container = QWidget()
            spin_layout = QHBoxLayout(spin_container)
            spin_layout.setContentsMargins(0, 0, 0, 0)
            spin_layout.setSpacing(2)

            # NumDoubleSpinBox：滚轮只滚页面不改值 + 去尾零（与主面板一致）
            spin_x = NumDoubleSpinBox()
            spin_x.setRange(-40, 40)
            spin_x.setSingleStep(0.25)
            spin_x.setDecimals(2)
            spin_x.setFixedWidth(70)
            spin_x.setPrefix("x ")
            spin_x.setProperty("weapon_idx", i)
            spin_x.setProperty("coord", "x")
            spin_x.valueChanged.connect(self._on_weapon_spin_changed)
            spin_x.editingFinished.connect(self._on_weapon_spin_finished)
            # 先 connect 再 block+setValue：重建期间 setValue 不得触发
            # valueChanged 写回 dict（否则把编辑区已修改的 XY 覆写为旧值，
            # 或把引用武器默认值污染进 dict，v0.2.5 修复）
            spin_x.blockSignals(True)
            spin_x.setValue(wx)
            spin_x.blockSignals(False)
            spin_layout.addWidget(spin_x)

            spin_y = NumDoubleSpinBox()
            spin_y.setRange(-40, 40)
            spin_y.setSingleStep(0.25)
            spin_y.setDecimals(2)
            spin_y.setFixedWidth(70)
            spin_y.setPrefix("y ")
            spin_y.setProperty("weapon_idx", i)
            spin_y.setProperty("coord", "y")
            spin_y.valueChanged.connect(self._on_weapon_spin_changed)
            spin_y.editingFinished.connect(self._on_weapon_spin_finished)
            spin_y.blockSignals(True)
            spin_y.setValue(wy)
            spin_y.blockSignals(False)
            spin_layout.addWidget(spin_y)

            self._layer_tree.setItemWidget(item, 1, spin_container)

    def _add_engine_layer_item(self, root: QTreeWidgetItem) -> None:
        """引擎示意虚拟图层。"""
        data = self._content.data if self._content else {}
        if float(data.get("engineSize", 0)) <= 0:
            return
        item = QTreeWidgetItem(root, ["引擎示意", ""])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        visible = self._layer_visibility.get("__engine__", True)
        item.setCheckState(
            0,
            Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked,
        )
        item.setData(0, self._ROLE_SUFFIX, "__engine__")
        item.setData(0, self._ROLE_WEAPON_INDEX, -1)

    # ── 武器 SpinBox 交互（D7）─────────────────────────────────────────

    def _on_weapon_spin_changed(self, value: float) -> None:
        """D7: valueChanged → 直接改 dict + 实时预览（不入 CommandStack）。"""
        spin = self.sender()
        if spin is None or self._content is None:
            return
        idx = spin.property("weapon_idx")
        coord = spin.property("coord")
        weapons = self._content.data.get("weapons")
        if not isinstance(weapons, list) or idx >= len(weapons):
            return
        w = weapons[idx]
        if not isinstance(w, dict):
            return
        w[coord] = value
        self._refresh_preview()

    def _on_weapon_spin_finished(self) -> None:
        """D7: editingFinished → 标记 dirty + 通知编辑器。"""
        self.content_modified.emit()

    def _on_layer_check_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """图层 checkbox 切换 → 更新场景可见性。"""
        suffix = item.data(0, self._ROLE_SUFFIX)
        if suffix is None:
            return
        visible = item.checkState(0) == Qt.CheckState.Checked
        self._layer_visibility[suffix] = visible

        for scene_item in self._scene_items.get(suffix, []):
            scene_item.setVisible(visible)

    # ── D8: 双击替换 + 右键菜单 ─────────────────────────────────────

    def _on_layer_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """双击图层：已存在→替换，缺失→导入。"""
        suffix = item.data(0, self._ROLE_SUFFIX)
        if suffix is None or suffix.startswith("__"):
            return  # 虚拟图层不可双击
        self._import_sprite_for_suffix(suffix)

    def _show_layer_context_menu(self, pos) -> None:
        """D8: 图层右键菜单。"""
        item = self._layer_tree.itemAt(pos)
        if item is None:
            return
        suffix = item.data(0, self._ROLE_SUFFIX)
        if suffix is None or suffix.startswith("__"):
            return
        path_str = item.data(0, self._ROLE_PATH)
        if not path_str:
            return
        sprite_path = Path(path_str)
        exists = sprite_path.exists()

        autogen = bool(item.data(0, self._ROLE_AUTOGEN))

        menu = QMenu(self)
        if exists:
            replace_action = menu.addAction("替换精灵图")
            regen_action = menu.addAction("重新生成") if autogen else None
            reveal_action = menu.addAction("在文件管理器中打开")
            menu.addSeparator()
            delete_action = menu.addAction("删除精灵图")
        else:
            replace_action = menu.addAction("导入精灵图")
            regen_action = menu.addAction("自动生成") if autogen else None
            reveal_action = None
            delete_action = None

        chosen = menu.exec(self._layer_tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == replace_action:
            self._import_sprite_for_suffix(suffix)
        elif chosen == regen_action and autogen:
            self._generate_sprite(suffix)
        elif chosen == reveal_action and exists:
            self._reveal_sprite(sprite_path)
        elif chosen == delete_action and exists:
            self._delete_sprite(sprite_path, suffix)

    def _on_generate_clicked(self) -> None:
        """F-20: [生成] 按钮点击。"""
        btn = self.sender()
        if btn is None:
            return
        suffix = btn.property("gen_suffix")
        if suffix:
            self._generate_sprite(suffix)

    def _generate_sprite(self, suffix: str) -> None:
        """F-20: 自动生成 outline/shadow/full 精灵图。"""
        from ..core.sprite_generator import generate_full, generate_outline, generate_shadow

        if self._content is None or self._project is None:
            return

        category = self._content.category
        name = self._content.name
        main_path = self._project.sprite_path(category, name)
        if not main_path.exists():
            return

        from PIL import Image as PILImage

        src = PILImage.open(str(main_path)).convert("RGBA")
        if suffix == "-outline":
            result = generate_outline(src)
        elif suffix == "-shadow":
            result = generate_shadow(src)
        elif suffix == "-full":
            # 收集额外图层（cell 等）
            layers_pil = []
            layers_cfg = self._sprite_layers_config.get(
                self._content.data.get("type", ""), []
            )
            for layer in layers_cfg:
                ls = layer.get("suffix", "")
                if ls in ("", "-full", "-outline", "-shadow"):
                    continue
                lp = self._project.sprite_path(category, name, ls)
                if lp.exists():
                    layers_pil.append(PILImage.open(str(lp)).convert("RGBA"))

            # 收集武器精灵
            weapons = self._content.data.get("weapons")
            weapon_sprites = []
            weapons_list = []
            if isinstance(weapons, list):
                for w in weapons:
                    if not isinstance(w, dict):
                        continue
                    w_name = w.get("name", "")
                    if not w_name:
                        continue
                    wp = self._find_weapon_sprite(w_name)
                    if wp is not None and not wp.isNull():
                        # QPixmap → PIL
                        img = wp.toImage().convertToFormat(
                            wp.toImage().Format.RGBA8888
                        )
                        ptr = img.bits()
                        pil_img = PILImage.frombytes(
                            "RGBA", (img.width(), img.height()), bytes(ptr)
                        )
                        weapon_sprites.append(pil_img)
                        weapons_list.append(w)

            result = generate_full(
                src, layers=layers_pil or None,
                weapons=weapons_list or None,
                weapon_sprites=weapon_sprites or None,
                ppu=float(self._PPU),
            )
        else:
            return

        save_sprite(self._project, category, name, result, suffix, overwrite=True)
        self._refresh_preview()
        self._refresh_layer_tree()

    def _reveal_sprite(self, path: Path) -> None:
        """在文件管理器中定位精灵图。"""
        if os.name == "nt":
            subprocess.Popen(f'explorer /select,"{path}"')
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])

    def _delete_sprite(self, path: Path, suffix: str) -> None:
        """从磁盘删除精灵图 + 刷新预览。"""
        if path.exists():
            path.unlink()
        self._refresh_preview()
        self._refresh_layer_tree()

    # ── 导入 ─────────────────────────────────────────────────────────────

    def _import_main_sprite(self) -> None:
        if self._content is None or self._project is None:
            return
        self._import_sprite_for_suffix("")

    def _import_sprite_for_suffix(self, suffix: str) -> None:
        if self._content is None or self._project is None:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择精灵图 (PNG)", "", "PNG 图片 (*.png)"
        )
        if not file_path:
            return

        category = self._content.category
        name = self._content.name
        target = self._project.sprite_path(category, name, suffix)
        if target.exists():
            reply = QMessageBox.question(
                self,
                "覆盖精灵图",
                f"图层 '{target.name}' 已存在，是否覆盖？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            import_sprite(
                self._project,
                category,
                name,
                file_path,
                suffix,
                overwrite=target.exists(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "导入精灵图失败", str(exc))
            return

        self._refresh_preview()
        self._refresh_layer_tree()

    @staticmethod
    def _load_sprite_layers() -> dict:
        return get_sprite_layers() or {}
