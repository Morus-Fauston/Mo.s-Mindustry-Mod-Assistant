"""Qt-free candidate resolution for content reference editors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


UNLOCKABLE_CATEGORIES = (
    "Blocks",
    "UnitTypes",
    "Items",
    "Liquids",
    "StatusEffects",
    "Planets",
    "SectorPresets",
)

_CATEGORY_NAME_KEYS = {
    "Blocks": "blocks",
    "UnitTypes": "units",
    "Items": "items",
    "Liquids": "liquids",
    "StatusEffects": "status",
    "Planets": "planets",
    "SectorPresets": "sectors",
    "Weapons": "weapons",
}

_PROJECT_CATEGORY_MAP = {
    "blocks": "Blocks",
    "units": "UnitTypes",
    "weapons": "Weapons",
}


@dataclass(frozen=True)
class RefCandidate:
    """One selectable content identifier and its source/category metadata."""

    value: str
    category: str
    label: str
    is_project: bool = False


def resolve_candidates(
    metadata: Any,
    project: Any | None = None,
    categories: Iterable[str] = UNLOCKABLE_CATEGORIES,
    query: str = "",
    names_zh: dict[str, dict[str, str]] | None = None,
) -> list[RefCandidate]:
    """Resolve vanilla and current-project candidates, filtered by category/query."""
    selected_categories = tuple(categories)
    names_zh = names_zh or {}
    candidates = _project_candidates(project, selected_categories, names_zh)

    for category in selected_categories:
        name_key = _CATEGORY_NAME_KEYS.get(category, category.lower())
        try:
            names = metadata.list_instances(category)
        except Exception:
            names = []
        for name in sorted(names):
            candidates.append(RefCandidate(
                value=name,
                category=category,
                label=_display_label(name, names_zh.get(name_key, {})),
            ))

    needle = query.casefold().strip()
    if not needle:
        return candidates
    return [candidate for candidate in candidates if needle in candidate.label.casefold() or needle in candidate.value.casefold()]


def _project_candidates(
    project: Any | None,
    categories: tuple[str, ...],
    names_zh: dict[str, dict[str, str]],
) -> list[RefCandidate]:
    if project is None:
        return []
    try:
        mod_name = project.mod_info.name
        refs = project.contents.list()
    except (AttributeError, OSError):
        return []

    candidates: list[RefCandidate] = []
    for ref in refs:
        category = _PROJECT_CATEGORY_MAP.get(ref.category)
        if category not in categories:
            continue
        value = f"{mod_name}-{ref.name}"
        name_key = _CATEGORY_NAME_KEYS.get(category, category.lower())
        candidates.append(RefCandidate(
            value=value,
            category=category,
            label=_display_label(value, names_zh.get(name_key, {})),
            is_project=True,
        ))
    return sorted(candidates, key=lambda candidate: candidate.value)


def _display_label(value: str, names: dict[str, str]) -> str:
    chinese_name = names.get(value, "")
    return f"{chinese_name} ({value})" if chinese_name else value
