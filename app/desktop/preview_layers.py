"""Read-only layer tree over a scene and the current authoritative form plan."""

from copy import deepcopy
import re

from app.core.config_loader import get_sprite_layers, get_field_names_zh, get_field_docs
from app.core.metadata import normalize_content_type
from app.desktop.preview import PreviewService, WeaponPreviewResolver


def _fields(plan):
    return {field['name']: field for group in plan.get('groups', []) for field in group['fields']}


class PreviewLayerService:
    def __init__(self, project):
        self.project = project
        self._resolver = WeaponPreviewResolver(project)

    def decorate(self, scene, content, form, path, revision):
        result = deepcopy(scene)
        result.update(path=path, revision=revision, tree=[])
        subtype = content.data.get('type', {'units': 'UnitType', 'weapons': 'Weapon'}.get(content.category, 'Block'))
        kind = normalize_content_type(subtype) if isinstance(subtype, str) else ''
        config = get_sprite_layers().get(kind, [{'suffix': '', 'label': '主体', 'required': True}])
        drawn = {layer['key'] for layer in result['layers']}
        for layer in config:
            if layer.get('visible_for') and subtype not in layer['visible_for']:
                continue
            suffix = layer['suffix']
            exists = self.project.sprite_path(content.category, content.name, suffix).is_file()
            # The scene attempted every existing overlay only after loading the
            # body. A present but rejected PNG must not look like a ready layer.
            # When the body is missing, overlays were not attempted: keep their
            # file availability, while explaining why there is no drawing yet.
            attempted = not suffix or '' in drawn
            invalid = exists and attempted and suffix not in drawn
            node = {'id': f'sprite:{suffix}', 'kind': 'sprite', 'label': layer['label'],
                    'status': 'invalid' if invalid else 'ready' if exists else 'missing' if layer.get('required') else 'optional',
                    'drawableKeys': [suffix]}
            if invalid:
                node['notice'] = next((message for message in result['warnings']
                                       if message.startswith(f"{layer['label']}：")),
                                      '贴图加载失败，请检查图片格式、尺寸与访问权限。')
            elif exists and not attempted:
                node['notice'] = '主体贴图不可用，此图层尚未绘制。'
            result['tree'].append(node)
        weapon_ids = self._weapons(content, form, result)
        for layer in result['layers']:
            match = re.fullmatch(r'__weapon_(\d+)__', layer['key'])
            layer['nodeId'] = weapon_ids.get(int(match[1]), 'group:weapons') if match else f"sprite:{layer['key']}"
            if match and int(match[1]) not in weapon_ids:
                group = next((node for node in result['tree'] if node['id'] == 'group:weapons'), None)
                if group is None:
                    group = {'id': 'group:weapons', 'kind': 'weapon-group', 'label': get_field_names_zh().get('weapons', '武器'),
                             'status': 'invalid', 'notice': '此武器数组不可编辑，原值已保留。', 'children': []}
                    result['tree'].append(group)
                keys = group.setdefault('drawableKeys', [])
                if layer['key'] not in keys:
                    keys.append(layer['key'])
        size = content.data.get('engineSize', 0)
        try:
            has_engine = self._resolver.number(size) > 0
        except ValueError:
            has_engine = False
        if result['circles'] or content.category == 'units' and has_engine:
            result['tree'].append({'id': 'engine', 'kind': 'engine', 'label': '引擎示意',
                'status': 'ready' if result['circles'] else 'missing',
                'drawableKeys': list(dict.fromkeys(circle['key'] for circle in result['circles']))})
        for circle in result['circles']:
            circle['nodeId'] = 'engine'
        return result

    def _weapons(self, content, form, result):
        field = _fields(form).get('weapons')
        values = content.data.get('weapons', [])
        if content.category != 'units' or values is None or values == []:
            return {}
        children, identities = [], {}
        group = {'id': 'group:weapons', 'kind': 'weapon-group',
                 'label': get_field_names_zh().get('weapons', '武器'), 'children': children}
        result['tree'].append(group)
        if (not isinstance(values, list) or not field or field.get('control') != 'weapon_array'
                or field.get('readOnly')):
            group.update(status='invalid', notice=(field or {}).get('validationError') or '此武器数组不可编辑，原值已保留。')
            return identities
        if len(field['items']) > PreviewService.MAX_WEAPONS:
            group['notice'] = '武器数量超过预览上限，部分武器未显示。'
        for item in field['items'][:PreviewService.MAX_WEAPONS]:
            index = item['index']
            node_id = f"weapon:{item['itemId']}"
            value = values[index]
            label = value.get('name') if isinstance(value, dict) else None
            node = {'id': node_id, 'kind': 'weapon', 'label': label if isinstance(label, str) and label else f'第 {index + 1} 项',
                    'status': 'ready' if any(layer['key'] == f'__weapon_{index}__' for layer in result['layers']) else 'missing',
                    'drawableKeys': [f'__weapon_{index}__']}
            if item.get('form', {}).get('knownType') and isinstance(value, dict):
                descriptors = _fields(item['form'])
                node['weapon'] = {'itemId': item['itemId'], 'objectPath': deepcopy(item['objectPath']),
                    'coordinates': self._coordinates(value, descriptors, node)}
            else:
                node.update(status='invalid', notice=item.get('notice') or '此武器项不能编辑安装坐标。')
            children.append(node)
            identities[index] = node_id
        return identities

    def _coordinates(self, value, descriptors, node):
        names, docs = get_field_names_zh(), get_field_docs()
        effective, error = {}, ''
        try:
            effective = dict(zip(('x', 'y'), self._resolver.coordinates(value)))
        except (ValueError, OSError, TypeError, OverflowError, RecursionError):
            error = '安装坐标或引用武器资料无效，请检查参数和武器定义。'
            node.update(status='invalid', notice=error)
        coordinates = {}
        for name in ('x', 'y'):
            if name in descriptors:
                descriptor = deepcopy(descriptors[name])
                if value.get(name) is None and name in effective:
                    descriptor['displayValue'] = effective[name]
            else:
                # An absent form route is not permission to write it. The caller
                # must expose a real parser-backed field before this is editable.
                descriptor = {'name': name, 'label': names.get(name, name), 'help': docs.get(name, ''),
                    'control': 'number', 'fieldType': 'num', 'javaType': 'float', 'mode': 'PRIMITIVE',
                    'nullable': False, 'readOnly': True, 'deletable': False,
                    'present': name in value, 'value': deepcopy(value.get(name)),
                    'displayValue': effective.get(name, value.get(name)), 'defaultValue': effective.get(name),
                    'defaultSource': '引用武器坐标', 'inactiveReason': '', 'validationError': error}
            coordinates[name] = descriptor
        return coordinates
