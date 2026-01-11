import yaml
import json
from typing import List
from pathlib import Path
import os
import pika
import time
import psycopg2
import traceback

rabbitmq_host ="rabbitmq"
queue_input = "translation"
queue_output = "filtering"

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "data_processing")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgress_password")

print("Connecting to database...")
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
    CREATE TABLE IF NOT EXISTS collection_status (
        id SERIAL PRIMARY KEY,
        file_name VARCHAR(255),
        status VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
db_connection.commit()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS data_filter (
        id SERIAL PRIMARY KEY,
        file_name VARCHAR(255),
        status VARCHAR(50),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
db_connection.commit()
print("Connected to Database successfully")

def translate_to_tripels(path) -> List[List[str]]:
    try:
        with open("/input/" + path, "r") as file:   
            lines : List[str] = file.readlines()
            lines = _concatinate_and_revome(lines)
            triples = _translate_to_triples(lines)
            triples = _clean_triples(triples)
        output_name = path.split(".")[0] + ".jsonl"
        with open("/output/"+ output_name, "w") as output: 
                json.dump(triples, output)
        return output_name
    except:
        traceback.print_exc()
        return ""
    

def _concatinate_and_revome(lines : List[str]) -> List[str]:
    """
    Given a List of lines representing a OWL Ontology in Manchaster syntax,
    removes any occurance of a "Prefix:xxx" definition, and if two consecutive lines are logically connected by and, 
    merges them into one line
    """
    result = []
    for i in range(0,len(lines)):
        lines[i] = lines[i].strip().replace("\n", "")
        if "Prefix:" in lines[i]:
            continue
        if i > 0 and "and " in lines[i]:
            result[-1] = result[-1] + " " + lines[i]
            continue
        result.append(lines[i])
    
    return result

def _translate_to_triples(lines : List[str]) -> List[str]:
    """
    Translates a list of lines representing a OWL Ontology in Manchaster Syntax into a List of triples.
    Always checks the next two lines. If both lines are empty, the next Object starts in the file. 
    If only one line is empty, the following line starts a new property of the Object.
    """
    triples : List[List[str]] = []
    line = lines[0]
    for i in range(1, len(lines)):

        line2 = lines[i]
        # Both Lines are Empty: New Object starts at the next Line
        if(line == "" and line2 == ""):
            line = lines[i]
            continue
        # Only one line Empty: Skip
        if(line == ""):
            line = lines[i]
            continue
        
        # If line contains ":": new Object gets defined
        tuple = line.split(":")
        if(":" in line):
            if(tuple[1] != ""):
                sub = tuple[0]
                obj = tuple[1]
                relation = "is"
        #If Line does contains ":" but no subject, new relation gets defined
            else: 
                relation = tuple[0].strip()
                line = lines[i]
                continue
        #If Line does not contain ":": new Subject gets defined
        else:
            sub = line.strip()        
        line = lines[i].replace("\n", "").strip()
        triples.append([obj, relation, sub])
    return triples

def _clean_triples(triples : List[List[str]]) -> List[List[str]]:
    """ 
    Given a list of triples, if a triple contains the relation "Facts", the actual relation is part of the subject. 
    E.g.  ["Person1", "Facts", "hasParent Person2"] -> ["Person1" "hasParent", "Person2"]
    """
    for i in range(len(triples)-1, -1, -1):
        [sub, relation, obj] = triples[i]
        if(relation == "Facts"):
            try:
                obj_parts = obj.split("  ")
                new_relation = obj_parts[0]
                new_obj = obj_parts[1]
            except: 
                print([sub, relation, obj])
                print(relation)
                raise IndexError("BOOOOB")
            triples[i] = [sub, new_relation, new_obj]
        if(relation == "DisjointWith"):
            if("," in obj):
                disjoints = obj.split(",")
                for disjoint in disjoints:
                    triples.insert(i+1, [sub, relation, disjoint.lstrip(" ")])
                triples.pop(i)
        if("comment" in sub or "comment" in relation or "comment" in obj):
            triples.pop(i)
        
    return triples

        

def on_message(channel, method, properties, body):
    try:
        file_name = body.decode()
        if(file_name in os.listdir("/output/")):
            cursor.execute("UPDATE translation SET status =%s WHERE file_name=%s", ("Done", file_name))
            db_connection.commit()
            channel.basic_publish(exchange="", routing_key=queue_output, body=file_name)
        else:
            cursor.execute("INSERT INTO data_filter (file_name, status) VALUES (%s, %s)", (file_name.split(".")[0] + ".jsonl", "Waiting"))
            db_connection.commit() 
            cursor.execute("UPDATE translation SET status =%s WHERE file_name=%s", ("Processing", file_name))
            db_connection.commit() 

            output_name = translate_to_tripels(file_name)
            # Publish the processed message to the output queue
            if queue_output and output_name:
                channel.basic_publish(exchange="", routing_key=queue_output, body=output_name)
                print(f"Sent processed message to {queue_output}: {file_name}")

            cursor.execute("UPDATE translation SET status =%s WHERE file_name=%s", ("Done", file_name))
            db_connection.commit()  

        # Acknowledge the message to RabbitMQ
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except:
        traceback.print_exc()




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