"""Desktop editing orchestration over the existing core command stack."""

from __future__ import annotations

from copy import deepcopy
from typing import Callable

from app.core.commands import Command, SetFieldCommand
from app.core.config_loader import get_field_docs, get_field_names_zh
from app.core.content_store import ContentData
from app.core.metadata import normalize_content_type
from app.core.session import ProjectSession
from app.core.settings import get_settings
from app.desktop.forms import FormCommand, FormMemory, FormService, json_values_equal


class EditingError(Exception):
    def __init__(self, code: str, message: str, path: str | None = None):
        super().__init__(message)
        self.code, self.path = code, path


class DocumentCommand(Command):
    """Retain document identity when session-wide history reopens a closed tab."""

    def __init__(self, command: Command, path: str, description: str, on_change: Callable[[str], None]):
        self.command, self.path = command, path
        self._description, self._on_change = description, on_change

    @property
    def description(self) -> str:
        return self._description

    def execute(self) -> None:
        self.command.execute()
        self._on_change(self.path)

    def undo(self) -> None:
        self.command.undo()
        self._on_change(self.path)

    def merge_with(self, other: Command) -> Command | None:
        if isinstance(other, DocumentCommand) and other.path == self.path:
            merged = self.command.merge_with(other.command)
            if merged is not None:
                return DocumentCommand(merged, self.path, other.description, self._on_change)
        return None


class EditingService:
    def __init__(self, session: ProjectSession, session_id: str | None, revision: int = 0):
        self.session, self.session_id, self.revision = session, session_id, revision
        self._documents: dict[str, ContentData] = {}
        self._opened: dict[str, None] = {}
        self._saved: dict[str, dict] = {}
        self._saved_forms: dict[str, FormMemory] = {}
        self.forms = FormService(session.metadata)

    def check_revision(self, payload: dict) -> None:
        if type(payload.get("expectedRevision")) is not int or payload["expectedRevision"] != self.revision:
            raise EditingError("STALE_REVISION", "内容已更新，请刷新后重试。")

    def has_dirty(self) -> bool:
        return any(not json_values_equal(self._documents[path].data, self._saved[path]) for path in self._opened)

    def opened(self, path: str, content: ContentData) -> dict:
        if path not in self._documents:
            self._documents[path] = content
            self._saved[path] = deepcopy(content.data)
            self._saved_forms[path] = self.forms.snapshot(path)
        if path not in self._opened:
            self._opened[path] = None
            self.revision += 1
        return self.document(path)

    def document(self, path: str) -> dict:
        content = self._documents[path]
        kind = content.data.get("type", "UnitType" if content.category == "units" else "Weapon" if content.category == "weapons" else "Block")
        kind = kind if isinstance(kind, str) else "Unknown"
        return {"sessionId": self.session_id, "path": path, "name": content.name,
                "category": content.category, "contentType": normalize_content_type(kind),
                "data": deepcopy(content.data), "fieldNames": deepcopy(get_field_names_zh()),
                "fieldDocs": deepcopy(get_field_docs()), "revision": self.revision,
                "dirty": not json_values_equal(content.data, self._saved[path]), "form": self.forms.plan(content, path)}

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
        self.check_revision(payload)
        path, field = payload.get("path"), payload.get("field")
        if not isinstance(path, str) or path not in self._opened:
            raise EditingError("DOCUMENT_NOT_OPEN", "请先打开要编辑的内容。")
        content = self._documents[path]
        try:
            value = self.forms.parse(content, path, payload)
        except ValueError as exc:
            raise EditingError("INVALID_FIELD_VALUE", str(exc), path) from exc
        if field in content.data and json_values_equal(content.data[field], value):
            return self.state()
        label = get_field_names_zh().get(field, field)
        self.session.command_stack.execute(DocumentCommand(
            SetFieldCommand(content.data, field, value), path, f"修改 {path} 的{label}为 {value}", self.changed))
        return self.state()

    def history(self, action: str, payload: dict) -> dict:
        self.check_revision(payload)
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
            command = self.forms.command(action, self._documents[path], path, payload)
        except ValueError as exc:
            raise EditingError("INVALID_FORM_ACTION", str(exc), path) from exc
        if command is not None:
            name = payload.get("field") or payload.get("group")
            from app.core.form_labels import GROUP_LABELS
            label = get_field_names_zh().get(name, GROUP_LABELS.get(name, name))
            verb = {"add_field": "添加字段", "delete_field": "删除字段", "add_group": "添加字段组",
                    "delete_group": "删除字段组", "set_capability": "开启能力" if payload.get("enabled") else "关闭能力"}[action]
            self.session.command_stack.execute(DocumentCommand(command, path, f"{verb} {label}（{path}）", self.changed))
        return self.state()

    def save(self, payload: dict) -> dict:
        self.check_revision(payload)
        for path in self._opened:
            content = self._documents[path]
            try:
                self.session.save_content(content)
            except (OSError, ValueError, TypeError) as exc:
                raise EditingError("SAVE_FAILED", "保存失败，修改仍保留，请检查文件占用和访问权限后重试。", path) from exc
            self._saved[path] = deepcopy(content.data)
            self._saved_forms[path] = self.forms.snapshot(path)
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
                content = self._documents[path]
                if not json_values_equal(content.data, self._saved[path]) or self.forms.snapshot(path) != self._saved_forms[path]:
                    self.session.command_stack.execute(DocumentCommand(
                        FormCommand(self.forms, path, content.data, self._saved[path], self._saved_forms[path]), path,
                        f"放弃 {path} 的未保存修改", self.changed))
        for path in paths:
            self._opened.pop(path, None)
        self.revision += 1
        if self.session.project is not None:
            self.session.project.is_dirty = self.has_dirty()
        return self.state()
