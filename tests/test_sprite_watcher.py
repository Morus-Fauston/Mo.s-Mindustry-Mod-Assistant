"""SpriteWatcher（F-21 精灵图目录监听）单元测试。

覆盖：归属判定（当前 content 精灵 vs 其他）、目录结构变化标记、
防抖合并（一次 flush 只发一次信号）。QFileSystemWatcher 的真实
文件系统事件不在这里测（需要真机），这里直接调内部方法验证纯逻辑。
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.ui.widgets.sprite_watcher import SpriteWatcher


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def watcher(qapp, tmp_path):
    w = SpriteWatcher()
    yield w
    w.unwatch()


class TestNotePathChange:
    """归属判定：_note_path_change 是否正确分类变更文件。"""

    def _make_project(self, tmp_path):
        from app.core.project import ModInfo, Project

        root = tmp_path / "proj"
        (root / "sprites" / "units").mkdir(parents=True)
        return Project(root, ModInfo(name="test-mod"))

    def test_current_content_sprite(self, watcher, tmp_path):
        """当前 content 的精灵图变更 → 记入 sprite_changed。"""
        proj = self._make_project(tmp_path)
        watcher.watch(proj)
        watcher.set_current_content("units", "坦候")

        watcher._note_path_change(proj.sprites_dir / "units" / "坦候-cell.png")

        assert watcher._pending_sprite == {("units", "坦候")}
        assert not watcher._pending_restructure

    def test_other_content_sprite(self, watcher, tmp_path):
        """其他 content 的精灵图变更 → 只标记结构变化（刷新图层树）。"""
        proj = self._make_project(tmp_path)
        watcher.watch(proj)
        watcher.set_current_content("units", "坦候")

        watcher._note_path_change(proj.sprites_dir / "units" / "其他.png")

        assert watcher._pending_sprite == set()
        assert watcher._pending_restructure

    def test_sprites_root_change(self, watcher, tmp_path):
        """sprites/ 根级变更（分类目录被删）→ 结构变化。"""
        proj = self._make_project(tmp_path)
        watcher.watch(proj)

        watcher._note_path_change(proj.sprites_dir / "units")

        assert watcher._pending_sprite == set()
        assert watcher._pending_restructure

    def test_outside_sprites_ignored(self, watcher, tmp_path):
        """sprites/ 之外的路径 → 忽略。"""
        proj = self._make_project(tmp_path)
        watcher.watch(proj)

        watcher._note_path_change(tmp_path / "content" / "unit.json")

        assert watcher._pending_sprite == set()
        assert not watcher._pending_restructure


class TestFlushDebounce:
    """防抖合并：_flush 发出合并后的信号。"""

    def _make_project(self, tmp_path):
        from app.core.project import ModInfo, Project

        root = tmp_path / "proj"
        (root / "sprites" / "units").mkdir(parents=True)
        return Project(root, ModInfo(name="test-mod"))

    def test_flush_emits_sprite_changed(self, watcher, tmp_path):
        proj = self._make_project(tmp_path)
        watcher.watch(proj)
        watcher.set_current_content("units", "坦候")

        received = []
        watcher.sprite_changed.connect(lambda c, n: received.append((c, n)))

        watcher._note_path_change(proj.sprites_dir / "units" / "坦候.png")
        watcher._note_path_change(proj.sprites_dir / "units" / "坦候-cell.png")
        watcher._flush()

        # 同一个 content 的多个图层变更合并成一次
        assert received == [("units", "坦候")]

    def test_flush_clears_pending(self, watcher, tmp_path):
        proj = self._make_project(tmp_path)
        watcher.watch(proj)
        watcher.set_current_content("units", "坦候")

        watcher._note_path_change(proj.sprites_dir / "units" / "坦候.png")
        watcher._flush()
        assert watcher._pending_sprite == set()
        assert not watcher._pending_restructure

    def test_flush_emits_restructure(self, watcher, tmp_path):
        proj = self._make_project(tmp_path)
        watcher.watch(proj)
        watcher.set_current_content("units", "坦候")

        received = []
        watcher.sprites_restructured.connect(lambda: received.append(True))

        watcher._note_path_change(proj.sprites_dir / "units" / "其他.png")
        watcher._flush()

        assert received == [True]
