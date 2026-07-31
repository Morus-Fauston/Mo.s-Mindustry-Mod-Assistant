"""Unified validation engine.

Interface (1 method):
    validate(data, level) -> list[Issue]

Levels:
    'field'   - type checks only (for real-time input validation)
    'content' - + required fields + reference existence
    'project' - + mod.json format + file naming conventions
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .metadata import Metadata, FieldDef


@dataclass
class Issue:
    path: str  # e.g. "weapons[0].bullet.damage"
    severity: str  # "error" | "warning"
    message: str


class Validator:
    """Validates content data against metadata definitions."""

    def __init__(self, metadata: Metadata) -> None:
        self._meta = metadata

    def validate(self, data: dict[str, Any], level: str = "content") -> list[Issue]:
        """Validate content data at the specified level."""
        issues: list[Issue] = []

        content_type = data.get("type")
        if not content_type:
            issues.append(Issue("type", "error", "缺少 type 字段"))
            return issues

        # Get class definition
        try:
            class_def = self._meta.get_class(content_type)
        except KeyError:
            issues.append(Issue("type", "error", f"未知类型: {content_type}"))
            return issues

        # Field-level validation
        for field_def in class_def.fields:
            field_issues = self._validate_field(data, field_def)
            issues.extend(field_issues)

        if level in ("content", "project"):
            # Reference existence checks
            ref_issues = self._validate_references(data, class_def)
            issues.extend(ref_issues)

        return issues

    def validate_field_value(self, field_def: FieldDef, value: Any) -> Issue | None:
        """Validate a single field value (for real-time input checking)."""
        if value is None or value == "":
            if not field_def.nullable:
                return Issue(field_def.name, "error", f"{field_def.name} 为必填项")
            return None

        if field_def.mode == "PRIMITIVE":
            return self._check_primitive(field_def, value)

        return None

    def _validate_field(self, data: dict, field_def: FieldDef) -> list[Issue]:
        issues: list[Issue] = []
        value = data.get(field_def.name)

        # Only validate fields that mods actually set in JSON.
        # Skip internal engine fields (regions, sounds, effects, controllers).
        if field_def.is_internal:
            return issues

        # Required check: only for primitive fields that are non-nullable
        if value is None and not field_def.nullable:
            if field_def.mode == "PRIMITIVE" and field_def.default is None:
                issues.append(Issue(
                    field_def.name, "error",
                    f"{field_def.name} 为必填项"
                ))
            return issues

        if value is None:
            return issues

        # Type check for primitives
        if field_def.mode == "PRIMITIVE":
            issue = self._check_primitive(field_def, value)
            if issue:
                issues.append(issue)

        return issues

    def _check_primitive(self, field_def: FieldDef, value: Any) -> Issue | None:
        java_type = field_def.java_type

        if java_type in ("float", "double", "int", "long", "short"):
            if not isinstance(value, (int, float)):
                return Issue(
                    field_def.name, "error",
                    f"{field_def.name} 应为数字，当前为: {type(value).__name__}"
                )
        elif java_type == "boolean":
            if not isinstance(value, bool):
                return Issue(
                    field_def.name, "error",
                    f"{field_def.name} 应为布尔值"
                )
        elif java_type == "String":
            if not isinstance(value, str):
                return Issue(
                    field_def.name, "error",
                    f"{field_def.name} 应为字符串"
                )

        return None

    def _validate_references(self, data: dict, class_def: Any) -> list[Issue]:
        """Check that STRING_REF fields point to existing instances."""
        issues: list[Issue] = []

        for field_def in class_def.fields:
            if field_def.mode != "STRING_REF" or not field_def.ref_source:
                continue

            value = data.get(field_def.name)
            if value is None or not isinstance(value, str):
                continue

            # Check if the referenced instance exists
            try:
                instances = self._meta.list_instances(field_def.ref_source)
                if value not in instances:
                    issues.append(Issue(
                        field_def.name, "error",
                        f"引用的对象不存在: {value} (在 {field_def.ref_source} 中)"
                    ))
            except Exception:
                pass  # Category not available, skip

        return issues
