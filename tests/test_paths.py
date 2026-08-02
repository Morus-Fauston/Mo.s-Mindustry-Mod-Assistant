"""路径统一管理（F-53）测试。

开发模式下 data_dir = 项目根，user_config_dir = 项目 app/config。
打包模式（frozen）下 data = _MEIPASS，user = %APPDATA%/MoMA。
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import app.core.paths as paths


class TestDevMode:
    def test_data_dir_is_project_root(self):
        # app/core/paths.py 的 3 级父目录 = 项目根
        expected = Path(__file__).resolve().parent.parent
        assert paths.data_dir() == expected

    def test_metadata_dir(self):
        assert (paths.metadata_dir() / "manifest.json").exists()

    def test_resources_dir(self):
        assert (paths.resources_dir() / "style.qss").exists()

    def test_user_config_dir_is_app_config(self):
        # 开发模式：用户配置 = 项目 app/config
        assert paths.user_config_dir() == paths.data_dir() / "app" / "config"

    def test_ensure_user_config_dir(self):
        d = paths.ensure_user_config_dir()
        assert d.is_dir()


class TestFrozenMode:
    def test_frozen_paths(self, monkeypatch):
        """模拟打包模式：sys.frozen=True，_MEIPASS 指定路径。"""
        fake_meipass = Path("C:/fake/bundle")
        monkeypatch.setattr("sys.frozen", True, raising=False)
        monkeypatch.setattr("sys._MEIPASS", str(fake_meipass), raising=False)
        try:
            assert paths.is_frozen()
            assert paths.data_dir() == fake_meipass
            assert paths.metadata_dir() == fake_meipass / "metadata"
            # 打包后用户配置不写临时目录，写 APPDATA
            assert paths.user_config_dir() == (
                Path.home() / "AppData" / "Roaming" / "MoMA"
            )
        finally:
            monkeypatch.delattr("sys.frozen", raising=False)
            monkeypatch.delattr("sys._MEIPASS", raising=False)
