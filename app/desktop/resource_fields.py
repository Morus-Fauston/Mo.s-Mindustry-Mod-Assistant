"""Legacy resource list, slot and consumes routes over one nested snapshot stack."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from uuid import uuid4

from app.core.config_loader import display_name, get_field_docs, get_field_groups, get_config
from app.core.commands import ArrayInsertCommand, ArrayMoveCommand, ArrayRemoveCommand
from app.core.content_store import ContentData
from app.core.metadata import normalize_content_type
from app.desktop.forms import json_values_equal
from app.desktop.nested_forms import _NestedCommand


_CONSUMES = {
    "items": ("resource_list", "item", [{"item": "", "amount": 1}]),
    "power": ("number", "", 1.0),
    "liquid": ("resource_slot", "liquid", {"liquid": "", "amount": 1}),
    "liquids": ("resource_list", "liquid", [{"liquid": "", "amount": 1}]),
    "coolant": ("resource_slot", "liquid", {"liquid": "", "amount": 1}),
    "heat": ("number", "", 1.0),
}


@dataclass
class _Leaf:
    data: dict
    name: str
    descriptor: dict
    slot: tuple[dict, str] | None = None


class ResourceFieldsService:
    def __init__(self, nested):
        self.nested = nested
        self._routes: dict[tuple[str, str], tuple] = {}
        self._leaves: dict[tuple[str, str], _Leaf] = {}
        nested.register_plan_extension(self._augment)

    def _id(self, address, field):
        if not isinstance(field, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", field):
            raise ValueError("资源字段名称无效。")
        return self.nested._key(address), field

    def _augment(self, content, path, state, plan, nodes, budget):
        self._routes = {}
        self._leaves = {}
        for data, forms, document, node, scalar in list(nodes.values()):
            if not node["knownType"] or scalar is not None:
                continue
            configuration = get_field_groups().get(normalize_content_type(node["contentType"]), {})
            for group in node["groups"]:
                widgets = configuration.get(group["id"], {}).get("widgets", {})
                for descriptor in group["fields"]:
                    route = widgets.get(descriptor["name"], {})
                    kind = route.get("widget")
                    if kind in ("resource_list", "resource_slot", "consumes"):
                        self._attach(data, descriptor, kind, route.get("resource_type", "item"),
                                     node["objectPath"], state, budget, bool(route.get("has_booster")))

    def _attach(self, data, descriptor, kind, resource_type, owner, state, budget, booster=False):
        name = descriptor["name"]
        address = [*owner, name]
        value = data.get(name)
        if len(address) > self.nested.MAX_DEPTH or budget[0] <= 0:
            descriptor.update(readOnly=True, validationError="资源表单显示已达上限，原值已保留。")
            return
        budget[0] -= 1
        self._routes[self._id(owner, name)] = (data, name, descriptor, resource_type, booster)
        descriptor.update(control=kind, readOnly=False, objectPath=address)
        if kind == "resource_list":
            if value is not None and not isinstance(value, list):
                descriptor.update(readOnly=True, validationError="资源列表格式无效，原值已保留。", rows=[])
                return
            values = value if isinstance(value, list) else []
            if (len(address) >= self.nested.MAX_DEPTH or len(values) > self.nested.MAX_ARRAY_ITEMS
                    or len(values) * 3 > budget[0]):
                descriptor.update(readOnly=True, validationError="资源列表显示已达上限，原值已保留。", rows=[])
                return
            key = self.nested._key(address)
            ids = state.item_ids.get(key)
            if ids is None or len(ids) != len(values):
                ids = [uuid4().hex for _ in values]
                state.item_ids[key] = ids
            budget[1].add(key)
            descriptor.update(rows=[], resourceType=resource_type, canInsert=len(values) < self.nested.MAX_ARRAY_ITEMS,
                              canRemove=bool(values), canMove=len(values) > 1)
            for entry, item_id in zip(values, ids):
                row_address = [*address, {"itemId": item_id}]
                row = {"itemId": item_id, "objectPath": row_address, "fields": []}
                budget[0] -= 3
                if isinstance(entry, dict):
                    row["fields"] = self._resource_leaves(entry, row_address, resource_type, booster)
                else:
                    row["notice"] = "此资源项不是已有字典格式，原值已保留。"
                descriptor["rows"].append(row)
        elif kind == "resource_slot":
            if value is not None and not isinstance(value, dict):
                descriptor.update(readOnly=True, validationError="资源槽格式无效，原值已保留。", fields=[], empty=False)
                return
            descriptor.update(resourceType=resource_type, empty=not bool(value),
                              fields=self._resource_leaves(value if isinstance(value, dict) else {}, address,
                                                           resource_type, False, (data, name)))
        elif kind == "consumes":
            if value is not None and not isinstance(value, dict):
                descriptor.update(readOnly=True, validationError="消耗定义格式无效，原值已保留。", children=[], addable=[])
                return
            consumes = value if isinstance(value, dict) else {}
            children = []
            for child_name, (child_kind, child_resource, _) in _CONSUMES.items():
                if child_name not in consumes:
                    continue
                child = self._descriptor(child_name, child_kind, consumes[child_name], True)
                if child_kind == "number":
                    child.update(javaType="double", minimum=0, maximum=99999, decimals=2, objectPath=address)
                    self._check_display(child)
                    self._leaves[self._id(address, child_name)] = _Leaf(consumes, child_name, child)
                else:
                    self._attach(consumes, child, child_kind, child_resource, address, state, budget, child_name == "items")
                children.append(child)
            descriptor.update(children=children, addable=[{"name": key, "label": display_name(key)}
                for key in _CONSUMES if key not in consumes])

    def _descriptor(self, name, control, value, present, default=None):
        return {"name": name, "label": display_name(name), "help": get_field_docs().get(name, ""),
                "control": control, "fieldType": {"reference": "ref", "number": "num", "boolean": "bool",
                    "resource_list": "arr", "resource_slot": "ref", "consumes": "obj"}.get(control, "str"),
                "javaType": "String", "mode": "PRIMITIVE", "nullable": False, "readOnly": False,
                "deletable": False, "present": present, "value": deepcopy(value),
                "displayValue": deepcopy(value if present else default), "defaultValue": deepcopy(default),
                "defaultSource": "既有资源控件默认值", "inactiveReason": "", "validationError": ""}

    def _resource_leaves(self, data, address, resource_type, booster, slot=None):
        if resource_type not in ("item", "liquid"):
            raise ValueError("资源类型配置无效。")
        category = "Items" if resource_type == "item" else "Liquids"
        reference = self._descriptor(resource_type, "reference", data.get(resource_type), resource_type in data, "")
        reference.update(mode="STRING_REF", refSource=category, categories=[category], nullable=slot is not None)
        amount = self._descriptor("amount", "number", data.get("amount"), "amount" in data, 1)
        amount.update(javaType="int", integer=True, minimum=1, maximum=99999, readOnly=slot is not None and not bool(data))
        descriptors = [reference, amount]
        if booster:
            toggle = self._descriptor("booster", "boolean", data.get("booster"), "booster" in data, False)
            toggle["javaType"] = "boolean"
            descriptors.append(toggle)
        for descriptor in descriptors:
            self._check_display(descriptor)
            self._leaves[self._id(address, descriptor["name"])] = _Leaf(data, descriptor["name"], descriptor, slot)
        return descriptors

    def _check_display(self, descriptor):
        if descriptor["present"]:
            try:
                self._parse(descriptor, {"value": descriptor["value"]})
            except ValueError as exc:
                descriptor["validationError"] = str(exc)

    def _parse(self, descriptor, payload):
        if ("value" in payload) == ("text" in payload):
            raise ValueError("请提供一种资源字段值。")
        value = payload.get("value")
        if "text" in payload:
            value = payload["text"]
            if not isinstance(value, str):
                raise ValueError("输入文本格式无效。")
            if descriptor["control"] == "number":
                text = value.strip()
                if len(text) > 1024 or not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", text):
                    raise ValueError("请输入完整的有限数量，空文本不等于零。")
                try:
                    number = Decimal(text)
                    if not number.is_finite() or number < descriptor["minimum"] or number > descriptor["maximum"]:
                        raise ValueError("资源数量超出支持范围。")
                    if descriptor.get("integer") and number != number.to_integral_value():
                        raise ValueError("资源数量必须为整数。")
                    if descriptor.get("decimals") == 2 and number != number.quantize(Decimal("0.01")):
                        raise ValueError("此消耗值最多保留两位小数。")
                    value = int(number) if descriptor.get("integer") else float(number)
                except InvalidOperation as exc:
                    raise ValueError("资源数量无效。") from exc
            elif descriptor["control"] == "boolean":
                raise ValueError("加速开关需要布尔值。")
        value = self.nested.forms.validate(descriptor, value)
        if descriptor["control"] == "number":
            if value > descriptor["maximum"]:
                raise ValueError("资源数量超出支持范围。")
            if descriptor.get("decimals") == 2 and Decimal(str(value)).as_tuple().exponent < -2:
                raise ValueError("此消耗值最多保留两位小数。")
        return value

    def plan(self, content, path):
        return self.nested.plan(content, path)

    def _prepare(self, content, path, payload):
        address = self.nested._address(payload)
        state = self.nested.snapshot(path)
        _, nodes = self.nested._build(content, path, state)
        if not nodes:
            raise ValueError("资源表单超出支持范围。")
        return address, state

    def reference_candidates(self, content, path, payload):
        address, state = self._prepare(content, path, payload)
        leaf = self._leaves.get(self._id(address, payload.get("field")))
        if leaf is None or leaf.descriptor["control"] != "reference":
            raise ValueError("请选择有效的资源引用字段。")
        result = self._reference(leaf, payload.get("query", ""))
        self.nested.restore(path, state)
        return result

    def _reference(self, leaf, query):
        references = self.nested.forms.references
        result = references.read(leaf.descriptor, leaf.data.get(leaf.name), query)
        # The existing resource editors support bare project item/liquid stems.
        # Core resolve_candidates currently only maps project units/blocks/weapons;
        # keep the resource adapter's established storage spelling here.
        project = references._project
        if project is None:
            return result
        resource_type = leaf.name
        directory = project.contents.content_dir / ("items" if resource_type == "item" else "liquids")
        root = project.root.resolve()
        if not directory.is_dir() or not directory.resolve().is_relative_to(root):
            return result
        category = "Items" if resource_type == "item" else "Liquids"
        names = get_config("resource_names_zh").get("items" if resource_type == "item" else "liquids", {})
        needle = query.casefold().strip()
        existing = {entry["value"] for entry in result["candidates"]}
        for index, file in enumerate(sorted(directory.glob("*.json"))):
            if index >= 10000:
                raise ValueError("工程资源候选数量超出检索上限。")
            if not file.is_file() or not file.resolve().is_relative_to(root):
                continue
            value = file.stem
            label = f"{names[value]} ({value})" if value in names else value
            if leaf.data.get(leaf.name) == value:
                result["current"] = {"value": value, "label": label, "known": True}
            if value not in existing and (not needle or needle in value.casefold() or needle in label.casefold()):
                result["candidates"].append({"value": value, "category": category, "label": label, "isProject": True})
        return result

    def command(self, action, content, path, payload):
        address, before = self._prepare(content, path, payload)
        draft = ContentData(content.name, content.category, deepcopy(content.data), content.path)
        after = deepcopy(before)
        self.nested._build(draft, path, after)
        if action == "resource_set":
            self._set_leaf(address, payload)
        elif action in ("resource_add", "resource_remove", "resource_move", "consume_add", "consume_remove"):
            route = self._routes.get(self._id(address, payload.get("field")))
            if route is None or route[2]["readOnly"]:
                raise ValueError("资源字段不可操作或已失效。")
            data, name, descriptor, resource_type, _ = route
            if action in ("consume_add", "consume_remove"):
                if descriptor["control"] != "consumes":
                    raise ValueError("请选择消耗定义。")
                key = payload.get("key")
                if not isinstance(key, str) or key not in _CONSUMES:
                    raise ValueError("不支持此消耗子项。")
                consumes = data.get(name)
                if consumes is None:
                    consumes = {}
                    data[name] = consumes
                if action == "consume_add":
                    if key in consumes:
                        raise ValueError("此消耗子项已存在。")
                    consumes[key] = deepcopy(_CONSUMES[key][2])
                else:
                    if key not in consumes:
                        raise ValueError("此消耗子项不存在。")
                    del consumes[key]
            else:
                if descriptor["control"] != "resource_list":
                    raise ValueError("请选择资源列表。")
                ids = after.item_ids[self.nested._key([*address, name])]
                if action == "resource_add":
                    if not descriptor["canInsert"]:
                        raise ValueError("资源列表已达数量上限。")
                    anchor = payload.get("beforeItemId")
                    if anchor is not None and anchor not in ids:
                        raise ValueError("资源插入位置已失效。")
                    index = len(ids) if anchor is None else ids.index(anchor)
                    if data.get(name) is None:
                        data[name] = []
                    ArrayInsertCommand(data, name, index, {resource_type: "", "amount": 1}).execute()
                    ids.insert(index, uuid4().hex)
                else:
                    item_id = payload.get("itemId")
                    if not isinstance(item_id, str) or item_id not in ids:
                        raise ValueError("资源条目已失效，请刷新后重试。")
                    index = ids.index(item_id)
                    if action == "resource_remove":
                        ArrayRemoveCommand(data, name, index).execute()
                        ids.pop(index)
                    else:
                        if "beforeItemId" not in payload:
                            raise ValueError("请指定资源移动位置。")
                        anchor = payload["beforeItemId"]
                        if anchor == item_id:
                            return None
                        if anchor is not None and anchor not in ids:
                            raise ValueError("资源移动位置已失效。")
                        remaining = [item for item in ids if item != item_id]
                        destination = len(remaining) if anchor is None else remaining.index(anchor)
                        if destination == index:
                            return None
                        ArrayMoveCommand(data, name, index, destination).execute()
                        ids.insert(destination, ids.pop(index))
        else:
            raise ValueError("不支持此资源操作。")
        _, nodes = self.nested._build(draft, path, after)
        if not nodes:
            raise ValueError("资源修改超出表单大小上限，原值已保留。")
        if json_values_equal(content.data, draft.data) and before == after:
            return None
        return _NestedCommand(self.nested, path, content.data, draft.data, before, after, "修改资源字段")

    def _set_leaf(self, address, payload):
        leaf = self._leaves.get(self._id(address, payload.get("field")))
        if leaf is None or leaf.descriptor["readOnly"]:
            raise ValueError("此资源字段不可编辑或条目已失效。")
        value = self._parse(leaf.descriptor, payload)
        if leaf.descriptor["control"] == "reference":
            try:
                self.nested.forms.references.validate(leaf.descriptor, value, leaf.data.get(leaf.name))
            except ValueError:
                if not isinstance(value, str) or len(value) > 1024 or not any(
                        entry["value"] == value for entry in self._reference(leaf, "")["candidates"]):
                    raise
        if leaf.slot:
            parent, name = leaf.slot
            if leaf.name in ("item", "liquid") and value in (None, ""):
                parent[name] = None
            else:
                replacement = deepcopy(leaf.data)
                replacement[leaf.name] = value
                replacement.setdefault("amount", 1)
                parent[name] = replacement
        else:
            leaf.data[leaf.name] = value
