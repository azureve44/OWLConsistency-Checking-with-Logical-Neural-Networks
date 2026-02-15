import sys
from pathlib import Path
from rdflib import Graph, RDF, RDFS, OWL, URIRef


def short(u):
    u = str(u)
    return u.split("#")[-1].split("/")[-1]


def extract_owl_to_ir(owl_path: Path, out_txt: Path):
    g = Graph()
    g.parse(owl_path)

    lines = set()

    # ---- Classes ----
    for c in g.subjects(RDF.type, OWL.Class):
        lines.add(f"UNARY is {short(c)} Class")

    # ---- Object Properties ----
    for p in g.subjects(RDF.type, OWL.ObjectProperty):
        lines.add(f"UNARY is {short(p)} ObjectProperty")

    # ---- SubClassOf ----
    for a, b in g.subject_objects(RDFS.subClassOf):
        if isinstance(a, URIRef) and isinstance(b, URIRef):
            lines.add(f"BINARY SubClassOf {short(a)} {short(b)}")

    # ---- DisjointWith ----
    for a, b in g.subject_objects(OWL.disjointWith):
        lines.add(f"BINARY DisjointWith {short(a)} {short(b)}")

    # ---- Domain / Range ----
    for p, d in g.subject_objects(RDFS.domain):
        lines.add(f"BINARY Domain {short(p)} {short(d)}")

    for p, r in g.subject_objects(RDFS.range):
        lines.add(f"BINARY Range {short(p)} {short(r)}")

    # ---- InverseOf ----
    for p, q in g.subject_objects(OWL.inverseOf):
        lines.add(f"BINARY InverseOf {short(p)} {short(q)}")

    # ---- Class Assertions ----
    for x, c in g.subject_objects(RDF.type):
        if c not in (OWL.Class, OWL.ObjectProperty):
            lines.add(f"BINARY InstanceOf {short(x)} {short(c)}")

    # ---- Object Property Assertions ----
    object_props = set(g.subjects(RDF.type, OWL.ObjectProperty))
    for s, p, o in g:
        if p in object_props and isinstance(o, URIRef):
            lines.add(f"BINARY {short(p)} {short(s)} {short(o)}")

    out_txt.parent.mkdir(parents=True, exist_ok=True)
    with open(out_txt, "w") as f:
        for l in sorted(lines):
            f.write(l + "\n")


def main():
    if len(sys.argv) != 3:
        print("Usage: python owl_to_ir.py <owl_dir> <out_dir>")
        sys.exit(1)

    owl_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])

    out_dir.mkdir(parents=True, exist_ok=True)

    owl_files = list(owl_dir.glob("*.owl"))
    if not owl_files:
        print("No .owl files found")
        return

    for owl_file in owl_files:
        try:
            out_file = out_dir / (owl_file.stem + ".txt")
            extract_owl_to_ir(owl_file, out_file)
            print(f"[OK] {owl_file.name} → {out_file.name}")
        except Exception as e:
            print(f"[FAIL] {owl_file.name}: {e}")


if __name__ == "__main__":
    main()

