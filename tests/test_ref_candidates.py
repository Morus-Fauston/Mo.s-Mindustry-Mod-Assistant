"""Candidate resolution for Research and other content references."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.ref_candidates import UNLOCKABLE_CATEGORIES, resolve_candidates


class _Metadata:
    def __init__(self, values: dict[str, list[str]]) -> None:
        self._values = values

    def list_instances(self, category: str) -> list[str]:
        return self._values.get(category, [])


@dataclass
class _Ref:
    name: str
    category: str


class _Contents:
    def list(self) -> list[_Ref]:
        return [_Ref("project-wall", "blocks"), _Ref("project-weapon", "weapons")]


class _Project:
    class _Info:
        name = "probe-mod"

    mod_info = _Info()
    contents = _Contents()


def test_unlockable_candidates_exclude_weapons_and_include_current_project_content():
    metadata = _Metadata({
        "Blocks": ["copper-wall"],
        "UnitTypes": ["dagger"],
        "Items": ["copper"],
        "Liquids": ["water"],
        "StatusEffects": ["burning"],
        "Planets": ["serpulo"],
        "SectorPresets": ["groundZero"],
        "Weapons": ["duo-weapon"],
    })

    candidates = resolve_candidates(metadata, _Project(), UNLOCKABLE_CATEGORIES)

    assert [candidate.value for candidate in candidates] == [
        "probe-mod-project-wall", "copper-wall", "dagger", "copper", "water",
        "burning", "serpulo", "groundZero",
    ]
    assert all(candidate.category != "Weapons" for candidate in candidates)


def test_bilingual_search_matches_chinese_or_english_identifiers():
    metadata = _Metadata({"Blocks": ["copper-wall"], "UnitTypes": ["dagger"]})
    names_zh = {"blocks": {"copper-wall": "铜墙"}, "units": {"dagger": "尖刀"}}

    by_chinese = resolve_candidates(metadata, categories=("Blocks", "UnitTypes"), query="铜", names_zh=names_zh)
    by_english = resolve_candidates(metadata, categories=("Blocks", "UnitTypes"), query="dag", names_zh=names_zh)

    assert [candidate.value for candidate in by_chinese] == ["copper-wall"]
    assert [candidate.value for candidate in by_english] == ["dagger"]
