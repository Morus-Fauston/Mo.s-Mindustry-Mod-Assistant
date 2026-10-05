from pathlib import Path
from types import SimpleNamespace
from contextlib import contextmanager
import os

import pytest

from app.desktop.resource_watch import ResourceWatch
from app.desktop import resource_watch


def test_observer_detects_changed_bytes_when_stat_signature_is_identical(tmp_path, monkeypatch):
    image = tmp_path / "sprites/units/a.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"one")
    original_stat = Path.stat
    fixed = image.stat()

    def same_stat(path, *args, **kwargs):
        result = original_stat(path, *args, **kwargs)
        if path == image:
            return SimpleNamespace(
                **{name: getattr(result, name) for name in dir(result) if name.startswith('st_') and name != 'st_ctime_ns'},
                st_ctime_ns=fixed.st_ctime_ns)
        return result

    # Only the observation tuple is fixed; the verified read still uses real OS handles.
    monkeypatch.setattr(Path, "stat", same_stat)
    watch = ResourceWatch(tmp_path)
    assert not watch.scan()
    image.write_bytes(b"two")
    os.utime(image, ns=(fixed.st_atime_ns, fixed.st_mtime_ns))
    assert watch.scan()
    assert not watch.scan()


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


def test_digest_reads_share_budget_and_rotate_without_starving_later_files(tmp_path, monkeypatch):
    directory = tmp_path / "sprites"
    directory.mkdir()
    for name, size in (("a", 8), ("b", 8), ("c", 4)):
        (directory / f"{name}.png").write_bytes(name.encode() * size)
    monkeypatch.setattr(ResourceWatch, "MAX_FILE_BYTES", 8)
    monkeypatch.setattr(ResourceWatch, "MAX_SCAN_BYTES", 12)
    monkeypatch.setattr(ResourceWatch, "READ_CHUNK_BYTES", 4)
    original_open = resource_watch.open_project_file
    reads, opened, handles = [], [], []

    @contextmanager
    def observe_open(root, path):
        opened.append(path.name)
        with original_open(root, path) as stream:
            handles.append(stream)

            class Counted:
                def fileno(self):
                    return stream.fileno()

                def read(self, amount):
                    assert 0 < amount <= 4
                    chunk = stream.read(amount)
                    reads.append(len(chunk))
                    return chunk

            yield Counted()

    monkeypatch.setattr(resource_watch, "open_project_file", observe_open)
    watch = ResourceWatch(tmp_path)
    assert sum(reads) == 8 and opened == ["a.png"]
    for expected in (["b.png", "c.png"], ["a.png"], ["b.png", "c.png"]):
        reads.clear()
        opened.clear()
        watch.scan()
        assert opened == expected
        assert sum(reads) <= 12
        assert all(stream.closed for stream in handles)
    watch.close()
    assert not watch._digests and not watch._snapshot and not watch._next_path
    with pytest.raises(ValueError, match="关闭"):
        watch.scan()
    assert all(stream.closed for stream in handles)


def test_oversize_assets_are_stat_only_and_do_not_block_supported_assets(tmp_path, monkeypatch):
    directory = tmp_path / "sprites"
    directory.mkdir()
    large, small = directory / "a.png", directory / "z.png"
    large.write_bytes(b"oversized")
    small.write_bytes(b"ok")
    monkeypatch.setattr(ResourceWatch, "MAX_FILE_BYTES", 8)
    monkeypatch.setattr(ResourceWatch, "MAX_SCAN_BYTES", 12)
    original_open = resource_watch.open_project_file
    opened = []

    @contextmanager
    def observe_open(root, path):
        opened.append(path.name)
        with original_open(root, path) as stream:
            yield stream

    monkeypatch.setattr(resource_watch, "open_project_file", observe_open)
    watch = ResourceWatch(tmp_path)
    assert opened == ["z.png"]
    assert not watch.scan()
    large.write_bytes(b"even larger")
    assert watch.scan()
    assert set(opened) == {"z.png"}


def test_failed_handle_verification_discards_digest_and_recovery_is_observable(tmp_path, monkeypatch):
    directory = tmp_path / "sprites"
    directory.mkdir()
    (directory / "a.png").write_bytes(b"png")
    watch = ResourceWatch(tmp_path)
    original_open = resource_watch.open_project_file
    handles = []

    @contextmanager
    def fail_after_read(root, path):
        with original_open(root, path) as stream:
            handles.append(stream)
            yield stream
            raise OSError("句柄复核失败")

    monkeypatch.setattr(resource_watch, "open_project_file", fail_after_read)
    with pytest.raises(OSError, match="内容观察失败"):
        watch.scan()
    assert all(stream.closed for stream in handles)
    failed_revision = watch.revision
    monkeypatch.setattr(resource_watch, "open_project_file", original_open)
    assert watch.scan() and watch.revision > failed_revision
    assert not watch.scan()
