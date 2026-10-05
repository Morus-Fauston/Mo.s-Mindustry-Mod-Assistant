"""Real OS-handle ownership and lifecycle checks for project reads."""

from pathlib import Path
import os

import pytest

from app.core.project_files import open_project_file


def test_regular_file_is_read_from_checked_handle_and_closed(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    path = root / "asset.txt"
    path.write_bytes(b"project bytes")
    with open_project_file(root, path) as stream:
        assert stream.read() == b"project bytes"
    assert stream.closed
    path.unlink()


def test_internal_file_link_keeps_existing_read_semantics(tmp_path):
    target = tmp_path / "asset.txt"
    target.write_bytes(b"internal bytes")
    link = tmp_path / "alias.txt"
    try:
        link.symlink_to(target)
    except OSError as error:
        pytest.skip(f"此环境不能创建符号链接：{error}")
    with open_project_file(tmp_path, link) as stream:
        assert stream.read() == b"internal bytes"


def test_file_modified_while_reading_fails_and_releases_handle(tmp_path):
    path = tmp_path / "asset.txt"
    path.write_bytes(b"first")
    with pytest.raises(OSError, match="变化"):
        with open_project_file(tmp_path, path) as stream:
            assert stream.read() == b"first"
            path.write_bytes(b"changed length")
    assert stream.closed
    path.unlink()


def test_handle_redirect_cannot_be_hidden_by_unchanged_requested_path(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    path = root / "asset.txt"
    path.write_bytes(b"inside")
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"external marker")
    original_open = os.open
    descriptors = []
    def redirect(candidate, flags, *args, **kwargs):
        descriptor = original_open(outside if Path(candidate) == path else candidate, flags, *args, **kwargs)
        descriptors.append(descriptor)
        return descriptor
    monkeypatch.setattr(os, "open", redirect)
    with pytest.raises(OSError, match="变化"):
        with open_project_file(root, path):
            pytest.fail("外部句柄不得交给调用方读取")
    assert path.read_bytes() == b"inside" and len(descriptors) == 1
    with pytest.raises(OSError):
        os.fstat(descriptors[0])


def test_nonregular_source_is_rejected_before_open(tmp_path):
    with pytest.raises(OSError, match="普通文件"):
        with open_project_file(tmp_path, tmp_path):
            pytest.fail("目录不得当作文件读取")
