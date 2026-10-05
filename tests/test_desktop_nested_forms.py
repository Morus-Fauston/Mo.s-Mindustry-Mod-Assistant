"""Nested public forms use one real root dictionary and session command stack."""

from copy import deepcopy

import pytest

from app.core.commands import CommandStack
from app.core.content_store import ContentData
from app.core.metadata import Metadata
from app.desktop.forms import FormService
from app.desktop.nested_forms import NestedFormService


PATH = "content/weapons/gun.json"


def setup(data, category="weapons"):
    metadata = Metadata("metadata")
    forms = FormService(metadata)
    service = NestedFormService(metadata, forms)
    content = ContentData("gun", category, data)
    return service, content, CommandStack()


def fields(plan):
    return {field["name"]: field for group in plan["groups"] for field in group["fields"]}


def apply(service, content, stack, action, **payload):
    command = service.command(action, content, PATH, payload)
    if command is not None:
        stack.execute(command)
    return command


def test_replace_saved_snapshot_restores_all_sidecars_and_preserves_root_identity():
    service, content, stack = setup({"bullet": {"damage": 12}})
    service.plan(content, PATH)
    saved_data, saved_state = deepcopy(content.data), service.snapshot(PATH)
    assert service.replace(content, PATH, saved_data, saved_state) is None
    apply(service, content, stack, "set_field", objectPath=["bullet"], field="damage", value=18)
    changed_data, changed_state = deepcopy(content.data), service.snapshot(PATH)
    changed_state.item_ids['["custom"]'] = ["a" * 32]
    service.restore(PATH, changed_state)
    identity = content.data
    command = service.replace(content, PATH, saved_data, saved_state)
    assert content.data == changed_data and service.snapshot(PATH) == changed_state
    stack.execute(command)
    assert content.data is identity and content.data == saved_data
    assert service.snapshot(PATH) == saved_state
    stack.undo()
    assert content.data is identity and content.data == changed_data
    assert service.snapshot(PATH) == changed_state
    stack.redo()
    assert content.data == saved_data and service.snapshot(PATH) == saved_state
    changed_state = service.snapshot(PATH)
    changed_state.item_ids['["custom"]'] = ["b" * 32]
    assert service.replace(content, PATH, saved_data, changed_state) is not None


def test_type_switch_preserves_unknown_keys_and_undo_restores_missing_type():
    service, content, stack = setup({"bullet": {"damage": 12, "customUnknown": {"keep": 1}}})
    before = deepcopy(content.data)
    plan = service.plan(content, PATH)
    bullet = fields(plan)["bullet"]["child"]
    assert bullet["objectPath"] == ["bullet"]
    assert bullet["typeSelector"]["value"] is None
    assert "LaserBulletType" in {item["value"] for item in bullet["typeSelector"]["choices"]}
    assert content.data == before
    apply(service, content, stack, "set_type", objectPath=["bullet"], type="LaserBulletType")
    assert content.data["bullet"] == {"type": "LaserBulletType", "damage": 12, "customUnknown": {"keep": 1}}
    stack.undo()
    assert content.data == before
    stack.redo()
    assert content.data["bullet"]["type"] == "LaserBulletType"


def test_nested_primitives_references_and_unit_switch_share_existing_rules():
    service, content, stack = setup({"bullet": {"type": "BasicBulletType", "damage": 12, "status": "burning"}})
    apply(service, content, stack, "set_field", objectPath=["bullet"], field="damage", text="15.5")
    assert content.data["bullet"]["damage"] == 15.5
    with pytest.raises(ValueError):
        apply(service, content, stack, "set_field", objectPath=["bullet"], field="damage", text="NaN")
    candidates = service.reference_candidates(content, PATH, {"objectPath": ["bullet"], "field": "status", "query": "burn"})
    assert any(item["value"] == "burning" for item in candidates["candidates"])
    with pytest.raises(ValueError):
        apply(service, content, stack, "set_field", objectPath=["bullet"], field="status", value="copper")
    apply(service, content, stack, "set_field", objectPath=["bullet"], field="status", value="freezing")
    assert content.data["bullet"]["status"] == "freezing"
    stack.undo()
    assert content.data["bullet"]["status"] == "burning"
    unit_service, unit, unit_stack = setup({"type": "mech", "health": 100, "custom": 3}, "units")
    apply(unit_service, unit, unit_stack, "set_type", objectPath=[], type="tank")
    assert unit.data == {"type": "tank", "health": 100, "custom": 3}
    unit_stack.undo()
    assert unit.data["type"] == "mech"


def test_missing_object_is_created_explicitly_in_one_undo_and_unknown_type_is_retained():
    service, content, stack = setup({})
    plan = service.plan(content, PATH)
    assert fields(plan)["bullet"]["canCreate"] is True
    assert content.data == {}
    apply(service, content, stack, "create_object", field="bullet")
    assert content.data == {"bullet": {}}
    stack.undo()
    assert content.data == {}
    stack.redo()
    apply(service, content, stack, "set_type", objectPath=["bullet"], type="BasicBulletType")
    content.data["bullet"]["type"] = "UnknownCustomBullet"
    before = deepcopy(content.data)
    plan = service.plan(content, PATH)
    assert fields(plan)["bullet"]["child"]["knownType"] is False
    assert fields(plan)["bullet"]["child"]["typeSelector"]["value"] == "UnknownCustomBullet"
    assert content.data == before
    with pytest.raises(ValueError):
        apply(service, content, stack, "set_field", objectPath=["bullet"], field="damage", value=10)


def test_object_array_reordering_tracks_duplicate_items_and_undo_restores_tokens():
    service, content, stack = setup({"bullet": {"type": "BasicBulletType", "spawnBullets": [
        {"type": "BasicBulletType", "damage": 1}, {"type": "BasicBulletType", "damage": 1}]}})
    def items():
        return fields(fields(service.plan(content, PATH))["bullet"]["child"])["spawnBullets"]["items"]
    original = items()
    first, second = [item["itemId"] for item in original]
    assert first != second
    apply(service, content, stack, "array_move", objectPath=["bullet"], field="spawnBullets", itemId=first, beforeItemId=None)
    assert [item["itemId"] for item in items()] == [second, first]
    apply(service, content, stack, "set_field", objectPath=["bullet", "spawnBullets", {"itemId": first}], field="damage", value=8)
    assert [item["damage"] for item in content.data["bullet"]["spawnBullets"]] == [1, 8]
    apply(service, content, stack, "array_remove", objectPath=["bullet"], field="spawnBullets", itemId=first)
    with pytest.raises(ValueError):
        apply(service, content, stack, "set_field", objectPath=["bullet", "spawnBullets", {"itemId": first}], field="damage", value=4)
    stack.undo()
    assert [item["itemId"] for item in items()] == [second, first]
    stack.undo()
    stack.undo()
    assert [item["itemId"] for item in items()] == [first, second]
    assert content.data["bullet"]["spawnBullets"] == [{"type": "BasicBulletType", "damage": 1}] * 2


def test_scalar_array_value_edit_insert_and_move_noop():
    service, content, stack = setup({"bullet": {"type": "LaserBulletType", "colors": ["ff000080", "00ff00"]}})
    def array():
        return fields(fields(service.plan(content, PATH))["bullet"]["child"])["colors"]
    initial = array()
    first = initial["items"][0]["itemId"]
    assert initial["items"][0]["field"]["control"] == "color"
    apply(service, content, stack, "set_field", objectPath=["bullet", "colors", {"itemId": first}], field="value", value="#123456")
    assert content.data["bullet"]["colors"][0] == "12345680"
    count_before = len(content.data["bullet"]["colors"])
    apply(service, content, stack, "array_insert", objectPath=["bullet"], field="colors", beforeItemId=first)
    assert len(content.data["bullet"]["colors"]) == count_before + 1
    inserted = array()["items"][0]["itemId"]
    assert inserted != first
    assert apply(service, content, stack, "array_move", objectPath=["bullet"], field="colors", itemId=inserted, beforeItemId=first) is None
    stack.undo()
    assert [item["itemId"] for item in array()["items"]] == [item["itemId"] for item in initial["items"]]
    stack.undo()
    assert content.data["bullet"]["colors"] == ["ff000080", "00ff00"]


def test_special_ability_weapon_and_object_map_routes_remain_readonly():
    service, content, stack = setup({"type": "tank", "abilities": [], "weapons": []}, "units")
    plan = service.plan(content, PATH)
    for name in ("abilities", "weapons"):
        assert fields(plan)[name]["readOnly"] is True
        with pytest.raises(ValueError):
            apply(service, content, stack, "array_insert", field=name)
    block_service, block, block_stack = setup({"type": "ItemTurret", "ammoTypes": {}}, "blocks")
    assert fields(block_service.plan(block, PATH))["ammoTypes"]["readOnly"] is True
    with pytest.raises(ValueError):
        apply(block_service, block, block_stack, "create_object", field="ammoTypes")


def test_nested_form_memory_is_isolated_and_snapshot_restore_recovers_identities():
    service, content, stack = setup({"bullet": {"type": "BasicBulletType", "spawnBullets": [
        {"type": "BasicBulletType", "splashDamage": 3}, {"type": "BasicBulletType", "splashDamage": 5}]}})
    def items():
        return fields(fields(service.plan(content, PATH))["bullet"]["child"])["spawnBullets"]["items"]
    first, second = [item["itemId"] for item in items()]
    before_state = service.snapshot(PATH)
    before_data = deepcopy(content.data)
    address = ["bullet", "spawnBullets", {"itemId": first}]
    apply(service, content, stack, "delete_group", objectPath=address, group="splash")
    assert "splashDamage" not in content.data["bullet"]["spawnBullets"][0]
    assert content.data["bullet"]["spawnBullets"][1]["splashDamage"] == 5
    apply(service, content, stack, "add_group", objectPath=address, group="splash")
    assert content.data["bullet"]["spawnBullets"][0]["splashDamage"] == 3
    stack.undo()
    stack.undo()
    assert service.snapshot(PATH) == before_state and content.data == before_data
    service.restore(PATH, before_state)
    assert [item["itemId"] for item in items()] == [first, second]


@pytest.mark.parametrize("address", [["bullet.damage"], ["bullet", "0"], ["bullet", 0], ["bullet", {"index": 0}], "bullet", [None]])
def test_invalid_addresses_and_failed_commands_preserve_data_and_state(address):
    service, content, stack = setup({"bullet": {"type": "BasicBulletType", "damage": 2}})
    service.plan(content, PATH)
    before_data, before_state = deepcopy(content.data), service.snapshot(PATH)
    with pytest.raises(ValueError):
        apply(service, content, stack, "set_field", objectPath=address, field="damage", value=9)
    assert content.data == before_data and service.snapshot(PATH) == before_state
    assert not stack.can_undo


def test_array_item_identity_is_scoped_to_document_and_not_serialized():
    service, content, stack = setup({"bullet": {"type": "LaserBulletType", "colors": ["ff0000"]}})
    first = fields(fields(service.plan(content, PATH))["bullet"]["child"])["colors"]["items"][0]["itemId"]
    other = ContentData("other", "weapons", deepcopy(content.data))
    other_path = "content/weapons/other.json"
    service.plan(other, other_path)
    with pytest.raises(ValueError):
        service.command("set_field", other, other_path, {"objectPath": ["bullet", "colors", {"itemId": first}], "field": "value", "value": "00ff00"})
    assert content.data == {"bullet": {"type": "LaserBulletType", "colors": ["ff0000"]}}


def test_plan_budgets_limit_rendering_without_truncating_data():
    service, content, stack = setup({"bullet": {"type": "LaserBulletType", "colors": ["ff0000"] * 513}})
    before = deepcopy(content.data)
    colors = fields(fields(service.plan(content, PATH))["bullet"]["child"])["colors"]
    assert colors["readOnly"] and "上限" in colors["validationError"]
    with pytest.raises(ValueError):
        apply(service, content, stack, "array_remove", objectPath=["bullet"], field="colors", itemId="a" * 32)
    assert content.data == before


def test_invalid_object_shape_is_retained_and_never_replaced_implicitly():
    service, content, stack = setup({"bullet": "vanilla-bullet"})
    plan = service.plan(content, PATH)
    assert fields(plan)["bullet"]["readOnly"]
    with pytest.raises(ValueError):
        apply(service, content, stack, "create_object", field="bullet")
    assert content.data == {"bullet": "vanilla-bullet"}


def test_large_document_budget_and_unknown_family_refuse_mutation(monkeypatch):
    service, content, stack = setup({"bullet": {"type": "BasicBulletType", "damage": 3}, "custom": "x" * 100})
    monkeypatch.setattr(service, "MAX_DOCUMENT_BYTES", 30)
    plan = service.plan(content, PATH)
    assert not plan["groups"] and "上限" in plan["notice"]
    with pytest.raises(ValueError):
        apply(service, content, stack, "set_field", objectPath=["bullet"], field="damage", value=10)
    other_service, wrong, other_stack = setup({"type": "Wall", "health": 10})
    assert other_service.plan(wrong, PATH)["knownType"] is False
    with pytest.raises(ValueError):
        apply(other_service, wrong, other_stack, "set_field", field="health", value=99)


def test_deleted_container_releases_descendant_item_ids_and_undo_restores_them():
    service, content, stack = setup({"bullet": {"type": "BasicBulletType", "spawnBullets": [
        {"type": "LaserBulletType", "colors": ["ff0000"]}]}})
    plan = service.plan(content, PATH)
    array = fields(fields(plan)["bullet"]["child"])["spawnBullets"]
    item_id = array["items"][0]["itemId"]
    before = service.snapshot(PATH)
    assert len(before.item_ids) == 2
    apply(service, content, stack, "array_remove", objectPath=["bullet"], field="spawnBullets", itemId=item_id)
    assert len(service.snapshot(PATH).item_ids) == 1
    stack.undo()
    assert service.snapshot(PATH) == before


def test_real_save_reopen_excludes_session_ids_and_keeps_nested_values(tmp_path):
    from app.core.project import Project
    project = Project.create(tmp_path / "project", "test", "测试")
    project.contents.save("gun", {"bullet": {"type": "LaserBulletType", "colors": ["ff0000"]}}, "weapons")
    content = project.contents.get_by_path("weapons/gun.json")
    metadata = Metadata("metadata")
    service = NestedFormService(metadata, FormService(metadata))
    stack = CommandStack()
    scalar = fields(fields(service.plan(content, PATH))["bullet"]["child"])["colors"]["items"][0]["field"]
    assert scalar["label"] == "值"
    first = fields(fields(service.plan(content, PATH))["bullet"]["child"])["colors"]["items"][0]["itemId"]
    apply(service, content, stack, "set_field", objectPath=["bullet", "colors", {"itemId": first}], field="value", text="123456")
    project.contents.save("gun", content.data, "weapons")
    reopened = Project.open(project.root).contents.get_by_path("weapons/gun.json")
    assert reopened.data == {"bullet": {"type": "LaserBulletType", "colors": ["123456"]}}
    fresh = NestedFormService(metadata, FormService(metadata))
    fresh_id = fields(fields(fresh.plan(reopened, PATH))["bullet"]["child"])["colors"]["items"][0]["itemId"]
    assert fresh_id != first
    with pytest.raises(ValueError):
        fresh.command("set_field", reopened, PATH, {"objectPath": ["bullet", "colors", {"itemId": first}], "field": "value", "text": "ffffff"})


def test_boolean_array_and_invalid_item_shapes_preserve_neighbors():
    service, content, stack = setup({"type": "Wall", "itemFilter": [True, False, True]}, "blocks")
    plan = service.plan(content, PATH)
    item = fields(plan)["itemFilter"]["items"][1]
    apply(service, content, stack, "set_field", objectPath=["itemFilter", {"itemId": item["itemId"]}], field="value", value=True)
    assert content.data["itemFilter"] == [True, True, True]
    with pytest.raises(ValueError):
        apply(service, content, stack, "set_field", objectPath=["itemFilter", {"itemId": item["itemId"]}], field="value", value=1)
    stack.undo()
    assert content.data["itemFilter"] == [True, False, True]
    bad_service, bad, bad_stack = setup({"bullet": {"spawnBullets": ["bad", {"damage": 5}]}})
    items = fields(fields(bad_service.plan(bad, PATH))["bullet"]["child"])["spawnBullets"]["items"]
    assert "notice" in items[0]
    with pytest.raises(ValueError):
        apply(bad_service, bad, bad_stack, "set_field", objectPath=["bullet", "spawnBullets", {"itemId": items[0]["itemId"]}], field="damage", value=9)
    assert bad.data["bullet"]["spawnBullets"] == ["bad", {"damage": 5}]


def test_unknown_field_and_type_paths_cannot_bypass_metadata():
    service, content, stack = setup({"bullet": {"type": "BasicBulletType", "damage": 2, "unknown": {"damage": 3}}})
    for payload in ({"objectPath": ["bullet", "unknown"], "field": "damage", "value": 6},
                    {"objectPath": ["bullet"], "field": "type", "text": "Wall"},
                    {"objectPath": ["bullet"], "field": "damage.x", "value": 4}):
        with pytest.raises(ValueError):
            apply(service, content, stack, "set_field", **payload)
    with pytest.raises(ValueError):
        apply(service, content, stack, "set_type", objectPath=["bullet"], type="Weapon")
    assert not stack.can_undo and content.data["bullet"]["damage"] == 2


def test_edit_exceeding_document_budget_is_rejected_before_commit(monkeypatch):
    service, content, stack = setup({"type": "tank", "description": "旧说明"}, "units")
    monkeypatch.setattr(service, "MAX_DOCUMENT_BYTES", 200)
    before = deepcopy(content.data)
    with pytest.raises(ValueError, match="上限"):
        apply(service, content, stack, "set_field", field="description", text="x" * 300)
    assert content.data == before and not stack.can_undo
