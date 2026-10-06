"""Closing an actual project releases its session without closing the host."""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import PackageNotFoundError
from itertools import count
from pathlib import Path
from threading import Event
import tomllib

from PIL import Image
import pytest

from app.desktop.api import DesktopApi
from app.desktop import api as api_module


@pytest.fixture
def opened_project(tmp_path):
    root = tmp_path / "中文 工程"
    path = "content/units/unit.json"
    (root / path).parent.mkdir(parents=True)
    (root / "mod.json").write_text('{"name":"close-test"}', encoding="utf-8")
    (root / path).write_text('{"type":"mech","health":100}', encoding="utf-8")
    closed = []
    api = DesktopApi("metadata", on_close=lambda: closed.append(True))
    serial = count()
    current = [None]

    def request(action, payload=None, *, sid=..., request_id=None):
        result = api.request({"protocolVersion": 1,
                              "requestId": request_id or f"close-{next(serial)}",
                              "sessionId": current[0] if sid is ... else sid,
                              "action": action, "payload": payload or {}})
        if result.get("ok"):
            current[0] = result["sessionId"]
        return result

    assert request("open_project", {"path": str(root)})["ok"]
    assert request("read_document", {"path": path})["ok"]
    state = request("editing_state")["data"]
    changed = request("set_field", {"path": path, "field": "health", "value": 250,
                                     "expectedRevision": state["revision"]})
    assert changed["ok"]
    return api, request, root, path, changed["data"], closed


def test_discard_close_releases_project_history_and_keeps_host(opened_project):
    api, request, root, path, state, closed = opened_project
    old_sid = state["sessionId"]
    result = request("close_project", {"decision": "discard", "expectedRevision": state["revision"]})
    assert result["ok"], result
    assert result["sessionId"] != old_sid
    assert result["data"]["project"] is None
    empty = result["data"]["state"]
    assert empty["sessionId"] == result["sessionId"]
    assert empty["documents"] == []
    assert not empty["history"]["canUndo"] and not empty["history"]["canRedo"]
    assert json.loads((root / path).read_text(encoding="utf-8"))["health"] == 100
    assert closed == []
    assert request("read_document", {"path": path})["error"]["code"] == "NO_PROJECT"
    assert request("editing_state", sid=old_sid)["error"]["code"] == "STALE_SESSION"
    assert request("open_project", {"path": str(root)})["ok"]
    assert request("read_document", {"path": path})["data"]["data"]["health"] == 100


def test_save_close_persists_and_duplicate_never_closes_new_session(opened_project):
    api, request, root, path, state, closed = opened_project
    old_sid = state["sessionId"]
    payload = {"decision": "save", "expectedRevision": state["revision"]}
    result = request("close_project", payload, request_id="save-close")
    assert result["ok"], result
    assert json.loads((root / path).read_text(encoding="utf-8"))["health"] == 250
    assert result["data"]["state"]["revision"] > state["revision"] + 1
    assert request("close_project", payload, sid=old_sid, request_id="save-close") == result
    assert api.request_result("save-close")["response"] == result
    assert request("close_project", {**payload, "decision": "discard"},
                   sid=old_sid, request_id="save-close")["error"]["code"] == "REQUEST_CONFLICT"
    opened = request("open_project", {"path": str(root)})
    assert opened["ok"]
    assert request("close_project", payload, sid=old_sid,
                   request_id="save-close")["error"]["code"] == "STALE_SESSION"
    assert request("read_document", {"path": path})["data"]["data"]["health"] == 250
    assert closed == []


def test_failed_save_keeps_project_dirty_history_and_resources(opened_project, monkeypatch):
    api, request, root, path, state, closed = opened_project
    workspace = api._workspace
    owners = (workspace._session, workspace._preview, workspace._generation,
              workspace._reference_projects, workspace._resource_watch)
    def denied(content):
        raise PermissionError("read-only project")
    monkeypatch.setattr(workspace._session, "save_content", denied)
    result = request("close_project", {"decision": "save", "expectedRevision": state["revision"]})
    assert result["error"]["code"] == "SAVE_FAILED"
    assert request("editing_state")["data"] == state
    assert owners == (workspace._session, workspace._preview, workspace._generation,
                      workspace._reference_projects, workspace._resource_watch)
    assert not workspace._generation._closed and not workspace._resource_watch._closed
    assert state["documents"][0]["dirty"] and state["history"]["canUndo"]
    assert json.loads((root / path).read_text(encoding="utf-8"))["health"] == 100
    assert closed == []


def test_empty_session_preparation_failure_preserves_unsaved_project(opened_project, monkeypatch):
    api, request, root, path, state, _ = opened_project
    session = api._workspace._session
    def broken(candidate):
        raise OSError("metadata unavailable during close")
    monkeypatch.setattr(api._workspace, "_prepare_services", broken)
    response = request("close_project", {"decision": "save", "expectedRevision": state["revision"]})
    assert not response["ok"]
    assert api._workspace._session is session
    assert request("editing_state")["data"] == state
    assert json.loads((root / path).read_text(encoding="utf-8"))["health"] == 100


@pytest.mark.parametrize("patch", [
    {"decision": "cancel"}, {"decision": None}, {"decision": []},
    {"extra": True}, {"expectedRevision": True}, {"expectedRevision": "1"},
    {"expectedRevision": -1},
])
def test_close_payload_and_revision_are_validated_without_release(opened_project, patch):
    api, request, root, path, state, closed = opened_project
    payload = {"decision": "discard", "expectedRevision": state["revision"], **patch}
    result = request("close_project", payload)
    assert not result["ok"]
    assert result["error"]["code"] in {"INVALID_CLOSE", "STALE_REVISION"}
    assert request("editing_state")["data"] == state
    assert closed == []


@pytest.mark.parametrize("missing", ["decision", "expectedRevision"])
def test_close_requires_both_payload_fields(opened_project, missing):
    _, request, _, _, state, _ = opened_project
    payload = {"decision": "discard", "expectedRevision": state["revision"]}
    payload.pop(missing)
    assert request("close_project", payload)["error"]["code"] == "INVALID_CLOSE"
    assert request("editing_state")["data"] == state


def test_bootstrap_reports_product_version_from_project_metadata():
    product = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    response = DesktopApi("metadata").bootstrap(1)
    assert response["ok"], response
    assert response["data"]["application"] == {"version": product}


def test_close_releases_real_preview_generation_and_reference_sources(opened_project, monkeypatch, tmp_path):
    api, request, root, path, state, _ = opened_project
    sprite = root / "sprites/units/unit.png"
    sprite.parent.mkdir(parents=True)
    with Image.new("RGBA", (7, 7), (20, 60, 120, 255)) as image:
        image.save(sprite)
    reference = tmp_path / "参考工程"
    (reference / "content/units").mkdir(parents=True)
    (reference / "content/units/unit.json").write_text('{"health":777}', encoding="utf-8")
    workspace = api._workspace
    monkeypatch.setattr(workspace, "_choose_directory", lambda: str(reference))
    scene = request("preview_scene", {"path": path})
    assert scene["ok"], scene
    resource_id = scene["data"]["layers"][0]["resourceId"]
    assert request("preview_resource", {"resourceId": resource_id})["ok"]
    generation = request("preview_generation", {"path": path, "outputs": [{"suffix": "-outline"}],
                                               "expectedRevision": state["revision"]})
    assert generation["ok"], generation
    candidate_id = generation["data"]["candidate"]["candidateId"]
    opened_reference = request("open_reference", {"kind": "folder", "expectedRevision": state["revision"]})
    assert opened_reference["ok"], opened_reference
    old_generation, old_references, old_watch = workspace._generation, workspace._reference_projects, workspace._resource_watch
    before_png = sprite.read_bytes()
    result = request("close_project", {"decision": "discard", "expectedRevision": state["revision"]})
    assert result["ok"], result
    assert old_generation._closed and not old_generation._candidates
    assert old_references._closed and not old_references._external
    with pytest.raises(ValueError, match="关闭"):
        old_watch.scan()
    assert workspace._preview is None and workspace._resources is None
    for response in (generation, opened_reference):
        assert api.request_result(response["requestId"])["response"]["error"]["code"] == "RESULT_EXPIRED"
    assert request("preview_resource", {"resourceId": resource_id})["error"]["code"] == "NO_PROJECT"
    assert request("open_project", {"path": str(root)})["ok"]
    assert request("read_document", {"path": path})["ok"]
    current = request("editing_state")["data"]
    assert request("preview_resource", {"resourceId": resource_id})["error"]["code"] == "PREVIEW_RESOURCE_UNAVAILABLE"
    rejected = request("confirm_generation", {"candidateId": candidate_id, "overwrite": False,
                                               "expectedRevision": current["revision"]})
    assert not rejected["ok"]
    assert not (sprite.parent / "unit-outline.png").exists()
    assert sprite.read_bytes() == before_png


def test_close_and_late_edit_are_serialized_and_old_session_rejected(opened_project, monkeypatch):
    api, _, root, path, state, closed = opened_project
    session = api._workspace._session
    save = session.save_content
    saving, release, editing_started = Event(), Event(), Event()

    def held_save(content):
        saving.set()
        assert release.wait(5), "test failed to release the save boundary"
        return save(content)

    monkeypatch.setattr(session, "save_content", held_save)
    def envelope(action, request_id, payload):
        return {"protocolVersion": 1, "requestId": request_id,
                "sessionId": state["sessionId"], "action": action, "payload": payload}
    close = envelope("close_project", "serialized-close", {"decision": "save", "expectedRevision": state["revision"]})
    edit = envelope("set_field", "late-edit", {"path": path, "field": "health", "value": 999,
                                               "expectedRevision": state["revision"]})
    def late_edit():
        editing_started.set()
        return api.request(edit)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(api.request, close)
        try:
            assert saving.wait(5)
            second = pool.submit(late_edit)
            assert editing_started.wait(5)
            assert api.request_result("serialized-close")["state"] == "pending"
        finally:
            release.set()
        assert first.result(timeout=5)["ok"]
        assert second.result(timeout=5)["error"]["code"] == "STALE_SESSION"
    assert json.loads((root / path).read_text(encoding="utf-8"))["health"] == 250
    assert closed == []


def test_close_without_project_cannot_create_another_empty_session():
    api = DesktopApi("metadata")
    envelope = {"protocolVersion": 1, "requestId": "empty-close", "sessionId": None,
                "action": "close_project", "payload": {"decision": "discard", "expectedRevision": 0}}
    response = api.request(envelope)
    assert response["error"]["code"] == "NO_PROJECT"
    assert response["sessionId"] is None


def test_uninstalled_source_bootstrap_uses_pyproject_version_and_retries_missing_data(tmp_path, monkeypatch):
    def missing(name):
        raise PackageNotFoundError(name)
    monkeypatch.setattr(api_module, "distribution_version", missing)
    monkeypatch.setattr(api_module, "data_dir", lambda: tmp_path)
    api = DesktopApi("metadata")
    assert api.bootstrap(1)["error"]["code"] == "METADATA_UNAVAILABLE"
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "7.8.9a1"\n', encoding="utf-8")
    assert api.bootstrap(1)["data"]["application"] == {"version": "7.8.9a1"}
    assert api._workspace is None


def test_source_bootstrap_prefers_project_version_over_stale_installed_metadata(monkeypatch):
    product = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    monkeypatch.setattr(api_module, "distribution_version", lambda name: "0.2.6")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    response = DesktopApi("metadata").bootstrap(1)
    assert response["ok"], response
    assert response["data"]["application"] == {"version": product}


def test_source_without_pyproject_uses_installed_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(api_module, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(api_module, "distribution_version", lambda name: "7.8.9a2")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert DesktopApi("metadata").bootstrap(1)["data"]["application"] == {"version": "7.8.9a2"}


def test_frozen_version_never_needs_source_pyproject(monkeypatch):
    monkeypatch.setattr(api_module, "distribution_version", lambda name: "0.3.0a5" if name == "moma" else None)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    def forbidden():
        raise AssertionError("Frozen version must not read source files")
    monkeypatch.setattr(api_module, "data_dir", forbidden)
    assert DesktopApi("metadata").bootstrap(1)["data"]["application"] == {"version": "0.3.0a5"}


def test_frozen_missing_metadata_does_not_fall_back_to_source(tmp_path, monkeypatch):
    def missing(name):
        raise PackageNotFoundError(name)
    monkeypatch.setattr(api_module, "distribution_version", missing)
    monkeypatch.setattr(api_module, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "7.8.9a1"\n', encoding="utf-8")
    response = DesktopApi("metadata").bootstrap(1)
    assert not response["ok"]
    assert response["error"]["code"] == "METADATA_UNAVAILABLE"
