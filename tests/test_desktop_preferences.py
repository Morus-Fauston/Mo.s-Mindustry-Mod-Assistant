"""Preferences persist independently of project data and preserve legacy files."""

import json
import os
from pathlib import Path

import pytest

from app.desktop.preferences import PreferencesError, PreferencesService


DEFAULTS = Path(__file__).resolve().parents[1] / 'app/config/settings_default.json'
LAYOUT = {'leftWidth': None, 'rightWidth': None, 'previewRatio': None,
          'filesVisible': True, 'previewVisible': True}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def test_reads_real_defaults_and_preserves_legacy_and_unknown_values(tmp_path):
    write_json(tmp_path / 'settings.json', {'theme': 'dark', 'mindustry_path': '旧路径',
                                         'future': {'choice': [1]}, 'nullable': None})
    write_json(tmp_path / 'editor_state.json', {'last_project': '不应修改', 'future': 3})
    service = PreferencesService(DEFAULTS, tmp_path)
    state = service.state()
    assert state['defaults'] == {'theme': 'light', 'display_name_mode': 'zh_en',
        'auto_save_interval': 180, 'sprite_zoom': 4, 'mindustry_path': '',
        'bullet_type_count': 5, 'window_width': 1400, 'window_height': 900}
    assert state['values']['theme'] == 'dark'
    assert state['values']['mindustry_path'] == '旧路径'
    assert state['values']['future'] == {'choice': [1]}
    assert state['values']['nullable'] is None
    assert state['layout'] == LAYOUT
    assert state['warnings'] == []
    state['values']['future']['choice'].append(2)
    state['defaults']['theme'] = 'changed'
    state['layout']['filesVisible'] = False
    assert service.state()['values']['future'] == {'choice': [1]}
    assert service.state()['defaults']['theme'] == 'light'
    assert service.state()['layout'] == LAYOUT


def test_settings_apply_is_durable_and_keeps_unedited_keys(tmp_path):
    write_json(tmp_path / 'settings.json', {'window_width': 1700, 'future': {'x': 2}, 'nullable': None})
    service = PreferencesService(DEFAULTS, tmp_path)
    before = service.state()
    applied = service.update_settings({'theme': 'dark', 'display_name_mode': 'en_zh',
        'auto_save_interval': 0, 'sprite_zoom': 8}, before['revision'])
    assert applied['revision'] == before['revision'] + 1
    reopened = PreferencesService(DEFAULTS, tmp_path).state()
    assert reopened['values'] == applied['values']
    assert reopened['values']['nullable'] is None
    assert reopened['values']['window_width'] == 1700
    assert reopened['values']['future'] == {'x': 2}
    assert reopened['values']['auto_save_interval'] == 0
    assert reopened['values']['sprite_zoom'] == 8
    # Existing compact override storage remains compatible with legacy Settings.
    assert 'bullet_type_count' not in json.loads((tmp_path / 'settings.json').read_text('utf-8'))


@pytest.mark.parametrize('patch', [None, [], {'theme': 'unknown'}, {'theme': []},
    {'display_name_mode': 'both'}, {'auto_save_interval': True}, {'auto_save_interval': -1},
    {'auto_save_interval': 3601}, {'auto_save_interval': 1.0}, {'sprite_zoom': 0},
    {'sprite_zoom': 9}, {'sprite_zoom': '4'}, {'sprite_zoom': False},
    {'theme': 'dark', 'window_width': 1900}, {'unknown': 2}])
def test_rejects_invalid_settings_without_mutation(tmp_path, patch):
    service = PreferencesService(DEFAULTS, tmp_path)
    before = service.state()
    with pytest.raises(Exception) as error:
        service.update_settings(patch, before['revision'])
    assert error.value.code == 'INVALID_PREFERENCES'
    assert service.state() == before
    assert not (tmp_path / 'settings.json').exists()


@pytest.mark.parametrize('revision', [-1, 1, None, False, 0.0, '0'])
def test_stale_or_noninteger_preferences_revision_rejected(tmp_path, revision):
    service = PreferencesService(DEFAULTS, tmp_path)
    before = service.state()
    with pytest.raises(Exception) as error:
        service.update_settings({'theme': 'dark'}, revision)
    assert error.value.code == 'STALE_PREFERENCES_REVISION'
    assert service.state() == before


@pytest.mark.parametrize('mode', ['zh_en', 'en_zh', 'zh', 'en'])
def test_all_display_modes_and_numeric_endpoints(tmp_path, mode):
    service = PreferencesService(DEFAULTS, tmp_path)
    result = service.update_settings({'display_name_mode': mode, 'auto_save_interval': 3600,
                                      'sprite_zoom': 1}, 0)
    assert result['values']['display_name_mode'] == mode
    assert PreferencesService(DEFAULTS, tmp_path).state()['values'] == result['values']


def test_layout_reopens_and_merges_latest_editor_state_without_losing_recent_project(tmp_path):
    write_json(tmp_path / 'editor_state.json', {'last_project': '旧工程', 'future': {'keep': 1}})
    service = PreferencesService(DEFAULTS, tmp_path)
    write_json(tmp_path / 'editor_state.json', {'last_project': '新工程', 'future': {'keep': 2}})
    layout = {**LAYOUT, 'leftWidth': 218, 'rightWidth': 370.5, 'previewRatio': 0.55,
              'filesVisible': False}
    result = service.update_layout(layout, 0)
    assert result['layout'] == layout
    assert result['revision'] == 1
    assert PreferencesService(DEFAULTS, tmp_path).state()['layout'] == layout
    stored = json.loads((tmp_path / 'editor_state.json').read_text('utf-8'))
    assert stored == {'last_project': '新工程', 'future': {'keep': 2}, 'web_workbench': layout}
    service.update_layout(LAYOUT, 1)
    assert PreferencesService(DEFAULTS, tmp_path).state()['layout'] == LAYOUT


@pytest.mark.parametrize('patch', [None, [], {}, {'unknown': 1}, {'leftWidth': True},
    {'leftWidth': 159}, {'rightWidth': 304}, {'rightWidth': 10001},
    {'previewRatio': 0}, {'previewRatio': 1}, {'previewRatio': float('nan')},
    {'leftWidth': float('inf')}, {'filesVisible': 1}, {'previewVisible': None}])
def test_layout_strict_schema_and_bounds(tmp_path, patch):
    service = PreferencesService(DEFAULTS, tmp_path)
    value = {**LAYOUT, **patch} if isinstance(patch, dict) and patch else patch
    before = service.state()
    with pytest.raises(Exception) as error:
        service.update_layout(value, 0)
    assert error.value.code == 'INVALID_PREFERENCES'
    assert service.state() == before
    assert not (tmp_path / 'editor_state.json').exists()


def test_layout_and_settings_share_only_preferences_revision(tmp_path):
    service = PreferencesService(DEFAULTS, tmp_path)
    service.update_layout(LAYOUT, 0)
    with pytest.raises(Exception) as error:
        service.update_settings({'theme': 'dark'}, 0)
    assert error.value.code == 'STALE_PREFERENCES_REVISION'
    state = service.update_settings({'theme': 'dark'}, 1)
    with pytest.raises(Exception) as error:
        service.update_layout(LAYOUT, 1)
    assert error.value.code == 'STALE_PREFERENCES_REVISION'
    assert service.state() == state


@pytest.mark.parametrize('filename,raw', [('settings.json', b'{broken'),
    ('settings.json', b'[]'), ('settings.json', b'\xff'),
    ('settings.json', b'{"sprite_zoom":0,"future":2}'),
    ('settings.json', b'{"future":NaN}'),
    ('editor_state.json', b'null'), ('editor_state.json', b'{"web_workbench":{}}')])
def test_bad_existing_file_warns_and_cannot_be_silently_overwritten(tmp_path, filename, raw):
    path = tmp_path / filename
    path.write_bytes(raw)
    service = PreferencesService(DEFAULTS, tmp_path)
    before = service.state()
    assert before['warnings']
    assert before['values']['sprite_zoom'] == 4
    assert before['layout'] == LAYOUT
    with pytest.raises(Exception) as error:
        if filename == 'settings.json':
            service.update_settings({'theme': 'dark'}, 0)
        else:
            service.update_layout(LAYOUT, 0)
    assert error.value.code == 'PREFERENCES_READ_ONLY'
    assert path.read_bytes() == raw
    assert service.state()['revision'] == 0


def test_missing_defaults_warns_and_prevents_settings_write(tmp_path):
    service = PreferencesService(tmp_path / 'missing.json', tmp_path / 'user')
    assert service.state()['warnings']
    assert service.state()['values']['theme'] == 'light'
    with pytest.raises(Exception) as error:
        service.update_settings({'theme': 'dark'}, 0)
    assert error.value.code == 'PREFERENCES_READ_ONLY'
    assert not (tmp_path / 'user/settings.json').exists()


def test_unreadable_user_file_is_reported_without_overwrite(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{}', encoding='utf-8')
    original_read = Path.read_text
    def unreadable(self, *args, **kwargs):
        if self == path:
            raise PermissionError('denied')
        return original_read(self, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', unreadable)
    service = PreferencesService(DEFAULTS, tmp_path)
    assert service.state()['warnings']
    with pytest.raises(Exception) as error:
        service.update_settings({'theme': 'dark'}, 0)
    assert error.value.code == 'PREFERENCES_READ_ONLY'
    assert path.read_bytes() == b'{}'


def test_write_rereads_unknown_user_keys_and_detects_new_corruption(tmp_path):
    service = PreferencesService(DEFAULTS, tmp_path)
    write_json(tmp_path / 'settings.json', {'new_future': None, 'window_height': 1080})
    updated = service.update_settings({'theme': 'dark'}, 0)
    assert updated['values']['new_future'] is None
    assert updated['values']['window_height'] == 1080
    (tmp_path / 'editor_state.json').write_text('{damaged', encoding='utf-8')
    with pytest.raises(Exception) as error:
        service.update_layout(LAYOUT, 1)
    assert error.value.code == 'PREFERENCES_READ_ONLY'
    assert service.state()['warnings']
    assert (tmp_path / 'editor_state.json').read_text('utf-8') == '{damaged'


@pytest.mark.parametrize('method,filename', [('update_settings', 'settings.json'),
                                           ('update_layout', 'editor_state.json')])
@pytest.mark.parametrize('failure', ['replace', 'fsync', 'mkdir'])
def test_io_failure_preserves_snapshot_and_original_bytes_then_can_retry(tmp_path, monkeypatch, method, filename, failure):
    write_json(tmp_path / 'settings.json', {'theme': 'light', 'future': None})
    write_json(tmp_path / 'editor_state.json', {'last_project': '工程', 'future': [1]})
    service = PreferencesService(DEFAULTS, tmp_path)
    before = service.state()
    original = (tmp_path / filename).read_bytes()
    value = {'theme': 'dark'} if method == 'update_settings' else {**LAYOUT, 'filesVisible': False}
    def denied(*args, **kwargs):
        raise PermissionError('injected filesystem failure')
    with monkeypatch.context() as boundary:
        boundary.setattr(Path if failure == 'mkdir' else os, failure, denied)
        with pytest.raises(PreferencesError) as error:
            getattr(service, method)(value, 0)
        assert error.value.code == 'PREFERENCES_SAVE_FAILED'
    assert service.state() == before
    assert (tmp_path / filename).read_bytes() == original
    assert not list(tmp_path.glob('.*.tmp'))
    result = getattr(service, method)(value, 0)
    assert result['revision'] == 1
    assert PreferencesService(DEFAULTS, tmp_path).state()['values'] == result['values']
    assert PreferencesService(DEFAULTS, tmp_path).state()['layout'] == result['layout']


def test_service_publishes_new_state_only_after_atomic_replacement(tmp_path, monkeypatch):
    service = PreferencesService(DEFAULTS, tmp_path)
    before = service.state()
    real_replace = os.replace
    def replace(source, destination):
        assert service.state() == before
        real_replace(source, destination)
    monkeypatch.setattr(os, 'replace', replace)
    assert service.update_settings({'theme': 'dark'}, 0)['values']['theme'] == 'dark'


def test_extreme_integer_layout_is_rejected_as_validation_error(tmp_path):
    service = PreferencesService(DEFAULTS, tmp_path)
    with pytest.raises(PreferencesError) as error:
        service.update_layout({**LAYOUT, 'leftWidth': 10 ** 400}, 0)
    assert error.value.code == 'INVALID_PREFERENCES'


def test_bad_layout_does_not_prevent_unrelated_valid_settings_save(tmp_path):
    (tmp_path / 'editor_state.json').write_text('{bad', encoding='utf-8')
    service = PreferencesService(DEFAULTS, tmp_path)
    result = service.update_settings({'theme': 'dark'}, 0)
    assert result['values']['theme'] == 'dark'
    assert result['warnings']
    assert (tmp_path / 'editor_state.json').read_text('utf-8') == '{bad'
