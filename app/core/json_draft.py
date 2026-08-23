"""Qt-free helpers for the editor's JSON output draft."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JsonParseResult:
    data: dict[str, Any] | None
    error: str | None


@dataclass(frozen=True)
class PathLocation:
    line: int | None
    is_exact: bool


def parse_json_object(source: str) -> JsonParseResult:
    """Parse a JSON object without ever mutating the caller's content data."""
    try:
        data = json.loads(source)
    except json.JSONDecodeError as exc:
        return JsonParseResult(None, f"第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}")
    if not isinstance(data, dict):
        return JsonParseResult(None, "JSON 顶层必须是对象")
    return JsonParseResult(data, None)


def format_json_draft(source: str) -> tuple[str, str | None]:
    """Format valid JSON while keeping invalid draft text exactly intact."""
    result = parse_json_object(source)
    if result.data is None:
        return source, result.error
    return json.dumps(result.data, ensure_ascii=False, indent=2) + "\n", None


def locate_path_line(source: str, path: str) -> PathLocation:
    """Find an exact JSON key line, falling back to the top-level key line."""
    result = parse_json_object(source)
    tokens = _parse_path(path)
    if result.data is None or not tokens:
        return PathLocation(None, False)

    locations: dict[tuple[str | int, ...], list[int]] = {}
    try:
        _JsonLocationParser(source, locations).parse()
    except ValueError:
        return PathLocation(None, False)

    exact_lines = locations.get(tuple(tokens), [])
    if len(exact_lines) == 1:
        return PathLocation(exact_lines[0], True)

    top_lines = locations.get((tokens[0],), [])
    if len(top_lines) == 1:
        return PathLocation(top_lines[0], False)
    return PathLocation(None, False)


def _parse_path(path: str) -> list[str | int]:
    tokens: list[str | int] = []
    for part in path.replace("[", ".").replace("]", "").split("."):
        if part.isdigit():
            tokens.append(int(part))
        elif part:
            tokens.append(part)
    return tokens


class _JsonLocationParser:
    """Small JSON tokenizer/parser that records object-key line positions."""

    def __init__(self, source: str, locations: dict[tuple[str | int, ...], list[int]]) -> None:
        self._source = source
        self._locations = locations
        self._index = 0

    def parse(self) -> None:
        self._parse_value(())
        self._skip_whitespace()
        if self._index != len(self._source):
            raise ValueError("trailing input")

    def _parse_value(self, path: tuple[str | int, ...]) -> None:
        self._skip_whitespace()
        if self._index >= len(self._source):
            raise ValueError("missing value")
        current = self._source[self._index]
        if current == "{":
            self._parse_object(path)
        elif current == "[":
            self._parse_array(path)
        elif current == '"':
            self._read_string()
        else:
            self._read_literal()

    def _parse_object(self, path: tuple[str | int, ...]) -> None:
        self._index += 1
        self._skip_whitespace()
        if self._consume("}"):
            return
        while True:
            self._skip_whitespace()
            line = self._line_number()
            key = self._read_string()
            key_path = path + (key,)
            self._locations.setdefault(key_path, []).append(line)
            self._skip_whitespace()
            self._expect(":")
            self._parse_value(key_path)
            self._skip_whitespace()
            if self._consume("}"):
                return
            self._expect(",")

    def _parse_array(self, path: tuple[str | int, ...]) -> None:
        self._index += 1
        self._skip_whitespace()
        if self._consume("]"):
            return
        item_index = 0
        while True:
            self._parse_value(path + (item_index,))
            item_index += 1
            self._skip_whitespace()
            if self._consume("]"):
                return
            self._expect(",")

    def _read_string(self) -> str:
        start = self._index
        self._expect('"')
        escaped = False
        while self._index < len(self._source):
            character = self._source[self._index]
            self._index += 1
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                return json.loads(self._source[start:self._index])
        raise ValueError("unterminated string")

    def _read_literal(self) -> None:
        start = self._index
        while self._index < len(self._source) and self._source[self._index] not in ",]} \t\r\n":
            self._index += 1
        if start == self._index:
            raise ValueError("invalid literal")

    def _skip_whitespace(self) -> None:
        while self._index < len(self._source) and self._source[self._index] in " \t\r\n":
            self._index += 1

    def _consume(self, token: str) -> bool:
        if self._index < len(self._source) and self._source[self._index] == token:
            self._index += 1
            return True
        return False

    def _expect(self, token: str) -> None:
        if not self._consume(token):
            raise ValueError(f"expected {token}")

    def _line_number(self) -> int:
        return self._source.count("\n", 0, self._index) + 1
