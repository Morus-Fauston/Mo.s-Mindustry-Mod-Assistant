"""欢迎页：无打开工程时显示在编辑区中央。

设计定稿（见 Docs/v021-风格规划.html）：
- MiSans 700 品牌大字，两行错落，第二行缩进染铜橙
- 等宽副标题
- 理念小字
- 实心铜橙「新建工程」+ 描边「打开工程」两按钮
- 底部「上次打开」快速恢复提示

objectName 与 QSS 中的 #welcomePage / #welcomeBrand 等选择器对应。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class WelcomePage(QWidget):
    """编辑区空态：品牌时刻 + 打开/新建入口。"""

    new_project_requested = Signal()
    open_project_requested = Signal()
    restore_requested = Signal(str)  # 上次打开的路径

    def __init__(self, last_project: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("welcomePage")
        self._last_project = last_project
        self._setup_ui()

    def set_last_project(self, path: str | None) -> None:
        """更新「上次打开」提示。"""
        self._last_project = path
        self._update_hint()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.addStretch(1)

        # 居中容器
        center = QVBoxLayout()
        center.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # 品牌大字（两行错落）
        brand = QLabel("Mo's Mindustry")
        brand.setObjectName("welcomeBrand")
        brand.setAlignment(Qt.AlignmentFlag.AlignLeft)
        brand2 = QLabel("Mod Assistant")
        brand2.setObjectName("welcomeBrandAccent")
        brand2.setAlignment(Qt.AlignmentFlag.AlignLeft)
        brand2.setContentsMargins(54, 0, 0, 0)  # 错落缩进
        center.addWidget(brand)
        center.addWidget(brand2)

        # 等宽副标题
        sub = QLabel("MINDUSTRY MOD EDITOR")
        sub.setObjectName("welcomeSub")
        sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sub.setContentsMargins(0, 16, 0, 0)
        center.addWidget(sub)

        # 理念
        phi = QLabel(
            "为中文 Mindustry mod 社区打造的可视化编辑器。\n"
            "不写一行 JSON，也能调出想要的单位、方块与武器。"
        )
        phi.setObjectName("welcomePhi")
        phi.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        phi.setContentsMargins(0, 22, 0, 30)
        center.addWidget(phi)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        btn_row.setSpacing(12)

        new_btn = QPushButton("新建工程")
        new_btn.setProperty("class", "primary")
        new_btn.setFixedSize(158, 52)
        new_btn.setToolTip("从零开始一个 mod")
        new_btn.clicked.connect(self.new_project_requested.emit)

        open_btn = QPushButton("打开工程")
        open_btn.setFixedSize(158, 52)
        open_btn.setToolTip("选择已有 mod 目录")
        open_btn.clicked.connect(self.open_project_requested.emit)

        btn_row.addWidget(new_btn)
        btn_row.addWidget(open_btn)
        center.addLayout(btn_row)

        # 上次打开提示
        self._hint = QLabel()
        self._hint.setObjectName("welcomeHint")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._hint.setContentsMargins(0, 24, 0, 0)
        self._update_hint()
        center.addWidget(self._hint)

        root.addLayout(center)
        root.addStretch(1)

    def _update_hint(self) -> None:
        if self._last_project:
            # 只显示目录名，完整路径放 tooltip
            from pathlib import Path
            name = Path(self._last_project).name or self._last_project
            self._hint.setText(f"上次打开：{name} · 点击快速恢复")
            self._hint.setToolTip(self._last_project)
            self._hint.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self._hint.setText("尚未打开过工程")
            self._hint.setToolTip("")
            self._hint.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """点击「上次打开」提示时恢复工程。"""
        if self._last_project and self._hint.geometry().contains(event.pos()):
            self.restore_requested.emit(self._last_project)
        super().mousePressEvent(event)
