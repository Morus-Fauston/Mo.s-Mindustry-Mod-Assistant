"""Research and planet collections share the real nested snapshot history."""

from copy import deepcopy

import pytest

from app.core.commands import CommandStack
from app.core.content_store import ContentData
from app.core.metadata import Metadata
from app.desktop.forms import FormService
from app.desktop.nested_forms import NestedFormService


PATH = "content/blocks/test-wall.json"


def setup(data):
    from app.desktop.research_fields import ResearchFieldsService

    nested = NestedFormService(Metadata("metadata"), FormService(Metadata("metadata")))
    return ResearchFieldsService(nested), nested, ContentData("test-wall", "blocks", data), CommandStack()


def fields(plan):
    return {field["name"]: field for group in plan["groups"] for field in group["fields"]}


def apply(service, content, stack, action, **payload):
    command = service.command(action, content, PATH, payload)
    if command is not None:
        stack.execute(command)
    return command


def test_legacy_research_string_projects_without_writing_and_edit_undo_restores_string():
    service, nested, content, stack = setup({"type": "Wall", "research": "copper-wall", "custom": 3})
    plan = fields(service.plan(content, PATH))["research"]
    assert plan["control"] == "research"
    assert next(field for field in plan["fields"] if field["name"] == "parent")["displayValue"] == "copper-wall"
    assert content.data["research"] == "copper-wall" and not stack.can_undo
    assert apply(service, content, stack, "research_set", objectPath=["research"], field="parent", value="copper-wall") is None
    apply(service, content, stack, "research_set", objectPath=["research"], field="parent", value="dagger")
    assert content.data == {"type": "Wall", "research": {"parent": "dagger"}, "custom": 3}
    stack.undo()
    assert content.data["research"] == "copper-wall"


def test_research_lists_use_stable_item_ids_and_explicit_target_type_reset():
    initial = {"type": "Wall", "research": {"parent": "copper-wall", "future": {"keep": True}}}
    service, nested, content, stack = setup(deepcopy(initial))
    apply(service, content, stack, "research_add", field="research", collection="requirements")
    apply(service, content, stack, "research_add", field="research", collection="requirements")
    def research():
        return fields(service.plan(content, PATH))["research"]
    first, second = [row["itemId"] for row in research()["requirements"]["rows"]]
    address = ["research", "requirements", {"itemId": first}]
    apply(service, content, stack, "research_set", objectPath=address, field="amount", text="999999")
    apply(service, content, stack, "research_move", field="research", collection="requirements", itemId=first, beforeItemId=None)
    assert [row["itemId"] for row in research()["requirements"]["rows"]] == [second, first]
    assert content.data["research"]["requirements"][1] == {"item": "copper", "amount": 999999}
    apply(service, content, stack, "research_add", field="research", collection="objectives")
    objective = research()["objectives"]["rows"][0]
    apply(service, content, stack, "research_objective_type", field="research", itemId=objective["itemId"], type="OnPlanet")
    assert content.data["research"]["objectives"] == [{"type": "OnPlanet"}]
    apply(service, content, stack, "research_set", objectPath=objective["objectPath"], field="planet", value="serpulo")
    assert content.data["research"]["objectives"] == [{"type": "OnPlanet", "planet": "serpulo"}]
    apply(service, content, stack, "research_remove", field="research", collection="objectives", itemId=objective["itemId"])
    assert "objectives" not in content.data["research"]
    for _ in range(8):
        stack.undo()
    assert content.data == initial


def test_planets_preserve_unknowns_read_only_then_explicit_set_deduplicates_and_undo_restores():
    initial = {"type": "Wall", "shownPlanets": ["missing-planet", "serpulo", "serpulo"]}
    service, nested, content, stack = setup(deepcopy(initial))
    planets = fields(service.plan(content, PATH))["shownPlanets"]
    ids = [row["itemId"] for row in planets["rows"]]
    assert content.data == initial and not stack.can_undo
    current = service.reference_candidates(content, PATH, {"objectPath": planets["rows"][0]["objectPath"], "field": "planet"})
    assert current["current"] == {"value": "missing-planet", "label": "missing-planet", "known": False}
    apply(service, content, stack, "planet_set", field="shownPlanets", itemId=ids[0], value="erekir")
    assert content.data["shownPlanets"] == ["erekir", "serpulo"]
    assert [row["itemId"] for row in fields(service.plan(content, PATH))["shownPlanets"]["rows"]] == ids[:2]
    stack.undo()
    assert content.data == initial
    assert [row["itemId"] for row in fields(service.plan(content, PATH))["shownPlanets"]["rows"]] == ids


def test_planet_add_remove_last_deletes_field_with_one_command_each():
    service, nested, content, stack = setup({"type": "Wall", "shownPlanets": []})
    apply(service, content, stack, "planet_add", field="shownPlanets", value="serpulo")
    assert content.data["shownPlanets"] == ["serpulo"]
    assert apply(service, content, stack, "planet_add", field="shownPlanets", value="serpulo") is None
    row = fields(service.plan(content, PATH))["shownPlanets"]["rows"][0]
    apply(service, content, stack, "planet_remove", field="shownPlanets", itemId=row["itemId"])
    assert "shownPlanets" not in content.data
    stack.undo()
    assert content.data["shownPlanets"] == ["serpulo"]
    stack.undo()
    assert content.data["shownPlanets"] == []


def test_seven_fields_keep_unknown_data_and_low_frequency_clear_semantics():
    initial = {"type": "Wall", "research": {"parent": "copper-wall", "future": {"keep": True}}}
    service, nested, content, stack = setup(deepcopy(initial))
    for field, value in (("planet", "serpulo"), ("root", True), ("name", "  研究根  "), ("requiresUnlock", True)):
        apply(service, content, stack, "research_set", objectPath=["research"], field=field, value=value)
    assert content.data["research"] == {**initial["research"], "planet": "serpulo", "root": True, "name": "研究根", "requiresUnlock": True}
    for field, value in (("parent", ""), ("planet", None), ("root", False), ("name", "  "), ("requiresUnlock", False)):
        apply(service, content, stack, "research_set", objectPath=["research"], field=field, value=value)
    assert content.data["research"] == {"future": {"keep": True}}
    for _ in range(9):
        stack.undo()
    assert content.data == initial


@pytest.mark.parametrize("kind,target,category,value", [
    ("Research", "content", "Blocks", "copper-wall"), ("Produce", "content", "Items", "copper"),
    ("SectorComplete", "preset", "SectorPresets", "groundZero"),
    ("OnSector", "preset", "SectorPresets", "groundZero"), ("OnPlanet", "planet", "Planets", "serpulo"),
])
def test_objective_candidate_categories_and_actual_target_writes(kind, target, category, value):
    service, nested, content, stack = setup({"type": "Wall", "research": {"objectives": [{"type": kind}]}})
    row = fields(service.plan(content, PATH))["research"]["objectives"]["rows"][0]
    result = service.reference_candidates(content, PATH, {"objectPath": row["objectPath"], "field": target})
    assert not any(candidate["category"] == "Weapons" for candidate in result["candidates"])
    assert any(candidate["category"] == category and candidate["value"] == value for candidate in result["candidates"])
    apply(service, content, stack, "research_set", objectPath=row["objectPath"], field=target, value=value)
    assert content.data["research"]["objectives"] == [{"type": kind, target: value}]
    with pytest.raises(ValueError):
        apply(service, content, stack, "research_set", objectPath=row["objectPath"], field=target, value="not-in-this-category")
    if kind in ("SectorComplete", "OnSector", "OnPlanet"):
        with pytest.raises(ValueError):
            apply(service, content, stack, "research_set", objectPath=row["objectPath"], field=target, value="copper")


@pytest.mark.parametrize("payload", [{"text": ""}, {"text": "1e999"}, {"text": "999999.00000000000001"},
    {"text": "1.00000000000000001"}, {"text": "NaN"}, {"value": True}, {"value": None},
    {"value": 0}, {"value": -1}, {"value": 1.5}, {"value": 1000000}])
def test_invalid_requirement_numbers_preserve_real_data_and_history(payload):
    service, nested, content, stack = setup({"type": "Wall", "research": {"requirements": [{"item": "copper", "amount": 1}]}})
    row = fields(service.plan(content, PATH))["research"]["requirements"]["rows"][0]
    before, state = deepcopy(content.data), nested.snapshot(PATH)
    with pytest.raises(ValueError):
        apply(service, content, stack, "research_set", objectPath=row["objectPath"], field="amount", **payload)
    assert content.data == before and nested.snapshot(PATH) == state and not stack.can_undo


@pytest.mark.parametrize("objective", [{"content": "copper-wall", "future": 3},
                                      {"type": "Unknown", "planet": "serpulo", "future": 3}])
def test_unknown_objective_types_are_retained_and_explicit_switch_clears_only_target_keys(objective):
    service, nested, content, stack = setup({"type": "Wall", "research": {"objectives": [deepcopy(objective)]}})
    row = fields(service.plan(content, PATH))["research"]["objectives"]["rows"][0]
    assert row["notice"] and not row["fields"]
    assert content.data["research"]["objectives"] == [objective]
    apply(service, content, stack, "research_objective_type", field="research", itemId=row["itemId"], type="Produce")
    assert content.data["research"]["objectives"] == [{"type": "Produce", "future": 3}]
    stack.undo()
    assert content.data["research"]["objectives"] == [objective]


@pytest.mark.parametrize("field,value", [("research", 42), ("research", []), ("shownPlanets", "serpulo"),
                                         ("shownPlanets", ["serpulo", 3])])
def test_invalid_top_level_shapes_are_readonly_and_untouched(field, value):
    initial = {"type": "Wall", field: value}
    service, nested, content, stack = setup(deepcopy(initial))
    descriptor = fields(service.plan(content, PATH))[field]
    assert descriptor["readOnly"] and descriptor["validationError"]
    with pytest.raises(ValueError):
        if field == "research":
            apply(service, content, stack, "research_set", objectPath=[field], field="parent", value="dagger")
        else:
            apply(service, content, stack, "planet_add", field=field, value="serpulo")
    assert content.data == initial and not stack.can_undo


def test_unsupported_list_shapes_and_entries_survive_other_field_edits():
    initial = {"type": "Wall", "research": {"requirements": "copper/2", "objectives": ["copper-wall", 9]}}
    service, nested, content, stack = setup(deepcopy(initial))
    plan = fields(service.plan(content, PATH))["research"]
    assert plan["requirements"]["readOnly"] and all(row["notice"] for row in plan["objectives"]["rows"])
    apply(service, content, stack, "research_set", objectPath=["research"], field="parent", value="dagger")
    assert content.data["research"] == {**initial["research"], "parent": "dagger"}
    with pytest.raises(ValueError):
        apply(service, content, stack, "research_add", field="research", collection="requirements")
    apply(service, content, stack, "research_remove", field="research", collection="objectives", itemId=plan["objectives"]["rows"][0]["itemId"])
    assert content.data["research"]["objectives"] == [9]


def test_deleted_objective_address_cannot_edit_another_item():
    service, nested, content, stack = setup({"type": "Wall", "research": {"objectives": [{"type": "Research", "content": "copper-wall"}]}})
    row = fields(service.plan(content, PATH))["research"]["objectives"]["rows"][0]
    apply(service, content, stack, "research_remove", field="research", collection="objectives", itemId=row["itemId"])
    apply(service, content, stack, "research_add", field="research", collection="objectives")
    with pytest.raises(ValueError):
        apply(service, content, stack, "research_set", objectPath=row["objectPath"], field="content", value="dagger")
    stack.undo()
    stack.undo()
    assert fields(service.plan(content, PATH))["research"]["objectives"]["rows"][0]["itemId"] == row["itemId"]


def test_planet_set_requires_explicit_value_and_rejects_other_content_categories():
    service, nested, content, stack = setup({"type": "Wall", "shownPlanets": ["serpulo"]})
    row = fields(service.plan(content, PATH))["shownPlanets"]["rows"][0]
    for extra in ({}, {"value": "copper"}, {"value": ""}, {"value": None}):
        with pytest.raises(ValueError):
            apply(service, content, stack, "planet_set", field="shownPlanets", itemId=row["itemId"], **extra)
    assert content.data["shownPlanets"] == ["serpulo"] and not stack.can_undo


def test_empty_planet_set_exposes_read_only_add_candidates_without_creating_rows():
    service, nested, content, stack = setup({"type": "Wall", "shownPlanets": []})
    descriptor = fields(service.plan(content, PATH))["shownPlanets"]
    assert descriptor["addField"]["name"] == "planet"
    before = deepcopy(content.data)
    candidates = service.reference_candidates(content, PATH, {"objectPath": ["shownPlanets"], "field": "planet", "query": "serpulo"})
    assert any(row["value"] == "serpulo" and row["category"] == "Planets" for row in candidates["candidates"])
    assert candidates["current"]["value"] is None
    assert content.data == before and not stack.can_undo
    apply(service, content, stack, "planet_add", field="shownPlanets", value="serpulo")
    apply(service, content, stack, "planet_add", field="shownPlanets", value="erekir")
    assert content.data["shownPlanets"] == ["serpulo", "erekir"]


@pytest.mark.parametrize("limit,value", [("MAX_DEPTH", 2), ("MAX_NODES", 1), ("MAX_ARRAY_ITEMS", 0), ("MAX_DOCUMENT_BYTES", 10)])
def test_display_budgets_prevent_unaddressable_mutation_without_data_loss(limit, value):
    initial = {"type": "Wall", "research": {"requirements": [{"item": "copper", "amount": 1}]}}
    service, nested, content, stack = setup(deepcopy(initial))
    setattr(nested, limit, value)
    service.plan(content, PATH)
    state = nested.snapshot(PATH)
    with pytest.raises(ValueError):
        apply(service, content, stack, "research_add", field="research", collection="requirements")
    assert content.data == initial and nested.snapshot(PATH) == state and not stack.can_undo


def test_research_extension_preserves_resource_extension_ids_and_shared_history():
    from app.desktop.resource_fields import ResourceFieldsService

    service, nested, content, stack = setup({"type": "Wall", "requirements": [{"item": "copper", "amount": 2}], "research": "copper-wall"})
    resources = ResourceFieldsService(nested)
    row = fields(nested.plan(content, PATH))["requirements"]["rows"][0]
    apply(service, content, stack, "research_add", field="research", collection="objectives")
    assert fields(nested.plan(content, PATH))["requirements"]["rows"][0]["itemId"] == row["itemId"]
    command = resources.command("resource_set", content, PATH, {"objectPath": row["objectPath"], "field": "amount", "text": "3"})
    stack.execute(command)
    objective = fields(nested.plan(content, PATH))["research"]["objectives"]["rows"][0]
    stack.undo()
    assert fields(nested.plan(content, PATH))["research"]["objectives"]["rows"][0]["itemId"] == objective["itemId"]
    stack.undo()
    assert content.data["research"] == "copper-wall" and content.data["requirements"][0]["amount"] == 2
