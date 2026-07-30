"""MoMA entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from .ui.main_window import MainWindow
from .ui.theme import apply_theme
from .core.settings import get_settings


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("MoMA")
    app.setApplicationDisplayName("Mo's Mindustry Mod Assistant")

    # 应用统一主题（读取用户设置，默认浅色），加载 QSS 样式表
    apply_theme(app, get_settings().get("theme", "light"))

    # Locate metadata directory
    metadata_dir = _find_metadata_dir()
    if metadata_dir is None:
        QMessageBox.critical(
            None,
            "启动失败",
            "未找到游戏元数据 (metadata/ 目录)。\n\n"
            "请确保 metadata/ 目录位于程序根目录，\n"
            "或从 GitHub Releases 下载。",
        )
        sys.exit(1)

    window = MainWindow(metadata_dir)
    window.show()
    sys.exit(app.exec())


def _find_metadata_dir() -> Path | None:
    """Search for metadata/ directory in likely locations."""
    candidates = [
        Path(__file__).parent.parent / "metadata",  # project root
        Path.cwd() / "metadata",
        Path(sys.argv[0]).parent / "metadata",
    ]
    for candidate in candidates:
        if (candidate / "manifest.json").exists():
            return candidate
    return None


if __name__ == "__main__":
    main()
