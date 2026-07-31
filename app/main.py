"""MoMA entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from PySide6.QtCore import QLibraryInfo, QTranslator

from .ui.main_window import MainWindow
from .ui.theme import apply_theme
from .core.settings import get_settings


def _install_qt_translations(app: QApplication) -> None:
    """Load Qt's built-in Chinese translations so all built-in dialogs
    (QDialogButtonBox, QInputDialog, QMessageBox, QFileDialog) show
    Chinese button text instead of English OK/Cancel."""
    translator = QTranslator(app)
    # Try PySide6 translations directory first
    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load("qtbase_zh_CN", translations_path):
        app.installTranslator(translator)
        return
    # Fallback: try common PySide6 install locations
    import PySide6
    ps6_dir = Path(PySide6.__file__).parent / "translations"
    if translator.load("qtbase_zh_CN", str(ps6_dir)):
        app.installTranslator(translator)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("MoMA")
    app.setApplicationDisplayName("Mo's Mindustry Mod Assistant")

    # Qt built-in Chinese translations (OK→确定, Cancel→取消, etc.)
    _install_qt_translations(app)

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
