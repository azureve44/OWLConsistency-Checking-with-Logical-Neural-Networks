from typing import List
import os
import pika
import time
import traceback
from owl2vec_star import owl2vec_star
import os
import numpy as np
import traceback
from typing import List, Dict
import nltk
import gc

nltk.download("punkt_tab")


rabbitmq_host ="rabbitmq"
queue_input = "embed"

PREFIXES : List[str] = ["AIO","EID","OIL","OILWI","OILWPI","UE","UEWI1","UEWI2","UEWPI","UEWIP","SOSINETO","CSC","OOR","OOD"]

def _create_graph_embedding(embeddings):
    ''' 
    Given the KeyedVector Embeddings of all words in an ontology, 
    returns the average of the vectors as graph embeddings
    '''
    words = embeddings.key_to_index
    vectors = [embeddings[word] for word in words]
    graph_embedding = np.array(vectors)
    return graph_embedding
# %%

def process_file(filename):
    """Processes a single file to extract its graph embedding."""
    directory_path = "/input_inconsistent/" if filename.split("_")[0] in PREFIXES else "/input_consistent/"
    print(f"processing {directory_path} {filename}")
    gensim_model = owl2vec_star.extract_owl2vec_model(
        f"{directory_path}{filename}", "./default.cfg", True, True, True
    )
    graph_embedding = _create_graph_embedding(gensim_model.wv)
    del gensim_model
    gc.collect()
    return filename, graph_embedding

def on_message(channel, method, properties, body):
    try:
        file_name = body.decode()
        if(file_name.split(".")[0]+".npy" not in os.listdir("/output/")): 
            embedding = process_file(file_name)
            if embedding:
                output_path = f"/output/{file_name.rsplit('.', 1)[0]}.npy"
                np.save(output_path, embedding[1])
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exception:

        with open("/output/error_log.txt", "a", buffering=1) as f:
            tb = traceback.extract_tb(exception.__traceback__)
            error_file, line_number, func_name, _ = tb[-1]
            log_message = f"{body.decode()}, {error_file}-{line_number}: {str(exception)}\n"
            print(log_message)
            f.write(log_message)
            f.flush()


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
            # Start consuming messages
            channel.basic_consume(queue=queue_input, on_message_callback=on_message)
            print(f"Waiting for messages in {queue_input}. To exit press CTRL+C")
            channel.start_consuming()

        except Exception as e:
            print(f"Connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)  # Wait 5 seconds before retrying
    

if __name__ == "__main__":
    with open("/output/error_log.txt", "w") as f:
        pass
    start_worker()
