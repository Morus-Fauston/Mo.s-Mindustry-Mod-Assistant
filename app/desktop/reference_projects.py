"""Bounded readonly reference snapshots, separate from editable project sessions.

Workspace owns serialization, native selection and request replay. It alone passes
native paths and the current ContentFile.data to this service. Importing never
registers project documents, writes files or changes command history.
"""

from __future__ import annotations

import json
import math
import stat
import zipfile
import zlib
from pathlib import Path
from uuid import uuid4

from app.core.config_loader import get_category_names_zh, get_content_names_zh


_MISSING = object()
_NAME_CATEGORIES = {'Blocks': 'blocks', 'UnitTypes': 'units', 'Weapons': 'weapons',
                    'Items': 'items', 'Liquids': 'liquids', 'StatusEffects': 'status',
                    'Planets': 'planets', 'SectorPresets': 'sectors'}


class ReferenceProjectsService:
    """At most a current and pending external source plus builtin vanilla data.

    Opening is transactional: failures leave all existing sources untouched.
    The caller releases the pending source on cancel, or the old source after a
    successful selection. Closing invalidates the entire owning session.
    """

    MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
    MAX_TOTAL_BYTES = 64 * 1024 * 1024
    MAX_ENTRIES = 10_000
    MAX_CONTENTS = 2_000
    MAX_JSON_DEPTH = 64
    MAX_JSON_NODES = 100_000
    MAX_SOURCE_NODES = 500_000
    MAX_ROWS = 2_000
    MAX_WARNINGS = 20
    MAX_TEXT = 512
    MAX_PAGE = 100
    MAX_PATH_DEPTH = 8
    MAX_PATH_LENGTH = 1024
    MAX_ARCHIVE_BYTES = 64 * 1024 * 1024

    def __init__(self, metadata, session_id: str):
        if not isinstance(session_id, str) or not session_id:
            raise ValueError('参考服务需要有效的工程会话。')
        self._metadata = metadata
        self._session_id = session_id
        self._external: dict[str, dict] = {}
        self._closed = False

    def _ready(self):
        if self._closed:
            raise ValueError('参考会话已关闭，请在当前工程重新打开参考。')

    def _room(self):
        self._ready()
        if len(self._external) >= 2:
            raise ValueError('请先确认或取消待选参考，再导入其他来源。')

    def _descriptor(self, source_id, source):
        labels = get_category_names_zh()
        categories = sorted(source['contents'], key=lambda value: (
            {'units': 0, 'blocks': 1, 'weapons': 2}.get(value, 3), value))
        reverse = {value: key for key, value in _NAME_CATEGORIES.items()}
        return {'sourceId': source_id, 'kind': source['kind'], 'label': source['label'],
                'categories': [{'id': category, 'label': labels.get(category, labels.get(reverse.get(category), category))}
                               for category in categories], 'warnings': list(source['warnings'])}

    def _publish(self, kind, label, contents, warnings):
        if not contents:
            raise ValueError('参考中没有可读取的 JSON 内容，请检查 content 目录。')
        if sum(len(values) for values in contents.values()) > self.MAX_CONTENTS:
            raise ValueError('参考内容数量超过上限。')
        source_id = uuid4().hex
        source = {'kind': kind, 'label': label, 'contents': contents, 'warnings': warnings}
        self._external[source_id] = source
        return self._descriptor(source_id, source)

    def open_folder(self, native_path: Path):
        self._room()
        try:
            root = Path(native_path).resolve(strict=True)
            if not root.is_dir():
                raise ValueError('参考来源不是目录。')
            contents, warnings, budget = {}, [], {'entries': 0, 'bytes': 0, 'nodes': 0}
            label = root.name
            mod = root / 'mod.json'
            if mod.exists() or mod.is_symlink():
                data = self._parse(self._read_file(root, mod, budget), 'mod.json', warnings, budget)
                if data:
                    label = self._label(data, label)
            content = root / 'content'
            if content.exists() or content.is_symlink():
                self._contained(root, content)
                if not content.is_dir():
                    raise ValueError('参考 content 路径不是目录。')
                for category in self._children(root, content, budget):
                    if not category.is_dir():
                        continue
                    values = {}
                    for path in self._children(root, category, budget):
                        if not path.is_file() or path.suffix.lower() != '.json':
                            continue
                        data = self._parse(self._read_file(root, path, budget), f'{category.name}/{path.name}', warnings, budget)
                        if data is not None:
                            values[path.stem] = data
                    if values:
                        contents[category.name] = values
        except OSError as exc:
            raise ValueError('无法读取参考目录，请检查目录是否存在及访问权限。') from exc
        return self._publish('folder', label, contents, warnings)

    @staticmethod
    def _contained(root, path):
        # Reject all reparse points below the chosen root, including junctions.
        for entry in [path, *path.parents]:
            if entry == root:
                break
            info = entry.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError('参考目录含符号链接或重解析点，不能作为只读来源。')
        if not path.resolve(strict=True).is_relative_to(root):
            raise ValueError('参考路径超出所选目录。')

    def _children(self, root, parent, budget):
        values = []
        identities = set()
        for path in parent.iterdir():
            budget['entries'] += 1
            if budget['entries'] > self.MAX_ENTRIES:
                raise ValueError('参考目录条目数量超过上限。')
            self._contained(root, path)
            identity = path.name.casefold()
            if identity in identities:
                raise ValueError('参考目录存在大小写冲突名称。')
            identities.add(identity)
            values.append(path)
        return sorted(values)

    def _read_file(self, root, path, budget):
        self._contained(root, path)
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('参考 JSON 路径不是普通文件。')
        if info.st_size > self.MAX_DOCUMENT_BYTES:
            raise ValueError(f'参考文件过大：{path.name}')
        with path.open('rb') as stream:
            raw = stream.read(min(self.MAX_DOCUMENT_BYTES, self.MAX_TOTAL_BYTES - budget['bytes']) + 1)
        budget['bytes'] += len(raw)
        if budget['bytes'] > self.MAX_TOTAL_BYTES:
            raise ValueError('参考读取字节总量超过上限。')
        return raw

    def open_zip(self, native_path: Path):
        self._room()
        archive = Path(native_path)
        try:
            if archive.stat().st_size > self.MAX_ARCHIVE_BYTES:
                raise ValueError('ZIP 文件大小超过上限。')
            with zipfile.ZipFile(archive) as source:
                entries = source.infolist()
                self._validate_archive(entries)
                names = [entry.filename for entry in entries]
                def has_root(prefix):
                    folded = prefix.casefold()
                    return any(name.casefold() == folded + 'mod.json'
                               or name.casefold().startswith(folded + 'content/') for name in names)
                prefix = ''
                if not has_root(''):
                    folders = {name.split('/')[0] for name in names if '/' in name}
                    if len(folders) != 1:
                        raise ValueError('ZIP 内未找到模组根目录，只支持顶层或一层目录包装。')
                    prefix = next(iter(folders)) + '/'
                    if not has_root(prefix):
                        raise ValueError('ZIP 内未找到模组根目录，只支持顶层或一层目录包装。')
                contents, warnings, total, budget = {}, [], 0, {'nodes': 0}
                label = archive.stem
                for entry in entries:
                    if entry.is_dir() or not entry.filename.startswith(prefix):
                        continue
                    relative = entry.filename[len(prefix):]
                    parts = relative.split('/')
                    is_mod = relative.casefold() == 'mod.json'
                    is_content = len(parts) == 3 and parts[0].casefold() == 'content' and parts[-1].lower().endswith('.json')
                    if not is_mod and not is_content:
                        continue
                    if entry.file_size > self.MAX_DOCUMENT_BYTES:
                        raise ValueError(f'参考文件过大：{relative}')
                    with source.open(entry) as stream:
                        raw = stream.read(min(self.MAX_DOCUMENT_BYTES, self.MAX_TOTAL_BYTES - total) + 1)
                    total += len(raw)
                    if total > self.MAX_TOTAL_BYTES:
                        raise ValueError('参考读取字节总量超过上限。')
                    data = self._parse(raw, relative, warnings, budget)
                    if data is not None:
                        if is_mod:
                            label = self._label(data, label)
                        else:
                            contents.setdefault(parts[1], {})[parts[2][:-5]] = data
        except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError, zlib.error, EOFError, UnicodeError) as exc:
            raise ValueError('无法读取 ZIP 参考，请检查文件完整性、加密或压缩方式。') from exc
        return self._publish('zip', label, contents, warnings)

    def _validate_archive(self, entries):
        if len(entries) > self.MAX_ENTRIES:
            raise ValueError('ZIP 条目数量超过上限。')
        total, known, explicit = 0, {}, set()
        reserved = {'CON', 'PRN', 'AUX', 'NUL', 'CLOCK$', 'CONIN$', 'CONOUT$',
                    *(f'{prefix}{suffix}' for prefix in ('COM', 'LPT') for suffix in '123456789¹²³')}
        for entry in entries:
            name = entry.orig_filename
            parts = name.removesuffix('/').split('/')
            if (len(name) > self.MAX_PATH_LENGTH or len(parts) > self.MAX_PATH_DEPTH
                    or any(not part or part in ('.', '..') or len(part) > 255
                           or part[-1] in ' .' or any(char in '\\:<>"|?*' or ord(char) < 32 for char in part)
                           or part.split('.')[0].rstrip(' ').upper() in reserved for part in parts)):
                raise ValueError('ZIP 路径不安全、过长或有歧义。')
            mode = stat.S_IFMT(entry.external_attr >> 16)
            if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError('ZIP 含符号链接或不支持的特殊条目。')
            if entry.flag_bits & 1:
                raise ValueError('ZIP 参考不支持加密条目。')
            key = '/'.join(parts).casefold()
            if key in explicit:
                raise ValueError('ZIP 存在重复或大小写冲突路径。')
            explicit.add(key)
            for index in range(1, len(parts) + 1):
                path = '/'.join(parts[:index])
                is_dir = index < len(parts) or entry.is_dir()
                previous = known.get(path.casefold())
                if previous is not None and previous != (path, is_dir):
                    raise ValueError('ZIP 存在文件目录冲突或大小写歧义路径。')
                known[path.casefold()] = (path, is_dir)
            total += entry.file_size
            if entry.file_size < 0 or total > self.MAX_TOTAL_BYTES:
                raise ValueError('ZIP 展开字节总量超过上限。')

    @staticmethod
    def _label(data, fallback):
        for value in (data.get('name'), data.get('displayName')):
            if isinstance(value, str) and value.strip():
                return value[:256]
        return fallback[:256]

    def _parse(self, raw, name, warnings, budget):
        if len(raw) > self.MAX_DOCUMENT_BYTES:
            raise ValueError(f'参考文件过大：{name}')
        try:
            data = json.loads(raw.decode('utf-8'))
            if not isinstance(data, dict):
                raise ValueError('顶层需要对象')
        except RecursionError as exc:
            raise ValueError(f'参考内容结构过深：{name}') from exc
        except (ValueError, UnicodeError):
            if len(warnings) < self.MAX_WARNINGS:
                warnings.append(f'已跳过无法解析的 JSON 内容：{name}')
            return None
        budget['nodes'] += self._validate_json(data)
        if budget['nodes'] > self.MAX_SOURCE_NODES:
            raise ValueError('参考内容节点总量超过上限。')
        return data

    def _validate_json(self, data):
        pending = [(data, 0)]
        count = 0
        while pending:
            value, depth = pending.pop()
            count += 1
            if depth > self.MAX_JSON_DEPTH or count > self.MAX_JSON_NODES:
                raise ValueError('参考内容结构过深或过大。')
            if isinstance(value, dict):
                if not all(isinstance(key, str) for key in value):
                    raise ValueError('参考对象字段名必须是文本。')
                pending.extend((child, depth + 1) for child in value.values())
            elif isinstance(value, list):
                pending.extend((child, depth + 1) for child in value)
            elif value is not None and type(value) not in (str, int, float, bool):
                raise ValueError('参考内容含不支持的数据类型。')
        return count

    def _source(self, source_id):
        self._ready()
        if not isinstance(source_id, str) or source_id not in self._external:
            raise ValueError('参考来源不存在或已释放，请重新选择。')
        return self._external[source_id]

    def sources(self):
        self._ready()
        vanilla = {'kind': 'vanilla', 'label': '原版内容', 'warnings': [],
                   'contents': {category: {} for category in self._metadata.list_instance_categories()}}
        return [self._descriptor('vanilla', vanilla),
                *(self._descriptor(key, value) for key, value in self._external.items())]

    def _names(self, source_id, category):
        self._ready()
        if not isinstance(category, str):
            raise ValueError('请选择有效的参考类别。')
        if source_id == 'vanilla':
            if category not in self._metadata.list_instance_categories():
                raise ValueError('参考类别不存在。')
            return sorted(self._metadata.list_instances(category))
        source = self._source(source_id)
        if category not in source['contents']:
            raise ValueError('参考类别不存在。')
        return sorted(source['contents'][category])

    def candidates(self, source_id, category, query='', offset=0, limit=100):
        if not isinstance(query, str) or len(query) > 256:
            raise ValueError('参考搜索内容须为 256 字以内的文本。')
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= self.MAX_PAGE:
            raise ValueError('参考分页参数无效。')
        names = self._names(source_id, category)
        labels = get_content_names_zh().get(_NAME_CATEGORIES.get(category, category), {}) if source_id == 'vanilla' else {}
        needle = query.strip().casefold()
        matches = []
        for name in names:
            translated = labels.get(name)
            label = f'{translated} ({name})' if translated else name
            if not needle or needle in name.casefold() or needle in label.casefold():
                matches.append({'sourceId': source_id, 'category': category, 'name': name, 'label': label})
        return {'sourceId': source_id, 'category': category, 'candidates': matches[offset:offset + limit],
                'offset': offset, 'total': len(matches),
                'hasMore': offset + limit < len(matches)}

    def compare(self, source_id, category, name, current_data, current_path, revision):
        if not isinstance(name, str) or name not in self._names(source_id, category):
            raise ValueError('参考内容不存在，请重新选择。')
        if not isinstance(current_data, dict) or not isinstance(current_path, str) or not current_path:
            raise ValueError('请先打开一个内容文件。')
        if type(revision) is not int or revision < 0:
            raise ValueError('当前编辑版本无效，请刷新后重试。')
        reference = (self._metadata.get_instance(category, name) if source_id == 'vanilla'
                     else self._source(source_id)['contents'][category][name])
        if not isinstance(reference, dict):
            raise ValueError('参考内容顶层必须是对象。')
        self._validate_json(current_data)
        self._validate_json(reference)
        keys = sorted(current_data.keys() | reference.keys())
        if len(keys) > self.MAX_ROWS:
            raise ValueError('对比字段过多，无法完整显示。')
        return {'sessionId': self._session_id, 'sourceId': source_id, 'category': category, 'name': name,
                'currentPath': current_path, 'revision': revision,
                'rows': [{'field': key, 'current': self._cell(current_data.get(key, _MISSING)),
                          'reference': self._cell(reference.get(key, _MISSING)),
                          'different': not _equal(current_data.get(key, _MISSING), reference.get(key, _MISSING))}
                         for key in keys]}

    def _cell(self, value):
        kind = _kind(value)
        if kind == 'missing':
            text = '未设置'
        elif kind == 'object':
            text = '{…}'
        elif kind == 'array':
            text = f'[{len(value)} 项]'
        elif kind == 'nonfinite':
            text = 'NaN' if math.isnan(value) else 'Infinity' if value > 0 else '-Infinity'
        else:
            text = json.dumps(value, ensure_ascii=False, allow_nan=False)
        truncated = len(text) > self.MAX_TEXT
        return {'present': value is not _MISSING, 'kind': kind,
                'text': text[:self.MAX_TEXT] + ('…（已截断）' if truncated else ''), 'truncated': truncated}

    def release(self, source_id):
        self._ready()
        if not isinstance(source_id, str):
            raise ValueError('参考来源标识无效。')
        self._external.pop(source_id, None)

    def close(self):
        self._external.clear()
        self._closed = True


def _kind(value):
    if value is _MISSING:
        return 'missing'
    if value is None:
        return 'null'
    if type(value) is bool:
        return 'boolean'
    if type(value) is float and not math.isfinite(value):
        return 'nonfinite'
    if type(value) in (int, float):
        return 'number'
    if isinstance(value, str):
        return 'string'
    if isinstance(value, list):
        return 'array'
    return 'object'


def _equal(left, right):
    if _kind(left) != _kind(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right
