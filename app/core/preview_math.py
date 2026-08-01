"""预览渲染的纯数学层——坐标映射 / 武器叠加 / 引擎圆几何。

本模块不 import Qt。输入 content 数据 + 精灵图尺寸，输出每个图层的
位置/层级/翻转描述（dataclass），由 UI 层翻译成 QGraphicsItem。

这样坐标公式（PPU=4、y 翻转、mirror、引擎内圈偏移）可以脱离 Qt 用
pytest 直接验证——ADR-003 要求"渲染公式必须带源码引用、可提取"，本模块
即该要求的落地。阶段二动画管线（Time.time 参数）也将以此为落点。

坐标系约定：
- Mindustry：x 右正、y 上正，原点在精灵中心
- Qt 场景：x 右正、y 下正
- 换算：scene_x = cx + wx*PPU；scene_y = cy - wy*PPU
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 坐标缩放比：4 像素 = 1 世界单位（003 调研结论）
PPU = 4


@dataclass
class LayerSpec:
    """一个精灵图层的渲染描述（UI 层据此 addPixmap）。"""

    key: str            # 场景元素标识（""=主体, "-cell", "__weapon_0__" ...）
    x: float            # 左上角 scene x（已减去半宽）
    y: float            # 左上角 scene y（已减去半高）
    z: int              # zValue
    flip_x: bool = False  # 水平翻转（武器 mirror 的镜像份）
    tooltip: str = ""


@dataclass
class CircleSpec:
    """一个实心圆的渲染描述（UI 层据此 addEllipse）。"""

    key: str
    cx: float           # 圆心 scene x
    cy: float           # 圆心 scene y
    radius: float
    z: int
    color_hex: str      # "#rrggbb"
    tooltip: str = ""


@dataclass
class SceneSpec:
    """整张预览场景的纯数据描述。"""

    width: float = 0.0
    height: float = 0.0
    pixmaps: list[LayerSpec] = field(default_factory=list)
    circles: list[CircleSpec] = field(default_factory=list)


def weapon_xy(w: dict, ref_defaults: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float]:
    """解析武器 x/y：条目内有覆盖用覆盖，否则回退被引用武器默认值。

    ref_defaults = 被引用武器 JSON 的 (x, y)，由调用方从 ContentStore 读取。
    """
    wx = w.get("x")
    wy = w.get("y")
    if wx is None:
        wx = ref_defaults[0]
    if wy is None:
        wy = ref_defaults[1]
    return float(wx), float(wy)


def compute_weapon_layers(
    weapons: list,
    center: tuple[float, float],
    sprite_size: callable,
    resolve_xy: callable | None = None,
) -> list[LayerSpec]:
    """计算武器叠加图层（含 mirror 镜像份）。

    参数：
        weapons      — content["weapons"] 数组
        center       — 主体精灵中心 (cx, cy)，单位像素
        sprite_size  — callable(name) -> (w, h) | None，武器精灵尺寸；None=无图跳过
        resolve_xy   — callable(w, name) -> (wx, wy)，可选；默认用 weapon_xy 无回退
    """
    cx, cy = center
    specs: list[LayerSpec] = []
    for i, w in enumerate(weapons):
        if not isinstance(w, dict):
            continue
        name = w.get("name", "")
        if not name:
            continue
        size = sprite_size(name)
        if size is None:
            continue
        ww, wh = size
        if resolve_xy is not None:
            wx, wy = resolve_xy(w, name)
        else:
            wx, wy = weapon_xy(w)
        mirror = bool(w.get("mirror", False))

        w_cx, w_cy = ww / 2.0, wh / 2.0
        key = f"__weapon_{i}__"
        specs.append(LayerSpec(
            key=key,
            x=cx + wx * PPU - w_cx,
            y=cy - wy * PPU - w_cy,
            z=10,
            tooltip=f"武器: {name}  ({wx}, {wy})",
        ))
        if mirror:
            specs.append(LayerSpec(
                key=key,
                x=cx - wx * PPU - w_cx,
                y=cy - wy * PPU - w_cy,
                z=10,
                flip_x=True,
                tooltip=f"武器: {name}  ({-wx}, {wy}) (镜像)",
            ))
    return specs


# 引擎默认占位色（engineColor 未设置时 = 默认队伍色亮黄/橙）
_ENGINE_OUTER_DEFAULT = "#ffc832"
_ENGINE_INNER_DEFAULT = "#ffffff"


def _normalize_hex(value: str | None, default: str) -> str:
    if not value:
        return default
    return value if value.startswith("#") else f"#{value}"


def compute_engine_circles(
    data: dict,
    center: tuple[float, float],
) -> list[CircleSpec]:
    """计算引擎双实心圆（外圈 engineColor + 内圈 engineColorInner）。

    默认 z 在主体下（-1）；engineLayer>0 时提升到主体上（11）。
    内圈半径=外圈/2，沿默认 rotation(-90°) 偏移 rad/4 形成喷口感。
    """
    import math

    engine_size = float(data.get("engineSize", 0))
    if engine_size <= 0:
        return []
    engine_offset = float(data.get("engineOffset", 0))
    cx, cy = center

    ex = cx
    ey = cy + engine_offset * PPU  # y 取反：精灵上向下
    radius = engine_size * PPU

    engine_layer = float(data.get("engineLayer", -1))
    z = 11 if engine_layer > 0 else -1

    outer_color = _normalize_hex(data.get("engineColor"), _ENGINE_OUTER_DEFAULT)
    inner_color = _normalize_hex(data.get("engineColorInner"), _ENGINE_INNER_DEFAULT)

    circles = [CircleSpec(
        key="__engine__",
        cx=ex, cy=ey, radius=radius, z=z, color_hex=outer_color,
        tooltip=f"引擎外圈 (大小={engine_size}, 偏移={engine_offset})",
    )]

    inner_radius = radius / 2.0
    rot_rad = math.radians(-90.0)  # 默认引擎 rotation
    inner_offset = radius / 4.0
    circles.append(CircleSpec(
        key="__engine__",
        cx=ex - math.cos(rot_rad) * inner_offset,
        cy=ey - math.sin(rot_rad) * inner_offset,
        radius=inner_radius, z=z, color_hex=inner_color,
        tooltip="引擎内圈",
    ))
    return circles
