"""Readonly reference snapshots remain separate from live project documents."""

import json
import os
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest

from app.core.metadata import Metadata
from app.desktop.reference_projects import ReferenceProjectsService


def folder(root, data=None):
    path = root / 'content' / 'units' / '同名.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data if data is not None else {'health': 100}), encoding='utf-8')
    return root


def service():
    return ReferenceProjectsService(Metadata('metadata'), 'session-one')


def test_folder_snapshot_compares_actual_unsaved_values_without_mutation(tmp_path):
    root = folder(tmp_path / '参考模组', {'health': 100, 'nullable': None, 'dash': '-', 'enabled': 1,
                                      'nested': {'enabled': 1}, 'array': [1, 2], 'number': 1})
    source_file = root / 'content/units/同名.json'
    before = source_file.read_bytes()
    refs = service()
    source = refs.open_folder(root)
    assert source['kind'] == 'folder' and source['label'] == '参考模组'
    candidates = refs.candidates(source['sourceId'], 'units')
    assert candidates['candidates'] == [{'sourceId': source['sourceId'], 'category': 'units',
                                         'name': '同名', 'label': '同名'}]
    current = {'health': 200, 'enabled': True, 'nested': {'enabled': True}, 'array': [2, 1],
               'number': 1.0, 'empty': ''}
    result = refs.compare(source['sourceId'], 'units', '同名', current, 'content/units/live.json', 7)
    rows = {row['field']: row for row in result['rows']}
    assert result['sessionId'] == 'session-one' and result['revision'] == 7
    assert result['currentPath'] == 'content/units/live.json'
    assert rows['health']['current']['text'] == '200'
    assert rows['health']['different'] and rows['enabled']['different'] and rows['nested']['different']
    assert rows['array']['different'] and not rows['number']['different']
    assert rows['nullable']['current']['kind'] == 'missing'
    assert rows['nullable']['reference']['kind'] == 'null'
    assert rows['dash']['reference']['text'] == '"-"'
    assert rows['empty']['current']['text'] == '""'
    assert current['enabled'] is True and 'nullable' not in current
    assert source_file.read_bytes() == before
    # The snapshot owns its data, and callers cannot alter it through returned DTOs.
    source_file.write_text('{"health":999}', encoding='utf-8')
    rows['health']['reference']['text'] = 'changed'
    again = refs.compare(source['sourceId'], 'units', '同名', {}, 'content/units/live.json', 8)
    assert next(row for row in again['rows'] if row['field'] == 'health')['reference']['text'] == '100'


@pytest.mark.parametrize('prefix', ['', '一层包装/'])
def test_zip_snapshot_supports_existing_layouts_and_releases_the_file(tmp_path, prefix):
    archive = tmp_path / '中文参考.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr(prefix + 'mod.json', '{"name":"参考"}')
        output.writestr(prefix + 'content/units/同名.json', '{"health":123}')
        output.writestr(prefix + 'content/blocks/同名.json', '{"health":456}')
        output.writestr(prefix + 'scripts/main.js', 'throw new Error("must not execute")')
        output.writestr(prefix + 'content/units/deeper/ignored.json', '{"health":999}')
    before = archive.read_bytes()
    refs = service()
    source = refs.open_zip(archive)
    assert source['label'] == '参考' and source['kind'] == 'zip'
    assert archive.read_bytes() == before
    # Windows will refuse this if any ZIP handle has leaked.
    archive.rename(tmp_path / 'renamed.zip')
    assert len(list(tmp_path.iterdir())) == 1
    assert refs.candidates(source['sourceId'], 'units')['total'] == 1
    result = refs.compare(source['sourceId'], 'blocks', '同名', {}, 'content/units/live.json', 1)
    assert result['rows'][0]['reference']['text'] == '456'


@pytest.mark.parametrize('bad_name', ['../escape.json', '/absolute.json', 'C:/drive.json',
    'a\\b.json', 'content/units/a:stream.json', 'content/units/CON.json',
    'content/units/trailing /x.json', 'a/./b.json', 'content//units/a.json',
    'content/units/name.json.', 'content/units/COM1.txt', '//server/path', 'a/' * 9 + 'x.json'])
def test_archive_rejects_unsafe_or_ambiguous_paths_without_losing_current(tmp_path, bad_name):
    refs = service()
    good = refs.open_folder(folder(tmp_path / 'current'))
    archive = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('content/units/a.json', '{}')
        output.writestr(bad_name, '{}')
    if bad_name == 'a\\b.json':
        # ZipFile normalizes separators on Windows when writing fixtures.
        archive.write_bytes(archive.read_bytes().replace(b'a/b.json', b'a\\b.json'))
    with pytest.raises(ValueError, match='ZIP.*路径'):
        refs.open_zip(archive)
    assert [item['sourceId'] for item in refs.sources()] == ['vanilla', good['sourceId']]


@pytest.mark.parametrize('kind', ['case', 'link', 'parent_file'])
def test_archive_rejects_duplicate_identity_links_and_file_directory_collisions(tmp_path, kind):
    archive = tmp_path / 'ambiguous.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('content/units/a.json', '{}')
        if kind == 'case':
            output.writestr('CONTENT/units/A.json', '{}')
        elif kind == 'link':
            entry = zipfile.ZipInfo('link')
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            output.writestr(entry, '../outside')
        else:
            output.writestr('content/units', '{}')
    with pytest.raises(ValueError, match='ZIP'):
        service().open_zip(archive)


@pytest.mark.parametrize('limit', ['MAX_DOCUMENT_BYTES', 'MAX_TOTAL_BYTES', 'MAX_ENTRIES', 'MAX_CONTENTS'])
@pytest.mark.parametrize('kind', ['folder', 'zip'])
def test_source_budgets_fail_atomically(tmp_path, kind, limit):
    refs = service()
    current = refs.open_folder(folder(tmp_path / 'current'))
    setattr(refs, limit, 1)
    if kind == 'folder':
        root = folder(tmp_path / 'candidate')
        (root / 'content/units/second.json').write_text('{}', encoding='utf-8')
        read = lambda: refs.open_folder(root)
    else:
        archive = tmp_path / 'budget.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('content/units/a.json', '{}')
            output.writestr('content/units/b.json', '{}')
        read = lambda: refs.open_zip(archive)
    with pytest.raises(ValueError):
        read()
    assert [item['sourceId'] for item in refs.sources()] == ['vanilla', current['sourceId']]


def test_two_phase_sources_cancel_release_and_session_close(tmp_path):
    refs = service()
    current = refs.open_folder(folder(tmp_path / 'current'))
    pending = refs.open_folder(folder(tmp_path / 'pending'))
    with pytest.raises(ValueError, match='确认或取消'):
        refs.open_folder(tmp_path / 'not-read')
    refs.release(pending['sourceId'])
    refs.release(pending['sourceId'])
    assert refs.candidates(current['sourceId'], 'units')['total'] == 1
    replacement = refs.open_folder(folder(tmp_path / 'replacement'))
    refs.release(current['sourceId'])
    with pytest.raises(ValueError, match='不存在或已释放'):
        refs.candidates(current['sourceId'], 'units')
    other_session = ReferenceProjectsService(Metadata('metadata'), 'session-two')
    with pytest.raises(ValueError, match='不存在或已释放'):
        other_session.candidates(replacement['sourceId'], 'units')
    refs.close()
    refs.close()
    with pytest.raises(ValueError, match='已关闭'):
        refs.sources()


def test_malformed_files_are_reported_and_empty_reference_fails(tmp_path):
    root = folder(tmp_path / 'mixed')
    (root / 'content/units/bad.json').write_text('{bad', encoding='utf-8')
    (root / 'content/units/list.json').write_text('[]', encoding='utf-8')
    (root / 'mod.json').write_text('{"name":42,"displayName":"显示名"}', encoding='utf-8')
    refs = service()
    result = refs.open_folder(root)
    assert result['label'] == '显示名' and len(result['warnings']) == 2
    (root / 'content/units/同名.json').unlink()
    with pytest.raises(ValueError, match='没有可读取'):
        refs.open_folder(root)


@pytest.mark.parametrize('kind', ['folder', 'zip'])
def test_deep_json_and_cumulative_node_budget_are_rejected(tmp_path, kind):
    deep = '{"value":' + '[' * 1200 + '0' + ']' * 1200 + '}'
    refs = service()
    if kind == 'folder':
        root = folder(tmp_path / 'deep')
        (root / 'content/units/同名.json').write_text(deep, encoding='utf-8')
        read = lambda: refs.open_folder(root)
    else:
        archive = tmp_path / 'deep.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('content/units/a.json', deep)
        read = lambda: refs.open_zip(archive)
    with pytest.raises(ValueError, match='结构过深'):
        read()
    refs.MAX_SOURCE_NODES = 5
    root = folder(tmp_path / 'nodes', {'one': 1, 'two': 2})
    (root / 'content/units/second.json').write_text('{"one":1,"two":2}', encoding='utf-8')
    with pytest.raises(ValueError, match='总量'):
        refs.open_folder(root)


def test_real_vanilla_candidates_and_nonfinite_values_are_readonly_json_safe():
    refs = service()
    source = refs.sources()[0]
    assert source['sourceId'] == 'vanilla'
    candidates = refs.candidates('vanilla', 'Weapons', 'beam-weapon')
    assert candidates['total'] >= 1
    result = refs.compare('vanilla', 'Weapons', 'beam-weapon', {}, 'content/weapons/current.json', 0)
    assert any(row['reference']['kind'] == 'nonfinite' for row in result['rows'])
    json.dumps(result, allow_nan=False)
    with pytest.raises(ValueError):
        refs.compare('vanilla', 'Weapons', '../../outside', {}, 'content/weapons/current.json', 0)


def test_directory_junction_cannot_import_outside_content(tmp_path):
    root = tmp_path / 'chosen'
    root.mkdir()
    outside = folder(tmp_path / 'outside')
    link = root / 'content'
    if os.name == 'nt':
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside / 'content')],
                       check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        link.symlink_to(outside / 'content', target_is_directory=True)
    with pytest.raises(ValueError, match='符号链接或重解析点'):
        service().open_folder(root)


@pytest.mark.parametrize('case', ['not_zip', 'no_content', 'two_roots', 'deep_wrapper', 'corrupt_deflate'])
def test_unsupported_and_corrupt_archives_leave_no_source_or_handle(tmp_path, case):
    path = tmp_path / 'invalid.zip'
    if case == 'not_zip':
        path.write_text('plain text', encoding='utf-8')
    else:
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as output:
            if case == 'no_content':
                output.writestr('mod.json', '{}')
            elif case == 'two_roots':
                output.writestr('first/content/units/a.json', '{}')
                output.writestr('second/content/units/a.json', '{}')
            elif case == 'deep_wrapper':
                output.writestr('first/second/content/units/a.json', '{}')
            else:
                output.writestr('content/units/a.json', '{"health":100}')
        if case == 'corrupt_deflate':
            raw = bytearray(path.read_bytes())
            data_start = 30 + len('content/units/a.json')
            raw[data_start] = 0xff
            path.write_bytes(raw)
    refs = service()
    with pytest.raises(ValueError):
        refs.open_zip(path)
    assert len(refs.sources()) == 1
    path.rename(tmp_path / 'closed.zip')


def test_candidate_pagination_search_and_descriptor_copies(tmp_path):
    root = folder(tmp_path / 'names')
    for name in ['aaa', 'bbb', 'ccc']:
        (root / f'content/units/{name}.json').write_text('{}', encoding='utf-8')
    refs = service()
    result = refs.open_folder(root)
    result['categories'].clear()
    assert refs.sources()[1]['categories'][0]['id'] == 'units'
    page = refs.candidates(result['sourceId'], 'units', offset=1, limit=2)
    assert [item['name'] for item in page['candidates']] == ['bbb', 'ccc']
    assert page['total'] == 4 and page['hasMore']
    assert refs.candidates(result['sourceId'], 'units', 'BBB')['candidates'][0]['name'] == 'bbb'
    for bad in [True, -1, '0']:
        with pytest.raises(ValueError, match='分页'):
            refs.candidates(result['sourceId'], 'units', offset=bad)
    with pytest.raises(ValueError, match='搜索'):
        refs.candidates(result['sourceId'], 'units', query='a' * 257)


def test_structure_comparison_preserves_key_order_independence_and_unknown_fields(tmp_path):
    refs = service()
    source = refs.open_folder(folder(tmp_path / 'nested', {'custom': {'a': 1, 'b': [None, '-', False]},
                                                          'actualDash': '-', 'long': 'x' * 600}))
    current = {'custom': {'b': [None, '-', False], 'a': 1}, 'actualDash': None, 'long': 'x' * 599 + 'y'}
    result = refs.compare(source['sourceId'], 'units', '同名', current, 'current.json', 1)
    rows = {row['field']: row for row in result['rows']}
    assert not rows['custom']['different']
    assert rows['actualDash']['different'] and rows['long']['different']
    assert rows['long']['current']['truncated']
    # Truncated display equality is not used for the actual comparison.
    assert rows['long']['current']['text'] == rows['long']['reference']['text']


def test_zip_keeps_windows_case_insensitive_root_and_explicit_directories(tmp_path):
    path = tmp_path / 'upper.zip'
    with zipfile.ZipFile(path, 'w') as output:
        output.writestr('Wrapper/', '')
        output.writestr('Wrapper/CONTENT/', '')
        output.writestr('Wrapper/CONTENT/Units/', '')
        output.writestr('Wrapper/MOD.JSON', '{"name":"大写路径"}')
        output.writestr('Wrapper/CONTENT/Units/A.JSON', '{"health":10}')
    refs = service()
    source = refs.open_zip(path)
    assert source['label'] == '大写路径'
    assert refs.candidates(source['sourceId'], 'Units')['candidates'][0]['name'] == 'A'
