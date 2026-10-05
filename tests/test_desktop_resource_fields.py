"""Legacy resource representations through the shared nested command seam."""

from copy import deepcopy
import pytest

from app.core.commands import CommandStack
from app.core.content_store import ContentData
from app.core.metadata import Metadata
from app.desktop.forms import FormService
from app.desktop.nested_forms import NestedFormService
from app.desktop.resource_fields import ResourceFieldsService


PATH = "content/blocks/crafter.json"


def setup(data):
    metadata = Metadata("metadata")
    nested = NestedFormService(metadata, FormService(metadata))
    return ResourceFieldsService(nested), nested, ContentData("crafter", "blocks", data), CommandStack()


def fields(plan):
    return {field["name"]: field for group in plan["groups"] for field in group["fields"]}


def apply(service, content, stack, action, **payload):
    command = service.command(action, content, PATH, payload)
    if command is not None:
        stack.execute(command)
    return command


def test_resource_rows_read_without_materializing_and_update_one_shared_history():
    service, nested, content, stack = setup({"type": "GenericCrafter", "requirements": [{"item": "copper", "amount": 2, "custom": True}]})
    before = deepcopy(content.data)
    plan = service.plan(content, PATH)
    resource = fields(plan)["requirements"]
    assert resource["control"] == "resource_list"
    row = resource["rows"][0]
    assert row["objectPath"] == ["requirements", {"itemId": row["itemId"]}]
    assert {f["name"] for f in row["fields"]} == {"item", "amount"}
    assert content.data == before and not stack.can_undo
    apply(service, content, stack, "resource_set", objectPath=row["objectPath"], field="amount", text="8")
    assert content.data["requirements"] == [{"item": "copper", "amount": 8, "custom": True}]
    stack.undo()
    assert content.data == before
    stack.redo()
    assert content.data["requirements"][0]["amount"] == 8


def test_resource_list_empty_insert_remove_move_and_generic_edit_preserve_ids():
    service, nested, content, stack = setup({"type": "GenericCrafter", "health": 100, "requirements": []})
    apply(service, content, stack, "resource_add", field="requirements")
    assert content.data["requirements"] == [{"item": "", "amount": 1}]
    first = fields(service.plan(content, PATH))["requirements"]["rows"][0]["itemId"]
    apply(service, content, stack, "resource_add", field="requirements")
    rows = fields(service.plan(content, PATH))["requirements"]["rows"]
    second = rows[1]["itemId"]
    apply(service, content, stack, "resource_move", field="requirements", itemId=first, beforeItemId=None)
    assert [row["itemId"] for row in fields(service.plan(content, PATH))["requirements"]["rows"]] == [second, first]
    generic = nested.command("set_field", content, PATH, {"field": "health", "value": 150})
    stack.execute(generic)
    assert [row["itemId"] for row in fields(service.plan(content, PATH))["requirements"]["rows"]] == [second, first]
    apply(service, content, stack, "resource_remove", field="requirements", itemId=first)
    with pytest.raises(ValueError):
        apply(service, content, stack, "resource_set", objectPath=["requirements", {"itemId": first}], field="amount", value=2)
    stack.undo()
    assert [row["itemId"] for row in fields(service.plan(content, PATH))["requirements"]["rows"]] == [second, first]


def test_slot_clear_is_null_not_zero_or_delete_and_restore_keeps_unknown_keys():
    service, nested, content, stack = setup({"type": "GenericCrafter", "outputItem": {"item": "copper", "amount": 2, "custom": 3}})
    original = deepcopy(content.data)
    apply(service, content, stack, "resource_set", objectPath=["outputItem"], field="item", value="")
    assert content.data["outputItem"] is None
    stack.undo()
    assert content.data == original
    apply(service, content, stack, "resource_set", objectPath=["outputItem"], field="item", value="lead")
    assert content.data["outputItem"] == {"item": "lead", "amount": 2, "custom": 3}
    with pytest.raises(ValueError):
        apply(service, content, stack, "resource_set", objectPath=["outputItem"], field="amount", value=0)


def test_empty_slot_rejects_quantity_without_materializing_and_can_select_liquid():
    service, nested, content, stack = setup({"type": "GenericCrafter", "outputLiquid": None})
    original = deepcopy(content.data)
    with pytest.raises(ValueError):
        apply(service, content, stack, "resource_set", objectPath=["outputLiquid"], field="amount", value=2)
    assert content.data == original and not stack.can_undo
    apply(service, content, stack, "resource_set", objectPath=["outputLiquid"], field="liquid", value="water")
    assert content.data["outputLiquid"] == {"liquid": "water", "amount": 1}
    stack.undo()
    assert content.data == original


def test_resource_list_depth_limit_does_not_offer_unaddressable_rows():
    service, nested, content, stack = setup({"type": "Wall", "requirements": [{"item": "copper", "amount": 1}]})
    nested.MAX_DEPTH = 1
    descriptor = fields(service.plan(content, PATH))["requirements"]
    assert descriptor["readOnly"] and descriptor["rows"] == []
    with pytest.raises(ValueError):
        apply(service, content, stack, "resource_add", field="requirements")
    assert content.data["requirements"] == [{"item": "copper", "amount": 1}]
    assert not stack.can_undo


def test_consumes_add_remove_booster_and_zero_power_are_single_commands():
    service, nested, content, stack = setup({"type": "GenericCrafter", "consumes": {"custom": {"keep": True}}})
    before = deepcopy(content.data)
    apply(service, content, stack, "consume_add", field="consumes", key="items")
    assert content.data["consumes"]["items"] == [{"item": "", "amount": 1}]
    stack.undo()
    assert content.data == before
    stack.redo()
    consumes = fields(service.plan(content, PATH))["consumes"]
    row = next(field for field in consumes["children"] if field["name"] == "items")["rows"][0]
    apply(service, content, stack, "resource_set", objectPath=row["objectPath"], field="booster", value=True)
    assert content.data["consumes"]["items"][0]["booster"] is True
    apply(service, content, stack, "consume_add", field="consumes", key="power")
    apply(service, content, stack, "resource_set", objectPath=["consumes"], field="power", text="0")
    assert content.data["consumes"]["power"] == 0
    apply(service, content, stack, "consume_remove", field="consumes", key="power")
    assert "power" not in content.data["consumes"]
    assert content.data["consumes"]["custom"] == {"keep": True}
    stack.undo()
    assert content.data["consumes"]["power"] == 0


@pytest.mark.parametrize("text", ["1e-999", "1.00000000000000001", "0.001", "0.0100000000000000000000000000001"])
def test_consumes_decimal_precision_checked_before_float_conversion(text):
    service, nested, content, stack = setup({"type": "GenericCrafter", "consumes": {"power": 2}})
    service.plan(content, PATH)
    before, memory = deepcopy(content.data), nested.snapshot(PATH)
    with pytest.raises(ValueError):
        apply(service, content, stack, "resource_set", objectPath=["consumes"], field="power", text=text)
    assert content.data == before and nested.snapshot(PATH) == memory and not stack.can_undo


def test_consumes_decimal_precision_allows_insignificant_trailing_zeroes():
    service, _, content, stack = setup({"type": "GenericCrafter", "consumes": {"power": 2}})
    apply(service, content, stack, "resource_set", objectPath=["consumes"], field="power", text="1.200000")
    assert content.data["consumes"]["power"] == 1.2


@pytest.mark.parametrize("payload", [{"value": 0}, {"value": -1}, {"value": 1.5}, {"value": True}, {"value": None}, {"value": 100000},
                                     {"text": ""}, {"text": "NaN"}, {"text": "1e999"}, {"text": "2.5"}])
def test_invalid_resource_amount_preserves_data_sidecar_and_history(payload):
    service, nested, content, stack = setup({"type": "Wall", "requirements": [{"item": "copper", "amount": 1}]})
    row = fields(service.plan(content, PATH))["requirements"]["rows"][0]
    original, state = deepcopy(content.data), nested.snapshot(PATH)
    with pytest.raises(ValueError):
        apply(service, content, stack, "resource_set", objectPath=row["objectPath"], field="amount", **payload)
    assert content.data == original and nested.snapshot(PATH) == state and not stack.can_undo


def test_reference_candidates_bilingual_categories_unknown_values_and_project_legacy_names(tmp_path):
    from app.core.project import Project
    from app.desktop.references import ReferenceService
    project = Project.create(tmp_path / "project", "custom", "测试")
    project.contents.save("local-item", {}, "items")
    project.contents.save("local-liquid", {}, "liquids")
    metadata = Metadata("metadata")
    nested = NestedFormService(metadata, FormService(metadata, ReferenceService(metadata, project)))
    service = ResourceFieldsService(nested)
    content = ContentData("crafter", "blocks", {"type": "GenericCrafter", "outputItem": {"item": "missing-item", "amount": 1}, "outputLiquid": {"liquid": "water", "amount": 1}})
    stack = CommandStack()
    current = service.reference_candidates(content, PATH, {"objectPath": ["outputItem"], "field": "item", "query": "铜"})
    assert any(row["value"] == "copper" for row in current["candidates"])
    assert current["current"]["value"] == "missing-item" and not current["current"]["known"]
    local = service.reference_candidates(content, PATH, {"objectPath": ["outputItem"], "field": "item", "query": "local"})
    assert local["candidates"] == [{"value": "local-item", "category": "Items", "label": "local-item", "isProject": True}]
    apply(service, content, stack, "resource_set", objectPath=["outputItem"], field="item", value="local-item")
    assert content.data["outputItem"]["item"] == "local-item"
    with pytest.raises(ValueError):
        apply(service, content, stack, "resource_set", objectPath=["outputLiquid"], field="liquid", value="local-item")
    assert content.data["outputLiquid"]["liquid"] == "water"


def test_mixed_consumption_roundtrip_and_invalid_formats_stay_unchanged(tmp_path):
    from app.core.project import Project
    project = Project.create(tmp_path / "project", "resources", "测试")
    original = {"type": "GenericCrafter", "outputItem": None, "requirements": [], "consumes": {
        "power": 0, "items": [], "liquid": {"liquid": "water", "amount": 1}, "heat": 2.5, "unknown": True}}
    service, nested, content, stack = setup(deepcopy(original))
    before = deepcopy(content.data)
    service.plan(content, PATH)
    assert content.data == before
    apply(service, content, stack, "resource_set", objectPath=["consumes"], field="heat", text="3.25")
    apply(service, content, stack, "consume_add", field="consumes", key="coolant")
    project.contents.save("crafter", content.data, "blocks")
    reopened = Project.open(project.root).contents.get_by_path("blocks/crafter.json")
    assert reopened.data == {**original, "consumes": {**original["consumes"], "heat": 3.25, "coolant": {"liquid": "", "amount": 1}}}
    stack.undo()
    stack.undo()
    assert content.data == original
    for field, value in (("requirements", ["copper/2"]), ("outputItem", "copper/2"), ("consumes", ["power"])):
        data = {"type": "GenericCrafter", field: value}
        invalid, _, document, _ = setup(data)
        plan = invalid.plan(document, PATH)
        assert document.data == data
        if field != "requirements":
            assert fields(plan)[field]["readOnly"]
        else:
            assert fields(plan)[field]["rows"][0]["notice"]
