"""Command Pattern infrastructure for undo/redo.

Interface (3 methods on CommandStack):
    execute(cmd) / undo() / redo()

All data mutations in the editor go through CommandStack.execute().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable


class Command(ABC):
    """A reversible data mutation."""

    @abstractmethod
    def execute(self) -> None: ...

    @abstractmethod
    def undo(self) -> None: ...

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
        cmd = self._history.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        self._notify()

    def redo(self) -> None:
        if not self._redo_stack:
            return
        cmd = self._redo_stack.pop()
        cmd.execute()
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
