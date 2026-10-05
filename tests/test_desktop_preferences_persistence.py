"""Real settings files survive project lifecycle and storage failures."""

import json
import os
from pathlib import Path

import pytest

from app.core import config_loader, paths
import app.core.session as session_module
from app.core.project import Project
from app.core.session import ProjectSession
from app.desktop.preferences import PreferencesError, PreferencesService
from app.desktop.content_actions import create_project


ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / 'app/config/settings_default.json'
LAYOUT = {'leftWidth': 218, 'rightWidth': 370.5, 'previewRatio': 0.55,
          'filesVisible': False, 'previewVisible': True}


@pytest.fixture
def real_persistence(tmp_path, monkeypatch):
    """Use production persistence with only its filesystem location isolated."""
    user_dir = tmp_path / 'user'
    user_dir.mkdir()
    monkeypatch.setattr(paths, 'user_config_dir', lambda: user_dir)
    # Undo the legacy suite's fake serializer for this integration seam.
    monkeypatch.setattr(session_module, 'load_editor_state', config_loader.load_editor_state)
    monkeypatch.setattr(session_module, 'save_editor_state', config_loader.save_editor_state)
    return user_dir


def write_state(user_dir, value):
    (user_dir / 'editor_state.json').write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def test_opening_project_preserves_workbench_and_unknown_editor_state(real_persistence, tmp_path):
    write_state(real_persistence, {'last_project': '旧工程', 'web_workbench': LAYOUT,
                                  'future': {'nested': [1, None, '保留']}})
    project = Project.create(tmp_path, 'new-mod', '新工程')
    session = ProjectSession(ROOT / 'metadata')
    assert session.open_project(project.root).root == project.root
    assert PreferencesService(DEFAULTS, real_persistence).state()['layout'] == LAYOUT
    assert config_loader.load_editor_state() == {'last_project': str(project.root),
        'web_workbench': LAYOUT, 'future': {'nested': [1, None, '保留']}}


@pytest.mark.parametrize('raw', [b'{broken', b'[]', b'null', b'\xff',
                                b'{"future":NaN}', b'{"future":Infinity}'])
@pytest.mark.parametrize('operation', ['open', 'create'])
def test_corrupt_state_is_preserved_without_reporting_project_failure(real_persistence, tmp_path, raw, operation):
    state_path = real_persistence / 'editor_state.json'
    state_path.write_bytes(raw)
    session = ProjectSession(ROOT / 'metadata')
    if operation == 'open':
        existing = Project.create(tmp_path, 'existing', '现有工程')
        project = session.open_project(existing.root)
    else:
        project = session.create_project(tmp_path, 'created', '新工程')
    assert state_path.read_bytes() == raw
    assert session.project is project
    assert (project.root / 'mod.json').is_file()
    assert session.persistence_warning
    assert session.last_project_path() is None
    assert not session.command_stack.can_undo


@pytest.mark.parametrize('failure', ['read', 'replace', 'fsync', 'mkdir'])
def test_recent_project_io_failure_preserves_bytes_and_reports_warning_then_recovers(real_persistence, tmp_path, monkeypatch, failure):
    write_state(real_persistence, {'last_project': '旧工程', 'web_workbench': LAYOUT, 'future': 7})
    state_path = real_persistence / 'editor_state.json'
    original_bytes = state_path.read_bytes()
    project = Project.create(tmp_path, 'existing', '现有工程')
    session = ProjectSession(ROOT / 'metadata')

    def denied(*args, **kwargs):
        raise PermissionError('injected filesystem failure')

    with monkeypatch.context() as boundary:
        if failure == 'read':
            original_read = Path.read_text
            def read(path, *args, **kwargs):
                return denied() if path == state_path else original_read(path, *args, **kwargs)
            boundary.setattr(Path, 'read_text', read)
        elif failure == 'mkdir':
            original_mkdir = Path.mkdir
            def mkdir(path, *args, **kwargs):
                return denied() if path == real_persistence else original_mkdir(path, *args, **kwargs)
            boundary.setattr(Path, 'mkdir', mkdir)
        else:
            boundary.setattr(os, failure, denied)
        assert session.open_project(project.root).root == project.root
        assert state_path.read_bytes() == original_bytes
        assert session.persistence_warning
    assert not list(real_persistence.glob('.*.tmp'))
    assert session.open_project(project.root).root == project.root
    assert session.persistence_warning is None
    assert session.last_project_path() == str(project.root)
    assert PreferencesService(DEFAULTS, real_persistence).state()['layout'] == LAYOUT


def test_adopted_new_project_and_redo_remember_without_extra_history_or_undo_erasure(real_persistence, tmp_path):
    write_state(real_persistence, {'last_project': '旧工程', 'web_workbench': LAYOUT, 'future': 9})
    session = ProjectSession(ROOT / 'metadata')

    def adopted(project, undo):
        session.attach_project(None if undo else project)

    project = create_project(tmp_path, 'new-mod', '新工程', session.command_stack, on_change=adopted)
    assert session.last_project_path() == '旧工程'
    assert session.remember_project() is None
    assert session.last_project_path() == str(project.root)
    session.undo()
    assert session.project is None
    original_bytes = (real_persistence / 'editor_state.json').read_bytes()
    assert session.remember_project() is None
    assert (real_persistence / 'editor_state.json').read_bytes() == original_bytes
    assert not session.command_stack.can_undo
    assert session.command_stack.can_redo
    session.redo()
    assert session.project is project
    assert session.remember_project() is None
    assert session.last_project_path() == str(project.root)
    assert PreferencesService(DEFAULTS, real_persistence).state()['layout'] == LAYOUT
    session.undo()
    assert not session.command_stack.can_undo


def test_failed_recent_write_does_not_undo_adopted_project_and_success_clears_warning(real_persistence, tmp_path, monkeypatch):
    write_state(real_persistence, {'last_project': '旧工程', 'web_workbench': LAYOUT})
    session = ProjectSession(ROOT / 'metadata')
    project = Project.create(tmp_path, 'adopted', '已采用工程')
    session.attach_project(project)
    original_bytes = (real_persistence / 'editor_state.json').read_bytes()
    def denied(*args, **kwargs):
        raise PermissionError('injected replace failure')
    with monkeypatch.context() as boundary:
        boundary.setattr(os, 'replace', denied)
        assert session.remember_project() == session.persistence_warning
        assert session.persistence_warning
    assert session.project is project
    assert (project.root / 'mod.json').exists()
    assert (real_persistence / 'editor_state.json').read_bytes() == original_bytes
    assert session.remember_project() is None
    assert session.persistence_warning is None
    assert session.project is project
    assert session.last_project_path() == str(project.root)


def test_layout_and_recent_project_updates_preserve_each_other_in_both_orders(real_persistence, tmp_path):
    write_state(real_persistence, {'last_project': '旧工程', 'future': {'retain': True}})
    service = PreferencesService(DEFAULTS, real_persistence)
    first = service.update_layout(LAYOUT, 0)
    session = ProjectSession(ROOT / 'metadata')
    project = session.create_project(tmp_path, 'next-mod', '新工程')
    next_layout = {**LAYOUT, 'previewVisible': False}
    service.update_layout(next_layout, first['revision'])
    assert session.remember_project() is None
    assert config_loader.load_editor_state() == {'last_project': str(project.root),
        'future': {'retain': True}, 'web_workbench': next_layout}
    assert PreferencesService(DEFAULTS, real_persistence).state()['layout'] == next_layout


@pytest.mark.parametrize('method,filename', [('update_settings', 'settings.json'),
                                           ('update_layout', 'editor_state.json')])
def test_preferences_detects_read_failure_after_startup_without_publishing_or_overwriting(real_persistence, monkeypatch, method, filename):
    path = real_persistence / filename
    initial = {'theme': 'light', 'future': [3]} if filename == 'settings.json' else {
        'last_project': '旧工程', 'web_workbench': LAYOUT, 'future': [3]}
    path.write_text(json.dumps(initial), encoding='utf-8')
    service = PreferencesService(DEFAULTS, real_persistence)
    before = service.state()
    original_bytes = path.read_bytes()
    original_read = Path.read_text

    def read(target, *args, **kwargs):
        if target == path:
            raise PermissionError('injected read failure')
        return original_read(target, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', read)
    value = {'theme': 'dark'} if method == 'update_settings' else {**LAYOUT, 'previewVisible': False}
    with pytest.raises(PreferencesError) as error:
        getattr(service, method)(value, before['revision'])
    assert error.value.code == 'PREFERENCES_READ_ONLY'
    after = service.state()
    assert after['warnings']
    assert all(after[key] == before[key] for key in ('values', 'defaults', 'layout', 'revision'))
    assert path.read_bytes() == original_bytes
    assert not list(real_persistence.glob('.*.tmp'))

