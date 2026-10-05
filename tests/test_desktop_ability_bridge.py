"""Ability editing through the actual workspace command/revision boundary."""
import json
from itertools import count

from app.desktop.workspace import WorkspaceService


def test_ability_reference_identity_and_save_reopen(tmp_path):
    root = tmp_path / "ability"
    (root / "content/units").mkdir(parents=True)
    (root / "mod.json").write_text('{"name":"ability"}')
    path = "content/units/flyer.json"
    (root / path).write_text(json.dumps({"type": "flying", "abilities": [
        {"type": "RegenAbility", "amount": 1}, {"type": "RegenAbility", "amount": 2}]}))
    service, ids, sid = WorkspaceService("metadata"), count(), None
    def call(action, **payload):
        response = service.request({"protocolVersion": 1, "requestId": str(next(ids)), "sessionId": sid,
                                    "action": action, "payload": payload})
        assert response["ok"], response
        return response["data"]
    sid = call("open_project", path=str(root))["sessionId"]
    call("read_document", path=path)
    def state():
        return call("editing_state")
    def change(action, **payload):
        return call(action, expectedRevision=state()["revision"], **payload)
    def items():
        return next(f for g in state()["documents"][0]["form"]["groups"] for f in g["fields"] if f["name"] == "abilities")["items"]
    a, b = [item["itemId"] for item in items()]
    change("array_move", path=path, field="abilities", itemId=a, beforeItemId=None)
    address = ["abilities", {"itemId": a}]
    change("set_field", path=path, objectPath=address, field="amount", text="7")
    change("set_type", path=path, objectPath=address, type="UnitSpawnAbility")
    candidates = call("reference_candidates", path=path, objectPath=address, field="unit", query="dagger")
    assert any(row["value"] == "dagger" for row in candidates["candidates"])
    change("set_field", path=path, objectPath=address, field="unit", value="dagger")
    change("save_opened")
    saved = json.loads((root / path).read_text())
    assert saved["abilities"][0] == {"type": "RegenAbility", "amount": 2}
    assert saved["abilities"][1] == {"type": "UnitSpawnAbility", "amount": 7, "unit": "dagger"}
    change("close_documents", paths=[path], decision="discard")
    reopened = call("read_document", path=path)
    assert reopened["data"] == saved and not reopened["dirty"]
    change("undo")
    assert state()["documents"][0]["data"]["abilities"][1].get("unit") != "dagger"
    assert [item["itemId"] for item in items()] == [b, a]
