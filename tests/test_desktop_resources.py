"""Resource service exercises real PNG bytes, disk failures and shared history."""

from PIL import Image
import pytest

from app.core.commands import CommandStack
from app.core.project import Project
from app.desktop.resources import ResourceService


@pytest.fixture
def resources(tmp_path):
    project = Project.create(tmp_path / "project", "test", "测试")
    project.contents.save("坦克", {"type": "tank"}, "units")
    stack = CommandStack()
    changed = []
    service = ResourceService(project, stack, on_change=lambda: changed.append(True))
    source = tmp_path / "source.png"
    Image.new("RGBA", (7, 5), (255, 0, 0, 128)).save(source)
    return project, stack, service, source, changed


def test_import_real_png_and_undo_redo_restore_bytes(resources):
    project, stack, service, source, changed = resources
    result = service.import_sprite("content/units/坦克.json", source)
    target = project.sprite_path("units", "坦克")
    assert result == {"path": "sprites/units/坦克.png", "width": 7, "height": 5, "exists": True}
    assert target.read_bytes() == source.read_bytes()
    stack.undo()
    assert not target.exists()
    stack.redo()
    assert target.read_bytes() == source.read_bytes()
    assert len(changed) == 3


def test_failed_undo_preserves_external_bytes_and_history(resources):
    project, stack, service, source, changed = resources
    service.import_sprite("content/units/坦克.json", source)
    target = project.sprite_path("units", "坦克")
    original = target.read_bytes()
    target.write_bytes(b"external edit")
    with pytest.raises(ValueError, match="外部修改"):
        stack.undo()
    assert target.read_bytes() == b"external edit"
    assert stack.can_undo and not stack.can_redo
    assert len(changed) == 1
    target.write_bytes(original)
    stack.undo()
    assert not target.exists()


def test_replace_delete_undo_uses_exact_snapshots_and_confirmations(resources):
    project, stack, service, source, changed = resources
    path = "content/units/坦克.json"
    service.import_sprite(path, source, "-treads")
    original = source.read_bytes()
    Image.new("RGBA", (9, 6), "blue").save(source)
    target = project.sprite_path("units", "坦克", "-treads")
    with pytest.raises(FileExistsError):
        service.import_sprite(path, source, "-treads")
    assert target.read_bytes() == original
    service.import_sprite(path, source, "-treads", overwrite=True)
    replacement = target.read_bytes()
    with pytest.raises(ValueError, match="确认"):
        service.delete_sprite(path, "-treads")
    service.delete_sprite(path, "-treads", confirmed=True)
    assert not target.exists()
    stack.undo()
    assert target.read_bytes() == replacement
    stack.undo()
    assert target.read_bytes() == original
    stack.redo()
    assert target.read_bytes() == replacement


def test_failed_redo_preserves_external_bytes_and_history(resources):
    project, stack, service, source, changed = resources
    service.import_sprite("content/units/坦克.json", source)
    stack.undo()
    target = project.sprite_path("units", "坦克")
    target.write_bytes(b"external edit")
    with pytest.raises(ValueError, match="外部修改"):
        stack.redo()
    assert target.read_bytes() == b"external edit"
    assert stack.can_redo and not stack.can_undo
    target.unlink()
    stack.redo()
    assert target.read_bytes() == source.read_bytes()


def test_current_session_subtype_controls_supported_layers(resources):
    project, stack, _, source, changed = resources
    content = project.contents.get_by_path("units/坦克.json")
    content.data["type"] = "mech"
    service = ResourceService(project, stack, content_resolver=lambda _: content)
    suffixes = {target["suffix"] for target in service.targets("content/units/坦克.json")}
    assert "-base" in suffixes and "-leg" in suffixes and "-treads" not in suffixes
    with pytest.raises(ValueError, match="后缀"):
        service.import_sprite("content/units/坦克.json", source, "-treads")
    assert not stack.can_undo


@pytest.mark.parametrize("path", ["units/坦克.json", "content/units/../坦克.json", "content//units/坦克.json", "content/units/坦克.json/", "C:/outside.json", "content\\units\\坦克.json"])
def test_invalid_content_paths_do_not_write(resources, path):
    project, stack, service, source, changed = resources
    with pytest.raises(ValueError):
        service.import_sprite(path, source)
    assert not stack.can_undo and changed == []


@pytest.mark.parametrize("suffix", ["../outside", "-unknown", "-leg", None, 1])
def test_invalid_or_inapplicable_suffixes_do_not_write(resources, suffix):
    project, stack, service, source, changed = resources
    with pytest.raises(ValueError):
        service.import_sprite("content/units/坦克.json", source, suffix)
    assert not stack.can_undo and changed == []


@pytest.mark.parametrize("broken", [b"not PNG", b"\x89PNG\r\n\x1a\n"])
def test_corrupt_png_cannot_replace_existing_sprite(resources, broken):
    project, stack, service, source, changed = resources
    path = "content/units/坦克.json"
    service.import_sprite(path, source)
    target = project.sprite_path("units", "坦克")
    original = target.read_bytes()
    source.write_bytes(broken)
    with pytest.raises(ValueError, match="PNG"):
        service.import_sprite(path, source, overwrite=True)
    assert target.read_bytes() == original and len(changed) == 1


def test_jpeg_disguised_as_png_is_rejected(resources):
    project, stack, service, source, changed = resources
    Image.new("RGB", (4, 4), "red").save(source, format="JPEG")
    with pytest.raises(ValueError, match="PNG"):
        service.import_sprite("content/units/坦克.json", source)
    assert not stack.can_undo


def test_png_limits_and_snapshot_budget_preserve_prior_state(resources, monkeypatch):
    project, stack, service, source, changed = resources
    path = "content/units/坦克.json"
    monkeypatch.setattr(service, "MAX_DIMENSION", 6)
    with pytest.raises(ValueError, match="尺寸"):
        service.import_sprite(path, source)
    monkeypatch.setattr(service, "MAX_DIMENSION", 8192)
    monkeypatch.setattr(service, "MAX_PIXELS", 30)
    with pytest.raises(ValueError, match="尺寸"):
        service.import_sprite(path, source)
    monkeypatch.setattr(service, "MAX_PIXELS", 8 * 1024 * 1024)
    monkeypatch.setattr(service, "MAX_FILE_BYTES", 2)
    with pytest.raises(ValueError, match="大小"):
        service.import_sprite(path, source)
    monkeypatch.setattr(service, "MAX_FILE_BYTES", 16 * 1024 * 1024)
    monkeypatch.setattr(service, "MAX_SNAPSHOT_BYTES", len(source.read_bytes()))
    service.import_sprite(path, source)
    with pytest.raises(ValueError, match="快照"):
        service.delete_sprite(path, confirmed=True)
    assert project.sprite_path("units", "坦克").read_bytes() == source.read_bytes()
    assert len(changed) == 1
    stack.clear()
    service.delete_sprite(path, confirmed=True)
    assert not project.sprite_path("units", "坦克").exists()


def test_replace_io_failure_leaves_original_history_and_no_temporary_file(resources, monkeypatch):
    import os
    project, stack, service, source, changed = resources
    path = "content/units/坦克.json"
    service.import_sprite(path, source)
    target = project.sprite_path("units", "坦克")
    original = target.read_bytes()
    Image.new("RGBA", (4, 5), "green").save(source)
    def fail(*_):
        raise PermissionError("目标不可写")
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(PermissionError):
        service.import_sprite(path, source, overwrite=True)
    assert target.read_bytes() == original and len(changed) == 1
    assert list(target.parent.glob("*.tmp")) == []
    assert stack.undo_description == "导入贴图 坦克.png"


def test_same_bytes_do_not_create_duplicate_resource_history(resources):
    _, stack, service, source, changed = resources
    service.import_sprite("content/units/坦克.json", source)
    service.import_sprite("content/units/坦克.json", source, overwrite=True)
    stack.undo()
    assert not stack.can_undo and len(changed) == 2


def test_notification_failure_does_not_lose_successful_disk_history(resources, caplog):
    project, stack, _, source, _ = resources
    def failed_notification():
        raise RuntimeError("刷新通知失败")
    service = ResourceService(project, stack, on_change=failed_notification)
    service.import_sprite("content/units/坦克.json", source)
    target = project.sprite_path("units", "坦克")
    assert target.read_bytes() == source.read_bytes() and stack.can_undo
    stack.undo()
    assert not target.exists() and stack.can_redo
    assert "刷新通知失败" in caplog.text


def test_external_change_during_staged_write_is_not_overwritten(resources, monkeypatch):
    import os
    project, stack, service, source, changed = resources
    path = "content/units/坦克.json"
    service.import_sprite(path, source)
    target = project.sprite_path("units", "坦克")
    Image.new("RGBA", (4, 4), "green").save(source)
    original_fsync = os.fsync
    def changed_while_flushing(fd):
        original_fsync(fd)
        target.write_bytes(b"external update during staging")
    monkeypatch.setattr(os, "fsync", changed_while_flushing)
    with pytest.raises(ValueError, match="外部修改"):
        service.import_sprite(path, source, overwrite=True)
    assert target.read_bytes() == b"external update during staging"
    assert len(changed) == 1 and list(target.parent.glob("*.tmp")) == []


def test_resource_target_symlink_is_rejected(resources, tmp_path):
    project, stack, service, source, changed = resources
    target = project.sprite_path("units", "坦克")
    external = tmp_path / "outside.png"
    external.write_bytes(b"outside")
    try:
        target.symlink_to(external)
    except OSError as exc:
        pytest.skip(f"创建符号链接需要系统授权: {exc}")
    with pytest.raises(ValueError, match="路径"):
        service.import_sprite("content/units/坦克.json", source, overwrite=True)
    assert external.read_bytes() == b"outside" and not stack.can_undo
