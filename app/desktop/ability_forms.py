"""Ability array projection on the existing nested form session."""

from dataclasses import replace

from app.core.ability_types import ABILITY_LABELS, DEFAULT_ABILITY_TYPE, create_ability
from app.core.metadata import ClassDef


class AbilityFormsService:
    """Register inline abilities without owning data, history or session state."""

    def __init__(self, nested):
        self.nested = nested
        nested.register_family(
            "Ability",
            choices=tuple({"value": kind, "label": label} for kind, label in ABILITY_LABELS.items()),
            default_type=DEFAULT_ABILITY_TYPE,
            create_default=create_ability,
            project_definition=self._project_definition,
        )

    @staticmethod
    def _project_definition(kind: str, definition: ClassDef) -> ClassDef:
        # ContentParser resolves Content subclasses from names. The extractor
        # reports these two UnitType fields as inline objects; correct only the
        # ability projection, leaving the shared metadata cache untouched.
        if kind not in ("SpawnDeathAbility", "UnitSpawnAbility"):
            return definition
        return replace(definition, fields=[
            replace(field, mode="STRING_REF", ref_source="UnitTypes", inline_type=None)
            if field.name == "unit" else field for field in definition.fields
        ])
