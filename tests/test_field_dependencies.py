"""Field-dependency evaluation stays independent from Qt widgets."""

from app.core.field_dependencies import inactive_dependencies
from app.core.metadata import Metadata
from app.core.validator import Validator
from pathlib import Path


def test_known_rules_report_only_set_dependents_when_the_prerequisite_is_false():
    assert inactive_dependencies("UnitType", {"engineSize": 0, "engineOffset": 12}) == {
        "engineOffset": "engineSize > 0"
    }
    assert inactive_dependencies("UnitType", {"engineSize": 2, "engineOffset": 12}) == {}
    assert inactive_dependencies("Weapon", {
        "rotate": False,
        "rotateSpeed": 8,
        "rotationLimit": 90,
        "continuous": False,
        "initialShootSound": "shoot",
    }) == {
        "rotateSpeed": "rotate 为 true",
        "rotationLimit": "rotate 为 true",
        "initialShootSound": "continuous 为 true",
    }


def test_missing_values_and_unknown_types_are_not_inactive():
    assert inactive_dependencies("UnitType", {"engineSize": 0}) == {}
    assert inactive_dependencies("Wall", {"engineOffset": 12}) == {}


def test_validator_reports_inactive_values_as_locatable_warnings():
    validator = Validator(Metadata(Path("metadata")))

    issues = validator.validate({
        "type": "mech", "health": 100, "engineSize": 0, "engineOffset": 8,
    })

    dependency_warnings = [issue for issue in issues if issue.path == "engineOffset"]
    assert len(dependency_warnings) == 1
    assert dependency_warnings[0].severity == "warning"
    assert dependency_warnings[0].field == "engineOffset"
    assert "engineSize > 0" in dependency_warnings[0].message
