"""Metadata access layer. Reads the metadata/ directory produced by the Java extractor.

Interface (3 methods):
    get_class(name) -> ClassDef       (fields already merged from inheritance chain)
    get_instance(category, name) -> dict
    list_instances(category) -> list[str]
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FieldDef:
    name: str
    java_type: str
    mode: str  # PRIMITIVE | STRING_REF | INLINE_OBJECT | ARRAY
    nullable: bool = True
    default: Any = None
    element_type: str | None = None
    polymorphic: bool = False
    ref_source: str | None = None
    inline_type: str | None = None
    doc: str = ""

    # ── 字段可见性规则（唯一来源，Validator 和 EditorPanel 共用）──────────

    _INTERNAL_SUFFIXES = ("Region", "Sound", "Effect", "Controller", "Color")
    _INTERNAL_NAMES = frozenset({
        "id", "minfo", "stats", "localizedName",
        "alwaysUnlocked", "removed",
        "uiIcon", "fullIcon", "fullOverride", "shownPlanets",
        "databaseTabs", "allDatabaseTabs", "techNodes", "techNode",
        "constructor", "firstRequirements",
        "engineColorInner", "engineColor", "healColor",
        "generateIcons", "generateFullIcon", "internalGenerateSprites",
        "cachedRequirements", "totalRequirements",
        "dpsEstimate", "sample", "unlocked",
        "hideDatabase", "databaseCategory", "databaseTag",
    })
    _EDITABLE_JAVA_TYPES = frozenset({
        "float", "double", "int", "long", "short", "boolean", "String", "Color",
    })

    @property
    def is_internal(self) -> bool:
        """True if this field is engine-internal and never set in mod JSON.

        Used by Validator (skip validation) and EditorPanel (hide from
        add-field menu). Single source of truth — no duplicated blacklists.
        """
        if self.name in self._INTERNAL_NAMES:
            return True
        if any(self.name.endswith(s) for s in self._INTERNAL_SUFFIXES):
            return True
        # Non-editable primitive types (e.g. Object references stored as primitives)
        if self.mode == "PRIMITIVE" and self.java_type not in self._EDITABLE_JAVA_TYPES:
            return True
        return False


@dataclass
class ClassDef:
    name: str
    full_name: str
    parent: str | None
    fields: list[FieldDef] = field(default_factory=list)


class Metadata:
    """Lazy-loading accessor for extracted Mindustry metadata."""

    # Types that don't have dedicated metadata classes but are used in mods.
    # Mapped to the closest parent class with metadata.
    _TYPE_ALIASES: dict[str, str] = {
        "PowerTurret": "Turret",
        "payload": "UnitType",
        "tank": "UnitType",
        "naval": "UnitType",
        "crawler": "UnitType",
        "mech": "UnitType",
        "legs": "UnitType",
        "hover": "UnitType",
        "Liquid": "UnlockableContent",
    }

    def __init__(self, metadata_dir: Path | str) -> None:
        self._dir = Path(metadata_dir)
        self._manifest: dict[str, Any] | None = None
        self._class_cache: dict[str, ClassDef] = {}
        self._instance_list_cache: dict[str, list[str]] = {}

    # ── public interface ────────────────────────────────────────────────

    def get_class(self, name: str) -> ClassDef:
        """Return class definition with ALL fields (inheritance chain merged)."""
        if name in self._class_cache:
            return self._class_cache[name]

        raw = self._load_class_file(name)
        if raw is None:
            # Try type alias fallback (e.g. PowerTurret → Turret, payload → UnitType)
            alias = self._TYPE_ALIASES.get(name)
            if alias is not None:
                return self.get_class(alias)
            raise KeyError(f"Unknown class: {name}")

        # Build own fields
        own_fields = [self._parse_field(f) for f in raw.get("fields", [])]

        # Merge parent fields (parent first, own overrides)
        parent_name = raw.get("parent")
        if parent_name:
            try:
                parent_def = self.get_class(parent_name)
                merged = {f.name: f for f in parent_def.fields}
                merged.update({f.name: f for f in own_fields})
                own_fields = list(merged.values())
            except KeyError:
                pass  # parent not in extracted set, skip

        class_def = ClassDef(
            name=raw["name"],
            full_name=raw.get("fullName", ""),
            parent=parent_name,
            fields=own_fields,
        )
        self._class_cache[name] = class_def
        return class_def

    def get_instance(self, category: str, name: str) -> dict[str, Any]:
        """Return full property values for a vanilla instance."""
        path = self._dir / "instances" / category / f"{name}.json"
        if not path.exists():
            raise KeyError(f"Instance not found: {category}/{name}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_instances(self, category: str) -> list[str]:
        """Return all instance names in a category."""
        if category in self._instance_list_cache:
            return self._instance_list_cache[category]

        cat_dir = self._dir / "instances" / category
        if not cat_dir.is_dir():
            return []

        names = sorted(p.stem for p in cat_dir.glob("*.json"))
        self._instance_list_cache[category] = names
        return names

    def list_instance_categories(self) -> list[str]:
        """Return all instance category names."""
        return self.manifest.get("instanceCategories", [])

    # ── helpers ─────────────────────────────────────────────────────────

    @property
    def manifest(self) -> dict[str, Any]:
        if self._manifest is None:
            manifest_path = self._dir / "manifest.json"
            if not manifest_path.exists():
                raise FileNotFoundError(
                    f"metadata/manifest.json not found at {self._dir}. "
                    "Run the extractor first."
                )
            self._manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return self._manifest

    @property
    def game_version(self) -> str:
        return self.manifest.get("gameVersion", "unknown")

    @property
    def available_classes(self) -> list[str]:
        return self.manifest.get("classes", [])

    @property
    def instance_categories(self) -> list[str]:
        return self.manifest.get("instanceCategories", [])

    def _load_class_file(self, name: str) -> dict[str, Any] | None:
        path = self._dir / "classes" / f"{name}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _parse_field(raw: dict[str, Any]) -> FieldDef:
        return FieldDef(
            name=raw["name"],
            java_type=raw.get("javaType", "Object"),
            mode=raw.get("mode", "PRIMITIVE"),
            nullable=raw.get("nullable", True),
            default=raw.get("default"),
            element_type=raw.get("elementType"),
            polymorphic=raw.get("polymorphic", False),
            ref_source=raw.get("refSource"),
            inline_type=raw.get("inlineType"),
            doc=raw.get("doc", ""),
        )
