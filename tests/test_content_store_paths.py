"""Explicit content identity remains unambiguous across categories."""

import json

import pytest

from app.core.content_store import ContentStore
from app.core.session import ProjectSession


def test_explicit_path_reads_same_name_in_different_categories(tmp_path):
    for category, health in [("units", 100), ("blocks", 500)]:
        folder = tmp_path / category
        folder.mkdir()
        (folder / "同名 文件.json").write_text(json.dumps({"health": health}), encoding="utf-8")
    store = ContentStore(tmp_path)
    assert store.get_by_path("units/同名 文件.json").data["health"] == 100
    assert store.get_by_path("blocks/同名 文件.json").data["health"] == 500


@pytest.mark.parametrize("path", ["../outside.json", "units/../blocks/a.json", "/units/a.json", "C:/a.json", "units\\a.json", "units/a.png", "units/sub/a.json"])
def test_explicit_path_rejects_noncanonical_or_out_of_scope_paths(tmp_path, path):
    with pytest.raises(ValueError):
        ContentStore(tmp_path).get_by_path(path)


def test_explicit_path_rejects_symlink_escape(tmp_path):
    root = tmp_path / "content"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "a.json").write_text('{}', encoding="utf-8")
    try:
        (root / "units").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("当前 Windows 权限不支持创建符号链接")
    with pytest.raises(ValueError):
        ContentStore(root).get_by_path("units/a.json")


def test_new_project_does_not_reuse_previous_core_document(tmp_path):
    session = ProjectSession("metadata")
    first = session.create_project(tmp_path, "first", "第一个")
    first.contents.save("same", {"health": 100}, "units")
    assert session.read_content("units/same.json").data["health"] == 100
    second = session.create_project(tmp_path, "second", "第二个")
    second.contents.save("same", {"health": 200}, "units")
    assert session.read_content("units/same.json").data["health"] == 200
