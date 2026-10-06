"""Current core validation and existing-format exports, without a GUI."""

from copy import deepcopy
import json
from pathlib import Path
import zipfile

import pytest

from app.core.session import ProjectSession
from app.desktop.editing import EditingError, EditingService
from app.desktop.source_editing import RawDocument
from app.desktop.validation_export import ValidationExportService


PATH = "content/blocks/same.json"


def _same_directory(candidate, expected: Path) -> bool:
    """Compare a directory argument (str/bytes/Path/fd) against an expected path."""
    if isinstance(candidate, int):
        return False
    try:
        return Path(candidate) == expected
    except (TypeError, ValueError, OSError):
        return False


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "mod"
    (root / "content/blocks").mkdir(parents=True)
    (root / "content/units").mkdir(parents=True)
    (root / "mod.json").write_text('{"name":"validation-mod"}', encoding="utf-8")
    (root / PATH).write_text('{"type":"Wall","name":"same","health":123}', encoding="utf-8")
    (root / "content/units/same.json").write_text('{"type":"UnitType","name":"same","speed":2}', encoding="utf-8")
    session = ProjectSession("metadata")
    session.open_project(root)
    editing = EditingService(session, "session-validation")
    editing.opened(PATH, session.read_content("blocks/same.json"))
    return root, session, editing


def test_validate_uses_current_core_values_exact_paths_without_saving_or_opening_tabs(setup):
    root, session, editing = setup
    before_disk = (root / PATH).read_bytes()
    editing.set_source({"path": PATH, "text": '{"type":"Wall","name":"same","health":"bad"}',
                        "expectedRevision": editing.revision})
    before = editing.state()
    service = ValidationExportService(session, "session-validation", editing, None)
    report = service.validate({"expectedRevision": editing.revision})
    assert report["sessionId"] == "session-validation" and report["revision"] == editing.revision
    assert report["complete"]
    issue = next(issue for issue in report["issues"] if issue["field"] == "health")
    assert issue["path"] == PATH and issue["severity"] == "error" and issue["target"] == "form"
    assert any(issue["path"] == "content/units/same.json" for issue in report["issues"])
    assert editing.state() == before and (root / PATH).read_bytes() == before_disk
    assert session.loaded_content("units/same.json") is None


def test_export_saves_current_content_and_keeps_business_errors_as_report(setup, tmp_path):
    root, session, editing = setup
    editing.set_source({"path": PATH, "text": '{"type":"Wall","name":"same","health":"unfinished"}',
                        "expectedRevision": editing.revision})
    selected = []
    target = root / "release.zip"
    target.write_bytes(b"old export")

    def choose(name):
        selected.append(name)
        assert json.loads((root / PATH).read_text(encoding="utf-8"))["health"] == "unfinished"
        return str(target)

    service = ValidationExportService(session, "session-validation", editing, choose)
    result = service.export({"expectedRevision": editing.revision})
    assert result["exported"] and not result["cancelled"] and result["report"]["errors"] > 0
    assert result["state"] == editing.state() and not result["state"]["documents"][0]["dirty"]
    assert result["output"]["path"] == str(target) and result["output"]["bytes"] == target.stat().st_size
    assert selected == ["validation-mod.zip"]
    with zipfile.ZipFile(target) as archive:
        assert json.loads(archive.read(PATH))["health"] == "unfinished"
        assert "release.zip" not in archive.namelist()
        assert "mod.json" in archive.namelist()


@pytest.mark.parametrize("text", ['{broken', '[]', '{"name":"probe","bad":NaN}'])
def test_invalid_mod_json_is_reported_and_blocks_export_without_choosing(setup, text):
    root, session, editing = setup
    (root / "mod.json").write_text(text, encoding="utf-8")
    selections = []
    service = ValidationExportService(session, "session-validation", editing, lambda name: selections.append(name))
    report = service.validate({"expectedRevision": editing.revision})
    assert any(issue["path"] == "mod.json" and issue["origin"] == "source" for issue in report["issues"])
    with pytest.raises(EditingError) as caught:
        service.export({"expectedRevision": editing.revision})
    assert caught.value.code == "SOURCE_INVALID" and selections == []


def test_cancel_returns_saved_state_and_does_not_produce_archive(setup):
    root, session, editing = setup
    editing.set_field({"path": PATH, "field": "health", "text": "245", "expectedRevision": editing.revision})
    service = ValidationExportService(session, "session-validation", editing, lambda _name: None)
    result = service.export({"expectedRevision": editing.revision})
    assert result["cancelled"] and not result["exported"] and "output" not in result
    assert result["state"] == editing.state() and result["revision"] == editing.revision
    assert json.loads((root / PATH).read_text(encoding="utf-8"))["health"] == 245
    assert not list(root.rglob("*.zip"))


def test_raw_memory_takes_priority_over_repaired_disk_and_blocks_export(setup):
    root, session, editing = setup
    raw_path = "content/units/raw.json"
    target = root / raw_path
    target.write_text('{\n"type":\n}', encoding="utf-8")
    raw = RawDocument("raw", "units", target, '{\n"type":\n}', {"message": "第 3 行第 1 列：JSON 语法无效。", "line": 3, "column": 1})
    editing.opened(raw_path, raw)
    target.write_text('{"type":"UnitType","name":"raw"}', encoding="utf-8")
    choices = []
    service = ValidationExportService(session, "session-validation", editing, lambda name: choices.append(name))
    before = editing.state()
    report = service.validate({"expectedRevision": editing.revision})
    issue = next(row for row in report["issues"] if row["path"] == raw_path)
    assert issue["origin"] == "source" and issue["target"] == "source" and issue["line"] == 3
    assert editing.state() == before
    with pytest.raises(EditingError) as caught:
        service.export({"expectedRevision": editing.revision})
    assert caught.value.code == "SOURCE_INVALID" and choices == [] and editing.state() == before


def test_closed_registered_data_and_deleted_disk_remain_in_current_validation(setup):
    root, session, editing = setup
    editing.set_source({"path": PATH, "text": '{"type":"Wall","name":"same","health":"bad"}',
                        "expectedRevision": editing.revision})
    editing.close({"paths": [PATH], "decision": "save", "expectedRevision": editing.revision})
    (root / PATH).unlink()
    assert editing.state()["documents"] == []
    service = ValidationExportService(session, "session-validation", editing, None)
    report = service.validate({"expectedRevision": editing.revision})
    assert any(row["path"] == PATH and row["field"] == "health" for row in report["issues"])
    assert editing.state()["documents"] == [] and not (root / PATH).exists()


def test_save_failure_prevents_selector_and_keeps_existing_target(setup, tmp_path, monkeypatch):
    root, session, editing = setup
    editing.set_field({"path": PATH, "field": "health", "text": "222", "expectedRevision": editing.revision})
    target = tmp_path / "result.zip"
    target.write_bytes(b"previous good export")
    choices = []

    def fail_save(_content):
        raise OSError("文件占用")

    monkeypatch.setattr(session, "save_content", fail_save)
    service = ValidationExportService(session, "session-validation", editing, lambda name: choices.append(name) or str(target))
    with pytest.raises(EditingError) as caught:
        service.export({"expectedRevision": editing.revision})
    assert caught.value.code == "SAVE_FAILED" and choices == []
    assert target.read_bytes() == b"previous good export" and editing.has_dirty()


@pytest.mark.parametrize("stage", ["write", "replace"])
def test_export_io_failure_preserves_old_target_and_removes_temporary_file(setup, tmp_path, monkeypatch, stage):
    root, session, editing = setup
    target = tmp_path / "output.zip"
    target.write_bytes(b"old export")
    if stage == "write":
        def fail_write(destination, **_kwargs):
            Path(destination).write_bytes(b"partial")
            raise OSError("打包时磁盘已满")
        monkeypatch.setattr(session.project, "export_zip", fail_write)
    else:
        def fail_replace(*_args):
            raise PermissionError("目标被占用")
        monkeypatch.setattr("app.desktop.validation_export.os.replace", fail_replace)
    service = ValidationExportService(session, "session-validation", editing, lambda _name: str(target))
    with pytest.raises(EditingError) as caught:
        service.export({"expectedRevision": editing.revision})
    assert caught.value.code == "EXPORT_FAILED"
    assert target.read_bytes() == b"old export" and not list(tmp_path.glob(".moma-export-*"))


def test_unopened_bad_content_blocks_export_and_scan_failure_does_not_claim_success(setup, monkeypatch):
    root, session, editing = setup
    (root / "content/units/same.json").write_text('[null]', encoding="utf-8")
    selections = []
    service = ValidationExportService(session, "session-validation", editing, lambda name: selections.append(name))
    with pytest.raises(EditingError) as caught:
        service.export({"expectedRevision": editing.revision})
    assert caught.value.code == "SOURCE_INVALID" and not selections
    read = service._read_json
    def unreadable(path):
        if path.startswith("content/"):
            raise PermissionError("文件不可读")
        return read(path)
    monkeypatch.setattr(service, "_read_json", unreadable)
    with pytest.raises(EditingError) as caught:
        service.validate({"expectedRevision": editing.revision})
    assert caught.value.code == "VALIDATION_FAILED"


@pytest.mark.parametrize("payload", [{}, {"expectedRevision": -1}, {"expectedRevision": 1, "path": "C:/other.zip"}])
def test_invalid_request_or_revision_does_not_save_or_open_picker(setup, payload):
    root, session, editing = setup
    before = editing.state()
    picks = []
    service = ValidationExportService(session, "session-validation", editing, lambda name: picks.append(name))
    for method in (service.validate, service.export):
        with pytest.raises(EditingError):
            method(payload)
    assert editing.state() == before and not picks


def test_stale_service_is_rejected_before_any_operation(setup):
    _, session, editing = setup
    service = ValidationExportService(session, "old-session", editing, None)
    with pytest.raises(EditingError) as caught:
        service.validate({"expectedRevision": editing.revision})
    assert caught.value.code == "STALE_SESSION"


def test_invalid_json_introduced_while_picker_open_does_not_replace_existing_archive(setup, tmp_path):
    root, session, editing = setup
    target = tmp_path / "output.zip"
    target.write_bytes(b"previous export")
    def choose(_name):
        (root / PATH).write_text('{broken', encoding="utf-8")
        return str(target)
    service = ValidationExportService(session, "session-validation", editing, choose)
    with pytest.raises(EditingError) as caught:
        service.export({"expectedRevision": editing.revision})
    assert caught.value.code == "SOURCE_INVALID" and target.read_bytes() == b"previous export"
    assert not list(tmp_path.glob(".moma-export-*"))


@pytest.mark.parametrize("selected", ["relative.zip", "C:/wrong.json", "", "C:/nul\x00.zip"])
def test_invalid_native_destination_is_rejected_after_save_without_zip(setup, selected):
    root, session, editing = setup
    service = ValidationExportService(session, "session-validation", editing, lambda _name: selected)
    with pytest.raises(EditingError) as caught:
        service.export({"expectedRevision": editing.revision})
    assert caught.value.code == "EXPORT_FAILED" and not list(root.rglob("*.zip"))


def test_unwritable_destination_parent_is_recoverable(setup, tmp_path):
    _, session, editing = setup
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("keep", encoding="utf-8")
    service = ValidationExportService(session, "session-validation", editing,
                                       lambda _name: str(blocked_parent / "output.zip"))
    with pytest.raises(EditingError) as caught:
        service.export({"expectedRevision": editing.revision})
    assert caught.value.code == "EXPORT_FAILED" and blocked_parent.read_text(encoding="utf-8") == "keep"


def test_actual_external_symlink_content_is_rejected_without_reading_external_data(setup, tmp_path):
    root, session, editing = setup
    external = tmp_path / "external.json"
    external.write_text('{"type":"UnitType","name":"secret"}', encoding="utf-8")
    link = root / "content/units/external.json"
    try:
        link.symlink_to(external)
    except OSError as error:
        pytest.skip(f"此 Windows 环境不允许创建测试符号链接：{error}")
    service = ValidationExportService(session, "session-validation", editing, None)
    with pytest.raises(EditingError) as caught:
        service.validate({"expectedRevision": editing.revision})
    assert caught.value.code == "VALIDATION_FAILED"


def test_external_export_asset_symlink_keeps_previous_archive(setup, tmp_path):
    root, session, editing = setup
    external = tmp_path / "outside.txt"
    external.write_bytes(b"do not export")
    link = root / "notes.txt"
    try:
        link.symlink_to(external)
    except OSError as error:
        pytest.skip(f"此 Windows 环境不允许创建测试符号链接：{error}")
    target = tmp_path / "out.zip"
    target.write_bytes(b"old archive")
    service = ValidationExportService(session, "session-validation", editing, lambda _name: str(target))
    with pytest.raises(EditingError) as caught:
        service.export({"expectedRevision": editing.revision})
    assert caught.value.code == "EXPORT_FAILED" and target.read_bytes() == b"old archive"


def test_export_bytes_match_legacy_core_output_for_normal_project(setup, tmp_path):
    root, session, editing = setup
    (root / "scripts").mkdir()
    (root / "scripts/main.js").write_text("// known legacy asset", encoding="utf-8")
    (root / ".custom").mkdir()
    (root / ".custom/keep.txt").write_text("legacy keeps nonstandard hidden directories", encoding="utf-8")
    (root / "content/weapons").mkdir()
    (root / "content/weapons/legacy.json").write_text('{"type":"Weapon","bullet":{"damage":12}}', encoding="utf-8")
    target = tmp_path / "new.zip"
    result = ValidationExportService(session, "session-validation", editing,
                                     lambda _name: str(target)).export({"expectedRevision": editing.revision})
    legacy = tmp_path / "legacy.zip"
    session.project.export_zip(legacy)
    with zipfile.ZipFile(target) as actual, zipfile.ZipFile(legacy) as baseline:
        assert actual.namelist() == baseline.namelist()
        assert {name: actual.read(name) for name in actual.namelist()} == {name: baseline.read(name) for name in baseline.namelist()}
        assert "content/weapons/legacy.json" in actual.namelist()
        assert ".custom/keep.txt" in actual.namelist()
    assert result["exported"]


def test_missing_mod_json_or_unreadable_encoding_is_validation_failure(setup):
    root, session, editing = setup
    service = ValidationExportService(session, "session-validation", editing, None)
    (root / "content/units/same.json").write_bytes(b"\xff\xfe")
    with pytest.raises(EditingError) as caught:
        service.validate({"expectedRevision": editing.revision})
    assert caught.value.code == "VALIDATION_FAILED"
    (root / "mod.json").unlink()
    with pytest.raises(EditingError) as caught:
        service.validate({"expectedRevision": editing.revision})
    assert caught.value.code == "VALIDATION_FAILED"


def test_cleanup_failure_is_explicit_and_original_archive_is_unchanged(setup, tmp_path, monkeypatch):
    _, session, editing = setup
    target = tmp_path / "result.zip"
    target.write_bytes(b"keep old")
    original_unlink = Path.unlink
    def fail_unlink(path, *args, **kwargs):
        if path.name.startswith(".moma-export-"):
            raise PermissionError("临时文件占用")
        return original_unlink(path, *args, **kwargs)
    def fail_export(destination, **_kwargs):
        raise OSError("打包失败")
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    monkeypatch.setattr(session.project, "export_zip", fail_export)
    service = ValidationExportService(session, "session-validation", editing, lambda _name: str(target))
    with pytest.raises(EditingError) as caught:
        service.export({"expectedRevision": editing.revision})
    assert caught.value.code == "EXPORT_FAILED" and "临时文件" in str(caught.value)
    assert target.read_bytes() == b"keep old"
    leftovers = list(tmp_path.glob(".moma-export-*"))
    assert len(leftovers) == 1
    for leftover in leftovers:
        original_unlink(leftover)


def test_unreadable_content_category_cannot_disappear_from_validation(setup, monkeypatch):
    import os

    root, session, editing = setup
    denied = (root / "content/units").resolve()
    # Path.iterdir() delegates to os.listdir() before Python 3.12 and to
    # os.scandir() from 3.12 on, so patching only one leaves the simulated
    # unreadable directory invisible on the other (CI runs 3.11). Patch both:
    # a real unreadable directory raises from whichever primitive it uses.
    listdir = os.listdir
    scandir = os.scandir
    def failing_listdir(path="."):
        if _same_directory(path, denied):
            raise PermissionError("单位目录不可读")
        return listdir(path)
    def failing_scandir(path="."):
        if _same_directory(path, denied):
            raise PermissionError("单位目录不可读")
        return scandir(path)
    monkeypatch.setattr(os, "listdir", failing_listdir)
    monkeypatch.setattr(os, "scandir", failing_scandir)
    service = ValidationExportService(session, "session-validation", editing, None)
    with pytest.raises(EditingError) as caught:
        service.validate({"expectedRevision": editing.revision})
    assert caught.value.code == "VALIDATION_FAILED"


@pytest.mark.parametrize("operation", ["validate", "export"])
def test_source_swapped_to_external_link_at_actual_open_is_rejected(setup, tmp_path, monkeypatch, operation):
    import builtins
    import io
    import os

    root, session, editing = setup
    inside = root / ("content/units/same.json" if operation == "validate" else "notes.txt")
    inside.write_text('{"type":"UnitType"}' if operation == "validate" else "project asset", encoding="utf-8")
    external = tmp_path / "external.json"
    external.write_text('{"type":"UnitType","weapons":[{"name":"EXTERNAL_TEST_MARKER"}]}', encoding="utf-8")
    permission_probe = tmp_path / "link-permission-probe"
    try:
        permission_probe.symlink_to(external)
        permission_probe.unlink()
    except OSError as error:
        pytest.skip(f"此环境不能创建符号链接：{error}")
    target = tmp_path / "previous.zip"
    target.write_bytes(b"old verified archive")
    attacked = []
    def wrap(opener):
        def race(path, mode="r", *args, **kwargs):
            if not attacked and not isinstance(path, int) and Path(path) == inside and mode == "rb":
                attacked.append(True)
                inside.unlink()
                inside.symlink_to(external)
            return opener(path, mode, *args, **kwargs)
        return race
    monkeypatch.setattr(builtins, "open", wrap(builtins.open))
    monkeypatch.setattr(io, "open", wrap(io.open))
    original_os_open = os.open
    def race_os_open(path, flags, *args, **kwargs):
        if not attacked and Path(path) == inside:
            attacked.append(True)
            inside.unlink()
            inside.symlink_to(external)
        return original_os_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(os, "open", race_os_open)
    service = ValidationExportService(session, "session-validation", editing, lambda _name: str(target))
    with pytest.raises(EditingError) as caught:
        getattr(service, operation)({"expectedRevision": editing.revision})
    assert attacked
    assert caught.value.code == ("VALIDATION_FAILED" if operation == "validate" else "EXPORT_FAILED")
    assert target.read_bytes() == b"old verified archive"
    assert not list(tmp_path.glob(".moma-export-*"))
