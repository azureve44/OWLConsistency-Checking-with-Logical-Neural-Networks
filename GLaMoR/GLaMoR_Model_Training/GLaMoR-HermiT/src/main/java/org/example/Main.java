package org.example;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;
import org.semanticweb.HermiT.Reasoner;
import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.model.OWLOntology;
import org.semanticweb.owlapi.model.OWLOntologyCreationException;
import org.semanticweb.owlapi.model.OWLOntologyManager;
import org.semanticweb.owlapi.reasoner.OWLReasoner;
import org.semanticweb.owlapi.reasoner.OWLReasonerFactory;

import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.io.Reader;
import java.util.LinkedList;
import java.util.List;

public class Main {

    private static void check_consistency(String fileName, OWLReasonerFactory reasonerFactory, OWLOntologyManager manager) throws OWLOntologyCreationException {
        List<String> inconsistent_prefixes = List.of("AIO", "EID", "OIL", "OILWI", "OILWPI", "UE", "UEWI1", "UEWI2", "UEWPI", "UEWIP", "SOSINETO", "OOD", "OOR", "CSC");
        String root_path = "../data/";
        String dir = inconsistent_prefixes.contains(fileName.split("_")[0]) ? "ont_modules_inconsistent" : "ont_modules";

        File owlFile = new File(root_path + dir + fileName);

        OWLOntology ontology = manager.loadOntologyFromOntologyDocument(owlFile);

        // Create a reasoner
        OWLReasoner reasoner = reasonerFactory.createReasoner(ontology);

        // Check consistency
        boolean isConsistent = reasoner.isConsistent();
        // Optional: Release the reasoner
        reasoner.dispose();
    }

    public static void main(String[] args) {
        long startTime = System.currentTimeMillis();
        String filePath = "../data/test_data.csv"; // Path to your CSV file
        List<String> file_names = new LinkedList<>();
        try (Reader reader = new FileReader(filePath);
             CSVParser csvParser = new CSVParser(reader, CSVFormat.DEFAULT.withFirstRecordAsHeader())) {

            for (CSVRecord record : csvParser) {
                file_names.add(record.get(0).split("\\.")[0] + ".owl");
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
        OWLOntologyManager manager = OWLManager.createOWLOntologyManager();

        // HermiT reasoner
        OWLReasonerFactory reasonerFactory = new Reasoner.ReasonerFactory();
        int errors = 0;
        for (String fileName : file_names) {
            try{
                check_consistency(fileName, reasonerFactory, manager);
            }
            catch (OWLOntologyCreationException e) {
                errors +=1;
            }
        }
        long elapsedTime = System.currentTimeMillis() - startTime;
        long hours = (elapsedTime / 1000) / 3600;
        long minutes = (elapsedTime / 1000) % 3600 / 60;

        System.out.println(hours + " hours " + minutes + " minutes. Errors:" + errors);
    }
}