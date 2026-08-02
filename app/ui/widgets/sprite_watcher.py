"""精灵图目录监听器（F-21）。

监听工程 sprites/ 目录的递归变更，外部改图（PS 覆盖、资源管理器替换、
自动生成脚本输出）后自动刷新预览与图层树。

设计要点：
- 只监听 sprites/，不监听 content/（外部改 JSON 会使撤销历史与磁盘不一致，
  不是监听能解决的，见规格文档 18.8）。
- QFileSystemWatcher 只能监听已存在的目录且不递归 → 用 addPath 逐个注册
  子目录；新增/删除目录时重建监听集。
- 300ms 防抖：一次连续保存只触发一次刷新（QTimer.singleShot 合并）。
- 归属判定：变更文件是否为「当前 content 的任一精灵图层」或「当前分类下的
  文件」（影响图层树列表），分别对应刷新预览 / 刷新图层树。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from ...core.project import Project


class SpriteWatcher(QObject):
    """监听一个工程的 sprites/ 目录，发出刷新请求信号。

    Signals:
        sprite_changed(str): 变更的是某 content 的精灵图（category/name）
        sprites_restructured(): 目录结构变化（新增/删除），需刷新图层树
    """

    sprite_changed = Signal(str, str)   # (category, name) —— 精灵图归属的 content
    sprites_restructured = Signal()     # 目录结构变化

    # 防抖窗口（毫秒）
    _DEBOUNCE_MS = 300

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        from PySide6.QtCore import QFileSystemWatcher

        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_dir_changed)
        self._watcher.fileChanged.connect(self._on_file_changed)

        self._project: Project | None = None
        self._current_category: str = ""
        self._current_name: str = ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._DEBOUNCE_MS)
        self._timer.timeout.connect(self._flush)
        self._pending_sprite: set[tuple[str, str]] = set()
        self._pending_restructure = False

    # ── 生命周期 ────────────────────────────────────────────────────────

    def watch(self, project: Project) -> None:
        """开始监听一个工程。"""
        self.unwatch()
        self._project = project
        self._rebuild_watch_set()

    def unwatch(self) -> None:
        """停止监听。"""
        dirs = self._watcher.directories()
        files = self._watcher.files()
        if dirs:
            self._watcher.removePaths(dirs)
        if files:
            self._watcher.removePaths(files)
        self._project = None
        self._timer.stop()
        self._pending_sprite.clear()
        self._pending_restructure = False

    def set_current_content(self, category: str, name: str) -> None:
        """记录当前预览的 content，用于归属判定。"""
        self._current_category = category
        self._current_name = name

    # ── 监听集维护 ──────────────────────────────────────────────────────

    def _rebuild_watch_set(self) -> None:
        """递归收集 sprites/ 下所有存在的目录并注册监听。"""
        if self._project is None:
            return
        cur = self._watcher.directories()
        if cur:
            self._watcher.removePaths(cur)
        dirs: list[str] = []
        root = self._project.sprites_dir
        if root.is_dir():
            dirs.append(str(root))
            for d in root.rglob("*"):
                if d.is_dir():
                    dirs.append(str(d))
        self._watcher.addPaths(dirs)

    # ── Qt 信号 → 合并 ─────────────────────────────────────────────────

    def _on_dir_changed(self, _path: str) -> None:
        """目录变化：可能新增/删除了文件或子目录 → 重建监听集 + 标记结构变化。"""
        self._rebuild_watch_set()
        self._pending_restructure = True
        self._kick_timer()

    def _on_file_changed(self, path: str) -> None:
        """文件变化：记录归属，防抖合并。"""
        self._note_path_change(Path(path))

    def _note_path_change(self, p: Path) -> None:
        """判断变更文件归属哪个 content 的精灵图。

        归属判定：变更文件是否为「当前预览 content」的任一图层精灵
        （sprites/{category}/{name}{suffix}.png，suffix 可能为空或 -cell 等）。
        是 → 刷新预览；否（同分类其他文件/目录结构变化）→ 刷新图层树。
        """
        if self._project is None:
            return
        try:
            rel = p.relative_to(self._project.sprites_dir)
        except ValueError:
            return
        parts = rel.parts
        if len(parts) < 2:
            # sprites/ 根下的变更（如整个分类目录被删）
            self._pending_restructure = True
            self._kick_timer()
            return
        category = parts[0]
        filename = parts[-1]

        # 当前预览 content 的精灵前缀：sprites/{cat}/{name}[.或-图层后缀].png
        # 注意：content 名后可能是 "."（主体 xxx.png）或 "-"（-cell/-outline 等）
        if (
            category == self._current_category
            and filename.startswith(self._current_name)
            and filename[len(self._current_name):len(self._current_name) + 1]
            in (".", "-")
        ):
            self._pending_sprite.add((self._current_category, self._current_name))
        else:
            # 其他文件：可能是新 content 的精灵 / 其他分类 → 图层树列表变化
            self._pending_restructure = True
        self._kick_timer()

    def _kick_timer(self) -> None:
        self._timer.start()

    def _flush(self) -> None:
        """防抖窗口结束，发出合并后的信号。"""
        for category, name in self._pending_sprite:
            self.sprite_changed.emit(category, name)
        if self._pending_restructure:
            self.sprites_restructured.emit()
        self._pending_sprite.clear()
        self._pending_restructure = False
