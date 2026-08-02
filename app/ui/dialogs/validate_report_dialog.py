"""项目级全量验证报告对话框（F-51）。

工具 → 全量验证 → 弹窗列出所有问题（严重度/文件/消息）。
点击问题行跳转到对应 content 标签页（复用主窗口跳转机制）。
无问题时显示成功提示。

交互契约（供 main_window 使用）：
    ValidateReportDialog.show_report(issues, jump_to) 
        issues: list[Issue]（validate_project 输出）
        jump_to: callable(issue) -> bool — 点击行时调用，由 main_window
                 负责打开/切换到对应 content 标签页。返回是否成功。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class ValidateReportDialog(QDialog):
    """全量验证报告：错误/警告表格 + 点击跳转。"""

    def __init__(self, issues, jump_to=None, parent=None) -> None:
        super().__init__(parent)
        self._issues = issues
        self._jump_to = jump_to
        self.setWindowTitle("全量验证")
        self.setMinimumSize(680, 420)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        errors = sum(1 for i in self._issues if i.severity == "error")
        warnings = len(self._issues) - errors

        if not self._issues:
            title = QLabel("✓ 未发现问题")
            title.setObjectName("validateOkTitle")
            layout.addWidget(title)
            ok_btn = QPushButton("关闭")
            ok_btn.clicked.connect(self.accept)
            layout.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignRight)
            return

        summary = QLabel(
            f"发现 {errors} 个错误，{warnings} 个警告（点击行跳转到对应内容）"
        )
        summary.setObjectName("validateSummary")
        layout.addWidget(summary)

        self._table = QTableWidget(len(self._issues), 3)
        self._table.setHorizontalHeaderLabels(["严重度", "文件", "消息"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        for row, issue in enumerate(self._issues):
            sev_item = QTableWidgetItem("错误" if issue.severity == "error" else "警告")
            sev_item.setData(Qt.ItemDataRole.UserRole, issue.severity)
            sev_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if issue.severity == "error":
                sev_item.setForeground(Qt.GlobalColor.red)
            else:
                sev_item.setForeground(Qt.GlobalColor.darkYellow)

            file_item = QTableWidgetItem(issue.path)
            msg_item = QTableWidgetItem(issue.message)

            self._table.setItem(row, 0, sev_item)
            self._table.setItem(row, 1, file_item)
            self._table.setItem(row, 2, msg_item)
            # 存 issue 引用供跳转
            msg_item.setData(Qt.ItemDataRole.UserRole + 1, row)

        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)
        self._table.cellClicked.connect(self._on_row_clicked)
        layout.addWidget(self._table, stretch=1)

        # 底部按钮
        btns = QHBoxLayout()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btns.addStretch(1)
        btns.addWidget(close_btn)
        layout.addLayout(btns)

    def _on_row_clicked(self, row: int, _col: int) -> None:
        self._jump_to_issue(row)

    def _on_row_double_clicked(self, row: int, _col: int) -> None:
        self._jump_to_issue(row)

    def _jump_to_issue(self, row: int) -> None:
        if not (0 <= row < len(self._issues)):
            return
        issue = self._issues[row]
        if self._jump_to is not None:
            self._jump_to(issue)
