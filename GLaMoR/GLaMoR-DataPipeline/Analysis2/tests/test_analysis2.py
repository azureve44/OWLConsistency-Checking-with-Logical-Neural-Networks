from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from Analysis2.analysis2.analyzer import (
    DEFAULT_LUBM_NAMESPACE,
    analyze_directory,
    count_bioportal_like_entities,
    count_lubm_symbols,
    load_schema_entities,
    render_latex_rows,
    summarize_counts,
    write_counts_csv,
    write_latex_rows,
    write_summary_json,
)
from Analysis2.analysis2.cli import main
ONTOLOGY_XML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rdf:RDF
  xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\"
  xmlns:ub=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#\">
  <ub:University rdf:about=\"http://example.org/u1\">
    <ub:name>University One</ub:name>
  </ub:University>
  <ub:Department rdf:about=\"http://example.org/d1\">
    <ub:subOrganizationOf rdf:resource=\"http://example.org/u1\" />
  </ub:Department>
  <ub:Professor rdf:about=\"http://example.org/p1\">
    <ub:worksFor rdf:resource=\"http://example.org/d1\" />
    <ub:teacherOf rdf:resource=\"http://example.org/c1\" />
  </ub:Professor>
</rdf:RDF>
"""
MODULE_XML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rdf:RDF
  xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\"
  xmlns:ub=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#\">
  <ub:UndergraduateStudent rdf:about=\"http://example.org/s1\">
    <ub:takesCourse rdf:resource=\"http://example.org/c1\" />
  </ub:UndergraduateStudent>
  <ub:Course rdf:about=\"http://example.org/c1\">
    <ub:name>Course One</ub:name>
  </ub:Course>
</rdf:RDF>
"""
SCHEMA_XML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rdf:RDF
  xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\"
  xmlns:owl=\"http://www.w3.org/2002/07/owl#\"
  xmlns:ub=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#\">
  <owl:Class rdf:about=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#University\" />
  <owl:Class rdf:about=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#Department\" />
  <owl:Class rdf:about=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#Professor\" />
  <owl:Class rdf:about=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#UndergraduateStudent\" />
  <owl:Class rdf:about=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#Course\" />
  <owl:ObjectProperty rdf:about=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#subOrganizationOf\" />
  <owl:ObjectProperty rdf:about=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#worksFor\" />
  <owl:ObjectProperty rdf:about=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#teacherOf\" />
  <owl:ObjectProperty rdf:about=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#takesCourse\" />
  <owl:DatatypeProperty rdf:about=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#name\" />
</rdf:RDF>
"""
ONTOLOGY_WITH_IMPORT_XML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<rdf:RDF
  xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\"
  xmlns:owl=\"http://www.w3.org/2002/07/owl#\"
  xmlns:ub=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl#\">
  <owl:Ontology rdf:about=\"\">
    <owl:imports rdf:resource=\"http://www.lehigh.edu/~zhp2/2004/0401/univ-bench.owl\" />
  </owl:Ontology>
  <ub:University rdf:about=\"http://example.org/u1\">
    <ub:name>University One</ub:name>
  </ub:University>
</rdf:RDF>
"""
class Analysis2Tests(unittest.TestCase):
    def test_count_lubm_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "sample.owl"
            file_path.write_text(ONTOLOGY_XML, encoding="utf-8")
            counts = count_lubm_symbols(file_path)
            self.assertEqual(counts.classes, 3)
            self.assertEqual(counts.properties, 4)
            self.assertEqual(counts.combined, 7)
    def test_count_bioportal_like_entities_uses_schema_and_import_closure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema_path = root / "univ-bench.owl"
            ontology_path = root / "University0.owl"
            module_path = root / "Department0.owl"
            schema_path.write_text(SCHEMA_XML, encoding="utf-8")
            ontology_path.write_text(ONTOLOGY_WITH_IMPORT_XML, encoding="utf-8")
            module_path.write_text(MODULE_XML, encoding="utf-8")
            schema_entities = load_schema_entities(schema_path)
            ontology_counts = count_bioportal_like_entities(ontology_path, schema_entities=schema_entities)
            module_counts = count_bioportal_like_entities(module_path, schema_entities=schema_entities)
            self.assertEqual(ontology_counts.classes, 5)
            self.assertEqual(ontology_counts.properties, 5)
            self.assertEqual(ontology_counts.combined, 10)
            self.assertEqual(module_counts.classes, 2)
            self.assertEqual(module_counts.properties, 2)
            self.assertEqual(module_counts.combined, 4)
    def test_analyze_directory_and_writers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ont_root = root / "ontologies"
            mod_root = root / "modules"
            out_root = root / "output"
            ont_root.mkdir()
            mod_root.mkdir()
            (ont_root / "University0.owl").write_text(ONTOLOGY_XML, encoding="utf-8")
            (ont_root / "University1.owl").write_text(MODULE_XML, encoding="utf-8")
            (mod_root / "Department0.owl").write_text(MODULE_XML, encoding="utf-8")
            ontology_counts, ontology_failures = analyze_directory(ont_root, namespace=DEFAULT_LUBM_NAMESPACE)
            module_counts, module_failures = analyze_directory(mod_root, namespace=DEFAULT_LUBM_NAMESPACE)
            ontology_summary = summarize_counts(ont_root, ontology_counts, ontology_failures)
            module_summary = summarize_counts(mod_root, module_counts, module_failures)
            write_counts_csv(out_root / "ontologies_counts.csv", ontology_counts)
            write_counts_csv(out_root / "modules_counts.csv", module_counts)
            write_summary_json(out_root / "summary.json", ontology_summary, module_summary)
            write_latex_rows(out_root / "lubm_table_rows.tex", "LUBM100", ontology_summary, module_summary)
            summary = json.loads((out_root / "summary.json").read_text(encoding="utf-8"))
            latex = (out_root / "lubm_table_rows.tex").read_text(encoding="utf-8")
            self.assertEqual(summary["ontologies"]["file_count"], 2)
            self.assertEqual(summary["modules"]["file_count"], 1)
            self.assertIn("\\multirow{2}{*}{LUBM100}", latex)
            self.assertIn("\\\\\n", latex)
            self.assertIn("Modules", latex)
    def test_cli_main_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ont_root = root / "ontologies"
            mod_root = root / "modules"
            out_root = root / "output"
            ont_root.mkdir()
            mod_root.mkdir()
            (ont_root / "University0.owl").write_text(ONTOLOGY_XML, encoding="utf-8")
            (mod_root / "Department0.owl").write_text(MODULE_XML, encoding="utf-8")
            exit_code = main([
                "--ontologies-root", str(ont_root),
                "--modules-root", str(mod_root),
                "--output-dir", str(out_root),
                "--dataset-name", "LUBM10",
            ])
            self.assertEqual(exit_code, 0)
            self.assertTrue((out_root / "summary.json").exists())
            self.assertTrue((out_root / "ontologies_counts.csv").exists())
            self.assertTrue((out_root / "modules_counts.csv").exists())
            self.assertTrue((out_root / "lubm_table_rows.tex").exists())
            self.assertIn("LUBM10", render_latex_rows("LUBM10", summarize_counts(ont_root, *analyze_directory(ont_root)), summarize_counts(mod_root, *analyze_directory(mod_root))))
    def test_cli_main_bioportal_like_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema_path = root / "univ-bench.owl"
            ont_root = root / "ontologies"
            mod_root = root / "modules"
            out_root = root / "output"
            schema_path.write_text(SCHEMA_XML, encoding="utf-8")
            ont_root.mkdir()
            mod_root.mkdir()
            (ont_root / "University0.owl").write_text(ONTOLOGY_WITH_IMPORT_XML, encoding="utf-8")
            (mod_root / "Department0.owl").write_text(MODULE_XML, encoding="utf-8")
            exit_code = main([
                "--metric", "bioportal_like",
                "--schema-path", str(schema_path),
                "--ontologies-root", str(ont_root),
                "--modules-root", str(mod_root),
                "--output-dir", str(out_root),
                "--dataset-name", "LUBM10",
            ])
            self.assertEqual(exit_code, 0)
            summary = json.loads((out_root / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["ontologies"]["combined"]["median"], 10.0)
            self.assertEqual(summary["modules"]["combined"]["median"], 4.0)
if __name__ == "__main__":
    unittest.main()
