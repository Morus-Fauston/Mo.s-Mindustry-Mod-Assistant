"""Public nested editing envelopes, identities, history and saved JSON."""
import json
from itertools import count

import pytest

from app.desktop.workspace import WorkspaceService

PATH = "content/weapons/gun.json"


def fields(plan):
    return {field["name"]: field for group in plan["groups"] for field in group["fields"]}


@pytest.fixture
def client(tmp_path):
    root = tmp_path / "nested"
    (root / "content/weapons").mkdir(parents=True)
    (root / "mod.json").write_text('{"name":"nested"}')
    (root / PATH).write_text(json.dumps({"reload": 20, "bullet": {"type": "BasicBulletType", "damage": 10,
        "spawnBullets": [{"damage": 1}, {"damage": 2}]}}))
    service = WorkspaceService("metadata")
    sid, ids = None, count()
    def call(action, **payload):
        return service.request({"protocolVersion": 1, "requestId": str(next(ids)), "sessionId": sid,
            "action": action, "payload": payload})
    opened = call("open_project", path=str(root))
    sid = opened["sessionId"]
    assert call("read_document", path=PATH)["ok"]
    def state():
        return call("editing_state")["data"]
    def mutate(action, **payload):
        return call(action, expectedRevision=state()["revision"], **payload)
    return root, service, call, state, mutate


def test_nested_type_edit_and_save_roundtrip(client):
    root, _, call, state, mutate = client
    bullet = fields(state()["documents"][0]["form"])["bullet"]["child"]
    assert bullet["knownType"]
    assert mutate("set_type", path=PATH, objectPath=["bullet"], type="LaserBulletType")["ok"]
    assert mutate("set_field", path=PATH, objectPath=["bullet"], field="damage", text="35")["ok"]
    assert state()["documents"][0]["data"]["bullet"]["damage"] == 35
    assert mutate("undo")["ok"]
    assert state()["documents"][0]["data"]["bullet"]["damage"] == 10
    assert mutate("redo")["ok"]
    assert mutate("save_opened")["ok"]
    assert json.loads((root / PATH).read_text())["bullet"]["damage"] == 35
    assert not state()["documents"][0]["dirty"]
    assert not call("set_field", path=PATH, objectPath=["bullet"], field="damage", value=99, expectedRevision=-1)["ok"]


def test_array_item_address_moves_and_discard_restores_saved_form_state(client):
    _, _, _, state, mutate = client
    def items():
        return fields(fields(state()["documents"][0]["form"])["bullet"]["child"])["spawnBullets"]["items"]
    a, b = [item["itemId"] for item in items()]
    assert mutate("array_move", path=PATH, objectPath=["bullet"], field="spawnBullets", itemId=a, beforeItemId=None)["ok"]
    assert [item["itemId"] for item in items()] == [b, a]
    assert mutate("set_field", path=PATH, objectPath=["bullet", "spawnBullets", {"itemId": a}], field="damage", text="12")["ok"]
    assert state()["documents"][0]["data"]["bullet"]["spawnBullets"] == [{"damage": 2}, {"damage": 12}]
    assert mutate("array_remove", path=PATH, objectPath=["bullet"], field="spawnBullets", itemId=a)["ok"]
    assert not mutate("set_field", path=PATH, objectPath=["bullet", "spawnBullets", {"itemId": a}], field="damage", text="99")["ok"]
    assert mutate("undo")["ok"]
    assert [item["itemId"] for item in items()] == [b, a]
    assert mutate("close_documents", paths=[PATH], decision="discard")["ok"]
    assert not state()["documents"]
    assert mutate("undo")["ok"]
    assert [item["itemId"] for item in items()] == [b, a]
    assert state()["documents"][0]["data"]["bullet"]["spawnBullets"][1]["damage"] == 12
