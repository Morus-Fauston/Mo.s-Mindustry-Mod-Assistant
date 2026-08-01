"""预览渲染纯数学层测试——坐标公式脱离 Qt 验证（候选①核心收益）。

覆盖 ADR-003 要求的核心管线公式：
- PPU=4 坐标缩放
- Mindustry(y上) → Qt(y下) 翻转
- 武器 mirror 镜像份
- 引用武器 x/y 回退默认值
- 引擎双圆几何 + engineLayer z 切换 + 颜色归一化
"""

from __future__ import annotations

import math

from app.core.preview_math import (
    PPU,
    CircleSpec,
    LayerSpec,
    SceneSpec,
    compute_engine_circles,
    compute_weapon_layers,
    weapon_xy,
)


class TestWeaponXY:
    def test_override_wins(self):
        assert weapon_xy({"x": 3.0, "y": -2.0}) == (3.0, -2.0)

    def test_fallback_to_ref_defaults(self):
        # 条目无 x/y → 用被引用武器默认值
        assert weapon_xy({}, ref_defaults=(5.0, -3.0)) == (5.0, -3.0)

    def test_partial_override_mixes(self):
        # 只有 x 覆盖，y 回退默认
        assert weapon_xy({"x": 1.0}, ref_defaults=(5.0, -3.0)) == (1.0, -3.0)

    def test_int_coerced_to_float(self):
        wx, wy = weapon_xy({"x": 2, "y": 4})
        assert isinstance(wx, float) and isinstance(wy, float)


class TestComputeWeaponLayers:
    def _size(self, name):
        return (20.0, 10.0)  # 固定武器精灵 20x10

    def test_ppu_scaling_and_y_flip(self):
        # 中心 (100, 100)，武器 (x=2, y=3)
        # scene_x = 100 + 2*4 - 10(半宽) = 98
        # scene_y = 100 - 3*4 - 5(半高) = 83  ← y 翻转（减）
        specs = compute_weapon_layers(
            [{"name": "w"}], center=(100.0, 100.0), sprite_size=self._size,
            resolve_xy=lambda w, n: (2.0, 3.0),
        )
        assert len(specs) == 1
        s = specs[0]
        assert s.x == 100 + 2 * PPU - 10
        assert s.y == 100 - 3 * PPU - 5
        assert s.z == 10
        assert not s.flip_x

    def test_mirror_produces_second_flipped(self):
        specs = compute_weapon_layers(
            [{"name": "w", "mirror": True}],
            center=(100.0, 100.0), sprite_size=self._size,
            resolve_xy=lambda w, n: (2.0, 3.0),
        )
        assert len(specs) == 2
        orig, mirrored = specs
        assert not orig.flip_x
        assert mirrored.flip_x
        # 镜像份 x 关于中心对称：cx - wx*PPU - 半宽
        assert mirrored.x == 100 - 2 * PPU - 10
        assert mirrored.y == orig.y  # y 相同
        assert orig.key == mirrored.key == "__weapon_0__"

    def test_no_sprite_skipped(self):
        specs = compute_weapon_layers(
            [{"name": "missing"}], center=(0.0, 0.0),
            sprite_size=lambda n: None,
        )
        assert specs == []

    def test_no_name_skipped(self):
        specs = compute_weapon_layers(
            [{"x": 1}], center=(0.0, 0.0), sprite_size=self._size,
        )
        assert specs == []

    def test_per_weapon_key_index(self):
        specs = compute_weapon_layers(
            [{"name": "a"}, {"name": "b"}], center=(0.0, 0.0),
            sprite_size=self._size, resolve_xy=lambda w, n: (0.0, 0.0),
        )
        assert specs[0].key == "__weapon_0__"
        assert specs[1].key == "__weapon_1__"


class TestComputeEngineCircles:
    def test_no_engine_size_returns_empty(self):
        assert compute_engine_circles({}, center=(0, 0)) == []
        assert compute_engine_circles({"engineSize": 0}, center=(0, 0)) == []

    def test_outer_radius_and_position(self):
        circles = compute_engine_circles(
            {"engineSize": 2.0, "engineOffset": 3.0}, center=(100.0, 100.0),
        )
        outer = circles[0]
        assert outer.radius == 2.0 * PPU
        assert outer.cx == 100.0
        # y 取反：中心偏后 = cy + offset*PPU
        assert outer.cy == 100.0 + 3.0 * PPU

    def test_default_z_below_body(self):
        circles = compute_engine_circles({"engineSize": 1.0}, center=(0, 0))
        assert circles[0].z == -1

    def test_engine_layer_positive_raises_z(self):
        circles = compute_engine_circles(
            {"engineSize": 1.0, "engineLayer": 2.0}, center=(0, 0),
        )
        assert circles[0].z == 11

    def test_inner_circle_offset_along_rotation(self):
        circles = compute_engine_circles({"engineSize": 4.0}, center=(50.0, 50.0))
        outer, inner = circles
        assert inner.radius == outer.radius / 2.0
        # rotation=-90° → cos=0, sin=-1；内圈沿 -sin 方向偏移 rad/4
        expected_ix = outer.cx - math.cos(math.radians(-90.0)) * (outer.radius / 4.0)
        expected_iy = outer.cy - math.sin(math.radians(-90.0)) * (outer.radius / 4.0)
        assert abs(inner.cx - expected_ix) < 1e-9
        assert abs(inner.cy - expected_iy) < 1e-9

    def test_color_normalization(self):
        circles = compute_engine_circles(
            {"engineSize": 1.0, "engineColor": "ff0000", "engineColorInner": "#00ff00"},
            center=(0, 0),
        )
        assert circles[0].color_hex == "#ff0000"  # 补 #
        assert circles[1].color_hex == "#00ff00"  # 已有 # 保留

    def test_default_colors_when_unset(self):
        circles = compute_engine_circles({"engineSize": 1.0}, center=(0, 0))
        assert circles[0].color_hex == "#ffc832"  # 外圈默认亮黄/橙
        assert circles[1].color_hex == "#ffffff"  # 内圈默认白


class TestSceneSpec:
    def test_empty_default(self):
        s = SceneSpec()
        assert s.pixmaps == []
        assert s.circles == []
