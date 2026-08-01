"""字段组的缓存 / 恢复 / 移除——能力开关组与添加字段组共用的数据操作。

本模块不 import Qt。所有数据变更通过传入的 CommandStack 执行（符合
AGENTS.md "数据变更走命令栈" 约束）。

提取动机：editor_panel 里"把一组字段写回 / 移出 data"的逻辑曾在三处
（能力勾选、能力联动、添加字段组）各抄一遍，且是历史 bug 高发区
（缓存丢失、存在标记漏写）。集中到一个深模块后，三处调用各剩一行，
bug 只需修一次，且可脱离 GUI 用 pytest 直接验证。

字段值解析优先级：缓存值 → 组配置 defaults → 类型零值（type_default）。
"""

from __future__ import annotations

from typing import Any, Callable

from .commands import CommandStack, DeleteFieldCommand, SetFieldCommand
from .form_plan import type_default
from .metadata import ClassDef


def group_field_names(group_def: dict) -> list[str]:
    """组内全部字段名 = required + default + optional（保序）。"""
    return (
        list(group_def.get("required", []))
        + list(group_def.get("default", []))
        + list(group_def.get("optional", []))
    )


def _find_field(class_def: ClassDef | None, field_name: str):
    if class_def is None:
        return None
    for f in class_def.fields:
        if f.name == field_name:
            return f
    return None


def resolve_field_value(
    field_name: str,
    group_def: dict,
    cached: dict[str, Any],
    class_def: ClassDef | None,
) -> Any:
    """按 缓存 → 组 defaults → 类型零值 的优先级解析字段初始值。"""
    if field_name in cached:
        return cached[field_name]
    defaults = group_def.get("defaults", {})
    if field_name in defaults:
        return defaults[field_name]
    field_def = _find_field(class_def, field_name)
    return type_default(field_def) if field_def else None


def cache_group_fields(data: dict, group_def: dict) -> dict[str, Any]:
    """收集组内当前存在于 data 的字段值（纯读取，不改 data）。"""
    return {name: data[name] for name in group_field_names(group_def) if name in data}


def restore_group_fields(
    data: dict,
    group_def: dict,
    cached: dict[str, Any],
    class_def: ClassDef | None,
    commands: CommandStack,
    on_change: Callable[[], None] | None,
    *,
    restore_optional: bool = True,
    existence_marker: bool = True,
) -> None:
    """把组字段写回 data（走命令栈，可撤销）。

    - required + default 级：缓存 → defaults → 零值
    - restore_optional=True：额外恢复 optional 级中缓存里有的字段
    - existence_marker=True：若写完整组仍无任何字段，写第一个 optional 作存在标记
      （能力组靠"至少有一个字段"来判定启用，见 form_plan）

    能力联动用 restore_optional=False, existence_marker=False（只补 required+default）。
    """
    required = list(group_def.get("required", []))
    default = list(group_def.get("default", []))
    optional = list(group_def.get("optional", []))

    for field_name in required + default:
        if field_name not in data:
            val = resolve_field_value(field_name, group_def, cached, class_def)
            commands.execute(SetFieldCommand(
                data=data, path=field_name, new_value=val, on_change=on_change,
            ))

    if restore_optional:
        for field_name, val in cached.items():
            if field_name not in data and field_name in optional:
                commands.execute(SetFieldCommand(
                    data=data, path=field_name, new_value=val, on_change=on_change,
                ))

    if existence_marker:
        written = any(fn in data for fn in required + default + optional)
        if not written and optional:
            first_opt = optional[0]
            if first_opt not in data:
                val = resolve_field_value(first_opt, group_def, cached, class_def)
                commands.execute(SetFieldCommand(
                    data=data, path=first_opt, new_value=val, on_change=on_change,
                ))


def remove_group_fields(
    data: dict,
    group_def: dict,
    commands: CommandStack,
    on_change: Callable[[], None] | None,
) -> None:
    """移除组内所有存在于 data 的字段（走命令栈，可撤销）。"""
    for name in group_field_names(group_def):
        if name in data:
            commands.execute(DeleteFieldCommand(
                data=data, path=name, on_change=on_change,
            ))
