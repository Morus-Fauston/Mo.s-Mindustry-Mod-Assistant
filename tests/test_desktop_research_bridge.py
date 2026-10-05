"""Research and planets through the real workspace protocol and shared history."""

from copy import deepcopy
from itertools import count
import json

import pytest

from app.desktop.workspace import WorkspaceService


CONTENT = "content/blocks/wall.json"


def fields(plan):
    return {field["name"]: field for group in plan["groups"] for field in group["fields"]}


class WorkspaceProbe:
    def __init__(self, root):
        self.service = WorkspaceService("metadata")
        self.ids, self.sid = count(), None
        self.sid = self.call("open_project", path=str(root))["sessionId"]
        self.call("read_document", path=CONTENT)

    def envelope(self, action, **payload):
        return {"protocolVersion": 1, "requestId": f"research-{next(self.ids)}",
                "sessionId": self.sid, "action": action, "payload": payload}

    def response(self, action, **payload):
        return self.service.request(self.envelope(action, **payload))

    def call(self, action, **payload):
        response = self.response(action, **payload)
        assert response["ok"], response
        return response["data"]

    def state(self):
        return self.call("editing_state")

    def change(self, action, **payload):
        return self.call(action, expectedRevision=self.state()["revision"], **payload)

    def document(self):
        return next(document for document in self.state()["documents"] if document["path"] == CONTENT)

    def descriptor(self, name="research"):
        return fields(self.document()["form"])[name]

    def rows(self, collection):
        return self.descriptor()[collection]["rows"]


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "research-project"
    (root / "content/blocks").mkdir(parents=True)
    (root / "mod.json").write_text('{"name":"probe"}', encoding="utf-8")
    (root / CONTENT).write_text(json.dumps({"type": "Wall", "research": "copper-wall", "health": 137}), encoding="utf-8")
    return root


def test_legacy_string_display_and_read_candidates_do_not_write_then_edit_undo(project):
    disk = (project / CONTENT).read_bytes()
    probe = WorkspaceProbe(project)
    before = probe.state()
    assert probe.descriptor()["control"] == "research"
    envelope = probe.envelope("research_reference_candidates", path=CONTENT, objectPath=["research"], field="parent", query="copper-wall")
    candidates = probe.service.request(envelope)
    assert candidates["ok"], candidates
    assert any(row["value"] == "copper-wall" for row in candidates["data"]["candidates"])
    assert probe.service.request_result(envelope["requestId"])["state"] == "unknown"
    assert probe.state() == before and (project / CONTENT).read_bytes() == disk
    probe.change("research_set", path=CONTENT, objectPath=["research"], field="parent", value="copper-wall")
    assert probe.state() == before
    probe.change("research_set", path=CONTENT, objectPath=["research"], field="parent", value="dagger")
    assert probe.document()["data"]["research"] == {"parent": "dagger"}
    probe.change("undo")
    assert probe.document()["data"]["research"] == "copper-wall"
    probe.change("redo")
    assert probe.document()["data"]["research"] == {"parent": "dagger"}


def test_seven_fields_shared_history_stable_rows_and_save_reopen(project):
    original = {"type": "Wall", "research": {"parent": "copper-wall", "future": {"keep": True}},
                "requirements": [{"item": "copper", "amount": 2}]}
    (project / CONTENT).write_text(json.dumps(original), encoding="utf-8")
    probe = WorkspaceProbe(project)
    resource = probe.descriptor("requirements")["rows"][0]
    for name, value in (("parent", "dagger"), ("planet", "serpulo"), ("root", True),
                        ("name", "  研究根  "), ("requiresUnlock", True)):
        probe.change("research_set", path=CONTENT, objectPath=["research"], field=name, value=value)
    for _ in range(2):
        probe.change("research_add", path=CONTENT, field="research", collection="requirements")
    first, second = probe.rows("requirements")
    probe.change("research_set", path=CONTENT, objectPath=first["objectPath"], field="amount", text="999999")
    probe.change("research_move", path=CONTENT, field="research", collection="requirements", itemId=first["itemId"], beforeItemId=None)
    assert [row["itemId"] for row in probe.rows("requirements")] == [second["itemId"], first["itemId"]]
    probe.change("research_set", path=CONTENT, objectPath=first["objectPath"], field="item", value="lead")
    assert probe.document()["data"]["research"]["requirements"] == [{"item": "copper", "amount": 1}, {"item": "lead", "amount": 999999}]
    probe.change("research_remove", path=CONTENT, field="research", collection="requirements", itemId=first["itemId"])
    before = probe.state()
    failed = probe.response("research_set", path=CONTENT, objectPath=first["objectPath"], field="amount", text="5", expectedRevision=before["revision"])
    assert not failed["ok"] and probe.state() == before
    probe.change("undo")
    assert probe.rows("requirements")[1]["itemId"] == first["itemId"]
    probe.change("research_add", path=CONTENT, field="research", collection="objectives")
    objective = probe.rows("objectives")[0]
    probe.change("research_objective_type", path=CONTENT, field="research", itemId=objective["itemId"], type="OnPlanet")
    probe.change("research_set", path=CONTENT, objectPath=objective["objectPath"], field="planet", value="erekir")
    expected = {"parent": "dagger", "planet": "serpulo", "root": True, "name": "研究根", "requiresUnlock": True,
                "requirements": [{"item": "copper", "amount": 1}, {"item": "lead", "amount": 999999}],
                "objectives": [{"type": "OnPlanet", "planet": "erekir"}], "future": {"keep": True}}
    assert probe.document()["data"]["research"] == expected
    assert probe.descriptor("requirements")["rows"][0]["itemId"] == resource["itemId"]
    probe.change("resource_set", path=CONTENT, objectPath=resource["objectPath"], field="amount", text="7")
    probe.change("undo")
    assert probe.document()["data"]["requirements"][0]["amount"] == 2
    assert probe.rows("objectives")[0]["itemId"] == objective["itemId"]
    probe.change("save_opened")
    saved = probe.document()["data"]
    assert json.loads((project / CONTENT).read_text(encoding="utf-8")) == saved
    probe.change("close_documents", paths=[CONTENT], decision="discard")
    assert probe.call("read_document", path=CONTENT)["data"] == saved
    fresh = WorkspaceProbe(project)
    assert fresh.document()["data"] == saved and not fresh.document()["dirty"]


@pytest.mark.parametrize("kind,target,category,value,wrong", [
    ("Research", "content", "Blocks", "copper-wall", "beam-weapon"),
    ("Produce", "content", "Items", "lead", "beam-weapon"),
    ("SectorComplete", "preset", "SectorPresets", "groundZero", "copper"),
    ("OnSector", "preset", "SectorPresets", "groundZero", "copper"),
    ("OnPlanet", "planet", "Planets", "erekir", "copper"),
])
def test_objective_types_candidates_category_guards_and_type_undo(project, kind, target, category, value, wrong):
    (project / "content/weapons").mkdir()
    (project / "content/weapons/gun.json").write_text('{"bullet":{}}', encoding="utf-8")
    probe = WorkspaceProbe(project)
    probe.change("research_add", path=CONTENT, field="research", collection="objectives")
    row = probe.rows("objectives")[0]
    original = deepcopy(probe.document()["data"])
    probe.change("research_objective_type", path=CONTENT, field="research", itemId=row["itemId"], type=kind)
    candidates = probe.call("research_reference_candidates", path=CONTENT, objectPath=row["objectPath"], field=target, query=value)
    assert any(item["value"] == value and item["category"] == category for item in candidates["candidates"])
    assert all(item["id"] != "Weapons" for item in candidates["categories"])
    probe.change("research_set", path=CONTENT, objectPath=row["objectPath"], field=target, value=value)
    assert probe.document()["data"]["research"]["objectives"] == [{"type": kind, target: value}]
    before = probe.state()
    for candidate in (wrong, "probe-gun"):
        failed = probe.response("research_set", path=CONTENT, objectPath=row["objectPath"], field=target, value=candidate, expectedRevision=before["revision"])
        assert not failed["ok"] and probe.state() == before
    # Explicitly switching target kinds drops incompatible keys and remains undoable.
    other = "OnPlanet" if kind != "OnPlanet" else "Research"
    probe.change("research_objective_type", path=CONTENT, field="research", itemId=row["itemId"], type=other)
    assert probe.document()["data"]["research"]["objectives"] == [{"type": other}]
    probe.change("undo")
    assert probe.document()["data"]["research"]["objectives"] == [{"type": kind, target: value}]
    assert probe.rows("objectives")[0]["itemId"] == row["itemId"]
    assert original["research"]["objectives"][0]["type"] == "Research"


@pytest.mark.parametrize("payload", [{"text": "0"}, {"text": "1000000"}, {"text": "1.00000000000000001"},
    {"text": "999999.00000000000001"}, {"text": "1e-999"}, {"text": "NaN"}, {"value": True},
    {"value": None}, {"value": -1}, {"value": 1.5}])
def test_invalid_requirement_amount_keeps_state_and_disk(project, payload):
    probe = WorkspaceProbe(project)
    probe.change("research_add", path=CONTENT, field="research", collection="requirements")
    row, before, disk = probe.rows("requirements")[0], probe.state(), (project / CONTENT).read_bytes()
    failed = probe.response("research_set", path=CONTENT, objectPath=row["objectPath"], field="amount", expectedRevision=before["revision"], **payload)
    assert not failed["ok"] and failed["error"]["code"] == "INVALID_FORM_ACTION"
    assert probe.state() == before and (project / CONTENT).read_bytes() == disk


def test_planets_unknowns_candidate_reads_and_explicit_dedup_with_undo(project):
    original = {"type": "Wall", "shownPlanets": ["missing-planet", "serpulo", "serpulo"]}
    (project / CONTENT).write_text(json.dumps(original), encoding="utf-8")
    disk = (project / CONTENT).read_bytes()
    probe = WorkspaceProbe(project)
    rows, before = probe.descriptor("shownPlanets")["rows"], probe.state()
    candidates = probe.call("research_reference_candidates", path=CONTENT, objectPath=rows[0]["objectPath"], field="planet")
    assert candidates["current"] == {"value": "missing-planet", "label": "missing-planet", "known": False}
    add = probe.call("research_reference_candidates", path=CONTENT, objectPath=["shownPlanets"], field="planet", query="erekir")
    assert [item["value"] for item in add["candidates"]] == ["erekir"]
    assert probe.state() == before and (project / CONTENT).read_bytes() == disk
    probe.change("planet_set", path=CONTENT, field="shownPlanets", itemId=rows[0]["itemId"], value="erekir")
    assert probe.document()["data"]["shownPlanets"] == ["erekir", "serpulo"]
    assert [row["itemId"] for row in probe.descriptor("shownPlanets")["rows"]] == [row["itemId"] for row in rows[:2]]
    before = probe.state()
    probe.change("planet_add", path=CONTENT, field="shownPlanets", value="erekir")
    assert probe.state() == before
    probe.change("undo")
    assert probe.document()["data"] == original
    assert [row["itemId"] for row in probe.descriptor("shownPlanets")["rows"]] == [row["itemId"] for row in rows]
    probe.change("redo")
    for row in list(probe.descriptor("shownPlanets")["rows"]):
        probe.change("planet_remove", path=CONTENT, field="shownPlanets", itemId=row["itemId"])
    assert "shownPlanets" not in probe.document()["data"]
    probe.change("undo")
    assert probe.document()["data"]["shownPlanets"] == ["serpulo"]


def test_research_request_dedup_revision_conflict_and_old_session(project, tmp_path):
    probe = WorkspaceProbe(project)
    envelope = probe.envelope("research_add", path=CONTENT, field="research", collection="requirements", expectedRevision=probe.state()["revision"])
    first = probe.service.request(envelope)
    assert first["ok"] and probe.service.request(envelope) == first
    assert len(probe.rows("requirements")) == 1
    before = probe.state()
    stale = deepcopy(envelope)
    stale["requestId"] = "stale-revision"
    assert probe.service.request(stale)["error"]["code"] == "STALE_REVISION"
    conflict = deepcopy(envelope)
    conflict["payload"]["collection"] = "objectives"
    assert probe.service.request(conflict)["error"]["code"] == "REQUEST_CONFLICT"
    assert probe.state() == before
    other = tmp_path / "second"
    (other / "content/blocks").mkdir(parents=True)
    (other / "mod.json").write_text('{"name":"second"}', encoding="utf-8")
    (other / CONTENT).write_text('{"type":"Wall","research":"copper-wall"}', encoding="utf-8")
    opened = probe.change("open_project", path=str(other), discard=True)
    probe.sid = opened["sessionId"]
    probe.call("read_document", path=CONTENT)
    before = probe.state()
    assert probe.service.request(envelope)["error"]["code"] == "STALE_SESSION"
    envelope["requestId"] = "uncached-old-session"
    assert probe.service.request(envelope)["error"]["code"] == "STALE_SESSION"
    assert probe.state() == before


def test_objective_reorder_delete_and_unknown_values_restore_by_item_id(project):
    original = {"type": "Wall", "research": {"parent": "copper-wall", "objectives": [
        {"type": "Unknown", "future": 9}, {"type": "Research", "content": "dagger"}]}}
    (project / CONTENT).write_text(json.dumps(original), encoding="utf-8")
    probe = WorkspaceProbe(project)
    first, second = probe.rows("objectives")
    assert first["notice"] and not first["fields"]
    probe.change("research_move", path=CONTENT, field="research", collection="objectives", itemId=second["itemId"], beforeItemId=first["itemId"])
    probe.change("research_set", path=CONTENT, objectPath=second["objectPath"], field="content", value="lead")
    assert probe.document()["data"]["research"]["objectives"] == [{"type": "Research", "content": "lead"}, original["research"]["objectives"][0]]
    probe.change("research_remove", path=CONTENT, field="research", collection="objectives", itemId=second["itemId"])
    before = probe.state()
    failed = probe.response("research_set", path=CONTENT, objectPath=second["objectPath"], field="content", value="copper", expectedRevision=before["revision"])
    assert not failed["ok"] and probe.state() == before
    probe.change("undo")
    assert [row["itemId"] for row in probe.rows("objectives")] == [second["itemId"], first["itemId"]]
    probe.change("undo")
    probe.change("undo")
    assert probe.document()["data"] == original
    assert [row["itemId"] for row in probe.rows("objectives")] == [first["itemId"], second["itemId"]]


def test_optional_research_fields_clear_without_losing_unknown_keys(project):
    original = {"type": "Wall", "research": {"parent": "copper-wall", "planet": "serpulo", "root": True,
        "name": "研究根", "requiresUnlock": True, "future": {"keep": True}}}
    (project / CONTENT).write_text(json.dumps(original), encoding="utf-8")
    probe = WorkspaceProbe(project)
    for name, value in (("parent", ""), ("planet", None), ("root", False), ("name", "  "), ("requiresUnlock", False)):
        probe.change("research_set", path=CONTENT, objectPath=["research"], field=name, value=value)
    assert probe.document()["data"]["research"] == {"future": {"keep": True}}
    for _ in range(5):
        probe.change("undo")
    assert probe.document()["data"] == original


def test_research_inside_weapon_spawned_unit_uses_same_bridge_and_history(project):
    unit = "content/units/unit.json"
    (project / "content/units").mkdir()
    original = {"type": "mech", "weapons": [{"name": "inline", "bullet": {"spawnUnit": {
        "type": "mech", "research": "dagger", "shownPlanets": ["serpulo"]}}}]}
    (project / unit).write_text(json.dumps(original), encoding="utf-8")
    probe = WorkspaceProbe(project)
    document = probe.call("read_document", path=unit)
    weapon = fields(document["form"])["weapons"]["items"][0]
    spawn = fields(fields(weapon["form"])["bullet"]["child"])["spawnUnit"]["child"]
    research, planets = fields(spawn)["research"], fields(spawn)["shownPlanets"]
    assert research["control"] == "research" and planets["control"] == "planet_set"
    probe.change("research_set", path=unit, objectPath=research["objectPath"], field="name", text="子单位研究")
    probe.change("planet_add", path=unit, objectPath=spawn["objectPath"], field="shownPlanets", value="erekir")
    def current():
        return next(row for row in probe.state()["documents"] if row["path"] == unit)["data"]
    assert current()["weapons"][0]["bullet"]["spawnUnit"]["research"] == {"parent": "dagger", "name": "子单位研究"}
    assert current()["weapons"][0]["bullet"]["spawnUnit"]["shownPlanets"] == ["serpulo", "erekir"]
    probe.change("undo")
    probe.change("undo")
    assert current() == original
