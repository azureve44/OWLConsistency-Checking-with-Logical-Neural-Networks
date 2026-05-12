from __future__ import annotations
import argparse
from pathlib import Path
from .analyzer import (
    DEFAULT_LUBM_NAMESPACE,
    analyze_directory,
    count_bioportal_like_entities,
    load_schema_entities,
    render_latex_rows,
    summarize_counts,
    write_counts_csv,
    write_latex_rows,
    write_summary_json,
)
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze LUBM ontologies and modules using either used-vocabulary or BioPortal-like schema metrics.")
    parser.add_argument("--ontologies-root", required=True, help="Directory containing LUBM ontology OWL files.")
    parser.add_argument("--modules-root", required=True, help="Directory containing LUBM module OWL files.")
    parser.add_argument("--output-dir", required=True, help="Directory where CSV/JSON/TeX outputs will be written.")
    parser.add_argument("--dataset-name", default="LUBM100", help="Dataset label used in the generated LaTeX rows.")
    parser.add_argument("--namespace", default=DEFAULT_LUBM_NAMESPACE, help="Target XML namespace to count.")
    parser.add_argument("--pattern", default="*.owl", help="Glob pattern for input files.")
    parser.add_argument("--metric", choices=["used_vocabulary", "bioportal_like"], default="used_vocabulary", help="Counting strategy to use.")
    parser.add_argument("--schema-path", help="Path to the LUBM schema ontology (required for --metric bioportal_like).")
    parser.add_argument("--no-import-closure", action="store_true", help="Do not expand ontologies that import the benchmark schema to the full schema size.")
    return parser
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    count_file = None
    if args.metric == "bioportal_like":
        if not args.schema_path:
            raise SystemExit("--schema-path is required when --metric bioportal_like is used")
        schema_entities = load_schema_entities(args.schema_path)
        count_file = lambda file_path: count_bioportal_like_entities(
            file_path,
            schema_entities=schema_entities,
            namespace=args.namespace,
            include_import_closure=not args.no_import_closure,
        )
    ontology_counts, ontology_failures = analyze_directory(args.ontologies_root, namespace=args.namespace, pattern=args.pattern, count_file=count_file)
    module_counts, module_failures = analyze_directory(args.modules_root, namespace=args.namespace, pattern=args.pattern, count_file=count_file)
    ontology_summary = summarize_counts(args.ontologies_root, ontology_counts, ontology_failures)
    module_summary = summarize_counts(args.modules_root, module_counts, module_failures)
    write_counts_csv(output_dir / "ontologies_counts.csv", ontology_counts)
    write_counts_csv(output_dir / "modules_counts.csv", module_counts)
    write_summary_json(output_dir / "summary.json", ontology_summary, module_summary)
    write_latex_rows(output_dir / "lubm_table_rows.tex", args.dataset_name, ontology_summary, module_summary)
    print(f"Metric: {args.metric}")
    print(f"Ontologies analyzed: {ontology_summary.file_count}")
    print(f"Modules analyzed: {module_summary.file_count}")
    print(f"Ontology combined median/avg/sd: {ontology_summary.combined.median:.2f} / {ontology_summary.combined.average:.2f} / {ontology_summary.combined.sd:.2f}")
    print(f"Module combined median/avg/sd: {module_summary.combined.median:.2f} / {module_summary.combined.average:.2f} / {module_summary.combined.sd:.2f}")
    if ontology_summary.parse_failures or module_summary.parse_failures:
        print(f"Parse failures: {len(ontology_summary.parse_failures) + len(module_summary.parse_failures)}")
    print("LaTeX rows:")
    print(render_latex_rows(args.dataset_name, ontology_summary, module_summary), end="")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
