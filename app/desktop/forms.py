"""Qt-free form plans and validated edits over the shared core rules."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field as dataclass_field
from decimal import Decimal, InvalidOperation
from math import isfinite
import json
import re

from app.core.config_loader import get_field_docs, get_field_groups, get_field_names_zh
from app.core.commands import Command, DeleteFieldCommand, ReplaceDataCommand, SetFieldCommand
from app.core.content_store import ContentData
from app.core.form_plan import (CAPABILITY_GROUPS, CAPABILITY_LINKAGE, compute_form_plan,
    get_addable_fields, group_visible, infer_subtype, type_default)
from app.core.field_dependencies import inactive_dependencies
from app.core.group_ops import cache_group_fields, group_field_names, remove_group_fields, resolve_field_value, restore_group_fields
from app.core.metadata import ClassDef, FieldDef, Metadata, normalize_content_type
from app.desktop.references import ReferenceService


# Configured editor semantics take precedence over the raw JSON value shape.
# `research` is the current route name for ADR-012's earlier `tech_ref`.
_WIDGET_FIELD_TYPES = {
    "research": "ref",
    "tech_ref": "ref",
    "resource_slot": "ref",
    "resource_list": "arr",
    "planet_set": "arr",
    "consumes": "obj",
}


def field_type_hint(field: FieldDef, group: dict, control: str) -> str:
    route = group.get("widgets", {}).get(field.name, {}).get("widget")
    if route in _WIDGET_FIELD_TYPES:
        return _WIDGET_FIELD_TYPES[route]
    return {"number": "num", "boolean": "bool", "color": "col"}.get(control,
        {"ARRAY": "arr", "INLINE_OBJECT": "obj", "STRING_REF": "ref"}.get(field.mode, "str"))


def color_channels(value: object) -> tuple[int, int, int]:
    """Validate supported game color formats without importing a GUI toolkit."""
    if isinstance(value, str) and re.fullmatch(r"#?(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", value):
        rgb = value.lstrip("#")[:6]
        return tuple(int(rgb[index:index + 2], 16) for index in (0, 2, 4))
    if isinstance(value, dict) and not (value.keys() - {"r", "g", "b", "a"}):
        for channel in (value.get(key, 1) for key in ("r", "g", "b", "a")):
            if type(channel) not in (int, float) or not 0 <= channel <= 1:
                raise ValueError("颜色分量必须为 0 到 1 之间的有限数字。")
        return tuple(round(value.get(key, 1) * 255) for key in ("r", "g", "b"))
    raise ValueError("颜色需要六位或八位十六进制，或 RGBA 对象。")


def select_rgb(value: str, previous: object) -> object:
    """A native RGB picker changes RGB only; alpha and representation survive."""
    color_channels(value)
    try:
        color_channels(previous)
    except ValueError:
        return value.lstrip("#")
    rgb = value.lstrip("#")
    if isinstance(previous, dict):
        result = deepcopy(previous)
        result.update({key: int(rgb[index:index + 2], 16) / 255 for key, index in (("r", 0), ("g", 2), ("b", 4))})
        return result
    prefix = "#" if previous.startswith("#") else ""
    return prefix + rgb + previous.lstrip("#")[6:]


def json_values_equal(left: object, right: object) -> bool:
    """JSON booleans and numbers are distinct, unlike Python False == 0."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(json_values_equal(value, right[key]) for key, value in left.items())
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(json_values_equal(a, b) for a, b in zip(left, right))
    return left == right


@dataclass
class FormMemory:
    cached: dict = dataclass_field(default_factory=dict)
    enabled: set[str] = dataclass_field(default_factory=set)
    deleted: set[str] = dataclass_field(default_factory=set)

    def __eq__(self, other: object) -> bool:
        return (isinstance(other, FormMemory) and self.enabled == other.enabled and self.deleted == other.deleted
                and json_values_equal(self.cached, other.cached))


class FormCommand(Command):
    """One core history entry restores JSON and its session form state together."""

    def __init__(self, service: FormService, path: str, data: dict, replacement: dict, after: FormMemory):
        self._replace = ReplaceDataCommand(data, replacement)
        self._service, self._path = service, path
        self._before, self._after = service.snapshot(path), deepcopy(after)

    def execute(self) -> None:
        self._replace.execute()
        self._service.restore(self._path, self._after)

    def undo(self) -> None:
        self._replace.undo()
        self._service.restore(self._path, self._before)

    def rekey_document(self, old: str, new: str) -> None:
        if self._path == old:
            self._path = new


class _DraftCommands:
    """Apply shared group rules only to a private draft; no second user history.

    The real content is changed exclusively by FormCommand through the session
    CommandStack. This adapter never receives the real content dictionary.
    """

    def execute(self, command: Command) -> None:
        command.execute()


class FormService:
    def __init__(self, metadata: Metadata, references: ReferenceService | None = None):
        self.metadata = metadata
        self.references = references or ReferenceService(metadata)
        self._memories: dict[str, FormMemory] = {}

    def snapshot(self, path: str) -> FormMemory:
        return deepcopy(self._memories.get(path, FormMemory()))

    def restore(self, path: str, memory: FormMemory) -> None:
        self._memories[path] = deepcopy(memory)

    def drop_state(self, path: str) -> None:
        self._memories.pop(path, None)

    def context(self, content: ContentData) -> tuple[dict, ClassDef, dict]:
        # Missing type is interpreted for display only, never written into JSON.
        data = {**content.data}
        kind = data.get("type", {"units": "UnitType", "weapons": "Weapon"}.get(content.category, "Block"))
        # Metadata class keys are identifiers, never project-supplied paths.
        kind = kind if isinstance(kind, str) and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", kind) else "Unknown"
        data["type"] = kind
        try:
            definition = self.metadata.get_class(kind)
        except KeyError:
            definition = ClassDef(kind, kind, None)
        config = get_field_groups().get(normalize_content_type(kind), {})
        return data, definition, config

    @staticmethod
    def control(field: FieldDef, group: dict) -> str:
        if field.name in ("name", "type") or group.get("widgets", {}).get(field.name):
            return "readonly"
        if field.mode == "STRING_REF" and field.java_type != "ObjectMap" and "<" not in field.java_type:
            return "reference"
        if field.mode != "PRIMITIVE":
            return "readonly"
        if field.java_type in ("int", "long", "short", "float", "double"):
            return "number"
        return {"String": "string", "boolean": "boolean", "Color": "color"}.get(field.java_type, "readonly")

    def field(self, content: ContentData, path: str, name: object) -> dict:
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name):
            raise ValueError("字段名称无效。")
        for group in self.plan(content, path)["groups"]:
            for field in group["fields"]:
                if field["name"] == name:
                    return field
        raise ValueError("该字段当前不可编辑，请通过添加字段入口操作。")

    @staticmethod
    def validate(field: dict, value: object) -> object:
        if value is None:
            if not field["nullable"]:
                raise ValueError("此字段不允许空值。")
            return None
        control = field["control"]
        if control == "number":
            if type(value) not in (int, float):
                raise ValueError("请输入有效数字。")
            try:
                finite = isfinite(value)
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError("数字必须有限。")
            kind = field["javaType"]
            if kind in ("int", "short", "long"):
                if int(value) != value:
                    raise ValueError("此字段需要整数。")
                # Long is also bounded by the lossless JSON number range in JS.
                low, high = {"short": (-32768, 32767), "int": (-2147483648, 2147483647),
                             "long": (-9007199254740991, 9007199254740991)}[kind]
                if not low <= value <= high:
                    raise ValueError("整数超出此字段可安全表示的范围。")
                value = int(value)
            elif kind == "float" and abs(value) > 3.4028234663852886e38:
                raise ValueError("数值超出单精度浮点范围。")
            if field.get("minimum") is not None and value < field["minimum"]:
                raise ValueError(f"数值不能小于 {field['minimum']}。")
        elif control == "boolean" and type(value) is not bool:
            raise ValueError("此字段需要布尔值。")
        elif control in ("string", "reference") and not isinstance(value, str):
            raise ValueError("此字段需要文本。")
        elif control == "color":
            color_channels(value)
        return value

    def parse(self, content: ContentData, path: str, payload: dict) -> object:
        field = self.field(content, path, payload.get("field"))
        if field["readOnly"]:
            raise ValueError("该字段为只读或需要专用编辑器。")
        if ("text" in payload) == ("value" in payload):
            raise ValueError("请提供一种字段值。")
        value = payload.get("value")
        if "text" in payload:
            value = payload["text"]
            if not isinstance(value, str):
                raise ValueError("输入文本格式无效。")
            if field["control"] == "number":
                text = value.strip()
                if len(text) > 1024 or not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", text):
                    raise ValueError("请输入完整的有限数字，空文本不会转换成零。")
                try:
                    if field["javaType"] in ("int", "short", "long"):
                        decimal = Decimal(text)
                        if not decimal.is_finite() or abs(decimal) > 9007199254740991 or decimal != decimal.to_integral_value():
                            raise ValueError("请输入范围内的整数。")
                        value = int(decimal)
                    else:
                        value = float(text)
                except (InvalidOperation, OverflowError) as exc:
                    raise ValueError("数字超出支持范围。") from exc
            elif field["control"] == "boolean":
                raise ValueError("布尔字段请使用开关修改。")
            elif field["control"] == "color":
                value = value.strip()
                if value.startswith("{"):
                    try:
                        value = json.loads(value)
                    except (ValueError, RecursionError) as exc:
                        raise ValueError("RGBA 颜色对象格式不正确。") from exc
        elif field["control"] == "color" and isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            value = select_rgb(value, content.data.get(field["name"]))
        value = self.validate(field, value)
        if field["control"] == "reference":
            return self.references.validate(field, value, content.data.get(field["name"]))
        return value

    def command(self, action: str, content: ContentData, path: str, payload: dict) -> Command | None:
        data, definition, config = self.context(content)
        plan = self.plan(content, path)
        shown = {group["id"]: group for group in plan["groups"]}
        group_name = payload.get("group")
        if action == "delete_field":
            descriptor = self.field(content, path, payload.get("field"))
            name = descriptor["name"]
            occurrences = [f for g in plan["groups"] for f in g["fields"] if f["name"] == name]
            if not descriptor["present"] or any(not f["deletable"] for f in occurrences):
                raise ValueError("该字段不存在或为保留字段，不能删除。")
            return DeleteFieldCommand(content.data, name)
        if not isinstance(group_name, str):
            raise ValueError("字段组名称无效。")
        group_def = config.get(group_name, {})
        if action == "add_field":
            group = shown.get(group_name)
            name = payload.get("field")
            if not group or name not in [f["name"] for f in group["addableFields"]] or name in ("name", "type"):
                raise ValueError("该字段不在此组当前的可添加清单中。")
            value = deepcopy(resolve_field_value(name, group_def, {}, definition))
            return SetFieldCommand(content.data, name, value)
        if action == "add_group":
            if group_name not in [g["id"] for g in plan["addableGroups"]]:
                raise ValueError("此字段组当前不能添加。")
        elif group_name not in shown or group_name not in config:
            raise ValueError("此字段组当前不可操作。")
        elif action == "delete_group" and shown[group_name]["locked"]:
            raise ValueError("锁定字段组不能删除。")
        elif action == "set_capability":
            if not shown[group_name]["capability"] or type(payload.get("enabled")) is not bool:
                raise ValueError("能力开关请求无效。")
            if payload["enabled"] == shown[group_name]["enabled"]:
                return None
        # Group rules operate on a detached draft. Their commands are committed
        # atomically with form state by the one real session history entry.
        draft, memory = deepcopy(content.data), self.snapshot(path)
        commands = _DraftCommands()
        enabling = action == "add_group" or (action == "set_capability" and payload["enabled"])
        if enabling:
            restore_group_fields(draft, group_def, deepcopy(memory.cached.get(group_name, {})), definition, commands, None)
            memory.deleted.discard(group_name)
            if group_name in CAPABILITY_GROUPS:
                memory.enabled.add(group_name)
            linked = CAPABILITY_LINKAGE.get(group_name) if action == "set_capability" else None
            if linked and linked in config and group_visible(config[linked], infer_subtype(data["type"], data)):
                was_enabled = linked in memory.enabled or any(name in draft for name in group_field_names(config[linked]))
                if not was_enabled:
                    restore_group_fields(draft, config[linked], deepcopy(memory.cached.get(linked, {})), definition,
                                         commands, None, restore_optional=False, existence_marker=False)
                memory.enabled.add(linked)
                memory.deleted.discard(linked)
        else:
            cached = deepcopy(cache_group_fields(draft, group_def))
            if cached:
                memory.cached[group_name] = cached
            remove_group_fields(draft, group_def, commands, None)
            memory.enabled.discard(group_name)
            if action == "delete_group":
                memory.deleted.add(group_name)
        return FormCommand(self, path, content.data, draft, memory)

    def plan(self, content: ContentData, path: str) -> dict:
        from app.core.form_labels import GROUP_LABELS

        data, definition, config = self.context(content)
        memory = self.snapshot(path)
        names, docs = get_field_names_zh(), get_field_docs()
        inactive = inactive_dependencies(data["type"], data)
        plans = compute_form_plan(definition, data, get_field_groups(), group_labels=GROUP_LABELS,
                                  deleted_groups=memory.deleted, enabled_groups=memory.enabled)
        groups = []
        for group in plans:
            if group.group_name in memory.deleted and not group.locked:
                continue
            group_config = config.get(group.group_name, {})
            enabled = group.capability_enabled
            if group.capability:
                # Required virtual fields remain in the plan even when absent.
                # They do not prove that a capability has real persisted data.
                enabled = group.group_name in memory.enabled or any(name in content.data for name in group_field_names(group_config))
            fields = []
            for item in group.fields:
                field = item.field_def
                control = self.control(field, group_config)
                default = group_config.get("defaults", {}).get(field.name, field.default)
                source = "组配置默认值" if field.name in group_config.get("defaults", {}) else "元数据默认值"
                if default is None:
                    default, source = type_default(field), "类型零值"
                present = field.name in content.data
                value = deepcopy(content.data.get(field.name))
                display = deepcopy(value if present else default)
                if field.name == "name":
                    display = content.name
                descriptor = {"name": field.name, "label": names.get(field.name, field.name),
                    "help": docs.get(field.name, ""), "javaType": field.java_type, "mode": field.mode,
                    "control": control, "fieldType": field_type_hint(field, group_config, control),
                    "nullable": field.nullable, "readOnly": control == "readonly",
                    "deletable": item.deletable and field.name not in ("name", "type"),
                    "present": present, "value": value, "displayValue": display,
                    "defaultValue": deepcopy(default), "defaultSource": source,
                    "inactiveReason": "", "validationError": ""}
                if control == "reference":
                    descriptor["refSource"] = field.ref_source
                    descriptor["categories"] = [field.ref_source] if field.ref_source else []
                if field.name in inactive:
                    reason = re.sub(r"[A-Za-z_][A-Za-z_0-9]*", lambda match:
                        {"true": "开启", "false": "关闭"}.get(match[0], names.get(match[0], match[0])), inactive[field.name])
                    descriptor["inactiveReason"] = f"当前不生效，需要：{reason}。原值已保留。"
                if control == "number":
                    descriptor["integer"] = field.java_type in ("int", "short", "long")
                    if field.name == "health":
                        descriptor["minimum"] = 0
                if present and control != "readonly":
                    try:
                        self.validate(descriptor, value)
                    except ValueError as exc:
                        descriptor["validationError"] = str(exc)
                if control == "color" and display is not None:
                    try:
                        descriptor["swatchHex"] = "#" + "".join(f"{channel:02x}" for channel in color_channels(display))
                    except ValueError:
                        pass
                fields.append(descriptor)
            candidates = get_addable_fields(definition, data, get_field_groups(), group.group_name)
            if group.capability and not enabled:
                candidates = []
            # Synthetic buckets have no configured group operation; individual
            # fields remain deletable according to their own descriptors.
            groups.append({"id": group.group_name, "label": group.label,
                "locked": group.locked or group.group_name not in config,
                "defaultExpanded": group.expanded, "capability": group.capability,
                "enabled": enabled, "fields": fields,
                "addableFields": [{"name": f.name, "label": names.get(f.name, f.name)} for f in candidates]})
        present_groups = {group["id"] for group in groups}
        subtype = infer_subtype(data["type"], data)
        addable_groups = [{"id": name, "label": GROUP_LABELS.get(name, name)}
            for name, group in config.items() if name not in present_groups and group_visible(group, subtype)
            and (group_field_names(group) or name in memory.deleted)]
        return {"groups": groups, "addableGroups": addable_groups}
