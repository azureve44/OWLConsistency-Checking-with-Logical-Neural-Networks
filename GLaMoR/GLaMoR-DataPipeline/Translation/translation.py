import json
from pathlib import Path
from typing import List, Optional
import os
import pika
import time
import psycopg2
import traceback
rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
queue_input = os.getenv("RABBITMQ_QUEUE_INPUT", "Translation")
queue_output = os.getenv("RABBITMQ_QUEUE_OUTPUT", "filtering")
input_directory = Path(os.getenv("INPUT_DIRECTORY", "/input"))
output_directory = Path(os.getenv("OUTPUT_DIRECTORY", "/output"))
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "data_processing")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgress_password")
print("Connecting to database...")
cursor = None
while cursor is None:
    try:
        db_connection = psycopg2.connect(
            host=POSTGRES_HOST,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
        )
        cursor = db_connection.cursor()
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        print("Retrying in 5 seconds...")
        time.sleep(5)
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS collection_status (
        id SERIAL PRIMARY KEY,
        file_name VARCHAR(255),
        status VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)
db_connection.commit()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS data_filter (
        id SERIAL PRIMARY KEY,
        file_name VARCHAR(255) NOT NULL,
        status VARCHAR(50) NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        error_message TEXT
    )
    """
)
db_connection.commit()
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS translation (
        id SERIAL PRIMARY KEY,
        file_name VARCHAR(255) NOT NULL,
        status VARCHAR(50) NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        error_message TEXT
    )
    """
)
db_connection.commit()
print("Connected to Database successfully")
ALLOWED_STATUS_TABLES = {"translation", "data_filter"}
DECLARATION_HEADS = {"Class", "Individual", "ObjectProperty", "DataProperty", "AnnotationProperty", "Datatype", "Ontology"}
DECLARATION_OBJECTS = DECLARATION_HEADS - {"Ontology"}
def upsert_status(table_name: str, file_name: str, status: str, error_message: Optional[str] = None):
    if table_name not in ALLOWED_STATUS_TABLES:
        raise ValueError(f"Unsupported table name: {table_name}")
    try:
        cursor.execute(
            f"INSERT INTO {table_name} (file_name, status, error_message) VALUES (%s, %s, %s) "
            f"ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, error_message = EXCLUDED.error_message",
            (file_name, status, error_message),
        )
        db_connection.commit()
    except Exception:
        db_connection.rollback()
        raise
def translate_to_tripels(path) -> str:
    try:
        with open(input_directory / path, "r", encoding="utf-8") as file:
            lines: List[str] = file.readlines()
            lines = _concatinate_and_revome(lines)
            triples = _translate_to_triples(lines)
            triples = _clean_triples(triples)
        output_name = path.split(".")[0] + ".jsonl"
        with open(output_directory / output_name, "w", encoding="utf-8") as output:
            json.dump(triples, output)
        return output_name
    except Exception:
        traceback.print_exc()
        return ""
def _concatinate_and_revome(lines: List[str]) -> List[str]:
    result = []
    for i in range(0, len(lines)):
        lines[i] = lines[i].strip().replace("\n", "")
        if "Prefix:" in lines[i]:
            continue
        if i > 0 and "and " in lines[i]:
            result[-1] = result[-1] + " " + lines[i]
            continue
        result.append(lines[i])
    return result
def _translate_to_triples(lines: List[str]) -> List[List[str]]:
    triples: List[List[str]] = []
    current_subject = ""
    current_relation = "is"
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line == "Ontology:":
            continue
        if ":" in line:
            head, tail = line.split(":", 1)
            head = head.strip()
            tail = tail.strip()
            if tail:
                current_subject = tail
                current_relation = "is"
                if head not in DECLARATION_HEADS:
                    triples.append([tail, "is", head])
            else:
                current_relation = "is" if head == "Types" else head
            continue
        if not current_subject:
            current_subject = line
            continue
        triples.append([current_subject, current_relation, line])
    return triples
def _clean_triples(triples: List[List[str]]) -> List[List[str]]:
    cleaned: List[List[str]] = []
    seen = set()
    for sub, relation, obj in triples:
        if relation == "Facts":
            try:
                obj_parts = obj.split("  ", 1)
                relation = obj_parts[0].strip()
                obj = obj_parts[1].strip()
            except Exception:
                print([sub, relation, obj])
                print(relation)
                raise IndexError("BOOOOB")
        if relation == "DisjointWith" and "," in obj:
            split_values = [part.lstrip(" ") for part in obj.split(",") if part.strip()]
            for disjoint in split_values:
                candidate = [sub.strip(), relation.strip(), disjoint.strip()]
                key = tuple(candidate)
                if not any("comment" in field.lower() for field in candidate) and key not in seen:
                    seen.add(key)
                    cleaned.append(candidate)
            continue
        candidate = [sub.strip(), relation.strip(), obj.strip()]
        if any(not field for field in candidate):
            continue
        if any("comment" in field.lower() for field in candidate):
            continue
        if candidate[1] == "is" and candidate[2] in DECLARATION_OBJECTS:
            continue
        key = tuple(candidate)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(candidate)
    return cleaned
def on_message(channel, method, properties, body):
    del properties
    file_name = body.decode().strip()
    output_name = file_name.split(".")[0] + ".jsonl"
    try:
        if (output_directory / output_name).exists():
            upsert_status("data_filter", output_name, "Waiting")
            upsert_status("translation", file_name, "Done")
            channel.basic_publish(exchange="", routing_key=queue_output, body=output_name.encode("utf-8"))
            print(f"Reused existing translated output for {file_name}")
        else:
            upsert_status("data_filter", output_name, "Waiting")
            upsert_status("translation", file_name, "Processing")
            translated_output_name = translate_to_tripels(file_name)
            if not translated_output_name:
                raise RuntimeError(f"Translation produced no output for {file_name}")
            if queue_output:
                channel.basic_publish(exchange="", routing_key=queue_output, body=translated_output_name.encode("utf-8"))
                print(f"Sent processed message to {queue_output}: {file_name}")
            upsert_status("translation", file_name, "Done")
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except Exception:
        error_message = traceback.format_exc()
        print(error_message)
        db_connection.rollback()
        try:
            upsert_status("translation", file_name, "Error", error_message)
        except Exception:
            print(traceback.format_exc())
        try:
            upsert_status("data_filter", output_name, "Error", error_message)
        except Exception:
            print(traceback.format_exc())
        channel.basic_ack(delivery_tag=method.delivery_tag)
def start_worker():
    connection = None
    channel = None
    while connection is None:
        try:
            print("Attempting to connect to RabbitMQ...")
            credentials = pika.PlainCredentials("rabbitmq_user", "rabbitmq_password")
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host, credentials=credentials))
            channel = connection.channel()
            channel.queue_declare(queue=queue_input, durable=True)
            channel.queue_declare(queue=queue_output, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=queue_input, on_message_callback=on_message)
            print(f"Waiting for messages in {queue_input}. To exit press CTRL+C")
            channel.start_consuming()
        except Exception as e:
            print(f"Connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)
if __name__ == "__main__":
    start_worker()
