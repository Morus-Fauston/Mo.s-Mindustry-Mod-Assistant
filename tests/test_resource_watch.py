from pathlib import Path

import pytest

from app.desktop.resource_watch import ResourceWatch


def test_png_observer_detects_create_replace_remove_and_closes(tmp_path):
    watch = ResourceWatch(tmp_path)
    assert not watch.scan()
    image = tmp_path / "sprites/units/a.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"one")
    assert watch.scan()
    revision = watch.revision
    assert not watch.scan()
    image.write_bytes(b"new image")
    assert watch.scan() and watch.revision > revision
    image.unlink()
    assert watch.scan()
    watch.close()
    with pytest.raises(ValueError, match="关闭"):
        watch.scan()


def test_observer_ignores_non_png_and_has_enumeration_bound(tmp_path, monkeypatch):
    directory = tmp_path / "sprites"
    directory.mkdir()
    watch = ResourceWatch(tmp_path)
    (directory / "notes.txt").write_text("not PNG")
    assert not watch.scan()
    monkeypatch.setattr(ResourceWatch, "MAX_ENTRIES", 1)
    (directory / "another.txt").touch()
    with pytest.raises(ValueError, match="上限"):
        watch.scan()
