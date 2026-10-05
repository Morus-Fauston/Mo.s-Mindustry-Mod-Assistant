"""The existing UI's supported type families, without importing Qt widgets."""

from app.core.metadata import GAME_UNIT_TYPE_TO_SUBTYPE


BULLET_TYPES = (
    "BasicBulletType", "LaserBulletType", "MissileBulletType", "ArtilleryBulletType", "FlakBulletType",
)
UNIT_TYPES = tuple(GAME_UNIT_TYPE_TO_SUBTYPE)
TYPE_LABELS = {
    "mech": "机甲", "flying": "飞行", "tank": "坦克", "legs": "多足",
    "BasicBulletType": "基础子弹", "LaserBulletType": "激光子弹", "MissileBulletType": "导弹",
    "ArtilleryBulletType": "炮弹", "FlakBulletType": "高射子弹",
}
