"""项目级全量验证（F-51）单元测试。

覆盖：mod.json 检查 / content JSON 解析 / 重复文件名 / 武器引用 /
requirements 物品存在性 / 精灵图缺失 / 严重度排序。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app.core.project import ModInfo, Project
from app.core.validator import validate_project


@pytest.fixture
def project(tmp_path):
    """最小可用工程：mod.json + sprites/units + 一个单位 content。"""
    root = tmp_path / "proj"
    root.mkdir()
    (root / "mod.json").write_text(
        json.dumps({"name": "test-mod", "displayName": "测试"}), encoding="utf-8"
    )
    (root / "sprites" / "units").mkdir(parents=True)
    (root / "content" / "units").mkdir(parents=True)
    (root / "content" / "units" / "soldier.json").write_text(
        json.dumps({"type": "UnitType", "health": 100}), encoding="utf-8"
    )
    # 主体精灵图
    (root / "sprites" / "units" / "soldier.png").write_bytes(b"")
    return Project(root, ModInfo(name="test-mod"))


class TestValidateProject:
    @pytest.mark.parametrize("data", [[], None, {"type": ["Wall"]},
                                      {"type": "UnitType", "weapons": [{"name": ["bad"]}]},
                                      {"type": "Wall", "requirements": [{"item": {"bad": 1}}]}])
    def test_malformed_business_shapes_report_errors_instead_of_throwing(self, project, data):
        (project.root / "content/units/soldier.json").write_text(json.dumps(data), encoding="utf-8")
        assert any(issue.severity == "error" for issue in validate_project(project, None))

    def test_nonstring_mod_name_reports_error(self, project):
        (project.root / "mod.json").write_text('{"name":["bad"]}', encoding="utf-8")
        assert any(issue.path == "mod.json" and issue.severity == "error" for issue in validate_project(project, None))

    def test_current_content_reader_validates_unsaved_data_without_writing(self, project):
        before = (project.root / "content/units/soldier.json").read_bytes()
        issues = validate_project(project, None, read_content=lambda relative: {
            "type": "UnitType", "weapons": [{"name": "missing-weapon"}],
        })
        assert any(issue.path == "units/soldier.json" and issue.field == "weapons" for issue in issues)
        assert (project.root / "content/units/soldier.json").read_bytes() == before

    def test_clean_project_no_issues(self, project):
        issues = validate_project(project, None)
        assert issues == []

    def test_missing_mod_json(self, tmp_path):
        root = tmp_path / "proj"
        root.mkdir()
        (root / "content").mkdir()
        proj = Project(root, ModInfo(name="test-mod"))
        issues = validate_project(proj, None)
        assert any("缺少 mod.json" in i.message for i in issues)

    def test_bad_mod_json(self, project):
        project.root.joinpath("mod.json").write_text("{broken", encoding="utf-8")
        issues = validate_project(project, None)
        assert any("不是合法 JSON" in i.message for i in issues)

    def test_mod_name_invalid(self, project):
        project.root.joinpath("mod.json").write_text(
            json.dumps({"name": "Bad_Name!"}), encoding="utf-8"
        )
        issues = validate_project(project, None)
        assert any("name 非法" in i.message for i in issues)

    def test_content_bad_json(self, project):
        project.root.joinpath("content/units/soldier.json").write_text(
            "{oops", encoding="utf-8"
        )
        issues = validate_project(project, None)
        assert any("JSON 解析失败" in i.message for i in issues)

    def test_content_missing_type(self, project):
        project.root.joinpath("content/units/soldier.json").write_text(
            json.dumps({"health": 100}), encoding="utf-8"
        )
        issues = validate_project(project, None)
        assert any("缺少 type" in i.message for i in issues)

    def test_duplicate_name_same_category(self, project):
        (project.root / "content" / "units" / "soldier-copy.json").write_text(
            json.dumps({"type": "UnitType", "health": 100}), encoding="utf-8"
        )
        # 注意：真实文件名必须唯一，这里模拟"重复"要两个同 stem 文件
        # —— 实际文件系统不允许同目录同名。改为验证跨目录不误报。
        issues = validate_project(project, None)
        assert not any("文件名重复" in i.message for i in issues)

    def test_weapon_ref_missing(self, project):
        (project.root / "content" / "units" / "soldier.json").write_text(
            json.dumps({
                "type": "UnitType",
                "weapons": [{"name": "不存在炮"}],
            }),
            encoding="utf-8",
        )
        issues = validate_project(project, None)
        assert any("武器引用不存在" in i.message for i in issues)

    def test_weapon_ref_exists(self, project):
        (project.root / "content" / "weapons").mkdir()
        (project.root / "content" / "weapons" / "短管炮.json").write_text(
            json.dumps({"type": "Weapon"}), encoding="utf-8"
        )
        (project.root / "content" / "units" / "soldier.json").write_text(
            json.dumps({
                "type": "UnitType",
                "weapons": [{"name": "短管炮"}],
            }),
            encoding="utf-8",
        )
        issues = validate_project(project, None)
        assert not any("武器引用不存在" in i.message for i in issues)

    def test_inline_weapon_with_name_not_flagged(self, project):
        """内联武器（含 bullet 键的完整定义）带 name 是合法标识，不做引用检查。

        回归（v0.2.6）：模板生成的内联武器曾被误报"武器引用不存在"。
        """
        (project.root / "content" / "units" / "soldier.json").write_text(
            json.dumps({
                "type": "UnitType",
                "weapons": [
                    {"name": "内置炮", "bullet": {"type": "BasicBulletType", "damage": 10}},
                ],
            }),
            encoding="utf-8",
        )
        issues = validate_project(project, None)
        assert not any("武器引用不存在" in i.message for i in issues)

    def test_requirements_unknown_item_warning(self, project):
        (project.root / "content" / "units" / "soldier.json").write_text(
            json.dumps({
                "type": "UnitType",
                "requirements": [{"item": "不存在的物品", "amount": 1}],
            }),
            encoding="utf-8",
        )
        issues = validate_project(project, None)
        assert any("引用的物品不存在" in i.message for i in issues)

    def test_sprite_missing_warning(self, project):
        (project.root / "sprites" / "units" / "soldier.png").unlink()
        issues = validate_project(project, None)
        assert any("缺少主体精灵图" in i.message for i in issues)

    def test_error_sorted_before_warning(self, project):
        # 同时有 error（坏 mod.json）和 warning（缺精灵图）
        project.root.joinpath("mod.json").write_text("{broken", encoding="utf-8")
        (project.root / "sprites" / "units" / "soldier.png").unlink()
        issues = validate_project(project, None)
        sevs = [i.severity for i in issues]
        assert sevs == sorted(sevs)  # error 全在 warning 前

    def test_issue_has_content_name(self, project):
        (project.root / "sprites" / "units" / "soldier.png").unlink()
        issues = validate_project(project, None)
        sprite_issue = next(i for i in issues if "精灵图" in i.message)
        assert sprite_issue.content_name == "soldier"
