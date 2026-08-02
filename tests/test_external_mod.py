"""外部 mod 参考导入（F-52）core 层测试。

覆盖：文件夹解析 / zip 解析（顶层根 + 一层包裹）/ mod 根判定 /
content 扫描 / 清理临时目录 / 坏 JSON 容错。
"""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app.core.external_mod import ExternalMod, _find_mod_root


def _make_mod(root, mod_name="ext-mod"):
    """构造一个最小 mod 目录。"""
    root.mkdir(parents=True, exist_ok=True)
    (root / "mod.json").write_text(
        json.dumps({"name": mod_name}), encoding="utf-8"
    )
    (root / "content" / "units").mkdir(parents=True)
    (root / "content" / "blocks").mkdir(parents=True)
    (root / "content" / "units" / "soldier.json").write_text(
        json.dumps({"type": "UnitType", "health": 100}), encoding="utf-8"
    )
    (root / "content" / "blocks" / "wall.json").write_text(
        json.dumps({"type": "Wall", "health": 200}), encoding="utf-8"
    )
    (root / "content" / "units" / "broken.json").write_text(
        "{bad json", encoding="utf-8"
    )
    return root


class TestLoadFromFolder:
    def test_scan_structure(self, tmp_path):
        root = _make_mod(tmp_path / "mymod")
        mod = ExternalMod.load_from_folder(root)
        assert mod.name == "ext-mod"
        assert mod.categories() == ["blocks", "units"]
        assert mod.names("units") == ["soldier"]
        assert mod.get("units", "soldier")["health"] == 100
        assert mod.get("blocks", "wall")["type"] == "Wall"

    def test_bad_json_skipped(self, tmp_path):
        root = _make_mod(tmp_path / "mymod")
        mod = ExternalMod.load_from_folder(root)
        # broken.json 解析失败应被跳过
        assert "broken" not in mod.names("units")

    def test_missing_dir_raises(self, tmp_path):
        with pytest.raises(ValueError):
            ExternalMod.load_from_folder(tmp_path / "不存在")

    def test_mod_json_missing_uses_dirname(self, tmp_path):
        root = tmp_path / "other-mod"
        (root / "content" / "units").mkdir(parents=True)
        (root / "content" / "units" / "a.json").write_text(
            json.dumps({"type": "UnitType"}), encoding="utf-8"
        )
        mod = ExternalMod.load_from_folder(root)
        assert mod.name == "other-mod"


class TestLoadFromZip:
    def test_zip_top_level_root(self, tmp_path):
        root = _make_mod(tmp_path / "src")
        zp = tmp_path / "mod.zip"
        with zipfile.ZipFile(zp, "w") as zf:
            for f in root.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(root))
        mod = ExternalMod.load_from_zip(zp)
        try:
            assert mod.name == "ext-mod"
            assert mod.names("units") == ["soldier"]
        finally:
            mod.cleanup()
            assert not mod.root.exists()

    def test_zip_wrapped_root(self, tmp_path):
        root = _make_mod(tmp_path / "src")
        wrapper = tmp_path / "some-wrapper"
        zp = tmp_path / "wrapped.zip"
        with zipfile.ZipFile(zp, "w") as zf:
            for f in root.rglob("*"):
                if f.is_file():
                    zf.write(f, str(Path("wrapper") / f.relative_to(root)))
        mod = ExternalMod.load_from_zip(zp)
        try:
            assert mod.name == "ext-mod"
        finally:
            mod.cleanup()

    def test_zip_no_mod_root(self, tmp_path):
        bad = tmp_path / "bad"
        bad.mkdir()
        (bad / "readme.txt").write_text("hi", encoding="utf-8")
        zp = tmp_path / "bad.zip"
        with zipfile.ZipFile(zp, "w") as zf:
            zf.write(bad / "readme.txt", "readme.txt")
        with pytest.raises(ValueError):
            ExternalMod.load_from_zip(zp)


class TestFindModRoot:
    def test_top_level(self, tmp_path):
        root = _make_mod(tmp_path / "r")
        assert _find_mod_root(root) == root

    def test_wrapped(self, tmp_path):
        root = _make_mod(tmp_path / "r")
        wrapper = tmp_path / "w"
        (wrapper / "inner").mkdir(parents=True)
        # 模拟一层包裹：把 r 的内容移到 wrapper/inner
        import shutil

        shutil.move(str(root / "mod.json"), wrapper / "inner" / "mod.json")
        shutil.move(str(root / "content"), wrapper / "inner" / "content")
        assert _find_mod_root(wrapper) == wrapper / "inner"

    def test_no_root(self, tmp_path):
        empty = tmp_path / "e"
        empty.mkdir()
        assert _find_mod_root(empty) is None
