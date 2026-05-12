from __future__ import annotations
import csv
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from statistics import median, pstdev
from typing import Callable, Iterable
import xml.etree.ElementTree as ET
DEFAULT_LUBM_NAMESPACE = "http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#"
RDF_ABOUT = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about"
RDF_ID = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}ID"
RDF_NODE_ID = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}nodeID"
RDF_RESOURCE = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource"
OWL_IMPORTS = "{http://www.w3.org/2002/07/owl#}imports"
LATEX_ROW_BREAK = r"\\"
@dataclass(frozen=True)
class FileCount:
    file: str
    classes: int
    properties: int
    @property
    def combined(self) -> int:
        return self.classes + self.properties
    def to_row(self) -> dict[str, int | str]:
        return {
            "file": self.file,
            "classes": self.classes,
            "properties": self.properties,
            "combined": self.combined,
        }
@dataclass(frozen=True)
class SchemaEntities:
    classes: frozenset[str]
    object_properties: frozenset[str]
    datatype_properties: frozenset[str]
    @property
    def properties(self) -> frozenset[str]:
        return self.object_properties | self.datatype_properties
@dataclass(frozen=True)
class SummaryStats:
    count: int
    min: int
    max: int
    median: float
    average: float
    sd: float
@dataclass(frozen=True)
class DirectorySummary:
    root: str
    file_count: int
    classes: SummaryStats
    properties: SummaryStats
    combined: SummaryStats
    parse_failures: list[str]
def _stats(values: Iterable[int]) -> SummaryStats:
    values = list(values)
    if not values:
        raise ValueError("cannot summarize an empty value list")
    return SummaryStats(
        count=len(values),
        min=min(values),
        max=max(values),
        median=float(median(values)),
        average=float(sum(values) / len(values)),
        sd=float(pstdev(values)),
    )
def _is_target_namespace(tag: str, namespace: str) -> bool:
    return isinstance(tag, str) and tag.startswith("{" + namespace + "}")
def _local_name(tag: str) -> str:
    return tag.split("}", 1)[1]
def _entity_name_from_iri(iri: str) -> str:
    if "#" in iri:
        return iri.rsplit("#", 1)[1]
    return iri.rstrip("/").rsplit("/", 1)[-1]
def load_schema_entities(schema_path: str | Path) -> SchemaEntities:
    root = ET.parse(schema_path).getroot()
    owl_namespace = "http://www.w3.org/2002/07/owl#"
    class_tag = f"{{{owl_namespace}}}Class"
    object_property_tag = f"{{{owl_namespace}}}ObjectProperty"
    datatype_property_tag = f"{{{owl_namespace}}}DatatypeProperty"
    classes: set[str] = set()
    object_properties: set[str] = set()
    datatype_properties: set[str] = set()
    for element in root.iter():
        iri = element.attrib.get(RDF_ABOUT) or element.attrib.get(RDF_ID)
        if not iri:
            continue
        if element.tag == class_tag:
            classes.add(_entity_name_from_iri(iri))
        elif element.tag == object_property_tag:
            object_properties.add(_entity_name_from_iri(iri))
        elif element.tag == datatype_property_tag:
            datatype_properties.add(_entity_name_from_iri(iri))
    return SchemaEntities(
        classes=frozenset(classes),
        object_properties=frozenset(object_properties),
        datatype_properties=frozenset(datatype_properties),
    )
def count_lubm_symbols(file_path: str | Path, namespace: str = DEFAULT_LUBM_NAMESPACE) -> FileCount:
    file_path = Path(file_path)
    root = ET.parse(file_path).getroot()
    classes: set[str] = set()
    properties: set[str] = set()
    for element in root.iter():
        tag = element.tag
        if not _is_target_namespace(tag, namespace):
            continue
        if any(attribute in element.attrib for attribute in (RDF_ABOUT, RDF_ID, RDF_NODE_ID)):
            classes.add(tag)
        else:
            properties.add(tag)
    return FileCount(file=str(file_path), classes=len(classes), properties=len(properties))
def count_bioportal_like_entities(
    file_path: str | Path,
    schema_entities: SchemaEntities,
    namespace: str = DEFAULT_LUBM_NAMESPACE,
    include_import_closure: bool = True,
) -> FileCount:
    file_path = Path(file_path)
    root = ET.parse(file_path).getroot()
    classes: set[str] = set()
    properties: set[str] = set()
    imports_schema = False
    for element in root.iter():
        if element.tag == OWL_IMPORTS:
            resource = element.attrib.get(RDF_RESOURCE, "")
            if resource.endswith("univ-bench.owl") or resource.rstrip("#/") == namespace.rstrip("#/"):
                imports_schema = True
        tag = element.tag
        if _is_target_namespace(tag, namespace):
            local_name = _local_name(tag)
            if local_name in schema_entities.classes and any(attribute in element.attrib for attribute in (RDF_ABOUT, RDF_ID, RDF_NODE_ID)):
                classes.add(local_name)
            if local_name in schema_entities.properties:
                properties.add(local_name)
        for value in element.attrib.values():
            if not isinstance(value, str) or not value.startswith(namespace):
                continue
            entity_name = _entity_name_from_iri(value)
            if entity_name in schema_entities.classes:
                classes.add(entity_name)
            if entity_name in schema_entities.properties:
                properties.add(entity_name)
    if imports_schema and include_import_closure:
        classes = set(schema_entities.classes)
        properties = set(schema_entities.properties)
    return FileCount(file=str(file_path), classes=len(classes), properties=len(properties))
def analyze_directory(
    root_dir: str | Path,
    namespace: str = DEFAULT_LUBM_NAMESPACE,
    pattern: str = "*.owl",
    count_file: Callable[[str | Path], FileCount] | None = None,
) -> tuple[list[FileCount], list[str]]:
    root_dir = Path(root_dir)
    counts: list[FileCount] = []
    failures: list[str] = []
    count_file = count_file or (lambda file_path: count_lubm_symbols(file_path, namespace=namespace))
    for file_path in sorted(root_dir.rglob(pattern)):
        if not file_path.is_file():
            continue
        try:
            counts.append(count_file(file_path))
        except ET.ParseError:
            failures.append(str(file_path))
    return counts, failures
def summarize_counts(root_dir: str | Path, counts: list[FileCount], parse_failures: list[str]) -> DirectorySummary:
    if not counts:
        raise ValueError(f"no readable OWL files found under {root_dir}")
    return DirectorySummary(
        root=str(Path(root_dir)),
        file_count=len(counts),
        classes=_stats(item.classes for item in counts),
        properties=_stats(item.properties for item in counts),
        combined=_stats(item.combined for item in counts),
        parse_failures=parse_failures,
    )
def write_counts_csv(file_path: str | Path, counts: list[FileCount]) -> None:
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "classes", "properties", "combined"])
        writer.writeheader()
        for item in counts:
            writer.writerow(item.to_row())
def _summary_to_dict(summary: DirectorySummary) -> dict:
    return {
        "root": summary.root,
        "file_count": summary.file_count,
        "classes": asdict(summary.classes),
        "properties": asdict(summary.properties),
        "combined": asdict(summary.combined),
        "parse_failures": summary.parse_failures,
    }
def write_summary_json(file_path: str | Path, ontologies: DirectorySummary, modules: DirectorySummary) -> None:
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ontologies": _summary_to_dict(ontologies),
        "modules": _summary_to_dict(modules),
    }
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
def _fmt(value: float) -> str:
    return f"{value:.2f}"
def render_latex_rows(dataset_name: str, ontologies: DirectorySummary, modules: DirectorySummary) -> str:
    ont = ontologies.combined
    mod = modules.combined
    return (
        f"\\multirow{{2}}{{*}}{{{dataset_name}}} & Ontologies & {_fmt(ont.median)} & {_fmt(ont.average)} & {_fmt(ont.sd)} {LATEX_ROW_BREAK}\n"
        f"                         & Modules    & {_fmt(mod.median)} & {_fmt(mod.average)} & {_fmt(mod.sd)} {LATEX_ROW_BREAK}\n"
    )
def write_latex_rows(file_path: str | Path, dataset_name: str, ontologies: DirectorySummary, modules: DirectorySummary) -> None:
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(render_latex_rows(dataset_name, ontologies, modules), encoding="utf-8")
