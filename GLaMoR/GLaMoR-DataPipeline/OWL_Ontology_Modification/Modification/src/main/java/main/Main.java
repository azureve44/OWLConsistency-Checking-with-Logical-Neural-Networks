package main;
import anti_pattern.Anti_Pattern;
import anti_pattern.implementations.*;
import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.formats.FunctionalSyntaxDocumentFormat;
import org.semanticweb.owlapi.model.*;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.Collectors;
public class Main {
    private static final List<String> PREFIXES = List.of("EID", "AIO", "OIL", "CSC", "OILWI", "OILWPI", "OOD", "OOR", "SOSINETO", "UE", "UEWI1", "UEWI2", "UEWIP", "UEWPI");
    private static final String INPUT_PATH = System.getenv().getOrDefault("INPUT_PATH", "/input");
    private static final String OUTPUT_PATH = System.getenv().getOrDefault("OUTPUT_PATH", "/output");
    private static final boolean ENABLE_MULTI_PASS = Boolean.parseBoolean(System.getenv().getOrDefault("ENABLE_MULTI_PASS", "true"));
    private static final int MAX_INJECTION_PASSES = Integer.parseInt(System.getenv().getOrDefault("MAX_INJECTION_PASSES", "3"));
    private static final int MODIFICATION_THREADS = Integer.parseInt(System.getenv().getOrDefault("MODIFICATION_THREADS", "16"));
    private static final Set<String> ENABLED_PATTERN_NAMES = parseEnabledPatternNames(System.getenv("ENABLED_PATTERNS"));
    private static final List<Anti_Pattern> consideredAntiPattern = buildConsideredAntiPatternList();
    private static final class OntologyProfile {
        final int someValuesFrom;
        final int allValuesFrom;
        final int maxCardinality;
        final int disjointClasses;
        final int objectPropertyAssertions;
        final int subPropertyAxioms;
        final int inversePropertyAxioms;
        OntologyProfile(int someValuesFrom,
                        int allValuesFrom,
                        int maxCardinality,
                        int disjointClasses,
                        int objectPropertyAssertions,
                        int subPropertyAxioms,
                        int inversePropertyAxioms) {
            this.someValuesFrom = someValuesFrom;
            this.allValuesFrom = allValuesFrom;
            this.maxCardinality = maxCardinality;
            this.disjointClasses = disjointClasses;
            this.objectPropertyAssertions = objectPropertyAssertions;
            this.subPropertyAxioms = subPropertyAxioms;
            this.inversePropertyAxioms = inversePropertyAxioms;
        }
        @Override
        public String toString() {
            return "someValuesFrom=" + someValuesFrom
                    + " allValuesFrom=" + allValuesFrom
                    + " maxCardinality=" + maxCardinality
                    + " disjoint=" + disjointClasses
                    + " objPropAssertion=" + objectPropertyAssertions
                    + " subProperty=" + subPropertyAxioms
                    + " inverseOf=" + inversePropertyAxioms;
        }
    }
    private static List<Anti_Pattern> allAntiPatterns() {
        return List.of(
                new EID(),
                new AIO(),
                new CSC(),
                new OOR(),
                new OOD(),
                new OIL(),
                new OILWI(),
                new OILWPI(),
                new SOSINETO(),
                new UE(),
                new UEWI1(),
                new UEWI2(),
                new UEWIP(),
                new UEWPI()
        );
    }
    private static Set<String> parseEnabledPatternNames(String raw) {
        if (raw == null || raw.trim().isEmpty()) {
            return Collections.emptySet();
        }
        return Arrays.stream(raw.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .map(String::toUpperCase)
                .collect(Collectors.toCollection(LinkedHashSet::new));
    }
    private static List<Anti_Pattern> buildConsideredAntiPatternList() {
        List<Anti_Pattern> all = allAntiPatterns();
        if (ENABLED_PATTERN_NAMES.isEmpty()) {
            return new LinkedList<>(all);
        }
        List<Anti_Pattern> filtered = all.stream()
                .filter(pattern -> ENABLED_PATTERN_NAMES.contains(pattern.getName().toUpperCase()))
                .collect(Collectors.toCollection(LinkedList::new));
        Set<String> foundNames = filtered.stream()
                .map(pattern -> pattern.getName().toUpperCase())
                .collect(Collectors.toCollection(LinkedHashSet::new));
        Set<String> unknown = new LinkedHashSet<>(ENABLED_PATTERN_NAMES);
        unknown.removeAll(foundNames);
        if (!unknown.isEmpty()) {
            System.err.println("Unknown anti-pattern names requested via ENABLED_PATTERNS: " + unknown);
        }
        if (filtered.isEmpty()) {
            throw new IllegalArgumentException("No valid anti-patterns enabled. ENABLED_PATTERNS=" + ENABLED_PATTERN_NAMES);
        }
        return filtered;
    }
    private static boolean hasKnownPatternPrefix(String fileName) {
        String name = baseName(fileName);
        String prefix = name.split("_", 2)[0];
        return PREFIXES.contains(prefix);
    }
    public static void main(String[] args) {
        File inputDir = new File(INPUT_PATH);
        File[] dir = inputDir.listFiles();
        if (dir == null) {
            System.err.println("Input path is missing or not readable: " + inputDir.getAbsolutePath());
            return;
        }
        System.out.println("Enabled anti-patterns: " + (ENABLED_PATTERN_NAMES.isEmpty() ? "ALL" : ENABLED_PATTERN_NAMES));
        ExecutorService executor = Executors.newFixedThreadPool(Math.max(1, MODIFICATION_THREADS));
        List<Callable<Void>> tasks = new ArrayList<>();
        for (File file : dir) {
            if (!file.isFile() || file.getName().startsWith(".")) continue;
            if (hasKnownPatternPrefix(file.getName())) continue;
            tasks.add(() -> {
                try {
                    List<String> fileNames = executeInjection(file.getPath());
                    System.out.println("Created Files: " + fileNames);
                } catch (StackOverflowError overflowError) {
                    System.out.println("Overflow on ontology: " + file.getName());
                }
                return null;
            });
        }
        try {
            executor.invokeAll(tasks);
            executor.shutdown();
        } catch (InterruptedException e) {
            System.err.println("Execution interrupted: " + e.getMessage());
            Thread.currentThread().interrupt();
        }
    }
    private static OWLOntology loadOntology(File file, OWLOntologyManager manager) {
        try {
            OWLOntology ontology = manager.loadOntologyFromOntologyDocument(file);
            OWLDocumentFormat format = manager.getOntologyFormat(ontology);
            String formatName = (format == null) ? "unknown" : format.getKey();
            System.out.println("Ontology " + file.getName() + " loaded successfully. format=" + formatName);
            return ontology;
        } catch (Exception e) {
            System.err.println("Couldn't load ontology " + file.getPath() + ": " + e.getMessage());
            return null;
        }
    }
    private static String baseName(String path) {
        if (path == null) return "";
        String p = path.trim().replace("\\", "/");
        int idx = p.lastIndexOf('/');
        return idx >= 0 ? p.substring(idx + 1) : p;
    }
    private static File resolveOntologyFile(String payload) {
        String p = payload == null ? "" : payload.trim();
        if (p.isEmpty()) {
            return new File(INPUT_PATH, p);
        }
        if (p.startsWith("/input/")) {
            return new File(p);
        }
        if (p.startsWith("../input/")) {
            return new File(INPUT_PATH, p.substring("../input/".length()));
        }
        return new File(INPUT_PATH, baseName(p));
    }
    private static int countAxiomsInClosure(Set<OWLOntology> closure, AxiomType<?> axiomType) {
        int count = 0;
        for (OWLOntology o : closure) {
            count += o.getAxiomCount(axiomType);
        }
        return count;
    }
    private static int countLogicalAxiomsInClosure(Set<OWLOntology> closure) {
        int count = 0;
        for (OWLOntology o : closure) {
            count += o.getLogicalAxiomCount();
        }
        return count;
    }
    private static OntologyProfile buildProfile(OWLOntology ontology) {
        int someValuesFrom = (int) ontology.axioms(AxiomType.SUBCLASS_OF)
                .filter(ax -> ax.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_SOME_VALUES_FROM))
                .count();
        int allValuesFrom = (int) ontology.axioms(AxiomType.SUBCLASS_OF)
                .filter(ax -> ax.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_ALL_VALUES_FROM))
                .count();
        int maxCardinality = (int) ontology.axioms(AxiomType.SUBCLASS_OF)
                .filter(ax -> ax.getSuperClass().getClassExpressionType().equals(ClassExpressionType.OBJECT_MAX_CARDINALITY))
                .count();
        return new OntologyProfile(
                someValuesFrom,
                allValuesFrom,
                maxCardinality,
                ontology.getAxiomCount(AxiomType.DISJOINT_CLASSES),
                ontology.getAxiomCount(AxiomType.OBJECT_PROPERTY_ASSERTION),
                ontology.getAxiomCount(AxiomType.SUB_OBJECT_PROPERTY),
                ontology.getAxiomCount(AxiomType.INVERSE_OBJECT_PROPERTIES)
        );
    }
    private static List<String> missingSignalsForPattern(String patternName, OntologyProfile profile) {
        List<String> missingSignals = new ArrayList<>();
        switch (patternName) {
            case "OOR":
            case "OOD":
                if (profile.objectPropertyAssertions == 0) missingSignals.add("objPropAssertion>0");
                if (profile.disjointClasses == 0) missingSignals.add("disjoint>0");
                break;
            case "OIL":
            case "OILWI":
            case "OILWPI":
            case "SOSINETO":
            case "UEWI1":
            case "UEWI2":
            case "UEWPI":
                if (profile.allValuesFrom == 0) missingSignals.add("allValuesFrom>0");
                if (profile.disjointClasses == 0) missingSignals.add("disjoint>0");
                break;
            case "UEWIP":
                if (profile.inversePropertyAxioms == 0) missingSignals.add("inverseOf>0");
                if (profile.someValuesFrom == 0) missingSignals.add("someValuesFrom>0");
                break;
            case "UE":
                if (profile.someValuesFrom == 0) missingSignals.add("someValuesFrom>0");
                break;
            default:
                break;
        }
        return missingSignals;
    }
    private static OWLOntology cloneOntology(OWLOntology source) throws OWLOntologyCreationException {
        OWLOntologyManager snapshotManager = OWLManager.createOWLOntologyManager();
        OWLOntology snapshot = source.getOntologyID().isAnonymous()
                ? snapshotManager.createOntology()
                : snapshotManager.createOntology(source.getOntologyID());
        for (OWLImportsDeclaration declaration : source.getImportsDeclarations()) {
            snapshotManager.applyChange(new AddImport(snapshot, declaration));
        }
        snapshotManager.addAxioms(snapshot, source.getAxioms());
        return snapshot;
    }
    private static boolean saveInjectedVariant(OWLOntology sourceOntology,
                                               List<OWLAxiom> injectionAxioms,
                                               File outputFile) {
        try {
            OWLOntology snapshot = cloneOntology(sourceOntology);
            OWLOntologyManager snapshotManager = snapshot.getOWLOntologyManager();
            snapshotManager.addAxioms(snapshot, injectionAxioms);
            OWLDocumentFormat format = sourceOntology.getOWLOntologyManager().getOntologyFormat(sourceOntology);
            if (format == null) {
                format = new FunctionalSyntaxDocumentFormat();
            }
            snapshotManager.saveOntology(snapshot, format, new FileOutputStream(outputFile));
            return true;
        } catch (OWLOntologyStorageException storageException) {
            System.err.println("Failed to save ontology variant to " + outputFile.getAbsolutePath() + " due to " + storageException.getMessage());
            storageException.printStackTrace();
        } catch (FileNotFoundException e) {
            System.err.println("Could not open output file " + outputFile.getAbsolutePath() + ": " + e.getMessage());
            e.printStackTrace();
        } catch (OWLOntologyCreationException e) {
            System.err.println("Could not clone ontology for isolated save: " + e.getMessage());
            e.printStackTrace();
        }
        return false;
    }
    public static List<String> executeInjection(String filepath) {
        List<String> newFiles = new LinkedList<>();
        OWLOntologyManager manager = OWLManager.createOWLOntologyManager();
        File outputDir = new File(OUTPUT_PATH);
        if (!outputDir.exists() && !outputDir.mkdirs()) {
            System.err.println("Could not create output directory: " + outputDir.getAbsolutePath());
            return newFiles;
        }
        File file = resolveOntologyFile(filepath);
        if (hasKnownPatternPrefix(file.getName())) {
            System.out.println("Skipping already generated pattern file: " + file.getName());
            return newFiles;
        }
        OWLOntology ontology = loadOntology(file, manager);
        if (ontology == null) return newFiles;
        Set<OWLOntology> importsClosure = ontology.getImportsClosure();
        OntologyProfile profile = buildProfile(ontology);
        System.out.println(file.getPath() + ": Checking for pattern");
        System.out.println("Axiom profile " + file.getName()
                + " | subClass=" + ontology.getAxiomCount(AxiomType.SUBCLASS_OF)
                + " disjoint=" + ontology.getAxiomCount(AxiomType.DISJOINT_CLASSES)
                + " equiv=" + ontology.getAxiomCount(AxiomType.EQUIVALENT_CLASSES)
                + " domain=" + ontology.getAxiomCount(AxiomType.OBJECT_PROPERTY_DOMAIN)
                + " range=" + ontology.getAxiomCount(AxiomType.OBJECT_PROPERTY_RANGE)
                + " classAssertion=" + ontology.getAxiomCount(AxiomType.CLASS_ASSERTION)
                + " objPropAssertion=" + ontology.getAxiomCount(AxiomType.OBJECT_PROPERTY_ASSERTION)
                + " declarations=" + ontology.getAxiomCount(AxiomType.DECLARATION));
        System.out.println("Imports profile " + file.getName()
                + " | importDecl=" + ontology.getImportsDeclarations().size()
                + " closureOntologies=" + importsClosure.size()
                + " closureLogical=" + countLogicalAxiomsInClosure(importsClosure)
                + " closureSubClass=" + countAxiomsInClosure(importsClosure, AxiomType.SUBCLASS_OF)
                + " closureDisjoint=" + countAxiomsInClosure(importsClosure, AxiomType.DISJOINT_CLASSES)
                + " closureEquiv=" + countAxiomsInClosure(importsClosure, AxiomType.EQUIVALENT_CLASSES)
                + " closureDomain=" + countAxiomsInClosure(importsClosure, AxiomType.OBJECT_PROPERTY_DOMAIN)
                + " closureRange=" + countAxiomsInClosure(importsClosure, AxiomType.OBJECT_PROPERTY_RANGE));
        System.out.println("Pattern prerequisites " + file.getName() + " | " + profile);
        Set<OWLAxiom> injectedAxiomSet = new HashSet<>();
        int passLimit = ENABLE_MULTI_PASS ? Math.max(1, MAX_INJECTION_PASSES) : 1;
        for (int pass = 1; pass <= passLimit; pass++) {
            Map<String, List<OWLAxiom>> possibleInjections = new LinkedHashMap<>();
            for (Anti_Pattern pattern : consideredAntiPattern) {
                try {
                    Optional<List<OWLAxiom>> injectablePattern = pattern.checkForPossiblePatternCompletion(ontology);
                    if (injectablePattern.isPresent()) {
                        List<OWLAxiom> freshAxioms = injectablePattern.get().stream()
                                .filter(ax -> !ontology.containsAxiom(ax))
                                .filter(injectedAxiomSet::add)
                                .collect(Collectors.toList());
                        if (!freshAxioms.isEmpty()) {
                            possibleInjections.put(pattern.getName(), freshAxioms);
                            System.out.println("Anti_Pattern hit: " + pattern.getName()
                                    + " pass=" + pass
                                    + " -> " + freshAxioms.size()
                                    + " axioms for " + file.getName());
                        } else {
                            System.out.println("Anti_Pattern duplicate-only: " + pattern.getName()
                                    + " pass=" + pass
                                    + " for " + file.getName());
                        }
                    } else {
                        List<String> missingSignals = missingSignalsForPattern(pattern.getName(), profile);
                        if (missingSignals.isEmpty()) {
                            System.out.println("Anti_Pattern miss: " + pattern.getName() + " pass=" + pass + " for " + file.getName());
                        } else {
                            System.out.println("Anti_Pattern miss: " + pattern.getName()
                                    + " pass=" + pass
                                    + " for " + file.getName()
                                    + " | missing=" + String.join(",", missingSignals));
                        }
                    }
                } catch (Throwable t) {
                    System.err.println("Anti_Pattern error: " + pattern.getName()
                            + " pass=" + pass
                            + " for " + file.getName()
                            + " -> " + t.getClass().getSimpleName() + ": " + t.getMessage());
                    t.printStackTrace();
                }
            }
            if (possibleInjections.isEmpty()) {
                if (pass == 1) {
                    System.out.println("No injectable anti-pattern found for " + file.getName());
                } else {
                    System.out.println("No additional injectable anti-pattern found on pass " + pass + " for " + file.getName());
                }
                break;
            }
            for (Map.Entry<String, List<OWLAxiom>> injection : possibleInjections.entrySet()) {
                String patternName = injection.getKey();
                List<OWLAxiom> injectionAxioms = injection.getValue();
                String sourceName = file.getName();
                String outputName = patternName + "_p" + pass + "_" + injectionAxioms.size() + "_" + sourceName;
                File outputFile = new File(outputDir, outputName);
                if (saveInjectedVariant(ontology, injectionAxioms, outputFile)) {
                    newFiles.add(outputName);
                    System.out.println("Successfully saved Ontology with pattern " + patternName + " pass=" + pass + ": " + outputName);
                }
            }
            for (List<OWLAxiom> injectionAxioms : possibleInjections.values()) {
                for (OWLAxiom injectionAxiom : injectionAxioms) {
                    manager.addAxiom(ontology, injectionAxiom);
                }
            }
            if (!ENABLE_MULTI_PASS) {
                break;
            }
        }
        return newFiles;
    }
}
