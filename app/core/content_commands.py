"""Reversible, project-local file mutations for existing content files.

Snapshots are command-lifetime memory, not a new on-disk project format.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable
import os
import tempfile
import json

from .commands import Command
from .project import Project


@dataclass(frozen=True)
class ContentChange:
    action: str
    before_path: str | None
    after_path: str | None
    resource_moves: tuple[tuple[str, str], ...] = ()
    before_data: dict | None = None
    after_data: dict | None = None


def local_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or any(char in relative for char in ("\\", ":", "\x00")):
        raise ValueError("工程内路径无效。")
    parts = PurePosixPath(relative)
    if (parts.is_absolute() or not parts.parts or parts.as_posix() != relative
            or any(part in (".", "..") for part in parts.parts)):
        raise ValueError("路径必须是规范的工程内相对路径。")
    base = root.resolve()
    target = base / relative
    # Reject aliases as well as outward links: category identity must be exact.
    if target.resolve() != target or not target.resolve().is_relative_to(base):
        raise ValueError("内容路径不能通过链接指向其他位置。")
    return target


def file_bytes(path: Path) -> bytes | None:
    if path.exists() and not path.is_file():
        raise ValueError("操作目标不是普通文件。")
    return path.read_bytes() if path.exists() else None


class ContentFilesCommand(Command):
    """One command owns all affected file bytes, rollback and identity notice.

    on_change runs inside the command. It must restore identities atomically
    and accept the inverse notification if its forward application raises.
    """

    def __init__(self, root: Path, before: dict[str, bytes | None], after: dict[str, bytes | None],
                 change: ContentChange, on_change: Callable[[ContentChange, bool], None] | None = None,
                 trusted_files: dict[str, bytes | None] | None = None):
        self.root = root.resolve()
        self.before, self.after = dict(before), dict(after)
        self.change, self.on_change = change, on_change
        self.trusted_files = trusted_files if trusted_files is not None else {}

    @property
    def description(self) -> str:
        label = {"create": "新建内容", "rename": "重命名内容", "delete": "删除内容"}[self.change.action]
        return f"{label} {self.change.after_path or self.change.before_path}"

    def execute(self) -> None:
        self._apply(self.before, self.after, False)

    def undo(self) -> None:
        self._apply(self.after, self.before, True)

    def _apply(self, expected: dict[str, bytes | None], desired: dict[str, bytes | None], undo: bool) -> None:
        paths = {name: local_path(self.root, name) for name in expected}
        observed = {}
        for name, path in paths.items():
            observed[name] = file_bytes(path)
            if observed[name] != expected[name] and not (name in self.trusted_files and observed[name] == self.trusted_files[name]):
                raise ValueError("文件已被其他操作修改，已停止以免覆盖：" + name)
        completed: list[str] = []
        callback_started = False
        try:
            # Write destinations before deleting sources, so source bytes survive
            # even when a later destination is locked or otherwise unwritable.
            order = sorted(desired, key=lambda name: desired[name] is None)
            for name in order:
                if desired[name] != observed[name]:
                    self._write(local_path(self.root, name), desired[name])
                    completed.append(name)
            if self.on_change:
                callback_started = True
                self.on_change(self.change, undo)
            self.trusted_files.update(desired)
        except Exception as failure:
            recovery_errors = []
            for name in reversed(completed):
                try:
                    self._write(local_path(self.root, name), observed[name])
                except Exception as exc:
                    recovery_errors.append(exc)
            if callback_started and self.on_change:
                try:
                    self.on_change(self.change, not undo)
                except Exception as exc:
                    recovery_errors.append(exc)
            if recovery_errors:
                raise ExceptionGroup("内容操作失败，部分回滚未完成，请保留工程并检查文件占用。", [failure, *recovery_errors])
            raise

    @staticmethod
    def _write(path: Path, value: bytes | None) -> None:
        if value is None:
            path.unlink()
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".moma-content-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(value)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)


class NewProjectCommand(Command):
    """Create only a missing old-format project directory, never overwrite one."""

    _directories = ("content", "content/units", "content/blocks", "content/weapons",
                    "sprites", "sprites/units", "sprites/blocks", "sprites/weapons")

    def __init__(self, project: Project, on_change: Callable[[Project, bool], None] | None = None):
        self.project, self.on_change = project, on_change
        self.root = project.root
        self._mod_bytes = (json.dumps(project.mod_info.to_dict(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    @property
    def description(self) -> str:
        return f"新建工程 {self.project.mod_info.name}"

    def _safe_root(self) -> None:
        if not self.root.parent.is_dir() or self.root.resolve() != self.root:
            raise ValueError("工程目标目录已变化，请重新选择父目录。")

    def execute(self) -> None:
        self._safe_root()
        if self.root.exists() or self.root.is_symlink():
            raise FileExistsError("工程目标目录已存在，请选择新的模组 ID。")
        created: list[Path] = []
        callback_started = False
        try:
            self.root.mkdir()
            created.append(self.root)
            for name in self._directories:
                path = local_path(self.root, name)
                path.mkdir()
                created.append(path)
            mod = local_path(self.root, "mod.json")
            ContentFilesCommand._write(mod, self._mod_bytes)
            created.append(mod)
            if self.on_change:
                callback_started = True
                self.on_change(self.project, False)
        except Exception as failure:
            errors = []
            for path in reversed(created):
                try:
                    if path == self.root:
                        self._safe_root()
                    else:
                        local_path(self.root, path.relative_to(self.root).as_posix())
                    path.rmdir() if path.is_dir() else path.unlink()
                except Exception as exc:
                    errors.append(exc)
            if callback_started and self.on_change:
                try:
                    self.on_change(self.project, True)
                except Exception as exc:
                    errors.append(exc)
            if errors:
                raise ExceptionGroup("新建工程失败，部分清理未完成，请检查目标目录。", [failure, *errors])
            raise

    def undo(self) -> None:
        self._safe_root()
        expected = {*self._directories, "mod.json"}
        actual = {path.relative_to(self.root).as_posix() for path in self.root.rglob("*")}
        if actual != expected:
            raise ValueError("工程中出现了其他文件，已停止撤销以免删除用户资料。")
        for name in expected:
            local_path(self.root, name)
        mod = self.root / "mod.json"
        if file_bytes(mod) != self._mod_bytes or any(not (self.root / name).is_dir() for name in self._directories):
            raise ValueError("工程内容已改变，不能撤销创建。")
        removed: list[Path] = []
        mod_removed = callback_started = False
        try:
            mod.unlink()
            mod_removed = True
            for name in reversed(self._directories):
                path = local_path(self.root, name)
                path.rmdir()
                removed.append(path)
            self.root.rmdir()
            removed.append(self.root)
            if self.on_change:
                callback_started = True
                self.on_change(self.project, True)
        except Exception as failure:
            errors = []
            for path in reversed(removed):
                try:
                    path.mkdir()
                except Exception as exc:
                    errors.append(exc)
            if mod_removed:
                try:
                    ContentFilesCommand._write(mod, self._mod_bytes)
                except Exception as exc:
                    errors.append(exc)
            if callback_started and self.on_change:
                try:
                    self.on_change(self.project, False)
                except Exception as exc:
                    errors.append(exc)
            if errors:
                raise ExceptionGroup("撤销新建工程失败，部分恢复未完成。", [failure, *errors])
            raise
