"""Tests for app.core.form_plan — pure form computation logic, no Qt."""

from copy import deepcopy
from pathlib import Path

import pytest

from app.core.form_plan import (
    GroupPlan,
    FieldPlan,
    compute_form_plan,
    infer_subtype,
    group_visible,
    is_group_locked,
    is_group_expanded,
    type_default,
    get_addable_fields,
)
from app.core.config_loader import get_field_groups
from app.core.metadata import ClassDef, FieldDef, Metadata


# ── Fixtures ───────────────────────────────────────────────────────────


def _field(name, java_type="float", mode="PRIMITIVE", **kw):
    return FieldDef(name=name, java_type=java_type, mode=mode, **kw)


def _class_def(fields):
    return ClassDef(name="TestType", full_name="test.TestType", parent=None, fields=fields)


SAMPLE_FIELDS = [
    _field("health"),
    _field("speed"),
    _field("armor"),
    _field("flying", java_type="boolean"),
    _field("legCount", java_type="int"),
    _field("squareShape", java_type="boolean"),
    _field("crushDamage"),
]

SAMPLE_GROUPS = {
    "TestType": {
        "basic": {
            "required": ["health", "speed"],
            "optional": ["armor"],
        },
        "movement": {
            "required": [],
            "optional": ["flying", "legCount"],
            "visible_for": ["TestType-flying", "TestType-legs"],
        },
        "tank": {
            "required": ["squareShape"],
            "optional": ["crushDamage"],
            "visible_for": ["TestType-tank"],
            "locked_for": ["TestType-tank"],
        },
    }
}


@pytest.fixture
def real_unit_form():
    metadata_dir = Path(__file__).resolve().parents[1] / "metadata"
    if not metadata_dir.is_dir():
        pytest.skip("metadata/ directory not found — run the extractor first")
    return Metadata(metadata_dir).get_class("UnitType"), get_field_groups()


class TestGameUnitForms:
    @pytest.mark.parametrize(
        ("alias", "group_name", "field_name"),
        [
            ("tank", "tank", "treadFrames"),
            ("legs", "legs", "legLength"),
            ("flying", "flying_engine", "engineSize"),
            ("mech", "mech", "mechStride"),
        ],
    )
    def test_raw_alias_keeps_subtype_group_and_lock(
        self, real_unit_form, alias, group_name, field_name,
    ):
        class_def, groups = real_unit_form
        # No heuristic flags: the game's explicit type must identify its group.
        data = {"type": alias, field_name: 4}
        before = deepcopy(data)
        plans = compute_form_plan(class_def, data, groups)
        by_name = {plan.group_name: plan for plan in plans}

        assert group_name in by_name
        assert by_name[group_name].locked is True
        assert by_name[group_name].expanded is False
        assert field_name in [field.field_def.name for field in by_name[group_name].fields]
        assert {"tank", "legs", "flying_engine", "mech"} & by_name.keys() == {group_name}
        assert not any(
            field.field_def.name == field_name
            for plan in plans if plan.group_name == "_other"
            for field in plan.fields
        )
        assert data == before

    @pytest.mark.parametrize("alias", ["tank", "legs", "flying", "mech"])
    def test_raw_alias_has_configured_addable_fields(self, real_unit_form, alias):
        class_def, groups = real_unit_form
        data = {"type": alias, "hovering": True}
        basic = get_addable_fields(class_def, data, groups, "basic")
        names = {field.name for field in basic}

        assert {"description", "lowAltitude"} <= names
        assert "hovering" not in names
        assert "health" not in names
        assert all(not field.is_internal for field in basic)
        other = get_addable_fields(class_def, data, groups, "_other")
        assert not {"description", "lowAltitude", "health"} & {field.name for field in other}


# ── infer_subtype ──────────────────────────────────────────────────────


class TestInferSubtype:
    def test_non_unit_returns_type(self):
        assert infer_subtype("Wall", {}) == "Wall"
        assert infer_subtype("ItemTurret", {"health": 100}) == "ItemTurret"

    def test_plain_unit(self):
        assert infer_subtype("UnitType", {"health": 100}) == "UnitType"

    def test_flying_unit(self):
        assert infer_subtype("UnitType", {"flying": True}) == "UnitType-flying"

    def test_legs_unit(self):
        assert infer_subtype("UnitType", {"legCount": 4}) == "UnitType-legs"

    def test_tank_by_square_shape(self):
        assert infer_subtype("UnitType", {"squareShape": True}) == "UnitType-tank"

    def test_tank_by_crush_damage(self):
        assert infer_subtype("UnitType", {"crushDamage": 10}) == "UnitType-tank"

    def test_tank_takes_priority_over_flying(self):
        """squareShape checked before flying."""
        assert infer_subtype("UnitType", {"squareShape": True, "flying": True}) == "UnitType-tank"

    def test_game_subtype_strings(self):
        """v0.2.6: type 字段存游戏子类型字符串（mech/flying/tank/legs）。"""
        assert infer_subtype("mech", {}) == "UnitType-mech"
        assert infer_subtype("flying", {"flying": True}) == "UnitType-flying"
        assert infer_subtype("tank", {}) == "UnitType-tank"
        assert infer_subtype("legs", {}) == "UnitType-legs"


# ── group_visible ──────────────────────────────────────────────────────


class TestGroupVisible:
    def test_no_visible_for_always_visible(self):
        assert group_visible({"required": ["health"]}, "anything")

    def test_visible_for_match(self):
        assert group_visible({"visible_for": ["UnitType-flying"]}, "UnitType-flying")

    def test_visible_for_no_match(self):
        assert not group_visible({"visible_for": ["UnitType-flying"]}, "UnitType-tank")


# ── is_group_locked ────────────────────────────────────────────────────


class TestIsGroupLocked:
    def test_basic_always_locked(self):
        assert is_group_locked("basic", {}, "UnitType", {})

    def test_locked_flag(self):
        assert is_group_locked("combat", {"locked": True}, "UnitType", {})

    def test_locked_for_matching_subtype(self):
        assert is_group_locked("tank", {"locked_for": ["UnitType-tank"]}, "UnitType", {"squareShape": True})

    def test_locked_for_non_matching_subtype(self):
        assert not is_group_locked("tank", {"locked_for": ["UnitType-tank"]}, "UnitType", {"flying": True})

    def test_unlocked_by_default(self):
        assert not is_group_locked("combat", {}, "UnitType", {})


# ── is_group_expanded ──────────────────────────────────────────────────


class TestIsGroupExpanded:
    def test_basic_expanded_by_default(self):
        # basic has required fields → expanded by default
        assert is_group_expanded("basic", None, has_required=True)

    def test_other_collapsed_by_default(self):
        # combat has required fields but we test without has_required
        assert not is_group_expanded("combat", None)

    def test_state_override(self):
        assert is_group_expanded("combat", {"combat": True})
        assert not is_group_expanded("basic", {"basic": False})

    def test_missing_key_uses_default(self):
        # basic with required → expanded; combat without required → collapsed
        assert is_group_expanded("basic", {"combat": False}, has_required=True)
        assert not is_group_expanded("combat", {"basic": True})

    def test_returns_plain_bool_even_with_non_bool_input(self):
        # v0.2.4.batch1 regression: compute_form_plan passed the raw
        # `required` list here, which flowed into QWidget.setVisible(list).
        # The function must coerce to bool regardless of caller input.
        assert is_group_expanded("basic", None, has_required=["health", "speed"]) is True
        assert isinstance(is_group_expanded("combat", None, has_required=[]), bool)
        assert is_group_expanded("combat", {"combat": 1}) is True


# ── type_default ───────────────────────────────────────────────────────


class TestTypeDefault:
    def test_float(self):
        assert type_default(_field("x", "float")) == 0.0

    def test_double(self):
        assert type_default(_field("x", "double")) == 0.0

    def test_int(self):
        assert type_default(_field("x", "int")) == 0

    def test_long(self):
        assert type_default(_field("x", "long")) == 0

    def test_short(self):
        assert type_default(_field("x", "short")) == 0

    def test_boolean(self):
        assert type_default(_field("x", "boolean")) is False

    def test_array(self):
        assert type_default(_field("x", "Seq", mode="ARRAY")) == []

    def test_inline_object(self):
        assert type_default(_field("x", "Object", mode="INLINE_OBJECT")) == {}

    def test_string_returns_none(self):
        assert type_default(_field("x", "String")) is None


# ── compute_form_plan ──────────────────────────────────────────────────


class TestComputeFormPlan:
    def test_basic_group_always_present(self):
        plan = compute_form_plan(_class_def(SAMPLE_FIELDS), {"type": "TestType", "health": 100, "speed": 1.0}, SAMPLE_GROUPS)
        names = [g.group_name for g in plan]
        assert "basic" in names

    def test_basic_group_has_required_fields(self):
        plan = compute_form_plan(_class_def(SAMPLE_FIELDS), {"type": "TestType", "health": 100, "speed": 1.0}, SAMPLE_GROUPS)
        basic = next(g for g in plan if g.group_name == "basic")
        field_names = [fp.field_def.name for fp in basic.fields]
        assert "health" in field_names
        assert "speed" in field_names

    def test_optional_field_hidden_when_not_in_data(self):
        plan = compute_form_plan(_class_def(SAMPLE_FIELDS), {"type": "TestType", "health": 100, "speed": 1.0}, SAMPLE_GROUPS)
        basic = next(g for g in plan if g.group_name == "basic")
        field_names = [fp.field_def.name for fp in basic.fields]
        assert "armor" not in field_names

    def test_optional_field_shown_when_in_data(self):
        plan = compute_form_plan(_class_def(SAMPLE_FIELDS), {"type": "TestType", "health": 100, "speed": 1.0, "armor": 5}, SAMPLE_GROUPS)
        basic = next(g for g in plan if g.group_name == "basic")
        field_names = [fp.field_def.name for fp in basic.fields]
        assert "armor" in field_names

    def test_visible_for_filters_movement_for_plain_unit(self):
        plan = compute_form_plan(_class_def(SAMPLE_FIELDS), {"type": "TestType", "health": 100}, SAMPLE_GROUPS)
        names = [g.group_name for g in plan]
        assert "movement" not in names

    def test_visible_for_shows_movement_for_flying(self):
        data = {"type": "TestType", "health": 100, "flying": True}
        # Need to adjust groups for UnitType-like subtype inference
        groups = {"TestType": {"basic": {"required": ["health"]}, "movement": {"required": [], "optional": ["flying"], "visible_for": ["TestType-flying"]}}}
        # infer_subtype only works for "UnitType", so for TestType it returns "TestType"
        # This tests that visible_for=["TestType-flying"] does NOT match "TestType"
        plan = compute_form_plan(_class_def(SAMPLE_FIELDS), data, groups)
        names = [g.group_name for g in plan]
        assert "movement" not in names

    def test_extra_fields_go_to_other_group(self):
        data = {"type": "TestType", "health": 100, "speed": 1.0, "unknownField": 42}
        fields = SAMPLE_FIELDS + [_field("unknownField", "int")]
        plan = compute_form_plan(_class_def(fields), data, SAMPLE_GROUPS)
        names = [g.group_name for g in plan]
        assert "_other" in names
        other = next(g for g in plan if g.group_name == "_other")
        assert any(fp.field_def.name == "unknownField" for fp in other.fields)

    def test_required_fields_not_deletable(self):
        plan = compute_form_plan(_class_def(SAMPLE_FIELDS), {"type": "TestType", "health": 100, "speed": 1.0}, SAMPLE_GROUPS)
        basic = next(g for g in plan if g.group_name == "basic")
        health_fp = next(fp for fp in basic.fields if fp.field_def.name == "health")
        assert not health_fp.deletable

    def test_optional_fields_deletable(self):
        plan = compute_form_plan(_class_def(SAMPLE_FIELDS), {"type": "TestType", "health": 100, "speed": 1.0, "armor": 5}, SAMPLE_GROUPS)
        basic = next(g for g in plan if g.group_name == "basic")
        armor_fp = next(fp for fp in basic.fields if fp.field_def.name == "armor")
        assert armor_fp.deletable

    def test_expanded_state_respected(self):
        plan = compute_form_plan(
            _class_def(SAMPLE_FIELDS),
            {"type": "TestType", "health": 100, "speed": 1.0},
            SAMPLE_GROUPS,
            expanded_state={"basic": False},
        )
        basic = next(g for g in plan if g.group_name == "basic")
        assert not basic.expanded

    def test_required_group_expanded_is_bool_without_state(self):
        # v0.2.4.batch1 regression: with no expanded_state, groups with
        # required fields got `expanded` = the raw required list, crashing
        # EditorPanel (setVisible(list)). Must be a plain bool.
        plan = compute_form_plan(
            _class_def(SAMPLE_FIELDS),
            {"type": "TestType", "health": 100, "speed": 1.0},
            SAMPLE_GROUPS,
        )
        basic = next(g for g in plan if g.group_name == "basic")
        assert isinstance(basic.expanded, bool)
        assert basic.expanded is True

    def test_group_labels_applied(self):
        labels = {"basic": "基础属性"}
        plan = compute_form_plan(
            _class_def(SAMPLE_FIELDS),
            {"type": "TestType", "health": 100, "speed": 1.0},
            SAMPLE_GROUPS,
            group_labels=labels,
        )
        basic = next(g for g in plan if g.group_name == "basic")
        assert basic.label == "基础属性"

    def test_empty_data_no_crash(self):
        plan = compute_form_plan(_class_def(SAMPLE_FIELDS), {"type": "TestType"}, SAMPLE_GROUPS)
        assert isinstance(plan, list)

    def test_unknown_type_no_groups(self):
        plan = compute_form_plan(_class_def(SAMPLE_FIELDS), {"type": "UnknownType"}, SAMPLE_GROUPS)
        # No groups configured for UnknownType → empty plan (no _other either since no extra fields)
        assert plan == []


# ── get_addable_fields ─────────────────────────────────────────────────


class TestGetAddableFields:
    def test_named_group_returns_optional_not_in_data(self):
        fields = get_addable_fields(
            _class_def(SAMPLE_FIELDS),
            {"type": "TestType", "health": 100, "speed": 1.0},
            SAMPLE_GROUPS,
            "basic",
        )
        names = [f.name for f in fields]
        assert "armor" in names
        assert "health" not in names  # already in data
        assert "speed" not in names  # already in data

    def test_named_group_excludes_in_data(self):
        fields = get_addable_fields(
            _class_def(SAMPLE_FIELDS),
            {"type": "TestType", "health": 100, "speed": 1.0, "armor": 5},
            SAMPLE_GROUPS,
            "basic",
        )
        names = [f.name for f in fields]
        assert "armor" not in names

    def test_other_group_returns_ungrouped_fields(self):
        fields = get_addable_fields(
            _class_def(SAMPLE_FIELDS),
            {"type": "TestType", "health": 100},
            SAMPLE_GROUPS,
            "_other",
        )
        names = [f.name for f in fields]
        # "armor" is in basic group → excluded from _other
        assert "armor" not in names
        # "flying" is in movement group → excluded from _other
        assert "flying" not in names

    def test_internal_fields_excluded(self):
        fields_with_internal = SAMPLE_FIELDS + [_field("baseRegion", "TextureRegion")]
        fields = get_addable_fields(
            _class_def(fields_with_internal),
            {"type": "TestType", "health": 100},
            SAMPLE_GROUPS,
            "_other",
        )
        names = [f.name for f in fields]
        assert "baseRegion" not in names

    def test_unknown_group_returns_empty(self):
        fields = get_addable_fields(
            _class_def(SAMPLE_FIELDS),
            {"type": "TestType", "health": 100},
            SAMPLE_GROUPS,
            "nonexistent_group",
        )
        assert fields == []


# ── synthetic_field_def (v0.2.5 F-22) ─────────────────────────────────


class TestSyntheticFieldDef:
    """JSON 中存在但元数据缺失的字段（如 consumes）仍可渲染。"""

    def test_import_synthetic(self):
        from app.core.form_plan import synthetic_field_def

        assert callable(synthetic_field_def)

    def test_dict_infers_inline_object(self):
        from app.core.form_plan import synthetic_field_def

        fd = synthetic_field_def("consumes", {"power": 1.0})
        assert fd.name == "consumes"
        assert fd.mode == "INLINE_OBJECT"

    def test_list_infers_array(self):
        from app.core.form_plan import synthetic_field_def

        fd = synthetic_field_def("consumes", [])
        assert fd.mode == "ARRAY"

    def test_number_infers_primitive(self):
        from app.core.form_plan import synthetic_field_def

        assert synthetic_field_def("craftTime", 60).mode == "PRIMITIVE"
        assert synthetic_field_def("craftTime", 60).java_type == "int"
        assert synthetic_field_def("craftTime", 60.0).java_type == "float"

    def test_bool_infers_primitive(self):
        from app.core.form_plan import synthetic_field_def

        assert synthetic_field_def("hasPower", True).java_type == "boolean"

    def test_not_internal(self):
        """合成字段不应被 is_internal 误判（否则会被隐藏/跳过校验）。"""
        from app.core.form_plan import synthetic_field_def

        fd = synthetic_field_def("consumes", {"power": 1.0})
        assert not fd.is_internal

    def test_data_field_not_in_class_def_renders(self):
        """class_def 无 consumes，但 data 有 → 组内仍渲染该字段。"""
        from app.core.form_plan import compute_form_plan

        class_def = _class_def(SAMPLE_FIELDS)  # 无 consumes
        groups = {
            "TestType": {
                "basic": {"required": ["health"], "optional": []},
                "consumption": {
                    "required": [],
                    "optional": ["consumes"],
                    "widgets": {"consumes": {"widget": "consumes"}},
                },
            }
        }
        plan = compute_form_plan(
            class_def, {"type": "TestType", "health": 100, "consumes": {"power": 1.0}}, groups
        )
        group = next(g for g in plan if g.group_name == "consumption")
        names = [f.field_def.name for f in group.fields]
        assert "consumes" in names

    def test_data_field_not_in_class_def_hidden_when_absent(self):
        """data 无 consumes 时 consumption 组隐藏（与既有行为一致）。"""
        from app.core.form_plan import compute_form_plan

        class_def = _class_def(SAMPLE_FIELDS)
        groups = {
            "TestType": {
                "basic": {"required": ["health"], "optional": []},
                "consumption": {"required": [], "optional": ["consumes"]},
            }
        }
        plan = compute_form_plan(
            class_def, {"type": "TestType", "health": 100}, groups
        )
        names = [g.group_name for g in plan]
        assert "consumption" not in names
