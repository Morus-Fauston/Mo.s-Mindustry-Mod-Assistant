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
        nested.register_plan_extension(self._extend_plan)

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

    def _extend_plan(self, content, path, state, plan, nodes, budget):
        visited = set()
        while True:
            pending = [(key, node) for key, node in nodes.items() if key not in visited]
            if not pending:
                return
            for key, (data, forms, document, node_plan, scalar_target) in pending:
                visited.add(key)
                if not node_plan["knownType"] or scalar_target is not None:
                    continue
                definition = next((field for field in forms.definition.fields
                                   if field.name == "abilities" and field.mode == "ARRAY"
                                   and field.element_type == "Ability"), None)
                if definition is None:
                    continue
                for group in node_plan["groups"]:
                    for descriptor in group["fields"]:
                        if descriptor["name"] == definition.name:
                            self.nested._array(
                                descriptor, definition, data.get(definition.name),
                                [*node_plan["objectPath"], definition.name],
                                content, path, state, nodes, budget,
                            )
