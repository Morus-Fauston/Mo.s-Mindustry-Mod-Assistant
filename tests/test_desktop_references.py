"""Reference selection through serialized requests and real project storage."""

import json
from itertools import count

import pytest

from app.desktop.workspace import WorkspaceService


PATH = "content/blocks/wall.json"


class Client:
    def __init__(self, root, metadata="metadata"):
        self.service = WorkspaceService(metadata)
        self.ids = count()
        self.sid = None
        result = self.call("open_project", path=str(root))
        assert result["ok"], result
        self.sid = result["sessionId"]
        result = self.call("read_document", path=PATH)
        assert result["ok"], result

    def call(self, action, **payload):
        return self.service.request({"protocolVersion": 1, "sessionId": self.sid,
            "requestId": str(next(self.ids)), "action": action, "payload": payload})

    def state(self):
        result = self.call("editing_state")
        assert result["ok"], result
        return result["data"]

    def mutate(self, action, **payload):
        return self.call(action, expectedRevision=self.state()["revision"], **payload)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    (root / "content/blocks").mkdir(parents=True)
    (root / "mod.json").write_text('{"name":"refs"}', encoding="utf-8")
    (root / PATH).write_text(json.dumps({"type": "Wall", "itemDrop": "copper", "lightLiquid": "water"}), encoding="utf-8")
    return root


def test_real_reference_candidates_bilingual_category_and_read_only_loading(project):
    client = Client(project)
    before = client.state()
    for query in ("铜", "COPPER"):
        result = client.call("reference_candidates", path=PATH, field="itemDrop", query=query)
        assert result["ok"], result
        data = result["data"]
        assert {item["category"] for item in data["candidates"]} == {"Items"}
        assert any(item["value"] == "copper" and "铜" in item["label"] for item in data["candidates"])
        assert data["categories"] == [{"id": "Items", "label": "物品"}]
        assert data["current"] == {"value": "copper", "label": "铜 (copper)", "known": True}
    fields = {field["name"]: field for group in before["documents"][0]["form"]["groups"] for field in group["fields"]}
    assert fields["itemDrop"]["control"] == "reference"
    assert fields["itemDrop"]["refSource"] == "Items"
    assert fields["itemDrop"]["categories"] == ["Items"]
    assert client.state() == before


def test_explicit_selections_and_save_are_undo_boundaries(project):
    client = Client(project)
    assert client.mutate("set_field", path=PATH, field="itemDrop", value="lead")["ok"]
    assert client.mutate("set_field", path=PATH, field="itemDrop", value=None)["ok"]
    assert client.mutate("undo")["ok"]
    assert client.state()["documents"][0]["data"]["itemDrop"] == "lead"
    assert client.mutate("undo")["ok"]
    assert client.state()["documents"][0]["data"]["itemDrop"] == "copper"
    assert client.mutate("set_field", path=PATH, field="health", text="275")["ok"]
    assert client.mutate("save_opened")["ok"]
    assert client.mutate("set_field", path=PATH, field="health", text="300")["ok"]
    assert client.mutate("undo")["ok"]
    assert client.state()["documents"][0]["data"]["health"] == 275


@pytest.mark.parametrize("value", ["lead", "", None])
def test_reference_edit_clear_undo_save_and_reopen(project, value):
    client = Client(project)
    result = client.mutate("set_field", path=PATH, field="itemDrop", value=value)
    assert result["ok"], result
    assert client.state()["documents"][0]["data"]["itemDrop"] == value
    assert client.mutate("undo")["ok"]
    assert client.state()["documents"][0]["data"]["itemDrop"] == "copper"
    assert client.mutate("redo")["ok"]
    assert client.mutate("save_opened")["ok"]
    assert Client(project).state()["documents"][0]["data"]["itemDrop"] == value


@pytest.mark.parametrize("payload", [{"value": "water"}, {"text": "water"}, {"value": "铜"}, {"value": 7}, {"value": ["copper"]}, {"value": "x" * 1025}])
def test_invalid_reference_values_are_rejected_without_state_change(project, payload):
    client = Client(project)
    before = client.state()
    result = client.mutate("set_field", path=PATH, field="itemDrop", **payload)
    assert not result["ok"] and result["error"]["code"] == "INVALID_FIELD_VALUE"
    assert client.state() == before


def test_unknown_existing_reference_remains_visible_and_is_not_implicitly_replaced(project):
    data = json.loads((project / PATH).read_text())
    data["itemDrop"] = "missing-mod-item"
    (project / PATH).write_text(json.dumps(data), encoding="utf-8")
    client = Client(project)
    before = client.state()
    result = client.call("reference_candidates", path=PATH, field="itemDrop", query="no matches")
    assert result["ok"], result
    assert result["data"]["candidates"] == []
    assert result["data"]["current"] == {"value": "missing-mod-item", "label": "missing-mod-item", "known": False}
    assert client.mutate("set_field", path=PATH, field="itemDrop", value="missing-mod-item")["ok"]
    assert client.state() == before
    assert client.mutate("set_field", path=PATH, field="itemDrop", value="")["ok"]
    assert client.mutate("undo")["ok"]
    assert client.state()["documents"][0]["data"]["itemDrop"] == "missing-mod-item"


def test_nonnullable_reference_clear_is_empty_string_and_null_is_rejected(project):
    target = project / "content/weapons/gun.json"
    target.parent.mkdir()
    target.write_text('{"shootStatus":"burning"}', encoding="utf-8")
    client = Client(project)
    assert client.call("read_document", path="content/weapons/gun.json")["ok"]
    before = client.state()
    assert not client.mutate("set_field", path="content/weapons/gun.json", field="shootStatus", value=None)["ok"]
    assert client.state() == before
    assert client.mutate("set_field", path="content/weapons/gun.json", field="shootStatus", value="")["ok"]


@pytest.mark.parametrize("field,query", [("health", ""), ("itemDrop", "x" * 257), ("itemDrop", None), ("itemDrop", [])])
def test_bad_reference_lookup_does_not_mutate(project, field, query):
    client = Client(project)
    before = client.state()
    result = client.call("reference_candidates", path=PATH, field=field, query=query)
    assert not result["ok"] and result["error"]["code"] == "INVALID_REFERENCE"
    assert client.state() == before


def test_reference_source_without_instances_returns_empty_and_unknown_current(project):
    data = json.loads((project / PATH).read_text())
    data["category"] = "defense"
    (project / PATH).write_text(json.dumps(data), encoding="utf-8")
    client = Client(project)
    result = client.call("reference_candidates", path=PATH, field="category", query="")
    assert result["ok"], result
    assert result["data"]["candidates"] == []
    assert result["data"]["current"]["known"] is False
    assert client.state()["documents"][0]["data"]["category"] == "defense"


def test_candidate_reads_are_not_copied_into_mutation_result_cache(project):
    client = Client(project)
    envelope = {"protocolVersion": 1, "sessionId": client.sid, "requestId": "read-candidates",
                "action": "reference_candidates", "payload": {"path": PATH, "field": "itemDrop", "query": ""}}
    assert client.service.request(envelope)["ok"]
    assert client.service.request_result("read-candidates") == {"state": "unknown"}


def test_duplicate_selection_and_old_session_requests_are_safe(project):
    client = Client(project)
    envelope = {"protocolVersion": 1, "sessionId": client.sid, "requestId": "select-once", "action": "set_field",
                "payload": {"path": PATH, "field": "itemDrop", "value": "lead", "expectedRevision": client.state()["revision"]}}
    first = client.service.request(envelope)
    assert first["ok"] and client.service.request(envelope) == first
    assert client.mutate("undo")["ok"]
    assert client.state()["documents"][0]["data"]["itemDrop"] == "copper"
    assert not client.state()["history"]["canUndo"]
    opened = client.call("open_project", path=str(project))
    assert opened["ok"] and opened["sessionId"] != client.sid
    stale = client.call("reference_candidates", path=PATH, field="itemDrop", query="")
    assert not stale["ok"] and stale["error"]["code"] == "STALE_SESSION"
    assert client.service.request(envelope)["error"]["code"] == "STALE_SESSION"


def test_project_candidates_and_same_name_categories_use_declared_source(project, tmp_path):
    # Actual offline metadata currently has no top-level UnitTypes STRING_REF.
    # This disk metadata fixture verifies the public generic reference contract
    # without inventing a production field or treating ObjectMap as a string.
    metadata = tmp_path / "metadata"
    (metadata / "classes").mkdir(parents=True)
    (metadata / "manifest.json").write_text('{"classes":["Wall"],"instanceCategories":["UnitTypes","Blocks"]}')
    definition = {"name": "Wall", "fields": [
        {"name": "itemDrop", "mode": "STRING_REF", "javaType": "UnitType", "refSource": "UnitTypes"},
        {"name": "lightLiquid", "mode": "STRING_REF", "javaType": "Block", "refSource": "Blocks"}]}
    (metadata / "classes/Wall.json").write_text(json.dumps(definition))
    for category in ("units", "blocks"):
        (project / f"content/{category}").mkdir(exist_ok=True)
        (project / f"content/{category}/same.json").write_text('{}')
    (project / "content/blocks/only-block.json").write_text('{}')
    client = Client(project, metadata)
    for field, category in (("itemDrop", "UnitTypes"), ("lightLiquid", "Blocks")):
        result = client.call("reference_candidates", path=PATH, field=field, query="refs-same")
        assert result["ok"] and result["data"]["candidates"] == [{"value": "refs-same", "category": category, "label": "refs-same", "isProject": True}]
    assert not client.mutate("set_field", path=PATH, field="itemDrop", value="refs-only-block")["ok"]
    assert client.mutate("set_field", path=PATH, field="itemDrop", value="refs-same")["ok"]
    assert client.mutate("save_opened")["ok"]
    assert Client(project, metadata).state()["documents"][0]["data"]["itemDrop"] == "refs-same"
    # Only offline candidates are cached; new project content is reflected live.
    (project / "content/units/later.json").write_text('{}')
    result = client.call("reference_candidates", path=PATH, field="itemDrop", query="refs-later")
    assert result["data"]["candidates"][0]["value"] == "refs-later"


def test_specialized_fields_and_ammo_mapping_remain_readonly(project):
    target = project / "content/blocks/turret.json"
    target.write_text(json.dumps({"type": "ItemTurret", "ammoTypes": {"copper": {"damage": 10}}, "research": "duo"}))
    client = Client(project)
    result = client.call("read_document", path="content/blocks/turret.json")
    assert result["ok"]
    fields = {field["name"]: field for group in result["data"]["form"]["groups"] for field in group["fields"]}
    for field in ("ammoTypes", "research"):
        assert fields[field]["control"] == "readonly"
        assert not client.call("reference_candidates", path="content/blocks/turret.json", field=field, query="")["ok"]
