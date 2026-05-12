#!/usr/bin/env python3
"""Aggregate per-module consistency predictions to university-level."""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
FALSE_VALUES = {"0", "false", "f", "no", "n", "inconsistent"}
TRUE_VALUES = {"1", "true", "t", "yes", "y", "consistent"}
def normalize_label(raw_label: str) -> str | None:
    label = (raw_label or "").strip().lower()
    if not label:
        return None
    if label in FALSE_VALUES:
        return "inconsistent"
    if label in TRUE_VALUES:
        return "consistent"
    return label
def aggregate(predictions_file, output_file):
    uni_votes = defaultdict(list)
    with open(predictions_file, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("file_name") or row.get("file")
            raw_label = row.get("consistency") or row.get("label")
            label = normalize_label(raw_label)
            if not filename or not label:
                continue
            if "_Department" in filename:
                uni = filename.split("_Department")[0]
            elif "_module" in filename.lower():
                uni = filename.split("_module")[0]
            else:
                uni = filename.split("_")[0]
            uni_votes[uni].append(1 if label == "inconsistent" else 0)
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["university", "consistency", "num_modules", "pct_inconsistent"])
        for uni, votes in sorted(uni_votes.items()):
            pct = sum(votes) / len(votes) * 100 if votes else 0.0
            label = "inconsistent" if any(v == 1 for v in votes) else "consistent"
            writer.writerow([uni, label, len(votes), f"{pct:.1f}%"])
    print(f"Aggregated {len(uni_votes)} universities -> {output_file}")
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python aggregate_predictions.py <predictions.csv> <output.csv>")
        sys.exit(1)
    aggregate(sys.argv[1], sys.argv[2])
