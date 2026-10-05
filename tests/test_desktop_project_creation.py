"""Native-directory seam, candidate adoption and real project command history."""
from pathlib import Path
import json
import gc
import weakref

import pytest
from PIL import Image

from app.desktop.workspace import WorkspaceService
from app.desktop import workspace as workspace_module
from app.desktop.api import DesktopApi
from test_desktop_content_bridge import Client, make_project


def test_create_project_owns_stack_and_roundtrips_content_across_empty_workbench(tmp_path):
    client = Client(WorkspaceService('metadata', choose_directory=lambda: str(tmp_path)))
    created = client.change('create_project', mod_id='new-mod', displayName='新工程', author='作者')
    assert created['project']['sessionId'] == created['state']['sessionId'] == client.session
    assert created['project']['root'] == str(tmp_path / 'new-mod')
    stack = client.service._session.command_stack
    first = client.session
    client.change('create_content', kind='UnitType', name='scout', category='units', overwrite=False)
    client.change('undo')
    empty = client.change('undo')
    assert empty['project'] is None and empty['documents'] == []
    assert empty['history']['canRedo'] and not empty['history']['canUndo']
    assert client.session != first and not (tmp_path / 'new-mod').exists()
    assert client.service._session.command_stack is stack
    detached = client.session
    restored = client.change('redo')
    assert restored['project']['sessionId'] == client.session != detached
    assert client.service._session.command_stack is stack
    content = client.change('redo')
    assert content['activePath'] == 'content/units/scout.json'
    assert content['documents'][0]['path'] == content['activePath']
    assert (tmp_path / 'new-mod/content/units/scout.json').is_file()


def test_existing_target_failure_keeps_old_dirty_document_and_history(tmp_path):
    old = make_project(tmp_path / 'old')
    client = Client(WorkspaceService('metadata', choose_directory=lambda: str(tmp_path)))
    client.call('open_project', {'path': str(old)})
    client.change('create_content', kind='UnitType', name='scout', category='units')
    client.change('set_field', path='content/units/scout.json', field='health', value=987)
    before, sid = client.state(), client.session
    error = client.call('create_project', {'mod_id': 'old', 'displayName': '冲突', 'author': '',
                       'decision': 'discard', 'expectedRevision': before['revision']}, ok=False)
    assert error['code'] == 'FILE_EXISTS'
    assert client.session == sid and client.state() == before


def test_native_cancel_keeps_dirty_old_session_and_no_project_side_effect(tmp_path):
    old = make_project(tmp_path / 'old')
    chosen = []
    client = Client(DesktopApi('metadata', choose_directory=lambda: chosen.append(True)))
    client.call('open_project', {'path': str(old)})
    client.change('create_content', kind='UnitType', name='scout', category='units')
    client.change('set_field', path='content/units/scout.json', field='health', value=345)
    before, sid = client.state(), client.session
    cancelled = client.change('create_project', mod_id='new', displayName='新工程', author='', decision='discard')
    assert cancelled == {'cancelled': True, 'state': before}
    assert client.session == sid and client.state() == before and not (tmp_path / 'new').exists()
    assert len(chosen) == 1


def test_new_project_duplicate_request_is_one_creation_and_old_session_cannot_replay(tmp_path):
    chosen = []
    client = Client(WorkspaceService('metadata', choose_directory=lambda: chosen.append(True) or str(tmp_path)))
    request = {'protocolVersion': 1, 'requestId': 'new-project-once', 'sessionId': None, 'action': 'create_project',
               'payload': {'mod_id': 'new', 'displayName': '新工程', 'author': '作者', 'expectedRevision': 0}}
    created = client.call('create_project', envelope=request)
    assert client.call('create_project', envelope=request) == created and len(chosen) == 1
    first = client.session
    undone = client.change('undo')
    assert client.session != first and undone['project'] is None
    assert client.call('create_project', envelope=request, ok=False)['code'] == 'STALE_SESSION'
    assert not (tmp_path / 'new').exists()


def test_initial_service_failure_rolls_back_new_directory_and_keeps_old_services(tmp_path, monkeypatch):
    old = make_project(tmp_path / 'old')
    client = Client(WorkspaceService('metadata', choose_directory=lambda: str(tmp_path)))
    client.call('open_project', {'path': str(old)})
    client.change('create_content', kind='UnitType', name='scout', category='units')
    client.change('set_field', path='content/units/scout.json', field='health', value=456)
    before, sid = client.state(), client.session
    watch, generation = client.service._resource_watch, client.service._generation
    original = workspace_module.ResourceWatch
    def fail_new(root):
        if root.name == 'new':
            raise OSError('资源初始化失败')
        return original(root)
    monkeypatch.setattr(workspace_module, 'ResourceWatch', fail_new)
    error = client.call('create_project', {'mod_id': 'new', 'displayName': '新工程', 'author': '',
                       'decision': 'discard', 'expectedRevision': before['revision']}, ok=False)
    assert error['code'] == 'PROJECT_CREATE_FAILED' and '资源初始化失败' in error['message']
    assert client.session == sid and client.state() == before
    assert not (tmp_path / 'new').exists()
    assert client.service._resource_watch is watch and not watch._closed
    assert client.service._generation is generation and not generation._closed


def test_old_save_failure_removes_prepared_candidate_but_keeps_old_workbench(tmp_path, monkeypatch):
    old = make_project(tmp_path / 'old')
    client = Client(WorkspaceService('metadata', choose_directory=lambda: str(tmp_path)))
    client.call('open_project', {'path': str(old)})
    client.change('create_content', kind='UnitType', name='scout', category='units')
    client.change('set_field', path='content/units/scout.json', field='health', value=456)
    before, sid = client.state(), client.session
    def fail_save(_content):
        raise PermissionError('文件被占用')
    monkeypatch.setattr(client.service._session, 'save_content', fail_save)
    error = client.call('create_project', {'mod_id': 'new', 'displayName': '新工程', 'author': '',
                       'decision': 'save', 'expectedRevision': before['revision']}, ok=False)
    assert '保存' in error['message']
    assert client.session == sid and client.state() == before and not (tmp_path / 'new').exists()
    assert client.service._pending_project_services is None


def test_undo_external_file_failure_preserves_created_project_and_redo_failure_is_recoverable(tmp_path, monkeypatch):
    client = Client(WorkspaceService('metadata', choose_directory=lambda: str(tmp_path)))
    created = client.change('create_project', mod_id='new', displayName='新工程', author='')
    extra = tmp_path / 'new/user.txt'
    extra.write_text('保留用户文件', encoding='utf-8')
    before, sid = client.state(), client.session
    error = client.call('undo', {'expectedRevision': before['revision']}, ok=False)
    assert error['code'] == 'HISTORY_FAILED' and extra.exists()
    assert client.session == sid and client.state() == before
    extra.unlink()
    client.change('undo')
    detached = client.session
    original = workspace_module.ResourceWatch
    def fail_resource(_root):
        raise OSError('重做资源初始化失败')
    monkeypatch.setattr(workspace_module, 'ResourceWatch', fail_resource)
    error = client.call('redo', {'expectedRevision': client.state()['revision']}, ok=False)
    assert error['code'] == 'HISTORY_FAILED'
    assert client.session == detached and client.state()['history']['canRedo'] and not (tmp_path / 'new').exists()
    monkeypatch.setattr(workspace_module, 'ResourceWatch', original)
    redone = client.change('redo')
    assert redone['project']['root'] == created['project']['root'] and client.session != detached


def test_successful_project_adoption_closes_only_old_resources_and_uses_new_history(tmp_path):
    old = make_project(tmp_path / 'old')
    client = Client(WorkspaceService('metadata', choose_directory=lambda: str(tmp_path)))
    client.call('open_project', {'path': str(old)})
    client.change('create_content', kind='UnitType', name='scout', category='units')
    old_stack, watch, generation = client.service._session.command_stack, client.service._resource_watch, client.service._generation
    created = client.change('create_project', mod_id='new', displayName='新工程', author='')
    assert client.service._session.command_stack is not old_stack
    assert created['state']['history']['undoDescription'] == '新建工程 new'
    assert watch._closed and generation._closed
    client.change('undo')
    assert not (tmp_path / 'new').exists() and (old / 'content/units/scout.json').exists()


def test_project_undo_releases_first_preview_cache_while_retaining_redo_history(tmp_path):
    source = tmp_path / 'source.png'
    with Image.new('RGBA', (5, 3), (12, 34, 56, 128)) as image:
        image.save(source)
    client = Client(WorkspaceService('metadata', choose_directory=lambda: str(tmp_path),
                                     choose_sprite=lambda: str(source)))
    client.change('create_project', mod_id='new', displayName='新工程', author='')
    stack = client.service._session.command_stack
    path = 'content/units/scout.json'
    client.change('create_content', kind='UnitType', name='scout', category='units')
    client.change('import_sprite', path=path, suffix='')
    scene = client.call('preview_scene', {'path': path})
    resource = client.call('preview_resource', {'resourceId': scene['layers'][0]['resourceId']})
    assert resource['dataUrl'].startswith('data:image/png;base64,')
    assert (resource['width'], resource['height']) == (5, 3)
    assert client.service._preview._cache_bytes > 0
    preview = weakref.ref(client.service._preview)
    watch = weakref.ref(client.service._resource_watch)
    generation = weakref.ref(client.service._generation)

    client.change('undo')  # Imported PNG.
    client.change('undo')  # Content JSON.
    detached = client.change('undo')  # Project directory.
    gc.collect()
    assert detached['project'] is None and detached['history']['canRedo']
    assert client.service._session.command_stack is stack
    assert preview() is None, 'Detached project history must not retain the old preview PNG cache'
    assert watch() is None and generation() is None

    for _ in range(3):
        client.change('redo')
    assert client.service._session.command_stack is stack
    restored = client.call('preview_scene', {'path': path})
    restored_resource = client.call('preview_resource', {'resourceId': restored['layers'][0]['resourceId']})
    assert restored_resource['sessionId'] != resource['sessionId']
    assert restored_resource['dataUrl'] == resource['dataUrl']


@pytest.mark.parametrize('payload', [
    {'mod_id': '../escape', 'displayName': 'bad'},
    {'mod_id': 'new', 'displayName': 1},
    {'mod_id': 'new', 'displayName': 'bad', 'author': []},
    {'mod_id': 'new', 'displayName': 'bad', 'decision': 'cancel'},
    {'mod_id': 'new', 'displayName': 'bad', 'path': '/outside'},
])
def test_invalid_project_requests_never_open_native_picker(tmp_path, payload):
    picks = []
    client = Client(WorkspaceService('metadata', choose_directory=lambda: picks.append(True) or str(tmp_path)))
    client.call('create_project', {**payload, 'expectedRevision': 0}, ok=False)
    assert not picks and not (tmp_path / 'new').exists()
