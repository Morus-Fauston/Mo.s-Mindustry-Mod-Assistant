"""Legacy weapon representations use one real root and shared reversible state."""

from copy import deepcopy
import json
import pytest

from app.core.commands import CommandStack
from app.core.content_store import ContentData
from app.core.metadata import Metadata
from app.core.project import Project
from app.desktop.forms import FormService
from app.desktop.nested_forms import NestedFormService
from app.desktop.references import ReferenceService
from app.desktop.weapon_forms import WeaponFormsService


PATH = 'content/units/unit.json'


def setup(tmp_path, data=None):
    project = Project.create(tmp_path, 'probe', '武器测试')
    metadata = Metadata('metadata')
    nested = NestedFormService(metadata, FormService(metadata, ReferenceService(metadata, project)))
    service = WeaponFormsService(nested, project)
    content = ContentData('unit', 'units', data if data is not None else {'type': 'mech', 'weapons': []})
    return service, nested, project, content, CommandStack()


def fields(plan):
    return {field['name']: field for group in plan['groups'] for field in group['fields']}


def rows(service, content):
    return fields(service.plan(content, PATH))['weapons']['items']


def apply(service, content, stack, action, **payload):
    command = service.command(action, content, PATH, payload)
    if command is not None:
        stack.execute(command)
    return command


def test_missing_type_weapon_modes_and_display_do_not_materialize_values(tmp_path):
    original = {'type': 'mech', 'weapons': [{'name': 'missing', 'x': 2, 'rotateSpeed': 8},
                                         {'name': 'inline', 'bullet': None, 'custom': {'keep': True}}]}
    service, nested, project, content, stack = setup(tmp_path, deepcopy(original))
    items = rows(service, content)
    assert [item['mode'] for item in items] == ['reference', 'inline']
    assert all(item['form']['knownType'] for item in items)
    assert fields(items[0]['form'])['name']['control'] == 'reference'
    assert fields(items[0]['form'])['name']['displayValue'] == 'missing'
    assert fields(items[0]['form'])['rotateSpeed']['displayValue'] == 8
    assert 'reload' not in fields(items[0]['form'])
    assert fields(items[1]['form'])['name']['control'] == 'string'
    assert content.data == original and not stack.can_undo


def test_add_reference_inline_and_nested_bullet_edits_share_identity_history(tmp_path):
    service, nested, project, content, stack = setup(tmp_path)
    project.contents.save('gun', {'name': 'gun', 'bullet': {'damage': 9}}, 'weapons')
    apply(service, content, stack, 'weapon_add', field='weapons', mode='reference', name='probe-gun')
    assert content.data['weapons'][0] == {'name': 'probe-gun', 'x': 0.0, 'y': 0.0, 'reload': 1.0, 'top': True, 'rotate': False, 'mirror': True}
    first = rows(service, content)[0]['itemId']
    apply(service, content, stack, 'weapon_add', field='weapons', mode='inline', name='same', bulletType='LaserBulletType')
    inline = rows(service, content)[1]
    assert content.data['weapons'][1]['bullet'] == {'type': 'LaserBulletType', 'damage': 1.0, 'speed': 1.0}
    command = nested.command('set_field', content, PATH, {'objectPath': [*inline['objectPath'], 'bullet'], 'field': 'damage', 'text': '25'})
    stack.execute(command)
    assert content.data['weapons'][1]['bullet']['damage'] == 25
    stack.undo(); stack.undo()
    assert rows(service, content)[0]['itemId'] == first and len(content.data['weapons']) == 1
    stack.redo(); assert rows(service, content)[1]['itemId'] == inline['itemId']


def test_invalid_top_level_file_does_not_remove_valid_project_weapon_candidates(tmp_path):
    service, nested, project, content, stack = setup(tmp_path)
    project.contents.save('good', {'bullet': {'damage': 9}}, 'weapons')
    (project.contents.content_dir / 'weapons/broken.json').write_text('[]')
    result = service.weapon_reference_candidates(content, PATH, {'field': 'weapons', 'query': 'probe-good'})
    assert any(row['value'] == 'probe-good' for row in result['candidates'])
    apply(service, content, stack, 'weapon_add', field='weapons', mode='reference', name='probe-good')
    assert content.data['weapons'][0]['name'] == 'probe-good'


def test_weapon_spawned_unit_abilities_use_shared_recursive_budget_and_identity(tmp_path):
    from app.desktop.ability_forms import AbilityFormsService
    service, nested, project, content, stack = setup(tmp_path, {'type': 'flying', 'weapons': [
        {'name': 'inline', 'bullet': {'type': 'BasicBulletType', 'spawnUnit': {'type': 'flying',
            'abilities': [{'type': 'RegenAbility', 'amount': 1}]}}}]})
    nested = NestedFormService(nested.metadata, nested.forms)
    AbilityFormsService(nested)
    service = WeaponFormsService(nested, project)
    weapon = rows(service, content)[0]
    bullet = fields(weapon['form'])['bullet']['child']
    spawn = fields(bullet)['spawnUnit']['child']
    ability = fields(spawn)['abilities']['items'][0]
    address = ability['form']['objectPath']
    command = nested.command('set_field', content, PATH, {'objectPath': address, 'field': 'amount', 'text': '4'})
    stack.execute(command)
    assert content.data['weapons'][0]['bullet']['spawnUnit']['abilities'][0]['amount'] == 4
    stack.undo()
    again = fields(fields(fields(rows(service, content)[0]['form'])['bullet']['child'])['spawnUnit']['child'])['abilities']['items'][0]
    assert again['itemId'] == ability['itemId']
    assert content.data['weapons'][0]['bullet']['spawnUnit']['abilities'][0]['amount'] == 1


def test_explicit_expand_uses_only_weapon_category_and_usage_overrides_win(tmp_path):
    service, nested, project, content, stack = setup(tmp_path, {'type': 'tank', 'weapons': [{'name': 'probe-same', 'x': 7, 'reload': 4, 'custom': 3}]})
    project.contents.save('same', {'name': 'wrong-block', 'bullet': {'damage': 999}}, 'blocks')
    source = {'name': 'source-name', 'reload': 12, 'x': 1, 'bullet': {'type': 'BasicBulletType', 'damage': 8}}
    project.contents.save('same', source, 'weapons')
    item = rows(service, content)[0]
    original = deepcopy(content.data)
    apply(service, content, stack, 'weapon_expand', objectPath=item['objectPath'])
    assert content.data['weapons'][0] == {**source, 'x': 7, 'reload': 4, 'custom': 3}
    assert project.contents.get_by_path('weapons/same.json').data == source
    assert rows(service, content)[0]['itemId'] == item['itemId']
    stack.undo(); assert content.data == original
    stack.redo(); assert content.data['weapons'][0]['bullet']['damage'] == 8


def test_missing_definition_requires_explicit_blank_but_broken_source_never_falls_back(tmp_path):
    service, nested, project, content, stack = setup(tmp_path, {'type': 'mech', 'weapons': [{'name': 'missing', 'x': 8}]})
    item = rows(service, content)[0]
    with pytest.raises(ValueError, match='不存在'):
        apply(service, content, stack, 'weapon_expand', objectPath=item['objectPath'])
    assert not stack.can_undo
    apply(service, content, stack, 'weapon_expand', objectPath=item['objectPath'], allowBlank=True)
    assert content.data['weapons'][0]['bullet']['type'] == 'BasicBulletType'
    assert content.data['weapons'][0]['x'] == 8
    stack.undo()
    (project.root / 'content/weapons/missing.json').write_text('{ broken', encoding='utf-8')
    with pytest.raises(ValueError, match='读取|损坏'):
        apply(service, content, stack, 'weapon_expand', objectPath=item['objectPath'], allowBlank=True)
    assert content.data['weapons'][0] == {'name': 'missing', 'x': 8}


def test_same_name_items_move_and_edit_by_id_then_save_reopen_without_export_expansion(tmp_path):
    original = {'type': 'mech', 'weapons': [{'name': 'same', 'x': 1}, {'name': 'same', 'x': 2}]}
    service, nested, project, content, stack = setup(tmp_path, deepcopy(original))
    first, second = rows(service, content)
    apply(service, content, stack, 'weapon_move', field='weapons', itemId=first['itemId'], beforeItemId=None)
    stack.execute(nested.command('set_field', content, PATH, {'objectPath': first['objectPath'], 'field': 'x', 'value': 12}))
    assert [item['x'] for item in content.data['weapons']] == [2, 12]
    apply(service, content, stack, 'weapon_remove', field='weapons', itemId=second['itemId'])
    with pytest.raises(ValueError):
        nested.command('set_field', content, PATH, {'objectPath': second['objectPath'], 'field': 'x', 'value': 13})
    stack.undo(); assert [item['itemId'] for item in rows(service, content)] == [second['itemId'], first['itemId']]
    project.contents.save('unit', content.data, 'units')
    assert Project.open(project.root).contents.get_by_path('units/unit.json').data == content.data
    import zipfile
    archive = project.export_zip(tmp_path / 'result.zip')
    with zipfile.ZipFile(archive) as exported:
        assert json.loads(exported.read('content/units/unit.json')) == content.data
        assert all('bullet' not in value for value in json.loads(exported.read('content/units/unit.json'))['weapons'])


def test_reference_candidates_categories_aliases_and_name_edit_are_authoritative(tmp_path):
    service, nested, project, content, stack = setup(tmp_path, {'type': 'mech', 'weapons': [{'name': 'gun', 'x': 1}]})
    project.contents.save('gun', {'name': 'gun', 'bullet': {'damage': 1}}, 'weapons')
    project.contents.save('not-weapon', {}, 'blocks')
    item = rows(service, content)[0]
    choices = service.weapon_reference_candidates(content, PATH, {'objectPath': item['objectPath'], 'field': 'name', 'query': 'probe-'})
    assert choices['current'] == {'value': 'gun', 'label': 'gun', 'known': True}
    assert [row['value'] for row in choices['candidates']] == ['probe-gun']
    assert all(row['category'] == 'Weapons' for row in choices['candidates'])
    command = nested.command('set_field', content, PATH, {'objectPath': item['objectPath'], 'field': 'name', 'value': 'probe-gun'})
    stack.execute(command)
    assert content.data['weapons'][0]['name'] == 'probe-gun'
    with pytest.raises(ValueError):
        nested.command('set_field', content, PATH, {'objectPath': item['objectPath'], 'field': 'name', 'value': 'probe-not-weapon'})
    stack.undo(); assert content.data['weapons'][0]['name'] == 'gun'
    with pytest.raises(ValueError):
        service.weapon_reference_candidates(content, PATH, {'field': []})


def test_override_add_uses_current_allowlist_preserves_existing_data_and_undo(tmp_path):
    service, nested, project, content, stack = setup(tmp_path, {'type': 'mech', 'weapons': [{'name': 'missing', 'custom': True}]})
    item = rows(service, content)[0]
    available = {field['name'] for group in item['overrideGroups'] for field in group['fields']}
    assert {'x', 'rotateSpeed', 'mirror'} <= available
    assert 'bullet' not in available and 'name' not in available
    original = deepcopy(content.data)
    apply(service, content, stack, 'weapon_add_override', objectPath=item['objectPath'], field='rotateSpeed')
    assert content.data['weapons'][0]['rotateSpeed'] == 5.0
    assert fields(rows(service, content)[0]['form'])['rotateSpeed']['control'] == 'number'
    with pytest.raises(ValueError):
        apply(service, content, stack, 'weapon_add_override', objectPath=item['objectPath'], field='rotateSpeed')
    with pytest.raises(ValueError):
        apply(service, content, stack, 'weapon_add_override', objectPath=item['objectPath'], field='bullet')
    stack.undo(); assert content.data == original


@pytest.mark.parametrize('payload', [
    {'mode': 'other', 'name': 'x'}, {'mode': 'inline', 'name': '../outside'},
    {'mode': 'inline', 'name': ''}, {'mode': 'inline', 'name': 'x', 'bulletType': 'NoSuchBullet'},
    {'mode': 'reference', 'name': 'missing'}, {'mode': 'reference', 'name': 'probe-nonweapon'},
])
def test_invalid_add_preserves_document_state_and_history(tmp_path, payload):
    service, nested, project, content, stack = setup(tmp_path)
    project.contents.save('nonweapon', {}, 'blocks')
    service.plan(content, PATH)
    original, state = deepcopy(content.data), nested.snapshot(PATH)
    with pytest.raises(ValueError):
        apply(service, content, stack, 'weapon_add', field='weapons', **payload)
    assert content.data == original and nested.snapshot(PATH) == state and not stack.can_undo


def test_invalid_array_entry_depth_and_standalone_weapon_are_preserved(tmp_path):
    service, nested, project, content, stack = setup(tmp_path, {'type': 'mech', 'weapons': ['old-string', {'name': 'same', 'bullet': {}}]})
    items = rows(service, content)
    assert items[0]['mode'] == 'unsupported' and items[0]['notice']
    apply(service, content, stack, 'weapon_remove', field='weapons', itemId=items[0]['itemId'])
    stack.undo(); assert content.data['weapons'][0] == 'old-string'
    nested.MAX_DEPTH = 1
    descriptor = fields(service.plan(content, PATH))['weapons']
    assert descriptor['readOnly'] and not descriptor['canInsert']
    with pytest.raises(ValueError):
        apply(service, content, stack, 'weapon_add', field='weapons', mode='inline', name='blocked')
    nested.MAX_DEPTH = 12
    standalone = ContentData('same', 'weapons', {'name': 'same', 'bullet': {'damage': 2}})
    plan = service.plan(standalone, 'content/weapons/same.json')
    assert plan['knownType'] and fields(plan)['name']['readOnly']
    assert fields(plan)['bullet']['child']['knownType']


def test_real_vanilla_nonfinite_source_is_rejected_without_silent_cleaning(tmp_path):
    service, nested, project, content, stack = setup(tmp_path, {'type': 'mech', 'weapons': [{'name': 'beam-weapon', 'x': 2}]})
    item = rows(service, content)[0]
    with pytest.raises(ValueError, match='非有限 JSON 数字.*beam-weapon'):
        apply(service, content, stack, 'weapon_expand', objectPath=item['objectPath'])
    assert content.data['weapons'] == [{'name': 'beam-weapon', 'x': 2}] and not stack.can_undo


def test_source_without_bullet_and_unsafe_source_are_not_fake_inline_success(tmp_path):
    service, nested, project, content, stack = setup(tmp_path, {'type': 'mech', 'weapons': [{'name': 'empty'}]})
    project.contents.save('empty', {'name': 'empty', 'x': 1}, 'weapons')
    item = rows(service, content)[0]
    with pytest.raises(ValueError, match='没有内联子弹'):
        apply(service, content, stack, 'weapon_expand', objectPath=item['objectPath'])
    other = ContentData('unit', 'units', {'type': 'mech', 'weapons': [{'name': '../outside'}]})
    invalid = rows(service, other)[0]
    assert not invalid['canExpand'] and not invalid['canCreateBlank']
    with pytest.raises(ValueError):
        apply(service, other, stack, 'weapon_expand', objectPath=invalid['objectPath'], allowBlank=True)
    assert not stack.can_undo


def test_recursive_weapons_share_nested_ids_and_commands(tmp_path):
    service, nested, project, content, stack = setup(tmp_path, {'type': 'mech', 'weapons': [{
        'name': 'outer', 'bullet': {'spawnUnit': {'type': 'mech',
                                               'weapons': [{'name': 'inner', 'bullet': {'damage': 3}}]}}}]})
    outer = rows(service, content)[0]
    bullet = fields(outer['form'])['bullet']['child']
    spawned = fields(bullet)['spawnUnit']['child']
    inner = fields(spawned)['weapons']['items'][0]
    stack.execute(nested.command('set_field', content, PATH, {'objectPath': [*inner['objectPath'], 'bullet'], 'field': 'damage', 'value': 8}))
    assert content.data['weapons'][0]['bullet']['spawnUnit']['weapons'][0]['bullet']['damage'] == 8
    stack.undo()
    refreshed = fields(fields(rows(service, content)[0]['form'])['bullet']['child'])['spawnUnit']['child']
    assert fields(refreshed)['weapons']['items'][0]['itemId'] == inner['itemId']
