"""Weapon edits through the real serialized workspace, files and shared history."""

from copy import deepcopy
from itertools import count
import json

import pytest

from app.desktop.workspace import WorkspaceService


UNIT = "content/units/unit.json"
SOURCE = "content/weapons/gun.json"


def fields(plan):
    return {field["name"]: field for group in plan["groups"] for field in group["fields"]}


class WorkspaceProbe:
    def __init__(self, root):
        self.service = WorkspaceService("metadata")
        self.ids, self.sid = count(), None
        self.sid = self.call("open_project", path=str(root))["sessionId"]

    def envelope(self, action, **payload):
        return {"protocolVersion": 1, "requestId": f"weapon-{next(self.ids)}",
                "sessionId": self.sid, "action": action, "payload": payload}

    def response(self, action, **payload):
        return self.service.request(self.envelope(action, **payload))

    def call(self, action, **payload):
        result = self.response(action, **payload)
        assert result["ok"], result
        return result["data"]

    def state(self):
        return self.call("editing_state")

    def change(self, action, **payload):
        return self.call(action, expectedRevision=self.state()["revision"], **payload)

    def document(self, path=UNIT):
        return next(document for document in self.state()["documents"] if document["path"] == path)

    def items(self):
        return fields(self.document()["form"])["weapons"]["items"]


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "weapon-project"
    for category in ("units", "blocks", "weapons"):
        (root / "content" / category).mkdir(parents=True)
    (root / "mod.json").write_text('{"name":"probe"}', encoding="utf-8")
    (root / UNIT).write_text(json.dumps({"type": "mech", "weapons": [], "health": 137}), encoding="utf-8")
    (root / SOURCE).write_text(json.dumps({"name": "gun", "reload": 18, "x": 2,
        "bullet": {"type": "BasicBulletType", "damage": 9}}), encoding="utf-8")
    return root


def test_real_weapon_commands_deduplicate_preserve_source_and_roundtrip(project):
    source_bytes = (project / SOURCE).read_bytes()
    probe = WorkspaceProbe(project)
    probe.call("read_document", path=UNIT)
    standalone = probe.call("read_document", path=SOURCE)
    assert fields(standalone["form"])["name"]["readOnly"]
    candidates = probe.call("weapon_reference_candidates", path=UNIT, objectPath=[], field="weapons", query="probe-gun")
    assert [item["value"] for item in candidates["candidates"]] == ["probe-gun"]
    assert candidates["categories"] == [{"id": "Weapons", "label": "武器"}]
    envelope = probe.envelope("weapon_add", path=UNIT, objectPath=[], field="weapons",
                              mode="reference", name="probe-gun", expectedRevision=probe.state()["revision"])
    first = probe.service.request(envelope)
    assert first["ok"] and probe.service.request(envelope) == first
    reference = probe.items()[0]
    assert len(probe.items()) == 1 and reference["mode"] == "reference"
    unchanged = probe.state()
    stale = probe.response("weapon_add", path=UNIT, field="weapons", mode="inline", name="stale",
                           expectedRevision=envelope["payload"]["expectedRevision"])
    assert stale["error"]["code"] == "STALE_REVISION" and probe.state() == unchanged
    conflicting = deepcopy(envelope)
    conflicting["payload"]["name"] = "different"
    assert probe.service.request(conflicting)["error"]["code"] == "REQUEST_CONFLICT"
    assert probe.state() == unchanged

    probe.change("weapon_add", path=UNIT, field="weapons", mode="inline", name="gun", bulletType="LaserBulletType")
    inline = probe.items()[1]
    probe.change("weapon_add_override", path=UNIT, objectPath=reference["objectPath"], field="rotateSpeed")
    probe.change("set_field", path=UNIT, objectPath=reference["objectPath"], field="x", text="7")
    before_expand = deepcopy(probe.document()["data"])
    probe.change("weapon_expand", path=UNIT, objectPath=reference["objectPath"])
    expanded = probe.document()["data"]["weapons"][0]
    assert expanded == {"name": "gun", "reload": 1.0, "x": 7.0, "y": 0.0,
                        "top": True, "rotate": False, "mirror": True, "rotateSpeed": 5.0,
                        "bullet": {"type": "BasicBulletType", "damage": 9}}
    assert probe.items()[0]["itemId"] == reference["itemId"]
    assert probe.document(SOURCE)["data"] == json.loads(source_bytes)
    assert (project / SOURCE).read_bytes() == source_bytes
    probe.change("undo")
    assert probe.document()["data"] == before_expand
    probe.change("redo")
    probe.change("weapon_move", path=UNIT, field="weapons", itemId=reference["itemId"], beforeItemId=None)
    assert [item["itemId"] for item in probe.items()] == [inline["itemId"], reference["itemId"]]
    probe.change("set_field", path=UNIT, objectPath=[*reference["objectPath"], "bullet"], field="damage", text="21")
    assert [item["bullet"]["damage"] for item in probe.document()["data"]["weapons"]] == [1, 21]
    probe.change("weapon_remove", path=UNIT, field="weapons", itemId=inline["itemId"])
    removed = probe.state()
    rejected = probe.response("set_field", path=UNIT, objectPath=inline["objectPath"], field="x", value=99,
                              expectedRevision=removed["revision"])
    assert not rejected["ok"] and probe.state() == removed
    probe.change("undo")
    assert [item["itemId"] for item in probe.items()] == [inline["itemId"], reference["itemId"]]
    saved = deepcopy(probe.document()["data"])
    probe.change("save_opened")
    assert json.loads((project / UNIT).read_text(encoding="utf-8")) == saved
    assert json.loads((project / SOURCE).read_text(encoding="utf-8")) == json.loads(source_bytes)
    probe.change("close_documents", paths=[UNIT], decision="discard")
    assert probe.call("read_document", path=UNIT)["data"] == saved
    fresh = WorkspaceProbe(project)
    reopened = fresh.call("read_document", path=UNIT)
    assert reopened["data"] == saved and not reopened["dirty"]
    assert len(fields(reopened["form"])["weapons"]["items"]) == 2


@pytest.mark.parametrize("action,payload", [
    ("weapon_add", {"field": "weapons", "mode": "inline", "name": "../outside"}),
    ("weapon_add", {"field": "weapons", "mode": "reference", "name": "not-a-candidate"}),
    ("weapon_add", {"field": "weapons", "mode": "inline", "name": "gun", "bulletType": "UnknownBullet"}),
    ("weapon_move", {"field": "weapons", "itemId": "0" * 32, "beforeItemId": None}),
    ("weapon_expand", {"objectPath": ["weapons", {"itemId": "0" * 32}], "allowBlank": True}),
])
def test_invalid_bridge_weapon_input_keeps_data_revision_history_and_disk(project, action, payload):
    probe = WorkspaceProbe(project)
    probe.call("read_document", path=UNIT)
    before, disk = probe.state(), (project / UNIT).read_bytes()
    failed = probe.response(action, path=UNIT, expectedRevision=before["revision"], **payload)
    assert not failed["ok"] and failed["error"]["message"]
    assert probe.state() == before and (project / UNIT).read_bytes() == disk


@pytest.mark.parametrize("source", ["{ broken", "[]", '{"name":"missing","bullet":{"damage":Infinity}}'])
def test_broken_source_never_becomes_blank_inline_even_with_confirmation(project, source):
    (project / UNIT).write_text(json.dumps({"type": "mech", "weapons": [{"name": "missing", "x": 8}]}), encoding="utf-8")
    (project / "content/weapons/missing.json").write_text(source, encoding="utf-8")
    probe = WorkspaceProbe(project)
    probe.call("read_document", path=UNIT)
    item, before = probe.items()[0], probe.state()
    response = probe.response("weapon_expand", path=UNIT, objectPath=item["objectPath"], allowBlank=True,
                              expectedRevision=before["revision"])
    assert not response["ok"] and response["error"]["code"] == "INVALID_FORM_ACTION"
    assert probe.state() == before
    assert (project / "content/weapons/missing.json").read_text(encoding="utf-8") == source
    choices = probe.call("weapon_reference_candidates", path=UNIT, field="weapons", query="probe-gun")
    assert [candidate["value"] for candidate in choices["candidates"]] == ["probe-gun"]


def test_missing_source_blank_requires_confirmation_and_undo_restores_reference(project):
    original = {"type": "mech", "weapons": [{"name": "missing", "x": 8, "custom": {"keep": True}}]}
    (project / UNIT).write_text(json.dumps(original), encoding="utf-8")
    probe = WorkspaceProbe(project)
    probe.call("read_document", path=UNIT)
    item, before = probe.items()[0], probe.state()
    assert item["canCreateBlank"] and not item["canExpand"]
    for confirmation in (None, False, "true"):
        response = probe.response("weapon_expand", path=UNIT, objectPath=item["objectPath"],
                                  expectedRevision=before["revision"], **({} if confirmation is None else {"allowBlank": confirmation}))
        assert not response["ok"] and probe.state() == before
    probe.change("weapon_expand", path=UNIT, objectPath=item["objectPath"], allowBlank=True)
    assert probe.document()["data"]["weapons"][0] == {**original["weapons"][0], "reload": 1.0,
        "bullet": {"type": "BasicBulletType", "damage": 1.0, "speed": 1.0}}
    probe.change("undo")
    assert probe.document()["data"] == original and probe.items()[0]["itemId"] == item["itemId"]


def test_weapon_session_switch_rejects_cached_and_uncached_old_requests(project, tmp_path):
    probe = WorkspaceProbe(project)
    probe.call("read_document", path=UNIT)
    envelope = probe.envelope("weapon_add", path=UNIT, field="weapons", mode="inline", name="old",
                              expectedRevision=probe.state()["revision"])
    assert probe.service.request(envelope)["ok"]
    other = tmp_path / "other"
    (other / "content/units").mkdir(parents=True)
    (other / "mod.json").write_text('{"name":"other"}', encoding="utf-8")
    (other / UNIT).write_text('{"type":"mech","weapons":[]}', encoding="utf-8")
    opened = probe.change("open_project", path=str(other), discard=True)
    probe.sid = opened["sessionId"]
    probe.call("read_document", path=UNIT)
    before = probe.state()
    assert probe.service.request(envelope)["error"]["code"] == "STALE_SESSION"
    envelope["requestId"] = "uncached-old-session"
    assert probe.service.request(envelope)["error"]["code"] == "STALE_SESSION"
    assert probe.state() == before


def test_weapon_spawn_unit_abilities_use_same_bridge_addresses_and_history(project):
    original = {"type": "mech", "weapons": [{"name": "outer", "bullet": {
        "spawnUnit": {"type": "mech", "abilities": [{"type": "RegenAbility", "amount": 1}],
                      "weapons": [{"name": "inner", "bullet": {"damage": 2}}]}}}]}
    (project / UNIT).write_text(json.dumps(original), encoding="utf-8")
    probe = WorkspaceProbe(project)
    probe.call("read_document", path=UNIT)
    outer = probe.items()[0]
    spawn = fields(fields(outer["form"])["bullet"]["child"])["spawnUnit"]["child"]
    abilities, weapons = fields(spawn)["abilities"], fields(spawn)["weapons"]
    assert abilities["control"] == "array" and weapons["control"] == "weapon_array"
    ability, inner = abilities["items"][0], weapons["items"][0]
    probe.change("set_field", path=UNIT, objectPath=ability["form"]["objectPath"], field="amount", text="4")
    probe.change("set_field", path=UNIT, objectPath=[*inner["objectPath"], "bullet"], field="damage", text="9")
    updated = probe.document()["data"]["weapons"][0]["bullet"]["spawnUnit"]
    assert updated["abilities"][0]["amount"] == 4 and updated["weapons"][0]["bullet"]["damage"] == 9
    probe.change("undo")
    probe.change("undo")
    assert probe.document()["data"] == original
    refreshed = fields(fields(probe.items()[0]["form"])["bullet"]["child"])["spawnUnit"]["child"]
    assert fields(refreshed)["abilities"]["items"][0]["itemId"] == ability["itemId"]
    assert fields(refreshed)["weapons"]["items"][0]["itemId"] == inner["itemId"]


def test_weapon_reference_name_edit_and_standalone_bullet_stay_isolated(project):
    (project / UNIT).write_text('{"type":"mech","weapons":[{"name":"missing","x":4}]}', encoding="utf-8")
    probe = WorkspaceProbe(project)
    probe.call("read_document", path=UNIT)
    probe.call("read_document", path=SOURCE)
    item = probe.items()[0]
    choices = probe.call("weapon_reference_candidates", path=UNIT, objectPath=item["objectPath"],
                         field="name", query="probe-gun")
    assert [candidate["value"] for candidate in choices["candidates"]] == ["probe-gun"]
    probe.change("set_field", path=UNIT, objectPath=item["objectPath"], field="name", value="probe-gun")
    assert probe.document()["data"]["weapons"] == [{"name": "probe-gun", "x": 4}]
    before = probe.state()
    for value in ("probe-not-weapon", "../outside", None):
        result = probe.response("set_field", path=UNIT, objectPath=item["objectPath"], field="name",
                                value=value, expectedRevision=before["revision"])
        assert not result["ok"] and probe.state() == before
    probe.change("set_field", path=SOURCE, objectPath=["bullet"], field="damage", text="17")
    assert probe.document(SOURCE)["data"]["bullet"]["damage"] == 17
    assert probe.document()["data"]["weapons"] == [{"name": "probe-gun", "x": 4}]
    probe.change("undo")
    assert probe.document(SOURCE)["data"]["bullet"]["damage"] == 9
    probe.change("undo")
    assert probe.document()["data"]["weapons"] == [{"name": "missing", "x": 4}]


def test_weapon_save_failure_retains_unsaved_data_and_history(project, monkeypatch):
    disk = (project / UNIT).read_bytes()
    probe = WorkspaceProbe(project)
    probe.call("read_document", path=UNIT)
    probe.change("weapon_add", path=UNIT, field="weapons", mode="inline", name="gun")
    before = probe.state()
    original_save = probe.service._session.save_content

    def fail_save(content):
        raise PermissionError("injected denied write")

    monkeypatch.setattr(probe.service._session, "save_content", fail_save)
    failed = probe.response("save_opened", expectedRevision=before["revision"])
    assert not failed["ok"] and failed["error"]["code"] == "SAVE_FAILED"
    assert probe.state() == before and (project / UNIT).read_bytes() == disk
    probe.change("undo")
    assert probe.document()["data"]["weapons"] == []
    probe.change("redo")
    monkeypatch.setattr(probe.service._session, "save_content", original_save)
    probe.change("save_opened")
    assert not probe.document()["dirty"]
    assert json.loads((project / UNIT).read_text(encoding="utf-8")) == probe.document()["data"]
