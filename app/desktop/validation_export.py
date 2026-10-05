"""Current-session validation and existing-format export orchestration.

The workspace owns serialization, request deduplication and session lifetime.
This service owns neither a command stack nor a second editable data model.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import Callable
import zipfile

from app.core.content_store import ContentData
from app.core.project_files import open_project_file
from app.core.session import ProjectSession
from app.core.validator import Issue, validate_project
from app.desktop.editing import EditingError, EditingService
from app.desktop.source_editing import RawDocument, SourceEditingService


class ValidationExportService:
    def __init__(self, session: ProjectSession, session_id: str, editing: EditingService,
                 choose_export: Callable[[str], str | None] | None):
        self.session, self.session_id, self.editing = session, session_id, editing
        self.choose_export = choose_export

    def _check(self, payload: dict) -> None:
        if self.session.project is None:
            raise EditingError("NO_PROJECT", "请先打开工程。")
        if self.editing.session is not self.session or self.editing.session_id != self.session_id:
            raise EditingError("STALE_SESSION", "工程已切换，请在当前工程重试。")
        if not isinstance(payload, dict) or set(payload) - {"expectedRevision"}:
            raise EditingError("INVALID_REQUEST", "校验与导出请求参数无效。")
        self.editing.check_revision(payload)

    def _path(self, relative: str) -> Path:
        root = self.session.project.root.resolve()
        identity = PurePosixPath(relative)
        if (identity.is_absolute() or identity.as_posix() != relative or ".." in identity.parts
                or any(character in relative for character in ("\\", ":", "\x00"))):
            raise ValueError("校验文件路径无效")
        path = root / relative
        if not path.resolve().is_relative_to(root):
            raise OSError("校验文件位于工程范围之外")
        return path

    def _read_json(self, relative: str) -> dict:
        path = self._path(relative)
        with open_project_file(self.session.project.root, path) as stream:
            raw = stream.read(SourceEditingService.MAX_BYTES + 1)
        if len(raw) > SourceEditingService.MAX_BYTES:
            raise OSError("校验文件超过 4 MiB 读取上限")
        try:
            text = raw.decode("utf-8")
        except UnicodeError as exc:
            raise OSError("校验文件不是有效 UTF-8 文本") from exc
        return SourceEditingService._decode(text)

    @staticmethod
    def _issue(issue: Issue, path: str, origin: str, *, source_error: dict | None = None) -> dict:
        field = issue.field or (issue.path if origin == "content" else "")
        field = field if field and field.isidentifier() else None
        supported = len(path.split("/")) == 3 and path.split("/")[1] in ("units", "blocks", "weapons")
        target = "source" if source_error is not None and supported else (
            "form" if field and supported else "file" if supported else "unavailable")
        result = {"id": sha256(f"{path}\0{field}\0{issue.severity}\0{issue.message}".encode("utf-8")).hexdigest()[:24],
                  "severity": issue.severity, "message": issue.message, "path": path, "field": field,
                  "target": target, "origin": origin}
        if source_error is not None:
            result.update({key: source_error[key] for key in ("line", "column") if key in source_error})
        return result

    def validate(self, payload: dict) -> dict:
        self._check(payload)
        return self._validate()

    def export(self, payload: dict) -> dict:
        self._check(payload)
        if self.choose_export is None:
            raise EditingError("DIALOG_UNAVAILABLE", "导出文件选择器尚未就绪。")
        # Save is the existing opened-document path, including its raw precheck
        # and partial-I/O semantics; business validation errors remain editable.
        state = self.editing.save(payload)
        report = self._validate()
        invalid = next((issue for issue in report["issues"] if issue["origin"] == "source"), None)
        if invalid is not None:
            raise EditingError("SOURCE_INVALID", "工程中仍有无效 JSON 源码，请修复后导出。", invalid["path"])
        project = self.session.project
        name = project.mod_info.name
        default = f"{name}.zip" if isinstance(name, str) and name and all(
            character.isascii() and (character.isalnum() or character == "-") for character in name) else "mod.zip"
        try:
            selected = self.choose_export(default)
        except (OSError, ValueError, RuntimeError) as exc:
            raise EditingError("EXPORT_FAILED", f"无法选择导出位置：{exc}") from exc
        result = {"sessionId": self.session_id, "revision": self.editing.revision,
                  "state": state, "report": report, "cancelled": selected is None, "exported": False}
        if selected is None:
            return result
        temporary: Path | None = None
        try:
            if (not isinstance(selected, str) or not selected or len(selected) > 4096 or "\x00" in selected
                    or not Path(selected).is_absolute() or Path(selected).suffix.lower() != ".zip"):
                raise ValueError("请选择 ZIP 压缩包的完整保存路径")
            target = Path(selected)
            if target.is_symlink() or target.exists() and not target.is_file():
                raise ValueError("导出目标不是普通文件")
            target = target.resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temp_name = tempfile.mkstemp(prefix=".moma-export-", suffix=".zip", dir=target.parent)
            os.close(descriptor)
            temporary = Path(temp_name)
            project.export_zip(temporary, exclude_paths=[target, temporary])
            with zipfile.ZipFile(temporary) as archive:
                if "mod.json" not in archive.namelist() or archive.testzip() is not None:
                    raise ValueError("导出包未通过完整性检查")
                # Verify the actual bytes that will be published. A native
                # picker does not prevent another process changing source files.
                for item in archive.infolist():
                    if item.filename == "mod.json" or (item.filename.startswith("content/") and item.filename.lower().endswith(".json")):
                        try:
                            if item.file_size > SourceEditingService.MAX_BYTES:
                                raise ValueError("JSON 文件超过 4 MiB 校验上限")
                            SourceEditingService._decode(archive.read(item).decode("utf-8"))
                        except (ValueError, UnicodeError) as exc:
                            raise EditingError("SOURCE_INVALID", "实际导出内容包含无效 JSON，请刷新并修复后再导出。", item.filename) from exc
            size = temporary.stat().st_size
            digest = sha256()
            with temporary.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            os.replace(temporary, target)
            temporary = None
            return {**result, "exported": True,
                    "output": {"name": target.name, "path": str(target), "bytes": size, "sha256": digest.hexdigest()}}
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
            raise EditingError("EXPORT_FAILED", f"导出失败，原有目标文件已保留，请检查位置和访问权限：{exc}") from exc
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError as exc:
                    raise EditingError("EXPORT_FAILED", f"导出失败，临时文件未能清理，原目标未替换：{temporary}。请关闭文件占用后清理。") from exc

    def _validate(self) -> dict:
        entries = self.editing.document_entries()
        current = {path: deepcopy(entry.data) if isinstance(entry, ContentData) else entry
                   for path, entry in entries.items()}
        contents: dict[str, dict] = {}
        source_errors: dict[str, dict] = {}

        def read_mod() -> dict:
            try:
                return self._read_json("mod.json")
            except ValueError as exc:
                source_errors["mod.json"] = SourceEditingService.error_details(exc)
                raise

        def read_content(relative: str) -> dict:
            path = f"content/{relative}"
            # Recheck path ownership even for a registered in-memory document.
            self._path(path)
            entry = current.get(path)
            try:
                if isinstance(entry, RawDocument):
                    source_errors[path] = deepcopy(entry.source_error)
                    raise ValueError(entry.source_error["message"])
                data = entry if isinstance(entry, dict) else self._read_json(path)
            except ValueError as exc:
                source_errors.setdefault(path, SourceEditingService.error_details(exc))
                raise
            contents[path] = data
            return data

        try:
            # Reject escaping category/mod paths before the core filesystem scan.
            if not self._path("mod.json").is_file():
                raise OSError("缺少可读取的 mod.json")
            content_root = self._path("content")
            if content_root.exists():
                for category in content_root.iterdir():
                    if category.is_dir():
                        self._path(f"content/{category.name}")
            project_issues = validate_project(self.session.project, self.session.metadata,
                read_content=read_content, extra_paths=[path[8:] for path in current], read_mod=read_mod)
            issues = []
            for issue in project_issues:
                path = "mod.json" if issue.path == "mod.json" else f"content/{issue.path}"
                issues.append(self._issue(issue, path, "source" if path in source_errors else "project",
                                          source_error=source_errors.get(path)))
            for path, data in contents.items():
                issues.extend(self._issue(issue, path, "content") for issue in self.session.validator.validate(data, "content"))
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            raise EditingError("VALIDATION_FAILED", f"校验未完成，请检查工程文件和资料：{exc}") from exc
        unique = {(issue["path"], issue["field"], issue["severity"], issue["message"]): issue for issue in issues}
        rows = sorted(unique.values(), key=lambda issue: (issue["severity"] != "error", issue["path"], issue["id"]))
        return {"sessionId": self.session_id, "revision": self.editing.revision, "issues": rows,
                "errors": sum(row["severity"] == "error" for row in rows),
                "warnings": sum(row["severity"] == "warning" for row in rows), "complete": True}
