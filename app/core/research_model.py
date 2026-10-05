"""Qt-free JSON contract helpers for Mindustry Research configuration."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .ref_candidates import UNLOCKABLE_CATEGORIES


RESEARCH_FIELDS = (
    "parent",
    "requirements",
    "objectives",
    "planet",
    "root",
    "name",
    "requiresUnlock",
)

OBJECTIVE_CATEGORIES = {
    "Research": UNLOCKABLE_CATEGORIES,
    "Produce": UNLOCKABLE_CATEGORIES,
    "SectorComplete": ("SectorPresets",),
    "OnSector": ("SectorPresets",),
    "OnPlanet": ("Planets",),
}

# These are the field names read by Mindustry's Objective implementations.
OBJECTIVE_TARGET_FIELDS = {
    "Research": "content",
    "Produce": "content",
    "SectorComplete": "preset",
    "OnSector": "preset",
    "OnPlanet": "planet",
}


def as_research_object(value: Any) -> dict[str, Any]:
    """Return the editable object form while accepting the legacy string form."""
    if isinstance(value, str):
        return {"parent": value} if value else {}
    if not isinstance(value, dict):
        return {}
    # The editor renders only RESEARCH_FIELDS, but existing mods may carry
    # newer or mod-specific keys. Keep those keys through any supported edit.
    return deepcopy(value)


def serialize_research(original: Any, research: dict[str, Any]) -> str | dict[str, Any] | None:
    """Preserve an unchanged legacy string; otherwise emit the allowed object form."""
    normalized = as_research_object(research)
    if isinstance(original, str) and normalized == as_research_object(original):
        return original
    return normalized or None
