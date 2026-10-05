"""Legacy weapon cards on the shared document, nested addresses and history."""

from copy import deepcopy
import json
import re
from uuid import uuid4

from app.core.commands import ArrayInsertCommand, ArrayMoveCommand, ArrayRemoveCommand
from app.core.config_loader import display_name, get_field_docs, get_field_groups, get_field_names_zh
from app.core.content_store import ContentData
from app.core.form_labels import GROUP_LABELS
from app.core.form_plan import type_default
from app.core.form_types import BULLET_TYPES, TYPE_LABELS
from app.desktop.forms import FormService, json_values_equal
from app.desktop.nested_forms import _NestedCommand, _NodeForms
from app.desktop.preview import WeaponPreviewResolver


_REFERENCE_FIELDS = ('x', 'y', 'reload', 'top', 'rotate', 'mirror')
_OVERRIDE_DEFAULTS = {
    'x': 0.0, 'y': 0.0, 'shootX': 0.0, 'shootY': 0.0, 'reload': 1.0,
    'top': True, 'rotate': False, 'mirror': True, 'alternate': True,
    'rotateSpeed': 5.0, 'shootCone': 15.0, 'inaccuracy': 0.0,
    'controllable': True, 'aiControllable': True, 'shots': 1, 'shotDelay': 5.0,
    'recoil': 1.0, 'recoilTime': 20.0, 'shake': 0.0, 'velocityRnd': 0.0,
    'cooldownTime': 30.0, 'autoTarget': False, 'predictTarget': True,
    'targetInterval': 40, 'continuous': False, 'alwaysContinuous': False,
    'shootSoundVolume': 0.5, 'layerOffset': 0.0, 'shadow': 0.0,
}


def _name(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 255
            or value in ('.', '..') or re.search(r'[\\/:\x00-\x1f<>"|?*]', value)):
        raise ValueError('武器名称必须是有效的文件名或武器标识。')
    return value


class _WeaponNodeForms(_NodeForms):
    def __init__(self, original, reference, coordinates):
        super().__init__(original.metadata, original.references, original.kind, original.definition)
        self.reference = reference
        self.coordinates = coordinates

    def project(self, plan, content):
        effective = None
        if self.reference and any(name not in content.data for name in ('x', 'y')):
            try:
                effective = self.coordinates(content.data)
            except (OSError, ValueError, TypeError, RecursionError, OverflowError):
                # Keep the card readable when a referenced file cannot supply
                # coordinates; never present a fabricated zero as its value.
                pass
        for group in plan['groups']:
            for descriptor in group['fields']:
                if descriptor['name'] == 'name':
                    descriptor.update(control='reference' if self.reference else 'string', readOnly=False,
                                      displayValue=deepcopy(content.data.get('name', '')), fieldType='ref' if self.reference else 'str',
                                      nullable=False, deletable=False)
                    if self.reference:
                        descriptor.update(mode='STRING_REF', refSource='Weapons', categories=['Weapons'])
                if self.reference and descriptor['name'] in ('x', 'y') and not descriptor['present']:
                    value = effective[0 if descriptor['name'] == 'x' else 1] if effective is not None else None
                    descriptor.update(displayValue=value, defaultValue=value, defaultSource='引用武器有效坐标')
                    if effective is None:
                        descriptor.update(readOnly=True, validationError='引用武器坐标读取失败，请先修复武器定义。')
            if self.reference:
                group['fields'] = [field for field in group['fields'] if field['name'] in ('name', 'x', 'y') or field['name'] in content.data]
                group.update(locked=True, addableFields=[])
        if self.reference:
            plan['groups'] = [group for group in plan['groups'] if group['fields']]
            plan['addableGroups'] = []
        return plan

    def plan(self, content, path):
        return self.project(super().plan(content, path), content)

    def parse(self, content, path, payload):
        value = super().parse(content, path, payload)
        if payload.get('field') == 'name':
            # Preserve an already-stored legacy spelling on a no-op, but do not
            # create a path-like new reference or inline sprite name.
            if not json_values_equal(value, content.data.get('name')):
                _name(value)
        return value


class WeaponFormsService:
    def __init__(self, nested, project):
        self.nested, self.project = nested, project
        self._coordinates = WeaponPreviewResolver(project).coordinates if project is not None else lambda _: (0.0, 0.0)
        self._arrays = {}
        self._entries = {}
        self._vanilla = frozenset(nested.metadata.list_instances('Weapons'))
        nested.register_plan_extension(self._augment)

    def _augment(self, content, path, state, plan, nodes, budget):
        self._arrays, self._entries = {}, {}
        visited = set()
        while True:
            pending = [(key, node) for key, node in nodes.items() if key not in visited]
            if not pending:
                return
            for key, (data, forms, document, node, scalar) in pending:
                visited.add(key)
                if not node['knownType'] or scalar is not None:
                    continue
                definition = next((field for field in forms.definition.fields if field.name == 'weapons'
                                   and field.mode == 'ARRAY' and field.element_type == 'Weapon'), None)
                if definition is None:
                    continue
                for group in node['groups']:
                    for descriptor in group['fields']:
                        if descriptor['name'] == 'weapons':
                            self._array(data, descriptor, node['objectPath'], content, path, state, nodes, budget)

    def _array(self, data, descriptor, owner, content, path, state, nodes, budget):
        address = [*owner, 'weapons']
        values = data.get('weapons')
        descriptor.update(control='weapon_array', objectPath=address, items=[], readOnly=False,
                          canInsert=False, canRemove=False, canMove=False,
                          bulletTypes=[{'value': kind, 'label': TYPE_LABELS[kind]} for kind in BULLET_TYPES])
        self._arrays[(self.nested._key(owner), 'weapons')] = (data, descriptor)
        if values is not None and not isinstance(values, list):
            descriptor.update(readOnly=True, validationError='武器数组格式无效，原值已保留。')
            return
        values = values if values is not None else []
        if (len(address) >= self.nested.MAX_DEPTH or len(values) > self.nested.MAX_ARRAY_ITEMS
                or len(values) > budget[0]):
            descriptor.update(readOnly=True, validationError='武器表单显示已达上限，原值已保留。')
            return
        key = self.nested._key(address)
        budget[1].add(key)
        ids = state.item_ids.get(key)
        if ids is None or len(ids) != len(values):
            ids = [uuid4().hex for _ in values]
            state.item_ids[key] = ids
        descriptor.update(canInsert=len(values) < self.nested.MAX_ARRAY_ITEMS, canRemove=bool(values), canMove=len(values) > 1)
        for index, (value, item_id) in enumerate(zip(values, ids)):
            item_address = [*address, {'itemId': item_id}]
            item = {'itemId': item_id, 'index': index, 'objectPath': item_address,
                    'mode': 'unsupported', 'canExpand': False, 'canCreateBlank': False}
            descriptor['items'].append(item)
            if not isinstance(value, dict):
                budget[0] -= 1
                item['notice'] = '此武器项不是对象，原值已保留。'
                continue
            reference = 'bullet' not in value
            child = self.nested._object(value, 'Weapon', item_address, content, path, state, nodes, budget)
            item.update(mode='reference' if reference else 'inline', form=child)
            item_key = self.nested._key(item_address)
            if item_key not in nodes or not child['knownType']:
                continue
            child_data, original_forms, document, _, scalar = nodes[item_key]
            forms = _WeaponNodeForms(original_forms, reference, self._coordinates)
            forms.restore(item_key, original_forms.snapshot(item_key))
            forms.project(child, document)
            nodes[item_key] = (child_data, forms, document, child, scalar)
            self._entries[item_key] = (values, index, item, forms)
            if reference:
                item['overrideGroups'] = self._overrides(value, forms)
                try:
                    present = self._source_presence(value.get('name'))
                    item.update(canExpand=present, canCreateBlank=not present)
                    if not present:
                        item['notice'] = '未找到武器定义，可保留引用或明确创建空白内联。'
                except (OSError, ValueError) as exc:
                    item['notice'] = str(exc)

    def _overrides(self, data, forms):
        names, docs = get_field_names_zh(), get_field_docs()
        definitions = {field.name: field for field in forms.definition.fields}
        groups = []
        seen = set()
        for group_name, configuration in get_field_groups().get('Weapon', {}).items():
            if group_name == 'bullet':
                continue
            fields = []
            candidates = [*(_REFERENCE_FIELDS if group_name == 'basic' else ()), *configuration.get('optional', [])]
            for name in candidates:
                if name in seen or name in data or name not in definitions:
                    continue
                seen.add(name)
                definition = definitions[name]
                control = FormService.control(definition, configuration)
                if control not in ('number', 'boolean', 'string', 'color', 'reference'):
                    continue
                value = deepcopy(_OVERRIDE_DEFAULTS.get(name, definition.default if definition.default is not None else type_default(definition)))
                probe = {'control': control, 'javaType': definition.java_type, 'nullable': definition.nullable}
                try:
                    FormService.validate(probe, value)
                except ValueError:
                    continue
                fields.append({'name': name, 'label': display_name(name, names), 'help': docs.get(name, ''), 'defaultValue': value})
            if fields:
                groups.append({'id': group_name, 'label': GROUP_LABELS.get(group_name, group_name), 'fields': fields})
        return groups

    def _source_path(self, name):
        name = _name(name)
        if self.project is None:
            return None
        prefix = self.project.mod_info.name + '-'
        local = name[len(prefix):] if name.startswith(prefix) else name
        _name(local)
        target = self.project.root / 'content' / 'weapons' / f'{local}.json'
        root = self.project.root.resolve()
        if not target.resolve().is_relative_to(root / 'content' / 'weapons'):
            raise ValueError('武器定义路径超出当前工程范围。')
        return target

    def _source_presence(self, name):
        target = self._source_path(name)
        return bool(target is not None and target.exists() or name in self._vanilla)

    def _source(self, name):
        target = self._source_path(name)
        if target is not None and target.exists():
            try:
                if not target.is_file() or target.stat().st_size > self.nested.MAX_DOCUMENT_BYTES:
                    raise ValueError('武器定义不是普通文件或超过大小上限。')
                value = self.project.contents.get_by_path(f'weapons/{target.stem}.json').data
            except (OSError, ValueError, RecursionError) as exc:
                raise ValueError('武器定义读取失败或数据损坏，不能改为空白内联。') from exc
            self._source_json(value, target.relative_to(self.project.root).as_posix())
            return deepcopy(value)
        if name not in self._vanilla:
            return None
        try:
            value = self.nested.metadata.get_instance('Weapons', name)
            if not isinstance(value, dict):
                raise ValueError('武器定义不是对象。')
        except (OSError, ValueError, KeyError, RecursionError) as exc:
            raise ValueError('原版武器定义读取失败或数据损坏。') from exc
        self._source_json(value, f'metadata/instances/Weapons/{name}.json')
        return deepcopy(value)

    def _source_json(self, value, location):
        try:
            raw = json.dumps(value, allow_nan=False, ensure_ascii=False)
        except ValueError as exc:
            raise ValueError(f'武器定义含非有限 JSON 数字，无法安全展开：{location}。') from exc
        except (TypeError, RecursionError) as exc:
            raise ValueError(f'武器定义格式无效或嵌套过深：{location}。') from exc
        if len(raw.encode('utf-8')) > self.nested.MAX_DOCUMENT_BYTES:
            raise ValueError(f'武器定义超过大小上限：{location}。')

    def plan(self, content, path):
        return self.nested.plan(content, path)

    def weapon_reference_candidates(self, content, path, payload):
        address = self.nested._address(payload)
        if not isinstance(payload.get('field'), str):
            raise ValueError('武器字段名称无效。')
        state = self.nested.snapshot(path)
        self.nested._build(content, path, state)
        key = self.nested._key(address)
        current = None
        if key in self._entries and self._entries[key][2]['mode'] == 'reference':
            if payload.get('field') != 'name':
                raise ValueError('请选择武器引用名称。')
            values, index, _, _ = self._entries[key]
            current = values[index].get('name')
        elif (key, payload.get('field')) not in self._arrays:
            raise ValueError('武器数组或条目已失效。')
        descriptor = {'control': 'reference', 'categories': ['Weapons'], 'nullable': False}
        result = self.nested.forms.references.read(descriptor, current, payload.get('query', ''))
        if current and not result['current']['known']:
            try:
                result['current']['known'] = self._source_presence(current)
            except ValueError:
                pass
        self.nested.restore(path, state)
        return result

    reference_candidates = weapon_reference_candidates

    def command(self, action, content, path, payload):
        address = self.nested._address(payload)
        before = self.nested.snapshot(path)
        self.nested._build(content, path, before)
        draft = ContentData(content.name, content.category, deepcopy(content.data), content.path)
        after = deepcopy(before)
        self.nested._build(draft, path, after)
        key = self.nested._key(address)
        if action in ('weapon_add', 'weapon_remove', 'weapon_move'):
            field = payload.get('field')
            if not isinstance(field, str) or (key, field) not in self._arrays:
                raise ValueError('武器数组已失效。')
            data, descriptor = self._arrays[(key, field)]
            if descriptor['readOnly']:
                raise ValueError('此武器数组不可编辑。')
            ids = after.item_ids[self.nested._key([*address, field])]
            if action == 'weapon_add':
                if not descriptor['canInsert']:
                    raise ValueError('武器数量已达上限。')
                name = _name(payload.get('name'))
                mode = payload.get('mode')
                if mode == 'reference':
                    self.nested.forms.references.validate({'control': 'reference', 'categories': ['Weapons'], 'nullable': False}, name, None)
                    value = {'name': name, 'x': 0.0, 'y': 0.0, 'reload': 1.0, 'top': True, 'rotate': False, 'mirror': True}
                elif mode == 'inline':
                    bullet = payload.get('bulletType', 'BasicBulletType')
                    if bullet not in BULLET_TYPES:
                        raise ValueError('请选择支持的子弹类型。')
                    value = {'name': name, 'reload': 1.0, 'x': 0.0, 'y': 0.0,
                             'bullet': {'type': bullet, 'damage': 1.0, 'speed': 1.0}}
                else:
                    raise ValueError('请选择引用或内联添加方式。')
                anchor = payload.get('beforeItemId')
                if anchor is not None and anchor not in ids:
                    raise ValueError('武器插入位置已失效。')
                index = len(ids) if anchor is None else ids.index(anchor)
                if data.get(field) is None:
                    data[field] = []
                ArrayInsertCommand(data, field, index, value).execute()
                ids.insert(index, uuid4().hex)
            else:
                item_id = payload.get('itemId')
                if not isinstance(item_id, str) or item_id not in ids:
                    raise ValueError('武器条目已失效。')
                index = ids.index(item_id)
                if action == 'weapon_remove':
                    ArrayRemoveCommand(data, field, index).execute()
                    ids.pop(index)
                else:
                    if 'beforeItemId' not in payload:
                        raise ValueError('请指定武器移动位置。')
                    anchor = payload['beforeItemId']
                    if anchor == item_id:
                        return None
                    if anchor is not None and anchor not in ids:
                        raise ValueError('武器移动位置已失效。')
                    remaining = [value for value in ids if value != item_id]
                    destination = len(remaining) if anchor is None else remaining.index(anchor)
                    if destination == index:
                        return None
                    ArrayMoveCommand(data, field, index, destination).execute()
                    ids.insert(destination, ids.pop(index))
        elif action in ('weapon_add_override', 'weapon_expand'):
            if key not in self._entries:
                raise ValueError('武器条目已失效或不可编辑。')
            values, index, item, _ = self._entries[key]
            if item['mode'] != 'reference':
                raise ValueError('此操作只适用于已有武器引用。')
            if action == 'weapon_add_override':
                candidates = [field for group in item['overrideGroups'] for field in group['fields']]
                selected = next((field for field in candidates if field['name'] == payload.get('field')), None)
                if selected is None:
                    raise ValueError('此覆盖字段不能添加或已经存在。')
                values[index][selected['name']] = deepcopy(selected['defaultValue'])
            else:
                allow_blank = payload.get('allowBlank', False)
                if type(allow_blank) is not bool:
                    raise ValueError('创建空白内联需要明确确认。')
                original = values[index]
                source = self._source(original.get('name'))
                if source is None:
                    if not allow_blank:
                        raise ValueError('武器定义不存在；创建空白内联需要明确确认。')
                    source = {'name': original['name'], 'reload': 1.0,
                              'bullet': {'type': 'BasicBulletType', 'damage': 1.0, 'speed': 1.0}}
                if 'bullet' not in source:
                    raise ValueError('源武器没有内联子弹定义，不能将引用冒充内联展开。')
                source.update({name: deepcopy(value) for name, value in original.items() if name != 'name'})
                values[index] = source
        else:
            raise ValueError('不支持此武器操作。')
        _, nodes = self.nested._build(draft, path, after)
        if not nodes:
            raise ValueError('武器修改超出文档大小上限，原值已保留。')
        if json_values_equal(content.data, draft.data) and before == after:
            return None
        return _NestedCommand(self.nested, path, content.data, draft.data, before, after, '修改武器')
