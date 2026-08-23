"""Unified validation engine.

Interface:
    validate(data, level) -> list[Issue]          — 单 content 验证
    validate_project(project, metadata) -> list[Issue]  — 项目级全量验证（F-51）

Levels:
    'field'   - type checks only (for real-time input validation)
    'content' - + required fields + reference existence
    'project' - + mod.json format + file naming conventions
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .metadata import Metadata, FieldDef
from .field_dependencies import inactive_dependencies

# mod.json name 字段允许的字符（与 project.py 的 _MOD_ID_RE 一致）
_MOD_NAME_RE = re.compile(r"^[a-z0-9-]+$")


@dataclass
class Issue:
    path: str  # e.g. "weapons[0].bullet.damage"
    severity: str  # "error" | "warning"
    message: str
    # 项目级验证附加信息（F-51）：用于报告窗口跳转到对应 content 标签页
    content_name: str = ""  # 关联的 content 名（空 = 不关联）
    field: str = ""  # 关联的字段（空 = 不定位字段）


def validate_project(project, metadata: Metadata) -> list[Issue]:
    """项目级全量验证（F-51）。

    检查项（严重度见规格文档 18.9）：
    - mod.json 存在 / 可解析 / name 非空且合法（error）
    - 每个 content JSON 可解析 / type 存在（error）
    - 同分类下文件名重复（error）
    - 跨文件武器引用存在（error）
    - requirements 物品存在于原版或工程（warning）
    - 精灵图缺失（有 content 无主体 png）（warning）

    不 import Qt（core 层约束）。返回按严重度排序（error 在前）的列表。
    """
    from .project import Project

    if not isinstance(project, Project):
        raise TypeError("validate_project 需要 Project 实例")

    issues: list[Issue] = []

    # ── mod.json ────────────────────────────────────────────────────────
    mod_json = project.root / "mod.json"
    if not mod_json.exists():
        issues.append(Issue("mod.json", "error", "缺少 mod.json"))
    else:
        try:
            import json as _json

            mod_data = _json.loads(mod_json.read_text(encoding="utf-8"))
            if not isinstance(mod_data, dict):
                issues.append(Issue("mod.json", "error", "mod.json 应为 JSON 对象"))
            else:
                mod_name = mod_data.get("name", "")
                if not mod_name:
                    issues.append(Issue("mod.json", "error", "mod.json 缺少 name 字段"))
                elif not _MOD_NAME_RE.match(mod_name):
                    issues.append(Issue(
                        "mod.json", "error",
                        f"mod.json name 非法: {mod_name!r}（须小写字母/数字/连字符）",
                    ))
        except ValueError as e:
            issues.append(Issue("mod.json", "error", f"mod.json 不是合法 JSON: {e}"))

    # ── content 文件 ────────────────────────────────────────────────────
    all_content: list = []
    categories = _project_categories(project)
    for cat in categories:
        cat_dir = project.contents.content_dir / cat
        if not cat_dir.is_dir():
            continue
        for f in sorted(cat_dir.glob("*.json")):
            name = f.stem
            all_content.append((cat, name, f))
            try:
                data = _load_json(f)
            except ValueError as e:
                issues.append(Issue(
                    f"{cat}/{name}.json", "error", f"JSON 解析失败: {e}",
                    content_name=name,
                ))
                continue
            if not data.get("type"):
                issues.append(Issue(
                    f"{cat}/{name}.json", "error", "缺少 type 字段",
                    content_name=name,
                ))
                continue
            # 跨文件武器引用存在性（error）
            _check_weapon_refs(project, cat, name, data, issues)
            # requirements 物品存在性（warning）
            _check_requirements(project, metadata, cat, name, data, issues)
            # 精灵图缺失（warning）
            _check_sprite_missing(project, cat, name, issues)

    # 同分类文件名重复（error）
    _check_duplicate_names(categories, project, issues)

    # error 在前，warning 在后
    issues.sort(key=lambda i: 0 if i.severity == "error" else 1)
    return issues


# ── 辅助 ────────────────────────────────────────────────────────────────


def _load_json(path) -> dict:
    import json as _json

    return _json.loads(path.read_text(encoding="utf-8"))


def _project_categories(project) -> list[str]:
    """列出工程 content 下的所有分类目录。"""
    d = project.contents.content_dir
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir())


def _check_duplicate_names(categories, project, issues: list[Issue]) -> None:
    """同分类下文件名重复（不同目录不算，如 units/x 与 blocks/x）。"""
    for cat in categories:
        cat_dir = project.contents.content_dir / cat
        if not cat_dir.is_dir():
            continue
        seen: dict[str, Path] = {}
        for f in sorted(cat_dir.glob("*.json")):
            name = f.stem
            if name in seen:
                issues.append(Issue(
                    f"{cat}/{name}.json", "error",
                    f"同分类下文件名重复: {name}（{seen[name].name} 与 {f.name}）",
                    content_name=name,
                ))
            else:
                seen[name] = f


def _check_weapon_refs(project, cat, name, data, issues: list[Issue]) -> None:
    """weapons 数组中的 name 引用的武器必须存在（error）。

    只检查**引用模式**条目（无 bullet 键）。内联武器（含 bullet 键的完整
    定义）带 name 是合法标识，游戏会以 modname-name 注册，不查外部文件
    （v0.2.6 修复：模板生成的内联武器曾被误报"引用不存在"）。
    """
    weapons = data.get("weapons")
    if not isinstance(weapons, list):
        return
    known_weapons = set()
    wdir = project.contents.content_dir / "weapons"
    if wdir.is_dir():
        known_weapons = {f.stem for f in wdir.glob("*.json")}
    for i, w in enumerate(weapons):
        if not isinstance(w, dict):
            continue
        # 内联武器：有 bullet 键的完整定义，不做引用检查
        if "bullet" in w:
            continue
        wname = w.get("name", "")
        if wname and wname not in known_weapons:
            issues.append(Issue(
                f"{cat}/{name}.json", "error",
                f"武器引用不存在: {wname}（weapons[{i}].name）",
                content_name=name, field="weapons",
            ))


def _check_requirements(project, metadata, cat, name, data, issues: list[Issue]) -> None:
    """requirements 物品必须存在于原版或工程（warning）。"""
    reqs = data.get("requirements")
    if not isinstance(reqs, list):
        return
    items = {r.get("item") for r in reqs if isinstance(r, dict) and r.get("item")}
    if not items:
        return
    known: set[str] = set()
    try:
        known = set(metadata.list_instances("Items"))
    except Exception:
        pass
    idir = project.contents.content_dir / "items"
    if idir.is_dir():
        known |= {f.stem for f in idir.glob("*.json")}
    for it in sorted(items):
        if it not in known:
            issues.append(Issue(
                f"{cat}/{name}.json", "warning",
                f"requirements 引用的物品不存在: {it}",
                content_name=name, field="requirements",
            ))


def _check_sprite_missing(project, cat, name, issues: list[Issue]) -> None:
    """有 content 无主体 png → warning。"""
    sprite = project.sprite_path(cat, name)
    if not sprite.exists():
        issues.append(Issue(
            f"{cat}/{name}.json", "warning",
            f"缺少主体精灵图: {cat}/{name}.png",
            content_name=name,
        ))


class Validator:
    """Validates content data against metadata definitions."""

    def __init__(self, metadata: Metadata) -> None:
        self._meta = metadata

    def validate(self, data: dict[str, Any], level: str = "content") -> list[Issue]:
        """Validate content data at the specified level."""
        issues: list[Issue] = []

        content_type = data.get("type")
        if not content_type:
            issues.append(Issue("type", "error", "缺少 type 字段"))
            return issues

        # Get class definition
        try:
            class_def = self._meta.get_class(content_type)
        except KeyError:
            issues.append(Issue("type", "error", f"未知类型: {content_type}"))
            return issues

        # Field-level validation
        for field_def in class_def.fields:
            field_issues = self._validate_field(data, field_def)
            issues.extend(field_issues)

        for field, prerequisite in inactive_dependencies(content_type, data).items():
            issues.append(Issue(
                field,
                "warning",
                f"字段当前不生效，前置条件为：{prerequisite}",
                field=field,
            ))

        if level in ("content", "project"):
            # Reference existence checks
            ref_issues = self._validate_references(data, class_def)
            issues.extend(ref_issues)

        return issues

    def validate_field_value(self, field_def: FieldDef, value: Any) -> Issue | None:
        """Validate a single field value (for real-time input checking)."""
        if value is None or value == "":
            if not field_def.nullable:
                return Issue(field_def.name, "error", f"{field_def.name} 为必填项")
            return None

        if field_def.mode == "PRIMITIVE":
            return self._check_primitive(field_def, value)

        return None

    def _validate_field(self, data: dict, field_def: FieldDef) -> list[Issue]:
        issues: list[Issue] = []
        value = data.get(field_def.name)

        # Only validate fields that mods actually set in JSON.
        # Skip internal engine fields (regions, sounds, effects, controllers).
        if field_def.is_internal:
            return issues

        # Mindustry initializes this ObjectSet itself when the key is absent.
        # When a mod explicitly writes it, JSON must keep the Planet-name list
        # shape used by the dedicated form editor and the content parser.
        if field_def.name == "shownPlanets":
            if value is None:
                return issues
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                return [Issue("shownPlanets", "error", "shownPlanets 应为星球标识符数组")]
            try:
                planets = set(self._meta.list_instances("Planets"))
            except Exception:
                planets = set()
            unknown = [planet for planet in value if planets and planet not in planets]
            if unknown:
                return [Issue(
                    "shownPlanets", "error",
                    f"shownPlanets 包含不存在的星球: {unknown[0]}",
                )]
            return issues

        # Required check: only for primitive fields that are non-nullable
        if value is None and not field_def.nullable:
            if field_def.mode == "PRIMITIVE" and field_def.default is None:
                issues.append(Issue(
                    field_def.name, "error",
                    f"{field_def.name} 为必填项"
                ))
            return issues

        if value is None:
            return issues

        # Type check for primitives
        if field_def.mode == "PRIMITIVE":
            issue = self._check_primitive(field_def, value)
            if issue:
                issues.append(issue)

        return issues

    def _check_primitive(self, field_def: FieldDef, value: Any) -> Issue | None:
        java_type = field_def.java_type

        if java_type in ("float", "double", "int", "long", "short"):
            if not isinstance(value, (int, float)):
                return Issue(
                    field_def.name, "error",
                    f"{field_def.name} 应为数字，当前为: {type(value).__name__}"
                )
        elif java_type == "boolean":
            if not isinstance(value, bool):
                return Issue(
                    field_def.name, "error",
                    f"{field_def.name} 应为布尔值"
                )
        elif java_type == "String":
            if not isinstance(value, str):
                return Issue(
                    field_def.name, "error",
                    f"{field_def.name} 应为字符串"
                )

        return None

    def _validate_references(self, data: dict, class_def: Any) -> list[Issue]:
        """Check that STRING_REF fields point to existing instances."""
        issues: list[Issue] = []

        for field_def in class_def.fields:
            if field_def.mode != "STRING_REF" or not field_def.ref_source:
                continue

            value = data.get(field_def.name)
            if value is None or not isinstance(value, str):
                continue

            # Check if the referenced instance exists
            try:
                instances = self._meta.list_instances(field_def.ref_source)
                if value not in instances:
                    issues.append(Issue(
                        field_def.name, "error",
                        f"引用的对象不存在: {value} (在 {field_def.ref_source} 中)"
                    ))
            except Exception:
                pass  # Category not available, skip

        return issues
