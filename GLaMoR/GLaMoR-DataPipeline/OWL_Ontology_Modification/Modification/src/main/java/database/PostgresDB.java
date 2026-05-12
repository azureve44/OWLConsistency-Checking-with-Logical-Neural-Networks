package database;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.util.List;
public class PostgresDB {
    private final String POSTGRES_HOST;
    private final String POSTGRES_DB;
    private final String POSTGRES_USER;
    private final String POSTGRES_PASSWORD;
    private final int PORT;
    private final String URL;
    public PostgresDB(String host, String db, String user, String password, int port) throws SQLException {
        this.POSTGRES_HOST = host;
        this.POSTGRES_DB = db;
        this.POSTGRES_USER = user;
        this.POSTGRES_PASSWORD = password;
        this.PORT = port;
        this.URL = "jdbc:postgresql://" + this.POSTGRES_HOST + ":" + this.PORT + "/" + this.POSTGRES_DB;
    }
    public void insertStatusInModificationDatabaseWaiting(String fileName) {
        String insertQuery = "INSERT INTO modification (file_name, status, injected_axiom) VALUES (?, ?, ?) " +
                "ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, injected_axiom = EXCLUDED.injected_axiom, error_message = NULL, timestamp = CURRENT_TIMESTAMP";
        try (java.sql.Connection dbConnection = DriverManager.getConnection(this.URL, this.POSTGRES_USER, this.POSTGRES_PASSWORD);
             PreparedStatement statement = dbConnection.prepareStatement(insertQuery)) {
            statement.setString(1, fileName);
            statement.setString(2, "Waiting");
            statement.setString(3, "TBD");
            statement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
            System.err.println("Error logging to the database (insert waiting modification)");
        }
    }
    public void updateStatusInModificationDatabaseStart(String fileName) {
        String updateQuery = "INSERT INTO modification (file_name, status, injected_axiom) VALUES (?, ?, ?) " +
                "ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, injected_axiom = EXCLUDED.injected_axiom, error_message = NULL, timestamp = CURRENT_TIMESTAMP";
        try (java.sql.Connection dbConnection = DriverManager.getConnection(this.URL, this.POSTGRES_USER, this.POSTGRES_PASSWORD);
             PreparedStatement statement = dbConnection.prepareStatement(updateQuery)) {
            statement.setString(1, fileName);
            statement.setString(2, "Processing");
            statement.setString(3, "TBD");
            statement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
            System.err.println("Error logging to the database (start modification)");
        }
    }
    public void updateStatusInModificationDatabaseEnd(String fileName, List<String> injectedAxioms) {
        String updateQuery = "INSERT INTO modification (file_name, status, injected_axiom, error_message) VALUES (?, ?, ?, NULL) " +
                "ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, injected_axiom = EXCLUDED.injected_axiom, error_message = NULL, timestamp = CURRENT_TIMESTAMP";
        try (java.sql.Connection dbConnection = DriverManager.getConnection(this.URL, this.POSTGRES_USER, this.POSTGRES_PASSWORD);
             PreparedStatement statement = dbConnection.prepareStatement(updateQuery)) {
            statement.setString(1, fileName);
            statement.setString(2, "Done");
            statement.setString(3, injectedAxioms.toString());
            statement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
            System.err.println("Error logging to the database (end modification)");
        }
    }
    public void updasteStatusInPreprocessingDatabase(String fileName) {
        String insertQuery = "INSERT INTO preprocessing (file_name, status, consistent) VALUES (?, ?, ?) " +
                "ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, consistent = EXCLUDED.consistent, error_message = NULL, timestamp = CURRENT_TIMESTAMP";
        try (java.sql.Connection dbConnection = DriverManager.getConnection(this.URL, this.POSTGRES_USER, this.POSTGRES_PASSWORD);
             PreparedStatement statement = dbConnection.prepareStatement(insertQuery)) {
            statement.setString(1, fileName);
            statement.setString(2, "Waiting");
            statement.setString(3, "False");
            statement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
            System.err.println("Error logging to the database (insert preprocessing)");
        }
    }
    public void updateStatusInModificationDatabaseEndError(String fileName) {
        String updateQuery = "INSERT INTO modification (file_name, status, injected_axiom, error_message) VALUES (?, ?, ?, ?) " +
                "ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, injected_axiom = EXCLUDED.injected_axiom, error_message = EXCLUDED.error_message, timestamp = CURRENT_TIMESTAMP";
        try (java.sql.Connection dbConnection = DriverManager.getConnection(this.URL, this.POSTGRES_USER, this.POSTGRES_PASSWORD);
             PreparedStatement statement = dbConnection.prepareStatement(updateQuery)) {
            statement.setString(1, fileName);
            statement.setString(2, "Failed");
            statement.setString(3, "TBD");
            statement.setString(4, "No injectable Axiom found");
            statement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
            System.err.println("Error logging to the database (error modification)");
        }
    }
}
