"""Tests for app.core.content_store — ContentStore CRUD + atomic writes.

Uses tmp_path fixture for isolated filesystem tests.
"""

import json
import pytest
from pathlib import Path

from app.core.content_store import ContentStore, ContentRef, ContentData


@pytest.fixture
def content_dir(tmp_path):
    """Create a temporary content directory with sample data."""
    units = tmp_path / "units"
    units.mkdir()
    (units / "my-soldier.json").write_text(
        json.dumps({"type": "UnitType", "health": 100, "speed": 1.2}),
        encoding="utf-8",
    )
    (units / "my-tank.json").write_text(
        json.dumps({"type": "UnitType", "health": 500, "squareShape": True}),
        encoding="utf-8",
    )

    blocks = tmp_path / "blocks"
    blocks.mkdir()
    (blocks / "my-wall.json").write_text(
        json.dumps({"type": "Wall", "health": 200}),
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def store(content_dir):
    return ContentStore(content_dir)


# ── list ───────────────────────────────────────────────────────────────


class TestList:
    def test_list_all(self, store):
        refs = store.list()
        names = {r.name for r in refs}
        assert names == {"my-soldier", "my-tank", "my-wall"}

    def test_list_filtered_by_category(self, store):
        refs = store.list(category="units")
        assert len(refs) == 2
        assert all(r.category == "units" for r in refs)

    def test_list_empty_category(self, store):
        refs = store.list(category="weapons")
        assert refs == []

    def test_list_returns_content_type(self, store):
        refs = store.list(category="units")
        types = {r.content_type for r in refs}
        assert types == {"UnitType"}

    def test_list_returns_paths(self, store):
        refs = store.list()
        for r in refs:
            assert r.path.exists()

    def test_list_skips_invalid_json(self, store, content_dir):
        (content_dir / "units" / "broken.json").write_text("{invalid", encoding="utf-8")
        refs = store.list(category="units")
        names = {r.name for r in refs}
        assert "broken" not in names

    def test_list_empty_dir(self, tmp_path):
        store = ContentStore(tmp_path / "nonexistent")
        assert store.list() == []


# ── get ────────────────────────────────────────────────────────────────


class TestGet:
    def test_get_existing(self, store):
        data = store.get("my-soldier")
        assert isinstance(data, ContentData)
        assert data.name == "my-soldier"
        assert data.category == "units"
        assert data.data["health"] == 100

    def test_get_from_second_category(self, store):
        data = store.get("my-wall")
        assert data.category == "blocks"
        assert data.data["type"] == "Wall"

    def test_get_missing_raises(self, store):
        with pytest.raises(FileNotFoundError, match="Content not found"):
            store.get("nonexistent")

    def test_get_returns_path(self, store):
        data = store.get("my-soldier")
        assert data.path is not None
        assert data.path.exists()


# ── save ───────────────────────────────────────────────────────────────


class TestSave:
    def test_save_new_file(self, store, content_dir):
        path = store.save("new-unit", {"type": "UnitType", "health": 50}, "units")
        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["health"] == 50

    def test_save_creates_category_dir(self, store, content_dir):
        store.save("my-weapon", {"type": "Weapon"}, "weapons")
        assert (content_dir / "weapons" / "my-weapon.json").exists()

    def test_save_overwrites_existing(self, store):
        store.save("my-soldier", {"type": "UnitType", "health": 999}, "units")
        data = store.get("my-soldier")
        assert data.data["health"] == 999

    def test_save_atomic_no_temp_leftover(self, store, content_dir):
        store.save("clean-unit", {"type": "UnitType"}, "units")
        temps = list((content_dir / "units").glob(".*_*.tmp"))
        assert temps == []

    def test_save_returns_path(self, store):
        path = store.save("ret-unit", {"type": "UnitType"}, "units")
        assert isinstance(path, Path)
        assert path.name == "ret-unit.json"

    def test_save_unicode_content(self, store):
        store.save("cn-unit", {"type": "UnitType", "localizedName": "步兵"}, "units")
        data = store.get("cn-unit")
        assert data.data["localizedName"] == "步兵"


# ── delete ─────────────────────────────────────────────────────────────


class TestDelete:
    def test_delete_existing(self, store):
        store.delete("my-soldier")
        with pytest.raises(FileNotFoundError):
            store.get("my-soldier")

    def test_delete_missing_raises(self, store):
        with pytest.raises(FileNotFoundError, match="Content not found"):
            store.delete("nonexistent")

    def test_delete_does_not_affect_others(self, store):
        store.delete("my-soldier")
        refs = store.list(category="units")
        names = {r.name for r in refs}
        assert names == {"my-tank"}


# ── round-trip ─────────────────────────────────────────────────────────


class TestRoundTrip:
    def test_save_then_get(self, store):
        original = {"type": "Wall", "health": 300, "armor": 5}
        store.save("roundtrip", original, "blocks")
        loaded = store.get("roundtrip")
        assert loaded.data == original

    def test_save_delete_save(self, store):
        store.save("phoenix", {"type": "UnitType"}, "units")
        store.delete("phoenix")
        store.save("phoenix", {"type": "UnitType", "health": 1}, "units")
        data = store.get("phoenix")
        assert data.data["health"] == 1
