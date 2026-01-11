import pika
import os
import time
import psycopg2
import pandas as pd

# Fetch environment variables
rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
queue_output_ontologies = "Ontologies"
queue_output_modules = "Modules_Preprocess"
queue_output_filter = "filtering"
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = "postgress_password"

print("GETTING DATABASE CONNECTION")
def start_worker():
    """ Main worker function to consume messages """
    connection = None
    channel = None
    input_directory = (f"/input")
    output_directory = ("/output")

    # Retry loop until RabbitMQ is available
    while connection is None:
        try:
            print("Attempting to connect to RabbitMQ...")
            credentials = pika.PlainCredentials("rabbitmq_user", "rabbitmq_password")
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host, credentials=credentials))
            channel = connection.channel()
            channel.queue_declare(queue="embed", durable=True)

        except Exception as e:
            print(f"Connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)  # Wait 5 seconds before retrying
    time.sleep(8)        

    data = pd.read_csv("/input/filtered_dataset.csv", names=["file_name", "consistency", "tokenized_length", "body", "inconsistency"])
    filenames = data["file_name"].values



    done_processing = []
#    for filename in os.listdir(output_directory):
#        done_processing.append(filename.split("_Module")[0]+ ".owl")
#    done_processing = set(done_processing)    
#    print(done_processing)
    for filename in filenames:
#        print(filename)
        file_path = os.path.join(input_directory, filename)
        
#        if os.path.isfile(file_path):  # Ensure it's a file
        channel.basic_publish("", "embed", filename.split(".")[0]+".owl")  # Send to RabbitMQ queue
        print(f"Processed file: {filename}")


if __name__ == "__main__":
    start_worker()
