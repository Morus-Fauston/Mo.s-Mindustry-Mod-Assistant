"""Real preference transport, persistence and business-history isolation."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.core import config_loader, paths, session, settings
from app.desktop import preferences
from app.desktop.api import DesktopApi
from app.desktop.workspace import WorkspaceService
from test_desktop_content_bridge import Client, make_project


@pytest.fixture(autouse=True)
def preference_files(tmp_path, monkeypatch, isolate_editor_state, isolate_preferences):
    directory = tmp_path / 'preferences'
    directory.mkdir()
    monkeypatch.setattr(preferences, 'user_config_dir', lambda: directory)
    monkeypatch.setattr(paths, 'user_config_dir', lambda: directory)
    monkeypatch.setattr(settings, '_USER_FILE', directory / 'settings.json')
    monkeypatch.setattr(settings, '_instance', None)
    monkeypatch.setattr(config_loader, '_current_mode', 'zh_en')
    monkeypatch.setattr(session, 'load_editor_state', config_loader.load_editor_state)
    monkeypatch.setattr(session, 'save_editor_state', config_loader.save_editor_state)
    return directory


def update(client, patch, revision=0, **kwargs):
    return client.call('update_settings', {'patch': patch, 'expectedPreferencesRevision': revision}, **kwargs)


@pytest.mark.parametrize('raw', [b'\xff', b'{"nested":' + b'[' * 1500 + b'0' + b']' * 1500 + b'}'], ids=['invalid-utf8', 'deep-json'])
def test_corrupt_settings_still_bootstrap_to_warning_without_overwriting(preference_files, raw):
    target = preference_files / 'settings.json'
    target.write_bytes(raw)
    api = DesktopApi('metadata')
    client = Client(api)
    value = client.call('preferences_state')
    assert value['warnings']
    assert value['values']['theme'] == 'light'
    assert client.state()['autoSaveInterval'] == 180
    response = api.request({'protocolVersion': 1, 'requestId': 'protect-damaged-settings', 'sessionId': None,
                            'action': 'update_settings', 'payload': {'patch': {'theme': 'dark'}, 'expectedPreferencesRevision': 0}})
    assert response['error']['code'] == 'PREFERENCES_READ_ONLY'
    assert target.read_bytes() == raw


def test_no_project_reads_actual_defaults_and_updates_runtime_cache(preference_files):
    client = Client(DesktopApi('metadata'))
    state = client.call('preferences_state')
    assert state['values']['display_name_mode'] == 'zh_en'
    before = client.state()
    result = update(client, {'auto_save_interval': 29, 'display_name_mode': 'en', 'theme': 'dark', 'sprite_zoom': 6})
    assert result['preferences']['revision'] == 1
    assert result['state'] == {**before, 'autoSaveInterval': 29}
    assert client.session is None
    assert settings.get_settings().get('theme') == 'dark'
    assert settings.get_settings().get('sprite_zoom') == 6
    assert config_loader.get_display_mode() == 'en'
    assert json.loads((preference_files / 'settings.json').read_text('utf-8'))['auto_save_interval'] == 29


def test_loaded_preferences_apply_before_first_editing_state(preference_files):
    (preference_files / 'settings.json').write_text(json.dumps({'auto_save_interval': 0, 'display_name_mode': 'en_zh'}), 'utf-8')
    client = Client(DesktopApi('metadata'))
    assert client.state()['autoSaveInterval'] == 0
    assert config_loader.get_display_mode() == 'en_zh'


def test_duplicate_request_and_recovery_write_only_once(monkeypatch):
    writes = []
    original = preferences.PreferencesService._write_atomic
    def record(path, data):
        writes.append(path)
        return original(path, data)
    monkeypatch.setattr(preferences.PreferencesService, '_write_atomic', staticmethod(record))
    api = DesktopApi('metadata')
    envelope = {'protocolVersion': 1, 'requestId': 'preferences-once', 'sessionId': None,
                'action': 'update_settings', 'payload': {'patch': {'theme': 'dark'}, 'expectedPreferencesRevision': 0}}
    response = api.request(envelope)
    assert response['ok']
    assert api.request(envelope) == response
    assert api.request_result('preferences-once') == {'state': 'completed', 'response': response}
    assert len(writes) == 1


def test_inflight_write_is_pending_and_competing_revision_cannot_overwrite(monkeypatch):
    started, release = Event(), Event()
    original = preferences.PreferencesService._write_atomic
    def delayed(path, data):
        started.set()
        assert release.wait(5), 'test write was not released'
        return original(path, data)
    monkeypatch.setattr(preferences.PreferencesService, '_write_atomic', staticmethod(delayed))
    api = DesktopApi('metadata')
    first = {'protocolVersion': 1, 'requestId': 'first', 'sessionId': None, 'action': 'update_settings',
             'payload': {'patch': {'theme': 'dark'}, 'expectedPreferencesRevision': 0}}
    second = {**first, 'requestId': 'second', 'payload': {'patch': {'theme': 'light'}, 'expectedPreferencesRevision': 0}}
    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(api.request, first)
        try:
            assert started.wait(5)
            assert api.request_result('first') == {'state': 'pending'}
            two = pool.submit(api.request, second)
        finally:
            release.set()
        assert one.result(timeout=5)['ok']
        assert two.result(timeout=5)['error']['code'] == 'STALE_PREFERENCES_REVISION'
    assert api.request_result('first')['response']['data']['preferences']['values']['theme'] == 'dark'


@pytest.mark.parametrize('action,payload,code', [
    ('preferences_state', {'extra': True}, 'INVALID_REQUEST'),
    ('update_settings', {'patch': {'theme': 'dark'}, 'expectedPreferencesRevision': 0, 'extra': True}, 'INVALID_REQUEST'),
    ('update_settings', {'patch': {'auto_save_interval': True}, 'expectedPreferencesRevision': 0}, 'INVALID_PREFERENCES'),
    ('update_settings', {'patch': {'theme': 'dark'}, 'expectedPreferencesRevision': True}, 'STALE_PREFERENCES_REVISION'),
    ('update_layout', {'layout': {}, 'expectedPreferencesRevision': 0}, 'INVALID_PREFERENCES'),
])
def test_invalid_requests_do_not_write_or_change_history(action, payload, code, preference_files):
    client = Client(WorkspaceService('metadata'))
    before = client.state()
    assert client.call(action, payload, ok=False)['code'] == code
    assert client.state() == before
    assert not list(preference_files.iterdir())


@pytest.mark.parametrize('mode', ['zh_en', 'en_zh', 'zh', 'en'])
def test_display_mode_reprojects_real_dirty_document_without_business_mutation(mode, tmp_path):
    client = Client(WorkspaceService('metadata'))
    client.call('open_project', {'path': str(make_project(tmp_path / 'project'))})
    client.change('create_content', kind='UnitType', name='scout', category='units')
    path = 'content/units/scout.json'
    client.change('set_field', path=path, field='health', value=813)
    before = client.state()
    result = update(client, {'display_name_mode': mode})
    after = result['state']
    assert (after['revision'], after['history'], after['sessionId']) == (before['revision'], before['history'], before['sessionId'])
    document = after['documents'][0]
    assert document['dirty'] and document['data'] == before['documents'][0]['data']
    expected = config_loader.display_name('health')
    assert document['fieldNames']['health'] == expected
    fields = [field for group in document['form']['groups'] for field in group['fields']]
    assert next(field for field in fields if field['name'] == 'health')['label'] == expected
    assert config_loader.get_field_names_zh()['health'] != 'health'
    layout = {**result['preferences']['layout'], 'leftWidth': 241, 'previewRatio': .7}
    configured = client.call('update_layout', {'layout': layout, 'expectedPreferencesRevision': 1})
    assert configured['state'] == after
    assert client.change('undo')['documents'][0]['data'].get('health') != 813


def test_global_revision_survives_project_switch_and_old_session_is_rejected(tmp_path):
    client = Client(WorkspaceService('metadata'))
    update(client, {'theme': 'dark'})
    client.call('open_project', {'path': str(make_project(tmp_path / 'first'))})
    old_session = client.session
    client.call('open_project', {'path': str(make_project(tmp_path / 'second'))})
    assert client.call('preferences_state')['revision'] == 1
    stale = {'protocolVersion': 1, 'requestId': 'stale-preferences', 'sessionId': old_session,
             'action': 'update_settings', 'payload': {'patch': {'theme': 'light'}, 'expectedPreferencesRevision': 1}}
    assert client.call('update_settings', envelope=stale, ok=False)['code'] == 'STALE_SESSION'
    assert update(client, {'sprite_zoom': 2}, 1)['preferences']['revision'] == 2


def test_atomic_save_failure_preserves_file_cache_mode_and_revision(preference_files, monkeypatch):
    client = Client(WorkspaceService('metadata'))
    before = update(client, {'display_name_mode': 'zh'})
    original = (preference_files / 'settings.json').read_bytes()
    def deny(*args):
        raise PermissionError('locked')
    monkeypatch.setattr(preferences.os, 'replace', deny)
    error = update(client, {'display_name_mode': 'en', 'auto_save_interval': 7}, 1, ok=False)
    assert error['code'] == 'PREFERENCES_SAVE_FAILED'
    assert client.call('preferences_state') == before['preferences']
    assert client.state() == before['state']
    assert config_loader.get_display_mode() == 'zh'
    assert settings.get_settings().get('auto_save_interval') == 180
    assert (preference_files / 'settings.json').read_bytes() == original


def test_broken_config_returns_warning_and_cannot_overwrite(preference_files):
    path = preference_files / 'settings.json'
    path.write_text('{broken', 'utf-8')
    client = Client(WorkspaceService('metadata'))
    assert client.call('preferences_state')['warnings']
    assert update(client, {'theme': 'dark'}, ok=False)['code'] == 'PREFERENCES_READ_ONLY'
    assert path.read_text('utf-8') == '{broken'


def test_layout_and_recent_project_survive_create_undo_redo(preference_files, tmp_path):
    client = Client(WorkspaceService('metadata', choose_directory=lambda: str(tmp_path)))
    layout = {**client.call('preferences_state')['layout'], 'leftWidth': 230, 'previewVisible': False}
    result = client.call('update_layout', {'layout': layout, 'expectedPreferencesRevision': 0})
    assert result['state']['revision'] == 0
    created = client.change('create_project', mod_id='created', displayName='新工程')
    assert created['project']['warnings'] == []
    state_file = preference_files / 'editor_state.json'
    persisted = json.loads(state_file.read_text('utf-8'))
    assert persisted['web_workbench'] == layout
    assert persisted['last_project'] == str(tmp_path / 'created')
    client.change('undo')
    persisted['last_project'] = 'prior'
    state_file.write_text(json.dumps(persisted), 'utf-8')
    client.change('redo')
    persisted = json.loads(state_file.read_text('utf-8'))
    assert persisted['last_project'] == str(tmp_path / 'created') and persisted['web_workbench'] == layout
    assert client.call('preferences_state')['revision'] == 1


def test_recent_record_failure_warns_but_new_project_is_usable(preference_files, tmp_path):
    state_file = preference_files / 'editor_state.json'
    state_file.write_text('{broken', 'utf-8')
    client = Client(WorkspaceService('metadata', choose_directory=lambda: str(tmp_path)))
    assert client.call('recent_projects')['warnings']
    created = client.change('create_project', mod_id='created', displayName='新工程')
    assert created['project']['warnings'] and (tmp_path / 'created/mod.json').is_file()
    assert state_file.read_text('utf-8') == '{broken'
    client.change('create_content', kind='UnitType', name='scout', category='units')


def test_failed_candidate_preparation_does_not_replace_recent_path(preference_files, tmp_path, monkeypatch):
    from app.desktop import workspace
    root = make_project(tmp_path / 'candidate')
    state_file = preference_files / 'editor_state.json'
    state_file.write_text('{"last_project":"prior"}', 'utf-8')
    client = Client(WorkspaceService('metadata'))
    def broken(*args):
        raise ValueError('invalid resource')
    monkeypatch.setattr(workspace, 'ResourceWatch', broken)
    assert client.call('open_project', {'path': str(root)}, ok=False)['code'] == 'PROJECT_OPEN_FAILED'
    assert json.loads(state_file.read_text('utf-8'))['last_project'] == 'prior'
