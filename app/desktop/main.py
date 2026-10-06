"""Windows WebView2 entry point; no Qt dependency in this process."""

from __future__ import annotations

import argparse
import ctypes
import logging
import os
import subprocess
import sys
from threading import Event

from app.core.paths import data_dir, metadata_dir, ensure_user_config_dir
from app.desktop.api import DesktopApi
from app.desktop.close import WindowCloseGuard

WEBVIEW2_DOWNLOAD_URL = "https://developer.microsoft.com/microsoft-edge/webview2#download-the-webview2-runtime"
WEBVIEW2_OFFLINE_HELP = (
    "请在联网电脑打开微软官方页面：\n"
    f"{WEBVIEW2_DOWNLOAD_URL}\n"
    "选择与目标电脑架构对应的 Evergreen Standalone Installer（独立安装程序），"
    "将安装文件带到离线电脑手动安装，再重新启动本程序。"
)


class _StartupError(RuntimeError):
    """A startup error with actionable Chinese feedback for the user."""


def _require_webview2() -> None:
    # The pinned pywebview version silently falls back to MSHTML on Windows.
    from webview.guilib import initialize

    try:
        renderer = initialize("edgechromium").renderer
    except Exception as exc:
        raise _StartupError(f"无法初始化 WebView2 Runtime。\n{WEBVIEW2_OFFLINE_HELP}") from exc
    if renderer != "edgechromium":
        raise _StartupError(f"未找到可用的 WebView2 Runtime。\n{WEBVIEW2_OFFLINE_HELP}")


def _watch_startup(window, finished: Event, failed: Event, timeout: float = 20) -> None:
    if not finished.wait(timeout):
        failed.set()
        logging.error("WebView2 did not load the application within %s seconds", timeout)
        window.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="MoMA Web 桌面程序")
    parser.add_argument("--debug", action="store_true", help="启用开发诊断（发行运行勿用）")
    options = parser.parse_args()
    log_file = None
    log_handler = None
    window = None
    root_logger = logging.getLogger()
    previous_level = root_logger.level
    try:
        log_file = ensure_user_config_dir() / "desktop.log"
        log_handler = logging.FileHandler(log_file, encoding="utf-8")
        log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root_logger.addHandler(log_handler)
        root_logger.setLevel(logging.INFO)
        frozen = bool(getattr(sys, "frozen", False))
        if frozen:
            if options.debug:
                raise _StartupError("发行版已关闭开发调试。请移除 --debug 参数后重新启动；开发调试请使用源码环境。")
            arguments = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "").lower()
            if "--remote-debugging-" in arguments or "--auto-open-devtools-for-tabs" in arguments:
                raise _StartupError(
                    "发行版已关闭远程调试。请移除 WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS "
                    "环境变量中的远程调试或开发工具参数，再重新启动。"
                )
        page = data_dir() / "frontend" / "dist" / "index.html"
        if not page.is_file():
            raise _StartupError("界面资源缺失。发行包请重新解压；源码开发环境请先构建前端资源。")
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

        def choose_reference_zip():
            selected = window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False,
                                                 file_types=('ZIP 压缩包 (*.zip)',))
            return selected[0] if selected else None

        def choose_export(default_filename):
            selected = window.create_file_dialog(webview.FileDialog.SAVE, save_filename=default_filename,
                                                 file_types=('ZIP 压缩包 (*.zip)',))
            return selected[0] if isinstance(selected, (tuple, list)) and selected else selected or None

        api = DesktopApi(metadata_dir(), choose_directory,
                         on_close=lambda: guard.approve(), on_close_ready=lambda: guard.ready(),
                         choose_sprite=choose_sprite, choose_export=choose_export, reveal_file=reveal_file,
                         choose_reference_zip=choose_reference_zip)
        webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
        if frozen:
            webview.settings["REMOTE_DEBUGGING_PORT"] = None
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
            raise _StartupError("WebView2 初始化超时，未能加载界面。请检查运行时和程序文件后重试。")
    except Exception as exc:
        logging.exception("Desktop startup failed")
        if window is not None:
            try:
                window.destroy()
            except Exception:
                logging.exception("Could not destroy failed startup window")
        if log_handler is None:
            message = "无法写入程序配置目录或启动日志。请检查当前用户目录的访问权限后重新启动。"
            diagnostic = "诊断日志无法写入。"
        else:
            message = str(exc) if isinstance(exc, _StartupError) else (
                "无法启动桌面界面。请确认程序文件完整，且已安装 Microsoft Edge WebView2 Runtime。\n"
                + WEBVIEW2_OFFLINE_HELP
            )
            diagnostic = f"诊断记录：{log_file}"
        try:
            ctypes.windll.user32.MessageBoxW(None, f"{message}\n\n{diagnostic}", "MoMA 启动失败", 0x10)
        except Exception:
            logging.exception("Could not display startup failure feedback")
        raise SystemExit(1) from exc
    finally:
        if log_handler is not None:
            root_logger.removeHandler(log_handler)
            log_handler.close()
        root_logger.setLevel(previous_level)


if __name__ == "__main__":
    main()
