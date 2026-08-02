"""路径统一管理（F-53 / 规格 18.11）。

开发期与打包后使用不同的数据/配置根目录：

| 场景 | data_dir（只读：metadata/默认配置） | user_config_dir（可写） |
|------|--------------------------------------|-------------------------|
| 开发模式 | 项目根 | 项目根 / app / config |
| 打包模式 | sys._MEIPASS | %APPDATA% / MoMA |

注意：打包后用户可写设置不得写入 sys._MEIPASS（临时解压目录，会被清理）。
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """是否处于 PyInstaller 打包运行模式。"""
    return getattr(sys, "frozen", False)


def data_dir() -> Path:
    """只读数据根目录：metadata/、app/config/、app/resources/ 的父级。

    开发模式 = 项目根（app/ 的上一级）；打包模式 = sys._MEIPASS。
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).parent.parent.parent


def user_config_dir() -> Path:
    """可写用户配置目录：settings.json / editor_state.json。

    开发模式 = 项目 app/config（现状不变）；打包模式 = %APPDATA%/MoMA。
    """
    if is_frozen():
        return Path.home() / "AppData" / "Roaming" / "MoMA"
    return data_dir() / "app" / "config"


def ensure_user_config_dir() -> Path:
    """确保可写配置目录存在（打包后首次运行创建），返回该目录。"""
    d = user_config_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def metadata_dir() -> Path:
    """元数据目录（只读）。"""
    return data_dir() / "metadata"


def resources_dir() -> Path:
    """应用资源目录（QSS / 图标，只读）。"""
    return data_dir() / "app" / "resources"
