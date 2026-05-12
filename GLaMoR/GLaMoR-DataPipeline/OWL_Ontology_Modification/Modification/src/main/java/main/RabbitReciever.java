package main;
import com.rabbitmq.client.Channel;
import com.rabbitmq.client.Connection;
import com.rabbitmq.client.ConnectionFactory;
import com.rabbitmq.client.DeliverCallback;
import database.PostgresDB;
import java.nio.charset.StandardCharsets;
import java.util.List;
public class RabbitReciever {
    private static final String INPUT_QUEUE = System.getenv().getOrDefault("RABBITMQ_QUEUE_INPUT", "Modules_Modify");
    private static final String OUTPUT_QUEUE = System.getenv().getOrDefault("RABBITMQ_QUEUE_OUTPUT", "Modules_Preprocess");
    private static final String RABBITMQ_HOST = System.getenv().getOrDefault("RABBITMQ_HOST", "rabbitmq");
    private static final String RABBITMQ_USER = System.getenv().getOrDefault("RABBITMQ_USER", "rabbitmq_user");
    private static final String RABBITMQ_PASS = System.getenv().getOrDefault("RABBITMQ_PASS", "rabbitmq_password");
    private static final String POSTGRES_HOST = System.getenv().getOrDefault("POSTGRES_HOST", "postgres");
    private static final String POSTGRES_USER = System.getenv().getOrDefault("POSTGRES_USER", "postgres_user");
    private static final String POSTGRES_PASSWORD = System.getenv().getOrDefault("POSTGRES_PASSWORD", "postgress_password");
    private static final String POSTGRES_DB = System.getenv().getOrDefault("POSTGRES_DB", "data_processing");
    private static final int POSTGRES_PORT = Integer.parseInt(System.getenv().getOrDefault("POSTGRES_PORT", "5432"));
    public static void main(String[] args) throws Exception {
        ConnectionFactory factory = new ConnectionFactory();
        factory.setHost(RABBITMQ_HOST);
        factory.setUsername(RABBITMQ_USER);
        factory.setPassword(RABBITMQ_PASS);
        PostgresDB postgresDB;
        try {
            postgresDB = new PostgresDB(POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_PORT);
        } catch (Exception e) {
            System.err.println("Failed to initialize PostgresDB: " + e.getMessage());
            e.printStackTrace();
            throw e;
        }
        try (Connection connection = factory.newConnection()) {
            Channel channel = connection.createChannel();
            channel.queueDeclare(INPUT_QUEUE, true, false, false, null);
            channel.queueDeclare(OUTPUT_QUEUE, true, false, false, null);
            DeliverCallback deliverCallback = (consumerTag, delivery) -> {
                String filepath = new String(delivery.getBody(), StandardCharsets.UTF_8);
                try {
                    postgresDB.insertStatusInModificationDatabaseWaiting(filepath);
                    postgresDB.updateStatusInModificationDatabaseStart(filepath);
                    List<String> newFileNames = Main.executeInjection(filepath);
                    if (newFileNames != null && !newFileNames.isEmpty()) {
                        for (String newFileName : newFileNames) {
                            channel.basicPublish("", OUTPUT_QUEUE, null, newFileName.getBytes(StandardCharsets.UTF_8));
                            postgresDB.updasteStatusInPreprocessingDatabase(newFileName);
                        }
                        postgresDB.updateStatusInModificationDatabaseEnd(filepath, newFileNames);
                    } else {
                        postgresDB.updateStatusInModificationDatabaseEndError(filepath);
                    }
                    System.out.println("Processed file: " + filepath + " -> " + newFileNames);
                } catch (Exception e) {
                    System.err.println("Error processing file " + filepath + ": " + e.getMessage());
                    e.printStackTrace();
                    postgresDB.updateStatusInModificationDatabaseEndError(filepath);
                }
                channel.basicAck(delivery.getEnvelope().getDeliveryTag(), false);
            };
            channel.basicConsume(INPUT_QUEUE, false, deliverCallback, consumerTag -> {});
            while (true) {
                Thread.sleep(1000);
            }
        } catch (Exception e) {
            e.printStackTrace();
            throw e;
        }
    }
}
