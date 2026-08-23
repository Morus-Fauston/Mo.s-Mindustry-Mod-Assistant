"""Tests for app.core.config_loader — centralized config loading and display modes."""

import pytest

from app.core.config_loader import (
    clear_cache,
    display_name,
    get_category_names_zh,
    get_field_docs,
    get_field_groups,
    get_field_names_zh,
    get_vanilla_weapon_names_zh,
    set_display_mode,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset display mode and cache between tests."""
    clear_cache()
    set_display_mode("zh_en")
    yield
    set_display_mode("zh_en")


class TestConfigLoading:
    def test_field_names_zh_loads(self):
        names = get_field_names_zh()
        assert isinstance(names, dict)
        assert len(names) > 100
        assert "health" in names

    def test_field_docs_loads(self):
        docs = get_field_docs()
        assert isinstance(docs, dict)
        assert len(docs) > 100

    def test_field_groups_loads(self):
        groups = get_field_groups()
        assert "UnitType" in groups
        assert "Weapon" in groups
        assert "BasicBulletType" in groups

    def test_vanilla_weapon_names_loads(self):
        names = get_vanilla_weapon_names_zh()
        assert isinstance(names, dict)
        assert len(names) > 40
        assert "artillery" in names

    def test_category_names_loads(self):
        names = get_category_names_zh()
        assert names["UnitTypes"] == "单位"
        assert names["Weapons"] == "武器"

    def test_missing_config_returns_empty_dict(self):
        from app.core.config_loader import get_config
        result = get_config("nonexistent_file_xyz")
        assert result == {}

    def test_caching(self):
        names1 = get_field_names_zh()
        names2 = get_field_names_zh()
        assert names1 is names2  # Same object (cached)


class TestDisplayModes:
    def test_zh_en_mode(self):
        set_display_mode("zh_en")
        result = display_name("health")
        assert "生命值" in result
        assert "health" in result
        assert result == "生命值 (health)"

    def test_en_zh_mode(self):
        set_display_mode("en_zh")
        result = display_name("health")
        assert result == "health (生命值)"

    def test_zh_mode(self):
        set_display_mode("zh")
        result = display_name("health")
        assert result == "生命值"

    def test_en_mode(self):
        set_display_mode("en")
        result = display_name("health")
        assert result == "health"

    def test_unknown_field_fallback(self):
        set_display_mode("zh_en")
        result = display_name("someUnknownField12345")
        assert result == "someUnknownField12345"

    def test_invalid_mode_ignored(self):
        set_display_mode("zh_en")
        set_display_mode("invalid_mode")
        # Should stay at zh_en
        result = display_name("health")
        assert result == "生命值 (health)"

    def test_custom_names_dict(self):
        custom = {"myField": "我的字段"}
        result = display_name("myField", custom)
        assert result == "我的字段 (myField)"


class TestFieldGroupsBulletTypes:
    def test_basic_bullet_has_groups(self):
        groups = get_field_groups()
        basic = groups["BasicBulletType"]
        assert "basic" in basic
        assert "pierce" in basic
        assert "splash" in basic

    def test_basic_bullet_required_fields(self):
        groups = get_field_groups()
        basic = groups["BasicBulletType"]["basic"]
        assert "damage" in basic["required"]
        assert "speed" in basic["required"]
        assert "lifetime" in basic["required"]

    def test_basic_bullet_defaults(self):
        groups = get_field_groups()
        basic = groups["BasicBulletType"]["basic"]
        defaults = basic.get("defaults", {})
        assert defaults.get("damage") == 10
        assert defaults.get("speed") == 3

    def test_laser_bullet_has_laser_group(self):
        groups = get_field_groups()
        laser = groups["LaserBulletType"]
        assert "laser" in laser

    def test_flak_bullet_has_flak_group(self):
        groups = get_field_groups()
        flak = groups["FlakBulletType"]
        assert "flak" in flak

    def test_missile_bullet_has_homing_group(self):
        groups = get_field_groups()
        missile = groups["MissileBulletType"]
        assert "homing" in missile


class TestV030FieldGroups:
    def test_research_is_in_the_shared_tech_tree_group(self):
        groups = get_field_groups()
        for content_type in (
            "UnitType", "Wall", "ItemTurret", "PowerTurret", "GenericCrafter",
            "Drill", "Conveyor", "Battery", "MendProjector",
        ):
            tech_tree = groups[content_type]["tech_tree"]
            assert tech_tree["required"] == ["research"]
            assert tech_tree["widgets"]["research"]["widget"] == "research"

    def test_unit_combat_is_split_by_the_confirmed_workflow(self):
        unit = get_field_groups()["UnitType"]
        assert "combat" not in unit
        assert unit["weapons_range"]["required"] == ["weapons", "range"]
        assert "maxRange" in unit["weapons_range"]["default"]
        assert "targetAir" in unit["target_selection"]["required"]
        assert "canAttack" in unit["attack_behavior"]["default"]

    def test_shown_planets_is_in_each_supported_basic_group(self):
        groups = get_field_groups()
        for content_type in (
            "UnitType", "Wall", "ItemTurret", "PowerTurret", "GenericCrafter",
            "Drill", "Conveyor", "Battery", "MendProjector",
        ):
            basic = groups[content_type]["basic"]
            assert "shownPlanets" in basic["optional"]
            assert basic["widgets"]["shownPlanets"]["widget"] == "planet_set"
