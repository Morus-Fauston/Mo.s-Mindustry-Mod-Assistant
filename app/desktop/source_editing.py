"""JSON source transactions over the existing content and nested form state.

Syntax/transport safety is a write gate. Game-schema diagnostics are not: valid
JSON may retain unknown fields, types, references and existing business errors.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import os
from math import isfinite
from pathlib import Path
from typing import Callable

from app.core.commands import Command, ReplaceDataCommand
from app.core.content_store import ContentData
from app.desktop.forms import FormService, json_values_equal
from app.desktop.nested_forms import NestedFormService, NestedFormState


@dataclass(frozen=True)
class RawDocument:
    """A readable but invalid source has no fabricated core content object."""

    name: str
    category: str
    path: Path
    source_text: str
    source_error: dict


class _SourceCommand(Command):
    def __init__(self, nested: NestedFormService, path: str, data: dict, replacement: dict,
                 before: NestedFormState, after: NestedFormState):
        self._nested, self._path = nested, path
        self._data = data
        self._replace = ReplaceDataCommand(data, replacement)
        self._before, self._after = deepcopy(before), deepcopy(after)

    @property
    def description(self) -> str:
        return "修改 JSON 源码"

    def execute(self) -> None:
        self._apply(self._replace.execute, self._after)

    def undo(self) -> None:
        self._apply(self._replace.undo, self._before)

    def rekey_document(self, old: str, new: str) -> None:
        if self._path == old:
            self._path = new

    def _apply(self, replace: Callable[[], None], state: NestedFormState) -> None:
        previous_data = deepcopy(self._data)
        previous_state = self._nested.snapshot(self._path)
        try:
            replace()
            self._nested.restore(self._path, state)
        except Exception as error:
            # CommandStack only moves history after this method succeeds. Keep
            # data and form identities at the same history point on failure.
            try:
                self._data.clear()
                self._data.update(previous_data)
                self._nested.restore(self._path, previous_state)
            except Exception as rollback_error:
                raise ExceptionGroup("源码修改失败，恢复原状态也失败。", [error, rollback_error]) from error
            raise


class SourceEditingService:
    """Return commands; only the caller may execute them on its session stack."""

    MAX_BYTES = 4 * 1024 * 1024
    MAX_DEPTH = 64
    MAX_NODES = 100_000

    def __init__(self, nested: NestedFormService):
        self.nested = nested

    @staticmethod
    def error_details(error: ValueError) -> dict:
        details = {"message": str(error)}
        if isinstance(error.__cause__, json.JSONDecodeError):
            details.update(line=error.__cause__.lineno, column=error.__cause__.colno)
        return details

    @staticmethod
    def encode(data: dict) -> str:
        return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)

    @classmethod
    def _decode(cls, text: str) -> dict:
        if not isinstance(text, str):
            raise ValueError("JSON 源码必须为文本。")
        try:
            if len(text) > cls.MAX_BYTES or len(text.encode("utf-8")) > cls.MAX_BYTES:
                raise ValueError("JSON 源码大小超过允许上限。")
        except UnicodeError as exc:
            raise ValueError("JSON 源码包含无法编码的字符。") from exc
        depth = 0
        quoted = escaped = False
        # Bound nesting before invoking Python's recursive JSON decoder; braces
        # inside quoted strings do not contribute to structural depth.
        for character in text:
            if quoted:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    quoted = False
            elif character == '"':
                quoted = True
            elif character in "[{":
                depth += 1
                if depth > cls.MAX_DEPTH:
                    raise ValueError("JSON 嵌套层数超过允许上限。")
            elif character in "]}":
                depth -= 1
        try:
            # Python accepts these JavaScript extensions by default. JSON does
            # not, and non-finite numbers cannot cross the desktop JSON bridge.
            replacement = json.loads(text, parse_constant=cls._nonfinite)
        except json.JSONDecodeError as exc:
            raise ValueError(f"第 {exc.lineno} 行第 {exc.colno} 列：JSON 语法无效。") from exc
        except (ValueError, RecursionError) as exc:
            raise ValueError("JSON 数字无效、不是有限值或超过可解析范围。") from exc
        if not isinstance(replacement, dict):
            raise ValueError("JSON 顶层必须是对象。")
        pending = [replacement]
        count = 0
        while pending:
            value = pending.pop()
            count += 1
            if count > cls.MAX_NODES:
                raise ValueError("JSON 节点数量超过允许上限。")
            if isinstance(value, dict):
                pending.extend(value.keys())
                pending.extend(value.values())
            elif isinstance(value, list):
                pending.extend(value)
            elif isinstance(value, float) and not isfinite(value):
                raise ValueError("JSON 数字必须是有限值。")
            elif isinstance(value, str):
                try:
                    value.encode("utf-8")
                except UnicodeError as exc:
                    raise ValueError("JSON 字段名或文本包含无法编码的字符。") from exc
        # The existing text writer uses indent=2 and platform newlines. Bound
        # that representation too so accepted source can be saved and reopened.
        saved_text = cls.encode(replacement).replace("\n", os.linesep) + os.linesep
        if len(saved_text.encode("utf-8")) > cls.MAX_BYTES:
            raise ValueError("JSON 格式化后的保存大小超过允许上限。")
        return replacement

    @staticmethod
    def _nonfinite(value: str):
        raise ValueError("JSON 不支持非有限数字。")

    @staticmethod
    def _identity(content: ContentData, path: str) -> None:
        if not isinstance(content, ContentData) or not isinstance(content.data, dict):
            raise ValueError("源码编辑需要当前已打开的 JSON 内容对象。")
        if not isinstance(path, str) or not path:
            raise ValueError("当前内容身份无效。")

    def _projection(self, content: ContentData, path: str, replacement: dict) -> tuple[NestedFormState, dict]:
        isolated = NestedFormService(self.nested.metadata, FormService(self.nested.metadata, self.nested.forms.references))
        candidate = ContentData(content.name, content.category, replacement, content.path)
        try:
            plan = isolated.plan(candidate, path)
        except (OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError):
            # Metadata/renderer limitations are diagnostics, not JSON syntax
            # errors. In particular custom types must remain source-editable.
            return NestedFormState(), {"objectPath": [], "groups": [], "addableGroups": [],
                                       "contentType": "Unknown", "knownType": False,
                                       "notice": "表单诊断暂时不可用，请检查离线资料或内容结构。"}
        return isolated.snapshot(path), plan

    def parse(self, content: ContentData, path: str, text: str) -> Command | None:
        self._identity(content, path)
        replacement = self._decode(text)
        if json_values_equal(content.data, replacement):
            return None
        # New source owns its values. Old capability caches and same-length array
        # item IDs must not be accidentally attached to the replacement tree.
        after, _ = self._projection(content, path, replacement)
        return _SourceCommand(self.nested, path, content.data, replacement,
                              self.nested.snapshot(path), after)

    def diagnostics(self, content: ContentData, path: str, text: str) -> list[dict]:
        """Read-only form diagnostics, not full game validation or a write gate.

        Diagnostic objectPath uses numeric array indices rather than ephemeral
        edit item IDs; it identifies locations in this source text only.
        """
        self._identity(content, path)
        _, plan = self._projection(content, path, self._decode(text))
        issues = []
        pending = [(plan, [])]
        while pending:
            node, address = pending.pop()
            if node.get("notice"):
                issues.append({"objectPath": address, "field": "", "severity": "warning", "message": node["notice"]})
            for group in node.get("groups", []):
                for descriptor in group["fields"]:
                    if descriptor.get("validationError"):
                        issues.append({"objectPath": address, "field": descriptor["name"], "severity": "error",
                                       "message": descriptor["validationError"]})
                    if descriptor.get("child"):
                        pending.append((descriptor["child"], [*address, descriptor["name"]]))
                    for item in descriptor.get("items", []):
                        item_address = [*address, descriptor["name"], item["index"]]
                        if item.get("form"):
                            pending.append((item["form"], item_address))
                        elif item.get("field", {}).get("validationError"):
                            issues.append({"objectPath": item_address, "field": "", "severity": "error",
                                           "message": item["field"]["validationError"]})
                        elif item.get("notice"):
                            issues.append({"objectPath": item_address, "field": "", "severity": "warning", "message": item["notice"]})
        return issues
