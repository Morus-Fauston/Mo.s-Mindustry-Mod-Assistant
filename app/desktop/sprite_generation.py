"""Session-owned previews over existing Pillow generators and resource commands."""
from __future__ import annotations

import base64
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
import logging
import math
import os
from pathlib import Path
import re
import warnings
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from app.core.commands import Command
from app.core.config_loader import get_sprite_layers
from app.core.project_files import open_project_file
from app.core.resource_commands import ResourceCommand
from app.core.sprite_generator import generate_full, generate_outline, generate_shadow
from app.core.sprite_io import canonical_png_bytes


class GeneratedResourcesCommand(Command):
    """One history entry; failed forward or reverse batches restore prior bytes."""
    def __init__(self, commands, on_change=None, validate_sources=None, validate_outputs=None):
        self._commands, self._on_change = commands, on_change
        self._validate_sources = validate_sources
        self._validate_outputs = validate_outputs

    @property
    def snapshot_bytes(self):
        return sum(command.snapshot_bytes for command in self._commands)

    @property
    def description(self):
        return '生成贴图 ' + '、'.join(command.target.name for command in self._commands)

    def execute(self):
        self._apply(False)

    def undo(self):
        self._apply(True)

    def _apply(self, undo):
        ordered = list(reversed(self._commands)) if undo else self._commands
        completed = []
        try:
            if self._validate_outputs:
                self._validate_outputs(undo)
            if not undo and self._validate_sources:
                self._validate_sources()
            for command in ordered:
                (command.undo if undo else command.execute)()
                completed.append(command)
            if not undo and self._validate_sources:
                self._validate_sources()
        except Exception as failure:
            rollback_errors = []
            for command in reversed(completed):
                try:
                    (command.execute if undo else command.undo)()
                except Exception as rollback_error:
                    rollback_errors.append(f'{command.target.name}：{rollback_error}')
            if rollback_errors:
                raise OSError('生成批次失败，部分文件回滚失败，请保留当前会话并检查文件：' + '；'.join(rollback_errors)) from failure
            raise
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                logging.getLogger(__name__).exception('贴图已生成，刷新通知失败')


@dataclass
class Candidate:
    path: str
    content: str
    dependencies: dict
    full: bool
    outputs: list

    @property
    def cache_bytes(self):
        return (len(self.content) + len(self.path) + len(json.dumps(self.dependencies))
                + sum(len(output['before'] or b'') + len(output['after'])
                      + len(output['public']['dataUrl']) for output in self.outputs))


class SpriteGenerationService:
    MAX_FILE_BYTES = 16 * 1024 * 1024
    MAX_PIXELS = 8 * 1024 * 1024
    MAX_DIMENSION = 8192
    MAX_TOTAL_PIXELS = 16 * 1024 * 1024
    MAX_SEARCH_ENTRIES = 10000
    MAX_WEAPONS = 128
    MAX_CANDIDATES = 4
    MAX_CANDIDATE_BYTES = 64 * 1024 * 1024

    def __init__(self, project, resources, session_id, *, content_resolver=None, on_change=None):
        self._project, self._resources, self._session_id = project, resources, session_id
        self._content_resolver, self._on_change = content_resolver, on_change
        self._candidates: dict[str, Candidate] = {}
        self._closed = False
        self._root = project.root.resolve()

    def _ready(self):
        if self._closed:
            raise ValueError('贴图生成会话已关闭')

    def _specs(self, outputs, targets):
        if not isinstance(outputs, list) or not 1 <= len(outputs) <= 3:
            raise ValueError('请选择一至三种生成结果')
        supported = {row['suffix'] for row in targets} & {'-outline', '-shadow', '-full'}
        seen = set()
        for spec in outputs:
            if (not isinstance(spec, dict) or set(spec) - {'suffix', 'options'}
                    or not isinstance(spec.get('suffix'), str) or spec['suffix'] not in supported
                    or spec['suffix'] in seen or not isinstance(spec.get('options', {}), dict)):
                raise ValueError('生成类型或参数无效')
            seen.add(spec['suffix'])
            options = spec.get('options', {})
            allowed = {'expandPx', 'color'} if spec['suffix'] == '-outline' else {'opacity'} if spec['suffix'] == '-shadow' else set()
            if set(options) - allowed:
                raise ValueError('不支持此生成参数')
            if spec['suffix'] == '-outline':
                expand, color = options.get('expandPx', 1), options.get('color', '#000000')
                if type(expand) is not int or not 0 <= expand <= 8 or not isinstance(color, str) or not re.fullmatch(r'#?[0-9a-fA-F]{6}', color):
                    raise ValueError('描边宽度或颜色无效')
            if spec['suffix'] == '-shadow':
                opacity = options.get('opacity', 80)
                if type(opacity) is not int or not 0 <= opacity <= 255:
                    raise ValueError('阴影透明度无效')

    def _content(self, path):
        content = (self._content_resolver(path) if self._content_resolver else
                   self._project.contents.get_by_path(path[len('content/'):]))
        digest = hashlib.sha256(json.dumps(content.data, sort_keys=True, ensure_ascii=False,
                                          allow_nan=False).encode('utf-8')).hexdigest()
        return content, digest

    def _validate_path(self, path):
        sprites = self._root / 'sprites'
        if (not sprites.resolve().is_relative_to(self._root) or path.resolve() != path
                or not path.is_relative_to(sprites) or path.suffix.lower() != '.png'
                or (path.exists() and not path.is_file())):
            raise ValueError('生成资源路径无效或超出工程')

    def _read(self, path):
        self._validate_path(path)
        if not path.exists():
            return None
        with open_project_file(self._root, path) as stream:
            raw = stream.read(self.MAX_FILE_BYTES + 1)
        if len(raw) > self.MAX_FILE_BYTES:
            raise ValueError('生成资源文件超过大小上限')
        return raw

    def _size(self, width, height):
        if max(width, height) > self.MAX_DIMENSION or width * height > self.MAX_PIXELS:
            raise ValueError('生成贴图尺寸超过上限')

    def _weapon_path(self, name, category):
        if (not isinstance(name, str) or len(name) > 255 or name in ('.', '..')
                or any(character in name for character in '/\\:\x00<>"|?*')):
            raise ValueError('武器贴图名称无效')
        for category_name in ('weapons', category):
            path = self._root / 'sprites' / category_name / f'{name}.png'
            self._validate_path(path)
            if path.exists():
                return path
        count = 0
        for directory, folders, files in os.walk(self._root / 'sprites', followlinks=False):
            count += len(folders) + len(files)
            if count > self.MAX_SEARCH_ENTRIES:
                raise ValueError('武器贴图检索超过上限')
            folders[:] = sorted(folder for folder in folders
                                if (Path(directory) / folder).resolve() == Path(directory) / folder
                                and (Path(directory) / folder).resolve().is_relative_to(self._root))
            if f'{name}.png' in files:
                path = Path(directory) / f'{name}.png'
                self._validate_path(path)
                return path
        return None

    @contextmanager
    def _inputs(self, path, full):
        targets = self._resources.targets(path)
        content, digest = self._content(path)
        dependencies = {}
        pixels = 0
        with ExitStack() as images:
            def load(file):
                nonlocal pixels
                raw = self._read(file)
                dependencies[file.as_posix()] = hashlib.sha256(raw).hexdigest() if raw is not None else None
                if raw is None:
                    return None
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter('error', Image.DecompressionBombWarning)
                        with Image.open(BytesIO(raw)) as source:
                            if source.format != 'PNG':
                                raise ValueError('生成来源必须是真实 PNG')
                            self._size(*source.size)
                            pixels += source.width * source.height
                            if pixels > self.MAX_TOTAL_PIXELS:
                                raise ValueError('生成来源累计像素超过上限')
                            source.verify()
                        with Image.open(BytesIO(raw)) as source:
                            decoded = source.convert('RGBA')
                            images.callback(decoded.close)
                            return decoded
                except (UnidentifiedImageError, OSError, SyntaxError, EOFError,
                        Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
                    raise ValueError('生成来源 PNG 损坏') from exc

            main = load(self._root / next(row for row in targets if row['suffix'] == '')['path'])
            if main is None:
                raise ValueError('缺少主体贴图，无法生成')
            layers, weapons, sprites = [], [], []
            if full:
                # Preserve the old Qt generator's configuration lookup and
                # centered overlay composition, including its type key semantics.
                for layer in get_sprite_layers().get(content.data.get('type', ''), []):
                    suffix = layer.get('suffix', '')
                    if suffix in ('', '-full', '-outline', '-shadow'):
                        continue
                    decoded = load(self._root / 'sprites' / content.category / f'{content.name}{suffix}.png')
                    if decoded is not None:
                        layers.append(decoded)
                source_weapons = content.data.get('weapons', [])
                if not isinstance(source_weapons, list) or len(source_weapons) > self.MAX_WEAPONS:
                    raise ValueError('武器资料无效或超过数量上限')
                for weapon in source_weapons:
                    if not isinstance(weapon, dict) or not weapon.get('name'):
                        continue
                    file = self._weapon_path(weapon['name'], content.category)
                    if file is None:
                        continue
                    sprite = load(file)
                    for coordinate in ('x', 'y'):
                        number = weapon.get(coordinate, 0)
                        if type(number) not in (int, float) or not math.isfinite(number):
                            raise ValueError('武器坐标必须是有限数字')
                    if type(weapon.get('mirror', False)) is not bool:
                        raise ValueError('武器镜像参数无效')
                    weapons.append(weapon)
                    sprites.append(sprite)
                # Bound generate_full's expanded canvas before Pillow allocates it.
                minimum_x, minimum_y, maximum_x, maximum_y = 0, 0, main.width, main.height
                for weapon, sprite in zip(weapons, sprites):
                    positions = [weapon.get('x', 0)]
                    if weapon.get('mirror', False):
                        positions.append(-weapon.get('x', 0))
                    top = round(main.height / 2 - weapon.get('y', 0) * 4 - sprite.height / 2)
                    minimum_y, maximum_y = min(minimum_y, top), max(maximum_y, top + sprite.height)
                    for position in positions:
                        left = round(main.width / 2 + position * 4 - sprite.width / 2)
                        minimum_x, maximum_x = min(minimum_x, left), max(maximum_x, left + sprite.width)
                self._size(maximum_x - minimum_x, maximum_y - minimum_y)
            yield main, layers, weapons, sprites, dependencies, digest

    def preview(self, path, outputs):
        self._ready()
        if len(self._candidates) >= self.MAX_CANDIDATES:
            raise ValueError('生成候选数量已达上限，请取消旧预览')
        targets = self._resources.targets(path)
        self._specs(outputs, targets)
        result = []
        output_pixels = 0
        full = any(spec['suffix'] == '-full' for spec in outputs)
        with self._inputs(path, full) as (source, layers, weapons, sprites, dependencies, content_digest):
            for spec in outputs:
                target = next(row for row in targets if row['suffix'] == spec['suffix'])
                options = spec.get('options', {})
                if spec['suffix'] == '-outline':
                    generated = generate_outline(source, options.get('expandPx', 1), options.get('color', '#000000'))
                elif spec['suffix'] == '-shadow':
                    generated = generate_shadow(source, options.get('opacity', 80))
                else:
                    generated = generate_full(source, layers or None, weapons or None, sprites or None, ppu=4)
                with generated:
                    output_pixels += generated.width * generated.height
                    if output_pixels > self.MAX_TOTAL_PIXELS or generated.width * generated.height * 4 > self.MAX_FILE_BYTES:
                        raise ValueError('生成输出累计像素或文件大小超过上限')
                    raw = canonical_png_bytes(generated)
                    if len(raw) > self.MAX_FILE_BYTES:
                        raise ValueError('生成输出文件大小超过上限')
                    target_path = self._root / target['path']
                    result.append({'public': {**target, 'width': generated.width, 'height': generated.height,
                                              'dataUrl': 'data:image/png;base64,' + base64.b64encode(raw).decode('ascii')},
                                   'target': target_path, 'before': self._read(target_path), 'after': raw})
        candidate_id = uuid4().hex
        candidate = Candidate(path, content_digest, dependencies, full, result)
        if candidate.cache_bytes + sum(item.cache_bytes for item in self._candidates.values()) > self.MAX_CANDIDATE_BYTES:
            raise ValueError('生成候选缓存已达上限，请取消旧预览')
        self._candidates[candidate_id] = candidate
        return {'sessionId': self._session_id, 'candidateId': candidate_id,
                'outputs': [deepcopy(output['public']) for output in result]}

    def cancel(self, candidate_id):
        self._ready()
        if not isinstance(candidate_id, str) or not candidate_id or len(candidate_id) > 128:
            raise ValueError('生成候选标识无效')
        self._candidates.pop(candidate_id, None)

    def close(self):
        self._candidates.clear()
        self._closed = True

    def _validate_sources(self, path, full, dependencies, digest):
        try:
            with self._inputs(path, full) as inputs:
                if inputs[-2] != dependencies or inputs[-1] != digest:
                    raise ValueError('生成来源已变化，请重新预览')
        except (OSError, ValueError) as exc:
            raise ValueError('生成来源已变化或无法读取，请重新预览') from exc

    def confirm(self, candidate_id, *, overwrite=False):
        self._ready()
        if not isinstance(candidate_id, str) or candidate_id not in self._candidates:
            raise ValueError('生成候选已失效')
        candidate = self._candidates[candidate_id]
        if type(overwrite) is not bool:
            raise ValueError('覆盖确认无效')
        if any(output['before'] is not None for output in candidate.outputs) and not overwrite:
            raise ValueError('贴图已存在，需要明确确认覆盖')
        source_path, full, dependencies, digest = candidate.path, candidate.full, candidate.dependencies, candidate.content
        validate = lambda: self._validate_sources(source_path, full, dependencies, digest)
        commands = [ResourceCommand(output['target'], output['before'], output['after'],
                                    lambda target=output['target']: self._validate_path(target))
                    for output in candidate.outputs]
        snapshots = [(output['target'], output['before'], output['after']) for output in candidate.outputs]
        def validate_outputs(undo):
            for target, before, after in snapshots:
                if self._read(target) != (after if undo else before):
                    raise ValueError('生成目标已被外部修改，请重新预览')
        self._resources.execute_resource_command(GeneratedResourcesCommand(commands, self._on_change, validate, validate_outputs))
        self._candidates.pop(candidate_id)
        return {'sessionId': self._session_id,
                'outputs': [{**{key: value for key, value in output['public'].items() if key != 'dataUrl'}, 'exists': True}
                            for output in candidate.outputs]}
