"""Validation/export use the same session, revision and deduplication lane."""
import json
from itertools import count
from zipfile import ZipFile

from app.desktop.workspace import WorkspaceService


def test_export_bridge_saves_current_document_and_deduplicates_picker(tmp_path):
    root = tmp_path / 'project'
    (root / 'content/units').mkdir(parents=True)
    (root / 'mod.json').write_text('{"name":"test"}', encoding='utf-8')
    path = 'content/units/unit.json'
    (root / path).write_text('{"type":"flying","health":10}', encoding='utf-8')
    selected = []
    output = tmp_path / 'mod.zip'
    def choose(name):
        selected.append(name)
        return str(output)
    workspace = WorkspaceService('metadata', choose_export=choose)
    ids, session = count(), None
    def request(action, **payload):
        return {'protocolVersion': 1, 'requestId': str(next(ids)), 'sessionId': session,
                'action': action, 'payload': payload}
    def call(action, **payload):
        result = workspace.request(request(action, **payload))
        assert result['ok'], result
        return result['data']
    session = call('open_project', path=str(root))['sessionId']
    try:
        call('read_document', path=path)
        before = call('editing_state')
        state = call('set_field', path=path, field='health', text='123', expectedRevision=before['revision'])
        validated = call('validate_project', expectedRevision=state['revision'])
        assert validated['state'] == state
        assert validated['report']['complete']
        assert json.loads((root / path).read_text())['health'] == 10
        envelope = request('export_project', expectedRevision=state['revision'])
        first = workspace.request(envelope)
        assert first['ok'], first
        assert workspace.request(envelope) == first
        assert len(selected) == 1
        assert first['data']['exported']
        assert not first['data']['state']['documents'][0]['dirty']
        with ZipFile(output) as archive:
            assert json.loads(archive.read(path))['health'] == 123
        assert workspace.request_result(envelope['requestId'])['response'] == first
        old = request('validate_project', expectedRevision=state['revision'])
        session = call('open_project', path=str(root))['sessionId']
        assert workspace.request(old)['error']['code'] == 'STALE_SESSION'
    finally:
        call('close_window', expectedRevision=call('editing_state')['revision'], decision='discard')
