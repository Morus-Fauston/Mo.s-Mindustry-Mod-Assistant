"""Static preview contracts use real PNG pixels and existing project files."""

import base64
from io import BytesIO

from PIL import Image
import pytest

from app.core.content_store import ContentData
from app.core.project import Project
from app.desktop.preview import PreviewService


def png(project, category, name, size=(16, 12), color=(255, 0, 0, 255)):
    path = project.sprite_path(category, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, color).save(path)
    return path


def content(project, data, category="units", name="unit"):
    path = project.contents.save(name, data, category)
    return project.contents.get_by_path(f"{category}/{name}.json")


def test_real_png_scene_preserves_dimensions_pixels_and_explicit_identity(tmp_path):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "mech"})
    source = png(project, "units", "unit")
    service = PreviewService(project, "session-a")
    scene = service.scene(doc)
    assert scene["status"] == "ready"
    assert (scene["width"], scene["height"]) == (16, 12)
    assert scene["sessionId"] == "session-a"
    base = scene["layers"][0]
    assert (base["key"], base["x"], base["y"], base["z"], base["flipX"]) == ("", 0, 0, 0, False)
    resource = service.resource(base["resourceId"])
    assert resource["mime"] == "image/png"
    assert (resource["width"], resource["height"]) == (16, 12)
    encoded = base64.b64decode(resource["dataUrl"].split(",", 1)[1])
    with Image.open(BytesIO(encoded)) as decoded, Image.open(source) as original:
        assert decoded.convert("RGBA").tobytes() == original.convert("RGBA").tobytes()


def test_layers_subtypes_weapon_mirror_and_legacy_engine_vectors(tmp_path):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "mech", "weapons": [{"name": "gun", "mirror": True}],
                            "engineSize": 2, "engineOffset": 3, "engineColor": "123456"})
    project.contents.save("gun", {"x": 3, "y": 2}, "weapons")
    # Same-name unit must never supply weapon offsets.
    project.contents.save("gun", {"x": 100, "y": 200}, "units")
    for name in ("unit", "unit-cell", "unit-outline", "unit-shadow", "unit-leg", "unit-leg-base", "unit-treads"):
        png(project, "units", name, size=(32, 24))
    png(project, "weapons", "gun", size=(8, 4))
    scene = PreviewService(project, "session").scene(doc)
    layers = scene["layers"]
    assert [layer["key"] for layer in layers] == ["", "-cell", "-outline", "-shadow", "-leg", "__weapon_0__", "__weapon_0__"]
    assert [layer["z"] for layer in layers] == [0, 1, -2, -3, 2, 10, 10]
    assert [(layer["x"], layer["y"], layer["flipX"]) for layer in layers[-2:]] == [(24, 2, False), (0, 2, True)]
    outer, inner = scene["circles"]
    assert (outer["cx"], outer["cy"], outer["radius"], outer["z"], outer["color"]) == (16, 24, 8, -1, "#123456")
    # Existing Qt _draw_engine: iy = ey + sin(-90 degrees) * radius / 4.
    assert (inner["cx"], inner["cy"], inner["radius"]) == (16, 22, 4)
    assert inner["color"] == "#ffffff"


def test_fixed_pixel_composite_mirrors_asymmetric_weapon_and_centers_overlays(tmp_path):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "flying", "weapons": [{"name": "gun", "x": 2, "y": 1, "mirror": True}]})
    png(project, "units", "unit", size=(24, 16), color=(0, 0, 0, 0))
    png(project, "units", "unit-cell", size=(2, 2), color=(0, 255, 0, 255))
    path = png(project, "weapons", "gun", size=(2, 1))
    image = Image.new("RGBA", (2, 1))
    image.putdata([(255, 0, 0, 255), (0, 0, 255, 255)])
    image.save(path)
    service = PreviewService(project, "session")
    scene = service.scene(doc)
    cell = next(layer for layer in scene["layers"] if layer["key"] == "-cell")
    assert (cell["x"], cell["y"]) == (11, 7)
    for layer, expected_x, expected_pixels in zip(scene["layers"][-2:], (19, 3),
            ([(255, 0, 0, 255), (0, 0, 255, 255)], [(0, 0, 255, 255), (255, 0, 0, 255)])):
        assert (layer["x"], layer["y"]) == (expected_x, 3.5)
        raw = base64.b64decode(service.resource(layer["resourceId"])["dataUrl"].split(",")[1])
        with Image.open(BytesIO(raw)) as weapon:
            rendered = weapon.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if layer["flipX"] else weapon
            assert [rendered.getpixel((x, 0)) for x in range(2)] == expected_pixels


def test_missing_corrupt_and_disguised_images_recover_without_restarting(tmp_path):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "Wall"}, "blocks")
    service = PreviewService(project, "session")
    missing = service.scene(doc)
    assert missing["status"] == "missing" and not missing["layers"]
    assert missing["warnings"]
    path = project.sprite_path("blocks", "unit")
    path.write_text('<svg onload="alert(1)"></svg>', encoding="utf-8")
    assert service.scene(doc)["status"] == "missing"
    Image.new("RGB", (4, 4)).save(path, format="JPEG")
    assert service.scene(doc)["status"] == "missing"
    png(project, "blocks", "unit")
    assert service.scene(doc)["status"] == "ready"
    project.sprite_path("blocks", "unit", "-team").write_bytes(b"bad png")
    partial = service.scene(doc)
    assert partial["status"] == "missing" and len(partial["layers"]) == 1


def test_resources_are_session_scoped_immutable_and_released_on_scene_switch(tmp_path):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "Wall"}, "blocks")
    png(project, "blocks", "unit")
    service = PreviewService(project, "first")
    rid = service.scene(doc)["layers"][0]["resourceId"]
    original = service.resource(rid)
    original["dataUrl"] = "corrupted response"
    assert service.resource(rid)["dataUrl"].startswith("data:image/png;base64,")
    for invalid in (rid, "sprites/blocks/unit.png", "../mod.json"):
        with pytest.raises(ValueError):
            PreviewService(project, "second").resource(invalid)
    service.scene(doc)
    with pytest.raises(ValueError):
        service.resource(rid)


@pytest.mark.parametrize("boundary,value", [("MAX_FILE_BYTES", 10), ("MAX_PIXELS", 10),
    ("MAX_DIMENSION", 2), ("MAX_OUTPUT_BYTES", 10), ("MAX_CACHE_BYTES", 10), ("MAX_RESOURCES", 0)])
def test_png_resource_limits_fail_closed_with_visible_reason(tmp_path, monkeypatch, boundary, value):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "Wall"}, "blocks")
    png(project, "blocks", "unit")
    monkeypatch.setattr(PreviewService, boundary, value)
    scene = PreviewService(project, "session").scene(doc)
    assert scene["status"] == "missing" and not scene["layers"] and scene["warnings"]


def test_sprite_symlink_outside_project_is_not_read(tmp_path):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "Wall"}, "blocks")
    outside = tmp_path / "outside.png"
    Image.new("RGBA", (2, 2)).save(outside)
    try:
        project.sprite_path("blocks", "unit").symlink_to(outside)
    except OSError:
        pytest.skip("当前权限不支持符号链接")
    scene = PreviewService(project, "session").scene(doc)
    assert scene["status"] == "missing" and not scene["layers"]
    assert "超出" in scene["warnings"][0]


def test_foreign_content_and_weapon_path_traversal_are_rejected(tmp_path):
    project = Project.create(tmp_path, "test", "测试")
    foreign = Project.create(tmp_path, "foreign", "其他")
    doc = content(project, {"type": "mech", "weapons": [{"name": "../../outside"}]})
    foreign_doc = content(foreign, {})
    png(project, "units", "unit")
    service = PreviewService(project, "session")
    with pytest.raises(ValueError):
        service.scene(foreign_doc)
    scene = service.scene(doc)
    assert len(scene["layers"]) == 1
    assert scene["status"] == "missing"


def test_invalid_numeric_engine_and_weapon_values_do_not_break_main_sprite(tmp_path):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "mech", "weapons": [{"name": "gun", "x": "nan"}], "engineSize": "inf"})
    png(project, "units", "unit")
    png(project, "weapons", "gun")
    scene = PreviewService(project, "session").scene(doc)
    assert len(scene["layers"]) == 1 and not scene["circles"]
    assert len(scene["warnings"]) == 2


def test_weapon_png_sibling_and_recursive_fallback_match_existing_order(tmp_path):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "mech", "weapons": [{"name": "sibling"}, {"name": "nested"}]})
    png(project, "units", "unit")
    png(project, "units", "sibling", size=(3, 3))
    path = project.sprites_dir / "custom" / "deep" / "nested.png"
    path.parent.mkdir(parents=True)
    Image.new("RGBA", (5, 5)).save(path)
    scene = PreviewService(project, "session").scene(doc)
    assert [layer["width"] for layer in scene["layers"]] == [16, 3, 5]


def test_png_bad_chunk_checksum_is_reported_without_crashing_scene(tmp_path):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "Wall"}, "blocks")
    path = png(project, "blocks", "unit")
    raw = bytearray(path.read_bytes())
    idat = raw.index(b"IDAT")
    size = int.from_bytes(raw[idat - 4:idat], "big")
    raw[idat + 4 + size] ^= 1
    path.write_bytes(raw)
    scene = PreviewService(project, "session").scene(doc)
    assert scene["status"] == "missing" and scene["warnings"]


def test_resource_limit_keeps_prior_layers_usable_and_reports_partial_preview(tmp_path, monkeypatch):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "mech"})
    png(project, "units", "unit")
    png(project, "units", "unit-cell")
    monkeypatch.setattr(PreviewService, "MAX_RESOURCES", 1)
    service = PreviewService(project, "session")
    scene = service.scene(doc)
    assert len(scene["layers"]) == 1 and scene["status"] == "missing"
    assert service.resource(scene["layers"][0]["resourceId"])["width"] == 16


def test_weapon_search_and_number_are_bounded_with_explicit_warning(tmp_path, monkeypatch):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "mech", "weapons": [{"name": "nested"}, {"name": "extra"}]})
    png(project, "units", "unit")
    png(project, "custom", "nested")
    monkeypatch.setattr(PreviewService, "MAX_WEAPONS", 1)
    monkeypatch.setattr(PreviewService, "MAX_SEARCH_ENTRIES", 1)
    scene = PreviewService(project, "session").scene(doc)
    assert len(scene["layers"]) == 1
    assert len(scene["warnings"]) == 2
    assert "武器数量" in scene["warnings"][0]
    assert "检索数量" in scene["warnings"][1]


def test_engine_above_body_and_tank_filter_match_existing_static_scene(tmp_path):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "tank", "engineSize": 1, "engineLayer": 1})
    for name in ("unit", "unit-treads", "unit-leg"):
        png(project, "units", name)
    scene = PreviewService(project, "session").scene(doc)
    assert [layer["key"] for layer in scene["layers"]] == ["", "-treads"]
    assert [circle["z"] for circle in scene["circles"]] == [11, 11]


def test_scene_decoded_pixel_budget_limits_small_compressed_pngs_and_resets(tmp_path, monkeypatch):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "mech"})
    base = png(project, "units", "unit", size=(16, 16))
    cell = png(project, "units", "unit-cell", size=(16, 16))
    assert base.stat().st_size < 1024 and cell.stat().st_size < 1024
    service = PreviewService(project, "session")
    monkeypatch.setattr(service, "MAX_SCENE_PIXELS", 300, raising=False)
    scene = service.scene(doc)
    assert scene["status"] == "missing"
    assert len(scene["layers"]) == 1
    assert "像素" in scene["warnings"][0]
    assert service.resource(scene["layers"][0]["resourceId"])["width"] == 16
    cell.unlink()
    assert service.scene(doc)["status"] == "ready"


def test_scene_pixel_budget_counts_shared_weapon_resource_only_once(tmp_path, monkeypatch):
    project = Project.create(tmp_path, "test", "测试")
    doc = content(project, {"type": "mech", "weapons": [
        {"name": "gun", "mirror": True}, {"name": "gun", "x": 3},
    ]})
    png(project, "units", "unit", size=(10, 10))
    png(project, "weapons", "gun", size=(10, 10))
    service = PreviewService(project, "session")
    monkeypatch.setattr(service, "MAX_SCENE_PIXELS", 200, raising=False)
    scene = service.scene(doc)
    assert scene["status"] == "ready" and len(scene["layers"]) == 4
    assert len({layer["resourceId"] for layer in scene["layers"]}) == 2
