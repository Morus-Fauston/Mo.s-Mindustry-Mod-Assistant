"""Existing sprite naming and bounded PNG import over the session command stack.

Source paths are supplied by the native picker, never accepted from browser IPC.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Callable
import warnings
from weakref import WeakSet

from PIL import Image, UnidentifiedImageError

from app.core.commands import Command, CommandStack
from app.core.content_store import ContentData
from app.core.config_loader import get_sprite_layers
from app.core.metadata import normalize_content_type
from app.core.project import Project
from app.core.resource_commands import ResourceCommand


class ResourceService:
    MAX_FILE_BYTES = 16 * 1024 * 1024
    MAX_PIXELS = 8 * 1024 * 1024
    MAX_DIMENSION = 8192
    MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024

    def __init__(self, project: Project, commands: CommandStack,
                 on_change: Callable[[], None] | None = None,
                 content_resolver: Callable[[str], ContentData] | None = None):
        self._project, self._commands = project, commands
        self._root = project.root.resolve()
        self._on_change = on_change
        self._content_resolver = content_resolver
        self._snapshots: WeakSet[Command] = WeakSet()

    def _content(self, path: str):
        if (not isinstance(path, str) or len(path) > 4096 or not path.startswith("content/")
                or "\\" in path or ":" in path or "\x00" in path
                or PurePosixPath(path).as_posix() != path
                or len(PurePosixPath(path).parts) != 3 or ".." in PurePosixPath(path).parts
                or PurePosixPath(path).suffix != ".json"):
            raise ValueError("内容路径必须是工程内规范路径")
        if not (self._root / path).resolve().is_relative_to(self._root):
            raise ValueError("内容路径超出当前工程")
        content = (self._content_resolver(path) if self._content_resolver
                   else self._project.contents.get_by_path(path[len("content/"):]))
        if (not isinstance(content, ContentData) or not isinstance(content.data, dict)
                or path != f"content/{content.category}/{content.name}.json"
                or content.path is None or content.path.resolve() != (self._root / path).resolve()):
            raise ValueError("内容不属于当前工程")
        if content.category not in ("units", "blocks", "weapons"):
            raise ValueError("此内容分类不支持贴图操作")
        if any(c in content.name for c in '<>"|?*') or content.name.endswith((".", " ")):
            raise ValueError("贴图名称无效")
        return content

    def _validate_target(self, target: Path) -> None:
        sprites = self._root / "sprites"
        if (not sprites.resolve().is_relative_to(self._root)
                or target.resolve() != target or not target.is_relative_to(sprites)):
            raise ValueError("贴图路径已变化或超出当前工程")
        if target.exists() and not target.is_file():
            raise ValueError("贴图目标不是文件")

    def targets(self, path: str) -> list[dict]:
        content = self._content(path)
        subtype = content.data.get("type", "UnitType" if content.category == "units" else "Weapon" if content.category == "weapons" else "Block")
        kind = normalize_content_type(subtype) if isinstance(subtype, str) else ""
        layers = get_sprite_layers().get(kind, [{"suffix": "", "label": "主体"}])
        result = []
        for layer in layers:
            if layer.get("visible_for") and subtype not in layer["visible_for"]:
                continue
            target = self._root / "sprites" / content.category / f"{content.name}{layer['suffix']}.png"
            self._validate_target(target)
            result.append({"suffix": layer["suffix"], "label": layer["label"],
                           "path": target.relative_to(self._root).as_posix(), "exists": target.exists()})
        return result

    def _target(self, path: str, suffix: str) -> Path:
        for target in self.targets(path):
            if target["suffix"] == suffix:
                return self._root / target["path"]
        raise ValueError("不支持此内容类型的贴图后缀")

    def _read(self, path: Path) -> bytes:
        with path.open("rb") as stream:
            raw = stream.read(self.MAX_FILE_BYTES + 1)
        if len(raw) > self.MAX_FILE_BYTES:
            raise ValueError("PNG 文件超出资源大小上限")
        return raw

    def _png(self, raw: bytes) -> tuple[int, int]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(raw)) as image:
                    if image.format != "PNG":
                        raise ValueError("素材必须是真实 PNG 图片")
                    width, height = image.size
                    if max(width, height) > self.MAX_DIMENSION or width * height > self.MAX_PIXELS:
                        raise ValueError("PNG 解码尺寸超出资源上限")
                    image.verify()
                with Image.open(BytesIO(raw)) as image:
                    image.load()
            return width, height
        except (UnidentifiedImageError, OSError, SyntaxError, EOFError,
                Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ValueError("PNG 文件损坏，未修改原贴图") from exc

    def _execute(self, target: Path, before: bytes | None, after: bytes | None) -> None:
        command = ResourceCommand(target, before, after, lambda: self._validate_target(target), self._on_change)
        self.execute_resource_command(command)

    def execute_resource_command(self, command: Command) -> None:
        """Trusted application commands share the import/delete history budget."""
        size = getattr(command, "snapshot_bytes", None)
        if not isinstance(command, Command) or type(size) is not int or size < 0:
            raise ValueError("资源命令快照无效")
        if sum(item.snapshot_bytes for item in self._snapshots) + size > self.MAX_SNAPSHOT_BYTES:
            raise ValueError("会话贴图撤销快照已达上限，请保存后重新打开工程")
        self._commands.execute(command)
        self._snapshots.add(command)

    def import_sprite(self, path: str, source_path: str | Path, suffix: str = "", *, overwrite: bool = False) -> dict:
        target = self._target(path, suffix)
        if type(overwrite) is not bool:
            raise ValueError("覆盖确认无效")
        if target.exists() and not overwrite:
            raise FileExistsError("贴图已存在，需确认后替换")
        source = Path(source_path)
        if source.suffix.lower() != ".png":
            raise ValueError("请选择 PNG 文件")
        after = self._read(source)
        width, height = self._png(after)
        before = self._read(target) if target.exists() else None
        if before != after:
            self._execute(target, before, after)
        return {"path": target.relative_to(self._root).as_posix(), "width": width, "height": height, "exists": True}

    def delete_sprite(self, path: str, suffix: str = "", *, confirmed: bool = False) -> dict:
        target = self._target(path, suffix)
        if confirmed is not True:
            raise ValueError("删除贴图需要确认")
        if not target.exists():
            raise FileNotFoundError("贴图不存在，请刷新后重试")
        before = self._read(target)
        self._execute(target, before, None)
        return {"path": target.relative_to(self._root).as_posix(), "exists": False}
