package dev.moma.extractor;

import arc.struct.Seq;
import mindustry.Vars;
import mindustry.ctype.Content;
import mindustry.ctype.ContentType;
import mindustry.ctype.UnlockableContent;
import mindustry.entities.bullet.*;
import mindustry.type.*;
import mindustry.world.Block;

import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.util.*;

/**
 * Extracts all static content instances from Mindustry's content registries.
 * Outputs full property values for each instance (used by the reference/comparison panel).
 */
public class InstanceExtractor {

    /** Categories to extract and their corresponding ContentType */
    private static final Map<String, ContentType> CATEGORIES = new LinkedHashMap<>(Map.of(
            "UnitTypes", ContentType.unit,
            "Blocks", ContentType.block,
            "Items", ContentType.item,
            "Liquids", ContentType.liquid,
            "StatusEffects", ContentType.status,
            "Planets", ContentType.planet,
            "SectorPresets", ContentType.sector
    ));

    /** Fields to serialize for each content type (whitelist approach for v1) */
    private static final Map<String, Set<String>> FIELD_WHITELIST = Map.of(
            "UnitTypes", Set.of(
                    "name", "health", "armor", "speed", "hitSize", "flying",
                    "rotateSpeed", "accel", "drag", "range", "mineSpeed",
                    "buildSpeed", "itemCapacity", "ammoCapacity", "lightRadius"
            ),
            "Blocks", Set.of(
                    "name", "health", "size", "buildCost", "requirements",
                    "category", "buildTime", "hasPower", "hasLiquids", "hasItems",
                    "range", "reload", "ammoTypes", "targetAir", "targetGround"
            ),
            "Items", Set.of(
                    "name", "hardness", "cost", "color", "explosiveness",
                    "flammability", "radioactivity", "charge"
            ),
            "Liquids", Set.of(
                    "name", "heatCapacity", "temperature", "viscosity",
                    "explosiveness", "flammability", "color"
            ),
            "StatusEffects", Set.of(
                    "name", "damage", "speedMultiplier", "healthMultiplier",
                    "damageMultiplier", "reloadMultiplier", "buildSpeedMultiplier",
                    "transitionDamage", "effect"
            ),
            "Planets", Set.of("name"),
            "SectorPresets", Set.of("name")
    );

    /** Weapon fields to serialize (v1.1) — excludes complex types (Sound, Effect) */
    private static final Set<String> WEAPON_WHITELIST = Set.of(
            "name", "x", "y", "reload", "top", "rotate", "mirror",
            "alternate", "flipSprite", "display", "showStatSprite",
            "baseRotation", "continuous", "alwaysContinuous",
            "aimChangeSpeed", "controllable", "aiControllable",
            "alwaysShooting", "autoTarget", "predictTarget", "useAttackRange",
            "targetInterval", "targetSwitchInterval", "rotateSpeed",
            "inaccuracy", "shake", "recoil", "recoils", "recoilTime", "recoilPow",
            "cooldownTime", "shootX", "shootY", "xRand", "yRand", "shadow",
            "velocityRnd", "extraVelocity", "shootCone", "rotationLimit",
            "minWarmup", "shootWarmupSpeed", "smoothReloadSpeed", "linearWarmup",
            "soundPitchMin", "soundPitchMax", "ignoreRotation", "noAttack",
            "minShootVelocity", "parentizeEffects", "otherSide", "layerOffset",
            "activeSoundVolume", "shootSoundVolume", "shootStatusDuration",
            "shootOnDeath"
    );

    /** BulletType base fields to serialize (v1.1) */
    private static final Set<String> BULLET_WHITELIST = Set.of(
            "speed", "damage", "lifetime", "pierce", "pierceCap",
            "pierceBuilding", "knockback", "status", "statusDuration",
            "hitEffect", "despawnEffect", "shootEffect", "smokeEffect",
            "hitSound", "hitSoundVolume", "hitSoundPitch",
            "despawnHit", "incendAmount", "incendSpread", "incendChance",
            "ammoMultiplier", "reloadMultiplier", "recoilMultiplier",
            "damageMultiplier", "speedMultiplier", "dragMultiplier",
            "homingPower", "homingRange", "splashDamage", "splashDamageRadius",
            "lightning", "lightningLength", "lightningLengthRand",
            "lightningDamage", "lightningAngleRand", "lightningCone",
            "weaveScale", "weaveRandom", "weaveMag", "collides", "collidesAir",
            "collidesGround", "collidesTeam", "collidesTiles",
            "absorbable", "hittable", "reflectable", "keepVelocity",
            "hitShake", "hitSquares", "shootOnDeath", "suppression",
            "fragBullet", "fragBullets", "fragVelocityMin", "fragVelocityMax",
            "fragAngle", "fragSpread", "fragRandomAngle", "fragRandomSpread",
            "trailEffect", "trailParam", "trailLength", "trailWidth",
            "trailColor", "trailInterp", "frontTrail", "backTrail",
            "width", "height", "shrinkX", "shrinkY", "spin", "casingSplashes",
            "casingDespawnEffect", "casingShootEffect", "casingWidth",
            "casingHeight", "drawSize", "hitColor", "despawnShake",
            "lightColor", "lightOpacity", "puddleAmount", "puddleLiquid",
            "puddleRange", "orbiting", "buildingDamageMultiplier",
            "scaleLife", "scaleVelocity", "drag", "maxRange",
            "resetLength", "healPercent", "healAmount", "collisionRadius",
            "casingDespawnShake", "bulletSprite", "backSprite", "frontSprite",
            "casingSprite", "sprite"
    );

    /**
     * Extract all instances.
     * Note: Requires Mindustry's content system to be initialized.
     * In headless mode, we initialize it manually.
     */
    public Map<String, Map<String, Object>> extract() {
        Map<String, Map<String, Object>> result = new LinkedHashMap<>();

        // Initialize Mindustry content in headless mode
        initHeadless();

        for (var entry : CATEGORIES.entrySet()) {
            String categoryName = entry.getKey();
            ContentType contentType = entry.getValue();
            Set<String> whitelist = FIELD_WHITELIST.getOrDefault(categoryName, Set.of());

            Map<String, Object> instances = new LinkedHashMap<>();

            Seq<Content> contents = Vars.content.getBy(contentType);
            if (contents == null) continue;

            for (Content content : contents) {
                String name = getContentName(content);
                if (name == null || name.isEmpty()) continue;

                Map<String, Object> props = serializeContent(content, whitelist);
                if (!props.isEmpty()) {
                    instances.put(name, props);
                }
            }

            result.put(categoryName, instances);
        }

        // v1.1: Extract weapons from all UnitTypes
        System.out.println("      Extracting weapons from UnitTypes...");
        Map<String, Object> weapons = extractWeapons();
        result.put("Weapons", weapons);
        System.out.println("      Found " + weapons.size() + " unique weapons.");

        return result;
    }

    /**
     * Extract all weapons from UnitType instances (v1.1).
     * Deduplicates by weapon name — first occurrence wins.
     */
    private Map<String, Object> extractWeapons() {
        Map<String, Object> weapons = new LinkedHashMap<>();

        Seq<Content> units = Vars.content.getBy(ContentType.unit);
        if (units == null) return weapons;

        for (Content content : units) {
            if (!(content instanceof UnitType unitType)) continue;

            // Access the weapons Seq via reflection
            try {
                Field weaponsField = UnitType.class.getDeclaredField("weapons");
                weaponsField.setAccessible(true);
                Object weaponsObj = weaponsField.get(unitType);

                if (weaponsObj instanceof Seq<?> weaponSeq) {
                    for (Object w : weaponSeq) {
                        if (!(w instanceof Weapon weapon)) continue;
                        String name = weapon.name;
                        if (name == null || name.isEmpty() || weapons.containsKey(name)) continue;

                        Map<String, Object> weaponData = serializeWeapon(weapon);
                        weapons.put(name, weaponData);
                    }
                }
            } catch (Exception e) {
                System.err.println("      WARNING: Failed to extract weapons from "
                        + getContentName(content) + ": " + e.getMessage());
            }
        }

        return weapons;
    }

    /**
     * Serialize a Weapon instance to a flat field map, with nested bullet.
     */
    private Map<String, Object> serializeWeapon(Weapon weapon) {
        Map<String, Object> data = new LinkedHashMap<>();

        // Serialize whitelisted primitive fields
        for (Field field : Weapon.class.getDeclaredFields()) {
            if (Modifier.isStatic(field.getModifiers())) continue;
            if (!WEAPON_WHITELIST.contains(field.getName())) continue;

            try {
                field.setAccessible(true);
                Object value = field.get(weapon);
                Object serialized = serializeValue(value);
                if (serialized != null) {
                    data.put(field.getName(), serialized);
                }
            } catch (Exception ignored) {
            }
        }

        // Also walk parent class fields (none currently, but for robustness)
        Class<?> parent = Weapon.class.getSuperclass();
        while (parent != null && parent != Object.class) {
            for (Field field : parent.getDeclaredFields()) {
                if (Modifier.isStatic(field.getModifiers())) continue;
                if (!WEAPON_WHITELIST.contains(field.getName())) continue;
                if (data.containsKey(field.getName())) continue;

                try {
                    field.setAccessible(true);
                    Object value = field.get(weapon);
                    Object serialized = serializeValue(value);
                    if (serialized != null) {
                        data.put(field.getName(), serialized);
                    }
                } catch (Exception ignored) {
                }
            }
            parent = parent.getSuperclass();
        }

        // Serialize bullet
        if (weapon.bullet != null) {
            data.put("bullet", serializeBullet(weapon.bullet));
        }

        return data;
    }

    /**
     * Serialize a BulletType instance, including its concrete type name.
     */
    private Map<String, Object> serializeBullet(BulletType bullet) {
        Map<String, Object> data = new LinkedHashMap<>();

        // Record the concrete type (handle anonymous subclasses)
        String typeName = getConcreteClassName(bullet);
        data.put("type", typeName);

        // Walk the class hierarchy to collect all whitelisted fields
        Class<?> clazz = bullet.getClass();
        while (clazz != null && clazz != Object.class && Content.class.isAssignableFrom(clazz)) {
            for (Field field : clazz.getDeclaredFields()) {
                if (Modifier.isStatic(field.getModifiers())) continue;
                if (!BULLET_WHITELIST.contains(field.getName())) continue;
                if (data.containsKey(field.getName())) continue;

                try {
                    field.setAccessible(true);
                    Object value = field.get(bullet);
                    Object serialized = serializeValue(value);
                    if (serialized != null) {
                        data.put(field.getName(), serialized);
                    }
                } catch (Exception ignored) {
                }
            }
            clazz = clazz.getSuperclass();
        }

        return data;
    }

    private void initHeadless() {
        // Mindustry requires headless initialization to load content
        // This sets up the content registry without launching a game window
        try {
            // Set headless mode
            System.setProperty("java.awt.headless", "true");

            // Initialize core application stub
            if (!Vars.headless) {
                Vars.headless = true;
            }

            // Load content
            Vars.content = new mindustry.core.ContentLoader();
            Vars.content.createBaseContent();

            System.out.println("      Headless content initialized.");
        } catch (Exception e) {
            System.err.println("      WARNING: Headless init failed: " + e.getMessage());
            System.err.println("      Instance extraction may be incomplete.");
        }
    }

    private String getContentName(Content content) {
        if (content instanceof UnlockableContent uc) {
            return uc.name;
        }
        try {
            Field nameField = content.getClass().getField("name");
            return (String) nameField.get(content);
        } catch (Exception e) {
            return null;
        }
    }

    /**
     * Get the concrete class name, handling anonymous subclasses
     * (e.g. new BasicBulletType(2.5f, 9){{...}} → "BasicBulletType").
     */
    private String getConcreteClassName(Object obj) {
        Class<?> clazz = obj.getClass();
        while (clazz.isAnonymousClass() && clazz.getSuperclass() != null) {
            clazz = clazz.getSuperclass();
        }
        return clazz.getSimpleName();
    }

    private Map<String, Object> serializeContent(Content content, Set<String> whitelist) {
        Map<String, Object> props = new LinkedHashMap<>();
        Class<?> clazz = content.getClass();

        // Walk up the hierarchy to find all whitelisted fields
        while (clazz != null && clazz != Object.class) {
            for (Field field : clazz.getDeclaredFields()) {
                if (Modifier.isStatic(field.getModifiers())) continue;
                if (!whitelist.contains(field.getName())) continue;
                if (props.containsKey(field.getName())) continue; // Already found in subclass

                try {
                    field.setAccessible(true);
                    Object value = field.get(content);
                    Object serialized = serializeValue(value);
                    if (serialized != null) {
                        props.put(field.getName(), serialized);
                    }
                } catch (Exception ignored) {
                }
            }
            clazz = clazz.getSuperclass();
        }

        return props;
    }

    private Object serializeValue(Object value) {
        if (value == null) return null;

        // Primitives and wrappers
        if (value instanceof Number || value instanceof Boolean || value instanceof String) {
            return value;
        }

        // Color → hex string
        if (value instanceof arc.graphics.Color color) {
            return String.format("#%08x", color.rgba());
        }

        // ItemStack[] → list of {item, amount}
        if (value instanceof ItemStack[] stacks) {
            List<Map<String, Object>> list = new ArrayList<>();
            for (ItemStack stack : stacks) {
                list.add(Map.of("item", stack.item.name, "amount", stack.amount));
            }
            return list;
        }

        // Seq → list
        if (value instanceof Seq<?> seq) {
            List<Object> list = new ArrayList<>();
            for (Object item : seq) {
                Object s = serializeValue(item);
                if (s != null) list.add(s);
            }
            return list;
        }

        // Enum → name
        if (value instanceof Enum<?> e) {
            return e.name();
        }

        // Content references → name string
        if (value instanceof UnlockableContent uc) {
            return uc.name;
        }

        // Skip complex objects (weapons, bullets, etc.) in v1 instance dump
        return null;
    }
}
