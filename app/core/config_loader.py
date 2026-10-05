"""Centralized configuration loading for the MoMA editor.

All JSON config files in app/config/ are loaded through this module.
No Qt imports here — this is a core module.

Usage:
    from ..core.config_loader import get_config

    names_zh = get_config("field_names_zh")
    docs = get_config("field_docs")
    groups = get_config("field_groups")
"""

from __future__ import annotations

import json
import os
from contextlib import suppress
from pathlib import Path
import tempfile
from typing import Any

from .paths import data_dir

# 只读配置目录（F-53）：开发模式 = 项目 app/config；打包模式 = _MEIPASS/app/config
_CONFIG_DIR = data_dir() / "app" / "config"

# Module-level cache: loaded once per process lifetime.
_cache: dict[str, Any] = {}


def get_config(name: str) -> Any:
    """Load and cache a JSON config file by name (without .json extension).

    Returns an empty dict if the file does not exist or is invalid JSON.
    """
    if name in _cache:
        return _cache[name]

    path = _CONFIG_DIR / f"{name}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    _cache[name] = data
    return data


def reload_config(name: str) -> Any:
    """Force-reload a config file (bypasses cache)."""
    _cache.pop(name, None)
    return get_config(name)


def clear_cache() -> None:
    """Clear all cached configs. Useful for testing."""
    _cache.clear()


# ── Convenience accessors ────────────────────────────────────────────────


def get_field_names_zh() -> dict[str, str]:
    """Chinese field name translations: {english_name: chinese_name}."""
    return get_config("field_names_zh")


def get_field_docs() -> dict[str, str]:
    """Field tooltip documentation: {field_name: doc_string}."""
    return get_config("field_docs")


def get_field_groups() -> dict:
    """Field grouping configuration per content type."""
    return get_config("field_groups")


def get_field_dependencies() -> dict:
    """字段依赖规则：{内容类型: {从属字段: {前置字段: 条件}}}。"""
    return get_config("field_dependencies")


def get_vanilla_weapon_names_zh() -> dict[str, str]:
    """Vanilla weapon Chinese name translations."""
    return get_config("vanilla_weapon_names_zh")


def get_category_names_zh() -> dict[str, str]:
    """Instance category Chinese name translations."""
    return get_config("category_names_zh")


def get_block_categories() -> dict:
    """Block virtual grouping configuration for the file tree."""
    return get_config("block_categories")


def get_sprite_layers() -> dict:
    """Sprite layer definitions per content type for the preview panel."""
    return get_config("sprite_layers")


def get_content_names_zh() -> dict:
    """内容名总表（E-4 / ADR-013）：{category: {name: 中文名}}。

    类别键：items / liquids / blocks / units / weapons / status。
    """
    return get_config("content_names_zh")


# ── Editor state persistence ────────────────────────────────────────────


def load_editor_state() -> dict[str, Any]:
    """Load editor_state.json (bypasses cache — mutable file).

    F-53：打包模式写 %APPDATA%/MoMA/editor_state.json（用户级，可写）。
    Missing state is empty; unreadable or malformed state raises so a caller
    cannot accidentally replace an existing configuration with defaults.
    """
    from .paths import user_config_dir

    path = user_config_dir() / "editor_state.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict):
        raise ValueError("编辑器状态顶层必须是对象")
    json.dumps(data, allow_nan=False)
    return data


def save_editor_state(state: dict[str, Any]) -> None:
    """Merge editor state atomically; failures leave the existing file intact.

    Callers handle persistence errors separately from successful project work.
    Unknown keys remain in the existing user configuration format.
    """
    from .paths import ensure_user_config_dir

    if not isinstance(state, dict):
        raise ValueError("编辑器状态必须是对象")
    merged = {**load_editor_state(), **state}
    serialized = json.dumps(merged, ensure_ascii=False, indent=2, allow_nan=False)
    temporary = None
    try:
        d = ensure_user_config_dir()
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=d,
                                         prefix=".editor_state.json.", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, d / "editor_state.json")
    finally:
        if temporary is not None:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)


# ── Display name formatting ──────────────────────────────────────────────

# The four display name modes:
#   zh_en  → "中文 (english)"   (default)
#   en_zh  → "english (中文)"
#   zh     → "中文"
#   en     → "english"

_current_mode: str = "zh_en"


def set_display_mode(mode: str) -> None:
    """Set the global display name mode. One of: zh_en, en_zh, zh, en."""
    global _current_mode
    if mode in ("zh_en", "en_zh", "zh", "en"):
        _current_mode = mode


def get_display_mode() -> str:
    """Get the current display name mode."""
    return _current_mode


def display_name(field_name: str, names_zh: dict[str, str] | None = None) -> str:
    """Format a field name according to the current display mode.

    Args:
        field_name: The English field name (always used as fallback).
        names_zh: Optional pre-loaded zh names dict. If None, loads from config.
    """
    if names_zh is None:
        names_zh = get_field_names_zh()

    zh = names_zh.get(field_name)

    if _current_mode == "zh_en":
        return f"{zh} ({field_name})" if zh else field_name
    elif _current_mode == "en_zh":
        return f"{field_name} ({zh})" if zh else field_name
    elif _current_mode == "zh":
        return zh if zh else field_name
    else:  # "en"
        return field_name
