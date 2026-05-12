package main;

import com.rabbitmq.client.Channel;
import com.rabbitmq.client.Connection;
import com.rabbitmq.client.ConnectionFactory;
import com.rabbitmq.client.DeliverCallback;
import fusion.oapt.algorithm.partitioner.SeeCOnt.Findk.FindOptimalCluster;

import fusion.oapt.general.cc.Controller;
import fusion.oapt.general.cc.Coordinator;
import org.apache.jena.ontology.OntModel;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedList;
import java.util.List;
import java.util.concurrent.*;
import java.util.stream.Collectors;
import java.util.stream.Stream;


public class Main {

    private static final String RABBITMQ_HOST = System.getenv("RABBITMQ_HOST");
    private static  String QUEUE_INPUT = System.getenv("RABBITMQ_QUEUE_INPUT");
    private static  String QUEUE_OUTPUT= System.getenv("RABBITMQ_QUEUE_OUTPUT");

    private static  String POSTGRES_HOST = System.getenv("POSTGRES_HOST");
    private static  String POSTGRES_USER = System.getenv("POSTGRES_USER");
    private static  String POSTGRES_PASSWORD = System.getenv("POSTGRES_PASSWORD");
    private static  String POSTGRES_DB = System.getenv("POSTGRES_DB");

    public static void main(String[] args) throws IOException, TimeoutException, InterruptedException {

        if (QUEUE_INPUT == null || QUEUE_INPUT.isBlank()) QUEUE_INPUT = "Ontologies";
        if (QUEUE_OUTPUT == null || QUEUE_OUTPUT.isBlank()) QUEUE_OUTPUT = "Modules_Preprocess";
        if (POSTGRES_HOST == null || POSTGRES_HOST.isBlank()) POSTGRES_HOST = "postgres";
        if (POSTGRES_USER == null || POSTGRES_USER.isBlank()) POSTGRES_USER = "postgres_user";
        if (POSTGRES_PASSWORD == null || POSTGRES_PASSWORD.isBlank()) POSTGRES_PASSWORD = "postgress_password";
        if (POSTGRES_DB == null || POSTGRES_DB.isBlank()) POSTGRES_DB = "data_processing";

        String rabbitHost = (RABBITMQ_HOST == null || RABBITMQ_HOST.isBlank()) ? "rabbitmq" : RABBITMQ_HOST;
        ConnectionFactory factory = new ConnectionFactory();
        factory.setHost(rabbitHost);
        factory.setUsername("rabbitmq_user");
        factory.setPassword("rabbitmq_password");
        Connection connection = null;
        Channel channel = null;

        while (connection == null || channel == null) {
            try {
                // Attempt to establish a connection and channel
                System.out.println("[OAPT] RabbitMQ host=" + rabbitHost + " inputQueue=" + QUEUE_INPUT + " outputQueue=" + QUEUE_OUTPUT);
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
            String filepath = new String(delivery.getBody(), StandardCharsets.UTF_8);
            try {
                insertStatusInModularizationDatabaseWaiting(filepath);
                updateStatusInModularizationDatabaseStart(filepath);
                List<String> modulePaths = modularize(filepath);
                if (!modulePaths.isEmpty()) {
                    updateStatusInModularizationDatabaseEnd(filepath, modulePaths.size());
                    for (String modulePath : modulePaths) {
                        System.out.println("[OAPT] Publishing module to " + QUEUE_OUTPUT + ": " + modulePath);
                        finalChannel.basicPublish("", QUEUE_OUTPUT, null, modulePath.getBytes(StandardCharsets.UTF_8));
                        updateStatusInPreprocessingDatabase(modulePath);
                    }
                } else {
                    updateStatusInModularizationDatabaseEndError(filepath, "No modules generated");
                }
                System.out.println("Received file: " + filepath);
            } catch (Exception e) {
                updateStatusInModularizationDatabaseEndError(filepath, e.getMessage());
                throw e;
            } finally {
                finalChannel.basicAck(delivery.getEnvelope().getDeliveryTag(), false);
            }
        };

        channel.basicConsume(QUEUE_INPUT, false, deliverCallback, consumerTag -> { });
        System.out.println("Waiting for messages. To exit press CTRL+C");

        while (true) {
            Thread.sleep(1000);
        }
    }

    private static List<String> modularize(String filepath) throws IOException {
        File dir = new File("/input");
        String[] files = dir.list();
        if (files != null) {
            for (String file : files) {
                System.out.println("File in directory: " + file);
            }
        }

        List<String> completedOntologies = findCompletedOntologies("/input");
        System.out.println(completedOntologies);
        if(completedOntologies.contains(filepath)){
            return findCompletedModulesOfOntologie(filepath);
        }
        return processFile(new File("/input/" + filepath));
    }

    private static List<String> findCompletedModulesOfOntologie(String filepath) throws IOException {
        String name = filepath.split("\\.")[0];
        try(Stream<Path> fif = Files.walk(Paths.get("/output"))){
            return fif.filter(Files::isRegularFile)
                    .map(Path::toFile)
                    .map(File::getName)
                    .filter(fileName -> fileName.contains(name))
                    .collect(Collectors.toList());
        }
    }

    private static List<String> findCompletedOntologies(String path) {
        List<String> filesInFolder = null;
        try (Stream<Path> fif = Files.walk(Paths.get(path))){
            filesInFolder = fif
                    .filter(Files::isRegularFile)
                    .map(Path::toFile)
                    .map(File::getName)
                    .map(name -> name.split("_Module")[0]+".owl")
                    .distinct()
                    .collect(Collectors.toList());
        } catch (IOException e) {
            e.printStackTrace();
            return new LinkedList<String>();
        }
        return filesInFolder;
    }
    private static List<String> processFile(File f) throws IOException {
        List<String> moduleFileNames = new ArrayList<>();
        String path = f.getPath();
        System.out.println(path);
        Controller con = new Controller(path);
        FindOptimalCluster OP = new FindOptimalCluster(con.MB);
        int NumCH = OP.FindOptimalClusterFunc();
        Coordinator.KNumCH = NumCH;
        List<OntModel> modules = con.InitialRun_API("SeeCOnt", Coordinator.KNumCH);
        String basename = f.getName().split("\\.")[0];
        for(int i = 0; i<modules.size(); i++){
            moduleFileNames.add(basename + "_Module_" + i + ".owl");
        }
        return moduleFileNames;
    }

    private static void logError(File file, Exception e) {
        try (BufferedWriter bwe = new BufferedWriter(new FileWriter("src/resources/merge/error.csv", true))) {
            bwe.write(file.getName() + ":\t" + e.toString());
            bwe.flush();
        } catch (IOException ex) {
            ex.printStackTrace();
        }
    }
    private static void updateStatusInPreprocessingDatabase(String moduleName) {
        String url = "jdbc:postgresql://" + POSTGRES_HOST + ":5432/" + POSTGRES_DB;
        String insertQuery = "INSERT INTO preprocessing (file_name, status, consistent) VALUES (?, ?, ?) " +
                "ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, consistent = EXCLUDED.consistent, error_message = NULL, timestamp = CURRENT_TIMESTAMP";
        try (java.sql.Connection dbConnection = DriverManager.getConnection(url, POSTGRES_USER, POSTGRES_PASSWORD);
             PreparedStatement statement = dbConnection.prepareStatement(insertQuery)) {
            statement.setString(1, moduleName);
            statement.setString(2, "Waiting");
            statement.setString(3, "True");
            statement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
            System.err.println("Error logging to the database");
        }
    }

    private static void updateStatusInModificationDatabase(String moduleName) {
        String url = "jdbc:postgresql://" + POSTGRES_HOST + ":5432/" + POSTGRES_DB;
        String insertQuery = "INSERT INTO modification (file_name, status, injected_axiom) VALUES (?, ?, ?)";

        sendQuery(moduleName, url, insertQuery);
    }

    private static void sendQuery(String moduleName, String url, String insertQuery) {
        try (java.sql.Connection dbConnection = DriverManager.getConnection(url, POSTGRES_USER, POSTGRES_PASSWORD);
             PreparedStatement statement = dbConnection.prepareStatement(insertQuery)) {
            statement.setString(1, moduleName);
            statement.setString(2, "Waiting");
            statement.setString(3, "TBD");
            statement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
            System.err.println("Error logging to the database");
        }
    }

    private static void updateStatusInModularizationDatabaseEnd(String ontName, int cluster) {
        String url = "jdbc:postgresql://" + POSTGRES_HOST + ":5432/" + POSTGRES_DB;
        String updateQuery = "INSERT INTO modularization (file_name, status, cluster, error_message) VALUES (?, ?, ?, NULL) " +
                "ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, cluster = EXCLUDED.cluster, error_message = NULL, timestamp = CURRENT_TIMESTAMP";

        try (java.sql.Connection dbConnection = DriverManager.getConnection(url, POSTGRES_USER, POSTGRES_PASSWORD);
             PreparedStatement statement = dbConnection.prepareStatement(updateQuery)) {
            statement.setString(1, ontName);
            statement.setString(2, "Done");
            statement.setString(3, String.valueOf(cluster));

            statement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
            System.err.println("Error logging to the database");
        }
    }

    private static void updateStatusInModularizationDatabaseStart(String ontName) {
        String url = "jdbc:postgresql://" + POSTGRES_HOST + ":5432/" + POSTGRES_DB;
        String updateQuery = "INSERT INTO modularization (file_name, status, cluster, error_message) VALUES (?, ?, ?, NULL) " +
                "ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, cluster = EXCLUDED.cluster, error_message = NULL, timestamp = CURRENT_TIMESTAMP";

        try (java.sql.Connection dbConnection = DriverManager.getConnection(url, POSTGRES_USER, POSTGRES_PASSWORD);
             PreparedStatement statement = dbConnection.prepareStatement(updateQuery)) {
            statement.setString(1, ontName);
            statement.setString(2, "Processing");
            statement.setString(3, "TBD");
            statement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
            System.err.println("Error logging to the database");
        }
    }

    private static void insertStatusInModularizationDatabaseWaiting(String ontName) {
        String url = "jdbc:postgresql://" + POSTGRES_HOST + ":5432/" + POSTGRES_DB;
        String insertQuery = "INSERT INTO modularization (file_name, status, cluster, error_message) VALUES (?, ?, ?, NULL) " +
                "ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, cluster = EXCLUDED.cluster, error_message = NULL, timestamp = CURRENT_TIMESTAMP";

        try (java.sql.Connection dbConnection = DriverManager.getConnection(url, POSTGRES_USER, POSTGRES_PASSWORD);
             PreparedStatement statement = dbConnection.prepareStatement(insertQuery)) {
            statement.setString(1, ontName);
            statement.setString(2, "Waiting");
            statement.setString(3, "TBD");
            statement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
            System.err.println("Error logging to the database");
        }
    }

    private static void updateStatusInModularizationDatabaseEndError(String ontName, String errorMessage) {
        String url = "jdbc:postgresql://" + POSTGRES_HOST + ":5432/" + POSTGRES_DB;
        String safeMessage = (errorMessage == null || errorMessage.isBlank()) ? "Unknown modularization error" : errorMessage;
        String updateQuery = "INSERT INTO modularization (file_name, status, cluster, error_message) VALUES (?, ?, ?, ?) " +
                "ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, cluster = EXCLUDED.cluster, error_message = EXCLUDED.error_message, timestamp = CURRENT_TIMESTAMP";

        try (java.sql.Connection dbConnection = DriverManager.getConnection(url, POSTGRES_USER, POSTGRES_PASSWORD);
             PreparedStatement statement = dbConnection.prepareStatement(updateQuery)) {
            statement.setString(1, ontName);
            statement.setString(2, "Failed");
            statement.setString(3, "TBD");
            statement.setString(4, safeMessage);
            statement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
            System.err.println("Error logging to the database");
        }
    }
}
