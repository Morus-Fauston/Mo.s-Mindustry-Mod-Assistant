"""Session reference choices use the shared core resolver and offline names."""

from __future__ import annotations

from collections import OrderedDict
import re

from app.core.config_loader import get_content_names_zh
from app.core.ref_candidates import resolve_candidates


_CATEGORY_LABELS = {"Blocks": "方块", "UnitTypes": "单位", "Items": "物品", "Liquids": "液体",
                    "StatusEffects": "状态效果", "Planets": "星球", "SectorPresets": "战区",
                    "Weapons": "武器", "BuildingCacheLayers": "绘制缓存层", "BlockGroups": "方块组",
                    "Categorys": "建造分类"}


class ReferenceService:
    """Cache offline candidates once, while resolving live project names each read."""

    def __init__(self, metadata, project=None):
        self._metadata, self._project = metadata, project
        self._vanilla: OrderedDict[tuple[str, ...], tuple] = OrderedDict()

    def _candidates(self, field: dict):
        if field["control"] != "reference":
            raise ValueError("该字段不是基础内容引用。")
        categories = tuple(field.get("categories", []))
        if any(not isinstance(category, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", category) for category in categories):
            raise ValueError("引用来源配置无效。")
        if categories not in self._vanilla:
            self._vanilla[categories] = tuple(resolve_candidates(self._metadata, categories=categories, names_zh=get_content_names_zh()))
            if len(self._vanilla) > 32:
                self._vanilla.popitem(last=False)
        else:
            self._vanilla.move_to_end(categories)
        project = resolve_candidates(_ProjectOnlyMetadata(), self._project, categories=categories, names_zh=get_content_names_zh())
        return [*project, *self._vanilla[categories]]

    def read(self, field: dict, current: object, query: object = "") -> dict:
        if not isinstance(query, str) or len(query) > 256:
            raise ValueError("搜索内容必须是 256 字以内的文本。")
        candidates = self._candidates(field)
        selected = next((candidate for candidate in candidates if candidate.value == current), None)
        needle = query.casefold().strip()
        return {
            "candidates": [{"value": item.value, "category": item.category, "label": item.label, "isProject": item.is_project}
                for item in candidates if not needle or needle in item.value.casefold() or needle in item.label.casefold()],
            "categories": [{"id": category, "label": _CATEGORY_LABELS.get(category, "其他引用")}
                           for category in field.get("categories", [])],
            "current": {"value": current if isinstance(current, str) else None,
                        "label": selected.label if selected else "未选择" if current in (None, "") else str(current),
                        "known": selected is not None or current in (None, "")},
        }

    def validate(self, field: dict, value: object, current: object) -> object:
        if value is None:
            if not field["nullable"]:
                raise ValueError("此字段不允许空值。")
            return None
        if not isinstance(value, str) or len(value) > 1024:
            raise ValueError("内容引用需要有效的文本标识。")
        if value == "" or value == current:
            return value
        if not any(item.value == value for item in self._candidates(field)):
            raise ValueError("此引用不属于该字段的可选类别，请从候选中选择。")
        return value


class _ProjectOnlyMetadata:
    """Core resolver still owns project identifiers and category filtering."""

    @staticmethod
    def list_instances(category: str) -> list:
        return []
