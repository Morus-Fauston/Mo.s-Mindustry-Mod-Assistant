"""Legacy research and planet-set projections on one nested form session."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from uuid import uuid4

from app.core.config_loader import display_name, get_field_docs, get_field_groups, get_field_names_zh
from app.core.content_store import ContentData
from app.core.metadata import normalize_content_type
from app.core.ref_candidates import UNLOCKABLE_CATEGORIES
from app.core.research_model import (OBJECTIVE_CATEGORIES, OBJECTIVE_TARGET_FIELDS,
                                     as_research_object, serialize_research)
from app.desktop.forms import json_values_equal
from app.desktop.nested_forms import _NestedCommand


@dataclass
class _Route:
    owner: dict
    name: str
    descriptor: dict
    view: dict | list


@dataclass
class _Leaf:
    route: _Route
    data: dict
    name: str
    descriptor: dict
    optional: bool = False


def _field_label(name, names):
    """Research translations use qualified keys; English retains the JSON key."""
    chinese = names.get(f"research.{name}", names.get(name))
    return display_name(name, {name: chinese} if chinese else {})


class ResearchFieldsService:
    """Return commands for the caller's existing stack; never own a history."""

    def __init__(self, nested):
        self.nested = nested
        self._routes = {}
        self._leaves = {}
        nested.register_plan_extension(self._augment)

    def _key(self, address, field):
        if not isinstance(field, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", field):
            raise ValueError("研究字段名称无效。")
        return self.nested._key(address), field

    def _augment(self, content, path, state, plan, nodes, budget):
        self._routes, self._leaves = {}, {}
        for data, forms, document, node, scalar in list(nodes.values()):
            if not node["knownType"] or scalar is not None:
                continue
            config = get_field_groups().get(normalize_content_type(node["contentType"]), {})
            for group in node["groups"]:
                widgets = config.get(group["id"], {}).get("widgets", {})
                for descriptor in group["fields"]:
                    kind = widgets.get(descriptor["name"], {}).get("widget")
                    if kind not in ("research", "tech_ref", "planet_set"):
                        continue
                    address = [*node["objectPath"], descriptor["name"]]
                    if len(address) > self.nested.MAX_DEPTH or budget[0] <= 0:
                        descriptor.update(readOnly=True, validationError="研究表单显示已达上限，原值已保留。")
                        continue
                    budget[0] -= 1
                    original = data.get(descriptor["name"])
                    descriptor.update(control="planet_set" if kind == "planet_set" else "research",
                                      objectPath=address, readOnly=False)
                    if kind == "planet_set":
                        self._planets(data, descriptor, address, state, budget)
                    else:
                        if original is not None and not isinstance(original, (str, dict)):
                            descriptor.update(readOnly=True, validationError="研究配置格式无效，原值已保留。", fields=[])
                            continue
                        route = _Route(data, descriptor["name"], descriptor, as_research_object(original))
                        self._routes[self._key(node["objectPath"], descriptor["name"])] = route
                        self._research(route, address, state, budget)

    def _field(self, route, data, address, name, control, *, categories=(), default=None, optional=False):
        names, docs = get_field_names_zh(), get_field_docs()
        descriptor = {"name": name, "label": _field_label(name, names),
            "help": docs.get(f"research.{name}", docs.get(name, "")),
            "control": control, "fieldType": {"reference": "ref", "number": "num", "boolean": "bool"}.get(control, "str"),
            "javaType": {"number": "int", "boolean": "boolean"}.get(control, "String"),
            "mode": "STRING_REF" if control == "reference" else "PRIMITIVE", "nullable": optional,
            "readOnly": False, "deletable": False, "present": name in data,
            "value": deepcopy(data.get(name)), "displayValue": deepcopy(data.get(name, default)),
            "defaultValue": default, "defaultSource": "既有研究控件默认值", "inactiveReason": "", "validationError": ""}
        if categories:
            descriptor.update(categories=list(categories), refSource=categories[0] if len(categories) == 1 else None)
        if control == "number":
            descriptor.update(integer=True, minimum=1, maximum=999999)
        if name in data:
            try:
                self._parse(descriptor, {"value": data[name]})
            except ValueError as exc:
                descriptor["validationError"] = str(exc)
        self._leaves[self._key(address, name)] = _Leaf(route, data, name, descriptor, optional)
        return descriptor

    def _research(self, route, address, state, budget):
        data, descriptor = route.view, route.descriptor
        if budget[0] < 5:
            descriptor.update(readOnly=True, fields=[], validationError="研究字段显示已达上限，原值已保留。")
            return
        budget[0] -= 5
        descriptor["fields"] = [
            self._field(route, data, address, "parent", "reference", categories=UNLOCKABLE_CATEGORIES, default="", optional=True),
            self._field(route, data, address, "planet", "reference", categories=("Planets",), default="", optional=True),
            self._field(route, data, address, "root", "boolean", default=False, optional=True),
            self._field(route, data, address, "name", "string", default="", optional=True),
            self._field(route, data, address, "requiresUnlock", "boolean", default=False, optional=True),
        ]
        for name in ("requirements", "objectives"):
            values = data.get(name, [])
            collection = self._collection(values, [*address, name], state, budget)
            names, docs = get_field_names_zh(), get_field_docs()
            collection.update(name=name, label=_field_label(name, names),
                              help=docs.get(f"research.{name}", docs.get(name, "")))
            descriptor[name] = collection
            for row in collection["rows"]:
                value = row["value"]
                if not isinstance(value, dict):
                    row["notice"] = "此条目不是受支持的对象，原值已保留。"
                    continue
                if name == "requirements":
                    row["fields"] = [
                        self._field(route, value, row["objectPath"], "item", "reference", categories=("Items",), default=""),
                        self._field(route, value, row["objectPath"], "amount", "number", default=1),
                    ]
                else:
                    kind = value.get("type")
                    row["typeSelector"] = {"value": kind if isinstance(kind, str) else None, "choices": [
                        {"value": choice, "label": get_field_names_zh().get(f"objective.{choice}", choice)}
                        for choice in OBJECTIVE_CATEGORIES]}
                    if not isinstance(kind, str) or kind not in OBJECTIVE_CATEGORIES:
                        row["notice"] = "未识别目标类型，原值已保留；可显式选择受支持类型。"
                        continue
                    target = OBJECTIVE_TARGET_FIELDS[kind]
                    row["fields"] = [self._field(route, value, row["objectPath"], target, "reference",
                        categories=OBJECTIVE_CATEGORIES[kind], default="")]

    def _collection(self, values, address, state, budget):
        descriptor = {"objectPath": address, "rows": [], "readOnly": False, "validationError": "",
                      "canInsert": False, "canRemove": False, "canMove": False}
        if not isinstance(values, list):
            descriptor.update(readOnly=True, validationError="列表格式无效，原值已保留。", value=deepcopy(values))
            return descriptor
        if (len(address) >= self.nested.MAX_DEPTH or len(values) > self.nested.MAX_ARRAY_ITEMS
                or len(values) * 3 + 1 > budget[0]):
            descriptor.update(readOnly=True, validationError="列表显示已达上限，原值已保留。", value=deepcopy(values))
            return descriptor
        budget[0] -= len(values) * 3 + 1
        key = self.nested._key(address)
        ids = state.item_ids.get(key)
        if ids is None or len(ids) != len(values):
            ids = [uuid4().hex for _ in values]
            state.item_ids[key] = ids
        budget[1].add(key)
        descriptor.update(canInsert=len(values) < self.nested.MAX_ARRAY_ITEMS,
                          canRemove=bool(values), canMove=len(values) > 1)
        descriptor["rows"] = [{"itemId": item_id, "objectPath": [*address, {"itemId": item_id}],
                               "fields": [], "value": value} for item_id, value in zip(ids, values)]
        return descriptor

    def _planets(self, data, descriptor, address, state, budget):
        original = data.get(descriptor["name"])
        if original is not None and (not isinstance(original, list) or not all(isinstance(value, str) for value in original)):
            descriptor.update(readOnly=True, rows=[], validationError="星球集合必须为标识符数组，原值已保留。")
            return
        values = deepcopy(original) if isinstance(original, list) else []
        collection = self._collection(values, address, state, budget)
        descriptor.update(collection)
        if descriptor["readOnly"]:
            return
        route = _Route(data, descriptor["name"], descriptor, values)
        self._routes[self._key(address[:-1], descriptor["name"])] = route
        descriptor["addField"] = self._field(route, {}, address, "planet", "reference",
                                               categories=("Planets",), default="")
        for row in descriptor["rows"]:
            row["fields"] = [self._field(route, {"planet": row["value"]}, row["objectPath"],
                                         "planet", "reference", categories=("Planets",), default="")]

    def _parse(self, descriptor, payload):
        if ("value" in payload) == ("text" in payload):
            raise ValueError("请提供一种研究字段值。")
        value = payload.get("value")
        if "text" in payload:
            value = payload["text"]
            if not isinstance(value, str):
                raise ValueError("输入文本格式无效。")
            if descriptor["control"] == "number":
                if len(value) > 1024 or not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value.strip()):
                    raise ValueError("请输入完整的整数需求数量。")
                try:
                    number = Decimal(value.strip())
                    if not number.is_finite() or not 1 <= number <= 999999 or number != number.to_integral_value():
                        raise ValueError("研究需求数量必须为 1 到 999999 的整数。")
                    value = int(number)
                except InvalidOperation as exc:
                    raise ValueError("研究需求数量无效。") from exc
            elif descriptor["control"] == "boolean":
                raise ValueError("研究开关需要布尔值。")
        value = self.nested.forms.validate(descriptor, value)
        if descriptor["control"] == "number" and value > 999999:
            raise ValueError("研究需求数量不能超过 999999。")
        if descriptor["control"] == "string" and isinstance(value, str):
            if len(value) > 1024:
                raise ValueError("研究名称不能超过 1024 字。")
            value = value.strip()
        return value

    def plan(self, content, path):
        return self.nested.plan(content, path)

    def _prepare(self, content, path, payload):
        address = self.nested._address(payload)
        state = self.nested.snapshot(path)
        _, nodes = self.nested._build(content, path, state)
        if not nodes:
            raise ValueError("研究表单超出支持范围。")
        return address, state

    def reference_candidates(self, content, path, payload):
        address, state = self._prepare(content, path, payload)
        leaf = self._leaves.get(self._key(address, payload.get("field")))
        if leaf is None or leaf.descriptor["control"] != "reference":
            raise ValueError("请选择有效的研究引用字段。")
        result = self.nested.forms.references.read(leaf.descriptor, leaf.data.get(leaf.name), payload.get("query", ""))
        self.nested.restore(path, state)
        return result

    def command(self, action, content, path, payload):
        address, before = self._prepare(content, path, payload)
        draft = ContentData(content.name, content.category, deepcopy(content.data), content.path)
        after = deepcopy(before)
        self.nested._build(draft, path, after)
        if action == "research_set":
            leaf = self._leaves.get(self._key(address, payload.get("field")))
            if leaf is None or leaf.descriptor["readOnly"] or leaf.route.descriptor["control"] != "research":
                raise ValueError("研究字段不可编辑或条目已失效。")
            value = self._parse(leaf.descriptor, payload)
            if leaf.descriptor["control"] == "reference":
                self.nested.forms.references.validate(leaf.descriptor, value, leaf.data.get(leaf.name))
            if leaf.optional and (value is None or value == "" or value is False):
                leaf.data.pop(leaf.name, None)
            else:
                leaf.data[leaf.name] = value
            route = leaf.route
        elif action in ("research_add", "research_remove", "research_move", "research_objective_type"):
            route = self._routes.get(self._key(address, payload.get("field")))
            if route is None or route.descriptor["readOnly"] or route.descriptor["control"] != "research":
                raise ValueError("研究配置不可编辑或已失效。")
            collection = "objectives" if action == "research_objective_type" else payload.get("collection")
            if collection not in ("requirements", "objectives"):
                raise ValueError("请选择需求或目标列表。")
            descriptor = route.descriptor[collection]
            if descriptor["readOnly"]:
                raise ValueError("此研究列表格式无效或超出支持范围。")
            ids = after.item_ids[self.nested._key(descriptor["objectPath"])]
            if action == "research_objective_type":
                index = self._index(ids, payload.get("itemId"))
                objective = route.view[collection][index]
                selected = payload.get("type")
                if not isinstance(objective, dict) or not isinstance(selected, str) or selected not in OBJECTIVE_CATEGORIES:
                    raise ValueError("请选择受支持的目标对象与类型。")
                if objective.get("type") == selected:
                    return None
                objective["type"] = selected
                for target in set(OBJECTIVE_TARGET_FIELDS.values()):
                    objective.pop(target, None)
            else:
                default = {"item": "copper", "amount": 1} if collection == "requirements" else {"type": "Research", "content": "copper-wall"}
                values = route.view.setdefault(collection, [])
                self._change_list(action.removeprefix("research_"), values, ids, descriptor, payload, default)
                if not values:
                    route.view.pop(collection, None)
        elif action in ("planet_add", "planet_remove", "planet_set"):
            route = self._routes.get(self._key(address, payload.get("field")))
            if route is None or route.descriptor["readOnly"] or route.descriptor["control"] != "planet_set":
                raise ValueError("星球集合不可编辑或已失效。")
            ids = after.item_ids[self.nested._key(route.descriptor["objectPath"])]
            if action == "planet_remove":
                self._change_list("remove", route.view, ids, route.descriptor, payload, None)
            else:
                index = self._index(ids, payload.get("itemId")) if action == "planet_set" else None
                if action == "planet_set" and "value" not in payload:
                    raise ValueError("请提供要设置的星球。")
                candidates = self.nested.metadata.list_instances("Planets")
                value = payload.get("value", candidates[0] if candidates else None)
                if not isinstance(value, str) or not value:
                    raise ValueError("请选择有效的星球。")
                current = route.view[index] if index is not None else None
                self.nested.forms.references.validate({"control": "reference", "categories": ["Planets"], "nullable": False}, value, current)
                if index is None:
                    self._change_list("add", route.view, ids, route.descriptor, payload, value)
                else:
                    route.view[index] = value
            unique, unique_ids = [], []
            for value, item_id in zip(route.view, ids):
                if value not in unique:
                    unique.append(value)
                    unique_ids.append(item_id)
            route.view[:] = unique
            ids[:] = unique_ids
        else:
            raise ValueError("不支持此研究操作。")
        value = (route.view or None) if route.descriptor["control"] == "planet_set" else serialize_research(route.owner.get(route.name), route.view)
        if value is None:
            route.owner.pop(route.name, None)
        else:
            route.owner[route.name] = value
        _, nodes = self.nested._build(draft, path, after)
        if not nodes:
            raise ValueError("研究修改超出表单大小上限，原值已保留。")
        if json_values_equal(content.data, draft.data) and before == after:
            return None
        return _NestedCommand(self.nested, path, content.data, draft.data, before, after, "修改研究配置")

    @staticmethod
    def _index(ids, item_id):
        if not isinstance(item_id, str) or item_id not in ids:
            raise ValueError("列表条目已失效，请刷新后重试。")
        return ids.index(item_id)

    def _change_list(self, action, values, ids, descriptor, payload, default):
        if action == "add":
            if not descriptor["canInsert"]:
                raise ValueError("列表已达数量上限。")
            anchor = payload.get("beforeItemId")
            index = len(ids) if anchor is None else self._index(ids, anchor)
            values.insert(index, deepcopy(default))
            ids.insert(index, uuid4().hex)
            return
        index = self._index(ids, payload.get("itemId"))
        if action == "remove":
            values.pop(index)
            ids.pop(index)
            return
        if "beforeItemId" not in payload:
            raise ValueError("请指定列表移动位置。")
        anchor = payload["beforeItemId"]
        if anchor == payload["itemId"]:
            return
        remaining = [item for item in ids if item != payload["itemId"]]
        destination = len(remaining) if anchor is None else self._index(remaining, anchor)
        values.insert(destination, values.pop(index))
        ids.insert(destination, ids.pop(index))
