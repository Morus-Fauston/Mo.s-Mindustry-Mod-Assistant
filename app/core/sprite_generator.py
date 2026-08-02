"""Sprite auto-generation: outline / shadow / full (F-20).

Pure Pillow implementation — no Qt dependency (core layer constraint).
All functions accept and return PIL.Image.Image in RGBA mode.
"""

from __future__ import annotations

from PIL import Image, ImageFilter


def generate_outline(
    source: Image.Image,
    expand_px: int = 1,
    color: str = "#000000",
) -> Image.Image:
    """Generate an outline (轮廓) image from the source sprite.

    Algorithm:
      1. Extract alpha channel
      2. Expand alpha via MaxFilter (3x3) ``expand_px`` times
      3. Fill expanded region with solid color
      4. Composite original sprite on top

    Returns RGBA image same size as source.
    """
    src = source.convert("RGBA")
    w, h = src.size

    # Extract and expand alpha
    alpha = src.getchannel("A")
    for _ in range(expand_px):
        alpha = alpha.filter(ImageFilter.MaxFilter(3))

    # Build outline layer: solid color where expanded alpha > 0
    outline_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    # Parse color
    r, g, b = _parse_color(color)
    color_layer = Image.new("RGBA", (w, h), (r, g, b, 255))
    outline_layer.paste(color_layer, mask=alpha)

    # Composite: outline behind, source on top
    result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    result = Image.alpha_composite(result, outline_layer)
    result = Image.alpha_composite(result, src)
    return result


def generate_shadow(
    source: Image.Image,
    opacity: int = 80,
) -> Image.Image:
    """Generate a shadow (阴影) image from the source sprite.

    Algorithm:
      1. Extract alpha channel
      2. Vertically compress to 50% height
      3. Fill with semi-transparent black
      4. Place at bottom of a canvas same size as source

    Returns RGBA image same size as source.
    """
    src = source.convert("RGBA")
    w, h = src.size

    alpha = src.getchannel("A")
    # Compress vertically to 50%
    shadow_h = max(1, h // 2)
    alpha_compressed = alpha.resize((w, shadow_h), Image.Resampling.LANCZOS)

    # Build shadow: black RGB, alpha = compressed alpha scaled by opacity.
    # (putalpha replaces the whole channel, so fold opacity into the mask
    #  rather than compositing a flat-opacity layer, which would be overwritten.)
    alpha_with_opacity = alpha_compressed.point(lambda p: int(p * opacity / 255))
    shadow_img = Image.new("RGBA", (w, shadow_h), (0, 0, 0, 0))
    shadow_img.putalpha(alpha_with_opacity)

    # Place at bottom of full-size canvas
    result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    y_offset = h - shadow_h
    result.paste(shadow_img, (0, y_offset))
    return result


def generate_full(
    base: Image.Image,
    layers: list[Image.Image] | None = None,
    weapons: list[dict] | None = None,
    weapon_sprites: list[Image.Image | None] | None = None,
    ppu: float = 4.0,
) -> Image.Image:
    """Generate a full (完整图/定妆照) image: layers + weapons, no engine.

    Args:
        base: Main body sprite (RGBA).
        layers: Additional layer images to composite (cell, etc.), centered.
        weapons: List of weapon dicts with x/y/mirror keys.
        weapon_sprites: Corresponding weapon sprite images (or None to skip).
        ppu: Pixels per world unit (default 4).

    Returns RGBA image. Canvas is expanded if weapons exceed base bounds.
    """
    base = base.convert("RGBA")
    bw, bh = base.size
    cx, cy = bw / 2.0, bh / 2.0

    # Calculate required canvas size (weapons may extend beyond base)
    min_x, min_y, max_x, max_y = 0.0, 0.0, float(bw), float(bh)
    if weapons and weapon_sprites:
        for w, ws in zip(weapons, weapon_sprites):
            if ws is None:
                continue
            ws = ws.convert("RGBA")
            wx = float(w.get("x", 0))
            wy = float(w.get("y", 0))
            mirror = bool(w.get("mirror", False))
            ww, wh = ws.size
            # Position (round to nearest pixel per 006 report)
            sx = round(cx + wx * ppu - ww / 2.0)
            sy = round(cy - wy * ppu - wh / 2.0)
            min_x = min(min_x, sx)
            min_y = min(min_y, sy)
            max_x = max(max_x, sx + ww)
            max_y = max(max_y, sy + wh)
            if mirror:
                sx_m = round(cx - wx * ppu - ww / 2.0)
                min_x = min(min_x, sx_m)
                max_x = max(max_x, sx_m + ww)

    # Create expanded canvas
    offset_x = int(-min_x) if min_x < 0 else 0
    offset_y = int(-min_y) if min_y < 0 else 0
    canvas_w = int(max_x - min_x)
    canvas_h = int(max_y - min_y)
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    # Paste base centered
    base_x = offset_x + int(cx - bw / 2.0)
    base_y = offset_y + int(cy - bh / 2.0)
    canvas.paste(base, (base_x, base_y), base)

    # Paste additional layers (centered on base)
    if layers:
        for layer in layers:
            layer = layer.convert("RGBA")
            lw, lh = layer.size
            lx = offset_x + int(cx - lw / 2.0)
            ly = offset_y + int(cy - lh / 2.0)
            canvas = Image.alpha_composite(
                canvas,
                _place_on_canvas(layer, lx, ly, canvas_w, canvas_h),
            )

    # Paste weapons
    if weapons and weapon_sprites:
        for w, ws in zip(weapons, weapon_sprites):
            if ws is None:
                continue
            ws = ws.convert("RGBA")
            wx = float(w.get("x", 0))
            wy = float(w.get("y", 0))
            mirror = bool(w.get("mirror", False))
            ww, wh = ws.size
            sx = offset_x + round(cx + wx * ppu - ww / 2.0)
            sy = offset_y + round(cy - wy * ppu - wh / 2.0)
            canvas = Image.alpha_composite(
                canvas,
                _place_on_canvas(ws, sx, sy, canvas_w, canvas_h),
            )
            if mirror:
                flipped = ws.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                sx_m = offset_x + round(cx - wx * ppu - ww / 2.0)
                canvas = Image.alpha_composite(
                    canvas,
                    _place_on_canvas(flipped, sx_m, sy, canvas_w, canvas_h),
                )

    return canvas


# ── helpers ────────────────────────────────────────────────────────────────


def _parse_color(hex_str: str) -> tuple[int, int, int]:
    """Parse '#RRGGBB' or 'RRGGBB' to (r, g, b)."""
    s = hex_str.lstrip("#")
    if len(s) == 6:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    return 0, 0, 0


def _place_on_canvas(
    img: Image.Image, x: int, y: int, cw: int, ch: int
) -> Image.Image:
    """Place img at (x, y) on a transparent canvas of size (cw, ch)."""
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    canvas.paste(img, (x, y))
    return canvas
