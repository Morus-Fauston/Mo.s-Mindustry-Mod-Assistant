"""Core-only ownership checks used by source repair commands."""

from pathlib import Path

import pytest

from app.core.content_store import ContentData
from app.core.session import ProjectSession


@pytest.fixture
def session(tmp_path):
    (tmp_path / "content/blocks").mkdir(parents=True)
    (tmp_path / "mod.json").write_text('{"name":"probe"}', encoding="utf-8")
    (tmp_path / "content/blocks/wall.json").write_text('{broken}', encoding="utf-8")
    current = ProjectSession("metadata")
    current.open_project(tmp_path)
    return current


def content(session):
    return ContentData("wall", "blocks", {"type": "Wall", "health": 371},
                       (session.project.root / "content/blocks/wall.json").resolve())


def test_attach_detach_preserve_exact_object_and_save_requires_current_ownership(session):
    real = content(session)
    session.attach_content("blocks/wall.json", real)
    assert session.read_content("blocks/wall.json") is real
    session.attach_content("blocks/wall.json", real)
    with pytest.raises(ValueError):
        session.attach_content("blocks/wall.json", content(session))
    with pytest.raises(ValueError):
        session.detach_content("blocks/wall.json", content(session))
    session.detach_content("blocks/wall.json", real)
    with pytest.raises(ValueError):
        session.save_content(real)
    assert session.loaded_content("blocks/wall.json") is None
    session.attach_content("blocks/wall.json", real)
    assert session.save_content(real) == real.path


@pytest.mark.parametrize("relative", ["../wall.json", "/blocks/wall.json", "blocks/../wall.json",
                                     "blocks\\wall.json", "blocks//wall.json", "blocks/wall.txt", "C:/wall.json"])
def test_attach_rejects_noncanonical_paths(session, relative):
    with pytest.raises(ValueError):
        session.attach_content(relative, content(session))
    assert session.loaded_content("blocks/wall.json") is None


@pytest.mark.parametrize("change", ["name", "category", "data", "path"])
def test_attach_rejects_invalid_identity_without_registering(session, change):
    candidate = content(session)
    setattr(candidate, change, {"name": "other", "category": "units", "data": [],
                                "path": Path("C:/outside.json")}[change])
    with pytest.raises(ValueError):
        session.attach_content("blocks/wall.json", candidate)
    assert session.loaded_content("blocks/wall.json") is None


def test_old_object_cannot_detach_new_session_owner(session, tmp_path):
    old = content(session)
    session.attach_content("blocks/wall.json", old)
    session.open_project(tmp_path)
    new = content(session)
    session.attach_content("blocks/wall.json", new)
    with pytest.raises(ValueError):
        session.detach_content("blocks/wall.json", old)
    assert session.loaded_content("blocks/wall.json") is new
