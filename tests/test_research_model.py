"""Research JSON compatibility and objective category contracts."""

from app.core.research_model import (
    OBJECTIVE_CATEGORIES,
    OBJECTIVE_TARGET_FIELDS,
    RESEARCH_FIELDS,
    as_research_object,
    serialize_research,
)


def test_legacy_string_research_remains_a_string_until_the_object_is_changed():
    original = "copper-wall"
    research = as_research_object(original)

    assert research == {"parent": "copper-wall"}
    assert serialize_research(original, research) == "copper-wall"


def test_research_object_preserves_unknown_fields_while_exposing_the_confirmed_fields():
    original = {"parent": "copper-wall", "root": True, "unknown": "ignored"}

    research = as_research_object(original)

    assert tuple(RESEARCH_FIELDS) == (
        "parent", "requirements", "objectives", "planet", "root", "name", "requiresUnlock",
    )
    assert research == {"parent": "copper-wall", "root": True, "unknown": "ignored"}
    assert serialize_research(original, research) == research


def test_objective_types_use_only_their_confirmed_candidate_categories():
    assert OBJECTIVE_CATEGORIES["Research"] == (
        "Blocks", "UnitTypes", "Items", "Liquids", "StatusEffects", "Planets", "SectorPresets",
    )
    assert OBJECTIVE_CATEGORIES["Produce"] == OBJECTIVE_CATEGORIES["Research"]
    assert OBJECTIVE_CATEGORIES["SectorComplete"] == ("SectorPresets",)
    assert OBJECTIVE_CATEGORIES["OnSector"] == ("SectorPresets",)
    assert OBJECTIVE_CATEGORIES["OnPlanet"] == ("Planets",)
    assert OBJECTIVE_TARGET_FIELDS == {
        "Research": "content",
        "Produce": "content",
        "SectorComplete": "preset",
        "OnSector": "preset",
        "OnPlanet": "planet",
    }
