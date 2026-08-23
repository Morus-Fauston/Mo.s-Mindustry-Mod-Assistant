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
import math

# 坐标缩放比：4 像素 = 1 世界单位（003 调研结论）
PPU = 4


# 动态预览只需要稳定、可辨识的队伍色。键名同时作为 UI 离散选项，避免 UI
# 层维护另一份颜色表。默认值保留现有引擎占位色，其他值对应 Mindustry 常见队伍。
TEAM_COLORS = {
    "默认": "#ffc832",
    "废弃": "#898989",
    "碎片": "#4d6bf3",
    "红队": "#e82d2d",
    "紫队": "#a958d5",
    "绿队": "#4ac44a",
    "蓝队": "#50a9ee",
    "橙队": "#f4a958",
    "黄队": "#f3e979",
    "青队": "#46cdbd",
    "粉队": "#f26aa0",
    "棕队": "#a06a42",
}

HEALTH_LEVELS = {
    "满血": 1.0,
    "半血": 0.5,
    "残血": 0.15,
}

_DIRECTION_DEGREES = {
    "右": 0.0,
    "上": -90.0,
    "左": 180.0,
    "下": 90.0,
}


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


@dataclass
class PreviewAnimationState:
    """Pure, resettable state for the first dynamic-preview effects."""

    time_tick: float = 0.0
    recoil: float = 0.0
    heat: float = 0.0
    muzzle_flash_ticks: float = 0.0
    tread_time: float = 0.0

    def fire(self) -> None:
        self.recoil = 1.0
        self.heat = 1.0
        self.muzzle_flash_ticks = 3.0

    def advance(
        self,
        delta_tick: float,
        *,
        recoil_time: float = 10.0,
        cooldown_time: float = 20.0,
        moving: bool = False,
    ) -> None:
        delta = max(0.0, min(float(delta_tick), 3.0))
        self.time_tick += delta
        self.recoil = max(0.0, self.recoil - delta / max(recoil_time, 1.0))
        self.heat = max(0.0, self.heat - delta / max(cooldown_time, 1.0))
        self.muzzle_flash_ticks = max(0.0, self.muzzle_flash_ticks - delta)
        if moving:
            self.tread_time += delta

    def pulse(self, period: float = 2.0) -> float:
        return abs(math.sin(math.pi * self.time_tick / max(period, 0.001)))

    def tread_frame(self, frames: int) -> int:
        return int(self.tread_time) % max(int(frames), 1)

    def recoil_offset(self, distance: float = 1.0, power: float = 1.8) -> float:
        """Return the signed Mindustry recoil offset for the current state."""
        return -(max(self.recoil, 0.0) ** max(float(power), 0.0)) * float(distance)

    def muzzle_flash_opacity(self) -> float:
        """Map the three-tick demo flash lifetime to a Qt opacity."""
        return max(0.0, min(self.muzzle_flash_ticks / 3.0, 1.0))


def team_color_hex(team: str) -> str:
    """Return a known team color, falling back to the default preview color."""
    return TEAM_COLORS.get(team, TEAM_COLORS["默认"])


def health_fraction(level: str) -> float:
    """Return the discrete health fraction used by dynamic cell rendering."""
    return HEALTH_LEVELS.get(level, HEALTH_LEVELS["满血"])


def direction_degrees(direction: str) -> float:
    """Map the four supported directions to a scene rotation in degrees."""
    return _DIRECTION_DEGREES.get(direction, _DIRECTION_DEGREES["右"])


def cell_color_hex(team: str, health: str, time_tick: float) -> str:
    """Approximate UnitType.cellColor with health-scaled absin pulsing."""
    fraction = max(0.0, min(health_fraction(health), 1.0))
    period = max(fraction * 5.0, 1.0)
    pulse = abs(math.sin(math.pi * float(time_tick) / period)) * (1.0 - fraction)
    amount = max(0.0, min(fraction + pulse, 1.0))
    color = team_color_hex(team).lstrip("#")
    red, green, blue = (int(color[offset:offset + 2], 16) for offset in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(
        round(red * amount), round(green * amount), round(blue * amount)
    )


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
