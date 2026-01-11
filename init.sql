-- Switch to the data_processing database (if needed, depends on your environment)
\c data_processing;

-- Create processing_status table
CREATE TABLE IF NOT EXISTS modularization (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    cluster VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT
);

-- Create collection_status table
CREATE TABLE IF NOT EXISTS modification (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    injected_axiom VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT
);

-- Create collection_status table
CREATE TABLE IF NOT EXISTS preprocessing (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    consistent VARCHAR(50),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT
);

-- Create collection_status table
CREATE TABLE IF NOT EXISTS translation (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT
);


CREATE TABLE IF NOT EXISTS prefix_removal(
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS data_filter(
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    tokens VARCHAR(50), 
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT
);