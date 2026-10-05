"""Real-file content actions through the desktop public boundary."""

import json
import os
from pathlib import Path

import pytest

from app.core.commands import CommandStack, SetFieldCommand
from app.core.project import ModInfo, Project
from app.desktop.content_actions import ContentActions


@pytest.fixture
def actions(tmp_path):
    project = Project(tmp_path, ModInfo(name="test"))
    commands = CommandStack()
    return ContentActions(project, commands), commands, tmp_path


def test_create_template_then_undo_and_redo_real_file(actions):
    service, commands, root = actions
    result = service.create("UnitType-flying", "scout", "units")
    target = root / "content/units/scout.json"
    assert result.after_path == "content/units/scout.json"
    assert json.loads(target.read_text("utf-8"))["type"] == "flying"
    commands.undo()
    assert not target.exists()
    commands.redo()
    assert json.loads(target.read_text("utf-8"))["name"] == "scout"


def put(root, relative, data):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode("utf-8"))
    return path


@pytest.mark.parametrize("data", [{"type": "mech", "name": "显示名称"}, {"type": "mech"}])
def test_rename_exact_category_existing_name_and_only_matching_sprites(actions, data):
    service, commands, root = actions
    old = put(root, "content/units/scout.json", data)
    original = old.read_bytes()
    other = put(root, "content/weapons/scout.json", {"type": "Weapon", "name": "不变"})
    other_bytes = other.read_bytes()
    for sprite in ("scout.png", "scout-cell.png", "scout-custom.png", "scoutx.png"):
        put(root, "sprites/units/" + sprite, sprite.encode())
    put(root, "sprites/weapons/scout.png", b"other")
    result = service.rename("content/units/scout.json", "new-scout")
    target = root / "content/units/new-scout.json"
    expected = {**data, "name": "new-scout"} if "name" in data else data
    assert json.loads(target.read_text("utf-8")) == expected
    assert not old.exists()
    assert len(result.resource_moves) == 3
    assert (root / "sprites/units/new-scout-cell.png").read_bytes() == b"scout-cell.png"
    assert (root / "sprites/units/scoutx.png").read_bytes() == b"scoutx.png"
    assert (root / "sprites/weapons/scout.png").read_bytes() == b"other"
    assert other.read_bytes() == other_bytes
    commands.undo()
    assert old.read_bytes() == original
    assert not target.exists()
    assert (root / "sprites/units/scout-cell.png").read_bytes() == b"scout-cell.png"
    commands.redo()
    assert json.loads(target.read_text("utf-8")) == expected


def test_delete_only_selected_content_and_undo_restores_exact_bytes(actions):
    service, commands, root = actions
    original = b'{"type":"mech","health":123}\n'
    target = put(root, "content/units/same.json", original)
    other = put(root, "content/blocks/same.json", {"type": "Wall"})
    sprite = put(root, "sprites/units/same.png", b"keep sprite")
    result = service.delete("content/units/same.json")
    assert result.before_path == "content/units/same.json"
    assert result.after_path is None
    assert not target.exists()
    assert other.exists() and sprite.exists()
    commands.undo()
    assert target.read_bytes() == original
    commands.redo()
    assert not target.exists()


def test_catalogue_exposes_real_templates_and_rejects_mismatched_category(actions):
    service, commands, root = actions
    catalogue = service.catalogue()
    assert catalogue["namePattern"] == "[a-z0-9-]+"
    assert {entry["id"] for entry in catalogue["categories"]} == {"units", "blocks", "weapons"}
    assert any(item["kind"] == "GenericCrafter" and item["label"] == "工厂"
               for entry in catalogue["categories"] for item in entry["templates"])
    for entry in catalogue["categories"]:
        for item in entry["templates"]:
            service.create(item["kind"], item["kind"].lower().replace("unittype", "unit"), entry["id"])
    with pytest.raises(ValueError):
        service.create("Weapon", "wrong", "units")
    assert not (root / "content/units/wrong.json").exists()


@pytest.mark.parametrize("name", ["", "../escape", "a/b", "a\\b", "Bad", "bad name", "x\n", "con", "nul", "lpt1"])
def test_invalid_names_never_write_or_enter_history(actions, name):
    service, commands, root = actions
    with pytest.raises(ValueError):
        service.create("Weapon", name, "weapons")
    assert not commands.can_undo
    assert not (root / "content").exists()


def test_locked_source_rolls_back_new_json_and_every_sprite(actions, monkeypatch):
    service, commands, root = actions
    original = put(root, "content/units/old.json", {"type": "mech", "name": "原名"})
    original_bytes = original.read_bytes()
    put(root, "sprites/units/old.png", b"main")
    put(root, "sprites/units/old-cell.png", b"cell")
    unlink = Path.unlink

    def locked(path, *args, **kwargs):
        if path == original:
            raise PermissionError("source in use")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked)
    with pytest.raises(PermissionError):
        service.rename("content/units/old.json", "new")
    assert original.read_bytes() == original_bytes
    assert not (root / "content/units/new.json").exists()
    assert (root / "sprites/units/old.png").read_bytes() == b"main"
    assert (root / "sprites/units/old-cell.png").read_bytes() == b"cell"
    assert not list((root / "sprites/units").glob("new*"))
    assert not list(root.rglob("*.tmp"))
    assert not commands.can_undo


def test_identity_callback_failure_rolls_back_files_and_receives_inverse(actions):
    service, commands, root = actions
    original = put(root, "content/units/old.json", {"type": "mech"})
    identity = {"path": "content/units/old.json"}
    events = []

    def update(change, undo):
        events.append(undo)
        identity["path"] = change.before_path if undo else change.after_path
        if not undo:
            raise RuntimeError("identity callback failed")

    service.on_change = update
    with pytest.raises(RuntimeError, match="identity callback"):
        service.rename("content/units/old.json", "new")
    assert original.exists()
    assert not (root / "content/units/new.json").exists()
    assert identity["path"] == "content/units/old.json"
    assert events == [False, True]
    assert not commands.can_undo


def test_external_edit_blocks_undo_without_overwriting_file(actions):
    service, commands, root = actions
    service.create("Weapon", "gun", "weapons")
    target = put(root, "content/weapons/gun.json", b'{"type":"Weapon","external":true}')
    with pytest.raises(ValueError, match="文件已被其他操作修改"):
        commands.undo()
    assert target.read_bytes() == b'{"type":"Weapon","external":true}'
    assert commands.can_undo
    assert not commands.can_redo


@pytest.mark.parametrize("path", ["../outside.json", "content/units/../blocks/a.json", "content//units/a.json",
    "content\\units\\a.json", "content/units/a.json/extra", "content/units/a.json:stream", "mod.json", "content/units/a.hjson"])
def test_invalid_paths_do_not_change_existing_files(actions, path):
    service, commands, root = actions
    original = put(root, "content/units/a.json", {"type": "mech"})
    for action in (service.delete, service.reveal_path, lambda value: service.rename(value, "b")):
        with pytest.raises(ValueError):
            action(path)
    assert original.exists()
    assert not commands.can_undo


def test_overwrite_requires_boolean_confirmation_and_undo_restores_original(actions):
    service, commands, root = actions
    original = b'{"type":"Weapon","reload":23}\n'
    target = put(root, "content/weapons/gun.json", original)
    with pytest.raises(FileExistsError):
        service.create("Weapon", "gun", "weapons")
    with pytest.raises(ValueError):
        service.create("Weapon", "gun", "weapons", overwrite="false")
    assert target.read_bytes() == original
    assert not commands.can_undo
    service.create("Weapon", "gun", "weapons", overwrite=True)
    assert target.read_bytes() != original
    commands.undo()
    assert target.read_bytes() == original


@pytest.mark.parametrize("conflict", ["content/units/new.json", "sprites/units/new-cell.png"])
def test_rename_conflict_does_not_partially_write(actions, conflict):
    service, commands, root = actions
    original = put(root, "content/units/old.json", {"type": "mech"})
    sprite = put(root, "sprites/units/old-cell.png", b"original")
    target = put(root, conflict, b"conflict")
    with pytest.raises(FileExistsError):
        service.rename("content/units/old.json", "new")
    assert original.exists() and sprite.read_bytes() == b"original"
    assert target.read_bytes() == b"conflict"
    assert not commands.can_undo


def test_confirmed_overwrite_can_replace_invalid_json_and_undo_restores_it(actions):
    service, commands, root = actions
    target = put(root, "content/units/broken.json", b'{"broken":')
    service.create("UnitType", "broken", "units", overwrite=True)
    assert json.loads(target.read_text("utf-8"))["type"] == "mech"
    commands.undo()
    assert target.read_bytes() == b'{"broken":'


def test_delete_can_remove_invalid_content_without_destroying_undo_bytes(actions):
    service, commands, root = actions
    target = put(root, "content/units/broken.json", b'{"broken":')
    service.delete("content/units/broken.json")
    assert not target.exists()
    commands.undo()
    assert target.read_bytes() == b'{"broken":'


def test_noop_rename_and_reveal_do_not_add_history(actions):
    service, commands, root = actions
    target = put(root, "content/units/scout.json", {"type": "mech"})
    result = service.rename("content/units/scout.json", "scout")
    assert result.before_path == result.after_path == "content/units/scout.json"
    assert service.reveal_path("content/units/scout.json") == target
    assert not commands.can_undo


def test_acknowledged_save_after_create_can_be_undone(actions):
    service, commands, root = actions
    service.create("Weapon", "gun", "weapons")
    service.project.contents.save("gun", {"type": "Weapon", "reload": 99}, "weapons")
    service.saved("content/weapons/gun.json")
    commands.undo()
    assert not (root / "content/weapons/gun.json").exists()
    commands.redo()
    assert json.loads((root / "content/weapons/gun.json").read_text("utf-8"))["type"] == "Weapon"


def test_rename_edit_save_undo_edit_undo_rename_preserves_shared_data_identity(actions):
    service, commands, root = actions
    original = b'{"type":"mech","name":"old","health":100}\n'
    put(root, "content/units/old.json", original)
    content = service.project.contents.get_by_path("units/old.json")
    shared_data = content.data

    def identity(change, undo):
        relative = change.before_path if undo else change.after_path
        content.name = Path(relative).stem
        content.path = root / relative
        content.data.clear()
        content.data.update(change.before_data if undo else change.after_data)

    service.on_change = identity
    service.rename("content/units/old.json", "new")
    commands.execute(SetFieldCommand(content.data, "health", 250))
    service.project.contents.save(content.name, content.data, content.category)
    service.saved("content/units/new.json")
    commands.undo()
    assert content.data["health"] == 100
    commands.undo()
    assert content.name == "old"
    assert content.data is shared_data
    assert content.data == {"type": "mech", "name": "old", "health": 100}
    assert (root / "content/units/old.json").read_bytes() == original
    assert not (root / "content/units/new.json").exists()
    commands.redo()
    commands.redo()
    assert content.data is shared_data
    assert content.name == "new" and content.data["health"] == 250


def test_external_write_after_acknowledged_save_still_blocks_undo(actions):
    service, commands, root = actions
    service.create("Weapon", "gun", "weapons")
    service.project.contents.save("gun", {"type": "Weapon", "reload": 99}, "weapons")
    service.saved("content/weapons/gun.json")
    target = put(root, "content/weapons/gun.json", b'{"external":true}')
    with pytest.raises(ValueError):
        commands.undo()
    assert target.read_bytes() == b'{"external":true}'
    assert commands.can_undo


def test_new_project_uses_old_layout_and_undo_redo_only_its_new_directory(tmp_path):
    from app.desktop.content_actions import create_project

    commands = CommandStack()
    events = []
    project = create_project(tmp_path, "new-mod", "新模组", commands, author="作者",
                             on_change=lambda project, undo: events.append((project.root.name, undo)))
    assert project.root == tmp_path / "new-mod"
    assert json.loads((project.root / "mod.json").read_text("utf-8")) == {
        "name": "new-mod", "displayName": "新模组", "author": "作者", "description": "",
        "version": "1.0", "minGameVersion": "146",
    }
    assert (project.root / "content/units").is_dir()
    assert (project.root / "content/blocks").is_dir()
    assert (project.root / "content/weapons").is_dir()
    assert (project.root / "sprites/units").is_dir()
    assert not (project.root / ".moma").exists()
    commands.undo()
    assert not project.root.exists()
    commands.redo()
    assert (project.root / "mod.json").is_file()
    assert events == [("new-mod", False), ("new-mod", True), ("new-mod", False)]


def test_new_project_rejects_existing_directory_and_preserves_untracked_files(tmp_path):
    from app.desktop.content_actions import create_project

    commands = CommandStack()
    (tmp_path / "existing").mkdir()
    with pytest.raises(FileExistsError):
        create_project(tmp_path, "existing", "existing", commands)
    assert not commands.can_undo
    project = create_project(tmp_path, "fresh", "fresh", commands)
    extra = put(project.root, "content/units/external.json", {"type": "mech"})
    with pytest.raises(ValueError):
        commands.undo()
    assert extra.exists()
    assert commands.can_undo


def test_new_project_failure_cleans_only_created_items(tmp_path, monkeypatch):
    from app.desktop.content_actions import create_project

    commands = CommandStack()
    sibling = put(tmp_path, "sibling.txt", b"untouched")
    mkdir = Path.mkdir

    def fail_one(path, *args, **kwargs):
        if path.name == "weapons":
            raise PermissionError("directory unavailable")
        return mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_one)
    with pytest.raises(PermissionError):
        create_project(tmp_path, "fresh", "fresh", commands)
    assert sibling.read_bytes() == b"untouched"
    assert not (tmp_path / "fresh").exists()
    assert not commands.can_undo


@pytest.mark.skipif(os.name != "nt", reason="Windows 文件占用语义")
def test_real_windows_locked_source_keeps_files_and_history(actions):
    import ctypes
    from ctypes import wintypes

    service, commands, root = actions
    source = put(root, "content/units/old.json", {"type": "mech"})
    put(root, "sprites/units/old.png", b"sprite")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(source), 0x80000000, 1, None, 3, 0x80, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        with pytest.raises(PermissionError):
            service.rename("content/units/old.json", "new")
        assert source.exists()
        assert not (root / "content/units/new.json").exists()
        assert (root / "sprites/units/old.png").read_bytes() == b"sprite"
        assert not (root / "sprites/units/new.png").exists()
        assert not commands.can_undo
    finally:
        kernel.CloseHandle(handle)


def test_project_link_cannot_target_content_outside_project(actions, tmp_path):
    service, commands, root = actions
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    original = put(outside, "old.json", {"type": "mech"})
    (root / "content").mkdir()
    try:
        (root / "content/units").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"当前系统不允许创建测试符号链接：{exc}")
    for action in (service.delete, service.reveal_path, lambda path: service.rename(path, "new")):
        with pytest.raises(ValueError):
            action("content/units/old.json")
    assert original.exists()
    assert not commands.can_undo


def test_failed_undo_after_acknowledged_save_restores_latest_disk_bytes(actions):
    service, commands, root = actions

    def callback(change, undo):
        if undo:
            raise RuntimeError("cannot detach identity")

    service.on_change = callback
    service.create("Weapon", "gun", "weapons")
    target = put(root, "content/weapons/gun.json", b'{"type":"Weapon","reload":99}')
    service.saved("content/weapons/gun.json")
    with pytest.raises(RuntimeError):
        commands.undo()
    assert target.read_bytes() == b'{"type":"Weapon","reload":99}'
    assert commands.can_undo


@pytest.mark.parametrize("fail_undo", [False, True])
def test_new_project_callback_failure_restores_files_and_identity(tmp_path, fail_undo):
    from app.desktop.content_actions import create_project

    commands = CommandStack()
    attached = []

    def callback(project, undo):
        attached[:] = [] if undo else [project.root]
        if undo == fail_undo:
            raise RuntimeError("identity callback failed")

    if not fail_undo:
        with pytest.raises(RuntimeError):
            create_project(tmp_path, "fresh", "fresh", commands, on_change=callback)
        assert attached == []
        assert not (tmp_path / "fresh").exists()
        assert not commands.can_undo
    else:
        project = create_project(tmp_path, "fresh", "fresh", commands, on_change=callback)
        with pytest.raises(RuntimeError):
            commands.undo()
        assert attached == [project.root]
        assert (project.root / "mod.json").is_file()
        assert (project.root / "content/units").is_dir()
        assert commands.can_undo
