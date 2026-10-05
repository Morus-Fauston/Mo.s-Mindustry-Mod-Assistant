"""Narrow content-file operations; the desktop session owns open identities."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

from app.core.commands import CommandStack
from app.core.config_loader import get_block_categories
from app.core.content_commands import ContentChange, ContentFilesCommand, NewProjectCommand, file_bytes, local_path
from app.core.metadata import Metadata
from app.core.paths import metadata_dir
from app.core.project import ModInfo, Project
from app.core.template import TemplateEngine


class ContentActions:
    def __init__(self, project: Project, commands: CommandStack, *, metadata: Metadata | None = None, on_change=None):
        self.project, self.commands, self.on_change = project, commands, on_change
        self.templates = TemplateEngine(metadata or Metadata(metadata_dir()))
        self._trusted_files: dict[str, bytes | None] = {}

    def saved(self, path: str) -> None:
        """Acknowledge an actual successful session save, never a UI request.

        This is only the current trusted disk baseline, not a second history.
        Call immediately after save_content succeeds, including automatic saves.
        """
        value = file_bytes(self._content_path(path))
        if value is None:
            raise FileNotFoundError("保存结果文件不存在。")
        self._trusted_files[path] = value

    def _execute(self, before: dict, after: dict, change: ContentChange) -> None:
        self.commands.execute(ContentFilesCommand(self.project.root, before, after, change,
                                                  self.on_change, self._trusted_files))

    @staticmethod
    def _name(name: str) -> None:
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9-]+", name):
            raise ValueError("名称只能包含小写字母、数字、连字符。")
        if len(name) > 250 or re.fullmatch(r"(?:con|prn|aux|nul|com[0-9]|lpt[0-9])", name):
            raise ValueError("名称过长或为 Windows 保留名称。")

    def _content_path(self, relative: str):
        path = local_path(self.project.root, relative)
        parts = PurePosixPath(relative)
        if (len(parts.parts) != 3 or parts.parts[0] != "content"
                or parts.parts[1] not in ("units", "blocks", "weapons") or parts.suffix != ".json"):
            raise ValueError("请选择单位、方块或独立武器的内容文件。")
        return path

    @staticmethod
    def _encode(data: dict) -> bytes:
        return (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")

    @staticmethod
    def _data(value: bytes) -> dict:
        data = json.loads(value)
        if not isinstance(data, dict):
            raise ValueError("内容必须为 JSON 对象。")
        return data

    @classmethod
    def _data_or_none(cls, value: bytes | None) -> dict | None:
        if value is None:
            return None
        try:
            return cls._data(value)
        except (ValueError, UnicodeError):
            # Deleting/replacing a broken file must still keep its exact undo
            # bytes; there simply is no valid document to publish to the form.
            return None

    def catalogue(self) -> dict:
        units = [("UnitType", "地面单位（双足）"), ("UnitType-flying", "飞行单位"),
                 ("UnitType-tank", "坦克（履带）"), ("UnitType-legs", "多足单位（蜘蛛）")]
        blocks = []
        for group in get_block_categories().get("categories", []):
            for sub in group.get("subCategories", []):
                for kind in sub.get("types", []):
                    try:
                        self.templates.create(kind, "template-preview")
                    except ValueError:
                        continue
                    blocks.append({"kind": kind, "label": sub.get("name", kind), "group": group.get("name", "")})
        return {"namePattern": "[a-z0-9-]+", "nameHint": "名称只能包含小写字母、数字、连字符。",
                "categories": [
                    {"id": "units", "label": "单位", "templates": [{"kind": kind, "label": label} for kind, label in units]},
                    {"id": "blocks", "label": "方块", "templates": blocks},
                    {"id": "weapons", "label": "独立武器", "templates": [{"kind": "Weapon", "label": "武器"}]},
                ]}

    def create(self, kind: str, name: str, category: str, overwrite: bool = False) -> ContentChange:
        self._name(name)
        if type(overwrite) is not bool:
            raise ValueError("覆盖确认必须为布尔值。")
        allowed = {entry["id"]: {item["kind"] for item in entry["templates"]}
                   for entry in self.catalogue()["categories"]}
        if not isinstance(category, str) or category not in allowed or not isinstance(kind, str) or kind not in allowed[category]:
            raise ValueError("模板与内容类别不匹配。")
        relative = f"content/{category}/{name}.json"
        before = file_bytes(local_path(self.project.root, relative))
        if before is not None and not overwrite:
            raise FileExistsError("内容已存在，请确认覆盖所选类别内的文件。")
        data = self.templates.create(kind, name)
        value = self._encode(data)
        change = ContentChange("create", relative if before is not None else None, relative,
                               before_data=self._data_or_none(before), after_data=data)
        self._execute({relative: before}, {relative: value}, change)
        return change

    def rename(self, path: str, new_name: str) -> ContentChange:
        self._name(new_name)
        source = self._content_path(path)
        original = file_bytes(source)
        if original is None:
            raise FileNotFoundError("找不到需要重命名的内容。")
        target_name = str(PurePosixPath(path).with_name(new_name + ".json"))
        if target_name == path:
            return ContentChange("rename", path, path)
        target = self._content_path(target_name)
        if target.exists():
            raise FileExistsError("目标内容已存在，不能重命名。")
        previous = self._data(original)
        data = {**previous}
        if "name" in data:
            data["name"] = new_name
        before = {path: original, target_name: None}
        after = {path: None, target_name: self._encode(data)}
        category = PurePosixPath(path).parts[1]
        sprite_dir = local_path(self.project.root, f"sprites/{category}")
        moves = []
        if sprite_dir.is_dir():
            for sprite in sorted(sprite_dir.iterdir()):
                if sprite.suffix != ".png" or not (sprite.stem == source.stem or sprite.stem.startswith(source.stem + "-")):
                    continue
                old = sprite.relative_to(self.project.root.resolve()).as_posix()
                new = str(PurePosixPath(old).with_name(new_name + sprite.stem[len(source.stem):] + ".png"))
                # A prefix rename may map onto another source; reject it rather
                # than overwrite an existing layer or depend on move ordering.
                if local_path(self.project.root, new).exists():
                    raise FileExistsError("目标贴图已存在，不能重命名：" + new)
                before[old] = file_bytes(local_path(self.project.root, old))
                before[new] = None
                after[old] = None
                after[new] = before[old]
                moves.append((old, new))
        change = ContentChange("rename", path, target_name, tuple(moves), previous, data)
        self._execute(before, after, change)
        return change

    def delete(self, path: str) -> ContentChange:
        original = file_bytes(self._content_path(path))
        if original is None:
            raise FileNotFoundError("找不到需要删除的内容。")
        change = ContentChange("delete", path, None, before_data=self._data_or_none(original))
        self._execute({path: original}, {path: None}, change)
        return change

    def reveal_path(self, path: str):
        target = self._content_path(path)
        if file_bytes(target) is None:
            raise FileNotFoundError("需要定位的文件已不存在。")
        return target


def create_project(path: str | Path, mod_id: str, display_name: str, commands: CommandStack,
                   *, author: str = "", on_change=None) -> Project:
    """Create under a user-selected existing parent, using the session stack.

    The host chooses the directory; this entry accepts no shell or executable.
    on_change(project, undo) must attach/detach the project failure-atomically.
    """
    ContentActions._name(mod_id)
    if not isinstance(display_name, str) or not isinstance(author, str):
        raise ValueError("显示名称和作者必须为文本。")
    parent = Path(path).resolve()
    if not parent.is_dir():
        raise ValueError("请选择已存在的工程父目录。")
    target = local_path(parent, mod_id)
    project = Project(target, ModInfo(name=mod_id, display_name=display_name, author=author))
    commands.execute(NewProjectCommand(project, on_change))
    return project
