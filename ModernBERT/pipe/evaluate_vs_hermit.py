#!/usr/bin/env python3
"""
evaluate_vs_hermit.py
─────────────────────
Loads a trained ModernBERT checkpoint, runs inference on the test split,
and produces a side-by-side comparison against HermiT's verdicts.

Metrics reported
─────────────────
  Agreement rate  — how often ModernBERT and HermiT agree
  ModernBERT F1   — treating HermiT as ground truth
  Per-class breakdown (consistent vs inconsistent)
  Latency comparison  — ModernBERT ms/example vs HermiT ms/example

Usage
──────
  python evaluate_vs_hermit.py \
      --checkpoint checkpoints/lubm_consistency/latest-rank0.pt \
      --test       dataset/test.jsonl \
      --benchmark  dataset/hermit_benchmark.jsonl \
      [--batch_size 64] [--device cuda]
"""

import json
import time
import argparse
import numpy as np
from pathlib import Path
from collections import defaultdict

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import (
    classification_report, confusion_matrix,
    accuracy_score, f1_score,
)


# ─────────────────────────────────────────────────────────────────────────────
# Dataset
# ─────────────────────────────────────────────────────────────────────────────

class ConsistencyDataset(Dataset):
    def __init__(self, jsonl_path: str, tokenizer, max_length: int = 512):
        self.examples = []
        with open(jsonl_path) as fh:
            for line in fh:
                rec = json.loads(line)
                self.examples.append(rec)
        self.tokenizer  = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        rec = self.examples[idx]
        enc = self.tokenizer(
            rec["text"],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids":      enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "label":          torch.tensor(rec["label"], dtype=torch.long),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Inference
# ─────────────────────────────────────────────────────────────────────────────

def run_inference(model, loader, device):
    model.eval()
    all_preds, all_labels, all_probs = [], [], []
    elapsed_total = 0.0

    with torch.no_grad():
        for batch in loader:
            input_ids      = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels         = batch["label"]

            t0     = time.perf_counter()
            logits = model(input_ids=input_ids,
                           attention_mask=attention_mask).logits
            elapsed_total += time.perf_counter() - t0

            probs = torch.softmax(logits, dim=-1)
            preds = logits.argmax(dim=-1).cpu().numpy()

            all_preds.extend(preds.tolist())
            all_labels.extend(labels.numpy().tolist())
            all_probs.extend(probs[:, 1].cpu().numpy().tolist())

    n_examples = len(all_labels)
    ms_per_example = (elapsed_total * 1000) / n_examples
    return all_preds, all_labels, all_probs, ms_per_example


# ─────────────────────────────────────────────────────────────────────────────
# HermiT timing stats
# ─────────────────────────────────────────────────────────────────────────────

def hermit_latency(benchmark_path: str):
    times = []
    with open(benchmark_path) as fh:
        for line in fh:
            rec = json.loads(line)
            ms = rec.get("hermit_ms", -1)
            if ms >= 0:
                times.append(ms)
    if not times:
        return None
    return {
        "mean_ms":   np.mean(times),
        "median_ms": np.median(times),
        "p95_ms":    np.percentile(times, 95),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Compare ModernBERT predictions against HermiT verdicts."
    )
    parser.add_argument("--checkpoint",  required=True)
    parser.add_argument("--test",        required=True,
                        help="dataset/test.jsonl")
    parser.add_argument("--benchmark",   required=True,
                        help="dataset/hermit_benchmark.jsonl")
    parser.add_argument("--model_name",  default="answerdotai/ModernBERT-base")
    parser.add_argument("--batch_size",  type=int, default=64)
    parser.add_argument("--max_length",  type=int, default=512)
    parser.add_argument("--device",      default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    print(f"Device: {args.device}")

    # ── load model ────────────────────────────────────────────────────────
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    model     = AutoModelForSequenceClassification.from_pretrained(
        args.model_name, num_labels=2
    )

    ckpt = torch.load(args.checkpoint, map_location="cpu")
    state = ckpt.get("state", ckpt.get("model", ckpt))
    model.load_state_dict(state, strict=False)
    model.to(args.device)

    # ── dataset + loader ──────────────────────────────────────────────────
    dataset = ConsistencyDataset(args.test, tokenizer, args.max_length)
    loader  = DataLoader(dataset, batch_size=args.batch_size,
                         shuffle=False, num_workers=4, pin_memory=True)

    print(f"Test examples: {len(dataset)}")

    # ── inference ─────────────────────────────────────────────────────────
    preds, labels, probs, bert_ms = run_inference(model, loader, args.device)

    # ── ModernBERT metrics (vs HermiT ground truth) ────────────────────────
    acc = accuracy_score(labels, preds)
    f1  = f1_score(labels, preds, average="binary", pos_label=1)
    agreement = (np.array(preds) == np.array(labels)).mean()

    print("\n" + "═" * 65)
    print("ModernBERT vs HermiT — Test Set Results")
    print("═" * 65)
    print(f"  Agreement rate      : {agreement:.4f}  ({int(agreement*len(labels))}/{len(labels)})")
    print(f"  Accuracy            : {acc:.4f}")
    print(f"  F1 (inconsistent=1) : {f1:.4f}")
    print(f"\nPer-class report (HermiT = ground truth):")
    print(classification_report(labels, preds,
                                  target_names=["consistent", "inconsistent"],
                                  digits=4))

    cm = confusion_matrix(labels, preds)
    print("Confusion matrix (rows=HermiT, cols=ModernBERT):")
    print(f"  {'':20} consistent  inconsistent")
    print(f"  {'HermiT consistent':20} {cm[0,0]:>10}  {cm[0,1]:>12}")
    print(f"  {'HermiT inconsistent':20} {cm[1,0]:>10}  {cm[1,1]:>12}")

    # ── Latency comparison ─────────────────────────────────────────────────
    h_lat = hermit_latency(args.benchmark)
    print("\nLatency comparison (per example):")
    print(f"  ModernBERT : {bert_ms:.2f} ms")
    if h_lat:
        print(f"  HermiT     : mean={h_lat['mean_ms']:.1f} ms  "
              f"median={h_lat['median_ms']:.1f} ms  "
              f"p95={h_lat['p95_ms']:.1f} ms")
        speedup = h_lat["mean_ms"] / bert_ms if bert_ms > 0 else float("nan")
        print(f"  Speedup    : {speedup:.1f}×")
    else:
        print("  HermiT     : timing data not available")


if __name__ == "__main__":
    main()