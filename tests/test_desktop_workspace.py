"""Real-file workspace requests through the public desktop boundary."""

import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.desktop.workspace import WorkspaceService
from app.core import session as session_module


def project(root, title="测试工程"):
    root.mkdir(parents=True)
    (root / "mod.json").write_text(json.dumps({"name": "test", "displayName": title}), encoding="utf-8")
    for category, kind, health in [("units", "UnitType", 100), ("blocks", "Wall", 500), ("weapons", "Weapon", 0)]:
        directory = root / "content" / category
        directory.mkdir(parents=True)
        (directory / "同名 内容.json").write_text(json.dumps({"type": kind, "health": health}), encoding="utf-8")
    sprite = root / "sprites" / "units"
    sprite.mkdir(parents=True)
    (sprite / "同名 内容.png").write_bytes(b"image fixture")
    return root


def call(service, action, payload=None, session=None, request_id="request-1"):
    return service.request({"protocolVersion": 1, "requestId": request_id,
                            "sessionId": session, "action": action, "payload": payload or {}})


def flatten(nodes):
    return [item for node in nodes for item in [node, *flatten(node.get("children", []))]]


def test_open_real_project_tree_and_category_specific_documents(tmp_path):
    root = project(tmp_path / "中文 空格工程")
    service = WorkspaceService(Path("metadata"))
    opened = call(service, "open_project", {"path": str(root)})
    assert opened["ok"] is True
    assert opened["data"]["name"] == "测试工程"
    sid = opened["data"]["sessionId"]
    assert opened["sessionId"] == sid
    nodes = flatten(opened["data"]["tree"])
    assert "防御" in [n["label"] for n in nodes]
    assert "墙" in [n["label"] for n in nodes]
    assert any(n.get("path") == "sprites/units/同名 内容.png" for n in nodes)
    for category, health in [("units", 100), ("blocks", 500)]:
        doc = call(service, "read_document", {"path": f"content/{category}/同名 内容.json"}, sid, category)
        assert doc["ok"] is True
        assert doc["data"]["data"]["health"] == health
        assert doc["data"]["category"] == category
        assert doc["data"]["fieldNames"]["health"]
        assert doc["data"]["fieldDocs"]["health"]
    recent = call(service, "recent_projects", request_id="recent")
    assert recent["data"]["recentProjects"] == [{"path": str(root.resolve()), "name": "测试工程"}]


def test_failed_open_cancel_and_broken_document_keep_current_session(tmp_path):
    root = project(tmp_path / "existing")
    (root / "content" / "units" / "broken.json").write_text('{bad', encoding="utf-8")
    service = WorkspaceService("metadata", choose_directory=lambda: None)
    opened = call(service, "open_project", {"path": str(root)})
    sid = opened["sessionId"]
    broken = next(n for n in flatten(opened["data"]["tree"]) if n.get("name") == "broken")
    assert broken["error"]
    result = call(service, "read_document", {"path": broken["path"]}, sid, "broken")
    assert result["error"]["path"] == broken["path"]
    assert result["error"]["code"] == "DOCUMENT_READ_FAILED"
    cancelled = call(service, "choose_project", session=sid, request_id="cancel")
    assert cancelled["data"] == {"cancelled": True}
    assert cancelled["sessionId"] == sid
    failed = call(service, "open_project", {"path": str(tmp_path / "missing")}, sid, "missing")
    assert failed["error"]["code"] == "PROJECT_OPEN_FAILED"
    assert failed["sessionId"] == sid
    assert call(service, "read_document", {"path": "content/units/同名 内容.json"}, sid, "read")["ok"]


def test_requests_are_deduplicated_and_old_session_is_rejected(tmp_path):
    first = project(tmp_path / "first")
    second = project(tmp_path / "second", "另一个工程")
    chosen = []
    service = WorkspaceService("metadata", choose_directory=lambda: chosen.append(True) or str(first))
    opened = call(service, "choose_project")
    assert call(service, "choose_project") == opened
    assert len(chosen) == 1
    assert call(service, "open_project", {"path": str(second)})["error"]["code"] == "REQUEST_CONFLICT"
    new = call(service, "open_project", {"path": str(second)}, opened["sessionId"], "second")
    assert new["sessionId"] != opened["sessionId"]
    assert call(service, "choose_project")["error"]["code"] == "STALE_SESSION"
    assert call(service, "read_document", {"path": "content/units/同名 内容.json"}, opened["sessionId"], "stale")["error"]["code"] == "STALE_SESSION"


def test_document_cache_is_core_owned_and_responses_are_detached(tmp_path):
    root = project(tmp_path / "existing")
    service = WorkspaceService("metadata")
    sid = call(service, "open_project", {"path": str(root)})["sessionId"]
    payload = {"path": "content/units/同名 内容.json"}
    doc = call(service, "read_document", payload, sid, "first-read")
    doc["data"]["data"]["health"] = 999
    (root / payload["path"]).write_text('{bad', encoding="utf-8")
    assert call(service, "read_document", payload, sid, "next-read")["data"]["data"]["health"] == 100
    assert call(service, "read_document", payload, sid, "first-read")["data"]["data"]["health"] == 100


def test_request_cache_evicts_oldest_result_after_128_requests(tmp_path):
    calls = []
    service = WorkspaceService("metadata", choose_directory=lambda: calls.append(True) or None)
    call(service, "choose_project", request_id="old")
    for i in range(128):
        assert call(service, "recent_projects", request_id=f"recent-{i}")["ok"]
    call(service, "choose_project", request_id="old")
    assert len(calls) == 2


def test_content_root_symlink_cannot_read_outside_project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "mod.json").write_text('{"name":"test"}', encoding="utf-8")
    outside = tmp_path / "outside"
    (outside / "units").mkdir(parents=True)
    (outside / "units" / "secret.json").write_text('{"secret":true}', encoding="utf-8")
    try:
        (root / "content").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("当前权限不支持符号链接")
    service = WorkspaceService("metadata")
    sid = call(service, "open_project", {"path": str(root)})["sessionId"]
    response = call(service, "read_document", {"path": "content/units/secret.json"}, sid, "outside")
    assert response["ok"] is False
    assert response["error"]["path"] == "content/units/secret.json"


@pytest.mark.parametrize("envelope", [None, [], {},
    {"protocolVersion": True, "requestId": "x"},
    {"protocolVersion": 1, "requestId": "x" * 129},
    {"protocolVersion": 1, "requestId": "x", "action": "execute_script", "payload": {}},
    {"protocolVersion": 1, "requestId": "x", "action": "recent_projects", "payload": []},
    {"protocolVersion": 1, "requestId": "x", "action": "recent_projects", "payload": {"text": "a" * 17000}},
])
def test_invalid_requests_return_structured_failure(envelope):
    response = WorkspaceService("metadata").request(envelope)
    assert response["ok"] is False
    assert response["error"]["code"] in {"INVALID_REQUEST", "PROTOCOL_MISMATCH"}


@pytest.mark.parametrize("path", ["../mod.json", "/content/units/a.json", "content/units/../mod.json",
                                  "content/units/C:a.json", "content/units/..\\mod.json", "content/other/a.json"])
def test_read_request_rejects_paths_outside_content_scope(tmp_path, path):
    root = project(tmp_path / "existing")
    service = WorkspaceService("metadata")
    sid = call(service, "open_project", {"path": str(root)})["sessionId"]
    response = call(service, "read_document", {"path": path}, sid, "outside")
    assert response["ok"] is False


def test_broken_content_can_be_retried_with_new_request_id(tmp_path):
    root = project(tmp_path / "existing")
    content = root / "content" / "units" / "broken.json"
    content.write_text("[]", encoding="utf-8")
    service = WorkspaceService("metadata")
    sid = call(service, "open_project", {"path": str(root)})["sessionId"]
    payload = {"path": "content/units/broken.json"}
    assert not call(service, "read_document", payload, sid, "broken")["ok"]
    content.write_text('{"type":"mech","health":12}', encoding="utf-8")
    recovered = call(service, "read_document", payload, sid, "recovered")
    assert recovered["data"]["contentType"] == "UnitType"
    assert recovered["data"]["data"]["health"] == 12


def test_tree_uses_display_name_and_preserves_file_identity_for_search(tmp_path):
    root = project(tmp_path / "existing")
    directory = root / "content" / "units"
    for filename, display in [("twin", "同名单元"), ("blank", "  "), ("invalid", ["wrong"])]:
        (directory / f"{filename}.json").write_text(json.dumps({"type": "UnitType", "name": display}), encoding="utf-8")
    result = call(WorkspaceService("metadata"), "open_project", {"path": str(root)})
    leaves = {n.get("name"): n for n in flatten(result["data"]["tree"]) if n["kind"] == "content" and n["category"] == "units"}
    assert leaves["twin"]["label"] == "同名单元"
    assert leaves["twin"]["path"] == "content/units/twin.json"
    assert leaves["blank"]["label"] == "blank"
    assert leaves["invalid"]["label"] == "invalid"


def test_oversized_payload_is_not_retained_as_a_deduplicated_request():
    service = WorkspaceService("metadata")
    response = call(service, "recent_projects", {"unused": "a" * 17000})
    assert response["error"]["code"] == "INVALID_REQUEST"
    assert call(service, "recent_projects")["ok"]


@pytest.mark.parametrize("info,expected", [
    ({"displayName": {"wrong": True}, "name": ["wrong"]}, "recent-project"),
    ({"displayName": [], "name": "fallback"}, "fallback"),
    ({"displayName": "显示名称", "name": {}}, "显示名称"),
])
def test_recent_project_names_are_always_strings(tmp_path, info, expected):
    root = tmp_path / "recent-project"
    root.mkdir()
    (root / "mod.json").write_text(json.dumps(info), encoding="utf-8")
    session_module.save_editor_state({"last_project": str(root)})
    recent = call(WorkspaceService("metadata"), "recent_projects")
    assert recent["data"]["recentProjects"] == [{"path": str(root), "name": expected}]


def test_invalid_recent_path_is_ignored():
    session_module.save_editor_state({"last_project": {"wrong": "shape"}})
    result = call(WorkspaceService("metadata"), "recent_projects")
    assert result["data"]["recentProjects"] == []


def test_query_completed_request_returns_original_response_without_reopening(tmp_path):
    root = project(tmp_path / "existing")
    selected = []
    service = WorkspaceService("metadata", choose_directory=lambda: selected.append(True) or str(root))
    response = call(service, "choose_project", request_id="original")
    queried = service.request_result("original")
    assert queried == {"state": "completed", "response": response}
    assert len(selected) == 1
    queried["response"]["data"]["name"] = "mutated"
    assert service.request_result("original")["response"]["data"]["name"] == "测试工程"


def test_query_pending_request_is_nonblocking_and_never_reexecutes(tmp_path):
    root = project(tmp_path / "existing")
    entered, release = Event(), Event()

    def choose():
        entered.set()
        assert release.wait(5)
        return str(root)

    service = WorkspaceService("metadata", choose_directory=choose)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(call, service, "choose_project", request_id="original")
        try:
            assert entered.wait(5)
            assert service.request_result("original") == {"state": "pending"}
        finally:
            release.set()
        original = future.result(timeout=5)
    assert service.request_result("original") == {"state": "completed", "response": original}


def test_query_unknown_expired_or_invalid_id_has_no_side_effects():
    choices = []
    service = WorkspaceService("metadata", choose_directory=lambda: choices.append(True) or None)
    for request_id in (None, [], {}, "", "x" * 129, "missing"):
        assert service.request_result(request_id) == {"state": "unknown"}
    assert not choices
    call(service, "choose_project", request_id="old")
    for i in range(128):
        call(service, "recent_projects", request_id=f"recent-{i}")
    assert service.request_result("old") == {"state": "unknown"}
    assert len(choices) == 1
