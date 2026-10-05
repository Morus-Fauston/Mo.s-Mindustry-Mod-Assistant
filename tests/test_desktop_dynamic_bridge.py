"""Real Workspace/PNG contracts, not frontend frame scheduling or native visual proof."""

import base64
from io import BytesIO
from itertools import count
import json

from PIL import Image
import pytest

from app.desktop.workspace import WorkspaceService
from app.desktop.preview import PreviewService


UNIT = "content/units/unit.json"


class DynamicBridge:
    def __init__(self, root):
        self.root = root
        self.workspace = WorkspaceService("metadata")
        self.ids, self.sid = count(), None
        self.sid = self.call("open_project", path=str(root))["sessionId"]

    def envelope(self, action, **payload):
        return {"protocolVersion": 1, "requestId": f"dynamic-{next(self.ids)}",
                "sessionId": self.sid, "action": action, "payload": payload}

    def response(self, action, **payload):
        return self.workspace.request(self.envelope(action, **payload))

    def call(self, action, **payload):
        response = self.response(action, **payload)
        assert response["ok"], response
        return response["data"]

    def state(self):
        return self.call("editing_state")

    def scene(self, path=UNIT):
        return self.call("preview_scene", path=path)

    def disk(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}


@pytest.fixture
def bridge(tmp_path):
    probes = []

    def create(data, *, content=None, sprites=None):
        root = tmp_path / f"dynamic-{len(probes)}"
        root.mkdir()
        (root / "mod.json").write_text('{"name":"dynamic"}', encoding="utf-8")
        for relative, value in {UNIT: data, **(content or {})}.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding="utf-8")
        for relative, spec in {"sprites/units/unit.png": (32, 32), **(sprites or {})}.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(spec, bytes):
                path.write_bytes(spec)
            elif spec is not None:
                Image.new("RGBA", spec, (60, 130, 210, 170)).save(path)
        probe = DynamicBridge(root)
        probes.append(probe)
        return probe

    yield create
    for probe in probes:
        probe.call("close_window", decision="discard", expectedRevision=probe.state()["revision"])


def test_reference_coordinates_mirror_and_node_identity_are_readonly_across_real_bridge(bridge):
    data = {"type": "mech", "health": 137, "engineSize": 2, "engineOffset": 3,
            "weapons": [{"name": "dynamic-gun", "mirror": True}]}
    probe = bridge(data, content={"content/weapons/gun.json": {"x": -3, "y": 2, "recoil": 99,
        "bullet": {"type": "BasicBulletType", "damage": 8}}}, sprites={"sprites/weapons/gun.png": (8, 12)})
    probe.call("read_document", path=UNIT)
    # Verify read-only behavior even with a real unsaved command/history present.
    probe.call("set_field", path=UNIT, field="health", text="155", expectedRevision=probe.state()["revision"])
    before, disk = probe.state(), probe.disk()
    envelope = probe.envelope("preview_scene", path=UNIT)
    response = probe.workspace.request(envelope)
    assert response["ok"], response
    scene = response["data"]
    dynamic = scene["dynamic"]
    form = before["documents"][0]["form"]
    weapons = next(field for group in form["groups"] for field in group["fields"] if field["name"] == "weapons")
    node_id = f"weapon:{weapons['items'][0]['itemId']}"
    assert dynamic["weapons"] == [{"nodeId": node_id, "layerKeys": ["__weapon_0__"],
        "recoilDistance": 1, "recoilPower": 1.8, "flashCenter": {"x": 4, "y": 8}}]
    drawings = [layer for layer in scene["layers"] if layer["nodeId"] == node_id]
    assert [(layer["x"], layer["y"], layer["flipX"]) for layer in drawings] == [(0, 2, False), (24, 2, True)]
    assert len(dynamic["weapons"]) == 1  # Flash stays at the original mount, with no mirrored extra flash.
    assert dynamic["engine"] == {"nodeId": "engine", "outerIndex": 0, "innerIndex": 1, "size": 2}
    assert [(circle["cx"], circle["cy"], circle["radius"]) for circle in scene["circles"]] == [(16, 28, 8), (16, 26, 4)]
    assert (scene["sessionId"], scene["path"], scene["revision"]) == (probe.sid, UNIT, before["revision"])
    assert probe.workspace.request(envelope) == response
    assert probe.workspace.request_result(envelope["requestId"]) == {"state": "unknown"}
    for layer in scene["layers"]:
        assert probe.call("preview_resource", resourceId=layer["resourceId"])["sessionId"] == probe.sid
    assert str(probe.root) not in json.dumps(dynamic, allow_nan=False)
    assert probe.state() == before and probe.disk() == disk
    assert before["documents"][0]["dirty"] and before["history"]["canUndo"]


def test_tank_frame_and_heat_endpoints_decode_real_pixels_and_refresh_with_stable_ids(bridge):
    probe = bridge({"type": "tank", "treadFrames": 4}, sprites={
        "sprites/units/unit-treads.png": (32, 32),
        "sprites/units/unit-treads0-0.png": (12, 8),
        "sprites/units/unit-treads0-2.png": b"corrupt PNG",
        "sprites/units/unit-treads0-3.png": (14, 10),
        "sprites/units/unit-treads1-0.png": (99, 99),
        "sprites/units/unit-heat.png": (8, 12),
    })
    probe.call("read_document", path=UNIT)
    before, disk = probe.state(), probe.disk()
    scene = probe.scene()
    dynamic = scene["dynamic"]
    assert dynamic["supported"] and dynamic["notices"]
    assert dynamic["treads"]["nodeId"] == "sprite:-treads"
    assert dynamic["treads"]["layerKey"] == "-treads"
    frames = dynamic["treads"]["frames"]
    assert [(frame["width"], frame["height"]) for frame in frames] == [(12, 8), (14, 10)]
    heat = dynamic["heat"]
    assert (heat["x"], heat["y"], heat["z"], heat["width"], heat["height"]) == (12, 10, 12, 8, 12)
    assert (heat["nodeId"], heat["key"], heat["color"]) == ("sprite:-heat", "__heat__", "#ff795e")
    for descriptor in [*scene["layers"], *frames, heat]:
        response = probe.response("preview_resource", resourceId=descriptor["resourceId"])
        assert response["ok"], response
        resource = response["data"]
        assert resource["sessionId"] == probe.sid and resource["mime"] == "image/png"
        with Image.open(BytesIO(base64.b64decode(resource["dataUrl"].split(",", 1)[1]))) as image:
            assert image.size == (descriptor["width"], descriptor["height"])
            assert image.convert("RGBA").getpixel((0, 0)) == (60, 130, 210, 170)
        assert probe.workspace.request_result(response["requestId"]) == {"state": "unknown"}
    assert probe.scene() == scene
    assert probe.state() == before and probe.disk() == disk
    json.dumps(scene, allow_nan=False)


def test_dynamic_resources_expire_on_other_content_and_cannot_cross_project_sessions(bridge):
    other = "content/units/other.json"
    probe = bridge({"type": "tank", "treadFrames": 1}, content={other: {"type": "mech"}}, sprites={
        "sprites/units/unit-treads.png": (32, 32), "sprites/units/unit-treads0-0.png": (6, 4),
        "sprites/units/unit-heat.png": (8, 12), "sprites/units/other.png": (20, 10),
    })
    for path in (UNIT, other):
        probe.call("read_document", path=path)
    before, disk = probe.state(), probe.disk()
    initial = probe.scene()
    heat_id = initial["dynamic"]["heat"]["resourceId"]
    frame_id = initial["dynamic"]["treads"]["frames"][0]["resourceId"]
    resource_envelope = probe.envelope("preview_resource", resourceId=heat_id)
    assert probe.workspace.request(resource_envelope)["ok"]
    assert probe.scene(other)["dynamic"]["heat"] is None
    for resource_id in (heat_id, frame_id):
        rejected = probe.response("preview_resource", resourceId=resource_id)
        assert not rejected["ok"] and rejected["error"]["code"] == "PREVIEW_RESOURCE_UNAVAILABLE"
    assert probe.workspace.request(resource_envelope)["error"]["code"] == "PREVIEW_RESOURCE_UNAVAILABLE"
    restored = probe.scene()
    assert restored["dynamic"]["heat"]["resourceId"] == heat_id
    assert restored["dynamic"]["treads"]["frames"][0]["resourceId"] == frame_id
    assert probe.state() == before and probe.disk() == disk
    old_scene_envelope = probe.envelope("preview_scene", path=UNIT)
    old_sid = probe.sid
    probe.sid = probe.call("open_project", path=str(probe.root))["sessionId"]
    assert probe.sid != old_sid
    for envelope in (old_scene_envelope, resource_envelope):
        assert probe.workspace.request(envelope)["error"]["code"] == "STALE_SESSION"
    assert probe.response("preview_resource", resourceId=heat_id)["error"]["code"] == "PREVIEW_RESOURCE_UNAVAILABLE"
    probe.call("read_document", path=UNIT)
    new_before = probe.state()
    new_scene = probe.scene()
    assert new_scene["dynamic"]["heat"]["resourceId"] != heat_id
    assert new_scene["dynamic"]["treads"]["frames"][0]["resourceId"] != frame_id
    assert probe.state() == new_before and probe.disk() == disk


@pytest.mark.parametrize("body", [None, b"broken body"])
def test_missing_or_corrupt_body_does_not_scan_extra_dynamic_resources(bridge, body):
    probe = bridge({"type": "tank", "treadFrames": 2}, sprites={
        "sprites/units/unit.png": body, "sprites/units/unit-treads.png": (32, 32),
        "sprites/units/unit-treads0-0.png": b"broken frame", "sprites/units/unit-heat.png": b"broken heat",
    })
    probe.call("read_document", path=UNIT)
    before, disk = probe.state(), probe.disk()
    scene = probe.scene()
    dynamic = scene["dynamic"]
    assert scene["status"] == "missing" and not scene["layers"]
    assert not dynamic["supported"] and dynamic["treads"] is None and dynamic["heat"] is None
    assert dynamic["notices"] == []  # Extra corrupt files were not scanned after the body failed.
    assert probe.state() == before and probe.disk() == disk


def test_unusable_frames_and_heat_leave_static_scene_readable_and_recover_without_commands(bridge):
    probe = bridge({"type": "tank", "treadFrames": 3}, sprites={
        "sprites/units/unit-treads.png": (32, 32),
        "sprites/units/unit-treads0-0.png": b"broken frame", "sprites/units/unit-heat.png": b"broken heat",
    })
    probe.call("read_document", path=UNIT)
    before, disk = probe.state(), probe.disk()
    scene = probe.scene()
    assert scene["dynamic"]["supported"]
    assert scene["dynamic"]["treads"] is None and scene["dynamic"]["heat"] is None
    assert len(scene["dynamic"]["notices"]) == 2
    assert [layer["key"] for layer in scene["layers"]] == ["", "-treads"]
    for layer in scene["layers"]:
        assert probe.call("preview_resource", resourceId=layer["resourceId"])["width"] == 32
    assert probe.state() == before and probe.disk() == disk
    # Simulate a separately repaired external PNG, then measure reads against that new disk baseline.
    Image.new("RGBA", (5, 7), (20, 40, 60, 255)).save(probe.root / "sprites/units/unit-treads0-0.png")
    Image.new("RGBA", (3, 5), (20, 40, 60, 255)).save(probe.root / "sprites/units/unit-heat.png")
    repaired_disk = probe.disk()
    recovered = probe.scene()["dynamic"]
    assert recovered["notices"] == []
    assert recovered["treads"]["frames"][0]["width"] == 5 and recovered["heat"]["width"] == 3
    assert probe.state() == before and probe.disk() == repaired_disk


@pytest.mark.parametrize("limit,value", [("MAX_RESOURCES", 2), ("MAX_SCENE_PIXELS", 2048)])
def test_dynamic_registration_shares_static_resource_budgets_through_workspace(bridge, monkeypatch, limit, value):
    monkeypatch.setattr(PreviewService, limit, value)
    probe = bridge({"type": "tank", "treadFrames": 1}, sprites={
        "sprites/units/unit-treads.png": (32, 32), "sprites/units/unit-treads0-0.png": (4, 4),
        "sprites/units/unit-heat.png": (4, 4),
    })
    probe.call("read_document", path=UNIT)
    before, disk = probe.state(), probe.disk()
    scene = probe.scene()
    assert len(scene["layers"]) == 2 and scene["dynamic"]["supported"]
    assert scene["dynamic"]["treads"] is None and scene["dynamic"]["heat"] is None
    assert len(scene["dynamic"]["notices"]) == 2
    for layer in scene["layers"]:
        assert probe.call("preview_resource", resourceId=layer["resourceId"])["width"] == 32
    assert probe.state() == before and probe.disk() == disk


def test_finite_fallback_and_tread_candidate_limit_cross_bridge_without_normalizing_content(bridge):
    data = {"type": "tank", "treadFrames": 1000000, "recoilTime": "nan", "cooldownTime": "inf",
            "weapons": [{"name": "gun", "x": 2, "y": 1, "recoil": 1000001, "recoilPow": -2},
                        {"name": "gun", "x": "nan"}]}
    probe = bridge(data, sprites={"sprites/weapons/gun.png": (8, 12), "sprites/units/unit-treads.png": (32, 32),
        "sprites/units/unit-treads0-63.png": (2, 3), "sprites/units/unit-treads0-64.png": (7, 8)})
    probe.call("read_document", path=UNIT)
    before, disk = probe.state(), probe.disk()
    dynamic = probe.scene()["dynamic"]
    assert (dynamic["recoilTime"], dynamic["cooldownTime"]) == (10, 20)
    assert len(dynamic["weapons"]) == 1
    assert (dynamic["weapons"][0]["recoilDistance"], dynamic["weapons"][0]["recoilPower"]) == (1, 0)
    assert dynamic["weapons"][0]["flashCenter"] == {"x": 24, "y": 12}
    assert [(frame["width"], frame["height"]) for frame in dynamic["treads"]["frames"]] == [(2, 3)]
    assert any("64" in notice for notice in dynamic["notices"])
    assert any("安装坐标" in notice for notice in dynamic["notices"])
    json.dumps(dynamic, allow_nan=False)
    assert probe.state() == before and probe.disk() == disk
    assert before["documents"][0]["data"] == data


def test_standalone_weapon_static_and_dynamic_heat_share_real_resource_without_deduping_layers(bridge):
    path = "content/weapons/gun.json"
    probe = bridge({"type": "mech"}, content={path: {"type": "Weapon"}}, sprites={
        "sprites/weapons/gun.png": (20, 10), "sprites/weapons/gun-heat.png": (4, 6),
    })
    probe.call("read_document", path=path)
    before, disk = probe.state(), probe.disk()
    scene = probe.scene(path)
    static = next(layer for layer in scene["layers"] if layer["key"] == "-heat")
    dynamic = scene["dynamic"]["heat"]
    assert scene["dynamic"]["supported"] and scene["path"] == path
    assert static["resourceId"] == dynamic["resourceId"]
    assert static["key"] == "-heat" and dynamic["key"] == "__heat__"
    assert (dynamic["x"], dynamic["y"], dynamic["z"]) == (8, 2, 12)
    assert probe.call("preview_resource", resourceId=dynamic["resourceId"])["width"] == 4
    assert probe.scene(path) == scene
    assert probe.state() == before and probe.disk() == disk
