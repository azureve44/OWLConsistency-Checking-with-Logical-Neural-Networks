from typing import List, Optional
import re
import os
import pika
import time
import psycopg2
import traceback
rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
queue_input = os.getenv("RABBITMQ_QUEUE_INPUT", "Remove_Prefix")
queue_output = os.getenv("RABBITMQ_QUEUE_OUTPUT", "Translation")
input_directory = os.getenv("INPUT_DIRECTORY", "/input")
output_directory = os.getenv("OUTPUT_DIRECTORY", "/output")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "data_processing")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgress_password")
def _get_db_cursor():
    """Open a fresh connection and return (connection, cursor)."""
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )
    return conn, conn.cursor()
print("Connecting to database....")
db_connection, cursor = None, None
while db_connection is None:
    try:
        db_connection, cursor = _get_db_cursor()
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
def _extract_prefix_alias(line: str) -> Optional[str]:
    if "Prefix:" not in line:
        return None
    match = re.match(r'^\s*Prefix:\s*(.*?)\s*:\s*<.*>\s*$', line)
    if not match:
        return None
    alias = match.group(1).strip()
    return alias if alias else None
def _find_prefixes(lines: List[str]):
    prefixes = []
    for line in lines:
        alias = _extract_prefix_alias(line)
        if alias:
            prefixes.append(alias)
    prefixes.sort(key=len, reverse=True)
    return prefixes
def _remove_prefixes(file_name):
    try:
        input_file = os.path.join(input_directory, file_name)
        output_file = os.path.join(output_directory, file_name)
        with open(input_file, "r", encoding="utf8") as file:
            print(f"Removing Prefixes from {file_name}")
            lines = file.readlines()
            modified_lines = []
            prefixes: List[str] = _find_prefixes(lines)
            for line in lines:
                if "Prefix:" in line:
                    continue
                for prefix in prefixes:
                    line = line.replace(prefix + ":", "")
                line = line.replace("<http://", "")
                line = line.replace(">", "")
                modified_lines.append(line)
            with open(output_file, "w", encoding="utf8") as output:
                output.writelines(modified_lines)
            return True
    except Exception:
        traceback.print_exc()
        return False
def _db_execute(sql, params=()):
    """Execute a SQL statement, reconnecting once on failure."""
    global db_connection, cursor
    try:
        cursor.execute(sql, params)
        db_connection.commit()
    except Exception as e:
        print(f"DB error ({e}), reconnecting and retrying once...")
        try:
            db_connection.rollback()
        except Exception:
            pass
        try:
            db_connection, cursor = _get_db_cursor()
            cursor.execute(sql, params)
            db_connection.commit()
        except Exception as e2:
            print(f"DB retry also failed: {e2}")
            try:
                db_connection.rollback()
            except Exception:
                pass
def on_message(channel, method, properties, body):
    file_name = body.decode()
    print(f"Processing {file_name}")
    try:
        if file_name not in os.listdir(output_directory):
            _db_execute(
                "UPDATE prefix_removal SET status=%s WHERE file_name=%s",
                ("Processing", file_name),
            )
            if _remove_prefixes(file_name):
                # Publish to the next queue
                channel.basic_publish(
                    exchange="", routing_key=queue_output, body=file_name.encode("utf-8")
                )
                print(f"Sent processed message to {queue_output}: {file_name}")
                _db_execute(
                    "UPDATE prefix_removal SET status=%s WHERE file_name=%s",
                    ("Done", file_name),
                )
                # ON CONFLICT DO NOTHING — safe to re-run across restarts/re-runs
                _db_execute(
                    "INSERT INTO translation (file_name, status) VALUES (%s, %s) "
                    "ON CONFLICT (file_name) DO NOTHING",
                    (file_name, "Waiting"),
                )
                print("Updated Database!")
            else:
                _db_execute(
                    "UPDATE prefix_removal SET status=%s WHERE file_name=%s",
                    ("Couldnt Remove Prefixes", file_name),
                )
        else:
            print(f"Already processed (output exists), skipping: {file_name}")
    except Exception:
        traceback.print_exc()
    # Always ack — even on error we don't want infinite redelivery
    channel.basic_ack(delivery_tag=method.delivery_tag)
def start_worker():
    """Main worker function to consume messages."""
    while True:
        connection = None
        try:
            print("Attempting to connect to RabbitMQ...")
            credentials = pika.PlainCredentials("rabbitmq_user", "rabbitmq_password")
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=rabbitmq_host, credentials=credentials)
            )
            channel = connection.channel()
            # Set prefetch so we don't swallow all messages at once
            channel.basic_qos(prefetch_count=1)
            channel.queue_declare(queue=queue_input, durable=True)
            channel.queue_declare(queue=queue_output, durable=True)
            channel.basic_consume(queue=queue_input, on_message_callback=on_message)
            print(f"Waiting for messages in {queue_input}. To exit press CTRL+C")
            channel.start_consuming()
        except KeyboardInterrupt:
            print("Shutting down.")
            break
        except Exception as e:
            print(f"Connection/consumer error: {e}. Retrying in 5 seconds...")
            try:
                if connection and not connection.is_closed:
                    connection.close()
            except Exception:
                pass
            time.sleep(5)
if __name__ == "__main__":
    start_worker()
