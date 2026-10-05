"""Real editing requests, session history, and disk round trips."""

import json
import ctypes
import sys
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from itertools import count

import pytest

from app.desktop.workspace import WorkspaceService


def make_project(root):
    root.mkdir()
    (root / "mod.json").write_text('{"name":"editing"}', encoding="utf-8")
    for category, health in (("units", 100), ("blocks", 500)):
        directory = root / "content" / category
        directory.mkdir(parents=True)
        (directory / "same.json").write_text(json.dumps({"type": "UnitType" if category == "units" else "Wall", "health": health}), encoding="utf-8")
    return root


class Client:
    def __init__(self, root, service=None):
        self.service = service or WorkspaceService("metadata")
        self.ids = count()
        self.sid = None
        opened = self.call("open_project", {"path": str(root)})
        assert opened["ok"], opened
        self.sid = opened["sessionId"]

    def call(self, action, payload=None, request_id=None):
        return self.service.request({"protocolVersion": 1, "sessionId": self.sid,
            "requestId": request_id or str(next(self.ids)), "action": action, "payload": payload or {}})

    def state(self):
        result = self.call("editing_state")
        assert result["ok"], result
        return result["data"]

    def mutate(self, action, **payload):
        return self.call(action, {"expectedRevision": self.state()["revision"], **payload})


def test_read_sent_before_close_cannot_reopen_a_document_after_close(tmp_path):
    client = Client(make_project(tmp_path / "project"))
    client.call('read_document', {'path': 'content/units/same.json'})
    revision = client.state()['revision']
    assert client.mutate('close_documents', paths=['content/units/same.json'], decision='discard')['ok']
    stale = client.call('read_document', {'path': 'content/blocks/same.json', 'expectedRevision': revision})
    assert stale['error']['code'] == 'STALE_REVISION'
    assert client.state()['documents'] == []


def test_real_health_edit_undo_redo_save_and_reopen(tmp_path):
    root = make_project(tmp_path / "project")
    client = Client(root)
    initial = client.call("read_document", {"path": "content/units/same.json"})["data"]
    assert initial["dirty"] is False
    edited = client.mutate("set_field", path=initial["path"], field="health", value=137)
    assert edited["ok"], edited
    state = edited["data"]
    assert state["documents"][0]["data"]["health"] == 137
    assert state["documents"][0]["dirty"] is True
    assert state["history"]["canUndo"] is True
    assert "生命" in state["history"]["undoDescription"]
    assert client.mutate("undo")["data"]["documents"][0]["data"]["health"] == 100
    assert client.state()["documents"][0]["dirty"] is False
    assert client.mutate("redo")["data"]["documents"][0]["data"]["health"] == 137
    assert client.mutate("save_opened")["data"]["documents"][0]["dirty"] is False
    disk = json.loads((root / initial["path"]).read_text(encoding="utf-8"))
    assert disk["health"] == 137
    fresh = Client(root)
    assert fresh.call("read_document", {"path": initial["path"]})["data"]["data"]["health"] == 137


def test_save_all_opened_content_and_closed_history_reopens_its_actual_document(tmp_path):
    root = make_project(tmp_path / "project")
    client = Client(root)
    unit, block = "content/units/same.json", "content/blocks/same.json"
    for path, health in ((unit, 137), (block, 823)):
        client.call("read_document", {"path": path})
        assert client.mutate("set_field", path=path, field="health", value=health)["ok"]
    saved = client.mutate("save_opened")
    assert all(not doc["dirty"] for doc in saved["data"]["documents"])
    assert json.loads((root / unit).read_text())["health"] == 137
    assert json.loads((root / block).read_text())["health"] == 823
    closed = client.mutate("close_documents", paths=[block], decision="discard")
    assert closed["ok"], closed
    assert [d["path"] for d in closed["data"]["documents"]] == [unit]
    undone = client.mutate("undo")["data"]
    docs = {d["path"]: d for d in undone["documents"]}
    assert docs[block]["data"]["health"] == 500
    assert docs[block]["dirty"] is True
    assert docs[unit]["data"]["health"] == 137


def test_cancel_and_discard_close_use_core_history_without_saving_closed_content(tmp_path):
    root = make_project(tmp_path / "project")
    client = Client(root)
    path = "content/units/same.json"
    client.call("read_document", {"path": path})
    client.mutate("set_field", path=path, field="health", value=137)
    before = client.state()
    assert client.mutate("close_documents", paths=[path], decision="cancel")["data"] == before
    closed = client.mutate("close_documents", paths=[path], decision="discard")
    assert closed["ok"], closed
    assert closed["data"]["documents"] == []
    assert client.mutate("save_opened")["ok"]
    assert json.loads((root / path).read_text())["health"] == 100
    restored = client.mutate("undo")["data"]["documents"][0]
    assert restored["data"]["health"] == 137 and restored["dirty"]


def test_switch_requires_current_discard_decision_and_failed_or_cancelled_open_keeps_edits(tmp_path):
    root = make_project(tmp_path / "project")
    next_root = make_project(tmp_path / "next")
    service = WorkspaceService("metadata", choose_directory=lambda: None)
    client = Client(root, service)
    path = "content/units/same.json"
    client.call("read_document", {"path": path})
    client.mutate("set_field", path=path, field="health", value=137)
    before = client.state()
    denied = client.call("open_project", {"path": str(next_root)})
    assert denied["error"]["code"] == "UNSAVED_CHANGES"
    stale = client.call("open_project", {"path": str(next_root), "discard": True, "expectedRevision": 0})
    assert stale["error"]["code"] == "STALE_REVISION"
    cancelled = client.mutate("choose_project", discard=True)
    assert cancelled["data"] == {"cancelled": True}
    assert client.state() == before
    assert not client.mutate("open_project", path=str(tmp_path / "missing"), discard=True)["ok"]
    assert client.state() == before
    opened = client.mutate("open_project", path=str(next_root), discard=True)
    assert opened["ok"], opened
    client.sid = opened["sessionId"]
    current = client.state()
    assert current["revision"] > before["revision"]
    assert current["documents"] == []
    assert current["history"]["canUndo"] is False
    assert json.loads((root / path).read_text())["health"] == 100


def test_native_close_validates_revision_then_freezes_session(tmp_path):
    root = make_project(tmp_path / "project")
    client = Client(root)
    path = "content/units/same.json"
    client.call("read_document", {"path": path})
    client.mutate("set_field", path=path, field="health", value=137)
    denied = client.call("close_window", {"decision": "discard", "expectedRevision": 0})
    assert denied["error"]["code"] == "STALE_REVISION"
    closed = client.mutate("close_window", decision="discard")
    assert closed["ok"] and closed["data"]["closeApproved"]
    assert json.loads((root / path).read_text())["health"] == 100
    assert client.mutate("set_field", path=path, field="health", value=145)["error"]["code"] == "WINDOW_CLOSING"
    assert client.call("open_project", {"path": str(root)})["error"]["code"] == "WINDOW_CLOSING"
    assert client.state()["documents"][0]["data"]["health"] == 137


def test_native_close_without_project_uses_null_session_and_initial_revision():
    service = WorkspaceService("metadata")
    state = service.request({"protocolVersion": 1, "requestId": "state", "sessionId": None, "action": "editing_state"})
    assert state["data"]["revision"] == 0 and state["data"]["sessionId"] is None
    result = service.request({"protocolVersion": 1, "requestId": "close", "sessionId": None,
        "action": "close_window", "payload": {"expectedRevision": 0, "decision": "discard"}})
    assert result["data"]["closeApproved"] is True


@contextmanager
def locked_file(path):
    if sys.platform != "win32":
        pytest.skip("真实共享锁验证仅适用于 Windows")
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 128, None)
    assert handle != ctypes.c_void_p(-1).value, ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        kernel.CloseHandle(handle)


def test_real_locked_second_file_preserves_partial_save_and_prevents_close(tmp_path):
    root = make_project(tmp_path / "project")
    client = Client(root)
    unit, block = "content/units/same.json", "content/blocks/same.json"
    for path in (unit, block):
        client.call("read_document", {"path": path})
        client.mutate("set_field", path=path, field="health", value=137)
    with locked_file(root / block):
        failed = client.mutate("close_documents", paths=[unit, block], decision="save")
        assert failed["error"]["code"] == "SAVE_FAILED"
        assert failed["error"]["path"] == block
        docs = {doc["path"]: doc for doc in client.state()["documents"]}
        assert len(docs) == 2
        assert docs[unit]["dirty"] is False
        assert docs[block]["dirty"] is True
        assert docs[block]["data"]["health"] == 137
        assert json.loads((root / unit).read_text())["health"] == 137
        assert json.loads((root / block).read_text())["health"] == 500
        assert not client.mutate("close_window", decision="save")["ok"]
        assert client.mutate("set_field", path=block, field="health", value=823)["ok"]
    saved = client.mutate("save_opened")
    assert saved["ok"]
    assert all(not doc["dirty"] for doc in saved["data"]["documents"])
    assert json.loads((root / block).read_text())["health"] == 823


def test_save_revalidates_replaced_category_symlink_and_preserves_dirty(tmp_path):
    root = make_project(tmp_path / "project")
    client = Client(root)
    path = "content/units/same.json"
    client.call("read_document", {"path": path})
    client.mutate("set_field", path=path, field="health", value=137)
    original = root / "content" / "units"
    moved = root / "content" / "units-old"
    original.rename(moved)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "same.json").write_text('{"health":999}', encoding="utf-8")
    try:
        original.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("当前权限不支持符号链接")
    failed = client.mutate("save_opened")
    assert failed["error"]["code"] == "SAVE_FAILED"
    assert client.state()["documents"][0]["dirty"] is True
    assert json.loads((outside / "same.json").read_text())["health"] == 999


def test_closed_clean_content_is_not_part_of_save_scope(tmp_path):
    root = make_project(tmp_path / "project")
    client = Client(root)
    path = "content/units/same.json"
    client.call("read_document", {"path": path})
    assert client.mutate("close_documents", paths=[path], decision="discard")["ok"]
    (root / path).write_text('{"health":900}', encoding="utf-8")
    assert client.mutate("save_opened")["ok"]
    assert json.loads((root / path).read_text())["health"] == 900


def test_repeated_mutation_and_stale_revision_do_not_execute_twice(tmp_path):
    root = make_project(tmp_path / "project")
    client = Client(root)
    path = "content/units/same.json"
    client.call("read_document", {"path": path})
    payload = {"path": path, "field": "health", "value": 137, "expectedRevision": client.state()["revision"]}
    first = client.call("set_field", payload, "once")
    assert first["ok"]
    assert client.call("set_field", payload, "once") == first
    stale = client.call("set_field", {**payload, "value": 155})
    assert stale["error"]["code"] == "STALE_REVISION"
    assert client.service.request_result("once")["response"] == first
    assert client.mutate("undo")["data"]["history"]["canUndo"] is False


@pytest.mark.parametrize("value", [True, "137", None, {}, -1, float("inf"), float("nan"), 10 ** 500])
def test_invalid_field_values_never_mutate_core(tmp_path, value):
    client = Client(make_project(tmp_path / "project"))
    path = "content/units/same.json"
    client.call("read_document", {"path": path})
    failed = client.mutate("set_field", path=path, field="health", value=value)
    assert not failed["ok"]
    assert client.state()["documents"][0]["data"]["health"] == 100
    assert client.state()["history"]["canUndo"] is False


def test_save_rejects_file_replaced_by_directory_instead_of_reporting_success(tmp_path):
    root = make_project(tmp_path / "project")
    client = Client(root)
    path = "content/units/same.json"
    client.call("read_document", {"path": path})
    client.mutate("set_field", path=path, field="health", value=137)
    target = root / path
    target.unlink()
    target.mkdir()
    failed = client.mutate("save_opened")
    assert failed["error"]["code"] == "SAVE_FAILED"
    assert client.state()["documents"][0]["dirty"]
    assert list(target.iterdir()) == []


def test_concurrent_edits_with_one_revision_have_one_winner(tmp_path):
    client = Client(make_project(tmp_path / "project"))
    path = "content/units/same.json"
    client.call("read_document", {"path": path})
    revision = client.state()["revision"]
    def request(value):
        return client.call("set_field", {"path": path, "field": "health", "value": value,
                                        "expectedRevision": revision}, f"edit-{value}")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(request, [137, 155]))
    assert sum(result["ok"] for result in results) == 1
    assert next(result for result in results if not result["ok"])["error"]["code"] == "STALE_REVISION"
    assert client.state()["revision"] == revision + 1
    assert client.mutate("undo")["data"]["documents"][0]["data"]["health"] == 100


def test_missing_health_field_undo_restores_absence_and_invalid_field_is_rejected(tmp_path):
    root = make_project(tmp_path / "project")
    path = "content/units/same.json"
    (root / path).write_text('{"type":"UnitType"}', encoding="utf-8")
    client = Client(root)
    client.call("read_document", {"path": path})
    assert not client.mutate("set_field", path=path, field="weapons[0].damage", value=12)["ok"]
    assert client.mutate("set_field", path=path, field="health", value=123.5)["ok"]
    restored = client.mutate("undo")["data"]["documents"][0]
    assert "health" not in restored["data"] and not restored["dirty"]


@pytest.mark.parametrize("interval", [0, 73, 180])
def test_existing_auto_save_setting_is_exposed_in_seconds(tmp_path, monkeypatch, interval):
    from types import SimpleNamespace
    import app.desktop.editing as editing_module
    monkeypatch.setattr(editing_module, "get_settings", lambda: SimpleNamespace(get=lambda key, default: interval))
    assert Client(make_project(tmp_path / "project")).state()["autoSaveInterval"] == interval
