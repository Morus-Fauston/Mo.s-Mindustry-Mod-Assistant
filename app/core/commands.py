"""Command Pattern infrastructure for undo/redo.

Interface (3 methods on CommandStack):
    execute(cmd) / undo() / redo()

All data mutations in the editor go through CommandStack.execute().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Callable


class Command(ABC):
    """A reversible data mutation."""

    @abstractmethod
    def execute(self) -> None: ...

    @abstractmethod
    def undo(self) -> None: ...

    @property
    def description(self) -> str:
        """人类可读的操作描述，用于撤销/重做按钮 tooltip。子类可覆盖。"""
        return "操作"

    def merge_with(self, other: Command) -> Command | None:
        """Try to merge with a subsequent command. Return merged or None."""
        return None


class SetFieldCommand(Command):
    """Set a single field value in a content dict."""

    def __init__(
        self,
        data: dict,
        path: str,
        new_value: object,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._data = data
        self._path = path
        self._new = new_value
        self._old: object = None
        self._on_change = on_change

    @property
    def description(self) -> str:
        return f"修改 {self._path} 为 {self._new}"

    def execute(self) -> None:
        self._old = _get_nested(self._data, self._path)
        _set_nested(self._data, self._path, self._new)
        if self._on_change:
            self._on_change()

    def undo(self) -> None:
        if self._old is _NOT_FOUND:
            _del_nested(self._data, self._path)
        else:
            _set_nested(self._data, self._path, self._old)
        if self._on_change:
            self._on_change()

    def merge_with(self, other: Command) -> Command | None:
        # Merge consecutive edits to the same field (e.g. typing in a number box)
        if (
            isinstance(other, SetFieldCommand)
            and other._data is self._data
            and other._path == self._path
        ):
            # Keep original old value, take new value from other
            merged = SetFieldCommand(self._data, self._path, other._new, self._on_change)
            merged._old = self._old
            return merged
        return None


class ReplaceDataCommand(Command):
    """Replace a complete content dict while preserving its shared identity."""

    def __init__(
        self,
        data: dict,
        replacement: dict,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        if not isinstance(replacement, dict):
            raise TypeError("完整 JSON 输出必须是对象")
        self._data = data
        self._old = deepcopy(data)
        self._new = deepcopy(replacement)
        self._on_change = on_change

    @property
    def description(self) -> str:
        return "替换完整 JSON 输出"

    def execute(self) -> None:
        self._replace_with(self._new)

    def undo(self) -> None:
        self._replace_with(self._old)

    def _replace_with(self, source: dict) -> None:
        self._data.clear()
        self._data.update(deepcopy(source))
        if self._on_change:
            self._on_change()


class DeleteFieldCommand(Command):
    """Delete a single field (dict key) reversibly.

    execute() removes the key (remembering its value); undo() restores it.
    Used for optional-field deletion and whole-group deletion.
    """

    def __init__(
        self,
        data: dict,
        path: str,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._data = data
        self._path = path
        self._old: object = _NOT_FOUND
        self._on_change = on_change

    @property
    def description(self) -> str:
        return f"删除字段 {self._path}"

    def execute(self) -> None:
        self._old = _get_nested(self._data, self._path)
        if self._old is not _NOT_FOUND:
            _del_nested(self._data, self._path)
        if self._on_change:
            self._on_change()

    def undo(self) -> None:
        if self._old is not _NOT_FOUND:
            _set_nested(self._data, self._path, self._old)
        if self._on_change:
            self._on_change()


class ArrayInsertCommand(Command):
    """Insert an element into an array at specific index."""

    def __init__(
        self,
        data: dict,
        path: str,  # e.g. "weapons" (parent array path)
        index: int,
        element: dict,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._data = data
        self._path = path
        self._index = index
        self._element = element
        self._on_change = on_change

    @property
    def description(self) -> str:
        return f"添加 {self._path} 项"

    def execute(self) -> None:
        arr = _get_nested(self._data, self._path)
        if not isinstance(arr, list):
            return
        arr.insert(self._index, self._element)
        if self._on_change:
            self._on_change()

    def undo(self) -> None:
        arr = _get_nested(self._data, self._path)
        if not isinstance(arr, list):
            return
        del arr[self._index]
        if self._on_change:
            self._on_change()


class ArrayRemoveCommand(Command):
    """Remove an element from an array at specific index."""

    def __init__(
        self,
        data: dict,
        path: str,
        index: int,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._data = data
        self._path = path
        self._index = index
        self._removed: object = None
        self._on_change = on_change

    @property
    def description(self) -> str:
        return f"移除 {self._path} 项"

    def execute(self) -> None:
        arr = _get_nested(self._data, self._path)
        if not isinstance(arr, list):
            return
        self._removed = arr.pop(self._index)
        if self._on_change:
            self._on_change()

    def undo(self) -> None:
        arr = _get_nested(self._data, self._path)
        if not isinstance(arr, list):
            return
        arr.insert(self._index, self._removed)
        if self._on_change:
            self._on_change()


class ArrayMoveCommand(Command):
    """Move an element within an array from one index to another (reversible)."""

    def __init__(
        self,
        data: dict,
        path: str,
        from_index: int,
        to_index: int,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._data = data
        self._path = path
        self._from = from_index
        self._to = to_index
        self._on_change = on_change

    @property
    def description(self) -> str:
        return f"调整 {self._path} 顺序"

    def execute(self) -> None:
        arr = _get_nested(self._data, self._path)
        if not isinstance(arr, list):
            return
        if 0 <= self._from < len(arr) and 0 <= self._to < len(arr):
            elem = arr.pop(self._from)
            arr.insert(self._to, elem)
        if self._on_change:
            self._on_change()

    def undo(self) -> None:
        arr = _get_nested(self._data, self._path)
        if not isinstance(arr, list):
            return
        if 0 <= self._to < len(arr) and 0 <= self._from < len(arr):
            elem = arr.pop(self._to)
            arr.insert(self._from, elem)
        if self._on_change:
            self._on_change()


class CommandStack:
    """Manages command history for undo/redo."""

    def __init__(self, max_history: int = 200) -> None:
        self._history: list[Command] = []
        self._redo_stack: list[Command] = []
        self._max = max_history
        self._on_change: Callable[[], None] | None = None

    @property
    def can_undo(self) -> bool:
        return len(self._history) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def undo_description(self) -> str:
        """最近一条可撤销操作的描述（用于按钮 tooltip）。"""
        if self._history:
            return self._history[-1].description
        return ""

    @property
    def redo_description(self) -> str:
        """最近一条可重做操作的描述（用于按钮 tooltip）。"""
        if self._redo_stack:
            return self._redo_stack[-1].description
        return ""

    def set_on_change(self, callback: Callable[[], None]) -> None:
        self._on_change = callback

    def execute(self, cmd: Command) -> None:
        cmd.execute()

        # Try to merge with last command
        if self._history:
            merged = self._history[-1].merge_with(cmd)
            if merged is not None:
                self._history[-1] = merged
                self._redo_stack.clear()
                self._notify()
                return

        self._history.append(cmd)
        if len(self._history) > self._max:
            self._history.pop(0)
        self._redo_stack.clear()
        self._notify()

    def undo(self) -> None:
        if not self._history:
            return
        cmd = self._history[-1]
        cmd.undo()
        self._history.pop()
        self._redo_stack.append(cmd)
        self._notify()

    def redo(self) -> None:
        if not self._redo_stack:
            return
        cmd = self._redo_stack[-1]
        cmd.execute()
        self._redo_stack.pop()
        self._history.append(cmd)
        self._notify()

    def clear(self) -> None:
        self._history.clear()
        self._redo_stack.clear()

    def _notify(self) -> None:
        if self._on_change:
            self._on_change()


# ── nested dict helpers ─────────────────────────────────────────────────

_NOT_FOUND = object()  # sentinel: key did not exist in dict


def _get_nested(data: dict, path: str) -> object:
    """Get value at dotted path like 'weapons[0].bullet.damage'.

    Returns _NOT_FOUND if any key in the path does not exist.
    """
    keys = _parse_path(path)
    current: object = data
    for key in keys:
        try:
            if isinstance(key, int):
                current = current[key]  # type: ignore[index]
            else:
                current = current[key]  # type: ignore[index]
        except (KeyError, IndexError, TypeError):
            return _NOT_FOUND
    return current


def _set_nested(data: dict, path: str, value: object) -> None:
    keys = _parse_path(path)
    current: object = data
    for key in keys[:-1]:
        if isinstance(key, int):
            current = current[key]  # type: ignore[index]
        else:
            current = current[key]  # type: ignore[index]
    last = keys[-1]
    if isinstance(last, int):
        current[last] = value  # type: ignore[index]
    else:
        current[last] = value  # type: ignore[index]


def _del_nested(data: dict, path: str) -> None:
    """Delete a key at dotted path. Silently ignores missing keys."""
    keys = _parse_path(path)
    current: object = data
    for key in keys[:-1]:
        try:
            if isinstance(key, int):
                current = current[key]  # type: ignore[index]
            else:
                current = current[key]  # type: ignore[index]
        except (KeyError, IndexError, TypeError):
            return
    last = keys[-1]
    try:
        if isinstance(last, int):
            current.pop(last)  # type: ignore[index]
        else:
            current.pop(last, None)  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        pass


def _parse_path(path: str) -> list[str | int]:
    """Parse 'weapons[0].bullet.damage' into ['weapons', 0, 'bullet', 'damage']."""
    keys: list[str | int] = []
    for part in path.replace("[", ".").replace("]", "").split("."):
        if part.isdigit():
            keys.append(int(part))
        elif part:
            keys.append(part)
    return keys
