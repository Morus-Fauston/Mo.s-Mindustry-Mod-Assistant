"""Resource controls through the real serialized workspace and saved files."""
import json
from itertools import count

from app.desktop.workspace import WorkspaceService


def test_resource_bridge_roundtrip_revisions_duplicates_and_sessions(tmp_path):
    root = tmp_path / "resources"
    (root / "content/blocks").mkdir(parents=True)
    (root / "mod.json").write_text('{"name":"resources"}')
    path = "content/blocks/crafter.json"
    initial = {"type": "GenericCrafter", "requirements": [{"item": "copper", "amount": 2}],
               "outputItem": {"item": "lead", "amount": 1}, "consumes": {"power": 1}}
    (root / path).write_text(json.dumps(initial))
    service = WorkspaceService("metadata")
    ids, sid = count(), None
    def call(action, **payload):
        return service.request({"protocolVersion": 1, "requestId": str(next(ids)), "sessionId": sid,
                                "action": action, "payload": payload})
    sid = call("open_project", path=str(root))["sessionId"]
    document = call("read_document", path=path)["data"]
    fields = {f["name"]: f for g in document["form"]["groups"] for f in g["fields"]}
    assert fields["requirements"]["control"] == "resource_list"
    row = fields["requirements"]["rows"][0]
    address = row["objectPath"]
    def state():
        return call("editing_state")["data"]
    def change(action, **payload):
        return call(action, expectedRevision=state()["revision"], **payload)
    result = call("resource_reference_candidates", path=path, objectPath=address, field="item", query="铅")
    assert result["ok"] and any(c["value"] == "lead" for c in result["data"]["candidates"])
    assert change("resource_set", path=path, objectPath=address, field="item", value="lead")["ok"]
    assert not change("resource_set", path=path, objectPath=address, field="amount", text="0")["ok"]
    envelope = {"protocolVersion": 1, "requestId": "quantity", "sessionId": sid,
                "action": "resource_set", "payload": {"path": path, "objectPath": address,
                "field": "amount", "text": "8", "expectedRevision": state()["revision"]}}
    first = service.request(envelope)
    assert first["ok"] and service.request(envelope) == first
    assert not call("resource_set", path=path, objectPath=address, field="amount", text="9", expectedRevision=-1)["ok"]
    assert change("resource_set", path=path, objectPath=["consumes"], field="power", text="0")["ok"]
    assert change("resource_set", path=path, objectPath=["outputItem"], field="item", value="")["ok"]
    assert state()["documents"][0]["data"]["outputItem"] is None
    assert change("undo")["ok"]
    assert state()["documents"][0]["data"]["outputItem"] == initial["outputItem"]
    assert change("save_opened")["ok"]
    disk = json.loads((root / path).read_text())
    assert disk["requirements"] == [{"item": "lead", "amount": 8}]
    assert disk["consumes"]["power"] == 0
    reopened = WorkspaceService("metadata")
    other = reopened.request({"protocolVersion": 1, "requestId": "open", "sessionId": None,
                              "action": "open_project", "payload": {"path": str(root)}})
    assert reopened.request({"protocolVersion": 1, "requestId": "read", "sessionId": other["sessionId"],
        "action": "read_document", "payload": {"path": path}})["data"]["data"] == disk
    assert not reopened.request(envelope)["ok"]


def test_combat_resource_configuration_uses_same_save_history(tmp_path):
    root = tmp_path / "combat"
    (root / "content/blocks").mkdir(parents=True)
    (root / "mod.json").write_text('{"name":"combat"}')
    path = "content/blocks/turret.json"
    initial = {"type": "PowerTurret", "consumes": {"power": 1.5,
        "coolant": {"liquid": "water", "amount": 2}}, "requirements": [{"item": "copper", "amount": 4}]}
    (root / path).write_text(json.dumps(initial))
    service, ids, sid = WorkspaceService("metadata"), count(), None
    def call(action, **payload):
        result = service.request({"protocolVersion": 1, "requestId": str(next(ids)), "sessionId": sid,
                                  "action": action, "payload": payload})
        assert result["ok"], result
        return result["data"]
    sid = call("open_project", path=str(root))["sessionId"]
    doc = call("read_document", path=path)
    result = call("resource_set", path=path, objectPath=["consumes", "coolant"], field="amount",
                  text="5", expectedRevision=doc["revision"])
    result = call("undo", expectedRevision=result["revision"])
    assert result["documents"][0]["data"] == initial
    result = call("redo", expectedRevision=result["revision"])
    call("save_opened", expectedRevision=result["revision"])
    assert json.loads((root / path).read_text())["consumes"]["coolant"]["amount"] == 5
