"""字段标签富文本辅助：中文正常 + 英文淡化缩小等宽。

对齐设计稿 HTML 的 .row label em 样式。
颜色从 theme 令牌读取，深浅自适应。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from ..theme import get_tokens


def rich_label(zh: str, en: str, parent=None) -> QLabel:  # noqa: ANN001
    """返回一个富文本 QLabel：中文正常 + 英文淡化缩小等宽。

    如果 zh 为空或等于 en，则只显示 en（纯文本，无 span）。
    """
    label = QLabel(parent)
    if zh and zh != en:
        t = get_tokens()
        ink2 = t.get("INK2", "#6B7280")
        html = (
            f'{zh} <span style="color:{ink2};font-size:11.5px;'
            f'font-family:\'JetBrains Mono\',Consolas,monospace">{en}</span>'
        )
        label.setText(html)
        label.setTextFormat(Qt.TextFormat.RichText)
    else:
        label.setText(en or zh or "")
    return label
