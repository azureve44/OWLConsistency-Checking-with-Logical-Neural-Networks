import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.model.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;


public class Main {
    public static void main(String[] args) throws OWLOntologyCreationException, IOException {
        Logger logger = LoggerFactory.getLogger("org.semanticweb.owlapi");
        ((ch.qos.logback.classic.Logger) logger).setLevel(ch.qos.logback.classic.Level.ERROR);

        File[] dir = new File("../data/ontologies/").listFiles();
        BufferedWriter class_writer = new BufferedWriter(new FileWriter("C:\\Users\\Doo5i\\git\\GLaMoR\\Analysis\\src\\main\\output\\classes"));
        BufferedWriter property_writer = new BufferedWriter(new FileWriter("C:\\Users\\Doo5i\\git\\GLaMoR\\Analysis\\src\\main\\output\\properties"));

        for (File file : dir) {
            if (file.getName().equals(".gitkeep")) continue;
                try {
                    // Create a new manager for each file
                    OWLOntologyManager localManager = OWLManager.createOWLOntologyManager();
                    OWLOntology ontology = localManager.loadOntologyFromOntologyDocument(file);

                    // Change the IRI of the loaded ontology
                    IRI newIRI = IRI.create("http://example.org/ontologies/" + file.getName());
                    OWLOntology newOntology = localManager.createOntology(newIRI);

                    // Copy axioms from the original ontology to the new one
                    localManager.addAxioms(newOntology, ontology.getAxioms());

                    // Count classes and properties in the new ontology
                    int num_classes = (int) newOntology.getAxioms(AxiomType.DECLARATION).stream()
                            .filter(x -> x.toString().contains("Declaration(Class(")).count();
                    int num_properties = (int) newOntology.getAxioms(AxiomType.DECLARATION).stream()
                            .filter(x -> x.toString().contains("Declaration(ObjectProperty")).count();

                    // Print counts to console for debugging
                    System.out.println("File: " + file.getName() + ", New IRI: " + newIRI + ", Classes: " + num_classes + ", Properties: " + num_properties);
                    class_writer.append(String.valueOf(num_classes)).append(",\n");
                    property_writer.append(String.valueOf(num_properties)).append(",\n");
                }
                catch(Exception e){
                    logger.debug("Couldnt Load ontology");
                }
        }


        class_writer.close();
        property_writer.close();
    }
        //System.out.println(ontologies.get(0).equals(ontologies.get(1)));

/*
        classes.add((int) ontology.getAxioms(AxiomType.DECLARATION).stream()
                .filter(x -> x.toString().contains("Declaration(Class(")).count());
        properties.add((int) ontology.getAxioms(AxiomType.DECLARATION).stream()
                .filter(x -> x.toString().contains("Declaration(ObjectProperty")).count());




 */

}
