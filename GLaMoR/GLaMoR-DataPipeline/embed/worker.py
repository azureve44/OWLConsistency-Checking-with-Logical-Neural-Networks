from typing import List
import gc
import hashlib
import os
import time
import traceback
import nltk
import numpy as np
import pika
from rdflib import Graph, Literal
from owl2vec_star import owl2vec_star
nltk.download("punkt_tab")
rabbitmq_host = "rabbitmq"
queue_input = "embed"
INPUT_CONSISTENT_DIR = os.getenv("INPUT_CONSISTENT_DIR", "/input_consistent")
INPUT_INCONSISTENT_DIR = os.getenv("INPUT_INCONSISTENT_DIR", "/input_inconsistent")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/output")
INPUT_SEARCH_DIRS = [
    d.strip()
    for d in os.getenv(
        "INPUT_SEARCH_DIRS",
        f"{INPUT_CONSISTENT_DIR},{INPUT_INCONSISTENT_DIR}",
    ).split(",")
    if d.strip()
]
PREFIXES: List[str] = [
    "AIO",
    "EID",
    "OIL",
    "OILWI",
    "OILWPI",
    "UE",
    "UEWI1",
    "UEWI2",
    "UEWPI",
    "UEWIP",
    "SOSINETO",
    "CSC",
    "OOR",
    "OOD",
]
EMBEDDING_DIMENSION = 100
# NOTE:
# We currently force all ontologies through the fallback RDF-hash
# embedding path so consistent and inconsistent files share the
# same embedding method during training and evaluation.
def _normalize_rel_path(filename: str) -> str:
    rel = filename.strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        raise ValueError(f"Invalid filename payload: {filename}")
    return rel
def _resolve_input_path(filename: str) -> str:
    rel = _normalize_rel_path(filename)
    base_name = os.path.basename(rel)
    preferred_root = INPUT_INCONSISTENT_DIR if base_name.split("_")[0] in PREFIXES else INPUT_CONSISTENT_DIR
    fallback_root = INPUT_CONSISTENT_DIR if preferred_root == INPUT_INCONSISTENT_DIR else INPUT_INCONSISTENT_DIR
    prioritized_roots = [preferred_root, fallback_root] + [
        d for d in INPUT_SEARCH_DIRS if d not in {preferred_root, fallback_root}
    ]
    candidates = [
        os.path.join(preferred_root, rel),
        os.path.join(preferred_root, base_name),
        os.path.join(fallback_root, rel),
        os.path.join(fallback_root, base_name),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    basename_hits = []
    for root in prioritized_roots:
        if not os.path.isdir(root):
            continue
        for walk_root, _, files in os.walk(root):
            if base_name in files:
                basename_hits.append(os.path.join(walk_root, base_name))
    if len(basename_hits) == 1:
        return basename_hits[0]
    if len(basename_hits) > 1:
        raise FileNotFoundError(
            f"Ambiguous basename '{base_name}'. Matches: {basename_hits}. Payload was '{filename}'."
        )
    raise FileNotFoundError(f"Input ontology not found. Tried: {candidates}")
def _output_npy_path(filename: str) -> str:
    rel = _normalize_rel_path(filename)
    output_path = os.path.join(OUTPUT_DIR, f"{os.path.splitext(rel)[0]}.npy")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    return output_path
def _create_graph_embedding(embeddings):
    words = list(embeddings.key_to_index)
    vectors = [embeddings[word] for word in words]
    graph_embedding = np.mean(np.array(vectors), axis=0)
    return graph_embedding
def _local_name(text: str) -> str:
    value = text.rsplit("#", 1)[-1]
    value = value.rsplit("/", 1)[-1]
    return value
def _term_tokens(term) -> list[str]:
    if isinstance(term, Literal):
        text = str(term)
    else:
        text = _local_name(str(term))
    text = text.replace("-", " ").replace("_", " ").replace(".", " ")
    chunks: list[str] = []
    current: list[str] = []
    for char in text:
        if char.isalnum():
            if current and char.isupper() and any(c.islower() for c in current):
                chunks.append("".join(current).lower())
                current = [char]
            else:
                current.append(char)
        else:
            if current:
                chunks.append("".join(current).lower())
                current = []
    if current:
        chunks.append("".join(current).lower())
    return [chunk for chunk in chunks if chunk]
def _hash_token(token: str, *, dimensions: int) -> tuple[int, float]:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    index = int.from_bytes(digest[:8], "big") % dimensions
    sign = -1.0 if digest[8] % 2 else 1.0
    magnitude = 1.0 + (digest[9] / 255.0)
    return index, sign * magnitude
def _fallback_graph_embedding(ontology_path: str, *, dimensions: int = EMBEDDING_DIMENSION) -> np.ndarray:
    graph = Graph()
    graph.parse(ontology_path)
    vector = np.zeros(dimensions, dtype=np.float32)
    token_count = 0
    for subject, predicate, obj in graph:
        for term in (subject, predicate, obj):
            for token in _term_tokens(term):
                index, signed_weight = _hash_token(token, dimensions=dimensions)
                vector[index] += signed_weight
                token_count += 1
    if token_count == 0:
        with open(ontology_path, "rb") as handle:
            raw_bytes = handle.read()
        digest = hashlib.sha256(raw_bytes).digest()
        for index in range(dimensions):
            vector[index] = ((digest[index % len(digest)] / 255.0) * 2.0) - 1.0
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector.astype(np.float32)
def _owl2vec_embedding(ontology_path: str) -> np.ndarray:
    gensim_model = owl2vec_star.extract_owl2vec_model(
        ontology_path, "./default.cfg", True, True, True
    )
    try:
        words = list(gensim_model.wv.key_to_index)
        if not words:
            raise ValueError("OWL2Vec produced an empty vocabulary")
        graph_embedding = _create_graph_embedding(gensim_model.wv)
        if graph_embedding is None or np.size(graph_embedding) == 0:
            raise ValueError("OWL2Vec produced an empty graph embedding")
        graph_embedding = np.asarray(graph_embedding, dtype=np.float32)
        if np.isnan(graph_embedding).any():
            raise ValueError("OWL2Vec produced NaN values")
        return graph_embedding
    finally:
        del gensim_model
        gc.collect()
def process_file(filename):
    ontology_path = _resolve_input_path(filename)
    print(f"processing {ontology_path}")
    # Force a single embedding method for all files so consistent and
    # inconsistent ontologies are represented the same way.
    graph_embedding = _fallback_graph_embedding(ontology_path)
    print(f"generated fallback RDF hash embedding for {filename}")
    # Old mixed-method logic kept here intentionally for reference.
    # try:
    #     graph_embedding = _owl2vec_embedding(ontology_path)
    #     print(f"generated owl2vec embedding for {filename}")
    # except Exception as exception:
    #     print(f"falling back to RDF hash embedding for {filename}: {exception}")
    #     graph_embedding = _fallback_graph_embedding(ontology_path)
    return filename, graph_embedding
def on_message(channel, method, properties, body):
    file_name = body.decode()
    output_path = _output_npy_path(file_name)
    try:
        if not os.path.isfile(output_path):
            embedding = process_file(file_name)
            if embedding:
                np.save(output_path, embedding[1])
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except FileNotFoundError as exception:
        with open(os.path.join(OUTPUT_DIR, "error_log.txt"), "a", buffering=1) as f:
            log_message = f"{file_name}, missing input: {str(exception)}\n"
            print(log_message)
            f.write(log_message)
            f.flush()
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exception:
        with open(os.path.join(OUTPUT_DIR, "error_log.txt"), "a", buffering=1) as f:
            tb = traceback.extract_tb(exception.__traceback__)
            error_file, line_number, func_name, _ = tb[-1]
            log_message = f"{file_name}, {error_file}-{line_number}: {str(exception)}\n"
            print(log_message)
            f.write(log_message)
            f.flush()
        channel.basic_ack(delivery_tag=method.delivery_tag)
def start_worker():
    connection = None
    channel = None
    print(f"Configured search dirs: {INPUT_SEARCH_DIRS}")
    while connection is None:
        try:
            print("Attempting to connect to RabbitMQ...")
            credentials = pika.PlainCredentials("rabbitmq_user", "rabbitmq_password")
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=rabbitmq_host, credentials=credentials)
            )
            channel = connection.channel()
            channel.queue_declare(queue=queue_input, durable=True)
            channel.basic_consume(queue=queue_input, on_message_callback=on_message)
            print(f"Waiting for messages in {queue_input}. To exit press CTRL+C")
            channel.start_consuming()
        except Exception as e:
            print(f"Connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)
if __name__ == "__main__":
    with open(os.path.join(OUTPUT_DIR, "error_log.txt"), "w") as f:
        pass
    start_worker()
