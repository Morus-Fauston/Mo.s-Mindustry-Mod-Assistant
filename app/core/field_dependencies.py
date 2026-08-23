"""Qt-free evaluation of documented field-effect prerequisites."""

from __future__ import annotations

from typing import Any

from .config_loader import get_config
from .metadata import normalize_content_type


def inactive_dependencies(content_type: str, data: dict[str, Any]) -> dict[str, str]:
    """Return set dependent fields whose configured prerequisites are unmet.

    Missing dependents are deliberately omitted: a missing JSON key has no value
    to preserve and must not produce a warning or a disabled virtual field.
    """
    rules = get_config("field_dependencies")
    type_rules = rules.get(normalize_content_type(content_type), {})
    inactive: dict[str, str] = {}
    for dependent, prerequisites in type_rules.items():
        if dependent not in data or not isinstance(prerequisites, dict):
            continue
        failed = [
            _describe_requirement(field, condition)
            for field, condition in prerequisites.items()
            if not _matches(data.get(field), condition)
        ]
        if failed:
            inactive[dependent] = "且".join(failed)
    return inactive


def _matches(value: Any, condition: Any) -> bool:
    if isinstance(condition, dict):
        if "$gt" in condition:
            return isinstance(value, (int, float)) and not isinstance(value, bool) and value > condition["$gt"]
        if "$notEmpty" in condition:
            return bool(value) if condition["$notEmpty"] else not bool(value)
        if "$exists" in condition:
            return (value is not None) is bool(condition["$exists"])
        return False
    return value == condition


def _describe_requirement(field: str, condition: Any) -> str:
    if isinstance(condition, dict) and "$gt" in condition:
        return f"{field} > {condition['$gt']}"
    if condition is True:
        return f"{field} 为 true"
    if condition is False:
        return f"{field} 为 false"
    return f"{field} 为 {condition}"
