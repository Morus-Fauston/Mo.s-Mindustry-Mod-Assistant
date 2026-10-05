"""Windows WebView2 entry point; no Qt dependency in this process."""

from __future__ import annotations

import argparse
import ctypes
import logging
import subprocess
from threading import Event

from app.core.paths import data_dir, metadata_dir, ensure_user_config_dir
from app.desktop.api import DesktopApi
from app.desktop.close import WindowCloseGuard


def _require_webview2() -> None:
    # The pinned pywebview version silently falls back to MSHTML on Windows.
    from webview.guilib import initialize

    if initialize("edgechromium").renderer != "edgechromium":
        raise RuntimeError("未找到可用的 WebView2 Runtime，请安装微软官方 Evergreen 运行时后重试。")


def _watch_startup(window, finished: Event, failed: Event, timeout: float = 20) -> None:
    if not finished.wait(timeout):
        failed.set()
        logging.error("WebView2 did not load the application within %s seconds", timeout)
        window.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="MoMA Web 桌面程序")
    parser.add_argument("--debug", action="store_true", help="启用开发诊断（发行运行勿用）")
    options = parser.parse_args()
    log_file = ensure_user_config_dir() / "desktop.log"
    logging.basicConfig(filename=log_file, encoding="utf-8", level=logging.INFO)
    page = data_dir() / "frontend" / "dist" / "index.html"
    try:
        if not page.is_file():
            raise RuntimeError("界面资源缺失。开发环境请先运行 npm.cmd --prefix frontend run build；发行包请重新解压。")
        import webview

        _require_webview2()
        def choose_directory():
            selected = window.create_file_dialog(webview.FileDialog.FOLDER)
            return selected[0] if selected else None

        def choose_sprite():
            selected = window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False,
                                                 file_types=('PNG 图片 (*.png)',))
            return selected[0] if selected else None

        def reveal_file(path):
            # Keep the switch outside Windows' quoting of paths containing spaces.
            subprocess.Popen(['explorer.exe', '/select,', str(path)], creationflags=subprocess.CREATE_NO_WINDOW)

        def choose_export(default_filename):
            selected = window.create_file_dialog(webview.FileDialog.SAVE, save_filename=default_filename,
                                                 file_types=('ZIP 压缩包 (*.zip)',))
            return selected[0] if isinstance(selected, (tuple, list)) and selected else selected or None

        api = DesktopApi(metadata_dir(), choose_directory,
                         on_close=lambda: guard.approve(), on_close_ready=lambda: guard.ready(),
                         choose_sprite=choose_sprite, choose_export=choose_export, reveal_file=reveal_file)
        webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
        window = webview.create_window(
            "MoMA 模组助手", str(page), js_api=api,
            width=1400, height=900, min_size=(1024, 640),
            background_color="#f5f6f7", text_select=True,
        )
        guard = WindowCloseGuard(
            lambda: window.evaluate_js("window.dispatchEvent(new Event('moma-close-request'))"),
            window.destroy,
        )
        window.events.closing += guard.on_closing
        finished, failed = Event(), Event()
        window.events.loaded += finished.set
        window.events.closed += finished.set
        # Window focus is not visibility: a background but visible workbench
        # may continue animating. Minimize/restore explicitly suspend its clock.
        def report_hidden(hidden):
            value = "true" if hidden else "false"
            window.evaluate_js(f"window.__momaWindowHidden={value};window.dispatchEvent(new CustomEvent('moma-window-hidden',{{detail:{value}}}))")

        window.events.minimized += lambda: report_hidden(True)
        window.events.restored += lambda: report_hidden(False)
        window.events.maximized += lambda: report_hidden(False)
        webview.start(func=lambda: _watch_startup(window, finished, failed),
                      gui="edgechromium", debug=options.debug, http_server=True)
        if failed.is_set():
            raise RuntimeError("WebView2 初始化超时，未能加载界面。请检查运行时和程序文件后重试。")
    except Exception as exc:
        logging.exception("Desktop startup failed")
        message = str(exc) if isinstance(exc, RuntimeError) else (
            "无法启动桌面界面。请确认已安装 Microsoft Edge WebView2 Runtime，"
            "且程序文件完整。离线环境可使用微软官方的 Evergreen 独立安装程序。"
        )
        ctypes.windll.user32.MessageBoxW(None, f"{message}\n\n诊断记录：{log_file}", "MoMA 启动失败", 0x10)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
