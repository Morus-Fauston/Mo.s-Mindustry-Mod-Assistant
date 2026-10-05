"""Layer identities and coordinates come from real workspace form snapshots."""

from copy import deepcopy
from itertools import count

from PIL import Image
import pytest

from app.core.content_store import ContentData
from app.core.project import Project
from app.desktop.preview import PreviewService
from app.desktop.preview_layers import PreviewLayerService
from app.desktop.workspace import WorkspaceService


class LayerProbe:
    def __init__(self, tmp_path, data):
        self.project = Project.create(tmp_path, "test", "测试")
        self.project.contents.save("unit", data, "units")
        self.path = "content/units/unit.json"
        self.workspace = WorkspaceService("metadata")
        self.ids, self.session = count(), None
        self.session = self.call("open_project", path=str(self.project.root))["sessionId"]
        self.call("read_document", path=self.path)
        self.preview = PreviewService(self.project, self.session)
        self.layers = PreviewLayerService(self.project)

    def call(self, action, **payload):
        response = self.workspace.request({"protocolVersion": 1, "requestId": str(next(self.ids)),
            "sessionId": self.session, "action": action, "payload": payload})
        assert response["ok"], response
        return response["data"]

    def document(self):
        return self.call("editing_state")["documents"][0]

    def change(self, action, **payload):
        return self.call(action, path=self.path, expectedRevision=self.document()["revision"], **payload)

    def sprite(self, name, category="units", size=(32, 32)):
        path = self.project.sprite_path(category, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", size, (255, 0, 0, 255)).save(path)

    def decorate(self):
        document = self.document()
        content = ContentData("unit", "units", document["data"], self.project.root / self.path)
        scene = self.preview.scene(content)
        return self.layers.decorate(scene, content, document["form"], self.path, document["revision"])


def fields(plan):
    return {field["name"]: field for group in plan["groups"] for field in group["fields"]}


def weapons(scene):
    return next(node for node in scene["tree"] if node["kind"] == "weapon-group")["children"]


def test_real_scene_and_form_share_stable_weapon_identity_without_mutation(tmp_path):
    probe = LayerProbe(tmp_path, {"type": "mech", "engineSize": 1, "weapons": [
        {"name": "gun", "x": -3, "y": 2, "mirror": True, "bullet": {}},
        {"name": "gun", "x": 5, "y": -2, "bullet": {}},
    ]})
    probe.sprite("unit")
    probe.sprite("gun", "weapons", (8, 12))
    document = probe.document()
    content = ContentData("unit", "units", document["data"], probe.project.root / probe.path)
    scene = probe.preview.scene(content)
    before = deepcopy((scene, content.data, document["form"]))
    result = probe.layers.decorate(scene, content, document["form"], probe.path, document["revision"])
    assert (scene, content.data, document["form"]) == before
    assert result["path"] == probe.path and result["revision"] == document["revision"]
    items = fields(document["form"])["weapons"]["items"]
    assert [node["id"] for node in weapons(result)] == [f'weapon:{item["itemId"]}' for item in items]
    assert [node["weapon"]["objectPath"] for node in weapons(result)] == [item["objectPath"] for item in items]
    draw = [layer for layer in result["layers"] if layer["key"].startswith("__weapon_")]
    assert [layer["nodeId"] for layer in draw] == [weapons(result)[0]["id"], weapons(result)[0]["id"], weapons(result)[1]["id"]]
    assert [(layer["x"], layer["y"], layer["flipX"]) for layer in draw[:2]] == [(0, 2, False), (24, 2, True)]
    assert {circle["nodeId"] for circle in result["circles"]} == {"engine"}
    assert result["layers"][0]["nodeId"] == "sprite:"
    assert all(node["kind"] != "content" for node in result["tree"])
    assert weapons(result)[0]["weapon"]["coordinates"]["x"]["displayValue"] == -3


def test_missing_body_keeps_configured_tree_and_editable_weapon_coordinates(tmp_path):
    probe = LayerProbe(tmp_path, {"type": "tank", "engineSize": 2,
        "weapons": [{"name": "missing", "x": 3, "y": -2, "bullet": {}}]})
    probe.sprite("unit-treads")
    before = probe.document()
    scene = probe.decorate()
    nodes = {node["id"]: node for node in scene["tree"]}
    assert scene["status"] == "missing" and not scene["layers"]
    assert nodes["sprite:"]["status"] == "missing"
    assert nodes["sprite:-treads"]["status"] == "ready"
    assert nodes["sprite:-cell"]["status"] == "optional"
    assert "sprite:-leg" not in nodes
    assert nodes["engine"]["kind"] == "engine"
    assert weapons(scene)[0]["status"] == "missing"
    assert weapons(scene)[0]["weapon"]["coordinates"]["y"]["displayValue"] == -2
    assert probe.document() == before


def test_reference_coordinate_fallback_is_read_only_until_authoritative_plan_allows_editing(tmp_path):
    probe = LayerProbe(tmp_path, {"type": "mech", "weapons": [{"name": "test-gun"}]})
    probe.project.contents.save("gun", {"x": -3, "y": 2}, "weapons")
    before = probe.document()
    scene = probe.decorate()
    row = weapons(scene)[0]
    coordinates = row["weapon"]["coordinates"]
    assert coordinates["x"]["displayValue"] == -3 and coordinates["y"]["displayValue"] == 2
    actual = fields(fields(before["form"])["weapons"]["items"][0]["form"])
    for name in ("x", "y"):
        assert coordinates[name]["present"] is False
        assert coordinates[name]["readOnly"] == actual.get(name, {"readOnly": True})["readOnly"]
        assert coordinates[name]["label"] == before["fieldNames"][name]
        assert coordinates[name]["help"] == before["fieldDocs"][name]
    assert probe.document() == before
    assert probe.project.contents.get_by_path("units/unit.json").data == {"type": "mech", "weapons": [{"name": "test-gun"}]}


@pytest.mark.parametrize('value', [{'legacy': 'preserved'}, [7, {'type': 'UnknownWeapon', 'name': 'gun'}],
                                  [{'name': 'gun'}] * 513])
def test_uneditable_weapon_data_stays_visible_without_fabricated_write_routes(tmp_path, value):
    probe = LayerProbe(tmp_path, {'type': 'mech', 'weapons': value})
    before = probe.document()
    scene = probe.decorate()
    group = next(node for node in scene['tree'] if node['kind'] == 'weapon-group')
    assert group.get('notice') or all(node.get('notice') for node in group['children'])
    assert all('weapon' not in node for node in group['children'])
    assert len(group['children']) <= 128
    assert probe.document() == before


def test_unknown_root_can_show_existing_weapon_pixels_without_forging_item_identity(tmp_path):
    probe = LayerProbe(tmp_path, {'type': 'UnknownUnitType', 'weapons': [{'name': 'gun', 'x': 1, 'y': 2}]})
    probe.sprite('unit')
    probe.sprite('gun', 'weapons')
    scene = probe.decorate()
    group = next(node for node in scene['tree'] if node['kind'] == 'weapon-group')
    assert group['status'] == 'invalid' and group['children'] == []
    assert scene['layers'][1]['nodeId'] == group['id']
    assert group['drawableKeys'] == ['__weapon_0__']


def test_coordinates_reorder_delete_undo_and_save_use_same_real_workspace_item(tmp_path):
    probe = LayerProbe(tmp_path, {'type': 'mech', 'weapons': [
        {'name': 'gun', 'x': -3, 'y': 2, 'mirror': True, 'bullet': {}},
        {'name': 'gun', 'x': 5, 'y': -2, 'bullet': {}},
    ]})
    probe.sprite('unit')
    probe.sprite('gun', 'weapons', (8, 12))
    first, second = weapons(probe.decorate())
    address = first['weapon']['objectPath']
    probe.change('weapon_move', field='weapons', itemId=first['weapon']['itemId'], beforeItemId=None)
    assert [row['id'] for row in weapons(probe.decorate())] == [second['id'], first['id']]
    probe.change('set_field', objectPath=address, field='x', text='-4.25')
    scene = probe.decorate()
    assert weapons(scene)[1]['weapon']['coordinates']['x']['displayValue'] == -4.25
    drawn = [layer for layer in scene['layers'] if layer['nodeId'] == first['id']]
    assert [(layer['x'], layer['y']) for layer in drawn] == [(-5, 2), (29, 2)]
    probe.change('undo')
    assert weapons(probe.decorate())[1]['weapon']['coordinates']['x']['displayValue'] == -3
    probe.change('redo')
    probe.change('weapon_remove', field='weapons', itemId=first['weapon']['itemId'])
    assert [row['id'] for row in weapons(probe.decorate())] == [second['id']]
    probe.change('undo')
    assert weapons(probe.decorate())[1]['id'] == first['id']
    probe.change('save_opened')
    saved = probe.project.contents.get_by_path('units/unit.json').data
    assert saved['weapons'][1]['x'] == -4.25 and saved['weapons'][0]['x'] == 5
    probe.change('close_documents', paths=[probe.path], decision='discard')
    reopened = probe.call('read_document', path=probe.path)
    assert reopened['data'] == saved
    assert weapons(probe.decorate())[1]['weapon']['coordinates']['x']['displayValue'] == -4.25


@pytest.mark.parametrize('source', ['{ broken', '[]', '{"x": Infinity, "y": 2}'])
def test_invalid_reference_source_has_visible_failure_without_fallback_write(tmp_path, source):
    probe = LayerProbe(tmp_path, {'type': 'mech', 'weapons': [{'name': 'test-gun'}]})
    target = probe.project.root / 'content/weapons/gun.json'
    target.write_text(source, encoding='utf-8')
    before = probe.document()
    row = weapons(probe.decorate())[0]
    assert row['status'] == 'invalid' and row['notice']
    assert row['weapon']['coordinates']['x']['displayValue'] is None
    assert probe.document() == before and target.read_text(encoding='utf-8') == source


def test_out_of_range_engine_value_does_not_break_layer_tree(tmp_path):
    probe = LayerProbe(tmp_path, {'type': 'mech', 'engineSize': 10 ** 400})
    probe.sprite('unit')
    scene = probe.decorate()
    assert scene['layers'][0]['nodeId'] == 'sprite:'
    assert scene['warnings'] and not scene['circles']
