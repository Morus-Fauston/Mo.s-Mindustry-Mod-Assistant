"""Serialized desktop access to existing-format projects and core sessions."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import json
from pathlib import Path
from threading import RLock
from typing import Callable
from uuid import uuid4

from app.core.config_loader import get_block_categories, get_field_docs, get_field_names_zh
from app.core.metadata import normalize_content_type
from app.core.project import Project
from app.core.session import ProjectSession


class WorkspaceError(Exception):
    def __init__(self, code: str, message: str, path: str | None = None):
        super().__init__(message)
        self.code, self.path = code, path


class WorkspaceService:
    """One window owns one core session; requests never accept arbitrary actions."""

    def __init__(self, metadata_dir: Path | str, choose_directory: Callable[[], str | None] | None = None):
        self._metadata_dir = Path(metadata_dir)
        self._choose_directory = choose_directory
        self._session = ProjectSession(metadata_dir)
        self._session_id: str | None = None
        self._lock = RLock()
        self._results: OrderedDict[str, tuple[str, dict]] = OrderedDict()

    def request_result(self, request_id: object) -> dict:
        """Inspect a completed operation without replaying or waiting for it."""
        if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
            return {"state": "unknown"}
        if not self._lock.acquire(blocking=False):
            return {"state": "pending"}
        try:
            cached = self._results.get(request_id)
            if cached is None:
                return {"state": "unknown"}
            return {"state": "completed", "response": deepcopy(cached[1])}
        finally:
            self._lock.release()

    def request(self, envelope: object) -> dict:
        with self._lock:
            request_id = envelope.get("requestId") if isinstance(envelope, dict) else None
            response = {"ok": False, "protocolVersion": 1, "requestId": request_id,
                        "sessionId": self._session_id}
            fingerprint = None
            try:
                if not isinstance(envelope, dict):
                    raise WorkspaceError("INVALID_REQUEST", "请求格式无效。")
                if type(envelope.get("protocolVersion")) is not int or envelope["protocolVersion"] != 1:
                    raise WorkspaceError("PROTOCOL_MISMATCH", "界面与程序版本不匹配，请重新启动。")
                if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
                    raise WorkspaceError("INVALID_REQUEST", "请求标识无效。")
                if envelope.get("sessionId") is not None and not isinstance(envelope["sessionId"], str):
                    raise WorkspaceError("INVALID_REQUEST", "会话标识无效。")
                action, payload = envelope.get("action"), envelope.get("payload", {})
                if action not in ("recent_projects", "open_project", "choose_project", "read_document") or not isinstance(payload, dict):
                    raise WorkspaceError("INVALID_REQUEST", "不支持此请求。")
                fingerprint = json.dumps(envelope, sort_keys=True, ensure_ascii=False, allow_nan=False)
                if len(fingerprint) > 16384:
                    fingerprint = None
                    raise WorkspaceError("INVALID_REQUEST", "请求内容过长。")
                if request_id in self._results:
                    previous, result = self._results[request_id]
                    if previous != fingerprint:
                        raise WorkspaceError("REQUEST_CONFLICT", "请求标识已用于其他操作，请重新发起。")
                    if result["sessionId"] != self._session_id:
                        raise WorkspaceError("STALE_SESSION", "工程已切换，请在当前工程重试。")
                    return deepcopy(result)
                if action != "recent_projects" and envelope.get("sessionId") != self._session_id:
                    raise WorkspaceError("STALE_SESSION", "工程已切换，请在当前工程重试。")
                data = self._dispatch(action, payload)
                response.update(ok=True, sessionId=self._session_id, data=data)
            except WorkspaceError as exc:
                response["error"] = {"code": exc.code, "message": str(exc)}
                if exc.path is not None:
                    response["error"]["path"] = exc.path
            except (OSError, ValueError, TypeError, RecursionError):
                response["error"] = {"code": "READ_FAILED", "message": "无法读取工程资料，请检查文件格式和访问权限后重试。"}
            if fingerprint is not None and request_id not in self._results:
                self._results[request_id] = (fingerprint, deepcopy(response))
                while len(self._results) > 128:
                    self._results.popitem(last=False)
            return response

    def _dispatch(self, action: str, payload: dict) -> dict:
        if action == "recent_projects":
            recent = self._session.last_project_path()
            if not isinstance(recent, str) or not recent or len(recent) > 4096 or "\x00" in recent:
                return {"recentProjects": []}
            path = Path(recent)
            name = path.name
            try:
                info = Project.open(path).mod_info
                name = next((value for value in (info.display_name, info.name)
                             if isinstance(value, str) and value.strip()), name)
            except (OSError, ValueError):
                pass
            return {"recentProjects": [{"path": str(path), "name": name}]}
        if action == "choose_project":
            if self._choose_directory is None:
                raise WorkspaceError("DIALOG_UNAVAILABLE", "目录选择器尚未就绪，请稍后重试。")
            path = self._choose_directory()
            if path is None:
                return {"cancelled": True}
            return self._open(path)
        if action == "open_project":
            return self._open(payload.get("path"))
        return self._read(payload.get("path"))

    def _open(self, path: object) -> dict:
        if not isinstance(path, str) or not path or len(path) > 4096 or "\x00" in path or not Path(path).is_absolute():
            raise WorkspaceError("INVALID_PATH", "请选择工程的完整目录路径。")
        root = Path(path).resolve()
        try:
            project = Project.open(root)
            if not isinstance(project.mod_info.name, str) or not isinstance(project.mod_info.display_name, str):
                raise ValueError("Invalid mod name")
            tree = self._tree(project)
            candidate = ProjectSession(self._metadata_dir)
            candidate.open_project(root)
        except (OSError, ValueError) as exc:
            raise WorkspaceError("PROJECT_OPEN_FAILED", "无法打开工程，请检查目录中的 mod.json 和文件访问权限。", str(root)) from exc
        self._session = candidate
        self._session_id = uuid4().hex
        return {"sessionId": self._session_id, "name": project.mod_info.display_name or project.mod_info.name or root.name,
                "root": str(root), "tree": tree}

    def _read(self, path: object) -> dict:
        if self._session.project is None:
            raise WorkspaceError("NO_PROJECT", "请先打开工程。")
        if not isinstance(path, str) or len(path) > 4096 or not path.startswith("content/"):
            raise WorkspaceError("INVALID_PATH", "请选择工程内容文件。")
        parts = path.split("/")
        if len(parts) != 3 or parts[1] not in ("units", "blocks", "weapons"):
            raise WorkspaceError("INVALID_PATH", "内容路径不在支持的分类内。", path)
        try:
            root = self._session.project.root.resolve()
            if not (root / path).resolve().is_relative_to(root):
                raise ValueError("Content escapes project")
            content = self._session.read_content(path[8:])
        except (OSError, ValueError) as exc:
            raise WorkspaceError("DOCUMENT_READ_FAILED", "无法读取此内容，请检查 JSON 格式、路径和文件访问权限。", path) from exc
        kind = content.data.get("type", "UnitType" if content.category == "units" else "Weapon" if content.category == "weapons" else "Block")
        if not isinstance(kind, str):
            kind = "Unknown"
        return {"sessionId": self._session_id, "path": path, "name": content.name,
                "category": content.category, "contentType": normalize_content_type(kind),
                "data": deepcopy(content.data), "fieldNames": deepcopy(get_field_names_zh()),
                "fieldDocs": deepcopy(get_field_docs())}

    @staticmethod
    def _group(identifier: str, label: str, children: list[dict]) -> dict:
        return {"id": identifier, "kind": "group", "label": label, "children": children}

    def _tree(self, project: Project) -> list[dict]:
        root = project.root.resolve()
        content_groups = []
        for category, label in (("units", "单位"), ("blocks", "方块"), ("weapons", "武器")):
            directory = root / "content" / category
            leaves = []
            if directory.is_dir() and directory.resolve().is_relative_to(root):
                for file in sorted(directory.glob("*.json")):
                    if not file.is_file() or not file.resolve().is_relative_to(root):
                        continue
                    path = file.relative_to(root).as_posix()
                    leaf = {"id": path, "kind": "content", "label": file.stem, "name": file.stem,
                            "category": category, "path": path}
                    try:
                        data = project.contents.get_by_path(f"{category}/{file.name}").data
                        display_name = data.get("name")
                        if isinstance(display_name, str) and display_name.strip():
                            leaf["label"] = display_name
                        kind = data.get("type", "Unknown")
                        leaf["contentType"] = kind if isinstance(kind, str) else "Unknown"
                    except (OSError, ValueError):
                        leaf["error"] = "内容读取失败，打开查看详情"
                    leaves.append(leaf)
            if leaves:
                if category == "blocks":
                    leaves = self._block_groups(leaves)
                content_groups.append(self._group(f"content/{category}", label, leaves))
        sprites = []
        if project.sprites_dir.is_dir() and project.sprites_dir.resolve().is_relative_to(root):
            for directory in sorted(project.sprites_dir.iterdir()):
                if not directory.is_dir() or not directory.resolve().is_relative_to(root):
                    continue
                children = [{"id": f.relative_to(root).as_posix(), "kind": "sprite", "label": f.name,
                             "name": f.stem, "category": directory.name, "path": f.relative_to(root).as_posix()}
                            for f in sorted(directory.glob("*.png"))
                            if f.is_file() and f.resolve().is_relative_to(root)]
                sprites.append(self._group(f"sprites/{directory.name}", {"units": "单位", "blocks": "方块", "weapons": "武器"}.get(directory.name, directory.name), children))
        return [self._group("content", "内容", content_groups), self._group("sprites", "贴图", sprites)]

    def _block_groups(self, leaves: list[dict]) -> list[dict]:
        groups = []
        assigned = set()
        for category in get_block_categories().get("categories", []):
            subgroups = []
            for sub in category.get("subCategories", []):
                children = [leaf for leaf in leaves if leaf.get("contentType") in sub.get("types", [])]
                if children:
                    assigned.update(leaf["id"] for leaf in children)
                    subgroups.append(self._group(f"blocks/{category['id']}/{sub['id']}", sub["name"], children))
            if subgroups:
                groups.append(self._group(f"blocks/{category['id']}", category["name"], subgroups))
        others = [leaf for leaf in leaves if leaf["id"] not in assigned]
        if others:
            groups.append(self._group("blocks/other", "其他", others))
        return groups
