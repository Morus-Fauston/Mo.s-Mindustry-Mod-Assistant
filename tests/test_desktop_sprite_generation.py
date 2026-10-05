"""Generation candidates use actual PNGs, core algorithms and the shared history."""
import base64
from io import BytesIO

from PIL import Image
import pytest

from app.core.commands import CommandStack
from app.core.project import Project
from app.desktop.resources import ResourceService
from app.desktop.sprite_generation import SpriteGenerationService


@pytest.fixture
def generation(tmp_path):
    project = Project.create(tmp_path, 'generation', '生成测试')
    project.contents.save('unit', {'type': 'UnitType'}, 'units')
    source = Image.new('RGBA', (7, 7), (0, 0, 0, 0))
    source.putpixel((3, 3), (200, 50, 30, 255))
    source.save(project.sprite_path('units', 'unit'))
    stack = CommandStack()
    changed = []
    resources = ResourceService(project, stack)
    service = SpriteGenerationService(project, resources, 'session-a', on_change=lambda: changed.append(True))
    return project, stack, service, changed


def test_outline_preview_is_real_png_without_disk_or_history_and_cancel_releases(generation):
    project, stack, service, _ = generation
    candidate = service.preview('content/units/unit.json', [{'suffix': '-outline'}])
    assert candidate['sessionId'] == 'session-a'
    output = candidate['outputs'][0]
    assert (output['width'], output['height']) == (7, 7)
    with Image.open(BytesIO(base64.b64decode(output['dataUrl'].split(',', 1)[1]))) as image:
        assert image.getpixel((3, 3)) == (200, 50, 30, 255)
        assert image.getpixel((2, 3)) == (0, 0, 0, 255)
        assert image.getpixel((0, 0)) == (0, 0, 0, 0)
    assert not project.sprite_path('units', 'unit', '-outline').exists()
    assert not stack.can_undo
    service.cancel(candidate['candidateId'])
    with pytest.raises(ValueError, match='候选'):
        service.confirm(candidate['candidateId'])


def test_preview_propagates_verified_file_read_failure_without_candidate_or_history(generation, monkeypatch):
    from contextlib import contextmanager
    import app.desktop.sprite_generation as module
    project, stack, service, changed = generation
    checked = []
    @contextmanager
    def unavailable(root, path):
        checked.append((root, path))
        raise OSError('工程来源在读取时发生变化，请刷新后重试')
        yield
    monkeypatch.setattr(module, 'open_project_file', unavailable, raising=False)
    with pytest.raises(OSError, match='读取时发生变化'):
        service.preview('content/units/unit.json', [{'suffix': '-outline'}])
    assert checked == [(project.root.resolve(), project.sprite_path('units', 'unit'))]
    assert not stack.can_undo and not changed
    assert not project.sprite_path('units', 'unit', '-outline').exists()


@pytest.mark.parametrize('changed_part', ['source', 'target', 'content'])
def test_confirm_rejects_changed_inputs_or_destination_without_losing_candidate(generation, changed_part):
    project, stack, service, _ = generation
    target = project.sprite_path('units', 'unit', '-outline')
    candidate = service.preview('content/units/unit.json', [{'suffix': '-outline'}])
    if changed_part == 'source':
        project.sprite_path('units', 'unit').write_bytes(b'external source')
    elif changed_part == 'target':
        target.write_bytes(b'external destination')
    else:
        project.contents.save('unit', {'type': 'UnitType', 'health': 25}, 'units')
    with pytest.raises(ValueError, match='变化|修改'):
        service.confirm(candidate['candidateId'], overwrite=True)
    assert not stack.can_undo
    assert target.read_bytes() == b'external destination' if changed_part == 'target' else not target.exists()
    service.cancel(candidate['candidateId'])


def test_confirm_saves_batch_as_one_command_and_history_restores_exact_files(generation):
    project, stack, service, changed = generation
    candidate = service.preview('content/units/unit.json', [
        {'suffix': '-outline', 'options': {'expandPx': 1, 'color': '#112233'}},
        {'suffix': '-shadow', 'options': {'opacity': 40}},
    ])
    saved = service.confirm(candidate['candidateId'])
    assert len(saved['outputs']) == 2
    outline = project.sprite_path('units', 'unit', '-outline')
    shadow = project.sprite_path('units', 'unit', '-shadow')
    original = [outline.read_bytes(), shadow.read_bytes()]
    with Image.open(outline) as image:
        assert image.getpixel((2, 3)) == (17, 34, 51, 255)
    with Image.open(shadow) as image:
        assert 0 < max(image.getchannel('A').tobytes()) <= 40
    stack.undo()
    assert not outline.exists() and not shadow.exists() and not stack.can_undo
    stack.redo()
    assert [outline.read_bytes(), shadow.read_bytes()] == original
    assert changed == [True, True, True]
    with pytest.raises(ValueError, match='候选'):
        service.confirm(candidate['candidateId'])


@pytest.mark.parametrize('outputs', [None, [], [{'suffix': '../x'}], [{'suffix': '-cell'}],
    [{'suffix': '-outline'}, {'suffix': '-outline'}], [{'suffix': '-outline', 'path': '/elsewhere'}],
    [{'suffix': '-outline', 'options': {'expandPx': True}}],
    [{'suffix': '-outline', 'options': {'expandPx': 1000000}}],
    [{'suffix': '-outline', 'options': {'color': 'invalid'}}],
    [{'suffix': '-shadow', 'options': {'opacity': -1}}],
    [{'suffix': '-shadow', 'options': {'opacity': 256}}],
    [{'suffix': '-shadow', 'options': {'unknown': 1}}]])
def test_invalid_generation_requests_never_write_or_create_history(generation, outputs):
    project, stack, service, _ = generation
    with pytest.raises(ValueError):
        service.preview('content/units/unit.json', outputs)
    assert not stack.can_undo
    assert len(list(project.sprites_dir.rglob('*.png'))) == 1


def test_overwrite_confirmation_required_and_close_invalidates_candidates(generation):
    project, stack, service, _ = generation
    target = project.sprite_path('units', 'unit', '-outline')
    target.write_bytes(b'prior file preserved')
    candidate = service.preview('content/units/unit.json', [{'suffix': '-outline'}])
    with pytest.raises(ValueError, match='确认'):
        service.confirm(candidate['candidateId'])
    assert target.read_bytes() == b'prior file preserved' and not stack.can_undo
    service.confirm(candidate['candidateId'], overwrite=True)
    stack.undo()
    assert target.read_bytes() == b'prior file preserved'
    another = service.preview('content/units/unit.json', [{'suffix': '-outline'}])
    service.close()
    with pytest.raises(ValueError, match='关闭|候选'):
        service.confirm(another['candidateId'], overwrite=True)
    with pytest.raises(ValueError, match='关闭'):
        service.preview('content/units/unit.json', [{'suffix': '-outline'}])


def test_full_uses_actual_overlay_and_recursive_weapon_with_mirror_and_detects_changes(generation):
    project, stack, service, _ = generation
    project.contents.save('unit', {'type': 'UnitType', 'weapons': [{'name': 'laser', 'x': 2, 'y': 0, 'mirror': True}]}, 'units')
    cell = Image.new('RGBA', (7, 7), (0, 0, 0, 0))
    cell.putpixel((3, 3), (0, 0, 255, 255))
    cell.save(project.sprite_path('units', 'unit', '-cell'))
    weapon = project.sprites_dir / 'custom/laser.png'
    weapon.parent.mkdir()
    Image.new('RGBA', (2, 2), (0, 255, 0, 255)).save(weapon)
    candidate = service.preview('content/units/unit.json', [{'suffix': '-full'}])
    output = candidate['outputs'][0]
    assert (output['width'], output['height']) == (18, 7)
    with Image.open(BytesIO(base64.b64decode(output['dataUrl'].split(',', 1)[1]))) as image:
        assert image.getpixel((9, 3)) == (0, 0, 255, 255)
        assert image.getpixel((0, 2)) == image.getpixel((16, 2)) == (0, 255, 0, 255)
    Image.new('RGBA', (2, 2), 'red').save(weapon)
    with pytest.raises(ValueError, match='变化'):
        service.confirm(candidate['candidateId'])
    assert not stack.can_undo


def test_full_refuses_unbounded_weapon_canvas_before_allocating(generation):
    project, _, service, _ = generation
    project.contents.save('unit', {'type': 'UnitType', 'weapons': [{'name': 'laser', 'x': 1000000}]}, 'units')
    Image.new('RGBA', (2, 2), 'green').save(project.sprite_path('weapons', 'laser'))
    with pytest.raises(ValueError, match='尺寸|上限'):
        service.preview('content/units/unit.json', [{'suffix': '-full'}])


def test_candidates_have_count_and_byte_budgets_and_cancel_frees_capacity(generation, monkeypatch):
    _, _, service, _ = generation
    monkeypatch.setattr(service, 'MAX_CANDIDATES', 1)
    first = service.preview('content/units/unit.json', [{'suffix': '-outline'}])
    with pytest.raises(ValueError, match='上限'):
        service.preview('content/units/unit.json', [{'suffix': '-shadow'}])
    service.cancel(first['candidateId'])
    second = service.preview('content/units/unit.json', [{'suffix': '-shadow'}])
    service.cancel(second['candidateId'])
    monkeypatch.setattr(service, 'MAX_CANDIDATE_BYTES', 1)
    with pytest.raises(ValueError, match='上限'):
        service.preview('content/units/unit.json', [{'suffix': '-outline'}])


@pytest.mark.parametrize('operation', ['confirm', 'undo', 'redo'])
def test_batch_write_failure_restores_all_files_and_preserves_history(generation, monkeypatch, operation):
    import os
    project, stack, service, changed = generation
    paths = [project.sprite_path('units', 'unit', suffix) for suffix in ('-outline', '-shadow')]
    old = [b'prior outline', b'prior shadow']
    for path, raw in zip(paths, old):
        path.write_bytes(raw)
    candidate = service.preview('content/units/unit.json', [{'suffix': '-outline'}, {'suffix': '-shadow'}])
    if operation != 'confirm':
        service.confirm(candidate['candidateId'], overwrite=True)
        if operation == 'redo':
            stack.undo()
    previous = [path.read_bytes() for path in paths]
    previous_history, previous_notifications = (stack.can_undo, stack.can_redo), len(changed)
    actual_replace, calls = os.replace, 0
    def fail_second(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise PermissionError('模拟第二个生成文件不可写')
        actual_replace(source, destination)
    monkeypatch.setattr(os, 'replace', fail_second)
    with pytest.raises(PermissionError):
        if operation == 'confirm':
            service.confirm(candidate['candidateId'], overwrite=True)
        else:
            getattr(stack, operation)()
    assert [path.read_bytes() for path in paths] == previous
    assert (stack.can_undo, stack.can_redo) == previous_history
    assert len(changed) == previous_notifications
    assert list(paths[0].parent.glob('*.tmp')) == []
    if operation == 'confirm':
        result = service.confirm(candidate['candidateId'], overwrite=True)
        assert all(output['exists'] for output in result['outputs'])


def test_shared_resource_history_budget_applies_to_generated_batch(generation, monkeypatch):
    _, stack, service, _ = generation
    monkeypatch.setattr(ResourceService, 'MAX_SNAPSHOT_BYTES', 1)
    candidate = service.preview('content/units/unit.json', [{'suffix': '-outline'}])
    with pytest.raises(ValueError, match='快照'):
        service.confirm(candidate['candidateId'])
    assert not stack.can_undo
    service.cancel(candidate['candidateId'])


def test_source_change_during_staged_write_rolls_back_generated_files(generation, monkeypatch):
    import os
    project, stack, service, changed = generation
    candidate = service.preview('content/units/unit.json', [{'suffix': '-outline'}])
    flush = os.fsync
    def external_edit(fd):
        flush(fd)
        project.sprite_path('units', 'unit').write_bytes(b'external edit during generation save')
    monkeypatch.setattr(os, 'fsync', external_edit)
    with pytest.raises(ValueError, match='变化'):
        service.confirm(candidate['candidateId'])
    assert not project.sprite_path('units', 'unit', '-outline').exists()
    assert not stack.can_undo and changed == []


@pytest.mark.parametrize('limit', ['MAX_FILE_BYTES', 'MAX_PIXELS', 'MAX_DIMENSION', 'MAX_TOTAL_PIXELS'])
def test_generation_input_budgets_reject_before_creating_files(generation, monkeypatch, limit):
    project, stack, service, _ = generation
    monkeypatch.setattr(service, limit, 1)
    with pytest.raises(ValueError, match='上限'):
        service.preview('content/units/unit.json', [{'suffix': '-outline'}])
    assert not stack.can_undo and not project.sprite_path('units', 'unit', '-outline').exists()


def test_corrupt_or_disguised_source_cannot_generate(generation):
    project, stack, service, _ = generation
    source = project.sprite_path('units', 'unit')
    source.write_bytes(b'broken PNG')
    with pytest.raises(ValueError, match='PNG'):
        service.preview('content/units/unit.json', [{'suffix': '-outline'}])
    Image.new('RGB', (3, 3), 'red').save(source, format='JPEG')
    with pytest.raises(ValueError, match='PNG'):
        service.preview('content/units/unit.json', [{'suffix': '-outline'}])
    assert not stack.can_undo


def test_batch_checks_all_destinations_before_writing_any(generation, monkeypatch):
    import os
    project, stack, service, _ = generation
    candidate = service.preview('content/units/unit.json', [{'suffix': '-outline'}, {'suffix': '-shadow'}])
    project.sprite_path('units', 'unit', '-shadow').write_bytes(b'external destination')
    def unexpected_write(*args):
        pytest.fail('Batch wrote before validating all targets')
    monkeypatch.setattr(os, 'replace', unexpected_write)
    with pytest.raises(ValueError, match='修改'):
        service.confirm(candidate['candidateId'])
    assert not stack.can_undo and not project.sprite_path('units', 'unit', '-outline').exists()


def test_added_overlay_invalidates_full_preview_and_fresh_candidate_uses_it(generation):
    project, _, service, _ = generation
    candidate = service.preview('content/units/unit.json', [{'suffix': '-full'}])
    Image.new('RGBA', (7, 7), (4, 5, 6, 255)).save(project.sprite_path('units', 'unit', '-cell'))
    with pytest.raises(ValueError, match='变化'):
        service.confirm(candidate['candidateId'])
    service.cancel(candidate['candidateId'])
    fresh = service.preview('content/units/unit.json', [{'suffix': '-full'}])
    service.confirm(fresh['candidateId'])
    with Image.open(project.sprite_path('units', 'unit', '-full')) as image:
        assert image.getpixel((3, 3)) == (4, 5, 6, 255)
