"""Startup failure feedback without opening a blocking native message box."""

import ctypes
import logging
import sys
from threading import Event
from types import SimpleNamespace

import pytest

from app.desktop import main as desktop_main

REQUIRE_WEBVIEW2 = desktop_main._require_webview2


@pytest.mark.parametrize("missing_page", [True, False])
def test_startup_failure_has_chinese_feedback_and_nonzero_exit(tmp_path, monkeypatch, missing_page):
    monkeypatch.setattr(desktop_main, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(desktop_main, "ensure_user_config_dir", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["run_web.py"])
    monkeypatch.setattr(desktop_main, "_require_webview2", lambda: None)
    messages = []
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(
        MessageBoxW=lambda _owner, message, title, _flags: messages.append((message, title))
    )), raising=False)
    calls = []

    def fail_runtime(**kwargs):
        calls.append(kwargs)
        raise ImportError("WebView2 missing")

    class NativeEvent:
        def __iadd__(self, callback):
            return self

    window = SimpleNamespace(events=SimpleNamespace(loaded=NativeEvent(), closed=NativeEvent(), closing=NativeEvent(),
                                                   minimized=NativeEvent(), restored=NativeEvent(), maximized=NativeEvent()),
                             destroy=lambda: None)
    monkeypatch.setitem(sys.modules, "webview", SimpleNamespace(
        settings={}, create_window=lambda *args, **kwargs: window, start=fail_runtime,
    ))
    if not missing_page:
        page = tmp_path / "frontend" / "dist" / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        desktop_main.main()
    assert error.value.code == 1
    assert len(messages) == 1
    assert messages[0][1] == "MoMA 启动失败"
    assert "诊断记录" in messages[0][0]
    assert ("界面资源缺失" if missing_page else "WebView2 Runtime") in messages[0][0]
    assert len(calls) == (0 if missing_page else 1)


@pytest.mark.parametrize("renderer", ["mshtml", "edgechromium"])
def test_backend_selection_rejects_silent_mshtml_fallback(monkeypatch, renderer):
    monkeypatch.setitem(sys.modules, "webview.guilib", SimpleNamespace(
        initialize=lambda requested: SimpleNamespace(renderer=renderer),
    ))
    if renderer == "mshtml":
        with pytest.raises(RuntimeError, match="WebView2 Runtime"):
            desktop_main._require_webview2()
    else:
        desktop_main._require_webview2()


@pytest.mark.parametrize("loaded_or_closed", [False, True])
def test_initialization_watchdog_closes_failed_window(loaded_or_closed):
    finished, failed = Event(), Event()
    closed = []
    if loaded_or_closed:
        finished.set()
    desktop_main._watch_startup(SimpleNamespace(destroy=lambda: closed.append(True)),
                                finished, failed, timeout=0)
    assert failed.is_set() is (not loaded_or_closed)
    assert bool(closed) is (not loaded_or_closed)


@pytest.fixture
def startup_host(tmp_path, monkeypatch):
    page = tmp_path / "frontend/dist/index.html"
    page.parent.mkdir(parents=True)
    page.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(desktop_main, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(desktop_main, "ensure_user_config_dir", lambda: tmp_path)
    monkeypatch.setattr(desktop_main, "metadata_dir", lambda: tmp_path / "metadata")
    monkeypatch.setattr(desktop_main, "_require_webview2", lambda: None)
    monkeypatch.setattr(desktop_main, "DesktopApi", lambda *args, **kwargs: object())
    monkeypatch.setattr(sys, "argv", ["run_web.py"])
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.delenv("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", raising=False)

    class NativeEvent:
        def __iadd__(self, callback):
            return self

    events = SimpleNamespace(**{name: NativeEvent() for name in (
        "loaded", "closed", "closing", "minimized", "restored", "maximized")})
    calls, destroyed, messages = [], [], []
    window = SimpleNamespace(events=events, destroy=lambda: destroyed.append(True))
    webview = SimpleNamespace(settings={"REMOTE_DEBUGGING_PORT": 9911},
                              create_window=lambda *args, **kwargs: window,
                              start=lambda **kwargs: calls.append(kwargs))
    monkeypatch.setitem(sys.modules, "webview", webview)
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(
        MessageBoxW=lambda _owner, message, title, _flags: messages.append((message, title))
    )), raising=False)
    return SimpleNamespace(webview=webview, calls=calls, destroyed=destroyed,
                           messages=messages, log=tmp_path / "desktop.log")


@pytest.mark.parametrize("frozen,debug", [(False, False), (False, True), (True, False)])
def test_release_disables_debug_while_development_can_opt_in(startup_host, monkeypatch, frozen, debug):
    monkeypatch.setattr(sys, "frozen", frozen)
    monkeypatch.setattr(sys, "argv", ["run_web.py"] + (["--debug"] if debug else []))
    desktop_main.main()
    assert startup_host.calls[0]["debug"] is debug
    assert startup_host.calls[0]["gui"] == "edgechromium"
    assert startup_host.webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] is False
    assert startup_host.webview.settings["REMOTE_DEBUGGING_PORT"] == (None if frozen else 9911)


@pytest.mark.parametrize("source", ["argument", "port", "pipe", "devtools"])
def test_frozen_debug_rejected_before_window_with_actionable_feedback(startup_host, monkeypatch, source):
    monkeypatch.setattr(sys, "frozen", True)
    if source == "argument":
        monkeypatch.setattr(sys, "argv", ["MoMA.exe", "--debug"])
    else:
        values = {"port": "--remote-debugging-port=9911", "pipe": "--remote-debugging-pipe",
                  "devtools": "--auto-open-devtools-for-tabs"}
        monkeypatch.setenv("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", values[source])
    with pytest.raises(SystemExit) as error:
        desktop_main.main()
    assert error.value.code == 1
    assert startup_host.calls == []
    assert "发行版" in startup_host.messages[0][0]
    assert "调试" in startup_host.messages[0][0]
    assert "重新启动" in startup_host.messages[0][0]
    assert "未找到可用" not in startup_host.messages[0][0]
    assert "Desktop startup failed" in startup_host.log.read_text(encoding="utf-8")


def test_frozen_harmless_runtime_arguments_do_not_prevent_startup(startup_host, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True)
    monkeypatch.setenv("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--disable-gpu")
    desktop_main.main()
    assert len(startup_host.calls) == 1


def test_missing_runtime_includes_official_offline_install_instructions(startup_host, monkeypatch):
    # Use the real renderer requirement, with only backend selection replaced.
    monkeypatch.setitem(sys.modules, "webview.guilib", SimpleNamespace(
        initialize=lambda requested: SimpleNamespace(renderer="mshtml")))
    monkeypatch.setattr(desktop_main, "_require_webview2", REQUIRE_WEBVIEW2)
    with pytest.raises(SystemExit) as error:
        desktop_main.main()
    assert error.value.code == 1
    text = startup_host.messages[0][0]
    assert "https://developer.microsoft.com/microsoft-edge/webview2" in text
    assert "Evergreen Standalone Installer" in text
    assert "离线" in text and "联网" in text
    assert startup_host.calls == []


@pytest.mark.parametrize("failure", ["directory", "log-file"])
def test_unwritable_logging_still_reports_chinese_and_exits(startup_host, monkeypatch, failure):
    def denied(*args, **kwargs):
        raise PermissionError("permission denied")
    if failure == "directory":
        monkeypatch.setattr(desktop_main, "ensure_user_config_dir", denied)
    else:
        monkeypatch.setattr(logging, "FileHandler", denied)
    with pytest.raises(SystemExit) as error:
        desktop_main.main()
    assert error.value.code == 1
    assert startup_host.calls == []
    assert "日志" in startup_host.messages[0][0]
    assert "无法写入" in startup_host.messages[0][0]


def test_partial_window_failure_is_destroyed_and_recorded(startup_host, monkeypatch):
    def broken(**kwargs):
        raise OSError("native creation failed")
    monkeypatch.setattr(startup_host.webview, "start", broken)
    with pytest.raises(SystemExit) as error:
        desktop_main.main()
    assert error.value.code == 1
    assert startup_host.destroyed == [True]
    assert "native creation failed" in startup_host.log.read_text(encoding="utf-8")


def test_message_box_failure_cannot_hide_nonzero_exit(startup_host, monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("native unavailable")
    monkeypatch.setattr(startup_host.webview, "start", broken)
    monkeypatch.setattr(ctypes.windll.user32, "MessageBoxW", broken)
    with pytest.raises(SystemExit) as error:
        desktop_main.main()
    assert error.value.code == 1
    assert startup_host.destroyed == [True]


@pytest.mark.parametrize("fails", [False, True])
def test_startup_log_handler_is_released_without_removing_existing_handlers(startup_host, monkeypatch, fails):
    logger = logging.getLogger()
    original_handlers, original_level = logger.handlers[:], logger.level
    if fails:
        monkeypatch.setattr(sys, "frozen", True)
        monkeypatch.setattr(sys, "argv", ["MoMA.exe", "--debug"])
        with pytest.raises(SystemExit):
            desktop_main.main()
    else:
        desktop_main.main()
    assert logger.handlers == original_handlers
    assert logger.level == original_level
    # Windows rejects unlink when a FileHandler still owns this file.
    startup_host.log.unlink()


def test_backend_initialization_exception_has_same_offline_guidance(monkeypatch):
    def broken(requested):
        raise ImportError("backend loader missing")
    monkeypatch.setitem(sys.modules, "webview.guilib", SimpleNamespace(initialize=broken))
    with pytest.raises(RuntimeError) as error:
        REQUIRE_WEBVIEW2()
    assert "WebView2 Runtime" in str(error.value)
    assert "Evergreen Standalone Installer" in str(error.value)
    assert isinstance(error.value.__cause__, ImportError)
