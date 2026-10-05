"""Command-owned document identity snapshots around existing content-file writes."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import PurePosixPath
import weakref

from app.core.content_commands import ContentChange, file_bytes, local_path
from app.core.content_store import ContentData
from app.desktop.editing import DocumentCommand, EditingError, _DocumentState, _DocumentStateCommand
from app.desktop.forms import json_values_equal
from app.desktop.nested_forms import NestedFormState
from app.desktop.source_editing import RawDocument, SourceEditingService


@dataclass
class _Snapshot:
    paths: tuple[str, ...]
    mappings: dict
    registered: dict
    entries: dict
    identities: list
    forms: dict
    form_presence: dict
    opened: list[str]


@dataclass
class _Record:
    change: weakref.ReferenceType
    before: _Snapshot
    after: _Snapshot | None = None
    applied: bool = False
    ignore_compensation: bool | None = None


class ContentIdentityAdapter:
    """prepare before the file command; handler inside its execute/undo callback.

    Records are weakly owned by ContentChange, whose file command owns history.
    They are identity snapshots only, never an independently executable history.
    """
    _MAPS = ('_documents', '_raw_documents', '_saved', '_saved_entries', '_saved_forms')

    def __init__(self, editing):
        self.editing = editing
        self._prepared: _Snapshot | None = None
        self._records: dict[int, _Record] = {}
        self.last_change: dict | None = None

    def consume_change(self) -> dict | None:
        change, self.last_change = self.last_change, None
        return change

    def prepare(self, paths: list[str], decision: str | None = None) -> None:
        """Resolve only affected dirty documents, keeping their tabs open."""
        self._prepared = None
        self.last_change = None
        if decision not in (None, 'save', 'discard'):
            raise EditingError('INVALID_REQUEST', '请选择保存、放弃或取消内容操作。')
        paths = tuple(dict.fromkeys(paths))
        for path in paths:
            self._path(path)
            self._check_disk_baseline(path)
        dirty = [path for path in paths if self.editing.entry(path) is not None and self.editing._dirty(path)]
        if dirty and decision is None:
            raise EditingError('UNSAVED_CHANGES', '受影响内容有未保存修改，请选择保存或放弃。', dirty[0])
        if decision == 'save' and dirty:
            self.editing.save_paths(dirty)
        elif decision == 'discard':
            for path in dirty:
                content, saved = self.editing.entry(path), self.editing._saved_entries[path]
                if isinstance(content, RawDocument) or isinstance(saved, RawDocument):
                    command = _DocumentStateCommand(self.editing, path, _DocumentState(
                        saved, deepcopy(self.editing._saved.get(path)), self.editing._saved_forms[path]))
                else:
                    command = self.editing.nested.replace(content, path, self.editing._saved[path],
                                                          self.editing._saved_forms[path])
                if command is not None:
                    self.editing.session.command_stack.execute(DocumentCommand(
                        command, path, f'放弃 {path} 的未保存修改', self.editing.changed))
        self._prepared = self._capture(paths)

    def _check_disk_baseline(self, path: str) -> None:
        editing = self.editing
        saved = editing._saved_entries.get(path) or editing.session.loaded_content(path[8:])
        if saved is None:
            return
        try:
            raw = file_bytes(self._path(path))
            if raw is None:
                raise ValueError('文件已不存在')
            text = raw.decode('utf-8')
            matches = (text == saved.source_text if isinstance(saved, RawDocument) else
                       json_values_equal(SourceEditingService._decode(text), editing._saved.get(path, saved.data)))
            if not matches:
                raise ValueError('文件资料已变化')
        except (OSError, ValueError, UnicodeError) as error:
            raise EditingError('CONTENT_CHANGED', '文件已被外部修改或无法读取，请保留当前修改并重新打开工程后重试。', path) from error

    def _path(self, path: str):
        project = self.editing.session.project
        if project is None:
            raise EditingError('NO_PROJECT', '请先打开工程。')
        target = local_path(project.root, path)
        relative = PurePosixPath(path)
        if (len(relative.parts) != 3 or relative.parts[0] != 'content'
                or relative.parts[1] not in ('units', 'blocks', 'weapons') or relative.suffix != '.json'):
            raise ValueError('请选择分类内的内容文件。')
        return target

    def _capture(self, paths: tuple[str, ...]) -> _Snapshot:
        editing = self.editing
        mappings = {}
        for name in self._MAPS:
            selected = {path: getattr(editing, name)[path] for path in paths if path in getattr(editing, name)}
            mappings[name] = deepcopy(selected) if name in ('_saved', '_saved_forms') else selected
        registered = {path: editing.session.loaded_content(path[8:]) for path in paths}
        entries = {}
        for path in paths:
            entry = editing.entry(path) or registered[path]
            if entry is None:
                target = self._path(path)
                raw = file_bytes(target)
                if raw is not None:
                    text = raw.decode('utf-8')
                    try:
                        data = SourceEditingService._decode(text)
                    except ValueError as error:
                        entry = RawDocument(target.stem, path.split('/')[1], target, text,
                                            SourceEditingService.error_details(error))
                    else:
                        entry = ContentData(target.stem, path.split('/')[1], data, target)
            entries[path] = entry
        objects = [*entries.values(), *registered.values(), *mappings['_saved_entries'].values()]
        identities, seen = [], set()
        for entry in objects:
            if isinstance(entry, ContentData) and id(entry) not in seen:
                seen.add(id(entry))
                identities.append((entry, entry.name, entry.category, entry.path, deepcopy(entry.data)))
        return _Snapshot(paths, mappings, registered, entries, identities,
                         {path: editing.nested.snapshot(path) for path in paths},
                         {path: (path in editing.nested._states, path in editing.forms._memories) for path in paths},
                         list(editing._opened))

    def _drop(self, path: str) -> None:
        editing = self.editing
        current = editing.session.loaded_content(path[8:])
        if current is not None:
            editing.session.detach_content(path[8:], current)
        for name in self._MAPS:
            getattr(editing, name).pop(path, None)
        editing._opened.pop(path, None)
        editing.nested.drop_state(path)

    def _restore(self, snapshot: _Snapshot) -> None:
        editing = self.editing
        for path in snapshot.paths:
            self._drop(path)
        for entry, name, category, path, data in snapshot.identities:
            entry.name, entry.category, entry.path = name, category, path
            entry.data.clear()
            entry.data.update(deepcopy(data))
        for name, selected in snapshot.mappings.items():
            getattr(editing, name).update(deepcopy(selected) if name in ('_saved', '_saved_forms') else selected)
        for path, entry in snapshot.registered.items():
            if entry is not None:
                editing.session.attach_content(path[8:], entry)
        for path in snapshot.paths:
            nested_present, root_present = snapshot.form_presence[path]
            if nested_present:
                editing.nested.restore(path, snapshot.forms[path])
            elif root_present:
                editing.forms.restore(path, snapshot.forms[path].root)
            if not root_present:
                editing.forms.drop_state(path)
        # Restore affected tab positions without closing unrelated tabs opened later.
        opened = list(editing._opened)
        for index, path in enumerate(snapshot.opened):
            if path not in snapshot.paths:
                continue
            previous = next((item for item in reversed(snapshot.opened[:index]) if item in opened), None)
            position = opened.index(previous) + 1 if previous else min(index, len(opened))
            opened.insert(position, path)
        editing._opened = dict.fromkeys(opened)

    def _forward(self, change: ContentChange, before: _Snapshot) -> None:
        editing = self.editing
        old, new = change.before_path, change.after_path
        source = before.entries.get(old or new)
        form = before.forms.get(old or new, NestedFormState())
        old_position = list(editing._opened).index(old) if old in editing._opened else None
        if old:
            self._drop(old)
        if new is None:
            return
        if new != old:
            self._drop(new)
        relative = PurePosixPath(new)
        if isinstance(source, ContentData):
            entry = source
            entry.name, entry.category, entry.path = relative.stem, relative.parts[1], self._path(new)
            entry.data.clear()
            entry.data.update(deepcopy(change.after_data))
        else:
            entry = ContentData(relative.stem, relative.parts[1], deepcopy(change.after_data), self._path(new))
        editing.session.attach_content(new[8:], entry)
        editing._documents[new] = entry
        editing._saved_entries[new] = entry
        editing._saved[new] = deepcopy(entry.data)
        if change.action != 'rename':
            form, _ = editing.source._projection(entry, new, entry.data)
        editing.nested.restore(new, form)
        editing._saved_forms[new] = deepcopy(form)
        opened = list(editing._opened)
        opened.insert(old_position if old_position is not None else len(opened), new)
        editing._opened = dict.fromkeys(opened)

    def handler(self, change: ContentChange, undo: bool) -> None:
        key = id(change)
        record = self._records.get(key)
        if record is None:
            paths = {path for path in (change.before_path, change.after_path) if path is not None}
            if undo or self._prepared is None or not paths.issubset(self._prepared.paths):
                raise ValueError('内容身份操作未准备，不能发布文件变化。')
            record = _Record(weakref.ref(change, lambda _ref: self._records.pop(key, None)), self._prepared)
            self._records[key] = record
            self._prepared = None
        if record.ignore_compensation is undo:
            record.ignore_compensation = None
            return
        if record.applied is (not undo):
            return
        editing = self.editing
        previous = self._capture(record.before.paths)
        revision, merge, notice = editing.revision, editing._merge_token, self.last_change
        rename = change.action == 'rename' and change.before_path != change.after_path
        old, new = ((change.after_path, change.before_path) if undo else (change.before_path, change.after_path))
        rekeyed = False
        try:
            if rename:
                editing.session.command_stack.rekey_document(old, new)
                rekeyed = True
            if undo:
                self._restore(record.before)
            elif record.after is None:
                self._forward(change, record.before)
                record.after = self._capture(record.before.paths)
            else:
                self._restore(record.after)
            editing._merge_token = object()
            editing.revision += 1
            editing.session.project.is_dirty = editing.has_dirty()
            self.last_change = {'action': change.action, 'beforePath': change.before_path,
                                'afterPath': change.after_path, 'undo': undo}
            record.applied = not undo
        except Exception:
            if rekeyed:
                editing.session.command_stack.rekey_document(new, old)
            self._restore(previous)
            editing.revision, editing._merge_token, self.last_change = revision, merge, notice
            record.ignore_compensation = not undo
            raise
