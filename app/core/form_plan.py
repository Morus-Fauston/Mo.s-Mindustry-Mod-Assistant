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

from .metadata import ClassDef, FieldDef


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


# ── Public interface ───────────────────────────────────────────────────


def compute_form_plan(
    class_def: ClassDef,
    data: dict[str, Any],
    field_groups: dict[str, Any],
    expanded_state: dict[str, bool] | None = None,
    group_labels: dict[str, str] | None = None,
    deleted_groups: set[str] | None = None,
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
    content_type = data.get("type", "")
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

        visible = [all_fields[n] for n in visible_names if n in all_fields]

        # Empty-group hiding: show group only if it has required fields
        # or at least one visible field.  Groups with only default/optional
        # and nothing in data stay hidden (user adds via header button).
        # Exception: capability groups always render (checkbox must be visible)
        # unless manually deleted (handled by deleted_groups param).
        is_cap = group_name in CAPABILITY_GROUPS
        is_deleted = group_name in (deleted_groups or set())
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
                capability=group_name in CAPABILITY_GROUPS,
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
    """
    if content_type != "UnitType":
        return content_type

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
