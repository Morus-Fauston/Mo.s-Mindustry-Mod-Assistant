"""Desktop bootstrap contract, tested against actual metadata files."""

import json

import pytest

from app.desktop.api import DesktopApi


def test_bootstrap_reads_local_metadata_and_rejects_protocol_mismatch(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({
        "gameVersion": "159", "classes": ["UnitType", "Weapon"],
        "instanceCategories": ["Units"],
    }), encoding="utf-8")
    units = tmp_path / "instances" / "Units"
    units.mkdir(parents=True)
    (units / "dagger.json").write_text('{}', encoding="utf-8")

    api = DesktopApi(tmp_path)
    assert api.bootstrap(99)["error"]["code"] == "PROTOCOL_MISMATCH"
    result = api.bootstrap(1)
    assert result["ok"] is True
    assert result["data"]["metadata"] == {
        "gameVersion": "159", "classCount": 2,
        "categories": [{"name": "Units", "count": 1}],
    }
    assert api.bootstrap(1) == result


def test_missing_or_corrupt_metadata_can_be_retried_without_restarting(tmp_path):
    api = DesktopApi(tmp_path)
    missing = api.bootstrap(1)
    assert missing["ok"] is False
    assert missing["error"]["code"] == "METADATA_UNAVAILABLE"
    (tmp_path / "manifest.json").write_text('{broken', encoding="utf-8")
    assert api.bootstrap(1)["error"]["code"] == "METADATA_UNAVAILABLE"
    (tmp_path / "manifest.json").write_text(json.dumps({
        "gameVersion": "159", "classes": ["UnitType"], "instanceCategories": [],
    }), encoding="utf-8")
    assert api.bootstrap(1)["data"]["metadata"]["classCount"] == 1


@pytest.mark.parametrize("manifest", [
    [], None, {},
    {"gameVersion": 159, "classes": [], "instanceCategories": []},
    {"gameVersion": "159", "classes": "UnitType", "instanceCategories": []},
    {"gameVersion": "159", "classes": [None], "instanceCategories": []},
    {"gameVersion": "159", "classes": [], "instanceCategories": "Units"},
    {"gameVersion": "159", "classes": [], "instanceCategories": ["../outside"]},
])
def test_invalid_manifest_returns_recoverable_structured_error(tmp_path, manifest):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    api = DesktopApi(tmp_path)
    response = api.bootstrap(1)
    assert response["ok"] is False
    assert response["protocolVersion"] == 1
    assert response["error"]["code"] == "METADATA_UNAVAILABLE"
    assert "重试" in response["error"]["message"]
    manifest_path.write_text(json.dumps({
        "gameVersion": "159", "classes": ["UnitType"], "instanceCategories": [],
    }), encoding="utf-8")
    assert api.bootstrap(1)["data"]["metadata"]["classCount"] == 1


def test_declared_instance_category_must_exist_before_bootstrap_is_cached(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({
        "gameVersion": "159", "classes": ["UnitType"], "instanceCategories": ["Units"],
    }), encoding="utf-8")
    api = DesktopApi(tmp_path)
    assert api.bootstrap(1)["error"]["code"] == "METADATA_UNAVAILABLE"
    units = tmp_path / "instances" / "Units"
    units.mkdir(parents=True)
    (units / "dagger.json").write_text('{}', encoding="utf-8")
    result = api.bootstrap(1)
    assert result["data"]["metadata"]["categories"] == [{"name": "Units", "count": 1}]
    (units / "dagger.json").unlink()
    assert api.bootstrap(1) == result
