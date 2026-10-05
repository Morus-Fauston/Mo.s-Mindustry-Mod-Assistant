"""Desktop editing orchestration over the existing core command stack."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import PurePosixPath
from typing import Callable

from app.core.commands import Command, SetFieldCommand
from app.core.config_loader import get_field_docs, get_field_names_zh
from app.core.content_store import ContentData
from app.core.metadata import normalize_content_type
from app.core.session import ProjectSession
from app.core.settings import get_settings
from app.desktop.forms import FormService, json_values_equal
from app.desktop.references import ReferenceService
from app.desktop.nested_forms import NestedFormService, NestedFormState
from app.desktop.resource_fields import ResourceFieldsService
from app.desktop.ability_forms import AbilityFormsService
from app.desktop.weapon_forms import WeaponFormsService
from app.desktop.research_fields import ResearchFieldsService
from app.desktop.source_editing import RawDocument, SourceEditingService


class EditingError(Exception):
    def __init__(self, code: str, message: str, path: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.code, self.path = code, path
        self.details = details or {}


@dataclass
class _DocumentState:
    entry: ContentData | RawDocument
    data: dict | None
    form: NestedFormState


class _DocumentStateCommand(Command):
    """An atomic raw/valid transition, retaining the real object's identity."""

    def __init__(self, editing: EditingService, path: str, after: _DocumentState):
        self.editing, self.path, self.after = editing, path, after
        self.before = editing._snapshot(path)

    def execute(self) -> None:
        self.editing._restore(self.path, self.after)

    def undo(self) -> None:
        self.editing._restore(self.path, self.before)

    def rekey_document(self, old: str, new: str) -> None:
        if self.path != old:
            return
        self.path = new
        relative = PurePosixPath(new)
        for state in (self.before, self.after):
            entry = state.entry
            values = {'name': relative.stem, 'category': relative.parts[1],
                      'path': self.editing.session.project.root / new}
            if isinstance(entry, RawDocument):
                state.entry = replace(entry, **values)
            else:
                entry.name, entry.category, entry.path = values.values()


class DocumentCommand(Command):
    """Retain document identity when session-wide history reopens a closed tab."""

    def __init__(self, command: Command, path: str, description: str, on_change: Callable[[str], None],
                 merge_token: object | None = None):
        self.command, self.path = command, path
        self._description, self._on_change = description, on_change
        self._merge_token = merge_token

    @property
    def description(self) -> str:
        return self._description

    def execute(self) -> None:
        self.command.execute()
        self._on_change(self.path)

    def undo(self) -> None:
        self.command.undo()
        self._on_change(self.path)

    def rekey_document(self, old: str, new: str) -> None:
        self.command.rekey_document(old, new)
        if self.path == old:
            self.path = new

    def merge_with(self, other: Command) -> Command | None:
        if (isinstance(other, DocumentCommand) and other.path == self.path
                and self._merge_token is not None and other._merge_token is self._merge_token):
            merged = self.command.merge_with(other.command)
            if merged is not None:
                return DocumentCommand(merged, self.path, other.description, self._on_change, self._merge_token)
        return None


class EditingService:
    def __init__(self, session: ProjectSession, session_id: str | None, revision: int = 0,
                 *, on_saved: Callable[[str], None] | None = None):
        self.session, self.session_id, self.revision = session, session_id, revision
        self._on_saved = on_saved
        self._documents: dict[str, ContentData] = {}
        self._raw_documents: dict[str, RawDocument] = {}
        self._opened: dict[str, None] = {}
        self._saved: dict[str, dict] = {}
        self._saved_forms: dict[str, NestedFormState] = {}
        self._saved_entries: dict[str, ContentData | RawDocument] = {}
        self._merge_token = object()
        self.references = ReferenceService(session.metadata, session.project)
        self.forms = FormService(session.metadata, self.references)
        self.nested = NestedFormService(session.metadata, self.forms)
        self.ability_forms = AbilityFormsService(self.nested)
        self.weapon_forms = WeaponFormsService(self.nested, session.project)
        self.resource_fields = ResourceFieldsService(self.nested)
        self.research_fields = ResearchFieldsService(self.nested)
        self.source = SourceEditingService(self.nested)

    def entry(self, path: str) -> ContentData | RawDocument | None:
        return self._raw_documents.get(path) or self._documents.get(path)

    def document_entries(self) -> dict[str, ContentData | RawDocument]:
        """Enumerate registered identities for same-lock read-only validation."""
        return {**self._documents, **self._raw_documents}

    def require_content(self, path: str) -> ContentData:
        entry = self.entry(path)
        if isinstance(entry, RawDocument):
            raise EditingError("SOURCE_INVALID", "当前源码无效，请先修复 JSON。", path, entry.source_error)
        if entry is None:
            raise EditingError("DOCUMENT_NOT_OPEN", "请先打开要编辑的内容。", path)
        return entry

    def _snapshot(self, path: str) -> _DocumentState:
        entry = self.entry(path)
        if entry is None:
            raise EditingError("DOCUMENT_NOT_OPEN", "请先打开要编辑的内容。", path)
        return _DocumentState(entry, deepcopy(entry.data) if isinstance(entry, ContentData) else None,
                              self.nested.snapshot(path))

    def _install(self, path: str, state: _DocumentState) -> None:
        current = self.entry(path)
        if isinstance(state.entry, RawDocument):
            if isinstance(current, ContentData):
                self.session.detach_content(path[8:], current)
            self._documents.pop(path, None)
            self._raw_documents[path] = state.entry
        else:
            self.session.attach_content(path[8:], state.entry)
            state.entry.data.clear()
            state.entry.data.update(deepcopy(state.data))
            self._raw_documents.pop(path, None)
            self._documents[path] = state.entry
        self.nested.restore(path, state.form)

    def _restore(self, path: str, state: _DocumentState) -> None:
        before = self._snapshot(path)
        try:
            self._install(path, state)
        except Exception as error:
            try:
                # Registration may have succeeded before a later adapter error.
                # Roll back only the candidate owned by this transaction.
                if (isinstance(before.entry, RawDocument) and isinstance(state.entry, ContentData)
                        and self.session.loaded_content(path[8:]) is state.entry
                        and not isinstance(self.entry(path), ContentData)):
                    self.session.detach_content(path[8:], state.entry)
                self._install(path, before)
            except Exception as rollback_error:
                raise ExceptionGroup("源码状态切换失败，恢复原状态也失败。", [error, rollback_error]) from error
            raise

    def _dirty(self, path: str) -> bool:
        current, saved = self.entry(path), self._saved_entries[path]
        if isinstance(current, RawDocument):
            return not isinstance(saved, RawDocument) or current.source_text != saved.source_text
        return isinstance(saved, RawDocument) or not json_values_equal(current.data, self._saved[path])

    def reference_candidates(self, payload: dict, *, resource: bool = False, weapon: bool = False, research: bool = False) -> dict:
        path = payload.get("path")
        if not isinstance(path, str) or path not in self._opened:
            raise EditingError("DOCUMENT_NOT_OPEN", "请先打开要编辑的内容。")
        if "expectedRevision" in payload:
            self.check_revision(payload)
        content = self.require_content(path)
        try:
            if research:
                return self.research_fields.reference_candidates(content, path, payload)
            if resource:
                return self.resource_fields.reference_candidates(content, path, payload)
            if weapon:
                return self.weapon_forms.weapon_reference_candidates(content, path, payload)
            if "objectPath" not in payload or payload["objectPath"] == []:
                field = self.forms.field(content, path, payload.get("field"))
                return self.references.read(field, content.data.get(field["name"]), payload.get("query", ""))
            return self.nested.reference_candidates(content, path, payload)
        except ValueError as exc:
            raise EditingError("INVALID_REFERENCE", str(exc), path) from exc

    def check_revision(self, payload: dict) -> None:
        if type(payload.get("expectedRevision")) is not int or payload["expectedRevision"] != self.revision:
            raise EditingError("STALE_REVISION", "内容已更新，请刷新后重试。")

    def has_dirty(self) -> bool:
        return any(self._dirty(path) for path in self._opened)

    def opened(self, path: str, content: ContentData | RawDocument) -> dict:
        first_open = self.entry(path) is None
        if first_open:
            if isinstance(content, RawDocument):
                self._raw_documents[path] = content
            else:
                self._documents[path] = content
                self._saved[path] = deepcopy(content.data)
            self._saved_entries[path] = content
        if path not in self._opened:
            self._opened[path] = None
            self.revision += 1
        document = self.document(path)
        if first_open:
            self._saved_forms[path] = self.nested.snapshot(path)
        return document

    def document(self, path: str) -> dict:
        content = self.entry(path)
        common = {"sessionId": self.session_id, "path": path, "name": content.name,
                  "category": content.category, "fieldNames": deepcopy(get_field_names_zh()),
                  "fieldDocs": deepcopy(get_field_docs()), "revision": self.revision, "dirty": self._dirty(path)}
        if isinstance(content, RawDocument):
            return {**common, "validData": False, "data": None, "form": None, "contentType": "Unknown",
                    "sourceText": content.source_text, "sourceError": deepcopy(content.source_error)}
        kind = content.data.get("type", "UnitType" if content.category == "units" else "Weapon" if content.category == "weapons" else "Block")
        kind = kind if isinstance(kind, str) else "Unknown"
        try:
            form = self.nested.plan(content, path)
        except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
            # A renderer/metadata limitation must not turn a committed legal
            # source transaction into a reported write failure.
            form = {"objectPath": [], "groups": [], "addableGroups": [],
                    "contentType": normalize_content_type(kind), "knownType": False,
                    "notice": "表单诊断暂时不可用，请检查离线资料或内容结构。"}
        return {**common, "validData": True, "contentType": normalize_content_type(kind),
                "data": deepcopy(content.data), "form": form,
                "sourceText": self.source.encode(content.data), "sourceError": None}

    def set_source(self, payload: dict) -> dict:
        self.check_revision(payload)
        path = payload.get("path")
        if not isinstance(path, str) or path not in self._opened:
            raise EditingError("DOCUMENT_NOT_OPEN", "请先打开要编辑的内容。")
        entry = self.entry(path)
        try:
            if isinstance(entry, RawDocument):
                replacement = self.source._decode(payload.get("text"))
                content = ContentData(entry.name, entry.category, replacement, entry.path)
                state, _ = self.source._projection(content, path, replacement)
                command = _DocumentStateCommand(self, path, _DocumentState(content, deepcopy(replacement), state))
            else:
                command = self.source.parse(entry, path, payload.get("text"))
        except ValueError as exc:
            raise EditingError("SOURCE_INVALID", str(exc), path, self.source.error_details(exc)) from exc
        if command is not None:
            self._merge_token = object()
            self.session.command_stack.execute(DocumentCommand(command, path, f"修改 {path} 的 JSON 源码", self.changed))
        return self.state()

    def format_source(self, payload: dict) -> dict:
        if "expectedRevision" in payload:
            self.check_revision(payload)
        path = payload.get("path")
        if not isinstance(path, str) or path not in self._opened:
            raise EditingError("DOCUMENT_NOT_OPEN", "请先打开要编辑的内容。")
        try:
            return {"text": self.source.encode(self.source._decode(payload.get("text")))}
        except ValueError as exc:
            raise EditingError("SOURCE_INVALID", str(exc), path, self.source.error_details(exc)) from exc

    def state(self) -> dict:
        stack = self.session.command_stack
        interval = get_settings().get("auto_save_interval", 180)
        if type(interval) is not int or interval < 0:
            interval = 180
        return {"sessionId": self.session_id, "revision": self.revision,
                "documents": [self.document(path) for path in self._opened],
                "history": {"canUndo": stack.can_undo, "canRedo": stack.can_redo,
                            "undoDescription": stack.undo_description, "redoDescription": stack.redo_description},
                "autoSaveInterval": interval}

    def changed(self, path: str) -> None:
        self._opened[path] = None
        self.revision += 1
        if self.session.project is not None:
            self.session.project.is_dirty = self.has_dirty()

    def set_field(self, payload: dict) -> dict:
        if "objectPath" in payload and payload["objectPath"] != []:
            return self.form_action("set_field", payload)
        self.check_revision(payload)
        path, field = payload.get("path"), payload.get("field")
        if not isinstance(path, str) or path not in self._opened:
            raise EditingError("DOCUMENT_NOT_OPEN", "请先打开要编辑的内容。")
        content = self.require_content(path)
        try:
            value = self.forms.parse(content, path, payload)
        except ValueError as exc:
            raise EditingError("INVALID_FIELD_VALUE", str(exc), path) from exc
        if field in content.data and json_values_equal(content.data[field], value):
            return self.state()
        label = get_field_names_zh().get(field, field)
        self.session.command_stack.execute(DocumentCommand(
            SetFieldCommand(content.data, field, value), path, f"修改 {path} 的{label}为 {value}", self.changed,
            self._merge_token if "text" in payload else None))
        return self.state()

    def history(self, action: str, payload: dict) -> dict:
        self.check_revision(payload)
        self._merge_token = object()
        if action == "undo":
            self.session.undo()
        else:
            self.session.redo()
        return self.state()

    def form_action(self, action: str, payload: dict) -> dict:
        self.check_revision(payload)
        path = payload.get("path")
        if not isinstance(path, str) or path not in self._opened:
            raise EditingError("DOCUMENT_NOT_OPEN", "请先打开要编辑的内容。")
        try:
            service = (self.resource_fields if action.startswith(("resource_", "consume_")) else
                       self.weapon_forms if action.startswith("weapon_") else
                       self.research_fields if action.startswith(("research_", "planet_")) else self.nested)
            command = service.command(action, self.require_content(path), path, payload)
        except ValueError as exc:
            raise EditingError("INVALID_FORM_ACTION", str(exc), path) from exc
        if command is not None:
            self.session.command_stack.execute(DocumentCommand(command, path, f"{command.description}（{path}）", self.changed))
        return self.state()

    def save(self, payload: dict) -> dict:
        self.check_revision(payload)
        return self.save_paths(list(self._opened))

    def save_paths(self, paths: list[str]) -> dict:
        """Save exactly these identities, acknowledging each successful write."""
        for path in paths:
            self.require_content(path)
        # A saved state must remain reachable by undo, including partial saves.
        self._merge_token = object()
        for path in paths:
            content = self._documents[path]
            try:
                self.session.save_content(content)
                if self._on_saved is not None:
                    self._on_saved(path)
            except (OSError, ValueError, TypeError) as exc:
                raise EditingError("SAVE_FAILED", "保存失败，修改仍保留，请检查文件占用和访问权限后重试。", path) from exc
            self._saved[path] = deepcopy(content.data)
            self._saved_entries[path] = content
            self._saved_forms[path] = self.nested.snapshot(path)
            self.revision += 1
        if self.session.project is not None:
            self.session.project.is_dirty = self.has_dirty()
        return self.state()

    def close(self, payload: dict) -> dict:
        self.check_revision(payload)
        paths, decision = payload.get("paths"), payload.get("decision")
        if (not isinstance(paths, list) or len(paths) > 1024
                or any(not isinstance(path, str) or path not in self._opened for path in paths)
                or decision not in ("save", "discard", "cancel")):
            raise EditingError("INVALID_CLOSE", "关闭请求无效，请重新选择已打开的内容。")
        if decision == "cancel" or not paths:
            return self.state()
        if decision == "save":
            self.save(payload)
        elif decision == "discard":
            for path in dict.fromkeys(paths):
                content, saved = self.entry(path), self._saved_entries[path]
                if isinstance(content, RawDocument) and not self._dirty(path):
                    continue
                if isinstance(content, RawDocument) or isinstance(saved, RawDocument):
                    command = _DocumentStateCommand(self, path, _DocumentState(
                        saved, deepcopy(self._saved.get(path)), self._saved_forms[path]))
                else:
                    command = self.nested.replace(content, path, self._saved[path], self._saved_forms[path])
                if command is not None:
                    self.session.command_stack.execute(DocumentCommand(
                        command, path,
                        f"放弃 {path} 的未保存修改", self.changed))
        for path in paths:
            self._opened.pop(path, None)
        self.revision += 1
        if self.session.project is not None:
            self.session.project.is_dirty = self.has_dirty()
        return self.state()
