"""Global view preferences; no project mutations or business command history."""

from __future__ import annotations

from contextlib import suppress
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile

from app.core.paths import data_dir, user_config_dir
from app.desktop.editing import EditingError


_DEFAULT_LAYOUT = {'leftWidth': None, 'rightWidth': None, 'previewRatio': None,
                   'filesVisible': True, 'previewVisible': True}
_SETTING_OPTIONS = {'theme': ('light', 'dark'),
                    'display_name_mode': ('zh_en', 'en_zh', 'zh', 'en')}
_SETTING_RANGES = {'auto_save_interval': (0, 3600), 'sprite_zoom': (1, 8)}
_SAFE_SETTINGS = {'theme': 'light', 'display_name_mode': 'zh_en',
                  'auto_save_interval': 180, 'sprite_zoom': 4}


class PreferencesError(EditingError):
    """Transport-compatible configuration failure with an actionable code."""


class PreferencesService:
    """Workspace serializes calls; callers receive detached JSON snapshots."""

    def __init__(self, defaults_path=None, user_dir=None):
        self._defaults_path = Path(defaults_path) if defaults_path is not None else data_dir() / 'app/config/settings_default.json'
        self._user_dir = Path(user_dir) if user_dir is not None else user_config_dir()
        self._settings_path = self._user_dir / 'settings.json'
        self._state_path = self._user_dir / 'editor_state.json'
        self._warnings = []
        self._blocked = set()
        defaults = self._read(self._defaults_path, required=True)
        self._defaults = self._validated_settings(defaults, self._defaults_path, _SAFE_SETTINGS)
        overrides = self._validated_settings(self._read(self._settings_path), self._settings_path, self._defaults)
        self._values = {**self._defaults, **overrides}
        self._layout = dict(_DEFAULT_LAYOUT)
        editor = self._read(self._state_path)
        if 'web_workbench' in editor:
            try:
                self._validate_layout(editor['web_workbench'])
                self._layout = editor['web_workbench']
            except PreferencesError:
                self._block(self._state_path, '工作台布局值无效，当前使用默认布局')
        self._revision = 0

    def state(self):
        return deepcopy({'revision': self._revision, 'defaults': self._defaults,
                         'values': self._values, 'layout': self._layout,
                         'warnings': self._warnings})

    def update_settings(self, patch, expected_revision):
        self._check_revision(expected_revision)
        if not isinstance(patch, dict):
            raise PreferencesError('INVALID_PREFERENCES', '设置修改必须是键值对象。')
        for key, value in patch.items():
            self._validate_setting(key, value)
        self._writable(self._defaults_path)
        self._writable(self._settings_path)
        current = self._validated_settings(self._read(self._settings_path), self._settings_path, self._defaults)
        self._writable(self._settings_path)
        values = {**self._defaults, **current, **deepcopy(patch)}
        overrides = {key: value for key, value in values.items()
                     if key not in self._defaults or value != self._defaults[key]}
        self._write_atomic(self._settings_path, overrides)
        self._values = values
        self._revision += 1
        return self.state()

    def update_layout(self, layout, expected_revision):
        self._check_revision(expected_revision)
        self._validate_layout(layout)
        self._writable(self._state_path)
        editor = self._read(self._state_path)
        if 'web_workbench' in editor:
            try:
                self._validate_layout(editor['web_workbench'])
            except PreferencesError:
                self._block(self._state_path, '工作台布局值无效')
        self._writable(self._state_path)
        editor['web_workbench'] = deepcopy(layout)
        self._write_atomic(self._state_path, editor)
        self._layout = deepcopy(layout)
        self._revision += 1
        return self.state()

    def _block(self, path, reason):
        self._blocked.add(path)
        warning = f'{path.name}：{reason}；保留原文件并禁用写入，请修复后重启。'
        if warning not in self._warnings:
            self._warnings.append(warning)

    def _writable(self, path):
        if path in self._blocked:
            raise PreferencesError('PREFERENCES_READ_ONLY', f'{path.name} 读取或校验失败，已保护原文件，请修复后重启。')

    def _read(self, path, *, required=False):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError('顶层必须是对象')
            json.dumps(data, allow_nan=False)
            # Validate copying here too, inside the protected read boundary.
            # json.loads can accept nesting deeper than deepcopy can handle.
            return deepcopy(data)
        except FileNotFoundError:
            if required:
                self._block(path, '缺少默认配置，当前使用安全回退值')
        except (OSError, UnicodeError, ValueError, RecursionError):
            self._block(path, '无法读取有效配置，当前保留有效值或使用默认值')
        return {}

    def _validated_settings(self, values, path, fallback):
        result = deepcopy(values)
        for key in _SAFE_SETTINGS:
            if key not in result:
                if path == self._defaults_path:
                    result[key] = fallback[key]
                    self._block(path, f'缺少设置项 {key}，当前使用安全回退值')
                continue
            try:
                self._validate_setting(key, result[key])
            except PreferencesError:
                result[key] = fallback[key]
                self._block(path, f'设置项 {key} 无效，当前使用默认值')
        return result

    @staticmethod
    def _validate_layout(layout):
        if not isinstance(layout, dict) or set(layout) != set(_DEFAULT_LAYOUT):
            raise PreferencesError('INVALID_PREFERENCES', '工作台布局字段不完整或包含未知字段。')
        for key, value in layout.items():
            if key in ('filesVisible', 'previewVisible'):
                valid = type(value) is bool
            elif value is None:
                valid = True
            elif type(value) not in (int, float):
                valid = False
            elif key == 'previewRatio':
                valid = 0 < value < 1
            else:
                valid = (160 if key == 'leftWidth' else 305) <= value <= 10000
            if not valid:
                raise PreferencesError('INVALID_PREFERENCES', f'工作台布局项 {key} 的值无效。', details={'field': key})

    def _check_revision(self, revision):
        if type(revision) is not int or revision != self._revision:
            raise PreferencesError('STALE_PREFERENCES_REVISION', '设置已更新，请刷新后重试。')

    @staticmethod
    def _validate_setting(key, value):
        if key in _SETTING_OPTIONS:
            valid = type(value) is str and value in _SETTING_OPTIONS[key]
        elif key in _SETTING_RANGES:
            lower, upper = _SETTING_RANGES[key]
            valid = type(value) is int and lower <= value <= upper
        else:
            valid = False
        if not valid:
            raise PreferencesError('INVALID_PREFERENCES', f'设置项 {key} 的值无效或不允许修改。', details={'field': key})

    @staticmethod
    def _write_atomic(path, data):
        temporary = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                             prefix=f'.{path.name}.', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except (OSError, ValueError, RecursionError) as exc:
            raise PreferencesError('PREFERENCES_SAVE_FAILED',
                                   f'{path.name} 保存失败，原设置仍然有效，请检查文件占用和权限后重试。') from exc
        finally:
            if temporary is not None:
                with suppress(OSError):
                    temporary.unlink(missing_ok=True)
