"""Qt-free PNG import and write operations for project sprite paths."""

from __future__ import annotations

import os
import shutil
import tempfile
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
    """Write a Pillow image as PNG using the project's sprite-path contract."""
    if not isinstance(image, Image.Image):
        raise TypeError("image 必须是 PIL.Image.Image")

    target = project.sprite_path(category, name, suffix)
    _ensure_writable(target, overwrite)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(target)
    try:
        image.save(temporary, format="PNG")
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
