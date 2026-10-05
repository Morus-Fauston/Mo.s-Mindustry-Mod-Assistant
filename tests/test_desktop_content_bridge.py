"""Real content-file workflows through the serialized desktop boundary."""
import json
from itertools import count
from pathlib import Path

import pytest

from app.desktop.workspace import WorkspaceService
from app.desktop.api import DesktopApi


class Client:
    def __init__(self, service):
        self.service, self.session, self.ids = service, None, count()

    def call(self, action, payload=None, *, ok=True, envelope=None):
        request = envelope or {'protocolVersion': 1, 'requestId': f'content-{next(self.ids)}',
                               'sessionId': self.session, 'action': action, 'payload': payload or {}}
        response = self.service.request(request)
        assert response['ok'] is ok, response
        if ok:
            self.session = response['sessionId']
        return response['data'] if ok else response['error']

    def state(self):
        return self.call('editing_state')

    def change(self, action, **payload):
        return self.call(action, {'expectedRevision': self.state()['revision'], **payload})


def make_project(root):
    root.mkdir()
    (root / 'mod.json').write_text('{"name":"old","displayName":"旧工程"}', encoding='utf-8')
    return root


def test_real_create_rename_delete_and_history_report_tree_and_identity(tmp_path):
    root = make_project(tmp_path / 'project')
    client = Client(WorkspaceService('metadata'))
    client.call('open_project', {'path': str(root)})
    result = client.change('create_content', kind='UnitType-flying', name='scout', category='units', overwrite=False)
    old, new = 'content/units/scout.json', 'content/units/new-scout.json'
    assert result['activePath'] == old and result['change']['action'] == 'create'
    assert json.loads((root / old).read_text('utf-8'))['type'] == 'flying'
    document = next(row for row in result['state']['documents'] if row['path'] == old)
    assert not document['dirty']
    renamed = client.change('rename_content', path=old, newName='new-scout')
    assert renamed['activePath'] == new and not (root / old).exists()
    deleted = client.change('delete_content', path=new, confirmed=True)
    assert deleted['activePath'] is None and deleted['state']['documents'] == [] and not (root / new).exists()
    undone = client.change('undo')
    assert undone['activePath'] == new and undone['contentChange']['undo'] is True
    assert next(row for row in undone['documents'] if row['path'] == new)['data']['name'] == 'new-scout'
    restored = client.change('undo')
    assert restored['activePath'] == old and (root / old).exists() and not (root / new).exists()
    client.change('redo')
    assert (root / new).exists() and not (root / old).exists()


def test_create_edit_save_undo_edit_then_undo_creation_acknowledges_saved_disk(tmp_path):
    root = make_project(tmp_path / 'project')
    client = Client(WorkspaceService('metadata'))
    client.call('open_project', {'path': str(root)})
    path = 'content/units/scout.json'
    client.change('create_content', kind='UnitType', name='scout', category='units')
    client.change('set_field', path=path, field='health', value=345)
    client.change('save_opened')
    assert json.loads((root / path).read_text('utf-8'))['health'] == 345
    client.change('undo')
    result = client.change('undo')
    assert not (root / path).exists() and result['documents'] == []
    client.change('redo')
    result = client.change('redo')
    assert result['documents'][0]['data']['health'] == 345


def test_content_catalogue_without_project_is_real_and_rejects_extra_fields():
    client = Client(WorkspaceService('metadata'))
    catalogue = client.call('content_catalogue')
    assert {row['id'] for row in catalogue['categories']} == {'units', 'blocks', 'weapons'}
    assert any(item['kind'] == 'GenericCrafter' for row in catalogue['categories'] for item in row['templates'])
    assert client.call('content_catalogue', {'path': 'outside'}, ok=False)['code'] == 'INVALID_REQUEST'
    assert client.call('create_content', {'expectedRevision': 0}, ok=False)['code'] == 'NO_PROJECT'


def test_three_categories_same_name_are_separate_and_reveal_uses_host_once(tmp_path):
    root = make_project(tmp_path / 'project')
    revealed = []
    api = DesktopApi('metadata', reveal_file=lambda path: revealed.append(path))
    client = Client(api)
    client.call('open_project', {'path': str(root)})
    for category, kind in [('units', 'UnitType'), ('blocks', 'Wall'), ('weapons', 'Weapon')]:
        result = client.change('create_content', category=category, kind=kind, name='same')
        assert result['activePath'] == f'content/{category}/same.json'
    assert len(client.state()['documents']) == 3
    request = {'protocolVersion': 1, 'requestId': 'reveal-once', 'sessionId': client.session, 'action': 'reveal_content',
               'payload': {'path': 'content/weapons/same.json', 'expectedRevision': client.state()['revision']}}
    result = client.call('reveal_content', envelope=request)
    assert result['revealed'] and client.call('reveal_content', envelope=request) == result
    assert revealed == [root / 'content/weapons/same.json']
    client.change('delete_content', path='content/units/same.json', confirmed=True)
    assert (root / 'content/blocks/same.json').exists() and (root / 'content/weapons/same.json').exists()


def test_dirty_rename_save_and_history_keep_registered_object_and_saved_baseline(tmp_path):
    root = make_project(tmp_path / 'project')
    client = Client(WorkspaceService('metadata'))
    client.call('open_project', {'path': str(root)})
    old, new = 'content/units/scout.json', 'content/units/new-scout.json'
    client.change('create_content', kind='UnitType', name='scout', category='units')
    identity = client.service._session.loaded_content('units/scout.json')
    data = identity.data
    client.change('set_field', path=old, field='health', value=234)
    before = client.state()
    error = client.call('rename_content', {'path': old, 'newName': 'new-scout', 'expectedRevision': before['revision']}, ok=False)
    assert error['code'] == 'UNSAVED_CHANGES' and error['path'] == old
    assert client.state() == before
    no_op = client.change('rename_content', path=old, newName='scout')
    assert no_op['state'] == before
    client.change('rename_content', path=old, newName='new-scout', decision='save')
    assert client.service._session.loaded_content('units/new-scout.json') is identity and identity.data is data
    client.change('set_field', path=new, field='health', value=456)
    client.change('save_opened')
    client.change('undo')
    restored = client.change('undo')
    assert restored['documents'][0]['path'] == old and not restored['documents'][0]['dirty']
    assert json.loads((root / old).read_text('utf-8'))['health'] == 234
    assert client.service._session.loaded_content('units/scout.json') is identity and identity.data is data
    client.change('redo')
    result = client.change('redo')
    assert result['documents'][0]['data']['health'] == 456 and result['documents'][0]['dirty']


@pytest.mark.parametrize('action,payload', [
    ('create_content', {'kind': 'UnitType', 'name': 'bad', 'category': 'units', 'overwrite': 'true'}),
    ('create_content', {'kind': 'Weapon', 'name': 'bad', 'category': 'units'}),
    ('create_content', {'kind': 'UnitType', 'name': '../bad', 'category': 'units'}),
    ('delete_content', {'path': 'content/units/scout.json', 'confirmed': 1}),
    ('delete_content', {'path': '../outside.json', 'confirmed': True}),
    ('rename_content', {'path': 'content/units/scout.json', 'newName': 'new', 'decision': 'cancel'}),
    ('rename_content', {'path': 'content/units/scout.json', 'newName': 'scout', 'decision': 'cancel'}),
    ('reveal_content', {'path': 'content/units/scout.json', 'target': 'outside'}),
])
def test_invalid_content_requests_do_not_change_state_or_files(tmp_path, action, payload):
    root = make_project(tmp_path / 'project')
    client = Client(WorkspaceService('metadata'))
    client.call('open_project', {'path': str(root)})
    client.change('create_content', kind='UnitType', name='scout', category='units')
    before = client.state()
    files = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    client.call(action, {**payload, 'expectedRevision': before['revision']}, ok=False)
    assert client.state() == before
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()} == files


def test_overwrite_broken_json_and_delete_undo_restore_exact_source(tmp_path):
    root = make_project(tmp_path / 'project')
    target = root / 'content/units/broken.json'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'{"bad":\n')
    client = Client(WorkspaceService('metadata'))
    client.call('open_project', {'path': str(root)})
    original = client.call('read_document', {'path': 'content/units/broken.json'})
    conflict = client.call('create_content', {'kind': 'UnitType', 'name': 'broken', 'category': 'units',
                                           'expectedRevision': client.state()['revision']}, ok=False)
    assert conflict['code'] == 'FILE_EXISTS'
    client.change('create_content', kind='UnitType', name='broken', category='units', overwrite=True)
    undone = client.change('undo')
    assert target.read_bytes() == b'{"bad":\n' and undone['documents'][0]['sourceText'] == original['sourceText']
    client.change('delete_content', path='content/units/broken.json', confirmed=True)
    client.change('save_opened')
    assert not target.exists()
    client.change('undo')
    assert target.read_bytes() == b'{"bad":\n'


def test_external_bytes_block_undo_and_tree_refresh_failure_does_not_replay_write(tmp_path, monkeypatch):
    root = make_project(tmp_path / 'project')
    client = Client(WorkspaceService('metadata'))
    client.call('open_project', {'path': str(root)})
    revision = client.state()['revision']
    def broken_tree(_project):
        raise OSError('tree temporarily locked')
    monkeypatch.setattr(client.service, '_tree', broken_tree)
    request = {'protocolVersion': 1, 'requestId': 'create-once', 'sessionId': client.session, 'action': 'create_content',
               'payload': {'kind': 'UnitType', 'name': 'scout', 'category': 'units', 'expectedRevision': revision}}
    created = client.call('create_content', envelope=request)
    assert client.call('create_content', envelope=request) == created
    target = root / 'content/units/scout.json'
    target.write_bytes(b'{"external":true}')
    before = client.state()
    error = client.call('undo', {'expectedRevision': before['revision']}, ok=False)
    assert error['code'] == 'HISTORY_FAILED' and '文件已被其他操作修改' in error['message']
    assert target.read_bytes() == b'{"external":true}' and client.state() == before


@pytest.mark.parametrize('action,code', [('create_content', 'CONTENT_FAILED'), ('undo', 'HISTORY_FAILED')])
def test_identity_callback_runtime_failure_rolls_back_and_returns_safe_error(tmp_path, monkeypatch, action, code):
    root = make_project(tmp_path / 'project')
    client = Client(WorkspaceService('metadata'))
    client.call('open_project', {'path': str(root)})
    if action == 'undo':
        client.change('create_content', kind='UnitType', name='scout', category='units')
    identity = client.service._content_identity
    method = '_forward' if action == 'create_content' else '_restore'
    original = getattr(identity, method)
    calls = []

    def fail_once(*args):
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError('模拟身份发布故障')
        return original(*args)

    monkeypatch.setattr(identity, method, fail_once)
    before = client.state()
    files = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    payload = {'expectedRevision': before['revision']}
    if action == 'create_content':
        payload.update(kind='UnitType', name='scout', category='units')
    error = client.call(action, payload, ok=False)
    assert error['code'] == code and '模拟身份发布故障' in error['message']
    assert client.state() == before
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()} == files
