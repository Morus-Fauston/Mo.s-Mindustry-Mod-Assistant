"""外部 mod 参考导入（F-52）：解析 mod 文件夹 / zip 为只读参考数据。

数据生命周期：会话级（内存），不持久化。不修改外部文件、不复制精灵图、
不解析 Java mod（只读 JSON content）。

Interface:
    ExternalMod.load_from_folder(path) -> ExternalMod
    ExternalMod.load_from_zip(zip_path, tmp_dir) -> ExternalMod
    mod.contents -> dict[category, dict[name, data]]
      category 为 content 子目录名（units/blocks/weapons/items/liquids/...）

不 import Qt（core 层约束）。
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any


class ExternalMod:
    """一个外部 mod 的只读参考数据。"""

    def __init__(self, name: str, root: Path) -> None:
        self.name = name
        self.root = root
        self.contents: dict[str, dict[str, dict[str, Any]]] = {}
        self._scan()

    # ── 静态工厂 ────────────────────────────────────────────────────────

    @staticmethod
    def load_from_folder(path: str | Path) -> "ExternalMod":
        """从 mod 文件夹加载。要求目录含 mod.json 或 content/。"""
        root = Path(path)
        if not root.is_dir():
            raise ValueError(f"目录不存在: {root}")
        mod_json = root / "mod.json"
        name = root.name
        if mod_json.exists():
            try:
                data = json.loads(mod_json.read_text(encoding="utf-8"))
                name = data.get("name") or data.get("displayName") or name
            except (json.JSONDecodeError, OSError):
                pass
        return ExternalMod(name, root)

    @staticmethod
    def load_from_zip(zip_path: str | Path) -> "ExternalMod":
        """从 zip 导入：解压到临时目录，识别 mod 根（顶层或一层包裹）。

        返回的 ExternalMod 拥有临时目录；用完后调用 .cleanup() 删除。
        """
        zp = Path(zip_path)
        if not zp.exists():
            raise ValueError(f"zip 不存在: {zp}")
        tmp_dir = Path(tempfile.mkdtemp(prefix="moma_ext_"))
        with zipfile.ZipFile(zp) as zf:
            zf.extractall(tmp_dir)

        root = _find_mod_root(tmp_dir)
        if root is None:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise ValueError("zip 内未找到 mod 根（需要 mod.json 或 content/ 目录）")

        mod = ExternalMod.load_from_folder(root)
        mod._tmp_dir = tmp_dir  # type: ignore[attr-defined]
        return mod

    # ── 清理 ────────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        """删除 zip 导入产生的临时目录（会话结束/重新导入时调用）。"""
        tmp = getattr(self, "_tmp_dir", None)
        if tmp is not None:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)
            self._tmp_dir = None  # type: ignore[attr-defined]

    # ── 解析 ────────────────────────────────────────────────────────────

    def _scan(self) -> None:
        """扫描 content/**/*.json → {category: {name: data}}。"""
        content_dir = self.root / "content"
        if not content_dir.is_dir():
            return
        for cat_dir in sorted(p for p in content_dir.iterdir() if p.is_dir()):
            category = cat_dir.name
            entries: dict[str, dict[str, Any]] = {}
            for f in sorted(cat_dir.glob("*.json")):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                if not isinstance(data, dict):
                    continue
                entries[f.stem] = data
            if entries:
                self.contents[category] = entries

    def categories(self) -> list[str]:
        """该 mod 含 content 的分类目录名（units/blocks/weapons/...）。"""
        return sorted(self.contents.keys())

    def names(self, category: str) -> list[str]:
        """某分类下的 content 名列表。"""
        return sorted(self.contents.get(category, {}).keys())

    def get(self, category: str, name: str) -> dict[str, Any] | None:
        """按分类+名取 content 数据（只读，调用方不应修改）。"""
        return self.contents.get(category, {}).get(name)


def _find_mod_root(tmp_dir: Path) -> Path | None:
    """在解压目录中定位 mod 根：含 mod.json 或 content/ 的目录。

    支持两种布局：
      - zip 顶层即 mod 根（根下有 mod.json / content/）
      - zip 内一层目录包裹 mod 根（根/子目录/下有 mod.json）
    """
    if (tmp_dir / "mod.json").exists() or (tmp_dir / "content").is_dir():
        return tmp_dir
    # 一层包裹：tmp_dir 下只有一个子目录且其内含 mod 标记
    subs = [p for p in tmp_dir.iterdir() if p.is_dir()]
    if len(subs) == 1:
        sub = subs[0]
        if (sub / "mod.json").exists() or (sub / "content").is_dir():
            return sub
    return None
