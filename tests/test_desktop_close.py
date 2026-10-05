"""Native-close handshake without running a GUI message pump."""

from app.desktop.close import WindowCloseGuard


def test_close_cancels_before_javascript_and_only_approval_allows_destroy():
    queued, notified, destroyed = [], [], []
    guard = WindowCloseGuard(lambda: notified.append('close'), lambda: destroyed.append(True), queued.append)
    guard.ready()
    assert guard.on_closing() is False
    assert notified == []
    assert destroyed == []
    queued.pop()()
    assert notified == ['close']
    guard.approve()
    queued.pop()()
    assert destroyed == [True]
    assert guard.on_closing() is True


def test_unloaded_page_can_close_and_notification_failure_allows_another_attempt():
    queued = []
    def fail():
        raise RuntimeError('page not available')
    guard = WindowCloseGuard(fail, lambda: None, queued.append)
    assert guard.on_closing() is True
    guard.ready()
    assert guard.on_closing() is False
    queued.pop()()
    assert guard.on_closing() is False
    assert len(queued) == 1
