"""Display-name preferences reach specialized descriptors without editing data."""

import json

import pytest

from app.core.config_loader import get_field_names_zh
from app.desktop.workspace import WorkspaceService
from test_desktop_content_bridge import Client, make_project


def fields(plan):
    return {field['name']: field for group in plan['groups'] for field in group['fields']}


def expected_label(mode, name, *, research=False):
    names = get_field_names_zh()
    chinese = names.get(f'research.{name}', names.get(name)) if research else names.get(name)
    if not chinese or mode == 'en':
        return name
    if mode == 'zh':
        return chinese
    return f'{chinese} ({name})' if mode == 'zh_en' else f'{name} ({chinese})'


@pytest.mark.parametrize('mode', ['zh_en', 'en_zh', 'zh', 'en'])
def test_specialized_field_labels_follow_mode_without_changing_documents(tmp_path, mode):
    project = make_project(tmp_path / 'project')
    samples = {
        'content/blocks/crafter.json': {'type': 'GenericCrafter', 'consumes': {
            'power': 2, 'items': [{'item': 'copper', 'amount': 3}]},
            'research': {'parent': 'copper-wall', 'requirements': [{'item': 'copper', 'amount': 5}],
                         'objectives': [{'type': 'Research', 'content': 'copper-wall'}]}},
        'content/units/unit.json': {'type': 'mech', 'weapons': [{'name': 'missing-reference'}]},
    }
    for path, data in samples.items():
        target = project / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data), encoding='utf-8')
    client = Client(WorkspaceService('metadata'))
    client.call('open_project', {'path': str(project)})
    for path in samples:
        client.call('read_document', {'path': path})
    before = client.state()
    result = client.call('update_settings', {'patch': {'display_name_mode': mode},
                                           'expectedPreferencesRevision': 0})['state']
    documents = {document['path']: document for document in result['documents']}
    block = fields(documents['content/blocks/crafter.json']['form'])
    consumes = block['consumes']
    checked = []
    for descriptor in consumes['children'] + consumes['addable']:
        checked.append((descriptor, False))
        for row in descriptor.get('rows', []):
            checked.extend((field, False) for field in row['fields'])
    research = block['research']
    checked.extend((field, True) for field in research['fields'])
    for name in ('requirements', 'objectives'):
        collection = research[name]
        checked.append((collection, True))
        for row in collection['rows']:
            checked.extend((field, True) for field in row['fields'])
    weapon = fields(documents['content/units/unit.json']['form'])['weapons']['items'][0]
    overrides = [field for group in weapon['overrideGroups'] for field in group['fields']]
    assert any(field['name'] == 'reload' for field in overrides)
    checked.extend((field, False) for field in overrides)
    for descriptor, is_research in checked:
        assert descriptor['label'] == expected_label(mode, descriptor['name'], research=is_research), descriptor['name']
    assert (result['sessionId'], result['revision'], result['history']) == (
        before['sessionId'], before['revision'], before['history'])
    for document in result['documents']:
        previous = next(item for item in before['documents'] if item['path'] == document['path'])
        assert document['data'] == previous['data']
        assert document['dirty'] == previous['dirty']
        assert json.loads((project / document['path']).read_text('utf-8')) == samples[document['path']]
