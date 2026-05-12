#!/usr/bin/env python3
"""
hermit_pipeline/prepare_hermit_labels.py
─────────────────────────────────────────
Cleans and validates the raw HermiT output (hermit_raw.jsonl) into a stable
intermediate file (labelled_facts.jsonl) that the ModernBERT pipeline can
consume independently.

What this script does
──────────────────────
  1. Filters out records where HermiT errored or timed out
     (consistent == None)
  2. Adds a clean integer label field:
       consistent   → label 0
       inconsistent → label 1
  3. Writes hermit_benchmark.jsonl — HermiT verdicts + timing only,
     used later by evaluate_vs_hermit.py for the benchmark comparison
  4. Prints a class-balance summary

What this script does NOT do
─────────────────────────────
  - No text serialisation (that is prepare_modernbert_data.py's job)
  - No train/val/test splitting (same)
  - No ModernBERT-specific formatting

Inputs / outputs
─────────────────
  Input:  hermit_raw.jsonl          (from run_hermit.py)
  Output: labelled_facts.jsonl      → fed to modernbert_pipeline
          hermit_benchmark.jsonl    → fed to evaluate_vs_hermit.py
          label_stats.txt           → human-readable class balance report

Usage
──────
  python hermit_pipeline/prepare_hermit_labels.py \
      --hermit_raw  hermit_labels/hermit_raw.jsonl \
      --out_dir     hermit_labels/
"""

import json
import argparse
from pathlib import Path
from collections import Counter


def main():
    parser = argparse.ArgumentParser(
        description="Clean raw HermiT output into labelled_facts.jsonl."
    )
    parser.add_argument("--hermit_raw", required=True,
                        help="hermit_raw.jsonl from run_hermit.py")
    parser.add_argument("--out_dir", default="hermit_labels",
                        help="Output directory (default: hermit_labels/)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── load raw records ──────────────────────────────────────────────────
    raw_records = []
    skipped_errors = 0

    with open(args.hermit_raw) as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("consistent") is None:
                # HermiT errored or timed out on this record — discard
                skipped_errors += 1
                continue
            raw_records.append(rec)

    print(f"Loaded   : {len(raw_records):>7,} valid records")
    print(f"Skipped  : {skipped_errors:>7,} errored / timed-out records")

    # ── attach clean label field ──────────────────────────────────────────
    labelled = []
    for rec in raw_records:
        out_rec = dict(rec)
        out_rec["label"] = 0 if rec["consistent"] else 1
        labelled.append(out_rec)

    # ── class balance ─────────────────────────────────────────────────────
    counts = Counter(r["label"] for r in labelled)
    total = len(labelled)
    c0, c1 = counts[0], counts[1]
    print(f"\nClass balance:")
    print(f"  consistent(0)   : {c0:>7,}  ({100 * c0 / total:.1f}%)")
    print(f"  inconsistent(1) : {c1:>7,}  ({100 * c1 / total:.1f}%)")

    if c1 == 0:
        print("\n⚠  No inconsistent examples found.")
        print("   Re-run run_hermit.py with --inject_negatives.")

    # ── write labelled_facts.jsonl ────────────────────────────────────────
    # Keeps all original fields (individual, types, properties, source,
    # synthetic, injected_clash) plus the new 'label' field.
    # The ModernBERT pipeline reads this file and handles text serialisation.
    labelled_path = out_dir / "labelled_facts.jsonl"
    with open(labelled_path, "w") as fh:
        for rec in labelled:
            fh.write(json.dumps(rec) + "\n")

    # ── write hermit_benchmark.jsonl ──────────────────────────────────────
    # Stripped-down version: only the fields needed for the final comparison.
    # evaluate_vs_hermit.py reads this to get HermiT's verdict + timing.
    bench_path = out_dir / "hermit_benchmark.jsonl"
    with open(bench_path, "w") as fh:
        for rec in labelled:
            fh.write(json.dumps({
                "individual": rec["individual"],
                "consistent": rec["consistent"],
                "label": rec["label"],
                "hermit_ms": rec.get("hermit_ms", -1),
                "synthetic": rec.get("synthetic", False),
            }) + "\n")

    # ── write human-readable stats ────────────────────────────────────────
    stats_path = out_dir / "label_stats.txt"
    stats_path.write_text(
        f"HermiT label statistics\n"
        f"{'=' * 45}\n"
        f"Total records      : {total:>7,}\n"
        f"Skipped (errors)   : {skipped_errors:>7,}\n"
        f"consistent(0)      : {c0:>7,}  ({100 * c0 / total:.1f}%)\n"
        f"inconsistent(1)    : {c1:>7,}  ({100 * c1 / total:.1f}%)\n"
    )

    print(f"\nWrote:")
    print(f"  {labelled_path}    ← feed to modernbert_pipeline")
    print(f"  {bench_path}  ← feed to evaluate_vs_hermit.py")
    print(f"  {stats_path}")


if __name__ == "__main__":
    main()