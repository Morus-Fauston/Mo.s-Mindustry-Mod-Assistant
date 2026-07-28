package dev.moma.extractor;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.*;

/**
 * Writes extracted metadata to the structured directory format:
 * 
 * metadata/
 * ├── manifest.json
 * ├── classes/
 * │   ├── UnitType.json
 * │   └── ...
 * ├── instances/
 * │   ├── UnitTypes/
 * │   │   ├── dagger.json
 * │   │   └── ...
 * │   └── ...
 * └── docs/
 *     └── field_docs.json
 */
public class JsonWriter {

    private final Path outputDir;
    private final Gson gson;

    public JsonWriter(Path outputDir) {
        this.outputDir = outputDir;
        this.gson = new GsonBuilder()
                .setPrettyPrinting()
                .serializeNulls()
                .serializeSpecialFloatingPointValues()
                .disableHtmlEscaping()
                .create();
    }

    public void writeManifest(Map<String, ClassExtractor.ClassDef> classDefs,
                              Map<String, Map<String, Object>> instances) throws IOException {
        Map<String, Object> manifest = new LinkedHashMap<>();
        manifest.put("gameVersion", Main.GAME_VERSION);
        manifest.put("extractorVersion", Main.EXTRACTOR_VERSION);
        manifest.put("generatedAt", Instant.now().toString());
        manifest.put("classes", new ArrayList<>(classDefs.keySet()));
        manifest.put("instanceCategories", new ArrayList<>(instances.keySet()));

        // Add instance counts per category
        Map<String, Integer> counts = new LinkedHashMap<>();
        for (var entry : instances.entrySet()) {
            counts.put(entry.getKey(), entry.getValue().size());
        }
        manifest.put("instanceCounts", counts);

        writeJson(outputDir.resolve("manifest.json"), manifest);
        System.out.println("      manifest.json");
    }

    public void writeClasses(Map<String, ClassExtractor.ClassDef> classDefs) throws IOException {
        Path classesDir = outputDir.resolve("classes");
        Files.createDirectories(classesDir);

        for (var entry : classDefs.entrySet()) {
            String className = entry.getKey();
            ClassExtractor.ClassDef def = entry.getValue();

            Map<String, Object> json = new LinkedHashMap<>();
            json.put("name", def.name);
            json.put("fullName", def.fullName);
            json.put("parent", def.parent);

            List<Map<String, Object>> fields = new ArrayList<>();
            for (ClassExtractor.FieldDef field : def.fields) {
                Map<String, Object> f = new LinkedHashMap<>();
                f.put("name", field.name);
                f.put("javaType", field.javaType);
                f.put("mode", field.mode);
                f.put("nullable", field.nullable);
                f.put("default", field.defaultValue);

                if (field.elementType != null) {
                    f.put("elementType", field.elementType);
                }
                if (field.polymorphic != null) {
                    f.put("polymorphic", field.polymorphic);
                }
                if (field.refSource != null) {
                    f.put("refSource", field.refSource);
                }
                if (field.inlineType != null) {
                    f.put("inlineType", field.inlineType);
                }

                fields.add(f);
            }
            json.put("fields", fields);

            writeJson(classesDir.resolve(className + ".json"), json);
        }
        System.out.println("      classes/ (" + classDefs.size() + " files)");
    }

    public void writeInstances(Map<String, Map<String, Object>> instances) throws IOException {
        Path instancesDir = outputDir.resolve("instances");
        Files.createDirectories(instancesDir);

        for (var categoryEntry : instances.entrySet()) {
            String category = categoryEntry.getKey();
            Map<String, Object> categoryInstances = categoryEntry.getValue();

            Path categoryDir = instancesDir.resolve(category);
            Files.createDirectories(categoryDir);

            for (var instanceEntry : categoryInstances.entrySet()) {
                String instanceName = instanceEntry.getKey();
                Object data = instanceEntry.getValue();

                // Sanitize filename (replace characters invalid on Windows)
                String safeName = instanceName.replaceAll("[<>:\"/\\\\|?*]", "_");
                writeJson(categoryDir.resolve(safeName + ".json"), data);
            }
            System.out.println("      instances/" + category + "/ ("
                    + categoryInstances.size() + " files)");
        }
    }

    public void writeFieldDocs(Map<String, Map<String, String>> docs) throws IOException {
        Path docsDir = outputDir.resolve("docs");
        Files.createDirectories(docsDir);
        writeJson(docsDir.resolve("field_docs.json"), docs);
        System.out.println("      docs/field_docs.json");
    }

    private void writeJson(Path path, Object data) throws IOException {
        Files.createDirectories(path.getParent());
        String json = gson.toJson(data);
        Files.writeString(path, json);
    }
}
