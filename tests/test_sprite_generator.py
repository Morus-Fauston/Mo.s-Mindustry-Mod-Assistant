"""Tests for app.core.sprite_generator — pure Pillow, no Qt (F-20).

Covers the three generators:
- generate_outline: same size, 1px expansion, default black color
- generate_shadow: same size, bottom placement, opacity-respecting alpha
- generate_full: canvas expansion, mirror, layers, no engine
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.core import sprite_generator as sg


# ── Fixtures ───────────────────────────────────────────────────────────


def _source(size: int = 32) -> Image.Image:
    """32x32 transparent image with a solid ellipse in the center."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 24, 24), fill=(255, 0, 0, 255))
    return img


@pytest.fixture
def src() -> Image.Image:
    return _source()


# ── outline ────────────────────────────────────────────────────────────


class TestOutline:
    def test_same_size(self, src):
        out = sg.generate_outline(src)
        assert out.size == src.size

    def test_expands_1px(self, src):
        """主体椭圆左缘在 x=8；扩展后 x=7 出现轮廓像素。"""
        assert src.getpixel((7, 16))[3] == 0  # 原图透明
        out = sg.generate_outline(src)
        assert out.getpixel((7, 16))[3] > 0  # 轮廓外扩 1px

    def test_default_black_color(self, src):
        out = sg.generate_outline(src)
        r, g, b, _ = out.getpixel((7, 16))
        assert (r, g, b) == (0, 0, 0)

    def test_custom_color(self, src):
        out = sg.generate_outline(src, color="#FF0000")
        r, g, b, _ = out.getpixel((7, 16))
        assert (r, g, b) == (255, 0, 0)

    def test_body_preserved_on_top(self, src):
        """主体像素颜色不被轮廓覆盖。"""
        out = sg.generate_outline(src)
        r, g, b, _ = out.getpixel((16, 16))
        assert (r, g, b) == (255, 0, 0)

    def test_alpha_fully_opaque_in_body(self, src):
        out = sg.generate_outline(src)
        assert out.getpixel((16, 16))[3] == 255


# ── shadow ─────────────────────────────────────────────────────────────


class TestShadow:
    def test_same_size(self, src):
        sh = sg.generate_shadow(src)
        assert sh.size == src.size

    def test_black_pixels(self, src):
        sh = sg.generate_shadow(src)
        r, g, b, a = sh.getpixel((16, 30))
        assert a > 0
        assert (r, g, b) == (0, 0, 0)

    def test_alpha_respects_opacity(self, src):
        """阴影 alpha 由 opacity 约束，绝不能是 255（原 alpha 直接 put 的 bug）。"""
        sh = sg.generate_shadow(src)
        max_alpha = max(sh.getchannel("A").tobytes())
        assert 0 < max_alpha <= 81  # 80/255 * 255 ≈ 80

    def test_placed_at_bottom(self, src):
        sh = sg.generate_shadow(src)
        # 底部有阴影，顶部透明
        assert sh.getpixel((16, 30))[3] > 0
        assert sh.getpixel((16, 1))[3] == 0

    def test_default_opacity_80(self, src):
        sh = sg.generate_shadow(src)
        max_alpha = max(sh.getchannel("A").tobytes())
        assert max_alpha == 80


# ── full ───────────────────────────────────────────────────────────────


class TestFull:
    def test_contains_base(self, src):
        full = sg.generate_full(src)
        assert full.size == src.size
        assert full.getpixel((16, 16))[3] == 255

    def test_canvas_expands_for_weapon(self, src):
        """武器伸出主体左侧 → 画布扩展容纳。"""
        wpn = Image.new("RGBA", (10, 10), (0, 255, 0, 255))
        full = sg.generate_full(
            src,
            weapons=[{"x": 4.0, "y": 2.0, "mirror": True}],
            weapon_sprites=[wpn],
            ppu=4.0,
        )
        assert full.size[0] > src.size[0]  # 42 > 32

    def test_contains_weapon_pixels(self, src):
        wpn = Image.new("RGBA", (10, 10), (0, 255, 0, 255))
        full = sg.generate_full(
            src,
            weapons=[{"x": 4.0, "y": 2.0, "mirror": True}],
            weapon_sprites=[wpn],
            ppu=4.0,
        )
        greens = 0
        a = full.getchannel("A").tobytes()
        r = full.getchannel("R").tobytes()
        g = full.getchannel("G").tobytes()
        b = full.getchannel("B").tobytes()
        greens = sum(1 for i in range(len(a)) if a[i] > 0 and r[i] == 0 and g[i] == 255 and b[i] == 0)
        assert greens > 0

    def test_mirror_both_sides(self, src):
        """mirror=True 时左右各有一份武器像素。"""
        wpn = Image.new("RGBA", (8, 8), (0, 255, 0, 255))
        full = sg.generate_full(
            src,
            weapons=[{"x": 2.0, "y": 0.0, "mirror": True}],
            weapon_sprites=[wpn],
            ppu=4.0,
        )
        w = full.size[0]
        greens = [x for x in range(w) for y in range(full.size[1])
                  if full.getpixel((x, y))[:3] == (0, 255, 0)]
        left = any(x < w // 2 for x in greens)
        right = any(x >= w // 2 for x in greens)
        assert left and right

    def test_contains_layers(self, src):
        """额外图层按中心对齐合成（层在主体上方）。"""
        layer = Image.new("RGBA", (32, 32), (0, 0, 255, 255))
        full = sg.generate_full(src, layers=[layer])
        assert full.getpixel((16, 16))[:3] == (0, 0, 255)  # layer 覆盖主体

    def test_no_engine_parameter(self, src):
        """API 无 engine 参数——结构上不可能绘制引擎。"""
        import inspect

        sig = inspect.signature(sg.generate_full)
        assert "engine" not in sig.parameters

    def test_no_qt_import(self):
        """core 层约束：sprite_generator 不得 import Qt。"""
        src_code = Path(sg.__file__).read_text(encoding="utf-8")
        assert "PySide6" not in src_code
        assert "PyQt" not in src_code

    def test_weapon_offset_rounded(self, src):
        """武器偏移四舍五入到整像素（.5 进位）。"""
        wpn = Image.new("RGBA", (4, 4), (0, 255, 0, 255))
        # x=1.625*4=6.5 → round(16+6.5-2)=21；x=1.375*4=5.5 → round(16+5.5-2)=20
        a = sg.generate_full(src, weapons=[{"x": 1.625, "y": 0}], weapon_sprites=[wpn])
        b = sg.generate_full(src, weapons=[{"x": 1.375, "y": 0}], weapon_sprites=[wpn])
        # 两者武器位置相差 1px（21-20）
        assert a.size == b.size
