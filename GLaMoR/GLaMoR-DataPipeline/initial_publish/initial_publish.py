import os
import time
import pika
import pandas as pd

rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
rabbitmq_user = os.getenv("RABBITMQ_USER", "rabbitmq_user")
rabbitmq_pass = os.getenv("RABBITMQ_PASS", "rabbitmq_password")
queue_output = os.getenv("RABBITMQ_QUEUE_OUTPUT", "Ontologies")

INPUT_CSV = "/input/filtered_dataset.csv"
INPUT_ROOT = "/input"


def connect_rabbitmq():
    connection = None
    channel = None

    while connection is None:
        try:
            print("Attempting to connect to RabbitMQ...")
            credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)
            params = pika.ConnectionParameters(host=rabbitmq_host, credentials=credentials)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=queue_output, durable=True)
            print(f"Connected. Publishing to queue: {queue_output}")
        except Exception as e:
            print(f"Connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

    return connection, channel


def start_worker():
    print("GETTING DATABASE CONNECTION")
    connection, channel = connect_rabbitmq()

    time.sleep(2)

    data = pd.read_csv(INPUT_CSV, header=0)
    filenames = data["file_name"].dropna().astype(str).values

    published = 0
    for filename in filenames:
        file_path = os.path.join(INPUT_ROOT, filename)
        if not os.path.isfile(file_path):
            print(f"Skipping missing file: {file_path}")
            continue

        channel.basic_publish("", queue_output, filename.encode("utf-8"))
        print(f"Processed file: {filename}")
        published += 1

    print(f"Done. Published {published} files.")
    connection.close()


if __name__ == "__main__":
    start_worker()
