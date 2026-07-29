"""Tests for app.core.template — TemplateEngine content generation."""

import pytest

from app.core.template import TemplateEngine
from app.core.metadata import Metadata
from pathlib import Path


@pytest.fixture
def metadata():
    """Load real metadata from the project's metadata/ directory."""
    meta_dir = Path(__file__).parent.parent / "metadata"
    if not meta_dir.exists():
        pytest.skip("metadata/ directory not found")
    return Metadata(meta_dir)


@pytest.fixture
def engine(metadata):
    return TemplateEngine(metadata)


class TestUnitTemplates:
    def test_ground_unit(self, engine):
        t = engine.create("UnitType", "test-unit")
        assert t["type"] == "UnitType"
        assert t["name"] == "test-unit"
        assert t["health"] > 0
        assert t["speed"] > 0
        assert "weapons" in t

    def test_flying_unit(self, engine):
        t = engine.create("UnitType-flying", "test-flyer")
        assert t["flying"] is True
        assert t["health"] > 0
        assert "engineOffset" in t

    def test_tank_unit(self, engine):
        t = engine.create("UnitType-tank", "test-tank")
        assert t["squareShape"] is True
        assert t["crushDamage"] >= 1
        assert t["health"] > 0

    def test_legs_unit(self, engine):
        t = engine.create("UnitType-legs", "test-spider")
        assert t["legCount"] >= 4
        assert t["health"] > 0


class TestBlockTemplates:
    def test_wall(self, engine):
        t = engine.create("Wall", "test-wall")
        assert t["type"] == "Wall"
        assert t["health"] > 0
        assert t["size"] >= 1
        assert "requirements" in t

    def test_item_turret(self, engine):
        t = engine.create("ItemTurret", "test-turret")
        assert t["type"] == "ItemTurret"
        assert t["range"] > 0
        assert t["reload"] > 0
        assert "ammoTypes" in t

    def test_power_turret(self, engine):
        t = engine.create("PowerTurret", "test-power-turret")
        assert t["type"] == "PowerTurret"
        assert t["range"] > 0
        assert "shootType" in t
        assert "consumes" in t


class TestWeaponTemplate:
    def test_weapon(self, engine):
        t = engine.create("Weapon", "test-weapon")
        assert t["type"] == "Weapon"
        assert t["name"] == "test-weapon"
        assert t["reload"] > 0
        assert "bullet" in t
        assert t["bullet"]["type"] == "BasicBulletType"
        assert t["bullet"]["damage"] > 0


class TestTemplateDefaults:
    def test_unknown_kind_raises(self, engine):
        with pytest.raises(ValueError):
            engine.create("NonExistentType", "test")

    def test_all_templates_have_name(self, engine):
        kinds = [
            "UnitType", "UnitType-flying", "UnitType-tank", "UnitType-legs",
            "Wall", "ItemTurret", "PowerTurret", "Weapon",
        ]
        for kind in kinds:
            t = engine.create(kind, "my-test")
            assert t.get("name") == "my-test", f"{kind} template missing name"
