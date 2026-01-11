import yaml
import json
from typing import List
from pathlib import Path
import os
import pika
import os
import time
import psycopg2
import traceback

rabbitmq_host ="rabbitmq"
queue_input = "Prefix_Removal"
queue_output = "translation"

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "data_processing")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgress_password")

print("Connecting to database....")
cursor = None
while cursor is None:
    try:
        # Connect to PostgreSQL
        db_connection = psycopg2.connect(
            host=POSTGRES_HOST,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
        cursor = db_connection.cursor()
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        print("Retrying in 5 seconds...")
        time.sleep(5)

# Ensure the necessary table exists in PostgreSQL
cursor.execute("""
    CREATE TABLE IF NOT EXISTS prefix_removal (
        id SERIAL PRIMARY KEY,
        file_name VARCHAR(255),
        status VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
db_connection.commit()
print("Connected to Database successfully")


def _find_prefixes(lines: List[str]):
    prefixes = []
    for line in lines: 
        if "Prefix: " in line: 
            prefix = line.split(":")[1].lstrip(" ")
            print(prefix)
            if prefix != ":" and prefix != "": 
                prefixes.append(prefix)
    return prefixes

def _remove_prefixes(file_name):
    try:
        with open("data/processed_modules/" +file_name, "r", encoding="utf8") as file:
            try:
                print(f"Removing Prefixes from {file_name}")
                lines = file.readlines()
                modified_lines = []
                prefixes : List[str] = _find_prefixes(lines)
                for line in lines: 
                    if("Prefix:") in line: continue
                    for prefix in prefixes:
                        line = line.replace(prefix+":", "")
                        line = line.replace(prefix, "")
                        line = line.replace ("<http://" ,"")
                        line = line.replace (">", "")
                    modified_lines.append(line)
                with open("data/prefixless_modules/" + file_name, "w") as output:
                    output.writelines(modified_lines)
                return True
            except Exception as e:
                with open("log/prefix_removal", "a") as log:
                    log.write(f"Couldn't remove prefixes in {file_name}\n")
    except:
        traceback.print_exc()


def on_message(channel, method, properties, body):
    file_name = body.decode()
    print(f"Processing {file_name}")
    if(file_name not in os.listdir("/output/")):
        cursor.execute("UPDATE prefix_removal SET status =%s WHERE file_name=%s", ("Processing", file_name))
        db_connection.commit() 
        channel.basic_publish(exchange="", routing_key=queue_output, body=file_name)
        if(_remove_prefixes(file_name)):
        # Publish the processed message to the output queue
            channel.basic_publish(exchange="", routing_key=queue_output, body=file_name)
            print(f"Sent processed message to {queue_output}: {file_name}")
            print(f"Updating Database: {file_name} - Done")
            # Insert into PostgreSQL table
            cursor.execute("UPDATE prefix_removal SET status =%s WHERE file_name=%s", ("Done", file_name))
            db_connection.commit()  
            cursor.execute("INSERT INTO translation (file_name, status) VALUES (%s, %s)", (file_name, "Waiting"))
            db_connection.commit()  
            print("Updated Database!")
        else: 
            cursor.execute("UPDATE prefix_removal SET status =%s, error_message=%s WHERE file_name=%s", ("Coudlt Remove Prefixes","Failed", file_name))
            db_connection.commit()

    # Acknowledge the message to RabbitMQ
    channel.basic_ack(delivery_tag=method.delivery_tag)





def start_worker():
    """ Main worker function to consume messages """
    connection = None
    channel = None

    # Retry loop until RabbitMQ is available
    while connection is None:
        try:
            print("Attempting to connect to RabbitMQ...")
            credentials = pika.PlainCredentials("rabbitmq_user", "rabbitmq_password")

            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host, credentials=credentials))
            channel = connection.channel()

            # Declare the input queue to ensure it exists
            channel.queue_declare(queue=queue_input, durable=True)
            channel.queue_declare(queue=queue_output, durable=True)

            # Start consuming messages
            channel.basic_consume(queue=queue_input, on_message_callback=on_message)
            print(f"Waiting for messages in {queue_input}. To exit press CTRL+C")
            channel.start_consuming()

        except Exception as e:
            print(f"Connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)  # Wait 5 seconds before retrying
    

if __name__ == "__main__":
    start_worker()