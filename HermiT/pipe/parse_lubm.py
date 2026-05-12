#!/usr/bin/env python3
"""
Parse University*_*.txt
into structured JSON-lines file
<RARITY> <predicate> <subject> <object>

Output (facts.jsonl) — one JSON object per individual:
  {
    "individual": "AssistantProfessor0",
    "types":      ["AssistantProfessor"],
    "properties": [["worksFor","Department0"], ["teacherOf","GraduateCourse0"]],
    "source":     "University0_0.txt"
  }

Usage
──────
  python parse_lubm.py --data_dir /path/to/lubm_txt --out facts.jsonl
  python parse_lubm.py --data_dir . --out facts.jsonl --verbose
"""

import re
import json
import argparse
from pathlib import Path
from collections import defaultdict


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────

_RE_BINARY = re.compile(r"^BINARY\s+(\S+)\s+(\S+)\s+(\S+)\s*$")


def parse_file(path: Path):
    """
    Return a list of (predicate, subject, object) triples from one txt file.
    Silently skips blank lines and non-BINARY lines (e.g. UNARY declarations
    if present in some variants of the dump).
    """
    triples = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or not line.startswith("BINARY"):
                continue
            m = _RE_BINARY.match(line)
            if not m:
                continue
            pred, subj, obj = m.group(1), m.group(2), m.group(3)
            triples.append((pred, subj, obj))
    return triples


def group_by_individual(triples, source_name: str):
    """
    Aggregate triples by subject individual.
    Returns a dict: individual → {"types": [...], "properties": [[p,o], ...]}
    """
    individuals = defaultdict(lambda: {"types": [], "properties": []})
    for pred, subj, obj in triples:
        if pred == "InstanceOf":
            individuals[subj]["types"].append(obj)
        else:
            individuals[subj]["properties"].append([pred, obj])
    return individuals


# ─────────────────────────────────────────────────────────────────────────────
# Statistics
# ─────────────────────────────────────────────────────────────────────────────

def print_stats(all_records):
    total_ind  = len(all_records)
    total_type = sum(len(r["types"])      for r in all_records)
    total_prop = sum(len(r["properties"]) for r in all_records)

    # predicate frequency
    pred_counts = defaultdict(int)
    class_counts = defaultdict(int)
    for r in all_records:
        for t in r["types"]:
            class_counts[t] += 1
        for p, _ in r["properties"]:
            pred_counts[p] += 1

    print(f"\nParsed statistics")
    print(f"  Individuals    : {total_ind:>8,}")
    print(f"  Type assertions: {total_type:>8,}")
    print(f"  Property facts : {total_prop:>8,}")
    print(f"\nTop-10 classes:")
    for cls, cnt in sorted(class_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {cls:<35} {cnt:>7,}")
    print(f"\nProperty predicates ({len(pred_counts)} distinct):")
    for pred, cnt in sorted(pred_counts.items(), key=lambda x: -x[1]):
        print(f"  {pred:<35} {cnt:>7,}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Parse LUBM BINARY txt files into per-individual JSONL."
    )
    parser.add_argument("--data_dir", required=True,
                        help="Directory containing University*_*.txt files")
    parser.add_argument("--out",      default="facts.jsonl",
                        help="Output JSONL path (default: facts.jsonl)")
    parser.add_argument("--verbose",  action="store_true")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    txt_files = sorted(data_dir.glob("University*_*.txt"))
    if not txt_files:
        raise FileNotFoundError(
            f"No University*_*.txt files found in {data_dir}"
        )
    print(f"Found {len(txt_files)} LUBM txt files in {data_dir}")

    all_records = []
    total_triples = 0

    for fpath in txt_files:
        triples = parse_file(fpath)
        total_triples += len(triples)
        grouped = group_by_individual(triples, fpath.name)

        for ind, data in grouped.items():
            all_records.append({
                "individual": ind,
                "types":      data["types"],
                "properties": data["properties"],
                "source":     fpath.name,
            })

        if args.verbose:
            print(f"  {fpath.name:<30} {len(triples):>6} triples  "
                  f"{len(grouped):>5} individuals")

    print(f"\nTotal triples    : {total_triples:,}")
    print(f"Total individuals: {len(all_records):,}")

    # Write output
    out_path = Path(args.out)
    with open(out_path, "w") as fh:
        for rec in all_records:
            fh.write(json.dumps(rec) + "\n")
    print(f"\nWrote {len(all_records):,} records → {out_path}")

    if args.verbose:
        print_stats(all_records)


if __name__ == "__main__":
    main()