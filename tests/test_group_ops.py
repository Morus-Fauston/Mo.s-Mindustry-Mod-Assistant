"""字段组缓存/恢复/移除测试——脱离 Qt 验证（优化5 提取的核心收益）。

覆盖历史 bug 高发区：
- 缓存值优先于 defaults
- optional 级缓存恢复
- 存在标记（能力组靠"至少一个字段"判定启用）
- 移除字段走命令栈可撤销
"""

from __future__ import annotations

from app.core.commands import CommandStack
from app.core.group_ops import (
    cache_group_fields,
    group_field_names,
    remove_group_fields,
    resolve_field_value,
    restore_group_fields,
)
from app.core.metadata import ClassDef, FieldDef


def _class() -> ClassDef:
    return ClassDef(
        name="UnitType",
        full_name="mindustry.type.UnitType",
        parent=None,
        fields=[
            FieldDef(name="mineSpeed", java_type="float", mode="PRIMITIVE"),
            FieldDef(name="mineTier", java_type="int", mode="PRIMITIVE"),
            FieldDef(name="mineHardnessScaling", java_type="boolean", mode="PRIMITIVE"),
        ],
    )


# 采矿组：mineSpeed(required) + mineTier(default) + mineHardnessScaling(optional)
_GROUP = {
    "required": ["mineSpeed"],
    "default": ["mineTier"],
    "optional": ["mineHardnessScaling"],
    "defaults": {"mineSpeed": 1.0, "mineTier": 1},
}


class TestGroupFieldNames:
    def test_concat_order(self):
        assert group_field_names(_GROUP) == [
            "mineSpeed", "mineTier", "mineHardnessScaling",
        ]

    def test_missing_keys_treated_empty(self):
        assert group_field_names({"required": ["a"]}) == ["a"]


class TestResolveFieldValue:
    def test_cached_wins_over_defaults(self):
        cached = {"mineSpeed": 9.9}
        assert resolve_field_value("mineSpeed", _GROUP, cached, _class()) == 9.9

    def test_defaults_when_no_cache(self):
        assert resolve_field_value("mineSpeed", _GROUP, {}, _class()) == 1.0

    def test_type_zero_when_no_cache_no_default(self):
        # mineHardnessScaling 无缓存无 default → boolean 零值 False
        val = resolve_field_value("mineHardnessScaling", _GROUP, {}, _class())
        assert val is False

    def test_none_when_field_unknown(self):
        assert resolve_field_value("ghost", _GROUP, {}, _class()) is None


class TestCacheGroupFields:
    def test_only_existing_fields(self):
        data = {"mineSpeed": 5.0, "unrelated": 1}
        assert cache_group_fields(data, _GROUP) == {"mineSpeed": 5.0}


class TestRestoreGroupFields:
    def test_restores_required_and_default(self):
        data: dict = {}
        stack = CommandStack()
        restore_group_fields(data, _GROUP, {}, _class(), stack, on_change=None)
        assert data["mineSpeed"] == 1.0
        assert data["mineTier"] == 1

    def test_cached_value_used(self):
        data: dict = {}
        stack = CommandStack()
        restore_group_fields(
            data, _GROUP, {"mineSpeed": 7.0}, _class(), stack, on_change=None,
        )
        assert data["mineSpeed"] == 7.0

    def test_optional_cache_restored(self):
        data: dict = {}
        stack = CommandStack()
        restore_group_fields(
            data, _GROUP,
            {"mineSpeed": 1.0, "mineHardnessScaling": True},
            _class(), stack, on_change=None,
        )
        assert data["mineHardnessScaling"] is True

    def test_optional_not_restored_when_disabled(self):
        data: dict = {}
        stack = CommandStack()
        restore_group_fields(
            data, _GROUP,
            {"mineHardnessScaling": True},
            _class(), stack, on_change=None,
            restore_optional=False, existence_marker=False,
        )
        assert "mineHardnessScaling" not in data

    def test_existence_marker_writes_first_optional(self):
        # 空组（无 required/default）+ 无缓存 → 写第一个 optional 作标记
        empty_group = {"optional": ["mineHardnessScaling"]}
        data: dict = {}
        stack = CommandStack()
        restore_group_fields(data, empty_group, {}, _class(), stack, on_change=None)
        assert "mineHardnessScaling" in data

    def test_undo_reverts_restore(self):
        data: dict = {}
        stack = CommandStack()
        restore_group_fields(data, _GROUP, {}, _class(), stack, on_change=None)
        assert "mineSpeed" in data
        # 撤销全部（每字段一条命令）
        while stack.can_undo:
            stack.undo()
        assert "mineSpeed" not in data
        assert "mineTier" not in data


class TestRemoveGroupFields:
    def test_removes_only_group_fields(self):
        data = {"mineSpeed": 5.0, "mineTier": 2, "health": 100}
        stack = CommandStack()
        remove_group_fields(data, _GROUP, stack, on_change=None)
        assert "mineSpeed" not in data
        assert "mineTier" not in data
        assert data["health"] == 100  # 组外字段不动

    def test_undo_restores_removed(self):
        data = {"mineSpeed": 5.0, "mineTier": 2}
        stack = CommandStack()
        remove_group_fields(data, _GROUP, stack, on_change=None)
        while stack.can_undo:
            stack.undo()
        assert data["mineSpeed"] == 5.0
        assert data["mineTier"] == 2
