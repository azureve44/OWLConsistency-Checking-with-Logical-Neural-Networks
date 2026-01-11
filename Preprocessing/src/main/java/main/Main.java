package main;

import com.rabbitmq.client.Channel;
import com.rabbitmq.client.Connection;
import com.rabbitmq.client.ConnectionFactory;
import com.rabbitmq.client.DeliverCallback;
import database.PostgresDB;
import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.model.*;
import org.semanticweb.owlapi.formats.*;
import org.semanticweb.owlapi.util.DefaultPrefixManager;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.sql.SQLException;
import java.util.HashSet;
import java.util.Optional;
import java.util.Set;

public class Main {



    private static void removeAnnotationAxioms(OWLOntology ontology, OWLOntologyManager manager) {
        ontology.axioms().filter(OWLAxiom::isAnnotationAxiom).forEach(axiom -> manager.removeAxiom(ontology, axiom));
    }

    /**
     *
     * @param ontology
     * @param manager
     * @return
     */
    private static void removeSKOSAxioms(OWLOntology ontology, OWLOntologyManager manager) {
        IRI skosIRI = IRI.create("http://www.w3.org/2004/02/skos/core#");
        ontology.axioms()
                .filter(axiom -> axiom.signature()
                        .anyMatch(entity -> entity.getIRI().getNamespace().equals(skosIRI.toString())))
                .forEach(axiom -> manager.removeAxiom(ontology, axiom));
    }

    private static Optional<Set<String>> findBaseIRI(OWLOntology ontology, OWLOntologyManager manager){
        Set<OWLEntity> entities = ontology.getSignature();
        Set<String> baseIRIs = new HashSet<>();

        for (OWLEntity entity : entities) {
            IRI iri = entity.getIRI();
            String iriString = iri.toString();
            // Remove the local fragment (after last '/' or '#') to find base IRI
            int lastSlash = iriString.lastIndexOf('/');
            int lastHash = iriString.lastIndexOf('#');
            int splitIndex = Math.max(lastSlash, lastHash);

            if (splitIndex > -1) {
                String currentBase = iriString.substring(0, splitIndex + 1);
                baseIRIs.add(currentBase);
            }
        }
        return Optional.of(baseIRIs);
    }

    private static String preprocess(File file) {
        OWLOntologyManager manager = OWLManager.createOWLOntologyManager();
        OWLOntology ontology = null;
        try {
            System.out.println(file);
            ontology = manager.loadOntologyFromOntologyDocument(file);
        } catch (Exception e) {
            System.out.println("Couldn't load ontology " + file.getPath());
        }
        if (ontology == null) return "";
        // Remove Annotation Axioms

        removeAnnotationAxioms(ontology, manager);

        removeSKOSAxioms(ontology, manager);

        System.out.println("Saving: " + file.getName());
        ManchesterSyntaxDocumentFormat manchesterSyntaxDocumentFormat = new ManchesterSyntaxDocumentFormat();
        Optional<Set<String>> prefixes = findBaseIRI(ontology, manager);
        if(prefixes.isPresent()){
            System.out.println(prefixes);
            DefaultPrefixManager pm = new DefaultPrefixManager();
            for(String prefix : prefixes.get()){
                String nameTag = prefix.replaceFirst("^(http://|https://)", "")
                        .replace("www\\.", "")
                        .replaceFirst("^(\\.org|\\.de|\\.edu)", "");

                pm.setPrefix(nameTag, prefix);
            }
            manchesterSyntaxDocumentFormat.copyPrefixesFrom(pm);
        }
        File outputDir = new File("/output/");

        try {
            manager.saveOntology(ontology, manchesterSyntaxDocumentFormat, IRI.create(new File(outputDir, file.getName()).toURI()));
            System.out.println("Successfully saved Ontology: " + file.getName());
        } catch (OWLOntologyStorageException e) {
            System.err.println("Failed to save ontology: " + file.getName() + " due to " + e.getMessage());
        }
        System.out.println("Saved File to Disk: " + file.getName());
        return file.getName();
    }



    public static void main(String[] args) throws OWLOntologyStorageException, SQLException, IOException, InterruptedException {
        File inputDir1 = new File("/input/");

        String QUEUE_INPUT = "Modules_Preprocess";
        String QUEUE_OUTPUT = "Prefix_Removal";

        PostgresDB database = new PostgresDB("postgres", "data_processing", "postgres_user", "postgress_password", 5432);

        ConnectionFactory factory = new ConnectionFactory();
        factory.setHost("rabbitmq");
        factory.setUsername("rabbitmq_user");
        factory.setPassword("rabbitmq_password");
        Connection connection = null;
        Channel channel = null;

        while (connection == null || channel == null) {
            try {
                // Attempt to establish a connection and channel
                connection = factory.newConnection();
                channel = connection.createChannel();

                System.out.println("Connected to RabbitMQ successfully.");
            } catch (Exception e) {
                System.out.println("Error connecting to RabbitMQ: " + e.getMessage());
                System.out.println("Retrying in 5 seconds...");

                // Sleep for 5 seconds before retrying
                try {
                    Thread.sleep(5000);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                }
            }
        }

        channel.queueDeclare(QUEUE_INPUT, true, false, false, null);
        channel.queueDeclare(QUEUE_OUTPUT, true, false, false, null);

        Channel finalChannel = channel;
        DeliverCallback deliverCallback = (consumerTag, delivery) -> {
            //Add Database calls
            String fileName = new String(delivery.getBody(), StandardCharsets.UTF_8);
            System.out.println("Processing Message: " + fileName);
            database.updateStatusInPreprocessDatabaseStart(fileName);
            String newFile = preprocess(new File(inputDir1 +"/"+ fileName));
            finalChannel.basicPublish("", QUEUE_OUTPUT, null, newFile.getBytes(StandardCharsets.UTF_8));
            database.updateStatusInPreprocessDatabaseEnd(newFile);
            database.insertInPrefixRemovalDatabase(fileName);
            System.out.println("Received file: " + fileName);
            // Acknowledge the message
            finalChannel.basicAck(delivery.getEnvelope().getDeliveryTag(), false);
        };

        channel.basicConsume(QUEUE_INPUT, false, deliverCallback, consumerTag -> { });
        System.out.println("Waiting for messages. To exit press CTRL+C");

        while (true) {
            Thread.sleep(1000);
        }



    }
}
