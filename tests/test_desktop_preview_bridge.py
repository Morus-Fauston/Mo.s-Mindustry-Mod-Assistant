"""Preview actions use the same serialized session and cannot leak old resources."""

import json
from itertools import count

from PIL import Image

from app.desktop.workspace import WorkspaceService


def test_scene_and_resources_are_readonly_and_expire_on_project_switch(tmp_path):
    root = tmp_path / 'project'
    (root / 'content/units').mkdir(parents=True)
    (root / 'sprites/units').mkdir(parents=True)
    (root / 'mod.json').write_text('{"name":"preview"}', encoding='utf-8')
    (root / 'content/units/test.json').write_text('{"type":"flying","health":137}', encoding='utf-8')
    Image.new('RGBA', (16, 12), (10, 20, 30, 255)).save(root / 'sprites/units/test.png')
    service, ids = WorkspaceService('metadata'), count()
    session = None
    def call(action, payload=None):
        return service.request({'protocolVersion': 1, 'requestId': str(next(ids)), 'sessionId': session,
                                'action': action, 'payload': payload or {}})
    opened = call('open_project', {'path': str(root)})
    session = opened['sessionId']
    before = call('editing_state')['data']
    scene = call('preview_scene', {'path': 'content/units/test.json'})
    assert scene['ok'], scene
    resource_id = scene['data']['layers'][0]['resourceId']
    resource = call('preview_resource', {'resourceId': resource_id})
    assert resource['ok'], resource
    assert resource['data']['mime'] == 'image/png'
    assert resource['data']['width'] == 16
    assert service.request_result(resource['requestId']) == {'state': 'unknown'}
    assert service.request_result(scene['requestId']) == {'state': 'unknown'}
    assert call('editing_state')['data'] == before
    assert json.loads((root / 'content/units/test.json').read_text())['health'] == 137
    opened = call('open_project', {'path': str(root)})
    session = opened['sessionId']
    rejected = call('preview_resource', {'resourceId': resource_id})
    assert rejected['ok'] is False
    assert rejected['error']['code'] == 'PREVIEW_RESOURCE_UNAVAILABLE'
