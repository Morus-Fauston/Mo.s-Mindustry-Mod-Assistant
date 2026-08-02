"""主题管理器：颜色令牌 + QSS 模板加载 + 深浅色即时切换。

设计定稿（见 Docs/v021-风格规划.html）：
- 浅色 VS Code 气质，中性灰做结构，马卡龙做字段类型编码，铜橙只做状态栏与焦点态。
- QSS 不支持 CSS 变量，用 @TOKEN@ 占位符 + Python 替换生成最终样式表。
- 字段类型着色通过控件的动态属性 fieldType 走 QSS 属性选择器（见 style_*.qss）。

用法：
    from app.ui.theme import apply_theme, get_tokens, field_type_property
    apply_theme(app, "light")

注意：app/core 不 import Qt，本模块属于 app/ui。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

_RESOURCES = Path(__file__).parent.parent / "resources"

# ── 颜色令牌 ──────────────────────────────────────────────────────────────
# 键名与 QSS 中的 @TOKEN@ 占位符一一对应。

LIGHT: dict[str, str] = {
    # 中性层（结构）
    "CANVAS": "#FFFFFF",
    "PANEL": "#F5F6F7",
    "PANEL2": "#ECEEF0",
    "INK": "#2B2E33",
    "INK2": "#6B7280",
    "LINE": "#E3E6EA",
    # 铜橙与状态
    "COPPER": "#E08A3C",
    "COPPER_DEEP": "#C4702A",
    "COPPER_TINT": "#FDF1E5",
    "ERR": "#D64545",
    "ERR_BG": "#FDECEC",
    "SB_BG": "#C4702A",
    "SB_INK": "#FFF6EC",
    "VIEWPORT": "#171827",
    "GROUP_HEAD": "#F5F5F5",
    # 字段类型（淡底 / 描边 / 色条）
    "F_NUM": "#F4FAFE", "S_NUM": "#BFDFF5", "B_NUM": "#A6D3F2",
    "F_BOOL": "#F4FBF4", "S_BOOL": "#C0E6C4", "B_BOOL": "#A8DCAD",
    "F_STR": "#FFFBF2", "S_STR": "#F8DFB0", "B_STR": "#F6D396",
    "F_REF": "#FAF4FB", "S_REF": "#E0C0E8", "B_REF": "#D3A6DE",
    "F_COL": "#FEF4F8", "S_COL": "#F7C9D8", "B_COL": "#F4B1C9",
    "F_ARR": "#F1FBFD", "S_ARR": "#B5E5ED", "B_ARR": "#97DBE6",
    "F_OBJ": "#FFFDF2", "S_OBJ": "#F2E7A6", "B_OBJ": "#EDDD82",
    # 模式徽章
    "BADGE_REF_BG": "#E4F3E7", "BADGE_REF_FG": "#2E7D43",
    "BADGE_INL_BG": "#E3EDF9", "BADGE_INL_FG": "#2F6FB2",
    # 参考对比差异行
    "DIFF_BG": "#FFF3CD", "DIFF_FG": "#8A6D1F",
    # 选中态（文件树 + 设置列表共用）
    "SEL_BG": "#DCE4F0",
    "SEL_FOCUS": "#9FB3CF",
}

DARK: dict[str, str] = {
    "CANVAS": "#1E1F22",
    "PANEL": "#26272B",
    "PANEL2": "#2D2F34",
    "INK": "#D6D7DA",
    "INK2": "#8B8E94",
    "LINE": "#3A3C42",
    "COPPER": "#E8A05C",
    "COPPER_DEEP": "#8F5A1F",
    "COPPER_TINT": "#3A2E1E",
    "ERR": "#E06666",
    "ERR_BG": "#3E2226",
    "SB_BG": "#8F5A1F",
    "SB_INK": "#F5E9DC",
    "VIEWPORT": "#10111A",
    "GROUP_HEAD": "#2B2D31",
    "F_NUM": "#1A2D3C", "S_NUM": "#3A5F80", "B_NUM": "#5B8FB8",
    "F_BOOL": "#1A2E21", "S_BOOL": "#3D6B4C", "B_BOOL": "#63A877",
    "F_STR": "#33291A", "S_STR": "#7A6038", "B_STR": "#B8935E",
    "F_REF": "#2C1F31", "S_REF": "#66476E", "B_REF": "#A070AA",
    "F_COL": "#331D24", "S_COL": "#77455A", "B_COL": "#B86E8A",
    "F_ARR": "#163035", "S_ARR": "#3A6A74", "B_ARR": "#5CA3B0",
    "F_OBJ": "#302D17", "S_OBJ": "#6F6838", "B_OBJ": "#B0A65C",
    "BADGE_REF_BG": "#1E3527", "BADGE_REF_FG": "#7FC896",
    "BADGE_INL_BG": "#1D2C3D", "BADGE_INL_FG": "#7EB0E8",
    # 参考对比差异行（深色降明度保色相）
    "DIFF_BG": "#3D3520", "DIFF_FG": "#D9B45B",
    # 选中态（文件树 + 设置列表共用）
    "SEL_BG": "#2D3139",
    "SEL_FOCUS": "#4A6DA0",
}

_THEMES: dict[str, dict[str, str]] = {"light": LIGHT, "dark": DARK}

_current_theme: str = "light"


def get_tokens(theme: str | None = None) -> dict[str, str]:
    """返回指定主题（默认当前主题）的颜色令牌字典。"""
    return _THEMES.get(theme or _current_theme, LIGHT)


def get_current_theme() -> str:
    return _current_theme


def load_qss(theme: str | None = None) -> str:
    """加载单一 QSS 模板并用对应主题的令牌替换 @TOKEN@ 占位符。

    深浅色共用同一份模板（style.qss），差异全部体现在令牌字典里，避免维护两份重复样式表。
    """
    theme = theme or _current_theme
    qss_path = _RESOURCES / "style.qss"
    if not qss_path.exists():
        return ""
    template = qss_path.read_text(encoding="utf-8")
    tokens = get_tokens(theme)
    for key, value in tokens.items():
        template = template.replace(f"@{key}@", value)
    # 树复选框勾图标：QSS 的 url() 相对路径基于进程 cwd 不可靠，且不接受
    # file:// 协议（会被当相对路径拼到 cwd 前），故用绝对盘符路径
    # （as_posix）替换 @CHECK_ICON@（v0.2.5 图层树渲染修复）。
    check_icon = _RESOURCES / "icons" / "check_copper.svg"
    if check_icon.exists():
        template = template.replace("@CHECK_ICON@", f"url({check_icon.as_posix()})")
    # 下拉箭头图标：@ARROW_ICON@（v0.2.5 修复——border transparent 三角在
    # windows11 editable QComboBox 上渲染成黑块矩形）。
    arrow_icon = _RESOURCES / "icons" / "arrow_down.svg"
    if arrow_icon.exists():
        template = template.replace("@ARROW_ICON@", f"url({arrow_icon.as_posix()})")
    return template


def apply_theme(app: "QApplication", theme: str | None = None) -> None:
    """把主题应用到 QApplication，即时生效（无需重启）。

    会刷新所有顶层窗口的样式，确保已创建的控件重绘。
    """
    global _current_theme
    theme = theme or _current_theme
    if theme not in _THEMES:
        theme = "light"
    _current_theme = theme

    app.setStyleSheet(load_qss(theme))
    # 强制刷新已实例化控件的样式
    for widget in app.topLevelWidgets():
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()


# ── 字段类型动态属性 ──────────────────────────────────────────────────────
# QSS 用属性选择器 *[fieldType="num"] 命中。编辑面板创建控件后调用此函数，
# 再 unpolish/polish 一次即可让 QSS 生效。

# 字段 mode/java_type → fieldType 值的映射
FIELD_TYPE_VALUES = ("num", "bool", "str", "ref", "col", "arr", "obj")


def field_type_property(field_mode: str, java_type: str) -> str:
    """根据字段元数据推断 fieldType 属性值（供 QSS 属性选择器使用）。"""
    if field_mode == "ARRAY":
        return "arr"
    if field_mode == "INLINE_OBJECT":
        return "obj"
    if field_mode == "STRING_REF":
        return "ref"
    # PRIMITIVE
    if java_type == "boolean":
        return "bool"
    if java_type in ("int", "long", "short", "float", "double"):
        return "num"
    if java_type == "Color":
        return "col"
    return "str"
