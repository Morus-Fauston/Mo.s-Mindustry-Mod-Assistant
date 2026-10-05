"""Content-file commands preserve the actual editing identity and disk baseline."""
from copy import deepcopy
import json
from pathlib import Path
import gc
from types import SimpleNamespace

import pytest

from app.core.project import Project
from app.core.session import ProjectSession
from app.desktop.content_actions import ContentActions
from app.desktop.editing import EditingService, EditingError
from app.desktop.source_editing import RawDocument, SourceEditingService

OLD = 'content/weapons/gun.json'
NEW = 'content/weapons/renamed.json'


@pytest.fixture
def client(tmp_path):
    from app.desktop.content_identity import ContentIdentityAdapter
    project = Project.create(tmp_path, 'identity', '身份')
    session = ProjectSession('metadata')
    session.open_project(project.root)
    actions = ContentActions(session.project, session.command_stack)
    editing = EditingService(session, 'session-a', on_saved=actions.saved)
    adapter = ContentIdentityAdapter(editing)
    actions.on_change = adapter.handler

    def open_document(path=OLD, data=None, raw=None):
        target = project.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw if raw is not None else json.dumps(data or {
            'type': 'Weapon', 'name': 'gun', 'reload': 10,
            'bullet': {'type': 'BasicBulletType', 'damage': 12}}).encode())
        if raw is None:
            entry = session.read_content(path[8:])
        else:
            text = raw.decode()
            try:
                SourceEditingService._decode(text)
            except ValueError as error:
                entry = RawDocument(target.stem, path.split('/')[1], target, text,
                                    SourceEditingService.error_details(error))
        editing.opened(path, entry)
        return entry

    def edit(method, **payload):
        return getattr(editing, method)({'expectedRevision': editing.revision, **payload})

    return SimpleNamespace(project=project, session=session, actions=actions, editing=editing,
                           adapter=adapter, open=open_document, edit=edit, stack=session.command_stack)


def test_rename_source_nested_save_and_history_keep_object_dict_and_baseline(client):
    c = client
    entry = c.open()
    identity = entry.data
    source = {**entry.data, 'reload': 20}
    c.edit('set_source', path=OLD, text=json.dumps(source))
    c.editing.form_action('set_field', entry_payload(c, OLD, objectPath=['bullet'], field='damage', value=24))
    c.edit('save')
    old_bytes = (c.project.root / OLD).read_bytes()
    old_form = c.editing.nested.snapshot(OLD)
    c.adapter.prepare([OLD, NEW], None)
    c.actions.rename(OLD, 'renamed')
    assert c.editing.entry(NEW) is entry and entry.data is identity
    assert c.session.loaded_content(OLD[8:]) is None
    assert c.session.loaded_content(NEW[8:]) is entry
    assert entry.name == 'renamed' and entry.path == c.project.root / NEW
    assert c.editing.nested.snapshot(NEW) == old_form
    c.edit('set_field', path=NEW, field='reload', value=30)
    c.edit('save')
    c.stack.undo()
    assert entry.data['reload'] == 20
    c.stack.undo()
    assert c.editing.entry(OLD) is entry and entry.data is identity
    assert (c.project.root / OLD).read_bytes() == old_bytes
    assert not c.editing.document(OLD)['dirty']
    c.stack.undo()
    assert entry.data['bullet']['damage'] == 12
    c.stack.undo()
    assert entry.data['reload'] == 10
    for _ in range(4):
        c.stack.redo()
    assert c.editing.entry(NEW) is entry and entry.data is identity
    assert entry.data['reload'] == 30 and entry.data['bullet']['damage'] == 24
    assert c.adapter.last_change == {'action': 'rename', 'beforePath': OLD, 'afterPath': NEW, 'undo': False}


def entry_payload(c, path, **payload):
    return {'path': path, 'expectedRevision': c.editing.revision, **payload}


def test_raw_repair_rename_then_undo_redo_restores_real_raw_and_valid_identities(client):
    c = client
    raw = c.open(raw=b'{"broken":')
    c.edit('set_source', path=OLD, text='{"type":"Weapon","reload":12}')
    repaired = c.editing.entry(OLD)
    data = repaired.data
    c.edit('save')
    c.adapter.prepare([OLD, NEW])
    c.actions.rename(OLD, 'renamed')
    c.stack.undo()
    c.stack.undo()
    restored = c.editing.entry(OLD)
    assert isinstance(restored, RawDocument) and restored.source_text == raw.source_text
    assert restored.path == c.project.root / OLD
    assert c.session.loaded_content(OLD[8:]) is None
    c.stack.redo()
    assert c.editing.entry(OLD) is repaired and repaired.data is data
    c.stack.redo()
    assert c.editing.entry(NEW) is repaired and repaired.data is data
    assert c.session.loaded_content(NEW[8:]) is repaired
    assert repaired.path == c.project.root / NEW


@pytest.mark.parametrize('action', ['delete', 'overwrite'])
def test_bad_json_delete_or_overwrite_undo_restores_exact_raw_file_and_open_state(client, action):
    c = client
    original = b'{"broken":\r\n'
    raw = c.open(raw=original)
    c.adapter.prepare([OLD])
    if action == 'delete':
        c.actions.delete(OLD)
        assert c.editing.entry(OLD) is None
        assert c.editing.state()['documents'] == []
    else:
        c.actions.create('Weapon', 'gun', 'weapons', overwrite=True)
        assert c.editing.document(OLD)['validData']
    c.stack.undo()
    assert c.editing.entry(OLD) is raw
    assert (c.project.root / OLD).read_bytes() == original
    assert c.editing.state()['documents'][0]['validData'] is False
    assert c.editing.document(OLD)['dirty'] is False
    c.stack.redo()
    if action == 'delete':
        assert not (c.project.root / OLD).exists()
        c.edit('save')
        assert not (c.project.root / OLD).exists()
    else:
        assert c.editing.document(OLD)['validData']


@pytest.mark.parametrize('direction', ['forward', 'undo', 'redo'])
def test_identity_failure_restores_disk_tabs_data_history_and_allows_retry(client, monkeypatch, direction):
    c = client
    entry = c.open()
    root_dict = entry.data
    c.edit('set_source', path=OLD, text=json.dumps({**entry.data, 'reload': 18}))
    c.edit('save')
    c.adapter.prepare([OLD, NEW])
    if direction != 'forward':
        c.actions.rename(OLD, 'renamed')
        if direction == 'redo':
            c.stack.undo()
    c.adapter.consume_change()
    before = deepcopy(c.editing.state())
    sidecar_keys = set(c.editing.nested._states), set(c.editing.forms._memories)
    disk = {path: (c.project.root / path).read_bytes() if (c.project.root / path).exists() else None for path in (OLD, NEW)}
    real_restore = c.editing.nested.restore
    calls = []

    def fail_once(path, state):
        real_restore(path, state)
        calls.append(path)
        if len(calls) == 1:
            raise OSError('模拟身份发布失败')

    monkeypatch.setattr(c.editing.nested, 'restore', fail_once)
    operation = (lambda: c.actions.rename(OLD, 'renamed')) if direction == 'forward' else getattr(c.stack, direction)
    with pytest.raises(OSError, match='身份发布'):
        operation()
    assert c.editing.state() == before
    assert (set(c.editing.nested._states), set(c.editing.forms._memories)) == sidecar_keys
    assert entry.data is root_dict
    assert c.adapter.consume_change() is None
    for path, raw in disk.items():
        target = c.project.root / path
        assert (target.read_bytes() if target.exists() else None) == raw
    if direction == 'forward':
        c.adapter.prepare([OLD, NEW])
    operation()
    assert c.adapter.consume_change() is not None
    assert c.adapter.consume_change() is None


def test_prepare_affected_dirty_only_keeps_tabs_and_requires_explicit_decision(client):
    c = client
    first = c.open()
    other_path = 'content/weapons/other.json'
    other = c.open(other_path)
    c.edit('set_field', path=OLD, field='reload', value=25)
    c.edit('set_field', path=other_path, field='reload', value=30)
    before = c.editing.state()
    with pytest.raises(EditingError) as error:
        c.adapter.prepare([OLD, NEW])
    assert error.value.code == 'UNSAVED_CHANGES'
    assert c.editing.state() == before
    c.adapter.prepare([OLD, NEW], 'save')
    assert not c.editing.document(OLD)['dirty']
    assert c.editing.document(other_path)['dirty']
    assert len(c.editing.state()['documents']) == 2
    c.actions.rename(OLD, 'renamed')
    assert c.editing.entry(NEW) is first and c.editing.entry(other_path) is other
    assert c.editing.document(other_path)['dirty']
    c.adapter.prepare([other_path], 'discard')
    assert c.editing.entry(other_path) is other and other.data['reload'] == 10
    assert len(c.editing.state()['documents']) == 2
    c.stack.undo()
    assert other.data['reload'] == 30


def test_unopened_file_rename_undo_can_be_opened_with_original_identity(client):
    c = client
    entry = c.open()
    c.editing.close(entry_payload(c, OLD, paths=[OLD], decision='discard'))
    c.adapter.prepare([OLD, NEW])
    c.actions.rename(OLD, 'renamed')
    assert c.editing.entry(NEW) is entry
    c.stack.undo()
    assert c.editing.entry(OLD) is entry
    c.editing.opened(OLD, c.session.loaded_content(OLD[8:]))
    c.edit('set_field', path=OLD, field='reload', value=99)
    c.edit('save')
    assert json.loads((c.project.root / OLD).read_text())['reload'] == 99


def test_new_create_edit_save_undo_and_redo_keep_created_identity(client):
    c = client
    c.adapter.prepare([OLD])
    c.actions.create('Weapon', 'gun', 'weapons')
    entry = c.editing.entry(OLD)
    identity = entry.data
    c.edit('set_field', path=OLD, field='reload', value=35)
    c.edit('save')
    c.stack.undo()
    c.stack.undo()
    assert c.editing.entry(OLD) is None and not (c.project.root / OLD).exists()
    c.stack.redo()
    c.stack.redo()
    assert c.editing.entry(OLD) is entry and entry.data is identity
    assert entry.data['reload'] == 35
    assert c.editing.document(OLD)['dirty']


def test_rename_does_not_leave_old_sidecar_after_redo_and_release_frees_command_snapshots(client):
    c = client
    c.open()
    c.adapter.prepare([OLD, NEW])
    c.actions.rename(OLD, 'renamed')
    assert OLD not in c.editing.nested._states and OLD not in c.editing.forms._memories
    c.stack.undo()
    assert NEW not in c.editing.nested._states and NEW not in c.editing.forms._memories
    c.stack.redo()
    assert OLD not in c.editing.nested._states and OLD not in c.editing.forms._memories
    c.stack.clear()
    gc.collect()
    assert not c.adapter._records


def test_attach_detach_project_retains_own_stack_and_rejects_wrong_registered_rekey(client):
    c = client
    entry = c.open()
    c.edit('set_field', path=OLD, field='reload', value=15)
    stack = c.session.command_stack
    c.session.rekey_content(OLD[8:], NEW[8:], entry)
    assert c.session.loaded_content(OLD[8:]) is None
    assert c.session.loaded_content(NEW[8:]) is entry
    assert entry.path == c.project.root / NEW
    with pytest.raises(ValueError):
        c.session.rekey_content(OLD[8:], NEW[8:], entry)
    c.session.attach_project(None)
    assert c.session.project is None and c.session.command_stack is stack and stack.can_undo
    c.session.attach_project(c.project)
    assert c.session.project is c.project and c.session.command_stack is stack and stack.can_undo


def test_partial_save_acknowledges_success_only_and_external_writes_still_block_file_undo(client, monkeypatch):
    c = client
    c.adapter.prepare([OLD])
    c.actions.create('Weapon', 'gun', 'weapons')
    other_path = 'content/weapons/other.json'
    c.open(other_path)
    c.edit('set_field', path=OLD, field='reload', value=40)
    c.edit('set_field', path=other_path, field='reload', value=50)
    actual = c.session.save_content
    acknowledged = []
    real_saved = c.actions.saved

    def on_saved(path):
        acknowledged.append(path)
        real_saved(path)

    c.editing._on_saved = on_saved

    def save(content):
        if content.name == 'other':
            raise PermissionError('模拟另一个文件占用')
        return actual(content)

    monkeypatch.setattr(c.session, 'save_content', save)
    with pytest.raises(EditingError):
        c.edit('save')
    assert acknowledged == [OLD]
    assert not c.editing.document(OLD)['dirty'] and c.editing.document(other_path)['dirty']
    c.stack.undo()
    c.stack.undo()
    (c.project.root / OLD).write_bytes(b'{"external":true}')
    with pytest.raises(ValueError, match='其他操作'):
        c.stack.undo()
    assert (c.project.root / OLD).read_bytes() == b'{"external":true}'
    assert c.editing.entry(OLD) is not None


@pytest.mark.parametrize('raw', [False, True])
def test_prepare_rejects_external_document_change_without_replacing_cached_identity(client, raw):
    c = client
    entry = c.open(raw=b'{"broken":' if raw else None)
    external = b'{"type":"Weapon","reload":99}'
    (c.project.root / OLD).write_bytes(external)
    before = c.editing.state()
    with pytest.raises(EditingError) as error:
        c.adapter.prepare([OLD, NEW])
    assert error.value.code == 'CONTENT_CHANGED'
    assert c.editing.entry(OLD) is entry
    assert c.editing.state() == before
    assert (c.project.root / OLD).read_bytes() == external


def test_valid_overwrite_preserves_identity_and_other_category_same_name(client):
    c = client
    entry = c.open()
    data = entry.data
    other_path = 'content/units/gun.json'
    other = c.open(other_path, data={'type': 'UnitType', 'health': 200})
    other_data = other.data
    c.edit('set_field', path=OLD, field='reload', value=65)
    c.edit('save')
    original = (c.project.root / OLD).read_bytes()
    c.adapter.prepare([OLD])
    c.actions.create('Weapon', 'gun', 'weapons', overwrite=True)
    assert c.editing.entry(OLD) is entry and entry.data is data
    c.stack.undo()
    assert c.editing.entry(OLD) is entry and entry.data is data and entry.data['reload'] == 65
    assert (c.project.root / OLD).read_bytes() == original
    c.stack.undo()
    assert entry.data['reload'] == 10
    assert c.editing.entry(other_path) is other and other.data is other_data
    assert other.data == {'type': 'UnitType', 'health': 200}


def test_first_open_happens_only_after_unopened_content_rename_success(client):
    c = client
    path = c.project.root / OLD
    path.write_bytes(b'{"type":"Weapon","reload":17}')
    c.adapter.prepare([OLD, NEW])
    assert c.editing.state()['documents'] == []
    c.actions.rename(OLD, 'renamed')
    entry = c.editing.entry(NEW)
    assert entry.data['reload'] == 17
    assert c.editing.state()['documents'][0]['path'] == NEW
    c.stack.undo()
    assert c.editing.state()['documents'] == []
    c.stack.redo()
    assert c.editing.entry(NEW) is entry
