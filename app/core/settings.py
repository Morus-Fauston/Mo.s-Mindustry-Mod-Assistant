"""用户设置的读取与持久化（core 层，不 import Qt）。

默认值来自 app/config/settings_default.json；
用户修改持久化到 app/config/settings.json（与 editor_state.json 同目录）。

用法：
    from ..core.settings import get_settings
    settings = get_settings()
    theme = settings.get("theme")
    settings.set("theme", "dark")
    settings.save()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import data_dir, user_config_dir

# 只读默认配置（F-53）：开发 = 项目 app/config；打包 = _MEIPASS/app/config
_DEFAULT_FILE = data_dir() / "app" / "config" / "settings_default.json"
# 可写用户配置：开发 = 项目 app/config；打包 = %APPDATA%/MoMA
_USER_FILE = user_config_dir() / "settings.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError, UnicodeError, RecursionError):
        return {}


class Settings:
    """合并默认值与用户设置，支持读取、修改、持久化。"""

    def __init__(self) -> None:
        self._defaults = _load_json(_DEFAULT_FILE)
        self._values: dict[str, Any] = dict(self._defaults)
        # 用户设置覆盖默认值
        self._values.update(_load_json(_USER_FILE))

    def get(self, key: str, default: Any = None) -> Any:
        """读取设置项，未定义时返回 default。"""
        return self._values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """写入设置项（仅改内存，需调用 save() 持久化）。"""
        self._values[key] = value

    def save(self) -> None:
        """把与默认值不同的设置项持久化到 settings.json。"""
        # 只保存被修改过的项，保持文件精简
        diff = {
            k: v for k, v in self._values.items()
            if self._defaults.get(k) != v
        }
        try:
            from .paths import ensure_user_config_dir

            ensure_user_config_dir()
            _USER_FILE.write_text(
                json.dumps(diff, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def as_dict(self) -> dict[str, Any]:
        return dict(self._values)


# 进程级单例
_instance: Settings | None = None


def get_settings() -> Settings:
    """返回进程级 Settings 单例。"""
    global _instance
    if _instance is None:
        _instance = Settings()
    return _instance


def reset_settings() -> None:
    """重置单例（主要用于测试）。"""
    global _instance
    _instance = None
