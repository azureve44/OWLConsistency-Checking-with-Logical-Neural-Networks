package main;
import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.formats.FunctionalSyntaxDocumentFormat;
import org.semanticweb.owlapi.model.*;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
public class SeedMain {
    private static final List<String> KNOWN_PATTERN_PREFIXES = List.of("EID", "AIO", "OIL", "CSC", "OILWI", "OILWPI", "OOD", "OOR", "SOSINETO", "UE", "UEWI1", "UEWI2", "UEWIP", "UEWPI");
    private static final List<String> SUPPORTED_FAMILIES = List.of("AIO", "UE", "OIL", "CSC", "SOSINETO", "UEWI1", "UEWI2", "OILWI", "OOD", "OOR", "OILWPI", "UEWIP", "UEWPI");
    private static final String INPUT_PATH = System.getenv().getOrDefault("INPUT_PATH", "/input");
    private static final String OUTPUT_PATH = System.getenv().getOrDefault("OUTPUT_PATH", "/output");
    private static final String SEED_MANIFEST_PATH = System.getenv().getOrDefault("SEED_MANIFEST_PATH", "");
    private static final int MAX_FILES = Integer.parseInt(System.getenv().getOrDefault("MAX_FILES", "0"));
    private static final Set<String> SEED_FAMILIES = parseFamilies(System.getenv().getOrDefault("SEED_FAMILIES", String.join(",", SUPPORTED_FAMILIES)));
    private static final String UB = "http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#";
    private static Set<String> parseFamilies(String raw) {
        if (raw == null || raw.trim().isEmpty()) {
            return new LinkedHashSet<>(SUPPORTED_FAMILIES);
        }
        Set<String> families = Arrays.stream(raw.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .map(String::toUpperCase)
                .collect(Collectors.toCollection(LinkedHashSet::new));
        families.retainAll(new LinkedHashSet<>(SUPPORTED_FAMILIES));
        if (families.isEmpty()) {
            throw new IllegalArgumentException("No supported seed families selected. Requested=" + raw + " supported=" + SUPPORTED_FAMILIES);
        }
        return families;
    }
    private static boolean hasKnownPatternPrefix(String fileName) {
        String prefix = baseName(fileName).split("_", 2)[0];
        return KNOWN_PATTERN_PREFIXES.contains(prefix);
    }
    private static String baseName(String path) {
        if (path == null) return "";
        String p = path.trim().replace("\\", "/");
        int idx = p.lastIndexOf('/');
        return idx >= 0 ? p.substring(idx + 1) : p;
    }
    private static String stripExtension(String name) {
        int idx = name.lastIndexOf('.');
        return idx >= 0 ? name.substring(0, idx) : name;
    }
    private static OWLClass cls(OWLDataFactory df, String localName) {
        return df.getOWLClass(IRI.create(UB + localName));
    }
    private static OWLObjectProperty prop(OWLDataFactory df, String localName) {
        return df.getOWLObjectProperty(IRI.create(UB + localName));
    }
    private static OWLNamedIndividual ind(OWLDataFactory df, String localName) {
        return df.getOWLNamedIndividual(IRI.create(UB + localName));
    }
    private static List<OWLAxiom> buildSeedAxioms(OWLDataFactory df, String family) {
        switch (family) {
            case "AIO": {
                OWLClass university = cls(df, "University");
                OWLClass department = cls(df, "Department");
                OWLObjectProperty subOrganizationOf = prop(df, "subOrganizationOf");
                return List.of(df.getOWLSubClassOfAxiom(university, df.getOWLObjectSomeValuesFrom(subOrganizationOf, department)));
            }
            case "UE": {
                OWLClass professor = cls(df, "Professor");
                OWLClass graduateCourse = cls(df, "GraduateCourse");
                OWLObjectProperty teacherOf = prop(df, "teacherOf");
                return List.of(df.getOWLSubClassOfAxiom(professor, df.getOWLObjectSomeValuesFrom(teacherOf, graduateCourse)));
            }
            case "OIL": {
                OWLClass professor = cls(df, "Professor");
                OWLClass course = cls(df, "Course");
                OWLObjectProperty teacherOf = prop(df, "teacherOf");
                return List.of(df.getOWLSubClassOfAxiom(professor, df.getOWLObjectAllValuesFrom(teacherOf, course)));
            }
            case "CSC": {
                OWLClass fullProfessor = cls(df, "FullProfessor");
                OWLClass professor = cls(df, "Professor");
                OWLClass employee = cls(df, "Employee");
                return List.of(
                        df.getOWLSubClassOfAxiom(fullProfessor, professor),
                        df.getOWLSubClassOfAxiom(professor, employee)
                );
            }
            case "SOSINETO": {
                OWLClass phdStudent = cls(df, "PhDStudent");
                OWLClass graduateCourse = cls(df, "GraduateCourse");
                OWLClass undergraduateCourse = cls(df, "UndergraduateCourse");
                OWLObjectProperty takesCourse = prop(df, "takesCourse");
                return List.of(
                        df.getOWLSubClassOfAxiom(phdStudent, df.getOWLObjectSomeValuesFrom(takesCourse, graduateCourse)),
                        df.getOWLSubClassOfAxiom(phdStudent, df.getOWLObjectSomeValuesFrom(takesCourse, undergraduateCourse)),
                        df.getOWLDisjointClassesAxiom(graduateCourse, undergraduateCourse)
                );
            }
            case "UEWI1": {
                OWLClass fullProfessor = cls(df, "FullProfessor");
                OWLClass professor = cls(df, "Professor");
                OWLClass graduateCourse = cls(df, "GraduateCourse");
                OWLClass course = cls(df, "Course");
                OWLObjectProperty teacherOf = prop(df, "teacherOf");
                return List.of(
                        df.getOWLSubClassOfAxiom(fullProfessor, professor),
                        df.getOWLSubClassOfAxiom(fullProfessor, df.getOWLObjectSomeValuesFrom(teacherOf, graduateCourse)),
                        df.getOWLSubClassOfAxiom(professor, df.getOWLObjectAllValuesFrom(teacherOf, course))
                );
            }
            case "UEWI2": {
                OWLClass fullProfessor = cls(df, "FullProfessor");
                OWLClass professor = cls(df, "Professor");
                OWLClass graduateCourse = cls(df, "GraduateCourse");
                OWLClass undergraduateCourse = cls(df, "UndergraduateCourse");
                OWLObjectProperty teacherOf = prop(df, "teacherOf");
                return List.of(
                        df.getOWLSubClassOfAxiom(fullProfessor, professor),
                        df.getOWLSubClassOfAxiom(fullProfessor, df.getOWLObjectAllValuesFrom(teacherOf, graduateCourse)),
                        df.getOWLSubClassOfAxiom(professor, df.getOWLObjectSomeValuesFrom(teacherOf, undergraduateCourse))
                );
            }
            case "OILWI": {
                OWLClass fullProfessor = cls(df, "FullProfessor");
                OWLClass professor = cls(df, "Professor");
                OWLClass graduateCourse = cls(df, "GraduateCourse");
                OWLClass undergraduateCourse = cls(df, "UndergraduateCourse");
                OWLObjectProperty teacherOf = prop(df, "teacherOf");
                return List.of(
                        df.getOWLSubClassOfAxiom(fullProfessor, professor),
                        df.getOWLSubClassOfAxiom(fullProfessor, df.getOWLObjectAllValuesFrom(teacherOf, graduateCourse)),
                        df.getOWLSubClassOfAxiom(professor, df.getOWLObjectAllValuesFrom(teacherOf, undergraduateCourse))
                );
            }
            case "OOD": {
                OWLClass domainWitness = cls(df, "SeedOODDomainWitness");
                OWLClass clashWitness = cls(df, "SeedOODClashWitness");
                OWLNamedIndividual subject = ind(df, "seedOODSubject");
                OWLNamedIndividual object = ind(df, "seedOODObject");
                OWLObjectProperty witnessProperty = prop(df, "seedOODProperty");
                return List.of(
                        df.getOWLDisjointClassesAxiom(domainWitness, clashWitness),
                        df.getOWLClassAssertionAxiom(clashWitness, subject),
                        df.getOWLClassAssertionAxiom(clashWitness, object),
                        df.getOWLObjectPropertyAssertionAxiom(witnessProperty, subject, object)
                );
            }
            case "OOR": {
                OWLClass rangeWitness = cls(df, "SeedOORRangeWitness");
                OWLClass clashWitness = cls(df, "SeedOORClashWitness");
                OWLNamedIndividual subject = ind(df, "seedOORSubject");
                OWLNamedIndividual object = ind(df, "seedOORObject");
                OWLObjectProperty witnessProperty = prop(df, "seedOORProperty");
                return List.of(
                        df.getOWLDisjointClassesAxiom(rangeWitness, clashWitness),
                        df.getOWLClassAssertionAxiom(clashWitness, subject),
                        df.getOWLClassAssertionAxiom(clashWitness, object),
                        df.getOWLObjectPropertyAssertionAxiom(witnessProperty, subject, object)
                );
            }
            case "OILWPI": {
                OWLClass subject = cls(df, "SeedOILWPISubject");
                OWLClass left = cls(df, "SeedOILWPILeft");
                OWLClass right = cls(df, "SeedOILWPIRight");
                OWLObjectProperty subProperty = prop(df, "seedOILWPISubProperty");
                OWLObjectProperty superProperty = prop(df, "seedOILWPISuperProperty");
                return List.of(
                        df.getOWLSubObjectPropertyOfAxiom(subProperty, superProperty),
                        df.getOWLSubClassOfAxiom(subject, df.getOWLObjectAllValuesFrom(subProperty, left)),
                        df.getOWLSubClassOfAxiom(subject, df.getOWLObjectAllValuesFrom(superProperty, right))
                );
            }
            case "UEWIP": {
                OWLClass source = cls(df, "SeedUEWIPSource");
                OWLClass middle = cls(df, "SeedUEWIPMiddle");
                OWLClass clash = cls(df, "SeedUEWIPClash");
                OWLObjectProperty forward = prop(df, "seedUEWIPForward");
                OWLObjectProperty inverseTarget = prop(df, "seedUEWIPInverseTarget");
                return List.of(
                        df.getOWLDisjointClassesAxiom(source, clash),
                        df.getOWLSubClassOfAxiom(source, df.getOWLObjectSomeValuesFrom(forward, middle)),
                        df.getOWLSubClassOfAxiom(middle, df.getOWLObjectAllValuesFrom(inverseTarget, clash))
                );
            }
            case "UEWPI": {
                OWLClass subject = cls(df, "SeedUEWPISubject");
                OWLClass left = cls(df, "SeedUEWPILeft");
                OWLClass right = cls(df, "SeedUEWPIRight");
                OWLObjectProperty subProperty = prop(df, "seedUEWPISubProperty");
                OWLObjectProperty superProperty = prop(df, "seedUEWPISuperProperty");
                return List.of(
                        df.getOWLSubObjectPropertyOfAxiom(subProperty, superProperty),
                        df.getOWLSubClassOfAxiom(subject, df.getOWLObjectSomeValuesFrom(subProperty, left)),
                        df.getOWLSubClassOfAxiom(subject, df.getOWLObjectAllValuesFrom(superProperty, right))
                );
            }
            default:
                throw new IllegalArgumentException("Unsupported seed family: " + family);
        }
    }
    private static OWLOntology loadOntology(File file, OWLOntologyManager manager) throws OWLOntologyCreationException {
        return manager.loadOntologyFromOntologyDocument(file);
    }
    private static void saveOntology(OWLOntology ontology, File outputFile) throws OWLOntologyStorageException, IOException {
        OWLOntologyManager manager = ontology.getOWLOntologyManager();
        OWLDocumentFormat format = manager.getOntologyFormat(ontology);
        if (format == null) {
            format = new FunctionalSyntaxDocumentFormat();
        }
        try (FileOutputStream stream = new FileOutputStream(outputFile)) {
            manager.saveOntology(ontology, format, stream);
        }
    }
    private static void writeManifestHeader(BufferedWriter writer) throws IOException {
        writer.write("family,source_file,seeded_file,added_axioms");
        writer.newLine();
    }
    private static void writeManifestRow(BufferedWriter writer,
                                         String family,
                                         String sourceFile,
                                         String seededFile,
                                         int addedAxioms) throws IOException {
        writer.write(String.join(",",
                family,
                sourceFile,
                seededFile,
                Integer.toString(addedAxioms)));
        writer.newLine();
    }
    public static void main(String[] args) throws Exception {
        File inputDir = new File(INPUT_PATH);
        File outputDir = new File(OUTPUT_PATH);
        if (!inputDir.isDirectory()) {
            throw new IllegalArgumentException("Input path is missing or not readable: " + inputDir.getAbsolutePath());
        }
        if (!outputDir.exists() && !outputDir.mkdirs()) {
            throw new IllegalStateException("Could not create output directory: " + outputDir.getAbsolutePath());
        }
        List<File> sourceFiles = Arrays.stream(inputDir.listFiles() == null ? new File[0] : inputDir.listFiles())
                .filter(File::isFile)
                .filter(file -> !file.getName().startsWith("."))
                .filter(file -> !hasKnownPatternPrefix(file.getName()))
                .sorted((a, b) -> a.getName().compareToIgnoreCase(b.getName()))
                .collect(Collectors.toCollection(ArrayList::new));
        if (MAX_FILES > 0 && sourceFiles.size() > MAX_FILES) {
            sourceFiles = new ArrayList<>(sourceFiles.subList(0, MAX_FILES));
        }
        BufferedWriter manifestWriter = null;
        try {
            if (!SEED_MANIFEST_PATH.isBlank()) {
                Path manifestPath = Path.of(SEED_MANIFEST_PATH);
                if (manifestPath.getParent() != null) {
                    Files.createDirectories(manifestPath.getParent());
                }
                manifestWriter = Files.newBufferedWriter(manifestPath, StandardCharsets.UTF_8);
                writeManifestHeader(manifestWriter);
            }
            System.out.println("Seeding families: " + SEED_FAMILIES);
            System.out.println("Source modules selected: " + sourceFiles.size());
            for (File sourceFile : sourceFiles) {
                for (String family : SEED_FAMILIES) {
                    OWLOntologyManager manager = OWLManager.createOWLOntologyManager();
                    OWLOntology ontology = loadOntology(sourceFile, manager);
                    List<OWLAxiom> seedAxioms = buildSeedAxioms(manager.getOWLDataFactory(), family);
                    int added = 0;
                    for (OWLAxiom axiom : seedAxioms) {
                        if (!ontology.containsAxiom(axiom)) {
                            manager.addAxiom(ontology, axiom);
                            added++;
                        }
                    }
                    String seededName = stripExtension(sourceFile.getName()) + "__seed-" + family + ".owl";
                    File seededFile = new File(outputDir, seededName);
                    saveOntology(ontology, seededFile);
                    System.out.println("Seeded " + family + " -> " + seededFile.getName() + " (added=" + added + ")");
                    if (manifestWriter != null) {
                        writeManifestRow(manifestWriter, family, sourceFile.getName(), seededFile.getName(), added);
                    }
                }
            }
        } finally {
            if (manifestWriter != null) {
                manifestWriter.close();
            }
        }
    }
}
