"""Bounded recursive forms and reversible session-only array identities.

The workspace owns session/revision checks and executes returned commands through
its existing DocumentCommand. This service never saves or creates another stack.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
import re
from uuid import uuid4

from app.core.commands import ArrayInsertCommand, ArrayMoveCommand, ArrayRemoveCommand, Command, ReplaceDataCommand
from app.core.config_loader import get_field_groups
from app.core.content_store import ContentData
from app.core.form_types import BULLET_TYPES, UNIT_TYPES, TYPE_LABELS
from app.core.metadata import ClassDef, FieldDef, normalize_content_type
from app.desktop.forms import FormMemory, FormService, json_values_equal


@dataclass
class NestedFormState:
    root: FormMemory = field(default_factory=FormMemory)
    memories: dict[str, FormMemory] = field(default_factory=dict)
    item_ids: dict[str, list[str]] = field(default_factory=dict)


class _NodeForms(FormService):
    def __init__(self, metadata, references, kind: str, definition: ClassDef):
        super().__init__(metadata, references)
        self.kind, self.definition = kind, definition

    def context(self, content):
        return ({**content.data, "type": self.kind}, self.definition,
                get_field_groups().get(normalize_content_type(self.kind), {}))


class _NestedCommand(Command):
    def __init__(self, service, path, data, replacement, before, after, description):
        self._replace = ReplaceDataCommand(data, replacement)
        self._service, self._path = service, path
        self._before, self._after = deepcopy(before), deepcopy(after)
        self._description = description

    @property
    def description(self):
        return self._description

    def execute(self):
        self._replace.execute()
        self._service.restore(self._path, self._after)

    def undo(self):
        self._replace.undo()
        self._service.restore(self._path, self._before)

    def rekey_document(self, old: str, new: str) -> None:
        if self._path == old:
            self._path = new


class NestedFormService:
    MAX_DEPTH = 12
    MAX_NODES = 2000
    MAX_ARRAY_ITEMS = 512
    MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
    _SCALAR_TYPES = {"String", "boolean", "int", "short", "long", "float", "double", "Color"}

    def __init__(self, metadata, forms: FormService):
        self.metadata, self.forms = metadata, forms
        self._states: dict[str, NestedFormState] = {}
        self._plan_extensions = []
        self._families = {}

    def register_family(self, base_type: str, *, choices: tuple[dict[str, str], ...],
                        default_type: str, create_default, project_definition=None) -> None:
        """Register a specialized object family on this session's form routes.

        Defaults apply only on explicit insertion. Existing objects with absent
        or unsupported types remain unknown until the user selects a type.
        """
        if (not isinstance(base_type, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", base_type)
                or base_type in self._families or not callable(create_default)
                or project_definition is not None and not callable(project_definition)):
            raise ValueError("表单类型族注册无效或重复。")
        if (not isinstance(choices, tuple) or not choices
                or any(not isinstance(item, dict) or set(item) != {"value", "label"}
                       or not isinstance(item["value"], str)
                       or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", item["value"])
                       or not isinstance(item["label"], str) or not item["label"] for item in choices)):
            raise ValueError("表单类型选项无效。")
        values = tuple(item["value"] for item in choices)
        if len(set(values)) != len(values) or default_type not in values:
            raise ValueError("表单默认类型或选项重复。")
        self._families[base_type] = {
            "choices": deepcopy(choices), "values": values, "default_type": default_type,
            "create_default": create_default, "project_definition": project_definition,
        }

    def register_plan_extension(self, callback) -> None:
        """Attach a session-owned specialized route before sidecar pruning.

        Extensions receive (content, path, state, plan, nodes, budget), may add
        descriptors and visited array identities to budget[1], and must never
        mutate content data. The same hook runs on detached command drafts.
        """
        if not callable(callback):
            raise TypeError("表单扩展必须可调用。")
        if callback not in self._plan_extensions:
            self._plan_extensions.append(callback)

    def snapshot(self, path: str) -> NestedFormState:
        state = deepcopy(self._states.get(path, NestedFormState()))
        state.root = self.forms.snapshot(path)
        return state

    def restore(self, path: str, state: NestedFormState) -> None:
        if not isinstance(state, NestedFormState):
            raise ValueError("嵌套表单状态无效。")
        self._states[path] = deepcopy(state)
        self.forms.restore(path, state.root)

    def drop_state(self, path: str) -> None:
        self._states.pop(path, None)
        self.forms.drop_state(path)

    def move_state(self, old: str, new: str) -> None:
        state = self.snapshot(old)
        self.restore(new, state)
        self.drop_state(old)

    def replace(self, content: ContentData, path: str, data: dict,
                state: NestedFormState) -> Command | None:
        """Restore saved document data and all form sidecars in one command."""
        if not isinstance(data, dict) or not isinstance(state, NestedFormState):
            raise ValueError("保存的文档或嵌套表单状态无效。")
        before = self.snapshot(path)
        if json_values_equal(content.data, data) and before == state:
            return None
        return _NestedCommand(self, path, content.data, data, before, state, "恢复保存的文档")

    @staticmethod
    def _key(address: list) -> str:
        return json.dumps(address, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _address(self, payload: dict) -> list:
        address = payload.get("objectPath", [])
        if not isinstance(address, list) or len(address) > self.MAX_DEPTH:
            raise ValueError("嵌套对象地址无效或过深。")
        for segment in address:
            if isinstance(segment, str) and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", segment):
                continue
            if (isinstance(segment, dict) and set(segment) == {"itemId"}
                    and isinstance(segment["itemId"], str) and re.fullmatch(r"[0-9a-f]{32}", segment["itemId"])):
                continue
            raise ValueError("对象地址只能使用字段名和当前会话项标识。")
        return address

    def _definition(self, data, base):
        family = self._families.get(base)
        kind = data.get("type", "BasicBulletType" if base == "BulletType" else base)
        choices = (family["values"] if family else
                   BULLET_TYPES if base == "BulletType" else UNIT_TYPES if base == "UnitType" else ())
        if (not isinstance(kind, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", kind)
                or family and ("type" not in data or kind not in choices)
                or choices and kind not in (*choices, base)):
            return str(kind), ClassDef("Unknown", "Unknown", None), False, choices
        try:
            definition = self.metadata.get_class(kind)
        except KeyError:
            return kind, ClassDef(kind, kind, None), False, choices
        if (not choices or family) and kind != base:
            ancestor, seen = definition, set()
            while ancestor.name != base and ancestor.parent and ancestor.name not in seen:
                seen.add(ancestor.name)
                try:
                    ancestor = self.metadata.get_class(ancestor.parent)
                except KeyError:
                    break
            if ancestor.name != base:
                return kind, ClassDef("Unknown", "Unknown", None), False, choices
        if family and family["project_definition"]:
            definition = family["project_definition"](kind, definition)
        return kind, definition, True, choices

    @staticmethod
    def _base(content):
        return {"units": "UnitType", "weapons": "Weapon"}.get(content.category, "Block")

    def _build(self, content, path, state):
        if not isinstance(content, ContentData) or not isinstance(content.data, dict):
            raise ValueError("内容必须是当前文档的 JSON 对象。")
        try:
            too_large = len(json.dumps(content.data, ensure_ascii=False).encode("utf-8")) > self.MAX_DOCUMENT_BYTES
        except (RecursionError, TypeError, ValueError) as exc:
            raise ValueError("内容嵌套过深或不是有效 JSON 数据。") from exc
        if too_large:
            return {"objectPath": [], "contentType": self._base(content), "knownType": False,
                    "groups": [], "addableGroups": [], "notice": "表单数据大小已达上限，原始数据完整保留。"}, {}
        nodes = {}
        budget = [self.MAX_NODES, set()]
        plan = self._object(content.data, self._base(content), [], content, path, state, nodes, budget)
        for extension in self._plan_extensions:
            extension(content, path, state, plan, nodes, budget)
        state.item_ids = {key: value for key, value in state.item_ids.items() if key in budget[1]}
        state.memories = {key: value for key, value in state.memories.items() if key in nodes}
        return plan, nodes

    def _object(self, data, base, address, content, path, state, nodes, budget):
        if len(address) > self.MAX_DEPTH or budget[0] <= 0:
            return {"objectPath": deepcopy(address), "contentType": base, "knownType": False,
                    "groups": [], "addableGroups": [], "notice": "嵌套显示已达上限，原始数据完整保留。"}
        budget[0] -= 1
        key = self._key(address)
        kind, definition, known, choices = self._definition(data, base)
        forms = _NodeForms(self.metadata, self.forms.references, kind, definition)
        forms.restore(key, state.memories.get(key, FormMemory()) if address else state.root)
        document = ContentData(content.name, content.category, data, content.path)
        plan = forms.plan(document, key)
        plan.update(objectPath=deepcopy(address), contentType=kind, knownType=known)
        if choices:
            labels = ({item["value"]: item["label"] for item in self._families[base]["choices"]}
                      if base in self._families else TYPE_LABELS)
            plan["typeSelector"] = {"value": data.get("type"), "choices": [
                {"value": value, "label": labels.get(value, value)} for value in choices
                if normalize_content_type(value) in self.metadata.available_classes]}
        if not known:
            plan["notice"] = "未识别此类型，原始数据已保留；可显式选择受支持类型。"
        nodes[key] = (data, forms, document, plan, None)
        definitions = {item.name: item for item in definition.fields}
        for group in plan["groups"]:
            config = get_field_groups().get(normalize_content_type(kind), {}).get(group["id"], {})
            for descriptor in group["fields"]:
                budget[0] -= 1
                if not known:
                    descriptor.update(control="readonly", readOnly=True)
                    continue
                field_def = definitions.get(descriptor["name"])
                if not field_def or config.get("widgets", {}).get(field_def.name):
                    continue
                if budget[0] <= 0 or len(address) >= self.MAX_DEPTH:
                    if field_def.mode in ("ARRAY", "INLINE_OBJECT"):
                        descriptor.update(control="readonly", readOnly=True, validationError="嵌套显示已达上限，原值已保留。")
                    continue
                if field_def.mode == "ARRAY" and field_def.name != "weapons":
                    self._array(descriptor, field_def, data.get(field_def.name), [*address, field_def.name],
                                content, path, state, nodes, budget)
                if field_def.mode == "INLINE_OBJECT" and field_def.inline_type and field_def.inline_type != "ObjectMap":
                    try:
                        self.metadata.get_class(field_def.inline_type)
                    except KeyError:
                        continue
                    value = data.get(field_def.name)
                    descriptor.update(control="object", readOnly=False, canCreate=value is None)
                    if isinstance(value, dict):
                        descriptor["child"] = self._object(value, field_def.inline_type, [*address, field_def.name],
                            content, path, state, nodes, budget)
                    elif value is not None:
                        descriptor.update(readOnly=True, canCreate=False, validationError="对象格式无效，原值已保留。")
        return plan

    def _array(self, descriptor, definition, values, address, content, path, state, nodes, budget):
        kind = definition.element_type
        if not isinstance(kind, str) or kind in ("Ability", "Weapon") and kind not in self._families:
            return
        if kind not in self._SCALAR_TYPES:
            try:
                self.metadata.get_class(kind)
            except KeyError:
                return
        if values is not None and not isinstance(values, list):
            descriptor["validationError"] = "数组格式无效，原值已保留。"
            return
        values = values if values is not None else []
        if len(values) > self.MAX_ARRAY_ITEMS or len(address) >= self.MAX_DEPTH or len(values) > budget[0]:
            descriptor["validationError"] = "数组显示已达上限，原始数据完整保留。"
            return
        key = self._key(address)
        budget[1].add(key)
        ids = state.item_ids.get(key)
        if ids is None or len(ids) != len(values):
            ids = [uuid4().hex for _ in values]
            state.item_ids[key] = ids
        descriptor.update(control="array", readOnly=False, canInsert=len(values) < self.MAX_ARRAY_ITEMS,
                          canRemove=bool(values), canMove=len(values) > 1, items=[])
        for index, (value, item_id) in enumerate(zip(values, ids)):
            budget[0] -= 1
            item_address = [*address, {"itemId": item_id}]
            item = {"itemId": item_id, "index": index}
            if kind in self._SCALAR_TYPES:
                item_key = self._key(item_address)
                scalar = FieldDef("value", kind, "PRIMITIVE", nullable=False)
                forms = _NodeForms(self.metadata, self.forms.references, "ArrayItem", ClassDef("ArrayItem", "ArrayItem", None, [scalar]))
                data = {"value": value}
                document = ContentData(content.name, content.category, data, content.path)
                scalar_plan = forms.plan(document, item_key)
                scalar_plan.update(objectPath=item_address, contentType=kind, knownType=True)
                item["field"] = self._field(scalar_plan, "value")
                nodes[item_key] = (data, forms, document, scalar_plan, (values, index))
            elif isinstance(value, dict):
                item["form"] = self._object(value, kind, item_address, content, path, state, nodes, budget)
            else:
                item["notice"] = "该数组项不是受支持的对象，原值已保留。"
            descriptor["items"].append(item)

    def plan(self, content: ContentData, path: str) -> dict:
        state = self.snapshot(path)
        plan, _ = self._build(content, path, state)
        self.restore(path, state)
        return plan

    @staticmethod
    def _field(plan, name):
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name):
            raise ValueError("字段名称无效。")
        for group in plan["groups"]:
            for descriptor in group["fields"]:
                if descriptor["name"] == name:
                    return descriptor
        raise ValueError("字段当前不可编辑，请先添加字段。")

    def reference_candidates(self, content, path, payload):
        address = self._address(payload)
        state = self.snapshot(path)
        _, nodes = self._build(content, path, state)
        key = self._key(address)
        if key not in nodes or not nodes[key][3]["knownType"]:
            raise ValueError("嵌套对象或数组项已失效，请刷新后重试。")
        data, forms, document, plan, _ = nodes[key]
        descriptor = self._field(plan, payload.get("field"))
        result = self.forms.references.read(descriptor, data.get(descriptor["name"]), payload.get("query", ""))
        self.restore(path, state)
        return result

    def command(self, action: str, content: ContentData, path: str, payload: dict) -> Command | None:
        address = self._address(payload)
        before = self.snapshot(path)
        _, existing_nodes = self._build(content, path, before)
        key = self._key(address)
        if key not in existing_nodes:
            raise ValueError("嵌套对象或数组项已失效，或已达显示上限，请刷新后重试。")
        draft = ContentData(content.name, content.category, deepcopy(content.data), content.path)
        after = deepcopy(before)
        _, nodes = self._build(draft, path, after)
        if key not in nodes:
            raise ValueError("嵌套对象或数组项已失效，请刷新后重试。")
        data, forms, document, plan, scalar_target = nodes[key]
        if not plan["knownType"] and action != "set_type":
            raise ValueError("未知类型只保留原数据，请先选择受支持类型。")
        description = "修改嵌套表单"
        if action == "set_type":
            choices = plan.get("typeSelector", {}).get("choices", [])
            if payload.get("type") not in [choice["value"] for choice in choices]:
                raise ValueError("请选择此对象支持的类型。")
            data["type"] = payload["type"]
            description = "切换类型"
        elif action == "set_field":
            value = forms.parse(document, key, payload)
            data[payload["field"]] = value
        elif action == "create_object":
            descriptor = self._field(plan, payload.get("field"))
            if descriptor["control"] != "object" or not descriptor.get("canCreate"):
                raise ValueError("此位置不能创建对象。")
            data[descriptor["name"]] = {}
            description = "创建嵌套对象"
        elif action in ("array_insert", "array_remove", "array_move"):
            descriptor = self._field(plan, payload.get("field"))
            if descriptor["control"] != "array" or descriptor["readOnly"]:
                raise ValueError("此数组需要专用编辑器或超出支持范围。")
            name = descriptor["name"]
            array_key = self._key([*address, name])
            ids = after.item_ids[array_key]
            if action == "array_insert":
                if not descriptor["canInsert"]:
                    raise ValueError("数组项数量已达上限。")
                anchor = payload.get("beforeItemId")
                if anchor is not None and anchor not in ids:
                    raise ValueError("数组插入位置已失效。")
                index = len(ids) if anchor is None else ids.index(anchor)
                definition = next(item for item in forms.definition.fields if item.name == name)
                kind = definition.element_type
                value = ({"String": "", "boolean": False, "Color": "ffffffff"}.get(kind, 0)
                         if kind in self._SCALAR_TYPES else {})
                if kind in self._families:
                    family = self._families[kind]
                    selected = payload.get("type", family["default_type"])
                    if selected not in family["values"]:
                        raise ValueError("请选择此数组支持的类型。")
                    value = deepcopy(family["create_default"](selected))
                    if not isinstance(value, dict) or value.get("type") != selected:
                        raise ValueError("新增对象的默认值无效。")
                if data.get(name) is None:
                    data[name] = []
                ArrayInsertCommand(data, name, index, value).execute()
                ids.insert(index, uuid4().hex)
                description = "添加数组项"
            else:
                item_id = payload.get("itemId")
                if not isinstance(item_id, str) or item_id not in ids:
                    raise ValueError("数组项已失效，请刷新后重试。")
                index = ids.index(item_id)
                if action == "array_remove":
                    ArrayRemoveCommand(data, name, index).execute()
                    ids.pop(index)
                    description = "删除数组项"
                else:
                    if "beforeItemId" not in payload:
                        raise ValueError("请指定数组移动位置。")
                    anchor = payload["beforeItemId"]
                    if anchor == item_id:
                        return None
                    if anchor is not None and anchor not in ids:
                        raise ValueError("数组移动位置已失效。")
                    remaining = [item for item in ids if item != item_id]
                    destination = len(remaining) if anchor is None else remaining.index(anchor)
                    if index == destination:
                        return None
                    ArrayMoveCommand(data, name, index, destination).execute()
                    ids.insert(destination, ids.pop(index))
                    description = "移动数组项"
        elif action in ("add_field", "delete_field", "add_group", "delete_group", "set_capability"):
            command = forms.command(action, document, key, payload)
            if command is None:
                return None
            command.execute()
            if address:
                after.memories[key] = forms.snapshot(key)
            else:
                after.root = forms.snapshot(key)
        else:
            raise ValueError("不支持此嵌套操作。")
        if scalar_target is not None:
            if action != "set_field":
                raise ValueError("普通数组值只支持值编辑。")
            values, index = scalar_target
            values[index] = data["value"]
        # Capture identities for newly visible/inserted children in this same
        # history entry, and release sidecars for removed descendants.
        _, after_nodes = self._build(draft, path, after)
        if not after_nodes:
            raise ValueError("编辑后的表单数据大小超出上限，原值已保留。")
        if json_values_equal(content.data, draft.data) and before == after:
            return None
        return _NestedCommand(self, path, content.data, draft.data, before, after, description)
