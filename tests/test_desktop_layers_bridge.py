"""Layer trees are exercised only through the real serialized Workspace API."""

from copy import deepcopy
from itertools import count
import json

from PIL import Image
import pytest

from app.desktop.workspace import WorkspaceService


DOCUMENT = 'content/units/unit.json'


def fields(plan):
    return {field['name']: field for group in plan['groups'] for field in group['fields']}


def weapons(scene):
    return next(node for node in scene['tree'] if node['kind'] == 'weapon-group')['children']


class LayersBridge:
    def __init__(self, root):
        self.root, self.workspace = root, WorkspaceService('metadata')
        self.ids, self.sid = count(), None
        self.sid = self.call('open_project', path=str(root))['sessionId']

    def envelope(self, action, **payload):
        return {'protocolVersion': 1, 'requestId': f'layers-{next(self.ids)}',
                'sessionId': self.sid, 'action': action, 'payload': payload}

    def response(self, action, **payload):
        return self.workspace.request(self.envelope(action, **payload))

    def call(self, action, **payload):
        response = self.response(action, **payload)
        assert response['ok'], response
        return response['data']

    def state(self):
        return self.call('editing_state')

    def document(self):
        return next(document for document in self.state()['documents'] if document['path'] == DOCUMENT)

    def change(self, action, **payload):
        return self.call(action, expectedRevision=self.state()['revision'], **payload)

    def scene(self):
        return self.call('preview_scene', path=DOCUMENT)


@pytest.fixture
def bridge(tmp_path):
    active, identifiers = [], count()
    def create(data, *, body=True, gun=True, source=None):
        root = tmp_path / f'project-{next(identifiers)}'
        for directory in ('content/units', 'content/weapons', 'sprites/units', 'sprites/weapons'):
            (root / directory).mkdir(parents=True)
        (root / 'mod.json').write_text('{"name":"probe"}', encoding='utf-8')
        (root / DOCUMENT).write_text(data if isinstance(data, str) else json.dumps(data), encoding='utf-8')
        if source is not None:
            (root / 'content/weapons/gun.json').write_text(source if isinstance(source, str) else json.dumps(source), encoding='utf-8')
        if body:
            Image.new('RGBA', (32, 32), (150, 160, 170, 255)).save(root / 'sprites/units/unit.png')
        if gun:
            Image.new('RGBA', (8, 12), (180, 80, 90, 255)).save(root / 'sprites/weapons/gun.png')
        probe = LayersBridge(root)
        active.append(probe)
        return probe
    yield create
    for probe in active:
        probe.change('close_window', decision='discard')


def test_bridge_scene_uses_authoritative_path_revision_ids_and_mirror_world_coordinates(bridge):
    probe = bridge({'type': 'mech', 'engineSize': 1, 'weapons': [
        {'name': 'gun', 'x': -3, 'y': 2, 'mirror': True, 'bullet': {}},
        {'name': 'gun', 'x': 5, 'y': -2, 'bullet': {}},
    ]})
    probe.call('read_document', path=DOCUMENT)
    before, disk = probe.state(), (probe.root / DOCUMENT).read_bytes()
    response = probe.response('preview_scene', path=DOCUMENT)
    assert response['ok'], response
    scene = response['data']
    assert (scene['sessionId'], scene['path'], scene['revision']) == (probe.sid, DOCUMENT, before['revision'])
    items = fields(before['documents'][0]['form'])['weapons']['items']
    rows = weapons(scene)
    assert [row['id'] for row in rows] == [f"weapon:{item['itemId']}" for item in items]
    assert [row['weapon']['objectPath'] for row in rows] == [item['objectPath'] for item in items]
    assert rows[0]['id'] != rows[1]['id'] and rows[0]['label'] == rows[1]['label'] == 'gun'
    drawings = [layer for layer in scene['layers'] if layer['nodeId'] == rows[0]['id']]
    assert [(layer['x'], layer['y'], layer['flipX']) for layer in drawings] == [(0, 2, False), (24, 2, True)]
    assert (drawings[0]['width'], drawings[0]['height']) == (8, 12)
    assert {circle['nodeId'] for circle in scene['circles']} == {'engine'}
    assert scene['layers'][0]['nodeId'] == 'sprite:'
    assert all(node['kind'] != 'content' for node in scene['tree'])
    assert probe.workspace.request_result(response['requestId']) == {'state': 'unknown'}
    resource = probe.call('preview_resource', resourceId=drawings[0]['resourceId'])
    assert (resource['width'], resource['height']) == (8, 12)
    assert probe.state() == before and (probe.root / DOCUMENT).read_bytes() == disk


def test_same_name_reorder_edit_undo_redo_delete_restore_and_save_stay_on_one_item(bridge):
    probe = bridge({'type': 'mech', 'weapons': [
        {'name': 'gun', 'x': -3, 'y': 2, 'mirror': True, 'bullet': {}},
        {'name': 'gun', 'x': 5, 'y': -2, 'bullet': {}},
    ]})
    probe.call('read_document', path=DOCUMENT)
    first, second = weapons(probe.scene())
    anchor = first['weapon']['objectPath']
    probe.change('weapon_move', path=DOCUMENT, field='weapons', itemId=first['weapon']['itemId'], beforeItemId=None)
    assert [row['id'] for row in weapons(probe.scene())] == [second['id'], first['id']]
    payload = {'path': DOCUMENT, 'objectPath': anchor, 'field': 'x', 'text': '-4.25', 'expectedRevision': probe.state()['revision']}
    envelope = probe.envelope('set_field', **payload)
    result = probe.workspace.request(envelope)
    assert result['ok'] and probe.workspace.request(envelope) == result
    scene = probe.scene()
    assert scene['revision'] == probe.document()['revision']
    assert [row['weapon']['coordinates']['x']['displayValue'] for row in weapons(scene)] == [5, -4.25]
    assert [(layer['x'], layer['y']) for layer in scene['layers'] if layer['nodeId'] == first['id']] == [(-5, 2), (29, 2)]
    before = probe.state()
    stale = probe.response('set_field', **payload)
    assert stale['error']['code'] == 'STALE_REVISION' and probe.state() == before
    probe.change('undo')
    assert weapons(probe.scene())[1]['weapon']['coordinates']['x']['displayValue'] == -3
    probe.change('redo')
    probe.change('weapon_remove', path=DOCUMENT, field='weapons', itemId=first['weapon']['itemId'])
    assert [row['id'] for row in weapons(probe.scene())] == [second['id']]
    before = probe.state()
    invalid = probe.response('set_field', path=DOCUMENT, objectPath=anchor, field='y', value=8, expectedRevision=before['revision'])
    assert not invalid['ok'] and probe.state() == before
    probe.change('undo')
    assert weapons(probe.scene())[1]['id'] == first['id']
    probe.change('save_opened')
    saved = deepcopy(probe.document()['data'])
    assert json.loads((probe.root / DOCUMENT).read_text('utf-8')) == saved
    probe.change('close_documents', paths=[DOCUMENT], decision='discard')
    reopened = probe.call('read_document', path=DOCUMENT)
    assert reopened['data'] == saved and not reopened['dirty']
    assert weapons(probe.scene())[1]['weapon']['coordinates']['x']['displayValue'] == -4.25


def test_reference_virtual_coordinates_cross_bridge_without_read_materialization(bridge):
    source = {'x': -3, 'y': 2, 'bullet': {'damage': 8}}
    original = {'type': 'mech', 'weapons': [{'name': 'probe-gun', 'mirror': True}]}
    probe = bridge(original, source=source)
    probe.call('read_document', path=DOCUMENT)
    before = probe.state()
    row = weapons(probe.scene())[0]
    x = row['weapon']['coordinates']['x']
    assert x['displayValue'] == -3 and not x['present'] and not x['readOnly']
    assert probe.state() == before and probe.document()['data'] == original
    probe.change('set_field', path=DOCUMENT, objectPath=row['weapon']['objectPath'], field='x', text='-6')
    assert probe.document()['data']['weapons'][0] == {'name': 'probe-gun', 'mirror': True, 'x': -6}
    assert weapons(probe.scene())[0]['id'] == row['id']
    assert weapons(probe.scene())[0]['weapon']['coordinates']['y']['displayValue'] == 2
    probe.change('undo')
    assert probe.document()['data'] == original
    assert not weapons(probe.scene())[0]['weapon']['coordinates']['x']['present']
    assert json.loads((probe.root / 'content/weapons/gun.json').read_text('utf-8')) == source


@pytest.mark.parametrize('body,gun', [(False, False), (True, False)])
def test_missing_images_keep_real_tree_and_writable_coordinates(bridge, body, gun):
    probe = bridge({'type': 'mech', 'weapons': [{'name': 'absent'}]}, body=body, gun=gun)
    probe.call('read_document', path=DOCUMENT)
    before = probe.state()
    scene = probe.scene()
    assert scene['status'] == 'missing'
    row = weapons(scene)[0]
    assert row['status'] == 'missing'
    assert row['weapon']['coordinates']['x']['displayValue'] == 0
    assert not row['weapon']['coordinates']['x']['readOnly']
    if not body:
        assert not scene['layers'] and scene['tree'][0]['id'] == 'sprite:'
    assert probe.state() == before
    probe.change('set_field', path=DOCUMENT, objectPath=row['weapon']['objectPath'], field='y', text='-2')
    assert weapons(probe.scene())[0]['weapon']['coordinates']['y']['displayValue'] == -2


@pytest.mark.parametrize('source', ['{broken', '[]', '{"x":Infinity,"y":2}'])
def test_invalid_reference_reports_failure_without_forging_writable_fallback(bridge, source):
    probe = bridge({'type': 'mech', 'weapons': [{'name': 'probe-gun'}]}, source=source)
    probe.call('read_document', path=DOCUMENT)
    before = probe.state()
    row = weapons(probe.scene())[0]
    assert row['status'] == 'invalid' and row['notice']
    assert row['weapon']['coordinates']['x']['displayValue'] is None
    assert row['weapon']['coordinates']['x']['readOnly']
    assert probe.state() == before
    assert (probe.root / 'content/weapons/gun.json').read_text('utf-8') == source


def test_raw_source_gate_then_repair_and_undo_never_invents_a_valid_scene(bridge):
    probe = bridge('{broken')
    opened = probe.call('read_document', path=DOCUMENT)
    assert not opened['validData']
    before = probe.state()
    failed = probe.response('preview_scene', path=DOCUMENT)
    assert failed['error']['code'] == 'SOURCE_INVALID'
    assert probe.state() == before
    probe.change('set_source', path=DOCUMENT, text='{"type":"mech","weapons":[{"name":"gun","x":-3,"y":2}]}')
    assert weapons(probe.scene())[0]['weapon']['coordinates']['x']['displayValue'] == -3
    probe.change('undo')
    assert not probe.document()['validData']
    assert probe.response('preview_scene', path=DOCUMENT)['error']['code'] == 'SOURCE_INVALID'


def test_scene_from_closed_session_and_its_resources_are_rejected_after_switch(bridge):
    probe = bridge({'type': 'mech', 'weapons': [{'name': 'gun', 'x': 1, 'y': 2}]})
    probe.call('read_document', path=DOCUMENT)
    scene = probe.scene()
    old_envelope = probe.envelope('preview_scene', path=DOCUMENT)
    resource_id = scene['layers'][0]['resourceId']
    probe.sid = probe.call('open_project', path=str(probe.root))['sessionId']
    rejected = probe.workspace.request(old_envelope)
    assert rejected['error']['code'] == 'STALE_SESSION'
    assert probe.response('preview_resource', resourceId=resource_id)['error']['code'] == 'PREVIEW_RESOURCE_UNAVAILABLE'
    probe.call('read_document', path=DOCUMENT)
    assert probe.scene()['sessionId'] == probe.sid != scene['sessionId']


@pytest.mark.parametrize('suffix', ['', '-cell'])
def test_corrupt_existing_sprite_cannot_be_reported_as_ready_layer(bridge, suffix):
    probe = bridge({'type': 'mech'})
    (probe.root / f'sprites/units/unit{suffix}.png').write_bytes(b'not a PNG')
    probe.call('read_document', path=DOCUMENT)
    before = probe.state()
    scene = probe.scene()
    assert scene['status'] == 'missing' and scene['warnings']
    row = next(node for node in scene['tree'] if node['id'] == f'sprite:{suffix}')
    assert row['status'] in ('missing', 'invalid'), row
    assert not any(layer['nodeId'] == row['id'] for layer in scene['layers'])
    assert probe.state() == before
