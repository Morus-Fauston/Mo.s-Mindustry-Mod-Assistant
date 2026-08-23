"""Qt-free PNG import and write operations for project sprite paths."""

from __future__ import annotations

import os
import shutil
import struct
import tempfile
import zlib
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, UnidentifiedImageError

if TYPE_CHECKING:
    from .project import Project


def import_sprite(
    project: Project,
    category: str,
    name: str,
    source_path: str | Path,
    suffix: str = "",
    *,
    overwrite: bool = False,
) -> Path:
    """Verify a source is PNG, then copy its original bytes into a project.

    Pillow performs validation, but the successful copy intentionally avoids
    decoding and re-encoding so source pixels and metadata are preserved.
    """
    source = Path(source_path)
    try:
        with Image.open(source) as image:
            if image.format != "PNG":
                raise ValueError(f"精灵图来源不是 PNG: {source}")
            image.verify()
    except (FileNotFoundError, OSError, UnidentifiedImageError) as exc:
        raise ValueError(f"精灵图来源不是可读取的 PNG: {source}") from exc

    target = project.sprite_path(category, name, suffix)
    _ensure_writable(target, overwrite)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == target.resolve():
        return target

    temporary = _temporary_path(target)
    try:
        shutil.copy2(source, temporary)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def save_sprite(
    project: Project,
    category: str,
    name: str,
    image: Image.Image,
    suffix: str = "",
    *,
    overwrite: bool = False,
) -> Path:
    """Write a Pillow image as canonical PNG using the sprite-path contract.

    The fixture and A4 baseline compare PNG files by SHA-256.  Pillow's PNG
    encoder can produce different deflate streams on different platforms, so
    generated sprites use a fixed RGBA encoding instead of ``Image.save``.
    """
    if not isinstance(image, Image.Image):
        raise TypeError("image 必须是 PIL.Image.Image")

    target = project.sprite_path(category, name, suffix)
    _ensure_writable(target, overwrite)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(target)
    try:
        _write_canonical_png(temporary, image)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def _ensure_writable(target: Path, overwrite: bool) -> None:
    if target.exists() and not overwrite:
        raise FileExistsError(f"精灵图已存在，需显式允许覆盖: {target}")


def _temporary_path(target: Path) -> Path:
    fd, path = tempfile.mkstemp(prefix=f".{target.stem}_", suffix=".tmp", dir=target.parent)
    os.close(fd)
    return Path(path)


def _write_canonical_png(path: Path, image: Image.Image) -> None:
    """Encode image bytes without platform-dependent PNG compression choices."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    if width <= 0 or height <= 0:
        raise ValueError("精灵图尺寸必须大于 0")

    pixels = rgba.tobytes()
    row_size = width * 4
    rows = b"".join(
        b"\x00" + pixels[offset:offset + row_size]
        for offset in range(0, len(pixels), row_size)
    )
    compressed = _stored_deflate(rows)
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def _stored_deflate(data: bytes) -> bytes:
    """Return a zlib stream made solely of deterministic uncompressed blocks."""
    blocks = bytearray(b"\x78\x01")
    for offset in range(0, len(data), 65535):
        block = data[offset:offset + 65535]
        final = offset + len(block) >= len(data)
        blocks.append(1 if final else 0)
        blocks.extend(struct.pack("<H", len(block)))
        blocks.extend(struct.pack("<H", 0xFFFF - len(block)))
        blocks.extend(block)
    blocks.extend(struct.pack(">I", zlib.adler32(data) & 0xFFFFFFFF))
    return bytes(blocks)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )
