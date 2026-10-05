"""Project session: the deep module that owns the editing lifecycle.

Assembles the core services (Metadata, CommandStack, TemplateEngine,
Validator) and concentrates project lifecycle + content creation +
save-with-validation behind a small interface. MainWindow becomes a thin
shell: layout, dialogs, and signal forwarding.

Interface:
    ProjectSession(metadata_dir)
    .metadata / .validator / .command_stack   (read-only, for wiring UI)
    .project                                   (current Project | None)
    open_project(path) -> Project
    create_project(path, mod_id, display_name, author) -> Project
    close_project() -> None
    create_content(kind, name, category) -> None
    save_contents(items) -> SaveReport
    undo() / redo()
    last_project_path() -> str | None
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .commands import CommandStack
from .config_loader import load_editor_state, save_editor_state
from .content_store import ContentData
from .metadata import Metadata
from .project import Project
from .template import TemplateEngine
from .validator import Validator


@dataclass
class SaveReport:
    """Result of saving all open contents."""
    error_count: int = 0
    first_error_content: str | None = None  # name of first content with errors


class ProjectSession:
    """Owns the editing session: services + project lifecycle + persistence.

    One implementation, many call sites: MainWindow drives it from Qt,
    tests drive it headlessly without a QApplication.
    """

    def __init__(self, metadata_dir: Path | str) -> None:
        self._metadata = Metadata(metadata_dir)
        self._command_stack = CommandStack()
        self._template_engine = TemplateEngine(self._metadata)
        self._validator = Validator(self._metadata)
        self._project: Project | None = None
        self._open_contents: dict[str, ContentData] = {}

    # ── read-only accessors (for UI wiring / EditorPanel construction) ──

    @property
    def metadata(self) -> Metadata:
        return self._metadata

    @property
    def validator(self) -> Validator:
        return self._validator

    @property
    def command_stack(self) -> CommandStack:
        return self._command_stack

    @property
    def project(self) -> Project | None:
        return self._project

    # ── project lifecycle ───────────────────────────────────────────────

    def open_project(self, path: str | Path) -> Project:
        """Open an existing project and remember it as the last project."""
        project = Project.open(path)
        self._project = project
        self._remember_project(project)
        self._open_contents.clear()
        return project

    def create_project(
        self, path: str | Path, mod_id: str, display_name: str, author: str = ""
    ) -> Project:
        """Create a new project skeleton and remember it."""
        project = Project.create(path, mod_id, display_name, author)
        self._project = project
        self._remember_project(project)
        self._open_contents.clear()
        return project

    def close_project(self) -> None:
        """Detach the current project (does not touch disk)."""
        self._project = None
        self._open_contents.clear()

    def read_content(self, relative_path: str) -> ContentData:
        """Keep one core-owned document per explicit category/file path."""
        if self._project is None:
            raise RuntimeError("No project open")
        if relative_path not in self._open_contents:
            self._open_contents[relative_path] = self._project.contents.get_by_path(relative_path)
        return self._open_contents[relative_path]

    # ── content creation ────────────────────────────────────────────────

    def content_exists(self, name: str) -> bool:
        """Whether a content file with this name already exists in the project."""
        if self._project is None:
            return False
        return self._project.contents.exists(name)

    def create_content(self, kind: str, name: str, category: str) -> None:
        """Generate a template and write it to disk under category."""
        if self._project is None:
            raise RuntimeError("No project open")
        data = self._template_engine.create(kind, name)
        self._project.contents.save(name, data, category)

    # ── persistence ─────────────────────────────────────────────────────

    def save_contents(self, items: list[ContentData]) -> SaveReport:
        """Save each open content and validate at content level.

        Returns a SaveReport with the total error count and the name of the
        first content that had errors (for UI jump-to-error).
        """
        if self._project is None:
            return SaveReport()

        report = SaveReport()
        for content in items:
            self._project.contents.save(
                content.name, content.data, content.category
            )
            issues = self._validator.validate(content.data, "content")
            errs = [iss for iss in issues if iss.severity == "error"]
            report.error_count += len(errs)
            if errs and report.first_error_content is None:
                report.first_error_content = content.name

        self._project.is_dirty = False
        return report

    def save_content(self, content: ContentData) -> Path:
        """Save one opened document after rechecking its project-local identity."""
        if self._project is None:
            raise ValueError("没有已打开的工程")
        relative = f"{content.category}/{content.name}.json"
        if self._open_contents.get(relative) is not content:
            raise ValueError("内容不属于当前会话")
        root = self._project.root.resolve()
        target = root / "content" / relative
        if not target.resolve().is_relative_to(root) or target.resolve() != content.path:
            raise ValueError("内容路径已变化或超出工程范围")
        if target.exists() and not target.is_file():
            raise ValueError("内容保存目标不是文件")
        return self._project.contents.save(content.name, content.data, content.category)

    def last_project_path(self) -> str | None:
        """Return the last opened project path from persisted state."""
        return load_editor_state().get("last_project") or None

    # ── undo / redo ─────────────────────────────────────────────────────

    def undo(self) -> None:
        self._command_stack.undo()

    def redo(self) -> None:
        self._command_stack.redo()

    # ── helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _remember_project(project: Project) -> None:
        save_editor_state({"last_project": str(project.root)})
