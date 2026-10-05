"""Source edits share real metadata, nested identities and the session stack."""

from copy import deepcopy
import json
import os

import pytest

from app.core.commands import CommandStack
from app.core.content_store import ContentData
from app.core.metadata import Metadata
from app.desktop.forms import FormService
from app.desktop.nested_forms import NestedFormService
from app.desktop.source_editing import SourceEditingService


PATH = "content/weapons/gun.json"


def test_expanded_save_representation_is_bounded_before_accepting_source():
    source = '{"x":' + '[' * 60 + '[' + ','.join('0' for _ in range(40000)) + ']' + ']' * 60 + '}'
    assert len(source) < SourceEditingService.MAX_BYTES
    with pytest.raises(ValueError, match="保存大小"):
        SourceEditingService._decode(source)


def test_source_save_budget_includes_writer_newline(monkeypatch):
    source = '{"name":"中文"}'
    saved = (SourceEditingService.encode(json.loads(source)).replace('\n', os.linesep) + os.linesep).encode('utf-8')
    monkeypatch.setattr(SourceEditingService, 'MAX_BYTES', len(saved) - 1)
    with pytest.raises(ValueError, match="保存大小"):
        SourceEditingService._decode(source)
    monkeypatch.setattr(SourceEditingService, 'MAX_BYTES', len(saved))
    assert SourceEditingService._decode(source) == {"name": "中文"}


def setup(data, category="weapons"):
    metadata = Metadata("metadata")
    nested = NestedFormService(metadata, FormService(metadata))
    content = ContentData("gun", category, data)
    return SourceEditingService(nested), nested, content, CommandStack()


def test_source_parse_is_read_only_until_one_command_executes_and_undo_keeps_dictionary_identity():
    service, nested, content, stack = setup({"bullet": {"damage": 12}})
    original, shared = deepcopy(content.data), content.data
    state = nested.snapshot(PATH)
    command = service.parse(content, PATH, '{"bullet":{"damage":27},"自定义":{"keep":[1,true,null]}}')
    assert content.data == original and nested.snapshot(PATH) == state
    stack.execute(command)
    assert content.data is shared
    assert content.data == {"bullet": {"damage": 27}, "自定义": {"keep": [1, True, None]}}
    stack.undo()
    assert content.data is shared and content.data == original
    assert not stack.can_undo
    stack.redo()
    assert content.data["bullet"]["damage"] == 27


@pytest.mark.parametrize("text", ['{"bullet":', '[1,2]', 'null', 'true', '42', '"text"',
    '{"health":NaN}', '{"nested":[Infinity]}', '{"health":-Infinity}', '{"health":1e400}',
    '{"text":"\\ud800"}', None, 42])
def test_invalid_json_and_unsafe_values_keep_data_and_form_memory(text):
    service, nested, content, stack = setup({"bullet": {"damage": 12}})
    nested.plan(content, PATH)
    before_data, before_state = deepcopy(content.data), nested.snapshot(PATH)
    with pytest.raises(ValueError, match="[\u4e00-\u9fff]"):
        service.parse(content, PATH, text)
    assert content.data == before_data
    assert nested.snapshot(PATH) == before_state
    assert not stack.can_undo


def test_syntax_error_reports_line_and_column():
    service, _, content, _ = setup({})
    with pytest.raises(ValueError, match=r"第 3 行第 1 列"):
        service.parse(content, PATH, '{\n"health":\n}')


def test_size_depth_and_node_budgets_are_bounded_before_command_creation():
    service, nested, content, stack = setup({})
    too_large = json.dumps({"未知字段": "中" * (service.MAX_BYTES // 3 + 1)}, ensure_ascii=False)
    with pytest.raises(ValueError, match="大小"):
        service.parse(content, PATH, too_large)
    deep = '{"x":' + '[' * service.MAX_DEPTH + '0' + ']' * service.MAX_DEPTH + '}'
    with pytest.raises(ValueError, match="嵌套"):
        service.parse(content, PATH, deep)
    many = '{"x":[' + ','.join('0' for _ in range(service.MAX_NODES)) + ']}'
    with pytest.raises(ValueError, match="节点"):
        service.parse(content, PATH, many)
    assert content.data == {} and not stack.can_undo


def fields(plan):
    return {item["name"]: item for group in plan["groups"] for item in group["fields"]}


def test_source_reordering_replaces_item_ids_and_undo_recovers_original_array_addresses():
    service, nested, content, stack = setup({"bullet": {"spawnBullets": [{"damage": 1}, {"damage": 2}]}})
    plan = nested.plan(content, PATH)
    old_items = fields(fields(plan)["bullet"]["child"])["spawnBullets"]["items"]
    old_ids = [item["itemId"] for item in old_items]
    before = nested.snapshot(PATH)
    command = service.parse(content, PATH, '{"bullet":{"spawnBullets":[{"damage":2},{"damage":1}]}}')
    assert nested.snapshot(PATH) == before
    stack.execute(command)
    plan = nested.plan(content, PATH)
    new_ids = [item["itemId"] for item in fields(fields(plan)["bullet"]["child"])["spawnBullets"]["items"]]
    assert not set(old_ids) & set(new_ids)
    with pytest.raises(ValueError):
        nested.command("set_field", content, PATH, {"objectPath": ["bullet", "spawnBullets", {"itemId": old_ids[0]}], "field": "damage", "value": 99})
    stack.undo()
    assert nested.snapshot(PATH) == before
    edit = nested.command("set_field", content, PATH, {"objectPath": ["bullet", "spawnBullets", {"itemId": old_ids[0]}], "field": "damage", "value": 7})
    stack.execute(edit)
    assert [item["damage"] for item in content.data["bullet"]["spawnBullets"]] == [7, 2]


def test_source_replaces_capability_memory_and_undo_restores_cached_user_values():
    service, nested, content, stack = setup({"type": "mech", "health": 100, "mineSpeed": 7}, "units")
    nested.plan(content, PATH)
    stack.execute(nested.command("set_capability", content, PATH, {"group": "mining", "enabled": False}))
    before = nested.snapshot(PATH)
    assert before.root.cached["mining"]["mineSpeed"] == 7
    stack.execute(service.parse(content, PATH, '{"type":"mech","health":200,"mineSpeed":11}'))
    assert nested.snapshot(PATH).root.cached == {}
    assert content.data["mineSpeed"] == 11
    stack.undo()
    assert nested.snapshot(PATH) == before
    stack.execute(nested.command("set_capability", content, PATH, {"group": "mining", "enabled": True}))
    assert content.data["mineSpeed"] == 7


def test_formatting_only_is_noop_but_boolean_is_not_equal_to_number():
    service, nested, content, stack = setup({"type": "mech", "health": 1}, "units")
    before = nested.snapshot(PATH)
    assert service.parse(content, PATH, '{ "health": 1, "type": "mech" }') is None
    assert nested.snapshot(PATH) == before
    stack.execute(service.parse(content, PATH, '{"type":"mech","health":true}'))
    assert content.data["health"] is True
    stack.undo()
    assert type(content.data["health"]) is int


@pytest.mark.parametrize("replacement", [
    {"type": "UnknownCustomType", "unknown": {"key": [1, "value", None]}},
    {"type": "mech", "health": "not a number", "custom": 3},
    {"type": {"invalid": "business type"}, "unknown": 7},
    {"type": "Wall", "itemDrop": "missing-reference", "size": -12},
])
def test_legal_json_business_errors_and_unknown_values_are_not_a_write_gate(replacement):
    service, nested, content, stack = setup({"type": "mech", "health": 100}, "units")
    stack.execute(service.parse(content, PATH, json.dumps(replacement)))
    assert content.data == replacement


def test_real_nested_plan_diagnostics_do_not_mutate_valid_data_or_block_source():
    service, nested, content, stack = setup({"bullet": {"damage": 12}})
    before = nested.snapshot(PATH)
    text = '{"bullet":{"damage":"bad"},"keep":{"unknown":true}}'
    issues = service.diagnostics(content, PATH, text)
    assert any(item["field"] == "damage" and item["objectPath"] == ["bullet"] and item["severity"] == "error" for item in issues)
    assert content.data["bullet"]["damage"] == 12 and nested.snapshot(PATH) == before
    stack.execute(service.parse(content, PATH, text))
    assert content.data["bullet"]["damage"] == "bad"


def test_unavailable_form_metadata_is_diagnostic_not_rejection_of_valid_json(monkeypatch):
    service, nested, content, stack = setup({"bullet": {"damage": 12}})
    def unavailable(_name):
        raise OSError("metadata unavailable")
    monkeypatch.setattr(nested.metadata, "get_class", unavailable)
    text = '{"bullet":{"damage":30},"unknown":"kept"}'
    assert service.diagnostics(content, PATH, text)
    stack.execute(service.parse(content, PATH, text))
    assert content.data["unknown"] == "kept"


def test_source_then_nested_form_edit_undo_in_same_stack_and_other_document_state_is_untouched():
    service, nested, content, stack = setup({"bullet": {"damage": 12}})
    other_path = "content/weapons/other.json"
    other = ContentData("other", "weapons", {"bullet": {"spawnBullets": [{"damage": 8}]}})
    nested.plan(other, other_path)
    other_state = nested.snapshot(other_path)
    identity = content.data
    stack.execute(service.parse(content, PATH, '{"bullet":{"damage":30}}'))
    source_state = nested.snapshot(PATH)
    stack.execute(nested.command("set_field", content, PATH, {"objectPath": ["bullet"], "field": "damage", "value": 45}))
    assert content.data["bullet"]["damage"] == 45
    stack.undo()
    assert content.data["bullet"]["damage"] == 30 and nested.snapshot(PATH) == source_state
    stack.undo()
    assert content.data["bullet"]["damage"] == 12 and content.data is identity
    assert nested.snapshot(other_path) == other_state


@pytest.mark.parametrize("fail_undo", [False, True])
def test_form_state_failure_rolls_back_whole_source_transaction(monkeypatch, fail_undo):
    service, nested, content, stack = setup({"bullet": {"damage": 12}})
    command = service.parse(content, PATH, '{"bullet":{"damage":30}}')
    if fail_undo:
        stack.execute(command)
    before_data, before_state = deepcopy(content.data), nested.snapshot(PATH)
    original_restore, calls = nested.restore, []
    def fail_once(path, state):
        original_restore(path, state)
        calls.append(path)
        if len(calls) == 1:
            raise ValueError("状态恢复失败")
    monkeypatch.setattr(nested, "restore", fail_once)
    with pytest.raises(ValueError, match="状态恢复失败"):
        stack.undo() if fail_undo else stack.execute(command)
    assert content.data == before_data and nested.snapshot(PATH) == before_state
    assert stack.can_undo is fail_undo


def test_deep_brackets_and_escapes_inside_string_do_not_count_as_nesting():
    service, _, content, stack = setup({})
    value = '[' * 1000 + '"\\quoted\\"' + '}' * 1000
    stack.execute(service.parse(content, PATH, json.dumps({"custom": value})))
    assert content.data["custom"] == value


def test_source_rollback_failure_reports_both_errors_without_recording_history(monkeypatch):
    service, nested, content, stack = setup({"bullet": {"damage": 12}})
    identity = content.data
    command = service.parse(content, PATH, '{"bullet":{"damage":30}}')
    failures = [ValueError("首次状态失败"), RuntimeError("回滚状态失败")]
    def fail_restore(path, state):
        raise failures.pop(0)
    monkeypatch.setattr(nested, "restore", fail_restore)
    with pytest.raises(ExceptionGroup, match="恢复原状态也失败") as caught:
        stack.execute(command)
    assert [str(error) for error in caught.value.exceptions] == ["首次状态失败", "回滚状态失败"]
    assert content.data is identity and content.data == {"bullet": {"damage": 12}}
    assert not stack.can_undo
