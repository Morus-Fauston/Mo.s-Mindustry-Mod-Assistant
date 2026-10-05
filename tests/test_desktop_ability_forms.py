"""Ability arrays use the current nested form session and command history."""

from copy import deepcopy

import pytest

from app.core.commands import CommandStack
from app.core.content_store import ContentData
from app.core.metadata import Metadata
from app.desktop.forms import FormService
from app.desktop.nested_forms import NestedFormService


PATH = "content/units/test-unit.json"


def setup(data):
    from app.desktop.ability_forms import AbilityFormsService

    metadata = Metadata("metadata")
    nested = NestedFormService(metadata, FormService(metadata))
    AbilityFormsService(nested)
    return nested, ContentData("test-unit", "units", data), CommandStack()


def fields(plan):
    return {field["name"]: field for group in plan["groups"] for field in group["fields"]}


def apply(nested, content, stack, action, **payload):
    command = nested.command(action, content, PATH, payload)
    if command is not None:
        stack.execute(command)
    return command


def test_new_ability_defaults_are_detached_and_only_supported_types_are_created():
    from app.core.ability_types import create_ability

    expected = {"type": "ShieldRegenFieldAbility", "amount": 1.0,
                "max": 100.0, "reload": 100.0, "range": 60.0}
    created = create_ability("ShieldRegenFieldAbility")
    assert created == expected
    created["max"] = 999
    assert create_ability("ShieldRegenFieldAbility") == expected
    assert create_ability("UnitSpawnAbility") == {"type": "UnitSpawnAbility"}
    with pytest.raises(ValueError):
        create_ability("UnknownAbility")


def test_missing_ability_array_is_view_only_and_explicit_additions_undo_to_missing_key():
    nested, content, stack = setup({"type": "flying", "health": 100, "custom": 9})
    before = deepcopy(content.data)
    assert "abilities" not in fields(nested.plan(content, PATH))
    assert content.data == before and not stack.can_undo
    apply(nested, content, stack, "add_group", group="abilities")
    ability = fields(nested.plan(content, PATH))["abilities"]
    assert ability["control"] == "array" and ability["items"] == []
    assert content.data == {**before, "abilities": []}
    apply(nested, content, stack, "array_insert", field="abilities")
    assert content.data["abilities"] == [{"type": "ShieldRegenFieldAbility", "amount": 1.0,
                                         "max": 100.0, "reload": 100.0, "range": 60.0}]
    item = fields(nested.plan(content, PATH))["abilities"]["items"][0]
    assert item["form"]["knownType"] is True
    assert len(item["form"]["typeSelector"]["choices"]) == 15
    stack.undo()
    assert content.data == {**before, "abilities": []}
    stack.redo()
    assert fields(nested.plan(content, PATH))["abilities"]["items"][0]["itemId"] == item["itemId"]
    stack.undo()
    stack.undo()
    assert content.data == before


def test_duplicate_abilities_keep_identity_through_move_edit_delete_and_full_undo_redo():
    nested, content, stack = setup({"type": "flying", "abilities": [
        {"type": "RegenAbility", "amount": 1, "custom": "first"},
        {"type": "RegenAbility", "amount": 1, "custom": "second"},
        {"type": "ForceFieldAbility", "radius": 60}], "unrelated": {"keep": True}})
    before = deepcopy(content.data)

    def items():
        return fields(nested.plan(content, PATH))["abilities"]["items"]

    original = [item["itemId"] for item in items()]
    first, second, third = original
    address = ["abilities", {"itemId": first}]
    apply(nested, content, stack, "array_move", field="abilities", itemId=first, beforeItemId=None)
    assert [item["itemId"] for item in items()] == [second, third, first]
    apply(nested, content, stack, "set_field", objectPath=address, field="amount", text="2.5")
    assert content.data["abilities"][2]["amount"] == 2.5
    apply(nested, content, stack, "set_type", objectPath=address, type="ShieldRegenFieldAbility")
    assert content.data["abilities"][2] == {"type": "ShieldRegenFieldAbility", "amount": 2.5, "custom": "first"}
    apply(nested, content, stack, "array_remove", field="abilities", itemId=first)
    with pytest.raises(ValueError):
        apply(nested, content, stack, "set_field", objectPath=address, field="amount", value=7)
    final = deepcopy(content.data)
    for _ in range(4):
        stack.undo()
    assert content.data == before
    assert [item["itemId"] for item in items()] == original
    for _ in range(4):
        stack.redo()
    assert content.data == final and content.data["unrelated"] == {"keep": True}


@pytest.mark.parametrize("ability", [{"amount": 1, "extra": 3}, {"type": "UnknownAbility", "extra": 3},
                                      {"type": "Ability", "extra": 3}, {"type": None, "extra": 3}])
def test_unknown_and_missing_ability_types_are_preserved_until_explicit_selection(ability):
    nested, content, stack = setup({"type": "flying", "abilities": [deepcopy(ability)]})
    item = fields(nested.plan(content, PATH))["abilities"]["items"][0]
    address = item["form"]["objectPath"]
    assert not item["form"]["knownType"]
    assert content.data["abilities"] == [ability]
    with pytest.raises(ValueError):
        apply(nested, content, stack, "set_field", objectPath=address, field="extra", value=6)
    apply(nested, content, stack, "set_type", objectPath=address, type="RegenAbility")
    assert content.data["abilities"][0] == {**ability, "type": "RegenAbility"}
    stack.undo()
    assert content.data["abilities"] == [ability]


@pytest.mark.parametrize("kind,field,source,value", [
    ("UnitSpawnAbility", "unit", "UnitTypes", "dagger"),
    ("SpawnDeathAbility", "unit", "UnitTypes", "dagger"),
    ("StatusFieldAbility", "effect", "StatusEffects", "burning"),
    ("LiquidRegenAbility", "liquid", "Liquids", "water"),
])
def test_ability_references_use_shared_candidates_without_mutating_metadata(kind, field, source, value):
    nested, content, stack = setup({"type": "flying", "abilities": [{"type": kind, field: value}]})
    original_metadata = deepcopy(nested.metadata.get_class(kind))
    item = fields(nested.plan(content, PATH))["abilities"]["items"][0]
    descriptor = fields(item["form"])[field]
    assert descriptor["control"] == "reference" and descriptor["refSource"] == source
    address = item["form"]["objectPath"]
    result = nested.reference_candidates(content, PATH, {"objectPath": address, "field": field, "query": value})
    assert any(candidate["value"] == value for candidate in result["candidates"])
    with pytest.raises(ValueError):
        apply(nested, content, stack, "set_field", objectPath=address, field=field, value="not-a-known-content")
    assert nested.metadata.get_class(kind) == original_metadata
    assert content.data["abilities"] == [{"type": kind, field: value}]


@pytest.mark.parametrize("kind", [
    "ShieldRegenFieldAbility", "RegenAbility", "MoveLightningAbility", "StatusFieldAbility",
    "ForceFieldAbility", "EnergyFieldAbility", "RepairFieldAbility", "ArmorPlateAbility",
    "MoveEffectAbility", "SpawnDeathAbility", "LiquidExplodeAbility", "LiquidRegenAbility",
    "SuppressionFieldAbility", "UnitSpawnAbility", "ShieldArcAbility",
])
def test_each_legacy_ability_can_be_inserted_as_a_known_configured_form(kind):
    nested, content, stack = setup({"type": "flying", "abilities": []})
    apply(nested, content, stack, "array_insert", field="abilities", type=kind)
    assert content.data["abilities"][0]["type"] == kind
    child = fields(nested.plan(content, PATH))["abilities"]["items"][0]["form"]
    assert child["knownType"] and child["groups"]
    assert all(choice["label"] != choice["value"] for choice in child["typeSelector"]["choices"])
    stack.undo()
    assert content.data == {"type": "flying", "abilities": []}


@pytest.mark.parametrize("kind", [None, "UnknownAbility", "Weapon", "../Ability", [], {}])
def test_invalid_insert_type_preserves_data_state_and_history(kind):
    nested, content, stack = setup({"type": "flying", "abilities": []})
    nested.plan(content, PATH)
    before, state = deepcopy(content.data), nested.snapshot(PATH)
    with pytest.raises(ValueError):
        apply(nested, content, stack, "array_insert", field="abilities", type=kind)
    assert content.data == before and nested.snapshot(PATH) == state and not stack.can_undo


@pytest.mark.parametrize("abilities", ["not-array", {"type": "RegenAbility"},
                                        [{"type": "RegenAbility"}] * 513])
def test_invalid_or_oversized_arrays_remain_untouched_and_not_editable(abilities):
    nested, content, stack = setup({"type": "flying", "abilities": abilities})
    before = deepcopy(content.data)
    descriptor = fields(nested.plan(content, PATH))["abilities"]
    assert descriptor["readOnly"] and descriptor["validationError"]
    with pytest.raises(ValueError):
        apply(nested, content, stack, "array_insert", field="abilities")
    assert content.data == before and not stack.can_undo


def test_unregistered_weapons_remain_readonly_and_malformed_ability_items_can_be_removed():
    nested, content, stack = setup({"type": "flying", "abilities": [3, {"type": "RegenAbility"}], "weapons": []})
    plan = fields(nested.plan(content, PATH))
    assert plan["weapons"]["readOnly"]
    assert "notice" in plan["abilities"]["items"][0]
    malformed_id = plan["abilities"]["items"][0]["itemId"]
    apply(nested, content, stack, "array_remove", field="abilities", itemId=malformed_id)
    assert content.data["abilities"] == [{"type": "RegenAbility"}]
    stack.undo()
    assert content.data["abilities"][0] == 3
