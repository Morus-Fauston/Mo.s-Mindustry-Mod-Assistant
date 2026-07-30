"""Nieobie SVG 图标加载器：染色 + QIcon 缓存。

设计定稿：
- 工具栏/菜单图标默认深灰 #424242（深色主题浅灰），hover 由控件自行染色。
- 文件树分类图标染各分类主题色：units 蓝 / blocks 铜橙 / weapons 红。

SVG 染色用 QPainter + CompositionMode_SourceIn 实现，结果按 (路径, 颜色) 缓存，
避免重复 IO 与重绘。

用法：
    from app.ui.icon_loader import icon, FileTreeIcon
    btn.setIcon(icon("1.UI/save.svg"))
    item.setIcon(0, FileTreeIcon.units())
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap

# Nieobie icons 位于项目根目录（已 gitignore，随仓库分发）
_ICON_ROOT = Path(__file__).resolve().parents[2] / "Nieobie icons"

# 图标默认色（工具栏/菜单中性灰）
DEFAULT_LIGHT = "#424242"
DEFAULT_DARK = "#B9BDC4"

# 分类主题色
CATEGORY_COLORS = {
    "units": "#4A90D9",
    "blocks": "#E08A3C",
    "weapons": "#C0504D",
}

# 缓存：(相对路径, 颜色, 尺寸) → QIcon
_cache: dict[tuple[str, str, int], QIcon] = {}


def _resolve(rel_path: str) -> Path | None:
    """把 '1.UI/save.svg' 解析为绝对路径，找不到返回 None。"""
    p = _ICON_ROOT / rel_path
    return p if p.exists() else None


def _tinted_pixmap(svg_path: Path, color: str, size: int) -> QPixmap:
    """读取 SVG，染成指定颜色，返回 size×size 的 QPixmap。"""
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(str(svg_path))
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, size, size))
    # 用 SourceIn 把已绘制的不透明像素染成目标色
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(image.rect(), QColor(color))
    painter.end()

    return QPixmap.fromImage(image)


def icon(rel_path: str, color: str | None = None, size: int = 18) -> QIcon:
    """加载并染色一个 Nieobie 图标，返回 QIcon（带缓存）。

    Args:
        rel_path: 相对 Nieobie icons 根目录的路径，如 "1.UI/save.svg"。
        color: 染色十六进制色值；None 用默认深灰。
        size: 渲染像素尺寸。

    找不到文件时返回空 QIcon（不抛异常，保证 UI 不崩）。
    """
    color = color or DEFAULT_LIGHT
    key = (rel_path, color, size)
    if key in _cache:
        return _cache[key]

    svg_path = _resolve(rel_path)
    if svg_path is None:
        return QIcon()

    qicon = QIcon(_tinted_pixmap(svg_path, color, size))
    _cache[key] = qicon
    return qicon


def clear_cache() -> None:
    """清空图标缓存（主题切换换默认色时可调用）。"""
    _cache.clear()


class FileTreeIcon:
    """文件树分类图标的便捷入口。"""

    @staticmethod
    def units(size: int = 16) -> QIcon:
        return icon("5.Game/character.svg", CATEGORY_COLORS["units"], size)

    @staticmethod
    def blocks(size: int = 16) -> QIcon:
        return icon("5.Game/tower.svg", CATEGORY_COLORS["blocks"], size)

    @staticmethod
    def weapons(size: int = 16) -> QIcon:
        return icon("6.Items/sword.svg", CATEGORY_COLORS["weapons"], size)


class ToolbarIcon:
    """工具栏常用图标的便捷入口（默认深灰）。"""

    SAVE = "1.UI/save.svg"
    SETTINGS = "1.UI/settings.svg"
    UNDO = "3.Editing Tools/undo.svg"
    REDO = "3.Editing Tools/redo.svg"
    SEARCH = "1.UI/search.svg"
    REFRESH = "1.UI/refresh.svg"
    ZOOM_IN = "1.UI/zoom-in.svg"
    ZOOM_OUT = "1.UI/zoom-out.svg"
    INFO = "1.UI/info.svg"
    LOCK = "1.UI/lock.svg"
    UNLOCK = "1.UI/unlock.svg"
    ADD = "1.UI/menu-add.svg"
    CROSS = "1.UI/cross.svg"
    TICK = "1.UI/tick.svg"
    # 新建内容
    NEW_UNIT = "5.Game/character.svg"
    NEW_BLOCK = "5.Game/tower.svg"
    NEW_WEAPON = "6.Items/sword.svg"

    @staticmethod
    def get(rel_path: str, color: str | None = None, size: int = 18) -> QIcon:
        return icon(rel_path, color, size)
