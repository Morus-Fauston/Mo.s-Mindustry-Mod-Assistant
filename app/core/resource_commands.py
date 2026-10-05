"""Reversible, atomic resource bytes; no GUI or second history."""

from __future__ import annotations

import os
import logging
from pathlib import Path
import tempfile
from typing import Callable

from app.core.commands import Command


class ResourceCommand(Command):
    """Keep before/after bytes until the session command stack releases them."""

    def __init__(self, target: Path, before: bytes | None, after: bytes | None,
                 validate: Callable[[], None], on_change: Callable[[], None] | None = None):
        self.target = target
        self._before, self._after = before, after
        self._validate, self._on_change = validate, on_change

    @property
    def snapshot_bytes(self) -> int:
        return len(self._before or b"") + len(self._after or b"")

    @property
    def description(self) -> str:
        action = "删除" if self._after is None else "导入" if self._before is None else "替换"
        return f"{action}贴图 {self.target.name}"

    def execute(self) -> None:
        self._write(self._before, self._after)

    def undo(self) -> None:
        self._write(self._after, self._before)

    def _check_expected(self, expected: bytes | None) -> None:
        self._validate()
        if self.target.exists():
            with self.target.open("rb") as stream:
                current = stream.read(len(expected or b"") + 1)
        else:
            current = None
        if current != expected:
            raise ValueError("贴图已被外部修改，请刷新后处理；本次操作未写入")

    def _write(self, expected: bytes | None, replacement: bytes | None) -> None:
        self._check_expected(expected)
        if replacement is None:
            self.target.unlink()
        else:
            self.target.parent.mkdir(parents=True, exist_ok=True)
            fd, filename = tempfile.mkstemp(prefix=f".{self.target.stem}_", suffix=".tmp", dir=self.target.parent)
            temporary = Path(filename)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(replacement)
                    stream.flush()
                    os.fsync(stream.fileno())
                self._check_expected(expected)
                os.replace(temporary, self.target)
            finally:
                temporary.unlink(missing_ok=True)
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                # A notification failure cannot turn a committed disk mutation
                # into an unrecorded command. The bridge refreshes authoritative
                # state after every successful mutation and history operation.
                logging.getLogger(__name__).exception("贴图已更新，刷新通知失败")
