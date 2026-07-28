package dev.moma.extractor;

import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * MoMA Metadata Extractor
 * 
 * Extracts class metadata and instance data from Mindustry via reflection.
 * Output: structured JSON directory for the Python editor to consume.
 * 
 * Usage: java -jar extractor.jar [--output <dir>]
 * Default output: ../metadata (relative to working directory)
 */
public class Main {

    public static final String GAME_VERSION = "159";
    public static final String EXTRACTOR_VERSION = "1.0";

    public static void main(String[] args) {
        Path outputDir = parseOutputDir(args);

        System.out.println("=== MoMA Metadata Extractor v" + EXTRACTOR_VERSION + " ===");
        System.out.println("Target Mindustry version: v" + GAME_VERSION);
        System.out.println("Output directory: " + outputDir.toAbsolutePath());
        System.out.println();

        try {
            // Phase 1: Extract class definitions (field metadata)
            System.out.println("[1/3] Extracting class definitions...");
            ClassExtractor classExtractor = new ClassExtractor();
            var classDefs = classExtractor.extract();
            System.out.println("      Found " + classDefs.size() + " content classes.");

            // Phase 2: Extract static instances (all vanilla content objects)
            System.out.println("[2/3] Extracting static instances...");
            InstanceExtractor instanceExtractor = new InstanceExtractor();
            var instances = instanceExtractor.extract();
            int totalInstances = instances.values().stream().mapToInt(m -> m.size()).sum();
            System.out.println("      Found " + totalInstances + " instances across "
                    + instances.size() + " categories.");

            // Phase 3: Write output
            System.out.println("[3/3] Writing output...");
            JsonWriter writer = new JsonWriter(outputDir);
            writer.writeManifest(classDefs, instances);
            writer.writeClasses(classDefs);
            writer.writeInstances(instances);
            System.out.println("      Done.");

            System.out.println();
            System.out.println("=== Extraction complete ===");
            System.out.println("Files written to: " + outputDir.toAbsolutePath());

        } catch (Exception e) {
            System.err.println("FATAL: Extraction failed.");
            e.printStackTrace();
            System.exit(1);
        }
    }

    private static Path parseOutputDir(String[] args) {
        for (int i = 0; i < args.length - 1; i++) {
            if ("--output".equals(args[i]) || "-o".equals(args[i])) {
                return Paths.get(args[i + 1]);
            }
        }
        return Paths.get("..", "metadata");
    }
}
