#!/usr/bin/env python3
"""
run_hermit.py
─────────────
Uses HermiT to check consistency of ontology fragments derived from LUBM.

Strategy
─────────
1. Load the LUBM TBox (univ-bench.owl) once as the background ontology.
2. For each individual record from facts.jsonl, build a minimal OWL file
   (TBox import + ABox assertions for that individual).
3. Call HermiT on the file — exit code 0 = consistent, non-zero = inconsistent.
4. Write labelled records to hermit_labels.jsonl:
     {"individual": ..., "consistent": true/false, "hermit_ms": 123}

Negative example injection
───────────────────────────
For training ModernBERT we need inconsistent examples too.  LUBM's TBox has
disjoint-class axioms (e.g. Professor DisjointWith Student).  We generate
synthetic inconsistencies by assigning an individual to two disjoint classes.
The --inject_negatives flag enables this; they are marked "synthetic": true.

HermiT invocation
──────────────────
  java -jar HermiT.jar --consistency <ontology.owl>
Exit 0  → consistent
Exit 1  → inconsistent (or error — we capture stderr to distinguish)

Usage
──────
  python run_hermit.py \
      --facts    facts.jsonl \
      --tbox     univ-bench.owl \
      --hermit   HermiT.jar \
      --out      hermit_labels.jsonl \
      [--workers 8] \
      [--inject_negatives] \
      [--max_records 5000]
"""

import json
import time
import shutil
import argparse
import tempfile
import subprocess
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# LUBM TBox disjoint pairs (from univ-bench.owl)
# Each pair is mutually disjoint — assigning one individual to both = UNSAT
# ─────────────────────────────────────────────────────────────────────────────

DISJOINT_PAIRS = [
    ("Professor",         "Student"),
    ("AssistantProfessor","GraduateStudent"),
    ("AssociateProfessor","UndergraduateStudent"),
    ("FullProfessor",     "GraduateStudent"),
    ("Lecturer",          "Student"),
    ("Professor",         "ResearchAssistant"),
    ("Course",            "Person"),
    ("Department",        "Person"),
    ("University",        "Person"),
]


# ─────────────────────────────────────────────────────────────────────────────
# OWL serialisation helpers
# ─────────────────────────────────────────────────────────────────────────────

LUBM_NS  = "http://swat.cse.lehigh.edu/onto/univ-bench.owl#"
TEMP_NS  = "http://example.org/abox#"


def individual_to_owl(record: dict, tbox_path: str) -> str:
    """
    Serialise one individual's facts as a minimal OWL/XML file that imports
    the LUBM TBox.  Uses OWL Functional Syntax which HermiT accepts directly.
    """
    ind  = record["individual"]
    types = record["types"]
    props = record["properties"]

    lines = [
        'Prefix(:=<http://example.org/abox#>)',
        f'Prefix(lubm:=<{LUBM_NS}>)',
        'Prefix(owl:=<http://www.w3.org/2002/07/owl#>)',
        '',
        'Ontology(<http://example.org/abox>',
        f'  Import(<{Path(tbox_path).as_uri()}>)',
        '',
    ]

    # Class assertions
    for t in types:
        lines.append(f'  ClassAssertion(lubm:{t} :{ind})')

    # Object property assertions
    for pred, obj in props:
        lines.append(f'  ObjectPropertyAssertion(lubm:{pred} :{ind} :{obj})')

    lines.append(')')
    return "\n".join(lines)


def inject_inconsistency(record: dict, disjoint_pair) -> dict:
    """
    Return a copy of record with an extra type added that creates a
    disjointness contradiction with an existing type.
    """
    import copy
    rec = copy.deepcopy(record)
    cls_a, cls_b = disjoint_pair
    existing_types = set(rec["types"])

    if cls_a in existing_types:
        rec["types"].append(cls_b)
        rec["injected_clash"] = f"{cls_a} DisjointWith {cls_b}"
    elif cls_b in existing_types:
        rec["types"].append(cls_a)
        rec["injected_clash"] = f"{cls_b} DisjointWith {cls_a}"
    else:
        # Individual has neither class → give it both
        rec["types"].extend([cls_a, cls_b])
        rec["injected_clash"] = f"{cls_a} DisjointWith {cls_b}"

    rec["synthetic"] = True
    return rec


# ─────────────────────────────────────────────────────────────────────────────
# HermiT invocation
# ─────────────────────────────────────────────────────────────────────────────

def run_hermit(owl_text: str, hermit_jar: str, java_bin: str = "java",
               timeout_s: int = 30) -> tuple[bool, int, str]:
    """
    Write owl_text to a temp file and invoke HermiT.
    Returns (is_consistent: bool, elapsed_ms: int, stderr: str).
    """
    with tempfile.NamedTemporaryFile(suffix=".owl", mode="w",
                                     delete=False) as tmp:
        tmp.write(owl_text)
        tmp_path = tmp.name

    try:
        t0 = time.monotonic()
        result = subprocess.run(
            [java_bin, "-jar", hermit_jar, "--consistency", tmp_path],
            capture_output=True, text=True, timeout=timeout_s,
        )
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        # HermiT exit codes:
        #   0 → consistent
        #   1 → inconsistent
        #   other → error / timeout / parse failure
        stderr = result.stderr.strip()
        if result.returncode == 0:
            return True, elapsed_ms, stderr
        elif result.returncode == 1 and "inconsistent" in result.stdout.lower():
            return False, elapsed_ms, stderr
        else:
            # Parse or runtime error — skip this record
            raise RuntimeError(
                f"HermiT exit {result.returncode}: {stderr[:200]}"
            )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"HermiT timed out after {timeout_s}s")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Worker (used by ProcessPoolExecutor)
# ─────────────────────────────────────────────────────────────────────────────

def _worker(args):
    record, tbox_path, hermit_jar, java_bin, timeout_s = args
    try:
        owl = individual_to_owl(record, tbox_path)
        consistent, ms, stderr = run_hermit(owl, hermit_jar, java_bin, timeout_s)
        out = dict(record)
        out["consistent"]   = consistent
        out["hermit_ms"]    = ms
        out["hermit_error"] = None
        return out
    except Exception as e:
        out = dict(record)
        out["consistent"]   = None
        out["hermit_ms"]    = -1
        out["hermit_error"] = str(e)
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Run HermiT consistency checks on LUBM individuals."
    )
    parser.add_argument("--facts",   required=True,
                        help="Input facts.jsonl from parse_lubm.py")
    parser.add_argument("--tbox",    required=True,
                        help="Path to univ-bench.owl (LUBM TBox)")
    parser.add_argument("--hermit",  required=True,
                        help="Path to HermiT.jar")
    parser.add_argument("--out",     default="hermit_labels.jsonl")
    parser.add_argument("--workers", type=int, default=4,
                        help="Parallel Java processes (default: 4)")
    parser.add_argument("--timeout", type=int, default=30,
                        help="Per-record HermiT timeout in seconds (default: 30)")
    parser.add_argument("--java",    default="java",
                        help="java binary (default: java)")
    parser.add_argument("--inject_negatives", action="store_true",
                        help="Also generate synthetic inconsistent examples")
    parser.add_argument("--max_records", type=int, default=None,
                        help="Cap total records processed (for quick testing)")
    args = parser.parse_args()

    # Validate paths
    for label, path in [("facts",  args.facts),
                         ("tbox",   args.tbox),
                         ("hermit", args.hermit)]:
        if not Path(path).exists():
            raise FileNotFoundError(f"--{label} path not found: {path}")

    if not shutil.which(args.java):
        raise EnvironmentError(f"java binary not found: {args.java}")

    # Load records
    records = []
    with open(args.facts) as fh:
        for line in fh:
            records.append(json.loads(line))

    if args.max_records:
        records = records[:args.max_records]

    # Optionally inject synthetic inconsistencies
    if args.inject_negatives:
        import random, copy
        random.seed(42)
        neg_records = []
        for rec in records:
            pair = random.choice(DISJOINT_PAIRS)
            neg_records.append(inject_inconsistency(rec, pair))
        records = records + neg_records
        print(f"After negative injection: {len(records)} records "
              f"({len(neg_records)} synthetic inconsistencies)")

    print(f"Processing {len(records)} records with {args.workers} workers …")

    # Build worker args
    worker_args = [
        (rec, args.tbox, args.hermit, args.java, args.timeout)
        for rec in records
    ]

    out_path = Path(args.out)
    done = skipped = consistent_count = inconsistent_count = 0

    with open(out_path, "w") as out_fh, \
         ProcessPoolExecutor(max_workers=args.workers) as pool:

        futures = {pool.submit(_worker, wa): wa[0]["individual"]
                   for wa in worker_args}

        for fut in as_completed(futures):
            result = fut.result()
            if result["consistent"] is None:
                skipped += 1
            else:
                out_fh.write(json.dumps(result) + "\n")
                if result["consistent"]:
                    consistent_count += 1
                else:
                    inconsistent_count += 1
            done += 1
            if done % 500 == 0:
                print(f"  {done}/{len(records)}  "
                      f"consistent={consistent_count}  "
                      f"inconsistent={inconsistent_count}  "
                      f"skipped={skipped}")

    print(f"\nFinished.")
    print(f"  Consistent   : {consistent_count:>7,}")
    print(f"  Inconsistent : {inconsistent_count:>7,}")
    print(f"  Skipped/err  : {skipped:>7,}")
    print(f"\nWrote → {out_path}")


if __name__ == "__main__":
    main()