"""Form plan computation — pure logic, no Qt imports.

Computes WHICH groups and fields to display for a given content item,
based on metadata class definitions and field_groups.json configuration.
The UI layer (EditorPanel) renders this plan into actual widgets.

Interface:
    compute_form_plan(class_def, data, field_groups, expanded_state) -> list[GroupPlan]
    infer_subtype(content_type, data) -> str
    type_default(field_def) -> Any

This module is the single place where "what to show" decisions live.
EditorPanel only handles "how to render it".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .metadata import ClassDef, FieldDef, GAME_UNIT_TYPE_TO_SUBTYPE, normalize_content_type


# ── Synthetic field defs (v0.2.5 F-22) ────────────────────────────────


def synthetic_field_def(name: str, value: Any) -> FieldDef:
    """为 JSON 中存在但提取元数据缺失的字段构造 FieldDef。

    背景：`consumes` 等字段在部分游戏版本的反射提取中缺失，导致模板生成的
    数据无法渲染（field 不在 class_def → 组被隐藏）。此函数按值的运行时类型
    推断 mode/java_type，让这类字段仍走正常渲染（含 widgets 路由）。

    Returns:
        一个可渲染的 FieldDef；mode 依 value 推断。
    """
    if isinstance(value, bool):
        mode, jt = "PRIMITIVE", "boolean"
    elif isinstance(value, int):
        mode, jt = "PRIMITIVE", "int"
    elif isinstance(value, float):
        mode, jt = "PRIMITIVE", "float"
    elif isinstance(value, list):
        mode, jt = "ARRAY", "List"
    elif isinstance(value, dict):
        mode, jt = "INLINE_OBJECT", "Object"
    else:
        mode, jt = "PRIMITIVE", "String"
    return FieldDef(name=name, java_type=jt, mode=mode, nullable=True)


# ── Data structures ────────────────────────────────────────────────────


@dataclass
class FieldPlan:
    """A single field to render in the form."""
    field_def: FieldDef
    deletable: bool  # False for required fields in locked groups


# 能力开关组名单（v0.2.4.batch2）
CAPABILITY_GROUPS = {"mining", "building", "boost", "capacity"}

# 单向联动：勾选 key → 自动勾选 value
CAPABILITY_LINKAGE = {"mining": "capacity"}


@dataclass
class GroupPlan:
    """A group of fields to render as a collapsible section."""
    group_name: str
    label: str
    locked: bool
    expanded: bool
    fields: list[FieldPlan] = field(default_factory=list)
    has_optional: bool = False  # True if group has more fields available via '+'
    capability: bool = False  # True = 能力开关组（▾ ☐ 标题）
    capability_enabled: bool = False  # True = 能力组复选框已勾选


# ── Public interface ───────────────────────────────────────────────────


def compute_form_plan(
    class_def: ClassDef,
    data: dict[str, Any],
    field_groups: dict[str, Any],
    expanded_state: dict[str, bool] | None = None,
    group_labels: dict[str, str] | None = None,
    deleted_groups: set[str] | None = None,
    enabled_groups: set[str] | None = None,
) -> list[GroupPlan]:
    """Compute the full form plan for a content item.

    Args:
        class_def: The merged class definition (with inheritance).
        data: The current content JSON data.
        field_groups: The field_groups.json config for this content type.
        expanded_state: Per-group expanded state memory (None = default).
        group_labels: Chinese labels for group names (None = use group_name).

    Returns:
        Ordered list of GroupPlan, including an "_other" group for
        fields present in data but not in any configured group.
    """
    content_type = normalize_content_type(data.get("type", ""))
    groups_config = field_groups.get(content_type, {})
    all_fields = {f.name: f for f in class_def.fields}
    subtype = infer_subtype(content_type, data)

    # Collect all field names that appear in any visible group
    grouped_names: set[str] = set()
    for gd in groups_config.values():
        if not group_visible(gd, subtype):
            continue
        grouped_names.update(gd.get("required", []))
        grouped_names.update(gd.get("default", []))
        grouped_names.update(gd.get("optional", []))

    # Fields already in JSON but not in any visible group → "其他"
    json_fields = set(data.keys()) - {"type"}
    extra_names = json_fields - grouped_names

    plans: list[GroupPlan] = []

    # Render configured groups: required always, optional only if in data
    for group_name, group_def in groups_config.items():
        if not group_visible(group_def, subtype):
            continue

        label = (group_labels or {}).get(group_name, group_name)
        required = group_def.get("required", [])
        default = group_def.get("default", [])
        optional = group_def.get("optional", [])

        # Three-level visibility:
        #   required → always visible
        #   default  → visible if in data (pre-filled by template on new content)
        #   optional → visible only if in data (user explicitly added)
        visible_names = list(required)
        for n in default:
            if n in data:
                visible_names.append(n)
        for n in optional:
            if n in data:
                visible_names.append(n)

        visible = []
        for n in visible_names:
            if n in all_fields:
                visible.append(all_fields[n])
            elif n in data:
                # 模板/JSON 中存在但元数据缺失的字段（如 consumes）：
                # 合成 FieldDef 保证仍可渲染（v0.2.5 F-22）
                visible.append(synthetic_field_def(n, data[n]))

        # Empty-group hiding: show group only if it has required fields
        # or at least one visible field.  Groups with only default/optional
        # and nothing in data stay hidden (user adds via header button).
        # Exception: capability groups always render (checkbox must be visible)
        # unless manually deleted (handled by deleted_groups param).
        is_cap = group_name in CAPABILITY_GROUPS
        is_deleted = group_name in (deleted_groups or set())
        is_enabled = group_name in (enabled_groups or set())
        if required or visible or (is_cap and not is_deleted):
            locked = is_group_locked(group_name, group_def, content_type, data)
            expanded = is_group_expanded(
                group_name, expanded_state, bool(required),
                is_capability=group_name in CAPABILITY_GROUPS,
            )
            required_set = set(required)

            field_plans = [
                FieldPlan(field_def=f, deletable=f.name not in required_set)
                for f in visible
            ]

            plans.append(GroupPlan(
                group_name=group_name,
                label=label,
                locked=locked,
                expanded=expanded,
                fields=field_plans,
                has_optional=bool(optional) or bool(default),
                capability=is_cap,
                capability_enabled=is_enabled or bool(visible),
            ))

    # Render extra fields from JSON (not in any group) → "其他"
    if extra_names:
        extra = [all_fields[n] for n in sorted(extra_names) if n in all_fields]
        if extra:
            expanded = is_group_expanded("_other", expanded_state)
            plans.append(GroupPlan(
                group_name="_other",
                label="其他",
                locked=False,
                expanded=expanded,
                fields=[FieldPlan(field_def=f, deletable=True) for f in extra],
                has_optional=False,
            ))

    return plans


def infer_subtype(content_type: str, data: dict[str, Any]) -> str:
    """Infer the subtype key for visible_for filtering.

    For UnitType, checks data flags (flying, legCount, squareShape, etc.)
    to determine which subtype template was used.
    Returns e.g. 'UnitType-tank', 'UnitType-flying', 'UnitType-legs', 'UnitType'.

    Also accepts game entity subtype strings (mech/flying/tank/legs) as
    content_type — since v0.2.6 the unit JSON `type` field stores the game
    value, not the Java class name — and maps them to MoMA subtype keys.
    """
    if content_type not in ("UnitType", ""):
        return GAME_UNIT_TYPE_TO_SUBTYPE.get(content_type, content_type)

    if data.get("squareShape") or data.get("crushDamage") is not None:
        return "UnitType-tank"
    if data.get("legCount"):
        return "UnitType-legs"
    if data.get("flying"):
        return "UnitType-flying"
    return "UnitType"


def group_visible(group_def: dict[str, Any], subtype: str) -> bool:
    """Check if a group should be visible for the given subtype.

    A group with no 'visible_for' key is always visible.
    A group with 'visible_for' is visible only if subtype is in the list.
    """
    visible_for = group_def.get("visible_for")
    if visible_for is None:
        return True
    return subtype in visible_for


def is_group_locked(
    group_name: str,
    group_def: dict[str, Any],
    content_type: str,
    data: dict[str, Any],
) -> bool:
    """Determine if a group is locked (cannot be deleted).

    basic group is always locked. Groups with 'locked: true' are locked.
    Groups with 'locked_for' are locked when the subtype matches.
    """
    if group_name == "basic":
        return True
    if group_def.get("locked"):
        return True
    locked_for = group_def.get("locked_for")
    if locked_for:
        subtype = infer_subtype(content_type, data)
        if subtype in locked_for:
            return True
    return False


def is_group_expanded(
    group_name: str,
    expanded_state: dict[str, bool] | None,
    has_required: bool = False,
    is_capability: bool = False,
) -> bool:
    """Query expanded state memory.

    Default: groups with required fields or capability groups are expanded;
    groups with only default/optional are collapsed.

    Always returns a plain bool: callers must be able to pass
    has_required directly to QWidget.setVisible without coercion.
    """
    if expanded_state is not None and group_name in expanded_state:
        return bool(expanded_state[group_name])
    return bool(has_required or is_capability)


def type_default(field_def: FieldDef) -> Any:
    """Return the zero/default value for a field type."""
    if field_def.java_type in ("float", "double"):
        return 0.0
    if field_def.java_type in ("int", "long", "short"):
        return 0
    if field_def.java_type == "boolean":
        return False
    if field_def.mode == "ARRAY":
        return []
    if field_def.mode == "INLINE_OBJECT":
        return {}
    return None


def get_addable_fields(
    class_def: ClassDef,
    data: dict[str, Any],
    field_groups: dict[str, Any],
    group_name: str,
) -> list[FieldDef]:
    """Return fields that can be added to a group via the '+' menu.

    For '_other': all class fields not in any group and not in data.
    For named groups: optional fields of that group not yet in data.
    Internal fields are always excluded.
    """
    content_type = data.get("type", "")
    groups_config = field_groups.get(content_type, {})
    data_keys = set(data.keys())

    if group_name == "_other":
        all_grouped: set[str] = set()
        for gd in groups_config.values():
            all_grouped.update(gd.get("required", []))
            all_grouped.update(gd.get("default", []))
            all_grouped.update(gd.get("optional", []))
        return [
            f for f in class_def.fields
            if f.name not in all_grouped
            and f.name not in data_keys
            and not f.is_internal
        ]
    else:
        group_def = groups_config.get(group_name, {})
        addable_names = set(group_def.get("default", [])) | set(group_def.get("optional", []))
        return [
            f for f in class_def.fields
            if f.name in addable_names
            and f.name not in data_keys
            and not f.is_internal
        ]
