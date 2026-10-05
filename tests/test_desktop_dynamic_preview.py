"""Dynamic descriptors use real static resources and never alter content."""

from copy import deepcopy
import json

from PIL import Image
import pytest

from app.core.project import Project
from app.desktop.preview import PreviewService
from app.desktop.dynamic_preview import DynamicPreviewService


def png(project, name, size=(32, 32), category='units'):
    path = project.sprite_path(category, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGBA', size, (60, 130, 210, 170)).save(path)
    return path


def fixture(tmp_path, data):
    project = Project.create(tmp_path, 'test', '测试')
    project.contents.save('unit', data, 'units')
    content = project.contents.get_by_path('units/unit.json')
    png(project, 'unit')
    preview = PreviewService(project, 'session')
    return project, content, preview


def test_descriptor_preserves_real_reference_coordinates_and_stable_weapon_identity(tmp_path):
    project, content, preview = fixture(tmp_path, {'type': 'mech', 'weapons': [
        {'name': 'test-gun', 'mirror': True, 'recoil': 2, 'recoilPow': 1.8}]})
    project.contents.save('gun', {'x': -3, 'y': 2, 'recoil': 99}, 'weapons')
    png(project, 'gun', (8, 12), 'weapons')
    scene = preview.scene(content)
    scene['tree'] = [{'id': 'group:weapons', 'children': [
        {'id': 'weapon:stable-id', 'drawableKeys': ['__weapon_0__']}]}]
    original, original_scene = deepcopy(content.data), deepcopy(scene)
    # Root adds the public thin registration method during serial integration.
    descriptor = DynamicPreviewService(project, preview._load).describe(content, scene)
    assert descriptor['supported'] is True
    assert descriptor['weapons'] == [{'nodeId': 'weapon:stable-id', 'layerKeys': ['__weapon_0__'],
        'recoilDistance': 2, 'recoilPower': 1.8, 'flashCenter': {'x': 4, 'y': 8}}]
    assert descriptor['recoilTime'] == 10 and descriptor['cooldownTime'] == 20
    assert descriptor['directions'] == [{'value': v, 'label': v, 'degrees': d}
        for v, d in [('上', 0), ('右', 90), ('下', 180), ('左', 270)]]
    assert next(team for team in descriptor['teams'] if team['value'] == '蓝队')['color'] == '#50a9ee'
    assert content.data == original and scene == original_scene
    assert json.loads(content.path.read_text(encoding='utf-8')) == original


def test_finite_parameter_fallback_and_bad_reference_keep_static_content(tmp_path):
    project, content, preview = fixture(tmp_path, {'type': 'mech', 'recoilTime': 'nan',
        'cooldownTime': 'inf', 'weapons': [{'name': 'gun', 'x': 2, 'y': 1,
        'recoil': 'nan', 'recoilPow': 'inf'}, {'name': '../bad'}, {'x': 0, 'y': 0}]})
    png(project, 'gun', category='weapons')
    scene = preview.scene(content)
    result = DynamicPreviewService(project, preview._load).describe(content, scene)
    assert (result['recoilTime'], result['cooldownTime']) == (10, 20)
    assert (result['weapons'][0]['recoilDistance'], result['weapons'][0]['recoilPower']) == (1, 1.8)
    assert len(result['weapons']) == 2 and len(result['notices']) == 5
    json.dumps(result, allow_nan=False)
    assert len(scene['layers']) == 2


def test_treads_use_only_existing_rect_zero_frames_and_preserve_resource_registry(tmp_path):
    project, content, preview = fixture(tmp_path, {'type': 'tank', 'treadFrames': 4})
    png(project, 'unit-treads')
    png(project, 'unit-treads0-0', (12, 8))
    png(project, 'unit-treads0-2', (14, 10))
    png(project, 'unit-treads1-0', (99, 99))
    scene = preview.scene(content)
    body = scene['layers'][0]['resourceId']
    result = DynamicPreviewService(project, preview._load).describe(content, scene)
    assert result['treads']['nodeId'] == 'sprite:-treads'
    assert result['treads']['layerKey'] == '-treads'
    assert [(f['width'], f['height']) for f in result['treads']['frames']] == [(12, 8), (14, 10)]
    for frame in result['treads']['frames']:
        assert preview.resource(frame['resourceId'])['width'] == frame['width']
    assert preview.resource(body)['width'] == 32
    assert scene['layers'][1]['width'] == 32


def test_heat_engine_and_tint_targets_preserve_existing_static_layers(tmp_path):
    project, content, preview = fixture(tmp_path, {'type': 'flying', 'engineSize': 2, 'engineOffset': 3})
    png(project, 'unit-cell', (16, 16))
    png(project, 'unit-heat', (8, 12))
    scene = preview.scene(content)
    original = deepcopy(scene)
    result = DynamicPreviewService(project, preview._load).describe(content, scene)
    assert result['engine'] == {'nodeId': 'engine', 'outerIndex': 0, 'innerIndex': 1, 'size': 2}
    assert result['cellLayerKeys'] == ['-cell'] and result['teamLayerKeys'] == []
    heat = result['heat']
    assert (heat['x'], heat['y'], heat['width'], heat['height'], heat['z']) == (12, 10, 8, 12, 12)
    assert (heat['key'], heat['nodeId'], heat['color']) == ('__heat__', 'sprite:-heat', '#ff795e')
    assert preview.resource(heat['resourceId'])['width'] == 8
    assert result['flash'] == {'radius': 4, 'color': '#fff3a1', 'z': 20}
    assert scene == original


def test_foreign_content_cannot_be_described_using_another_projects_scene(tmp_path):
    project, content, preview = fixture(tmp_path, {'type': 'tank'})
    foreign = Project.create(tmp_path, 'foreign', '其他')
    foreign.contents.save('unit', {'type': 'tank'}, 'units')
    other = foreign.contents.get_by_path('units/unit.json')
    with pytest.raises(ValueError, match='当前工程'):
        DynamicPreviewService(project, preview._load).describe(other, preview.scene(content))


@pytest.mark.parametrize('limit,value', [('MAX_RESOURCES', 2), ('MAX_SCENE_PIXELS', 2048), ('MAX_CACHE_BYTES', 500)])
def test_dynamic_resource_limits_leave_static_layers_usable(tmp_path, monkeypatch, limit, value):
    project, content, preview = fixture(tmp_path, {'type': 'tank', 'treadFrames': 3})
    png(project, 'unit-treads')
    png(project, 'unit-treads0-0')
    png(project, 'unit-heat')
    scene = preview.scene(content)
    monkeypatch.setattr(preview, limit, value)
    result = DynamicPreviewService(project, preview._load).describe(content, scene)
    assert result['supported'] is True
    assert result['treads'] is None and result['heat'] is None and result['notices']
    assert all(preview.resource(layer['resourceId'])['width'] == 32 for layer in scene['layers'])


def test_corrupt_tread_and_heat_recover_after_valid_resource_replacement(tmp_path):
    project, content, preview = fixture(tmp_path, {'type': 'tank', 'treadFrames': 3})
    png(project, 'unit-treads')
    corrupt = project.sprite_path('units', 'unit', '-treads0-0')
    corrupt.write_bytes(b'not png')
    project.sprite_path('units', 'unit', '-heat').write_bytes(b'not png')
    service = DynamicPreviewService(project, preview._load)
    result = service.describe(content, preview.scene(content))
    assert result['treads'] is None and result['heat'] is None and len(result['notices']) == 2
    png(project, 'unit-treads0-0', (5, 7))
    png(project, 'unit-heat', (3, 5))
    recovered = service.describe(content, preview.scene(content))
    assert recovered['treads']['frames'][0]['width'] == 5 and recovered['heat']['width'] == 3
    assert recovered['notices'] == []


def test_tread_candidate_budget_ignores_frames_after_64_and_reports_limit(tmp_path):
    project, content, preview = fixture(tmp_path, {'type': 'tank', 'treadFrames': 1000000})
    png(project, 'unit-treads')
    png(project, 'unit-treads0-63', (2, 3))
    png(project, 'unit-treads0-64', (7, 8))
    result = DynamicPreviewService(project, preview._load).describe(content, preview.scene(content))
    assert [(f['width'], f['height']) for f in result['treads']['frames']] == [(2, 3)]
    assert any('64' in notice for notice in result['notices'])


@pytest.mark.parametrize('frames', ['nan', 'inf', None, {}, 10**100])
def test_invalid_tread_count_falls_back_to_18_with_notice(tmp_path, frames):
    project, content, preview = fixture(tmp_path, {'type': 'tank', 'treadFrames': frames})
    png(project, 'unit-treads')
    png(project, 'unit-treads0-17', (2, 3))
    png(project, 'unit-treads0-18', (7, 8))
    result = DynamicPreviewService(project, preview._load).describe(content, preview.scene(content))
    assert [(f['width'], f['height']) for f in result['treads']['frames']] == [(2, 3)]
    assert result['notices']
    json.dumps(result, allow_nan=False)


def test_missing_body_and_non_tank_keep_static_fallback_without_generated_frames(tmp_path):
    project, content, preview = fixture(tmp_path, {'type': 'mech'})
    png(project, 'unit-treads0-0')
    png(project, 'unit-treads')
    service = DynamicPreviewService(project, preview._load)
    assert service.describe(content, preview.scene(content))['treads'] is None
    project.sprite_path('units', 'unit').unlink()
    png(project, 'unit-heat')
    result = service.describe(content, preview.scene(content))
    assert result['supported'] is False and result['heat'] is None and result['treads'] is None


def test_actual_published_heat_layer_remains_alongside_dynamic_heat(tmp_path):
    project = Project.create(tmp_path, 'test', '测试')
    project.contents.save('gun', {'type': 'Weapon'}, 'weapons')
    content = project.contents.get_by_path('weapons/gun.json')
    png(project, 'gun', category='weapons')
    png(project, 'gun-heat', category='weapons')
    preview = PreviewService(project, 'session')
    scene = preview.scene(content)
    result = DynamicPreviewService(project, preview._load).describe(content, scene)
    static_heat = next(layer for layer in scene['layers'] if layer['key'] == '-heat')
    assert result['heat']['resourceId'] == static_heat['resourceId']
    assert static_heat['key'] != result['heat']['key'] and result['heat']['z'] == 12


def test_dynamic_resource_ids_are_revoked_with_the_scene_and_reject_foreign_session(tmp_path):
    project, content, preview = fixture(tmp_path, {'type': 'tank'})
    png(project, 'unit-treads')
    png(project, 'unit-treads0-0')
    png(project, 'unit-heat')
    result = DynamicPreviewService(project, preview._load).describe(content, preview.scene(content))
    resource_id = result['heat']['resourceId']
    other_preview = PreviewService(project, 'other-session')
    with pytest.raises(ValueError):
        other_preview.resource(resource_id)
    project.sprite_path('units', 'unit').unlink()
    preview.scene(content)
    with pytest.raises(ValueError):
        preview.resource(resource_id)


def test_invalid_weapon_collection_keeps_descriptor_usable_with_notice(tmp_path):
    project, content, preview = fixture(tmp_path, {'type': 'mech', 'weapons': {'unexpected': True}})
    result = DynamicPreviewService(project, preview._load).describe(content, preview.scene(content))
    assert result['supported'] and not result['weapons'] and result['notices']


def test_content_filename_equal_to_project_prefix_is_not_a_weapon_reference(tmp_path):
    project = Project.create(tmp_path, 'test', '测试')
    project.contents.save('test-', {'type': 'mech'}, 'units')
    content = project.contents.get_by_path('units/test-.json')
    png(project, 'test-')
    preview = PreviewService(project, 'session')
    result = DynamicPreviewService(project, preview._load).describe(content, preview.scene(content))
    assert result['supported'] and result['notices'] == []
