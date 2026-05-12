#!/usr/bin/env python3
"""
Department-based modularization for consolidated LUBM ontologies.
Replaces OAPT for the consolidated University*.owl intake path.
"""
import os
import time
import traceback
from pathlib import Path
from typing import Optional, Set
import pika
import psycopg2
import rdflib
from rdflib import URIRef
from rdflib.namespace import OWL, RDF, RDFS
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "rabbitmq_user")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "rabbitmq_password")
QUEUE_INPUT = os.getenv("RABBITMQ_QUEUE_INPUT", "Ontologies")
QUEUE_OUTPUT = os.getenv("RABBITMQ_QUEUE_OUTPUT", "Modules_Preprocess")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "data_processing")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgress_password")
INPUT_ROOT = Path(os.getenv("INPUT_ROOT", "/input"))
OUTPUT_ROOT = Path(os.getenv("OUTPUT_ROOT", "/output"))
STATUS_CLUSTER = os.getenv("MODULARIZATION_CLUSTER", "department-splitter")
CLASS_PROPERTY_TYPES = [
    OWL.Class,
    OWL.ObjectProperty,
    OWL.DatatypeProperty,
    OWL.AnnotationProperty,
    OWL.FunctionalProperty,
    OWL.InverseFunctionalProperty,
    OWL.TransitiveProperty,
    OWL.SymmetricProperty,
]
SCHEMA_PREDICATES = {
    RDF.type,
    RDFS.subClassOf,
    RDFS.domain,
    RDFS.range,
    OWL.equivalentClass,
    OWL.disjointWith,
    OWL.imports,
}
def log(message: str):
    print(message, flush=True)
def local_name(term) -> str:
    text = str(term)
    if "#" in text:
        return text.rsplit("#", 1)[1]
    return text.rstrip("/").rsplit("/", 1)[-1]
def is_lubm_term(term) -> bool:
    return isinstance(term, URIRef) and "univ-bench.owl#" in str(term)
def is_department_class(term) -> bool:
    return isinstance(term, URIRef) and local_name(term) == "Department"
def is_department_local(term, department_uri: URIRef) -> bool:
    return isinstance(term, URIRef) and str(term).startswith(str(department_uri))
def setup_database():
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS modularization (
            id SERIAL PRIMARY KEY,
            file_name VARCHAR(255),
            status VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    return conn, cur
def extract_tbox(graph: rdflib.Graph) -> rdflib.Graph:
    tbox = rdflib.Graph()
    for class_type in CLASS_PROPERTY_TYPES:
        for subject in graph.subjects(RDF.type, class_type):
            for predicate, obj in graph.predicate_objects(subject):
                tbox.add((subject, predicate, obj))
            for incoming_subject, incoming_predicate in graph.subject_predicates(subject):
                if incoming_predicate == RDF.type:
                    continue
                if is_lubm_term(incoming_subject):
                    tbox.add((incoming_subject, incoming_predicate, subject))
    for subject, predicate, obj in graph:
        if predicate == RDF.type:
            if is_lubm_term(subject):
                tbox.add((subject, predicate, obj))
            continue
        if predicate in SCHEMA_PREDICATES and (is_lubm_term(subject) or is_lubm_term(obj)):
            tbox.add((subject, predicate, obj))
    return tbox
def find_departments(graph: rdflib.Graph):
    return sorted({subject for subject, obj in graph.subject_objects(RDF.type) if is_department_class(obj)}, key=str)
def find_university_uri(graph: rdflib.Graph, department_uri: URIRef):
    for obj in graph.objects(department_uri, None):
        if isinstance(obj, URIRef) and local_name(obj).startswith("University"):
            return obj
    return None
def build_department_subgraph(graph: rdflib.Graph, department_uri: URIRef) -> rdflib.Graph:
    subgraph = rdflib.Graph()
    university_uri = find_university_uri(graph, department_uri)
    for subject, predicate, obj in graph:
        subject_local = is_department_local(subject, department_uri)
        object_local = is_department_local(obj, department_uri)
        touches_department_root = subject == department_uri or obj == department_uri
        touches_university = university_uri is not None and (subject == university_uri or obj == university_uri)
        if subject_local or object_local or touches_department_root:
            if isinstance(subject, URIRef) and not (subject_local or touches_department_root or subject == university_uri or is_lubm_term(subject)):
                continue
            if isinstance(obj, URIRef) and not (object_local or touches_department_root or obj == university_uri or is_lubm_term(obj)):
                continue
            subgraph.add((subject, predicate, obj))
            continue
        if touches_university:
            other = obj if subject == university_uri else subject
            if is_department_local(other, department_uri) or other == department_uri:
                subgraph.add((subject, predicate, obj))
    if university_uri is not None:
        for predicate, obj in graph.predicate_objects(university_uri):
            if not isinstance(obj, URIRef):
                subgraph.add((university_uri, predicate, obj))
    return subgraph
def extract_referenced_tbox(tbox: rdflib.Graph, local_subgraph: rdflib.Graph) -> rdflib.Graph:
    seed_terms: Set[URIRef] = set()
    for subject, predicate, obj in local_subgraph:
        if is_lubm_term(subject):
            seed_terms.add(subject)
        if is_lubm_term(predicate):
            seed_terms.add(predicate)
        if is_lubm_term(obj):
            seed_terms.add(obj)
    referenced_tbox = rdflib.Graph()
    changed = True
    while changed:
        changed = False
        for subject, predicate, obj in tbox:
            if subject not in seed_terms and predicate not in seed_terms and obj not in seed_terms:
                continue
            triple = (subject, predicate, obj)
            if triple in referenced_tbox:
                continue
            referenced_tbox.add(triple)
            previous_size = len(seed_terms)
            if is_lubm_term(subject):
                seed_terms.add(subject)
            if is_lubm_term(predicate):
                seed_terms.add(predicate)
            if is_lubm_term(obj):
                seed_terms.add(obj)
            if len(seed_terms) != previous_size:
                changed = True
    return referenced_tbox
def safe_department_name(dept_uri: URIRef) -> str:
    return local_name(dept_uri).replace(":", "_").replace(".", "_")
def process_file(input_path: Path, output_dir: Path):
    graph = rdflib.Graph()
    graph.parse(input_path, format="application/rdf+xml")
    tbox = extract_tbox(graph)
    departments = find_departments(graph)
    if not departments:
        log(f"[WARNING]: No departments found in {input_path}")
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = input_path.stem
    module_names = []
    for dept_uri in departments:
        module = rdflib.Graph()
        local_subgraph = build_department_subgraph(graph, dept_uri)
        referenced_tbox = extract_referenced_tbox(tbox, local_subgraph)
        for triple in referenced_tbox:
            module.add(triple)
        for triple in local_subgraph:
            module.add(triple)
        for prefix, namespace in graph.namespaces():
            module.bind(prefix, namespace)
        output_filename = f"{base_name}_{safe_department_name(dept_uri)}.owl"
        output_path = output_dir / output_filename
        module.serialize(destination=str(output_path), format="pretty-xml")
        module_names.append(output_filename)
    log(f"Generated {len(module_names)} modules for {base_name}")
    return module_names
def mark_status(cur, conn, file_name: str, status: str, error_message: Optional[str] = None):
    try:
        cur.execute(
            "INSERT INTO modularization (file_name, status, cluster, error_message) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (file_name) DO UPDATE SET status = EXCLUDED.status, cluster = EXCLUDED.cluster, error_message = EXCLUDED.error_message",
            (file_name, status, STATUS_CLUSTER, error_message),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
def on_message(channel, method, properties, body, conn, cur):
    del properties
    file_name = body.decode().strip()
    log(f"Processing: {file_name}")
    input_path = INPUT_ROOT / file_name
    output_dir = OUTPUT_ROOT
    try:
        mark_status(cur, conn, file_name, "Processing")
        module_names = process_file(input_path, output_dir)
        if module_names:
            mark_status(cur, conn, file_name, "Done")
            for mod_name in module_names:
                channel.basic_publish(exchange="", routing_key=QUEUE_OUTPUT, body=mod_name.encode())
                log(f"[PUBLISHED]: {mod_name} -> {QUEUE_OUTPUT}")
        else:
            mark_status(cur, conn, file_name, "[ERROR]", "No departments found")
    except Exception:
        error_message = traceback.format_exc()
        log(error_message)
        try:
            mark_status(cur, conn, file_name, "Error", error_message)
        except Exception:
            log(traceback.format_exc())
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)
def start_worker():
    conn, cur = setup_database()
    while True:
        try:
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
            parameters = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_INPUT, durable=True)
            channel.queue_declare(queue=QUEUE_OUTPUT, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=QUEUE_INPUT,
                on_message_callback=lambda ch, method, props, body: on_message(ch, method, props, body, conn, cur),
            )
            log(f"Waiting for messages on {QUEUE_INPUT!r}...")
            channel.start_consuming()
        except Exception as exc:
            log(f"Connection failed: {exc}. Retrying in 5 seconds...")
            time.sleep(5)
if __name__ == "__main__":
    start_worker()
