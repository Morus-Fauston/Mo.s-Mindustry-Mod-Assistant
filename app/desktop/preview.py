"""Qt-free static scene assembly and session-scoped, decoded PNG resources."""

from __future__ import annotations

import base64
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from hashlib import sha256
import math
import os
import re
import warnings

from PIL import Image, UnidentifiedImageError

from app.core.content_store import ContentData
from app.core.config_loader import get_sprite_layers
from app.core.metadata import normalize_content_type
from app.core.preview_math import compute_engine_circles, compute_weapon_layers, weapon_xy
from app.core.project import Project


def _preview_name(value: str) -> str:
    if (not isinstance(value, str) or not value or len(value) > 255 or value in ('.', '..')
            or re.search(r'[\\/:\x00-\x1f<>"|?*]', value)):
        raise ValueError('素材名称无效')
    return value


class WeaponPreviewResolver:
    """One read-only name/coordinate policy for scene drawing and layer rows."""

    MAX_SOURCE_BYTES = 16 * 1024 * 1024

    def __init__(self, project: Project):
        self.project = project

    def local_name(self, name: str) -> str:
        name = _preview_name(name)
        prefix = self.project.mod_info.name + '-'
        return _preview_name(name[len(prefix):] if name.startswith(prefix) else name)

    def sprite_names(self, name: str) -> tuple[str, ...]:
        local = self.local_name(name)
        return tuple(dict.fromkeys((name, local)))

    @staticmethod
    def number(value: object) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError('预览坐标必须是有限数字') from exc
        if not math.isfinite(number) or abs(number) > 1_000_000:
            raise ValueError('预览坐标超出支持范围')
        return number

    def coordinates(self, weapon: dict) -> tuple[float, float]:
        local = self.local_name(weapon.get('name'))
        defaults = (0, 0)
        if weapon.get('x') is None or weapon.get('y') is None:
            root = self.project.root.resolve()
            path = root / 'content' / 'weapons' / f'{local}.json'
            if not path.resolve().is_relative_to(root / 'content' / 'weapons'):
                raise ValueError('引用武器文件超出预览读取范围')
            if path.exists():
                if not path.is_file() or path.stat().st_size > self.MAX_SOURCE_BYTES:
                    raise ValueError('引用武器文件超出预览读取范围')
                reference = self.project.contents.get_by_path(f'weapons/{local}.json').data
                defaults = (reference.get('x', 0), reference.get('y', 0))
        coordinates = weapon_xy(weapon, defaults)
        return self.number(coordinates[0]), self.number(coordinates[1])


class PreviewService:
    """Resources belong to the latest scene in this project/session only."""

    MAX_FILE_BYTES = 16 * 1024 * 1024
    MAX_PIXELS = 8 * 1024 * 1024
    MAX_DIMENSION = 8192
    MAX_OUTPUT_BYTES = 16 * 1024 * 1024
    MAX_CACHE_BYTES = 64 * 1024 * 1024
    MAX_SCENE_PIXELS = 16 * 1024 * 1024
    MAX_RESOURCES = 128
    MAX_WEAPONS = 128
    MAX_SEARCH_ENTRIES = 10000

    def __init__(self, project: Project, session_id: str):
        self._project = project
        self._root = project.root.resolve()
        self._session_id = session_id
        self._resources: dict[str, dict] = {}
        self._paths: dict[Path, str] = {}
        self._cache_bytes = 0
        self._scene_pixels = 0
        self._weapons_resolver = WeaponPreviewResolver(project)

    @staticmethod
    def _name(value: str) -> str:
        return _preview_name(value)

    def _safe_path(self, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(self._root) or not resolved.is_relative_to((self._root / "sprites").resolve()):
            raise ValueError("素材路径超出当前工程")
        if path.suffix.lower() != ".png" or not resolved.is_file():
            raise ValueError("素材必须是当前工程中的 PNG 文件")
        return resolved

    def register_resource(self, path: Path) -> dict:
        """Add a dynamic frame to this scene's existing bounded registry."""
        return self._load(path)

    def _load(self, path: Path) -> dict:
        path = self._safe_path(path)
        if path in self._paths:
            return self._resources[self._paths[path]]
        if len(self._resources) >= self.MAX_RESOURCES:
            raise ValueError("预览素材数量超出本次场景上限")
        with path.open("rb") as stream:
            raw = stream.read(self.MAX_FILE_BYTES + 1)
        if len(raw) > self.MAX_FILE_BYTES:
            raise ValueError("PNG 文件过大，无法预览")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(raw)) as image:
                    if image.format != "PNG":
                        raise ValueError("素材不是有效 PNG 图片")
                    width, height = image.size
                    if max(width, height) > self.MAX_DIMENSION or width * height > self.MAX_PIXELS:
                        raise ValueError("PNG 解码尺寸过大，无法预览")
                    if self._scene_pixels + width * height > self.MAX_SCENE_PIXELS:
                        raise ValueError("场景累计解码像素已达上限，部分贴图无法预览")
                    image.verify()
                with Image.open(BytesIO(raw)) as image:
                    rgba = image.convert("RGBA")
                    output = BytesIO()
                    rgba.save(output, format="PNG")
                    encoded = output.getvalue()
        except (UnidentifiedImageError, OSError, SyntaxError, EOFError,
                Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ValueError("PNG 文件损坏，无法预览") from exc
        if len(encoded) > self.MAX_OUTPUT_BYTES:
            raise ValueError("PNG 预览数据过大")
        data_url = "data:image/png;base64," + base64.b64encode(encoded).decode("ascii")
        if self._cache_bytes + len(data_url) > self.MAX_CACHE_BYTES:
            raise ValueError("预览资源缓存已达上限")
        resource_id = sha256(self._session_id.encode("utf-8") + str(path).encode("utf-8") + encoded).hexdigest()
        resource = {"sessionId": self._session_id, "resourceId": resource_id,
                    "mime": "image/png", "dataUrl": data_url, "width": width, "height": height}
        self._resources[resource_id] = resource
        self._paths[path] = resource_id
        self._cache_bytes += len(data_url)
        self._scene_pixels += width * height
        return resource

    def resource(self, resource_id: str) -> dict:
        if not isinstance(resource_id, str) or len(resource_id) > 128 or resource_id not in self._resources:
            raise ValueError("预览资源已失效或不属于当前会话，请刷新预览")
        return deepcopy(self._resources[resource_id])

    def scene(self, content: ContentData) -> dict:
        self._resources.clear()
        self._paths.clear()
        self._cache_bytes = 0
        self._scene_pixels = 0
        scene = {"sessionId": self._session_id, "width": 0, "height": 0,
                 "layers": [], "circles": [], "warnings": [], "status": "empty"}
        if not isinstance(content, ContentData) or not isinstance(content.data, dict):
            raise ValueError("预览内容无效")
        if content.category not in ("units", "blocks", "weapons"):
            raise ValueError("不支持此内容分类的预览")
        self._name(content.name)
        expected = self._root / "content" / content.category / f"{content.name}.json"
        if not expected.resolve().is_relative_to(self._root) or (content.path is not None and content.path.resolve() != expected.resolve()):
            raise ValueError("预览内容不属于当前工程")
        try:
            main = self._load(self._project.sprite_path(content.category, content.name))
        except (ValueError, OSError) as exc:
            scene.update(status="missing", warnings=[f"主体贴图：{exc}"])
            return scene
        scene.update(width=main["width"], height=main["height"], status="ready")
        scene["layers"].append(self._layer("", main, 0, 0, 0, "主体"))
        center = (main["width"] / 2, main["height"] / 2)
        self._overlays(content, scene, center)
        self._weapons(content, scene, center)
        self._engine(content, scene, center)
        if scene["warnings"]:
            scene["status"] = "missing"
        return scene

    def _overlays(self, content: ContentData, scene: dict, center: tuple[float, float]) -> None:
        subtype = content.data.get("type", "")
        kind = normalize_content_type(subtype) if isinstance(subtype, str) else ""
        configuration = get_sprite_layers().get(kind, [])
        z = 1
        for layer in configuration:
            suffix = layer.get("suffix", "")
            if not suffix or (layer.get("visible_for") and subtype not in layer["visible_for"]):
                continue
            path = self._project.sprite_path(content.category, content.name, suffix)
            if not path.exists() and not layer.get("required", False):
                continue
            try:
                resource = self._load(path)
            except (OSError, ValueError) as exc:
                scene["warnings"].append(f"{layer.get('label', suffix)}：{exc}")
                continue
            level = -3 if suffix == "-shadow" else -2 if suffix == "-outline" else z
            if level >= 0:
                z += 1
            scene["layers"].append(self._layer(suffix, resource, center[0] - resource["width"] / 2,
                center[1] - resource["height"] / 2, level, layer.get("label", suffix)))

    def _weapon_resource(self, name: str, category: str) -> dict:
        names = self._weapons_resolver.sprite_names(name)
        for source_category in dict.fromkeys(('weapons', category)):
            for candidate in names:
                path = self._project.sprite_path(source_category, candidate)
                if path.exists():
                    return self._load(path)
        sprites = self._project.sprites_dir
        if not sprites.resolve().is_relative_to(self._root):
            raise ValueError("贴图目录超出工程范围")
        count = 0
        for directory, folders, files in os.walk(sprites, followlinks=False):
            count += len(folders) + len(files)
            if count > self.MAX_SEARCH_ENTRIES:
                raise ValueError("贴图检索数量超出上限，请将武器贴图放入武器目录")
            folders[:] = sorted(folder for folder in folders
                                if (Path(directory) / folder).resolve().is_relative_to(self._root))
            for candidate in names:
                if f"{candidate}.png" in files:
                    return self._load(Path(directory) / f"{candidate}.png")
        raise ValueError("缺少武器 PNG 贴图")

    @staticmethod
    def _number(value: object) -> float:
        return WeaponPreviewResolver.number(value)

    def _weapon_xy(self, weapon: dict, name: str) -> tuple[float, float]:
        return self._weapons_resolver.coordinates(weapon)

    def _weapons(self, content: ContentData, scene: dict, center: tuple[float, float]) -> None:
        weapons = content.data.get("weapons", [])
        if not isinstance(weapons, list):
            scene["warnings"].append("武器资料不是数组，无法绘制武器")
            return
        if len(weapons) > self.MAX_WEAPONS:
            scene["warnings"].append("武器数量超过预览上限，部分武器未显示")
        for index, weapon in enumerate(weapons[:self.MAX_WEAPONS]):
            if not isinstance(weapon, dict) or not weapon.get("name"):
                continue
            name = weapon["name"]
            try:
                resource = self._weapon_resource(name, content.category)
                specs = compute_weapon_layers([weapon], center, lambda _: (resource["width"], resource["height"]), self._weapon_xy)
            except (OSError, ValueError, TypeError, OverflowError) as exc:
                scene["warnings"].append(f"武器 {index + 1}：{exc}")
                continue
            for spec in specs:
                scene["layers"].append(self._layer(f"__weapon_{index}__", resource, spec.x, spec.y, spec.z, spec.tooltip, spec.flip_x))

    def _engine(self, content: ContentData, scene: dict, center: tuple[float, float]) -> None:
        try:
            data = {key: self._number(content.data.get(key, default))
                    for key, default in (("engineSize", 0), ("engineOffset", 0), ("engineLayer", -1))}
            for key in ("engineColor", "engineColorInner"):
                color = content.data.get(key)
                if color:
                    if not isinstance(color, str) or not re.fullmatch(r"#?(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", color):
                        raise ValueError("引擎颜色必须是十六进制颜色")
                    data[key] = color
            circles = compute_engine_circles(data, center)
            # Preserve preview_panel._draw_engine static output. Its inner Y is
            # ey + sin(-90) * radius / 4, unlike preview_math's existing sign.
            if len(circles) == 2:
                circles[1].cy = circles[0].cy - circles[0].radius / 4
            for circle in circles:
                scene["circles"].append({"key": circle.key, "cx": circle.cx, "cy": circle.cy,
                    "radius": circle.radius, "z": circle.z, "color": circle.color_hex, "tooltip": circle.tooltip})
        except (ValueError, TypeError, OverflowError) as exc:
            scene["warnings"].append(f"引擎：{exc}")

    @staticmethod
    def _layer(key: str, resource: dict, x: float, y: float, z: int, tooltip: str, flip_x: bool = False) -> dict:
        return {"key": key, "resourceId": resource["resourceId"], "x": x, "y": y, "z": z,
                "width": resource["width"], "height": resource["height"], "flipX": flip_x, "tooltip": tooltip}
