"""Tests for app.core.validator — Validator.validate + validate_field_value.

Uses the real metadata/ directory (skipped if absent).
"""

import pytest
from pathlib import Path

from app.core.metadata import Metadata, FieldDef
from app.core.validator import Validator, Issue

METADATA_DIR = Path(__file__).parent.parent / "metadata"

pytestmark = pytest.mark.skipif(
    not METADATA_DIR.exists(),
    reason="metadata/ directory not found — run the extractor first",
)


@pytest.fixture
def meta():
    return Metadata(METADATA_DIR)


@pytest.fixture
def validator(meta):
    return Validator(meta)


# ── validate: basic structure ──────────────────────────────────────────


class TestValidateBasic:
    @pytest.mark.parametrize("data", [None, [], {"type": ["Wall"]}, {"type": {"bad": True}}, {"type": 42}])
    def test_malformed_root_or_type_reports_error(self, validator, data):
        assert any(issue.severity == "error" for issue in validator.validate(data))

    def test_missing_type_field(self, validator):
        issues = validator.validate({"health": 100})
        assert any(i.path == "type" and i.severity == "error" for i in issues)

    def test_unknown_type(self, validator):
        issues = validator.validate({"type": "NonExistentType"})
        assert any("未知类型" in i.message for i in issues)

    def test_valid_wall_minimal(self, validator):
        issues = validator.validate({"type": "Wall", "name": "my-wall", "health": 200})
        errors = [i for i in issues if i.severity == "error"]
        assert errors == []

    def test_valid_unit_type(self, validator):
        issues = validator.validate({
            "type": "UnitType",
            "name": "my-unit",
            "health": 100,
            "speed": 1.5,
        })
        errors = [i for i in issues if i.severity == "error"]
        assert errors == []

    def test_shown_planets_is_optional_but_requires_a_planet_name_list_when_set(self, validator):
        absent = validator.validate({"type": "Wall", "name": "my-wall", "health": 200})
        valid = validator.validate({
            "type": "Wall", "name": "my-wall", "health": 200,
            "shownPlanets": ["serpulo", "erekir"],
        })
        invalid = validator.validate({
            "type": "Wall", "name": "my-wall", "health": 200,
            "shownPlanets": "serpulo",
        })

        assert not any(issue.path == "shownPlanets" for issue in absent)
        assert not any(issue.path == "shownPlanets" for issue in valid)
        assert any(issue.path == "shownPlanets" for issue in invalid)


# ── validate: type checking ────────────────────────────────────────────


class TestValidateTypeChecks:
    def test_wrong_type_number_as_string(self, validator):
        issues = validator.validate({"type": "Wall", "health": "not a number"})
        assert any("应为数字" in i.message for i in issues)

    def test_wrong_type_boolean_as_string(self, validator):
        issues = validator.validate({"type": "UnitType", "flying": "yes"})
        assert any("应为布尔值" in i.message for i in issues)

    def test_correct_types_pass(self, validator):
        issues = validator.validate({
            "type": "UnitType",
            "name": "my-unit",
            "health": 100,
            "speed": 1.5,
            "flying": True,
        })
        errors = [i for i in issues if i.severity == "error"]
        assert errors == []

    def test_short_type_is_checked(self, validator):
        """v0.2.3：short 字段的类型检查（此前漏掉，错值不报错）。"""
        field_def = FieldDef(
            name="testShort", java_type="short", mode="PRIMITIVE", nullable=True
        )
        assert validator.validate_field_value(field_def, 5) is None
        issue = validator.validate_field_value(field_def, "oops")
        assert issue is not None
        assert "应为数字" in issue.message


# ── validate: internal fields are skipped ──────────────────────────────


class TestInternalFieldsSkipped:
    def test_internal_field_not_validated(self, validator):
        """Internal fields (e.g. 'id', 'baseRegion') should not produce issues
        even if their values have wrong types."""
        issues = validator.validate({
            "type": "Wall",
            "health": 100,
            "id": "wrong-type-but-internal",
        })
        # 'id' is internal → no issue for it
        assert not any(i.path == "id" for i in issues)

    def test_region_field_skipped(self, validator):
        issues = validator.validate({
            "type": "Wall",
            "health": 100,
            "baseRegion": "should-be-skipped",
        })
        assert not any(i.path == "baseRegion" for i in issues)


# ── validate: field level vs content level ─────────────────────────────


class TestValidationLevels:
    def test_field_level_skips_references(self, validator):
        """At 'field' level, reference existence is not checked."""
        issues = validator.validate(
            {"type": "UnitType", "health": 100},
            level="field",
        )
        # Should not contain reference errors
        assert not any("引用的对象不存在" in i.message for i in issues)

    def test_content_level_checks_references(self, validator):
        """At 'content' level, STRING_REF fields are checked against instances."""
        # This test verifies the mechanism works; actual ref errors depend
        # on whether the data has STRING_REF fields with ref_source.
        issues = validator.validate(
            {"type": "Wall", "health": 100},
            level="content",
        )
        # Wall with just health should have no reference errors
        ref_errors = [i for i in issues if "引用的对象不存在" in i.message]
        assert ref_errors == []


# ── validate_field_value ───────────────────────────────────────────────


class TestValidateFieldValue:
    def test_valid_number(self, validator):
        f = FieldDef(name="health", java_type="float", mode="PRIMITIVE", nullable=False)
        assert validator.validate_field_value(f, 100.0) is None

    def test_invalid_number(self, validator):
        f = FieldDef(name="health", java_type="float", mode="PRIMITIVE", nullable=False)
        issue = validator.validate_field_value(f, "abc")
        assert issue is not None
        assert "应为数字" in issue.message

    def test_valid_boolean(self, validator):
        f = FieldDef(name="flying", java_type="boolean", mode="PRIMITIVE")
        assert validator.validate_field_value(f, True) is None

    def test_invalid_boolean(self, validator):
        f = FieldDef(name="flying", java_type="boolean", mode="PRIMITIVE")
        issue = validator.validate_field_value(f, 1)
        assert issue is not None
        assert "应为布尔值" in issue.message

    def test_valid_string(self, validator):
        f = FieldDef(name="name", java_type="String", mode="PRIMITIVE")
        assert validator.validate_field_value(f, "hello") is None

    def test_invalid_string(self, validator):
        f = FieldDef(name="name", java_type="String", mode="PRIMITIVE")
        issue = validator.validate_field_value(f, 123)
        assert issue is not None
        assert "应为字符串" in issue.message

    def test_none_nullable_ok(self, validator):
        f = FieldDef(name="armor", java_type="float", mode="PRIMITIVE", nullable=True)
        assert validator.validate_field_value(f, None) is None

    def test_none_non_nullable_error(self, validator):
        f = FieldDef(name="health", java_type="float", mode="PRIMITIVE", nullable=False)
        issue = validator.validate_field_value(f, None)
        assert issue is not None
        assert "必填" in issue.message

    def test_empty_string_nullable_ok(self, validator):
        f = FieldDef(name="desc", java_type="String", mode="PRIMITIVE", nullable=True)
        assert validator.validate_field_value(f, "") is None

    def test_int_accepts_int(self, validator):
        f = FieldDef(name="armor", java_type="int", mode="PRIMITIVE")
        assert validator.validate_field_value(f, 5) is None

    def test_int_rejects_string(self, validator):
        f = FieldDef(name="armor", java_type="int", mode="PRIMITIVE")
        issue = validator.validate_field_value(f, "five")
        assert issue is not None


# ── Issue dataclass ────────────────────────────────────────────────────


class TestIssue:
    def test_issue_fields(self):
        issue = Issue(path="health", severity="error", message="test")
        assert issue.path == "health"
        assert issue.severity == "error"
        assert issue.message == "test"
