"""Generation through the real serialized workspace, PNG files and command stack."""
import base64
import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from itertools import count
from threading import Event
from types import SimpleNamespace

from PIL import Image
import pytest

from app.core.commands import CommandStack
from app.core.project import Project
from app.desktop.sprite_generation import SpriteGenerationService
from app.desktop.workspace import WorkspaceService


PATH = 'content/units/unit.json'
OUTPUTS = [{'suffix': '-outline'}, {'suffix': '-shadow'}]


@pytest.fixture
def client(tmp_path):
    project = Project.create(tmp_path / '工程', 'generation', '生成桥接')
    project.contents.save('unit', {'type': 'UnitType'}, 'units')
    source = project.sprite_path('units', 'unit')
    with Image.new('RGBA', (7, 7), (0, 0, 0, 0)) as image:
        image.putpixel((3, 3), (200, 50, 30, 255))
        image.save(source)
    service = WorkspaceService('metadata')
    ids, session = count(), [None]

    def envelope(action, **payload):
        return {'protocolVersion': 1, 'requestId': f'g-{next(ids)}',
                'sessionId': session[0], 'action': action, 'payload': payload}

    def call(action, **payload):
        result = service.request(envelope(action, **payload))
        if result['ok'] and action == 'open_project':
            session[0] = result['sessionId']
        return result

    def state():
        result = call('editing_state')
        assert result['ok'], result
        return result['data']

    def mutate(action, **payload):
        return call(action, expectedRevision=state()['revision'], **payload)

    assert call('open_project', path=str(project.root))['ok']
    assert call('read_document', path=PATH)['ok']
    yield SimpleNamespace(project=project, source=source, service=service, call=call,
                          envelope=envelope, state=state, mutate=mutate, session=session)
    # Actual window-close path releases the resource observer and candidates.
    mutate('close_window', decision='discard')


def candidate(client, outputs=None):
    result = client.mutate('preview_generation', path=PATH, outputs=outputs or OUTPUTS)
    assert result['ok'], result
    assert result['data']['state'] == client.state()
    return result['data']['candidate']


def test_preview_real_pixels_is_read_only_and_cancel_ignores_revision(client):
    before = client.state()
    original = (client.project.root / PATH).read_bytes()
    preview = candidate(client)
    assert preview['sessionId'] == client.session[0]
    for output in preview['outputs']:
        assert not (client.project.root / output['path']).exists()
        with Image.open(BytesIO(base64.b64decode(output['dataUrl'].split(',', 1)[1]))) as image:
            assert image.format == 'PNG' and image.size == (7, 7)
            if output['suffix'] == '-outline':
                assert image.getpixel((3, 3)) == (200, 50, 30, 255)
                assert image.getpixel((2, 3)) == (0, 0, 0, 255)
    assert client.state() == before
    assert (client.project.root / PATH).read_bytes() == original
    cancelled = client.call('cancel_generation', candidateId=preview['candidateId'], expectedRevision=-1)
    assert cancelled['ok'], cancelled
    assert cancelled['data'] == {'state': before, 'cancelled': True}
    assert not client.mutate('confirm_generation', candidateId=preview['candidateId'], overwrite=False)['ok']


def test_confirm_batch_uses_one_command_and_duplicate_request_never_rewrites(client, monkeypatch):
    executed = []
    actual = CommandStack.execute

    def execute(stack, command):
        executed.append(command)
        return actual(stack, command)

    monkeypatch.setattr(CommandStack, 'execute', execute)
    before = client.state()
    preview = candidate(client)
    envelope = client.envelope('confirm_generation', candidateId=preview['candidateId'],
                               overwrite=False, expectedRevision=before['revision'])
    result = client.service.request(envelope)
    assert result['ok'], result
    assert len(executed) == 1
    assert result['data']['state']['revision'] > before['revision']
    assert not result['data']['state']['documents'][0]['dirty']
    paths = [client.project.root / output['path'] for output in preview['outputs']]
    saved = [path.read_bytes() for path in paths]
    assert all(row['exists'] and 'dataUrl' not in row for row in result['data']['outputs'])
    # A lost response may be retried after the user changes a generated file.
    paths[0].write_bytes(b'external edit after successful confirmation')
    assert client.service.request(envelope) == result
    assert paths[0].read_bytes() == b'external edit after successful confirmation'
    assert len(executed) == 1
    paths[0].write_bytes(saved[0])
    assert not client.mutate('confirm_generation', candidateId=preview['candidateId'], overwrite=True)['ok']
    assert len(executed) == 1
    assert client.mutate('undo')['ok']
    assert not any(path.exists() for path in paths)
    assert not client.state()['history']['canUndo']
    assert client.mutate('redo')['ok']
    assert [path.read_bytes() for path in paths] == saved


def test_preview_and_cancel_retries_use_original_result_cache(client, monkeypatch):
    monkeypatch.setattr(SpriteGenerationService, 'MAX_CANDIDATES', 1)
    envelope = client.envelope('preview_generation', path=PATH, outputs=OUTPUTS,
                               expectedRevision=client.state()['revision'])
    first = client.service.request(envelope)
    assert first['ok'], first
    assert client.service.request(envelope) == first
    assert not client.mutate('preview_generation', path=PATH, outputs=OUTPUTS)['ok']
    cancel = client.envelope('cancel_generation', candidateId=first['data']['candidate']['candidateId'])
    result = client.service.request(cancel)
    assert result['ok'], result
    assert client.service.request(cancel) == result
    assert candidate(client)['candidateId'] != first['data']['candidate']['candidateId']


@pytest.mark.parametrize('end', ['cancel', 'confirm', 'switch', 'close'])
def test_released_preview_cache_keeps_tombstone_without_png_or_recreating_candidate(client, tmp_path, monkeypatch, end):
    generated = []
    actual = SpriteGenerationService.preview

    def preview(service, path, outputs):
        generated.append(path)
        return actual(service, path, outputs)

    monkeypatch.setattr(SpriteGenerationService, 'preview', preview)
    envelope = client.envelope('preview_generation', path=PATH, outputs=OUTPUTS,
                               expectedRevision=client.state()['revision'])
    result = client.service.request(envelope)
    assert result['ok'], result
    candidate_id = result['data']['candidate']['candidateId']
    owner = client.service._generation
    assert candidate_id in owner._candidates
    assert 'data:image/png;base64,' in json.dumps(client.service._results)
    retained_size = client.service._result_sizes[envelope['requestId']]
    if end == 'cancel':
        ended = client.call('cancel_generation', candidateId=candidate_id)
    elif end == 'confirm':
        ended = client.mutate('confirm_generation', candidateId=candidate_id, overwrite=False)
    elif end == 'switch':
        other = Project.create(tmp_path / '缓存切换工程', 'other', '缓存切换')
        ended = client.call('open_project', path=str(other.root))
    else:
        ended = client.mutate('close_window', decision='discard')
    assert ended['ok'], ended
    assert not owner._candidates
    assert 'data:image/png;base64,' not in json.dumps(client.service._results)
    assert client.service._result_sizes[envelope['requestId']] < retained_size
    assert client.service._result_bytes == sum(client.service._result_sizes.values())
    cached = client.service.request_result(envelope['requestId'])
    assert cached['state'] == 'completed'
    assert cached['response']['error']['code'] == 'RESULT_EXPIRED'
    assert 'data' not in cached['response']
    replay = client.service.request(envelope)
    assert not replay['ok']
    assert replay['error']['code'] == ('STALE_SESSION' if end == 'switch' else 'RESULT_EXPIRED')
    assert generated == [PATH]
    assert not owner._candidates


@pytest.mark.parametrize('change', ['source', 'target', 'content'])
def test_candidate_rejects_changed_dependencies_without_generated_writes(client, change):
    preview = candidate(client)
    target = client.project.sprite_path('units', 'unit', '-outline')
    if change == 'source':
        with Image.new('RGBA', (7, 7), 'blue') as image:
            image.save(client.source)
    elif change == 'target':
        target.write_bytes(b'external destination')
    else:
        result = client.mutate('set_source', path=PATH, text='{"type":"UnitType","health":25}')
        assert result['ok'], result
    before = client.state()
    result = client.mutate('confirm_generation', candidateId=preview['candidateId'], overwrite=True)
    assert not result['ok']
    assert client.state() == before
    assert not client.project.sprite_path('units', 'unit', '-shadow').exists()
    if change == 'target':
        assert target.read_bytes() == b'external destination'
    else:
        assert not target.exists()


def test_generation_revision_and_overwrite_confirmation_are_authoritative(client):
    target = client.project.sprite_path('units', 'unit', '-outline')
    target.write_bytes(b'old exact bytes')
    before = client.state()
    assert not client.call('preview_generation', path=PATH, outputs=OUTPUTS, expectedRevision=-1)['ok']
    preview = candidate(client)
    assert not client.call('confirm_generation', candidateId=preview['candidateId'],
                           overwrite=True, expectedRevision=-1)['ok']
    assert not client.mutate('confirm_generation', candidateId=preview['candidateId'], overwrite=False)['ok']
    assert not client.mutate('confirm_generation', candidateId=preview['candidateId'], overwrite='true')['ok']
    assert target.read_bytes() == b'old exact bytes'
    assert client.state() == before
    assert client.mutate('confirm_generation', candidateId=preview['candidateId'], overwrite=True)['ok']
    assert target.read_bytes() != b'old exact bytes'
    assert client.mutate('undo')['ok']
    assert target.read_bytes() == b'old exact bytes'


@pytest.mark.parametrize('payload', [
    {'path': '../outside.json', 'outputs': OUTPUTS},
    {'path': PATH, 'outputs': []},
    {'path': PATH, 'outputs': [{'suffix': '-outline', 'options': {'expandPx': True}}]},
    {'path': PATH, 'outputs': OUTPUTS, 'sourcePath': 'C:/outside.png'},
])
def test_generation_rejects_bad_payload_without_mutation(client, payload):
    before = client.state()
    result = client.mutate('preview_generation', **payload)
    assert not result['ok']
    assert client.state() == before
    assert not client.project.sprite_path('units', 'unit', '-outline').exists()


@pytest.mark.parametrize('end', ['switch', 'close'])
def test_session_end_clears_candidates_and_rejects_old_requests(client, tmp_path, monkeypatch, end):
    closed = []
    actual = SpriteGenerationService.close

    def close(service):
        held = len(service._candidates)
        actual(service)
        closed.append((held, len(service._candidates), service._closed))

    monkeypatch.setattr(SpriteGenerationService, 'close', close)
    preview = candidate(client)
    requests = [client.envelope(action, **payload) for action, payload in [
        ('preview_generation', {'path': PATH, 'outputs': OUTPUTS, 'expectedRevision': client.state()['revision']}),
        ('confirm_generation', {'candidateId': preview['candidateId'], 'overwrite': False,
                                'expectedRevision': client.state()['revision']}),
        ('cancel_generation', {'candidateId': preview['candidateId']}),
    ]]
    if end == 'switch':
        other = Project.create(tmp_path / '另一个工程', 'other', '另一个工程')
        assert client.call('open_project', path=str(other.root))['ok']
    else:
        assert client.mutate('close_window', decision='discard')['ok']
    assert closed == [(1, 0, True)]
    for request in requests:
        result = client.service.request(request)
        assert not result['ok'], result
        assert result['error']['code'] == ('STALE_SESSION' if end == 'switch' else 'WINDOW_CLOSING')
    assert not client.project.sprite_path('units', 'unit', '-outline').exists()


def test_generation_is_serialized_and_request_status_reports_pending(client, monkeypatch):
    entered, release, follower_started, follower_finished = Event(), Event(), Event(), Event()
    actual = SpriteGenerationService.preview

    def paused_preview(service, path, outputs):
        entered.set()
        assert release.wait(5), 'test release timed out'
        return actual(service, path, outputs)

    monkeypatch.setattr(SpriteGenerationService, 'preview', paused_preview)
    request = client.envelope('preview_generation', path=PATH, outputs=OUTPUTS,
                              expectedRevision=client.state()['revision'])

    def following_request():
        follower_started.set()
        result = client.call('editing_state')
        follower_finished.set()
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.service.request, request)
        try:
            assert entered.wait(2), first.result(timeout=2)
            second = pool.submit(following_request)
            assert follower_started.wait(2)
            assert not follower_finished.wait(0.05)
            assert client.service.request_result(request['requestId']) == {'state': 'pending'}
        finally:
            release.set()
        result = first.result(timeout=5)
        assert result['ok'], result
        assert second.result(timeout=5)['ok']
    assert client.service.request_result(request['requestId']) == {'state': 'completed', 'response': result}
