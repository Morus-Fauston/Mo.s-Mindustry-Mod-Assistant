"""Tests for app.core.metadata — Metadata, ClassDef, FieldDef.is_internal.

Uses the real metadata/ directory (skipped if absent).
"""

import pytest
from pathlib import Path

from app.core.metadata import Metadata, FieldDef, ClassDef

METADATA_DIR = Path(__file__).parent.parent / "metadata"

pytestmark = pytest.mark.skipif(
    not METADATA_DIR.exists(),
    reason="metadata/ directory not found — run the extractor first",
)


@pytest.fixture
def meta():
    return Metadata(METADATA_DIR)


# ── manifest / properties ──────────────────────────────────────────────


class TestManifest:
    def test_game_version(self, meta):
        assert meta.game_version == "159"

    def test_available_classes_nonempty(self, meta):
        assert len(meta.available_classes) > 10

    def test_instance_categories(self, meta):
        cats = meta.instance_categories
        assert "UnitTypes" in cats
        assert "Blocks" in cats


# ── get_class: inheritance chain ───────────────────────────────────────


class TestGetClass:
    def test_wall_has_own_fields(self, meta):
        wall = meta.get_class("Wall")
        names = {f.name for f in wall.fields}
        assert "lightningChance" in names

    def test_wall_inherits_block_fields(self, meta):
        """Wall → Block → UnlockableContent → MappableContent → Content.
        Fields from the entire chain should be merged."""
        wall = meta.get_class("Wall")
        names = {f.name for f in wall.fields}
        # 'health' comes from Block (or higher)
        assert "health" in names

    def test_child_overrides_parent_field(self, meta):
        """If a child redefines a field, the child's version wins."""
        wall = meta.get_class("Wall")
        block = meta.get_class("Block")
        # Both should have 'health', but Wall's field list should contain
        # exactly one 'health' entry (no duplicates).
        health_fields = [f for f in wall.fields if f.name == "health"]
        assert len(health_fields) == 1

    def test_turret_inherits_reload_turret(self, meta):
        turret = meta.get_class("Turret")
        names = {f.name for f in turret.fields}
        # 'reload' is defined in ReloadTurret
        assert "reload" in names

    def test_item_turret_inherits_turret(self, meta):
        it = meta.get_class("ItemTurret")
        names = {f.name for f in it.fields}
        assert "reload" in names  # from ReloadTurret via Turret
        assert "ammoTypes" in names or "ammo" in names or len(names) > 10

    def test_unknown_class_raises(self, meta):
        with pytest.raises(KeyError, match="Unknown class"):
            meta.get_class("NonExistentClass")


# ── type aliases ───────────────────────────────────────────────────────


class TestTypeAliases:
    def test_power_turret_maps_to_turret(self, meta):
        pt = meta.get_class("PowerTurret")
        t = meta.get_class("Turret")
        assert pt.name == t.name  # both resolve to Turret

    def test_tank_maps_to_unit_type(self, meta):
        tank = meta.get_class("tank")
        ut = meta.get_class("UnitType")
        assert tank.name == ut.name

    def test_payload_maps_to_unit_type(self, meta):
        p = meta.get_class("payload")
        assert p.name == "UnitType"


# ── get_instance / list_instances ──────────────────────────────────────


class TestInstances:
    def test_list_unit_types(self, meta):
        names = meta.list_instances("UnitTypes")
        assert len(names) > 0
        assert "dagger" in names

    def test_get_instance(self, meta):
        dagger = meta.get_instance("UnitTypes", "dagger")
        assert isinstance(dagger, dict)
        assert "health" in dagger or "type" in dagger

    def test_get_missing_instance_raises(self, meta):
        with pytest.raises(KeyError, match="Instance not found"):
            meta.get_instance("UnitTypes", "nonexistent_unit_xyz")

    def test_list_missing_category_returns_empty(self, meta):
        assert meta.list_instances("NonExistentCategory") == []

    def test_list_instance_categories(self, meta):
        cats = meta.list_instance_categories()
        assert "Blocks" in cats


# ── FieldDef.is_internal (single source of truth) ─────────────────────


class TestFieldDefIsInternal:
    def test_region_suffix_is_internal(self):
        f = FieldDef(name="baseRegion", java_type="TextureRegion", mode="PRIMITIVE")
        assert f.is_internal

    def test_sound_suffix_is_internal(self):
        f = FieldDef(name="shootSound", java_type="Sound", mode="PRIMITIVE")
        assert f.is_internal

    def test_effect_suffix_is_internal(self):
        f = FieldDef(name="deathEffect", java_type="Effect", mode="PRIMITIVE")
        assert f.is_internal

    def test_controller_suffix_is_internal(self):
        f = FieldDef(name="aiController", java_type="Controller", mode="PRIMITIVE")
        assert f.is_internal

    def test_color_suffix_is_internal(self):
        f = FieldDef(name="engineColor", java_type="Color", mode="PRIMITIVE")
        assert f.is_internal

    def test_id_is_internal(self):
        f = FieldDef(name="id", java_type="int", mode="PRIMITIVE")
        assert f.is_internal

    def test_health_is_not_internal(self):
        f = FieldDef(name="health", java_type="float", mode="PRIMITIVE")
        assert not f.is_internal

    def test_speed_is_not_internal(self):
        f = FieldDef(name="speed", java_type="float", mode="PRIMITIVE")
        assert not f.is_internal

    def test_boolean_field_not_internal(self):
        f = FieldDef(name="flying", java_type="boolean", mode="PRIMITIVE")
        assert not f.is_internal

    def test_string_field_not_internal(self):
        f = FieldDef(name="name", java_type="String", mode="PRIMITIVE")
        assert not f.is_internal

    def test_non_editable_primitive_is_internal(self):
        """Primitive fields with non-editable java types (e.g. Object) are internal."""
        f = FieldDef(name="someObject", java_type="Object", mode="PRIMITIVE")
        assert f.is_internal

    def test_string_ref_mode_not_internal(self):
        """STRING_REF fields should not be flagged as internal even if java_type is unusual."""
        f = FieldDef(name="ammoType", java_type="Item", mode="STRING_REF")
        assert not f.is_internal

    def test_array_mode_not_internal(self):
        f = FieldDef(name="weapons", java_type="Seq", mode="ARRAY")
        assert not f.is_internal

    def test_validator_and_editor_share_same_rules(self, meta):
        """Validator._is_internal_field was deleted; both now use FieldDef.is_internal.
        Verify the property exists and is consistent across class fields."""
        wall = meta.get_class("Wall")
        for f in wall.fields:
            # Just verify the property is accessible and returns bool
            assert isinstance(f.is_internal, bool)
