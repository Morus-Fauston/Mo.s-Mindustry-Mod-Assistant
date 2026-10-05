"""Resource mutations use the real serialized session and disk, including history."""
from io import BytesIO
from itertools import count
import json

from PIL import Image
import pytest

from app.desktop.workspace import WorkspaceService

PATH = "content/units/unit.json"


def png(color):
    stream = BytesIO()
    Image.new("RGBA", (3, 2), color).save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture
def client(tmp_path):
    root = tmp_path / "工程"
    (root / "content/units").mkdir(parents=True)
    (root / "mod.json").write_text('{"name":"resources"}', encoding="utf-8")
    (root / PATH).write_text('{"type":"flying","health":100}', encoding="utf-8")
    source = tmp_path / "来源.png"
    source.write_bytes(png("red"))
    selected = [str(source)]
    revealed = []
    service = WorkspaceService("metadata", choose_sprite=lambda: selected[0], reveal_file=revealed.append)
    ids = count()
    sid = None

    def call(action, **payload):
        return service.request({"protocolVersion": 1, "requestId": str(next(ids)),
            "sessionId": sid, "action": action, "payload": payload})

    result = call("open_project", path=str(root))
    assert result["ok"], result
    sid = result["sessionId"]
    assert call("read_document", path=PATH)["ok"]

    def mutate(action, **payload):
        revision = call("editing_state")["data"]["revision"]
        return call(action, expectedRevision=revision, **payload)

    return root, source, selected, revealed, service, call, mutate


def test_import_replace_delete_history_and_refresh(client):
    root, source, _, revealed, _, call, mutate = client
    target = root / "sprites/units/unit.png"
    before = call("editing_state")["data"]
    result = mutate("import_sprite", path=PATH, suffix="")
    assert result["ok"], result
    assert target.read_bytes() == png("red")
    assert result["data"]["revision"] > before["revision"]
    assert not result["data"]["documents"][0]["dirty"]
    assert call("sprite_targets", path=PATH)["data"]["targets"][0]["exists"]
    assert mutate("reveal_sprite", path=PATH, suffix="")["ok"]
    assert revealed == [target]
    source.write_bytes(png("blue"))
    assert not mutate("import_sprite", path=PATH, suffix="")["ok"]
    assert target.read_bytes() == png("red")
    assert mutate("import_sprite", path=PATH, suffix="", overwrite=True)["ok"]
    assert target.read_bytes() == png("blue")
    assert mutate("delete_sprite", path=PATH, suffix="", confirmed=True)["ok"]
    assert not target.exists()
    assert mutate("undo")["ok"]
    assert target.read_bytes() == png("blue")
    assert mutate("undo")["ok"]
    assert target.read_bytes() == png("red")
    assert mutate("undo")["ok"]
    assert not target.exists()
    assert mutate("redo")["ok"]
    assert target.read_bytes() == png("red")


def test_cancel_invalid_input_and_stale_revision_have_no_side_effects(client):
    root, source, selected, _, _, call, mutate = client
    before = call("editing_state")["data"]
    selected[0] = None
    result = mutate("import_sprite", path=PATH, suffix="")
    assert result["ok"] and result["data"]["cancelled"]
    assert call("editing_state")["data"] == before
    selected[0] = str(source)
    assert not mutate("import_sprite", path=PATH, sourcePath=str(source))["ok"]
    assert not call("import_sprite", path=PATH, expectedRevision=-1)["ok"]
    source.write_bytes(b"fake PNG")
    result = mutate("import_sprite", path=PATH)
    assert not result["ok"] and result["error"]["code"] == "RESOURCE_FAILED"
    assert call("editing_state")["data"] == before
    assert not (root / "sprites/units/unit.png").exists()


def test_duplicate_mutation_old_session_and_external_refresh(client, tmp_path):
    root, _, _, _, service, call, mutate = client
    before = call("editing_state")["data"]
    envelope = {"protocolVersion": 1, "requestId": "same", "sessionId": before["sessionId"],
        "action": "import_sprite", "payload": {"path": PATH, "expectedRevision": before["revision"]}}
    result = service.request(envelope)
    assert result["ok"], result
    assert service.request(envelope) == result
    version = call("resource_state")["data"]["resourceRevision"]
    (root / "sprites/units/unit.png").write_bytes(png("green"))
    updated = call("resource_state")["data"]
    assert updated["resourceRevision"] > version
    # External edits cannot be erased by undo; its failed command stays available.
    result = mutate("undo")
    assert not result["ok"]
    assert call("editing_state")["data"]["history"]["canUndo"]
    other = tmp_path / "other"
    other.mkdir()
    (other / "mod.json").write_text('{"name":"other"}')
    assert mutate("open_project", path=str(other))["ok"]
    assert not service.request(envelope)["ok"]


def test_switch_and_window_close_release_the_previous_observer(client, tmp_path, monkeypatch):
    from app.desktop.resource_watch import ResourceWatch
    root, _, _, _, _, call, mutate = client
    released = []
    original = ResourceWatch.close

    def close(watch):
        released.append(watch)
        original(watch)

    monkeypatch.setattr(ResourceWatch, "close", close)
    assert not mutate("open_project", path=str(tmp_path / "missing"))["ok"]
    assert not released
    assert call("resource_state")["ok"]
    assert mutate("open_project", path=str(root))["ok"]
    assert len(released) == 1
    with pytest.raises(ValueError, match="关闭"):
        released[0].scan()
    # Obtain current session from a fresh public open result for the final close.
    service = WorkspaceService("metadata")
    opened = service.request({"protocolVersion": 1, "requestId": "open", "sessionId": None,
        "action": "open_project", "payload": {"path": str(root)}})
    sid = opened["sessionId"]
    state = service.request({"protocolVersion": 1, "requestId": "state", "sessionId": sid,
        "action": "editing_state", "payload": {}})["data"]
    result = service.request({"protocolVersion": 1, "requestId": "close", "sessionId": sid,
        "action": "close_window", "payload": {"decision": "discard", "expectedRevision": state["revision"]}})
    assert result["ok"] and len(released) == 2
    with pytest.raises(ValueError, match="关闭"):
        released[-1].scan()
