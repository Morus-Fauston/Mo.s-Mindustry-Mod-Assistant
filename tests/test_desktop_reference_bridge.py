"""Real reference sources through the serialized desktop bridge."""
import json
import gc
import weakref
import zipfile
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.desktop.api import DesktopApi
from app.desktop.workspace import WorkspaceService
from app.desktop import workspace as workspace_module
from test_desktop_content_bridge import Client, make_project


PATH = 'content/units/scout.json'


def reference_folder(root, value=101):
    target = root / 'content/units/scout.json'
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({'health': value, 'referenceOnly': None}), encoding='utf-8')
    return root


def reference_zip(path):
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('包装/mod.json', '{"displayName":"中文参考"}')
        archive.writestr('包装/content/units/scout.json', '{"health":101,"referenceOnly":null}')
        archive.writestr('包装/content/blocks/scout.json', '{"health":505}')
        archive.writestr('包装/scripts/main.js', 'throw new Error("never execute")')
    return path


def opened_client(tmp_path, factory=WorkspaceService, **callbacks):
    root = make_project(tmp_path / 'current')
    path = root / PATH
    path.parent.mkdir(parents=True)
    path.write_text('{"type":"flying","health":137}', encoding='utf-8')
    client = Client(factory('metadata', **callbacks))
    client.call('open_project', {'path': str(root)})
    client.call('read_document', {'path': PATH})
    return client, root


def workspace(client):
    return client.service._workspace if isinstance(client.service, DesktopApi) else client.service


def open_request(client, request_id='reference-once', kind='folder'):
    return {'protocolVersion': 1, 'requestId': request_id, 'sessionId': client.session,
            'action': 'open_reference', 'payload': {'kind': kind, 'expectedRevision': client.state()['revision']}}


@pytest.mark.parametrize('kind', ['folder', 'zip'])
@pytest.mark.parametrize('factory', [WorkspaceService, DesktopApi])
def test_real_reference_compare_uses_unsaved_current_data_without_writes(tmp_path, kind, factory):
    folder = reference_folder(tmp_path / '中文目录')
    archive = reference_zip(tmp_path / '中文参考.zip')
    selections = []
    client, current = opened_client(tmp_path, factory,
        choose_directory=lambda: selections.append('folder') or str(folder),
        choose_reference_zip=lambda: selections.append('zip') or str(archive))
    client.change('set_field', path=PATH, field='health', value=239)
    before = client.state()
    files = {str(path): path.read_bytes() for path in tmp_path.rglob('*') if path.is_file()}
    result = client.change('open_reference', kind=kind)
    assert result['state'] == before and result['source']['kind'] == kind
    source_id = result['source']['sourceId']
    candidates = client.call('reference_candidates_for_compare', {'sourceId': source_id, 'category': 'units', 'query': 'scout', 'offset': 0})
    assert candidates['candidates'][0]['name'] == 'scout'
    comparison = client.change('compare_reference', sourceId=source_id, category='units', name='scout', path=PATH)
    rows = {row['field']: row for row in comparison['rows']}
    assert rows['health']['current']['text'] == '239' and rows['health']['reference']['text'] == '101'
    assert rows['referenceOnly']['current']['kind'] == 'missing'
    assert comparison['sessionId'] == client.session and comparison['currentPath'] == PATH
    assert comparison['revision'] == before['revision'] and client.state() == before
    assert selections == [kind]
    assert {str(path): path.read_bytes() for path in tmp_path.rglob('*') if path.is_file()} == files
    assert json.loads((current / PATH).read_text('utf-8'))['health'] == 137


def test_reference_open_duplicate_and_query_never_repeat_native_selection(tmp_path):
    folder = reference_folder(tmp_path / 'reference')
    selections = []
    client, _ = opened_client(tmp_path, choose_directory=lambda: selections.append(True) or str(folder))
    request = open_request(client)
    result = client.call('open_reference', envelope=request)
    assert client.call('open_reference', envelope=request) == result
    cached = workspace(client).request_result(request['requestId'])
    assert cached['state'] == 'completed' and cached['response']['data'] == result
    assert len(selections) == 1
    assert len(client.call('reference_sources')['sources']) == 2


def test_release_is_idempotent_and_expires_original_open_result(tmp_path):
    folder = reference_folder(tmp_path / 'reference')
    selections = []
    client, _ = opened_client(tmp_path, choose_directory=lambda: selections.append(True) or str(folder))
    request = open_request(client)
    result = client.call('open_reference', envelope=request)
    source_id = result['source']['sourceId']
    for _ in range(2):
        assert client.call('release_reference', {'sourceId': source_id}) == {'released': True}
    expired = workspace(client).request_result(request['requestId'])['response']
    assert not expired['ok'] and expired['error']['code'] == 'RESULT_EXPIRED'
    assert client.call('open_reference', envelope=request, ok=False)['code'] == 'RESULT_EXPIRED'
    assert client.call('reference_candidates_for_compare', {'sourceId': source_id, 'category': 'units'}, ok=False)['code'] == 'REFERENCE_FAILED'
    assert len(client.call('reference_sources')['sources']) == 1 and len(selections) == 1


def test_readonly_reference_queries_are_not_retained_in_mutation_cache(tmp_path):
    folder = reference_folder(tmp_path / 'reference')
    client, _ = opened_client(tmp_path, choose_directory=lambda: str(folder))
    source_id = client.change('open_reference', kind='folder')['source']['sourceId']
    revision = client.state()['revision']
    queries = [
        ('reference_sources', {}),
        ('reference_candidates_for_compare', {'sourceId': source_id, 'category': 'units'}),
        ('compare_reference', {'sourceId': source_id, 'category': 'units', 'name': 'scout', 'path': PATH, 'expectedRevision': revision}),
    ]
    for index, (action, payload) in enumerate(queries):
        request = {'protocolVersion': 1, 'requestId': f'readonly-{index}', 'sessionId': client.session, 'action': action, 'payload': payload}
        client.call(action, envelope=request)
        assert request['requestId'] not in workspace(client)._results


@pytest.mark.parametrize('kind', ['folder', 'zip'])
def test_native_reference_cancel_and_missing_picker_preserve_current_session(tmp_path, kind):
    client, _ = opened_client(tmp_path, choose_directory=lambda: None, choose_reference_zip=lambda: None)
    before = client.state()
    assert client.change('open_reference', kind=kind) == {'state': before, 'source': None}
    assert client.state() == before and len(client.call('reference_sources')['sources']) == 1
    service = workspace(client)
    setattr(service, '_choose_directory' if kind == 'folder' else '_choose_reference_zip', None)
    error = client.call('open_reference', {'kind': kind, 'expectedRevision': before['revision']}, ok=False)
    assert error['code'] == 'DIALOG_UNAVAILABLE' and client.state() == before


def test_invalid_zip_keeps_original_reference_and_does_not_extract(tmp_path):
    folder = reference_folder(tmp_path / 'reference')
    archive = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('../outside.json', '{"health":9}')
        output.writestr('content/units/a.json', '{}')
    client, _ = opened_client(tmp_path, choose_directory=lambda: str(folder), choose_reference_zip=lambda: str(archive))
    original = client.change('open_reference', kind='folder')['source']
    before = client.state()
    error = client.call('open_reference', {'kind': 'zip', 'expectedRevision': before['revision']}, ok=False)
    assert error['code'] == 'REFERENCE_FAILED'
    assert client.state() == before and not (tmp_path / 'outside.json').exists()
    assert client.call('reference_sources')['sources'][1] == original
    archive.rename(tmp_path / 'handle-released.zip')


@pytest.mark.parametrize('action,payload', [
    ('reference_sources', {'path': 'outside'}),
    ('open_reference', {'kind': 'unknown'}),
    ('open_reference', {'kind': 'folder', 'path': 'outside'}),
    ('reference_candidates_for_compare', {'sourceId': 'vanilla', 'category': 'Weapons', 'offset': True}),
    ('reference_candidates_for_compare', {'sourceId': 'vanilla', 'category': 'Weapons', 'query': 'x' * 257}),
    ('compare_reference', {'sourceId': 'vanilla', 'category': 'Weapons', 'name': 'beam-weapon', 'path': PATH, 'currentData': {}}),
    ('release_reference', {'sourceId': 'vanilla', 'path': 'outside'}),
])
def test_bad_reference_payloads_never_mutate_or_open_native_picker(tmp_path, action, payload):
    selections = []
    client, _ = opened_client(tmp_path, choose_directory=lambda: selections.append(True))
    before = client.state()
    if action in ('open_reference', 'compare_reference'):
        payload = {**payload, 'expectedRevision': before['revision']}
    assert client.call(action, payload, ok=False)['code'] == 'INVALID_REQUEST'
    assert client.state() == before and not selections


def test_compare_requires_open_valid_current_content_and_current_revision(tmp_path):
    folder = reference_folder(tmp_path / 'reference')
    client, current = opened_client(tmp_path, choose_directory=lambda: str(folder))
    source_id = client.change('open_reference', kind='folder')['source']['sourceId']
    payload = {'sourceId': source_id, 'category': 'units', 'name': 'scout', 'path': PATH}
    assert client.call('compare_reference', {**payload, 'expectedRevision': -1}, ok=False)['code'] == 'STALE_REVISION'
    unopened = current / 'content/units/not-open.json'
    unopened.write_text('{}', encoding='utf-8')
    before = client.state()
    assert client.call('compare_reference', {**payload, 'path': 'content/units/not-open.json', 'expectedRevision': before['revision']}, ok=False)['code'] == 'DOCUMENT_NOT_OPEN'
    broken = current / 'content/units/broken.json'
    broken.write_text('{invalid', encoding='utf-8')
    client.call('read_document', {'path': 'content/units/broken.json'})
    assert client.call('compare_reference', {**payload, 'path': 'content/units/broken.json', 'expectedRevision': client.state()['revision']}, ok=False)['code'] == 'SOURCE_INVALID'


@pytest.mark.parametrize('transition', ['open', 'create', 'close'])
def test_session_transition_or_close_releases_sources_and_expires_old_results(tmp_path, transition):
    folder = reference_folder(tmp_path / 'reference')
    client, _ = opened_client(tmp_path, choose_directory=lambda: str(folder))
    request = open_request(client)
    source = client.call('open_reference', envelope=request)['source']
    service = workspace(client)
    references, old_session = service._reference_projects, client.session
    if transition == 'open':
        other = make_project(tmp_path / 'other')
        client.call('open_project', {'path': str(other)})
    elif transition == 'create':
        service._choose_directory = lambda: str(tmp_path)
        client.change('create_project', mod_id='new', displayName='新工程', author='')
    else:
        client.change('close_window', decision='discard')
    assert references._closed and not references._external
    assert service.request_result(request['requestId'])['response']['error']['code'] == 'RESULT_EXPIRED'
    if transition != 'close':
        assert client.session != old_session and len(client.call('reference_sources')['sources']) == 1
        old = {'protocolVersion': 1, 'requestId': 'late-release', 'sessionId': old_session,
               'action': 'release_reference', 'payload': {'sourceId': source['sourceId']}}
        assert client.call('release_reference', envelope=old, ok=False)['code'] == 'STALE_SESSION'


def test_without_project_reference_actions_are_explicitly_unavailable():
    client = Client(WorkspaceService('metadata'))
    for action in ('reference_sources', 'open_reference', 'reference_candidates_for_compare', 'compare_reference', 'release_reference'):
        assert client.call(action, ok=False)['code'] == 'NO_PROJECT'


def test_project_history_releases_reference_service_without_retaining_it(tmp_path):
    folder = reference_folder(tmp_path / 'reference')
    client = Client(WorkspaceService('metadata', choose_directory=lambda: str(tmp_path)))
    client.change('create_project', mod_id='new', displayName='新工程', author='')
    service = client.service
    service._choose_directory = lambda: str(folder)
    stack = service._session.command_stack
    for index in range(2):
        request = open_request(client, f'before-undo-{index}')
        client.call('open_reference', envelope=request)
        references = service._reference_projects
        weak = weakref.ref(references)
        client.change('undo')
        assert references._closed and not references._external
        assert service._reference_projects is None
        assert service.request_result(request['requestId'])['response']['error']['code'] == 'RESULT_EXPIRED'
        del references
        gc.collect()
        assert weak() is None, 'Project history must not retain disposed reference content'
        client.change('redo')
        assert service._session.command_stack is stack
        assert len(client.call('reference_sources')['sources']) == 1


@pytest.mark.parametrize('transition', ['open', 'create'])
def test_failed_project_preparation_preserves_live_reference(tmp_path, monkeypatch, transition):
    folder = reference_folder(tmp_path / 'reference')
    client, _ = opened_client(tmp_path, choose_directory=lambda: str(folder))
    request = open_request(client)
    opened = client.call('open_reference', envelope=request)
    service = client.service
    references, before, old_session = service._reference_projects, client.state(), client.session
    def fail_prepare(_root):
        raise OSError('模拟候选初始化失败')
    monkeypatch.setattr(workspace_module, 'ResourceWatch', fail_prepare)
    if transition == 'open':
        other = make_project(tmp_path / 'other')
        client.call('open_project', {'path': str(other)}, ok=False)
    else:
        service._choose_directory = lambda: str(tmp_path)
        client.call('create_project', {'mod_id': 'new', 'displayName': '新工程',
                    'author': '', 'expectedRevision': before['revision']}, ok=False)
        assert not (tmp_path / 'new').exists()
    assert client.session == old_session and client.state() == before
    assert service._reference_projects is references and not references._closed
    assert service.request_result(request['requestId'])['response']['data'] == opened
    assert len(client.call('reference_sources')['sources']) == 2


def test_failed_save_disposes_candidate_references_but_preserves_old_source(tmp_path, monkeypatch):
    folder = reference_folder(tmp_path / 'reference')
    client, _ = opened_client(tmp_path, choose_directory=lambda: str(folder))
    source = client.change('open_reference', kind='folder')['source']
    client.change('set_field', path=PATH, field='health', value=239)
    service, candidates = client.service, []
    references, before = service._reference_projects, client.state()
    constructor = workspace_module.ReferenceProjectsService
    def capture(metadata, session_id):
        candidate = constructor(metadata, session_id)
        candidates.append(candidate)
        return candidate
    def fail_save(_content):
        raise PermissionError('模拟保存占用')
    monkeypatch.setattr(workspace_module, 'ReferenceProjectsService', capture)
    monkeypatch.setattr(service._session, 'save_content', fail_save)
    service._choose_directory = lambda: str(tmp_path)
    client.call('create_project', {'mod_id': 'new', 'displayName': '新工程', 'decision': 'save',
                'author': '', 'expectedRevision': before['revision']}, ok=False)
    assert len(candidates) == 1 and candidates[0]._closed and not candidates[0]._external
    assert service._pending_project_services is None and not (tmp_path / 'new').exists()
    assert service._reference_projects is references and not references._closed
    assert client.state() == before and client.call('reference_sources')['sources'][1] == source


def test_pending_open_queries_and_concurrent_duplicate_share_one_native_selection(tmp_path):
    folder = reference_folder(tmp_path / 'reference')
    entered, finish, selections = Event(), Event(), []
    def select():
        selections.append(True)
        entered.set()
        assert finish.wait(5), 'Test must release its isolated chooser'
        return str(folder)
    client, _ = opened_client(tmp_path, DesktopApi, choose_directory=select)
    request = open_request(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.service.request, request)
        try:
            assert entered.wait(5)
            for _ in range(3):
                assert client.service.request_result(request['requestId']) == {'state': 'pending'}
            second = pool.submit(client.service.request, request)
        finally:
            finish.set()
        original, duplicate = first.result(timeout=5), second.result(timeout=5)
    assert original['ok'] and original == duplicate and selections == [True]
    assert client.service.request_result(request['requestId'])['response'] == original


def test_stale_open_never_selects_and_release_preserves_other_sources_and_cache_accounting(tmp_path):
    folder = reference_folder(tmp_path / 'reference')
    selections = []
    client, _ = opened_client(tmp_path, choose_directory=lambda: selections.append(True) or str(folder))
    assert client.call('open_reference', {'kind': 'folder', 'expectedRevision': -1}, ok=False)['code'] == 'STALE_REVISION'
    assert not selections
    first_request, second_request = open_request(client, 'first'), open_request(client, 'second')
    first = client.call('open_reference', envelope=first_request)
    second = client.call('open_reference', envelope=second_request)
    client.call('release_reference', {'sourceId': first['source']['sourceId']})
    assert client.call('reference_sources')['sources'][1:] == [second['source']]
    service = client.service
    assert service.request_result('first')['response']['error']['code'] == 'RESULT_EXPIRED'
    assert service.request_result('second')['response']['data'] == second
    assert service._result_bytes == sum(service._result_sizes.values())
    assert service._result_bytes == sum(len(json.dumps(response, ensure_ascii=True, allow_nan=False).encode('utf-8'))
                                        for _, response in service._results.values())
