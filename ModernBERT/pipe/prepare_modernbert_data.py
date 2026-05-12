"""
modernbert_pipeline/prepare_modernbert_data.py
──────────────────────────────────────────────
Convert labelled_facts.jsonl (output of HermiT pipeline) into
ModernBERT-ready JSONL splits with stratified 70/15/15 sampling

In:  hermit_labels/labelled_facts.jsonl
Out: (in --out_dir):
  train.jsonl   {"text": "...", "label": 0|1}
  val.jsonl
  test.jsonl
  data_stats.txt

run after the HermiT pipeline

Usage
──────
  python modernbert_pipeline/prepare_modernbert_data.py \
      --labelled_facts hermit_labels/labelled_facts.jsonl \
      --out_dir        modernbert_data/ \
      [--max_tokens 512] [--seed 42]
"""

import json
import random
import argparse
from pathlib import Path
from collections import Counter


# ─────────────────────────────────────────────────────────────────────────────
# Text serialisation (same format as HermiT pipeline)
# ─────────────────────────────────────────────────────────────────────────────

def serialise(record: dict, max_tokens: int = 512) -> str:
    """
    Linearise one individual's ABox facts into a flat text string.

    Format:
      "<individual> is a <Type1> , <Type2> . <prop1> <obj1> . <prop2> <obj2> ."

    CamelCase identifiers are kept intact — ModernBERT's tokeniser sub-word
    splits them naturally (Assistant ##Professor ##0).
    """
    ind = record["individual"]
    types = record.get("types", [])
    props = record.get("properties", [])

    parts = [ind]

    if types:
        parts += ["is", "a", " , ".join(types)]

    parts.append(".")

    token_budget = max_tokens - len(parts)
    for pred, obj in props:
        chunk = [pred, obj, "."]
        if token_budget - len(chunk) < 0:
            break
        parts.extend(chunk)
        token_budget -= len(chunk)

    # Surface the injected clash token so the model can learn disjointness
    if record.get("synthetic") and record.get("injected_clash"):
        parts += ["[CLASH]", record["injected_clash"]]

    return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Stratified split
# ─────────────────────────────────────────────────────────────────────────────

def stratified_split(records, train_r=0.70, val_r=0.15, seed=42):
    """
    Stratify by label so class balance is preserved across all three splits.
    """
    rng = random.Random(seed)
    by_label = {}
    for rec in records:
        by_label.setdefault(rec["label"], []).append(rec)

    train, val, test = [], [], []
    for lbl, group in sorted(by_label.items()):
        rng.shuffle(group)
        n = len(group)
        n_val = round(n * val_r)
        n_test = round(n * (1 - train_r - val_r))
        n_train = n - n_val - n_test
        train += group[:n_train]
        val += group[n_train: n_train + n_val]
        test += group[n_train + n_val:]

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return train, val, test


# ─────────────────────────────────────────────────────────────────────────────
# Writers
# ─────────────────────────────────────────────────────────────────────────────

def write_jsonl(records, path: Path):
    with open(path, "w") as fh:
        for rec in records:
            fh.write(json.dumps({"text": rec["text"], "label": rec["label"]}) + "\n")


def write_stats(splits: dict, path: Path):
    lines = ["ModernBERT data statistics", "=" * 55]
    for name, recs in splits.items():
        counts = Counter(r["label"] for r in recs)
        total = len(recs)
        c0 = counts.get(0, 0)
        c1 = counts.get(1, 0)
        lines.append(
            f"\n{name:<8}  total={total:>7,}  "
            f"consistent(0)={c0:>6,} ({100 * c0 / total:.1f}%)  "
            f"inconsistent(1)={c1:>6,} ({100 * c1 / total:.1f}%)"
        )
    path.write_text("\n".join(lines) + "\n")
    print(path.read_text())


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Prepare ModernBERT training splits from HermiT labels."
    )
    parser.add_argument("--labelled_facts", required=True,
                        help="hermit_labels/labelled_facts.jsonl")
    parser.add_argument("--out_dir", default="modernbert_data",
                        help="Output directory (default: modernbert_data/)")
    parser.add_argument("--max_tokens", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── load ──────────────────────────────────────────────────────────────
    raw, skipped = [], 0
    with open(args.labelled_facts) as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("consistent") is None:
                skipped += 1
                continue
            raw.append(rec)

    print(f"Loaded {len(raw):,} labelled records  ({skipped} skipped)")

    # ── serialise to text ─────────────────────────────────────────────────
    dataset = []
    for rec in raw:
        dataset.append({
            "text": serialise(rec, args.max_tokens),
            "label": 0 if rec["consistent"] else 1,
            "individual": rec["individual"],
            "synthetic": rec.get("synthetic", False),
        })

    counts = Counter(r["label"] for r in dataset)
    print(f"Label distribution: consistent(0)={counts[0]:,}  "
          f"inconsistent(1)={counts[1]:,}")

    if counts[1] == 0:
        print("\n No inconsistent examples found in the input.")
        print("   Re-run the HermiT pipeline with --inject_negatives.")

    # ── split ─────────────────────────────────────────────────────────────
    train, val, test = stratified_split(dataset, seed=args.seed)

    # ── write ─────────────────────────────────────────────────────────────
    write_jsonl(train, out_dir / "train.jsonl")
    write_jsonl(val, out_dir / "val.jsonl")
    write_jsonl(test, out_dir / "test.jsonl")
    write_stats({"train": train, "val": val, "test": test},
                out_dir / "data_stats.txt")

    print(f"\nWrote to {out_dir.resolve()}/")
    print(f"  train.jsonl  {len(train):>7,}")
    print(f"  val.jsonl    {len(val):>7,}")
    print(f"  test.jsonl   {len(test):>7,}")


if __name__ == "__main__":
    main()