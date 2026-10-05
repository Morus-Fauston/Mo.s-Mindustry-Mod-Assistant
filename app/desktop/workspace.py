"""Serialized desktop access to existing-format projects and core sessions."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import json
from pathlib import Path
from threading import RLock
from typing import Callable
from uuid import uuid4

from app.core.config_loader import get_block_categories
from app.core.project import Project
from app.core.session import ProjectSession
from app.desktop.editing import EditingError, EditingService
from app.desktop.preview import PreviewService
from app.desktop.resources import ResourceService
from app.desktop.resource_watch import ResourceWatch


class WorkspaceError(EditingError):
    pass


class WorkspaceService:
    """One window owns one core session; requests never accept arbitrary actions."""

    def __init__(self, metadata_dir: Path | str, choose_directory: Callable[[], str | None] | None = None,
                 *, choose_sprite: Callable[[], str | None] | None = None,
                 reveal_file: Callable[[Path], None] | None = None):
        self._metadata_dir = Path(metadata_dir)
        self._choose_directory = choose_directory
        self._choose_sprite, self._reveal_file = choose_sprite, reveal_file
        self._resources: ResourceService | None = None
        self._resource_watch: ResourceWatch | None = None
        self._session = ProjectSession(metadata_dir)
        self._session_id: str | None = None
        self._editing = EditingService(self._session, None)
        self._closing = False
        self._preview: PreviewService | None = None
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
                if action not in ("recent_projects", "open_project", "choose_project", "read_document",
                                  "editing_state", "set_field", "undo", "redo", "save_opened",
                                  "close_documents", "close_window", "preview_scene", "preview_resource",
                                  "add_field", "delete_field", "set_capability", "add_group", "delete_group",
                                  "reference_candidates", "sprite_targets", "resource_state",
                                  "import_sprite", "delete_sprite", "reveal_sprite", "set_type", "create_object",
                                  "array_insert", "array_remove", "array_move", "resource_reference_candidates",
                                  "resource_set", "resource_add", "resource_remove", "resource_move",
                                  "consume_add", "consume_remove", "weapon_reference_candidates", "weapon_add",
                                  "weapon_remove", "weapon_move", "weapon_add_override", "weapon_expand",
                                  "research_reference_candidates", "research_set", "research_add", "research_remove",
                                  "research_move", "research_objective_type", "planet_add", "planet_remove", "planet_set") or not isinstance(payload, dict):
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
                if self._closing and action not in ("editing_state", "recent_projects"):
                    raise WorkspaceError("WINDOW_CLOSING", "窗口正在关闭，不能继续修改工程。")
                data = self._dispatch(action, payload)
                response.update(ok=True, sessionId=self._session_id, data=data)
            except EditingError as exc:
                response["error"] = {"code": exc.code, "message": str(exc)}
                if exc.path is not None:
                    response["error"]["path"] = exc.path
            except (OSError, ValueError, TypeError, RecursionError):
                response["error"] = {"code": "READ_FAILED", "message": "无法读取工程资料，请检查文件格式和访问权限后重试。"}
            # Preview reads can be repeated explicitly. Keeping their data URLs in
            # the mutation-result cache would retain old scenes after resource cleanup.
            cacheable = isinstance(envelope, dict) and envelope.get("action") not in ("preview_scene", "preview_resource", "reference_candidates", "resource_reference_candidates", "weapon_reference_candidates", "research_reference_candidates", "sprite_targets", "resource_state")
            if cacheable and fingerprint is not None and request_id not in self._results:
                self._results[request_id] = (fingerprint, deepcopy(response))
                while len(self._results) > 128:
                    self._results.popitem(last=False)
            return response

    def _dispatch(self, action: str, payload: dict) -> dict:
        if action == "resource_state":
            return self._resource_state()
        if action in ("sprite_targets", "import_sprite", "delete_sprite", "reveal_sprite"):
            return self._sprite_action(action, payload)
        if action == "reference_candidates":
            return self._editing.reference_candidates(payload)
        if action == "resource_reference_candidates":
            return self._editing.reference_candidates(payload, resource=True)
        if action == "research_reference_candidates":
            return self._editing.reference_candidates(payload, research=True)
        if action == "weapon_reference_candidates":
            return self._editing.reference_candidates(payload, weapon=True)
        if action == "preview_scene":
            content = self._content(payload.get("path"))
            if self._preview is None:
                raise WorkspaceError("NO_PROJECT", "请先打开工程。")
            try:
                return self._preview.scene(content)
            except (ValueError, OSError) as exc:
                raise WorkspaceError("PREVIEW_FAILED", "预览组装失败，请检查内容与素材后刷新预览。") from exc
        if action == "preview_resource":
            if self._preview is None:
                raise WorkspaceError("NO_PROJECT", "请先打开工程。")
            try:
                return self._preview.resource(payload.get("resourceId"))
            except ValueError as exc:
                raise WorkspaceError("PREVIEW_RESOURCE_UNAVAILABLE", str(exc)) from exc
        if action == "editing_state":
            return self._editing.state()
        if action == "set_field":
            return self._editing.set_field(payload)
        if action in ("add_field", "delete_field", "set_capability", "add_group", "delete_group",
                      "set_type", "create_object", "array_insert", "array_remove", "array_move",
                      "resource_set", "resource_add", "resource_remove", "resource_move", "consume_add", "consume_remove",
                      "weapon_add", "weapon_remove", "weapon_move", "weapon_add_override", "weapon_expand",
                      "research_set", "research_add", "research_remove", "research_move", "research_objective_type",
                      "planet_add", "planet_remove", "planet_set"):
            return self._editing.form_action(action, payload)
        if action in ("undo", "redo"):
            return self._editing.history(action, payload)
        if action == "save_opened":
            return self._editing.save(payload)
        if action == "close_documents":
            return self._editing.close(payload)
        if action == "close_window":
            self._editing.check_revision(payload)
            decision = payload.get("decision")
            if decision not in ("save", "discard"):
                raise WorkspaceError("INVALID_CLOSE", "请明确选择保存、放弃或取消关闭。")
            if decision == "save":
                self._editing.save(payload)
            self._closing = True
            if self._resource_watch is not None:
                self._resource_watch.close()
            return {**self._editing.state(), "closeApproved": True}
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
            self._check_open_decision(payload)
            if self._choose_directory is None:
                raise WorkspaceError("DIALOG_UNAVAILABLE", "目录选择器尚未就绪，请稍后重试。")
            path = self._choose_directory()
            if path is None:
                return {"cancelled": True}
            return self._open(path)
        if action == "open_project":
            self._check_open_decision(payload)
            return self._open(payload.get("path"))
        if "expectedRevision" in payload:
            self._editing.check_revision(payload)
        return self._read(payload.get("path"))

    def _check_open_decision(self, payload: dict) -> None:
        if self._editing.has_dirty():
            if payload.get("discard") is not True:
                raise WorkspaceError("UNSAVED_CHANGES", "当前工程有未保存修改，请先保存或明确放弃。")
            self._editing.check_revision(payload)
        elif "expectedRevision" in payload:
            self._editing.check_revision(payload)

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
        watch = ResourceWatch(candidate.project.root)
        if self._resource_watch is not None:
            self._resource_watch.close()
        self._session = candidate
        self._session_id = uuid4().hex
        self._editing = EditingService(candidate, self._session_id, self._editing.revision + 1)
        self._preview = PreviewService(candidate.project, self._session_id)
        self._resource_watch = watch
        self._resources = ResourceService(candidate.project, candidate.command_stack,
            on_change=self._resource_changed, content_resolver=self._content)
        return {"sessionId": self._session_id, "name": project.mod_info.display_name or project.mod_info.name or root.name,
                "root": str(root), "tree": tree}

    def _resource_changed(self) -> None:
        # Notification is in the command, so undo/redo also invalidate revision.
        self._editing.revision += 1

    def _resource_state(self) -> dict:
        if self._resource_watch is None or self._session.project is None:
            raise WorkspaceError("NO_PROJECT", "请先打开工程。")
        try:
            self._resource_watch.scan()
            return {"sessionId": self._session_id, "resourceRevision": self._resource_watch.revision,
                    "tree": self._tree(self._session.project)}
        except (OSError, ValueError) as exc:
            raise WorkspaceError("RESOURCE_FAILED", f"资源刷新失败：{exc}") from exc

    def _sprite_action(self, action: str, payload: dict) -> dict:
        if self._resources is None:
            raise WorkspaceError("NO_PROJECT", "请先打开工程。")
        allowed = {"path", "suffix", "expectedRevision", "overwrite", "confirmed"}
        if set(payload) - allowed:
            raise WorkspaceError("INVALID_REQUEST", "贴图操作不接受外部文件路径。")
        path, suffix = payload.get("path"), payload.get("suffix", "")
        if not isinstance(suffix, str):
            raise WorkspaceError("INVALID_REQUEST", "贴图后缀无效。")
        try:
            targets = self._resources.targets(path)
            if action == "sprite_targets":
                return {"targets": targets}
            self._editing.check_revision(payload)
            target = next((item for item in targets if item["suffix"] == suffix), None)
            if target is None:
                raise ValueError("不支持此贴图类型")
            if action == "import_sprite":
                overwrite = payload.get("overwrite", False)
                if type(overwrite) is not bool:
                    raise ValueError("覆盖确认无效")
                if target["exists"] and not overwrite:
                    raise FileExistsError("贴图已存在，请先确认替换")
                if self._choose_sprite is None:
                    raise ValueError("文件选择器尚未就绪")
                source = self._choose_sprite()
                if source is None:
                    return {**self._editing.state(), "cancelled": True}
                self._resources.import_sprite(path, source, suffix, overwrite=overwrite)
            elif action == "delete_sprite":
                self._resources.delete_sprite(path, suffix, confirmed=payload.get("confirmed", False))
            else:
                if not target["exists"] or self._reveal_file is None:
                    raise ValueError("贴图不存在或系统定位尚未就绪")
                self._reveal_file(self._session.project.root / target["path"])
            return self._editing.state()
        except (OSError, ValueError) as exc:
            raise WorkspaceError("RESOURCE_FAILED", f"贴图操作失败：{exc}") from exc

    def _read(self, path: object) -> dict:
        return self._editing.opened(path, self._content(path))

    def _content(self, path: object):
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
        return content

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
