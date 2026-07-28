package dev.moma.extractor;

import arc.struct.Seq;
import mindustry.ctype.Content;
import mindustry.ctype.UnlockableContent;
import mindustry.entities.bullet.BulletType;
import mindustry.type.UnitType;
import mindustry.type.Weapon;
import mindustry.world.Block;

import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import java.util.*;

/**
 * Extracts class field metadata from Mindustry content classes via reflection.
 * Walks the inheritance chain to collect all fields with their types, defaults, and nullability.
 */
public class ClassExtractor {

    /** The content classes we care about in v1 (extensible later) */
    private static final List<Class<?>> TARGET_CLASSES = List.of(
            UnitType.class,
            Block.class,
            Weapon.class,
            BulletType.class
    );

    /** Additional block subclasses to extract */
    private static final List<Class<?>> BLOCK_SUBCLASSES = List.of(
            mindustry.world.blocks.defense.Wall.class,
            mindustry.world.blocks.defense.turrets.ItemTurret.class
    );

    public Map<String, ClassDef> extract() {
        Map<String, ClassDef> result = new LinkedHashMap<>();

        for (Class<?> clazz : TARGET_CLASSES) {
            extractClass(clazz, result);
        }
        for (Class<?> clazz : BLOCK_SUBCLASSES) {
            extractClass(clazz, result);
        }

        return result;
    }

    private void extractClass(Class<?> clazz, Map<String, ClassDef> result) {
        String name = clazz.getSimpleName();
        if (result.containsKey(name)) return;

        // Extract parent first (recursion)
        String parentName = null;
        Class<?> parent = clazz.getSuperclass();
        if (parent != null && parent != Object.class && Content.class.isAssignableFrom(parent)) {
            parentName = parent.getSimpleName();
            extractClass(parent, result);
        }

        // Collect fields declared in THIS class only (parent fields come from parent def)
        List<FieldDef> fields = new ArrayList<>();
        for (Field field : clazz.getDeclaredFields()) {
            int mods = field.getModifiers();
            // Skip static, transient, synthetic fields
            if (Modifier.isStatic(mods) || Modifier.isTransient(mods) || field.isSynthetic()) {
                continue;
            }
            // Skip internal/implementation fields
            if (field.getName().startsWith("$") || field.getName().contains("$")) {
                continue;
            }

            FieldDef def = extractField(field, clazz);
            if (def != null) {
                fields.add(def);
            }
        }

        ClassDef classDef = new ClassDef();
        classDef.name = name;
        classDef.fullName = clazz.getName();
        classDef.parent = parentName;
        classDef.fields = fields;

        result.put(name, classDef);
    }

    private FieldDef extractField(Field field, Class<?> owner) {
        FieldDef def = new FieldDef();
        def.name = field.getName();
        def.javaType = field.getType().getSimpleName();

        // Determine mode
        def.mode = determineMode(field);

        // Nullability: primitive types are never null
        def.nullable = !field.getType().isPrimitive()
                && field.getAnnotation(arc.util.Nullable.class) != null;

        // For non-primitive, non-annotated fields, check if type is a reference type
        if (!field.getType().isPrimitive() && def.nullable == null) {
            // Heuristic: object fields are nullable by default in Mindustry
            def.nullable = true;
        }

        // Default value (try to read from a fresh instance)
        def.defaultValue = getDefaultValue(field, owner);

        // For ARRAY mode, determine element type
        if ("ARRAY".equals(def.mode)) {
            def.elementType = resolveElementType(field);
            def.polymorphic = isPolymorphic(field);
        }

        // For STRING_REF mode, determine reference source
        if ("STRING_REF".equals(def.mode)) {
            def.refSource = resolveRefSource(field);
        }

        // For INLINE_OBJECT mode, determine the target class
        if ("INLINE_OBJECT".equals(def.mode)) {
            def.inlineType = field.getType().getSimpleName();
        }

        return def;
    }

    private String determineMode(Field field) {
        Class<?> type = field.getType();

        // Primitives and wrappers
        if (type.isPrimitive() || type == Boolean.class || type == Integer.class
                || type == Float.class || type == Double.class || type == Long.class) {
            return "PRIMITIVE";
        }

        // String
        if (type == String.class) {
            return "PRIMITIVE";
        }

        // Color
        if (type.getSimpleName().equals("Color")) {
            return "PRIMITIVE";
        }

        // Seq (Mindustry's array type)
        if (Seq.class.isAssignableFrom(type)) {
            return "ARRAY";
        }

        // Java arrays
        if (type.isArray()) {
            return "ARRAY";
        }

        // ObjectMap / HashMap → treat as inline
        if (Map.class.isAssignableFrom(type) || type.getSimpleName().equals("ObjectMap")) {
            return "INLINE_OBJECT";
        }

        // Content subtypes that are typically referenced by name
        if (isReferenceType(type)) {
            return "STRING_REF";
        }

        // Other Content subtypes → inline object
        if (Content.class.isAssignableFrom(type) || BulletType.class.isAssignableFrom(type)
                || Weapon.class.isAssignableFrom(type)) {
            return "INLINE_OBJECT";
        }

        // Enum types
        if (type.isEnum()) {
            return "STRING_REF";
        }

        // Fallback
        return "PRIMITIVE";
    }

    private boolean isReferenceType(Class<?> type) {
        // Items, Liquids, StatusEffects are referenced by name in JSON
        String name = type.getSimpleName();
        return name.equals("Item") || name.equals("Liquid") || name.equals("StatusEffect")
                || name.equals("AmmoType") || name.equals("Category") || name.equals("ContentType");
    }

    private String resolveElementType(Field field) {
        // Try generic type first
        Type genericType = field.getGenericType();
        if (genericType instanceof ParameterizedType pt) {
            Type[] typeArgs = pt.getActualTypeArguments();
            if (typeArgs.length > 0) {
                Type arg = typeArgs[0];
                if (arg instanceof Class<?> c) {
                    return c.getSimpleName();
                }
                return arg.getTypeName();
            }
        }
        // Java array
        if (field.getType().isArray()) {
            return field.getType().getComponentType().getSimpleName();
        }
        return "Object";
    }

    private boolean isPolymorphic(Field field) {
        String elementType = resolveElementType(field);
        // BulletType fields are polymorphic (BasicBulletType, LaserBulletType, etc.)
        return "BulletType".equals(elementType) || "Weapon".equals(elementType);
    }

    private String resolveRefSource(Field field) {
        String typeName = field.getType().getSimpleName();
        return switch (typeName) {
            case "Item" -> "Items";
            case "Liquid" -> "Liquids";
            case "StatusEffect" -> "StatusEffects";
            case "AmmoType" -> "Items"; // AmmoType references items
            default -> typeName + "s";
        };
    }

    private Object getDefaultValue(Field field, Class<?> owner) {
        // For primitives, return Java default
        Class<?> type = field.getType();
        if (type == boolean.class) return false;
        if (type == int.class) return 0;
        if (type == float.class) return 0.0f;
        if (type == double.class) return 0.0;
        if (type == long.class) return 0L;

        // For object types, try to instantiate owner and read field
        try {
            // UnitType and Block require a name parameter
            Object instance = createMinimalInstance(owner);
            if (instance != null) {
                field.setAccessible(true);
                Object value = field.get(instance);
                // Only return serializable defaults
                if (value == null || value instanceof Number || value instanceof Boolean
                        || value instanceof String) {
                    return value;
                }
            }
        } catch (Exception ignored) {
            // Can't instantiate or read — leave default as null
        }
        return null;
    }

    private Object createMinimalInstance(Class<?> clazz) {
        try {
            if (UnitType.class.isAssignableFrom(clazz)) {
                return new UnitType("extractor-temp");
            }
            if (Block.class.isAssignableFrom(clazz)) {
                return clazz.getDeclaredConstructor(String.class).newInstance("extractor-temp");
            }
            if (Weapon.class.isAssignableFrom(clazz)) {
                return new Weapon("extractor-temp");
            }
            if (BulletType.class.isAssignableFrom(clazz)) {
                return clazz.getDeclaredConstructor().newInstance();
            }
        } catch (Exception ignored) {
        }
        return null;
    }

    // ─── Data classes ───────────────────────────────────────────────────────────

    public static class ClassDef {
        public String name;
        public String fullName;
        public String parent;
        public List<FieldDef> fields;
    }

    public static class FieldDef {
        public String name;
        public String javaType;
        public String mode;           // PRIMITIVE | STRING_REF | INLINE_OBJECT | ARRAY
        public Boolean nullable;
        public Object defaultValue;
        public String elementType;    // for ARRAY
        public Boolean polymorphic;   // for ARRAY
        public String refSource;      // for STRING_REF
        public String inlineType;     // for INLINE_OBJECT
    }
}
