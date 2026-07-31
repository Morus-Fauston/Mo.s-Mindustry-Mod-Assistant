"""字段标签富文本辅助：中文正常 + 英文淡化缩小等宽 + 截断。

v0.2.4.batch2：固定列宽 180px，中文始终完整，英文超长时截断加 …。
tooltip 补英文字段名（调用方追加）。
颜色从 theme 令牌读取，深浅自适应。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QLabel

from ..theme import get_tokens

# 固定列宽（v0.2.4.batch2：150→180px，给中文+英文更多空间）
LABEL_WIDTH = 180


def rich_label(zh: str, en: str, parent=None) -> QLabel:  # noqa: ANN001
    """返回一个富文本 QLabel：中文正常 + 英文淡化缩小等宽。

    如果 zh 为空或等于 en，则只显示 en（纯文本，无 span）。
    英文超长时截断加 …（中文始终完整）。
    """
    label = QLabel(parent)
    if zh and zh != en:
        t = get_tokens()
        ink2 = t.get("INK2", "#6B7280")

        # 计算中文占用的像素宽度，剩余空间给英文
        zh_font = QFont()
        zh_font.setPixelSize(14)
        zh_fm = QFontMetrics(zh_font)
        zh_width = zh_fm.horizontalAdvance(zh)

        en_font = QFont("JetBrains Mono")
        en_font.setPixelSize(12)
        en_fm = QFontMetrics(en_font)
        # 可用宽度 = 总宽 - 中文宽 - 空格间距(约4px)
        en_available = max(LABEL_WIDTH - zh_width - 6, 20)
        en_display = en_fm.elidedText(en, Qt.TextElideMode.ElideRight, en_available)

        html = (
            f'<span style="font-size:14px">{zh}</span> '
            f'<span style="color:{ink2};font-size:12px;'
            f'font-family:\'JetBrains Mono\',Consolas,monospace">{en_display}</span>'
        )
        label.setText(html)
        label.setTextFormat(Qt.TextFormat.RichText)
        # tooltip 补完整英文名（调用方可追加 field_docs）
        label.setProperty("_en_name", en)
    else:
        label.setText(en or zh or "")
        label.setProperty("_en_name", en or zh or "")
    return label
