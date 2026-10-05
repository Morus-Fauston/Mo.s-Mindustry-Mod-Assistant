"""Read-only descriptors for the existing preview effects; no GUI or clocks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.core.content_store import ContentData
from app.core.config_loader import get_field_names_zh
from app.core.preview_math import HEALTH_LEVELS, PPU, TEAM_COLORS, direction_degrees
from app.core.project import Project
from app.desktop.preview import PreviewService, WeaponPreviewResolver


class DynamicPreviewService:
    """Reuse the scene's resource registry, budgets and authoritative identities."""

    MAX_TREAD_FRAMES = 64

    def __init__(self, project: Project, load_resource: Callable[[Path], dict]):
        self._project = project
        self._load_resource = load_resource
        self._resolver = WeaponPreviewResolver(project)

    def describe(self, content: ContentData, scene: dict) -> dict:
        if (not isinstance(content, ContentData) or not isinstance(content.data, dict)
                or content.category not in ('units', 'blocks', 'weapons')):
            raise ValueError('动态预览内容无效')
        PreviewService._name(content.name)
        root = self._project.root.resolve()
        expected = root / 'content' / content.category / f'{content.name}.json'
        if (not expected.resolve().is_relative_to(root)
                or content.path is not None and content.path.resolve() != expected.resolve()):
            raise ValueError('动态预览内容不属于当前工程')
        descriptor = {
            'supported': bool(scene['width'] > 0 and scene['height'] > 0),
            'notices': [], 'recoilTime': 10.0, 'cooldownTime': 20.0,
            'teams': [{'value': key, 'label': key, 'color': value} for key, value in TEAM_COLORS.items()],
            'healthLevels': [{'value': key, 'label': key, 'fraction': value} for key, value in HEALTH_LEVELS.items()],
            'directions': [{'value': key, 'label': key, 'degrees': direction_degrees(key)} for key in ('上', '右', '下', '左')],
            'weapons': [], 'engine': None, 'teamLayerKeys': [], 'cellLayerKeys': [],
            'heat': None, 'treads': None,
            'flash': {'radius': max(3.0, min(scene['width'], scene['height']) / 8), 'color': '#fff3a1', 'z': 20},
            'colorize': 'qt-colorize-strength-1',
        }
        if not descriptor['supported']:
            return descriptor
        notices = descriptor['notices']
        data = content.data
        names = get_field_names_zh()
        descriptor['recoilTime'] = max(1, self._number(data.get('recoilTime', 10), 10, names.get('recoilTime', 'recoilTime'), notices))
        descriptor['cooldownTime'] = max(1, self._number(data.get('cooldownTime', 20), 20, names.get('cooldownTime', 'cooldownTime'), notices))
        center = (scene['width'] / 2, scene['height'] / 2)
        identities = {}
        for node in scene.get('tree', []):
            for child in node.get('children', []):
                for key in child.get('drawableKeys', []):
                    identities[key] = child['id']
        weapons = data.get('weapons', [])
        if isinstance(weapons, list):
            if len(weapons) > PreviewService.MAX_WEAPONS:
                notices.append('武器数量超过动态预览上限，超出部分保持静态。')
            for index, weapon in enumerate(weapons[:PreviewService.MAX_WEAPONS]):
                if not isinstance(weapon, dict):
                    continue
                try:
                    if weapon.get('name'):
                        x, y = self._resolver.coordinates(weapon)
                    else:
                        x, y = (self._resolver.number(weapon.get(axis) or 0) for axis in ('x', 'y'))
                except (ValueError, OSError, TypeError, OverflowError, RecursionError):
                    notices.append(f'武器 {index + 1}：安装坐标无效，已保留静态预览。')
                    continue
                key = f'__weapon_{index}__'
                descriptor['weapons'].append({
                    'nodeId': identities.get(key, 'group:weapons'), 'layerKeys': [key],
                    'recoilDistance': self._number(weapon.get('recoil', 1), 1, f"武器 {index + 1} {names.get('recoil', 'recoil')}", notices),
                    'recoilPower': max(0, self._number(weapon.get('recoilPow', 1.8), 1.8, f"武器 {index + 1} {names.get('recoilPow', 'recoilPow')}", notices)),
                    'flashCenter': {'x': center[0] + x * PPU, 'y': center[1] - y * PPU},
                })
        else:
            notices.append('武器资料不是数组，已保留静态预览。')
        descriptor['treads'] = self._treads(content, scene, notices)
        descriptor['heat'] = self._heat(content, center, notices)
        descriptor['teamLayerKeys'] = [layer['key'] for layer in scene['layers'] if layer['key'] == '-team']
        descriptor['cellLayerKeys'] = [layer['key'] for layer in scene['layers'] if layer['key'] == '-cell']
        engine_indices = [index for index, circle in enumerate(scene['circles']) if circle['key'] == '__engine__']
        if len(engine_indices) == 2:
            size = self._number(data.get('engineSize', 0), 0, names.get('engineSize', 'engineSize'), notices)
            if size > 0:
                descriptor['engine'] = {'nodeId': 'engine', 'outerIndex': engine_indices[0],
                    'innerIndex': engine_indices[1], 'size': size}
        return descriptor

    def _heat(self, content, center, notices):
        path = self._project.sprite_path(content.category, content.name, '-heat')
        try:
            if not path.exists():
                return None
            resource = self._load_resource(path)
        except (ValueError, OSError) as exc:
            notices.append(f'热图：{exc}；已保留静态预览。')
            return None
        return {'nodeId': 'sprite:-heat', 'key': '__heat__', 'resourceId': resource['resourceId'],
            'x': center[0] - resource['width'] / 2, 'y': center[1] - resource['height'] / 2,
            'width': resource['width'], 'height': resource['height'], 'z': 12,
            'flipX': False, 'tooltip': '热图', 'color': '#ff795e'}

    def _treads(self, content, scene, notices):
        layer = next((layer for layer in scene['layers'] if layer['key'] == '-treads'), None)
        if layer is None:
            return None
        count = max(1, int(self._number(content.data.get('treadFrames', 18), 18,
            get_field_names_zh().get('treadFrames', 'treadFrames'), notices)))
        if count > self.MAX_TREAD_FRAMES:
            notices.append('履带帧数超过预览上限，仅加载前 64 个候选帧。')
            count = self.MAX_TREAD_FRAMES
        frames = []
        for index in range(count):
            path = self._project.sprite_path(content.category, content.name, f'-treads0-{index}')
            try:
                if not path.exists():
                    continue
                resource = self._load_resource(path)
                frames.append({key: resource[key] for key in ('resourceId', 'width', 'height')})
            except (ValueError, OSError) as exc:
                notices.append(f'履带第 {index + 1} 帧：{exc}；不可用时保留静态贴图。')
        if not frames:
            return None
        return {'nodeId': layer.get('nodeId', 'sprite:-treads'), 'layerKey': '-treads', 'frames': frames}

    def _number(self, value, fallback, label, notices):
        try:
            return self._resolver.number(value)
        except (ValueError, TypeError, OverflowError):
            notices.append(f'{label}无效，预览已使用默认值。')
            return fallback
