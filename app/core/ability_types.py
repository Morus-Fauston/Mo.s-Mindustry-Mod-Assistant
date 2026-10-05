"""Supported inline ability types and legacy explicit-creation defaults."""

from copy import deepcopy


ABILITY_LABELS = {
    "ShieldRegenFieldAbility": "范围护盾恢复",
    "RegenAbility": "生命恢复",
    "MoveLightningAbility": "移动闪电",
    "StatusFieldAbility": "范围状态",
    "ForceFieldAbility": "力场护盾",
    "EnergyFieldAbility": "能量场",
    "RepairFieldAbility": "范围修复",
    "ArmorPlateAbility": "装甲板",
    "MoveEffectAbility": "移动效果",
    "SpawnDeathAbility": "死亡生成单位",
    "LiquidExplodeAbility": "死亡液体爆发",
    "LiquidRegenAbility": "液体恢复",
    "SuppressionFieldAbility": "修复压制场",
    "UnitSpawnAbility": "定时生成单位",
    "ShieldArcAbility": "弧形护盾",
}
ABILITY_TYPES = tuple(ABILITY_LABELS)
DEFAULT_ABILITY_TYPE = "ShieldRegenFieldAbility"

# Preserve the six explicit defaults used by the existing Qt ability editor.
# Other configured defaults remain display-only until the user edits a field.
_DEFAULTS = {
    "ShieldRegenFieldAbility": {"amount": 1.0, "max": 100.0, "reload": 100.0, "range": 60.0},
    "RegenAbility": {"amount": 1.0},
    "MoveLightningAbility": {"damage": 10.0, "chance": 0.15, "length": 12},
    "StatusFieldAbility": {"duration": 60.0, "range": 60.0, "reload": 60.0},
    "ForceFieldAbility": {"max": 100.0, "regen": 0.5, "cooldown": 60.0, "radius": 60.0},
    "EnergyFieldAbility": {"damage": 10.0, "reload": 30.0, "range": 60.0},
}


def create_ability(kind: str) -> dict:
    """Return a detached legacy default only for an explicit insertion."""
    if not isinstance(kind, str) or kind not in ABILITY_TYPES:
        raise ValueError("请选择受支持的能力类型。")
    return {"type": kind, **deepcopy(_DEFAULTS.get(kind, {}))}
