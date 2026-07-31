"""Tests for app.core.session — ProjectSession lifecycle, headless (no Qt).

Proves the deep module can be driven without a QApplication: project
open/create/close, content creation, and save-with-validation all run
through one small interface.
"""

import json
import pytest
from pathlib import Path

from app.core.session import ProjectSession, SaveReport
from app.core.content_store import ContentData

METADATA_DIR = Path(__file__).parent.parent / "metadata"

pytestmark = pytest.mark.skipif(
    not METADATA_DIR.exists(),
    reason="metadata/ directory not found — run the extractor first",
)


@pytest.fixture
def session():
    return ProjectSession(METADATA_DIR)


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal mod project on disk."""
    root = tmp_path / "my-mod"
    (root / "content" / "units").mkdir(parents=True)
    (root / "content" / "blocks").mkdir(parents=True)
    (root / "content" / "weapons").mkdir(parents=True)
    (root / "mod.json").write_text(
        json.dumps({"name": "my-mod", "displayName": "My Mod"}), encoding="utf-8"
    )
    return root


# ── service accessors ──────────────────────────────────────────────────


class TestAccessors:
    def test_metadata_available(self, session):
        assert session.metadata.game_version == "159"

    def test_validator_available(self, session):
        assert session.validator is not None

    def test_command_stack_available(self, session):
        assert session.command_stack is not None

    def test_project_none_initially(self, session):
        assert session.project is None


# ── project lifecycle ──────────────────────────────────────────────────


class TestLifecycle:
    def test_open_project(self, session, project_dir):
        project = session.open_project(project_dir)
        assert project.mod_info.name == "my-mod"
        assert session.project is project

    def test_open_missing_raises(self, session, tmp_path):
        with pytest.raises(FileNotFoundError):
            session.open_project(tmp_path / "does-not-exist")

    def test_create_project(self, session, tmp_path):
        project = session.create_project(tmp_path, "new-mod", "New Mod", "me")
        assert project.mod_info.name == "new-mod"
        assert (tmp_path / "new-mod" / "mod.json").exists()
        assert session.project is project

    def test_close_project(self, session, project_dir):
        session.open_project(project_dir)
        session.close_project()
        assert session.project is None


# ── content creation ───────────────────────────────────────────────────


class TestCreateContent:
    def test_create_unit(self, session, project_dir):
        session.open_project(project_dir)
        session.create_content("UnitType", "my-unit", "units")
        path = project_dir / "content" / "units" / "my-unit.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["type"] == "UnitType"

    def test_create_without_project_raises(self, session):
        with pytest.raises(RuntimeError, match="No project open"):
            session.create_content("UnitType", "x", "units")

    def test_content_exists(self, session, project_dir):
        session.open_project(project_dir)
        session.create_content("UnitType", "my-unit", "units")
        assert session.content_exists("my-unit")
        assert not session.content_exists("other-unit")

    def test_content_exists_without_project(self, session):
        assert not session.content_exists("whatever")


# ── save with validation ───────────────────────────────────────────────


class TestSaveContents:
    def test_save_valid_content(self, session, project_dir):
        session.open_project(project_dir)
        content = ContentData(
            name="wall", category="blocks",
            data={"type": "Wall", "name": "wall", "health": 100},
        )
        report = session.save_contents([content])
        assert report.error_count == 0
        assert report.first_error_content is None
        assert (project_dir / "content" / "blocks" / "wall.json").exists()

    def test_save_reports_errors(self, session, project_dir):
        session.open_project(project_dir)
        content = ContentData(
            name="bad", category="blocks",
            data={"type": "Wall", "name": "bad", "health": "not-a-number"},
        )
        report = session.save_contents([content])
        assert report.error_count > 0
        assert report.first_error_content == "bad"

    def test_save_first_error_content_is_first(self, session, project_dir):
        session.open_project(project_dir)
        good = ContentData(
            name="good", category="blocks",
            data={"type": "Wall", "name": "good", "health": 100},
        )
        bad = ContentData(
            name="bad", category="blocks",
            data={"type": "Wall", "name": "bad", "health": "x"},
        )
        report = session.save_contents([good, bad])
        assert report.first_error_content == "bad"

    def test_save_without_project_returns_empty_report(self, session):
        report = session.save_contents([])
        assert report == SaveReport()


# ── undo / redo ────────────────────────────────────────────────────────


class TestUndoRedo:
    def test_undo_redo_delegates_to_stack(self, session):
        from app.core.commands import SetFieldCommand
        data = {"health": 100}
        session.command_stack.execute(
            SetFieldCommand(data=data, path="health", new_value=200)
        )
        assert data["health"] == 200
        session.undo()
        assert data["health"] == 100
        session.redo()
        assert data["health"] == 200
