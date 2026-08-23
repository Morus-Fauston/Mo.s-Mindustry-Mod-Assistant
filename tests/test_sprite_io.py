"""Core PNG import and write contract tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from PIL import Image

from app.core import sprite_io
from app.core.project import Project
from app.core.sprite_io import import_sprite, save_sprite


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project.create(tmp_path, "sprite-test", "Sprite Test")


def test_import_sprite_copies_verified_png_without_reencoding(project: Project, tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    Image.new("RGBA", (2, 2), (12, 34, 56, 255)).save(source, "PNG")

    target = import_sprite(project, "units", "scout", source)

    assert target == project.sprite_path("units", "scout")
    assert target.read_bytes() == source.read_bytes()


@pytest.mark.parametrize("payload", [b"not an image", b"\x89PNG\r\n\x1a\ntruncated"])
def test_import_sprite_rejects_invalid_or_disguised_png(project: Project, tmp_path: Path, payload: bytes) -> None:
    source = tmp_path / "invalid.png"
    source.write_bytes(payload)

    with pytest.raises(ValueError, match="PNG"):
        import_sprite(project, "units", "scout", source)


def test_import_sprite_rejects_a_readable_non_png(project: Project, tmp_path: Path) -> None:
    source = tmp_path / "renamed.png"
    Image.new("RGB", (2, 2), "red").save(source, "JPEG")

    with pytest.raises(ValueError, match="不是 PNG"):
        import_sprite(project, "units", "scout", source)


def test_import_sprite_rejects_existing_target_unless_overwrite_is_explicit(project: Project, tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGBA", (2, 2), "red").save(source, "PNG")
    target = project.sprite_path("units", "scout")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"old")

    with pytest.raises(FileExistsError, match="scout"):
        import_sprite(project, "units", "scout", source)

    import_sprite(project, "units", "scout", source, overwrite=True)
    assert target.read_bytes() == source.read_bytes()


def test_save_sprite_uses_project_path_suffix_and_explicit_overwrite(project: Project) -> None:
    first = Image.new("RGBA", (3, 3), "red")
    second = Image.new("RGBA", (3, 3), "blue")

    target = save_sprite(project, "blocks", "wall", first, "-outline")
    assert target == project.sprite_path("blocks", "wall", "-outline")
    assert Image.open(target).getpixel((0, 0))[:3] == (255, 0, 0)

    with pytest.raises(FileExistsError, match="wall-outline"):
        save_sprite(project, "blocks", "wall", second, "-outline")

    save_sprite(project, "blocks", "wall", second, "-outline", overwrite=True)
    assert Image.open(target).getpixel((0, 0))[:3] == (0, 0, 255)


def test_save_sprite_writes_the_canonical_png_bytes_for_a_fixed_rgba_image(project: Project) -> None:
    target = save_sprite(project, "blocks", "wall", Image.new("RGBA", (2, 2), "red"))

    assert hashlib.sha256(target.read_bytes()).hexdigest() == (
        "de11064a1fe6798bb786999d9c0ed73dc92aa15971772899eaebf7df62bb1fe0"
    )


def test_save_sprite_keeps_existing_png_when_overwrite_write_fails(project: Project, monkeypatch) -> None:
    target = save_sprite(project, "blocks", "wall", Image.new("RGBA", (2, 2), "red"))
    before = target.read_bytes()

    def fail_write(*args, **kwargs) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(sprite_io, "_write_canonical_png", fail_write)
    with pytest.raises(OSError, match="disk full"):
        save_sprite(project, "blocks", "wall", Image.new("RGBA", (2, 2), "blue"), overwrite=True)

    assert target.read_bytes() == before


def test_import_sprite_keeps_existing_png_when_copy_fails(project: Project, tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.png"
    Image.new("RGBA", (2, 2), "blue").save(source, "PNG")
    target = save_sprite(project, "units", "scout", Image.new("RGBA", (2, 2), "red"))
    before = target.read_bytes()

    def fail_copy(*args, **kwargs) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(sprite_io.shutil, "copy2", fail_copy)
    with pytest.raises(OSError, match="disk full"):
        import_sprite(project, "units", "scout", source, overwrite=True)

    assert target.read_bytes() == before


def test_sprite_io_has_no_qt_dependency() -> None:
    source = Path(__file__).parents[1] / "app" / "core" / "sprite_io.py"
    code = source.read_text(encoding="utf-8")
    assert "PySide6" not in code
    assert "PyQt" not in code
