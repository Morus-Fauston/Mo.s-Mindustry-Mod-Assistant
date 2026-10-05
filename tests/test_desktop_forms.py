"""Basic forms through real serialized requests and existing-format files."""

import json
from itertools import count

import pytest

from app.desktop.workspace import WorkspaceService


UNIT = "content/units/same.json"
BLOCK = "content/blocks/same.json"


class Client:
    def __init__(self, root):
        self.root = root
        self.service = WorkspaceService("metadata")
        self.ids = count()
        self.sid = None
        opened = self.call("open_project", path=str(root))
        assert opened["ok"], opened
        self.sid = opened["sessionId"]

    def call(self, action, **payload):
        return self.service.request({"protocolVersion": 1, "sessionId": self.sid,
            "requestId": str(next(self.ids)), "action": action, "payload": payload})

    def state(self):
        result = self.call("editing_state")
        assert result["ok"], result
        return result["data"]

    def mutate(self, action, **payload):
        return self.call(action, expectedRevision=self.state()["revision"], **payload)

    def document(self, path=UNIT):
        return next(d for d in self.state()["documents"] if d["path"] == path)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "mod.json").write_text('{"name":"forms"}', encoding="utf-8")
    for path, data in ((UNIT, {"type": "flying", "health": 100}),
                       (BLOCK, {"type": "Wall", "health": 500, "size": 1})):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data), encoding="utf-8")
    return root


def fields(document):
    return {f["name"]: f for g in document["form"]["groups"] for f in g["fields"]}


def groups(document):
    return {g["id"]: g for g in document["form"]["groups"]}


def test_open_returns_authoritative_form_and_does_not_materialize_defaults(project):
    client = Client(project)
    before = (project / UNIT).read_bytes()
    result = client.call("read_document", path=UNIT)
    assert result["ok"], result
    document = result["data"]
    form = fields(document)
    assert form["health"]["control"] == "number"
    assert form["health"]["label"] == "生命值"
    assert form["health"]["help"]
    assert form["armor"]["present"] is False
    assert form["armor"]["defaultSource"]
    assert form["armor"]["deletable"] is False
    assert form["name"]["readOnly"] is True
    assert form["name"]["displayValue"] == "same"
    assert form["weapons"]["control"] == "weapon_array"
    assert form["weapons"]["items"] == []
    assert groups(document)["basic"]["locked"] is True
    assert groups(document)["mining"]["enabled"] is False
    assert document["data"] == {"type": "flying", "health": 100}
    assert document["dirty"] is False
    assert client.state()["revision"] == document["revision"]
    assert client.state()["history"]["canUndo"] is False
    assert (project / UNIT).read_bytes() == before


@pytest.mark.parametrize(("path", "field", "payload", "expected"), [
    (UNIT, "health", {"text": "137.5"}, 137.5),
    (UNIT, "health", {"text": "0"}, 0),
    (UNIT, "description", {"text": "中文说明\n第二行"}, "中文说明\n第二行"),
    (UNIT, "description", {"text": ""}, ""),
    (UNIT, "description", {"value": None}, None),
    (UNIT, "flying", {"value": False}, False),
    (BLOCK, "size", {"text": "2147483647"}, 2147483647),
])
def test_primitive_edits_undo_save_and_reopen(project, path, field, payload, expected):
    original = json.loads((project / path).read_text())
    if field == "description":
        original[field] = "原说明"
        (project / path).write_text(json.dumps(original), encoding="utf-8")
    client = Client(project)
    assert client.call("read_document", path=path)["ok"]
    result = client.mutate("set_field", path=path, field=field, **payload)
    assert result["ok"], result
    assert client.document(path)["data"][field] == expected
    assert client.mutate("undo")["ok"]
    assert client.document(path)["data"] == original
    assert client.mutate("redo")["ok"]
    assert client.mutate("save_opened")["ok"]
    fresh = Client(project)
    reopened = fresh.call("read_document", path=path)["data"]
    assert reopened["data"][field] == expected
    assert reopened["dirty"] is False


@pytest.mark.parametrize(("field", "payload"), [
    ("health", {"text": ""}), ("health", {"text": "-"}),
    ("health", {"text": "1e"}), ("health", {"text": "NaN"}),
    ("health", {"text": "1e999"}), ("health", {"text": "-1"}),
    ("health", {"value": True}), ("health", {"value": None}),
    ("health", {"value": 42, "text": "42"}), ("health", {}),
    ("health", {"text": "1e39"}), ("size", {"text": "2.5"}),
    ("size", {"text": "2147483648"}), ("size", {"value": "3"}),
    ("destructible", {"value": 1}), ("name", {"text": "changed"}),
    ("type", {"text": "UnitType"}), ("unknown", {"value": 3}),
    ("health.x", {"value": 3}),
])
def test_invalid_primitive_requests_leave_data_revision_and_history_unchanged(project, field, payload):
    client = Client(project)
    assert client.call("read_document", path=BLOCK)["ok"]
    before = client.state()
    result = client.mutate("set_field", path=BLOCK, field=field, **payload)
    assert result["ok"] is False
    assert client.state() == before


@pytest.mark.parametrize(("original", "payload", "expected", "swatch"), [
    ("ff000080", {"value": "#123456"}, "12345680", "#123456"),
    ("#ff000080", {"value": "#abcdef"}, "#abcdef80", "#abcdef"),
    ({"r": 1, "g": 0.5, "b": 0, "a": 0.3}, {"value": "#00ff00"},
     {"r": 0, "g": 1, "b": 0, "a": 0.3}, "#00ff00"),
    ("ff000080", {"text": "00FF00"}, "00FF00", "#00ff00"),
    ("ffffff", {"text": "12345678"}, "12345678", "#123456"),
    ("ffffff", {"text": '{"r":0,"g":1,"b":0,"a":0.4}'},
     {"r": 0, "g": 1, "b": 0, "a": 0.4}, "#00ff00"),
])
def test_color_text_and_picker_preserve_alpha_and_undo(project, original, payload, expected, swatch):
    data = {"type": "flying", "health": 100, "outlineColor": original}
    (project / UNIT).write_text(json.dumps(data), encoding="utf-8")
    client = Client(project)
    assert client.call("read_document", path=UNIT)["ok"]
    assert client.document()["data"]["outlineColor"] == original
    assert client.document()["dirty"] is False
    result = client.mutate("set_field", path=UNIT, field="outlineColor", **payload)
    assert result["ok"], result
    assert client.document()["data"]["outlineColor"] == expected
    assert fields(client.document())["outlineColor"]["swatchHex"] == swatch
    assert client.mutate("undo")["ok"]
    assert client.document()["data"]["outlineColor"] == original
    assert client.mutate("redo")["ok"]
    assert client.mutate("save_opened")["ok"]
    fresh = Client(project)
    assert fresh.call("read_document", path=UNIT)["data"]["data"]["outlineColor"] == expected


@pytest.mark.parametrize("value", ["", "red", "fff", "#1234567", "url(x)",
    {"r": 1, "g": 0, "b": 0, "a": 2}, {"r": True, "g": 0, "b": 0},
    {"r": 0, "g": 0, "b": 0, "extra": 1}, None, 12])
def test_invalid_color_is_rejected_without_replacing_original(project, value):
    (project / UNIT).write_text(json.dumps({"type": "flying", "outlineColor": "12345678"}), encoding="utf-8")
    client = Client(project)
    assert client.call("read_document", path=UNIT)["ok"]
    before = client.state()
    result = client.mutate("set_field", path=UNIT, field="outlineColor", value=value)
    assert not result["ok"]
    assert client.state() == before


def test_capability_cache_linkage_and_history_are_one_atomic_operation(project):
    client = Client(project)
    assert client.call("read_document", path=UNIT)["ok"]
    original = client.document()["data"]
    result = client.mutate("set_capability", path=UNIT, group="mining", enabled=True)
    assert result["ok"], result
    current = client.document()
    assert current["data"]["mineSpeed"] == 0
    assert groups(current)["mining"]["enabled"] is True
    assert groups(current)["capacity"]["enabled"] is True
    assert "itemCapacity" not in current["data"]
    assert client.mutate("undo")["ok"]
    assert client.document()["data"] == original
    assert groups(client.document())["capacity"]["enabled"] is False
    assert client.mutate("redo")["ok"]
    assert groups(client.document())["capacity"]["enabled"] is True
    assert client.mutate("set_field", path=UNIT, field="mineSpeed", text="3.75")["ok"]
    assert client.mutate("set_capability", path=UNIT, group="mining", enabled=False)["ok"]
    assert "mineSpeed" not in client.document()["data"]
    assert groups(client.document())["capacity"]["enabled"] is True
    assert client.mutate("set_capability", path=UNIT, group="mining", enabled=True)["ok"]
    assert client.document()["data"]["mineSpeed"] == 3.75
    assert client.mutate("set_capability", path=UNIT, group="mining", enabled=False)["ok"]
    assert client.mutate("set_capability", path=UNIT, group="capacity", enabled=False)["ok"]
    assert client.mutate("set_capability", path=UNIT, group="capacity", enabled=True)["ok"]
    assert groups(client.document())["mining"]["enabled"] is False


def test_add_and_delete_allowed_fields_and_group_restore_cached_value(project):
    client = Client(project)
    assert client.call("read_document", path=UNIT)["ok"]
    assert "description" in {f["name"] for f in groups(client.document())["basic"]["addableFields"]}
    assert client.mutate("add_field", path=UNIT, group="basic", field="description")["ok"]
    assert client.mutate("set_field", path=UNIT, field="description", text="新说明")["ok"]
    assert client.mutate("delete_field", path=UNIT, field="description")["ok"]
    assert "description" not in client.document()["data"]
    assert client.mutate("undo")["ok"]
    assert client.document()["data"]["description"] == "新说明"
    assert client.mutate("add_group", path=UNIT, group="appearance")["ok"]
    assert client.mutate("set_field", path=UNIT, field="lightRadius", text="21")["ok"]
    assert client.mutate("delete_group", path=UNIT, group="appearance")["ok"]
    assert "appearance" not in groups(client.document())
    assert "lightRadius" not in client.document()["data"]
    assert client.mutate("add_group", path=UNIT, group="appearance")["ok"]
    assert client.document()["data"]["lightRadius"] == 21
    assert client.mutate("undo")["ok"]
    assert "appearance" not in groups(client.document())


def test_other_group_is_locked_but_its_fields_can_be_deleted_and_undone(project):
    data = {"type": "flying", "health": 100, "legLength": 4}
    (project / UNIT).write_text(json.dumps(data), encoding="utf-8")
    client = Client(project)
    assert client.call("read_document", path=UNIT)["ok"]
    other = groups(client.document())["_other"]
    assert other["locked"] is True
    assert next(field for field in other["fields"] if field["name"] == "legLength")["deletable"] is True
    before = client.state()
    assert not client.mutate("delete_group", path=UNIT, group="_other")["ok"]
    assert client.state() == before
    assert client.mutate("delete_field", path=UNIT, field="legLength")["ok"]
    assert "legLength" not in client.document()["data"]
    assert "_other" not in groups(client.document())
    assert client.mutate("undo")["ok"]
    assert client.document()["data"] == data
    assert groups(client.document())["_other"]["locked"] is True


def test_unlocked_group_with_required_fields_can_be_deleted_and_restored(project):
    data = {"type": "flying", "health": 100, "research": {"parent": "dagger"}}
    (project / UNIT).write_text(json.dumps(data), encoding="utf-8")
    client = Client(project)
    assert client.call("read_document", path=UNIT)["ok"]
    assert groups(client.document())["tech_tree"]["locked"] is False
    assert not client.mutate("delete_field", path=UNIT, field="research")["ok"]
    deleted = client.mutate("delete_group", path=UNIT, group="tech_tree")
    assert deleted["ok"], deleted
    assert "tech_tree" not in groups(client.document())
    assert "research" not in client.document()["data"]
    assert "tech_tree" in {g["id"] for g in client.document()["form"]["addableGroups"]}
    assert client.mutate("undo")["ok"]
    assert client.document()["data"] == data
    assert "tech_tree" in groups(client.document())
    assert client.mutate("redo")["ok"]
    assert client.mutate("add_group", path=UNIT, group="tech_tree")["ok"]
    assert client.document()["data"] == data


@pytest.mark.parametrize(("action", "payload"), [
    ("delete_field", {"field": "health"}), ("delete_field", {"field": "name"}),
    ("delete_field", {"field": "type"}), ("delete_group", {"group": "basic"}),
    ("delete_group", {"group": "movement"}),
    ("set_capability", {"group": "basic", "enabled": False}),
    ("set_capability", {"group": "mining", "enabled": 1}),
    ("add_group", {"group": "tank"}), ("add_group", {"group": "basic"}),
    ("add_field", {"group": "basic", "field": "engineSize"}),
    ("add_field", {"group": "basic", "field": "name"}),
])
def test_forged_group_and_field_permissions_cannot_bypass_current_plan(project, action, payload):
    client = Client(project)
    assert client.call("read_document", path=UNIT)["ok"]
    before = client.state()
    assert not client.mutate(action, path=UNIT, **payload)["ok"]
    assert client.state() == before


def test_discard_restores_data_and_form_memory_and_undo_reopens_them_together(project):
    client = Client(project)
    assert client.call("read_document", path=UNIT)["ok"]
    original = client.document()["data"]
    assert client.mutate("set_capability", path=UNIT, group="mining", enabled=True)["ok"]
    assert client.mutate("set_field", path=UNIT, field="mineSpeed", text="7")["ok"]
    assert client.mutate("set_capability", path=UNIT, group="mining", enabled=False)["ok"]
    # JSON is back at baseline, but cached mining and enabled capacity differ.
    assert client.document()["data"] == original
    assert groups(client.document())["capacity"]["enabled"] is True
    assert client.mutate("close_documents", paths=[UNIT], decision="discard")["ok"]
    assert client.state()["documents"] == []
    assert client.call("read_document", path=UNIT)["ok"]
    assert groups(client.document())["capacity"]["enabled"] is False
    assert client.mutate("undo")["ok"]
    assert groups(client.document())["capacity"]["enabled"] is True
    assert client.mutate("set_capability", path=UNIT, group="mining", enabled=True)["ok"]
    assert client.document()["data"]["mineSpeed"] == 7
    assert client.mutate("close_documents", paths=[UNIT], decision="discard")["ok"]
    assert client.state()["documents"] == []
    # Undo the actual discard reopens the document through existing history.
    assert client.mutate("undo")["ok"]
    assert client.document()["data"]["mineSpeed"] == 7
    assert groups(client.document())["mining"]["enabled"] is True


def test_saved_form_cache_survives_tab_close_but_not_new_session(project):
    client = Client(project)
    assert client.call("read_document", path=UNIT)["ok"]
    assert client.mutate("set_capability", path=UNIT, group="mining", enabled=True)["ok"]
    assert client.mutate("set_field", path=UNIT, field="mineSpeed", text="9")["ok"]
    assert client.mutate("set_capability", path=UNIT, group="mining", enabled=False)["ok"]
    assert client.mutate("save_opened")["ok"]
    assert client.mutate("close_documents", paths=[UNIT], decision="discard")["ok"]
    assert client.call("read_document", path=UNIT)["ok"]
    assert client.mutate("set_capability", path=UNIT, group="mining", enabled=True)["ok"]
    assert client.document()["data"]["mineSpeed"] == 9
    fresh = Client(project)
    assert fresh.call("read_document", path=UNIT)["ok"]
    assert groups(fresh.document())["capacity"]["enabled"] is False
    assert fresh.mutate("set_capability", path=UNIT, group="mining", enabled=True)["ok"]
    assert fresh.document()["data"]["mineSpeed"] == 0


def test_dependency_hints_preserve_values_and_clear_when_prerequisite_changes(project):
    data = {"type": "flying", "health": 100, "engineSize": 0, "engineOffset": 8,
            "canBoost": False, "boostMultiplier": 2}
    (project / UNIT).write_text(json.dumps(data), encoding="utf-8")
    client = Client(project)
    assert client.call("read_document", path=UNIT)["ok"]
    first = fields(client.document())
    assert first["engineOffset"]["inactiveReason"]
    assert "engineSize" not in first["engineOffset"]["inactiveReason"]
    assert first["engineOffset"]["validationError"] == ""
    assert first["boostMultiplier"]["inactiveReason"]
    assert client.document()["data"] == data
    assert client.document()["dirty"] is False
    assert client.mutate("set_field", path=UNIT, field="engineSize", text="2")["ok"]
    assert fields(client.document())["engineOffset"]["inactiveReason"] == ""
    assert client.document()["data"]["engineOffset"] == 8
    assert client.mutate("set_field", path=UNIT, field="canBoost", value=True)["ok"]
    assert fields(client.document())["boostMultiplier"]["inactiveReason"] == ""
    assert client.document()["data"]["boostMultiplier"] == 2


def test_same_name_categories_do_not_share_cache_and_stale_group_requests_are_rejected(project):
    (project / BLOCK).write_text('{"type":"Wall","health":500,"lightRadius":42}', encoding="utf-8")
    (project / UNIT).write_text('{"type":"flying","health":100,"lightRadius":7}', encoding="utf-8")
    client = Client(project)
    assert client.call("read_document", path=UNIT)["ok"]
    assert client.call("read_document", path=BLOCK)["ok"]
    revision = client.state()["revision"]
    assert client.mutate("delete_group", path=UNIT, group="appearance")["ok"]
    assert client.mutate("delete_group", path=BLOCK, group="visual")["ok"]
    assert client.call("add_group", path=UNIT, group="appearance", expectedRevision=revision)["error"]["code"] == "STALE_REVISION"
    assert client.mutate("add_group", path=UNIT, group="appearance")["ok"]
    assert client.document()["data"]["lightRadius"] == 7
    assert client.mutate("add_group", path=BLOCK, group="visual")["ok"]
    assert client.document(BLOCK)["data"]["lightRadius"] == 42
    request = {"protocolVersion": 1, "sessionId": client.sid, "requestId": "duplicate-group",
        "action": "delete_group", "payload": {"path": UNIT, "group": "appearance", "expectedRevision": client.state()["revision"]}}
    first = client.service.request(request)
    assert first["ok"]
    assert client.service.request(request) == first
    opened = client.mutate("open_project", path=str(project), discard=True)
    assert opened["ok"]
    assert client.service.request(request)["error"]["code"] == "STALE_SESSION"


def test_correcting_imported_boolean_in_numeric_field_changes_type_and_dirty(project):
    (project / UNIT).write_text('{"type":"flying","health":false}', encoding="utf-8")
    client = Client(project)
    assert client.call("read_document", path=UNIT)["ok"]
    assert fields(client.document())["health"]["validationError"]
    assert client.mutate("set_field", path=UNIT, field="health", text="0")["ok"]
    assert type(client.document()["data"]["health"]) in (int, float)
    assert client.document()["dirty"] is True
    assert fields(client.document())["health"]["validationError"] == ""
    assert client.mutate("undo")["ok"]
    assert client.document()["data"]["health"] is False
    assert client.document()["dirty"] is False


@pytest.mark.parametrize(("original", "corrected"), [(0, False), (1, True)])
def test_correcting_imported_number_in_boolean_field_survives_discard_history(project, original, corrected):
    (project / UNIT).write_text(json.dumps({"type": "flying", "health": 100, "flying": original}), encoding="utf-8")
    client = Client(project)
    assert client.call("read_document", path=UNIT)["ok"]
    assert fields(client.document())["flying"]["validationError"]
    assert client.mutate("set_field", path=UNIT, field="flying", value=corrected)["ok"]
    assert client.document()["data"]["flying"] is corrected
    assert client.document()["dirty"] is True
    assert client.mutate("close_documents", paths=[UNIT], decision="discard")["ok"]
    assert client.call("read_document", path=UNIT)["ok"]
    assert type(client.document()["data"]["flying"]) is int
    assert client.document()["data"]["flying"] == original
    assert client.document()["dirty"] is False
    assert client.mutate("undo")["ok"]
    assert client.document()["data"]["flying"] is corrected
    assert client.document()["dirty"] is True


def test_content_type_cannot_read_arbitrary_metadata_file(project):
    outside = project.parent / "outside.json"
    outside.write_text(json.dumps({"name": "outside", "fields": [{"name": "secret", "javaType": "String", "mode": "PRIMITIVE"}]}), encoding="utf-8")
    (project / UNIT).write_text(json.dumps({"type": str(outside.with_suffix("")), "secret": "present"}), encoding="utf-8")
    client = Client(project)
    opened = client.call("read_document", path=UNIT)
    assert opened["ok"], opened
    assert fields(opened["data"]) == {}


def test_capability_with_required_fields_can_be_disabled_without_default_writes(project):
    (project / BLOCK).write_text('{"type":"Drill","health":500,"tier":3,"drillTime":280}', encoding="utf-8")
    client = Client(project)
    assert client.call("read_document", path=BLOCK)["ok"]
    assert groups(client.document(BLOCK))["mining"]["enabled"] is True
    assert client.mutate("set_capability", path=BLOCK, group="mining", enabled=False)["ok"]
    disabled = client.document(BLOCK)
    assert "tier" not in disabled["data"]
    assert groups(disabled)["mining"]["enabled"] is False
    assert client.mutate("set_capability", path=BLOCK, group="mining", enabled=True)["ok"]
    assert client.document(BLOCK)["data"]["tier"] == 3
    assert client.document(BLOCK)["data"]["drillTime"] == 280


@pytest.mark.parametrize("extra", [{}, {"research": "copper"}, {"research": {"parent": "copper"}}])
def test_research_route_uses_reference_type_for_missing_string_and_object_values(project, extra):
    data = {"type": "flying", "health": 100, **extra}
    (project / UNIT).write_text(json.dumps(data), encoding="utf-8")
    client = Client(project)
    opened = client.call("read_document", path=UNIT)
    assert opened["ok"], opened
    research = fields(opened["data"])["research"]
    assert research["fieldType"] == "ref"
    assert research["control"] == "readonly"
    assert opened["data"]["data"] == data
    assert opened["data"]["dirty"] is False


def test_configured_resource_routes_override_inferred_value_types(project):
    data = {"type": "GenericCrafter", "health": 100,
            "outputItem": {"item": "copper", "amount": 2},
            "outputLiquid": "water/1", "requirements": ["copper/2"],
            "consumes": {"power": 1}, "shownPlanets": ["serpulo"]}
    (project / BLOCK).write_text(json.dumps(data), encoding="utf-8")
    client = Client(project)
    opened = client.call("read_document", path=BLOCK)
    assert opened["ok"], opened
    form = fields(opened["data"])
    assert form["outputItem"]["fieldType"] == "ref"
    assert form["outputLiquid"]["fieldType"] == "ref"
    assert form["requirements"]["fieldType"] == "arr"
    assert form["consumes"]["fieldType"] == "obj"
    assert form["shownPlanets"]["fieldType"] == "arr"
    assert form["outputItem"]["control"] == "resource_slot"
    assert form["outputLiquid"]["control"] == "resource_slot" and form["outputLiquid"]["readOnly"]
    assert form["requirements"]["control"] == "resource_list" and form["requirements"]["rows"][0]["notice"]
    assert form["consumes"]["control"] == "consumes"
    assert opened["data"]["data"] == data
    assert opened["data"]["dirty"] is False
