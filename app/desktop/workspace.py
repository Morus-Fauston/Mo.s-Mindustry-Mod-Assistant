"""Serialized desktop access to existing-format projects and core sessions."""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from hashlib import sha256
import json
import logging
from pathlib import Path
from threading import RLock
from typing import Callable
from uuid import uuid4

from app.core.config_loader import get_block_categories, set_display_mode
from app.core.settings import get_settings
from app.core.content_store import ContentData
from app.core.project import Project
from app.core.session import ProjectSession
from app.desktop.editing import EditingError, EditingService
from app.desktop.content_actions import ContentActions, create_project
from app.desktop.content_identity import ContentIdentityAdapter
from app.desktop.preview import PreviewService
from app.desktop.reference_projects import ReferenceProjectsService
from app.desktop.preview_layers import PreviewLayerService
from app.desktop.dynamic_preview import DynamicPreviewService
from app.desktop.resources import ResourceService
from app.desktop.sprite_generation import SpriteGenerationService
from app.desktop.resource_watch import ResourceWatch
from app.desktop.source_editing import RawDocument, SourceEditingService
from app.desktop.validation_export import ValidationExportService
from app.desktop.preferences import PreferencesService


class WorkspaceError(EditingError):
    pass


class WorkspaceService:
    """One window owns one core session; requests never accept arbitrary actions."""

    MAX_RESULT_CACHE_BYTES = 32 * 1024 * 1024

    def __init__(self, metadata_dir: Path | str, choose_directory: Callable[[], str | None] | None = None,
                 *, choose_sprite: Callable[[], str | None] | None = None,
                 choose_export: Callable[[str], str | None] | None = None,
                 choose_reference_zip: Callable[[], str | None] | None = None,
                 reveal_file: Callable[[Path], None] | None = None):
        self._metadata_dir = Path(metadata_dir)
        self._choose_directory = choose_directory
        self._choose_sprite, self._reveal_file = choose_sprite, reveal_file
        self._choose_export = choose_export
        self._choose_reference_zip = choose_reference_zip
        self._reference_projects: ReferenceProjectsService | None = None
        self._resources: ResourceService | None = None
        self._generation: SpriteGenerationService | None = None
        self._resource_watch: ResourceWatch | None = None
        self._session = ProjectSession(metadata_dir)
        self._preferences = PreferencesService()
        self._sync_preferences(self._preferences.state())
        self._session_id: str | None = None
        self._editing = EditingService(self._session, None)
        self._content_actions: ContentActions | None = None
        self._content_identity = ContentIdentityAdapter(self._editing)
        self._last_tree: list[dict] = []
        self._pending_project_services: dict | None = None
        self._closing = False
        self._preview: PreviewService | None = None
        self._lock = RLock()
        self._results: OrderedDict[str, tuple[str, dict]] = OrderedDict()
        self._result_sizes: dict[str, int] = {}
        self._result_bytes = 0

    @staticmethod
    def _expired_result(response: dict) -> dict:
        return {"ok": False, "protocolVersion": 1, "requestId": response["requestId"],
                "sessionId": response["sessionId"], "error": {"code": "RESULT_EXPIRED",
                "message": "此请求已经执行，完整结果已释放，请刷新当前状态确认；不要重复提交。"}}

    def _cache_result(self, request_id: str, fingerprint: str, response: dict) -> None:
        # Bound retained transport data, including sourceText and repeated form
        # projections. Small tombstones prevent an evicted mutation being replayed.
        # Escaped JSON also covers non-content metadata; counting a response
        # must never fail after its operation has already committed.
        size = len(json.dumps(response, ensure_ascii=True, allow_nan=False).encode("utf-8"))
        stored = response if size <= self.MAX_RESULT_CACHE_BYTES else self._expired_result(response)
        if stored is not response:
            size = len(json.dumps(stored, ensure_ascii=True).encode("utf-8"))
        self._results[request_id] = (fingerprint, deepcopy(stored))
        self._result_sizes[request_id] = size
        self._result_bytes += size
        while len(self._results) > 128:
            old_id, _ = self._results.popitem(last=False)
            self._result_bytes -= self._result_sizes.pop(old_id)
        for old_id, (digest, result) in self._results.items():
            if self._result_bytes <= self.MAX_RESULT_CACHE_BYTES:
                break
            expired = self._expired_result(result)
            expired_size = len(json.dumps(expired, ensure_ascii=True).encode("utf-8"))
            if expired_size >= self._result_sizes[old_id]:
                continue
            self._result_bytes += expired_size - self._result_sizes[old_id]
            self._result_sizes[old_id] = expired_size
            self._results[old_id] = (digest, expired)

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
                if action not in ("preferences_state", "update_settings", "update_layout", "recent_projects", "open_project", "choose_project", "read_document",
                                  "content_catalogue", "create_content", "rename_content", "delete_content", "reveal_content", "create_project",
                                  "editing_state", "validate_project", "export_project", "set_field", "set_source", "format_source", "undo", "redo", "save_opened",
                                  "close_documents", "close_project", "close_window", "preview_scene", "preview_resource",
                                  "add_field", "delete_field", "set_capability", "add_group", "delete_group",
                                  "reference_candidates", "sprite_targets", "resource_state",
                                  "reference_sources", "open_reference", "reference_candidates_for_compare", "compare_reference", "release_reference",
                                  "import_sprite", "delete_sprite", "reveal_sprite", "preview_generation", "confirm_generation", "cancel_generation", "set_type", "create_object",
                                  "array_insert", "array_remove", "array_move", "resource_reference_candidates",
                                  "resource_set", "resource_add", "resource_remove", "resource_move",
                                  "consume_add", "consume_remove", "weapon_reference_candidates", "weapon_add",
                                  "weapon_remove", "weapon_move", "weapon_add_override", "weapon_expand",
                                  "research_reference_candidates", "research_set", "research_add", "research_remove",
                                  "research_move", "research_objective_type", "planet_add", "planet_remove", "planet_set") or not isinstance(payload, dict):
                    raise WorkspaceError("INVALID_REQUEST", "不支持此请求。")
                source_action = action in ("set_source", "format_source")
                if source_action:
                    source_text = payload.get("text")
                    if (not isinstance(source_text, str) or len(source_text) > SourceEditingService.MAX_BYTES
                            or len(source_text.encode("utf-8")) > SourceEditingService.MAX_BYTES):
                        raise WorkspaceError("SOURCE_INVALID", "JSON 源码必须为不超过 4 MiB 的 UTF-8 文本。", payload.get("path"))
                    if set(payload) - {"path", "text", "expectedRevision"}:
                        raise WorkspaceError("INVALID_REQUEST", "源码请求参数无效。")
                serialized = json.dumps(envelope, sort_keys=True, ensure_ascii=False, allow_nan=False)
                # JSON escaping can multiply a source's UTF-8 size by six.
                limit = SourceEditingService.MAX_BYTES * 6 + 16384 if source_action else 16384
                if len(serialized.encode("utf-8")) > limit:
                    raise WorkspaceError("INVALID_REQUEST", "请求内容过长。")
                fingerprint = sha256(serialized.encode("utf-8")).hexdigest()
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
                response["error"].update({key: value for key, value in exc.details.items() if key in ("line", "column")})
                if exc.path is not None:
                    response["error"]["path"] = exc.path
            except (OSError, ValueError, TypeError, RecursionError):
                response["error"] = {"code": "READ_FAILED", "message": "无法读取工程资料，请检查文件格式和访问权限后重试。"}
            # Preview reads can be repeated explicitly. Keeping their data URLs in
            # the mutation-result cache would retain old scenes after resource cleanup.
            cacheable = isinstance(envelope, dict) and envelope.get("action") not in ("preview_scene", "preview_resource", "reference_candidates", "resource_reference_candidates", "weapon_reference_candidates", "research_reference_candidates", "sprite_targets", "resource_state", "format_source", "reference_sources", "reference_candidates_for_compare", "compare_reference")
            if cacheable and fingerprint is not None and request_id not in self._results:
                self._cache_result(request_id, fingerprint, response)
            return response

    def _dispatch(self, action: str, payload: dict) -> dict:
        if action in ("preferences_state", "update_settings", "update_layout"):
            return self._preferences_action(action, payload)
        if action in ("reference_sources", "open_reference", "reference_candidates_for_compare", "compare_reference", "release_reference"):
            return self._reference_action(action, payload)
        if action == "content_catalogue":
            if payload:
                raise WorkspaceError("INVALID_REQUEST", "模板目录不接受额外参数。")
            return ContentActions(None, self._session.command_stack, metadata=self._session.metadata).catalogue()
        if action in ("create_content", "rename_content", "delete_content", "reveal_content"):
            return self._content_action(action, payload)
        if action == "create_project":
            return self._create_project(payload)
        if action in ("preview_generation", "confirm_generation", "cancel_generation"):
            return self._generation_action(action, payload)
        if action in ("validate_project", "export_project"):
            service = ValidationExportService(self._session, self._session_id, self._editing, self._choose_export)
            if action == "export_project":
                return service.export(payload)
            report = service.validate(payload)
            return {"state": self._editing.state(), "report": report}
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
                path = payload.get("path")
                form = self._editing.nested.plan(content, path)
                scene = PreviewLayerService(self._session.project).decorate(
                    self._preview.scene(content), content, form, path, self._editing.revision)
                scene["dynamic"] = DynamicPreviewService(self._session.project, self._preview.register_resource).describe(content, scene)
                return scene
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
        if action == "set_source":
            return self._editing.set_source(payload)
        if action == "format_source":
            return self._editing.format_source(payload)
        if action in ("add_field", "delete_field", "set_capability", "add_group", "delete_group",
                      "set_type", "create_object", "array_insert", "array_remove", "array_move",
                      "resource_set", "resource_add", "resource_remove", "resource_move", "consume_add", "consume_remove",
                      "weapon_add", "weapon_remove", "weapon_move", "weapon_add_override", "weapon_expand",
                      "research_set", "research_add", "research_remove", "research_move", "research_objective_type",
                      "planet_add", "planet_remove", "planet_set"):
            return self._editing.form_action(action, payload)
        if action in ("undo", "redo"):
            try:
                result = self._editing.history(action, payload)
                if self._pending_project_services is not None:
                    services, self._pending_project_services = self._pending_project_services, None
                    self._adopt_services(services)
                    return {**self._editing.state(), "project": services["project"]}
                change = self._content_identity.consume_change()
                if change:
                    result.update(tree=self._current_tree(), contentChange=change,
                                  activePath=self._active_content_path(change))
                return result
            except EditingError:
                raise
            except ExceptionGroup as exc:
                raise WorkspaceError("CONTENT_ROLLBACK_FAILED", str(exc)) from exc
            except (OSError, ValueError, TypeError, RuntimeError) as exc:
                raise WorkspaceError("HISTORY_FAILED", f"撤销或重做未完成：{exc}") from exc
        if action == "save_opened":
            return self._editing.save(payload)
        if action == "close_documents":
            return self._editing.close(payload)
        if action == "close_project":
            return self._close_project(payload)
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
            if self._generation is not None:
                self._generation.close()
            self._release_generation_results()
            if self._reference_projects is not None:
                self._reference_projects.close()
            self._release_reference_results()
            return {**self._editing.state(), "closeApproved": True}
        if action == "recent_projects":
            recent = self._session.last_project_path()
            warnings = [self._session.persistence_warning] if self._session.persistence_warning else []
            if not isinstance(recent, str) or not recent or len(recent) > 4096 or "\x00" in recent:
                return {"recentProjects": [], "warnings": warnings}
            path = Path(recent)
            name = path.name
            try:
                info = Project.open(path).mod_info
                name = next((value for value in (info.display_name, info.name)
                             if isinstance(value, str) and value.strip()), name)
            except (OSError, ValueError):
                pass
            return {"recentProjects": [{"path": str(path), "name": name}], "warnings": warnings}
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

    @staticmethod
    def _sync_preferences(state: dict) -> None:
        settings = get_settings()
        for key in ("theme", "display_name_mode", "auto_save_interval", "sprite_zoom"):
            settings.set(key, state["values"][key])
        set_display_mode(state["values"]["display_name_mode"])

    def _preferences_action(self, action: str, payload: dict) -> dict:
        if action == "preferences_state":
            if payload:
                raise WorkspaceError("INVALID_REQUEST", "读取设置不接受额外参数。")
            return self._preferences.state()
        key = "patch" if action == "update_settings" else "layout"
        if set(payload) != {key, "expectedPreferencesRevision"}:
            raise WorkspaceError("INVALID_REQUEST", "设置请求参数无效。")
        update = self._preferences.update_settings if action == "update_settings" else self._preferences.update_layout
        state = update(payload[key], payload["expectedPreferencesRevision"])
        self._sync_preferences(state)
        return {"preferences": state, "state": self._editing.state()}

    def _check_open_decision(self, payload: dict) -> None:
        if self._editing.has_dirty():
            if payload.get("discard") is not True:
                raise WorkspaceError("UNSAVED_CHANGES", "当前工程有未保存修改，请先保存或明确放弃。")
            self._editing.check_revision(payload)
        elif "expectedRevision" in payload:
            self._editing.check_revision(payload)

    def _close_project(self, payload: dict) -> dict:
        if set(payload) != {"decision", "expectedRevision"} or payload.get("decision") not in ("save", "discard"):
            raise WorkspaceError("INVALID_CLOSE", "关闭工程请求无效，请明确选择保存或放弃。")
        self._editing.check_revision(payload)
        if self._session.project is None:
            raise WorkspaceError("NO_PROJECT", "请先打开工程。")
        services = self._prepare_services(ProjectSession(self._metadata_dir))
        if payload["decision"] == "save":
            self._editing.save(payload)
        # Saving may advance revisions. The empty session must be newer than
        # every acknowledged write, and is adopted only after saving succeeds.
        services["revision"] = self._editing.revision + 1
        self._adopt_services(services)
        return {"project": None, "state": self._editing.state()}

    def _open(self, path: object) -> dict:
        if not isinstance(path, str) or not path or len(path) > 4096 or "\x00" in path or not Path(path).is_absolute():
            raise WorkspaceError("INVALID_PATH", "请选择工程的完整目录路径。")
        root = Path(path).resolve()
        try:
            project = Project.open(root)
            if not isinstance(project.mod_info.name, str) or not isinstance(project.mod_info.display_name, str):
                raise ValueError("Invalid mod name")
            candidate = ProjectSession(self._metadata_dir)
            # Preparing a candidate must not replace the last successful project.
            # Publish its recent path only after the complete service adoption.
            candidate.attach_project(project)
            services = self._prepare_services(candidate)
        except (OSError, ValueError) as exc:
            raise WorkspaceError("PROJECT_OPEN_FAILED", "无法打开工程，请检查目录中的 mod.json 和文件访问权限。", str(root)) from exc
        self._adopt_services(services)
        return services["project"]

    def _prepare_services(self, candidate: ProjectSession, retained: dict | None = None) -> dict:
        """Build all fallible services before releasing the visible workbench."""
        sid = uuid4().hex
        project = candidate.project
        tree = self._tree(project) if project else []
        if retained is None:
            editing = EditingService(candidate, sid, self._editing.revision + 1,
                                     on_saved=lambda path: actions.saved(path) if actions else None)
            identity = ContentIdentityAdapter(editing)
            actions = ContentActions(project, candidate.command_stack, metadata=candidate.metadata,
                                     on_change=identity.handler) if project else None
            # Capture the actual action owner; old history must never acknowledge
            # a later project's files as saves belonging to this project.
        else:
            editing, identity, actions = retained["editing"], retained["identity"], retained["actions"]
        preview = PreviewService(project, sid) if project else None
        resources = ResourceService(project, candidate.command_stack,
            on_change=self._resource_changed, content_resolver=self._content) if project else None
        generation = SpriteGenerationService(project, resources, sid,
            content_resolver=self._content, on_change=self._resource_changed) if project else None
        watch = ResourceWatch(project.root) if project else None
        references = ReferenceProjectsService(candidate.metadata, sid) if project else None
        snapshot = {"sessionId": sid,
                    "name": project.mod_info.display_name or project.mod_info.name or project.root.name,
                    "root": str(project.root), "tree": tree} if project else None
        return {"session": candidate, "sid": sid, "revision": self._editing.revision + 1,
                "editing": editing, "identity": identity, "actions": actions, "preview": preview,
                "resources": resources, "generation": generation, "watch": watch, "references": references,
                "tree": tree, "project": snapshot}

    def _adopt_services(self, services: dict) -> None:
        if self._reference_projects is not None:
            self._reference_projects.close()
        self._release_reference_results()
        if self._generation is not None:
            self._generation.close()
        self._release_generation_results()
        if self._resource_watch is not None:
            self._resource_watch.close()
        self._session, self._session_id = services["session"], services["sid"]
        self._editing, self._content_identity = services["editing"], services["identity"]
        self._editing.session_id, self._editing.revision = self._session_id, services["revision"]
        self._content_actions = services["actions"]
        self._last_tree, self._preview = services["tree"], services["preview"]
        self._resource_watch, self._resources = services["watch"], services["resources"]
        self._generation = services["generation"]
        self._reference_projects = services["references"]
        if services["project"] is not None:
            warning = self._session.remember_project()
            services["project"]["warnings"] = [warning] if warning else []

    def _create_project(self, payload: dict) -> dict:
        if set(payload) - {"mod_id", "displayName", "author", "expectedRevision", "decision"}:
            raise WorkspaceError("INVALID_REQUEST", "新建工程参数无效，目录必须通过系统选择。")
        self._editing.check_revision(payload)
        try:
            ContentActions._name(payload.get("mod_id"))
            if not isinstance(payload.get("displayName"), str) or not isinstance(payload.get("author", ""), str):
                raise ValueError("显示名称和作者必须为文本。")
            if payload.get("decision") not in (None, "save", "discard"):
                raise ValueError("请选择保存、放弃或取消新建工程。")
            if self._editing.has_dirty() and payload.get("decision") is None:
                raise WorkspaceError("UNSAVED_CHANGES", "当前工程有未保存修改，请选择保存或放弃。")
            if self._choose_directory is None:
                raise WorkspaceError("DIALOG_UNAVAILABLE", "目录选择器尚未就绪，请稍后重试。")
            parent = self._choose_directory()
            if parent is None:
                return {"cancelled": True, "state": self._editing.state()}
            if not isinstance(parent, str) or not Path(parent).is_absolute():
                raise ValueError("请选择工程父目录的完整路径。")
            candidate = ProjectSession(self._metadata_dir)
            holder = {"retained": None, "attached": False, "ignore": None}

            def changed(project: Project, undo: bool) -> None:
                # The command can send an inverse callback after rolling files
                # back. If publication never happened, that callback is a no-op.
                if holder["ignore"] == undo:
                    holder["ignore"] = None
                    return
                attached = not undo
                if holder["attached"] == attached:
                    return
                previous = candidate.project
                try:
                    candidate.attach_project(None if undo else project)
                    services = self._prepare_services(candidate, holder["retained"])
                except Exception:
                    candidate.attach_project(previous)
                    holder["ignore"] = not undo
                    raise
                holder["attached"] = attached
                if holder["retained"] is None:
                    # History needs document identity, not the old session's PNG
                    # cache, resource watcher or generation service.
                    holder["retained"] = {key: services[key] for key in ("editing", "identity", "actions")}
                self._pending_project_services = services

            create_project(parent, payload["mod_id"], payload["displayName"], candidate.command_stack,
                           author=payload.get("author", ""), on_change=changed)
            # Only resolve old drafts once the new project and all its services
            # are ready. A name collision or initialization failure must not
            # discard an otherwise healthy current workbench.
            services = self._pending_project_services
            try:
                self._content_identity.prepare(list(self._editing.document_entries()), payload.get("decision"))
            except Exception as failure:
                try:
                    candidate.undo()
                except Exception as recovery:
                    raise ExceptionGroup("新建工程取消失败，请保留当前工程并检查新目录。", [failure, recovery]) from failure
                finally:
                    if services["generation"] is not None:
                        services["generation"].close()
                    if services["watch"] is not None:
                        services["watch"].close()
                    if services["references"] is not None:
                        services["references"].close()
                    self._pending_project_services = None
                raise
            services["revision"] = self._editing.revision + 1
            services, self._pending_project_services = self._pending_project_services, None
            self._adopt_services(services)
            return {"project": services["project"], "state": self._editing.state()}
        except EditingError:
            raise
        except FileExistsError as exc:
            raise WorkspaceError("FILE_EXISTS", str(exc)) from exc
        except ExceptionGroup as exc:
            raise WorkspaceError("PROJECT_ROLLBACK_FAILED", str(exc)) from exc
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            raise WorkspaceError("PROJECT_CREATE_FAILED", f"新建工程未完成：{exc}") from exc

    def _current_tree(self) -> list[dict]:
        # Tree refresh is observational; a failure after a committed command must
        # not turn its response into a false mutation failure and invite replay.
        if self._session.project is None:
            return []
        try:
            self._last_tree = self._tree(self._session.project)
        except (OSError, ValueError):
            logging.getLogger(__name__).exception("内容已更新，工程树刷新失败；请刷新资源")
        return deepcopy(self._last_tree)

    @staticmethod
    def _active_content_path(change: dict) -> str | None:
        return change["beforePath"] if change["undo"] else change["afterPath"]

    def _content_action(self, action: str, payload: dict) -> dict:
        if self._content_actions is None or self._session.project is None:
            raise WorkspaceError("NO_PROJECT", "请先打开工程。")
        allowed = {
            "create_content": {"kind", "name", "category", "overwrite", "expectedRevision", "decision"},
            "rename_content": {"path", "newName", "expectedRevision", "decision"},
            "delete_content": {"path", "confirmed", "expectedRevision", "decision"},
            "reveal_content": {"path", "expectedRevision"},
        }[action]
        if set(payload) - allowed:
            raise WorkspaceError("INVALID_REQUEST", "内容操作参数无效。")
        if payload.get("decision") not in (None, "save", "discard"):
            raise WorkspaceError("INVALID_REQUEST", "请选择保存、放弃或取消内容操作。")
        self._editing.check_revision(payload)
        service = self._content_actions
        try:
            if action == "create_content":
                name, category, kind = payload.get("name"), payload.get("category"), payload.get("kind")
                service._name(name)
                if type(payload.get("overwrite", False)) is not bool:
                    raise ValueError("覆盖确认必须为布尔值。")
                choices = {row["id"]: {item["kind"] for item in row["templates"]} for row in service.catalogue()["categories"]}
                if not isinstance(category, str) or category not in choices or not isinstance(kind, str) or kind not in choices[category]:
                    raise ValueError("模板与内容类别不匹配。")
                path = f"content/{category}/{name}.json"
                target = service._content_path(path)
                if target.exists() and not payload.get("overwrite", False):
                    raise FileExistsError("内容已存在，请确认覆盖所选类别内的文件。")
                paths = [path]
            else:
                path = payload.get("path")
                target = service.reveal_path(path)
                paths = [path]
                if action == "reveal_content":
                    if self._reveal_file is None:
                        raise ValueError("系统文件定位尚未就绪。")
                    self._reveal_file(target)
                    return {"state": self._editing.state(), "revealed": True}
                if action == "delete_content" and payload.get("confirmed") is not True:
                    raise ValueError("请明确确认删除内容。")
                if action == "rename_content":
                    service._name(payload.get("newName"))
                    new_path = str(Path(path).with_name(payload["newName"] + ".json")).replace("\\", "/")
                    if new_path != path and service._content_path(new_path).exists():
                        raise FileExistsError("目标内容已存在，不能重命名。")
                    if new_path == path:
                        change = {"action": "rename", "beforePath": path, "afterPath": path, "undo": False}
                        return {"state": self._editing.state(), "tree": self._current_tree(), "change": change, "activePath": path}
                    paths.append(new_path)
            self._content_identity.prepare(paths, payload.get("decision"))
            if action == "create_content":
                service.create(kind, name, category, payload.get("overwrite", False))
            elif action == "rename_content":
                service.rename(path, payload["newName"])
            else:
                service.delete(path)
            change = self._content_identity.consume_change()
            return {"state": self._editing.state(), "tree": self._current_tree(), "change": change,
                    "activePath": self._active_content_path(change)}
        except EditingError:
            raise
        except FileExistsError as exc:
            raise WorkspaceError("FILE_EXISTS", str(exc), payload.get("path")) from exc
        except ExceptionGroup as exc:
            raise WorkspaceError("CONTENT_ROLLBACK_FAILED", str(exc), payload.get("path")) from exc
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            raise WorkspaceError("CONTENT_FAILED", f"内容操作未完成：{exc}", payload.get("path")) from exc

    def _resource_changed(self) -> None:
        # Notification is in the command, so undo/redo also invalidate revision.
        self._editing.revision += 1

    def _release_generation_results(self, candidate_id: str | None = None) -> None:
        # Retain small deduplication tombstones, not PNG data after candidate disposal.
        for request_id, (fingerprint, response) in list(self._results.items()):
            data = response.get("data", {})
            candidate = data.get("candidate") if isinstance(data, dict) else None
            if not isinstance(candidate, dict) or candidate_id is not None and candidate.get("candidateId") != candidate_id:
                continue
            expired = self._expired_result(response)
            size = len(json.dumps(expired, ensure_ascii=True).encode("utf-8"))
            self._result_bytes += size - self._result_sizes[request_id]
            self._result_sizes[request_id] = size
            self._results[request_id] = (fingerprint, expired)

    def _release_reference_results(self, source_id: str | None = None) -> None:
        # Released sources must not be revived by recovery of an earlier open.
        for request_id, (fingerprint, response) in list(self._results.items()):
            data = response.get("data", {})
            source = data.get("source") if isinstance(data, dict) else None
            if not isinstance(source, dict) or source_id is not None and source.get("sourceId") != source_id:
                continue
            expired = self._expired_result(response)
            size = len(json.dumps(expired, ensure_ascii=True).encode("utf-8"))
            self._result_bytes += size - self._result_sizes[request_id]
            self._result_sizes[request_id] = size
            self._results[request_id] = (fingerprint, expired)

    def _reference_action(self, action: str, payload: dict) -> dict:
        service = self._reference_projects
        if service is None:
            raise WorkspaceError("NO_PROJECT", "请先打开工程。")
        allowed = {
            "reference_sources": set(),
            "open_reference": {"kind", "expectedRevision"},
            "reference_candidates_for_compare": {"sourceId", "category", "query", "offset"},
            "compare_reference": {"sourceId", "category", "name", "path", "expectedRevision"},
            "release_reference": {"sourceId"},
        }[action]
        if set(payload) - allowed:
            raise WorkspaceError("INVALID_REQUEST", "参考请求参数无效，来源必须通过系统选择。")
        if action == "open_reference":
            if payload.get("kind") not in ("folder", "zip"):
                raise WorkspaceError("INVALID_REQUEST", "请选择目录或 ZIP 参考。")
        elif action != "reference_sources":
            required = ["sourceId"]
            if action != "release_reference":
                required.append("category")
            if action == "compare_reference":
                required.extend(("name", "path"))
            if any(not isinstance(payload.get(key), str) or not payload[key] for key in required):
                raise WorkspaceError("INVALID_REQUEST", "参考来源、类别或内容标识无效。")
        if action == "reference_candidates_for_compare":
            query, offset = payload.get("query", ""), payload.get("offset", 0)
            if not isinstance(query, str) or len(query) > 256 or type(offset) is not int or offset < 0:
                raise WorkspaceError("INVALID_REQUEST", "参考搜索或分页参数无效。")
        if action in ("open_reference", "compare_reference"):
            self._editing.check_revision(payload)
        try:
            if action == "reference_sources":
                return {"sources": service.sources()}
            if action == "open_reference":
                chooser = self._choose_directory if payload["kind"] == "folder" else self._choose_reference_zip
                if chooser is None:
                    raise WorkspaceError("DIALOG_UNAVAILABLE", "参考选择器尚未就绪，请稍后重试。")
                state = self._editing.state()
                selected = chooser()
                if selected is None:
                    return {"state": state, "source": None}
                source = service.open_folder(Path(selected)) if payload["kind"] == "folder" else service.open_zip(Path(selected))
                return {"state": state, "source": source}
            if action == "reference_candidates_for_compare":
                return service.candidates(payload["sourceId"], payload["category"], query, offset)
            if action == "compare_reference":
                content = self._editing.require_content(payload["path"])
                return service.compare(payload["sourceId"], payload["category"], payload["name"],
                                       content.data, payload["path"], self._editing.revision)
            service.release(payload["sourceId"])
            self._release_reference_results(payload["sourceId"])
            return {"released": True}
        except EditingError:
            raise
        except (OSError, ValueError, TypeError, RuntimeError) as exc:
            raise WorkspaceError("REFERENCE_FAILED", f"参考操作未完成：{exc}") from exc

    def _generation_action(self, action: str, payload: dict) -> dict:
        if self._generation is None:
            raise WorkspaceError("NO_PROJECT", "请先打开工程。")
        allowed = {"path", "outputs", "expectedRevision"} if action == "preview_generation" else (
            {"candidateId", "overwrite", "expectedRevision"} if action == "confirm_generation" else {"candidateId", "expectedRevision"})
        if set(payload) - allowed:
            raise WorkspaceError("INVALID_REQUEST", "贴图生成参数无效。")
        try:
            if action == "cancel_generation":
                candidate_id = payload.get("candidateId")
                self._generation.cancel(candidate_id)
                self._release_generation_results(candidate_id)
                return {"state": self._editing.state(), "cancelled": True}
            self._editing.check_revision(payload)
            if action == "preview_generation":
                candidate = self._generation.preview(payload.get("path"), payload.get("outputs"))
                return {"state": self._editing.state(), "candidate": candidate}
            candidate_id = payload.get("candidateId")
            result = self._generation.confirm(candidate_id, overwrite=payload.get("overwrite", False))
            self._release_generation_results(candidate_id)
            return {"state": self._editing.state(), "outputs": result["outputs"]}
        except EditingError:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise WorkspaceError("GENERATION_FAILED", f"贴图生成未完成：{exc}") from exc

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
        return self._editing.opened(path, self._load_content(path))

    def _load_content(self, path: object) -> ContentData | RawDocument:
        target = self._content_path(path)
        existing = self._editing.entry(path)
        if existing is not None:
            return existing
        registered = self._session.loaded_content(path[8:])
        if registered is not None:
            return registered
        try:
            text = self._read_source_text(target)
        except (OSError, ValueError) as exc:
            raise WorkspaceError("DOCUMENT_READ_FAILED", "无法读取此内容，请检查大小、编码、路径和访问权限。", path) from exc
        try:
            data = SourceEditingService._decode(text)
        except ValueError as exc:
            content = RawDocument(target.stem, path.split("/")[1], target, text, SourceEditingService.error_details(exc))
        else:
            content = ContentData(target.stem, path.split("/")[1], data, target)
            self._session.attach_content(path[8:], content)
        return content

    @staticmethod
    def _read_source_text(target: Path) -> str:
        with target.open("rb") as stream:
            raw = stream.read(SourceEditingService.MAX_BYTES + 1)
        if len(raw) > SourceEditingService.MAX_BYTES:
            raise ValueError("内容大小超过允许上限")
        text = raw.decode("utf-8")
        if "\x00" in text:
            raise ValueError("内容不是可编辑的 UTF-8 文本")
        return text

    def _content_path(self, path: object) -> Path:
        if self._session.project is None:
            raise WorkspaceError("NO_PROJECT", "请先打开工程。")
        if (not isinstance(path, str) or len(path) > 4096 or not path.startswith("content/")
                or any(c in path for c in ("\\", ":", "\x00"))):
            raise WorkspaceError("INVALID_PATH", "请选择工程内容文件。")
        parts = path.split("/")
        if (len(parts) != 3 or parts[1] not in ("units", "blocks", "weapons")
                or not parts[2].endswith(".json") or parts[2] in (".json", "..")):
            raise WorkspaceError("INVALID_PATH", "内容路径不在支持的分类内。", path)
        try:
            root = self._session.project.root.resolve()
            target = (root / path).resolve()
            if not target.is_relative_to(root) or not target.is_relative_to((root / "content").resolve()):
                raise ValueError("Content escapes project")
        except (OSError, ValueError) as exc:
            raise WorkspaceError("DOCUMENT_READ_FAILED", "无法读取此内容，请检查 JSON 格式、路径和文件访问权限。", path) from exc
        return target

    def _content(self, path: object):
        content = self._load_content(path)
        if isinstance(content, RawDocument):
            raise WorkspaceError("SOURCE_INVALID", "当前源码无效，请先修复 JSON。", path, content.source_error)
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
                        data = SourceEditingService._decode(self._read_source_text(file))
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
