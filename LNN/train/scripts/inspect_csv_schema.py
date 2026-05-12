#!/usr/bin/env python3
"""Quick CSV schema inspector for the GLaMoR split files."""

import argparse
import csv
import sys


def set_csv_field_limit():
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit = limit // 10


def inspect(path, max_rows):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        print(f"\n=== {path} ===")
        print(f"columns: {reader.fieldnames}")
        for idx, row in enumerate(reader):
            if idx >= max_rows:
                break
            short = {k: (str(v)[:120] + "..." if len(str(v)) > 120 else v) for k, v in row.items()}
            print(f"row[{idx}]: {short}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", help="CSV files to inspect")
    parser.add_argument("--max_rows", type=int, default=2)
    args = parser.parse_args()

    set_csv_field_limit()

    for p in args.paths:
        inspect(p, args.max_rows)


if __name__ == "__main__":
    main()

