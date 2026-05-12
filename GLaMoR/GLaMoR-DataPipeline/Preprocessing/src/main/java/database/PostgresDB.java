package database;
import java.sql.*;
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
    public void updateStatusInPreprocessDatabaseStart(String fileName) {
        String updateQuery = "INSERT INTO preprocessing (file_name, status, consistent) VALUES (?, ?, ?) " +
                "ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, error_message = NULL, timestamp = CURRENT_TIMESTAMP";
        try (java.sql.Connection dbConnection = DriverManager.getConnection(this.URL, this.POSTGRES_USER, this.POSTGRES_PASSWORD);
             PreparedStatement statement = dbConnection.prepareStatement(updateQuery)) {
            statement.setString(1, fileName);
            statement.setString(2, "Processing");
            statement.setString(3, "True");
            statement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
            System.err.println("Error logging to the database");
        }
    }
    public void updateStatusInPreprocessDatabaseEnd(String fileName) {
        System.out.println("Setting file " + fileName + " as Done");
        String updateQuery = "INSERT INTO preprocessing (file_name, status, consistent) VALUES (?, ?, ?) " +
                "ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, error_message = NULL, timestamp = CURRENT_TIMESTAMP";
        try (java.sql.Connection dbConnection = DriverManager.getConnection(this.URL, this.POSTGRES_USER, this.POSTGRES_PASSWORD);
             PreparedStatement statement = dbConnection.prepareStatement(updateQuery)) {
            statement.setString(1, fileName);
            statement.setString(2, "Done");
            statement.setString(3, "True");
            statement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
            System.err.println("Error logging to the database");
        }
    }
    public void insertInPrefixRemovalDatabase(String fileName) {
        String insertQuery = "INSERT INTO prefix_removal (file_name, status) VALUES (?, ?) " +
                "ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, error_message = NULL, timestamp = CURRENT_TIMESTAMP";
        try (java.sql.Connection dbConnection = DriverManager.getConnection(this.URL, this.POSTGRES_USER, this.POSTGRES_PASSWORD);
             PreparedStatement statement = dbConnection.prepareStatement(insertQuery)) {
            statement.setString(1, fileName);
            statement.setString(2, "Waiting");
            statement.executeUpdate();
        } catch (SQLException e) {
            e.printStackTrace();
            System.err.println("Error logging to the database");
        }
    }
    public boolean queryConsistencyOfFileName(String fileName) {
        String query = "SELECT consistent FROM preprocessing WHERE file_name = ?";
        boolean isConsistent = false;
        try (java.sql.Connection connection = DriverManager.getConnection(this.URL, this.POSTGRES_USER, this.POSTGRES_PASSWORD);
             PreparedStatement preparedStatement = connection.prepareStatement(query)) {
            preparedStatement.setString(1, fileName);
            try (ResultSet resultSet = preparedStatement.executeQuery()) {
                if (resultSet.next()) {
                    isConsistent = resultSet.getBoolean("consistent");
                }
            }
        } catch (SQLException e) {
            e.printStackTrace();
        }
        return isConsistent;
    }
}
