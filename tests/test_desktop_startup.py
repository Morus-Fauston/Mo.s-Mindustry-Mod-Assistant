"""Startup failure feedback without opening a blocking native message box."""

import ctypes
import sys
from threading import Event
from types import SimpleNamespace

import pytest

from app.desktop import main as desktop_main


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
