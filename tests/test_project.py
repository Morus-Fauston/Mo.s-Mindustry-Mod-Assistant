"""Tests for app.core.project — Project.open/create edge cases.

v0.2.3 修复：#1 坏 mod.json 打开应抛友好 ValueError（不崩槽）；
#4 新建工程 mod_id 校验（非法字符拒绝）。
"""

import json
import pytest
from pathlib import Path

from app.core.project import Project


def _make_project(root: Path, mod_id: str = "my-mod") -> Path:
    (root / "content" / "units").mkdir(parents=True)
    (root / "content" / "blocks").mkdir(parents=True)
    (root / "content" / "weapons").mkdir(parents=True)
    (root / "mod.json").write_text(
        json.dumps({"name": mod_id, "displayName": "My Mod"}), encoding="utf-8"
    )
    return root


class TestOpen:
    def test_open_valid(self, tmp_path):
        root = _make_project(tmp_path)
        project = Project.open(root)
        assert project.mod_info.name == "my-mod"

    def test_open_missing_mod_json_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            Project.open(tmp_path / "empty")

    def test_open_bad_json_raises_value_error(self, tmp_path):
        root = tmp_path / "bad"
        root.mkdir()
        (root / "mod.json").write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ValueError, match="JSON"):
            Project.open(root)

    def test_open_non_object_json_raises_value_error(self, tmp_path):
        root = tmp_path / "list"
        root.mkdir()
        (root / "mod.json").write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ValueError, match="JSON 对象"):
            Project.open(root)


class TestExportZip:
    def test_verified_handle_export_keeps_legacy_entries_and_bytes(self, tmp_path):
        import zipfile

        root = _make_project(tmp_path / "mod")
        for name, data in {"scripts/main.js": b"script", ".custom/keep.txt": b"custom",
                           "sprites/units/body.png": b"png bytes", "content/units/body.json": b"{}",
                           ".git/HEAD": b"skip", ".hidden": b"skip", "kept.zip": b"asset"}.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        target, legacy = tmp_path / "new.zip", tmp_path / "legacy.zip"
        Project.open(root).export_zip(target)
        # The pre-migration algorithm is the oracle, not another call to the
        # revised export_zip implementation.
        skipped = {".git", ".idea", ".vscode", "__pycache__", ".venv"}
        with zipfile.ZipFile(legacy, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file() and not path.name.startswith(".") and not any(part in skipped for part in path.relative_to(root).parts):
                    archive.write(path, path.relative_to(root).as_posix())
        with zipfile.ZipFile(target) as actual, zipfile.ZipFile(legacy) as expected:
            assert actual.namelist() == expected.namelist()
            for name in actual.namelist():
                assert actual.read(name) == expected.read(name)
                a, e = actual.getinfo(name), expected.getinfo(name)
                assert (a.file_size, a.CRC, a.compress_type, a.external_attr, a.date_time) == (
                    e.file_size, e.CRC, e.compress_type, e.external_attr, e.date_time)

    def test_export_scan_failure_is_not_silently_omitted(self, tmp_path, monkeypatch):
        import os

        root = _make_project(tmp_path / "mod")
        denied = root / "scripts"
        denied.mkdir()
        (denied / "main.js").write_text("keep", encoding="utf-8")
        target = tmp_path / "out.zip"
        target.write_bytes(b"old archive")
        scandir = os.scandir
        def failing_scandir(path):
            if Path(path) == denied:
                raise PermissionError("脚本目录不可读")
            return scandir(path)
        monkeypatch.setattr(os, "scandir", failing_scandir)
        with pytest.raises(PermissionError):
            Project.open(root).export_zip(target)
        assert target.read_bytes() == b"old archive"

    def test_export_inside_project_excludes_itself_and_explicit_old_target(self, tmp_path):
        import zipfile

        root = _make_project(tmp_path)
        (root / "previous.zip").write_bytes(b"previous archive")
        (root / "kept.zip").write_bytes(b"unrelated project asset")
        project = Project.open(root)
        dest = root / "temporary.zip"
        project.export_zip(dest, exclude_paths=[root / "previous.zip"])
        with zipfile.ZipFile(dest) as archive:
            assert "temporary.zip" not in archive.namelist()
            assert "previous.zip" not in archive.namelist()
            assert archive.read("kept.zip") == b"unrelated project asset"

    """导出 Mod 为 Mindustry 可导入的 zip（F-55）。"""

    def test_export_zip_contains_mod_json_and_content(self, tmp_path):
        import zipfile

        root = _make_project(tmp_path)
        (root / "content" / "blocks" / "foo.json").write_text("{}", encoding="utf-8")
        project = Project.open(root)
        dest = tmp_path / "out" / "my-mod.zip"
        project.export_zip(dest)
        assert dest.exists()
        with zipfile.ZipFile(dest) as zf:
            names = zf.namelist()
        assert "mod.json" in names, "zip 根目录应含 mod.json"
        assert "content/blocks/foo.json" in names

    def test_export_zip_skips_hidden_and_cache(self, tmp_path):
        import zipfile

        root = _make_project(tmp_path)
        (root / ".git" / "objects").mkdir(parents=True)
        (root / ".git" / "HEAD").write_text("ref", encoding="utf-8")
        (root / "content" / "__pycache__" / "x.pyc").mkdir(parents=True)
        (root / "content" / "__pycache__" / "x.pyc").touch()
        project = Project.open(root)
        dest = tmp_path / "out.zip"
        project.export_zip(dest)
        with zipfile.ZipFile(dest) as zf:
            names = zf.namelist()
        assert not any(".git" in n for n in names), "应跳过 .git"
        assert not any("__pycache__" in n for n in names), "应跳过 __pycache__"

    def test_export_zip_empty_project(self, tmp_path):
        import zipfile

        root = tmp_path / "empty"
        root.mkdir()
        (root / "mod.json").write_text('{"name": "e"}', encoding="utf-8")
        project = Project.open(root)
        dest = tmp_path / "empty.zip"
        project.export_zip(dest)
        with zipfile.ZipFile(dest) as zf:
            names = zf.namelist()
        assert names == ["mod.json"]


class TestCreate:
    def test_create_valid(self, tmp_path):
        project = Project.create(tmp_path, "new-mod", "New Mod", "me")
        assert (tmp_path / "new-mod" / "mod.json").exists()

    def test_create_empty_id_raises(self, tmp_path):
        with pytest.raises(ValueError, match="不能为空"):
            Project.create(tmp_path, "", "New")

    def test_create_invalid_id_raises(self, tmp_path):
        with pytest.raises(ValueError, match="只能包含"):
            Project.create(tmp_path, "Bad Mod:name", "New")
